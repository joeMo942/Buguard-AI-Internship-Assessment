from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import func
from app.models.asset import Asset
from app.models.relationship import AssetRelationship
import json

async def get_all_assets_summary(db: AsyncSession, org_id: str = "default", limit: int = 200) -> str:
    """
    Retrieves all assets and formats them compactly to be injected into prompts.
    This ensures the LLM ONLY knows about actual data.
    """
    stmt = select(Asset).where(Asset.org_id == org_id).order_by(Asset.first_seen).limit(limit)
    result = await db.execute(stmt)
    assets = result.scalars().all()
    
    return format_assets_for_prompt(assets)

async def get_asset_statistics(db: AsyncSession, org_id: str = "default") -> dict:
    """Compute aggregate stats for large datasets."""
    total = await db.scalar(select(func.count(Asset.id)).where(Asset.org_id == org_id))
    by_type = await db.execute(
        select(Asset.type, func.count(Asset.id)).where(Asset.org_id == org_id).group_by(Asset.type)
    )
    by_status = await db.execute(
        select(Asset.status, func.count(Asset.id)).where(Asset.org_id == org_id).group_by(Asset.status)
    )
    return {
        "total_assets": total,
        "by_type": dict(by_type.fetchall()),
        "by_status": dict(by_status.fetchall()),
    }

async def get_asset_by_id_with_context(db: AsyncSession, asset_id: str, org_id: str = "default") -> Optional[dict]:
    """
    Fetches a specific asset and its immediate relationships for targeted context
    (e.g., for risk scoring or enrichment).
    """
    stmt = select(Asset).where(Asset.id == asset_id, Asset.org_id == org_id)
    result = await db.execute(stmt)
    asset = result.scalar_one_or_none()
    
    if not asset:
        return None
        
    # Get relationships where this asset is source
    rel_stmt_out = select(AssetRelationship).where(AssetRelationship.source_asset_id == asset.id)
    rel_result_out = await db.execute(rel_stmt_out)
    out_rels = rel_result_out.scalars().all()
    
    # Get relationships where this asset is target
    rel_stmt_in = select(AssetRelationship).where(AssetRelationship.target_asset_id == asset.id)
    rel_result_in = await db.execute(rel_stmt_in)
    in_rels = rel_result_in.scalars().all()

    return {
        "asset": format_single_asset(asset),
        "relationships_out": [{"type": r.relationship_type, "target_id": r.target_asset_id} for r in out_rels],
        "relationships_in": [{"type": r.relationship_type, "source_id": r.source_asset_id} for r in in_rels]
    }

async def execute_asset_filter(
    db: AsyncSession, 
    org_id: str = "default",
    types: List[str] = None, 
    statuses: List[str] = None, 
    tags: List[str] = None, 
    value_contains: str = None
) -> List[Asset]:
    """
    Executes a structured filter against the DB.
    This is called by our backend after the LLM translates the user's NL query into a JSON filter.
    """
    stmt = select(Asset).where(Asset.org_id == org_id)
    
    if types:
        stmt = stmt.where(Asset.type.in_(types))
    if statuses:
        stmt = stmt.where(Asset.status.in_(statuses))
    if tags:
        # PostgreSQL/SQLite JSON containment check is complex, but for MVP we can filter in memory or use basic JSON operators.
        # Since we use JSON across DBs, a naive python-side filter or specific dialect filter is needed.
        # For MVP simplicity, we will fetch and filter in Python if tags are present, 
        # or use a generic approach if strictly SQL. We'll do a basic python-side filter for tags.
        pass 
    if value_contains:
        stmt = stmt.where(Asset.value.ilike(f"%{value_contains}%"))
        
    result = await db.execute(stmt)
    assets = result.scalars().all()
    
    if tags:
        assets = [a for a in assets if any(t in a.tags for t in tags)]
        
    return assets

def format_single_asset(asset: Asset) -> dict:
    return {
        "id": asset.id,
        "type": asset.type,
        "value": asset.value,
        "status": asset.status,
        "tags": asset.tags,
        "metadata": asset.metadata_
    }

def format_assets_for_prompt(assets: List[Asset]) -> str:
    """
    Converts a list of assets into a compact JSON string for prompt injection.
    """
    formatted = [format_single_asset(a) for a in assets]
    return json.dumps(formatted, indent=2)
