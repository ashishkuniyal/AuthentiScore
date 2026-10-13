"""
AuthentiScore — SHAP Explainer
================================

Generates plain-English ML explanations for a single profile prediction
using SHAP TreeExplainer on the Random Forest sub-model of the ensemble.

Note (C24): The SHAP values describe the Random-Forest component only,
not the full calibrated LR+RF+XGB ensemble. The score itself comes from
the ensemble. Method label: "RandomForest component (approximation)".

None values for missing features are reported with "imputed": True;
SHAP is still computed on the imputed row. NaN/Inf are never emitted.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

import pandas as pd
from fastapi import HTTPException

from app.services.model_store import get_model, get_features, is_loaded
from app.services.feature_engine import extract_features

logger = logging.getLogger(__name__)

# SHAP explainer singleton (built lazily, once per process)
_shap_explainer = None
_shap_load_error: Optional[str] = None


def _get_explainer():
    """Build and cache the SHAP TreeExplainer."""
    global _shap_explainer, _shap_load_error

    if _shap_explainer is not None:
        return _shap_explainer

    if not is_loaded():
        raise HTTPException(
            status_code=503,
            detail="Model not trained. Run: python -m scripts.train_v3_ensemble",
        )

    try:
        import shap  # type: ignore

        model = get_model()
        calibrated = model.named_steps["calibrated_ensemble"]
        rf_estimator = (
            calibrated.calibrated_classifiers_[0].estimator.estimators_[1]
        )
        _shap_explainer = shap.TreeExplainer(rf_estimator)
        logger.info("SHAP TreeExplainer built on RF sub-model.")
        return _shap_explainer

    except Exception as exc:
        _shap_load_error = f"SHAP explainer failed to build: {exc}"
        logger.error(_shap_load_error)
        raise HTTPException(status_code=503, detail=_shap_load_error)


# --------------------------------------------------
# Plain-language label mapping
# --------------------------------------------------

def _feature_label(feature: str, value: Optional[float], is_risk: bool) -> str:
    """
    Convert a raw feature + SHAP direction into a plain-English sentence.
    Labels are chosen so that:
      - risk labels describe what *raises* risk
      - trust labels describe what *lowers* risk
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "Missing data (imputed by model)"

    rules = {
        "followers": [
            (lambda v: v < 50,   "Very low follower count raises risk",        "Healthy follower base (trust signal)"),
            (lambda v: v < 200,  "Low follower count is suspicious",            "Moderate follower count is normal"),
            (lambda v: v < 2000, "Below-average follower count",                "Reasonable follower base"),
            (lambda v: True,     "Unusually large follower base (check ratio)", "Large, healthy follower base"),
        ],
        "following": [
            (lambda v: v > 5000, "Following an unusually large number of accounts (bot signal)",  "Normal following count"),
            (lambda v: v > 2000, "Following a very high number of accounts",                       "Normal following count"),
            (lambda v: True,     "Normal following count",                                         "Normal following count"),
        ],
        "follower_following_ratio": [
            (lambda v: v < 0.05, "Follows far more accounts than it has followers (bot pattern)",  "Very balanced ratio"),
            (lambda v: v < 0.2,  "Heavily skewed toward following over followers",                 "Mostly balanced ratio"),
            (lambda v: v < 1.0,  "Follows more accounts than followers",                           "Slightly more following than followers"),
            (lambda v: v >= 10,  "Disproportionately large follower base (verify authenticity)",    "Very high follower-to-following ratio"),
            (lambda v: True,     "Balanced follower-to-following ratio",                            "Balanced follower-to-following ratio"),
        ],
        "bio_length": [
            (lambda v: v == 0,  "Empty biography is a strong bot/fake signal",  "Profile has a biography"),
            (lambda v: v < 20,  "Very short biography is suspicious",            "Short but present biography"),
            (lambda v: v < 60,  "Brief biography may indicate automated account","Brief but present biography"),
            (lambda v: True,    "Detailed biography reduces fake risk",           "Detailed biography (trust signal)"),
        ],
        "has_profile_picture": [
            (lambda v: v == 0, "No profile picture — strong fake indicator",      "Profile picture present"),
            (lambda v: True,   "Profile picture present",                          "Profile picture is set (trust signal)"),
        ],
        "is_private": [
            (lambda v: v == 1, "Private account limits verification",             "Account is private"),
            (lambda v: True,   "Public account is fully verifiable",               "Publicly visible account"),
        ],
        "username_digit_ratio": [
            (lambda v: v > 0.5,  "Username is mostly digits — common bot pattern", "Username looks natural"),
            (lambda v: v > 0.3,  "Username contains many digits",                   "Username looks mostly natural"),
            (lambda v: True,     "Username digit ratio looks normal",                "Natural-looking username"),
        ],
        "posts": [
            (lambda v: v == 0,  "Account has never posted — strong bot indicator", "Account has posts"),
            (lambda v: v < 5,   "Very few posts for an established account",        "Some posting history"),
            (lambda v: v < 20,  "Few posts may indicate new or bot account",        "Account has made several posts"),
            (lambda v: True,    "Active posting history reduces fake risk",          "Active posting history (trust signal)"),
        ],
        "profile_completeness": [
            (lambda v: v < 0.4,  "Very incomplete profile is a fake indicator",    "Profile is mostly complete"),
            (lambda v: v < 0.7,  "Incomplete profile raises suspicion",             "Profile is partially complete"),
            (lambda v: True,     "Complete profile reduces fake risk",               "Complete profile (trust signal)"),
        ],
    }

    feature_rules = rules.get(feature)
    if not feature_rules:
        return "Increases risk" if is_risk else "Reduces risk"

    for condition_fn, risk_lbl, trust_lbl in feature_rules:
        try:
            if condition_fn(value):
                return risk_lbl if is_risk else trust_lbl
        except Exception:
            continue

    return "Increases risk" if is_risk else "Reduces risk"


