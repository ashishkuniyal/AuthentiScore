# AuthentiScore Model Card — Ensemble v4

## Model Details
- **Model Architecture**: Soft-Voting Ensemble (LogisticRegression + RandomForest + XGBoost) wrapped in `CalibratedClassifierCV(method='sigmoid', cv=5)`.
- **Model Version**: `v4`
- **Feature Schema Version**: `v4`
- **Training Date**: `2026-10-13T20:45:16.524882+00:00`
- **Libraries**: `scikit-learn 1.9.1`, `xgboost 3.4.1`, `joblib 1.6.0`.

## Intended Use
- Predicts probability of social media account inauthenticity, mass-bot creation, and fraudulent profile activity.
- Primary serving surface: AuthentiScore Profile Scanner.

## Training Data & Calibration
- **Source**: Instagram Fake / Spammer Benchmark Dataset (train + test partitions).
- **Dataset Checksums**: `54adc145282c4bbd` (train), `4d09fc192c9f9736` (test).
- **Class Imbalance Strategy**: Handled via algorithmic sample weighting (`class_weight='balanced'`, `scale_pos_weight`) without synthetic oversampling before calibration.
- **Calibration**: 5-fold Sigmoid calibration on held-out splits of natural un-resampled distributions.

## Performance Metrics (Held-out Validation)
- **F1 Score**: 0.9173
- **Precision**: 0.9683
- **Recall**: 0.8714
- **ROC-AUC**: 0.9720
- **Brier Score**: 0.0647
- **Optimal Decision Threshold**: 0.7505
- **Precision @ 90% Recall**: 0.9265
- **Recall @ 90% Precision**: 0.9000

## Platform Coverage & Known Limitations
- The underlying tabular model was trained on Instagram profile distributions.
- When applied to non-Instagram platforms (Twitter, YouTube, GitHub, Mastodon), tabular inference is treated as an approximation or gated by rules & NLP signals (`model_applicable: false`), reflecting lower confidence.
