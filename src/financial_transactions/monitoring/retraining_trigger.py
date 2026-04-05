"""Retraining trigger module.

Evaluates whether retraining should be triggered based on drift signals,
performance metrics, and data volume, then dispatches retraining jobs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from loguru import logger

from financial_transactions.config import RetrainingConfig


class RetrainingTrigger:
    """Evaluate and trigger retraining jobs.

    Combines drift detection results, performance metrics, and data volume
    to decide if retraining should occur. Enforces cooldown periods and
    daily rate limits.

    Usage:
        trigger = RetrainingTrigger(config, spark)
        if trigger.evaluate_trigger_conditions(drift_report, metrics):
            trigger.trigger_retraining_job(job_id)
    """

    def __init__(self, config: RetrainingConfig, spark: Any | None = None) -> None:
        self.config = config
        self.spark = spark
        self.min_records = config.min_new_records
        self.cooldown_hours = config.cooldown_hours
        self.max_per_day = config.max_retrain_per_day

    def evaluate_trigger_conditions(
        self,
        drift_report: dict[str, Any] | None = None,
        current_metrics: dict[str, float] | None = None,
        baseline_metrics: dict[str, float] | None = None,
        new_record_count: int = 0,
    ) -> bool:
        """Evaluate whether retraining should be triggered.

        :param drift_report: Output from DriftDetector
        :param current_metrics: Current model performance
        :param baseline_metrics: Baseline performance to compare against
        :param new_record_count: Number of new records since last training
        :return: True if retraining should be triggered
        """
        reasons = []

        # Check data drift
        if drift_report and drift_report.get("overall_drift", False):
            reasons.append("data_drift")

        # Check performance degradation
        if current_metrics and baseline_metrics:
            for metric in ["pr_auc", "f1_score"]:
                if (
                    metric in current_metrics
                    and metric in baseline_metrics
                    and baseline_metrics[metric] - current_metrics[metric] > 0.05
                ):
                    reasons.append(f"performance_degradation_{metric}")

        # Check data volume
        if new_record_count >= self.min_records:
            reasons.append("sufficient_new_data")

        if not reasons:
            logger.info("No retraining triggers met")
            return False

        # Check cooldown
        if not self.check_cooldown():
            logger.info(f"Retraining skipped: cooldown period ({self.cooldown_hours}h) not elapsed")
            return False

        # Check daily limit
        if not self._check_daily_limit():
            logger.info(f"Retraining skipped: daily limit ({self.max_per_day}) reached")
            return False

        logger.info(f"Retraining triggered! Reasons: {reasons}")
        return True

    def check_cooldown(self) -> bool:
        """Check if the cooldown period has elapsed since last retraining.

        :return: True if cooldown has elapsed (OK to retrain)
        """
        if self.spark is None:
            return True

        try:
            last_run = self.spark.sql(
                "SELECT MAX(timestamp) as last_run FROM "
                f"{self._audit_table()} "
                "WHERE event_type = 'retraining_triggered'"
            ).collect()[0]["last_run"]

            if last_run is None:
                return True

            elapsed = (datetime.now(tz=UTC) - last_run).total_seconds() / 3600
            return elapsed >= self.cooldown_hours
        except Exception:
            return True  # Allow if audit table doesn't exist

    def _check_daily_limit(self) -> bool:
        """Check if daily retraining limit has been reached."""
        if self.spark is None:
            return True

        try:
            today_count = self.spark.sql(
                "SELECT COUNT(*) as cnt FROM "
                f"{self._audit_table()} "
                "WHERE event_type = 'retraining_triggered' "
                "AND DATE(timestamp) = CURRENT_DATE()"
            ).collect()[0]["cnt"]

            return today_count < self.max_per_day
        except Exception:
            return True

    def trigger_retraining_job(self, job_id: str | None = None) -> None:
        """Trigger specifying retraining job via Databricks SDK.

        :param job_id: Databricks job ID to trigger
        """
        logger.info(f"Triggering retraining job: {job_id}")
        self._write_audit_event("retraining_triggered", {"job_id": job_id})

        if job_id:
            try:
                from databricks.sdk import WorkspaceClient

                w = WorkspaceClient()
                run = w.jobs.run_now(job_id=int(job_id))
                logger.info(f"Retraining job triggered. Run ID: {run.run_id}")
            except Exception:
                logger.exception("Failed to trigger retraining job")

    def _write_audit_event(self, event_type: str, details: dict | None = None) -> None:
        """Write audit event to Delta table."""
        if self.spark is None:
            return

        import json

        from pyspark.sql import Row

        row = Row(
            timestamp=datetime.now(tz=UTC).isoformat(),
            event_type=event_type,
            details=json.dumps(details or {}),
        )

        try:
            df = self.spark.createDataFrame([row])
            df.write.format("delta").mode("append").saveAsTable(self._audit_table())
        except Exception:
            logger.warning("Failed to write audit event")

    def _audit_table(self) -> str:
        """Get the audit table name."""
        return "retraining_audit"
