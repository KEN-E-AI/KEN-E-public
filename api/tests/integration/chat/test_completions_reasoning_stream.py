"""Integration tests for reasoning-channel SSE stream (CH-60).

Tests cover:
- Interleaved text/reasoning chunks produce correctly framed SSE output.
- Cancellation path still flushes the side-table accumulator.
- Contentless event chunks between thought+text produce zero output bytes (CH-59 regression).

These tests monkey-patch ``agent_client.stream_chat_completion`` to return a
known sequence of (channel, text) tuples — no real Vertex AI calls are made.

References: CH-60 Implementation Plan Task 5.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from kene_api.routers.chat import _stream_completion_sse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _collect_sse(gen) -> list[str]:
    """Collect all SSE frames from an async generator into a list."""
    frames: list[str] = []
    async for frame in gen:
        frames.append(frame)
    return frames


async def _fake_stream(items: list[tuple[str, str]]):
    """Async generator that yields pre-defined (channel, text) tuples."""
    for item in items:
        yield item


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_user_context():
    ctx = MagicMock()
    ctx.user_id = "test-user"
    ctx.has_account_access = MagicMock(return_value=True)
    return ctx


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_text_and_reasoning_interleaving():
    """Two reasoning blocks and three text blocks produce correctly framed SSE."""
    items = [
        ("text", "Hi. "),
        ("reasoning", "I should think step by step."),
        ("text", "Let me "),
        ("reasoning", "First, check assumptions."),
        ("text", "answer."),
    ]

    async def fake_stream(**kwargs):
        for item in items:
            yield item

    with (
        patch(
            "kene_api.routers.chat.agent_client.stream_chat_completion",
            side_effect=fake_stream,
        ),
        patch(
            "kene_api.routers.chat._flush_stream_turn",
            new_callable=AsyncMock,
        ) as mock_flush,
    ):
        frames = await _collect_sse(
            _stream_completion_sse(
                messages=[],
                user_context=_make_user_context(),
                session_id="sess-1",
                conversation_name=None,
                account_id="acc-1",
                turn_uuid="turn-1",
            )
        )

    # Separate reasoning frames from text frames
    reasoning_frames = [f for f in frames if f.startswith("event: reasoning")]
    text_frames = [f for f in frames if f.startswith("data:") and "[DONE]" not in f]
    done_frames = [f for f in frames if "[DONE]" in f]

    # Two reasoning blocks
    assert len(reasoning_frames) == 2
    seq_values = []
    for rf in reasoning_frames:
        data_part = rf.split("data: ", 1)[1].strip()
        payload = json.loads(data_part)
        seq_values.append(payload["seq"])
    assert seq_values == [0, 1], "seq must start at 0 and increment per reasoning emit"

    # Three text blocks
    assert len(text_frames) == 3

    # One DONE terminator
    assert len(done_frames) == 1
    assert done_frames[0] == "data: [DONE]\n\n"

    # flush was called exactly once (finally block)
    mock_flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancellation_path_calls_flush():
    """CancelledError triggers the finally block which calls _flush_stream_turn."""

    async def fake_stream_raises(**kwargs):
        yield ("text", "partial")
        raise asyncio.CancelledError()

    with (
        patch(
            "kene_api.routers.chat.agent_client.stream_chat_completion",
            side_effect=fake_stream_raises,
        ),
        patch(
            "kene_api.routers.chat._flush_stream_turn",
            new_callable=AsyncMock,
        ) as mock_flush,
    ):
        gen = _stream_completion_sse(
            messages=[],
            user_context=_make_user_context(),
            session_id="sess-cancel",
            conversation_name=None,
            account_id="acc-1",
            turn_uuid="turn-cancel",
        )

        frames: list[str] = []
        with pytest.raises((asyncio.CancelledError, GeneratorExit, Exception)):
            async for frame in gen:
                frames.append(frame)

    # Flush is called with turn_failed=True to record the partial token counts
    mock_flush.assert_awaited_once()
    call_kwargs = mock_flush.await_args.kwargs
    assert call_kwargs.get("turn_failed") is True


@pytest.mark.asyncio
async def test_contentless_event_produces_no_output():
    """CH-59 regression guard: contentless events produce zero SSE frames (excluding DONE)."""

    # stream_chat_completion itself skips contentless chunks — the caller gets no tuples
    # for those chunks. Simulate: zero tuples emitted.
    async def fake_stream_empty(**kwargs):
        # Yield nothing — simulates contentless event + function event skipping
        return
        yield  # make it a generator

    with (
        patch(
            "kene_api.routers.chat.agent_client.stream_chat_completion",
            side_effect=fake_stream_empty,
        ),
        patch(
            "kene_api.routers.chat._flush_stream_turn",
            new_callable=AsyncMock,
        ),
    ):
        frames = await _collect_sse(
            _stream_completion_sse(
                messages=[],
                user_context=_make_user_context(),
                session_id="sess-2",
                conversation_name=None,
                account_id="acc-1",
                turn_uuid="turn-2",
            )
        )

    non_done = [f for f in frames if "[DONE]" not in f]
    assert non_done == [], "No content frames expected when stream yields nothing"
    done_frames = [f for f in frames if "[DONE]" in f]
    assert len(done_frames) == 1
