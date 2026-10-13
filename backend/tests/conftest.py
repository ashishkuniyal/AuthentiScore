"""
AuthentiScore — Pytest Conftest
================================

Hermetic test environment for all unit and integration tests (M3).
- Uses mongomock for in-memory MongoDB without network/daemon
- Builds and monkeypatches a tiny trained ensemble pipeline so tests
  do not require trained_models/*.pkl artifacts
- Mocks external network calls by default
"""

import sys
import os

# Enforce offline & hermetic test environment immediately (M3)
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["REQUIRE_EMAIL_VERIFICATION"] = "false"

from pathlib import Path
import pytest
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from xgboost import XGBClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
import mongomock

# Ensure backend directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

FEATURES_LIST = [
    "followers", "following", "posts", "bio_length", "has_profile_picture",
    "is_private", "username_digit_ratio", "follower_following_ratio", "profile_completeness"
]


@pytest.fixture(scope="session")
def tiny_trained_pipeline():
    """Create a lightweight calibrated ensemble on synthetic data for tests."""
    np.random.seed(42)
    auth_X = np.column_stack([
        np.random.uniform(500, 2000, 50),   # followers
        np.random.uniform(50, 300, 50),     # following
        np.random.uniform(10, 100, 50),     # posts
        np.random.uniform(10, 150, 50),     # bio_length
        np.ones(50),                        # has_pic
        np.zeros(50),                       # is_private
        np.zeros(50),                       # digit_ratio
        np.random.uniform(2, 10, 50),       # ratio
        np.ones(50),                        # completeness
    ])
    auth_y = np.zeros(50, dtype=int)

    fake_X = np.column_stack([
        np.random.uniform(0, 10, 50),       # followers
        np.random.uniform(2000, 7000, 50),  # following
        np.zeros(50),                       # posts
        np.random.uniform(0, 100, 50),      # bio_length
        np.zeros(50),                       # has_pic
        np.zeros(50),                       # is_private
        np.random.uniform(0.3, 0.9, 50),    # digit_ratio
        np.random.uniform(0.0001, 0.01, 50),# ratio
        np.random.uniform(0.3, 0.5, 50),    # completeness
    ])
    fake_y = np.ones(50, dtype=int)

    X = np.vstack([auth_X, fake_X])
    y = np.concatenate([auth_y, fake_y])
    
    lr = LogisticRegression(max_iter=100, random_state=42)
    rf = RandomForestClassifier(n_estimators=5, max_depth=2, random_state=42)
    xgb = XGBClassifier(n_estimators=5, max_depth=2, eval_metric="logloss", random_state=42)
    
    ensemble = VotingClassifier(
        estimators=[("lr", lr), ("rf", rf), ("xgb", xgb)],
        voting="soft"
    )
    
    pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("calibrated_ensemble", CalibratedClassifierCV(ensemble, cv=2, method="sigmoid"))
    ])
    pipe.fit(X, y)
    return pipe


@pytest.fixture(autouse=True)
def hermetic_env(monkeypatch, tiny_trained_pipeline):
    """
    Autouse fixture that replaces MongoDB and ML model with hermetic in-memory versions.
    """
    # 1. In-memory Mongo via mongomock
    mock_client = mongomock.MongoClient()
    mock_db = mock_client["authentiscore"]
    mock_scans = mock_db["scans"]
    mock_users = mock_db["users"]
    mock_bulk = mock_db["bulk_jobs"]
    mock_audits = mock_db["influencer_audits"]
    mock_activity = mock_db["activity_logs"]
    mock_keys = mock_db["api_keys"]

    import app.database.mongodb as mongo_mod
    monkeypatch.setattr(mongo_mod, "client", mock_client)
    monkeypatch.setattr(mongo_mod, "db", mock_db)
    monkeypatch.setattr(mongo_mod, "scans_collection", mock_scans)
    monkeypatch.setattr(mongo_mod, "users_collection", mock_users)
    monkeypatch.setattr(mongo_mod, "bulk_jobs_collection", mock_bulk)
    monkeypatch.setattr(mongo_mod, "influencer_audits_collection", mock_audits)

    # Also patch routes and services that might have directly imported collections
    for mod_name in [
        "app.routes.users", "app.routes.auth", "app.routes.scan", "app.routes.bulk",
        "app.routes.audit", "app.routes.history", "app.routes.analytics",
        "app.services.audience_auditor", "app.services.bulk_processor"
    ]:
        if mod_name in sys.modules:
            mod = sys.modules[mod_name]
            if hasattr(mod, "users_collection"):
                monkeypatch.setattr(mod, "users_collection", mock_users)
            if hasattr(mod, "scans_collection"):
                monkeypatch.setattr(mod, "scans_collection", mock_scans)
            if hasattr(mod, "bulk_jobs_collection"):
                monkeypatch.setattr(mod, "bulk_jobs_collection", mock_bulk)
            if hasattr(mod, "influencer_audits_collection"):
                monkeypatch.setattr(mod, "influencer_audits_collection", mock_audits)
            if hasattr(mod, "db"):
                monkeypatch.setattr(mod, "db", mock_db)

    # 2. In-memory model store
    import app.services.model_store as ms
    monkeypatch.setattr(ms, "_model", tiny_trained_pipeline)
    monkeypatch.setattr(ms, "_features", FEATURES_LIST)
    monkeypatch.setattr(ms, "_loaded", True)
    monkeypatch.setattr(ms, "_load_error", None)
    monkeypatch.setattr(ms, "get_model", lambda: tiny_trained_pipeline)
    monkeypatch.setattr(ms, "get_features", lambda: FEATURES_LIST)
    monkeypatch.setattr(ms, "is_loaded", lambda: True)
    monkeypatch.setattr(ms, "get_load_error", lambda: None)

    # 3. Hermetic NLP pipelines (M3 — zero network / download)
    def mock_semantic_classifier(text):
        text_lower = str(text).lower()
        spam_signals = [
            "guaranteed", "double your money", "whatsapp", "5000",
            "free iphone", "act now", "limited time", "buy real followers",
            "earn money", "giveaway", "selected", "crypto", "scam"
        ]
        if any(s in text_lower for s in spam_signals):
            return [{"label": "LABEL_1", "score": 0.88}]
        return [{"label": "LABEL_0", "score": 0.95}]

    import app.services.semantic_nlp_engine as sem_nlp
    monkeypatch.setattr(sem_nlp, "_classifier", mock_semantic_classifier)
    monkeypatch.setattr(sem_nlp, "_model_available", True)
    monkeypatch.setattr(sem_nlp, "get_classifier", lambda: sem_nlp._classifier or mock_semantic_classifier)

    import app.services.nlp_engine as nlp_mod
    monkeypatch.setattr(nlp_mod, "_nlp_pipeline", None)
    monkeypatch.setattr(nlp_mod, "_nlp_load_failed", True)
    monkeypatch.setattr(nlp_mod, "get_nlp_pipeline", lambda: None)

    # 4. Hermetic collector mocks (M3 — zero network calls)
    import app.services.collectors.instaloader_collector as insta_mod
    def mock_instaloader_run(self, url):
        return {
            "collection_status": "failed",
            "collection_source": "none",
            "platform": "instagram",
            "identifier": "mock_user",
            "error": "Instaloader offline mock",
            "fields_collected": []
        }
    monkeypatch.setattr(insta_mod.InstaLoaderCollector, "run", mock_instaloader_run)
