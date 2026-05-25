"""Table-driven unit tests for _validate_todo_list_entry (CH-41).

References: CH-PRD-05 §4.1, §7 AC-5.
"""

from __future__ import annotations

import pytest
from src.kene_api.chat.todos import _validate_todo_list_entry
from src.kene_api.models.chat import TodoList

# ---------------------------------------------------------------------------
# Valid case
# ---------------------------------------------------------------------------


class TestValidEntry:
    def test_valid_dict_returns_todo_list(self) -> None:
        raw = {
            "list_id": "list_001",
            "title": "My Tasks",
            "is_current": True,
            "created_at": "2026-04-01T10:00:00Z",
            "items": [
                {
                    "item_id": "item_001",
                    "text": "Do thing",
                    "completed": False,
                    "completed_at": None,
                }
            ],
        }
        result = _validate_todo_list_entry(raw)
        assert isinstance(result, TodoList)
        assert result.list_id == "list_001"
        assert result.title == "My Tasks"
        assert result.is_current is True
        assert len(result.items) == 1
        assert result.items[0].item_id == "item_001"


# ---------------------------------------------------------------------------
# Missing required fields
# ---------------------------------------------------------------------------


class TestMissingRequiredFields:
    def test_missing_list_id_returns_none(self) -> None:
        raw = {"title": "No ID"}
        result = _validate_todo_list_entry(raw)
        assert result is None

    def test_missing_title_returns_none(self) -> None:
        raw = {"list_id": "list_001"}
        result = _validate_todo_list_entry(raw)
        assert result is None


# ---------------------------------------------------------------------------
# Non-dict inputs
# ---------------------------------------------------------------------------


class TestNonDictInputs:
    @pytest.mark.parametrize(
        "raw",
        [
            None,
            [],
            ["list_001", "title"],
            "string_value",
            42,
        ],
    )
    def test_non_dict_returns_none(self, raw: object) -> None:
        result = _validate_todo_list_entry(raw)
        assert result is None


# ---------------------------------------------------------------------------
# Wrong type for items field
# ---------------------------------------------------------------------------


class TestWrongItemsType:
    def test_items_as_string_returns_none(self) -> None:
        raw = {
            "list_id": "list_001",
            "title": "Bad Items",
            "items": "not_a_list",
        }
        result = _validate_todo_list_entry(raw)
        assert result is None

    def test_items_as_int_returns_none(self) -> None:
        raw = {
            "list_id": "list_001",
            "title": "Bad Items",
            "items": 999,
        }
        result = _validate_todo_list_entry(raw)
        assert result is None

    def test_items_as_dict_returns_none(self) -> None:
        raw = {
            "list_id": "list_001",
            "title": "Bad Items",
            "items": {"not": "a list"},
        }
        result = _validate_todo_list_entry(raw)
        assert result is None


# ---------------------------------------------------------------------------
# Non-string list_id coercion
# ---------------------------------------------------------------------------


class TestNonStringListId:
    def test_integer_list_id_rejected_by_pydantic_v2(self) -> None:
        """Pydantic v2 with strict str fields rejects int list_id — returns None, no exception."""
        raw = {"list_id": 42, "title": "Int ID"}
        result = _validate_todo_list_entry(raw)
        assert result is None


# ---------------------------------------------------------------------------
# Comprehensive malformed shapes table (6 malformed + 1 valid)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expect_none",
    [
        # 1. Missing list_id
        ({"title": "No ID"}, True),
        # 2. Missing title
        ({"list_id": "list_001"}, True),
        # 3. None input
        (None, True),
        # 4. List input
        ([], True),
        # 5. String input
        ("bad_string", True),
        # 6. items is a string
        ({"list_id": "list_001", "title": "Bad Items", "items": "nope"}, True),
        # 7. Valid entry
        (
            {
                "list_id": "list_ok",
                "title": "Good",
                "is_current": False,
                "items": [],
            },
            False,
        ),
    ],
)
def test_table_driven_validation(raw: object, expect_none: bool) -> None:
    result = _validate_todo_list_entry(raw)
    if expect_none:
        assert result is None
    else:
        assert isinstance(result, TodoList)
