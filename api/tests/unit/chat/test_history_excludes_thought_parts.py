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
    # Stub the side-table so chart enrichment short-circuits offline (no session
    # row → no chart lookup); keeps these text-only history tests pure and fast.
    side_table = MagicMock()
    side_table.find_session_for_user.return_value = None
    with (
        patch.object(chat_module, "get_redis_service", return_value=fake),
        patch.object(
            chat_module, "get_chat_side_table_service", return_value=side_table
        ),
    ):
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

    @pytest.mark.asyncio
    async def test_reasoning_captured_into_reasoning_field(self) -> None:
        """A [thought, answer] turn keeps the answer in content AND surfaces the
        thought in a separate `reasoning` field so the ThinkingBlock re-renders
        on reload (CH-63 kept thoughts out of content; we now re-serve them)."""
        client = _client_with_events(
            [_part(_THOUGHT, thought=True), _part(_ANSWER)]
        )
        result = await client.get_conversation_history("u1", "s1")
        event = result["events"][0]
        assert event["content"]["parts"] == [{"text": _ANSWER}]
        assert event["reasoning"] == {
            "thoughts": [_THOUGHT],
            "durationSeconds": 0,
        }

    @pytest.mark.asyncio
    async def test_reasoning_from_thought_only_event_attaches_to_next_answer(
        self,
    ) -> None:
        """Thoughts emitted in a preceding thought-only event attach to the next
        answer event (reasoning accumulates across events within a turn)."""
        client = AgentEngineClient()
        client._session_service = AsyncMock()
        thought_only = SimpleNamespace(
            content=SimpleNamespace(role="model", parts=[_part(_THOUGHT, thought=True)]),
            author="ken_e",
            timestamp=1780054954.0,
        )
        session = SimpleNamespace(
            events=[thought_only, _assistant_event([_part(_ANSWER)])]
        )
        client._session_service.get_session = AsyncMock(return_value=session)

        result = await client.get_conversation_history("u1", "s1")

        # The thought-only event produced no content → dropped; its reasoning
        # rode forward onto the single answer event.
        assert len(result["events"]) == 1
        assert result["events"][0]["content"]["parts"] == [{"text": _ANSWER}]
        assert result["events"][0]["reasoning"]["thoughts"] == [_THOUGHT]

    @pytest.mark.asyncio
    async def test_reasoning_duration_computed_from_timestamp_gap(self) -> None:
        """When thoughts precede the answer in a separate event, the thinking
        duration is recovered from the gap between event timestamps."""
        client = AgentEngineClient()
        client._session_service = AsyncMock()
        thought_only = SimpleNamespace(
            content=SimpleNamespace(role="model", parts=[_part(_THOUGHT, thought=True)]),
            author="ken_e",
            timestamp=100.0,
        )
        answer = SimpleNamespace(
            content=SimpleNamespace(role="model", parts=[_part(_ANSWER)]),
            author="ken_e",
            timestamp=107.0,
        )
        session = SimpleNamespace(events=[thought_only, answer])
        client._session_service.get_session = AsyncMock(return_value=session)

        result = await client.get_conversation_history("u1", "s1")

        assert result["events"][0]["reasoning"]["durationSeconds"] == 7

    @pytest.mark.asyncio
    async def test_plain_answer_has_no_reasoning_field(self) -> None:
        """A turn with no thoughts carries no reasoning field (no empty key)."""
        client = _client_with_events([_part(_ANSWER)])
        result = await client.get_conversation_history("u1", "s1")
        assert "reasoning" not in result["events"][0]

    @pytest.mark.asyncio
    async def test_contentless_system_state_event_is_excluded(self) -> None:
        """The per-turn ga_credentials state event (author=system, no content)
        must not surface as a blank message in history."""
        client = AgentEngineClient()
        client._session_service = AsyncMock()
        system_state_event = SimpleNamespace(
            content=None, author="system", timestamp=1780054954.0
        )
        session = SimpleNamespace(
            events=[system_state_event, _assistant_event([_part(_ANSWER)])]
        )
        client._session_service.get_session = AsyncMock(return_value=session)

        result = await client.get_conversation_history("u1", "s1")

        assert result["events"] == [
            {
                "content": {"parts": [{"text": _ANSWER}]},
                "role": "model",
                "timestamp": 1780054954.0,
            }
        ]
