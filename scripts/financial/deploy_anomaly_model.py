# Databricks notebook source
# MAGIC %md
# MAGIC # Deploy Anomaly Model — Canary Deployment

# COMMAND ----------
# MAGIC %pip install /Volumes/mlops_dev/financial_transactions/packages/financial_ai_mlops-latest-py3-none-any.whl --quiet
# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
from financial_transactions.serving.model_serving import AnomalyModelServing

# COMMAND ----------
decision = dbutils.jobs.taskValues.get(taskKey="train_tournament", key="decision", default="REJECT")

if decision != "PROMOTE":
    print(f"Skipping deployment: decision={decision}")
    dbutils.notebook.exit("SKIPPED")

# COMMAND ----------
model_version = dbutils.jobs.taskValues.get(taskKey="train_tournament", key="model_version")
catalog = dbutils.widgets.get("catalog_name")
schema = dbutils.widgets.get("schema_name")

model_name = f"{catalog}.{schema}.anomaly_model_champion"
endpoint_name = f"anomaly-model-serving-{schema}"

serving = AnomalyModelServing(model_name, endpoint_name)

# COMMAND ----------
# Deploy canary (10% traffic)
serving.deploy_canary(version=model_version, canary_pct=10)
print(f"Canary deployed: v{model_version} at 10% traffic")

# COMMAND ----------
dbutils.notebook.exit(f"CANARY_DEPLOYED:v{model_version}")
