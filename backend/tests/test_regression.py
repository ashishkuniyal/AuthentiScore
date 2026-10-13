"""
AuthentiScore — M3 Hermetic Regression Test Suite
=================================================
Tests 1–14 covering security (S1, S2, S4, S5), correctness (C1, C4, C5, C6, C12, C14, C20, C22, C23, C28).
Runs completely offline without MongoDB daemon, network, or external model files.
"""

import io
import json
import math
import threading
import time
import pytest
from datetime import datetime, timezone
from bson import ObjectId
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.routes.auth import verify_token_string, _determine_role_and_plan
from app.core.risk_levels import classify_risk, is_suspicious, risk_key
from app.services.feature_engine import extract_features, calculate_profile_completeness
from app.services.explainer import generate_ml_explanation, _feature_label
from app.services.audience_auditor import score_profile
from app.services.report_generator import generate_pdf_report
from app.core.ws import manager, notify_user_threadsafe
from app.services.collectors.apify_instagram_collector import ApifyInstagramCollector


# ─────────────────────────────────────────────────────────────
# 1. Forged/Unsigned JWT -> 401 (S1)
# ─────────────────────────────────────────────────────────────
def test_regression_01_forged_jwt():
    # Attempting to verify an unsigned or forged token must raise HTTPException 401
    with pytest.raises(HTTPException) as exc_info:
        verify_token_string("eyJhbGciOiJub25lIn0.eyJlbWFpbCI6ImF0dGFja2VyQGV4YW1wbGUuY29tIn0.")
    assert exc_info.value.status_code == 401


# ─────────────────────────────────────────────────────────────
# 2. sysadmin@x.com -> Role "User" (S2)
# ─────────────────────────────────────────────────────────────
def test_regression_02_admin_privilege_escalation_prevented(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "real_admin@authentiscore.com")
    role, plan = _determine_role_and_plan("sysadmin@anything.com", {"email_verified": True})
    assert role == "User"
    assert plan == "Free"

    # Exact match from ADMIN_EMAILS allowlist with verified email gets Administrator
    admin_role, admin_plan = _determine_role_and_plan("real_admin@authentiscore.com", {"email_verified": True})
    assert admin_role == "Administrator"
    assert admin_plan == "Pro"


# ─────────────────────────────────────────────────────────────
# 3. Insufficient-Data scan does not crash endpoints or PDF (C4)
# ─────────────────────────────────────────────────────────────
def test_regression_03_insufficient_data_endpoints_and_pdf(hermetic_env):
    import app.database.mongodb as db_mod

    test_user_id = str(ObjectId())
    user_doc = {
        "_id": ObjectId(test_user_id),
        "email": "test_insufficient@example.com",
        "username": "testuser",
        "role": "User",
        "plan": "Free"
    }
    db_mod.users_collection.insert_one(user_doc)

    scan_id = "test-scan-insufficient-001"
    scan_doc = {
        "scan_id": scan_id,
        "user_id": test_user_id,
        "platform": "instagram",
        "username": "unknown_profile",
        "final_score": None,
        "classification": "Insufficient Data",
        "top_ml_factors": None,
        "nlp_signals": None,
        "score_breakdown": None,
        "timestamp": datetime.now(timezone.utc)
    }
    db_mod.scans_collection.insert_one(scan_doc)

    from app.routes.scan import get_recent_scans
    from app.routes.analytics import analytics_summary, dashboard_summary

    # /scan/recent
    recents = get_recent_scans(limit=5, current_user=user_doc)
    assert len(recents) >= 1
    recent_item = next(r for r in recents if r["scan_id"] == scan_id)
    assert recent_item["score"] == "N/A"
    assert recent_item["status"] == "Insufficient Data"
    assert recent_item["risk_level"] == "insufficient_data"

    # /analytics/summary
    summary = analytics_summary(current_user=user_doc)
    assert "insufficient_data" in summary["classification_counts"]
    assert summary["classification_counts"]["insufficient_data"] >= 1

    # /analytics/dashboard-summary
    dash_summary = dashboard_summary(current_user=user_doc)
    assert dash_summary["insufficient_data"] >= 1

    # PDF generation for Insufficient Data
    pdf_bytes = generate_pdf_report(scan_doc)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0


# ─────────────────────────────────────────────────────────────
# 4. score_profile with Insufficient Data -> not "Error" (C4)
# ─────────────────────────────────────────────────────────────
def test_regression_04_score_profile_insufficient_data():
    sparse_data = {
        "collection_status": "partial",
        "followers": None,
        "following": None,
        "posts": None,
        "bio": None,
        "has_profile_picture": None,
        "is_private": None
    }
    scored = score_profile("sparse_user", "instagram", sparse_data)
    res = scored["result"]
    assert res["classification"] == "Insufficient Data"
    assert res["status"] != "Error"
    assert res["score"] is None
    assert scored["is_fake"] is False


