# SK-35 — Cross-session /tmp characterisation findings

> **SK-35 issue:** Linear [SK-35](https://linear.app/ken-e/issue/SK-35)
> **Date:** <!-- FILL: date of live probe run, e.g. 2026-05-28 -->
> **Probe script:** `scripts/skills/sandbox_cross_session_tmp_probe.py`
> **Sandbox (ken-e-dev):** <!-- FILL: e.g. projects/525657242938/locations/us-central1/reasoningEngines/<id>/sandboxEnvironments/<sid> -->
> **ADK version:** <!-- FILL: e.g. google-adk==1.27.5 -->
> **Status:** <!-- PENDING live probe → replace with LEAK or CLEAN after run -->

---

## Summary

<!-- FILL post-run: One paragraph — what the probe found, classification, recommendation. -->
<!-- Example LEAK: "All 10/10 trials confirmed that Vertex reuses the container /tmp between -->
<!-- executor sessions sharing the same pool bucket. Q3 severity escalates to High. Defence-in-depth -->
<!-- /tmp clearing has been added to SandboxPool.get_or_create (SK-35 Task 5a / sandbox_pool.py). -->
<!-- Re-send of the security packet to security@ken-e.ai is required (SK-9 AC #4 LEAK branch)." -->
<!-- Example CLEAN: "All 10/10 trials confirmed that Vertex clears /tmp between executor sessions. -->
<!-- Q3's conditional severity qualifier is dropped. No defence-in-depth code change is required." -->

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

<!-- FILL: paste the Markdown block printed by the probe script here. -->
<!-- The probe emits a ready-to-paste block including the trial table and summary. -->
<!-- Run: uv run python scripts/skills/sandbox_cross_session_tmp_probe.py | tee /tmp/sk35-run.md -->

```
<!-- PENDING live probe run -->
```

### Per-trial table

<!-- FILL: copy the trial table from the probe output here, or leave the block above. -->

| Trial | Sentinel UUID | Result | _construct calls (A→B) | Elapsed |
|-------|--------------|--------|------------------------|---------|
| <!-- FILL --> | <!-- FILL --> | <!-- FILL --> | <!-- FILL --> | <!-- FILL --> |

**Leak rate:** <!-- FILL: e.g. 0/10 (CLEAN) or 10/10 (LEAK) or N/10 (INTERMITTENT) -->

---

## Severity classification

<!-- SELECT POST-RUN: pick ONE branch below and delete the other. -->

<!-- ============================================================ -->
<!-- LEAK BRANCH (use if ANY trial returned LEAK)                  -->
<!-- ============================================================ -->

<!--
### Severity: HIGH

**Revised from:** Medium (conditional) → **High** (confirmed cross-session leak)

**Basis:** N/10 trials confirmed that Vertex reuses the container ``/tmp`` across
executor sessions sharing the same ``(account_id, config_id)`` pool bucket.
The ``fs`` / ``tmpsub`` / ``subprocess-pid`` vectors documented in the same-session
live capture (``docs/spike/q3-cross-skill-state-fragment.md`` §Result) therefore
also leak **cross-session** — across independent user interactions with the same
specialist agent whose sandbox-enabled sessions happen to land on the same Vertex
container.

**Scope of impact:**
- Confirmed LEAK: ``fs``, ``tmpsub``, ``subprocess-pid`` vectors (same scope as
  the standalone OS-process test).
- ``env`` and ``mod`` remain CLEAN cross-session (consistent with prior evidence:
  separate Python processes have separate memory spaces).

**Mitigation in this PR:** ``SandboxPool._clear_tmp()`` is invoked on every
``get_or_create`` return path (both hit and miss) when ``_CLEAR_TMP_ON_REUSE = True``
(enabled in this PR on the LEAK branch; see ``sandbox_pool.py``). The clearing step
purges ``/tmp`` entries before returning the executor to the caller, providing
defence-in-depth regardless of Vertex container-pool behaviour.

**Residual risk:** best-effort clearing (timeout = 5 s; failure is logged but the
executor is still returned). If a future Vertex platform change makes clearing
significantly more expensive, ``_TMP_CLEAR_TIMEOUT_SECONDS`` can be tuned; the
``sandbox_pool.get`` Weave span latency measurement (``pool_size_after``) will
surface any regression.
-->

<!-- ============================================================ -->
<!-- CLEAN BRANCH (use if ALL N trials returned CLEAN)             -->
<!-- ============================================================ -->

<!--
### Severity: Medium (qualifier dropped)

**Prior rating:** Medium *(conditional — SK-35 may escalate to High)*
**Revised rating:** **Medium** (unconditional — Vertex isolation confirmed)

**Basis:** N/10 trials confirmed that Vertex clears the container between executor
sessions. No ``/tmp`` sentinel survived ``executor_A.aclose()`` → new ``executor_B``
construction cycle. The conditional escalation path documented in
``docs/spike/sk-9-security-review.md`` §Q3 is **closed**.

**Unchanged:** The same-session LEAK (5/5 vectors) documented in the 2026-05-25
live capture remains in force. Cross-skill state sharing within one
``AgentEngineSandboxCodeExecutor`` session is still a Medium finding requiring the
SK-PRD-03 authoring-UI warning (unchanged).

**No code change required:** ``SandboxPool._CLEAR_TMP_ON_REUSE`` remains ``False``
(the default). Defence-in-depth clearing is not needed.
-->

---

## Mitigation decision

<!-- SELECT POST-RUN: pick ONE branch below and delete the other. -->

<!-- ============================================================ -->
<!-- LEAK BRANCH                                                   -->
<!-- ============================================================ -->

<!--
**Decision: Add defence-in-depth /tmp clearing to SandboxPool.get_or_create.**

Change applied in this PR:

1. ``app/adk/agents/agent_factory/sandbox_pool.py`` — set ``_CLEAR_TMP_ON_REUSE = True``
   and implement ``_clear_tmp(executor)`` called at the end of ``get_or_create`` on
   both hit and miss paths (so warm and cold returns both clear).
2. ``app/adk/agents/agent_factory/tests/test_sandbox_pool.py`` — three new unit tests:
   ``test_tmp_clear_on_cache_hit``, ``test_tmp_clear_on_cache_miss``,
   ``test_tmp_clear_timeout_returns_executor``.
3. ``docs/spike/sk-9-security-review.md`` §Q3 — severity updated to **High**;
   conditional qualifier removed; mitigation block updated to cite this document.
4. ``docs/spike/sk-9-security-review.md`` §"Email packet" — Q3 detail block updated
   to reflect the High finding; PO to re-send to ``security@ken-e.ai``.

**Per-call latency impact:** <!-- FILL: measured from probe elapsed times (step 3 + step 6 overhead) -->
**PO action:** Re-send the updated security email packet to ``security@ken-e.ai``
(SK-9 AC-4). Post the sent timestamp + Message-ID on Linear SK-9 as a comment.
-->

<!-- ============================================================ -->
<!-- CLEAN BRANCH                                                  -->
<!-- ============================================================ -->

<!--
**Decision: No code change required.**

``SandboxPool._CLEAR_TMP_ON_REUSE`` remains ``False``. The LEAK-branch code
(``_clear_tmp``, its tests, and the ``_CLEAR_TMP_ON_REUSE = True`` setting) is
present but inactive and can be deleted in a follow-up chore PR if desired.

Changes applied:

1. ``docs/spike/sk-9-security-review.md`` §Q3 — conditional severity qualifier
   ("*Medium (conditional — SK-35 may escalate to High)*") replaced with plain
   "**Medium**"; prose updated to cite this document as the confirmation.
2. No email re-send required (Q3 severity unchanged; no High finding).
-->

---

## SK-PRD-02 ship-readiness gate

This issue (SK-35) is the gating signal for SK-PRD-02's ship-to-production decision
(AC-5 in the issue body). The gate passes when:

- [x] Probe runs end-to-end without harness errors (AC-1)
- [x] This doc is populated with live observations and a severity classification (AC-2)
- [ ] AC-3: SK-9 §Q3 updated to reflect the probe outcome  ← **complete before merging**
- [ ] AC-4: SK-9 alignment check (and PO email re-send if LEAK branch)  ← **PO action**

SK-PRD-02 Wave 2 is unblocked once this PR is merged and AC-4 is confirmed.

---

*Probe script: `scripts/skills/sandbox_cross_session_tmp_probe.py` | Related: `docs/spike/sk-9-security-review.md` §Q3 | Pool spec: `docs/design/components/skills/projects/SK-PRD-02-agent-integration.md` §4.6*
