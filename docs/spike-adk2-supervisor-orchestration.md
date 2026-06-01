# ADK 2.0 Supervisor-Orchestration Spike — Findings

**Status:** Complete  
**ADK versions tested:** 2.0.0, 2.1.0 (static analysis + runnable probes)  
**KEN-E baseline bumped to:** 1.34.1 (discharges SK-10 / SK-32 unpin TODO)  
**Date:** 2026-06-01  
**Spike issue:** [AH-96](https://linear.app/ken-e/issue/AH-96)  
**Probe scripts:** `docs/spike-adk2/probe-{1-7}-*.py` (runnable against ADK 2.0 venv)  
**Analysis doc:** `docs/design/adk2-supervisor-orchestration-analysis.md`

---

## 🟢 VERDICT: CONDITIONAL GO

**ADK 2.0's task-mode and dynamic-graph architecture solves the core event-propagation
problem** that [AH-75](https://linear.app/ken-e/issue/AH-75) worked around on 1.x.
Inner sub-agent events (model chunks, tool calls, `usage_metadata`) reach the outer
`Runner.run_async` stream natively — no hand-built bridge required.

**Conditions for GO:**

1. KEN-E must use `LlmAgent(mode='task')` sub-agents under an `LlmAgent(mode='chat')`
   coordinator — NOT `AgentTool` (still discards events; #3984 OPEN) and NOT as
   static `Workflow` graph nodes (prohibited in 2.0/2.1).
2. The review-loop wrapper (`LoopAgent`) cannot carry `mode='task'`; it stays as a
   plain loop container. Worker + reviewer sub-agents can be `LlmAgent` leaves.
3. Chat team must review `SessionTurnAccumulator` for compatibility with new 2.0 Event
   fields (`node_info`, `isolation_scope`). No schema migration required.
4. AH-PRD-05's `execute_workflow` must be rewritten for the 2.0 task-mode topology
   (tracked in [AH-97](https://linear.app/ken-e/issue/AH-97) on GO signal).

**Hard rule preserved:** Do NOT ship AH-PRD-05's `execute_workflow` inner-Runner
pattern on ADK 1.x. The 2.0 task-mode path is the gate.

---

## AC Evidence Table

| AC | Question | Verdict | Evidence |
|----|----------|---------|----------|
| Q1 | Do inner events reach the outer Runner stream in task-mode AND dynamic-graph? | **✅ YES** | `NodeRunner._run_node_loop` enqueues ALL events to `ic._event_queue`; `Runner._consume_event_queue` yields them all. See probe-1 + §1 below. |
| Q2 | When is task mode re-enabled inside graphs? #3984 status? | **🔴 OPEN / WORKAROUND** | Prohibited as static `Workflow` graph nodes in 2.0.0 and 2.1.0 (`_validate_no_task_mode_graph_nodes`). #3984 OPEN (no code reference in 2.0/2.1). Workaround: chat coordinator + task sub-agents. See probe-2 + §2 below. |
| Q3 | Does `asyncio.run` on worker thread preserve Weave contextvar call-stack? | **🟡 NO (limited scope)** | Contextvars NOT propagated through `asyncio.run` in thread pool. Scope limited to MCP pool checkout only — NOT main agent LLM calls. Existing issue on 1.34.1 too. See probe-3 + §3 below. |
| Q4 | `usage_metadata` location on 2.0 events; `extract_billable_tokens` compat? | **✅ COMPATIBLE** | `Event.usage_metadata` same type and fields. `extract_billable_tokens` uses duck-typing — fully compatible. Inner task token now counted (billing accuracy improvement). See probe-4 + §4 below. |
| Q5 | `VertexAiSessionService` schema; `chat_sessions` Firestore mirror? | **🟡 LIKELY SAFE / REVIEW** | Service stores full `raw_event` via `model_dump()` (new 2.0 path, with fallback). New fields (`node_info`, `isolation_scope`) are additive. Chat team review recommended. No migration. See probe-5 + §5 below. |
| Q6 | What bridge makes parity tests pass if AgentTool leaf calls remain? | **✅ NO BRIDGE NEEDED** | `_TaskAgentTool.run_async` returns None; framework dispatches via `ctx.run_node` → events flow natively. Parity tests pass after updating topology to task-mode. See probe-6 + §6 below. |
| Q7 | Can `LoopAgent` carry `mode='task'` given leaf-node constraint? | **🔴 NO (restructure needed)** | `LoopAgent` deprecated in 2.0; neither `LoopAgent` nor `Workflow` can carry `mode='task'`. Review sub-agents (worker + reviewer) can be `LlmAgent` leaves. See probe-7 + §7 below. |

---

## §1 — Q1: Inner Event Propagation (DECISIVE)

**Finding: YES — inner events reach the outer stream in ADK 2.0.**

The fundamental change from ADK 1.x is the new **node/graph runtime**:

**ADK 1.x (current KEN-E):**
- Sub-agents dispatched via `AgentTool.run_async` (inner-Runner path)
- `AgentTool.run_async` spins up a fresh `Runner`, consumes ALL inner events in a
  private loop, and returns only `last_content`
- `usage_metadata`, model chunks, tool calls — all discarded
- GitHub issue [#3984](https://github.com/google/adk-python/issues/3984) documents this

**ADK 2.0 (new architecture):**
- Task sub-agents dispatched via `_TaskAgentTool` → `ctx.run_node()` →
  `DynamicNodeScheduler` → `NodeRunner._run_node_loop`
- `NodeRunner._run_node_loop` iterates ALL events from `node.run()` and calls
  `ctx._invocation_context._enqueue_event(event)` for each
- `InvocationContext._enqueue_event` posts events to `ic._event_queue` (asyncio.Queue)
- `Runner._run_node_async` drains the queue via `_consume_event_queue`, yielding
  every event to the caller — **no isolation_scope filter on the outer consumer**
- The `isolation_scope` field tags inner task events for LLM-content-builder filtering
  (coordinator LLM doesn't see inner turns), but the outer Runner sees everything

```
Outer Runner.run_async consumer
  ↑ ALL events (including inner task sub-agent events)
ic._event_queue  ← _enqueue_event
  ↑
NodeRunner._run_node_loop → iterates node.run() events
  ↑
ctx.run_node() → DynamicNodeScheduler → _run_node_internal
  ↑
_dispatch_task_fc (intercepts _TaskAgentTool FC)
  ↑
LlmAgent(mode='chat') coordinator
```

**Source verified in ADK 2.0.0 and 2.1.0:**
- `google/adk/runners.py:Runner._consume_event_queue` — yields ALL events, no filter
- `google/adk/workflow/_node_runner.py:NodeRunner._run_node_loop` — enqueues all events
- `google/adk/agents/invocation_context.py:InvocationContext._enqueue_event` — posts to queue
- `google/adk/tools/agent_tool.py:_TaskAgentTool.run_async` — returns None (marker)
- `google/adk/workflow/_llm_agent_wrapper.py:_dispatch_task_fc` — uses ctx.run_node

**Caveat:** The legacy `AgentTool.run_async` path STILL discards events in 2.0 (#3984 OPEN).
KEN-E must NOT use `AgentTool` for specialist delegation; use the task-mode path exclusively.

---

## §2 — Q2: Task Mode in Graphs + #3984 Status

**Finding: Task mode prohibited as static Workflow graph node (2.0.0 and 2.1.0). Workaround available.**

`Workflow._validate_no_task_mode_graph_nodes()` raises `ValueError` at construction time if any
static graph node is an `LlmAgent` with `mode='task'`. The docstring explains why:

> "Task-mode agents are multi-turn — they pause for user replies and expect the
> original `node_input` (the task brief) to remain visible across re-dispatches.
> The workflow scheduler currently overwrites `node_input` with the latest user
> message on every re-entry, so the task brief is lost and the agent loses context."

**Allowed task-mode uses:**
1. `LlmAgent(mode='chat', sub_agents=[LlmAgent(mode='task', ...)])` — chat coordinator
   with task sub-agents, dispatched via `_TaskAgentTool` and `_dispatch_task_fc`
2. `ctx.run_node(task_agent, ...)` from a custom `FunctionNode` inside a Workflow

**GitHub #3984 status:** OPEN in 2.0.0 and 2.1.0. No code references to issue #3984
found in either release's source. No CHANGELOG entry found. The AgentTool event-discard
behavior is unchanged; #3984 is not on a fixed release milestone as of 2026-06-01.

**KEN-E impact:** AH-PRD-05's `execute_workflow` cannot use `AgentTool` and cannot use
task agents as static Workflow nodes. Must use the chat-coordinator-with-task-sub-agents pattern.

---

## §3 — Q3: Weave Contextvar Propagation

**Finding: asyncio.run on worker thread orphans Weave spans, but scope is limited to MCP pool checkout only.**

Python test (probe-3, Python 3.12.3):
```python
ThreadPoolExecutor.submit(worker_bare)  # bare asyncio.run → contextvar = None (orphaned)
ThreadPoolExecutor.submit(ctx.run, worker_ctx)  # explicit ctx.run → contextvar preserved
```

KEN-E's `_build_specialist` uses `get_pool_checkout_executor().submit(_runner)` where
`_runner` calls `asyncio.run(pool.get_or_create(...))`. This is for MCP toolset checkout
(timeout enforcement), not for running agent invocations.

**Scope:** Only MCP toolset construction spans will orphan from the parent Weave trace.
Main agent LLM calls, tool dispatch, and sub-agent events all happen in the main event
loop — Weave contextvars are fully propagated there.

**Existing issue:** This same orphaning exists on ADK 1.34.1 (not a 2.0 regression).

**Fix (if needed):** Replace `ex.submit(_runner)` with `ex.submit(contextvars.copy_context().run, _runner)`.
One-line change in `specialist_runtime.py`. Not blocking for the GO decision.

**ADK 2.0 specific:** The node/graph runtime runs sub-agents in the main asyncio event
loop via `asyncio.create_task()` (in `_run_node_internal`), so the contextvar issue
does not apply to sub-agent event propagation in the 2.0 architecture.

---

## §4 — Q4: usage_metadata in ADK 2.0 Events

**Finding: usage_metadata unchanged; extract_billable_tokens fully compatible.**

ADK 2.0 `Event.usage_metadata` type: `Optional[GenerateContentResponseUsageMetadata]` —
same as 1.x. The `GenerateContentResponseUsageMetadata` struct has two new optional fields
in the 2026 genai SDK release:
- `tool_use_prompt_token_count: Optional[int]`
- `traffic_type: Optional[TrafficType]`

`extract_billable_tokens` in `shared/token_accounting.py` uses duck-typing (`getattr` with
defaults), so both new fields are silently ignored.

**New fields on Event in 2.0 (non-breaking):**
- `node_info: NodeInfo` — path, output_for, message_as_output (routing metadata)
- `output: Any | None` — structured output from the node
- `isolation_scope: str | None` — scopes events to a specific function-call context

**Billing impact (improvement):** Inner task sub-agent events now reach the outer stream,
so their `usage_metadata` is now counted in `SessionTurnAccumulator` and the billing
meter. This is CORRECT — billing accuracy improves vs. ADK 1.x where inner tokens were
silently discarded.

**MER-E Weave extractor:** Must be updated (tracked in AH-97 on GO). The trace shape
changes from `transfer_to_agent → specialist_sub_agent_events` to a task-delegation
topology with `isolation_scope` on inner events. The per-turn dispatch trace contract
diff in `AH-PRD-09-trace-contract-diff.md` will need a 2.0 addendum.

---

## §5 — Q5: VertexAiSessionService Schema

**Finding: Backward-compatible; no schema migration required. Chat team review recommended.**

ADK 2.0's `VertexAiSessionService.append_event` stores the full event as `raw_event`
via `event.model_dump(exclude_none=True, mode='json', by_alias=True)`. This is a NEW
code path in 2.0 — 1.x stored only specific extracted fields.

New fields in `raw_event` on ADK 2.0: `node_info` (as `nodeInfo`), `output`, `isolation_scope`
(as `isolationScope`). These are passed to the Vertex AI Agent Engine API.

**Fallback:** If the API returns a `pydantic.ValidationError` on `raw_event` (older
Agent Engine backend doesn't accept the field), the service retries without `raw_event`.
This ensures backward compatibility across Agent Engine versions.

**chat_sessions Firestore mirror (KEN-E):** The mirror in `api/src/kene_api/chat/`
copies events from ADK sessions to Firestore for the Chat component. Assessment:
- If it stores raw event dicts: new fields appear in Firestore (additive, no breakage)
- If it extracts specific fields: `author`, `invocation_id`, `timestamp`, `content`,
  `usage_metadata` — all present and unchanged in 2.0
- No Firestore schema migration needed; new fields are optional

**Recommendation:** Chat team should audit `SessionTurnAccumulator` and the chat-sessions
side-table update code to confirm no hard-rejection of unknown Event fields before 2.0 migration.

---

## §6 — Q6: AgentTool Bridge for Parity Tests

**Finding: No bridge needed — task-mode architecture is the fix.**

In ADK 2.0's task-mode delegation:
1. `_TaskAgentTool.run_async` returns `None` (it's a marker/shim)
2. `_dispatch_task_fc` calls `ctx.run_node(task_agent, node_input, override_isolation_scope=fc_id)`
3. `ctx.run_node` routes through `DynamicNodeScheduler` → `NodeRunner._run_node_loop`
4. All inner events enqueued to `ic._event_queue` → yielded by outer Runner
5. A synthesized function-response event is emitted to the coordinator LLM (so it knows the task is done)

The parity test contract (`extract_billable_tokens` agrees across Chat and Billing) holds
because `usage_metadata` is still on the same event field and the helper uses duck-typing.

**Required parity test updates for ADK 2.0 adoption:**
- Test topology: use `LlmAgent(mode='task')` sub-agents instead of `sub_agents=[specialist]`
- Expected events: include `isolation_scope` on inner task events, `node_info` on all events
- Token counts: increase by the inner task sub-agent's token cost (previously discarded)
- The parity INVARIANT (Chat and Billing see the same total) continues to hold

**Synthetic state-key bridge (Q6 Option 1):** Not needed. The architecture IS the fix.  
**Per-turn counter flushed via side-table (Q6 Option 2):** Not needed. Not needed.

---

## §7 — Q7: LoopAgent + task mode

**Finding: LoopAgent cannot carry mode='task'. Review-loop restructuring required for ADK 2.0.**

- `LoopAgent` is **deprecated** in ADK 2.0 (replaced by `Workflow`)
- Neither `LoopAgent` nor `Workflow` has a `mode` field — they inherit from `BaseAgent`,
  not `LlmAgent` which has `mode`
- `mode='task'` applies ONLY to `LlmAgent` leaf nodes (no `sub_agents`)
- A `LoopAgent` wrapping a worker + reviewer cannot be task-mode

**Short-term path (recommended for R1/R2):** Keep `LoopAgent` as the review-loop
container. It is deprecated but functional in ADK 2.0. Worker and reviewer sub-agents
remain `LlmAgent` leaves without `mode='task'` (they don't need it — they're one-shot
per iteration). The coordinator dispatches the review pipeline as a whole.

**Long-term path (ADK 2.0 idiomatic):** Replace `LoopAgent` with `Workflow(graph=...)`.
Define worker + reviewer as static graph nodes; use a loop trigger when reviewer rejects.
This is a non-trivial redesign — appropriate after the 2.0 migration is stable.

**Leaf-node constraint scope:** The constraint (task-mode agents must be leaves) applies
to the agent that PAUSES mid-invocation to receive user input. The review-loop worker and
reviewer are one-shot per turn — they don't need `mode='task'`. Only the coordinator
(the root chat agent) needs to "regain control" after a task completes, and it does so
via the `_dispatch_task_fc` → `ctx.run_node` mechanism, not via task mode on the review loop.

---

## §8 — Migration Path (GO branch)

If the product team approves the ADK 2.0 migration (tracked in AH-97):

### Phase 1: Foundation (AH-PRD-09 retrofit)
1. Bump `google-adk` to `2.0.0` (NOT done in this spike — spike workspace is isolated)
2. Update `build_hierarchy()` to use `LlmAgent(mode='chat')` for root coordinator
3. Migrate specialist construction: task-mode delegates use `LlmAgent(mode='task')`
4. Replace `generate_dispatch_functions` / `dispatch_to_{name}()` with task-mode sub-agents
5. Update AH-75 parity tests for 2.0 event topology
6. Chat team: audit `SessionTurnAccumulator` for 2.0 event field compatibility
7. MER-E team: update Weave extractor for 2.0 trace shape

### Phase 2: AH-PRD-05 rewrite
8. Rewrite `execute_workflow` using `LlmAgent(mode='chat')` coordinator +
   `LlmAgent(mode='task')` sub-agents per step
9. Fan-out via concurrent `ctx.run_node()` calls (replaces `ParallelAgent`)
10. Synthesize via a task-mode specialist with `depends_on` semantics
11. Approval-checkpoint via `wait_for_output=True` or standard task multi-turn

### Phase 3: Review-loop
12. Keep `LoopAgent` for review-loop wrapper (deprecated but functional in 2.0)
13. Plan `Workflow(graph=...)` migration as a separate R3 project
14. Update reviewer instruction for 2.0 event topology (no behavior change)

---

## §9 — NO-GO Fallback (if GO conditions cannot be met)

Per the analysis doc §5.1: maintain ADK 1.34.1 (just bumped from 1.27.5), implement
AH-PRD-05's multi-step workflow via the **static composition tree** pattern:

- All specialists remain `transfer_to_agent` sub-agents (current AH-75 topology)
- Multi-step coordination via sequential dispatch calls from the root LLM
- Fan-out via multiple `transfer_to_agent` in separate turns (no parallel)
- No inner-event-loss problem because `transfer_to_agent` is native ADK
- Limitation: no true parallel fan-out in a single turn; no post-process compose step

This fallback does NOT achieve the supervisor-orchestrator product goal (single-turn
fan-out + synthesis) but avoids re-introducing the AH-75 billing/tracing defects.

---

## Primary Sources

| Source | Claim verified |
|--------|---------------|
| `docs/design/adk2-supervisor-orchestration-analysis.md` | Pre-spike background memo and decision framework (not a primary source for probe evidence; context only) |
| [`google/adk-python/issues/3984`](https://github.com/google/adk-python/issues/3984) | OPEN; AgentTool still discards events in 2.0/2.1 |
| `google/adk/runners.py:Runner._run_node_async` (ADK 2.0.0) | Event queue architecture; all events yielded |
| `google/adk/workflow/_node_runner.py:NodeRunner._run_node_loop` (ADK 2.0.0) | All events enqueued |
| `google/adk/tools/agent_tool.py:_TaskAgentTool.run_async` (ADK 2.0.0) | Returns None; ctx.run_node dispatch |
| `google/adk/workflow/_llm_agent_wrapper.py:_dispatch_task_fc` (ADK 2.0.0) | ctx.run_node → event propagation |
| `google/adk/workflow/_workflow.py:Workflow._validate_no_task_mode_graph_nodes` | Task mode prohibited as static graph node |
| `google/adk/agents/loop_agent.py:LoopAgent` (ADK 2.0.0) | @deprecated; no mode field |
| `docs/spike-adk2/probe-{1-7}-*.py` | Runnable reproductions of all 7 ACs |
| `docs/spike-adk2/probe-{1-7}-*.log` | Captured probe output |

---

_Spike conducted by: agentic-harness-dev-team | AH-96 | 2026-06-01_

---

## Live Evidence (AH-99)

The static analysis above returned a **CONDITIONAL GO**. [AH-99](https://linear.app/ken-e/issue/AH-99)
(Phase 0.5) is the live-validation gate that converts this to a **confirmed GO** or **NO-GO** by
running the four decisive probes against real Gemini Flash and the dev Vertex AI Agent Engine.

Current status: ✅ **GO-confirmed** (2026-06-01). All four live probes (Q1, Q4, Q5, Q7) executed
against real Gemini Flash + the dev Agent Engine on `ken-e-dev` and exit 0:
- **AC #1** (task-mode): inner specialist events reach the outer stream with non-null `usage_metadata`.
- **AC #2** (dynamic-graph): `ctx.run_node` fan-out branches surface inner events in the outer stream.
- **AC #3**: `node_info` / `isolation_scope` survive a real `VertexAiSessionService` round-trip (no migration needed).
- **Q7**: the `LoopAgent` review-loop terminates via `exit_loop` end-to-end (deprecated → `Workflow` long-term).

The earlier "INDETERMINATE due to missing IAM" note was incorrect — IAM is sufficient on a
credentialed ADC; the real blockers were two probe bugs (model pin + Vertex routing), now fixed.
See [`docs/spike-adk2-supervisor-orchestration-live.md`](spike-adk2-supervisor-orchestration-live.md)
for the full evidence table, decisive event JSON, and the AH-97 routing decision.

[AH-97](https://linear.app/ken-e/issue/AH-97) (doc propagation) is **unblocked**: per AH-99 AC #5,
write the ADK 2.0 supervisor-orchestration model as the target architecture.
