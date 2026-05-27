"""Unit tests for list_todo_lists service function (CH-41).

References: CH-PRD-05 §4.1, §4.3, §7 AC-5.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from src.kene_api.chat.todos import list_todo_lists

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(state: dict) -> MagicMock:
    sess = MagicMock()
    sess.state = state
    return sess


def _make_service(
    session: MagicMock | None = None, *, raises: Exception | None = None
) -> MagicMock:
    svc = MagicMock()
    if raises is not None:
        svc.get_session = AsyncMock(side_effect=raises)
    else:
        svc.get_session = AsyncMock(return_value=session)
    return svc


def _valid_raw(
    *,
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


def _run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestListTodoListsSessionErrors:
    def test_returns_empty_when_get_session_raises(self) -> None:
        svc = _make_service(raises=RuntimeError("boom"))
        result = _run(
            list_todo_lists(
                session_service=svc,
                app_name="ken_e_chatbot",
                user_id="user_1",
                session_id="sess_1",
            )
        )
        assert result == []

    def test_returns_empty_when_session_is_none(self) -> None:
        svc = _make_service(session=None)
        result = _run(
            list_todo_lists(
                session_service=svc,
                app_name="ken_e_chatbot",
                user_id="user_1",
                session_id="sess_1",
            )
        )
        assert result == []

    def test_returns_empty_when_session_state_is_none(self) -> None:
        sess = MagicMock()
        sess.state = None
        svc = _make_service(session=sess)
        result = _run(
            list_todo_lists(
                session_service=svc,
                app_name="ken_e_chatbot",
                user_id="user_1",
                session_id="sess_1",
            )
        )
        assert result == []


class TestListTodoListsMissingKey:
    def test_returns_empty_when_no_todo_lists_key(self) -> None:
        svc = _make_service(session=_make_session(state={}))
        result = _run(
            list_todo_lists(
                session_service=svc,
                app_name="ken_e_chatbot",
                user_id="user_1",
                session_id="sess_1",
            )
        )
        assert result == []

    def test_returns_empty_when_todo_lists_is_none(self) -> None:
        svc = _make_service(session=_make_session(state={"todo_lists": None}))
        result = _run(
            list_todo_lists(
                session_service=svc,
                app_name="ken_e_chatbot",
                user_id="user_1",
                session_id="sess_1",
            )
        )
        assert result == []

    def test_returns_empty_when_todo_lists_is_a_list(self) -> None:
        svc = _make_service(session=_make_session(state={"todo_lists": []}))
        result = _run(
            list_todo_lists(
                session_service=svc,
                app_name="ken_e_chatbot",
                user_id="user_1",
                session_id="sess_1",
            )
        )
        assert result == []

    def test_returns_empty_when_todo_lists_is_a_string(self) -> None:
        svc = _make_service(session=_make_session(state={"todo_lists": "not_a_dict"}))
        result = _run(
            list_todo_lists(
                session_service=svc,
                app_name="ken_e_chatbot",
                user_id="user_1",
                session_id="sess_1",
            )
        )
        assert result == []


class TestListTodoListsSortOrder:
    def test_is_current_first_then_created_at_desc(self) -> None:
        raw_state = {
            "todo_lists": {
                "list_old_false": _valid_raw(
                    list_id="list_old_false",
                    title="Old False",
                    is_current=False,
                    created_at="2026-01-01T00:00:00Z",
                ),
                "list_current": _valid_raw(
                    list_id="list_current",
                    title="Current",
                    is_current=True,
                    created_at="2026-02-01T00:00:00Z",
                ),
                "list_new_false": _valid_raw(
                    list_id="list_new_false",
                    title="New False",
                    is_current=False,
                    created_at="2026-03-01T00:00:00Z",
                ),
            }
        }
        svc = _make_service(session=_make_session(state=raw_state))
        result = _run(
            list_todo_lists(
                session_service=svc,
                app_name="ken_e_chatbot",
                user_id="user_1",
                session_id="sess_1",
            )
        )
        assert len(result) == 3
        # is_current=True comes first
        assert result[0].list_id == "list_current"
        # then by created_at DESC (newer first)
        assert result[1].list_id == "list_new_false"
        assert result[2].list_id == "list_old_false"

    def test_naive_created_at_does_not_raise(self) -> None:
        """Naive datetime (no tzinfo) is coerced to UTC for sorting without error."""
        # We construct a TodoList directly with a naive datetime
        naive_dt = datetime(2026, 4, 1, 10, 0, 0)  # no tzinfo
        raw_state = {
            "todo_lists": {
                "list_naive": {
                    "list_id": "list_naive",
                    "title": "Naive",
                    "is_current": False,
                    # Pass a naive datetime object — Pydantic will accept it
                    "created_at": naive_dt,
                    "items": [],
                }
            }
        }
        svc = _make_service(session=_make_session(state=raw_state))
        # Should not raise
        result = _run(
            list_todo_lists(
                session_service=svc,
                app_name="ken_e_chatbot",
                user_id="user_1",
                session_id="sess_1",
            )
        )
        assert len(result) == 1
        assert result[0].list_id == "list_naive"


class TestListTodoListsMixedValidity:
    def test_only_valid_entries_returned(self) -> None:
        raw_state = {
            "todo_lists": {
                "good": _valid_raw(list_id="good", title="Good List"),
                "bad_no_title": {"list_id": "bad_no_title"},
                "bad_none": None,
                "bad_wrong_items": {
                    "list_id": "bad_items",
                    "title": "Bad Items",
                    "items": "not_a_list",
                },
            }
        }
        svc = _make_service(session=_make_session(state=raw_state))
        result = _run(
            list_todo_lists(
                session_service=svc,
                app_name="ken_e_chatbot",
                user_id="user_1",
                session_id="sess_1",
            )
        )
        assert len(result) == 1
        assert result[0].list_id == "good"
