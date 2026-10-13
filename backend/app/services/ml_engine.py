"""
AuthentiScore — ML Risk Engine
================================

Runs the calibrated LR+RF+XGB ensemble pipeline (v3) to predict the
probability that a social-media profile is fake/inauthentic.

The model is loaded via model_store (lazy, thread-safe). If the model
is not yet trained, callers will receive an HTTPException 503.
"""

from __future__ import annotations

import logging

import pandas as pd
from fastapi import HTTPException

from app.services.model_store import get_model, get_features, is_loaded, MODEL_VERSION

logger = logging.getLogger(__name__)


def _require_model():
    """Raise HTTP 503 when the model artefacts are not available."""
    if not is_loaded():
        raise HTTPException(
            status_code=503,
            detail=(
                "Model not trained. "
                "Run: python -m scripts.train_v3_ensemble"
            ),
        )


# --------------------------------------------------
# ML Risk Prediction
# --------------------------------------------------

def calculate_ml_risk(features_dict: dict) -> float:
    """
    Given a features dict (with possible None values), return a 0–100
    fake-probability score.

    Parameters
    ----------
    features_dict : dict
        Output of feature_engine.extract_features().  None values are
        allowed; the model's imputer handles them.

    Returns
    -------
    float — probability × 100, rounded to 2 dp.
    """
    _require_model()

    model    = get_model()
    features = get_features()

    X = pd.DataFrame(
        [[features_dict.get(f) for f in features]],
        columns=features,
    ).astype(float)

    probability = model.predict_proba(X)[0][1]
    return round(float(probability * 100), 2)