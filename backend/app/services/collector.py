"""
AuthentiScore — Collector Dispatcher
======================================

Entry point for the automated profile collection layer.

Architecture:
    collect_profile(url)
        ↓
    validate_profile_url()     – scheme + platform check
        ↓
    dispatcher selects collector via can_handle()
        ↓
    collector.run()            – collect → normalize → validate
        ↓
    normalized profile dict    – common AuthentiScore schema

If automated collection returns status "failed" or "partial",
the frontend shows the manual fallback form pre-filled with
whatever was collected.

Existing functions (create_manual_profile, get_collection_error,
validate_profile_url, detect_platform, extract_username) are
preserved unchanged so that all existing endpoints continue
to work without modification.
"""

import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

from app.services.collectors.instaloader_collector import InstaLoaderCollector
from app.services.collectors.instagram_collector import InstagramCollector
from app.services.collectors.twitter_collector import TwitterCollector
from app.services.collectors.youtube_collector import YouTubeCollector
from app.services.collectors.github_collector import GitHubCollector
from app.services.collectors.mastodon_collector import MastodonCollector
from app.services.circuit_breaker import get_circuit_breaker

logger = logging.getLogger(__name__)

CORE_PROVENANCE_FIELDS = [
    "username", "followers", "following", "posts", "bio",
    "has_profile_picture", "is_private", "display_name"
]


def classify_error_taxonomy(err_msg: str | None) -> str:
    """Classify error into standard taxonomy (B4)."""
    if not err_msg:
        return "none"
    low = err_msg.lower()
    if "429" in low or "rate limit" in low or "too many requests" in low:
        return "rate_limited"
    if "challenge" in low or "checkpoint" in low or "bot" in low or "403" in low or "login_required" in low:
        return "anti_bot_challenge"
    if "404" in low or "not found" in low or "does not exist" in low:
        return "account_not_found"
    if "suspend" in low or "deactivated" in low:
        return "account_suspended"
    if "timeout" in low or "timed out" in low:
        return "network_timeout"
    return "parse_error"


def build_provenance_and_verification(profile: dict) -> dict:
    """Attach field-level provenance and calculate 'Data verified' status (B4, S8)."""
    source = profile.get("collection_source", "none")
    timestamp = profile.get("collected_at") or datetime.now(timezone.utc).isoformat()
    fields_collected = profile.get("fields_collected", [])

    provenance = {}
    direct_core_count = 0
    is_direct_source = source in {"official_api", "permitted_public_page", "apify", "instaloader"}

    for f in fields_collected:
        conf = 1.0 if is_direct_source else 0.8
        provenance[f] = {
            "source": source,
            "timestamp": timestamp,
            "confidence": conf,
        }
        if f in CORE_PROVENANCE_FIELDS and is_direct_source:
            direct_core_count += 1

    # Decision S8: >= 6 of 8 core fields obtained directly from official source
    data_verified = direct_core_count >= 6
    error_taxonomy = classify_error_taxonomy(profile.get("error"))

    if data_verified:
        trust_level = {
            "code": "verified",
            "label": "Data verified",
            "tooltip": "Collected from verified official/direct source with >=6 confirmed core attributes"
        }
    elif source == "user_provided":
        trust_level = {
            "code": "user_provided",
            "label": "User provided",
            "tooltip": "Profile attributes manually entered by user"
        }
    else:
        trust_level = {
            "code": "unverified",
            "label": "Public page (unverified)",
            "tooltip": "Collected from public web markup without full official verification"
        }

    profile["provenance"] = provenance
    profile["data_verified"] = data_verified
    profile["error_taxonomy"] = error_taxonomy
    profile["trust_level"] = trust_level
    return profile


# ==============================================================
# Supported Platforms
# ==============================================================

