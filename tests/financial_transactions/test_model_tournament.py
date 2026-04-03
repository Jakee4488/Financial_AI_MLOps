"""Tests for the 4-model tournament."""

from unittest.mock import patch, MagicMock

from financial_transactions.config import ProjectConfig, Tags
from financial_transactions.models.base_model import ModelResult
from financial_transactions.models.model_tournament import ModelTournament


def test_build_comparison_table(mock_config_path: str) -> None:
    """Test building the metrics comparison table from tournament results."""
    config = ProjectConfig.from_yaml(mock_config_path, env="dev")
    tags = Tags(git_sha="123", branch="main")
    
    tournament = ModelTournament(config, tags, spark=MagicMock())
    
    results = [
        ModelResult(model_name="m1", model_type="lgbm", metrics={"pr_auc": 0.8}, training_time_seconds=10.0),
        ModelResult(model_name="m2", model_type="xgb", metrics={"pr_auc": 0.9}, training_time_seconds=12.0),
        ModelResult(model_name="m3", model_type="rf", metrics={"pr_auc": 0.85}, training_time_seconds=8.0),
    ]
    
    df = tournament._build_comparison_table(results)
    
    assert len(df) == 3
    assert "model_type" in df.columns
    assert "pr_auc" in df.columns
    assert "training_time_s" in df.columns
    
    # Should be sorted descending by pr_auc
    assert df.iloc[0]["model_type"] == "xgb"
    assert df.iloc[1]["model_type"] == "rf"
    assert df.iloc[2]["model_type"] == "lgbm"


@patch("financial_transactions.models.model_tournament.IsolationForestModel")
@patch("financial_transactions.models.model_tournament.RandomForestModel")
@patch("financial_transactions.models.model_tournament.XGBoostModel")
@patch("financial_transactions.models.model_tournament.LightGBMModel")
def test_run_tournament(mock_lgbm, mock_xgb, mock_rf, mock_iso, mock_config_path: str) -> None:
    """Test running the tournament and selecting the winner."""
    # Set up mocks to return specific metrics
    lgbm_inst = mock_lgbm.return_value
    lgbm_inst.evaluate.return_value = {"pr_auc": 0.80}
    lgbm_inst.to_result.return_value = ModelResult(model_name="", model_type="lightgbm", metrics={"pr_auc": 0.80})
    
    xgb_inst = mock_xgb.return_value
    xgb_inst.evaluate.return_value = {"pr_auc": 0.90}
    xgb_inst.to_result.return_value = ModelResult(model_name="", model_type="xgboost", metrics={"pr_auc": 0.90})
    
    rf_inst = mock_rf.return_value
    rf_inst.evaluate.return_value = {"pr_auc": 0.85}
    rf_inst.to_result.return_value = ModelResult(model_name="", model_type="random_forest", metrics={"pr_auc": 0.85})
    
    iso_inst = mock_iso.return_value
    iso_inst.evaluate.return_value = {"pr_auc": 0.70}
    iso_inst.to_result.return_value = ModelResult(model_name="", model_type="isolation_forest", metrics={"pr_auc": 0.70})
    
    config = ProjectConfig.from_yaml(mock_config_path, env="dev")
    tags = Tags(git_sha="123", branch="main")
    
    tournament = ModelTournament(config, tags, spark=MagicMock())
    result = tournament.run_tournament()
    
    assert len(result.all_results) == 4
    # XGBoost had highest PR-AUC, so it should be challenger
    assert result.challenger.model_type == "xgboost"
    assert result.challenger.metrics["pr_auc"] == 0.90
