# Data Pipeline — Product Requirements Document

> **Linear Team:** [KEN-E] Data Pipeline
> **Last Updated:** 2026-04-23
> **Status:** Design complete, implementation not started

## 1. Overview

The Data Pipeline component is KEN-E's **deterministic, non-agentic** path to third-party platform APIs. Agent-routed extraction — Root Agent → specialist → MCP tool call → code execution — is the right shape for reasoning-heavy requests ("what caused last week's drop?") but the wrong shape for repeatable, well-defined extractions ("pull transactions by date, daily, at 07:00 UTC"). For the second class, the Data Pipeline calls the platform API directly with a known recipe, produces a structured artifact, and hands off to downstream tasks. It exists *alongside* narrow specialists (AH-PRD-03 Google Analytics Specialist, future connector-specific specialists), not in place of them.

Concretely, a `PlanTask` carries a third `assignee_type="data_pipeline"` alongside `agent` and `human`. The task holds a `pipeline_spec` (`{job_id, inputs, output_artifact_name}`); when the `TaskOrchestrator` (PR-PRD-04) fires it, the `DataPipelineDispatcher` HTTP-calls the sibling Cloud Run service (`kene-data-pipeline-{env}`) which runs the job via a connector, writes the result as a `TaskArtifact` (A-PRD-03), and reports completion back through a callback endpoint — the main API marks the task `Complete` and downstream tasks read the artifact as upstream context. SAR-E (SE-PRD-02) is the first production consumer: its daily KPI ingestion is a four-job `is_system` automation that feeds a single agent task.

A developer reading only this section should understand: this component owns the `/api/v1/data-pipeline/*` public API, the `/api/v1/internal/data-pipeline/*` internal RPC surface (run + callback), the sibling `kene-data-pipeline-{env}` Cloud Run service, the four connectors (GA, Google Ads, Meta Ads, Mailchimp), the `data_pipeline_jobs/*` Firestore collections, and the inline data-pipeline authoring UX surfaced from inside the shared DAG editor's task side-panel (DP-PRD-04 — `<PipelineJobPicker>` + `<CustomJobAuthoringPanel>`; **no standalone `/workflows/data-pipelines` routes**). It does **not** own OAuth token lifecycle (Integrations — IN-PRD-02), the plan/task DAG (Project Tasks — PR-PRD-01), the orchestrator itself (PR-PRD-04), the recurring scheduler (A-PRD-02), the shared DAG editor itself (A-PRD-06), or artifact storage (A-PRD-03) — it is a consumer of all six.

## 2. Architecture

```
┌───────────────────┐   POST /internal/data-pipeline/run (OIDC)    ┌────────────────────────┐
│  Main API         │ ──────────────────────────────────────────▶  │  kene-data-pipeline    │
│  TaskOrchestrator │                                              │  (sibling Cloud Run)   │
│  (PR-PRD-04)      │                                              │                        │
│      │            │                                              │  DataPipelineService   │
│      │ dispatch   │                                              │   ├─ cache lookup      │
│      ▼            │                                              │   ├─ connector.run()   │
│  Dispatcher ──────┘                                              │   └─ persist run       │
│                                                                  │                        │
│                    POST /internal/data-pipeline/callback (OIDC)  │  Connectors            │
│  Dispatcher ◀─────────────────────────────────────────────────── │   ├─ GoogleAnalytics   │
│      │                                                           │   ├─ GoogleAds         │
│      ▼                                                           │   ├─ MetaAds           │
│  TaskOrchestrator                                                │   └─ Mailchimp         │
│      │ mark Complete                                             │                        │
│      ▼                                                           └───────────┬────────────┘
│  PlanTask (→ downstream)                                                     │ run output
└───────────────────┘                                                          ▼
                                                                  ┌────────────────────────┐
                                                                  │  TaskArtifact (A-PRD-03)│
                                                                  │  gs://kene-task-        │
                                                                  │  artifacts-{env}/…      │
                                                                  │  (Parquet | JSON | CSV)│
                                                                  └────────────────────────┘
       credentials (OIDC, per run)                                             ▲
       ───────────────────────────▶  GET /internal/integrations/credentials/   │
       (IN-PRD-02 internal endpoint)  {account_id}/{platform_id}               │
                                                                               │
                                                                    downstream task reads
```

### 2.1 Key Directories

