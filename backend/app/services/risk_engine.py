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


def calculate_profile_rule_risk(profile: dict):
    """
    Calculate rule-based risk from profile characteristics.
    """

    risk = 0
    signals = []

    # Rule 1: Empty biography
    bio_length = profile.get("bio_length") or 0

    if bio_length == 0:
        risk += 10

        signals.append({
            "rule": "empty_bio",
            "weight": 10,
            "message": "Profile has no biography",
            "status": "fail"
        })

    # Rule 2: No profile picture
    has_profile_picture = profile.get("has_profile_picture") or 0

    if has_profile_picture == 0:
        risk += 15

        signals.append({
            "rule": "no_profile_picture",
            "weight": 15,
            "message": "Profile has no profile picture",
            "status": "fail"
        })

    # Rule 3: Very high username digit ratio
    username_digit_ratio = profile.get("username_digit_ratio") or 0

    if username_digit_ratio >= 0.5:
        risk += 15

        signals.append({
            "rule": "high_username_digit_ratio",
            "weight": 15,
            "message": "Username contains a high proportion of digits",
            "status": "fail"
        })

    # Rule 4: Very low follower count
    followers = profile.get("followers") or 0

    if followers < 10:
        risk += 10

        signals.append({
            "rule": "very_low_followers",
            "weight": 10,
            "message": "Profile has very few followers",
            "status": "fail"
        })

    # Rule 5: Very high following/follower imbalance
    following = profile.get("following") or 0

    if followers > 0:

        ratio = following / followers

        if ratio >= 10:
            risk += 15

            signals.append({
                "rule": "high_following_ratio",
                "weight": 15,
                "message": "Following count is much higher than follower count",
                "status": "fail"
            })

    # Keep score between 0 and 100
    risk = min(risk, 100)

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