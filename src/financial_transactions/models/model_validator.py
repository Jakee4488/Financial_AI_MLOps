"""Model validation gate for deployment readiness.

Validates performance thresholds, data coverage, and inference latency
before allowing a model to be deployed to serving endpoints.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from loguru import logger

from financial_transactions.models.base_model import ModelResult


@dataclass
class ValidationResult:
    """Result from model validation checks."""

    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    details: dict[str, str] = field(default_factory=dict)


class ModelValidator:
    """Validate models before deployment.

    Runs a suite of checks: performance thresholds, data coverage,
    and inference latency to ensure the model is production-ready.

    Usage:
        validator = ModelValidator(min_pr_auc=0.7, min_f1=0.5)
        result = validator.validate(model_result, X_test)
        if result.passed:
            deploy(model_result)
    """

    def __init__(
        self,
        min_pr_auc: float = 0.5,
        min_f1: float = 0.3,
        max_latency_ms: float = 50.0,
        required_symbols: list[str] | None = None,
    ) -> None:
        """Initialize validator with thresholds.

        :param min_pr_auc: Minimum PR-AUC score
        :param min_f1: Minimum F1 score
        :param max_latency_ms: Maximum p99 inference latency in milliseconds
        :param required_symbols: List of symbols that must be in training data
        """
        self.min_pr_auc = min_pr_auc
        self.min_f1 = min_f1
        self.max_latency_ms = max_latency_ms
        self.required_symbols = required_symbols or []

    def validate(
        self,
        model_result: ModelResult,
        test_data: Any | None = None,
        pipeline: Any | None = None,
    ) -> ValidationResult:
        """Run all validation checks.

        :param model_result: ModelResult with metrics
        :param test_data: Test DataFrame for latency checks
        :param pipeline: Trained pipeline for latency checks
        :return: ValidationResult
        """
        checks = {}
        details = {}

        # Performance check
        pr_auc = model_result.metrics.get("pr_auc", 0)
        checks["performance_pr_auc"] = pr_auc >= self.min_pr_auc
        details["performance_pr_auc"] = f"PR-AUC: {pr_auc:.4f} (min: {self.min_pr_auc})"

        f1 = model_result.metrics.get("f1_score", 0)
        checks["performance_f1"] = f1 >= self.min_f1
        details["performance_f1"] = f"F1: {f1:.4f} (min: {self.min_f1})"

        # Latency check (if pipeline and test data provided)
        if pipeline is not None and test_data is not None:
            latency_result = self._check_latency(pipeline, test_data)
            checks["latency"] = latency_result["passed"]
            details["latency"] = latency_result["detail"]
        else:
            checks["latency"] = True
            details["latency"] = "Skipped (no pipeline/data provided)"

        # Data coverage check
        if test_data is not None and "symbol" in getattr(test_data, "columns", []):
            coverage = self._check_data_coverage(test_data)
            checks["data_coverage"] = coverage["passed"]
            details["data_coverage"] = coverage["detail"]
        else:
            checks["data_coverage"] = True
            details["data_coverage"] = "Skipped"

        passed = all(checks.values())

        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"Validation {status}")
        for check, ok in checks.items():
            icon = "✅" if ok else "❌"
            logger.info(f"  {icon} {check}: {details[check]}")

        return ValidationResult(passed=passed, checks=checks, details=details)

    def _check_latency(self, pipeline: Any, test_data: Any) -> dict[str, Any]:
        """Check inference latency (p99).

        :param pipeline: Trained sklearn pipeline
        :param test_data: Test features DataFrame
        :return: Dictionary with passed flag and detail string
        """
        sample = test_data[:100] if len(test_data) > 100 else test_data
        latencies = []

        for _ in range(10):
            start = time.perf_counter()
            pipeline.predict(sample)
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms / len(sample))

        p99 = float(np.percentile(latencies, 99))
        passed = p99 <= self.max_latency_ms

        return {
            "passed": passed,
            "detail": f"p99 latency: {p99:.2f}ms (max: {self.max_latency_ms}ms)",
        }

    def _check_data_coverage(self, test_data: Any) -> dict[str, Any]:
        """Check if training data covers all required symbols.

        :param test_data: Test DataFrame with 'symbol' column
        :return: Dictionary with passed flag and detail string
        """
        if not self.required_symbols:
            return {"passed": True, "detail": "No required symbols specified"}

        present = set(test_data["symbol"].unique())
        missing = set(self.required_symbols) - present
        passed = len(missing) == 0

        return {
            "passed": passed,
            "detail": f"Coverage: {len(present)}/{len(self.required_symbols)} symbols"
            + (f" (missing: {missing})" if missing else ""),
        }
