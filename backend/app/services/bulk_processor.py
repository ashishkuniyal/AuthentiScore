import os
import time
import uuid
import logging
from datetime import datetime, timezone

from app.database.mongodb import bulk_jobs_collection, save_scan_result
from app.services.collector import collect_profile
from app.services.feature_engine import extract_features
from app.services.model_store import MODEL_NAME, MODEL_VERSION

logger = logging.getLogger(__name__)


def start_bulk_job(urls: list[str], user_id: str | None = None) -> str:
    job_id = str(uuid.uuid4())
    bulk_jobs_collection.insert_one({
        "job_id": job_id,
        "user_id": user_id,
        "status": "processing",
        "total": len(urls),
        "completed": 0,
        "failed": 0,
        "insufficient_data": 0,
        "created_at": datetime.now(timezone.utc),
        "results": []
    })
    return job_id


def get_bulk_job_status(job_id: str, user_id: str | None = None) -> dict | None:
    query = {"job_id": job_id}
    if user_id:
        query["user_id"] = user_id
    job = bulk_jobs_collection.find_one(query, {"_id": 0})
    return job


def process_bulk_scan(job_id: str, urls: list[str], user_id: str | None = None):
    from app.routes.scan import run_risk_pipeline

    delay_seconds = float(os.getenv("BULK_SCAN_DELAY_SECONDS", "1.0"))
    has_failed_fatal = False

    try:
        for idx, url in enumerate(urls):
            result_data = None
            status = "failed"

            try:
                url = url.strip()
                if not url:
                    continue

                if idx > 0 and delay_seconds > 0:
                    time.sleep(delay_seconds)

                profile_data = collect_profile(url)

                if profile_data.get("collection_status") in ["success", "partial"]:
                    bio = profile_data.get("bio") or ""
                    report = run_risk_pipeline(profile_data, bio)
                    final_score = report.get("final_score")

                    if final_score is None:
                        status = "insufficient_data"
                        result_data = {
                            "url": url,
                            "status": "insufficient_data",
                            "score": None,
                            "classification": "Insufficient Data"
                        }
                    else:
                        status = "success"
                        result_data = {
                            "url": url,
                            "status": "success",
                            "score": round(float(final_score), 1),
                            "classification": report.get("classification", "Unknown")
                        }

                    # Persist scan to MongoDB so history and stats reflect bulk results (C28)
                    scan_id = str(uuid.uuid4())
                    features = extract_features(profile_data)
                    save_scan_result(
                        scan_id=scan_id,
                        platform=profile_data.get("platform", "unknown"),
                        username=profile_data.get("username", "unknown"),
                        profile_url=url,
                        features=features,
                        result=report,
                        collection_source=profile_data.get("collection_source", "bulk"),
                        collection_status=profile_data.get("collection_status", "success"),
                        model_name=MODEL_NAME,
                        model_version=MODEL_VERSION,
                        user_id=user_id
                    )

                else:
                    status = "failed"
                    result_data = {
                        "url": url,
                        "status": "failed",
                        "error": profile_data.get("error", "Failed to collect profile data")
                    }

            except Exception as e:
                logger.error(f"Bulk scan error for {url}: {e}")
                status = "failed"
                result_data = {
                    "url": url,
                    "status": "failed",
                    "error": str(e)
                }

            # Update job progress in MongoDB
            inc_fields = {
                "completed": 1 if status == "success" else 0,
                "failed": 1 if status == "failed" else 0,
                "insufficient_data": 1 if status == "insufficient_data" else 0
            }
            bulk_jobs_collection.update_one(
                {"job_id": job_id},
                {
                    "$inc": inc_fields,
                    "$push": {"results": result_data}
                }
            )

    except Exception as fatal_e:
        logger.exception(f"Fatal error processing bulk scan job {job_id}: {fatal_e}")
        has_failed_fatal = True
    finally:
        # Guarantee terminal state is set (C28)
        terminal_status = "failed" if has_failed_fatal else "completed"
        bulk_jobs_collection.update_one(
            {"job_id": job_id},
            {"$set": {"status": terminal_status, "completed_at": datetime.now(timezone.utc)}}
        )
