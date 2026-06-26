from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class QueryFilter(BaseModel):
    """
    The structured output expected from the LLM when translating a Natural Language Query.
    """
    types: Optional[List[str]] = Field(default=None, description="Asset types to filter by (e.g. 'domain', 'certificate')")
    statuses: Optional[List[str]] = Field(default=None, description="Asset statuses to filter by (e.g. 'active', 'stale')")
    tags: Optional[List[str]] = Field(default=None, description="Tags to filter by")
    value_contains: Optional[str] = Field(default=None, description="Substring match for the asset value")

class RiskScoreResponse(BaseModel):
    """
    Structured output for risk scoring an asset.
    """
    risk_score: int = Field(..., ge=1, le=10, description="Risk score from 1 to 10")
    summary: str = Field(..., description="Concise summary explaining the risk score")
    findings: List[str] = Field(..., description="Specific risk findings (e.g. 'Expired certificate')")

class EnrichmentResponse(BaseModel):
    """
    Structured output for categorizing and enriching an asset.
    """
    environment: str = Field(..., description="One of: prod, staging, dev, unknown")
    criticality: str = Field(..., description="One of: critical, high, medium, low")
    category: str = Field(..., description="One of: infrastructure, application, security, data")
    suggested_metadata: Dict[str, Any] = Field(..., description="Suggested key-value pairs to add to metadata")
    suggested_tags: List[str] = Field(..., description="Suggested tags to add to the asset")

class NLQueryResponse(BaseModel):
    """
    Final API response for the natural language query endpoint.
    """
    query_interpreted: QueryFilter
    assets_found: int
    assets: List[Dict[str, Any]]
