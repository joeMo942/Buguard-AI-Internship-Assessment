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
    rel_stmt_out = select(AssetRelationship).where(
        AssetRelationship.source_asset_id == asset.id,
        AssetRelationship.org_id == org_id
    )
    rel_result_out = await db.execute(rel_stmt_out)
    out_rels = rel_result_out.scalars().all()
    
    # Get relationships where this asset is target
    rel_stmt_in = select(AssetRelationship).where(
        AssetRelationship.target_asset_id == asset.id,
        AssetRelationship.org_id == org_id
    )
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
    value_contains: str = None,
    sort_by: str = "first_seen",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 50
) -> dict:
    """
    Executes a structured filter against the DB.
    This is called by our backend after the LLM translates the user's NL query into a JSON filter.
    """
    from sqlalchemy import cast, String
    stmt = select(Asset).where(Asset.org_id == org_id)
    
    if types:
        stmt = stmt.where(Asset.type.in_(types))
    if statuses:
        stmt = stmt.where(Asset.status.in_(statuses))
    if tags:
        # Cross-db naive JSON array check
        for tag in tags:
            stmt = stmt.where(cast(Asset.tags, String).ilike(f'%"{tag}"%'))
    if value_contains:
        stmt = stmt.where(Asset.value.ilike(f"%{value_contains}%"))
        
    # Sorting
    sort_column = getattr(Asset, sort_by, Asset.first_seen)
    if sort_order == "asc":
        stmt = stmt.order_by(sort_column.asc())
    else:
        stmt = stmt.order_by(sort_column.desc())
        
    # Count total before pagination
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(count_stmt)

    # Apply pagination
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    assets = result.scalars().all()
        
    return {
        "assets": assets,
        "total": total,
        "page": page,
        "page_size": page_size
    }

def format_single_asset(asset: Asset) -> dict:
    return {
        "id": asset.id,
        "type": asset.type,
        "value": asset.value,
        "status": asset.status,
        "first_seen": asset.first_seen.isoformat() if asset.first_seen else None,
        "last_seen": asset.last_seen.isoformat() if asset.last_seen else None,
        "source": asset.source,
        "tags": asset.tags,
        "metadata": asset.metadata_
    }

def format_assets_for_prompt(assets: List[Asset]) -> str:
    """
    Converts a list of assets into a compact JSON string for prompt injection.
    """
    formatted = [format_single_asset(a) for a in assets]
    return json.dumps(formatted, indent=2)
