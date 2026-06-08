# AH-PRD-05 — Multi-Step Workflow Orchestration (Supervisor Model)

**Status:** Ready (spec) — implementation requires ADK 2.0 (Foundation PRD [AH-PRD-13](./AH-PRD-13-adk2-foundation.md))
**Owner team:** Core AI / Agent Platform
**Blocked by:** [AH-PRD-01](./AH-PRD-01-review-loop-framework.md) (`build_review_pipeline()`), [AH-PRD-02](./AH-PRD-02-agent-factory.md) (agent factory), [AH-PRD-03](./AH-PRD-03-google-analytics-specialist.md) (first specialist); the **ADK 2.0 Foundation PRD ([AH-PRD-13](./AH-PRD-13-adk2-foundation.md))** (primary gate — the `google-adk` 1.34.1 → 2.0.0 unpin + breaking-change migration lives there). [AH-PRD-04](./AH-PRD-04-data-visualization.md) (artifact threading — soft; artifact-threading scope in §2 ships when AH-PRD-04 is available but is not the primary implementation gate)
**Parallel with:** Knowledge-Graph (KG-PRD-04 / KG-PRD-05), Skills SK-PRDs, Performance SE-PRD-05 / PE-PRDs
**Blocks:** Any future R3+ feature requiring multi-specialist synthesis or staged execution with user approval
**Estimated effort:** TBD — implementation follows the ADK 2.0 Foundation PRD ([AH-PRD-13](./AH-PRD-13-adk2-foundation.md))

