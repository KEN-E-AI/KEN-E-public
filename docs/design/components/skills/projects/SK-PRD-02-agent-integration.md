# SK-PRD-02 — Agent Factory: Skills & Sandbox Integration

**Status:** Blocked (requires AH-PRD-02, SK-PRD-00, SK-PRD-01)
**Owner team:** Skills / Agent Platform
**Blocked by:** [AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) (Agent Factory, forward-compat fields), [SK-PRD-01](./SK-PRD-01-skills-backend.md) (Skills API + loader), [SK-PRD-00](./SK-PRD-00-skills-experiment.md) (Sandbox spike findings)
**Parallel with:** SK-PRD-03
**Blocks:** SK-PRD-04; AH-PRD-09 Phase 5 default-on (SandboxPool — see §4.6)
**Estimated effort:** 6–9 days (5–7 base + 1–2 for SandboxPool added by [per-turn dispatch RFC](../../../per-turn-dispatch-rfc.md))

---

## 1. Context

[AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) delivers a config-driven agent factory that reads Firestore `agent_configs/{config_id}` documents and assembles `LlmAgent` instances. As part of AH-PRD-02's forward-compat asks, the agent config schema gains two fields:

- `skill_ids: list[str]` — references into `skills/{skill_id}` (Sprint 2.6-A)
- `sandbox_code_executor_enabled: bool` — opt-in for `AgentEngineSandboxCodeExecutor`

AH-PRD-02 ships these as *passive placeholders*: the constructor accepts them and the API round-trips them, but nothing is actually wired. This sprint **lights up the wiring**:

1. For each agent with `skill_ids != []`, hydrate a `SkillToolset` and attach it to the constructed `LlmAgent`.
2. For each agent with `sandbox_code_executor_enabled=true`, attach `code_executor=AgentEngineSandboxCodeExecutor(...)` to the constructed `LlmAgent`.
3. Enforce each attached skill's `allowed-tools` frontmatter as a **restriction filter** over the agent's existing toolset.
4. Emit W&B Weave spans for skill load and invoke events, extending the trace spec.

No new user-facing endpoints are introduced. The observable change is: an existing agent's behavior now reflects its attached skills when it runs.

**Scope addition from the [per-turn dispatch RFC](../../../per-turn-dispatch-rfc.md) (AH-PRD-09).** AH-PRD-09 makes the agent factory **resolve specialists per turn** instead of once at deploy. Under that model, every chat turn rebuilds the `LlmAgent` from the cached `MergedAgentConfig`. If `_build_code_executor` constructed a fresh `AgentEngineSandboxCodeExecutor` per rebuild, every turn would pay a sandbox cold-start — dominating latency. The fix is to **pool sandboxes** by `(account_id, config_id)` so the sandbox process outlives any single `LlmAgent` instance and is reused across rebuilds. This adds a new `SandboxPool` abstraction (§4.6) to this PRD's scope. AH-PRD-09's Phase 5 default-on is gated on `SandboxPool` shipping — without it, sandbox-attached specialists regress under the runtime resolver.

## 2. Scope

### In scope
- Extend `agent_factory.build_agent(config)` to construct and attach a `SkillToolset` when `skill_ids` is non-empty
- Extend the constructor to set `code_executor=<pooled AgentEngineSandboxCodeExecutor>` when `sandbox_code_executor_enabled=true` (sourced from `SandboxPool`, see below)
- **`SandboxPool`** at `app/adk/agents/agent_factory/sandbox_pool.py` — process-wide pool of `AgentEngineSandboxCodeExecutor` instances keyed by `(account_id, config_id)`, with LRU cap, idle TTL, and `aclose()`-on-eviction. Decouples sandbox lifecycle from `agent_cache` rebuild under [AH-PRD-09](../../../per-turn-dispatch-rfc.md)'s runtime resolver. See §4.6.
- `_build_code_executor` delegates to `SandboxPool.get_or_create(...)` rather than constructing a fresh executor per call
- Implement `allowed-tools` restriction: per-skill allow-list that narrows which of the agent's tools are visible during that skill's invocation window
- Wire the Skills loader (`api/src/kene_api/services/skill_loader.py` from SK-PRD-01) into the agent factory — import and call, do not reimplement
- Tracing: add spans for `skill.list`, `skill.load`, `skill.load_resource` per the Weave spec extension below, plus `sandbox_pool.get` / `sandbox_pool.evict` spans for pool observability
- Unit + integration tests for the factory with mixed skill/code-executor configs; concurrent-pool-access + eviction-cleanup tests for `SandboxPool`
- Update `docs/trace-structure-spec.md` with the new spans
- Update [AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) §5.2 (config-to-constructor mapping) to document the behavior of the new `skill_ids` and `sandbox_code_executor_enabled` fields

