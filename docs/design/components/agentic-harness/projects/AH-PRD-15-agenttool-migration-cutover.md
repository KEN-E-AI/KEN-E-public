# AH-PRD-15 — Agent-as-Tool Isolation & ADK 2.0 Prod Cutover

**Status:** Re-planned (AH-121, 2026-06-07) — ADK 2.0 migration initiative (Phase 4)
**Owner team:** Core AI / Agent Platform (Agentic Harness)
**Blocked by:** [AH-PRD-13](./AH-PRD-13-adk2-foundation.md) (the chat tree must be on ADK 2.0). Coordinates with AH-PRD-05 (coordinator tool model) and AH-PRD-14 (parity contracts).
**Blocks:** **ADK 2.0 production cutover** — this PRD's completion is the cutover go/no-go gate.
**Release:** 1 — Foundation (ADK 2.0 migration initiative; owns the prod-cutover gate).
**Decision record:** [DESIGN-REVIEW-LOG Review 45](../../../DESIGN-REVIEW-LOG.md#review-45--adk-20-migration-initiative-structuring-strategy-agent-pin-sk-10-correction); origin: [AH-99](https://linear.app/ken-e/issue/AH-99) §9 carry-forward.

> **⚠️ RE-PLAN (AH-121, 2026-06-07) — the original task-mode premise is invalid.**
> The original plan migrated `agent.google_search` from an `AgentTool` to a
> `mode='task'` sub-agent to fix the `#3984` billing under-count. **That is
> fundamentally unworkable.** The built-in `google_search` grounding tool (and the
> `numerical_analyst` code-execution leaf) must be the ONLY tool in their LLM
> request — Gemini rejects `400 INVALID_ARGUMENT: "Multiple tools are supported only
> when they are all search tools."` whenever a function declaration shares the
> request. **Every** in-hierarchy sub-agent mode injects one next to it
> (`mode='task'` → `FinishTaskTool`; `mode='chat'` → `transfer_to_agent`), so the
> leaf can ONLY be isolated by an `AgentTool` (own sub-runner, no injected sibling
> tool). The task-mode cutover deployed to prod and `agent.google_search` 400'd on
> **every** web-search turn (AH-121 incident). Verified against ADK 2.0 source and a
> live staging engine. **The re-plan keeps these tools as isolated `AgentTool`s and
> recovers the `#3984`-dropped `usage_metadata` with a leaf `after_model_callback`,
> not task-mode.** This document's §2/§5/§7 are revised accordingly; the original
> task-mode framing is retained only where struck through for history.

> **Why this is its own PRD.** [AH-98](https://linear.app/ken-e/issue/AH-98) shipped `agent.google_search` as an `AgentTool(agent=create_google_search_agent())` (`source="agent"`), and [AH-100](https://linear.app/ken-e/issue/AH-100) made it per-turn-assignable to the **root**. On ADK 2.0, GitHub `#3984` (OPEN) means `AgentTool.run_async` still **discards inner sub-agent events** — so the search sub-agent's `gemini-2.5-flash` tokens go **uncounted**: the exact AH-75 billing defect, on the most critical agents. Adopting 2.0 (AH-PRD-13) without fixing this ships a billing regression to prod. **Re-plan correction:** the fix is *billing capture on the isolated AgentTool leaf*, NOT moving it off the AgentTool path (which is the only path that works). This PRD is the **prod-cutover gate**.

---

## 1. Context

Post-AH-75, the chat runtime preserves outer-stream events via ADK-native `transfer_to_agent`. AH-98 then re-introduced an inner-Runner path for one specific capability — web search as an `AgentTool` — because at the time (1.34.1) `AgentTool` was the only way to expose a sub-agent as a *callable tool* inside another agent's turn. On 1.34.1 this is a latent issue; on 2.0 it is an active regression (`#3984` still open).

ADK 2.0 provides the correct replacement: **task mode** (`mode='task'` sub-agent invoked via the auto-injected `request_task_<name>` tool, returning control on `complete_task`) and **`ctx.run_node`** for parallel fan-out — both of which propagate inner events to the outer stream (AH-99 probe-1 / probe-4). This PRD migrates the agent-as-tool registry/resolver to emit task-mode sub-agents instead of `AgentTool` instances on 2.0, re-validates AH-98's parallel-search behaviour under the new concurrency model, and reconciles AH-100's per-turn root-tool hot-reload with the supervisor coordinator's tool model.

**Scope boundary — `strategy_agent` is excluded.** Per Review 45, `app/adk/agents/strategy_agent/` (the bulk of the repo's `AgentTool` usage) stays pinned to ADK 1.34.x and is retired via KG-PRD-05. Its `AgentTool` usage never reaches 2.0, so it is **out of scope**. This PRD covers only the **chat-tree** agent-as-tool surface.

**Chat-tree AgentTool surface (recon 2026-06-02):**
- `app/adk/tools/registry/agent_tool_registry.py` — the AH-98 `source="agent"` registry that wires `agent.google_search` (`agent.{name}` tool IDs; consumed by `roster.py` + `specialist_runtime`).
- `app/adk/agent_standalone_embedded.py` — wires `AgentTool(agent=google_search_agent)` but is **not referenced by `deploy_ken_e.py` or `hierarchy.py`** (not in the chat deploy path). Disposition: verify legacy + remove (or exclude from the 2.0 build).

---

## 2. Scope

> **Re-planned (AH-121).** The struck-through bullets reflect the original
> task-mode plan, retained for history. The live bullets are the AgentTool-isolation
> design that actually ships.

### In scope (re-planned)
- **Keep `source="agent"` tools as isolated `AgentTool`s.** `google_search`
  (built-in grounding) and `numerical_analyst` (built-in code execution) wrap a
  built-in tool that Gemini forbids alongside any function declaration. They are
  registered on an **isolated AgentTool lane** in `agent_tool_registry.py`
  (`register_isolated_agent_tool` / `resolve_isolated_agent_tools`), filtered by the
  same `agent.{name}` opt-in id, and routed into `RosterResolution.tools` (regular
  tools), **not** `sub_agents`. The dormant task-mode lane is retained for a future
  multi-tool agent-tool that can tolerate the injected delegation tool.
- **Recover the `#3984`-dropped tokens with a leaf `after_model_callback`.** Each
  isolated leaf carries `capture_agent_tool_usage` (`app/adk/agents/agent_tool_billing.py`),
  which parks the leaf model call's `usage_metadata` in a per-turn off-state sink
  (keyed by the outer `invocation_id` via a `ContextVar`; mirrors the proven
  `tool_trace_context.py` pattern that survives `AgentTool.run_async`'s state
  deep-copy). The root `chat_after_agent_callback` drains the sink and folds the
  total into the turn delta. Verified with the real `extract_billable_tokens` on
  **both** root (AH-100 path) and specialist assignment.
- **`numerical_analyst` is fixed alongside `google_search`** — it has the identical
  task-mode 400 (code-exec + injected `FinishTaskTool`); the same isolation +
  billing-callback fix applies.
- **Mandatory live-Gemini staging smoke** (`smoke_google_search_live.py`) before any
  prod re-deploy — a real grounded web-search turn against the staging engine that
  asserts no `error_code`, a grounded answer, and the leaf tokens reaching the meter.
  The AC #1–#6 suites mock the LLM; this is the gate the prod 400 slipped through.
- **AC #4 no-AgentTool guard** is amended to a narrow allow-list (the two isolation
  files) + mandatory `isolation-required` marker + a companion test asserting the
  billing callback is present — so an AgentTool can never be reintroduced unbilled.
- **Dispose of `agent_standalone_embedded.py`** — already done (AH-120); unchanged.
- **Prod cutover go/no-go** — deploy of the 2.0 chat tree to production, gated on:
  AH-PRD-13 green in staging, this fix complete, the live-Gemini staging smoke PASS,
  and Billing/Chat parity confirmed on the search leaf.

### ~~In scope (original task-mode plan — invalid, retained for history)~~
- ~~Migrate the agent-as-tool registry/resolver to task-mode (`mode='task'` /
  `ctx.run_node`).~~ **Unworkable** — built-in grounding/code-exec tools cannot share
  their request with the injected `FinishTaskTool`/`transfer_to_agent` (400).
- ~~Coordinator/root reconciliation dispatching agent-as-tool as `mode='task'`.~~
  Reconciled instead as an isolated `AgentTool` in `root.tools`.

### Out of scope
- `strategy_agent` `AgentTool` usage (stays 1.34.1; retired via KG-PRD-05).
- The supervisor coordinator implementation itself (AH-PRD-05).
- New web-search capabilities — this is a billing/isolation fix, not a feature change. The user-visible web-search behaviour is unchanged.

---

## 3. Dependencies

| Dependency | Nature | Reference |
|---|---|---|
| **[AH-PRD-13](./AH-PRD-13-adk2-foundation.md)** | Hard — the chat tree must be on ADK 2.0 for `mode='task'` / `ctx.run_node` to exist. | This component |
| **[AH-98](https://linear.app/ken-e/issue/AH-98)** | The migrated surface — `agent_tool_registry.py`, `roster.py`, `source="agent"`, `agent.{name}` tool IDs, `create_google_search_agent()`. | PR #795 |
| **[AH-100](https://linear.app/ken-e/issue/AH-100)** | The per-turn root-`tools` hot-reload path that must dispatch agent-as-tool entries as task-mode. AH-100's mechanism is re-validated under 2.0 by AH-PRD-13 §5.3. | PR #805 |
| **AH-PRD-14** | Parity contracts (accumulator multi-task aggregation, parity fixtures) the migration is verified against. | [AH-PRD-14](./AH-PRD-14-supervisor-contract-preservation.md) |
| **GitHub `#3984`** | The open upstream bug that makes this migration necessary; track for closure (would simplify but does not block — task-mode is the validated path regardless). | `google/adk-python#3984` |

---

## 4. Data Contract

- No Firestore schema change. `agent_configs.tool_ids` continues to carry `agent.{name}` entries; what changes is how the **resolver materializes** them (task-mode sub-agent vs `AgentTool`) on 2.0.
- No `ChatResponse` / session-state change beyond what AH-PRD-14 defines.

---

## 5. Implementation Outline (re-planned — AH-121)

| Action | File | Note |
|---|---|---|
| Add | `app/adk/agents/agent_tool_billing.py` | `ContextVar` outer-turn id + off-state per-turn sink + `capture_agent_tool_usage` (after_model) + `drain_turn_billing`. Mirrors `tool_trace_context.py` (survives AgentTool's state deep-copy). Top-level funcs (cloudpickle-safe). |
| Modify | `app/adk/tools/agent_tools/google_search.py` | Add `create_google_search_agent_tool() -> AgentTool` (leaf named `google_search`, `after_model_callback=capture_agent_tool_usage`, marker comment). Register on the isolated lane (gated on the 2.0 chat tree). Keep `create_google_search_agent` byte-identical (strategy 1.34.x). |
| Modify | `app/adk/tools/agent_tools/numerical_analyst.py` | Same pattern: `create_numerical_analyst_agent_tool()`; register on the isolated lane. |
| Modify | `app/adk/tools/registry/agent_tool_registry.py` | Add the isolated lane: `register_isolated_agent_tool` (validates AgentTool + name + billing callback) / `get_isolated_agent_tool` / `resolve_isolated_agent_tools`. Suppress the task-mode "no factory" warning for isolated-lane entries. |
| Modify | `app/adk/agents/agent_factory/roster.py` | `isolated_agent_tools` param; filter by `agent.{name}`; route into `RosterResolution.tools`; count in the ≤30-tool cap. |
| Modify | `app/adk/agents/agent_factory/{hierarchy,root_tools_attacher,specialist_runtime}.py` | Resolve isolated tools and pass them through so they land in `.tools` (no `_TaskAgentTool` injection). |
| Modify | `app/adk/agents/chat_callbacks.py` | `chat_before_agent_callback` binds the outer turn id; `chat_after_agent_callback` drains the sink and folds captured tokens into `_build_turn_delta(extra=...)`. |
| Modify | `api/scripts/lint/check_no_agent_tool_in_chat_tree.py` | Allow-list the two isolation files + require the `isolation-required` marker; companion test asserts the billing callback. |
| Add | `app/adk/agents/scripts/smoke_google_search_live.py` | Live-Gemini staging engine-probe smoke (the mandatory pre-prod gate). |
| Extend | billing/guard/factory tests | Real-`extract_billable_tokens` parity (root + specialist); parallel additive-sink; guard allow-list; isolation-leaf billing-callback present. |

---

## 6. API Contract

No HTTP API change. Web-search tool selection (`tool_ids` containing `agent.google_search`) is unchanged from the user's perspective.

---

## 7. Acceptance Criteria (re-planned — AH-121)

1. On ADK 2.0, a turn where `agent.google_search` runs (as an isolated `AgentTool`)
   has its leaf `usage_metadata` captured by `capture_agent_tool_usage` and folded
   into the turn delta by `chat_after_agent_callback`; `extract_billable_tokens`
   counts its `gemini-2.5-flash` tokens with no double-count — verified on **both**
   root (AH-100) and specialist assignment — **merge blocker**.
2. **(Re-scoped.)** The `google_search` `AgentTool` `function_call`/`function_response`
   are visible in the outer trace, and the turn's billing reflects the leaf. The leaf's
   *inner* grounded-search spans are NOT recoverable under `AgentTool` (the same
   `#3984` event-drop) and are a documented known gap — the same class as the AH-88
   `generate_content` Weave-autopatch deferral. (The original "all grounded steps in
   the trace" is unachievable without task-mode and is dropped.)
3. AH-98's parallel-search AC #9 passes under the `AgentTool`/`asyncio.gather` model:
   multiple `google_search` calls in one turn each capture their tokens additively in
   the per-turn sink (no clobber across the `gather`-copied contexts).
4. **(Amended.)** No `AgentTool` is constructed in the chat-tree 2.0 build **except**
   the two sanctioned isolation leaves (`google_search`, `numerical_analyst`), which
   must carry the `isolation-required` marker; a companion test asserts each carries
   the `capture_agent_tool_usage` billing callback. Enforced by
   `check_no_agent_tool_in_chat_tree.py`.
5. `agent_standalone_embedded.py` is removed/excluded from the chat deploy (AH-120; unchanged).
6. Root/coordinator path: a hot-reloaded `agent.google_search` `tool_id` is dispatched
   as an isolated `AgentTool` in `root.tools` (not task-mode) and bills correctly.
7. **(New blocking precondition.)** A live-Gemini `google_search` smoke
   (`smoke_google_search_live.py`) passes on the **staging** engine — no `error_code`,
   a grounded answer, and the leaf tokens reaching the meter — **before** any prod
   re-deploy.
8. **Prod cutover gate:** AH-PRD-13 green in staging + ACs 1–7 green → documented
   go/no-go; 2.0 chat tree deployed to production with billing parity confirmed in the
   first 24h.

---

## 8. Test Plan

- **Integration (merge blockers):** search-sub-agent token-count parity on 2.0 (root + specialist); parallel-search AC #9 under `ctx.run_node`.
- **Regression guard:** grep-based no-`AgentTool`-in-chat-tree check wired into CI.
- **Trace:** search steps present in the committed fixture / live trace.
- **Cutover smoke:** post-deploy SSE curl + a real web-search turn in prod; 24h billing reconciliation (Weave-vs-meter drift < 0.5%).

---

## 9. Risks & Open Questions

| Risk | Mitigation |
|---|---|
| **Shipping 2.0 to prod before this lands** → billing under-counts every web-search turn | This PRD **is** the cutover gate (AC #7); AH-PRD-13 explicitly validates 2.0 with `agent.google_search` unassigned until this lands. |
| Task-mode dispatch changes web-search latency/behaviour | AC #1–3 assert behavioural parity; this is a mechanism swap, not a feature change. |
| `#3984` closes upstream mid-flight (AgentTool streaming fixed) | Would simplify but does not change the plan — task-mode is the validated path; re-evaluate only if upstream ships a supported fix. |
| Coordinator vs root tool-model ambiguity (AH-100) | Resolved in AC #6 + the AH-PRD-05 coordinator design; the reconciliation is owned here. |

**Open questions:**
- Should `source="agent"` tools always be `mode='task'`, or only when invoked in a multi-task turn? (Default: always task-mode on 2.0 — simplest, and AH-99 shows no downside for single-task.)
- Is there any non-`google_search` `source="agent"` tool planned before cutover? (If so, it inherits this migration automatically via the registry change.)

---

## 10. Reference

- `docs/spike-adk2-supervisor-orchestration-live.md` §9 (AH-99 carry-forward directive — the source of this PRD), §4 (probe-1/4 propagation evidence)
- [AH-98](https://linear.app/ken-e/issue/AH-98) (PR #795), [AH-100](https://linear.app/ken-e/issue/AH-100) (PR #805)
- [AH-PRD-13](./AH-PRD-13-adk2-foundation.md), [AH-PRD-14](./AH-PRD-14-supervisor-contract-preservation.md), [AH-PRD-05](./AH-PRD-05-multi-step-workflows.md)
- GitHub `google/adk-python#3984` (AgentTool event streaming — OPEN)

---

## 11. Linear issue breakdown

> **Re-plan (AH-121).** AH-114–120 (the task-mode migration) shipped but the cutover
> failed at the prod `google_search` 400. The re-plan replaces the task-mode mechanism
> with AgentTool isolation + billing capture. The original task-mode issues are
> retained for history (struck through); the re-plan issues below are what gets built.

### Re-plan issues (AgentTool isolation + billing — AH-121 follow-on)

| # | Issue | AC | Notes |
|---|---|---|---|
| R1 | Add `agent_tool_billing.py` (ContextVar + off-state sink + capture/drain) | 1, 3 | core billing primitive; mirrors `tool_trace_context.py` |
| R2 | Isolated AgentTool factories for `google_search` + `numerical_analyst` | 1, 4 | leaf + `after_model_callback`; keep strategy leaf byte-identical |
| R3 | Registry isolated lane + roster/attachers/hierarchy route into `.tools` | 1, 6 | `register_isolated_agent_tool` / `resolve_isolated_agent_tools` |
| R4 | Wire capture/drain into `chat_callbacks` (`_build_turn_delta(extra=...)`) | 1 | **merge blocker**; real `extract_billable_tokens`, root + specialist |
| R5 | Amend AC #4 no-AgentTool guard (allow-list + marker + billing-callback test) | 4 | regression guard |
| R6 | Live-Gemini staging smoke (`smoke_google_search_live.py`) + runbook §5 re-base | 7, 8 | the mandatory pre-prod gate |
| R7 | Re-deploy staging→prod after smoke PASS; 24h billing reconciliation | 8 | cutover gate |

### ~~Original task-mode issues (AH-114–120 — premise invalidated)~~

| # | Issue | AC | Notes |
|---|---|---|---|
| ~~1~~ | ~~Registry: emit `mode='task'` for `source="agent"` on 2.0~~ | ~~1, 4~~ | AH-114 — superseded by R3 |
| ~~2~~ | ~~Roster + `specialist_runtime`: resolve `agent.{name}` to task-mode leaves~~ | ~~1, 4~~ | AH-115 — superseded by R3 |
| ~~3~~ | ~~AH-100 root path: dispatch hot-reloaded agent-as-tool as task-mode~~ | ~~6~~ | AH-116 — superseded by R3 |
| ~~4~~ | ~~`agent.google_search` billing parity on 2.0~~ | ~~1~~ | AH-117 — superseded by R4 |
| ~~5~~ | ~~`agent.google_search` trace-step coverage on 2.0~~ | ~~2~~ | AH-118 — re-scoped (inner spans unrecoverable) |
| ~~6~~ | ~~Re-validate parallel-search under `ctx.run_node`~~ | ~~3~~ | AH-119 — superseded by R3 (`asyncio.gather`) |
| 7 | Remove/exclude `agent_standalone_embedded.py`; no-`AgentTool` CI guard | 4, 5 | AH-120 — guard **amended** by R5 (allow-list) |
| 8 | Prod cutover runbook + go/no-go + 24h reconciliation | 8 | AH-121 — runbook §5 re-based by R6 |
