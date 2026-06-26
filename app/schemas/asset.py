from pydantic import BaseModel, ConfigDict, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum as PyEnum

class AssetType(str, PyEnum):
    domain = "domain"
    subdomain = "subdomain"
    ip_address = "ip_address"
    service = "service"
    certificate = "certificate"
    technology = "technology"

class AssetStatus(str, PyEnum):
    active = "active"
    stale = "stale"
    archived = "archived"

class AssetImportItem(BaseModel):
    id: str
    type: AssetType
    value: str
    status: Optional[AssetStatus] = AssetStatus.active
    source: Optional[str] = "import"
    tags: Optional[List[str]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata")
    parent: Optional[str] = None
    covers: Optional[str] = None
    resolves_to: Optional[str] = None
    runs_on: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True, extra="allow", use_enum_values=True)

class ImportResponse(BaseModel):
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: List[Dict[str, Any]] = Field(default_factory=list)

class AssetResponse(BaseModel):
    id: str
    type: str
    value: str
    status: str
    first_seen: datetime
    last_seen: datetime
    source: str
    tags: List[str]
    metadata_: Dict[str, Any] = Field(alias="metadata")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
