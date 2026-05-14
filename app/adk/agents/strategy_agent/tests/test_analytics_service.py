"""Unit tests for Analytics Service."""

from unittest.mock import MagicMock, patch

import pytest

from ..analytics_service import AnalyticsService


@pytest.fixture
def mock_firestore_client():
    """Create mock Firestore clients."""
    with patch("google.cloud.firestore.Client") as mock_client:
        mock_analytics_db = MagicMock()
        mock_default_db = MagicMock()

        def client_side_effect(project=None, database=None):
            if database == "analytics":
                return mock_analytics_db
            return mock_default_db

        mock_client.side_effect = client_side_effect
        yield mock_analytics_db, mock_default_db


@pytest.fixture
def analytics_service(mock_firestore_client):
    """Create Analytics Service instance with mocked Firestore."""
    mock_analytics_db, _ = mock_firestore_client
    service = AnalyticsService(account_id="test_account", project_id="test_project")
    # Inject mock analytics_db directly so the test stays hermetic (no live Firestore in CI)
    service.analytics_db = mock_analytics_db
    return service


def test_analytics_service_initialization(mock_firestore_client):
    """Test Analytics Service initialization."""
    service = AnalyticsService(account_id="test_account", project_id="test_project")

    assert service.account_id == "test_account"
    assert service.project_id == "test_project"
    assert service.execution_id is not None
    assert service.execution_metrics["total_tokens"] == 0
    assert service.execution_metrics["total_cost"] == 0.0


def test_track_agent_execution(analytics_service, mock_firestore_client):
    """Test tracking agent execution metrics."""
    mock_analytics_db, _ = mock_firestore_client
    mock_collection = MagicMock()
    mock_analytics_db.collection.return_value = mock_collection

    metrics = analytics_service.track_agent_execution(
        agent_name="test_agent",
        prompt_tokens=1000,
        response_tokens=500,
        model="gemini-2.5-flash",
        execution_time=2.5,
        success=True,
    )

    assert metrics["agent_name"] == "test_agent"
    assert metrics["total_tokens"] == 1500
    assert metrics["execution_time_seconds"] == 2.5
    assert metrics["success"] is True

    # Verify Shape B path used for write
    mock_analytics_db.collection.assert_called_with(
        "accounts/test_account/agent_analytics"
    )

    # Check cost calculation (Flash model pricing)
    expected_prompt_cost = (1000 / 1_000_000) * 0.075
    expected_response_cost = (500 / 1_000_000) * 0.30
    assert metrics["prompt_cost"] == pytest.approx(expected_prompt_cost)
    assert metrics["response_cost"] == pytest.approx(expected_response_cost)
    assert metrics["total_cost"] == pytest.approx(
        expected_prompt_cost + expected_response_cost
    )


def test_track_agent_execution_pro_model(analytics_service):
    """Test tracking with Pro model (higher costs)."""
    metrics = analytics_service.track_agent_execution(
        agent_name="strategist",
        prompt_tokens=10000,
        response_tokens=5000,
        model="gemini-2.5-pro",
        execution_time=10.0,
        success=True,
    )

    # Check Pro model pricing
    expected_prompt_cost = (10000 / 1_000_000) * 3.50
    expected_response_cost = (5000 / 1_000_000) * 10.50
    assert metrics["total_cost"] == pytest.approx(
        expected_prompt_cost + expected_response_cost
    )


def test_cumulative_metrics_update(analytics_service):
    """Test cumulative metrics tracking across multiple executions."""
    # Track first execution
    analytics_service.track_agent_execution(
        agent_name="agent1",
        prompt_tokens=1000,
        response_tokens=500,
        model="gemini-2.5-flash",
        execution_time=2.0,
        success=True,
    )

    # Track second execution
    analytics_service.track_agent_execution(
        agent_name="agent2",
        prompt_tokens=2000,
        response_tokens=1000,
        model="gemini-2.5-flash",
        execution_time=3.0,
        success=True,
    )

    # Check cumulative metrics
    assert analytics_service.execution_metrics["total_tokens"] == 4500
    assert (
        analytics_service.execution_metrics["agent_metrics"]["agent1"]["executions"]
        == 1
    )
    assert (
        analytics_service.execution_metrics["agent_metrics"]["agent2"]["executions"]
        == 1
    )


def test_track_token_estimation(analytics_service, mock_firestore_client):
    """Test token estimation tracking."""
    mock_analytics_db, _ = mock_firestore_client
    mock_collection = MagicMock()
    mock_analytics_db.collection.return_value = mock_collection

    analytics_service.track_token_estimation(
        agent_name="test_agent",
        estimated_tokens=1000,
        actual_tokens=950,
        context="input",
    )

    # Verify Shape B path used for write
    mock_analytics_db.collection.assert_called_with(
        "accounts/test_account/agent_analytics"
    )

    # Verify that the estimation was tracked
    mock_collection.add.assert_called_once()
    call_args = mock_collection.add.call_args[0][0]
    assert call_args["estimated_tokens"] == 1000
    assert call_args["actual_tokens"] == 950
    assert call_args["accuracy_error"] == pytest.approx(0.05263, rel=1e-3)


