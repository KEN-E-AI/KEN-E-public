<!-- Paste this entire section verbatim into docs/spike-agent-engine-sandbox-findings.md
     under the "## Question 2 — Cost per session" heading when SK-7 creates that file.
     Update the placeholder tables with real data once execution unblocks. -->

## Question 2 — Cost per session

### Method

**ADK version:** google-adk==1.27.5
**Spike engine:** `projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568` (displayName `sk-prd-00-spike-sandbox`)
**Service account:** `ken-e-api@ken-e-dev.iam.gserviceaccount.com`

**Representative workload** (defined in `q2-cost-per-session-methodology.md` §d):

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

**Billing attribution:** Billing was pulled 2026-05-31 (≫ the 36 h window that opened
2026-05-27T01:30Z) from the Cloud Billing export at `ken-e-dev.billing_export`
(`gcp_billing_export_resource_v1_*`). The Vertex billing export attributes cost by
**project + resource + label**, not by calling principal — so the spike was isolated two ways
rather than by service account: (a) the dedicated spike engine by `resource.name`
(`reasoning-engine-2624457839443181568` — the Cloud Run backing-service id equals the
`reasoningEngine` id, verified against the Vertex `reasoningEngines.list` API), and (b) the
spike agent's LLM usage by the billing label `adk_agent_name = "spike_sandbox_agent"`. The
proportional-by-duration fallback (§e) was **not needed**: see the Line-item Split below.

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

**Live N=30 capture (2026-05-25):**

Run command (from a `git worktree` checkout at `/tmp/kene-spike/` on
`spike/agent-engine-sandbox`, isolated from the main repo's branch
switches — the harness reads the workload script from disk at subprocess
spawn time, so the working tree must remain stable across the orchestrator's
~16-minute run):

```bash
GOOGLE_CLOUD_PROJECT=ken-e-dev \
GOOGLE_CLOUD_LOCATION=us-central1 \
GOOGLE_GENAI_USE_VERTEXAI=1 \
VERTEX_AI_LOCATION=us-central1 \
KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME=projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568 \
uv run python scripts/spike/q2_cost_orchestrator.py \
  --n 30 --cohorts cold,warm --out /tmp/q2_sessions.jsonl
```

**Outcome:** 60/60 sessions completed successfully (30 cold + 30 warm, all
`status=ok`). Per-session JSONL retained at `/tmp/q2_sessions.jsonl`
(local-only — not committed because it contains absolute paths).

**Per-cohort timing (`elapsed_orchestrator_ms` field; includes subprocess
spawn + harness + Vertex round-trip + in-sandbox workload):**

| Cohort | n | ok | min | p25 | p50 | p75 | p95 | max | mean | stdev |
|--------|---|----|------|------|------|------|------|------|------|--------|
| cold | 30 | 30 | 13.34 s | 13.85 s | **14.10 s** | 14.32 s | 22.95 s | 28.65 s | 15.25 s | 3.27 s |
| warm | 30 | 30 | 13.49 s | 14.04 s | **14.14 s** | 14.32 s | 22.21 s | 25.99 s | 15.21 s | 2.82 s |

**Headline observation: cold and warm cohorts are statistically
indistinguishable.** p50 differs by 40 ms (0.3% of the median). mean differs
by 40 ms. p95 differs by 0.74 s (cold higher). This contradicts the
methodology's a-priori model that warm sessions would be measurably
faster due to sandbox container reuse.

Two plausible interpretations (both consistent with the orchestrator's
design note about cross-subprocess warmth being a Vertex-backend behaviour):

1. **Vertex does not reuse sandbox containers across `execute_code` API
   calls within this engine.** Every call provisions a fresh runtime,
   bringing the warm cohort to the cold cohort's baseline.
2. **Vertex does reuse containers, but the saved time is below this
   probe's noise floor** (the per-session overhead is dominated by
   subprocess spawn + Python startup + `google-genai` SDK import, which
   are paid per orchestrator subprocess regardless of Vertex's
   container state).

Either way, **the SK-PRD-02 `SandboxPool` warmth win cannot come from
holding the same engine resource name across separate ADK sessions.** It
has to come from holding the same `AgentEngineSandboxCodeExecutor`
*Python object* across multiple invocations within one process — which
is the in-process pool pattern SK-PRD-02 already designs around.

**In-sandbox workload timing (representative first cold session):**

