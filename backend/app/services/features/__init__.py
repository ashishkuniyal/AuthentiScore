"""
AuthentiScore — Feature Engine (A3)
===================================

Versioned single definition for training and serving.
Defines both:
  - CORE_FEATURES (9 features available in public benchmark datasets)
  - EXTENDED_FEATURES (24 behavioral, identity & text features)

Schema Version: v4
"""

from __future__ import annotations

from typing import Any, Dict

from app.services.features.account_features import (
    calculate_account_age_days,
    calculate_followers_per_day,
    calculate_following_per_day,
    calculate_is_verified,
    calculate_posts_per_day,
)
from app.services.features.text_features import (
    calculate_bio_digit_ratio,
    calculate_bio_emoji_ratio,
    calculate_bio_uppercase_ratio,
    calculate_has_external_link,
    calculate_link_shortener_in_bio,
    detect_bio_language,
)
from app.services.features.username_features import (
    calculate_display_name_matches_username,
    calculate_username_entropy,
    calculate_username_has_long_digit_run,
    calculate_username_repeated_chars,
)

FEATURE_SCHEMA_VERSION = "v4"

CORE_FEATURES = [
    "followers",
    "following",
    "posts",
    "bio_length",
    "has_profile_picture",
    "is_private",
    "username_digit_ratio",
    "follower_following_ratio",
    "profile_completeness",
]

EXTENDED_FEATURES = CORE_FEATURES + [
    "account_age_days",
    "posts_per_day",
    "followers_per_day",
    "following_per_day",
    "is_verified",
    "has_external_link",
    "link_shortener_in_bio",
    "bio_emoji_ratio",
    "bio_uppercase_ratio",
    "bio_digit_ratio",
    "username_entropy",
    "username_has_long_digit_run",
    "username_repeated_chars",
    "display_name_matches_username",
    "bio_language",
]


def calculate_username_digit_ratio(username: Any) -> float:
    """Calculate the proportion of digits in a username."""
    if not username:
        return 0.0
    u = str(username)
    digit_count = sum(char.isdigit() for char in u)
    return round(digit_count / len(u), 4)


def calculate_follower_following_ratio(
    followers: Any,
    following: Any,
) -> float | None:
    """Calculate followers / following ratio."""
    if followers is None or following is None:
        return None
    try:
        f_in = float(followers)
        f_out = float(following)
        if f_out == 0:
            return f_in
        return round(f_in / f_out, 4)
    except (ValueError, TypeError):
        return None


def calculate_profile_completeness(profile: Dict[str, Any]) -> float:
    """
    Shared definition: Calculate completeness based on available core fields:
    {username, non-empty bio, followers, following, posts, has_profile_picture}.
    """
    username_val = profile.get("username")
    has_username = bool(username_val and str(username_val).strip()) or (profile.get("username_digit_ratio") is not None)

    bio_val = profile.get("bio")
    has_bio = bool(bio_val and str(bio_val).strip()) or (
        profile.get("bio_length") is not None and profile.get("bio_length") > 0
    )

    has_followers = profile.get("followers") is not None
    has_following = profile.get("following") is not None
    has_posts = profile.get("posts") is not None
    has_pic = profile.get("has_profile_picture") is not None

    present_count = sum([has_username, has_bio, has_followers, has_following, has_posts, has_pic])
    return round(present_count / 6.0, 4)


def extract_features(profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract complete features dict.
    Preserves existing core feature output format while augmenting with new v4 features.
    """
    username = profile.get("username") or ""
    bio = profile.get("bio")
    followers = profile.get("followers")
    following = profile.get("following")
    posts = profile.get("posts")

    # Bio length
    if "bio_length" in profile and profile["bio_length"] is not None:
        bio_length = float(profile["bio_length"])
    elif bio is not None:
        bio_length = float(len(str(bio)))
    else:
        bio_length = None

    # Profile picture
    has_pic = profile.get("has_profile_picture")
    if has_pic is not None:
        try:
            has_pic = 1 if int(has_pic) == 1 else 0
        except (ValueError, TypeError):
            has_pic = None

    # Privacy
    is_priv = profile.get("is_private")
    if is_priv is not None:
        try:
            is_priv = 1 if int(is_priv) == 1 else 0
        except (ValueError, TypeError):
            is_priv = None

    # Username digit ratio
    if "username_digit_ratio" in profile and profile["username_digit_ratio"] is not None:
        digit_ratio = float(profile["username_digit_ratio"])
    else:
        digit_ratio = calculate_username_digit_ratio(username)

    # Ratio & Completeness
    ratio = calculate_follower_following_ratio(followers, following)
    completeness = calculate_profile_completeness(profile)

    # Core feature dict
    feat: Dict[str, Any] = {
        "followers": float(followers) if followers is not None else None,
        "following": float(following) if following is not None else None,
        "posts": float(posts) if posts is not None else None,
        "bio_length": bio_length,
        "has_profile_picture": has_pic,
        "is_private": is_priv,
        "username_digit_ratio": digit_ratio,
        "follower_following_ratio": ratio,
        "profile_completeness": completeness,
    }

    # Extended v4 features
    created_at = profile.get("account_created_at") or profile.get("created_at")
    age_days = calculate_account_age_days(created_at)
    ext_url = profile.get("external_url")

    feat["account_age_days"] = age_days
    feat["posts_per_day"] = calculate_posts_per_day(feat["posts"], age_days)
    feat["followers_per_day"] = calculate_followers_per_day(feat["followers"], age_days)
    feat["following_per_day"] = calculate_following_per_day(feat["following"], age_days)
    feat["is_verified"] = calculate_is_verified(profile.get("is_verified"))
    feat["has_external_link"] = calculate_has_external_link(bio, ext_url)
    feat["link_shortener_in_bio"] = calculate_link_shortener_in_bio(bio, ext_url)
    feat["bio_emoji_ratio"] = calculate_bio_emoji_ratio(bio)
    feat["bio_uppercase_ratio"] = calculate_bio_uppercase_ratio(bio)
    feat["bio_digit_ratio"] = calculate_bio_digit_ratio(bio)
    feat["username_entropy"] = calculate_username_entropy(username)
    feat["username_has_long_digit_run"] = calculate_username_has_long_digit_run(username)
    feat["username_repeated_chars"] = calculate_username_repeated_chars(username)
    feat["display_name_matches_username"] = calculate_display_name_matches_username(username, profile.get("display_name"))
    feat["bio_language"] = detect_bio_language(bio)

    return feat
