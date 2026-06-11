"""Unit tests for GET /conversations/{session_id}/history (CH-76).

Tests cover:
- 404 (ownership-gate) when resolve_session_for_user returns None.
- 200 with formatted history when the session is owned and ADK returns events.
- 500 passthrough when the inner ADK formatting call raises a non-HTTP exception.
- 404 (inner fallback) when ownership passes but ADK history fetch returns None.
- 500 passthrough when resolve_session_for_user itself raises an unexpected exception.

The outer 404 uses detail "Conversation not found" (matching sibling endpoints).
The inner 404 uses detail "Conversation history not found" (distinct so logs can
distinguish ownership denial from history-fetch failure — Decision-2 in CH-76
implementation plan).

References: CH-76 issue body §Acceptance Criteria.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from fastapi import HTTPException
from src.kene_api.auth.models import UserContext
from src.kene_api.models.chat import ChatSessionMetadata

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SENTINEL = object()


def _make_user_context(user_id: str = "user_1") -> UserContext:
    return UserContext(
        user_id=user_id,
        email="user@example.com",
        organization_permissions={},
        account_permissions={},
    )


def _make_meta(
    *,
    session_id: str = "sess_1",
    user_id: str = "user_1",
    account_id: str = "acc_1",
    organization_id: str = "org_1",
) -> ChatSessionMetadata:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return ChatSessionMetadata(
        session_id=session_id,
        user_id=user_id,
        account_id=account_id,
        organization_id=organization_id,
        model_id="gemini-2.5-flash",
        created_at=now,
        updated_at=now,
    )


def _make_formatted_history(session_id: str = "sess_1") -> dict:
    return {
        "session_id": session_id,
        "events": [
            {
                "content": {"parts": [{"text": "Hello from agent"}]},
                "role": "model",
                "timestamp": 1780054954.0,
            }
        ],
    }


def _run_handler(
    session_id: str = "sess_1",
    meta: ChatSessionMetadata | None = None,
    history_return: object = _SENTINEL,
    history_raises: Exception | None = None,
    resolve_raises: Exception | None = None,
    user_id: str = "user_1",
) -> dict:
    """Run get_conversation_history with patched dependencies.

    ``meta`` is what ``resolve_session_for_user`` returns — None exercises the
    ownership-gate 404 path, a ChatSessionMetadata instance for the 200+ path.
    ``history_return`` is what ``agent_client.get_conversation_history`` returns.
    ``history_raises`` is an exception to raise from the inner ADK call.
    ``resolve_raises`` is an exception to raise from resolve_session_for_user itself.
    """
    from src.kene_api.routers import chat as chat_module

    fake_svc = MagicMock()
    if resolve_raises is not None:
        fake_svc.resolve_session_for_user = AsyncMock(side_effect=resolve_raises)
    else:
        fake_svc.resolve_session_for_user = AsyncMock(return_value=meta)

    # Mock the session_service property on agent_client (needed by resolve_session_for_user).
    fake_session_service = MagicMock()

    user_ctx = _make_user_context(user_id=user_id)

    # Compute the default history return value fresh each call to avoid sharing
    # mutable state across tests (mutable-default-argument guard).
    _history_return = _make_formatted_history() if history_return is _SENTINEL else history_return

    async def _call() -> dict:
        with (
            patch.object(
                chat_module, "get_chat_side_table_service", return_value=fake_svc
            ),
            patch.object(chat_module, "WEAVE_AVAILABLE", False),
            patch.object(
                type(chat_module.agent_client),
                "session_service",
                new_callable=PropertyMock,
                return_value=fake_session_service,
            ),
        ):
            if history_raises is not None:
                chat_module.agent_client.get_conversation_history = AsyncMock(
                    side_effect=history_raises
                )
            else:
                chat_module.agent_client.get_conversation_history = AsyncMock(
                    return_value=_history_return
                )
            from src.kene_api.routers.chat import get_conversation_history

            return await get_conversation_history(
                session_id=session_id,
                user_context=user_ctx,
            )

    return asyncio.run(_call())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetConversationHistory:
    def test_404_when_session_not_found(self) -> None:
        """Ownership gate: resolve_session_for_user returning None → 404 "Conversation not found"."""
        with pytest.raises(HTTPException) as exc_info:
            _run_handler(session_id="sess_missing", meta=None)
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Conversation not found"

    def test_200_when_session_owned(self) -> None:
        """Happy path: meta present, ADK returns formatted events → 200 with history dict."""
        meta = _make_meta()
        expected = _make_formatted_history()
        assert _run_handler(meta=meta, history_return=expected) == expected

    def test_500_passthrough_on_inner_exception(self) -> None:
        """Inner ADK call raising a non-HTTP exception → 500 (not rewrapped as 404)."""
        meta = _make_meta()
        with pytest.raises(HTTPException) as exc_info:
            _run_handler(
                meta=meta,
                history_raises=RuntimeError("ADK transient error"),
            )
        assert exc_info.value.status_code == 500
        assert "Failed to get conversation history" in exc_info.value.detail

    def test_inner_404_when_history_is_none(self) -> None:
        """Ownership passes but inner history fetch returns None → 404 with distinct
        "Conversation history not found" detail (Decision-2: keeps log differentiation
        between ownership denial and history-fetch failure)."""
        meta = _make_meta()
        with pytest.raises(HTTPException) as exc_info:
            _run_handler(meta=meta, history_return=None)
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Conversation history not found"

    def test_500_when_resolve_session_for_user_raises(self) -> None:
        """Unexpected exception from the ownership gate → 500 (not swallowed silently)."""
        with pytest.raises(HTTPException) as exc_info:
            _run_handler(
                meta=None,
                resolve_raises=RuntimeError("Firestore I/O error"),
            )
        assert exc_info.value.status_code == 500
        assert "Failed to get conversation history" in exc_info.value.detail
