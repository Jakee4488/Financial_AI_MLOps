"""Performance monitoring for deployed anomaly models.

Computes live metrics, manages Lakehouse Monitor tables,
and exports metrics to JSON for the performance dashboard.
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from financial_transactions.config import ProjectConfig


class PerformanceMonitor:
    """Monitor deployed model performance.

    Tracks inference metrics, manages Lakehouse monitoring tables,
    and exports metrics for the web dashboard.

    Usage:
        monitor = PerformanceMonitor(config, spark, workspace)
        monitor.create_monitoring_table()
        monitor.refresh_monitoring()
        monitor.export_metrics_json("dashboard/data/")
    """

    def __init__(
        self,
        config: ProjectConfig,
        spark: Any,
        workspace: Any | None = None,
    ) -> None:
        self.config = config
        self.spark = spark
        self.workspace = workspace
        self.catalog = config.catalog_name
        self.schema = config.schema_name
        self.monitoring_table = f"{self.catalog}.{self.schema}.model_monitoring"

    def create_monitoring_table(self) -> None:
        """Create a Lakehouse Monitor for the inference log table."""
        if self.workspace is None:
            logger.warning("No workspace client — skipping monitor creation")
            return

        from databricks.sdk.service.catalog import (
            MonitorInferenceLog,
            MonitorInferenceLogProblemType,
        )

        try:
            self.workspace.quality_monitors.get(self.monitoring_table)
            logger.info(f"Monitor already exists for {self.monitoring_table}")
        except Exception:
            logger.info(f"Creating monitor for {self.monitoring_table}")
            self.workspace.quality_monitors.create(
                table_name=self.monitoring_table,
                assets_dir=f"/Workspace/Shared/lakehouse_monitoring/{self.monitoring_table}",
                output_schema_name=f"{self.catalog}.{self.schema}",
                inference_log=MonitorInferenceLog(
                    problem_type=MonitorInferenceLogProblemType.PROBLEM_TYPE_CLASSIFICATION,
                    prediction_col="prediction",
                    timestamp_col="timestamp",
                    granularities=["30 minutes"],
                    model_id_col="model_name",
                ),
            )
            self.spark.sql(
                f"ALTER TABLE {self.monitoring_table} "
                "SET TBLPROPERTIES (delta.enableChangeDataFeed = true);"
            )
            logger.info("Monitoring table created")

    def refresh_monitoring(self) -> None:
        """Refresh the Lakehouse Monitor."""
        if self.workspace is None:
            return
        try:
            self.workspace.quality_monitors.run_refresh(table_name=self.monitoring_table)
            logger.info("Monitoring refresh triggered")
        except Exception:
            logger.warning("Failed to refresh monitoring")

    def compute_live_metrics(self) -> dict[str, float]:
        """Compute live model performance metrics from the monitoring table.

        :return: Dictionary of current performance metrics
        """
        try:
            from pyspark.sql import functions as F

            monitoring_df = self.spark.table(self.monitoring_table)
            total = monitoring_df.count()
            if total == 0:
                return {"total_predictions": 0}

            metrics = monitoring_df.agg(
                F.count("*").alias("total_predictions"),
                F.avg("execution_duration_ms").alias("avg_latency_ms"),
                F.percentile_approx("execution_duration_ms", 0.99).alias("p99_latency_ms"),
                F.countDistinct("model_name").alias("active_models"),
            ).collect()[0]

            return {
                "total_predictions": int(metrics["total_predictions"]),
                "avg_latency_ms": float(metrics["avg_latency_ms"] or 0),
                "p99_latency_ms": float(metrics["p99_latency_ms"] or 0),
                "active_models": int(metrics["active_models"]),
            }
        except Exception:
            logger.warning("Failed to compute live metrics")
            return {}

    def export_metrics_json(self, output_dir: str, additional_data: dict | None = None) -> None:
        """Export current metrics to JSON for the dashboard.

        :param output_dir: Directory to write JSON files
        :param additional_data: Additional data to include
        """
        import os

        os.makedirs(output_dir, exist_ok=True)

        metrics = self.compute_live_metrics()
        if additional_data:
            metrics.update(additional_data)

        output_path = os.path.join(output_dir, "performance_timeline.json")
        with open(output_path, "w") as f:
            json.dump(metrics, f, indent=2)

        logger.info(f"Metrics exported to {output_path}")
