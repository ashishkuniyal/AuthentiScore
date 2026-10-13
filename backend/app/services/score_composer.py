"""
AuthentiScore — Score Composer & Confidence Engine
===================================================

Provides unified decision logic:
- Confidence calculation (high, medium, low) with explanatory reasons
- Abstention logic
- Declared automation / bot detection
- Account type classification: likely_fake, likely_real, automated_declared, uncertain
- Unified multi-source explanation generator (SHAP + Rules + NLP)
"""

from __future__ import annotations
import re
from typing import Optional, List, Dict, Any


_BOT_KEYWORDS_RE = re.compile(
    r"\b(bot|automated|robot|feed bot|tracker bot|giveaway bot|updater bot|service bot|discord bot|telegram bot)\b",
    re.IGNORECASE,
)


def is_automation_declared(profile_data: dict, bio: str = "") -> bool:
    """
    Check if the account self-identifies as automated or a bot.
    """
    if profile_data.get("automation_declared") in (1, True):
        return True

    text_to_check = f"{profile_data.get('username', '')} {profile_data.get('full_name', '')} {bio or profile_data.get('bio', '')}"
    return bool(_BOT_KEYWORDS_RE.search(text_to_check))


def calculate_scan_confidence(
    profile_data: dict,
    data_completeness: float,
    ml_risk: Optional[float] = None,
    nlp_insufficient: bool = False,
    platform: str = "instagram",
) -> dict:
    """
    Calculate scan confidence (level, value 0.0–1.0, reasons).
    """
    reasons = []
    platform = (platform or "instagram").lower()

    # 1. Base completeness
    if data_completeness >= 0.8:
        val = 0.85
        reasons.append("High profile completeness (majority of core fields observed)")
    elif data_completeness >= 0.5:
        val = 0.65
        reasons.append("Moderate profile completeness (some optional fields missing)")
    else:
        val = 0.35
        reasons.append("Low profile completeness (minimal fields available)")

    # 2. Platform domain calibration
    if platform != "instagram":
        val -= 0.15
        reasons.append(f"Model trained on Instagram data; {platform} scan confidence adjusted")
    else:
        val += 0.05

    # 3. Decision boundary distance (for ML)
    if ml_risk is not None:
        if 40.0 <= ml_risk <= 60.0:
            val -= 0.15
            reasons.append("ML model prediction is near the decision boundary (40%–60%)")
        else:
            val += 0.05

    # 4. Bio adequacy
    if nlp_insufficient:
        val -= 0.10
        reasons.append("Biography was too short or unavailable for NLP text analysis")

    # Clamping
    val = round(max(0.10, min(val, 0.98)), 2)

    if val >= 0.70:
        level = "high"
    elif val >= 0.45:
        level = "medium"
    else:
        level = "low"

    return {
        "level": level,
        "value": val,
        "reasons": reasons,
    }


def determine_account_type(
    final_score: Optional[float],
    is_declared_bot: bool,
    abstain: bool = False,
) -> str:
    """
    Determine account type:
    'automated_declared' | 'likely_fake' | 'likely_real' | 'uncertain'
    """
    if is_declared_bot:
        return "automated_declared"
    if abstain or final_score is None:
        return "uncertain"
    if final_score >= 60.0:
        return "likely_fake"
    if final_score <= 40.0:
        return "likely_real"
    return "uncertain"


def build_unified_reasons(
    top_ml_factors: Optional[List[Dict[str, Any]]],
    rule_signals: Optional[List[Dict[str, Any]]],
    nlp_signals: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Synthesize SHAP, rule triggers, and NLP signals into a unified explanations list.
    """
    reasons: List[Dict[str, Any]] = []

    # 1. Rules signals
    if rule_signals:
        for sig in rule_signals:
            status = sig.get("status", "")
            if status in ("fail", "pass") and sig.get("weight", 0) != 0:
                direction = sig.get("direction")
                if not direction:
                    direction = "lowers" if sig.get("weight", 0) < 0 else "raises"
                
                weight_mag = abs(sig.get("weight", 0))
                impact = "high" if weight_mag >= 15 else ("medium" if weight_mag >= 10 else "low")
                
                reasons.append({
                    "factor": sig.get("rule", "rule"),
                    "name": sig.get("name", sig.get("rule", "Rule")),
                    "direction": direction,
                    "impact": impact,
                    "description": sig.get("message", ""),
                    "source": "rules",
                })

    # 2. Top ML factors (SHAP)
    if top_ml_factors:
        for factor in top_ml_factors:
            feature_name = factor.get("feature", "")
            importance = abs(factor.get("importance", 0.0))
            direction = factor.get("direction", "raises")
            desc = factor.get("description", factor.get("message", f"ML factor: {feature_name}"))
            impact = "high" if importance >= 0.15 else ("medium" if importance >= 0.08 else "low")
            
            reasons.append({
                "factor": feature_name,
                "name": feature_name.replace("_", " ").title(),
                "direction": direction,
                "impact": impact,
                "description": desc,
                "source": "ml",
            })

    # 3. NLP signals
    if nlp_signals and not nlp_signals.get("nlp_insufficient", False):
        matched_phrases = nlp_signals.get("matched_phrases", [])
        matched_cats = nlp_signals.get("matched_categories", [])
        if matched_phrases:
            reasons.append({
                "factor": "bio_suspicious_phrases",
                "name": "Suspicious Bio Phrases",
                "direction": "raises",
                "impact": "high" if len(matched_phrases) >= 2 else "medium",
                "description": f"Bio contains flag words: {', '.join(matched_phrases[:3])}",
                "source": "nlp",
            })
        elif matched_cats:
            reasons.append({
                "factor": "bio_spam_category",
                "name": "Bio Spam Category",
                "direction": "raises",
                "impact": "medium",
                "description": f"Bio matched category: {', '.join(matched_cats[:2])}",
                "source": "nlp",
            })

    # Deduplicate by factor name while preserving priority
    seen = set()
    deduped = []
    for r in reasons:
        if r["factor"] not in seen:
            seen.add(r["factor"])
            deduped.append(r)

    return deduped
