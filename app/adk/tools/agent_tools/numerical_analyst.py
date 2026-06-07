"""Numerical analyst agent tool (AH-149 / AH-114 / AH-PRD-15 re-plan).

``create_numerical_analyst_agent()`` builds a leaf ``Agent`` that only
carries ``code_executor=BuiltInCodeExecutor()`` — no other tools, no MCP
servers, no ``output_schema``. This isolation is load-bearing: Gemini 2.5+
rejects combining built-in code execution with function tools on the same
agent (HTTP 400 "Multiple tools are supported only when they are all search
tools"). The analyst lives in its own leaf and is exposed to the GA
specialist (and any other specialist that needs arithmetic-via-code) as an
agent-as-a-tool.

**AH-PRD-15 re-plan (AH-121).** AH-114 tried to register this as a
``mode='task'`` sub-agent; that is unworkable for the same reason isolation is
needed — ``mode='task'`` injects ``FinishTaskTool`` next to the code executor →
the very ``400 ... all search tools`` above. The code-execution leaf can ONLY be
isolated by an ADK ``AgentTool``. ``create_numerical_analyst_agent_tool()`` builds
that isolated ``AgentTool`` for the ADK 2.0 chat tree and attaches
``capture_agent_tool_usage`` so the ``usage_metadata`` that ``AgentTool.run_async``
drops (GitHub #3984) is still billed (``app/adk/agents/agent_tool_billing.py``). It
is registered on the *isolated* lane under the catalogue name ``numerical_analyst``
(opt-in; ``default_global: false`` — see the ``agent_tools:`` entry in
``tools.yaml``). ``create_numerical_analyst_subagent`` (the AH-114 task-mode variant)
is retained but DORMANT — it is no longer registered.

``create_numerical_analyst_agent`` is left byte-identical (the ADK 1.34.x leaf).

Design reference: AH-PRD-15 §2 (scope boundary), §5 (Implementation Outline), §7.7.
"""

from __future__ import annotations

import logging

from google.adk.agents import Agent, LlmAgent
from google.adk.code_executors import BuiltInCodeExecutor
from google.adk.tools.agent_tool import AgentTool
from google.genai import types

from app.adk.agents.agent_tool_billing import capture_agent_tool_usage
from app.adk.tools.registry.agent_tool_registry import (
    register_isolated_agent_tool,
    task_mode_supported,
)

logger = logging.getLogger(__name__)

_NUMERICAL_ANALYST_INSTRUCTION = """You are a specialised numerical computation assistant.

You receive specific numbers and a description of the calculation needed. Your ONLY job is:
1. Write a short, correct Python snippet that computes the requested figure.
2. Execute it using the built-in code executor.
3. Return BOTH the numeric result AND the formula you used (e.g. "(5391 - 4823) / 4823 * 100 = 11.78%").

Rules:
- Operate ONLY on the numbers provided to you in the prompt. Do NOT call any external tools.
- Keep code short (< 20 lines). Prefer clear variable names over brevity.
- Round displayed results to at most 2 decimal places.
- If the input is insufficient to perform the calculation, state clearly what is missing.

Failure handling:
- If the code executor returns a failure (e.g. ZeroDivisionError, TypeError, NameError,
  or a sandbox timeout), examine the error message carefully.
- Attempt at most ONE corrective rewrite: fix the specific error (for example, guard
  against division by zero, correct the wrong variable name, or simplify the expression).
- If the corrected code also fails, stop retrying. Return a clear, human-readable error
  message that names the calculation you attempted and the kind of error encountered
  (e.g. "Cannot compute the week-over-week change: division by zero because the baseline
  value is 0"). Do NOT retry indefinitely.
- NEVER include a raw Python stack trace in your reply. Do NOT use the literal token
  "OUTCOME_FAILED" in your response. The user-visible message must be plain English.
"""


def create_numerical_analyst_agent() -> Agent:
    """Create the numerical analyst leaf agent (code-execution only, no other tools).

    Left unchanged from AH-149. See AH-PRD-15 §2 scope boundary.
    """
    return Agent(
        name="numerical_analyst_agent",
        model="gemini-2.5-flash",
        code_executor=BuiltInCodeExecutor(),
        description=(
            "Specialised arithmetic assistant that computes numerical results "
            "(percentages, growth rates, averages, sorting) by writing and "
            "executing Python code in a sandboxed Gemini code executor."
        ),
        instruction=_NUMERICAL_ANALYST_INSTRUCTION,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=2048,
        ),
    )