> **This PRD is the supervisor-orchestration implementation spec** (rewritten AH-97, 2026-06-01). The prior re-scoping banner ("architecture-refresh, do not implement as written") is removed — the ADK 2.0 supervisor-orchestration model is now **GO-confirmed** (AH-99 live validation) and this document is the canonical target architecture. Decision: [DESIGN-REVIEW-LOG Review 44](../../../DESIGN-REVIEW-LOG.md#review-44--ah-97-supervisor-orchestration-adoption-adk-20).
>
> **HARD RULE — do NOT implement the `execute_workflow()` / `invoke_pipeline()` inner-Runner shape on ADK 1.x.** AH-75 (see [AH-PRD-09](./AH-PRD-09-per-turn-dispatch.md) §4.6) proved that any inner-Runner / `AgentTool` call-and-return path silently discards inner sub-agent events, which **breaks the Billing token meter, Chat status tracking, MER-E Weave traces, the review loop, and UI streaming**. The `execute_workflow` / `invoke_pipeline` pattern is preserved below only as a named anti-pattern for documentation purposes.

---

## 1. Context

KEN-E's post-AH-75 dispatch model (`transfer_to_agent`) covers the bulk of marketing-analysis questions: root agent picks one specialist, dispatches once, gets an approved draft. That covers simple single-specialist queries ("Show me traffic trends for the past week") but breaks down for tasks that **inherently span multiple specialists or phases**. The motivating example — "Increase budgets for Meta Ads campaigns that result in the most engaged website visitors" — needs (a) parallel data-gathering across two specialists (GA engagement + Meta Ads spend), (b) synthesis into an optimisation plan, (c) **explicit user approval** before any spend changes, then (d) execution in Meta Ads. There is no way to express that with single-tool-call dispatch.

**Why `transfer_to_agent` alone cannot solve this.** `transfer_to_agent` hands the turn over and does not return. It is one-way by design — the perfect primitive for single-specialist delegation, but it prevents the parent from post-processing results, fanning out to a second specialist, or synthesizing across parallel branches in the same user turn.

**The ADK 2.0 supervisor model resolves the trilemma** (AH-99 GO-confirmed, 2026-06-01). ADK 2.0 introduces:
- **`LlmAgent(mode='task')`** — a specialist that runs, completes, and returns control to the parent coordinator. The parent stays in the loop.
- **`ctx.run_node()` + `asyncio.gather`** — dynamic-graph fan-out allowing the coordinator to run multiple task specialists in parallel and collect all results before synthesizing.
- **Outer-stream event propagation is native — at the task-mode specialist boundary.** AH-99 probe-1 and probe-4 confirmed that task-mode `usage_metadata` reaches the outer `Runner.run_async` event stream without a custom bridge — Billing, Chat, MER-E, and UI streaming parity contracts are preserved for the per-task delegation itself. **Caveat (AH-121 re-plan):** a specialist's *built-in-tool leaves* (`google_search` grounding, `numerical_analyst` code-execution) must stay `AgentTool`-isolated (§2 out-of-scope), and `AgentTool.run_async` still drops their inner `usage_metadata` / events (GitHub `#3984`). Those tokens are **not** native — they are recovered by AH-PRD-15's leaf `after_model_callback` off-state sink and folded into the turn delta; their inner grounded-search / code-exec spans are an accepted trace gap.

This PRD lands the **supervisor-orchestration primitive**: a `LlmAgent(mode='chat')` coordinator that decomposes the user message into a TODO ledger, delegates per-task to `mode='task'` specialist leaves, post-processes, fans out via `ctx.run_node`, and returns a synthesized response in one user turn. Each per-task delegation is optionally wrapped in the AH-PRD-01 review `LoopAgent`. User approval for spend-changing tasks is handled by the coordinator's conversational return — no ADK `pause_invocation` infrastructure required.

After this PRD's implementation, KEN-E can express the multi-platform optimisation pattern end-to-end, and the harness has a complete orchestration story for both single-specialist-per-turn and multi-task supervisor-orchestrated turns.

> **Layer boundary.** In-session orchestration (this PRD) is not the same as cross-session scheduled work ([Project Tasks — `TaskOrchestrator`](../../project-tasks/README.md)). The supervisor's TODO ledger (in `session.state`) borrows the DAG + assignee concepts conceptually but does NOT route through `TaskOrchestrator`. In-session tasks are ephemeral; cross-session project tasks persist in Firestore.

## 2. Scope

### In scope
- **`LlmAgent(mode='chat')` coordinator** — the root agent that controls the conversation, decomposes user messages into a TODO ledger, drives per-task delegation, and synthesizes results.
- **`LlmAgent(mode='task')` specialist leaves** — specialists constructed with `mode='task'` so the coordinator regains control after each task completes. Each specialist uses its configured `McpToolset` + function tools as today (<=30-tool cap, ToolRegistry-assembled).
- **`ctx.run_node()` + `asyncio.gather` fan-out** — coordinator invokes multiple task branches in parallel for tasks whose `depends_on` sets are satisfied; results collected before synthesis.
- **Review `LoopAgent` leaves** — `build_review_pipeline()` from AH-PRD-01 wraps each per-task specialist when `TodoItem.criteria` is non-empty. `LoopAgent` is deprecated in ADK 2.0 but functional; migration to `Workflow(graph=...)` is a deferred long-term item.
- **TODO ledger in `session.state`** — coordinator writes a `todo_lists` entry with the widened `TodoItem` schema (§4.1) before delegation; updates status as tasks complete.
- **Approval-via-conversation-turns** — coordinator returns intermediate results when it reaches an approval-required task; the next user turn with "approved" resumes from the pending task. No ADK `pause_invocation` infrastructure; entirely on `tool_context.state["pending_supervisor_tasks"]`.
- **Artifact threading** — follows the AH-PRD-04 convention: `create_visualization()` appends to `response_artifacts` (the turn-level key the chat endpoint drains into `ChatResponse.artifacts`, then clears); review-loop-scoped artifacts use AH-PRD-04's `<output_key_prefix>_artifacts` form (prefix = the task's `result_key`). Each artifact is persisted through the shipped `register_artifact` provenance path (GCS + `ChatArtifactIndex`). Gated on AH-PRD-04.
- Unit tests + integration tests (port AH-99 probe-1 / probe-4 assertions into CI); E2E test: budget-optimisation flow with the GA specialist + a stubbed Meta Ads specialist.

