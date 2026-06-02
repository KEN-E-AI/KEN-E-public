"""Runtime registry mapping catalogued agent-tool names to ADK ``AgentTool`` instances.

AH-98 introduces a third tool kind — an *agent-as-a-tool*: an ADK ``AgentTool``
wrapping a leaf sub-agent (e.g. a Google-search agent holding the built-in
``google_search`` tool, which cannot be combined with other tools or an
``output_schema`` in the same agent). The static catalogue (``tools.yaml``
``agent_tools:`` entries) is metadata-only; this module is where the actual
``AgentTool`` instances live and how the agent factory finds them.

Lifecycle (mirrors ``function_tool_registry``):

  1. A module that implements an agent tool (e.g.
     ``app/adk/tools/agent_tools/google_search.py``) calls
     :func:`register_agent_tool` at import time.
  2. ``app/adk/agents/agent_factory/hierarchy.py`` imports those modules at
     startup so the registration side effects run before rosters resolve.
  3. ``specialist_runtime`` calls :func:`resolve_agent_tools` per build; the
     resolver returns the ``AgentTool`` instances for every catalogued
     ``agent_tools:`` entry. Catalogue entries without a registered instance are
     skipped with a logged warning so the catalogue can lead the implementation.

The registry is a process-global singleton — tests should call
:func:`clear_agent_tool_registry` in setup or teardown to avoid leaking
fixtures into adjacent suites.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from google.adk.tools.agent_tool import AgentTool

if TYPE_CHECKING:
    from app.adk.tools.registry.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


# Process-global registry. Keyed by the bare tool name (matches
# ``ToolDefinition.name`` and the ``tool_ids`` allow-list's ``agent.{name}``
# suffix).
_REGISTRY: dict[str, AgentTool] = {}


def register_agent_tool(name: str, tool: AgentTool) -> None:
    """Register an ``AgentTool`` for a catalogued ``agent_tools:`` entry.

    The registered ``name`` is stamped onto ``tool.name``. This is load-bearing:
    an ``AgentTool``'s name defaults to the *wrapped agent's* name (e.g.
    ``google_search_agent``), but the catalogue id and the roster filter key on
    the catalogue name (``agent.google_search``). Without the stamp the filter
    would silently drop the tool. ``AgentTool.name`` is a plain settable
    attribute, so this is a direct assignment.

    Re-registering the same ``name`` overwrites the previous entry and logs at
    WARNING — in a production deploy this typically means two modules collide on
    a single catalogue name, which is a real bug worth surfacing loudly.

    Args:
        name: Bare tool name; must match the ``name`` field of the corresponding
            ``agent_tools:`` entry in ``tools.yaml``.
        tool: A constructed ``AgentTool`` instance.

    Raises:
        TypeError: If ``tool`` is not an ``AgentTool``.
    """
    if not isinstance(tool, AgentTool):
        raise TypeError(
            f"register_agent_tool expects an AgentTool, got {type(tool).__name__!r}"
        )
    tool.name = name
    if name in _REGISTRY:
        logger.warning(
            "AgentTool %r is being re-registered, overwriting the previous "
            "entry. Two modules claiming the same catalogue name is almost "
            "always a bug; if this is intentional (e.g. a test fixture), call "
            "``clear_agent_tool_registry()`` between registrations to silence "
            "this warning.",
            name,
        )
    _REGISTRY[name] = tool


def get_agent_tool(name: str) -> AgentTool | None:
    """Return the registered ``AgentTool`` for *name*, or ``None``."""
    return _REGISTRY.get(name)


def resolve_agent_tools(registry: ToolRegistry) -> list[AgentTool]:
    """Return the ``AgentTool`` instances for every catalogued ``agent_tools`` entry.

    Iterates the catalogue's ``agent_tools:`` entries (via
    :meth:`ToolRegistry.list_agent_tools`) and looks up each one's registered
    instance. Entries without a registered instance are skipped with a logged
    warning — this lets the catalogue and the implementation evolve at different
    paces (the warning surfaces the gap so a missing registration doesn't go
    unnoticed).

    Note: this returns *all* catalogued agent tools, irrespective of
    ``default_global``. The roster resolver applies the per-agent ``tool_ids``
    allowlist (opt-in) on top — see ``agent_factory/roster.py``.

    Args:
        registry: The ToolRegistry to read catalogue entries from. Pass
            ``get_default_registry()`` in production; tests use a fake.

    Returns:
        Ordered list of ``AgentTool`` instances, matching catalogue (YAML)
        insertion order.
    """
    resolved: list[AgentTool] = []
    for tool_def in registry.list_agent_tools():
        agent_tool = _REGISTRY.get(tool_def.name)
        if agent_tool is None:
            logger.warning(
                "Agent tool %r is catalogued in tools.yaml but no AgentTool is "
                "registered; skipping. Register via "
                "``register_agent_tool(%r, <AgentTool>)`` from the module that "
                "implements the tool — usually imported at startup from "
                "``app/adk/agents/agent_factory/hierarchy.py`` so the side "
                "effect fires before build_hierarchy resolves rosters.",
                tool_def.name,
                tool_def.name,
            )
            continue
        resolved.append(agent_tool)
    return resolved


def clear_agent_tool_registry() -> None:
    """Empty the registry. Test-only — never call from production code."""
    _REGISTRY.clear()


__all__ = [
    "clear_agent_tool_registry",
    "get_agent_tool",
    "register_agent_tool",
    "resolve_agent_tools",
]