| Path | Purpose |
|------|---------|
| `services/data_pipeline/src/kene_data_pipeline/service.py` | `DataPipelineService` — entrypoint for `POST /api/v1/internal/data-pipeline/run`; cache check, connector dispatch, run-record write, callback emit. DP-PRD-01. |
| `services/data_pipeline/src/kene_data_pipeline/cache.py` | `sha256(account_id \|\| job_id \|\| canonical_json(inputs) \|\| job.version)` cache key; Firestore-backed; `status=cached` audit rows. DP-PRD-01. |
| `services/data_pipeline/src/kene_data_pipeline/connectors/base.py` | `DataPipelineConnector` Protocol + `BaseConnector` abstract (rate-limit middleware, retry/auth-error handling, Weave span emission). DP-PRD-01/02. |
| `services/data_pipeline/src/kene_data_pipeline/connectors/google_analytics.py` | `GoogleAnalyticsConnector` using the official `google-analytics-data` client. DP-PRD-02. |
| `services/data_pipeline/src/kene_data_pipeline/connectors/{google_ads,meta_ads,mailchimp}.py` | Additional connectors. DP-PRD-05. |
| `services/data_pipeline/src/kene_data_pipeline/connectors/ga_credentials.py` | Thin wrapper around `GET /api/v1/internal/integrations/credentials/{account_id}/{platform_id}` with 401-refresh handling. DP-PRD-02 (extended in DP-PRD-05 for `auth_type`). |
| `services/data_pipeline/src/kene_data_pipeline/routers/internal.py` | OIDC-authed `POST /api/v1/internal/data-pipeline/run`. DP-PRD-01. |
| `services/data_pipeline/src/kene_data_pipeline/seeds/` | Declarative job seed files — GA × 8, Google Ads × 3–5, Meta × 3–5, Mailchimp × 3–5. DP-PRD-02 + DP-PRD-05. |
| `api/src/kene_api/models/data_pipeline_models.py` | Shared Pydantic shapes (`DataPipelineJob`, `DataPipelineRun`, `PipelineJobSpec`, `PipelineOutput`, `FieldSpec`, `BqTableRef`). DP-PRD-01. |
| `api/src/kene_api/routers/data_pipeline.py` | Public catalog + runs endpoints (`/api/v1/data-pipeline/*`). DP-PRD-01 + DP-PRD-04. |
| `api/src/kene_api/routers/internal/data_pipeline_callback.py` | OIDC-authed `POST /api/v1/internal/data-pipeline/callback` — sibling service → main API completion report. DP-PRD-03. |
| `api/src/kene_api/services/data_pipeline_dispatcher.py` | `DataPipelineDispatcher` — bridges `TaskOrchestrator` to the sibling service (fire-and-forget `POST /run`; applies per-job `test_mode_policy`). DP-PRD-03. |
| `frontend/src/components/dataPipeline/PipelineJobPicker.tsx` + `CustomJobAuthoringPanel.tsx` | Inline data-pipeline-task picker + authoring panel surfaced from the shared DAG editor's "+ Add Task" side-panel (and from Calendar's `ProjectEditDrawer`). No standalone route. DP-PRD-04. |
| `frontend/src/components/data-pipeline/PipelineJobPicker.tsx` | Browses global + per-account overlay catalog inside `ProjectEditDrawer`. DP-PRD-04. |
| `frontend/src/components/data-pipeline/SchemaDrivenInputForm.tsx` | JSON-Schema → form renderer for job inputs. DP-PRD-04. |
| `frontend/src/components/data-pipeline/PipelineRunPanel.tsx` | Run viewer inside `ActivityDetailPanel` — status, inputs, artifact preview, cache indicator, Weave link. DP-PRD-04. |
| `frontend/src/components/data-pipeline/JobAuthoringForm.tsx` | Guided schema builder + connection picker (IN-PRD-03) + preview-run CTA. DP-PRD-04. |
| `deployment/terraform/data_pipeline/` | Cloud Run service module for `kene-data-pipeline-{env}`; OIDC service-account bindings to main API + Integrations. DP-PRD-01. |

### 2.2 Data Flow

