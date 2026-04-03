"""Tests for model serving rollback functionality."""

import pytest
from unittest.mock import patch, MagicMock

from financial_transactions.config import ProjectConfig
from financial_transactions.serving.rollback_manager import RollbackManager


def test_capture_state(mock_config_path: str) -> None:
    """Test capturing the current deployment state."""
    config = ProjectConfig.from_yaml(mock_config_path, env="dev")
    rm = RollbackManager(config, spark=None)  # Spark is optional here
    
    snapshot = rm.capture_state(model_version="3", endpoint_name="test-endpoint")
    
    assert snapshot["model_version"] == "3"
    assert snapshot["endpoint_name"] == "test-endpoint"
    assert snapshot["catalog"] == "mlops_dev"
    assert "timestamp" in snapshot
    
    history = rm.get_rollback_history()
    assert len(history) == 1
    assert history[0] == snapshot


@patch("financial_transactions.serving.rollback_manager.AnomalyModelServing")
def test_rollback_model(mock_serving_cls, mock_config_path: str) -> None:
    """Test rolling back a model to a specific version."""
    mock_serving = mock_serving_cls.return_value
    
    config = ProjectConfig.from_yaml(mock_config_path, env="dev")
    rm = RollbackManager(config, spark=None)
    
    rm.rollback_model(version="2")
    
    # Verify AnomalyModelServing was called correctly
    mock_serving_cls.assert_called_once()
    mock_serving.rollback.assert_called_once_with(version="2")


@patch("financial_transactions.serving.rollback_manager.mlflow.MlflowClient")
def test_verify_rollback(mock_client_cls, mock_config_path: str) -> None:
    """Test verifying a model rollback via MLflow aliases."""
    mock_client = mock_client_cls.return_value
    mock_version = MagicMock()
    mock_version.version = "2"
    mock_client.get_model_version_by_alias.return_value = mock_version
    
    config = ProjectConfig.from_yaml(mock_config_path, env="dev")
    rm = RollbackManager(config, spark=None)
    
    assert rm.verify_rollback(expected_version="2") is True
    # Should fail if it's not the expected version
    assert rm.verify_rollback(expected_version="3") is False
