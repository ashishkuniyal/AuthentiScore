#!/usr/bin/env python3
"""
AuthentiScore — Evaluation Label Helper CLI (A1)
=================================================

CLI tool for annotators to view stored profile snapshots and record
ground-truth labels ('fake' | 'real' | 'automated_declared') into
backend/eval/labeled_profiles.csv without fabricating data.
"""

from __future__ import annotations

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[1] / "eval"
LABELED_CSV = EVAL_DIR / "labeled_profiles.csv"
TEMPLATE_CSV = EVAL_DIR / "labeled_profiles.template.csv"

FIELDNAMES = [
    "platform", "profile_url", "username", "label", "labeler",
    "labeled_at", "notes", "followers", "following", "posts", "bio",
    "has_profile_picture", "is_private", "is_verified",
    "account_created_at", "external_url"
]


def init_labeled_csv_if_missing():
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    if not LABELED_CSV.exists():
        with open(LABELED_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
        print(f"Initialized empty labeled dataset at: {LABELED_CSV}")


def append_label(record: dict) -> None:
    init_labeled_csv_if_missing()
    with open(LABELED_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writerow(record)
    print(f"Saved label '{record['label']}' for @{record['username']} ({record['platform']}).")


def interactive_label_entry():
    print("=== AuthentiScore Profile Label Helper ===")
    print("Record a ground-truth profile snapshot for evaluation harness.")
    init_labeled_csv_if_missing()

    try:
        platform = input("Platform [instagram/twitter/github/youtube/mastodon]: ").strip().lower() or "instagram"
        username = input("Username / Handle: ").strip().lstrip("@")
        if not username:
            print("Username cannot be empty.")
            return

        profile_url = input(f"Profile URL [default https://{platform}.com/{username}]: ").strip()
        if not profile_url:
            profile_url = f"https://{platform}.com/{username}"

        followers = input("Followers count [int, default 0]: ").strip() or "0"
        following = input("Following count [int, default 0]: ").strip() or "0"
        posts = input("Posts count [int, default 0]: ").strip() or "0"
        bio = input("Bio text [optional]: ").strip()
        has_pic = input("Has profile picture [1/0, default 1]: ").strip() or "1"
        is_priv = input("Is private [1/0, default 0]: ").strip() or "0"
        is_ver = input("Is verified [1/0, default 0]: ").strip() or "0"
        created_at = input("Account created at [ISO string, optional]: ").strip()
        ext_url = input("External link [optional]: ").strip()

        print("\nChoose label:")
        print("  1. fake (bot, spammer, impersonator)")
        print("  2. real (authentic human, verified organization)")
        print("  3. automated_declared (transparent utility/feed bot)")
        choice = input("Select [1/2/3]: ").strip()

        label_map = {"1": "fake", "2": "real", "3": "automated_declared"}
        label = label_map.get(choice)
        if not label:
            print("Invalid choice. Aborting.")
            return

        labeler = input("Your name/id [default annotator]: ").strip() or "annotator"
        notes = input("Notes/rationale [optional]: ").strip()

        record = {
            "platform": platform,
            "profile_url": profile_url,
            "username": username,
            "label": label,
            "labeler": labeler,
            "labeled_at": datetime.now(timezone.utc).isoformat(),
            "notes": notes,
            "followers": int(followers),
            "following": int(following),
            "posts": int(posts),
            "bio": bio,
            "has_profile_picture": int(has_pic),
            "is_private": int(is_priv),
            "is_verified": int(is_ver),
            "account_created_at": created_at,
            "external_url": ext_url,
        }

        append_label(record)

    except (KeyboardInterrupt, EOFError):
        print("\nExiting label helper.")


if __name__ == "__main__":
    interactive_label_entry()