def create_numerical_analyst_subagent() -> LlmAgent:
    """Create the numerical analyst task-mode sub-agent for the ADK 2.0 chat tree.

    Returns an ``LlmAgent(name='numerical_analyst', mode='task')`` with the same
    model / code_executor / description / instruction / generate_content_config as
    ``create_numerical_analyst_agent``. ``mode='task'`` is orthogonal to
    ``code_executor=BuiltInCodeExecutor()`` — the leaf's code executor is
    unaffected by the mode flag. Task-mode dispatch propagates inner events
    to the outer Runner stream so ``usage_metadata`` is counted (AH-99 probe-4).
    See AH-PRD-15 §2 + §5.
    """
    return LlmAgent(
        name="numerical_analyst",
        model="gemini-2.5-flash",
        mode="task",
        code_executor=BuiltInCodeExecutor(),
        description=(
            "Specialised arithmetic assistant that computes numerical results "
            "(percentages, growth rates, averages, sorting) by writing and "
            "executing Python code in a sandboxed Gemini code executor."
        ),
        instruction=_NUMERICAL_ANALYST_INSTRUCTION,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=2048,
        ),
    )


def create_numerical_analyst_agent_tool() -> AgentTool:
    """Create the isolated ``AgentTool`` wrapping the numerical-analyst leaf (chat tree).

    The leaf is named ``numerical_analyst`` so ``AgentTool.name`` matches the
    ``agent.numerical_analyst`` tool id. It carries ONLY ``BuiltInCodeExecutor()``
    — no sibling function tool — which is the invariant Gemini 2.5+ enforces for
    code execution (same ``400 ... all search tools`` class as google_search). The
    AH-114 task-mode variant would inject ``FinishTaskTool`` next to the code
    executor and 400 on dispatch; ``AgentTool`` is the only mechanism that isolates
    it. ``capture_agent_tool_usage`` recovers the leaf's ``usage_metadata`` for
    billing, dropped by ``AgentTool.run_async`` (#3984). See AH-PRD-15 §5 / §7.7.
    """
    leaf = Agent(
        name="numerical_analyst",
        model="gemini-2.5-flash",
        code_executor=BuiltInCodeExecutor(),
        description=(
            "Specialised arithmetic assistant that computes numerical results "
            "(percentages, growth rates, averages, sorting) by writing and "
            "executing Python code in a sandboxed Gemini code executor."
        ),
        instruction=_NUMERICAL_ANALYST_INSTRUCTION,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=2048,
        ),
        after_model_callback=capture_agent_tool_usage,
    )
    # isolation-required: AH-PRD-15 §7.7 — built-in code execution must be isolated
    # in its own AgentTool sub-runner; billing via the leaf after_model_callback.
    return AgentTool(agent=leaf)


# ---------------------------------------------------------------------------
# Registry wiring (side-effect on import) — AH-PRD-15 re-plan (AH-121)
#
# ``task_mode_supported()`` is reused as a "this is the ADK 2.0 chat tree" proxy
# (``LlmAgent.mode`` exists only on 2.0). The 1.34.x deploy tree skips registration
# (it never reads this registry). The isolated AgentTool replaces the AH-114
# task-mode registration: ``mode='task'`` injects ``FinishTaskTool`` next to the
# built-in code executor → Gemini 2.5+ rejects it with the same 400 as google_search.
# ---------------------------------------------------------------------------

if task_mode_supported():
    register_isolated_agent_tool(
        "numerical_analyst", create_numerical_analyst_agent_tool
    )
else:
    logger.info(
        "Skipping numerical_analyst isolated-AgentTool registration on the ADK "
        "1.34.x deploy tree. create_numerical_analyst_agent (ADK 1.34.x leaf) "
        "remains available."
    )


__all__ = [
    "create_numerical_analyst_agent",
    "create_numerical_analyst_agent_tool",
    "create_numerical_analyst_subagent",
]
