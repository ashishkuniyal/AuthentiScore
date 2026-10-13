"""
AuthentiScore — Score Composition, Confidence & Bot Handling Tests (A7 & A8)
===========================================================================

Tests:
1. Declared bot fixture (@GiveawayBot) labeled as 'automated_declared', not fake.
2. Confidence score and level computation.
3. Abstention logic.
4. Account type classification boundaries.
5. Unified explanations structure (direction: 'raises'|'lowers', source).
"""

import pytest
from app.services.score_composer import (
    is_automation_declared,
    calculate_scan_confidence,
    determine_account_type,
    build_unified_reasons,
)
from app.routes.scan import run_risk_pipeline


def test_declared_bot_giveaway_bot():
    """
    Declared bot fixture @GiveawayBot should be classified as
    account_type: 'automated_declared' and classification: 'Automated (Declared)',
    NOT as 'High Risk' or fake.
    """
    giveaway_bot_profile = {
        "username": "GiveawayBot",
        "platform": "instagram",
        "bio": "A bot for hosting giveaways! Add the bot and type /ghelp.",
        "followers": 5000,
        "following": 10,
        "posts": 100,
        "has_profile_picture": 1,
        "is_private": 0,
        "is_verified": 0,
    }

    assert is_automation_declared(giveaway_bot_profile, giveaway_bot_profile["bio"]) is True

    result = run_risk_pipeline(giveaway_bot_profile, bio=giveaway_bot_profile["bio"])

    assert result["account_type"] == "automated_declared"
    assert result["classification"] == "Automated (Declared)"
    assert result["classification"] != "High Risk"
    assert result["classification"] != "Very High Risk"


def test_confidence_calculation_levels():
    """High completeness produces high confidence; sparse completeness produces lower confidence."""
    # High completeness profile
    high_conf = calculate_scan_confidence(
        profile_data={"username": "alice"},
        data_completeness=1.0,
        ml_risk=10.0,
        nlp_insufficient=False,
        platform="instagram",
    )
    assert high_conf["level"] == "high"
    assert high_conf["value"] >= 0.70
    assert len(high_conf["reasons"]) > 0

    # Low completeness profile on non-instagram platform near decision boundary
    low_conf = calculate_scan_confidence(
        profile_data={"username": "bob"},
        data_completeness=0.3,
        ml_risk=52.0,
        nlp_insufficient=True,
        platform="twitter",
    )
    assert low_conf["level"] in ("low", "medium")
    assert low_conf["value"] < 0.60


def test_account_type_determinations():
    """Account type classification respects boundaries."""
    assert determine_account_type(final_score=85.0, is_declared_bot=False) == "likely_fake"
    assert determine_account_type(final_score=20.0, is_declared_bot=False) == "likely_real"
    assert determine_account_type(final_score=50.0, is_declared_bot=False) == "uncertain"
    assert determine_account_type(final_score=85.0, is_declared_bot=True) == "automated_declared"
    assert determine_account_type(final_score=None, is_declared_bot=False, abstain=True) == "uncertain"


def test_unified_reasons_structure():
    """Unified reasons must combine ML, Rules, and NLP into consistent schema."""
    ml_factors = [
        {"feature": "username_digit_ratio", "importance": 0.25, "direction": "raises", "message": "High digits in username"}
    ]
    rule_signals = [
        {"rule": "no_profile_picture", "name": "No profile picture", "weight": 15, "direction": "raises", "status": "fail", "message": "No avatar"},
        {"rule": "verified_account", "name": "Verified badge", "weight": -20, "direction": "lowers", "status": "pass", "message": "Verified account"}
    ]
    nlp_signals = {
        "nlp_insufficient": False,
        "matched_phrases": ["guaranteed profit"],
        "matched_categories": ["Financial / Crypto Scams"]
    }

    reasons = build_unified_reasons(ml_factors, rule_signals, nlp_signals)

    assert len(reasons) >= 3
    for r in reasons:
        assert "factor" in r
        assert "direction" in r
        assert r["direction"] in ("raises", "lowers", "neutral")
        assert "impact" in r
        assert r["impact"] in ("high", "medium", "low")
        assert "source" in r
        assert r["source"] in ("ml", "rules", "nlp")
