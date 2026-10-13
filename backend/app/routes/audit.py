import logging
import time
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field

from app.services.audience_auditor import run_audience_audit, run_live_audience_audit
from app.services.collectors.apify_instagram_collector import ApifyInstagramCollector
from app.routes.auth import get_current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/audit",
    tags=["Audit"]
)

# 10-minute cache for Instagram Apify status (C29)
_INSTAGRAM_STATUS_CACHE = {
    "result": None,
    "cached_at": 0.0
}


@router.post("/influencer/csv")
def audit_influencer_csv(
    file: UploadFile = File(...),
    target_influencer: str = Form("Unknown"),
    current_user: dict = Depends(get_current_active_user)
):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    try:
        content = file.file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")

    # 1 MB size limit (S9)
    if len(content) > 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds the 1 MB limit.")

    try:
        csv_text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File encoding must be UTF-8.")

    try:
        user_id = str(current_user["_id"])
        result = run_audience_audit(csv_text, target_influencer, user_id=user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error processing CSV audit: %s", e)
        raise HTTPException(status_code=500, detail="Internal error processing audit.")


class LiveAuditRequest(BaseModel):
    target_influencer: str
    platform: str = "instagram"
    sample_size: int = Field(10, ge=1, le=50)
    simulate_fallback: bool = False


@router.post("/influencer/live")
def audit_influencer_live(
    request: LiveAuditRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_active_user)
):
    audit_id = str(uuid.uuid4())
    user_id = str(current_user["_id"])

    # Fire off background worker in threadpool (C2)
    background_tasks.add_task(
        run_live_audience_audit,
        request.target_influencer,
        request.platform,
        request.sample_size,
        audit_id,
        user_id,
        request.simulate_fallback
    )

    return {
        "message": "Live audit started",
        "audit_id": audit_id,
        "status": "processing"
    }


@router.get("/instagram/status")
def get_instagram_session_status(
    current_user: dict = Depends(get_current_active_user)
):
    now = time.time()
    # Cache for 10 minutes (600 seconds) to avoid consuming Apify compute units (C29)
    if _INSTAGRAM_STATUS_CACHE["result"] is not None and (now - _INSTAGRAM_STATUS_CACHE["cached_at"] < 600):
        return _INSTAGRAM_STATUS_CACHE["result"]

    status_info = ApifyInstagramCollector.validate_session()
    _INSTAGRAM_STATUS_CACHE["result"] = status_info
    _INSTAGRAM_STATUS_CACHE["cached_at"] = now
    return status_info
