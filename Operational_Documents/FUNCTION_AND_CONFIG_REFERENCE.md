# Financial AI MLOps — Function & Configuration Reference

Complete reference for every class, function, and configuration field in the project.

---

## Table of Contents

1. [Configuration System](#1-configuration-system)
2. [Streaming: FinnhubCollector](#2-streaming-finnhubcollector)
3. [Streaming: AlphaVantageCollector](#3-streaming-alphavantagecollector)
4. [Streaming: StreamProcessor](#4-streaming-streamprocessor)
5. [DLT Pipeline Tables](#5-dlt-pipeline-tables)
6. [Features: FeatureEngineer](#6-features-featureengineer)
7. [Features: FeatureStoreManager](#7-features-featurestoremanager)
8. [Models: BaseAnomalyModel & ModelResult](#8-models-baseanomalymodel--modelresult)
9. [Models: ModelTournament](#9-models-modeltournament)
10. [Models: ChampionChallenger](#10-models-championchallenger)
11. [Monitoring: DriftDetector](#11-monitoring-driftdetector)
12. [Monitoring: RetrainingTrigger](#12-monitoring-retrainingtrigger)
13. [Monitoring: PerformanceMonitor](#13-monitoring-performancemonitor)
14. [Monitoring: AlertManager](#14-monitoring-alertmanager)
15. [Serving: AnomalyModelServing](#15-serving-anomalymodelserving)
16. [Serving: RollbackManager](#16-serving-rollbackmanager)
17. [Serving: ABTestManager](#17-serving-abtestmanager)
18. [project_config.yml — All Fields](#18-project_configyml--all-fields)
19. [databricks.yml — All Variables & Targets](#19-databricksyml--all-variables--targets)

---

## 1. Configuration System

**File:** `src/financial_transactions/config.py`

All config classes are Pydantic `BaseModel`s — they validate types on construction and can be loaded from YAML via `ProjectConfig.from_yaml()`.

---

### `ProjectConfig`

Main config object. Loaded by every notebook script and model.

```python
config = ProjectConfig.from_yaml("../../project_config.yml", env="dev")
```

#### `ProjectConfig.from_yaml(config_path, env)`

| Param | Type | Description |
|---|---|---|
| `config_path` | `str` | Path to `project_config.yml` |
| `env` | `str` | One of `"dev"`, `"acc"`, `"prd"` |

**What it does:** Reads the YAML, selects the `catalog_name` and `schema_name` for the chosen `env`, then parses all nested config blocks (`streaming`, `drift`, etc.) into their typed Pydantic models.

**Returns:** `ProjectConfig` instance.

**Raises:** `ValueError` if `env` is not `dev`, `acc`, or `prd`.

#### `ProjectConfig` Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `num_features` | `list[str]` | — | Numerical feature columns used in model training |
| `cat_features` | `list[str]` | — | Categorical feature columns (label-encoded) |
| `target` | `str` | — | Target column name (always `"is_anomaly"`) |
| `catalog_name` | `str` | — | Unity Catalog name (resolved from env) |
| `schema_name` | `str` | — | Schema name (always `"financial_transactions"`) |
| `parameters` | `dict` | — | Default LightGBM hyperparameters |
| `experiment_name_basic` | `str \| None` | — | MLflow experiment path |
| `experiment_name_custom` | `str \| None` | — | MLflow experiment path (custom models) |
| `models` | `dict \| None` | — | Per-model hyperparameter overrides |
| `champion_challenger` | `ChampionChallengerConfig` | defaults | C/C gating settings |
| `streaming` | `StreamingConfig` | defaults | Finnhub WebSocket settings |
| `historical` | `HistoricalConfig` | defaults | Alpha Vantage settings |
| `drift` | `DriftConfig` | defaults | Drift detection thresholds |
| `retraining` | `RetrainingConfig` | defaults | Retraining guard settings |

---

### `StreamingConfig`

Controls the Finnhub WebSocket collector.

| Field | Type | Default | Description |
|---|---|---|---|
| `finnhub_api_key` | `str` | `""` | Finnhub WebSocket API key (from env var `${FINNHUB_API_KEY}`) |
| `finnhub_ws_url` | `str` | `"wss://ws.finnhub.io"` | WebSocket endpoint |
| `finnhub_symbols` | `list[str]` | `[]` | Ticker symbols to subscribe to |
| `batch_interval_seconds` | `int` | `30` | How often buffer is flushed to Delta |
| `checkpoint_base` | `str` | `"/Workspace/checkpoints/financial-anomaly"` | Spark streaming checkpoint root |
| `max_records_per_batch` | `int` | `1000` | Buffer overflow threshold — triggers early flush |
| `watermark_delay` | `str` | `"2 minutes"` | Late-arriving data tolerance for Spark Structured Streaming |
| `landing_zone_path` | `str` | `"dbfs:/Volumes/mlops_dev/.../trades"` | Where JSON trade files land |

---

### `HistoricalConfig`

Controls the Alpha Vantage REST collector.

| Field | Type | Default | Description |
|---|---|---|---|
| `alphavantage_api_key` | `str` | `""` | Alpha Vantage API key |
| `alphavantage_base_url` | `str` | `"https://www.alphavantage.co/query"` | REST endpoint |
| `symbols` | `list[str]` | `[]` | Tickers to pull history for |
| `interval` | `str` | `"5min"` | OHLCV bar interval |
| `outputsize` | `str` | `"full"` | `"compact"` (100 bars) or `"full"` (all history) |
| `rate_limit_sleep` | `int` | `12` | Seconds to sleep between calls (avoid 5 req/min limit) |
| `max_calls_per_day` | `int` | `25` | Hard cap on daily API calls |

---

### `DriftConfig`

Controls drift detection thresholds.

| Field | Type | Default | Description |
|---|---|---|---|
| `reference_window_days` | `int` | `30` | Days of historical data used as baseline distribution |
| `detection_interval_minutes` | `int` | `60` | How often the drift job runs (set via cron, not this field) |
| `psi_threshold` | `float` | `0.2` | PSI above this = numerical feature drifted |
| `js_divergence_threshold` | `float` | `0.1` | JS divergence above this = categorical feature drifted |
| `performance_degradation_threshold` | `float` | `0.05` | PR-AUC drop greater than this triggers retraining |

> **Tuning tip:** Lower `psi_threshold` to `0.1` for more sensitive drift detection in volatile markets. Raise to `0.25` for noisier, stable assets.

---

### `RetrainingConfig`

Guards against excessive retraining.

| Field | Type | Default | Description |
|---|---|---|---|
| `min_new_records` | `int` | `5000` | Minimum new trades since last training to trigger data-volume retraining |
| `cooldown_hours` | `int` | `6` | Minimum hours between consecutive retraining runs |
| `max_retrain_per_day` | `int` | `4` | Maximum retraining jobs allowed per calendar day |

---

### `ChampionChallengerConfig`

Controls the promotion gate between tournament winner and production champion.

| Field | Type | Default | Description |
|---|---|---|---|
| `primary_metric` | `str` | `"pr_auc"` | Metric used for the primary promotion decision |
| `secondary_metrics` | `list[str]` | `["f1_score", "precision", "recall"]` | Reported alongside primary but don't affect decision |
| `min_improvement_threshold` | `float` | `0.005` | Challenger must exceed champion by at least this on `primary_metric` |
| `require_all_metrics_improvement` | `bool` | `False` | If `True`, challenger must improve ALL secondary metrics too |

---

### `Tags`

MLflow run tags. Attached to every training run.

| Field | Type | Description |
|---|---|---|
| `git_sha` | `str` | Git commit SHA that triggered training |
| `branch` | `str` | Git branch name |
| `run_id` | `str \| None` | Optional parent run ID for nested runs |

#### `Tags.to_dict()`
Returns `{"git_sha": "...", "branch": "..."}` (excludes `run_id` if `None`).

---

## 2. Streaming: FinnhubCollector

**File:** `src/financial_transactions/streaming/finnhub_collector.py`

Connects to Finnhub's WebSocket API, buffers trade ticks in memory, and flushes micro-batches to Delta.

### Constructor

```python
FinnhubCollector(config: StreamingConfig, spark=None, output_path=None)
```

| Param | Description |
|---|---|
| `config` | `StreamingConfig` with API key and symbols |
| `spark` | SparkSession — if `None`, writes local Parquet instead of Delta |
| `output_path` | Override the landing zone path from config |

### Methods

#### `start(duration=None)`
Start the collector. Blocks until done.

| Param | Type | Default | Description |
|---|---|---|---|
| `duration` | `int \| None` | `None` | Run for N seconds then stop. `None` = run forever |

**What happens:**
1. Sets `_running = True`
2. Starts `_periodic_flush` background thread (wakes every `batch_interval_seconds`)
3. If `duration` is set: runs WebSocket in a thread, sleeps `duration` seconds, then calls `stop()`
4. If no duration: runs WebSocket in the main thread (blocking)

#### `stop()`
Gracefully stop. Closes WebSocket, does final flush of remaining buffer records.

#### `get_buffer_size() → int`
Returns number of records currently buffered (thread-safe).

### Internal Methods

| Method | Description |
|---|---|
| `_on_message(ws, message)` | Parses Finnhub JSON tick, adds UUID, converts epoch milliseconds to UTC datetime, appends to buffer. Calls `_flush_buffer()` if buffer hits `max_records_per_batch`. |
| `_on_error(ws, error)` | Logs error. Connection remains open if non-fatal. |
| `_on_close(ws, code, msg)` | If `_running` is True, waits 5s and calls `_connect()` to reconnect. |
| `_on_open(ws)` | Sends `{"type":"subscribe","symbol":"X"}` for each configured symbol. |
| `_parse_exchange(symbol) → str` | Static. Splits `"BINANCE:BTCUSDT"` → `"BINANCE"`. Returns `"US"` for plain tickers. |
| `_flush_buffer()` | Thread-safe. Copies + clears buffer. Writes to Delta (Spark mode) or Parquet (local mode). On exception, puts records back in buffer. |
| `_periodic_flush()` | Background loop: sleeps `batch_interval_seconds`, calls `_flush_buffer()`. |
| `_connect()` | Creates `WebSocketApp` with all 4 handlers and calls `run_forever()`. |

---

## 3. Streaming: AlphaVantageCollector

**File:** `src/financial_transactions/streaming/alphavantage_collector.py`

Pulls intraday OHLCV data from Alpha Vantage's REST API with rate-limit management.

### Key Methods

#### `collect_intraday(symbol) → pd.DataFrame`
Fetches intraday bars for a single symbol. Respects `rate_limit_sleep`. Returns DataFrame with `open`, `high`, `low`, `close`, `volume`, `timestamp`.

#### `collect_all_symbols() → pd.DataFrame`
Iterates over all configured symbols, calls `collect_intraday()`, enforces `max_calls_per_day`. Returns combined DataFrame.

#### `save_to_delta(df, path)`
Writes collected data to the Delta landing zone via Spark.

---

## 4. Streaming: StreamProcessor

**File:** `src/financial_transactions/streaming/stream_processor.py`

Reads from the Delta landing zone using Spark Structured Streaming and writes to Silver Delta tables.

### Constructor

```python
StreamProcessor(config: StreamingConfig, spark: SparkSession)
```

### Methods

#### `read_landing_zone() → DataFrame`
Returns a **streaming** DataFrame from the Delta landing zone. Enforces the trade schema:

```
trade_id (String), symbol (String), price (Double), volume (Double),
timestamp (Timestamp), exchange (String), ingestion_timestamp (Timestamp)
```

Uses `maxFilesPerTrigger = max_records_per_batch` to control micro-batch size.

#### `transform_bronze_to_silver(bronze_df) → DataFrame`
Applies transformations to the raw stream:

| Transformation | Logic |
|---|---|
| Deduplication | `.dropDuplicates(["trade_id"])` |
| Filter invalid | `price > 0`, `symbol IS NOT NULL` |
| `hour_of_day` | `F.hour("timestamp")` |
| `minute_of_hour` | `F.minute("timestamp")` |
| `day_of_week` | `F.dayofweek("timestamp")` (1=Sun, 7=Sat) |
| `is_weekend` | `dayofweek IN (1,7)` |
| `session_type` | `hour >= 9 AND hour < 16` → `regular`, else `pre_market`/`after_hours` |
| `trade_type` | `volume >= 10000` → `block`, `>= 100` → `standard`, else `odd_lot` |
| Null fill | `volume → 0.0`, `exchange → "US"` |
| `processed_timestamp` | `current_timestamp()` |
| Watermark | `.withWatermark("timestamp", watermark_delay)` — drops records older than 2 min |

#### `start_bronze_to_silver(output_table=None, output_path=None) → StreamingQuery`
Chains `read_landing_zone()` → `transform_bronze_to_silver()` and writes with:
- Format: Delta
- Output mode: append
- Trigger: `processingTime = batch_interval_seconds seconds`
- Checkpoint: `checkpoint_base/bronze_to_silver`

**Requires** either `output_table` (write to UC table) or `output_path` (write to path).

#### `stop_all()`
Stops all streaming queries tracked by this processor.

#### `compute_batch_quality_metrics(batch_df, batch_id) → dict` *(static)*
For use with `foreachBatch`. Computes `record_count`, `symbol_count`, `avg_price`, `stddev_price`, `total_volume` per micro-batch.

---

## 5. DLT Pipeline Tables

**File:** `scripts/financial/dlt_pipeline.py`

Defines 3 DLT tables. Runs inside a Databricks Delta Live Tables pipeline context.

### `bronze_trades()`
- **Source:** Auto Loader (`cloudFiles`) reading JSON from `streaming_landing/trades/`
- **Adds:** `_ingested_at` (timestamp), `_source_file` (file path metadata)
- **No filtering** — all raw data preserved

### `silver_trades()`

Quality expectations (via `@dlt.expect_*` decorators):

| Expectation | Rule | Action |
|---|---|---|
| `valid_price` | `price > 0` | Drop row |
| `valid_symbol` | `symbol IS NOT NULL AND symbol != ''` | Drop row |
| `valid_timestamp` | `timestamp IS NOT NULL` | **Fail pipeline** |
| `valid_volume` | `volume >= 0` | Warn only (metric tracked) |

Enrichment applied:
- Dedup by `trade_id`
- Type casts: price, volume → double; timestamp → proper Timestamp
- Time fields: `hour_of_day`, `minute_of_hour`, `day_of_week`, `is_weekend`
- `session_type` (UTC hours): `14:00–21:00` → regular, `< 14:00` → pre_market, else after_hours
- `trade_type`: block / standard / odd_lot
- Null fills, `_processed_at` timestamp

### `gold_trade_features()`

Reads from `silver_trades` (batch, not stream). Applies window functions per symbol with a 14-row rolling window (`symbol_rows_14 = Window.partitionBy("symbol").orderBy("timestamp").rowsBetween(-13, 0)`).

| Feature | Computation |
|---|---|
| `price_change_pct` | `(price - prev_price) / prev_price * 100` via `lag()` |
| `rolling_avg_price_14` | `avg(price)` over 14 rows |
| `rolling_std_price_14` | `stddev(price)` over 14 rows |
| `rolling_avg_volume_14` | `avg(volume)` over 14 rows |
| `rolling_std_volume_14` | `stddev(volume)` over 14 rows |
| `volume_zscore` | `(volume - avg_vol) / std_vol` |
| `price_volatility_1h` | `rolling_std_price_14` (proxy) |
| `trade_intensity_1m` | Count of trades in rolling 14-row window |
| `vwap_14` | `sum(price*volume) / sum(volume)` over 14 rows |
| `vwap_deviation` | `(price - vwap) / vwap * 100` |
| `rsi_14` | 14-period RSI via average gain/loss |
| `macd_signal` | `ema_12 - ema_26` (approximated with rolling averages) |
| `bollinger_position` | `(price - lower_band) / (upper_band - lower_band)` |
| `bid_ask_spread_pct` | `rolling_std / price * 100` (proxy) |

All NaN values from window edges filled with `0.0`.

---

## 6. Features: FeatureEngineer

**File:** `src/financial_transactions/features/feature_engineering.py`

Pandas-based (batch mode) feature computation for model training.

### Constructor

```python
FeatureEngineer(config: ProjectConfig, spark=None)
```

### Methods

#### `compute_trade_features_pandas(df) → pd.DataFrame`
Computes all rolling/technical features per symbol. Sorts by `(symbol, timestamp)`, then for each symbol:

| Feature | Window | Algorithm |
|---|---|---|
| `price_change_pct` | — | `pct_change() * 100` |
| `rolling_avg_price` | 14 | `rolling(14).mean()` |
| `rolling_std_price` | 14 | `rolling(14).std()` |
| `rolling_avg_volume` | 14 | `rolling(14).mean()` |
| `rolling_std_volume` | 14 | `rolling(14).std()` |
| `volume_zscore` | 14 | `(v - avg_v) / std_v` |
| `price_volatility_1h` | 14 | `rolling_std_price` |
| `trade_intensity_1m` | 14 | `rolling(14).count()` |
| `vwap` / `vwap_deviation` | 14 | `sum(p*v)/sum(v)`, `(p-vwap)/vwap*100` |
| `rsi_14` | 14 | Average gain/loss, `100 - 100/(1+RS)` |
| `macd_signal` | — | `EMA(12) - EMA(26)` |
| `bollinger_position` | 14 | `(price - lower) / (upper - lower)` |
| `bid_ask_spread_pct` | 14 | `rolling_std / price * 100` |

Also adds `hour_of_day`, `minute_of_hour` from `timestamp`. Fills all NaN with `0`.

#### `generate_anomaly_labels(df, volume_threshold=3.0, price_threshold=2.0) → pd.DataFrame`
Adds `is_anomaly` (int: 0 or 1) column using OR of 3 rules:

| Rule | Condition |
|---|---|
| Volume + price spike | `volume_zscore.abs() > 3.0 AND price_change_pct.abs() > 2.0` |
| Extreme RSI | `rsi_14 > 85 OR rsi_14 < 15` |
| Bollinger break | `bollinger_position > 1.0 OR bollinger_position < 0.0` |

Logs anomaly rate as a percentage.

#### `prepare_training_data(df, test_size=0.2, random_state=42) → tuple[DataFrame, DataFrame]`
Calls `sklearn.model_selection.train_test_split` with **stratification** on `is_anomaly` to preserve anomaly ratio across splits. Returns `(train_df, test_df)`.

---

## 7. Features: FeatureStoreManager

**File:** `src/financial_transactions/features/feature_store_manager.py`

Manages Unity Catalog Delta tables for features and training sets.

### Table Names (auto-derived from config)

| Table | Name |
|---|---|
| Feature table | `{catalog}.{schema}.trade_features` |
| Training set | `{catalog}.{schema}.train_set` |
| Test set | `{catalog}.{schema}.test_set` |

### Methods

#### `create_feature_table(features_df, mode="overwrite")`
Adds `update_timestamp_utc` column, writes to `trade_features`, enables Change Data Feed (`delta.enableChangeDataFeed = true`).

#### `save_training_sets(train_df, test_df)`
Writes both DataFrames to their respective UC tables with `mode="overwrite"`, enables CDF on both.

#### `get_training_set() → (DataFrame, DataFrame)`
Reads `train_set` and `test_set` from UC. Returns `(train_df, test_df)`.

#### `get_feature_table_version() → str`
Uses `delta.tables.DeltaTable.history()` to return the latest Delta version number as a string.

#### `get_data_versions() → dict`
Returns `{"train_version": "N", "test_version": "N"}` — used by `RollbackManager` for state capture.

---

## 8. Models: BaseAnomalyModel & ModelResult

**File:** `src/financial_transactions/models/base_model.py`

### `ModelResult` (dataclass)

Returned by every model after training. Used by the tournament for ranking.

| Field | Type | Description |
|---|---|---|
| `model_name` | `str` | Full UC model path |
| `model_type` | `str` | e.g. `"lightgbm"`, `"xgboost"` |
| `metrics` | `dict[str, float]` | At minimum: `pr_auc`, `f1_score`, `precision`, `recall` |
| `model_uri` | `str` | MLflow URI e.g. `"runs:/abc123/model"` |
| `run_id` | `str` | MLflow run ID |
| `training_time_seconds` | `float` | Wall-clock training duration |
| `parameters` | `dict` | Hyperparameters used |

### `BaseAnomalyModel` (abstract)

All 4 tournament models extend this. **Must implement:**

| Abstract Method | Contract |
|---|---|
| `prepare_features()` | Build sklearn Pipelines, preprocessors, encoders |
| `train()` | `pipeline.fit(X_train, y_train)`, set `self.run_id` |
| `evaluate() → dict` | Return metrics dict with at minimum `pr_auc`, `f1_score`, `precision`, `recall`, `accuracy` |
| `log_model()` | `mlflow.sklearn.log_model(...)`, log params and metrics |

#### Concrete (inherited) methods:

| Method | Description |
|---|---|
| `load_data()` | Reads `train_set` and `test_set` from UC tables, converts to Pandas, splits into `X_train`, `y_train`, `X_test`, `y_test` |
| `get_model_uri() → str` | Returns `f"runs:/{self.run_id}/model"` |
| `to_result(training_time=0.0) → ModelResult` | Packages all fields into a `ModelResult` dataclass |

---

## 9. Models: ModelTournament

**File:** `src/financial_transactions/models/model_tournament.py`

Orchestrates training all 4 models and selecting the best.

### Constructor

```python
ModelTournament(config: ProjectConfig, tags: Tags, spark: SparkSession)
```

### Methods

#### `run_tournament() → TournamentResult`
Main entry point. Iterates over `MODEL_CLASSES = [LightGBMModel, XGBoostModel, RandomForestModel, IsolationForestModel]`.

For each model, calls in order:
1. `model.load_data()`
2. `model.prepare_features()`
3. `model.train()`
4. `model.evaluate()`
5. `model.log_model()`

Sorts results by `primary_metric` (descending). Returns `TournamentResult(challenger=results[0], all_results=results, comparison_table=...)`.

If a model raises any exception, it's logged and assigned `pr_auc = 0.0` (excluded from promotion).

#### `log_tournament_results(result: TournamentResult)`
Creates a new MLflow run named `"tournament-summary"`. Logs:
- Winner model type and metrics
- Tournament time
- Comparison table as CSV artifact
- Full results as JSON artifact

#### `_build_comparison_table(results) → pd.DataFrame` *(static)*
Builds a DataFrame with columns: `model_type`, `run_id` (first 8 chars), all metric columns, `training_time_s`. Sorted by `pr_auc` descending.

### `TournamentResult` (dataclass)

| Field | Description |
|---|---|
| `challenger` | `ModelResult` of the best model |
| `all_results` | List of all 4 `ModelResult`s |
| `comparison_table` | `pd.DataFrame` with all models ranked |
| `tournament_time_seconds` | Total wall-clock time |

---

## 10. Models: ChampionChallenger

**File:** `src/financial_transactions/models/champion_challenger.py`

### Constructor

```python
ChampionChallenger(config: ProjectConfig, spark=None)
```

`model_name` is auto-derived: `f"{catalog}.{schema}.anomaly_model_champion"`

### Methods

#### `compare(challenger_result: ModelResult) → ComparisonResult`
1. Calls `_get_champion_metrics()` — queries MLflow for the model with alias `"champion"`
2. If no champion exists → returns `ComparisonResult(decision="PROMOTE", reason="No existing champion...")` immediately
3. Computes `improvement = {metric: challenger - champion}` for primary + secondary metrics
4. If `improvement[primary_metric] >= min_improvement_threshold` → `"PROMOTE"`, else `"REJECT"`

#### `promote_challenger(challenger_result: ModelResult) → str`
1. `mlflow.register_model(model_uri, name)` — creates new version in UC Model Registry
2. Sets alias `"champion"` → new version
3. Sets alias `"latest-model"` → new version
4. Returns version number as string

#### `log_comparison(result: ComparisonResult)`
Creates MLflow run `"champion-challenger-comparison"`. Logs `decision`, `reason`, and all `improvement_*`, `challenger_*`, `champion_*` metrics.

#### `write_audit_record(result: ComparisonResult, challenger: ModelResult)`
Appends one row to `{catalog}.{schema}.champion_challenger_audit` Delta table with: `timestamp`, `decision`, `reason`, `challenger_model_type`, `challenger_run_id`, `primary_metric_value`, `improvement` (JSON).

### `ComparisonResult` (dataclass)

| Field | Description |
|---|---|
| `decision` | `"PROMOTE"` or `"REJECT"` |
| `reason` | Human-readable explanation |
| `challenger_metrics` | Dict of challenger metric values |
| `champion_metrics` | Dict of champion metric values (empty if first deploy) |
| `improvement` | Dict of `challenger - champion` per metric |
| `timestamp` | UTC ISO timestamp, auto-set on creation |

---

## 11. Monitoring: DriftDetector

**File:** `src/financial_transactions/monitoring/drift_detector.py`

### Constructor

```python
DriftDetector(config: DriftConfig, spark=None)
```

### Methods

#### `compute_psi(reference, current, bins=10) → float` *(static)*
Population Stability Index between two numpy arrays.

**Algorithm:**
1. Create bin edges from `reference` using percentiles (0 to 100, `bins+1` points)
2. Histogram both arrays into those bins
3. Add Laplace smoothing: `(count + 1) / (N + n_bins)`
4. `PSI = Σ (cur_pct - ref_pct) * ln(cur_pct / ref_pct)`

**Interpretation:**
- PSI < 0.1 → no change
- 0.1–0.2 → moderate change
- > 0.2 → significant drift ← triggers alarm

#### `compute_js_divergence(reference: pd.Series, current: pd.Series) → float` *(static)*
Jensen-Shannon divergence for categorical columns.

1. Gets union of all categories
2. Aligns value-count distributions over that union
3. Adds `1e-10` smoothing, normalizes
4. Uses `scipy.spatial.distance.jensenshannon(p, q) ** 2`

**Returns:** 0 (identical) to 1 (completely different). Threshold: `0.1`.

#### `detect_data_drift(reference_df, current_df, numerical_features, categorical_features) → dict`
Runs PSI on each numerical feature and JS divergence on each categorical feature. Sets `overall_drift = True` if ANY feature breaches its threshold.

**Returns:**
```json
{
  "timestamp": "2026-04-11T00:00:00Z",
  "reference_size": 5000,
  "current_size": 1200,
  "feature_drift": {
    "price": {"metric": "psi", "value": 0.045, "threshold": 0.2, "drifted": false},
    "symbol": {"metric": "js_divergence", "value": 0.002, "threshold": 0.1, "drifted": false}
  },
  "drifted_features": [],
  "overall_drift": false
}
```

#### `detect_prediction_drift(reference_preds, current_preds) → dict`
Applies PSI to model output score distributions. Returns `{"prediction_psi": float, "drifted": bool}`.

#### `should_retrain(drift_report, current_performance=None, baseline_performance=None) → bool`
Returns `True` if:
- `drift_report["overall_drift"] is True`, OR
- `pr_auc` degradation > `perf_threshold`, OR
- `f1_score` degradation > `perf_threshold`

#### `write_drift_metrics(drift_report, table_name=None)`
Writes one row to the Delta `drift_monitoring` table:

| Column | Value |
|---|---|
| `timestamp` | UTC ISO string |
| `reference_size` | int |
| `current_size` | int |
| `overall_drift` | bool |
| `drifted_features` | JSON array string |
| `feature_drift_details` | JSON object string |

No-ops if `spark` is `None`.

---

## 12. Monitoring: RetrainingTrigger

**File:** `src/financial_transactions/monitoring/retraining_trigger.py`

### Constructor

```python
RetrainingTrigger(config: RetrainingConfig, spark=None)
```

### Methods

#### `evaluate_trigger_conditions(drift_report=None, current_metrics=None, baseline_metrics=None, new_record_count=0) → bool`
**Step 1 — Collect trigger reasons (OR):**
- Drift detected: `drift_report["overall_drift"] == True`
- Performance degraded: `pr_auc` or `f1_score` diff > 0.05
- Data volume: `new_record_count >= min_new_records`

**Step 2 — Apply guards (AND — both must pass):**
- `check_cooldown()` — must be ≥ `cooldown_hours` since last run
- `_check_daily_limit()` — must be < `max_retrain_per_day` runs today

Returns `True` only if at least one reason AND both guards pass.

#### `check_cooldown() → bool`
Queries `retraining_audit` Delta table for `MAX(timestamp)` where `event_type = 'retraining_triggered'`. Returns `True` (OK to retrain) if elapsed hours ≥ `cooldown_hours` or if the table doesn't exist yet.

#### `trigger_retraining_job(job_id=None)`
Uses `databricks.sdk.WorkspaceClient().jobs.run_now(job_id=int(job_id))` to programmatically trigger the Databricks retraining job. Writes an audit event first via `_write_audit_event("retraining_triggered", ...)`.

#### `_write_audit_event(event_type, details=None)`
Appends a row to `retraining_audit` Delta table with `timestamp`, `event_type`, `details` (JSON).

---

## 13. Monitoring: PerformanceMonitor

**File:** `src/financial_transactions/monitoring/performance_monitor.py`

### Constructor

```python
PerformanceMonitor(config: ProjectConfig, spark, workspace=None)
```

`monitoring_table` = `{catalog}.{schema}.model_monitoring`

### Methods

#### `create_monitoring_table()`
Creates a Databricks Lakehouse Monitor on `model_monitoring` with:
- `problem_type = CLASSIFICATION`
- `prediction_col = "prediction"`, `timestamp_col = "timestamp"`, `model_id_col = "model_name"`
- Granularity: `"30 minutes"`

Enables CDF on the table. No-ops if monitor already exists.

#### `refresh_monitoring()`
Calls `workspace.quality_monitors.run_refresh(table_name=monitoring_table)` to recompute monitor statistics.

#### `compute_live_metrics() → dict`
Aggregates from `model_monitoring`:

| Metric | Query |
|---|---|
| `total_predictions` | COUNT(*) |
| `avg_latency_ms` | AVG(execution_duration_ms) |
| `p99_latency_ms` | PERCENTILE_APPROX(execution_duration_ms, 0.99) |
| `active_models` | COUNT(DISTINCT model_name) |

#### `export_metrics_json(output_dir, additional_data=None)`
Creates directory, calls `compute_live_metrics()`, merges with `additional_data` if provided, writes to `output_dir/performance_timeline.json`.

---

## 14. Monitoring: AlertManager

**File:** `src/financial_transactions/monitoring/alerting.py`

### Constructor

```python
AlertManager(webhook_url=None, spark=None, audit_table=None)
```

All params are optional. Alerts fire to whichever sinks are configured.

### Methods

| Method | Trigger | Message Format |
|---|---|---|
| `send_drift_alert(drift_report)` | Data drift detected | Lists drifted features, reference/current sizes |
| `send_performance_alert(metrics, threshold="")` | Model performance drop | JSON metrics dict + threshold |
| `send_retraining_notification(reason, model_type="")` | Retraining triggered | Reason + model type |
| `send_deployment_notification(version, model_type, decision)` | PROMOTE/REJECT event | Decision + model version |

#### `_send(message, alert_type, data=None)` *(internal)*
1. Logs message via `loguru`
2. If `webhook_url` set: POST `{"text": message}` to webhook (Slack/Teams compatible). Timeout: 10s. Errors swallowed.
3. If `spark` + `audit_table` set: calls `_log_to_delta()`

#### `_log_to_delta(alert_type, message, data)` *(internal)*
Appends row to audit Delta table: `timestamp`, `alert_type`, `message` (truncated to 500 chars), `data` (JSON string).

---

## 15. Serving: AnomalyModelServing

**File:** `src/financial_transactions/serving/model_serving.py`

Manages Databricks Model Serving endpoints.

### Constructor

```python
AnomalyModelServing(model_name: str, endpoint_name: str)
```

Uses `databricks.sdk.WorkspaceClient` for all Databricks API calls.

### Methods

#### `get_latest_model_version() → str`
Calls `mlflow.MlflowClient().get_model_version_by_alias(model_name, alias="champion")`. Returns version number.

#### `deploy_or_update(version="latest", workload_size="Small", scale_to_zero=True)`
- Checks if endpoint exists via `workspace.serving_endpoints.list()`
- If not exists: `workspace.serving_endpoints.create(...)` with 100% traffic to `version`
- If exists: `workspace.serving_endpoints.update_config(...)` with new version

| Param | Default | Description |
|---|---|---|
| `version` | `"latest"` | Model version (or `"latest"` to use champion alias) |
| `workload_size` | `"Small"` | Databricks compute tier: `"Small"`, `"Medium"`, `"Large"` |
| `scale_to_zero` | `True` | Scale down to 0 when no traffic (saves cost) |

#### `deploy_canary(version, canary_pct=10, workload_size="Small")`
Deploys two served entities with split traffic:
- Production version: `(100 - canary_pct)%`
- Canary version: `canary_pct%`

Sets `_canary_version` for tracking.

#### `promote_to_production()`
Calls `deploy_or_update(version=self._canary_version)` to route 100% traffic to canary. Clears `_canary_version`.

#### `rollback(version=None)`
Calls `deploy_or_update(version=rollback_version)` with the specified or last-known production version.

---

## 16. Serving: RollbackManager

**File:** `src/financial_transactions/serving/rollback_manager.py`

Handles emergency rollback of model versions and feature tables.

### Methods

#### `capture_state(model_version, endpoint_name) → dict`
Snapshots: `timestamp`, `model_version`, `endpoint_name`, `catalog`, `schema`, and `feature_table_version` (via Delta history query). Stores in `_snapshots` list.

#### `rollback_model(version: str)`
Creates an `AnomalyModelServing` instance and calls `serving.rollback(version=version)`.

#### `rollback_features(version: int)`
Executes `RESTORE TABLE {table} TO VERSION AS OF {version}` via SparkSession. Uses Delta **Time Travel** — works instantly without data movement.

#### `verify_rollback(expected_version=None) → bool`
Calls `mlflow.MlflowClient().get_model_version_by_alias(model_name, "champion")`. If `expected_version` provided, checks it matches. Returns `True`/`False`.

#### `get_rollback_history() → list[dict]`
Returns copy of `_snapshots` — all state captures made during this session.

---

## 17. Serving: ABTestManager

**File:** `src/financial_transactions/serving/ab_testing.py`

Lifecycle management for A/B tests between model versions.

### Methods

#### `create_experiment(control_version, treatment_version, traffic_split=50) → dict`
Creates an experiment record with:
- Auto-generated ID: `"ab_YYYYMMDD_HHMMSS"`
- `control_version`, `treatment_version`, `traffic_split` (treatment %)
- `status = "running"`, empty `control_metrics` and `treatment_metrics`

Appends to `_experiments` list.

#### `monitor_experiment(experiment_id=None) → dict`
Returns current state of the experiment. In production, this would query the inference log table. Returns `{"control": {}, "treatment": {}}` structure.

#### `conclude_experiment(experiment_id=None, min_samples=1000) → dict`
Compares `pr_auc` of control vs treatment:
- Treatment `pr_auc` > control → `"PROMOTE_TREATMENT"`
- Otherwise → `"KEEP_CONTROL"`
- No metrics available → `"NEEDS_MORE_DATA"`

Sets `status = "concluded"`, stores `conclusion` in the experiment dict.

#### `_get_experiment(experiment_id) → dict | None` *(internal)*
Returns experiment by ID, or the most recent if `experiment_id` is `None`.

---

## 18. `project_config.yml` — All Fields

Location: project root. Loaded by `ProjectConfig.from_yaml()`.

### Environment Blocks

```yaml
prd:
  catalog_name: mlops_prd
  schema_name: financial_transactions
acc:
  catalog_name: mlops_acc
  schema_name: financial_transactions
dev:
  catalog_name: mlops_dev
  schema_name: financial_transactions
```

### MLflow Experiments

```yaml
experiment_name_basic: /Shared/financial-anomaly-basic  # Main tournament runs
experiment_name_custom: /Shared/financial-anomaly-custom  # Custom model runs
```

### Model Hyperparameters

```yaml
parameters:               # LightGBM defaults
  learning_rate: 0.01
  n_estimators: 1500
  max_depth: 8
  num_leaves: 63
  min_child_samples: 20
  colsample_bytree: 0.8
  subsample: 0.8
  reg_alpha: 0.1
  reg_lambda: 1.0

models:
  lightgbm:
    scale_pos_weight: 10  # Handles class imbalance (anomalies are rare)
    ...
  xgboost:
    eval_metric: aucpr    # Area under PR curve (better for imbalanced)
    tree_method: hist
    ...
  random_forest:
    class_weight: balanced  # Sklearn auto-adjusts for imbalance
    ...
  isolation_forest:
    contamination: 0.015    # Expected anomaly rate ≈ 1.5%
    ...
```

### Feature Lists

```yaml
num_features:   # fed to PSI drift detection + all supervised models
  - price
  - volume
  - price_change_pct
  - volume_zscore
  - price_volatility_1h
  - trade_intensity_1m
  - vwap_deviation
  - bid_ask_spread_pct
  - rsi_14
  - macd_signal
  - bollinger_position
  - hour_of_day
  - minute_of_hour

cat_features:   # fed to JS divergence drift detection + label-encoded in models
  - symbol
  - exchange
  - trade_type
  - session_type

target: is_anomaly  # Binary 0/1 label
```

### Champion/Challenger Config

```yaml
champion_challenger:
  primary_metric: pr_auc              # Sole decision metric
  secondary_metrics: [f1_score, precision, recall]  # Reported, not decisive
  min_improvement_threshold: 0.005    # 0.5% PR-AUC improvement required
  require_all_metrics_improvement: false
```

### Streaming Config

```yaml
streaming:
  finnhub_api_key: ${FINNHUB_API_KEY}  # Injected at runtime
  finnhub_ws_url: wss://ws.finnhub.io
  finnhub_symbols: [AAPL, MSFT, GOOGL, AMZN, TSLA, META, NVDA, JPM, BAC, GS]
  batch_interval_seconds: 30           # Flush buffer every 30s
  checkpoint_base: /Workspace/checkpoints/financial-anomaly
  max_records_per_batch: 1000          # Flush immediately at 1000 records
  watermark_delay: "2 minutes"         # Drop Spark late-arriving records
  landing_zone_path: dbfs:/Volumes/mlops_dev/financial_transactions/streaming_landing/trades
```

### Historical Config

```yaml
historical:
  alphavantage_api_key: ${ALPHAVANTAGE_API_KEY}
  alphavantage_base_url: https://www.alphavantage.co/query
  symbols: [AAPL, MSFT, GOOGL, AMZN, TSLA]
  interval: 5min          # 5-minute OHLCV bars
  outputsize: full        # Full history (not just last 100 bars)
  rate_limit_sleep: 12    # 12s between calls = 5 req/min (free tier limit)
  max_calls_per_day: 25
```

### Drift Config

```yaml
drift:
  reference_window_days: 30           # Use last 30 days of data as baseline
  detection_interval_minutes: 60      # Informational — actual schedule in drift_monitoring.yml
  psi_threshold: 0.2                  # PSI > 0.2 = numerical feature drifted
  js_divergence_threshold: 0.1        # JS > 0.1 = categorical feature drifted
  performance_degradation_threshold: 0.05  # 5% PR-AUC drop triggers retrain
```

### Retraining Config

```yaml
retraining:
  min_new_records: 5000     # Need at least 5,000 new trades to trigger volume-based retrain
  cooldown_hours: 6         # No two retraining runs within 6 hours
  max_retrain_per_day: 4    # Hard cap of 4 retraining jobs per day
```

---

## 19. `databricks.yml` — All Variables & Targets

Location: project root. Defines the Databricks Asset Bundle.

### Bundle Variables

| Variable | Default | Description |
|---|---|---|
| `git_sha` | `"abcd"` | Git commit SHA — passed to notebooks as `base_parameters` |
| `branch` | `"main"` | Git branch name |
| `schedule_pause_status` | `"PAUSED"` | `PAUSED` or `UNPAUSED` — controls all job schedules |
| `finnhub_api_key` | `""` | Provided at deploy time via `--var` flag |
| `alphavantage_api_key` | `""` | Provided at deploy time via `--var` flag |
| `stream_checkpoint_path` | `"/Workspace/checkpoints/financial-anomaly"` | Spark streaming checkpoint base |
| `catalog_name` | `"mlops_dev"` | Unity Catalog name (overridden per target) |
| `schema_name` | `"financial_transactions"` | Schema name (same across all envs) |

### Targets

| Target | Mode | Workspace Host | Catalog | Root Path |
|---|---|---|---|---|
| `dev` (default) | `development` | `https://8259560517811498.8.gcp.databricks.com` | `mlops_dev` | `~/.bundle/dev/financial-ai-mlops` |
| `acc` | — | same workspace | `mlops_acc` | `/Workspace/Shared/.bundle/acc/financial-ai-mlops` |
| `prd` | `production` | same workspace | `mlops_prd` | `/Workspace/Shared/.bundle/prd/financial-ai-mlops` |

> **Note:** All three targets share the same workspace URL. In a true multi-workspace setup, each target would have a different `host`.

> [!IMPORTANT]
> `schedule_pause_status` defaults to `PAUSED` in all environments (including prd). Change prd to `UNPAUSED` after validating all pipelines are stable.
