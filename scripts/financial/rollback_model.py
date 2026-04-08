# Databricks notebook source
# MAGIC %md
# MAGIC # Emergency Model Rollback

# COMMAND ----------
import glob
import subprocess
import sys

WHEEL_GLOBS = [

	"/Volumes/*/financial_transactions/packages/financial_ai_mlops-*.whl",
]
wheel_candidates = []
for pattern in WHEEL_GLOBS:
	wheel_candidates.extend(glob.glob(pattern))
wheel_candidates = sorted(wheel_candidates, reverse=True)

if not wheel_candidates:
	raise FileNotFoundError(f"No wheel found for patterns: {WHEEL_GLOBS}")

subprocess.check_call(
	[
		sys.executable,
		"-m",
		"pip",
		"install",
		"--disable-pip-version-check",
		"--quiet",
		wheel_candidates[0],
	]
)
print(f"Installed wheel: {wheel_candidates[0]}")
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
