import pytest
from app.models.asset import Asset
from app.models.relationship import AssetRelationship
from sqlalchemy.future import select
from datetime import datetime, timezone, timedelta

# 1. Test List Assets (Pagination & Defaults)
@pytest.mark.asyncio
async def test_list_assets_pagination(client):
    # Import 100 assets
    payload = [
        {
            "id": f"asset-{i}",
            "type": "domain",
            "value": f"example{i}.com",
            "status": "active",
            "source": "scan"
        }
        for i in range(100)
    ]
    response = client.post("/import/", json=payload, headers={"X-API-Key": "admin-key-123"})
    assert response.status_code == 200
    
    # Test sane default pagination
    res1 = client.get("/assets/", headers={"X-API-Key": "admin-key-123"})
    assert res1.status_code == 200
    data1 = res1.json()
    assert len(data1["assets"]) == 50  # Default page size
    assert data1["page"] == 1
    assert data1["total"] == 100
    
    # Test page 2
    res2 = client.get("/assets/?page=2", headers={"X-API-Key": "admin-key-123"})
    data2 = res2.json()
    assert len(data2["assets"]) == 50
    assert data2["page"] == 2
    
    # Test large inventory doesn't return all at once
    res3 = client.get("/assets/?page_size=200", headers={"X-API-Key": "admin-key-123"})
    data3 = res3.json()
    assert len(data3["assets"]) == 100

# 2. Test List Assets (Filtering & Sorting)
@pytest.mark.asyncio
async def test_list_assets_filtering(client):
    payload = [
        {"id": "f1", "type": "domain", "value": "findme.com", "status": "active", "source": "scan", "tags": ["special"]},
        {"id": "f2", "type": "subdomain", "value": "sub.findme.com", "status": "active", "source": "scan", "tags": ["normal"]},
        {"id": "f3", "type": "domain", "value": "other.com", "status": "stale", "source": "scan", "tags": ["special"]}
    ]
    client.post("/import/", json=payload, headers={"X-API-Key": "admin-key-123"})
    
    # Filter by type
    res = client.get("/assets/?type=subdomain", headers={"X-API-Key": "admin-key-123"})
    assert len(res.json()["assets"]) == 1
    assert res.json()["assets"][0]["id"] == "f2"
    
    # Filter by tag and status
    res2 = client.get("/assets/?tag=special&status=active", headers={"X-API-Key": "admin-key-123"})
    assert len(res2.json()["assets"]) == 1
    assert res2.json()["assets"][0]["id"] == "f1"
    
    # Filter by value contains
    res3 = client.get("/assets/?value_contains=findme", headers={"X-API-Key": "admin-key-123"})
    assert len(res3.json()["assets"]) == 2

# 3. Test Get Asset with Relationships
@pytest.mark.asyncio
async def test_get_asset_relationships(client):
    payload = [
        {"id": "r1", "type": "domain", "value": "parent.com", "status": "active", "source": "scan"},
        {"id": "r2", "type": "subdomain", "value": "sub.parent.com", "status": "active", "source": "scan", "parent": "r1"}
    ]
    client.post("/import/", json=payload, headers={"X-API-Key": "admin-key-123"})
    
    res = client.get("/assets/r2", headers={"X-API-Key": "admin-key-123"})
    assert res.status_code == 200
    data = res.json()
    assert data["asset"]["id"] == "r2"
    assert "relationships_out" in data
    assert any(rel["target_id"] == "r1" for rel in data["relationships_out"])

# 4. Test Update Asset Status
@pytest.mark.asyncio
async def test_update_asset_status(client):
    payload = [{"id": "u1", "type": "domain", "value": "updateme.com", "status": "active", "source": "scan"}]
    client.post("/import/", json=payload, headers={"X-API-Key": "admin-key-123"})
    
    res = client.patch("/assets/u1/status?status=stale", headers={"X-API-Key": "admin-key-123"})
    assert res.status_code == 200
    
    res_get = client.get("/assets/u1", headers={"X-API-Key": "admin-key-123"})
    assert res_get.json()["asset"]["status"] == "stale"

# 5. Test Delete Asset
@pytest.mark.asyncio
async def test_delete_asset(client):
    payload = [{"id": "d1", "type": "domain", "value": "deleteme.com", "status": "active", "source": "scan"}]
    client.post("/import/", json=payload, headers={"X-API-Key": "admin-key-123"})
    
    res_delete = client.delete("/assets/d1", headers={"X-API-Key": "admin-key-123"})
    assert res_delete.status_code == 200
    
    res_get = client.get("/assets/d1", headers={"X-API-Key": "admin-key-123"})
    assert res_get.status_code == 404

# 6. Test Re-appearing Assets (Stale to Active)
@pytest.mark.asyncio
async def test_reappearing_assets(client):
    # Import as stale
    payload1 = [{"id": "re1", "type": "domain", "value": "reappear.com", "status": "stale", "source": "scan"}]
    client.post("/import/", json=payload1, headers={"X-API-Key": "admin-key-123"})
    
    # Ensure it's stale
    res = client.get("/assets/re1", headers={"X-API-Key": "admin-key-123"})
    assert res.json()["asset"]["status"] == "stale"
    
    # Import again, should become active and last_seen updated
    payload2 = [{"id": "re1", "type": "domain", "value": "reappear.com", "status": "active", "source": "scan"}]
    client.post("/import/", json=payload2, headers={"X-API-Key": "admin-key-123"})
    
    res2 = client.get("/assets/re1", headers={"X-API-Key": "admin-key-123"})
    assert res2.json()["asset"]["status"] == "active"

