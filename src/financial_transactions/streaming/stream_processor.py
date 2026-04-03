"""Structured Streaming processor for financial trade data.

Reads from a Delta landing zone (written by FinnhubCollector),
applies Bronze → Silver transformations, and writes to downstream
Delta tables with checkpoint management.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from financial_transactions.config import StreamingConfig


class StreamProcessor:
    """Process streaming trade data through the medallion architecture.

    Reads from a Delta landing zone using Structured Streaming,
    applies schema validation, deduplication, and enrichment,
    then writes to Silver Delta tables.

    Usage:
        processor = StreamProcessor(config, spark)
        processor.start_bronze_to_silver()
    """

    def __init__(self, config: StreamingConfig, spark: Any) -> None:
        """Initialize the stream processor.

        :param config: Streaming configuration
        :param spark: SparkSession with streaming support
        """
        self.config = config
        self.spark = spark
        self.checkpoint_base = config.checkpoint_base
        self.landing_zone = config.landing_zone_path
        self.trigger_interval = f"{config.batch_interval_seconds} seconds"
        self._active_queries: list[Any] = []

    def read_landing_zone(self) -> Any:
        """Read streaming data from the Delta landing zone.

        :return: Streaming DataFrame from the landing zone
        """
        from pyspark.sql.types import (
            DoubleType,
            StringType,
            StructField,
            StructType,
            TimestampType,
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

        logger.info(f"Reading stream from landing zone: {self.landing_zone}")
        return (
            self.spark.readStream
            .format("delta")
            .schema(schema)
            .option("maxFilesPerTrigger", self.config.max_records_per_batch)
            .load(self.landing_zone)
        )

    def transform_bronze_to_silver(self, bronze_df: Any) -> Any:
        """Apply Bronze → Silver transformations.

        - Deduplication by trade_id
        - Null handling for optional fields
        - Timestamp enrichment (hour, minute, day_of_week, session type)
        - Price/volume validation

        :param bronze_df: Raw streaming DataFrame from landing zone
        :return: Transformed streaming DataFrame
        """
        from pyspark.sql import functions as F

        silver_df = (
            bronze_df
            # Drop duplicates by trade_id
            .dropDuplicates(["trade_id"])
            # Filter invalid records
            .filter(F.col("price") > 0)
            .filter(F.col("symbol").isNotNull())
            # Enrich with time features
            .withColumn("hour_of_day", F.hour(F.col("timestamp")))
            .withColumn("minute_of_hour", F.minute(F.col("timestamp")))
            .withColumn("day_of_week", F.dayofweek(F.col("timestamp")))
            .withColumn("is_weekend", F.when(
                F.dayofweek(F.col("timestamp")).isin(1, 7), True
            ).otherwise(False))
            # Derive session type based on market hours (EST)
            .withColumn("session_type", F.when(
                (F.hour(F.col("timestamp")) >= 9) & (F.hour(F.col("timestamp")) < 16),
                "regular"
            ).when(
                F.hour(F.col("timestamp")) < 9,
                "pre_market"
            ).otherwise("after_hours"))
            # Derive trade type from volume
            .withColumn("trade_type", F.when(
                F.col("volume") >= 10000, "block"
            ).when(
                F.col("volume") >= 100, "standard"
            ).otherwise("odd_lot"))
            # Fill nulls
            .fillna({"volume": 0.0, "exchange": "US"})
            # Add processing timestamp
            .withColumn("processed_timestamp", F.current_timestamp())
            # Apply watermark for late-arriving data
            .withWatermark("timestamp", self.config.watermark_delay)
        )

        return silver_df

    def start_bronze_to_silver(
        self,
        output_table: str | None = None,
        output_path: str | None = None,
    ) -> Any:
        """Start the Bronze → Silver streaming pipeline.

        :param output_table: Delta table name for Silver output
        :param output_path: Delta path for Silver output (if not using table)
        :return: StreamingQuery handle
        """
        bronze_df = self.read_landing_zone()
        silver_df = self.transform_bronze_to_silver(bronze_df)

        checkpoint_path = f"{self.checkpoint_base}/bronze_to_silver"

        writer = (
            silver_df.writeStream
            .format("delta")
            .outputMode("append")
            .option("checkpointLocation", checkpoint_path)
            .trigger(processingTime=self.trigger_interval)
        )

        if output_table:
            query = writer.toTable(output_table)
        elif output_path:
            query = writer.start(output_path)
        else:
            raise ValueError("Either output_table or output_path must be specified")

        self._active_queries.append(query)
        logger.info(f"Started Bronze → Silver streaming pipeline (trigger: {self.trigger_interval})")
        return query

    def stop_all(self) -> None:
        """Stop all active streaming queries."""
        for query in self._active_queries:
            try:
                query.stop()
            except Exception:
                logger.warning(f"Error stopping query: {query.name}")
        self._active_queries.clear()
        logger.info("All streaming queries stopped")

    @staticmethod
    def compute_batch_quality_metrics(batch_df: Any, batch_id: int) -> dict[str, Any]:
        """Compute quality metrics for a micro-batch (for foreachBatch).

        :param batch_df: Micro-batch DataFrame
        :param batch_id: Micro-batch ID
        :return: Dictionary of quality metrics
        """
        from pyspark.sql import functions as F

        count = batch_df.count()
        if count == 0:
            return {"batch_id": batch_id, "count": 0}

        metrics = batch_df.agg(
            F.count("*").alias("record_count"),
            F.countDistinct("symbol").alias("symbol_count"),
            F.avg("price").alias("avg_price"),
            F.stddev("price").alias("stddev_price"),
            F.sum("volume").alias("total_volume"),
            F.min("timestamp").alias("min_timestamp"),
            F.max("timestamp").alias("max_timestamp"),
        ).collect()[0]

        return {
            "batch_id": batch_id,
            "record_count": metrics["record_count"],
            "symbol_count": metrics["symbol_count"],
            "avg_price": float(metrics["avg_price"] or 0),
            "stddev_price": float(metrics["stddev_price"] or 0),
            "total_volume": float(metrics["total_volume"] or 0),
        }
