"""
AuthentiScore — URL and Handle Normalizer Unit Tests (B1)
=========================================================

Table-driven tests covering >= 40 cases across platforms, formats,
query strings, reserved slugs, and edge cases.
"""

import pytest
from app.services.url_normalizer import normalize_profile_input


TEST_CASES = [
    # 1. Plain handles
    ("natgeo", "instagram", True, "instagram", "natgeo", "https://www.instagram.com/natgeo"),
    ("@natgeo", "instagram", True, "instagram", "natgeo", "https://www.instagram.com/natgeo"),
    ("@TheRock", "instagram", True, "instagram", "therock", "https://www.instagram.com/therock"),
    ("john.doe_99", "instagram", True, "instagram", "john.doe_99", "https://www.instagram.com/john.doe_99"),
    ("@jack", "twitter", True, "twitter", "jack", "https://x.com/jack"),
    
    # 2. Instagram standard URLs
    ("https://instagram.com/natgeo", "instagram", True, "instagram", "natgeo", "https://www.instagram.com/natgeo"),
    ("https://www.instagram.com/natgeo/", "instagram", True, "instagram", "natgeo", "https://www.instagram.com/natgeo"),
    ("http://instagram.com/natgeo", "instagram", True, "instagram", "natgeo", "https://www.instagram.com/natgeo"),
    ("instagram.com/natgeo", "instagram", True, "instagram", "natgeo", "https://www.instagram.com/natgeo"),
    ("www.instagram.com/natgeo", "instagram", True, "instagram", "natgeo", "https://www.instagram.com/natgeo"),
    ("https://m.instagram.com/natgeo", "instagram", True, "instagram", "natgeo", "https://www.instagram.com/natgeo"),
    ("https://mobile.instagram.com/natgeo", "instagram", True, "instagram", "natgeo", "https://www.instagram.com/natgeo"),
    ("https://instagr.am/natgeo", "instagram", True, "instagram", "natgeo", "https://www.instagram.com/natgeo"),
    ("https://instagram.com/@natgeo", "instagram", True, "instagram", "natgeo", "https://www.instagram.com/natgeo"),

    # 3. Instagram tracking parameters & query stripping
    ("https://instagram.com/natgeo?igshid=12345", "instagram", True, "instagram", "natgeo", "https://www.instagram.com/natgeo"),
    ("https://www.instagram.com/natgeo/?utm_source=ig_web_copy_link&utm_medium=banner", "instagram", True, "instagram", "natgeo", "https://www.instagram.com/natgeo"),
    
    # 4. Instagram posts/reels and reserved paths (invalid profile)
    ("https://instagram.com/p/B123456789/", "instagram", False, "instagram", "", None),
    ("https://instagram.com/reel/C987654321", "instagram", False, "instagram", "", None),
    ("https://instagram.com/tv/D111111111", "instagram", False, "instagram", "", None),
    ("https://instagram.com/explore", "instagram", False, "instagram", "", None),
    ("https://instagram.com/settings", "instagram", False, "instagram", "", None),
    ("https://instagram.com/accounts/login", "instagram", False, "instagram", "", None),

    # 5. Twitter / X URLs
    ("https://twitter.com/jack", "twitter", True, "twitter", "jack", "https://x.com/jack"),
    ("https://www.twitter.com/jack/", "twitter", True, "twitter", "jack", "https://x.com/jack"),
    ("https://mobile.twitter.com/jack", "twitter", True, "twitter", "jack", "https://x.com/jack"),
    ("https://x.com/jack", "twitter", True, "twitter", "jack", "https://x.com/jack"),
    ("https://www.x.com/jack", "twitter", True, "twitter", "jack", "https://x.com/jack"),
    ("x.com/jack", "twitter", True, "twitter", "jack", "https://x.com/jack"),
    ("https://x.com/jack?s=20&t=abcdefg", "twitter", True, "twitter", "jack", "https://x.com/jack"),

    # 6. Twitter status URLs (extracts author username)
    ("https://twitter.com/jack/status/20", "twitter", True, "twitter", "jack", "https://x.com/jack"),
    ("https://x.com/elonmusk/status/1700000000000000000", "twitter", True, "twitter", "elonmusk", "https://x.com/elonmusk"),

    # 7. Twitter reserved pages
    ("https://twitter.com/home", "twitter", False, "twitter", "", None),
    ("https://x.com/explore", "twitter", False, "twitter", "", None),
    ("https://x.com/notifications", "twitter", False, "twitter", "", None),

    # 8. Mastodon webfinger and URL formats
    ("@alice@mastodon.social", "mastodon", True, "mastodon", "alice", "https://mastodon.social/@alice"),
    ("bob@fosstodon.org", "mastodon", True, "mastodon", "bob", "https://fosstodon.org/@bob"),
    ("https://mastodon.social/@alice", "mastodon", True, "mastodon", "alice", "https://mastodon.social/@alice"),
    ("https://fosstodon.org/@charlie/", "mastodon", True, "mastodon", "charlie", "https://fosstodon.org/@charlie"),

    # 9. YouTube channel and handle formats
    ("https://www.youtube.com/@mkbhd", "youtube", True, "youtube", "mkbhd", "https://www.youtube.com/@mkbhd"),
    ("https://youtube.com/@Veritasium?si=98765", "youtube", True, "youtube", "veritasium", "https://www.youtube.com/@veritasium"),
    ("https://youtube.com/c/3Blue1Brown", "youtube", True, "youtube", "3blue1brown", "https://www.youtube.com/c/3blue1brown"),
    ("https://youtube.com/channel/UC123456789", "youtube", True, "youtube", "uc123456789", "https://www.youtube.com/channel/uc123456789"),
    ("https://youtube.com/user/PewDiePie", "youtube", True, "youtube", "pewdiepie", "https://www.youtube.com/user/pewdiepie"),

    # 10. TikTok URLs
    ("https://www.tiktok.com/@khaby.lame", "tiktok", True, "tiktok", "khaby.lame", "https://www.tiktok.com/@khaby.lame"),
    ("https://tiktok.com/@charlidamelio?lang=en", "tiktok", True, "tiktok", "charlidamelio", "https://www.tiktok.com/@charlidamelio"),

    # 11. Invalid / Empty / Unsupported inputs
    ("", "instagram", False, "instagram", "", None),
    ("   ", "instagram", False, "instagram", "", None),
    ("https://unknown-network-site.com/user", "instagram", False, "unknown", "", None),
    ("invalid$username#character", "instagram", False, "instagram", "", None),
]


@pytest.mark.parametrize("raw_input,hint_platform,expected_valid,expected_platform,expected_user,expected_canonical", TEST_CASES)
def test_normalize_profile_input_table(
    raw_input,
    hint_platform,
    expected_valid,
    expected_platform,
    expected_user,
    expected_canonical
):
    result = normalize_profile_input(raw_input, default_platform=hint_platform)

    assert result["valid"] == expected_valid, f"Failed for input '{raw_input}': expected valid={expected_valid}, got {result['valid']}"
    if expected_valid:
        assert result["platform"] == expected_platform
        assert result["username"] == expected_user
        if expected_canonical:
            assert result["canonical_url"] == expected_canonical
        assert result["error"] is None
    else:
        assert result["error"] is not None
