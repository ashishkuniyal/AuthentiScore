from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any


# ==================================================
# Profile Data
# ==================================================

class ProfileData(BaseModel):

    followers: float = Field(ge=0)

    following: float = Field(ge=0)

    posts: float = Field(ge=0)

    bio_length: float = Field(ge=0)

    has_profile_picture: int = Field(
        ge=0,
        le=1
    )

    is_private: int = Field(
        ge=0,
        le=1
    )

    username_digit_ratio: float = Field(
        ge=0,
        le=1
    )

    follower_following_ratio: float = Field(
        ge=0
    )

    profile_completeness: float = Field(
        ge=0,
        le=1
    )


# ==================================================
# Scan Request
# ==================================================

class ScanRequest(BaseModel):

    profile: ProfileData

    bio: Optional[str] = ""


# ==================================================
# Risk Components
# ==================================================

class RiskComponents(BaseModel):

    ml_risk: float

    nlp_risk: float

    rule_risk: float


# ==================================================
# Scan Response
# ==================================================

class ScanResponse(BaseModel):
    final_score: float = Field(..., description="Unified risk score between 0 and 1")
    classification: str = Field(..., description="High, Medium, or Low Risk")
    score_breakdown: Optional[Dict[str, Any]] = Field(default=None, description="Canonical breakdown: components, weights, final")
    risk_components: RiskComponents
    top_ml_factors: List[dict] = Field(..., description="Top features contributing to the score")
    nlp_signals: dict = Field(..., description="Hybrid keyword + semantic NLP bio signals")
    rule_signals: list = Field(..., description="Heuristic profile rules")
    network_signals: Optional[dict] = Field(default=None, description="Signals from Network Graph Analysis")
    image_signals: Optional[dict] = Field(default=None, description="Signals from Image Forensics")


# ==================================================
# Profile URL Request
# ==================================================

class ProfileURLRequest(BaseModel):

    profile_url: HttpUrl

    bio: Optional[str] = ""


# ==================================================
# Collected Profile
# ==================================================

class CollectedProfile(BaseModel):

    platform: str

    profile_url: str

    username: Optional[str] = None

    followers: Optional[float] = None

    following: Optional[float] = None

    posts: Optional[float] = None

    bio: Optional[str] = None

    bio_length: Optional[float] = None

    has_profile_picture: Optional[int] = None

    is_private: Optional[int] = None

    username_digit_ratio: Optional[float] = None

    follower_following_ratio: Optional[float] = None

    profile_completeness: Optional[float] = None

    collection_status: str = "success"

    collection_source: str = "unknown"

    error: Optional[str] = None


# ==================================================
# Manual Profile Request
# ==================================================

class ManualProfileRequest(BaseModel):

    platform: str

    profile_url: HttpUrl

    username: str

    followers: float = Field(
        ge=0
    )

    following: float = Field(
        ge=0
    )

    posts: float = Field(
        ge=0
    )

    bio: str = ""

    has_profile_picture: int = Field(
        ge=0,
        le=1
    )

    is_private: int = Field(
        ge=0,
        le=1
    )

class ProfileScanResponse(BaseModel):

    profile: Dict[str, Any]

    features: Dict[str, Any]

    final_score: float

    classification: str

    score_breakdown: Optional[Dict[str, Any]] = None

    risk_components: RiskComponents

    top_ml_factors: List[Dict[str, Any]]

    nlp_signals: Dict[str, Any]
    rule_signals: List[Dict[str, Any]]
    network_signals: Optional[Dict[str, Any]] = None
    image_signals: Optional[Dict[str, Any]] = None

# ==================================================
# Complete Profile Scan Response
# ==================================================

class CompleteProfileScanResponse(BaseModel):

    scan_id: str

    platform: str

    username: str

    profile_url: str

    features: Dict[str, Any]

    final_score: float

    classification: str

    score_breakdown: Optional[Dict[str, Any]] = None

    risk_components: RiskComponents

    top_ml_factors: List[Dict[str, Any]]

    nlp_signals: Dict[str, Any]
    rule_signals: List[Dict[str, Any]]
    network_signals: Optional[Dict[str, Any]] = None
    image_signals: Optional[Dict[str, Any]] = None


# ==================================================
# Auto-Scan Request
# ==================================================

class AutoScanRequest(BaseModel):
    """
    Input for the automated URL-driven scan endpoint.

    The user only provides the public profile URL.
    All other data is collected automatically by the
    collector layer.
    """

    profile_url: HttpUrl


# ==================================================
# Collection Metadata
# ==================================================

class CollectionMetadata(BaseModel):
    """
    Audit record for every automated scan.

    Records exactly where the data came from, when it
    was collected, and which fields were successfully
    obtained — for research reproducibility.
    """

    source: str
    """
    "official_api"         — Twitter v2 API with bearer token
    "permitted_public_page"— Unauthenticated public HTML / JSON
    "user_provided"        — Manual fallback entry
    "none"                 — Collection failed before a source was used
    """

    status: str
    """
    "success" | "partial" | "failed"
    """

    timestamp: str
    """ISO-8601 UTC timestamp of the collection attempt."""

    fields_collected: List[str]
    """
    Names of fields that were successfully obtained from the
    automated source.  Empty list when source is "user_provided"
    or "none".
    """


# ==================================================
# Auto-Scan Response
# ==================================================

class AutoScanResponse(BaseModel):
    """
    Complete response from POST /scan/auto.

    Extends the CompleteProfileScanResponse with
    collection-specific metadata and the raw collected
    profile fields.
    """

    scan_id: str

    platform: str

    username: str

    profile_url: str

    # -- Collected profile fields --
    display_name: Optional[str] = None
    collected_bio: Optional[str] = None
    profile: Dict[str, Any]

    # -- ML features used by the model --
    features: Dict[str, Any]

    # -- Risk results --
    final_score: float
    classification: str
    score_breakdown: Optional[Dict[str, Any]] = None
    risk_components: RiskComponents
    top_ml_factors: List[Dict[str, Any]]
    nlp_signals: Dict[str, Any]
    rule_signals: List[Dict[str, Any]]
    network_signals: Optional[Dict[str, Any]] = None
    image_signals: Optional[Dict[str, Any]] = None

    # -- Collection audit --
    collection: CollectionMetadata
