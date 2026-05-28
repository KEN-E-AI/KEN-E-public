# AH-PRD-09 Trace Contract Diff — MER-E Coordination

**Document type:** Contract diff (per-sprint companion to the authoritative spec)  
**Authoritative spec:** [`docs/trace-structure-spec.md`](../../../../trace-structure-spec.md)  
**Issue:** AH-67 · Phase 5 — MER-E coordination + eval suite cutover gate  
**Status:** Ready for MER-E review

---

## §1 Purpose

AH-PRD-09 (Per-Turn Dispatch Agent) replaces the deploy-time agent factory model
(AH-PRD-02) with a per-turn specialist resolution path.  From a tracing perspective
the change is a **span shape change**: the N individual `dispatch_to_<specialist>`
Weave spans produced by the old factory are replaced by a single
`delegate_to_specialist` span that wraps a `specialist_run` child.

This document exists so that MER-E extractor authors can:

1. Understand exactly which spans were removed and which were added.
2. Update extraction queries before the Phase 5 default-on flag flip (the cutover
   gate; see §8).
3. Validate their updated extractors against the canonical staging fixture in §6.

---

## §2 Before / After Span Hierarchy

### 2.1 Pre-AH-PRD-09 (ADK factory model)

Each specialist gets its own Weave span, named after the specialist:

```
KEN-E root agent invocation (root span)
└── LLM call(s)
└── dispatch_to_business_researcher       ← one span per specialist type
    └── review_loop_iteration (0..N)
└── dispatch_to_competitive_analyst
    └── review_loop_iteration (0..N)
```

Span name pattern: `dispatch_to_{specialist_name}`  
Number of spans: **N** (one per registered specialist function called in the turn)

### 2.2 Post-AH-PRD-09 (per-turn dispatch model)

All specialist calls share a single entry-point span `delegate_to_specialist`, which
wraps a `specialist_run` child:

```
KEN-E root agent invocation (root span)
└── LLM call(s)
└── delegate_to_specialist                ← single entry-point span
    └── specialist_run                    ← per-call child (one per delegation)
        ├── load_config_from_firestore    ← Firestore config fetch (on cache miss)
        └── review_loop_iteration (0..N)  ← when acceptance_criteria is non-empty
```

Span name: always `delegate_to_specialist`  
Number of spans: **1** `delegate_to_specialist` per turn (plus one `specialist_run`
child per delegation call — root agent may call it multiple times in one turn).

---

## §3 Span-by-Span Attribute Table

### 3.1 `delegate_to_specialist` span (new)

| Attribute | Type | Source | Notes |
|-----------|------|--------|-------|
| `specialist_name` | `str` | `dispatch.delegate_to_specialist` | Matches the Firestore `doc_id` |
| `cache_hit` | `bool` | `specialist_runtime.resolve_agent_with_hit` | `True` when the LRU cache served the `LlmAgent`; `False` when a fresh build was triggered |
| `mcp_pool_hit` | `bool` | *(not yet implemented)* | Placeholder — will be set by AH-62. Always absent in this release. |

`specialist_name` and `cache_hit` are written via `set_delegate_attrs()` in
`app/adk/agents/utils/review_pipeline_tracing.py`, following the same
`weave.get_current_call().summary` pattern as `set_pipeline_attrs()`.

### 3.2 `specialist_run` span (child of `delegate_to_specialist`)

| Attribute | Type | Source | Notes |
|-----------|------|--------|-------|
| `acceptance_criteria` | `str` | forwarded from `delegate_to_specialist` args | Empty string for single-pass mode |
| `exit_reason` | `str` | `set_pipeline_attrs` | `"approved"` or `"max_iterations"` |
| `total_iterations` | `int` | `set_pipeline_attrs` | 0 in single-pass mode |
| `output_key_prefix` | `str` | `set_pipeline_attrs` | e.g. `"{doc_id}_review"` |

These attributes were already defined in AH-PRD-01 §7 AC#9.  Their location moves
from the `dispatch_to_<specialist>` span (pre) to the `specialist_run` span (post),
which is one level deeper.

### 3.3 `review_loop_iteration` span (grandchild, unchanged)

Structure unchanged from pre-AH-PRD-09.  One child per review iteration with
`iteration`, `specialist_output`, `reviewer_output` summary attributes.

---

## §4 Retired Patterns

The following span names are **no longer emitted** after the Phase 5 flag flip.
MER-E extractors that match on these names must be updated before the flip.

