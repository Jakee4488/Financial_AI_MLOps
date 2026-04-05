"""XGBoost model for financial anomaly detection."""

from __future__ import annotations

import mlflow
from loguru import logger
from mlflow.models import infer_signature
from pyspark.sql import SparkSession
from sklearn.compose import ColumnTransformer
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder
from xgboost import XGBClassifier

from financial_transactions.config import ProjectConfig, Tags
from financial_transactions.models.base_model import BaseAnomalyModel


class XGBoostModel(BaseAnomalyModel):
    """XGBoost classifier for anomaly detection.

    Uses ordinal encoding for categoricals and scale_pos_weight for class imbalance.
    Optimizes for PR-AUC using eval_metric='aucpr'.
    """

    def __init__(self, config: ProjectConfig, tags: Tags, spark: SparkSession) -> None:
        super().__init__(config, tags, spark, model_type="xgboost")
        self.params = config.models.get("xgboost", {}) if config.models else {}

    def prepare_features(self) -> None:
        """Build XGBoost pipeline with ordinal encoding."""
        logger.info("[xgboost] Preparing features...")
        cat_features_available = [f for f in self.cat_features if f in self.X_train.columns]

        preprocessor = ColumnTransformer(
            transformers=[
                ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), cat_features_available),
            ],
            remainder="passthrough",
        )

        xgb_params = {k: v for k, v in self.params.items()}
        scale = xgb_params.pop("scale_pos_weight", 1)
        eval_metric = xgb_params.pop("eval_metric", "aucpr")

        self.pipeline = Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                (
                    "classifier",
                    XGBClassifier(
                        scale_pos_weight=scale,
                        eval_metric=eval_metric,
                        use_label_encoder=False,
                        verbosity=0,
                        **xgb_params,
                    ),
                ),
            ]
        )

    def train(self) -> None:
        """Train the XGBoost model."""
        logger.info("[xgboost] Training...")
        self.pipeline.fit(self.X_train, self.y_train)
        logger.info("[xgboost] Training complete.")

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
        logger.info(f"[xgboost] Metrics: {self.metrics}")
        return self.metrics

    def log_model(self) -> None:
        """Log model to MLflow."""
        mlflow.set_experiment(self.experiment_name)
        with mlflow.start_run(run_name="xgboost-anomaly", tags=self.tags) as run:
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
        logger.info(f"[xgboost] Model logged. Run ID: {self.run_id}")
