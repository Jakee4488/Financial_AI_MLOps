# Databricks notebook source
import json
import sys
import glob
import subprocess

WHEEL_GLOBS = ["/Volumes/*/financial_transactions/packages/financial_ai_mlops-*.whl"]
wheel_candidates = sorted([w for p in WHEEL_GLOBS for w in glob.glob(p)], reverse=True)
if wheel_candidates:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--quiet", wheel_candidates[0]])

dbutils.library.restartPython()

# COMMAND ----------
from financial_transactions.config import ProjectConfig, Tags
from financial_transactions.models.model_tournament import ModelTournament
from financial_transactions.serving.model_serving import AnomalyModelServing

config = ProjectConfig.from_yaml("../../project_config.yml", env="dev")
tags = Tags(git_sha=dbutils.widgets.get("git_sha", "dev"), branch=dbutils.widgets.get("branch", "main"))

# 1. Run Full Tournament
tournament = ModelTournament(config, tags, spark)
result = tournament.run_tournament()
tournament.log_tournament_results(result)

print(f"🥇 Discovery Winner: {result.challenger.model_type} (PR-AUC: {result.challenger.metrics.get('pr_auc', 0):.4f})")

# 2. Register as Champion directly
import mlflow
client = mlflow.MlflowClient()
model_name = f"{config.catalog_name}.{config.schema_name}.anomaly_model_champion"

try:
    client.create_registered_model(model_name)
except Exception:
    pass

model_version = client.create_model_version(
    name=model_name,
    source=result.challenger.model_uri,
    run_id=result.challenger.run_id
)
client.set_registered_model_alias(model_name, "champion", model_version.version)
print(f"✅ Registered as Champion v{model_version.version}")

# 3. Deploy to Production immediately (Discovery Mode)
endpoint_name = f"anomaly-model-serving-{config.schema_name}"
serving = AnomalyModelServing(model_name, endpoint_name)
serving.deploy_or_update(version=model_version.version)
print(f"🚀 Deployed to 100% traffic on endpoint {endpoint_name}")
