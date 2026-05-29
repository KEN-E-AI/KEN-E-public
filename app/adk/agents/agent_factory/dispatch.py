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
from collections.abc import Mapping
from typing import Any

from google.adk.agents import BaseAgent

from app.adk.agents.utils.criteria_utils import (
    sanitise_criteria,
)

logger = logging.getLogger(__name__)

# Hard cap on specialist description length in the Available Specialists block.
_MAX_DESCRIPTION_CHARS: int = 500

# Hard cap on human name / title fields (AH-84). Short identity strings; keep
# the block compact relative to the root agent's context budget.
_MAX_IDENTITY_CHARS: int = 64


def _format_specialist_line(
    name: str,
    raw_desc: str,
    human_name: str | None = None,
    title: str | None = None,
) -> str:
    """Return a single specialist bullet for the Available Specialists block.

    Shared by both ``assemble_available_specialists_block`` and
    ``assemble_specialists_block_from_state`` so the Markdown output is
    byte-for-byte identical regardless of which path produced it.

    The bold-wrapped token is always *name* (the Firestore ``doc_id`` and the
    ``transfer_to_agent`` routing key).  *human_name* and *title* are optional
    identity clauses that help the LLM map conversational references to the
    correct ``doc_id`` (AH-84).

    Format rules:
    - Both clauses present:  ``- **{name}** — known as "{human_name}", {title}: {desc}``
    - Only *human_name*:     ``- **{name}** — known as "{human_name}": {desc}``
    - Only *title*:          ``- **{name}** — {title}: {desc}``
    - Neither:               ``- **{name}**: {desc}``  (byte-identical to pre-AH-84)
    """
    raw_desc = raw_desc.strip()
    if not raw_desc:
        description = "(no description provided)"
    else:
        description = sanitise_criteria(raw_desc[:_MAX_DESCRIPTION_CHARS])
        if not description:
            description = "(no description provided)"

    # Sanitise and cap the identity fields.  We do NOT run them through
    # sanitise_criteria (which strips apostrophes / hyphens used legitimately in
    # human names); a length cap + strip is sufficient.
    cleaned_human_name: str | None = None
    if human_name:
        cleaned_human_name = human_name.strip()[:_MAX_IDENTITY_CHARS] or None

    cleaned_title: str | None = None
    if title:
        cleaned_title = title.strip()[:_MAX_IDENTITY_CHARS] or None

    if cleaned_human_name and cleaned_title:
        return (
            f'- **{name}** — known as "{cleaned_human_name}",'
            f" {cleaned_title}: {description}"
        )
    if cleaned_human_name:
        return f'- **{name}** — known as "{cleaned_human_name}": {description}'
    if cleaned_title:
        return f"- **{name}** — {cleaned_title}: {description}"
    return f"- **{name}**: {description}"


def assemble_available_specialists_block(
    specialists: dict[str, BaseAgent],
    metadata: Mapping[str, Mapping[str, str | None]] | None = None,
) -> str:
    """Build a Markdown block listing every registered specialist.

    Returns a string starting with ``"## Available Specialists\\n\\n"`` followed
    by one bullet per specialist in alphabetical order.  Each bullet has the
    form ``"- **{name}**: {description}"``, optionally enriched with the
    agent's human name and title when *metadata* is supplied (AH-84).

    When the registry is empty, the heading is still emitted, followed by a
    single ``"- None registered."`` line.

    Args:
        specialists: Mapping of specialist name -> ``BaseAgent``. Accepts
            ``LlmAgent`` for plain specialists or ``LoopAgent`` for
            review-pipeline-wrapped specialists (AH-75 / AH-PRD-09).
        metadata: Optional per-specialist identity metadata keyed by
            ``doc_id``.  Each value may carry ``"human_name"`` and/or
            ``"title"`` strings.  When ``None`` (default) or when a
            specialist's doc_id is absent from the mapping, the bullet
            renders without those clauses — byte-for-byte identical to the
            pre-AH-84 output.

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
        spec_meta = (metadata or {}).get(name, {})
        lines.append(
            _format_specialist_line(
                name,
                raw_desc,
                human_name=spec_meta.get("human_name"),
                title=spec_meta.get("title"),
            )
        )

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
        lines.append(
            _format_specialist_line(
                name,
                raw_desc,
                human_name=entry.get("human_name"),
                title=entry.get("title"),
            )
        )

    if not lines:
        return heading + "- None registered."

    return heading + "\n".join(lines)
