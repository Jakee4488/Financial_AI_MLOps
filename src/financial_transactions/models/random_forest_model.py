"""Random Forest model for financial anomaly detection."""

from __future__ import annotations

import mlflow
from loguru import logger
from mlflow.models import infer_signature
from pyspark.sql import SparkSession
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

from financial_transactions.config import ProjectConfig, Tags
from financial_transactions.models.base_model import BaseAnomalyModel


class RandomForestModel(BaseAnomalyModel):
    """Random Forest classifier for anomaly detection.

    Uses class_weight='balanced' for class imbalance handling.
    Serves as a robust tree-based baseline for comparison.
    """

    def __init__(self, config: ProjectConfig, tags: Tags, spark: SparkSession) -> None:
        super().__init__(config, tags, spark, model_type="random_forest")
        self.params = config.models.get("random_forest", {}) if config.models else {}

    def prepare_features(self) -> None:
        """Build Random Forest pipeline with ordinal encoding."""
        logger.info("[random_forest] Preparing features...")
        cat_features_available = [f for f in self.cat_features if f in self.X_train.columns]

        preprocessor = ColumnTransformer(
            transformers=[
                ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), cat_features_available),
            ],
            remainder="passthrough",
        )

        rf_params = dict(self.params.items())
        class_weight = rf_params.pop("class_weight", "balanced")

        self.pipeline = Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                (
                    "classifier",
                    RandomForestClassifier(
                        class_weight=class_weight,
                        random_state=42,
                        n_jobs=-1,
                        **rf_params,
                    ),
                ),
            ]
        )

    def train(self) -> None:
        """Train the Random Forest model."""
        logger.info("[random_forest] Training...")
        self.pipeline.fit(self.X_train, self.y_train)
        logger.info("[random_forest] Training complete.")

    def evaluate(self) -> dict[str, float]:
        """Evaluate model performance."""
        y_pred = self.pipeline.predict(self.X_test)
        y_prob = self.pipeline.predict_proba(self.X_test)[:, 1]

        self.metrics = {
            "pr_auc": float(average_precision_score(self.y_test, y_prob)),
            "f1_score": float(f1_score(self.y_test, y_pred, zero_division=0)),
            "precision": float(precision_score(self.y_test, y_pred, zero_division=0)),
            "recall": float(recall_score(self.y_test, y_pred, zero_division=0)),
            "accuracy": float((y_pred == self.y_test).mean()),
        }
        logger.info(f"[random_forest] Metrics: {self.metrics}")
        return self.metrics

    def log_model(self) -> None:
        """Log model to MLflow."""
        mlflow.set_experiment(self.experiment_name)
        with mlflow.start_run(run_name="rf-anomaly", tags=self.tags) as run:
            self.run_id = run.info.run_id
            mlflow.log_params(self.params)
            mlflow.log_metrics(self.metrics)

            signature = infer_signature(self.X_train, self.pipeline.predict(self.X_train))
            self.model_info = mlflow.sklearn.log_model(
                sk_model=self.pipeline,
                artifact_path="model",
                signature=signature,
                input_example=self.X_test[:1],
            )
        logger.info(f"[random_forest] Model logged. Run ID: {self.run_id}")
