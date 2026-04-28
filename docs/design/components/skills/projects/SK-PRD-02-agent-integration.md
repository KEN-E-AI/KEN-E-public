# Sprint 2.6-B — Agent Factory: Skills & Sandbox Integration

**Status:** Blocked (requires AH-PRD-02, 2.6-0, 2.6-A)
**Owner team:** Agent Platform
**Blocked by:** [AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) (Agent Factory, forward-compat fields), 2.6-A (Skills API + loader), 2.6-0 (Sandbox spike findings)
**Parallel with:** 2.6-C
**Blocks:** 2.6-D
**Estimated effort:** 5–7 days

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

## 2. Scope

### In scope
- Extend `agent_factory.build_agent(config)` to construct and attach a `SkillToolset` when `skill_ids` is non-empty
- Extend the constructor to set `code_executor=AgentEngineSandboxCodeExecutor(sandbox_resource_name=...)` when `sandbox_code_executor_enabled=true`
- Implement `allowed-tools` restriction: per-skill allow-list that narrows which of the agent's tools are visible during that skill's invocation window
- Wire the Skills loader (`api/src/kene_api/services/skill_loader.py` from Sprint 2.6-A) into the agent factory — import and call, do not reimplement
- Tracing: add spans for `skill.list`, `skill.load`, `skill.load_resource` per the Weave spec extension below
- Unit + integration tests for the factory with mixed skill/code-executor configs
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
- **Sprint 2.6-A:** Skills API live; `api/src/kene_api/services/skill_loader.py` exports `load_skill(account_id, skill_id)` returning an ADK `Skill` object with lazy L3 resources. `account_id` is required — skills are stored under `accounts/{account_id}/skills/{skill_id}` (Shape B per [Review 15 in DESIGN-REVIEW-LOG](../../../DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1)) and GCS prefixes (`accounts/{account_id}/…`).
- **Sprint 2.6-0:** Spike findings doc at `docs/spike-agent-engine-sandbox-findings.md` with network/cost/resource answers that inform the sandbox config chosen here.
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
def _build_code_executor(
    config: AgentConfig,
) -> CodeExecutor | None:
    if not config.sandbox_code_executor_enabled:
        return None
    return AgentEngineSandboxCodeExecutor(
        sandbox_resource_name=_sandbox_resource_name_for(config),
        # Additional config (resource limits, network policy) per Sprint 2.6-0 findings
    )
