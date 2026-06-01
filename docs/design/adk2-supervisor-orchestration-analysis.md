# ADK 2.0 & KEN-E Supervisor-Orchestration — Analysis & Recommendation

> **Status:** Analysis / recommendation — **decision requested**. Spike-gated.
> **Date:** 2026-06-01
> **Owner:** Agentic Harness (Core AI / Agent Platform)
> **Scope:** Whether and how to make KEN-E a supervisor-orchestrator (control the conversation, build TODO lists that delegate individual tasks to sub-agents, post-process sub-agent output, fan out to multiple specialists and synthesize in one turn), and whether to adopt Google ADK 2.0 to do it.
> **Decision gate:** Linear **AH-96** — Phase 0 spike (does ADK 2.0 propagate inner node events to the outer Runner stream?). Do not fund the rework until that spike returns GO/NO-GO.
> **Related:** [AH-PRD-05](./components/agentic-harness/projects/AH-PRD-05-multi-step-workflows.md) (Multi-Step Workflow Orchestration — the rewrite target), [AH-PRD-09](./components/agentic-harness/projects/AH-PRD-09-per-turn-dispatch.md) §4.6 (AH-75 dispatch rationale / event-loss evidence), [AH-PRD-02](./components/agentic-harness/projects/AH-PRD-02-agent-factory.md) §5.4, SK-10 (ADK unpin).

> **Provenance & confidence.** This memo was produced by a multi-agent analysis workflow (2026-06-01) and the ADK 2.0 claims were adversarially verified against primary sources — PyPI, the `google/adk-python` CHANGELOG, `adk.dev/2.0`, and the GitHub REST API for issue state (verification overall-confidence: HIGH). **Two facts to keep front-of-mind:** (1) the single *decisive* question — whether 2.0's task-mode/graph paths propagate inner sub-agent events to an outer `Runner.run_async` consumer — is **UNVERIFIED by any primary source** and is exactly what AH-96 must close; (2) the "2.0 sessions readable by ADK 1.28+" threshold cited below came from a search summary, not a primary page — treat the specific version number as unconfirmed. During web research, two agents independently encountered and correctly **refused to act on a prompt-injection** embedded in GitHub Discussion #5263; source 2.0 facts from `adk.dev/2.0` only.

---

# Decision Memo: Making KEN-E a Supervisor-Orchestrator — and the ADK 2.0 Question

**Audience:** KEN-E Product + Engineering
**Author:** Lead Architect
**Date:** 2026-06-01
**Status:** Decision requested — spike-gated recommendation

---

## 1. Executive summary

**Yes, we can give KEN-E supervisor-orchestration control, and ADK 2.0 is the strategically correct vehicle — but we should not commit to a 2.0 migration until a one-week spike proves the single fact everything hinges on: that 2.0's task-mode / graph paths propagate inner sub-agent events (`usage_metadata`, tool calls, streaming chunks) to the *outer* Runner stream that Billing, Chat status, MER-E, and UI streaming all consume.** The product's five requirements (control the conversation, delegate TODO items, post-process, fan-out-and-synthesize, orchestrate across specialists) are exactly the "parent stays in control and gets results back" pattern that AH-75 deliberately abandoned on ADK 1.27.5 — because the only 1.x mechanism that returns control to the parent (`AgentTool` / inner-Runner) silently discards every inner event except `state_delta` + final content (verified against `agent_tool.py:249-276` and `functions.py:1114`). ADK 2.0 ships the *conceptually* perfect primitives (task mode's `complete_task` auto-return; dynamic graphs' `ctx.run_node` + `asyncio.gather` fan-out/synthesize), and KEN-E's own `AH-PRD-02 §5.4` predicted this. **But the decisive guarantee is unverified by any primary source, and the underlying AgentTool event-loss bug (GitHub `#3984`) is still OPEN post-GA.** Recommendation: **spike-then-decide** — fund a 2.0 propagation spike now; if it passes, adopt 2.0 as the supervisor substrate; if it fails, fall back to a current-ADK composition graph (AH-PRD-05's tree) plus a hand-built event bridge. Do not build the inner-Runner `execute_workflow` tool on 1.x under any circumstance — it re-introduces every defect AH-75 fixed.

