"""Unit tests for ChatCategoryService — happy path, name stripping, list ordering,
delete_category batching and write payloads.

Pure-logic unit tests (T-4): Firestore client is mocked with MagicMock.
No emulator dependency. Covers: create_category, list_categories, delete_category,
singleton factory.
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock

import pytest
from google.cloud import firestore as _fs
from src.kene_api.chat.categories import (
    ChatCategoryService,
    DeleteCategoryResult,
    get_chat_category_service,
)
from src.kene_api.models.chat import ChatCategoryDefinition

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db() -> MagicMock:
    """Return a MagicMock Firestore client with .document().create() succeeding by default.

    create_category no longer dedup-queries — collisions surface as AlreadyExists
    from the .create() call thanks to the deterministic doc id. The .collection
    chain is still wired so the list_categories tests in this module work.
    """
    db = MagicMock()
    db.document.return_value.create.return_value = None
    return db


def _make_svc(db: MagicMock | None = None) -> ChatCategoryService:
    return ChatCategoryService(db=db or _make_db())


# ---------------------------------------------------------------------------
# create_category — happy path
# ---------------------------------------------------------------------------


class TestCreateCategoryHappyPath:
    def test_returns_chat_category_definition(self) -> None:
        svc = _make_svc()
        result = svc.create_category("u1", "Q3 Campaigns")
        assert isinstance(result, ChatCategoryDefinition)

    def test_user_id_propagated(self) -> None:
        svc = _make_svc()
        result = svc.create_category("u1", "Q3 Campaigns")
        assert result.user_id == "u1"

    def test_name_stored_on_definition(self) -> None:
        svc = _make_svc()
        result = svc.create_category("u1", "Q3 Campaigns")
        assert result.name == "Q3 Campaigns"

    def test_name_casefold_derived_correctly(self) -> None:
        svc = _make_svc()
        result = svc.create_category("u1", "Q3 Campaigns")
        assert result.name_casefold == "q3 campaigns"

    def test_category_id_prefix_convention(self) -> None:
        svc = _make_svc()
        result = svc.create_category("u1", "Q3 Campaigns")
        assert result.category_id.startswith("cat_")

    def test_category_id_hex_suffix_length(self) -> None:
        svc = _make_svc()
        result = svc.create_category("u1", "Q3 Campaigns")
        # Format: cat_ + 24 hex chars
        assert re.fullmatch(r"cat_[0-9a-f]{24}", result.category_id), (
            f"category_id '{result.category_id}' does not match cat_<24hex> format"
        )

    def test_timestamps_populated(self) -> None:
        svc = _make_svc()
        result = svc.create_category("u1", "Q3 Campaigns")
        assert result.created_at is not None
        assert result.updated_at is not None
        assert result.created_at == result.updated_at


# ---------------------------------------------------------------------------
# create_category — name stripping
# ---------------------------------------------------------------------------


class TestCreateCategoryNameStripping:
    def test_leading_trailing_whitespace_stripped_from_name(self) -> None:
        svc = _make_svc()
        result = svc.create_category("u1", "  Q3 Campaigns  ")
        assert result.name == "Q3 Campaigns"

    def test_casefold_uses_stripped_name(self) -> None:
        svc = _make_svc()
        result = svc.create_category("u1", "  Q3 Campaigns  ")
        assert result.name_casefold == "q3 campaigns"

    def test_name_only_whitespace_raises_value_error(self) -> None:
        svc = _make_svc()
        with pytest.raises(ValueError, match="empty"):
            svc.create_category("u1", "   ")

    def test_empty_string_raises_value_error(self) -> None:
        svc = _make_svc()
        with pytest.raises(ValueError):
            svc.create_category("u1", "")

    def test_name_exceeding_64_chars_raises_value_error(self) -> None:
        svc = _make_svc()
        with pytest.raises(ValueError, match="64"):
            svc.create_category("u1", "A" * 65)

    def test_name_exactly_64_chars_is_accepted(self) -> None:
        svc = _make_svc()
        result = svc.create_category("u1", "A" * 64)
        assert len(result.name) == 64


# ---------------------------------------------------------------------------
# create_category — Firestore write path
# ---------------------------------------------------------------------------


class TestCreateCategoryFirestoreWrite:
    def test_document_written_under_user_collection(self) -> None:
        db = _make_db()
        svc = _make_svc(db)
        result = svc.create_category("u1", "Demo")
        expected_path = f"users/u1/chat_categories/{result.category_id}"
        db.document.assert_called_with(expected_path)

    def test_doc_create_called_once(self) -> None:
        db = _make_db()
        svc = _make_svc(db)
        svc.create_category("u1", "Demo")
        db.document.return_value.create.assert_called_once()

    def test_create_path_does_not_query_the_collection(self) -> None:
        """The query-then-write dedup path was removed in favour of a
        deterministic doc id + .create()'s AlreadyExists. create_category
        must never call .collection(...) — that would re-introduce the race."""
        db = _make_db()
        svc = _make_svc(db)
        svc.create_category("u1", "Demo")
        db.collection.assert_not_called()


# ---------------------------------------------------------------------------
# list_categories — ordering
# ---------------------------------------------------------------------------


def _make_doc(name: str, user_id: str = "u1") -> MagicMock:
    """Return a mock Firestore document snapshot."""
    from datetime import datetime, timezone
    doc = MagicMock()
    doc.to_dict.return_value = {
        "category_id": f"cat_{hash(name) & 0xFFFFFF:024x}",
        "user_id": user_id,
        "name": name,
        "name_casefold": name.casefold(),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    return doc


class TestListCategories:
    def test_returns_list_of_chat_category_definitions(self) -> None:
        db = _make_db()
        db.collection.return_value.order_by.return_value.get.return_value = [
            _make_doc("Zulu"),
        ]
        svc = _make_svc(db)
        result = svc.list_categories("u1")
        assert isinstance(result, list)
        assert all(isinstance(c, ChatCategoryDefinition) for c in result)

    def test_empty_list_when_no_categories(self) -> None:
        db = _make_db()
        db.collection.return_value.order_by.return_value.get.return_value = []
        svc = _make_svc(db)
        result = svc.list_categories("u1")
        assert result == []

    def test_ordered_by_name_asc(self) -> None:
        db = _make_db()
        # Return docs in Firestore order (which is name ASC — the service uses order_by)
        docs = [_make_doc("Alpha"), _make_doc("Beta"), _make_doc("Zeta")]
        db.collection.return_value.order_by.return_value.get.return_value = docs
        svc = _make_svc(db)
        result = svc.list_categories("u1")
        names = [c.name for c in result]
        assert names == ["Alpha", "Beta", "Zeta"]

    def test_order_by_called_with_name_ascending(self) -> None:
        from google.cloud import firestore as fs
        db = _make_db()
        db.collection.return_value.order_by.return_value.get.return_value = []
        svc = _make_svc(db)
        svc.list_categories("u1")
        db.collection.return_value.order_by.assert_called_once_with(
            "name", direction=fs.Query.ASCENDING
        )

    def test_collection_scoped_to_user(self) -> None:
        db = _make_db()
        db.collection.return_value.order_by.return_value.get.return_value = []
        svc = _make_svc(db)
        svc.list_categories("u1")
        db.collection.assert_called_with("users/u1/chat_categories")


# ---------------------------------------------------------------------------
# get_chat_category_service — singleton
# ---------------------------------------------------------------------------


class TestGetChatCategoryServiceSingleton:
    def test_same_instance_returned_on_repeated_calls(self) -> None:
        # get_chat_category_service is @lru_cache(maxsize=1), so it must return
        # the identical object on repeated calls within the same process.
        svc_a = get_chat_category_service()
        svc_b = get_chat_category_service()
        assert svc_a is svc_b

    def test_returns_chat_category_service_instance(self) -> None:
        svc = get_chat_category_service()
        assert isinstance(svc, ChatCategoryService)


# ---------------------------------------------------------------------------
# assign_category — unit tests (CH-33 Task 3)
# ---------------------------------------------------------------------------


def _base_session_row(
    *,
    session_id: str = "sess_1",
    user_id: str = "user_1",
    account_id: str = "acc_1",
) -> dict:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return {
        "session_id": session_id,
        "user_id": user_id,
        "account_id": account_id,
        "organization_id": "org_1",
        "model_id": "gemini-2.5-flash",
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
        "title": "My Session",
        "latest_summary": "A brief summary",
        "category_id": None,
        "search_text": "",
    }


def _make_db_with_session_and_optional_category(
    *,
    session_row: dict | None = None,
    category_exists: bool = True,
    category_name: str = "Paid Media",
) -> MagicMock:
    """Build a mock db that:
    - Supports find_session_for_user via collection_group chain
    - Supports category doc read via db.document().get()
    - Supports final session update via db.document().update()
    """
    db = MagicMock()

    # ---- collection_group chain for find_session_for_user ----
    query_chain = MagicMock()
    query_chain.where.return_value = query_chain
    query_chain.limit.return_value = query_chain

    if session_row is not None:
        snap = MagicMock()
        snap.exists = True
        snap.to_dict.return_value = session_row
        query_chain.get.return_value = [snap]
    else:
        query_chain.get.return_value = []

    db.collection_group.return_value = query_chain

    # ---- db.document().get() for category and db.document().update() ----
    cat_doc = MagicMock()
    cat_doc.exists = category_exists
    cat_doc.to_dict.return_value = {"name": category_name}

    cat_doc_ref = MagicMock()
    cat_doc_ref.get.return_value = cat_doc

    update_doc_ref = MagicMock()

    # Route by path rather than call order — robust against future refactors.
    def _document_side_effect(path: str) -> MagicMock:
        if "chat_categories" in path:
            return cat_doc_ref
        return update_doc_ref

    db.document.side_effect = _document_side_effect
    # Expose update_doc_ref so tests can inspect the payload.
    db._test_update_ref = update_doc_ref
    return db


# ---------------------------------------------------------------------------
# delete_category — batching logic
# ---------------------------------------------------------------------------


def _make_snap(
    *,
    user_id: str = "u1",
    category_id: str = "cat_abc",
    title: str = "Session",
    latest_summary: str | None = None,
    deleted_at: object = None,
) -> MagicMock:
    """Return a MagicMock document snapshot for a chat_sessions row."""
    snap = MagicMock()
    snap.reference = MagicMock()
    row: dict = {
        "user_id": user_id,
        "category_id": category_id,
        "title": title,
        "updated_at": None,
        "deleted_at": deleted_at,
    }
    if latest_summary is not None:
        row["latest_summary"] = latest_summary
    snap.to_dict.return_value = row
    return snap


def _make_db_for_delete(snaps: list[MagicMock]) -> MagicMock:
    """Return a Firestore client mock wired for delete_category.

    Chains: db.collection_group(...).where(...).where(...).get() → snaps
    db.transaction() → a fresh MagicMock tx each call (tx.update and tx.delete
    are MagicMocks that record calls).
    db.document(...) → a MagicMock category_ref.
    """
    db = MagicMock()

    # Collection-group discovery chain
    query_chain = MagicMock()
    query_chain.where.return_value = query_chain
    query_chain.get.return_value = snaps
    db.collection_group.return_value = query_chain

    # Each call to db.transaction() returns a fresh transaction mock
    db.transaction.return_value = MagicMock()

    return db


class TestAssignCategorySessionOwnership:
    def test_raises_permission_error_when_session_not_found(self) -> None:
        db = _make_db_with_session_and_optional_category(session_row=None)
        svc = _make_svc(db)
        with pytest.raises(PermissionError):
            svc.assign_category("user_1", "sess_1", None)

    def test_permission_error_message_does_not_leak_user_id(self) -> None:
        db = _make_db_with_session_and_optional_category(session_row=None)
        svc = _make_svc(db)
        with pytest.raises(PermissionError) as exc_info:
            svc.assign_category("user_1", "sess_1", None)
        assert "user_1" not in str(exc_info.value)


class TestAssignCategoryCategoryOwnership:
    def test_raises_permission_error_when_category_not_found(self) -> None:
        row = _base_session_row()
        db = _make_db_with_session_and_optional_category(
            session_row=row, category_exists=False
        )
        svc = _make_svc(db)
        with pytest.raises(PermissionError):
            svc.assign_category("user_1", "sess_1", "cat_nonexistent")

    def test_permission_error_message_does_not_leak_user_id(self) -> None:
        row = _base_session_row()
        db = _make_db_with_session_and_optional_category(
            session_row=row, category_exists=False
        )
        svc = _make_svc(db)
        with pytest.raises(PermissionError) as exc_info:
            svc.assign_category("user_1", "sess_1", "cat_nonexistent")
        assert "user_1" not in str(exc_info.value)


class TestAssignCategoryHappyPath:
    def _make_assign_db(
        self,
        title: str = "My Session",
        summary: str | None = "A brief summary",
        category_name: str = "Paid Media",
    ) -> MagicMock:
        row = _base_session_row()
        row["title"] = title
        row["latest_summary"] = summary
        return _make_db_with_session_and_optional_category(
            session_row=row, category_name=category_name
        )

    def test_returns_updated_metadata(self) -> None:
        db = self._make_assign_db()
        svc = _make_svc(db)
        result = svc.assign_category("user_1", "sess_1", "cat_abc")
        assert result.category_id == "cat_abc"

    def test_search_text_contains_casefolded_title(self) -> None:
        db = self._make_assign_db(title="My Session", category_name="Paid Media")
        svc = _make_svc(db)
        result = svc.assign_category("user_1", "sess_1", "cat_abc")
        assert "my session" in result.search_text

    def test_search_text_contains_casefolded_category_name(self) -> None:
        db = self._make_assign_db(category_name="Paid Media")
        svc = _make_svc(db)
        result = svc.assign_category("user_1", "sess_1", "cat_abc")
        assert "paid media" in result.search_text

    def test_search_text_contains_casefolded_summary(self) -> None:
        db = self._make_assign_db(summary="A brief summary")
        svc = _make_svc(db)
        result = svc.assign_category("user_1", "sess_1", "cat_abc")
        assert "a brief summary" in result.search_text

    def test_exactly_one_firestore_update_call(self) -> None:
        db = self._make_assign_db()
        svc = _make_svc(db)
        svc.assign_category("user_1", "sess_1", "cat_abc")
        assert db._test_update_ref.update.call_count == 1

    def test_update_dict_contains_expected_keys(self) -> None:
        db = self._make_assign_db()
        svc = _make_svc(db)
        svc.assign_category("user_1", "sess_1", "cat_abc")
        payload = db._test_update_ref.update.call_args[0][0]
        assert payload["category_id"] == "cat_abc"
        assert "search_text" in payload
        assert "updated_at" in payload


class TestAssignCategoryUnassign:
    def test_category_id_cleared_when_none(self) -> None:
        row = _base_session_row()
        row["category_id"] = "cat_old"
        # For None assignment, db.document is only called once (for the update).
        db = MagicMock()
        query_chain = MagicMock()
        query_chain.where.return_value = query_chain
        query_chain.limit.return_value = query_chain
        snap = MagicMock()
        snap.exists = True
        snap.to_dict.return_value = row
        query_chain.get.return_value = [snap]
        db.collection_group.return_value = query_chain
        db.document.return_value.update = MagicMock()

        svc = _make_svc(db)
        result = svc.assign_category("user_1", "sess_1", None)
        assert result.category_id is None

    def test_search_text_excludes_category_name_after_unassign(self) -> None:
        row = _base_session_row()
        row["title"] = "My Session"
        row["latest_summary"] = None
        row["category_id"] = "cat_old"

        db = MagicMock()
        query_chain = MagicMock()
        query_chain.where.return_value = query_chain
        query_chain.limit.return_value = query_chain
        snap = MagicMock()
        snap.exists = True
        snap.to_dict.return_value = row
        query_chain.get.return_value = [snap]
        db.collection_group.return_value = query_chain
        db.document.return_value.update = MagicMock()

        svc = _make_svc(db)
        result = svc.assign_category("user_1", "sess_1", None)
        # search_text should only contain the title — no category name
        assert result.search_text == "my session"
        # No "Paid Media" or similar fragment
        assert "cat_old" not in result.search_text

    def test_no_category_doc_read_on_unassign(self) -> None:
        """When category_id is None, the category doc must not be read."""
        row = _base_session_row()
        db = MagicMock()
        query_chain = MagicMock()
        query_chain.where.return_value = query_chain
        query_chain.limit.return_value = query_chain
        snap = MagicMock()
        snap.exists = True
        snap.to_dict.return_value = row
        query_chain.get.return_value = [snap]
        db.collection_group.return_value = query_chain
        db.document.return_value.update = MagicMock()

        svc = _make_svc(db)
        svc.assign_category("user_1", "sess_1", None)

        # db.document should be called exactly once (for the session update path)
        # — NOT for a category read.
        assert db.document.call_count == 1


class TestDeleteCategoryBatching:
    """Verify that delete_category creates the correct number of transactions."""

    def test_zero_sessions_one_transaction(self) -> None:
        db = _make_db_for_delete([])
        svc = _make_svc(db)
        result = svc.delete_category("u1", "cat_abc")
        assert result == DeleteCategoryResult(category_id="cat_abc", sessions_reassigned=0)
        assert db.transaction.call_count == 1

    def test_one_session_one_transaction_fused(self) -> None:
        db = _make_db_for_delete([_make_snap()])
        svc = _make_svc(db)
        result = svc.delete_category("u1", "cat_abc")
        assert result == DeleteCategoryResult(category_id="cat_abc", sessions_reassigned=1)
        assert db.transaction.call_count == 1

    def test_400_sessions_one_transaction_boundary(self) -> None:
        snaps = [_make_snap() for _ in range(400)]
        db = _make_db_for_delete(snaps)
        svc = _make_svc(db)
        result = svc.delete_category("u1", "cat_abc")
        assert result.sessions_reassigned == 400
        assert db.transaction.call_count == 1

    def test_401_sessions_two_transactions(self) -> None:
        snaps = [_make_snap() for _ in range(401)]
        db = _make_db_for_delete(snaps)
        svc = _make_svc(db)
        result = svc.delete_category("u1", "cat_abc")
        assert result.sessions_reassigned == 401
        assert db.transaction.call_count == 2

    def test_800_sessions_two_transactions(self) -> None:
        snaps = [_make_snap() for _ in range(800)]
        db = _make_db_for_delete(snaps)
        svc = _make_svc(db)
        result = svc.delete_category("u1", "cat_abc")
        assert result.sessions_reassigned == 800
        assert db.transaction.call_count == 2

    def test_returns_delete_category_result_type(self) -> None:
        db = _make_db_for_delete([_make_snap()])
        svc = _make_svc(db)
        result = svc.delete_category("u1", "cat_abc")
        assert isinstance(result, DeleteCategoryResult)

    def test_result_category_id_matches_input(self) -> None:
        db = _make_db_for_delete([])
        svc = _make_svc(db)
        result = svc.delete_category("u1", "cat_xyz")
        assert result.category_id == "cat_xyz"

    def test_collection_group_queried_with_correct_filters(self) -> None:
        db = _make_db_for_delete([])
        svc = _make_svc(db)
        svc.delete_category("u1", "cat_abc")
        db.collection_group.assert_called_once_with("chat_sessions")
        assert db.collection_group.return_value.where.call_count == 2

    def test_tombstoned_sessions_excluded_from_count(self) -> None:
        from datetime import datetime, timezone

        live = _make_snap()
        tombstoned = _make_snap(deleted_at=datetime.now(timezone.utc))
        db = _make_db_for_delete([live, tombstoned])
        svc = _make_svc(db)
        result = svc.delete_category("u1", "cat_abc")
        assert result.sessions_reassigned == 1

    def test_tombstoned_sessions_not_updated(self) -> None:
        from datetime import datetime, timezone

        live = _make_snap()
        tombstoned = _make_snap(deleted_at=datetime.now(timezone.utc))
        db = _make_db_for_delete([live, tombstoned])
        svc = _make_svc(db)
        svc.delete_category("u1", "cat_abc")
        tx = db.transaction.return_value
        assert tx.update.call_count == 1


# ---------------------------------------------------------------------------
# delete_category — write payload verification
# ---------------------------------------------------------------------------


class TestDeleteCategoryWritePayloads:
    """Verify the exact fields written to each affected session and to the category doc."""

    def _run_delete(
        self,
        snaps: list[MagicMock],
        *,
        user_id: str = "u1",
        category_id: str = "cat_abc",
    ) -> tuple[MagicMock, DeleteCategoryResult]:
        db = _make_db_for_delete(snaps)
        svc = _make_svc(db)
        result = svc.delete_category(user_id, category_id)
        return db, result

    def test_update_clears_category_id_with_delete_field(self) -> None:
        snap = _make_snap(title="My Session")
        db, _ = self._run_delete([snap])
        tx = db.transaction.return_value
        payload = tx.update.call_args[0][1]
        assert payload["category_id"] is _fs.DELETE_FIELD

    def test_update_includes_updated_at(self) -> None:
        snap = _make_snap()
        db, _ = self._run_delete([snap])
        tx = db.transaction.return_value
        payload = tx.update.call_args[0][1]
        assert "updated_at" in payload

    def test_update_includes_search_text(self) -> None:
        snap = _make_snap(title="My Session")
        db, _ = self._run_delete([snap])
        tx = db.transaction.return_value
        payload = tx.update.call_args[0][1]
        assert "search_text" in payload

    def test_search_text_recomputed_without_category(self) -> None:
        snap = _make_snap(title="Q3 Plan", latest_summary="draft")
        db, _ = self._run_delete([snap])
        tx = db.transaction.return_value
        payload = tx.update.call_args[0][1]
        # Formula: casefold(title + summary), no category
        assert payload["search_text"] == "q3 plan draft"

    def test_search_text_title_only_when_no_summary(self) -> None:
        snap = _make_snap(title="Alpha", latest_summary=None)
        db, _ = self._run_delete([snap])
        tx = db.transaction.return_value
        payload = tx.update.call_args[0][1]
        assert payload["search_text"] == "alpha"

    def test_tx_delete_called_once_for_category_doc(self) -> None:
        snaps = [_make_snap()]
        db, _ = self._run_delete(snaps)
        tx = db.transaction.return_value
        tx.delete.assert_called_once()

    def test_tx_delete_called_on_correct_category_ref(self) -> None:
        db = _make_db_for_delete([_make_snap()])
        category_ref = MagicMock()
        db.document.return_value = category_ref
        svc = _make_svc(db)
        svc.delete_category("u1", "cat_abc")
        tx = db.transaction.return_value
        tx.delete.assert_called_once_with(category_ref)

    def test_zero_sessions_no_tx_update_only_delete(self) -> None:
        db = _make_db_for_delete([])
        svc = _make_svc(db)
        svc.delete_category("u1", "cat_abc")
        tx = db.transaction.return_value
        tx.update.assert_not_called()
        tx.delete.assert_called_once()

    def test_update_called_once_per_affected_session(self) -> None:
        snaps = [_make_snap() for _ in range(3)]
        db = _make_db_for_delete(snaps)
        svc = _make_svc(db)
        svc.delete_category("u1", "cat_abc")
        tx = db.transaction.return_value
        assert tx.update.call_count == 3

    def test_update_targets_snap_reference(self) -> None:
        snap = _make_snap()
        db, _ = self._run_delete([snap])
        tx = db.transaction.return_value
        ref_arg = tx.update.call_args[0][0]
        assert ref_arg is snap.reference
