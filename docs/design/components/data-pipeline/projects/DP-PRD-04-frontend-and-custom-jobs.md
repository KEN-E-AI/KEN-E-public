# DP-PRD-04 — Frontend + Custom-Job Authoring

**Status:** Blocked — resumes once DP-PRD-03 and IN-PRD-03 ship
**Owner team:** Frontend (Data Pipeline) — with one backend line for the `POST /api/v1/data-pipeline/jobs` custom-job authoring endpoint already scoped in plan §4 but hardened here
**Blocked by:** DP-PRD-03 (task-system integration: `PlanTask.assignee_type="data_pipeline"`, `pipeline_spec`, `TaskOrchestrator.data_pipeline` branch, artifact write via A-PRD-03); IN-PRD-03 (connection-management UI — custom-job authoring needs the connection picker)
**Blocks:** DP-PRD-06 (integration testing depends on a working end-to-end UI flow)
**Estimated effort:** 5–6 days

---

## 1. Context

DP-PRD-01 through DP-PRD-03 deliver the service, the Google Analytics connector, the seeded catalog, and the orchestrator branch that dispatches pipeline tasks end-to-end. Every one of those flows is API-only today — a user can only author a pipeline task by hand-constructing a `pipeline_spec` payload and PATCHing it onto a `PlanTask`. That is good enough for SAR-E's `is_system` ingestion plan (seeded programmatically) but not for the R5 narrow-specialist cohort, where a marketing manager needs to point-and-click their way from "I want daily GA transaction pulls" to a scheduled automation.

This PRD ships the UI surface that closes that gap. Three facts shape the design:

1. **The Calendar page is the entry point.** `ProjectEditDrawer` (PR-PRD-03) gains a third assignee option — **"Data Pipeline"** — that swaps the agent / human fields for a **`PipelineJobPicker`** + a schema-driven **input form** rendered from the selected job's `input_schema`. `ActivityDetailPanel` (PR-PRD-03) gains a **pipeline-run viewer** that renders status, inputs, artifact preview, and a Weave span deep-link.
2. **Custom jobs are a per-account authoring flow, not a code-drop.** A new route `/workflows/data-pipelines` lists global (`data_pipeline_jobs/*`) + per-account (`accounts/{account_id}/data_pipeline_jobs/*`) jobs. An `editor`-role user can author a custom job from scratch using a **guided schema builder** for `input_schema` / `output_schema`, a connector picker sourced from IN-PRD-03's connection list, and a **preview run** against sample inputs before publishing. Platform-global jobs remain read-only from the UI — changes to them land through migrations.
3. **Custom code still lives in Skills.** The authoring UI does not accept Python. It composes a declarative `DataPipelineJob` document that the existing connectors know how to execute. This is the plan §9 non-goal — "user-authored Python" — reinforced at the UI layer.

The exit test: a user with no prior Data Pipeline experience composes, activates, and reviews a pipeline task end-to-end from the UI without ever touching an API client; and an editor-role user authors a custom per-account job from scratch, saves it, and invokes it inside a plan in the same session.

## 2. Scope

### In scope

- **`ProjectEditDrawer` — "Data Pipeline" assignee option.** Adds `"data_pipeline"` to the `assignee_type` selector (alongside `"agent"`, `"human"`). When chosen, renders the `<PipelineJobPicker>` + schema-driven `<PipelineInputsForm>` in place of the agent-prompt / human-assignee fields.
- **`<PipelineJobPicker>` component.** Browses global `data_pipeline_jobs/*` + per-account overlay from `GET /api/v1/data-pipeline/jobs`. Filterable by connector. Renders each job's `display_name`, `description`, and a connector badge. Search by `display_name` + `job_id` substring match.
- **`<PipelineInputsForm>` component.** JSON Schema → React form primitives. Inline validation against the job's declared `input_schema`. Primitive support: `string`, `integer`, `number`, `boolean`, `date`, `enum`, `array<primitive>`, single-level nested `object`. No `$ref` / `oneOf` / `allOf` / `anyOf` in v1 — deferred.
- **Pipeline-run viewer inside `<ActivityDetailPanel>`.** For a task with `assignee_type="data_pipeline"`, replaces the "completion notes" / "revision comment" panels with a `<PipelineRunPanel>` showing: status chip (`running` / `succeeded` / `failed` / `cached`), inputs table (resolved after `{inputs.*}` substitution per A-PRD-02), artifact preview (first N rows for Parquet / JSON; N = 25 by default), cache-hit indicator with the input-hash shown, per-run `started_at` / `finished_at` / `error_message`, and a "View Weave span" deep-link.
- **Artifact preview endpoint hand-off.** Uses the existing A-PRD-03 `GET /api/v1/artifacts/{artifact_id}/preview` (already rendered by Activity detail in PR-PRD-03). This PRD adds a thin preview-shape consumer for Parquet / JSON; CSV preview falls back to the default A-PRD-03 renderer.
- **Custom-job catalog + authoring UI** at three routes under `/workflows/data-pipelines`:
  - `/workflows/data-pipelines` — list of global + per-account jobs with a "New Job" CTA (editor role+). Platform-global jobs are flagged `system` and open read-only; per-account jobs open in the editor.
  - `/workflows/data-pipelines/new` — authoring form.
  - `/workflows/data-pipelines/:job_id` — view / edit. Read-only for `data_pipeline_jobs/*` (global); editable for `accounts/{account_id}/data_pipeline_jobs/*`.
