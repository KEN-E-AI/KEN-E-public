"""Google web search agent tool (AH-98 / AH-114 / AH-PRD-15 re-plan).

``create_google_search_agent()`` builds a leaf ``Agent`` holding the ADK built-in
``google_search`` tool. The built-in tool cannot be combined with other tools or
an ``output_schema`` in the same agent, so it lives in a dedicated leaf agent.

**AH-PRD-15 re-plan (AH-121, 2026-06-07).** AH-114 tried to migrate this to a
``mode='task'`` sub-agent; that 400'd in prod (``Multiple tools are supported only
when they are all search tools``) because task mode injects ``FinishTaskTool``
next to the grounding tool. The built-in ``google_search`` tool can ONLY be
isolated by an ADK ``AgentTool`` (own sub-runner, no transfer/task tool injected).
``create_google_search_agent_tool()`` builds that isolated ``AgentTool`` for the
ADK 2.0 chat tree and attaches ``capture_agent_tool_usage`` to the leaf so the
``usage_metadata`` that ``AgentTool.run_async`` drops (GitHub #3984, OPEN) is still
billed (see ``app/adk/agents/agent_tool_billing.py``). It is registered on the
*isolated* lane under the catalogue name ``google_search`` so it can be assigned to
any agent via ``tool_ids`` (opt-in; see the ``agent_tools:`` entry in
``tools.yaml``). ``create_google_search_subagent`` (the AH-114 task-mode variant)
is retained but DORMANT — it is no longer registered.

The strategy researchers import ``create_google_search_agent`` from here (re-exported
by ``app/adk/agents/strategy_agent/agents.py``). That path stays on ADK 1.34.x
(KG-PRD-05 retires strategy_agent). ``create_google_search_agent`` is left
byte-identical so the strategy pipeline is unaffected.

Design reference: AH-PRD-15 §2 (scope boundary), §5 (Implementation Outline), §7.7.
"""

from __future__ import annotations

import logging

from google.adk.agents import Agent, LlmAgent
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from google.genai import types

from app.adk.agents.agent_tool_billing import capture_agent_tool_usage
from app.adk.tools.registry.agent_tool_registry import (
    register_isolated_agent_tool,
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


def create_google_search_agent_tool() -> AgentTool:
    """Create the isolated ``AgentTool`` wrapping the Google-search leaf (chat tree).

    The leaf is named ``google_search`` so ``AgentTool.name == 'google_search'``
    matches the ``agent.google_search`` tool id. It carries ONLY the built-in
    ``google_search`` grounding tool — no sibling function tool — which is the
    invariant Gemini enforces; ``AgentTool`` is the only dispatch mechanism that
    preserves it (own sub-runner, no transfer/task tool injected). The
    ``capture_agent_tool_usage`` after_model_callback recovers the leaf's
    ``usage_metadata`` for billing, since ``AgentTool.run_async`` drops the leaf's
    inner events from the outer stream (#3984). See AH-PRD-15 §5 / §7.7.
    """
    leaf = Agent(
        name="google_search",
        model="gemini-2.5-flash",
        tools=[google_search],
        description="Expert web researcher that searches Google for public information",
        instruction="Search for relevant public information about the topic. Focus on official sources and recent data.",
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192,
        ),
        after_model_callback=capture_agent_tool_usage,
    )
    # isolation-required: AH-PRD-15 §7.7 — built-in google_search must be isolated
    # in its own AgentTool sub-runner; billing via the leaf after_model_callback.
    return AgentTool(agent=leaf)


# ---------------------------------------------------------------------------
# Registry wiring (side-effect on import) — AH-PRD-15 re-plan (AH-121)
#
# ``task_mode_supported()`` is reused purely as a "this is the ADK 2.0 chat tree"
# proxy (``LlmAgent.mode`` exists only on 2.0). The strategy-supervisor deploy tree
# (deploy_with_sys_version.py) is FROZEN at google-adk==1.34.1 and imports this
# module via the strategy ``agents.py`` re-export of ``create_google_search_agent``;
# it must NOT register the chat-tree agent-tool (it never reads the registry, but
# we keep the gate so its import path is byte-for-byte unchanged in behaviour).
# The isolated AgentTool replaces the AH-114 task-mode registration, which 400'd in
# prod (the built-in grounding tool cannot share its request with FinishTaskTool).
# ---------------------------------------------------------------------------

if task_mode_supported():
    register_isolated_agent_tool("google_search", create_google_search_agent_tool)
else:
    logger.info(
        "Skipping google_search isolated-AgentTool registration on the ADK 1.34.x "
        "strategy deploy tree. create_google_search_agent (ADK 1.34.x leaf) remains "
        "available for the strategy researchers."
    )


__all__ = [
    "create_google_search_agent",
    "create_google_search_agent_tool",
    "create_google_search_subagent",
]
