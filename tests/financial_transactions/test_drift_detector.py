"""Tests for data drift detection logic."""

import numpy as np
import pandas as pd

from financial_transactions.config import DriftConfig
from financial_transactions.monitoring.drift_detector import DriftDetector


def test_compute_psi() -> None:
    """Test Population Stability Index calculation."""
    detector = DriftDetector(DriftConfig(psi_threshold=0.1))

    # Identical distributions should have ~0 PSI
    ref = np.random.normal(0, 1, 1000)
    cur = np.random.normal(0, 1, 1000)
    psi = detector.compute_psi(ref, cur, bins=10)
    assert psi < 0.1

    # Shifted distributions should have high PSI
    cur_shifted = np.random.normal(2, 1, 1000)
    psi_shifted = detector.compute_psi(ref, cur_shifted, bins=10)
    assert psi_shifted > 0.5


def test_compute_js_divergence() -> None:
    """Test Jensen-Shannon Divergence for categoricals."""
    detector = DriftDetector(DriftConfig(js_divergence_threshold=0.1))

    # Same distributions
    ref = pd.Series(["A", "A", "B", "C"])
    cur = pd.Series(["A", "A", "B", "C"])
    js = detector.compute_js_divergence(ref, cur)
    assert js < 0.01

    # Different distributions
    cur_diff = pd.Series(["B", "B", "C", "D"])
    js_diff = detector.compute_js_divergence(ref, cur_diff)
    assert js_diff > 0.1


def test_detect_data_drift() -> None:
    """Test overall data drift detection across features."""
    detector = DriftDetector(DriftConfig(psi_threshold=0.2, js_divergence_threshold=0.1))

    ref_df = pd.DataFrame({"num": np.random.normal(0, 1, 100), "cat": ["A"] * 50 + ["B"] * 50})

    cur_df = pd.DataFrame(
        {
            "num": np.random.normal(3, 1, 100),  # Drifted numerical
            "cat": ["A"] * 50 + ["B"] * 50,  # Stable categorical
        }
    )

    report = detector.detect_data_drift(ref_df, cur_df, numerical_features=["num"], categorical_features=["cat"])

    assert report["overall_drift"] is True
    assert "num" in report["drifted_features"]
    assert "cat" not in report["drifted_features"]


def test_should_retrain() -> None:
    """Test retraining trigger logic."""
    detector = DriftDetector(DriftConfig(performance_degradation_threshold=0.05))

    # Trigger on data drift alone
    drift_report = {"overall_drift": True}
    assert detector.should_retrain(drift_report) is True

    # Trigger on performance degradation
    drift_report = {"overall_drift": False}
    base_perf = {"pr_auc": 0.80}
    cur_perf = {"pr_auc": 0.70}  # Degraded by 0.1 > 0.05
    assert detector.should_retrain(drift_report, cur_perf, base_perf) is True

    # Do not trigger if stable
    cur_perf = {"pr_auc": 0.79}  # Degraded by 0.01 < 0.05
    assert detector.should_retrain(drift_report, cur_perf, base_perf) is False
