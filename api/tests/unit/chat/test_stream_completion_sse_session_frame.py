"""Unit tests for the SSE session frame emitted by _stream_completion_sse.

Verifies that when stream_chat_completion yields a ("session", id) tuple,
_stream_completion_sse emits a well-formed `event: session\ndata: {...}\n\n`
frame before any text content frames; and that the accumulator's token/tool
counters are not affected by the session tuple.

References: CH-62 Implementation Plan Task 6c-d.
"""
from __future__ import annotations

import json
import os
import sys
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user_context(user_id: str = "user_1") -> MagicMock:
    ctx = MagicMock()
    ctx.user_id = user_id
    return ctx


async def _collect_sse(gen: AsyncGenerator[str, None]) -> list[str]:
    """Collect all SSE string frames from an async generator."""
    return [frame async for frame in gen]


def _parse_sse_frames(frames: list[str]) -> list[dict]:
    """Parse a list of raw SSE frame strings into dicts with 'event' and 'data'."""
    parsed = []
    for frame in frames:
        lines = frame.strip().split("\n")
        obj: dict = {}
        data_lines: list[str] = []
        for line in lines:
            if line.startswith("event: "):
                obj["event"] = line[7:]
            elif line.startswith("data: "):
                data_lines.append(line[6:])
        if data_lines:
            obj["data"] = "\n".join(data_lines)
        parsed.append(obj)
    return parsed


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestStreamCompletionSseSessionFrame:
    async def test_session_tuple_produces_event_session_frame(self):
        """A ("session", "real_42", "model") tuple yields event: session + data JSON frame."""
        from kene_api.routers.chat import _stream_completion_sse
        from kene_api.routers.chat import ChatMessage

        async def _fake_stream(**kwargs) -> AsyncGenerator[tuple[str, str, str], None]:
            yield ("session", "real_42", "model")
            yield ("text", "Hello.", "model")

        with patch(
            "kene_api.routers.chat.agent_client.stream_chat_completion",
            side_effect=lambda **kw: _fake_stream(**kw),
        ):
            with patch(
                "kene_api.routers.chat._flush_stream_turn",
                new=AsyncMock(),
            ):
                frames = await _collect_sse(
                    _stream_completion_sse(
                        messages=[ChatMessage(role="user", content="hi")],
                        user_context=_make_user_context(),
                        session_id="pending_abc",
                        conversation_name=None,
                        account_id="acct_1",
                        turn_uuid="test-uuid",
                    )
                )

        parsed = _parse_sse_frames(frames)
        session_frames = [f for f in parsed if f.get("event") == "session"]
        assert len(session_frames) == 1, (
            f"Expected exactly one session frame, got {session_frames}"
        )
        payload = json.loads(session_frames[0]["data"])
        assert payload == {"session_id": "real_42"}, (
            f"Unexpected session payload: {payload}"
        )

    async def test_session_frame_appears_before_text_frame(self):
        """The session frame precedes the first text frame in the SSE output."""
        from kene_api.routers.chat import _stream_completion_sse
        from kene_api.routers.chat import ChatMessage

        async def _fake_stream(**kwargs) -> AsyncGenerator[tuple[str, str, str], None]:
            yield ("session", "real_99", "model")
            yield ("text", "Answer text.", "model")

        with patch(
            "kene_api.routers.chat.agent_client.stream_chat_completion",
            side_effect=lambda **kw: _fake_stream(**kw),
        ):
            with patch(
                "kene_api.routers.chat._flush_stream_turn",
                new=AsyncMock(),
            ):
                frames = await _collect_sse(
                    _stream_completion_sse(
                        messages=[ChatMessage(role="user", content="hi")],
                        user_context=_make_user_context(),
                        session_id="pending_xyz",
                        conversation_name=None,
                        account_id="acct_1",
                        turn_uuid="test-uuid-2",
                    )
                )

        # Find position of session frame and first data (text) frame.
        session_pos = next(
            (i for i, f in enumerate(frames) if "event: session" in f), None
        )
        text_pos = next(
            (
                i
                for i, f in enumerate(frames)
                if f.startswith("data:") and "[DONE]" not in f and "event:" not in f
            ),
            None,
        )
        assert session_pos is not None, "No session frame found"
        assert text_pos is not None, "No text frame found"
        assert session_pos < text_pos, (
            f"Session frame at {session_pos} must precede text frame at {text_pos}"
        )

    async def test_session_frame_does_not_appear_without_session_tuple(self):
        """Without a ("session", ...) tuple from stream_chat_completion, no
        event: session frame appears in the SSE output."""
        from kene_api.routers.chat import _stream_completion_sse
        from kene_api.routers.chat import ChatMessage

        async def _fake_stream(**kwargs) -> AsyncGenerator[tuple[str, str, str], None]:
            yield ("text", "No session resolution here.", "model")

        with patch(
            "kene_api.routers.chat.agent_client.stream_chat_completion",
            side_effect=lambda **kw: _fake_stream(**kw),
        ):
            with patch(
                "kene_api.routers.chat._flush_stream_turn",
                new=AsyncMock(),
            ):
                frames = await _collect_sse(
                    _stream_completion_sse(
                        messages=[ChatMessage(role="user", content="hi")],
                        user_context=_make_user_context(),
                        session_id="existing_99",
                        conversation_name=None,
                        account_id="acct_1",
                        turn_uuid="test-uuid-3",
                    )
                )

        session_frames = [f for f in frames if "event: session" in f]
        assert session_frames == [], (
            f"No session frame expected, got {session_frames}"
        )

    async def test_accumulator_unaffected_by_session_tuple(self):
        """The session tuple is metadata; it must not advance token counters or
        the reasoning sequence counter. We verify this by checking that the
        accumulated text content is from the text tuple only."""
        from kene_api.routers.chat import _stream_completion_sse
        from kene_api.routers.chat import ChatMessage

        async def _fake_stream(**kwargs) -> AsyncGenerator[tuple[str, str, str], None]:
            yield ("session", "real_77", "model")
            yield ("text", "The real answer.", "model")

        with patch(
            "kene_api.routers.chat.agent_client.stream_chat_completion",
            side_effect=lambda **kw: _fake_stream(**kw),
        ):
            with patch(
                "kene_api.routers.chat._flush_stream_turn",
                new=AsyncMock(),
            ) as mock_flush:
                frames = await _collect_sse(
                    _stream_completion_sse(
                        messages=[ChatMessage(role="user", content="hi")],
                        user_context=_make_user_context(),
                        session_id="pending_zzz",
                        conversation_name=None,
                        account_id="acct_1",
                        turn_uuid="test-uuid-4",
                    )
                )

        # The text frame should carry "The real answer." — verifies the session
        # tuple didn't consume the text tuple.
        text_frames = [f for f in frames if f.startswith("data: The real answer.")]
        assert len(text_frames) == 1, (
            f"Expected one text frame with answer, got frames: {frames}"
        )

        # _flush_stream_turn should have been called exactly once (in the finally block).
        assert mock_flush.call_count == 1

    async def test_only_one_session_frame_emitted(self):
        """Even if stream_chat_completion accidentally yields multiple session
        tuples, _stream_completion_sse passes them through; but the test confirms
        the normal contract: exactly one session tuple → exactly one SSE frame."""
        from kene_api.routers.chat import _stream_completion_sse
        from kene_api.routers.chat import ChatMessage

        async def _fake_stream(**kwargs) -> AsyncGenerator[tuple[str, str, str], None]:
            yield ("session", "real_once", "model")
            yield ("text", "reply", "model")

        with patch(
            "kene_api.routers.chat.agent_client.stream_chat_completion",
            side_effect=lambda **kw: _fake_stream(**kw),
        ):
            with patch(
                "kene_api.routers.chat._flush_stream_turn",
                new=AsyncMock(),
            ):
                frames = await _collect_sse(
                    _stream_completion_sse(
                        messages=[ChatMessage(role="user", content="hi")],
                        user_context=_make_user_context(),
                        session_id="pending_once",
                        conversation_name=None,
                        account_id="acct_1",
                        turn_uuid="test-uuid-5",
                    )
                )

        session_frames = [f for f in frames if "event: session" in f]
        assert len(session_frames) == 1, (
            f"Expected exactly 1 session frame, got {len(session_frames)}"
        )
