"""
AuthentiScore — Score engine unit tests.

Tests:
  1. Final score equals the weighted sum of components.
  2. Weights sum to exactly 1.0 in normal mode.
  3. Weights sum to exactly 1.0 after NLP renormalization (bio too short).
  4. Score is bounded to [0, 100].
  5. NLP weight is 0.0 when bio is insufficient.
  6. ML + Rules weights correctly renormalize (ML=0.80, Rules=0.20).
  7. Short bio is detected as insufficient.
  8. Link-only bio is detected as insufficient.
  9. Adequate bio is NOT flagged as insufficient.
"""

import pytest
from app.services.risk_engine import (
    build_score_breakdown,
    calculate_unified_risk,
    _is_bio_insufficient,
    _effective_weights,
)


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _bd(ml=50.0, nlp=50.0, rules=50.0, bio="A detailed biography here.", insufficient=None):
    """Shortcut to build a breakdown, optionally forcing nlp_insufficient."""
    if insufficient is not None:
        return build_score_breakdown(ml, nlp, rules, nlp_insufficient=insufficient)
    return build_score_breakdown(ml, nlp, rules, bio=bio)


# ──────────────────────────────────────────────────────────────
# 1. Final score equals the weighted sum of components
# ──────────────────────────────────────────────────────────────

def test_final_equals_weighted_sum_normal():
    ml, nlp, rules = 70.0, 40.0, 20.0
    bd = _bd(ml, nlp, rules)
    expected = round(
        ml   * bd["components"]["ml"]["weight"]
        + nlp   * bd["components"]["nlp"]["weight"]
        + rules * bd["components"]["rules"]["weight"],
        2,
    )
    assert bd["final"] == expected


def test_final_equals_weighted_sum_renormalized():
    ml, nlp, rules = 70.0, 0.0, 20.0
    bd = _bd(ml, nlp, rules, insufficient=True)
    expected = round(
        ml    * bd["components"]["ml"]["weight"]
        + nlp    * bd["components"]["nlp"]["weight"]
        + rules  * bd["components"]["rules"]["weight"],
        2,
    )
    assert bd["final"] == expected


# ──────────────────────────────────────────────────────────────
# 2. Weights sum to 1.0 — normal mode
# ──────────────────────────────────────────────────────────────

def test_weights_sum_to_one_normal():
    bd = _bd(insufficient=False)
    assert bd["weights_sum"] == 1.0


# ──────────────────────────────────────────────────────────────
# 3. Weights sum to 1.0 after NLP renormalization
# ──────────────────────────────────────────────────────────────

def test_weights_sum_to_one_after_renormalization():
    bd = _bd(insufficient=True)
    assert bd["weights_sum"] == 1.0


# ──────────────────────────────────────────────────────────────
# 4. Score bounded to [0, 100]
# ──────────────────────────────────────────────────────────────

def test_score_bounded_max():
    bd = _bd(ml=100.0, nlp=100.0, rules=100.0, insufficient=False)
    assert 0 <= bd["final"] <= 100


def test_score_bounded_min():
    bd = _bd(ml=0.0, nlp=0.0, rules=0.0, insufficient=False)
    assert bd["final"] == 0.0


# ──────────────────────────────────────────────────────────────
# 5. NLP weight is 0 when bio is insufficient
# ──────────────────────────────────────────────────────────────

def test_nlp_weight_zero_when_insufficient():
    bd = _bd(insufficient=True)
    assert bd["components"]["nlp"]["weight"] == 0.0
    assert bd["nlp_insufficient"] is True
    assert bd["signals_used"] == 2


# ──────────────────────────────────────────────────────────────
# 6. Renormalized weights are ML=0.80, Rules=0.20
# ──────────────────────────────────────────────────────────────

def test_renormalized_weights_values():
    w = _effective_weights(nlp_insufficient=True)
    assert w["ml"]    == pytest.approx(0.8, abs=1e-4)
    assert w["rules"] == pytest.approx(0.2, abs=1e-4)
    assert w["nlp"]   == 0.0


# ──────────────────────────────────────────────────────────────
# 7 + 8 + 9. Bio insufficiency detection
# ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("bio", [
    "",
    "   ",
    "Hi",
    "Short",
    "A bot for",          # < 15 chars
])
def test_short_bio_is_insufficient(bio):
    assert _is_bio_insufficient(bio) is True


def test_link_only_bio_is_insufficient():
    assert _is_bio_insufficient("https://example.com/profile") is True
    assert _is_bio_insufficient("http://t.co/abc123  https://bit.ly/xyz") is True


@pytest.mark.parametrize("bio", [
    "A bot for hosting giveaways! Add the bot and type /ghelp.",
    "Photographer | Travel | Coffee lover 📸 DMs open",
    "Official news and updates from the team.",
])
def test_adequate_bio_is_not_insufficient(bio):
    assert _is_bio_insufficient(bio) is False


