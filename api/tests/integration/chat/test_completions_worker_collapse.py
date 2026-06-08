"""Integration tests for worker-draft collapse on the SSE stream path (CH-69).

Tests verify that only the final approved worker draft per review loop is
surfaced in the user-visible SSE output.  Earlier-iteration drafts (whose
matched reviewer fired a rejection) are suppressed while the accumulator
continues to receive every chunk unchanged.

The tests monkey-patch ``agent_client.stream_chat_completion`` to return a
known sequence of ``(channel, text, author)`` tuples — no real Vertex AI
calls are made.

References: CH-69 Implementation Plan Task 2, Task 4.
"""

from __future__ import annotations

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


def _make_user_context():
    ctx = MagicMock()
    ctx.user_id = "test-user"
    ctx.has_account_access = MagicMock(return_value=True)
    return ctx


def _text_frames(frames: list[str]) -> list[str]:
    return [
        f
        for f in frames
        if f.startswith("data:") and "[DONE]" not in f and not f.startswith("data: [")
    ]


def _reasoning_frames(frames: list[str]) -> list[str]:
    return [f for f in frames if f.startswith("event: reasoning")]


def _author_sidecar_frames(frames: list[str]) -> list[str]:
    return [f for f in frames if f.startswith("event: author")]


def _text_content(frames: list[str]) -> str:
    return "".join(f.split("data: ", 1)[1].rstrip("\n") for f in _text_frames(frames))


def _make_gen(items):
    async def fake_stream(**kwargs):
        for item in items:
            yield item

    return fake_stream


# ---------------------------------------------------------------------------
# AC-1: multi-iteration loop — only final draft visible
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_three_iteration_loop_only_final_draft_visible():
    """Given a 3-iteration review loop, only draft 3 appears in SSE output."""
    items = [
        ("text", "Draft 1: 62 active users last 7 days.", "ga_worker"),
        ("text", "Relative date range missing.", "ga_review_reviewer"),
        ("text", "Draft 2: 62 active users 2024-01-16 to 2024-01-22.", "ga_worker"),
        ("text", "Missing formula explanation.", "ga_review_reviewer"),
        ("text", "Draft 3: 62 active users (no formula needed).", "ga_worker"),
    ]

    async def fake_stream(**kwargs):
        for item in items:
            yield item

    with (
        patch(
            "kene_api.routers.chat.agent_client.stream_chat_completion",
            side_effect=fake_stream,
        ),
        patch("kene_api.routers.chat._flush_stream_turn", new_callable=AsyncMock),
        patch("kene_api.routers.chat._maybe_set_temp_title", new_callable=AsyncMock),
    ):
        frames = await _collect_sse(
            _stream_completion_sse(
                messages=[],
                user_context=_make_user_context(),
                session_id="sess-3iter",
                conversation_name=None,
                account_id="acc-1",
                turn_uuid="turn-3iter",
            )
        )

    combined = _text_content(frames)
    assert "Draft 1" not in combined, "Draft 1 must be suppressed"
    assert "Draft 2" not in combined, "Draft 2 must be suppressed"
    assert "Draft 3" in combined, "Final draft must appear"
    assert "Relative date range" not in combined, "Reviewer text must remain suppressed"
    assert "Missing formula" not in combined


# ---------------------------------------------------------------------------
# AC-2: single-iteration loop — the one draft is visible
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_iteration_loop_draft_visible():
    """A single-iteration loop (worker → reviewer → end) yields the worker draft."""
    items = [
        ("text", "Only draft: 42 sessions.", "ga_worker"),
        ("text", "Approved.", "ga_review_reviewer"),
    ]

    async def fake_stream(**kwargs):
        for item in items:
            yield item

    with (
        patch(
            "kene_api.routers.chat.agent_client.stream_chat_completion",
            side_effect=fake_stream,
        ),
        patch("kene_api.routers.chat._flush_stream_turn", new_callable=AsyncMock),
        patch("kene_api.routers.chat._maybe_set_temp_title", new_callable=AsyncMock),
    ):
        frames = await _collect_sse(
            _stream_completion_sse(
                messages=[],
                user_context=_make_user_context(),
                session_id="sess-1iter",
                conversation_name=None,
                account_id="acc-1",
                turn_uuid="turn-1iter",
            )
        )

    combined = _text_content(frames)
    assert "Only draft" in combined


