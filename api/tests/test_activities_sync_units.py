"""Unit tests for sync helper functions."""

import pytest
from unittest.mock import Mock, AsyncMock
from fastapi import HTTPException

from src.kene_api.routers.activities import (
    _validate_account_and_get_regions,
    _fetch_existing_activity_logs,
    _calculate_sync_operations,
    _create_activity_logs_batch,
    _delete_activity_logs_batch,
    _execute_sync_operations,
)


class TestValidateAccountAndGetRegions:
    """Test account validation and region fetching."""

    @pytest.mark.asyncio
    async def test_valid_account_with_regions(self):
        """Test with valid account that has regions."""
        mock_db = AsyncMock()
        mock_db.execute_query.side_effect = [
            [{"regions": ["US", "CA"]}],  # Account query
            [{"a": {}}],  # Activity exists query
        ]

        result = await _validate_account_and_get_regions(mock_db, "acc_123")

        assert result["regions"] == ["US", "CA"]
        assert result["has_regions"] is True
        assert mock_db.execute_query.call_count == 2

    @pytest.mark.asyncio
    async def test_account_not_found(self):
        """Test with non-existent account."""
        mock_db = AsyncMock()
        mock_db.execute_query.return_value = []

        with pytest.raises(HTTPException) as exc_info:
            await _validate_account_and_get_regions(mock_db, "acc_invalid")

        assert exc_info.value.status_code == 404
        assert "Account acc_invalid not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_account_no_regions(self):
        """Test with account that has no regions."""
        mock_db = AsyncMock()
        mock_db.execute_query.return_value = [{"regions": []}]

        result = await _validate_account_and_get_regions(mock_db, "acc_123")

        assert result["regions"] == []
        assert result["has_regions"] is False
        # Should not check for activity when no regions
        assert mock_db.execute_query.call_count == 1

    @pytest.mark.asyncio
    async def test_activity_not_found(self):
        """Test when act_00 doesn't exist for account."""
        mock_db = AsyncMock()
        mock_db.execute_query.side_effect = [
            [{"regions": ["US"]}],  # Account query
            [],  # Activity not found
        ]

        with pytest.raises(HTTPException) as exc_info:
            await _validate_account_and_get_regions(mock_db, "acc_123")

        assert exc_info.value.status_code == 404
        assert "Activity act_00 not found" in str(exc_info.value.detail)


class TestFetchExistingActivityLogs:
    """Test fetching existing activity logs."""

    @pytest.mark.asyncio
    async def test_fetch_logs_with_protected(self):
        """Test fetching logs with some protected by metric relationships."""
        mock_db = AsyncMock()
        mock_db.execute_query.return_value = [
            {
                "log_id": "log_1",
                "description": "Holiday1",
                "start_date": "2024-01-01",
                "end_date": "2024-01-01",
                "has_metric_relationship": False,
            },
            {
                "log_id": "log_2",
                "description": "Holiday2",
                "start_date": "2024-02-01",
                "end_date": "2024-02-01",
                "has_metric_relationship": True,
            },
        ]

        existing_holidays, protected_logs = await _fetch_existing_activity_logs(
            mock_db, "acc_123"
        )

        assert len(existing_holidays) == 2
        assert ("Holiday1", "2024-01-01", "2024-01-01") in existing_holidays
        assert ("Holiday2", "2024-02-01", "2024-02-01") in existing_holidays
        assert len(protected_logs) == 1
        assert "log_2" in protected_logs

    @pytest.mark.asyncio
    async def test_fetch_no_logs(self):
        """Test when no logs exist."""
        mock_db = AsyncMock()
        mock_db.execute_query.return_value = []

        existing_holidays, protected_logs = await _fetch_existing_activity_logs(
            mock_db, "acc_123"
        )

        assert len(existing_holidays) == 0
        assert len(protected_logs) == 0


class TestCalculateSyncOperations:
    """Test sync operation calculation."""

    def test_all_operations(self):
        """Test with creates, deletes, and protected logs."""
        existing_holidays = {
            ("Holiday1", "2024-01-01", "2024-01-01"): "log_1",
            ("Holiday2", "2024-02-01", "2024-02-01"): "log_2",
            ("Holiday3", "2024-03-01", "2024-03-01"): "log_3",
        }

        bigquery_holidays = [
            {
                "description": "Holiday1",
                "start_date": "2024-01-01",
                "end_date": "2024-01-01",
            },
            {
                "description": "Holiday4",
                "start_date": "2024-04-01",
                "end_date": "2024-04-01",
            },
        ]

        protected_logs = {"log_2"}

        operations = _calculate_sync_operations(
            existing_holidays, bigquery_holidays, protected_logs, "acc_123"
        )

        # Should create Holiday4
        assert len(operations["to_create"]) == 1
        assert operations["to_create"][0]["description"] == "Holiday4"

        # Should delete Holiday3 (Holiday2 is protected)
        assert len(operations["to_delete"]) == 1
        assert "log_3" in operations["to_delete"]

        # Should protect Holiday2
        assert len(operations["protected"]) == 1
        assert "log_2" in operations["protected"]

    def test_no_changes_needed(self):
        """Test when everything is already in sync."""
        existing_holidays = {
            ("Holiday1", "2024-01-01", "2024-01-01"): "log_1",
        }

        bigquery_holidays = [
            {
                "description": "Holiday1",
                "start_date": "2024-01-01",
                "end_date": "2024-01-01",
            },
        ]

        operations = _calculate_sync_operations(
            existing_holidays, bigquery_holidays, set(), "acc_123"
        )

        assert len(operations["to_create"]) == 0
        assert len(operations["to_delete"]) == 0
        assert len(operations["protected"]) == 0


