"""Regression tests for status-event routing in _stream_completion_sse (CH-71).

The status channel is dispatched BEFORE the author-based reviewer/worker
branches. These tests drive the real `_stream_completion_sse` generator with a
worker-/reviewer-/model-authored status event and assert:

- A worker-authored status NEVER leaks into the answer text (it must not be
  buffered into _worker_text_buf and flushed as an `event: text` frame — the
  CH-68/69 leak class). It is surfaced as an `event: status` frame instead.
- A worker's real draft text still flushes as answer text at stream end, so the
  reorder did not break CH-69's collapse-to-final buffering.
- A reviewer-authored status is fully suppressed (CH-68 consistency).
- A model-authored status is emitted as an `event: status` frame.

Harness mirrors test_stream_flush.py.
"""

from __future__ import annotations

from typing import Any

import pytest
from src.kene_api.chat.accumulator import SessionTurnAccumulator
from src.kene_api.routers import chat as chat_module


def _fake_stream(tuples: list[tuple[str, str, str]]):
    """Stand-in for AgentEngineClient.stream_chat_completion yielding raw tuples."""

    async def _gen(
        *, accumulator: SessionTurnAccumulator | None = None, **_kwargs: Any
    ):
        for item in tuples:
            yield item

    return _gen


async def _collect_frames(tuples: list[tuple[str, str, str]]) -> list[str]:
    from unittest.mock import MagicMock, patch

    with (
        patch.object(
            chat_module.agent_client, "stream_chat_completion", _fake_stream(tuples)
        ),
        patch.object(
            chat_module, "apply_side_table_update", MagicMock(return_value={})
        ),
        patch.object(chat_module, "_get_firestore_client", lambda: MagicMock()),
    ):
        gen = chat_module._stream_completion_sse(
            messages=[],
            user_context=MagicMock(),
            session_id="sess-x",
            conversation_name=None,
            account_id="acc-x",
            turn_uuid="turn-x",
        )
        return [frame async for frame in gen]


def _text_frames(frames: list[str]) -> list[str]:
    """Plain answer-text frames: `data: …` not prefixed by an `event:` line."""
    return [f for f in frames if f.startswith("data: ")]


def _status_frames(frames: list[str]) -> list[str]:
    return [f for f in frames if f.startswith("event: status")]


class TestStatusRouting:
    @pytest.mark.asyncio
    async def test_worker_authored_status_does_not_leak_into_answer_text(self) -> None:
        frames = await _collect_frames(
            [
                ("text", "worker draft answer ", "ga_specialist_worker"),
                ("status", "Running GA report…", "ga_specialist_worker"),
            ]
        )

        # The status label must NOT appear in any answer-text frame (the leak).
        assert all("Running GA report" not in f for f in _text_frames(frames)), frames
        # It is surfaced as an event: status frame (worker progress is shown).
        assert any("Running GA report" in f for f in _status_frames(frames)), frames
        # The worker's real draft still flushes as answer text (CH-69 intact).
        assert any("worker draft answer" in f for f in _text_frames(frames)), frames

    @pytest.mark.asyncio
    async def test_worker_status_does_not_prematurely_flush_draft(self) -> None:
        # A status arriving mid-iteration must not collapse the buffered draft:
        # both worker text fragments must end up in a single flushed answer.
        frames = await _collect_frames(
            [
                ("text", "part one ", "ga_specialist_worker"),
                ("status", "Running GA report…", "ga_specialist_worker"),
                ("text", "part two", "ga_specialist_worker"),
            ]
        )
        text_blob = "".join(_text_frames(frames))
        assert "part one " in text_blob and "part two" in text_blob, frames
        assert "Running GA report" not in text_blob, frames

    @pytest.mark.asyncio
    async def test_reviewer_authored_status_is_suppressed(self) -> None:
        frames = await _collect_frames(
            [("status", "Running GA report…", "ga_specialist_reviewer")]
        )
        # Reviewer activity is display-suppressed — neither text nor status frame.
        assert all("Running GA report" not in f for f in frames), frames
        assert _status_frames(frames) == [], frames

    @pytest.mark.asyncio
    async def test_model_authored_status_is_emitted(self) -> None:
        frames = await _collect_frames(
            [("status", "Creating visualization…", "model")]
        )
        status = _status_frames(frames)
        assert len(status) == 1, frames
        # json.dumps escapes the non-ASCII ellipsis (ensure_ascii) — match the
        # ASCII stem, which the client's JSON.parse decodes back to "…".
        assert "Creating visualization" in status[0]
        # Model author → no "author" key in the payload (back-compat).
        assert '"author"' not in status[0], status[0]
