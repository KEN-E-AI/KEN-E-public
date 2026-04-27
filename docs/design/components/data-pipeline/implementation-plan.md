# Data Pipeline — Implementation Plan

**Status:** Promoted from backlog — 2026-04-23
**Owner:** Data Pipeline component team (TBD)
**Proposed PRD prefix:** `DP-PRD-NN`

> **Promotion note.** This doc supersedes `../backlog/data-pipeline.md`. Architecture rationale and connector roadmap in §1–§4 are ported + refined; §5 adds SAR-E as the first production consumer.

---

## 1. What Data Pipeline is

The Data Pipeline is KEN-E's **deterministic, non-agentic** path to third-party platform APIs. It exists because agent-routed extraction — Root Agent → specialist → MCP tool call → code execution — is the right shape for *reasoning-heavy* requests ("what caused the drop?") but the wrong shape for *repeatable, well-defined* extractions ("pull transactions by date, daily, at 07:00 UTC"). For the second class, the Data Pipeline calls the platform API directly with a known recipe, produces a structured artifact, and hands off to downstream tasks.

Concretely, a task in a project plan can be assigned to the **Data Pipeline** (a third `assignee_type` alongside `agent` and `human`). The task carries a `pipeline_job` reference (e.g., `ga.transactions_by_date`) plus its inputs. When the `TaskOrchestrator` fires the task, it dispatches to the Data Pipeline service — which runs the job via a connector, writes the result as a `TaskArtifact`, and marks the task Complete. Downstream tasks read the artifact as upstream context.

Three facts shape the design:

1. **Reasoning lives in agents; extraction lives in pipelines.** Complementary, not alternatives. The Google Analytics Specialist (AH-PRD-03) continues to own ambiguous analytical questions; Data Pipeline owns deterministic pulls.
2. **Pipeline jobs are declarative recipes, not code.** Users pick from a catalog; they do not write Python. Custom code lives in Skills.
3. **SAR-E is the first production consumer.** The KPI ingestion powering SAR-E's VAR model is a daily `is_system` automation invoking 4 pre-seeded GA jobs.

## 2. What exists today (before Data Pipeline)

| Upstream | What it gives us |
|---|---|
| **PR-PRD-01** | `PlanTask` + `ProjectPlan` + DAG. Data Pipeline adds `assignee_type="data_pipeline"` + `pipeline_spec`. |
| **PR-PRD-04** | `TaskOrchestrator` dispatch branches. Adds a `data_pipeline` branch. |
| **A-PRD-03** | `TaskArtifact` + GCS storage. Pipeline outputs are artifacts. |
| **Integrations (IN-PRD-02)** | OAuth flows + encrypted token store + refresh lifecycle for every third-party platform. Connectors read credentials via Integrations' internal endpoint, never directly from Firestore. |
| **DM-PRD-00** | Shape B convention + migration framework for new `data_pipeline_jobs` / `accounts/*/data_pipeline_runs` collections. |

## 3. Data-model

### 3.1 Pydantic shapes

```python
class PipelineJobSpec(BaseModel):
    job_id: str
    inputs: dict                           # validated against job's input_schema
    output_artifact_name: str

class PlanTask(BaseModel):
    # ... existing fields
    assignee_type: Literal["agent", "human", "data_pipeline"]   # extended
    pipeline_spec: PipelineJobSpec | None = None

class DataPipelineJob(BaseModel):
    job_id: str
    connector: Literal["google_analytics", "google_ads", "meta_ads", "mailchimp"]
    operation: str                         # "transactions_by_date"
    display_name: str
    description: str
    input_schema: dict                     # JSON Schema
    output_schema: dict                    # JSON Schema
    output_format: Literal["parquet", "json", "csv"] = "parquet"
    bigquery_external_table: BqTableRef | None = None      # optional external table over the Parquet artifact
    default_cache_ttl_seconds: int | None
    test_mode_policy: Literal["run_normally", "sandbox_endpoint", "fail_not_testable"] = "run_normally"
    visible_in_frontend: bool
    version: int

class DataPipelineRun(BaseModel):
    run_id: str
    account_id: str
    plan_id: str
    task_id: str
    job_id: str
    inputs: dict
    input_hash: str
    output_artifact_id: str | None
    status: Literal["running", "succeeded", "failed", "cached"]
    cache_hit: bool
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None
    tokens_charged: int = 0                # always 0; kept for parity with agent runs

class DataPipelineConnector(Protocol):
    async def run(self, operation: str, inputs: dict, credentials: dict) -> PipelineOutput: ...

class PipelineOutput(BaseModel):
    rows: list[dict]
    schema: list[FieldSpec]
    metadata: dict                         # {row_count, query_params, source_api_version}
```

