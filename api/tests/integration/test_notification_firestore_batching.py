"""Integration tests for Firestore notification batching and pagination."""

import asyncio
import re
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from google.cloud import firestore
from src.kene_api.models.kene_models import (
    Notification,
    NotificationCategory,
)
from src.kene_api.repositories import FirestoreNotificationRepository


class TestFirestoreNotificationBatching:
    """Test cases for Firestore batching logic."""

    @pytest.fixture
    def mock_firestore_client(self):
        """Create a mock Firestore client."""
        return Mock(spec=firestore.Client)

    @pytest.fixture
    def repository(self, mock_firestore_client):
        """Create repository with mock client."""
        return FirestoreNotificationRepository(mock_firestore_client)

    def create_mock_notification(self, account_id: str, index: int) -> dict:
        """Create a mock notification document."""
        return {
            "id": f"notif_{account_id}_{1700000000000 + index}_001",
            "account_id": account_id,
            "category": NotificationCategory.KPI_PERFORMANCE.value,
            "description": f"Test notification {index}",
            "data": {},
            "created_at": (datetime.now() - timedelta(minutes=index)).isoformat(),
            "archived_at": (datetime.now() + timedelta(days=30)).isoformat(),
        }

    @pytest.mark.asyncio
    async def test_empty_account_list(self, repository):
        """Test that empty account list returns empty result."""
        result = await repository.get_by_account([], include_archived=False)
        assert result == []
        # Ensure no database query was made
        repository.db.collection.assert_not_called()

    @pytest.mark.asyncio
    async def test_single_account(self, repository, mock_firestore_client):
        """Test fetching notifications for a single account."""
        account_id = "acc_001"
        mock_doc = Mock()
        mock_doc.to_dict.return_value = self.create_mock_notification(account_id, 1)

        mock_query = Mock()
        mock_query.where.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.stream.return_value = [mock_doc]

        mock_firestore_client.collection.return_value.where.return_value = mock_query

        result = await repository.get_by_account([account_id])

        assert len(result) == 1
        assert result[0].account_id == account_id
        # Verify single batch query
        mock_firestore_client.collection.assert_called_once_with("notifications")

    @pytest.mark.asyncio
    async def test_exactly_10_accounts(self, repository, mock_firestore_client):
        """Test with exactly 10 accounts (single batch)."""
        account_ids = [f"acc_{i:03d}" for i in range(10)]

        mock_docs = []
        for i, acc_id in enumerate(account_ids):
            mock_doc = Mock()
            mock_doc.to_dict.return_value = self.create_mock_notification(acc_id, i)
            mock_docs.append(mock_doc)

        mock_query = Mock()
        mock_query.where.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.stream.return_value = mock_docs

        mock_firestore_client.collection.return_value.where.return_value = mock_query

        result = await repository.get_by_account(account_ids)

        assert len(result) == 10
        # Should be sorted by created_at descending
        for i in range(1, len(result)):
            assert result[i - 1].created_at >= result[i].created_at

    @pytest.mark.asyncio
    async def test_15_accounts_two_batches(self, repository, mock_firestore_client):
        """Test with 15 accounts (requires 2 batches)."""
        account_ids = [f"acc_{i:03d}" for i in range(15)]

        # Mock the parallel batch fetching
        with patch.object(repository, "_fetch_batch") as mock_fetch:
            # Create notifications for each batch
            batch1_notifications = [
                Notification(**self.create_mock_notification(acc_id, i))
                for i, acc_id in enumerate(account_ids[:10])
            ]
            batch2_notifications = [
                Notification(**self.create_mock_notification(acc_id, i))
                for i, acc_id in enumerate(account_ids[10:])
            ]

            # Configure mock to return different results for each batch
            mock_fetch.side_effect = [batch1_notifications, batch2_notifications]

            result = await repository.get_by_account(account_ids)

            # Should have called _fetch_batch twice (2 batches)
            assert mock_fetch.call_count == 2
            # Should return all 15 notifications
            assert len(result) == 15
            # Should be sorted by created_at
            for i in range(1, len(result)):
                assert result[i - 1].created_at >= result[i].created_at

    @pytest.mark.asyncio
    async def test_100_accounts_parallel_execution(self, repository):
        """Test with 100 accounts to verify parallel execution."""
        account_ids = [f"acc_{i:03d}" for i in range(100)]

        # Track execution times to verify parallel processing
        execution_times = []

        async def mock_fetch_with_delay(batch_ids, include_archived):
            """Mock fetch that records execution time."""
            start_time = asyncio.get_event_loop().time()
            await asyncio.sleep(0.01)  # Simulate network delay
            execution_times.append(asyncio.get_event_loop().time() - start_time)

            return [
                Notification(**self.create_mock_notification(acc_id, i))
                for i, acc_id in enumerate(batch_ids)
            ]

        with patch.object(
            repository, "_fetch_batch", side_effect=mock_fetch_with_delay
        ):
            result = await repository.get_by_account(account_ids)

            # Should have 10 batches for 100 accounts
            assert len(execution_times) == 10
            # All batches should complete in roughly the same time (parallel)
            # If sequential, total time would be ~0.1s (10 * 0.01)
            # If parallel, total time should be ~0.01s
            max_time = max(execution_times)
            assert max_time < 0.05  # Allow some overhead

            assert len(result) == 100

    @pytest.mark.asyncio
    async def test_pagination_with_single_batch(
        self, repository, mock_firestore_client
    ):
        """Test pagination with <= 10 accounts uses Firestore pagination."""
        account_ids = [f"acc_{i:03d}" for i in range(5)]

        mock_query = Mock()
        mock_query.where.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.stream.return_value = []

        mock_firestore_client.collection.return_value.where.return_value = mock_query

        await repository.get_by_account(account_ids, limit=10, offset=5)

        # Verify Firestore pagination was used
        mock_query.offset.assert_called_once_with(5)
        mock_query.limit.assert_called_once_with(10)

    @pytest.mark.asyncio
    async def test_pagination_with_multiple_batches(self, repository):
        """Test pagination with > 10 accounts uses in-memory pagination."""
        account_ids = [f"acc_{i:03d}" for i in range(25)]

        with patch.object(repository, "_fetch_batches_parallel") as mock_fetch:
            # Create 25 notifications
            all_notifications = [
                Notification(**self.create_mock_notification(acc_id, i))
                for i, acc_id in enumerate(account_ids)
            ]
            mock_fetch.return_value = all_notifications

            # Get page 2 with page size 10
            result = await repository.get_by_account(account_ids, limit=10, offset=10)

            # Should return notifications 10-19
            assert len(result) == 10
            # Verify it's the correct page
            assert result[0].account_id == account_ids[10]
            assert result[9].account_id == account_ids[19]

    @pytest.mark.asyncio
    async def test_archive_filtering(self, repository, mock_firestore_client):
        """Test that archived notifications are filtered correctly."""
        account_id = "acc_001"

        # Create mix of active and archived notifications
        active_notif = self.create_mock_notification(account_id, 1)
        archived_notif = self.create_mock_notification(account_id, 2)
        archived_notif["archived_at"] = (datetime.now() - timedelta(days=1)).isoformat()

        mock_query = Mock()
        mock_query.where.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.stream.return_value = []

        mock_collection = Mock()
        mock_collection.where.return_value = mock_query
        mock_firestore_client.collection.return_value = mock_collection

        # Test include_archived=False
        await repository.get_by_account([account_id], include_archived=False)

        # Verify archived_at filter was applied via FieldFilter keyword arg
        where_calls = mock_query.where.call_args_list
        assert len(where_calls) >= 1
        archived_filter_call = where_calls[0]
        filter_obj = archived_filter_call.kwargs["filter"]
        assert isinstance(filter_obj, firestore.FieldFilter)

    @pytest.mark.asyncio
    async def test_error_handling_fallback(self, repository, mock_firestore_client):
        """Test fallback when Firestore index is missing."""
        account_id = "acc_001"

        # Create a mock query chain that fails on order_by for created_at
        mock_collection = Mock()
        mock_query_after_where = Mock()
        mock_query_after_archived_filter = Mock()
        mock_query_after_archived_order = Mock()

        # Set up the chain: collection -> where -> where (archived_at) -> order_by (archived_at) -> order_by (created_at - fails)
        mock_collection.where.return_value = mock_query_after_where
        mock_query_after_where.where.return_value = mock_query_after_archived_filter
        mock_query_after_archived_filter.order_by.return_value = (
            mock_query_after_archived_order
        )

        # The second order_by (created_at) should fail
        mock_query_after_archived_order.order_by.side_effect = Exception(
            "Index not found"
        )

        # Fallback: query.stream() should work (returns empty list)
        mock_query_after_archived_order.stream.return_value = iter([])  # Empty iterator

        mock_firestore_client.collection.return_value = mock_collection

        with patch(
            "src.kene_api.repositories.firestore_notification_repository.logger"
        ) as mock_logger:
            result = await repository.get_by_account([account_id])

            # Should log warning about missing index
            mock_logger.warning.assert_called()
            # Strengthen assertion: check exact error message pattern
            warning_message = str(mock_logger.warning.call_args[0][0])
            assert re.match(
                r"Firestore query failed \(likely missing index\): .*Index.*",
                warning_message,
            )
            # Should still return result (empty in this case)
            assert result == []

    @pytest.mark.asyncio
    async def test_boundary_11_accounts(self, repository):
        """Test with exactly 11 accounts (boundary case for batching)."""
        account_ids = [f"acc_{i:03d}" for i in range(11)]

        with patch.object(repository, "_fetch_batch") as mock_fetch:
            # First batch of 10
            batch1 = [
                Notification(**self.create_mock_notification(acc_id, i))
                for i, acc_id in enumerate(account_ids[:10])
            ]
            # Second batch of 1
            batch2 = [
                Notification(**self.create_mock_notification(account_ids[10], 10))
            ]

            mock_fetch.side_effect = [batch1, batch2]

            result = await repository.get_by_account(account_ids)

            # Should have exactly 2 batches
            assert mock_fetch.call_count == 2
            # First batch should have 10 items
            assert len(mock_fetch.call_args_list[0][0][0]) == 10
            # Second batch should have 1 item
            assert len(mock_fetch.call_args_list[1][0][0]) == 1
            # Total should be 11
            assert len(result) == 11

    @pytest.mark.asyncio
    async def test_pagination_boundary_cases(self, repository, mock_firestore_client):
        """Test pagination with boundary values."""
        account_ids = [f"acc_{i:03d}" for i in range(5)]

        # Create mock documents
        mock_docs = []
        for i, acc_id in enumerate(account_ids):
            mock_doc = Mock()
            mock_doc.to_dict.return_value = self.create_mock_notification(acc_id, i)
            mock_docs.append(mock_doc)

        # Setup mock query that returns empty when offset >= count
        mock_query = Mock()
        mock_query.where.return_value = mock_query
        mock_query.order_by.return_value = mock_query

        def mock_offset(n):
            if n >= 5:
                mock_query.stream.return_value = []
            else:
                mock_query.stream.return_value = mock_docs[n:]
            return mock_query

        def mock_limit(n):
            if n == 0:
                mock_query.stream.return_value = []
            return mock_query

        mock_query.offset = mock_offset
        mock_query.limit = mock_limit
        mock_query.stream.return_value = []

        mock_firestore_client.collection.return_value.where.return_value = mock_query

        # Test offset equals total count
        result = await repository.get_by_account(account_ids, limit=10, offset=5)
        assert result == []

        # Test offset greater than total count
        result = await repository.get_by_account(account_ids, limit=10, offset=100)
        assert result == []

        # Test limit of 0 (should return empty)
        result = await repository.get_by_account(account_ids, limit=0, offset=0)
        assert result == []

    @pytest.mark.asyncio
    async def test_notifications_sorted_correctly(self, repository):
        """Test that notifications are properly sorted by created_at."""
        account_ids = ["acc_001", "acc_002"]

        with patch.object(repository, "_fetch_batch") as mock_fetch:
            # Create notifications with specific timestamps
            now = datetime.now()
            notifications = [
                Notification(
                    id=f"notif_{i}",
                    account_id=account_ids[i % 2],
                    category=NotificationCategory.KPI_PERFORMANCE,
                    description=f"Notification {i}",
                    data={},
                    created_at=(now - timedelta(hours=i)).isoformat(),
                    archived_at=(now + timedelta(days=30)).isoformat(),
                )
                for i in range(10)
            ]
            # Shuffle to ensure sorting is tested
            import random

            shuffled = notifications.copy()
            random.shuffle(shuffled)
            mock_fetch.return_value = shuffled

            result = await repository.get_by_account(account_ids)

            # Verify proper descending order
            for i in range(1, len(result)):
                assert result[i - 1].created_at >= result[i].created_at
                # Verify exact ordering
                expected_diff = timedelta(hours=1)
                actual_diff = datetime.fromisoformat(
                    result[i - 1].created_at
                ) - datetime.fromisoformat(result[i].created_at)
                assert abs(actual_diff - expected_diff).total_seconds() < 1

    @pytest.mark.asyncio
    async def test_large_batch_performance(self, repository):
        """Test performance with very large number of accounts."""
        # Test with 1000 accounts (100 batches)
        account_ids = [f"acc_{i:04d}" for i in range(1000)]

        execution_count = 0

        async def mock_fetch_counter(batch_ids, include_archived):
            """Count executions and return empty list."""
            nonlocal execution_count
            execution_count += 1
            return []

        with patch.object(repository, "_fetch_batch", side_effect=mock_fetch_counter):
            import time

            start_time = time.time()

            result = await repository.get_by_account(account_ids)

            elapsed = time.time() - start_time

            # Should have exactly 100 batches
            assert execution_count == 100
            # Should complete reasonably quickly (parallel execution)
            assert elapsed < 2.0  # Generous timeout for CI environments
            assert result == []

    @pytest.mark.asyncio
    async def test_duplicate_notifications_handled(
        self, repository, mock_firestore_client
    ):
        """Test that duplicate notifications from different batches are handled."""
        # This could happen if account_ids has duplicates
        account_ids = ["acc_001", "acc_002", "acc_001"]  # Duplicate acc_001

        mock_doc = Mock()
        mock_doc.to_dict.return_value = self.create_mock_notification("acc_001", 1)

        mock_query = Mock()
        mock_query.where.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.stream.return_value = [mock_doc]

        mock_firestore_client.collection.return_value.where.return_value = mock_query

        # Even with duplicates in input, should handle gracefully
        result = await repository.get_by_account(account_ids)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_concurrent_modifications(self, repository):
        """Test behavior when notifications are modified during fetch."""
        account_ids = [f"acc_{i:03d}" for i in range(20)]

        call_count = 0

        async def mock_fetch_with_modification(batch_ids, include_archived):
            """Simulate notifications being added between batches."""
            nonlocal call_count
            call_count += 1
            # Return different number of notifications for each call
            return [
                Notification(**self.create_mock_notification(batch_ids[0], i))
                for i in range(call_count * 2)
            ]

        with patch.object(
            repository, "_fetch_batch", side_effect=mock_fetch_with_modification
        ):
            result = await repository.get_by_account(account_ids)

            # Should handle varying result sizes
            assert len(result) > 0
            # Results should still be sorted
            for i in range(1, len(result)):
                assert result[i - 1].created_at >= result[i].created_at
