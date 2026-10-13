"""
AuthentiScore — URL and Handle Normalizer (B1)
==============================================

Normalizes social media profile URLs, mobile URLs, status/post links,
handles with leading '@', Mastodon webfinger handles, and strips
tracking parameters (UTM, igshid, etc.).
"""

from __future__ import annotations
import re
from typing import Optional, Dict, Any
from urllib.parse import urlparse, parse_qs, urlunparse

RESERVED_SLUGS = {
    "login", "signup", "register", "explore", "reels", "stories",
    "direct", "settings", "accounts", "about", "help", "terms",
    "privacy", "home", "search", "notifications", "messages",
    "i", "intent", "tos", "legal", "jobs", "press", "contact"
}

PLATFORM_HOSTS = {
    "instagram.com": "instagram",
    "www.instagram.com": "instagram",
    "m.instagram.com": "instagram",
    "mobile.instagram.com": "instagram",
    "instagr.am": "instagram",
    "twitter.com": "twitter",
    "www.twitter.com": "twitter",
    "mobile.twitter.com": "twitter",
    "x.com": "twitter",
    "www.x.com": "twitter",
    "youtube.com": "youtube",
    "www.youtube.com": "youtube",
    "m.youtube.com": "youtube",
    "youtu.be": "youtube",
    "tiktok.com": "tiktok",
    "www.tiktok.com": "tiktok",
}


