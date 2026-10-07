import io
import csv
import logging
import os
import requests
import instaloader
import asyncio
import random
from datetime import datetime, timezone, timedelta
import uuid
from collections import Counter

logger = logging.getLogger(__name__)

from app.database.mongodb import influencer_audits_collection
from app.services.collector import validate_profile_url, collect_profile
from app.services.feature_engine import extract_features
from app.routes.scan import run_risk_pipeline
from app.services.collectors.apify_instagram_collector import ApifyInstagramCollector

INSTAGRAM_COOLDOWN_UNTIL = None

def fetch_live_followers(platform: str, target: str, limit: int):
    global INSTAGRAM_COOLDOWN_UNTIL
    
    platform = platform.lower()
    if platform == "github":
        resp = requests.get(f"https://api.github.com/users/{target}/followers?per_page={limit}")
        if resp.status_code == 200:
            return [user["login"] for user in resp.json()]
        return []
        
    elif platform == "twitter" or platform == "x":
        token = os.getenv("TWITTER_BEARER_TOKEN")
        if not token:
            raise ValueError("TWITTER_BEARER_TOKEN is not set in .env")
        headers = {"Authorization": f"Bearer {token}"}
        user_resp = requests.get(f"https://api.twitter.com/2/users/by/username/{target}", headers=headers)
        if user_resp.status_code == 401:
            raise Exception("Twitter Bearer Token invalid or expired — check .env")
        if user_resp.status_code == 429:
            raise Exception("Twitter API rate limit reached.")
        if user_resp.status_code != 200:
            return []
        user_data = user_resp.json().get("data")
        if not user_data:
            return []
        user_id = user_data["id"]
        followers_resp = requests.get(f"https://api.twitter.com/2/users/{user_id}/followers?max_results={min(limit, 1000)}", headers=headers)
        if followers_resp.status_code == 401:
            raise Exception("Twitter Bearer Token invalid or expired — check .env")
        if followers_resp.status_code == 429:
            raise Exception("Twitter API rate limit reached.")
        if followers_resp.status_code == 200:
            return [user["username"] for user in followers_resp.json().get("data", [])]
        return []
        
    elif platform == "instagram":
        return ApifyInstagramCollector.get_follower_sample(target, limit)
            
    elif platform == "youtube":
        raise Exception("YouTube does not provide a public follower (subscriber) list API for other channels.")
    else:
        raise ValueError(f"Unsupported platform: {platform}")


def parse_csv_for_profiles(csv_content: str):
    """Parses a single-column CSV string looking for a header like 'username' or 'profile_url'"""
    # Use python's csv sniffer/reader
    reader = csv.reader(io.StringIO(csv_content))
    lines = list(reader)
    if not lines:
        return []
    
    # Check if first line is a header
    first_row = lines[0][0].strip().lower()
    start_idx = 1 if first_row in ["username", "profile_url", "url", "profile", "user"] else 0
    
    profiles = []
    for row in lines[start_idx:]:
        if not row or not row[0].strip():
            continue
        profiles.append(row[0].strip())
        
    return profiles

