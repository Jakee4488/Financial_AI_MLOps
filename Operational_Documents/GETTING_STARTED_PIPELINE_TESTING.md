# Getting Started and Full Pipeline Capability Testing

This document is a practical guide to:
- start the project locally,
- run tests,
- validate end-to-end pipeline capability on Databricks.

## 1. Quick Start (Local)

### 1.1 Create and activate environment

```bash
uv venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### 1.2 Install dependencies

```bash
uv pip install -e ".[dev,test,streaming]"
```

### 1.3 Run all tests

```bash
pytest -q
```

Latest verified local result in this workspace (2026-04-08):
- 28 passed
- 1 skipped
- Runtime about 51s
- Coverage about 46%

## 2. What Current Tests Cover

Automated tests currently validate:
- Alpha Vantage collector success/error/rate-limit behavior
- Finnhub collector parsing and message handling
- Feature engineering and training data preparation
- Model tournament scoring and comparison
- Champion/challenger promotion logic
- Drift detector metrics and retrain decision logic
- Serving update/canary logic and rollback manager logic
- Stream transformation utility behavior

Automated tests currently do not fully validate:
- Delta Live Tables notebook execution end-to-end
- Databricks workflow orchestration runtime behavior
- Live model serving endpoint behavior in Databricks

## 3. Full Pipeline Capability Validation (Databricks)

Run these checks in order.

### 3.1 Validate bundle config

```bash
databricks bundle validate -t dev
```

Pass condition:
- command succeeds with no validation errors.

### 3.2 Deploy to dev

```bash
databricks bundle deploy -t dev
```

Pass condition:
- deployment completes successfully.

### 3.3 Execute pipeline resources

```bash
databricks bundle run -t dev financial_streaming_pipeline
databricks bundle run -t dev financial_retraining_workflow
databricks bundle run -t dev drift_monitoring_job
```

Pass conditions:
- each run completes successfully,
- retraining reaches model deployment step,
- drift monitoring emits decision output.

### 3.4 Verify outcomes in Databricks UI

Check:
- DLT tables were updated in target catalog/schema,
- MLflow has a valid champion model alias/version,
- drift artifacts and metrics were produced,
- rollback path can be executed successfully.

## 4. How to Test the Data Pipeline

This section is specifically for validating the medallion data pipeline.

### 4.1 Local pipeline-related tests

Run focused tests for ingestion/transform logic:

```bash
pytest -q tests/financial_transactions/test_stream_processor.py
pytest -q tests/financial_transactions/test_finnhub_collector.py
pytest -q tests/financial_transactions/test_alphavantage_collector.py
pytest -q tests/financial_transactions/test_feature_engineering.py
```

Pass condition:
- all four test modules pass.

### 4.2 Run DLT pipeline in Databricks

```bash
databricks bundle run -t dev financial_streaming_pipeline
```

Pass condition:
- pipeline run completes successfully with no failed update.

### 4.3 Validate Bronze -> Silver -> Gold data flow

In Databricks SQL editor (or notebook SQL cell), run:

```sql
SELECT COUNT(*) AS bronze_count
FROM mlops_dev.financial_transactions.bronze_trades;

SELECT COUNT(*) AS silver_count
FROM mlops_dev.financial_transactions.silver_trades;

SELECT COUNT(*) AS gold_count
FROM mlops_dev.financial_transactions.gold_trade_features;
```

Pass condition:
- all three queries return non-zero counts after pipeline run.

### 4.4 Validate data-quality expectations on Silver

`silver_trades` has these DLT expectations:
- `valid_price` (`price > 0`)
- `valid_symbol` (`symbol IS NOT NULL AND symbol != ''`)
- `valid_timestamp` (`timestamp IS NOT NULL`)
- `valid_volume` (`volume >= 0`)

Run checks:

```sql
SELECT COUNT(*) AS invalid_price
FROM mlops_dev.financial_transactions.silver_trades
WHERE price <= 0;

SELECT COUNT(*) AS invalid_symbol
FROM mlops_dev.financial_transactions.silver_trades
WHERE symbol IS NULL OR symbol = '';

SELECT COUNT(*) AS invalid_timestamp
FROM mlops_dev.financial_transactions.silver_trades
WHERE timestamp IS NULL;
```

Pass condition:
- invalid counts are zero.

### 4.5 Validate Gold feature completeness

Run checks:

```sql
SELECT COUNT(*) AS null_critical_features
FROM mlops_dev.financial_transactions.gold_trade_features
WHERE symbol IS NULL OR timestamp IS NULL;

