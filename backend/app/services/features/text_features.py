"""
AuthentiScore — Bio & Text Shape Features (A3)
==============================================
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional
from urllib.parse import urlparse

LINK_SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "buff.ly",
    "is.gd", "cutt.ly", "rebrand.ly", "shorturl.at", "linktr.ee",
    "beacons.ai", "snip.ly", "rotf.lol", "t.me", "wa.me", "chat.whatsapp.com"
}

URL_REGEX = re.compile(
    r"(?:https?://|www\.)[a-zA-Z0-9.\-_]+(?:\.[a-zA-Z]{2,})(?:/[^\s]*)?",
    re.IGNORECASE,
)


def calculate_has_external_link(
    bio: Optional[str],
    external_url: Optional[str] = None,
) -> int:
    """
    Check if profile bio contains an HTTP(S) URL or external_url is set.
    Returns 1 if a link is present, else 0.
    """
    if external_url and str(external_url).strip():
        return 1
    if not bio:
        return 0
    return 1 if bool(URL_REGEX.search(str(bio))) else 0


def calculate_link_shortener_in_bio(
    bio: Optional[str],
    external_url: Optional[str] = None,
) -> int:
    """
    Detect if any link in the bio or external_url uses a link shortener or direct-message redirect.
    Link shorteners are heavily correlated with affiliate phishing and spam bots.
    Returns 1 if detected, else 0.
    """
    targets = []
    if external_url:
        targets.append(str(external_url))
    if bio:
        found_urls = URL_REGEX.findall(str(bio))
        targets.extend(found_urls)

    for u in targets:
        clean = u.lower()
        if not clean.startswith(("http://", "https://")):
            clean = "https://" + clean
        try:
            domain = urlparse(clean).netloc.lower()
            if domain in LINK_SHORTENERS or any(domain.endswith("." + s) for s in LINK_SHORTENERS):
                return 1
        except Exception:
            continue
    return 0


def calculate_bio_emoji_ratio(bio: Optional[str]) -> float:
    """
    Calculate the ratio of emoji characters in the bio text.
    High emoji stuffing often marks spam/promotional affiliate bios.
    """
    if not bio:
        return 0.0
    text = str(bio).strip()
    if not text:
        return 0.0

    emoji_count = 0
    for char in text:
        # Check standard Unicode emoji ranges and symbols
        cp = ord(char)
        if (
            0x1F300 <= cp <= 0x1F6FF or  # Misc symbols & pictographs, Emoticons
            0x1F900 <= cp <= 0x1F9FF or  # Supplemental symbols & pictographs
            0x1FA70 <= cp <= 0x1FAFF or  # Symbols and pictographs extended
            0x2600  <= cp <= 0x27BF  or  # Misc symbols, Dingbats
            unicodedata.category(char) in {"So", "Sk"}
        ):
            emoji_count += 1

    return round(emoji_count / len(text), 4)


def calculate_bio_uppercase_ratio(bio: Optional[str]) -> float:
    """
    Calculate uppercase character ratio in bio text (excluding whitespace/punctuation).
    Excessive all-caps indicates urgency or promotional shouting.
    """
    if not bio:
        return 0.0
    text = str(bio).strip()
    alpha_chars = [c for c in text if c.isalpha()]
    if not alpha_chars:
        return 0.0
    upper_count = sum(1 for c in alpha_chars if c.isupper())
    return round(upper_count / len(alpha_chars), 4)


def calculate_bio_digit_ratio(bio: Optional[str]) -> float:
    """Calculate numeric digit ratio in bio text."""
    if not bio:
        return 0.0
    text = str(bio).strip()
    if not text:
        return 0.0
    digit_count = sum(1 for c in text if c.isdigit())
    return round(digit_count / len(text), 4)


def detect_bio_language(bio: Optional[str]) -> str:
    """
    Lightweight deterministic language and script detector for bio text.
    Used to gate English-only NLP pipelines.
    Returns: 'en', 'es', 'ar', 'ru', 'zh', 'other', or 'none'.
    """
    if not bio or not str(bio).strip():
        return "none"

    text = str(bio).strip()

    # Check script blocks
    arabic_count = sum(1 for c in text if 0x0600 <= ord(c) <= 0x06FF)
    cyrillic_count = sum(1 for c in text if 0x0400 <= ord(c) <= 0x04FF)
    cjk_count = sum(1 for c in text if 0x4E00 <= ord(c) <= 0x9FFF or 0x3040 <= ord(c) <= 0x30FF)

    total_alpha = sum(1 for c in text if c.isalpha())
    if total_alpha == 0:
        return "none"

    if arabic_count / total_alpha > 0.3:
        return "ar"
    if cyrillic_count / total_alpha > 0.3:
        return "ru"
    if cjk_count / total_alpha > 0.3:
        return "zh"

    # Latin-script heuristic check for common English stop words
    words = re.findall(r"\b[a-zA-Z]+\b", text.lower())
    if not words:
        return "other"

    en_stops = {"the", "and", "for", "with", "my", "of", "in", "to", "is", "dm", "follow", "free", "life", "artist"}
    if any(w in en_stops for w in words):
        return "en"

    return "en" if all(ord(c) < 128 for c in text if c.isalpha()) else "other"
