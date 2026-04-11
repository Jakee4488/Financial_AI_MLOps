# Financial AI MLOps — Project Structure

Complete map of every directory, file, and its role in the system.

---

## Top-Level Layout

```
Financial_AI_MLOps/
├── .databricks/              # Local Databricks CLI state (auto-generated)
├── .github/workflows/        # CI/CD automation (GitHub Actions)
├── .sops.yaml                # Secret encryption rules (Age/SOPS)
├── .venv/                    # Python virtual environment
├── Operational_Documents/    # ← You are here — runbooks, guides, references
├── dashboard/                # Web-based monitoring dashboard (HTML/JS)
├── databricks.yml            # Databricks Asset Bundle root config
├── dist/                     # Built Python wheel (output of `uv build`)
├── project_config.yml        # Master runtime configuration (YAML)
├── pyproject.toml            # Python project definition, deps, lint rules
├── resources/                # Databricks job & pipeline YAML definitions
├── scripts/financial/        # Notebook-style entry-point scripts
├── setup_uc_infrastructure.sql # Unity Catalog DDL (catalogs, schemas, volumes)
├── src/financial_transactions/ # Main Python library (installable wheel)
├── tests/                    # Pytest unit tests
├── typings/                  # Custom type stubs
└── version.txt               # Package version (dynamic in pyproject.toml)
```

---

## `resources/` — Databricks Workflow Definitions

All jobs and pipelines defined here are deployed via `databricks bundle deploy`.

| File | Databricks Resource | Schedule | Purpose |
|---|---|---|---|
| `ingestion_workflow.yml` | Job: `financial-api-ingestion-workflow` | Manual / event-triggered | Collect live trades, then run DLT |
| `streaming_pipeline.yml` | Pipeline: `financial-streaming-dlt` | Triggered by ingestion job | DLT Bronze→Silver→Gold medallion |
| `retraining_workflow.yml` | Job: `financial-retraining-workflow` | Nightly `0 0 0 * * ?` | Train 4 models + champion/challenger gate |
| `drift_monitoring.yml` | Job: `financial-drift-monitoring` | Every 30 min `0 */30 * * * ?` | PSI/JS drift detection + retrain trigger |

---

## `scripts/financial/` — Notebook Entry-Point Scripts

These run directly inside Databricks as notebooks or `spark_python_task`. They install the wheel and call library code.

| Script | Pipeline | What It Does |
|---|---|---|
| `collect_finnhub_stream.py` | Ingestion | Runs `FinnhubCollector` for 5 minutes, dumps JSON to landing zone |
| `collect_alphavantage_history.py` | Ingestion | Pulls historical OHLCV from Alpha Vantage REST API |
| `dlt_pipeline.py` | Streaming DLT | Defines `bronze_trades`, `silver_trades`, `gold_trade_features` DLT tables |
| `train_tournament.py` | Retraining | Runs 4-model tournament via `ModelTournament` |
| `deploy_anomaly_model.py` | Retraining | Champion/challenger gate; registers winning model |
| `detect_drift.py` | Drift Monitoring | Loads reference/current windows, runs `DriftDetector`, triggers retrain |
| `rollback_model.py` | Drift Monitoring | Emergency: re-aliases previous champion in UC Model Registry |
| `export_dashboard_metrics.py` | Monitoring | Exports JSON metrics files for the web dashboard |

---

## `src/financial_transactions/` — Python Library

Installed as a wheel (`financial-ai-mlops-*.whl`) on every Databricks task. Organised by domain.

```
src/financial_transactions/
├── __init__.py
├── config.py                 # All Pydantic config models + ProjectConfig.from_yaml()
├── dlt/                      # Standalone DLT helper modules
│   ├── bronze_ingest.py      # Auto Loader helpers
│   ├── silver_transform.py   # Transformation helpers
│   └── gold_features.py      # Window-function feature computations
├── features/
│   ├── feature_engineering.py   # FeatureEngineer (pandas batch mode)
│   └── feature_store_manager.py # FeatureStoreManager (Unity Catalog)
├── models/
│   ├── base_model.py            # BaseAnomalyModel ABC + ModelResult dataclass
│   ├── lightgbm_model.py        # LightGBMModel
│   ├── xgboost_model.py         # XGBoostModel
│   ├── random_forest_model.py   # RandomForestModel
│   ├── isolation_forest_model.py # IsolationForestModel
│   ├── model_tournament.py      # ModelTournament orchestrator
│   ├── champion_challenger.py   # ChampionChallenger gate + ComparisonResult
│   ├── model_validator.py       # ModelValidator (pre-deployment checks)
│   └── custom_model.py          # CustomModel (MLflow pyfunc wrapper)
├── monitoring/
│   ├── drift_detector.py        # DriftDetector (PSI + JS divergence)
│   ├── performance_monitor.py   # PerformanceMonitor (Lakehouse Monitor)
│   ├── retraining_trigger.py    # RetrainingTrigger (cooldown + daily limits)
│   └── alerting.py              # AlertManager (webhook + Delta audit)
└── streaming/
    ├── alphavantage_collector.py # AlphaVantageCollector (REST historical)
    ├── finnhub_collector.py      # FinnhubCollector (WebSocket real-time)
    └── stream_processor.py       # StreamProcessor (Bronze→Silver streaming)
```

