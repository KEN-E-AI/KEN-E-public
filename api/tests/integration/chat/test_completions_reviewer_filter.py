"""Integration tests for reviewer-author SSE stream filter (CH-68).

Tests verify that text/reasoning tuples whose ``author`` matches the
``*_reviewer`` convention are suppressed from the user-visible SSE output,
while the accumulator and other channels are unaffected.

The tests monkey-patch ``agent_client.stream_chat_completion`` to return a
known sequence of ``(channel, text, author)`` tuples — no real Vertex AI
calls are made.

References: CH-68 Implementation Plan Task 2.
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
    """Return frames that carry a plain ``data:`` text payload (no DONE, no event:)."""
    return [
        f for f in frames
        if f.startswith("data:") and "[DONE]" not in f and not f.startswith("data: [")
    ]


def _reasoning_frames(frames: list[str]) -> list[str]:
    return [f for f in frames if f.startswith("event: reasoning")]


def _author_sidecar_frames(frames: list[str]) -> list[str]:
    return [f for f in frames if f.startswith("event: author")]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reviewer_text_suppressed_in_sse():
    """Worker→reviewer→revised-worker sequence: reviewer text absent from SSE."""
    items = [
        ("text", "First draft: 65 active users.", "ga_worker"),
        ("text", "The date range is missing.", "ga_review_reviewer"),
        ("text", "Revised: 65 users from Oct 19-25.", "ga_worker"),
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

    text_frames = _text_frames(frames)
    # Only the two worker frames should appear — reviewer text is suppressed.
    assert len(text_frames) == 2, f"Expected 2 text frames, got {len(text_frames)}: {text_frames}"

    combined = "".join(f.split("data: ", 1)[1].strip() for f in text_frames)
    assert "date range is missing" not in combined, "Reviewer critique must not appear in SSE output"
    assert "First draft" in combined or "Revised" in combined

    # Flush called once (finally block)
    mock_flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_reviewer_reasoning_suppressed_in_sse():
    """Reviewer-authored reasoning channel is also suppressed (no reasoning SSE frame)."""
    items = [
        ("reasoning", "Worker thinking...", "ga_worker"),
        ("reasoning", "Reviewer internal critique.", "ga_review_reviewer"),
        ("text", "Final answer.", "ga_worker"),
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
        ),
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
    # Only the worker's reasoning frame should appear.
    assert len(reasoning_frames) == 1
    data = json.loads(reasoning_frames[0].split("data: ", 1)[1].strip())
    assert "Reviewer internal critique" not in data["text"]
    assert "Worker thinking" in data["text"]


@pytest.mark.asyncio
async def test_no_author_sidecar_for_reviewer():
    """No ``event: author`` sidecar frame should be emitted for a ``*_reviewer`` author."""
    items = [
        ("text", "Worker says hi.", "ga_worker"),
        ("text", "Reviewer says nope.", "ga_review_reviewer"),
        ("text", "Worker revised.", "ga_worker"),
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
        ),
    ):
        frames = await _collect_sse(
            _stream_completion_sse(
                messages=[],
                user_context=_make_user_context(),
                session_id="sess-sidecar",
                conversation_name=None,
                account_id="acc-1",
                turn_uuid="turn-sidecar",
            )
        )

    sidecar_frames = _author_sidecar_frames(frames)
    for frame in sidecar_frames:
        data = frame.split("data: ", 1)[1].strip()
        assert not data.endswith("_reviewer"), (
            f"Author sidecar must not expose reviewer author: {frame!r}"
        )


@pytest.mark.asyncio
async def test_single_author_model_unaffected():
    """Single-author ``model`` turn (no reviewer) is byte-for-byte unaffected."""
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
        patch(
            "kene_api.routers.chat._flush_stream_turn",
            new_callable=AsyncMock,
        ),
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
    assert len(text_frames) == 2
    # Extract payload without stripping so trailing spaces are preserved.
    combined = "".join(f.split("data: ", 1)[1].rstrip("\n") for f in text_frames)
    assert "Hello." in combined
    assert "World." in combined


@pytest.mark.asyncio
async def test_reviewer_chunks_still_fed_to_accumulator():
    """AC #2: reviewer chunks must reach the accumulator before display filter (billing/MER-E parity).

    Drives worker -> reviewer -> worker through the real stream_chat_completion
    generator (not patched at the tuple level), verifying accumulator.add_stream_chunk
    is called for every chunk including the reviewer's.
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "api", "src"))

    from kene_api.auth.models import UserContext
    from kene_api.chat.accumulator import SessionTurnAccumulator
    from kene_api.routers.chat import AgentEngineClient, ChatMessage

    # Build a synthetic chunk sequence with worker, reviewer, and worker events.
    worker_chunk = {
        "author": "ga_worker",
        "content": {"parts": [{"text": "Worker answer."}]},
    }
    reviewer_chunk = {
        "author": "ga_review_reviewer",
        "content": {"parts": [{"text": "Needs more context."}]},
    }
    revised_chunk = {
        "author": "ga_worker",
        "content": {"parts": [{"text": "Revised answer."}]},
    }

    mock_engine = MagicMock()

    def mock_stream_query(message: str, user_id: str, session_id: str):
        yield from [worker_chunk, reviewer_chunk, revised_chunk]

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

    # Spy on the accumulator's add_stream_chunk to count calls.
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
    messages = [ChatMessage(role="user", content="How many users?", timestamp="")]

    results = []
    async for item in client.stream_chat_completion(
        messages=messages,
        user_context=user_ctx,
        session_id="test-session-acc",
        accumulator=accumulator,
    ):
        results.append(item)

    # Accumulator must have received all 3 chunks — including the reviewer's.
    assert len(add_calls) == 3, (
        f"Expected 3 accumulator.add_stream_chunk calls (worker+reviewer+worker), got {len(add_calls)}"
    )
    assert add_calls[1] is reviewer_chunk, "Reviewer chunk must feed the accumulator"

    # User-visible text must NOT include the reviewer's text.
    text_items = [t for ch, t, a in results if ch == "text"]
    combined = "".join(text_items)
    assert "Needs more context" not in combined, "Reviewer text must not appear in stream output"
    assert "Worker answer" in combined or "Revised answer" in combined
