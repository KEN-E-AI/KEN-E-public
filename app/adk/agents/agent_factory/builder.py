from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Callable
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.code_executors import BuiltInCodeExecutor
from google.genai.types import GenerateContentConfig

from app.adk.agents.agent_factory._executors import get_pool_checkout_executor
from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
from app.adk.agents.agent_factory.leased_sandbox_executor import LeasedSandboxExecutor
from app.adk.agents.agent_factory.roster import (
    MAX_TOOLS_PER_SPECIALIST,
    RosterCapExceededError,
)
from app.adk.agents.agent_factory.sandbox_pool import SandboxPool
from app.adk.agents.agent_factory.skill_metadata import record_skill_build_metadata
from app.adk.agents.skill_tool_filter import skill_allowed_tools_before_tool_callback
from app.adk.agents.utils import config_cache
from app.adk.security.hooks import adk_before_tool_callback
from app.adk.tracking.callbacks import (
    adk_after_tool_callback,
    weave_after_agent_callback,
    weave_before_agent_callback,
)
from app.adk.tracking.skill_spans import (
    assert_skill_tool_names_match,
    skill_spans_after_tool_callback,
    skill_spans_before_agent_callback,
    skill_spans_before_tool_callback,
)
from shared.structured_logging import get_structured_logger

logger = get_structured_logger(__name__)

_MAX_ORG_CONTEXT_CHARS = 4000
_ORG_CONTEXT_BLOCKED = ("[END CONTEXT]", "[ORGANIZATION CONTEXT]")
_SKILL_LOAD_TIMEOUT_SECONDS = 30

# Process-wide singleton — one pool per Cloud Run instance. Mirrors the
# ``_specialists_cache`` singleton pattern in specialist_runtime.py:169.
# Tests inject a fresh pool or a MagicMock via the ``sandbox_pool=`` kwarg
# on ``build_agent`` so the module global is never mutated by test code.
#
# start() / stop() are wired by the runtime entrypoints (SK-37):
#   - FastAPI lifespan in api/src/kene_api/main.py (Cloud Run process)
#   - attach_specialists_before_agent_callback in sub_agent_attacher.py
#     (Agent Engine process — no AdkApp startup hook in pinned ADK version)
_DEFAULT_SANDBOX_POOL: SandboxPool = SandboxPool()


def _sanitize_org_context(value: str) -> str:
    for seq in _ORG_CONTEXT_BLOCKED:
        value = value.replace(seq, "")
    return value[:_MAX_ORG_CONTEXT_CHARS]


def _make_factory_instruction_provider(
    instruction_text: str,
    *,
    config_doc_id: str | None = None,
    instruction_suffix: str = "",
    instruction_suffix_provider: Callable[[ReadonlyContext], str] | None = None,
) -> Callable[[ReadonlyContext], str]:
    if instruction_suffix and instruction_suffix_provider is not None:
        raise ValueError(
            "instruction_suffix and instruction_suffix_provider are mutually exclusive; "
            "supply at most one."
        )

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

        if instruction_suffix_provider is not None:
            dynamic_suffix = instruction_suffix_provider(context)
            full_instruction = (
                (base.rstrip() + "\n\n" + dynamic_suffix).rstrip()
                if dynamic_suffix
                else base
            )
        else:
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
) -> tuple[Any | None, dict]:
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

    # loaded_pairs preserves insertion order; errors are skipped.
    # Tracking (sid, skill) together lets us build the name→skill_id index later.
    loaded_pairs: list[tuple[str, Any]] = []
    for sid in skill_ids:
        try:
            skill = await load_skill(account_id, sid)
            loaded_pairs.append((sid, skill))
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

    if not loaded_pairs:
        logger.error(
            "skill_load_total_failure",
            extra={
                "account_id": account_id,
                "config_id": config_id,
                "skill_ids": skill_ids,
            },
        )
        return None, {}

    loaded_skills = [skill for _, skill in loaded_pairs]

    # Deferred import — SkillToolset lives in google.adk.tools.skill_toolset
    # (not google.adk.skills, which does not re-export it in ADK 1.27.x).
    from google.adk.tools.skill_toolset import SkillToolset

    # Build name → {skill_id, version, allowed_tools} index consumed by SK-27
    # (skill_spans.py callbacks) for span attrs and skills_allowed_tools seeding.
    # `version=0` is a v1 placeholder: load_skill() resolves current_version
    # internally but the ADK Skill type does not surface it.  SK-29 / SK-PRD-05
    # will plumb the resolved version once the loader API exposes it.
    skill_name_index: dict[str, dict] = {
        skill.frontmatter.name: {
            "skill_id": sid,
            "version": 0,
            "allowed_tools": skill.frontmatter.allowed_tools,
        }
        for sid, skill in loaded_pairs
    }

    try:
        toolset = SkillToolset(skills=loaded_skills)
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
        return None, {}

    # Verify SkillToolset's auto-generated tool names match our hardcoded
    # constants in skill_spans.py.  RuntimeError propagates to the caller —
    # a rename is a build-time programmer error, not a degrade-open scenario.
    # The module-level flag amortises this to a single introspection per process.
    assert_skill_tool_names_match(toolset)
    return toolset, skill_name_index


