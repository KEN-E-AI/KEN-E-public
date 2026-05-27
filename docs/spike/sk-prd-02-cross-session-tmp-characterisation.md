# SK-35 — Cross-session /tmp characterisation findings

> **SK-35 issue:** Linear [SK-35](https://linear.app/ken-e/issue/SK-35)
> **Date:** 2026-05-27
> **Probe script:** `scripts/skills/sandbox_cross_session_tmp_probe.py`
> **Sandbox (ken-e-dev):** `projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568/sandboxEnvironments/8580220406768599040` (reused from SK-PRD-00 spike — `sk-prd-00-spike-sandbox`)
> **ADK version:** google-adk==1.27.5, vertexai==1.134.0
> **Status:** **LEAK** (50/50 trials)

---

## Summary

All 50/50 trials confirmed that Vertex reuses the container `/tmp` between
`AgentEngineSandboxCodeExecutor` sessions sharing the same `sandboxEnvironments/<sid>`
resource — `pool.evict()` followed by a fresh `pool.get_or_create()` for the same key
returns a new executor object, but the underlying Vertex sandbox container persists
and `/tmp` retains entries written by the previous session. Q3 severity in
[`docs/spike/sk-9-security-review.md`](./sk-9-security-review.md) escalates from
**Medium (conditional)** to **High**. Defence-in-depth `/tmp` clearing is now active in
`SandboxPool.get_or_create` (`_CLEAR_TMP_ON_REUSE = True` in
[`app/adk/agents/agent_factory/sandbox_pool.py`](../../app/adk/agents/agent_factory/sandbox_pool.py)).
Re-send of the security packet to `security@ken-e.ai` is required per SK-9 AC #4 LEAK
branch.

---

## Methodology

The probe exercises the **production** ``SandboxPool`` lifecycle rather than a direct
``AgentEngineSandboxCodeExecutor`` construction, because the security question is about
**pool-reuse semantics** — whether ``aclose()``-on-eviction actually causes Vertex to
discard (or preserve) the container when a new executor is constructed for the same
sandbox resource name.

### Probe mechanics (per trial)

```
Trial N:
  1. pool.evict(key)              — ensure no residual entry (clean trial start)
  2. executor_A = await pool.get_or_create(key)   — cache MISS → _construct called
  3. execute_in_sandbox(write_sentinel_code)       — writes /tmp/kene-probe-<uuid>
  4. await pool.evict(key, reason="manual")        — calls executor_A.aclose()
  5. executor_B = await pool.get_or_create(key)   — cache MISS → _construct called again
  6. execute_in_sandbox(read_sentinel_code)        — checks if /tmp/kene-probe-<uuid> exists
  7. Record: LEAK (file found) or CLEAN (file not found)
```

Step 4 (``aclose()``) is the load-bearing step: it should cause Vertex to release the
sandbox handle. Step 5 constructs a new executor for the same resource name. If Vertex
reuses the same container (warm-pool behaviour), the sentinel from step 3 survives into
step 6 — a cross-session LEAK. If Vertex allocates a fresh container (cold-start
isolation), the sentinel is absent — CLEAN.

### Pool subclass

``_ProbeSandboxPool`` inherits all production pool code (LRU, idle-TTL, striped locks,
``aclose()``-on-eviction, Weave spans) and only overrides ``_construct`` to route to the
real ``sandboxEnvironments/<sid>`` path from ``KENE_SK35_AGENT_ENGINE_RESOURCE_NAME``
instead of the PRD-placeholder format. A ``construct_count`` attribute tracks how many
times ``_construct`` is called per trial so inconclusive results (where Vertex returned a
cache hit rather than a fresh executor) can be flagged.

### Resource lifecycle

A fresh throwaway sandbox was provisioned on ``ken-e-dev`` for this probe, mirroring the
SK-PRD-00 spike-resource lifecycle documented in
[``docs/spike/sk-9-security-review.md``](./sk-9-security-review.md) (§Methodology).
The sandbox resource name is recorded in the header above. Post-merge deletion is a
separate operations step (analogous to SK-10's cleanup; tracked in the Linear issue
comment on SK-35).

### Related evidence

* ``docs/spike/q3-cross-skill-state-fragment.md`` §"Standalone process validation" —
  confirmed that ``fs``/``tmpsub``/``subprocess-pid`` vectors LEAK across separate
  ``uv run python`` invocations sharing a host ``/tmp``. That test established the
  lower-level OS-process isolation model. This probe answers the higher-level Vertex
  container-pool question.
* ``docs/spike/sk-9-security-review.md`` §Q3 — the conditional Medium severity this
  probe resolves.
* ``app/adk/agents/agent_factory/sandbox_pool.py`` §``SandboxPool`` — the production
  pool whose ``get_or_create`` / ``evict`` lifecycle is exercised here.

---

## Raw observations

Probe markdown summary (full output captured to `/tmp/sk35/findings.md` during the
2026-05-27 run; reproduced below):

```
## SK-35 Probe Run — 2026-05-27T20:39:03Z

**Sandbox:** `projects/525657242938/locations/us-central1/reasoningEngines/2624457839443181568/sandboxEnvironments/8580220406768599040`
**Pool key:** `('sk35-acc-v2', 'sk35-cfg-v2')`
**ADK version:** 1.27.5
**Trials:** 50
**Leak rate:** 50/50
**Classification:** **LEAK — all 50 trials confirmed /tmp reuse across executor sessions**
```

A first probe attempt (recorded in `/tmp/sk35/findings.md` from an earlier run, not
reproduced here) classified all 50 trials as `PROBE_ERROR_UNEXPECTED: read_stdout=''`.
Root cause was an SDK-shape change: `vertexai==1.134.0` returns
`Chunk(data=bytes_json, mime_type='application/json')` from
`agent_engines.sandboxes.execute_code(...)`, whereas the original probe parser expected
the legacy `code_execution_result.output` attribute. The script was updated in this PR
(`scripts/skills/sandbox_cross_session_tmp_probe.py:_execute_in_sandbox`) to decode the
JSON payload's `msg_out` / `msg_err` fields; the re-run reproduced above is the
authoritative result.

**Independent confirmation of the LEAK signal** (sanity check before the script fix):
a one-off `execute_code` call against the same sandbox, made outside any pool, observed
all 50 sentinels from the first (failed) probe attempt still resident in `/tmp` — 51
entries total including `matplotlib_config_dir`. That side-channel evidence and the
50/50 LEAK trial table agree on the same conclusion: Vertex reuses the container
behind a stable `sandboxEnvironments/<sid>` resource name across executor sessions.

### Per-trial table

All 50 trials returned `LEAK`. `_construct calls (A→B)` increments by 2 per trial (one
call for executor_A on the post-evict cache miss, one for executor_B on the next
cache miss), confirming the `evict → get_or_create` cycle actually hit the construct
path both times (no residual cache hit masking the result).

| Trial | Sentinel UUID | Result | _construct calls (A→B) | Elapsed |
|-------|--------------|--------|------------------------|---------|
| 1 | sk35-t001-9c90a6a06e55 | LEAK | 1→2 | 2.39s |
| 2 | sk35-t002-f0482bac5279 | LEAK | 3→4 | 1.14s |
| 3 | sk35-t003-06e66c3fdc2d | LEAK | 5→6 | 1.11s |
| 4 | sk35-t004-eeb0d65dfd23 | LEAK | 7→8 | 1.16s |
| 5 | sk35-t005-2c466a94c180 | LEAK | 9→10 | 1.04s |
| 6 | sk35-t006-5b8c53bc043e | LEAK | 11→12 | 1.23s |
| 7 | sk35-t007-729f9a9a9ca0 | LEAK | 13→14 | 1.19s |
| 8 | sk35-t008-49d908b6e3bb | LEAK | 15→16 | 1.96s |
| 9 | sk35-t009-dfe8a0b02f4e | LEAK | 17→18 | 1.29s |
| 10 | sk35-t010-505ecb5bc62c | LEAK | 19→20 | 1.27s |
| 11 | sk35-t011-33bab8e5d4f5 | LEAK | 21→22 | 1.31s |
| 12 | sk35-t012-0954d6f535a2 | LEAK | 23→24 | 1.14s |
| 13 | sk35-t013-a239c4f0ad50 | LEAK | 25→26 | 1.08s |
| 14 | sk35-t014-a6e5102cbb6f | LEAK | 27→28 | 1.02s |
| 15 | sk35-t015-c6a9649f9a9a | LEAK | 29→30 | 1.21s |
| 16 | sk35-t016-85848c8463ee | LEAK | 31→32 | 1.17s |
| 17 | sk35-t017-6f1a3f8a7678 | LEAK | 33→34 | 1.12s |
| 18 | sk35-t018-41156c72e0a5 | LEAK | 35→36 | 1.35s |
| 19 | sk35-t019-aaf4b37e7c0d | LEAK | 37→38 | 1.66s |
| 20 | sk35-t020-1a9a7af646b1 | LEAK | 39→40 | 1.46s |
| 21 | sk35-t021-6be536243230 | LEAK | 41→42 | 1.45s |
| 22 | sk35-t022-9c6ff0dc495a | LEAK | 43→44 | 1.48s |
| 23 | sk35-t023-94dfe7c46bb2 | LEAK | 45→46 | 1.62s |
| 24 | sk35-t024-a3c4302a463d | LEAK | 47→48 | 1.39s |
| 25 | sk35-t025-5e6d7b414b14 | LEAK | 49→50 | 1.33s |
| 26 | sk35-t026-17898b0cb18c | LEAK | 51→52 | 1.31s |
| 27 | sk35-t027-069fc07f9032 | LEAK | 53→54 | 1.27s |
| 28 | sk35-t028-773dd9503731 | LEAK | 55→56 | 1.25s |
| 29 | sk35-t029-5e558f482610 | LEAK | 57→58 | 1.22s |
| 30 | sk35-t030-3a241814c37c | LEAK | 59→60 | 1.24s |
| 31 | sk35-t031-b85969717deb | LEAK | 61→62 | 1.39s |
| 32 | sk35-t032-235a377ea54d | LEAK | 63→64 | 1.20s |
| 33 | sk35-t033-33a80c3514ae | LEAK | 65→66 | 1.11s |
| 34 | sk35-t034-61c42a4bf3d1 | LEAK | 67→68 | 1.19s |
| 35 | sk35-t035-cbc100493dab | LEAK | 69→70 | 1.16s |
| 36 | sk35-t036-f96804807deb | LEAK | 71→72 | 1.27s |
| 37 | sk35-t037-f74eb60ddc6f | LEAK | 73→74 | 1.11s |
| 38 | sk35-t038-cd81a56980de | LEAK | 75→76 | 1.25s |
| 39 | sk35-t039-1897fb57757b | LEAK | 77→78 | 1.18s |
| 40 | sk35-t040-874478157a84 | LEAK | 79→80 | 1.09s |
| 41 | sk35-t041-38b50f82b004 | LEAK | 81→82 | 1.09s |
| 42 | sk35-t042-10d66859bb5a | LEAK | 83→84 | 1.11s |
| 43 | sk35-t043-f8d1aac5a34d | LEAK | 85→86 | 1.17s |
| 44 | sk35-t044-26b212275153 | LEAK | 87→88 | 1.12s |
| 45 | sk35-t045-a80d8396d4c7 | LEAK | 89→90 | 1.45s |
| 46 | sk35-t046-bf609f10a8ed | LEAK | 91→92 | 1.83s |
| 47 | sk35-t047-c20e38a9b860 | LEAK | 93→94 | 1.24s |
| 48 | sk35-t048-fd5f51a87a77 | LEAK | 95→96 | 1.08s |
| 49 | sk35-t049-72fb8909281a | LEAK | 97→98 | 1.11s |
| 50 | sk35-t050-01e06b90d745 | LEAK | 99→100 | 1.16s |

**Leak rate:** 50/50 (LEAK)

**`executor.aclose()` side note.** The pool's eviction path logged
`AttributeError: 'AgentEngineSandboxCodeExecutor' object has no attribute 'aclose'`
on every trial. ADK 1.27.5's `AgentEngineSandboxCodeExecutor` does not expose `aclose()`;
the pool's try/except catches and logs this so pool integrity is preserved (the entry is
still removed). This is operationally consistent with the LEAK finding — without a real
close hook, the Vertex container behind the resource name persists, which is exactly
what the trial table records. Separately tracked as a SK-PRD-02 follow-up for an
ADK-side close contract (or a SandboxPool change to drop the `aclose()` call when ADK
does not expose it).