- **Guided `input_schema` / `output_schema` builder.** Form-based UI for adding fields with name / type / required / default / description / `enum`-values. Emits a valid JSON Schema document. The builder validates on submit via the backend's JSON-Schema meta-validator (plan §4, `POST /api/v1/data-pipeline/jobs`).
- **Connection picker inside authoring.** Sources the list from IN-PRD-03's `GET /api/v1/integrations/{account_id}/connections` scoped to the connector the user selected. An authoring session can only pick an operation for a connector the account has a `connected` `PlatformConnection` for.
- **Preview run.** Authoring page exposes a "Preview" button that POSTs the draft job + sample inputs to `POST /api/v1/data-pipeline/jobs/preview` (new endpoint scoped here — invokes the chosen connector end-to-end against live credentials, does **not** persist a `DataPipelineRun`). Displays the resulting row count + a first-N-row preview inline. Dry-run only; no artifact written.
- **Feature-flag gates** on both the authoring UI and the assignee option — see §5.4.
- **TypeScript mirrors** of every Pydantic shape in `frontend/src/types/dataPipeline.ts` (branded IDs per C-5; `import type` per C-6; `type` over `interface` per C-8).
- **Unit tests** per component + hook + form primitive; **Playwright specs** covering (a) the Calendar end-to-end flow and (b) the authoring → preview → publish → invoke flow.

### Out of scope

- **Editing global platform jobs from the UI.** Read-only view only. Changes land via migrations + a CODEOWNER-gated PR.
- **Python code in authored jobs.** Custom code remains in Skills (plan §9 non-goal).
- **Sharing a custom job across accounts.** Out of scope per plan §10 "Custom-job sharing across accounts" — an account authors jobs for itself only.
- **JSON Schema `$ref` / `oneOf` / `allOf` / `anyOf`.** Deferred; v1 supports only the primitive + single-level-object subset listed above.
- **Dashboard widget composition of pipeline artifacts.** Artifact surfacing in Dashboards lands in a later Dashboards PRD; this PRD ends at the run viewer + preview.
- **Retry / revise controls in the run viewer.** Pipeline tasks are excluded from the review loop (DP-PRD-03); the panel is read-only. Failures re-run by re-firing the parent task via the standard PR-PRD-04 controls.
- **Scheduled-run preview / test-mode toggle in authoring.** Test-mode policy is captured as the `test_mode_policy` field on `DataPipelineJob` per plan §3.1 — the value is set here but not re-exercised by a separate test-mode preview button.
- **Bulk import of job definitions** (e.g., YAML upload). One-at-a-time authoring only in v1.

## 3. Dependencies

- **DP-PRD-03 (Task-system integration):** `PlanTask.assignee_type="data_pipeline"`, `PipelineJobSpec`, `TaskOrchestrator` dispatch branch, `TaskArtifact` write on completion, and the pipeline-run read endpoints. This PRD composes that surface.
- **IN-PRD-03 (Connection-management UI):** the connection picker in the authoring UI reads `GET /api/v1/integrations/{account_id}/connections`. If the account has zero connections for the chosen connector, the UI deep-links to `/settings/integrations` with a return URL.
- **PR-PRD-03 (Calendar page):** hosts `ProjectEditDrawer` + `ActivityDetailPanel`. This PRD extends both; shape contract defined in PR-PRD-03 §5.
- **A-PRD-03 (Task Artifact System):** provides `GET /api/v1/artifacts/{artifact_id}/preview` + the artifact render primitives. This PRD consumes them.
- **A-PRD-02 (Recurring Scheduler):** provides the `{inputs.*}` substitution used in the resolved-inputs view of the run viewer. Contract consumed, not modified.
- **DM-PRD-07 (Approval & Audit):** role table gates the authoring endpoints. Viewing the catalog is any authenticated role; authoring / deleting requires `editor` or higher.
- **FF-PRD-03 (Feature-flag hook):** `useFeatureFlag('data_pipeline_task_assignee')` gates the assignee option; `useFeatureFlag('data_pipeline_custom_jobs')` gates the authoring UI.
- **UI-PRD-01 (Soft Maximalism):** design tokens, shadcn primitives, Stepper pattern for authoring, Drawer pattern for the run viewer. No new primitives.
- **Existing files to study:**
  - `/Volumes/WorkDrive/Active Work/Github/KEN-E/docs/design/components/project-tasks/projects/PR-PRD-03-calendar-page-frontend.md` — `ProjectEditDrawer` + `ActivityDetailPanel` shape
  - `/Volumes/WorkDrive/Active Work/Github/KEN-E/docs/design/components/integrations/implementation-plan.md` §6 IN-PRD-03 — connection-picker contract
  - `/Volumes/WorkDrive/Active Work/Github/KEN-E/frontend/src/pages/` — existing page conventions (no `Workflows/` directory exists yet; this PRD creates it)
  - `/Volumes/WorkDrive/Active Work/Github/KEN-E/frontend/src/lib/api.ts` — axios client with Firebase token injection
  - `/Volumes/WorkDrive/Active Work/Github/KEN-E/frontend/src/App.tsx` — routing registration
  - `/Volumes/WorkDrive/Active Work/Github/KEN-E/api/src/kene_api/routers/integrations.py` — pattern for new router module

