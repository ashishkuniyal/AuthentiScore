"""
AuthentiScore — Admin Routes
=============================

Provides operational monitoring, feedback analytics, and aggregate metrics.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any

from app.database.mongodb import db, scans_collection
from app.routes.auth import get_current_active_user

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/metrics")
def get_admin_metrics(current_user: dict = Depends(get_current_active_user)):
    """
    Returns administrative metrics regarding scan performance, feedback agreement,
    and user satisfaction metrics.
    """
    try:
        total_scans = scans_collection.count_documents({})
    except Exception:
        total_scans = 0

    feedback_docs = []
    try:
        if hasattr(db, "scan_feedback"):
            feedback_docs = list(db.scan_feedback.find({}))
    except Exception:
        pass

    total_feedback = len(feedback_docs)
    agreement_count = 0
    dispute_count = 0
    verdict_breakdown = {"real": 0, "fake": 0, "bot": 0}

    for f in feedback_docs:
        u_verdict = (f.get("user_verdict") or "").lower()
        if u_verdict in verdict_breakdown:
            verdict_breakdown[u_verdict] += 1
            
        sys_score = f.get("system_score")
        if sys_score is not None:
            sys_is_fake = sys_score >= 50
            user_is_fake = u_verdict in ("fake", "bot")
            if sys_is_fake == user_is_fake:
                agreement_count += 1
            else:
                dispute_count += 1

    agreement_rate = round(agreement_count / total_feedback, 4) if total_feedback > 0 else 1.0

    return {
        "total_scans": total_scans,
        "total_feedback": total_feedback,
        "agreement_count": agreement_count,
        "dispute_count": dispute_count,
        "agreement_rate": agreement_rate,
        "verdict_breakdown": verdict_breakdown,
        "status": "operational"
    }
