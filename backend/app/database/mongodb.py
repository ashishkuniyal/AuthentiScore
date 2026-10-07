import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient


# ==================================================
# Load Environment Variables
# ==================================================

load_dotenv(override=True)


# ==================================================
# MongoDB Configuration
# ==================================================

MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb://localhost:27017"
)

DATABASE_NAME = os.getenv(
    "MONGODB_DATABASE",
    "authentiscore"
)


# ==================================================
# Data Retention Configuration
# ==================================================

try:
    SCAN_RETENTION_DAYS = int(
        os.getenv(
            "SCAN_RETENTION_DAYS",
            "30"
        )
    )

except ValueError:
    SCAN_RETENTION_DAYS = 30


# Prevent invalid retention values
if SCAN_RETENTION_DAYS < 1:
    SCAN_RETENTION_DAYS = 30


# ==================================================
# MongoDB Client
# ==================================================

client = MongoClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=5000
)


# ==================================================
# Database
# ==================================================

db = client[DATABASE_NAME]


# ==================================================
# Collections
# ==================================================

scans_collection = db["scans"]
bulk_jobs_collection = db["bulk_jobs"]
influencer_audits_collection = db["influencer_audits"]
users_collection = db["users"]


# ==================================================
# Connection Test
# ==================================================

def test_mongodb_connection():

    try:

        client.admin.command("ping")

        return True

    except Exception:

        return False


# ==================================================
# Data Retention / TTL Index
# ==================================================

def setup_scan_retention_policy():
    """
    Configure MongoDB TTL index for automatic
    deletion of expired scan records.

    Scan documents use the `timestamp` field as
    the retention reference.

    The retention period is controlled by:

        SCAN_RETENTION_DAYS

    in the .env file.
    """

    index_name = "scan_retention_ttl"

    expire_after_seconds = (
        SCAN_RETENTION_DAYS * 24 * 60 * 60
    )

    try:

        existing_indexes = (
            scans_collection.index_information()
        )

        # ------------------------------------------
        # Check whether our TTL index already exists
        # ------------------------------------------

        if index_name in existing_indexes:

            existing_index = (
                existing_indexes[index_name]
            )

            existing_expiration = (
                existing_index.get(
                    "expireAfterSeconds"
                )
            )

            # --------------------------------------
            # Existing configuration is correct
            # --------------------------------------

            if (
                existing_expiration
                == expire_after_seconds
            ):

                return {
                    "success": True,
                    "retention_days": SCAN_RETENTION_DAYS,
                    "expire_after_seconds": expire_after_seconds,
                    "index_name": index_name,
                    "message": (
                        "Scan retention policy is already configured."
                    )
                }

            # --------------------------------------
            # Retention period changed
            # --------------------------------------

            scans_collection.drop_index(
                index_name
            )

        # ------------------------------------------
        # Create TTL index
        # ------------------------------------------

        scans_collection.create_index(
            [("timestamp", 1)],
            expireAfterSeconds=expire_after_seconds,
            name=index_name
        )

        return {
            "success": True,
            "retention_days": SCAN_RETENTION_DAYS,
            "expire_after_seconds": expire_after_seconds,
            "index_name": index_name,
            "message": (
                "Scan retention policy configured successfully."
            )
        }

    except Exception as error:

        return {
            "success": False,
            "retention_days": SCAN_RETENTION_DAYS,
            "expire_after_seconds": expire_after_seconds,
            "index_name": index_name,
            "message": (
                "Unable to configure scan retention policy."
            ),
            "error": str(error)
        }


# ==================================================
# Save Scan Result
# ==================================================

def save_scan_result(
    scan_id: str,
    platform: str,
    username: str,
    profile_url: str,
    features: dict,
    result: dict,
    collection_source: str = "unknown",
    collection_status: str = "unknown",
    model_name: str = "RandomForest",
    model_version: str = "v1",
    collection_metadata: dict | None = None,
    user_id: str = None,
):
    """
    Save a completed AuthentiScore prediction.

    collection_source records where the profile information
    used for the prediction came from.

    Examples:
        - url_metadata
        - user_provided
        - official_api
        - unknown

    Scan records are automatically removed after the
    configured retention period using the MongoDB TTL index.
    """

    document = {

        # ------------------------------------------
        # Scan Metadata
        # ------------------------------------------

        "scan_id": scan_id,
        "user_id": user_id,

        "timestamp": datetime.now(
            timezone.utc
        ),

        # ------------------------------------------
        # Profile Metadata
        # ------------------------------------------

        "platform": platform,

        "username": username,

        "profile_url": profile_url,

        # ------------------------------------------
        # Collection Audit Trail
        # ------------------------------------------

        "collection_source": collection_source,

        "collection_status": collection_status,

        # ------------------------------------------
        # Model Metadata
        # ------------------------------------------

        "model_name": model_name,

        "model_version": model_version,

        # ------------------------------------------
        # Features
        # ------------------------------------------

        "features": features,

        # ------------------------------------------
        # Prediction
        # ------------------------------------------

        "final_score": result["final_score"],

        "classification": result["classification"],

        # ------------------------------------------
        # Risk Components
        # ------------------------------------------

        "risk_components": result[
            "risk_components"
        ],

        # ------------------------------------------
        # Explainability
        # ------------------------------------------

        "top_ml_factors": result[
            "top_ml_factors"
        ],

        "nlp_signals": result[
            "nlp_signals"
        ],

        "rule_signals": result[
            "rule_signals"
        ],

        # ------------------------------------------
        # Collection Audit Trail (automated scans)
        # ------------------------------------------

        "collection_metadata": collection_metadata,
    }

    inserted_result = scans_collection.insert_one(
        document
    )

    return {

        "scan_id": scan_id,

        "inserted_id": str(
            inserted_result.inserted_id
        )
    }
# ==================================================
# Initialize Retention Policy
# ==================================================

retention_result = setup_scan_retention_policy()

print(
    "AuthentiScore retention policy:",
    retention_result
)