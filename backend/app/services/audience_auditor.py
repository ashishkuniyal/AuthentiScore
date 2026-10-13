import io
import csv
import logging
import os
import math
import uuid
import httpx
from datetime import datetime, timezone
from collections import Counter

from app.database.mongodb import influencer_audits_collection
from app.services.collector import validate_profile_url, collect_profile
from app.routes.scan import run_risk_pipeline
from app.services.collectors.apify_instagram_collector import ApifyInstagramCollector
from app.core.risk_levels import is_suspicious
from app.core.ws import notify_user_threadsafe

logger = logging.getLogger(__name__)


def calculate_wilson_ci(fake_count, total, z=1.96):
    if total == 0:
        return 0, 0
    phat = fake_count / total
    denominator = 1 + z**2 / total
    centre_adj_prob = phat + z**2 / (2 * total)
    adj_std_dev = math.sqrt((phat * (1 - phat) + z**2 / (4 * total)) / total)

    lower_bound = (centre_adj_prob - z * adj_std_dev) / denominator
    upper_bound = (centre_adj_prob + z * adj_std_dev) / denominator
    return max(0, lower_bound * 100), min(100, upper_bound * 100)


def score_profile(identifier: str, platform: str, collected_data: dict) -> dict:
    try:
        if collected_data.get("collection_status") == "failed":
            return {
                "result": {
                    "identifier": identifier,
                    "platform": platform,
                    "score": 0,
                    "classification": "Collection Failed",
                    "status": "collection_failed",
                    "is_mocked": False
                },
                "is_fake": False,
                "red_flags": []
            }

        bio = collected_data.get("bio", "") or ""
        pipeline_res = run_risk_pipeline(collected_data, bio)

        final_score = pipeline_res.get("final_score")
        classification = pipeline_res.get("classification", "Low Risk")

        if classification == "Insufficient Data" or final_score is None:
            return {
                "result": {
                    "identifier": identifier,
                    "platform": platform,
                    "score": None,
                    "classification": "Insufficient Data",
                    "status": "Success",
                    "is_mocked": False,
                    "top_ml_factors": None,
                    "nlp_signals": None,
                    "features": collected_data
                },
                "is_fake": False,
                "red_flags": []
            }

        is_fake = bool(is_suspicious(final_score))
        red_flags = []
        for factor in (pipeline_res.get("top_ml_factors") or []):
            red_flags.append(factor.get("feature", ""))
        for cat in (pipeline_res.get("nlp_signals") or {}).get("matched_categories", []):
            red_flags.append(cat)

        return {
            "result": {
                "identifier": identifier,
                "platform": platform,
                "score": round(float(final_score), 1),
                "classification": classification,
                "status": "Success",
                "is_mocked": False,
                "top_ml_factors": pipeline_res.get("top_ml_factors") or [],
                "nlp_signals": pipeline_res.get("nlp_signals") or {},
                "features": collected_data
            },
            "is_fake": is_fake,
            "red_flags": red_flags
        }
    except Exception as e:
        logger.exception(f"Failed to process profile {identifier}: {e}")
        return {
            "result": {
                "identifier": identifier,
                "platform": platform,
                "score": 0,
                "classification": "Error",
                "status": "collection_failed",
                "is_mocked": False
            },
            "is_fake": False,
            "red_flags": []
        }


def fetch_live_followers(platform: str, target: str, limit: int) -> list:
    target = target.lstrip("@")
    platform = platform.lower()

    if platform == "mastodon":
        with httpx.Client(timeout=10.0) as client:
            res = client.get(f"https://mastodon.social/api/v1/accounts/lookup?acct={target}")
            if res.status_code == 200:
                user_id = res.json().get("id")
                f_res = client.get(f"https://mastodon.social/api/v1/accounts/{user_id}/followers?limit={limit}")
                if f_res.status_code == 200:
                    return [user["username"] for user in f_res.json()]
        return []

    elif platform == "github":
        gh_token = os.getenv("GITHUB_TOKEN")
        headers = {"Authorization": f"Bearer {gh_token}"} if gh_token else {}
        with httpx.Client(timeout=10.0, headers=headers) as client:
            resp = client.get(f"https://api.github.com/users/{target}/followers?per_page={limit}")
            if resp.status_code == 200:
                return [user["login"] for user in resp.json()]
        return []

    elif platform in ["twitter", "x"]:
        token = os.getenv("TWITTER_BEARER_TOKEN")
        if not token:
            raise ValueError("TWITTER_BEARER_TOKEN is not set in environment")
        headers = {"Authorization": f"Bearer {token}"}
        with httpx.Client(timeout=10.0, headers=headers) as client:
            user_resp = client.get(f"https://api.twitter.com/2/users/by/username/{target}")
            if user_resp.status_code == 401:
                raise Exception("Twitter Bearer Token invalid or expired")
            if user_resp.status_code == 429:
                raise Exception("Twitter API rate limit reached.")
            if user_resp.status_code == 402:
                raise Exception("Twitter API credits depleted (Payment Required).")
            if user_resp.status_code != 200:
                return []
            user_data = user_resp.json().get("data")
            if not user_data:
                return []
            user_id = user_data["id"]
            followers_resp = client.get(
                f"https://api.twitter.com/2/users/{user_id}/followers?max_results={min(limit, 1000)}"
            )
            if followers_resp.status_code == 200:
                return [user["username"] for user in followers_resp.json().get("data", [])]
        return []

    elif platform == "instagram":
        return ApifyInstagramCollector.get_follower_sample(target, limit)

    elif platform == "youtube":
        raise Exception("YouTube does not provide a public follower list API.")
    else:
        raise ValueError(f"Unsupported platform: {platform}")


