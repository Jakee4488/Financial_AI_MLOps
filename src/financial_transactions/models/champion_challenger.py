"""Champion/Challenger model comparison gate.

Compares the tournament winner (challenger) against the current production
champion model. Deployment only proceeds if the challenger demonstrates
sufficient improvement on the primary metric.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import mlflow
import pandas as pd
from loguru import logger
from mlflow import MlflowClient

from financial_transactions.config import ProjectConfig
from financial_transactions.models.base_model import ModelResult


@dataclass
class ComparisonResult:
    """Result of a champion vs. challenger comparison."""

    decision: str  # "PROMOTE", "REJECT"
    reason: str = ""
    challenger_metrics: dict[str, float] = field(default_factory=dict)
    champion_metrics: dict[str, float] = field(default_factory=dict)
    improvement: dict[str, float] = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(tz=UTC).isoformat()


class ChampionChallenger:
    """Champion/Challenger gating framework.

    Compares the tournament winner against the current production champion.
    The challenger must beat the champion on the primary metric (PR-AUC)
    by at least `min_improvement_threshold` to be promoted.

    Usage:
        gate = ChampionChallenger(config, spark)
        result = gate.compare(challenger_result)
        if result.decision == "PROMOTE":
            gate.promote_challenger(challenger_result)
    """

    def __init__(self, config: ProjectConfig, spark: Any | None = None) -> None:
        """Initialize the Champion/Challenger gate.

        :param config: Project configuration with champion_challenger settings
        :param spark: SparkSession for Delta audit writes
        """
        self.config = config
        self.spark = spark
        self.cc_config = config.champion_challenger
        self.primary_metric = self.cc_config.primary_metric
        self.min_threshold = self.cc_config.min_improvement_threshold
        self.model_name = f"{config.catalog_name}.{config.schema_name}.anomaly_model_champion"

    def _get_champion_metrics(self) -> dict[str, float] | None:
        """Retrieve metrics for the current production champion.

        :return: Dictionary of champion metrics, or None if no champion exists
        """
        client = MlflowClient()
        try:
            champion_version = client.get_model_version_by_alias(name=self.model_name, alias="champion")
            champion_run = client.get_run(champion_version.run_id)
            metrics = {k: float(v) for k, v in champion_run.data.metrics.items()}
            logger.info(f"Current champion: v{champion_version.version}, metrics: {metrics}")
            return metrics
        except Exception:
            logger.info("No existing champion found — challenger will be auto-promoted")
            return None

    def compare(self, challenger_result: ModelResult) -> ComparisonResult:
        """Compare the tournament winner against the current champion.

        :param challenger_result: ModelResult from the tournament winner
        :return: ComparisonResult with PROMOTE or REJECT decision
        """
        logger.info("=" * 50)
        logger.info("⚔️ Champion vs. Challenger Comparison")
        logger.info("=" * 50)

        champion_metrics = self._get_champion_metrics()
        challenger_metrics = challenger_result.metrics

        # No champion exists — auto-promote
        if champion_metrics is None:
            logger.info("✅ No existing champion — auto-promoting challenger")
            return ComparisonResult(
                decision="PROMOTE",
                reason="No existing champion — first model auto-promoted",
                challenger_metrics=challenger_metrics,
                champion_metrics={},
                improvement=dict(challenger_metrics.items()),
            )

        # Compute improvements
        improvement = {}
        for metric in [self.primary_metric] + self.cc_config.secondary_metrics:
            chall_val = challenger_metrics.get(metric, 0)
            champ_val = champion_metrics.get(metric, 0)
            improvement[metric] = chall_val - champ_val

        primary_improvement = improvement.get(self.primary_metric, 0)

        # Decision logic
        if primary_improvement >= self.min_threshold:
            decision = "PROMOTE"
            reason = (
                f"Challenger improves {self.primary_metric} by {primary_improvement:.4f} "
                f"(>= threshold {self.min_threshold})"
            )
            logger.info(f"✅ {reason}")
        else:
            decision = "REJECT"
            reason = (
                f"Insufficient improvement on {self.primary_metric}: {primary_improvement:.4f} < {self.min_threshold}"
            )
            logger.info(f"❌ {reason}")

        # Log comparison details
        comparison_df = pd.DataFrame(
            {
                "metric": list(challenger_metrics.keys()),
                "challenger": list(challenger_metrics.values()),
                "champion": [champion_metrics.get(k, 0) for k in challenger_metrics],
                "improvement": [improvement.get(k, 0) for k in challenger_metrics],
            }
        )
        logger.info(f"\n{comparison_df.to_string()}")
        logger.info(f"\nDecision: {decision}")

        return ComparisonResult(
            decision=decision,
            reason=reason,
            challenger_metrics=challenger_metrics,
            champion_metrics=champion_metrics,
            improvement=improvement,
        )

    def promote_challenger(self, challenger_result: ModelResult) -> str:
        """Register the challenger as the new champion in Unity Catalog.

        :param challenger_result: ModelResult of the winning challenger
        :return: Registered model version number
        """
        logger.info(f"🏆 Promoting {challenger_result.model_type} as new champion...")

        # Register model
        registered_model = mlflow.register_model(
            model_uri=challenger_result.model_uri,
            name=self.model_name,
            tags={"model_type": challenger_result.model_type},
        )

        client = MlflowClient()

        # Set champion alias
        client.set_registered_model_alias(
            name=self.model_name,
            alias="champion",
            version=registered_model.version,
        )

        # Also set latest-model alias for compatibility
        client.set_registered_model_alias(
            name=self.model_name,
            alias="latest-model",
            version=registered_model.version,
        )

        logger.info(
            f"✅ Champion promoted: {challenger_result.model_type} "
            f"v{registered_model.version} ({self.primary_metric}="
            f"{challenger_result.metrics.get(self.primary_metric, 0):.4f})"
        )

        return str(registered_model.version)

    def log_comparison(self, result: ComparisonResult) -> None:
        """Log comparison results to MLflow.

        :param result: ComparisonResult to log
        """
        mlflow.set_experiment(self.config.experiment_name_basic)
        with mlflow.start_run(run_name="champion-challenger-comparison"):
            mlflow.log_param("decision", result.decision)
            mlflow.log_param("reason", result.reason[:250])

            for k, v in result.improvement.items():
                mlflow.log_metric(f"improvement_{k}", v)

            for k, v in result.challenger_metrics.items():
                mlflow.log_metric(f"challenger_{k}", v)

            for k, v in result.champion_metrics.items():
                mlflow.log_metric(f"champion_{k}", v)

        logger.info("Comparison results logged to MLflow")

    def write_audit_record(self, result: ComparisonResult, challenger: ModelResult) -> None:
        """Write comparison result to Delta audit table.

        :param result: ComparisonResult
        :param challenger: ModelResult of the challenger
        """
        if self.spark is None:
            return

        import json

        from pyspark.sql import Row

        audit_record = Row(
            timestamp=result.timestamp,
            decision=result.decision,
            reason=result.reason,
            challenger_model_type=challenger.model_type,
            challenger_run_id=challenger.run_id,
            primary_metric_value=challenger.metrics.get(self.primary_metric, 0),
            improvement=json.dumps(result.improvement),
        )

        audit_df = self.spark.createDataFrame([audit_record])
        audit_table = f"{self.config.catalog_name}.{self.config.schema_name}.champion_challenger_audit"

        try:
            audit_df.write.format("delta").mode("append").saveAsTable(audit_table)
            logger.info(f"Audit record written to {audit_table}")
        except Exception:
            logger.warning("Failed to write audit record (table may not exist yet)")
