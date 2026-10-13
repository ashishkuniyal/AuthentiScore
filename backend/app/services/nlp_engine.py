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
# ==============================================================
# Context Rules & Whitelists (A5)
# ==============================================================

BENIGN_WHITELIST_PHRASES = [
    r"\bgiveaway bot\b",
    r"\bfree software\b",
    r"\bopen source\b",
    r"\bwin-win\b",
    r"\bfree to play\b",
]

NEGATION_PATTERNS = [
    r"\bno scams?\b",
    r"\banti-scams?\b",
    r"\breport scammers?\b",
    r"\bavoid scams?\b",
    r"\bscam alert\b",
    r"\bstop scammers?\b",
    r"\bnot a scam\b",
    r"\bnot for sale\b",
]


# ==============================================================
# Keyword Detection (A5 with context rules & negation checks)
# ==============================================================

def detect_risk_patterns(text: str) -> list[dict]:
    """
    Detect known suspicious keyword patterns in bio text.
    Applies context rules:
      - Ignores whitelisted benign phrases ('giveaway bot', 'open source', etc.)
      - Ignores negated phrases ('no scams', 'anti-scam', 'report scammers')
    """
    if not text:
        return []

    text_lower = str(text).lower()

    # Mask whitelisted benign phrases so sub-words (e.g. 'free', 'giveaway') don't falsely fire
    sanitized = text_lower
    for w_pat in BENIGN_WHITELIST_PHRASES:
        sanitized = re.sub(w_pat, " __benign__ ", sanitized)

    # Mask negated phrases so words like 'scam' don't fire on anti-scam educators
    for neg_pat in NEGATION_PATTERNS:
        sanitized = re.sub(neg_pat, " __negated__ ", sanitized)

    matches = []
    for category, patterns in RISK_PATTERNS.items():
        for pattern in patterns:
            found = re.findall(pattern, sanitized)
            for match in found:
                matches.append({
                    "category": category,
                    "matched_text": match,
                })
    return matches


# ==============================================================
# Keyword NLP Score (A5: no +25 sentiment boost, multi-signal required)
# ==============================================================

def _calculate_keyword_risk(text: str) -> tuple[float, list]:
    """
    Calculate keyword-based NLP risk.
    - Each category is counted only once (max weight per category).
    - Requires at least two independent category signals before reaching high scam tiers.
    - Decision S3: Removed unconditional +25 negative sentiment boost.
    """
    if not text or not str(text).strip():
        return 0.0, []

    matches = detect_risk_patterns(text)

    # Count each category once
    seen_categories: set[str] = set()
    category_score = 0.0
    for match in matches:
        category = match["category"]
        if category not in seen_categories:
            category_score += CATEGORY_WEIGHTS.get(category, 0)
            seen_categories.add(category)

    # Single isolated signal attenuation: e.g. only 'promotional' word in utility account
    if len(seen_categories) == 1:
        # Attenuate single isolated keyword trigger to avoid false positives on utility bots
        category_score = min(category_score, 15.0)

    # Decision S3: Tone is not spam. Removed +25 negative boost and -10 positive bonus.
    # Transformer sentiment adds at most +5 if multiple suspicious categories were already matched.
    transformer_boost = 0
    if len(seen_categories) >= 2:
        classifier = get_nlp_pipeline()
        if classifier is not None:
            try:
                truncated = str(text)[:500]
                result = classifier(truncated)[0]
                if result["label"] == "NEGATIVE" and result["score"] > 0.85:
                    transformer_boost = 5
                    matches.append({
                        "category": "ai_sentiment_flag",
                        "matched_text": f"NEGATIVE ({result['score']:.2f})",
                    })
            except Exception as exc:
                logger.error("Transformer NLP check failed: %s", exc)

    keyword_risk = float(max(0, min(category_score + transformer_boost, 100)))
    return keyword_risk, matches


# ==============================================================
# Hybrid NLP Score — Primary Entry Point
# ==============================================================

def calculate_nlp_rule_score(text: str) -> dict:
    """
    Compute hybrid NLP risk combining keyword context rules and semantic model.
    Dynamically adjusts weights if the semantic model is inapplicable.
    """
    # ── 1. Keyword + sentiment risk ───────────────────────────────
    keyword_risk, matches = _calculate_keyword_risk(text or "")

    # ── 2. Semantic risk ──────────────────────────────────────────
    semantic_result = calculate_semantic_nlp_risk(text or "")
    semantic_risk   = semantic_result.get("semantic_risk", 0.0)
    semantic_applicable = bool(semantic_result.get("model_applicable", True))

    # ── 3. Hybrid combination (A5) ────────────────────────────────
    if not semantic_applicable:
        eff_kw_weight = 1.0
        eff_sem_weight = 0.0
        hybrid_nlp_risk = round(keyword_risk, 2)
        nlp_method = "keyword_rules_only (semantic inapplicable)"
    else:
        eff_kw_weight = KEYWORD_WEIGHT
        eff_sem_weight = SEMANTIC_WEIGHT
        hybrid_nlp_risk = round(
            min(
                (keyword_risk  * eff_kw_weight)
                + (semantic_risk * eff_sem_weight),
                100.0,
            ),
            2,
        )
        nlp_method = "calibrated_context_hybrid"

    # ── 4. Return (Additive fields) ──────────────────────────────
    return {
        # Preserved existing keys
        "score":   hybrid_nlp_risk,
        "matches": matches,

        # Additive metadata
        "keyword_risk":      round(keyword_risk,  2),
        "semantic_risk":     round(semantic_risk, 2),
        "hybrid_nlp_risk":   hybrid_nlp_risk,
        "semantic_details":  semantic_result,
        "nlp_model_name":    semantic_result.get("model_name", ""),
        "nlp_model_version": semantic_result.get("model_version", ""),
        "keyword_weight":    eff_kw_weight,
        "semantic_weight":   eff_sem_weight,
        "method":            nlp_method,
    }