SELECT
	MIN(price_volatility_1h) AS min_volatility,
	MAX(price_volatility_1h) AS max_volatility,
	MIN(trade_intensity_1m) AS min_intensity,
	MAX(trade_intensity_1m) AS max_intensity
FROM mlops_dev.financial_transactions.gold_trade_features;
```

Pass condition:
- `null_critical_features = 0`
- feature ranges look reasonable (not all null/zero due to broken transforms).

### 4.6 Regression check for pipeline changes

After any code change in DLT notebooks:
- rerun step 4.2,
- rerun all SQL checks in steps 4.3 to 4.5,
- rerun local tests in step 4.1.

### 4.7 Table test checks (copy/paste suite)

Use this as a quick test suite after every pipeline run.

1. Table existence

```sql
SHOW TABLES IN mlops_dev.financial_transactions;
```

Pass condition:
- result includes `bronze_trades`, `silver_trades`, `gold_trade_features`.

2. Non-empty table checks

```sql
SELECT
	SUM(CASE WHEN table_name = 'bronze_trades' AND row_count > 0 THEN 1 ELSE 0 END) AS bronze_ok,
	SUM(CASE WHEN table_name = 'silver_trades' AND row_count > 0 THEN 1 ELSE 0 END) AS silver_ok,
	SUM(CASE WHEN table_name = 'gold_trade_features' AND row_count > 0 THEN 1 ELSE 0 END) AS gold_ok
FROM (
	SELECT 'bronze_trades' AS table_name, COUNT(*) AS row_count FROM mlops_dev.financial_transactions.bronze_trades
	UNION ALL
	SELECT 'silver_trades' AS table_name, COUNT(*) AS row_count FROM mlops_dev.financial_transactions.silver_trades
	UNION ALL
	SELECT 'gold_trade_features' AS table_name, COUNT(*) AS row_count FROM mlops_dev.financial_transactions.gold_trade_features
) t;
```

Pass condition:
- `bronze_ok = 1`, `silver_ok = 1`, and `gold_ok = 1`.

3. Duplicate key checks

```sql
SELECT COUNT(*) AS duplicate_trade_ids
FROM (
	SELECT trade_id
	FROM mlops_dev.financial_transactions.silver_trades
	GROUP BY trade_id
	HAVING COUNT(*) > 1
) d;

SELECT COUNT(*) AS duplicate_gold_trade_ids
FROM (
	SELECT trade_id
	FROM mlops_dev.financial_transactions.gold_trade_features
	GROUP BY trade_id
	HAVING COUNT(*) > 1
) d;
```

Pass condition:
- both duplicate counts are `0`.

4. Freshness check

```sql
SELECT
	MAX(_ingested_at) AS latest_bronze_ingest,
	MAX(_processed_at) AS latest_silver_process
FROM mlops_dev.financial_transactions.bronze_trades b
CROSS JOIN mlops_dev.financial_transactions.silver_trades s;

SELECT MAX(_processed_at) AS latest_gold_process
FROM mlops_dev.financial_transactions.gold_trade_features;
```

Pass condition:
- timestamps are recent relative to your latest pipeline run window.

5. Required column checks

```sql
DESCRIBE TABLE mlops_dev.financial_transactions.bronze_trades;
DESCRIBE TABLE mlops_dev.financial_transactions.silver_trades;
DESCRIBE TABLE mlops_dev.financial_transactions.gold_trade_features;
```

Pass condition:
- silver includes `trade_id`, `symbol`, `price`, `volume`, `timestamp`, `session_type`, `trade_type`.
- gold includes `price_change_pct`, `volume_zscore`, `price_volatility_1h`, `trade_intensity_1m`, `vwap_deviation`, `rsi_14`, `macd_signal`, `bollinger_position`.

## 5. Release-Readiness Gate

Treat a candidate as ready only when all are true:
- local pytest suite is green,
- bundle validate and deploy are green in target env,
- streaming, retraining, and drift runs are green,
- rollback process has been validated,
- no blocking monitoring alerts remain.

## 6. Useful Paths

- `databricks.yml`
- `project_config.yml`
- `resources/streaming_pipeline.yml`
- `resources/retraining_workflow.yml`
- `resources/drift_monitoring.yml`
- `tests/financial_transactions/`
