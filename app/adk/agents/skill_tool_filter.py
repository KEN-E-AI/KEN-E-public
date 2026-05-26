"""Skill allowed-tools restriction filter.

This module enforces each skill's ``allowed-tools`` frontmatter as a
**restriction** over the agent's existing toolset during that skill's
invocation window — it can never *grant* a tool that the agent does not
already have.

Session-state contract
----------------------
Two keys are read from ``tool_context.state`` by
``skill_allowed_tools_before_tool_callback``:

``active_skill_id``: ``str | None``
    Set by SK-27 (SkillToolset span wiring) when the LLM activates a skill
    via ``load_skill``; cleared at turn boundary.  ``None`` or absent means
    no skill is currently active and the callback is a no-op.

``skills_allowed_tools``: ``dict[str, list[str] | None]``
    Populated by SK-22 (SkillToolset construction) at agent-build time.
    Maps each attached skill's ``skill_id`` to the pre-parsed token list
    produced by ``parse_allowed_tools``, or ``None`` when the skill carries
    no ``allowed-tools`` frontmatter (= no restriction).

These keys are written by the producers (SK-22, SK-27); this module only
*reads* them.  SK-30's integration test exercises the full round-trip.

Glob support (v1)
-----------------
``allowed-tools`` is a space-separated string.  Each token is either:

* An exact tool name (e.g. ``Read``)
* A suffix-glob ending with ``*`` (e.g. ``Bash(git:*)``)

Full glob compliance (``?``, ``[...]``, ``**``) is a v2 story (PRD §9).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

logger = logging.getLogger(__name__)


def parse_allowed_tools(raw: str | None) -> set[str] | None:
    """Parse the ``allowed-tools`` frontmatter string into a set of patterns.

    Returns ``None`` when there is no restriction (``raw`` is ``None`` or
    empty after stripping).  Returns a non-empty ``set[str]`` otherwise.

    Args:
        raw: Space-separated token string from the ``allowed-tools`` frontmatter
             field, or ``None``.

    Returns:
        ``None`` for "no restriction"; otherwise the set of pattern strings.
    """
    if not raw:
        return None
    tokens = {tok.strip() for tok in raw.split() if tok.strip()}
    return tokens if tokens else None


def _tool_name_matches(tool_name: str, pattern: str) -> bool:
    """Return ``True`` if ``tool_name`` matches ``pattern``.

    Supported pattern syntax (v1):
    * Exact match: ``"Read"`` matches only ``"Read"``.
    * Single-wildcard glob: a ``*`` anywhere in the pattern matches any
      substring at that position.  For example ``"Bash(git:*)"`` matches
      ``"Bash(git:status)"`` (``*`` expands to ``"status"``).  A bare
      ``"*"`` matches every tool name.

    Only a single ``*`` is supported in v1.  Full glob compliance is a v2
    story (PRD §9).

    Args:
        tool_name: The name of the tool being tested.
        pattern: A single pattern token from ``parse_allowed_tools``.

    Returns:
        ``True`` if the tool name matches the pattern.
    """
    if "*" not in pattern:
        return tool_name == pattern
    # Split on the first (and assumed only) wildcard.
    prefix, _, suffix = pattern.partition("*")
    return tool_name.startswith(prefix) and tool_name.endswith(suffix)


def restrict_tools_for_skill(
    agent_tools: Sequence[Any],
    allowed: set[str] | None,
) -> list[Any]:
    """Return the subset of ``agent_tools`` permitted by ``allowed``.

    This function is a **restriction filter only** — it can never introduce a
    tool that is not already present in ``agent_tools``.

    Args:
        agent_tools: The full list of tool objects available to the agent.
                     Each object must expose a ``.name`` attribute.
        allowed: Set of patterns from ``parse_allowed_tools``, or ``None``
                 meaning "no restriction — allow everything".

    Returns:
        The filtered list of tools.  Order is preserved.  If ``allowed`` is
        ``None`` the original sequence is returned as-is (no copy).  If
        ``allowed`` is an empty set, an empty list is returned (explicit
        empty allow-list = block all).
    """
    if allowed is None:
        return list(agent_tools)
    return [
        t
        for t in agent_tools
        if any(_tool_name_matches(t.name, pattern) for pattern in allowed)
    ]


async def skill_allowed_tools_before_tool_callback(
    tool: Any,
    args: dict[str, Any],
    tool_context: Any,
) -> dict[str, Any] | None:
    """ADK ``before_tool_callback`` that enforces the active skill's ``allowed-tools``.

    Registered in the builder's ``before_tool_callback`` chain after
    ``adk_before_tool_callback``.  When no skill is active the callback exits
    in O(1) (single state-dict lookup) with zero per-turn overhead.

    Returns ``None`` to allow the tool call, or a blocking error dict if the
    tool is not in the active skill's allow-list.

    Degrade-open behaviour: if ``active_skill_id`` is set but
    ``skills_allowed_tools`` is missing or has no entry for that skill ID,
    the callback returns ``None`` (allow) and emits a WARNING.  Missing wiring
    from a not-yet-shipped producer (SK-22 / SK-27) must not break agent runs.

    Args:
        tool: The ADK ``BaseTool`` about to be called.
        args: The tool's call arguments (not inspected here).
        tool_context: ADK ``ToolContext``; ``tool_context.state`` must support
                      ``.get(...)``.  If ``state`` is unavailable the callback
                      degrades open.

    Returns:
        ``None`` if execution is allowed; a ``dict`` with ``"error"`` key if
        blocked.
    """
    # Safely extract session state — mirrors the hasattr guard in hooks.py:211
    state: dict[str, Any] = {}
    if hasattr(tool_context, "state") and hasattr(tool_context.state, "get"):
        state = tool_context.state

    active_skill_id: str | None = state.get("active_skill_id")
    if not active_skill_id:
        return None  # No skill active — unrestricted

    skill_map: dict[str, list[str] | None] | None = state.get("skills_allowed_tools")
    if skill_map is None:
        logger.warning(
            "skill_filter: active_skill_id=%r but skills_allowed_tools missing from state; "
            "degrading open (SK-22 may not yet be wired)",
            active_skill_id,
        )
        return None

    raw_patterns = skill_map.get(active_skill_id)
    if raw_patterns is None:
        # Skill has no allowed-tools frontmatter — no restriction
        return None
    if not raw_patterns:
        # Explicit empty list — block all tools
        return {
            "error": "tool_restricted_by_skill",
            "message": (
                f"Tool '{tool.name}' is not permitted while skill "
                f"'{active_skill_id}' is active (empty allowed-tools list)."
            ),
            "active_skill_id": active_skill_id,
            "tool_name": tool.name,
        }

    allowed_set = set(raw_patterns)
    if any(_tool_name_matches(tool.name, pattern) for pattern in allowed_set):
        return None

    return {
        "error": "tool_restricted_by_skill",
        "message": (
            f"Tool '{tool.name}' is not permitted while skill "
            f"'{active_skill_id}' is active. "
            f"Allowed: {sorted(allowed_set)!r}."
        ),
        "active_skill_id": active_skill_id,
        "tool_name": tool.name,
    }