# --------------------------------------------------
# Generate ML Explanation
# --------------------------------------------------

def generate_ml_explanation(profile: dict, top_n: int = 3) -> list:
    """
    Return a list of up to *top_n* SHAP-based feature explanations.

    Each element:
    {
        "label":      str,    # human-readable sentence
        "is_risk":    bool,   # True = raises fake-risk
        "feature":    str,    # feature name
        "value":      float|None,  # pre-imputation value (None when missing)
        "imputed":    bool,   # True when the model imputed this value
        "shap_value": float,  # SHAP contribution (fake class)
        "impact":     str,    # "increases risk" | "decreases risk"
        "explanation_method": str
    }
    """
    explainer = _get_explainer()
    features  = get_features()
    model     = get_model()

    # Build raw feature vector (may contain None → NaN after astype)
    features_dict = extract_features(profile)

    X_raw = pd.DataFrame(
        [[features_dict.get(f) for f in features]],
        columns=features,
    ).astype(float)

    # Impute for SHAP (same step name as training pipeline)
    imputer  = model.named_steps["imputer"]
    X_imputed = imputer.transform(X_raw)

    # SHAP values on imputed data
    shap_values = explainer.shap_values(X_imputed)

    # Normalise SHAP output shape (supports old and new SHAP versions)
    if hasattr(shap_values, "ndim") and shap_values.ndim == 3:
        fake_class_shap = shap_values[0, :, 1]
    elif isinstance(shap_values, list):
        fake_class_shap = shap_values[1][0]
    else:
        fake_class_shap = shap_values[0]

    # Raw values (pre-imputation) for display
    raw_values = X_raw.iloc[0].tolist()

    import numpy as np
    factors = []
    indexed = sorted(
        enumerate(fake_class_shap),
        key=lambda x: abs(x[1]),
        reverse=True,
    )

    for idx, shap_val in indexed[:top_n]:
        feature_name = features[idx]
        raw_val      = raw_values[idx]

        # Determine whether this feature was missing (imputed)
        is_missing = bool(raw_val is None or (
            isinstance(raw_val, float) and np.isnan(raw_val)
        ))
        display_val = None if is_missing else float(raw_val)

        shap_val_f  = float(shap_val)
        is_risk     = bool(shap_val_f > 0)

        # Guard against NaN/Inf in SHAP output
        if not math.isfinite(shap_val_f):
            shap_val_f = 0.0

        label = _feature_label(feature_name, display_val, is_risk)

        factors.append({
            "label":              label,
            "is_risk":            is_risk,
            "feature":            feature_name,
            "value":              display_val,
            "imputed":            is_missing,
            "shap_value":         round(shap_val_f, 4),
            "impact":             "increases risk" if is_risk else "decreases risk",
            "explanation_method": "RandomForest component (approximation)",
        })

    return factors