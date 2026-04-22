# Dashboards — Product Requirements Document

> **Linear Team:** [TBD] Dashboards
> **Last Updated:** 2026-04-22
> **Status:** Design complete, implementation not started

## 1. Overview

The Dashboards component lets a user compose a canvas of widgets — text blocks, data visualizations, tables, and file cards — whose content is produced by an agent-executed plan. A dashboard is a `ProjectPlan` with `type="dashboard"` that additionally carries a `dashboard_placements` array describing the canvas layout. Running the dashboard invokes the standard Automations manual-trigger endpoint, produces a `PlanRun` with artifacts via the existing A-PRD-03 artifact system, and the canvas refreshes by re-resolving each placement against the latest run.

The component does not introduce a new data store, orchestrator, or scheduler. It sits on top of five upstream components — **Project Tasks** (the `ProjectPlan` / `PlanTask` base model), **Automations** (`PlanRun`, manual trigger, recurring scheduler, `type` enum), **Automations Artifacts** (A-PRD-03's GCS store and signed-URL downloads), **Data Management Shape B** (the Firestore convention every account-scoped collection uses), and **Approval Workflow & Audit** (DM-PRD-07's role gate and audit log). What Dashboards adds is (a) a canvas layout on the plan, (b) a server-side artifact resolver that maps `(task_id, file_type)` → the latest `PlanRun`'s matching `OutputFile` with status (fresh / stale / disconnected / pending), and (c) the Performance-tab UI to create, edit, run, and view dashboards.

A developer reading only this section should understand: this component owns the `/api/v1/dashboards/*` API surface, the Dashboards tab on the Performance page, the Dashboard Details page (canvas + widget renderers), and the `DashboardArtifactResolver` service. It does not own plan CRUD, run triggering, schedule config, or artifact storage — those come from Project Tasks, Automations, and Automations Artifacts respectively.

## 2. Architecture

### 2.1 Key Directories

| Path | Purpose |
|------|---------|
| `api/src/kene_api/models/project_plan_models.py` | Extended in DB-PRD-01 with `DashboardPlacement`, `OutputConfig`. Base model owned by Project Tasks PR-PRD-01. |
| `api/src/kene_api/models/output_types.py` | `OutputFileType` enum (shared across Automations + Dashboards). DB-PRD-01. |
| `api/src/kene_api/models/dashboard_models.py` | `DashboardArtifact`, `DashboardGetResponse` wrapper. DB-PRD-01. |
| `api/src/kene_api/routers/dashboards.py` | `/api/v1/dashboards/*` — list / get-enriched / create / PUT placements / delete. DB-PRD-01. |
| `api/src/kene_api/services/dashboard_artifact_resolver.py` | Maps `(task_id, file_type)` → latest `PlanRun`'s matching `OutputFile` with status. DB-PRD-01. |
| `frontend/src/pages/performance/DashboardsSection.tsx` | Dashboards tab content (list view, empty state). DB-PRD-02. |
| `frontend/src/pages/performance/DashboardDetailsPage.tsx` | `/performance/dashboards/{plan_id}` — DAG + canvas + task panel. DB-PRD-03. |
| `frontend/src/components/dashboards/DashboardCanvas.tsx` | Free-form positioning, drag, resize, 8-px grid snap. DB-PRD-03. |
| `frontend/src/components/dashboards/widgets/` | Four widget renderers: `TextWidget`, `VisualizationWidget`, `TableWidget`, `FileWidget`. DB-PRD-03. |
| `frontend/src/components/dashboards/PinToDashboardPicker.tsx` | Task-panel action that adds a placement for a task's declared output. DB-PRD-03. |
| `frontend/src/services/dashboardsApi.ts` | Axios wrappers for the dashboards API. DB-PRD-02 + DB-PRD-03. |
| `frontend/src/hooks/useDashboardDetails.ts`, `useDashboards.ts` | TanStack Query hooks (2 s poll while a run is in-flight; 30 s stale on list). DB-PRD-02 + DB-PRD-03. |

### 2.2 Data Flow