### Out of scope
- Authoring UI (Sprint 2.6-C)
- Agent builder skill-picker (Sprint 2.6-D)
- Attach-time validation of script-bearing skills onto non-sandbox agents (Sprint 2.6-D owns the `PUT agent-configs` enforcement)
- Any Firestore schema change (AH-PRD-02 already did it)
- **Skill content/prompt-injection scanning — deferred to v2.** v1 mitigates by: (a) all user-authored content is rendered to agents with a system-level wrapper noting the source is user-provided; (b) MER-E consumes the new `skill.list` / `skill.load` / `skill.load_resource` spans to score skill-triggered sessions, surfacing poisoned skills in quality metrics. A heuristic scan-on-save is the v2 design surface and is not on any v1 PRD.

## 3. Dependencies

- **[AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) (Agent Factory):** `agent_configs/{config_id}` has `skill_ids: list[str]` and `sandbox_code_executor_enabled: bool`; constructor reads them but doesn't act. Migration script populated defaults on existing docs.
- **[SK-PRD-01](./SK-PRD-01-skills-backend.md) (Skills Backend):** Skills API live; `api/src/kene_api/services/skill_loader.py` exports `load_skill(account_id, skill_id)` returning an ADK `Skill` object with lazy L3 resources. `account_id` is required — skills are stored under `accounts/{account_id}/skills/{skill_id}` (Shape B per [Review 15 in DESIGN-REVIEW-LOG](../../../DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1)) and GCS prefixes (`accounts/{account_id}/…`).
- **[SK-PRD-00](./SK-PRD-00-skills-experiment.md) (Sandbox Spike):** Spike findings doc at `docs/spike-agent-engine-sandbox-findings.md` with network / cost / resource answers that inform the sandbox config + `SandboxPool` sizing chosen here.
- **[AH-PRD-09](../../../per-turn-dispatch-rfc.md) (Per-Turn Dispatch Agent — coordination dep, downstream consumer):** AH-PRD-09's runtime resolver rebuilds `LlmAgent` instances per turn. `SandboxPool` (§4.6) must ship before AH-PRD-09 Phase 5 default-on so sandbox-attached specialists do not respawn their sandbox on every turn. The pool design mirrors AH-PRD-09's `McpToolsetPool` (LRU + idle TTL + `aclose()`-on-eviction) for operational consistency.
- **ADK:** v1.25.0+ pinned. Relevant APIs:
  - `google.adk.skills.SkillToolset` / `load_skill_from_dir` / `models.Skill`
  - `google.adk.code_executors.agent_engine_sandbox_code_executor.AgentEngineSandboxCodeExecutor`
- **Existing files to study:**
  - `app/adk/agents/agent_factory.py` (AH-PRD-02 output — `build_agent`, `build_hierarchy`)
  - `app/adk/agents/ken_e_agent.py`, `google_analytics_agent_v4.py` — reference patterns
  - `app/adk/tracking/` — Weave span decorators / helpers

## 4. Data contract

No new persisted data. Contract changes are code-level.

### Agent factory — signature extensions