---

## 2. The core conflict

### 2.1 Why AH-75 chose `transfer_to_agent`

The deployed root agent (`ken_e`, `tools=[]`) dispatches via ADK-native `transfer_to_agent`. AH-75 (AH-PRD-09 §4.6) **replaced** an earlier `delegate_to_specialist` function-tool (which ran an inner Runner) with native transfer for one verified reason: **only `transfer_to_agent` propagates inner sub-agent events to the outer Runner event stream.** Confirmed against the pinned source:

- `AgentTool.run_async` (`agent_tool.py:249-276`) iterates the inner Runner and keeps **only** `event.actions.state_delta` and the last `event.content`, returning a single merged string.
- `__build_response_event` (`functions.py:1114`) builds the function-response `Event` with `content` + `actions` and **no `usage_metadata` slot** — so no callback can retro-fit token usage onto the tool result.
- By contrast `LlmAgent._run_async_impl` yields sub-agent events natively (`llm_agent.py:469-481`), and transfer is gated on `function_response.name == 'transfer_to_agent'` (`llm_agent.py:805-818`).

**Five consumers depend on that outer stream** (descending fragility):

| Consumer | Mechanism | Failure under inner-Runner dispatch |
|---|---|---|
| **Billing token meter** | `shared/token_accounting.py::extract_billable_tokens(event)` reads `event.usage_metadata` (verified line 80) | Specialist tokens become invisible → **billing under-counts every delegated turn** |
| **Chat status** | `chat_after_agent_callback._build_turn_delta` over `session.events` filtered by `invocation_id`; root-only guarded | Tool/message counts + tokens for delegated work go to **zero** (sub-agent runs in a separate inner session) |
| **UI streaming** | `chat.py` parses serialized `stream_query` outer stream → `reasoning`/`text` SSE channels | Live specialist "typing" + reasoning **vanish**; user sees "silent then dump" |
| **Review loop** | `extract_iterations`/`_check_hallucinated_approval` scan flat event list for worker/reviewer authored `state_delta` | All iterations **collapse to one opaque result**; hallucinated-approval detection degrades |
| **MER-E Weave traces** | Callback-driven (more resilient), but contextvar call-stack + §2/§14 span hierarchy | Sub-spans can **orphan** across thread boundaries; span shape changes |

The Chat start/stop *stamps* (root-only `before/after_agent` boundary) and the `_available_specialists` roster capture survive any dispatch model — they read the attached sub-agent set, not the event stream.

### 2.2 The precise technical problem

`transfer_to_agent` **hands the turn over and does not return.** It is one-way by design — that is exactly why `specialist_runtime.py:579` sets `disallow_transfer_to_parent=True` (to force the *next* user turn back to root). The product asks for the opposite: the parent transfers down, the child runs, **the parent regains control and post-processes / fans out to a second child / synthesizes — all in one user turn, with all child events on the outer stream.**

ADK 1.27.5 offers no path that is both. This is a genuine **trilemma**:

| Path | Parent regains control in-turn? | Outer-stream events preserved? |
|---|---|---|
| **(A)** `transfer_to_agent` (today) | ❌ No (one-way handoff) | ✅ Yes (native) |
| **(B)** `AgentTool` / inner Runner | ✅ Yes | ❌ No (the AH-75 defect) |
| **(C)** Static sub-agent composition (Parallel/Sequential/Loop trees) | ⚠️ "Parent" is a *static graph*, not a freely-reasoning LLM between calls | ✅ Yes |

**The precise problem to solve: obtain (B)'s call-and-return ergonomics while keeping (A)'s native event propagation.** ADK 1.x gives you one or the other. ADK 2.0 *claims* to give both — that claim is the entire decision.

