"""
AuthentiScore — InstagramCollector
====================================

Attempts to collect public Instagram profile data using two
unauthenticated strategies:

Strategy A (primary):
    Legacy JSON endpoint:
        https://www.instagram.com/{username}/?__a=1&__d=dis

    This endpoint returns structured profile JSON without login
    for some public accounts. Instagram periodically restricts it,
    so failure is handled gracefully.

Strategy B (fallback):
    Public HTML extraction:
        https://www.instagram.com/{username}/

    Tries JSON-LD, OpenGraph, and Twitter card meta tags to extract
    at least username, display name, and bio.

POLICY:
  - No login, cookies, session tokens, or authentication used.
  - No CAPTCHA solving.
  - No anti-bot bypass.
  - Single GET request per strategy; no retry loops.
  - If Instagram blocks access, collection_status = "failed" and
    the system falls back to the manual form.

collection_source: "permitted_public_page"
"""

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from app.services.collectors.base_collector import BaseCollector
from app.services.collectors.generic_public_collector import (
    compute_fields_collected,
    extract_embedded_json,
    extract_json_ld,
    extract_opengraph,
    extract_twitter_card,
    fetch_json_endpoint,
    fetch_public_page,
    parse_bool_to_int,
    parse_count,
    utc_now_iso,
)

INSTAGRAM_DOMAINS = {
    "instagram.com",
    "www.instagram.com",
}


