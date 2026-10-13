"""
AuthentiScore — Collector Test Suite
======================================

Tests all 11 specified cases using mocked HTTP responses
so no real social-media requests are made during testing.
"""

import unittest
from unittest.mock import patch, MagicMock


from app.services.collector import (
    validate_profile_url,
    detect_platform,
    extract_username,
    collect_profile,
    create_manual_profile,
)

from app.services.feature_engine import (
    extract_features,
)

from app.services.collectors.instagram_collector import InstagramCollector
from app.services.collectors.twitter_collector import TwitterCollector


# ==============================================================
# 1. Existing URL Validation Tests (preserved + updated)
# ==============================================================

class TestURLValidation(unittest.TestCase):

    def test_instagram_url(self):
        result = validate_profile_url(
            "https://www.instagram.com/testuser/"
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["platform"], "instagram")

    def test_twitter_url(self):
        result = validate_profile_url(
            "https://x.com/testuser"
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["platform"], "twitter")

    def test_unsupported_url(self):
        result = validate_profile_url(
            "https://example.com/testuser"
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["platform"], "unknown")

    def test_invalid_url(self):
        result = validate_profile_url("not-a-valid-url")
        self.assertFalse(result["valid"])

    def test_platform_detection(self):
        self.assertEqual(
            detect_platform("https://www.instagram.com/testuser/"),
            "instagram",
        )
        self.assertEqual(
            detect_platform("https://x.com/testuser"),
            "twitter",
        )

    def test_username_extraction(self):
        username = extract_username(
            "https://www.instagram.com/testuser/"
        )
        self.assertEqual(username, "testuser")


# ==============================================================
# 2. Manual Profile (fallback)
# ==============================================================

class TestManualProfile(unittest.TestCase):

    # Test 10: Manual fallback
    def test_manual_profile(self):
        profile = create_manual_profile(
            platform="instagram",
            profile_url="https://www.instagram.com/testuser/",
            username="testuser",
            followers=1200,
            following=450,
            posts=85,
            bio="Computer science student | Developer | AI ML",
            has_profile_picture=1,
            is_private=0,
        )
        self.assertEqual(profile["collection_status"], "success")
        self.assertEqual(profile["collection_source"], "user_provided")
        self.assertEqual(profile["username"], "testuser")
        self.assertEqual(profile["followers"], 1200)

    def test_manual_profile_fields_collected(self):
        profile = create_manual_profile(
            platform="instagram",
            profile_url="https://www.instagram.com/testuser/",
            username="testuser",
            followers=0,
            following=0,
            posts=0,
            bio="",
            has_profile_picture=1,
            is_private=0,
        )
        # user_provided profiles always report these fields
        self.assertIn("username", profile["fields_collected"])


# ==============================================================
# 3. Feature Generation Tests (preserved)
# ==============================================================

