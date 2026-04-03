"""Model serving manager for Databricks endpoints with canary deployment."""

from __future__ import annotations

from typing import Any

import mlflow
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import EndpointCoreConfigInput, ServedEntityInput
from loguru import logger


class AnomalyModelServing:
    """Manage model serving endpoints with canary deployment support.

    Supports deploying, updating, and rolling back model serving endpoints
    on Databricks with configurable traffic splits for canary testing.

    Usage:
        serving = AnomalyModelServing(model_name, endpoint_name)
        serving.deploy_or_update(version="3")
        serving.deploy_canary(version="4", canary_pct=10)
        serving.promote_to_production()
    """

    def __init__(self, model_name: str, endpoint_name: str) -> None:
        self.workspace = WorkspaceClient()
        self.endpoint_name = endpoint_name
        self.model_name = model_name
        self._canary_version: str | None = None
        self._production_version: str | None = None

    def get_latest_model_version(self) -> str:
        """Get the latest model version from Unity Catalog."""
        client = mlflow.MlflowClient()
        version = client.get_model_version_by_alias(self.model_name, alias="champion").version
        logger.info(f"Latest champion version: {version}")
        return version

    def deploy_or_update(
        self,
        version: str = "latest",
        workload_size: str = "Small",
        scale_to_zero: bool = True,
    ) -> None:
        """Deploy or update the serving endpoint (full traffic)."""
        endpoint_exists = any(
            item.name == self.endpoint_name
            for item in self.workspace.serving_endpoints.list()
        )
        entity_version = self.get_latest_model_version() if version == "latest" else version

        served_entities = [
            ServedEntityInput(
                entity_name=self.model_name,
                scale_to_zero_enabled=scale_to_zero,
                workload_size=workload_size,
                entity_version=entity_version,
            )
        ]

        if not endpoint_exists:
            self.workspace.serving_endpoints.create(
                name=self.endpoint_name,
                config=EndpointCoreConfigInput(served_entities=served_entities),
            )
            logger.info(f"Created endpoint {self.endpoint_name} with v{entity_version}")
        else:
            self.workspace.serving_endpoints.update_config(
                name=self.endpoint_name, served_entities=served_entities
            )
            logger.info(f"Updated endpoint {self.endpoint_name} to v{entity_version}")

        self._production_version = entity_version

    def deploy_canary(
        self,
        version: str,
        canary_pct: int = 10,
        workload_size: str = "Small",
    ) -> None:
        """Deploy a canary version with split traffic.

        :param version: New model version to test
        :param canary_pct: Percentage of traffic to route to canary
        :param workload_size: Compute size for served entities
        """
        current_version = self._production_version or self.get_latest_model_version()
        production_pct = 100 - canary_pct

        served_entities = [
            ServedEntityInput(
                entity_name=self.model_name,
                entity_version=current_version,
                workload_size=workload_size,
                scale_to_zero_enabled=True,
            ),
            ServedEntityInput(
                entity_name=self.model_name,
                entity_version=version,
                workload_size=workload_size,
                scale_to_zero_enabled=True,
            ),
        ]

        traffic_config = {
            "routes": [
                {"served_model_name": f"{self.model_name}-{current_version}", "traffic_percentage": production_pct},
                {"served_model_name": f"{self.model_name}-{version}", "traffic_percentage": canary_pct},
            ]
        }

        self.workspace.serving_endpoints.update_config(
            name=self.endpoint_name,
            served_entities=served_entities,
            traffic_config=traffic_config,
        )

        self._canary_version = version
        logger.info(f"Canary deployed: v{version} ({canary_pct}%), v{current_version} ({production_pct}%)")

    def promote_to_production(self) -> None:
        """Promote canary version to 100% production traffic."""
        if self._canary_version is None:
            logger.warning("No canary version to promote")
            return

        self.deploy_or_update(version=self._canary_version)
        logger.info(f"Canary v{self._canary_version} promoted to 100% production")
        self._production_version = self._canary_version
        self._canary_version = None

    def rollback(self, version: str | None = None) -> None:
        """Rollback to a previous model version."""
        rollback_version = version or self._production_version
        if rollback_version is None:
            logger.error("No version to rollback to")
            return

        self.deploy_or_update(version=rollback_version)
        self._canary_version = None
        logger.info(f"Rolled back to v{rollback_version}")
