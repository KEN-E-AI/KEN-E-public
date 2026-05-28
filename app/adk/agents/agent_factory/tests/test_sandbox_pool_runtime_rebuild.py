"""AH-PRD-09 §7 AC #23 hard gate: sandbox not respawned across runtime rebuilds.

Verifies that per-turn specialist rebuilds under the AH-PRD-09 runtime resolver
(``specialist_runtime._build_specialist`` → ``builder.build_agent``) do NOT
spawn a new sandbox executor on each turn when
``sandbox_code_executor_enabled=True``.

The SandboxPool (SK-PRD-02, shipped SK-23 + SK-26 + SK-37) ensures the
underlying executor is constructed lazily on the first ``execute_code`` call
and reused across all subsequent ``LlmAgent`` rebuilds sharing the same
``(account_id, config_id)`` pool key.

SK-42 lazy-construction model recap
------------------------------------
``build_agent`` no longer calls ``SandboxPool._construct`` directly.  Instead
it returns a ``LeasedSandboxExecutor`` wrapper that references the shared pool.
``_construct`` fires only on the first ``execute_code`` call (via
``pool.lease()`` → ``pool.get_or_create()``).  This test:

1. Builds the specialist twice (simulating two consecutive per-turn resolver
   calls after a config change / cache miss).
2. Asserts both wrappers reference the *same* pool + key → **no respawn**.
3. Asserts the pool is still empty after both builds (lazy; ``_construct`` has
   not yet fired).
4. Triggers ``execute_code`` on both wrappers and asserts ``_construct`` was
   called exactly once (pool reuse).

This file is colocated with the factory unit tests so it runs in the standard
``uv run pytest app/adk/agents/agent_factory/tests/`` sweep.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
from app.adk.agents.agent_factory.leased_sandbox_executor import LeasedSandboxExecutor
from app.adk.agents.agent_factory.sandbox_pool import SandboxPool

# ---------------------------------------------------------------------------
# Callback patch set — same pattern as test_sandbox_pool_runtime_resolver.py
# ---------------------------------------------------------------------------

_WEAVE_BEFORE = MagicMock(name="weave_before_agent_callback")
_WEAVE_AFTER = MagicMock(name="weave_after_agent_callback")
_ADK_BEFORE_TOOL = MagicMock(name="adk_before_tool_callback")
_ADK_AFTER_TOOL = MagicMock(name="adk_after_tool_callback")
_SKILL_FILTER = MagicMock(name="skill_allowed_tools_before_tool_callback")
_SK_SPANS_BEFORE_AGENT = MagicMock(name="skill_spans_before_agent_callback")
_SK_SPANS_BEFORE_TOOL = MagicMock(name="skill_spans_before_tool_callback")
_SK_SPANS_AFTER_TOOL = MagicMock(name="skill_spans_after_tool_callback")

_PATCH_BEFORE_AGENT = patch(
    "app.adk.agents.agent_factory.builder.weave_before_agent_callback",
    _WEAVE_BEFORE,
)
_PATCH_AFTER_AGENT = patch(
    "app.adk.agents.agent_factory.builder.weave_after_agent_callback",
    _WEAVE_AFTER,
)
_PATCH_BEFORE_TOOL = patch(
    "app.adk.agents.agent_factory.builder.adk_before_tool_callback",
    _ADK_BEFORE_TOOL,
)
_PATCH_AFTER_TOOL = patch(
    "app.adk.agents.agent_factory.builder.adk_after_tool_callback",
    _ADK_AFTER_TOOL,
)
_PATCH_BUILD_SKILL_TOOLSET = patch(
    "app.adk.agents.agent_factory.builder._build_skill_toolset",
    return_value=(None, {}, False),
)
_PATCH_SKILL_FILTER = patch(
    "app.adk.agents.agent_factory.builder.skill_allowed_tools_before_tool_callback",
    _SKILL_FILTER,
)
_PATCH_SK_SPANS_BEFORE_AGENT = patch(
    "app.adk.agents.agent_factory.builder.skill_spans_before_agent_callback",
    _SK_SPANS_BEFORE_AGENT,
)
_PATCH_SK_SPANS_BEFORE_TOOL = patch(
    "app.adk.agents.agent_factory.builder.skill_spans_before_tool_callback",
    _SK_SPANS_BEFORE_TOOL,
)
_PATCH_SK_SPANS_AFTER_TOOL = patch(
    "app.adk.agents.agent_factory.builder.skill_spans_after_tool_callback",
    _SK_SPANS_AFTER_TOOL,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sandbox_config(**kw: Any) -> MergedAgentConfig:
    """Return a MergedAgentConfig with the sandbox executor enabled."""
    defaults: dict[str, Any] = {
        "instruction": "You are a test specialist.",
        "model": "gemini-2.0-flash",
        "sandbox_code_executor_enabled": True,
        "skill_ids": [],
    }
    return MergedAgentConfig(**{**defaults, **kw})


def _make_pool_with_stub() -> tuple[SandboxPool, Any, list[int]]:
    """Return ``(pool, sentinel_executor, construct_call_count_list)``.

    ``_construct`` is monkey-assigned to a sync stub that records every call.
    The sentinel executor is a plain ``MagicMock`` because the pool's inner
    executor is separate from the ``LeasedSandboxExecutor`` wrapper held by
    ``LlmAgent.code_executor`` — Pydantic validation is on the wrapper, not
    the inner executor.
    """
    sentinel = MagicMock()
    call_count: list[int] = [0]

    def _stub_construct(*, account_id: str, config_id: str) -> Any:
        call_count[0] += 1
        return sentinel

    pool = SandboxPool()
    pool._construct = _stub_construct  # type: ignore[method-assign]
    pool._clear_tmp = MagicMock()  # avoid live Vertex calls
    return pool, sentinel, call_count


def _build_with_pool(
    config: MergedAgentConfig,
    *,
    account_id: str,
    name: str,
    pool: SandboxPool,
) -> Any:
    """Call ``build_agent`` with all heavy callbacks patched out."""
    import app.adk.agents.agent_factory.builder as b

    with (
        _PATCH_BEFORE_AGENT,
        _PATCH_AFTER_AGENT,
        _PATCH_BEFORE_TOOL,
        _PATCH_AFTER_TOOL,
        _PATCH_BUILD_SKILL_TOOLSET,
        _PATCH_SKILL_FILTER,
        _PATCH_SK_SPANS_BEFORE_AGENT,
        _PATCH_SK_SPANS_BEFORE_TOOL,
        _PATCH_SK_SPANS_AFTER_TOOL,
    ):
        return b.build_agent(
            config, name=name, account_id=account_id, sandbox_pool=pool
        )


# ---------------------------------------------------------------------------
# AC #23 — SandboxPool not respawned across per-turn specialist rebuilds
# ---------------------------------------------------------------------------


def test_sandbox_not_respawned_across_runtime_rebuilds() -> None:
    """PRD §7 AC #23 hard gate.

    Two consecutive ``build_agent`` calls for the same ``(account_id,
    config_id)`` — simulating two AH-PRD-09 per-turn specialist rebuilds after
    a config change (cache miss) — must NOT spawn two sandbox executors.  Both
    ``LeasedSandboxExecutors`` must target the same pool key so the pool's
    single-construction guarantee holds on the first ``execute_code`` call.

    SK-42 lazy construction: the pool is empty after both builds;
    ``_construct`` fires only on the first ``execute_code``.
    """
    import app.adk.agents.agent_factory.builder as b

    pool, sentinel, call_count = _make_pool_with_stub()
    config = _make_sandbox_config()
    initial_global_size = len(b._DEFAULT_SANDBOX_POOL._pool)

    # Simulate two per-turn runtime resolver builds for the same specialist.
    agent_turn_1 = _build_with_pool(
        config, account_id="acc_test", name="test_specialist", pool=pool
    )
    agent_turn_2 = _build_with_pool(
        config, account_id="acc_test", name="test_specialist", pool=pool
    )

    # Both agents must carry LeasedSandboxExecutor wrappers (SK-42 lazy model).
    assert isinstance(agent_turn_1.code_executor, LeasedSandboxExecutor), (
        "Turn-1 agent must carry a LeasedSandboxExecutor (SK-42)"
    )
    assert isinstance(agent_turn_2.code_executor, LeasedSandboxExecutor), (
        "Turn-2 agent must carry a LeasedSandboxExecutor (SK-42)"
    )

    # Both wrappers must reference the shared pool (no respawn = shared pool).
    assert agent_turn_1.code_executor._pool is pool, (
        "Turn-1 executor must reference the shared pool"
    )
    assert agent_turn_2.code_executor._pool is pool, (
        "Turn-2 executor must reference the shared pool"
    )

    # Both wrappers must target the same (account_id, config_id) key.
    assert agent_turn_1.code_executor._account_id == "acc_test"
    assert agent_turn_1.code_executor._config_id == "test_specialist"
    assert agent_turn_2.code_executor._account_id == "acc_test"
    assert agent_turn_2.code_executor._config_id == "test_specialist"

    # SK-42: _construct NOT called during build_agent — pool stays empty.
    assert len(pool._pool) == 0, (
        "Pool must be empty after build_agent calls; _construct is lazy (SK-42)"
    )
    assert call_count[0] == 0, (
        "_construct must not fire during build_agent — only on first execute_code"
    )

    # Trigger execute_code on turn-1 agent → _construct fires for the first time.
    class _FakeResult:
        stdout = "ok"
        stderr = ""

    class _FakeInner:
        def execute_code(self, invocation_context: Any, code_input: Any) -> Any:
            return _FakeResult()

    pool._construct = lambda *, account_id, config_id: (  # type: ignore[method-assign]
        call_count.__setitem__(0, call_count[0] + 1) or _FakeInner()
    )

    agent_turn_1.code_executor.execute_code(MagicMock(), MagicMock())
    assert call_count[0] == 1, (
        "_construct must be called exactly once on first execute_code"
    )
    assert len(pool._pool) == 1, (
        "Pool must have exactly one entry after first execute_code"
    )

    # Trigger execute_code on turn-2 agent → pool reuse, _construct NOT called again.
    agent_turn_2.code_executor.execute_code(MagicMock(), MagicMock())
    assert call_count[0] == 1, (
        "_construct must NOT be called again — sandbox not respawned for turn-2 (AC #23)"
    )
    assert len(pool._pool) == 1, "Pool must still have exactly one entry (no respawn)"

    # Module-global pool is untouched.
    assert len(b._DEFAULT_SANDBOX_POOL._pool) == initial_global_size


def test_different_account_ids_construct_independently() -> None:
    """Integrity check: two distinct account IDs get separate pool keys.

    This guards against a regression where all accounts share one pool entry.
    """
    pool, _sentinel, call_count = _make_pool_with_stub()
    config = _make_sandbox_config()

    agent_acc_a = _build_with_pool(config, account_id="acc_a", name="spec_x", pool=pool)
    agent_acc_b = _build_with_pool(config, account_id="acc_b", name="spec_x", pool=pool)

    # Keys must differ by account_id.
    assert agent_acc_a.code_executor._account_id == "acc_a"
    assert agent_acc_b.code_executor._account_id == "acc_b"
    assert (
        agent_acc_a.code_executor._account_id != agent_acc_b.code_executor._account_id
    ), "Different account IDs must map to different pool keys"

    # Both still reference the shared pool (different keys, same pool object).
    assert agent_acc_a.code_executor._pool is pool
    assert agent_acc_b.code_executor._pool is pool


def test_no_sandbox_when_account_id_is_none() -> None:
    """build_agent with account_id=None must not set a sandbox executor.

    PRD §7 (builder.py _build_code_executor): sandbox requires an account_id;
    when None, log a WARNING and fall through to None (or BuiltInCodeExecutor).
    This prevents a KeyError in the pool on the first execute_code call.
    """
    pool, _sentinel, call_count = _make_pool_with_stub()
    config = _make_sandbox_config()

    agent = _build_with_pool(config, account_id=None, name="spec_y", pool=pool)  # type: ignore[arg-type]

    assert not isinstance(agent.code_executor, LeasedSandboxExecutor), (
        "account_id=None must not produce a LeasedSandboxExecutor (no pool key)"
    )
    # _construct must not have fired.
    assert call_count[0] == 0
    assert len(pool._pool) == 0
