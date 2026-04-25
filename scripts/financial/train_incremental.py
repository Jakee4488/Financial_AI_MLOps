# Databricks notebook source
import json
import sys
import glob
import subprocess
import mlflow

WHEEL_GLOBS = ["/Volumes/*/financial_transactions/packages/financial_ai_mlops-*.whl"]
wheel_candidates = sorted([w for p in WHEEL_GLOBS for w in glob.glob(p)], reverse=True)
if wheel_candidates:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--quiet", wheel_candidates[0]])

dbutils.library.restartPython()

# COMMAND ----------
from financial_transactions.config import ProjectConfig, Tags
from financial_transactions.models.model_tournament import ModelTournament
from financial_transactions.serving.model_serving import AnomalyModelServing
from financial_transactions.models.lightgbm_model import LightGBMModel
from financial_transactions.models.xgboost_model import XGBoostModel
from financial_transactions.models.random_forest_model import RandomForestModel
from financial_transactions.models.isolation_forest_model import IsolationForestModel

# Map names to classes
MODEL_MAP = {
    "LightGBMModel": LightGBMModel,
    "XGBoostModel": XGBoostModel,
    "RandomForestModel": RandomForestModel,
    "IsolationForestModel": IsolationForestModel
}

config = ProjectConfig.from_yaml("../../project_config.yml", env="dev")
tags = Tags(git_sha=dbutils.widgets.get("git_sha", "dev"), branch=dbutils.widgets.get("branch", "main"))

# 1. Find Top 2 architectures from previous runs
client = mlflow.MlflowClient()
experiment = client.get_experiment_by_name(config.experiment_name)
if experiment:
    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by=[f"metrics.{config.champion_challenger.primary_metric} DESC"],
        max_results=20
    )
    # Get top 2 unique architectures
    seen_archs = []
    for r in runs:
        arch = r.data.tags.get("model_type")
        if arch and arch in MODEL_MAP and arch not in seen_archs:
            seen_archs.append(arch)
            if len(seen_archs) == 2:
                break
    top_2_classes = [MODEL_MAP[a] for a in seen_archs]
else:
    top_2_classes = [LightGBMModel, XGBoostModel]

if not top_2_classes:
    top_2_classes = [LightGBMModel, XGBoostModel]

print(f"🔄 Incremental Retraining Top 2 Architectures: {[c.__name__ for c in top_2_classes]}")

# 2. Train only these 2 models
tournament = ModelTournament(config, tags, spark)
result = tournament.run_tournament(model_classes=top_2_classes)
tournament.log_tournament_results(result)

# 3. Register winner as Challenger
model_name = f"{config.catalog_name}.{config.schema_name}.anomaly_model_champion"
model_version = client.create_model_version(
    name=model_name,
    source=result.challenger.model_uri,
    run_id=result.challenger.run_id
)
client.set_registered_model_alias(model_name, "challenger", model_version.version)
print(f"✅ Registered as Challenger v{model_version.version}")

# 4. Deploy Challenger as Canary (A/B Test)
endpoint_name = f"anomaly-model-serving-{config.schema_name}"
serving = AnomalyModelServing(model_name, endpoint_name)
serving.deploy_canary(version=model_version.version, canary_pct=50) # 50/50 A/B split
print(f"⚖️ Deployed Challenger v{model_version.version} to 50% canary traffic for A/B testing.")
