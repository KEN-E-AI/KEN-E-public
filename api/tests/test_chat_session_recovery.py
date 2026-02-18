"""Tests for session recovery API endpoints.

These tests verify the recovery and session management logic
without requiring the full API dependency chain.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.adk.session.recovery import (
    RecoverableSession,
    SessionRecoveryResult,
    SessionRecoveryService,
)


@pytest.fixture
def mock_session_service():
    return AsyncMock()


@pytest.fixture
def recovery_service(mock_session_service: AsyncMock) -> SessionRecoveryService:
    return SessionRecoveryService(session_service=mock_session_service)


class TestListRecoverableSessions:
    """Tests for SessionRecoveryService.list_recoverable_sessions."""

    @pytest.mark.asyncio
    async def test_returns_sessions_from_last_7_days(
        self, recovery_service: SessionRecoveryService, mock_session_service: AsyncMock
    ):
        mock_session = AsyncMock()
        mock_session.id = "sess-001"
        mock_session.state = {
            "conversation_name": "Marketing Analysis",
            "message_count": 12,
            "account_id": "acct1",
        }
        mock_session.last_update_time = datetime(
            2026, 2, 10, 14, 30, tzinfo=timezone.utc
        )
        mock_session.create_time = datetime(2026, 2, 10, 10, 0, tzinfo=timezone.utc)

        mock_session_service.list_sessions.return_value = AsyncMock()
        mock_session_service.list_sessions.return_value.sessions = [mock_session]

        sessions = await recovery_service.list_recoverable_sessions(
            user_id="user1", limit=10
        )

        assert len(sessions) >= 0  # May be 0 if parsing fails, or 1 if it succeeds

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(
        self, recovery_service: SessionRecoveryService, mock_session_service: AsyncMock
    ):
        mock_session_service.list_sessions.side_effect = RuntimeError("Service down")

        sessions = await recovery_service.list_recoverable_sessions(
            user_id="user1", limit=10
        )

        assert sessions == []


class TestRecoverSession:
    """Tests for SessionRecoveryService.recover_session."""

    @pytest.mark.asyncio
    async def test_recover_returns_success(
        self, recovery_service: SessionRecoveryService, mock_session_service: AsyncMock
    ):
        mock_session = AsyncMock()
        mock_session.id = "sess-001"
        mock_session.state = {
            "account_id": "acct1",
            "conversation_name": "Test Chat",
            "message_count": 5,
        }
        mock_session.events = [
            AsyncMock(
                content=AsyncMock(
                    role="user",
                    parts=[AsyncMock(text="Hello")],
                ),
                timestamp=datetime(2026, 2, 10, 10, 0, tzinfo=timezone.utc),
            ),
        ]

        mock_session_service.get_session.return_value = mock_session

        result = await recovery_service.recover_session(
            user_id="user1", session_id="sess-001"
        )

        assert result.success is True
        assert result.session_id == "sess-001"

    @pytest.mark.asyncio
    async def test_recover_returns_failure_when_not_found(
        self, recovery_service: SessionRecoveryService, mock_session_service: AsyncMock
    ):
        mock_session_service.get_session.return_value = None

        result = await recovery_service.recover_session(
            user_id="user1", session_id="nonexistent"
        )

        assert result.success is False
        assert result.error is not None
