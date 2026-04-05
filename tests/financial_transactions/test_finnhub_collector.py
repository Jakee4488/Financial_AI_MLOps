"""Tests for Finnhub WebSocket collector."""

import json
from datetime import UTC, datetime
from typing import Any

from financial_transactions.config import StreamingConfig
from financial_transactions.streaming.finnhub_collector import FinnhubCollector


def test_parse_exchange() -> None:
    """Test parsing exchange from Finnhub symbols."""
    assert FinnhubCollector._parse_exchange("BINANCE:BTCUSDT") == "BINANCE"
    assert FinnhubCollector._parse_exchange("AAPL") == "US"


def test_on_message() -> None:
    """Test buffering of trade messages."""
    config = StreamingConfig(finnhub_symbols=["AAPL"])
    collector = FinnhubCollector(config)

    # Valid trade message
    msg = {"type": "trade", "data": [{"s": "AAPL", "p": 150.5, "v": 100, "t": 1640995200000}]}
    collector._on_message(None, json.dumps(msg))  # type: ignore

    assert collector.get_buffer_size() == 1

    with collector._buffer_lock:
        stored = collector._buffer[0]
        assert stored["symbol"] == "AAPL"
        assert stored["price"] == 150.5
        assert stored["volume"] == 100.0
        assert stored["exchange"] == "US"
        assert "trade_id" in stored
        assert "timestamp" in stored
        assert "ingestion_timestamp" in stored


def test_on_message_invalid_type() -> None:
    """Test ignoring non-trade messages."""
    config = StreamingConfig()
    collector = FinnhubCollector(config)

    msg = {"type": "ping"}
    collector._on_message(None, json.dumps(msg))  # type: ignore

    assert collector.get_buffer_size() == 0


def test_flush_buffer_local(tmp_path: Any) -> None:
    """Test flushing buffered trades to local parquet."""
    config = StreamingConfig()
    out_dir = tmp_path / "landing"
    out_dir.mkdir()

    collector = FinnhubCollector(config, output_path=str(out_dir))

    # Manually populate buffer
    with collector._buffer_lock:
        collector._buffer.extend(
            [
                {
                    "trade_id": "1",
                    "symbol": "AAPL",
                    "price": 100.0,
                    "volume": 10.0,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "exchange": "US",
                },
            ]
        )

    assert collector.get_buffer_size() == 1

    collector._flush_buffer()

    assert collector.get_buffer_size() == 0

    # Verify parquet file creation
    files = list(out_dir.glob("*.parquet"))
    assert len(files) == 1

    import pandas as pd

    df = pd.read_parquet(files[0])
    assert len(df) == 1
    assert df.iloc[0]["symbol"] == "AAPL"