```json
{
  "steps": {
    "compute":    {"elapsed_ms": 1.83},
    "file_io":    {"elapsed_ms": 2.54},
    "subprocess": {"elapsed_ms": 7.16, "output": "{\"tool\": \"stub\", \"result\": \"ok\"}"},
    "sleep":      {"elapsed_ms": 10000.76}
  },
  "rss_kb": 127344,
  "total_elapsed_ms": 10012.3
}
```

The 10 s `time.sleep(10)` dominates the in-sandbox elapsed time (10.01 s
total). The other three steps account for ~11 ms. The
**~4 s gap between in-sandbox total (10.01 s) and orchestrator p50 (14.10 s)**
is the per-session overhead: subprocess startup (~1 s for `uv run` cold
start within the worktree), Python interpreter + SDK import (~1-2 s), and
Vertex `execute_code` API round-trip (~1-2 s including sandbox creation).

#### Cost (Vertex billing export — settled; pulled 2026-05-31)

Vertex AI billing exports have daily granularity; the N=30 run completed
2026-05-25 and the export was fully settled by this pull on 2026-05-31
(≫ the 36 h window that opened 2026-05-27T01:30Z).

**Headline: the sandbox path produced no separately-metered Vertex cost.**
The dedicated spike engine `sk-prd-00-spike-sandbox`
(`…/reasoningEngines/2624457839443181568`) is a **sandbox-parent-only engine
with no `query()` implementation**, so it runs no deployed serving container
and accrued **zero `ReasoningEngine management fee`** over 2026-05-23 →
2026-05-30 (0 billing rows for `reasoning-engine-2624457839443181568`). Vertex
does **not** itemise a `SANDBOX_ENVIRONMENT_RUNTIME` or code-execution SKU in
this billing account/window (0 rows for any `%sandbox%` / `%code exec%` SKU
across all six projects in the export). The only spike-attributable line items
are orchestration-layer Gemini tokens (label `adk_agent_name=spike_sandbox_agent`),
which §a explicitly **excludes** from the Q2 sandbox-cost measure — and which
were consumed almost entirely on 2026-05-24 during SK-1 agent runs, not by the
2026-05-25 direct-executor N=30 run.

**Line-item split:**

| Billing SKU | Window total ($) | Per-session (cold, $) | Per-session (warm, $) | Attribution |
|---|---|---|---|---|
| Vertex AI Reasoning Engine compute (`reasoning-engine-2624457839443181568`) | 0.000000 | 0.000000 | 0.000000 | Direct (resource name) — 0 rows; sandbox-parent engine, no `query()` container |
| sandboxEnvironment lifecycle (`SANDBOX_ENVIRONMENT_RUNTIME`) | n/a | n/a | n/a | SKU not itemised by Vertex in this window |
| Generative AI code-exec output tokens (`GENERATIVE_AI_CODE_EXECUTION`) | n/a | n/a | n/a | SKU not present; direct executor emits no `code_execution_result` Gemini tokens |
| Network egress (`NETWORKING_EGRESS_GOOG`) | 0.000000 | 0.000000 | 0.000000 | 0 spike-tagged egress rows (same-region same-project; Q1 is authoritative) |
| **Total (session-attributable)** | **0.000000** | **0.000000** | **0.000000** | |
| _Memo: orchestration LLM — **excluded** by §a_ | _0.290715_ | _≤ 0.0048¹_ | _≤ 0.0048¹_ | Label `spike_sandbox_agent`: $0.290024 on 05-24 (SK-1 runs), $0.000691 on 05-25 (Q2) |

¹ Upper bound only, and out of scope per §a. Even if the **entire** $0.290715 of
orchestration-layer Gemini spend (almost all of it 2026-05-24 SK-1 traffic, not
the Q2 run) were wrongly charged to the 60 Q2 sessions, that is $0.0048/session
— still ~20× under the $0.10 threshold. The 2026-05-25-only spike LLM spend was
$0.000691 total (≈ $0.0000115/session).

Reproducible query (run 2026-05-31 against `ken-e-dev.billing_export`):