### 3.2 Firestore layout (Shape B carve-outs)

| Path | Scope |
|---|---|
| `data_pipeline_jobs/{job_id}` | Global catalog (Shape B carve-out, mirrors `agent_configs/*`) |
| `accounts/{account_id}/data_pipeline_jobs/{job_id}` | Per-account overlay + custom jobs |
| `accounts/{account_id}/data_pipeline_runs/{run_id}` | Execution history |

### 3.3 Execution model

- **Deployment target:** sibling Cloud Run service (`kene-data-pipeline-{env}`). Isolated from request-path latency budgets; independent scaling. Connects to Firestore + GCS.
- **Invocation:** `TaskOrchestrator` HTTP-calls `POST /internal/data-pipeline/run` (OIDC-authed, same pattern as PR-PRD-06 / A-PRD-02).
- **Concurrency:** fire-and-forget from orchestrator; service PATCHes back to the plan when done. 10-min cap per run.
- **Credential loading:** via Integrations' internal endpoint (`GET /internal/integrations/credentials/{account_id}/{platform_id}`, OIDC). Integrations owns the OAuth lifecycle; Data Pipeline is a read-only consumer.
- **Cache key:** `sha256(account_id || job_id || canonical_json(inputs) || job.version)`. Cache hits still write a `DataPipelineRun` (`status=cached`) for audit completeness.
- **Artifact format:** Parquet by default (columnar, typed, ~10× smaller than JSON for tabular data). Jobs emitting non-tabular output (single-record fetches, nested documents) set `output_format="json"`. Jobs that declare `bigquery_external_table` trigger creation / refresh of a BigQuery external table pointing at the Parquet artifact — gives SQL access without duplicating storage.
- **Rate limits (per account, per connector — v1 starting points):** `google_analytics` 100/day · 20/hr · 5 concurrent · `google_ads` 50/day · 10/hr · 3 concurrent · `meta_ads` 50/day · 10/hr · 3 concurrent · `mailchimp` 20/day · 5/hr · 2 concurrent. Breach returns `429` with `Retry-After`; after 3 breaches in a 24-hour window an account-level notification fires. Tuned via DP-PRD-06 telemetry.
- **Error handling:** transient errors (network, 5xx, platform 429) auto-retry with exponential backoff (3 attempts). Semantic 4xx errors fail the task, surface a notification with the API response, and hold the plan — no agent-driven retry in v1 (see [`../backlog/pipeline-error-recovery-specialist.md`](../backlog/pipeline-error-recovery-specialist.md) for the future enhancement). Auth 401/403 trigger Integrations' re-auth flow; downstream tasks halt until reconnection.
- **Test-mode behavior:** pipeline tasks run normally under `is_test=true` so downstream analysis agents in a test plan have real upstream data to validate against. The `test_mode_policy` attribute on `DataPipelineJob` (default `run_normally`) lets future write-capable jobs opt into `sandbox_endpoint` — side-effect suppression happens at side-effecting tasks (email, ad spend), not at extraction tasks.
- **Observability:** every run emits a `data_pipeline.run` Weave span with `{connector, operation, input_hash, row_count, cache_hit, test_mode}`.

## 4. API surface

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/data-pipeline/jobs` | List catalog (global + per-account overlay); filter by connector. |
| `GET` | `/api/v1/data-pipeline/jobs/{job_id}` | Fetch job definition (input schema for form rendering). |
| `POST` | `/api/v1/data-pipeline/jobs` | Create a per-account custom job. Validated against the `DataPipelineJob` schema + a JSON-Schema meta-validator on the declared `input_schema` / `output_schema`. Requires `editor` role or higher (DM-PRD-07). |
| `GET` | `/api/v1/data-pipeline/{account_id}/runs` | List runs (filters: plan_id, task_id, job_id, status, date range). |
| `GET` | `/api/v1/data-pipeline/{account_id}/runs/{run_id}` | Run details + artifact link. |
| `POST` | `/api/v1/internal/data-pipeline/run` | OIDC; called by the orchestrator on task dispatch. |

Pipeline-task authoring endpoints (`POST /plans/.../tasks` with `assignee_type=data_pipeline`) live on project-tasks, not here.

## 5. Integration with SAR-E (new for this promotion)

SAR-E is the first production consumer. The integration is a single `is_system=true` recurring automation per account:

```
Plan: "SAR-E Daily KPI Ingestion" (is_system=true, recurrence: 0 7 * * * UTC)
  ├─ task_1: ga.unbranded_search_daily    (assignee_type=data_pipeline)
  ├─ task_2: ga.branded_search_daily      (assignee_type=data_pipeline)
  ├─ task_3: ga.pdp_views_daily           (assignee_type=data_pipeline)
  ├─ task_4: ga.first_purchases_daily     (assignee_type=data_pipeline)
  └─ task_5: sar-e.ingest                 (assignee_type=agent, depends_on=[1,2,3,4])