### Out of scope
- **Firestore persistence of `pending_supervisor_tasks`** — session-state continuation is sufficient for v1; crash-recovery / cross-device resumption is deferred.
- **Workflow CRUD / history UI** — no Workflows-page UI for supervisor tasks. Multi-task orchestration is coordinator-decomposed at runtime, not user-authored. (User-authored multi-step is the **Project Tasks** + **Automations** story.)
- **Cross-session workflow state** — workflows live within a single session. Anything spanning sessions belongs to Project Tasks.
- **Task-mode nodes inside a static `Workflow(graph=...)`** — GitHub `#3984` is still OPEN; this topology is unvalidated. Do not use it.
- **Parallel-step partial failure beyond returning partial results** — failed branches write an error sentinel to their `result_key`; the coordinator decides how to handle missing data. No automatic retry in this PRD.
- **Migration of `LoopAgent` to `Workflow(graph=...)`** — deferred long-term follow-on; `LoopAgent` remains functional in ADK 2.0.
- **AgentTool isolation of built-in-tool leaves** — `source="agent"` tools (incl. `agent.google_search` grounding and `numerical_analyst` code-execution, AH-98/AH-100) — owned by **[AH-PRD-15](./AH-PRD-15-agenttool-migration-cutover.md)** (a hard prerequisite for shipping the supervisor model + the prod cutover). **Re-planned (AH-121, 2026-06-07):** these leaves wrap a built-in tool that Gemini forbids alongside any function declaration, and every in-hierarchy sub-agent mode injects exactly such a sibling (`mode='task'` → `FinishTaskTool`; `mode='chat'` → `transfer_to_agent`) — so they **cannot** be task-mode sub-agents and must stay isolated `AgentTool`s. AH-PRD-15 keeps them as `AgentTool`s and recovers the `#3984`-dropped `usage_metadata` via a leaf `after_model_callback` off-state sink. The coordinator dispatches *whole specialists* via its task-mode primitive (valid — a specialist carries a function-declaration roster, not a lone built-in tool); the built-in-tool leaves remain `AgentTool`-isolated *inside* a specialist. AH-100's per-turn `root.tools` mechanism is re-validated under 2.0 by [AH-PRD-13](./AH-PRD-13-adk2-foundation.md) §5.3.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[AH-PRD-01](./AH-PRD-01-review-loop-framework.md)** | `build_review_pipeline()` is the per-task review wrapping primitive — called by the coordinator when `TodoItem.criteria` is non-empty. | This component |
| **[AH-PRD-02](./AH-PRD-02-agent-factory.md)** | `specialist_runtime.resolve_agent()` constructs `mode='task'` specialists per turn; `McpToolsetPool` reuses MCP connections across per-task rebuilds. AH-PRD-02 §5.4 Pitfall #3 is now "Realized" — task mode is the predicted ADK 2.0 primitive. | This component |
| **[AH-PRD-03](./AH-PRD-03-google-analytics-specialist.md)** | First concrete specialist for E2E coverage. | This component |
| **[AH-PRD-04](./AH-PRD-04-data-visualization.md)** | Artifact convention: `create_visualization()` appends to `response_artifacts` (drained into `ChatResponse.artifacts` by the chat endpoint, then cleared); review-loop-scoped artifacts use `<output_key_prefix>_artifacts` (prefix = the task's `result_key`). Persistence uses the shipped `register_artifact` provenance path (GCS + `ChatArtifactIndex`). Artifact threading ships when AH-PRD-04 is available (soft dependency). | This component |
| **[ADK 2.0 Foundation (AH-PRD-13)](./AH-PRD-13-adk2-foundation.md)** | `LlmAgent(mode='task')` and `ctx.run_node()` are ADK 2.0 primitives. Implementation is gated on the `google-adk` 1.34.1 -> 2.0.0 unpin + breaking-change migration owned by AH-PRD-13 (the primary gate; supersedes the now-discharged 1.27.5 → 1.34.1 bump). | AH-PRD-13 |
| **[AH-PRD-09 §4.6](./AH-PRD-09-per-turn-dispatch.md#46-dispatch-surface--ah-75-approach-1)** | Documents the AH-75 inner-Runner anti-pattern (the exact defect the `execute_workflow` / `invoke_pipeline` shape reintroduces). The supervisor model layers on top of AH-PRD-09, not in place of it. | This component |
| **[AH-PRD-15](./AH-PRD-15-agenttool-migration-cutover.md)** (AgentTool isolation + leaf billing) | **Hard prerequisite — re-planned (AH-121).** `source="agent"` built-in-tool leaves (`agent.google_search`, `numerical_analyst`) **stay isolated `AgentTool`s** — they cannot be task-mode sub-agents (the injected `FinishTaskTool` / `transfer_to_agent` sibling triggers Gemini `400 "Multiple tools must all be search tools"`). AH-PRD-15 recovers the `#3984`-dropped `usage_metadata` via a leaf `after_model_callback` off-state sink (keyed by outer `invocation_id`), re-validates parallel-search additive billing under `asyncio.gather`, and owns the prod-cutover gate. The supervisor path therefore *does* construct these two sanctioned `AgentTool`s — and no others. | AH-PRD-15 |
| W&B Weave tracing | Every per-task delegation + fan-out emits spans per `docs/trace-structure-spec.md` + `AH-PRD-05-trace-contract-diff.md`. MER-E must update extractors against the new fixture before any implementation PR merges. | `AH-PRD-05-trace-contract-diff.md` |

## 4. Data Contract

No new Firestore collections. All supervisor state lives in ADK `session.state`.

### 4.1 `TodoItem` schema (widened for supervisor-orchestration)

```python
from typing import Literal
from pydantic import BaseModel

class TodoItem(BaseModel):
    # Existing fields (unchanged — backward-compatible)
    item_id: str
    title: str
    status: Literal[
        "pending", "dispatched", "awaiting_review", "completed", "failed"
    ] = "pending"  # Widened from binary to 5-state enum

    # New supervisor-orchestration ledger fields
    assignee: str | None = None           # specialist doc_id (e.g., "google_analytics_specialist")
    query: str | None = None              # task query passed to the specialist
    criteria: str | None = None           # acceptance criteria for the LoopAgent review wrapper
    depends_on: list[str] = []            # upstream item_ids that must complete first
    result_key: str | None = None         # session-state key where the specialist writes its output
```

The existing `set_todo_list` / `update_todo_list` tool surface is unchanged from the user's perspective. The supervisor coordinator (not the user) writes the new fields.

### 4.2 Session-state keys

| Key | Shape | Written by | Read by | Lifetime |
|-----|-------|-----------|---------|----------|
| `todo_lists` | `dict[str, list[TodoItem]]` | Coordinator + `set_todo_list` / `update_todo_list` tools | Chat UI (read-only) | Per-session |
| `{result_key}` | `str` (output of the task specialist) | Task specialist (via `output_key`) | Coordinator (synthesizer) | Per-turn |
| `response_artifacts` | `list[Artifact]` | Task specialist via `create_visualization()` (AH-PRD-04) | Chat endpoint -> `ChatResponse.artifacts` (then cleared) | Per-turn |
| `<result_key>_artifacts` | `list[Artifact]` | Task specialist inside its review loop (AH-PRD-04 `<prefix>_artifacts`, prefix = `result_key`) | Reviewer via `{<result_key>_artifacts?}` template | Per pipeline run |
| `pending_supervisor_tasks` | `{remaining: list[TodoItem], completed_results: dict}` | Coordinator when approval checkpoint hit | Coordinator on next turn (continuation); cleared on completion | Spans turns within a session |

### 4.3 Parallel fan-out shape (`ctx.run_node`)

```python
# Conceptual shape — implementation uses ADK 2.0 ctx.run_node API
import asyncio

async def fan_out(coordinator_context, tasks: list[TodoItem]) -> dict[str, str]:
    """Fan out independent tasks in parallel; return per-task results."""
    results = await asyncio.gather(*[
        coordinator_context.run_node(
            specialist_agent,           # mode='task' specialist
            query=task.query,
            output_key=task.result_key,
        )
        for task in tasks
    ])
    return {task.item_id: result for task, result in zip(tasks, results)}
```

This is the **recommended** fan-out shape for *specialists*. `AgentTool.run_async` is NOT used to dispatch specialists — it discards inner sub-agent events (the AH-75 / `#3984` defect). **Exception (AH-121 re-plan):** a specialist may *internally* carry `AgentTool`-isolated built-in-tool leaves (`google_search`, `numerical_analyst`) — those are the only sanctioned `AgentTool`s, and their dropped `usage_metadata` is recovered by AH-PRD-15's leaf-callback off-state sink. The specialist consumes the leaf's returned text inline (as a tool result), so nothing threads through the deep-copied child session state across that boundary — the specialist's own `output_key` → `result_key` write is unaffected.

## 5. Implementation Outline

### 5.1 File inventory

| Action | File |
|--------|------|
| Modify | `app/adk/agents/agent_factory/builder.py` — construct `LlmAgent(mode='task')` for specialists when a supervisor turn is active |
| Modify | `app/adk/agents/agent_factory/specialist_runtime.py` — `resolve_agent()` accepts an optional `mode` parameter (`'chat'` for the coordinator, `'task'` for leaf specialists) |
| Create | `app/adk/agents/orchestration/supervisor.py` — coordinator decomposition logic: TODO-ledger construction, per-task delegation, `ctx.run_node` fan-out, continuation on approval checkpoint |
| Modify | `app/adk/agents/agent_factory/hierarchy.py` — root agent now optionally wraps as a `mode='chat'` coordinator when a multi-task decomposition is requested |
| Modify | `app/adk/tools/function_tools/todo_tools.py` — widen `TodoItem` schema per §4.1 |
| Modify | `api/src/kene_api/models/chat.py` — update `TodoItem` model for the new fields |
| Modify | `app/adk/agents/utils/review_pipeline.py` — minor: ensure `build_review_pipeline()` works with `mode='task'` specialist leaves (the pipeline's structure is unchanged; `mode` is a constructor argument, not a LoopAgent concern) |
| Create | `app/adk/agents/orchestration/tests/test_supervisor.py` — unit tests |
| Create | `app/adk/agents/tests/test_supervisor_e2e.py` — E2E tests (`@pytest.mark.llm`) |
| Create | `docs/design/components/agentic-harness/projects/AH-PRD-05-trace-contract-diff.md` — MER-E trace contract diff (authored in AH-97) |

### 5.2 Coordinator dispatch pattern

The coordinator (`mode='chat'`) decomposes the user request into a TODO ledger when it determines a multi-specialist, multi-step response is needed. Single-specialist queries continue to dispatch via `transfer_to_agent` as today.

**Decision logic (not rigid — LLM-driven):**
- One specialist, one query -> `transfer_to_agent` (existing R1 path, unchanged)
- Multiple specialists or phases -> Coordinator builds TODO ledger -> fan-out + synthesis

**Per-task delegation sequence:**
1. Coordinator resolves the specialist for each ready task (per `depends_on` DAG).
2. For each ready task: `specialist_runtime.resolve_agent(config, mode='task')` returns a `mode='task'` specialist. **`_TaskAgentTool` injection trap:** ADK only injects `_TaskAgentTool` (the `request_task_<name>` delegation marker) inside `LlmAgent.model_post_init`. Because specialists are resolved per-turn and attached to the coordinator **after** construction, `model_post_init` has already run — the tool is missing from `coordinator.tools` and delegation silently no-ops (the AH-117 / AH-PRD-15 prod-incident pattern). **Fix:** always use `attach_task_subagent(coordinator, specialist)` to attach per-turn task-mode specialists — it injects `_TaskAgentTool` by hand. Never use `coordinator.sub_agents.append(specialist)` directly. See `mcp-architecture.md` learning #6 for the full rationale. The coordinator delegates via `request_task_<name>`; the specialist runs to `complete_task`, at which point ADK returns control to the coordinator (the call-and-return primitive AH-99 validated and AH-135 verified with a stub-model-through-real-Runner integration test).
3. Independent tasks: `ctx.run_node()` + `asyncio.gather` for parallel fan-out.
4. Dependent tasks: delegated sequentially after their upstream tasks complete.
5. Synthesis task (if present): `mode='task'` specialist with `include_contents='none'`; upstream `{result_key}` values injected via template.
6. Coordinator assembles the final response from per-task results.

### 5.3 Approval-checkpoint continuation

When the coordinator reaches a task that is approval-gated (identified by the coordinator's own reasoning — e.g., the task involves irreversible spend changes, indicated via `TodoItem.criteria` containing the string `"requires_approval"` or by instruction convention):
1. Coordinator saves `pending_supervisor_tasks` to `session.state` (remaining tasks + completed results collected so far).
2. Returns intermediate results to the user with a clear approval request, summarizing what will happen if approved.
3. On the next user turn, if `pending_supervisor_tasks` is set and the user's message indicates approval, the coordinator resumes from the pending task list.
4. On completion (whether approved, cancelled, or failed), coordinator clears `pending_supervisor_tasks`.

## 6. API Contract

No new HTTP endpoints. The coordinator uses ADK-native delegation primitives — no root-level function tool (`execute_workflow` is explicitly NOT added).

The `set_todo_list` / `update_todo_list` tools (AH-PRD-01 / Chat) remain unchanged in their user-visible surface. The coordinator writes to them using the widened schema fields.

The existing chat endpoint (`POST /api/v1/accounts/{account_id}/chat`) sees no shape change: the `response_artifacts` -> `ChatResponse.artifacts` drain (AH-PRD-04) is unchanged; the supervisor model adds no new artifact surface.

The TODO status-detail surface reuses CH-PRD-05 (the session status view) — no new API surface is introduced by the supervisor model.

## 7. Acceptance Criteria

1. **Single-specialist path unaffected.** Existing AH-PRD-03 GA specialist E2E tests pass; simple queries still dispatch via `transfer_to_agent` with no supervisor machinery activated.
2. **Coordinator decomposes multi-task requests.** Given "Increase budgets for best-performing Meta Ads campaigns," the coordinator builds a TODO ledger (at minimum: GA engagement task + Meta Ads spend task + synthesis task + approval-required budget-change task) before delegating.
3. **Task-mode specialist call-and-return.** After delegating to a `mode='task'` GA specialist, the coordinator regains control and can delegate to the next specialist in the same turn.
4. **Fan-out with `ctx.run_node`.** Two independent tasks (GA + Meta Ads) run in parallel; both results are present in session state before the synthesis task begins.
5. **Billing/Chat/MER-E parity — task-mode (from AH-99 probe-1 + probe-4).** Per-task specialist tokens appear in `SessionTurnAccumulator` aggregates and `extract_billable_tokens` totals, identical to the `transfer_to_agent` baseline from a parity-test fixture. **Merge blocker for the first implementation PR.**
6. **Review-loop integration.** Given `TodoItem.criteria` non-empty, `build_review_pipeline()` wraps the task specialist; reviewer approves/rejects as today. `LoopAgent` functional under ADK 2.0 (AH-99 probe-7 confirmed).
7. **Approval checkpoint.** Coordinator returns intermediate results when it reaches an approval-required task; `pending_supervisor_tasks` set in session state; next-turn continuation works.
8. **Artifact threading.** A task specialist that calls `create_visualization()` appends to `response_artifacts` (per AH-PRD-04); the chat endpoint drains it into `ChatResponse.artifacts` and clears the key. (Gated on AH-PRD-04.)
9. **AgentTool confined to the two sanctioned isolation leaves (re-planned, AH-121).** [AH-PRD-15](./AH-PRD-15-agenttool-migration-cutover.md) is complete: no `AgentTool` is constructed in the supervisor path **except** the two isolation leaves (`google_search`, `numerical_analyst`), each carrying the `capture_agent_tool_usage` `after_model_callback` and the `isolation-required` marker. Their leaf `usage_metadata` is folded into the turn delta and `extract_billable_tokens` counts it with no double-count (verified on both root and specialist assignment). A live-Gemini staging smoke (AH-PRD-15 AC #7) has passed for any supervisor turn that dispatches a built-in-tool-carrying specialist. Enforced by `check_no_agent_tool_in_chat_tree.py` (allow-list + marker + billing-callback test). (Prerequisite verified here, not implemented here.)
10. **Weave traces.** Full E2E run produces trace with: coordinator span -> per-task delegation spans (with `task_id`, `assignee`) -> (optional) fan-out span -> (optional) LoopAgent review iterations. MER-E has signed off on extractor readiness per `AH-PRD-05-trace-contract-diff.md`. **Merge blocker for the first implementation PR.**

## 8. Test Plan

### Unit (`test_supervisor.py`)
- TODO-ledger construction: given a multi-task query, coordinator produces a `list[TodoItem]` with correct `assignee`, `query`, `criteria`, `depends_on` fields.
- Dependency-level computation: known DAG -> expected level partition; cyclic input raises.
- Fan-out: two independent tasks -> `ctx.run_node` called twice; both results in state.
- Approval checkpoint: sets `pending_supervisor_tasks`; continuation clears it on completion.
- Partial failure: one branch fails -> error sentinel in `result_key`; coordinator proceeds.

### Integration (Firestore emulator + factory)
- **`_TaskAgentTool` injection guard (AH-135 amended AC, merge blocker):** `TestTaskModePerTurnDispatch` in `test_specialist_runtime.py` — coordinator built WITHOUT sub_agents, specialist attached post-construction via `attach_task_subagent`, verifies `request_task_<name>` is in `coordinator.tools` and that the coordinator actually emits the delegation `FunctionCall` through a stub-model-through-real-`Runner` run with billing assertion. Verifies that construct-time-only tests cannot mask the per-turn injection gap.
- Port AH-99 probe-1 assertion: task-mode specialist token counts reach `SessionTurnAccumulator` correctly (parity test — merge blocker).
- Port AH-99 probe-4 assertion: `ctx.run_node` fan-out events reach outer stream with `usage_metadata` (parity test — merge blocker).
- Single-specialist path unaffected: existing AH-PRD-03 integration tests pass unchanged.
- **Manual `_TaskAgentTool` injection (AH-117 guard):** a coordinator with a **per-turn-resolved** `mode='task'` specialist exposes `request_task_<name>` to the model and actually dispatches — asserted via a **stub-model-through-a-real-`Runner`** run, NOT a construct-time check. Guards the silent-no-op trap (§5.2 step 2).
- **Compound fan-out billing (AgentTool-isolated leaves):** parallel specialists fanned out via `ctx.run_node` + `asyncio.gather`, each internally invoking an isolated `AgentTool` leaf → all leaf `usage_metadata` accumulate **additively** in the off-state sink keyed by the single outer `invocation_id` (no clobber across `gather`-copied contexts). Extends AH-PRD-15 AC #3 to the supervisor fan-out level.

### E2E (`test_supervisor_e2e.py`, `@pytest.mark.llm`)
- Budget-optimisation flow: GA specialist + stubbed Meta Ads specialist -> approval gate -> approval continuation -> all result keys populated.
- Artifact threading: specialist calls `create_visualization()` -> `ChatResponse.artifacts` populated.
- Weave trace verification: expected hierarchy per `AH-PRD-05-trace-contract-diff.md`.

### Mandatory live-Gemini staging smoke (merge blocker — mock-LLM tests cannot catch this)
The tool-composition `400` is a **server-side** error that only surfaces on a real Gemini call; mock-LLM suites structurally cannot see it (the AH-121 prod lesson — every AC #1–#6 suite passed while the design was broken). Therefore, **before any prod cutover**, any supervisor turn that dispatches a built-in-tool-carrying specialist (e.g. the GA specialist, which carries the isolated `google_search` / `numerical_analyst` leaves) must run a **real grounded turn against the staging engine** asserting no `error_code` and the leaf tokens reaching the meter. This rides on AH-PRD-15's `smoke_google_search_live.py` gate; the supervisor adds the multi-task dispatch path on top of it.

## 9. Risks & Open Questions

| Risk | Mitigation |
|------|------------|
| **`LoopAgent` deprecation in ADK 2.0** (functional, not removed) | `LoopAgent` review loops continue to work in ADK 2.0; future migration to `Workflow(graph=...)` is a deferred long-term item. AC #6 verifies it works; `LoopAgent` is explicitly NOT a blocking concern for this PRD. |
| **GitHub `#3984` still OPEN** (task-mode inside static `Workflow` graphs unvalidated) | The validated path is `mode='task'` under a `mode='chat'` coordinator, NOT task-mode nodes inside a static `Workflow` graph. This PRD uses only the validated topology. Do not use `Workflow(graph=...)` until `#3984` closes. |
| **`AgentTool.run_async` for built-in-tool leaves (AH-98/AH-100)** | Built-in `google_search` / `numerical_analyst` leaves **must** stay `AgentTool`-isolated (they cannot be task-mode — Gemini 400), and `AgentTool.run_async` drops their inner `usage_metadata` / events (`#3984`). Owned + mitigated by **[AH-PRD-15](./AH-PRD-15-agenttool-migration-cutover.md)** (re-planned AH-121): a leaf `after_model_callback` off-state sink recovers the tokens; inner spans are an accepted trace gap. Hard prerequisite for shipping the supervisor + the prod cutover. |
| **Per-turn task-mode dispatch silently no-ops (AH-117 pattern — captured 2026-06-07)** | ADK injects `_TaskAgentTool` only in `model_post_init`. Per-turn specialists are resolved AFTER construction — the coordinator never sees `request_task_<name>` if the tool is not injected by hand. Mitigated by: (a) using `attach_task_subagent(coordinator, specialist)` for every per-turn task-mode attachment (never raw `sub_agents.append`); (b) `_reconcile` in `sub_agent_attacher.py` injects/removes `_TaskAgentTool` for task-mode sub-agents added/dropped post-construction; (c) `TestTaskModePerTurnDispatch` (stub-model-through-real-Runner) fails if the injection is missing — construct-time-only tests cannot catch this. See `mcp-architecture.md` learning #6. |
| **Latency** | Per-task delegation adds round-trips. Fan-out (`ctx.run_node` + `asyncio.gather`) caps wall-clock at the slowest branch. Review loops add ~3-5 s each (unchanged from AH-PRD-01). Surface p95 via Weave. |
| **Synthesizer bracket-placeholder failure mode** | Synthesizer instructions must frame template-injected data as "completed research" (not templates). Integration test asserts synthesizer output references specific values from upstream `result_key` contents. |
| **Coordinator generates an invalid TODO ledger** (unknown specialist, cyclic deps, missing approval gate on write-operations) | Coordinator validates: unknown specialist -> error string; cyclic deps -> caught in dependency-level computation; missing approval gate is an instruction-level concern — mitigated by worked examples in the coordinator instruction. Invalid input does not raise — returns an error string the coordinator reads. |
| **`pending_supervisor_tasks` leak** | Coordinator clears the key at the start of every turn and at workflow completion. Restart test confirms prior pending state is overwritten on a fresh request. |

### Open Questions
- **Q:** Should the coordinator carry any domain tools (e.g., `create_visualization`)? Recommendation: no — keep the coordinator domain-tool-free; only the leaf specialists carry domain tools. Coordinator tools are limited to ledger management (`set_todo_list`, `update_todo_list`).
- **Q:** Maximum TODO-ledger size? Soft cap of 12 items (same as the old `execute_workflow` cap). Items above 12 should be expressed as a `ProjectPlan` (Project Tasks).
- **Q:** Does `ctx.run_node` require ADK 2.0.0 exactly, or will it land in a 1.x patch? Gate is the ADK 2.0 Foundation PRD ([AH-PRD-13](./AH-PRD-13-adk2-foundation.md)); do not attempt backport.

## 10. Reference

- **ADK 2.0 GO decision:** `docs/design/adk2-supervisor-orchestration-analysis.md` + `docs/spike-adk2-supervisor-orchestration-live.md` §1 (probe results)
- **Decision log:** `docs/design/DESIGN-REVIEW-LOG.md` [Review 44](../../../DESIGN-REVIEW-LOG.md#review-44--ah-97-supervisor-orchestration-adoption-adk-20)
- **Trace contract:** `docs/design/components/agentic-harness/projects/AH-PRD-05-trace-contract-diff.md`
- **Dispatch predecessor:** [AH-PRD-09 §4.6](./AH-PRD-09-per-turn-dispatch.md#46-dispatch-surface--ah-75-approach-1) (AH-75 rationale + supervisor-orchestration successor note)
- **Task Mode prediction realized:** [AH-PRD-02 §5.4](./AH-PRD-02-agent-factory.md#54-dynamic-agent-creation-why-pre-declared-specialists) Pitfall #3
- **Review loop primitive:** [AH-PRD-01](./AH-PRD-01-review-loop-framework.md)
- **Artifact convention:** [AH-PRD-04](./AH-PRD-04-data-visualization.md) §4.3
- **Project Tasks layer boundary:** [project-tasks README](../../project-tasks/README.md) §1 Layer Boundary
- **CLAUDE.md rules in scope:** PY-1, PY-2, PY-3, PY-7; C-2, C-4, C-7; T-1, T-3, T-5, T-6
