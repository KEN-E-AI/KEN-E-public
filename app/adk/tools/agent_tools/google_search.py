"""Google web search agent tool (AH-98 / AH-114).

``create_google_search_agent()`` builds a leaf ``Agent`` holding the ADK built-in
``google_search`` tool. The built-in tool cannot be combined with other tools or
an ``output_schema`` in the same agent, so it lives in a dedicated leaf agent.

AH-114 (ADK 2.0 task-mode migration): ``create_google_search_subagent()`` builds
the equivalent ``LlmAgent(mode='task')`` for the ADK 2.0 chat tree. Task-mode
dispatch (``request_task_google_search`` / ``complete_task``) propagates inner
events to the outer stream (AH-99 probe-1 / probe-4), fixing the AH-75 billing and
trace defect that ``AgentTool.run_async`` introduced on 2.0 (GitHub #3984, OPEN).
This module registers the task-mode variant under the catalogue name ``google_search``
so it can be assigned to any agent via ``tool_ids`` (opt-in; see the ``agent_tools:``
entry in ``tools.yaml``).

The strategy researchers import ``create_google_search_agent`` from here (re-exported
by ``app/adk/agents/strategy_agent/agents.py``). That path stays on ADK 1.34.x
(KG-PRD-05 retires strategy_agent) and is explicitly out of scope for AH-114.
``create_google_search_agent`` is left byte-identical so the strategy pipeline is
unaffected.

Design reference: AH-PRD-15 §2 (scope boundary), §5 (Implementation Outline), AH-114.
"""

from __future__ import annotations

import logging

from google.adk.agents import Agent, LlmAgent
from google.adk.tools import google_search
from google.genai import types

from app.adk.tools.registry.agent_tool_registry import (
    register_agent_subagent,
    task_mode_supported,
)

logger = logging.getLogger(__name__)


def create_google_search_agent() -> Agent:
    """Create the Google search leaf agent (built-in ``google_search``, isolated).

    Used by the strategy researchers (re-exported at
    ``app/adk/agents/strategy_agent/agents.py``). Stays on ADK 1.34.x — do not
    modify the return shape. See AH-PRD-15 §2 scope boundary.
    """
    return Agent(
        name="google_search_agent",
        model="gemini-2.5-flash",
        tools=[google_search],
        description="Expert web researcher that searches Google for public information",
        instruction="Search for relevant public information about the topic. Focus on official sources and recent data.",
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192,
        ),
    )


def create_google_search_subagent() -> LlmAgent:
    """Create the Google search task-mode sub-agent for the ADK 2.0 chat tree.

    Returns an ``LlmAgent(name='google_search', mode='task')`` with the same
    model / tools / description / instruction / generate_content_config as
    ``create_google_search_agent``. Task-mode dispatch propagates inner events
    to the outer Runner stream so ``usage_metadata`` is counted and grounded-search
    steps appear in traces (AH-99 probe-1 / probe-4). See AH-PRD-15 §2 + §5.
    """
    return LlmAgent(
        name="google_search",
        model="gemini-2.5-flash",
        mode="task",
        tools=[google_search],
        description="Expert web researcher that searches Google for public information",
        instruction="Search for relevant public information about the topic. Focus on official sources and recent data.",
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192,
        ),
    )


# ---------------------------------------------------------------------------
# Registry wiring (side-effect on import) — AH-114
#
# The strategy-supervisor deploy tree (deploy_with_sys_version.py) is FROZEN at
# google-adk==1.34.1 and imports this module via the strategy ``agents.py``
# re-export of ``create_google_search_agent``. On 1.34.x ``LlmAgent`` has no
# ``mode`` field, so building the task-mode sub-agent there raises a Pydantic
# ``ValidationError`` at import and crashes the strategy deploy-tree smoke test.
# ``task_mode_supported()`` gates the construction + registration so the ADK 2.0
# chat tree registers it while the 1.34.x strategy tree skips it cleanly.
# See AH-PRD-15 §2.
# ---------------------------------------------------------------------------

if task_mode_supported():
    register_agent_subagent("google_search", create_google_search_subagent)
else:
    logger.info(
        "Skipping google_search task-mode registration: installed google-adk "
        "LlmAgent has no 'mode' field (ADK 1.34.x strategy deploy tree). "
        "create_google_search_agent (ADK 1.34.x leaf) remains available."
    )


__all__ = ["create_google_search_agent", "create_google_search_subagent"]
