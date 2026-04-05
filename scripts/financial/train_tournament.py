# Databricks notebook source
# MAGIC %md
# MAGIC # 4-Model Tournament Training
# MAGIC
# MAGIC Trains LightGBM, XGBoost, Random Forest, and Isolation Forest,
# MAGIC selects the best performer, and runs champion/challenger gate.

# COMMAND ----------
# MAGIC %pip install /Volumes/mlops_dev/financial_transactions/packages/financial_ai_mlops-latest-py3-none-any.whl --quiet

# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
import json

from financial_transactions.config import ProjectConfig, Tags
from financial_transactions.models.champion_challenger import ChampionChallenger
from financial_transactions.models.model_tournament import ModelTournament
from financial_transactions.models.model_validator import ModelValidator

# COMMAND ----------
# Load configuration
config = ProjectConfig.from_yaml("../../project_config.yml", env="dev")
tags = Tags(
    git_sha=dbutils.widgets.get("git_sha"),
    branch=dbutils.widgets.get("branch"),
)

# COMMAND ----------
# Run 4-model tournament
tournament = ModelTournament(config, tags, spark)
result = tournament.run_tournament()

# Log tournament results to MLflow
tournament.log_tournament_results(result)

print(f"\n🏆 Tournament Winner: {result.challenger.model_type}")
print(f"   PR-AUC: {result.challenger.metrics.get('pr_auc', 0):.4f}")
print(f"   Total time: {result.tournament_time_seconds:.1f}s")

# COMMAND ----------
# Validate the winner
validator = ModelValidator(min_pr_auc=0.5, min_f1=0.3)
validation = validator.validate(result.challenger)

if not validation.passed:
    dbutils.notebook.exit(
        json.dumps(
            {
                "status": "VALIDATION_FAILED",
                "details": validation.details,
            }
        )
    )

# COMMAND ----------
# Champion/Challenger comparison
gate = ChampionChallenger(config, spark)
comparison = gate.compare(result.challenger)

# Log comparison
gate.log_comparison(comparison)
gate.write_audit_record(comparison, result.challenger)

print(f"\n⚔️ Decision: {comparison.decision}")
print(f"   Reason: {comparison.reason}")

# COMMAND ----------
# Promote if approved
if comparison.decision == "PROMOTE":
    version = gate.promote_challenger(result.challenger)
    print(f"✅ Promoted to champion v{version}")

    dbutils.jobs.taskValues.set(key="model_version", value=version)
    dbutils.jobs.taskValues.set(key="model_uri", value=result.challenger.model_uri)
    dbutils.jobs.taskValues.set(key="decision", value="PROMOTE")
else:
    print(f"❌ Challenger rejected: {comparison.reason}")
    dbutils.jobs.taskValues.set(key="decision", value="REJECT")

# COMMAND ----------
# Output summary
dbutils.notebook.exit(
    json.dumps(
        {
            "status": comparison.decision,
            "winner": result.challenger.model_type,
            "metrics": result.challenger.metrics,
            "comparison_table": result.comparison_table.to_dict(),
        }
    )
)
