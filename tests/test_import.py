import pytest

def test_import_endpoint(client):
    payload = [
        {
            "id": "a1", "type": "domain", "value": "test.com",
            "status": "active", "source": "scan"
        },
        {
            "id": "a2", "type": "subdomain", "value": "api.test.com",
            "status": "active", "source": "scan", "parent": "a1"
        }
    ]
    
    # First import
    response = client.post("/import/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["created"] == 2
    assert data["updated"] == 0
    assert data["skipped"] == 0
    
    # Idempotent import test
    response2 = client.post("/import/", json=payload)
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["created"] == 0
    assert data2["updated"] == 2  # They get updated because they exist
    assert data2["skipped"] == 0

def test_import_invalid_data(client):
    payload = [
        {"id": "a1", "type": "domain"} # missing value
    ]
    response = client.post("/import/", json=payload)
    assert response.status_code == 422 # Pydantic validation catches this!
