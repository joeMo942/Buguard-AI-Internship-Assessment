import pytest
from unittest.mock import patch, AsyncMock
from app.schemas.analysis import RiskScoreResponse, QueryFilter, EnrichmentResponse

@pytest.mark.asyncio
@patch("app.api.analysis_router.run_nl_query_chain")
async def test_analyze_query(mock_chain, client):
    # Mock the LLM chain response
    mock_chain.return_value = {
        "query_interpreted": QueryFilter(types=["domain"]).model_dump(),
        "assets_found": 1,
        "assets": [{"id": "1", "type": "domain", "value": "test.com"}]
    }
    
    response = client.post("/analyze/query", json={"question": "show domains"})
    assert response.status_code == 200
    data = response.json()
    assert data["assets_found"] == 1
    assert data["query_interpreted"]["types"] == ["domain"]

@pytest.mark.asyncio
@patch("app.api.analysis_router.run_risk_scoring_chain")
async def test_analyze_risk(mock_chain, client):
    mock_chain.return_value = RiskScoreResponse(
        risk_score=5,
        summary="Test risk",
        findings=["Test finding"]
    )
    
    response = client.post("/analyze/risk", json={"asset_id": "a1"})
    assert response.status_code == 200
    data = response.json()
    assert data["risk_score"] == 5

@pytest.mark.asyncio
@patch("app.api.analysis_router.run_enrichment_chain")
async def test_analyze_enrich(mock_chain, client):
    mock_chain.return_value = EnrichmentResponse(
        environment="prod",
        criticality="high",
        category="application",
        suggested_metadata={"test": "val"},
        suggested_tags=["new_tag"]
    )
    
    response = client.post("/analyze/enrich", json={"asset_id": "a1"})
    assert response.status_code == 200
    data = response.json()
    assert data["environment"] == "prod"

@pytest.mark.asyncio
@patch("app.api.analysis_router.run_report_chain")
async def test_analyze_report(mock_chain, client):
    mock_chain.return_value = "# Mock Report"
    
    response = client.post("/analyze/report")
    assert response.status_code == 200
    data = response.json()
    assert data["report"] == "# Mock Report"