1. **Authoring.** A user in the Calendar (PR-PRD-03) opens `ProjectEditDrawer`, selects **Data Pipeline** as the assignee (DP-PRD-04), picks a job from `PipelineJobPicker` (platform-global + their account's overlay), and fills the JSON-Schema-driven input form. Save flows through PR-PRD-01's plan-task PATCH.
2. **Dispatch.** When the task becomes due (`on_task_due` from PR-PRD-04 or `on_task_status_change` when a predecessor completes), the orchestrator's `data_pipeline` branch hands off to `DataPipelineDispatcher`. The dispatcher computes `{inputs.*}` substitution (A-PRD-02 style) if the task is inside a `PlanRun`, then fire-and-forget POSTs `/api/v1/internal/data-pipeline/run` to the sibling service with 10-minute cap.
3. **Execution.** The sibling service looks up the job definition (global `data_pipeline_jobs/{job_id}` or `accounts/{account_id}/data_pipeline_jobs/{job_id}` overlay), computes the cache key `sha256(account_id \|\| job_id \|\| canonical_json(inputs) \|\| job.version)`, and either (a) returns a cached `DataPipelineRun` with `status=cached` and an existing artifact id, or (b) loads credentials via Integrations' internal endpoint (`GET /api/v1/internal/integrations/credentials/{account_id}/{platform_id}`, OIDC) and invokes the connector.
4. **Connector execution.** The connector runs against the platform API under per-account rate-limit budgets (§7). Transient errors (network, 5xx, 429) retry with exponential backoff ×3; semantic 4xx fails the task with a notification; auth 401/403 triggers Integrations' re-auth flow (IN-PRD-05). On success it returns a `PipelineOutput(rows, schema, metadata)`.
5. **Artifact write.** The service serializes to Parquet (default) or JSON (non-tabular), uploads to `gs://kene-task-artifacts-{env}/{account_id}/{plan_id}/{run_id}/{task_id}/` via A-PRD-03's artifact store, and records the artifact metadata in `accounts/{account_id}/plan_runs/{run_id}/artifacts/{artifact_id}`. If `bigquery_external_table` is set, a version-suffixed BigQuery external table is created/refreshed over the Parquet object.
6. **Run persistence.** A `DataPipelineRun(run_id, account_id, plan_id, task_id, job_id, inputs, input_hash, output_artifact_id, status, cache_hit, started_at, finished_at, error_message, tokens_charged=0)` is written to `accounts/{account_id}/data_pipeline_runs/{run_id}`. A `data_pipeline.run` Weave span is emitted with `{connector, operation, input_hash, row_count, cache_hit, test_mode}`.
7. **Callback + downstream.** The sibling service POSTs `/api/v1/internal/data-pipeline/callback` to the main API (OIDC). The callback handler calls `DataPipelineDispatcher._on_pipeline_complete`, which advances the task to `Complete` and notifies `TaskOrchestrator` — downstream agent tasks pick up the artifact through A-PRD-03's prompt-injection helper.
8. **SAR-E daily ingestion.** Runs as an `is_system=true` recurring automation: 4 GA pipeline tasks (`ga.unbranded_search_daily`, `ga.branded_search_daily`, `ga.pdp_views_daily`, `ga.first_purchases_daily`) + 1 `sar-e.ingest` agent task depending on all four. Cron `0 7 * * * UTC`. End-to-end target < 120 seconds.

Storage: jobs live in `data_pipeline_jobs/{job_id}` (global catalog — Shape B carve-out mirroring `agent_configs/*`) and `accounts/{account_id}/data_pipeline_jobs/{job_id}` (per-account overlay + custom jobs). Runs live in `accounts/{account_id}/data_pipeline_runs/{run_id}`. Artifact blobs are owned by A-PRD-03; this component never writes to GCS directly outside A-PRD-03's store helpers.

### 2.3 API Contracts

Owned endpoints:

| Endpoint | Method | Owner | Schema |
|----------|--------|-------|--------|
| `/api/v1/data-pipeline/jobs` | GET | DP-PRD-01 | `PaginatedResponse<DataPipelineJob>` — global catalog + per-account overlay; filter `?connector=` |
| `/api/v1/data-pipeline/jobs/{job_id}` | GET | DP-PRD-01 | `DataPipelineJob` — full definition incl. `input_schema` for form rendering |
| `/api/v1/data-pipeline/jobs` | POST | DP-PRD-01 (account-scope authoring in DP-PRD-04) | `DataPipelineJob` (per-account); JSON-Schema meta-validation on `input_schema` + `output_schema`; requires `editor` role (DM-PRD-07) |
| `/api/v1/data-pipeline/jobs/{job_id}` | PUT | DP-PRD-04 | `DataPipelineJob` (per-account only; global jobs are read-only from the API); bumps `version` |
| `/api/v1/data-pipeline/jobs/{job_id}` | DELETE | DP-PRD-04 | Soft-delete via `is_active=false` on per-account overlay docs |
| `/api/v1/data-pipeline/jobs/preview` | POST | DP-PRD-04 | `{job, sample_inputs}` → synchronous sample run ≤30 s; does **not** write `DataPipelineRun` or `TaskArtifact`; emits `data_pipeline.preview` Weave span |
| `/api/v1/data-pipeline/{account_id}/runs` | GET | DP-PRD-01 | Paginated `DataPipelineRun[]`; filters `plan_id, task_id, job_id, status, date_range` |
| `/api/v1/data-pipeline/{account_id}/runs/{run_id}` | GET | DP-PRD-01 | `DataPipelineRun` + signed URL for `output_artifact_id` |
| `/api/v1/internal/data-pipeline/run` | POST | DP-PRD-01 (on sibling service) | OIDC; `{account_id, plan_id, task_id, job_id, inputs, is_test}` → `{run_id, status}` |
| `/api/v1/internal/data-pipeline/callback` | POST | DP-PRD-03 (on main API) | OIDC; `{run_id, status, output_artifact_id?, error_class?, error_message?}` → `200 OK`; idempotent by `run_id` |

Consumed endpoints (not duplicated in the data-pipeline namespace):

| Endpoint | Owner | Purpose in this component |
|---|---|---|
| `GET /api/v1/internal/integrations/credentials/{account_id}/{platform_id}` | IN-PRD-02 (extended by IN-PRD-04) | Every connector's per-run credential fetch — OIDC-authed, returns `{access_token, expires_at, external_account_id, auth_type}` |
| `POST /internal/integrations/connections/{id}/mark-expired` | IN-PRD-05 | Auth 401/403 from a connector triggers re-auth flow |
| `PUT /api/v1/plans/{account_id}/{plan_id}` + `PATCH .../tasks/{task_id}` | PR-PRD-01 | Task authoring with `assignee_type="data_pipeline"` + `pipeline_spec` |
| `TaskOrchestrator.on_task_due` / `on_task_status_change` | PR-PRD-04 | Dispatch branch added by DP-PRD-03 |
| `attach_task_artifact()` helper | A-PRD-03 | Persists connector output as a `TaskArtifact` |
| `{inputs.*}` substitution helper | A-PRD-02 | Applied to `pipeline_spec.inputs` inside a `PlanRun` identically to agent prompts |
| `ConnectionPicker` component | IN-PRD-03 | Sourced from the Integrations connection-management UI for custom-job authoring |

Schema source of truth: `api/src/kene_api/models/data_pipeline_models.py` (Pydantic). Mirrored TypeScript types live in `frontend/src/types/dataPipeline.ts` (`DataPipelineJobId` branded, `DataPipelineJob`, `DataPipelineRun`, `PipelineJobSpec`). The sibling service imports the same Pydantic models from the shared `api/src/kene_api/models/` path — no duplicate definitions.

### 2.4 Key Abstractions

| Abstraction | Path | Purpose |
|-------------|------|---------|
| `DataPipelineJob` | `api/src/kene_api/models/data_pipeline_models.py` | Declarative recipe: `(job_id, connector, operation, input_schema, output_schema, output_format, default_cache_ttl_seconds, test_mode_policy, version, bigquery_external_table?)`. `job_id` matches `^[a-z0-9_]+\.[a-z0-9_]+$`. |
| `DataPipelineRun` | Same file | Execution record with `input_hash`, `status ∈ {running, succeeded, failed, cached}`, `cache_hit`, `tokens_charged=0` (always — kept for parity with agent runs). |
| `PipelineJobSpec` | Same file | `(job_id, inputs, output_artifact_name)` — the field on `PlanTask` when `assignee_type="data_pipeline"`. |
| `PipelineOutput` | Same file | Connector return: `(rows, schema: FieldSpec[], metadata: {row_count, query_params, source_api_version})`. |
| `DataPipelineConnector` (Protocol) | `services/data_pipeline/src/kene_data_pipeline/connectors/base.py` | `async run(operation, inputs, credentials) -> PipelineOutput`. One implementation per platform. |
| `BaseConnector` | Same file | Abstract superclass — rate-limit middleware, exponential-backoff retry, auth-error classification, Weave span emission. Connector subclasses supply `operation → handler` dispatch only. |
| `DataPipelineService` | `services/data_pipeline/src/kene_data_pipeline/service.py` | Internal run entrypoint — cache lookup, credential fetch, connector invocation, run persistence, callback emit. |
| `DataPipelineDispatcher` | `api/src/kene_api/services/data_pipeline_dispatcher.py` | Main-API side adapter — subscribes to `TaskOrchestrator` events, POSTs to the sibling service, applies per-job `test_mode_policy`. |
| `StubConnector` | `services/data_pipeline/src/kene_data_pipeline/connectors/stub.py` | Contract-test connector returning deterministic rows; used by DP-PRD-01's E2E + every PRD that needs to exercise the path without live APIs. |

## 3. Component Dependencies

### 3.1 Depends On

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **Data Management — DM-PRD-00 (Migration Foundation)** | Shape B convention + migration framework provisions the three new collections (`data_pipeline_jobs/*` global carve-out + `accounts/{account_id}/data_pipeline_jobs/*` overlay + `accounts/{account_id}/data_pipeline_runs/*`). | [`../data-management/README.md`](../data-management/README.md), [DM-PRD-00](../data-management/projects/DM-PRD-00-migration-foundation.md) |
| **Data Management — DM-PRD-05 (Deletion Sweep Rewrite)** | `recursive_delete(accounts/{account_id})` covers the new per-account subcollections. Global `data_pipeline_jobs/*` is not account-scoped and is unaffected. | [DM-PRD-05](../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md) |
| **Data Management — DM-PRD-07 (Approval Workflow & Audit)** | `require_role("editor")` on `POST/PUT/DELETE /api/v1/data-pipeline/jobs`; `write_audit` on every mutation; `viewer` can GET the catalog + runs. | [DM-PRD-07](../data-management/projects/DM-PRD-07-approval-workflow-and-audit.md) |
| **Integrations — IN-PRD-02 (Google OAuth + credentials substrate)** | `PlatformConnection` data model + OAuth lifecycle + the internal endpoint `GET /api/v1/internal/integrations/credentials/{account_id}/{platform_id}`. Data Pipeline is a **read-only** consumer of tokens — never reads `accounts/{account_id}/platform_connections/*` directly. | [`../integrations/implementation-plan.md`](../integrations/implementation-plan.md) §3.1, §4 |
| **Integrations — IN-PRD-03 (Connection-management UI)** | `ConnectionPicker` component — embedded in DP-PRD-04's custom-job authoring form so users pick *which* connected account to query. | [`../integrations/implementation-plan.md`](../integrations/implementation-plan.md) §7 IN-PRD-03 |
| **Integrations — IN-PRD-04 (Meta + Mailchimp OAuth)** | OAuth flows + `PlatformConnection` entries for Meta Ads and Mailchimp. Google Ads reuses DP-PRD-02's Google OAuth app. | [`../integrations/implementation-plan.md`](../integrations/implementation-plan.md) §7 IN-PRD-04 |
| **Integrations — IN-PRD-05 (Re-auth notification loop)** | Auth 401/403 from a connector calls `POST /internal/integrations/connections/{id}/mark-expired`; user re-auth surfaces in the existing notification UI. | [`../integrations/implementation-plan.md`](../integrations/implementation-plan.md) §7 IN-PRD-05 |
| **Project Tasks — PR-PRD-01 (Data Model & API)** | `PlanTask.assignee_type` is extended from `Literal["agent", "human"]` to `Literal["agent", "human", "data_pipeline"]` + a sibling `pipeline_spec: PipelineJobSpec \| None` field. DAG validator unchanged. | [`../project-tasks/README.md`](../project-tasks/README.md), [PR-PRD-01](../project-tasks/projects/PR-PRD-01-data-model-and-api.md) |
| **Project Tasks — PR-PRD-03 (Calendar Page Frontend)** | `ProjectEditDrawer` gains a "Data Pipeline" assignee option; `ActivityDetailPanel` embeds `PipelineRunPanel` for run inspection. | [PR-PRD-03](../project-tasks/projects/PR-PRD-03-calendar-page-frontend.md) |
| **Project Tasks — PR-PRD-04 (Event-Driven Orchestrator)** | `TaskOrchestrator` gains a `data_pipeline` branch in `on_task_due` + `on_task_status_change`. Revision loop is **disabled** for pipeline tasks (deterministic output — nothing to revise). | [PR-PRD-04](../project-tasks/projects/PR-PRD-04-event-driven-orchestrator.md) |
| **Automations — A-PRD-02 (Recurring Scheduler & Run Engine)** | `{inputs.*}` substitution applied to `pipeline_spec.inputs` the same way it applies to agent prompts. SAR-E daily ingestion rides on this scheduler. | [`../automations/README.md`](../automations/README.md), [A-PRD-02](../automations/projects/A-PRD-02-recurring-scheduler.md) |
| **Automations — A-PRD-03 (Task Artifact System)** | Pipeline output is written through `attach_task_artifact()` into `gs://kene-task-artifacts-{env}/…` with 30-day lifecycle + 100 MB cap; no parallel storage path. | [A-PRD-03](../automations/projects/A-PRD-03-task-artifact-system.md) |
| **Automations — A-PRD-04 (Test / Dry-Run Mode)** | `TaskOrchestrator` exposes `is_test` per run; the dispatcher forwards it and the service honors each job's `test_mode_policy` (`run_normally` default / `sandbox_endpoint` / `fail_not_testable`). | [A-PRD-04](../automations/projects/A-PRD-04-test-dry-run-mode.md) |
| **UI — UI-PRD-01 (Design System)** | Soft Maximalism tokens, shadcn primitives, form primitives for the JSON-Schema renderer and guided schema builder. | [UI-PRD-01](../ui/projects/UI-PRD-01-design-system-foundation.md) |
| **Automations — A-PRD-06 (Automation Details Page)** | Publishes the **shared `frontend/src/components/dag/TaskGraph.tsx`** + the right-side task panel that DP-PRD-04 plugs into via its `PipelineJobPicker` + `CustomJobAuthoringPanel`. Same panel is reused by DB-PRD-03 (Dashboards details). No standalone Workflows tab for data pipelines. | [A-PRD-06](../automations/projects/A-PRD-06-automation-details-page.md) |
| **UI — UI-PRD-03 (Workflows Shell + Tabs)** | The Automations tab on `/workflows` hosts the DAG editor surface where data-pipeline tasks are created (via A-PRD-06's details page). UI-PRD-03 itself does **not** introduce a Data Pipelines tab — three tabs only (Agents / Automations / Skills). | [UI-PRD-03](../ui/projects/UI-PRD-03-workflows-shell.md) |
| **Agentic Harness — AH-PRD-03 (GA Specialist)** | *Soft* — the specialist reasons, the pipeline extracts. They share no code. The GA Data API client is used independently by each (pipeline via the official Python client, not MCP). | [AH-PRD-03](../agentic-harness/projects/AH-PRD-03-google-analytics-specialist.md) |
| External | `google-analytics-data` (GA Data API v1 client), `google-ads` Python SDK, `facebook-business` SDK (Meta), `mailchimp-marketing`, `pyarrow` + `pandas` (Parquet serialization), `jsonschema` (meta-validation of `input_schema`/`output_schema` on write). | — |

### 3.2 Depended On By

| Component | Dependency |
|-----------|------------|
| **SAR-E (SE-PRD-02 — Weekly KPI ingestion)** | Hard dependency. The four daily GA jobs seeded by DP-PRD-02 produce the `[{date, value}]` time-series rows that feed SAR-E's VAR model. The daily `is_system` automation runs 4 pipeline tasks + 1 `sar-e.ingest` agent task. Stable output schema across runs is a contract. |
| **Performance (PE-PRD-07 — Diagnostics tab)** | Reads ingestion-health signals from `accounts/{account_id}/data_pipeline_runs/*` (per-KPI last-success timestamp, gap counts, failed-job surfacing). Read-only — no write coupling. |
| **Dashboards (future)** | Pipeline `TaskArtifact`s are pinnable onto dashboard canvases through A-PRD-03's shared artifact surface — no changes needed to Dashboards to support it. |
| **Knowledge Graph (future)** | Pipeline artifacts are natural inputs for dated `Observation` ingestion (KG-PRD-02). Out of scope for v1; noted to inform artifact-schema decisions. |
| **Agentic Harness — Future narrow specialists (AH-PRD-05+)** | A specialist and a connector for the same platform can ship in either order. They share no code, only the platform's OAuth connection (owned by Integrations). |

## 4. Design System References

Applies to DP-PRD-04 only (the rest of the component is backend).

| Document | Sections | When to Read |
|----------|----------|--------------|
| Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) | Shared DAG editor (A-PRD-06), `ProjectEditDrawer` assignee extension, `ActivityDetailPanel` run viewer, inline `<PipelineJobPicker>` + `<CustomJobAuthoringPanel>` in the task side-panel | Before starting DP-PRD-04 UI work. |
| `frontend/CLAUDE.md` | CSS architecture, branded types, form primitives | Before adding any frontend component. |
| [`../ui/README.md`](../ui/README.md) | §2 Architecture, §7 Conventions | Shell + scope-boundary patterns — data pipelines are a `PlanTask.assignee_type` value created from the shared DAG editor's side-panel; no standalone `/workflows/data-pipelines` route. |
| [`../project-tasks/README.md`](../project-tasks/README.md) §2.4 | `ProjectEditDrawer`, `ActivityDetailPanel` | DP-PRD-04 extends these two components additively — read their contracts before modifying. |
| [`../automations/README.md`](../automations/README.md) §2.4 | `AutomationTaskPanel` + output rendering | Reference pattern for how pipeline runs surface inside a task detail view. |

## 5. Project Index

The component's work is split across **6 independently shippable project PRDs** under [`projects/`](./projects/). DP-PRD-01 is the foundation; DP-PRD-02 proves the connector framework on GA; DP-PRD-03 wires it into the task system; DP-PRD-04 delivers the UI surface; DP-PRD-05 adds the remaining three connectors; DP-PRD-06 closes out with end-to-end coverage and a verification report.

### 5.1 Dependency graph

```
  Upstream:
  ────────────────────────────────────────────────────────────
  DM-PRD-00 ──────────────────────────────┐
                                          │
  IN-PRD-02 (Google OAuth + credentials) ─┤
                                          ▼
                                    ┌────────────────┐
                                    │   DP-PRD-01    │  Foundation (models + service + cache)
                                    └──┬─────────────┘
                                       │
                                       ▼
                                    ┌────────────────┐
                                    │   DP-PRD-02    │  Google Analytics connector + 8-job catalog
                                    └──┬────┬────────┘
                          ┌────────────┘    │
                          ▼                 │
  PR-PRD-04 ──┐                             │       ┌──────────────────────┐
  A-PRD-03  ──┤                             │       │   SE-PRD-02          │
  A-PRD-04  ──┼───────►   DP-PRD-03         │       │   (SAR-E ingestion)  │
              ▼           Task-system       │       └──────────────────────┘
         ┌────────────┐   integration       │
         │ DP-PRD-03  │◀────────────────────┤
         └──┬─────────┘                     │
            │                               │
            ▼                               ▼
  IN-PRD-03 ─────►   DP-PRD-04       DP-PRD-05 ◀── IN-PRD-04
                     Frontend +       Additional
                     custom jobs      connectors
                          │               │
                          └───────┬───────┘
                                  ▼
                            ┌────────────┐
                            │ DP-PRD-06  │  Integration testing + polish
                            └────────────┘
```

### 5.2 Projects

| # | Project PRD | Owner team | Blocked by | Parallel with | Est. |
|---|-------------|------------|------------|---------------|------|
| 01 | [Foundation](./projects/DP-PRD-01-foundation.md) | Backend (foundation) | DM-PRD-00 | — | 3–4 days |
| 02 | [Google Analytics Connector](./projects/DP-PRD-02-google-analytics-connector.md) | Backend | DP-PRD-01, IN-PRD-02 | — | 4–5 days |
| 03 | [Task-system Integration](./projects/DP-PRD-03-task-system-integration.md) | Backend | DP-PRD-02, PR-PRD-04, A-PRD-03, A-PRD-04 | 05 | 3–4 days |
| 04 | [Frontend + Custom-job Authoring](./projects/DP-PRD-04-frontend-and-custom-jobs.md) | Frontend | DP-PRD-03, IN-PRD-03 | — | 5–6 days |
| 05 | [Additional Connectors](./projects/DP-PRD-05-additional-connectors.md) | Backend | DP-PRD-02, IN-PRD-04 | 03 / 04 | 7–9 days |
| 06 | [Integration Testing & Polish](./projects/DP-PRD-06-integration-testing.md) | QA + first-finished team | DP-PRDs 01–04 (05 optional) | — | 2 days |

### 5.3 Cross-PRD coordination points

Three touchpoints don't fit cleanly inside one PRD:

- **`PlanTask.assignee_type` extension (DP-PRD-03 ↔ PR-PRD-01):** literal union widens from `"agent" | "human"` to `"agent" | "human" | "data_pipeline"`, and `pipeline_spec` is added as an optional sibling field. Additive; existing PR-PRD-01 callers unchanged. PR-PRD-01 owners review the PR.
- **`TaskOrchestrator` dispatch branch (DP-PRD-03 ↔ PR-PRD-04):** adds a `data_pipeline` arm to `on_task_due` + `on_task_status_change` that delegates to `DataPipelineDispatcher`. The revision loop is intentionally skipped for this arm. PR-PRD-04 owners review.
- **`ProjectEditDrawer` assignee extension (DP-PRD-04 ↔ PR-PRD-03):** adds a "Data Pipeline" option in the assignee selector; when chosen, the form body swaps in `PipelineJobPicker` + `SchemaDrivenInputForm` instead of the agent/human fields. Additive; existing agent/human paths unchanged. PR-PRD-03 owners review.

### 5.4 Recommended workflow

1. **Prerequisite sprint(s):** DM-PRD-00 + IN-PRD-02 merge. Optionally PR-PRD-04 + A-PRD-03 + A-PRD-04 merge in parallel — DP-PRD-03 consumes them but DP-PRD-01/02 do not.
2. **Sprint 1 (foundation):** Backend ships DP-PRD-01. Frontend teams stub against the published Pydantic models.
3. **Sprint 2 (connector + task system):** DP-PRD-02 ships. As soon as PR-PRD-04 + A-PRD-03 + A-PRD-04 are all green, DP-PRD-03 starts.
4. **Sprint 3 (parallel expansion):** DP-PRD-04 (frontend) and DP-PRD-05 (Meta / Google Ads / Mailchimp) run in parallel once DP-PRD-03 + IN-PRD-03 + IN-PRD-04 are ready.
5. **Sprint 4 (close-out):** DP-PRD-06 runs the E2E suite (pipeline task → artifact → downstream agent task → review loop), the SAR-E daily-ingestion smoke test, the per-connector load tests, and appends the verification report to this README.

## 6. Global Document References

| Document | Relevant Sections | Why |
|----------|-------------------|-----|
| [`./implementation-plan.md`](./implementation-plan.md) | All sections | Architectural overview, phasing rationale, connector roadmap, SAR-E integration story. Read first if you're new to the component. |
| `docs/KEN-E-System-Architecture.md` | §1.6 Component Landscape, §8 Multi-Step Orchestration, §10 Infrastructure | Cross-component placement of Data Pipeline; how the sibling Cloud Run service fits the overall deployment story. |
| [`../project-tasks/README.md`](../project-tasks/README.md) | §2 Architecture, §2.3 API Contracts | `PlanTask` + orchestrator contract being extended — required reading before DP-PRD-03. |
| [`../automations/README.md`](../automations/README.md) | §2 Architecture, §5 Project Index | Artifact storage + `{inputs.*}` substitution patterns consumed here. |
| [`../integrations/implementation-plan.md`](../integrations/implementation-plan.md) | §3.1 `PlatformConnection`, §4 credentials endpoint, §7 IN-PRD-02/03/04/05 | Every connector's credential contract + re-auth signaling. |
| [`../sar-e/implementation-plan.md`](../sar-e/implementation-plan.md) | §3.1 Weekly KPIs, §5 Ingestion pipeline | Shape and cadence of the first production consumer. Read when modifying DP-PRD-02's four SAR-E daily jobs. |
| [`../agentic-harness/README.md`](../agentic-harness/README.md) | §2 Architecture, §3 (GA Specialist) | Complementary reasoning path — understand why the pipeline exists alongside AH-PRD-03. |
| [`../../DESIGN-REVIEW-LOG.md`](../../DESIGN-REVIEW-LOG.md) | 2026-04-23 entry (Data Pipeline promoted from backlog) | Rationale for promoting Data Pipeline from the backlog and for the sibling-service deployment choice. |

## 7. Conventions and Constraints

### Data model

- **Jobs are declarative recipes, not code.** `DataPipelineJob.input_schema` / `output_schema` are JSON Schemas meta-validated on write (`jsonschema.validators.Draft202012Validator.check_schema`). User-authored Python belongs in the **Skills** component, not here.
- **`job_id` format:** `^[a-z0-9_]+\.[a-z0-9_]+$` — `namespace.operation`. Examples: `ga.transactions_by_date`, `gads.campaign_performance_daily`. Enforce at save-time.
- **Versioning is monotonic, per-job.** `PUT` bumps `version`; old versions are not retained in v1 (cache invalidation happens because the version is part of the cache key). BigQuery external tables are version-suffixed.
- **Shape B only.** Three collections: `data_pipeline_jobs/{job_id}` (global carve-out, mirrors `agent_configs/*`), `accounts/{account_id}/data_pipeline_jobs/{job_id}` (per-account overlay + custom jobs, soft-delete via `is_active=false`), `accounts/{account_id}/data_pipeline_runs/{run_id}` (execution history).
- **Catalog resolution:** lookups fall back `account overlay → global`. Account-custom jobs cannot reuse a global `job_id` namespace (server enforces).

### Execution

- **Sibling Cloud Run service** (`kene-data-pipeline-{env}`) — isolated from request-path latency budgets, independent scaling. Never invoked from the main API's request path; always via the internal OIDC-authed `POST /api/v1/internal/data-pipeline/run`.
- **Fire-and-forget dispatch with PATCH-back.** The orchestrator does not block on connector execution. The sibling service reports completion via `POST /api/v1/internal/data-pipeline/callback` — handler must be **idempotent by `run_id`**.
- **Cache key:** `sha256(account_id \|\| job_id \|\| canonical_json(inputs) \|\| job.version)`. **Per-account only** — global caching would leak timing signals across accounts. Cache hits still write a `DataPipelineRun` with `status=cached` for audit completeness.
- **Artifact format:** Parquet default (columnar, typed, ~10× smaller than JSON for tabular data). Jobs emitting non-tabular output set `output_format="json"`. Jobs that declare `bigquery_external_table` trigger creation/refresh of a BigQuery external table over the Parquet artifact — SQL access without duplicating storage.
- **One connector per job.** Cross-platform joins happen in a downstream agent task, not inside the pipeline job.
- **Run cap:** 10 minutes per run. Exceeded runs are marked `failed` with `error_class="timeout"` and the task fails (no auto-retry on timeout).

### Credentials

- **Via Integrations only.** Connectors read credentials exclusively through `GET /api/v1/internal/integrations/credentials/{account_id}/{platform_id}` (OIDC). Never read `accounts/{account_id}/platform_connections/*` directly. Unit tests for each connector must assert this invariant (grep-style check on connector module imports).
- **Auth error → Integrations re-auth.** On 401/403 from the platform API, the connector calls `POST /internal/integrations/connections/{id}/mark-expired` and fails the task; downstream tasks halt until the user reconnects.

### Rate limits (v1 starting points — tuned via DP-PRD-06 telemetry)

| Connector | Per day | Per hour | Concurrent |
|---|---|---|---|
| `google_analytics` | 100 | 20 | 5 |
| `google_ads` | 50 | 10 | 3 |
| `meta_ads` | 50 | 10 | 3 |
| `mailchimp` | 20 | 5 | 2 |

Breach returns HTTP `429` with `Retry-After`. Three breaches within a 24-hour window triggers an account-level notification (`"Data Pipeline Rate Limit"` category).

### Error handling

- **Transient** (network, 5xx, platform 429): exponential-backoff retry ×3 inside the connector.
- **Semantic 4xx**: fail the task, surface the API response in a notification, hold the plan. **No agent-driven recovery in v1** — [`../backlog/pipeline-error-recovery-specialist.md`](../backlog/pipeline-error-recovery-specialist.md) tracks the future enhancement.
- **Auth 401/403**: Integrations re-auth flow.
- **Revision loop is disabled for pipeline tasks.** Deterministic output — nothing to revise. Do not wire the review-loop pattern (AH-PRD-01) into the `data_pipeline` dispatch branch.

### Test-mode

- **Default `test_mode_policy="run_normally"`.** Pipeline tasks produce real data under `is_test=true` so downstream analysis agents in a test plan can validate against real upstream. Side-effect suppression happens at *side-effecting* tasks (email send, ad spend), not at extraction tasks.
- **Opt-in alternatives** for future write-capable jobs: `"sandbox_endpoint"` (platform provides one), `"fail_not_testable"` (cannot run safely in test mode).

### API surface

- Public endpoints under `/api/v1/data-pipeline/*`. Internal RPC under `/api/v1/internal/data-pipeline/*` (both `/run` on the sibling service and `/callback` on the main API).
- Plan edits, run triggers, and schedule config flow through **Project Tasks** and **Automations** endpoints. Do not duplicate those surfaces here.
- `POST /api/v1/data-pipeline/jobs/preview` (DP-PRD-04) is synchronous and capped at 30 seconds; does **not** write `DataPipelineRun` or `TaskArtifact` and does **not** count against the cache.

### Security / Audit

- Every mutating endpoint uses DM-PRD-07's `require_role` (`editor` for `POST/PUT/DELETE /jobs`; `viewer` for reads) and writes via `write_audit`.
- Cross-account isolation is enforced at the router layer: an editor on account A cannot target `accounts/{B}/data_pipeline_jobs/*` — unit tests assert 404 on cross-account reads/writes.
- OIDC service accounts are separate for main-API → sibling-service calls and sibling-service → Integrations calls; audited in IAM.

### Observability

- Every run emits a `data_pipeline.run` Weave span with `{connector, operation, input_hash, row_count, cache_hit, test_mode}`. Preview runs (DP-PRD-04) emit a distinct `data_pipeline.preview` span so production dashboards are not polluted.
- DP-PRD-06 ships the observability dashboard: run volume, cache-hit rate, failure rate, per-connector p95 duration.

### Frontend (DP-PRD-04 only)

- Branded types (`DataPipelineJobId`) per CLAUDE.md C-5.
- **No standalone routes** — data pipelines are surfaced inline:
  - **Side-panel** (canonical): `<PipelineJobPicker>` + `<CustomJobAuthoringPanel>` mounted in A-PRD-06's task-creation right-side panel (the panel that opens from the shared DAG editor's "+ Add Task" button on `/workflows/automations/{plan_id}` and `/performance/dashboards/{plan_id}`).
  - Calendar's `ProjectEditDrawer` (PR-PRD-03) also surfaces the same `assignee_type="data_pipeline"` option for adding pipeline tasks to free-form plans.