SUPPORTED_PLATFORMS = {
    "instagram.com":     "instagram",
    "www.instagram.com": "instagram",
    "twitter.com":       "twitter",
    "www.twitter.com":   "twitter",
    "x.com":             "twitter",
    "www.x.com":         "twitter",
    "youtube.com":       "youtube",
    "www.youtube.com":   "youtube",
    "github.com":        "github",
    "www.github.com":    "github",
    "mastodon.social":   "mastodon",
    "www.mastodon.social":"mastodon",
}


# ==============================================================
# Collector Registry
# ==============================================================
# Collectors are tried in order; the first one that can_handle()
# the URL wins.
#
# Instagram: InstaLoaderCollector (instaloader library) is tried first.
#            InstagramCollector (HTML scraper) is the fallback.
# Twitter/X: TwitterCollector (official API v2, then HTML scraper).

_COLLECTOR_REGISTRY = [
    InstaLoaderCollector(),   # Instagram — instaloader (primary)
    InstagramCollector(),     # Instagram — HTML scraper (fallback)
    TwitterCollector(),       # Twitter/X — API v2 + HTML scraper
    YouTubeCollector(),       # YouTube — ytInitialData extractor
    GitHubCollector(),        # GitHub — API
    MastodonCollector(),      # Mastodon — unauthenticated API
]


# ==============================================================
# URL Validation
# ==============================================================

def detect_platform(profile_url: str) -> str:
    parsed = urlparse(profile_url)
    domain = parsed.netloc.lower()
    return SUPPORTED_PLATFORMS.get(domain, "unknown")


def validate_profile_url(profile_url: str) -> dict:
    parsed = urlparse(profile_url)

    if parsed.scheme not in {"http", "https"}:
        return {
            "valid": False,
            "platform": "unknown",
            "error": "URL must use http or https.",
        }

    platform = detect_platform(profile_url)

    if platform == "unknown":
        return {
            "valid": False,
            "platform": "unknown",
            "error": "Unsupported social media platform.",
        }

    return {
        "valid": True,
        "platform": platform,
        "error": None,
    }


def extract_username(profile_url: str) -> str | None:
    """
    Extract username from a standard public profile URL.
    """
    parsed = urlparse(profile_url)
    path = parsed.path.strip("/")

    if not path:
        return None

    username = path.split("/")[0]
    return username or None


# ==============================================================
# Automated Collection — Primary Entry Point
# ==============================================================

