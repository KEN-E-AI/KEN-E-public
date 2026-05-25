# Q2 Cost-Per-Session Measurement — Methodology

**ADK version:** google-adk==1.27.5
**Spike engine:** `projects/PROJECT_NUMBER/locations/us-central1/reasoningEngines/ENGINE_ID`
**Service account:** `ken-e-api@ken-e-dev.iam.gserviceaccount.com`

---

## (a) Vertex AI Billing Line Items Counted as "Session-Attributable"

A single Q2 session spans from `AgentEngineSandboxCodeExecutor` construction (cold: includes
`sandboxEnvironment` creation; warm: omitted) through the final `code_execution_result` event
received by the harness. The following line items are counted:

| Line item | Billing SKU | Attribution method |
|---|---|---|
| **Vertex AI Reasoning Engine — compute** | `REASONING_ENGINE_COMPUTE` | Direct: billed per second of active `reasoningEngine` allocation during the session window |
| **Vertex AI sandboxEnvironment lifecycle** | `SANDBOX_ENVIRONMENT_RUNTIME` (if billed separately) | Direct if Vertex billing exports break this out; proportional-by-duration fallback (see §e) |
| **Vertex AI Generative AI compute — code execution** | `GENERATIVE_AI_CODE_EXECUTION` (Gemini code-exec output tokens) | Direct: ~500–2,000 output tokens per `code_execution_result` event at Gemini Flash pricing; per KEN-E System Architecture §10.3 (~$0.00015–$0.0006 per session) |
| **Network egress (GCP → GCP same-region)** | `NETWORKING_EGRESS_GOOG` | Direct if billing exports surface it; otherwise assumed negligible for same-region same-project traffic (Q1 is the authoritative egress measurement) |

Items explicitly **not counted**:
- Gemini prompt/completion tokens for the LLM orchestration layer (Q2 measures sandbox cost, not
  LLM cost; LLM layer is tracked separately in System Architecture §10.3)
- Storage I/O for the 1 KB file write in the workload (sub-cent per million operations)

---

## (b) Measurement Window Definition

| Marker | Definition |
|---|---|
| **Window start** | Timestamp immediately before `AgentEngineSandboxCodeExecutor(...)` construction in the orchestrator process |
| **Window end** | Timestamp immediately after the harness's `Exit status: ok` line is printed |
| **Billing pull time** | ≥ 36 hours after the last session in the bulk run (Task 4). Vertex AI billing exports have daily granularity; 36 h covers one full settlement cycle plus a margin for late-posted usage |
| **Billing filter** | Service account: `ken-e-api@ken-e-dev.iam.gserviceaccount.com`; SKUs: those named in §a; date range: run date through run date + 2 days |

The orchestrator records `session_start_iso` and `session_end_iso` (UTC ISO 8601) in each JSONL
row so the total measurement window is derivable from `min(session_start_iso)` and
`max(session_end_iso)` in `q2_sessions.jsonl`.

---

## (c) Cold-Start vs Warm-Start Operational Definitions

**Cold session:** the orchestrator passes a *fresh* Agent Engine resource name
(`projects/<proj>/locations/<loc>/reasoningEngines/<id>`) as `--sandbox-resource-name`.
The ADK `AgentEngineSandboxCodeExecutor` constructor lazily creates a new
`sandboxEnvironment` under the engine, incurring the full creation latency + any
per-creation billing event. One fresh resource name per cold session in a cohort block.

**Warm session:** the orchestrator passes a resource name that was already used in an
earlier cold session in the same cohort block (i.e., includes `/sandboxEnvironments/<id>`).
The executor attaches to the already-warm sandbox, skipping creation overhead.

**Cohort interleaving:** sessions are interleaved in blocks of 10 (5 cold + 5 warm) to
net out time-of-day billing artifacts (Vertex pricing tiers, regional load variation).
Within each block, the 5 warm sessions reuse the `sandbox_resource_name` from the
first cold session in the same block.

**SandboxPool relevance:** `SandboxPool` (SK-PRD-02 §4.6) operates exclusively on the
**warm path** — it pools already-created `AgentEngineSandboxCodeExecutor` instances across
turns. The warm-cohort p50/p95 is therefore the load-bearing cost number for pool tuning.
The cold-path cost is still reported for completeness (it informs `SandboxPool._MAX_ENTRIES`
economics — is it worth keeping a sandbox warm vs letting it expire?).

---

## (d) Workload Composition

The in-sandbox workload (`scripts/spike/skills/q2_cost_per_session.py`) runs the following
three synthetic "tool call" stand-ins plus a `time.sleep(10)` in sequence:

| Step | Operation | Rationale |
|---|---|---|
| **Step 1 — compute** | Deterministic float math: `sum(i * 1.23456789 for i in range(10_000))` | Exercises in-sandbox CPU path; analogous to a real tool call's compute overhead |
| **Step 2 — file I/O** | Write 1 KB of repeated bytes to a temp file via `pathlib`, then read it back and verify content | Exercises file-system I/O; analogous to a skill that writes/reads intermediate results |
| **Step 3 — subprocess** | `subprocess.run(["/bin/echo", '{"tool": "stub", "result": "ok"}'], ...)` capturing JSON output | Exercises subprocess spawning; analogous to a skill calling a bundled CLI tool |
| **Step 4 — sleep** | `time.sleep(10)` | Simulates a ~10s script invocation (SK-PRD-00 §7.AC-2 workload definition) |

Per-step timing is recorded via `time.perf_counter()`. Peak RSS after all steps is recorded
via `resource.getrusage(RUSAGE_SELF).ru_maxrss`. A single JSON record is emitted to stdout.

---

## (e) Attribution Fallback (Proportional-by-Duration)

If Vertex AI billing exports for the measurement window do **not** separately break out
`sandboxEnvironment` compute from `reasoningEngine` compute (i.e., all execution cost is
lumped under a single SKU), the following fallback applies:

1. Compute the **total billing delta** for the spike service account over the measurement
   window (sum of all Vertex AI line items).
2. Compute the **session-hours fraction**: `sum(session_elapsed_s) / (measurement_window_s)`.
3. Attribute `total_billing_delta × session-hours_fraction` as the session-attributable cost.
4. Divide by session count to get $/session.

The fallback produces an upper-bound estimate (it attributes all billing cost to sessions,
ignoring idle/infrastructure cost). The findings document must flag this explicitly so
SK-PRD-02 owners can re-baseline if Vertex adds per-resource billing granularity.
