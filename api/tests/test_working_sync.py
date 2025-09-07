"""Working test of holiday sync with proper mocks."""

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
async def test_us_to_au_region_change_deletes_us_holidays(
    mock_neo4j_service, mock_bigquery_service
):
    """
    Test the specific scenario for account acc_af08bd32c4f540da96f1c7d9642f8009:
    - Currently has US holidays (including US_PresidentDay)
    - Changes region from US to AU
    - US holidays should be deleted
    - AU holidays should be added
    """
    account_id = "acc_af08bd32c4f540da96f1c7d9642f8009"

    # Track all calls for debugging
    query_calls = []
    write_calls = []

    async def mock_execute_query(query, params):
        call_info = {"query": query, "params": params}
        query_calls.append(call_info)

        # Determine response based on query content
        if 'MATCH (a:Activity {activity_id: "act_00"})' in query and "LOGGED" in query:
            # Fetching existing activity logs
            return [
                {
                    "log_id": "log_us_presidents_day_001",
                    "description": "US_PresidentDay",
                    "start_date": "2024-02-19",
                    "end_date": "2024-02-19",
                    "has_metric_relationship": False,
                },
                {
                    "log_id": "log_us_memorial_day_002",
                    "description": "US_MemorialDay",
                    "start_date": "2024-05-27",
                    "end_date": "2024-05-27",
                    "has_metric_relationship": False,
                },
            ]
        elif (
            'MATCH (a:Activity {activity_id: "act_00"})' in query
            and "count(a)" in query
        ):
            # Checking if act_00 exists
            return [{"count": 1}]
        elif (
            "UNWIND $log_ids AS log_id" in query
            and "count(al) as to_delete_count" in query
        ):
            # Counting deletable logs
            log_ids = params.get("log_ids", [])
            return [{"to_delete_count": len(log_ids)}]
        else:
            return []

    async def mock_execute_write_query(query, params):
        call_info = {"query": query, "params": params}
        write_calls.append(call_info)

        if "CREATE (al:ActivityLog" in query:
            # Creating new logs
            logs = params.get("logs", [])
            return {"nodes_created": len(logs)}
        elif "DETACH DELETE al" in query:
            # Deleting logs
            log_ids = params.get("log_ids", [])
            return {"nodes_deleted": len(log_ids)}
        else:
            return {}

    mock_neo4j_service.execute_query = mock_execute_query
    mock_neo4j_service.execute_write_query = mock_execute_write_query

    # Mock BigQuery returns AU holidays
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

    # Execute sync
    with patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
        result = await _sync_holiday_activity_logs_for_account(
            mock_neo4j_service,
            mock_bigquery_service,
            account_id,
            "org_123",
            ["AU"],  # Changed to AU
        )

    # Print debug info
    print("\nSync Results:")
    print(f"  Created: {result['created']}")
    print(f"  Deleted: {result['deleted']}")
    print(f"  Errors: {result.get('errors', [])}")

    print("\nOperations:")
    print(f"  To create: {len(result['operations']['to_create'])} logs")
    for log in result["operations"]["to_create"]:
        print(f"    - {log['description']}")

    print(f"  To delete: {len(result['operations']['to_delete'])} logs")
    for log_id in result["operations"]["to_delete"]:
        print(f"    - {log_id}")

    print("\nQuery calls made:")
    for i, call in enumerate(query_calls):
        print(
            f"  {i + 1}. {call['query'][:50]}... with params: {list(call['params'].keys())}"
        )

    print("\nWrite calls made:")
    for i, call in enumerate(write_calls):
        print(
            f"  {i + 1}. {call['query'][:50]}... with params: {list(call['params'].keys())}"
        )

    # Assertions
    assert result["created"] == 2, f"Expected 2 created, got {result['created']}"
    assert result["deleted"] == 2, f"Expected 2 deleted, got {result['deleted']}"

    # Verify US holidays were marked for deletion
    assert "log_us_presidents_day_001" in result["operations"]["to_delete"]
    assert "log_us_memorial_day_002" in result["operations"]["to_delete"]

    # Verify AU holidays were created
    created_descriptions = [
        log["description"] for log in result["operations"]["to_create"]
    ]
    assert "AU_AustraliaDay" in created_descriptions
    assert "AU_AnzacDay" in created_descriptions

    # Verify BigQuery was called with AU region
    mock_bigquery_service.query_holiday_activities.assert_called_once_with(
        "test-project", ["AU"]
    )

    print("\n✅ Test passed! US holidays were deleted and AU holidays were added.")


@pytest.mark.asyncio
async def test_au_to_us_region_change_adds_us_holidays(
    mock_neo4j_service, mock_bigquery_service
):
    """
    Test changing back from AU to US:
    - Currently has AU holidays
    - Changes region from AU to US
    - AU holidays should be deleted
    - US holidays (including US_PresidentDay) should be added
    """
    account_id = "acc_af08bd32c4f540da96f1c7d9642f8009"

    async def mock_execute_query(query, params):
        if 'MATCH (a:Activity {activity_id: "act_00"})' in query and "LOGGED" in query:
            # Currently has AU holidays
            return [
                {
                    "log_id": "log_au_australia_day_001",
                    "description": "AU_AustraliaDay",
                    "start_date": "2024-01-26",
                    "end_date": "2024-01-26",
                    "has_metric_relationship": False,
                },
                {
                    "log_id": "log_au_anzac_day_002",
                    "description": "AU_AnzacDay",
                    "start_date": "2024-04-25",
                    "end_date": "2024-04-25",
                    "has_metric_relationship": False,
                },
            ]
        elif (
            'MATCH (a:Activity {activity_id: "act_00"})' in query
            and "count(a)" in query
        ):
            return [{"count": 1}]
        elif (
            "UNWIND $log_ids AS log_id" in query
            and "count(al) as to_delete_count" in query
        ):
            log_ids = params.get("log_ids", [])
            return [{"to_delete_count": len(log_ids)}]
        else:
            return []

    async def mock_execute_write_query(query, params):
        if "CREATE (al:ActivityLog" in query:
            logs = params.get("logs", [])
            return {"nodes_created": len(logs)}
        elif "DETACH DELETE al" in query:
            log_ids = params.get("log_ids", [])
            return {"nodes_deleted": len(log_ids)}
        else:
            return {}

    mock_neo4j_service.execute_query = mock_execute_query
    mock_neo4j_service.execute_write_query = mock_execute_write_query

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

    # Execute sync
    with patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
        result = await _sync_holiday_activity_logs_for_account(
            mock_neo4j_service,
            mock_bigquery_service,
            account_id,
            "org_123",
            ["US"],  # Changed back to US
        )

    # Assertions
    assert result["created"] == 2
    assert result["deleted"] == 2

    # Verify AU holidays were deleted
    assert "log_au_australia_day_001" in result["operations"]["to_delete"]
    assert "log_au_anzac_day_002" in result["operations"]["to_delete"]

    # Verify US holidays were created (including US_PresidentDay)
    created_descriptions = [
        log["description"] for log in result["operations"]["to_create"]
    ]
    assert "US_PresidentDay" in created_descriptions
    assert "US_MemorialDay" in created_descriptions

    print(
        "\n✅ Test passed! AU holidays were deleted and US holidays (including US_PresidentDay) were added back."
    )


if __name__ == "__main__":
    import asyncio

    pytest.main([__file__, "-v"])