```

Requirements this places on Data Pipeline:
- Four GA jobs seeded into the catalog in DP-PRD-02.
- Output shape stable enough that SAR-E ingests without schema adaptation across runs.
- The `ga.*_daily` jobs accept a `target_date: date` input (default: yesterday UTC) and return `[{date, value}]` rows — simplest possible output for time-series append.
- `default_cache_ttl_seconds=0` on these jobs (each daily pull is unique by date).

For the initial 13-month history backfill, SAR-E runs the same jobs with a wide date range as a one-shot `is_system` plan.

## 6. Integration with existing components

### 6.1 Project Tasks

- **PR-PRD-01** (Data Model & API): extended with `assignee_type="data_pipeline"` + `pipeline_spec`. DAG validator unchanged.
- **PR-PRD-03** (Calendar Page): `ProjectEditDrawer` gains a "Data Pipeline" assignee option; when chosen, a schema-driven job-picker + inputs form replaces agent / human fields.
- **PR-PRD-04** (Event-Driven Orchestrator): `TaskOrchestrator` gains a `data_pipeline` branch. Revision loop is disabled for pipeline tasks (deterministic output — nothing to revise).

### 6.2 Automations

- **A-PRD-02** (Recurring Scheduler): unchanged. `{inputs.*}` substitution applies to `pipeline_spec.inputs` the same way it applies to agent prompts.
- **A-PRD-03** (Task Artifact System): pipeline output is a `TaskArtifact` — same bucket, same lifecycle.
- **A-PRD-04** (Test / Dry-Run Mode): pipeline tasks run normally in test mode so downstream analysis agents can validate against real data. The `test_mode_policy` attribute on `DataPipelineJob` (default `run_normally`) lets future write-capable jobs opt into `sandbox_endpoint` where the platform provides one, or `fail_not_testable` for jobs that cannot run safely in test mode. Skipping is not a default — it starves downstream analysis of the input it needs to be tested.

### 6.3 Agentic Harness

- **AH-PRD-03** (GA Specialist): no changes; continues to own the reasoning path. First DP connector hits GA Data API via the official Python client (not MCP) — independent failure modes.
- **Future specialists** (AH-PRD-05+): a specialist and a connector for the same platform can ship in either order.

### 6.4 Knowledge Graph (future)

Pipeline artifacts are natural inputs for dated `Observation` ingestion (KG-PRD-02). Out of scope here; noted to inform artifact-schema decisions.

## 7. Phasing

Six PRDs:

### DP-PRD-01 — Foundation

**Delivers:** All Pydantic models (`DataPipelineJob`, `DataPipelineRun`, `PipelineJobSpec`, `PipelineOutput`, `DataPipelineConnector` protocol); `DataPipelineService` scaffold + `POST /internal/data-pipeline/run` (OIDC-authed); cache-lookup + run-record persistence; `StubConnector` for contract tests; Firestore collections + migration.

**Exit criteria:** a stub job runs end-to-end, writes a `DataPipelineRun`, returns a `PipelineOutput`.

**Blocked by:** DM-PRD-00.

**Blocks:** DP-PRD-02, DP-PRD-03.

**Effort:** 3–4 days.

### DP-PRD-02 — Google Analytics connector

**Delivers:** `GoogleAnalyticsConnector` (GA Data API v1 Python client); starter catalog:

- `ga.sessions_by_date`
- `ga.transactions_by_date`
- `ga.conversions_by_source_medium`
- `ga.top_landing_pages`
- **`ga.unbranded_search_daily` / `ga.branded_search_daily` / `ga.pdp_views_daily` / `ga.first_purchases_daily`** — four SAR-E-specific jobs (new for this promotion).

Credential loading via Integrations (`/internal/integrations/credentials/{account_id}/google`); rate-limit enforcement per the §3.3 starting points; retry / auth-error handling; unit tests (mocked GA client + stub credentials service); integration tests (live API + live OAuth, `@pytest.mark.platform`).

**Exit criteria:** each seeded GA job runs end-to-end against a real GA4 property and produces a deterministic Parquet artifact. SAR-E's 4 daily jobs produce stable `[{date, value}]` output.

**Blocked by:** DP-PRD-01, IN-PRD-02 (Google OAuth flow + credential substrate).

**Blocks:** DP-PRD-03 (task-system integration requires a real connector), **SE-PRD-02** (SAR-E ingestion depends on the 4 daily jobs).

**Effort:** 4–5 days.

### DP-PRD-03 — Task-system integration

**Delivers:** `PlanTask.assignee_type` extension + `pipeline_spec` field (PR-PRD-01 patch); `TaskOrchestrator.on_task_due` / `on_task_status_change` `data_pipeline` branch (PR-PRD-04 patch); `DataPipelineDispatcher` bridging orchestrator → service; `TaskArtifact` write via A-PRD-03; revision-loop disabled for pipeline tasks; `is_test` policy per job.

**Exit criteria:** a plan with a pipeline task can be activated; task runs, artifact is written, a downstream agent task sees it as upstream context.

**Blocked by:** DP-PRD-02, PR-PRD-04, A-PRD-03, A-PRD-04.

**Blocks:** DP-PRD-04, DP-PRD-06, SE-PRD-02.

**Effort:** 3–4 days.

### DP-PRD-04 — Frontend + custom-job authoring

**Delivers:** "Data Pipeline" option in the task-creation right-side panel that opens from the shared DAG editor's "+ Add Task" button (A-PRD-06's panel, used on `/workflows/automations/{plan_id}` and `/performance/dashboards/{plan_id}`) and in Calendar's `ProjectEditDrawer`; `<PipelineJobPicker>` browsing the global + account-overlay catalog; schema-driven input form (JSON Schema → form, inline validation); pipeline-run viewer in `ActivityDetailPanel` (status, inputs, artifact preview, cache indicator); **inline `<CustomJobAuthoringPanel>`** mounted in the same side-panel — 4-step stepper (Basics → Schemas → Connection → Preview) for creating / editing per-account jobs, with guided schema builder + Integrations connection picker + "Publish & Use" button that creates the job and selects it back in the parent picker. Platform-global jobs remain read-only from the UI. **No standalone `/workflows/data-pipelines` route group** — that scope was retired.

**Exit criteria:** a user composes, activates, and reviews a pipeline task end-to-end inline from the DAG editor side-panel without API calls; an account editor can author a custom per-account job inline from the same panel, preview it, and use it in a task in the same session.

**Blocked by:** DP-PRD-03, A-PRD-06 (shared DAG editor + side-panel pattern), IN-PRD-03 (connection-management UI — custom-job authoring needs the connection picker), PR-PRD-03 (Calendar — owns `ProjectEditDrawer` + `ActivityDetailPanel` extended in place).

**Blocks:** DP-PRD-06.

**Effort:** 5–6 days (expanded to cover authoring UI).

### DP-PRD-05 — Additional connectors

**Delivers:** `GoogleAdsConnector`, `MetaAdsConnector`, `MailchimpConnector` (can split further if estimation shows). Each ships with a 3–5 job starter catalog. Reuses DP-PRD-02's `load_credentials()` helper unchanged — Integrations IN-PRD-01 v1 contract is OAuth-only, no `auth_type` branching needed. HubSpot deferred until the HubSpot Specialist PRD lands.

**Exit criteria:** users of the R5 narrow-specialist cohort can run deterministic extracts for every covered platform.

**Blocked by:** DP-PRD-02 (framework proven).

**Blocks:** —

**Effort:** 2–3 days per connector (3 connectors).

### DP-PRD-06 — Integration testing & polish

**Delivers:** E2E: pipeline task → artifact → downstream agent task → review loop. Recurring-automation smoke test: pipeline task in a scheduled `PlanRun` with `{inputs.*}` substitution. Concurrent-runs load test per connector. Observability dashboard (run volume, cache-hit rate, failure rate). `api/CLAUDE.md` + `frontend/CLAUDE.md` runbook updates.

**Exit criteria:** verification report appended to the component README; ready to mark GA.

**Blocked by:** DP-PRDs 01–04 (DP-PRD-05 optional for per-connector perf).

**Blocks:** —

**Effort:** 2 days.

## 8. Dependency graph

```
IN-PRD-02 (Google OAuth) ─────────────────────┐
                                              ▼
