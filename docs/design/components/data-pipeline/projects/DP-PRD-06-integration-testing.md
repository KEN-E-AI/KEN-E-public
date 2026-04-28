# DP-PRD-06 — Integration Testing & Polish

**Status:** Blocked — resumes once DP-PRD-01, DP-PRD-02, DP-PRD-03, DP-PRD-04 ship (DP-PRD-05 optional for per-connector performance data)
**Owner team:** QA + whichever Data Pipeline team finishes first
**Blocked by:** DP-PRD-01 (foundation + service scaffold); DP-PRD-02 (Google Analytics connector end-to-end); DP-PRD-03 (task-system integration + artifact write); DP-PRD-04 (UI for authoring + run review); DP-PRD-05 (optional — used only for per-connector performance data)
**Blocks:** —
**Estimated effort:** 2 days

---

## 1. Context

The five prior Data Pipeline PRDs deliver the service, the Google Analytics connector, the task-system integration, the Calendar + authoring UI, and (optionally) three additional connectors. Each ships with its own colocated unit + integration tests. This PRD is the **end-to-end closing sprint**: the production-parity workflows nobody owns end-to-end yet — SAR-E's daily `is_system` ingestion, cross-connector rate-limit ceilings, the Weave observability dashboard — plus the runbook updates that hand the component off to operators.

It also performs the final naming audit. Early drafts of this component used `pipeline_job` / `pipeline_run` without the `data_` prefix; the plan §3.1 shapes are `DataPipelineJob` / `DataPipelineRun`. This PRD greps the codebase and docs, kills any stale references, and enforces the canonical names via a CI audit.

This PRD is the belt-and-suspenders check on the three invariants the Data Pipeline component has to satisfy:

1. **Pipeline tasks produce artifacts downstream agents can consume.** A plan composed in the UI with a pipeline task + an agent task that depends on it must run end-to-end with the agent seeing the pipeline's output as upstream context.
2. **Recurring automations with `{inputs.*}` substitution work for the SAR-E ingestion pattern.** The 4-GA-jobs + 1-agent-task template from plan §5 runs daily, completes in under 120 seconds, and stays cache-hit-dominated across runs with stable inputs.
3. **Every run emits a `data_pipeline.run` Weave span.** 100% span-emission rate (no drops) on the happy path; the observability dashboard reads those spans and surfaces run volume, cache-hit rate, failure rate, and per-connector p95 duration.

All three are tested here via automation — E2E Playwright for (1), an integration test simulating the SAR-E cron for (2), and a contract test against emitted spans for (3).

## 2. Scope

### In scope

- **E2E test (full task-system round trip):** pipeline task → artifact → downstream agent task → review loop end-to-end. Covers the R5 narrow-specialist flow where a user composes a plan with a pipeline step + an analysis step, activates it, and sees the agent consume the pipeline artifact.
- **Recurring-automation smoke test:** SAR-E-style `is_system` automation (4 pipeline tasks + 1 ingestion agent task) runs via A-PRD-02 with `{inputs.*}` substitution, completes in < 120 seconds, and produces stable output.
- **Concurrent-runs load test** per connector at its rate-limit ceiling (plan §3.3). GA at 5 concurrent; Google Ads at 3; Meta Ads at 3; Mailchimp at 2. 429s expected past the ceiling with a correct `Retry-After` header.
- **Observability dashboard:** Grafana (or equivalent) panel reading `data_pipeline.run` Weave spans — run volume, cache-hit rate, failure rate, per-connector p95 duration. Panel JSON checked into `deployment/observability/dashboards/`.
- **Weave-span emission audit:** 100% span-emission rate on the happy path; at least one test that runs N pipeline tasks and asserts N spans with the expected `{connector, operation, input_hash, row_count, cache_hit, test_mode}` fields populated.
- **Naming-consistency grep audit** across the codebase + docs. Targets: `data_pipeline_jobs/*`, `/api/v1/data-pipeline/`, `/api/v1/internal/data-pipeline/run`. Asserts no stale references to pre-DP naming (`pipeline_jobs/` without the `data_` prefix, `/api/v1/pipeline/`, or bare `PipelineJob` / `PipelineRun` as Pydantic class names where `DataPipelineJob` / `DataPipelineRun` are meant).
- **Rate-limit ceiling tests** — per-account enforcement under concurrent load.
- **Runbook updates**:
  - `api/CLAUDE.md` gains a "Running Data Pipeline jobs locally" section — how to start the sibling service, invoke `POST /api/v1/internal/data-pipeline/run` with a test token, view runs, invalidate caches by account + job.
  - `frontend/CLAUDE.md` gains a "Authoring a custom pipeline job" walkthrough — open the Automation Details (or Dashboard Details) page, click "+ Add Task" in the shared DAG editor, choose Data Pipeline assignee, click "Or author a new job →", step through Basics / Schemas / Connection / Preview / Publish & Use.
