"""Debug test to understand deletion issue."""

import os
import sys
from unittest.mock import AsyncMock

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.kene_api.database import Neo4jService
from src.kene_api.routers.activities import (
    _calculate_sync_operations,
    _delete_activity_logs_batch,
    _fetch_existing_activity_logs,
)


@pytest.mark.asyncio
async def test_deletion_batch_function_directly():
    """Test the deletion batch function to understand the issue."""
    mock_db = AsyncMock(spec=Neo4jService)

    # Setup mocks to track calls
    query_calls = []
    write_calls = []

    async def track_query(*args, **kwargs):
        query_calls.append((args, kwargs))
        # Return count result
        return [{"to_delete_count": 2}]

    async def track_write(*args, **kwargs):
        write_calls.append((args, kwargs))
        return {"nodes_deleted": 2}

    mock_db.execute_query = track_query
    mock_db.execute_write_query = track_write

    # Test deletion
    log_ids = ["log_us_presidents_day", "log_us_memorial_day"]
    result = await _delete_activity_logs_batch(mock_db, log_ids)

    print("\nQuery calls:")
    for i, (args, kwargs) in enumerate(query_calls):
        print(f"  Call {i}: args={args}, kwargs={kwargs}")

    print("\nWrite calls:")
    for i, (args, kwargs) in enumerate(write_calls):
        print(f"  Call {i}: args={args}, kwargs={kwargs}")

    assert result == 2


@pytest.mark.asyncio
async def test_fetch_existing_logs_format():
    """Test the format of existing logs fetch."""
    mock_db = AsyncMock(spec=Neo4jService)

    # Mock the response
    mock_db.execute_query.return_value = [
        {
            "log_id": "log_us_presidents_day",
            "description": "US_PresidentDay",
            "start_date": "2024-02-19",
            "end_date": "2024-02-19",
            "activity_id": "act_00_us",
            "has_metric_relationship": False,
        },
        {
            "log_id": "log_us_memorial_day",
            "description": "US_MemorialDay",
            "start_date": "2024-05-27",
            "end_date": "2024-05-27",
            "activity_id": "act_00_us",
            "has_metric_relationship": False,
        },
    ]

    # Call the function
    existing_holidays, protected_logs = await _fetch_existing_activity_logs(
        mock_db, "acc_test"
    )

    print("\nExisting holidays:")
    for key, log_id in existing_holidays.items():
        print(f"  {key} -> {log_id}")

    print(f"\nProtected logs: {protected_logs}")

    # Verify the structure: keys are (description, start_date, end_date, activity_id)
    key = ("US_PresidentDay", "2024-02-19", "2024-02-19", "act_00_us")
    assert key in existing_holidays
    assert existing_holidays[key] == "log_us_presidents_day"
    assert len(protected_logs) == 0


@pytest.mark.asyncio
async def test_calculate_sync_operations():
    """Test sync operation calculation."""
    # Existing holidays in Neo4j
    existing_holidays = {
        (
            "US_PresidentDay",
            "2024-02-19",
            "2024-02-19",
            "act_00_us",
        ): "log_us_presidents_day",
        (
            "US_MemorialDay",
            "2024-05-27",
            "2024-05-27",
            "act_00_us",
        ): "log_us_memorial_day",
    }

    # BigQuery returns AU holidays
    bigquery_holidays = [
        {
            "description": "AU_AustraliaDay",
            "start_date": "2024-01-26",
            "end_date": "2024-01-26",
            "region": "AU",
        },
        {
            "description": "AU_AnzacDay",
            "start_date": "2024-04-25",
            "end_date": "2024-04-25",
            "region": "AU",
        },
    ]

    protected_logs = set()  # No protected logs

    # Calculate operations
    operations = _calculate_sync_operations(
        existing_holidays, bigquery_holidays, protected_logs, "acc_test"
    )

    print("\nOperations to create:")
    for log in operations["to_create"]:
        print(f"  {log}")

    print(f"\nOperations to delete: {operations['to_delete']}")
    print(f"Protected from deletion: {operations['protected']}")

    # Verify US holidays should be deleted
    assert "log_us_presidents_day" in operations["to_delete"]
    assert "log_us_memorial_day" in operations["to_delete"]
    assert len(operations["to_delete"]) == 2

    # Verify AU holidays should be created
    assert len(operations["to_create"]) == 2
    descriptions = [log["description"] for log in operations["to_create"]]
    assert "AU_AustraliaDay" in descriptions
    assert "AU_AnzacDay" in descriptions


if __name__ == "__main__":
    import asyncio

    print("Running deletion batch test...")
    asyncio.run(test_deletion_batch_function_directly())

    print("\n\nRunning fetch existing logs test...")
    asyncio.run(test_fetch_existing_logs_format())

    print("\n\nRunning calculate sync operations test...")
    asyncio.run(test_calculate_sync_operations())