def _build_skill_toolset(
    account_id: str | None,
    skill_ids: list[str],
    *,
    config_id: str | None,
) -> tuple[Any | None, dict, bool]:
    """Load skill objects and construct a SkillToolset.

    Returns ``(toolset, skill_name_index, timed_out)``:

    * ``toolset`` is ``None`` when ``skill_ids`` is empty, ``account_id`` is
      ``None``, every skill fails to load, or the load times out.  Single-skill
      failures are tolerated with a WARNING; total failure emits an ERROR.
    * ``skill_name_index`` maps ``skill.frontmatter.name`` →
      ``{skill_id, version, allowed_tools}`` for all loaded skills.  Empty when
      no skills loaded or when the toolset is ``None``.  Consumed by SK-27
      (``skill_spans.py``) to resolve span attrs at callback time.
    * ``timed_out`` is ``True`` only when the worker-thread bridge hit
      ``_SKILL_LOAD_TIMEOUT_SECONDS``.  The caller surfaces this as a separate
      sidecar marker so ops can distinguish "infra slow" from "every skill
      genuinely failed" (which has a different remediation path).

    Works from both sync callers (deploy-time ``build_hierarchy()``) and async
    callers (any future FastAPI / per-turn rebuild path).  When invoked inside
    a running event loop, the async loader is run on a worker thread that owns
    a fresh loop — mirrors the pattern in
    ``app/adk/agents/utils/supervisor_utils.py:181-207`` and
    ``app/adk/agents/strategy_agent/artifact_utils.py:171-180``.
    """
    if not skill_ids:
        return None, {}, False

    if account_id is None:
        logger.warning(
            "skill_toolset_skipped_no_account",
            extra={"config_id": config_id, "skill_ids": skill_ids},
        )
        return None, {}, False

    # asyncio.get_running_loop() raises RuntimeError when no loop is active,
    # which is the Python 3.12+ canonical way to probe loop state.
    try:
        asyncio.get_running_loop()
        running = True
    except RuntimeError:
        running = False

    if not running:
        toolset, skill_name_index = asyncio.run(
            _build_skill_toolset_async(account_id, skill_ids, config_id=config_id)
        )
        return toolset, skill_name_index, False

    # A loop is already running — submit asyncio.run on a worker thread so we
    # don't collide with the caller's loop.  The thread owns its own event loop
    # for the lifetime of the coroutine, then tears it down.
    #
    # AH-77 Item F / AH-80: reuse the process-wide singleton executor rather
    # than constructing a new ThreadPoolExecutor per skill-toolset load.  The
    # executor's sole role is timeout enforcement via future.result(timeout=…) —
    # it is not used for parallelism.  Mirrors specialist_runtime.py:452-456.
    def _runner() -> tuple[Any | None, dict]:
        return asyncio.run(
            _build_skill_toolset_async(account_id, skill_ids, config_id=config_id)
        )

    future = get_pool_checkout_executor().submit(_runner)
    try:
        toolset, skill_name_index = future.result(
            timeout=_SKILL_LOAD_TIMEOUT_SECONDS
        )
        return toolset, skill_name_index, False
    except concurrent.futures.TimeoutError:
        logger.error(
            "skill_toolset_load_timeout",
            extra={
                "account_id": account_id,
                "config_id": config_id,
                "skill_ids": skill_ids,
                "timeout_s": _SKILL_LOAD_TIMEOUT_SECONDS,
            },
        )
        return None, {}, True


def _build_code_executor(
    config: MergedAgentConfig,
    *,
    account_id: str | None,
    name: str,
    sandbox_pool: SandboxPool,
) -> Any:
    """Resolve the code executor for this agent using sandbox > built-in > None precedence.

    * ``sandbox_code_executor_enabled=True`` → return a ``LeasedSandboxExecutor``
      that routes every ``execute_code`` call through ``sandbox_pool.lease()``
      (SK-42 CLOBBER fix).  The underlying pooled
      ``AgentEngineSandboxCodeExecutor`` is constructed on first use and reused
      across ``LlmAgent`` rebuilds under AH-PRD-09's per-turn resolver.  This
      wins over ``code_execution_enabled`` when both are True — AC-4 requires
      the sandbox specifically and ``LlmAgent.code_executor`` is a single field.
    * ``sandbox_code_executor_enabled=False`` (or absent) → fall through to
      the existing ``code_execution_enabled`` rule (``BuiltInCodeExecutor()``
      or ``None``).

    ``account_id is None`` returns ``None`` regardless of
    ``code_execution_enabled`` — requesting sandbox is a hard requirement, not a
    soft preference, and the pool cannot be keyed without an account, so a
    WARNING is emitted before the ``None`` return so operators retain the
    signal.  See DESIGN-REVIEW-LOG Review 36 for the fail-closed rationale.

    Construction is a cheap, synchronous, I/O-free call:
    ``LeasedSandboxExecutor`` only stores the pool + key, and the pooled
    ``AgentEngineSandboxCodeExecutor.__init__`` merely parses a resource-name
    regex.  The real sandbox cold-start happens lazily inside the inner
    ``execute_code`` (ADK's ``sandboxes.create``), so there is nothing here to
    bound with a timeout; ``SandboxPool._clear_tmp`` keeps its own 5s bound.
    """
    if config.sandbox_code_executor_enabled:
        if account_id is None:
            logger.warning(
                "sandbox_skipped_no_account",
                extra={"config_id": name},
            )
            return None

        return LeasedSandboxExecutor(
            pool=sandbox_pool,
            account_id=account_id,
            config_id=name,
        )

    return BuiltInCodeExecutor() if config.code_execution_enabled else None


