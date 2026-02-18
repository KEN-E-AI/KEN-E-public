"""Tests for session timeout manager."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.adk.session.timeout import (
    SessionTimeoutManager,
    TimeoutConfig,
    configure_timeout_manager,
    reset_timeout_manager,
)


class TestTimeoutConfig:
    """Tests for TimeoutConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = TimeoutConfig()

        assert config.warning_minutes == 25
        assert config.timeout_minutes == 30
        assert config.check_interval_seconds == 30

    def test_custom_values(self):
        """Test custom configuration values."""
        config = TimeoutConfig(
            warning_minutes=10,
            timeout_minutes=15,
            check_interval_seconds=30,
        )

        assert config.warning_minutes == 10
        assert config.timeout_minutes == 15
        assert config.check_interval_seconds == 30


class TestSessionTimeoutManager:
    """Tests for SessionTimeoutManager."""

    @pytest.fixture
    def manager(self):
        """Create a manager with short intervals for testing."""
        config = TimeoutConfig(
            warning_minutes=1,  # 1 minute for testing
            timeout_minutes=2,  # 2 minutes for testing
            check_interval_seconds=1,  # 1 second for testing
        )
        return SessionTimeoutManager(config=config)

    def test_record_activity(self, manager):
        """Test recording activity."""
        manager.record_activity("user1", "sess1")

        assert manager.get_active_session_count() == 1
        assert manager.get_remaining_time("user1", "sess1") is not None

    def test_record_activity_resets_timer(self, manager):
        """Test that recording activity resets the timer."""
        manager.record_activity("user1", "sess1")
        initial_remaining = manager.get_remaining_time("user1", "sess1")

        # Wait a bit
        import time

        time.sleep(0.1)

        # Record activity again
        manager.record_activity("user1", "sess1")
        new_remaining = manager.get_remaining_time("user1", "sess1")

        # Timer should be reset (new remaining >= initial)
        assert new_remaining >= initial_remaining - 1  # Allow 1 second variance

    def test_untrack_session(self, manager):
        """Test untracking a session."""
        manager.record_activity("user1", "sess1")
        assert manager.get_active_session_count() == 1

        manager.untrack_session("user1", "sess1")
        assert manager.get_active_session_count() == 0
        assert manager.get_remaining_time("user1", "sess1") is None

    def test_remaining_time_not_tracked(self, manager):
        """Test remaining time for untracked session."""
        remaining = manager.get_remaining_time("user1", "untracked")
        assert remaining is None

    def test_remaining_time_calculation(self, manager):
        """Test remaining time is calculated correctly."""
        manager.record_activity("user1", "sess1")

        # Should be close to timeout (2 minutes = 120 seconds)
        remaining = manager.get_remaining_time("user1", "sess1")
        assert remaining is not None
        assert 115 <= remaining <= 120  # Allow 5 second variance

    def test_is_warned_false_initially(self, manager):
        """Test session is not warned initially."""
        manager.record_activity("user1", "sess1")
        assert manager.is_warned("user1", "sess1") is False

    def test_activity_clears_warning(self, manager):
        """Test that activity clears the warning flag."""
        manager.record_activity("user1", "sess1")
        manager._warned.add("user1:sess1")  # Manually set warned

        manager.record_activity("user1", "sess1")

        assert manager.is_warned("user1", "sess1") is False


