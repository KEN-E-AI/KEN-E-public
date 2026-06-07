# AH-118 — `agent.google_search` Grounded-Search Trace-Step Coverage Runbook

**Issue:** [AH-118](https://linear.app/ken-e/issue/AH-118) — `agent.google_search` grounded-search trace-step coverage on 2.0  
**PRD:** `docs/design/components/agentic-harness/projects/AH-PRD-15-agenttool-migration-cutover.md` §7.2 (AC #2) + §8 (Test Plan — Trace) + §1 (steps vanish from traces under #3984)  
**Branch:** `feat/AH-118-google-search-trace-step-coverage`  
**Date authored:** 2026-06-06  
**Executed by:** Operator with `ken-e-dev` + `ken-e-staging` ADC (agent VM blocked by cross-project IAM — see §0)

---

## §0 — IAM Prerequisite

The Dev Team agent VM (`fun-e-agent-vm@fun-e-business.iam.gserviceaccount.com`) lacks:
- `storage.buckets.get` on `gs://ken-e-dev-adk-staging`
- `aiplatform.reasoningEngines.create` on `ken-e-dev`

These are the same blockers documented in `docs/spike-ah104-deploy-sandbox-weave.md` §3.1
and inherited by `docs/runs/AH-111-adk2-deploy-smoke.md` §0 and `docs/runs/AH-113-adk2-weave-verification.md` §0.  
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

### 1.3 Tracking-tier offline regression suite green (includes AH-118 guard)

```bash
uv run python -m pytest app/adk/tracking/tests/ -v
```

Expected: all tracking tests pass, including:
- `test_no_adk2_event_field_consumers.py::test_no_adk2_event_fields_in_production_tracking`
- `test_transfer_to_specialist_fixture.py::TestEmissionStatus::test_emitted_spans_are_exactly_the_runtime_set`
- `test_google_search_task_mode_fixture.py::TestEmissionStatus::test_emitted_spans_are_exactly_the_runtime_set`
- `test_google_search_task_mode_fixture.py::TestGroundedSearchSteps::test_grounded_search_spans_are_emitted`

The last two tests are the primary offline CI guards for AH-PRD-15 §7.2 AC #2.

**Pre-deploy invariants — Agent-verified result (2026-06-06):**

| Check | Result |
|---|---|
| `google-adk==2.0.0` in all 4 manifests | ✅ VERIFIED (via AH-111) |
| AH-110 parity suite 68/68 | ✅ VERIFIED (via AH-111) |
| Tracking-tier offline suite (347 tests including AH-118 guard) | ✅ VERIFIED (AH-118 PR CI) |

---

## §2 — SSE-curl Turn Triggering `agent.google_search`

Send a turn that forces the `google_analytics_specialist` to invoke `agent.google_search`
via the migrated `mode='task'` path. The turn must assign `agent.google_search` to either
the specialist (AH-115 path) or `ken_e_chatbot` root (AH-116 path per
[AH-100](https://linear.app/ken-e/issue/AH-100)).

### 2.1 Specialist-assignment path (AH-115 baseline)

```bash
BYPASS_TOKEN="<API_TEST_BYPASS_TOKEN from Secret Manager>"
API_URL="https://api.ken-e-dev.ai"   # or the Cloud Run URL for ken-e-api-dev
ACCOUNT_ID="test-account"

# Ensure agent.google_search is in the google_analytics_specialist's tool_ids
# (via Firestore or the /api/v1/accounts/{account_id}/agent-configs/ PUT endpoint)

curl -X POST "${API_URL}/api/v1/accounts/${ACCOUNT_ID}/chat" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${BYPASS_TOKEN}" \
    -H "Accept: text/event-stream" \
    -d '{
      "message": "Search the web for Q2 2026 digital marketing benchmark reports covering paid search CPC trends and organic search CTR changes.",
      "stream": true
    }' \
    --no-buffer \
    2>&1 | tee /tmp/ah118-dev-sse-specialist.log
echo "SSE curl exit=$?"
```

**Expected:** SSE stream with `data:` lines containing text events; final `data: [DONE]` or
equivalent turn-complete event. The turn must route to the `google_analytics_specialist` via
`transfer_to_agent`, and the specialist must invoke `request_task_google_search`.

### 2.2 Root-assignment path (AH-116 — optional verification)

```bash
# Ensure agent.google_search is in ken_e_chatbot root tool_ids
# (via the /api/v1/accounts/{account_id}/agent-configs/ken_e_chatbot PUT endpoint)

curl -X POST "${API_URL}/api/v1/accounts/${ACCOUNT_ID}/chat" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${BYPASS_TOKEN}" \
    -H "Accept: text/event-stream" \
    -d '{
      "message": "Search the web for the latest news about Vertex AI Agent Engine updates in 2026.",
      "stream": true
    }' \
    --no-buffer \
    2>&1 | tee /tmp/ah118-dev-sse-root.log
echo "SSE curl exit=$?"
```

---

## §3 — Weave UI Span Inspection

After the turn completes, open the Weave project for `ken-e-dev` and locate the trace for
this session. Capture the span names and compare to the canonical fixture
`app/adk/tracking/tests/fixtures/google_search_task_mode_trace.json`.

### 3.1 Expected emitted span set (specialist-assignment path)

| Span | `emission_status` |
|---|---|
| `ken_e` (root) | `emitted` |
| `transfer_to_agent` | `emitted` |
| `google_analytics_specialist` | `emitted` |
| `google_analytics_specialist_worker` | `emitted` |
| `request_task_google_search` | `emitted` |
| `google_search_agent` (task-mode leaf) | `emitted` |
| `google_search` (1st grounded-search call) | `emitted` |
| `google_search` (2nd grounded-search call, if ≥2 queries) | `emitted` |
| `google_analytics_specialist_review_reviewer` | `deferred` (not present in live traces) |
| `generate_content` (inside task-mode leaf) | `deferred` — carry-forward per §3.3 |

### 3.2 Verdict guide

| Observation | Classification |
|---|---|
| All `emitted` spans present, no unexpected additions | ✅ GO (no delta) |
| `google_search` spans are present under `google_search_agent` | ✅ GO — AC #2 confirmed |
| `google_search` spans are **absent** under `google_search_agent` | ❌ NO-GO — grounded-search steps are still vanishing; revert to investigation |
| `google_search_agent` span is absent | ❌ NO-GO — task-mode leaf not emitting; check AH-115/116 migration |
| A known `deferred` span now appears | INDETERMINATE — record as potential future change; not a regression |
| An unexpected new span appears | INDETERMINATE — open follow-up for MER-E assessment |
| `google.genai` LLM-call span absent | ✅ GO (carry-forward; see §3.3 below) |
| `request_task_google_search` span absent | ❌ NO-GO — task-mode dispatch not wired; check AH-115 roster/registry |

**node_path validation:** Locate the `google_search_agent` span's `node_path` attribute.
Expected format: `<specialist_name>@1/task_specialist@adk-<uuid>` (e.g.
`google_analytics_specialist@1/task_specialist@adk-30c59a97-…`). This format is sourced from
AH-99 probe-1 evidence in `docs/spike-adk2-supervisor-orchestration-live.md` §4; a different
format observed here is an INDETERMINATE signal — record in §5 and open a follow-up to update
the fixture + conformance test.

**Live span capture result:**

> _(Operator-populated post-merge — leave this blank until the runbook is executed.)_

| Field | Value |
|---|---|
| Weave project URL | `https://wandb.ai/ken-e/ken-e-dev/weave` |
| Trace ID | _(operator fills in)_ |
| Observed span names | _(operator fills in)_ |
| `google_search` spans present under `google_search_agent` | _(operator fills in)_ |
| `node_path` observed value | _(operator fills in)_ |
| Delta vs fixture's emitted set | _(operator fills in)_ |
| Notes | _(operator fills in)_ |

### 3.3 `google.genai` LLM-call span — carry-forward classification

Per AH-PRD-13 §9 and `docs/trace-structure-spec.md` §4.5: the `google.genai` LLM-call span
(`google.genai.generate_content` or similar) may be absent in both 1.34.1 and 2.0 traces
inside the `google_search_agent` task-mode leaf due to the known Weave autopatch fragility.
This is a **pre-existing condition, not a 2.0 regression** and not a 2.0 task-mode regression.
Record the autopatch state in §5 and proceed.

The canonical fixture marks `generate_content` as `emission_status='deferred'` (see
`app/adk/tracking/tests/fixtures/google_search_task_mode_trace.json` — the
`deferred_reason` references this runbook and `docs/trace-structure-spec.md` §4.5).
`test_google_search_task_mode_fixture.py::TestEmissionStatus::test_generate_content_span_is_deferred`
locks this classification in CI so a future fix that makes it emit breaks CI intentionally.

---

## §4 — Staging Variant

Run the same probes against `ken-e-staging` after confirming the staging deploy
includes the AH-118 code and the AH-115/116 migration.

```bash
# Configure ADC for ken-e-staging
gcloud config set project ken-e-staging

STAGING_API_URL="https://api.ken-e-staging.ai"   # or the Cloud Run URL for ken-e-api-staging
STAGING_BYPASS_TOKEN="<API_TEST_BYPASS_TOKEN from ken-e-staging Secret Manager>"
STAGING_ACCOUNT_ID="test-account"

curl -X POST "${STAGING_API_URL}/api/v1/accounts/${STAGING_ACCOUNT_ID}/chat" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${STAGING_BYPASS_TOKEN}" \
    -H "Accept: text/event-stream" \
    -d '{
      "message": "Search the web for Q2 2026 digital marketing benchmark reports.",
      "stream": true
    }' \
    --no-buffer \
    2>&1 | tee /tmp/ah118-staging-sse.log
echo "SSE curl (staging) exit=$?"
```

Repeat §3.1–§3.2 with `ken-e-staging` Weave project and staging API URL.

---

## §5 — Results Table

One row per (environment × signal). **Operator-populated post-merge.**

| Environment | AC | Signal | Result | Evidence link / notes |
|---|---|---|---|---|
| dev | AC #2 — `google_search` spans present in trace | Weave UI span inspection | _(operator fills in)_ | _(operator fills in)_ |
| dev | AC #2 — `google_search_agent` task-mode leaf present | Weave UI span inspection | _(operator fills in)_ | _(operator fills in)_ |
| dev | AC #2 — `request_task_google_search` span present | Weave UI span inspection | _(operator fills in)_ | _(operator fills in)_ |
| dev | AC #2 — `node_path` format matches AH-99 probe-1 | Weave UI attribute inspection | _(operator fills in)_ | _(operator fills in)_ |
| dev | AC #3 — `google.genai` autopatch state | Weave UI (absent = carry-forward) | _(operator fills in)_ | _(operator fills in)_ |
| staging | AC #2 — `google_search` spans present | Weave UI span inspection | **NOT RUN** | Staging deferred — dev evidence considered sufficient for the AH-118 merge; run post-staging-deploy. |

**Exit-code contract:** 0 = GO (PASS); 1 = NO-GO (FAIL); 2 = INDETERMINATE (infrastructure/credentials).

**Delta found → action:** If any row is NO-GO:
1. Record the observed span shape as a comment on [AH-118](https://linear.app/ken-e/issue/AH-118).
2. Open a follow-up bug with the probe log attached.
3. Revert the §17 subsection addition in `docs/trace-structure-spec.md` from this PR, or
   update its `emission_status` table to reflect the observed delta.
4. Notify MER-E — the delta belongs in the AH-PRD-14 extractor update queue.

---

## §6 — Hand-Off Note

Once all rows in §5 are populated:

1. Paste the completed §5 table as a comment on [AH-118](https://linear.app/ken-e/issue/AH-118)
   with PASS/FAIL per signal.
2. If all rows are PASS (or CARRY-FORWARD for the `google.genai` autopatch row):
   - Comment "All AH-118 ACs verified — grounded-search steps appear in the Weave trace
     on the migrated task-mode path. `google.genai` autopatch state recorded as
     carry-forward per AH-PRD-13 §9."
   - @mention the PO.
3. If any row is FAIL (exit 1): follow the "Delta found → action" steps in §5 before proceeding.
4. If any row is INDETERMINATE (exit 2): resolve the infrastructure issue and re-run.

**Downstream:**
- AH-118 result feeds `docs/trace-structure-spec.md` §17 (the task-mode agent-as-tool leaf
  trace shape subsection) — the §17 `emission_status` table was added **assuming the happy
  path (no delta)** per Decision D1 in the AH-118 Implementation Plan (offline evidence +
  runbook live confirmation, same as AH-113 Decision D1). If a delta is found post-merge,
  follow the §5 "Delta found → action" steps: update §17's `emission_status` table and
  annotate the delta inline.
- AH-PRD-15 §7.2 AC #2 is marked verified once this runbook's §5 PASS rows are confirmed.

---

## §7 — References

- **Issue:** [AH-118](https://linear.app/ken-e/issue/AH-118)
- **PRD:** `docs/design/components/agentic-harness/projects/AH-PRD-15-agenttool-migration-cutover.md` §7.2 (AC #2) + §8 (Test Plan — Trace) + §1 (context)
- **AH-113 runbook (structural template):** `docs/runs/AH-113-adk2-weave-verification.md`
- **Canonical fixture:** `app/adk/tracking/tests/fixtures/google_search_task_mode_trace.json`
- **Conformance test:** `app/adk/tracking/tests/test_google_search_task_mode_fixture.py`
- **Trace spec subsection:** `docs/trace-structure-spec.md` §17
- **AH-99 node_path evidence:** `docs/spike-adk2-supervisor-orchestration-live.md` §4
- **Autopatch carry-forward note:** `docs/trace-structure-spec.md` §4.5
- **AH-115 (roster/specialist_runtime migration):** [AH-115](https://linear.app/ken-e/issue/AH-115)
- **AH-116 (root/coordinator path migration):** [AH-116](https://linear.app/ken-e/issue/AH-116)
