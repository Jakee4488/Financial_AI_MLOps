"""Tests for configuration loading."""

from financial_transactions.config import ProjectConfig


def test_config_loading_dev(mock_config_path: str) -> None:
    """Test loading configuration for the dev environment."""
    config = ProjectConfig.from_yaml(mock_config_path, env="dev")
    
    assert config.catalog_name == "mlops_dev"
    assert config.schema_name == "financial"
    assert "price" in config.num_features
    assert "symbol" in config.cat_features
    assert config.streaming.finnhub_symbols == ["AAPL", "MSFT"]
    assert config.drift.psi_threshold == 0.15


def test_config_loading_prd(mock_config_path: str) -> None:
    """Test loading configuration for the prd environment."""
    config = ProjectConfig.from_yaml(mock_config_path, env="prd")
    
    assert config.catalog_name == "mlops_prd"
    assert config.schema_name == "financial"


def test_invalid_environment(mock_config_path: str) -> None:
    """Test loading configuration with an invalid environment."""
    import pytest
    with pytest.raises(ValueError, match="Invalid environment"):
        ProjectConfig.from_yaml(mock_config_path, env="invalid")
