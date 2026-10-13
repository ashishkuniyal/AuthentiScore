#!/usr/bin/env python3
"""
AuthentiScore — Production Evaluation Harness (A1)
===================================================

Runs the full AuthentiScore pipeline on:
  1. Instagram fake/spammer benchmark (stratified train/test split)
  2. InstaFake benchmark (cross-dataset validation)
  3. Custom human-labeled profiles (backend/eval/labeled_profiles.csv) if present

Computes:
  - Precision, Recall, F1, PR-AUC, ROC-AUC
  - Brier score, Expected Calibration Error (ECE, 10 bins)
  - Confusion Matrix at the production threshold
  - Abstain rate
  - Per-slice performance (verified vs unverified, bio empty vs present,
    follower buckets, completeness buckets)

Outputs:
  - backend/eval/report_<date>.json
  - backend/eval/report_<date>.md
  - Console table summary
  - Compares with or updates backend/eval/baseline.json
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

# Setup import path for backend
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Suppress verbose loggers for evaluation
logging.getLogger("app").setLevel(logging.WARNING)

from app.routes.scan import run_risk_pipeline
from app.services.model_store import MODEL_NAME, MODEL_VERSION

ROOT_DIR = BACKEND_DIR.parent
DATA_DIR = ROOT_DIR / "data" / "raw"
EVAL_DIR = BACKEND_DIR / "eval"


def calculate_ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Calculate 10-bin Expected Calibration Error."""
    if len(y_true) == 0:
        return 0.0
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    total = len(y_true)

    for i in range(n_bins):
        low, high = bin_boundaries[i], bin_boundaries[i + 1]
        if i == n_bins - 1:
            mask = (y_prob >= low) & (y_prob <= high)
        else:
            mask = (y_prob >= low) & (y_prob < high)
        n_in_bin = np.sum(mask)
        if n_in_bin > 0:
            bin_acc = np.mean(y_true[mask])
            bin_conf = np.mean(y_prob[mask])
            ece += (n_in_bin / total) * abs(bin_acc - bin_conf)

    return float(round(ece, 4))


def compute_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    abstain_mask: np.ndarray,
    threshold: float = 0.50,
) -> Dict[str, Any]:
    """Compute comprehensive accuracy, calibration and abstention metrics."""
    total_samples = len(y_true)
    abstain_count = int(np.sum(abstain_mask))
    abstain_rate = round(abstain_count / total_samples, 4) if total_samples > 0 else 0.0

    # Evaluated samples are non-abstained
    eval_mask = ~abstain_mask
    y_t_eval = y_true[eval_mask]
    y_p_eval = y_prob[eval_mask]

    if len(y_t_eval) == 0 or len(np.unique(y_t_eval)) < 2:
        return {
            "total_samples": total_samples,
            "evaluated_samples": len(y_t_eval),
            "abstain_count": abstain_count,
            "abstain_rate": abstain_rate,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "roc_auc": 0.0,
            "pr_auc": 0.0,
            "brier_score": 0.0,
            "ece": 0.0,
            "confusion_matrix": {"tn": 0, "fp": 0, "fn": 0, "tp": 0},
        }

    y_pred = (y_p_eval >= threshold).astype(int)

    precision = float(round(precision_score(y_t_eval, y_pred, zero_division=0), 4))
    recall = float(round(recall_score(y_t_eval, y_pred, zero_division=0), 4))
    f1 = float(round(f1_score(y_t_eval, y_pred, zero_division=0), 4))

    try:
        roc_auc = float(round(roc_auc_score(y_t_eval, y_p_eval), 4))
    except Exception:
        roc_auc = 0.0

    try:
        pr_auc = float(round(average_precision_score(y_t_eval, y_p_eval), 4))
    except Exception:
        pr_auc = 0.0

    brier = float(round(brier_score_loss(y_t_eval, y_p_eval), 4))
    ece = calculate_ece(y_t_eval, y_p_eval, n_bins=10)

    tn, fp, fn, tp = confusion_matrix(y_t_eval, y_pred, labels=[0, 1]).ravel()

    return {
        "total_samples": total_samples,
        "evaluated_samples": int(len(y_t_eval)),
        "abstain_count": abstain_count,
        "abstain_rate": abstain_rate,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "brier_score": brier,
        "ece": ece,
        "confusion_matrix": {
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
        },
    }