def parse_csv_for_profiles(csv_content: str) -> list[str]:
    """Parses a single-column CSV string looking for a header like 'username' or 'profile_url'"""
    reader = csv.reader(io.StringIO(csv_content))
    lines = list(reader)
    if not lines:
        return []

    first_row = lines[0][0].strip().lower() if lines[0] else ""
    start_idx = 1 if first_row in ["username", "profile_url", "url", "profile", "user"] else 0

    profiles = []
    for row in lines[start_idx:]:
        if not row or not row[0].strip():
            continue
        profiles.append(row[0].strip())

    return profiles


def run_audience_audit(csv_content: str, target_influencer: str = "Unknown", user_id: str | None = None) -> dict:
    audit_id = str(uuid.uuid4())
    profiles_to_scan = parse_csv_for_profiles(csv_content)

    if not profiles_to_scan:
        raise ValueError("CSV file is empty or improperly formatted.")

    sample_size = len(profiles_to_scan)
    results = []
    risk_counts = {"low": 0, "medium": 0, "high": 0, "very_high": 0, "insufficient_data": 0}
    red_flag_counter = Counter()
    total_fake = 0

    for identifier in profiles_to_scan:
        is_url = "://" in identifier or any(domain in identifier for domain in ["instagram.com", "twitter.com", "x.com"])
        url_to_scan = identifier if is_url else f"https://instagram.com/{identifier.lstrip('@')}"

        validation = validate_profile_url(url_to_scan)
        if not validation["valid"]:
            continue

        collected = collect_profile(url_to_scan)
        score_res = score_profile(identifier, validation["platform"], collected)

        res = score_res["result"]
        results.append(res)

        if res["status"] == "Success":
            if res["classification"] == "Insufficient Data":
                risk_counts["insufficient_data"] += 1
            else:
                cls_key = res["classification"].lower().replace(" risk", "").replace(" ", "_")
                if cls_key not in risk_counts:
                    risk_counts[cls_key] = 0
                risk_counts[cls_key] += 1

                if score_res["is_fake"]:
                    total_fake += 1
                for flag in score_res["red_flags"]:
                    if flag:
                        red_flag_counter[flag] += 1

    successful_scans = [r for r in results if r["status"] == "Success"]
    successful_count = len(successful_scans)

    valid_count = len([r for r in successful_scans if r["classification"] != "Insufficient Data"])
    fake_percentage = (total_fake / valid_count * 100) if valid_count > 0 else 0
    ci_lower, ci_upper = calculate_wilson_ci(total_fake, valid_count)
    collection_success_rate = (successful_count / sample_size * 100) if sample_size > 0 else 0
    top_red_flags = [{"flag": flag, "count": count} for flag, count in red_flag_counter.most_common(5)]

    audit_record = {
        "audit_id": audit_id,
        "user_id": user_id,
        "target_influencer": target_influencer,
        "timestamp": datetime.now(timezone.utc),
        "sample_size": sample_size,
        "successful_scans": successful_count,
        "valid_scans": valid_count,
        "collection_success_rate": round(collection_success_rate, 1),
        "fake_percentage": round(fake_percentage, 1),
        "ci_lower": round(ci_lower, 1),
        "ci_upper": round(ci_upper, 1),
        "risk_breakdown": risk_counts,
        "top_red_flags": top_red_flags,
        "followers_data": results
    }

    influencer_audits_collection.insert_one(audit_record)

    audit_record["_id"] = str(audit_record["_id"])
    audit_record["timestamp"] = audit_record["timestamp"].isoformat()

    return audit_record


