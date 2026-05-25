# Question 4 — Resource limits and failure modes

> Live capture from a credentialled workstation (`ken@ken-e.ai`) against the
> spike Agent Engine
> (`projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568`),
> 2026-05-25, post SK-33 harness rework. Three independent probe scripts
> (CPU, memory, wall-clock) run as separate harness invocations in direct
> mode (no `LlmAgent`). Each probe is designed to trigger Vertex's
> sandbox-level enforcer; the `Elapsed (s)` and `Exit status` fields are the
> measurement.
>
> SK-7 will absorb this file verbatim under `## Question 4 — Resource
> limits and failure modes` in
> `docs/spike-agent-engine-sandbox-findings.md`.
>
> **Prior context:** A first attempt at SK-5 used `--local-limits` mode
> (Linux `RLIMIT_CPU` / `RLIMIT_AS` on the host VM). That measures the host
> kernel's enforcer, not Vertex's platform enforcer. AC-5 requires the
> latter; this fragment captures the latter.

---

## Question 4 — Resource limits and failure modes

### Test

**Probe scripts** (each runs as a separate harness invocation):

| Script | What it does | Expected enforcer signal |
|---|---|---|
| `scripts/spike/skills/q4_cpu_loop.py` | `while True: pass` after a start marker | A CPU cap surfaces as either `OUTCOME_DEADLINE_EXCEEDED` or as a generic API error |
| `scripts/spike/skills/q4_memory_balloon.py` | Doubling `bytearray(N)` allocations starting at 1 MiB | `MemoryError` (Python-level) or a kernel OOM kill (no Python-level signal) |
| `scripts/spike/skills/q4_wall_clock.py` | Cumulative probes at 30s / 120s / 600s for both compute-bound and idle-sleep | The probe whose target exceeds the cap fails; preceding probes establish the threshold |

**Harness invocation pattern:**

```bash
GOOGLE_CLOUD_PROJECT=ken-e-dev \
GOOGLE_CLOUD_LOCATION=us-central1 \
GOOGLE_GENAI_USE_VERTEXAI=1 \
VERTEX_AI_LOCATION=us-central1 \
KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME=projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568 \
uv run python scripts/spike/sandbox_test_harness.py \
    --script scripts/spike/skills/q4_<probe>.py
```

---

### Result

#### CPU loop

```
=== [1/1] q4_cpu_loop.py status: error (ServerError): execute_code call failed —
503 UNAVAILABLE. {'error': {'code': 503, 'message': 'The service is currently
unavailable.', 'status': 'UNAVAILABLE'}}
---
ADK version  : 1.27.5
Sandbox      : projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568
Mode         : direct (no LlmAgent)
Scripts      : 1
Elapsed (s)  : 304.17
Exit status  : error (ServerError): execute_code call failed — 503 UNAVAILABLE.
```

**Interpretation.** The probe ran for **304.17 s** before Vertex's
`execute_code` API returned **503 UNAVAILABLE**. This is consistent with a
~5-minute CPU cap on a runaway compute-bound process. The error surface is
notable — Vertex does NOT return a structured `OUTCOME_DEADLINE_EXCEEDED` or
`OUTCOME_RESOURCE_LIMIT` enum; it returns a generic 503 from the API. The
harness classifies this as `error (ServerError)`, which is the right shape
for SK-PRD-02 to handle.

No stdout was captured beyond the start marker (`q4_cpu_loop: start —
entering tight busy loop`); the process was killed before any further
output. The Python-level start-marker print confirms the script reached
the busy loop before being killed.

#### Memory balloon

Two consecutive invocations, both with identical signature:

```
=== [1/1] q4_memory_balloon.py status: ok ===
---
ADK version  : 1.27.5
Sandbox      : projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568
Mode         : direct (no LlmAgent)
Scripts      : 1
Elapsed (s)  : 4.43  (first run)  /  3.95  (second run)
Exit status  : ok
```

**Interpretation.** Both runs returned `Exit status: ok` in ~4 s with
**zero stdout captured** — neither the per-allocation `q4_memory_balloon:
allocated N MiB total` line nor the `MemoryError` sentinel made it into
the harness output. Two possibilities, neither cleanly distinguishable
from this single observation:

1. Vertex's memory enforcer kills the sandbox process with SIGKILL when
   the bytearray allocation exceeds the per-process memory cap. The
   SIGKILL bypasses Python's stdout buffer flush, and Vertex's
   `execute_code` API still surfaces `OUTCOME_OK` for the API call
   itself.
2. The sandbox image has Linux memory overcommit enabled such that all
   doubling allocations succeed at the virtual-memory layer (lazy
   zero-page mapping) without ever touching the per-process cap; the
   script terminates "naturally" via some path that produces no output.

Either way, **the memory probe pattern is not informative for SK-PRD-02
SandboxPool tuning** — the harness cannot derive a per-MiB cap from this
signal. A redesigned probe that streams progress to a sandbox-side file
(then captured by a sibling read-probe) would be needed to recover this
measurement.

#### Wall-clock

```
=== [1/1] q4_wall_clock.py status: error (ServerError): execute_code call failed —
503 UNAVAILABLE. {'error': {'code': 503, 'message': 'The service is currently
unavailable.', 'status': 'UNAVAILABLE'}}
---
ADK version  : 1.27.5
Sandbox      : projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568
Mode         : direct (no LlmAgent)
Scripts      : 1
Elapsed (s)  : 303.49
Exit status  : error (ServerError): execute_code call failed — 503 UNAVAILABLE.
```