# ---------------------------------------------------------------------------
# AC-3: single-author model turn — byte-for-byte identical to pre-CH-69
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_author_model_turn_unchanged():
    """Single-author ``model`` turn produces no buffering artefacts."""
    items = [
        ("text", "Hello. ", "model"),
        ("text", "World.", "model"),
    ]

    async def fake_stream(**kwargs):
        for item in items:
            yield item

    with (
        patch(
            "kene_api.routers.chat.agent_client.stream_chat_completion",
            side_effect=fake_stream,
        ),
        patch("kene_api.routers.chat._flush_stream_turn", new_callable=AsyncMock),
        patch("kene_api.routers.chat._maybe_set_temp_title", new_callable=AsyncMock),
    ):
        frames = await _collect_sse(
            _stream_completion_sse(
                messages=[],
                user_context=_make_user_context(),
                session_id="sess-model",
                conversation_name=None,
                account_id="acc-1",
                turn_uuid="turn-model",
            )
        )

    text_frames = _text_frames(frames)
    assert len(text_frames) == 2, "model turn must yield 2 text frames (no buffering)"
    sidecar_frames = _author_sidecar_frames(frames)
    assert len(sidecar_frames) == 0, "no author sidecar for single-author model turn"
    combined = _text_content(frames)
    assert "Hello." in combined and "World." in combined


# ---------------------------------------------------------------------------
# AC-4: AH-PRD-05 interleaved fan-out — independent worker buffers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_interleaved_fan_out_independent_buffers():
    """specialist_a (2 iterations) and specialist_b (1 iteration) fan-out.

    Key invariant: specialist_a_review_reviewer must NOT touch specialist_b's
    buffer.  After specialist_a's reviewer fires and specialist_a produces a
    new draft, specialist_b's single-iteration buffer should still be intact
    and flush at stream end.
    """
    items = [
        ("text", "A draft 1.", "specialist_a_worker"),
        ("text", "B draft 1 (final).", "specialist_b_worker"),
        ("text", "Reject A.", "specialist_a_review_reviewer"),
        ("text", "A draft 2 (final).", "specialist_a_worker"),
    ]

    async def fake_stream(**kwargs):
        for item in items:
            yield item

    with (
        patch(
            "kene_api.routers.chat.agent_client.stream_chat_completion",
            side_effect=fake_stream,
        ),
        patch("kene_api.routers.chat._flush_stream_turn", new_callable=AsyncMock),
        patch("kene_api.routers.chat._maybe_set_temp_title", new_callable=AsyncMock),
    ):
        frames = await _collect_sse(
            _stream_completion_sse(
                messages=[],
                user_context=_make_user_context(),
                session_id="sess-fanout",
                conversation_name=None,
                account_id="acc-1",
                turn_uuid="turn-fanout",
            )
        )

    combined = _text_content(frames)
    assert "A draft 1" not in combined, "Rejected A draft 1 must be suppressed"
    assert "A draft 2 (final)" in combined, "Final A draft must appear"
    # specialist_b had only 1 iteration; its buffer was NOT cleared by A's reviewer.
    assert "B draft 1 (final)" in combined, "B single-iteration draft must appear"


