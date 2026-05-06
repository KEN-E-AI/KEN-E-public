from __future__ import annotations

from collections.abc import Callable
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.code_executors import BuiltInCodeExecutor
from google.genai.types import GenerateContentConfig

from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
from app.adk.agents.agent_factory.roster import (
    MAX_TOOLS_PER_SPECIALIST,
    RosterCapExceededError,
)
from app.adk.security.hooks import adk_before_tool_callback
from app.adk.tracking.callbacks import (
    adk_after_tool_callback,
    weave_after_agent_callback,
    weave_before_agent_callback,
)

_MAX_ORG_CONTEXT_CHARS = 4000
_ORG_CONTEXT_BLOCKED = ("[END CONTEXT]", "[ORGANIZATION CONTEXT]")


def _sanitize_org_context(value: str) -> str:
    for seq in _ORG_CONTEXT_BLOCKED:
        value = value.replace(seq, "")
    return value[:_MAX_ORG_CONTEXT_CHARS]


def _make_factory_instruction_provider(
    instruction_text: str,
) -> Callable[[ReadonlyContext], str]:
    def instruction_provider(context: ReadonlyContext) -> str:
        org_context = context.state.get("organization_context")
        if isinstance(org_context, str) and org_context:
            sanitized = _sanitize_org_context(org_context)
            return f"[ORGANIZATION CONTEXT]\n{sanitized}\n[END CONTEXT]\n\n{instruction_text}"
        return instruction_text

    return instruction_provider


def build_agent(
    config: MergedAgentConfig,
    *,
    name: str,
    tools: list[Any] | None = None,
    additional_before_agent_callbacks: list[Callable] | None = None,
    additional_after_agent_callbacks: list[Callable] | None = None,
    additional_before_tool_callbacks: list[Callable] | None = None,
    additional_after_tool_callbacks: list[Callable] | None = None,
    additional_before_model_callbacks: list[Callable] | None = None,
    additional_after_model_callbacks: list[Callable] | None = None,
) -> LlmAgent:
    instruction = _make_factory_instruction_provider(config.instruction)

    generate_content_config: GenerateContentConfig | None = None
    if config.temperature is not None:
        generate_content_config = GenerateContentConfig(temperature=config.temperature)

    # ADK 1.27+ requires code_executor on LlmAgent directly (not via GenerateContentConfig.tools)
    code_executor = BuiltInCodeExecutor() if config.code_execution_enabled else None

    # ADK 1.27+ requires output_schema on LlmAgent directly (not via GenerateContentConfig.response_schema)
    output_schema = config.response_schema

    # Defensive literal cap — catches gross misuse by direct callers that bypass
    # resolve_specialist_roster.  One McpToolset counts as one item here even
    # though it may resolve to many individual MCP tools at runtime, so this is
    # intentionally weaker than the upstream logical cap in roster.py.
    # The upstream resolver is the canonical enforcement point; this is defense
    # in depth.  See AH-PRD-02 §4 Specialist tool rosters and agentic-harness
    # README §2.5 for the full rationale.
    if tools and len(tools) > MAX_TOOLS_PER_SPECIALIST:
        raise RosterCapExceededError(
            f"Specialist {name!r} was passed {len(tools)} items in tools=, "
            f"which exceeds the {MAX_TOOLS_PER_SPECIALIST}-tool cap.  "
            f"Use resolve_specialist_roster() to enforce the cap before construction."
        )

    before_agent_callback: list[Callable] = [weave_before_agent_callback] + (
        additional_before_agent_callbacks or []
    )
    after_agent_callback: list[Callable] = [weave_after_agent_callback] + (
        additional_after_agent_callbacks or []
    )
    before_tool_callback: list[Callable] = [adk_before_tool_callback] + (
        additional_before_tool_callbacks or []
    )
    after_tool_callback: list[Callable] = [adk_after_tool_callback] + (
        additional_after_tool_callbacks or []
    )
    before_model_callback: list[Callable] | None = (
        additional_before_model_callbacks or None
    )
    after_model_callback: list[Callable] | None = (
        additional_after_model_callbacks or None
    )

    return LlmAgent(
        name=name,
        model=config.model,
        description=config.description or "",
        instruction=instruction,
        generate_content_config=generate_content_config,
        tools=tools or [],
        code_executor=code_executor,
        output_schema=output_schema,
        before_agent_callback=before_agent_callback,
        after_agent_callback=after_agent_callback,
        before_tool_callback=before_tool_callback,
        after_tool_callback=after_tool_callback,
        before_model_callback=before_model_callback,
        after_model_callback=after_model_callback,
    )
