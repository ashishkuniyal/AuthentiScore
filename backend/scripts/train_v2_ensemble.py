import joblib
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from xgboost import XGBClassifier

def train_ensemble_model():
    print("Generating synthetic dataset...")
    np.random.seed(42)
    
    n_samples = 5000
    
    # Generate Real Profiles (0)
    real_followers = np.random.randint(100, 100000, n_samples // 2)
    real_following = np.random.randint(50, 1000, n_samples // 2)
    real_posts = np.random.randint(10, 5000, n_samples // 2)
    real_bio_len = np.random.randint(20, 150, n_samples // 2)
    real_pic = np.random.choice([1], n_samples // 2)
    real_priv = np.random.choice([0, 1], n_samples // 2, p=[0.7, 0.3])
    real_dig = np.random.uniform(0, 0.1, n_samples // 2)
    real_ratio = real_followers / (real_following + 1)
    real_comp = np.random.uniform(0.7, 1.0, n_samples // 2)
    
    # Generate Fake Profiles (1)
    fake_followers = np.random.randint(0, 50, n_samples // 2)
    fake_following = np.random.randint(500, 5000, n_samples // 2)
    fake_posts = np.random.randint(0, 5, n_samples // 2)
    fake_bio_len = np.random.randint(0, 30, n_samples // 2)
    fake_pic = np.random.choice([0, 1], n_samples // 2, p=[0.8, 0.2])
    fake_priv = np.random.choice([0, 1], n_samples // 2, p=[0.9, 0.1])
    fake_dig = np.random.uniform(0.3, 0.8, n_samples // 2)
    fake_ratio = fake_followers / (fake_following + 1)
    fake_comp = np.random.uniform(0.1, 0.5, n_samples // 2)

    X_real = pd.DataFrame({
        'followers': real_followers,
        'following': real_following,
        'posts': real_posts,
        'bio_length': real_bio_len,
        'has_profile_picture': real_pic,
        'is_private': real_priv,
        'username_digit_ratio': real_dig,
        'follower_following_ratio': real_ratio,
        'profile_completeness': real_comp
    })
    y_real = np.zeros(n_samples // 2)
    
    X_fake = pd.DataFrame({
        'followers': fake_followers,
        'following': fake_following,
        'posts': fake_posts,
        'bio_length': fake_bio_len,
        'has_profile_picture': fake_pic,
        'is_private': fake_priv,
        'username_digit_ratio': fake_dig,
        'follower_following_ratio': fake_ratio,
        'profile_completeness': fake_comp
    })
    y_fake = np.ones(n_samples // 2)
    
    X = pd.concat([X_real, X_fake]).reset_index(drop=True)
    y = np.concatenate([y_real, y_fake])
    
    # Models
    rf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
    xgb = XGBClassifier(n_estimators=100, max_depth=5, random_state=42, use_label_encoder=False, eval_metric='logloss')
    
    # Voting Classifier (Soft voting to get probabilities)
    ensemble = VotingClassifier(
        estimators=[('rf', rf), ('xgb', xgb)],
        voting='soft',
        weights=[1, 1.5] # slightly more weight to XGBoost
    )
    
    print("Training Ensemble Model...")
    ensemble.fit(X, y)
    
    backend_dir = Path(__file__).resolve().parents[1]
    out_path = backend_dir / "trained_models" / "authentiscore_ensemble_v2.pkl"
    joblib.dump(ensemble, out_path)
    print(f"Saved ensemble to {out_path}")
    
if __name__ == "__main__":
    train_ensemble_model()