# ---------------------------------------------------------------------------
# AC-5: worker buffer flushes before non-worker non-reviewer author mid-stream
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_worker_buffer_flushed_before_coordinator():
    """Worker buffer flushes to SSE before a coordinator text event."""
    items = [
        ("text", "Worker final draft.", "ga_worker"),
        ("text", "Coordinator summary.", "coordinator"),
    ]

    async def fake_stream(**kwargs):
        for item in items:
            yield item

    with (
        patch(
            "kene_api.routers.chat.agent_client.stream_chat_completion",
            side_effect=fake_stream,
        ),
        patch("kene_api.routers.chat._flush_stream_turn", new_callable=AsyncMock),
        patch("kene_api.routers.chat._maybe_set_temp_title", new_callable=AsyncMock),
    ):
        frames = await _collect_sse(
            _stream_completion_sse(
                messages=[],
                user_context=_make_user_context(),
                session_id="sess-coord",
                conversation_name=None,
                account_id="acc-1",
                turn_uuid="turn-coord",
            )
        )

    # Worker frame should appear before coordinator frame.
    combined = _text_content(frames)
    assert "Worker final draft" in combined
    assert "Coordinator summary" in combined
    worker_pos = combined.index("Worker final draft")
    coord_pos = combined.index("Coordinator summary")
    assert worker_pos < coord_pos, "Worker buffer must flush before coordinator"


# ---------------------------------------------------------------------------
# AC-6: accumulator parity — every chunk reaches the accumulator
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_accumulator_receives_all_chunks_including_discarded_worker():
    """CH-69 AC-3 / CH-68 AC-2: all worker chunks (even discarded ones) feed the
    accumulator; billing / MER-E counts are unchanged."""
    import sys

    sys.path.insert(
        0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "api", "src")
    )

    from kene_api.auth.models import UserContext
    from kene_api.chat.accumulator import SessionTurnAccumulator
    from kene_api.routers.chat import AgentEngineClient, ChatMessage

    worker_chunk_1 = {
        "author": "ga_worker",
        "content": {"parts": [{"text": "Draft 1."}]},
    }
    reviewer_chunk = {
        "author": "ga_review_reviewer",
        "content": {"parts": [{"text": "Rejected."}]},
    }
    worker_chunk_2 = {
        "author": "ga_worker",
        "content": {"parts": [{"text": "Draft 2 (final)."}]},
    }

    mock_engine = MagicMock()

    def mock_stream_query(message: str, user_id: str, session_id: str):
        yield from [worker_chunk_1, reviewer_chunk, worker_chunk_2]

    mock_engine.stream_query = mock_stream_query

    with patch.dict(
        os.environ,
        {
            "GOOGLE_CLOUD_PROJECT_ID": "test-project",
            "VERTEX_AI_LOCATION": "us-central1",
            "VERTEX_AI_AGENT_ENGINE_ID": "projects/test/locations/us-central1/reasoningEngines/test-id",
            "ENVIRONMENT": "test",
        },
    ):
        client = AgentEngineClient()
        client._agent_engine = mock_engine

    accumulator = SessionTurnAccumulator()
    original_add = accumulator.add_stream_chunk
    add_calls: list = []

    def spy_add(chunk):
        add_calls.append(chunk)
        original_add(chunk)

    accumulator.add_stream_chunk = spy_add  # type: ignore[method-assign]

    user_ctx = UserContext(
        user_id="test-user",
        email="t@example.com",
        organization_permissions={},
        account_permissions={},
    )
    messages = [ChatMessage(role="user", content="GA query", timestamp="")]

    results = []
    async for item in client.stream_chat_completion(
        messages=messages,
        user_context=user_ctx,
        session_id="test-session-acc",
        accumulator=accumulator,
    ):
        results.append(item)

    # Accumulator must have received all 3 chunks — including the discarded draft 1.
    assert len(add_calls) == 3, (
        f"Expected 3 accumulator calls (worker1+reviewer+worker2), got {len(add_calls)}"
    )
    assert add_calls[0] is worker_chunk_1, "Discarded chunk 1 must reach the accumulator"
    assert add_calls[1] is reviewer_chunk, "Reviewer chunk must feed the accumulator"
    assert add_calls[2] is worker_chunk_2, "Final chunk must reach the accumulator"

    # stream_chat_completion emits (channel, text, author) tuples with the CH-68
    # reviewer filter applied, but the CH-69 worker collapse is applied at the
    # _stream_completion_sse layer above.  Both worker drafts appear here; the
    # collapse into final-draft-only happens in _stream_completion_sse.
    text_items = [t for ch, t, a in results if ch == "text"]
    combined = "".join(text_items)
    assert "Needs more context" not in combined, "Reviewer text must remain suppressed (CH-68)"
    assert "Draft 1" in combined, "stream_chat_completion passes both worker drafts through"
    assert "Draft 2 (final)" in combined