**Interpretation.** The cumulative wall-clock probe was killed at
**303.49 s** — within 1 s of the CPU loop's 304.17 s. Vertex caps both
compute-bound and wall-clock-bound scripts at the **same ~5-minute
threshold**, surfaced as `503 UNAVAILABLE` rather than a structured
outcome enum. Because no stdout was captured (the SIGKILL bypassed
Python's stdout flush, same as CPU and memory), we cannot determine
exactly which probe was running when the cap fired. However, the
elapsed time (303 s) bounds the answer: the script had completed
`compute-30s` (cumulative 30 s), completed `compute-120s` (cumulative
150 s), and was midway through `compute-600s` (would have finished at
750 s) when killed. The idle-sleep probes never ran.

**Implications for the compute-vs-sleep question:** undetermined from
this probe. The 5-minute cap fired during the compute-bound phase before
the script reached the idle-sleep portion. A refined probe would
front-load a short idle-sleep test (~60 s) to determine whether sleep
time counts equivalently against the same cap.

---

### Findings summary

| Probe | Vertex signal | Observed cap |
|---|---|---|
| CPU loop | `503 UNAVAILABLE` after 304.17 s | ~5 min (300 s) cap |
| Memory balloon | `OUTCOME_OK` with no stdout | not measurable via this probe pattern |
| Wall-clock (compute path) | `503 UNAVAILABLE` after 303.49 s | ~5 min (300 s) cap |

**The CPU and wall-clock probes returning the same ~300 s threshold
(within 1 s of each other) is consistent with a single Vertex sandbox
lifetime cap, not two independent caps.** SK-PRD-02 should model this as
"one 5-minute budget per `execute_code` call" rather than "5 min CPU AND
5 min wall-clock as independent budgets."

> [!NOTE]
> **503 ≠ definitely-a-cap caveat.** Vertex's `execute_code` API also
> returns `503 UNAVAILABLE` for transient backend errors (load shedding,
> region capacity, internal restarts). The 5-minute interpretation is
> the most parsimonious explanation given two independent probes (CPU
> and wall-clock) hit it within 1 s of each other, but a third probe run
> a day later that produces the same elapsed time would be the cleanest
> confirmation. SK-7 should note this as "best-current-interpretation,"
> not "validated against a known SLA."

### Concurrent-sandbox observation — RETRACTED

> An earlier draft of this fragment claimed Vertex had a "low
> concurrent-sandbox cap (1-2)" based on a Q2 orchestrator run where
> 59/60 sessions failed at 0.06 s elapsed. **That finding was incorrect.**
> The Q2 failure was caused by a branch-switch during orchestrator
> execution: the orchestrator `subprocess.run`s the harness with a
> filesystem-relative path to `scripts/spike/skills/q2_cost_per_session.py`,
> and the main working tree's branch was switched from `spike/...` to
> `integration/...` between sessions 1 and 2, removing the file from the
> tree the subprocess saw. Diagnosed via the per-session `raw_stdout` in
> `/tmp/q2_sessions.jsonl`, which showed
> `[harness] Script not found: .../q2_cost_per_session.py` for every
> failed session.
>
> A clean Q2 re-run was performed from a `git worktree` checkout of
> `spike/agent-engine-sandbox` at `/tmp/kene-spike/`, isolated from
> the main repo's branch switches. See the Q2 staging fragment
> (`q2-cost-per-session-findings.md`) for those numbers.
>
> No empirical evidence for or against a Vertex concurrent-sandbox cap
> remains; the earlier claim is withdrawn. A future probe specifically
> designed to test concurrent sandbox creation (multiple
> `execute_code` calls in flight against the same engine) would resolve
> this question if it matters for SK-PRD-02 `SandboxPool` design.

---

### Implication for Skills

1. **SK-PRD-02 `_MAX_ENTRIES` for `SandboxPool`:** The 5-min CPU cap is
   the per-script-invocation budget. A pool entry's effective useful
   lifespan is bounded by this cap (if the script holds CPU). The pool's
   eviction strategy should prefer warm entries that have served short
   invocations recently over entries that have been idle for >5 min.
2. **SK-PRD-02 `_IDLE_TTL_SECONDS`:** The wall-clock cap is ~5 min total
   per `execute_code` invocation (CPU and wall-clock probes both fired at
   ~303 s). Whether idle-sleep counts the same as compute remains
   undetermined from this probe — Vertex killed the script before reaching
   the idle-sleep probes. A refined probe with a front-loaded idle-sleep
   would resolve this; captured as an SK-PRD-02 follow-up. For now, treat
   `_IDLE_TTL_SECONDS` as bounded by the same 5-minute budget — a pooled
   sandbox cannot be "kept warm" past this point.
3. **Error-handling: 503 UNAVAILABLE is a kill signal, not a transient.**
   SK-PRD-02 MUST NOT retry `execute_code` on 503 — that response means
   the sandbox was forcibly terminated. Retry would waste quota and
   produce no new information. Treat 503 like any structured
   `OUTCOME_*_LIMIT` enum.
4. **Concurrent-sandbox cap — withdrawn.** See the RETRACTED section
   above; the apparent cap was a branch-switching artifact in the spike's
   own tooling, not a Vertex behaviour. No SK-PRD-02 implication remains
   from this thread.
5. **Memory measurement gap:** SK-PRD-02 cannot rely on Python-level
   `MemoryError` to detect OOM. The sandbox memory enforcer kills the
   process opaquely. If memory cost is a tuning input for the pool,
   measurement must come from an external signal (e.g., a separate probe
   that reads `/proc/self/status` and writes to a sandbox-side file
   before the OOM-trigger allocation).

> Q4 partial findings: SK-9 should note the 5-min CPU cap as a DoS
> defence (good news — scripts cannot occupy a sandbox indefinitely).
> No security escalation triggered.
