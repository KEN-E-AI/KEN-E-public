# AH-PRD-01 — Review Loop Framework

**Status:** Ready to start
**Owner team:** Core AI / Agent Platform
**Blocked by:** —
**Parallel with:** DM-PRD-00, DM-PRD-01, DM-PRD-02, DM-PRD-03, DM-PRD-04 (no data-model coupling)
**Blocks:** AH-PRD-02 (dispatch-function generator imports `build_review_pipeline`)
**Estimated effort:** 2–3 days (9 issues, originally Sprint 8)

---

## 1. Context

The current dispatch pattern runs specialist agents once and relays their output verbatim to the user. There is no quality gate — the Root Agent cannot verify that a specialist's response meets the user's intent before presenting it. This project introduces a **Generator–Critic review loop** using ADK's native `LoopAgent`: every specialist delegation runs inside a review pipeline that iterates until an independent reviewer approves the draft or `max_iterations` is reached.

The core deliverable is `build_review_pipeline(specialist, acceptance_criteria, output_key_prefix, max_iterations) -> LoopAgent` — a factory function that takes **any** `LlmAgent` and returns a `LoopAgent` with the specialist and a lightweight `gemini-2.0-flash` reviewer as direct sub-agents. The reviewer either calls `exit_loop` (approval) or writes feedback to session state for the next iteration. The full chain is wired through: Root Agent generates 2–4 acceptance criteria → passes them through tool functions and dispatch handlers → `build_review_pipeline()` constructs the loop → approved draft returns to the Root Agent.

Because the factory is **agent-agnostic**, this project can be verified against the existing hardcoded specialists (`company_news_chatbot`, `google_analytics_agent_v4`) without any factory-built specialist present. When `acceptance_criteria is None/empty`, the existing single-pass behavior is preserved (backward compatible). This project is the atomic building block that [AH-PRD-02](./AH-PRD-02-agent-factory.md)'s dispatch-function generator composes with and that [AH-PRD-03](./AH-PRD-03-google-analytics-specialist.md) validates end-to-end with the first factory-built specialist.

## 2. Scope

### In scope
- Create `app/adk/agents/utils/review_pipeline.py` — `build_review_pipeline()` factory
- Add `acceptance_criteria: str | None = None` parameter to dispatch functions in `dispatch_handlers.py`
- Add `acceptance_criteria: str = ""` parameter to root-agent tool wrappers (`search_company_news`, `query_google_analytics`) in `ken_e_agent.py`
- Update `ken_e_agent.py` root-instruction to guide 2–4-criterion generation before tool calls
- Update `supervisor_utils.py` to extract `{prefix}_draft` from session state after pipeline runs
- Unit tests for pipeline structure, exit-on-approval, exhaustion-on-max-iterations, state isolation, template correctness
- Single-step integration test exercising the full chain (user message → criteria → dispatch → review loop → approved result) with Weave trace verification

### Out of scope
- Multi-step workflow orchestration (`build_workflow_pipeline`, `execute_workflow`, `ParallelAgent` + synthesizer pattern) — deferred to a Release 3 story tracked in `docs/design/review-loop-implementation-plan.md` §Phase 4
- Agent-factory generation of dispatch functions (owned by AH-PRD-02 story 2.2-5)
- Any changes to the specialist agents themselves — the review loop wraps them externally

## 3. Dependencies

- **None hard.** The pipeline wraps any `LlmAgent`; existing hardcoded specialists (`app/adk/agents/company_news_chatbot/agent.py`, `app/adk/agents/google_analytics_agent_v4.py`) are sufficient for integration testing.
- **ADK 1.26.0** — `LoopAgent`, `LlmAgent`, `output_key`, `include_contents='none'`, `exit_loop`. Already pinned.
- **Existing files to study:**
  - `app/adk/agents/ken_e_agent.py` (root-agent definition + tool wrappers)
  - `app/adk/agents/utils/dispatch_handlers.py` (existing dispatch pattern with `@safe_weave_op()`)
  - `app/adk/agents/utils/supervisor_utils.py` (existing `invoke_agent_sync` helper)
  - `app/adk/agents/google_analytics_agent_v4.py`, `app/adk/agents/company_news_chatbot/agent.py` (two integration-test specialists)
  - `docs/design/review-loop-implementation-plan.md` (parent implementation plan — §3.1 Building Block and Phase 1–3 drive this PRD)

## 4. Data contract

This project introduces **no new Firestore or GCS state**. All intermediate state lives in ADK session state via ADK's `output_key` mechanism:

