"""
AuthentiScore — Analytics Router
=================================

Implements:
  - S4: Authenticated user scans only
  - S6: No exception/URI leak in /database-test
  - C4: Safe handling of final_score=None ("Insufficient Data")
  - C5: Central risk classification & risk_level keys
  - C32: Accurate metrics without fabricated active_users
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.risk_levels import is_suspicious, risk_key
from app.database.mongodb import scans_collection
from app.routes.auth import get_current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
)


# ============================================================
# Database Connection Test (S6)
# ============================================================

@router.get("/database-test")
def database_test(current_user: dict = Depends(get_current_active_user)):
    try:
        scans_collection.database.client.admin.command("ping")
        return {"mongodb_connected": True}
    except Exception as exc:
        logger.error("Database test ping failed: %s", exc)
        return {"mongodb_connected": False, "error": "Database connection failed"}


# ============================================================
# Dashboard Summary (C4, C5, C32)
# ============================================================

@router.get("/dashboard-summary")
def dashboard_summary(current_user: dict = Depends(get_current_active_user)):
    user_id = str(current_user["_id"])
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    scans = list(
        scans_collection.find(
            {"timestamp": {"$gte": cutoff}, "user_id": user_id},
            {"_id": 0, "final_score": 1, "classification": 1, "timestamp": 1},
        )
    )

    total_scans = len(scans)
    fake_count = 0
    authentic_count = 0
    insufficient_count = 0
    daily_volume = defaultdict(int)
    daily_fake = defaultdict(int)
    daily_authentic = defaultdict(int)

    for scan in scans:
        final_score = scan.get("final_score")
        classification = scan.get("classification") or ""

        is_fake = False
        is_auth = False
        if final_score is None or "insufficient" in classification.lower():
            insufficient_count += 1
        elif is_suspicious(final_score):
            fake_count += 1
            is_fake = True
        else:
            authentic_count += 1
            is_auth = True

        ts = scan.get("timestamp")
        if ts:
            try:
                date_key = ts.strftime("%Y-%m-%d")
                daily_volume[date_key] += 1
                if is_fake:
                    daily_fake[date_key] += 1
                elif is_auth:
                    daily_authentic[date_key] += 1
            except AttributeError:
                pass

    scan_volume = []
    for i in range(29, -1, -1):
        d = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
        scan_volume.append({
            "date": d,
            "scans": daily_volume.get(d, 0),
            "fake": daily_fake.get(d, 0),
            "authentic": daily_authentic.get(d, 0),
        })

    return {
        "total_scans": total_scans,
        "fake_profiles": fake_count,
        "authentic_profiles": authentic_count,
        "insufficient_data": insufficient_count,
        "scan_volume": scan_volume,
    }


# ============================================================
# Analytics Summary (C4, C5, C32)
# ============================================================

@router.get("/summary")
def analytics_summary(
    days: Optional[int] = Query(None, description="Number of days to look back"),
    current_user: dict = Depends(get_current_active_user),
):
    query = {"user_id": str(current_user["_id"])}
    if days is not None and isinstance(days, int):
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
                "risk_components": 1,
            },
        )
    )

    total_scans = len(scans)

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
                "very_high": 0,
                "insufficient_data": 0,
            },
            "platform_counts": {},
            "average_risk_components": {
                "ml_risk": 0,
                "nlp_risk": 0,
                "rule_risk": 0,
            },
            "recent_trend": [],
            "top_risky_scans": [],
        }

    valid_scores = []
    classification_counts = {
        "low": 0,
        "medium": 0,
        "high": 0,
        "very_high": 0,
        "insufficient_data": 0,
    }
    platform_counts = defaultdict(int)
    component_totals = {"ml_risk": 0.0, "nlp_risk": 0.0, "rule_risk": 0.0}
    component_counts = {"ml_risk": 0, "nlp_risk": 0, "rule_risk": 0}
    daily_counts = defaultdict(int)

    for scan in scans:
        final_score = scan.get("final_score")
        classification = scan.get("classification") or ""
        rkey = risk_key(classification)

        if final_score is not None:
            valid_scores.append(float(final_score))
            if rkey in classification_counts:
                classification_counts[rkey] += 1
        else:
            classification_counts["insufficient_data"] += 1

        platform = str(scan.get("platform", "unknown")).strip().lower()
        platform_counts[platform] += 1

        components = scan.get("risk_components") or {}
        for comp in ("ml_risk", "nlp_risk", "rule_risk"):
            val = components.get(comp)
            if val is not None:
                component_totals[comp] += float(val)
                component_counts[comp] += 1

        timestamp = scan.get("timestamp")
        if timestamp is not None:
            try:
                date_key = timestamp.strftime("%Y-%m-%d")
                daily_counts[date_key] += 1
            except AttributeError:
                pass

    recent_trend = [
        {"date": d, "count": daily_counts[d]}
        for d in sorted(daily_counts.keys())[-7:]
    ]

    # Top risky scans: exclude None scores (C4) and deduplicate by (username, platform)
    scored_scans = [s for s in scans if s.get("final_score") is not None]
    sorted_scans = sorted(
        scored_scans,
        key=lambda s: float(s["final_score"]),
        reverse=True,
    )

    seen_pairs = set()
    uniq = []
    for s in sorted_scans:
        uname = (s.get("username") or "").strip().lower()
        plat = (s.get("platform") or "").strip().lower()
        key = (uname, plat)
        if key not in seen_pairs:
            seen_pairs.add(key)
            uniq.append(s)

    top_risky_scans = []
    for s in uniq[:5]:
        ts = s.get("timestamp")
        cls = s.get("classification") or ""
        top_risky_scans.append({
            "scan_id": s.get("scan_id"),
            "username": s.get("username"),
            "platform": s.get("platform"),
            "final_score": s.get("final_score"),
            "classification": cls,
            "risk_level": risk_key(cls),
            "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else ts,
        })

    avg_score = (sum(valid_scores) / len(valid_scores)) if valid_scores else 0
    max_score = max(valid_scores) if valid_scores else 0
    min_score = min(valid_scores) if valid_scores else 0

    return {
        "total_scans": total_scans,
        "average_risk_score": round(avg_score, 1),
        "highest_risk_score": round(max_score, 1),
        "lowest_risk_score": round(min_score, 1),
        "classification_counts": classification_counts,
        "platform_counts": dict(
            sorted(platform_counts.items(), key=lambda item: item[1], reverse=True)
        ),
        "average_risk_components": {
            comp: round(
                component_totals[comp] / component_counts[comp], 1
            ) if component_counts[comp] > 0 else 0
            for comp in ("ml_risk", "nlp_risk", "rule_risk")
        },
        "recent_trend": recent_trend,
        "top_risky_scans": top_risky_scans,
    }