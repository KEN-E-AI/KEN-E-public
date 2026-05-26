"""Unit tests for ChatCategoryService — happy path, name stripping, list ordering.

Pure-logic unit tests (T-4): Firestore client is mocked with MagicMock.
No emulator dependency. Covers: create_category, list_categories, singleton factory.
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock

import pytest
from src.kene_api.chat.categories import (
    ChatCategoryService,
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
