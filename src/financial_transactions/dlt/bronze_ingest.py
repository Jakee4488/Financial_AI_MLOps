# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze Ingest — Raw Trade Data
# MAGIC
# MAGIC Ingests raw financial trade data from the streaming landing zone
# MAGIC using Auto Loader (cloudFiles) into the Bronze layer.

import dlt
from pyspark.sql import functions as F

STREAMING_SOURCE_PATH = spark.conf.get(
    "financial.streaming_source_path",
    "dbfs:/Volumes/mlops_dev/financial_transactions/streaming_landing/trades",
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

    Reads JSON files from the streaming landing zone with schema inference.
    All raw fields are preserved for downstream processing.
    """
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.inferColumnTypes", "true")
        .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
        .load(STREAMING_SOURCE_PATH)
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source_file", F.input_file_name())
    )
