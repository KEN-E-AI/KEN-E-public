"""Unit tests for author-tagging in stream_chat_completion 3-tuple yields.

Verifies that every tuple yielded by AgentEngineClient.stream_chat_completion
is a 3-tuple (channel, text, author) and that the author field is extracted
from the chunk dict when present, defaulting to "model" otherwise.

References: AH-124 SSE author-tagging for fan-out turns.
"""
from __future__ import annotations

import os
import sys
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from kene_api.routers.chat import AgentEngineClient, ChatMessage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client() -> AgentEngineClient:
    """Return an AgentEngineClient with a stubbed agent_engine."""
    client = AgentEngineClient.__new__(AgentEngineClient)
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
class TestStreamChatCompletionAuthor:
    async def test_dict_chunk_with_author_field(self) -> None:
        """A dict chunk with author="specialist_a" propagates to the 3-tuple."""
        client = _make_client()
        user_context = _fake_user_context()

        chunk = {
            "content": {"parts": [{"text": "hi"}]},
            "author": "specialist_a",
        }

        with patch.object(
            client,
            "get_or_create_session",
            new=AsyncMock(return_value="sess_1"),
        ):
            client._agent_engine.stream_query = MagicMock(return_value=iter([chunk]))

            messages = [ChatMessage(role="user", content="hello")]
            tuples = await _collect(
                client.stream_chat_completion(
                    messages=messages,
                    user_context=user_context,
                    session_id="sess_1",
                    account_id="acct_1",
                )
            )

        text_tuples = [t for t in tuples if t[0] == "text"]
        assert len(text_tuples) == 1
        assert text_tuples[0] == ("text", "hi", "specialist_a")

    async def test_dict_chunk_without_author_defaults_to_model(self) -> None:
        """A dict chunk without an author field defaults author to "model"."""
        client = _make_client()
        user_context = _fake_user_context()

        chunk = {"content": {"parts": [{"text": "hi"}]}}

        with patch.object(
            client,
            "get_or_create_session",
            new=AsyncMock(return_value="sess_2"),
        ):
            client._agent_engine.stream_query = MagicMock(return_value=iter([chunk]))

            messages = [ChatMessage(role="user", content="hello")]
            tuples = await _collect(
                client.stream_chat_completion(
                    messages=messages,
                    user_context=user_context,
                    session_id="sess_2",
                    account_id="acct_1",
                )
            )

        text_tuples = [t for t in tuples if t[0] == "text"]
        assert len(text_tuples) == 1
        assert text_tuples[0] == ("text", "hi", "model")

    async def test_string_chunk_author_defaults_to_model(self) -> None:
        """A plain string chunk always uses author="model"."""
        client = _make_client()
        user_context = _fake_user_context()

        with patch.object(
            client,
            "get_or_create_session",
            new=AsyncMock(return_value="sess_3"),
        ):
            client._agent_engine.stream_query = MagicMock(
                return_value=iter(["hello"])
            )

            messages = [ChatMessage(role="user", content="hello")]
            tuples = await _collect(
                client.stream_chat_completion(
                    messages=messages,
                    user_context=user_context,
                    session_id="sess_3",
                    account_id="acct_1",
                )
            )

        text_tuples = [t for t in tuples if t[0] == "text"]
        assert len(text_tuples) == 1
        assert text_tuples[0] == ("text", "hello", "model")

    async def test_reasoning_chunk_with_author(self) -> None:
        """A thought part in a dict chunk with author propagates to ("reasoning", ..., author)."""
        client = _make_client()
        user_context = _fake_user_context()

        chunk = {
            "content": {"parts": [{"text": "thinking...", "thought": True}]},
            "author": "specialist_a",
        }

        with patch.object(
            client,
            "get_or_create_session",
            new=AsyncMock(return_value="sess_4"),
        ):
            client._agent_engine.stream_query = MagicMock(return_value=iter([chunk]))

            messages = [ChatMessage(role="user", content="hello")]
            tuples = await _collect(
                client.stream_chat_completion(
                    messages=messages,
                    user_context=user_context,
                    session_id="sess_4",
                    account_id="acct_1",
                )
            )

        reasoning_tuples = [t for t in tuples if t[0] == "reasoning"]
        assert len(reasoning_tuples) == 1
        assert reasoning_tuples[0] == ("reasoning", "thinking...", "specialist_a")

    async def test_session_tuple_author_is_model(self) -> None:
        """The session-resolution tuple always uses author="model"."""
        client = _make_client()
        user_context = _fake_user_context()

        with patch.object(
            client,
            "get_or_create_session",
            new=AsyncMock(return_value="real_session_77"),
        ):
            client._agent_engine.stream_query = MagicMock(return_value=iter([]))

            messages = [ChatMessage(role="user", content="hi")]
            tuples = await _collect(
                client.stream_chat_completion(
                    messages=messages,
                    user_context=user_context,
                    session_id="pending_abc",
                    account_id="acct_1",
                )
            )

        session_tuples = [t for t in tuples if t[0] == "session"]
        assert len(session_tuples) == 1
        assert session_tuples[0] == ("session", "real_session_77", "model")

    async def test_all_tuples_are_3_tuples(self) -> None:
        """Every tuple in any stream output must have exactly 3 elements."""
        client = _make_client()
        user_context = _fake_user_context()

        chunks = [
            {"content": {"parts": [{"text": "hello", "thought": True}]}, "author": "spec_x"},
            {"content": {"parts": [{"text": "world"}]}, "author": "spec_y"},
            {"content": {"parts": [{"text": "done"}]}},
        ]

        with patch.object(
            client,
            "get_or_create_session",
            new=AsyncMock(return_value="real_id"),
        ):
            client._agent_engine.stream_query = MagicMock(return_value=iter(chunks))

            messages = [ChatMessage(role="user", content="hi")]
            tuples = await _collect(
                client.stream_chat_completion(
                    messages=messages,
                    user_context=user_context,
                    session_id="pending_xyz",
                    account_id="acct_1",
                )
            )

        for t in tuples:
            assert len(t) == 3, f"Expected 3-tuple, got {t!r}"