---

## 3. What must change to enable supervisor-orchestration

Two layers. The **state layer is nearly ready**; the **dispatch/orchestration layer is the hard, net-new work.**

### 3.1 Reuse (already built or specced)

- **TODO-list tools** (`set_todo_list`/`update_todo_list`, `tools.yaml:313-332` `default_global: true`, root-carried) — satisfy requirement #2's *display* side. **Net-new extension:** add an `assignee` (specialist doc_id), `query`, `criteria`, `depends_on`, `result_key`, and a richer `status` to `TodoItem` so it becomes the supervisor's task ledger (today it is a string + `completed` bool with no dispatch binding). Decision: widen the existing item schema (single source of truth) vs. a parallel `orchestration_plan` key projected to a display todo list.
- **Review loop** (`build_review_pipeline`, LoopAgent, live per-turn) — directly reusable as the per-delegated-task wrapper, exactly as AH-PRD-05 planned (call once per fanned-out task). Covers requirement #3 at the *single-specialist* level.
- **AH-PRD-05 composition tree** (`build_workflow_pipeline`) — the **correct primitive**: ParallelAgent fan-out per dependency level, SequentialAgent gates, a synthesizer step (`depends_on >= 2`, `include_contents='none'`). Reuse the *tree shape*.
- **`register_artifact`** (`api/.../chat/artifacts.py:335`) — the shipped provenance substrate (GCS + `ChatArtifactIndex` Firestore row, `created_by_tool`). Reuse for collecting/attributing sub-agent outputs.
- **Project Tasks `depends_on` DAG + `assignee_type`** — borrow as *conceptual inspiration* for the task ledger. **Do NOT route in-turn fan-out through `TaskOrchestrator`** — that is the cross-session, scheduled, separate-invocation layer (and it is entirely unbuilt).

### 3.2 Net-new (must be built)

- **The dispatch primitive that returns control to the root while preserving the outer stream.** This is the crux and does not exist. AH-PRD-05's `execute_workflow()` function-tool calling `invoke_pipeline()` via an inner Runner is the **wrong wrapper** — it is precisely the (B) event-loss trap. **The tree must be reachable as a sub-agent graph (via attach/transfer machinery), not invoked inside a function tool.**
- **The synthesizer agent_config** — specced in AH-PRD-05 but never seeded as a live Firestore config; fan-out synthesis has no default executor today.
- **Spec-vs-reality reconciliation:** AH-PRD-05 §5.4 assumes a `response_artifacts` session-state list that **does not exist** (0 grep hits in `app/`); the shipped convention is `register_artifact`. AH-PRD-05 and the project-tasks README (which still references the deleted `delegate_to_specialist`) must be corrected.

### 3.3 Outer-stream contracts to rework regardless of path