1. **Authoring:** A user clicks "+ New Dashboard" on the Performance → Dashboards tab. Frontend POSTs `{title, description, tags}`; backend creates a `ProjectPlan` with `type="dashboard"`, empty tasks, empty placements. User is redirected to the Details page.
2. **Task DAG:** The Details page exposes the same task-graph + task-panel UI as the Automation Details page (A-PRD-06). The user authors tasks; for any task that should feed the canvas, they enable `output_config.enabled=true` and declare `expected_file_types` (e.g., `["visualization", "text"]`).
3. **Pinning:** From the task panel, the user clicks "Pin to dashboard" → picker lists the task's expected file types → selecting one appends a `DashboardPlacement` at the next empty grid location. The canvas PUT is debounced 500 ms.
4. **Running:** The Run button POSTs to `A-PRD-02`'s manual-trigger endpoint. A normal `PlanRun` executes via the `TaskOrchestrator`. Each agent task emits artifacts via `attach_task_artifact` (A-PRD-03). The frontend polls `GET /dashboards/{plan_id}` every 2 s until the run reaches terminal state.
5. **Resolution:** The `DashboardArtifactResolver` walks each placement, finds the matching `OutputFile` from the latest run's `artifacts/` subcollection, classifies it (fresh / stale / disconnected / pending), and inlines the payload (text, Vega-Lite spec ≤64 KB) or returns a 1-hour signed URL (CSV, images, large payloads).
6. **Rendering:** The canvas receives `DashboardArtifact[]` from the GET response and routes each to one of four widget renderers by `file_type`. Status badges overlay tiles as needed.
7. **Scheduling (optional):** A dashboard can carry a `recurrence_cron` + `recurrence_timezone`. If set and `is_active=true`, A-PRD-02's recurring scheduler tick fires runs on schedule. The canvas refreshes on the next user visit (no SSE push in v1).

Storage: placements are embedded on the plan doc (not a subcollection). Canvas layout persists on `PUT /placements`; plan + task edits persist via PR-PRD-01; artifacts live in `accounts/{account_id}/plan_runs/{run_id}/artifacts/{artifact_id}` (A-PRD-03); audit entries via DM-PRD-07.

### 2.3 API Contracts

Owned endpoints:

| Endpoint | Method | Owner | Schema |
|----------|--------|-------|--------|
| `/api/v1/dashboards/{account_id}` | GET | DB-PRD-01 | `PaginatedResponse<DashboardSummary>`; server filters `type="dashboard"` + `is_system=false` |
| `/api/v1/dashboards/{account_id}/{plan_id}` | GET | DB-PRD-01 | `{plan: ProjectPlan, latest_run: PlanRun \| null, artifacts: DashboardArtifact[]}` with resolver-applied status |
| `/api/v1/dashboards/{account_id}` | POST | DB-PRD-01 | `{title, description?, tags?}` → new `ProjectPlan` |
| `/api/v1/dashboards/{account_id}/{plan_id}/duplicate` | POST | DB-PRD-01 | `{title?}` → new `ProjectPlan` — deep-copy with new task_ids + remapped depends_on and placements; schedule preserved but `is_active=false` |
| `/api/v1/dashboards/{account_id}/{plan_id}/placements` | PUT | DB-PRD-01 | `DashboardPlacement[]` (full replace, last-write-wins) |
| `/api/v1/dashboards/{account_id}/{plan_id}` | DELETE | DB-PRD-01 | soft-delete via PR-PRD-01 |

Consumed endpoints (not duplicated in the dashboards namespace):

| Endpoint | Owner | Purpose in this component |
|---|---|---|
| `PUT /api/v1/plans/{account_id}/{plan_id}` | PR-PRD-01 | Title edit, DAG edit |
| `PATCH /api/v1/plans/{account_id}/{plan_id}/tasks/{task_id}` | PR-PRD-01 | Task edits including `output_config` |
| `POST /api/v1/automations/{account_id}/{plan_id}/runs` | A-PRD-02 | Run button (manual trigger) |
| `PATCH /api/v1/automations/{account_id}/{plan_id}/recurrence` | A-PRD-01 | Schedule editor |
| `GET /api/v1/dashboards/{account_id}/{plan_id}/runs/{run_id}/artifacts/{artifact_id}/download` | A-PRD-03 | Signed-URL generation (via resolver) |

