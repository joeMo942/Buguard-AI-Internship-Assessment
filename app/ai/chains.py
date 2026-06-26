from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List
from sqlalchemy.future import select as sa_select
import json

from app.ai.llm import get_llm
from app.ai.prompts import nl_query_prompt, risk_scoring_prompt, enrichment_prompt, report_prompt
from app.schemas.analysis import QueryFilter, RiskScoreResponse, EnrichmentResponse, NLQueryResponse
from app.ai.grounding import get_all_assets_summary, get_asset_by_id_with_context, execute_asset_filter, format_single_asset, get_asset_statistics
from app.ai.guardrails import sanitize_report
from app.models.asset import Asset

async def run_nl_query_chain(db: AsyncSession, user_input: str, org_id: str = "default") -> NLQueryResponse:
    """
    Capability 1: Natural-language asset query.
    Two-step process: LLM translates NL to JSON filter -> We execute filter against DB.
    """
    llm = get_llm(temperature=0.0)
    
    # Step 1: NL -> Structured Filter
    structured_llm = llm.with_structured_output(QueryFilter)
    chain = nl_query_prompt | structured_llm
    
    filter_params: QueryFilter = await chain.ainvoke({"user_input": user_input})
    
    # Step 2: Execute filter
    assets = await execute_asset_filter(
        db=db,
        org_id=org_id,
        types=filter_params.types,
        statuses=filter_params.statuses,
        tags=filter_params.tags,
        value_contains=filter_params.value_contains
    )
    
    formatted_assets = [format_single_asset(a) for a in assets]
    
    return NLQueryResponse(
        query_interpreted=filter_params,
        assets_found=len(assets),
        assets=formatted_assets
    )

async def run_risk_scoring_chain(db: AsyncSession, asset_id: str, org_id: str = "default") -> RiskScoreResponse:
    """
    Capability 2: Risk scoring & summarization for a specific asset.
    """
    context = await get_asset_by_id_with_context(db, asset_id, org_id=org_id)
    if not context:
        raise ValueError(f"Asset with ID {asset_id} not found.")
        
    llm = get_llm(temperature=0.0)
    structured_llm = llm.with_structured_output(RiskScoreResponse)
    
    chain = risk_scoring_prompt | structured_llm
    
    response: RiskScoreResponse = await chain.ainvoke({
        "asset_context": json.dumps(context, indent=2)
    })
    
    return response

async def run_enrichment_chain(db: AsyncSession, asset_id: str, org_id: str = "default") -> EnrichmentResponse:
    """
    Capability 3: Automated enrichment & categorization.
    """
    context = await get_asset_by_id_with_context(db, asset_id, org_id=org_id)
    if not context:
        raise ValueError(f"Asset with ID {asset_id} not found.")
        
    llm = get_llm(temperature=0.0)
    structured_llm = llm.with_structured_output(EnrichmentResponse)
    
    chain = enrichment_prompt | structured_llm
    
    response: EnrichmentResponse = await chain.ainvoke({
        "asset_context": json.dumps(context, indent=2)
    })
    
    # Write enrichments back to the database
    asset_stmt = sa_select(Asset).where(Asset.id == asset_id)
    asset_result = await db.execute(asset_stmt)
    asset = asset_result.scalar_one()
    
    # Merge suggested tags
    existing_tags = asset.tags or []
    asset.tags = list(set(existing_tags + response.suggested_tags))
    
    # Merge suggested metadata
    existing_meta = asset.metadata_ or {}
    existing_meta.update(response.suggested_metadata)
    existing_meta["environment"] = response.environment
    existing_meta["criticality"] = response.criticality
    existing_meta["category"] = response.category
    asset.metadata_ = existing_meta
    
    await db.commit()
    
    return response

async def run_report_chain(db: AsyncSession, org_id: str = "default") -> str:
    """
    Capability 4: Natural-language report generation.
    Returns markdown text.
    """
    assets_summary = await get_all_assets_summary(db, org_id=org_id)
    stats = await get_asset_statistics(db, org_id=org_id)
    
    # Pre-fetch known values for post-generation validation and prompt injection
    result = await db.execute(sa_select(Asset.id, Asset.value).where(Asset.org_id == org_id))
    rows = result.fetchall()
    known_ids = {r[0] for r in rows}
    known_values = {r[1] for r in rows}
    valid_references = json.dumps([{"id": r[0], "value": r[1]} for r in rows])
    
    llm = get_llm(temperature=0.2) # Slightly higher temp for better narrative flow
    
    chain = report_prompt | llm
    
    response = await chain.ainvoke({
        "assets_summary": assets_summary,
        "valid_references": valid_references,
        "stats": json.dumps(stats, default=str)
    })
    
    raw_text = response.content
    if isinstance(raw_text, list):
        raw_text = "\n".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in raw_text
        )
    
    return sanitize_report(raw_text, known_ids, known_values)
