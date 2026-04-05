"""Rollback manager for model and feature table versioning."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import mlflow
from loguru import logger

from financial_transactions.serving.model_serving import AnomalyModelServing


class RollbackManager:
    """Manage rollback of models and feature tables.

    Captures deployment state snapshots, performs rollback via
    Delta Time Travel, and verifies rollback success.

    Usage:
        rm = RollbackManager(config, spark)
        rm.capture_state()
        # ... deployment happens ...
        rm.rollback_model(previous_version)
        rm.verify_rollback()
    """

    def __init__(self, config: Any, spark: Any | None = None) -> None:
        self.config = config
        self.spark = spark
        self._snapshots: list[dict[str, Any]] = []

    def capture_state(self, model_version: str, endpoint_name: str) -> dict[str, Any]:
        """Capture current deployment state before changes."""
        snapshot = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "model_version": model_version,
            "endpoint_name": endpoint_name,
            "catalog": self.config.catalog_name,
            "schema": self.config.schema_name,
        }

        if self.spark:
            try:
                from delta.tables import DeltaTable

                feature_table = f"{self.config.catalog_name}.{self.config.schema_name}.trade_features"
                dt = DeltaTable.forName(self.spark, feature_table)
                snapshot["feature_table_version"] = str(dt.history().select("version").first()[0])
            except Exception:
                snapshot["feature_table_version"] = "unknown"

        self._snapshots.append(snapshot)
        logger.info(f"State captured: {json.dumps(snapshot, indent=2)}")
        return snapshot

    def rollback_model(self, version: str) -> None:
        """Rollback model serving endpoint to a specific version."""
        model_name = f"{self.config.catalog_name}.{self.config.schema_name}.anomaly_model_champion"
        endpoint_name = f"anomaly-model-serving-{self.config.schema_name}"

        serving = AnomalyModelServing(model_name, endpoint_name)
        serving.rollback(version=version)
        logger.info(f"Model rolled back to version {version}")

    def rollback_features(self, version: int) -> None:
        """Rollback feature table to a previous version using Delta Time Travel."""
        if self.spark is None:
            logger.warning("No Spark session — cannot rollback features")
            return

        feature_table = f"{self.config.catalog_name}.{self.config.schema_name}.trade_features"
        try:
            self.spark.sql(f"RESTORE TABLE {feature_table} TO VERSION AS OF {version}")
            logger.info(f"Feature table restored to version {version}")
        except Exception:
            logger.exception(f"Failed to restore feature table to version {version}")

    def verify_rollback(self, expected_version: str | None = None) -> bool:
        """Verify that rollback was successful."""
        model_name = f"{self.config.catalog_name}.{self.config.schema_name}.anomaly_model_champion"
        try:
            client = mlflow.MlflowClient()
            current = client.get_model_version_by_alias(model_name, "champion")
            if expected_version and current.version != expected_version:
                logger.error(f"Rollback verification failed: expected v{expected_version}, got v{current.version}")
                return False
            logger.info(f"Rollback verified: current champion is v{current.version}")
            return True
        except Exception:
            logger.exception("Rollback verification failed")
            return False

    def get_rollback_history(self) -> list[dict[str, Any]]:
        """Return the history of captured state snapshots."""
        return list(self._snapshots)