def run_audience_audit(csv_content: str, target_influencer: str = "Unknown"):
    audit_id = str(uuid.uuid4())
    profiles_to_scan = parse_csv_for_profiles(csv_content)
    
    if not profiles_to_scan:
        raise ValueError("CSV file is empty or improperly formatted.")
        
    results = []
    risk_counts = {"low": 0, "medium": 0, "high": 0, "very_high": 0}
    red_flag_counter = Counter()
    total_fake = 0
    
    allow_mock = os.getenv("ALLOW_MOCK_FALLBACK", "False").lower() == "true"
    
    # Run each profile through the pipeline
    for identifier in profiles_to_scan:
        is_url = "://" in identifier or "instagram.com" in identifier or "twitter.com" in identifier or "x.com" in identifier
        url_to_scan = identifier if is_url else f"https://instagram.com/{identifier.lstrip('@')}"
        
        validation = validate_profile_url(url_to_scan)
        if not validation["valid"]:
            continue
            
        collected = collect_profile(url_to_scan)
        coll_status = collected.get("collection_status", "failed")
        is_mocked = False
        
        if coll_status in ["failed", "partial"]:
            if allow_mock:
                is_mocked = True
                is_fake = "fake" in identifier.lower() or "spam" in identifier.lower()
                is_huge = identifier.lower() in ["cristiano", "elonmusk", "mrbeast"]
                
                collected = {
                    "collection_status": "success",
                    "collection_source": "mock",
                    "platform": validation["platform"],
                    "profile_url": url_to_scan,
                    "username": identifier,
                    "display_name": identifier,
                    "followers": 12 if is_fake else (100000000 if is_huge else 15000),
                    "following": 4500 if is_fake else (100 if is_huge else 4000),
                    "posts": 0 if is_fake else (500 if is_huge else 12),
                    "bio": "Click link for free money!!!" if is_fake else ("Official account." if is_huge else "Crypto enthusiast! 🚀 Link in bio."),
                    "bio_length": 34,
                    "has_profile_picture": 0 if is_fake else 1,
                    "is_private": 0,
                    "fields_collected": ["username", "followers", "following", "posts", "bio", "has_profile_picture", "is_private"]
                }
            else:
                # Real failure, no mock allowed
                results.append({
                    "identifier": identifier,
                    "platform": validation["platform"],
                    "score": 0,
                    "classification": "Collection Failed",
                    "status": "collection_failed",
                    "is_mocked": False
                })
                continue
            
        try:
            bio = collected.get("bio", "")
            pipeline_res = run_risk_pipeline(collected, bio)
            final_score = pipeline_res.get("final_score", 0)
            
            if is_mocked:
                if is_fake:
                    final_score = 92.4 if "bot" in identifier.lower() else 88.1
                elif is_huge:
                    final_score = 12.5 if "cristiano" in identifier.lower() else (14.2 if "mrbeast" in identifier.lower() else 18.7)
                else:
                    final_score = 45.0
                    
                from app.services.risk_engine import classify_risk
                pipeline_res["final_score"] = final_score
                pipeline_res["classification"] = classify_risk(final_score)
            
            classification = pipeline_res.get("classification", "Low Risk")
            cls_key = classification.lower().replace(" risk", "").replace(" ", "_")
            
            if cls_key not in risk_counts:
                risk_counts[cls_key] = 0
            risk_counts[cls_key] += 1
            
            if final_score >= 60 or cls_key in ["high", "very_high"]:
                total_fake += 1
                
            for factor in pipeline_res.get("top_ml_factors", []):
                red_flag_counter[factor["feature"]] += 1
            for cat in pipeline_res.get("nlp_signals", {}).get("matched_categories", []):
                red_flag_counter[cat] += 1
                
            status = "Success"
        except Exception as e:
            logger.exception(f"Failed to process profile {identifier}: {e}")
            final_score = None
            classification = "Error"
            status = "collection_failed"
            
        results.append({
            "identifier": identifier,
            "platform": collected.get("platform", validation["platform"]),
            "score": final_score if final_score is not None else 0,
            "classification": classification,
            "status": status,
            "is_mocked": is_mocked
        })
        
    successful_scans = [r for r in results if r["status"] == "Success"]
    successful_count = len(successful_scans)
    
    fake_percentage = (total_fake / successful_count * 100) if successful_count > 0 else 0
    collection_success_rate = (successful_count / sample_size * 100) if sample_size > 0 else 0
    top_red_flags = [{"flag": flag, "count": count} for flag, count in red_flag_counter.most_common(5)]
    
    audit_record = {
        "audit_id": audit_id,
        "target_influencer": target_influencer,
        "timestamp": datetime.now(timezone.utc),
        "sample_size": sample_size,
        "successful_scans": successful_count,
        "collection_success_rate": round(collection_success_rate, 1),
        "fake_percentage": round(fake_percentage, 1),
        "risk_breakdown": risk_counts,
        "top_red_flags": top_red_flags,
        "followers_data": results
    }
    
    influencer_audits_collection.insert_one(audit_record)
    
    # Format for JSON response
    audit_record["_id"] = str(audit_record["_id"])
    audit_record["timestamp"] = audit_record["timestamp"].isoformat()
    
    return audit_record


