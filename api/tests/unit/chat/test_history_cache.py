"""Unit tests for Redis caching of conversation history.

A revisit / session-status toggle should serve formatted history from Redis
rather than re-hitting Vertex; a new turn or a delete must invalidate it.
All Vertex / Redis interactions are mocked.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.kene_api.cache import session_history_key
from src.kene_api.routers import chat as chat_module
from src.kene_api.routers.chat import (
    AgentEngineClient,
    _invalidate_conversation_history_cache,
)


def _assistant_event(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=SimpleNamespace(role="model", parts=[SimpleNamespace(text=text)]),
        author="ken_e",
        timestamp=1780054954.0,
    )


def _client() -> AgentEngineClient:
    client = AgentEngineClient()
    client._session_service = AsyncMock()
    client._session_service.get_session = AsyncMock(
        return_value=SimpleNamespace(events=[_assistant_event("answer")])
    )
    return client


class _FakeRedis:
    """In-memory stand-in for the JSON Redis helpers used by history caching."""

    def __init__(self) -> None:
        self.store: dict[str, Any] = {}

    def is_available(self) -> bool:
        return True

    def get_json(self, key: str) -> Any | None:
        return self.store.get(key)

    def set_json(self, key: str, value: Any, ttl: int | None = None) -> bool:
        self.store[key] = value
        return True

    def delete(self, key: str) -> bool:
        return self.store.pop(key, None) is not None


@pytest.fixture
def _no_side_table():
    """Charts off — isolate cache behaviour from the GCS/Firestore enrichment."""
    svc = MagicMock()
    svc.find_session_for_user.return_value = None
    with patch.object(
        chat_module, "get_chat_side_table_service", return_value=svc
    ):
        yield


class TestHistoryCache:
    @pytest.mark.asyncio
    async def test_miss_then_hit_skips_second_vertex_call(self, _no_side_table) -> None:
        redis = _FakeRedis()
        client = _client()
        with patch.object(chat_module, "get_redis_service", return_value=redis):
            first = await client.get_conversation_history("u1", "s1")
            second = await client.get_conversation_history("u1", "s1")

        assert first == second
        # Vertex hit once (miss); second served from cache.
        assert client._session_service.get_session.await_count == 1
        assert session_history_key("u1", "s1") in redis.store

    @pytest.mark.asyncio
    async def test_invalidation_forces_rebuild(self, _no_side_table) -> None:
        redis = _FakeRedis()
        client = _client()
        with patch.object(chat_module, "get_redis_service", return_value=redis):
            await client.get_conversation_history("u1", "s1")
            _invalidate_conversation_history_cache("u1", "s1")
            assert session_history_key("u1", "s1") not in redis.store
            await client.get_conversation_history("u1", "s1")

        assert client._session_service.get_session.await_count == 2

    @pytest.mark.asyncio
    async def test_rewarm_invalidates_then_repopulates(self, _no_side_table) -> None:
        """Re-warm drops the stale entry synchronously, then a background task
        re-fetches + re-caches so the next load is a hit (not a ~2.4s miss)."""
        import asyncio

        redis = _FakeRedis()
        redis.store[session_history_key("u1", "s1")] = {"events": [], "stale": True}
        client = _client()
        with (
            patch.object(chat_module, "get_redis_service", return_value=redis),
            patch.object(chat_module, "agent_client", client),
        ):
            chat_module._rewarm_conversation_history_cache("u1", "s1")
            # Invalidation is synchronous — a load during the re-warm window
            # gets a fresh miss, never the stale snapshot.
            assert session_history_key("u1", "s1") not in redis.store
            # Drain the background re-warm task.
            for task in list(chat_module._background_tasks):
                await task

        # Re-warm repopulated the cache with fresh (non-stale) history.
        cached = redis.store.get(session_history_key("u1", "s1"))
        assert cached is not None and "stale" not in cached
        assert client._session_service.get_session.await_count == 1

    @pytest.mark.asyncio
    async def test_cache_is_user_scoped_no_cross_user_disclosure(
        self, _no_side_table
    ) -> None:
        """A cached history for user A must NOT be served to user B for the same
        session_id. The cache key includes user_id; the history endpoint's only
        ownership gate is the user-scoped get_session this cache short-circuits,
        so a session-only key would have leaked A's conversation to B (IDOR)."""
        redis = _FakeRedis()
        # User A owns s1 — their get_session returns real content.
        client_a = _client()
        # User B does NOT own s1 — Vertex returns None for B (per-user scoping).
        client_b = AgentEngineClient()
        client_b._session_service = AsyncMock()
        client_b._session_service.get_session = AsyncMock(return_value=None)

        with patch.object(chat_module, "get_redis_service", return_value=redis):
            a = await client_a.get_conversation_history("user_a", "s1")
            b = await client_b.get_conversation_history("user_b", "s1")

        # A sees their own (non-empty) history, cached under their own key.
        assert a is not None and a["events"]
        assert session_history_key("user_a", "s1") in redis.store
        # B gets an empty history (their own miss → user-scoped Vertex None),
        # NEVER A's cached content.
        assert b == {"session_id": "s1", "events": []}

    @pytest.mark.asyncio
    async def test_redis_unavailable_is_transparent(self, _no_side_table) -> None:
        unavailable = MagicMock()
        unavailable.is_available.return_value = False
        client = _client()
        with patch.object(
            chat_module, "get_redis_service", return_value=unavailable
        ):
            result = await client.get_conversation_history("u1", "s1")

        assert result["events"][0]["content"]["parts"] == [{"text": "answer"}]
        unavailable.get_json.assert_not_called()
        unavailable.set_json.assert_not_called()
