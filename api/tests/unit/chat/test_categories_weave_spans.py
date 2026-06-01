"""Unit tests for Weave span emission in ChatCategoryService (CH-34).

Verifies that each public method emits the correct weave.attributes context
with the documented attribute dict, and that the service degrades gracefully
(nullcontext) when weave is not importable.

Pure-logic unit tests (T-4): Firestore client is mocked with MagicMock.
No emulator dependency. Covers: chat.category.created, .assigned, .deleted,
.bulk_clear spans + nullcontext degradation.

PRD reference: CH-PRD-03 §2 (Weave spans), §7 AC-12.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, call

import pytest
import src.kene_api.chat.categories as _cat_module
from src.kene_api.chat.categories import (
    ChatCategoryService,
    _deterministic_category_id,
)
from src.kene_api.models.chat import compute_name_casefold

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db() -> MagicMock:
    db = MagicMock()
    db.document.return_value.create.return_value = None
    return db


def _make_svc(db: MagicMock | None = None) -> ChatCategoryService:
    return ChatCategoryService(db=db or _make_db())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_session_snap(
    *,
    session_id: str = "sess_1",
    user_id: str = "u1",
    account_id: str = "acc_1",
) -> MagicMock:
    now = _now()
    snap = MagicMock()
    snap.exists = True
    snap.to_dict.return_value = {
        "session_id": session_id,
        "user_id": user_id,
        "account_id": account_id,
        "organization_id": "org_1",
        "model_id": "gemini-2.5-flash",
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
        "title": "My Session",
        "latest_summary": "",
        "category_id": None,
        "search_text": "",
    }
    return snap


def _make_assign_db(
    *,
    user_id: str = "u1",
    session_id: str = "sess_1",
    account_id: str = "acc_1",
) -> MagicMock:
    """DB mock wired for assign_category(user_id, session_id, None).

    category_id=None skips the category doc lookup, so only the
    collection-group session query and the session update call are needed.
    """
    db = MagicMock()
    snap = _make_session_snap(session_id=session_id, user_id=user_id, account_id=account_id)

    query_chain = MagicMock()
    query_chain.where.return_value = query_chain
    query_chain.limit.return_value = query_chain
    query_chain.get.return_value = [snap]
    db.collection_group.return_value = query_chain
    return db


def _make_assign_db_with_category(
    *,
    user_id: str = "u1",
    session_id: str = "sess_1",
    account_id: str = "acc_1",
    category_name: str = "Q3 Campaigns",
) -> MagicMock:
    """DB mock wired for assign_category(user_id, session_id, cat_id) with a real category.

    category_id is non-None, so the category doc lookup path is exercised.
    """
    db = MagicMock()
    snap = _make_session_snap(session_id=session_id, user_id=user_id, account_id=account_id)

    query_chain = MagicMock()
    query_chain.where.return_value = query_chain
    query_chain.limit.return_value = query_chain
    query_chain.get.return_value = [snap]
    db.collection_group.return_value = query_chain

    cat_doc = MagicMock()
    cat_doc.exists = True
    cat_doc.to_dict.return_value = {"name": category_name}

    def _doc_side(path: str) -> MagicMock:
        if "chat_categories" in path:
            m = MagicMock()
            m.get.return_value = cat_doc
            return m
        return MagicMock()

    db.document.side_effect = _doc_side
    return db


def _make_chat_session_snap(
    *,
    user_id: str = "u1",
    category_id: str = "cat_abc",
) -> MagicMock:
    """Minimal chat_sessions snapshot for delete_category batching tests."""
    snap = MagicMock()
    snap.reference = MagicMock()
    snap.to_dict.return_value = {
        "user_id": user_id,
        "category_id": category_id,
        "title": "Session",
        "updated_at": None,
        "deleted_at": None,
    }
    return snap


def _make_delete_db(snaps: list[MagicMock]) -> MagicMock:
    db = MagicMock()
    query_chain = MagicMock()
    query_chain.where.return_value = query_chain
    query_chain.get.return_value = snaps
    db.collection_group.return_value = query_chain
    db.transaction.return_value = MagicMock()
    return db


# ---------------------------------------------------------------------------
# TestSpanCreated — chat.category.created
# ---------------------------------------------------------------------------


class TestSpanCreated:
    def test_weave_attributes_called_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_weave = MagicMock()
        monkeypatch.setattr(_cat_module, "weave", mock_weave)
        monkeypatch.setattr(_cat_module, "WEAVE_AVAILABLE", True)

        svc = _make_svc()
        svc.create_category("u1", "Q3 Campaigns")

        mock_weave.attributes.assert_called_once()

    def test_span_attribute_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_weave = MagicMock()
        monkeypatch.setattr(_cat_module, "weave", mock_weave)
        monkeypatch.setattr(_cat_module, "WEAVE_AVAILABLE", True)

        svc = _make_svc()
        svc.create_category("u1", "Q3 Campaigns")

        casefold = compute_name_casefold("Q3 Campaigns")
        expected_id = _deterministic_category_id("u1", casefold)
        mock_weave.attributes.assert_called_once_with(
            {
                "user_id": "u1",
                "category_id": expected_id,
                "name_casefold": casefold,
            }
        )

    def test_still_returns_definition_when_weave_available(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_weave = MagicMock()
        monkeypatch.setattr(_cat_module, "weave", mock_weave)
        monkeypatch.setattr(_cat_module, "WEAVE_AVAILABLE", True)

        svc = _make_svc()
        result = svc.create_category("u1", "Q3 Campaigns")

        assert result.user_id == "u1"
        assert result.name == "Q3 Campaigns"


# ---------------------------------------------------------------------------
# TestSpanAssigned — chat.category.assigned
# ---------------------------------------------------------------------------


class TestSpanAssigned:
    def test_weave_attributes_called_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_weave = MagicMock()
        monkeypatch.setattr(_cat_module, "weave", mock_weave)
        monkeypatch.setattr(_cat_module, "WEAVE_AVAILABLE", True)

        db = _make_assign_db(user_id="u1", session_id="sess_1")
        svc = _make_svc(db)
        svc.assign_category("u1", "sess_1", None)

        mock_weave.attributes.assert_called_once()

    def test_span_attribute_dict_with_none_category(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_weave = MagicMock()
        monkeypatch.setattr(_cat_module, "weave", mock_weave)
        monkeypatch.setattr(_cat_module, "WEAVE_AVAILABLE", True)

        db = _make_assign_db(user_id="u1", session_id="sess_1")
        svc = _make_svc(db)
        svc.assign_category("u1", "sess_1", None)

        mock_weave.attributes.assert_called_once_with(
            {
                "user_id": "u1",
                "session_id": "sess_1",
                "category_id": None,
            }
        )

    def test_span_attribute_dict_with_real_category_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_weave = MagicMock()
        monkeypatch.setattr(_cat_module, "weave", mock_weave)
        monkeypatch.setattr(_cat_module, "WEAVE_AVAILABLE", True)

        db = _make_assign_db_with_category(user_id="u1", session_id="sess_1")
        svc = _make_svc(db)
        svc.assign_category("u1", "sess_1", "cat_abc")

        mock_weave.attributes.assert_called_once_with(
            {
                "user_id": "u1",
                "session_id": "sess_1",
                "category_id": "cat_abc",
            }
        )

    def test_still_returns_metadata_when_weave_available(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.kene_api.models.chat import ChatSessionMetadata

        mock_weave = MagicMock()
        monkeypatch.setattr(_cat_module, "weave", mock_weave)
        monkeypatch.setattr(_cat_module, "WEAVE_AVAILABLE", True)

        db = _make_assign_db()
        svc = _make_svc(db)
        result = svc.assign_category("u1", "sess_1", None)

        assert isinstance(result, ChatSessionMetadata)


# ---------------------------------------------------------------------------
# TestSpanDeleted — chat.category.deleted (outer) + bulk_clear (inner)
# ---------------------------------------------------------------------------


class TestSpanDeleted:
    def test_deleted_span_fires_once_no_sessions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_weave = MagicMock()
        monkeypatch.setattr(_cat_module, "weave", mock_weave)
        monkeypatch.setattr(_cat_module, "WEAVE_AVAILABLE", True)

        db = _make_delete_db(snaps=[])
        svc = _make_svc(db)
        svc.delete_category("u1", "cat_abc")

        # Only the outer deleted span; the empty-batch transaction does not emit
        # a bulk_clear span (no sessions to clear — only a category doc deletion).
        assert mock_weave.attributes.call_count == 1

    def test_deleted_span_attributes_no_sessions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_weave = MagicMock()
        monkeypatch.setattr(_cat_module, "weave", mock_weave)
        monkeypatch.setattr(_cat_module, "WEAVE_AVAILABLE", True)

        db = _make_delete_db(snaps=[])
        svc = _make_svc(db)
        svc.delete_category("u1", "cat_abc")

        # First call is the outer deleted span
        outer_call = mock_weave.attributes.call_args_list[0]
        assert outer_call == call(
            {
                "user_id": "u1",
                "category_id": "cat_abc",
                "sessions_reassigned": 0,
                "transactions_used": 1,
            }
        )

    def test_deleted_span_attributes_with_single_session(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_weave = MagicMock()
        monkeypatch.setattr(_cat_module, "weave", mock_weave)
        monkeypatch.setattr(_cat_module, "WEAVE_AVAILABLE", True)

        snaps = [_make_chat_session_snap(user_id="u1", category_id="cat_abc")]
        db = _make_delete_db(snaps)
        svc = _make_svc(db)
        svc.delete_category("u1", "cat_abc")

        outer_call = mock_weave.attributes.call_args_list[0]
        assert outer_call == call(
            {
                "user_id": "u1",
                "category_id": "cat_abc",
                "sessions_reassigned": 1,
                "transactions_used": 1,
            }
        )


# ---------------------------------------------------------------------------
# TestSpanBulkClear — 401 sessions → 2 batches
# ---------------------------------------------------------------------------


class TestSpanBulkClear:
    def test_two_bulk_clear_spans_for_401_sessions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """401 sessions → 2 bulk_clear spans (sizes 400 + 1) + 1 deleted parent span."""
        mock_weave = MagicMock()
        monkeypatch.setattr(_cat_module, "weave", mock_weave)
        monkeypatch.setattr(_cat_module, "WEAVE_AVAILABLE", True)

        snaps = [
            _make_chat_session_snap(user_id="u1", category_id="cat_abc")
            for _ in range(401)
        ]
        db = _make_delete_db(snaps)
        svc = _make_svc(db)
        svc.delete_category("u1", "cat_abc")

        # 1 deleted span + 2 bulk_clear spans
        assert mock_weave.attributes.call_count == 3

    def test_first_bulk_clear_span_attrs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_weave = MagicMock()
        monkeypatch.setattr(_cat_module, "weave", mock_weave)
        monkeypatch.setattr(_cat_module, "WEAVE_AVAILABLE", True)

        snaps = [
            _make_chat_session_snap(user_id="u1", category_id="cat_abc")
            for _ in range(401)
        ]
        db = _make_delete_db(snaps)
        svc = _make_svc(db)
        svc.delete_category("u1", "cat_abc")

        calls = mock_weave.attributes.call_args_list
        # calls[0] = deleted outer, calls[1] = bulk_clear batch 0, calls[2] = bulk_clear batch 1
        assert calls[1] == call(
            {
                "user_id": "u1",
                "category_id": "cat_abc",
                "batch_index": 0,
                "batch_size": 400,
            }
        )

    def test_second_bulk_clear_span_attrs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_weave = MagicMock()
        monkeypatch.setattr(_cat_module, "weave", mock_weave)
        monkeypatch.setattr(_cat_module, "WEAVE_AVAILABLE", True)

        snaps = [
            _make_chat_session_snap(user_id="u1", category_id="cat_abc")
            for _ in range(401)
        ]
        db = _make_delete_db(snaps)
        svc = _make_svc(db)
        svc.delete_category("u1", "cat_abc")

        calls = mock_weave.attributes.call_args_list
        assert calls[2] == call(
            {
                "user_id": "u1",
                "category_id": "cat_abc",
                "batch_index": 1,
                "batch_size": 1,
            }
        )

    def test_deleted_parent_span_carries_correct_counts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_weave = MagicMock()
        monkeypatch.setattr(_cat_module, "weave", mock_weave)
        monkeypatch.setattr(_cat_module, "WEAVE_AVAILABLE", True)

        snaps = [
            _make_chat_session_snap(user_id="u1", category_id="cat_abc")
            for _ in range(401)
        ]
        db = _make_delete_db(snaps)
        svc = _make_svc(db)
        svc.delete_category("u1", "cat_abc")

        outer_call = mock_weave.attributes.call_args_list[0]
        assert outer_call == call(
            {
                "user_id": "u1",
                "category_id": "cat_abc",
                "sessions_reassigned": 401,
                "transactions_used": 2,
            }
        )

    def test_bulk_clear_no_name_casefold_attribute(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify bulk_clear span does not include name_casefold (PII guard)."""
        mock_weave = MagicMock()
        monkeypatch.setattr(_cat_module, "weave", mock_weave)
        monkeypatch.setattr(_cat_module, "WEAVE_AVAILABLE", True)

        snaps = [_make_chat_session_snap(user_id="u1", category_id="cat_abc")]
        db = _make_delete_db(snaps)
        svc = _make_svc(db)
        svc.delete_category("u1", "cat_abc")

        # calls[1] is the bulk_clear span
        calls = mock_weave.attributes.call_args_list
        bulk_clear_attrs: dict = calls[1][0][0]
        assert "name_casefold" not in bulk_clear_attrs
        assert "name" not in bulk_clear_attrs
        assert "search_text" not in bulk_clear_attrs