---

## Severity classification

### Severity: HIGH

**Revised from:** Medium (conditional) → **High** (confirmed cross-session leak)

**Basis:** 50/50 trials confirmed that Vertex reuses the container `/tmp` across
executor sessions sharing the same `sandboxEnvironments/<sid>` resource. The
`fs` / `tmpsub` / `subprocess-pid` vectors documented in the same-session live
capture (`docs/spike/q3-cross-skill-state-fragment.md` §Result) therefore also leak
**cross-session** — across independent user interactions with the same specialist
agent whose sandbox-enabled sessions land on the same Vertex container behind a
stable resource name.

The `SandboxPool` keying by `(account_id, config_id)` maps each agent config to one
deterministic `sandboxEnvironments/<sid>` path (see `_sandbox_resource_name` in
`sandbox_pool.py`), so cross-session reuse within a single account+config bucket is
the load-bearing failure mode. Cross-account / cross-config buckets remain isolated
by construction (different resource names → different containers); no cross-account
leak was observed or is architecturally possible given the keying scheme.

**Scope of impact:**
- Confirmed LEAK: `fs`, `tmpsub`, `subprocess-pid` vectors (same scope as the
  standalone OS-process test in SK-PRD-00).
- `env` and `mod` remain CLEAN cross-session (consistent with prior evidence:
  separate Python processes have separate memory spaces).

