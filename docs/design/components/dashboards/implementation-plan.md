# Dashboards — Implementation Plan

**Status:** Draft — 2026-04-22
**Owner:** Dashboards component team (TBD)

---

## 1. What a Dashboard is

A Dashboard is a `ProjectPlan` with `type="dashboard"` that carries an additional **canvas** — an ordered set of `DashboardPlacement` entries that bind plan tasks to visual widgets on a free-form 2D surface.

Three facts shape the design:

1. **A dashboard IS a plan.** The data lives in `accounts/{account_id}/project_plans/{plan_id}`, the same subcollection Project Tasks and Automations write to. Dashboards add fields; they do not introduce a new root entity.
2. **A dashboard runs like an automation.** "Run Dashboard" invokes `POST /api/v1/automations/{account_id}/{plan_id}/runs` (A-PRD-02) and produces a normal `PlanRun`. The dashboard canvas resolves its widgets against the **latest `PlanRun`**; re-running produces fresh artifacts and the canvas refreshes.
3. **Widgets are bound to tasks, not to artifact IDs.** A placement references `(task_id, file_type)`. When a new run completes, the dashboard re-resolves `(task_id, file_type)` → `latest_run.task_states[task_id].artifacts[file_type]`. If a task no longer produces the expected file type (task was edited, `output_config.enabled=false`), the placement is rendered as **disconnected**.

## 2. What exists today (before Dashboards)

This component does not build from scratch. Five upstream components already supply most of the machinery:

| Upstream | What it gives us |
|---|---|
| **PR-PRD-01** | `ProjectPlan` + `PlanTask` models, DAG validator, CRUD under `/api/v1/plans/*`, versioning + audit pattern. |
| **PR-PRD-04** | `TaskOrchestrator` — advances a run's tasks as statuses change. A dashboard run uses the same orchestrator. |
| **A-PRD-01** | `ProjectPlan.type: freeform \| dashboard` enum, `PlanRun` model, `TaskRunState`, `is_active` and schedule fields. |
| **A-PRD-02** | Manual run trigger (`POST /automations/{account_id}/{plan_id}/runs`), recurring scheduler (dashboards can be scheduled), `schedule/preview` endpoint. |
| **A-PRD-03** | `TaskArtifact` model, GCS storage at `gs://kene-task-artifacts-{env}/{account_id}/{plan_id}/{run_id}/{task_id}/...`, `attach_task_artifact` ADK tool, signed-URL download, 100 MB cap, 30-day lifecycle. |

What's **missing** and needed for Dashboards:

- A way for a task to **declare** what outputs it produces (`output_config` on `PlanTask`) — drives the "Pin to Dashboard" picker and staleness detection.
- A **canvas layout** on the plan (`dashboard_placements` on `ProjectPlan`) — the set of widgets on the dashboard.
- A server-side **artifact resolver** that maps `(task_id, file_type)` → the latest matching `OutputFile` with staleness / disconnected status — so the frontend doesn't re-implement this logic per page.
- A **`/api/v1/dashboards/*`** API surface — create a dashboard, save the canvas layout, fetch a fully-resolved dashboard with artifacts inlined where small and signed-URL'd where large.
- The **Dashboards tab** on the Performance page and the **Dashboard Details** frontend — free-form drag/resize canvas, widget renderers for text / Vega-Lite / table / file, pin-to-dashboard from the task graph, Run button.

## 3. Data-model extensions

### 3.1 `ProjectPlan` — add canvas layout

When `type="dashboard"`, the plan carries a `dashboard_placements` list describing the canvas. Each placement is a minimal binding plus layout metadata:

```python
class DashboardPlacement(BaseModel):
    placement_id: str                           # UUID — stable across edits
    task_id: str                                # references a PlanTask.task_id in this plan
    file_type: OutputFileType                   # "text" | "visualization" | "csv" | "image" | "document" | ...
    # Canvas layout (free-form absolute positioning, 8-pixel grid snap)
    x: int
    y: int
    w: int
    h: int
    # Optional presentation overrides (apply at render time)
    view_override: Literal["bar", "line", "area", "point", "arc", "table"] | None = None
    color: str | None = None
    show_data_labels: bool | None = None
```

