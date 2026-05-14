"""Shared limits governing per-agent tool assignment.

Two consumers need to agree on the cap:

* ``app.adk.agents.agent_factory.roster`` enforces it at deploy-time agent
  construction (the canonical runtime gate).
* ``api.src.kene_api.models.agent_config_models`` enforces it at the API
  boundary as ``Annotated[..., max_length=...]`` on ``tool_ids`` so the
  client gets a 422 long before the factory sees the doc.

Keeping the literal in one place removes the cross-module drift risk the
original two-comment dance was trying to flag (AH-PRD-06 review round 2).
"""

from __future__ import annotations

MAX_TOOLS_PER_SPECIALIST: int = 30
"""Hard cap on the number of tools a factory-built specialist may carry.

Exceeding this limit signals that the specialist's scope is too broad and
should be split into narrower per-platform agents (see
``docs/design/components/agentic-harness/README.md`` §2.6).
"""

__all__ = ["MAX_TOOLS_PER_SPECIALIST"]