## 4. Data contract

This PRD introduces one new backend endpoint (`POST /api/v1/data-pipeline/jobs/preview`) and adds TypeScript mirrors for the existing Pydantic shapes in plan §3.1. Everything else is consumed as-is.

### 4.1 TypeScript mirrors

```ts
// frontend/src/types/dataPipeline.ts
import type { Brand } from '@/types/brand';

export type AccountId = Brand<string, 'AccountId'>;
export type JobId = Brand<string, 'JobId'>;
export type RunId = Brand<string, 'RunId'>;
export type ArtifactId = Brand<string, 'ArtifactId'>;

export type Connector = 'google_analytics' | 'google_ads' | 'meta_ads' | 'mailchimp';
export type OutputFormat = 'parquet' | 'json' | 'csv';
export type TestModePolicy = 'run_normally' | 'sandbox_endpoint' | 'fail_not_testable';
export type RunStatus = 'running' | 'succeeded' | 'failed' | 'cached';
export type AssigneeType = 'agent' | 'human' | 'data_pipeline';

export type DataPipelineJob = {
  job_id: JobId;
  connector: Connector;
  operation: string;
  display_name: string;
  description: string;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  output_format: OutputFormat;
  bigquery_external_table: { dataset: string; table: string } | null;
  default_cache_ttl_seconds: number | null;
  test_mode_policy: TestModePolicy;
  visible_in_frontend: boolean;
  version: number;
  scope: 'global' | 'account';
  account_id?: AccountId;
};

export type PipelineJobSpec = {
  job_id: JobId;
  inputs: Record<string, unknown>;
  output_artifact_name: string;
};

export type DataPipelineRun = {
  run_id: RunId;
  account_id: AccountId;
  plan_id: string;
  task_id: string;
  job_id: JobId;
  inputs: Record<string, unknown>;
  input_hash: string;
  output_artifact_id: ArtifactId | null;
  status: RunStatus;
  cache_hit: boolean;
  started_at: string;
  finished_at: string | null;
  error_message: string | null;
  tokens_charged: number;
};
```

### 4.2 New endpoint — preview run

```python
# api/src/kene_api/models/data_pipeline_preview_models.py
class PipelinePreviewRequest(BaseModel):
    connector: Literal["google_analytics", "google_ads", "meta_ads", "mailchimp"]
    operation: str
    inputs: dict                           # validated against the draft input_schema
    input_schema: dict                     # JSON Schema — validated before the run fires
    sample_row_limit: int = 25             # capped at 100

class PipelinePreviewResponse(BaseModel):
    row_count: int
    rows: list[dict]                       # first N rows
    schema: list[FieldSpec]
    duration_ms: int
    # preview runs never persist a DataPipelineRun; no run_id is returned.
```

Semantics:

- Preview is **synchronous** (blocks the request for the duration of the connector call) and capped at 30 seconds.
- Requires `editor` role or higher per DM-PRD-07.
- Reads credentials via Integrations' `GET /api/v1/internal/integrations/credentials/{account_id}/{platform_id}` — same path the production dispatcher uses.
- Emits a `data_pipeline.preview` Weave span (distinct from the production `data_pipeline.run` span) so preview runs don't pollute run-volume dashboards.
- Does **not** write a `DataPipelineRun`, does **not** write a `TaskArtifact`, does **not** count against cache. The input-hash is computed and returned for diagnostic purposes only.
- Errors: 4xx with the connector's error message for semantic failures; 408 on timeout; 429 on rate-limit breach (shares the same per-account rate-limit bucket as the production connector — plan §3.3).

## 5. Implementation outline

