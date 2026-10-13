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
    "account_age_days"
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
    if followers is None or following is None:
        return None

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
    Missing values remain None to honestly reflect data sufficiency.
    """

    username = profile.get("username") or ""

    followers = profile.get("followers")
    following = profile.get("following")
    posts = profile.get("posts")
    bio = profile.get("bio")
    account_age_days = profile.get("account_age_days")

    bio_length = len(bio) if bio is not None else None

    has_profile_picture = profile.get("has_profile_picture")
    is_private = profile.get("is_private")

    username_digit_ratio = calculate_username_digit_ratio(username)

    follower_following_ratio = calculate_follower_following_ratio(
        followers,
        following
    )

    profile_completeness = calculate_profile_completeness(profile)

    return {
        "followers": float(followers) if followers is not None else None,
        "following": float(following) if following is not None else None,
        "posts": float(posts) if posts is not None else None,
        "bio_length": float(bio_length) if bio_length is not None else None,
        "has_profile_picture": int(has_profile_picture) if has_profile_picture is not None else None,
        "is_private": int(is_private) if is_private is not None else None,
        "username_digit_ratio": username_digit_ratio,
        "follower_following_ratio": follower_following_ratio,
        "profile_completeness": profile_completeness,
        "account_age_days": float(account_age_days) if account_age_days is not None else None,
    }