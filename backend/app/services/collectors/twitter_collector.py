"""
AuthentiScore — TwitterCollector
=================================

Collects public Twitter/X profile data.

Two collection paths:

Path 1 — Official Twitter API v2 (when TWITTER_BEARER_TOKEN is set):
    GET /2/users/by/username/{username}
        ?user.fields=public_metrics,description,profile_image_url,protected

    Returns: followers, following, tweet_count, bio, profile_picture,
             is_private (protected).
    collection_source: "official_api"

Path 2 — No token available:
    Twitter/X requires authentication for all profile pages.
    Unauthenticated requests are redirected to the login page.
    The collector immediately returns collection_status = "failed"
    and a clear user-facing message to trigger the manual fallback.
    collection_source: "none"

POLICY:
  - No login automation, no CAPTCHA, no cookie injection.
  - The API token (if present) is read from the environment variable
    TWITTER_BEARER_TOKEN only — never from user input.
  - The token is used only as an Authorization header to the
    official Twitter v2 public endpoint.
  - No private data, DMs, or protected tweets are accessed.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from urllib.parse import unquote, urlparse

import httpx

from app.services.collectors.base_collector import BaseCollector
from app.services.collectors.generic_public_collector import (
    compute_fields_collected,
    parse_bool_to_int,
    parse_count,
    utc_now_iso,
    fetch_public_page
)

logger = logging.getLogger(__name__)

TWITTER_DOMAINS = {
    "twitter.com",
    "www.twitter.com",
    "x.com",
    "www.x.com",
}

TWITTER_API_BASE = "https://api.twitter.com/2"
REQUEST_TIMEOUT = 10.0


class TwitterCollector(BaseCollector):
    """
    Collector for public Twitter/X profiles.

    Strategy 1: Official Twitter v2 API when a working bearer token is available.
    Strategy 2: Real-time public extraction via FxTwitter/FixTweet API proxy when
                the official API is unconfigured or restricted (e.g. HTTP 402).
    """

    # ---------------------------------------------------------------
    # BaseCollector Interface
    # ---------------------------------------------------------------

    def can_handle(self, url: str) -> bool:
        try:
            domain = urlparse(url).netloc.lower()
            return domain in TWITTER_DOMAINS
        except Exception:
            return False

    def collect(self, url: str) -> dict:
        """
        Main collection entry point.
        Strategy 1: Official Twitter API v2 when TWITTER_BEARER_TOKEN is set.
        Strategy 2: Public live extraction fallback via FxTwitter/FixTweet proxy.
        """
        username = self._extract_username(url)

        if not username:
            return {
                "platform": "twitter",
                "url": url,
                "collection_status": "failed",
                "error": "Could not extract username from URL.",
                "username": None,
                "success": False,
            }

        bearer_token = unquote(os.getenv("TWITTER_BEARER_TOKEN", "").strip())
        if bearer_token:
            api_res = self._collect_via_api(username, bearer_token, url)
            if api_res.get("success"):
                return api_res
            logger.info("Twitter API v2 did not succeed (%s) — falling back to public extraction", api_res.get("error"))

        # Strategy 2: Live public extraction via FxTwitter / FixTweet proxy
        return self._collect_via_public(username, url)

    def normalize(self, raw: dict) -> dict:
        username = raw.get("username")

        profile = {
            "platform":            "twitter",
            "profile_url":         raw.get("url", ""),
            "username":            username,
            "display_name":        raw.get("display_name"),
            "bio":                 raw.get("bio"),
            "followers":           raw.get("followers"),
            "following":           raw.get("following"),
            "posts":               raw.get("posts"),
            "has_profile_picture": raw.get("has_profile_picture"),
            "is_private":          raw.get("is_private"),
            "joined_date":         raw.get("joined_date"),
            "collection_source":   raw.get("collection_source", "none"),
            "collection_status":   "partial" if raw.get("success") else "failed",
            "collected_at":        utc_now_iso(),
            "fields_collected":    [],
            "error":               raw.get("error"),
        }

        if raw.get("success"):
            profile["fields_collected"] = compute_fields_collected(profile)
            
        return profile

    def validate(self, profile: dict) -> dict:
        # If collection was never attempted (no API token available),
        # the source is "none" — mark as failed regardless of username.
        if profile.get("collection_source") == "none":
            profile["collection_status"] = "failed"
            return profile

        # If no username obtained at all → failed
        if not profile.get("username"):
            profile["collection_status"] = "failed"
            return profile

        # If already marked as failed by the collector, preserve that state
        if profile.get("collection_status") == "failed":
            return profile

        fields = set(profile.get("fields_collected", []))
        core = {"followers", "following", "posts"}

        if core.issubset(fields):
            profile["collection_status"] = "success"
            profile["error"] = None
        else:
            profile["collection_status"] = "partial"
            missing = core - fields
            if not profile.get("error"):
                profile["error"] = (
                    f"Partial Twitter collection: {', '.join(sorted(missing))} "
                    "could not be obtained."
                )

        return profile

    # ---------------------------------------------------------------
    # Official API v2 Collection
    # ---------------------------------------------------------------

    def _collect_via_api(
        self,
        username: str,
        bearer_token: str,
        url: str,
    ) -> dict:
        """
        Fetch public profile data from the Twitter v2 users endpoint.

        Only accesses public fields: public_metrics, description,
        profile_image_url, protected.
        """
        endpoint = (
            f"{TWITTER_API_BASE}/users/by/username/{username}"
            "?user.fields=public_metrics,description,"
            "profile_image_url,protected,name"
        )

        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
                response = client.get(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {bearer_token}",
                        "User-Agent": "AuthentiScore/1.0 (research prototype)",
                    },
                )

        except (httpx.TimeoutException, httpx.RequestError) as exc:
            return {
                "success": False,
                "url": url,
                "username": username,
                "collection_source": "official_api",
                "error": f"Twitter API network error: {type(exc).__name__}.",
            }

        if response.status_code == 401:
            return {
                "success": False,
                "url": url,
                "username": username,
                "collection_source": "official_api",
                "error": (
                    "Twitter API bearer token is invalid or expired. "
                    "Please update TWITTER_BEARER_TOKEN in the backend .env file."
                ),
            }

        if response.status_code == 429:
            return {
                "success": False,
                "url": url,
                "username": username,
                "collection_source": "official_api",
                "error": (
                    "Twitter API rate limit reached. "
                    "Please use the manual fallback."
                ),
            }

        if response.status_code == 404:
            return {
                "success": False,
                "url": url,
                "username": username,
                "collection_source": "official_api",
                "error": "Twitter profile not found.",
            }

        if response.status_code >= 400:
            return {
                "success": False,
                "url": url,
                "username": username,
                "collection_source": "official_api",
                "error": f"Twitter API error (HTTP {response.status_code}).",
            }

        try:
            data = response.json()
        except Exception:
            return {
                "success": False,
                "url": url,
                "username": username,
                "collection_source": "official_api",
                "error": "Failed to parse Twitter API response.",
            }

        user = data.get("data")
        if not user:
            errors = data.get("errors", [])
            msg = errors[0].get("detail", "User not found.") if errors else "User not found."
            return {
                "success": False,
                "url": url,
                "username": username,
                "collection_source": "official_api",
                "error": msg,
            }

        metrics = user.get("public_metrics", {})

        has_profile_pic = parse_bool_to_int(
            bool(user.get("profile_image_url"))
        )

        return {
            "success":             True,
            "url":                 url,
            "username":            user.get("username") or username,
            "display_name":        user.get("name"),
            "bio":                 user.get("description"),
            "followers":           parse_count(metrics.get("followers_count")),
            "following":           parse_count(metrics.get("following_count")),
            "posts":               parse_count(metrics.get("tweet_count")),
            "has_profile_picture": has_profile_pic,
            "is_private":          parse_bool_to_int(user.get("protected")),
            "collection_source":   "official_api",
            "error":               None,
        }

    # ---------------------------------------------------------------
    # Public Live Extraction (FxTwitter / FixTweet)
    # ---------------------------------------------------------------

    def _collect_via_public(self, username: str, url: str) -> dict:
        """
        Public live extraction via FixTweet / FxTwitter public API proxy.
        Retrieves real-time public Twitter/X profile data without requiring
        a paid Twitter API v2 subscription or login credentials.
        """
        endpoint = f"https://api.fxtwitter.com/{username}"
        page_res = fetch_public_page(
            endpoint,
            extra_headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
            },
        )

        if not page_res.get("success") or not page_res.get("html"):
            return {
                "success": False,
                "url": url,
                "username": username,
                "collection_source": "none",
                "error": page_res.get("error") or "Twitter profile could not be reached via public extraction.",
            }

        try:
            data = json.loads(page_res["html"])
        except Exception:
            return {
                "success": False,
                "url": url,
                "username": username,
                "collection_source": "none",
                "error": "Failed to parse public Twitter profile response.",
            }

        if data.get("code") == 404 or not data.get("user"):
            return {
                "success": False,
                "url": url,
                "username": username,
                "collection_source": "none",
                "error": "Twitter profile not found.",
            }

        user = data["user"]
        has_profile_pic = parse_bool_to_int(bool(user.get("avatar_url")))

        return {
            "success":             True,
            "url":                 url,
            "username":            user.get("screen_name") or username,
            "display_name":        user.get("name"),
            "bio":                 user.get("description"),
            "followers":           parse_count(user.get("followers")),
            "following":           parse_count(user.get("following")),
            "posts":               parse_count(user.get("tweets")),
            "has_profile_picture": has_profile_pic,
            "is_private":          parse_bool_to_int(user.get("protected")),
            "joined_date":         user.get("joined"),
            "collection_source":   "permitted_public_page",
            "error":               None,
        }

    # ---------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------

    @staticmethod
    def _extract_username(url: str) -> str | None:
        path = urlparse(url).path.strip("/")
        if not path:
            return None

        segment = path.split("/")[0]

        # Skip known Twitter non-profile paths
        reserved = {
            "home", "explore", "notifications", "messages",
            "settings", "i", "intent", "search",
        }
        if segment.lower() in reserved:
            return None

        # Twitter usernames: letters, digits, underscores, 1–50 chars
        if re.fullmatch(r"[A-Za-z0-9_]{1,50}", segment):
            return segment

        return None
