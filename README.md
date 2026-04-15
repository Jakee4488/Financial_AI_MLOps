# Financial AI MLOps

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Databricks](https://img.shields.io/badge/Databricks-Asset%20Bundles-orange.svg)
![MLflow](https://img.shields.io/badge/MLflow-3.1.1-blue.svg)

## Introduction

**Financial AI MLOps** is an enterprise-grade machine learning operations project focused on detecting anomalies in financial market transactions. Built on Databricks, it provides a comprehensive end-to-end framework starting from real-time streaming data ingestion to automated model retraining and serving. 

The primary objective is to reliably capture financial data streams (e.g., via Finnhub WebSockets), process them using Delta Live Tables (DLT), generate predictive features, and serve robust anomaly detection models capable of identifying irregular market behaviors.

## Key Functionalities

This repository encompasses a complete MLOps lifecycle, broken down into the following core functionalities:

### 1. Data Ingestion (Streaming & Historical)
* **Real-time Streaming:** Consumes continuous websocket streams from the Finnhub API for real-time trade data.
* **Historical Batching:** Periodically pulls historical market data using Alpha Vantage for robust training sets and baselining.

### 2. Data Processing & Feature Engineering (DLT)
* **Delta Live Tables (DLT):** A declarative pipeline architecture transforming raw data into high-value assets.
  * *Bronze:* Raw ingestion layer.
  * *Silver:* Cleaned, formatted, and validated transactional data.
  * *Gold:* Aggregated features ready for ML training and inference.
* **Feature Store Integration:** Centralized tracking and lookup of engineered features to maintain consistency between offline training and online serving.

### 3. Model Training & Tournament
* **Multi-Model Support:** Implementations for XGBoost, LightGBM, Random Forest, and Isolation Forest.
* **Model Tournament:** An automated training system that concurrently trains multiple algorithms on the latest Gold data, tuning hyperparameters and evaluating relative performance across custom metrics (e.g., PR AUC, F1 Score).

### 4. Advanced Monitoring & Observability
* **Data & Concept Drift Detection:** Continuously calculates Population Stability Index (PSI) and Jensen-Shannon Divergence on incoming live data against reference windows.
* **Automated Retraining:** Programmatic triggers that initiate a retraining pipeline (Model Tournament) if performance degrades or substantial drift is detected.

---

## Deployment Strategies

To ensure zero-downtime, safe, and highly performant model deployments, this project employs advanced deployment and release strategies:

### Champion / Challenger Gating
Before any newly trained model is deployed to production, it must survive a "Champion vs. Challenger" validation phase. The system automatically benchmarks the Challenger against the currently deployed Champion across primary (PR AUC) and secondary (F1, Precision, Recall) metrics. A new model is only promoted if it proves definitively better based on configured thresholds.

### A/B Testing & Traffic Splitting
Production deployments support A/B testing directly within Databricks Model Serving. Traffic can be weighted and split between the stable model and a newly promoted model, allowing the team to measure real-world performance differences without impacting all end-users.

### Automated Rollbacks
Model serving includes a dedicated `rollback_manager`. If continuous monitoring detects severe performance degradation or latency spikes in the newest deployment, the system can automatically orchestrate a rollback to the previous known-good model state, minimizing business risk.

### CI/CD with Databricks Asset Bundles
Infrastructure as Code (IaC) and pipeline automation are handled using **Databricks Asset Bundles (DABs)** (`databricks.yml`). Changes merged to the main branch trigger GitHub Actions that automatically validate code, run tests, and deploy the updated resources (Jobs, DLT Pipelines, Workflows) to Databricks environments (Dev, Acc, Prd).

---

## Getting Started

For a comprehensive guide on setting up the infrastructure, running pipelines, and managing operations, please refer to our internal [Operational Documents](./Operational_Documents/):

* 🧭 [Project Structure Map](./Operational_Documents/PROJECT_STRUCTURE.md)
* 🚀 [Comprehensive MLOps Setup Guide](./Operational_Documents/COMPREHENSIVE_MLOPS_SETUP_GUIDE.md)
* ✅ [Pipeline Testing & Validation](./Operational_Documents/GETTING_STARTED_PIPELINE_TESTING.md)
* 📖 [Operations Runbook](./Operational_Documents/RUNBOOK.md)

*Note: Canonical configurations are found in `project_config.yml` and `pyproject.toml`.*