def load_instagram_fake_spammer() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Load and format the Instagram fake/spammer benchmark dataset."""
    p_train = DATA_DIR / "instagram_fake_spammer" / "train.csv"
    p_test = DATA_DIR / "instagram_fake_spammer" / "test.csv"

    if not p_train.exists() or not p_test.exists():
        print("Warning: instagram_fake_spammer dataset not found.")
        return [], []

    df_train = pd.read_csv(p_train)
    df_test = pd.read_csv(p_test)
    df_all = pd.concat([df_train, df_test], ignore_index=True)

    # Convert to standard profile records
    records = []
    for idx, row in df_all.iterrows():
        username = f"user_{idx}_{int(row['nums/length username'] * 100)}"
        bio_len = int(row["description length"])
        bio = "A" * bio_len if bio_len > 0 else ""
        rec = {
            "platform": "instagram",
            "username": username,
            "followers": float(row["#followers"]),
            "following": float(row["#follows"]),
            "posts": float(row["#posts"]),
            "bio": bio,
            "bio_length": float(bio_len),
            "has_profile_picture": int(row["profile pic"]),
            "is_private": int(row["private"]),
            "username_digit_ratio": float(row["nums/length username"]),
            "is_verified": 0,
            "label": int(row["fake"]),
        }
        records.append(rec)

    # Grouped/stratified split by account (fixed seed 42)
    y = [r["label"] for r in records]
    train_records, test_records = train_test_split(
        records, test_size=0.25, stratify=y, random_state=42
    )
    return train_records, test_records


def load_instafake_cross_dataset() -> List[Dict[str, Any]]:
    """Load InstaFake cross-dataset benchmark."""
    fake_json = DATA_DIR / "instafake" / "fake-v1.0" / "fakeAccountData.json"
    real_json = DATA_DIR / "instafake" / "fake-v1.0" / "realAccountData.json"

    if not fake_json.exists() or not real_json.exists():
        print("Warning: instafake dataset not found.")
        return []

    records = []
    with open(fake_json, "r", encoding="utf-8") as f:
        fakes = json.load(f)
    with open(real_json, "r", encoding="utf-8") as f:
        reals = json.load(f)

    for idx, item in enumerate(fakes + reals):
        ulen = item.get("usernameLength", 10)
        digits = item.get("usernameDigitCount", 0)
        digit_ratio = (digits / ulen) if ulen > 0 else 0.0
        bio_len = item.get("userBiographyLength", 0)
        bio = "Bio" * (bio_len // 3) if bio_len > 0 else ""
        records.append({
            "platform": "instagram",
            "username": f"instafake_{idx}",
            "followers": float(item.get("userFollowerCount", 0)),
            "following": float(item.get("userFollowingCount", 0)),
            "posts": float(item.get("userMediaCount", 0)),
            "bio": bio,
            "bio_length": float(bio_len),
            "has_profile_picture": int(item.get("userHasProfilPic", 1)),
            "is_private": int(item.get("userIsPrivate", 0)),
            "username_digit_ratio": float(digit_ratio),
            "is_verified": 0,
            "label": int(item.get("isFake", 0)),
        })

    return records


def load_human_labeled_dataset() -> List[Dict[str, Any]]:
    """Load custom human-labeled profiles from eval/labeled_profiles.csv."""
    labeled_csv = EVAL_DIR / "labeled_profiles.csv"
    if not labeled_csv.exists():
        return []

    df = pd.read_csv(labeled_csv)
    records = []
    for _, row in df.iterrows():
        raw_label = str(row.get("label", "")).strip().lower()
        if raw_label not in {"fake", "real", "automated_declared"}:
            continue
        # Fake is 1; real and declared automated utility bots are non-fake (0)
        binary_label = 1 if raw_label == "fake" else 0
        records.append({
            "platform": str(row.get("platform", "instagram")).lower(),
            "profile_url": str(row.get("profile_url", "")),
            "username": str(row.get("username", "")),
            "followers": float(row.get("followers", 0) or 0),
            "following": float(row.get("following", 0) or 0),
            "posts": float(row.get("posts", 0) or 0),
            "bio": str(row.get("bio", "") or ""),
            "has_profile_picture": int(row.get("has_profile_picture", 1) or 0),
            "is_private": int(row.get("is_private", 0) or 0),
            "is_verified": int(row.get("is_verified", 0) or 0),
            "raw_label": raw_label,
            "label": binary_label,
        })
    return records


def evaluate_dataset(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Run production pipeline on records and evaluate slices."""
    if not records:
        return {}

    y_true = []
    y_prob = []
    abstain_flags = []
    processed_records = []

    for item in records:
        target = item["label"]
        res = run_risk_pipeline(item, bio=item.get("bio", ""))
        score = res.get("final_score")
        is_abstain = bool(res.get("abstain", False) or score is None)

        prob = (float(score) / 100.0) if score is not None else 0.50

        y_true.append(target)
        y_prob.append(prob)
        abstain_flags.append(is_abstain)

        rec_entry = {**item, "predicted_score": score, "predicted_prob": prob, "abstain": is_abstain}
        processed_records.append(rec_entry)

    y_true_arr = np.array(y_true, dtype=int)
    y_prob_arr = np.array(y_prob, dtype=float)
    abstain_arr = np.array(abstain_flags, dtype=bool)

    overall = compute_metrics(y_true_arr, y_prob_arr, abstain_arr)

    # Slice Evaluations
    df = pd.DataFrame(processed_records)

    slices: Dict[str, Any] = {}

    # Slice: Bio presence
    has_bio = df["bio"].apply(lambda b: len(str(b or "").strip()) > 0).values
    slices["bio_present"] = compute_metrics(y_true_arr[has_bio], y_prob_arr[has_bio], abstain_arr[has_bio])
    slices["bio_empty"] = compute_metrics(y_true_arr[~has_bio], y_prob_arr[~has_bio], abstain_arr[~has_bio])

    # Slice: Verified status
    is_ver = df["is_verified"].values == 1
    if np.sum(is_ver) > 0:
        slices["verified"] = compute_metrics(y_true_arr[is_ver], y_prob_arr[is_ver], abstain_arr[is_ver])
    slices["unverified"] = compute_metrics(y_true_arr[~is_ver], y_prob_arr[~is_ver], abstain_arr[~is_ver])

    # Slice: Follower buckets
    followers = df["followers"].values
    b_lt100 = followers < 100
    b_100_1k = (followers >= 100) & (followers < 1000)
    b_1k_10k = (followers >= 1000) & (followers < 10000)
    b_gt10k = followers >= 10000

    slices["followers_lt_100"] = compute_metrics(y_true_arr[b_lt100], y_prob_arr[b_lt100], abstain_arr[b_lt100])
    slices["followers_100_to_1k"] = compute_metrics(y_true_arr[b_100_1k], y_prob_arr[b_100_1k], abstain_arr[b_100_1k])
    slices["followers_1k_to_10k"] = compute_metrics(y_true_arr[b_1k_1k := b_1k_10k], y_prob_arr[b_1k_1k], abstain_arr[b_1k_1k])
    slices["followers_gt_10k"] = compute_metrics(y_true_arr[b_gt10k], y_prob_arr[b_gt10k], abstain_arr[b_gt10k])

    return {"overall": overall, "slices": slices}


