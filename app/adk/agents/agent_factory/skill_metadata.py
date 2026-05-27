"""Build-time skill metadata sidecar.

Stores per-agent build-time facts (currently: ``skill_load_total_failure``)
without mutating the ADK ``LlmAgent`` Pydantic model.  SK-27 reads via
``get_skill_build_metadata`` when emitting the ``skill.list`` Weave span
(SK-PRD-02 §7 AC-2a).

Why not ``WeakKeyDictionary``?  ``LlmAgent`` is a Pydantic ``BaseModel`` with
``eq``-based hashing disabled by default, so it is unhashable — and
``WeakKeyDictionary`` requires hashable keys.  We instead use an
``id(agent)``-keyed dict and register a ``weakref.finalize`` callback that
pops the entry when the agent is garbage-collected.  ``id()`` reuse after GC
is safe because the finalizer runs before the slot can be reassigned.
"""

from __future__ import annotations

import weakref
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from google.adk.agents import LlmAgent

_metadata: dict[int, dict[str, Any]] = {}


def record_skill_build_metadata(agent: LlmAgent, **fields: Any) -> None:
    """Attach build-time skill metadata to ``agent``.  Merges with prior calls."""
    agent_id = id(agent)
    if agent_id not in _metadata:
        _metadata[agent_id] = {}
        # Drop the entry when the agent is GC'd so the dict cannot grow unbounded.
        weakref.finalize(agent, _metadata.pop, agent_id, None)
    _metadata[agent_id].update(fields)


def get_skill_build_metadata(agent: LlmAgent) -> dict[str, Any]:
    """Return a copy of the metadata for ``agent`` (empty dict if none)."""
    return dict(_metadata.get(id(agent), {}))
