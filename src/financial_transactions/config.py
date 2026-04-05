"""Configuration module for the Financial Transactions project."""

from __future__ import annotations

from typing import Any

import yaml
from pydantic import BaseModel


class StreamingConfig(BaseModel):
    """Configuration for Finnhub WebSocket streaming."""

    finnhub_api_key: str = ""
    finnhub_ws_url: str = "wss://ws.finnhub.io"
    finnhub_symbols: list[str] = []
    batch_interval_seconds: int = 30
    checkpoint_base: str = "/Workspace/checkpoints/financial-anomaly"
    max_records_per_batch: int = 1000
    watermark_delay: str = "2 minutes"
    landing_zone_path: str = "/mnt/streaming-landing/trades"


class HistoricalConfig(BaseModel):
    """Configuration for Alpha Vantage historical data."""

    alphavantage_api_key: str = ""
    alphavantage_base_url: str = "https://www.alphavantage.co/query"
    symbols: list[str] = []
    interval: str = "5min"
    outputsize: str = "full"
    rate_limit_sleep: int = 12
    max_calls_per_day: int = 25


class DriftConfig(BaseModel):
    """Configuration for drift detection."""

    reference_window_days: int = 30
    detection_interval_minutes: int = 60
    psi_threshold: float = 0.2
    js_divergence_threshold: float = 0.1
    performance_degradation_threshold: float = 0.05


class RetrainingConfig(BaseModel):
    """Configuration for automated retraining."""

    min_new_records: int = 5000
    cooldown_hours: int = 6
    max_retrain_per_day: int = 4


class ChampionChallengerConfig(BaseModel):
    """Configuration for champion/challenger model comparison."""

    primary_metric: str = "pr_auc"
    secondary_metrics: list[str] = ["f1_score", "precision", "recall"]
    min_improvement_threshold: float = 0.005
    require_all_metrics_improvement: bool = False


class ModelHyperparameters(BaseModel):
    """Hyperparameters for a single model."""

    # Allows arbitrary hyperparameters per model type
    model_config = {"extra": "allow"}


class ProjectConfig(BaseModel):
    """Main project configuration loaded from YAML.

    Handles feature specifications, catalog details, experiment parameters,
    streaming config, drift config, and multi-model tournament settings.
    """

    num_features: list[str]
    cat_features: list[str]
    target: str
    catalog_name: str
    schema_name: str
    parameters: dict[str, Any]
    experiment_name_basic: str | None = None
    experiment_name_custom: str | None = None
    models: dict[str, dict[str, Any]] | None = None
    champion_challenger: ChampionChallengerConfig = ChampionChallengerConfig()
    streaming: StreamingConfig = StreamingConfig()
    historical: HistoricalConfig = HistoricalConfig()
    drift: DriftConfig = DriftConfig()
    retraining: RetrainingConfig = RetrainingConfig()

    @classmethod
    def from_yaml(cls, config_path: str, env: str = "dev") -> ProjectConfig:
        """Load and parse configuration from a YAML file.

        :param config_path: Path to the YAML configuration file
        :param env: Environment name (prd, acc, or dev)
        :return: ProjectConfig instance
        """
        if env not in ["prd", "acc", "dev"]:
            raise ValueError(f"Invalid environment: {env}. Expected 'prd', 'acc', or 'dev'")

        with open(config_path) as f:
            config_dict = yaml.safe_load(f)
            config_dict["catalog_name"] = config_dict[env]["catalog_name"]
            config_dict["schema_name"] = config_dict[env]["schema_name"]

            # Parse nested configs
            if "streaming" in config_dict:
                config_dict["streaming"] = StreamingConfig(**config_dict["streaming"])
            if "historical" in config_dict:
                config_dict["historical"] = HistoricalConfig(**config_dict["historical"])
            if "drift" in config_dict:
                config_dict["drift"] = DriftConfig(**config_dict["drift"])
            if "retraining" in config_dict:
                config_dict["retraining"] = RetrainingConfig(**config_dict["retraining"])
            if "champion_challenger" in config_dict:
                config_dict["champion_challenger"] = ChampionChallengerConfig(**config_dict["champion_challenger"])

            return cls(**config_dict)


class Tags(BaseModel):
    """Model for MLflow tags."""

    git_sha: str
    branch: str
    run_id: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        """Convert the Tags instance to a dictionary."""
        tags_dict = {"git_sha": self.git_sha, "branch": self.branch}
        if self.run_id is not None:
            tags_dict["run_id"] = self.run_id
        return tags_dict
