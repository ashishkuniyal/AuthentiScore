"""
AuthentiScore — Model Store
============================

Thread-safe lazy loader for the trained ML model and feature list.

Exposes:
    get_model()     → the loaded sklearn Pipeline (or None if not available)
    get_features()  → list[str] of feature names (or None if not available)
    is_loaded()     → bool
    MODEL_NAME      → str
    MODEL_VERSION   → str

If the model artefacts are missing, the app still starts.
Endpoints that require the model should call is_loaded() first and
return HTTP 503 with a clear message when it returns False.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────

BACKEND_DIR = Path(__file__).resolve().parents[2]
TRAINED_MODELS_DIR = BACKEND_DIR / "trained_models"

_MODEL_PKL   = TRAINED_MODELS_DIR / "authentiscore_ensemble_v4.pkl"
_FEATURES_JSON = TRAINED_MODELS_DIR / "authentiscore_features_v4.json"
_METRICS_JSON  = TRAINED_MODELS_DIR / "metrics_v4.json"

# ─────────────────────────────────────────────────────────────
# Public metadata (available even without artefacts)
# ─────────────────────────────────────────────────────────────

MODEL_NAME    = "CalibratedEnsemble_LR_RF_XGB"
MODEL_VERSION = "v4"

# ─────────────────────────────────────────────────────────────
# Internal singleton state
# ─────────────────────────────────────────────────────────────

_lock: threading.Lock = threading.Lock()
_model: Optional[object] = None
_features: Optional[list] = None
_loaded: bool = False
_load_error: Optional[str] = None


def _attempt_load() -> None:
    """Load model + features once. Must be called with _lock held."""
    global _model, _features, _loaded, _load_error

    # ── Check artefacts exist ────────────────────────────────
    if not _MODEL_PKL.exists():
        _load_error = (
            f"Model file not found: {_MODEL_PKL}. "
            "Run: python -m scripts.train_v3_ensemble"
        )
        logger.warning(_load_error)
        return

    if not _FEATURES_JSON.exists():
        _load_error = (
            f"Features file not found: {_FEATURES_JSON}. "
            "Run: python -m scripts.train_v3_ensemble"
        )
        logger.warning(_load_error)
        return

    # ── Load ─────────────────────────────────────────────────
    try:
        import joblib  # type: ignore

        logger.info("AuthentiScore ModelStore: loading %s …", _MODEL_PKL.name)
        _model = joblib.load(_MODEL_PKL)

        with open(_FEATURES_JSON, "r", encoding="utf-8") as fh:
            raw_data = json.load(fh)
            if isinstance(raw_data, dict) and "features" in raw_data:
                _features = raw_data["features"]
            else:
                _features = raw_data

        _loaded = True
        _load_error = None
        logger.info(
            "AuthentiScore ModelStore: loaded %s with %d features.",
            MODEL_VERSION,
            len(_features),
        )

    except Exception as exc:
        _load_error = f"Model load failed: {type(exc).__name__}: {exc}"
        logger.error("AuthentiScore ModelStore: %s", _load_error)
        _model = None
        _features = None
        _loaded = False


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def get_model():
    """Return the loaded model pipeline, or None if not available."""
    if not _loaded:
        with _lock:
            if not _loaded:
                _attempt_load()
    return _model


def get_features() -> Optional[list]:
    """Return the feature name list, or None if not available."""
    if not _loaded:
        with _lock:
            if not _loaded:
                _attempt_load()
    return _features


def is_loaded() -> bool:
    """Return True when the model and features are ready."""
    if not _loaded:
        with _lock:
            if not _loaded:
                _attempt_load()
    return _loaded


def get_load_error() -> Optional[str]:
    """Return the load-error string (or None when loaded OK)."""
    return _load_error


def get_metrics() -> dict:
    """Return the training metrics from metrics_v3.json (best-effort)."""
    try:
        if _METRICS_JSON.exists():
            with open(_METRICS_JSON, "r", encoding="utf-8") as fh:
                return json.load(fh)
    except Exception as exc:
        logger.warning("Could not read metrics_v3.json: %s", exc)
    return {}