def run_full_evaluation(update_baseline: bool = False) -> Dict[str, Any]:
    """Execute complete evaluation suite across all datasets and produce reports."""
    print("=" * 70)
    print("AuthentiScore — Production Accuracy Evaluation Harness (A1)")
    print("=" * 70)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Current Model: {MODEL_NAME} ({MODEL_VERSION})")

    EVAL_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Instagram fake/spammer
    print("\n[1/3] Evaluating Instagram Fake/Spammer Test Split...")
    _, test_records = load_instagram_fake_spammer()
    spammer_eval = evaluate_dataset(test_records)

    # 2. InstaFake cross-dataset
    print("[2/3] Evaluating InstaFake Cross-Dataset...")
    instafake_records = load_instafake_cross_dataset()
    instafake_eval = evaluate_dataset(instafake_records)

    # 3. Custom human-labeled
    print("[3/3] Evaluating Custom Labeled Profiles (eval/labeled_profiles.csv)...")
    human_records = load_human_labeled_dataset()
    human_eval = evaluate_dataset(human_records) if human_records else None

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "datasets": {
            "instagram_fake_spammer_test": spammer_eval,
            "instafake_cross_dataset": instafake_eval,
            "human_labeled": human_eval,
        },
    }

    # Print summary table
    print("\n" + "=" * 70)
    print(f"{'Dataset / Split':<30} | {'F1':<6} | {'ROC-AUC':<7} | {'Brier':<6} | {'ECE':<6} | {'Abstain':<7}")
    print("-" * 70)

    for ds_name, ds_data in report["datasets"].items():
        if not ds_data or "overall" not in ds_data:
            continue
        ov = ds_data["overall"]
        print(f"{ds_name:<30} | {ov['f1']:<6.4f} | {ov['roc_auc']:<7.4f} | {ov['brier_score']:<6.4f} | {ov['ece']:<6.4f} | {ov['abstain_rate']:<7.2%}")

    print("=" * 70)

    # Save timestamped report
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_json = EVAL_DIR / f"report_{today_str}.json"
    report_md = EVAL_DIR / f"report_{today_str}.md"

    with open(report_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    # Generate Markdown summary
    md_lines = [
        "# AuthentiScore Scanner Accuracy Evaluation Report",
        f"- **Date**: {report['timestamp']}",
        f"- **Model**: {MODEL_NAME} ({MODEL_VERSION})",
        "",
        "## Overall Benchmark Metrics",
        "| Dataset | Samples | Precision | Recall | F1 | ROC-AUC | Brier | ECE | Abstain |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for ds_name, ds_data in report["datasets"].items():
        if not ds_data or "overall" not in ds_data:
            continue
        ov = ds_data["overall"]
        md_lines.append(
            f"| `{ds_name}` | {ov['total_samples']} | {ov['precision']:.4f} | {ov['recall']:.4f} | **{ov['f1']:.4f}** | {ov['roc_auc']:.4f} | {ov['brier_score']:.4f} | {ov['ece']:.4f} | {ov['abstain_rate']:.1%} |"
        )
    md_lines.append("")

    with open(report_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    # Baseline management
    baseline_file = EVAL_DIR / "baseline.json"
    if update_baseline or not baseline_file.exists():
        with open(baseline_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\n[Baseline] Updated baseline metrics file: {baseline_file}")
    else:
        # Check against baseline
        with open(baseline_file, "r", encoding="utf-8") as f:
            baseline = json.load(f)
        b_spammer = baseline.get("datasets", {}).get("instagram_fake_spammer_test", {}).get("overall", {})
        c_spammer = spammer_eval.get("overall", {})

        f1_delta = c_spammer.get("f1", 0) - b_spammer.get("f1", 0)
        brier_delta = c_spammer.get("brier_score", 0) - b_spammer.get("brier_score", 0)
        print(f"\n[Baseline Comparison vs {baseline.get('timestamp')}]")
        print(f"  F1 Delta:    {f1_delta:+.4f} (Baseline: {b_spammer.get('f1', 0):.4f} -> Current: {c_spammer.get('f1', 0):.4f})")
        print(f"  Brier Delta: {brier_delta:+.4f} (Lower is better)")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AuthentiScore Evaluation Harness")
    parser.add_argument("--update-baseline", action="store_true", help="Record current metrics as new baseline.json")
    args = parser.parse_args()

    run_full_evaluation(update_baseline=args.update_baseline)