If the chosen path uses *any* inner-Runner/AgentTool leaf calls, three artifacts need rework **before cutover**, and the merge-blocking parity tests (`test_chat_billing_parity.py`, AH-PRD-09 §7 ACs #9/#10) must still pass:

1. **Token path** — `accumulator.add_stream_chunk` + `chat_callbacks._build_turn_delta` must capture sub-call usage (synthetic state keys the accumulator reads, or a parent-owned per-turn counter flushed via the side-table).
2. **`trace-structure-spec.md` §2/§14/§16** — currently **stale** (still describes the deleted `delegate_to_specialist` span, names `delegate_to_specialist_trace.json` while AH-PRD-09 references `transfer_to_specialist_trace.json`). Re-spec the hierarchy + re-issue the canonical fixture.
3. **`chat.py` SSE parser** — must author-tag interleaved multi-author partial events to render fan-out progress (today it assumes a single logical author sequence).

### 3.4 Requirement → change map

| Req | Collision | Reuse | Net-new |
|---|---|---|---|
| **R1** Control conversation | LOW | root LLM loop, session.state scratchpad | dispatch that *returns* results |
| **R2** TODO delegation | LOW | `todo_lists` tools | widen `TodoItem` schema (assignee/result binding) |
| **R3** Post-process output | **HARD** | review-loop draft/feedback keys | root regains control mid-turn |
| **R4** Fan-out + synthesize | **HARDEST** | `build_workflow_pipeline` tree, synthesizer | parallel dispatch returning to root + author-tagged streaming |
| **R5** Cross-specialist orchestration | MEDIUM | `pending_workflow` continuation, `register_artifact` | embeds R3/R4 → inherits their collisions |

---

## 4. ADK 2.0 assessment

**Verification confidence: HIGH on capabilities and the blocker; the single decisive propagation guarantee is UNCERTAIN.**

### 4.1 Confirmed (high confidence, primary sources)

- **2.0.0 is GA (2026-05-19); 2.1.0 (2026-05-23); 1.x continues (1.34.1, 2026-05-22).** KEN-E is pinned to **1.27.5** in 4 locations, all with an SK-10 unpin TODO (verified locally). 2.0 is a **major architecture shift**, not a drop-in: `BaseAgent` now subclasses `BaseNode`; agents/tools/functions are graph nodes.
- **Task mode** (`Agent(mode='task')`): auto-injected `request_task_<name>` tools; sub-agent runs until `complete_task`, then **control automatically returns to the parent.** This is the call-and-return semantics 1.x lacks, and exactly what AH-PRD-02 §5.4 predicted. `transfer_to_agent` is **retained** (chat-mode handoff), not removed — task mode *augments* it.
- **Dynamic graphs**: `ctx.run_node(agent, input)` + `asyncio.gather` → fan out to N sub-agents and synthesize in one turn. `single_turn` mode runs parallel branches in isolated session sub-branches; parent receives collected results for fan-in synthesis. This is requirements #4/#5 natively expressed.
- **`SequentialAgent`/`ParallelAgent`/`LoopAgent` persist**; `RoutedAgent` (code router) is new.

### 4.2 The blockers (high confidence)

- **`#3984` ("Support Event Streaming propagation from AgentTool to Runner") is still OPEN post-GA** (state=open, labels core/needs-review, milestone=null, opened 2025-12-20). Its body describes KEN-E's AH-75 problem verbatim. **So the AgentTool path still loses inner events in 2.0.** The reason AH-75 moved off agent-as-tool remains valid for that specific path.
- **Task mode is explicitly DISABLED inside graph-based workflows in v2.0.0** ("expected to be re-enabled in a future release"). Since 2.0's whole runtime *is* the graph engine, the cleanest call-and-return primitive is not usable in the new runtime today. **Maturity risk.**
- **Task-mode agents must be leaf agents (no sub-agents)** — directly constrains wrapping our review-loop `LoopAgent` in `mode='task'`; may force restructuring.

### 4.3 The decisive uncertainty (LOW confidence — this is what the spike must close)

**Whether the new graph/task-mode paths surface *inner* node events (model chunks, inner tool_calls, streaming) to an *outer* `Runner.run_async` consumer — vs. only final node output — is UNCONFIRMED by any primary source.** 2.0 added `Event.node_info`/`Event.output` and centralizes emission in the Workflow runner (warning that manual `session.events.append` "circumvents the graph engine"), which *implies* the engine owns the stream — but no source states inner events reach an external consumer the way KEN-E's billing/chat/MER-E/UI need. With `#3984` open, **we must not assume 2.0 solves event propagation without a hands-on spike against v2.0.0.**

### 4.4 Migration cost/risk (moderate, not a rewrite)

Google asserts 1.x agent compatibility; KEN-E uses standard constructs. Breaking changes that touch KEN-E:

- `BaseAgent → BaseNode`; **`_run_async_impl`/`generate_content` overrides are silently ignored** — move logic to `Before/AfterAgentCallback`.
- **`Event` gains `node_info`/`output`** — the Vertex AI Agent Engine **managed session backend** (which KEN-E does not own) must accept the new fields, and the `chat_sessions` Firestore mirror / any strict JSON validator (`additionalProperties:false`) must be updated. **Open risk.**
- **Broad `except Exception` in tools disables 2.0 auto-retry**; catching `BaseException` traps `NodeInterruptedError` (breaks HITL) — audit needed.
- **No direct `session.events.append`/`enqueue_event`** — yield instead.
- Python **3.11+** safe floor. `McpToolsetPool` is KEN-E-owned and should port unchanged (confirm constructor signature stability).
- The per-turn resolver (`resolve_config`/`resolve_agent`) and `McpToolsetPool` **largely survive** — the main edit is setting `mode` on resolved specialists.

> ⚠️ **Security note for the team:** GitHub Discussion **#5263** ("Migration guide from ADK 1.x to 2.0") contains a **prompt-injection** in its body (a fake "ADK ANSWERING AGENT" block instructing readers to post a bogus security advisory on #5196). It contains **no real migration content** — source migration guidance from `adk.dev/2.0` only. Do not act on that thread.

---

## 5. Recommendation

**Spike-then-decide.** Fund a tightly-scoped ADK 2.0 propagation spike now (Phase 0 below). Adopt 2.0 as the supervisor substrate **only if** the spike proves outer-stream event propagation. This is the only recommendation calibrated to the verification: 2.0's *capabilities* are confirmed-perfect, but the *one guarantee KEN-E lives or dies on* is genuinely unverified and the underlying bug class is still open.

**Why not adopt 2.0 now:** the decisive propagation guarantee is unconfirmed, task mode is disabled in graphs in 2.0.0, and the managed-session-backend compatibility is an unowned open risk. **Why not build the supervisor on current ADK as the primary plan:** the only 1.x return-to-parent path is the inner-Runner trap AH-75 proved unworkable; building it re-introduces billing under-counting, chat-count zeroing, review-loop collapse, and UI streaming blackout, requiring hand-built event-bridging that ADK gives no clean hook for.

**Sequencing decisions:**
- **Bump 1.27.5 → 1.34.x first** (low-risk, same-major; de-risks within the 1.x line) regardless of the 2.0 decision — this also discharges the SK-10 TODO.
- **Hard rule:** never ship AH-PRD-05's `execute_workflow()` inner-Runner function-tool on 1.x.

### 5.1 Fallback if the spike fails (2.0 does NOT propagate inner events)

Build the supervisor on **path (C) — static sub-agent composition** (AH-PRD-05's `build_workflow_pipeline` tree) reachable via the existing attach/transfer machinery, **plus a hand-built event bridge** for any unavoidable inner-Runner leaf call: a forwarder that (a) writes per-sub-call `usage_metadata` + tool/message counts into `session.state` under known keys, (b) teaches `accumulator` + `_build_turn_delta` + the `chat.py` SSE parser to read them, and (c) tags inner-Runner events with the **outer `invocation_id`** so `_gather_turn_events` picks them up. This is more work and forfeits the "LLM freely reasoning between sub-calls" ergonomics, but it is fully expressible on 1.x today and preserves every parity test.

---

## 6. Phased plan

| Phase | Goal | Key work | Risk | Home |
|---|---|---|---|---|
| **0 — Decisive spike** (1 wk) | Prove/disprove 2.0 outer-stream propagation | Stand up v2.0.0; instrument a task-mode AND a dynamic-graph fan-out flow; assert inner model-call/tool events (with `usage_metadata`) appear in `Runner.run_async` output that `extract_billable_tokens` + the TurnDelta builder + Weave see; test the review-`LoopAgent`-as-`mode='task'` leaf constraint; confirm Vertex Agent Engine managed session accepts `node_info`/`output` | Spike inconclusive on managed-session backend; contextvar orphaning across thread boundaries | **New `AH-PRD-1x` spike PRD** (sibling to SK-10) |
| **1 — 1.34.x bump** (parallel) | De-risk within 1.x; discharge SK-10 | Unpin 1.27.5 → 1.34.x in all 4 locations; re-run parity suite | Low | SK-10 / existing |
| **2 — Contract preservation** | Make outer-stream contracts robust to the new dispatch | Token-path capture of sub-call usage; re-spec `trace-structure-spec.md §2/§14/§16` + re-issue canonical fixture; author-tag `chat.py` SSE parser; widen `TodoItem` schema; seed synthesizer agent_config | Parity tests (AH-PRD-09 §7 #9/#10) are merge blockers | New `AH-PRD` + Chat/MER-E tickets |
| **3 — Orchestration primitive** | Build the supervisor on the spike-chosen substrate | If 2.0 passes: task-mode coordinator + single-turn fan-out + synthesizer; if fail: composition tree + event bridge. Revive AH-PRD-05's tree, **drop** `execute_workflow`/`invoke_pipeline` wrapper; correct `response_artifacts` → `register_artifact`; correct project-tasks README | The hardest req (#4 fan-out) | **Rewritten AH-PRD-05** |
| **4 — Migration / cutover** | (2.0 path only) full BaseNode/graph migration | `agent_factory` re-arch against graph runtime; `except`/`append` audits; managed-session schema; chat_sessions mirror | Breaking architectural migration | New `AH-PRD` |

**Layer boundary (enforce):** in-session fan-out lives in the **Agentic Harness** workflow primitive; **Project Tasks / `TaskOrchestrator`** owns persistent, cross-session, scheduled work — borrow only its `depends_on` DAG + `assignee_type` concepts.

---

## 7. Risks & open questions

**Top risks:** (1) Spike shows 2.0 graph/task-mode does *not* propagate inner events to outer consumers (`#3984` still open) → forces the heavier fallback bridge. (2) Task mode disabled in graphs in 2.0.0 — the clean primitive may be unusable until a future release. (3) Vertex Agent Engine managed-session backend (unowned) may reject `node_info`/`output` events. (4) Review-`LoopAgent` cannot carry `mode='task'` (leaf-node constraint) → restructure. (5) Any inner-Runner leaf path re-breaks the merge-blocking Billing/Chat parity tests unless the event bridge is complete first.

**Open questions the spike must close:**
1. **DECISIVE:** Do inner sub-agent/node events (model chunks, inner tool_calls, streaming) reach the *outer* `Runner.run_async` consumer in 2.0 task-mode AND dynamic-graph paths — or only final node output?
2. When is task mode re-enabled inside graphs? Is `#3984` on any roadmap/milestone?
3. Does running an inner Runner via `asyncio.run` on a worker thread (the `_build_specialist` pool pattern) preserve Weave's contextvar call-stack, or do sub-spans orphan from the `ken_e_agent` root?
4. Where does `usage_metadata` land on 2.0 events (with `node_info`/`output`), and do `extract_billable_tokens` + the MER-E Weave extractor still read it?
5. Does the Vertex Agent Engine managed session accept 2.0 events with no schema change, and does the `chat_sessions` Firestore mirror need migration?
6. If any AgentTool leaf calls remain: synthetic state-keys the accumulator reads, or a parent-owned per-turn counter flushed via the side-table? (Determines whether parity tests pass.)
7. Which trace fixture actually exists in `app/adk/tracking/tests/fixtures`, and is MER-E currently matching the transfer shape or the stale `delegate` shape?

---

**Bottom line:** ADK 2.0 is the right strategic target and dissolves the trilemma *in principle* — but the one fact that matters most to KEN-E (outer-stream propagation) is unverified, and the underlying bug is open. Gate the rework on Phase 0. Bump to 1.34.x and fix the outer-stream contracts in parallel so we are ready to build on whichever substrate the spike chooses.
