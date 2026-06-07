"""Specialist tool-roster resolution for the agent factory (AH-PRD-02 Phase 2 / AH-13).

Resolves each specialist's curated tool list from its MCP server references and
function tools, enforcing the ≤30-tool cap at build time.

The ToolRegistry is consulted here **solely as a build-time metadata catalog** —
it is not wired as a runtime callback, tool_filter predicate, or
before_agent_callback.  Specialists are constructed with a final tool list bound
directly to ``tools=``.  See agentic-harness README §2.5 (Tool-assignment &
routing model) for the full rationale.

AH-115: ``resolve_specialist_roster`` now returns a :class:`RosterResolution`
dataclass with two separate slots — ``tools`` (MCP toolsets + function tools) and
``sub_agents`` (task-mode ``LlmAgent`` leaves from the AH-114 registry). Callers
must pass the two slots to the appropriate ADK attachment points:

* ``tools=roster_result.tools`` → ``build_agent(...)``
* ``specialist.sub_agents += roster_result.sub_agents`` → inner ``LlmAgent`` worker
  (before any review-pipeline wrap) in ``_build_specialist``.

The root paths (``hierarchy.py``, ``root_tools_attacher.py``) pass
``agent_subagents=[]`` and discard the empty ``sub_agents`` slot — their
agent-subagent wiring is handled separately by AH-116.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.adk.agents.agent_factory.mcp import MCPFactoryError
from shared.agent_tool_limits import MAX_TOOLS_PER_SPECIALIST

if TYPE_CHECKING:
    from app.adk.tools.registry.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)

# ``MAX_TOOLS_PER_SPECIALIST`` is re-exported above so existing
# ``from app.adk.agents.agent_factory.roster import MAX_TOOLS_PER_SPECIALIST``
# callsites keep working. The single source of truth lives in
# ``shared.agent_tool_limits`` so the API model (which enforces the same
# cap at the request boundary) and the factory can't drift.


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class RosterCapExceededError(MCPFactoryError):
    """Raised when a specialist's resolved tool roster exceeds MAX_TOOLS_PER_SPECIALIST.

    The error message always names the specialist and the observed count so
    the operator knows immediately which config to tighten.
    """


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RosterResolution:
    """Two-slot result from :func:`resolve_specialist_roster` (AH-115).

    Separates the two ADK attachment points:

    * ``tools`` — MCP toolsets + function tools; pass to ``build_agent(tools=...)``.
    * ``sub_agents`` — task-mode ``LlmAgent`` leaves from the AH-114 registry;
      attach to the inner specialist ``LlmAgent`` *before* any review-pipeline
      wrap: ``specialist.sub_agents = list(specialist.sub_agents or []) + sub_agents``.

    Cap arithmetic is unchanged: each entry in either slot counts as one logical
    tool slot (each ``sub_agents`` entry causes ADK to inject one
    ``request_task_<name>`` callable).
    """

    tools: list[Any] = field(default_factory=list)
    sub_agents: list[Any] = field(default_factory=list)


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
    agent_subagents: list[Any] | None = None,
    registry: ToolRegistry,
) -> int:
    """Return the logical tool count for a specialist before construction.

    The logical count is the canonical cap-enforcement value:

        sum(registry entries for each mcp_server_id) + len(function_tools)
        + len(agent_subagents)

    Built-in model capabilities (Gemini code execution, etc.) are not
    parameters of this function and do not contribute to the count — they
    are configured on the agent via ``code_executor=``, not via ``tools=``.

    Each task-mode sub-agent (``agent_subagents`` entry) counts as 1 because ADK
    auto-injects one ``request_task_<name>`` callable on the parent per sub-agent
    — semantically one tool slot from the LLM's perspective (AH-115 / D5).

    NOTE on default-global function tools (AH-PRD-06 PR-C): the
    ``function_tools`` parameter includes any tools that
    ``hierarchy.py`` resolves from the default-global registry on top of
    spec-listed function tools, so a specialist with ``tool_ids=None``
    near ``MAX_TOOLS_PER_SPECIALIST`` can trip the cap when a new
    ``default_global: true`` entry is added to ``tools.yaml`` — even
    though the spec doc didn't change. If you see ``RosterCapExceededError``
    after a tools.yaml change, that's the most likely cause; either tighten
    the spec's ``mcp_servers`` or shave the catalogue. Subtracting
    default-globals from the cap is tracked as a future option.

    Args:
        specialist_name: Used only in log messages for traceability.
        mcp_server_ids: Ordered list of ``mcp_server_configs/{id}`` keys
            assigned to this specialist.
        function_tools: SDK function tools (e.g. ``create_visualization``)
            to be included in the specialist's roster.
        agent_subagents: Task-mode ``LlmAgent`` sub-agents (AH-114/AH-115) to
            be attached to the specialist's ``sub_agents`` list.
        registry: ToolRegistry instance to query for per-server tool counts.

    Returns:
        Total logical tool count.
    """
    agent_subagent_count = len(agent_subagents or [])
    server_count = sum(_tool_count_for_server(sid, registry) for sid in mcp_server_ids)
    total = server_count + len(function_tools) + agent_subagent_count
    logger.debug(
        "Logical roster count for %r: %d mcp-tool(s) + %d function-tool(s) + "
        "%d agent-subagent(s) = %d",
        specialist_name,
        server_count,
        len(function_tools),
        agent_subagent_count,
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
    ``{server_id: [bare_tool_name, …]}``. ``function.*`` and ``agent.*`` IDs are
    excluded — those built-in tools are filtered separately by name (AH-98).

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
        if not name or server in ("function", "agent"):
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


def _filter_agent_subagents_by_ids(
    agent_subagents: list[Any], tool_ids: set[str]
) -> list[Any]:
    """Return only task-mode sub-agents whose ``agent.{name}`` ID is in tool_ids (AH-115).

    Task-mode sub-agents are ``LlmAgent(mode='task')`` instances from the AH-114
    registry; their name is stamped to the catalogue name by
    ``register_agent_subagent``. Anything without a discoverable ``name`` is
    dropped silently — there's nothing reliable to match against.
    """
    kept: list[Any] = []
    for subagent in agent_subagents:
        bare_name = getattr(subagent, "name", None)
        if isinstance(bare_name, str) and f"agent.{bare_name}" in tool_ids:
            kept.append(subagent)
    return kept


def resolve_specialist_roster(
    specialist_name: str,
    *,
    mcp_toolsets: dict[str, Any],
    function_tools: list[Any],
    mcp_server_ids: list[str],
    agent_subagents: list[Any] | None = None,
    tool_ids: list[str] | None = None,
    registry: ToolRegistry | None = None,
) -> RosterResolution:
    """Validate the logical tool count and return a :class:`RosterResolution`.

    This is the canonical entry point for assembling a specialist's tool
    attachment. It performs two actions:

    1. Counts the logical roster via :func:`count_specialist_tool_roster` and
       raises :class:`RosterCapExceededError` if the count exceeds
       :data:`MAX_TOOLS_PER_SPECIALIST`.
    2. Returns a :class:`RosterResolution` with two slots:

       * ``tools`` — ``[*mcp_toolsets.values(), *function_tools]`` — pass to
         ``build_agent(..., tools=...)``.
       * ``sub_agents`` — filtered task-mode ``LlmAgent`` leaves — attach to the
         inner specialist ``LlmAgent`` before any review-pipeline wrap.

    AH-115 (D2): returning a dataclass instead of a flat list separates the two
    ADK attachment points (``tools=`` vs ``sub_agents=``) and prevents callers
    from accidentally mixing them.

    Args:
        specialist_name: Human-readable name; used in error / log messages.
        mcp_toolsets: Mapping of ``{server_id: McpToolset}`` for this
            specialist, as returned by :func:`load_toolsets_for_specialist`.
        function_tools: SDK function tools to append after the MCP toolsets.
        mcp_server_ids: Ordered list of server IDs matching the keys in
            *mcp_toolsets* (used for registry lookup; order is preserved).
        agent_subagents: Task-mode ``LlmAgent`` sub-agents from the AH-114
            registry (``resolve_agent_subagents(get_default_registry())``).
            ``None`` or ``[]`` produces an empty ``RosterResolution.sub_agents``.
        tool_ids: Optional per-agent tool allowlist (AH-PRD-06). ``None``
            preserves legacy behaviour (every tool from every attached
            server). ``[]`` returns an empty roster. ``[…]`` filters: each
            MCP toolset is rebuilt with a per-server allowlist (via the
            ``allowed_tool_names`` arg already plumbed through
            :func:`build_toolset_for_doc`), and function tools are filtered
            to those whose ``function.{name}`` is in the list. Servers with
            no allowed tools are dropped entirely.  Agent sub-agents are
            included only when their ``agent.{name}`` ID appears in the list.
        registry: ToolRegistry instance.  When ``None`` the default registry
            is loaded via ``get_default_registry()``.

    Returns:
        :class:`RosterResolution` with ``.tools`` (MCP toolsets + function
        tools) and ``.sub_agents`` (task-mode ``LlmAgent`` leaves).

    Raises:
        ValueError: ``mcp_server_ids`` contains empty/blank entries, duplicate
            entries, or entries that do not match ``mcp_toolsets.keys()``.
        RosterCapExceededError: The logical count exceeds
            :data:`MAX_TOOLS_PER_SPECIALIST`.
    """
    # Snapshot mutable inputs immediately so the validated count and the
    # returned result are always consistent (TOCTOU guard).
    frozen_toolsets: dict[str, Any] = dict(mcp_toolsets)
    frozen_function_tools: list[Any] = list(function_tools)
    frozen_agent_subagents: list[Any] = list(agent_subagents or [])

    # AH-PRD-06: apply the per-agent tool allowlist. Within-toolset filtering
    # is the caller's job at construction (``hierarchy.py`` passes
    # ``allowed_tool_names`` into ``build_toolset_for_doc``). This branch
    # only:
    #   * defensively re-checks the cap so non-router callers (migration /
    #     seed scripts / tests) can't sneak past the API gate;
    #   * drops toolsets whose servers don't appear in ``tool_ids`` as a
    #     safety net when the caller didn't pre-filter;
    #   * prunes function tools to those whose ``function.{name}`` is listed;
    #   * prunes agent sub-agents to those whose ``agent.{name}`` is listed.
    if tool_ids is not None:
        # Defensive cap (review item #2): the API layer gates len(tool_ids)
        # to MAX_TOOLS_PER_SPECIALIST, but a direct Firestore write or a
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
        # AH-115 (AH-98): opt-in agent sub-agents are attached only when their
        # ``agent.{name}`` id is listed. The candidate set is the full catalogue
        # (passed in by the caller), so non-default-global sub-agents like
        # google_search attach here even though they're excluded from the legacy
        # "all tools" branch.
        kept_agent_subagents = _filter_agent_subagents_by_ids(
            frozen_agent_subagents, tool_id_set
        )
        return RosterResolution(
            tools=[*kept_toolsets.values(), *kept_function_tools],
            sub_agents=kept_agent_subagents,
        )

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

    # AH-115 (AH-98): with no per-agent ``tool_ids`` allowlist, only
    # ``default_global`` agent sub-agents attach (parity with default-global
    # function tools). Opt-in sub-agents like google_search are excluded here —
    # they require an explicit ``agent.{name}`` entry in ``tool_ids`` (the
    # branch above). The registry lookup is guarded so empty-agent-subagent
    # callers don't depend on it.
    kept_agent_subagents = []
    if frozen_agent_subagents:
        default_global_agent_names = {
            t.name for t in registry.list_agent_tools() if t.default_global
        }
        kept_agent_subagents = [
            t
            for t in frozen_agent_subagents
            if getattr(t, "name", None) in default_global_agent_names
        ]

    logical_count = count_specialist_tool_roster(
        specialist_name,
        mcp_server_ids=mcp_server_ids,
        function_tools=frozen_function_tools,
        agent_subagents=kept_agent_subagents,
        registry=registry,
    )

    if logical_count > MAX_TOOLS_PER_SPECIALIST:
        mcp_count = (
            logical_count - len(frozen_function_tools) - len(kept_agent_subagents)
        )
        raise RosterCapExceededError(
            f"Specialist {specialist_name!r} has a logical tool count of {logical_count} "
            f"({len(frozen_function_tools)} function tool(s) + "
            f"{len(kept_agent_subagents)} agent-subagent(s) + "
            f"{mcp_count} MCP tool(s)), "
            f"which exceeds the {MAX_TOOLS_PER_SPECIALIST}-tool cap. "
            f"Note: function tools include any default-global entries from "
            f"``tools.yaml`` resolved by ``hierarchy.py`` (AH-PRD-06 PR-C) — if "
            f"this spec was passing before a recent tools.yaml change, a newly "
            f"added ``default_global: true`` entry is the likely cause. "
            f"Otherwise split this specialist into narrower per-platform agents "
            f"(see README §2.6)."
        )

    return RosterResolution(
        tools=[*frozen_toolsets.values(), *frozen_function_tools],
        sub_agents=kept_agent_subagents,
    )
