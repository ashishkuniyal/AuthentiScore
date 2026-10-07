"""
AuthentiScore — InstaLoaderCollector
======================================

Collects public Instagram profile data using the instaloader library.

Collection strategy:
  1. If INSTAGRAM_USERNAME + INSTAGRAM_PASSWORD are set in .env:
     → Authenticates with Instagram using a session (much richer data,
       bypasses most rate limits, gets all numeric fields reliably).
  2. If credentials are NOT set:
     → Unauthenticated instaloader access (works for many public profiles,
       may fail for private or rate-limited accounts).
  3. On any instaloader failure:
     → Gracefully falls back to the existing HTML/OpenGraph scraper
       (InstagramCollector) so the manual form is still shown correctly.

Data collected when successful:
  - username, full name (display_name), biography (bio)
  - followers, following, posts count
  - has_profile_picture, is_private, is_verified

POLICY:
  - Credentials are read from .env only — never from user input.
  - No CAPTCHA solving, no anti-bot bypass.
  - Does not access private posts, DMs, or stories.
  - Single attempt per scan; no retry loops.
  - If instaloader session file already exists on disk it is reused
    to avoid unnecessary re-authentication.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from urllib.parse import urlparse

from app.services.collectors.base_collector import BaseCollector
from app.services.collectors.generic_public_collector import (
    compute_fields_collected,
    parse_bool_to_int,
    utc_now_iso,
)

logger = logging.getLogger(__name__)

INSTAGRAM_DOMAINS = {
    "instagram.com",
    "www.instagram.com",
}

# Session file stored next to this file so it persists across restarts.
_SESSION_DIR = Path(__file__).parent / ".instaloader_sessions"
_SESSION_DIR.mkdir(exist_ok=True)


# ==============================================================
# Singleton loader — created once per process
# ==============================================================

_loader = None


def _get_loader():
    """
    Return (or create) the shared instaloader.Instaloader instance.

    If INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD are configured in .env,
    an authenticated session is used.  Otherwise the loader runs
    anonymously.

    Calling this function multiple times returns the same instance.
    """
    global _loader

    if _loader is not None:
        return _loader

    try:
        import instaloader  # type: ignore

        ig_username = os.getenv("INSTAGRAM_USERNAME", "").strip()
        ig_password = os.getenv("INSTAGRAM_PASSWORD", "").strip()

        loader = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            quiet=True,
        )

        if ig_username and ig_password:
            session_file = _SESSION_DIR / f"{ig_username}.session"

            # Reuse existing session to avoid re-authentication on every restart
            if session_file.exists():
                try:
                    loader.load_session_from_file(ig_username, str(session_file))
                    logger.info(
                        "InstaLoader: Restored session for @%s", ig_username
                    )
                except Exception as exc:
                    logger.warning(
                        "InstaLoader: Could not restore session (%s) — "
                        "re-authenticating.", exc
                    )
                    _login_and_save(loader, ig_username, ig_password, session_file)
            else:
                _login_and_save(loader, ig_username, ig_password, session_file)
        else:
            logger.info(
                "InstaLoader: No Instagram credentials configured — "
                "running anonymously (public profiles only)."
            )

        _loader = loader
        return _loader

    except ImportError:
        logger.error(
            "InstaLoader: instaloader is not installed. "
            "Run: pip install instaloader"
        )
        return None

    except Exception as exc:
        logger.error("InstaLoader: Loader initialisation failed: %s", exc)
        return None


def _login_and_save(loader, username: str, password: str, session_file: Path):
    """Authenticate and save the session file for future reuse."""
    try:
        loader.login(username, password)
        loader.save_session_to_file(str(session_file))
        logger.info(
            "InstaLoader: Logged in as @%s and saved session.", username
        )
    except Exception as exc:
        logger.error(
            "InstaLoader: Login failed for @%s: %s", username, exc
        )
        raise


# ==============================================================
# InstaLoaderCollector
# ==============================================================

class InstaLoaderCollector(BaseCollector):
    """
    Instagram profile collector using the instaloader library.

    Registered in the dispatcher BEFORE InstagramCollector so it is
    tried first.  Falls back to InstagramCollector's HTML strategy on
    any failure.
    """

    # ── BaseCollector interface ──────────────────────────────────────

    def can_handle(self, url: str) -> bool:
        try:
            domain = urlparse(url).netloc.lower()
            return domain in INSTAGRAM_DOMAINS
        except Exception:
            return False

    def collect(self, url: str) -> dict:
        username = self._extract_username(url)
        if not username:
            return {
                "success": False,
                "url": url,
                "username": None,
                "error": "Unable to extract username from Instagram URL.",
            }

        loader = _get_loader()

        if loader is None:
            return {
                "success": False,
                "url": url,
                "username": username,
                "error": "instaloader is not available.",
            }

        try:
            import instaloader  # type: ignore

            logger.info("InstaLoader: Fetching profile for @%s", username)
            profile = instaloader.Profile.from_username(loader.context, username)

            followers = profile.followers
            following = profile.followees
            posts     = profile.mediacount
            bio       = profile.biography or None
            has_pic   = parse_bool_to_int(bool(profile.profile_pic_url))
            is_priv   = parse_bool_to_int(profile.is_private)

            return {
                "success":             True,
                "url":                 url,
                "username":            profile.username,
                "display_name":        profile.full_name or None,
                "bio":                 bio,
                "followers":           float(followers),
                "following":           float(following),
                "posts":               float(posts),
                "has_profile_picture": has_pic,
                "is_private":          is_priv,
                "is_verified":         profile.is_verified,
                "collection_source":   _source_label(),
                "error":               None,
            }

        except Exception as exc:
            err_str = str(exc)
            logger.warning(
                "InstaLoader: Failed to fetch @%s: %s", username, err_str
            )

            # Specific user-friendly messages for common failures
            if "Private" in err_str or "private" in err_str:
                friendly = "This Instagram profile is private."
            elif "not exist" in err_str or "ProfileNotExistsException" in type(exc).__name__:
                friendly = "Instagram profile not found."
            elif "login" in err_str.lower() or "LoginRequired" in type(exc).__name__:
                friendly = (
                    "Instagram requires login to view this profile. "
                    "Add INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD to .env."
                )
            elif "429" in err_str or "RateLimitError" in type(exc).__name__:
                friendly = "Instagram rate limit reached. Please try again later."
            else:
                friendly = f"Instagram collection failed: {err_str[:120]}"

            return {
                "success": False,
                "url":     url,
                "username": username,
                "error":   friendly,
            }

    def normalize(self, raw: dict) -> dict:
        profile = {
            "platform":            "instagram",
            "profile_url":         raw.get("url", ""),
            "username":            raw.get("username"),
            "display_name":        raw.get("display_name"),
            "bio":                 raw.get("bio"),
            "followers":           raw.get("followers"),
            "following":           raw.get("following"),
            "posts":               raw.get("posts"),
            "has_profile_picture": raw.get("has_profile_picture"),
            "is_private":          raw.get("is_private"),
            "collection_source":   raw.get("collection_source", "permitted_public_page"),
            "collection_status":   "partial",
            "collected_at":        utc_now_iso(),
            "fields_collected":    [],
            "error":               raw.get("error"),
        }
        profile["fields_collected"] = compute_fields_collected(profile)
        return profile

    def validate(self, profile: dict) -> dict:
        if not profile.get("username"):
            profile["collection_status"] = "failed"
            if not profile.get("error"):
                profile["error"] = (
                    "Instagram profile data could not be collected. "
                    "The profile may be private or instaloader may need "
                    "Instagram credentials — add them to the .env file."
                )
            return profile

        core = {"followers", "following", "posts"}
        fields = set(profile.get("fields_collected", []))

        if core.issubset(fields):
            profile["collection_status"] = "success"
            profile["error"] = None
        else:
            profile["collection_status"] = "partial"
            missing = core - fields
            profile["error"] = (
                f"Partial Instagram collection: "
                f"{', '.join(sorted(missing))} could not be obtained."
            )

        return profile

    # ── Helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _extract_username(url: str) -> str | None:
        path = urlparse(url).path.strip("/")
        if not path:
            return None
        segment = path.split("/")[0]
        if re.fullmatch(r"[A-Za-z0-9._]{1,30}", segment):
            return segment
        return None


def _source_label() -> str:
    """Return the appropriate collection_source label."""
    ig_username = os.getenv("INSTAGRAM_USERNAME", "").strip()
    return "official_api" if ig_username else "permitted_public_page"
