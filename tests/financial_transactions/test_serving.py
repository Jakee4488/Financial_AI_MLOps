"""Tests for model serving edge endpoints."""

from unittest.mock import MagicMock, patch

from financial_transactions.serving.model_serving import AnomalyModelServing


@patch("financial_transactions.serving.model_serving.WorkspaceClient")
def test_deploy_or_update_create(mock_ws) -> None:
    """Test deploying a new endpoint."""
    mock_client = mock_ws.return_value
    mock_client.serving_endpoints.list.return_value = []
    
    serving = AnomalyModelServing("my_model", "my_endpoint")
    
    with patch.object(serving, "get_latest_model_version", return_value="5"):
        serving.deploy_or_update(version="latest")
        
    mock_client.serving_endpoints.create.assert_called_once()
    mock_client.serving_endpoints.update_config.assert_not_called()
    
    assert serving._production_version == "5"


@patch("financial_transactions.serving.model_serving.WorkspaceClient")
def test_deploy_or_update_existing(mock_ws) -> None:
    """Test updating an existing endpoint."""
    mock_client = mock_ws.return_value
    mock_endpoint = MagicMock()
    mock_endpoint.name = "my_endpoint"
    mock_client.serving_endpoints.list.return_value = [mock_endpoint]
    
    serving = AnomalyModelServing("my_model", "my_endpoint")
    
    serving.deploy_or_update(version="6")
        
    mock_client.serving_endpoints.create.assert_not_called()
    mock_client.serving_endpoints.update_config.assert_called_once()
    
    assert serving._production_version == "6"


@patch("financial_transactions.serving.model_serving.WorkspaceClient")
def test_deploy_canary(mock_ws) -> None:
    """Test deploying a canary version with split traffic."""
    mock_client = mock_ws.return_value
    
    serving = AnomalyModelServing("my_model", "my_endpoint")
    serving._production_version = "5"
    
    serving.deploy_canary(version="6", canary_pct=20)
    
    mock_client.serving_endpoints.update_config.assert_called_once()
    
    # Extract the traffic_config passed to update_config
    kwargs = mock_client.serving_endpoints.update_config.call_args[1]
    traffic_config = kwargs["traffic_config"]
    
    assert len(traffic_config["routes"]) == 2
    
    # Check canary route
    canary_route = next(r for r in traffic_config["routes"] if r["served_model_name"] == "my_model-6")
    assert canary_route["traffic_percentage"] == 20
    
    # Check production route
    prod_route = next(r for r in traffic_config["routes"] if r["served_model_name"] == "my_model-5")
    assert prod_route["traffic_percentage"] == 80
    
    assert serving._canary_version == "6"
