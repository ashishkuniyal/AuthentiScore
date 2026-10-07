import re


FEATURES = [
    "followers",
    "following",
    "posts",
    "bio_length",
    "has_profile_picture",
    "is_private",
    "username_digit_ratio",
    "follower_following_ratio",
    "profile_completeness",
]


def calculate_username_digit_ratio(username: str) -> float:
    """
    Calculate the proportion of digits in a username.
    """

    if not username:
        return 0.0

    username = str(username)

    digit_count = sum(char.isdigit() for char in username)

    return round(digit_count / len(username), 4)


def calculate_follower_following_ratio(
    followers: float,
    following: float
) -> float:
    """
    Calculate followers / following ratio.
    """

    if following == 0:
        return float(followers)

    return round(followers / following, 4)


def calculate_profile_completeness(profile: dict) -> float:
    """
    Calculate profile completeness based on available
    core profile fields.
    """

    fields = [
        profile.get("username"),
        profile.get("bio"),
        profile.get("followers"),
        profile.get("following"),
        profile.get("posts"),
        profile.get("has_profile_picture"),
    ]

    available = sum(
        1 for value in fields
        if value is not None
    )

    return round(available / len(fields), 4)


def extract_features(profile: dict) -> dict:
    """
    Convert collected profile data into the
    feature schema required by the ML model.
    """

    username = profile.get("username") or ""

    followers = profile.get("followers")
    following = profile.get("following")
    posts = profile.get("posts")
    bio = profile.get("bio")

    # Values that are not available from the collector
    # remain None rather than being fabricated.
    if followers is None:
        followers = 0

    if following is None:
        following = 0

    if posts is None:
        posts = 0

    if bio is None:
        bio = ""

    bio_length = len(bio)

    has_profile_picture = profile.get(
        "has_profile_picture"
    )

    if has_profile_picture is None:
        has_profile_picture = 0

    is_private = profile.get("is_private")

    if is_private is None:
        is_private = 0

    username_digit_ratio = calculate_username_digit_ratio(
        username
    )

    follower_following_ratio = calculate_follower_following_ratio(
        followers,
        following
    )

    profile_completeness = calculate_profile_completeness(
        profile
    )

    return {
        "followers": float(followers),
        "following": float(following),
        "posts": float(posts),
        "bio_length": float(bio_length),
        "has_profile_picture": int(has_profile_picture),
        "is_private": int(is_private),
        "username_digit_ratio": username_digit_ratio,
        "follower_following_ratio": follower_following_ratio,
        "profile_completeness": profile_completeness,
    }