"""Tests for feature engineering logic."""

from typing import Any
import pandas as pd

from financial_transactions.config import ProjectConfig
from financial_transactions.features.feature_engineering import FeatureEngineer


def test_compute_trade_features(sample_trade_data: pd.DataFrame, mock_config_path: str) -> None:
    """Test pandas-based windowed feature computation."""
    config = ProjectConfig.from_yaml(mock_config_path, env="dev")
    fe = FeatureEngineer(config)
    
    # AAPL has 3 records, MSFT has 2
    res = fe.compute_trade_features_pandas(sample_trade_data)
    
    assert len(res) == 5
    assert "price_change_pct" in res.columns
    assert "rsi_14" in res.columns
    assert "bollinger_position" in res.columns
    assert "vwap_deviation" in res.columns
    
    # Check NaN filling
    assert res["price_change_pct"].isna().sum() == 0
    assert res["rsi_14"].isna().sum() == 0


def test_generate_anomaly_labels(sample_trade_data: pd.DataFrame, mock_config_path: str) -> None:
    """Test rule-based anomaly labeling."""
    config = ProjectConfig.from_yaml(mock_config_path, env="dev")
    fe = FeatureEngineer(config)
    
    # Manually compute features to set up specific anomaly scenarios
    features = fe.compute_trade_features_pandas(sample_trade_data)
    
    # Forcing anomalies for testing
    features.loc[0, "volume_zscore"] = 4.0  # High z-score
    features.loc[0, "price_change_pct"] = 3.0  # High price change -> Anomaly
    
    features.loc[1, "rsi_14"] = 90.0  # Extreme overbought -> Anomaly
    features.loc[2, "bollinger_position"] = 1.1  # Outside upper band -> Anomaly
    
    features.loc[3, "volume_zscore"] = 1.0  # Normal -> Not an anomaly
    features.loc[3, "price_change_pct"] = 1.0
    features.loc[3, "rsi_14"] = 50.0
    features.loc[3, "bollinger_position"] = 0.5
    
    labeled = fe.generate_anomaly_labels(features, volume_threshold=3.0, price_threshold=2.0)
    
    assert labeled.loc[0, "is_anomaly"] == 1
    assert labeled.loc[1, "is_anomaly"] == 1
    assert labeled.loc[2, "is_anomaly"] == 1
    assert labeled.loc[3, "is_anomaly"] == 0


def test_prepare_training_data(sample_trade_data: pd.DataFrame, mock_config_path: str) -> None:
    """Test train/test splitting functionality."""
    config = ProjectConfig.from_yaml(mock_config_path, env="dev")
    fe = FeatureEngineer(config)
    
    # Add dummy target column to raw data for test
    sample_trade_data["is_anomaly"] = [0, 1, 0, 1, 0]
    
    # 5 rows total, so doing a small split
    train, test = fe.prepare_training_data(sample_trade_data, test_size=0.4, random_state=42)
    
    assert len(train) == 3
    assert len(test) == 2
    assert "is_anomaly" in train.columns
    assert "price" in train.columns
    assert "volume" in train.columns
