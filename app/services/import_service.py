from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Dict, Any
import logging
from datetime import datetime, timezone
import uuid

from app.schemas.asset import AssetImportItem, ImportResponse
from app.models.asset import Asset
from app.models.relationship import AssetRelationship
from datetime import timedelta

logger = logging.getLogger(__name__)

def check_certificate_lifecycle(asset: Asset):
    """Deterministically flag expired or expiring-soon certificates."""
    if asset.type != 'certificate':
        return
    meta = asset.metadata_ or {}
    expires_str = meta.get("expires") or meta.get("expiry") or meta.get("not_after")
    if not expires_str:
        return
    try:
        expires_dt = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return
    
    now = datetime.now(timezone.utc)
    if expires_dt < now:
        asset.status = "stale"
        asset.tags = list(set((asset.tags or []) + ["expired-cert"]))
    elif expires_dt < now + timedelta(days=30):
        asset.tags = list(set((asset.tags or []) + ["expiring-soon"]))

from pydantic import ValidationError

async def process_import(db: AsyncSession, raw_items: List[Dict[str, Any]], org_id: str = "default") -> ImportResponse:
    response = ImportResponse()
    relationships_to_create = []

    for index, raw in enumerate(raw_items):
        try:
            item = AssetImportItem(**raw)
        except ValidationError as ve:
            # We must serialize the Pydantic error list to a basic dict so it doesn't cause issues
            error_details = ve.errors()
            for err in error_details:
                if 'ctx' in err and 'error' in err['ctx'] and isinstance(err['ctx']['error'], Exception):
                    err['ctx']['error'] = str(err['ctx']['error'])
            response.skipped += 1
            response.errors.append({"index": index, "error": error_details})
            continue

        try:
            if not item.type or not item.value:
                response.skipped += 1
                response.errors.append({"index": index, "error": "Missing type or value"})
                continue
            
            # Check for existing asset by ID to handle collisions
            existing_by_id = await db.get(Asset, item.id)
            if existing_by_id and (existing_by_id.type != item.type or existing_by_id.value != item.value):
                # ID collision with a different asset — generate new ID
                item.id = str(uuid.uuid4())

            # Check for existing asset by (type, value) unique constraint, scoped by org_id
            stmt = select(Asset).where(
                Asset.org_id == org_id,
                Asset.type == item.type, 
                Asset.value == item.value
            )
            result = await db.execute(stmt)
            existing_asset = result.scalar_one_or_none()

            # Ensure tags are a list
            new_tags = item.tags if isinstance(item.tags, list) else []
            new_metadata = item.metadata if isinstance(item.metadata, dict) else {}

            if existing_asset:
                # Deduplication logic: Merge tags and metadata, update last_seen/status
                merged_tags = list(set(existing_asset.tags + new_tags))
                merged_metadata = {**existing_asset.metadata_, **new_metadata}
                
                # Track source provenance
                if item.source and item.source != existing_asset.source:
                    sources = existing_asset.metadata_.get("_sources", [existing_asset.source])
                    if item.source not in sources:
                        sources.append(item.source)
                    merged_metadata["_sources"] = sources
                
                existing_asset.tags = merged_tags
                existing_asset.metadata_ = merged_metadata
                existing_asset.last_seen = datetime.now(timezone.utc)  # Explicitly trigger update
                
                if existing_asset.status == 'stale':
                    existing_asset.status = 'active'
                
                # last_seen will be updated automatically by onupdate in the model
                response.updated += 1
                db_asset = existing_asset
            else:
                # Create new asset
                db_asset = Asset(
                    id=item.id,
                    org_id=org_id,
                    type=item.type,
                    value=item.value,
                    status=item.status,
                    source=item.source,
                    tags=new_tags,
                    metadata_=new_metadata
                )
                db.add(db_asset)
                response.created += 1

            check_certificate_lifecycle(db_asset)

            # Extract implicit relationships
            if item.parent:
                relationships_to_create.append((db_asset.id, item.parent, "parent"))
            if item.covers:
                relationships_to_create.append((db_asset.id, item.covers, "covers"))
            if item.resolves_to:
                relationships_to_create.append((db_asset.id, item.resolves_to, "resolves_to"))
            if item.runs_on:
                relationships_to_create.append((db_asset.id, item.runs_on, "runs_on"))
            
            # Allow custom relationships from extra fields or metadata if any, but we'll stick to MVP
        except Exception as e:
            logger.error(f"Error importing item {index}: {e}")
            response.errors.append({"index": index, "error": str(e)})
            response.skipped += 1

    # Commit assets first so they have IDs for relationships
    await db.commit()

    # Validate that relationship targets actually exist in the DB
    imported_ids = {raw.get("id") for raw in raw_items if raw.get("id")}
    existing_ids_stmt = select(Asset.id)
    existing_result = await db.execute(existing_ids_stmt)
    all_known_ids = {row[0] for row in existing_result.fetchall()} | imported_ids

    # Now create relationships if they don't exist and target is valid
    for source_id, target_id, rel_type in relationships_to_create:
        if target_id not in all_known_ids:
            continue
        try:
            stmt = select(AssetRelationship).where(
                AssetRelationship.org_id == org_id,
                AssetRelationship.source_asset_id == source_id,
                AssetRelationship.target_asset_id == target_id,
                AssetRelationship.relationship_type == rel_type
            )
            result = await db.execute(stmt)
            existing_rel = result.scalar_one_or_none()

            if not existing_rel:
                new_rel = AssetRelationship(
                    org_id=org_id,
                    source_asset_id=source_id,
                    target_asset_id=target_id,
                    relationship_type=rel_type
                )
                db.add(new_rel)
        except Exception as e:
            logger.error(f"Error creating relationship: {e}")

    await db.commit()
    return response
