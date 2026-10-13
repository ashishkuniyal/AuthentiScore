import os
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Response, Depends

from app.database.mongodb import save_scan_result, scans_collection, db
from app.routes.auth import get_current_active_user
from app.models.schemas import (
    ScanRequest,
    ScanResponse,
    ManualProfileRequest,
    CompleteProfileScanResponse,
    AutoScanRequest,
    AutoScanResponse,
    ScanFeedbackRequest,
    ScanJobRequest,
    ManualCompletionRequest,
)

from app.services.url_normalizer import normalize_profile_input
from app.services.scan_manager import (
    create_scan_job,
    get_job_status,
    cancel_job,
    get_cached_scan,
)
from app.services.ml_engine import calculate_ml_risk

from app.services.collector import (
    validate_profile_url,
    collect_profile,
    create_manual_profile,
)
from app.services.feature_engine import extract_features
from app.services.nlp_engine import calculate_nlp_rule_score
from app.services.risk_engine import (
    calculate_profile_rule_risk,
    calculate_unified_risk,
    build_score_breakdown,
    _is_bio_insufficient,
)
from app.core.risk_levels import classify_risk, risk_key
from app.services.explainer import generate_ml_explanation
from app.services.report_generator import generate_pdf_report
from app.services.network_engine import analyze_network
from app.services.image_engine import analyze_avatar
from app.services.model_store import MODEL_NAME, MODEL_VERSION
from app.core.ws import notify_user_threadsafe
from app.services.score_composer import (
    is_automation_declared,
    calculate_scan_confidence,
    determine_account_type,
    build_unified_reasons,
)


logger = logging.getLogger(__name__)

# ==================================================
# Router
# ==================================================

router = APIRouter(
    prefix="/scan",
    tags=["Scan"]
)

# Minimum observed features required for scoring (D11)
MIN_OBSERVED = 4
REQUIRED_OBSERVED = {"followers", "following"}
OBSERVED_KEYS = ["followers", "following", "posts", "bio_length", "has_profile_picture", "is_private"]


# ==================================================
# Complete Risk Pipeline
# ==================================================

