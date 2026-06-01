"""Regression tests for CH-63: reasoning (`thought=True`) parts must never be
rebuilt into chat history content.

A Gemini "thinking" turn stores two parts on the assistant event — the
reasoning (`thought=True`) first, then the answer. The streaming path already
filters thought parts (test_stream_event_filtering covers the contentless case;
chat.py routes thoughts to the "reasoning" channel). The history path
(`get_conversation_history`) did not, so a reloaded turn surfaced the reasoning
as the message content and dropped the answer (the frontend renders parts[0]).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.kene_api.routers import chat as chat_module
from src.kene_api.routers.chat import AgentEngineClient

_ANSWER = "I don't have access to a real-time system clock."
_THOUGHT = "**My Thought Process** — none of my specialists handle the time…"


def _part(text: Any, thought: Any = None) -> SimpleNamespace:
    return SimpleNamespace(text=text, thought=thought)


def _assistant_event(parts: list[SimpleNamespace]) -> SimpleNamespace:
    return SimpleNamespace(
        content=SimpleNamespace(role="model", parts=parts),
        author="ken_e",
        timestamp=1780054954.0,
    )


def _client_with_events(parts: list[SimpleNamespace]) -> AgentEngineClient:
    client = AgentEngineClient()
    client._session_service = AsyncMock()
    session = SimpleNamespace(events=[_assistant_event(parts)])
    client._session_service.get_session = AsyncMock(return_value=session)
    return client


def _history_parts(result: dict[str, Any]) -> list[dict[str, Any]]:
    return result["events"][0]["content"]["parts"]


@pytest.fixture(autouse=True)
def _no_redis():
    fake = MagicMock()
    fake.is_available.return_value = False
    with patch.object(chat_module, "get_redis_service", return_value=fake):
        yield


class TestHistoryExcludesThoughtParts:
    @pytest.mark.asyncio
    async def test_thought_part_is_excluded_answer_survives(self) -> None:
        """A [thought, answer] turn rebuilds to the answer only (CH-63)."""
        client = _client_with_events(
            [_part(_THOUGHT, thought=True), _part(_ANSWER)]
        )
        result = await client.get_conversation_history("u1", "s1")
        assert _history_parts(result) == [{"text": _ANSWER}]

    @pytest.mark.asyncio
    async def test_plain_turn_is_unchanged(self) -> None:
        """A turn with no reasoning is unaffected (regression guard)."""
        client = _client_with_events([_part(_ANSWER)])
        result = await client.get_conversation_history("u1", "s1")
        assert _history_parts(result) == [{"text": _ANSWER}]

    @pytest.mark.asyncio
    async def test_empty_text_parts_are_excluded(self) -> None:
        """Non-text parts (e.g. a function call with text=None) yield nothing."""
        client = _client_with_events([_part(None), _part(_ANSWER)])
        result = await client.get_conversation_history("u1", "s1")
        assert _history_parts(result) == [{"text": _ANSWER}]