# ---------------------------------------------------------------------------
# TestNullcontextDegradation
# ---------------------------------------------------------------------------


class TestNullcontextDegradation:
    def test_create_category_works_without_weave(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_cat_module, "WEAVE_AVAILABLE", False)
        monkeypatch.setattr(_cat_module, "weave", None)

        svc = _make_svc()
        result = svc.create_category("u1", "Q3 Campaigns")

        assert result.user_id == "u1"
        assert result.name == "Q3 Campaigns"

    def test_assign_category_works_without_weave(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.kene_api.models.chat import ChatSessionMetadata

        monkeypatch.setattr(_cat_module, "WEAVE_AVAILABLE", False)
        monkeypatch.setattr(_cat_module, "weave", None)

        db = _make_assign_db()
        svc = _make_svc(db)
        result = svc.assign_category("u1", "sess_1", None)

        assert isinstance(result, ChatSessionMetadata)

    def test_delete_category_works_without_weave(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.kene_api.chat.categories import DeleteCategoryResult

        monkeypatch.setattr(_cat_module, "WEAVE_AVAILABLE", False)
        monkeypatch.setattr(_cat_module, "weave", None)

        snaps = [_make_chat_session_snap()]
        db = _make_delete_db(snaps)
        svc = _make_svc(db)
        result = svc.delete_category("u1", "cat_abc")

        assert isinstance(result, DeleteCategoryResult)
        assert result.sessions_reassigned == 1

    def test_no_attribute_error_when_weave_attributes_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """weave.attributes() blowing up degrades to nullcontext — no exception propagated."""
        mock_weave = MagicMock()
        mock_weave.attributes.side_effect = RuntimeError("Weave SDK error")
        monkeypatch.setattr(_cat_module, "weave", mock_weave)
        monkeypatch.setattr(_cat_module, "WEAVE_AVAILABLE", True)

        svc = _make_svc()
        # Should not raise — the helper catches the exception and uses nullcontext
        result = svc.create_category("u1", "Q3 Campaigns")
        assert result.user_id == "u1"
