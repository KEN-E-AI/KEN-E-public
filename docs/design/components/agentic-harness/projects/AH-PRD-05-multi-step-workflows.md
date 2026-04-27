# AH-PRD-05 — Multi-Step Workflow Orchestration

**Status:** Blocked
**Owner team:** Core AI / Agent Platform
**Blocked by:** AH-PRD-01 (`build_review_pipeline()`), AH-PRD-02 (factory-assembled specialist registry the workflow draws from), AH-PRD-03 (concrete first specialist for E2E coverage), AH-PRD-04 (artifact session-state convention threaded into `<prefix>_artifacts`)
**Parallel with:** Knowledge-Graph (KG-PRD-04 / KG-PRD-05), Skills SK-PRDs, Performance SE-PRD-05 / PE-PRDs (no overlap — workflow plumbing is intra-component)
**Blocks:** Any future R3+ feature that needs decomposed parallel data-gathering or staged execution with user approval — most concretely the multi-platform optimisation flows that motivate the R5 narrow specialists (Google Ads / Meta Ads / Mailchimp)
**Estimated effort:** 4 stories (originally `review-loop-implementation-plan.md` Phase 4). ≈ 3–5 days.

---

## 1. Context

After AH-PRD-01–04 ship, every specialist delegation runs inside a single-step Generator–Critic review loop: Root Agent picks one specialist, generates acceptance criteria, dispatches, gets an approved draft. That covers the bulk of marketing-analysis questions (`"Show me traffic trends for the past week"`) but breaks down for tasks that **inherently span multiple specialists or phases**. The motivating example from the parent design doc — `"Increase budgets for Meta Ads campaigns that result in the most engaged website visitors"` — needs (a) parallel data-gathering across two specialists (GA engagement + Meta Ads spend), (b) synthesis into an optimisation plan, (c) **explicit user approval** before any spend changes, then (d) execution in Meta Ads. There is no way to express that with single-tool-call dispatch.

This PRD lands the **multi-step workflow primitive**: a `build_workflow_pipeline()` factory that composes a list of `WorkflowStep`s into the right `ParallelAgent` / `SequentialAgent` / `LoopAgent` tree (each step still wrapped in the AH-PRD-01 review loop), plus an `execute_workflow()` root tool that lets the Root Agent decompose a complex request into structured steps and run them. User approval is handled by the Root Agent's existing conversational nature — no ADK `pause_invocation` infrastructure required: the workflow tool returns intermediate results when it hits an approval-required step, the Root Agent presents them to the user, and on the next turn the remaining steps resume from session state. After this project, KEN-E can express the multi-platform optimisation pattern end-to-end and the harness has a complete review-loop story for both single-step and multi-step composition.

This is the Release-3 capability that AH-PRD-01 §2 explicitly defers ("Multi-step workflow orchestration … deferred to a Release 3 story tracked in `docs/design/review-loop-implementation-plan.md` §Phase 4") and that the System Architecture §8.1 references when it talks about composing review pipelines into larger workflows. The four stories below are the canonical Phase 4 stories from that implementation plan, lifted into PRD form.

## 2. Scope

### In scope
- **`build_workflow_pipeline(steps, specialists) -> Agent`** factory — given a list of `WorkflowStep`s and the factory-assembled specialist registry, produce the composed agent hierarchy:
  - Steps with no shared dependencies → wrapped in `ParallelAgent` (one dependency-level group at a time)
  - Each step wrapped in a review pipeline via `build_review_pipeline()` from AH-PRD-01 with a unique `output_key_prefix` (`step_{id}`)
  - Each `LoopAgent` further wrapped in a per-branch `SequentialAgent` "pipeline" wrapper so future pre/post steps per branch don't restructure the tree (per `review-loop-implementation-plan.md` §3.3 + §8 pitfall: pipeline wrappers are required for `ParallelAgent` branches)
  - Steps with `approval_required=True` are excluded from the pipeline — the Root Agent handles them between turns
