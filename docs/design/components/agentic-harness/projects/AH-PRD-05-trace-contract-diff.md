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
└── synthesis: {result_key}          ← synthesizer task (depends_on both)
    └── mode='task' specialist run
```

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

### 3.2 `fanout` span (new, when `ctx.run_node` is used)

| Attribute | Type | Source | Notes |
|-----------|------|--------|-------|
| `task_ids` | `list[str]` | Fan-out branch task IDs | Identifies which TODO items ran in parallel |
| `branch_count` | `int` | Len of parallel group | |
| `all_succeeded` | `bool` | Set after gather completes | |

### 3.3 Usage metadata on task-mode spans

**AH-99 probe-1 and probe-4 confirmed:** task-mode sub-agent `usage_metadata` appears on the outer `Runner.run_async` event stream natively. The existing `extract_billable_tokens(event)` helper (`shared/token_accounting.py`) reads `usage_metadata` from each event and works unchanged for supervisor-orchestrated turns.

No custom event bridge is needed. MER-E extracts token counts from the same event stream — the task-mode boundary adds span structure but does not change event-level `usage_metadata` placement.

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

When the first AH-PRD-05 implementation PR lands, a canonical staging fixture will be committed to:

```
app/adk/tracking/tests/fixtures/supervisor_orchestration_trace.json
```

MER-E should validate extractors against that fixture before the PR merges to main. Until then, the span-attribute table in §3 is the contract.

---

## §7 MER-E Validation Checklist

Before any AH-PRD-05 implementation PR merges to main:

- [ ] `extract_billable_tokens` correctly sums `usage_metadata` from task-mode sub-agent events in the outer stream (same helper, new events).
- [ ] MER-E extractors recognize `task_delegation` span by `span.name == "task_delegation"` + presence of `task_id` attribute.
- [ ] Fan-out spans (`fanout`) are correctly attributed as parallel-group parents.
- [ ] LoopAgent review iterations appear as grandchildren of `task_delegation` and are extracted as today.
- [ ] Old `execute_workflow` pattern is removed from any extractor that searched for it.

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
