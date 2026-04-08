# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze Ingest — Raw Trade Data
# MAGIC
# MAGIC Ingests raw financial trade data from the streaming landing zone
# MAGIC using Auto Loader (cloudFiles) into the Bronze layer.

import dlt
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, StringType, StructField, StructType, TimestampType

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
    """Ingest raw trade data using Auto Loader.

    Reads JSON files from the streaming landing zone with explicit schema.
    All raw fields are preserved for downstream processing.
    """
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .schema(TRADE_SCHEMA)
        .load(STREAMING_SOURCE_PATH)
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source_file", F.col("_metadata.file_path"))
    )