- **`WorkflowStep` dataclass** — `id`, `specialist`, `query`, `criteria`, `depends_on: list[str]`, `approval_required: bool`. Lives in `app/adk/agents/utils/workflow.py`.
- **`execute_workflow(steps: str, tool_context)` root-agent tool** — takes a JSON-string list of step objects, parses them, splits into pre-approval and post-approval phases, builds + invokes the pre-approval pipeline, persists `pending_workflow` to session state when an approval checkpoint is reached, and returns intermediate results for the Root Agent to present to the user.
- **Approval-via-conversation-turns continuation** — on the next user turn, the Root Agent reads `pending_workflow` from session state, calls `execute_workflow()` again with the remaining steps, and clears the key when the workflow finishes. No new ADK infrastructure; entirely on `tool_context.state`.
- **Synthesizer pattern** — when a workflow step exists whose role is to combine prior parallel results (`depends_on` covers ≥2 prior steps), the factory honors `include_contents='none'` on its specialist (or wraps its instruction with template-injected `{step_<id>_draft}` references) per `review-loop-implementation-plan.md` §3.3 + §8 pitfall: synthesizers must use `include_contents='none'` with strong "completed research" framing.
- **Root-instruction guidance** — extend the root agent's instruction (built at factory time per AH-PRD-02) with a "Multi-Step Workflows" section that teaches decomposition, dependency identification, parallel-vs-sequential discrimination, and approval-checkpoint identification. Includes worked-example: the budget-optimisation flow.
- **Artifact threading** — when a step's specialist calls `create_visualization()` (AH-PRD-04), the artifacts written to `<step_id>_artifacts` ride through the existing review-loop reviewer template (`{<prefix>_artifacts?}`) and are aggregated into `response_artifacts` on workflow completion so the chat endpoint extracts them as it does for single-step calls.
- **Tests** — unit (pipeline structure for parallel + sequential + approval cases; `WorkflowStep` parsing; output_key uniqueness), integration (full E2E against the GA specialist + a stubbed second specialist for parallelism), Weave trace verification (parallel sub-spans + phase boundaries visible).

### Out of scope
- **Firestore persistence of `pending_workflow`** — session-state continuation is sufficient for v1; full Firestore persistence (crash recovery, cross-device resumption) is deferred (see `review-loop-implementation-plan.md` §10 Q5).
- **Workflow observability beyond Weave** — user-facing progress streaming ("Gathering analytics data…", "Querying Meta Ads spend…") is `review-loop-implementation-plan.md` Phase 5 and a separate future PRD (planned Release 5).
- **Workflow CRUD / history UI** — no Workflows UI in this PRD. Multi-step workflows are agent-decomposed at runtime, not user-authored. (User-authored multi-step is the **Project Tasks** + **Automations** story, not the in-session workflow primitive.)
- **Workflow-step-specific skills attachment** — Skills attach at the specialist level (SK-PRD-02 / SK-PRD-04), not per-step. A step's specialist carries whatever skills it carries.
- **Cross-session workflow state** — workflows live within a single conversation session. Anything spanning sessions belongs to Project Tasks (`ProjectPlan` + `TaskOrchestrator`).
- **Parallel-step partial failure recovery beyond returning partial results** — per `review-loop-implementation-plan.md` §8 risk: ParallelAgent branches that fail are reported via their `output_key`; the synthesizer / Root Agent decides how to handle missing data. No automatic retry / rerun of failed branches in this PRD.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[AH-PRD-01](./AH-PRD-01-review-loop-framework.md)** | `build_review_pipeline(specialist, criteria, output_key_prefix, max_iterations)` is the per-step wrapping primitive. The workflow factory calls it once per `WorkflowStep`. **Hard prerequisite.** | This component |
| **[AH-PRD-02](./AH-PRD-02-agent-factory.md)** | Factory-assembled specialist registry — the `specialists: dict[str, LlmAgent]` argument to `build_workflow_pipeline()` is the factory's output. The Root Agent's instruction is also assembled by the factory; this PRD extends it with the Multi-Step Workflows section. **Hard prerequisite.** | This component |
| **[AH-PRD-03](./AH-PRD-03-google-analytics-specialist.md)** | First concrete specialist available for E2E coverage. Story 5.4 uses GA + a stubbed second specialist for the parallel test. | This component |
| **[AH-PRD-04](./AH-PRD-04-data-visualization.md)** | Artifact session-state convention (`<output_key_prefix>_artifacts` per AH-PRD-04 §4.3 as updated). Workflow steps that call `create_visualization()` write to `step_<id>_artifacts`; the workflow tool aggregates into `response_artifacts` on completion. | This component |
| ADK 1.26.0 | `ParallelAgent`, `SequentialAgent`, `LoopAgent`, `include_contents='none'`. Already pinned by AH-PRD-01. The pitfalls validated in `review-loop-implementation-plan.md` §8 (no `SequentialAgent` wrapper inside `LoopAgent`; pipeline wrapper required around each `LoopAgent` inside a `ParallelAgent`; `include_contents='none'` on synthesizer) are structural ACs of this PRD. | — |
| W&B Weave tracing | Each step's review-loop iterations and the parallel-branch boundaries appear as Weave sub-spans per `docs/trace-structure-spec.md`. No new span types required — the workflow span is the natural parent of the per-step pipeline spans AH-PRD-01 already emits. | `../../../trace-structure-spec.md` |

