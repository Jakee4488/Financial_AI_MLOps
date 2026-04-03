# Databricks notebook source
# MAGIC %md
# MAGIC # Emergency Model Rollback

# COMMAND ----------
# MAGIC %pip install /Volumes/mlops_dev/financial_transactions/packages/financial_ai_mlops-latest-py3-none-any.whl --quiet
# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
from financial_transactions.config import ProjectConfig
from financial_transactions.serving.rollback_manager import RollbackManager

# COMMAND ----------
config = ProjectConfig.from_yaml("../../project_config.yml", env="dev")
rollback_version = dbutils.widgets.get("rollback_version")

# COMMAND ----------
rm = RollbackManager(config, spark)
rm.rollback_model(version=rollback_version)

# Verify
success = rm.verify_rollback(expected_version=rollback_version)
print(f"Rollback to v{rollback_version}: {'✅ SUCCESS' if success else '❌ FAILED'}")

dbutils.notebook.exit(f"rollback_v{rollback_version}_{'success' if success else 'failed'}")
