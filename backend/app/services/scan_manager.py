"""
AuthentiScore — Scan Job Manager & Cache (B2 & B3)
=================================================

Manages asynchronous background scan jobs with:
- Bounded concurrency (ThreadPoolExecutor max_workers=4)
- Per-user job limits (max 3 concurrent jobs)
- Stage transitions and WebSocket SCAN_PROGRESS broadcasting
- 24-hour result caching with in-flight request deduplication
- Job cancellation
"""

from __future__ import annotations
import uuid
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

from app.database.mongodb import scans_collection, save_scan_result, db
from app.core.ws import notify_user_threadsafe
from app.services.collector import collect_profile
from app.services.feature_engine import extract_features
from app.services.model_store import MODEL_NAME, MODEL_VERSION

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 86400  # 24 hours (Decision S6)
MAX_WORKERS = 4            # Bounded worker pool (Decision S7)
MAX_JOBS_PER_USER = 3      # Max queued/running jobs per user

_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="scan_worker")

# In-memory jobs store
_jobs: Dict[str, Dict[str, Any]] = {}

# In-flight deduplication: (platform, username) -> job_id
_in_flight: Dict[Tuple[str, str], str] = {}


def get_cached_scan(platform: str, username: str) -> Optional[Dict[str, Any]]:
    """
    Look up a completed scan in MongoDB within the last 24 hours.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=CACHE_TTL_SECONDS)
    try:
        doc = scans_collection.find_one(
            {
                "platform": platform.lower(),
                "username": username.lower(),
                "timestamp": {"$gte": cutoff},
            },
            {"_id": 0}
        )
        if doc:
            doc["from_cache"] = True
            return doc
    except Exception as exc:
        logger.warning("Cache lookup error: %s", exc)
    return None


def get_active_user_job_count(user_id: str) -> int:
    """Count how many jobs are currently queued or running for this user."""
    return sum(
        1 for j in _jobs.values()
        if j.get("user_id") == user_id and j.get("status") in ("queued", "running")
    )


def emit_progress(job_id: str, stage: str, progress: int, message: str, status: str = "running"):
    """Update job state and broadcast WebSocket progress event."""
    job = _jobs.get(job_id)
    if not job or job.get("status") == "cancelled":
        return

    job["stage"] = stage
    job["progress"] = progress
    job["status"] = status
    job["message"] = message
    job["updated_at"] = datetime.now(timezone.utc).isoformat()

    user_id = job.get("user_id")
    if user_id:
        notify_user_threadsafe(user_id, {
            "type": "SCAN_PROGRESS",
            "job_id": job_id,
            "stage": stage,
            "progress": progress,
            "status": status,
            "message": message,
            "platform": job.get("platform"),
            "username": job.get("username"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


def _execute_scan_job(job_id: str, platform: str, username: str, canonical_url: str, user_id: str):
    """Worker function executed inside ThreadPoolExecutor."""
    job = _jobs.get(job_id)
    if not job or job.get("status") == "cancelled":
        return

    key = (platform.lower(), username.lower())

    try:
        # 1. Normalizing (done prior to dispatch, but update progress)
        emit_progress(job_id, "normalizing", 15, f"Normalized handle @{username} on {platform}")

        # Check cancellation
        if _jobs.get(job_id, {}).get("status") == "cancelled":
            return

        # 2. Collecting
        emit_progress(job_id, "collecting", 35, f"Fetching profile data for @{username}...")
        collected = collect_profile(canonical_url)
        
        if _jobs.get(job_id, {}).get("status") == "cancelled":
            return

        # 3. Features
        emit_progress(job_id, "features", 60, "Extracting behavioral and account features...")
        features = extract_features(collected)
        bio = collected.get("bio") or ""

        if _jobs.get(job_id, {}).get("status") == "cancelled":
            return

        # 4. Scoring
        emit_progress(job_id, "scoring", 80, "Running multi-stage ensemble scoring...")
        from app.routes.scan import run_risk_pipeline
        result = run_risk_pipeline(collected, bio)

        if _jobs.get(job_id, {}).get("status") == "cancelled":
            return

        # 5. Explaining
        emit_progress(job_id, "explaining", 95, "Synthesizing explainability reasons...")

        # Persist scan result to DB
        scan_id = job.get("scan_id", str(uuid.uuid4()))
        collection_metadata = {
            "source": collected.get("collection_source", "permitted_public_page"),
            "status": collected.get("collection_status", "success"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fields_collected": collected.get("fields_collected", []),
            "trust_level": collected.get("trust_level"),
            "data_verified": collected.get("data_verified", False),
        }

        save_scan_result(
            scan_id=scan_id,
            platform=platform,
            username=username,
            profile_url=canonical_url,
            features=features,
            result=result,
            collection_source=collection_metadata["source"],
            collection_status=collection_metadata["status"],
            model_name=MODEL_NAME,
            model_version=MODEL_VERSION,
            collection_metadata=collection_metadata,
            user_id=user_id,
        )

        full_result = {
            "scan_id": scan_id,
            "platform": platform,
            "username": username,
            "profile_url": canonical_url,
            "display_name": collected.get("display_name"),
            "collected_bio": bio or None,
            "profile": collected,
            "features": features,
            **result,
            "collection": collection_metadata,
            "from_cache": False,
        }

        job["result"] = full_result
        emit_progress(job_id, "complete", 100, "Analysis complete", status="complete")

        # Notify completion
        notify_user_threadsafe(user_id, {
            "type": "SCAN_COMPLETE",
            "job_id": job_id,
            "scan_id": scan_id,
            "message": f"Analysis complete for @{username}",
            "risk_score": result.get("final_score"),
            "platform": platform,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    except Exception as exc:
        logger.exception("Scan job %s failed: %s", job_id, exc)
        job["error"] = str(exc)
        emit_progress(job_id, "failed", 0, f"Analysis failed: {exc}", status="failed")

    finally:
        # Clear in-flight record
        if _in_flight.get(key) == job_id:
            _in_flight.pop(key, None)


def create_scan_job(
    platform: str,
    username: str,
    canonical_url: str,
    user_id: str,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """
    Enqueue a background scan job or return cached/in-flight result.
    """
    key = (platform.lower(), username.lower())

    # 1. Check in-flight deduplication
    if not force_refresh and key in _in_flight:
        existing_job_id = _in_flight[key]
        existing_job = _jobs.get(existing_job_id)
        if existing_job and existing_job.get("status") in ("queued", "running"):
            return {
                "job_id": existing_job_id,
                "status": existing_job.get("status"),
                "stage": existing_job.get("stage", "queued"),
                "progress": existing_job.get("progress", 0),
                "from_cache": False,
                "deduplicated": True,
            }

    # 2. Check 24-hour cache
    if not force_refresh:
        cached = get_cached_scan(platform, username)
        if cached:
            cached_job_id = str(uuid.uuid4())
            _jobs[cached_job_id] = {
                "job_id": cached_job_id,
                "scan_id": cached.get("scan_id"),
                "user_id": user_id,
                "platform": platform,
                "username": username,
                "status": "complete",
                "stage": "complete",
                "progress": 100,
                "result": cached,
                "error": None,
                "from_cache": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            return {
                "job_id": cached_job_id,
                "status": "complete",
                "stage": "complete",
                "progress": 100,
                "from_cache": True,
                "result": cached,
            }

    # 3. Check per-user rate limit
    if get_active_user_job_count(user_id) >= MAX_JOBS_PER_USER:
        raise ValueError(f"Too many active scan jobs (max {MAX_JOBS_PER_USER} concurrent scans per user).")

    # 4. Create new job
    job_id = str(uuid.uuid4())
    scan_id = str(uuid.uuid4())

    job_data = {
        "job_id": job_id,
        "scan_id": scan_id,
        "user_id": user_id,
        "platform": platform,
        "username": username,
        "canonical_url": canonical_url,
        "status": "queued",
        "stage": "queued",
        "progress": 0,
        "message": "Job queued for analysis",
        "result": None,
        "error": None,
        "from_cache": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    _jobs[job_id] = job_data
    _in_flight[key] = job_id

    # Dispatch to background thread pool
    _executor.submit(_execute_scan_job, job_id, platform, username, canonical_url, user_id)

    return {
        "job_id": job_id,
        "status": "queued",
        "stage": "queued",
        "progress": 0,
        "platform": platform,
        "username": username,
        "from_cache": False,
    }


def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve current state of a scan job."""
    return _jobs.get(job_id)


def cancel_job(job_id: str) -> bool:
    """Attempt to cancel an ongoing or queued job."""
    job = _jobs.get(job_id)
    if not job:
        return False
    if job.get("status") in ("complete", "failed"):
        return False

    job["status"] = "cancelled"
    job["stage"] = "cancelled"
    job["message"] = "Scan cancelled by user"
    job["updated_at"] = datetime.now(timezone.utc).isoformat()

    key = (job.get("platform", "").lower(), job.get("username", "").lower())
    if _in_flight.get(key) == job_id:
        _in_flight.pop(key, None)

    return True
