"""
AuthentiScore — GenericPublicCollector utilities
================================================

Shared HTTP client and multi-strategy public-page parser used
by platform-specific collectors.

Extraction strategies (tried in order):
  1. JSON-LD  (<script type="application/ld+json">)
  2. OpenGraph meta tags  (og:title, og:description, og:image, ...)
  3. Twitter card meta tags  (twitter:title, twitter:description, ...)
  4. Embedded page JSON blobs  (window._sharedData, __additionalDataLoaded, etc.)
  5. Visible text heuristics on specific public structures

None of these strategies:
  - Require authentication.
  - Bypass CAPTCHA or rate limits.
  - Access private content.
  - Follow redirects to login pages.
"""

import json
import re
import time
import random
from datetime import datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup


# ==============================================================
# HTTP Configuration
# ==============================================================

# Conservative timeouts — single request per scan.
REQUEST_TIMEOUT = 10.0           # seconds

# Honest User-Agent aligning with collection policy (C15, D8)
DEFAULT_USER_AGENT = "AuthentiScore/1.0"


def _get_headers(extra_headers: dict | None = None) -> dict:
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if extra_headers:
        headers.update(extra_headers)
    return headers


def fetch_public_page(url: str, extra_headers: dict | None = None, max_retries: int = 2) -> dict:
    """
    Fetch a public URL and return a result dict:

    {
        "success": bool,
        "html":    str | None,
        "status_code": int | None,
        "error":   str | None,
    }

    Honest single request with at most one retry on timeout or 5xx (C15, D8).
    """
    headers = _get_headers(extra_headers)
    last_error_message = "Unknown error"
    last_status_code = None

    for attempt in range(max_retries):
        try:
            with httpx.Client(
                timeout=REQUEST_TIMEOUT,
                follow_redirects=True,
                headers=headers,
            ) as client:
                response = client.get(url)

            # Detect redirect to a login/gate page
            if response.url and _is_login_redirect(str(response.url)):
                return {
                    "success": False,
                    "html": None,
                    "status_code": response.status_code,
                    "error": (
                        "Profile collection is unavailable: "
                        "the platform requires login to view this profile."
                    ),
                }

            if response.status_code == 404:
                return {
                    "success": False,
                    "html": None,
                    "status_code": 404,
                    "error": "Profile not found (HTTP 404).",
                }

            if response.status_code == 429:
                return {
                    "success": False,
                    "html": None,
                    "status_code": 429,
                    "error": "Rate limited by platform.",
                }

            if response.status_code >= 500:
                last_status_code = response.status_code
                last_error_message = f"Platform server error (HTTP {response.status_code})."
                if attempt < max_retries - 1:
                    time.sleep(1.0)
                    continue
                return {
                    "success": False,
                    "html": None,
                    "status_code": last_status_code,
                    "error": last_error_message,
                }

            if response.status_code >= 400:
                return {
                    "success": False,
                    "html": None,
                    "status_code": response.status_code,
                    "error": f"Platform returned HTTP {response.status_code}.",
                }

            return {
                "success": True,
                "html": response.text,
                "status_code": response.status_code,
                "error": None,
            }

        except (httpx.TimeoutException, httpx.RequestError) as exc:
            last_error_message = f"Network error: {type(exc).__name__}."
            if attempt < max_retries - 1:
                time.sleep(1.0)
                continue
            return {
                "success": False,
                "html": None,
                "status_code": None,
                "error": last_error_message,
            }

    # All retries failed
    return {
        "success": False,
        "html": None,
        "status_code": last_status_code,
        "error": f"Failed after {max_retries} attempts. Last error: {last_error_message}",
    }


