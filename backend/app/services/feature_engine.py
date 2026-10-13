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
    """Calculate the proportion of digits in a username."""
    if not username:
        return 0.0

    username = str(username)
    digit_count = sum(char.isdigit() for char in username)
    return round(digit_count / len(username), 4)


def calculate_follower_following_ratio(
    followers: float,
    following: float
) -> float | None:
    """Calculate followers / following ratio."""
    if followers is None or following is None:
        return None

    if following == 0:
        return float(followers)

    return round(followers / following, 4)


def calculate_profile_completeness(profile: dict) -> float:
    """
    Calculate profile completeness based on available core profile fields:
    {username, non-empty bio, followers, following, posts, has_profile_picture}.
    """
    username_val = profile.get("username")
    has_username = bool(username_val and str(username_val).strip()) or (profile.get("username_digit_ratio") is not None)

    bio_val = profile.get("bio")
    has_bio = bool(bio_val and str(bio_val).strip()) or (
        profile.get("bio_length") is not None and profile.get("bio_length") > 0
    )

    has_followers = profile.get("followers") is not None
    has_following = profile.get("following") is not None
    has_posts = profile.get("posts") is not None
    has_pic = profile.get("has_profile_picture") is not None

    present_count = sum([has_username, has_bio, has_followers, has_following, has_posts, has_pic])
    return round(present_count / 6.0, 4)


def extract_features(profile: dict) -> dict:
    """
    Convert collected profile data into the feature schema required by the ML model.
    Missing values remain None to honestly reflect data sufficiency.
    Honours pre-computed bio_length / username_digit_ratio when raw fields are absent.
    """
    username = profile.get("username")
    bio = profile.get("bio")

    followers = profile.get("followers")
    following = profile.get("following")
    posts = profile.get("posts")

    # Bio length: raw bio takes precedence, fallback to supplied bio_length
    if bio is not None:
        bio_length = float(len(bio))
    elif profile.get("bio_length") is not None:
        bio_length = float(profile.get("bio_length"))
    else:
        bio_length = None

    # Username digit ratio: raw username takes precedence, fallback to supplied ratio
    if username is not None and str(username).strip() != "":
        username_digit_ratio = calculate_username_digit_ratio(str(username))
    elif profile.get("username_digit_ratio") is not None:
        username_digit_ratio = float(profile.get("username_digit_ratio"))
    else:
        username_digit_ratio = 0.0

    has_profile_picture = profile.get("has_profile_picture")
    is_private = profile.get("is_private")

    # Follower-following ratio
    if followers is not None and following is not None:
        follower_following_ratio = calculate_follower_following_ratio(followers, following)
    elif profile.get("follower_following_ratio") is not None:
        follower_following_ratio = float(profile.get("follower_following_ratio"))
    else:
        follower_following_ratio = None

    # Profile completeness
    if (
        profile.get("profile_completeness") is not None
        and username is None
        and bio is None
        and followers is None
        and following is None
        and posts is None
        and has_profile_picture is None
    ):
        profile_completeness = float(profile.get("profile_completeness"))
    else:
        profile_completeness = calculate_profile_completeness(profile)

    return {
        "followers": float(followers) if followers is not None else None,
        "following": float(following) if following is not None else None,
        "posts": float(posts) if posts is not None else None,
        "bio_length": bio_length,
        "has_profile_picture": int(has_profile_picture) if has_profile_picture is not None else None,
        "is_private": int(is_private) if is_private is not None else None,
        "username_digit_ratio": username_digit_ratio,
        "follower_following_ratio": follower_following_ratio,
        "profile_completeness": profile_completeness,
    }