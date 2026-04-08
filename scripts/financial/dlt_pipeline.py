"""
Financial Streaming DLT Pipeline Entrypoint

Defines Bronze, Silver, and Gold DLT tables in a single file so pipeline
parsing always discovers table definitions.
"""

import dlt
from pyspark.sql.types import DoubleType, StringType, StructField, StructType, TimestampType
from pyspark.sql import Window
from pyspark.sql import functions as F

STREAMING_SOURCE_PATH = spark.conf.get(
    "financial.streaming_source_path",
    "dbfs:/Volumes/mlops_dev/financial_transactions/streaming_landing/trades",
)
TRADE_SCHEMA = StructType(
    [
        StructField("trade_id", StringType(), True),
        StructField("symbol", StringType(), True),
        StructField("price", DoubleType(), True),
        StructField("volume", DoubleType(), True),
        StructField("timestamp", TimestampType(), True),
        StructField("exchange", StringType(), True),
    ]
)


@dlt.table(
    name="bronze_trades",
    comment="Raw financial trade data ingested from streaming landing zone via Auto Loader",
    table_properties={
        "quality": "bronze",
        "delta.enableChangeDataFeed": "true",
        "pipelines.autoOptimize.zOrderCols": "symbol,timestamp",
    },
)
def bronze_trades():
    """Ingest raw trade data using Auto Loader."""
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .schema(TRADE_SCHEMA)
        .load(STREAMING_SOURCE_PATH)
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source_file", F.col("_metadata.file_path"))
    )


@dlt.table(
    name="silver_trades",
    comment="Cleaned and enriched trade data with quality expectations applied",
    table_properties={
        "quality": "silver",
        "delta.enableChangeDataFeed": "true",
    },
)
@dlt.expect_or_drop("valid_price", "price > 0")
@dlt.expect_or_drop("valid_symbol", "symbol IS NOT NULL AND symbol != ''")
@dlt.expect_or_fail("valid_timestamp", "timestamp IS NOT NULL")
@dlt.expect("valid_volume", "volume >= 0")
def silver_trades():
    """Clean and enrich Bronze trade data."""
    bronze = dlt.read_stream("bronze_trades")

    return (
        bronze.dropDuplicates(["trade_id"])
        .withColumn("price", F.col("price").cast("double"))
        .withColumn("volume", F.col("volume").cast("double"))
        .withColumn("timestamp", F.to_timestamp(F.col("timestamp")))
        .withColumn("hour_of_day", F.hour(F.col("timestamp")))
        .withColumn("minute_of_hour", F.minute(F.col("timestamp")))
        .withColumn("day_of_week", F.dayofweek(F.col("timestamp")))
        .withColumn("is_weekend", F.when(F.dayofweek(F.col("timestamp")).isin(1, 7), True).otherwise(False))
        .withColumn(
            "session_type",
            F.when((F.hour(F.col("timestamp")) >= 14) & (F.hour(F.col("timestamp")) < 21), "regular")
            .when(F.hour(F.col("timestamp")) < 14, "pre_market")
            .otherwise("after_hours"),
        )
        .withColumn(
            "trade_type",
            F.when(F.col("volume") >= 10000, "block").when(F.col("volume") >= 100, "standard").otherwise("odd_lot"),
        )
        .fillna({"volume": 0.0, "exchange": "US"})
        .withColumn("_processed_at", F.current_timestamp())
    )