| Action | File |
|--------|------|
| Modify | `frontend/src/components/ProjectEditDrawer.tsx` — add `"data_pipeline"` option to assignee selector; render `<PipelineJobPicker>` + `<PipelineInputsForm>` when selected; feature-flag gated by `data_pipeline_task_assignee` |
| Create | `frontend/src/components/dataPipeline/PipelineJobPicker.tsx` — searchable, filterable catalog list |
| Create | `frontend/src/components/dataPipeline/PipelineInputsForm.tsx` — JSON-Schema-driven form with inline validation |
| Create | `frontend/src/components/dataPipeline/PipelineRunPanel.tsx` — run viewer rendered inside `<ActivityDetailPanel>` |
| Create | `frontend/src/components/dataPipeline/PipelineArtifactPreview.tsx` — first-N-row table for Parquet / JSON |
| Modify | `frontend/src/components/ActivityDetailPanel.tsx` — swap completion / revision panels for `<PipelineRunPanel>` when `assignee_type="data_pipeline"` |
| Create | `frontend/src/pages/Workflows/DataPipelinesListPage.tsx` — `/workflows/data-pipelines` route body |
| Create | `frontend/src/pages/Workflows/DataPipelineAuthoringPage.tsx` — `/workflows/data-pipelines/new` + `/workflows/data-pipelines/:job_id` |
| Create | `frontend/src/components/dataPipeline/SchemaBuilder.tsx` — guided `input_schema` / `output_schema` composer |
| Create | `frontend/src/components/dataPipeline/ConnectorConnectionPicker.tsx` — IN-PRD-03 connection picker scoped to the chosen connector |
| Create | `frontend/src/components/dataPipeline/PipelinePreviewPanel.tsx` — "Preview" button + result display |
| Create | `frontend/src/hooks/useDataPipelineCatalog.ts` — TanStack Query hook for `GET /api/v1/data-pipeline/jobs` (global + overlay) |
| Create | `frontend/src/hooks/useDataPipelineJob.ts` — GET / PUT / DELETE for a single job |
| Create | `frontend/src/hooks/useDataPipelineRun.ts` — GET for a single run by `run_id` |
| Create | `frontend/src/hooks/usePipelineJobPreview.ts` — mutation hook for `POST /api/v1/data-pipeline/jobs/preview` |
| Create | `frontend/src/services/dataPipelineApi.ts` — axios wrappers (catalog + jobs + runs + preview) |
| Create | `frontend/src/types/dataPipeline.ts` — branded types + mirrors per §4.1 |
| Modify | `frontend/src/App.tsx` — register the three `/workflows/data-pipelines*` routes |
| Modify | `frontend/src/components/Sidebar.tsx` (or equivalent) — add a "Workflows" nav section with a "Data Pipelines" child; gated by `data_pipeline_custom_jobs` |
| Create | `api/src/kene_api/models/data_pipeline_preview_models.py` — Pydantic shapes per §4.2 |
| Create | `api/src/kene_api/routers/data_pipeline_preview.py` — `POST /api/v1/data-pipeline/jobs/preview` endpoint |
| Modify | `api/src/kene_api/main.py` — register the preview router |
| Create | `frontend/src/components/dataPipeline/__tests__/PipelineJobPicker.test.tsx` |
| Create | `frontend/src/components/dataPipeline/__tests__/PipelineInputsForm.test.tsx` |
| Create | `frontend/src/components/dataPipeline/__tests__/PipelineRunPanel.test.tsx` |
| Create | `frontend/src/components/dataPipeline/__tests__/SchemaBuilder.test.tsx` |
| Create | `frontend/src/components/dataPipeline/__tests__/PipelinePreviewPanel.test.tsx` |
| Create | `frontend/src/components/__tests__/ProjectEditDrawer.dataPipeline.test.tsx` — covers only the Data Pipeline branch |
| Create | `frontend/src/components/__tests__/ActivityDetailPanel.pipelineRun.test.tsx` — covers only the Data Pipeline branch |
| Create | `frontend/src/pages/Workflows/__tests__/DataPipelinesListPage.test.tsx` |
| Create | `frontend/src/pages/Workflows/__tests__/DataPipelineAuthoringPage.test.tsx` |
| Create | `frontend/src/hooks/__tests__/useDataPipelineCatalog.test.ts` |
| Create | `frontend/src/hooks/__tests__/usePipelineJobPreview.test.ts` |
| Create | `api/tests/integration/test_data_pipeline_preview_router.py` |
| Create | `frontend/e2e/data-pipeline-calendar-flow.spec.ts` — Playwright: compose + activate + review a pipeline task end-to-end |
| Create | `frontend/e2e/data-pipeline-custom-job-authoring.spec.ts` — Playwright: author + preview + publish + invoke |

### 5.1 `ProjectEditDrawer` extension

1. Extend the `assignee_type` radio with a third option `"Data Pipeline"`; gate visibility on `useFeatureFlag('data_pipeline_task_assignee')`.
2. On selection:
   - Hide `assignee_name`, `agent_prompt`, and any human-assignee fields.
   - Render `<PipelineJobPicker value={spec?.job_id} onChange={...} />` and, once a job is picked, `<PipelineInputsForm schema={job.input_schema} value={spec?.inputs ?? {}} onChange={...} />`.
   - Render an `output_artifact_name` text input (defaults to `{job.job_id}_output`).
3. On Save, construct `pipeline_spec: PipelineJobSpec` and PATCH the task through the existing PR-PRD-01 `PATCH /api/v1/plans/{plan_id}/tasks/{task_id}` endpoint with `assignee_type: "data_pipeline"` + `pipeline_spec`.
4. Validation: `job_id` required; every `input_schema.required` field must resolve to a non-null input value (or a `{inputs.*}` placeholder per A-PRD-02).

