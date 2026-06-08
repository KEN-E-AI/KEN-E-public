"""Integration tests for ChatResponse.artifacts field and atomic SSE artifacts event.

Covers AH-132 acceptance criteria:
- AC-1: response_artifacts extracted + cleared from session state after run.
- AC-2: artifacts=None/omitted when no charts produced; legacy clients unaffected.
- AC-3: SSE frame ordering — messageXN -> event:artifacts -> data:[DONE].

Tests monkey-patch agent_client.stream_chat_completion (for SSE paths) and
AgentEngineClient._extract_and_clear_response_artifacts (for wiring tests), plus
session_service.get_session / append_event (for the helper unit tests).  No real
Vertex AI calls are made.

References: AH-PRD-04 §7.3, §6.2; AH-132 Implementation Plan Task 5.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from kene_api.routers.chat import (
    AgentEngineClient,
    ChatResponse,
    _stream_completion_sse,
)

from shared.artifact_models import Artifact, ArtifactMetadata

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_artifact(**overrides: Any) -> Artifact:
    """Build a minimal valid Artifact."""
    return Artifact(
        type="visualization",
        spec={
            "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
            "mark": "line",
            "encoding": {"x": {"field": "date"}, "y": {"field": "sessions"}},
            "data": {"values": [{"date": "2024-01-01", "sessions": 100}]},
        },
        metadata=ArtifactMetadata(
            chart_type_suggestion="line",
            title=overrides.pop("title", "Test Chart"),
            data_source="google_analytics",
        ),
    )


def _artifact_dict(**overrides: Any) -> dict[str, Any]:
    return _make_artifact(**overrides).model_dump(mode="json")


async def _collect_sse(gen) -> list[str]:
    """Collect all SSE frames from an async generator into a list."""
    frames: list[str] = []
    async for frame in gen:
        frames.append(frame)
    return frames


def _make_user_context(user_id: str = "test-user") -> MagicMock:
    ctx = MagicMock()
    ctx.user_id = user_id
    ctx.has_account_access = MagicMock(return_value=True)
    return ctx


# ---------------------------------------------------------------------------
# Test 1 — ChatResponse serialisation
# ---------------------------------------------------------------------------


def test_chat_response_serialization_without_artifacts():
    """ChatResponse with no artifacts serialises artifacts as null."""
    resp = ChatResponse(content="hello", session_id="s1")
    data = json.loads(resp.model_dump_json())
    assert data["content"] == "hello"
    assert data["artifacts"] is None


def test_chat_response_serialization_with_artifacts():
    """ChatResponse with one Artifact round-trips through model_dump_json."""
    artifact = _make_artifact()
    resp = ChatResponse(content="hi", session_id="s1", artifacts=[artifact])
    data = json.loads(resp.model_dump_json())
    assert len(data["artifacts"]) == 1
    assert data["artifacts"][0]["type"] == "visualization"
    assert data["artifacts"][0]["metadata"]["chart_type_suggestion"] == "line"


# ---------------------------------------------------------------------------
# Test 2 — _extract_and_clear_response_artifacts helper
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_helper_validates_and_clears():
    """Helper returns valid Artifacts, skips malformed, calls append_event once."""
    valid_dict = _artifact_dict()
    malformed_dict = {"type": "visualization", "spec": "not-a-dict", "metadata": {}}

    mock_session = MagicMock()
    mock_session.state = {"response_artifacts": [valid_dict, valid_dict, malformed_dict]}

    mock_session_service = AsyncMock()
    mock_session_service.get_session = AsyncMock(return_value=mock_session)
    mock_session_service.append_event = AsyncMock()

    client = AgentEngineClient.__new__(AgentEngineClient)
    client._session_service = mock_session_service

    result = await client._extract_and_clear_response_artifacts("user-1", "sess-1")

    assert len(result) == 2
    assert all(isinstance(a, Artifact) for a in result)
    # append_event called exactly once to clear the slot
    mock_session_service.append_event.assert_awaited_once()
    call_args = mock_session_service.append_event.await_args[0]
    event = call_args[1]
    assert event.actions.state_delta == {"response_artifacts": []}


@pytest.mark.asyncio
async def test_extract_helper_returns_empty_when_no_session():
    """Helper returns [] when get_session returns None."""
    mock_session_service = AsyncMock()
    mock_session_service.get_session = AsyncMock(return_value=None)
    mock_session_service.append_event = AsyncMock()

    client = AgentEngineClient.__new__(AgentEngineClient)
    client._session_service = mock_session_service

    result = await client._extract_and_clear_response_artifacts("user-1", "sess-x")
    assert result == []
    mock_session_service.append_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_helper_returns_empty_on_get_session_exception():
    """Helper returns [] (best-effort) when get_session raises."""
    mock_session_service = AsyncMock()
    mock_session_service.get_session = AsyncMock(
        side_effect=RuntimeError("Vertex error")
    )

    client = AgentEngineClient.__new__(AgentEngineClient)
    client._session_service = mock_session_service

    result = await client._extract_and_clear_response_artifacts("user-1", "sess-err")
    assert result == []


@pytest.mark.asyncio
async def test_extract_helper_returns_artifacts_when_append_event_fails():
    """Valid artifacts are returned even when the clear step (append_event) fails.

    Ensures a transient Vertex error on the clear step does not silently drop
    already-validated artifacts from the current response (AC-1 sub-case).
    """
    valid_dict = _artifact_dict()

    mock_session = MagicMock()
    mock_session.state = {"response_artifacts": [valid_dict]}

    mock_session_service = AsyncMock()
    mock_session_service.get_session = AsyncMock(return_value=mock_session)
    mock_session_service.append_event = AsyncMock(
        side_effect=RuntimeError("Vertex transient error")
    )

    client = AgentEngineClient.__new__(AgentEngineClient)
    client._session_service = mock_session_service

    result = await client._extract_and_clear_response_artifacts("user-1", "sess-clear-fail")

    # Artifacts still returned despite clear failure
    assert len(result) == 1
    assert isinstance(result[0], Artifact)
    # Clear was attempted exactly once
    mock_session_service.append_event.assert_awaited_once()


# ---------------------------------------------------------------------------
# Test 3 — non-streaming chat_completion wiring
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_streaming_emits_artifacts():
    """chat_completion endpoint populates ChatResponse.artifacts when helper returns Artifacts.

    AH-157: chat_completion now returns a 3-tuple (content, session_id, visualization_seen).
    When visualization_seen=True, the endpoint calls _extract_and_clear_response_artifacts.
    """
    artifact = _make_artifact()

    with (
        patch(
            "kene_api.routers.chat.agent_client.chat_completion",
            new_callable=AsyncMock,
            return_value=("hello", "real-sess", True),  # AH-157: visualization_seen=True
        ),
        patch(
            "kene_api.routers.chat.agent_client._extract_and_clear_response_artifacts",
            new_callable=AsyncMock,
            return_value=[artifact],
        ) as mock_extract,
        patch("kene_api.routers.chat._maybe_set_temp_title", new_callable=AsyncMock),
        patch("kene_api.routers.chat._post_response_writes", new_callable=AsyncMock, create=True),
        patch("kene_api.routers.chat._background_tasks", set()),
        patch("kene_api.routers.chat._reauth_cache", {}),
        patch("kene_api.routers.chat._get_firestore_client", return_value=MagicMock()),
    ):
        # Import the router handler directly
        from kene_api.routers import chat as chat_module

        # Build a minimal fake request
        request = MagicMock()
        request.stream = False
        request.messages = [MagicMock(content="hello")]
        request.session_id = "sess-1"
        request.conversation_name = None
        request.account_id = "acc-1"

        user_context = _make_user_context()

        response = await chat_module.chat_completion(request, user_context)

    assert isinstance(response, ChatResponse)
    assert response.artifacts == [artifact]
    mock_extract.assert_awaited_once_with("test-user", "real-sess")


@pytest.mark.asyncio
async def test_non_streaming_artifacts_none_when_empty():
    """chat_completion sets artifacts=None when helper returns [].

    AH-157: chat_completion now returns a 3-tuple. When visualization_seen=False,
    _extract_and_clear_response_artifacts is NOT called at all.
    """
    mock_extract = AsyncMock(return_value=[])

    with (
        patch(
            "kene_api.routers.chat.agent_client.chat_completion",
            new_callable=AsyncMock,
            return_value=("hello", "real-sess", False),  # AH-157: visualization_seen=False
        ),
        patch(
            "kene_api.routers.chat.agent_client._extract_and_clear_response_artifacts",
            mock_extract,
        ),
        patch("kene_api.routers.chat._maybe_set_temp_title", new_callable=AsyncMock),
        patch("kene_api.routers.chat._background_tasks", set()),
        patch("kene_api.routers.chat._reauth_cache", {}),
        patch("kene_api.routers.chat._get_firestore_client", return_value=MagicMock()),
    ):
        from kene_api.routers import chat as chat_module

        request = MagicMock()
        request.stream = False
        request.messages = [MagicMock(content="hi")]
        request.session_id = "sess-2"
        request.conversation_name = None
        request.account_id = "acc-1"

        response = await chat_module.chat_completion(request, _make_user_context())

    assert isinstance(response, ChatResponse)
    assert response.artifacts is None
    # AH-157: no visualization → extractor must NOT be called
    mock_extract.assert_not_awaited()


# ---------------------------------------------------------------------------
# Test 4 — SSE event ordering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sse_event_ordering_with_artifacts():
    """SSE frame order: data:<text>xN -> event:artifacts -> data:[DONE].

    AH-157: the fake stream now yields the ("tool_call", "create_visualization", "model")
    sentinel so _visualization_seen=True and the extractor is called.
    """
    artifact = _make_artifact()

    async def fake_stream(**kwargs):
        # AH-157: yield the sentinel first (before or during text — order within
        # turn doesn't matter; what matters is it arrives before end-of-stream).
        yield ("tool_call", "create_visualization", "model")
        for text in ("Hello", " world", "!"):
            yield ("text", text, "model")

    with (
        patch(
            "kene_api.routers.chat.agent_client.stream_chat_completion",
            side_effect=fake_stream,
        ),
        patch(
            "kene_api.routers.chat.agent_client._extract_and_clear_response_artifacts",
            new_callable=AsyncMock,
            return_value=[artifact],
        ),
        patch("kene_api.routers.chat._flush_stream_turn", new_callable=AsyncMock),
        patch("kene_api.routers.chat._maybe_set_temp_title", new_callable=AsyncMock),
    ):
        frames = await _collect_sse(
            _stream_completion_sse(
                messages=[],
                user_context=_make_user_context(),
                session_id="sess-sse",
                conversation_name=None,
                account_id="acc-1",
                turn_uuid="turn-1",
            )
        )

    # Three text frames, then artifacts, then DONE
    text_frames = [f for f in frames if f.startswith("data:") and "[DONE]" not in f]
    artifacts_frames = [f for f in frames if "event: artifacts" in f]
    done_frames = [f for f in frames if "[DONE]" in f]

    assert len(text_frames) == 3
    assert len(artifacts_frames) == 1
    assert len(done_frames) == 1

    # Ordering: last text frame index < artifacts frame index < DONE frame index
    last_text_idx = max(frames.index(f) for f in text_frames)
    artifacts_idx = frames.index(artifacts_frames[0])
    done_idx = frames.index(done_frames[0])
    assert last_text_idx < artifacts_idx < done_idx

    # Payload is valid JSON with an "artifacts" list
    data_line = next(
        line for line in artifacts_frames[0].splitlines() if line.startswith("data: ")
    )
    payload = json.loads(data_line[len("data: "):])
    assert "artifacts" in payload
    assert len(payload["artifacts"]) == 1
    assert payload["artifacts"][0]["type"] == "visualization"


# ---------------------------------------------------------------------------
# Test 5 — SSE no-artifacts omits the frame
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sse_no_artifacts_omits_frame():
    """When no tool_call sentinel is emitted, no event:artifacts frame appears.

    AH-157: _extract_and_clear_response_artifacts must NOT be called when
    _visualization_seen=False (no create_visualization sentinel in the stream).
    """
    mock_extract = AsyncMock(return_value=[])

    async def fake_stream(**kwargs):
        # No ("tool_call", "create_visualization", ...) sentinel — plain text only.
        yield ("text", "plain text", "model")

    with (
        patch(
            "kene_api.routers.chat.agent_client.stream_chat_completion",
            side_effect=fake_stream,
        ),
        patch(
            "kene_api.routers.chat.agent_client._extract_and_clear_response_artifacts",
            mock_extract,
        ),
        patch("kene_api.routers.chat._flush_stream_turn", new_callable=AsyncMock),
        patch("kene_api.routers.chat._maybe_set_temp_title", new_callable=AsyncMock),
    ):
        frames = await _collect_sse(
            _stream_completion_sse(
                messages=[],
                user_context=_make_user_context(),
                session_id="sess-noart",
                conversation_name=None,
                account_id="acc-1",
                turn_uuid="turn-2",
            )
        )

    joined = "".join(frames)
    assert "event: artifacts" not in joined
    assert "data: [DONE]" in joined
    # AH-157: no sentinel → extractor must NOT be called
    mock_extract.assert_not_awaited()


# ---------------------------------------------------------------------------
# Test 6 — SSE cancellation skips artifact extraction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sse_cancellation_skips_artifacts():
    """On GeneratorExit/CancelledError the artifact helper is NOT called."""
    import asyncio

    async def fake_stream_raises(**kwargs):
        yield ("text", "partial", "model")
        raise asyncio.CancelledError()

    mock_extract = AsyncMock(return_value=[_make_artifact()])

    with (
        patch(
            "kene_api.routers.chat.agent_client.stream_chat_completion",
            side_effect=fake_stream_raises,
        ),
        patch(
            "kene_api.routers.chat.agent_client._extract_and_clear_response_artifacts",
            mock_extract,
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
        with pytest.raises((asyncio.CancelledError, GeneratorExit, Exception)):
            async for _ in gen:
                pass

    mock_extract.assert_not_awaited()


# ---------------------------------------------------------------------------
# Test 7 — SSE session_id=None skips extraction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sse_session_id_none_skips_extraction():
    """When session_id=None and no session frame arrives, extraction is skipped.

    A new-conversation turn starts with session_id=None and resolved_session_id
    stays None if no 'session' channel event is emitted by the stream.  In that
    case _extract_and_clear_response_artifacts must not be called (no session
    exists yet to read from) and no event:artifacts frame appears in the output.
    """
    mock_extract = AsyncMock(return_value=[_make_artifact()])

    async def fake_stream_no_session_event(**kwargs):
        # Stream text without ever emitting a 'session' channel frame
        yield ("text", "hi", "model")

    with (
        patch(
            "kene_api.routers.chat.agent_client.stream_chat_completion",
            side_effect=fake_stream_no_session_event,
        ),
        patch(
            "kene_api.routers.chat.agent_client._extract_and_clear_response_artifacts",
            mock_extract,
        ),
        patch("kene_api.routers.chat._flush_stream_turn", new_callable=AsyncMock),
        patch("kene_api.routers.chat._maybe_set_temp_title", new_callable=AsyncMock),
    ):
        frames = await _collect_sse(
            _stream_completion_sse(
                messages=[],
                user_context=_make_user_context(),
                session_id=None,
                conversation_name=None,
                account_id="acc-1",
                turn_uuid="turn-no-sess",
            )
        )

    mock_extract.assert_not_awaited()
    joined = "".join(frames)
    assert "event: artifacts" not in joined
    assert "data: [DONE]" in joined


# ---------------------------------------------------------------------------
# AH-157 — gating tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sse_no_visualization_tool_call_skips_extraction():
    """SSE: when no tool_call sentinel appears, extractor is skipped entirely.

    Distinct from test_sse_no_artifacts_omits_frame in that this test explicitly
    checks the _extract_and_clear_response_artifacts call count (not just the
    frame output), confirming the Vertex AI round-trip is avoided.
    """
    mock_extract = AsyncMock(return_value=[])

    async def fake_stream_text_only(**kwargs):
        yield ("text", "plain response", "model")

    with (
        patch(
            "kene_api.routers.chat.agent_client.stream_chat_completion",
            side_effect=fake_stream_text_only,
        ),
        patch(
            "kene_api.routers.chat.agent_client._extract_and_clear_response_artifacts",
            mock_extract,
        ),
        patch("kene_api.routers.chat._flush_stream_turn", new_callable=AsyncMock),
        patch("kene_api.routers.chat._maybe_set_temp_title", new_callable=AsyncMock),
    ):
        frames = await _collect_sse(
            _stream_completion_sse(
                messages=[],
                user_context=_make_user_context(),
                session_id="sess-gate",
                conversation_name=None,
                account_id="acc-1",
                turn_uuid="turn-gate",
            )
        )

    # Extractor must not be called — the Vertex AI get_session round-trip is avoided.
    mock_extract.assert_not_awaited()
    joined = "".join(frames)
    assert "event: artifacts" not in joined


@pytest.mark.asyncio
async def test_non_streaming_no_visualization_skips_extraction():
    """Non-streaming: when visualization_seen=False, extractor is skipped entirely.

    Confirms the Vertex AI get_session round-trip is avoided for plain-text turns.
    """
    mock_extract = AsyncMock(return_value=[])

    with (
        patch(
            "kene_api.routers.chat.agent_client.chat_completion",
            new_callable=AsyncMock,
            return_value=("plain text response", "real-sess", False),
        ),
        patch(
            "kene_api.routers.chat.agent_client._extract_and_clear_response_artifacts",
            mock_extract,
        ),
        patch("kene_api.routers.chat._maybe_set_temp_title", new_callable=AsyncMock),
        patch("kene_api.routers.chat._background_tasks", set()),
        patch("kene_api.routers.chat._reauth_cache", {}),
        patch("kene_api.routers.chat._get_firestore_client", return_value=MagicMock()),
    ):
        from kene_api.routers import chat as chat_module

        request = MagicMock()
        request.stream = False
        request.messages = [MagicMock(content="what is revenue?")]
        request.session_id = "sess-plain"
        request.conversation_name = None
        request.account_id = "acc-1"

        response = await chat_module.chat_completion(request, _make_user_context())

    assert isinstance(response, ChatResponse)
    assert response.artifacts is None
    # AH-157: no visualization → extractor must NOT be called at all
    mock_extract.assert_not_awaited()