def collect_profile(profile_url: str) -> dict:
    """
    Automated profile collection dispatcher.

    Workflow:
      1. Validate URL (scheme + platform).
      2. Select the appropriate collector via can_handle().
      3. Run collect → normalize → validate.
      4. Return the normalized AuthentiScore profile dict.

    The returned dict always contains:
      collection_status: "success" | "partial" | "failed"
      collection_source: "official_api" | "permitted_public_page" | "none"
      fields_collected:  list of field names that were obtained
      error:             human-readable message if not success

    Does NOT raise exceptions — all errors are captured in the dict.

    POLICY:
      - No authentication bypass.
      - No CAPTCHA solving.
      - No anti-bot bypass.
      - Single request per strategy; no infinite retries.
    """

    # ── 1. Validate URL ──────────────────────────────────────────
    validation = validate_profile_url(profile_url)

    if not validation["valid"]:
        return {
            "collection_status": "failed",
            "collection_source": "none",
            "platform":          validation["platform"],
            "profile_url":       profile_url,
            "username":          None,
            "display_name":      None,
            "bio":               None,
            "followers":         None,
            "following":         None,
            "posts":             None,
            "has_profile_picture": None,
            "is_private":        None,
            "collected_at":      None,
            "fields_collected":  [],
            "error":             validation["error"],
        }

    # ── 2. Find all collectors that can handle this URL ──────────────
    candidates = [c for c in _COLLECTOR_REGISTRY if c.can_handle(profile_url)]

    if not candidates:
        return {
            "collection_status": "failed",
            "collection_source": "none",
            "platform":          validation["platform"],
            "profile_url":       profile_url,
            "username":          extract_username(profile_url),
            "display_name":      None,
            "bio":               None,
            "followers":         None,
            "following":         None,
            "posts":             None,
            "has_profile_picture": None,
            "is_private":        None,
            "collected_at":      None,
            "fields_collected":  [],
            "error":             "No collector available for this platform.",
        }

    # ── 3. Cascade through collectors — stop at first success/partial ─
    # "failed" means the collector could not get even a username;
    # "partial" or "success" means useful data was collected — stop.
    best_profile = None

    for collector in candidates:
        cb_name = type(collector).__name__.lower()
        cb = get_circuit_breaker(cb_name)
        if not cb.can_execute():
            logger.warning("Circuit breaker %s is OPEN; skipping attempt.", cb_name)
            continue

        try:
            profile = collector.run(profile_url)
            if profile.get("collection_status") in ("success", "partial") and len(profile.get("fields_collected", [])) > 0:
                cb.record_success()
            else:
                cb.record_failure()
        except Exception as exc:
            cb.record_failure()
            profile = {
                "collection_status":   "failed",
                "collection_source":   "none",
                "platform":            validation["platform"],
                "profile_url":         profile_url,
                "username":            extract_username(profile_url),
                "display_name":        None,
                "bio":                 None,
                "followers":           None,
                "following":           None,
                "posts":               None,
                "has_profile_picture": None,
                "is_private":          None,
                "collected_at":        None,
                "fields_collected":    [],
                "error":               f"Collector error: {type(exc).__name__}.",
            }

        # Keep the best attempt (most fields collected, or informative error)
        if best_profile is None:
            best_profile = profile
        else:
            best_fields = len(best_profile.get("fields_collected", []))
            curr_fields = len(profile.get("fields_collected", []))
            if curr_fields > best_fields:
                best_profile = profile
            elif curr_fields == best_fields and profile.get("collection_status") != "failed" and best_profile.get("collection_status") == "failed":
                best_profile = profile

        # Stop early only on success, or on partial that contains followers and following (C12)
        status = profile.get("collection_status")
        fields = set(profile.get("fields_collected", []))
        if status == "success":
            best_profile = profile
            break
        if status == "partial" and {"followers", "following"}.issubset(fields):
            best_profile = profile
            break

    profile = best_profile

    # Ensure profile_url is always populated
    if profile:
        profile.setdefault("profile_url", profile_url)
        profile = build_provenance_and_verification(profile)

    return profile


# ==============================================================
# Manual Profile — Fallback
# ==============================================================

def create_manual_profile(
    platform: str,
    profile_url: str,
    username: str,
    followers: float,
    following: float,
    posts: float,
    bio: str,
    has_profile_picture: int,
    is_private: int,
) -> dict:
    """
    Create a profile from user-provided public information.

    This is the fallback when automatic collection is unavailable.
    collection_source is "user_provided" for full auditability.
    """

    res = {
        "collection_status":   "success",
        "collection_source":   "user_provided",

        "platform":            platform,
        "profile_url":         profile_url,
        "username":            username,
        "display_name":        None,

        "followers":           followers,
        "following":           following,
        "posts":               posts,

        "bio":                 bio,
        "bio_length":          len(bio),

        "has_profile_picture": has_profile_picture,
        "is_private":          is_private,

        "fields_collected": [
            "username", "bio", "followers", "following",
            "posts", "has_profile_picture", "is_private",
        ],

        "error": None,
    }
    return build_provenance_and_verification(res)



# ==============================================================
# Error Helper
# ==============================================================

def get_collection_error(profile: dict) -> str | None:
    """
    Return a human-readable collection error, or None on success.
    """

    status = profile.get("collection_status")

    if status == "success":
        return None

    if status == "partial":
        return (
            "Automatic profile collection is incomplete. "
            "Provide permitted profile data manually or "
            "connect an official data source."
        )

    return profile.get(
        "error",
        "Unable to collect profile data.",
    )