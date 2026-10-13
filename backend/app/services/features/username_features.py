"""
AuthentiScore — Username & Identity Congruence Features (A3)
============================================================
"""

from __future__ import annotations

import collections
import math
import re
from typing import Optional


def calculate_username_entropy(username: Optional[str]) -> float:
    """
    Calculate Shannon entropy of characters in the username.
    Random auto-generated usernames (e.g. 'qzx_81k9m4') exhibit significantly
    higher character entropy than natural names (e.g. 'ashishkuniyal').
    """
    if not username:
        return 0.0
    u = str(username).lower().strip()
    if not u:
        return 0.0

    length = len(u)
    counts = collections.Counter(u)
    entropy = -sum((count / length) * math.log2(count / length) for count in counts.values())
    return round(float(entropy), 4)


def calculate_username_has_long_digit_run(
    username: Optional[str],
    threshold: int = 4,
) -> int:
    """
    Check if username contains a run of >= 4 consecutive digits.
    Frequently found in batch-registered bot accounts (e.g. 'john12894172').
    Returns 1 if a digit run of length >= threshold is found, else 0.
    """
    if not username:
        return 0
    pattern = rf"\d{{{threshold},}}"
    return 1 if bool(re.search(pattern, str(username))) else 0


def calculate_username_repeated_chars(username: Optional[str]) -> int:
    """
    Calculate maximum run length of identical repeated consecutive characters.
    e.g. 'aaaaaron' -> 5, 'john' -> 1.
    """
    if not username:
        return 0
    u = str(username)
    if not u:
        return 0

    max_repeat = 1
    current_repeat = 1
    for i in range(1, len(u)):
        if u[i] == u[i - 1]:
            current_repeat += 1
            max_repeat = max(max_repeat, current_repeat)
        else:
            current_repeat = 1
    return max_repeat


def calculate_display_name_matches_username(
    username: Optional[str],
    display_name: Optional[str],
) -> float:
    """
    Normalized string similarity (0.0 to 1.0) between display name and username.
    Legitimate human accounts typically have congruent display names and handles.
    Bot networks often have discordant or missing display names.
    """
    if not username or not display_name:
        return 0.0

    u_clean = re.sub(r"[^a-z0-9]", "", str(username).lower())
    d_clean = re.sub(r"[^a-z0-9]", "", str(display_name).lower())

    if not u_clean or not d_clean:
        return 0.0
    if u_clean == d_clean:
        return 1.0
    if u_clean in d_clean or d_clean in u_clean:
        return round(min(len(u_clean), len(d_clean)) / max(len(u_clean), len(d_clean)), 4)

    # Bigram Jaccard similarity
    u_bigrams = {u_clean[i:i+2] for i in range(len(u_clean) - 1)}
    d_bigrams = {d_clean[i:i+2] for i in range(len(d_clean) - 1)}

    if not u_bigrams or not d_bigrams:
        return 0.0

    intersection = len(u_bigrams.intersection(d_bigrams))
    union = len(u_bigrams.union(d_bigrams))
    return round(intersection / union if union > 0 else 0.0, 4)
