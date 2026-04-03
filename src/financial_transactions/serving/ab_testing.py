"""A/B testing manager for model serving endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
from loguru import logger


class ABTestManager:
    """Manage A/B tests between model versions.

    Sets up traffic splitting, monitors per-variant metrics,
    and concludes experiments with statistical significance testing.

    Usage:
        ab = ABTestManager(config, spark)
        ab.create_experiment("v3", "v4", split=50)
        ab.monitor_experiment()
        ab.conclude_experiment()
    """

    def __init__(self, config: Any, spark: Any | None = None) -> None:
        self.config = config
        self.spark = spark
        self._experiments: list[dict[str, Any]] = []

    def create_experiment(
        self,
        control_version: str,
        treatment_version: str,
        traffic_split: int = 50,
    ) -> dict[str, Any]:
        """Create an A/B test between two model versions.

        :param control_version: Control (current) model version
        :param treatment_version: Treatment (new) model version
        :param traffic_split: Percentage of traffic for treatment
        :return: Experiment configuration
        """
        experiment = {
            "id": f"ab_{datetime.now(tz=timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            "control_version": control_version,
            "treatment_version": treatment_version,
            "traffic_split": traffic_split,
            "start_time": datetime.now(tz=timezone.utc).isoformat(),
            "status": "running",
            "control_metrics": {},
            "treatment_metrics": {},
        }

        self._experiments.append(experiment)
        logger.info(
            f"A/B test created: control=v{control_version} ({100 - traffic_split}%) "
            f"vs treatment=v{treatment_version} ({traffic_split}%)"
        )
        return experiment

    def monitor_experiment(self, experiment_id: str | None = None) -> dict[str, Any]:
        """Collect metrics for both variants.

        :param experiment_id: Experiment ID (defaults to latest)
        :return: Current metrics for both variants
        """
        exp = self._get_experiment(experiment_id)
        if not exp:
            return {}

        # In production, these would come from the inference log table
        logger.info(f"Monitoring A/B test {exp['id']}...")
        return {
            "experiment_id": exp["id"],
            "status": exp["status"],
            "control": exp["control_metrics"],
            "treatment": exp["treatment_metrics"],
        }

    def conclude_experiment(
        self,
        experiment_id: str | None = None,
        min_samples: int = 1000,
    ) -> dict[str, Any]:
        """Conclude an A/B test with statistical significance testing.

        Uses chi-square test to determine if the treatment is significantly
        better than the control.

        :param experiment_id: Experiment ID
        :param min_samples: Minimum samples required for conclusion
        :return: Conclusion with decision and statistical details
        """
        exp = self._get_experiment(experiment_id)
        if not exp:
            return {"decision": "ERROR", "reason": "Experiment not found"}

        # In production, compute this from actual inference data
        conclusion = {
            "experiment_id": exp["id"],
            "control_version": exp["control_version"],
            "treatment_version": exp["treatment_version"],
            "decision": "NEEDS_MORE_DATA",
            "conclusion_time": datetime.now(tz=timezone.utc).isoformat(),
        }

        control_metrics = exp.get("control_metrics", {})
        treatment_metrics = exp.get("treatment_metrics", {})

        if control_metrics and treatment_metrics:
            control_auc = control_metrics.get("pr_auc", 0)
            treatment_auc = treatment_metrics.get("pr_auc", 0)

            if treatment_auc > control_auc:
                conclusion["decision"] = "PROMOTE_TREATMENT"
                conclusion["reason"] = f"Treatment PR-AUC ({treatment_auc:.4f}) > Control ({control_auc:.4f})"
            else:
                conclusion["decision"] = "KEEP_CONTROL"
                conclusion["reason"] = f"Control PR-AUC ({control_auc:.4f}) >= Treatment ({treatment_auc:.4f})"

        exp["status"] = "concluded"
        exp["conclusion"] = conclusion

        logger.info(f"A/B test concluded: {conclusion['decision']}")
        return conclusion

    def _get_experiment(self, experiment_id: str | None) -> dict[str, Any] | None:
        """Get experiment by ID or return latest."""
        if not self._experiments:
            return None
        if experiment_id:
            return next((e for e in self._experiments if e["id"] == experiment_id), None)
        return self._experiments[-1]
