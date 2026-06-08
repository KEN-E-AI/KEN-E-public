# AH-PRD-05 Trace Contract Diff — Supervisor-Orchestration (MER-E Coordination)

**Document type:** Contract diff (companion to the authoritative spec)
**Authoritative spec:** [`docs/trace-structure-spec.md`](../../../../trace-structure-spec.md)
**Issue:** AH-97 · Wave 5 — Trace contract for supervisor-orchestration
**Status:** Ready for MER-E review
**ADK 2.0 gate:** Implementation requires ADK 2.0 — the unpin + breaking-change migration is owned by the ADK 2.0 Foundation PRD ([AH-PRD-13](./AH-PRD-13-adk2-foundation.md)). This diff documents the **target span shape** — no live traces are emitted in the current R1 runtime. MER-E should prepare extractors now so they are ready when implementation PRDs land.

---

## §1 Purpose

AH-PRD-05 (Multi-Step Workflow Orchestration) is rewritten as the ADK 2.0 supervisor-orchestration spec (AH-97, 2026-06-01). This document records the span-shape change so MER-E can update extractors before any AH-PRD-05 implementation PR merges.

The prior AH-PRD-05 banner said "do NOT ship the inner-Runner shape." The new shape — coordinator + `mode='task'` specialists + `ctx.run_node` fan-out — is structurally different from both (a) the old `execute_workflow` inner-Runner anti-pattern and (b) the AH-PRD-09 post-AH-75 `transfer_to_agent` single-specialist shape.

---

## §2 Before / After Span Hierarchy

### 2.1 Single-specialist turn (unchanged from post-AH-75)

```
KEN-E root agent invocation (root span)
└── LLM call(s)
└── transfer_to_agent → specialist sub-agent run
    └── (optional) LoopAgent iterations
```

This path is **unchanged** by AH-PRD-05. AH-PRD-09 `transfer_to_agent` for single-specialist turns continues to be the R1 dispatch surface.

**ADK 2.0 verification (AH-113):** Verified on `google-adk==2.0.0` — no span-name additions, no span-name removals, no attribute-shape changes versus the post-AH-75 1.34.1 baseline. The emitter (`app/adk/tracking/callbacks.py` — `weave_before/after_agent_callback`) does not read `Event.node_info` or `Event.isolation_scope`, so the 2.0 event-shape additions leave the single-specialist span tree intact. Reference: `docs/runs/AH-113-adk2-weave-verification.md` §5 (operator-executed 2026-06-06 against the canonical dev 2.0 engine `5957383247464759296`) + offline regression suite passes on 2.0 (AH-113 Wave 1 — `app/adk/tracking/tests/` green in PR CI).

**`google.genai` LLM-call autopatch — carry-forward for MER-E (AH-113):** The Weave `google.genai` LLM-call span (`google.genai.generate_content` or similar) may be **absent** from traces in both ADK 1.34.1 and 2.0.0 due to a known Weave autopatch fragility — the integration does not always register. This was confirmed on 2.0 during AH-113 (`probe-10` Weave-check: `google_genai_autopatch=False`, autopatch registry empty) and is a **pre-existing condition, not a 2.0 regression**. **MER-E extractors must treat the per-LLM-call `google.genai` span as optional** and not depend on its presence for quality scoring. Full detail: `docs/trace-structure-spec.md` (Weave autopatch carry-forward note) + AH-PRD-13 §9. If the autopatch state ever flips to present (registered) without the span appearing in the UI, that *would* be a genuine 2.0 change worth a follow-up.

### 2.2 Supervisor-orchestrated multi-task turn (new — AH-PRD-05 target)

```
KEN-E root agent invocation (root span)
└── LLM call(s)  [coordinator — mode='chat']
└── task_delegation: {task_id}    ← one span per TODO-ledger task dispatched
    └── mode='task' specialist run
        ├── LLM call(s) + tool calls
        └── (optional) LoopAgent review iterations
            ├── worker LLM call(s)
            └── reviewer LLM call(s)
```

For parallel fan-out (`ctx.run_node` + `asyncio.gather`):

```
KEN-E root agent invocation (root span)
└── LLM call(s)  [coordinator]
└── fanout: {task_ids}               ← single fan-out span covering the parallel group
    ├── task_delegation: {task_id_A}  ← per-branch task span
    │   └── mode='task' specialist run
    └── task_delegation: {task_id_B}
        └── mode='task' specialist run
└── task_delegation: {task_id}       ← synthesis step (depends_on both fan-out result keys;
    └── mode='task' specialist run      specialist query references upstream result_key values)
```

