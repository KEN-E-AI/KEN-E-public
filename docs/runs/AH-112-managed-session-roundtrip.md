# AH-112 — Managed-session + chat_sessions Round-Trip Runbook & Evidence Log

**Issue:** [AH-112](https://linear.app/ken-e/issue/AH-112) — Managed-session + chat_sessions round-trip verified against deployed 2.0 agent  
**PRD:** `docs/design/components/agentic-harness/projects/AH-PRD-13-adk2-foundation.md` §7 AC #7 + §2 (Managed-session compatibility) + §4 (Data Contract) + §8 (Deploy smoke — round-trip a session)  
**Branch:** `feat/AH-112-managed-session-roundtrip`  
**Date authored:** 2026-06-06  
**Executed by:** Operator with `ken-e-dev` ADC (agent VM blocked by cross-project IAM — see §0)

---

## §0 — IAM Prerequisite

The Dev Team agent VM (`fun-e-agent-vm@fun-e-business.iam.gserviceaccount.com`) lacks the IAM grants needed to invoke the canonical dev Agent Engine or read Firestore chat_sessions. All live commands below **must be run by a developer/PO** with full `ken-e-dev` ADC.

```bash
# Configure ADC for ken-e-dev before running any command below
gcloud auth application-default login
gcloud config set project ken-e-dev
```

Required IAM roles on `ken-e-dev`:
- `aiplatform.reasoningEngines.use` (Agent Engine session service)
- `aiplatform.reasoningEngines.query` (stream_query for Leg B)
- `datastore.viewer` on `accounts/*/chat_sessions/*` (Firestore mirror inspection)

These are the same grants used for AH-111 §3 probes — see `docs/runs/AH-111-adk2-deploy-smoke.md` §0.

---

## §1 — Pre-Deploy Invariants

Verify before running any probe. The Dev Team agent verified these at PR-open time.

### 1.1 Canonical dev 2.0 engine is live (AH-111 prerequisite)

```bash
# Read the canonical engine ID from Secret Manager
ENGINE_ID=$(gcloud secrets versions access latest \
    --secret=ken-e-engine-id \
    --project=ken-e-dev)
echo "Canonical dev engine ID: $ENGINE_ID"

# Confirm the engine is on ADK 2.0 — check the displayName or version tag
# (set by deploy_ken_e.py during the AH-111 deploy)
gcloud ai reasoning-engines describe $ENGINE_ID \
    --project=ken-e-dev \
    --location=us-central1 \
    --format='value(displayName)'
```

Expected: `displayName` contains `ken-e` and the engine was last updated after the AH-111 2.0 deploy (2026-06-06 or later).

If the engine is still on 1.34.1 (AH-111 not yet executed), escalate to PO before running any probe. Probe 12 must target a deployed 2.0 agent.

### 1.2 CI guard test passing

```bash
cd /path/to/KEN-E
cd app/adk && uv run python -m pytest \
    agents/agent_factory/tests/test_adk2_session_roundtrip.py \
    -q
```

Expected: **69 passed** (68 from prior issues + 1 `TestChatSessionsMirrorAllowlist` guard added by AH-112).

**Pre-deploy invariants — Agent-verified result (2026-06-06):**

| Check | Result |
|---|---|
| Parity suite including new guard test | ✅ 69/69 passed |
| `probe-12` syntax check (`py_compile`) | ✅ PASS |

---

## §2 — Probe Execution

All probes run from repo root. Use `.venv-adk2/` (ADK 2.0.0) as the Python interpreter.

```bash
# Confirm .venv-adk2 is on ADK 2.0
.venv-adk2/bin/python -c "import google.adk; print(google.adk.__version__)"
# Expected: 2.0.0
```

### 2.1 Probe 5 (re-targeted) — Synthesised-event round-trip — AC #3

Re-run the original AH-99 probe-5 to confirm the synthesised-event path still passes against the canonical dev engine that AH-111 deployed on 2.0.

```bash
.venv-adk2/bin/python docs/spike-adk2/probe-5-session-service-schema.py \
    2>&1 | tee /tmp/ah112-probe5.log
echo "probe-5 exit=$?"
```

Expected: exit 0, terminal state "raw_event roundtrip OK" or "raw_event fallback triggered" — both are PASS per AH-99 AC #3 semantics.

**Probe 5 re-run result:**

> AC #3 was satisfied via **Probe 12 Leg A**, which re-runs the AH-99 probe-5 synthesised-event assertion path (append task-mode + dynamic-graph events → re-fetch → assert additive fields survive in STORED events) against the same canonical dev 2.0 engine. The standalone `probe-5-session-service-schema.py` was therefore not run separately. See §2.2 / §6.

| Field | Value |
|---|---|
| Exit code | 0 (via Probe 12 Leg A) |
| Terminal state | "roundtrip OK" — additive fields preserved on stored events |
| Notes | Covered by Probe 12 Leg A (2026-06-06). |

### 2.2 Probe 12 — Managed-session + mirror inspection — AC #1 + AC #2

Probe 12 runs two legs:
- **Leg A:** Synthesised ADK 2.0 events (task-mode + dynamic-graph) appended via `VertexAiSessionService` and re-fetched to assert additive fields survive in STORED events.
- **Leg B:** One real chat turn sent to the canonical dev 2.0 engine; resulting Firestore `chat_sessions` row inspected to confirm no ADK 2.0 session-layer fields (`node_info`, `isolation_scope`) leaked into the mirror.

```bash
# Set the test account ID (must have a chat_sessions subcollection in Firestore)
export PROBE_ACCOUNT_ID="<dev-test-account-id>"

.venv-adk2/bin/python docs/spike-adk2/probe-12-deploy-session-mirror.py \
    --account-id "$PROBE_ACCOUNT_ID" \
    2>&1 | tee /tmp/ah112-probe12.log
echo "probe-12 exit=$?"
```

If Firestore read access is unavailable for the test account, run with `--dry-run` for Leg A only (confirms Leg B prerequisites are documented but not executed):

```bash
.venv-adk2/bin/python docs/spike-adk2/probe-12-deploy-session-mirror.py \
    --dry-run \
    2>&1 | tee /tmp/ah112-probe12-dryrun.log
echo "probe-12 (dry-run) exit=$?"
```

**Expected (full run):** exit 0; both Leg A and Leg B report PASS; no FAIL lines.  
**Expected (dry-run):** exit 0; Leg A PASS; Leg B skipped.

**Probe 12 result (operator-executed 2026-06-06, `ken@ken-e.ai` ADC against canonical dev engine `5957383247464759296`):**

| Field | Value |
|---|---|
| Exit code | 0 (PASS) |
| Leg A result | PASS — both task-mode and dynamic-graph events stored with `node_info=present, isolation_scope=present` → preserved across `VertexAiSessionService` write→read |
| Leg B result | PASS — live turn stored 3 events (all with non-None author); session round-trip verified |
| Mirror row keys (Leg B) | Probe's synthetic session was not mirrored (direct-engine path does not exercise the API side-table writer; probe reported "row does not exist → PASS, write path separate"). See §2.3 for the supplementary inspection of **real** mirror rows. |
| Notes | Probe ran twice (dry-run Leg A only, then full run with `--account-id acc_4fed6116254f49d385de9e818135ad4a`); spike sessions cleaned up both times. |

### 2.3 Supplementary — real `chat_sessions` mirror-row inspection (AC #2 direct evidence)

Because Leg B's synthetic session is created directly via `VertexAiSessionService` (bypassing the API Cloud Run side-table writer), it produces no mirror row. To evidence AC #2 against **populated** rows, the 4 existing `chat_sessions` rows for `acc_4fed6116254f49d385de9e818135ad4a` were inspected directly:

| Check | Result |
|---|---|
| Rows inspected | 4 |
| `node_info` / `isolation_scope` present in ANY row | **NO** (PASS) |
| Top-level keys observed | All legitimate `ChatSessionMetadata` fields (`account_id`, `adk_app_name`, `category_id`, `model_id`, `search_text`, `latest_summary`, token counters, etc.) — no ADK 2.0 session-layer fields |

This confirms the mirror is unaffected by the 2.0 event shape on real data, complementing the `TestChatSessionsMirrorAllowlist` CI guard.

---

## §3 — Hand-Off Note

Once all rows in §6 are populated:

1. Paste the completed §6 table as a comment on [AH-112](https://linear.app/ken-e/issue/AH-112) with PASS/FAIL per AC.
2. If all three rows are PASS (or AC #3 is "fallback documented"), comment "All ACs verified — ready for Done" and @mention the PO.
3. If any row is FAIL (exit 1), open a follow-up bug with the probe log attached and comment on AH-112 with the NO-GO finding.
4. If any row is INDETERMINATE (exit 2), resolve the infrastructure issue and re-run that probe.

**Comment template:**

```
## AH-112 Results

Probes executed against canonical dev 2.0 engine (see §6 below).

### §6 Results Table

| AC | Signal | Result | Evidence / notes |
|---|---|---|---|
| AC #1 — VertexAiSessionService round-trip | Probe 12 Leg A | PASS | … |
| AC #2 — chat_sessions mirror unaffected | Probe 12 Leg B | PASS | … |
| AC #3 — probe-5 re-run (live 2.0 deploy) | Probe 5 re-targeted | PASS | … |

All ACs verified — ready for Done. @<PO-handle>
```

---

## §4 — References

- **Issue:** [AH-112](https://linear.app/ken-e/issue/AH-112)
- **PRD:** `docs/design/components/agentic-harness/projects/AH-PRD-13-adk2-foundation.md` §2 + §4 + §7 AC #7 + §8
- **AH-111 runbook (predecessor):** `docs/runs/AH-111-adk2-deploy-smoke.md` (§3.3 Probe 10 session round-trip; §0 IAM prereq)
- **AH-99 probe-5 (synthesised-event reference):** `docs/spike-adk2/probe-5-session-service-schema.py`
- **AH-112 probe:** `docs/spike-adk2/probe-12-deploy-session-mirror.py`
- **CI guard test:** `app/adk/agents/agent_factory/tests/test_adk2_session_roundtrip.py` — `TestChatSessionsMirrorAllowlist`
- **Mirror allow-list (source of truth):** `api/src/kene_api/chat/side_table_handlers.py:36` (`_ALLOWED_DELTA_FIELDS`)
- **Data contract:** AH-PRD-13 §4 — "No new Firestore collections; no schema change. ADK 2.0 events gain `node_info` / `isolation_scope` (additive)."

---

## §5 — Exit Code Contract

| Exit code | Meaning | Action |
|---|---|---|
| 0 | GO — all assertions passed | Mark AC as PASS |
| 1 | NO-GO — a real finding (assertion failed, field leaked, no events, changed API) | Open follow-up bug; mark AC as FAIL |
| 2 | INDETERMINATE — infrastructure / credentials (ADC missing, 401/403/5xx) | Fix infra issue; re-run probe |

Classifier: `_live_harness.classify_exit_code` in `docs/spike-adk2/_live_harness.py`.

---

## §6 — Results Table

One row per AC. **Operator-executed 2026-06-06** by `ken@ken-e.ai` with local ADC against the
canonical dev 2.0 engine `5957383247464759296` (project `ken-e-dev`). All three ACs PASS.

| AC | Signal | Result | Evidence link / notes |
|---|---|---|---|
| AC #1 — Given a deployed 2.0 agent, node_info/isolation_scope survive VertexAiSessionService write → read | Probe 12 Leg A (synthesised-event round-trip) | **PASS** | Probe 12 exit 0; task-mode + dynamic-graph events both stored with `node_info=present, isolation_scope=present`. See §2.2. |
| AC #2 — chat_sessions mirror row contains no node_info / isolation_scope / unrecognised top-level fields | Probe 12 Leg B + §2.3 real-row inspection | **PASS** | 4 real mirror rows for `acc_4fed6116254f49d385de9e818135ad4a` contain zero ADK 2.0 session-layer fields; only legitimate `ChatSessionMetadata` keys. Backed by `TestChatSessionsMirrorAllowlist` CI guard. See §2.3. |
| AC #3 — AH-99 probe-5 round-trip still passes against live 2.0 deploy | Probe 12 Leg A (re-runs the probe-5 assertion path) | **PASS** | Same run as AC #1 — additive fields preserved on STORED events. See §2.1 note. |
