"""Specialist tool-roster resolution for the agent factory (AH-PRD-02 Phase 2 / AH-13).

Resolves each specialist's curated tool list from its MCP server references and
function tools, enforcing the ≤30-tool cap at build time.

The ToolRegistry is consulted here **solely as a build-time metadata catalog** —
it is not wired as a runtime callback, tool_filter predicate, or
before_agent_callback.  Specialists are constructed with a final tool list bound
directly to ``tools=``.  See agentic-harness README §2.5 (Tool-assignment &
routing model) for the full rationale.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.adk.agents.agent_factory.mcp import MCPFactoryError

if TYPE_CHECKING:
    from app.adk.tools.registry.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_TOOLS_PER_SPECIALIST: int = 30
"""Hard cap on the number of tools a factory-built specialist may carry.

Exceeding this limit is the signal that the specialist's scope is too broad
and should be split into narrower per-platform agents (see README §2.6).
"""


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class RosterCapExceededError(MCPFactoryError):
    """Raised when a specialist's resolved tool roster exceeds MAX_TOOLS_PER_SPECIALIST.

    The error message always names the specialist and the observed count so
    the operator knows immediately which config to tighten.
    """


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _tool_count_for_server(server_id: str, registry: ToolRegistry) -> int:
    """Return the number of tools attributed to *server_id* in the registry.

    If no tool entries reference *server_id*, logs a warning and returns 1
    (documented fallback) so the cap remains meaningful for partially-cataloged
    servers.

    Args:
        server_id: The ``mcp_server_configs/{server_id}`` key to look up.
        registry: The ToolRegistry instance to query.

    Returns:
        Count of tools registered under *server_id*, or 1 if none found.
    """
    count = sum(1 for t in registry.list_tools() if t.mcp_server == server_id)
    if count == 0:
        logger.warning(
            "ToolRegistry has no entries for MCP server %r; counting as 1 logical tool.  "
            "Update tools.yaml when this server's tool list is catalogued.",
            server_id,
        )
        return 1
    return count


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def count_specialist_tool_roster(
    specialist_name: str,
    *,
    mcp_server_ids: list[str],
    function_tools: list[Any],
    registry: ToolRegistry,
) -> int:
    """Return the logical tool count for a specialist before construction.

    The logical count is the canonical cap-enforcement value:

        sum(registry entries for each mcp_server_id) + len(function_tools)

    Built-in model capabilities (Gemini code execution, etc.) are not
    parameters of this function and do not contribute to the count — they
    are configured on the agent via ``code_executor=``, not via ``tools=``.

    Args:
        specialist_name: Used only in log messages for traceability.
        mcp_server_ids: Ordered list of ``mcp_server_configs/{id}`` keys
            assigned to this specialist.
        function_tools: SDK function tools (e.g. ``create_visualization``)
            to be included in the specialist's roster.
        registry: ToolRegistry instance to query for per-server tool counts.

    Returns:
        Total logical tool count.
    """
    server_count = sum(_tool_count_for_server(sid, registry) for sid in mcp_server_ids)
    total = server_count + len(function_tools)
    logger.debug(
        "Logical roster count for %r: %d mcp-tool(s) + %d function-tool(s) = %d",
        specialist_name,
        server_count,
        len(function_tools),
        total,
    )
    return total


def resolve_specialist_roster(
    specialist_name: str,
    *,
    mcp_toolsets: dict[str, Any],
    function_tools: list[Any],
    mcp_server_ids: list[str],
    registry: ToolRegistry | None = None,
) -> list[Any]:
    """Validate the logical tool count and return the ordered tools list.

    This is the canonical entry point for assembling a specialist's
    ``tools=`` argument.  It performs two actions:

    1. Counts the logical roster via :func:`count_specialist_tool_roster` and
       raises :class:`RosterCapExceededError` if the count exceeds
       :data:`MAX_TOOLS_PER_SPECIALIST`.
    2. Returns the ordered list ``[*mcp_toolsets.values(), *function_tools]``
       ready to pass directly to ``build_agent(..., tools=...)``.

    Args:
        specialist_name: Human-readable name; used in error / log messages.
        mcp_toolsets: Mapping of ``{server_id: McpToolset}`` for this
            specialist, as returned by :func:`load_toolsets_for_specialist`.
        function_tools: SDK function tools to append after the MCP toolsets.
        mcp_server_ids: Ordered list of server IDs matching the keys in
            *mcp_toolsets* (used for registry lookup; order is preserved).
        registry: ToolRegistry instance.  When ``None`` the default registry
            is loaded via ``get_default_registry()``.

    Returns:
        Ordered list: all McpToolset values followed by all function tools.

    Raises:
        ValueError: ``mcp_server_ids`` contains empty/blank entries, duplicate
            entries, or entries that do not match ``mcp_toolsets.keys()``.
        RosterCapExceededError: The logical count exceeds
            :data:`MAX_TOOLS_PER_SPECIALIST`.
    """
    # Snapshot mutable inputs immediately so the validated count and the
    # returned list are always consistent (TOCTOU guard).
    frozen_toolsets: dict[str, Any] = dict(mcp_toolsets)
    frozen_function_tools: list[Any] = list(function_tools)

    # Validate server IDs: no empty/blank entries, no duplicates, must match
    # the toolsets dict keys so the logical count matches the runtime roster.
    blank = [
        sid for sid in mcp_server_ids if not isinstance(sid, str) or not sid.strip()
    ]
    if blank:
        raise ValueError(
            f"Specialist {specialist_name!r}: mcp_server_ids contains empty or blank "
            f"entries {blank!r}.  Each entry must be a non-empty Firestore document ID."
        )

    seen: set[str] = set()
    duplicates = [sid for sid in mcp_server_ids if sid in seen or seen.add(sid)]  # type: ignore[func-returns-value]
    if duplicates:
        raise ValueError(
            f"Specialist {specialist_name!r}: mcp_server_ids contains duplicate entries "
            f"{duplicates!r}.  Each server ID must appear exactly once."
        )

    if set(mcp_server_ids) != set(frozen_toolsets.keys()):
        raise ValueError(
            f"Specialist {specialist_name!r}: mcp_server_ids {sorted(mcp_server_ids)!r} "
            f"does not match mcp_toolsets keys {sorted(frozen_toolsets.keys())!r}.  "
            f"Pass the same server IDs used to build mcp_toolsets."
        )

    if registry is None:
        # NOTE: import must stay deferred (not at module level) so that tests
        # can patch app.adk.tools.registry.tool_registry.get_default_registry.
        from app.adk.tools.registry.tool_registry import get_default_registry

        registry = get_default_registry()

    logical_count = count_specialist_tool_roster(
        specialist_name,
        mcp_server_ids=mcp_server_ids,
        function_tools=frozen_function_tools,
        registry=registry,
    )

    if logical_count > MAX_TOOLS_PER_SPECIALIST:
        raise RosterCapExceededError(
            f"Specialist {specialist_name!r} has a logical tool count of {logical_count}, "
            f"which exceeds the {MAX_TOOLS_PER_SPECIALIST}-tool cap.  "
            f"Split this specialist into narrower per-platform agents (see README §2.6)."
        )

    return [*frozen_toolsets.values(), *frozen_function_tools]
