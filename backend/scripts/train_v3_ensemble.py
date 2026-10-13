import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path

from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from xgboost import XGBClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss, roc_auc_score, accuracy_score
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

def main():
    base_dir = Path(__file__).resolve().parents[2]
    data_dir = base_dir / "data" / "raw" / "instagram_fake_spammer"
    
    print(f"Loading datasets from {data_dir}...")
    df_train = pd.read_csv(data_dir / "train.csv")
    df_test = pd.read_csv(data_dir / "test.csv")
    
    df = pd.concat([df_train, df_test], ignore_index=True)
    
    print("Mapping columns to feature schema...")
    df_mapped = pd.DataFrame()
    df_mapped['followers'] = df['#followers']
    df_mapped['following'] = df['#follows']
    df_mapped['posts'] = df['#posts']
    df_mapped['bio_length'] = df['description length']
    df_mapped['has_profile_picture'] = df['profile pic']
    df_mapped['is_private'] = df['private']
    df_mapped['username_digit_ratio'] = df['nums/length username']
    
    # Calculate ratios and completeness
    df_mapped['follower_following_ratio'] = df.apply(
        lambda row: row['#followers'] / row['#follows'] if row['#follows'] > 0 else float(row['#followers']),
        axis=1
    )
    
    def calc_comp(row):
        fields = 6
        present = 5 # username, followers, following, posts, pic are implicit
        if row['description length'] > 0:
            present += 1
        return round(present / fields, 4)
        
    df_mapped['profile_completeness'] = df.apply(calc_comp, axis=1)
    
    y = df['fake'].values
    
    features_list = [
        "followers", "following", "posts", "bio_length", "has_profile_picture",
        "is_private", "username_digit_ratio", "follower_following_ratio", "profile_completeness"
    ]
    X = df_mapped[features_list].copy()
    
    print("Performing stratified train/test split...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
    
    print("Applying SMOTE to training fold...")
    smote = SMOTE(random_state=42)
    X_train_res, y_train_res = smote.fit_resample(X_train, y_train)
    
    # Base Models
    lr = LogisticRegression(max_iter=2000, random_state=42)
    rf = RandomForestClassifier(n_estimators=100, random_state=42)
    xgb = XGBClassifier(eval_metric='logloss', use_label_encoder=False, random_state=42)
    
    # Cross Validation on Training Data (for metrics)
    print("Running 5-fold CV for base models...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    metrics = {}
    
    for name, model in [("LR", lr), ("RF", rf), ("XGB", xgb)]:
        pipeline = ImbPipeline([
            ('imputer', SimpleImputer(strategy='constant', fill_value=0)),
            ('smote', SMOTE(random_state=42)), 
            ('model', model)
        ])
        scores = cross_val_score(pipeline, X_train, y_train, cv=cv, scoring='roc_auc')
        metrics[f"{name}_cv_roc_auc"] = np.mean(scores)
        print(f"  {name} CV ROC AUC: {metrics[f'{name}_cv_roc_auc']:.4f}")
        
    # Build Ensemble
    ensemble = VotingClassifier(
        estimators=[('lr', lr), ('rf', rf), ('xgb', xgb)],
        voting='soft'
    )
    
    print("Training calibrated ensemble pipeline...")
    # Pipeline handles NaN inputs and calibration
    final_pipeline = Pipeline([
        ('imputer', SimpleImputer(strategy='constant', fill_value=0)),
        ('calibrated_ensemble', CalibratedClassifierCV(ensemble, cv=5, method='sigmoid'))
    ])
    
    final_pipeline.fit(X_train_res, y_train_res)
    
    # Evaluation
    print("Evaluating on test set...")
    y_prob = final_pipeline.predict_proba(X_test)[:, 1]
    y_pred = final_pipeline.predict(X_test)
    
    brier = brier_score_loss(y_test, y_prob)
    roc = roc_auc_score(y_test, y_prob)
    acc = accuracy_score(y_test, y_pred)
    
    metrics.update({
        "test_brier_score": brier,
        "test_roc_auc": roc,
        "test_accuracy": acc
    })
    
    print("Test Metrics:")
    print(f"  Brier Score: {brier:.4f}")
    print(f"  ROC AUC: {roc:.4f}")
    print(f"  Accuracy: {acc:.4f}")
    
    # ---------------------------------------------------------
    # Cross-Dataset Testing (Instafake)
    # ---------------------------------------------------------
    print("Evaluating on Instafake cross-dataset...")
    instafake_dir = base_dir / "data" / "raw" / "instafake" / "fake-v1.0"
    if instafake_dir.exists():
        import json as builtin_json
        with open(instafake_dir / "fakeAccountData.json") as f:
            fake_data = builtin_json.load(f)
        with open(instafake_dir / "realAccountData.json") as f:
            real_data = builtin_json.load(f)
            
        df_insta = pd.DataFrame(fake_data + real_data)
        
        # Map Instafake to schema
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
            lambda row: row['userFollowerCount'] / row['userFollowingCount'] if row['userFollowingCount'] > 0 else float(row['userFollowerCount']),
            axis=1
        )
        
        df_insta_mapped['profile_completeness'] = df_insta.apply(
            lambda row: round((5 + (1 if row['userBiographyLength'] > 0 else 0)) / 6, 4), 
            axis=1
        )
        
        X_insta = df_insta_mapped[features_list].copy()
        y_insta = df_insta['isFake'].values
        
        y_prob_insta = final_pipeline.predict_proba(X_insta)[:, 1]
        y_pred_insta = final_pipeline.predict(X_insta)
        
        insta_brier = brier_score_loss(y_insta, y_prob_insta)
        insta_roc = roc_auc_score(y_insta, y_prob_insta)
        insta_acc = accuracy_score(y_insta, y_pred_insta)
        
        metrics.update({
            "cross_dataset_instafake_brier": insta_brier,
            "cross_dataset_instafake_roc_auc": insta_roc,
            "cross_dataset_instafake_accuracy": insta_acc
        })
        
        print("Cross-Dataset (Instafake) Metrics:")
        print(f"  Brier Score: {insta_brier:.4f}")
        print(f"  ROC AUC: {insta_roc:.4f}")
        print(f"  Accuracy: {insta_acc:.4f}")
    else:
        print("Instafake dataset not found, skipping cross-dataset test.")
    
    # Save Model
    out_dir = base_dir / "backend" / "trained_models"
    out_dir.mkdir(exist_ok=True, parents=True)
    
    model_path = out_dir / "authentiscore_ensemble_v3.pkl"
    joblib.dump(final_pipeline, model_path)
    print(f"Saved ensemble to {model_path}")
    
    metrics_path = out_dir / "metrics_v3.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=4)
    print(f"Saved metrics to {metrics_path}")

if __name__ == '__main__':
    main()
