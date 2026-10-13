from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any


# ==================================================
# Profile Data
# ==================================================

class ProfileData(BaseModel):
    username: Optional[str] = Field(None, max_length=64)
    bio: Optional[str] = Field(None, max_length=2000)
    followers: Optional[float] = Field(ge=0, default=None)
    following: Optional[float] = Field(ge=0, default=None)
    posts: Optional[float] = Field(ge=0, default=None)
    bio_length: Optional[float] = Field(ge=0, default=None)
    has_profile_picture: Optional[int] = Field(ge=0, le=1, default=None)
    is_private: Optional[int] = Field(ge=0, le=1, default=None)
    username_digit_ratio: Optional[float] = Field(ge=0, le=1, default=None)
    follower_following_ratio: Optional[float] = Field(ge=0, default=None)
    profile_completeness: Optional[float] = Field(ge=0, le=1, default=None)


# ==================================================
# Scan Request
# ==================================================

class ScanRequest(BaseModel):
    profile: ProfileData
    bio: Optional[str] = ""
    username: Optional[str] = None


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
    final_score: Optional[float] = Field(None, description="Unified risk score between 0 and 100, or None if Insufficient Data")
    classification: str = Field(..., description="Low Risk, Medium Risk, High Risk, Very High Risk, or Insufficient Data")
    data_completeness: Optional[float] = Field(None, description="Ratio of present features")
    missing_features: Optional[List[str]] = Field(None, description="List of missing feature names")
    field_sources: Optional[Dict[str, str]] = Field(None, description="Sources of individual fields")
    platform_coverage: Optional[str] = Field(None, description="Platform data availability coverage")
    score_breakdown: Optional[Dict[str, Any]] = Field(default=None, description="Canonical breakdown: components, weights, final")
    risk_components: Optional[RiskComponents] = None
    top_ml_factors: Optional[List[dict]] = Field(None, description="Top features contributing to the score")
    nlp_signals: Optional[dict] = Field(None, description="Hybrid keyword + semantic NLP bio signals")
    rule_signals: Optional[list] = Field(None, description="Heuristic profile rules")
    network_signals: Optional[dict] = Field(default=None, description="Signals from Network Graph Analysis")
    image_signals: Optional[dict] = Field(default=None, description="Signals from Image Forensics")
    confidence: Optional[Dict[str, Any]] = Field(default=None, description="Confidence level, value, and explanations")
    abstain: Optional[bool] = Field(default=False, description="Whether scanner abstained from conclusive verdict")
    model_applicable: Optional[bool] = Field(default=True, description="Whether ML model is applicable to this domain")
    account_type: Optional[str] = Field(default="uncertain", description="likely_fake | likely_real | automated_declared | uncertain")
    reasons: Optional[List[Dict[str, Any]]] = Field(default=None, description="Unified top explanatory factors")



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
    username: str = Field(..., min_length=1, max_length=64)
    followers: float = Field(ge=0)
    following: float = Field(ge=0)
    posts: float = Field(ge=0)
    bio: str = Field("", max_length=2000)
    has_profile_picture: int = Field(ge=0, le=1)
    is_private: int = Field(ge=0, le=1)

class ProfileScanResponse(BaseModel):

    profile: Dict[str, Any]

    features: Dict[str, Any]

    final_score: Optional[float] = None

    classification: str

    data_completeness: Optional[float] = None
    missing_features: Optional[List[str]] = None
    field_sources: Optional[Dict[str, str]] = None
    platform_coverage: Optional[str] = None

    score_breakdown: Optional[Dict[str, Any]] = None

    risk_components: Optional[RiskComponents] = None

    top_ml_factors: Optional[List[Dict[str, Any]]] = None

    nlp_signals: Optional[Dict[str, Any]] = None
    rule_signals: Optional[List[Dict[str, Any]]] = None
    network_signals: Optional[Dict[str, Any]] = None
    image_signals: Optional[Dict[str, Any]] = None
    confidence: Optional[Dict[str, Any]] = None
    abstain: Optional[bool] = False
    model_applicable: Optional[bool] = True
    account_type: Optional[str] = "uncertain"
    reasons: Optional[List[Dict[str, Any]]] = None

# ==================================================
# Complete Profile Scan Response
# ==================================================

class CompleteProfileScanResponse(BaseModel):

    scan_id: str

    platform: str

    username: str

    profile_url: str

    features: Dict[str, Any]

    final_score: Optional[float] = None

    classification: str

    data_completeness: Optional[float] = None
    missing_features: Optional[List[str]] = None
    field_sources: Optional[Dict[str, str]] = None
    platform_coverage: Optional[str] = None

    score_breakdown: Optional[Dict[str, Any]] = None

    risk_components: Optional[RiskComponents] = None

    top_ml_factors: Optional[List[Dict[str, Any]]] = None

    nlp_signals: Optional[Dict[str, Any]] = None
    rule_signals: Optional[List[Dict[str, Any]]] = None
    network_signals: Optional[Dict[str, Any]] = None
    image_signals: Optional[Dict[str, Any]] = None
    confidence: Optional[Dict[str, Any]] = None
    abstain: Optional[bool] = False
    model_applicable: Optional[bool] = True
    account_type: Optional[str] = "uncertain"
    reasons: Optional[List[Dict[str, Any]]] = None


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
    consent: Optional[bool] = True


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
    final_score: Optional[float] = None
    classification: str
    data_completeness: Optional[float] = None
    missing_features: Optional[List[str]] = None
    field_sources: Optional[Dict[str, str]] = None
    platform_coverage: Optional[str] = None
    score_breakdown: Optional[Dict[str, Any]] = None
    risk_components: Optional[RiskComponents] = None
    top_ml_factors: Optional[List[Dict[str, Any]]] = None
    nlp_signals: Optional[Dict[str, Any]] = None
    rule_signals: Optional[List[Dict[str, Any]]] = None
    network_signals: Optional[Dict[str, Any]] = None
    image_signals: Optional[Dict[str, Any]] = None
    confidence: Optional[Dict[str, Any]] = None
    abstain: Optional[bool] = False
    model_applicable: Optional[bool] = True
    account_type: Optional[str] = "uncertain"
    reasons: Optional[List[Dict[str, Any]]] = None
    from_cache: Optional[bool] = False

    # -- Collection audit --
    collection: CollectionMetadata


# ==================================================
# Scan Feedback Request
# ==================================================

class ScanFeedbackRequest(BaseModel):
    user_verdict: str  # "real" | "fake" | "bot"
    comment: Optional[str] = None
    rating: Optional[int] = None


class ScanJobRequest(BaseModel):
    input: str
    platform: Optional[str] = "instagram"
    consent: bool = False
    force_refresh: Optional[bool] = False


class ManualCompletionRequest(BaseModel):
    followers: Optional[float] = None
    following: Optional[float] = None
    posts: Optional[float] = None
    bio: Optional[str] = None
    has_profile_picture: Optional[int] = None
    is_private: Optional[int] = None