Schema source of truth: `api/src/kene_api/models/project_plan_models.py` + `dashboard_models.py` (Pydantic); mirrored TypeScript branded types in `frontend/src/types/dashboard.ts` (`DashboardPlanId`, `DashboardSummary`, `DashboardArtifact`, `DashboardPlacement`).

### 2.4 Key Abstractions

| Abstraction | Path | Purpose |
|-------------|------|---------|
| `DashboardPlacement` | `api/src/kene_api/models/project_plan_models.py` | Single canvas item: `(placement_id, task_id, file_type, x, y, w, h, view_override?, color?, show_data_labels?)`. Embedded array on `ProjectPlan` when `type="dashboard"`. Cap 100. |
| `OutputConfig` | Same file | `(enabled, expected_file_types)` on `PlanTask` — declares what outputs a task produces. Drives the Pin-to-Dashboard picker and the resolver's staleness detection. |
| `OutputFileType` enum | `api/src/kene_api/models/output_types.py` | Shared with Automations: `text \| visualization \| csv \| image \| document \| json \| html \| video \| audio \| other` |
| `DashboardArtifact` | `api/src/kene_api/models/dashboard_models.py` | Resolver output: status + inline payload or signed URL. One per placement on every GET. |
| `DashboardArtifactResolver` | `api/src/kene_api/services/dashboard_artifact_resolver.py` | Maps `(plan, latest_run) → DashboardArtifact[]`. O(placements) Firestore reads bounded at 100. Inlines ≤64 KB; else signed URL via A-PRD-03's store. |
| `DashboardCanvas` | `frontend/src/components/dashboards/DashboardCanvas.tsx` | Free-form canvas with drag, corner-resize, 8-px grid snap. Debounces `PUT /placements` 500 ms after last interaction. Flushes on `beforeunload`. |
| Four widget renderers | `frontend/src/components/dashboards/widgets/` | Text (markdown), Visualization (react-vega with `view_override`/`color`/`show_data_labels`), Table (CSV + papaparse + DataTable), File (fallback with download card). |

## 3. Component Dependencies