```python
# app/adk/agents/agent_factory.py  (modified)

from google.adk.skills import SkillToolset
from google.adk.code_executors.agent_engine_sandbox_code_executor import (
    AgentEngineSandboxCodeExecutor,
)
from kene_api.services.skill_loader import load_skill

async def build_agent(
    config: AgentConfig,
    *,
    account_id: str,
) -> LlmAgent:
    """Assembles an LlmAgent from Firestore config.

    `account_id` is required (was optional in AH-PRD-02's forward-compat signature).
    It is forwarded to `_build_skill_toolset` so the skill loader can resolve the
    per-account Firestore collection and GCS prefix defined in SK-PRD-01.

    New behaviors (Feature 2.6):
      - If config.skill_ids is non-empty, loads each via skill_loader.load_skill
        (passing account_id) and attaches a SkillToolset to the agent's tools.
      - If config.sandbox_code_executor_enabled is True, attaches
        AgentEngineSandboxCodeExecutor as the agent's code_executor.
    """
```

### `SkillToolset` construction

```python
async def _build_skill_toolset(
    account_id: str,
    skill_ids: list[str],
) -> SkillToolset | None:
    """`account_id` is mandatory — skills are stored under
    `accounts/{account_id}/skills/{skill_id}` (Shape B subcollection) and GCS
    prefixes (`accounts/{account_id}/…`) per SK-PRD-01. The agent factory passes
    the `account_id` it already has on `build_agent`.
    """
    if not skill_ids:
        return None
    skills = []
    for sid in skill_ids:
        try:
            skills.append(await load_skill(account_id, sid))
        except SkillLoaderError as e:
            # Log and skip — a missing/archived skill should not fail the whole agent
            logger.warning(
                "skill_load_skipped",
                account_id=account_id,
                skill_id=sid,
                reason=str(e),
            )
    return SkillToolset(skills=skills) if skills else None
```

### `allowed-tools` restriction filter

Implementation pattern: the `allowed-tools` frontmatter is a space-separated string such as `"Bash(git:*) Bash(jq:*) Read"`. When a skill is invoked, a restriction filter limits which of the agent's tools are callable during that skill's execution window. Parse and enforce as follows:

```python
def parse_allowed_tools(raw: str | None) -> set[str] | None:
    """Returns None (no restriction) or a set of tool-name patterns."""
    if raw is None:
        return None
    return {tok.strip() for tok in raw.split() if tok.strip()}


def restrict_tools_for_skill(
    agent_tools: list[Tool],
    allowed: set[str] | None,
) -> list[Tool]:
    """Returns the subset of agent_tools whose names match any pattern
    in `allowed`. Patterns support glob-style suffix wildcards (e.g., Bash(git:*)).
    Returns all tools if allowed is None.

    NEVER returns a tool not already in agent_tools — `allowed-tools` can only
    restrict, never grant.
    """
```

This filter hooks into the existing `before_tool_callback` (delivered by AH-PRD-02 story 2.2-1), reading the currently-active skill from session state and applying the restriction.

### Sandbox code executor

```python
async def _build_code_executor(
    config: AgentConfig,
    *,
    account_id: str,
    sandbox_pool: SandboxPool,
) -> CodeExecutor | None:
    if not config.sandbox_code_executor_enabled:
        return None
    return await sandbox_pool.get_or_create(
        account_id=account_id,
        config_id=config.name,  # stable Firestore doc id
    )
```

The factory no longer constructs `AgentEngineSandboxCodeExecutor` directly — that's the pool's job (§4.6). `_sandbox_resource_name_for(config)` moves into `SandboxPool` as an internal detail; callers see only the pooled executor.