class TestFeatureGeneration(unittest.TestCase):

    def _make_profile(self, **kwargs):
        defaults = dict(
            platform="instagram",
            profile_url="https://www.instagram.com/testuser/",
            username="testuser",
            followers=1200,
            following=450,
            posts=85,
            bio="Computer science student",
            has_profile_picture=1,
            is_private=0,
        )
        defaults.update(kwargs)
        return create_manual_profile(**defaults)

    def test_feature_generation(self):
        profile = self._make_profile()
        features = extract_features(profile)
        expected = [
            "followers", "following", "posts", "bio_length",
            "has_profile_picture", "is_private",
            "username_digit_ratio", "follower_following_ratio",
            "profile_completeness",
        ]
        for f in expected:
            self.assertIn(f, features)

    def test_feature_values(self):
        profile = self._make_profile()
        features = extract_features(profile)
        self.assertEqual(features["followers"], 1200.0)
        self.assertEqual(features["following"], 450.0)
        self.assertEqual(features["posts"], 85.0)
        self.assertEqual(features["has_profile_picture"], 1)
        self.assertEqual(features["is_private"], 0)
        self.assertGreater(features["follower_following_ratio"], 0)

    # Test 8: Missing bio → feature engine defaults gracefully
    def test_missing_bio_defaults(self):
        profile = create_manual_profile(
            platform="instagram",
            profile_url="https://www.instagram.com/testuser/",
            username="testuser",
            followers=100,
            following=50,
            posts=10,
            bio="",    # empty bio
            has_profile_picture=1,
            is_private=0,
        )
        features = extract_features(profile)
        self.assertEqual(features["bio_length"], 0.0)

    # Test 9: Missing followers → feature engine keeps None for data sufficiency
    def test_missing_followers_defaults(self):
        # Simulate a partially collected profile with no followers
        partial_profile = {
            "platform": "instagram",
            "profile_url": "https://www.instagram.com/testuser/",
            "username": "testuser",
            "followers": None,
            "following": None,
            "posts": None,
            "bio": None,
            "has_profile_picture": None,
            "is_private": None,
            "collection_status": "partial",
            "collection_source": "permitted_public_page",
        }
        features = extract_features(partial_profile)
        self.assertIsNone(features["followers"])
        self.assertIsNone(features["following"])
        self.assertIsNone(features["posts"])

    # Test 10b: Missing profile picture → feature engine keeps None
    def test_missing_profile_picture_defaults(self):
        partial_profile = {
            "platform": "instagram",
            "profile_url": "https://www.instagram.com/testuser/",
            "username": "testuser",
            "followers": 100,
            "following": 50,
            "posts": 10,
            "bio": "Test bio",
            "has_profile_picture": None,   # not collected
            "is_private": None,
            "collection_status": "partial",
            "collection_source": "permitted_public_page",
        }
        features = extract_features(partial_profile)
        self.assertIsNone(features["has_profile_picture"])


# ==============================================================
# 4. Automated Collector Tests (mocked HTTP)
# ==============================================================

