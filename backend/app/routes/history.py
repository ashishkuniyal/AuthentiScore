"""
AuthentiScore — Scan History Router
====================================

Implements:
  - S4: Authenticated user scans only
  - C5: Includes central risk_level key
  - C34: Query params limit (default 500, max 1000) and skip
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query

from app.core.risk_levels import risk_key
from app.database.mongodb import scans_collection
from app.routes.auth import get_current_active_user

router = APIRouter(
    prefix="/history",
    tags=["History"],
)


@router.get("", response_model=List[dict])
def get_scan_history(
    limit: int = Query(500, ge=1, le=1000),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_active_user),
):
    scans = (
        scans_collection.find(
            {"user_id": str(current_user["_id"])},
            {
                "_id": 0,
                "scan_id": 1,
                "timestamp": 1,
                "platform": 1,
                "username": 1,
                "profile_url": 1,
                "model_name": 1,
                "model_version": 1,
                "final_score": 1,
                "classification": 1,
            },
        )
        .sort("timestamp", -1)
        .skip(skip)
        .limit(limit)
    )

    result = []
    for s in scans:
        classification = s.get("classification") or "Unknown"
        s["risk_level"] = risk_key(classification)
        # Format timestamp if datetime
        if hasattr(s.get("timestamp"), "isoformat"):
            s["timestamp"] = s["timestamp"].isoformat()
        result.append(s)

    return result