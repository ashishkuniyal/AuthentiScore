"""
AuthentiScore — MongoDB Client & Utilities
==========================================

Provides:
  - Lazy-connected MongoClient (no network call at import time)
  - Collection references
  - setup_indexes()  — called from FastAPI lifespan (not at import)
  - save_scan_result()

B3 fix: client creation does NOT call serverSelectionTimeoutMS at import time.
S11 fix: load_dotenv(override=False) so real env vars take priority over .env
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Load environment variables
# override=False: real env-vars (container / prod) are NOT replaced by .env
# ─────────────────────────────────────────────────────────────

load_dotenv(override=False)

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("MONGODB_DATABASE", "authentiscore")

try:
    SCAN_RETENTION_DAYS = max(1, int(os.getenv("SCAN_RETENTION_DAYS", "30")))
except ValueError:
    SCAN_RETENTION_DAYS = 30

# ─────────────────────────────────────────────────────────────
# Client — created once, no network call until first operation
# ─────────────────────────────────────────────────────────────

client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
db = client[DATABASE_NAME]

# ─────────────────────────────────────────────────────────────
# Collection references
# ─────────────────────────────────────────────────────────────

scans_collection              = db["scans"]
bulk_jobs_collection          = db["bulk_jobs"]
influencer_audits_collection  = db["influencer_audits"]
users_collection              = db["users"]


# ─────────────────────────────────────────────────────────────
# Connection Test
# ─────────────────────────────────────────────────────────────

def test_mongodb_connection() -> bool:
    try:
        client.admin.command("ping")
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
# Index + TTL setup  (call from lifespan, not at import time)
# ─────────────────────────────────────────────────────────────

def setup_indexes() -> None:
    """
    Create all indexes. Safe to call on every startup — MongoDB
    ignores create_index when the index already exists.
    Called from the FastAPI lifespan context manager.
    """
    expire_secs = SCAN_RETENTION_DAYS * 24 * 3600

    try:
        # TTL on scans
        scans_collection.create_index(
            [("timestamp", ASCENDING)],
            expireAfterSeconds=expire_secs,
            name="scan_retention_ttl",
        )
        # Unique scan_id
        scans_collection.create_index(
            [("scan_id", ASCENDING)], unique=True, name="scan_id_unique"
        )
        # Listing by user
        scans_collection.create_index(
            [("user_id", ASCENDING), ("timestamp", DESCENDING)],
            name="scan_user_time",
        )

        # Users
        users_collection.create_index(
            [("email", ASCENDING)], unique=True, name="user_email_unique"
        )

        # Activity logs
        db["activity_logs"].create_index(
            [("user_id", ASCENDING), ("timestamp", DESCENDING)],
            name="activity_user_time",
        )

        # API keys
        db["api_keys"].create_index(
            [("user_id", ASCENDING)], name="api_keys_user"
        )

        # Bulk jobs
        bulk_jobs_collection.create_index(
            [("job_id", ASCENDING)], unique=True, name="bulk_job_id_unique"
        )

        # Influencer audits
        influencer_audits_collection.create_index(
            [("user_id", ASCENDING), ("timestamp", DESCENDING)],
            name="audit_user_time",
        )

        logger.info(
            "AuthentiScore MongoDB: indexes ensured (retention=%d days).",
            SCAN_RETENTION_DAYS,
        )

    except Exception as exc:
        logger.error("AuthentiScore MongoDB: index setup failed: %s", exc)


# ─────────────────────────────────────────────────────────────
# Save Scan Result
# ─────────────────────────────────────────────────────────────

def save_scan_result(
    scan_id: str,
    platform: str,
    username: str,
    profile_url: str,
    features: dict,
    result: dict,
    collection_source: str = "unknown",
    collection_status: str = "unknown",
    model_name: str = "CalibratedEnsemble_LR_RF_XGB",
    model_version: str = "v3",
    collection_metadata: Optional[dict] = None,
    user_id: Optional[str] = None,
) -> dict:
    """
    Persist a completed AuthentiScore prediction.

    Returns {"scan_id": ..., "inserted_id": ...} on success,
    or {"scan_id": ..., "error": ...} if MongoDB is down.
    """

    document = {
        "scan_id":              scan_id,
        "user_id":              user_id,
        "timestamp":            datetime.now(timezone.utc),
        "platform":             platform,
        "username":             username,
        "profile_url":          profile_url,
        "collection_source":    collection_source,
        "collection_status":    collection_status,
        "model_name":           model_name,
        "model_version":        model_version,
        "features":             features,
        "final_score":          result.get("final_score"),
        "classification":       result.get("classification"),
        "risk_components":      result.get("risk_components"),
        "top_ml_factors":       result.get("top_ml_factors"),
        "nlp_signals":          result.get("nlp_signals"),
        "rule_signals":         result.get("rule_signals"),
        "collection_metadata":  collection_metadata,
    }

    try:
        res = scans_collection.insert_one(document)
        return {"scan_id": scan_id, "inserted_id": str(res.inserted_id)}
    except DuplicateKeyError:
        logger.warning("Duplicate scan_id=%s; not re-inserted.", scan_id)
        return {"scan_id": scan_id, "inserted_id": None}
    except Exception as exc:
        logger.error("save_scan_result failed: %s", exc)
        return {"scan_id": scan_id, "error": str(exc)}