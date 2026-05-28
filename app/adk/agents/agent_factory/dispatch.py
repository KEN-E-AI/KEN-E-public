"""Dispatch utilities for the KEN-E agent factory.

Public symbols:

* ``assemble_available_specialists_block`` — produces a Markdown ``##
  Available Specialists`` block listing every registered specialist in
  alphabetical order, suitable for injection into a router agent's system
  prompt.  Consumed by ``specialist_runtime.available_specialists_provider``
  at ``specialist_runtime.py:680``.
"""

from __future__ import annotations

import logging

from google.adk.agents import BaseAgent

from app.adk.agents.utils.criteria_utils import (
    sanitise_criteria,
)

logger = logging.getLogger(__name__)

# Hard cap on specialist description length in the Available Specialists block.
_MAX_DESCRIPTION_CHARS: int = 500


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
        if not raw_desc:
            description = "(no description provided)"
        else:
            description = sanitise_criteria(raw_desc[:_MAX_DESCRIPTION_CHARS])
            if not description:
                description = "(no description provided)"
        lines.append(f"- **{name}**: {description}")

    return heading + "\n".join(lines)