### 5.2 `ActivityDetailPanel` — pipeline-run viewer

1. Branch on `task.assignee_type === 'data_pipeline'`.
2. Use `useDataPipelineRun(task.task_id)` to fetch the latest run. If no run yet (task in `Draft` / `Awaiting Approval`), show a "This task has not run yet" empty state with the resolved inputs preview only.
3. Once run, render `<PipelineRunPanel>` with:
   - Status chip (`running` / `succeeded` / `failed` / `cached`) styled with the existing Soft Maximalism status palette.
   - Inputs table: two columns (name / value), rendered from `run.inputs` — shows the *resolved* values, not the `{inputs.*}` placeholders.
   - `<PipelineArtifactPreview artifactId={run.output_artifact_id}>` when `run.status in ('succeeded', 'cached')`.
   - Cache badge when `run.cache_hit=true` showing the `input_hash` (truncated to 8 chars) and a "Cache key: {hash}" tooltip.
   - Timing row: `started_at`, `finished_at`, duration.
   - Error panel when `run.status === 'failed'` with `error_message` rendered as monospace.
   - "View Weave span" link — pattern TODO at kickoff (Weave span URL template resolution not yet standardized component-wide).

### 5.3 Custom-job authoring

**List page** (`/workflows/data-pipelines`):
- Table: `display_name`, `connector` badge, `scope` (`global` / `account`), `version`, `updated_at`.
- Filter bar: connector multi-select, scope toggle (All / Global / Custom).
- "New Job" CTA — editor role gated; reads `usePermissions()`.
- Row click on a global job → read-only view at `/workflows/data-pipelines/:job_id`; per-account job → editor.

**Authoring page** (`/workflows/data-pipelines/new` and `:job_id` for account jobs):

Stepper with 4 steps (URL-addressable via `?step=basics|schemas|connection|preview`):

1. **Basics** — `display_name`, `description`, connector (dropdown), operation (free-text; v1 does not enumerate supported operations per connector — documented in §9 as an open question), `output_format`, `default_cache_ttl_seconds`, `test_mode_policy`, `visible_in_frontend`.
2. **Schemas** — `<SchemaBuilder>` for `input_schema`; separate `<SchemaBuilder>` for `output_schema`. Each emits a valid JSON Schema document. Validated client-side against a meta-validator bundled with the frontend; errors render inline.
3. **Connection** — `<ConnectorConnectionPicker>` filtered to the chosen connector. If no connection exists, shows a "Connect {connector} first" CTA that deep-links to `/settings/integrations?return_to=/workflows/data-pipelines/new`.
4. **Preview** — `<PipelinePreviewPanel>`: renders the declared `input_schema` via `<PipelineInputsForm>` with sample-value inputs, fires `usePipelineJobPreview()` on "Run Preview", renders the first N rows + row-count + duration. "Publish" button enabled only after a successful preview run.

**On Publish:**
- `POST /api/v1/data-pipeline/jobs` with the composed `DataPipelineJob` body.
- Backend re-validates (a) the job against `DataPipelineJob` and (b) the nested `input_schema` / `output_schema` against a JSON-Schema meta-validator (plan §4).
- On success, redirect to `/workflows/data-pipelines/{job_id}` with a success toast.

**Editing an existing per-account job:**
- Same stepper. `PUT /api/v1/data-pipeline/jobs/{job_id}` on Publish (new endpoint scoped here — plan §4 covers create only; update edition follows the same validation path; confirm at kickoff if missing).
- `version` auto-increments on publish.
- A warning banner fires if any active plan references the job — edits ship new runs with the new version but existing cached runs remain addressable by their `input_hash` + prior `version`.

### 5.4 Feature-flag gating

| Flag | Scope | Behavior when off |
|---|---|---|
| `data_pipeline_task_assignee` | `ProjectEditDrawer` assignee selector | "Data Pipeline" option hidden; existing pipeline tasks still render in `ActivityDetailPanel` (read-only) so we don't brick already-authored tasks. |
| `data_pipeline_custom_jobs` | Authoring UI + `/workflows/data-pipelines*` routes + sidebar entry | List page returns a 404-style "Not available" page; `/new` and `/:job_id` likewise; sidebar entry hidden. The global catalog is still browseable via the job-picker in `ProjectEditDrawer` (when that flag is on). |

Role gating from DM-PRD-07:

| Action | Minimum role |
|---|---|
| View `/workflows/data-pipelines` list | any authenticated |
| View a job detail (global or account) | any authenticated |
| Create a per-account job (`POST /jobs`) | editor |
| Update a per-account job (`PUT /jobs/{job_id}`) | editor |
| Delete a per-account job (`DELETE /jobs/{job_id}`) | editor (must be the owning account) |
| Run a preview (`POST /jobs/preview`) | editor |
| Select a pipeline job in `ProjectEditDrawer` | same role as task authoring today (per PR-PRD-03) |
| View a pipeline run | any authenticated with access to the parent plan |