def test_get_execution_summary(analytics_service):
    """Test getting execution summary."""
    # Add some executions
    analytics_service.track_agent_execution(
        agent_name="agent1",
        prompt_tokens=1000,
        response_tokens=500,
        model="gemini-2.5-flash",
        execution_time=2.0,
        success=True,
    )

    summary = analytics_service.get_execution_summary()

    assert summary["execution_id"] == analytics_service.execution_id
    assert summary["account_id"] == "test_account"
    assert summary["total_tokens"] == 1500
    assert summary["total_cost"] > 0
    assert "agent1" in summary["agent_metrics"]


def test_aggregate_daily_costs(analytics_service, mock_firestore_client):
    """Test daily cost aggregation."""
    mock_analytics_db, _ = mock_firestore_client

    # Inject mock analytics_db directly so the test stays hermetic (no live Firestore in CI)
    analytics_service.analytics_db = mock_analytics_db

    # Source collection mock (Shape A agent_analytics_ read path)
    mock_source_collection = MagicMock()
    mock_doc1 = MagicMock()
    mock_doc1.to_dict.return_value = {
        "total_cost": 0.5,
        "total_tokens": 1000,
        "agent_name": "agent1",
        "model": "gemini-2.5-flash",
    }
    mock_doc2 = MagicMock()
    mock_doc2.to_dict.return_value = {
        "total_cost": 0.3,
        "total_tokens": 800,
        "agent_name": "agent2",
        "model": "gemini-2.5-flash",
    }
    mock_query = MagicMock()
    mock_query.where.return_value = mock_query
    mock_query.stream.return_value = [mock_doc1, mock_doc2]
    mock_source_collection.where.return_value = mock_query

    # Destination collection mock (Shape B accounts/ write path) — isolated from source
    mock_accounts_collection = MagicMock()
    agg_doc_mock = mock_accounts_collection.document.return_value.collection.return_value.document.return_value

    def collection_side_effect(name: str) -> MagicMock:
        return (
            mock_accounts_collection if name == "accounts" else mock_source_collection
        )

    mock_analytics_db.collection.side_effect = collection_side_effect

    aggregation = analytics_service.aggregate_daily_costs()

    assert aggregation["total_cost"] == 0.8
    assert aggregation["total_tokens"] == 1800
    assert aggregation["total_executions"] == 2

    # Verify Shape B path: accounts/{account_id}/cost_aggregations
    mock_analytics_db.collection.assert_any_call("accounts")
    mock_accounts_collection.document.assert_called_once_with("test_account")
    mock_accounts_collection.document.return_value.collection.assert_called_once_with(
        "cost_aggregations"
    )
    agg_doc_mock.set.assert_called_once()


def test_cleanup_old_metrics(analytics_service, mock_firestore_client):
    """Test cleanup of old metrics."""
    mock_analytics_db, _ = mock_firestore_client

    # Mock the collection and query
    mock_collection = MagicMock()
    mock_analytics_db.collection.return_value = mock_collection

    # Mock old documents
    mock_doc1 = MagicMock()
    mock_doc2 = MagicMock()
    mock_doc3 = MagicMock()

    mock_query = MagicMock()
    mock_query.stream.return_value = [mock_doc1, mock_doc2, mock_doc3]
    mock_collection.where.return_value = mock_query

    # Mock batch operations
    mock_batch = MagicMock()
    mock_analytics_db.batch.return_value = mock_batch

    analytics_service.cleanup_old_metrics(retention_days=90)

    # Verify batch delete was called
    assert mock_batch.delete.call_count == 3
    mock_batch.commit.assert_called()


def test_get_cost_trends(analytics_service, mock_firestore_client):
    """Test getting cost trends."""
    mock_analytics_db, _ = mock_firestore_client

    # Inject mock analytics_db directly so the test stays hermetic (no live Firestore in CI)
    analytics_service.analytics_db = mock_analytics_db

    # Mock the collection
    mock_collection = MagicMock()
    mock_analytics_db.collection.return_value = mock_collection

    # Mock document retrieval
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "date": "2024-01-01",
        "total_cost": 10.0,
        "total_tokens": 100000,
        "total_executions": 50,
    }
    # Shape B chained path: collection("accounts").document(id).collection("cost_aggregations").document(date).get()
    mock_collection.document.return_value.collection.return_value.document.return_value.get.return_value = mock_doc

    trends = analytics_service.get_cost_trends(days=7)

    # Should have data for requested days
    assert len(trends) == 7
    # Should be sorted by date
    assert all(
        trends[i]["date"] <= trends[i + 1]["date"] for i in range(len(trends) - 1)
    )

    # Verify Shape B path: accounts/{account_id}/cost_aggregations
    mock_analytics_db.collection.assert_called_once_with("accounts")
    mock_collection.document.assert_called_once_with("test_account")
    mock_collection.document.return_value.collection.assert_called_once_with(
        "cost_aggregations"
    )


def test_error_handling_no_firestore(mock_firestore_client):
    """Test Analytics Service handles Firestore connection errors gracefully."""
    with patch(
        "google.cloud.firestore.Client", side_effect=Exception("Connection error")
    ):
        service = AnalyticsService(account_id="test_account")

        # Should still initialize but without Firestore
        assert service.analytics_db is None
        assert service.default_db is None

        # Operations should handle missing Firestore gracefully
        metrics = service.track_agent_execution(
            agent_name="test",
            prompt_tokens=100,
            response_tokens=50,
            model="gemini-2.5-flash",
            execution_time=1.0,
        )

        # Should still return metrics even without storage
        assert metrics["total_tokens"] == 150
