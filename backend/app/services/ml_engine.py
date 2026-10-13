from pathlib import Path

import joblib
import pandas as pd

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
# Load model and feature list
# --------------------------------------------------

model = joblib.load(MODEL_PATH)
FEATURES = joblib.load(FEATURES_PATH)


# --------------------------------------------------
# ML Risk Prediction
# --------------------------------------------------

def calculate_ml_risk(features_dict: dict) -> float:

    X = pd.DataFrame(
        [[features_dict.get(feature) for feature in FEATURES]],
        columns=FEATURES
    ).astype(float)

    probability = model.predict_proba(X)[0][1]

    return round(float(probability * 100), 2)