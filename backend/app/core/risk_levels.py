"""
AuthentiScore — Central Risk Levels
=====================================

Single source of truth for risk classification (C5).

DECISION D1: bands are 34 / 67 / 90 (matching the engine documentation).

Exports:
    RISK_BANDS              — tuple of (upper_exclusive, key, label)
    classify_risk(score)    → "Low Risk" | "Medium Risk" | "High Risk" | "Very High Risk"
    risk_key(cls)           → "low" | "medium" | "high" | "very_high" | "insufficient_data"
    is_suspicious(score_or_cls) → bool (High and above)
"""

from __future__ import annotations
from typing import Union

# (upper_exclusive_bound, internal_key, display_label)
RISK_BANDS: tuple[tuple, ...] = (
    (34,    "low",          "Low Risk"),
    (67,    "medium",       "Medium Risk"),
    (90,    "high",         "High Risk"),
    (101,   "very_high",    "Very High Risk"),
)


def classify_risk(score: Union[float, int]) -> str:
    """Return the display label for a 0–100 numeric score."""
    for upper, _key, label in RISK_BANDS:
        if score < upper:
            return label
    return "Very High Risk"


def risk_key(classification: str) -> str:
    """
    Convert a display classification string to its internal key.

    Examples
    --------
    risk_key("High Risk")   → "high"
    risk_key("high")        → "high"
    risk_key("Insufficient Data") → "insufficient_data"
    """
    if not classification:
        return "unknown"
    lower = classification.strip().lower()
    if "insufficient" in lower:
        return "insufficient_data"
    # Normalise to the internal key
    for _upper, key, label in RISK_BANDS:
        if lower in {key, label.lower()}:
            return key
    # Fallback: strip " risk" suffix and replace spaces
    normalised = lower.replace(" risk", "").replace(" ", "_")
    return normalised or "unknown"


def is_suspicious(score_or_classification: Union[float, int, str]) -> bool:
    """
    Return True when the profile is High Risk or above.

    Accepts either a numeric score (0–100) or a classification string.
    """
    if isinstance(score_or_classification, str):
        key = risk_key(score_or_classification)
        return key in {"high", "very_high"}
    return float(score_or_classification) >= 67
