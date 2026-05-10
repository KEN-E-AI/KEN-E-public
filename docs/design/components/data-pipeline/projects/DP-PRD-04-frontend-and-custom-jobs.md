# DP-PRD-04 — Frontend + Custom-Job Authoring

**Status:** Blocked — resumes once DP-PRD-03, A-PRD-06, IN-PRD-03, and PR-PRD-03 ship
**Owner team:** Frontend (Data Pipeline) — backend-side endpoints (POST/PUT/DELETE/preview) are scoped in DP-PRD-01 and (for `/jobs/preview`) this PRD §4.2
**Blocked by:** DP-PRD-03 (task-system integration: `PlanTask.assignee_type="data_pipeline"`, `pipeline_spec`, `TaskOrchestrator.data_pipeline` branch, artifact write via A-PRD-03); A-PRD-06 (publishes the shared `frontend/src/components/dag/TaskGraph.tsx` + side-panel pattern this PRD plugs into); IN-PRD-03 (connection-management UI — custom-job authoring needs the connection picker); PR-PRD-03 (Calendar page — owns `ProjectEditDrawer` and `ActivityDetailPanel`, which this PRD extends in place)
**Blocks:** DP-PRD-06 (integration testing depends on a working end-to-end UI flow)
**Estimated effort:** 5–6 days

---

## 1. Context

DP-PRD-01 through DP-PRD-03 deliver the service, the Google Analytics connector, the seeded catalog, and the orchestrator branch that dispatches pipeline tasks end-to-end. Every one of those flows is API-only today — a user can only author a pipeline task by hand-constructing a `pipeline_spec` payload and PATCHing it onto a `PlanTask`. That is good enough for SAR-E's `is_system` ingestion plan (seeded programmatically) but not for the R5 narrow-specialist cohort, where a marketing manager needs to point-and-click their way from "I want daily GA transaction pulls" to a scheduled automation.

This PRD ships the UI surface that closes that gap. Three facts shape the design:

1. **A data pipeline is a task, created from the shared DAG editor.** Per the cross-component decision, data pipelines are **not** a top-level Workflows tab and have no standalone authoring route. They are `PlanTask`s with `assignee_type="data_pipeline"`, created from inside the shared DAG editor on either of two surfaces:
   - **Automation Details** at `/workflows/automations/{plan_id}` (A-PRD-06)
   - **Dashboard Details** at `/performance/dashboards/{plan_id}` (DB-PRD-03)

   Both surfaces use the **same shared DAG editor** that A-PRD-06 ships at `frontend/src/components/dag/TaskGraph.tsx`. Clicking "+ Add Task" on the canvas opens the right-side panel; selecting `assignee_type="data_pipeline"` swaps the agent / human fields for a `<PipelineJobPicker>` + schema-driven `<PipelineInputsForm>`. Calendar's `ProjectEditDrawer` (PR-PRD-03) ALSO accepts `data_pipeline` as an assignee type — there is no code constraint blocking it (per the architectural decision) — but the canonical authoring surface is the DAG editor.
