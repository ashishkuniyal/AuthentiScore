import os
import httpx
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

APIFY_ACTOR_ID = "themineworks~instagram-followers-scraper"

class ApifyInstagramCollector:
    @staticmethod
    def _extract_username(url_or_username: str) -> str:
        if "://" in url_or_username or "instagram.com" in url_or_username:
            path = urlparse(url_or_username).path.strip("/")
            return path.split("/")[0]
        return url_or_username.lstrip("@")

    @staticmethod
    def _redact_errors(error_message: str, sensitive_data: str) -> str:
        if not sensitive_data:
            return error_message
        return error_message.replace(sensitive_data, "[REDACTED]")

    @staticmethod
    def get_follower_sample(target_influencer: str, sample_size: int) -> list:
        token = os.getenv("APIFY_API_TOKEN")
        session_id = os.getenv("INSTAGRAM_SESSION_ID")
        if not token:
            raise ValueError("APIFY_API_TOKEN is not set in .env. Please add it to use Apify.")

        username = ApifyInstagramCollector._extract_username(target_influencer)

        # Enforce conservative sample size
        sample_size = min(sample_size, 50)

        # S6: Send token in Bearer header, not in query string
        url = f"https://api.apify.com/v2/acts/{APIFY_ACTOR_ID}/run-sync-get-dataset-items"
        headers = {"Authorization": f"Bearer {token}"}
        
        payload = {
            "usernames": [username],
            "mode": "followers",
            "maxPerUsername": sample_size,
        }
        
        # S8 / D5: Do not forward session cookies unless explicitly enabled
        forward_session = os.getenv("APIFY_FORWARD_SESSION", "").lower() == "true"
        if session_id and forward_session:
            payload["cookie"] = f"sessionid={session_id}"
            payload["cookies"] = [{"name": "sessionid", "value": session_id, "domain": ".instagram.com", "path": "/"}]
            payload["sessionid"] = session_id

        try:
            # We use timeout=120.0 because synchronous actor runs can take some time
            with httpx.Client(timeout=120.0) as client:
                response = client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException:
            raise Exception("Apify actor run timed out. The scraping took too long or the actor is unavailable.")
        except Exception as e:
            err = str(e)
            if token:
                err = ApifyInstagramCollector._redact_errors(err, token)
            if session_id:
                err = ApifyInstagramCollector._redact_errors(err, session_id)
            raise Exception(f"Failed to connect to Apify: {err}")

        if response.status_code == 401:
            raise Exception("Apify token invalid or expired. Check APIFY_API_TOKEN in .env.")
        elif response.status_code == 429:
            raise Exception("Apify rate limit reached or out of credits.")
        elif response.status_code >= 400:
            err_msg = f"Apify API error (HTTP {response.status_code})"
            try:
                err_msg += f": {response.json()}"
            except Exception:
                pass
            if token:
                err_msg = ApifyInstagramCollector._redact_errors(err_msg, token)
            if session_id:
                err_msg = ApifyInstagramCollector._redact_errors(err_msg, session_id)
            raise Exception(err_msg)

        data = response.json()
        
        # Apify's run-sync-get-dataset-items returns a list of items directly
        if not isinstance(data, list):
            raise Exception("Unexpected response format from Apify actor.")
            
        # Scan the entire dataset for any error/summary objects that indicate auth failure
        for item in data:
            status = item.get("status")
            reason = item.get("reason", "") or item.get("auth_dead_reason", "")
            if status == "auth_required" or item.get("auth_dead"):
                err_msg = f"Instagram session expired or flagged — burner account needs re-authentication. Reason: {reason}"
                if session_id:
                    err_msg = ApifyInstagramCollector._redact_errors(err_msg, session_id)
                raise Exception(err_msg)
            elif item.get("_type") == "summary" and status:
                err_msg = f"Apify actor error: {status} - {reason}"
                if session_id:
                    err_msg = ApifyInstagramCollector._redact_errors(err_msg, session_id)
                raise Exception(err_msg)

        followers = []
        for item in data[:sample_size]:  # Force slice to requested sample size
            f_username = item.get("username")
            if not f_username:
                continue
                
            has_pic = 1 if item.get("profilePictureUrl") else 0
            is_priv = 1 if item.get("isPrivate") else 0
            is_verif = 1 if item.get("isVerified") else 0

            # C14: Never fabricate baseline numbers. Unknown fields remain None.
            follower = {
                "identifier": f_username,
                "platform": "instagram",
                "profile_url": f"https://www.instagram.com/{f_username}/",
                "username": f_username,
                "display_name": item.get("fullName"),
                "has_profile_picture": has_pic,
                "is_private": is_priv,
                "is_verified": is_verif,
                "followers": None,
                "following": None,
                "posts": None,
                "bio": None,
                "collection_status": "partial",
            }
            followers.append(follower)

        if not followers:
            raise Exception(f"Apify actor returned 0 followers for '{username}'. Ensure the account is public and exists.")

        logger.info(f"Apify run complete for {username}. Consumed {len(followers)} results from actor '{APIFY_ACTOR_ID}'.")
        return followers

    @staticmethod
    def validate_session() -> dict:
        """
        Runs a minimal test call (1 follower) to check if the session is still valid.
        Returns {"status": "valid" | "expired" | "unknown", "message": "..."}
        """
        token = os.getenv("APIFY_API_TOKEN")
        session_id = os.getenv("INSTAGRAM_SESSION_ID")
        
        if not session_id:
            return {"status": "unknown", "message": "No INSTAGRAM_SESSION_ID provided in .env"}
        if not token:
            return {"status": "unknown", "message": "No APIFY_API_TOKEN provided in .env"}
            
        try:
            ApifyInstagramCollector.get_follower_sample("instagram", 1)
            return {"status": "valid", "message": "Session is active and valid"}
        except Exception as e:
            err_str = str(e).lower()
            if "expired" in err_str or "auth_required" in err_str or "checkpoint" in err_str or "session" in err_str or "login" in err_str:
                return {"status": "expired", "message": str(e)}
            return {"status": "unknown", "message": str(e)}
