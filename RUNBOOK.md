# Financial AI MLOps - Walkthrough & Runbook

This document serves as a complete architectural walkthrough and operational runbook for the Enterprise Financial Market Anomaly Detection MLOps system.

## 1. Repository Walkthrough

### System Overview
This project is an enterprise-grade streaming MLOps application built on Databricks. It consumes live financial market data (via Finnhub WebSockets and Alpha Vantage), passes it through a Medallion architecture (Bronze, Silver, Gold), trains models to detect anomalies using a multi-model tournament, and alerts via a customized dashboard.

### Core Architecture & Technologies
- **Compute & Orchestration:** Databricks, Databricks Asset Bundles (DABs), Delta Live Tables (DLT)
- **Machine Learning:** MLflow (Tracking & Registry), multi-model tournament (LightGBM, XGBoost, Random Forest, Isolation Forest). 
- **Data Engineering:** PySpark, Delta Lake.
- **Monitoring & Drift:** Evidently AI
- **Streaming:** Finnhub Websocket, Alpha Vantage REST.

### Directory Structure
```text
.
├── dashboard/               # HTML/JS/CSS frontend for viewing anomalies
├── project_config.yml       # Centralized hyperparameters, feature lists, and thresholds
├── databricks.yml           # Databricks Asset Bundles (DABs) configurations
├── pyproject.toml           # Python dependencies and build system
├── resources/               # YAML definitions for Databricks infrastructure
│   ├── drift_monitoring.yml # Scheduled drift detection job
│   ├── retraining_workflow.yml# Retraining & multi-model tournament pipeline
│   └── streaming_pipeline.yml# DLT pipeline definition
├── scripts/                 # Entry level scripts / Notebook tasks run by Databricks Jobs
│   ├── financial/
│   │   ├── collect_finnhub_stream.py
│   │   ├── train_tournament.py
│   │   ├── deploy_anomaly_model.py
│   │   └── detect_drift.py
└── src/                     # Core business logic module
    └── financial_transactions/
        ├── config.py        # Config loader
        ├── dlt/             # Bronze, Silver, Gold transformations
        ├── features/        # Feature engineering logic
        ├── models/          # Model topologies and wrappers
        └── monitoring/      # Evidently drift and data quality checks
```

## 2. Operational Runbook

### Initial Setup and Deployment
1. **API Keys**: Ensure `FINNHUB_API_KEY` and `ALPHAVANTAGE_API_KEY` are stored securely (e.g. Databricks Secrets or env vars).
2. **Environment Targets**: Modifying variables per environment (`dev`, `acc`, `prd`) is handled in `databricks.yml`.
3. **Deploying Infrastructure**:
   To deploy pipelines and job updates to Databricks via DABs:
   ```bash
   databricks bundle deploy -t dev
   ```

### Day-to-Day Operations

#### A. Delta Live Tables (Streaming Data Pipeline)
- **Name**: `financial-streaming-dlt` (defined in `resources/streaming_pipeline.yml`)
- **Status Check**: Ensure the DLT pipeline is running. If `continuous: false` is configured, it will run as a batch. Change to `true` for 24/7 web-socket streaming.
- **Failures in DLT**: Check the Databricks DLT UI. Look out for schema mismatches in data ingestion through `bronze_ingest.py`.

#### B. Model Retraining (Tournament)
- **Job Name**: `financial-retraining-workflow`
- **Trigger**: Run manually or via the specified schedule. (Currently defined as `PAUSED` in variables).
- **Process**:
  1. `train_tournament.py` evaluates LightGBM, XGBoost, Random Forest, & Isolation forest.
  2. The primary metric (`pr_auc`) is optimized.
  3. The `deploy_anomaly_model.py` task compares the winner with the current Champion (champion/challenger gating). If `pr_auc` improves by > `0.005`, the challenger replaces the champion in the Databricks Model Registry.

#### C. Drift & Monitoring 
- **Job Name**: `financial-drift-monitoring`
- **Schedule**: Every 30 minutes (`0 */30 * * * ?`).
- **Logic**: Pulls `reference_window_days` vs current window. Calculates PSI & JS Divergence on features like price volatility and trade intensity.
- If drift threshold (e.g., PSI > 0.2) is breached, an alert event log is generated.

### Troubleshooting Scenarios

**Issue: High volume of False Positives in Anomaly Detection**
- **Action**: Check `project_config.yml` under `drift`.
- **Action**: Verify if feature distributions have shifted. Run `financial-drift-monitoring` manually to review the Evidently reports. 
- **Mitigation**: Manually trigger `financial-retraining-workflow` to update the model to new market conditions.

**Issue: WebSockets disconnect or stop ingesting data**
- **Action**: Investigate logs for `collect_finnhub_stream.py`. Ensure Databricks cluster has external internet access. Review Finnhub API rate limits. Restart DLT pipeline.

**Issue: Dashboard is disconnected**
- **Action**: The frontend connects to an exposed model endpoint or metrics export. Verify `export_dashboard_metrics.py` is running or API serving endpoints are accessible via Databricks Model Serving.

### Emergency Rollback
- **Scenario**: A newly deployed model exhibits poor production performance that is impacting business logic. 
- **Mitigation**: Execute `scripts/financial/rollback_model.py` to revert the `Champion` alias in MLflow to the previous approved version.
