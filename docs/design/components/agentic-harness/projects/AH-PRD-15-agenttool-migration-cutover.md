# AH-PRD-15 — AgentTool → Task-Mode Migration & ADK 2.0 Prod Cutover

**Status:** Draft (spec) — ADK 2.0 migration initiative (Phase 4)
**Owner team:** Core AI / Agent Platform (Agentic Harness)
**Blocked by:** [AH-PRD-13](./AH-PRD-13-adk2-foundation.md) (the chat tree must be on ADK 2.0). Coordinates with AH-PRD-05 (coordinator tool model) and AH-PRD-14 (parity contracts).
**Blocks:** **ADK 2.0 production cutover** — this PRD's completion is the cutover go/no-go gate.
**Release:** 1 — Foundation (ADK 2.0 migration initiative; owns the prod-cutover gate).
**Decision record:** [DESIGN-REVIEW-LOG Review 45](../../../DESIGN-REVIEW-LOG.md#review-45--adk-20-migration-initiative-structuring-strategy-agent-pin-sk-10-correction); origin: [AH-99](https://linear.app/ken-e/issue/AH-99) §9 carry-forward.

> **Why this is its own PRD.** [AH-98](https://linear.app/ken-e/issue/AH-98) shipped `agent.google_search` as an `AgentTool(agent=create_google_search_agent())` (`source="agent"`), and [AH-100](https://linear.app/ken-e/issue/AH-100) made it per-turn-assignable to the **root**. On ADK 2.0, GitHub `#3984` (OPEN) means `AgentTool.run_async` still **discards inner sub-agent events** — so the search sub-agent's `gemini-2.5-flash` tokens go **uncounted** and its grounded-search steps **vanish from traces**: the exact AH-75 billing/tracing defect, on the most critical agents. Adopting 2.0 (AH-PRD-13) without this migration ships a billing regression to prod. This PRD migrates the chat-tree agent-as-tool surface off the inner-Runner path and is the **prod-cutover gate**.

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

### In scope
- **Migrate the agent-as-tool registry/resolver to task-mode.** On ADK 2.0, `agent_tool_registry.py` + `roster.py` + `specialist_runtime` emit `source="agent"` entries as `mode='task'` sub-agents (invoked via `request_task_<name>` / `ctx.run_node`) instead of `AgentTool` instances, so inner events (incl. `usage_metadata`) reach the outer stream.
- **`agent.google_search` specifically** migrated and verified: its `gemini-2.5-flash` tokens are counted by `extract_billable_tokens` + `SessionTurnAccumulator`, and its grounded-search steps appear in the trace — on both the **root** (AH-100 path) and **specialist** assignment paths.
- **Re-validate AH-98 parallel-search AC #9** under ADK 2.0's concurrency model (`ctx.run_node` fan-out, not 1.x `handle_function_call_list_async` → `asyncio.gather`).
- **Coordinator/root tool reconciliation** (the AH-100 × supervisor tension): define how a `mode='chat'` coordinator's per-turn hot-reloaded `tool_ids` containing agent-as-tool entries are dispatched as `mode='task'` (rather than carried as `AgentTool` on the coordinator). Aligns with AH-PRD-05's "coordinator carries only ledger tools" model.
- **Dispose of `agent_standalone_embedded.py`** — confirm it is not deployed; remove it or exclude it from the 2.0 chat build so it does not reintroduce an `AgentTool`.
- **Prod cutover go/no-go** — the deploy of the 2.0 chat tree to production, gated on: AH-PRD-13 green in staging, this migration complete, and Billing/Chat/MER-E parity confirmed on the search sub-agent.

### Out of scope
- `strategy_agent` `AgentTool` usage (stays 1.34.1; retired via KG-PRD-05).
- The supervisor coordinator implementation itself (AH-PRD-05) — this PRD only supplies the agent-as-tool dispatch primitive it relies on.
- New web-search capabilities — this is a dispatch-mechanism migration, not a feature change. The user-visible web-search behaviour is unchanged.

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

## 5. Implementation Outline

| Action | File | Note |
|---|---|---|
| Modify | `app/adk/tools/registry/agent_tool_registry.py` | Emit `mode='task'` sub-agent (or `ctx.run_node` dispatch) for `source="agent"` on 2.0 |
| Modify | `app/adk/agents/agent_factory/roster.py` | Resolve `agent.{name}` entries to task-mode sub-agents in the roster |
| Modify | `app/adk/agents/agent_factory/specialist_runtime.py` | Construct agent-as-tool entries as `mode='task'` leaves |
| Modify | AH-100 root-tools reconcile callback | Dispatch hot-reloaded `agent.{name}` root entries as task-mode (not `AgentTool` on root) |
| Remove/Exclude | `app/adk/agent_standalone_embedded.py` | Legacy, not in chat deploy — remove or exclude from 2.0 build |
| Extend | parity + trace tests | Assert search sub-agent tokens counted + steps traced (root + specialist paths) |

---

## 6. API Contract

No HTTP API change. Web-search tool selection (`tool_ids` containing `agent.google_search`) is unchanged from the user's perspective.

---

## 7. Acceptance Criteria

1. On ADK 2.0, a turn where `agent.google_search` is invoked yields the search sub-agent's `usage_metadata` to the outer stream; `extract_billable_tokens` + `SessionTurnAccumulator` count its `gemini-2.5-flash` tokens — verified on **both** root (AH-100) and specialist assignment — **merge blocker**.
2. The search sub-agent's grounded-search steps appear in the Weave trace (no missing spans vs the intended shape).
3. AH-98's parallel-search AC #9 passes under `ctx.run_node` concurrency (not `AgentTool.run_async`).
4. No `AgentTool` instance is constructed anywhere in the **chat-tree** 2.0 build (registry/resolver/standalone) — enforced by a grep-based regression guard (mirrors the `check_artifact_register` lint pattern).
5. `agent_standalone_embedded.py` is removed or provably excluded from the chat deploy.
6. Coordinator path: a `mode='chat'` coordinator with a hot-reloaded `agent.google_search` `tool_id` dispatches it as `mode='task'` and bills correctly.
7. **Prod cutover gate:** AH-PRD-13 green in staging + ACs 1–6 green → documented go/no-go; 2.0 chat tree deployed to production with billing parity confirmed in the first 24h.

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

## 11. Linear issue breakdown (AH-98 follow-through scopes)

Suggested issues for the Linear project (8–12 range per CLAUDE.md). Each maps to a §7 AC.

| # | Issue | AC | Notes |
|---|---|---|---|
| 1 | Registry: emit `mode='task'` for `source="agent"` on 2.0 | 1, 4 | `agent_tool_registry.py` core change |
| 2 | Roster + `specialist_runtime`: resolve `agent.{name}` to task-mode leaves | 1, 4 | resolver path |
| 3 | AH-100 root path: dispatch hot-reloaded agent-as-tool as task-mode | 6 | coordinator/root reconciliation |
| 4 | `agent.google_search` billing parity on 2.0 (root + specialist) | 1 | **merge blocker**; uses AH-PRD-14 parity harness |
| 5 | `agent.google_search` trace-step coverage on 2.0 | 2 | search steps present in trace |
| 6 | Re-validate AH-98 parallel-search AC #9 under `ctx.run_node` | 3 | concurrency model swap |
| 7 | Remove/exclude `agent_standalone_embedded.py`; add no-`AgentTool` CI guard | 4, 5 | regression guard |
| 8 | Prod cutover runbook + go/no-go + 24h billing reconciliation | 7 | depends on AH-PRD-13 staging-green |