| Retired span name | Replacement |
|-------------------|-------------|
| `dispatch_to_{specialist_name}` | `delegate_to_specialist` (parent) + `specialist_run` (child) |

Pattern to retire in extractor queries:
```python
# Before — matches N per-specialist spans
span["name"].startswith("dispatch_to_")

# After — match the single entry point
span["name"] == "delegate_to_specialist"
```

`generate_dispatch_functions` and `_build_dispatch` were deleted in AH-66; only `assemble_available_specialists_block` survives in `dispatch.py`.

---

## §5 Inner-Runner Nesting

When `acceptance_criteria` is non-empty, `specialist_runtime.run` invokes a
review-loop pipeline, which emits `review_loop_iteration` child spans.  The depth
is therefore:

```
delegate_to_specialist          (depth 1)
└── specialist_run              (depth 2)
    └── review_loop_iteration   (depth 3)  — 0..max_iterations children
```

When `acceptance_criteria` is empty (single-pass mode), the `review_loop_iteration`
children are absent; `specialist_run` contains only the LLM invocation events.

MER-E extractors that previously looked for `review_loop_iteration` as a direct
child of `dispatch_to_*` must now look two levels deeper (child of `specialist_run`,
grandchild of `delegate_to_specialist`).

---

## §6 Fixture Pointer

A canonical staging trace fixture is committed at:

```
app/adk/tracking/tests/fixtures/transfer_to_specialist_trace.json
```

The fixture represents a compliant post-AH-PRD-09 `delegate_to_specialist` trace
with:
- `specialist_name` and `cache_hit` summary attributes on the outer span
- A `specialist_run` child with `acceptance_criteria`, `exit_reason`,
  `total_iterations`, `output_key_prefix`
- One `review_loop_iteration` grandchild

Use `app/adk/tracking/tests/test_transfer_to_specialist_fixture.py` to run the
schema-conformance assertion.

---

## §7 Owner Pairing

| Role | Contact |
|------|---------|
| KEN-E trace producer (this issue) | AH team / AH-67 assignee |
| MER-E extractor consumer | MER-E team (to be tagged on AH-67 when this doc merges) |

The cutover gate (§8) requires a written sign-off from the MER-E team that their
eval suite passes against the new trace shape before the Phase 5 default-on flip.

---

## §8 MER-E Validation Workflow

The per-turn dispatch feature flag was dropped in AH-66 (2026-05-28).
The post-AH-75 trace shape is unconditional — there is no
"before the flag flip" state to reason about.

MER-E validation steps:

1. AH-75 has shipped. The post-AH-75 trace fixture at
   `app/adk/tracking/tests/fixtures/transfer_to_specialist_trace.json` is
   the canonical contract MER-E validates against.
2. MER-E team validates their extractors against the fixture + extractor
   guidance in §14.4 of `docs/trace-structure-spec.md`.
3. MER-E team confirms their eval suite passes on AH-67 and tags the
   AH-67 issue with confirmation.

Note: `dispatch_to_*` spans were never emitted in production after
AH-PRD-09 Phase 2 shipped — the `generate_dispatch_functions` code path
was deleted in AH-66 and never registered in the deployed root.

Note: This document still references `delegate_to_specialist` span names
throughout §2–§6 (AH-75 replaced that with `transfer_to_agent`). A
broader AH-75 refresh of this document is tracked separately; for the
canonical post-cutover trace shape see AH-66 and
`app/adk/tracking/tests/fixtures/transfer_to_specialist_trace.json`.

---

## §9 References

- [`docs/trace-structure-spec.md`](../../../../trace-structure-spec.md) §14 — authoritative per-span attribute spec for AH-PRD-09
- [`docs/trace-structure-spec.md`](../../../../trace-structure-spec.md) §3.1 — span naming conventions table (updated with `delegate_to_specialist` row)
- `app/adk/agents/agent_factory/dispatch.py` — `delegate_to_specialist` function
- `app/adk/agents/agent_factory/specialist_runtime.py` — `resolve_agent_with_hit`, `run`
- `app/adk/agents/utils/review_pipeline_tracing.py` — `set_delegate_attrs`
- `app/adk/tracking/tests/fixtures/transfer_to_specialist_trace.json` — canonical fixture
- AH-PRD-09 §7 AC #22 — cutover gate acceptance criterion
- AH-62 — `mcp_pool_hit` attribute (not yet implemented; TODO placeholder in `set_delegate_attrs`)