## 4. Data contract

No new Firestore collections or GCS state. All workflow state lives in ADK session state via the existing `output_key` mechanism plus a single `pending_workflow` continuation key.

### 4.1 `WorkflowStep` dataclass

```python
from dataclasses import dataclass, field

@dataclass
class WorkflowStep:
    id: str                              # short unique id within the workflow (e.g., "1a", "1b", "2", "3")
    specialist: str                      # config_id of a factory-built specialist (e.g., "google_analytics_specialist")
    query: str                           # task text passed to the specialist (becomes the user-message portion of its turn)
    criteria: str                        # acceptance criteria — same shape as AH-PRD-01's per-call criteria
    depends_on: list[str] = field(default_factory=list)
    approval_required: bool = False      # if True, workflow returns intermediate results before this step runs
```

The `id` doubles as the `output_key_prefix` suffix — each step's review pipeline uses `output_key_prefix=f"step_{step.id}"`, so the specialist writes to `step_{id}_draft` and the reviewer to `step_{id}_feedback`. Concurrent steps in the same `ParallelAgent` therefore have isolated state (per AH-PRD-01 AC #2).

### 4.2 Session-state keys

| Key | Shape | Written by | Read by | Lifetime |
|-----|-------|-----------|---------|----------|
| `step_{id}_draft` | `str` | step specialist (via `output_key`) | reviewer next iter, downstream-step specialist via `{step_{id}_draft}` template, synthesizer | Workflow run |
| `step_{id}_feedback` | `str` | step reviewer (via `output_key`) | step specialist next iter | Workflow run |
| `step_{id}_artifacts` | `list[Artifact]` | `create_visualization()` inside step specialist | reviewer via `{step_{id}_artifacts?}` template; aggregated into `response_artifacts` on workflow completion | Workflow run |
| `pending_workflow` | `{remaining_steps: list[dict], completed_results: dict}` | `execute_workflow()` when an approval-required step is reached | `execute_workflow()` on the next conversation turn (continuation); cleared when workflow finishes | Spans turns within a session |

`pending_workflow` is a single key, intentionally — only one workflow is active per session at a time. If a user cancels the approval ("nevermind"), the Root Agent clears the key as part of its acknowledgement; if the user starts a new workflow before approving, the new `execute_workflow()` call clears + replaces the prior `pending_workflow`.

### 4.3 Workflow JSON shape (root-tool argument)

The `execute_workflow(steps: str, ...)` tool takes a JSON string. Example for the budget-optimisation flow:

```json
[
  {"id": "1a", "specialist": "google_analytics_specialist", "query": "Engagement metrics by referring campaign for last 14 days", "criteria": "Return per-campaign engagement score; include time range; round to 2 decimals.", "depends_on": []},
  {"id": "1b", "specialist": "meta_ads_specialist", "query": "Daily spend by campaign for last 14 days", "criteria": "Return per-campaign daily spend totals; include time range.", "depends_on": []},
  {"id": "2", "specialist": "synthesizer", "query": "Combine analytics + spend into a budget-shift recommendation, ranked by efficiency", "criteria": "Output a ranked list with rationale; one chart of the proposed shift.", "depends_on": ["1a", "1b"], "approval_required": true},
  {"id": "3", "specialist": "meta_ads_specialist", "query": "Apply the approved budget changes", "criteria": "Each Campaign updated to the approved daily_budget; report success per campaign.", "depends_on": ["2"]}
]
```

Steps `1a` and `1b` run in parallel (no dependencies); step `2` depends on both and is the approval gate; step `3` runs only after the user approves on the next turn.

## 5. Implementation outline

### 5.1 File inventory

