"""Abstract base model for the 4-model tournament.

All model implementations must extend BaseAnomalyModel and implement
the required interface for consistent tournament evaluation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from pyspark.sql import SparkSession

from financial_transactions.config import ProjectConfig, Tags


@dataclass
class ModelResult:
    """Result from a single model's training and evaluation."""

    model_name: str
    model_type: str
    metrics: dict[str, float] = field(default_factory=dict)
    model_uri: str = ""
    run_id: str = ""
    training_time_seconds: float = 0.0
    parameters: dict[str, Any] = field(default_factory=dict)


class BaseAnomalyModel(ABC):
    """Abstract base class for anomaly detection models.

    All models in the tournament must implement this interface to ensure
    consistent data loading, training, evaluation, and MLflow logging.
    """

    def __init__(
        self,
        config: ProjectConfig,
        tags: Tags,
        spark: SparkSession,
        model_type: str = "base",
    ) -> None:
        """Initialize the base model.

        :param config: Project configuration
        :param tags: MLflow tags
        :param spark: SparkSession
        :param model_type: String identifier for this model type
        """
        self.config = config
        self.spark = spark
        self.num_features = config.num_features
        self.cat_features = config.cat_features
        self.target = config.target
        self.catalog_name = config.catalog_name
        self.schema_name = config.schema_name
        self.experiment_name = config.experiment_name_basic
        self.tags = tags.to_dict()
        self.model_type = model_type
        self.model_name = f"{self.catalog_name}.{self.schema_name}.anomaly_model_{model_type}"

        # Set during load_data
        self.train_set: pd.DataFrame | None = None
        self.test_set: pd.DataFrame | None = None
        self.X_train: pd.DataFrame | None = None
        self.X_test: pd.DataFrame | None = None
        self.y_train: pd.Series | None = None
        self.y_test: pd.Series | None = None

        # Set during training/logging
        self.pipeline: Any = None
        self.run_id: str = ""
        self.model_info: Any = None
        self.metrics: dict[str, float] = {}

    def load_data(self) -> None:
        """Load training and test data from Delta tables."""
        from loguru import logger

        logger.info(f"[{self.model_type}] Loading data from catalog...")
        train_spark = self.spark.table(f"{self.catalog_name}.{self.schema_name}.train_set")
        test_spark = self.spark.table(f"{self.catalog_name}.{self.schema_name}.test_set")

        self.train_set = train_spark.toPandas()
        self.test_set = test_spark.toPandas()

        all_features = self.num_features + self.cat_features
        available_features = [f for f in all_features if f in self.train_set.columns]

        self.X_train = self.train_set[available_features]
        self.y_train = self.train_set[self.target]
        self.X_test = self.test_set[available_features]
        self.y_test = self.test_set[self.target]

        logger.info(
            f"[{self.model_type}] Data loaded: train={len(self.train_set)}, "
            f"test={len(self.test_set)}, features={len(available_features)}"
        )

    @abstractmethod
    def prepare_features(self) -> None:
        """Prepare features and build the model pipeline."""

    @abstractmethod
    def train(self) -> None:
        """Train the model."""

    @abstractmethod
    def evaluate(self) -> dict[str, float]:
        """Evaluate the model and return metrics dictionary.

        Must return at least: pr_auc, f1_score, precision, recall, accuracy
        """

    @abstractmethod
    def log_model(self) -> None:
        """Log the model to MLflow."""

    def get_model_uri(self) -> str:
        """Return the MLflow model URI."""
        return f"runs:/{self.run_id}/model"

    def to_result(self, training_time: float = 0.0) -> ModelResult:
        """Convert to a ModelResult for tournament comparison."""
        return ModelResult(
            model_name=self.model_name,
            model_type=self.model_type,
            metrics=self.metrics,
            model_uri=self.get_model_uri(),
            run_id=self.run_id,
            training_time_seconds=training_time,
            parameters=self.config.models.get(self.model_type, {}) if self.config.models else {},
        )
