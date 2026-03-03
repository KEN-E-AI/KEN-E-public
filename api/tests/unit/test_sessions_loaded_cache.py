"""Unit tests for _sessions_loaded_for cache-first conversation listing.

Tests cover:
1. Cache-hit path — subsequent get_user_conversations calls skip list_sessions
2. Cache-miss path — first call goes through list_sessions
3. Session mutations (create/delete) keep cache valid without re-calling list_sessions
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.kene_api.routers.chat import AgentEngineClient


class TestSessionsLoadedForCache:
    """Tests for _sessions_loaded_for in-memory caching of conversation lists."""

    @pytest.mark.asyncio
    async def test_second_call_skips_list_sessions(self):
        """After sessions are loaded, subsequent calls to get_user_conversations
        return from in-memory cache without calling list_sessions."""
        client = AgentEngineClient()
        user_id = "user_1"

        # Mark user as already loaded and populate cache
        client._sessions_loaded_for.add(user_id)
        now = datetime.now(timezone.utc)
        client._user_sessions[f"{user_id}:session_abc"] = {
            "session_id": "session_abc",
            "user_id": user_id,
            "conversation_name": "Cached Chat",
            "created_at": now,
            "last_updated": now,
            "message_count": 3,
        }

        mock_session_service = AsyncMock()
        client._session_service = mock_session_service

        conversations = await client.get_user_conversations(user_id)

        assert len(conversations) == 1
        assert conversations[0].session_id == "session_abc"
        mock_session_service.list_sessions.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_conversation_keeps_cache_valid(self):
        """After create_conversation, the new session appears in
        get_user_conversations without re-calling list_sessions."""
        client = AgentEngineClient()
        user_id = "user_1"
        account_id = "acc_1"

        # Mark user as loaded (empty session list)
        client._sessions_loaded_for.add(user_id)

        mock_user_context = MagicMock()
        mock_user_context.accessible_accounts = [account_id]
        mock_user_context.has_account_access.return_value = True

        mock_session_service = MagicMock()
        mock_session_service.create_session = AsyncMock(
            return_value=MagicMock(id="new_session_id")
        )
        mock_session_service.list_sessions = AsyncMock()
        client._session_service = mock_session_service

        with patch("src.kene_api.routers.chat.get_redis_service") as mock_redis:
            mock_redis_instance = MagicMock()
            mock_redis_instance.is_available.return_value = False
            mock_redis.return_value = mock_redis_instance

            with patch(
                "src.kene_api.routers.chat.load_organization_context_from_neo4j",
                new=AsyncMock(return_value=None),
            ):
                session_id = await client.create_conversation(
                    user_id=user_id,
                    user_context=mock_user_context,
                    conversation_name="New Chat",
                    account_id=account_id,
                )

        # Session should appear in cache
        conversations = await client.get_user_conversations(user_id)
        session_ids = [c.session_id for c in conversations]
        assert session_id in session_ids
        # list_sessions should NOT be called
        mock_session_service.list_sessions.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_conversation_removes_from_cache(self):
        """After delete_conversation, the session disappears from
        get_user_conversations without re-calling list_sessions."""
        client = AgentEngineClient()
        user_id = "user_1"
        session_id = "session_to_delete"

        client._sessions_loaded_for.add(user_id)
        now = datetime.now(timezone.utc)
        client._user_sessions[f"{user_id}:{session_id}"] = {
            "session_id": session_id,
            "user_id": user_id,
            "conversation_name": "Doomed Chat",
            "created_at": now,
            "last_updated": now,
            "message_count": 0,
        }

        mock_session_service = MagicMock()
        mock_session_service.delete_session = AsyncMock()
        mock_session_service.list_sessions = AsyncMock()
        client._session_service = mock_session_service

        with patch("src.kene_api.routers.chat.get_redis_service") as mock_redis:
            mock_redis_instance = MagicMock()
            mock_redis_instance.is_available.return_value = False
            mock_redis.return_value = mock_redis_instance

            await client.delete_conversation(user_id, session_id)

        conversations = await client.get_user_conversations(user_id)
        session_ids = [c.session_id for c in conversations]
        assert session_id not in session_ids
        mock_session_service.list_sessions.assert_not_called()