def fetch_json_endpoint(url: str, extra_headers: dict | None = None) -> dict:
    """
    Fetch a URL that is expected to return JSON.

    Returns:
    {
        "success": bool,
        "data":    dict | None,
        "status_code": int | None,
        "error":   str | None,
    }
    """
    headers = _get_headers(extra_headers)
    headers["Accept"] = "application/json, text/javascript, */*"

    try:
        with httpx.Client(
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = client.get(url)

        if response.status_code == 404:
            return {
                "success": False,
                "data": None,
                "status_code": 404,
                "error": "JSON endpoint returned 404.",
            }

        if response.status_code >= 400:
            return {
                "success": False,
                "data": None,
                "status_code": response.status_code,
                "error": f"JSON endpoint unavailable (HTTP {response.status_code}).",
            }

        data = response.json()
        return {
            "success": True,
            "data": data,
            "status_code": response.status_code,
            "error": None,
        }

    except (httpx.TimeoutException, httpx.RequestError) as exc:
        return {
            "success": False,
            "data": None,
            "status_code": None,
            "error": f"Network error: {type(exc).__name__}.",
        }

    except Exception:
        return {
            "success": False,
            "data": None,
            "status_code": None,
            "error": "Failed to parse JSON response.",
        }


# ==============================================================
# Strategy 1 — JSON-LD
# ==============================================================

def extract_json_ld(soup: BeautifulSoup) -> dict:
    """
    Extract structured data from JSON-LD script tags.

    Returns a merged dict of all JSON-LD objects found on the page.
    """
    result = {}

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")

            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        result.update(item)
            elif isinstance(data, dict):
                result.update(data)

        except (json.JSONDecodeError, TypeError):
            continue

    return result


# ==============================================================
# Strategy 2 — OpenGraph
# ==============================================================

def extract_opengraph(soup: BeautifulSoup) -> dict:
    """
    Extract OpenGraph meta tags.

    Returns a dict keyed by the og: property name:
    { "title": ..., "description": ..., "image": ..., "url": ..., ... }
    """
    og = {}

    for tag in soup.find_all("meta"):
        prop = tag.get("property", "")
        content = tag.get("content", "")

        if prop.startswith("og:") and content:
            key = prop[3:]   # strip "og:" prefix
            og[key] = content

    return og


# ==============================================================
# Strategy 3 — Twitter card meta tags
# ==============================================================

def extract_twitter_card(soup: BeautifulSoup) -> dict:
    """
    Extract Twitter card meta tags.

    Returns { "title": ..., "description": ..., "image": ..., ... }
    """
    tc = {}

    for tag in soup.find_all("meta"):
        name = tag.get("name", "")
        content = tag.get("content", "")

        if name.startswith("twitter:") and content:
            key = name[8:]   # strip "twitter:" prefix
            tc[key] = content

    return tc


# ==============================================================
# Strategy 4 — Embedded JSON blobs
# ==============================================================

def extract_embedded_json(html: str, variable_names: list[str]) -> dict:
    """
    Search for JavaScript variable assignments that embed JSON objects.

    Examples:
        window._sharedData = {...};
        window.__additionalDataLoaded("...", {...});

    Uses json.JSONDecoder().raw_decode (C16) so nested structures are not cut off.
    Returns the first successfully parsed JSON dict found, or {}.
    """
    decoder = json.JSONDecoder()
    for name in variable_names:
        patterns = [
            rf'{re.escape(name)}\s*=\s*\{{',
            rf'{re.escape(name)}\(".*?",\s*\{{',
        ]

        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                brace_idx = match.end() - 1
                try:
                    obj, _ = decoder.raw_decode(html, brace_idx)
                    if isinstance(obj, dict):
                        return obj
                except (json.JSONDecodeError, ValueError):
                    continue

    return {}


# ==============================================================
# Numeric Helpers
# ==============================================================

def parse_count(value: Any) -> float | None:
    """
    Parse a follower/following/post count from various formats.

    Handles:
      "1,234"  → 1234.0
      "1.2M"   → 1200000.0
      "847K"   → 847000.0
      12345    → 12345.0
      None / ""→ None
    """
    if value is None:
        return None

    text = str(value).strip().upper().replace(",", "")

    if not text:
        return None

    try:
        if text.endswith("M"):
            return round(float(text[:-1]) * 1_000_000)
        if text.endswith("K"):
            return round(float(text[:-1]) * 1_000)
        return float(text)
    except (ValueError, TypeError):
        return None


def parse_bool_to_int(value: Any) -> int | None:
    """Convert a bool/int/str to 0 or 1, or None if unknown."""
    if value is None:
        return None
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int):
        return 1 if value else 0
    if isinstance(value, str):
        lower = value.lower()
        if lower in {"true", "yes", "1"}:
            return 1
        if lower in {"false", "no", "0"}:
            return 0
    return None


# ==============================================================
# Login-redirect Detection
# ==============================================================

_LOGIN_URL_PATTERNS = [
    r"/login",
    r"/signin",
    r"/accounts/login",
    r"login\.twitter\.com",
    r"twitter\.com/i/flow/login",
    r"accounts\.google\.com",
]

_LOGIN_COMPILED = [re.compile(p, re.IGNORECASE) for p in _LOGIN_URL_PATTERNS]


def _is_login_redirect(url: str) -> bool:
    return any(p.search(url) for p in _LOGIN_COMPILED)


# ==============================================================
# Timestamp Helper
# ==============================================================

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ==============================================================
# Fields Collected Helper
# ==============================================================

TRACKABLE_FIELDS = [
    "username",
    "display_name",
    "bio",
    "followers",
    "following",
    "posts",
    "has_profile_picture",
    "is_private",
]


def compute_fields_collected(profile: dict) -> list[str]:
    """Return a list of field names that have non-None values."""
    return [
        f for f in TRACKABLE_FIELDS
        if profile.get(f) is not None
    ]
