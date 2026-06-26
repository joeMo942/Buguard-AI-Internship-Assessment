from langchain_core.tools import tool
from app.ai.grounding import execute_asset_filter, get_asset_by_id_with_context, get_all_assets_summary, format_single_asset
import json

def create_tools(db, org_id="default"):
    @tool
    async def search_assets(types: str = "", statuses: str = "", tags: str = "", value_contains: str = "") -> str:
        """Search for assets by type, status, tags, or value substring.
        types: comma-separated, e.g. 'domain,certificate'
        statuses: comma-separated, e.g. 'active,stale'
        tags: comma-separated, e.g. 'prod,root'
        value_contains: substring to search for in asset values
        """
        assets = await execute_asset_filter(
            db=db,
            org_id=org_id,
            types=types.split(",") if types else None,
            statuses=statuses.split(",") if statuses else None,
            tags=tags.split(",") if tags else None,
            value_contains=value_contains or None
        )
        return json.dumps([format_single_asset(a) for a in assets], indent=2)

    @tool
    async def get_asset_details(asset_id: str) -> str:
        """Get full details and relationships for a specific asset by its ID."""
        context = await get_asset_by_id_with_context(db, asset_id, org_id=org_id)
        if not context:
            return f"No asset found with ID: {asset_id}"
        return json.dumps(context, indent=2)

    @tool
    async def get_inventory_summary() -> str:
        """Get a summary of all assets in the database."""
        return await get_all_assets_summary(db, org_id=org_id)

    return [search_assets, get_asset_details, get_inventory_summary]