def normalize_profile_input(raw_input: str, default_platform: str = "instagram") -> Dict[str, Any]:
    """
    Parse and normalize a profile handle or URL.

    Returns dict:
    {
        "valid": bool,
        "platform": str,
        "username": str,
        "canonical_url": str,
        "error": Optional[str]
    }
    """
    if not raw_input or not raw_input.strip():
        return {
            "valid": False,
            "platform": default_platform,
            "username": "",
            "canonical_url": "",
            "error": "Input cannot be empty",
        }

    cleaned = raw_input.strip()

    # 1. Handle Mastodon webfinger format: @user@instance.domain
    mastodon_webfinger = re.match(r"^@?([a-zA-Z0-9_\.-]+)@([a-zA-Z0-9_\.-]+\.[a-zA-Z]{2,})$", cleaned)
    if mastodon_webfinger:
        user = mastodon_webfinger.group(1).lower()
        host = mastodon_webfinger.group(2).lower()
        return {
            "valid": True,
            "platform": "mastodon",
            "username": user,
            "canonical_url": f"https://{host}/@{user}",
            "error": None,
        }

    # 2. Check if input is a URL
    if "://" in cleaned or cleaned.startswith("www.") or any(cleaned.lower().startswith(h) for h in PLATFORM_HOSTS):
        if not cleaned.startswith("http://") and not cleaned.startswith("https://"):
            cleaned = "https://" + cleaned

        try:
            parsed = urlparse(cleaned)
        except Exception as exc:
            return {
                "valid": False,
                "platform": default_platform,
                "username": "",
                "canonical_url": "",
                "error": f"Invalid URL structure: {exc}",
            }

        netloc = parsed.netloc.lower()
        # Strip port if any
        if ":" in netloc:
            netloc = netloc.split(":")[0]

        path = parsed.path.strip("/")
        path_parts = [p for p in path.split("/") if p]

        # Identify platform
        platform = PLATFORM_HOSTS.get(netloc)

        # Mastodon check (URL with /@user on unknown domain)
        if not platform:
            if path_parts and path_parts[0].startswith("@"):
                platform = "mastodon"
                user = path_parts[0].lstrip("@").lower()
                return {
                    "valid": True,
                    "platform": "mastodon",
                    "username": user,
                    "canonical_url": f"https://{netloc}/@{user}",
                    "error": None,
                }
            return {
                "valid": False,
                "platform": "unknown",
                "username": "",
                "canonical_url": "",
                "error": f"Unsupported social media domain '{netloc}'",
            }

        # Parse platform-specific paths
        if platform == "instagram":
            if not path_parts:
                return {
                    "valid": False,
                    "platform": "instagram",
                    "username": "",
                    "canonical_url": "",
                    "error": "Instagram URL does not contain a profile username",
                }
            if path_parts[0].lower() in ("p", "reel", "tv", "stories"):
                return {
                    "valid": False,
                    "platform": "instagram",
                    "username": "",
                    "canonical_url": "",
                    "error": f"URL points to a media/post ({path_parts[0]}), not a user profile",
                }
            candidate = path_parts[0].lstrip("@").lower()
            if candidate in RESERVED_SLUGS:
                return {
                    "valid": False,
                    "platform": "instagram",
                    "username": "",
                    "canonical_url": "",
                    "error": f"'{candidate}' is a reserved platform path, not a username",
                }
            return {
                "valid": True,
                "platform": "instagram",
                "username": candidate,
                "canonical_url": f"https://www.instagram.com/{candidate}",
                "error": None,
            }

        elif platform == "twitter":
            if not path_parts:
                return {
                    "valid": False,
                    "platform": "twitter",
                    "username": "",
                    "canonical_url": "",
                    "error": "Twitter/X URL does not contain a username",
                }
            candidate = path_parts[0].lstrip("@").lower()
            if candidate in RESERVED_SLUGS:
                return {
                    "valid": False,
                    "platform": "twitter",
                    "username": "",
                    "canonical_url": "",
                    "error": f"'{candidate}' is a reserved Twitter/X page",
                }
            # Handles status URL: twitter.com/username/status/12345
            return {
                "valid": True,
                "platform": "twitter",
                "username": candidate,
                "canonical_url": f"https://x.com/{candidate}",
                "error": None,
            }

        elif platform == "youtube":
            if not path_parts:
                return {
                    "valid": False,
                    "platform": "youtube",
                    "username": "",
                    "canonical_url": "",
                    "error": "YouTube URL does not contain a channel or handle",
                }
            first = path_parts[0]
            if first.startswith("@"):
                candidate = first.lstrip("@").lower()
                canonical = f"https://www.youtube.com/@{candidate}"
            elif first.lower() in ("c", "channel", "user") and len(path_parts) > 1:
                candidate = path_parts[1].lower()
                canonical = f"https://www.youtube.com/{first.lower()}/{candidate}"
            else:
                candidate = first.lower()
                canonical = f"https://www.youtube.com/{candidate}"

            return {
                "valid": True,
                "platform": "youtube",
                "username": candidate,
                "canonical_url": canonical,
                "error": None,
            }

        elif platform == "tiktok":
            if not path_parts:
                return {
                    "valid": False,
                    "platform": "tiktok",
                    "username": "",
                    "canonical_url": "",
                    "error": "TikTok URL does not contain a profile username",
                }
            candidate = path_parts[0].lstrip("@").lower()
            return {
                "valid": True,
                "platform": "tiktok",
                "username": candidate,
                "canonical_url": f"https://www.tiktok.com/@{candidate}",
                "error": None,
            }

    # 3. Handle plain username or @username
    username_cand = cleaned.lstrip("@").strip()
    # Check valid characters for usernames (alphanumeric, dots, underscores)
    if not re.match(r"^[a-zA-Z0-9_\.]+$", username_cand):
        return {
            "valid": False,
            "platform": default_platform,
            "username": "",
            "canonical_url": "",
            "error": "Username contains invalid characters",
        }

    username_norm = username_cand.lower()
    platform = default_platform.lower()

    if platform == "instagram":
        canonical = f"https://www.instagram.com/{username_norm}"
    elif platform in ("twitter", "x"):
        platform = "twitter"
        canonical = f"https://x.com/{username_norm}"
    elif platform == "youtube":
        canonical = f"https://www.youtube.com/@{username_norm}"
    elif platform == "tiktok":
        canonical = f"https://www.tiktok.com/@{username_norm}"
    else:
        canonical = f"https://{platform}.com/{username_norm}"

    return {
        "valid": True,
        "platform": platform,
        "username": username_norm,
        "canonical_url": canonical,
        "error": None,
    }
