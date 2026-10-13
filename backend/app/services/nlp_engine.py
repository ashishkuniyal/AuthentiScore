"""
AuthentiScore — Hybrid NLP Engine
====================================

Combines two complementary NLP approaches into a single hybrid risk signal:

    1. Keyword / Pattern NLP
       Rule-based regex matching against known suspicious phrases.
       Fast, deterministic, zero external dependencies.

    2. Semantic NLP
       Bio text is classified by a lightweight SMS-spam BERT model
       (mrm8488/bert-tiny-finetuned-sms-spam-detection).
       NOTE: This model was trained on SMS messages, not social-media bios;
       results are indicative. See README "Limitations".

Hybrid Weighting
----------------
    hybrid_nlp_risk = (keyword_risk × KEYWORD_WEIGHT)
                    + (semantic_risk × SEMANTIC_WEIGHT)

Limitations
-----------
    - Broad keywords (free, win, cash, invest) and the +25 negative-sentiment
      boost may produce false positives on legitimate bios. Flagged for owner
      review (D10 in CHANGES.md).
"""

import re
import logging
from typing import Optional

from app.services.semantic_nlp_engine import calculate_semantic_nlp_risk

logger = logging.getLogger(__name__)


# ==============================================================
# Hybrid Weighting Configuration
# ==============================================================
# Change these two constants to adjust the keyword/semantic balance.
# They must sum to 1.0.

KEYWORD_WEIGHT:  float = 0.40   # 40 % — keyword/pattern risk contribution
SEMANTIC_WEIGHT: float = 0.60   # 60 % — semantic embedding risk contribution


# ==============================================================
# Transformer Sentiment Model (existing, preserved)
# ==============================================================

# Lazy-loaded on first use; failure is cached (C25)
_nlp_pipeline = None
_nlp_load_failed: bool = False


def get_nlp_pipeline() -> Optional[object]:
    """Return the DistilBERT sentiment pipeline, or None when unavailable."""
    global _nlp_pipeline, _nlp_load_failed
    if _nlp_load_failed:
        return None
    if _nlp_pipeline is not None:
        return _nlp_pipeline
    try:
        from transformers import pipeline  # type: ignore  # lazy import (B3)
        logger.info("Loading DistilBERT sentiment model...")
        _nlp_pipeline = pipeline(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english",
        )
        logger.info("DistilBERT sentiment model loaded.")
        return _nlp_pipeline
    except Exception as exc:
        logger.warning("DistilBERT model unavailable (cached failure): %s", exc)
        _nlp_load_failed = True
        return None


# ==============================================================
# Keyword Risk Patterns (existing, preserved unchanged)
# ==============================================================

RISK_PATTERNS = {
    "scam": [
        r"\bscam\b",
        r"\bscammer\b",
        r"\bscammed\b",
        r"\bfraud\b",
        r"\bfraudulent\b",
    ],
    "money": [
        r"\bfree money\b",
        r"\bearn money\b",
        r"\bmake money\b",
        r"\bcash\b",
        r"\bprofit\b",
        r"\binvest\b",
        r"\binvestment\b",
    ],
    "urgency": [
        r"\burgent\b",
        r"\bact now\b",
        r"\blimited time\b",
        r"\blast chance\b",
    ],
    "contact": [
        r"\bcontact me\b",
        r"\bdm me\b",
        r"\bdirect message\b",
        r"\bwhatsapp\b",
        r"\btelegram\b",
    ],
    "promotional": [
        r"\bgiveaway\b",
        r"\bfree\b",
        r"\bwin\b",
        r"\bbonus\b",
        r"\boffer\b",
        r"\bdiscount\b",
    ],
}

CATEGORY_WEIGHTS = {
    "scam":        30,
    "money":       20,
    "urgency":     20,
    "contact":     15,
    "promotional": 15,
}


# ==============================================================
# Keyword Detection (existing, preserved)
# ==============================================================

def detect_risk_patterns(text: str):
    """Detect known suspicious keyword patterns in bio text."""
    if not text:
        text = ""

    text = str(text).lower()
    matches = []

    for category, patterns in RISK_PATTERNS.items():
        for pattern in patterns:
            found = re.findall(pattern, text)
            for match in found:
                matches.append({
                    "category": category,
                    "matched_text": match,
                })
    return matches


