"""Drift detection for financial market anomaly models.

Implements PSI (Population Stability Index) and Jensen-Shannon divergence
for detecting data drift, prediction drift, and concept drift.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger

from financial_transactions.config import DriftConfig


class DriftDetector:
    """Detect data and model drift using statistical methods.

    Monitors feature distributions against a reference window and
    triggers retraining when thresholds are breached.

    Usage:
        detector = DriftDetector(config)
        drift_result = detector.detect_data_drift(reference_df, current_df)
        if detector.should_retrain(drift_result):
            trigger_retraining()
    """

    def __init__(self, config: DriftConfig, spark: Any | None = None) -> None:
        """Initialize the drift detector.

        :param config: Drift detection configuration
        :param spark: SparkSession for Delta writes
        """
        self.config = config
        self.spark = spark
        self.psi_threshold = config.psi_threshold
        self.js_threshold = config.js_divergence_threshold
        self.perf_threshold = config.performance_degradation_threshold

    @staticmethod
    def compute_psi(reference: np.ndarray, current: np.ndarray, bins: int = 10) -> float:
        """Compute Population Stability Index between two distributions.

        PSI < 0.1: no significant change
        PSI 0.1-0.2: moderate change
        PSI > 0.2: significant change

        :param reference: Reference distribution
        :param current: Current distribution
        :param bins: Number of bins for histogram
        :return: PSI value
        """
        # Create bins from the reference distribution
        breakpoints = np.percentile(reference, np.linspace(0, 100, bins + 1))
        breakpoints = np.unique(breakpoints)

        ref_counts, _ = np.histogram(reference, bins=breakpoints)
        cur_counts, _ = np.histogram(current, bins=breakpoints)

        # Convert to proportions with smoothing
        ref_pct = (ref_counts + 1) / (len(reference) + len(breakpoints))
        cur_pct = (cur_counts + 1) / (len(current) + len(breakpoints))

        psi = np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct))
        return float(psi)

    @staticmethod
    def compute_js_divergence(reference: pd.Series, current: pd.Series) -> float:
        """Compute Jensen-Shannon divergence for categorical distributions.

        :param reference: Reference categorical distribution
        :param current: Current categorical distribution
        :return: JS divergence value (0 = identical, 1 = completely different)
        """
        from scipy.spatial.distance import jensenshannon

        # Get combined categories
        all_cats = set(reference.unique()) | set(current.unique())

        ref_dist = reference.value_counts(normalize=True)
        cur_dist = current.value_counts(normalize=True)

        # Align distributions
        ref_aligned = np.array([ref_dist.get(c, 0) for c in sorted(all_cats)])
        cur_aligned = np.array([cur_dist.get(c, 0) for c in sorted(all_cats)])

        # Smooth zeros
        ref_aligned = ref_aligned + 1e-10
        cur_aligned = cur_aligned + 1e-10

        # Normalize
        ref_aligned = ref_aligned / ref_aligned.sum()
        cur_aligned = cur_aligned / cur_aligned.sum()

        return float(jensenshannon(ref_aligned, cur_aligned) ** 2)

    def detect_data_drift(
        self,
        reference_df: pd.DataFrame,
        current_df: pd.DataFrame,
        numerical_features: list[str],
        categorical_features: list[str],
    ) -> dict[str, Any]:
        """Detect data drift across all features.

        :param reference_df: Reference period data
        :param current_df: Current period data
        :param numerical_features: List of numerical feature names
        :param categorical_features: List of categorical feature names
        :return: Drift report with per-feature PSI/JS values and overall drift flag
        """
        logger.info("Running data drift detection...")
        drift_report: dict[str, Any] = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "reference_size": len(reference_df),
            "current_size": len(current_df),
            "feature_drift": {},
            "overall_drift": False,
        }

        drifted_features = []

        # Numerical features → PSI
        for feature in numerical_features:
            if feature in reference_df.columns and feature in current_df.columns:
                ref_vals = reference_df[feature].dropna().values
                cur_vals = current_df[feature].dropna().values
                if len(ref_vals) > 0 and len(cur_vals) > 0:
                    psi = self.compute_psi(ref_vals, cur_vals)
                    is_drifted = psi > self.psi_threshold
                    drift_report["feature_drift"][feature] = {
                        "metric": "psi",
                        "value": round(psi, 4),
                        "threshold": self.psi_threshold,
                        "drifted": is_drifted,
                    }
                    if is_drifted:
                        drifted_features.append(feature)

        # Categorical features → JS divergence
        for feature in categorical_features:
            if feature in reference_df.columns and feature in current_df.columns:
                js = self.compute_js_divergence(reference_df[feature], current_df[feature])
                is_drifted = js > self.js_threshold
                drift_report["feature_drift"][feature] = {
                    "metric": "js_divergence",
                    "value": round(js, 4),
                    "threshold": self.js_threshold,
                    "drifted": is_drifted,
                }
                if is_drifted:
                    drifted_features.append(feature)

        drift_report["drifted_features"] = drifted_features
        drift_report["overall_drift"] = len(drifted_features) > 0

        logger.info(
            f"Drift detection complete: {len(drifted_features)}/{len(numerical_features) + len(categorical_features)} "
            f"features drifted"
        )

        return drift_report

    def detect_prediction_drift(self, reference_preds: np.ndarray, current_preds: np.ndarray) -> dict[str, Any]:
        """Detect prediction distribution drift.

        :param reference_preds: Reference period predictions
        :param current_preds: Current period predictions
        :return: Prediction drift report
        """
        psi = self.compute_psi(reference_preds, current_preds)
        return {
            "prediction_psi": round(psi, 4),
            "threshold": self.psi_threshold,
            "drifted": psi > self.psi_threshold,
        }

    def should_retrain(
        self,
        drift_report: dict[str, Any],
        current_performance: dict[str, float] | None = None,
        baseline_performance: dict[str, float] | None = None,
    ) -> bool:
        """Determine if retraining should be triggered.

        :param drift_report: Output from detect_data_drift
        :param current_performance: Current model metrics
        :param baseline_performance: Baseline model metrics
        :return: True if retraining should be triggered
        """
        # Data drift detected
        if drift_report.get("overall_drift", False):
            logger.info("Retraining recommended: data drift detected")
            return True

        # Performance degradation
        if current_performance and baseline_performance:
            for metric in ["pr_auc", "f1_score"]:
                if metric in current_performance and metric in baseline_performance:
                    degradation = baseline_performance[metric] - current_performance[metric]
                    if degradation > self.perf_threshold:
                        logger.info(f"Retraining recommended: {metric} degraded by {degradation:.4f}")
                        return True

        logger.info("No retraining needed")
        return False

    def write_drift_metrics(self, drift_report: dict[str, Any], table_name: str | None = None) -> None:
        """Write drift metrics to a Delta monitoring table.

        :param drift_report: Drift report to persist
        :param table_name: Full Delta table name
        """
        if self.spark is None:
            logger.info("No Spark session — skipping Delta write")
            return

        from pyspark.sql import Row

        row = Row(
            timestamp=drift_report["timestamp"],
            reference_size=drift_report["reference_size"],
            current_size=drift_report["current_size"],
            overall_drift=drift_report["overall_drift"],
            drifted_features=json.dumps(drift_report.get("drifted_features", [])),
            feature_drift_details=json.dumps(drift_report.get("feature_drift", {})),
        )

        df = self.spark.createDataFrame([row])
        target_table = table_name or "drift_monitoring"

        try:
            df.write.format("delta").mode("append").saveAsTable(target_table)
            logger.info(f"Drift metrics written to {target_table}")
        except Exception:
            logger.warning(f"Failed to write drift metrics to {target_table}")