def run_risk_pipeline(
    profile: dict,
    bio: str = ""
):
    """
    Run the complete AuthentiScore pipeline.
    Profile -> ML Risk -> NLP Risk -> Rule Risk -> Unified Risk -> Classification -> SHAP
    """
    profile_data = {**profile}
    if bio and "bio" not in profile_data:
        profile_data["bio"] = bio

    # --------------------------------------------------
    # 0. Feature Extraction
    # --------------------------------------------------
    features = extract_features(profile_data)

    # Observed inputs check (D11 / C7)
    observed_present = [k for k in OBSERVED_KEYS if features.get(k) is not None]
    has_required = features.get("followers") is not None and features.get("following") is not None
    missing_observed = [k for k in OBSERVED_KEYS if features.get(k) is None]
    data_completeness = round(len(observed_present) / len(OBSERVED_KEYS), 4)

    # Coverage & Field Sources (C9)
    platform = (profile_data.get("platform") or "").lower()
    if platform and platform != "instagram":
        platform_coverage = f"Model trained on Instagram data; results for {platform} are indicative only."
    else:
        platform_coverage = "Model trained on Instagram data."

    field_sources = {}
    source = profile_data.get("collection_source", "observed")
    for f in observed_present:
        field_sources[f] = source

    if not (has_required and len(observed_present) >= MIN_OBSERVED):
        # Insufficient Data path
        confidence = calculate_scan_confidence(
            profile_data,
            data_completeness=data_completeness,
            ml_risk=None,
            nlp_insufficient=True,
            platform=platform,
        )
        return {
            "features": features,
            "final_score": None,
            "classification": "Insufficient Data",
            "data_completeness": data_completeness,
            "missing_features": missing_observed,
            "field_sources": field_sources,
            "platform_coverage": platform_coverage,
            "confidence": confidence,
            "abstain": True,
            "model_applicable": False,
            "account_type": "uncertain",
            "reasons": [],
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
    ml_risk = calculate_ml_risk(features)

    # --------------------------------------------------
    # 2. NLP Risk
    # --------------------------------------------------
    effective_bio = bio or profile_data.get("bio", "") or ""
    nlp_result = calculate_nlp_rule_score(effective_bio)
    nlp_risk = nlp_result["score"]
    nlp_matches = nlp_result["matches"]

    # --------------------------------------------------
    # 3. Profile Rule Risk
    # --------------------------------------------------
    rule_result = calculate_profile_rule_risk(features)
    rule_risk = rule_result["profile_rule_risk"]

    # --------------------------------------------------
    # 4. Unified Risk
    # --------------------------------------------------
    nlp_insufficient = _is_bio_insufficient(effective_bio)
    final_score = calculate_unified_risk(
        ml_risk,
        nlp_risk,
        rule_risk,
        nlp_insufficient=nlp_insufficient,
    )

    # Canonical breakdown object
    score_breakdown = build_score_breakdown(
        ml_risk,
        nlp_risk,
        rule_risk,
        nlp_insufficient=nlp_insufficient,
        bio=effective_bio,
    )

    # --------------------------------------------------
    # 5. Simulated Forensics (C10 / D3)
    # --------------------------------------------------
    enable_simulated = os.getenv("ENABLE_SIMULATED_FORENSICS", "false").lower() == "true"
    if enable_simulated:
        network_result = analyze_network(
            profile_data.get("username", "unknown"),
            profile_data.get("platform", "unknown")
        )
        image_result = analyze_avatar(
            profile_data.get("profile_url", ""),
            profile_data.get("has_profile_picture", 1)
        )
        if network_result:
            network_result["simulated"] = True
            network_result["disclaimer"] = "Simulated demonstration forensics"
        if image_result:
            image_result["simulated"] = True
            image_result["disclaimer"] = "Simulated demonstration forensics"
    else:
        network_result = None
        image_result = None

    # --------------------------------------------------
    # 6. Classification & Declared Bot Handling (A7)
    # --------------------------------------------------
    is_declared = is_automation_declared(profile_data, effective_bio)
    if is_declared:
        classification = "Automated (Declared)"
        account_type = "automated_declared"
    else:
        classification = classify_risk(final_score)
        account_type = determine_account_type(final_score, is_declared_bot=False, abstain=False)

    confidence = calculate_scan_confidence(
        profile_data,
        data_completeness=data_completeness,
        ml_risk=ml_risk,
        nlp_insufficient=nlp_insufficient,
        platform=platform,
    )
    model_applicable = (platform in ("", "instagram")) and (data_completeness >= 0.5)

    # --------------------------------------------------
    # 7. SHAP Explanation
    # --------------------------------------------------
    top_ml_factors = generate_ml_explanation(profile_data, top_n=3)

    # --------------------------------------------------
    # 8. NLP Explanation
    # --------------------------------------------------
    matched_phrases = [match["matched_text"] for match in nlp_matches]
    matched_keyword_categories = list(dict.fromkeys(match["category"] for match in nlp_matches))
    semantic_details = nlp_result.get("semantic_details", {})
    matched_semantic_cats = semantic_details.get("matched_categories", [])
    semantic_explanation = semantic_details.get("explanation", "")

    nlp_signals_dict = {
        "nlp_risk": nlp_risk,
        "nlp_insufficient": nlp_insufficient,
        "matched_categories": matched_keyword_categories,
        "matched_phrases": matched_phrases,
        "keyword_risk": nlp_result.get("keyword_risk", 0.0),
        "semantic_risk": nlp_result.get("semantic_risk", 0.0),
        "hybrid_nlp_risk": nlp_result.get("hybrid_nlp_risk", nlp_risk),
        "matched_semantic_categories": matched_semantic_cats,
        "semantic_explanation": semantic_explanation,
        "nlp_model_name": nlp_result.get("nlp_model_name", ""),
    }

    # --------------------------------------------------
    # 9. Unified Reasons (A8)
    # --------------------------------------------------
    reasons = build_unified_reasons(top_ml_factors, rule_result["signals"], nlp_signals_dict)

    # --------------------------------------------------
    # 10. Final Result
    # --------------------------------------------------
    return {
        "features": features,
        "final_score": final_score,
        "classification": classification,
        "data_completeness": data_completeness,
        "missing_features": missing_observed,
        "field_sources": field_sources,
        "platform_coverage": platform_coverage,
        "confidence": confidence,
        "abstain": False,
        "model_applicable": model_applicable,
        "account_type": account_type,
        "reasons": reasons,
        "score_breakdown": score_breakdown,
        "risk_components": {
            "ml_risk": ml_risk,
            "nlp_risk": nlp_risk,
            "rule_risk": rule_risk,
        },
        "top_ml_factors": top_ml_factors,
        "nlp_signals": nlp_signals_dict,
        "rule_signals": rule_result["signals"],
        "network_signals": network_result,
        "image_signals": image_result,
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

        final_score = s.get("final_score")
        if final_score is None:
            status = "Insufficient Data"
            score_str = "N/A"
            r_key = "insufficient_data"
        else:
            score_val = float(final_score)
            score_str = f"{score_val:.0f}% Fake"
            status = classify_risk(score_val)
            r_key = risk_key(status)

        recent_scans.append({
            "profile": "@" + s.get("username", "unknown"),
            "platform": s.get("platform", "unknown").capitalize(),
            "score": score_str,
            "date": ts_str,
            "status": status,
            "risk_level": r_key,
            "scan_id": s.get("scan_id")
        })

    return recent_scans


# ==================================================
# 2. Basic Test
# ==================================================

@router.get("/test")
def scan_test():
    return {"message": "Scan route is working"}


# ==================================================
# 3. Existing Feature-Based Scan
# ==================================================

@router.post(
    "",
    response_model=ScanResponse
)
def scan_profile(
    request: ScanRequest,
    current_user: dict = Depends(get_current_active_user)
):
    profile = request.profile.model_dump()
    return run_risk_pipeline(profile, request.bio)


# ==================================================
# 4. URL Validation
# ==================================================

@router.post("/validate-url")
def validate_url(
    profile_url: str,
    current_user: dict = Depends(get_current_active_user)
):
    return validate_profile_url(profile_url)


# ==================================================
# 5. Debug Endpoints (gated behind ENABLE_DEBUG_ENDPOINTS)
# ==================================================

@router.post("/collect-test")
def collect_test(
    profile_url: str,
    current_user: dict = Depends(get_current_active_user)
):
    if os.getenv("ENABLE_DEBUG_ENDPOINTS", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Debug endpoints not enabled.")
    return collect_profile(profile_url)


@router.post("/features-test")
def features_test(
    profile_url: str,
    current_user: dict = Depends(get_current_active_user)
):
    if os.getenv("ENABLE_DEBUG_ENDPOINTS", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Debug endpoints not enabled.")
    collected_profile = collect_profile(profile_url)
    if collected_profile.get("collection_status") == "failed":
        return collected_profile
    features = extract_features(collected_profile)
    return {
        "profile": collected_profile,
        "features": features
    }


# ==================================================
# 6. Manual Profile
# ==================================================

@router.post("/manual-profile")
def manual_profile(
    request: ManualProfileRequest,
    current_user: dict = Depends(get_current_active_user)
):
    profile = create_manual_profile(
        platform=request.platform,
        profile_url=str(request.profile_url),
        username=request.username,
        followers=request.followers,
        following=request.following,
        posts=request.posts,
        bio=request.bio,
        has_profile_picture=request.has_profile_picture,
        is_private=request.is_private,
    )
    features = extract_features(profile)
    return {
        "profile": profile,
        "features": features
    }


# ==================================================
# 7. Complete Profile Scan (manual fallback endpoint)
# ==================================================

@router.post(
    "/profile-scan",
    response_model=CompleteProfileScanResponse
)
def profile_scan(
    request: ManualProfileRequest,
    current_user: dict = Depends(get_current_active_user)
):
    scan_id = str(uuid.uuid4())
    profile = create_manual_profile(
        platform=request.platform,
        profile_url=str(request.profile_url),
        username=request.username,
        followers=request.followers,
        following=request.following,
        posts=request.posts,
        bio=request.bio,
        has_profile_picture=request.has_profile_picture,
        is_private=request.is_private,
    )
    features = extract_features(profile)
    result = run_risk_pipeline(profile, request.bio)

    save_scan_result(
        scan_id=scan_id,
        platform=profile["platform"],
        username=profile["username"],
        profile_url=profile["profile_url"],
        features=features,
        result=result,
        collection_source="user_provided",
        collection_status="success",
        model_name=MODEL_NAME,
        model_version=MODEL_VERSION,
        user_id=str(current_user["_id"])
    )

    return {
        "scan_id": scan_id,
        "platform": profile["platform"],
        "username": profile["username"],
        "profile_url": profile["profile_url"],
        "features": features,
        **result
    }


# ==================================================
# 7.5 Background Scan Jobs (B2, B3)
# ==================================================

@router.post("/jobs")
def create_background_scan_job(
    job_req: ScanJobRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Launch an asynchronous background scan job with stage progress events (B2).
    Enforces user consent requirement (S10) and checks 24-hour result cache (B3).
    """
    if not job_req.consent:
        raise HTTPException(
            status_code=422,
            detail="Consent must be confirmed to perform automated profile scan."
        )

    norm = normalize_profile_input(job_req.input, default_platform=job_req.platform or "instagram")
    if not norm["valid"]:
        raise HTTPException(
            status_code=422,
            detail=norm.get("error") or "Invalid profile URL or handle format."
        )

    try:
        job_info = create_scan_job(
            platform=norm["platform"],
            username=norm["username"],
            canonical_url=norm["canonical_url"],
            user_id=str(current_user["_id"]),
            force_refresh=bool(job_req.force_refresh)
        )
    except ValueError as ve:
        raise HTTPException(status_code=429, detail=str(ve))

    return job_info


@router.get("/jobs/{job_id}")
def get_background_scan_job(
    job_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Query current stage, progress percentage, and results of a background scan job.
    """
    job = get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found.")
    return job


@router.delete("/jobs/{job_id}")
def cancel_background_scan_job(
    job_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Cancel an active or queued background scan job.
    """
    success = cancel_job(job_id)
    if not success:
        job = get_job_status(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Scan job not found.")
        return {"job_id": job_id, "status": job.get("status"), "message": "Job cannot be cancelled (already finished or failed)."}

    return {"job_id": job_id, "status": "cancelled", "message": "Scan job cancelled successfully."}


# ==================================================
# 8. Automated URL-Driven Scan (primary endpoint)
# ==================================================

@router.post(
    "/auto",
    response_model=AutoScanResponse,
    summary="Automated URL-driven profile scan",
)
def auto_scan(
    request: AutoScanRequest,
    current_user: dict = Depends(get_current_active_user)
):
    if not request.consent:
        raise HTTPException(
            status_code=422,
            detail="Consent must be confirmed to perform automated profile scan."
        )

    profile_url = str(request.profile_url)
    scan_id = str(uuid.uuid4())

    validation = validate_profile_url(profile_url)
    if not validation["valid"]:
        raise HTTPException(
            status_code=422,
            detail=validation["error"] or "Unsupported social media platform.",
        )

    # 24-hour cache check (Decision S6)
    username_cand = validation.get("username", "")
    platform_cand = validation.get("platform", "")
    if username_cand and platform_cand:
        cached = get_cached_scan(platform_cand, username_cand)
        if cached:
            return cached

    collected = collect_profile(profile_url)
    collection_metadata = {
        "source": collected.get("collection_source", "none"),
        "status": collected.get("collection_status", "failed"),
        "timestamp": collected.get("collected_at") or datetime.now(timezone.utc).isoformat(),
        "fields_collected": collected.get("fields_collected", []),
    }

    features = extract_features(collected)
    bio = collected.get("bio") or ""
    result = run_risk_pipeline(collected, bio)

    username = collected.get("username") or "unknown"
    user_id_str = str(current_user["_id"])

    save_scan_result(
        scan_id=scan_id,
        platform=collected.get("platform", validation["platform"]),
        username=username,
        profile_url=profile_url,
        features=features,
        result=result,
        collection_source=collection_metadata["source"],
        collection_status=collection_metadata["status"],
        model_name=MODEL_NAME,
        model_version=MODEL_VERSION,
        collection_metadata=collection_metadata,
        user_id=user_id_str
    )

    # WebSocket per-user notification (C1 / S5)
    notify_user_threadsafe(user_id_str, {
        "type": "SCAN_COMPLETE",
        "message": f"Analysis complete for @{username}",
        "risk_score": result["final_score"],
        "platform": collected.get("platform", validation["platform"]),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    return {
        "scan_id": scan_id,
        "platform": collected.get("platform", validation["platform"]),
        "username": username,
        "profile_url": profile_url,
        "display_name": collected.get("display_name"),
        "collected_bio": bio or None,
        "profile": collected,
        "features": features,
        **result,
        "collection": collection_metadata,
        "from_cache": False,
    }



# ==================================================
# 9. PDF Report Generation
# ==================================================

@router.get("/{scan_id}/report.pdf")
def download_pdf_report(
    scan_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    # Enforce scan ownership check (S4)
    scan_data = scans_collection.find_one(
        {"scan_id": scan_id, "user_id": str(current_user["_id"])},
        {"_id": 0}
    )
    if not scan_data:
        raise HTTPException(status_code=404, detail="Scan not found.")

    # Increment PDF downloads count for user stats (C32)
    db.users.update_one(
        {"_id": current_user["_id"]},
        {"$inc": {"reportsGenerated": 1}}
    )

    pdf_bytes = generate_pdf_report(scan_data)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="authentiscore_report_{scan_id}.pdf"'}
    )


# ==================================================
# 10. Scan Feedback (A9)
# ==================================================

@router.post("/{scan_id}/feedback")
def submit_scan_feedback(
    scan_id: str,
    feedback: ScanFeedbackRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Submit user feedback on a scan result ('real', 'fake', 'bot').
    Used for evaluation monitoring and retraining datasets.
    """
    scan_data = scans_collection.find_one({"scan_id": scan_id})
    if not scan_data:
        raise HTTPException(status_code=404, detail="Scan not found.")

    feedback_doc = {
        "feedback_id": str(uuid.uuid4()),
        "scan_id": scan_id,
        "user_id": str(current_user["_id"]),
        "username": scan_data.get("username", "unknown"),
        "platform": scan_data.get("platform", "unknown"),
        "user_verdict": feedback.user_verdict.lower().strip(),
        "system_score": scan_data.get("final_score"),
        "system_classification": scan_data.get("classification"),
        "comment": feedback.comment,
        "rating": feedback.rating,
        "features": scan_data.get("features", {}),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        if hasattr(db, "scan_feedback"):
            db.scan_feedback.insert_one(feedback_doc)
    except Exception as exc:
        logger.warning("Could not persist feedback to MongoDB: %s", exc)

    return {
        "status": "success",
        "message": "Feedback recorded successfully",
        "feedback_id": feedback_doc["feedback_id"]
    }


# ==================================================
# 11. Scan Deletion / GDPR Compliance (B8)
# ==================================================

@router.delete("/{scan_id}")
def delete_scan(
    scan_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Delete a scan and associated user data for GDPR/privacy compliance (B8).
    """
    user_id_str = str(current_user["_id"])
    query = {"scan_id": scan_id, "user_id": user_id_str}
    
    scan_doc = scans_collection.find_one(query)
    if not scan_doc:
        raise HTTPException(status_code=404, detail="Scan not found or not owned by user.")

    try:
        scans_collection.delete_one(query)
        if hasattr(db, "scan_feedback"):
            db.scan_feedback.delete_many({"scan_id": scan_id, "user_id": user_id_str})
    except Exception as exc:
        logger.warning("Error deleting scan %s: %s", scan_id, exc)

    return {
        "status": "deleted",
        "scan_id": scan_id,
        "message": "Scan and associated data successfully deleted."
    }


# ==================================================
# 12. Manual Scan Completion / Overrides (B5)
# ==================================================

@router.post("/{scan_id}/complete")
def manually_complete_scan(
    scan_id: str,
    override: ManualCompletionRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Allow user to manually complete missing fields or supply overrides for a scan (B5).
    Re-runs scoring and marks supplied fields as 'user_provided' provenance.
    """
    user_id_str = str(current_user["_id"])
    query = {"scan_id": scan_id, "user_id": user_id_str}
    scan_doc = scans_collection.find_one(query)
    if not scan_doc:
        raise HTTPException(status_code=404, detail="Scan not found or not owned by user.")

    profile_data = scan_doc.get("profile", {}) or {}
    for field in ("followers", "following", "posts", "has_profile_picture", "is_private"):
        val = getattr(override, field)
        if val is not None:
            profile_data[field] = val
    if override.bio is not None:
        profile_data["bio"] = override.bio

    field_sources = scan_doc.get("field_sources", {}) or {}
    for field in ("followers", "following", "posts", "has_profile_picture", "is_private"):
        if getattr(override, field) is not None:
            field_sources[field] = "user_provided"

    features = extract_features(profile_data)
    bio = profile_data.get("bio", "")
    new_result = run_risk_pipeline(profile_data, bio=bio)
    new_result["field_sources"] = {**new_result.get("field_sources", {}), **field_sources}

    update_data = {
        "features": features,
        "profile": profile_data,
        "final_score": new_result.get("final_score"),
        "classification": new_result.get("classification"),
        "confidence": new_result.get("confidence"),
        "account_type": new_result.get("account_type"),
        "reasons": new_result.get("reasons"),
        "score_breakdown": new_result.get("score_breakdown"),
        "risk_components": new_result.get("risk_components"),
        "top_ml_factors": new_result.get("top_ml_factors"),
        "nlp_signals": new_result.get("nlp_signals"),
        "rule_signals": new_result.get("rule_signals"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    scans_collection.update_one(query, {"$set": update_data})

    return {
        "scan_id": scan_id,
        "platform": scan_doc.get("platform"),
        "username": scan_doc.get("username"),
        "profile_url": scan_doc.get("profile_url"),
        "features": features,
        **new_result,
    }