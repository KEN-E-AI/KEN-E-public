"""Integration tests for reviewer-author filter on the non-streaming path (CH-68).

Tests drive a synthetic ``worker → reviewer → revised_worker`` chunk sequence
through ``AgentEngineClient.chat_completion()`` and assert the reviewer-authored
text never appears in the returned response string.

References: CH-68 Implementation Plan Task 3.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from kene_api.auth.models import UserContext
from kene_api.routers.chat import AgentEngineClient, ChatMessage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_dict_chunk(text: str, author: str) -> dict:
    """Build a chunk that mirrors the ``{'content': {'parts': [{'text': ...}]}}`` shape."""
    return {
        "author": author,
        "content": {"parts": [{"text": text}]},
    }


def _make_obj_chunk(text: str, author: str) -> SimpleNamespace:
    """Build an ADK ``Event``-like object chunk exposing ``.content`` and ``.author``.

    Drives the ``elif hasattr(chunk, "content")`` branch of the non-streaming
    assembler (neither ``dict`` nor ``str``), where the reviewer guard reads
    ``getattr(chunk, "author", None)``.
    """
    return SimpleNamespace(content=text, author=author)


def _make_client_with_chunks(chunks: list) -> AgentEngineClient:
    """Return an ``AgentEngineClient`` whose ``stream_query`` yields *chunks*."""
    mock_engine = MagicMock()

    def mock_stream_query(message: str, user_id: str, session_id: str):
        yield from chunks

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
        return client


def _make_user_context() -> UserContext:
    return UserContext(
        user_id="test-user-123",
        email="test@example.com",
        organization_permissions={},
        account_permissions={},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reviewer_text_absent_in_non_streaming():
    """Worker→reviewer→revised-worker: reviewer text absent from returned response."""
    chunks = [
        _make_dict_chunk("First draft: 65 active users.", "ga_worker"),
        _make_dict_chunk("The absolute date range is missing.", "ga_review_reviewer"),
        _make_dict_chunk("Revised: 65 users from Oct 19-25.", "ga_worker"),
    ]
    client = _make_client_with_chunks(chunks)

    messages = [ChatMessage(role="user", content="How many users?", timestamp="")]
    response, _session_id = await client.chat_completion(
        messages=messages, user_context=_make_user_context(), session_id="test-session"
    )

    assert response is not None
    assert "absolute date range is missing" not in response, (
        "Reviewer critique must not appear in non-streaming response"
    )
    # CH-69: only the final (revised) worker draft appears.
    assert "Revised" in response, "Final worker draft must be present"
    assert "First draft" not in response, "Intermediate draft must be suppressed (CH-69)"


@pytest.mark.asyncio
async def test_non_streaming_only_reviewer_chunk_returns_empty_or_stripped():
    """A turn where only a reviewer chunk arrives results in empty/whitespace response."""
    chunks = [
        _make_dict_chunk("Needs more detail.", "ga_review_reviewer"),
    ]
    client = _make_client_with_chunks(chunks)

    messages = [ChatMessage(role="user", content="Anything?", timestamp="")]
    response, _session_id = await client.chat_completion(
        messages=messages, user_context=_make_user_context(), session_id="test-session-2"
    )

    # Response should be empty (reviewer text suppressed) or a fallback message.
    # We don't assert empty string because the router has a "no response" fallback,
    # but the reviewer text itself must be absent.
    assert "Needs more detail" not in (response or ""), (
        "Reviewer-only turn must not surface reviewer text"
    )


@pytest.mark.asyncio
async def test_non_reviewer_author_unaffected():
    """A plain ``model`` author is not filtered."""
    chunks = [
        _make_dict_chunk("Hello, I can help with that.", "model"),
    ]
    client = _make_client_with_chunks(chunks)

    messages = [ChatMessage(role="user", content="Hello?", timestamp="")]
    response, _session_id = await client.chat_completion(
        messages=messages, user_context=_make_user_context(), session_id="test-session-3"
    )

    assert response is not None
    assert "Hello, I can help with that." in response


@pytest.mark.asyncio
async def test_multiple_reviewer_agents_all_suppressed():
    """Multiple distinct reviewer authors in one turn are all suppressed."""
    chunks = [
        _make_dict_chunk("Worker text A.", "task1_worker"),
        _make_dict_chunk("Critique A.", "task1_reviewer"),
        _make_dict_chunk("Worker text B.", "task2_worker"),
        _make_dict_chunk("Critique B.", "task2_reviewer"),
        _make_dict_chunk("Synthesized answer.", "coordinator"),
    ]
    client = _make_client_with_chunks(chunks)

    messages = [ChatMessage(role="user", content="Multi-task?", timestamp="")]
    response, _session_id = await client.chat_completion(
        messages=messages, user_context=_make_user_context(), session_id="test-session-4"
    )

    assert "Critique A" not in (response or "")
    assert "Critique B" not in (response or "")
    # Non-reviewer chunks are present
    assert "Worker text A" in (response or "") or "Synthesized answer" in (response or "")


@pytest.mark.asyncio
async def test_string_chunks_unaffected_by_reviewer_filter():
    """String chunks (no ``author`` field) pass through unchanged — back-compat guard."""
    # String chunks cannot carry an author field; they should never be filtered.
    # The non-streaming path's ``isinstance(chunk, str)`` branch is intentionally
    # unfiltered (D6 decision in CH-68 Implementation Plan).

    mock_engine = MagicMock()

    def mock_stream_query(message: str, user_id: str, session_id: str):
        yield "Plain string response with no author field."

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

    messages = [ChatMessage(role="user", content="Anything?", timestamp="")]
    response, _session_id = await client.chat_completion(
        messages=messages, user_context=_make_user_context(), session_id="test-session-5"
    )

    assert response is not None
    assert "Plain string response" in response


@pytest.mark.asyncio
async def test_object_chunk_reviewer_suppressed_worker_kept():
    """Object chunks (ADK ``Event``-like) honour the reviewer guard; worker text kept.

    Covers the ``elif hasattr(chunk, "content")`` branch of the non-streaming
    assembler — neither ``dict`` nor ``str`` — where the reviewer guard reads
    ``getattr(chunk, "author", None)``.
    """
    chunks = [
        _make_obj_chunk("Worker object answer.", "ga_worker"),
        _make_obj_chunk("Reviewer object critique.", "ga_review_reviewer"),
    ]
    client = _make_client_with_chunks(chunks)

    messages = [ChatMessage(role="user", content="Object path?", timestamp="")]
    response, _session_id = await client.chat_completion(
        messages=messages, user_context=_make_user_context(), session_id="test-session-obj"
    )

    assert response is not None
    assert "Reviewer object critique" not in response, (
        "Reviewer object-chunk must not appear in non-streaming response"
    )
    assert "Worker object answer" in response