### 3.1 Depends On

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **Project Tasks** | `ProjectPlan` / `PlanTask` base models, plan-edit endpoints, versioning, audit pattern. DB-PRD-01 extends both models with `dashboard_placements` + `output_config`. | [`../project-tasks/README.md`](../project-tasks/README.md), [PR-PRD-01](../project-tasks/projects/PR-PRD-01-data-model-and-api.md) |
| **Automations** | `ProjectPlan.type` enum, `PlanRun` + `TaskRunState`, manual-trigger endpoint, recurring scheduler, `schedule/preview` endpoint. DB-PRD-01 adds the small default filter `type="freeform"` to A-PRD-01's list endpoint. DB-PRD-03 reuses `AutomationGraph`, `AutomationTaskPanel`, `AutomationSchedulePanel` from A-PRD-06 with a small additive prop (`context: "automation" \| "dashboard"`). | [`../automations/README.md`](../automations/README.md), [A-PRD-01](../automations/projects/01-data-model-and-api.md), [A-PRD-02](../automations/projects/02-recurring-scheduler.md), [A-PRD-06](../automations/projects/06-automation-details-page.md) |
| **Automations Artifacts (A-PRD-03)** | GCS-backed `TaskArtifact` store at `gs://kene-task-artifacts-{env}/{account_id}/{plan_id}/{run_id}/{task_id}/...`; `artifact_store.generate_signed_url(artifact_id, ttl_seconds=3600)` helper; 100 MB cap; 30-day lifecycle. The resolver reads artifact metadata and generates signed URLs via these helpers — no new storage path. | [A-PRD-03](../automations/projects/03-task-artifact-system.md) |
| **Data Management — DM-PRD-00 (Migration Foundation)** | Shape B convention (`accounts/{account_id}/project_plans/...`). No new subcollection introduced (placements embedded). May need one new composite index — see §2.3 index note in DB-PRD-01. | [`../data-management/README.md`](../data-management/README.md) §7.1 / §7.7, [DM-PRD-00](../data-management/projects/DM-PRD-00-migration-foundation.md) |
| **Data Management — DM-PRD-05 (Deletion Sweep Rewrite)** | `recursive_delete(accounts/{account_id})` covers `project_plans` including embedded `dashboard_placements`. No additional cleanup logic required. | [DM-PRD-05](../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md) |
| **Data Management — DM-PRD-07 (Approval Workflow & Audit)** | `require_role` FastAPI dependency on every mutating endpoint; `write_audit` helper on every mutation including placement PUT diffs. Role gates: `viewer` (GET only), `editor` (POST / PUT / DELETE). | [`../data-management/README.md`](../data-management/README.md) §7.6, [DM-PRD-07](../data-management/projects/DM-PRD-07-approval-workflow-and-audit.md) |
| **UI — UI-PRD-01 (Design System)** | Soft Maximalism tokens, shadcn primitives, theming via CSS variables (used by the Vega renderer). | [UI-PRD-01](../ui/projects/UI-PRD-01-design-system-foundation.md) |
| **UI — UI-PRD-07 (Performance Page)** | *Soft* dep — DB-PRD-02 extends the Performance page's tab container. If UI-PRD-07 hasn't shipped, DB-PRD-02 lands a minimal tab container using UI-PRD-01 tokens. | [UI-PRD-07](../ui/projects/UI-PRD-07-performance-page.md) |
| External | `react-vega` (renderer), `react-markdown` + `rehype-raw` (text widget), `papaparse` (CSV widget), `dagre` (via A-PRD-06's graph). | — |

### 3.2 Depended On By

| Component | Dependency |
|-----------|------------|
| Knowledge Graph (future) | Session-end automations may surface their outputs on a dashboard. No current dependency; noted for forward planning. |
| Extensions (future) | A future Extensions component will likely ship pre-built dashboard templates that instantiate a `type="dashboard"` plan from a template. Out of scope for v1. |

## 4. Design System References

| Document | Sections | When to Read |
|----------|----------|--------------|
| Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) | Performance page, Dashboards tab, Dashboard Details (DAG split + canvas + task panel) | When implementing DB-PRD-02 (list) or DB-PRD-03 (details + canvas). |
| `frontend/CLAUDE.md` | CSS architecture, component library, branded types | Before adding new visual components. |
| `frontend/src/pages/workflows/AutomationDetailsPage.tsx` (A-PRD-06) | Task-graph + task-panel integration pattern | Starting DB-PRD-03; the Dashboard Details page mirrors this layout. |
| `docs/figma-export/AH-PRD-04-data-visualization.md` / `data-visualization-1.md` | Vega-Lite artifact format, `create_visualization()` tool | When extending `VisualizationWidget`. |
| [`../agentic-harness/data-visualization.md`](../agentic-harness/components/agentic-harness/data-visualization.md) | Chart rendering, channel considerations, theming | When debugging Vega rendering or adding a new `view_override`. |

## 5. Project Index

The component's work is split across **4 independently shippable project PRDs** under [`projects/`](./projects/). DB-PRD-01 is the foundation; the rest run in parallel once the API contract is published. DB-PRD-04 closes out with end-to-end coverage and a verification report.

### 5.1 Dependency graph

```
  Upstream:
  ────────────────────────────────────────────────────────────
  PR-PRD-01 ──┐
              │
  A-PRD-01 ──┤  publishes ProjectPlan + PlanTask + type enum
              │
  A-PRD-03 ──┤  publishes TaskArtifact store + signed URLs
              │
  DM-PRD-07 ──┘  publishes require_role + write_audit
              ▼
       ┌────────────────────┐
       │     DB-PRD-01      │  Data model + resolver + API (BLOCKING)
       └──┬─────────────┬───┘
          │             │
          ▼             │
  ┌──────────────┐      │
  │  DB-PRD-02   │      │      ┌────────────┐
  │  Tab + List  │      │      │  A-PRD-06  │ (shared graph/task-panel components)
  └──────┬───────┘      │      └─────┬──────┘
         │              │            │
         └───────┬──────┘            │
                 ▼                   │
            ┌────────────────┐       │
            │   DB-PRD-03    │◀──────┘
            │  Details +     │
            │   Canvas       │
            └───────┬────────┘
                    ▼
            ┌────────────────┐
            │   DB-PRD-04    │  Integration testing + polish
            └────────────────┘
```

