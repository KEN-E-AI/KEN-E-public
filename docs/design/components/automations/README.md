# Automations — Product Requirements Document

> **Linear Team:** [KEN-E] Automations
> **Last Updated:** 2026-04-20
> **Status:** Active

## 1. Overview

The Automations component turns a one-shot `ProjectPlan` (owned by the Project Tasks component) into a **re-executable template** that can fire on a recurring schedule, be triggered manually, or be run end-to-end in a "test" mode that halts at human-in-the-loop (HITL) gates for inspection. A user marks a project as an automation by setting `save_as_automation=true`; each subsequent execution creates its own `PlanRun` document with its own task statuses, dispatches, and generated artifacts, while the parent `ProjectPlan` remains the immutable-ish recipe.

The component spans three architectural pillars — a **template/run split** (`PlanRun` as the execution record alongside `ProjectPlan` as the template, orchestrator taught to operate on either), a **recurrence engine** (a sibling Cloud Scheduler tick that finds automations whose `next_run_at <= now`, clones the template, and hands off to the `TaskOrchestrator`), and a **task artifact system** (GCS-backed storage with 30-day lifecycle, downstream-agent prompt injection of upstream outputs). On top of those, a test/dry-run mode and two frontend surfaces (list + DAG details page) give users a control loop to validate automations before turning them loose.

A developer reading only this section should understand: this component owns `PlanRun` / `TaskRunState` data, the `/api/v1/automations/*` API (template config, runs, test runs, artifacts), the `/workflows` page with its Automations tab and per-automation Details page, the recurring Cloud Scheduler tick, and the artifact store. It is the platform the Knowledge Graph session-end automation (KG-PRD-04) rides on as a system-owned template.

## 2. Architecture

```
┌────────────────────┐                                  ┌─────────────────────┐
│  ProjectPlan       │  save_as_automation=true,        │  PlanRun            │
│  (template)        │──recurrence_cron, recurrence_tz─▶│  (execution)        │
│                    │                                  │  triggered_by:      │
│  tasks[]           │  scheduler tick                  │    scheduled │      │
│  recurrence_cron   │  ──────────────────────▶         │    manual    │      │
│  next_run_at       │  (clones template into a run)    │    test      │      │
│                    │                                  │    system           │
└────────────────────┘                                  │  task_states[]      │
                                                        │  artifacts[] ───────┼──▶ GCS
                                                        └─────────────────────┘     (30d TTL)
                                                                  │
                                                                  ▼
                                                        TaskOrchestrator
                                                        (Project Tasks PR-PRD-04,
                                                         extended here for runs +
                                                         test mode + artifacts)
```

### 2.1 Key Directories

| Path | Purpose |
|------|---------|
| `api/src/kene_api/models/plan_run_models.py` | `PlanRun`, `TaskRunState`, `RunStatus` enum (A-PRD-01) |
| `api/src/kene_api/models/task_artifact_models.py` | `TaskArtifact` Pydantic + Firestore shape (A-PRD-03) |
| `api/src/kene_api/routers/automations.py` | `/api/v1/automations/*` — list, get, recurrence PATCH, runs, manual-trigger, test-run, cancel |
| `api/src/kene_api/routers/internal/automation_scheduler.py` | Cloud-Scheduler-driven `launch-due-automations` endpoint (A-PRD-02) |
| `api/src/kene_api/routers/artifacts.py` | Artifact list + download endpoints (A-PRD-03) |
| `api/src/kene_api/services/automation_run_engine.py` | Clone-template, compute-next-fire, inputs template substitution (A-PRD-02) |
| `api/src/kene_api/services/automation_query.py` | Filter + cursor-pagination helper (A-PRD-01) |
| `api/src/kene_api/services/artifact_store.py` | GCS upload, signed-URL generation, size validation (A-PRD-03) |
| `api/src/kene_api/repositories/firestore_artifact_repository.py` | Artifact metadata CRUD (A-PRD-03) |
| `app/adk/tools/builtin/attach_task_artifact.py` | ADK tool agents call to register outputs (A-PRD-03) |
| `frontend/src/pages/WorkflowsPage.tsx` | `/workflows` route with Automations tab (A-PRD-05) |
| `frontend/src/pages/AutomationDetailsPage.tsx` | `/workflows/automations/:planId` — DAG editor, schedule editor, test runs, Outputs tab (A-PRD-06) |
| `frontend/src/components/automations/` | DAG diagram, schedule modal, outputs tab, test-run controls (A-PRD-05 + 06) |
| `deployment/terraform/cloud_scheduler_automations.tf` | Sibling Cloud Scheduler job + SA + IAM (A-PRD-02) |
| `deployment/terraform/gcs_task_artifacts.tf` | `kene-task-artifacts-{env}` bucket + 30-day lifecycle rule + IAM (A-PRD-03) |
| `deployment/terraform/firestore_indexes_automations.tf` | Collection-scope composite indexes for list/runs filtering (A-PRD-01) |

