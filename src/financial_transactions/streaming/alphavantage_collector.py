"""Alpha Vantage REST API collector for historical OHLCV data.

Fetches intraday stock price data from Alpha Vantage, respecting free-tier
rate limits (5 calls/min, 25 calls/day), and writes to Delta tables
for model training backfill.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests
from loguru import logger

from financial_transactions.config import HistoricalConfig


class AlphaVantageCollector:
    """Collect historical OHLCV data from Alpha Vantage REST API.

    Handles rate limiting, data transformation, and writes to Delta tables
    or local storage for offline model training.

    Usage:
        collector = AlphaVantageCollector(config, spark)
        df = collector.fetch_all_symbols()
        collector.save_to_delta(df)
    """

    def __init__(
        self,
        config: HistoricalConfig,
        spark: Any | None = None,
        output_path: str | None = None,
    ) -> None:
        """Initialize the Alpha Vantage collector.

        :param config: Historical data configuration
        :param spark: SparkSession for Delta writes (None for local mode)
        :param output_path: Override output path for historical data
        """
        self.config = config
        self.spark = spark
        self.output_path = output_path or "/mnt/historical/trades"
        self.api_key = config.alphavantage_api_key
        self.base_url = config.alphavantage_base_url
        self.symbols = config.symbols
        self.interval = config.interval
        self.outputsize = config.outputsize
        self.rate_limit_sleep = config.rate_limit_sleep
        self._call_count = 0

    def fetch_symbol(self, symbol: str) -> pd.DataFrame:
        """Fetch intraday OHLCV data for a single symbol.

        :param symbol: Stock ticker symbol (e.g., 'AAPL')
        :return: DataFrame with OHLCV data
        """
        logger.info(f"Fetching {self.interval} data for {symbol}...")

        params = {
            "function": "TIME_SERIES_INTRADAY",
            "symbol": symbol,
            "interval": self.interval,
            "outputsize": self.outputsize,
            "apikey": self.api_key,
            "datatype": "json",
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Check for API errors
            if "Error Message" in data:
                logger.error(f"API error for {symbol}: {data['Error Message']}")
                return pd.DataFrame()

            if "Note" in data:
                logger.warning(f"Rate limit hit: {data['Note']}")
                return pd.DataFrame()

            # Parse the time series data
            time_series_key = f"Time Series ({self.interval})"
            if time_series_key not in data:
                logger.warning(f"No data found for {symbol}")
                return pd.DataFrame()

            time_series = data[time_series_key]
            records = []
            for timestamp_str, values in time_series.items():
                records.append({
                    "symbol": symbol,
                    "timestamp": timestamp_str,
                    "open": float(values["1. open"]),
                    "high": float(values["2. high"]),
                    "low": float(values["3. low"]),
                    "close": float(values["4. close"]),
                    "volume": int(values["5. volume"]),
                    "interval": self.interval,
                    "fetch_timestamp": datetime.now(tz=timezone.utc).isoformat(),
                })

            df = pd.DataFrame(records)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            logger.info(f"Fetched {len(df)} records for {symbol}")

            self._call_count += 1
            return df

        except requests.RequestException:
            logger.exception(f"Request failed for {symbol}")
            return pd.DataFrame()

    def fetch_all_symbols(self) -> pd.DataFrame:
        """Fetch data for all configured symbols with rate limiting.

        :return: Combined DataFrame with OHLCV data for all symbols
        """
        all_dfs = []
        for i, symbol in enumerate(self.symbols):
            df = self.fetch_symbol(symbol)
            if not df.empty:
                all_dfs.append(df)

            # Rate limiting: sleep between calls (except after the last one)
            if i < len(self.symbols) - 1:
                logger.info(
                    f"Rate limiting: sleeping {self.rate_limit_sleep}s "
                    f"({self._call_count}/{self.config.max_calls_per_day} daily calls used)"
                )
                time.sleep(self.rate_limit_sleep)

        if not all_dfs:
            logger.warning("No data fetched for any symbol")
            return pd.DataFrame()

        combined = pd.concat(all_dfs, ignore_index=True)
        logger.info(f"Total records fetched: {len(combined)} across {len(all_dfs)} symbols")
        return combined

    def save_to_delta(self, df: pd.DataFrame, table_name: str | None = None) -> None:
        """Save the OHLCV DataFrame to a Delta table.

        :param df: DataFrame with OHLCV data
        :param table_name: Full table name (catalog.schema.table). If None, saves to path.
        """
        if df.empty:
            logger.warning("No data to save")
            return

        if self.spark is not None:
            spark_df = self.spark.createDataFrame(df)
            if table_name:
                spark_df.write.format("delta").mode("append").saveAsTable(table_name)
                logger.info(f"Saved {len(df)} records to table {table_name}")
            else:
                spark_df.write.format("delta").mode("append").save(self.output_path)
                logger.info(f"Saved {len(df)} records to {self.output_path}")
        else:
            # Local mode: save as parquet
            timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
            local_path = f"{self.output_path}/historical_{timestamp}.parquet"
            df.to_parquet(local_path, index=False)
            logger.info(f"Saved {len(df)} records to {local_path}")

    def save_to_csv(self, df: pd.DataFrame, path: str) -> None:
        """Save the OHLCV DataFrame to CSV for local testing.

        :param df: DataFrame with OHLCV data
        :param path: File path for the CSV output
        """
        if df.empty:
            logger.warning("No data to save")
            return

        df.to_csv(path, index=False)
        logger.info(f"Saved {len(df)} records to {path}")

    def get_call_count(self) -> int:
        """Return the number of API calls made in this session."""
        return self._call_count
