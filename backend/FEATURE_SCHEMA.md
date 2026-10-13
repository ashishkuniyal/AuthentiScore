# AuthentiScore Feature Schema Specification

Schema Version: **v4**

This document specifies the exact feature definitions, mathematical formulations, and platform availability for all features extracted by AuthentiScore in `app.services.features`.

---

## 1. Core Feature Set (Benchmark / Public Datasets)

These 9 features are available in public academic benchmarks (such as the Instagram Spammer and InstaFake datasets) and are supported across all platforms.

| Feature | Type | Value Range | Platforms | Definition / Formula |
| :--- | :--- | :--- | :--- | :--- |
| `followers` | `float` | $[0, \infty)$ | Instagram, Twitter/X, GitHub, YouTube, Mastodon | Total number of account followers. |
| `following` | `float` | $[0, \infty)$ | Instagram, Twitter/X, GitHub, Mastodon | Total number of accounts followed. |
| `posts` | `float` | $[0, \infty)$ | Instagram, Twitter/X, GitHub (public repos), YouTube (videos), Mastodon (toots) | Total content count posted by the account. |
| `bio_length` | `float` | $[0, \infty)$ | Instagram, Twitter/X, GitHub, YouTube, Mastodon | Character length of the profile biography. |
| `has_profile_picture` | `int` | $\{0, 1\}$ | Instagram, Twitter/X, GitHub, YouTube, Mastodon | 1 if custom avatar set, 0 if default or missing. |
| `is_private` | `int` | $\{0, 1\}$ | Instagram, Twitter/X, Mastodon | 1 if account is private / protected, 0 if public. |
| `username_digit_ratio` | `float` | $[0.0, 1.0]$ | All platforms | $\frac{\text{count of digits}}{\text{len(username)}}$ |
| `follower_following_ratio`| `float` | $[0.0, \infty)$ | Instagram, Twitter/X, GitHub, Mastodon | $\frac{\text{followers}}{\max(\text{following}, 1)}$ |
| `profile_completeness` | `float` | $[0.0, 1.0]$ | All platforms | Proportion of 6 core attributes observed: $\{\text{username}, \text{bio}, \text{followers}, \text{following}, \text{posts}, \text{avatar}\}$. |

---

## 2. Extended Behavioral & Identity Feature Set (v4)

These 15 extended features capture behavioral velocity, text-shaping, entropy, and identity congruence. When a platform does not supply the underlying data (e.g., account registration date on public unauthenticated web scrapes), the feature evaluates to `None` and is safely imputed by the median imputer.

| Feature | Type | Value Range | Platforms Supplying Data | Definition / Formula |
| :--- | :--- | :--- | :--- | :--- |
| `account_age_days` | `float \| None` | $[0.0, \infty)$ | Twitter/X (API), GitHub, Mastodon | Days elapsed since account creation ($\text{now} - \text{created\_at}$). |
| `posts_per_day` | `float \| None` | $[0.0, \infty)$ | Twitter/X, GitHub, Mastodon | $\frac{\text{posts}}{\max(\text{account\_age\_days}, 1.0)}$ |
| `followers_per_day` | `float \| None` | $[0.0, \infty)$ | Twitter/X, GitHub, Mastodon | Follower acquisition velocity: $\frac{\text{followers}}{\max(\text{account\_age\_days}, 1.0)}$ |
| `following_per_day` | `float \| None` | $[0.0, \infty)$ | Twitter/X, GitHub, Mastodon | Outgoing follow velocity: $\frac{\text{following}}{\max(\text{account\_age\_days}, 1.0)}$ |
| `is_verified` | `int \| None` | $\{0, 1\}$ | Instagram, Twitter/X, Mastodon, YouTube | 1 if platform-verified badge or business status confirmed. |
| `has_external_link` | `int` | $\{0, 1\}$ | All platforms | 1 if bio contains HTTP/HTTPS URL or `external_url` field is present. |
| `link_shortener_in_bio`| `int` | $\{0, 1\}$ | All platforms | 1 if bio or website uses link shorteners (bit.ly, t.co, linktr.ee, etc.) or chat redirects. |
| `bio_emoji_ratio` | `float` | $[0.0, 1.0]$ | All platforms | Proportion of emoji/pictograph characters in bio text. |
| `bio_uppercase_ratio`| `float` | $[0.0, 1.0]$ | All platforms | Proportion of uppercase alphabetical characters in bio. |
| `bio_digit_ratio` | `float` | $[0.0, 1.0]$ | All platforms | Proportion of numeric digits in bio text. |
| `username_entropy` | `float` | $[0.0, \infty)$ | All platforms | Shannon entropy of characters: $-\sum p(c) \log_2 p(c)$. High entropy indicates random generation. |
| `username_has_long_digit_run` | `int` | $\{0, 1\}$ | All platforms | 1 if username contains $\ge 4$ consecutive numerical digits. |
| `username_repeated_chars` | `int` | $[1, \infty)$ | All platforms | Maximum consecutive identical character run length (e.g. `aaaaa` $\rightarrow 5$). |
| `display_name_matches_username` | `float` | $[0.0, 1.0]$ | All platforms | Normalized bigram Jaccard similarity between username and display name. |
| `bio_language` | `str` | `{'en', 'es', 'ar', 'ru', 'zh', 'other', 'none'}` | All platforms | Detected script/language of the bio text used to gate English NLP models. |