## 6. API contract

### 6.1 Owned by this PRD

| Method | Path | Purpose | Role |
|---|---|---|---|
| `POST` | `/api/v1/data-pipeline/jobs/preview` | Preview a draft job's connector call against live credentials; returns `row_count` + first-N rows. Does **not** persist a `DataPipelineRun` or write an artifact. | editor |

### 6.2 Consumed (already owned by Data Pipeline + siblings)

| Method | Path | Purpose | Owner |
|---|---|---|---|
| `GET` | `/api/v1/data-pipeline/jobs` | List global + per-account catalog; `?connector=` filter | DP-PRD-01 |
| `GET` | `/api/v1/data-pipeline/jobs/{job_id}` | Job detail (incl. `input_schema`) | DP-PRD-01 |
| `POST` | `/api/v1/data-pipeline/jobs` | Create a per-account custom job | DP-PRD-01 (plan §4) |
| `PUT` | `/api/v1/data-pipeline/jobs/{job_id}` | Update a per-account custom job | **scoped here** — confirm with DP-PRD-01 owner at kickoff; if absent, add as a companion line in this PRD's API surface |
| `DELETE` | `/api/v1/data-pipeline/jobs/{job_id}` | Delete a per-account custom job | **scoped here** — same disposition as PUT |
| `GET` | `/api/v1/data-pipeline/{account_id}/runs` | List runs (filters: plan_id, task_id, job_id, status, date range) | DP-PRD-01 |
| `GET` | `/api/v1/data-pipeline/{account_id}/runs/{run_id}` | Run detail + artifact link | DP-PRD-01 |
| `GET` | `/api/v1/artifacts/{artifact_id}/preview` | First-N-row preview of a `TaskArtifact` | A-PRD-03 |
| `GET` | `/api/v1/integrations/{account_id}/connections` | Connection list, filtered client-side by connector | IN-PRD-03 |
| `PATCH` | `/api/v1/plans/{plan_id}/tasks/{task_id}` | Persist `assignee_type="data_pipeline"` + `pipeline_spec` on a task | PR-PRD-01 |

## 7. Acceptance criteria

1. Navigating to `/calendar`, opening a plan, and choosing the **Data Pipeline** assignee in `ProjectEditDrawer` renders `<PipelineJobPicker>`; the agent-prompt and human-assignee fields disappear from the DOM.
2. `<PipelineJobPicker>` renders the union of `data_pipeline_jobs/*` + `accounts/{account_id}/data_pipeline_jobs/*` returned by `GET /api/v1/data-pipeline/jobs`; the connector filter narrows the list correctly; search matches against `display_name` and `job_id`.
3. `<PipelineInputsForm>` renders one input control per property in the selected job's `input_schema`; required fields surface an inline error when empty on Save; enum fields render as a select; `date` fields render a date picker; `array<primitive>` fields render an add-row control.
4. On Save with a valid pipeline spec, the PATCH to `/api/v1/plans/{plan_id}/tasks/{task_id}` carries `assignee_type="data_pipeline"` + `pipeline_spec: { job_id, inputs, output_artifact_name }`.
5. For a task with `assignee_type="data_pipeline"` that has not yet run, `<ActivityDetailPanel>` renders `<PipelineRunPanel>` in its empty state ("This task has not run yet") with the resolved inputs preview.
6. For a task with a completed run, `<PipelineRunPanel>` renders the status chip, resolved inputs table, `<PipelineArtifactPreview>` with the first 25 rows, `started_at` / `finished_at` / duration, and a cache badge when `run.cache_hit=true` showing the truncated `input_hash`.
7. For a failed run, `<PipelineRunPanel>` renders the `error_message` in a monospace error block and hides the artifact-preview panel.
8. Feature-flag `data_pipeline_task_assignee=false` removes the "Data Pipeline" option from `ProjectEditDrawer`; already-authored pipeline tasks still render in `<ActivityDetailPanel>` (read-only).
9. Feature-flag `data_pipeline_custom_jobs=false` makes `/workflows/data-pipelines*` return a "Not available" page and hides the sidebar entry; the job-picker in `ProjectEditDrawer` is unaffected when `data_pipeline_task_assignee=true`.
10. The `/workflows/data-pipelines` list renders both global + per-account jobs with a `scope` badge; clicking a global job opens a read-only view; clicking a per-account job opens the editor for editor-role users and a read-only view for viewers.
11. The authoring stepper enforces step order: Schemas cannot be entered without a chosen connector on Basics; Preview cannot fire without a valid `input_schema` + an account connection to the chosen connector.
12. `<ConnectorConnectionPicker>` shows only `PlatformConnection`s for the chosen connector with `status="connected"`; when zero matches, the "Connect {connector} first" CTA deep-links to `/settings/integrations?return_to=/workflows/data-pipelines/new`.
13. "Run Preview" POSTs to `/api/v1/data-pipeline/jobs/preview` with `{connector, operation, inputs, input_schema, sample_row_limit: 25}`; on success renders the row count, first-N rows, and a `duration_ms` pill; on 429 renders a rate-limit warning with the `Retry-After` header value.
14. "Publish" is disabled until a successful preview run has completed in the current session; on click, POSTs to `/api/v1/data-pipeline/jobs` and redirects to the job-detail route on 2xx.
15. Role gating: a viewer-role user hitting `/workflows/data-pipelines/new` gets a 403 page; the same user hitting `POST /api/v1/data-pipeline/jobs` gets a 403 response.
16. Cross-account isolation: `GET /api/v1/data-pipeline/jobs` for account A does not return account B's custom jobs; an editor on account A cannot PUT or DELETE a job under `accounts/{B}/data_pipeline_jobs/*`.
17. Observability: every preview run emits a `data_pipeline.preview` Weave span with `{connector, operation, row_count, duration_ms}`; no preview creates a `DataPipelineRun` document.
18. `make lint`, `pytest api/tests/`, `npm run build`, `npm run typecheck`, `npm run format.fix`, `npm run lint` all green.

