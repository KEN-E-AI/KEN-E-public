"""Tests for usage tracking service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.adk.tracking.usage import (
    ExecutionStatus,
    UsageEvent,
    UsageTracker,
    get_usage_tracker,
    reset_usage_tracker,
)


class TestUsageEvent:
    """Tests for UsageEvent model."""

    def test_minimal_event(self):
        """Test creating minimal event."""
        event = UsageEvent(
            tool_name="test_tool",
            user_id="user1",
            account_id="acct1",
            status=ExecutionStatus.SUCCESS,
        )

        assert event.tool_name == "test_tool"
        assert event.user_id == "user1"
        assert event.account_id == "acct1"
        assert event.status == ExecutionStatus.SUCCESS
        assert event.event_id is not None
        assert event.timestamp is not None

    def test_full_event(self):
        """Test creating event with all fields."""
        now = datetime.now(timezone.utc)
        event = UsageEvent(
            event_id="test-123",
            timestamp=now,
            tool_name="test_tool",
            mcp_server="test_server",
            user_id="user1",
            account_id="acct1",
            organization_id="org1",
            status=ExecutionStatus.FAILURE,
            duration_ms=150,
            error_message="Test error",
            input_tokens=100,
            output_tokens=50,
            metadata={"key": "value"},
        )

        assert event.event_id == "test-123"
        assert event.timestamp == now
        assert event.mcp_server == "test_server"
        assert event.organization_id == "org1"
        assert event.duration_ms == 150
        assert event.error_message == "Test error"
        assert event.input_tokens == 100
        assert event.output_tokens == 50
        assert event.metadata == {"key": "value"}


class TestExecutionStatus:
    """Tests for ExecutionStatus enum."""

    def test_status_values(self):
        """Test all status values are accessible."""
        assert ExecutionStatus.SUCCESS.value == "success"
        assert ExecutionStatus.FAILURE.value == "failure"
        assert ExecutionStatus.TIMEOUT.value == "timeout"
        assert ExecutionStatus.PERMISSION_DENIED.value == "permission_denied"
        assert ExecutionStatus.RATE_LIMITED.value == "rate_limited"


class TestUsageTracker:
    """Tests for UsageTracker."""

    @pytest.fixture
    def tracker(self):
        """Create a tracker with in-memory storage."""
        t = UsageTracker()
        t._use_firestore = False  # Force in-memory storage
        return t

    @pytest.mark.asyncio
    async def test_track_execution_returns_event_id(self, tracker):
        """Test that tracking returns an event ID."""
        event_id = await tracker.track_execution(
            tool_name="test_tool",
            user_id="user1",
            account_id="acct1",
            status=ExecutionStatus.SUCCESS,
        )

        assert event_id is not None
        assert isinstance(event_id, str)
        assert len(event_id) > 0

    @pytest.mark.asyncio
    async def test_track_execution_adds_to_batch(self, tracker):
        """Test that tracking adds event to batch."""
        await tracker.track_execution(
            tool_name="test_tool",
            user_id="user1",
            account_id="acct1",
            status=ExecutionStatus.SUCCESS,
        )

        assert tracker.get_pending_count() == 1

    @pytest.mark.asyncio
    async def test_flush_moves_events_to_store(self, tracker):
        """Test that flush moves events from batch to store."""
        await tracker.track_execution(
            tool_name="tool1",
            user_id="user1",
            account_id="acct1",
            status=ExecutionStatus.SUCCESS,
        )
        await tracker.track_execution(
            tool_name="tool2",
            user_id="user1",
            account_id="acct1",
            status=ExecutionStatus.FAILURE,
        )

        assert tracker.get_pending_count() == 2
        assert tracker.get_stored_count() == 0

        await tracker.flush()

        assert tracker.get_pending_count() == 0
        assert tracker.get_stored_count() == 2

    @pytest.mark.asyncio
    async def test_batch_auto_flush_on_size_limit(self, tracker):
        """Test that batch auto-flushes when size limit reached."""
        tracker.BATCH_SIZE = 3  # Small batch for testing

        # Add 3 events (should trigger auto-flush)
        for i in range(3):
            await tracker.track_execution(
                tool_name=f"tool_{i}",
                user_id="user1",
                account_id="acct1",
                status=ExecutionStatus.SUCCESS,
            )

        # Batch should have been flushed
        assert tracker.get_pending_count() == 0
        assert tracker.get_stored_count() == 3


class TestUsageAggregation:
    """Tests for usage aggregation."""

    @pytest.fixture
    def tracker(self):
        """Create a tracker with in-memory storage."""
        t = UsageTracker()
        t._use_firestore = False
        return t

    @pytest.mark.asyncio
    async def test_aggregation_counts(self, tracker):
        """Test that aggregation counts are correct."""
        # Track various events
        await tracker.track_execution(
            tool_name="tool1",
            user_id="user1",
            account_id="acct1",
            status=ExecutionStatus.SUCCESS,
            duration_ms=100,
        )
        await tracker.track_execution(
            tool_name="tool1",
            user_id="user2",
            account_id="acct1",
            status=ExecutionStatus.SUCCESS,
            duration_ms=200,
        )
        await tracker.track_execution(
            tool_name="tool2",
            user_id="user1",
            account_id="acct1",
            status=ExecutionStatus.FAILURE,
            error_message="Test error",
        )

        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=1)
        end = now + timedelta(hours=1)

        agg = await tracker.get_usage_aggregation(
            account_id="acct1",
            start_date=start,
            end_date=end,
        )

        assert agg.total_calls == 3
        assert agg.success_count == 2
        assert agg.failure_count == 1
        assert agg.success_rate == pytest.approx(2 / 3)

    @pytest.mark.asyncio
    async def test_aggregation_by_tool(self, tracker):
        """Test that by_tool aggregation is correct."""
        await tracker.track_execution(
            tool_name="analytics",
            user_id="user1",
            account_id="acct1",
            status=ExecutionStatus.SUCCESS,
        )
        await tracker.track_execution(
            tool_name="analytics",
            user_id="user1",
            account_id="acct1",
            status=ExecutionStatus.SUCCESS,
        )
        await tracker.track_execution(
            tool_name="crm",
            user_id="user1",
            account_id="acct1",
            status=ExecutionStatus.SUCCESS,
        )

        now = datetime.now(timezone.utc)
        agg = await tracker.get_usage_aggregation(
            account_id="acct1",
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
        )

        assert agg.by_tool["analytics"] == 2
        assert agg.by_tool["crm"] == 1

    @pytest.mark.asyncio
    async def test_aggregation_by_user(self, tracker):
        """Test that by_user aggregation is correct."""
        await tracker.track_execution(
            tool_name="tool",
            user_id="user1",
            account_id="acct1",
            status=ExecutionStatus.SUCCESS,
        )
        await tracker.track_execution(
            tool_name="tool",
            user_id="user1",
            account_id="acct1",
            status=ExecutionStatus.SUCCESS,
        )
        await tracker.track_execution(
            tool_name="tool",
            user_id="user2",
            account_id="acct1",
            status=ExecutionStatus.SUCCESS,
        )

        now = datetime.now(timezone.utc)
        agg = await tracker.get_usage_aggregation(
            account_id="acct1",
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
        )

        assert agg.by_user["user1"] == 2
        assert agg.by_user["user2"] == 1

    @pytest.mark.asyncio
    async def test_aggregation_filters_by_account(self, tracker):
        """Test that aggregation filters by account."""
        await tracker.track_execution(
            tool_name="tool",
            user_id="user1",
            account_id="acct1",
            status=ExecutionStatus.SUCCESS,
        )
        await tracker.track_execution(
            tool_name="tool",
            user_id="user1",
            account_id="acct2",  # Different account
            status=ExecutionStatus.SUCCESS,
        )

        now = datetime.now(timezone.utc)
        agg = await tracker.get_usage_aggregation(
            account_id="acct1",
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
        )

        assert agg.total_calls == 1  # Only acct1

    @pytest.mark.asyncio
    async def test_aggregation_filters_by_date_range(self, tracker):
        """Test that aggregation filters by date range."""
        now = datetime.now(timezone.utc)

        # Create events with specific timestamps
        old_event = UsageEvent(
            tool_name="tool",
            user_id="user1",
            account_id="acct1",
            status=ExecutionStatus.SUCCESS,
            timestamp=now - timedelta(days=7),  # Old event
        )
        recent_event = UsageEvent(
            tool_name="tool",
            user_id="user1",
            account_id="acct1",
            status=ExecutionStatus.SUCCESS,
            timestamp=now,  # Recent event
        )

        tracker._in_memory_store = [old_event, recent_event]

        # Query only last day
        agg = await tracker.get_usage_aggregation(
            account_id="acct1",
            start_date=now - timedelta(days=1),
            end_date=now + timedelta(hours=1),
        )

        assert agg.total_calls == 1  # Only recent

    @pytest.mark.asyncio
    async def test_aggregation_calculates_avg_duration(self, tracker):
        """Test that average duration is calculated correctly."""
        await tracker.track_execution(
            tool_name="tool",
            user_id="user1",
            account_id="acct1",
            status=ExecutionStatus.SUCCESS,
            duration_ms=100,
        )
        await tracker.track_execution(
            tool_name="tool",
            user_id="user1",
            account_id="acct1",
            status=ExecutionStatus.SUCCESS,
            duration_ms=200,
        )

        now = datetime.now(timezone.utc)
        agg = await tracker.get_usage_aggregation(
            account_id="acct1",
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
        )

        assert agg.avg_duration_ms == 150.0

    @pytest.mark.asyncio
    async def test_aggregation_calculates_total_tokens(self, tracker):
        """Test that total tokens is calculated correctly."""
        await tracker.track_execution(
            tool_name="tool",
            user_id="user1",
            account_id="acct1",
            status=ExecutionStatus.SUCCESS,
            input_tokens=100,
            output_tokens=50,
        )
        await tracker.track_execution(
            tool_name="tool",
            user_id="user1",
            account_id="acct1",
            status=ExecutionStatus.SUCCESS,
            input_tokens=200,
            output_tokens=100,
        )

        now = datetime.now(timezone.utc)
        agg = await tracker.get_usage_aggregation(
            account_id="acct1",
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
        )

        assert agg.total_tokens == 450  # (100+50) + (200+100)


class TestSingleton:
    """Tests for singleton behavior."""

    @pytest.mark.asyncio
    async def test_get_usage_tracker_returns_same_instance(self):
        """Test that get_usage_tracker returns same instance."""
        await reset_usage_tracker()

        tracker1 = get_usage_tracker()
        tracker2 = get_usage_tracker()

        assert tracker1 is tracker2

        await reset_usage_tracker()

    @pytest.mark.asyncio
    async def test_reset_clears_singleton(self):
        """Test that reset clears the singleton."""
        tracker1 = get_usage_tracker()
        await reset_usage_tracker()
        tracker2 = get_usage_tracker()

        assert tracker1 is not tracker2

        await reset_usage_tracker()