| Session-state key | Written by | Read by |
|-------------------|-----------|---------|
| `{prefix}_draft` | specialist (via `output_key`) | reviewer (via `{prefix}_draft` template) |
| `{prefix}_feedback` | reviewer (via `output_key`) | specialist next iteration (via `{prefix}_feedback?` optional template) |

Each review pipeline uses a unique `output_key_prefix` (e.g., `news_review`, `ga_review`) to isolate state between concurrent pipelines in the same session.

**Approval-vs-exhaustion signal.** After the pipeline returns, the value of `{prefix}_feedback` distinguishes the two terminal states deterministically:

| `session.state[f"{prefix}_feedback"]` | Meaning |
|---|---|
| `""` (empty string) | Loop approved. `exit_loop` produces no text, so its `output_key` write overwrites the prior feedback to empty. |
| non-empty | `max_iterations` reached. Value is the last reviewer's feedback bullets. |

Dispatch handlers use this signal to relay either the approved draft or the last draft + warning to the caller. ADK does **not** emit any synthetic "max_iterations reached" event; the empty-string check is the canonical detector.

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `app/adk/agents/utils/review_pipeline.py` — `build_review_pipeline()` + `extract_pipeline_result()` (uses the §5.2 detection idiom) |
| Modify | `app/adk/agents/utils/dispatch_handlers.py` — add `acceptance_criteria` parameter; build pipeline when provided |
| Modify | `app/adk/agents/ken_e_agent.py` — add `acceptance_criteria` parameter to tool wrappers; extend base instruction with criteria-generation guidance |
| Modify | `app/adk/agents/utils/supervisor_utils.py` — extract `output_key` values from session state after pipeline runs; backward-compatible fallback |
| Create | `app/adk/agents/utils/test_review_pipeline.py` — unit tests |
| Create | `api/tests/integration/test_review_loop_single_step.py` (or `app/` equivalent per repo convention) — single-step E2E integration test |

### 5.1 `build_review_pipeline()` signature

```python
def build_review_pipeline(
    specialist: LlmAgent,
    acceptance_criteria: str,
    output_key_prefix: str = "review",
    max_iterations: int = 3,
    reviewer_model: str = "gemini-2.0-flash",
) -> LoopAgent:
    """Generator-Critic loop: specialist drafts, reviewer approves or gives feedback."""
```

