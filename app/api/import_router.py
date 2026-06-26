from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
import json

from app.database import get_db
from app.dependencies import get_current_org, require_role
from app.schemas.asset import AssetImportItem, ImportResponse
from app.services.import_service import process_import

router = APIRouter(prefix="/import", tags=["import"])

@router.post("/", response_model=ImportResponse, dependencies=[Depends(require_role(["admin"]))])
async def import_assets(items: List[Dict[str, Any]], db: AsyncSession = Depends(get_db), org_id: str = Depends(get_current_org)):
    """Bulk import assets with deduplication."""
    return await process_import(db, items, org_id=org_id)

@router.post("/file", response_model=ImportResponse, dependencies=[Depends(require_role(["admin"]))])
async def import_assets_file(file: UploadFile = File(...), db: AsyncSession = Depends(get_db), org_id: str = Depends(get_current_org)):
    """Upload a JSON file containing assets for bulk import."""
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only JSON files are allowed")
    
    try:
        content = await file.read()
        data = json.loads(content)
        if not isinstance(data, list):
            raise HTTPException(status_code=400, detail="JSON must contain a list of assets")
        
        # Pass raw dictionaries to process_import for batch resilience
        return await process_import(db, data, org_id=org_id)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
