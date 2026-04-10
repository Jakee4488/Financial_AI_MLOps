# Databricks notebook source
# MAGIC %md
# MAGIC # Drift Detection & Retraining Trigger

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
from datetime import UTC, datetime, timedelta

from financial_transactions.config import ProjectConfig
from financial_transactions.monitoring.alerting import AlertManager
from financial_transactions.monitoring.drift_detector import DriftDetector
from financial_transactions.monitoring.retraining_trigger import RetrainingTrigger

# COMMAND ----------
config = ProjectConfig.from_yaml("../../project_config.yml", env="dev")

# COMMAND ----------
# Load reference and current data
reference_end = datetime.now(tz=UTC) - timedelta(days=1)
reference_start = reference_end - timedelta(days=config.drift.reference_window_days)

feature_table = f"{config.catalog_name}.{config.schema_name}.trade_features"

reference_df = (
    spark.table(feature_table)
    .filter((spark.col("timestamp") >= reference_start) & (spark.col("timestamp") <= reference_end))
    .toPandas()
)

current_df = spark.table(feature_table).filter(spark.col("timestamp") > reference_end).toPandas()

print(f"Reference: {len(reference_df)} rows, Current: {len(current_df)} rows")

# COMMAND ----------
# Detect drift
detector = DriftDetector(config.drift, spark)
drift_report = detector.detect_data_drift(
    reference_df,
    current_df,
    numerical_features=config.num_features,
    categorical_features=config.cat_features,
)

detector.write_drift_metrics(
    drift_report,
    table_name=f"{config.catalog_name}.{config.schema_name}.drift_monitoring",
)

# COMMAND ----------
# Evaluate retraining trigger
trigger = RetrainingTrigger(config.retraining, spark)
should_retrain = trigger.evaluate_trigger_conditions(
    drift_report=drift_report,
    new_record_count=len(current_df),
)

# COMMAND ----------
if should_retrain:
    alerter = AlertManager(spark=spark)
    alerter.send_retraining_notification(
        reason="Drift detected" if drift_report.get("overall_drift") else "Sufficient new data",
    )
    print("🔄 Retraining triggered")
else:
    print("✅ No retraining needed")

dbutils.notebook.exit(str(should_retrain))
