"""ADK FunctionTools for managing session.state["todo_lists"].

Write side of the todo-list feature. The read path (chat/todos.py + GET /todos)
lives in the API tier.

Persistence is automatic through ADK's session-service state mechanism — there
are no direct Firestore writes here. ``tool_context.state["todo_lists"]`` is a
dict-of-dicts keyed by ``list_id``; each value matches the ``TodoList`` shape
in ``api/src/kene_api/models/chat.py``.

Registration: all tools call ``register_function_tool`` at module-bottom so the
side-effect fires when ``hierarchy.py`` imports this module at startup.
"""

from __future__ import annotations

import json
import re
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
_MAX_QUERY_LEN: int = 4096
_MAX_CRITERIA_LEN: int = 2048
_MAX_RESULT_KEY_LEN: int = 128

# ``result_key`` names the session.state slot a specialist writes its output to,
# and the value is chosen by the coordinator LLM. Validate it as an allowlist (a
# naming convention) rather than a denylist of sensitive keys — a denylist is
# inherently incomplete against an LLM-chosen name and silently grows stale as
# new state keys land. The convention closes the two open-ended families:
#   * ``_RESULT_KEY_PATTERN`` requires lowercase, leading letter, no leading
#     underscore — rejecting every internal/ADK key (all ``_``-prefixed) and any
#     name with surprising characters.
#   * ``_SENSITIVE_KEY_SUBSTRINGS`` rejects the open-ended credential/secret
#     family (``ga_credentials``, future ``*_token`` keys, …).
# ``_RESERVED_STATE_KEYS`` is then only the small, closed set of plain-named app
# keys the convention cannot catch on its own.
_RESULT_KEY_PATTERN: re.Pattern[str] = re.compile(r"^[a-z][a-z0-9_]*$")

_SENSITIVE_KEY_SUBSTRINGS: tuple[str, ...] = (
    "credential",
    "cred",
    "token",
    "secret",
    "password",
    "api_key",
    "apikey",
)

# Session-state key for the approval-checkpoint continuation (AH-144). Defined
# here — the module that owns save/resume/clear — as the single source of truth;
# supervisor.py imports it rather than re-declaring the literal.
_PENDING_SUPERVISOR_TASKS_KEY: str = "pending_supervisor_tasks"

_RESERVED_STATE_KEYS: frozenset[str] = frozenset(
    {
        "account_id",
        "organization_context",
        _PENDING_SUPERVISOR_TASKS_KEY,  # AH-144: prevent result_key collision with checkpoint
        "todo_lists",
        "user_id",
        "app_name",
        "session_id",
    }
)

