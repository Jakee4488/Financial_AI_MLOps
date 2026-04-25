"""4-Model Tournament orchestrator.

Trains all 4 models (LightGBM, XGBoost, Random Forest, Isolation Forest),
evaluates each, ranks by primary metric (PR-AUC), and selects the best
as the "challenger" for the champion/challenger gate.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import pandas as pd
from loguru import logger
from pyspark.sql import SparkSession

from financial_transactions.config import ProjectConfig, Tags
from financial_transactions.models.base_model import BaseAnomalyModel, ModelResult
from financial_transactions.models.isolation_forest_model import IsolationForestModel
from financial_transactions.models.lightgbm_model import LightGBMModel
from financial_transactions.models.random_forest_model import RandomForestModel
from financial_transactions.models.xgboost_model import XGBoostModel


@dataclass
class TournamentResult:
    """Result from a complete model tournament."""

    challenger: ModelResult
    all_results: list[ModelResult]
    comparison_table: pd.DataFrame
    tournament_time_seconds: float = 0.0


class ModelTournament:
    """Orchestrate the 4-model training tournament.

    Trains LightGBM, XGBoost, Random Forest, and Isolation Forest,
    evaluates each on the same test set, and ranks by primary metric.

    Usage:
        tournament = ModelTournament(config, tags, spark)
        result = tournament.run_tournament()
        print(result.challenger.model_type)  # Best model
        print(result.comparison_table)       # All metrics side-by-side
    """

    MODEL_CLASSES: list[type[BaseAnomalyModel]] = [
        LightGBMModel,
        XGBoostModel,
        RandomForestModel,
        IsolationForestModel,
    ]

    def __init__(self, config: ProjectConfig, tags: Tags, spark: SparkSession) -> None:
        """Initialize the tournament.

        :param config: Project configuration with model hyperparameters
        :param tags: MLflow tags
        :param spark: SparkSession
        """
        self.config = config
        self.tags = tags
        self.spark = spark
        self.primary_metric = config.champion_challenger.primary_metric

    def run_tournament(self, model_classes: list[type[BaseAnomalyModel]] | None = None) -> TournamentResult:
        """Run the tournament on specified models, or all if none provided.

        :param model_classes: List of model classes to train. Defaults to all 4.
        :return: TournamentResult with challenger (best model) and all results
        """
        if model_classes is None:
            model_classes = self.MODEL_CLASSES

        logger.info("=" * 60)
        logger.info(f"🏆 Starting Tournament with {len(model_classes)} models")
        logger.info("=" * 60)

        tournament_start = time.time()
        results: list[ModelResult] = []

        for model_class in model_classes:
            model_name = model_class.__name__
            logger.info(f"\n--- Training {model_name} ---")

            try:
                model = model_class(self.config, self.tags, self.spark)
                start = time.time()

                model.load_data()
                model.prepare_features()
                model.train()
                metrics = model.evaluate()
                model.log_model()

                elapsed = time.time() - start
                result = model.to_result(training_time=elapsed)
                results.append(result)

                logger.info(
                    f"✅ {model_name}: {self.primary_metric}={metrics.get(self.primary_metric, 0):.4f} ({elapsed:.1f}s)"
                )

            except Exception:
                logger.exception(f"❌ {model_name} failed during tournament")
                results.append(
                    ModelResult(
                        model_name=model_name,
                        model_type=model_name,
                        metrics={self.primary_metric: 0.0},
                    )
                )

        # Rank by primary metric (descending)
        results.sort(key=lambda r: r.metrics.get(self.primary_metric, 0), reverse=True)

        # Build comparison table
        comparison_table = self._build_comparison_table(results)

        tournament_time = time.time() - tournament_start

        logger.info("\n" + "=" * 60)
        logger.info("🏆 Tournament Results:")
        logger.info(f"\n{comparison_table.to_string()}")
        logger.info(
            f"\n🥇 Winner: {results[0].model_type} "
            f"({self.primary_metric}={results[0].metrics.get(self.primary_metric, 0):.4f})"
        )
        logger.info(f"⏱️ Total tournament time: {tournament_time:.1f}s")
        logger.info("=" * 60)

        return TournamentResult(
            challenger=results[0],
            all_results=results,
            comparison_table=comparison_table,
            tournament_time_seconds=tournament_time,
        )

    @staticmethod
    def _build_comparison_table(results: list[ModelResult]) -> pd.DataFrame:
        """Build a comparison table of all model metrics.

        :param results: List of ModelResult from each model
        :return: DataFrame with models as rows and metrics as columns
        """
        rows = []
        for r in results:
            row = {"model_type": r.model_type, "run_id": r.run_id[:8] if r.run_id else "N/A"}
            row.update(r.metrics)
            row["training_time_s"] = round(r.training_time_seconds, 1)
            rows.append(row)

        df = pd.DataFrame(rows)
        if "pr_auc" in df.columns:
            df = df.sort_values("pr_auc", ascending=False)
        return df.reset_index(drop=True)

    def log_tournament_results(self, result: TournamentResult) -> None:
        """Log full tournament results to MLflow as an artifact.

        :param result: TournamentResult to log
        """
        import json
        import tempfile

        import mlflow

        mlflow.set_experiment(self.config.experiment_name_basic)
        with mlflow.start_run(run_name="tournament-summary", tags=self.tags.to_dict()):
            # Log winner metrics
            mlflow.log_metrics({f"winner_{k}": v for k, v in result.challenger.metrics.items()})
            mlflow.log_param("winner_model_type", result.challenger.model_type)
            mlflow.log_metric("tournament_time_seconds", result.tournament_time_seconds)
            mlflow.log_metric("num_models", len(result.all_results))

            # Log comparison table as artifact
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                tournament_data = {
                    "winner": result.challenger.model_type,
                    "results": [
                        {"model": r.model_type, "metrics": r.metrics, "run_id": r.run_id} for r in result.all_results
                    ],
                }
                json.dump(tournament_data, f, indent=2)
                mlflow.log_artifact(f.name, "tournament")

            # Log comparison table as CSV
            with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
                result.comparison_table.to_csv(f.name, index=False)
                mlflow.log_artifact(f.name, "tournament")

        logger.info("Tournament results logged to MLflow")
