# Comprehensive MLOps Setup Guide

This guide provides an end-to-end setup for:
- initializing ingestion and Delta Live Tables (DLT) pipelines,
- evaluating and selecting the best model,
- deploying the champion model to streaming inference,
- implementing automated weekly retraining.

It is written for this repository's Databricks Asset Bundles (DAB) layout.

---

## 1) Architecture and Objectives

Target workflow:
1. **Ingest market data** into Bronze.
2. **Transform** Bronze -> Silver -> Gold features in DLT.
3. **Train multiple candidate models** (tournament).
4. **Select and promote champion** in MLflow Model Registry.
5. **Score streaming data** with the champion model.
6. **Retrain weekly** (plus drift-triggered retraining if needed).

Core bundle resources:
- `resources/streaming_pipeline.yml` -> `financial_streaming_pipeline`
- `resources/retraining_workflow.yml` -> `financial_retraining_workflow`
- `resources/drift_monitoring.yml` -> `drift_monitoring_job`

---

## 2) Prerequisites

### 2.1 Local + CLI

```powershell
.venv\Scripts\Activate.ps1
uv pip install -e ".[dev,test,streaming]"
databricks auth login
databricks bundle validate -t dev
```

### 2.2 Unity Catalog infrastructure

Run once (as principal with `CREATE CATALOG` permission):
- `setup_uc_infrastructure.sql`

This script provisions:
- `mlops_dev|acc|prd` catalogs
- `financial_transactions` schema in each catalog
- volumes:
  - `packages`
  - `streaming_landing`

### 2.3 Required privileges for pipeline/job principal

Grant on each environment (`dev`, `acc`, `prd`):
- `USE CATALOG`
- `USE SCHEMA`
- `CREATE TABLE`
- `SELECT`, `MODIFY` (recommended)
- `READ_VOLUME` on `streaming_landing`
- `WRITE_VOLUME` on `streaming_landing` (for data writers)

---

## 3) Initialize Data Ingestion

The DLT Bronze source path is configured as:
- `dbfs:/Volumes/<catalog>/<schema>/streaming_landing/trades`

Create the expected landing subfolder and upload sample files (dev):

```sql
-- Run in Databricks SQL
LIST 'dbfs:/Volumes/mlops_dev/financial_transactions/streaming_landing/';
```

If `trades/` is missing, create it by uploading at least one JSON file to:
- `dbfs:/Volumes/mlops_dev/financial_transactions/streaming_landing/trades/`

Expected JSON schema fields:
- `trade_id` (string)
- `symbol` (string)
- `price` (double)
- `volume` (double)
- `timestamp` (timestamp-compatible)
- `exchange` (string)

---

## 4) Deploy and Run DLT Pipeline

```powershell
databricks bundle deploy -t dev
databricks bundle run financial_streaming_pipeline -t dev
```

Validate medallion outputs:

```sql
SHOW TABLES IN mlops_dev.financial_transactions;

SELECT COUNT(*) AS bronze_count FROM mlops_dev.financial_transactions.bronze_trades;
SELECT COUNT(*) AS silver_count FROM mlops_dev.financial_transactions.silver_trades;
SELECT COUNT(*) AS gold_count   FROM mlops_dev.financial_transactions.gold_trade_features;
```

### Important migration note

If you changed Gold dataset semantics (streaming table -> materialized view style), you may need:

```sql
DROP TABLE IF EXISTS mlops_dev.financial_transactions.gold_trade_features;
```

Then rerun the pipeline.

---

## 5) Train, Evaluate, and Select Best Model

Run tournament + deployment workflow:

```powershell
databricks bundle run financial_retraining_workflow -t dev
```

This executes:
1. `train_tournament.py`
2. `deploy_anomaly_model.py`

### Evaluation strategy (recommended)

Use these criteria in order:
1. **Primary metric**: `pr_auc` (best for anomaly class imbalance).
2. **Secondary metrics**: `f1_score`, `precision`, `recall`.
3. **Promotion threshold**: challenger must beat champion by configured minimum delta.
4. **Stability checks**: compare train/validation gap and recent batch behavior.

### Selection checklist

Promote only if all are true:
- challenger improves `pr_auc` beyond threshold,
- no critical regression in secondary metrics,
- artifacts/params/metrics are fully logged in MLflow,
- model passes smoke inference test on recent Gold data.

---

## 6) Deploy Champion to Streaming Inference

Model deployment is handled by `deploy_anomaly_model.py` in the retraining workflow.

Operationally:
1. Champion alias is updated in Model Registry.
2. Streaming inference path reads champion version.
3. New data in Gold is scored with active champion.

Post-deploy validations:
- champion alias points to expected model version,
- inference endpoint/job can load model artifacts,
- anomaly outputs are produced for fresh records,
- rollback path is tested (`rollback_model.py`).

---

## 7) Weekly Automated Retraining

Current retraining schedule in `resources/retraining_workflow.yml` is daily:
- `0 0 0 * * ?`

To run weekly (example: Monday 02:00 UTC), change to:

```yaml
schedule:
  quartz_cron_expression: "0 0 2 ? * MON *"
  timezone_id: UTC
  pause_status: ${var.schedule_pause_status}
```

Then deploy:

```powershell
databricks bundle deploy -t dev
```

For production:
- set `schedule_pause_status` to `UNPAUSED` in `prd`,
- keep `dev` and `acc` paused unless testing schedule behavior.

---

## 8) Drift + Weekly Retraining Strategy (Recommended)

Use hybrid automation:
1. **Baseline cadence**: weekly retraining job.
2. **Drift monitor** (`drift_monitoring_job`) runs every 30 minutes.
3. **Escalation policy**:
   - if drift exceeds threshold, trigger retraining immediately,
   - else wait for next weekly cycle.

This balances model freshness and compute cost.

---

## 9) Promotion Flow Across Environments

Recommended promotion path:
1. `dev`: iterate quickly, fix pipeline/model issues.
2. `acc`: run full regression and acceptance checks.
3. `prd`: promote only validated bundle revision and model.

Commands:

```powershell
databricks bundle deploy -t acc
databricks bundle run financial_streaming_pipeline -t acc
databricks bundle run financial_retraining_workflow -t acc

databricks bundle deploy -t prd
databricks bundle run financial_streaming_pipeline -t prd
```

---

## 10) Operational Guardrails

- Do not manually create DLT target tables; let DLT own them.
- Run preflight table-name conflict checks from `setup_uc_infrastructure.sql`.
- Keep schema and source path stable across environments.
- Log all model metadata and git SHA for traceability.
- Test rollback after every champion promotion.

---

## 11) Go-Live Readiness Checklist

- UC infra exists in dev/acc/prd.
- Landing volume path exists and receives data.
- DLT run succeeds end-to-end (Bronze/Silver/Gold).
- Tournament run completes and champion is promoted.
- Streaming inference validates on fresh data.
- Weekly retraining schedule is configured and unpaused in target env.
- Drift monitor is active and alerting thresholds are validated.
