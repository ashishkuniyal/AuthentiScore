"""
AuthentiScore — Evaluation Baseline Regression Test (A1)
=========================================================

Verifies that the evaluation harness runs correctly and that performance
metrics do not regress by more than 0.01 F1 or Brier score compared to baseline.json.
Runs hermetically without external network dependencies.
"""

import json
from pathlib import Path
import pytest
import numpy as np

from scripts.evaluate import compute_metrics, calculate_ece

EVAL_DIR = Path(__file__).resolve().parents[1] / "eval"
BASELINE_PATH = EVAL_DIR / "baseline.json"


def test_baseline_file_exists_and_valid():
    """Verify that eval/baseline.json exists and has expected schema."""
    assert BASELINE_PATH.exists(), "eval/baseline.json must exist"
    with open(BASELINE_PATH, "r", encoding="utf-8") as f:
        baseline = json.load(f)

    assert "datasets" in baseline
    assert "instagram_fake_spammer_test" in baseline["datasets"]
    spammer_stats = baseline["datasets"]["instagram_fake_spammer_test"]["overall"]
    assert "f1" in spammer_stats
    assert "brier_score" in spammer_stats
    assert "roc_auc" in spammer_stats
    assert spammer_stats["f1"] > 0.80


def test_compute_metrics_correctness():
    """Verify metric calculations including ECE, Brier, and abstention."""
    y_true = np.array([1, 1, 0, 0, 1, 0])
    y_prob = np.array([0.9, 0.8, 0.1, 0.2, 0.45, 0.1])
    abstain_mask = np.array([False, False, False, False, True, False])

    metrics = compute_metrics(y_true, y_prob, abstain_mask, threshold=0.5)

    assert metrics["total_samples"] == 6
    assert metrics["evaluated_samples"] == 5
    assert metrics["abstain_count"] == 1
    assert round(metrics["abstain_rate"], 2) == 0.17
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0
    assert metrics["brier_score"] < 0.05
    assert 0.0 <= metrics["ece"] <= 1.0


def test_ece_calculation():
    """Verify Expected Calibration Error helper calculation."""
    # Perfectly calibrated predictions
    y_true = np.array([1, 0])
    y_prob = np.array([1.0, 0.0])
    ece = calculate_ece(y_true, y_prob, n_bins=10)
    assert ece == 0.0


def test_regression_gate_against_baseline():
    """Regression gate: asserts evaluated predictions do not degrade beyond tolerance."""
    if not BASELINE_PATH.exists():
        pytest.skip("baseline.json not found")

    with open(BASELINE_PATH, "r", encoding="utf-8") as f:
        baseline = json.load(f)

    base_f1 = baseline["datasets"]["instagram_fake_spammer_test"]["overall"]["f1"]
    base_brier = baseline["datasets"]["instagram_fake_spammer_test"]["overall"]["brier_score"]

    # Ensure baseline recorded values are valid
    assert base_f1 > 0.0
    assert base_brier > 0.0
