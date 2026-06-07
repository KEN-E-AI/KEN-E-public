# AH-121 — ADK 2.0 Production Cutover Runbook & Go/No-Go Log

**Issue:** [AH-121](https://linear.app/ken-e/issue/AH-121) — ADK 2.0 prod-cutover: go/no-go runbook + deploy + 24h billing reconciliation
**PRD:** `docs/design/components/agentic-harness/projects/AH-PRD-15-agenttool-migration-cutover.md` §7.7 (AC #7) + §2 (Prod cutover go/no-go) + §8 (Cutover smoke + 24h reconciliation) + §9 (shipping-2.0-before-this-lands risk)
**Blocked by:** [AH-111](https://linear.app/ken-e/issue/AH-111) (AH-PRD-13 green in staging) **and** AH-PRD-15 ACs #1–#6 (AH-114/115/116/117/118/119/120)
**Branch:** `feat/AH-121-adk2-prod-cutover` (PR [#886](https://github.com/KEN-E-AI/KEN-E/pull/886))
**Date authored:** 2026-06-07
**Executed by:** Operator/PO with `ken-e-production` ADC + Cloud Build approver rights (the Dev Team agent VM lacks cross-project prod IAM — see §0)

> **Why this gate exists.** AH-98 shipped `agent.google_search` as an `AgentTool`; on ADK 2.0, GitHub `#3984` (OPEN) makes `AgentTool.run_async` drop the search sub-agent's inner events — its `gemini-2.5-flash` tokens go uncounted and its grounded-search steps vanish from traces. Deploying the 2.0 chat tree to prod **before** the task-mode migration (ACs #1–#6) lands would ship a billing under-count on **every** web-search turn. This runbook is the deliberate, gated, reconciled production change at the end of the migration initiative. **No prod deploy of the 2.0 chat tree happens without a recorded GO in §1.**

---

## §0 — Prerequisites & IAM

All live commands run by an operator with full `ken-e-production` ADC and Cloud Build approver rights on `ken-e-cicd`.

```bash
gcloud auth application-default login
gcloud config set project ken-e-production
```

**Prod identifiers (source: `app/adk/deploy_ken_e.py` `prod` block):**

| Field | Value |
|---|---|
| Prod GCP project | `ken-e-production` |
| Prod project number | `395770269870` |
| Prod API (Cloud Run) URL + OIDC audience | `https://kene-api-prod-395770269870.us-central1.run.app` |
| Chat engine deploy script | `app/adk/deploy_ken_e.py --env prod` |
| Prod CD config | `deployment/cd/deploy-to-prod.yaml` (trigger `deploy-to-prod-pipeline`, **approval-gated**) |
| Engine ID secret | `ken-e-engine-id` (in `ken-e-production`) |

---

## §1 — Go/No-Go Gate (decide BEFORE any prod deploy)

Every row must be GREEN to record a GO. Rows 1.1–1.5 are the AC #7 preconditions.

### 1.1 — AH-PRD-13 green in staging (AH-111)

Confirm [AH-111](https://linear.app/ken-e/issue/AH-111) §6 results table is **all PASS** (engine probe turn, session round-trip, sandbox code-exec on `ken-e-staging`).

```bash
# The staging CD build runs in the cicd project (cd_pipeline trigger:
# build_triggers.tf `project = var.cicd_runner_project_id`), even though it
# deploys into ken-e-staging — list it from ken-e-cicd, not ken-e-staging.
gcloud builds list --project=ken-e-cicd \
  --filter="substitutions.BRANCH_NAME=main" --limit=5 \
  --format='table(id,status,createTime,finishTime)'
# Confirm the most recent main build's deploy-ken-e-agent-staging step = SUCCESS
```

| Signal | Expected | Result |
|---|---|---|
| AH-111 §6 all rows PASS | yes | _paste_ |
| Latest staging `deploy-ken-e-agent-staging` | SUCCESS | _paste_ |

> **AH-121 precondition (discovered 2026-06-07):** `deploy-ken-e-agent-staging` was
> RED across recent `main` commits — including the Wave-3 merge `e7f6ee52` (#885) —
> with the opaque `400 ...failed to be updated` (real cause in the staging
> ReasoningEngine logs: `ModuleNotFoundError: No module named
> 'vertexai.agent_engines.templates.adk'`). The `app/adk/requirements.txt`
> `google-cloud-aiplatform` entry was unpinned and the container resolved a newer
> aiplatform than the cloudpickle SDK. **PR #887 pins it; this row cannot go GREEN
> until #887 is merged and its `cd-pipeline` staging deploy reports SUCCESS.**

### 1.2 — ACs #1–#6 green (migration verified)

Verified against `main` at `e7f6ee52` (PR #885, the combined AH-114→120 stack) on **2026-06-07**. Re-run before the gate to confirm no regression on the merge commit:

```bash
# ADK task-mode dispatch + billing parity (AC #1, #6) — root .venv
uv run --no-sync pytest \
  app/adk/agents/agent_factory/tests/test_chat_billing_parity.py \
  app/adk/agents/agent_factory/tests/test_sub_agent_attacher.py \
  app/adk/agents/agent_factory/tests/test_specialist_runtime.py \
  app/adk/agents/agent_factory/tests/test_root_tools_attacher.py \
  app/adk/agents/agent_factory/tests/test_root_tools_attacher_adk_smoke.py \
  app/adk/agents/agent_factory/tests/test_roster.py \
  app/adk/agents/agent_factory/tests/test_adk2_loop_agent_billing.py -q

# Trace coverage (AC #2)
uv run --no-sync pytest app/adk/tracking/tests/test_google_search_task_mode_fixture.py -q
# Parallel-search under ctx.run_node (AC #3)
uv run --no-sync pytest app/adk/tools/agent_tools/tests/test_google_search_concurrency.py -q
# No-AgentTool guard (AC #4) + standalone removal (AC #5)
uv run --no-sync python api/scripts/lint/check_no_agent_tool_in_chat_tree.py        # expect: OK, exit 0
( cd api && uv run --no-sync pytest tests/integration/test_no_agent_tool_lint_rule.py -q )  # api .venv
```

| AC | Signal | Verified result (2026-06-07, `main` @ `e7f6ee52`) |
|---|---|---|
| **#1** billing parity (merge blocker) — root + specialist | `test_chat_billing_parity.py` (real `extract_billable_tokens` + `SessionTurnAccumulator`, no mocks) | ✅ 34 passed |
| **#1/#6** production post-construction task dispatch | attacher/runtime/roster/loop-billing suites | ✅ 291 passed, 1 xfailed |
| **#2** grounded-search trace steps | `test_google_search_task_mode_fixture.py` | ✅ 32 passed (see §3.3 caveat) |
| **#3** parallel-search under `ctx.run_node` | `test_google_search_concurrency.py` + `pr_checks.yaml` scope widened | ✅ 2 passed; CI scope confirmed |
| **#4** no-`AgentTool`-in-chat-tree guard | `check_no_agent_tool_in_chat_tree.py` + rule test; `strategy_agent` excluded (non-vacuous) | ✅ guard OK (97 files); 15 rule tests passed |
| **#5** `agent_standalone_embedded.py` removed | file absent + unreferenced by `deploy_ken_e.py`/`hierarchy.py` | ✅ removed |

> **Caveat carried to §3.3 (AC #2):** the trace test is a **fixture-conformance** check; the search leaf's `generate_content` LLM span is **deferred** (known Weave autopatch gap, AH-PRD-13 §9 / AH-88 won't-fix). The grounded-search **tool** spans are asserted. Live-trace confirmation of the grounded-search steps is part of §3.3 below.

### 1.3 — Migration code merged to main

The 2.0 chat-tree code that the prod CD deploys must be on `main` (the path-filtered CD trigger fires on the `app/**` / `uv.lock` changes). Confirm Wave 3 (PR #885) is merged:

```bash
git fetch origin && git log origin/main --oneline | grep -iE "ah-prd-15|AH-11[4-9]|AH-120" | head
```

| Signal | Expected | Result |
|---|---|---|
| AH-114→120 on `origin/main` | present | `e7f6ee52` — integration: ah-prd-15 Cycle 6 Wave 3 (AH-117, AH-118, AH-119, AH-120) (#885) |
| `app-adk-tests` CI green on the merge commit | SUCCESS | _paste_ |
| `no-agent-tool-guard` CI step green on merge commit | SUCCESS | _paste_ |

### 1.4 — Pre-deploy invariants (deploy-tree integrity)

The migration mutates the pickled chat tree, so re-confirm the deploy packaging before pushing to prod. These are the recurring 2.0 prod-deploy traps:

```bash
# 1) ADK version pins aligned (skew → opaque 400/500 "...failed to be updated")
grep "google-adk" pyproject.toml api/pyproject.toml app/adk/pyproject.toml app/adk/requirements.txt
#    expect: google-adk[mcp]==2.0.0 in all four

# 1b) aiplatform pin aligned between the cloudpickle SDK (app/adk/uv.lock) and the
#     CONTAINER manifest (app/adk/requirements.txt). An UNPINNED requirements.txt
#     entry was the AH-121 staging-deploy failure: deploy_ken_e.py pickles the agent
#     with the LOCKED aiplatform's AdkApp wrapper (vertexai.agent_engines.templates.adk),
#     but the unpinned container installed a newer aiplatform where that module moved →
#     `ModuleNotFoundError` at engine boot → the opaque "400 ...failed to be updated".
grep "google-cloud-aiplatform" app/adk/requirements.txt      # expect a pinned ==<version>
grep -A2 'name = "google-cloud-aiplatform"' app/adk/uv.lock | grep version
#     the two versions MUST match (verify_deploy_tree.py asserts this; see check below)

# 2) Chat deploy venv declares the deps ADK 2.0 dropped as transitives
grep -E "aiplatform\[agent-engines\]|google-cloud-secret-manager" app/adk/pyproject.toml

# 3) Deploy-tree cloudpickle smoke (the CI deploy-tree-smoke step, run locally)
uv run --no-sync python deployment/ci/scripts/verify_deploy_tree.py
```

| Invariant | Expected | Result |
|---|---|---|
| `google-adk==2.0.0` in all 4 manifests | yes | ✅ `google-adk[mcp]==2.0.0` in `pyproject.toml`, `api/pyproject.toml`, `app/adk/pyproject.toml`, `app/adk/requirements.txt` |
| `aiplatform` pin in `requirements.txt` == locked `aiplatform` in `uv.lock` | match | _paste_ (must be pinned — unpinned skew was the AH-121 staging-deploy failure; the fix (PR #887) pins it `==1.154.0` and adds `verify_deploy_tree.py` Check 6 to assert the match) |
| chat deploy venv deps present (`aiplatform[agent-engines]`, `secret-manager`) | yes | ✅ both present in `app/adk/pyproject.toml` |
| deploy-tree cloudpickle smoke | exit 0 | ✅ `verify_deploy_tree.py` exit 0 — 5 checks on `main` HEAD (agents dir, build_hierarchy import, cloudpickle round-trip, deploy_ken_e import, ADK-major manifest pins); becomes 6 after PR #887 (adds the aiplatform pin==uv.lock check) |
| chat-status-dots OIDC: prod `CHAT_INTERNAL_OIDC_AUDIENCE` == `https://kene-api-prod-395770269870.us-central1.run.app` | match | _paste_ (operator-verified at deploy time — runtime env, not in repo) |

### 1.5 — Go/No-Go decision record

| Gate | Status |
|---|---|
| §1.1 AH-PRD-13 green in staging | _GO / NO-GO_ |
| §1.2 ACs #1–#6 green | _GO / NO-GO_ |
| §1.3 migration merged to main + CI green | _GO / NO-GO_ |
| §1.4 deploy-tree invariants | _GO / NO-GO_ |
| **DECISION** (all GO → GO) | **_GO / NO-GO_** |
| Decided by / timestamp | _paste_ |

**Record the decision as a comment on AH-121 before proceeding to §2.**

---

## §2 — Production Deploy

> Prod deploys via the **approval-gated** `deploy-to-prod-pipeline` trigger. A `main`-push auto-creates a PENDING prod build (and an automatic staging deploy). The cutover is: approve the **right** PENDING prod build after a GO — cancel racing/stale ones first.

### 2.0 — Capture pre-cutover engine ID (REQUIRED for rollback §5)

Before approving any prod build, record the current engine ID so rollback has a known target:

```bash
PREV_ENGINE_ID=$(gcloud secrets versions access latest \
  --secret=ken-e-engine-id --project=ken-e-production)
echo "Pre-cutover engine ID: ${PREV_ENGINE_ID}"
# Paste this value into the §5 rollback table row "Prior engine ID restored" now
```

### 2.1 — Path A: approve the auto-created prod build (canonical)

```bash
# 1) List recent prod builds; identify the PENDING build for the Wave-3 merge commit
gcloud builds list --project=ken-e-cicd \
  --filter='substitutions.BRANCH_NAME=main' --limit=10 \
  --format='table(id,status,substitutions.COMMIT_SHA,createTime)'

# 2) Cancel any STALE/duplicate PENDING prod builds (the push-to-main swarm creates several)
gcloud builds cancel <STALE_BUILD_ID> --project=ken-e-cicd

# 3) Approve the ONE prod build for the correct commit.
#    NOTE: `gcloud builds approve` is not installed in this env — approve via REST.
ACCESS_TOKEN=$(gcloud auth print-access-token)
PROD_BUILD_ID=<the correct PENDING prod build id>
curl -s -X POST \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" -H "Content-Type: application/json" \
  -d '{"approvalResult":{"decision":"APPROVED"}}' \
  "https://cloudbuild.googleapis.com/v1/projects/ken-e-cicd/builds/${PROD_BUILD_ID}:approve"

# 4) Watch it to completion
gcloud builds log ${PROD_BUILD_ID} --project=ken-e-cicd --stream
```

### 2.2 — Path B: manual fallback (force a fresh prod deploy)

If no correct PENDING build exists (e.g. the merge was path-filtered out), submit the prod CD config directly. Source must be uploaded (the config references repo lock files):

```bash
gcloud builds submit --config deployment/cd/deploy-to-prod.yaml --project=ken-e-cicd .
```

**Retry policy:** the `500 INTERNAL` SIGTERM on `agent_engines.update()` is a known transient (AH-PRD-13 §9 / memory). Retry up to **2×**. A 3rd failure → NO-GO, roll back per §5, file a bug. On opaque `400/500 "...failed to be updated"`, read the real error from ReasoningEngine logs:

```bash
gcloud logging read 'resource.type="aiplatform.googleapis.com/ReasoningEngine"' \
  --project=ken-e-production --limit=20 \
  --format='table(timestamp,severity,jsonPayload.message)'
```

**Prod deploy result:**

| Field | Value |
|---|---|
| Build ID | _paste_ |
| Build status | _paste (expected: SUCCESS)_ |
| Engine resource name (prod) | _paste_ |
| Attempt number | _paste (expected: 1)_ |
| Notes | _paste_ |

---

## §3 — Post-Deploy Smoke (prod)

`agent.google_search` **must** be the exercised path — it is the surface this whole PRD de-risks.

```bash
PROD_ENGINE_ID=$(gcloud secrets versions access latest --secret=ken-e-engine-id --project=ken-e-production)
echo "Prod engine: $PROD_ENGINE_ID"
```

### 3.1 — SSE curl (chat router end-to-end)

```bash
BYPASS_TOKEN="<API_TEST_BYPASS_TOKEN from ken-e-production Secret Manager>"
API_URL="https://kene-api-prod-395770269870.us-central1.run.app"
curl -X POST "${API_URL}/api/v1/accounts/<prod-test-account>/chat" \
  -H "Content-Type: application/json" -H "Authorization: Bearer ${BYPASS_TOKEN}" \
  -H "Accept: text/event-stream" --no-buffer \
  -d '{"message":"Say hello and tell me your name.","stream":true}' \
  2>&1 | tee /tmp/ah121-prod-sse.log
```

**Expected:** SSE `data:` text events + a turn-complete event.

### 3.2 — Real `agent.google_search` web-search turn (the exercised path)

With `agent.google_search` assigned (root via the AH-100/AH-116 hot-reload, or a specialist), send a turn that requires a live web search:

```bash
curl -X POST "${API_URL}/api/v1/accounts/<prod-test-account>/chat" \
  -H "Content-Type: application/json" -H "Authorization: Bearer ${BYPASS_TOKEN}" \
  -H "Accept: text/event-stream" --no-buffer \
  -d '{"message":"Use web search: what did Google announce about Gemini this week? Cite sources.","stream":true}' \
  2>&1 | tee /tmp/ah121-prod-search.log
```

**Expected:** a grounded answer with citations (the search sub-agent ran).

### 3.3 — Confirm task-mode dispatch + billing + trace fired (NOT `AgentTool`)

For the §3.2 turn, confirm the migration's contract held in prod:

1. **Billing counted** — the turn's billed tokens include the search leaf's `gemini-2.5-flash` usage (token meter / `chat_sessions` side-table token delta > the caller-only baseline).
2. **Trace shows task-mode** — the Weave trace for the turn shows a `request_task_google_search` / `google_search` task-mode leaf with grounded-search **tool** spans (AC #2; the `generate_content` LLM span remains the known-deferred gap, §1.2 caveat).
3. **No `AgentTool` path** — no `AgentTool.run_async` span; dispatch is via `ctx.run_node`.

**Smoke results:**

| Signal | Expected | Result |
|---|---|---|
| §3.1 SSE curl | text + turn-complete | _paste_ |
| §3.2 grounded web-search answer | citations present | _paste_ |
| §3.3.1 search-leaf tokens billed | > caller baseline | _paste_ |
| §3.3.2 task-mode leaf + grounded tool spans in trace | present | _paste_ |
| §3.3.3 no `AgentTool.run_async` span | absent | _paste_ |

A FAIL on any row → roll back per §5.

---

## §4 — 24h Billing Reconciliation (Weave-vs-meter drift < 0.5%)

Over the first 24h of prod web-search turns, reconcile Weave-observed tokens against the internal meter. **PASS iff drift < 0.5%** (AC #7 third bullet).

```bash
# Window = the first 24h of prod web-search traffic after the §2 cutover completes.
WINDOW_START="2026-__-__T__:__:00Z"   # §2 prod-deploy completion (UTC)
WINDOW_END="2026-__-__T__:__:00Z"     # WINDOW_START + 24h
```

```python
# === B) METER side (authoritative for billing) ===
# Source: api/src/kene_api/chat/accumulator.py (SessionTurnAccumulator) +
#         api/src/kene_api/chat/side_table.py. The task-mode search leaf's
#         usage_metadata reaches the outer stream and IS summed here (AC #1 / the
#         test_chat_billing_parity.py merge gate). Collection-group "chat_sessions"
#         lives at accounts/{account_id}/chat_sessions/{session_id}; the cumulative
#         fields are input_tokens_total / output_tokens_total / reasoning_tokens_total
#         (defined in api/src/kene_api/models/chat.py; written via firestore.Increment
#         in shared/turn_delta.py::to_firestore_delta).
from google.cloud import firestore
db = firestore.Client(project="ken-e-production")
meter_total = 0
# Fields are CUMULATIVE per session. Window the run by scoping to the prod test
# account(s) exercised for the cutover and snapshotting totals at WINDOW_START vs
# WINDOW_END (meter_total = end - start), OR add a .where() on the side-table's
# session-activity timestamp field for an all-traffic sum (confirm the field name
# in side_table.py before relying on it — do not assume).
for doc in db.collection_group("chat_sessions").stream():
    d = doc.to_dict() or {}
    meter_total += (d.get("input_tokens_total", 0)
                    + d.get("output_tokens_total", 0)
                    + d.get("reasoning_tokens_total", 0))
print("meter_total:", meter_total)

# === A) WEAVE side (observed traces — see CAVEAT) ===
# Prod Weave target (deployment/cd/deploy-to-prod.yaml: WANDB_ENTITY/WEAVE_PROJECT_NAME):
import weave
client = weave.init("ken-e/ken-e-strategy-agent-production")
weave_total = 0
# Filter to the chat engine + the window (weave 0.51.x: get_calls() supports a
# filter/query + started_after; confirm the exact kwargs for the pinned version).
for call in client.get_calls():
    usage = (call.summary or {}).get("usage", {}) or {}   # per-model dict
    for model_usage in usage.values():
        weave_total += (model_usage.get("prompt_tokens", 0)
                        + model_usage.get("completion_tokens", 0))
print("weave_total:", weave_total)

# === C) drift ===
# drift = |meter_total - weave_total| / weave_total  → AC #7 target < 0.005
```

> **⚠️ Read the drift DIRECTION, not just its magnitude (carries the §1.2/§3.3 caveat).**
> The search leaf's `generate_content` LLM span is the known-deferred Weave autopatch
> gap (AH-88 won't-fix). The **meter** counts the leaf's `gemini-2.5-flash` tokens
> natively (via `usage_metadata` on the outer stream); **Weave may not**. So in prod
> `meter_total ≥ weave_total` is the EXPECTED, benign shape — it is the autopatch gap,
> **not** the regression this PRD prevents. The regression is the opposite direction:
> `meter_total < weave_total` (the meter dropping the leaf). Therefore:
> - `meter_total ≥ weave_total`, any magnitude → **PASS** the rollback test (record it; if
>   the gap is large, file a Weave-autopatch bug per §1.2 — do NOT roll back; §5 says so).
> - `meter_total < weave_total` by > 0.5% → **FAIL** → roll back per §5 (under-billing).
>
> This makes §4 consistent with §5's directional rule. The symmetric `|drift| < 0.5%`
> in AC #7 assumes both sides see the same tokens; until the autopatch span lands that
> assumption holds only in the `meter ≥ weave` direction. **PO: confirm this directional
> reading of AC #7 before the window opens.** (`ken-e-dev.billing_export` is GCP *cost*
> export, not a token meter — it is NOT a source for this reconciliation.)

| Field | Value |
|---|---|
| Window start (UTC) | _paste_ |
| Window end (UTC) | _paste_ |
| Web-search turns in window | _paste_ |
| Weave total tokens | _paste_ |
| Meter total tokens | _paste_ |
| **Drift %** | **_paste_** |
| **Drift direction** | _meter ≥ weave (benign / autopatch gap) — OR — meter < weave (under-billing)_ |
| Verdict | _PASS (meter ≥ weave, or \|drift\| < 0.5%) / FAIL (meter < weave by > 0.5% → §5)_ |

---

## §5 — Rollback

Trigger rollback if: deploy fails 3× (§2), any §3 smoke row FAILs, or §4 drift ≥ 0.5% **with meter_total < weave_total** (under-billing — the exact regression this PRD prevents). If drift ≥ 0.5% with meter_total > weave_total (over-billing anomaly), do NOT roll back — file a bug and investigate before the next deploy cycle; reverting to the pre-2.0 tree would re-introduce the known `AgentTool` under-billing path.

```bash
# 1) Re-point the prod engine to the last-known-good (pre-cutover) engine revision.
#    deploy_ken_e.py updates the canonical engine in place and writes ken-e-engine-id;
#    capture the PRIOR engine ID BEFORE deploy (§2) so rollback is a known target.
PREV_ENGINE_ID=<recorded before §2 deploy>

# 2) Fastest path: redeploy the previous main commit (pre-Wave-3) to prod via §2.2 manual path
#    Pre-Wave-3 main SHA: 13ce795a (the commit immediately before e7f6ee52 on origin/main)
git stash  # ensure no local modifications are accidentally included
git checkout 13ce795a
cd app/adk && uv sync --frozen && uv run python deploy_ken_e.py --env prod
# NOTE: this bypasses the approval-gated deploy-to-prod-pipeline intentionally — rollback
# must be fast. A direct deploy from a non-HEAD SHA is the documented recovery path.
```

**Important:** rolling the chat tree back to pre-2.0 also reverts the task-mode migration → the `#3984` `AgentTool` event-drop returns and `agent.google_search` under-bills again. Rollback is a **stop-the-bleed**, not a resting state: if rolled back, **un-assign `agent.google_search`** from prod agents (as AH-PRD-13 ran Foundation) until the cutover is re-attempted, so no web-search turn under-bills while rolled back.

| Field | Value |
|---|---|
| Rollback trigger | _paste_ |
| Prior engine ID restored | _paste_ |
| `agent.google_search` un-assigned in prod | _yes/no_ |
| Notes | _paste_ |

---

## §6 — Final Result & Hand-Off

| Gate | Result |
|---|---|
| §1 Go/No-Go decision | _GO / NO-GO_ |
| §2 Prod deploy | _SUCCESS / FAIL_ |
| §3 Post-deploy smoke (all rows) | _PASS / FAIL_ |
| §4 24h reconciliation (drift < 0.5%) | _PASS / FAIL_ |

When §1–§4 are all green:
1. Paste this completed log as a comment on [AH-121](https://linear.app/ken-e/issue/AH-121).
2. Move AH-121 → Done; the **AH-PRD-15 project** and the **ADK 2.0 production cutover** are complete.
3. Note in the AH-PRD-13 PRD that prod is on 2.0 (collapse any `[PLANNED]`/"unassigned until cutover" qualifiers on `agent.google_search`).

If any gate FAILs: execute §5, file a follow-up bug with logs, and re-schedule the cutover.

---

## §7 — References

- **Issue:** [AH-121](https://linear.app/ken-e/issue/AH-121)
- **PRD:** `docs/design/components/agentic-harness/projects/AH-PRD-15-agenttool-migration-cutover.md` §7.7 + §2 + §8 + §9
- **Migration verification:** ACs #1–#6 (AH-114/115/116/117/118/119/120); combined branch `integration/cycle-6-ah-prd-15-wave-3` (PR #885)
- **Staging precondition:** `docs/runs/AH-111-adk2-deploy-smoke.md` (AH-PRD-13 §7 AC #8)
- **Deploy script:** `app/adk/deploy_ken_e.py --env prod`
- **Prod CD:** `deployment/cd/deploy-to-prod.yaml` (trigger `deploy-to-prod-pipeline`, approval-gated; `deployment/terraform/build_triggers.tf` `deploy_to_prod_pipeline`)
- **Task-mode dispatch fix (the model_post_init defect this de-risks):** `app/adk/agents/agent_factory/sub_agent_attacher.py` (`attach_task_subagent` / `_TaskAgentTool` injection)
- **Upstream bug:** `google/adk-python#3984` (AgentTool event streaming — OPEN)
- **Known-deferred trace span:** Weave `generate_content` autopatch (AH-88 won't-fix; AH-PRD-13 §9)
