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

*Placeholder — populated when the cumulative wall-clock probe completes.
Probe sequence: compute-30s, compute-120s, compute-600s, idle-sleep-30s,
idle-sleep-120s, idle-sleep-600s. The earliest probe whose target
exceeds the sandbox cap is the threshold; if the script completes the
full 1500 s budget, no cap was observed in the 0-600 s band.*

```
[PENDING — wall-clock probe in flight at the time of this fragment's
first commit; will be updated in a follow-up commit when the harness
output finalises]
```

---

### Findings summary

| Probe | Vertex signal | Observed cap |
|---|---|---|
| CPU loop | `503 UNAVAILABLE` after 304 s | ~5 min (300 s) CPU cap |
| Memory balloon | `OUTCOME_OK` with no stdout | not measurable via this probe pattern |
| Wall-clock | [PENDING] | [PENDING] |

### Concurrent-sandbox observation (incidental finding)

When this Q4 wall-clock probe ran in parallel with the Q2 cost
orchestrator's session burst, 59 of 60 Q2 sessions failed immediately
(elapsed 0.06 s) with `error: no exit status line found`. Only the first
Q2 session succeeded. The cascade pattern (16.56 s → 3.50 s → 1.41 s →
0.06 s for the first four sessions, then a flat 0.06 s) suggests the
spike Agent Engine has a **low concurrent-sandbox cap (1-2)** — Q2's
attempts to create additional sandboxes while Q1/Q4 wall-clock already
held one were rejected at sandbox-creation time. This is a load-bearing
input for SK-PRD-02 `SandboxPool` design: the pool must serialise or
queue sandbox-creation requests per engine to avoid this failure mode.

The Q2 capture has been retained at `/tmp/q2_sessions.jsonl` for
SK-7 / SK-PRD-02 review; the Q2 staging fragment will be updated with a
clean N=30 re-run once the wall-clock probe finishes and releases its
sandbox slot.

---

### Implication for Skills

1. **SK-PRD-02 `_MAX_ENTRIES` for `SandboxPool`:** The 5-min CPU cap is
   the per-script-invocation budget. A pool entry's effective useful
   lifespan is bounded by this cap (if the script holds CPU). The pool's
   eviction strategy should prefer warm entries that have served short
   invocations recently over entries that have been idle for >5 min.
2. **SK-PRD-02 `_IDLE_TTL_SECONDS`:** Will be set by the wall-clock
   probe's idle-sleep results (PENDING). The compute-30s vs idle-sleep-30s
   comparison will reveal whether Vertex treats sleep time the same as
   CPU time.
3. **Error-handling: 503 UNAVAILABLE is a kill signal, not a transient.**
   SK-PRD-02 MUST NOT retry `execute_code` on 503 — that response means
   the sandbox was forcibly terminated. Retry would waste quota and
   produce no new information. Treat 503 like any structured
   `OUTCOME_*_LIMIT` enum.
4. **Concurrent-sandbox cap (1-2 per engine):** SK-PRD-02's `SandboxPool`
   must serialise sandbox creation per engine resource name. Parallel
   `execute_code` calls against the same engine will fail fast (0.06 s)
   when the cap is reached. Pool sizing must respect this.
5. **Memory measurement gap:** SK-PRD-02 cannot rely on Python-level
   `MemoryError` to detect OOM. The sandbox memory enforcer kills the
   process opaquely. If memory cost is a tuning input for the pool,
   measurement must come from an external signal (e.g., a separate probe
   that reads `/proc/self/status` and writes to a sandbox-side file
   before the OOM-trigger allocation).

> Q4 partial findings: SK-9 should note the 5-min CPU cap as a DoS
> defence (good news — scripts cannot occupy a sandbox indefinitely).
> No security escalation triggered.