class TestInstagramCollector(unittest.TestCase):
    """
    All HTTP calls are mocked — no real requests are made.
    """

    # Test 1: Valid supported profile URL — mocked success via JSON endpoint
    @patch(
        "app.services.collectors.instagram_collector.fetch_json_endpoint"
    )
    def test_collector_success_via_json_endpoint(self, mock_fetch):
        mock_fetch.return_value = {
            "success": True,
            "status_code": 200,
            "data": {
                "graphql": {
                    "user": {
                        "username": "testuser",
                        "full_name": "Test User",
                        "biography": "A test bio",
                        "edge_followed_by": {"count": 1200},
                        "edge_follow": {"count": 450},
                        "edge_owner_to_timeline_media": {"count": 85},
                        "profile_pic_url": "https://example.com/pic.jpg",
                        "is_private": False,
                    }
                }
            },
            "error": None,
        }

        collector = InstagramCollector()
        profile = collector.run("https://www.instagram.com/testuser/")

        self.assertEqual(profile["collection_status"], "success")
        self.assertEqual(profile["platform"], "instagram")
        self.assertEqual(profile["username"], "testuser")
        self.assertEqual(profile["followers"], 1200.0)
        self.assertEqual(profile["following"], 450.0)
        self.assertEqual(profile["posts"], 85.0)
        self.assertEqual(profile["has_profile_picture"], 1)
        self.assertEqual(profile["is_private"], 0)
        self.assertIn("followers", profile["fields_collected"])

    # Test 5: Collector success (HTML fallback — JSON endpoint fails)
    @patch(
        "app.services.collectors.instagram_collector.fetch_public_page"
    )
    @patch(
        "app.services.collectors.instagram_collector.fetch_json_endpoint"
    )
    def test_collector_success_via_html(self, mock_json, mock_html):
        # JSON endpoint fails
        mock_json.return_value = {
            "success": False,
            "status_code": 400,
            "data": None,
            "error": "JSON endpoint unavailable",
        }
        # HTML with OpenGraph tags
        mock_html.return_value = {
            "success": True,
            "status_code": 200,
            "html": """
                <html>
                <head>
                    <meta property="og:title" content="Test User (@testuser)"/>
                    <meta property="og:description"
                          content="500 Followers, 200 Following, 30 Posts - A bio"/>
                    <meta property="og:image" content="https://example.com/pic.jpg"/>
                </head>
                </html>
            """,
            "error": None,
        }

        collector = InstagramCollector()
        profile = collector.run("https://www.instagram.com/testuser/")

        self.assertIn(profile["collection_status"], {"success", "partial"})
        self.assertEqual(profile["platform"], "instagram")
        self.assertIsNotNone(profile["username"])

    # Test 6: Partial collection — JSON has no numeric counts
    @patch(
        "app.services.collectors.instagram_collector.fetch_json_endpoint"
    )
    def test_partial_collection_no_counts(self, mock_fetch):
        mock_fetch.return_value = {
            "success": True,
            "status_code": 200,
            "data": {
                "graphql": {
                    "user": {
                        "username": "testuser",
                        "biography": "A bio without counts",
                        # No edge_followed_by / edge_follow / edge_owner
                    }
                }
            },
            "error": None,
        }

        collector = InstagramCollector()
        profile = collector.run("https://www.instagram.com/testuser/")

        # Username collected but counts missing → partial
        self.assertEqual(profile["collection_status"], "partial")
        self.assertEqual(profile["username"], "testuser")
        self.assertIsNone(profile["followers"])

    # Test 7: Collection failure — HTTP error
    @patch(
        "app.services.collectors.instagram_collector.fetch_public_page"
    )
    @patch(
        "app.services.collectors.instagram_collector.fetch_json_endpoint"
    )
    def test_collection_failure_http_error(self, mock_json, mock_html):
        mock_json.return_value = {
            "success": False,
            "status_code": 429,
            "data": None,
            "error": "Rate limited",
        }
        mock_html.return_value = {
            "success": False,
            "status_code": 503,
            "html": None,
            "error": "Service unavailable",
        }

        collector = InstagramCollector()
        profile = collector.run("https://www.instagram.com/testuser/")

        self.assertEqual(profile["collection_status"], "failed")
        self.assertIsNotNone(profile["error"])


class TestTwitterCollector(unittest.TestCase):

    # Test 2: Valid Twitter URL — no token → fails gracefully (Test 2)
    @patch("app.services.collectors.twitter_collector.fetch_public_page")
    def test_twitter_no_token_fails_gracefully(self, mock_fetch):
        mock_fetch.return_value = {"success": False, "error": "Network Error"}
        
        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": ""}):
            collector = TwitterCollector()
            profile = collector.run("https://x.com/testuser")
            self.assertEqual(profile["collection_status"], "failed")
            self.assertIsNotNone(profile["error"])
            # Error message should be user-friendly, not a traceback
            self.assertNotIn("Traceback", profile.get("error", ""))

    # Twitter API success path with mock token
    @patch("app.services.collectors.twitter_collector.httpx.Client")
    def test_twitter_api_success_with_token(self, mock_client_class):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "username": "testuser",
                "name": "Test User",
                "description": "A Twitter bio",
                "profile_image_url": "https://pbs.twimg.com/pic.jpg",
                "protected": False,
                "public_metrics": {
                    "followers_count": 500,
                    "following_count": 200,
                    "tweet_count": 1500,
                },
            }
        }
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": "fake_token_xyz"}):
            collector = TwitterCollector()
            profile = collector.run("https://x.com/testuser")

        self.assertEqual(profile["collection_status"], "success")
        self.assertEqual(profile["username"], "testuser")
        self.assertEqual(profile["followers"], 500.0)
        self.assertEqual(profile["collection_source"], "official_api")

    # Twitter public live extraction success path without token
    @patch("app.services.collectors.twitter_collector.fetch_public_page")
    def test_twitter_public_success_without_token(self, mock_fetch):
        import json
        mock_fetch.return_value = {
            "success": True,
            "status_code": 200,
            "html": json.dumps({
                "code": 200,
                "user": {
                    "screen_name": "testuser",
                    "name": "Test User",
                    "description": "A public Twitter bio",
                    "followers": 1250,
                    "following": 320,
                    "tweets": 850,
                    "avatar_url": "https://pbs.twimg.com/avatar.jpg",
                    "protected": False,
                    "joined": "Mon Jan 01 00:00:00 +0000 2024",
                }
            }),
            "error": None,
        }

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": ""}):
            collector = TwitterCollector()
            profile = collector.run("https://x.com/testuser")

        self.assertEqual(profile["collection_status"], "success")
        self.assertEqual(profile["username"], "testuser")
        self.assertEqual(profile["followers"], 1250.0)
        self.assertEqual(profile["following"], 320.0)
        self.assertEqual(profile["posts"], 850.0)
        self.assertEqual(profile["collection_source"], "permitted_public_page")


