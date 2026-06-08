"""Integration tests for worker-draft collapse on the non-streaming path (CH-69).

Tests drive a synthetic ``worker → reviewer → worker`` chunk sequence through
``AgentEngineClient.chat_completion()`` and assert that only the final approved
worker draft appears in the returned response string.

References: CH-69 Implementation Plan Task 3, Task 4.
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
    return {"author": author, "content": {"parts": [{"text": text}]}}


def _make_obj_chunk(text: str, author: str) -> SimpleNamespace:
    return SimpleNamespace(content=text, author=author)


def _make_client_with_chunks(chunks: list) -> AgentEngineClient:
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
# AC-1: 3-iteration loop — only final draft returned
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_three_iteration_loop_only_final_draft_returned():
    """A 3-iteration review loop returns only draft 3 (the approved one)."""
    chunks = [
        _make_dict_chunk("Draft 1: relative date range.", "ga_worker"),
        _make_dict_chunk("Reject: use absolute dates.", "ga_review_reviewer"),
        _make_dict_chunk("Draft 2: 2024-01-16 to 2024-01-22.", "ga_worker"),
        _make_dict_chunk("Reject: formula missing.", "ga_review_reviewer"),
        _make_dict_chunk("Draft 3: final approved answer.", "ga_worker"),
    ]
    client = _make_client_with_chunks(chunks)

    messages = [ChatMessage(role="user", content="How many users?", timestamp="")]
    response, _, _ = await client.chat_completion(
        messages=messages, user_context=_make_user_context(), session_id="s1"
    )

    assert response is not None
    assert "Draft 1" not in response, "Draft 1 must be suppressed"
    assert "Draft 2" not in response, "Draft 2 must be suppressed"
    assert "Draft 3" in response, "Final draft 3 must appear"
    assert "Reject:" not in response


# ---------------------------------------------------------------------------
# AC-2: single-iteration loop — the worker draft is returned
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_iteration_loop_draft_returned():
    """A single-iteration loop (worker → reviewer → end) returns the worker draft."""
    chunks = [
        _make_dict_chunk("Only draft: 42 sessions.", "ga_worker"),
        _make_dict_chunk("Approved.", "ga_review_reviewer"),
    ]
    client = _make_client_with_chunks(chunks)

    messages = [ChatMessage(role="user", content="Sessions?", timestamp="")]
    response, _, _ = await client.chat_completion(
        messages=messages, user_context=_make_user_context(), session_id="s2"
    )

    assert response is not None
    assert "Only draft" in response


# ---------------------------------------------------------------------------
# AC-3: single-author model-only response — byte-for-byte unchanged
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_model_only_response_unchanged():
    """A plain ``model`` response (no review loop) is not affected."""
    chunks = [
        _make_dict_chunk("Hello, I can help.", "model"),
        _make_dict_chunk(" Here is the answer.", "model"),
    ]
    client = _make_client_with_chunks(chunks)

    messages = [ChatMessage(role="user", content="Hi.", timestamp="")]
    response, _, _ = await client.chat_completion(
        messages=messages, user_context=_make_user_context(), session_id="s3"
    )

    assert response is not None
    assert "Hello, I can help." in response
    assert "Here is the answer." in response


# ---------------------------------------------------------------------------
# AC-4: AH-PRD-05 multi-task — each specialist's final draft appears
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multi_task_each_final_draft_present():
    """Two sequential specialists, each with 2 iterations; both final drafts present."""
    chunks = [
        _make_dict_chunk("A draft 1.", "specialist_a_worker"),
        _make_dict_chunk("Reject A.", "specialist_a_review_reviewer"),
        _make_dict_chunk("A draft 2 (final).", "specialist_a_worker"),
        _make_dict_chunk("B draft 1.", "specialist_b_worker"),
        _make_dict_chunk("Reject B.", "specialist_b_review_reviewer"),
        _make_dict_chunk("B draft 2 (final).", "specialist_b_worker"),
    ]
    client = _make_client_with_chunks(chunks)

    messages = [ChatMessage(role="user", content="Multi?", timestamp="")]
    response, _, _ = await client.chat_completion(
        messages=messages, user_context=_make_user_context(), session_id="s4"
    )

    assert response is not None
    assert "A draft 1" not in response, "A draft 1 must be suppressed"
    assert "A draft 2 (final)" in response, "Final A draft must appear"
    assert "B draft 1" not in response, "B draft 1 must be suppressed"
    assert "B draft 2 (final)" in response, "Final B draft must appear"


@pytest.mark.asyncio
async def test_fan_out_independent_reviewer_buffers():
    """specialist_a (2 iterations) + specialist_b (1 iteration): A's reviewer
    must not clear B's buffer."""
    chunks = [
        _make_dict_chunk("A draft 1.", "specialist_a_worker"),
        _make_dict_chunk("B draft 1 (final).", "specialist_b_worker"),
        _make_dict_chunk("Reject A.", "specialist_a_review_reviewer"),
        _make_dict_chunk("A draft 2 (final).", "specialist_a_worker"),
    ]
    client = _make_client_with_chunks(chunks)

    messages = [ChatMessage(role="user", content="Fan-out?", timestamp="")]
    response, _, _ = await client.chat_completion(
        messages=messages, user_context=_make_user_context(), session_id="s7"
    )

    assert response is not None
    assert "A draft 1" not in response, "Rejected A draft 1 must be suppressed"
    assert "A draft 2 (final)" in response, "Final A draft must appear"
    assert "B draft 1 (final)" in response, "B single-iteration draft must appear"


# ---------------------------------------------------------------------------
# AC-5: function events and contentless CH-59 events unchanged
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_function_events_and_contentless_events_still_skipped():
    """Function-event parts and contentless dict chunks are still skipped."""
    chunks = [
        {
            "author": "ga_worker",
            "content": {
                "parts": [
                    {"function_call": {"name": "get_data", "args": {}}},
                    {"text": "Worker answer."},
                ]
            },
        },
    ]
    client = _make_client_with_chunks(chunks)

    messages = [ChatMessage(role="user", content="Call?", timestamp="")]
    response, _, _ = await client.chat_completion(
        messages=messages, user_context=_make_user_context(), session_id="s5"
    )

    assert response is not None
    # Worker text should appear; function_call artefact should not.
    assert "Worker answer" in response
    assert "get_data" not in response


# ---------------------------------------------------------------------------
# AC-6: ADK Event object branch honours worker collapse
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_object_chunk_worker_collapse():
    """ADK Event object chunks (``hasattr(chunk, 'content')``) honour the worker
    collapse — a reviewer object event drops the matched worker buffer."""
    chunks = [
        _make_obj_chunk("Worker object draft 1.", "ga_worker"),
        _make_obj_chunk("Reviewer reject.", "ga_review_reviewer"),
        _make_obj_chunk("Worker object draft 2 (final).", "ga_worker"),
    ]
    client = _make_client_with_chunks(chunks)

    messages = [ChatMessage(role="user", content="Object path?", timestamp="")]
    response, _, _ = await client.chat_completion(
        messages=messages, user_context=_make_user_context(), session_id="s6"
    )

    assert response is not None
    assert "Worker object draft 1" not in response, "Object draft 1 must be suppressed"
    assert "Worker object draft 2 (final)" in response, "Final object draft must appear"
    assert "Reviewer reject" not in response