**Note on the synthesis step:** the synthesis span is a standard `task_delegation` (not a distinct `synthesis`-named span type) — §3.1 attribute table applies. It is distinguished from other `task_delegation` spans by its `query`/`criteria` referencing upstream `<result_key>` template values injected by the coordinator.

---

## §3 Span-by-Span Attribute Table

### 3.1 `task_delegation` span (new)

| Attribute | Type | Source | Notes |
|-----------|------|--------|-------|
| `task_id` | `str` | TODO ledger `item_id` | Matches the `TodoItem.item_id` in session state |
| `assignee` | `str` | `TodoItem.assignee` | Specialist doc_id (e.g., `google_analytics_specialist`) |
| `query` | `str` | `TodoItem.query` | Task query string passed to the specialist |
| `criteria` | `str` | `TodoItem.criteria` | Acceptance criteria for the LoopAgent wrapper (empty = single-pass) |
| `task_status` | `str` | Set at completion | `completed` / `failed` |
| `cache_hit` | `bool` | `specialist_runtime.resolve_agent_with_hit` | True when LRU cache served the specialist |
| `node_path` | `str` | ADK 2.0 event stream (probe-1 / probe-4 evidence) | Hierarchical path of the ADK node that produced the inner events. Task-mode calls nest under the coordinator (e.g., `coordinator@1/task_specialist@adk-30c59a97-…`). Fan-out branches are rooted at the dispatched agent (e.g., `specialist_a@1`). Downstream consumers (e.g., `SessionTurnAccumulator` — see AH-123) **SHOULD** key on `(invocation_id, node_path)` for branch attribution in fan-out turns. |

### 3.2 `fanout` span (new, when `ctx.run_node` is used)

| Attribute | Type | Source | Notes |
|-----------|------|--------|-------|
| `task_ids` | `list[str]` | Fan-out branch task IDs | Identifies which TODO items ran in parallel |
| `branch_count` | `int` | Len of parallel group | |
| `all_succeeded` | `bool` | Set after gather completes | |
| `node_path` | `str` | ADK 2.0 event stream (probe-4 evidence) | Path of the fan-out coordinator node (e.g., `coordinator@1`). Each child `task_delegation` carries its own `node_path` reflecting the branch (e.g., `specialist_a@1`, `specialist_b@1`). |

### 3.3 Usage metadata on task-mode spans

**AH-99 probe-1 and probe-4 confirmed:** task-mode sub-agent `usage_metadata` appears on the outer `Runner.run_async` event stream natively. The existing `extract_billable_tokens(event)` helper (`shared/token_accounting.py`) reads `usage_metadata` from each event and works unchanged for supervisor-orchestrated turns.

No custom event bridge is needed **at the task-mode boundary**. MER-E extracts token counts from the same event stream — the task-mode boundary adds span structure but does not change event-level `usage_metadata` placement.

**Carry-forward for MER-E — isolated `AgentTool` built-in-tool leaves (AH-121 re-plan):** a specialist's built-in-tool leaves (`google_search` grounding, `numerical_analyst` code-execution) **must** stay `AgentTool`-isolated — they cannot be task-mode sub-agents (the injected `FinishTaskTool` / `transfer_to_agent` sibling triggers Gemini `400 "Multiple tools must all be search tools"`; see [AH-PRD-15](./AH-PRD-15-agenttool-migration-cutover.md)). `AgentTool.run_async` drops their inner events (`#3984`), so:

- **MER-E should expect NO inner grounded-search / code-exec spans for these leaves** — the same class of accepted gap as the `google.genai` autopatch carry-forward in §2.1. The `AgentTool`'s `function_call` / `function_response` are visible in the outer trace, but the leaf's inner steps are not.
- **Their `usage_metadata` does NOT appear as leaf-level events.** It is captured by a leaf `after_model_callback` off-state sink (AH-PRD-15 `agent_tool_billing.py`, keyed by the outer `invocation_id`) and folded into the turn delta. Token totals stay correct via `extract_billable_tokens` + the drained sink, but the per-leaf span detail is absent **by design** — extractors must not treat its absence as missing data.

---

## §4 Retired Patterns

The following span/pattern names will **not** be emitted by the AH-PRD-05 implementation:

| Anti-pattern | Reason retired | Replacement |
|---|---|---|
| `execute_workflow` function-tool span | Inner-Runner pattern; discards sub-agent events (AH-75 defect reintroduced) | `task_delegation` spans via ADK-native delegation |
| `invoke_pipeline` inner-Runner call | Same defect | `ctx.run_node` + `asyncio.gather` for fan-out |

