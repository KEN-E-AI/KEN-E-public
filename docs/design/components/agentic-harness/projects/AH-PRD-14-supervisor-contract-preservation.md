# AH-PRD-14 — Supervisor Contract Preservation

**Status:** Draft (spec) — ADK 2.0 migration initiative (Phase 2)
**Owner team:** Core AI / Agent Platform (Agentic Harness) — co-owned with **Chat** and **MER-E**
**Blocked by:** none for the prep work (can proceed on `google-adk==1.34.1`); full validation of the new event shapes needs [AH-PRD-13](./AH-PRD-13-adk2-foundation.md) (2.0).
**Blocks:** [AH-PRD-05](./AH-PRD-05-multi-step-workflows.md) (supervisor) — the outer-stream contracts must be supervisor-ready before the coordinator ships.
**Release:** 1 — Foundation (ADK 2.0 migration initiative; most prep lands on 1.34.1 ahead of the unpin).
**Decision record:** [DESIGN-REVIEW-LOG Review 45](../../../DESIGN-REVIEW-LOG.md#review-45--adk-20-migration-initiative-structuring-strategy-agent-pin-sk-10-correction).

> **What this PRD is.** The Phase-2 "contract preservation" work from the [analysis memo](../../../adk2-supervisor-orchestration-analysis.md) §3.3 / §6 — make the four outer-stream consumers (Billing, Chat, MER-E, UI streaming) robust to the supervisor model's **multi-task, multi-author, fan-out** event stream *before* the coordinator (AH-PRD-05) ships. Most of it can land on 1.34.1; the 2.0-shaped event fields are validated once AH-PRD-13 lands.

---

## 1. Context

AH-99 confirmed task-mode `usage_metadata` reaches the outer `Runner.run_async` stream natively — so the supervisor model needs **no custom event bridge**. But the four consumers were written for the post-AH-75 **single-specialist, single-author** turn:

- **Billing** (`shared/token_accounting.py::extract_billable_tokens`) reads `usage_metadata` per event — fine, but the per-turn **accumulator** must sum across *multiple* task specialists in one turn.
- **Chat** (`SessionTurnAccumulator`, `chat_after_agent_callback._build_turn_delta`) aggregates per `invocation_id` — must handle multiple task-delegation sub-runs and fan-out branches under one outer invocation.
- **UI streaming** (`chat.py` SSE parser) assumes a single logical author sequence — fan-out produces **interleaved multi-author** partial events.
- **MER-E** (`docs/trace-structure-spec.md` + [`AH-PRD-05-trace-contract-diff.md`](./AH-PRD-05-trace-contract-diff.md)) consumes the span tree — gains `task_delegation` / `fanout` spans.

Plus two enabling pieces the coordinator depends on: the widened **`TodoItem`** ledger schema (Chat-owned) and a seeded **synthesizer** `agent_config`.

This PRD hardens those contracts so AH-PRD-05 is a pure orchestration change, not a contracts-and-orchestration change.

---

## 2. Scope

### In scope
- **`TodoItem` schema widening (Chat-owned).** Add `assignee`, `query`, `criteria`, `depends_on`, `result_key`, and the 5-state `status` enum (`pending | dispatched | awaiting_review | completed | failed`) to `api/src/kene_api/models/chat.py` and the ADK-side `todo_tools.py`. **Additive, backward-compatible** — the `set_todo_list` / `update_todo_list` user surface is unchanged. (Schema already specced in AH-PRD-05 §4.1 + `chat/README.md`.) Lands on 1.34.1.
- **Per-turn accumulator multi-task aggregation.** `SessionTurnAccumulator` + `chat_after_agent_callback._build_turn_delta` correctly sum tokens / tool-call / message counts across **multiple task-delegation sub-runs and fan-out branches** sharing one outer `invocation_id`. Tolerate the 2.0 event fields (`node_info`, `isolation_scope`) without dropping events.
- **SSE author-tagging for fan-out.** `chat.py` SSE parser tags interleaved partial events by author so the UI can render concurrent fan-out progress (not "silent then dump"). Define the SSE event contract for multi-author turns.
- **Trace contract finalization.** Finalize `task_delegation` / `fanout` span attributes in [`AH-PRD-05-trace-contract-diff.md`](./AH-PRD-05-trace-contract-diff.md) and commit the canonical staging fixture `app/adk/tracking/tests/fixtures/supervisor_orchestration_trace.json`. **MER-E sign-off on extractor readiness is a merge blocker** for AH-PRD-05's first implementation PR (carried here so it precedes orchestration).
- **Synthesizer `agent_config`.** Seed a default synthesizer specialist config (`include_contents='none'`, template-injection of upstream `result_key` values) so fan-out fan-in has a default executor.
- **Parity tests extended.** Extend the Chat/Billing parity suite with a multi-task fixture (≥2 task specialists in one turn) asserting aggregate equality vs the sum of single-specialist baselines.

### Out of scope
- The coordinator / `mode='task'` / `ctx.run_node` orchestration itself — **AH-PRD-05**.
- The `google-adk` 2.0 unpin + framework migration — **AH-PRD-13**.
- AgentTool → task-mode migration — **AH-PRD-15**.
- Any new user-facing TODO UI (read-only `TodoListsPanel` already shipped in CH-PRD-05).

---

## 3. Dependencies

| Dependency | Nature | Reference |
|---|---|---|
| **Chat** (CH-PRD-05) | Owns `TodoItem` / `TodoList` schema + the `set_todo_list` / `update_todo_list` tools + `SessionTurnAccumulator`. Schema widening + accumulator changes land here, Chat-coordinated. | `docs/design/components/chat/README.md` |
| **Billing** (BL-PRD-02) | `extract_billable_tokens` + the parity test are Billing-owned; the multi-task parity fixture extends BL's contract. | `shared/token_accounting.py` |
| **MER-E** | Consumes the trace contract; must sign off on `task_delegation` / `fanout` extractors against the committed fixture. | [`AH-PRD-05-trace-contract-diff.md`](./AH-PRD-05-trace-contract-diff.md) |
| **[AH-PRD-13](./AH-PRD-13-adk2-foundation.md)** | Soft — the prep lands on 1.34.1, but the 2.0 event fields (`node_info`/`isolation_scope`) are only exercised end-to-end once the runtime is on 2.0. | This component |

---

## 4. Data Contract

- **`TodoItem`** (widened — additive): `assignee: str | None`, `query: str | None`, `criteria: str | None`, `depends_on: list[str]`, `result_key: str | None`, `status: Literal["pending","dispatched","awaiting_review","completed","failed"]`. Source of truth: `api/src/kene_api/models/chat.py`, mirrored in `todo_tools.py`.
- **Session-state keys** (per AH-PRD-05 §4.2): `response_artifacts` (AH-PRD-04), `<result_key>` / `<result_key>_artifacts`, `pending_supervisor_tasks`. No new collections.
- **SSE multi-author event contract:** each streamed partial carries an `author` discriminator; the parser groups by author for concurrent rendering. (Documented in `chat/README.md`.)
- **Trace spans:** `task_delegation` (attrs: `task_id`, `assignee`, `query`, `criteria`, `task_status`, `cache_hit`) and `fanout` (attrs: `task_ids`, `branch_count`, `all_succeeded`) per the contract diff.

---

## 5. Implementation Outline

| Action | File | Note |
|---|---|---|
| Modify | `api/src/kene_api/models/chat.py` | Widen `TodoItem` (additive) |
| Modify | `app/adk/tools/function_tools/todo_tools.py` | Mirror the widened schema; tools still accept the legacy shape |
| Modify | `api/src/kene_api/chat/accumulator.py` | Multi-task / fan-out aggregation under one `invocation_id`; tolerate `node_info`/`isolation_scope` |
| Modify | `app/adk/agents/chat_callbacks.py` (`_build_turn_delta`) | Same multi-author aggregation on the callback side |
| Modify | `api/src/kene_api/routers/chat.py` (SSE parser) | Author-tagged interleaved streaming for fan-out |
| Create | `app/adk/tracking/tests/fixtures/supervisor_orchestration_trace.json` | Canonical MER-E fixture |
| Modify | `docs/design/components/agentic-harness/projects/AH-PRD-05-trace-contract-diff.md` | Finalize attributes; flip status to "MER-E signed off" on completion |
| Seed | synthesizer `agent_config` (Firestore) | Default fan-in executor |
| Extend | Chat/Billing parity suite | Multi-task fixture |

---

## 6. API Contract

No new HTTP endpoints. `ChatResponse` unchanged. The SSE stream gains an `author` field on partial events (additive; existing single-author consumers ignore it).

---

## 7. Acceptance Criteria

1. `TodoItem` carries the six new fields; existing `set_todo_list` / `update_todo_list` round-trips and the read-only `TodoListsPanel` are unaffected (backward-compat test).
2. Given a synthetic multi-task turn (≥2 task specialists, one fan-out group), `SessionTurnAccumulator` and `_build_turn_delta` produce aggregate token / tool-call / message counts equal to the sum of the per-specialist baselines — **merge blocker**.
3. The SSE stream emits author-tagged partials for a fan-out turn; a UI integration test renders ≥2 concurrent authors without loss or interleave corruption.
4. `supervisor_orchestration_trace.json` is committed; MER-E extractors recognize `task_delegation` + `fanout` spans against it; **MER-E sign-off recorded**.
5. Synthesizer `agent_config` seeded in dev; a fan-in step produces a synthesis referencing upstream `result_key` values.
6. Multi-task Chat/Billing parity test passes (on 1.34.1 with simulated events; re-confirmed on 2.0 once AH-PRD-13 lands).

---

## 8. Test Plan

- **Unit:** `TodoItem` (de)serialization incl. legacy shape; accumulator aggregation across multiple sub-runs; SSE author grouping.
- **Integration:** multi-task parity fixture (merge blocker); synthesizer template-injection.
- **Contract:** MER-E extractor run against the committed fixture.

---

## 9. Risks & Open Questions

| Risk | Mitigation |
|---|---|
| Accumulator double-counts or drops events under multi-author interleave | Aggregation keyed by `(invocation_id, event identity)`; parity fixture is the merge gate. |
| SSE author-tagging breaks existing single-author clients | `author` is additive; existing clients ignore unknown fields; UI test covers both paths. |
| 2.0 event fields not fully exercisable on 1.34.1 | Prep + unit-test on 1.34.1 with simulated 2.0 events; re-confirm end-to-end once AH-PRD-13 lands. |
| MER-E extractor work lags | Sign-off is an explicit merge blocker on AH-PRD-05's first PR; the fixture is committed here so MER-E can start early. |

**Open questions:**
- Does the accumulator key on `invocation_id` alone, or `(invocation_id, node_path)` for fan-out branch attribution? (Resolve against the AH-99 probe-4 event shape.)
- Synthesizer: one shared default config, or per-domain synthesizers? (Default to one; revisit if synthesis quality varies by domain.)

---

## 10. Reference

- `docs/design/adk2-supervisor-orchestration-analysis.md` §3.3 (outer-stream contracts), §6 Phase 2
- `docs/spike-adk2-supervisor-orchestration-live.md` §4 (probe-1/4 event shapes)
- [AH-PRD-05](./AH-PRD-05-multi-step-workflows.md) (consumer), [AH-PRD-13](./AH-PRD-13-adk2-foundation.md) (runtime), [AH-PRD-05-trace-contract-diff.md](./AH-PRD-05-trace-contract-diff.md)
- `docs/design/components/chat/README.md` (TodoItem + accumulator ownership), `shared/token_accounting.py` (Billing)
