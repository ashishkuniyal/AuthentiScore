from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
import io
import csv

from app.services.bulk_processor import start_bulk_job, get_bulk_job_status, process_bulk_scan

router = APIRouter(prefix="/bulk", tags=["Bulk Scanning"])

@router.post("/upload")
async def upload_bulk_csv(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")
        
    content = await file.read()
    decoded = content.decode("utf-8")
    
    urls = []
    reader = csv.reader(io.StringIO(decoded))
    for row in reader:
        if row and row[0].strip():
            urls.append(row[0].strip())
            
    if not urls:
        raise HTTPException(status_code=400, detail="CSV is empty or invalid.")
        
    if len(urls) > 1000:
        raise HTTPException(status_code=400, detail="Maximum 1000 URLs per bulk upload allowed.")
        
    job_id = start_bulk_job(urls)
    
    # Process in the background so the HTTP request completes immediately
    background_tasks.add_task(process_bulk_scan, job_id, urls)
    
    return {"job_id": job_id, "message": f"Bulk scan started for {len(urls)} profiles."}

@router.get("/{job_id}")
async def get_job_status(job_id: str):
    job = get_bulk_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Bulk job not found.")
        
    # Convert datetime to string for JSON serialization
    if "created_at" in job:
        job["created_at"] = job["created_at"].isoformat()
        
    return job
