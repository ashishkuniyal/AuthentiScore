"""
AuthentiScore — MastodonCollector
=================================

Collects public Mastodon user data using the fully unauthenticated API.
"""

from urllib.parse import urlparse
import requests

from app.services.collectors.base_collector import BaseCollector
from app.services.collectors.generic_public_collector import utc_now_iso

MASTODON_DOMAINS = {
    "mastodon.social",
}

class MastodonCollector(BaseCollector):

    def can_handle(self, url: str) -> bool:
        try:
            domain = urlparse(url).netloc.lower()
            # Mastodon has many instances, but we'll focus on mastodon.social for simplicity
            return domain in MASTODON_DOMAINS
        except Exception:
            return False

    def collect(self, url: str) -> dict:
        from app.services.collector import extract_username
        username = extract_username(url)
        if not username:
            return {
                "error": "Unable to extract username from Mastodon URL.",
                "url": url,
                "username": None,
                "success": False,
            }

        # For Mastodon, the URL path is usually /@username
        username = username.lstrip('@')
        
        try:
            api_url = f"https://mastodon.social/api/v1/accounts/lookup?acct={username}"
            res = requests.get(api_url, timeout=10)
            
            if res.status_code == 404:
                return {"success": False, "error": "User not found on mastodon.social.", "url": url, "username": username}
            if res.status_code != 200:
                return {"success": False, "error": f"Mastodon API error {res.status_code}", "url": url, "username": username}
                
            data = res.json()
            return {
                "success": True,
                "url": url,
                "username": username,
                "data": data
            }
        except Exception as e:
            return {"success": False, "error": str(e), "url": url, "username": username}

    def normalize(self, raw: dict) -> dict:
        username = raw.get("username")
        url = raw.get("url", "")
        
        if not raw.get("success"):
            return {
                "platform":            "mastodon",
                "profile_url":         url,
                "username":            username,
                "collection_source":   "none",
                "collection_status":   "failed",
                "collected_at":        utc_now_iso(),
                "fields_collected":    [],
                "error":               raw.get("error"),
            }

        data = raw.get("data", {})
        
        display_name = data.get("display_name") or data.get("username")
        bio = data.get("note", "").replace("<p>", "").replace("</p>", "") # Basic HTML strip
        followers = data.get("followers_count", 0)
        following = data.get("following_count", 0)
        posts = data.get("statuses_count", 0)
        has_profile_picture = 1 if "missing.png" not in data.get("avatar", "") else 0
        is_private = 1 if data.get("locked") else 0

        profile = {
            "platform":            "mastodon",
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
            "collection_status":   "success",
            "collected_at":        utc_now_iso(),
            "error":               None,
        }
        
        from app.services.collectors.generic_public_collector import compute_fields_collected
        profile["fields_collected"] = compute_fields_collected(profile)
        return profile

    def validate(self, normalized: dict) -> dict:
        if normalized.get("collection_status") == "failed":
            return normalized
        if not normalized.get("username"):
            normalized["collection_status"] = "failed"
            normalized["error"] = "Validation failed: missing username"
        return normalized
