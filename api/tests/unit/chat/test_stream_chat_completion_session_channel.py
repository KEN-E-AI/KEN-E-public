"""Unit tests for the session-channel yield from stream_chat_completion.

Verifies that when get_or_create_session resolves a pending_ placeholder to a
different real id, stream_chat_completion yields ("session", "<real>") as the
first tuple before any text or reasoning chunks; and that when ids match (no
reconciliation) no session tuple is yielded.

References: CH-62 Implementation Plan Task 6a.
"""
from __future__ import annotations

import os
import sys
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from kene_api.routers.chat import AgentEngineClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client() -> AgentEngineClient:
    """Return an AgentEngineClient with a stubbed agent_engine."""
    client = AgentEngineClient.__new__(AgentEngineClient)
    # agent_engine is a property backed by _agent_engine; set the backing field.
    client._agent_engine = MagicMock()
    client._user_sessions = {}
    client._pending_sessions = {}
    client.agent_engine_id = None
    return client


def _fake_user_context(user_id: str = "user_1") -> MagicMock:
    ctx = MagicMock()
    ctx.user_id = user_id
    return ctx


async def _collect(
    gen: AsyncGenerator[tuple[str, str, str], None],
) -> list[tuple[str, str, str]]:
    return [t async for t in gen]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestStreamChatCompletionSessionChannel:
    async def test_session_tuple_yielded_when_pending_resolves(self):
        """When get_or_create_session returns a different id (pending_ resolved),
        the generator yields ("session", real_id) before any other tuple."""
        client = _make_client()
        user_context = _fake_user_context()

        # Patch get_or_create_session to simulate pending_ → real resolution.
        with patch.object(
            client,
            "get_or_create_session",
            new=AsyncMock(return_value="real_session_42"),
        ):
            # Patch the streaming loop so it doesn't try to hit Agent Engine.
            # After the session tuple, the generator should yield text chunks.
            async def _fake_stream(*args, **kwargs):
                # get_or_create_session is awaited inside the method; we just
                # need to not enter the streaming loop. Return immediately after
                # the async function; the test only cares about the session tuple.
                return
                yield  # make this an async generator

            # Inject the inner streaming loop by patching queue-based path:
            # Easier: capture yielded tuples by calling stream_chat_completion
            # with a real (short) conversation and a fake agent that yields nothing.
            client._agent_engine.stream_query = MagicMock(return_value=iter([]))
            client._pending_sessions = {}  # no pending tasks → get_or_create returns the mock value

            from kene_api.routers.chat import ChatMessage

            messages = [ChatMessage(role="user", content="hi")]

            tuples = await _collect(
                client.stream_chat_completion(
                    messages=messages,
                    user_context=user_context,
                    session_id="pending_abc123",  # incoming id differs from mock return
                    account_id="acct_1",
                )
            )

        # The first tuple must be ("session", "real_session_42", "model").
        assert len(tuples) >= 1
        assert tuples[0] == ("session", "real_session_42", "model"), (
            f"Expected first tuple ('session', 'real_session_42', 'model'), got {tuples[0]}"
        )

    async def test_no_session_tuple_when_ids_match(self):
        """When get_or_create_session returns the same id (no reconciliation),
        no ("session", ...) tuple is yielded."""
        client = _make_client()
        user_context = _fake_user_context()

        # Same id in and out → no reconciliation.
        with patch.object(
            client,
            "get_or_create_session",
            new=AsyncMock(return_value="existing_session_99"),
        ):
            client._agent_engine.stream_query = MagicMock(return_value=iter([]))

            from kene_api.routers.chat import ChatMessage

            messages = [ChatMessage(role="user", content="hi")]

            tuples = await _collect(
                client.stream_chat_completion(
                    messages=messages,
                    user_context=user_context,
                    session_id="existing_session_99",  # same as mock return
                    account_id="acct_1",
                )
            )

        # No session tuple in the output.
        session_tuples = [t for t in tuples if t[0] == "session"]
        assert session_tuples == [], (
            f"Expected no session tuples, got {session_tuples}"
        )

    async def test_session_tuple_emitted_when_session_id_is_none_and_real_id_differs(self):
        """When session_id=None (brand-new conversation), get_or_create_session
        returns a real id that differs from None, so a session tuple IS yielded.
        This is per the AC: "iff the resolved id differs from the incoming id."
        In practice the frontend always creates a pending_ first and never passes
        None, so this codepath is benign — but the contract is still correct."""
        client = _make_client()
        user_context = _fake_user_context()

        with patch.object(
            client,
            "get_or_create_session",
            new=AsyncMock(return_value="brand_new_99"),
        ):
            client._agent_engine.stream_query = MagicMock(return_value=iter([]))

            from kene_api.routers.chat import ChatMessage

            messages = [ChatMessage(role="user", content="hello")]

            tuples = await _collect(
                client.stream_chat_completion(
                    messages=messages,
                    user_context=user_context,
                    session_id=None,  # no incoming id — differs from "brand_new_99"
                    account_id="acct_1",
                )
            )

        # None != "brand_new_99" → session tuple is yielded (correct per AC).
        session_tuples = [t for t in tuples if t[0] == "session"]
        assert len(session_tuples) == 1
        assert session_tuples[0] == ("session", "brand_new_99", "model")

    async def test_session_tuple_is_first(self):
        """The session tuple precedes any text tuples in the output sequence."""
        client = _make_client()
        user_context = _fake_user_context()

        # The agent_engine.stream_query yields a text chunk.
        text_chunk = {"content": {"parts": [{"text": "Hello from agent."}]}}

        with patch.object(
            client,
            "get_or_create_session",
            new=AsyncMock(return_value="real_id_first"),
        ):
            client._agent_engine.stream_query = MagicMock(
                return_value=iter([text_chunk])
            )

            from kene_api.routers.chat import ChatMessage

            messages = [ChatMessage(role="user", content="hi")]

            tuples = await _collect(
                client.stream_chat_completion(
                    messages=messages,
                    user_context=user_context,
                    session_id="pending_xyz",
                    account_id="acct_1",
                )
            )

        channels = [t[0] for t in tuples]
        assert "session" in channels, f"Expected 'session' channel in {channels}"
        session_idx = channels.index("session")
        # All text/reasoning tuples must come after the session tuple.
        for i, ch in enumerate(channels):
            if ch in ("text", "reasoning"):
                assert i > session_idx, (
                    f"Text/reasoning at index {i} appeared before session at {session_idx}"
                )
