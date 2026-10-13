# --------------------------------------------------
# AuthentiScore Risk Engine
# --------------------------------------------------
#
# Weights:
#   Normal   (bio analyzable): ML=60%  NLP=25%  Rules=15%
#   Reduced  (bio too short):  ML=80%  NLP= 0%  Rules=20%
#                              derived as 0.60/0.75 and 0.15/0.75
# --------------------------------------------------

# Minimum bio character count needed for meaningful NLP analysis.
NLP_MIN_BIO_CHARS = 15

# Base weights (normal mode)
_W_ML    = 0.60
_W_NLP   = 0.25
_W_RULES = 0.15


def _is_bio_insufficient(bio: str) -> bool:
    """Return True when the bio is too short for reliable NLP analysis."""
    stripped = (bio or "").strip()
    # Also flag link-only bios (no real words)
    if not stripped or len(stripped) < NLP_MIN_BIO_CHARS:
        return True
    # A bio that is purely a URL and nothing else
    import re
    url_only = re.fullmatch(r"(https?://\S+\s*)+", stripped)
    if url_only:
        return True
    return False


def _effective_weights(nlp_insufficient: bool) -> dict:
    """
    Return the weights actually used in the final score calculation.

    When NLP cannot be computed (bio too short / link-only), redistribute
    its 25 pp share proportionally to ML and Rules:
        ML    = 0.60 / (0.60 + 0.15) = 0.800
        Rules = 0.15 / (0.60 + 0.15) = 0.200
    """
    if nlp_insufficient:
        total = _W_ML + _W_RULES          # 0.75
        return {
            "ml":    round(_W_ML    / total, 4),   # 0.8
            "nlp":   0.0,
            "rules": round(_W_RULES / total, 4),   # 0.2
        }
    return {"ml": _W_ML, "nlp": _W_NLP, "rules": _W_RULES}


import json
import os
from pathlib import Path

_RULES_CONFIG_PATH = Path(__file__).parent / "rules_config.json"
_DEFAULT_RULES_CONFIG = {
    "empty_bio": {"name": "Empty biography", "weight": 10, "direction": "raises", "enabled": True, "description": "Profile has no biography"},
    "no_profile_picture": {"name": "No profile picture", "weight": 15, "direction": "raises", "enabled": True, "description": "Profile has no profile picture"},
    "high_username_digit_ratio": {"name": "High username digit ratio", "weight": 15, "direction": "raises", "threshold": 0.5, "enabled": True, "description": "Username contains a high proportion of digits"},
    "very_low_followers": {"name": "Very low follower count", "weight": 10, "direction": "raises", "threshold": 10, "enabled": True, "description": "Profile has very few followers"},
    "high_following_ratio": {"name": "High following/follower imbalance", "weight": 15, "direction": "raises", "threshold": 10.0, "enabled": True, "description": "Following count is much higher than follower count"},
    "high_velocity": {"name": "Abnormal activity velocity", "weight": 15, "direction": "raises", "posts_per_day_threshold": 10.0, "following_per_day_threshold": 50.0, "enabled": True, "description": "Account activity rate is abnormally high"},
    "shortener_in_bio": {"name": "URL shortener in bio", "weight": 10, "direction": "raises", "enabled": True, "description": "Biography contains obfuscated short-link"},
    "verified_account": {"name": "Platform verified badge", "weight": -20, "direction": "lowers", "enabled": True, "description": "Account is verified by platform"},
    "aged_account": {"name": "Established account age", "weight": -10, "direction": "lowers", "age_days_threshold": 730, "enabled": True, "description": "Account is established and older than 2 years"},
    "automation_declared": {"name": "Self-declared automated account", "weight": 0, "direction": "neutral", "enabled": True, "description": "Account explicitly identifies as automated or bot"},
}

