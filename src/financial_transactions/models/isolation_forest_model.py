"""Isolation Forest model for financial anomaly detection.

Unsupervised anomaly detection — no labels needed. Anomaly scores
are calibrated to [0, 1] for fair comparison with supervised models.
"""

from __future__ import annotations

import mlflow
import numpy as np
from loguru import logger
from mlflow.models import infer_signature
from pyspark.sql import SparkSession
from scipy.special import expit
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

from financial_transactions.config import ProjectConfig, Tags
from financial_transactions.models.base_model import BaseAnomalyModel


class IsolationForestModel(BaseAnomalyModel):
    """Isolation Forest for unsupervised anomaly detection.

    Detects anomalies purely from feature distributions without labels.
    Anomaly scores are calibrated via sigmoid transformation for fair
    comparison with supervised models in the tournament.
    """

    def __init__(self, config: ProjectConfig, tags: Tags, spark: SparkSession) -> None:
        super().__init__(config, tags, spark, model_type="isolation_forest")
        self.params = config.models.get("isolation_forest", {}) if config.models else {}
        self._threshold: float = 0.0

    def prepare_features(self) -> None:
        """Build Isolation Forest pipeline (numerical features only)."""
        logger.info("[isolation_forest] Preparing features...")

        # Isolation Forest works best with numerical features
        cat_features_available = [f for f in self.cat_features if f in self.X_train.columns]

        preprocessor = ColumnTransformer(
            transformers=[
                ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), cat_features_available),
            ],
            remainder="passthrough",
        )

        iso_params = {k: v for k, v in self.params.items()}

        self.pipeline = Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("detector", IsolationForest(**iso_params)),
            ]
        )

    def train(self) -> None:
        """Train the Isolation Forest model."""
        logger.info("[isolation_forest] Training (unsupervised)...")
        self.pipeline.fit(self.X_train)

        # Compute threshold on training data using known contamination rate
        scores = self._get_anomaly_scores(self.X_train)
        contamination = self.params.get("contamination", 0.015)
        self._threshold = float(np.percentile(scores, (1 - contamination) * 100))

        logger.info(f"[isolation_forest] Training complete. Threshold: {self._threshold:.4f}")

    def _get_anomaly_scores(self, X: np.ndarray | object) -> np.ndarray:
        """Get calibrated anomaly scores (0 = normal, 1 = anomalous).

        Uses sigmoid transformation of the negative decision function
        to map raw scores to [0, 1] probabilities.
        """
        # decision_function: lower = more anomalous
        raw_scores = self.pipeline.decision_function(X)
        # Negate so higher = more anomalous, then apply sigmoid
        calibrated = expit(-raw_scores * 2)  # Scale factor for better separation
        return calibrated

    def evaluate(self) -> dict[str, float]:
        """Evaluate model using calibrated anomaly scores against ground truth."""
        scores = self._get_anomaly_scores(self.X_test)
        y_pred = (scores >= self._threshold).astype(int)

        self.metrics = {
            "pr_auc": float(average_precision_score(self.y_test, scores)),
            "f1_score": float(f1_score(self.y_test, y_pred, zero_division=0)),
            "precision": float(precision_score(self.y_test, y_pred, zero_division=0)),
            "recall": float(recall_score(self.y_test, y_pred, zero_division=0)),
            "accuracy": float((y_pred == self.y_test).mean()),
        }
        logger.info(f"[isolation_forest] Metrics: {self.metrics}")
        return self.metrics

    def log_model(self) -> None:
        """Log model to MLflow."""
        mlflow.set_experiment(self.experiment_name)
        with mlflow.start_run(run_name="iforest-anomaly", tags=self.tags) as run:
            self.run_id = run.info.run_id
            mlflow.log_params(self.params)
            mlflow.log_param("calibration_threshold", self._threshold)
            mlflow.log_metrics(self.metrics)

            # Log as sklearn model (IsolationForest supports predict)
            signature = infer_signature(self.X_train, self.pipeline.predict(self.X_train))
            self.model_info = mlflow.sklearn.log_model(
                sk_model=self.pipeline,
                artifact_path="model",
                signature=signature,
                input_example=self.X_test[:1],
            )
        logger.info(f"[isolation_forest] Model logged. Run ID: {self.run_id}")
