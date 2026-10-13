#!/usr/bin/env python3
"""
AuthentiScore — Model Training & Calibration v4 (A4)
===================================================

Trains the v4 calibrated ensemble (LR + RF + XGBoost) using:
  1. No SMOTE-before-calibration: handles class imbalance using class_weight='balanced'
     and XGBoost scale_pos_weight.
  2. Sigmoid calibration on held-out folds of the un-resampled distribution.
  3. PR-curve decision threshold tuning for target F1 / precision / recall trade-offs.
  4. Generates model card trained_models/MODEL_CARD.md and metrics_v4.json.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
import sklearn
import xgboost
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

# Path setup
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.features import (
    CORE_FEATURES,
    FEATURE_SCHEMA_VERSION,
    calculate_profile_completeness,
)

ROOT_DIR = BACKEND_DIR.parent
DATA_DIR = ROOT_DIR / "data" / "raw"
MODELS_DIR = BACKEND_DIR / "trained_models"


def compute_file_hash(path: Path) -> str:
    """Compute sha256 checksum of dataset file."""
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()[:16]


def load_dataset() -> Tuple[pd.DataFrame, np.ndarray, Dict[str, str]]:
    """Load and map training data from benchmark datasets."""
    p_train = DATA_DIR / "instagram_fake_spammer" / "train.csv"
    p_test = DATA_DIR / "instagram_fake_spammer" / "test.csv"

    hashes = {
        "train_csv_sha256": compute_file_hash(p_train),
        "test_csv_sha256": compute_file_hash(p_test),
    }

    df_train = pd.read_csv(p_train)
    df_test = pd.read_csv(p_test)
    df = pd.concat([df_train, df_test], ignore_index=True)

    df_mapped = pd.DataFrame()
    df_mapped["followers"] = df["#followers"].astype(float)
    df_mapped["following"] = df["#follows"].astype(float)
    df_mapped["posts"] = df["#posts"].astype(float)
    df_mapped["bio_length"] = df["description length"].astype(float)
    df_mapped["has_profile_picture"] = df["profile pic"].astype(int)
    df_mapped["is_private"] = df["private"].astype(int)
    df_mapped["username_digit_ratio"] = df["nums/length username"].astype(float)

    df_mapped["follower_following_ratio"] = df.apply(
        lambda row: row["#followers"] / row["#follows"] if row["#follows"] > 0 else float(row["#followers"]),
        axis=1,
    )

    df_mapped["profile_completeness"] = df.apply(
        lambda row: calculate_profile_completeness({
            "username": "user",
            "bio": "bio_sample" if row["description length"] > 0 else "",
            "followers": row["#followers"],
            "following": row["#follows"],
            "posts": row["#posts"],
            "has_profile_picture": row["profile pic"],
        }),
        axis=1,
    )

    y = df["fake"].values.astype(int)
    return df_mapped[CORE_FEATURES], y, hashes


def train_v4():
    print("=" * 70)
    print("AuthentiScore — Training & Calibrating Model Pipeline v4 (A4)")
    print("=" * 70)

    X, y, hashes = load_dataset()
    print(f"Total dataset rows: {len(X)} (Fake: {np.sum(y == 1)}, Real: {np.sum(y == 0)})")

    # Split train and validation (80/20 stratified)
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=42
    )

    # Class weighting ratio
    neg_count = np.sum(y_train == 0)
    pos_count = np.sum(y_train == 1)
    scale_pos = neg_count / max(pos_count, 1)

    print(f"Class weighting: neg={neg_count}, pos={pos_count}, scale_pos_weight={scale_pos:.2f}")

    # Base estimators with built-in imbalance weighting
    lr = LogisticRegression(
        max_iter=2000,
        class_weight="balanced",
        random_state=42,
    )
    rf = RandomForestClassifier(
        n_estimators=150,
        max_depth=5,
        min_samples_split=4,
        class_weight="balanced",
        random_state=42,
    )
    xgb = XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.05,
        scale_pos_weight=scale_pos,
        eval_metric="logloss",
        random_state=42,
    )

    ensemble = VotingClassifier(
        estimators=[("lr", lr), ("rf", rf), ("xgb", xgb)],
        voting="soft",
    )

    # Calibration pipeline on real un-resampled folds (cv=5)
    pipeline_v4 = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("calibrated_ensemble", CalibratedClassifierCV(ensemble, cv=5, method="sigmoid")),
    ])

    print("Fitting Calibrated Classifier pipeline v4...")
    pipeline_v4.fit(X_train, y_train)

    # Validation performance & threshold tuning
    val_probs = pipeline_v4.predict_proba(X_val)[:, 1]

    precisions, recalls, thresholds = precision_recall_curve(y_val, val_probs)
    f1_scores = 2 * (precisions * recalls) / (precisions + recalls + 1e-9)
    best_idx = np.argmax(f1_scores)
    optimal_threshold = float(thresholds[best_idx]) if best_idx < len(thresholds) else 0.50

    # Precision at 90% recall
    idx_90_rec = np.where(recalls >= 0.90)[0]
    prec_at_90_recall = float(np.max(precisions[idx_90_rec])) if len(idx_90_rec) > 0 else 0.0

    # Recall at 90% precision
    idx_90_prec = np.where(precisions >= 0.90)[0]
    rec_at_90_prec = float(np.max(recalls[idx_90_prec])) if len(idx_90_prec) > 0 else 0.0

    # Validation metrics at optimal threshold and default 0.50
    val_preds_opt = (val_probs >= optimal_threshold).astype(int)
    val_f1 = float(f1_score(y_val, val_preds_opt))
    val_prec = float(precision_score(y_val, val_preds_opt, zero_division=0))
    val_rec = float(recall_score(y_val, val_preds_opt, zero_division=0))
    val_auc = float(roc_auc_score(y_val, val_probs))
    val_pr_auc = float(average_precision_score(y_val, val_probs))
    val_brier = float(brier_score_loss(y_val, val_probs))

    print("\n--- Validation Performance (v4) ---")
    print(f"Optimal Decision Threshold:  {optimal_threshold:.4f}")
    print(f"F1 Score:                    {val_f1:.4f}")
    print(f"Precision:                   {val_prec:.4f}")
    print(f"Recall:                      {val_rec:.4f}")
    print(f"ROC-AUC:                     {val_auc:.4f}")
    print(f"PR-AUC:                      {val_pr_auc:.4f}")
    print(f"Brier Score:                 {val_brier:.4f}")
    print(f"Precision @ 90% Recall:      {prec_at_90_recall:.4f}")
    print(f"Recall @ 90% Precision:      {rec_at_90_prec:.4f}")

    # Save artifacts
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    v4_model_path = MODELS_DIR / "authentiscore_ensemble_v4.pkl"
    v4_features_path = MODELS_DIR / "authentiscore_features_v4.json"
    v4_metrics_path = MODELS_DIR / "metrics_v4.json"

    joblib.dump(pipeline_v4, v4_model_path)
    print(f"\nSaved v4 model artifact: {v4_model_path}")

    # Feature & schema metadata
    features_meta = {
        "schema_version": FEATURE_SCHEMA_VERSION,
        "features": CORE_FEATURES,
        "extended_features": CORE_FEATURES,
        "optimal_threshold": optimal_threshold,
    }
    with open(v4_features_path, "w", encoding="utf-8") as f:
        json.dump(features_meta, f, indent=2)

    metrics_meta = {
        "model_name": "CalibratedEnsemble_LR_RF_XGB",
        "model_version": "v4",
        "schema_version": FEATURE_SCHEMA_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "library_versions": {
            "sklearn": sklearn.__version__,
            "xgboost": xgboost.__version__,
            "joblib": joblib.__version__,
        },
        "dataset_hashes": hashes,
        "validation_metrics": {
            "optimal_threshold": round(optimal_threshold, 4),
            "f1": round(val_f1, 4),
            "precision": round(val_prec, 4),
            "recall": round(val_rec, 4),
            "roc_auc": round(val_auc, 4),
            "pr_auc": round(val_pr_auc, 4),
            "brier_score": round(val_brier, 4),
            "precision_at_90_recall": round(prec_at_90_recall, 4),
            "recall_at_90_precision": round(rec_at_90_prec, 4),
        },
    }
    with open(v4_metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics_meta, f, indent=2)

    # Generate Model Card
    model_card_path = MODELS_DIR / "MODEL_CARD.md"
    card_content = f"""# AuthentiScore Model Card — Ensemble v4

