"""Dispatch utilities for the KEN-E agent factory.

Public symbols:

* ``assemble_available_specialists_block`` — produces a Markdown ``##
  Available Specialists`` block listing every registered specialist in
  alphabetical order, suitable for injection into a router agent's system
  prompt.  Consumed by ``specialist_runtime.available_specialists_provider``
  at ``specialist_runtime.py:680``.
* ``assemble_specialists_block_from_state`` — same Markdown block built
  directly from the ``_available_specialists`` session-state dicts written
  by ``attach_specialists_before_agent_callback`` (AH-86).  Used by
  ``available_specialists_provider`` on the fast path (no Firestore/agent
  resolution required) when the before-agent callback has already populated
  the dicts for this turn.
"""

from __future__ import annotations

import logging
from typing import Any

from google.adk.agents import BaseAgent

from app.adk.agents.utils.criteria_utils import (
    sanitise_criteria,
)

logger = logging.getLogger(__name__)

# Hard cap on specialist description length in the Available Specialists block.
_MAX_DESCRIPTION_CHARS: int = 500


def _format_specialist_line(name: str, raw_desc: str) -> str:
    """Return a single ``"- **{name}**: {description}"`` bullet.

    Shared by both ``assemble_available_specialists_block`` and
    ``assemble_specialists_block_from_state`` so the Markdown output is
    byte-for-byte identical regardless of which path produced it.
    """
    raw_desc = raw_desc.strip()
    if not raw_desc:
        description = "(no description provided)"
    else:
        description = sanitise_criteria(raw_desc[:_MAX_DESCRIPTION_CHARS])
        if not description:
            description = "(no description provided)"
    return f"- **{name}**: {description}"


def assemble_available_specialists_block(
    specialists: dict[str, BaseAgent],
) -> str:
    """Build a Markdown block listing every registered specialist.

    Returns a string starting with ``"## Available Specialists\\n\\n"`` followed
    by one bullet per specialist in alphabetical order.  Each bullet has the
    form ``"- **{name}**: {description}"``.  When the specialist's description
    is absent or empty, the fallback text ``"(no description provided)"`` is
    used.

    When the registry is empty, the heading is still emitted, followed by a
    single ``"- None registered."`` line.

    Args:
        specialists: Mapping of specialist name -> ``BaseAgent``. Accepts
            ``LlmAgent`` for plain specialists or ``LoopAgent`` for
            review-pipeline-wrapped specialists (AH-75 / AH-PRD-09).

    Returns:
        A Markdown-formatted string ready for injection into a router agent's
        system prompt.
    """
    heading = "## Available Specialists\n\n"

    if not specialists:
        return heading + "- None registered."

    lines: list[str] = []
    for name in sorted(specialists):
        agent = specialists[name]
        raw_desc: str = (getattr(agent, "description", None) or "").strip()
        lines.append(_format_specialist_line(name, raw_desc))

    return heading + "\n".join(lines)


def assemble_specialists_block_from_state(
    state_dicts: list[dict[str, Any]],
) -> str:
    """Build the ``## Available Specialists`` block from session-state dicts.

    This is the AH-86 fast path: ``attach_specialists_before_agent_callback``
    writes ``state["_available_specialists"]`` as a list of
    ``{"name": str, "description": str, "agent_id": str}`` dicts before the
    instruction provider runs.  When that key is present, the provider calls
    this function instead of resolving agents from Firestore, which avoids
    the event-loop-blocking ``future.result()`` calls in ``_build_specialist``.

    The Markdown output is byte-for-byte identical to
    ``assemble_available_specialists_block`` for the same specialists — both
    delegate to ``_format_specialist_line``.

    Args:
        state_dicts: The value of ``context.state["_available_specialists"]``.
            Each dict must have at least a ``"name"`` key; ``"description"``
            is used when present and non-empty.

    Returns:
        A Markdown-formatted string ready for injection into a router agent's
        system prompt.
    """
    heading = "## Available Specialists\n\n"

    if not state_dicts:
        return heading + "- None registered."

    lines: list[str] = []
    for entry in sorted(state_dicts, key=lambda d: d.get("name", "")):
        name: str = entry.get("name", "")
        if not name:
            continue
        raw_desc: str = entry.get("description", "") or ""
        lines.append(_format_specialist_line(name, raw_desc))

    if not lines:
        return heading + "- None registered."

    return heading + "\n".join(lines)