# 7. Test Conflicting Data (Merge Strategy)
@pytest.mark.asyncio
async def test_conflicting_data_merge(client):
    # First source
    payload1 = [{
        "id": "c1", "type": "ip_address", "value": "1.1.1.1", "status": "active", 
        "source": "nmap", "tags": ["public"], "metadata": {"os": "linux"}
    }]
    client.post("/import/", json=payload1, headers={"X-API-Key": "admin-key-123"})
    
    # Second source, same asset, different metadata and tags
    payload2 = [{
        "id": "c1", "type": "ip_address", "value": "1.1.1.1", "status": "active", 
        "source": "shodan", "tags": ["scanned"], "metadata": {"ports": [80, 443]}
    }]
    client.post("/import/", json=payload2, headers={"X-API-Key": "admin-key-123"})
    
    res = client.get("/assets/c1", headers={"X-API-Key": "admin-key-123"})
    data = res.json()["asset"]
    
    # Check merge strategy
    assert "public" in data["tags"]
    assert "scanned" in data["tags"]
    assert data["metadata"]["os"] == "linux"
    assert data["metadata"]["ports"] == [80, 443]
    assert "nmap" in data["metadata"]["_sources"]
    assert "shodan" in data["metadata"]["_sources"]

# 8. Test Malformed/Partial Records in Import (Batch Resilience)
@pytest.mark.asyncio
async def test_malformed_records_import(client):
    payload = [
        {"id": "m1", "type": "domain", "value": "good.com", "status": "active", "source": "scan"},
        {"id": "m2", "type": "domain"}, # Malformed: missing value
        {"id": "m3", "type": "domain", "value": "good2.com", "status": "active", "source": "scan"}
    ]
    res = client.post("/import/", json=payload, headers={"X-API-Key": "admin-key-123"})
    assert res.status_code == 200
    
    data = res.json()
    assert data["created"] == 2
    assert data["skipped"] == 1
    assert len(data["errors"]) == 1
    
    # Check that good records were created
    res1 = client.get("/assets/m1", headers={"X-API-Key": "admin-key-123"})
    assert res1.status_code == 200
    res3 = client.get("/assets/m3", headers={"X-API-Key": "admin-key-123"})
    assert res3.status_code == 200

# 9. Test Certificate Lifecycle Dates (Expired vs Expiring Soon)
@pytest.mark.asyncio
async def test_certificate_lifecycle(client):
    now = datetime.now(timezone.utc)
    expired_date = (now - timedelta(days=5)).isoformat()
    expiring_soon_date = (now + timedelta(days=15)).isoformat()
    
    payload = [
        {
            "id": "cert1", "type": "certificate", "value": "expired.com", 
            "status": "active", "source": "scan", "metadata": {"expires": expired_date}
        },
        {
            "id": "cert2", "type": "certificate", "value": "soon.com", 
            "status": "active", "source": "scan", "metadata": {"expires": expiring_soon_date}
        }
    ]
    client.post("/import/", json=payload, headers={"X-API-Key": "admin-key-123"})
    
    # Expired should be marked stale and have expired-cert tag
    res1 = client.get("/assets/cert1", headers={"X-API-Key": "admin-key-123"})
    assert res1.json()["asset"]["status"] == "stale"
    assert "expired-cert" in res1.json()["asset"]["tags"]
    
    # Expiring soon should still be active but have expiring-soon tag
    res2 = client.get("/assets/cert2", headers={"X-API-Key": "admin-key-123"})
    assert res2.json()["asset"]["status"] == "active"
    assert "expiring-soon" in res2.json()["asset"]["tags"]

# 10. Test Multi-tenant Isolation
@pytest.mark.asyncio
async def test_multi_tenant_isolation(client):
    # Import for org1
    payload1 = [{"id": "mt1", "type": "domain", "value": "org1.com", "status": "active", "source": "scan"}]
    res1 = client.post("/import/", json=payload1, headers={"X-API-Key": "admin-key-123", "X-Org-Id": "org1"})
    assert res1.status_code == 200
    
    # Import for org2 with a different ID to avoid table-level primary key collision
    payload2 = [{"id": "mt2", "type": "domain", "value": "org2.com", "status": "active", "source": "scan"}]
    res2 = client.post("/import/", json=payload2, headers={"X-API-Key": "admin-key-123", "X-Org-Id": "org2"})
    assert res2.status_code == 200
    
    # Orgs should not see each other's data
    get_org1_own = client.get("/assets/mt1", headers={"X-API-Key": "admin-key-123", "X-Org-Id": "org1"})
    assert get_org1_own.status_code == 200
    
    get_org1_other = client.get("/assets/mt2", headers={"X-API-Key": "admin-key-123", "X-Org-Id": "org1"})
    assert get_org1_other.status_code == 404
    
    get_org2_own = client.get("/assets/mt2", headers={"X-API-Key": "admin-key-123", "X-Org-Id": "org2"})
    assert get_org2_own.status_code == 200
    
    get_org2_other = client.get("/assets/mt1", headers={"X-API-Key": "admin-key-123", "X-Org-Id": "org2"})
    assert get_org2_other.status_code == 404