class TestBatchOperations:
    """Test batch create and delete operations."""

    @pytest.mark.asyncio
    async def test_create_batch_success(self):
        """Test successful batch creation."""
        mock_db = AsyncMock()
        mock_db.execute_write_query.return_value = {"nodes_created": 3}

        logs_batch = [
            {"activity_log_id": "log_1", "description": "Holiday1"},
            {"activity_log_id": "log_2", "description": "Holiday2"},
            {"activity_log_id": "log_3", "description": "Holiday3"},
        ]

        created = await _create_activity_logs_batch(mock_db, logs_batch)

        assert created == 3
        mock_db.execute_write_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_empty_batch(self):
        """Test with empty batch."""
        mock_db = AsyncMock()

        created = await _create_activity_logs_batch(mock_db, [])

        assert created == 0
        mock_db.execute_write_query.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_batch_success(self):
        """Test successful batch deletion."""
        mock_db = AsyncMock()
        mock_db.execute_query.return_value = [{"to_delete_count": 2}]
        mock_db.execute_write_query.return_value = {"nodes_deleted": 2}

        deleted = await _delete_activity_logs_batch(mock_db, ["log_1", "log_2"])

        assert deleted == 2
        assert mock_db.execute_query.call_count == 1  # Count query
        assert mock_db.execute_write_query.call_count == 1  # Delete query

    @pytest.mark.asyncio
    async def test_delete_batch_all_protected(self):
        """Test when all logs are protected."""
        mock_db = AsyncMock()
        mock_db.execute_query.return_value = [{"to_delete_count": 0}]

        deleted = await _delete_activity_logs_batch(mock_db, ["log_1", "log_2"])

        assert deleted == 0
        # Should not execute delete when count is 0
        mock_db.execute_write_query.assert_not_called()


class TestExecuteSyncOperations:
    """Test sync operation execution with batching."""

    @pytest.mark.asyncio
    async def test_execute_with_batching(self):
        """Test operations are properly batched."""
        mock_db = AsyncMock()
        mock_db.execute_write_query.return_value = {"nodes_created": 50}
        mock_db.execute_query.return_value = [{"to_delete_count": 50}]

        # Create 120 items to test batching (batch size is 50)
        operations = {
            "to_create": [{"id": f"create_{i}"} for i in range(120)],
            "to_delete": [f"delete_{i}" for i in range(75)],
            "protected": [],
        }

        results = await _execute_sync_operations(mock_db, operations)

        # Should create 3 batches for creates (50, 50, 20)
        assert results["created"] == 150  # 3 batches * 50 (mock returns 50)
        # Should create 2 batches for deletes (50, 25)
        assert results["deleted"] == 100  # 2 batches * 50 (mock returns 50)
        assert len(results["errors"]) == 0

        # Verify correct number of calls
        create_calls = [
            call
            for call in mock_db.execute_write_query.call_args_list
            if "logs" in call.kwargs
        ]
        delete_calls = [
            call
            for call in mock_db.execute_write_query.call_args_list
            if "log_ids" in call.kwargs
        ]

        assert len(create_calls) == 3
        assert len(delete_calls) == 2

    @pytest.mark.asyncio
    async def test_execute_with_errors(self):
        """Test handling of batch errors."""
        mock_db = AsyncMock()
        mock_db.execute_write_query.side_effect = [
            {"nodes_created": 50},  # First batch succeeds
            Exception("Database error"),  # Second batch fails
            {"nodes_deleted": 25},  # Delete succeeds
        ]

        operations = {
            "to_create": [{"id": f"create_{i}"} for i in range(100)],
            "to_delete": [f"delete_{i}" for i in range(25)],
            "protected": [],
        }

        results = await _execute_sync_operations(mock_db, operations)

        assert results["created"] == 50  # Only first batch succeeded
        assert results["deleted"] == 25
        assert len(results["errors"]) == 1
        assert "Create batch 2 failed" in results["errors"][0]


@pytest.mark.parametrize(
    "batch_size,total_items,expected_batches",
    [
        (50, 150, 3),
        (50, 50, 1),
        (50, 49, 1),
        (50, 0, 0),
        (50, 151, 4),
    ],
)
def test_batch_calculation(batch_size, total_items, expected_batches):
    """Test batch size calculations."""
    items = list(range(total_items))
    batches = []

    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        batches.append(batch)

    assert len(batches) == expected_batches

    # Verify all items are included
    if total_items > 0:
        all_items = [item for batch in batches for item in batch]
        assert len(all_items) == total_items
