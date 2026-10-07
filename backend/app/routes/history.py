from fastapi import APIRouter, Depends
from app.database.mongodb import scans_collection
from app.routes.auth import get_current_active_user

router = APIRouter(
    prefix="/history",
    tags=["History"]
)


# ==================================================
# Get Scan History
# ==================================================

@router.get("")
def get_scan_history(current_user: dict = Depends(get_current_active_user)):

    scans = scans_collection.find(
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
            "classification": 1
        }
    ).sort(
        "timestamp",
        -1
    )

    return list(scans)