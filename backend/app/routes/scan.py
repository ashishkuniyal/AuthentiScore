from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Response
import uuid

from app.database.mongodb import save_scan_result, scans_collection
from app.routes.auth import get_current_active_user
from fastapi import Depends
from app.routes.auth import get_current_active_user
from fastapi import Depends

from app.models.schemas import (
    ScanRequest,
    ScanResponse,
    ManualProfileRequest,
    CompleteProfileScanResponse,
    AutoScanRequest,
    AutoScanResponse,
)

from app.services.ml_engine import (
    calculate_ml_risk
)

from app.services.collector import (
    validate_profile_url,
    collect_profile,
    create_manual_profile
)

from app.services.feature_engine import (
    extract_features
)

from app.services.nlp_engine import (
    calculate_nlp_rule_score
)

from app.services.risk_engine import (
    calculate_profile_rule_risk,
    calculate_unified_risk,
    build_score_breakdown,
    classify_risk,
    _is_bio_insufficient,
)

from app.services.explainer import (
    generate_ml_explanation
)

from app.services.report_generator import generate_pdf_report
from app.services.network_engine import analyze_network
from app.services.image_engine import analyze_avatar

# ==================================================
# Router
# ==================================================

router = APIRouter(
    prefix="/scan",
    tags=["Scan"]
)


# ==================================================
# Complete Risk Pipeline
# ==================================================