## Model Details
- **Model Architecture**: Soft-Voting Ensemble (LogisticRegression + RandomForest + XGBoost) wrapped in `CalibratedClassifierCV(method='sigmoid', cv=5)`.
- **Model Version**: `v4`
- **Feature Schema Version**: `{FEATURE_SCHEMA_VERSION}`
- **Training Date**: `{metrics_meta['trained_at']}`
- **Libraries**: `scikit-learn {sklearn.__version__}`, `xgboost {xgboost.__version__}`, `joblib {joblib.__version__}`.

## Intended Use
- Predicts probability of social media account inauthenticity, mass-bot creation, and fraudulent profile activity.
- Primary serving surface: AuthentiScore Profile Scanner.

## Training Data & Calibration
- **Source**: Instagram Fake / Spammer Benchmark Dataset (train + test partitions).
- **Dataset Checksums**: `{hashes['train_csv_sha256']}` (train), `{hashes['test_csv_sha256']}` (test).
- **Class Imbalance Strategy**: Handled via algorithmic sample weighting (`class_weight='balanced'`, `scale_pos_weight`) without synthetic oversampling before calibration.
- **Calibration**: 5-fold Sigmoid calibration on held-out splits of natural un-resampled distributions.

## Performance Metrics (Held-out Validation)
- **F1 Score**: {val_f1:.4f}
- **Precision**: {val_prec:.4f}
- **Recall**: {val_rec:.4f}
- **ROC-AUC**: {val_auc:.4f}
- **Brier Score**: {val_brier:.4f}
- **Optimal Decision Threshold**: {optimal_threshold:.4f}
- **Precision @ 90% Recall**: {prec_at_90_recall:.4f}
- **Recall @ 90% Precision**: {rec_at_90_prec:.4f}

## Platform Coverage & Known Limitations
- The underlying tabular model was trained on Instagram profile distributions.
- When applied to non-Instagram platforms (Twitter, YouTube, GitHub, Mastodon), tabular inference is treated as an approximation or gated by rules & NLP signals (`model_applicable: false`), reflecting lower confidence.
"""
    with open(model_card_path, "w", encoding="utf-8") as f:
        f.write(card_content)
    print(f"Generated Model Card: {model_card_path}")

    return metrics_meta


if __name__ == "__main__":
    train_v4()
