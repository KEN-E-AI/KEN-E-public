"""Unit tests for GET /conversations/{session_id}/todos (CH-41).

Tests cover:
- 404 when find_session_for_user returns None.
- 200 with empty list when ADK session has no todo_lists key.
- 200 with sorted/validated lists when state has valid + malformed entries.
- 200 with empty list when ADK get_session raises an exception.
- WEAVE_AVAILABLE is patched to False to skip telemetry.

References: CH-PRD-05 §6, §7 AC-5.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from fastapi import HTTPException
from src.kene_api.auth.models import UserContext
from src.kene_api.models.chat import ChatSessionMetadata, ListTodosResponse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _make_adk_session(state: dict) -> MagicMock:
    sess = MagicMock()
    sess.state = state
    return sess


def _make_session_service(
    state: dict | None = None,
    *,
    raises: Exception | None = None,
) -> MagicMock:
    svc = MagicMock()
    if raises is not None:
        svc.get_session = AsyncMock(side_effect=raises)
    else:
        session = _make_adk_session(state if state is not None else {})
        svc.get_session = AsyncMock(return_value=session)
    return svc


def _valid_raw(
    list_id: str = "list_001",
    title: str = "My List",
    is_current: bool = False,
    created_at: str = "2026-04-01T10:00:00Z",
) -> dict:
    return {
        "list_id": list_id,
        "title": title,
        "is_current": is_current,
        "created_at": created_at,
        "items": [],
    }


def _run_handler(
    session_id: str = "sess_1",
    meta: ChatSessionMetadata | None = None,
    session_service: MagicMock | None = None,
    user_id: str = "user_1",
) -> ListTodosResponse:
    """Run get_session_todos with patched dependencies."""
    from src.kene_api.routers import chat as chat_module

    fake_svc = MagicMock()
    fake_svc.find_session_for_user.return_value = meta

    _session_service = session_service or _make_session_service(state={})

    user_ctx = _make_user_context(user_id=user_id)

    async def _call() -> ListTodosResponse:
        with (
            patch.object(
                chat_module, "get_chat_side_table_service", return_value=fake_svc
            ),
            patch.object(chat_module, "WEAVE_AVAILABLE", False),
            patch.object(
                type(chat_module.agent_client),
                "session_service",
                new_callable=PropertyMock,
                return_value=_session_service,
            ),
        ):
            from src.kene_api.routers.chat import get_session_todos

            return await get_session_todos(
                session_id=session_id,
                user_context=user_ctx,
            )

    return asyncio.run(_call())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetSessionTodos:
    def test_404_when_session_not_found(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _run_handler(session_id="sess_missing", meta=None)
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Conversation not found"

    def test_200_empty_list_when_no_todo_lists_key(self) -> None:
        meta = _make_meta()
        svc = _make_session_service(state={})
        resp = _run_handler(meta=meta, session_service=svc)
        assert isinstance(resp, ListTodosResponse)
        assert resp.todo_lists == []

    def test_200_sorted_validated_lists(self) -> None:
        meta = _make_meta()
        state = {
            "todo_lists": {
                "current": _valid_raw(
                    list_id="current",
                    title="Current",
                    is_current=True,
                    created_at="2026-02-01T00:00:00Z",
                ),
                "old": _valid_raw(
                    list_id="old",
                    title="Old",
                    is_current=False,
                    created_at="2026-01-01T00:00:00Z",
                ),
                "recent": _valid_raw(
                    list_id="recent",
                    title="Recent",
                    is_current=False,
                    created_at="2026-03-01T00:00:00Z",
                ),
                "bad": {"nope": 1},
            }
        }
        svc = _make_session_service(state=state)
        resp = _run_handler(meta=meta, session_service=svc)
        assert len(resp.todo_lists) == 3
        assert resp.todo_lists[0].list_id == "current"
        assert resp.todo_lists[1].list_id == "recent"
        assert resp.todo_lists[2].list_id == "old"

    def test_200_empty_list_when_adk_get_session_raises(self) -> None:
        meta = _make_meta()
        svc = _make_session_service(raises=RuntimeError("ADK down"))
        resp = _run_handler(meta=meta, session_service=svc)
        assert isinstance(resp, ListTodosResponse)
        assert resp.todo_lists == []

    def test_200_empty_list_when_todo_lists_is_not_dict(self) -> None:
        meta = _make_meta()
        svc = _make_session_service(state={"todo_lists": ["not", "a", "dict"]})
        resp = _run_handler(meta=meta, session_service=svc)
        assert resp.todo_lists == []

    def test_response_model_is_list_todos_response(self) -> None:
        meta = _make_meta()
        svc = _make_session_service(state={})
        resp = _run_handler(meta=meta, session_service=svc)
        assert isinstance(resp, ListTodosResponse)
        assert hasattr(resp, "todo_lists")