# ---------------------------------------------------------------------------
# AC-7: cancelled stream does NOT flush worker buffer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancelled_stream_does_not_flush_worker_buffer():
    """On GeneratorExit / CancelledError, no synthesised worker text is emitted."""
    import asyncio

    yielded: list[str] = []

    async def cancelling_gen(**kwargs):
        yield ("text", "Worker draft.", "ga_worker")
        # Simulate agent-side cancellation after one chunk.
        raise asyncio.CancelledError

    with (
        patch(
            "kene_api.routers.chat.agent_client.stream_chat_completion",
            side_effect=cancelling_gen,
        ),
        patch("kene_api.routers.chat._flush_stream_turn", new_callable=AsyncMock),
        patch("kene_api.routers.chat._maybe_set_temp_title", new_callable=AsyncMock),
    ):
        gen = _stream_completion_sse(
            messages=[],
            user_context=_make_user_context(),
            session_id="sess-cancel",
            conversation_name=None,
            account_id="acc-1",
            turn_uuid="turn-cancel",
        )
        try:
            async for frame in gen:
                yielded.append(frame)
        except (asyncio.CancelledError, Exception):
            pass

    # No text frame containing worker draft should have been yielded.
    text_frames = _text_frames(yielded)
    combined = "".join(f.split("data: ", 1)[1] for f in text_frames)
    assert "Worker draft" not in combined, (
        "Cancelled stream must not flush buffered worker draft"
    )


# ---------------------------------------------------------------------------
# AC-8: reasoning channel buffered and dropped/flushed correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reasoning_channel_buffered_and_dropped_with_rejected_draft():
    """Reasoning frames from a rejected worker iteration are dropped."""
    items = [
        ("reasoning", "Worker thinking about draft 1.", "ga_worker"),
        ("text", "Draft 1.", "ga_worker"),
        ("text", "Reject.", "ga_review_reviewer"),
        ("reasoning", "Worker thinking about draft 2.", "ga_worker"),
        ("text", "Draft 2 (final).", "ga_worker"),
    ]

    async def fake_stream(**kwargs):
        for item in items:
            yield item

    with (
        patch(
            "kene_api.routers.chat.agent_client.stream_chat_completion",
            side_effect=fake_stream,
        ),
        patch("kene_api.routers.chat._flush_stream_turn", new_callable=AsyncMock),
        patch("kene_api.routers.chat._maybe_set_temp_title", new_callable=AsyncMock),
    ):
        frames = await _collect_sse(
            _stream_completion_sse(
                messages=[],
                user_context=_make_user_context(),
                session_id="sess-reasoning",
                conversation_name=None,
                account_id="acc-1",
                turn_uuid="turn-reasoning",
            )
        )

    reasoning_frames = _reasoning_frames(frames)
    reasoning_texts = [
        json.loads(f.split("data: ", 1)[1])["text"] for f in reasoning_frames
    ]
    # Draft 1 reasoning must be dropped; draft 2 reasoning must appear.
    assert not any("draft 1" in t.lower() for t in reasoning_texts), (
        "Rejected iteration reasoning must be dropped"
    )
    assert any("draft 2" in t.lower() for t in reasoning_texts), (
        "Final iteration reasoning must appear"
    )

    text_combined = _text_content(frames)
    assert "Draft 1" not in text_combined
    assert "Draft 2 (final)" in text_combined
