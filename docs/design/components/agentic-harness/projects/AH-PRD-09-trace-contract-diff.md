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

---

## §10 Post-AH-75 Attribute Emission Update (AH-35)

AH-35 (Weave trace structure verification) wired the attribute emission that was
deferred when `delegate_to_specialist` was deleted in AH-75. The attributes that
§3.1 declared on the now-deleted `delegate_to_specialist` span now live on the
**specialist sub-agent span** (the direct child of the root agent, named after the
specialist's doc_id).

### Where attributes are emitted

| Attribute | Where emitted | Source |
|---|---|---|
| `specialist_name` | specialist sub-agent span `summary` | `after_agent_callback` installed by `_build_specialist` |
| `agent_kind` | specialist sub-agent span `summary` | `after_agent_callback` |
| `exit_reason` | specialist sub-agent span `summary` | `after_agent_callback` (loop_pipeline only) |
| `total_iterations` | specialist sub-agent span `summary` | `after_agent_callback` (loop_pipeline only) |
| `output_key_prefix` | specialist sub-agent span `summary` | `after_agent_callback` (loop_pipeline only) |
| `cache_hit` | specialist sub-agent span `summary` | `after_agent_callback` (constant `false` today — built only on cache miss) |
| `mcp_pool_hit` | — | Deferred to AH-62 (placeholder `# TODO(AH-62)` in test) |

The `after_agent_callback` writes **only** the six rows tagged `after_agent_callback`
above. It does not write `acceptance_criteria` / `default_acceptance_criteria`, and
`total_iterations` is currently a constant `0` (accurate counting deferred, AH-35).

#### Worker / reviewer child spans are deferred

The specialist sub-agent span is the wrapping `LoopAgent`. Its per-iteration children
are **not fully emitted today**, and the canonical fixture tags them accordingly via
`emission_status`:

| Child span | Emission status | Reason |
|---|---|---|
| `{doc_id}_worker` | Emitted (span only) | Worker agent span is emitted, but `weave_after_agent_callback` writes only `output={status, text}`; the `iteration` / `specialist_output` summary annotations are deferred (fixture: `deferred_summary`). |
| `{doc_id}_review_reviewer` | **Deferred** | The reviewer `LlmAgent` carries no agent-span callbacks, so no reviewer span is produced. Fixture carries it as target shape only. |

### Extractor guidance

MER-E extractors that previously searched for `set_delegate_attrs` attributes on
a `delegate_to_specialist` span should now look for them on the specialist
sub-agent span:

```python
# Before (pre-AH-75 — RETIRED):
span["name"] == "delegate_to_specialist"  # and summary["specialist_name"]

# After (post-AH-75, AH-35):
span["name"] == specialist_doc_id  # e.g. "google_analytics_specialist"
# and summary["specialist_name"] == span["name"]
```

The canonical fixture at
`app/adk/tracking/tests/fixtures/transfer_to_specialist_trace.json` now carries
`specialist_name`, `agent_kind`, `exit_reason`, `total_iterations`,
`output_key_prefix`, and `cache_hit` in the specialist span's `summary` block.
Validate against `test_transfer_to_specialist_fixture.py`.

### How the write targets the correct span (AH-35 follow-up)

The `after_agent_callback` is **inserted immediately before**
`weave_after_agent_callback` (which finishes and pops the agent's span), so
`weave.get_current_call()` resolves to the specialist's own span rather than the
parent/root span. See `_wire_specialist_span_callbacks` in
`app/adk/agents/agent_factory/specialist_runtime.py`.

- **Single-pass specialist** — the raw `LlmAgent` already carries
  `weave_after_agent_callback` (from `build_agent`); the AH-35 callback is
  inserted before it.
- **Review pipeline** — the bare `LoopAgent` has no Weave span of its own, so it
  is given a dedicated one (`weave_before`/`weave_after` wired onto it). That
  span is named after the specialist `doc_id`. Structurally it wraps the
  `{doc_id}_worker` / `{doc_id}_review_reviewer` sub-agents, but only the
  `{doc_id}_worker` span is emitted as a Weave span today (see "Worker / reviewer
  child spans are deferred" above and §14.2).

Span naming: `weave_before_agent_callback` now names each agent-level span after
its agent (`op = agent.name`) — root `ken_e`, specialists their `doc_id`. The
legacy hardcoded `ken_e_agent` op name is retired. The same change replaced the
single `_current_agent_call` ContextVar with a per-agent LIFO stack so nested
sub-agents no longer leave the root span unfinished.

Single-pass spans intentionally **omit** `exit_reason` / `total_iterations` /
`output_key_prefix` — those are review-loop concepts and would be meaningless
without a reviewer.
