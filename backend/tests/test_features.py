"""
AuthentiScore — Unit Tests for Feature Engine (A3)
===================================================

Tests each individual feature function and schema compliance.
"""

from datetime import datetime, timezone
import pytest

from app.services.features import (
    FEATURE_SCHEMA_VERSION,
    CORE_FEATURES,
    EXTENDED_FEATURES,
    calculate_username_digit_ratio,
    calculate_follower_following_ratio,
    calculate_profile_completeness,
    extract_features,
)
from app.services.features.account_features import (
    calculate_account_age_days,
    calculate_followers_per_day,
    calculate_following_per_day,
    calculate_is_verified,
    calculate_posts_per_day,
)
from app.services.features.text_features import (
    calculate_bio_digit_ratio,
    calculate_bio_emoji_ratio,
    calculate_bio_uppercase_ratio,
    calculate_has_external_link,
    calculate_link_shortener_in_bio,
    detect_bio_language,
)
from app.services.features.username_features import (
    calculate_display_name_matches_username,
    calculate_username_entropy,
    calculate_username_has_long_digit_run,
    calculate_username_repeated_chars,
)


def test_schema_version_defined():
    assert FEATURE_SCHEMA_VERSION in {"v3", "v4"}
    assert len(CORE_FEATURES) == 9
    assert len(EXTENDED_FEATURES) == 24


def test_account_age_days():
    now = datetime(2026, 10, 14, 0, 0, 0, tzinfo=timezone.utc)
    # 10 days before
    created_iso = "2026-10-04T00:00:00Z"
    age = calculate_account_age_days(created_iso, now=now)
    assert age == 10.0

    # Twitter date format
    tw_date = "Sun Oct 04 00:00:00 +0000 2026"
    age_tw = calculate_account_age_days(tw_date, now=now)
    assert age_tw == 10.0

    # None input
    assert calculate_account_age_days(None) is None
    assert calculate_account_age_days("") is None


def test_velocity_metrics():
    # Posts per day
    assert calculate_posts_per_day(100, 10) == 10.0
    assert calculate_posts_per_day(None, 10) is None
    assert calculate_posts_per_day(10, None) is None

    # Follower and following velocity
    assert calculate_followers_per_day(500, 25) == 20.0
    assert calculate_following_per_day(100, 50) == 2.0


def test_is_verified():
    assert calculate_is_verified(True) == 1
    assert calculate_is_verified(False) == 0
    assert calculate_is_verified(1) == 1
    assert calculate_is_verified("true") == 1
    assert calculate_is_verified(None) is None


def test_has_external_link():
    assert calculate_has_external_link("Check my portfolio at https://example.com/art") == 1
    assert calculate_has_external_link("Just a normal bio without any links") == 0
    assert calculate_has_external_link("", external_url="https://site.org") == 1


def test_link_shortener_in_bio():
    assert calculate_link_shortener_in_bio("Get free followers: https://bit.ly/free123") == 1
    assert calculate_link_shortener_in_bio("Links: https://linktr.ee/creative_artist") == 1
    assert calculate_link_shortener_in_bio("Contact me: https://wa.me/1234567890") == 1
    assert calculate_link_shortener_in_bio("Personal website: https://example.com") == 0


def test_bio_text_shape_ratios():
    # Emoji ratio
    emoji_bio = "Travel 🌍 Nature 🌿 Photo 📸"
    assert calculate_bio_emoji_ratio(emoji_bio) > 0.05
    assert calculate_bio_emoji_ratio("No emojis here") == 0.0

    # Uppercase ratio
    shouting_bio = "WIN FREE IPHONE NOW ACT FAST"
    assert calculate_bio_uppercase_ratio(shouting_bio) == 1.0
    assert calculate_bio_uppercase_ratio("quiet lower case text") == 0.0

    # Digit ratio
    digit_bio = "Call 9876543210 for money"
    assert calculate_bio_digit_ratio(digit_bio) > 0.2


def test_detect_bio_language():
    assert detect_bio_language("Hello world, photographer and digital artist") == "en"
    assert detect_bio_language("مرحبا بكم في حسابي الرسمي") == "ar"
    assert detect_bio_language("Привет мир, официальный аккаунт") == "ru"
    assert detect_bio_language("") == "none"


def test_username_metrics():
    # Entropy
    ent_low = calculate_username_entropy("aaaaaaa")
    ent_high = calculate_username_entropy("q7x_89kz")
    assert ent_low == 0.0
    assert ent_high > 2.0

    # Consecutive digit runs
    assert calculate_username_has_long_digit_run("bot12345user") == 1
    assert calculate_username_has_long_digit_run("john99smith") == 0

    # Character repeats
    assert calculate_username_repeated_chars("johhhhn") == 4
    assert calculate_username_repeated_chars("alex") == 1

    # Congruence between username and display name
    assert calculate_display_name_matches_username("elonmusk", "Elon Musk") > 0.8
    assert calculate_display_name_matches_username("bot_991823", "Sarah Official") < 0.2


def test_extract_features_comprehensive():
    profile = {
        "platform": "twitter",
        "username": "cryptobot9999",
        "display_name": "Crypto Bot",
        "bio": "WIN FREE CRYPTO NOW! Link: https://bit.ly/claim 🔥💰",
        "followers": 15,
        "following": 5000,
        "posts": 2,
        "has_profile_picture": 0,
        "is_private": 0,
        "account_created_at": "2026-10-01T00:00:00Z",
    }
    feats = extract_features(profile)

    # Core features check
    for cf in CORE_FEATURES:
        assert cf in feats

    # Extended features check
    assert feats["has_external_link"] == 1
    assert feats["link_shortener_in_bio"] == 1
    assert feats["username_has_long_digit_run"] == 1
    assert feats["bio_uppercase_ratio"] > 0.3
    assert feats["bio_emoji_ratio"] > 0.01
    assert feats["account_age_days"] is not None
    assert feats["followers_per_day"] is not None
