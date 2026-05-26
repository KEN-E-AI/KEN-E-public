from __future__ import annotations

import logging
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
from app.adk.agents.utils import config_cache
from app.adk.security.hooks import adk_before_tool_callback
from app.adk.tracking.callbacks import (
    adk_after_tool_callback,
    weave_after_agent_callback,
    weave_before_agent_callback,
)

logger = logging.getLogger(__name__)

_MAX_ORG_CONTEXT_CHARS = 4000
_ORG_CONTEXT_BLOCKED = ("[END CONTEXT]", "[ORGANIZATION CONTEXT]")


def _sanitize_org_context(value: str) -> str:
    for seq in _ORG_CONTEXT_BLOCKED:
        value = value.replace(seq, "")
    return value[:_MAX_ORG_CONTEXT_CHARS]


def _make_factory_instruction_provider(
    instruction_text: str,
    *,
    config_doc_id: str | None = None,
    instruction_suffix: str = "",
) -> Callable[[ReadonlyContext], str]:
    def instruction_provider(context: ReadonlyContext) -> str:
        base = instruction_text
        if config_doc_id is not None:
            try:
                cfg, _, _ = config_cache.get_cached_config(config_doc_id)
                if cfg.instruction:
                    base = cfg.instruction
            except Exception as exc:
                logger.warning(
                    "InstructionProvider could not load %r from cache (%s); "
                    "falling back to deploy-time instruction",
                    config_doc_id,
                    exc,
                )

        full_instruction = (
            (base.rstrip() + "\n\n" + instruction_suffix).rstrip()
            if instruction_suffix
            else base
        )
        org_context = context.state.get("organization_context")
        if isinstance(org_context, str) and org_context:
            sanitized = _sanitize_org_context(org_context)
            return f"[ORGANIZATION CONTEXT]\n{sanitized}\n[END CONTEXT]\n\n{full_instruction}"
        return full_instruction

    return instruction_provider


def build_agent(
    config: MergedAgentConfig,
    *,
    name: str,
    tools: list[Any] | None = None,
    config_doc_id: str | None = None,
    instruction_suffix: str = "",
    additional_before_agent_callbacks: list[Callable] | None = None,
    additional_after_agent_callbacks: list[Callable] | None = None,
    additional_before_tool_callbacks: list[Callable] | None = None,
    additional_after_tool_callbacks: list[Callable] | None = None,
    additional_before_model_callbacks: list[Callable] | None = None,
    additional_after_model_callbacks: list[Callable] | None = None,
) -> LlmAgent:
    instruction = _make_factory_instruction_provider(
        config.instruction,
        config_doc_id=config_doc_id,
        instruction_suffix=instruction_suffix,
    )

    # AH-40: reconstruct the SDK GenerateContentConfig from flat fields at
    # the ADK construction boundary. Storage is flat; the nested grouping
    # exists only as an SDK API concern.
    gcc_kwargs: dict[str, Any] = {}
    if config.temperature is not None:
        gcc_kwargs["temperature"] = config.temperature
    if config.max_output_tokens is not None:
        gcc_kwargs["max_output_tokens"] = config.max_output_tokens
    generate_content_config: GenerateContentConfig | None = (
        GenerateContentConfig(**gcc_kwargs) if gcc_kwargs else None
    )

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