DP-PRD-01 (Foundation) ──► DP-PRD-02 (GA) ──┬──► DP-PRD-03 (Task system) ──► DP-PRD-04 (Frontend) ──► DP-PRD-06
                                            │                                       ▲
                                            ├──► SE-PRD-02 (SAR-E ingestion)        │
                                            │                                       │
A-PRD-06 (Shared DAG editor) ───────────────┼───────────────────────────────────────┤
PR-PRD-03 (Calendar — ProjectEditDrawer) ───┼───────────────────────────────────────┤
IN-PRD-03 (Connection mgmt UI) ─────────────┼───────────────────────────────────────┘
                                            │
IN-PRD-04 (Meta + Mailchimp OAuth) ─────────┴──► DP-PRD-05 (additional connectors)
```

## 9. Non-goals

- **Replacing the Google Analytics Specialist.** The specialist reasons; the pipeline extracts. Both exist.
- **General-purpose ETL.** Not a substitute for BigQuery / Fivetran / Airbyte. Scope is "repeatable API calls inside a project task."
- **User-authored Python.** Jobs are declarative. Custom code lives in Skills.
- **Cross-platform joins inside one job.** One connector per job; assembly happens in a downstream agent task.
- **Real-time streaming.** All runs are batch, on-demand or scheduled.

## 10. Risks & open questions

### Resolved decisions

| Decision | Resolution |
|---|---|
| Deployment target | **Sibling Cloud Run service** — lower start latency, shared connection pooling. |
| Custom jobs in v1 | **Yes.** Per-account overlay + authoring UI land in DP-PRD-04. Schema validation via a JSON-Schema meta-validator on write. |
| Artifact format defaults | **Parquet** by default; **JSON** fallback for non-tabular outputs; per-job override via `output_format`. Optional BigQuery external table via `bigquery_external_table`. |
| Cache granularity | **Per-account.** Global caching would leak timing signals. |
| Re-auth signaling | **Via Integrations + existing notification system.** Data Pipeline never touches token state directly. |
| Rate-limit budgets | **Starting points in §3.3.** GA 100/day · 20/hr · 5 concurrent; Google Ads 50/10/3; Meta 50/10/3; Mailchimp 20/5/2. DP-PRD-06 telemetry drives tuning. |
| Revision semantics | **Excluded from the review loop.** Transient-error retry + semantic-error fail are the v1 behavior. Agent-driven recovery tracked at [`../backlog/pipeline-error-recovery-specialist.md`](../backlog/pipeline-error-recovery-specialist.md). |
| Test-mode behavior | **Run normally.** Pipeline tasks produce real data so downstream test runs can validate their analysis; side-effect suppression happens at side-effecting tasks, not extraction tasks. Future write-capable jobs opt into `sandbox_endpoint` via `test_mode_policy`. |
| SAR-E-specific job definition | `target_date: date` input (default: yesterday UTC); output `[{date, value}]`; `default_cache_ttl_seconds=0`. Documented as part of DP-PRD-02. |

### Remaining open questions

| Question | Disposition |
|---|---|
| BigQuery external-table management when Parquet schema evolves across job versions | First-pass: new job version → new external table name (version-suffixed); prior tables remain for historical reads. Confirm during DP-PRD-02. |
| KMS key rotation coordination with Integrations | IN-PRD-01 owns KMS; Data Pipeline is a read-only consumer. Rotation should be transparent; validated during IN-PRD-06 integration testing. |
| Custom-job sharing across accounts | Out of scope for v1. An account authors jobs for itself. Cross-account sharing (e.g., for an agency) deferred. |
| Per-job observability alerts | v1: no per-job alerting beyond platform-level breach thresholds. Add if DP-PRD-06 telemetry shows a specific job failing disproportionately. |

## 11. Success criteria

- A pipeline task in a one-shot plan runs end-to-end against a real GA4 property, writes a deterministic artifact, and is re-readable by a downstream agent task.
- A scheduled `is_system` automation invoking 4 pipeline tasks + 1 ingestion task fires daily at 07:00 UTC, completes in under 2 minutes, and appends SAR-E KPI time-series rows.
- Cache-hit rate on a recurring pipeline task with stable inputs is ≥95% (first run uncached, subsequent runs cached until TTL).
- An account with no pipeline-task experience can pick a job from the catalog, fill the form, and activate the plan without API or CLI access.
- `make lint` + `pytest tests/data_pipeline/` green on every PR.
