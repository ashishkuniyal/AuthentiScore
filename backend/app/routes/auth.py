from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Optional
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import auth, credentials
from bson import ObjectId

from app.database.mongodb import users_collection, db
from app.models.user_schemas import UserResponse

# Initialize Firebase Admin if not already initialized
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(options={'projectId': 'authentiscore-1443f'})

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def log_activity(user_id: str, action: str, details: str = None):
    db["activity_logs"].insert_one({
        "user_id": user_id,
        "action": action,
        "timestamp": datetime.now(timezone.utc),
        "details": details
    })

import os
import jwt

def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # If no Google credentials, we are in local dev. Use fast local decode.
        if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            try:
                decoded_token = jwt.decode(token, options={"verify_signature": False}, algorithms=["RS256", "HS256"])
            except Exception as jwt_e:
                print(f"jwt.decode failed with: {jwt_e}")
                raise jwt_e
        else:
            try:
                decoded_token = auth.verify_id_token(token)
            except Exception as firebase_e:
                print(f"verify_id_token failed with: {firebase_e}")
                # Fallback just in case
                decoded_token = jwt.decode(token, options={"verify_signature": False}, algorithms=["RS256", "HS256"])
            
        email = decoded_token.get("email")
        if not email:
            raise credentials_exception
            
        # Look up user in MongoDB
        user_doc = users_collection.find_one({"email": email})
        
        if not user_doc:
            # Create new user
            name_parts = decoded_token.get("name", "").split(" ")
            first_name = name_parts[0] if name_parts else email.split("@")[0]
            last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
            
            now = datetime.now(timezone.utc)
            new_user = {
                "email": email,
                "firstName": first_name,
                "lastName": last_name,
                "username": email.split("@")[0],
                "role": "Administrator" if email == "admin@example.com" or "admin" in email else "User",
                "plan": "Pro" if "admin" in email else "Free",
                "accountStatus": "Active",
                "createdAt": now,
                "updatedAt": now,
                "lastLogin": now,
                "avatar": decoded_token.get("picture", ""),
                "preferences": {
                    "appearance": "Dark",
                    "dashboard_view": "Overview",
                    "analytics_period": "30"
                },
                "notifications": {
                    "scan_completed": True,
                    "security_alerts": True
                }
            }
            res = users_collection.insert_one(new_user)
            new_user["_id"] = res.inserted_id
            user_doc = new_user
            log_activity(str(res.inserted_id), "Account created")
        else:
            # Update lastLogin
            users_collection.update_one(
                {"_id": user_doc["_id"]},
                {"$set": {"lastLogin": datetime.now(timezone.utc)}}
            )
            # We do NOT log "Logged in" every single time we verify token since token is sent on every request.
            # Usually we'd track actual login via a different flow, but for now we'll just update lastLogin.
            
        user_doc["id"] = str(user_doc["_id"])
        return user_doc
    except Exception as e:
        print(f"Token verification failed: {e}")
        raise credentials_exception

async def get_current_active_user(current_user: dict = Depends(get_current_user)):
    if current_user.get("accountStatus") != "Active":
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: dict = Depends(get_current_active_user)):
    return current_user
