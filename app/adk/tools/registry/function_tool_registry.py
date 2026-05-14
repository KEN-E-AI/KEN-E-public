"""Runtime registry mapping catalogued function-tool names to ADK callables.

AH-PRD-06 PR-C bridges the gap between the static tool catalogue
(``tools.yaml`` ``function_tools:`` entries tagged ``default_global: true``)
and the actual ``FunctionTool`` instances each catalogued tool needs to be
wired as on a constructed agent. The catalogue is a metadata-only schema;
this module is where the *callables* live and how the agent factory finds
them.

Lifecycle:

  1. A module that implements a function tool (e.g. AH-PRD-04's
     ``create_visualization``) calls :func:`register_function_tool` at
     import time.
  2. ``app/adk/agents/agent_factory/hierarchy.py`` imports those modules at
     startup so the registration side effects run before
     ``build_hierarchy`` resolves rosters.
  3. ``build_hierarchy`` calls :func:`resolve_default_global_tools` once per
     specialist; the resolver returns the ``FunctionTool`` instances for
     every catalogue entry tagged ``default_global: true``. Catalogue
     entries without a registered callable are skipped with a logged
     warning so the catalogue can lead the implementation by a release
     (e.g. AH-PRD-06 lands the catalogue + wiring; AH-PRD-04 lands the
     ``create_visualization`` callable).

The registry is a process-global singleton — tests should call
:func:`clear_function_tool_registry` in setup or teardown to avoid leaking
fixtures into adjacent suites.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from google.adk.tools.function_tool import FunctionTool

if TYPE_CHECKING:
    from app.adk.tools.registry.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


# Process-global registry. Keyed by the bare tool name (matches
# ``ToolDefinition.name`` and the ``tool_ids`` allow-list's ``function.{name}``
# suffix).
_REGISTRY: dict[str, FunctionTool] = {}


def register_function_tool(
    name: str, tool: FunctionTool | Callable[..., object]
) -> None:
    """Register a callable for a catalogued ``function_tools:`` entry.

    Idempotent: re-registering the same ``name`` overwrites the previous
    entry and logs at DEBUG. This is intentional so a module reload (test
    harness, hot reload) doesn't fail loudly — but in production the same
    name should only register once.

    Args:
        name: Bare tool name; must match the ``name`` field of the
            corresponding ``function_tools:`` entry in ``tools.yaml``.
        tool: Either a pre-constructed ``FunctionTool`` or a raw callable
            that will be wrapped via ``FunctionTool(callable)``.

    The registered ``name`` is stamped onto ``tool.name`` so the roster
    filter (``_filter_function_tools_by_ids`` in roster.py) matches on the
    catalogue identity rather than the underlying callable's
    ``__name__``. Otherwise a tool registered as ``"create_visualization"``
    but implemented by a function named ``_create_viz_impl`` would be
    silently dropped by the filter when ``tool_ids`` lists
    ``function.create_visualization``.
    """
    if not isinstance(tool, FunctionTool):
        tool = FunctionTool(tool)
    tool.name = name
    if name in _REGISTRY:
        logger.debug("Overwriting existing FunctionTool registration for %r", name)
    _REGISTRY[name] = tool


def get_function_tool(name: str) -> FunctionTool | None:
    """Return the registered ``FunctionTool`` for *name*, or ``None``."""
    return _REGISTRY.get(name)


def resolve_default_global_tools(
    registry: ToolRegistry,
) -> list[FunctionTool]:
    """Return the ``FunctionTool`` instances for every ``default_global`` entry.

    Iterates the catalogue's ``default_global: true`` entries (via
    :meth:`ToolRegistry.list_default_global_tools`) and looks up each one's
    registered callable. Entries without a registered callable are skipped
    with a logged warning — this lets the catalogue and the implementation
    evolve at different paces (the warning surfaces the gap so a missing
    registration doesn't go unnoticed).

    Args:
        registry: The ToolRegistry to read catalogue entries from. Pass
            ``get_default_registry()`` in production; tests use a fake.

    Returns:
        Ordered list of ``FunctionTool`` instances. Order matches the order
        of ``list_default_global_tools()``, which is itself the YAML's
        insertion order — keep ``tools.yaml`` stable to keep agent tool
        ordering stable.
    """
    resolved: list[FunctionTool] = []
    for tool_def in registry.list_default_global_tools():
        fn_tool = _REGISTRY.get(tool_def.name)
        if fn_tool is None:
            logger.warning(
                "Function tool %r is catalogued as default_global in "
                "tools.yaml but no callable is registered; skipping. "
                "Register via ``register_function_tool(%r, <callable>)`` "
                "from the module that implements the tool — usually the "
                "module is imported at startup from "
                "``app/adk/agents/agent_factory/hierarchy.py`` so the "
                "side effect fires before build_hierarchy resolves rosters.",
                tool_def.name,
                tool_def.name,
            )
            continue
        resolved.append(fn_tool)
    return resolved


def clear_function_tool_registry() -> None:
    """Empty the registry. Test-only — never call from production code."""
    _REGISTRY.clear()


__all__ = [
    "clear_function_tool_registry",
    "get_function_tool",
    "register_function_tool",
    "resolve_default_global_tools",
]
