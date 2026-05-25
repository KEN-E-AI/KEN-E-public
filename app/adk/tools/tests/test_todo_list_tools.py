"""Unit tests for ``app.adk.tools.todo_list_tools`` (CH-PRD-05 #1).

Covers PRD §7 AC-1 through AC-5:
  AC-1  set_todo_list writes the expected shape
  AC-2  update_todo_list flips item + stamps completed_at
  AC-3  single-current invariant
  AC-4  20-list and 50-item caps with exact error strings
  AC-5  registry wiring: ToolRegistry.list_default_global_tools() returns both tools
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from types import SimpleNamespace
from typing import Any

import pytest

from app.adk.tools.registry.function_tool_registry import (
    clear_function_tool_registry,
    get_function_tool,
)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _fake_ctx(initial_state: dict[str, Any] | None = None) -> SimpleNamespace:
    """Return a minimal ToolContext stand-in with a ``.state`` dict."""
    return SimpleNamespace(state=dict(initial_state or {}))


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Registry teardown — prevent leakage across test classes
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registry() -> Generator[None, None, None]:
    """Clear the process-global function-tool registry before and after each test."""
    clear_function_tool_registry()
    # Re-import so the registration side effects re-fire in a clean registry.
    import importlib

    import app.adk.tools.todo_list_tools

    importlib.reload(app.adk.tools.todo_list_tools)
    yield
    clear_function_tool_registry()


# ---------------------------------------------------------------------------
# Convenience imports after fixture wires the reload
# ---------------------------------------------------------------------------


def _get_tools() -> tuple[Any, Any]:
    from app.adk.tools.todo_list_tools import set_todo_list, update_todo_list

    return set_todo_list, update_todo_list


# ---------------------------------------------------------------------------
# TestSetTodoListHappyPath — AC-1
# ---------------------------------------------------------------------------


class TestSetTodoListHappyPath:
    def test_writes_expected_shape(self) -> None:
        set_todo_list, _ = _get_tools()
        ctx = _fake_ctx()
        result = _run(
            set_todo_list(
                ctx,
                list_id="list_001",
                title="Research Phase",
                items=[{"text": "Gather data"}],
                is_current=False,
            )
        )
        assert result == "Todo list 'Research Phase' set with 1 items."
        lists = ctx.state["todo_lists"]
        assert "list_001" in lists
        entry = lists["list_001"]
        assert entry["list_id"] == "list_001"
        assert entry["title"] == "Research Phase"
        assert entry["is_current"] is False
        assert "created_at" in entry
        assert isinstance(entry["created_at"], str)
        assert "T" in entry["created_at"]  # ISO-8601

    def test_normalizes_items_with_auto_item_id(self) -> None:
        set_todo_list, _ = _get_tools()
        ctx = _fake_ctx()
        _run(
            set_todo_list(
                ctx,
                list_id="l1",
                title="T",
                items=[{"text": "step one"}, {"text": "step two"}],
            )
        )
        items = ctx.state["todo_lists"]["l1"]["items"]
        assert items[0]["item_id"] == "item_000"
        assert items[1]["item_id"] == "item_001"

    def test_preserves_caller_supplied_item_id(self) -> None:
        set_todo_list, _ = _get_tools()
        ctx = _fake_ctx()
        _run(
            set_todo_list(
                ctx,
                list_id="l1",
                title="T",
                items=[{"item_id": "custom_id", "text": "step"}],
            )
        )
        assert ctx.state["todo_lists"]["l1"]["items"][0]["item_id"] == "custom_id"

    def test_items_default_completed_false(self) -> None:
        set_todo_list, _ = _get_tools()
        ctx = _fake_ctx()
        _run(
            set_todo_list(
                ctx,
                list_id="l1",
                title="T",
                items=[{"text": "step"}],
            )
        )
        item = ctx.state["todo_lists"]["l1"]["items"][0]
        assert item["completed"] is False
        assert item["completed_at"] is None

    def test_replaces_existing_list(self) -> None:
        set_todo_list, _ = _get_tools()
        ctx = _fake_ctx()
        _run(set_todo_list(ctx, list_id="l1", title="Old", items=[{"text": "x"}]))
        _run(
            set_todo_list(
                ctx,
                list_id="l1",
                title="New",
                items=[{"text": "a"}, {"text": "b"}],
            )
        )
        entry = ctx.state["todo_lists"]["l1"]
        assert entry["title"] == "New"
        assert len(entry["items"]) == 2

    def test_is_current_true_stored(self) -> None:
        set_todo_list, _ = _get_tools()
        ctx = _fake_ctx()
        _run(
            set_todo_list(
                ctx,
                list_id="l1",
                title="Current",
                items=[],
                is_current=True,
            )
        )
        assert ctx.state["todo_lists"]["l1"]["is_current"] is True


# ---------------------------------------------------------------------------
# TestIsCurrentInvariant — AC-3
# ---------------------------------------------------------------------------


class TestIsCurrentInvariant:
    def test_setting_new_current_clears_previous(self) -> None:
        set_todo_list, _ = _get_tools()
        ctx = _fake_ctx()
        _run(set_todo_list(ctx, "l1", "List A", [], is_current=True))
        _run(set_todo_list(ctx, "l2", "List B", [], is_current=True))
        lists = ctx.state["todo_lists"]
        assert lists["l1"]["is_current"] is False
        assert lists["l2"]["is_current"] is True

    def test_no_two_lists_current_after_multiple_flips(self) -> None:
        set_todo_list, _ = _get_tools()
        ctx = _fake_ctx()
        for name in ("A", "B", "C", "B", "A"):
            _run(
                set_todo_list(
                    ctx,
                    list_id=f"l_{name}",
                    title=name,
                    items=[],
                    is_current=True,
                )
            )
        current_lists = [
            k for k, v in ctx.state["todo_lists"].items() if v.get("is_current")
        ]
        assert len(current_lists) == 1

    def test_updating_current_list_preserves_its_is_current_true(self) -> None:
        set_todo_list, _ = _get_tools()
        ctx = _fake_ctx()
        _run(set_todo_list(ctx, "l1", "Old Title", [], is_current=True))
        _run(set_todo_list(ctx, "l1", "New Title", [], is_current=True))
        assert ctx.state["todo_lists"]["l1"]["is_current"] is True

    def test_non_current_lists_stay_false_after_creation(self) -> None:
        set_todo_list, _ = _get_tools()
        ctx = _fake_ctx()
        _run(set_todo_list(ctx, "l1", "A", [], is_current=False))
        _run(set_todo_list(ctx, "l2", "B", [], is_current=False))
        for k, v in ctx.state["todo_lists"].items():
            assert v["is_current"] is False, f"{k} unexpectedly current"


# ---------------------------------------------------------------------------
# TestListCap — AC-4 (20-list cap)
# ---------------------------------------------------------------------------


class TestListCap:
    def _fill_to_max(self, ctx: SimpleNamespace) -> None:
        set_todo_list, _ = _get_tools()
        from app.adk.tools.todo_list_tools import MAX_LISTS_PER_SESSION

        for i in range(MAX_LISTS_PER_SESSION):
            result = _run(set_todo_list(ctx, f"list_{i:03d}", f"List {i}", []))
            assert "ERROR" not in result

    def test_20_lists_succeed(self) -> None:
        ctx = _fake_ctx()
        self._fill_to_max(ctx)
        from app.adk.tools.todo_list_tools import MAX_LISTS_PER_SESSION

        assert len(ctx.state["todo_lists"]) == MAX_LISTS_PER_SESSION

    def test_21st_list_returns_error(self) -> None:
        set_todo_list, _ = _get_tools()
        ctx = _fake_ctx()
        self._fill_to_max(ctx)
        result = _run(set_todo_list(ctx, "overflow", "Overflow", []))
        assert result.startswith("ERROR:")
        assert "20 todo lists" in result

    def test_21st_list_does_not_mutate_state(self) -> None:
        set_todo_list, _ = _get_tools()
        ctx = _fake_ctx()
        self._fill_to_max(ctx)
        from app.adk.tools.todo_list_tools import MAX_LISTS_PER_SESSION

        _run(set_todo_list(ctx, "overflow", "Overflow", []))
        assert len(ctx.state["todo_lists"]) == MAX_LISTS_PER_SESSION

    def test_updating_existing_list_bypasses_cap(self) -> None:
        set_todo_list, _ = _get_tools()
        ctx = _fake_ctx()
        self._fill_to_max(ctx)
        # Updating list_000 (already exists) should succeed even at cap.
        result = _run(
            set_todo_list(ctx, "list_000", "Updated Title", [{"text": "new item"}])
        )
        assert "ERROR" not in result
        assert ctx.state["todo_lists"]["list_000"]["title"] == "Updated Title"


# ---------------------------------------------------------------------------
# TestItemCap — AC-4 (50-item cap)
# ---------------------------------------------------------------------------


class TestItemCap:
    def test_50_items_succeed(self) -> None:
        set_todo_list, _ = _get_tools()
        from app.adk.tools.todo_list_tools import MAX_ITEMS_PER_LIST

        ctx = _fake_ctx()
        items = [{"text": f"item {i}"} for i in range(MAX_ITEMS_PER_LIST)]
        result = _run(set_todo_list(ctx, "l1", "Big List", items))
        assert "ERROR" not in result
        assert len(ctx.state["todo_lists"]["l1"]["items"]) == MAX_ITEMS_PER_LIST

    def test_51_items_returns_error(self) -> None:
        set_todo_list, _ = _get_tools()
        from app.adk.tools.todo_list_tools import MAX_ITEMS_PER_LIST

        ctx = _fake_ctx()
        items = [{"text": f"item {i}"} for i in range(MAX_ITEMS_PER_LIST + 1)]
        result = _run(set_todo_list(ctx, "l1", "Too Big", items))
        assert result.startswith("ERROR:")
        assert "50 items" in result

    def test_51_items_does_not_mutate_state(self) -> None:
        set_todo_list, _ = _get_tools()
        from app.adk.tools.todo_list_tools import MAX_ITEMS_PER_LIST

        ctx = _fake_ctx()
        items = [{"text": f"item {i}"} for i in range(MAX_ITEMS_PER_LIST + 1)]
        _run(set_todo_list(ctx, "l1", "Too Big", items))
        assert "l1" not in ctx.state.get("todo_lists", {})


# ---------------------------------------------------------------------------
# TestInputValidation — defensive guards added in review
# ---------------------------------------------------------------------------


class TestInputValidation:
    def test_item_missing_text_returns_error(self) -> None:
        set_todo_list, _ = _get_tools()
        ctx = _fake_ctx()
        result = _run(set_todo_list(ctx, "l1", "T", [{"item_id": "x"}]))
        assert result.startswith("ERROR:")
        assert "text" in result

    def test_item_missing_text_does_not_mutate_state(self) -> None:
        set_todo_list, _ = _get_tools()
        ctx = _fake_ctx()
        _run(set_todo_list(ctx, "l1", "T", [{"item_id": "x"}]))
        assert "l1" not in ctx.state.get("todo_lists", {})

    def test_item_empty_text_returns_error(self) -> None:
        set_todo_list, _ = _get_tools()
        ctx = _fake_ctx()
        result = _run(set_todo_list(ctx, "l1", "T", [{"text": ""}]))
        assert result.startswith("ERROR:")

    def test_item_id_absent_uses_positional_fallback(self) -> None:
        """item.get("item_id", f"item_{i:03d}") — absent key falls back; empty
        string does NOT fall back (matches PRD §5.4 Decision D-8)."""
        set_todo_list, _ = _get_tools()
        ctx = _fake_ctx()
        _run(set_todo_list(ctx, "l1", "T", [{"text": "step"}]))
        assert ctx.state["todo_lists"]["l1"]["items"][0]["item_id"] == "item_000"

    def test_item_id_empty_string_stored_as_empty(self) -> None:
        """An explicit item_id="" is stored verbatim (not replaced with
        auto-generated ID) — callers must supply valid IDs."""
        set_todo_list, _ = _get_tools()
        ctx = _fake_ctx()
        _run(set_todo_list(ctx, "l1", "T", [{"item_id": "", "text": "step"}]))
        assert ctx.state["todo_lists"]["l1"]["items"][0]["item_id"] == ""

    def test_created_at_preserved_on_replace(self) -> None:
        set_todo_list, _ = _get_tools()
        ctx = _fake_ctx()
        _run(set_todo_list(ctx, "l1", "Old Title", [{"text": "x"}]))
        original_created_at = ctx.state["todo_lists"]["l1"]["created_at"]
        _run(set_todo_list(ctx, "l1", "New Title", [{"text": "y"}]))
        assert ctx.state["todo_lists"]["l1"]["created_at"] == original_created_at


# ---------------------------------------------------------------------------
# TestUpdateTodoListItem — AC-2
# ---------------------------------------------------------------------------


class TestUpdateTodoListItem:
    def _ctx_with_list(self) -> SimpleNamespace:
        set_todo_list, _ = _get_tools()
        ctx = _fake_ctx()
        _run(
            set_todo_list(
                ctx,
                list_id="l1",
                title="Test List",
                items=[
                    {"item_id": "i1", "text": "Do thing A"},
                    {"item_id": "i2", "text": "Do thing B"},
                ],
            )
        )
        return ctx

    def test_check_item_flips_completed_and_stamps_completed_at(self) -> None:
        _, update_todo_list = _get_tools()
        ctx = self._ctx_with_list()
        result = _run(update_todo_list(ctx, "l1", "i1", completed=True))
        assert "ERROR" not in result
        item = ctx.state["todo_lists"]["l1"]["items"][0]
        assert item["completed"] is True
        assert item["completed_at"] is not None
        assert "T" in item["completed_at"]  # ISO-8601

    def test_uncheck_item_clears_completed_at(self) -> None:
        _, update_todo_list = _get_tools()
        ctx = self._ctx_with_list()
        _run(update_todo_list(ctx, "l1", "i1", completed=True))
        _run(update_todo_list(ctx, "l1", "i1", completed=False))
        item = ctx.state["todo_lists"]["l1"]["items"][0]
        assert item["completed"] is False
        assert item["completed_at"] is None

    def test_only_target_item_is_modified(self) -> None:
        _, update_todo_list = _get_tools()
        ctx = self._ctx_with_list()
        _run(update_todo_list(ctx, "l1", "i1", completed=True))
        item_b = ctx.state["todo_lists"]["l1"]["items"][1]
        assert item_b["completed"] is False

    def test_optional_text_rename(self) -> None:
        _, update_todo_list = _get_tools()
        ctx = self._ctx_with_list()
        _run(update_todo_list(ctx, "l1", "i1", completed=False, text="Renamed A"))
        item = ctx.state["todo_lists"]["l1"]["items"][0]
        assert item["text"] == "Renamed A"

    def test_missing_list_id_returns_error(self) -> None:
        _, update_todo_list = _get_tools()
        ctx = self._ctx_with_list()
        result = _run(update_todo_list(ctx, "no_such_list", "i1", completed=True))
        assert result.startswith("ERROR:")
        assert "no_such_list" in result

    def test_missing_item_id_returns_error(self) -> None:
        _, update_todo_list = _get_tools()
        ctx = self._ctx_with_list()
        result = _run(update_todo_list(ctx, "l1", "no_such_item", completed=True))
        assert result.startswith("ERROR:")
        assert "no_such_item" in result
        assert "l1" in result

    def test_state_unchanged_on_missing_list(self) -> None:
        _, update_todo_list = _get_tools()
        ctx = self._ctx_with_list()
        before = dict(ctx.state["todo_lists"]["l1"])
        _run(update_todo_list(ctx, "missing", "i1", completed=True))
        assert ctx.state["todo_lists"]["l1"] == before


# ---------------------------------------------------------------------------
# TestRegistryWiring — AC-5
# ---------------------------------------------------------------------------


class TestRegistryWiring:
    def test_both_tools_retrievable_from_registry(self) -> None:
        from google.adk.tools.function_tool import FunctionTool

        ft_set = get_function_tool("set_todo_list")
        ft_update = get_function_tool("update_todo_list")
        assert isinstance(ft_set, FunctionTool)
        assert isinstance(ft_update, FunctionTool)

    def test_registered_name_matches_tool_name(self) -> None:
        ft_set = get_function_tool("set_todo_list")
        ft_update = get_function_tool("update_todo_list")
        assert ft_set.name == "set_todo_list"
        assert ft_update.name == "update_todo_list"

    def test_underlying_func_name_matches_registered_name(self) -> None:
        """ADK builds FunctionDeclaration from func.__name__; it must match
        the dict key to avoid Gemini tool-call misses (mirrors the alignment
        contract in test_function_tool_registry.py)."""
        ft_set = get_function_tool("set_todo_list")
        ft_update = get_function_tool("update_todo_list")
        assert ft_set.func.__name__ == "set_todo_list"
        assert ft_update.func.__name__ == "update_todo_list"

    def test_function_declaration_advertises_registered_name(self) -> None:
        """End-to-end alignment: the FunctionDeclaration Gemini receives must
        carry the registered name."""
        ft_set = get_function_tool("set_todo_list")
        ft_update = get_function_tool("update_todo_list")
        decl_set = ft_set._get_declaration()
        decl_update = ft_update._get_declaration()
        assert decl_set is not None
        assert decl_set.name == "set_todo_list"
        assert decl_update is not None
        assert decl_update.name == "update_todo_list"

    def test_list_default_global_tools_includes_both(self) -> None:
        """ToolRegistry.list_default_global_tools() must return both tools
        so the agent factory wires them onto every specialist."""
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        from app.adk.tools.registry.function_tool_registry import (
            resolve_default_global_tools,
        )

        # Fake registry whose catalogue lists all three default-global tools.
        registry = MagicMock()
        registry.list_default_global_tools.return_value = [
            SimpleNamespace(name="create_visualization"),
            SimpleNamespace(name="set_todo_list"),
            SimpleNamespace(name="update_todo_list"),
        ]

        # create_visualization has no registered callable in this test context,
        # so it will be skipped — but both todo-list tools must resolve.
        resolved_names = {t.name for t in resolve_default_global_tools(registry)}
        assert "set_todo_list" in resolved_names
        assert "update_todo_list" in resolved_names