2. **Custom jobs are authored inline in the same side-panel — no standalone route.** When the user picks the data-pipeline assignee, the side-panel offers two paths: pick an existing job from the global + per-account catalog (via `<PipelineJobPicker>`), or **author a new per-account job** in the same panel (via `<CustomJobAuthoringPanel>` — guided schema builder, connector picker from IN-PRD-03's connections, preview-run button). Platform-global jobs remain read-only from the UI; changes to them land through migrations + a CODEOWNER-gated PR.
3. **Custom code still lives in Skills.** The authoring panel does not accept Python. It composes a declarative `DataPipelineJob` document that the existing connectors know how to execute. This is the plan §9 non-goal — "user-authored Python" — reinforced at the UI layer.

**Run viewer** lives in `<ActivityDetailPanel>` (PR-PRD-03) — same component, used by Calendar, Automation Details, and Dashboard Details. For a task with `assignee_type="data_pipeline"`, the panel renders the `<PipelineRunPanel>` (status, resolved inputs, artifact preview, Weave deep-link).

The exit test: a user with no prior Data Pipeline experience adds a data-pipeline task to an automation or dashboard from the DAG editor side-panel, activates and reviews it, all without ever touching an API client; and an editor-role user authors a custom per-account job inline from the same panel, previews it, and uses it in a task in the same session.

> **History:** earlier drafts of this PRD scoped a standalone `/workflows/data-pipelines` route group (list + new + detail). That scope is **retired** — see the architectural decision documented in PROJECT-PLANNER and System Architecture §8.4. All authoring is inline in the DAG editor side-panel.

## 2. Scope

### In scope

- **Task-side-panel — "Data Pipeline" assignee option.** Adds `"data_pipeline"` to the `assignee_type` selector in the right-side task panel that opens from the shared DAG editor's "+ Add Task" button (and from Calendar's `ProjectEditDrawer`). When chosen, renders the `<PipelineJobPicker>` + schema-driven `<PipelineInputsForm>` in place of the agent-prompt / human-assignee fields. Same panel component used on all three surfaces (Automation Details, Dashboard Details, Calendar).
- **`<PipelineJobPicker>` component.** Browses global `data_pipeline_jobs/*` + per-account overlay from `GET /api/v1/data-pipeline/jobs`. Filterable by connector. Renders each job's `display_name`, `description`, and a connector badge. Search by `display_name` + `job_id` substring match. Footer offers "Or author a new job →" which expands the panel into `<CustomJobAuthoringPanel>` mode (editor-role users only).
- **`<PipelineInputsForm>` component.** JSON Schema → React form primitives. Inline validation against the job's declared `input_schema`. Primitive support: `string`, `integer`, `number`, `boolean`, `date`, `enum`, `array<primitive>`, single-level nested `object`. No `$ref` / `oneOf` / `allOf` / `anyOf` in v1 — deferred.
- **Pipeline-run viewer inside `<ActivityDetailPanel>`.** For a task with `assignee_type="data_pipeline"`, replaces the "completion notes" / "revision comment" panels with a `<PipelineRunPanel>` showing: status chip (`running` / `succeeded` / `failed` / `cached`), inputs table (resolved after `{inputs.*}` substitution per A-PRD-02), artifact preview (first N rows for Parquet / JSON; N = 25 by default), cache-hit indicator with the input-hash shown, per-run `started_at` / `finished_at` / `error_message`, and a "View Weave span" deep-link. Same component used on all three surfaces.
- **Artifact preview endpoint hand-off.** Uses the existing A-PRD-03 `GET /api/v1/artifacts/{artifact_id}/preview` (already rendered by Activity detail in PR-PRD-03). This PRD adds a thin preview-shape consumer for Parquet / JSON; CSV preview falls back to the default A-PRD-03 renderer.
- **`<CustomJobAuthoringPanel>` — inline authoring inside the side-panel.** Replaces the previously-scoped `/workflows/data-pipelines/*` standalone routes. When an editor-role user clicks "Or author a new job →" inside `<PipelineJobPicker>`, the right-side panel expands into authoring mode: guided schema builder for `input_schema` / `output_schema`, connector picker from IN-PRD-03's connections, "Preview" button, "Publish & Use" button. On Publish & Use, the new per-account job is created (`POST /api/v1/data-pipeline/jobs`), then immediately selected back in the picker so the user can fill `<PipelineInputsForm>` and finish creating the task. Cancel returns to the picker without publishing. Platform-global jobs are not editable from the UI.
- **Guided `input_schema` / `output_schema` builder.** Form-based UI for adding fields with name / type / required / default / description / `enum`-values. Emits a valid JSON Schema document. The builder validates on submit via the backend's JSON-Schema meta-validator (plan §4, `POST /api/v1/data-pipeline/jobs`).
- **Connection picker inside authoring.** Sources the list from IN-PRD-03's `GET /api/v1/integrations/{account_id}/connections` scoped to the connector the user selected. An authoring session can only pick an operation for a connector the account has a `connected` `PlatformConnection` for.
- **Preview run.** Authoring panel exposes a "Preview" button that POSTs the draft job + sample inputs to `POST /api/v1/data-pipeline/jobs/preview` (new endpoint scoped here — invokes the chosen connector end-to-end against live credentials, does **not** persist a `DataPipelineRun`). Displays the resulting row count + a first-N-row preview inline. Dry-run only; no artifact written.
- **Feature-flag gates** on both the inline authoring UI and the assignee option — see §5.4.
- **TypeScript mirrors** of every Pydantic shape in `frontend/src/types/dataPipeline.ts` (branded IDs per C-5; `import type` per C-6; `type` over `interface` per C-8).
- **Unit tests** per component + hook + form primitive; **Playwright specs** covering (a) the Automation-Details end-to-end flow (add data-pipeline task → run → view artifact) and (b) the inline authoring → preview → publish & use → invoke flow.

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
  - `/Volumes/WorkDrive/Active Work/Github/KEN-E/frontend/src/pages/workflows/` — UI-PRD-03 creates this directory; A-PRD-06 ships `AutomationDetailsPage` here (the surface where the data-pipeline side-panel mounts)
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
| Modify | `frontend/src/components/ProjectEditDrawer.tsx` (Calendar) — add `"data_pipeline"` option to assignee selector; render `<PipelineJobPicker>` + `<PipelineInputsForm>` when selected; feature-flag gated by `data_pipeline_task_assignee`. (Same option lives in the shared DAG side-panel — see next row.) |
| Modify | A-PRD-06's task-creation side panel (the right-side panel that opens from the shared DAG editor's "+ Add Task" button) — add `"data_pipeline"` option to its assignee selector; render `<PipelineJobPicker>` + `<PipelineInputsForm>` + (when expanded) `<CustomJobAuthoringPanel>`. **This is the canonical authoring surface.** |
| Create | `frontend/src/components/dataPipeline/PipelineJobPicker.tsx` — searchable, filterable catalog list with "Or author a new job →" footer (editor role) |
| Create | `frontend/src/components/dataPipeline/PipelineInputsForm.tsx` — JSON-Schema-driven form with inline validation |
| Create | `frontend/src/components/dataPipeline/PipelineRunPanel.tsx` — run viewer rendered inside `<ActivityDetailPanel>` |
| Create | `frontend/src/components/dataPipeline/PipelineArtifactPreview.tsx` — first-N-row table for Parquet / JSON |
| Modify | `frontend/src/components/ActivityDetailPanel.tsx` — swap completion / revision panels for `<PipelineRunPanel>` when `assignee_type="data_pipeline"` |
| Create | `frontend/src/components/dataPipeline/CustomJobAuthoringPanel.tsx` — inline (in-side-panel) authoring panel; replaces the previously-scoped standalone `/workflows/data-pipelines/new` and `/:job_id` routes. Stepper with 4 steps (Basics → Schemas → Connection → Preview) rendered in the side-panel; "Publish & Use" creates the job and selects it back in the parent picker. |
| Create | `frontend/src/components/dataPipeline/SchemaBuilder.tsx` — guided `input_schema` / `output_schema` composer (used inside `<CustomJobAuthoringPanel>`) |
| Create | `frontend/src/components/dataPipeline/ConnectorConnectionPicker.tsx` — IN-PRD-03 connection picker scoped to the chosen connector |
| Create | `frontend/src/components/dataPipeline/PipelinePreviewPanel.tsx` — "Preview" button + result display (used inside `<CustomJobAuthoringPanel>`) |
| Create | `frontend/src/hooks/useDataPipelineCatalog.ts` — TanStack Query hook for `GET /api/v1/data-pipeline/jobs` (global + overlay) |
| Create | `frontend/src/hooks/useDataPipelineJob.ts` — GET / PUT / DELETE for a single job |
| Create | `frontend/src/hooks/useDataPipelineRun.ts` — GET for a single run by `run_id` |
| Create | `frontend/src/hooks/usePipelineJobPreview.ts` — mutation hook for `POST /api/v1/data-pipeline/jobs/preview` |
| Create | `frontend/src/services/dataPipelineApi.ts` — axios wrappers (catalog + jobs + runs + preview) |
| Create | `frontend/src/types/dataPipeline.ts` — branded types + mirrors per §4.1 |
| Create | `api/src/kene_api/models/data_pipeline_preview_models.py` — Pydantic shapes per §4.2 |
| Create | `api/src/kene_api/routers/data_pipeline_preview.py` — `POST /api/v1/data-pipeline/jobs/preview` endpoint |
| Modify | `api/src/kene_api/main.py` — register the preview router |
| Create | `frontend/src/components/dataPipeline/__tests__/PipelineJobPicker.test.tsx` |
| Create | `frontend/src/components/dataPipeline/__tests__/PipelineInputsForm.test.tsx` |
| Create | `frontend/src/components/dataPipeline/__tests__/PipelineRunPanel.test.tsx` |
| Create | `frontend/src/components/dataPipeline/__tests__/SchemaBuilder.test.tsx` |
| Create | `frontend/src/components/dataPipeline/__tests__/PipelinePreviewPanel.test.tsx` |
| Create | `frontend/src/components/dataPipeline/__tests__/CustomJobAuthoringPanel.test.tsx` |
| Create | `frontend/src/components/__tests__/ProjectEditDrawer.dataPipeline.test.tsx` — covers Calendar branch |
| Create | `frontend/src/components/__tests__/ActivityDetailPanel.pipelineRun.test.tsx` — covers run-viewer branch |
| Create | `frontend/src/components/dag/__tests__/TaskGraph.dataPipelineSidePanel.test.tsx` — covers add-data-pipeline-task flow inside the shared DAG editor |
| Create | `frontend/src/hooks/__tests__/useDataPipelineCatalog.test.ts` |
| Create | `frontend/src/hooks/__tests__/usePipelineJobPreview.test.ts` |
| Create | `api/tests/integration/test_data_pipeline_preview_router.py` |
| Create | `frontend/e2e/data-pipeline-automation-flow.spec.ts` — Playwright: from `/workflows/automations/{plan_id}` add a data-pipeline task → activate → view artifact |
| Create | `frontend/e2e/data-pipeline-inline-authoring.spec.ts` — Playwright: open shared DAG side-panel → "+ Add Task" → choose Data Pipeline → "Or author a new job →" → step through Basics / Schemas / Connection / Preview / Publish & Use → back to picker with new job auto-selected → finish task creation → run completes |

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

