"""Tests for session recovery service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.adk.session.recovery import (
    RecoverableSession,
    SessionRecoveryResult,
    SessionRecoveryService,
)


class TestRecoverableSession:
    """Tests for RecoverableSession dataclass."""

    def test_create_recoverable_session(self):
        """Test creating a recoverable session."""
        now = datetime.now(timezone.utc)
        session = RecoverableSession(
            session_id="sess123",
            conversation_name="My Chat",
            created_at=now,
            last_updated=now,
            message_count=5,
            preview="Hello, how can I...",
        )

        assert session.session_id == "sess123"
        assert session.conversation_name == "My Chat"
        assert session.message_count == 5
        assert session.preview == "Hello, how can I..."


class TestSessionRecoveryResult:
    """Tests for SessionRecoveryResult dataclass."""

    def test_success_result(self):
        """Test creating a success result."""
        result = SessionRecoveryResult(
            success=True,
            session_id="sess123",
            state={"account_id": "acct1"},
            conversation_history=[{"role": "user", "content": "Hello"}],
        )

        assert result.success is True
        assert result.error is None

    def test_failure_result(self):
        """Test creating a failure result."""
        result = SessionRecoveryResult(
            success=False,
            session_id="sess123",
            state=None,
            conversation_history=None,
            error="Session not found",
        )

        assert result.success is False
        assert result.error == "Session not found"


class TestSessionRecoveryService:
    """Tests for SessionRecoveryService."""

    @pytest.fixture
    def mock_session_service(self):
        """Create a mock session service."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_session_service):
        """Create recovery service with mocks."""
        return SessionRecoveryService(mock_session_service)

    def _create_mock_session(
        self,
        session_id: str,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        state: dict | None = None,
        events: list | None = None,
    ):
        """Create a mock session object."""
        now = datetime.now(timezone.utc)
        session = MagicMock()
        session.id = session_id
        session.create_time = created_at or now
        session.update_time = updated_at or created_at or now
        session.state = state or {"account_id": "acct1"}
        session.events = events or []
        return session

    @pytest.mark.asyncio
    async def test_list_recoverable_sessions(self, service, mock_session_service):
        """Test listing recoverable sessions."""
        now = datetime.now(timezone.utc)
        sessions = [
            self._create_mock_session(
                "sess1",
                created_at=now - timedelta(days=1),
                state={"account_id": "acct1", "conversation_name": "Chat 1"},
            ),
            self._create_mock_session(
                "sess2",
                created_at=now - timedelta(hours=2),
                state={"account_id": "acct1"},
            ),
        ]

        mock_response = MagicMock()
        mock_response.sessions = sessions
        mock_session_service.list_sessions = AsyncMock(return_value=mock_response)

        recoverable = await service.list_recoverable_sessions("user1")

        assert len(recoverable) == 2
        # Should be sorted by last_updated (newest first)
        assert recoverable[0].session_id == "sess2"
        assert recoverable[1].session_id == "sess1"

    @pytest.mark.asyncio
    async def test_list_excludes_old_sessions(self, service, mock_session_service):
        """Test that sessions older than 7 days are excluded."""
        now = datetime.now(timezone.utc)
        sessions = [
            self._create_mock_session(
                "old_sess",
                created_at=now - timedelta(days=10),
                updated_at=now - timedelta(days=10),
            ),
            self._create_mock_session(
                "recent_sess",
                created_at=now - timedelta(days=1),
            ),
        ]

        mock_response = MagicMock()
        mock_response.sessions = sessions
        mock_session_service.list_sessions = AsyncMock(return_value=mock_response)

        recoverable = await service.list_recoverable_sessions("user1")

        assert len(recoverable) == 1
        assert recoverable[0].session_id == "recent_sess"

    @pytest.mark.asyncio
    async def test_list_handles_error(self, service, mock_session_service):
        """Test that listing handles errors gracefully."""
        mock_session_service.list_sessions = AsyncMock(
            side_effect=Exception("API Error")
        )

        recoverable = await service.list_recoverable_sessions("user1")

        assert recoverable == []

    @pytest.mark.asyncio
    async def test_recover_session_success(self, service, mock_session_service):
        """Test successful session recovery."""
        now = datetime.now(timezone.utc)
        mock_event = MagicMock()
        mock_event.role = "user"
        mock_event.content = "Hello"
        mock_event.timestamp = now

        session = self._create_mock_session(
            "sess1",
            state={"account_id": "acct1", "conversation_name": "My Chat"},
            events=[mock_event],
        )

        mock_session_service.get_session = AsyncMock(return_value=session)

        result = await service.recover_session("user1", "sess1")

        assert result.success is True
        assert result.session_id == "sess1"
        assert result.state["account_id"] == "acct1"
        assert len(result.conversation_history) == 1
        assert result.conversation_history[0]["role"] == "user"
        assert result.conversation_history[0]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_recover_session_not_found(self, service, mock_session_service):
        """Test recovery when session not found."""
        mock_session_service.get_session = AsyncMock(return_value=None)

        result = await service.recover_session("user1", "nonexistent")

        assert result.success is False
        assert result.error == "Session not found"

    @pytest.mark.asyncio
    async def test_recover_session_repairs_incomplete_state(
        self, service, mock_session_service
    ):
        """Test that incomplete state is repaired."""
        # Create a session with genuinely empty state (no account_id)
        session = MagicMock()
        session.id = "sess1"
        session.create_time = datetime.now(timezone.utc)
        session.update_time = session.create_time
        session.state = {}  # Truly empty state
        session.events = []

        mock_session_service.get_session = AsyncMock(return_value=session)

        result = await service.recover_session("user1", "sess1")

        assert result.success is True
        assert result.state is not None
        # account_id should be None (needs selection) but present
        assert "account_id" in result.state
        assert "accessible_accounts" in result.state

    @pytest.mark.asyncio
    async def test_recover_session_handles_error(self, service, mock_session_service):
        """Test recovery handles errors gracefully."""
        mock_session_service.get_session = AsyncMock(
            side_effect=Exception("API Error")
        )

        result = await service.recover_session("user1", "sess1")

        assert result.success is False
        assert "API Error" in result.error


class TestSessionRecoveryServiceValidation:
    """Tests for state validation."""

    @pytest.fixture
    def service(self):
        return SessionRecoveryService(AsyncMock())

    def test_validate_state_with_account_id(self, service):
        """Test validation passes with account_id."""
        assert service._validate_state({"account_id": "acct1"}) is True

    def test_validate_state_without_account_id(self, service):
        """Test validation fails without account_id."""
        assert service._validate_state({}) is False
        assert service._validate_state({"other": "data"}) is False

    def test_repair_state_adds_defaults(self, service):
        """Test repair adds default values."""
        repaired = service._repair_state({})

        assert "account_id" in repaired
        assert repaired["account_id"] is None
        assert "accessible_accounts" in repaired
        assert repaired["accessible_accounts"] == []

    def test_repair_state_preserves_existing(self, service):
        """Test repair preserves existing values."""
        original = {"account_id": "acct1", "custom": "value"}
        repaired = service._repair_state(original)

        assert repaired["account_id"] == "acct1"
        assert repaired["custom"] == "value"
