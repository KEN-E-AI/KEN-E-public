"""ADK FunctionTools for managing session.state["todo_lists"].

Write side of the todo-list feature. The read path (chat/todos.py + GET /todos)
lives in the API tier.

Persistence is automatic through ADK's session-service state mechanism — there
are no direct Firestore writes here. ``tool_context.state["todo_lists"]`` is a
dict-of-dicts keyed by ``list_id``; each value matches the ``TodoList`` shape
in ``api/src/kene_api/models/chat.py``.

Registration: both tools call ``register_function_tool`` at module-bottom so the
side-effect fires when ``hierarchy.py`` imports this module at startup.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.adk.tools.registry.function_tool_registry import register_function_tool

MAX_LISTS_PER_SESSION: int = 20
MAX_ITEMS_PER_LIST: int = 50

_TODO_LISTS_KEY: str = "todo_lists"

_MAX_LIST_ID_LEN: int = 128
_MAX_TITLE_LEN: int = 256
_MAX_ITEM_ID_LEN: int = 128
_MAX_ITEM_TEXT_LEN: int = 1024


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_items(
    raw_items: list[dict[str, Any]],
) -> list[dict[str, Any]] | str:
    """Return a normalized copy of the caller's item list, or an ERROR string.

    Guarantees every item has ``item_id``, ``text``, ``completed``, and
    ``completed_at`` — matching the ``TodoItem`` Pydantic shape in
    ``api/src/kene_api/models/chat.py``. A missing ``item_id`` falls back to
    ``"item_{i:03d}"`` (zero-indexed); an explicit empty string is preserved.
    """
    normalized: list[dict[str, Any]] = []
    for i, item in enumerate(raw_items):
        text = item.get("text")
        if not isinstance(text, str) or not text:
            return f"ERROR: item at index {i} is missing a non-empty 'text' field."
        item_id = item.get("item_id", f"item_{i:03d}")
        if len(item_id) > _MAX_ITEM_ID_LEN:
            return f"ERROR: item_id at index {i} exceeds {_MAX_ITEM_ID_LEN} characters."
        if len(text) > _MAX_ITEM_TEXT_LEN:
            return f"ERROR: text at index {i} exceeds {_MAX_ITEM_TEXT_LEN} characters."
        raw_cat = item.get("completed_at")
        completed_at = raw_cat if isinstance(raw_cat, str) or raw_cat is None else None
        normalized.append(
            {
                "item_id": item_id,
                "text": text,
                "completed": bool(item.get("completed", False)),
                "completed_at": completed_at,
            }
        )
    return normalized


# ---------------------------------------------------------------------------
# Tool callables
# ---------------------------------------------------------------------------


async def set_todo_list(
    tool_context: Any,
    list_id: str,
    title: str,
    items: list[dict[str, Any]],
    is_current: bool = False,
) -> str:
    """Create or replace a todo list in the session.

    Enforces a 20-list cap per session and a 50-item cap per list.  When
    ``is_current=True`` any other list previously marked current is cleared to
    ``False`` — at most one list is current at any time.

    Args:
        tool_context: ADK ToolContext (carries ``.state``).
        list_id: Unique identifier for this list within the session.
        title: Human-readable list title shown in the UI.
        items: List of item dicts; each should carry ``text`` at minimum.
            Missing ``item_id`` values are auto-generated.
        is_current: Mark this list as the active/current list.

    Returns:
        Confirmation string on success; ``"ERROR: ..."`` string on cap
        violation or validation failure (the agent can recover and adjust
        rather than crashing).
    """
    if len(list_id) > _MAX_LIST_ID_LEN:
        return f"ERROR: list_id exceeds {_MAX_LIST_ID_LEN} characters."
    if len(title) > _MAX_TITLE_LEN:
        return f"ERROR: title exceeds {_MAX_TITLE_LEN} characters."
    if len(items) > MAX_ITEMS_PER_LIST:
        return f"ERROR: todo list capped at {MAX_ITEMS_PER_LIST} items."

    normalized = _normalize_items(items)
    if isinstance(normalized, str):
        return normalized  # propagate item-level validation error

    existing: dict[str, Any] = tool_context.state.get(_TODO_LISTS_KEY) or {}

    # Cap check: only applies when creating a *new* list_id.
    if list_id not in existing and len(existing) >= MAX_LISTS_PER_SESSION:
        return (
            f"ERROR: session has {MAX_LISTS_PER_SESSION} todo lists already; "
            "archive or remove one."
        )

    if is_current:
        # Clear any previously current list.
        for other_id, other_list in existing.items():
            if other_id != list_id and other_list.get("is_current"):
                other_list["is_current"] = False

    # Preserve created_at so list sort order in the read path stays stable.
    prior_created_at = existing.get(list_id, {}).get("created_at")
    existing[list_id] = {
        "list_id": list_id,
        "title": title,
        "is_current": is_current,
        "created_at": prior_created_at or _now_iso(),
        "items": normalized,
    }
    tool_context.state[_TODO_LISTS_KEY] = existing
    return f"Todo list '{title}' set with {len(normalized)} items."


async def update_todo_list(
    tool_context: Any,
    list_id: str,
    item_id: str,
    completed: bool,
    text: str | None = None,
) -> str:
    """Check or uncheck a single item in an existing todo list.

    Stamps ``completed_at`` when flipping to ``True`` and clears it when
    flipping to ``False``.  Optionally renames the item via ``text``.

    Args:
        tool_context: ADK ToolContext (carries ``.state``).
        list_id: Identifier of the list containing the item.
        item_id: Identifier of the item to update.
        completed: New completion state for the item.
        text: Optional new text for the item (rename).

    Returns:
        Confirmation string on success; ``"ERROR: ..."`` string when the list
        or item is not found.
    """
    if text is not None and len(text) > _MAX_ITEM_TEXT_LEN:
        return f"ERROR: text exceeds {_MAX_ITEM_TEXT_LEN} characters."

    existing: dict[str, Any] = tool_context.state.get(_TODO_LISTS_KEY) or {}

    if list_id not in existing:
        return f"ERROR: list_id {list_id} not found."

    todo_list = existing[list_id]
    items: list[dict[str, Any]] = todo_list.get("items", [])

    target_item: dict[str, Any] | None = None
    for item in items:
        if item.get("item_id") == item_id:
            target_item = item
            break

    if target_item is None:
        return f"ERROR: item_id {item_id} not found in list {list_id}."

    target_item["completed"] = completed
    if completed:
        target_item["completed_at"] = _now_iso()
    else:
        target_item["completed_at"] = None

    if text is not None:
        target_item["text"] = text

    tool_context.state[_TODO_LISTS_KEY] = existing
    action = "checked" if completed else "unchecked"
    return f"Item '{item_id}' in list '{list_id}' {action}."


# ---------------------------------------------------------------------------
# Registry wiring (side-effect on import)
# ---------------------------------------------------------------------------

register_function_tool("set_todo_list", set_todo_list)
register_function_tool("update_todo_list", update_todo_list)
