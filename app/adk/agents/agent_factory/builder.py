from __future__ import annotations

import asyncio
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
from shared.structured_logging import get_structured_logger

logger = get_structured_logger(__name__)

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
                # Intentionally broad: any cache/Firestore failure must not
                # crash the turn — fall back to the deploy-time instruction.
                logger.warning(
                    "InstructionProvider could not load %r from cache (%s); "
                    "falling back to deploy-time instruction",
                    config_doc_id,
                    type(exc).__name__,
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


async def _build_skill_toolset_async(
    account_id: str,
    skill_ids: list[str],
    *,
    config_id: str | None,
) -> Any | None:
    """Async core: load skill objects and construct a SkillToolset.

    The ``kene_api.services.skill_loader`` import is deferred so the agent
    module remains collectible in CI environments where ``kene_api`` is not
    installed (mirrors the lazy-import pattern in ``app/adk/tracking/usage.py``).
    """
    # Deferred import — kene_api is not available in the app-adk-tests CI venv.
    from kene_api.services.skill_loader import (
        SkillCorruptError,
        SkillNotFoundError,
        load_skill,
    )

    loaded_skills = []
    for sid in skill_ids:
        try:
            skill = await load_skill(account_id, sid)
            loaded_skills.append(skill)
        except (SkillNotFoundError, SkillCorruptError) as exc:
            logger.warning(
                "skill_load_skipped",
                extra={
                    "account_id": account_id,
                    "config_id": config_id,
                    "skill_id": sid,
                    "reason": str(exc),
                },
            )
        except Exception as exc:  # tolerate unexpected loader errors
            logger.warning(
                "skill_load_skipped",
                extra={
                    "account_id": account_id,
                    "config_id": config_id,
                    "skill_id": sid,
                    "reason": f"{type(exc).__name__}: {exc}",
                },
            )

    if not loaded_skills:
        logger.error(
            "skill_load_total_failure",
            extra={
                "account_id": account_id,
                "config_id": config_id,
                "skill_ids": skill_ids,
            },
        )
        return None

    # Deferred import — SkillToolset lives in google.adk.tools.skill_toolset
    # (not google.adk.skills, which does not re-export it in ADK 1.27.x).
    from google.adk.tools.skill_toolset import SkillToolset

    try:
        return SkillToolset(skills=loaded_skills)
    except ValueError as exc:
        # Duplicate skill names (stale data) — degrade same as total failure.
        logger.error(
            "skill_load_total_failure",
            extra={
                "account_id": account_id,
                "config_id": config_id,
                "skill_ids": skill_ids,
                "reason": f"SkillToolset construction failed: {exc}",
            },
        )
        return None


def _build_skill_toolset(
    account_id: str | None,
    skill_ids: list[str],
    *,
    config_id: str | None,
) -> Any | None:
    """Load skill objects and construct a SkillToolset.

    Returns ``None`` when ``skill_ids`` is empty, ``account_id`` is ``None``,
    or every skill fails to load.  Single-skill failures are tolerated with a
    WARNING; total failure emits an ERROR.

    Runs the async loader via ``asyncio.run()``.  This is safe for the
    deploy-time ``build_hierarchy()`` path where no event loop is running.
    SK-26 / AH-PRD-09 will make ``build_agent`` async when per-turn
    reconstruction requires it.
    """
    if not skill_ids:
        return None

    if account_id is None:
        logger.warning(
            "skill_toolset_skipped_no_account",
            extra={"config_id": config_id, "skill_ids": skill_ids},
        )
        return None

    # Guard against callers that already hold a running event loop (e.g. async
    # tests, FastAPI startup hooks).  asyncio.run() raises RuntimeError in that
    # case; detect it early and degrade gracefully so the agent still builds.
    try:
        asyncio.get_running_loop()
        logger.error(
            "skill_toolset_skipped_event_loop_conflict",
            extra={"config_id": config_id, "skill_ids": skill_ids},
        )
        return None
    except RuntimeError:
        pass  # No running loop — safe to call asyncio.run()

    return asyncio.run(
        _build_skill_toolset_async(account_id, skill_ids, config_id=config_id)
    )


def build_agent(
    config: MergedAgentConfig,
    *,
    name: str,
    account_id: str | None,
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

    # SK-PRD-02: hydrate a SkillToolset when the config has attached skills.
    # _build_skill_toolset returns None when skill_ids is empty, account_id is
    # None, or every skill fails to load (total-failure ERROR is logged then).
    assembled_tools: list[Any] = list(tools or [])
    skill_load_total_failure = False
    if config.skill_ids:
        skill_toolset = _build_skill_toolset(
            account_id,
            config.skill_ids,
            config_id=config_doc_id,
        )
        if skill_toolset is not None:
            assembled_tools.append(skill_toolset)
        elif account_id is not None:
            # account_id was provided but every skill failed — genuine failure.
            # When account_id is None, the skip is expected (global deploy) and
            # is NOT treated as a total failure.
            skill_load_total_failure = True

    # Defensive literal cap — catches gross misuse by direct callers that bypass
    # resolve_specialist_roster.  One McpToolset counts as one item here even
    # though it may resolve to many individual MCP tools at runtime, so this is
    # intentionally weaker than the upstream logical cap in roster.py.
    # The upstream resolver is the canonical enforcement point; this is defense
    # in depth.  See AH-PRD-02 §4 Specialist tool rosters and agentic-harness
    # README §2.5 for the full rationale.
    if assembled_tools and len(assembled_tools) > MAX_TOOLS_PER_SPECIALIST:
        raise RosterCapExceededError(
            f"Specialist {name!r} was passed {len(assembled_tools)} items in tools=, "
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

    agent = LlmAgent(
        name=name,
        model=config.model,
        description=config.description or "",
        instruction=instruction,
        generate_content_config=generate_content_config,
        tools=assembled_tools,
        code_executor=code_executor,
        output_schema=output_schema,
        before_agent_callback=before_agent_callback,
        after_agent_callback=after_agent_callback,
        before_tool_callback=before_tool_callback,
        after_tool_callback=after_tool_callback,
        before_model_callback=before_model_callback,
        after_model_callback=after_model_callback,
    )

    if skill_load_total_failure:
        # Hand-off marker for SK-27 (skill.* Weave spans): when every
        # requested skill failed to load, the agent carries no SkillToolset
        # and no list_skills tool will ever fire.  SK-27 can read this flag
        # to emit skill_load_total_failure=true on a synthetic span.
        # TODO(SK-27): remove this bypass once SK-27 adds span instrumentation.
        object.__setattr__(agent, "_kene_skill_load_total_failure", True)

    return agent