# ─────────────────────────────────────────────────────────────
# 5. /scan keeps supplied bio_length / username_digit_ratio (C6)
# ─────────────────────────────────────────────────────────────
def test_regression_05_features_preserve_supplied_bio_and_digits():
    features = extract_features({
        "bio_length": 85.0,
        "username_digit_ratio": 0.88,
        "followers": 200,
        "following": 150
    })
    assert features["bio_length"] == 85.0
    assert features["username_digit_ratio"] == 0.88


# ─────────────────────────────────────────────────────────────
# 6. Instaloader failure -> fallback collector invoked & error preserved (C12)
# ─────────────────────────────────────────────────────────────
def test_regression_06_instaloader_failure_invokes_fallback(monkeypatch):
    from app.services.collector import collect_profile
    import app.services.collectors.instaloader_collector as instaloader_mod
    import app.services.collectors.instagram_collector as instagram_mod

    # Make instaloader collector fail
    monkeypatch.setattr(
        instaloader_mod.InstaLoaderCollector,
        "run",
        lambda self, url: {
            "collection_status": "failed",
            "platform": "instagram",
            "identifier": "target_user",
            "error": "Instaloader rate limit 429",
            "fields_collected": []
        }
    )

    fallback_called = []
    def mock_instagram_run(self, url):
        fallback_called.append(True)
        return {
            "collection_status": "failed",
            "platform": "instagram",
            "identifier": "target_user",
            "error": "Instagram fallback login wall",
            "fields_collected": []
        }
    monkeypatch.setattr(instagram_mod.InstagramCollector, "run", mock_instagram_run)

    result = collect_profile("https://instagram.com/target_user")
    assert len(fallback_called) == 1
    assert result["collection_status"] == "failed"
    assert "error" in result


# ─────────────────────────────────────────────────────────────
# 7. profile_completeness identical in training and serving for empty bio (C20)
# ─────────────────────────────────────────────────────────────
def test_regression_07_profile_completeness_empty_bio():
    # Empty bio should not count as present
    profile_empty_bio = {
        "username": "user123",
        "bio": "",
        "followers": 100,
        "following": 50,
        "posts": 10,
        "has_profile_picture": 1
    }
    comp_empty = calculate_profile_completeness(profile_empty_bio)
    assert comp_empty == round(5 / 6.0, 4)  # 0.8333

    profile_with_bio = {
        "username": "user123",
        "bio": "Authentic bio text",
        "followers": 100,
        "following": 50,
        "posts": 10,
        "has_profile_picture": 1
    }
    comp_full = calculate_profile_completeness(profile_with_bio)
    assert comp_full == 1.0


# ─────────────────────────────────────────────────────────────
# 8. Explainer output contains no NaN and serializes allow_nan=False (C22)
# ─────────────────────────────────────────────────────────────
def test_regression_08_explainer_no_nan_serializable():
    factors = generate_ml_explanation({
        "followers": 500,
        "following": None,
        "posts": None,
        "bio_length": None
    }, top_n=3)

    assert isinstance(factors, list)
    assert len(factors) > 0
    # Must serialize with allow_nan=False without raising ValueError
    serialized = json.dumps(factors, allow_nan=False)
    assert serialized is not None

    for factor in factors:
        if factor["imputed"]:
            assert factor["value"] is None
        assert math.isfinite(factor["shap_value"])


# ─────────────────────────────────────────────────────────────
# 9. Label direction table (C23)
# ─────────────────────────────────────────────────────────────
def test_regression_09_label_direction_table():
    # When is_risk=True: label must describe risk factor
    risk_label_pic = _feature_label("has_profile_picture", 0, is_risk=True)
    assert "No profile picture" in risk_label_pic

    # When is_risk=False: label must describe trust signal
    trust_label_pic = _feature_label("has_profile_picture", 1, is_risk=False)
    assert "Profile picture is set" in trust_label_pic

    # Followers
    risk_followers = _feature_label("followers", 5, is_risk=True)
    assert "low" in risk_followers.lower() or "risk" in risk_followers.lower()

    trust_followers = _feature_label("followers", 50000, is_risk=False)
    assert "follower base" in trust_followers.lower() or "trust" in trust_followers.lower()


# ─────────────────────────────────────────────────────────────
# 10. notify_user_threadsafe delivers from a worker thread (C1)
# ─────────────────────────────────────────────────────────────
@pytest.mark.anyio
async def test_regression_10_notify_user_threadsafe_from_worker():
    import asyncio
    manager.capture_loop()

    received_messages = []
    class MockWebSocket:
        async def send_text(self, text):
            received_messages.append(json.loads(text))

    mock_ws = MockWebSocket()
    user_id = "test_worker_user_999"
    manager._connections[user_id] = {mock_ws}

    def worker_thread():
        time.sleep(0.05)
        notify_user_threadsafe(user_id, {"type": "WORKER_EVENT", "test": True})

    thread = threading.Thread(target=worker_thread)
    thread.start()
    thread.join()

    # Allow event loop to process the dispatched coroutine
    await asyncio.sleep(0.1)

    assert len(received_messages) == 1
    assert received_messages[0]["type"] == "WORKER_EVENT"
    manager.disconnect(mock_ws, user_id)


