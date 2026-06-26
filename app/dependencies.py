from fastapi import Header, HTTPException, Security
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import settings

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
limiter = Limiter(key_func=get_remote_address)

# Simple RBAC: key -> role mapping
API_KEY_ROLES = {
    "admin-key-123": "admin",    # Full access
    "analyst-key-456": "analyst", # Read + analyze, no import/delete
    "viewer-key-789": "viewer",   # Read only
}

async def get_current_org(x_org_id: str = Header(default="default")) -> str:
    """
    Extract org_id from a request header. 
    In production, this would validate against an auth token.
    """
    if not x_org_id:
        raise HTTPException(status_code=400, detail="X-Org-Id header required")
    return x_org_id

async def require_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """Validate API key for write operations."""
    valid_keys = settings.API_KEYS.split(",") if settings.API_KEYS else []
    all_valid = valid_keys + list(API_KEY_ROLES.keys())
    if not api_key or api_key not in all_valid:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key

def require_role(allowed_roles: list[str]):
    """Dependency factory: require the caller to have one of the allowed roles."""
    async def checker(api_key: str = Security(API_KEY_HEADER)) -> str:
        if not api_key:
            raise HTTPException(status_code=401, detail="API key required")
        role = API_KEY_ROLES.get(api_key, "admin")  # Legacy keys default to admin
        valid_keys = settings.API_KEYS.split(",") if settings.API_KEYS else []
        if api_key not in valid_keys and api_key not in API_KEY_ROLES:
            raise HTTPException(status_code=401, detail="Invalid API key")
        if role not in allowed_roles:
            raise HTTPException(status_code=403, detail=f"Role '{role}' not authorized. Required: {allowed_roles}")
        return api_key
    return checker
