from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.services.audience_auditor import run_audience_audit, run_live_audience_audit
from app.services.collectors.apify_instagram_collector import ApifyInstagramCollector
import uuid

router = APIRouter(
    prefix="/audit",
    tags=["Audit"]
)

@router.post("/influencer/csv")
async def audit_influencer_csv(
    file: UploadFile = File(...),
    target_influencer: str = Form("Unknown")
):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")
        
    try:
        content = await file.read()
        csv_text = content.decode('utf-8')
        result = run_audience_audit(csv_text, target_influencer)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class LiveAuditRequest(BaseModel):
    target_influencer: str
    platform: str = "instagram"
    sample_size: int = 10
    simulate_fallback: bool = False

@router.post("/influencer/live")
async def audit_influencer_live(
    request: LiveAuditRequest,
    background_tasks: BackgroundTasks
):
    audit_id = str(uuid.uuid4())
    
    # Fire off background task
    background_tasks.add_task(
        run_live_audience_audit,
        request.target_influencer,
        request.platform,
        request.sample_size,
        audit_id,
        request.simulate_fallback
    )
    
    return {
        "message": "Live audit started",
        "audit_id": audit_id,
        "status": "processing"
    }

@router.get("/instagram/status")
async def get_instagram_session_status():
    status_info = ApifyInstagramCollector.validate_session()
    return status_info