**Mitigation in this PR:** `SandboxPool._clear_tmp()` is invoked on every
`get_or_create` return path (both cache hit and cache miss) now that
`_CLEAR_TMP_ON_REUSE = True` in `sandbox_pool.py`. The clearing step purges `/tmp`
entries before returning the executor to the caller, providing defence-in-depth
regardless of Vertex container-pool behaviour.

**Residual risk:** best-effort clearing (timeout = 5 s; failure is logged at WARNING
and surfaced as `tmp_clear_failed=true` on the `sandbox_pool.get` Weave span; the
executor is still returned to preserve pool integrity). MER-E alerts on
`count(sandbox_pool.get where tmp_clear_failed=true) > 0` over a 5-minute window to
catch degraded mitigation in production.  If a future Vertex platform change makes
clearing significantly more expensive, `_TMP_CLEAR_TIMEOUT_SECONDS` can be tuned.

---

## Mitigation decision

**Decision: Add defence-in-depth /tmp clearing to SandboxPool.get_or_create.**

Changes applied in this PR:

1. `app/adk/agents/agent_factory/sandbox_pool.py` — `_CLEAR_TMP_ON_REUSE = True`;
   `_clear_tmp(executor)` invoked on every `get_or_create` return path (both hit and
   miss). Defensive guard short-circuits when `sandbox_resource_name` is missing or
   non-string so Mock executors in unit tests do not trigger network calls.