## 8. Test plan

**Unit tests — frontend components:**
- `PipelineJobPicker.test.tsx` — catalog rendering, filter by connector, search match logic, empty-state when `GET /jobs` returns `[]`.
- `PipelineInputsForm.test.tsx` — one assertion per primitive type; required-field validation; enum rendering; `array<primitive>` add / remove; invalid input blocks Save.
- `PipelineRunPanel.test.tsx` — empty-state branch, success branch (with artifact preview), failed branch, cached branch (input-hash shown), and a boundary test for `run.status="running"` (shows a spinner + resolved inputs only, no artifact preview).
- `SchemaBuilder.test.tsx` — emits a valid JSON Schema for each supported primitive; rejects unsupported shapes (`$ref`, `oneOf`) with an inline error; required-field toggle maps to the `required` array correctly.
- `PipelinePreviewPanel.test.tsx` — preview button disabled on invalid inputs; enabled after valid inputs + connection; wires through to the mutation hook; error cases surface correctly.

**Unit tests — pages:**
- `DataPipelinesListPage.test.tsx` — renders global + account rows with correct badges; "New Job" CTA gated on editor role; connector filter narrows.
- `DataPipelineAuthoringPage.test.tsx` — stepper state transitions; "Publish" gated on successful preview; POST payload shape on Publish.
- `ProjectEditDrawer.dataPipeline.test.tsx` — assignee option gated on `data_pipeline_task_assignee` flag; PATCH payload carries `pipeline_spec` on Save.
- `ActivityDetailPanel.pipelineRun.test.tsx` — branches correctly on `assignee_type`; renders `<PipelineRunPanel>` for pipeline tasks only.

**Unit tests — hooks:**
- `useDataPipelineCatalog.test.ts` — merges global + account lists; de-dupes by `job_id` with account overlay winning.
- `usePipelineJobPreview.test.ts` — mutation fires correct body; timeout handling; rate-limit handling.

**Integration tests — backend:**
- `test_data_pipeline_preview_router.py` — happy path with a `StubConnector` returning deterministic rows; 4xx on semantic connector errors; 408 on timeout; 429 on rate-limit breach; 403 for viewer role; 422 on malformed `input_schema`.

**Playwright — E2E:**
- `data-pipeline-calendar-flow.spec.ts` — seed an account with one connected Google integration and the seeded GA jobs. Navigate to `/calendar` → create a new plan → add a task → choose "Data Pipeline" assignee → pick `ga.sessions_by_date` → fill `target_date` → Save → activate the plan → verify the task fires → open `<ActivityDetailPanel>` → verify `<PipelineRunPanel>` renders the artifact preview.
- `data-pipeline-custom-job-authoring.spec.ts` — seed an editor-role user with one connected Google integration. Navigate to `/workflows/data-pipelines` → click "New Job" → step through Basics → Schemas → Connection → Preview with sample inputs → verify preview renders rows → click "Publish" → verify redirect to the detail route → navigate to `/calendar` → confirm the new job appears in `<PipelineJobPicker>` → author a task using it → verify the run completes.

## 9. Risks & open questions

### Resolved decisions

| Decision | Resolution |
|---|---|
| Calendar page integration | Extends `ProjectEditDrawer` + `ActivityDetailPanel` in place, not a sibling surface. |
| Custom-job authoring scope | Per-account only in v1; platform-global jobs read-only from UI. |
| Code in custom jobs | Declarative JSON Schema only; no Python. Code lives in Skills (plan §9). |
| Preview semantics | Synchronous, credentialed, no `DataPipelineRun` persisted, separate Weave span. |
| Feature-flag split | Two flags — `data_pipeline_task_assignee` (consumer-side) and `data_pipeline_custom_jobs` (authoring-side). Either can be off independently. |
| Role gating for authoring | `editor` minimum per DM-PRD-07. |
| Schema builder scope | Primitive subset in v1 (`string`, `integer`, `number`, `boolean`, `date`, `enum`, `array<primitive>`, single-level `object`). `$ref` / `oneOf` / `allOf` / `anyOf` deferred. |

