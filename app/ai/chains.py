from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List
from sqlalchemy.future import select as sa_select
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

from app.ai.llm import get_llm
from app.config import settings
from app.ai.prompts import nl_query_prompt, risk_scoring_prompt, enrichment_prompt, report_prompt
from app.schemas.analysis import QueryFilter, RiskScoreResponse, EnrichmentResponse, NLQueryResponse, GroupRiskScoreResponse
from app.ai.grounding import get_all_assets_summary, get_asset_by_id_with_context, execute_asset_filter, format_single_asset, get_asset_statistics
from app.ai.guardrails import sanitize_report
from app.models.asset import Asset
from app.ai.cache import llm_cache

async def run_nl_query_chain(db: AsyncSession, user_input: str, org_id: str = "default") -> NLQueryResponse:
    """
    Capability 1: Natural-language asset query.
    Two-step process: LLM translates NL to JSON filter -> We execute filter against DB.
    """
    llm = get_llm(temperature=0.0)
    
    # Step 1: NL -> Structured Filter
    cache_key = {"user_input": user_input, "org_id": org_id}
    cached_filter = llm_cache.get("nl_query", cache_key)
    
    if cached_filter:
        filter_params = cached_filter
    else:
        structured_llm = llm.with_structured_output(QueryFilter)
        chain = nl_query_prompt | structured_llm
        chain = chain.with_retry(stop_after_attempt=3)
        
        filter_params: QueryFilter = await chain.ainvoke({"user_input": user_input})
        llm_cache.set("nl_query", cache_key, filter_params)
    
    if filter_params.is_ambiguous:
        return NLQueryResponse(
            query_interpreted=filter_params,
            assets_found=0,
            page=1,
            page_size=50,
            assets=[],
            clarifying_question=filter_params.clarifying_question
        )
    
    # Step 2: Execute filter
    result = await execute_asset_filter(
        db=db,
        org_id=org_id,
        types=filter_params.types,
        statuses=filter_params.statuses,
        tags=filter_params.tags,
        value_contains=filter_params.value_contains
    )
    
    assets = result["assets"]
    formatted_assets = [format_single_asset(a) for a in assets]
    
    return NLQueryResponse(
        query_interpreted=filter_params,
        assets_found=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        assets=formatted_assets
    )

async def run_risk_scoring_chain(db: AsyncSession, asset_id: str, org_id: str = "default") -> RiskScoreResponse:
    """
    Capability 2: Risk scoring & summarization for a specific asset.
    """
    context = await get_asset_by_id_with_context(db, asset_id, org_id=org_id)
    if not context:
        raise ValueError(f"Asset with ID {asset_id} not found.")
        
    cache_key = {"asset_id": asset_id, "org_id": org_id}
    cached = llm_cache.get("risk_scoring", cache_key)
    if cached:
        return cached

    llm = get_llm(temperature=0.0)
    structured_llm = llm.with_structured_output(RiskScoreResponse)
    
    chain = risk_scoring_prompt | structured_llm
    chain = chain.with_retry(stop_after_attempt=3)
    
    response: RiskScoreResponse = await chain.ainvoke({
        "asset_context": json.dumps(context, indent=2)
    })
    
    llm_cache.set("risk_scoring", cache_key, response)
    return response

async def run_group_risk_scoring_chain(assets_data: List[dict]) -> GroupRiskScoreResponse:
    """Uses the LLM to score the risk of a group of assets."""
    llm = ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL, 
        temperature=0.0
    )
    
    cache_key = {"assets_ids": [a.get("asset", {}).get("id") for a in assets_data]}
    cached = llm_cache.get("group_risk_scoring", cache_key)
    if cached:
        return cached

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert security analyst. Evaluate the overall risk of these assets and output JSON matching the GroupRiskScoreResponse schema."),
        ("human", "Assets: {assets_json}")
    ])
    
    chain = prompt | llm.with_structured_output(GroupRiskScoreResponse)
    chain = chain.with_retry(stop_after_attempt=3)
    
    assets_json = json.dumps(assets_data, indent=2)
    response = await chain.ainvoke({"assets_json": assets_json})
    llm_cache.set("group_risk_scoring", cache_key, response)
    return response

async def run_enrichment_chain(db: AsyncSession, asset_id: str, org_id: str = "default") -> EnrichmentResponse:
    """
    Capability 3: Automated enrichment & categorization.
    """
    context = await get_asset_by_id_with_context(db, asset_id, org_id=org_id)
    if not context:
        raise ValueError(f"Asset with ID {asset_id} not found.")
        
    cache_key = {"asset_id": asset_id, "org_id": org_id}
    cached = llm_cache.get("enrichment", cache_key)
    if cached:
        response = cached
    else:
        llm = get_llm(temperature=0.0)
        structured_llm = llm.with_structured_output(EnrichmentResponse)
        
        chain = enrichment_prompt | structured_llm
        chain = chain.with_retry(stop_after_attempt=3)
        
        response: EnrichmentResponse = await chain.ainvoke({
            "asset_context": json.dumps(context, indent=2)
        })
        llm_cache.set("enrichment", cache_key, response)
    
    # Write enrichments back to the database
    asset_stmt = sa_select(Asset).where(Asset.id == asset_id, Asset.org_id == org_id)
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

async def run_report_chain(
    db: AsyncSession, 
    org_id: str = "default",
    types: List[str] = None,
    statuses: List[str] = None,
    tags: List[str] = None
) -> str:
    """
    Capability 4: Natural-language report generation.
    Returns markdown text.
    """
    cache_key = {"org_id": org_id, "types": types, "statuses": statuses, "tags": tags}
    cached = llm_cache.get("report", cache_key)
    if cached:
        return cached

    if any([types, statuses, tags]):
        result = await execute_asset_filter(
            db, org_id=org_id, types=types, statuses=statuses, tags=tags, page_size=200
        )
        from app.ai.grounding import format_assets_for_prompt
        assets_summary = format_assets_for_prompt(result["assets"])
        stats = {"filtered": True, "total_assets": result["total"]}
        rows = [(a.id, a.value) for a in result["assets"]]
    else:
        assets_summary = await get_all_assets_summary(db, org_id=org_id)
        stats = await get_asset_statistics(db, org_id=org_id)
        result_all = await db.execute(sa_select(Asset.id, Asset.value).where(Asset.org_id == org_id))
        rows = result_all.fetchall()
    
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
    
    final_report = sanitize_report(raw_text, known_ids, known_values)
    llm_cache.set("report", cache_key, final_report)
    return final_report
