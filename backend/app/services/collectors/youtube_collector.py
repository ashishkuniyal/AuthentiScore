"""
AuthentiScore — YouTubeCollector
================================

Collects public YouTube channel data by parsing the ytInitialData
JSON payload embedded in the HTML response.

POLICY:
  - No authentication used.
  - Single GET request.
  - Extract followers (subscribers), posts (videos), bio (description).
"""

import json
from urllib.parse import urlparse

from app.services.collectors.base_collector import BaseCollector
from app.services.collectors.generic_public_collector import (
    compute_fields_collected,
    extract_embedded_json,
    fetch_public_page,
    parse_count,
    utc_now_iso,
)

YOUTUBE_DOMAINS = {
    "youtube.com",
    "www.youtube.com",
}


class YouTubeCollector(BaseCollector):

    def can_handle(self, url: str) -> bool:
        try:
            domain = urlparse(url).netloc.lower()
            return domain in YOUTUBE_DOMAINS
        except Exception:
            return False

    def collect(self, url: str) -> dict:
        username = self._extract_username(url)
        if not username:
            return {
                "error": "Unable to extract username from YouTube URL.",
                "url": url,
                "username": None,
                "success": False,
            }

        page = fetch_public_page(
            url,
            extra_headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        if not page["success"]:
            return {"success": False, "error": page["error"], "url": url}

        html = page.get("html") or ""
        
        # YouTube embeds initial state in window.ytInitialData
        data = extract_embedded_json(html, ["ytInitialData", "window.ytInitialData"])
        
        if not data:
            return {
                "success": False,
                "error": "Could not find ytInitialData in page HTML.",
                "url": url,
                "username": username
            }
            
        return {
            "success": True,
            "url": url,
            "username": username,
            "data": data
        }

    def normalize(self, raw: dict) -> dict:
        username = raw.get("username")
        url = raw.get("url", "")
        
        if not raw.get("success"):
            return {
                "platform":            "youtube",
                "profile_url":         url,
                "username":            username,
                "collection_source":   "none",
                "collection_status":   "failed",
                "collected_at":        utc_now_iso(),
                "fields_collected":    [],
                "error":               raw.get("error"),
            }

        data = raw.get("data", {})
        
        # Try legacy c4TabbedHeaderRenderer
        c4 = data.get("header", {}).get("c4TabbedHeaderRenderer", {})
        
        # Try modern pageHeaderRenderer
        phr = data.get("header", {}).get("pageHeaderRenderer", {})
        vm = phr.get("content", {}).get("pageHeaderViewModel", {})

        display_name = None
        bio = None
        followers = None
        posts = None
        has_profile_picture = None

        if c4 and "title" in c4:
            display_name = c4.get("title")
            sub_text = c4.get("subscriberCountText", {}).get("simpleText", "")
            if sub_text:
                followers = parse_count(sub_text.replace("subscribers", "").replace("subscriber", "").strip())
                
            vid_text = c4.get("videosCountText", {}).get("runs", [{}])[0].get("text", "")
            if not vid_text:
                vid_text = c4.get("videosCountText", {}).get("simpleText", "")
            if vid_text:
                posts = parse_count(vid_text.replace("videos", "").replace("video", "").strip())

            avatar_list = c4.get("avatar", {}).get("thumbnails", [])
            has_profile_picture = 1 if avatar_list else 0

        elif phr and vm:
            display_name = phr.get("pageTitle", "")
            
            meta_runs = vm.get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", [])
            for row in meta_runs:
                parts = row.get("metadataParts", [])
                for part in parts:
                    text = part.get("text", {}).get("content", "").lower()
                    if "subscriber" in text:
                        followers = parse_count(text.replace("subscribers", "").replace("subscriber", "").strip())
                    elif "video" in text:
                        posts = parse_count(text.replace("videos", "").replace("video", "").strip())
                        
            avatar = vm.get("image", {}).get("decoratedAvatarViewModel", {}).get("avatar", {}).get("avatarViewModel", {}).get("image", {}).get("sources", [])
            has_profile_picture = 1 if avatar else 0
            
            bio = vm.get("description", {}).get("descriptionPreviewViewModel", {}).get("description", {}).get("content", "")

        profile = {
            "platform":            "youtube",
            "profile_url":         url,
            "username":            username,
            "display_name":        display_name,
            "bio":                 bio,
            "followers":           followers,
            "following":           None,  # YouTube does not expose following counts publicly (C14)
            "posts":               posts,
            "has_profile_picture": has_profile_picture,
            "is_private":          0,
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

        if not profile.get("username") or not profile.get("display_name"):
            profile["collection_status"] = "failed"
            profile["error"] = "Unable to extract basic channel information."
            return profile

        if "followers" in fields and "posts" in fields:
            profile["collection_status"] = "success"
        else:
            profile["collection_status"] = "partial"
            profile["error"] = "Partial collection: unable to extract subscriber or video count."

        return profile

    @staticmethod
    def _extract_username(url: str) -> str | None:
        path = urlparse(url).path.strip("/")
        if not path:
            return None
            
        segments = path.split("/")
        
        for segment in segments:
            if segment.startswith("@"):
                return segment[1:]
            
        # Handle legacy /c/ or /user/ urls
        if len(segments) >= 2 and segments[0] in {"c", "user", "channel"}:
            return segments[1]
            
        return segments[0]