# ─────────────────────────────────────────────────────────────
# 11. Bulk upload with BOM + header row (C28)
# ─────────────────────────────────────────────────────────────
def test_regression_11_bulk_upload_bom_and_header(hermetic_env):
    from app.routes.bulk import upload_bulk_csv
    from fastapi import UploadFile, BackgroundTasks

    user_id = str(ObjectId())
    current_user = {"_id": ObjectId(user_id), "email": "bulk@test.com"}

    # CSV with UTF-8-SIG (BOM) and header row
    csv_bytes = "\ufeffurl\nhttps://instagram.com/user_one\nhttps://instagram.com/user_two\n".encode("utf-8")
    upload_file = UploadFile(filename="test.csv", file=io.BytesIO(csv_bytes))

    bg = BackgroundTasks()
    res = upload_bulk_csv(background_tasks=bg, file=upload_file, current_user=current_user)

    assert "job_id" in res
    assert "Bulk scan started for 2 profiles." in res["message"]


# ─────────────────────────────────────────────────────────────
# 12. User stats count "High Risk" and "Low Risk" correctly (C4)
# ─────────────────────────────────────────────────────────────
def test_regression_12_user_stats_counts_risk_correctly(hermetic_env):
    import app.database.mongodb as db_mod
    from app.routes.users import get_user_stats

    user_id = ObjectId()
    user_str = str(user_id)
    current_user = {"_id": user_id, "email": "stats_user@test.com", "reportsGenerated": 4}

    # Insert 1 Low Risk, 1 High Risk, 1 Insufficient Data scan
    db_mod.scans_collection.insert_one({
        "scan_id": "s1", "user_id": user_str, "final_score": 15.0, "classification": "Low Risk", "timestamp": datetime.now(timezone.utc)
    })
    db_mod.scans_collection.insert_one({
        "scan_id": "s2", "user_id": user_str, "final_score": 85.0, "classification": "High Risk", "timestamp": datetime.now(timezone.utc)
    })
    db_mod.scans_collection.insert_one({
        "scan_id": "s3", "user_id": user_str, "final_score": None, "classification": "Insufficient Data", "timestamp": datetime.now(timezone.utc)
    })

    stats = get_user_stats(current_user=current_user)
    assert stats["totalScans"] == 3
    assert stats["authenticProfiles"] == 1
    assert stats["fakeProfiles"] == 1
    assert stats["reportsGenerated"] == 4


# ─────────────────────────────────────────────────────────────
# 13. Apify collector returns None for unknown follower fields (C14)
# ─────────────────────────────────────────────────────────────
def test_regression_13_apify_collector_no_fake_numbers(monkeypatch):
    sample_raw = [
        {"username": "follower_1", "profilePicUrl": "https://img.example/pic.jpg"},
        {"username": "follower_2"}
    ]

    class MockResponse:
        status_code = 200
        def json(self):
            return sample_raw

    import httpx
    monkeypatch.setattr(httpx.Client, "post", lambda self, url, **kwargs: MockResponse())

    followers = ApifyInstagramCollector.get_follower_sample("target_influencer", sample_size=2)
    assert len(followers) == 2
    f1 = followers[0]
    assert f1["followers"] is None
    assert f1["following"] is None
    assert f1["posts"] is None
    assert f1["bio"] is None
    assert f1["collection_status"] == "partial"


# ─────────────────────────────────────────────────────────────
# 14. One shared risk-band helper boundaries (C5)
# ─────────────────────────────────────────────────────────────
def test_regression_14_shared_risk_band_helper():
    assert classify_risk(33.99) == "Low Risk"
    assert classify_risk(34.0) == "Medium Risk"
    assert classify_risk(66.99) == "Medium Risk"
    assert classify_risk(67.0) == "High Risk"
    assert classify_risk(89.99) == "High Risk"
    assert classify_risk(90.0) == "Very High Risk"

    assert is_suspicious(33.99) is False
    assert is_suspicious(66.99) is False
    assert is_suspicious(67.0) is True
    assert is_suspicious(90.0) is True

    assert risk_key("Low Risk") == "low"
    assert risk_key("Medium Risk") == "medium"
    assert risk_key("High Risk") == "high"
    assert risk_key("Very High Risk") == "very_high"
    assert risk_key("Insufficient Data") == "insufficient_data"