| Action | File |
|--------|------|
| Create | `app/adk/agents/utils/workflow.py` — `WorkflowStep` dataclass, `_compute_dependency_levels()`, `build_workflow_pipeline()` |
| Modify | `app/adk/agents/utils/review_pipeline.py` (AH-PRD-01) — re-export `build_workflow_pipeline` for callsite parity (`build_review_pipeline` lives in the same module per AH-PRD-01 §5) |
| Modify | `app/adk/agents/agent_factory/dispatch.py` (AH-PRD-02) — generate the `execute_workflow()` root tool alongside the per-specialist `dispatch_to_*()` functions; both decorated with `@safe_weave_op()` |
| Modify | Root-agent instruction assembly inside `app/adk/agents/agent_factory/__init__.py` (AH-PRD-02) — append the "Multi-Step Workflows" section described in §5.3 below to the assembled instruction |
| Create | `app/adk/agents/utils/test_workflow.py` — unit tests (pipeline structure for parallel + sequential + approval; `WorkflowStep` parsing; output_key uniqueness; dependency-level computation) |
| Create | `app/adk/agents/tests/test_multi_step_workflow_e2e.py` — E2E (`@pytest.mark.llm`); GA specialist + stubbed second specialist for the parallel branch |

### 5.2 Pipeline composition rules

The factory groups steps into **dependency levels**:

- Level 0: steps with empty `depends_on`
- Level 1: steps whose `depends_on` is a subset of level 0
- Level N: steps whose `depends_on` is a subset of levels 0..N-1

Within a level, **all steps run in parallel** under a `ParallelAgent`; levels are stitched together with a top-level `SequentialAgent`. Each step's `LoopAgent` (built by `build_review_pipeline`) is wrapped in a per-step `SequentialAgent` "pipeline" — the pipeline wrappers absorb future pre/post steps without restructuring the tree.

Three structural rules (validated from ADK 1.26.0 experiments — see `review-loop-implementation-plan.md` §8):

1. **No `SequentialAgent` directly inside a `LoopAgent`.** The specialist + reviewer remain the `LoopAgent`'s direct children (per AH-PRD-01) — `SequentialAgent` would swallow `escalate` from `exit_loop`.
2. **Each `LoopAgent` inside a `ParallelAgent` is wrapped in a `SequentialAgent`.** The pipeline wrapper isolates the loop and gives a stable identity for parallel-branch tracing. Without it, future pre/post-loop steps within a branch would force a tree restructure.
3. **Synthesizer agents use `include_contents='none'`.** A synthesizer is just a step whose `depends_on` covers ≥2 prior steps; its specialist's instruction template injects the prior `step_{id}_draft` values explicitly. Conversation history would otherwise pollute synthesis with the noisy review-loop back-and-forth from each branch.

### 5.3 Root-instruction extension

The factory appends a "Multi-Step Workflows" section to the root agent's instruction at build time (via the same instruction-assembly path AH-PRD-02 introduced for the "Available specialists" block). Content:

```
## Multi-Step Workflows

For complex tasks that require multiple specialists or phased execution:
1. Decompose the task into discrete steps.
2. Identify which specialist handles each step (use the Available specialists list above).
3. Define acceptance criteria for each step (same rules as single-step).
4. Identify dependencies — which steps must complete before others can start.
5. Identify approval points — steps that change external state should require user approval first.
6. Call execute_workflow() with the step plan as a JSON string.

Example: "Increase budgets for best-performing Meta Ads campaigns"
Steps:
  1a: Query GA for engagement by campaign (analytics) — no dependencies
  1b: Query Meta Ads for spend by campaign (meta_ads) — no dependencies
  2:  Combine into an optimisation plan (synthesizer) — depends on 1a, 1b — approval_required
  3:  Apply approved budget changes (meta_ads) — depends on 2

Skip workflow decomposition for simple single-specialist questions — call the
specialist's dispatch tool directly. Reach for execute_workflow only when the
task is genuinely multi-step or genuinely cross-specialist.
```

### 5.4 `execute_workflow()` shape