### 2.2 Data Flow

1. **Template creation:** A user (via chat or UI) saves a `ProjectPlan` with `save_as_automation=true`, `recurrence_cron`, and `recurrence_timezone`. Persists to `accounts/{account_id}/project_plans/{plan_id}` (Project Tasks owns the base model; this component adds the automation fields).
2. **Recurring fire (A-PRD-02):** Cloud Scheduler cron fires `POST /api/v1/internal/scheduler/launch-due-automations` every minute. Inside a Firestore transaction per automation: re-read template, verify `next_run_at <= now`, compute the new next fire via `croniter(tz)`, update the template, and create a new `PlanRun` doc (`accounts/{account_id}/plan_runs/{run_id}`) with deep-cloned `task_states`. Hand off to `TaskOrchestrator.activate_plan(account_id, plan_id, run_id=run_id)` via `BackgroundTasks`.
3. **Manual fire (A-PRD-02):** `POST /api/v1/automations/{account_id}/{plan_id}/runs` with `triggered_by ∈ {"manual","system"}` and optional `inputs: dict` creates a run using the same engine. The `inputs` object is substituted into agent prompts via `{inputs.key}` template placeholders before dispatch.
4. **Test fire (A-PRD-04):** `POST .../runs/test` creates a run with `is_test=true`. Execution is identical to a production run except notifications carry `is_test=true` so the UI can badge them, and the run becomes cancellable. HITL halt behavior is unchanged from Calendar PRD-4.
5. **Artifact generation (A-PRD-03):** Agent tasks call the `attach_task_artifact(filename, content_base64, mime_type)` ADK tool during execution. The tool validates size (≤100 MB), sanitizes the filename, uploads to `gs://kene-task-artifacts-{env}/{account_id}/{plan_id}/{run_id}/{task_id}/...`, writes a metadata doc under `accounts/{account_id}/plan_runs/{run_id}/artifacts/{artifact_id}`, and records an audit entry.
6. **Downstream prompt injection (A-PRD-03):** When the orchestrator dispatches a task whose `depends_on` is non-empty, the prompt builder lists upstream artifacts — text under 64 KB inlined, everything else as filename + 1-hour signed URL.
7. **Frontend list (A-PRD-05):** `/workflows` loads the Automations tab. `GET /api/v1/automations/{account_id}` with filters (goal, campaign, tags, status, created_by, is_active) returns paginated results. `is_system=true` templates are filtered out of the default query.
8. **Frontend details (A-PRD-06):** `/workflows/automations/{plan_id}` renders the DAG via React Flow, a schedule editor modal, the Test Run button + progress, and a right-panel Outputs tab listing artifacts from past runs. System automations render read-only (HITL Mark Complete / Revision Requested still work on human tasks so reviewers can act on halted runs).

### 2.3 API Contracts

Owned endpoints:

| Endpoint | Method | Owner | Schema |
|----------|--------|-------|--------|
| `/api/v1/automations/{account_id}` | GET | A-PRD-01 | `PaginatedResponse<Automation>` (filters + cursor) |
| `/api/v1/automations/{account_id}/{plan_id}` | GET | A-PRD-01 | `Automation` (enriched with `last_run_*`, `next_run_at`) |
| `/api/v1/automations/{account_id}/{plan_id}/recurrence` | PATCH | A-PRD-01 | `{recurrence_cron, recurrence_timezone, is_active}` |
| `/api/v1/automations/{account_id}/{plan_id}/runs` | GET | A-PRD-01 | `PaginatedResponse<PlanRun>` |
| `/api/v1/automations/{account_id}/{plan_id}/runs/{run_id}` | GET | A-PRD-01 | `PlanRun` with `task_states` |
| `/api/v1/automations/{account_id}/{plan_id}/runs` | POST | A-PRD-02 | `{triggered_by, inputs?}` → new `PlanRun` |
| `/api/v1/automations/{account_id}/{plan_id}/runs/test` | POST | A-PRD-04 | `{inputs?}` → new `PlanRun` with `is_test=true` |
| `/api/v1/automations/{account_id}/{plan_id}/runs/{run_id}/cancel` | POST | A-PRD-04 | cancels in-flight run |
| `/api/v1/automations/{account_id}/{plan_id}/runs/{run_id}/tasks/{task_id}/artifacts` | GET | A-PRD-03 | artifact list |
| `/api/v1/automations/{account_id}/{plan_id}/tasks/{task_id}/artifacts/recent` | GET | A-PRD-03 | recent-runs artifact list (for Outputs tab) |
| `/api/v1/automations/{account_id}/{plan_id}/runs/{run_id}/artifacts/{artifact_id}/download` | GET | A-PRD-03 | 1-hour signed URL |
| `/api/v1/schedules/preview` | POST | A-PRD-02 | Expand a schedule config into occurrence dates for a window (≤90 days). Pure read — used by the Calendar grid (task-level recurrence) and the Activity-form UI |
| `/api/v1/automations/{account_id}/schedules/upcoming` | GET | A-PRD-02 | List automations with scheduled occurrences in a window, for the Calendar "Projects in view" panel |
| `/api/v1/internal/scheduler/launch-due-automations` | POST | A-PRD-02 | OIDC-auth only; sibling to Project Tasks `launch-due-tasks` |

Schema source of truth: `api/src/kene_api/models/plan_run_models.py` + `task_artifact_models.py` (Pydantic), mirrored TypeScript branded types in `frontend/src/types/`. The `ProjectPlan` base model and extension fields (`save_as_automation`, `recurrence_cron`, plus `type: freeform|dashboard`, `extension_id`, `goal_id` added alongside the Figma-frontend alignment work) are owned by Project Tasks PR-PRD-01 and extended in A-PRD-01.

### 2.4 Key Abstractions

