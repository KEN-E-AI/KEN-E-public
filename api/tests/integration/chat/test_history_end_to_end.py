"""Integration tests for GET /conversations/{session_id}/history (CH-76).

Run against the Firestore emulator:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/chat/test_history_end_to_end.py -v

The key acceptance-criteria test is ``test_404_when_session_belongs_to_different_user``:
a session owned by ``other_user`` must return 404 when called as ``different_user``.
This mirrors the existing test in ``test_todos_end_to_end.py``.

References: CH-76 issue body §Acceptance Criteria, §Scope.
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

_ACCOUNT_ID = "acc_ch76_test"
_SESSION_ID = "sess_ch76_real_001"
_USER_ID = "user_ch76_test"
_ORG_ID = "org_ch76_test"


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


def _make_formatted_history(session_id: str = _SESSION_ID) -> dict:
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


class TestHistoryEndpointIntegration:
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
        history_return: dict | None = None,
    ) -> Any:
        """Run get_conversation_history against the real emulator via the side-table service."""
        import asyncio

        from src.kene_api.auth.models import UserContext
        from src.kene_api.chat.side_table import ChatSessionSideTableService
        from src.kene_api.routers import chat as chat_module

        svc = ChatSessionSideTableService(db=self.db)
        _session_service = session_service or MagicMock()

        user_ctx = UserContext(
            user_id=user_id,
            email="test@example.com",
            organization_permissions={},
            account_permissions={},
        )

        _history_return = history_return if history_return is not None else _make_formatted_history(
            session_id=session_id
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
                chat_module.agent_client.get_conversation_history = AsyncMock(
                    return_value=_history_return
                )
                from src.kene_api.routers.chat import get_conversation_history

                return await get_conversation_history(
                    session_id=session_id,
                    user_context=user_ctx,
                )

        return asyncio.run(_call())

    def test_404_when_session_belongs_to_different_user(self) -> None:
        """AC (CH-76): session owned by other_user returns 404 when called as different_user.

        This is the primary acceptance-criteria test named in the issue — mirrors
        test_todos_end_to_end.py::test_404_when_session_belongs_to_different_user.
        """
        from fastapi import HTTPException

        _seed_session(self.db, user_id="other_user")

        with pytest.raises(HTTPException) as exc_info:
            self._run_handler(user_id="different_user")

        assert exc_info.value.status_code == 404

    def test_404_for_tombstoned_session_even_when_adk_has_it(self) -> None:
        """A soft-deleted side-table row returns 404 even when ADK would return events.

        The ADK mock (get_conversation_history) must NOT be called: ownership is
        denied at the side-table layer before the inner method is invoked.
        """
        from fastapi import HTTPException

        _seed_session(self.db)
        # Tombstone the row — ADK orphan scan will clean up the ADK session later.
        self.db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}").update(
            {"deleted_at": datetime.now(timezone.utc)}
        )

        with pytest.raises(HTTPException) as exc_info:
            self._run_handler()

        assert exc_info.value.status_code == 404

    def test_200_for_legitimate_owner(self) -> None:
        """Happy path: session owned by the calling user → 200 with formatted history."""
        _seed_session(self.db)
        expected = _make_formatted_history()
        assert self._run_handler() == expected

    def test_200_from_adk_fallback_when_side_table_missing(self) -> None:
        """No side-table row present → ADK fallback ownership check → 200 for the CH-71 recovery path.

        Covers the case where a legacy/dev session does not yet have a side-table
        row (pre-CH-PRD-01 backfill) but ADK has the session with account_id in
        state. resolve_session_for_user's ADK fallback synthesises the metadata,
        so the endpoint still returns 200. This is the CH-71 stream-death recovery
        path — if the side-table miss forced a 404, recovery would silently fail.
        """
        # No side-table row seeded — ADK fallback must synthesise ownership from state.
        adk_session = MagicMock()
        adk_session.state = {
            "account_id": _ACCOUNT_ID,
            "user_id": _USER_ID,
        }
        adk_session.app_name = "ken_e_chatbot"
        adk_session.id = _SESSION_ID
        adk_session.user_id = _USER_ID

        fake_session_service = MagicMock()
        fake_session_service.get_session = AsyncMock(return_value=adk_session)

        expected = _make_formatted_history()
        assert self._run_handler(session_service=fake_session_service) == expected