```python
def execute_workflow(steps: str, tool_context: ToolContext | None = None) -> str:
    """Execute a multi-step workflow with review loops and parallel branches."""
    parsed = json.loads(steps)
    workflow_steps = [WorkflowStep(**s) for s in parsed]

    # If a continuation is in flight and the new call doesn't supply step ids
    # already in pending_workflow.completed_results, this is a fresh workflow
    # and we clear the prior continuation.
    state = tool_context.state if tool_context else {}
    state.pop("pending_workflow", None)

    approval_idx = next(
        (i for i, s in enumerate(workflow_steps) if s.approval_required),
        len(workflow_steps),
    )
    pre_approval = workflow_steps[: approval_idx + 1]  # include the approval step itself

    pipeline = build_workflow_pipeline(pre_approval, available_specialists)
    results = invoke_pipeline(pipeline, state)

    if approval_idx < len(workflow_steps):
        state["pending_workflow"] = {
            "remaining_steps": [s.__dict__ for s in workflow_steps[approval_idx + 1 :]],
            "completed_results": results,
        }

    # Aggregate per-step artifacts into response_artifacts so AH-PRD-04's chat-endpoint
    # extraction works unchanged.
    aggregated_artifacts: list = []
    for step in pre_approval:
        aggregated_artifacts.extend(state.get(f"step_{step.id}_artifacts", []))
    if aggregated_artifacts:
        existing = state.get("response_artifacts", [])
        state["response_artifacts"] = existing + aggregated_artifacts

    return json.dumps(results)
```

Continuation on the next turn is the same function called with `steps` containing only `pending_workflow.remaining_steps`; the Root Agent reads `pending_workflow` from session state and constructs the continuation call.

## 6. API contract

No new HTTP endpoints. Two additive surface changes:

- A new `execute_workflow(steps, tool_context)` tool on the Root Agent — generated by the factory's dispatch generator alongside the per-specialist `dispatch_to_*()` functions; decorated with `@safe_weave_op()` for tracing.
- The existing chat endpoint sees no shape change — `response_artifacts` aggregation is internal; `ChatResponse.artifacts` (AH-PRD-04) is the same surface.

## 7. Acceptance criteria

1. **`build_workflow_pipeline` shape:** Given two steps with no shared dependencies, the factory returns a `ParallelAgent` whose `sub_agents` are exactly two per-step `SequentialAgent` pipeline wrappers, each wrapping a `LoopAgent` whose direct children are the specialist worker + reviewer (no `SequentialAgent` inside `LoopAgent`).
2. **Sequential + parallel composition:** Given two parallel steps and a third step that depends on both, the factory returns a top-level `SequentialAgent` whose `sub_agents` are `[ParallelAgent(2 pipelines), <step 3 pipeline>]`. Output keys for the three steps are pairwise distinct (`step_{id}_draft`, `step_{id}_feedback`).
3. **Approval-step exclusion:** Steps with `approval_required=True` are the **last** step in the pre-approval pipeline (the user must see the approval-step output before approving). Any step listed after an approval step is omitted from the pre-approval pipeline and persisted to `pending_workflow.remaining_steps`. Continuation execution rebuilds the pipeline for the remaining steps and runs them.
4. **Synthesizer rule:** Any step whose `depends_on` covers ≥2 prior steps is built with its specialist's `LlmAgent.include_contents` set to `'none'`. The specialist's instruction template injects `{step_{id}_draft}` for each upstream step id. Unit test asserts `include_contents='none'` is set.
5. **Output-key isolation:** Two parallel steps with ids `"1a"` and `"1b"` do not collide on `_draft` / `_feedback` / `_artifacts` keys. Asserted by integration test that runs both branches and checks both drafts in session state at completion.
6. **`execute_workflow` tool:** Generated by the factory's dispatch generator with `@safe_weave_op()`; signature `execute_workflow(steps: str, tool_context: ToolContext | None = None) -> str`; parses the JSON arg, invokes the pre-approval pipeline, persists `pending_workflow` if an approval step exists, returns a JSON string of results for the Root Agent to present.
7. **Continuation on next turn:** Given `pending_workflow` set in session state, the Root Agent calls `execute_workflow()` with `pending_workflow.remaining_steps` on the next turn, the remaining pipeline runs, and `pending_workflow` is cleared on completion. Integration test covers the two-turn flow.
8. **Artifact aggregation:** When a workflow step's specialist calls `create_visualization()`, the artifact lands in `step_{id}_artifacts`; `execute_workflow()` aggregates per-step artifacts into `response_artifacts` so the chat endpoint's existing AH-PRD-04 extraction populates `ChatResponse.artifacts` unchanged.
9. **Root-instruction extension:** The factory-assembled root instruction includes the "Multi-Step Workflows" section verbatim, including the worked example, after the "Available specialists" block. Snapshot-tested.
10. **Backward compatibility:** All single-specialist queries (existing AH-PRD-03 behaviour) continue to dispatch via `dispatch_to_*()` rather than `execute_workflow()`. The integration test from AH-PRD-03 continues to pass without modification.
11. **Weave traces:** A multi-step run produces a Weave trace with: the `execute_workflow` span as the root; one parallel-group sub-span per dependency level containing per-step pipeline sub-spans; per-step review-loop iterations as further sub-spans; acceptance criteria captured in the per-step pipeline span attributes; the approval-checkpoint boundary visible as a span attribute on the workflow span.
12. **Partial-failure tolerance:** If one branch in a parallel level fails, the other branches still complete; the synthesizer (or whichever step depends on the failing branch) sees the failure via the failing step's `step_{id}_draft` content and decides how to handle it. No automatic retry of failed branches.

