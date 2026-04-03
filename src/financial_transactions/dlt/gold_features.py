# Databricks notebook source
# MAGIC %md
# MAGIC # Gold Features — Aggregated Trade Features
# MAGIC
# MAGIC Computes windowed aggregations and technical indicators per symbol,
# MAGIC producing the Gold feature layer for model training and serving.

import dlt
from pyspark.sql import Window, functions as F


@dlt.table(
    name="gold_trade_features",
    comment="Aggregated trade features with windowed metrics and technical indicators per symbol",
    table_properties={
        "quality": "gold",
        "delta.enableChangeDataFeed": "true",
    },
)
def gold_trade_features():
    """Compute Gold-layer features from Silver trade data.

    Windowed aggregations per symbol:
    - price_volatility_1h: standard deviation of price over 1 hour
    - trade_intensity_1m: trade count per minute window
    - vwap_deviation: deviation from volume-weighted average price
    - volume_zscore: z-score of volume vs rolling mean
    - price_change_pct: percentage price change from previous trade
    - rsi_14: Relative Strength Index (14-period approximation)
    - macd_signal: MACD line approximation
    - bollinger_position: position within Bollinger Bands
    """
    silver = dlt.read_stream("silver_trades")

    # Define window specs
    symbol_time_window = Window.partitionBy("symbol").orderBy("timestamp")
    symbol_rows_14 = Window.partitionBy("symbol").orderBy("timestamp").rowsBetween(-13, 0)
    symbol_rows_50 = Window.partitionBy("symbol").orderBy("timestamp").rowsBetween(-49, 0)

    return (
        silver
        # Price change from previous trade
        .withColumn("prev_price", F.lag("price", 1).over(symbol_time_window))
        .withColumn("price_change_pct", F.when(
            F.col("prev_price").isNotNull() & (F.col("prev_price") > 0),
            ((F.col("price") - F.col("prev_price")) / F.col("prev_price")) * 100
        ).otherwise(0.0))
        # Rolling statistics (14-period windows)
        .withColumn("rolling_avg_price_14", F.avg("price").over(symbol_rows_14))
        .withColumn("rolling_std_price_14", F.stddev("price").over(symbol_rows_14))
        .withColumn("rolling_avg_volume_14", F.avg("volume").over(symbol_rows_14))
        .withColumn("rolling_std_volume_14", F.stddev("volume").over(symbol_rows_14))
        # Volume z-score
        .withColumn("volume_zscore", F.when(
            F.col("rolling_std_volume_14").isNotNull() & (F.col("rolling_std_volume_14") > 0),
            (F.col("volume") - F.col("rolling_avg_volume_14")) / F.col("rolling_std_volume_14")
        ).otherwise(0.0))
        # Price volatility (rolling std as proxy for 1h volatility)
        .withColumn("price_volatility_1h", F.coalesce(F.col("rolling_std_price_14"), F.lit(0.0)))
        # Trade intensity (count in rolling window)
        .withColumn("trade_intensity_1m", F.count("*").over(symbol_rows_14))
        # VWAP deviation
        .withColumn("vwap_14", F.when(
            F.sum("volume").over(symbol_rows_14) > 0,
            F.sum(F.col("price") * F.col("volume")).over(symbol_rows_14) /
            F.sum("volume").over(symbol_rows_14)
        ).otherwise(F.col("price")))
        .withColumn("vwap_deviation", F.when(
            F.col("vwap_14") > 0,
            ((F.col("price") - F.col("vwap_14")) / F.col("vwap_14")) * 100
        ).otherwise(0.0))
        # RSI approximation (14-period)
        .withColumn("price_diff", F.col("price") - F.coalesce(F.col("prev_price"), F.col("price")))
        .withColumn("gain", F.when(F.col("price_diff") > 0, F.col("price_diff")).otherwise(0.0))
        .withColumn("loss", F.when(F.col("price_diff") < 0, F.abs(F.col("price_diff"))).otherwise(0.0))
        .withColumn("avg_gain", F.avg("gain").over(symbol_rows_14))
        .withColumn("avg_loss", F.avg("loss").over(symbol_rows_14))
        .withColumn("rsi_14", F.when(
            F.col("avg_loss") > 0,
            100 - (100 / (1 + F.col("avg_gain") / F.col("avg_loss")))
        ).otherwise(50.0))
        # Bollinger Band position
        .withColumn("upper_band", F.col("rolling_avg_price_14") + 2 * F.col("rolling_std_price_14"))
        .withColumn("lower_band", F.col("rolling_avg_price_14") - 2 * F.col("rolling_std_price_14"))
        .withColumn("bollinger_position", F.when(
            (F.col("upper_band") - F.col("lower_band")) > 0,
            (F.col("price") - F.col("lower_band")) / (F.col("upper_band") - F.col("lower_band"))
        ).otherwise(0.5))
        # MACD approximation (fast EMA - slow EMA proxy)
        .withColumn("ema_12", F.avg("price").over(
            Window.partitionBy("symbol").orderBy("timestamp").rowsBetween(-11, 0)
        ))
        .withColumn("ema_26", F.avg("price").over(
            Window.partitionBy("symbol").orderBy("timestamp").rowsBetween(-25, 0)
        ))
        .withColumn("macd_signal", F.col("ema_12") - F.col("ema_26"))
        # Bid-ask spread proxy (high-low range as percentage)
        .withColumn("bid_ask_spread_pct", F.when(
            F.col("price") > 0,
            (F.col("rolling_std_price_14") / F.col("price")) * 100
        ).otherwise(0.0))
        # Select final feature columns
        .select(
            "trade_id", "symbol", "price", "volume", "timestamp",
            "exchange", "hour_of_day", "minute_of_hour", "day_of_week",
            "session_type", "trade_type",
            "price_change_pct", "volume_zscore", "price_volatility_1h",
            "trade_intensity_1m", "vwap_deviation", "rsi_14",
            "macd_signal", "bollinger_position", "bid_ask_spread_pct",
            "_processed_at",
        )
        # Fill any remaining nulls from window edges
        .fillna(0.0, subset=[
            "price_change_pct", "volume_zscore", "price_volatility_1h",
            "trade_intensity_1m", "vwap_deviation", "rsi_14",
            "macd_signal", "bollinger_position", "bid_ask_spread_pct",
        ])
    )