```sql
SELECT
  DATE(usage_start_time) AS day, service.description AS service,
  sku.description AS sku, ROUND(SUM(cost), 6) AS cost_usd
FROM `ken-e-dev.billing_export.gcp_billing_export_resource_v1_0183BD_803ED8_88685C`
WHERE usage_start_time >= TIMESTAMP("2026-05-23 00:00:00 UTC")
  AND usage_start_time <  TIMESTAMP("2026-05-31 00:00:00 UTC")
  AND project.id = "ken-e-dev"
  AND ( resource.name = "reasoning-engine-2624457839443181568"          -- engine fee: 0 rows
        OR EXISTS (SELECT 1 FROM UNNEST(labels) l                       -- spike LLM, by label
                   WHERE l.key = "adk_agent_name" AND l.value = "spike_sandbox_agent") )
GROUP BY day, service, sku ORDER BY day, cost_usd DESC;
```

**Threshold check (PRD §7.AC-2 / AC #5): PASS** — warm-cohort per-session
session-attributable cost = **$0.000000/session** (no metered sandbox or engine
cost; ≤ $0.0048 even under the absurd all-LLM upper bound) — far below the
$0.10/session threshold.

---

### Implication for Skills

#### Timing-derived implications (load-bearing today)

1. **`SandboxPool` warmth must be in-process.** Cross-subprocess warmth via
   the same engine resource name produces no measurable speedup (cold p50
   14.10 s, warm p50 14.14 s — within 40 ms). SK-PRD-02's pool design
   should not rely on Vertex reusing sandbox containers across separate
   API sessions; the latency win comes only from holding the same
   `AgentEngineSandboxCodeExecutor` instance across multiple
   `execute_code` calls in a single process.

2. **Per-session overhead is ~4 s on the orchestrator side, ~10 ms in the
   sandbox.** A 10 s in-sandbox script takes ~14 s wall-clock at the
   caller. For SK-PRD-02 pool sizing: the per-call orchestrator overhead
   does not amortise across pool entries (each entry pays its own SDK
   import + ADC bootstrap once), so the pool's value is for *batches of
   calls per session*, not for one-off invocations.

3. **`_IDLE_TTL_SECONDS` floor: ~14 s.** Idle TTL shorter than the typical
   session runtime would be premature eviction. This combined with Q4's
   5-minute single-budget cap gives a recommended range of `[15 s, 300 s]`
   for SK-PRD-02's `_IDLE_TTL_SECONDS`.

4. **Per-cohort stdev is modest (cold 3.27 s, warm 2.82 s).** The mean is
   stable. The N=30 sample is large enough that p50/p95 numbers above
   should be treated as load-bearing for SK-PRD-02 tuning.

#### Billing-derived implications (resolved 2026-05-31)

5. **`_MAX_ENTRIES` (LRU cap): cost is not the binding constraint — size by
   memory/concurrency; recommended default `_MAX_ENTRIES = 8`.** The billing
   reconciliation shows warm-held sandboxes carry **no metered holding cost**:
   the sandbox-parent engine accrues no `ReasoningEngine management fee` and
   sandbox runtime is not a separately-billed SKU. The original worry ("if
   sandbox-environment lifecycle is a per-pool-entry cost, a larger cap may be
   more economical") is therefore **moot** — there is no per-entry cost to
   amortise either way. `_MAX_ENTRIES` should be sized by per-process memory and
   expected concurrent in-process sessions (see Q4 resource limits), not
   economics. **Caveat for SK-PRD-02:** if the pool is later hosted under a
   *production* engine that also serves `query()` traffic, that host engine's
   management fee (~$0.086/h when active — observed on peer `ken-e-chat-agent` /
   `strategy-supervisor` engines in the same window) is a **fixed deployment
   cost shared across all sessions**, not a per-sandbox-session cost; it does
   not change the per-session economics measured here.

6. **Rate-limit recommendation: no cost-based sandbox rate limit needed for
   Release 1.** Per-session cost is $0.00 metered (≤ $0.0048 upper bound) —
   ~20×+ below the $0.10/session trigger in PRD §7.AC-2. A per-account
   sandbox-session cap is **not** warranted on cost grounds. Runaway/abuse
   protection remains the responsibility of Q4's per-session 5-minute budget cap
   and the SK-9 security controls, not a cost-based rate limiter.

7. **PRD §9 open question (rate-limit threshold): CLOSED.** Representative
   per-session cost ($0.00 metered; ≤ $0.0048 absolute upper bound) is far below
   $0.10/session, so KEN-E does **not** rate-limit sandbox sessions per account
   on cost grounds (Items 5–6). Re-open only if Vertex begins itemising
   `SANDBOX_ENVIRONMENT_RUNTIME`, or if SK-PRD-02 hosts the pool under a
   `query()`-serving engine and elects to attribute that engine's fixed
   management fee per-session.