### 5.2 Projects

| # | Project PRD | Owner team | Blocked by | Parallel with | Est. |
|---|-------------|------------|------------|---------------|------|
| 01 | [Data Model & API](./projects/DB-PRD-01-data-model-and-api.md) | Backend (foundation) | PR-PRD-01, A-PRD-01, A-PRD-03, DM-PRD-05, DM-PRD-07 | — | 2–3 days |
| 02 | [Dashboards Tab & List](./projects/DB-PRD-02-dashboards-tab-and-list.md) | Frontend | DB-PRD-01 (soft: UI-PRD-07) | 03 | 2 days |
| 03 | [Dashboard Details & Canvas](./projects/DB-PRD-03-dashboard-details-and-canvas.md) | Frontend | DB-PRD-01, DB-PRD-02, A-PRD-06 | 02 | 4–5 days |
| 04 | [Integration Testing & Polish](./projects/DB-PRD-04-integration-testing-and-polish.md) | QA + first-finished team | DB-PRDs 01–03 | — | 1–2 days |

### 5.3 Cross-PRD coordination points

Two touchpoints don't fit cleanly inside one PRD:

- **`AutomationTaskPanel` prop extension (DB-PRD-03 ↔ A-PRD-06):** adds `context: "automation" | "dashboard"` prop (default `"automation"`). In dashboard context, renders the Pin-to-Dashboard button. Additive; no breaking change for A-PRD-06 callers. A-PRD-06 owners review the PR.
- **Automations list default filter (DB-PRD-01 ↔ A-PRD-01):** `GET /api/v1/automations/{account_id}` gains a default `type="freeform"` filter to keep dashboards out. Small, backwards-compatible for the Automations UI (which never wanted dashboards in the list). DB-PRD-01 owners drive; A-PRD-05 team reviews.

### 5.4 Recommended workflow

1. **Prerequisite sprint(s):** PR-PRD-01, A-PRD-01, A-PRD-03, DM-PRD-05, DM-PRD-07 all merge. Frontend teams stub against DB-PRD-01's published Pydantic models.
2. **Sprint 1 (foundation):** Backend ships DB-PRD-01. Frontend begins DB-PRD-02 + DB-PRD-03 against API stubs.
3. **Sprint 2 (parallel):** DB-PRD-02 (list) and DB-PRD-03 (canvas) run in parallel. DB-PRD-03 coordinates with A-PRD-06 for the task-panel prop.
4. **Sprint 3 (close-out):** DB-PRD-04 runs the E2E suite, verifies the list-separation guarantee, measures perf, appends the verification report to this README.

## 6. Global Document References

| Document | Relevant Sections | Why |
|----------|-------------------|-----|
| [`./implementation-plan.md`](./implementation-plan.md) | All sections | Architectural overview + phasing rationale. Read first if you're new to the component. |
| [`../project-tasks/README.md`](../project-tasks/README.md) | §2 Architecture, §5 Project Index | Dashboards extends the same `ProjectPlan` data model; read the Project Tasks README before starting any DB-PRD. |
| [`../automations/README.md`](../automations/README.md) | §2 Architecture, §5 Project Index | A dashboard runs through the same `TaskOrchestrator` + artifact system as an automation. Required reading for DB-PRD-01 and DB-PRD-03. |
| [`../data-management/README.md`](../data-management/README.md) | §7.6 `is_system` convention, §7.7 cross-account query pattern | Dashboards inherits both conventions; the resolver uses collection-scope indexes (not collection-group). |
| [`../../DESIGN-REVIEW-LOG.md`](../../DESIGN-REVIEW-LOG.md) | 2026-04-20 entry (Multi-Tenant Shape B) | Rationale for `accounts/*/project_plans/*` layout (Dashboards does not deviate). |
| `docs/figma-export/src/app/pages/performance/DashboardDetailsPage.tsx` + `docs/figma-export/src/app/components/DashboardCanvas.tsx` | Entire files | Reference UX for the Details page and canvas mechanics. Rebuild in Soft Maximalism, not literal copy. |

