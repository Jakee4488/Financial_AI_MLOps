"""Tests for Champion/Challenger deployment gate."""

import pytest
from unittest.mock import patch, MagicMock

from financial_transactions.config import ProjectConfig
from financial_transactions.models.base_model import ModelResult
from financial_transactions.models.champion_challenger import ChampionChallenger


@patch("financial_transactions.models.champion_challenger.ChampionChallenger._get_champion_metrics")
def test_compare_no_champion(mock_get_metrics, mock_config_path: str) -> None:
    """Test logic when no production champion exists (auto-promote)."""
    mock_get_metrics.return_value = None  # No existing champion
    
    config = ProjectConfig.from_yaml(mock_config_path, env="dev")
    gate = ChampionChallenger(config, spark=MagicMock())
    
    challenger = ModelResult(model_name="test", model_type="xgb", metrics={"pr_auc": 0.8})
    result = gate.compare(challenger)
    
    assert result.decision == "PROMOTE"
    assert "No existing champion" in result.reason


@patch("financial_transactions.models.champion_challenger.ChampionChallenger._get_champion_metrics")
def test_compare_promote(mock_get_metrics, mock_config_path: str) -> None:
    """Test logic when challenger beats champion by threshold."""
    mock_get_metrics.return_value = {"pr_auc": 0.80}  # Champion metrics
    
    config = ProjectConfig.from_yaml(mock_config_path, env="dev")
    config.champion_challenger.primary_metric = "pr_auc"
    config.champion_challenger.min_improvement_threshold = 0.01
    
    gate = ChampionChallenger(config, spark=MagicMock())
    
    # 0.82 >= 0.80 + 0.01
    challenger = ModelResult(model_name="test", model_type="xgb", metrics={"pr_auc": 0.82})
    result = gate.compare(challenger)
    
    assert result.decision == "PROMOTE"
    assert result.improvement["pr_auc"] == pytest.approx(0.02)


@patch("financial_transactions.models.champion_challenger.ChampionChallenger._get_champion_metrics")
def test_compare_reject(mock_get_metrics, mock_config_path: str) -> None:
    """Test logic when challenger does not beat threshold."""
    mock_get_metrics.return_value = {"pr_auc": 0.80}  # Champion metrics
    
    config = ProjectConfig.from_yaml(mock_config_path, env="dev")
    config.champion_challenger.primary_metric = "pr_auc"
    config.champion_challenger.min_improvement_threshold = 0.01
    
    gate = ChampionChallenger(config, spark=MagicMock())
    
    # 0.805 < 0.80 + 0.01 (fails threshold)
    challenger = ModelResult(model_name="test", model_type="xgb", metrics={"pr_auc": 0.805})
    result = gate.compare(challenger)
    
    assert result.decision == "REJECT"
    assert "Insufficient improvement" in result.reason
