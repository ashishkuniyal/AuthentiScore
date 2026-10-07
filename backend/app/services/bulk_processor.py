import uuid
from datetime import datetime, timezone
import logging

from app.database.mongodb import bulk_jobs_collection
from app.services.collector import collect_profile

logger = logging.getLogger(__name__)

def start_bulk_job(urls: list[str]) -> str:
    job_id = str(uuid.uuid4())
    bulk_jobs_collection.insert_one({
        "job_id": job_id,
        "status": "processing",
        "total": len(urls),
        "completed": 0,
        "failed": 0,
        "created_at": datetime.now(timezone.utc),
        "results": []
    })
    return job_id

def get_bulk_job_status(job_id: str) -> dict:
    job = bulk_jobs_collection.find_one({"job_id": job_id}, {"_id": 0})
    return job

def process_bulk_scan(job_id: str, urls: list[str]):
    from app.routes.scan import run_risk_pipeline
    
    for url in urls:
        result_data = None
        status = "failed"
        
        try:
            url = url.strip()
            if not url:
                continue
                
            profile_data = collect_profile(url)
            
            if profile_data.get("collection_status") in ["success", "partial"]:
                report = run_risk_pipeline(profile_data, profile_data.get("bio", ""))
                result_data = {
                    "url": url,
                    "status": "success",
                    "score": report["final_score"],
                    "classification": report["classification"]
                }
                status = "success"
            else:
                result_data = {
                    "url": url,
                    "status": "failed",
                    "error": profile_data.get("error", "Failed to collect profile data")
                }
        except Exception as e:
            logger.error(f"Bulk scan error for {url}: {e}")
            result_data = {
                "url": url,
                "status": "failed",
                "error": str(e)
            }
            
        # Update Job Progress in DB
        update_fields = {
            "$inc": {"completed": 1 if status == "success" else 0, "failed": 1 if status == "failed" else 0},
            "$push": {"results": result_data}
        }
        bulk_jobs_collection.update_one({"job_id": job_id}, update_fields)
        
    # Mark job as completed
    bulk_jobs_collection.update_one({"job_id": job_id}, {"$set": {"status": "completed"}})
