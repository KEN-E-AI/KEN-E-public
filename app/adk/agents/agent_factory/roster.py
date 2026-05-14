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


def per_server_allowed_tools(
    tool_ids: list[str] | None,
) -> dict[str, list[str]] | None:
    """Group a flat ``tool_ids`` allowlist by MCP server.

    Returns ``None`` when ``tool_ids`` is ``None`` (signals "no filter / legacy
    behaviour"). Returns an empty dict when ``tool_ids`` is set but contains no
    MCP-attached IDs (signals "drop every server"). Otherwise returns
    ``{server_id: [bare_tool_name, …]}``. ``function.*`` IDs are excluded —
    function tools are filtered separately by name.

    Consumed by:
      * ``hierarchy.py`` Step 6a — passes the per-server list into
        ``build_toolset_for_doc(..., allowed_tool_names=...)`` so each
        ``McpToolset`` is constructed with ADK's native ``tool_filter``.
      * ``resolve_specialist_roster`` — uses the same map as belt-and-suspenders
        when the resolver receives pre-built (unfiltered) toolsets.
    """
    if tool_ids is None:
        return None
    result: dict[str, list[str]] = {}
    for tid in tool_ids:
        server, _, name = tid.partition(".")
        if not name or server == "function":
            continue
        result.setdefault(server, []).append(name)
    return result


def _filter_function_tools_by_ids(
    function_tools: list[Any], tool_ids: set[str]
) -> list[Any]:
    """Return only function tools whose ``function.{name}`` ID is in tool_ids.

    Function tools expose their name either as a ``name`` attribute (ADK
    convention) or via ``__name__``. We try both so the filter works for
    both ``FunctionTool``-wrapped callables and bare callables registered
    directly with an agent. Anything without a discoverable name is dropped
    silently — there's nothing reliable to match against.
    """
    kept: list[Any] = []
    for tool in function_tools:
        bare_name = getattr(tool, "name", None) or getattr(tool, "__name__", None)
        if isinstance(bare_name, str) and f"function.{bare_name}" in tool_ids:
            kept.append(tool)
    return kept


def resolve_specialist_roster(
    specialist_name: str,
    *,
    mcp_toolsets: dict[str, Any],
    function_tools: list[Any],
    mcp_server_ids: list[str],
    tool_ids: list[str] | None = None,
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
        tool_ids: Optional per-agent tool allowlist (AH-PRD-06). ``None``
            preserves legacy behaviour (every tool from every attached
            server). ``[]`` returns an empty roster. ``[…]`` filters: each
            MCP toolset is rebuilt with a per-server allowlist (via the
            ``allowed_tool_names`` arg already plumbed through
            :func:`build_toolset_for_doc`), and function tools are filtered
            to those whose ``function.{name}`` is in the list. Servers with
            no allowed tools are dropped entirely.
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

    # AH-PRD-06: apply the per-agent tool allowlist. Within-toolset filtering
    # is the caller's job at construction (``hierarchy.py`` passes
    # ``allowed_tool_names`` into ``build_toolset_for_doc``). This branch
    # only:
    #   * defensively re-checks the cap so non-router callers (migration /
    #     seed scripts / tests) can't sneak past the API gate;
    #   * drops toolsets whose servers don't appear in ``tool_ids`` as a
    #     safety net when the caller didn't pre-filter;
    #   * prunes function tools to those whose ``function.{name}`` is listed.
    if tool_ids is not None:
        # Defensive cap (review item #2): the API layer gates len(tool_ids)
        # to MAX_TOOL_IDS_PER_AGENT, but a direct Firestore write or a
        # future seeder could bypass it. Raising here surfaces the problem
        # at the construction boundary rather than at agent-runtime.
        if len(tool_ids) > MAX_TOOLS_PER_SPECIALIST:
            raise RosterCapExceededError(
                f"Specialist {specialist_name!r} has tool_ids length "
                f"{len(tool_ids)}, which exceeds the "
                f"{MAX_TOOLS_PER_SPECIALIST}-tool cap. Source likely "
                f"bypassed the API validator."
            )

        tool_id_set = set(tool_ids)
        per_server = per_server_allowed_tools(tool_ids) or {}
        kept_toolsets = {
            sid: ts for sid, ts in frozen_toolsets.items() if sid in per_server
        }
        kept_function_tools = _filter_function_tools_by_ids(
            frozen_function_tools, tool_id_set
        )
        return [*kept_toolsets.values(), *kept_function_tools]

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