## 7. Conventions and Constraints

### Data model
- A dashboard IS a `ProjectPlan` with `type="dashboard"`. No new root entity. Do not create a parallel `Dashboard` model.
- `dashboard_placements` is embedded on the plan doc, capped at 100 entries. Not a subcollection.
- `output_config` on `PlanTask` declares what outputs a task produces — drives the Pin-to-Dashboard picker and staleness detection.
- `(task_id, file_type)` is the placement's binding key. A single task can feed multiple placements (one per file type), but no two placements may share the same `(task_id, file_type)` pair.
- Placement layout uses **absolute pixel coordinates** with **8-pixel grid snap**; min tile size 64×64, max 4000×4000.

### Artifact resolution
- The resolver is the single source of truth for dashboard state. Frontend never resolves `(task_id, file_type)` → artifact client-side.
- Inline payload threshold: **≤64 KB** for text / Vega-Lite specs. Everything else uses 1-hour signed URLs.
- Status progression: `pending` (before first run) → `fresh` (after run produces expected artifact) → `stale` (after subsequent run fails to re-emit) → `disconnected` (task or `output_config` removed).

### API surface
- Dedicated `/api/v1/dashboards/*` namespace for dashboard-shaped reads (resolver) and canvas PUT.
- Plan edits, run triggers, and schedule config go through the existing **Project Tasks** and **Automations** endpoints. Do not duplicate those surfaces here.
- Default filter on A-PRD-01's Automations list is `type="freeform"` so dashboards don't appear as automations.

### Canvas interactions
- Drag and resize commit local state on `pointermove` for 60-fps feel; PUT fires via **500 ms debounce after drag-end**; `beforeunload` handler flushes pending PUT.
- Adding a placement from the task panel uses an empty-location heuristic (next free 320×240 rectangle on an 8-px grid).
- Placements PUT is last-write-wins. Concurrent edits by two users = final writer wins. Add `If-Match` ETag in a follow-up only if users report collisions.

### Security / Audit
- Every mutating endpoint uses DM-PRD-07's `require_role` and writes via `write_audit`.
- Placement PUT audit entries include a `diff_summary` of added / removed / moved placement ids.
- Signed URLs follow A-PRD-03's 1-hour expiry; frontend refetches the GET on 403.

### Frontend
- Branded types (`DashboardPlanId`) per CLAUDE.md C-5.
- URL structure: `/performance?tab=dashboards` (list), `/performance/dashboards/{plan_id}` (details), `/performance/dashboards/{plan_id}?runId={run_id}` (notification deep-link highlights a specific run).
- Client-side `type="dashboard"` filter defaults on the list (defense in depth; server enforces too).
- Polling cadence: 2 s while a run is in-flight; 30 s stale-time on the list; otherwise rely on user-triggered re-fetches.

### Testing
- Resolver unit tests cover all four status branches + inline threshold boundaries + Vega-Lite detection.
- DB-PRD-04 Playwright suites cover the five edge cases (disconnected, stale, pending, blob-expired, oversize-inline).
- Role-matrix test is parameterized to auto-cover new endpoints.
- Perf gates in CI: 100-placement GET p95 < 500 ms, canvas drag ≥ 55 fps, placements PUT p95 < 200 ms.

### Standard shape for a project PRD in [`projects/`](./projects/)

Each PRD follows the same 10-section structure as Project Tasks and Automations PRDs:

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
- DB-PRD-04 will append a "Shipped on YYYY-MM-DD — Verification Report" section below once the full component ships.

This PRD is read by the Dev Team agent during implementation planning (CLAUDE.md §Context Loading Sequence, Step 1). Keep it concise — every sentence should help the agent write better code or avoid mistakes.

-->