## 8. Test plan

### Unit (`test_workflow.py`)
- `WorkflowStep` parses from dict; `field(default_factory=list)` produces a fresh list per instance.
- `_compute_dependency_levels()` — known DAG → expected level partition; cyclic input raises a clear error.
- `build_workflow_pipeline` — 2 parallel steps → `ParallelAgent[Sequential(Loop), Sequential(Loop)]`; 1+1+1 sequential chain → `Sequential[Sequential(Loop), Sequential(Loop), Sequential(Loop)]`; 2-parallel-then-1 → `Sequential[Parallel[Sequential(Loop), Sequential(Loop)], Sequential(Loop)]`.
- Approval-step exclusion — `approval_required=True` on the last pre-approval step ⇒ pipeline includes it but stops there; subsequent steps not in the built tree.
- Synthesizer rule — step with 2+ upstream deps ⇒ specialist agent constructed with `include_contents='none'`.
- Output-key uniqueness — every constructed agent in the tree has a unique name; every `output_key` in the tree is unique.
- Pipeline structural rules — no `SequentialAgent` is ever a direct child of a `LoopAgent`; every `LoopAgent` inside a `ParallelAgent` is wrapped in exactly one `SequentialAgent`.

### Integration (Firestore emulator + factory; `@pytest.mark.adk`)
- Two-step parallel-only workflow against the GA specialist + a stubbed second specialist — both complete, both drafts present in session state, results aggregated into the tool return value.
- Two-step parallel + synthesizer — synthesizer's instruction template successfully injects both `step_1a_draft` and `step_1b_draft`; synthesizer output present in `step_2_draft`.
- Approval checkpoint — workflow stops at approval step; `pending_workflow` populated; intermediate result returned.
- Continuation — second `execute_workflow()` call with the persisted remaining steps runs the post-approval branch; `pending_workflow` cleared.
- Workflow restart — calling `execute_workflow` with a fresh step list while `pending_workflow` is populated overwrites the continuation cleanly.
- One branch fails (stubbed specialist raises) — other branch completes; failing branch's `step_{id}_draft` contains an error sentinel; downstream synthesizer sees the error.