def build_agent(
    config: MergedAgentConfig,
    *,
    name: str,
    account_id: str | None,
    tools: list[Any] | None = None,
    config_doc_id: str | None = None,
    instruction_suffix: str = "",
    instruction_suffix_provider: Callable[[ReadonlyContext], str] | None = None,
    sandbox_pool: SandboxPool | None = None,
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
        instruction_suffix_provider=instruction_suffix_provider,
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

    # ADK 1.27+ requires code_executor on LlmAgent directly (not via GenerateContentConfig.tools).
    # SK-PRD-02: delegate to SandboxPool when sandbox_code_executor_enabled is set;
    # sandbox takes precedence over BuiltInCodeExecutor when both flags are true.
    code_executor = _build_code_executor(
        config,
        account_id=account_id,
        name=name,
        sandbox_pool=sandbox_pool
        if sandbox_pool is not None
        else _DEFAULT_SANDBOX_POOL,
    )

    # ADK 1.27+ requires output_schema on LlmAgent directly (not via GenerateContentConfig.response_schema)
    output_schema = config.response_schema

    # SK-PRD-02: hydrate a SkillToolset when the config has attached skills.
    # _build_skill_toolset returns (toolset, skill_name_index, timed_out).
    # toolset is None when skill_ids is empty, account_id is None, every skill
    # fails to load, or the load timed out.  timed_out distinguishes the
    # infra-failure case (logged below as skill_load_timeout on the sidecar)
    # from a genuine total failure.
    assembled_tools: list[Any] = list(tools or [])
    skill_load_total_failure = False
    skill_load_timeout = False
    skill_name_index: dict[str, Any] = {}
    if config.skill_ids:
        skill_toolset, skill_name_index, skill_load_timeout = _build_skill_toolset(
            account_id,
            config.skill_ids,
            config_id=config_doc_id,
        )
        if skill_toolset is not None:
            assembled_tools.append(skill_toolset)
        elif account_id is not None and not skill_load_timeout:
            # account_id was provided and we didn't time out, yet every skill
            # failed — genuine total failure.  When account_id is None the skip
            # is expected (global deploy); when we timed out, that's the
            # skill_load_timeout marker, not a total failure.
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

    before_agent_callback: list[Callable] = [
        weave_before_agent_callback,
        skill_spans_before_agent_callback,
        *(additional_before_agent_callbacks or []),
    ]
    after_agent_callback: list[Callable] = [weave_after_agent_callback] + (
        additional_after_agent_callbacks or []
    )
    before_tool_callback: list[Callable] = [
        adk_before_tool_callback,
        skill_allowed_tools_before_tool_callback,
        skill_spans_before_tool_callback,
        *(additional_before_tool_callbacks or []),
    ]
    after_tool_callback: list[Callable] = [
        adk_after_tool_callback,
        skill_spans_after_tool_callback,
        *(additional_after_tool_callbacks or []),
    ]
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

    # Stash build-time skill outcomes on the sidecar so SK-27 can surface them
    # as attributes on the skill.list Weave span:
    #   * skill_load_total_failure  (SK-PRD-02 §7 AC-2a): every requested skill
    #     failed to load; the agent carries no SkillToolset and list_skills
    #     never fires.
    #   * skill_load_timeout: the 30s worker-thread bridge fired before any
    #     skill loaded.  Separate from total_failure because the remediation
    #     is different (infra/retry vs. stale skill IDs / config).
    #   * skill_name_index: maps frontmatter name → {skill_id, version,
    #     allowed_tools} for all successfully loaded skills.  Consumed by
    #     SK-27 (skill_spans.py) to resolve span attrs and seed
    #     state["skills_allowed_tools"] at turn start.
    if skill_load_total_failure:
        record_skill_build_metadata(agent, skill_load_total_failure=True)
    if skill_load_timeout:
        record_skill_build_metadata(agent, skill_load_timeout=True)
    if skill_name_index:
        record_skill_build_metadata(agent, skill_name_index=skill_name_index)

    return agent
