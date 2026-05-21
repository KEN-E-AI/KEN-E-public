"""Integration tests for POST /conversations/{session_id}/mark-read (CH-16).

Run against the Firestore emulator:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/chat/test_mark_read_endpoint.py -v

References: CH-PRD-02 §5.5, §6, §7 AC-7.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason=(
        "Firestore emulator integration tests skipped by default. "
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 (and GOOGLE_CLOUD_PROJECT_ID=test-project) "
        "to enable. Run `gcloud emulators firestore start --host-port=127.0.0.1:8090`."
    ),
)

_ACCOUNT_ID = "acc_ch16_test"
_SESSION_ID = "sess_ch16_real_001"
_USER_ID = "user_ch16_test"
_ORG_ID = "org_ch16_test"


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
    last_viewed_at: datetime | None = None,
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
        "last_viewed_at": last_viewed_at,
        "deleted_at": None,
    }
    db.document(f"accounts/{account_id}/chat_sessions/{session_id}").set(doc)


def _read_session(db: Any, account_id: str = _ACCOUNT_ID, session_id: str = _SESSION_ID) -> Any:
    snap = db.document(f"accounts/{account_id}/chat_sessions/{session_id}").get()
    return snap.to_dict() if snap.exists else None


class TestMarkReadEndpointIntegration:
    """Integration tests that write and read from the Firestore emulator."""

    def setup_method(self) -> None:
        self.db = _emulator_client()
        # Delete any stale doc from a previous run.
        self.db.document(
            f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}"
        ).delete()

    def _run_handler(
        self,
        session_id: str = _SESSION_ID,
        user_id: str = _USER_ID,
    ) -> Any:
        """Run mark_conversation_read against the real emulator via the side-table service."""
        import asyncio

        from src.kene_api.auth.models import UserContext
        from src.kene_api.chat.mark_read_limiter import MarkReadRateLimiter
        from src.kene_api.chat.side_table import ChatSessionSideTableService
        from src.kene_api.routers import chat as chat_module

        svc = ChatSessionSideTableService(db=self.db)
        limiter = MarkReadRateLimiter(max_requests=1000, window_seconds=60)
        user_ctx = UserContext(
            user_id=user_id,
            email="test@example.com",
            organization_permissions={},
            account_permissions={},
        )

        async def _call() -> Any:
            with (
                patch.object(chat_module, "get_chat_side_table_service", return_value=svc),
                patch.object(chat_module, "mark_read_limiter", limiter),
            ):
                from src.kene_api.routers.chat import mark_conversation_read

                return await mark_conversation_read(
                    session_id=session_id,
                    user_context=user_ctx,
                )

        return asyncio.run(_call())

    def test_stamps_last_viewed_at_in_firestore(self) -> None:
        """Handler stamps last_viewed_at; emulator reflects the write."""
        _seed_session(self.db, last_viewed_at=None)

        before = datetime.now(timezone.utc)
        resp = self._run_handler()
        after = datetime.now(timezone.utc)

        assert before <= resp.last_viewed_at <= after

        row = _read_session(self.db)
        assert row is not None
        stored = row["last_viewed_at"]
        if stored.tzinfo is None:
            stored = stored.replace(tzinfo=timezone.utc)
        assert before <= stored <= after

    def test_updated_at_also_stamped(self) -> None:
        """updated_at is written alongside last_viewed_at."""
        _seed_session(self.db, last_viewed_at=None)
        before = datetime.now(timezone.utc)
        self._run_handler()
        row = _read_session(self.db)
        assert row is not None
        updated_at = row["updated_at"]
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        assert updated_at >= before

    def test_dedup_skips_write_within_5s(self) -> None:
        """Second call within 5s returns existing timestamp and skips Firestore write."""
        recent = datetime.now(timezone.utc) - timedelta(seconds=2)
        _seed_session(self.db, last_viewed_at=recent)

        # Patch update_from_delta to detect whether it's called.
        from src.kene_api.chat.side_table import ChatSessionSideTableService

        original_update = ChatSessionSideTableService.update_from_delta
        call_count: list[int] = [0]

        def _counting_update(self: Any, **kwargs: Any) -> None:
            call_count[0] += 1
            original_update(self, **kwargs)

        with patch.object(ChatSessionSideTableService, "update_from_delta", _counting_update):
            resp = self._run_handler()

        assert resp.last_viewed_at == recent
        assert call_count[0] == 0

    def test_404_for_missing_session(self) -> None:
        """Handler returns 404 when session does not exist in Firestore."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            self._run_handler(session_id="sess_does_not_exist")

        assert exc_info.value.status_code == 404

    def test_404_for_tombstoned_session(self) -> None:
        """Handler returns 404 when the session exists but has been soft-deleted."""
        from fastapi import HTTPException

        _seed_session(self.db)
        # Tombstone it.
        self.db.document(
            f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}"
        ).update({"deleted_at": datetime.now(timezone.utc)})

        with pytest.raises(HTTPException) as exc_info:
            self._run_handler()

        assert exc_info.value.status_code == 404