```

`_sandbox_resource_name_for(config)` returns a per-account or per-agent sandbox resource name — decide based on the spike's cost findings. Default assumption: one sandbox pool per account, re-used across sessions.

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
| Modify | `app/adk/agents/agent_factory.py` — add `_build_skill_toolset`, `_build_code_executor`, wire into `build_agent` |
| Create | `app/adk/agents/skill_tool_filter.py` — `parse_allowed_tools`, `restrict_tools_for_skill`, callback wiring |
| Modify | `app/adk/tracking/` — new span helpers or decorators for the three skill spans |
| Modify | `docs/trace-structure-spec.md` — append span table entries |
| Modify | [AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) §5.2 — document `skill_ids` and `sandbox_code_executor_enabled` field behavior |
| Create | `app/adk/agents/test_agent_factory_skills.py` — unit tests |
| Create | `app/adk/agents/test_skill_tool_filter.py` — unit tests for the restriction filter |
| Create | `tests/integration/test_agent_with_skills.py` — end-to-end: factory builds → agent runs → loads skill → emits expected spans |
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
4. **Sandbox wiring:** Given `sandbox_code_executor_enabled=true`, the constructed `LlmAgent.code_executor` is an `AgentEngineSandboxCodeExecutor` instance. Given `false` or absent, `code_executor` is `None` or unchanged from pre-Sprint-9 default.
5. **Sandbox decoupled from skills:** Setting `sandbox_code_executor_enabled=true` with `skill_ids=[]` works (sandbox available without skills). Setting `skill_ids=["with_scripts"]` with `sandbox_code_executor_enabled=false` does NOT attempt to execute scripts — the scripts are present in `load_skill_resource` response but the agent has no runtime to run them. (Attach-time rejection is Sprint 2.6-D's job.)
6. **allowed-tools restriction:** Given skill X with frontmatter `allowed-tools: "Read"`, when X is the active skill, the agent's `before_tool_callback` filters the tool set to just `Read`. When X is not the active skill, all of the agent's tools are visible.
7. **allowed-tools can never expand:** Given a skill with `allowed-tools: "NonexistentTool"`, the restriction never adds `NonexistentTool` to the agent's toolset — the filtered set is empty.
8. **Tracing spans:** An end-to-end agent run that triggers `list_skills` + `load_skill` + `load_skill_resource` emits the three spans with the attributes documented in §4. MER-E ingests them without errors.
9. **AH-PRD-02 updated:** §5.2 config-to-constructor mapping documents the effect of `skill_ids` and `sandbox_code_executor_enabled` (replacing the forward-compat pass-through note).
10. **trace-structure-spec.md updated:** span table includes the three new entries.
11. **All unit + integration tests pass.** `make lint` passes.

## 8. Test plan

### Unit tests

**`test_agent_factory_skills.py`:**
- Mock `skill_loader.load_skill` to return canned `models.Skill` objects. Assert:
  - `skill_ids=["A", "B"]` → 2 skills in the returned SkillToolset; loader called twice with the same `account_id`
  - `skill_ids=[]` → no SkillToolset in tools; loader not called
  - `skill_ids=["missing"]` where loader raises → warning logged (with `account_id`), build succeeds with 0 skills
  - `build_agent` called without `account_id` → raises `TypeError` at the boundary (account_id is no longer optional)
- Mock `AgentEngineSandboxCodeExecutor` constructor. Assert `sandbox_code_executor_enabled=true` → constructor called once; `false` → not called.
- Verify independence: all 4 combinations of (skills=0|non-empty, sandbox=F|T) produce the expected agent structure.

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
| Sandbox session spin-up is slow enough to hurt first-response latency | Sprint 2.6-0 must surface this; if confirmed, pre-warm sandbox pool at agent-deploy time |
| `allowed-tools` spec uses glob syntax we don't fully support | v1 supports exact match + suffix `*` only; document in the authoring UI (Sprint 2.6-C). Full spec compliance is a v2 story. |
| Skill's `load_skill_resource` tool bypasses our auth (the LLM can request any rel_path) | `skill_loader.load_skill` returns lazy callbacks bound to the already-authenticated skill's GCS prefix; the callback validates `rel_path` against the bundle manifest (Sprint 2.6-A §5) |

### Open questions

- **Q:** Do we want `allowed-tools` to apply during the entire agent turn, or only during the specific skill-activation window? → **Default: skill-activation window.** A skill expresses "when using me, restrict tools" not "change the agent globally." Confirm with Sprint 2.6-0 findings.
- **Q:** Should sandbox be per-account or per-agent-session? → **Default: per-account pool reused across sessions**, subject to Sprint 2.6-0 cost findings. If per-session is cheap enough, switch — sessions are more isolated.

## 10. Reference

- Parent plan: [`../skills-implementation-plan.md`](../skills-implementation-plan.md) §2 (Architecture), §9 (Risks)
- Upstream project: [AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) (Agent Factory)
- Upstream spike: `docs/spike-agent-engine-sandbox-findings.md` (Sprint 2.6-0 output)
- Sibling sprint: [`SK-PRD-01-skills-backend.md`](./SK-PRD-01-skills-backend.md) — publishes `load_skill` this sprint consumes
- Tracing: [`trace-structure-spec.md`](../../../../trace-structure-spec.md)
- Design doc: [AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) §5 (factory internals + config-to-constructor mapping)
- ADK docs: [Skills](https://adk.dev/skills/), [Agent Engine Code Execution](https://adk.dev/integrations/code-exec-agent-engine/)
- CLAUDE.md rules in scope: C-1, C-2, C-4; PY-1, PY-2, PY-7; T-1, T-4, T-5, T-7, T-8
