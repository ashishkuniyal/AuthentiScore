"""
AuthentiScore — Background Scan Jobs & Cache Tests (B2 & B3)
============================================================

Tests:
1. Consent is required (HTTP 422 if consent: False).
2. Scan job creation, retrieval, and stage progress.
3. 24-hour cache hit returns from_cache: True.
4. Job cancellation via DELETE /scan/jobs/{job_id}.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from app.main import app
from app.routes.auth import get_current_active_user
from app.services.scan_manager import (
    create_scan_job,
    get_job_status,
    cancel_job,
    _jobs,
)


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



def test_consent_enforced_on_scan_jobs():
    """Submitting scan job without consent must fail with HTTP 422."""
    client = TestClient(app)
    response = client.post(
        "/scan/jobs",
        json={"input": "natgeo", "consent": False}
    )
    assert response.status_code == 422
    assert "Consent must be confirmed" in response.json()["detail"]


def test_create_and_query_scan_job():
    """Creating a scan job returns a job_id and can be queried."""
    client = TestClient(app)

    with patch("app.services.scan_manager.collect_profile") as mock_collect, \
         patch("app.services.scan_manager.save_scan_result"):

        mock_collect.return_value = {
            "platform": "instagram",
            "username": "testuser",
            "followers": 1000,
            "following": 200,
            "posts": 50,
            "has_profile_picture": 1,
            "is_private": 0,
            "bio": "Official test account",
            "collection_source": "permitted_public_page",
            "collection_status": "success",
            "fields_collected": ["followers", "following", "posts", "bio"],
        }

        response = client.post(
            "/scan/jobs",
            json={"input": "testuser", "consent": True}
        )
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        job_id = data["job_id"]

        # Query job status
        status_resp = client.get(f"/scan/jobs/{job_id}")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["job_id"] == job_id
        assert status_data["status"] in ("queued", "running", "complete")


def test_scan_job_cancellation():
    """Scan job can be cancelled via DELETE."""
    client = TestClient(app)
    
    # Pre-populate a fake queued job
    fake_job_id = "test-job-to-cancel"
    _jobs[fake_job_id] = {
        "job_id": fake_job_id,
        "user_id": "507f1f77bcf86cd799439011",
        "platform": "instagram",
        "username": "canceluser",
        "status": "queued",
        "stage": "queued",
        "progress": 0,
    }

    del_resp = client.delete(f"/scan/jobs/{fake_job_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "cancelled"

    # Query status confirms cancelled
    job = get_job_status(fake_job_id)
    assert job["status"] == "cancelled"


def test_cache_hit_returns_from_cache():
    """When a scan is found in the 24-hour cache, it returns from_cache: True."""
    client = TestClient(app)

    cached_scan = {
        "scan_id": "cached-1234",
        "platform": "instagram",
        "username": "cacheduser",
        "final_score": 15.0,
        "classification": "Low Risk",
        "timestamp": datetime.now(timezone.utc),
    }

    with patch("app.services.scan_manager.get_cached_scan") as mock_cache:
        mock_cache.return_value = cached_scan

        response = client.post(
            "/scan/jobs",
            json={"input": "cacheduser", "consent": True}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["from_cache"] is True
        assert data["status"] == "complete"