Rules:
- A placement MUST reference a `task_id` that exists in the plan's `tasks[]`.
- The referenced task SHOULD have `output_config.enabled=true` and `file_type` in `output_config.expected_file_types`. A violation is not a create-time error (the task may be edited later); it surfaces as **disconnected** status on the resolved GET response.
- Layout coordinates are plain pixels; the frontend snaps to an 8-px grid at interaction time but persists the snapped values.
- `dashboard_placements` is a plain array on the plan doc (embedded), not a subcollection. Cap: 100 placements per dashboard.

### 3.2 `PlanTask` — add `output_config`

A task may declare what outputs it emits. This drives:
- The "Pin to Dashboard" picker on the Details page (lists terminal-ish tasks with `output_config.enabled=true`).
- The staleness / disconnected resolver (an expected file type that didn't materialize is "pending" after a run completes).

```python
class OutputConfig(BaseModel):
    enabled: bool = False
    expected_file_types: list[OutputFileType] = []

class PlanTask(BaseModel):
    # ... existing fields (PR-PRD-01, PR-PRD-07)
    output_config: OutputConfig | None = None
```

`OutputFileType` mirrors the frontend inventory: `text`, `visualization`, `csv`, `image`, `document`, `json`, `html`, `video`, `audio`, `other`. Agents call `attach_task_artifact(filename, content, mime_type)` (A-PRD-03) as today — `output_config` does not change how artifacts are written, only declares intent.

### 3.3 Artifact resolution model

Given a dashboard's placements + its latest `PlanRun`, the resolver produces one `DashboardArtifact` per placement:

```python
class DashboardArtifact(BaseModel):
    placement_id: str
    task_id: str
    file_type: OutputFileType
    status: Literal["fresh", "stale", "disconnected", "pending"]
    # Inline payload for small artifacts (≤64 KB); None for large artifacts
    inline_payload: dict | None = None          # {"content": "...", "spec": {...}, "rows": [...]} shape varies by file_type
    # Signed URL for large artifacts (csv, image, document, video, audio, other)
    download_url: str | None = None             # 1-hour signed URL per A-PRD-03
    updated_at: datetime | None                 # when the referenced artifact was produced
    artifact_id: str | None                     # opaque ref to the underlying TaskArtifact doc
```

Status rules:
- **fresh** — artifact exists and was produced in the latest completed PlanRun.
- **stale** — artifact exists but was produced in a prior run (the dashboard has been re-run and the referenced task did not re-emit this file type on the latest run).
- **disconnected** — the referenced task no longer exists, or its `output_config.enabled=false`, or `file_type ∉ output_config.expected_file_types`.
- **pending** — `output_config` declares this file type but the latest run has no matching artifact (task hasn't completed, or agent did not emit it).

Inlining threshold is the same as A-PRD-03's orchestrator-prompt injection: ≤64 KB of text or Vega spec is inlined; everything else is a signed URL with 1-hour expiry.

## 4. API surface

A dedicated namespace parallel to Automations:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/dashboards/{account_id}` | List dashboards. Filters: `is_active`, `tags[]`, `cursor`, `page_size`. Server filters `type="dashboard"`. |
| `POST` | `/api/v1/dashboards/{account_id}` | Create. Body: `{title, description?, tags?}`. Server constructs a `ProjectPlan` with `type="dashboard"`, empty `tasks`, empty `dashboard_placements`. Returns the new plan. |
| `GET` | `/api/v1/dashboards/{account_id}/{plan_id}` | Fetch a dashboard with **resolved artifacts**. Returns `{plan: ProjectPlan, latest_run: PlanRun \| None, artifacts: DashboardArtifact[]}`. |
| `PUT` | `/api/v1/dashboards/{account_id}/{plan_id}/placements` | Replace the full canvas layout. Body: `DashboardPlacement[]`. Last-write-wins — no per-placement granularity. |
| `DELETE` | `/api/v1/dashboards/{account_id}/{plan_id}` | Soft-delete (`is_active=false`) via the PR-PRD-01 delete path. |

**Not owned here** (use the upstream endpoints directly):
- Plan edits (tasks, DAG, title, schedule) → `PUT /api/v1/plans/{account_id}/{plan_id}` (PR-PRD-01) or `PATCH /api/v1/plans/{account_id}/{plan_id}/tasks/{task_id}`. The Dashboard Details page calls these directly.
- Run a dashboard → `POST /api/v1/automations/{account_id}/{plan_id}/runs` (A-PRD-02, `triggered_by="manual"`).
- Cancel a run → `POST /api/v1/automations/{account_id}/{plan_id}/runs/{run_id}/cancel` (A-PRD-04).
- Schedule config → `PATCH /api/v1/automations/{account_id}/{plan_id}/recurrence` (A-PRD-01).

Rationale: dashboards, automations, and plans all edit the same `ProjectPlan`. Duplicating the plan-editing API under `/dashboards/` would create three places to keep in sync. The dedicated dashboards namespace is reserved for dashboard-shaped reads (the resolver) and the canvas PUT.

## 5. Interaction with existing components

### 5.1 Automations list separation

`A-PRD-05` (Automations list) currently defaults `is_system=false`. It will also need to default `type="freeform"` so that dashboards don't appear in the Automations list. A small update to `A-PRD-01`'s list endpoint — same pattern, new default filter.

### 5.2 Shared frontend components

The Dashboard Details page reuses three Automations frontend components:
- `AutomationGraph` — React Flow DAG visualization.
- `AutomationTaskPanel` — task-edit sidebar.
- `AutomationSchedulePanel` — schedule-edit modal.

The "Pin to Dashboard" action is added to `AutomationTaskPanel`, conditional on the containing page being a Dashboard Details page (not the Automation Details page). A small prop on the panel, wired by each consumer.

### 5.3 Artifact lifecycle

Dashboards do not introduce new artifact storage. Every artifact on a dashboard was produced by a normal run via `attach_task_artifact` and lives in the same GCS bucket with the same 30-day TTL. If a user opens a dashboard whose latest run is >30 days old, the resolver marks every placement **stale** and the download URL still works (signed URL is fetched on demand, but the blob may already be expired — surface a graceful error).

### 5.4 Role-based access

All dashboard endpoints use DM-PRD-07's `require_role` gate:
- `viewer` — GET only.
- `editor` — POST / PUT / DELETE / plan edits / run triggers.
- `approver` / `admin` — same as editor (no approval-sensitive transitions unique to dashboards).

All mutations write an `AuditEntry` via `write_audit`, including placement edits.

## 6. Phasing

Four PRDs, matching the Automations breakdown:

### DB-PRD-01 — Data Model & API

**Delivers:** `DashboardPlacement`, `OutputConfig`, `OutputFileType` Pydantic models; `dashboard_placements` extension on `ProjectPlan`; `output_config` extension on `PlanTask`; new `/api/v1/dashboards/*` router; `DashboardArtifactResolver` service that walks `(placement → task → latest run → OutputFile)` producing `DashboardArtifact[]` with inlined small payloads and signed URLs for large. Also the small A-PRD-01 update to filter `type="freeform"` on the Automations list by default.

**Blocked by:** PR-PRD-01, A-PRD-01, A-PRD-03, DM-PRD-05, DM-PRD-07.

**Blocks:** DB-PRD-02, DB-PRD-03.

**Effort:** 2–3 days.

### DB-PRD-02 — Dashboards Tab & List

**Delivers:** The Dashboards tab on the Performance page (`/performance/dashboards`, the 2nd tab per the figma export — slot reserved by PE-PRD-01), the list view (one row per dashboard with title, schedule, last-run, status badge), the "New Dashboard" create flow (title + description modal → `POST /dashboards` → redirect to Details), the empty state. Uses TanStack Query against the DB-PRD-01 API.

**Blocked by:** DB-PRD-01, **PE-PRD-01** (Performance page shell — owns the Dashboards tab slot, route, placeholder, and feature flag; this PRD swaps PE-PRD-01's `<DashboardsTabPlaceholder />` for the real `<DashboardsSection />`). UI-PRD-07 — the original presentation-only redesign — is **retired and subsumed by PE-PRD-01**.

**Blocks:** DB-PRD-03 (shares the tab shell), DB-PRD-04.

**Effort:** 2 days.

### DB-PRD-03 — Dashboard Details & Canvas

**Delivers:** The Dashboard Details page (`/performance/dashboards/{plan_id}`) with split layout (task graph on top, canvas on bottom, task panel on right). Free-form absolute-positioned canvas with drag-to-move / corner-resize, 8-px grid snap. Four widget renderers: text (markdown), visualization (react-vega), table (CSV parsed client-side), file (fallback with download link). "Pin to Dashboard" button on the task panel. Run button invokes A-PRD-02's manual trigger; polling on the latest run until terminal. Schedule modal invokes A-PRD-01's recurrence PATCH. Placement PUT debounced 500 ms after drag-end.

**Blocked by:** DB-PRD-01, DB-PRD-02, A-PRD-06 (consumes the **shared `frontend/src/components/dag/TaskGraph.tsx`** + `AutomationTaskPanel`, `AutomationSchedulePanel` published by A-PRD-06 — no fork).

**Blocks:** DB-PRD-04.

**Effort:** 4–5 days.

### DB-PRD-04 — Integration Testing & Polish

**Delivers:** E2E Playwright suite (create → add task with `output_config` → pin → run → verify canvas refresh). Edge-case tests: disconnected placement (task deleted), stale placement (task didn't re-emit this run), pending placement (task hasn't completed), 100-placement performance, large-CSV widget. Verifies the Automations list excludes `type="dashboard"` entries. Appends a verification report to the component README.

**Blocked by:** DB-PRD-01, DB-PRD-02, DB-PRD-03.

**Effort:** 1–2 days.

## 7. Dependency graph

```
                       ┌─────────────────┐
                       │   PR-PRD-01     │ (ProjectPlan + PlanTask base)
                       └───┬─────────┬───┘
                           │         │
                ┌──────────┘         └───────────┐
                ▼                                ▼
         ┌──────────────┐               ┌────────────────┐
         │  A-PRD-01    │ (type enum)   │   DM-PRD-07    │ (role gate, audit)
         │  A-PRD-03    │ (artifacts)   └───────┬────────┘
         └──────┬───────┘                       │
                │                               │
                └───────┬───────────────────────┘
                        ▼
                 ┌────────────────┐
                 │   DB-PRD-01    │  Data model + API + resolver
                 │  (BLOCKING)    │
                 └───┬────────┬───┘
                     │        │
            ┌────────┘        └────────┐
            ▼                          ▼
     ┌────────────┐             ┌────────────────┐
     │  DB-PRD-02 │             │   A-PRD-06     │ (shared React Flow components)
     │   Tab+List │             └────────┬───────┘
     └──────┬─────┘                      │
            │                            │
            └──────────┬─────────────────┘
                       ▼
                ┌────────────────┐
                │   DB-PRD-03    │  Details page + canvas + widgets
                └───────┬────────┘
                        │
                        ▼
                ┌────────────────┐
                │   DB-PRD-04    │  Integration testing
                └────────────────┘
```

## 8. Explicit non-goals for this release

- **Dashboard templates / extensions.** The Figma frontend has an Extensions concept (`extensionId` field) for pre-built dashboard templates. Extensions are a separate backend concern (covered by a future `extensions/` component, out of scope here). A dashboard created today is always user-authored.
- **Real-time refresh during runs.** The canvas shows the latest *completed* run's artifacts. While a run is in-flight, widgets display the previous run's artifacts (marked stale) plus per-task progress on the DAG visualization. A WebSocket / SSE stream for live artifact hydration is a future enhancement.
- **Separate Test Run button.** Dashboards ship with one Run button. A-PRD-04's `is_test` mode is an Automations affordance for validating recipes before enabling recurring firing; dashboards produce real artifacts on every run, so the distinction doesn't apply at the UX layer. The underlying `/runs/test` endpoint still works for anyone who needs it programmatically.
- **Widget types beyond the four listed.** No KPI tiles, no iframe embeds, no image galleries. If a file type doesn't match one of the four renderers, the **file fallback** widget offers a download link.
- **Drill-down / cross-filtering.** Widgets are independent. Clicking a point in one visualization does not filter another.
- **Sharing / access control per dashboard.** A dashboard is visible to everyone with access to the account; there's no per-dashboard viewer list. Cross-account sharing is out of scope.
- **Export / PDF snapshot.** No "export as PDF" or "email me the dashboard" — the dashboard is always live.
- **Undo / revision history on the canvas.** Layout changes are persisted last-write-wins. Plan edits are versioned (PR-PRD-01) but canvas layout changes are not separately versioned in v1.
- **Cascade-delete placements when a referenced task is deleted.** Placements are preserved and surfaced by the resolver with `status="disconnected"` so the user can re-point them.

These become discovery items as Dashboards gains usage, not launch requirements.

## 9. Risks

| Risk | Mitigation |
|---|---|
| Canvas PUT debounce loses the last drag if the user closes the tab immediately after dropping | `beforeunload` handler flushes the pending PUT; worst case re-open with slightly stale layout. |
| 30-day artifact TTL vs. infrequent dashboard re-runs | Resolver marks every placement stale beyond the TTL; download URL returns a 404. Add a clear "this artifact has expired — re-run the dashboard" message. |
| Large Vega specs (>64 KB) exceed the inline threshold | Rare in practice (most specs are <10 KB). If exceeded, serve via signed URL like any other large artifact; react-vega fetches it. |
| `output_config` declared but agent doesn't emit the declared type | Resolver marks the placement **pending** with a hint ("task completed but did not emit visualization"). Operators can diagnose from the Automation Details Outputs tab. |
| Drag operations generate chatty PUTs | 500 ms debounce on drag-end + final flush on `pointerup`. Single PUT per drag gesture. |
| Two users edit the same dashboard simultaneously | Last-write-wins on the placements PUT. Add `If-Match` ETag in a follow-up if users report collisions. |
| Dashboard with 100 placements × 50 tasks × 20 runs stored in Firestore | Run-outputs are capped (A-PRD-01 keeps the last N per task); resolver only reads the latest run doc. O(placements) Firestore reads per GET, bounded at 100. |

## 10. Open questions

1. **Canvas unit system.** Absolute pixels vs. responsive percent. Pixels match the Figma frontend today; responsive is a future enhancement. Document: pixels are the spec, frontend handles responsive scaling.
2. **Per-placement refresh vs. whole-dashboard refresh.** Current design: whole-dashboard only (re-run the plan). Per-placement refresh would require per-task re-execution, which the orchestrator already supports but which hasn't been exposed as an action. Deferred.
3. **Canvas templates.** A "copy from existing dashboard" affordance would help users. Low cost; not in the initial PRDs but worth a follow-up.
4. **Drill-down from a widget back to the source task.** Clicking a widget could focus the corresponding task in the DAG view above. Include in DB-PRD-03 if time permits; otherwise defer.

## 11. Success criteria (rolled up)

- A user can create a dashboard, attach 5+ tasks with declared outputs, run the plan, and see five populated widgets on the canvas. (DB-PRD-04 E2E)
- Re-running the dashboard updates every widget's `updated_at` to the new run's timestamp; staleness indicator clears. (DB-PRD-04 E2E)
- Disconnecting a task (disable `output_config`, or delete the task) flags affected placements as disconnected without data loss. (DB-PRD-04 edge case)
- The Dashboards list is distinct from the Automations list — a user toggling `save_as_automation=true` on a dashboard plan still sees it in Dashboards, not in Automations. (DB-PRD-04 isolation test)
- 100-placement dashboard GET returns in under 500 ms p95, with small payloads inlined and large ones signed-URL'd. (DB-PRD-04 perf test)
