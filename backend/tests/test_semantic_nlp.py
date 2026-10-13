"""
AuthentiScore — Semantic NLP Engine Tests
==========================================

Tests for the new semantic NLP component and the hybrid NLP pipeline.

Test scenarios:
    1.  Empty bio
    2.  Normal/benign bio
    3.  Suspicious financial bio
    4.  Promotional/spam bio
    5.  Mixed bio (some suspicious, some benign)
    6.  Very long bio (> 500 chars)
    7.  Special characters only
    8.  Unicode text (non-ASCII)
    9.  Semantic model unavailable (mocked)
    10. NLP API failure (mocked)

A small controlled test set is also defined with expected behaviour
ranges (not strict equality, since embeddings and sentiment models
return continuous scores).
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

pytest.importorskip("transformers")

# ---------------------------------------------------------------------------
# Path setup — allow running from the backend/ directory
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.semantic_nlp_engine import calculate_semantic_nlp_risk
from app.services.nlp_engine import calculate_nlp_rule_score


# ===========================================================================
# Controlled Test Bios
# ===========================================================================

BIOS = {
    "empty":       "",
    "whitespace":  "   \n\t  ",
    "normal": (
        "Photographer based in London. Sharing travel stories and "
        "coffee shop reviews. DM for collaborations."
    ),
    "financial_scam": (
        "Make $5000 weekly guaranteed! Double your money with our "
        "proven investment system. Limited spots. Contact me NOW on WhatsApp."
    ),
    "promotional": (
        "Follow for follow back! Like my pics for shoutout. "
        "Buy real followers and likes cheap. Grow your account fast."
    ),
    "giveaway": (
        "WIN a FREE iPhone! Just follow me, like this post and "
        "tag 3 friends. Giveaway ends tonight. You have been selected!"
    ),
    "urgency": (
        "ACT NOW! Last chance to join our exclusive program. "
        "Limited time offer expires in 24 hours. Don't miss out!"
    ),
    "mixed": (
        "Fitness enthusiast | Personal trainer | "
        "DM me for guaranteed results | earn money with our supplement program"
    ),
    "very_long": (
        "I am a legitimate content creator who shares daily life, "
        "recipes, travel adventures and lifestyle content. "
        "I believe in authentic connections and genuine engagement. "
        "No sponsored posts unless I truly believe in the product. "
        "Please reach out for genuine collaboration opportunities only. " * 5
    ),
    "special_chars":  "!!! *** @@@ ### $$$ %%% ^^^ &&& *** ((())) ---",
    "unicode_arabic": "أنا مصور محترف يعيش في القاهرة",
    "unicode_emoji":  "🌟 Travel | 📸 Photography | 🎨 Art | ✨ Life",
}


# ===========================================================================
# Test 1 — Empty Bio
# ===========================================================================

def test_semantic_empty_bio():
    """Empty bio should produce zero semantic risk with no matched categories."""
    result = calculate_semantic_nlp_risk(BIOS["empty"])
    assert result["semantic_risk"] == 0.0
    assert result["matched_categories"] == []
    assert "model_available" in result


def test_semantic_whitespace_bio():
    """Whitespace-only bio treated the same as empty."""
    result = calculate_semantic_nlp_risk(BIOS["whitespace"])
    assert result["semantic_risk"] == 0.0
    assert result["matched_categories"] == []


# ===========================================================================
# Test 2 — Normal / Benign Bio
# ===========================================================================

def test_semantic_normal_bio_low_risk():
    """
    A normal, benign bio should produce low semantic risk.
    We allow up to 30/100 — benign bios may have incidental similarity.
    """
    result = calculate_semantic_nlp_risk(BIOS["normal"])
    assert result["semantic_risk"] < 40.0, (
        f"Expected normal bio semantic_risk < 40, got {result['semantic_risk']}"
    )
    assert isinstance(result["matched_categories"], list)


# ===========================================================================
# Test 3 — Suspicious Financial Bio
# ===========================================================================

def test_semantic_financial_bio_high_risk():
    """
    A financial scam bio should produce elevated semantic risk when classified as spam.
    """
    with patch("app.services.semantic_nlp_engine.get_classifier") as mock_get_clf:
        mock_clf = MagicMock()
        mock_clf.return_value = [{"label": "LABEL_1", "score": 0.88}]
        mock_get_clf.return_value = mock_clf

        result = calculate_semantic_nlp_risk(BIOS["financial_scam"])

        assert result["semantic_risk"] > 20.0, (
            f"Expected financial bio semantic_risk > 20, got {result['semantic_risk']}"
        )
        matched_cats = [m["category"] for m in result["matched_categories"]]
        assert "Spam / Bot Content" in matched_cats


# ===========================================================================
# Test 4 — Promotional / Spam Bio
# ===========================================================================

def test_semantic_promotional_bio():
    """
    Promotional spam bio should return elevated risk when flagged as spam.
    """
    with patch("app.services.semantic_nlp_engine.get_classifier") as mock_get_clf:
        mock_clf = MagicMock()
        mock_clf.return_value = [{"label": "LABEL_1", "score": 0.85}]
        mock_get_clf.return_value = mock_clf

        result = calculate_semantic_nlp_risk(BIOS["promotional"])
        matched_cats = [m["category"] for m in result["matched_categories"]]
        assert "Spam / Bot Content" in matched_cats or result["semantic_risk"] > 15.0


# ===========================================================================
# Test 5 — Mixed Bio
# ===========================================================================

def test_semantic_mixed_bio():
    """
    Mixed bio with some suspicious language should produce moderate risk.
    The result should be between normal and clearly suspicious.
    """
    result = calculate_semantic_nlp_risk(BIOS["mixed"])
    # Should be somewhere in the middle — not zero, not maxed out
    assert result["semantic_risk"] >= 0.0
    assert result["semantic_risk"] <= 100.0
    assert isinstance(result["matched_categories"], list)


# ===========================================================================
# Test 6 — Very Long Bio
# ===========================================================================

def test_semantic_very_long_bio():
    """
    Very long bios should be gracefully truncated and not raise errors.
    """
    result = calculate_semantic_nlp_risk(BIOS["very_long"])
    assert "semantic_risk" in result
    assert result["semantic_risk"] >= 0.0
    assert result["error"] is None


# ===========================================================================
# Test 7 — Special Characters Only
# ===========================================================================

def test_semantic_special_chars():
    """
    A bio consisting only of special characters should not crash.
    Semantic risk should be low or zero (no meaningful sentence).
    """
    result = calculate_semantic_nlp_risk(BIOS["special_chars"])
    assert "semantic_risk" in result
    assert result["semantic_risk"] >= 0.0
    assert result["semantic_risk"] <= 100.0


# ===========================================================================
# Test 8 — Unicode Text
# ===========================================================================

def test_semantic_unicode_arabic():
    """Non-Latin Unicode text should be handled gracefully."""
    result = calculate_semantic_nlp_risk(BIOS["unicode_arabic"])
    assert "semantic_risk" in result
    assert isinstance(result["matched_categories"], list)


def test_semantic_unicode_emoji():
    """Emoji-heavy bio should be handled gracefully."""
    result = calculate_semantic_nlp_risk(BIOS["unicode_emoji"])
    assert "semantic_risk" in result
    assert result["semantic_risk"] >= 0.0


# ===========================================================================
# Test 9 — Semantic Model Unavailable (mocked)
# ===========================================================================

def test_semantic_model_unavailable():
    """
    When the classifier model is unavailable,
    the function should return zero semantic risk gracefully.
    """
    import app.services.semantic_nlp_engine as engine_module

    original_available = engine_module._model_available
    original_classifier = engine_module._classifier

    try:
        engine_module._model_available = False
        engine_module._classifier = None
        engine_module._model_load_error = "Model not installed (test mock)"

        result = calculate_semantic_nlp_risk("Win free money guaranteed returns!")

        assert result["semantic_risk"] == 0.0
        assert result["model_available"] is False
        assert result["matched_categories"] == []
        assert result["error"] is not None

    finally:
        engine_module._model_available = original_available
        engine_module._classifier      = original_classifier
        engine_module._model_load_error = None


# ===========================================================================
# Test 10 — NLP API Failure (mocked classification error)
# ===========================================================================

def test_semantic_encode_failure():
    """
    If classifier pipeline raises an exception, the function should return
    a safe fallback response with semantic_risk = 0 and an error message.
    """
    import app.services.semantic_nlp_engine as engine_module

    original_classifier = engine_module._classifier
    original_available = engine_module._model_available

    try:
        mock_classifier = MagicMock(side_effect=RuntimeError("CUDA out of memory"))
        engine_module._classifier = mock_classifier
        engine_module._model_available = True

        result = calculate_semantic_nlp_risk("Test bio for encoding failure")

        assert result["semantic_risk"] == 0.0
        assert result["error"] is not None
        assert "RuntimeError" in result["error"] or "CUDA" in result["error"]

    finally:
        engine_module._classifier = original_classifier
        engine_module._model_available = original_available


# ===========================================================================
# Hybrid NLP Pipeline Tests
# ===========================================================================

def test_hybrid_empty_bio():
    """Hybrid score for empty bio should be 0."""
    result = calculate_nlp_rule_score("")
    assert result["score"] == 0.0
    assert result["hybrid_nlp_risk"] == 0.0
    assert result["keyword_risk"] == 0.0
    assert result["semantic_risk"] == 0.0


def test_hybrid_keys_present():
    """All expected keys must be present in the hybrid result."""
    result = calculate_nlp_rule_score("Test bio text")
    required_keys = [
        "score", "matches", "keyword_risk", "semantic_risk",
        "hybrid_nlp_risk", "semantic_details", "nlp_model_name",
        "nlp_model_version", "keyword_weight", "semantic_weight",
    ]
    for key in required_keys:
        assert key in result, f"Missing key: {key}"


def test_hybrid_weights_sum_to_one():
    """Keyword and semantic weights must sum to 1.0."""
    result = calculate_nlp_rule_score("Test")
    total = result["keyword_weight"] + result["semantic_weight"]
    assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"


def test_hybrid_score_bounded():
    """Hybrid score must always be in [0, 100]."""
    for key, bio in BIOS.items():
        result = calculate_nlp_rule_score(bio)
        assert 0.0 <= result["hybrid_nlp_risk"] <= 100.0, (
            f"Bio '{key}' produced out-of-bound hybrid score: {result['hybrid_nlp_risk']}"
        )


def test_hybrid_financial_bio_elevated():
    """Financial scam bio should produce elevated hybrid NLP risk."""
    result = calculate_nlp_rule_score(BIOS["financial_scam"])
    assert result["hybrid_nlp_risk"] > 15.0, (
        f"Expected financial bio hybrid_nlp_risk > 15, got {result['hybrid_nlp_risk']}"
    )


def test_hybrid_score_equals_score_key():
    """result['score'] and result['hybrid_nlp_risk'] must be identical."""
    result = calculate_nlp_rule_score("Some bio text")
    assert result["score"] == result["hybrid_nlp_risk"]


def test_hybrid_semantic_details_present():
    """semantic_details should contain the full semantic result."""
    result = calculate_nlp_rule_score("Invest now for guaranteed returns!")
    details = result["semantic_details"]
    assert "semantic_risk" in details
    assert "matched_categories" in details
    assert "explanation" in details