### Remaining open questions

| Question | Disposition |
|---|---|
| PUT / DELETE for per-account jobs not explicit in plan §4 | Scoped here (§6); confirm with DP-PRD-01 owner at kickoff. If already in-scope for DP-PRD-01, remove from this PRD's API-surface section. |
| Operation field on authoring Basics step | Free-text in v1. Per-connector operation enums (drop-down with allowed operations) deferred until the catalog grows enough to be worth enumerating. TODO at kickoff to confirm. |
| Weave span URL template for the "View Weave span" link | Not yet standardized component-wide. Default: link to `{WEAVE_BASE_URL}/{project}/traces/{trace_id}` and resolve `WEAVE_BASE_URL` via env at build time. TODO: confirm with the observability team at kickoff. |
| Edit-warning banner text when a published job is in use by an active plan | Draft copy subject to product review. Confirm at kickoff. |
| Preview timeout handling on slow connectors | 30s cap surfaced here. If product wants async preview (poll-for-result), revisit post-v1. |
| Versioning UX on edit | `version` auto-increments; UI does not expose "pick a prior version" in v1. Historical run records still address by `version` + `input_hash`. Revisit if users need to pin a task to a specific version. |

## 10. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md) §7 DP-PRD-04
- Upstream: [DP-PRD-01 Foundation](./DP-PRD-01-foundation.md), [DP-PRD-02 Google Analytics connector](./DP-PRD-02-google-analytics-connector.md), [DP-PRD-03 Task-system integration](./DP-PRD-03-task-system-integration.md)
- Upstream: [IN-PRD-03 Connection-management UI](../../integrations/projects/IN-PRD-03-connection-management-ui.md)
- Sibling: [PR-PRD-03 Calendar page frontend](../../project-tasks/projects/PR-PRD-03-calendar-page-frontend.md) — hosts `ProjectEditDrawer` + `ActivityDetailPanel`
- Sibling: [PR-PRD-01 Project plan data model + API](../../project-tasks/projects/PR-PRD-01-data-model-and-api.md) — `PATCH /api/v1/plans/{plan_id}/tasks/{task_id}`
- Sibling: [A-PRD-02 Recurring scheduler](../../automations/projects/02-recurring-scheduler.md) — `{inputs.*}` substitution
- Sibling: [A-PRD-03 Task artifact system](../../automations/projects/03-task-artifact-system.md) — artifact preview endpoint
- Policy: [DM-PRD-07 Approval & audit](../../data-management/projects/DM-PRD-07-approval-workflow-and-audit.md) — role table
- Feature Flags: [FF-PRD-03 SDK hook](../../feature-flags/projects/FF-PRD-03-feature-flag-sdks.md) — `useFeatureFlag`
- Design tokens: [UI-PRD-01](../../ui/projects/UI-PRD-01-design-system-foundation.md)
- Code files expected to be touched:
  - `frontend/src/components/ProjectEditDrawer.tsx`
  - `frontend/src/components/ActivityDetailPanel.tsx`
  - `frontend/src/components/dataPipeline/*`
  - `frontend/src/pages/Workflows/DataPipelinesListPage.tsx`
  - `frontend/src/pages/Workflows/DataPipelineAuthoringPage.tsx`
  - `frontend/src/hooks/useDataPipelineCatalog.ts`, `useDataPipelineJob.ts`, `useDataPipelineRun.ts`, `usePipelineJobPreview.ts`
  - `frontend/src/services/dataPipelineApi.ts`
  - `frontend/src/types/dataPipeline.ts`
  - `frontend/src/App.tsx` (route registration)
  - `api/src/kene_api/models/data_pipeline_preview_models.py`
  - `api/src/kene_api/routers/data_pipeline_preview.py`
  - `api/src/kene_api/main.py` (router mount)
- CLAUDE.md rules in scope: C-1 (TDD), C-2 (domain vocabulary — `DataPipelineJob`, `DataPipelineRun`, `PipelineJobSpec`, `PipelineOutput`, `pipeline_spec`), C-5 (branded IDs — `AccountId`, `JobId`, `RunId`, `ArtifactId`), C-6 (`import type`), C-8 (`type` default), C-9 (no premature extraction — `<SchemaBuilder>` reused across `input_schema` + `output_schema` + future consumers); PY-1 (type hints), PY-2 (Pydantic), PY-3 (async I/O), PY-5 (context managers), PY-7 (no bare except); D-1 (Firestore session management), D-2 (Pydantic models), D-5 (no hardcoded credentials); T-1 (colocated pytest), T-2 (colocated `*.test.tsx`), T-3 (API integration tests), T-4 (split pure vs DB), T-5 (prefer integration over heavy mocking); G-1 (`make lint`), G-2 (`npm run format.fix`), G-3 (`npm run typecheck`); GH-1 (Conventional Commits).
