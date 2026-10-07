from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query, Depends
from typing import Optional
from app.routes.auth import get_current_active_user

from app.database.mongodb import scans_collection


router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"]
)


# ============================================================
# Database Connection Test
# ============================================================

@router.get("/database-test")
def database_test():

    try:

        scans_collection.database.client.admin.command("ping")

        return {
            "mongodb_connected": True
        }

    except Exception as exc:

        return {
            "mongodb_connected": False,
            "error": str(exc)
        }


# ============================================================
# Dashboard Summary
# ============================================================

@router.get("/dashboard-summary")
def dashboard_summary(current_user: dict = Depends(get_current_active_user)):
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    scans = list(
        scans_collection.find(
            {"timestamp": {"$gte": cutoff}, "user_id": str(current_user["_id"])},
            {"_id": 0, "final_score": 1, "classification": 1, "timestamp": 1}
        )
    )

    total_scans = len(scans)
    fake_count = 0
    authentic_count = 0
    daily_volume = defaultdict(int)

    for scan in scans:
        score = float(scan.get("final_score", 0) or 0)
        cls = str(scan.get("classification", "")).lower()
        if score >= 60 or cls in ["high", "very_high", "high risk", "very high risk"]:
            fake_count += 1
        else:
            authentic_count += 1
            
        ts = scan.get("timestamp")
        if ts:
            try:
                date_key = ts.strftime("%Y-%m-%d")
                daily_volume[date_key] += 1
            except AttributeError:
                pass

    scan_volume = []
    for i in range(29, -1, -1):
        d = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
        scan_volume.append({"date": d, "scans": daily_volume.get(d, 0)})

    # Mock active users since there's no auth/users collection defined
    return {
        "total_scans": total_scans,
        "fake_profiles": fake_count,
        "authentic_profiles": authentic_count,
        "active_users": 145, 
        "scan_volume": scan_volume
    }


# ============================================================
# Analytics Summary
# ============================================================

@router.get("/summary")
def analytics_summary(
    days: Optional[int] = Query(None, description="Number of days to look back"),
    current_user: dict = Depends(get_current_active_user)
):
    query = {"user_id": str(current_user["_id"])}
    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        query["timestamp"] = {"$gte": cutoff}

    scans = list(
        scans_collection.find(
            query,
            {
                "_id": 0,
                "scan_id": 1,
                "username": 1,
                "platform": 1,
                "timestamp": 1,
                "final_score": 1,
                "classification": 1,
                "risk_components": 1
            }
        )
    )

    total_scans = len(scans)

    # --------------------------------------------------------
    # No scans
    # --------------------------------------------------------

    if total_scans == 0:

        return {
            "total_scans": 0,
            "average_risk_score": 0,
            "highest_risk_score": 0,
            "lowest_risk_score": 0,
            "classification_counts": {
                "low": 0,
                "medium": 0,
                "high": 0,
                "very_high": 0
            },
            "platform_counts": {},
            "average_risk_components": {
                "ml_risk": 0,
                "nlp_risk": 0,
                "rule_risk": 0
            },
            "recent_trend": [],
            "top_risky_scans": []
        }


    # ========================================================
    # Containers
    # ========================================================

    scores = []
    classification_counts = {
        "low": 0,
        "medium": 0,
        "high": 0,
        "very_high": 0
    }
    platform_counts = defaultdict(int)
    component_totals = {
        "ml_risk": 0.0,
        "nlp_risk": 0.0,
        "rule_risk": 0.0
    }
    daily_counts = defaultdict(int)

    # ========================================================
    # Process scans
    # ========================================================

    for scan in scans:

        # ----------------------------------------------------
        # Risk score
        # ----------------------------------------------------
        score = float(scan.get("final_score", 0) or 0)
        scores.append(score)

        # ----------------------------------------------------
        # Classification
        # ----------------------------------------------------
        classification = str(scan.get("classification", "")).strip().lower()

        if classification in {"low", "low risk"}:
            classification_counts["low"] += 1
        elif classification in {"medium", "medium risk"}:
            classification_counts["medium"] += 1
        elif classification in {"high", "high risk"}:
            classification_counts["high"] += 1
        elif classification in {"very high", "very high risk", "very_high"}:
            classification_counts["very_high"] += 1
        else:
            if score < 30:
                classification_counts["low"] += 1
            elif score < 60:
                classification_counts["medium"] += 1
            elif score < 80:
                classification_counts["high"] += 1
            else:
                classification_counts["very_high"] += 1

        # ----------------------------------------------------
        # Platform
        # ----------------------------------------------------
        platform = str(scan.get("platform", "unknown")).strip().lower()
        platform_counts[platform] += 1

        # ----------------------------------------------------
        # Risk components
        # ----------------------------------------------------
        components = scan.get("risk_components", {}) or {}
        component_totals["ml_risk"] += float(components.get("ml_risk", 0) or 0)
        component_totals["nlp_risk"] += float(components.get("nlp_risk", 0) or 0)
        component_totals["rule_risk"] += float(components.get("rule_risk", 0) or 0)

        # ----------------------------------------------------
        # Daily trend
        # ----------------------------------------------------
        timestamp = scan.get("timestamp")
        if timestamp is not None:
            try:
                date_key = timestamp.strftime("%Y-%m-%d")
                daily_counts[date_key] += 1
            except AttributeError:
                pass

    # ========================================================
    # Recent 7-day trend
    # ========================================================
    recent_trend = [
        {
            "date": date,
            "count": daily_counts[date]
        }
        for date in sorted(daily_counts.keys())[-7:]
    ]

    # ========================================================
    # Top 5 Riskiest Scans
    # ========================================================
    sorted_scans = sorted(scans, key=lambda s: float(s.get("final_score", 0)), reverse=True)
    top_risky_scans = []
    for s in sorted_scans[:5]:
        ts = s.get("timestamp")
        top_risky_scans.append({
            "scan_id": s.get("scan_id"),
            "username": s.get("username"),
            "platform": s.get("platform"),
            "final_score": s.get("final_score"),
            "classification": s.get("classification"),
            "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else ts
        })

    # ========================================================
    # Final response
    # ========================================================
    return {
        "total_scans": total_scans,
        "average_risk_score": (sum(scores) / total_scans),
        "highest_risk_score": max(scores),
        "lowest_risk_score": min(scores),
        "classification_counts": classification_counts,
        "platform_counts": dict(sorted(platform_counts.items(), key=lambda item: item[1], reverse=True)),
        "average_risk_components": {
            key: value / total_scans
            for key, value in component_totals.items()
        },
        "recent_trend": recent_trend,
        "top_risky_scans": top_risky_scans
    }