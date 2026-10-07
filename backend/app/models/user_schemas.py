from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

class UserBase(BaseModel):
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    username: str
    email: str
    avatar: Optional[str] = None
    phone: Optional[str] = None
    jobTitle: Optional[str] = None
    company: Optional[str] = None
    bio: Optional[str] = None
    role: str = "User"
    plan: str = "Free"
    accountStatus: str = "Active"

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: str
    createdAt: datetime
    updatedAt: datetime
    lastLogin: Optional[datetime] = None
    
    preferences: Optional[Dict[str, Any]] = None
    notifications: Optional[Dict[str, Any]] = None

class UserProfileUpdate(BaseModel):
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    jobTitle: Optional[str] = None
    company: Optional[str] = None
    bio: Optional[str] = None
    avatar: Optional[str] = None

class UserPreferencesUpdate(BaseModel):
    appearance: Optional[str] = None
    dashboard_view: Optional[str] = None
    analytics_period: Optional[str] = None
    default_platform: Optional[str] = None
    history_retention: Optional[str] = None
    rows_per_page: Optional[int] = None

class UserNotificationsUpdate(BaseModel):
    scan_completed: Optional[bool] = None
    high_risk: Optional[bool] = None
    bulk_completed: Optional[bool] = None
    ai_insights: Optional[bool] = None
    security_alerts: Optional[bool] = None
    product_updates: Optional[bool] = None

class ActivityLogResponse(BaseModel):
    id: str
    action: str
    timestamp: datetime
    details: Optional[str] = None

class ApiKeyResponse(BaseModel):
    id: str
    name: str
    key_hint: str
    created_at: datetime
    last_used: Optional[datetime] = None
    status: str
    
class ApiKeyCreate(BaseModel):
    name: str
