import io
import csv
import logging
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Depends

from app.services.bulk_processor import start_bulk_job, get_bulk_job_status, process_bulk_scan
from app.services.collector import validate_profile_url
from app.routes.auth import get_current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bulk", tags=["Bulk Scanning"])


@router.post("/upload")
def upload_bulk_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_active_user)
):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    try:
        content = file.file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")

    # 1 MB file upload cap (S9)
    if len(content) > 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds the 1 MB limit.")

    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File encoding must be UTF-8.")

    reader = csv.reader(io.StringIO(decoded))
    lines = [row for row in reader if row and any(cell.strip() for cell in row)]

    if not lines:
        raise HTTPException(status_code=400, detail="CSV is empty or invalid.")

    # Check for header row
    first_cell = lines[0][0].strip().lower()
    start_idx = 1 if first_cell in ["url", "profile_url", "profile", "username", "user"] else 0

    urls = []
    seen = set()
    for row in lines[start_idx:]:
        raw_val = row[0].strip()
        if not raw_val or raw_val in seen:
            continue
        seen.add(raw_val)

        # Standardize username to full URL if needed
        if "://" not in raw_val and not any(p in raw_val for p in ["instagram.com", "twitter.com", "x.com"]):
            raw_val = f"https://instagram.com/{raw_val.lstrip('@')}"

        val = validate_profile_url(raw_val)
        if val["valid"]:
            urls.append(raw_val)

    if not urls:
        raise HTTPException(status_code=400, detail="No valid profile URLs found in CSV.")

    if len(urls) > 1000:
        raise HTTPException(status_code=400, detail="Maximum 1000 URLs per bulk upload allowed.")

    user_id = str(current_user["_id"])
    job_id = start_bulk_job(urls, user_id=user_id)

    # Process in threadpool so request completes immediately
    background_tasks.add_task(process_bulk_scan, job_id, urls, user_id)

    return {"job_id": job_id, "message": f"Bulk scan started for {len(urls)} profiles."}


@router.get("/{job_id}")
def get_job_status(
    job_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    user_id = str(current_user["_id"])
    job = get_bulk_job_status(job_id, user_id=user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Bulk job not found.")

    if "created_at" in job and hasattr(job["created_at"], "isoformat"):
        job["created_at"] = job["created_at"].isoformat()

    return job