# ==============================================================
# Keyword NLP Score (existing, preserved)
# ==============================================================

def _calculate_keyword_risk(text: str) -> tuple[float, list]:
    """
    Calculate keyword-based NLP risk.

    C26 fix: each category is counted only once (max weight per category),
    so "free free free" does not triple the promotional score.

    Returns (keyword_risk_score: float, matches: list)
    """
    if not text or not str(text).strip():
        return 0.0, []

    matches = detect_risk_patterns(text)

    # Count each category once (C26)
    seen_categories: set = set()
    regex_score = 0.0
    for match in matches:
        category = match["category"]
        if category not in seen_categories:
            regex_score += CATEGORY_WEIGHTS.get(category, 0)
            seen_categories.add(category)

    # Transformer sentiment boost (lazy; skipped when model unavailable)
    transformer_boost = 0
    classifier = get_nlp_pipeline()
    if classifier is not None:
        try:
            truncated = str(text)[:500]
            result = classifier(truncated)[0]
            if result["label"] == "NEGATIVE" and result["score"] > 0.8:
                transformer_boost = 25
                matches.append({
                    "category": "ai_sentiment_flag",
                    "matched_text": f"NEGATIVE ({result['score']:.2f})",
                })
            elif result["label"] == "POSITIVE" and result["score"] > 0.9:
                transformer_boost = -10
        except Exception as exc:
            logger.error("Transformer NLP failed: %s", exc)

    keyword_risk = float(max(0, min(regex_score + transformer_boost, 100)))
    return keyword_risk, matches


# ==============================================================
# Hybrid NLP Score — Primary Entry Point
# ==============================================================

def calculate_nlp_rule_score(text: str) -> dict:
    """
    Compute the hybrid NLP risk score combining keyword and semantic signals.

    This is the function called by the existing risk pipeline in scan.py.
    The return dict is a superset of the old format — all existing keys
    are preserved, new keys are added:

        score               (existing) — hybrid_nlp_risk (float 0–100)
        matches             (existing) — keyword matches list
        keyword_risk        (new)      — raw keyword+sentiment score
        semantic_risk       (new)      — raw semantic similarity score
        hybrid_nlp_risk     (new)      — weighted combination
        semantic_details    (new)      — full semantic result dict
        nlp_model_name      (new)      — sentence-transformer model ID
        nlp_model_version   (new)      — version string

    Note: `score` equals `hybrid_nlp_risk` so existing consumers that only
    read `result["score"]` continue to work without modification.
    """

    # ── 1. Keyword + sentiment risk (existing) ───────────────────────────────
    keyword_risk, matches = _calculate_keyword_risk(text or "")

    # ── 2. Semantic risk (new) ────────────────────────────────────────────────
    semantic_result = calculate_semantic_nlp_risk(text or "")
    semantic_risk   = semantic_result["semantic_risk"]

    # ── 3. Hybrid combination ─────────────────────────────────────────────────
    hybrid_nlp_risk = round(
        min(
            (keyword_risk  * KEYWORD_WEIGHT)
            + (semantic_risk * SEMANTIC_WEIGHT),
            100.0,
        ),
        2,
    )

    # ── 4. Return ─────────────────────────────────────────────────────────────
    return {
        # ------ Existing keys (preserved — backward compatible) ------
        "score":   hybrid_nlp_risk,    # used by risk_engine.py
        "matches": matches,            # used by scan.py for matched_phrases

        # ------ New keys ------
        "keyword_risk":      round(keyword_risk,  2),
        "semantic_risk":     round(semantic_risk, 2),
        "hybrid_nlp_risk":   hybrid_nlp_risk,
        "semantic_details":  semantic_result,

        # Model metadata
        "nlp_model_name":    semantic_result.get("model_name", ""),
        "nlp_model_version": semantic_result.get("model_version", ""),

        # Weighting config (for explainability / audit trail)
        "keyword_weight":    KEYWORD_WEIGHT,
        "semantic_weight":   SEMANTIC_WEIGHT,
    }