---

## `tests/` — Unit Tests

All tests run with `pytest`. Spark tests auto-skip if `databricks-connect` is installed.

| Test File | Tests |
|---|---|
| `conftest.py` | Shared fixtures: `spark`, `mock_config_path`, `sample_trade_data` |
| `test_config.py` | `ProjectConfig.from_yaml()` parsing, env switching, validation |
| `test_alphavantage_collector.py` | HTTP mocking, rate limiting, retry logic |
| `test_finnhub_collector.py` | WebSocket message parsing, buffer flush, reconnect |
| `test_stream_processor.py` | Bronze→Silver schema validation, dedup, session_type logic |
| `test_feature_engineering.py` | RSI, MACD, Bollinger, VWAP, anomaly label generation |
| `test_model_tournament.py` | Tournament ranking, comparison table, winner selection |
| `test_champion_challenger.py` | PROMOTE/REJECT decision logic, auto-promote on first deploy |
| `test_drift_detector.py` | PSI (identical vs shifted distributions), JS divergence, retrain trigger |
| `test_rollback.py` | State snapshot capture, model rollback, feature table time travel |
| `test_serving.py` | Endpoint create/update, canary split, promote_to_production |

---

## `.github/workflows/` — CI/CD

| File | Trigger | Jobs |
|---|---|---|
| `ci.yml` | Push to `main`/`develop`, PR to `main` | lint-and-test → security-scan → bundle-validate → build |
| `cd.yml` | Push to `main`, workflow_dispatch | deploy-dev → deploy-acc → deploy-prd → (rollback) |
| `model_validation.yml` | Workflow dispatch | Standalone model validation job |

---

## `Operational_Documents/` — This Folder

| File | Purpose |
|---|---|
| `README.md` | Index of all docs |
| `COMPREHENSIVE_MLOPS_SETUP_GUIDE.md` | Full environment setup from scratch |
| `DEPLOYMENT_VALIDATION_GUIDE.md` | Step-by-step deployment checklist |
| `GETTING_STARTED_PIPELINE_TESTING.md` | How to run and test all pipelines |
| `RUNBOOK.md` | On-call incident response procedures |
| `SECURE_ACCESS_ENCRYPTION_GUIDE.md` | SOPS/Age secret management |
| `SOPS_ENCRYPTION_SETUP.md` | SOPS tooling setup |
| `AGE_SOPS_QUICKSTART.md` | Quick Age key generation guide |
| `PROJECT_STRUCTURE.md` | ← **This file** — directory and file map |
| `FUNCTION_AND_CONFIG_REFERENCE.md` | Every function, class, and config field |

---

## Key Configuration Files

| File | What It Controls |
|---|---|
| `project_config.yml` | Runtime config: features, hyperparams, drift thresholds, API endpoints |
| `databricks.yml` | Bundle metadata, variables, environment targets (dev/acc/prd) |
| `pyproject.toml` | Python deps, pytest settings, ruff lint rules |
| `.sops.yaml` | Which files SOPS encrypts and with which key |
| `setup_uc_infrastructure.sql` | UC catalogs, schemas, volumes, grants |

---

## Delta Tables (Unity Catalog)

Created by the pipelines at runtime under `mlops_<env>.financial_transactions`.

| Table | Layer | Written By | Read By |
|---|---|---|---|
| `—` (landing zone volume) | Raw files | `FinnhubCollector` | DLT Auto Loader |
| `bronze_trades` | Bronze | DLT `bronze_trades()` | DLT `silver_trades()` |
| `silver_trades` | Silver | DLT `silver_trades()` | DLT `gold_trade_features()` |
| `gold_trade_features` | Gold | DLT `gold_trade_features()` | Training, Drift Monitoring |
| `trade_features` | Gold (alternate) | `FeatureStoreManager` | All model training |
| `train_set` | ML | `FeatureStoreManager.save_training_sets()` | All model `load_data()` |
| `test_set` | ML | `FeatureStoreManager.save_training_sets()` | All model `evaluate()` |
| `drift_monitoring` | Monitoring | `DriftDetector.write_drift_metrics()` | Dashboard, alerts |
| `model_monitoring` | Monitoring | `PerformanceMonitor` | Dashboard |
| `champion_challenger_audit` | Audit | `ChampionChallenger.write_audit_record()` | Analysis |
| `retraining_audit` | Audit | `RetrainingTrigger._write_audit_event()` | Cooldown checks |

---

## MLflow / Unity Catalog Model Registry

| Resource | Name Pattern | Aliases |
|---|---|---|
| UC Model | `mlops_<env>.financial_transactions.anomaly_model_champion` | `champion`, `latest-model` |
| Experiment | `/Shared/financial-anomaly-basic` | — |
| Experiment | `/Shared/financial-anomaly-custom` | — |