def load_rules_config() -> dict:
    """Load rule configuration from rules_config.json or return default."""
    try:
        if _RULES_CONFIG_PATH.exists():
            with open(_RULES_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return _DEFAULT_RULES_CONFIG


def calculate_profile_rule_risk(profile: dict):
    """
    Calculate rule-based risk from profile characteristics using data-driven rules.
    """
    rules_cfg = load_rules_config()
    risk = 0
    signals = []

    # Rule 1: Empty biography
    cfg = rules_cfg.get("empty_bio", {})
    if cfg.get("enabled", True):
        bio_length = profile.get("bio_length")
        if "bio_length" in profile and bio_length is None:
            signals.append({
                "rule": "empty_bio",
                "name": cfg.get("name", "Empty biography"),
                "weight": 0,
                "direction": cfg.get("direction", "raises"),
                "message": "Biography length not available",
                "status": "skipped (missing data)"
            })
        elif bio_length is not None and bio_length == 0:
            w = cfg.get("weight", 10)
            risk += w
            signals.append({
                "rule": "empty_bio",
                "name": cfg.get("name", "Empty biography"),
                "weight": w,
                "direction": cfg.get("direction", "raises"),
                "message": "Profile has no biography",
                "status": "fail"
            })

    # Rule 2: No profile picture
    cfg = rules_cfg.get("no_profile_picture", {})
    if cfg.get("enabled", True):
        has_profile_picture = profile.get("has_profile_picture")
        if "has_profile_picture" in profile and has_profile_picture is None:
            signals.append({
                "rule": "no_profile_picture",
                "name": cfg.get("name", "No profile picture"),
                "weight": 0,
                "direction": cfg.get("direction", "raises"),
                "message": "Profile picture status not available",
                "status": "skipped (missing data)"
            })
        elif has_profile_picture is not None and has_profile_picture == 0:
            w = cfg.get("weight", 15)
            risk += w
            signals.append({
                "rule": "no_profile_picture",
                "name": cfg.get("name", "No profile picture"),
                "weight": w,
                "direction": cfg.get("direction", "raises"),
                "message": "Profile has no profile picture",
                "status": "fail"
            })

    # Rule 3: Very high username digit ratio
    cfg = rules_cfg.get("high_username_digit_ratio", {})
    if cfg.get("enabled", True):
        username_digit_ratio = profile.get("username_digit_ratio")
        thresh = cfg.get("threshold", 0.5)
        if "username_digit_ratio" in profile and username_digit_ratio is None:
            signals.append({
                "rule": "high_username_digit_ratio",
                "name": cfg.get("name", "High username digit ratio"),
                "weight": 0,
                "direction": cfg.get("direction", "raises"),
                "message": "Username digit ratio not available",
                "status": "skipped (missing data)"
            })
        elif username_digit_ratio is not None and username_digit_ratio >= thresh:
            w = cfg.get("weight", 15)
            risk += w
            signals.append({
                "rule": "high_username_digit_ratio",
                "name": cfg.get("name", "High username digit ratio"),
                "weight": w,
                "direction": cfg.get("direction", "raises"),
                "message": "Username contains a high proportion of digits",
                "status": "fail"
            })

    # Rule 4: Very low follower count
    cfg = rules_cfg.get("very_low_followers", {})
    if cfg.get("enabled", True):
        followers = profile.get("followers")
        thresh = cfg.get("threshold", 10)
        if "followers" in profile and followers is None:
            signals.append({
                "rule": "very_low_followers",
                "name": cfg.get("name", "Very low follower count"),
                "weight": 0,
                "direction": cfg.get("direction", "raises"),
                "message": "Follower count not available",
                "status": "skipped (missing data)"
            })
        elif followers is not None and followers < thresh:
            w = cfg.get("weight", 10)
            risk += w
            signals.append({
                "rule": "very_low_followers",
                "name": cfg.get("name", "Very low follower count"),
                "weight": w,
                "direction": cfg.get("direction", "raises"),
                "message": "Profile has very few followers",
                "status": "fail"
            })

    # Rule 5: Very high following/follower imbalance (with followers == 0 ratio fix)
    cfg = rules_cfg.get("high_following_ratio", {})
    if cfg.get("enabled", True):
        following = profile.get("following")
        followers = profile.get("followers")
        thresh = cfg.get("threshold", 10.0)
        has_keys = ("following" in profile) or ("followers" in profile)

        if has_keys and (following is None or followers is None):
            signals.append({
                "rule": "high_following_ratio",
                "name": cfg.get("name", "High following/follower imbalance"),
                "weight": 0,
                "direction": cfg.get("direction", "raises"),
                "message": "Following/follower counts not available",
                "status": "skipped (missing data)"
            })
        elif followers is not None and following is not None:
            w = cfg.get("weight", 15)
            if followers == 0 and following > 0:
                risk += w
                signals.append({
                    "rule": "high_following_ratio",
                    "name": cfg.get("name", "High following/follower imbalance"),
                    "weight": w,
                    "direction": cfg.get("direction", "raises"),
                    "message": "Following accounts while having 0 followers",
                    "status": "fail"
                })
            elif followers > 0:
                ratio = following / followers
                if ratio >= thresh:
                    risk += w
                    signals.append({
                        "rule": "high_following_ratio",
                        "name": cfg.get("name", "High following/follower imbalance"),
                        "weight": w,
                        "direction": cfg.get("direction", "raises"),
                        "message": "Following count is much higher than follower count",
                        "status": "fail"
                    })

    # Rule 6: High Velocity (A6)
    cfg = rules_cfg.get("high_velocity", {})
    if cfg.get("enabled", True):
        posts_per_day = profile.get("posts_per_day")
        following_per_day = profile.get("following_per_day")
        p_thresh = cfg.get("posts_per_day_threshold", 10.0)
        f_thresh = cfg.get("following_per_day_threshold", 50.0)
        if ("posts_per_day" in profile or "following_per_day" in profile):
            if posts_per_day is None and following_per_day is None:
                signals.append({
                    "rule": "high_velocity",
                    "name": cfg.get("name", "Abnormal activity velocity"),
                    "weight": 0,
                    "direction": cfg.get("direction", "raises"),
                    "message": "Account velocity data not available",
                    "status": "skipped (missing data)"
                })
            elif (posts_per_day is not None and posts_per_day > p_thresh) or \
                 (following_per_day is not None and following_per_day > f_thresh):
                w = cfg.get("weight", 15)
                risk += w
                signals.append({
                    "rule": "high_velocity",
                    "name": cfg.get("name", "Abnormal activity velocity"),
                    "weight": w,
                    "direction": cfg.get("direction", "raises"),
                    "message": "Account activity rate is abnormally high",
                    "status": "fail"
                })

    # Rule 7: Shortener-only or shortener in bio (A6)
    cfg = rules_cfg.get("shortener_in_bio", {})
    if cfg.get("enabled", True):
        shortener = profile.get("link_shortener_in_bio")
        if "link_shortener_in_bio" in profile:
            if shortener is None:
                signals.append({
                    "rule": "shortener_in_bio",
                    "name": cfg.get("name", "URL shortener in bio"),
                    "weight": 0,
                    "direction": cfg.get("direction", "raises"),
                    "message": "Bio link check not available",
                    "status": "skipped (missing data)"
                })
            elif shortener == 1:
                w = cfg.get("weight", 10)
                risk += w
                signals.append({
                    "rule": "shortener_in_bio",
                    "name": cfg.get("name", "URL shortener in bio"),
                    "weight": w,
                    "direction": cfg.get("direction", "raises"),
                    "message": "Bio contains URL shortener or obfuscated redirect link",
                    "status": "fail"
                })

    # Rule 8: Trust Rule - Verified Account (A6)
    cfg = rules_cfg.get("verified_account", {})
    if cfg.get("enabled", True):
        is_verified = profile.get("is_verified")
        if is_verified == 1:
            w = cfg.get("weight", -20)
            risk += w  # w is negative, lowering risk
            signals.append({
                "rule": "verified_account",
                "name": cfg.get("name", "Platform verified badge"),
                "weight": w,
                "direction": cfg.get("direction", "lowers"),
                "message": "Account has official platform verification badge",
                "status": "pass"
            })

    # Rule 9: Trust Rule - Established Account Age (A6)
    cfg = rules_cfg.get("aged_account", {})
    if cfg.get("enabled", True):
        age_days = profile.get("account_age_days")
        age_thresh = cfg.get("age_days_threshold", 730)
        if age_days is not None and age_days >= age_thresh:
            w = cfg.get("weight", -10)
            risk += w  # w is negative
            signals.append({
                "rule": "aged_account",
                "name": cfg.get("name", "Established account age"),
                "weight": w,
                "direction": cfg.get("direction", "lowers"),
                "message": f"Account is established ({int(age_days)} days old)",
                "status": "pass"
            })

    # Rule 10: Declared Bot / Automation (A6)
    cfg = rules_cfg.get("automation_declared", {})
    if cfg.get("enabled", True):
        automation_declared = profile.get("automation_declared")
        if automation_declared == 1:
            signals.append({
                "rule": "automation_declared",
                "name": cfg.get("name", "Self-declared automated account"),
                "weight": 0,
                "direction": "neutral",
                "message": "Account explicitly identifies as automated or bot",
                "status": "pass"
            })

    # Keep score between 0 and 100
    risk = max(0, min(risk, 100))

    return {
        "profile_rule_risk": risk,
        "signals": signals
    }


# --------------------------------------------------
# Unified Risk
# --------------------------------------------------

def calculate_unified_risk(
    ml_risk: float,
    nlp_risk: float,
    rule_risk: float,
    nlp_insufficient: bool = False
) -> float:
    """
    Combine ML, NLP and rule-based risk into a single 0-100 score.

    When nlp_insufficient=True the NLP component is excluded and
    the remaining weights are renormalized.
    """
    weights = _effective_weights(nlp_insufficient)

    final_score = (
        (ml_risk   * weights["ml"])
        + (nlp_risk  * weights["nlp"])
        + (rule_risk * weights["rules"])
    )

    return round(min(max(final_score, 0), 100), 2)


# --------------------------------------------------
# Score Breakdown (canonical object returned by the API)
# --------------------------------------------------

def build_score_breakdown(
    ml_risk: float,
    nlp_risk: float,
    rule_risk: float,
    nlp_insufficient: bool = None,
    bio: str = ""
) -> dict:
    """
    Build the canonical score_breakdown dict returned in every API response.

    Shape:
    {
        "components": {
            "ml":    {"raw": float, "weight": float, "points": float},
            "nlp":   {"raw": float, "weight": float, "points": float},
            "rules": {"raw": float, "weight": float, "points": float},
        },
        "weights_sum": float,       # must equal 1.0
        "final": float,             # sum of points, == final_score
        "nlp_insufficient": bool,   # True when bio was too short to analyze
        "signals_used": int,        # 2 or 3
    }
    """
    if nlp_insufficient is None:
        nlp_insufficient = _is_bio_insufficient(bio)

    weights = _effective_weights(nlp_insufficient)

    components = {
        "ml": {
            "raw":    round(float(ml_risk),   2),
            "weight": weights["ml"],
            "points": round(float(ml_risk)   * weights["ml"],    2),
        },
        "nlp": {
            "raw":    round(float(nlp_risk),  2),
            "weight": weights["nlp"],
            "points": round(float(nlp_risk)  * weights["nlp"],   2),
        },
        "rules": {
            "raw":    round(float(rule_risk), 2),
            "weight": weights["rules"],
            "points": round(float(rule_risk) * weights["rules"], 2),
        },
    }

    weights_sum = round(
        components["ml"]["weight"]
        + components["nlp"]["weight"]
        + components["rules"]["weight"],
        4,
    )

    # Compute final from unrounded products (same arithmetic as calculate_unified_risk)
    # to guarantee exact equality between the two functions.
    final = round(
        min(max(
            float(ml_risk)   * weights["ml"]
            + float(nlp_risk)  * weights["nlp"]
            + float(rule_risk) * weights["rules"],
            0,
        ), 100),
        2,
    )

    signals_used = 2 if nlp_insufficient else 3

    return {
        "components":       components,
        "weights_sum":      weights_sum,
        "final":            final,
        "nlp_insufficient": nlp_insufficient,
        "signals_used":     signals_used,
    }


# --------------------------------------------------
# Risk Classification
# --------------------------------------------------

def classify_risk(score: float):

    if score < 34:
        return "Low Risk"

    elif score < 67:
        return "Medium Risk"

    elif score < 90:
        return "High Risk"

    else:
        return "Very High Risk"