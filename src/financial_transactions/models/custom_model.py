"""Custom MLflow PyFunc model wrapper for serving.

Wraps the winning model for deployment to Databricks Model Serving,
returning anomaly probability, binary prediction, and risk score.
"""

from __future__ import annotations

from datetime import datetime

import mlflow
import numpy as np
import pandas as pd
from mlflow import MlflowClient
from mlflow.models import infer_signature
from mlflow.pyfunc import PythonModelContext
from mlflow.utils.environment import _mlflow_conda_env

from financial_transactions.config import Tags


def classify_risk(probability: float) -> str:
    """Classify risk level from anomaly probability."""
    if probability >= 0.8:
        return "critical"
    elif probability >= 0.5:
        return "high"
    elif probability >= 0.2:
        return "medium"
    return "low"


class AnomalyModelWrapper(mlflow.pyfunc.PythonModel):
    """PyFunc wrapper for the anomaly detection model.

    Returns structured output with anomaly probability,
    binary prediction, and risk classification.
    """

    def load_context(self, context: PythonModelContext) -> None:
        """Load the underlying sklearn pipeline."""
        self.model = mlflow.sklearn.load_model(context.artifacts["anomaly-pipeline"])

    def predict(self, context: PythonModelContext, model_input: pd.DataFrame | np.ndarray) -> dict:
        """Predict with enriched output.

        :param context: MLflow model context
        :param model_input: Input features
        :return: Dictionary with predictions, probabilities, and risk levels
        """
        predictions = self.model.predict(model_input)

        # Get probabilities if available
        if hasattr(self.model, "predict_proba"):
            probabilities = self.model.predict_proba(model_input)[:, 1].tolist()
        elif hasattr(self.model, "decision_function"):
            from scipy.special import expit

            raw_scores = self.model.decision_function(model_input)
            probabilities = expit(-raw_scores * 2).tolist()
        else:
            probabilities = predictions.tolist()

        risk_levels = [classify_risk(p) for p in probabilities]

        return {
            "prediction": ["anomaly" if p == 1 else "normal" for p in predictions],
            "probability": probabilities,
            "risk_level": risk_levels,
        }

    def log_register_model(
        self,
        wrapped_model_uri: str,
        pyfunc_model_name: str,
        experiment_name: str,
        tags: Tags,
        code_paths: list[str],
        input_example: pd.DataFrame,
    ) -> str:
        """Log and register the wrapped model.

        :param wrapped_model_uri: URI of the underlying model
        :param pyfunc_model_name: Unity Catalog model name
        :param experiment_name: MLflow experiment name
        :param tags: MLflow tags
        :param code_paths: Paths to wheel files
        :param input_example: Input example for signature
        :return: Registered model version
        """
        mlflow.set_experiment(experiment_name=experiment_name)
        with mlflow.start_run(
            run_name=f"wrapper-anomaly-{datetime.now().strftime('%Y-%m-%d')}",
            tags=tags.to_dict(),
        ):
            additional_pip_deps = []
            for package in code_paths:
                whl_name = package.split("/")[-1]
                additional_pip_deps.append(f"code/{whl_name}")
            conda_env = _mlflow_conda_env(additional_pip_deps=additional_pip_deps)

            signature = infer_signature(
                model_input=input_example,
                model_output={"prediction": ["normal"], "probability": [0.1], "risk_level": ["low"]},
            )
            model_info = mlflow.pyfunc.log_model(
                python_model=self,
                name="pyfunc-wrapper",
                artifacts={"anomaly-pipeline": wrapped_model_uri},
                signature=signature,
                code_paths=code_paths,
                conda_env=conda_env,
            )

        client = MlflowClient()
        registered_model = mlflow.register_model(
            model_uri=model_info.model_uri,
            name=pyfunc_model_name,
            tags=tags.to_dict(),
        )
        latest_version = registered_model.version
        client.set_registered_model_alias(
            name=pyfunc_model_name,
            alias="latest-model",
            version=latest_version,
        )
        return str(latest_version)
