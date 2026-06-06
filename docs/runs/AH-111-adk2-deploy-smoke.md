# AH-111 — ADK 2.0 Deploy + Smoke-Test Runbook & Evidence Log

**Issue:** [AH-111](https://linear.app/ken-e/issue/AH-111) — Deploy + smoke-test chat tree on 2.0 (dev → staging) incl. sandbox code-exec  
**PRD:** `docs/design/components/agentic-harness/projects/AH-PRD-13-adk2-foundation.md` §7 AC #8 + §2 (Sandbox/code-exec) + §8 (Deploy smoke)  
**Branch:** `feat/AH-111-deploy-smoke-test-2-0`  
**Date authored:** 2026-06-06  
**Executed by:** Operator with `ken-e-dev` + `ken-e-staging` ADC (agent VM blocked by cross-project IAM — see §0)

---

## §0 — IAM Prerequisite

The Dev Team agent VM (`fun-e-agent-vm@fun-e-business.iam.gserviceaccount.com`) lacks:
- `storage.buckets.get` on `gs://ken-e-dev-adk-staging`
- `aiplatform.reasoningEngines.create` on `ken-e-dev`

These are the same blockers documented in `docs/spike-ah104-deploy-sandbox-weave.md` §3.1.
All live commands below **must be run by a developer/PO** with full `ken-e-dev` ADC.

```bash
# Configure ADC for ken-e-dev before running any command below
gcloud auth application-default login
gcloud config set project ken-e-dev
```

---

## §1 — Pre-Deploy Invariants

Verified by the Dev Team agent before opening the PR. Run these to confirm before deploying.

### 1.1 Version pins aligned

```bash
grep "google-adk" pyproject.toml api/pyproject.toml app/adk/pyproject.toml app/adk/requirements.txt
```

Expected: `google-adk[mcp]==2.0.0` in all four files.

### 1.2 AlwaysTrueSubAgentList shim present

```bash
grep -n "AlwaysTrueSubAgentList" \
    app/adk/agents/agent_factory/sub_agent_attacher.py \
    app/adk/agents/agent_factory/hierarchy.py
```

Expected: class definition in `sub_agent_attacher.py` and assignment in `hierarchy.py`.

### 1.3 Parity suite green

```bash
uv run python -m pytest \
    app/adk/agents/agent_factory/tests/test_chat_billing_parity.py \
    app/adk/agents/agent_factory/tests/test_adk2_session_roundtrip.py \
    app/adk/agents/agent_factory/tests/test_adk2_loop_agent_billing.py \
    -q
```

Expected: **68 passed** (as of 2026-06-06; count may grow if tests are added).

**Pre-deploy invariants — Agent-verified result (2026-06-06):**

| Check | Result |
|---|---|
| `google-adk==2.0.0` in all 4 manifests | ✅ VERIFIED |
| `AlwaysTrueSubAgentList` shim committed | ✅ VERIFIED (`sub_agent_attacher.py:81`, `hierarchy.py:272`) |
| Parity suite | ✅ 68/68 passed |

---

## §2 — Dev Deploy

### 2.1 Deploy command

```bash
cd /path/to/KEN-E
git fetch origin && git checkout main
uv sync --frozen

cd app/adk
uv sync --frozen
uv run python deploy_ken_e.py --env dev 2>&1 | tee /tmp/ah111-dev-deploy.log
echo "deploy exit=$?"
```

**Retry policy:** The `500 INTERNAL` SIGTERM on `agent_engines.update()` is a known transient
(AH-PRD-13 §9). Retry up to **2 times**. If the 3rd attempt also fails, treat as NO-GO and
file a follow-up bug.

**Expected success output:**
```
[deploy_ken_e] Resolved existing engine: projects/525657242938/locations/us-central1/reasoningEngines/<ID>
[deploy_ken_e] Uploading agent to Agent Engine...
[deploy_ken_e] Update complete. Engine ID: <ID>
[deploy_ken_e] Wrote engine ID to Secret Manager: ken-e-engine-id
```

If Cloud Run / Agent Engine build fails without a local error, check backend logs:
```bash
gcloud logging read \
    'resource.type="aiplatform.googleapis.com/ReasoningEngine"' \
    --project=ken-e-dev \
    --limit=20 \
    --format='table(timestamp,severity,jsonPayload.message)'
```

**Dev deploy result:**

| Field | Value |
|---|---|
| Date/time | _paste here_ |
| Exit code | _paste here (expected: 0)_ |
| Engine resource name | _paste here_ |
| Attempt number | _paste here (expected: 1)_ |
| Notes | _paste here_ |

---

## §3 — Dev Smoke Probes

All probes run from repo root. Set `ENGINE_ID` to the bare numeric ID from §2.

```bash
# Extract the bare engine ID from the full resource name
ENGINE_RESOURCE="projects/525657242938/locations/us-central1/reasoningEngines/<ID>"
ENGINE_ID=$(echo "$ENGINE_RESOURCE" | grep -oP '(?<=reasoningEngines/)[^/]+')
echo "Engine ID: $ENGINE_ID"
```

### 3.1 Probe 8 — Engine probe turn (AC #1)

Sends one probe turn to the canonical deployed engine and asserts a non-empty text response.

The canonical engine is identified by `ken-e-engine-id` in Secret Manager (written by
`deploy_ken_e.py`). Unlike the spike's ephemeral engine, this reads directly from Secret Manager.

```bash
# Read the engine ID from Secret Manager
ENGINE_ID=$(gcloud secrets versions access latest \
    --secret=ken-e-engine-id \
    --project=ken-e-dev)
echo "Engine ID from Secret Manager: $ENGINE_ID"

# Run the probe against the canonical engine
# (Probe 8 reads .spike_engine_id but we can override by writing the canonical ID)
echo "$ENGINE_ID" > docs/spike-adk2/.spike_engine_id

uv run python docs/spike-adk2/probe-8-deploy-probe-turn.py \
    2>&1 | tee /tmp/ah111-dev-probe8.log
echo "probe-8 exit=$?"
```

**Expected:** exit 0, non-empty text response, displayName matches the deployed agent.

**Probe 8 dev result:**

| Field | Value |
|---|---|
| Exit code | _paste here (expected: 0)_ |
| Response text preview | _paste here_ |
| Notes | _paste here_ |

### 3.2 API_TEST_BYPASS_TOKEN SSE curl (AC #1)

The bypass token curl exercises the chat router endpoint end-to-end, including session
creation and the ADK runner path.

```bash
# Set these from your dev environment
BYPASS_TOKEN="<API_TEST_BYPASS_TOKEN from Secret Manager>"
API_URL="https://api.ken-e-dev.ai"   # or the Cloud Run URL for ken-e-api-dev

curl -X POST "${API_URL}/api/v1/accounts/test-account/chat" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${BYPASS_TOKEN}" \
    -H "Accept: text/event-stream" \
    -d '{"message": "Say hello and tell me your name.", "stream": true}' \
    --no-buffer \
    2>&1 | tee /tmp/ah111-dev-sse-curl.log
echo "SSE curl exit=$?"
```

**Expected:** SSE stream with `data:` lines containing text events; final `data: [DONE]`
or equivalent turn-complete event.

**SSE curl dev result:**

| Field | Value |
|---|---|
| Exit code | _paste here (expected: 0)_ |
| First SSE event preview | _paste here_ |
| Notes | _paste here_ |

### 3.3 Probe 10 — Session round-trip (AC #2)

Sends a turn to the deployed engine, retrieves the session via `VertexAiSessionService`,
and asserts events are present.

```bash
uv run python docs/spike-adk2/probe-10-deploy-session-weave.py \
    2>&1 | tee /tmp/ah111-dev-probe10.log
echo "probe-10 exit=$?"
```

**Expected:** exit 0, session retrieved with at least one event, Weave check recorded
(either True or False — both are acceptable per AH-PRD-13 §9).

**Probe 10 dev result:**

| Field | Value |
|---|---|
| Exit code | _paste here (expected: 0)_ |
| Session ID | _paste here_ |
| Event count | _paste here_ |
| Weave init result | _paste here (True/False — both acceptable)_ |
| Notes | _paste here_ |

### 3.4 Probe 11 — Live sandbox round-trip (AC #3)

Requires a provisioned sandbox environment in `ken-e-dev`. Create one if it doesn't exist:

```bash
# Check for existing sandboxes
gcloud beta ai sandboxes list \
    --project=ken-e-dev \
    --region=us-central1

# Create a sandbox if none exists (takes ~2 min)
gcloud beta ai sandboxes create \
    --project=ken-e-dev \
    --region=us-central1 \
    --display-name="ah111-probe-sandbox"
# The output includes a resource name like:
#   projects/525657242938/locations/us-central1/reasoningEngines/<ENGINE_ID>/sandboxEnvironments/<SANDBOX_ID>
```

Then run the probe:

```bash
SANDBOX_RESOURCE="projects/525657242938/locations/us-central1/reasoningEngines/<ENGINE_ID>/sandboxEnvironments/<SANDBOX_ID>"

uv run python docs/spike-adk2/probe-11-deploy-sandbox-live.py \
    --sandbox-resource-name "$SANDBOX_RESOURCE" \
    2>&1 | tee /tmp/ah111-dev-probe11.log
echo "probe-11 exit=$?"
```

**Expected:** exit 0, Leg A: `execute_code('print(2+2)')` returns `4`, Leg B: pool
round-trip returns `2`.

**Probe 11 dev result:**

| Field | Value |
|---|---|
| Exit code | _paste here (expected: 0)_ |
| Sandbox resource name | _paste here_ |
| Leg A result text | _paste here (expected: contains '4')_ |
| Leg B result text | _paste here (expected: contains '2')_ |
| Notes | _paste here_ |

---

## §4 — Staging Deploy

The CD trigger (`cd-pipeline`, config `deployment/cd/staging.yaml`, step
`deploy-ken-e-agent-staging` at line 70) fires on every `main`-push — **but only for changes
matching its `included_files` globs** (`app/**`, `api/**`, `frontend/**`, `shared/**`,
`tests/**`, `deployment/**`, `uv.lock`; source of truth: `deployment/terraform/build_triggers.tf`).
**`docs/**` is intentionally excluded** ("docs changes do not require a staging redeploy"), so
merging this docs-only PR (and AH-111 in general) does **not** trigger a staging deploy on its
own. The ADK 2.0 code that actually needs deploying landed via the earlier code PRs (the
`google-adk==2.0.0` pin bumps under `app/**` / `uv.lock`), whose `main`-merges fired the
trigger.

So the operator should **either** confirm the most recent staging build that already included
the 2.0 code, **or** run the manual fallback in this section to force a fresh staging deploy.

Watch / locate the relevant build on `main`:

```bash
gcloud builds list \
    --project=ken-e-staging \
    --filter="substitutions.BRANCH_NAME=main" \
    --limit=5 \
    --format='table(id,status,createTime,finishTime)'
```

Confirm the `deploy-ken-e-agent-staging` step succeeded:

```bash
# Replace <BUILD_ID> with the relevant build ID from the list above
gcloud builds describe <BUILD_ID> \
    --project=ken-e-staging \
    --format='table(status,steps[].name,steps[].status)'
```

If no build fired for the merge that should deploy the 2.0 code (e.g., the last `main`-merge
was docs-only and path-filtered out of the CD trigger, or the trigger is disabled), run it
manually from the repo root. The Cloud Build config references repo files (`uv sync --frozen`,
lock files), so the source must be uploaded:

```bash
gcloud builds submit \
    --config deployment/cd/staging.yaml \
    --project=ken-e-staging \
    .
```

**Staging deploy result:**

| Field | Value |
|---|---|
| Build ID | _paste here_ |
| Build status | _paste here (expected: SUCCESS)_ |
| `deploy-ken-e-agent-staging` step status | _paste here (expected: SUCCESS)_ |
| Engine resource name (staging) | _paste here_ |
| Notes | _paste here_ |

---

## §5 — Staging Smoke Probes

Same four probes as §3, pointed at `ken-e-staging`. Run after §4 confirms SUCCESS.

```bash
# Configure ADC for ken-e-staging
gcloud config set project ken-e-staging

# Read the staging engine ID from Secret Manager
STAGING_ENGINE_ID=$(gcloud secrets versions access latest \
    --secret=ken-e-engine-id \
    --project=ken-e-staging)
echo "Staging Engine ID: $STAGING_ENGINE_ID"
echo "$STAGING_ENGINE_ID" > docs/spike-adk2/.spike_engine_id
```

Run probes 8, 10, and 11 with staging credentials following the same steps as §3, substituting
`ken-e-staging` for `ken-e-dev` in all GCP project references and using the staging `BYPASS_TOKEN`
for the SSE curl.

For Probe 11, provision or locate a staging sandbox and run:

```bash
# Check for existing staging sandboxes
gcloud beta ai sandboxes list \
    --project=ken-e-staging \
    --region=us-central1

STAGING_SANDBOX_RESOURCE="projects/<STAGING_PROJECT_NUMBER>/locations/us-central1/reasoningEngines/<STAGING_ENGINE_ID>/sandboxEnvironments/<STAGING_SANDBOX_ID>"

uv run python docs/spike-adk2/probe-11-deploy-sandbox-live.py \
    --sandbox-resource-name "$STAGING_SANDBOX_RESOURCE" \
    2>&1 | tee /tmp/ah111-staging-probe11.log
echo "probe-11 (staging) exit=$?"
```

**Staging smoke probe results:**

| AC | Probe | Exit code | Notes |
|---|---|---|---|
| AC #1 (engine probe turn) | Probe 8 (staging) | _paste here_ | _paste here_ |
| AC #1 (SSE curl) | SSE curl (staging) | _paste here_ | _paste here_ |
| AC #2 (session round-trip) | Probe 10 (staging) | _paste here_ | _paste here_ |
| AC #3 (sandbox code-exec) | Probe 11 (staging) | _paste here_ | _paste here_ |

---

## §6 — Results Table

One row per (environment × AC). Update after running probes.

| Environment | AC | Probe / Signal | Result | Evidence link / notes |
|---|---|---|---|---|
| dev | AC #1 — engine probe turn | Probe 8 + SSE curl | _PASS / FAIL / INDETERMINATE_ | _link or note_ |
| dev | AC #2 — session round-trip | Probe 10 | _PASS / FAIL / INDETERMINATE_ | _link or note_ |
| dev | AC #3 — sandbox code-exec | Probe 11 | _PASS / FAIL / INDETERMINATE_ | _link or note_ |
| staging | AC #1 — engine probe turn | Cloud Build `deploy-ken-e-agent-staging` + SSE curl | _PASS / FAIL / INDETERMINATE_ | _link or note_ |
| staging | AC #2 — session round-trip | Probe 10 (staging) | _PASS / FAIL / INDETERMINATE_ | _link or note_ |
| staging | AC #3 — sandbox code-exec | Probe 11 (staging) | _PASS / FAIL / INDETERMINATE_ | _link or note_ |

**Exit-code contract:** 0 = GO (PASS); 1 = NO-GO (FAIL); 2 = INDETERMINATE (infrastructure/credentials).  
Classifier: `_live_harness.classify_exit_code` in `docs/spike-adk2/_live_harness.py`.

---

## §7 — Hand-Off Note

Once all six rows in §6 are populated:

1. Paste the completed §6 table as a comment on [AH-111](https://linear.app/ken-e/issue/AH-111)
   with PASS/FAIL per AC.
2. If all six rows are PASS, comment "All ACs verified — ready for Done" and @mention the PO.
3. If any row is FAIL (exit 1), open a follow-up bug with the probe log attached and comment
   on AH-111 with the NO-GO finding.
4. If any row is INDETERMINATE (exit 2), resolve the infrastructure issue and re-run that probe.

**Downstream:** AH-111 unblocks [AH-112](https://linear.app/ken-e/issue/AH-112) (managed-session
round-trip vs deployed 2.0 agent) and [AH-113](https://linear.app/ken-e/issue/AH-113) (Weave trace
shape vs deployed 2.0 agent) — both target the deployed 2.0 engine this issue stands up.

---

## §8 — References

- **Issue:** [AH-111](https://linear.app/ken-e/issue/AH-111)
- **PRD:** `docs/design/components/agentic-harness/projects/AH-PRD-13-adk2-foundation.md` §2 + §7.8 + §8 + §9
- **Spike basis:** `docs/spike-ah104-deploy-sandbox-weave.md` (AH-104; §3.1 deploy, §3.3 sandbox, §3.4 session/Weave)
- **Probe scripts:** `docs/spike-adk2/probe-{8,9,10,11}-*.py`
- **Deploy script:** `app/adk/deploy_ken_e.py`
- **CD trigger:** `deployment/cd/staging.yaml` (step `deploy-ken-e-agent-staging`)
- **AH-104 verdict:** `docs/spike-ah104-deploy-sandbox-weave.md` §1 (PARTIAL GO → GO once this doc is complete)