import asyncio
import random

async def run_live_audience_audit(target_influencer: str, platform: str, sample_size: int, audit_id: str, simulate_fallback: bool = False):
    from app.main import manager  # Avoid circular import
    
    # allow_mock is true if env var is true OR if explicitly requested via UI for live scan
    allow_mock = simulate_fallback or (os.getenv("ALLOW_MOCK_FALLBACK", "False").lower() == "true")
    
    try:
        if allow_mock and platform == "instagram":
            # Just generate some fake profiles for demo
            profiles_to_scan = []
            for i in range(sample_size):
                if random.random() < 0.3:
                    profiles_to_scan.append(f"fake_bot_{random.randint(1000,9999)}")
                elif random.random() < 0.1:
                    profiles_to_scan.append(f"spam_account_{random.randint(10,99)}")
                else:
                    profiles_to_scan.append(f"real_user_{random.randint(100,999)}")
        else:
            profiles_to_scan = fetch_live_followers(platform, target_influencer, sample_size)
            if not profiles_to_scan:
                raise Exception(f"Failed to retrieve followers for {target_influencer} on {platform}.")
    except Exception as e:
        logger.error(f"Live follower fetch error: {e}")
        # Broadcast failure
        await manager.broadcast({
            "type": "AUDIT_ERROR",
            "audit_id": audit_id,
            "message": str(e)
        })
        return
            
    results = []
    risk_counts = {"low": 0, "medium": 0, "high": 0, "very_high": 0}
    red_flag_counter = Counter()
    total_fake = 0
    actual_sample_size = len(profiles_to_scan)
    
    for idx, identifier_data in enumerate(profiles_to_scan):
        try:
            # Check if identifier_data is already a pre-collected dict (like from Apify)
            if isinstance(identifier_data, dict):
                collected = identifier_data
                identifier = collected["identifier"]
                coll_status = "success"
                is_mocked = False
                # Re-add to ensure pipeline treats it correctly
                collected["collection_status"] = "success"
                collected["collection_source"] = "apify"
                collected["fields_collected"] = ["username", "has_profile_picture", "is_private", "is_verified"]
                
                # Mock fallback check still applies if it's "failed", but Apify only returns successful dicts
            else:
                identifier = identifier_data
                url_to_scan = f"https://{platform}.com/{identifier.lstrip('@')}"
                collected = collect_profile(url_to_scan)
                coll_status = collected.get("collection_status", "failed")
                is_mocked = False
                
            # Simulate scraping delay for mock, or normal rate limits
            if allow_mock and platform == "instagram" and coll_status in ["failed", "partial"]:
                await asyncio.sleep(0.5)
                
            if coll_status in ["failed", "partial"]:
                if allow_mock and platform == "instagram":
                    is_mocked = True
                    is_fake = "fake" in identifier.lower() or "spam" in identifier.lower()
                    collected = {
                        "collection_status": "success",
                        "collection_source": "mock",
                        "platform": platform,
                        "profile_url": f"https://{platform}.com/{identifier.lstrip('@')}",
                        "username": identifier,
                        "display_name": identifier,
                        "followers": 12 if is_fake else random.randint(100, 15000),
                        "following": 4500 if is_fake else random.randint(100, 1500),
                        "posts": 0 if is_fake else random.randint(5, 500),
                        "bio": "Click link for free money!!!" if is_fake else "Just a normal user.",
                        "bio_length": 34 if is_fake else 19,
                        "has_profile_picture": 0 if is_fake else 1,
                        "is_private": 0,
                        "fields_collected": ["username", "followers", "following", "posts", "bio", "has_profile_picture", "is_private"]
                    }
                else:
                    results.append({
                        "identifier": identifier,
                        "platform": platform,
                        "score": 0,
                        "classification": "Collection Failed",
                        "status": "collection_failed",
                        "is_mocked": False
                    })
                    # Broadcast failure row
                    await manager.broadcast({
                        "type": "AUDIT_PROGRESS",
                        "audit_id": audit_id,
                        "target_influencer": target_influencer,
                        "current": idx + 1,
                        "total": actual_sample_size,
                        "percentage": int(((idx + 1) / actual_sample_size) * 100),
                        "latest_profile": results[-1]
                    })
                    continue
                    
            bio = collected.get("bio", "")
            pipeline_res = run_risk_pipeline(collected, bio)
            final_score = pipeline_res.get("final_score", 0)
            
            if is_mocked:
                is_fake = "fake" in identifier.lower() or "spam" in identifier.lower()
                final_score = random.uniform(85.0, 95.0) if is_fake else random.uniform(10.0, 45.0)
                from app.services.risk_engine import classify_risk
                pipeline_res["final_score"] = final_score
                pipeline_res["classification"] = classify_risk(final_score)
                
            classification = pipeline_res.get("classification", "Low Risk")
            cls_key = classification.lower().replace(" risk", "").replace(" ", "_")
            
            if cls_key not in risk_counts:
                risk_counts[cls_key] = 0
            risk_counts[cls_key] += 1
            
            if final_score >= 60 or cls_key in ["high", "very_high"]:
                total_fake += 1
                
            for factor in pipeline_res.get("top_ml_factors", []):
                red_flag_counter[factor["feature"]] += 1
            for cat in pipeline_res.get("nlp_signals", {}).get("matched_categories", []):
                red_flag_counter[cat] += 1
                
            status = "Success"
        except Exception as e:
            logger.exception(f"Live process failed for {identifier}: {e}")
            final_score = None
            classification = "Error"
            status = "collection_failed"
            is_mocked = False
            
        result_item = {
            "identifier": identifier,
            "platform": platform.capitalize(),
            "score": round(final_score, 1) if final_score is not None else 0,
            "classification": classification,
            "status": status,
            "is_mocked": is_mocked
        }
        results.append(result_item)
        
        # Broadcast progress
        await manager.broadcast({
            "type": "AUDIT_PROGRESS",
            "audit_id": audit_id,
            "target_influencer": target_influencer,
            "current": idx + 1,
            "total": actual_sample_size,
            "percentage": int(((idx + 1) / actual_sample_size) * 100),
            "latest_profile": result_item
        })
        
    successful_scans = [r for r in results if r["status"] == "Success"]
    successful_count = len(successful_scans)
    
    fake_percentage = (total_fake / successful_count * 100) if successful_count > 0 else 0
    collection_success_rate = (successful_count / actual_sample_size * 100) if actual_sample_size > 0 else 0
    top_red_flags = [{"flag": flag, "count": count} for flag, count in red_flag_counter.most_common(5)]
    
    budget_warning = None
    if platform == "instagram" and not allow_mock and actual_sample_size >= 100:
        budget_warning = "Note: Large sample sizes consume Apify compute credits. Please monitor your usage."

    audit_record = {
        "audit_id": audit_id,
        "target_influencer": target_influencer,
        "timestamp": datetime.now(timezone.utc),
        "sample_size": actual_sample_size,
        "successful_scans": successful_count,
        "collection_success_rate": round(collection_success_rate, 1),
        "fake_percentage": round(fake_percentage, 1),
        "risk_breakdown": risk_counts,
        "top_red_flags": top_red_flags,
        "budget_warning": budget_warning,
        "followers_data": results
    }
    
    influencer_audits_collection.insert_one(audit_record)
    audit_record["_id"] = str(audit_record["_id"])
    audit_record["timestamp"] = audit_record["timestamp"].isoformat()
    
    # Broadcast completion
    await manager.broadcast({
        "type": "AUDIT_COMPLETE",
        "audit_id": audit_id,
        "target_influencer": target_influencer,
        "final_result": audit_record
    })