Structural rules (validated from ADK 1.26.0 experiments — see [Review 6 in DESIGN-REVIEW-LOG](../../../DESIGN-REVIEW-LOG.md#review-6-task-delegation-with-review-loops) and `review-loop-implementation-plan.md` §8 Risk Assessment):
- Sub-agents are **direct children** of `LoopAgent` — no `SequentialAgent` wrapper (`SequentialAgent` swallows the `escalate` signal from `exit_loop`).
- Reviewer uses `include_contents='none'` so it evaluates only the template-injected draft, not conversation history.
- Reviewer is `gemini-2.0-flash` (cheapest model; ~200–400 tokens per evaluation).
- Specialist template includes `{{{prefix}_feedback?}}` with the `?` suffix so the first iteration (no feedback yet) resolves to empty string instead of `KeyError`. The specialist's previous draft is carried via default conversation history — explicitly injecting `{{{prefix}_draft?}}` was tested and adds ~74 prompt tokens/iteration with no quality benefit, so it is deliberately omitted.
- Reviewer instruction must explicitly forbid text on the approval turn — the reviewer invokes `exit_loop` as a tool call with **no narration**. Without this, gemini-2.0-flash occasionally emits `"All criteria are met. Calling exit_loop."` as text without actually invoking the tool, leaving `escalate` unset and causing a wasted iteration. The reviewer instruction template should include: *"If criteria pass, invoke the `exit_loop` tool. Do not write 'calling exit_loop' or any approval text."*

### 5.2 Approval-vs-exhaustion detection in dispatch handlers

Dispatch handlers detect the loop's terminal state by inspecting session state after invocation. This idiom is the contract between `build_review_pipeline()` and every caller:

```python
state = session.state
draft = state[f"{prefix}_draft"]
feedback = state.get(f"{prefix}_feedback", "")
if feedback == "":
    # Approved: exit_loop wiped the feedback key on the approval turn
    return {"result": draft, "approved": True}
else:
    # max_iterations reached: feedback contains the last rejection bullets
    return {"result": draft, "approved": False, "warning": feedback}
```

**Defensive observability.** If the loop's last reviewer event has approval-sounding text (regex: `approved|all criteria|exit_loop`) but `escalate` was never set, the dispatch wrapper logs a warning span. This catches the rare hallucinated-approval failure mode (see §9 risks) and gives us a real-world rate via Weave.

## 6. API contract

No new HTTP endpoints. The tool-function surface on the root agent changes additively:

```python
# Before:
def search_company_news(query: str, tool_context: ToolContext | None = None) -> str: ...

# After:
def search_company_news(
    query: str,
    acceptance_criteria: str = "",        # NEW — empty string = legacy single-pass
    tool_context: ToolContext | None = None,
) -> str: ...
```

Empty-string criteria preserves the current single-pass dispatch; non-empty criteria triggers the review pipeline. Same signature change on `query_google_analytics`. Backward-compatible with Gemini tool-calling since `acceptance_criteria` is an optional parameter with a default.

## 7. Acceptance criteria

Mapped 1:1 to the Sprint 8 sprint-level ACs for traceability.

1. **Pipeline construction:** `build_review_pipeline(specialist, criteria)` returns a `LoopAgent` whose `sub_agents` list contains exactly `[specialist_worker, reviewer]` with no `SequentialAgent` wrapper.
2. **State isolation:** Two pipelines with different `output_key_prefix` values running in the same session do not collide on `_draft` or `_feedback` keys.
3. **Termination — approval:** When the reviewer determines all criteria are met, it calls `exit_loop` and the `LoopAgent` exits immediately without running the specialist again. The approved draft is retained in session state.
4. **Termination — exhaustion:** When `max_iterations` is reached without approval, the `LoopAgent` exits cleanly — no exception is raised, and ADK does **not** emit a synthetic warning event. The dispatch handler detects exhaustion by checking `session.state[f"{prefix}_feedback"] != ""` (per §5.2) and returns the last draft together with the final feedback text as the warning.
5. **Reviewer isolation:** The reviewer agent has `include_contents='none'` and uses `gemini-2.0-flash`. It evaluates only the template-injected draft and acceptance criteria — not conversation history.
6. **Criteria flow:** Acceptance criteria pass from root-agent tool functions through dispatch handlers into `build_review_pipeline()`. When `acceptance_criteria` is `None` or empty, existing single-pass behavior is preserved.
7. **Unit test coverage:** Unit tests verify pipeline structure, exit-on-approval, exhaustion-on-max-iterations, state isolation, and template correctness — all passing.
8. **Integration test:** End-to-end test validates the full chain (user message → root-agent criteria generation → dispatch → review iteration → approved result return) against an existing specialist (news or GA). Weave traces show review-loop iterations as sub-spans.
9. **Tracing:** All dispatch handlers with `acceptance_criteria` produce Weave traces with acceptance criteria, exit reason (`approved` | `max_iterations`), and total iteration count in the top-level pipeline span's attributes. Per-iteration sub-spans are **synthesized by the dispatch wrapper** — ADK's native event stream shares one `invocation_id` across the whole loop with `branch=null`, so the wrapper counts (specialist-final, reviewer-final) event pairs and emits one synthetic child span per pair.
10. **Approval-vs-exhaustion idiom implemented:** Dispatch handlers implement the §5.2 detection idiom verbatim. Unit test forces both branches (approved → `feedback == ""`; exhausted → `feedback != ""`) and asserts the handler returns the correct shape.
11. **Hallucinated-approval defensive check:** If the final reviewer event has approval-sounding text without `escalate=True`, the dispatch wrapper logs a warning span. Unit test forces this with a mocked reviewer that emits `"All criteria are met. Calling exit_loop."` as text only.

## 8. Test plan

### Unit (`test_review_pipeline.py`)
- Pipeline structure — `isinstance(pipeline, LoopAgent)`; `pipeline.sub_agents == [specialist_worker, reviewer]`; no intermediate `SequentialAgent`
- Reviewer config — `include_contents == 'none'`; `model == 'gemini-2.0-flash'`; `exit_loop` in tools
- Mock specialist returns bad draft iter 1, good draft iter 2 → `exit_loop` called on iter 2; approved draft in state
- `max_iterations=1` exhaustion → last draft retained; no exception
- Multiple pipelines with distinct prefixes → no key collisions
- Template correctness — specialist instruction contains `{{prefix}_feedback?}`; reviewer instruction contains `{{prefix}_draft}` and the full acceptance-criteria string
- Reviewer instruction-template assertion includes the forbid-narration clause (per §5.1 structural rule)

### Integration (single-step)
- Dispatch with `acceptance_criteria=None` → identical to current behavior (regression guard)
- Dispatch with criteria → pipeline built + invoked; approved draft returned
- End-to-end: real user message → root generates criteria (verify criteria in tool call) → pipeline runs against `google_analytics_agent_v4` or `company_news_chatbot` → approved draft in response
- Weave trace verification — review-loop iterations appear as **synthesized** sub-spans (one per specialist+reviewer event pair); acceptance criteria, exit reason, and iteration count in pipeline-level span attributes
- Exhaustion idiom — force max-iterations exit with a deadlock criterion; assert handler returns `{approved: False, warning: <last feedback>}` and `feedback` is non-empty in session state
- Hallucinated-approval defensive check — mock reviewer emits approval-sounding text without invoking `exit_loop`; assert dispatch wrapper logs a warning span and the loop continues normally

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| `SequentialAgent` wrapper swallows `escalate` | Factory places specialist + reviewer directly under `LoopAgent`; unit test asserts no `SequentialAgent` in sub-agents. |
| `output_key` + `exit_loop` overwrite important state | Reviewer (not specialist) calls `exit_loop`; reviewer's `output_key` holds feedback (overwritten to `""` on exit, but only read on next iter that never runs). |
| Latency increase (~3–5s per iteration) | `max_iterations=3` default caps overhead at ~15s. Root agent skips criteria for trivially simple lookups — empty string = single pass. |
| Token cost increase (~1–3k extra per delegation) | Reviewer on `gemini-2.0-flash` (cheapest). Monitor via Weave; adjust if cost-per-turn climbs. |
| LLM generates vague criteria | Root instruction includes good-vs-bad examples. Telemetry in AH-PRD-03 will reveal real-world quality; iterate on instruction. |
| Reviewer hallucinates `exit_loop` as plain text without invoking the tool (observed ~1/8 reviewer turns in pre-implementation testing) | Reviewer instruction explicitly forbids approval narration (§5.1). Dispatch wrapper logs a warning span when approval-sounding text appears without `escalate=True` (§5.2, AC#11). Telemetry will reveal real-world rate. |
| Reviewer cannot fact-check claims requiring external knowledge (observed approving a fabricated academic citation) | The reviewer is a structural / criteria-checker, not a fact-checker. Acceptance criteria must be phrased to be verifiable from the draft text alone (e.g., "must include a numbered list", not "numbers must be accurate"). Root-instruction examples should reflect this constraint. |
| Reviewer per-criterion feedback may include false positives | Treat the binary approve/reject signal as reliable; per-criterion bullets are guidance, not ground truth. Document this in dispatch-handler comments so callers don't surface bullets to users as authoritative. |

### Resolved questions
- **Q:** Should the reviewer model be configurable per specialist or always `gemini-2.0-flash`? → **Resolved:** default `"gemini-2.0-flash"` via the `reviewer_model` parameter (§5.1); revisit only if a specialist shows accuracy gaps.
- **Q:** Should the specialist instruction explicitly inject `{{{prefix}_feedback?}}` only, or also `{{{prefix}_draft?}}`? → **Resolved (feedback only).** Pre-implementation testing showed that adding `{{{prefix}_draft?}}` costs ~74 prompt tokens/iteration with no quality benefit — the previous draft is already available via default conversation history. Spec stays at feedback-only.

## 10. Reference

- Parent plan: [`../../../review-loop-implementation-plan.md`](../../../review-loop-implementation-plan.md) §Phase 1 (Core Building Block), §Phase 2 (Single-Step Integration), §Phase 3 (Criteria Generation), §Phase 4 (Multi-Step Workflow Support — deferred to Release 3)
- Harness design: `docs/KEN-E-System-Architecture.md` §4.6 (Review Loop Pattern), §8.1–8.3 (ADK pitfalls)
- Decision rationale: [Review 6 in DESIGN-REVIEW-LOG](../../../DESIGN-REVIEW-LOG.md#review-6-task-delegation-with-review-loops) (originally Notion Decision 21 — historical archive)
- Downstream: [AH-PRD-02](./AH-PRD-02-agent-factory.md) (dispatch generation imports `build_review_pipeline`), [AH-PRD-03](./AH-PRD-03-google-analytics-specialist.md) (first specialist to exercise review loop end-to-end)
- CLAUDE.md rules in scope: PY-1, PY-2, PY-6, PY-7; C-2, C-4, C-7; T-1, T-4, T-5, T-6
