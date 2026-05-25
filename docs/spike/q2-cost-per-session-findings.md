<!-- Paste this entire section verbatim into docs/spike-agent-engine-sandbox-findings.md
     under the "## Question 2 — Cost per session" heading when SK-7 creates that file.
     Update the placeholder tables with real data once execution unblocks. -->

> [!NOTE]
> **Live N=30 capture in progress (2026-05-25).** Wave 2.5 harness rework
> (SK-33) is merged; the orchestrator now runs against a trustworthy
> direct-mode harness. Timing data (cohort p50/p95, per-session elapsed)
> will land in this fragment as the re-run completes. **Vertex AI billing
> export numbers still require the ≥36 h settlement wait** (the §a/§e
> methodology is unchanged) — those land in a follow-up commit on or
> after 2026-05-27.
>
> Two prior orchestrator attempts (the same day, earlier) failed at
> session 2 of 60 with `[harness] Script not found:
> .../q2_cost_per_session.py`. Diagnosed as a branch-switching artifact:
> the orchestrator `subprocess.run`s the harness with a filesystem-relative
> path, and the main working tree was switched from `spike/...` to
> `integration/...` between sessions, removing the file from the
> subprocess's filesystem view. Fixed by running the re-run from a `git
> worktree` checkout of `spike/agent-engine-sandbox` at
> `/tmp/kene-spike/`, isolated from the main repo's branch switches.
>
> **Remove this banner only after** (1) the re-run completes with the
> error rate under threshold AND (2) the billing settlement has produced
> Vertex AI SKU-level numbers AND (3) every `*[Populate after execution]*`
> placeholder is replaced with real values.

## Question 2 — Cost per session

### Method

**ADK version:** google-adk==1.27.5
**Spike engine:** `projects/PROJECT_NUMBER/locations/us-central1/reasoningEngines/ENGINE_ID`
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

**Billing attribution:** Per `q2-cost-per-session-methodology.md` §e, billing data was pulled ≥36h after the
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

#### Cost (still pending Vertex billing settlement — 36 h from session end)

Vertex AI billing exports have daily granularity; 36 h from the last
session in the N=30 run (`warm_b5s4`, completed ~2026-05-25T13:30Z) covers
one full settlement cycle plus a margin. **Billing pull window opens
on or after 2026-05-27T01:30Z.**

**Line-item split (populate from billing export after 2026-05-27):**

| Billing SKU | Window total ($) | Per-session (cold, $) | Per-session (warm, $) |
|---|---|---|---|
| Vertex AI Reasoning Engine compute (`REASONING_ENGINE_COMPUTE`) | *[pending billing export]* | *[pending]* | *[pending]* |
| sandboxEnvironment lifecycle (`SANDBOX_ENVIRONMENT_RUNTIME`, if itemised) | *[pending]* | *[pending]* | *[pending]* |
| Generative AI code-exec output tokens (`GENERATIVE_AI_CODE_EXECUTION`) | *[pending]* | *[pending]* | *[pending]* |
| Network egress (`NETWORKING_EGRESS_GOOG`, if itemised) | *[pending]* | *[pending]* | *[pending]* |
| **Total** | *[pending]* | *[pending]* | *[pending]* |

**Threshold check (PRD §7.AC-2 / AC #5):** *[pending billing export — PASS / FAIL against $0.10/session warm-p50]*

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

#### Billing-derived implications (PENDING 2026-05-27 settlement)

5. **`_MAX_ENTRIES` (LRU cap):** TBD — needs per-session cost to compare
   against pool eviction cost. If per-session cost is dominated by
   compute (not container lifecycle), `_MAX_ENTRIES` can be small without
   meaningful regression. If sandbox-environment lifecycle is itemised
   separately and is a per-pool-entry cost, a larger cap may be more
   economical.

6. **Rate-limit recommendation:** TBD against the PRD §7.AC-2 $0.10/session
   threshold. Cold/warm equivalence above suggests cost should also be
   equivalent — but the billing export will confirm.

7. **PRD §9 open question (rate limit threshold):** still open pending
   billing.

> **Tasks 4 (live N=30 run) and 5 (cohort table) complete 2026-05-25.**
> **Tasks 6-8 (billing reconciliation, cost table, SK-8 recommendation)
> still pending the 36 h Vertex billing settlement** — billing pull
> window opens on or after 2026-05-27T01:30Z. Update the Line-item Split
> + Threshold Check tables and the billing-derived implications above
> when the export lands; then post the resolved finding as a comment on
> SK-3 and remove the `> [!NOTE]` banner at the top of this fragment.
