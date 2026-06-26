from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List

from app.database import get_db
from app.ai.chains import run_nl_query_chain, run_risk_scoring_chain, run_enrichment_chain, run_report_chain, run_group_risk_scoring_chain
from app.ai.agent import run_agent
from app.dependencies import get_current_org, limiter, require_role
from app.schemas.analysis import RiskScoreResponse, EnrichmentResponse, NLQueryResponse, GroupAssetRequest, GroupRiskScoreResponse
from app.ai.grounding import get_asset_by_id_with_context

router = APIRouter(prefix="/analyze", tags=["analysis"])

class QueryRequest(BaseModel):
    question: str

class AssetRequest(BaseModel):
    asset_id: str

@router.post("/query", response_model=NLQueryResponse, dependencies=[Depends(require_role(["admin", "analyst"]))])
@limiter.limit("10/minute")
async def analyze_query(request: Request, payload: QueryRequest, db: AsyncSession = Depends(get_db), org_id: str = Depends(get_current_org)):
    """
    Capability 1: Natural-language asset query.
    Translates a plain-English question into a structured query and returns matching assets.
    """
    try:
        return await run_nl_query_chain(db, payload.question, org_id=org_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/risk", response_model=RiskScoreResponse, dependencies=[Depends(require_role(["admin", "analyst"]))])
@limiter.limit("10/minute")
async def analyze_risk(request: Request, payload: AssetRequest, db: AsyncSession = Depends(get_db), org_id: str = Depends(get_current_org)):
    """
    Capability 2: Risk scoring & summarization for a specific asset.
    """
    try:
        return await run_risk_scoring_chain(db, payload.asset_id, org_id=org_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/risk/group", response_model=GroupRiskScoreResponse, dependencies=[Depends(require_role(["admin", "analyst"]))])
@limiter.limit("10/minute")
async def analyze_group_risk(request: Request, payload: GroupAssetRequest, db: AsyncSession = Depends(get_db), org_id: str = Depends(get_current_org)):
    """
    Capability 2: Risk scoring & summarization for a specific asset.
    """
    try:
        assets_data = []
        for asset_id in payload.asset_ids:
            context = await get_asset_by_id_with_context(db, asset_id, org_id)
            if context:
                assets_data.append(context)
                
        if not assets_data:
            raise HTTPException(status_code=404, detail="No assets found")
            
        return await run_group_risk_scoring_chain(assets_data)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/enrich", response_model=EnrichmentResponse, dependencies=[Depends(require_role(["admin", "analyst"]))])
@limiter.limit("10/minute")
async def analyze_enrich(request: Request, payload: AssetRequest, db: AsyncSession = Depends(get_db), org_id: str = Depends(get_current_org)):
    """
    Capability 3: Automated enrichment & categorization.
    """
    try:
        return await run_enrichment_chain(db, payload.asset_id, org_id=org_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ReportRequest(BaseModel):
    types: Optional[List[str]] = None
    statuses: Optional[List[str]] = None
    tags: Optional[List[str]] = None

@router.post("/report", dependencies=[Depends(require_role(["admin", "analyst"]))])
@limiter.limit("5/minute")
async def analyze_report(
    request: Request,
    payload: Optional[ReportRequest] = None,
    db: AsyncSession = Depends(get_db),
    org_id: str = Depends(get_current_org)
):
    """
    Capability 4: Natural-language report generation.
    Returns a comprehensive markdown report over the dataset.
    """
    try:
        markdown_report = await run_report_chain(
            db, 
            org_id=org_id,
            types=payload.types if payload else None,
            statuses=payload.statuses if payload else None,
            tags=payload.tags if payload else None
        )
        return {"report": markdown_report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/agent", dependencies=[Depends(require_role(["admin", "analyst"]))])
@limiter.limit("10/minute")
async def analyze_agent(request: Request, payload: QueryRequest, db: AsyncSession = Depends(get_db), org_id: str = Depends(get_current_org)):
    """
    Agentic analysis: the LLM dynamically chooses which tools to call.
    """
    try:
        result = await run_agent(payload.question, org_id=org_id)
        return {"response": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
