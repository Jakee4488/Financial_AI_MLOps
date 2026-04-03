"""LightGBM model for financial anomaly detection."""

from __future__ import annotations

import mlflow
import pandas as pd
from lightgbm import LGBMClassifier
from loguru import logger
from mlflow.models import infer_signature
from pyspark.sql import SparkSession
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score
from sklearn.pipeline import Pipeline

from financial_transactions.config import ProjectConfig, Tags
from financial_transactions.models.base_model import BaseAnomalyModel


class CatToIntTransformer(BaseEstimator, TransformerMixin):
    """Encode categorical columns as integer codes for LightGBM."""

    def __init__(self, cat_features: list[str]) -> None:
        self.cat_features = cat_features
        self.cat_maps_: dict[str, dict] = {}

    def fit(self, X: pd.DataFrame, y: pd.Series | None = None) -> "CatToIntTransformer":
        """Fit the transformer."""
        X = X.copy()
        for col in self.cat_features:
            if col in X.columns:
                c = pd.Categorical(X[col])
                self.cat_maps_[col] = dict(zip(c.categories, range(len(c.categories)), strict=False))
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Transform categorical features to integer codes."""
        X = X.copy()
        for col in self.cat_features:
            if col in X.columns:
                X[col] = X[col].map(lambda val, c=col: self.cat_maps_.get(c, {}).get(val, -1)).astype("category")
        return X


class LightGBMModel(BaseAnomalyModel):
    """LightGBM classifier for anomaly detection.

    Uses native categorical encoding and scale_pos_weight for class imbalance.
    """

    def __init__(self, config: ProjectConfig, tags: Tags, spark: SparkSession) -> None:
        super().__init__(config, tags, spark, model_type="lightgbm")
        self.params = config.models.get("lightgbm", {}) if config.models else config.parameters

    def prepare_features(self) -> None:
        """Build LightGBM pipeline with categorical encoding."""
        logger.info("[lightgbm] Preparing features...")
        cat_features_available = [f for f in self.cat_features if f in self.X_train.columns]

        preprocessor = ColumnTransformer(
            transformers=[("cat", CatToIntTransformer(cat_features_available), cat_features_available)],
            remainder="passthrough",
        )

        lgbm_params = {k: v for k, v in self.params.items() if k != "scale_pos_weight"}
        scale = self.params.get("scale_pos_weight", 1)

        self.pipeline = Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("classifier", LGBMClassifier(scale_pos_weight=scale, verbose=-1, **lgbm_params)),
            ]
        )

    def train(self) -> None:
        """Train the LightGBM model."""
        logger.info("[lightgbm] Training...")
        self.pipeline.fit(self.X_train, self.y_train)
        logger.info("[lightgbm] Training complete.")

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
        logger.info(f"[lightgbm] Metrics: {self.metrics}")
        return self.metrics

    def log_model(self) -> None:
        """Log model to MLflow."""
        mlflow.set_experiment(self.experiment_name)
        with mlflow.start_run(run_name="lightgbm-anomaly", tags=self.tags) as run:
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
        logger.info(f"[lightgbm] Model logged. Run ID: {self.run_id}")
