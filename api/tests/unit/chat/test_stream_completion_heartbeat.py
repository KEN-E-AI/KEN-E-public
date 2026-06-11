"""Unit tests for the SSE heartbeat frame (CH-71, workstream B).

These drive the REAL ``_stream_completion_sse`` generator and assert on the
frame it emits for a ``("ping", …)`` tuple — i.e. the production comment-frame
path at ``chat.py``'s ``if channel == "ping": yield f": ping {text}\\n\\n"`` —
the initial cold-start keep-alive ping, and the idle-cadence decision predicate
``_should_emit_heartbeat``.

NOTE: the wiring of ``_should_emit_heartbeat`` into the threaded chunk-queue
poller inside ``AgentEngineClient.stream_chat_completion`` (reading
``time.monotonic()`` off a background thread) is exercised in staging; the pure
cadence decision is unit-tested here via the extracted predicate.

Harness mirrors test_stream_flush.py / test_stream_completion_status_routing.py.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from src.kene_api.chat.accumulator import SessionTurnAccumulator
from src.kene_api.routers import chat as chat_module


def _fake_stream(tuples: list[tuple[str, str, str]]):
    async def _gen(
        *, accumulator: SessionTurnAccumulator | None = None, **_kwargs: Any
    ):
        for item in tuples:
            yield item

    return _gen


async def _collect_frames(tuples: list[tuple[str, str, str]]) -> list[str]:
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


@pytest.mark.asyncio
async def test_initial_keepalive_ping_is_emitted_first() -> None:
    """Every stream leads with a `: ping 0` keep-alive before any agent output,
    so a slow cold start cannot trip the client's first-read silence timer (#3)."""
    frames = await _collect_frames([("text", "answer", "model")])
    assert frames[0] == ": ping 0\n\n", frames


@pytest.mark.asyncio
async def test_ping_tuple_is_emitted_as_sse_comment_frame() -> None:
    """A ("ping", n, ...) tuple becomes a literal `: ping n\\n\\n` comment frame."""
    frames = await _collect_frames([("ping", "12345", "model")])
    assert ": ping 12345\n\n" in frames, frames


@pytest.mark.asyncio
async def test_emitted_ping_frame_is_a_valid_sse_comment() -> None:
    """The real frame must be ignorable by every SSE parser: ':'-prefixed, no event/data."""
    frames = await _collect_frames([("ping", "999", "model")])
    # The injected ping (not the leading keep-alive) — assert its exact frame.
    ping = next(f for f in frames if f == ": ping 999\n\n")
    assert ping.startswith(":") and ping.endswith("\n\n")
    for line in ping.strip().split("\n"):
        assert not line.startswith("event:")
        assert not line.startswith("data:")
    # Counter portion round-trips as an integer.
    assert ping[len(": ping ") :].strip().isdigit()


@pytest.mark.asyncio
async def test_ping_does_not_corrupt_surrounding_text_frames() -> None:
    """A heartbeat interleaved with answer text must not merge into the text frames."""
    frames = await _collect_frames(
        [
            ("text", "before ping", "model"),
            ("ping", "42", "model"),
            ("text", "after ping", "model"),
        ]
    )
    text_frames = [f for f in frames if f.startswith("data: ")]
    assert "data: before ping\n\n" in text_frames, frames
    assert "data: after ping\n\n" in text_frames, frames
    # The ping is its own comment frame; its counter never lands in a text frame.
    assert all("42" not in f for f in text_frames), frames
    assert ": ping 42\n\n" in frames, frames


class TestShouldEmitHeartbeat:
    """The idle-cadence decision split out of the threaded poll loop (#5)."""

    def test_false_below_threshold(self) -> None:
        assert chat_module._should_emit_heartbeat(now=114.0, last_chunk_at=100.0) is False

    def test_true_at_exactly_threshold(self) -> None:
        # Boundary: idle == interval must ping (>=, not >).
        assert (
            chat_module._should_emit_heartbeat(now=115.0, last_chunk_at=100.0) is True
        )

    def test_true_above_threshold(self) -> None:
        assert (
            chat_module._should_emit_heartbeat(now=130.0, last_chunk_at=100.0) is True
        )

    def test_just_below_threshold_is_false(self) -> None:
        assert (
            chat_module._should_emit_heartbeat(now=114.999, last_chunk_at=100.0)
            is False
        )

    def test_default_interval_is_15s_and_under_one_third_of_client_silence(self) -> None:
        # 3x ratio: client declares death at 45 s, so 15 s misses three pings.
        assert chat_module._HEARTBEAT_IDLE_SECONDS == 15.0

    def test_custom_interval_overrides_default(self) -> None:
        assert (
            chat_module._should_emit_heartbeat(
                now=105.0, last_chunk_at=100.0, interval=5.0
            )
            is True
        )
        assert (
            chat_module._should_emit_heartbeat(
                now=104.0, last_chunk_at=100.0, interval=5.0
            )
            is False
        )
