"""Finnhub WebSocket collector for real-time trade data.

Connects to Finnhub's WebSocket API, subscribes to configured stock symbols,
and writes micro-batches of trade data to a Delta landing zone for downstream
Structured Streaming consumption.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import websocket
from loguru import logger

from financial_transactions.config import StreamingConfig


class FinnhubCollector:
    """Collect real-time trade data from Finnhub WebSocket.

    Connects to the Finnhub WebSocket API, buffers trade ticks in memory,
    and periodically flushes micro-batches to a Delta landing zone.

    Usage:
        collector = FinnhubCollector(config, spark)
        collector.start()  # Blocking; runs until stopped
    """

    def __init__(
        self,
        config: StreamingConfig,
        spark: Any | None = None,
        output_path: str | None = None,
    ) -> None:
        """Initialize the Finnhub collector.

        :param config: Streaming configuration with API key and symbols
        :param spark: SparkSession for Delta writes (None for local file mode)
        :param output_path: Override output path for the landing zone
        """
        self.config = config
        self.spark = spark
        self.output_path = output_path or config.landing_zone_path
        self.api_key = config.finnhub_api_key
        self.ws_url = f"{config.finnhub_ws_url}?token={self.api_key}"
        self.symbols = config.finnhub_symbols
        self.batch_interval = config.batch_interval_seconds
        self.max_records = config.max_records_per_batch

        self._buffer: list[dict[str, Any]] = []
        self._buffer_lock = threading.Lock()
        self._running = False
        self._ws: websocket.WebSocketApp | None = None
        self._flush_thread: threading.Thread | None = None

    def _on_message(self, ws: websocket.WebSocketApp, message: str) -> None:
        """Handle incoming WebSocket messages.

        Finnhub sends: {"type":"trade","data":[{"s":"AAPL","p":150.5,"v":100,"t":1234567890000}]}
        """
        try:
            msg = json.loads(message)
            if msg.get("type") != "trade":
                return

            trades = msg.get("data", [])
            records = []
            for trade in trades:
                record = {
                    "trade_id": str(uuid.uuid4()),
                    "symbol": trade.get("s", ""),
                    "price": float(trade.get("p", 0.0)),
                    "volume": float(trade.get("v", 0.0)),
                    "timestamp": datetime.fromtimestamp(trade.get("t", 0) / 1000, tz=UTC).isoformat(),
                    "exchange": self._parse_exchange(trade.get("s", "")),
                    "ingestion_timestamp": datetime.now(tz=UTC).isoformat(),
                }
                records.append(record)

            with self._buffer_lock:
                self._buffer.extend(records)

            if len(self._buffer) >= self.max_records:
                self._flush_buffer()

        except (json.JSONDecodeError, KeyError, TypeError):
            logger.warning(f"Failed to parse message: {message[:200]}")

    def _on_error(self, ws: websocket.WebSocketApp, error: Exception) -> None:
        """Handle WebSocket errors."""
        logger.error(f"WebSocket error: {error}")

    def _on_close(
        self,
        ws: websocket.WebSocketApp,
        close_status_code: int | None,
        close_msg: str | None,
    ) -> None:
        """Handle WebSocket close — attempt reconnection."""
        logger.warning(f"WebSocket closed: {close_status_code} - {close_msg}")
        if self._running:
            logger.info("Attempting reconnection in 5 seconds...")
            time.sleep(5)
            self._connect()

    def _on_open(self, ws: websocket.WebSocketApp) -> None:
        """Subscribe to configured symbols on connection open."""
        logger.info(f"WebSocket connected. Subscribing to {len(self.symbols)} symbols...")
        for symbol in self.symbols:
            ws.send(json.dumps({"type": "subscribe", "symbol": symbol}))
            logger.info(f"  Subscribed to {symbol}")

    @staticmethod
    def _parse_exchange(symbol: str) -> str:
        """Parse exchange from symbol string (e.g., 'BINANCE:BTCUSDT' -> 'BINANCE')."""
        if ":" in symbol:
            return symbol.split(":")[0]
        return "US"

    def _flush_buffer(self) -> None:
        """Flush the in-memory buffer to the Delta landing zone."""
        with self._buffer_lock:
            if not self._buffer:
                return
            records = self._buffer.copy()
            self._buffer.clear()

        logger.info(f"Flushing {len(records)} trade records to {self.output_path}")

        try:
            df = pd.DataFrame(records)

            if self.spark is not None:
                # Write to Delta table on Databricks
                spark_df = self.spark.createDataFrame(df)
                spark_df.write.format("delta").mode("append").save(self.output_path)
            else:
                # Write to local parquet for testing
                timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
                local_path = f"{self.output_path}/batch_{timestamp}.parquet"
                df.to_parquet(local_path, index=False)

            logger.info(f"Successfully wrote {len(records)} records")

        except Exception:
            logger.exception("Failed to flush buffer")
            # Put records back in buffer on failure
            with self._buffer_lock:
                self._buffer = records + self._buffer

    def _periodic_flush(self) -> None:
        """Background thread that flushes the buffer at regular intervals."""
        while self._running:
            time.sleep(self.batch_interval)
            self._flush_buffer()

    def _connect(self) -> None:
        """Create and run the WebSocket connection."""
        self._ws = websocket.WebSocketApp(
            self.ws_url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open,
        )
        self._ws.run_forever()

    def start(self, duration: int | None = None) -> None:
        """Start the collector.

        :param duration: Run for N seconds then stop. None = run forever.
        """
        logger.info("Starting Finnhub collector...")
        self._running = True

        # Start periodic flush thread
        self._flush_thread = threading.Thread(target=self._periodic_flush, daemon=True)
        self._flush_thread.start()

        if duration:
            # Run for specified duration
            ws_thread = threading.Thread(target=self._connect, daemon=True)
            ws_thread.start()
            time.sleep(duration)
            self.stop()
        else:
            # Run forever (blocking)
            self._connect()

    def stop(self) -> None:
        """Stop the collector and flush remaining records."""
        logger.info("Stopping Finnhub collector...")
        self._running = False
        if self._ws:
            self._ws.close()
        self._flush_buffer()  # Final flush
        logger.info("Finnhub collector stopped.")

    def get_buffer_size(self) -> int:
        """Return the current number of buffered records."""
        with self._buffer_lock:
            return len(self._buffer)