def run_live_audience_audit(
    target_influencer: str,
    platform: str,
    sample_size: int,
    audit_id: str,
    user_id: str | None = None,
    simulate_fallback: bool = False
):
    try:
        profiles_to_scan = fetch_live_followers(platform, target_influencer, sample_size)
        if not profiles_to_scan:
            raise Exception(f"Failed to retrieve followers for {target_influencer} on {platform}.")
    except Exception as e:
        logger.error(f"Live follower fetch error: {e}")
        notify_user_threadsafe(user_id, {
            "type": "AUDIT_ERROR",
            "audit_id": audit_id,
            "message": str(e)
        })
        return

    results = []
    risk_counts = {"low": 0, "medium": 0, "high": 0, "very_high": 0, "insufficient_data": 0}
    red_flag_counter = Counter()
    total_fake = 0
    actual_sample_size = len(profiles_to_scan)

    for idx, identifier_data in enumerate(profiles_to_scan):
        try:
            if isinstance(identifier_data, dict):
                collected = identifier_data
                identifier = collected["identifier"]
                collected["collection_status"] = "success"
                collected["collection_source"] = "apify"
                if "fields_collected" not in collected:
                    collected["fields_collected"] = ["username", "has_profile_picture", "is_private", "is_verified"]
            else:
                identifier = identifier_data
                if platform == "mastodon":
                    url_to_scan = f"https://mastodon.social/@{identifier.lstrip('@')}"
                else:
                    url_to_scan = f"https://{platform}.com/{identifier.lstrip('@')}"
                collected = collect_profile(url_to_scan)

            score_res = score_profile(identifier, platform.capitalize(), collected)
            res = score_res["result"]
            results.append(res)

            if res["status"] == "Success":
                if res["classification"] == "Insufficient Data":
                    risk_counts["insufficient_data"] += 1
                else:
                    cls_key = res["classification"].lower().replace(" risk", "").replace(" ", "_")
                    if cls_key not in risk_counts:
                        risk_counts[cls_key] = 0
                    risk_counts[cls_key] += 1

                    if score_res["is_fake"]:
                        total_fake += 1
                    for flag in score_res["red_flags"]:
                        if flag:
                            red_flag_counter[flag] += 1

        except Exception as e:
            logger.exception(f"Live process failed for {identifier_data}: {e}")
            res = {
                "identifier": str(identifier_data),
                "platform": platform.capitalize(),
                "score": 0,
                "classification": "Error",
                "status": "collection_failed",
                "is_mocked": False
            }
            results.append(res)

        # Notify progress with audit_id
        notify_user_threadsafe(user_id, {
            "type": "AUDIT_PROGRESS",
            "audit_id": audit_id,
            "target_influencer": target_influencer,
            "current": idx + 1,
            "total": actual_sample_size,
            "percentage": int(((idx + 1) / actual_sample_size) * 100),
            "latest_profile": res
        })

    successful_scans = [r for r in results if r["status"] == "Success"]
    successful_count = len(successful_scans)

    valid_count = len([r for r in successful_scans if r["classification"] != "Insufficient Data"])
    fake_percentage = (total_fake / valid_count * 100) if valid_count > 0 else 0
    ci_lower, ci_upper = calculate_wilson_ci(total_fake, valid_count)
    collection_success_rate = (successful_count / actual_sample_size * 100) if actual_sample_size > 0 else 0
    top_red_flags = [{"flag": flag, "count": count} for flag, count in red_flag_counter.most_common(5)]

    budget_warning = None
    if platform == "instagram" and actual_sample_size >= 100:
        budget_warning = "Note: Large sample sizes consume Apify compute credits. Please monitor your usage."

    audit_record = {
        "audit_id": audit_id,
        "user_id": user_id,
        "target_influencer": target_influencer,
        "timestamp": datetime.now(timezone.utc),
        "sample_size": actual_sample_size,
        "successful_scans": successful_count,
        "valid_scans": valid_count,
        "collection_success_rate": round(collection_success_rate, 1),
        "fake_percentage": round(fake_percentage, 1),
        "ci_lower": round(ci_lower, 1),
        "ci_upper": round(ci_upper, 1),
        "risk_breakdown": risk_counts,
        "top_red_flags": top_red_flags,
        "budget_warning": budget_warning,
        "followers_data": results
    }

    influencer_audits_collection.insert_one(audit_record)
    audit_record["_id"] = str(audit_record["_id"])
    audit_record["timestamp"] = audit_record["timestamp"].isoformat()

    notify_user_threadsafe(user_id, {
        "type": "AUDIT_COMPLETE",
        "audit_id": audit_id,
        "target_influencer": target_influencer,
        "final_result": audit_record
    })