@dlt.table(
    name="gold_trade_features",
    comment="Aggregated trade features with windowed metrics and technical indicators per symbol",
    table_properties={
        "quality": "gold",
        "delta.enableChangeDataFeed": "true",
    },
)
def gold_trade_features():
    """Compute Gold-layer features from Silver trade data."""
    silver = dlt.read("silver_trades")

    symbol_time_window = Window.partitionBy("symbol").orderBy("timestamp")
    symbol_rows_14 = Window.partitionBy("symbol").orderBy("timestamp").rowsBetween(-13, 0)

    return (
        silver.withColumn("prev_price", F.lag("price", 1).over(symbol_time_window))
        .withColumn(
            "price_change_pct",
            F.when(
                F.col("prev_price").isNotNull() & (F.col("prev_price") > 0),
                ((F.col("price") - F.col("prev_price")) / F.col("prev_price")) * 100,
            ).otherwise(0.0),
        )
        .withColumn("rolling_avg_price_14", F.avg("price").over(symbol_rows_14))
        .withColumn("rolling_std_price_14", F.stddev("price").over(symbol_rows_14))
        .withColumn("rolling_avg_volume_14", F.avg("volume").over(symbol_rows_14))
        .withColumn("rolling_std_volume_14", F.stddev("volume").over(symbol_rows_14))
        .withColumn(
            "volume_zscore",
            F.when(
                F.col("rolling_std_volume_14").isNotNull() & (F.col("rolling_std_volume_14") > 0),
                (F.col("volume") - F.col("rolling_avg_volume_14")) / F.col("rolling_std_volume_14"),
            ).otherwise(0.0),
        )
        .withColumn("price_volatility_1h", F.coalesce(F.col("rolling_std_price_14"), F.lit(0.0)))
        .withColumn("trade_intensity_1m", F.count("*").over(symbol_rows_14))
        .withColumn(
            "vwap_14",
            F.when(
                F.sum("volume").over(symbol_rows_14) > 0,
                F.sum(F.col("price") * F.col("volume")).over(symbol_rows_14) / F.sum("volume").over(symbol_rows_14),
            ).otherwise(F.col("price")),
        )
        .withColumn(
            "vwap_deviation",
            F.when(F.col("vwap_14") > 0, ((F.col("price") - F.col("vwap_14")) / F.col("vwap_14")) * 100).otherwise(0.0),
        )
        .withColumn("price_diff", F.col("price") - F.coalesce(F.col("prev_price"), F.col("price")))
        .withColumn("gain", F.when(F.col("price_diff") > 0, F.col("price_diff")).otherwise(0.0))
        .withColumn("loss", F.when(F.col("price_diff") < 0, F.abs(F.col("price_diff"))).otherwise(0.0))
        .withColumn("avg_gain", F.avg("gain").over(symbol_rows_14))
        .withColumn("avg_loss", F.avg("loss").over(symbol_rows_14))
        .withColumn(
            "rsi_14",
            F.when(F.col("avg_loss") > 0, 100 - (100 / (1 + F.col("avg_gain") / F.col("avg_loss")))).otherwise(50.0),
        )
        .withColumn("upper_band", F.col("rolling_avg_price_14") + 2 * F.col("rolling_std_price_14"))
        .withColumn("lower_band", F.col("rolling_avg_price_14") - 2 * F.col("rolling_std_price_14"))
        .withColumn(
            "bollinger_position",
            F.when(
                (F.col("upper_band") - F.col("lower_band")) > 0,
                (F.col("price") - F.col("lower_band")) / (F.col("upper_band") - F.col("lower_band")),
            ).otherwise(0.5),
        )
        .withColumn("ema_12", F.avg("price").over(Window.partitionBy("symbol").orderBy("timestamp").rowsBetween(-11, 0)))
        .withColumn("ema_26", F.avg("price").over(Window.partitionBy("symbol").orderBy("timestamp").rowsBetween(-25, 0)))
        .withColumn("macd_signal", F.col("ema_12") - F.col("ema_26"))
        .withColumn(
            "bid_ask_spread_pct",
            F.when(F.col("price") > 0, (F.col("rolling_std_price_14") / F.col("price")) * 100).otherwise(0.0),
        )
        .select(
            "trade_id",
            "symbol",
            "price",
            "volume",
            "timestamp",
            "exchange",
            "hour_of_day",
            "minute_of_hour",
            "day_of_week",
            "session_type",
            "trade_type",
            "price_change_pct",
            "volume_zscore",
            "price_volatility_1h",
            "trade_intensity_1m",
            "vwap_deviation",
            "rsi_14",
            "macd_signal",
            "bollinger_position",
            "bid_ask_spread_pct",
            "_processed_at",
        )
        .fillna(
            0.0,
            subset=[
                "price_change_pct",
                "volume_zscore",
                "price_volatility_1h",
                "trade_intensity_1m",
                "vwap_deviation",
                "rsi_14",
                "macd_signal",
                "bollinger_position",
                "bid_ask_spread_pct",
            ],
        )
    )
