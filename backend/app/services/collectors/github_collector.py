"""
AuthentiScore — GitHubCollector
===============================

Collects public GitHub user or organization data using the 
fully unauthenticated public JSON API.

API Endpoint: https://api.github.com/users/{username}

POLICY:
  - No authentication used.
  - Single GET request.
  - Extract followers, following, public repos (posts).
"""

from urllib.parse import urlparse

from app.services.collectors.base_collector import BaseCollector
from app.services.collectors.generic_public_collector import (
    compute_fields_collected,
    fetch_json_endpoint,
    utc_now_iso,
)

GITHUB_DOMAINS = {
    "github.com",
    "www.github.com",
}


class GitHubCollector(BaseCollector):

    def can_handle(self, url: str) -> bool:
        try:
            domain = urlparse(url).netloc.lower()
            return domain in GITHUB_DOMAINS
        except Exception:
            return False

    def collect(self, url: str) -> dict:
        username = self._extract_username(url)
        if not username:
            return {
                "error": "Unable to extract username from GitHub URL.",
                "url": url,
                "username": None,
                "success": False,
            }

        api_url = f"https://api.github.com/users/{username}"
        result = fetch_json_endpoint(api_url)
        
        if not result["success"]:
            return {"success": False, "error": result["error"], "url": url, "username": username}

        return {
            "success": True,
            "url": url,
            "username": username,
            "data": result.get("data", {})
        }

    def normalize(self, raw: dict) -> dict:
        username = raw.get("username")
        url = raw.get("url", "")
        
        if not raw.get("success"):
            return {
                "platform":            "github",
                "profile_url":         url,
                "username":            username,
                "collection_source":   "none",
                "collection_status":   "failed",
                "collected_at":        utc_now_iso(),
                "fields_collected":    [],
                "error":               raw.get("error"),
            }

        data = raw.get("data", {})
        
        display_name = data.get("name")
        bio = data.get("bio")
        followers = data.get("followers")
        following = data.get("following")
        posts = data.get("public_repos")
        has_profile_picture = 1 if data.get("avatar_url") else 0
        is_private = 0

        profile = {
            "platform":            "github",
            "profile_url":         url,
            "username":            username,
            "display_name":        display_name,
            "bio":                 bio,
            "followers":           followers,
            "following":           following,
            "posts":               posts,
            "has_profile_picture": has_profile_picture,
            "is_private":          is_private,
            "collection_source":   "permitted_public_page",
            "collection_status":   "partial",
            "collected_at":        utc_now_iso(),
            "fields_collected":    [],
            "error":               None,
        }

        profile["fields_collected"] = compute_fields_collected(profile)
        return profile

    def validate(self, profile: dict) -> dict:
        fields = profile.get("fields_collected", [])

        if not profile.get("username"):
            profile["collection_status"] = "failed"
            profile["error"] = "Unable to extract GitHub account data."
            return profile

        core_numeric = {"followers", "following", "posts"}
        if core_numeric.issubset(set(fields)):
            profile["collection_status"] = "success"
        else:
            profile["collection_status"] = "partial"
            profile["error"] = "Partial collection: missing some metrics."

        return profile

    @staticmethod
    def _extract_username(url: str) -> str | None:
        path = urlparse(url).path.strip("/")
        if not path:
            return None
        return path.split("/")[0]