# ==============================================================
# 5. Dispatcher Tests
# ==============================================================

class TestDispatcher(unittest.TestCase):

    # Test 3: Unsupported platform
    def test_unsupported_platform_dispatcher(self):
        result = collect_profile("https://example.com/testuser")
        self.assertEqual(result["collection_status"], "failed")
        self.assertIsNotNone(result["error"])

    # Test 4: Malformed URL
    def test_malformed_url_dispatcher(self):
        result = collect_profile("not-a-url")
        self.assertEqual(result["collection_status"], "failed")

    # Test 11: End-to-end with manual profile
    def test_end_to_end_manual_profile(self):
        """
        Verifies that the manual fallback path produces
        a complete feature-ready profile.
        """
        profile = create_manual_profile(
            platform="instagram",
            profile_url="https://www.instagram.com/testuser/",
            username="testuser",
            followers=500,
            following=300,
            posts=42,
            bio="Blogger | Photographer",
            has_profile_picture=1,
            is_private=0,
        )
        features = extract_features(profile)

        # All 9 model features must be present
        required = [
            "followers", "following", "posts", "bio_length",
            "has_profile_picture", "is_private",
            "username_digit_ratio", "follower_following_ratio",
            "profile_completeness",
        ]
        for f in required:
            self.assertIn(f, features, f"Missing feature: {f}")

        # Sanity checks
        self.assertEqual(features["followers"], 500.0)
        self.assertEqual(features["bio_length"], float(len("Blogger | Photographer")))
        self.assertGreater(features["follower_following_ratio"], 0)

    # Instagram dispatcher — collector called correctly
    @patch("app.services.collectors.instaloader_collector.InstaLoaderCollector.run")
    @patch(
        "app.services.collectors.instagram_collector.fetch_json_endpoint"
    )
    def test_dispatcher_routes_instagram(self, mock_fetch, mock_instaloader_run):
        mock_instaloader_run.return_value = {
            "collection_status": "failed",
            "platform": "instagram",
            "identifier": "testuser",
            "error": "Instaloader rate limit 429",
            "fields_collected": []
        }
        mock_fetch.return_value = {
            "success": False,
            "status_code": 400,
            "data": None,
            "error": "Unavailable",
        }
        with patch(
            "app.services.collectors.instagram_collector.fetch_public_page"
        ) as mock_html:
            mock_html.return_value = {
                "success": False,
                "html": None,
                "status_code": 503,
                "error": "Service unavailable",
            }
            result = collect_profile(
                "https://www.instagram.com/testuser/"
            )

        # Platform is correctly identified even when collection fails
        self.assertEqual(result["platform"], "instagram")
        self.assertIn(
            result["collection_status"],
            {"success", "partial", "failed"},
        )


# ==============================================================
# Run
# ==============================================================

if __name__ == "__main__":
    unittest.main()