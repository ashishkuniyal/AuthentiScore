"""
AuthentiScore — System Status & GDPR Compliance Deletion Tests (B7 & B8)
========================================================================

Tests:
1. GET /system/status returns rolling latency, components loaded, active workers.
2. DELETE /scan/{scan_id} deletes user scan record and cascades to feedback.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes.auth import get_current_active_user


@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[get_current_active_user] = lambda: {
        "_id": "507f1f77bcf86cd799439011",
        "email": "test@example.com",
        "name": "Test User",
        "role": "user",
    }
    yield
    app.dependency_overrides.pop(get_current_active_user, None)


def test_get_system_status():
    """GET /system/status provides truthful operational health and components."""
    client = TestClient(app)
    response = client.get("/system/status")
    assert response.status_code == 200
    data = response.json()

    assert "rolling_latency_ms" in data
    assert "loaded_components" in data
    assert "total_scans_processed" in data
    assert "active_workers" in data
    assert "status" in data

    components = data["loaded_components"]
    assert "ml_model" in components
    assert "mongodb" in components
    assert "circuit_breakers" in components


def test_delete_scan_gdpr_compliance():
    """DELETE /scan/{scan_id} removes user scan and associated data."""
    client = TestClient(app)
    scan_id = "test-delete-scan-123"

    import app.database.mongodb as mongo_mod
    mongo_mod.scans_collection.insert_one({
        "scan_id": scan_id,
        "user_id": "507f1f77bcf86cd799439011",
        "platform": "instagram",
        "username": "delete_me",
        "final_score": 10.0,
    })

    # Delete scan
    del_resp = client.delete(f"/scan/{scan_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"

    # Confirm it is gone from db
    found = mongo_mod.scans_collection.find_one({"scan_id": scan_id})
    assert found is None

    # Deleting nonexistent returns 404
    del_resp_again = client.delete(f"/scan/{scan_id}")
    assert del_resp_again.status_code == 404