def run_risk_pipeline(
    profile: dict,
    bio: str = ""
):
    """
    Run the complete AuthentiScore pipeline.

    Pipeline:

    Profile
       ↓
    ML Risk
       ↓
    NLP Risk
       ↓
    Rule Risk
       ↓
    Unified Risk
       ↓
    Classification
       ↓
    SHAP Explanation
    """

    # --------------------------------------------------
    # 0. Feature Extraction
    # --------------------------------------------------
    features = extract_features(profile)

    # Core 9 features
    core_features = [k for k in features.keys() if k != "account_age_days"]
    present_count = sum(1 for k in core_features if features[k] is not None)
    data_completeness = round(present_count / len(core_features), 4)
    missing_features = [k for k in core_features if features[k] is None]

    if present_count < 5:
        # Insufficient Data path
        return {
            "features": features,
            "final_score": None,
            "classification": "Insufficient Data",
            "data_completeness": data_completeness,
            "missing_features": missing_features,
            "field_sources": {},
            "platform_coverage": "",
            "score_breakdown": None,
            "risk_components": None,
            "top_ml_factors": None,
            "nlp_signals": None,
            "rule_signals": None,
            "network_signals": None,
            "image_signals": None
        }

    # --------------------------------------------------
    # 1. ML Risk
    # --------------------------------------------------

    ml_risk = calculate_ml_risk(
        features
    )

    # --------------------------------------------------
    # 2. NLP Risk
    # --------------------------------------------------

    nlp_result = calculate_nlp_rule_score(
        bio
    )

    nlp_risk = nlp_result["score"]

    nlp_matches = nlp_result["matches"]

    # --------------------------------------------------
    # 3. Profile Rule Risk
    # --------------------------------------------------

    rule_result = calculate_profile_rule_risk(
        features
    )

    rule_risk = rule_result[
        "profile_rule_risk"
    ]

    # --------------------------------------------------
    # 4. Unified Risk
    # --------------------------------------------------

    # Determine whether bio is too short for NLP (drives weight renormalization)
    nlp_insufficient = _is_bio_insufficient(bio)

    final_score = calculate_unified_risk(
        ml_risk,
        nlp_risk,
        rule_risk,
        nlp_insufficient=nlp_insufficient,
    )

    # Canonical breakdown object — the single source of truth for weights & points
    score_breakdown = build_score_breakdown(
        ml_risk,
        nlp_risk,
        rule_risk,
        nlp_insufficient=nlp_insufficient,
        bio=bio,
    )

    # Collect mock forensics data for audit trail only (not factored into score)
    network_result = analyze_network(
        profile.get("username", "unknown"),
        profile.get("platform", "unknown")
    )
    image_result = analyze_avatar(
        profile.get("profile_url", ""),
        profile.get("has_profile_picture", 1)
    )

    # --------------------------------------------------
    # 7. Classification
    # --------------------------------------------------

    classification = classify_risk(
        final_score
    )

    # --------------------------------------------------
    # 6. SHAP Explanation
    # --------------------------------------------------

    top_ml_factors = generate_ml_explanation(
        profile,
        top_n=3
    )

    # --------------------------------------------------
    # 7. NLP Explanation (keyword + semantic signals)
    # --------------------------------------------------

    # Keyword-matched phrase list (for display)
    matched_phrases = [
        match["matched_text"]
        for match in nlp_matches
    ]

    # Keyword category list (deduplicated, existing behaviour)
    matched_keyword_categories = list(
        dict.fromkeys(
            match["category"]
            for match in nlp_matches
        )
    )

    # Semantic matched categories with similarity scores (new)
    semantic_details          = nlp_result.get("semantic_details", {})
    matched_semantic_cats     = semantic_details.get("matched_categories", [])
    semantic_explanation      = semantic_details.get("explanation", "")

    # --------------------------------------------------
    # 8. Final Result
    # --------------------------------------------------

    return {
        "features": features,
        "final_score":    final_score,

        "classification": classification,
        
        "data_completeness": data_completeness,
        "missing_features": missing_features,
        "field_sources": {},
        "platform_coverage": "",

        # Canonical breakdown — use this; do not recompute weights in the frontend
        "score_breakdown": score_breakdown,

        # Legacy component dict kept for backward-compat with history/analytics routes
        "risk_components": {
            "ml_risk":   ml_risk,
            "nlp_risk":  nlp_risk,
            "rule_risk": rule_risk,
        },

        "top_ml_factors": top_ml_factors,

        "nlp_signals": {
            "nlp_risk":                    nlp_risk,
            "nlp_insufficient":            nlp_insufficient,
            "matched_categories":          matched_keyword_categories,
            "matched_phrases":             matched_phrases,
            "keyword_risk":                nlp_result.get("keyword_risk", 0.0),
            "semantic_risk":               nlp_result.get("semantic_risk", 0.0),
            "hybrid_nlp_risk":             nlp_result.get("hybrid_nlp_risk", nlp_risk),
            "matched_semantic_categories": matched_semantic_cats,
            "semantic_explanation":        semantic_explanation,
            "nlp_model_name":              nlp_result.get("nlp_model_name", ""),
        },

        "rule_signals": rule_result["signals"],

        # Mock forensics kept in response for audit trail but NOT in score
        "network_signals": network_result,
        "image_signals":   image_result,

    }


# ==================================================
# 1. Recent Scans
# ==================================================

@router.get("/recent")
def get_recent_scans(limit: int = 5, current_user: dict = Depends(get_current_active_user)):
    scans = list(
        scans_collection.find(
            {"user_id": str(current_user["_id"])},
            {"_id": 0, "scan_id": 1, "username": 1, "platform": 1, "final_score": 1, "classification": 1, "timestamp": 1}
        ).sort("timestamp", -1).limit(limit)
    )
    
    recent_scans = []
    for s in scans:
        ts = s.get("timestamp")
        if hasattr(ts, "isoformat"):
            ts_str = ts.isoformat()
        else:
            ts_str = str(ts)
            
        score = float(s.get("final_score", 0))
        status = "Authentic" if score < 60 else ("Critical" if score >= 80 else "High Risk")
        
        recent_scans.append({
            "profile": "@" + s.get("username", "unknown"),
            "platform": s.get("platform", "unknown").capitalize(),
            "score": f"{score:.0f}% Fake",
            "date": ts_str,
            "status": status,
            "scan_id": s.get("scan_id")
        })
        
    return recent_scans


