import os
import sys
import json
import joblib
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

import sklearn
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
import xgboost
from xgboost import XGBClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss, roc_auc_score, accuracy_score
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

# Ensure backend directory is in sys.path to import feature_engine
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.feature_engine import calculate_profile_completeness  # C20 shared function


def main():
    base_dir = Path(__file__).resolve().parents[2]
    data_dir = base_dir / "data" / "raw" / "instagram_fake_spammer"

    print(f"Loading datasets from {data_dir}...")
    df_train = pd.read_csv(data_dir / "train.csv")
    df_test = pd.read_csv(data_dir / "test.csv")

    df = pd.concat([df_train, df_test], ignore_index=True)
    total_rows = len(df)

    print("Mapping columns to feature schema...")
    df_mapped = pd.DataFrame()
    df_mapped['followers'] = df['#followers']
    df_mapped['following'] = df['#follows']
    df_mapped['posts'] = df['#posts']
    df_mapped['bio_length'] = df['description length']
    df_mapped['has_profile_picture'] = df['profile pic']
    df_mapped['is_private'] = df['private']
    df_mapped['username_digit_ratio'] = df['nums/length username']

    df_mapped['follower_following_ratio'] = df.apply(
        lambda row: row['#followers'] / row['#follows'] if row['#follows'] > 0 else float(row['#followers']),
        axis=1
    )

    # C20: Use shared calculate_profile_completeness
    df_mapped['profile_completeness'] = df.apply(
        lambda row: calculate_profile_completeness({
            "username": "user",
            "bio": "bio_text" if row['description length'] > 0 else "",
            "followers": row['#followers'],
            "following": row['#follows'],
            "posts": row['#posts'],
            "has_profile_picture": row['profile pic'],
        }),
        axis=1
    )

    y = df['fake'].values

    features_list = [
        "followers", "following", "posts", "bio_length", "has_profile_picture",
        "is_private", "username_digit_ratio", "follower_following_ratio", "profile_completeness"
    ]
    X = df_mapped[features_list].copy()

    print("Performing stratified train/test split...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

    # ─────────────────────────────────────────────────────────────
    # Model Variant 1: SMOTE
    # ─────────────────────────────────────────────────────────────
    print("Training Variant 1: SMOTE pipeline...")
    smote = SMOTE(random_state=42)
    X_train_res, y_train_res = smote.fit_resample(X_train, y_train)

    lr_smote = LogisticRegression(max_iter=2000, random_state=42)
    rf_smote = RandomForestClassifier(n_estimators=100, random_state=42)
    xgb_smote = XGBClassifier(eval_metric='logloss', random_state=42)

    ensemble_smote = VotingClassifier(
        estimators=[('lr', lr_smote), ('rf', rf_smote), ('xgb', xgb_smote)],
        voting='soft'
    )
    pipeline_smote = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),  # C19 median imputer
        ('calibrated_ensemble', CalibratedClassifierCV(ensemble_smote, cv=5, method='sigmoid'))
    ])
    pipeline_smote.fit(X_train_res, y_train_res)

    y_prob_smote = pipeline_smote.predict_proba(X_test)[:, 1]
    y_pred_smote = pipeline_smote.predict(X_test)
    brier_smote = brier_score_loss(y_test, y_prob_smote)
    roc_smote = roc_auc_score(y_test, y_prob_smote)
    acc_smote = accuracy_score(y_test, y_pred_smote)

    # ─────────────────────────────────────────────────────────────
    # Model Variant 2: class_weight="balanced" + scale_pos_weight (M1, D9)
    # ─────────────────────────────────────────────────────────────
    print("Training Variant 2: Class-weighted pipeline without SMOTE...")
    num_neg = int((y_train == 0).sum())
    num_pos = int((y_train == 1).sum())
    scale_pos = num_neg / max(num_pos, 1)

    lr_cw = LogisticRegression(max_iter=2000, class_weight='balanced', random_state=42)
    rf_cw = RandomForestClassifier(n_estimators=100, class_weight='balanced', random_state=42)
    xgb_cw = XGBClassifier(eval_metric='logloss', scale_pos_weight=scale_pos, random_state=42)

    ensemble_cw = VotingClassifier(
        estimators=[('lr', lr_cw), ('rf', rf_cw), ('xgb', xgb_cw)],
        voting='soft'
    )
    pipeline_cw = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),  # C19 median imputer
        ('calibrated_ensemble', CalibratedClassifierCV(ensemble_cw, cv=5, method='sigmoid'))
    ])
    pipeline_cw.fit(X_train, y_train)

    y_prob_cw = pipeline_cw.predict_proba(X_test)[:, 1]
    y_pred_cw = pipeline_cw.predict(X_test)
    brier_cw = brier_score_loss(y_test, y_prob_cw)
    roc_cw = roc_auc_score(y_test, y_prob_cw)
    acc_cw = accuracy_score(y_test, y_pred_cw)

    print(f"Variant 1 (SMOTE): Brier={brier_smote:.4f}, ROC-AUC={roc_smote:.4f}, Acc={acc_smote:.4f}")
    print(f"Variant 2 (Class-Weighted): Brier={brier_cw:.4f}, ROC-AUC={roc_cw:.4f}, Acc={acc_cw:.4f}")

    # DECISION D9: Keep whichever pipeline yields the lower (better) Brier score
    if brier_cw <= brier_smote:
        chosen_variant = "class_weighted"
        final_pipeline = pipeline_cw
        best_brier, best_roc, best_acc = brier_cw, roc_cw, acc_cw
    else:
        chosen_variant = "smote"
        final_pipeline = pipeline_smote
        best_brier, best_roc, best_acc = brier_smote, roc_smote, acc_smote

    print(f"Selected model: {chosen_variant} with test Brier score {best_brier:.4f}")

    metrics = {
        "model_version": "v3",
        "model_name": "CalibratedEnsemble_LR_RF_XGB",
        "training_date": datetime.now(timezone.utc).isoformat(),
        "chosen_variant": chosen_variant,
        "features": features_list,
        "dataset_row_counts": {
            "total_rows": total_rows,
            "train_rows": len(X_train),
            "test_rows": len(X_test),
        },
        "library_versions": {
            "scikit_learn": sklearn.__version__,
            "xgboost": xgboost.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "variant_comparison": {
            "smote": {
                "test_brier_score": round(float(brier_smote), 4),
                "test_roc_auc": round(float(roc_smote), 4),
                "test_accuracy": round(float(acc_smote), 4),
            },
            "class_weighted": {
                "test_brier_score": round(float(brier_cw), 4),
                "test_roc_auc": round(float(roc_cw), 4),
                "test_accuracy": round(float(acc_cw), 4),
            }
        },
        "test_brier_score": round(float(best_brier), 4),
        "test_roc_auc": round(float(best_roc), 4),
        "test_accuracy": round(float(best_acc), 4),
    }

    # ─────────────────────────────────────────────────────────────
    # Optional Cross-Dataset Testing (Instafake)
    # ─────────────────────────────────────────────────────────────
    instafake_dir = base_dir / "data" / "raw" / "instafake" / "fake-v1.0"
    if instafake_dir.exists():
        print("Evaluating on Instafake cross-dataset...")
        with open(instafake_dir / "fakeAccountData.json", "r", encoding="utf-8") as f:
            fake_data = json.load(f)
        with open(instafake_dir / "realAccountData.json", "r", encoding="utf-8") as f:
            real_data = json.load(f)

        df_insta = pd.DataFrame(fake_data + real_data)
        df_insta_mapped = pd.DataFrame()
        df_insta_mapped['followers'] = df_insta['userFollowerCount']
        df_insta_mapped['following'] = df_insta['userFollowingCount']
        df_insta_mapped['posts'] = df_insta['userMediaCount']
        df_insta_mapped['bio_length'] = df_insta['userBiographyLength']
        df_insta_mapped['has_profile_picture'] = df_insta['userHasProfilPic']
        df_insta_mapped['is_private'] = df_insta['userIsPrivate']
        df_insta_mapped['username_digit_ratio'] = df_insta.apply(
            lambda r: r['usernameDigitCount'] / r['usernameLength'] if r['usernameLength'] > 0 else 0,
            axis=1
        )
        df_insta_mapped['follower_following_ratio'] = df_insta.apply(
            lambda r: r['userFollowerCount'] / r['userFollowingCount'] if r['userFollowingCount'] > 0 else float(r['userFollowerCount']),
            axis=1
        )
        df_insta_mapped['profile_completeness'] = df_insta.apply(
            lambda r: calculate_profile_completeness({
                "username": "user",
                "bio": "bio_text" if r['userBiographyLength'] > 0 else "",
                "followers": r['userFollowerCount'],
                "following": r['userFollowingCount'],
                "posts": r['userMediaCount'],
                "has_profile_picture": r['userHasProfilPic'],
            }),
            axis=1
        )

        X_insta = df_insta_mapped[features_list].copy()
        y_insta = df_insta['isFake'].values

        y_prob_insta = final_pipeline.predict_proba(X_insta)[:, 1]
        y_pred_insta = final_pipeline.predict(X_insta)

        metrics["cross_dataset_instafake"] = {
            "brier_score": round(float(brier_score_loss(y_insta, y_prob_insta)), 4),
            "roc_auc": round(float(roc_auc_score(y_insta, y_prob_insta)), 4),
            "accuracy": round(float(accuracy_score(y_insta, y_pred_insta)), 4),
        }

    # ─────────────────────────────────────────────────────────────
    # Save Artifacts
    # ─────────────────────────────────────────────────────────────
    out_dir = BACKEND_DIR / "trained_models"
    out_dir.mkdir(exist_ok=True, parents=True)

    model_path = out_dir / "authentiscore_ensemble_v3.pkl"
    joblib.dump(final_pipeline, model_path)
    print(f"Saved ensemble to {model_path}")

    # B2: Save features JSON list
    features_path = out_dir / "authentiscore_features_v3.json"
    with open(features_path, "w", encoding="utf-8") as f:
        json.dump(features_list, f, indent=4)
    print(f"Saved feature list to {features_path}")

    # Save metrics JSON
    metrics_path = out_dir / "metrics_v3.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=4)
    print(f"Saved metrics to {metrics_path}")


if __name__ == '__main__':
    main()
