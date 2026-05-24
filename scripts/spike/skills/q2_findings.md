<!-- Paste this entire section verbatim into docs/spike-agent-engine-sandbox-findings.md
     under the "## Question 2 — Cost per session" heading when SK-7 creates that file.
     Update the placeholder tables with real data once execution unblocks. -->

## Question 2 — Cost per session

### Method

**ADK version:** google-adk==1.27.5
**Spike engine:** `projects/PROJECT_NUMBER/locations/us-central1/reasoningEngines/ENGINE_ID`
**Service account:** `ken-e-api@ken-e-dev.iam.gserviceaccount.com`

**Representative workload** (defined in `q2_methodology.md` §d):

| Step | Operation | Purpose |
|---|---|---|
| 1 | Float math: `sum(i * 1.23456789 for i in range(10_000))` | In-sandbox CPU — analogous to a tool call's compute overhead |
| 2 | Write + read a 1 KB temp file via `pathlib` | File-system I/O — analogous to a skill that writes intermediate results |
| 3 | `subprocess.run(["/bin/echo", '{"tool": "stub", "result": "ok"}'])` | Subprocess spawn — analogous to a skill calling a bundled CLI tool |
| 4 | `time.sleep(10)` | Simulates a ~10s script invocation per SK-PRD-00 §7.AC-2 |

**In-sandbox script:** `scripts/spike/skills/q2_cost_per_session.py`
**Orchestrator:** `scripts/spike/q2_cost_orchestrator.py`
**Session data:** `scripts/spike/skills/q2_sessions.jsonl`

**Cohort design:** Sessions were interleaved in blocks of 10 (5 cold + 5 warm) to net out
time-of-day billing artifacts. Cold sessions pass a fresh Agent Engine resource name; warm
sessions reuse the `sandboxEnvironment` from the corresponding cold session in the block.

**Billing attribution:** Per `q2_methodology.md` §e, billing data was pulled ≥36h after the
last session from the Vertex AI billing export filtered to the spike service account and
measurement window. If the export did not separately break out `sandboxEnvironment` compute,
the proportional-by-duration fallback was applied (noted in the table below).

**Orchestrator standalone verification (structural):**

```
$ uv run python scripts/spike/skills/q2_cost_per_session.py
{"steps": {"compute": {"elapsed_ms": 0.76}, "file_io": {"elapsed_ms": 0.75},
 "subprocess": {"elapsed_ms": 5.18, "output": "{\"tool\": \"stub\", \"result\": \"ok\"}"},
 "sleep": {"elapsed_ms": 10000.13}}, "rss_kb": 93992, "total_elapsed_ms": 10006.82}
```

Script runs cleanly standalone (without Vertex AI); total wall-clock ~10s as designed.
`ruff` and `codespell` clean on all three new files.

---

### Result (table)

> **STATUS: EXECUTION BLOCKED — credentials constraint**
>
> This VM runs as `fun-e-agent-vm@fun-e-business.iam.gserviceaccount.com`, which does not
> have `aiplatform.reasoningEngines.get` / `aiplatform.reasoningEngines.sandboxes.create`
> on `ken-e-dev`. The orchestrator and workload script are fully implemented and verified
> structurally, but the N=30 measurement run (Task 4) and billing reconciliation (Task 5)
> require the spike service account `ken-e-api@ken-e-dev.iam.gserviceaccount.com`.
>
> **To unblock Tasks 4-8:** Run the orchestrator from a context with the spike service
> account (e.g., a VM in `ken-e-dev`, or after running
> `gcloud auth activate-service-account ken-e-api@ken-e-dev.iam.gserviceaccount.com ...`):
>
> ```bash
> # Smoke run (3 sessions)
> GOOGLE_CLOUD_PROJECT=ken-e-dev \
> VERTEX_AI_LOCATION=us-central1 \
> KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME=projects/PROJECT_NUMBER/locations/us-central1/reasoningEngines/ENGINE_ID \
> uv run python scripts/spike/q2_cost_orchestrator.py \
>   --n 3 --cohorts cold,warm
>
> # Bulk run (N=30)
> uv run python scripts/spike/q2_cost_orchestrator.py \
>   --n 30 --cohorts cold,warm \
>   --out scripts/spike/skills/q2_sessions.jsonl
> ```
>
> After the bulk run completes, wait ≥36h, pull the Vertex AI billing export, and populate
> the table below. Then update the **Implication for Skills** section accordingly and post
> the results as a comment on SK-3.

**Placeholder table structure** (populate after execution):

| Cohort | n | p50 (ms) | p95 (ms) | p50 ($/session) | p95 ($/session) | Attribution method |
|--------|---|----------|----------|-----------------|-----------------|-------------------|
| cold | — | — | — | — | — | — |
| warm | — | — | — | — | — | — |

**Line-item split** (populate from billing export):

| Billing SKU | Window total ($) | Per-session (cold, $) | Per-session (warm, $) |
|---|---|---|---|
| Vertex AI Reasoning Engine compute | — | — | — |
| sandboxEnvironment lifecycle (if separate) | — | — | — |
| Generative AI code-exec output tokens | — | — | — |
| Network egress (if itemised) | — | — | — |
| **Total** | — | — | — |

**Threshold check:** warm-cohort p50 vs $0.10/session threshold (PRD §7.AC-2 / AC #5):

> *[Populate after execution: PASS / FAIL against $0.10/session]*

---

### Implication for Skills

*(Populate after execution results are available.)*

**SandboxPool tuning inputs** (from warm-path p50/p95):

| Parameter | Derivation | Recommended value |
|---|---|---|
| `_MAX_ENTRIES` (LRU cap) | Cost-per-warm-session vs cost-of-cold-start; if cold >> warm, larger cap is worthwhile | *TBD* |
| `_IDLE_TTL_SECONDS` | Warm p50 elapsed as the floor (idle shorter than a session's runtime is premature); billing shows whether idle sandboxes accumulate cost | *TBD* |

**Rate-limit recommendation:**
- If warm-cohort p50 ≥ $0.10/session → recommend per-account rate limit; specific bound to be
  proposed in SK-8 comment informed by the cost number.
- If warm-cohort p50 < $0.10/session → "no rate limit needed for representative workload";
  closes PRD §9 open question "rate limit threshold".

---

*Tasks 1-3 (methodology, workload script, orchestrator) completed. Tasks 4-8 (execution, billing
reconciliation, cost table, findings staging, SK-8 recommendation) blocked by credential
constraint; see STATUS note above.*