class InstagramCollector(BaseCollector):
    """
    Collector for public Instagram profiles.
    """

    # ---------------------------------------------------------------
    # BaseCollector Interface
    # ---------------------------------------------------------------

    def can_handle(self, url: str) -> bool:
        try:
            domain = urlparse(url).netloc.lower()
            return domain in INSTAGRAM_DOMAINS
        except Exception:
            return False

    def collect(self, url: str) -> dict:
        """
        Try Strategy A (JSON endpoint) then Strategy B (HTML parsing).
        Returns a raw dict with whatever was obtained.
        """
        username = self._extract_username(url)
        if not username:
            return {
                "error": "Unable to extract username from Instagram URL.",
                "url": url,
                "username": None,
            }

        # ── Strategy A: Legacy JSON endpoint ──────────────────────
        json_result = self._try_json_endpoint(username)
        if json_result.get("success"):
            return {**json_result, "strategy": "json_endpoint", "url": url}

        # ── Strategy B: Public HTML extraction ────────────────────
        html_result = self._try_html_extraction(username, url)
        return {**html_result, "strategy": "html_extraction", "url": url}

    def normalize(self, raw: dict) -> dict:
        """
        Map raw Instagram data into the AuthentiScore profile schema.
        """
        username = raw.get("username")

        profile = {
            "platform":            "instagram",
            "profile_url":         raw.get("url", ""),
            "username":            username,
            "display_name":        raw.get("display_name"),
            "bio":                 raw.get("bio"),
            "followers":           raw.get("followers"),
            "following":           raw.get("following"),
            "posts":               raw.get("posts"),
            "has_profile_picture": raw.get("has_profile_picture"),
            "is_private":          raw.get("is_private"),
            "collection_source":   "permitted_public_page",
            "collection_status":   "partial",   # validated below
            "collected_at":        utc_now_iso(),
            "fields_collected":    [],
            "error":               raw.get("error"),
        }

        profile["fields_collected"] = compute_fields_collected(profile)
        return profile

    def validate(self, profile: dict) -> dict:
        """
        Determine collection_status based on which fields were obtained.

        success  → all core fields present
        partial  → username obtained but some numeric fields missing
        failed   → not even a username
        """
        fields = profile.get("fields_collected", [])

        if not profile.get("username"):
            profile["collection_status"] = "failed"
            if not profile.get("error"):
                profile["error"] = (
                    "Profile data could not be collected from Instagram's "
                    "permitted public source. The profile may be private, "
                    "or Instagram has restricted automated access."
                )
            return profile

        core_numeric = {"followers", "following", "posts"}
        has_all_numeric = core_numeric.issubset(set(fields))

        if has_all_numeric:
            profile["collection_status"] = "success"
            profile["error"] = None
        else:
            profile["collection_status"] = "partial"
            missing = core_numeric - set(fields)
            profile["error"] = (
                f"Partial collection: {', '.join(sorted(missing))} "
                "could not be obtained from Instagram's public source."
            )

        return profile

    # ---------------------------------------------------------------
    # Strategy A — Legacy JSON endpoint
    # ---------------------------------------------------------------

    def _try_json_endpoint(self, username: str) -> dict:
        """
        Try https://www.instagram.com/{username}/?__a=1&__d=dis

        This is a legacy unauthenticated JSON endpoint that Instagram
        has not fully removed. It works for some public accounts.
        """
        endpoint = (
            f"https://www.instagram.com/{username}/"
            "?__a=1&__d=dis"
        )

        result = fetch_json_endpoint(
            endpoint,
            extra_headers={
                "Referer": "https://www.instagram.com/",
                "X-Requested-With": "XMLHttpRequest",
            },
        )

        if not result["success"]:
            return {"success": False, "error": result["error"]}

        data = result.get("data") or {}

        # Navigate the Instagram JSON structure
        user = (
            data.get("graphql", {}).get("user")
            or data.get("data", {}).get("user")
            or {}
        )

        if not user:
            return {
                "success": False,
                "error": "JSON endpoint returned no user data.",
            }

        followers = parse_count(
            user.get("edge_followed_by", {}).get("count")
        )
        following = parse_count(
            user.get("edge_follow", {}).get("count")
        )
        posts = parse_count(
            user.get("edge_owner_to_timeline_media", {}).get("count")
        )

        has_pic = parse_bool_to_int(
            bool(user.get("profile_pic_url"))
            or bool(user.get("profile_pic_url_hd"))
        )

        return {
            "success":             True,
            "username":            user.get("username") or username,
            "display_name":        user.get("full_name"),
            "bio":                 user.get("biography"),
            "followers":           followers,
            "following":           following,
            "posts":               posts,
            "has_profile_picture": has_pic,
            "is_private":          parse_bool_to_int(user.get("is_private")),
            "error":               None,
        }

    # ---------------------------------------------------------------
    # Strategy B — Public HTML extraction
    # ---------------------------------------------------------------

    def _try_html_extraction(self, username: str, url: str) -> dict:
        """
        Fetch the public Instagram profile HTML and extract metadata
        using OpenGraph, Twitter card, and JSON-LD strategies.
        """
        page_url = f"https://www.instagram.com/{username}/"
        page = fetch_public_page(page_url)

        if not page["success"]:
            return {"success": False, "error": page["error"]}

        html = page["html"] or ""
        soup = BeautifulSoup(html, "lxml")

        og   = extract_opengraph(soup)
        tc   = extract_twitter_card(soup)
        ld   = extract_json_ld(soup)

        # -- Username --
        extracted_username = (
            ld.get("alternateName")
            or og.get("url", "").rstrip("/").split("/")[-1]
            or username
        )

        # -- Display name --
        display_name = (
            ld.get("name")
            or og.get("title", "").split(" (@")[0].strip()
            or tc.get("title", "").split(" (@")[0].strip()
            or None
        )

        # -- Bio --
        bio = (
            ld.get("description")
            or og.get("description")
            or tc.get("description")
            or None
        )

        # Clean up Instagram's prefixed descriptions like
        # "1,234 Followers, 567 Following, 89 Posts - ..."
        followers, following, posts = None, None, None

        if bio:
            follower_match = re.search(
                r"([\d,\.]+[KMB]?)\s+Followers",
                bio,
                re.IGNORECASE,
            )
            following_match = re.search(
                r"([\d,\.]+[KMB]?)\s+Following",
                bio,
                re.IGNORECASE,
            )
            posts_match = re.search(
                r"([\d,\.]+[KMB]?)\s+Posts?",
                bio,
                re.IGNORECASE,
            )

            if follower_match:
                followers = parse_count(follower_match.group(1))
            if following_match:
                following = parse_count(following_match.group(1))
            if posts_match:
                posts = parse_count(posts_match.group(1))

            # Remove the count prefix from bio text
            bio = re.sub(
                r"^[\d,\.]+[KMB]?\s+Followers,\s*[\d,\.]+[KMB]?\s+Following,"
                r"\s*[\d,\.]+[KMB]?\s+Posts?\s*[-–—]\s*",
                "",
                bio,
                flags=re.IGNORECASE,
            ).strip() or bio

        # -- Profile picture --
        has_profile_picture = None
        if og.get("image") or tc.get("image"):
            has_profile_picture = 1

        return {
            "success":             bool(extracted_username),
            "username":            extracted_username or None,
            "display_name":        display_name,
            "bio":                 bio,
            "followers":           followers,
            "following":           following,
            "posts":               posts,
            "has_profile_picture": has_profile_picture,
            "is_private":          None,   # not exposed in public HTML
            "error":               None if extracted_username else (
                "Unable to extract profile data from Instagram's public page."
            ),
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
        # Instagram usernames: letters, digits, underscores, periods
        if re.fullmatch(r"[A-Za-z0-9._]{1,30}", segment):
            return segment
        return None