# Mirrors TodoItem.status Literal in api/src/kene_api/models/chat.py (AH-122 / AH-PRD-14 §4).
_TODO_ITEM_STATUSES: frozenset[str] = frozenset(
    {"pending", "dispatched", "awaiting_review", "completed", "failed"}
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_items(
    raw_items: list[dict[str, Any]],
) -> list[dict[str, Any]] | str:
    """Return a normalized copy of the caller's item list, or an ERROR string.

    Guarantees every item has ``item_id``, ``text``, ``completed``,
    ``completed_at``, and the six supervisor-orchestration fields (``assignee``,
    ``query``, ``criteria``, ``depends_on``, ``result_key``, ``status``) —
    matching the ``TodoItem`` Pydantic shape in
    ``api/src/kene_api/models/chat.py`` (AH-122 / AH-PRD-14 §4). A missing
    ``item_id`` falls back to ``"item_{i:03d}"`` (zero-indexed); an explicit
    empty string is preserved.
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

        # --- supervisor-orchestration fields (AH-122 / AH-PRD-14 §4) ---
        assignee = item.get("assignee")
        if assignee is not None and not isinstance(assignee, str):
            return f"ERROR: assignee at index {i} must be a string or null."

        query = item.get("query")
        if query is not None and not isinstance(query, str):
            return f"ERROR: query at index {i} must be a string or null."
        if isinstance(query, str) and len(query) > _MAX_QUERY_LEN:
            return f"ERROR: query at index {i} exceeds {_MAX_QUERY_LEN} characters."

        criteria = item.get("criteria")
        if criteria is not None and not isinstance(criteria, str):
            return f"ERROR: criteria at index {i} must be a string or null."
        if isinstance(criteria, str) and len(criteria) > _MAX_CRITERIA_LEN:
            return f"ERROR: criteria at index {i} exceeds {_MAX_CRITERIA_LEN} characters."

        result_key = item.get("result_key")
        if result_key is not None and not isinstance(result_key, str):
            return f"ERROR: result_key at index {i} must be a string or null."
        # Empty/absent result_key is a no-op (the item simply has no output slot);
        # only validate a non-empty value the coordinator chose.
        if isinstance(result_key, str) and result_key:
            if len(result_key) > _MAX_RESULT_KEY_LEN:
                return f"ERROR: result_key at index {i} exceeds {_MAX_RESULT_KEY_LEN} characters."
            if (
                result_key.startswith("_")
                or result_key in _RESERVED_STATE_KEYS
                or any(s in result_key.lower() for s in _SENSITIVE_KEY_SUBSTRINGS)
            ):
                return (
                    f"ERROR: result_key {result_key!r} at index {i} is a reserved or "
                    "sensitive session-state key and cannot be used as a task output key."
                )
            if not _RESULT_KEY_PATTERN.match(result_key):
                return (
                    f"ERROR: result_key {result_key!r} at index {i} must be lowercase "
                    "alphanumeric with underscores and start with a letter "
                    f"(pattern {_RESULT_KEY_PATTERN.pattern})."
                )

        # Coerce absent/None → [] to match Pydantic Field(default_factory=list).
        # Only None (and absent key) are silently coerced; any other falsy type
        # (0, "", {}) fails the isinstance check below.
        raw_depends_on = item.get("depends_on")
        if raw_depends_on is None:
            raw_depends_on = []
        if not isinstance(raw_depends_on, list):
            return f"ERROR: depends_on at index {i} must be a list of strings."
        for j, dep in enumerate(raw_depends_on):
            if not isinstance(dep, str):
                return f"ERROR: depends_on[{j}] at index {i} must be a string."

        status = item.get("status", "pending")
        if status not in _TODO_ITEM_STATUSES:
            return (
                f"ERROR: status at index {i} must be one of "
                f"{sorted(_TODO_ITEM_STATUSES)}."
            )

        normalized.append(
            {
                "item_id": item_id,
                "text": text,
                "completed": bool(item.get("completed", False)),
                "completed_at": completed_at,
                "assignee": assignee,
                "query": query,
                "criteria": criteria,
                "depends_on": raw_depends_on,
                "result_key": result_key,
                "status": status,
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

    # Supervisor-mode validation: if any item carries an assignee field the
    # coordinator is building a multi-task ledger — validate it before writing.
    # Non-supervisor lists (no assignee on any item) skip this path entirely
    # so the existing CH-PRD-05 single-specialist TODO panel is unaffected.
    if any(item.get("assignee") for item in normalized):
        # Lazy import avoids circular deps (orchestration may import factory code).
        from app.adk.agents.orchestration.supervisor import validate_ledger

        state_specialists = tool_context.state.get("_available_specialists") or []
        known_specialist_ids: set[str] = {
            spec["agent_id"]
            for spec in state_specialists
            if isinstance(spec, dict) and "agent_id" in spec
        }
        validation_error = validate_ledger(normalized, known_specialist_ids)
        if validation_error is not None:
            return validation_error

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
# Pending supervisor tasks — approval-checkpoint continuation (AH-144)
# ---------------------------------------------------------------------------

# Maximum number of completed-result entries and per-value string length.
# These bounds prevent session-state bloat from unbounded specialist output.
# 12 mirrors MAX_LEDGER_ITEMS in supervisor.py (same cap, no circular import needed).
_MAX_COMPLETED_RESULTS_ENTRIES: int = 12
_MAX_COMPLETED_RESULT_VALUE_LEN: int = 65_536  # 64 KiB soft cap per entry


def _bound_result_value(value: Any) -> Any:
    """Bound one completed-result value to ``_MAX_COMPLETED_RESULT_VALUE_LEN``.

    Strings are truncated directly. Non-string values (nested dict/list/number)
    are bounded by their *serialized* size so a large structure cannot slip past
    the per-entry cap; an oversized value is replaced with a truncation marker
    and an unserializable one with a placeholder, since neither can be stored
    partially. This keeps the cap meaningful regardless of value shape.
    """
    if isinstance(value, str):
        if len(value) <= _MAX_COMPLETED_RESULT_VALUE_LEN:
            return value
        return value[:_MAX_COMPLETED_RESULT_VALUE_LEN]
    try:
        serialized = json.dumps(value)
    except (TypeError, ValueError):
        return "[unserializable value omitted]"
    if len(serialized) <= _MAX_COMPLETED_RESULT_VALUE_LEN:
        return value
    return serialized[:_MAX_COMPLETED_RESULT_VALUE_LEN] + "... [truncated]"


async def save_pending_supervisor_tasks(
    tool_context: Any,
    remaining: list[dict[str, Any]],
    completed_results: Any,
) -> str:
    """Save pending supervisor tasks when an approval checkpoint is reached.

    Stores the remaining tasks and the completed results collected so far in
    ``session.state["pending_supervisor_tasks"]`` so the coordinator can resume
    on the next user turn after the user approves.  The key is plain (no
    ``temp:`` prefix) so it survives across ADK invocations within the same
    session.

    Args:
        tool_context: ADK ToolContext (carries ``.state``).
        remaining: List of not-yet-executed ``TodoItem`` dicts.
        completed_results: Dict mapping ``result_key`` → specialist output for
            tasks already completed in this turn.

    Returns:
        ``"OK: pending supervisor tasks saved."`` on success.
        ``"ERROR: ..."`` string on validation failure.
    """
    if not isinstance(completed_results, dict):
        return "ERROR: completed_results must be a JSON object."

    if len(completed_results) > _MAX_COMPLETED_RESULTS_ENTRIES:
        return (
            f"ERROR: completed_results exceeds {_MAX_COMPLETED_RESULTS_ENTRIES} entries."
        )

    # Validate each completed_result key (same naming convention as result_key).
    for cr_key in completed_results:
        if not isinstance(cr_key, str):
            return "ERROR: completed_results keys must be strings."
        if any(s in cr_key.lower() for s in _SENSITIVE_KEY_SUBSTRINGS):
            return (
                f"ERROR: completed_results key {cr_key!r} matches a sensitive "
                "key pattern and cannot be stored."
            )

    normalized = _normalize_items(remaining)
    if isinstance(normalized, str):
        return normalized  # propagate item-level validation error

    # Bound every value at write time (strings by length, structures by
    # serialized size) so session-state cannot bloat from large specialist output.
    bounded_results: dict[str, Any] = {
        k: _bound_result_value(v) for k, v in completed_results.items()
    }

    tool_context.state[_PENDING_SUPERVISOR_TASKS_KEY] = {
        "remaining": normalized,
        "completed_results": bounded_results,
        "saved_at": _now_iso(),
    }
    return "OK: pending supervisor tasks saved."


async def resume_pending_supervisor_tasks(tool_context: Any) -> str:
    """Read and clear the pending supervisor tasks checkpoint.

    Returns the saved structure as a JSON string and removes the state key in
    one atomic call (single-shot continuation) — the coordinator cannot
    accidentally read without clearing.

    Args:
        tool_context: ADK ToolContext (carries ``.state``).

    Returns:
        JSON string of ``{remaining, completed_results, saved_at}`` on success.
        ``"ERROR: no pending supervisor tasks to resume."`` when no checkpoint
        is saved.
    """
    pending = tool_context.state.get(_PENDING_SUPERVISOR_TASKS_KEY)
    if not pending:
        return "ERROR: no pending supervisor tasks to resume."

    # Clear on read — single-shot continuation. Assign the ``None`` sentinel
    # rather than ``del``: ADK 2.0's ``State`` has no ``__delitem__``, and only a
    # ``__setitem__`` mutation is recorded in the session delta and persisted.
    # The provider treats a falsy value as "no checkpoint" (renders nothing).
    tool_context.state[_PENDING_SUPERVISOR_TASKS_KEY] = None
    return json.dumps(pending)


async def clear_pending_supervisor_tasks(tool_context: Any) -> str:
    """Idempotently clear the pending supervisor tasks checkpoint.

    Called when the user rejects the pending workflow, changes topic, or after
    a resumed workflow completes (success or failure).

    Args:
        tool_context: ADK ToolContext (carries ``.state``).

    Returns:
        ``"OK: pending supervisor tasks cleared."`` always (idempotent).
    """
    # Assign the ``None`` sentinel rather than ``.pop``: ADK 2.0's ``State`` has
    # no ``pop``/``__delitem__``, and only a ``__setitem__`` mutation is committed
    # to the session delta. Idempotent — setting ``None`` when already ``None`` is
    # a no-op.
    tool_context.state[_PENDING_SUPERVISOR_TASKS_KEY] = None
    return "OK: pending supervisor tasks cleared."


# ---------------------------------------------------------------------------
# Registry wiring (side-effect on import)
# ---------------------------------------------------------------------------

register_function_tool("set_todo_list", set_todo_list)
register_function_tool("update_todo_list", update_todo_list)
register_function_tool("save_pending_supervisor_tasks", save_pending_supervisor_tasks)
register_function_tool("resume_pending_supervisor_tasks", resume_pending_supervisor_tasks)
register_function_tool("clear_pending_supervisor_tasks", clear_pending_supervisor_tasks)