2. `app/adk/agents/agent_factory/tests/test_sandbox_pool.py` — three unit tests
   already shipped in PR #720 (`test_tmp_clear_on_cache_hit`,
   `test_tmp_clear_on_cache_miss`, `test_tmp_clear_timeout_returns_executor`); they
   continue to pass with the flag flipped (all 25 sandbox-pool tests green).
3. `docs/spike/sk-9-security-review.md` §Q3 — severity updated to **High**;
   conditional qualifier removed; mitigation block updated to cite this document.
4. `docs/spike/sk-9-security-review.md` §"Email packet" — Q3 detail block replaced
   with the LEAK-branch HIGH template; PO action below.
5. `scripts/skills/sandbox_cross_session_tmp_probe.py:_execute_in_sandbox` — updated
   to parse the `vertexai==1.134.0` `Chunk(data=bytes_json, ...)` response shape.
   Required to make the probe actually report results against the current SDK.

**Per-call latency impact — vertexai.Client construction:** the `vertexai.Client`
construction overhead (expected tens of ms for auth resolution + gRPC channel setup)
has been **eliminated as a per-call cost** by SK-43.  `_clear_tmp` now calls the
module-level `_get_vertexai_client(project, location)` (decorated with
`@functools.lru_cache(maxsize=2)`), so the client is constructed once per
`(project, location)` pair for the lifetime of the Cloud Run instance.  The
`sandbox_pool.get` Weave span carries a new `client_cache_hit: bool` attribute
so MER-E can monitor cache health in production.  Precise construction-latency
numbers (mean / p95 / max from 100 iterations) will be captured by a PO or Test
Team member running `scripts/skills/measure_vertexai_client_init.py` on a
credentialled workstation and posted as a comment on SK-43 (AC-3).

