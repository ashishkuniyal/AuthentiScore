"""
AuthentiScore — Legacy Feature Engine Forwarder
===============================================

Re-exports unified versioned features from app.services.features.
Preserves complete backward compatibility for all existing imports.
"""

from app.services.features import (
    FEATURE_SCHEMA_VERSION,
    CORE_FEATURES,
    EXTENDED_FEATURES,
    calculate_username_digit_ratio,
    calculate_follower_following_ratio,
    calculate_profile_completeness,
    extract_features,
)

FEATURES = CORE_FEATURES