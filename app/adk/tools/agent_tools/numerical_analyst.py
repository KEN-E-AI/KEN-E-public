"""Numerical analyst agent tool (AH-149 / AH-114).

``create_numerical_analyst_agent()`` builds a leaf ``Agent`` that only
carries ``code_executor=BuiltInCodeExecutor()`` — no other tools, no MCP
servers, no ``output_schema``. This isolation is load-bearing: Gemini 2.5+
rejects combining built-in code execution with function tools on the same
agent (HTTP 400 "Multiple tools are supported only when they are all search
tools"). The analyst lives in its own leaf and is exposed to the GA
specialist (and any other specialist that needs arithmetic-via-code) as an
agent-as-a-tool.

AH-114 (ADK 2.0 task-mode migration): ``create_numerical_analyst_subagent()``
builds the equivalent ``LlmAgent(mode='task')`` for the ADK 2.0 chat tree.
Task-mode dispatch (``request_task_numerical_analyst`` / ``complete_task``)
propagates inner events to the outer stream natively (AH-99 probe-4), fixing
the AH-75 billing / trace defect. ``mode='task'`` is orthogonal to
``code_executor=`` — the leaf's own code executor is unaffected. This module
registers the task-mode variant under the catalogue name ``numerical_analyst``
so it can be assigned to any agent via ``tool_ids`` (opt-in;
``default_global: false`` — see the ``agent_tools:`` entry in ``tools.yaml``).

``create_numerical_analyst_agent`` is left byte-identical — it is the
non-task-mode constructor kept for symmetry with the google_search isolation
pattern and to preserve any caller that might use it outside the ADK 2.0 chat
path.

Design reference: AH-PRD-15 §2 (scope boundary), §5 (Implementation Outline), AH-114.
"""

from __future__ import annotations

import logging

from google.adk.agents import Agent, LlmAgent
from google.adk.code_executors import BuiltInCodeExecutor
from google.genai import types

from app.adk.tools.registry.agent_tool_registry import (
    register_agent_subagent,
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


# ---------------------------------------------------------------------------
# Registry wiring (side-effect on import) — AH-114
#
# ``task_mode_supported()`` gates construction + registration: ``LlmAgent(mode=
# 'task')`` only validates on ADK 2.0+. Any ADK-1.34.x deploy tree that imports
# this module skips the task-mode sub-agent rather than crashing at import on the
# missing ``mode`` field. See ``task_mode_supported`` docstring and AH-PRD-15 §2.
# ---------------------------------------------------------------------------

if task_mode_supported():
    register_agent_subagent("numerical_analyst", create_numerical_analyst_subagent)
else:
    logger.info(
        "Skipping numerical_analyst task-mode registration: installed google-adk "
        "LlmAgent has no 'mode' field (ADK 1.34.x deploy tree). "
        "create_numerical_analyst_agent (ADK 1.34.x leaf) remains available."
    )


__all__ = ["create_numerical_analyst_agent", "create_numerical_analyst_subagent"]
