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
from financial_transactions.config import ProjectConfig
from financial_transactions.serving.model_serving import AnomalyModelServing
from financial_transactions.serving.ab_testing import ABTestManager

config = ProjectConfig.from_yaml("../../project_config.yml", env="dev")
client = mlflow.MlflowClient()

model_name = f"{config.catalog_name}.{config.schema_name}.anomaly_model_champion"
endpoint_name = f"anomaly-model-serving-{config.schema_name}"

# Get versions
try:
    champ_v = client.get_model_version_by_alias(model_name, "champion").version
    chall_v = client.get_model_version_by_alias(model_name, "challenger").version
except Exception as e:
    print(f"Could not find both champion and challenger aliases: {e}")
    dbutils.notebook.exit("ABORTED")

print(f"⚖️ Evaluating A/B Test: Champion (v{champ_v}) vs Challenger (v{chall_v})")

# In a real scenario, ABTestManager would query inference tables here.
# For demonstration, we compare their offline PR-AUC metrics as a proxy for the A/B metric override
champ_run_id = client.get_model_version_by_alias(model_name, "champion").run_id
chall_run_id = client.get_model_version_by_alias(model_name, "challenger").run_id

champ_auc = client.get_run(champ_run_id).data.metrics.get("pr_auc", 0)
chall_auc = client.get_run(chall_run_id).data.metrics.get("pr_auc", 0)

print(f"Champion PR-AUC: {champ_auc:.4f}")
print(f"Challenger PR-AUC: {chall_auc:.4f}")

serving = AnomalyModelServing(model_name, endpoint_name)

# Gated Deployment Logic
if chall_auc > champ_auc:
    print("✅ Challenger is better. Promoting to Champion!")
    client.set_registered_model_alias(model_name, "champion", chall_v)
    serving.promote_to_production() # Sets challenger to 100% traffic
    client.delete_registered_model_alias(model_name, "challenger")
else:
    print("❌ Challenger did not beat Champion. Rolling back.")
    serving.rollback(version=champ_v) # Restores champion to 100% traffic
    client.delete_registered_model_alias(model_name, "challenger")

print("A/B Test Concluded.")
