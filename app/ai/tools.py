from langchain_core.tools import tool
import httpx
import json

BASE_URL = "http://localhost:8000"

def create_tools(org_id="default"):
    """
    Creates tools that call our OWN REST API endpoints.
    This satisfies the Track B bonus: 'agent that calls your own API as tools'.
    """
    headers = {"X-Org-Id": org_id, "X-API-Key": "dev-key-123"}

    @tool
    async def search_assets(
        types: str = "", 
        statuses: str = "", 
        tags: str = "", 
        value_contains: str = ""
    ) -> str:
        """Search for assets by type, status, tags, or value substring.
        types: comma-separated, e.g. 'domain,certificate'
        statuses: comma-separated, e.g. 'active,stale'
        tags: comma-separated, e.g. 'prod,root'
        value_contains: substring to search for in asset values
        """
        params = {}
        if types:
            params["type"] = types.split(",")[0]  # API takes single values
        if statuses:
            params["status"] = statuses.split(",")[0]
        if tags:
            params["tag"] = tags.split(",")[0]
        if value_contains:
            params["value_contains"] = value_contains
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{BASE_URL}/assets/", 
                params=params, 
                headers=headers,
                timeout=30
            )
            return resp.text

    @tool
    async def get_asset_details(asset_id: str) -> str:
        """Get full details and relationships for a specific asset by its ID."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{BASE_URL}/assets/{asset_id}", 
                headers=headers,
                timeout=30
            )
            if resp.status_code == 404:
                return f"No asset found with ID: {asset_id}"
            return resp.text

    @tool
    async def score_asset_risk(asset_id: str) -> str:
        """Score the risk of a specific asset. Returns risk_score, summary, findings."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BASE_URL}/analyze/risk",
                json={"asset_id": asset_id},
                headers=headers,
                timeout=60
            )
            return resp.text

    @tool
    async def enrich_asset(asset_id: str) -> str:
        """Enrich and categorize an asset. Returns environment, criticality, category."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BASE_URL}/analyze/enrich",
                json={"asset_id": asset_id},
                headers=headers,
                timeout=60
            )
            return resp.text

    return [search_assets, get_asset_details, score_asset_risk, enrich_asset]
