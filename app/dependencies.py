from fastapi import Header, HTTPException

async def get_current_org(x_org_id: str = Header(default="default")) -> str:
    """
    Extract org_id from a request header. 
    In production, this would validate against an auth token.
    """
    if not x_org_id:
        raise HTTPException(status_code=400, detail="X-Org-Id header required")
    return x_org_id