# ==================================================
# 2. Basic Test
# ==================================================

@router.get("/test")
def scan_test():

    return {
        "message": "Scan route is working"
    }


# ==================================================
# 2. Existing Feature-Based Scan
# ==================================================

@router.post(
    "",
    response_model=ScanResponse
)
def scan_profile(
    request: ScanRequest
):

    profile = request.profile.model_dump()

    return run_risk_pipeline(
        profile,
        request.bio
    )


# ==================================================
# 3. URL Validation
# ==================================================

@router.post("/validate-url")
def validate_url(
    profile_url: str
):

    return validate_profile_url(
        profile_url
    )


# ==================================================
# 4. Collector Test
# ==================================================

@router.post("/collect-test")
def collect_test(
    profile_url: str
):

    return collect_profile(
        profile_url
    )


# ==================================================
# 5. Feature Extraction Test
# ==================================================

@router.post("/features-test")
def features_test(
    profile_url: str
):

    collected_profile = collect_profile(
        profile_url
    )

    if collected_profile.get(
        "collection_status"
    ) == "failed":

        return collected_profile

    features = extract_features(
        collected_profile
    )

    return {

        "profile": collected_profile,

        "features": features

    }


# ==================================================
# 6. Manual Profile
# ==================================================

@router.post("/manual-profile")
def manual_profile(
    request: ManualProfileRequest
):

    profile = create_manual_profile(

        platform=request.platform,

        profile_url=str(
            request.profile_url
        ),

        username=request.username,

        followers=request.followers,

        following=request.following,

        posts=request.posts,

        bio=request.bio,

        has_profile_picture=(
            request.has_profile_picture
        ),

        is_private=request.is_private

    )

    features = extract_features(
        profile
    )

    return {

        "profile": profile,

        "features": features

    }


# ==================================================
# 7. COMPLETE PROFILE SCAN  (manual fallback endpoint)
# ==================================================

@router.post(
    "/profile-scan",
    response_model=CompleteProfileScanResponse
)
def profile_scan(
    request: ManualProfileRequest,
    current_user: dict = Depends(get_current_active_user)
):

    # --------------------------------------------------
    # 1. Generate unique scan ID
    # --------------------------------------------------

    scan_id = str(
        uuid.uuid4()
    )

    # --------------------------------------------------
    # 2. Create standardized profile
    # --------------------------------------------------

    profile = create_manual_profile(

        platform=request.platform,

        profile_url=str(
            request.profile_url
        ),

        username=request.username,

        followers=request.followers,

        following=request.following,

        posts=request.posts,

        bio=request.bio,

        has_profile_picture=(
            request.has_profile_picture
        ),

        is_private=request.is_private

    )

    # --------------------------------------------------
    # 3. Convert profile → ML features
    # --------------------------------------------------

    features = extract_features(
        profile
    )

    # --------------------------------------------------
    # 4. Run complete risk pipeline
    # --------------------------------------------------

    result = run_risk_pipeline(
        profile,
        request.bio
    )

    # --------------------------------------------------
    # 5. Save prediction to MongoDB
    # --------------------------------------------------

    save_scan_result(

        scan_id=scan_id,

        platform=profile["platform"],

        username=profile["username"],

        profile_url=profile["profile_url"],

        features=features,

        result=result,

        collection_source="user_provided",

        collection_status="success",

        model_name="RandomForest",

        model_version="v1",

        user_id=str(current_user["_id"])

    )

    # --------------------------------------------------
    # 6. Return complete scan
    # --------------------------------------------------

    return {

        "scan_id": scan_id,

        "platform": profile["platform"],

        "username": profile["username"],

        "profile_url": profile["profile_url"],

        "features": features,

        **result

    }


# ==================================================
# 8. AUTOMATED URL-DRIVEN SCAN  (primary endpoint)
# ==================================================

