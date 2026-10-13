"""
AuthentiScore — Semantic NLP Engine
=====================================

Provides true Sequence Classification using a PyTorch-backed 
HuggingFace Transformer model to detect spam and bot-like behavior 
directly from the profile's bio text.

Architecture
------------
1.  HuggingFace Pipeline loaded ONCE at module initialisation.
2.  Bio text is fed into the neural network.
3.  Model outputs a label (e.g., 'spam' or 'ham') and a confidence score.
4.  Returns a bounded 0–100 semantic risk score.

Model
-----
    mrm8488/bert-tiny-finetuned-sms-spam-detection

Selected because it:
  - Is extremely lightweight and lightning fast on CPU.
  - Predicts spam/ham probabilities directly.
  - Runs locally without external API calls.
"""

from __future__ import annotations

import logging
import unicodedata
import re
from typing import Optional

logger = logging.getLogger(__name__)


# ==============================================================
# Configuration
# ==============================================================

# We use a tiny, fast model for SMS/Text spam detection
SEMANTIC_MODEL_NAME: str = "mrm8488/bert-tiny-finetuned-sms-spam-detection"
SEMANTIC_MODEL_VERSION: str = "v2"


# ==============================================================
# Model Singleton
# ==============================================================

_classifier = None
_model = None
_model_available: Optional[bool] = None
_model_load_error: Optional[str] = None


def get_classifier():
    """Lazy load text classification pipeline on first use."""
    global _classifier, _model, _model_available, _model_load_error
    if _model is not None and _model is not _classifier:
        return _model
    if _model_available is not None:
        return _classifier

    try:
        from transformers import pipeline

        logger.info(
            "AuthentiScore Semantic NLP: Loading Sequence Classifier '%s'...",
            SEMANTIC_MODEL_NAME,
        )

        _classifier = pipeline(
            "text-classification", 
            model=SEMANTIC_MODEL_NAME, 
            tokenizer=SEMANTIC_MODEL_NAME
        )
        _model_available = True
        logger.info("AuthentiScore Semantic NLP: Sequence Classifier loaded successfully.")
        return _classifier

    except ImportError:
        _model_load_error = (
            "transformers or torch is not installed. "
            "Run: pip install transformers torch"
        )
        logger.warning("Semantic NLP unavailable: %s", _model_load_error)
        _model_available = False
        return None

    except Exception as exc:
        _model_load_error = (
            f"Semantic NLP model failed to load: {type(exc).__name__}: {exc}"
        )
        logger.error("Semantic NLP model load error: %s", _model_load_error)
        _model_available = False
        return None


# ==============================================================
# Text Preprocessing
# ==============================================================

def _preprocess(text: str) -> str:
    """
    Lightweight preprocessing to normalise the bio text before classification.
    """
    if not text:
        return ""

    # Unicode normalise
    text = unicodedata.normalize("NFKC", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Truncate to avoid context window limits
    return text[:512]


# ==============================================================
# Main Semantic Analysis Function
# ==============================================================

def calculate_semantic_nlp_risk(bio: str, bio_language: Optional[str] = None) -> dict:
    """
    Analyse a profile bio using a PyTorch Sequence Classifier.

    Returns
    -------
    dict with keys:
        semantic_risk       : float  0–100
        matched_categories  : list[dict] (kept for compatibility)
        explanation         : str
        model_available     : bool
        model_applicable    : bool
        error               : str|None
        model_name          : str
        model_version       : str
    """
    global _classifier, _model_available, _model_load_error

    clf = get_classifier()

    # ── 0. Model unavailable ─────────────────────────────────────────────────
    if not _model_available or clf is None:
        return {
            "semantic_risk": 0.0,
            "matched_categories": [],
            "explanation": "Semantic NLP model is unavailable; semantic analysis skipped.",
            "model_available": False,
            "model_applicable": False,
            "error": _model_load_error,
            "model_name": SEMANTIC_MODEL_NAME,
            "model_version": SEMANTIC_MODEL_VERSION,
        }

    # ── 1. Empty / whitespace-only bio or bio under 15 chars (A5) ─────────────
    preprocessed = _preprocess(bio or "")

    if not preprocessed or len(preprocessed) < 15:
        return {
            "semantic_risk": 0.0,
            "matched_categories": [],
            "explanation": "Bio text too short for reliable semantic analysis (< 15 chars); skipped.",
            "model_available": True,
            "model_applicable": False,
            "error": None,
            "model_name": SEMANTIC_MODEL_NAME,
            "model_version": SEMANTIC_MODEL_VERSION,
        }

    # Language gating (A5): SMS-spam BERT is trained on English text only
    if bio_language is not None:
        detected_lang = bio_language
    else:
        from app.services.features.text_features import detect_bio_language
        detected_lang = detect_bio_language(preprocessed)
    if detected_lang not in {"en", "none"}:
        return {
            "semantic_risk": 0.0,
            "matched_categories": [],
            "explanation": f"Bio language '{detected_lang}' not supported by English semantic model; skipped.",
            "model_available": True,
            "model_applicable": False,
            "error": None,
            "model_name": SEMANTIC_MODEL_NAME,
            "model_version": SEMANTIC_MODEL_VERSION,
        }

    # ── 2. Run Classification ────────────────────────────────────────────────
    try:
        # returns e.g. [{'label': 'LABEL_1', 'score': 0.98}]
        result = clf(preprocessed)[0]
        
        label = result['label'].lower()
        score = result['score']
        
        is_spam = label in ['label_1', 'spam', 'toxic']
        
        # A5: Treat as weak signal on CPU — cap maximum semantic risk contribution to 50.0
        if is_spam:
            raw_risk = round(score * 100, 2)
            semantic_risk = min(raw_risk, 50.0)
            explanation = f"Neural Network detected spam signals (weak indicator, capped at 50% risk)."
            ui_label = "Spam / Bot Content"
        else:
            raw_risk = round((1.0 - score) * 100, 2)
            semantic_risk = min(raw_risk, 20.0)
            explanation = f"Neural Network detected typical human bio patterns."
            ui_label = "Authentic / Human Content"

    except Exception as exc:
        logger.error("Semantic NLP classification error: %s", exc)
        return {
            "semantic_risk": 0.0,
            "matched_categories": [],
            "explanation": f"Semantic classification failed: {type(exc).__name__}",
            "model_available": True,
            "model_applicable": False,
            "error": str(exc),
            "model_name": SEMANTIC_MODEL_NAME,
            "model_version": SEMANTIC_MODEL_VERSION,
        }

    return {
        "semantic_risk":       semantic_risk,
        "matched_categories":  [{"category": ui_label, "similarity": round(score, 4)}],
        "explanation":         explanation,
        "model_available":     True,
        "model_applicable":    True,
        "error":               None,
        "model_name":          SEMANTIC_MODEL_NAME,
        "model_version":       SEMANTIC_MODEL_VERSION,
    }
