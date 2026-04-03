"""Tests for streaming data transformations."""

from datetime import datetime, timezone
from typing import Any

import pandas as pd
from pyspark.sql import SparkSession

from financial_transactions.config import StreamingConfig
from financial_transactions.streaming.stream_processor import StreamProcessor


def test_transform_bronze_to_silver(spark: SparkSession) -> None:
    """Test the streaming Bronze to Silver transformation logic."""
    from pyspark.sql import functions as F
    from pyspark.sql.types import (
        DoubleType, StringType, StructField, StructType, TimestampType
    )
    
    schema = StructType([
        StructField("trade_id", StringType(), False),
        StructField("symbol", StringType(), False),
        StructField("price", DoubleType(), False),
        StructField("volume", DoubleType(), True),
        StructField("timestamp", TimestampType(), False),
        StructField("exchange", StringType(), True),
        StructField("ingestion_timestamp", TimestampType(), True),
    ])
    
    now = datetime(2026, 4, 1, 15, 30, 0, tzinfo=timezone.utc)  # Regular session
    pre_market = datetime(2026, 4, 1, 8, 30, 0, tzinfo=timezone.utc)
    
    data = [
        # Normal
        ("1", "AAPL", 150.0, 100.0, now, "US", now),
        # Block trade
        ("2", "MSFT", 300.0, 15000.0, now, "US", now),
        # Pre-market
        ("3", "GOOGL", 100.0, 50.0, pre_market, "US", now),
        # Invalid price (should drop)
        ("4", "AMZN", -10.0, 10.0, now, "US", now),
        # Duplicate trade_id (should dedup)
        ("1", "AAPL", 150.0, 100.0, now, "US", now),
    ]
    
    df = spark.createDataFrame(data, schema=schema)
    
    config = StreamingConfig()
    processor = StreamProcessor(config, spark)
    
    res_df = processor.transform_bronze_to_silver(df)
    res = res_df.toPandas()
    
    # Assertions
    assert len(res) == 3  # Dropped invalid price, dropped duplicate
    
    # Check derived fields
    aapl = res[res["trade_id"] == "1"].iloc[0]
    assert aapl["session_type"] == "regular"
    assert aapl["trade_type"] == "standard"
    assert aapl["hour_of_day"] == 15
    assert aapl["minute_of_hour"] == 30
    
    msft = res[res["trade_id"] == "2"].iloc[0]
    assert msft["trade_type"] == "block"
    
    googl = res[res["trade_id"] == "3"].iloc[0]
    assert googl["session_type"] == "pre_market"
    assert googl["trade_type"] == "odd_lot"
