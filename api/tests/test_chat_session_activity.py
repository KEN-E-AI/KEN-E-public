"""Tests for session activity / timeout tracking.

These tests verify the SessionTimeoutManager's activity recording
and remaining time calculation without requiring the full API chain.
"""

from __future__ import annotations

import pytest

from app.adk.session.timeout import SessionTimeoutManager, TimeoutConfig


@pytest.fixture
def timeout_manager() -> SessionTimeoutManager:
    config = TimeoutConfig(
        warning_minutes=25,
        timeout_minutes=30,
        check_interval_seconds=60,
    )
    return SessionTimeoutManager(config=config)


class TestSessionActivityTracking:
    """Tests for activity recording and remaining time."""

    def test_record_activity_and_get_remaining(
        self, timeout_manager: SessionTimeoutManager
    ):
        timeout_manager.record_activity("user1", "sess-001")
        remaining = timeout_manager.get_remaining_time("user1", "sess-001")

        assert remaining is not None
        assert 1790 <= remaining <= 1800  # ~30 minutes

    def test_activity_resets_warning(self, timeout_manager: SessionTimeoutManager):
        timeout_manager.record_activity("user1", "sess-001")
        timeout_manager._warned.add("user1:sess-001")
        assert timeout_manager.is_warned("user1", "sess-001") is True

        timeout_manager.record_activity("user1", "sess-001")
        assert timeout_manager.is_warned("user1", "sess-001") is False

    def test_remaining_time_none_for_untracked(
        self, timeout_manager: SessionTimeoutManager
    ):
        remaining = timeout_manager.get_remaining_time("user1", "nonexistent")
        assert remaining is None

    def test_multiple_sessions_tracked_independently(
        self, timeout_manager: SessionTimeoutManager
    ):
        timeout_manager.record_activity("user1", "sess-001")
        timeout_manager.record_activity("user1", "sess-002")

        assert timeout_manager.get_active_session_count() == 2

        remaining1 = timeout_manager.get_remaining_time("user1", "sess-001")
        remaining2 = timeout_manager.get_remaining_time("user1", "sess-002")

        assert remaining1 is not None
        assert remaining2 is not None