| Abstraction | Path | Purpose |
|-------------|------|---------|
| `PlanRun` / `TaskRunState` / `RunStatus` | `api/src/kene_api/models/plan_run_models.py` | Execution record — the single source of truth for a run's status, dispatches, and task-level state. Never reads from the template once a run is in flight. |
| `AutomationRunEngine` | `api/src/kene_api/services/automation_run_engine.py` | Clone-template + compute-next-fire + idempotent `next_run_at` write inside one Firestore transaction; also owns `{inputs.*}` prompt-template substitution |
| `TaskOrchestrator` (extended) | `api/src/kene_api/services/task_orchestrator.py` (Project Tasks) | Gains optional `run_id` + `is_test` parameters. `run_id is None` → legacy template behavior; `run_id is not None` → status reads/writes target `PlanRun.task_states[*]`. |
| `TaskArtifact` | `api/src/kene_api/models/task_artifact_models.py` | Artifact metadata + 100 MB size cap + `sha256` for content addressing |
| `attach_task_artifact` (ADK tool) | `app/adk/tools/builtin/attach_task_artifact.py` | Agent-callable entry point — resolves `account_id/plan_id/run_id/task_id` from `tool_context.state` |
| `is_system` flag (consumed) | `ProjectPlan` on Project Tasks PR-PRD-01 | Consumed here to filter the list page, render the details page read-only, and reject recurrence PATCH on system plans. Full cross-component enforcement table: [`../data-management/README.md` §7.6](../data-management/README.md#76-is_system-system-plan-convention). |
| `inputs: dict` on `PlanRun` | A-PRD-01 + A-PRD-02 | Caller-provided context (e.g. `session_id`) substituted into agent prompts at dispatch. Size cap 100 KB serialized. |

## 3. Component Dependencies

### 3.1 Depends On

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **Project Tasks (all 6 PRDs)** | **Hard prerequisite — must ship before any A-PRD starts.** Provides `ProjectPlan` / `PlanTask` base models, the `TaskOrchestrator` service this component extends, the `/api/v1/plans/*` CRUD surface, the Calendar frontend's `ActivityDetailPanel` (reused on the Details page), and the Cloud Scheduler infrastructure the sibling `launch-due-automations` tick reuses. | [`../project-tasks/README.md`](../project-tasks/README.md) |
| **Data Management — DM-PRD-00 (Migration Foundation)** | **Hard prerequisite for A-PRD-01.** Establishes the Shape B convention (`accounts/{account_id}/plan_runs/…`) and ships the two `plan_runs` collection-scope composite indexes (`template_plan_id ASC, started_at DESC` and `template_plan_id ASC, is_test ASC, started_at DESC`) that the runs-list endpoint consumes. | [`../data-management/projects/DM-PRD-00-migration-foundation.md`](../data-management/projects/DM-PRD-00-migration-foundation.md) |
| **Data Management — DM-PRD-05 (Deletion Sweep Rewrite)** | **Hard prerequisite for A-PRD-01.** Rewrites the enumerated account-deletion sweep in `routers/accounts.py:968-997` as `firestore.recursive_delete(accounts/{account_id})` so the new `plan_runs` subcollection and its nested `artifacts/` subcollection (A-PRD-03) are automatically covered on account deletion. | [`../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md`](../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md) |
| Notifications (existing) | `create_notification` + `Task Ready` category. A-PRD-04 adds an `is_test=true` field to the notification payload; no new enum value needed. | `api/src/kene_api/services/notification_service_v2.py` |
| Google Cloud Storage | A-PRD-03 provisions `kene-task-artifacts-{env}` with a 30-day lifecycle rule and generates 1-hour signed URLs. | `app/utils/gcs.py` (existing helpers) |
| Cloud Scheduler (GCP) | A-PRD-02 provisions a sibling per-minute cron under the same SA as Project Tasks PR-PRD-06. | `deployment/terraform/` |
| ADK tool registry | A-PRD-03 registers `attach_task_artifact` under an `artifacts` capability and adds that capability to agents that produce output. | `app/adk/tools/registry/config/tools.yaml` |
| Account / Auth | `check_strategy_access`-equivalent dependency, scoped per account. | `api/src/kene_api/auth/` |

### 3.2 Depended On By

| Component | Dependency |
|-----------|------------|
| Knowledge Graph (`docs/design/components/knowledge-graph/`) | KG-PRD-04 (session-end automation) ships as an `is_system=true` project plan that runs on this platform. Consumes `PlanRun.inputs` (for `session_id`), `triggered_by="system"`, the `Outputs` tab for reviewer approval, and the read-only rendering on the Details page. |

## 4. Design System References

| Document | Sections | When to Read |
|----------|----------|--------------|
| Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) | Workflows page (Automations tab), Automation Details (DAG diagram, schedule editor, Outputs tab) | When implementing A-PRD-05 (list) or A-PRD-06 (details). |
| `frontend/CLAUDE.md` | CSS architecture, component library | Before adding new visual components. |
| `frontend/src/pages/CalendarPage.tsx` (Project Tasks PR-PRD-03) | Filter bar + list-view pattern; branded types (`PlanId`, `AccountId`); service-layer pattern | Starting the list page (A-PRD-05) or the details page (A-PRD-06). |
| React Flow docs ([reactflow.dev](https://reactflow.dev/)) | Custom node components, draggable edges, auto-layout | When building the DAG diagram in A-PRD-06 (also pair with `dagre` for auto-layout). |

## 5. Project Index

The component's work is split across **7 independently shippable project PRDs** under [`projects/`](./projects/). The split follows the same logic as Project Tasks: ship a foundation that publishes the data contract first, then run independent pieces in parallel. Artifacts (A-PRD-03) and test mode (A-PRD-04) each get their own PRD — the artifact system is large enough (GCS bucket, lifecycle policy, ADK tool, prompt injection) and test mode is architecturally distinct from recurring scheduling, with its only non-trivial coupling being test mode's dependency on the artifact system for inspectable outputs.

### 5.1 Dependency graph

```
A-PRD-01: Data Model & API ──┬──> A-PRD-02: Recurring Scheduler ──┐
  (BLOCKING — ships first)   ├──> A-PRD-03: Task Artifact System ─┤
                             ├──> A-PRD-05: List Page ────────────┤──> A-PRD-07:
                             └──> A-PRD-06: Details Page ─────────┤     Integration Testing
                                                                  │     (closes out)
                             A-PRD-03 ──> A-PRD-04: Test Mode ────┘
```

### 5.2 Projects

| # | Project PRD | Owner team | Blocked by | Parallel with | Est. |
|---|-------------|------------|------------|---------------|------|
| 01 | [Data Model & API Extensions](./projects/A-PRD-01-data-model-and-api.md) | Backend (foundation) | PR-PRD-01, DM-PRD-00, DM-PRD-05 | — | 2–3 days |
| 02 | [Recurring Scheduler & Run Engine](./projects/A-PRD-02-recurring-scheduler.md) | Backend / Infra | A-PRD-01, Project Tasks PR-PRDs 04 + 06 | 03, 05, 06 | 3 days. Also ships the public `POST /v1/schedules/preview` and `GET /v1/automations/{account_id}/schedules/upcoming` endpoints consumed by the Calendar page. |
| 03 | [Task Artifact System](./projects/A-PRD-03-task-artifact-system.md) | Backend + Agent | A-PRD-01, Project Tasks PR-PRDs 02 + 04 | 02, 05, 06 | 3–4 days |
| 04 | [Test / Dry-Run Mode](./projects/A-PRD-04-test-dry-run-mode.md) | Backend | A-PRD-01, A-PRD-03, Project Tasks PR-PRD-04 | 05, 06 | 2 days |
| 05 | [Automations List Page](./projects/A-PRD-05-automations-list-page.md) | Frontend | A-PRD-01, Project Tasks PR-PRD-03 | 02, 03, 06 | 2 days |
| 06 | [Automation Details Page](./projects/A-PRD-06-automation-details-page.md) | Frontend | A-PRD-01, Project Tasks PR-PRD-03 (soft: A-PRDs 03 + 04) | 02, 03, 05 | 4–5 days |
| 07 | [Integration Testing & Polish](./projects/A-PRD-07-integration-testing-and-polish.md) | QA + first-finished team | A-PRDs 01–06 | — | 1–2 days |

### 5.3 Cross-PRD coordination points

Three touchpoints do not fit cleanly inside one PRD and need an owning team to consciously sync:

- **Orchestrator signature change (A-PRD-02 ↔ Project Tasks PR-PRD-04):** `TaskOrchestrator.activate_plan` and `on_task_status_change` grow an optional `run_id` (A-PRD-02) and optional `is_test` (A-PRD-04). Additive — no breaking change for existing callers. The Automations PRD owners drive the change; the Project Tasks PR-PRD-04 team reviews.
- **Right-panel Outputs tab (A-PRD-06 ↔ Project Tasks PR-PRD-03):** The Details page reuses `ActivityDetailPanel` and adds a new `"outputs"` tab that appears when the selected task is agent-assigned AND the page is the Automation Details page. Add an `availableTabs` prop or a slot pattern; coordinate with the PR-PRD-03 owners.
- **HITL notification payload (A-PRD-04 ↔ Project Tasks PR-PRD-04):** Reuses the existing `"Task Ready"` notification category; A-PRD-04 adds a single `is_test: bool` field to the payload data so the frontend can badge test-run notifications.

### 5.4 Recommended workflow

1. **Prerequisite sprint(s):** Data Management DM-PRD-00 (ships the `plan_runs` indexes) and DM-PRD-05 (makes `recursive_delete` cover the new subcollections) merge; Project Tasks PR-PRDs 01–06 ship (including the `is_system` and `inputs`-adjacent adds folded in for Knowledge Graph). No automations work starts before A-PRD-01's prerequisites are merged.
2. **Sprint 1 (foundation):** Backend ships A-PRD-01. All other teams stub against the published Pydantic schema and TypeScript types.
3. **Sprints 2–3 (parallel):** A-PRDs 02, 03, 05, 06 run in parallel. A-PRD-04 starts mid-sprint once A-PRD-03 lands (it needs artifacts to be the point of inspecting test runs).
4. **Sprint 4 (close-out):** A-PRD-07 runs end-to-end tests, closes out edge-case suites (DST, overlap, downtime backfill, artifact lifecycle), and appends a verification report to this README.

## 6. Global Document References

| Document | Relevant Sections | Why |
|----------|-------------------|-----|
| [`../project-tasks/README.md`](../project-tasks/README.md) | §2 (Architecture), §5 (Project Index) | Automations extends the base `ProjectPlan` / `PlanTask` data model and the `TaskOrchestrator` service owned there. Read this before starting any A-PRD. |
| [`../data-management/README.md`](../data-management/README.md) | §2 (Architecture), §5.3 (`plan_runs` indexes) | Shape B path convention and the composite-index registry that `accounts/*/plan_runs` lives under. |
| [`../data-management/multi-tenant-migration-plan.md`](../data-management/multi-tenant-migration-plan.md) | Phase 0 (indexes), Phase 5 (PRD + doc edits) | Confirms the Shape B paths the automations data model uses (`accounts/{account_id}/plan_runs/...`). |
| `docs/KEN-E-System-Architecture.md` | Agent dispatch, Tool discovery | When implementing A-PRD-03 (new ADK tool) and the orchestrator hand-off in A-PRD-02. |
| [`../agentic-harness/README.md`](../agentic-harness/README.md) | §2 Architecture, §2.4 Key Abstractions | When wiring the ADK tool + capability into the agent registry. |
| [`../../DESIGN-REVIEW-LOG.md`](../../DESIGN-REVIEW-LOG.md) | 2026-04-20 entry (Multi-Tenant Shape B) | Rationale for the current `accounts/*/plan_runs/*` and `accounts/*/plan_runs/{run_id}/artifacts/*` path layout. |

## 7. Conventions and Constraints

### Data model
- `ProjectPlan` is the **template**; `PlanRun` is the **execution record**. The orchestrator never reads from the template during a run — it reads and writes `PlanRun.task_states[*]` exclusively when a `run_id` is present.
- `recurrence_cron` is a 5-field cron expression (no seconds, no year). `recurrence_timezone` is an IANA name. Both are validated on the model via `croniter.is_valid` + `zoneinfo.ZoneInfo`.
- `inputs: dict | None` on `PlanRun` is caller-opaque JSON, max 100 KB serialized. Surfaced to agent prompts via `{inputs.<simple_key>}` or `{inputs.<key>.<nested_key>}` (two levels max) substitution before dispatch.
- `triggered_by` values: `"scheduled"` (Cloud Scheduler tick), `"manual"` (user clicked Run Now), `"test"` (user clicked Test Run), `"system"` (platform services like KG-PRD-04's sweeper).
- `is_test=true` runs save real artifacts, hit real agents, incur real costs — "test" framing is about validating outputs, not about sandboxing side effects. Document this prominently in any UX copy.
- `template_version` is snapshotted into the `PlanRun` at trigger time; edits to the template mid-run do not affect the in-flight run.
- No backfill replay: on server-downtime recovery, each automation fires **once** for "now" and schedules forward from there; missed slots are not replayed.

### Firestore layout (Shape B)

Component-owned paths (the base `project_plans` subcollection is owned by Project Tasks; this component extends it and adds the run + artifact subcollections):

- `accounts/{account_id}/project_plans/{plan_id}` — template (A-PRD-01 extends the base model with automation fields)
- `accounts/{account_id}/plan_runs/{run_id}` — per-execution doc
- `accounts/{account_id}/plan_runs/{run_id}/artifacts/{artifact_id}` — artifact metadata (A-PRD-03)
- `accounts/{account_id}/project_plan_audit/{audit_id}` — existing; new entry types for run lifecycle events (shape owned by DM-PRD-07)

Query pattern: the list page uses collection-scope composite indexes (`save_as_automation, is_system, <filter>, updated_at`); the recurring scheduler tick uses a collection-group index on `project_plans`. The full index registry and cross-account pattern are documented in [`../data-management/README.md` §7.7](../data-management/README.md#77-cross-account-query-pattern).

### GCS layout
- `gs://kene-task-artifacts-{env}/{account_id}/{plan_id}/{run_id}/{task_id}/{artifact_id}_{sanitized_filename}`
- 30-day lifecycle deletion rule; 100 MB size cap per artifact; signed URLs with 1-hour expiry.

### `is_system` semantics

Defined in Project Tasks; enforced across this component by A-PRD-01 (recurrence PATCH `403`), A-PRD-05 (list-page filter default), and A-PRD-06 (details-page read-only + HITL carve-out). The canonical cross-component enforcement table is in [`../data-management/README.md` §7.6](../data-management/README.md#76-is_system-system-plan-convention) — update that table rather than this section when a new consumer PRD touches the flag.

### Frontend
- Terminology mapping to Figma: **"Workflow" → Automation** (the Workflows page holds Automations as one tab).
- URL structure: `/workflows?tab=automations&campaign=Spring` for list state; `/workflows/automations/{plan_id}?run={run_id}&task={task_id}` for Details deep-links.
- Client-side `is_system` filter defaults to `false` on every list query (defense in depth; server enforces too).

### Testing
- DST transitions (spring-forward, fall-back) are exercised in integration tests via `croniter` + IANA tz.
- Idempotency of the scheduler tick is tested via two-concurrent-invocation simulation (Firestore transaction on `next_run_at` is the canonical guard).
- Artifact lifecycle is tested against a 1-day-TTL test bucket or mocked GCS lifecycle clock.
- The `now` override on the scheduler endpoint enables time-travel tests without wall-clock waiting.

### Standard shape for a project PRD in [`projects/`](./projects/)
Each PRD follows the same 10-section structure as the Project Tasks PRDs:

1. Context — problem this PRD solves
2. Scope — explicit in/out
3. Dependencies — other PRDs, files, services
4. Data contract — Pydantic / TypeScript types owned or consumed
5. Implementation outline — files to create / modify (table)
6. API contract — endpoints (where applicable)
7. Acceptance criteria — what "done" means
8. Test plan — unit / integration / E2E coverage
9. Risks & open questions
10. Reference — links back to sibling PRDs, Project Tasks PRDs, Figma

---

<!-- PRD MAINTENANCE NOTES

Updating this PRD:
- When a new feature-parent is created in Linear: add it to §5 Project Index
- When a feature-parent is completed: update its status in §5
- When architecture changes (new directories, new abstractions, new API endpoints): update §2
- When a new cross-component dependency is introduced: update §3
- When a new Figma spec or design doc section becomes relevant: update §4
- A-PRD-07 will append a "Status: shipped" section at the top of §5.4 with a verification-report link once the full set ships.

This PRD is read by the Dev Team agent during implementation planning. Keep it concise — every sentence should help a dev write better code or avoid mistakes.
-->
