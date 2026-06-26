from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.ai.chains import run_nl_query_chain, run_risk_scoring_chain, run_enrichment_chain, run_report_chain
from app.ai.agent import run_agent
from app.dependencies import get_current_org
from app.schemas.analysis import RiskScoreResponse, EnrichmentResponse, NLQueryResponse

router = APIRouter(prefix="/analyze", tags=["analysis"])

class QueryRequest(BaseModel):
    question: str

class AssetRequest(BaseModel):
    asset_id: str

@router.post("/query", response_model=NLQueryResponse)
async def analyze_query(request: QueryRequest, db: AsyncSession = Depends(get_db), org_id: str = Depends(get_current_org)):
    """
    Capability 1: Natural-language asset query.
    Translates a plain-English question into a structured query and returns matching assets.
    """
    try:
        return await run_nl_query_chain(db, request.question, org_id=org_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/risk", response_model=RiskScoreResponse)
async def analyze_risk(request: AssetRequest, db: AsyncSession = Depends(get_db), org_id: str = Depends(get_current_org)):
    """
    Capability 2: Risk scoring & summarization for a specific asset.
    """
    try:
        return await run_risk_scoring_chain(db, request.asset_id, org_id=org_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/enrich", response_model=EnrichmentResponse)
async def analyze_enrich(request: AssetRequest, db: AsyncSession = Depends(get_db), org_id: str = Depends(get_current_org)):
    """
    Capability 3: Automated enrichment & categorization.
    """
    try:
        return await run_enrichment_chain(db, request.asset_id, org_id=org_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/report")
async def analyze_report(db: AsyncSession = Depends(get_db), org_id: str = Depends(get_current_org)):
    """
    Capability 4: Natural-language report generation.
    Returns a comprehensive markdown report over the dataset.
    """
    try:
        markdown_report = await run_report_chain(db, org_id=org_id)
        return {"report": markdown_report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/agent")
async def analyze_agent(request: QueryRequest, db: AsyncSession = Depends(get_db), org_id: str = Depends(get_current_org)):
    """
    Agentic analysis: the LLM dynamically chooses which tools to call.
    """
    try:
        result = await run_agent(db, request.question, org_id=org_id)
        return {"response": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
