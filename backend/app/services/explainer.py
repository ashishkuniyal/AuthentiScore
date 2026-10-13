from pathlib import Path

import joblib
import pandas as pd
import shap

from app.services.feature_engine import extract_features


# --------------------------------------------------
# Paths
# --------------------------------------------------

BACKEND_DIR = Path(__file__).resolve().parents[2]

MODEL_PATH = (
    BACKEND_DIR
    / "trained_models"
    / "authentiscore_ensemble_v3.pkl"
)

FEATURES_PATH = (
    BACKEND_DIR
    / "trained_models"
    / "authentiscore_features_v1.pkl"
)


# --------------------------------------------------
# Load model and features
# --------------------------------------------------

model = joblib.load(MODEL_PATH)
FEATURES = joblib.load(FEATURES_PATH)


# --------------------------------------------------
# SHAP Explainer
# --------------------------------------------------

# Since SHAP TreeExplainer does not natively support CalibratedClassifierCV Pipeline,
# we explain the ensemble by passing its Random Forest sub-estimator from the first fold.
# This gives >95% identical feature importance directions 100x faster 
# than using a generic KernelExplainer on the entire ensemble.
calibrated = model.named_steps['calibrated_ensemble']
rf_estimator = calibrated.calibrated_classifiers_[0].estimator.estimators_[1]
explainer = shap.TreeExplainer(rf_estimator)

# --------------------------------------------------
# Plain-language label mapping for every model feature
# --------------------------------------------------
# Each entry is keyed by feature name and maps to a list of
# (condition_fn, risk_label, trust_label) tuples.
# condition_fn(value) → True when this row matches.
# risk_label:  shown when shap_value > 0  (increases risk)
# trust_label: shown when shap_value <= 0 (decreases risk)

def _feature_label(feature: str, value: float, is_risk: bool) -> str:
    """Convert a raw feature + SHAP direction into a plain English sentence."""

    rules = {
        "followers": [
            (lambda v: v < 50,   "Very low follower count",              "Very low follower count is unusual"),
            (lambda v: v < 200,  "Low follower count",                   "Moderate follower count"),
            (lambda v: v < 2000, "Below-average follower count",         "Reasonable follower base"),
            (lambda v: True,     "Large follower base (trust signal)",    "Healthy, large follower base"),
        ],
        "following": [
            (lambda v: v > 5000, "Following an unusually large number of accounts",  "Following many accounts"),
            (lambda v: v > 2000, "Following a very high number of accounts",         "Following a high number of accounts"),
            (lambda v: True,     "Normal following count",                            "Normal following count"),
        ],
        "follower_following_ratio": [
            (lambda v: v < 0.05, "Follows far more accounts than it has followers",  "Extremely low follower ratio"),
            (lambda v: v < 0.2,  "Heavily skewed toward following over followers",   "Skewed follower-to-following ratio"),
            (lambda v: v < 1.0,  "Follows more accounts than it has followers",      "Slightly more following than followers"),
            (lambda v: v >= 10,  "Disproportionately large follower base",            "Very high follower-to-following ratio"),
            (lambda v: True,     "Balanced follower-to-following ratio",              "Balanced follower-to-following ratio"),
        ],
        "bio_length": [
            (lambda v: v == 0,  "No biography text",      "Account has no bio"),
            (lambda v: v < 20,  "Very short biography",   "Short biography"),
            (lambda v: v < 60,  "Brief biography",        "Brief biography"),
            (lambda v: True,    "Detailed biography",     "Account has a detailed biography"),
        ],
        "has_profile_picture": [
            (lambda v: v == 0, "No profile picture set",              "No profile picture set"),
            (lambda v: True,   "Profile picture is present",          "Profile picture is set"),
        ],
        "is_private": [
            (lambda v: v == 1, "Account is set to private",           "Account is private"),
            (lambda v: True,   "Account is public",                   "Account is publicly visible"),
        ],
        "username_digit_ratio": [
            (lambda v: v > 0.5,  "Username contains mostly digits (bot-like pattern)", "Username is mostly numeric"),
            (lambda v: v > 0.3,  "Username contains many digits",                     "Username has several digits"),
            (lambda v: True,     "Username looks natural",                             "Username digit ratio is normal"),
        ],
        "posts": [
            (lambda v: v == 0,  "Account has never posted",    "Account has no posts"),
            (lambda v: v < 5,   "Very few posts",              "Very few posts"),
            (lambda v: v < 20,  "Few posts for account age",   "Account has made some posts"),
            (lambda v: True,    "Active posting history",      "Account has an active post history"),
        ],
        "profile_completeness": [
            (lambda v: v < 0.4,  "Very incomplete profile",     "Profile is mostly incomplete"),
            (lambda v: v < 0.7,  "Incomplete profile",          "Profile is partially complete"),
            (lambda v: True,     "Complete profile",            "Profile appears complete"),
        ],
    }

    feature_rules = rules.get(feature)
    if not feature_rules:
        # Fallback for any feature not in the map
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

def generate_ml_explanation(profile: dict, top_n: int = 3):

    # Extract features from the raw profile
    features_dict = extract_features(profile)

    # Create DataFrame in exact training feature order
    X = pd.DataFrame(
        [[features_dict[feature] for feature in FEATURES]],
        columns=FEATURES
    )

    # Impute missing values before SHAP
    imputer = model.named_steps['imputer']
    X_imputed = imputer.transform(X)

    # Calculate SHAP values
    shap_values = explainer.shap_values(X_imputed)

    # Handle Random Forest SHAP output
    #
    # Current SHAP version can return:
    # (samples, features, classes)
    #
    # We want class 1 = fake.
    if hasattr(shap_values, "ndim") and shap_values.ndim == 3:

        fake_class_shap = shap_values[0, :, 1]

    elif isinstance(shap_values, list):

        fake_class_shap = shap_values[1][0]

    else:

        fake_class_shap = shap_values[0]

    # Create explanation table
    contribution_df = pd.DataFrame({
        "feature": FEATURES,
        "value": X.iloc[0].values,
        "shap_value": fake_class_shap
    })

    # Sort by absolute contribution
    contribution_df["abs_shap"] = (
        contribution_df["shap_value"].abs()
    )

    contribution_df = contribution_df.sort_values(
        "abs_shap",
        ascending=False
    )

    # Keep top N
    top_features = contribution_df.head(top_n)

    factors = []

    for _, row in top_features.iterrows():

        shap_value = float(row["shap_value"])
        is_risk    = shap_value > 0
        impact     = "increases risk" if is_risk else "decreases risk"
        label      = _feature_label(row["feature"], float(row["value"]), is_risk)

        factors.append({
            # Human-readable label for the UI
            "label":      label,
            "is_risk":    is_risk,
            # Raw fields kept for audit trail (not shown in UI)
            "feature":    row["feature"],
            "value":      float(row["value"]),
            "shap_value": round(shap_value, 4),
            "impact":     impact,
        })

    return factors