**Timeout failure mode (fail-closed).** If `sandbox_pool.get_or_create` exceeds `_SANDBOX_BUILD_TIMEOUT_SECONDS` (30 s), `_build_code_executor` returns `None` regardless of `code_execution_enabled` — a sandbox request is a hard requirement, not a soft preference. The agent has no code executor that turn rather than silently downgrading to `BuiltInCodeExecutor`. See [DESIGN-REVIEW-LOG Review 36](../../../DESIGN-REVIEW-LOG.md#review-36--sk-39-sandbox-build-timeout-fails-closed-no-silent-builtincodexecutor-fallback) for rationale. AC-4 documents the full contract.

### 4.6 SandboxPool

`SandboxPool` is a process-wide pool of `AgentEngineSandboxCodeExecutor` instances keyed by `(account_id, config_id)`. It exists because [AH-PRD-09](../../../per-turn-dispatch-rfc.md)'s runtime resolver rebuilds the `LlmAgent` every turn; without pooling, every turn would respawn the sandbox process, paying the cold-start cost on each chat message.

```python
# app/adk/agents/agent_factory/sandbox_pool.py (new)

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.adk.code_executors.agent_engine_sandbox_code_executor import (
        AgentEngineSandboxCodeExecutor,
    )


class SandboxPool:
    """Process-wide pool of AgentEngineSandboxCodeExecutor instances.

    Keys: (account_id, config_id). One sandbox per (account, agent) tuple.
    Eviction: LRU (cap 64 entries) + idle TTL (15 min) + 60 s background sweep.
    Cleanup: aclose() invoked before any reference is dropped.

    The pool decouples sandbox lifecycle from agent_cache reuse — a config edit
    that invalidates the cached LlmAgent does NOT force a sandbox respawn.
    """

    _MAX_ENTRIES: int = 64
    _IDLE_TTL_SECONDS: int = 900
    _SWEEP_INTERVAL_SECONDS: int = 60

    def __init__(self) -> None:
        self._pool: OrderedDict[
            tuple[str, str], tuple[AgentEngineSandboxCodeExecutor, float]
        ] = OrderedDict()
        self._stripe_locks: dict[int, asyncio.Lock] = {}
        self._sweep_task: asyncio.Task | None = None

    def _stripe(self, key: tuple[str, str]) -> asyncio.Lock:
        idx = hash(key) % 32
        return self._stripe_locks.setdefault(idx, asyncio.Lock())

    async def get_or_create(
        self,
        *,
        account_id: str,
        config_id: str,
    ) -> AgentEngineSandboxCodeExecutor:
        """Return a pooled sandbox for (account_id, config_id), constructing
        on miss. LRU-bumps the entry on hit.
        """
        key = (account_id, config_id)
        async with self._stripe(key):
            entry = self._pool.get(key)
            now = time.monotonic()
            if entry is not None:
                executor, _last_used = entry
                self._pool.move_to_end(key)
                self._pool[key] = (executor, now)
                return executor

            executor = await self._construct(account_id=account_id, config_id=config_id)
            self._pool[key] = (executor, now)
            self._pool.move_to_end(key)
            await self._evict_if_over_cap()
            return executor

    async def evict(self, key: tuple[str, str]) -> None:
        """Closes the pooled sandbox via aclose() before dropping the reference."""
        async with self._stripe(key):
            entry = self._pool.pop(key, None)
            if entry is None:
                return
            executor, _ = entry
            try:
                await executor.aclose()
            except Exception:  # noqa: BLE001 — log + continue; pool integrity wins
                logger.exception("SandboxPool eviction aclose() failed", extra={"key": key})

    async def _construct(
        self,
        *,
        account_id: str,
        config_id: str,
    ) -> AgentEngineSandboxCodeExecutor:
        """Lazy import — see _build_code_executor docstring."""
        from google.adk.code_executors.agent_engine_sandbox_code_executor import (
            AgentEngineSandboxCodeExecutor,
        )
        return AgentEngineSandboxCodeExecutor(
            sandbox_resource_name=_sandbox_resource_name(account_id, config_id),
            # Resource limits + network policy per SK-PRD-00 findings
        )

    async def _evict_if_over_cap(self) -> None:
        while len(self._pool) > self._MAX_ENTRIES:
            oldest_key, _ = next(iter(self._pool.items()))
            await self.evict(oldest_key)

    async def sweep_idle(self) -> None:
        """Closes entries idle > _IDLE_TTL_SECONDS. Runs every _SWEEP_INTERVAL_SECONDS."""
        cutoff = time.monotonic() - self._IDLE_TTL_SECONDS
        stale_keys = [k for k, (_, last) in self._pool.items() if last < cutoff]
        for k in stale_keys:
            await self.evict(k)


def _sandbox_resource_name(account_id: str, config_id: str) -> str:
    """Per (account, agent) Vertex sandbox resource name.

    v1 simplification: one persistent sandbox per (account_id, config_id). If
    observation shows over-provisioning, loosen to per-account-only (drop the
    config_id from the key) in v2.
    """
    return f"projects/{_PROJECT_ID}/locations/{_LOCATION}/sandboxes/sb_{account_id}_{config_id}"
```

**Why `(account_id, config_id)` rather than `account_id` only.** v1 picks per-agent isolation to avoid cross-agent state leakage in a shared sandbox. The trade-off: an account with N sandbox-enabled agents keeps N sandbox processes warm. If SK-PRD-00 cost findings show this is too expensive, v2 may loosen the key to `account_id`-only with explicit acceptance of cross-agent state sharing (matches AH-PRD-02's original "one sandbox pool per account" default).

**Lifecycle.** The pool is constructed once per Cloud Run instance (`SandboxPool()` singleton in `agent_factory`) and survives across all per-turn `_build_code_executor` calls. The 60 s background sweep keeps memory bounded even when LRU isn't churning. `aclose()` on eviction is mandatory — leaked sandbox processes accumulate on Cloud Run instance recycle. Mirrors AH-PRD-09's `McpToolsetPool` discipline (RFC §4.8).

**Span contract.** Two new Weave spans for pool observability:

| Span name | Attributes | When emitted |
|---|---|---|
| `sandbox_pool.get` | `account_id`, `config_id`, `cache_hit: bool`, `pool_size_after: int` | Every `get_or_create` call |
| `sandbox_pool.evict` | `account_id`, `config_id`, `reason: "lru" \| "ttl" \| "manual"`, `pool_size_after: int` | Every `evict` call |

### Weave span contract — new spans

Append to `docs/trace-structure-spec.md`:

| Span name | Parent | Attributes | When emitted |
|---|---|---|---|
| `skill.list` | agent turn | `account_id: str`, `skill_count: int`, `skill_ids: list[str]` | `SkillToolset.list_skills` tool invocation |
| `skill.load` | agent turn | `account_id: str`, `skill_id: str`, `skill_name: str`, `skill_version: int`, `instruction_bytes: int` | `SkillToolset.load_skill` tool invocation |
| `skill.load_resource` | skill.load | `account_id: str`, `skill_id: str`, `rel_path: str`, `resource_bytes: int` | `SkillToolset.load_skill_resource` tool invocation |

MER-E consumes these spans to score skill-triggered sessions.

## 5. Implementation outline

| Action | File |
|---|---|
| Modify | `app/adk/agents/agent_factory.py` — add `_build_skill_toolset`, `_build_code_executor` (now delegating to `SandboxPool`), wire into `build_agent`; thread `SandboxPool` singleton through the factory |
| Create | `app/adk/agents/agent_factory/sandbox_pool.py` — `SandboxPool` (see §4.6); per-key striped locks, LRU + idle-TTL eviction, `aclose()`-on-eviction, background sweep task |
| Create | `app/adk/agents/skill_tool_filter.py` — `parse_allowed_tools`, `restrict_tools_for_skill`, callback wiring |
| Modify | `app/adk/tracking/` — new span helpers or decorators for the three skill spans + two `sandbox_pool.*` spans |
| Modify | `docs/trace-structure-spec.md` — append span table entries (skill spans + sandbox_pool spans) |
| Modify | [AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) §5.2 — document `skill_ids` and `sandbox_code_executor_enabled` field behavior |
| Create | `app/adk/agents/test_agent_factory_skills.py` — unit tests |
| Create | `app/adk/agents/agent_factory/tests/test_sandbox_pool.py` — pool unit tests (idempotency, LRU + TTL eviction, `aclose()`, concurrent access, sweep) |
| Create | `app/adk/agents/test_skill_tool_filter.py` — unit tests for the restriction filter |
| Create | `tests/integration/test_agent_with_skills.py` — end-to-end: factory builds → agent runs → loads skill → emits expected spans |
| Create | `tests/integration/test_sandbox_pool_runtime_resolver.py` — simulate AH-PRD-09's `agent_cache` miss → verify sandbox is reused from pool (no respawn) |
| Modify | `pyproject.toml` — pin ADK version if not already pinned |

### Tool-filter callback integration

The `before_tool_callback` already exists (AH-PRD-02). Extend it to:
1. Read `ctx.state.get("active_skill_id")` — set when a `load_skill` span opens.
2. If an active skill has a parsed `allowed-tools` set, apply `restrict_tools_for_skill` to the tool registry for this turn.
3. On skill-complete or next turn without an active skill, clear the restriction.

Naive alternative (recorded as an open question in §9): have `SkillToolset`'s `load_skill` tool set the restriction directly via a tool_context side-effect. Prefer the callback approach because it keeps state management in one place.

## 6. API contract

No new HTTP endpoints. The observable contract change is:
- Deploying an agent whose config has `skill_ids=["skill_123"]` results in `list_skills`, `load_skill`, and `load_skill_resource` appearing as tools on the agent, with L1 metadata for `skill_123` visible to `list_skills`.
- Deploying an agent whose config has `sandbox_code_executor_enabled=true` results in that agent's `code_executor` being an `AgentEngineSandboxCodeExecutor` instance.

## 7. Acceptance criteria

1. **Skill wiring:** Given an agent config with `skill_ids=["A", "B"]`, when `build_agent()` runs, the resulting `LlmAgent` has a `SkillToolset` in its tools, and `list_skills` returns both A's and B's L1 metadata.
2. **Missing skill tolerance:** Given `skill_ids=["A", "archived_B"]` where B is soft-archived, `build_agent()` succeeds with only A loaded and emits a `skill_load_skipped` warning log for B.
2a. **All-skills-fail edge case:** Given `skill_ids=["archived_A", "archived_B"]` where every attached skill fails to load, `build_agent()` succeeds (does NOT raise) and:
   - emits a structured **error**-level log `skill_load_total_failure` with `account_id`, `config_id`, and the requested `skill_ids` (operators alert on this signal),
   - sets `skill_load_total_failure=true` as an attribute on the agent's `skill.list` Weave span so MER-E can score sessions as degraded,
   - constructs the agent with **no** `SkillToolset` (rather than an empty one — the LLM should not see `list_skills` returning nothing).
3. **Empty skill list:** Given `skill_ids=[]`, no `SkillToolset` is attached. The agent's tools are unchanged from a no-skills config.
4. **Sandbox wiring:** Given `sandbox_code_executor_enabled=true`, the constructed `LlmAgent.code_executor` is an `AgentEngineSandboxCodeExecutor` instance. Given `false` or absent, `code_executor` is `None` or unchanged from pre-Sprint-9 default. **Timeout path:** if pool construction exceeds `_SANDBOX_BUILD_TIMEOUT_SECONDS`, `_build_code_executor` returns `None` regardless of `code_execution_enabled` — a sandbox request is a hard requirement; the agent has no code executor that turn (no silent fallback to `BuiltInCodeExecutor`).
5. **Sandbox decoupled from skills:** Setting `sandbox_code_executor_enabled=true` with `skill_ids=[]` works (sandbox available without skills). Setting `skill_ids=["with_scripts"]` with `sandbox_code_executor_enabled=false` does NOT attempt to execute scripts — the scripts are present in `load_skill_resource` response but the agent has no runtime to run them. (Attach-time rejection is Sprint 2.6-D's job.)
6. **allowed-tools restriction:** Given skill X with frontmatter `allowed-tools: "Read"`, when X is the active skill, the agent's `before_tool_callback` filters the tool set to just `Read`. When X is not the active skill, all of the agent's tools are visible.
7. **allowed-tools can never expand:** Given a skill with `allowed-tools: "NonexistentTool"`, the restriction never adds `NonexistentTool` to the agent's toolset — the filtered set is empty.
8. **Tracing spans:** An end-to-end agent run that triggers `list_skills` + `load_skill` + `load_skill_resource` emits the three spans with the attributes documented in §4. MER-E ingests them without errors.
9. **AH-PRD-02 updated:** §5.2 config-to-constructor mapping documents the effect of `skill_ids` and `sandbox_code_executor_enabled` (replacing the forward-compat pass-through note).
10. **trace-structure-spec.md updated:** span table includes the three skill spans plus the two `sandbox_pool.*` spans.
11. **SandboxPool reuse:** Calling `_build_code_executor` twice with the same `(account_id, config_id)` returns the **same** pooled `AgentEngineSandboxCodeExecutor` instance (verified by `is` identity); subsequent calls within the idle TTL do not invoke the underlying constructor.
12. **SandboxPool eviction cleanup:** LRU and TTL eviction paths both call `executor.aclose()` before dropping the reference. Unit test stubs `aclose` and asserts it's called exactly once per eviction.
13. **AH-PRD-09 readiness:** Under a simulated runtime resolver where the `LlmAgent` is rebuilt on every turn (mirroring the `agent_cache` miss path), the sandbox is reused from the pool — `_construct` is invoked exactly once across N rebuilds for the same `(account_id, config_id)`.
14. **SandboxPool concurrent safety:** Concurrent `get_or_create` calls for the same key resolve to the same executor instance (single-flight via per-key striped locks); concurrent calls for different keys do not serialize.
15. **All unit + integration tests pass.** `make lint` passes.

## 8. Test plan

### Unit tests

**`test_agent_factory_skills.py`:**
- Mock `skill_loader.load_skill` to return canned `models.Skill` objects. Assert:
  - `skill_ids=["A", "B"]` → 2 skills in the returned SkillToolset; loader called twice with the same `account_id`
  - `skill_ids=[]` → no SkillToolset in tools; loader not called
  - `skill_ids=["missing"]` where loader raises → warning logged (with `account_id`), build succeeds with 0 skills
  - `build_agent` called without `account_id` → raises `TypeError` at the boundary (account_id is no longer optional)
- Mock `SandboxPool.get_or_create`. Assert `sandbox_code_executor_enabled=true` → pool called once with `(account_id, config_id)`; `false` → pool not called.
- Verify independence: all 4 combinations of (skills=0|non-empty, sandbox=F|T) produce the expected agent structure.

**`test_sandbox_pool.py`:**
- `get_or_create((acc, cfg))` twice → same instance returned; underlying `_construct` called once
- Different keys → separate instances; concurrent `get_or_create` for distinct keys does not serialize (timing assertion)
- Concurrent `get_or_create` for the **same** key (asyncio.gather × 10) → all return the same instance; `_construct` called exactly once (single-flight)
- LRU at cap: `_MAX_ENTRIES=4` (test override) → after the 5th distinct insert, the oldest entry is evicted and its `aclose()` is invoked
- Idle TTL: stub `time.monotonic()`, advance > `_IDLE_TTL_SECONDS`, call `sweep_idle()` → idle entries evicted with `aclose()` invoked
- `aclose()` raising during eviction → exception caught + logged; pool integrity preserved (entry still removed)
- LRU bump on hit: re-accessing the oldest entry moves it to the end; subsequent over-cap insert evicts the new second-oldest instead

**`test_skill_tool_filter.py`:**
- `parse_allowed_tools(None)` → `None`
- `parse_allowed_tools("")` → `None` (treat empty as "no restriction")
- `parse_allowed_tools("Read Bash(git:*)")` → `{"Read", "Bash(git:*)"}`
- `restrict_tools_for_skill(all_tools, None)` → `all_tools` unchanged
- `restrict_tools_for_skill([Read, Write, Edit], {"Read"})` → `[Read]`
- `restrict_tools_for_skill([Read], {"NonExistent"})` → `[]` — restriction cannot grant
- Glob match: `restrict_tools_for_skill([bash_git, bash_jq], {"Bash(git:*)"})` → `[bash_git]`

### Integration tests

**`tests/integration/test_agent_with_skills.py`:**
- Seed Firestore (emulator) with an `agent_configs` doc and a `skills/` doc. Seed GCS with the corresponding SKILL.md.
- Build the agent via `build_hierarchy(account_id=...)`.
- Invoke the agent with a prompt that should trigger skill usage ("follow the seo-checklist skill").
- Assert: `list_skills` span emitted with `skill_ids=["seo-checklist-id"]`; `load_skill` span emitted with the correct skill_id; the agent's response reflects the skill's instructions.

This integration test requires a live Gemini endpoint; mark it `@pytest.mark.llm` for conditional execution in CI.

### Load characteristics

One smoke test: agent with the 10-skill cap. Assert:
- `build_agent` completes in <500ms (GCS reads are parallelized)
- `list_skills` tool response is ≤ 2 kB (10 × ~100 tokens × 1.5 markdown overhead)

## 9. Risks & open questions

| Risk / question | Mitigation |
|---|---|
| Restriction filter state leaks across skills within a turn | Tests assert restriction clears between skill activations; callback writes an `active_skill_id` key and clears it on turn boundary |
| ADK `SkillToolset` evolves between 1.25.0 and 1.26.0 | Pin the version; write a thin wrapper that can be updated in one file when upstream changes |
| Sandbox session spin-up is slow enough to hurt first-response latency | SK-PRD-00 must surface this; `SandboxPool` (§4.6) amortizes spin-up across turns; if first-turn cold-start is still too slow, pre-warm the pool at Cloud Run startup |
| `allowed-tools` spec uses glob syntax we don't fully support | v1 supports exact match + suffix `*` only; document in the authoring UI (SK-PRD-03). Full spec compliance is a v2 story. |
| Skill's `load_skill_resource` tool bypasses our auth (the LLM can request any rel_path) | `skill_loader.load_skill` returns lazy callbacks bound to the already-authenticated skill's GCS prefix; the callback validates `rel_path` against the bundle manifest (SK-PRD-01 §5) |
| `AgentEngineSandboxCodeExecutor.aclose()` semantics under ADK 1.27+ | Verify the cleanup contract during SK-PRD-00; if `aclose()` is not exposed, fall back to the lifecycle method ADK does provide. Pool integrity test (`test_sandbox_pool.py`) asserts the cleanup hook is actually invoked. |
| `SandboxPool` cap (`_MAX_ENTRIES=64`) misjudged | Conservative starting point — most accounts have <5 sandbox-enabled agents. Observability spans (`sandbox_pool.get` / `sandbox_pool.evict`) surface saturation; tune in a follow-up if eviction rate is high. |
| Per-`(account_id, config_id)` keying over-provisions sandboxes vs. per-account-only | v1 deliberately picks per-agent isolation. If SK-PRD-00 cost findings or production observation shows over-provisioning, v2 loosens the key to `account_id`-only (matches AH-PRD-02's original "one per account" default). Documented in §4.6. |

### Open questions

- **Q:** Do we want `allowed-tools` to apply during the entire agent turn, or only during the specific skill-activation window? → **Default: skill-activation window.** A skill expresses "when using me, restrict tools" not "change the agent globally." Confirm with SK-PRD-00 findings.
- **Q:** Should sandbox be per-account or per-(account, agent)? → **Resolved: per-(account, agent) via `SandboxPool` keyed by `(account_id, config_id)`** (§4.6). Original AH-PRD-02 default was per-account; this PRD refines to per-agent for isolation while preserving the pooling benefit. Revisit per the cost trade-off above.

## 10. Reference

- Parent plan: [`../skills-implementation-plan.md`](../skills-implementation-plan.md) §2 (Architecture), §9 (Risks)
- Upstream project: [AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) (Agent Factory)
- Upstream spike: `docs/spike-agent-engine-sandbox-findings.md` (SK-PRD-00 output)
- Sibling PRD: [`SK-PRD-01-skills-backend.md`](./SK-PRD-01-skills-backend.md) — publishes `load_skill` this PRD consumes
- Downstream consumer: [Per-turn dispatch RFC / AH-PRD-09](../../../per-turn-dispatch-rfc.md) — §4.9 cross-component contracts row for Skills sandbox; §9.2 #8 design decision; Phase 5 default-on gated on `SandboxPool` shipping
- Tracing: [`trace-structure-spec.md`](../../../../trace-structure-spec.md)
- Design doc: [AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) §5 (factory internals + config-to-constructor mapping)
- ADK docs: [Skills](https://adk.dev/skills/), [Agent Engine Code Execution](https://adk.dev/integrations/code-exec-agent-engine/)
- CLAUDE.md rules in scope: C-1, C-2, C-4; PY-1, PY-2, PY-7; T-1, T-4, T-5, T-7, T-8