### E2E (`test_multi_step_workflow_e2e.py`, `@pytest.mark.llm`)
- Real Gemini, real GA MCP, stubbed Meta Ads specialist (returns canned spend data) — full budget-optimisation flow up to the approval gate; user sends approval message on next turn; remaining step (stubbed Meta Ads write) executes.
- Weave trace inspection — assert the expected hierarchy (workflow span → per-level parallel groups → per-step pipelines → review-loop iterations); `acceptance_criteria` captured on each step span.
- Backward-compat — existing AH-PRD-03 single-specialist E2E tests still pass.

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| **Latency** — multi-step + multi-iteration workflows can hit ~30–90s per the cost table in `review-loop-implementation-plan.md` §3.6 | Cap each step at `max_iterations=3` (carries from AH-PRD-01); ParallelAgent levels run concurrently so wall-clock is the slowest branch, not the sum. Surface a Weave-derived workflow-duration metric for monitoring. |
| **Token cost** — each step adds reviewer overhead; multi-step amplifies | Reviewer stays on `gemini-2.0-flash` (per AH-PRD-01); criteria generation per step adds ~200 tokens; monitor via Weave per AH-PRD-01 risk-table pattern. Synthesizer's `include_contents='none'` keeps history out of the synthesis context. |
| **Root agent generates malformed step plans** — invalid JSON, unknown specialist names, cyclic dependencies, missing approval gates on writes | `execute_workflow()` validates the input: JSON parse error → tool returns clear error string; unknown specialist → tool returns specialist-not-found; cyclic deps → caught in `_compute_dependency_levels()`; missing approval gate is a soft instruction-level concern — mitigated by the worked example in the root instruction. Invalid input does not raise — it returns a string the Root Agent reads and reacts to. |
| **`ParallelAgent` state collision** | Per-step `output_key_prefix=f"step_{id}"` enforced by the factory; AC #5 covers it. |
| **`SequentialAgent` swallowing `escalate`** (validated pitfall) | AC #1 + AC #2 require LoopAgent's direct children to be specialist + reviewer (per AH-PRD-01) and forbid `SequentialAgent` between them. Unit test asserts. |
| **Synthesizer sees full conversation history** (validated pitfall) | AC #4 — `include_contents='none'` enforced for any step with ≥2 upstream deps; instruction template explicitly injects the prior drafts. |
| **`pending_workflow` leaks across unrelated workflows** | `execute_workflow` clears `pending_workflow` at the start of every call (§5.4) before parsing the new step list; restart test in §8 covers this. |
| **Crash recovery / cross-device resumption** | Out of scope for v1 — session-state continuation is sufficient for the chat-conversation use case. Firestore persistence is deferred per `review-loop-implementation-plan.md` §10 Q5; revisit when workflow framework matures. |
| **Workflow tries to dispatch to a dispatched-only-from-root specialist** | Specialist registry is the same one the factory hands to the root agent; the dispatcher rejects unknown specialist ids. No additional access control needed because the workflow tool is itself a root-agent tool — same trust boundary. |
| **Artifact ordering** — multiple parallel branches each emit charts; aggregation order should be stable | `execute_workflow` aggregates by step iteration order (sorted by `id` per dependency level), not by completion order. AC #8 + integration test cover this. |

### Open questions
- **Q:** Should the Root Agent be allowed to call `execute_workflow` recursively (a step whose specialist is the root itself)? → No. The dispatcher rejects `specialist == "ken_e"` to prevent infinite recursion. Documented in the root instruction.
- **Q:** Should `execute_workflow` support fan-out — same specialist invoked twice with different queries in the same level (`step_1a` and `step_1b` both use `google_analytics_specialist`)? → Yes; specialists are stateless from the workflow's point of view. Each invocation gets its own `output_key_prefix`. Already covered by AC #5.
- **Q:** Maximum step count? → Soft cap of 12 enforced by `execute_workflow` (validation). Multi-step workflows above 12 steps are almost always better expressed as a `ProjectPlan` (Project Tasks).
- **Q:** Should an explicit synthesizer specialist be a factory-built `LlmAgent` (`agent_configs/synthesizer`), or is the synthesizer pattern just any specialist with ≥2 upstream deps? → Both. The pattern works for any specialist; we additionally seed a generic `synthesizer` config (Gemini Flash, no tools, instruction templated for combining drafts) so simple workflows have a default. Future PRDs may add specialized synthesizers.

## 10. Reference

- Parent plan: [`../../../review-loop-implementation-plan.md`](../../../review-loop-implementation-plan.md) §3.3 (Multi-Step Workflow architecture), §Phase 4 (Stories 4.1–4.4 — the canonical source for this PRD), §8 (validated ADK pitfalls), §10 Q5 (deferred Firestore persistence)
- Harness design: `docs/KEN-E-System-Architecture.md` §2.1 (ADK agent types), §8.1 (in-session multi-step workflows — pointer updated to this PRD)
- Upstream: [AH-PRD-01](./AH-PRD-01-review-loop-framework.md), [AH-PRD-02](./AH-PRD-02-agent-factory.md), [AH-PRD-03](./AH-PRD-03-google-analytics-specialist.md), [AH-PRD-04](./AH-PRD-04-data-visualization.md)
- Trace spec: `docs/trace-structure-spec.md` — workflow span hierarchy (no new span types)
- Decision rationale: [Review 6 in DESIGN-REVIEW-LOG](../../../design/DESIGN-REVIEW-LOG.md#review-6-task-delegation-with-review-loops) (review-loop pattern; multi-step is a composition of it)
- CLAUDE.md rules in scope: PY-1, PY-2, PY-3, PY-7; C-2, C-4, C-7; T-1, T-3, T-5, T-6