- Global catalog jobs are read-only from the UI. Custom-job CRUD is editor-gated. Authoring is a 4-step inline stepper inside the side-panel (Basics → Schemas → Connection → Preview → Publish & Use).
- Pipeline-run polling inside `ActivityDetailPanel`: 2 s while `status="running"`, 30 s stale once terminal.

### Testing

- Unit tests for every connector use a mocked platform client + stub credentials service — never a live API in unit tests.
- Integration tests that hit live APIs are gated with `@pytest.mark.platform` and require live OAuth connections in a dedicated test account.
- T-4 separation enforced: `api/tests/data_pipeline/unit/` (pure logic) vs `api/tests/data_pipeline/integration/` (DB + sibling service).
- DP-PRD-06 Playwright suites cover the end-to-end path (pipeline task → artifact → downstream agent task → review loop) and the SAR-E recurring-automation smoke.
- Perf gates in CI: SAR-E daily-ingestion end-to-end < 120 s; cache-hit rate on stable-input recurring tasks ≥ 95 %; Weave-span emission at 100 %; 10 k-row GA pull p95 < 30 s.

### Standard shape for a project PRD in [`projects/`](./projects/)

Each PRD follows the same 10-section structure as every other component:

1. Context
2. Scope (in / out)
3. Dependencies
4. Data contract
5. Implementation outline
6. API contract
7. Acceptance criteria
8. Test plan
9. Risks & open questions
10. Reference

---

<!-- PRD MAINTENANCE NOTES

Updating this PRD:
- When a new feature-parent is created in Linear: add it to §5 Project Index
- When a feature-parent is completed: update its status in §5
- When architecture changes (new directories, new abstractions, new API endpoints): update §2
- When a new cross-component dependency is introduced: update §3
- When a new Figma spec or design doc section becomes relevant: update §4
- DP-PRD-06 will append a "Shipped on YYYY-MM-DD — Verification Report" section below once the full component ships.

This PRD is read by the Dev Team agent during implementation planning (CLAUDE.md §Context Loading Sequence, Step 1). Keep it concise — every sentence should help the agent write better code or avoid mistakes.

-->
