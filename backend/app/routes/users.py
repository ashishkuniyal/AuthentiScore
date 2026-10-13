"""
AuthentiScore — User Management Router
=======================================

Implements:
  - S3: Unique username check (409 on conflict), email cannot be changed
  - S10: ObjectId validation & 404 on API key revocation
  - C2: Sync def handlers to avoid blocking event loop with PyMongo
  - C4 / C32: Accurate user stats without fake counts
  - C33: API key management
  - C36: Python hygiene (clean imports)
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import List

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.database.mongodb import db, scans_collection, users_collection, bulk_jobs_collection
from app.models.user_schemas import (
    ActivityLogResponse,
    ApiKeyCreate,
    ApiKeyResponse,
    UserNotificationsUpdate,
    UserPreferencesUpdate,
    UserProfileUpdate,
)
from app.routes.auth import get_current_active_user, log_activity

router = APIRouter()


@router.put("/profile")
def update_profile(
    profile_data: UserProfileUpdate,
    current_user: dict = Depends(get_current_active_user),
):
    update_data = {k: v for k, v in profile_data.model_dump().items() if v is not None}

    # S3: Enforce unique username
    if "username" in update_data:
        new_username = update_data["username"].strip()
        existing = users_collection.find_one({
            "username": new_username,
            "_id": {"$ne": current_user["_id"]},
        })
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username is already taken.",
            )
        update_data["username"] = new_username

    update_data["updatedAt"] = datetime.now(timezone.utc)

    users_collection.update_one(
        {"_id": current_user["_id"]},
        {"$set": update_data},
    )
    log_activity(str(current_user["_id"]), "Profile information updated")
    return {"success": True, "message": "Profile updated successfully"}


@router.put("/preferences")
def update_preferences(
    prefs: UserPreferencesUpdate,
    current_user: dict = Depends(get_current_active_user),
):
    update_data = {
        f"preferences.{k}": v
        for k, v in prefs.model_dump().items()
        if v is not None
    }
    if update_data:
        users_collection.update_one({"_id": current_user["_id"]}, {"$set": update_data})
        log_activity(str(current_user["_id"]), "Preferences updated")
    return {"success": True, "message": "Preferences updated successfully"}


@router.put("/notifications")
def update_notifications(
    notifs: UserNotificationsUpdate,
    current_user: dict = Depends(get_current_active_user),
):
    update_data = {
        f"notifications.{k}": v
        for k, v in notifs.model_dump().items()
        if v is not None
    }
    if update_data:
        users_collection.update_one({"_id": current_user["_id"]}, {"$set": update_data})
        log_activity(str(current_user["_id"]), "Notification settings updated")
    return {"success": True, "message": "Notifications updated successfully"}


@router.get("/activity", response_model=List[ActivityLogResponse])
def get_activity(current_user: dict = Depends(get_current_active_user)):
    logs = list(
        db["activity_logs"]
        .find({"user_id": str(current_user["_id"])}, limit=50)
        .sort("timestamp", -1)
    )
    for log in logs:
        log["id"] = str(log["_id"])
    return logs


@router.get("/stats")
def get_user_stats(current_user: dict = Depends(get_current_active_user)):
    """
    C4, C32: Return real per-user statistics with risk band matching.
    """
    user_id = str(current_user["_id"])

    total_scans = scans_collection.count_documents({"user_id": user_id})
    fake_scans = scans_collection.count_documents({
        "user_id": user_id,
        "classification": {"$in": ["High Risk", "Very High Risk", "high", "very_high"]},
    })
    authentic_scans = scans_collection.count_documents({
        "user_id": user_id,
        "classification": {"$in": ["Low Risk", "low"]},
    })

    # C32: Compute bulk analyzed from real bulk_jobs
    bulk_jobs = list(bulk_jobs_collection.find({"user_id": user_id}, {"processed": 1, "total": 1}))
    bulk_analyzed = sum(j.get("processed", j.get("total", 0)) for j in bulk_jobs)

    # C32: Count PDF reports generated from user doc or activity logs
    user_doc = users_collection.find_one({"_id": current_user["_id"]}) or current_user
    reports_count = user_doc.get("reportsGenerated")
    if reports_count is None:
        reports_count = db["activity_logs"].count_documents({
            "user_id": user_id,
            "action": "PDF report downloaded",
        })

    return {
        "totalScans": total_scans,
        "fakeProfiles": fake_scans,
        "authenticProfiles": authentic_scans,
        "reportsGenerated": reports_count,
        "bulkProfilesAnalyzed": bulk_analyzed,
    }


@router.get("/billing")
def get_billing_info(current_user: dict = Depends(get_current_active_user)):
    user_id = str(current_user["_id"])
    scans_used = scans_collection.count_documents({"user_id": user_id})

    # C32: Label limits clearly as not strictly enforced
    return {
        "plan": current_user.get("plan", "Free"),
        "price": "$29/month" if current_user.get("plan") == "Pro" else "$0/month",
        "limits_enforced": False,
        "usage": {
            "scans": {"used": scans_used, "limit": 500, "enforced": False},
            "bulk": {"used": 0, "limit": 5000, "enforced": False},
            "api": {"used": 0, "limit": 10000, "enforced": False},
        },
    }


@router.get("/api-keys", response_model=List[ApiKeyResponse])
def get_api_keys(current_user: dict = Depends(get_current_active_user)):
    keys = list(
        db["api_keys"]
        .find({"user_id": str(current_user["_id"])})
        .sort("created_at", -1)
    )
    for key in keys:
        key["id"] = str(key["_id"])
    return keys


@router.post("/api-keys")
def create_api_key(
    data: ApiKeyCreate,
    current_user: dict = Depends(get_current_active_user),
):
    raw_key = f"auth_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    new_key = {
        "user_id": str(current_user["_id"]),
        "name": data.name,
        "key_hash": key_hash,
        "key_hint": f"{raw_key[:8]}...{raw_key[-4:]}",
        "created_at": datetime.now(timezone.utc),
        "status": "Active",
    }

    res = db["api_keys"].insert_one(new_key)
    log_activity(str(current_user["_id"]), "API key created", f"Key: {data.name}")

    return {
        "success": True,
        "message": "API key created successfully. This is the ONLY time you will see the full key.",
        "api_key": raw_key,
        "id": str(res.inserted_id),
    }


@router.delete("/api-keys/{key_id}")
def revoke_api_key(
    key_id: str,
    current_user: dict = Depends(get_current_active_user),
):
    # S10: Validate ObjectId
    if not ObjectId.is_valid(key_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid API key ID format.",
        )

    res = db["api_keys"].update_one(
        {"_id": ObjectId(key_id), "user_id": str(current_user["_id"])},
        {"$set": {"status": "Revoked"}},
    )

    if res.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found.",
        )

    log_activity(str(current_user["_id"]), "API key revoked")
    return {"success": True, "message": "API key revoked successfully"}
