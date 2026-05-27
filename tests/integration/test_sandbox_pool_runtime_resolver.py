"""Integration test: SandboxPool reuse under simulated AH-PRD-09 runtime resolver.

SK-31 — AC-13 (SK-PRD-02 §7).

Simulates AH-PRD-09's per-turn LlmAgent rebuild: calls build_agent N times for
the same (account_id, config_id) against a single SandboxPool, asserts
SandboxPool._construct is invoked exactly once, and validates span emission.

No live Gemini, Firestore, or GCS I/O — pure in-process pool semantics.

Coverage
--------
* AC-13 — SandboxPool reuse: _construct invoked exactly once across N rebuilds;
  all rebuilt agents share the same code_executor instance (is-identity).
* AC-13 — cache_hit spans: first sandbox_pool.get has cache_hit=False,
  remaining N-1 have cache_hit=True; pool_size_after=1 throughout.
* Integrity guard: two distinct config_ids each trigger exactly one _construct
  and return different executor instances so the single-construct assertion in
  test 1 is not vacuous.

Design notes
------------
Tests drive through build_agent (the public seam AH-PRD-09's
specialist_runtime._build_specialist calls at specialist_runtime.py:367) rather
than _build_code_executor directly — the boundary crossed is identical to the
production path.

_construct is monkey-assigned (not via unittest.mock.patch) to return a
BuiltInCodeExecutor() sentinel.  A MagicMock fails Pydantic's code_executor
type validation; BuiltInCodeExecutor() is a no-arg BaseCodeExecutor subclass
already in the test environment.  This follows test_sandbox_pool.py and
test_factory_skills.py:TestAC5IndependenceMatrix._make_mock_pool.

Span capture mirrors _make_span_recorder() in test_sandbox_pool.py:490-504.
The helper is intentionally duplicated here per CLAUDE.md C-9: promote to
shared only on the third caller.

The module-global _DEFAULT_SANDBOX_POOL in builder.py is never touched —
every build_agent call receives sandbox_pool=pool explicitly.  Each test
asserts the global pool is unchanged at start and end to guard against bleed.

Relationship with SK-30
-----------------------
SK-30 is the live-Gemini E2E that marks @pytest.mark.llm and uses a real
Vertex endpoint.  SK-31 is the no-LLM pool-reuse path; both live in
tests/integration/ but do not share any files.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

# ── neo4j mock — must precede any app imports ─────────────────────────────────
# Mirrors tests/integration/test_review_loop_single_step.py:32-37.
# app/conftest.py does not run for tests/integration/ paths, so the mock must
# be applied at module level here.
_neo4j_mock = MagicMock()
_neo4j_mock.exceptions = MagicMock()
_neo4j_mock.exceptions.ServiceUnavailable = Exception
_neo4j_mock.exceptions.SessionExpired = Exception
sys.modules.setdefault("neo4j", _neo4j_mock)
sys.modules.setdefault("neo4j.exceptions", _neo4j_mock.exceptions)

# ── sys.path: expose app/ as import root ──────────────────────────────────────
_app_dir = Path(__file__).parents[2] / "app"
if str(_app_dir) not in sys.path:
    sys.path.insert(0, str(_app_dir))

# ── Imports (after neo4j mock and path setup) ─────────────────────────────────
from app.adk.agents.agent_factory.config_loader import MergedAgentConfig  # noqa: E402
from app.adk.agents.agent_factory.sandbox_pool import SandboxPool  # noqa: E402

# ---------------------------------------------------------------------------
# Shared patch targets — mirrors test_factory.py:30-69
#
# All callbacks that would transitively import Weave, Firestore, or kene_api
# are patched to MagicMock sentinels so test collection succeeds in the
# app-adk-tests CI environment where those dependencies are not installed.
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
# _build_skill_toolset is patched to (None, {}, False) — the SK-27 extended
# triple — so skill_ids=[] keeps the skill path inert without requiring
# kene_api to be installed (belt-and-suspenders).
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

# Span emission patch target — same path the unit tests use at
# test_sandbox_pool.py:487.
_SPAN_PATH = "app.adk.agents.agent_factory.sandbox_pool.emit_sandbox_pool_span"

# Number of simulated per-turn rebuilds.  Large enough to distinguish
# "constructed once" from "constructed per call"; matches the concurrent-fanout
# count (asyncio.gather × 10) in test_sandbox_pool.py.
_N_REBUILDS = 10

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**kw: Any) -> MergedAgentConfig:
    """Return a MergedAgentConfig with sandbox enabled and no skills."""
    defaults: dict[str, Any] = {
        "instruction": "You are a test specialist.",
        "model": "gemini-2.0-flash",
        "sandbox_code_executor_enabled": True,
        "skill_ids": [],
    }
    return MergedAgentConfig(**{**defaults, **kw})


def _make_pool_with_stub() -> tuple[SandboxPool, Any, list[int]]:
    """Return (pool, executor_sentinel, construct_call_count_list).

    pool._construct is monkey-assigned to an async stub that always returns the
    same BuiltInCodeExecutor() sentinel regardless of key.  construct_call_count
    is a one-element list so the closure can mutate it.

    list.append / int mutation via index is GIL-protected on CPython; the
    10-rebuild loop is sequential (each build_agent returns before the next
    starts), so there is no concurrent mutation concern.
    """
    from google.adk.code_executors import BuiltInCodeExecutor

    sentinel = BuiltInCodeExecutor()
    call_count: list[int] = [0]

    async def _stub_construct(*, account_id: str, config_id: str) -> Any:
        call_count[0] += 1
        return sentinel

    pool = SandboxPool()
    pool._construct = _stub_construct  # type: ignore[method-assign]
    return pool, sentinel, call_count


def _make_pool_with_per_key_stub() -> tuple[
    SandboxPool, dict[tuple[str, str], Any], list[int]
]:
    """Return (pool, executors_by_key, construct_call_count_list).

    Like _make_pool_with_stub but returns a distinct BuiltInCodeExecutor()
    instance for each unique (account_id, config_id) key.  Used by the
    integrity-check test to verify that different keys yield different executors.
    """
    from google.adk.code_executors import BuiltInCodeExecutor

    executors: dict[tuple[str, str], Any] = {}
    call_count: list[int] = [0]

    async def _stub_construct(*, account_id: str, config_id: str) -> Any:
        call_count[0] += 1
        key = (account_id, config_id)
        if key not in executors:
            executors[key] = BuiltInCodeExecutor()
        return executors[key]

    pool = SandboxPool()
    pool._construct = _stub_construct  # type: ignore[method-assign]
    return pool, executors, call_count


def _make_span_recorder() -> tuple[list[tuple[str, dict]], Any]:
    """Return (recorded_spans, AsyncContextManager patch target).

    Mirrors app/adk/agents/agent_factory/tests/test_sandbox_pool.py:490-504.
    Each emitted span appends (name, attrs) to *recorded_spans*.

    Intentionally duplicated rather than promoted to a shared helper —
    only two callers exist today (CLAUDE.md C-9: promote on the third).
    """
    recorded: list[tuple[str, dict]] = []

    import contextlib

    @contextlib.asynccontextmanager
    async def _recording_span(name: str, attrs: dict) -> Any:
        recorded.append((name, dict(attrs)))
        yield

    return recorded, _recording_span


def _build_with_pool(
    config: MergedAgentConfig,
    *,
    account_id: str,
    name: str,
    pool: SandboxPool,
) -> Any:
    """Call build_agent through the 9-patch callback fixture.

    All callbacks that transitively import Weave / Firestore / kene_api are
    replaced with MagicMock sentinels.  sandbox_pool=pool is passed explicitly
    so the module-global _DEFAULT_SANDBOX_POOL is never touched.
    """
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
# Test 1 — AC-13: _construct invoked exactly once; all rebuilt agents share
#           the same code_executor instance by is-identity.
# ---------------------------------------------------------------------------


def test_repeated_build_agent_reuses_pooled_sandbox() -> None:
    """N build_agent calls for the same key → _construct once; is-identity holds.

    AC-13 (SK-PRD-02 §7): \"Under a simulated runtime resolver where the
    LlmAgent is rebuilt on every turn (mirroring the agent_cache miss path),
    the sandbox is reused from the pool — _construct is invoked exactly once
    across N rebuilds for the same (account_id, config_id).\"
    """
    import app.adk.agents.agent_factory.builder as b

    pool, sentinel, call_count = _make_pool_with_stub()
    config = _make_config()

    # Guard: module-global pool is untouched before this test.
    initial_global_size = len(b._DEFAULT_SANDBOX_POOL._pool)

    agents = [
        _build_with_pool(config, account_id="acc_x", name="spec_a", pool=pool)
        for _ in range(_N_REBUILDS)
    ]

    assert call_count[0] == 1, (
        f"_construct was called {call_count[0]} times; expected exactly 1 "
        f"across {_N_REBUILDS} simulated per-turn rebuilds"
    )
    assert all(a.code_executor is sentinel for a in agents), (
        "Every rebuilt LlmAgent must share the same code_executor instance (is-identity)"
    )

    # Guard: module-global pool is untouched after this test.
    assert len(b._DEFAULT_SANDBOX_POOL._pool) == initial_global_size


# ---------------------------------------------------------------------------
# Test 2 — AC-13: sandbox_pool.get spans report cache_hit correctly across
#           N rebuild calls.
# ---------------------------------------------------------------------------


def test_repeated_build_agent_emits_cache_hit_spans() -> None:
    """First rebuild emits cache_hit=False; subsequent N-1 rebuilds emit cache_hit=True.

    AC-13 (SK-PRD-02 §7) cache_hit-span clause.  Overlaps intentionally with
    test_sandbox_pool.py:test_span_get_cache_hit (AC-8): that test exercises
    the pool in isolation; this test crosses the build_agent boundary that the
    unit test does not cover.
    """
    import app.adk.agents.agent_factory.builder as b

    pool, _sentinel, _call_count = _make_pool_with_stub()
    config = _make_config()
    recorded, patch_target = _make_span_recorder()

    initial_global_size = len(b._DEFAULT_SANDBOX_POOL._pool)

    with patch(_SPAN_PATH, patch_target):
        for _ in range(_N_REBUILDS):
            _build_with_pool(config, account_id="acc_x", name="spec_a", pool=pool)

    get_spans = [(n, a) for n, a in recorded if n == "sandbox_pool.get"]

    # Sanity: len==0 means the patch target drifted — fail loudly before the
    # per-span checks so the failure message is actionable.
    assert len(get_spans) == _N_REBUILDS, (
        f"Expected {_N_REBUILDS} sandbox_pool.get spans; got {len(get_spans)}. "
        f"Verify _SPAN_PATH={_SPAN_PATH!r} is still the correct patch target."
    )

    _name_0, attrs_0 = get_spans[0]
    assert attrs_0["cache_hit"] is False, "First rebuild must be a cache miss"
    assert attrs_0["account_id"] == "acc_x"
    assert attrs_0["config_id"] == "spec_a"
    assert attrs_0["pool_size_after"] == 1

    for i, (_n, attrs) in enumerate(get_spans[1:], start=1):
        assert attrs["cache_hit"] is True, (
            f"Rebuild {i} should be a cache hit but got cache_hit={attrs['cache_hit']}"
        )
        assert attrs["pool_size_after"] == 1

    # Guard: module-global pool is untouched.
    assert len(b._DEFAULT_SANDBOX_POOL._pool) == initial_global_size


# ---------------------------------------------------------------------------
# Test 3 — Integrity guard: distinct config_ids each trigger their own
#           _construct and yield different executor instances.
# ---------------------------------------------------------------------------


def test_different_config_ids_construct_independently() -> None:
    """Two config_ids → two _construct invocations → two distinct executors.

    Integrity check: if _construct were broken into a single global (ignoring
    the key), test 1's \"_construct once\" assertion would still pass while the
    pool was semantically wrong.  This test makes the single-construct assertion
    non-vacuous.
    """
    import app.adk.agents.agent_factory.builder as b

    pool, executors_by_key, call_count = _make_pool_with_per_key_stub()
    config_a = _make_config()
    config_b = _make_config()

    initial_global_size = len(b._DEFAULT_SANDBOX_POOL._pool)

    agents_a = [
        _build_with_pool(config_a, account_id="acc_y", name="spec_a", pool=pool)
        for _ in range(5)
    ]
    agents_b = [
        _build_with_pool(config_b, account_id="acc_y", name="spec_b", pool=pool)
        for _ in range(5)
    ]

    assert call_count[0] == 2, (
        f"_construct should be called once per distinct (account_id, config_id) key; "
        f"got {call_count[0]}"
    )

    executor_a = executors_by_key[("acc_y", "spec_a")]
    executor_b = executors_by_key[("acc_y", "spec_b")]
    assert executor_a is not executor_b, (
        "Different config_ids must yield different executor instances — "
        "pool is keyed by (account_id, config_id)"
    )
    assert all(a.code_executor is executor_a for a in agents_a), (
        "All spec_a agents must share the spec_a executor"
    )
    assert all(a.code_executor is executor_b for a in agents_b), (
        "All spec_b agents must share the spec_b executor"
    )

    # Guard: module-global pool is untouched.
    assert len(b._DEFAULT_SANDBOX_POOL._pool) == initial_global_size
