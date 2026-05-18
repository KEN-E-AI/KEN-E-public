"""Unit tests for ChatSessionSideTableService (CH-PRD-01 §7 AC-5)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.kene_api.chat.side_table import ChatSessionSideTableService, _doc_path


def _make_db() -> MagicMock:
    return MagicMock()


class TestDocPath:
    def test_shape_b_layout(self) -> None:
        path = _doc_path("acc_123", "sess_abc")
        assert path == "accounts/acc_123/chat_sessions/sess_abc"


class TestCreate:
    def test_returns_metadata_with_correct_fields(self) -> None:
        db = _make_db()
        doc_ref = MagicMock()
        db.document.return_value = doc_ref

        svc = ChatSessionSideTableService(db=db)
        result = svc.create(
            session_id="sess_1",
            user_id="user_1",
            account_id="acc_1",
            organization_id="org_1",
            model_id="gemini-2.5-flash",
        )

        assert result.session_id == "sess_1"
        assert result.user_id == "user_1"
        assert result.account_id == "acc_1"
        assert result.organization_id == "org_1"
        assert result.model_id == "gemini-2.5-flash"

    def test_calls_doc_create(self) -> None:
        db = _make_db()
        doc_ref = MagicMock()
        db.document.return_value = doc_ref

        svc = ChatSessionSideTableService(db=db)
        svc.create(
            session_id="sess_1",
            user_id="user_1",
            account_id="acc_1",
            organization_id="org_1",
            model_id="gemini-2.5-flash",
        )

        db.document.assert_called_once_with("accounts/acc_1/chat_sessions/sess_1")
        doc_ref.create.assert_called_once()

    def test_context_window_max_set_from_registry(self) -> None:
        db = _make_db()
        db.document.return_value = MagicMock()

        svc = ChatSessionSideTableService(db=db)
        result = svc.create(
            session_id="s",
            user_id="u",
            account_id="a",
            organization_id="o",
            model_id="gemini-2.5-flash",
        )

        assert result.context_window_max > 0


class TestGet:
    def test_returns_none_when_not_found(self) -> None:
        db = _make_db()
        snapshot = MagicMock()
        snapshot.exists = False
        db.document.return_value.get.return_value = snapshot

        svc = ChatSessionSideTableService(db=db)
        result = svc.get(account_id="acc_1", session_id="sess_missing")

        assert result is None

    def test_returns_metadata_when_found(self) -> None:
        db = _make_db()
        snapshot = MagicMock()
        snapshot.exists = True
        snapshot.to_dict.return_value = {
            "session_id": "sess_1",
            "user_id": "user_1",
            "account_id": "acc_1",
            "organization_id": "org_1",
            "model_id": "gemini-2.5-flash",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        db.document.return_value.get.return_value = snapshot

        svc = ChatSessionSideTableService(db=db)
        result = svc.get(account_id="acc_1", session_id="sess_1")

        assert result is not None
        assert result.session_id == "sess_1"


class TestUpdateFromDelta:
    def test_calls_firestore_update(self) -> None:
        db = _make_db()
        doc_ref = MagicMock()
        db.document.return_value = doc_ref

        svc = ChatSessionSideTableService(db=db)
        svc.update_from_delta(
            account_id="acc_1",
            session_id="sess_1",
            delta={"message_count": 5, "updated_at": datetime.now(timezone.utc)},
        )

        doc_ref.update.assert_called_once()

    def test_noop_on_empty_delta(self) -> None:
        db = _make_db()
        doc_ref = MagicMock()
        db.document.return_value = doc_ref

        svc = ChatSessionSideTableService(db=db)
        svc.update_from_delta(account_id="acc_1", session_id="sess_1", delta={})

        doc_ref.update.assert_not_called()


class TestTombstone:
    def test_sets_deleted_at_and_updated_at(self) -> None:
        db = _make_db()
        doc_ref = MagicMock()
        db.document.return_value = doc_ref

        svc = ChatSessionSideTableService(db=db)
        deleted_at = svc.tombstone(account_id="acc_1", session_id="sess_1")

        assert isinstance(deleted_at, datetime)
        call_kwargs = doc_ref.update.call_args[0][0]
        assert "deleted_at" in call_kwargs
        assert "updated_at" in call_kwargs
        assert call_kwargs["deleted_at"] == deleted_at
