"""
AuthentiScore — Collector Provenance, Circuit Breaker & Manual Override Tests (B4 & B5)
=====================================================================================

Tests:
1. Circuit breaker state machine (CLOSED -> OPEN after 5 failures).
2. Data verified threshold logic (>= 6 of 8 core fields from direct source).
3. Error taxonomy classification.
4. POST /scan/{scan_id}/complete manual completion overrides missing fields.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.routes.auth import get_current_active_user
from app.database.mongodb import scans_collection
from app.services.circuit_breaker import CircuitBreaker
from app.services.collector import classify_error_taxonomy, build_provenance_and_verification


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


def test_circuit_breaker_trips_after_five_failures():
    """Circuit breaker must trip to OPEN after 5 consecutive failures."""
    cb = CircuitBreaker("test_breaker", threshold=5, cooldown=300)
    assert cb.can_execute() is True
    assert cb.state == "CLOSED"

    for _ in range(4):
        cb.record_failure()
        assert cb.can_execute() is True
        assert cb.state == "CLOSED"

    # 5th failure trips the breaker
    cb.record_failure()
    assert cb.state == "OPEN"
    assert cb.can_execute() is False


def test_data_verified_provenance_threshold():
    """Data verified badge requires >= 6 of 8 core fields from direct official sources."""
    # 7 core fields from permitted_public_page -> data_verified True
    profile_good = {
        "collection_source": "permitted_public_page",
        "fields_collected": ["username", "followers", "following", "posts", "bio", "has_profile_picture", "is_private"],
    }
    res_good = build_provenance_and_verification(profile_good)
    assert res_good["data_verified"] is True
    assert res_good["provenance"]["followers"]["confidence"] == 1.0

    # Only 3 core fields -> data_verified False
    profile_sparse = {
        "collection_source": "permitted_public_page",
        "fields_collected": ["username", "bio"],
    }
    res_sparse = build_provenance_and_verification(profile_sparse)
    assert res_sparse["data_verified"] is False

    # Manual user provided -> data_verified False
    profile_manual = {
        "collection_source": "user_provided",
        "fields_collected": ["username", "followers", "following", "posts", "bio", "has_profile_picture", "is_private"],
    }
    res_manual = build_provenance_and_verification(profile_manual)
    assert res_manual["data_verified"] is False


def test_error_taxonomy_mapping():
    """Error taxonomy accurately maps failure strings into categories."""
    assert classify_error_taxonomy("HTTP 429 Too Many Requests") == "rate_limited"
    assert classify_error_taxonomy("Instagram checkpoint challenge required") == "anti_bot_challenge"
    assert classify_error_taxonomy("User not found: 404") == "account_not_found"
    assert classify_error_taxonomy("Account suspended by platform") == "account_suspended"
    assert classify_error_taxonomy("Connection timed out after 30s") == "network_timeout"
    assert classify_error_taxonomy(None) == "none"


def test_manual_scan_completion():
    """POST /scan/{scan_id}/complete merges user fields and re-scores."""
    client = TestClient(app)
    scan_id = "test-scan-complete-123"

    import app.database.mongodb as mongo_mod
    # Seed an incomplete scan
    mongo_mod.scans_collection.insert_one({
        "scan_id": scan_id,
        "user_id": "507f1f77bcf86cd799439011",
        "platform": "instagram",
        "username": "incomplete_user",
        "profile_url": "https://www.instagram.com/incomplete_user",
        "profile": {"username": "incomplete_user"},
        "classification": "Insufficient Data",
        "final_score": None,
    })

    try:
        response = client.post(
            f"/scan/{scan_id}/complete",
            json={
                "followers": 1500,
                "following": 300,
                "posts": 50,
                "has_profile_picture": 1,
                "is_private": 0,
                "bio": "Now I have completed my profile info."
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["scan_id"] == scan_id
        assert data["final_score"] is not None
        assert data["classification"] != "Insufficient Data"
        assert data["field_sources"]["followers"] == "user_provided"
    finally:
        mongo_mod.scans_collection.delete_one({"scan_id": scan_id})