- **Verification report** appended to `docs/design/components/data-pipeline/README.md` capturing observed run volumes, cache-hit rates, p95 durations, and the state of plan §10 open questions at ship time.
- **PROJECT-PLANNER update** — flip all DP-PRD rows to `shipped` once this PRD's gates are green.

### Out of scope

- **Model-correctness testing of downstream agents that consume pipeline artifacts.** That's the downstream agent's concern. DP-PRD-06 asserts the artifact is produced + readable; correctness of analysis built on top of it is owned by the specialist PRD (e.g., SE-PRD-02 for the SAR-E ingestion correctness).
- **Load testing beyond the per-connector rate-limit ceilings.** Multi-tenant aggregate traffic testing is a separate infra concern.
- **Cross-browser Playwright matrix.** Chromium in CI; Safari / Firefox validation is separate infra.
- **Security pen-testing beyond OIDC-scoped endpoint checks.** The pen-test passes on the `/internal/data-pipeline/run` route happen inside the ongoing security-review skill, not here.
- **HubSpot.** Not shipped in DP-PRD-05; nothing to test.
- **Tuning rate-limit budgets.** DP-PRD-06 *surfaces* the per-connector p95 + breach rates; tuning happens in a follow-up polish PR after 30 days of live telemetry.
- **New Pydantic models or frontend types.** This PRD consumes the DP-PRD-01 through DP-PRD-05 contracts as-is.

## 3. Dependencies

- **DP-PRD-01 (Foundation):** service scaffold + `POST /api/v1/internal/data-pipeline/run` + cache + run-record persistence. E2E suites exercise this path end-to-end.
- **DP-PRD-02 (Google Analytics connector):** the seeded GA jobs + the `@pytest.mark.platform` live-API test harness. This PRD extends it with multi-connector rate-limit tests.
- **DP-PRD-03 (Task-system integration):** `assignee_type="data_pipeline"` on `PlanTask`, `TaskOrchestrator` dispatch branch, artifact write via A-PRD-03. E2E-1 exercises the full round trip.
- **DP-PRD-04 (Frontend + custom-job authoring):** Calendar `ProjectEditDrawer` extension + the inline `<PipelineJobPicker>` + `<CustomJobAuthoringPanel>` mounted in A-PRD-06's task-creation side-panel (the right-side panel that opens from the shared DAG editor's "+ Add Task" button on `/workflows/automations/{plan_id}` and `/performance/dashboards/{plan_id}`). E2E suites drive through the DAG-editor UI.
- **DP-PRD-05 (Additional connectors) — optional:** supplies Google Ads / Meta Ads / Mailchimp connectors for per-connector perf data. If DP-PRD-05 hasn't shipped, this PRD's rate-limit ceiling tests cover GA only and the dashboard omits the other connectors' series.
- **A-PRD-02 (Recurring scheduler):** the SAR-E smoke test uses the scheduler to fire the daily plan on a test-only cron expression; `{inputs.*}` substitution behavior verified here.
- **A-PRD-03 (Task artifact system):** artifact read used by the downstream agent task in E2E-1.
- **A-PRD-04 (Test / dry-run mode):** the E2E suites run with `is_test=true` where appropriate so the live-API integration tests can use sandbox accounts without contaminating real data.
- **PR-PRD-04 (Event-driven orchestrator):** the dispatcher branch consumed end-to-end.
- **IN-PRD-02 (Google OAuth):** the credential-read endpoint exercised in live tests.
- **DM-PRD-07 (Approval & audit):** the role-based acceptance assertions validate viewer-vs-editor gating still works.
- **Existing files to study:**
  - `/Volumes/WorkDrive/Active Work/Github/KEN-E/docs/design/components/performance/projects/PE-PRD-08-integration-testing.md` — direct pattern template for this PRD
  - `/Volumes/WorkDrive/Active Work/Github/KEN-E/docs/design/components/dashboards/projects/DB-PRD-04-integration-testing-and-polish.md` — secondary template
  - `/Volumes/WorkDrive/Active Work/Github/KEN-E/frontend/e2e/` — existing Playwright setup + helpers
  - `/Volumes/WorkDrive/Active Work/Github/KEN-E/api/tests/` — integration-test patterns
  - `/Volumes/WorkDrive/Active Work/Github/KEN-E/deployment/observability/dashboards/` — dashboard JSON conventions
  - `/Volumes/WorkDrive/Active Work/Github/KEN-E/docs/design/components/data-pipeline/README.md` — verification-report target file
  - `/Volumes/WorkDrive/Active Work/Github/KEN-E/docs/design/components/PROJECT-PLANNER.md` — status table target
  - `/Volumes/WorkDrive/Active Work/Github/KEN-E/api/CLAUDE.md`, `/Volumes/WorkDrive/Active Work/Github/KEN-E/frontend/CLAUDE.md` — runbook targets

