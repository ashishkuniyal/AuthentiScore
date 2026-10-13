"""
AuthentiScore — Account-Level Behavioral Features (A3)
=======================================================
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def calculate_account_age_days(
    created_at: Any,
    now: Optional[datetime] = None,
) -> Optional[float]:
    """
    Calculate account age in days from creation timestamp.
    Supported on: Twitter/X, GitHub, Mastodon.
    Returns None if creation timestamp is unavailable (e.g. standard Instagram).
    """
    if not created_at:
        return None

    if now is None:
        now = datetime.now(timezone.utc)

    dt: Optional[datetime] = None
    if isinstance(created_at, datetime):
        dt = created_at
    elif isinstance(created_at, str):
        created_str = created_at.strip()
        if not created_str:
            return None
        # Try ISO format
        try:
            dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        except Exception:
            # Try Twitter date format e.g. 'Mon Jan 01 00:00:00 +0000 2024'
            try:
                dt = datetime.strptime(created_str, "%a %b %d %H:%M:%S %z %Y")
            except Exception:
                try:
                    dt = datetime.strptime(created_str, "%Y-%m-%d")
                except Exception:
                    return None

    if dt is None:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    age_days = (now - dt).total_seconds() / 86400.0
    return round(max(0.0, age_days), 2)


def calculate_posts_per_day(
    posts: Optional[float],
    age_days: Optional[float],
) -> Optional[float]:
    """
    Calculate posting frequency (posts / age in days).
    Returns None if either posts or age_days is unavailable.
    """
    if posts is None or age_days is None:
        return None
    effective_days = max(float(age_days), 1.0)
    return round(float(posts) / effective_days, 4)


def calculate_followers_per_day(
    followers: Optional[float],
    age_days: Optional[float],
) -> Optional[float]:
    """
    Calculate follower velocity (followers / age in days).
    High burst velocity on very new accounts can indicate follower buying.
    Returns None if either followers or age_days is unavailable.
    """
    if followers is None or age_days is None:
        return None
    effective_days = max(float(age_days), 1.0)
    return round(float(followers) / effective_days, 4)


def calculate_following_per_day(
    following: Optional[float],
    age_days: Optional[float],
) -> Optional[float]:
    """
    Calculate following velocity (following / age in days).
    Rapid aggressive following on young accounts indicates bot/mass-following.
    Returns None if either following or age_days is unavailable.
    """
    if following is None or age_days is None:
        return None
    effective_days = max(float(age_days), 1.0)
    return round(float(following) / effective_days, 4)


def calculate_is_verified(is_verified: Any) -> Optional[int]:
    """
    Convert verification status to binary flag {0, 1} or None.
    Supported on: Instagram, Twitter/X, Mastodon, YouTube.
    """
    if is_verified is None:
        return None
    if isinstance(is_verified, bool):
        return 1 if is_verified else 0
    if isinstance(is_verified, (int, float)):
        return 1 if int(is_verified) == 1 else 0
    if isinstance(is_verified, str):
        return 1 if is_verified.lower() in {"true", "1", "yes", "verified"} else 0
    return 0
