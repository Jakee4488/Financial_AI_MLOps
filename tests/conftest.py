"""Pytest configuration and shared fixtures for financial transaction tests."""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
import pytest
from pyspark.sql import SparkSession


@pytest.fixture(scope="session")
def spark() -> SparkSession:
    """Provide a SparkSession for testing."""
    os.environ["SPARK_LOCAL_IP"] = "127.0.0.1"
    
    spark = (
        SparkSession.builder.master("local[2]")
        .appName("FinancialTransactionsTesting")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    
    yield spark
    spark.stop()


@pytest.fixture
def mock_config_path(tmp_path: Any) -> str:
    """Create a mock YAML config file for testing."""
    import yaml

    config_data = {
        "prd": {"catalog_name": "mlops_prd", "schema_name": "financial"},
        "acc": {"catalog_name": "mlops_acc", "schema_name": "financial"},
        "dev": {"catalog_name": "mlops_dev", "schema_name": "financial"},
        "experiment_name_basic": "/Shared/financial-basic",
        "parameters": {"learning_rate": 0.01},
        "num_features": ["price", "volume"],
        "cat_features": ["symbol", "session_type"],
        "target": "is_anomaly",
        "streaming": {
            "finnhub_symbols": ["AAPL", "MSFT"]
        },
        "drift": {
            "psi_threshold": 0.15
        }
    }
    
    config_path = tmp_path / "mock_config.yml"
    with open(config_path, "w") as f:
        yaml.dump(config_data, f)
        
    return str(config_path)


@pytest.fixture
def sample_trade_data() -> pd.DataFrame:
    """Provide sample trade data for feature engineering tests."""
    data = {
        "trade_id": ["t1", "t2", "t3", "t4", "t5"],
        "symbol": ["AAPL", "AAPL", "AAPL", "MSFT", "MSFT"],
        "price": [150.0, 151.0, 149.0, 300.0, 305.0],
        "volume": [100, 200, 150, 50, 60],
        "timestamp": pd.date_range(start="2026-04-01 10:00:00", periods=5, freq="5min", tz="UTC"),
        "exchange": ["US", "US", "US", "US", "US"],
        "session_type": ["regular", "regular", "regular", "regular", "regular"]
    }
    return pd.DataFrame(data)
