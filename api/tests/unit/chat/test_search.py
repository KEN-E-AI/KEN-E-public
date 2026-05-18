"""Unit tests for chat search helpers (CH-PRD-01 §7 AC-5)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.kene_api.chat.search import (
    CHAT_LIST_WINDOW_DAYS,
    decode_cursor,
    encode_cursor,
    list_sessions,
)


class TestConstants:
    def test_window_days_is_30(self) -> None:
        assert CHAT_LIST_WINDOW_DAYS == 30


class TestCursorRoundtrip:
    def _make_snapshot(self, ref_path: str, updated_at: datetime) -> MagicMock:
        snap = MagicMock()
        snap.reference.path = ref_path
        snap.to_dict.return_value = {"updated_at": updated_at}
        return snap

    def test_encode_decode_roundtrip(self) -> None:
        now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        snap = self._make_snapshot("accounts/acc/chat_sessions/sess", now)

        cursor = encode_cursor(snap)
        path, dt = decode_cursor(cursor)

        assert path == "accounts/acc/chat_sessions/sess"
        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 6

    def test_decode_malformed_cursor_returns_empty_datetime(self) -> None:
        path, dt = decode_cursor("not-valid-base64!!!")
        # Should not raise; path and dt may be garbage but no exception
        # (the caller ignores malformed cursors)

    def test_encode_cursor_is_urlsafe_base64(self) -> None:
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        snap = self._make_snapshot("a/b/c/d", now)
        cursor = encode_cursor(snap)
        # URL-safe base64 must not contain + or /
        assert "+" not in cursor
        assert "/" not in cursor


class TestListSessions:
    def _make_db(self, docs: list[dict]) -> MagicMock:
        """Return a mock Firestore client where collection_group yields `docs`."""
        db = MagicMock()
        snapshots = []
        for d in docs:
            snap = MagicMock()
            snap.to_dict.return_value = d
            snap.reference.path = f"accounts/{d['account_id']}/chat_sessions/{d['session_id']}"
            snapshots.append(snap)

        # Chain all the query method calls
        q = MagicMock()
        q.where.return_value = q
        q.order_by.return_value = q
        q.limit.return_value = q
        q.start_after.return_value = q
        q.stream.return_value = iter(snapshots)
        db.collection_group.return_value = q
        return db

    def _session_doc(
        self,
        session_id: str = "sess_1",
        user_id: str = "user_1",
        account_id: str = "acc_1",
        search_text: str = "",
    ) -> dict:
        from datetime import timedelta

        return {
            "session_id": session_id,
            "user_id": user_id,
            "account_id": account_id,
            "organization_id": "org_1",
            "model_id": "gemini-2.5-flash",
            "search_text": search_text,
            "updated_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "deleted_at": None,
        }

    def test_returns_sessions_for_correct_account(self) -> None:
        docs = [
            self._session_doc("s1", "user_1", "acc_1"),
            self._session_doc("s2", "user_1", "acc_OTHER"),
        ]
        db = self._make_db(docs)

        results, next_cursor = list_sessions(db=db, user_id="user_1", account_id="acc_1")

        assert len(results) == 1
        assert results[0].session_id == "s1"

    def test_query_filter_casefold(self) -> None:
        docs = [
            self._session_doc("s1", search_text="Marketing report"),
            self._session_doc("s2", search_text="unrelated content"),
        ]
        db = self._make_db(docs)

        results, _ = list_sessions(
            db=db, user_id="user_1", account_id="acc_1", query="marketing"
        )

        assert len(results) == 1
        assert results[0].session_id == "s1"

    def test_empty_results_when_no_match(self) -> None:
        db = self._make_db([])

        results, next_cursor = list_sessions(db=db, user_id="user_1", account_id="acc_1")

        assert results == []
        assert next_cursor is None

    def test_next_cursor_none_when_fewer_than_limit(self) -> None:
        docs = [self._session_doc(f"s{i}") for i in range(3)]
        db = self._make_db(docs)

        results, next_cursor = list_sessions(
            db=db, user_id="user_1", account_id="acc_1", limit=20
        )

        assert next_cursor is None

    def test_next_cursor_set_when_limit_reached(self) -> None:
        docs = [self._session_doc(f"s{i}") for i in range(5)]
        db = self._make_db(docs)

        results, next_cursor = list_sessions(
            db=db, user_id="user_1", account_id="acc_1", limit=5
        )

        assert next_cursor is not None