## 4. Data contract

This PRD has no new data contract. It consumes DP-PRD-01 through DP-PRD-05's models and endpoints as-is:

- `DataPipelineJob` (plan §3.1) — catalog documents.
- `DataPipelineRun` (plan §3.1) — run records.
- `PipelineJobSpec`, `PipelineOutput` (plan §3.1) — task + connector contracts.
- `PlanTask.assignee_type` (extended by DP-PRD-03 to include `"data_pipeline"`).
- `DataPipelineJob.output_format` values: `"parquet"` (default) / `"json"` / `"csv"`.
- `DataPipelineJob.test_mode_policy` values: `"run_normally"` (default) / `"sandbox_endpoint"` / `"fail_not_testable"`.
- `DataPipelineRun.status` values: `"running"` / `"succeeded"` / `"failed"` / `"cached"`.

Coverage asserted against SAR-E's OpenAPI + the live connectors' published API contracts is enforced in §5 tests (not new models).

## 5. Test plan

### 5.1 End-to-end Playwright suites

**E2E-1 — Pipeline task → artifact → downstream agent task → review loop (golden path)**

Fixture: account with a connected Google Analytics integration + the `ga.sessions_by_date` seeded job + an analytics specialist agent configured.

1. Log in as an editor-role user. Navigate to `/calendar`.
2. Create a new plan titled "GA → analysis smoke test".
3. Add task 1 — `assignee_type="data_pipeline"`, `job_id="ga.sessions_by_date"`, inputs `{start_date: "2026-04-01", end_date: "2026-04-07"}`, `output_artifact_name="ga_sessions_apr_first_week"`.
4. Add task 2 — `assignee_type="agent"`, assignee = Analytics Specialist, prompt references the artifact by name, depends_on `[task_1]`.
5. Activate the plan.
6. Wait for task 1 to fire. Assert:
   - `DataPipelineRun` created with `status="running"` then `status="succeeded"` within 30 seconds.
   - `TaskArtifact` written to GCS; artifact_id persisted on the task.
   - `data_pipeline.run` Weave span emitted with `{connector: "google_analytics", operation: "sessions_by_date", cache_hit: false, row_count: N}`.
7. Open `<ActivityDetailPanel>` for task 1; assert `<PipelineRunPanel>` renders with the artifact preview showing the first 25 rows.
8. Wait for task 2 to fire. Assert:
   - The agent reads the artifact via A-PRD-03's artifact-read contract.
   - Task 2 completes with `status="Awaiting Approval"` (review loop engaged for the agent task).
9. Approve task 2. Assert plan transitions to `completed`.

**E2E-2 — Recurring automation smoke test (SAR-E daily ingestion pattern)**

Fixture: account with connected GA + 4 seeded GA `*_daily` jobs per plan §5 + SAR-E ingestion agent configured. A test-only plan with `is_system=true`, `recurrence_cron="0 7 * * * UTC"`, and the 5-task template (4 pipeline + 1 ingestion).

