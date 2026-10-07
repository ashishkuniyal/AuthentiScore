"""
AuthentiScore — BaseCollector
=============================

Abstract base class that all platform-specific collectors must implement.

Every collector:
  1. Declares which URLs it handles via can_handle().
  2. Fetches raw platform data via collect().
  3. Normalises raw data into the common AuthentiScore profile schema
     via normalize().
  4. Validates the normalized profile via validate().

The normalized schema (from normalize()) is always:

{
    "platform":             str,
    "profile_url":          str,
    "username":             str | None,
    "display_name":         str | None,
    "bio":                  str | None,
    "followers":            float | None,
    "following":            float | None,
    "posts":                float | None,
    "has_profile_picture":  int | None,   # 0 or 1
    "is_private":           int | None,   # 0 or 1
    "collection_source":    str,          # "official_api" | "permitted_public_page" | "none"
    "collection_status":    str,          # "success" | "partial" | "failed"
    "collected_at":         str,          # ISO-8601 UTC timestamp
    "fields_collected":     list[str],    # which fields were actually obtained
    "error":                str | None,
}

Collectors MUST NOT:
  - Bypass authentication or login walls.
  - Solve or simulate CAPTCHA.
  - Bypass rate limits via retry loops.
  - Store passwords, tokens, private messages, or personal data
    beyond the schema fields listed above.
  - Invent or fabricate missing values.
"""

from abc import ABC, abstractmethod


class BaseCollector(ABC):
    """
    Abstract base class for AuthentiScore platform collectors.
    """

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """
        Return True if this collector is appropriate for the given URL.

        Called by the dispatcher before attempting collection.
        """

    @abstractmethod
    def collect(self, url: str) -> dict:
        """
        Attempt to fetch raw profile data from the permitted public source.

        Returns a raw dict whose keys are platform-specific.
        Must not raise exceptions — return an error dict instead.
        """

    @abstractmethod
    def normalize(self, raw: dict) -> dict:
        """
        Convert a raw collector result into the common AuthentiScore
        profile schema described in the module docstring.
        """

    @abstractmethod
    def validate(self, profile: dict) -> dict:
        """
        Validate a normalized profile.

        Adds / updates:
          - collection_status: "success" | "partial" | "failed"
          - error message if important fields are missing

        Returns the validated profile dict.
        """

    # ------------------------------------------------------------------
    # Convenience entry point
    # ------------------------------------------------------------------

    def run(self, url: str) -> dict:
        """
        Full collection pipeline: collect → normalize → validate.

        Callers should use this rather than calling the methods
        individually.
        """
        raw = self.collect(url)
        profile = self.normalize(raw)
        return self.validate(profile)
