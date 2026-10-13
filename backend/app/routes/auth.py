"""
AuthentiScore — Authentication Router & Dependencies
=====================================================

Implements:
  - S1: Strict Firebase ID token verification (no signature bypass)
  - S2: Admin privilege check via ADMIN_EMAILS allowlist
  - C30: Upsert / unique handling and lastLogin 10m update throttling
  - C36: Clean imports
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import firebase_admin
from firebase_admin import auth, credentials
import google.auth
from google.auth.credentials import AnonymousCredentials
from google.auth.exceptions import DefaultCredentialsError
from pymongo.errors import DuplicateKeyError

from app.database.mongodb import db, users_collection
from app.models.user_schemas import UserResponse

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Firebase Admin Initialization (S1)
# ─────────────────────────────────────────────────────────────

try:
    firebase_admin.get_app()
except ValueError:
    project_id = os.getenv("FIREBASE_PROJECT_ID", "authentiscore-1443f")
    cred = None
    service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
    if service_account_path and os.path.exists(service_account_path):
        cred = credentials.Certificate(service_account_path)
    else:
        try:
            g_cred, _ = google.auth.default()
            cred = credentials._ExternalCredentials(g_cred)
        except (DefaultCredentialsError, Exception):
            cred = credentials._ExternalCredentials(AnonymousCredentials())

    firebase_admin.initialize_app(cred, options={"projectId": project_id})

router = APIRouter()
security_bearer = HTTPBearer(auto_error=False)


def log_activity(user_id: str, action: str, details: Optional[str] = None) -> None:
    try:
        db["activity_logs"].insert_one({
            "user_id": user_id,
            "action": action,
            "timestamp": datetime.now(timezone.utc),
            "details": details,
        })
    except Exception as exc:
        logger.warning("Could not log activity for user=%s: %s", user_id, exc)


def _determine_role_and_plan(email: str, decoded_token: dict) -> tuple[str, str]:
    """
    S2: Default role=User, plan=Free.
    Administrator granted only to exact-match case-insensitive allowlist in ADMIN_EMAILS,
    and only when email_verified is true.
    """
    admin_emails_raw = os.getenv("ADMIN_EMAILS", "")
    admin_emails = {e.strip().lower() for e in admin_emails_raw.split(",") if e.strip()}
    email_verified = decoded_token.get("email_verified", False)

    if email.lower() in admin_emails and email_verified:
        return "Administrator", "Pro"

    return "User", "Free"


def verify_token_string(token: str) -> dict:
    """
    Verify a Firebase ID token string and return or create the MongoDB user document.
    Shared by HTTP dependency and WebSocket handshake (S1, S5).
    """
    try:
        decoded_token = auth.verify_id_token(token)
    except Exception as exc:
        logger.warning("Firebase token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = decoded_token.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing email claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # S1 / DECISION D2: Require email_verified for password sign-ups
    provider = decoded_token.get("firebase", {}).get("sign_in_provider", "")
    email_verified = decoded_token.get("email_verified", False)
    if provider == "password" and not email_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email address must be verified before signing in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # MongoDB lookup / creation
    try:
        user_doc = users_collection.find_one({"email": email})
    except Exception as exc:
        logger.error("MongoDB error during user lookup: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable",
        )

    now = datetime.now(timezone.utc)

    if not user_doc:
        name_parts = decoded_token.get("name", "").split(" ")
        first_name = name_parts[0] if name_parts else email.split("@")[0]
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
        role, plan = _determine_role_and_plan(email, decoded_token)

        new_user = {
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "username": email.split("@")[0],
            "role": role,
            "plan": plan,
            "accountStatus": "Active",
            "createdAt": now,
            "updatedAt": now,
            "lastLogin": now,
            "avatar": decoded_token.get("picture", ""),
            "preferences": {
                "appearance": "Dark",
                "dashboard_view": "Overview",
                "analytics_period": "30",
            },
            "notifications": {
                "scan_completed": True,
                "security_alerts": True,
            },
        }

        try:
            res = users_collection.insert_one(new_user)
            new_user["_id"] = res.inserted_id
            user_doc = new_user
            log_activity(str(res.inserted_id), "Account created")
        except DuplicateKeyError:
            # Race condition on concurrent first requests
            user_doc = users_collection.find_one({"email": email})
        except Exception as exc:
            logger.error("MongoDB error during user creation: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service unavailable",
            )
    else:
        # C30: Update lastLogin only if older than 10 minutes
        last_login = user_doc.get("lastLogin")
        should_update = False
        if not last_login:
            should_update = True
        else:
            if last_login.tzinfo is None:
                last_login = last_login.replace(tzinfo=timezone.utc)
            if (now - last_login).total_seconds() > 600:
                should_update = True

        if should_update:
            try:
                users_collection.update_one(
                    {"_id": user_doc["_id"]},
                    {"$set": {"lastLogin": now}},
                )
            except Exception as exc:
                logger.warning("Could not update lastLogin: %s", exc)

    user_doc["id"] = str(user_doc["_id"])
    return user_doc


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> dict:
    if not creds or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_token_string(creds.credentials)


async def get_current_active_user(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user.get("accountStatus") != "Active":
        raise HTTPException(status_code=400, detail="Inactive user account")
    return current_user


@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: dict = Depends(get_current_active_user)):
    return current_user
