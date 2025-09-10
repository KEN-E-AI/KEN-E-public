"""Direct test of holiday sync functionality to debug deletion issues."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date
from src.kene_api.database import Neo4jService
from src.kene_api.bigquery import BigQueryService
from src.kene_api.routers.accounts import _sync_holiday_activity_logs_for_account


@pytest.fixture
def mock_neo4j_service():
    """Create a mock Neo4j service."""
    mock = AsyncMock(spec=Neo4jService)
    mock.health_check = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_bigquery_service():
    """Create a mock BigQuery service."""
    mock = MagicMock(spec=BigQueryService)
    mock.health_check = MagicMock(return_value=True)
    return mock


@pytest.mark.asyncio
async def test_sync_removes_us_holidays_when_changing_to_au(
    mock_neo4j_service, mock_bigquery_service
):
    """Test that US holidays are removed when region changes to AU."""
    account_id = "acc_af08bd32c4f540da96f1c7d9642f8009"

    # Mock existing US holiday logs
    mock_neo4j_service.execute_query.side_effect = [
        # First call: get existing logs
        [
            {
                "log_id": "log_us_presidents_day",
                "description": "US_PresidentDay",
                "start_date": "2024-02-19",
                "end_date": "2024-02-19",
                "has_metric_relationship": False,
            },
            {
                "log_id": "log_us_memorial_day",
                "description": "US_MemorialDay",
                "start_date": "2024-05-27",
                "end_date": "2024-05-27",
                "has_metric_relationship": False,
            },
        ],
        # Second call: check act_00 exists
        [{"count": 1}],
        # Third call: count deletable logs
        [{"to_delete_count": 2}],
    ]

    # Mock BigQuery returns AU holidays only
    mock_bigquery_service.query_holiday_activities.return_value = [
        {
            "description": "AU_AustraliaDay",
            "start_date": "2024-01-26",
            "end_date": "2024-01-26",
        },
        {
            "description": "AU_AnzacDay",
            "start_date": "2024-04-25",
            "end_date": "2024-04-25",
        },
    ]

    # Mock write operations
    mock_neo4j_service.execute_write_query.side_effect = [
        # First: create new AU logs
        {"nodes_created": 2},
        # Second: delete US logs
        {"nodes_deleted": 2},
    ]

    # Execute sync
    with patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
        result = await _sync_holiday_activity_logs_for_account(
            mock_neo4j_service, mock_bigquery_service, account_id, "org_123", ["AU"]
        )

    # Verify results
    assert result["created"] == 2
    assert result["deleted"] == 2
    assert len(result["operations"]["to_delete"]) == 2
    assert "log_us_presidents_day" in result["operations"]["to_delete"]
    assert "log_us_memorial_day" in result["operations"]["to_delete"]

    # Verify BigQuery was called with AU region
    mock_bigquery_service.query_holiday_activities.assert_called_once_with(
        "test-project", ["AU"]
    )

    # Verify deletion was called with US log IDs
    delete_calls = [
        call
        for call in mock_neo4j_service.execute_write_query.call_args_list
        if "log_ids" in call[0][1]
    ]
    assert len(delete_calls) == 1
    delete_params = delete_calls[0][0][1]
    assert set(delete_params["log_ids"]) == {
        "log_us_presidents_day",
        "log_us_memorial_day",
    }


@pytest.mark.asyncio
async def test_sync_protected_logs_not_deleted(
    mock_neo4j_service, mock_bigquery_service
):
    """Test that logs with metric relationships are not deleted."""
    account_id = "acc_af08bd32c4f540da96f1c7d9642f8009"

    # Mock existing logs with one protected
    mock_neo4j_service.execute_query.side_effect = [
        # First call: get existing logs
        [
            {
                "log_id": "log_us_presidents_day",
                "description": "US_PresidentDay",
                "start_date": "2024-02-19",
                "end_date": "2024-02-19",
                "has_metric_relationship": True,  # Protected
            },
            {
                "log_id": "log_us_memorial_day",
                "description": "US_MemorialDay",
                "start_date": "2024-05-27",
                "end_date": "2024-05-27",
                "has_metric_relationship": False,
            },
        ],
        # Second call: check act_00 exists
        [{"count": 1}],
        # Third call: count deletable logs (only unprotected)
        [{"to_delete_count": 1}],
    ]

    # Mock BigQuery returns empty (switching to region with no holidays)
    mock_bigquery_service.query_holiday_activities.return_value = []

    # Mock write operation - only deletes unprotected log
    mock_neo4j_service.execute_write_query.return_value = {"nodes_deleted": 1}

    # Execute sync
    with patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
        result = await _sync_holiday_activity_logs_for_account(
            mock_neo4j_service,
            mock_bigquery_service,
            account_id,
            "org_123",
            ["XX"],  # Fictional region with no holidays
        )

    # Verify results
    assert result["deleted"] == 1
    assert len(result["operations"]["to_delete"]) == 1
    assert "log_us_memorial_day" in result["operations"]["to_delete"]
    assert "log_us_presidents_day" not in result["operations"]["to_delete"]
    assert len(result["operations"]["protected"]) == 1
    assert "log_us_presidents_day" in result["operations"]["protected"]


@pytest.mark.asyncio
async def test_sync_adds_missing_holidays(mock_neo4j_service, mock_bigquery_service):
    """Test that missing holidays are added when region changes."""
    account_id = "acc_af08bd32c4f540da96f1c7d9642f8009"

    # Mock no existing logs
    mock_neo4j_service.execute_query.side_effect = [
        # First call: get existing logs (empty)
        [],
        # Second call: check act_00 exists
        [{"count": 1}],
    ]

    # Mock BigQuery returns US holidays
    mock_bigquery_service.query_holiday_activities.return_value = [
        {
            "description": "US_PresidentDay",
            "start_date": "2024-02-19",
            "end_date": "2024-02-19",
        },
        {
            "description": "US_MemorialDay",
            "start_date": "2024-05-27",
            "end_date": "2024-05-27",
        },
    ]

    # Mock write operation - creates new logs
    mock_neo4j_service.execute_write_query.return_value = {"nodes_created": 2}

    # Execute sync
    with patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
        result = await _sync_holiday_activity_logs_for_account(
            mock_neo4j_service, mock_bigquery_service, account_id, "org_123", ["US"]
        )

    # Verify results
    assert result["created"] == 2
    assert result["deleted"] == 0
    assert len(result["operations"]["to_create"]) == 2

    # Verify the created logs have correct descriptions
    created_descriptions = [
        log["description"] for log in result["operations"]["to_create"]
    ]
    assert "US_PresidentDay" in created_descriptions
    assert "US_MemorialDay" in created_descriptions
