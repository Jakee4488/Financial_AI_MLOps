"""Tests for Alpha Vantage historical collector."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from financial_transactions.config import HistoricalConfig
from financial_transactions.streaming.alphavantage_collector import AlphaVantageCollector


@pytest.fixture
def mock_av_response():
    """Mock API response."""
    return {
        "Meta Data": {},
        "Time Series (5min)": {
            "2026-04-01 10:00:00": {
                "1. open": "150.0",
                "2. high": "151.0",
                "3. low": "149.0",
                "4. close": "150.5",
                "5. volume": "100",
            }
        },
    }


@patch("financial_transactions.streaming.alphavantage_collector.requests.get")
def test_fetch_symbol_success(mock_get, mock_av_response) -> None:
    """Test successfully fetching and parsing data for a symbol."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = mock_av_response
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    config = HistoricalConfig(alphavantage_api_key="test", symbols=["AAPL"])
    collector = AlphaVantageCollector(config)

    df = collector.fetch_symbol("AAPL")

    assert not df.empty
    assert len(df) == 1
    assert df.iloc[0]["symbol"] == "AAPL"
    assert df.iloc[0]["open"] == 150.0
    assert df.iloc[0]["volume"] == 100


@patch("financial_transactions.streaming.alphavantage_collector.requests.get")
def test_fetch_symbol_api_error(mock_get) -> None:
    """Test handling of API error responses."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"Error Message": "Invalid API call"}
    mock_get.return_value = mock_resp

    config = HistoricalConfig(alphavantage_api_key="test", symbols=["AAPL"])
    collector = AlphaVantageCollector(config)

    df = collector.fetch_symbol("AAPL")
    assert df.empty


@patch("financial_transactions.streaming.alphavantage_collector.time.sleep")
@patch.object(AlphaVantageCollector, "fetch_symbol")
def test_fetch_all_symbols_rate_limiting(mock_fetch, mock_sleep) -> None:
    """Test rate limiting sleep is called between symbols."""
    mock_fetch.return_value = pd.DataFrame([{"symbol": "TEST"}])

    config = HistoricalConfig(symbols=["AAPL", "MSFT", "GOOGL"], rate_limit_sleep=5)
    collector = AlphaVantageCollector(config)

    collector.fetch_all_symbols()

    assert mock_fetch.call_count == 3
    assert mock_sleep.call_count == 2  # Sleep between the 3 calls, not after last
    mock_sleep.assert_called_with(5)
