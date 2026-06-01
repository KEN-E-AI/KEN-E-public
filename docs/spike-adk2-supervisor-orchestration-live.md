# ADK 2.0 Supervisor-Orchestration Spike — Live Evidence (AH-99)

**Spike issue:** [AH-99](https://linear.app/ken-e/issue/AH-99)  
**Phase:** 0.5 — Live validation (gates [AH-97](https://linear.app/ken-e/issue/AH-97))  
**Static basis:** `docs/spike-adk2-supervisor-orchestration.md` (AH-96, CONDITIONAL GO)  
**Probe scripts:** `docs/spike-adk2/probe-{1,4,5,7}-*.py` (live) + `probe-{2,3,6}-*.py` (static)  
**Date executed:** 2026-06-01  
**Run environment:** local workstation, ADC `ken@ken-e.ai`, python3.12, `google-adk==2.0.0` (`.venv-adk2/`)  
**Status:** ✅ **GO-confirmed** — all four live probes exit 0 against real Gemini Flash + the dev Vertex AI Agent Engine.

---

## §1 — Verdict

✅ **GO-confirmed.** All four live probes (Q1, Q4, Q5, Q7) executed against real Gemini Flash
(`gemini-2.0-flash`) and the dev Agent Engine (`ken-e-dev` / `us-central1`, engine
`5957383247464759296`) and **all exit 0**. AH-96's CONDITIONAL GO is upgraded to a confirmed GO.

| Probe | AH-99 AC | Exit | Result |
|---|---|---|---|
| probe-1 | AC #1 (task-mode path) | 0 | Inner `task_specialist` event reaches the outer stream with non-null `usage_metadata`; counted by the real `extract_billable_tokens` + `SessionTurnAccumulator`. |
| probe-4 | AC #2 (dynamic-graph fan-out) | 0 | `tool_context.run_node()` works; both fan-out branches surface inner events with `usage_metadata` in the outer stream. |
| probe-5 | AC #3 (session round-trip) | 0 | `node_info` + `isolation_scope` **survive** an append→`get_session`→reconstruct round-trip on the dev backend (verified on the **stored** events). No migration needed. |
| probe-7 | AC #1 (Q7 review-loop) | 0 | `LoopAgent` runs end-to-end; `exit_loop` terminates it; all loop events visible in the outer stream; 1064 tokens billed. `LoopAgent` is deprecated (→ `Workflow`) but functional. |

**Correction to the prior INDETERMINATE diagnosis.** The earlier draft of this document
attributed the non-execution to a missing `aiplatform.endpoints.predict` / `aiplatform.sessions.*`
IAM grant on the build VM. That diagnosis was **wrong**. With a credentialed ADC, the session
service (`create`/`get`/`list`/`delete`) and Gemini `predict` calls all succeed — the IAM is
sufficient. The real blockers were two **probe bugs** that would have prevented success in *any*
environment, IAM notwithstanding:

1. **`_DEFAULT_MODEL = "gemini-2.0-flash-001"` reproducibly 404s through ADK 2.0's genai client.**
   ADK builds its client from environment (no explicit `project`/`location`), and the pinned
   `-001` alias does not resolve that way, even though it resolves via a direct
   `Client(vertexai=True, project=…, location=…)` call. The unversioned `gemini-2.0-flash`
   resolves correctly. **Fixed** in `_live_harness._DEFAULT_MODEL`.
2. **The model client was never routed to Vertex.** Without `GOOGLE_GENAI_USE_VERTEXAI=TRUE` +
   `GOOGLE_CLOUD_PROJECT` + `GOOGLE_CLOUD_LOCATION`, ADK falls back to the Gemini API (AI Studio)
   backend and raises `No API key was provided`. The harness configured only the *session
   service* for Vertex, not the *model client*. **Fixed** — `_live_harness` now sets these three
   vars at import (to the dev values), so probes are self-contained as the README promised.

Both failures were originally masked by a bare `except Exception → sys.exit(2)` ("infrastructure/
credentials"), which is why they were mis-recorded as INDETERMINATE rather than surfaced. See §10.

**Routing consequence:** [AH-97](https://linear.app/ken-e/issue/AH-97) is **unblocked**. Per
AH-99 AC #5, GO-confirmed means AH-97 writes the ADK 2.0 supervisor-orchestration model as the
**target architecture** (see §9).

---

## §2 — How to Reproduce This Run

**Prerequisites:**

```bash
# 1. ADC with access to ken-e-dev (Gemini predict + aiplatform.sessions.*).
gcloud auth application-default login

# 2. Bootstrap the isolated venv from repo root. Python 3.10+ is REQUIRED
#    (google-adk 2.0 does not support 3.9). This run used python3.12.
python3.12 -m venv .venv-adk2          # or: uv venv --python 3.12 .venv-adk2
.venv-adk2/bin/pip install -r docs/spike-adk2/requirements.txt
.venv-adk2/bin/python -c "from importlib.metadata import version; assert version('google-adk')=='2.0.0'; print('adk 2.0.0 OK')"

# 3. Verify the harness loads the REAL token-accounting modules.
.venv-adk2/bin/python -c "
import sys; sys.path.insert(0, 'docs/spike-adk2')
import _live_harness; _live_harness.import_real_modules(); print('OK')
"
```

No env-var `export` is needed — `_live_harness` sets `GOOGLE_GENAI_USE_VERTEXAI` /
`GOOGLE_CLOUD_PROJECT` / `GOOGLE_CLOUD_LOCATION` to the dev values at import.

**Run the four live probes:**

```bash
.venv-adk2/bin/python docs/spike-adk2/probe-1-inner-event-propagation.py; echo "probe-1 exit=$?"
.venv-adk2/bin/python docs/spike-adk2/probe-4-usage-metadata.py;          echo "probe-4 exit=$?"
.venv-adk2/bin/python docs/spike-adk2/probe-5-session-service-schema.py;  echo "probe-5 exit=$?"
.venv-adk2/bin/python docs/spike-adk2/probe-7-loop-agent-task-mode.py;    echo "probe-7 exit=$?"
```

Exit-code contract (post-AH-99 hardening): **0** = assertions hold; **1** = a real finding (model
404, changed ADK API, validation error) → NO-GO; **2** = infrastructure/credentials (missing ADC,
401/403/429/5xx, transport) → INDETERMINATE. The classifier is `_live_harness.classify_exit_code`.

---

## §3 — Per-AC Evidence Table

| AH-99 AC | Question | Probe | Exit | Outcome |
|---|---|---|---|---|
| AC #1 (task-mode) | Inner events visible in outer stream — task-mode path | probe-1 | **0** | PASS — inner `task_specialist` event with `usage_metadata` (prompt=248, cand=8) in outer stream; accumulator counted 353 tokens. |
| AC #2 (dynamic-graph) | Inner events visible — `ctx.run_node` fan-out | probe-4 | **0** | PASS — both `specialist_a` + `specialist_b` events with `usage_metadata` in outer stream; accumulator counted 657 tokens. |
| AC #3 | `VertexAiSessionService` round-trip preserves `node_info` / `isolation_scope` | probe-5 | **0** | PASS — both fields **present on the STORED events** after `get_session` re-fetch. No migration needed. |
| AC #1 (Q7 path) | `LoopAgent` review-loop terminates via `exit_loop`, events visible, billed | probe-7 | **0** | PASS — 2 drafts, `exit_loop` fired (escalate), 1064 tokens billed. `DeprecationWarning: LoopAgent is deprecated … Please use Workflow instead.` (deprecated ≠ removed). |

**Static AC evidence (from AH-96 probes — re-run this session, all exit 0):**

| AH-99 AC | From static probe | Evidence |
|---|---|---|
| AC #2 (`extract_billable_tokens` compat) | probe-4 static (duck-typing) | Canonical fixture `input=1050, output=380, reasoning=0`. Now also confirmed live (above). |
| AC #3 (Firestore mirror safe) | probe-5 static (source analysis) | `append_event` stores `raw_event` via `model_dump()`; new fields additive. Now also confirmed live round-trips. |

---

## §4 — Decisive Evidence

**Probe-1 (task-mode path) — first inner `task_specialist` event with `usage_metadata`:**

```json
{
  "author": "task_specialist",
  "prompt_token_count": 248,
  "candidates_token_count": 8,
  "isolation_scope": "adk-30c59a97-4878-4169-8ed3-9bccb5c30ace",
  "node_path": "coordinator@1/task_specialist@adk-30c59a97-4878-4169-8ed3-9bccb5c30ace"
}
```

**Probe-4 (dynamic-graph path) — first inner event per fan-out branch:**

```json
{
  "author": "specialist_a",
  "isolation_scope": "branch_a_What is th",
  "node_path": "specialist_a@1",
  "prompt_token_count": 132,
  "candidates_token_count": 44
}
{
  "author": "specialist_b",
  "isolation_scope": "branch_b_What is th",
  "node_path": "specialist_b@1",
  "prompt_token_count": 132,
  "candidates_token_count": 30
}
```

Note: `node_path` differs by path — task-mode events nest under the coordinator
(`coordinator@1/task_specialist@…`) while `ctx.run_node` fan-out events are rooted at the
dispatched agent (`specialist_a@1`). Both carry non-null `usage_metadata` in the outer stream,
which is the decisive billing-accuracy result for AC #1/#2.

---

## §5 — Q5: VertexAiSessionService Round-Trip Outcome

Probe-5 now bases its verdict on the **stored** events (append → `get_session` → reconstruct),
not on the local event object returned by `append_event` (the original probe inspected the local
object, which trivially still carried the fields — it could never have detected a backend that
drops them). Independent re-fetch confirms:

```
Session retrievable: events stored: 2
  [task-mode]      stored author=task_specialist: node_info=present, isolation_scope=present
  [dynamic-graph]  stored author=specialist_a:     node_info=present, isolation_scope=present
--- Q5 Terminal State ---
raw_event roundtrip OK — node_info / isolation_scope survive the Agent Engine round-trip.
AH-99 AC #3: NO migration needed for new event fields.
```

The Chat side-table (`raw_event` mirror) is safe: ADK 2.0's new `node_info` / `isolation_scope`
fields persist through a real Agent Engine session round-trip on `ken-e-dev`.

---

## §6 — Model Spend Record

Approximate Gemini `gemini-2.0-flash` calls in the GO run (derived from yielded events):

| Probe | ~Model calls | Exit |
|---|---|---|
| probe-1 | ~2 (coordinator + task_specialist) | 0 |
| probe-4 | ~4 (coordinator + 2 specialists + summary) | 0 |
| probe-5 | 0 (no LLM calls — session service only) | 0 |
| probe-7 | ~6 (worker ×2, reviewer ×3, coordinator) | 0 |
| **Total** | **~12** | — |

Well under the ≤~50-call aggregate target. Note: the harness budget guard
(`MAX_TURNS_PER_PROBE = 3`, `assert_under_budget`) counts `run_and_collect` invocations (one per
probe), not individual model calls — it is a coarse circuit-breaker, not a precise meter. Actual
spend is negligible.

---

## §7 — Static Probe Regression (re-run this session)

All three static-only probes exit 0 (cleanup nits from AH-99 Task 6 applied):

| Probe | Exit | Notes |
|---|---|---|
| probe-2 (task-mode graph restriction) | 0 | Portable ADK path via `importlib.util.find_spec`; context-manager `open()`. Confirms #3984 (AgentTool event streaming) still OPEN in 2.0.0/2.1.0 — workaround is `mode='task'`. |
| probe-3 (Weave contextvar) | 0 | ThreadPool contextvar non-propagation is a pre-existing 1.34.1 issue, not a 2.0 regression. |
| probe-6 (AgentTool bridge) | 0 | Token accounting unchanged; parity tests need task-mode topology + new event shapes. |

```bash
.venv-adk2/bin/python docs/spike-adk2/probe-2-task-mode-graph-restriction.py; echo "probe-2 exit=$?"
.venv-adk2/bin/python docs/spike-adk2/probe-3-weave-contextvar.py;            echo "probe-3 exit=$?"
.venv-adk2/bin/python docs/spike-adk2/probe-6-agent-tool-bridge.py;           echo "probe-6 exit=$?"
grep -rn '/tmp/adk2-probe' docs/spike-adk2/                      # → no matches
grep -nE 'open\([^)]+\)\.read' docs/spike-adk2/probe-2-*.py      # → no matches
```

---

## §8 — Session Cleanup Verification

Each probe cleans its own `spike-ah99-*` sessions in a `finally` block; probe-5 additionally
asserts zero remaining. A final sweep after all runs returned **0**:

```bash
.venv-adk2/bin/python -c "
import asyncio, sys
sys.path.insert(0, 'docs/spike-adk2')
import _live_harness
print('Spike sessions remaining:', asyncio.run(_live_harness.cleanup_spike_sessions()))
"
# → Spike sessions remaining: 0
```

---

## §9 — AH-97 Routing Decision

Per AH-99 AC #5, the GO-confirmed outcome routes [AH-97](https://linear.app/ken-e/issue/AH-97) to:

✅ **Write the ADK 2.0 supervisor-orchestration model as the target architecture** for the
agentic-harness README, `KEN-E-System-Architecture.md`, AH-PRD-05, and AH-PRD-09 §4.6 — using the
`LlmAgent(mode='chat')` coordinator + `mode='task'` specialists + `ctx.run_node` dynamic-graph
fan-out + `LoopAgent` (or its `Workflow` successor) review-loop topology validated here.

Carry-forward caveats for AH-97:
- **`LoopAgent` is deprecated** in ADK 2.0 (functional, not removed). Long-term, migrate the
  review loop to `Workflow(graph=…)`.
- **GitHub #3984** (AgentTool event streaming inside Workflow graph nodes) remains OPEN — the
  validated path is `mode='task'`, not task-mode nodes inside a static Workflow graph (probe-2).
- **AH-98's agent-as-tool layer was created *after* this spike** and is not yet in AH-97's scope.
  AH-98 wires `google_search` as a literal `AgentTool(agent=create_google_search_agent())`
  (`source="agent"`, `agent.{name}` tool IDs, registry + roster resolver) on ADK 1.34.1. On
  ADK 2.0 the legacy `AgentTool.run_async` path **still discards inner events** (#3984), so the
  search sub-agent's `gemini-2.5-flash` tokens would go **uncounted** and its grounded-search
  steps would be **missing from traces** — reintroducing the AH-75 billing/tracing defect on a
  surface this spike's scope predated (see probe-6: "any REMAINING AgentTool usage … must be
  migrated to the task-mode / `ctx.run_node` path"). **AH-97 must additionally document:**
  (a) migrating `source="agent"` tools off `AgentTool.run_async` onto the task-mode /
  `_TaskAgentTool` / `ctx.run_node` dispatch so their events propagate and bill correctly;
  (b) re-validating AH-98's parallel-search AC (#9) under ADK 2.0's concurrency model
  (`ctx.run_node` fan-out, not ADK 1.x `handle_function_call_list_async → asyncio.gather`);
  (c) whether the agent-tool registry/resolver (`agent_tool_registry.py`, `roster.py`) emits
  task-mode sub-agents instead of `AgentTool` instances on 2.0.

The superseded routes, for the record: **NO-GO** (any probe exits 1) would have routed AH-97 to
the fallback architecture (static composition tree + hand-built event bridge per
`docs/design/adk2-supervisor-orchestration-analysis.md` §5.1); **INDETERMINATE** would have kept
AH-97 in Backlog. Neither applies — the run is a clean GO.

---

## §10 — Probe Fixes Applied During the Live Run (AH-99 Phase 0.5)

The probes were written but never successfully executed before this run. Getting them to produce
a trustworthy verdict required the following fixes (all in `docs/spike-adk2/`):

| Fix | File | Why |
|---|---|---|
| `_DEFAULT_MODEL` → `gemini-2.0-flash` | `_live_harness.py` | `gemini-2.0-flash-001` reproducibly 404s through ADK 2.0's env-based genai client. |
| Set Vertex routing env vars at import | `_live_harness.py` | Otherwise ADK falls back to AI Studio and demands a `GEMINI_API_KEY`; the probes are now self-contained. |
| `classify_exit_code()` + wired into all 4 probes | `_live_harness.py`, `probe-{1,4,5,7}` | A bare `except → exit 2` mis-bucketed genuine NO-GO signals (model 404, API mismatch) as INDETERMINATE. Now exit 1 vs 2 is classified. |
| Real round-trip via `get_session` | `probe-5` | Original probe inspected `append_event`'s return (the local object), a false-positive that could never detect dropped fields. |
| Draft counter by text + `exit_loop` as a hard assertion | `probe-7` | `turn_complete` is `None` on ADK 2.0 events, so the old iteration counter under-counted; `exit_loop` detection was computed but never asserted. |
| Removed dead imports | `probe-1`, `probe-7` | `importlib.util`/`warnings`/`SimpleNamespace` (probe-1), `FunctionTool` (probe-7). |

These are the substantive correctness gaps flagged in the AH-99 PR review; they were latent
because the probes had never run. The verdict above reflects the **fixed** probes.

_Live run conducted by: ken@ken-e.ai | AH-99 Phase 0.5 | 2026-06-01_
