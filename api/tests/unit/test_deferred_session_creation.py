"""Unit tests for deferred session creation and pending session resolution.

Tests cover:
1. resolve_pending_session — normal resolution, concurrent access safety, error propagation
2. get_or_create_session — pending_* ID detection and resolution
3. delete_conversation — pending session cancellation
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.kene_api.routers.chat import AgentEngineClient


class TestResolvePendingSession:
    """Tests for AgentEngineClient.resolve_pending_session."""

    @pytest.mark.asyncio
    async def test_resolves_pending_id_to_real_session_id(self):
        """A pending session ID is replaced with the real Vertex AI session ID
        once the background task completes."""
        client = AgentEngineClient()
        user_id = "user_1"
        pending_id = "pending_abc123"
        real_id = "projects/p/locations/l/sessions/real_xyz"

        # Simulate background task that resolves to real session ID
        async def return_real_id():
            return real_id

        client._pending_sessions[pending_id] = asyncio.create_task(return_real_id())

        # Pre-populate _user_sessions with the pending entry
        client._user_sessions[f"{user_id}:{pending_id}"] = {
            "session_id": pending_id,
            "user_id": user_id,
            "conversation_name": "Test",
        }

        result = await client.resolve_pending_session(user_id, pending_id)

        assert result == real_id
        assert pending_id not in client._pending_sessions
        assert f"{user_id}:{pending_id}" not in client._user_sessions
        assert f"{user_id}:{real_id}" in client._user_sessions
        assert client._user_sessions[f"{user_id}:{real_id}"]["session_id"] == real_id

    @pytest.mark.asyncio
    async def test_returns_pending_id_unchanged_when_no_task_exists(self):
        """If the pending_id has no associated task (already resolved or unknown),
        return it as-is without error."""
        client = AgentEngineClient()

        result = await client.resolve_pending_session("user_1", "pending_unknown")

        assert result == "pending_unknown"

    @pytest.mark.asyncio
    async def test_concurrent_resolution_second_caller_gets_id_directly(self):
        """When two callers try to resolve the same pending_id concurrently,
        the first caller claims the task via pop(), and the second gets the
        pending_id back unchanged (no KeyError)."""
        client = AgentEngineClient()
        user_id = "user_1"
        pending_id = "pending_race"
        real_id = "real_session_after_race"

        async def slow_create():
            await asyncio.sleep(0.05)
            return real_id

        client._pending_sessions[pending_id] = asyncio.create_task(slow_create())
        client._user_sessions[f"{user_id}:{pending_id}"] = {
            "session_id": pending_id,
            "user_id": user_id,
            "conversation_name": "Race Test",
        }

        # Launch two concurrent resolvers
        results = await asyncio.gather(
            client.resolve_pending_session(user_id, pending_id),
            client.resolve_pending_session(user_id, pending_id),
        )

        # One should get the real ID, the other should get pending_id back
        assert real_id in results
        assert pending_id in results
        assert pending_id not in client._pending_sessions

    @pytest.mark.asyncio
    async def test_propagates_background_task_errors(self):
        """If the background create_session task fails, the error propagates
        to the caller and the task is cleaned up."""
        client = AgentEngineClient()
        pending_id = "pending_fail"

        async def failing_create():
            raise RuntimeError("Vertex AI unavailable")

        task = asyncio.create_task(failing_create())
        # Let the task start and fail
        await asyncio.sleep(0.01)
        client._pending_sessions[pending_id] = task

        with pytest.raises(RuntimeError, match="Vertex AI unavailable"):
            await client.resolve_pending_session("user_1", pending_id)

        assert pending_id not in client._pending_sessions


class TestGetOrCreateSessionPendingResolution:
    """Tests for pending_* detection in get_or_create_session."""

    @pytest.mark.asyncio
    async def test_pending_session_id_triggers_resolution(self):
        """get_or_create_session detects pending_* IDs and calls
        resolve_pending_session before proceeding."""
        client = AgentEngineClient()
        user_id = "user_1"
        pending_id = "pending_test123"
        real_id = "real_adk_session"

        with patch.object(
            client,
            "resolve_pending_session",
            new=AsyncMock(return_value=real_id),
        ) as mock_resolve:
            # Pre-populate cache so get_or_create_session returns immediately
            client._user_sessions[f"{user_id}:{real_id}"] = {
                "session_id": real_id,
                "user_id": user_id,
                "conversation_name": "Test",
                "created_at": "2025-01-01T00:00:00Z",
                "last_updated": "2025-01-01T00:00:00Z",
                "message_count": 0,
            }

            result = await client.get_or_create_session(
                user_id=user_id,
                session_id=pending_id,
            )

            mock_resolve.assert_called_once_with(user_id, pending_id)
            assert result == real_id

    @pytest.mark.asyncio
    async def test_non_pending_session_id_skips_resolution(self):
        """Normal session IDs (not starting with pending_) do not trigger
        resolve_pending_session."""
        client = AgentEngineClient()
        user_id = "user_1"
        session_id = "chat_normal_123"

        client._user_sessions[f"{user_id}:{session_id}"] = {
            "session_id": session_id,
            "user_id": user_id,
            "conversation_name": "Test",
            "created_at": "2025-01-01T00:00:00Z",
            "last_updated": "2025-01-01T00:00:00Z",
            "message_count": 0,
        }

        with patch.object(
            client,
            "resolve_pending_session",
            new=AsyncMock(),
        ) as mock_resolve:
            result = await client.get_or_create_session(
                user_id=user_id,
                session_id=session_id,
            )

            mock_resolve.assert_not_called()
            assert result == session_id


class TestDeletePendingConversation:
    """Tests for deleting conversations that are still pending creation."""

    @pytest.mark.asyncio
    async def test_delete_cancels_pending_task(self):
        """Deleting a conversation with a pending session cancels the
        background creation task instead of calling ADK delete."""
        client = AgentEngineClient()
        user_id = "user_1"
        pending_id = "pending_to_delete"

        async def slow_create():
            await asyncio.sleep(10)
            return "never_used"

        task = asyncio.create_task(slow_create())
        client._pending_sessions[pending_id] = task
        client._user_sessions[f"{user_id}:{pending_id}"] = {
            "session_id": pending_id,
            "user_id": user_id,
            "conversation_name": "Will be deleted",
            "created_at": "2025-01-01T00:00:00Z",
            "last_updated": "2025-01-01T00:00:00Z",
            "message_count": 0,
        }

        with patch("src.kene_api.routers.chat.get_redis_service") as mock_redis:
            mock_redis_instance = MagicMock()
            mock_redis_instance.is_available.return_value = False
            mock_redis.return_value = mock_redis_instance

            result = await client.delete_conversation(user_id, pending_id)

        assert result is True
        # Task is in cancelling state; yield to the event loop so it finalises
        await asyncio.sleep(0)
        assert task.cancelled()
        assert pending_id not in client._pending_sessions
        assert f"{user_id}:{pending_id}" not in client._user_sessions
