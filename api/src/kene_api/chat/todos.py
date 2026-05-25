"""Chat todo-lists read service.

Reads session.state["todo_lists"] from the ADK VertexAiSessionService.
Server-side Pydantic validation drops malformed entries with a warning log —
never 500s on bad state. Results are sorted is_current-first, then created_at DESC.
"""

from __future__ import annotations

import logging
from datetime import timezone
from typing import Any

from ..models.chat import TodoList

logger = logging.getLogger(__name__)

_MAX_TODO_LISTS = 100


def _validate_todo_list_entry(raw: Any) -> TodoList | None:
    """Validate a single entry from session.state["todo_lists"].

    Returns a TodoList on success or None (with a warning log) on any failure.
    Non-dict inputs are rejected immediately; dict inputs are validated through
    Pydantic with Exception catching to guard against unexpected ADK state shapes.
    """
    if not isinstance(raw, dict):
        logger.warning(
            "chat.todos.validation_dropped",
            extra={
                "list_id": "<unknown>",
                "error_type": "TypeError",
                "error": f"expected dict, got {type(raw).__name__}",
            },
        )
        return None
    list_id = str(raw.get("list_id", "<unknown>"))
    try:
        return TodoList(**raw)
    except Exception as exc:
        logger.warning(
            "chat.todos.validation_dropped",
            extra={
                "list_id": list_id,
                "error_type": type(exc).__name__,
                "error": repr(str(exc))[:256],
            },
        )
        return None


async def list_todo_lists(
    session_service: Any,
    app_name: str,
    user_id: str,
    session_id: str,
) -> list[TodoList]:
    """Fetch and validate todo lists from ADK session state.

    Args:
        session_service: VertexAiSessionService instance (injected so tests
            can supply a MagicMock without monkey-patching module globals).
        app_name: ADK app name (e.g. "ken_e_chatbot").
        user_id: Authenticated user id (used by ADK to scope the session).
        session_id: ADK session id.

    Returns:
        Sorted list of validated TodoList objects (capped at _MAX_TODO_LISTS):
        - is_current=True entries first
        - then created_at DESC within each bucket
        Returns [] on any exception from the session service, missing key,
        or when all entries are malformed.
    """
    try:
        session = await session_service.get_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )
    except Exception as exc:
        # Log at error: a real backend outage here would otherwise look exactly
        # like "this session has no todos". We still return [] (never 500 the
        # read endpoint), but the failure must be visible in ops dashboards.
        logger.error(
            "chat.todos.get_session_failed",
            extra={
                "session_id": session_id,
                "error_type": type(exc).__name__,
                "error": repr(str(exc))[:256],
            },
        )
        return []

    state: dict[str, Any] = {}
    if (
        session is not None
        and hasattr(session, "state")
        and isinstance(session.state, dict)
    ):
        state = session.state

    raw_todos = state.get("todo_lists", {})
    if not isinstance(raw_todos, dict):
        logger.warning(
            "chat.todos.unexpected_type",
            extra={"session_id": session_id, "type": type(raw_todos).__name__},
        )
        return []

    entries = list(raw_todos.values())
    if len(entries) > _MAX_TODO_LISTS:
        logger.warning(
            "chat.todos.truncated",
            extra={
                "session_id": session_id,
                "total": len(entries),
                "cap": _MAX_TODO_LISTS,
            },
        )
        entries = entries[:_MAX_TODO_LISTS]

    validated: list[TodoList] = []
    for entry in entries:
        todo = _validate_todo_list_entry(entry)
        if todo is not None:
            validated.append(todo)

    def _sort_key(t: TodoList) -> tuple[bool, float]:
        ca = t.created_at
        if ca.tzinfo is None:
            ca = ca.replace(tzinfo=timezone.utc)
        return (not t.is_current, -ca.timestamp())

    validated.sort(key=_sort_key)
    return validated