1. Fire the scheduled `PlanRun` manually via `POST /api/v1/automations/{plan_id}/trigger` (test harness).
2. Assert 4 `DataPipelineRun` records written, one per GA job.
3. Assert `{inputs.*}` substitution wired `target_date: "{inputs.date}"` → today's UTC date.
4. Assert the 5th task (SAR-E ingestion agent) dispatches only after all 4 pipeline tasks succeed.
5. Assert end-to-end wall-clock from `PlanRun.started_at` to `PlanRun.finished_at` is < 120 seconds.
6. Re-run the same `PlanRun` immediately with identical inputs. Assert all 4 GA runs report `cache_hit=true` and `status="cached"` (since `default_cache_ttl_seconds` on each job is 0, the cache hit only fires when the inputs + account + job version match *within the test window* — confirm the test fixture's window is tight enough that cache matches).

Note: plan §5 specifies `default_cache_ttl_seconds=0` on SAR-E's daily jobs because each day's pull is unique by date. The cache-hit assertion here applies when the **same day's job** fires twice — not across days. Test fixture adjusts accordingly.

**E2E-3 — Custom-job authoring + invoke (round trip through DP-PRD-04)**

Fixture: editor-role user with a connected GA integration.

1. Open an existing automation at `/workflows/automations/{plan_id}` (or create one). Click "+ Add Task" in the shared DAG editor; the right-side task panel opens.
2. Choose `assignee_type="data_pipeline"` in the side-panel; the picker renders. Click "Or author a new job →".
3. Step through Basics → Schemas → Connection → Preview inside the side-panel, composing a minimal GA job equivalent to `ga.sessions_by_date` but under a custom `job_id` (e.g., `custom.ga_sessions_test`).
4. Run preview; assert the preview panel renders non-empty rows.
5. Click "Publish & Use". Assert the panel returns to the picker with the new job pre-selected.
6. Fill required inputs in `<PipelineInputsForm>`; click Save to add the task to the plan; activate.
7. Assert the task runs + produces an artifact + emits a `data_pipeline.run` span with the custom `job_id`.

### 5.2 Concurrent-runs load test

Runs in `api/tests/load/test_data_pipeline_concurrent_runs.py` (Locust or asyncio-based; reuse the existing `tests/load_test/` conventions).

For each connector at its plan §3.3 ceiling:

| Connector | Concurrent ceiling | Expected behavior |
|---|---|---|
| `google_analytics` | 5 | First 5 concurrent runs succeed; 6th returns 429 with `Retry-After`. |
| `google_ads` | 3 | First 3 succeed; 4th returns 429. |
| `meta_ads` | 3 | Same. |
| `mailchimp` | 2 | First 2 succeed; 3rd returns 429. |

Assertions:
- The concurrent ceiling is enforced per-account (not global) — an account A exhausting its GA budget does not starve account B.
- 429 responses carry a `Retry-After` header computed from the tightest violated window.
- After a 3rd breach within a 24-hour window, the account-level notification fires (from DP-PRD-02).
- Pipeline task happy-path p95: **dispatch → artifact written < 30 seconds** for a 10,000-row GA pull (plan §11 target). Measured on the `ga.sessions_by_date` job with a sandbox property containing ≥10k rows in the chosen date range.

If DP-PRD-05 has not shipped, the Google Ads / Meta Ads / Mailchimp rows are skipped (marked `xfail` until the connectors exist).

### 5.3 Observability dashboard

- Dashboard JSON committed to `deployment/observability/dashboards/data-pipeline.json`.
- Panels backed by `data_pipeline.run` Weave spans:
  1. **Run volume** — runs per hour, stacked by `connector`.
  2. **Cache-hit rate** — % of runs where `cache_hit=true`, 15-minute rolling, per connector.
  3. **Failure rate** — % of runs where `status="failed"`, 15-minute rolling, per connector.
  4. **Per-connector p95 duration** — p95 of `finished_at - started_at` by connector, 5-minute rolling.
- Dashboard JSON lint-checked in CI (existing pattern if present; if not, ship a simple schema validator alongside).

### 5.4 Weave-span emission audit

Runs in `api/tests/integration/test_data_pipeline_span_emission.py`:

- Fires 20 pipeline tasks end-to-end (mixed connector + cache-hit / cache-miss scenarios).
- Asserts 20 `data_pipeline.run` spans received by the test Weave sink.
- Asserts every span carries the documented attribute set (plan §3.3): `{connector, operation, input_hash, row_count, cache_hit, test_mode}`.
- Asserts no span is emitted for a preview-endpoint call (DP-PRD-04 `/jobs/preview` uses `data_pipeline.preview` — a *different* span namespace).

### 5.5 Naming-consistency grep audit

Implemented as `api/tests/integration/test_data_pipeline_naming_audit.py` (Python-launched `grep` is the most portable form). Three patterns must return zero matches in the code + docs:

```bash
# 1) No stale pre-DP collection paths
grep -rn --include='*.py' --include='*.ts' --include='*.tsx' --include='*.md' \
  -E 'pipeline_jobs/[^d]|/api/v1/pipeline/|/internal/pipeline/run' \
  app/ api/src/ frontend/src/ docs/

# 2) No bare PipelineJob / PipelineRun as Pydantic class names
grep -rn --include='*.py' \
  -E 'class PipelineJob\b|class PipelineRun\b' \
  app/ api/src/

# 3) Canonical path spot-checks
grep -rn --include='*.py' --include='*.ts' --include='*.tsx' --include='*.md' \
  'data_pipeline_jobs/' app/ api/src/ frontend/src/ docs/ | head -1
grep -rn --include='*.py' --include='*.md' \
  '/api/v1/internal/data-pipeline/run' app/ api/src/ docs/ | head -1
```

The first two greps must return zero matches. The third grep must return at least one match (confirming the canonical paths are actually used). All three run as CI gates; a single violation of (1) or (2), or an empty result on (3), fails the build.

Exceptions: `DataPipelineJob` / `DataPipelineRun` intentionally contain the substring `PipelineJob` / `PipelineRun`; the grep uses word-boundary `\b` to avoid false positives. `PipelineJobSpec` and `PipelineOutput` are canonical (per plan §3.1) and remain untouched.

### 5.6 Runbook updates

**`api/CLAUDE.md` — new section "Running Data Pipeline jobs locally":**

- How to start the `kene-data-pipeline-dev` sibling service (`cd app/data_pipeline && uv run uvicorn ...`).
- How to invoke `POST /api/v1/internal/data-pipeline/run` with a local OIDC token (reuse the existing dev-token helper).
- How to tail `DataPipelineRun` records from the Firestore emulator.
- How to invalidate a specific cache entry: `DELETE` under `accounts/{account_id}/data_pipeline_runs/{run_id}` (admin-only; deletes the run and forces the next dispatch to re-hit the connector since cache lookup is keyed on `sha256(account_id || job_id || canonical_json(inputs) || job.version)` and cache entries live on the run record).
- How to force-bump a job version (stamp `version+=1` on the global `data_pipeline_jobs/{job_id}` doc) to effectively invalidate every cached run of that job.

**`frontend/CLAUDE.md` — new section "Authoring a custom pipeline job":**

- Short walkthrough: log in as an editor → open an automation at `/workflows/automations/{plan_id}` → click "+ Add Task" in the DAG editor → choose Data Pipeline assignee → click "Or author a new job →" → step through Basics / Schemas / Connection / Preview → Publish & Use → finish creating the task with the new job.
- How to reset an in-progress authoring session (close the tab; no draft persistence for authoring in v1 — confirm at kickoff whether DP-PRD-04 adds a draft collection).
- Where authored jobs live (`accounts/{account_id}/data_pipeline_jobs/{job_id}`).

### 5.7 Verification report (README append)

On completion, append a new section to `docs/design/components/data-pipeline/README.md`:

```markdown
## Verification Report (Shipped YYYY-MM-DD)

The Data Pipeline component shipped on YYYY-MM-DD. This section records the observed state at ship time.

**E2E coverage:** All three Playwright suites (`data-pipeline-e2e-golden-path`, `data-pipeline-sar-e-smoke`, `data-pipeline-custom-job-authoring`) green in CI.

**Performance targets (observed):**
- Recurring `is_system` automation (SAR-E daily ingest, 4 pipeline tasks + 1 agent task) end-to-end wall-clock: p95 = XXXs (target < 120s).
- Cache-hit rate on a recurring task with stable inputs: XX% (target ≥ 95%).
- Per-run Weave span emission rate: XX.X% (target 100%).
- Pipeline task happy-path round-trip (dispatch → artifact written): p95 = XXXs for a 10,000-row GA pull (target < 30s).

**Concurrent-runs ceilings:** GA 5; Google Ads 3; Meta Ads 3; Mailchimp 2. 429 + `Retry-After` returned past each ceiling; 3-breach account notification verified.

**Naming-consistency audit:** Zero stale references to `pipeline_jobs/` (without the `data_` prefix), `/api/v1/pipeline/`, or bare `PipelineJob` / `PipelineRun` Pydantic class names across `app/`, `api/src/`, `frontend/src/`, `docs/`.

**Observability dashboard:** Panels live in Grafana at {URL}; backing span namespace `data_pipeline.run`.

**Runbook updates:** `api/CLAUDE.md` + `frontend/CLAUDE.md` sections merged.

**Open questions at ship time:** <paste from implementation-plan §10 open questions with resolution notes>
```

## 6. Implementation outline

| Action | File |
|--------|------|
| Create | `frontend/e2e/data-pipeline.spec.ts` — E2E-1 (Pipeline → artifact → agent task → review loop) |
| Create | `frontend/e2e/data-pipeline-sar-e-smoke.spec.ts` — E2E-2 (recurring-automation 4+1 pattern) |
| Create | `frontend/e2e/data-pipeline-custom-job-authoring.spec.ts` — E2E-3 (authoring → preview → publish → invoke) |
| Create | `api/tests/data_pipeline/test_concurrent_runs_load.py` — §5.2 rate-limit ceiling + p95 targets |
| Create | `api/tests/data_pipeline/test_span_emission.py` — §5.4 Weave-span audit |
| Create | `api/tests/data_pipeline/test_naming_audit.py` — §5.5 grep audit as a pytest-run gate |
| Create | `deployment/observability/dashboards/data-pipeline.json` — §5.3 Grafana dashboard |
| Modify | `api/CLAUDE.md` — add "Running Data Pipeline jobs locally" section (§5.6) |
| Modify | `frontend/CLAUDE.md` — add "Authoring a custom pipeline job" section (§5.6) |
| Modify | `docs/design/components/data-pipeline/README.md` — append Verification Report per §5.7 + "Shipped YYYY-MM-DD" banner at the top |
| Modify | `docs/design/components/PROJECT-PLANNER.md` — flip all DP-PRD rows to `shipped` with today's date |
| Verify | `deployment/ci/` — pipeline includes the new E2E + load + naming-audit specs on PR and nightly |

## 7. API contract

This PRD owns no new endpoints. It consumes:

| Method | Path | Purpose | Owner |
|---|---|---|---|
| `POST` | `/api/v1/internal/data-pipeline/run` | Dispatches a pipeline run; exercised in E2E + load tests | DP-PRD-01 |
| `GET` | `/api/v1/data-pipeline/{account_id}/runs` | Lists runs for assertions | DP-PRD-01 |
| `GET` | `/api/v1/data-pipeline/{account_id}/runs/{run_id}` | Fetches a single run for assertions | DP-PRD-01 |
| `GET` | `/api/v1/data-pipeline/jobs` | Lists catalog for E2E filter assertions | DP-PRD-01 |
| `POST` | `/api/v1/data-pipeline/jobs` | E2E-3 publishes a custom job | DP-PRD-01 |
| `POST` | `/api/v1/data-pipeline/jobs/preview` | E2E-3 runs the preview step | DP-PRD-04 |
| `POST` | `/api/v1/automations/{plan_id}/trigger` | E2E-2 fires the recurring plan manually | A-PRD-02 |
| `GET` | `/api/v1/artifacts/{artifact_id}/preview` | Artifact preview in the run viewer | A-PRD-03 |

## 8. Acceptance criteria

1. `frontend/e2e/data-pipeline.spec.ts` (E2E-1) passes in CI — pipeline task fires, writes an artifact, downstream agent task reads it via upstream-context, review loop engages, plan completes.
2. `frontend/e2e/data-pipeline-sar-e-smoke.spec.ts` (E2E-2) passes — the 4-pipeline + 1-agent plan runs to completion with `{inputs.*}` substitution, end-to-end wall-clock < 120 seconds (plan §11 + this PRD's perf target).
3. E2E-2 re-run with identical inputs inside the cache window produces `cache_hit=true` and `status="cached"` on each of the 4 pipeline `DataPipelineRun` records, demonstrating cache-hit rate ≥ 95% on stable-input recurring tasks (plan §11).
4. `frontend/e2e/data-pipeline-custom-job-authoring.spec.ts` (E2E-3) passes — author → preview → publish → invoke round trip completes without API calls outside the UI.
5. `api/tests/data_pipeline/test_concurrent_runs_load.py` enforces per-connector ceilings: GA 5; Google Ads 3; Meta Ads 3; Mailchimp 2. Breaches return 429 with a correct `Retry-After`. Google Ads / Meta / Mailchimp rows may be `xfail` when DP-PRD-05 is not yet merged; GA row must always pass.
6. Pipeline task happy-path round-trip p95 < 30 seconds for a 10,000-row GA pull (plan §11 target), measured in the load test.
7. `api/tests/data_pipeline/test_span_emission.py` asserts 100% span-emission rate on 20 sampled runs; every span carries `{connector, operation, input_hash, row_count, cache_hit, test_mode}`.
8. `api/tests/data_pipeline/test_naming_audit.py` returns zero matches for stale `pipeline_jobs/` (without `data_` prefix), `/api/v1/pipeline/`, `/internal/pipeline/run`, or bare `class PipelineJob` / `class PipelineRun` in `app/`, `api/src/`, `frontend/src/`, `docs/`; canonical paths (`data_pipeline_jobs/`, `/api/v1/internal/data-pipeline/run`) confirmed present via spot-check greps.
9. Observability dashboard (`deployment/observability/dashboards/data-pipeline.json`) renders four panels (run volume, cache-hit rate, failure rate, per-connector p95) backed by `data_pipeline.run` spans. Panel JSON committed and lint-validated.
10. `api/CLAUDE.md` contains a "Running Data Pipeline jobs locally" section covering service startup, test invocation, run inspection, and cache invalidation.
11. `frontend/CLAUDE.md` contains an "Authoring a custom pipeline job" walkthrough covering the inline-in-DAG-editor flow end-to-end (no standalone route — open Automation Details → "+ Add Task" → Data Pipeline assignee → "Or author a new job →" → Basics / Schemas / Connection / Preview / Publish & Use).
12. `docs/design/components/data-pipeline/README.md` gains a "Shipped YYYY-MM-DD" banner + a Verification Report section per §5.7.
13. `docs/design/components/PROJECT-PLANNER.md` DP-PRD rows all read `shipped` with today's date.
14. Cross-account isolation confirmed by a test: an editor on account A cannot PATCH a pipeline task against an `accounts/{B}/data_pipeline_jobs/*` custom job; `POST /api/v1/internal/data-pipeline/run` with `account_id=A` + a custom-job `job_id` from account B returns 404.
15. Role-based access confirmed: a viewer-role user cannot hit `POST /api/v1/data-pipeline/jobs`, `POST /api/v1/data-pipeline/jobs/preview`, `PUT /api/v1/data-pipeline/jobs/{job_id}`, or `DELETE /api/v1/data-pipeline/jobs/{job_id}` (all return 403).
16. `make lint` clean; `pytest api/tests/data_pipeline/` all green; `npm run build` + `npm run typecheck` clean; Playwright CI green.
17. All `data_pipeline.run` spans are present in the configured Weave sink after a dry-run of E2E-1 + E2E-2; zero dropped spans.

## 9. Risks & open questions

### Resolved decisions

| Decision | Resolution |
|---|---|
| E2E fixture strategy | Reuse `@pytest.mark.platform` live-API harness from DP-PRD-02 for connector-live slices; mock OAuth + seeded Firestore docs for deterministic slices. |
| Naming-audit grep scope | `app/`, `api/src/`, `frontend/src/`, `docs/`. Widen if refactors surface references outside those trees. |
| Cache-hit target enforcement | 95% threshold on a single recurring-task run with stable inputs (not aggregate across all traffic). Aggregate-traffic tuning lives in follow-up polish. |
| HubSpot scope | Out of scope per DP-PRD-05 deferral. Dashboard omits HubSpot series. Re-add when HubSpot Specialist PRD lands. |
| Runbook ownership | `api/CLAUDE.md` and `frontend/CLAUDE.md` updates owned by this PRD, not scattered across earlier PRDs. Consolidates the operator story in one place. |
| Dashboard platform | Grafana (or platform-team equivalent) — panel JSON in `deployment/observability/dashboards/`. Confirm at kickoff if the observability team picked a different substrate; adjust pathing accordingly. |

### Remaining open questions

| Question | Disposition |
|---|---|
| Nightly-vs-PR cadence for the load + E2E suites | Recommendation: nightly + on PRs touching `app/data_pipeline/**` or `api/src/kene_api/routers/data_pipeline*.py` or `frontend/src/pages/Workflows/**` or `frontend/src/components/dataPipeline/**`. Confirm with infra at kickoff. |
| Dashboard on Grafana vs. another substrate | Depends on observability team's current decision. If non-Grafana, path the dashboard JSON accordingly; the panel shapes remain the same. Confirm at kickoff. |
| DP-PRD-05 merge status at DP-PRD-06 start | If DP-PRD-05 has not shipped, the per-connector perf data in the Verification Report is GA-only; the Google Ads / Meta / Mailchimp sections read "deferred to DP-PRD-05 follow-up." |
| Cache-invalidation runbook ergonomics | Current surface is "delete run record" or "bump `version`". If operators need a named "invalidate by account + job + input_hash" endpoint, revisit post-v1 as a small API addition. |
| Long-running recurring automations and Weave sink back-pressure | Weave span emission is best-effort today. If observation shows drops > 1%, add a local span buffer with retry. Not a v1 concern unless data shows otherwise. |
| How to surface per-job alerts past the platform-level breach threshold | Plan §10 resolution is "no per-job alerting in v1." If DP-PRD-06 telemetry shows a single job failing disproportionately, file a polish PRD. |

## 10. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md) §7 DP-PRD-06, §11 Success criteria
- Siblings: [DP-PRD-01 Foundation](./DP-PRD-01-foundation.md), [DP-PRD-02 Google Analytics connector](./DP-PRD-02-google-analytics-connector.md), [DP-PRD-03 Task-system integration](./DP-PRD-03-task-system-integration.md), [DP-PRD-04 Frontend + custom-job authoring](./DP-PRD-04-frontend-and-custom-jobs.md), [DP-PRD-05 Additional connectors](./DP-PRD-05-additional-connectors.md)
- Pattern template: [PE-PRD-08 Performance Integration Testing & Polish](../../performance/projects/PE-PRD-08-integration-testing.md)
- Secondary template: [DB-PRD-04 Dashboards Integration Testing & Polish](../../dashboards/projects/DB-PRD-04-integration-testing-and-polish.md)
- Upstream: [A-PRD-02 Recurring scheduler](../../automations/projects/A-PRD-02-recurring-scheduler.md), [A-PRD-03 Task artifact system](../../automations/projects/A-PRD-03-task-artifact-system.md), [A-PRD-04 Test / dry-run mode](../../automations/projects/A-PRD-04-test-dry-run-mode.md)
- Upstream: [PR-PRD-04 Event-driven orchestrator](../../project-tasks/projects/PR-PRD-04-event-driven-orchestrator.md)
- Upstream: [IN-PRD-02 Google OAuth](../../integrations/projects/IN-PRD-02-google-oauth-flow.md)
- Role policy: [DM-PRD-07 Approval & audit](../../data-management/projects/DM-PRD-07-approval-workflow-and-audit.md)
- Code files expected to be touched:
  - `frontend/e2e/data-pipeline.spec.ts`
  - `frontend/e2e/data-pipeline-sar-e-smoke.spec.ts`
  - `frontend/e2e/data-pipeline-custom-job-authoring.spec.ts`
  - `api/tests/data_pipeline/test_concurrent_runs_load.py`
  - `api/tests/data_pipeline/test_span_emission.py`
  - `api/tests/data_pipeline/test_naming_audit.py`
  - `deployment/observability/dashboards/data-pipeline.json`
  - `api/CLAUDE.md`
  - `frontend/CLAUDE.md`
  - `docs/design/components/data-pipeline/README.md`
  - `docs/design/components/PROJECT-PLANNER.md`
- CLAUDE.md rules in scope: T-2 (colocated frontend tests), T-3 (integration tests for API changes), T-4 (pure-logic vs DB-touching split — naming audit is pure-logic, concurrent-runs is DB+platform), T-5 (prefer integration over heavy mocking — the E2E suites are the authoritative coverage here), T-6 (unit-test complex algorithms — rate-limit state machine covered indirectly via load test); G-1 (`make lint`), G-2 (`npm run format.fix`), G-3 (`npm run typecheck`); GH-1 (Conventional Commits).