@router.post(
    "/auto",
    response_model=AutoScanResponse,
    summary="Automated URL-driven profile scan",
    description=(
        "Primary scan endpoint. Accepts only a public profile URL. "
        "Automatically attempts permitted profile data collection, "
        "runs the full ML + NLP + SHAP pipeline, persists the result, "
        "and returns a complete AuthentiScore analysis. "
        "If automated collection fails or is partial, the response "
        "contains the partial data so the frontend can show the "
        "manual fallback form pre-filled."
    ),
)
def auto_scan(
    request: AutoScanRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    URL → automated collection → feature extraction →
    NLP + ML → risk → SHAP → MongoDB → complete result.

    The caller only provides a public profile URL.
    """

    profile_url = str(request.profile_url)

    # --------------------------------------------------
    # 1. Generate unique scan ID
    # --------------------------------------------------

    scan_id = str(uuid.uuid4())

    # --------------------------------------------------
    # 2. Validate URL + detect platform
    # --------------------------------------------------

    validation = validate_profile_url(profile_url)

    if not validation["valid"]:
        raise HTTPException(
            status_code=422,
            detail=validation["error"] or "Unsupported social media platform.",
        )

    # --------------------------------------------------
    # 3. Attempt automated permitted collection
    # --------------------------------------------------

    collected = collect_profile(profile_url)

    # Build collection metadata for audit trail
    collection_metadata = {
        "source":           collected.get("collection_source", "none"),
        "status":           collected.get("collection_status", "failed"),
        "timestamp":        collected.get("collected_at")
                            or datetime.now(timezone.utc).isoformat(),
        "fields_collected": collected.get("fields_collected", []),
    }

    # --------------------------------------------------
    # 4. Convert collected profile → ML features
    # --------------------------------------------------

    features = extract_features(collected)

    # --------------------------------------------------
    # 5. Run complete risk pipeline
    # --------------------------------------------------

    bio = collected.get("bio") or ""

    result = run_risk_pipeline(collected, bio)

    # --------------------------------------------------
    # 6. Save to MongoDB (with collection audit trail)
    # --------------------------------------------------

    username = collected.get("username") or "unknown"

    save_scan_result(
        scan_id=scan_id,
        platform=collected.get("platform", validation["platform"]),
        username=username,
        profile_url=profile_url,
        features=features,
        result=result,
        collection_source=collection_metadata["source"],
        collection_status=collection_metadata["status"],
        model_name="RandomForest",
        model_version="v1",
        collection_metadata=collection_metadata,
        user_id=str(current_user["_id"])
    )

    # --------------------------------------------------
    # 7. Broadcast WebSocket Notification
    # --------------------------------------------------
    try:
        from app.main import manager
        import asyncio
        asyncio.create_task(manager.broadcast({
            "type": "SCAN_COMPLETE",
            "message": f"Analysis complete for @{username}",
            "risk_score": result["final_score"],
            "platform": collected.get("platform", validation["platform"]),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }))
    except Exception:
        pass

    # --------------------------------------------------
    # 8. Return complete scan result
    # --------------------------------------------------

    return {
        "scan_id":       scan_id,
        "platform":      collected.get("platform", validation["platform"]),
        "username":      username,
        "profile_url":   profile_url,
        "display_name":  collected.get("display_name"),
        "collected_bio": bio or None,
        "profile":       collected,
        "features":      features,
        **result,
        "collection":    collection_metadata,
    }


# ==================================================
# 9. PDF Report Generation
# ==================================================

@router.get("/{scan_id}/report.pdf")
def download_pdf_report(scan_id: str):
    scan_data = scans_collection.find_one({"scan_id": scan_id}, {"_id": 0})
    if not scan_data:
        raise HTTPException(status_code=404, detail="Scan not found.")

    from app.services.report_generator import generate_pdf_report
    pdf_bytes = generate_pdf_report(scan_data)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="authentiscore_report_{scan_id}.pdf"'}
    )