---

## §5 LoopAgent Review-Loop Spans (Unchanged)

Supervisor-orchestrated task delegations optionally wrap per-task specialists in a `LoopAgent` review loop (same as the existing single-step review path from AH-PRD-01). The `LoopAgent` review iteration spans (`review_loop_iteration`) are unchanged from the AH-PRD-09 baseline — they appear as grandchildren of the `task_delegation` span:

```
task_delegation: {task_id}
└── LoopAgent (review pipeline)
    ├── review_loop_iteration #1
    │   ├── specialist worker event(s)
    │   └── reviewer event(s)
    └── review_loop_iteration #2 (if not approved in #1)
```

**Note:** `LoopAgent` is deprecated in ADK 2.0 (migration path: `Workflow(graph=…)`) but functional. Future migration will change the inner span shape; that migration is a deferred follow-on.

---

## §6 Fixture Pointer

The canonical staging fixture is committed at:

```
app/adk/tracking/tests/fixtures/supervisor_orchestration_trace.json
```

The fixture models §2.2: one sequential `task_delegation` (task-mode call-and-return), a `fanout` span with two parallel `task_delegation` children, and a synthesis `task_delegation` whose `query` references upstream result keys. Every supervisor-specific span carries `emission_status: deferred` + `deferred_reason` referencing AH-PRD-05 — the runtime does not yet emit these; they are the target shape.

The schema-conformance test suite at `app/adk/tracking/tests/test_supervisor_orchestration_fixture.py` pins the emission-status honesty contract and asserts every §3.1 / §3.2 attribute (including `node_path`) is present with the expected type. It is wired into the standard pytest run and serves as the CI regression guard against fixture drift.

**MER-E should validate extractors against the fixture and the conformance test** before any AH-PRD-05 implementation PR merges to main.

---

## §7 MER-E Validation Checklist

Before any AH-PRD-05 implementation PR merges to main, run extractor validation against `app/adk/tracking/tests/fixtures/supervisor_orchestration_trace.json` and confirm:

- [ ] `pytest app/adk/tracking/tests/test_supervisor_orchestration_fixture.py -v` passes (schema-conformance gate).
- [ ] `extract_billable_tokens` correctly sums `usage_metadata` from task-mode sub-agent events in the outer stream (same helper, new events).
- [ ] MER-E extractors recognize `task_delegation` span by `span.name == "task_delegation"` + presence of `task_id` attribute.
- [ ] MER-E extractors read `node_path` from `task_delegation` summary for branch attribution in fan-out turns (task-mode path: `coordinator@1/task_specialist@…`; fan-out path: `specialist_a@1` / `specialist_b@1`).
- [ ] Fan-out spans (`fanout`) are correctly attributed as parallel-group parents using `task_ids` + `branch_count`.
- [ ] LoopAgent review iterations appear as grandchildren of `task_delegation` and are extracted as today.
- [ ] Old `execute_workflow` pattern is removed from any extractor that searched for it.
- [ ] Sign-off recorded in §8 Owner Pairing with date and reviewer name.

---

## §8 Owner Pairing

| Role | Contact |
|---|---|
| KEN-E trace producer | AH team / AH-97 assignee |
| MER-E extractor consumer | MER-E team (to be tagged on AH-97 when this doc merges) |

Implementation PRs must include a MER-E sign-off comment confirming extractor readiness before the PR is approved.

---

## §9 References

- [`docs/trace-structure-spec.md`](../../../../trace-structure-spec.md) §3.1, §14 — authoritative span attribute spec (updated by AH-97)
- [`docs/spike-adk2-supervisor-orchestration-live.md`](../../../../spike-adk2-supervisor-orchestration-live.md) §1 — AH-99 probe results (GO-confirmed; probe-1 + probe-4 inner-event propagation confirmation)
- [`docs/design/components/agentic-harness/projects/AH-PRD-05-multi-step-workflows.md`](./AH-PRD-05-multi-step-workflows.md) — implementation spec
- [`docs/design/components/agentic-harness/projects/AH-PRD-09-trace-contract-diff.md`](./AH-PRD-09-trace-contract-diff.md) — prior contract-diff (AH-75 transfer_to_agent; this document follows its template)
- [`docs/design/DESIGN-REVIEW-LOG.md`](../../../DESIGN-REVIEW-LOG.md) Review 44 — decision record
