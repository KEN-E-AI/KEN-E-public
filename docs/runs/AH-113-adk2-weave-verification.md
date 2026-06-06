# AH-113 — ADK 2.0 Weave Trace Verification Runbook & Evidence Log

**Issue:** [AH-113](https://linear.app/ken-e/issue/AH-113) — Verify Weave tracing survives the 2.0 event shape + document span deltas for MER-E  
**PRD:** `docs/design/components/agentic-harness/projects/AH-PRD-13-adk2-foundation.md` §7 AC #9 + §2 (Tracing) + §9 (Weave autopatch fragility)  
**Branch:** `feat/AH-113-weave-tracing-adk2-verification`  
**Date authored:** 2026-06-06  
**Executed by:** Operator with `ken-e-dev` + `ken-e-staging` ADC (agent VM blocked by cross-project IAM — see §0)

---

## §0 — IAM Prerequisite

The Dev Team agent VM (`fun-e-agent-vm@fun-e-business.iam.gserviceaccount.com`) lacks:
- `storage.buckets.get` on `gs://ken-e-dev-adk-staging`
- `aiplatform.reasoningEngines.create` on `ken-e-dev`

These are the same blockers documented in `docs/spike-ah104-deploy-sandbox-weave.md` §3.1
and inherited by `docs/runs/AH-111-adk2-deploy-smoke.md` §0.  
All live commands below **must be run by a developer/PO** with full `ken-e-dev` ADC.

```bash
# Configure ADC for ken-e-dev before running any command below
gcloud auth application-default login
gcloud config set project ken-e-dev
```

---

## §1 — Pre-Deploy Invariants

Verified by the Dev Team agent before opening the PR. Run these to confirm before executing live probes.

### 1.1 Version pins aligned

```bash
grep "google-adk" pyproject.toml api/pyproject.toml app/adk/pyproject.toml app/adk/requirements.txt
```

Expected: `google-adk[mcp]==2.0.0` in all four files.

### 1.2 AH-110 / AH-111 parity suite green

```bash
uv run python -m pytest \
    app/adk/agents/agent_factory/tests/test_chat_billing_parity.py \
    app/adk/agents/agent_factory/tests/test_adk2_session_roundtrip.py \
    app/adk/agents/agent_factory/tests/test_adk2_loop_agent_billing.py \
    -q
```

Expected: **68 passed** (count may grow; any number ≥ 68 is acceptable).

### 1.3 Weave-tier offline regression suite green

```bash
uv run python -m pytest app/adk/tracking/tests/ -v
```

Expected: all tracking tests pass, including:
- `test_no_adk2_event_field_consumers.py::test_no_adk2_event_fields_in_production_tracking`
- `test_transfer_to_specialist_fixture.py::TestEmissionStatus::test_emitted_spans_are_exactly_the_runtime_set`

**Pre-deploy invariants — Agent-verified result (2026-06-06):**

| Check | Result |
|---|---|
| `google-adk==2.0.0` in all 4 manifests | ✅ VERIFIED (via AH-111) |
| AH-110 parity suite 68/68 | ✅ VERIFIED (via AH-111) |
| Weave-tier offline suite | ✅ VERIFIED (AH-113 PR CI) |

---

## §2 — Probe 10 — Session Round-Trip + Weave Init Check

Reuses `docs/spike-adk2/probe-10-deploy-session-weave.py` verbatim. This probe was authored for AH-111
§3.3; this runbook reuses it for the Weave-specific signals it already captures.

Full procedure: see `docs/runs/AH-111-adk2-deploy-smoke.md` §3.3.

Summary of what Probe 10 captures relevant to AH-113:

1. **Weave init** — calls `init_weave_if_needed(required=False)`; records `True`/`False` and reason.
2. **`@safe_weave_op` round-trip** — if Weave init returned `True`, decorates a probe function and verifies a span was emitted (the op decorator path works on 2.0).
3. **`google.genai` LLM-call autopatch** — inspects the `google.genai` module's integration registry; records whether the autopatch is present (`True`) or absent (`False`). Per AH-PRD-13 §9, absence is a pre-existing 1.34.1 condition and is **non-blocking** — record it, don't block on it.

```bash
# From repo root; ENGINE_ID must be set (see AH-111 §3)
ENGINE_ID=$(gcloud secrets versions access latest \
    --secret=ken-e-engine-id \
    --project=ken-e-dev)
# docs/spike-adk2/.spike_engine_id is in .gitignore — safe to write here.
echo "$ENGINE_ID" > docs/spike-adk2/.spike_engine_id

uv run python docs/spike-adk2/probe-10-deploy-session-weave.py \
    2>&1 | tee /tmp/ah113-dev-probe10.log
echo "probe-10 exit=$?"
```

**Expected:** exit 0. Both `weave_init_result` and `google_genai_autopatch` are informational;
the Weave init returning `False` (e.g. absent `WANDB_API_KEY`) is acceptable per AH-PRD-13 §9.

> ⚠️ **Procedure correction (found during operator execution 2026-06-06):** `probe-10` contains
> a hard safety guard (`_CANONICAL_ENGINE_ID` check, ~line 237) that **aborts with exit 1 if
> `.spike_engine_id` points at the canonical engine** `5957383247464759296`. The `ken-e-engine-id`
> Secret Manager value *is* the canonical engine resource, so the command block above (which writes
> that secret into `.spike_engine_id`) cannot run `probe-10` end-to-end — it is rejected by design.
> `probe-10` is intended for an **ephemeral** engine from `spike_deploy.py --keep`.
>
> **How AC #9 was actually verified (2026-06-06):**
> 1. The **deployed-engine session round-trip** leg is already evidenced by AH-112 Probe 12
>    (Leg A synthesised round-trip + Leg B live turn storing 3 events) against the canonical 2.0
>    engine — see `docs/runs/AH-112-managed-session-roundtrip.md` §2.2.
> 2. The **engine-independent Weave legs** of `probe-10` (`_run_weave_check`) were executed directly
>    with the real `WANDB_API_KEY` (Secret Manager `wandb-api-key`, project `ken-e-dev`) on the
>    ADK 2.0 venv. Results below.

**Probe 10 Weave-check result (operator-executed 2026-06-06, ADK 2.0.0, `WANDB_API_KEY` from `ken-e-dev`):**

| Field | Value |
|---|---|
| Exit code | 0 (Weave-check legs) |
| Deployed-engine session round-trip | PASS (via AH-112 Probe 12 — 3 events stored, round-trip verified) |
| `weave_init_result` | **True** — `weave.init(project="ken-e-dev")` succeeded under ADK 2.0 (logged in as `kenwilly`) |
| `op_call_succeeded` | **True** — `@safe_weave_op` decorated fn returned 42 and emitted a span: `https://wandb.ai/ken-e/ken-e-dev/r/call/019e9dd6-efc7-7648-ab67-4e6db101168c` |
| `google_genai_autopatch` | **False** — autopatch registry empty; `google.genai` LLM-call autopatch absent → **carry-forward** per AH-PRD-13 §9 (pre-existing, not a 2.0 regression) |
| Notes | A prior run without `WANDB_API_KEY` returned `weave_init_result=False` (the documented §9 carry-forward path); `init_weave_if_needed` raised no exception under ADK 2.0 in either case. |

---

## §3 — Supplementary Live `@safe_weave_op` Span Capture

Run after §2 if `weave_init_result` is `True`. Sends a chat turn via the `API_TEST_BYPASS_TOKEN`
SSE curl and inspects the resulting Weave trace for the expected span set.

### 3.1 SSE curl — dispatch a single-specialist turn

```bash
BYPASS_TOKEN="<API_TEST_BYPASS_TOKEN from Secret Manager>"
API_URL="https://api.ken-e-dev.ai"   # or the Cloud Run URL for ken-e-api-dev

curl -X POST "${API_URL}/api/v1/accounts/test-account/chat" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${BYPASS_TOKEN}" \
    -H "Accept: text/event-stream" \
    -d '{"message": "What were my top 5 pages last week? Use Google Analytics.", "stream": true}' \
    --no-buffer \
    2>&1 | tee /tmp/ah113-dev-sse-span-capture.log
echo "SSE curl exit=$?"
```

**Expected:** SSE stream with `data:` lines containing text events; final `data: [DONE]` or
equivalent turn-complete event. The turn must route to the `google_analytics_specialist` via
`transfer_to_agent`.

### 3.2 Weave UI span inspection

After the turn completes, open the Weave project for `ken-e-dev` and locate the trace for
this session. Capture the span names and compare to the canonical set in
`app/adk/tracking/tests/fixtures/transfer_to_specialist_trace.json`:

**Expected emitted span set (single-specialist turn):**

| Span | `emission_status` |
|---|---|
| `ken_e` (root) | `emitted` |
| `transfer_to_agent` | `emitted` |
| `google_analytics_specialist` | `emitted` |
| `google_analytics_specialist_worker` | `emitted` |
| `google_analytics_specialist_review_reviewer` | `deferred` (not present in live traces) |

If any span in the `emitted` set is absent, or if a span not in the fixture appears, record it
in §5 and classify per the verdict guide below.

**Verdict guide:**

| Observation | Classification |
|---|---|
| All `emitted` spans present, no unexpected additions | ✅ GO (no delta) |
| A known `deferred` span now appears | INDETERMINATE — record as potential future change; not a regression |
| An `emitted` span is absent | ❌ NO-GO — regression vs 1.34.1 baseline |
| An unexpected new span appears | INDETERMINATE — open follow-up for MER-E assessment |
| `google.genai` LLM-call span absent | ✅ GO (carry-forward; see §3.3 below) |

**Live span capture result:**

> **Status (2026-06-06): offline-evidenced; visual Weave-UI diff remains an optional operator confirmation.**
> The `@safe_weave_op` span-emission path is confirmed working under ADK 2.0 (see §2 — span
> `019e9dd6-…` created in `wandb.ai/ken-e/ken-e-dev`). The single-specialist span *shape* is
> guarded offline by `test_no_adk2_event_field_consumers.py` (no production tracking module reads
> `node_info`/`isolation_scope`, so the emitter cannot change shape on 2.0) plus the emission-status
> lock in `test_transfer_to_specialist_fixture.py` — both green on `google-adk==2.0.0`. A live turn
> was dispatched to the deployed engine (AH-112 Probe 12 Leg B); the full visual span-name diff in
> the Weave UI is left as a low-risk optional confirmation.

| Field | Value |
|---|---|
| Weave project URL | `https://wandb.ai/ken-e/ken-e-dev/weave` |
| Trace ID | `@safe_weave_op` probe span: `019e9dd6-efc7-7648-ab67-4e6db101168c` (deployed-turn trace: dispatched via Probe 12 Leg B, session `3374245673468690432`) |
| Observed span names | Offline-locked to the fixture's `emitted` set via `test_transfer_to_specialist_fixture.py` (green on 2.0); live UI diff not separately captured |
| Delta vs fixture's emitted set | none expected — emitter does not read the 2.0 additive fields (offline guard green) |
| Notes | Visual Weave-UI span-name capture is the one residual manual step; risk is low given the offline shape guard. |

### 3.3 `google.genai` LLM-call span — carry-forward classification

Per AH-PRD-13 §9: the `google.genai` LLM-call span (`google.genai.generate_content` or similar)
may be absent in both 1.34.1 and 2.0 traces due to a known Weave autopatch fragility. This is a
**pre-existing condition, not a 2.0 regression**. Record the Probe 10 autopatch result in §5 and
proceed. The `trace-structure-spec.md` §4.5 note documents this for MER-E.

If Probe 10 shows `google_genai_autopatch: True` but no `google.genai` span appears in the Weave
UI, open a follow-up bug pointing at AH-PRD-13 §9 — this would be a genuine 2.0 change.

---

## §4 — Staging Variant

Run the same probes against `ken-e-staging` after confirming the staging deploy
includes the AH-113 code (see `docs/runs/AH-111-adk2-deploy-smoke.md` §4 for the CD trigger details).

```bash
# Configure ADC for ken-e-staging
gcloud config set project ken-e-staging

STAGING_ENGINE_ID=$(gcloud secrets versions access latest \
    --secret=ken-e-engine-id \
    --project=ken-e-staging)
# docs/spike-adk2/.spike_engine_id is in .gitignore — safe to write here.
echo "$STAGING_ENGINE_ID" > docs/spike-adk2/.spike_engine_id

uv run python docs/spike-adk2/probe-10-deploy-session-weave.py \
    2>&1 | tee /tmp/ah113-staging-probe10.log
echo "probe-10 (staging) exit=$?"
```

Repeat §3.1–§3.2 with `ken-e-staging` credentials and `API_URL` set to the staging API endpoint.

---

## §5 — Results Table

One row per (environment × signal). **Operator-executed 2026-06-06** by `ken@ken-e.ai` (local ADC,
ADK 2.0.0, `WANDB_API_KEY` from `ken-e-dev`). See §2 procedure correction re: the `probe-10`
canonical-engine safety guard.

| Environment | AC | Probe / Signal | Result | Evidence link / notes |
|---|---|---|---|---|
| dev | AC #9 — Weave init + `@safe_weave_op` round-trip | Probe 10 Weave-check legs | **PASS** | `weave_init_result=True`; `op_call_succeeded=True`; span `019e9dd6-efc7-7648-ab67-4e6db101168c` in `wandb.ai/ken-e/ken-e-dev`. |
| dev | AC #9 — `google.genai` autopatch state | Probe 10 (`google_genai_autopatch`) | **CARRY-FORWARD** | `False` (registry empty) — absent per AH-PRD-13 §9; documented in `trace-structure-spec.md` + `AH-PRD-05-trace-contract-diff.md` §2.1. |
| dev | AC #9 — span-set matches fixture (no regression) | offline guards + deployed turn | **PASS (offline) / UI confirm optional** | `test_no_adk2_event_field_consumers.py` + `test_transfer_to_specialist_fixture.py` green on 2.0; deployed turn dispatched (Probe 12 Leg B). Visual UI diff is the one residual manual step (low risk). |
| dev | AC #9 — deployed-engine session round-trip on 2.0 | AH-112 Probe 12 | **PASS** | 3 events stored, round-trip verified. See AH-112 runbook §2.2. |
| staging | AC #9 — Weave + span-set | Probe 10 (staging) | **NOT RUN** | Staging deferred — dev evidence considered sufficient for the foundation merge; run post-staging-deploy if required. |

**Exit-code contract:** 0 = GO (PASS); 1 = NO-GO (FAIL); 2 = INDETERMINATE (infrastructure/credentials).  
Classifier: `_live_harness.classify_exit_code` in `docs/spike-adk2/_live_harness.py`.

**Delta found → action:** If any row is NO-GO:
1. Record the observed span shape in a comment on [AH-113](https://linear.app/ken-e/issue/AH-113).
2. Open a follow-up bug with the probe log attached.
3. Revert the `AH-PRD-05-trace-contract-diff.md` §2.1 verification line added by this PR.
4. Update `AH-PRD-05-trace-contract-diff.md` §2.1 with the observed delta shape.
5. Notify MER-E — the delta belongs in the AH-PRD-14 extractor update.

---

## §6 — Hand-Off Note

Once all rows in §5 are populated:

1. Paste the completed §5 table as a comment on [AH-113](https://linear.app/ken-e/issue/AH-113)
   with PASS/FAIL per signal.
2. If all rows are PASS (or CARRY-FORWARD for the `google.genai` autopatch row):
   - Comment "All AH-113 ACs verified — Weave tracing survives ADK 2.0 with no span-shape delta.
     `google.genai` autopatch state recorded as carry-forward per AH-PRD-13 §9."
   - @mention the PO.
3. If any row is FAIL (exit 1): follow the "Delta found → action" steps in §5 before proceeding.
4. If any row is INDETERMINATE (exit 2): resolve the infrastructure issue and re-run.

**Downstream:**
- AH-113 result feeds `docs/design/components/agentic-harness/projects/AH-PRD-05-trace-contract-diff.md`
  §2.1 (the "no single-specialist span-shape delta on ADK 2.0" verification line) and
  `docs/trace-structure-spec.md` §4.5 (the `google.genai` autopatch carry-forward note).
- Both were updated in this PR **assuming the happy path (no delta)** — per Decision D1 the
  offline regression suite provides strong pre-merge evidence and the live operator execution
  is a post-merge confirmation step. If a delta is found post-merge, follow the §5 "Delta
  found → action" steps immediately: the PR author (or the operator who discovers the delta)
  opens a follow-up that reverts the §2.1 verification line and adds the observed delta shape.
  The window between merge and §5 completion is an accepted operational risk documented in
  AH-113 Decision D1.

---

## §7 — References

- **Issue:** [AH-113](https://linear.app/ken-e/issue/AH-113)
- **PRD:** `docs/design/components/agentic-harness/projects/AH-PRD-13-adk2-foundation.md` §2 (Tracing) + §7 AC #9 + §9 (Weave autopatch fragility risk)
- **AH-111 runbook (structural template):** `docs/runs/AH-111-adk2-deploy-smoke.md`
- **Probe 10 (reused verbatim):** `docs/spike-adk2/probe-10-deploy-session-weave.py`
- **Canonical fixture:** `app/adk/tracking/tests/fixtures/transfer_to_specialist_trace.json`
- **Offline regression guard (new, AH-113):** `app/adk/tracking/tests/test_no_adk2_event_field_consumers.py`
- **MER-E hand-off:** `docs/design/components/agentic-harness/projects/AH-PRD-05-trace-contract-diff.md` §2.1
- **Autopatch carry-forward note:** `docs/trace-structure-spec.md` §4.5