# ──────────────────────────────────────────────────────────────
# 10. calculate_unified_risk matches build_score_breakdown.final
# ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ml,nlp,rules,insuf", [
    (42.0, 11.1, 0.0,  False),
    (80.0, 60.0, 30.0, False),
    (50.0, 0.0,  20.0, True),
])
def test_unified_risk_matches_breakdown(ml, nlp, rules, insuf):
    score = calculate_unified_risk(ml, nlp, rules, nlp_insufficient=insuf)
    bd    = build_score_breakdown(ml, nlp, rules, nlp_insufficient=insuf)
    assert score == bd["final"]


# ──────────────────────────────────────────────────────────────
# 11. Risk Engine Rules handle missing data (None)
# ──────────────────────────────────────────────────────────────

from app.services.risk_engine import calculate_profile_rule_risk

def test_rules_skip_on_none():
    empty_profile = {
        "bio_length": None,
        "has_profile_picture": None,
        "username_digit_ratio": None,
        "followers": None,
        "following": None,
    }
    result = calculate_profile_rule_risk(empty_profile)
    assert result["profile_rule_risk"] == 0
    
    signals = result["signals"]
    # We have 5 rules: empty_bio, no_profile_picture, high_username_digit_ratio, very_low_followers, high_following_ratio
    assert len(signals) == 5
    for sig in signals:
        assert sig["status"] == "skipped (missing data)"
        assert sig["weight"] == 0


# ──────────────────────────────────────────────────────────────
# 12. Run risk pipeline insufficient data threshold
# ──────────────────────────────────────────────────────────────

from app.routes.scan import run_risk_pipeline

def test_insufficient_data_threshold():
    # Provide < 5 features (e.g. only username and picture)
    profile = {
        "username": "testuser",
        "has_profile_picture": 1,
    }
    result = run_risk_pipeline(profile, bio="")
    
    assert result["classification"] == "Insufficient Data"
    assert result["final_score"] is None
    assert result["data_completeness"] < 1.0
    assert "followers" in result["missing_features"]

def test_full_profile_scores_normally():
    # Provide at least 5 features
    profile = {
        "username": "testuser123",
        "has_profile_picture": 1,
        "followers": 500,
        "following": 100,
        "posts": 50,
        "is_private": 0,
    }
    result = run_risk_pipeline(profile, bio="This is a test bio.")
    
    assert result["classification"] != "Insufficient Data"
    assert result["final_score"] is not None
    assert result["data_completeness"] >= 5/9
    assert result["risk_components"] is not None


# ──────────────────────────────────────────────────────────────
# A6 Rule Engine Tests
# ──────────────────────────────────────────────────────────────

def test_followers_zero_following_positive_ratio_gap():
    profile = {"followers": 0, "following": 50}
    result = calculate_profile_rule_risk(profile)
    sigs = {s["rule"]: s for s in result["signals"]}
    assert "high_following_ratio" in sigs
    assert sigs["high_following_ratio"]["status"] == "fail"
    assert sigs["high_following_ratio"]["weight"] == 15
    assert "Following accounts while having 0 followers" in sigs["high_following_ratio"]["message"]


def test_high_velocity_rule():
    profile = {"posts_per_day": 15.0, "following_per_day": 2.0}
    result = calculate_profile_rule_risk(profile)
    sigs = {s["rule"]: s for s in result["signals"]}
    assert "high_velocity" in sigs
    assert sigs["high_velocity"]["status"] == "fail"
    assert sigs["high_velocity"]["weight"] == 15


def test_shortener_in_bio_rule():
    profile = {"link_shortener_in_bio": 1}
    result = calculate_profile_rule_risk(profile)
    sigs = {s["rule"]: s for s in result["signals"]}
    assert "shortener_in_bio" in sigs
    assert sigs["shortener_in_bio"]["status"] == "fail"
    assert sigs["shortener_in_bio"]["weight"] == 10


def test_trust_rules_lower_risk():
    # Base risk profile
    profile_base = {
        "bio_length": 0,       # +10
        "has_profile_picture": 0, # +15
    }
    res_base = calculate_profile_rule_risk(profile_base)
    assert res_base["profile_rule_risk"] == 25

    # With verified and aged account trust rules
    profile_trusted = {
        "bio_length": 0,       # +10
        "has_profile_picture": 0, # +15
        "is_verified": 1,      # -20
        "account_age_days": 800, # -10
    }
    res_trusted = calculate_profile_rule_risk(profile_trusted)
    # 25 - 20 - 10 = -5, clamped to 0
    assert res_trusted["profile_rule_risk"] == 0
    sigs = {s["rule"]: s for s in res_trusted["signals"]}
    assert sigs["verified_account"]["direction"] == "lowers"
    assert sigs["aged_account"]["direction"] == "lowers"


def test_declared_automation_rule():
    profile = {"automation_declared": 1}
    result = calculate_profile_rule_risk(profile)
    sigs = {s["rule"]: s for s in result["signals"]}
    assert "automation_declared" in sigs
    assert sigs["automation_declared"]["direction"] == "neutral"

