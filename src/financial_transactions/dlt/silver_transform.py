# Databricks notebook source
# MAGIC %md
# MAGIC # Silver Transform — Cleaned & Enriched Trades
# MAGIC
# MAGIC Applies data quality expectations, deduplication, type casting,
# MAGIC and temporal enrichment to produce the Silver layer.

import dlt
from pyspark.sql import functions as F


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
    """Clean and enrich Bronze trade data.

    Applies:
    - Data quality expectations (drop invalid price/symbol, fail on null timestamp)
    - Deduplication by trade_id
    - Temporal feature extraction (hour, minute, day_of_week, session type)
    - Trade type classification by volume
    """
    bronze = dlt.read_stream("bronze_trades")

    return (
        bronze.dropDuplicates(["trade_id"])
        # Cast types
        .withColumn("price", F.col("price").cast("double"))
        .withColumn("volume", F.col("volume").cast("double"))
        .withColumn("timestamp", F.to_timestamp(F.col("timestamp")))
        # Temporal features
        .withColumn("hour_of_day", F.hour(F.col("timestamp")))
        .withColumn("minute_of_hour", F.minute(F.col("timestamp")))
        .withColumn("day_of_week", F.dayofweek(F.col("timestamp")))
        .withColumn("is_weekend", F.when(F.dayofweek(F.col("timestamp")).isin(1, 7), True).otherwise(False))
        # Session type (US market hours in UTC: 14:30 - 21:00)
        .withColumn(
            "session_type",
            F.when((F.hour(F.col("timestamp")) >= 14) & (F.hour(F.col("timestamp")) < 21), "regular")
            .when(F.hour(F.col("timestamp")) < 14, "pre_market")
            .otherwise("after_hours"),
        )
        # Trade type classification
        .withColumn(
            "trade_type",
            F.when(F.col("volume") >= 10000, "block").when(F.col("volume") >= 100, "standard").otherwise("odd_lot"),
        )
        # Fill nulls
        .fillna({"volume": 0.0, "exchange": "US"})
        .withColumn("_processed_at", F.current_timestamp())
    )
