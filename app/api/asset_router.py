from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict, Any

from app.database import get_db
from app.dependencies import get_current_org, require_role
from app.ai.grounding import execute_asset_filter, get_asset_by_id_with_context, format_single_asset

router = APIRouter(prefix="/assets", tags=["assets"])

@router.get("/")
async def list_assets(
    type: Optional[str] = Query(None, description="Filter by asset type"),
    status: Optional[str] = Query(None, description="Filter by asset status"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    value_contains: Optional[str] = Query(None, description="Filter by substring in value"),
    sort_by: str = Query("first_seen", description="Sort by field"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    org_id: str = Depends(get_current_org)
):
    """List assets with filtering, sorting, and pagination."""
    result = await execute_asset_filter(
        db, 
        org_id=org_id,
        types=[type] if type else None,
        statuses=[status] if status else None,
        tags=[tag] if tag else None,
        value_contains=value_contains,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page, 
        page_size=page_size
    )
    # format assets using format_single_asset logic to serialize nicely
    return {
        "assets": [format_single_asset(a) for a in result["assets"]],
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"]
    }

@router.get("/{asset_id}")
async def get_asset(
    asset_id: str, 
    db: AsyncSession = Depends(get_db),
    org_id: str = Depends(get_current_org)
):
    """Get a specific asset with its relationships."""
    context = await get_asset_by_id_with_context(db, asset_id, org_id=org_id)
    if not context:
        raise HTTPException(status_code=404, detail="Asset not found")
    return context

@router.patch("/{asset_id}/status", dependencies=[Depends(require_role(["admin", "analyst"]))])
async def update_asset_status(
    asset_id: str,
    status: str = Query(..., pattern="^(active|stale|archived)$"),
    db: AsyncSession = Depends(get_db),
    org_id: str = Depends(get_current_org)
):
    """Update an asset's lifecycle status."""
    from sqlalchemy.future import select
    from app.models.asset import Asset
    from datetime import datetime, timezone

    stmt = select(Asset).where(Asset.id == asset_id, Asset.org_id == org_id)
    result = await db.execute(stmt)
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    asset.status = status
    if status == "active":
        asset.last_seen = datetime.now(timezone.utc)
    
    await db.commit()
    return {"id": asset_id, "status": status}

@router.delete("/{asset_id}", dependencies=[Depends(require_role(["admin"]))])
async def delete_asset(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    org_id: str = Depends(get_current_org)
):
    """Delete an asset."""
    from sqlalchemy.future import select
    from app.models.asset import Asset
    
    stmt = select(Asset).where(Asset.id == asset_id, Asset.org_id == org_id)
    result = await db.execute(stmt)
    asset = result.scalar_one_or_none()
    
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
        
    await db.delete(asset)
    await db.commit()
    return {"message": "Asset deleted successfully", "id": asset_id}