### 5.3 Custom-job authoring (inline in the side-panel)

**Entry point:** clicking "+ Add Task" in the shared DAG editor (A-PRD-06's `<TaskGraph>`) opens the right-side task panel. Selecting `assignee_type="data_pipeline"` renders `<PipelineJobPicker>`. Editor-role users see an "Or author a new job →" footer link in the picker; clicking it expands the right-side panel into `<CustomJobAuthoringPanel>` mode (the picker view is preserved in a "Back to picker" affordance).

**`<CustomJobAuthoringPanel>` — 4-step stepper inside the side-panel** (`step=basics|schemas|connection|preview`, persisted to local component state — no URL routing since this lives in a panel, not a page):

1. **Basics** — `display_name`, `description`, connector (dropdown), operation (free-text; v1 does not enumerate supported operations per connector — documented in §9 as an open question), `output_format`, `default_cache_ttl_seconds`, `test_mode_policy`, `visible_in_frontend`.
2. **Schemas** — `<SchemaBuilder>` for `input_schema`; separate `<SchemaBuilder>` for `output_schema`. Each emits a valid JSON Schema document. Validated client-side against a meta-validator bundled with the frontend; errors render inline.
3. **Connection** — `<ConnectorConnectionPicker>` filtered to the chosen connector. If no connection exists, shows a "Connect {connector} first" CTA that deep-links to `/settings/integrations?return_to=<current-DAG-url>`.
4. **Preview** — `<PipelinePreviewPanel>`: renders the declared `input_schema` via `<PipelineInputsForm>` with sample-value inputs, fires `usePipelineJobPreview()` on "Run Preview", renders the first N rows + row-count + duration. "Publish & Use" button enabled only after a successful preview run.

**On Publish & Use:**
- `POST /api/v1/data-pipeline/jobs` with the composed `DataPipelineJob` body.
- Backend re-validates (a) the job against `DataPipelineJob` and (b) the nested `input_schema` / `output_schema` against a JSON-Schema meta-validator (plan §4).
- On success, the panel returns to `<PipelineJobPicker>` mode with the new job pre-selected, ready for the user to fill `<PipelineInputsForm>` and finish creating the task. Success toast confirms publication.

**Editing an existing per-account job:**
Editing happens via the same panel. From the picker, a row's "Edit" affordance (editor role only, per-account jobs only) opens `<CustomJobAuthoringPanel>` pre-populated. "Save & Use" calls `PUT /api/v1/data-pipeline/jobs/{job_id}` (DP-PRD-01 §6.4.1). `version` auto-increments server-side on publish. A warning banner fires if any active plan references the job — edits ship new runs with the new version but existing cached runs remain addressable by their `input_hash` + prior `version`.

### 5.4 Feature-flag gating

| Flag | Scope | Behavior when off |
|---|---|---|
| `data_pipeline_task_assignee` | "Data Pipeline" assignee option in both the Calendar `ProjectEditDrawer` and the shared DAG editor's task side-panel | Option hidden everywhere; existing pipeline tasks still render in `ActivityDetailPanel` (read-only) so we don't brick already-authored tasks. |
| `data_pipeline_custom_jobs` | "Or author a new job →" footer in `<PipelineJobPicker>` + the entire `<CustomJobAuthoringPanel>` | Footer link hidden; "Edit" affordance on per-account job rows hidden. The global + per-account job catalog is still browsable via `<PipelineJobPicker>` (when `data_pipeline_task_assignee=true`). |

Role gating from DM-PRD-07:

| Action | Minimum role |
|---|---|
| Browse the job catalog in `<PipelineJobPicker>` | any authenticated with task-authoring permission |
| Open `<CustomJobAuthoringPanel>` (footer link visible) | editor |
| Create a per-account job (`POST /jobs`) | editor |
| Update a per-account job (`PUT /jobs/{job_id}`) | editor |
| Delete a per-account job (`DELETE /jobs/{job_id}`) | editor (must be the owning account) |
| Run a preview (`POST /jobs/preview`) | editor |
| Select a pipeline job in the side-panel | same role as task authoring today (per PR-PRD-03 / A-PRD-06) |
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
| `POST` | `/api/v1/data-pipeline/jobs` | Create a per-account custom job | DP-PRD-01 §6.4 |
| `PUT` | `/api/v1/data-pipeline/jobs/{job_id}` | Update a per-account custom job (bumps `version` monotonically; rejects writes against global `job_id`) | DP-PRD-01 §6.4.1 |
| `DELETE` | `/api/v1/data-pipeline/jobs/{job_id}` | Soft-delete a per-account custom job (`is_active=false`); rejects writes against global `job_id` | DP-PRD-01 §6.4.2 |
| `GET` | `/api/v1/data-pipeline/{account_id}/runs` | List runs (filters: plan_id, task_id, job_id, status, date range) | DP-PRD-01 |
| `GET` | `/api/v1/data-pipeline/{account_id}/runs/{run_id}` | Run detail + artifact link | DP-PRD-01 |
| `GET` | `/api/v1/artifacts/{artifact_id}/preview` | First-N-row preview of a `TaskArtifact` | A-PRD-03 |
| `GET` | `/api/v1/integrations/{account_id}/connections` | Connection list, filtered client-side by connector | IN-PRD-03 |
| `PATCH` | `/api/v1/plans/{plan_id}/tasks/{task_id}` | Persist `assignee_type="data_pipeline"` + `pipeline_spec` on a task | PR-PRD-01 |

## 7. Acceptance criteria

1. Opening the shared DAG editor at `/workflows/automations/{plan_id}` (or `/performance/dashboards/{plan_id}`), clicking "+ Add Task", and choosing the **Data Pipeline** assignee in the right-side panel renders `<PipelineJobPicker>`; the agent-prompt and human-assignee fields disappear from the DOM. Same flow works from Calendar's `ProjectEditDrawer`.
2. `<PipelineJobPicker>` renders the union of `data_pipeline_jobs/*` + `accounts/{account_id}/data_pipeline_jobs/*` returned by `GET /api/v1/data-pipeline/jobs`; the connector filter narrows the list correctly; search matches against `display_name` and `job_id`. Editor-role users see the "Or author a new job →" footer link; viewer-role users do not.
3. `<PipelineInputsForm>` renders one input control per property in the selected job's `input_schema`; required fields surface an inline error when empty on Save; enum fields render as a select; `date` fields render a date picker; `array<primitive>` fields render an add-row control.
4. On Save with a valid pipeline spec, the PATCH to `/api/v1/plans/{plan_id}/tasks/{task_id}` carries `assignee_type="data_pipeline"` + `pipeline_spec: { job_id, inputs, output_artifact_name }`.
5. For a task with `assignee_type="data_pipeline"` that has not yet run, `<ActivityDetailPanel>` renders `<PipelineRunPanel>` in its empty state ("This task has not run yet") with the resolved inputs preview.
6. For a task with a completed run, `<PipelineRunPanel>` renders the status chip, resolved inputs table, `<PipelineArtifactPreview>` with the first 25 rows, `started_at` / `finished_at` / duration, and a cache badge when `run.cache_hit=true` showing the truncated `input_hash`.
7. For a failed run, `<PipelineRunPanel>` renders the `error_message` in a monospace error block and hides the artifact-preview panel.
8. Feature-flag `data_pipeline_task_assignee=false` removes the "Data Pipeline" option from both the DAG editor's task side-panel and Calendar's `ProjectEditDrawer`; already-authored pipeline tasks still render in `<ActivityDetailPanel>` (read-only).
9. Feature-flag `data_pipeline_custom_jobs=false` hides the "Or author a new job →" footer in `<PipelineJobPicker>` and the per-row "Edit" affordance on custom jobs; the picker itself is unaffected when `data_pipeline_task_assignee=true`. **No `/workflows/data-pipelines*` routes exist** (this scope was retired — see §1 history note).
10. Clicking "Or author a new job →" in `<PipelineJobPicker>` (editor role) expands the side-panel into `<CustomJobAuthoringPanel>` mode; clicking "Back to picker" returns without losing in-progress draft state.
11. The authoring panel's stepper enforces step order: Schemas cannot be entered without a chosen connector on Basics; Preview cannot fire without a valid `input_schema` + an account connection to the chosen connector.
12. `<ConnectorConnectionPicker>` shows only `PlatformConnection`s for the chosen connector with `status="connected"`; when zero matches, the "Connect {connector} first" CTA deep-links to `/settings/integrations` with a `return_to` query parameter pointing back to the current DAG URL (preserving the user's plan + edit context).
13. "Run Preview" POSTs to `/api/v1/data-pipeline/jobs/preview` with `{connector, operation, inputs, input_schema, sample_row_limit: 25}`; on success renders the row count, first-N rows, and a `duration_ms` pill; on 429 renders a rate-limit warning with the `Retry-After` header value.
14. "Publish & Use" is disabled until a successful preview run has completed in the current session; on click, POSTs to `/api/v1/data-pipeline/jobs`, then on 2xx the panel returns to `<PipelineJobPicker>` mode with the newly-created job pre-selected (one round-trip; user immediately fills inputs and finishes the task).
15. Role gating: a viewer-role user does not see the "Or author a new job →" footer; the same user hitting `POST /api/v1/data-pipeline/jobs` directly gets a 403 response.
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

**Unit tests — panels + pages:**
- `CustomJobAuthoringPanel.test.tsx` — stepper state transitions inside the side-panel; "Publish & Use" gated on successful preview; POST payload shape on Publish & Use; cancel returns to picker without losing draft.
- `PipelineJobPicker.test.tsx` (extended) — "Or author a new job →" footer renders only for editor role and only when `data_pipeline_custom_jobs=true`; clicking it transitions the parent panel into authoring mode.
- `ProjectEditDrawer.dataPipeline.test.tsx` — Calendar branch: assignee option gated on `data_pipeline_task_assignee` flag; PATCH payload carries `pipeline_spec` on Save.
- `TaskGraph.dataPipelineSidePanel.test.tsx` — DAG side-panel branch: "+ Add Task" → choose Data Pipeline → picker renders → publish-and-use flow round-trips.
- `ActivityDetailPanel.pipelineRun.test.tsx` — branches correctly on `assignee_type`; renders `<PipelineRunPanel>` for pipeline tasks only.

**Unit tests — hooks:**
- `useDataPipelineCatalog.test.ts` — merges global + account lists; de-dupes by `job_id` with account overlay winning.
- `usePipelineJobPreview.test.ts` — mutation fires correct body; timeout handling; rate-limit handling.

**Integration tests — backend:**
- `test_data_pipeline_preview_router.py` — happy path with a `StubConnector` returning deterministic rows; 4xx on semantic connector errors; 408 on timeout; 429 on rate-limit breach; 403 for viewer role; 422 on malformed `input_schema`.

**Playwright — E2E:**
- `data-pipeline-automation-flow.spec.ts` — seed an account with one connected Google integration and the seeded GA jobs. Navigate to `/workflows/automations/{plan_id}` → click "+ Add Task" in the shared DAG editor → choose "Data Pipeline" assignee in the side-panel → pick `ga.sessions_by_date` → fill `target_date` → Save → activate the plan → verify the task fires → open `<ActivityDetailPanel>` → verify `<PipelineRunPanel>` renders the artifact preview.
- `data-pipeline-inline-authoring.spec.ts` — seed an editor-role user with one connected Google integration. Open the shared DAG editor → "+ Add Task" → choose "Data Pipeline" assignee → click "Or author a new job →" → step through Basics / Schemas / Connection / Preview with sample inputs → click "Publish & Use" → verify the panel returns to the picker with the new job pre-selected → fill inputs → Save → activate → verify the run completes against the newly-authored job.

## 9. Risks & open questions

### Resolved decisions

| Decision | Resolution |
|---|---|
| Authoring entry point | Inline inside the shared DAG editor's task side-panel (A-PRD-06's "+ Add Task" + Calendar's `ProjectEditDrawer`). **No standalone `/workflows/data-pipelines` routes** — that scope is retired. |
| Calendar page integration | Extends `ProjectEditDrawer` + `ActivityDetailPanel` in place, not a sibling surface. |
| PUT / DELETE on per-account jobs | **Owned by DP-PRD-01 §6.4.1 / §6.4.2.** This PRD consumes them only — no backend work for the catalog mutations. |
| Custom-job authoring scope | Per-account only in v1; platform-global jobs read-only from UI. |
| Code in custom jobs | Declarative JSON Schema only; no Python. Code lives in Skills (plan §9). |
| Preview semantics | Synchronous, credentialed, no `DataPipelineRun` persisted, separate Weave span. |
| Feature-flag split | Two flags — `data_pipeline_task_assignee` (consumer-side) and `data_pipeline_custom_jobs` (authoring-side). Either can be off independently. |
| Role gating for authoring | `editor` minimum per DM-PRD-07. |
| Schema builder scope | Primitive subset in v1 (`string`, `integer`, `number`, `boolean`, `date`, `enum`, `array<primitive>`, single-level `object`). `$ref` / `oneOf` / `allOf` / `anyOf` deferred. |

### Remaining open questions

| Question | Disposition |
|---|---|
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
- Sibling: [A-PRD-02 Recurring scheduler](../../automations/projects/A-PRD-02-recurring-scheduler.md) — `{inputs.*}` substitution
- Sibling: [A-PRD-03 Task artifact system](../../automations/projects/A-PRD-03-task-artifact-system.md) — artifact preview endpoint
- Policy: [DM-PRD-07 Approval & audit](../../data-management/projects/DM-PRD-07-approval-workflow-and-audit.md) — role table
- Feature Flags: [FF-PRD-03 SDK hook](../../feature-flags/projects/FF-PRD-03-frontend-sdk-and-e2e.md) — `useFeatureFlag`
- Design tokens: [UI-PRD-01](../../ui/projects/UI-PRD-01-design-system-foundation.md)
- Code files expected to be touched:
  - `frontend/src/components/ProjectEditDrawer.tsx` (Calendar)
  - `frontend/src/components/ActivityDetailPanel.tsx` (run viewer branch)
  - A-PRD-06's task-creation side panel (DAG editor)
  - `frontend/src/components/dataPipeline/*` (including the new `CustomJobAuthoringPanel.tsx`)
  - `frontend/src/hooks/useDataPipelineCatalog.ts`, `useDataPipelineJob.ts`, `useDataPipelineRun.ts`, `usePipelineJobPreview.ts`
  - `frontend/src/services/dataPipelineApi.ts`
  - `frontend/src/types/dataPipeline.ts`
  - `frontend/src/App.tsx` (route registration)
  - `api/src/kene_api/models/data_pipeline_preview_models.py`
  - `api/src/kene_api/routers/data_pipeline_preview.py`
  - `api/src/kene_api/main.py` (router mount)
- CLAUDE.md rules in scope: C-1 (TDD), C-2 (domain vocabulary — `DataPipelineJob`, `DataPipelineRun`, `PipelineJobSpec`, `PipelineOutput`, `pipeline_spec`), C-5 (branded IDs — `AccountId`, `JobId`, `RunId`, `ArtifactId`), C-6 (`import type`), C-8 (`type` default), C-9 (no premature extraction — `<SchemaBuilder>` reused across `input_schema` + `output_schema` + future consumers); PY-1 (type hints), PY-2 (Pydantic), PY-3 (async I/O), PY-5 (context managers), PY-7 (no bare except); D-1 (Firestore session management), D-2 (Pydantic models), D-5 (no hardcoded credentials); T-1 (colocated pytest), T-2 (colocated `*.test.tsx`), T-3 (API integration tests), T-4 (split pure vs DB), T-5 (prefer integration over heavy mocking); G-1 (`make lint`), G-2 (`npm run format.fix`), G-3 (`npm run typecheck`); GH-1 (Conventional Commits).
