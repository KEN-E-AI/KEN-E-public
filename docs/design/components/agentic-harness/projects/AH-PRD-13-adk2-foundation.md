# AH-PRD-13 — ADK 2.0 Migration Foundation

**Status:** Draft (spec) — gating PRD for the ADK 2.0 migration initiative
**Owner team:** Core AI / Agent Platform (Agentic Harness)
**Blocked by:** none (this is the initiative's gate). Empirical basis: [AH-96](https://linear.app/ken-e/issue/AH-96) + [AH-99](https://linear.app/ken-e/issue/AH-99) (GO-confirmed live validation — `docs/spike-adk2-supervisor-orchestration-live.md`).
**Blocks:** [AH-PRD-05](./AH-PRD-05-multi-step-workflows.md) (supervisor orchestration), AH-PRD-15 (AgentTool → task-mode migration). Soft-parallel: AH-PRD-14 (contract preservation — can proceed on 1.34.1).
**Release:** 1 — Foundation (initiative gate; sequences after AH-PRD-09 ships). See [PROJECT-PLANNER](../../PROJECT-PLANNER.md).
**Decision record:** [DESIGN-REVIEW-LOG Review 44](../../../DESIGN-REVIEW-LOG.md#review-44--ah-97-supervisor-orchestration-adoption-adk-20) (adoption) + Review 45 (this initiative + strategy-agent pin).

> **What this PRD is.** The narrow, gating step that makes the **existing** KEN-E chat runtime run correctly on `google-adk==2.0.0` **with no behaviour change**, so the supervisor model (AH-PRD-05) and the rest of the initiative have a real 2.0 base. It is *not* the supervisor feature, *not* the contract-preservation enhancements, and *not* the AgentTool migration — those are AH-PRD-05 / AH-PRD-14 / AH-PRD-15.

---

## 1. Context

ADK 2.0 went GA 2026-05-19. [AH-96](https://linear.app/ken-e/issue/AH-96) (static) and [AH-99](https://linear.app/ken-e/issue/AH-99) (live) confirmed the supervisor-orchestration model works on 2.0 and that inner task-mode `usage_metadata` reaches the outer `Runner.run_async` stream natively (Billing/Chat/MER-E parity holds). But **adopting any 2.0 primitive requires the whole chat runtime to move 1.34.1 → 2.0.0** — a *major*-version migration (`BaseAgent` now subclasses `BaseNode`; the runtime is a graph engine), not a pin bump. This PRD owns that migration.

**ADK footprint recon (2026-06-02, chat tree + `api/`):**

| Surface | Finding | Migration impact |
|---|---|---|
| `_run_async_impl` / `_run_live_impl` overrides | **0** | ✅ The highest-risk 2.0 break (overrides silently ignored under `BaseNode`) does not apply |
| Custom agent subclasses | **0** | ✅ Standard `LlmAgent`/`LoopAgent` via Firestore config — nothing to port |
| `session.events.append` / `enqueue_event` | **1** (`app/adk/agents/utils/supervisor_utils.py:148`) | Convert to a framework-managed yield |
| Callback-bearing files | **23** | Re-validate `before/after_(agent|tool|model)_callback` signatures + semantics on 2.0 |
| `except Exception` / `except BaseException` (`app/adk`) | **~307** (most in `strategy_agent`/tracking) | Triage only those **in chat-tree tool bodies** (broad excepts disable 2.0 auto-retry / can trap `NodeInterruptedError`) |
| `AgentTool(...)` sites | **20** (`agent.google_search`, `strategy_agent`) | Chat-tree AgentTool (`agent.google_search`) is a cutover blocker (see §3 / §9); `strategy_agent` stays on 1.34.1 |
| Deploy trees | **3** (`deploy_ken_e.py`, `deploy_with_sys_version.py`, `deploy_packaging.py`) | Decouple by ADK major (see below) |
| Weave / `safe_weave_op` files | **42** | Re-validate tracing survives the 2.0 event shape (`node_info`/`isolation_scope`) |

**Strategy-agent decision (Review 45).** `app/adk/agents/strategy_agent/` (≈45-file account-creation subsystem, its own `deploy_with_sys_version.py` tree, heavy `AgentTool` use) **stays pinned to ADK 1.34.x** and is removed in a later release (tracker TBD); [KG-PRD-05](../../knowledge-graph/README.md) begins the knowledge-graph-integration migration by refactoring its graph-write path but does **not** remove the agents. It is **out of scope** for the 2.0 migration. Consequently this PRD migrates only the **chat tree** (`deploy_ken_e.py`), and the two deploy trees **decouple by ADK major version**.

---

## 2. Scope

### In scope
- **Phase 0 (de-risking spike, ~few days):** stand up the chat tree on `google-adk==2.0.0` in an isolated dev workspace, deploy a **real 2.0 agent** to the dev Agent Engine, and verify the Chat/Billing parity suite + a **sandbox-attached specialist** + Weave traces round-trip — converting the two remaining unknowns (sandbox-on-2.0, live-deploy session/trace shape) to facts before the full migration is committed. Mirrors the AH-96/AH-99 discipline.
- **Pin bump (chat tree):** `google-adk` 1.34.1 → 2.0.0 in `pyproject.toml`, `api/pyproject.toml`, `app/adk/pyproject.toml`, and `app/adk/requirements.txt`; regenerate `uv.lock`. (Note: the 1.27.5 → 1.34.1 bump and the `requirements.txt` alignment were already done by AH-96 / PR #816 — this PRD takes it to 2.0.0.)
- **Deploy-tree decoupling:** chat tree (`deploy_ken_e.py`) → 2.0.0; strategy-supervisor tree (`deploy_with_sys_version.py`) stays 1.34.1. Audit and guard against cross-package `app.adk.*` imports that would force both trees to the same major (the two-deploy-trees packaging hazard; PR #817 recently packaged `app/adk` into the strategy tree — re-confirm isolation).
- **Breaking-change audit + remediation (chat tree):**
  - `BaseAgent → BaseNode`: confirm every chat-tree agent constructs and runs; fix any constructor signature drift. (Recon: no execution-method overrides to port.)
  - Remove the single `session.events.append` (`supervisor_utils.py:148`).
  - Narrow broad `except` blocks **inside chat-tree tool bodies** so they don't mask failures from 2.0 auto-retry or trap `NodeInterruptedError`.
  - Re-validate the 23 callback files on 2.0 — especially the per-turn reconciliation callbacks: `attach_specialists_before_agent_callback`, the AH-102 `sub_agents` fingerprint, and the **AH-100** root-`tools` reconcile (see §5.3).
- **Managed-session compatibility:** confirm `VertexAiSessionService` accepts 2.0 events (`node_info`/`isolation_scope`) end-to-end against a **deployed 2.0 chat agent** on dev Agent Engine (AH-99 probe-5 confirmed the round-trip on stored events; re-confirm against a live 2.0 deploy), and the `chat_sessions` Firestore mirror is unaffected.
- **Sandbox / code-exec compatibility:** confirm the `AgentEngineSandboxCodeExecutor` + `SandboxPool` (SK-PRD-02) execute code on ADK 2.0 — the SK-PRD-00 spike basis was 1.x. A sandbox-attached specialist must run end-to-end on 2.0. (AH-PRD-11 residency and SK-PRD-04 agent-builder both depend on this.)
- **Tracing:** confirm Weave / `safe_weave_op` spans survive the 2.0 event shape; document any span-shape deltas for MER-E (the contract diff lives in AH-PRD-14 / `AH-PRD-05-trace-contract-diff.md`). Carry forward the known weave-autopatch fragility.
- **Parity gate:** Chat/Billing parity tests + the AH-PRD-09 `transfer_to_agent` trace fixture pass on 2.0 with **current single-specialist behaviour**.
- **Deploy + smoke-test** the chat tree on 2.0 to **dev → staging**.

### Out of scope
- Supervisor-orchestration features — coordinator, `mode='task'`, `ctx.run_node` fan-out (**AH-PRD-05**).
- Contract-preservation enhancements — sub-call token capture, `chat.py` SSE author-tagging, `TodoItem` widening, synthesizer config (**AH-PRD-14**).
- `agent.google_search` `AgentTool` → task-mode migration (**AH-PRD-15**) — but **prod cutover is gated on it** (§3, §9).
- Migrating `strategy_agent` to 2.0 — stays 1.34.1; removed in a later release (tracker TBD; KG-PRD-05 refactors its write path but does not remove it).
- **Production cutover** — a separate go/no-go after AH-PRD-15 lands.

---

## 3. Dependencies

| Dependency | Nature | Reference |
|---|---|---|
| **AH-96 / AH-99 spikes** | Empirical GO basis (task-mode + dynamic-graph propagation, session round-trip, LoopAgent). | `docs/spike-adk2-supervisor-orchestration-live.md` |
| **AH-PRD-15 (AgentTool → task-mode migration)** | **Hard prerequisite for *prod cutover*, not for dev/staging validation.** The chat tree exposes `agent.google_search` as an `AgentTool` (AH-98), now per-turn-assignable to the root (AH-100). Under GitHub `#3984` (still OPEN) the `AgentTool.run_async` path drops inner events on 2.0 — the search sub-agent's tokens would go uncounted and its steps would vanish from traces (the AH-75 defect). Foundation validates 2.0 with `agent.google_search` **unassigned/disabled**; prod cannot cut over until AH-PRD-15 migrates it. | [AH-98](https://linear.app/ken-e/issue/AH-98), [AH-100](https://linear.app/ken-e/issue/AH-100), `#3984` |
| **MER-E / AH-PRD-14 trace contract** | Foundation preserves the current single-specialist span shape, so day-0 traces are unchanged; coordination is only needed for span-shape deltas surfaced by the audit. | [`AH-PRD-05-trace-contract-diff.md`](./AH-PRD-05-trace-contract-diff.md) |
| **Deploy infra** | The chat + strategy deploy trees and `requirements.txt` packaging must decouple cleanly by ADK major. | `app/adk/deploy_ken_e.py`, `app/adk/deploy_with_sys_version.py` |

---

## 4. Data Contract

- **No new Firestore collections; no schema change.** ADK 2.0 events gain `node_info` / `isolation_scope` (additive). AH-99 probe-5 confirmed the managed session backend and the `chat_sessions` mirror persist them without migration.
- **Dependency pin:** `google-adk` 1.34.1 → 2.0.0 (chat tree only). Strategy tree stays 1.34.1.

---

## 5. Implementation Outline

### 5.1 File inventory
| Action | File | Note |
|---|---|---|
| Modify | `pyproject.toml`, `api/pyproject.toml`, `app/adk/pyproject.toml` | `google-adk==2.0.0` |
| Modify | `app/adk/requirements.txt` | `google-adk==2.0.0` (chat-tree deploy pin — keep aligned to avoid the requirements/lockfile skew that breaks Agent Engine deploys) |
| Regenerate | `uv.lock` | `uv sync` |
| Modify | `app/adk/agents/utils/supervisor_utils.py` | Remove the `events.append` (line ~148) → framework-managed yield |
| Audit/Modify | chat-tree tool bodies with broad `except` | Narrow to specific exceptions; never `except BaseException` around node calls |
| Validate | 23 callback files | Confirm 2.0 signatures/semantics; expect few edits |
| Validate/Modify | `app/adk/agents/agent_factory/sub_agent_attacher.py`, AH-100 root-tools reconcile callback | Per-turn mutation must hold on 2.0 (§5.3). **AH-104 found the concrete fix:** apply the `AlwaysTrueSubAgentList` shim + in-place `_reconcile` + populated-guard, and re-add the parity-test Mode B hooks — exact diff in `docs/spike-ah104-deploy-sandbox-weave.md` §3.2.1. Verify under a 2.0 venv (parity test `total_billable=1430` for Mode B). |
| Modify | `app/adk/deploy_with_sys_version.py` (+ packaging) | Pin/guard strategy tree at 1.34.1; isolate from chat-tree 2.0 deps |

### 5.2 Deploy-tree decoupling
Audit every cross-package `app.adk.*` import shared between the chat tree and the strategy tree. Any module imported by both must be ADK-major-agnostic, or be duplicated/forked so the strategy tree can stay on 1.34.1 while the chat tree moves to 2.0.0. Add a smoke check that each tree imports cleanly under its own pinned major.

### 5.3 AH-100 re-validation (embedded evaluation — see §9 of the AH-100 issue)
AH-100 added a `before_agent_callback` that mutates **`root.tools`** per turn (hot-reloading `ken_e_chatbot.tool_ids`), mirroring how `sub_agent_attacher` reconciles `root.sub_agents`. Its correctness rests on a **1.x-specific guarantee**: *"ADK recomputes `canonical_tools` per invocation (cached per-invocation since 1.26); the before-agent callback runs at invocation start, so a `root.tools` mutation is picked up the same turn."* Under 2.0's `BaseNode`/graph engine, node tool-binding may differ. **This PRD must probe it** (a runnable assertion analogous to AH-96/99: edit `root.tools` in a `before_agent_callback`, assert the tool is honoured on the *same* invocation on 2.0). If it does not hold, implement AH-100's documented fallback (a toolset that re-resolves per turn, or rebuild/swap the root agent on config change). The sibling per-turn callbacks AH-101 (security tests) and AH-102 (`sub_agents` fingerprint) are in the same callback family and are covered by the §2 callback re-validation.

> **AH-100 × supervisor design.** AH-98/AH-100 let the **root** carry `agent.google_search` (an `AgentTool`). AH-PRD-05's coordinator design states the `mode='chat'` coordinator carries only ledger tools. The reconciliation — *does the coordinator hot-reload root `tool_ids`, and if so how do agent-as-tool entries become `mode='task'`?* — is owned by **AH-PRD-15** (migration) and noted forward in AH-PRD-05 §2. Foundation only needs the mechanism to keep working; the AgentTool *correctness* on 2.0 is AH-PRD-15.

---

## 6. API Contract

No HTTP API change. `ChatResponse` and all chat endpoints are unchanged.

---

## 7. Acceptance Criteria

1. `google-adk==2.0.0` pinned in the chat tree (root + `api/` + `app/adk/` pyproject **and** `app/adk/requirements.txt`); `uv.lock` regenerated; `make lint` + `make test` green.
2. Strategy-supervisor deploy tree remains pinned `1.34.1`, deploys green, and has **no cross-major import coupling** with the chat tree (guard test passes).
3. Chat/Billing parity tests pass on 2.0 (single-specialist `transfer_to_agent` path) — **merge blocker**.
4. AH-PRD-09 `transfer_to_agent` trace fixture passes on 2.0.
5. **AH-100:** a runnable test confirms a per-turn `root.tools` mutation in `before_agent_callback` is honoured **on the same invocation** on 2.0 — or the fallback is implemented and tested.
6. The single `session.events.append` is removed; enumerated broad `except` blocks in chat-tree tool bodies are narrowed.
7. `VertexAiSessionService` round-trip + `chat_sessions` mirror verified against a **deployed 2.0 chat agent** on dev.
8. Chat tree deploys + smoke-tests green on 2.0 in **dev → staging** (engine probe / `API_TEST_BYPASS_TOKEN` SSE curl per the deploy runbook); a sandbox-attached specialist executes code on 2.0 (`AgentEngineSandboxCodeExecutor` + `SandboxPool`).
9. Weave traces present on 2.0 with no regression vs the 1.34.1 baseline; any span-shape deltas documented for MER-E.

---

## 8. Test Plan

- **Unit/Integration:** port the AH-99 probe assertions (token propagation, session round-trip, LoopAgent) into CI on 2.0; Chat/Billing parity (merge blocker); the AH-100 same-turn tool-mutation assertion.
- **Deploy smoke:** deploy the 2.0 chat tree to dev; verify reasoning via the engine probe and an SSE curl; round-trip a session.
- **Regression:** the existing chat-tree test suite passes on 2.0; the strategy tree suite passes on 1.34.1.

---

## 9. Risks & Open Questions

| Risk | Mitigation |
|---|---|
| **`agent.google_search` AgentTool regresses billing/traces on 2.0** (`#3984` open) | Validate Foundation with `agent.google_search` **unassigned**; **gate prod cutover on AH-PRD-15**. Document the coupling in PROJECT-PLANNER. |
| **AH-100 per-turn `root.tools` mutation may not hold under the graph engine** | Probe first (§5.3); if it fails, implement the re-resolving-toolset / agent-swap fallback. |
| **Deploy-tree coupling** forces both trees to one ADK major | §5.2 cross-package import audit + per-tree import smoke check. |
| **Weave autopatch fragility** under the 2.0 event shape | Re-validate; the `google.genai` LLM-call span may remain absent (known carry-forward) — record, don't block. |
| **`except`-triage scope balloons** (~307 occurrences) | Scope strictly to chat-tree **tool-body** excepts; `strategy_agent` excepts are out of scope (stays 1.34.1). |
| **2.0 behavioural drift not caught by the spike** (event order/author) | Parity tests feed real `extract_billable_tokens` + `SessionTurnAccumulator`; any drift surfaces as a parity failure. |

**Open questions:**
- Does ADK 2.0 honour a `before_agent_callback` `root.tools` mutation same-turn? (AC #5 probe answers this.)
- Are any chat-tree modules imported by the strategy tree such that decoupling requires a fork? (§5.2 audit answers this.)

---

## 10. Reference

- `docs/spike-adk2-supervisor-orchestration.md` (AH-96) + `docs/spike-adk2-supervisor-orchestration-live.md` (AH-99)
- `docs/spike-ah104-deploy-sandbox-weave.md` (AH-104 Phase 0 de-risking spike — deploy + sandbox + Weave go/no-go; gates AH-105)
- `docs/design/adk2-supervisor-orchestration-analysis.md` (decision memo §4.4 migration cost, §6 phased plan)
- [DESIGN-REVIEW-LOG Review 44](../../../DESIGN-REVIEW-LOG.md#review-44--ah-97-supervisor-orchestration-adoption-adk-20) + Review 45
- [AH-PRD-05](./AH-PRD-05-multi-step-workflows.md) (supervisor — the consumer of this foundation), [AH-PRD-09 §4.6](./AH-PRD-09-per-turn-dispatch.md) (dispatch + AH-75 event-loss evidence)
- [mcp-architecture.md § ADK 2.0 Compatibility](../mcp-architecture.md#adk-20-compatibility)
- GitHub `google/adk-python#3984` (AgentTool event-streaming — still OPEN)
