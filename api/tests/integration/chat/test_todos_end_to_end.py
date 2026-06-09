"""Integration tests for GET /conversations/{session_id}/todos (CH-41).

Run against the Firestore emulator:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/chat/test_todos_end_to_end.py -v

References: CH-PRD-05 §6, §7 AC-5.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason=(
        "Firestore emulator integration tests skipped by default. "
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 (and GOOGLE_CLOUD_PROJECT_ID=test-project) "
        "to enable. Run `gcloud emulators firestore start --host-port=127.0.0.1:8090`."
    ),
)

_ACCOUNT_ID = "acc_ch41_test"
_SESSION_ID = "sess_ch41_real_001"
_USER_ID = "user_ch41_test"
_ORG_ID = "org_ch41_test"


def _emulator_client() -> Any:
    from google.cloud import firestore as _fs

    project = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")
    return _fs.Client(project=project)


def _seed_session(
    db: Any,
    *,
    session_id: str = _SESSION_ID,
    user_id: str = _USER_ID,
    account_id: str = _ACCOUNT_ID,
    organization_id: str = _ORG_ID,
) -> None:
    """Write a side-table doc directly to the emulator."""
    now = datetime.now(timezone.utc)
    doc = {
        "session_id": session_id,
        "user_id": user_id,
        "account_id": account_id,
        "organization_id": organization_id,
        "model_id": "gemini-2.5-flash",
        "created_at": now,
        "updated_at": now,
        "last_viewed_at": None,
        "deleted_at": None,
    }
    db.document(f"accounts/{account_id}/chat_sessions/{session_id}").set(doc)


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


class TestTodosEndpointIntegration:
    """Integration tests using the Firestore emulator for ownership checks."""

    def setup_method(self) -> None:
        self.db = _emulator_client()
        # Delete any stale doc from a previous run.
        self.db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}").delete()

    def _run_handler(
        self,
        session_id: str = _SESSION_ID,
        user_id: str = _USER_ID,
        session_service: MagicMock | None = None,
    ) -> Any:
        """Run get_session_todos against the real emulator via the side-table service."""
        import asyncio

        from src.kene_api.auth.models import UserContext
        from src.kene_api.chat.side_table import ChatSessionSideTableService
        from src.kene_api.routers import chat as chat_module

        svc = ChatSessionSideTableService(db=self.db)
        _session_service = session_service or _make_session_service(state={})

        user_ctx = UserContext(
            user_id=user_id,
            email="test@example.com",
            organization_permissions={},
            account_permissions={},
        )

        async def _call() -> Any:
            with (
                patch.object(
                    chat_module, "get_chat_side_table_service", return_value=svc
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

    def test_200_with_sorted_validated_todo_lists(self) -> None:
        """AC-5: Returns sorted, validated todo lists when state has valid entries."""
        _seed_session(self.db)
        state = {
            "todo_lists": {
                "current": _valid_raw(
                    list_id="current",
                    title="Current Task",
                    is_current=True,
                    created_at="2026-04-01T10:00:00Z",
                ),
                "old": _valid_raw(
                    list_id="old",
                    title="Old Task",
                    is_current=False,
                    created_at="2026-01-01T00:00:00Z",
                ),
            }
        }
        svc = _make_session_service(state=state)
        resp = self._run_handler(session_service=svc)
        assert len(resp.todo_lists) == 2
        assert resp.todo_lists[0].list_id == "current"
        assert resp.todo_lists[1].list_id == "old"

    def test_200_from_adk_fallback_when_side_table_missing(self) -> None:
        """Returns 200 via ADK fallback when side-table row is missing but ADK has the session."""
        # No side-table row seeded — only ADK session service mock has the session.
        state = {
            "account_id": _ACCOUNT_ID,
            "todo_lists": {
                "supervisor_ledger": _valid_raw(
                    list_id="supervisor_ledger",
                    title="Supervisor Ledger",
                    is_current=True,
                    created_at="2026-04-01T10:00:00Z",
                ),
            },
        }
        # ADK mock returns a session with account_id in state
        svc = _make_session_service(state=state)
        resp = self._run_handler(session_id=_SESSION_ID, session_service=svc)
        assert len(resp.todo_lists) == 1
        assert resp.todo_lists[0].list_id == "supervisor_ledger"

    def test_404_for_tombstoned_session_even_when_adk_has_it(self) -> None:
        """CH-70: a soft-deleted side-table row returns 404 even when ADK still
        has the session — the fallback must NOT re-expose deleted conversations
        during the orphan-scan grace window."""
        from fastapi import HTTPException

        _seed_session(self.db)
        # Tombstone the row (the ADK session is reaped later by the orphan scan).
        self.db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}").update(
            {"deleted_at": datetime.now(timezone.utc)}
        )
        # ADK still has the session with todo_lists — pre-fix this leaked as 200.
        state = {
            "account_id": _ACCOUNT_ID,
            "todo_lists": {"supervisor_ledger": _valid_raw(is_current=True)},
        }
        svc = _make_session_service(state=state)
        with pytest.raises(HTTPException) as exc_info:
            self._run_handler(session_id=_SESSION_ID, session_service=svc)

        assert exc_info.value.status_code == 404
        # Ownership is denied at the side-table layer — ADK must not be consulted.
        svc.get_session.assert_not_called()

    def test_404_when_session_missing_from_both_side_table_and_adk(self) -> None:
        """Returns 404 when session is missing from both side-table and ADK."""
        from fastapi import HTTPException

        # ADK returns None — no session at all
        svc = _make_session_service(raises=Exception("not found"))
        with pytest.raises(HTTPException) as exc_info:
            self._run_handler(session_id="sess_does_not_exist", session_service=svc)

        assert exc_info.value.status_code == 404

    def test_404_when_session_belongs_to_different_user(self) -> None:
        """Returns 404 when session belongs to a different user (no existence leak)."""
        from fastapi import HTTPException

        _seed_session(self.db, user_id="other_user")

        with pytest.raises(HTTPException) as exc_info:
            self._run_handler(user_id="different_user")

        assert exc_info.value.status_code == 404

    def test_200_empty_when_todo_lists_key_absent(self) -> None:
        """Returns 200 with empty list when state has no todo_lists key."""
        _seed_session(self.db)
        svc = _make_session_service(state={})
        resp = self._run_handler(session_service=svc)
        assert resp.todo_lists == []

    def test_ac5_mixed_valid_and_malformed_returns_only_valid(self) -> None:
        """AC-5: Mixed input returns only the good entry; bad entry dropped silently."""
        _seed_session(self.db)
        state = {
            "todo_lists": {
                "good_list": _valid_raw(list_id="good_list", title="Good List"),
                "bad_list": {"nope": 1},
            }
        }
        svc = _make_session_service(state=state)
        resp = self._run_handler(session_service=svc)
        assert len(resp.todo_lists) == 1
        assert resp.todo_lists[0].list_id == "good_list"