class TestSessionTimeoutMonitor:
    """Tests for timeout monitoring."""

    @pytest.fixture
    def fast_manager(self):
        """Create a manager with very short intervals."""
        config = TimeoutConfig(
            warning_minutes=0,  # Instant warning
            timeout_minutes=0,  # Instant timeout
            check_interval_seconds=1,
        )
        return SessionTimeoutManager(config=config)

    @pytest.mark.asyncio
    async def test_start_stop_monitor(self, fast_manager):
        """Test starting and stopping the monitor."""
        await fast_manager.start_monitor()
        assert fast_manager._monitor_task is not None

        await fast_manager.stop_monitor()
        assert fast_manager._monitor_task is None

    @pytest.mark.asyncio
    async def test_warning_callback_called(self):
        """Test that warning callback is called."""
        warning_called = asyncio.Event()
        warned_data = {}

        async def on_warning(user_id, session_id, remaining):
            warned_data["user_id"] = user_id
            warned_data["session_id"] = session_id
            warned_data["remaining"] = remaining
            warning_called.set()

        config = TimeoutConfig(
            warning_minutes=0,  # Immediate warning
            timeout_minutes=10,  # Long timeout
            check_interval_seconds=1,
        )
        manager = SessionTimeoutManager(config=config, on_warning=on_warning)

        # Record old activity
        manager._activity["user1:sess1"] = datetime.now(timezone.utc) - timedelta(
            minutes=5
        )

        # Manually trigger check
        await manager._check_sessions()

        assert warning_called.is_set()
        assert warned_data["user_id"] == "user1"
        assert warned_data["session_id"] == "sess1"

    @pytest.mark.asyncio
    async def test_timeout_callback_called(self):
        """Test that timeout callback is called."""
        timeout_called = asyncio.Event()
        timeout_data = {}

        async def on_timeout(user_id, session_id):
            timeout_data["user_id"] = user_id
            timeout_data["session_id"] = session_id
            timeout_called.set()

        config = TimeoutConfig(
            warning_minutes=0,
            timeout_minutes=0,  # Immediate timeout
            check_interval_seconds=1,
        )
        manager = SessionTimeoutManager(config=config, on_timeout=on_timeout)

        # Record old activity
        manager._activity["user1:sess1"] = datetime.now(timezone.utc) - timedelta(
            minutes=5
        )

        # Manually trigger check
        await manager._check_sessions()

        assert timeout_called.is_set()
        assert timeout_data["user_id"] == "user1"
        assert timeout_data["session_id"] == "sess1"

    @pytest.mark.asyncio
    async def test_timeout_removes_from_tracking(self):
        """Test that timed out session is removed from tracking."""
        config = TimeoutConfig(
            warning_minutes=0,
            timeout_minutes=0,
            check_interval_seconds=1,
        )
        manager = SessionTimeoutManager(config=config)

        # Record old activity
        manager._activity["user1:sess1"] = datetime.now(timezone.utc) - timedelta(
            minutes=5
        )
        manager._warned.add("user1:sess1")

        await manager._check_sessions()

        assert manager.get_active_session_count() == 0
        assert manager.get_warned_session_count() == 0

    @pytest.mark.asyncio
    async def test_active_session_not_warned(self):
        """Test that recently active session is not warned."""
        config = TimeoutConfig(
            warning_minutes=25,  # 25 minutes
            timeout_minutes=30,
            check_interval_seconds=1,
        )
        manager = SessionTimeoutManager(config=config)

        # Record recent activity
        manager.record_activity("user1", "sess1")

        await manager._check_sessions()

        assert manager.is_warned("user1", "sess1") is False

    @pytest.mark.asyncio
    async def test_warning_not_repeated(self):
        """Test that warning is not sent twice."""
        warning_count = {"count": 0}

        async def on_warning(user_id, session_id, remaining):
            warning_count["count"] += 1

        config = TimeoutConfig(
            warning_minutes=0,
            timeout_minutes=10,
            check_interval_seconds=1,
        )
        manager = SessionTimeoutManager(config=config, on_warning=on_warning)

        # Record old activity
        manager._activity["user1:sess1"] = datetime.now(timezone.utc) - timedelta(
            minutes=5
        )

        # Check twice
        await manager._check_sessions()
        await manager._check_sessions()

        # Warning should only be sent once
        assert warning_count["count"] == 1


class TestSessionCounts:
    """Tests for session counting methods."""

    def test_get_active_session_count(self):
        """Test active session count."""
        manager = SessionTimeoutManager()

        assert manager.get_active_session_count() == 0

        manager.record_activity("user1", "sess1")
        manager.record_activity("user1", "sess2")
        manager.record_activity("user2", "sess3")

        assert manager.get_active_session_count() == 3

    def test_get_warned_session_count(self):
        """Test warned session count."""
        manager = SessionTimeoutManager()

        assert manager.get_warned_session_count() == 0

        manager._warned.add("user1:sess1")
        manager._warned.add("user1:sess2")

        assert manager.get_warned_session_count() == 2


class TestConfigureTimeoutManager:
    """Tests for configure_timeout_manager factory."""

    @pytest.mark.asyncio
    async def test_creates_manager_with_callbacks(self):
        await reset_timeout_manager()
        try:
            async def on_warning(user_id: str, session_id: str, remaining: int) -> None:
                pass

            async def on_timeout(user_id: str, session_id: str) -> None:
                pass

            mgr = configure_timeout_manager(
                on_warning=on_warning, on_timeout=on_timeout
            )

            assert mgr._on_warning is on_warning
            assert mgr._on_timeout is on_timeout
        finally:
            await reset_timeout_manager()

    @pytest.mark.asyncio
    async def test_creates_manager_with_custom_config(self):
        await reset_timeout_manager()
        try:
            config = TimeoutConfig(warning_minutes=5, timeout_minutes=10)
            mgr = configure_timeout_manager(config=config)

            assert mgr.config.warning_minutes == 5
            assert mgr.config.timeout_minutes == 10
        finally:
            await reset_timeout_manager()

    @pytest.mark.asyncio
    async def test_returns_existing_instance_on_second_call(self):
        await reset_timeout_manager()
        try:
            mgr1 = configure_timeout_manager()
            mgr2 = configure_timeout_manager()

            assert mgr1 is mgr2
        finally:
            await reset_timeout_manager()
