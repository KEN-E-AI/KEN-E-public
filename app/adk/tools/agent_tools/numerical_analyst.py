"""Numerical analyst agent tool (AH-149).

``create_numerical_analyst_agent()`` builds a leaf ``Agent`` that only
carries ``code_executor=BuiltInCodeExecutor()`` — no other tools, no MCP
servers, no ``output_schema``. This isolation is load-bearing: Gemini 2.5+
rejects combining built-in code execution with function tools on the same
agent (HTTP 400 "Multiple tools are supported only when they are all search
tools"). The analyst lives in its own leaf and is exposed to the GA
specialist (and any other specialist that needs arithmetic-via-code) as an
``AgentTool`` (agent-as-a-tool).

This module also registers that ``AgentTool`` under the catalogue name
``numerical_analyst`` so it can be assigned to any agent via ``tool_ids``
(opt-in; ``default_global: false`` — see the ``agent_tools:`` entry in
``tools.yaml``).
"""

from __future__ import annotations

import logging

from google.adk.agents import Agent
from google.adk.code_executors import BuiltInCodeExecutor
from google.adk.tools.agent_tool import AgentTool
from google.genai import types

from app.adk.tools.registry.agent_tool_registry import register_agent_tool

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
"""


def create_numerical_analyst_agent() -> Agent:
    """Create the numerical analyst leaf agent (code-execution only, no other tools)."""
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


# ---------------------------------------------------------------------------
# Registry wiring (side-effect on import)
# ---------------------------------------------------------------------------

register_agent_tool("numerical_analyst", AgentTool(agent=create_numerical_analyst_agent()))


__all__ = ["create_numerical_analyst_agent"]