**Per-call latency impact — execute_code round-trip:** not directly measured
(the probe ran with `_CLEAR_TMP_ON_REUSE = False` so the trial timings do not
include `/tmp` clearing). Observed `execute_code` round-trip on the same sandbox
averaged ~1.2 s (range 1.0 – 2.4 s); `_clear_tmp` issues one `execute_code` call
per `get_or_create`, so first-order expectation is roughly +1 s on every pool
hit / miss. The `sandbox_pool.get` Weave span carries `pool_size_after`,
`tmp_clear_failed`, and `client_cache_hit`, and the span duration captures
end-to-end latency for downstream MER-E monitoring.

Two known optimisations are tracked as follow-ups, **both prioritised before
SK-PRD-02 takes broad production traffic**:

* [SK-43](https://linear.app/ken-e/issue/SK-43) — cache the `vertexai.Client`
  instance to amortise client init across calls. **Landed** (see PR linked to
  SK-43): `_get_vertexai_client(project, location)` with `lru_cache(maxsize=2)`
  is now in `sandbox_pool.py`; thread-safety verified against the Python gRPC
  documentation (gRPC channels are thread-safe); `client_cache_hit` attribute
  added to the `sandbox_pool.get` span for MER-E monitoring.
* `_TMP_CLEAR_TIMEOUT_SECONDS` tuning — currently 5 s; lower if Vertex round-trip
  improves and we want to bound worst-case `_clear_tmp` overhead more tightly.

Under AH-PRD-09 per-turn dispatch, the per-call latency is load-bearing because
every chat turn that uses a sandbox-enabled specialist pays this overhead.  SK-43
should close most of the gap.

**PO action:** Re-send the updated security email packet to `security@ken-e.ai`
(SK-9 AC-4). Post the sent timestamp + Message-ID on Linear SK-9 as a comment.

---

## SK-PRD-02 ship-readiness gate

This issue (SK-35) is the gating signal for SK-PRD-02's ship-to-production decision
(AC-5 in the issue body). The gate passes when:

- [x] Probe runs end-to-end without harness errors (AC-1) — 50-trial probe, 2026-05-27
- [x] This doc is populated with live observations and a severity classification (AC-2)
- [x] AC-3: SK-9 §Q3 updated from Medium *(conditional)* to **High** in this PR
- [ ] AC-4: SK-9 alignment check + PO email re-send to `security@ken-e.ai`  ← **PO action**

SK-PRD-02 Wave 2 is unblocked once this PR is merged and AC-4 is confirmed.

---

*Probe script: `scripts/skills/sandbox_cross_session_tmp_probe.py` | Related: `docs/spike/sk-9-security-review.md` §Q3 | Pool spec: `docs/design/components/skills/projects/SK-PRD-02-agent-integration.md` §4.6*
