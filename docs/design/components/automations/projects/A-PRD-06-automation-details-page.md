# A-PRD-6 — Automation Details Page

**Status:** Ready for development (after A-PRD-1 merges; soft dependencies on A-PRDs 3 + 4)
**Owner team:** Frontend
**Blocked by:** A-PRD-1; UI-PRD-03 (provides the `/workflows/automations/:planId` route and the empty-state `AutomationDetailsPage` shell that this PRD modifies)
**Soft-dependent on:** A-PRD-3 (Outputs tab), A-PRD-4 (Test Run button), DP-PRD-03 (adds `data_pipeline` to `PlanTask.assignee_type` so the third value can render in the side-panel picker; gate the `data_pipeline` option behind feature flag `data_pipeline_task_assignee` until DP-PRD-03 ships)
**Parallel with:** A-PRDs 2, 3, 5
**Estimated effort:** 4–5 days

---

## 1. Context

When a user clicks "Configure" on an automation row in A-PRD-5, they land on the Automation Details page. This page is the user's primary control surface for an automation: visualize the dependency graph as a diagram, edit tasks and edges, configure the recurrence schedule, trigger and inspect test runs, and review past artifact outputs per task.

This PRD is the largest frontend piece in the Automations set — five capabilities composed into one page.

**Shared DAG editor.** This PRD ships the React Flow DAG editor as a **shared, reusable component** at `frontend/src/components/dag/TaskGraph.tsx` (with siblings `TaskNode.tsx`, `dagLayout.ts`). DB-PRD-03 reuses this component verbatim for the Performance → Dashboards details page (`/performance/dashboards/{plan_id}`). One implementation, two consumers — driven by props (`tasks`, `edges`, `onTaskAdd`, `onEdgeChange`, `readOnly`, `selectedTaskId`, `availablePanels`). The "+ Add Task" button on the canvas opens the right-side panel for task configuration; for `assignee_type="data_pipeline"`, the panel surfaces DP-PRD-04's pipeline-job picker + custom-job authoring side-flow (see DP-PRD-04 §scope).

**Shared task and schedule panels.** This PRD also publishes two additional shared, reusable components consumed verbatim by DB-PRD-03:

- **`ActivityDetailPanel`** (the right-side task-edit panel, originally from Calendar PRD-3, extended here with the Outputs tab) is now relocated to `frontend/src/components/workflows/ActivityDetailPanel.tsx` so both Automations (Calendar + this PRD) and Dashboards (DB-PRD-03) consume it from a single location. New additive prop `pinToDashboardSlot?: ReactNode` — when present, the panel renders the slot in a dedicated location in the agent-task surface (DB-PRD-03 fills it with `<PinToDashboardPicker />`); when absent (the Automation Details page case), the slot region collapses to nothing. No breaking change for existing callers.
- **`ScheduleEditorModal`** (this PRD's schedule editor) ships at `frontend/src/components/workflows/ScheduleEditorModal.tsx` as a shared component DB-PRD-03 mounts on the Dashboards details page header. Same prop contract, same behavior, same `POST /v1/schedules/preview` consumer; the modal is unaware of `plan.type`.

Both are at `frontend/src/components/workflows/` rather than `.../automations/` to make the shared status visible at the file-tree level.

## 2. Scope

### In scope
- New route `/workflows/automations/{plan_id}`
- **Shared DAG editor** at `frontend/src/components/dag/TaskGraph.tsx` (+ `TaskNode.tsx`, `dagLayout.ts`) using **React Flow** (xyflow): draggable task nodes, draggable edges for dependencies, custom node component matching the design system. Designed to be reused unchanged by DB-PRD-03 on the Dashboards details page — driven by props, no automation-specific assumptions inside the component.
- Inline DAG editing: **+ Add Task** button (also available via right-click on canvas), connect tasks (drag handle to handle), delete (selection + Delete key), auto-layout (dagre) button
- "+ Add Task" → opens the right-side `ActivityDetailPanel` in "create" mode with an `assignee_type` picker (`agent` / `human` / `data_pipeline`). When `data_pipeline` is selected, DP-PRD-04's pipeline-job picker + custom-job authoring panel surfaces (see DP-PRD-04). No standalone `/workflows/data-pipelines` route — data pipelines are created inline from the DAG editor.
- Right-side `ActivityDetailPanel` — relocated from `frontend/src/components/ActivityDetailPanel.tsx` (Calendar PRD-3) to `frontend/src/components/workflows/ActivityDetailPanel.tsx` and extended with a new **"Outputs"** tab that lists artifacts from past runs of the selected task. Adds an additive `pinToDashboardSlot?: ReactNode` prop that DB-PRD-03 uses to render its `<PinToDashboardPicker />`; A-PRD-06 itself never passes this prop (slot collapses to nothing).
- Schedule editor modal at `frontend/src/components/workflows/ScheduleEditorModal.tsx`: Daily / Weekly / Monthly preset picker + Custom (cron) tab + timezone picker + "next 5 fires" preview. Published as a shared component consumed verbatim by DB-PRD-03's Dashboards details page header.
- "Test Run" button + in-page progress display: tasks animate as they complete; halted HITL tasks pulse with "Action required"; user can mark complete from the right panel
- Cancel-test-run button while a run is in flight
- **Read-only mode when `is_system=true`** — used for platform-owned templates (e.g. KG-PRD-04's session-end automation). See §is_system read-only mode. Also passed as the `readOnly` prop on the shared `TaskGraph`, which DB-PRD-03 and any future consumer can use too.
- **HITL Mark Complete / Revision Requested affordances** that work on system-owned runs too — this is how users review and approve session-end proposals without being able to edit the underlying template.
- Component tests on the shared `TaskGraph` covering both consumers' use cases (basic editing, read-only mode, data-pipeline assignee creation)
- Component tests on `ActivityDetailPanel` covering both consumers: `pinToDashboardSlot` absent (Automations path — slot empty) and `pinToDashboardSlot` present (Dashboards path — slot rendered with a stub node).

### Out of scope
- Backend test-run engine (A-PRD-4)
- Backend artifact storage (A-PRD-3)
- The list page (A-PRD-5)
- Real-time collaboration (multiple users editing the diagram simultaneously) — future
- Undo/redo for diagram edits — future

## 3. Dependencies

- **UI-PRD-03 (hard prerequisite):** ships `frontend/src/pages/workflows/AutomationDetailsPage.tsx` (empty-state / mocked-data shell this PRD replaces with the real DAG canvas + right-side panel layout) and the `/workflows/automations/:planId` route under `LayoutC` in `frontend/src/App.tsx`. Note: UI-PRD-03's mocked top-level Overview / Outputs sub-tabs are placeholders — this PRD replaces that structure with the canonical layout (DAG canvas as main content, Outputs surfaced as a tab inside the right-side `ActivityDetailPanel`). The `WorkflowsLayout` tab contract is consumed by reference, not modified.
- **A-PRD-1:** API for fetching the automation, listing runs, patching tasks
- **A-PRD-2:** consumes `POST /v1/schedules/preview` for cron validation + "next 5 fires" inside the schedule editor modal (replacing the previously-scoped `/automations/_validate_cron` placeholder)
- **A-PRD-3:** API for listing artifacts per task; without A-PRD-3, the Outputs tab shows an empty state
- **A-PRD-4:** Test-run endpoint + cancel endpoint; without A-PRD-4, the Test Run button is hidden
- **DP-PRD-03 (forward-coordination):** extends `PlanTask.assignee_type` from `{agent, human}` to `{agent, human, data_pipeline}`. This PRD's task-creation side-panel renders the `data_pipeline` option behind a `data_pipeline_task_assignee` feature flag until DP-PRD-03 ships; DP-PRD-04 then wires the picker + custom-job authoring panel into the same side-panel. A-PRD-06 ships only the assignee-type radio + flag gate; DP-PRD-04 fills in the data-pipeline-specific fields.
- **Calendar PRD-3:** sources `ActivityDetailPanel` (relocated from `frontend/src/components/ActivityDetailPanel.tsx` to `frontend/src/components/workflows/ActivityDetailPanel.tsx` by this PRD; updates Calendar PRD-3's import paths in the same change).
- **DB-PRD-03 (forward-coordination, Dashboards):** consumes the shared `frontend/src/components/dag/TaskGraph.tsx` plus the shared `frontend/src/components/workflows/ActivityDetailPanel.tsx` and `frontend/src/components/workflows/ScheduleEditorModal.tsx`. Coordination point: this PRD adds the `pinToDashboardSlot?: ReactNode` prop on `ActivityDetailPanel`; DB-PRD-03 supplies the slot value (`<PinToDashboardPicker />`). Additive only — no breaking change.
- **External libraries:**
  - `@xyflow/react` (React Flow) — DAG diagram
  - `dagre` — auto-layout
  - `cronstrue` — cron → human-readable in the schedule preview (can also import from A-PRD-5)
- **Existing files to study:**
  - `frontend/src/pages/workflows/AutomationDetailsPage.tsx` (UI-PRD-03) — empty-state shell this PRD replaces
  - `frontend/src/components/ActivityDetailPanel.tsx` (Calendar PRD-3)
  - `frontend/src/services/projectPlanService.ts` (Calendar PRD-3)

### Coordination — extending `ActivityDetailPanel` and relocating it as shared

The right-panel detail component owns the tab strip and is the canonical task-edit surface across three consumers (Calendar PRD-3, this PRD, and DB-PRD-03).

This PRD makes three changes to it:

1. **Relocate** from `frontend/src/components/ActivityDetailPanel.tsx` → `frontend/src/components/workflows/ActivityDetailPanel.tsx`. Update import paths in Calendar PRD-3's callers in the same change. (Calendar PRD-3 shipped first and put the panel under `components/`; the move surfaces its shared status.)
2. **Add** a new tab key (`"outputs"`) that appears when:
   - The selected task has `assignee_type === "agent"`, AND
   - The current page is the Automation Details page (not the Calendar — Calendar consumers pass `availableTabs` without `"outputs"`)
3. **Add** an additive prop `pinToDashboardSlot?: ReactNode`. When present, the panel renders the slot in a dedicated location near the bottom of the agent-task surface; when absent (Calendar + Automations callers), the slot region is empty. DB-PRD-03 supplies `<PinToDashboardPicker />` as the slot value.

Coordinate the relocation with Calendar PRD-3 owners (one-PR change with import-path updates).

## 4. Data contract (TypeScript)

Reuses A-PRD-5 types; adds:

```ts
type DagNode = {
  id: TaskId
  type: 'task'
  position: { x: number; y: number }
  data: { task: PlanTask }
}

type DagEdge = {
  id: string                           // `${source}->${target}`
  source: TaskId
  target: TaskId
  type: 'dependency'
}

type SchedulePreset =
  | { kind: 'daily'; time_local: string; timezone: string }
  | { kind: 'weekly'; days: DayOfWeek[]; time_local: string; timezone: string }
  | { kind: 'monthly'; day_of_month: number; time_local: string; timezone: string }
  | { kind: 'custom'; cron: string; timezone: string }

type RunProgress = {
  run_id: RunId
  status: RunStatus
  task_states: TaskRunState[]
}
```

## 5. Implementation outline

| Action | File |
|--------|------|
| Modify | `frontend/src/pages/workflows/AutomationDetailsPage.tsx` (UI-PRD-03 shell) — replace mocked top-level Overview / Outputs sub-tabs with the canonical DAG canvas + right-side `ActivityDetailPanel` layout |
| Create | `frontend/src/components/dag/TaskGraph.tsx` (shared React Flow wrapper — used here and by DB-PRD-03) |
| Create | `frontend/src/components/dag/TaskNode.tsx` (shared custom node) |
| Create | `frontend/src/components/dag/dagLayout.ts` (shared dagre auto-layout helper) |
| Create | `frontend/src/components/automations/dag/dagSerialize.ts` (`PlanTask[]` ↔ `{nodes, edges}`) |
| Create | `frontend/src/components/workflows/ScheduleEditorModal.tsx` (shared — used here and by DB-PRD-03) |
| Create | `frontend/src/components/automations/schedulePresetToCron.ts` |
| Move + Modify | `frontend/src/components/ActivityDetailPanel.tsx` (Calendar PRD-3) → `frontend/src/components/workflows/ActivityDetailPanel.tsx`; add `availableTabs` + Outputs tab content slot + additive `pinToDashboardSlot?: ReactNode` prop. Update import paths in Calendar PRD-3's existing callers in the same PR. |
| Create | `frontend/src/components/automations/OutputsTab.tsx` |
| Create | `frontend/src/components/automations/TestRunControls.tsx` (button + progress + cancel) |
| Modify | `frontend/src/services/projectPlanService.ts` — add `getAutomation`, `getRun`, `listRuns`, `triggerTestRun`, `cancelRun`, `listTaskArtifactsRecent`, `previewSchedule` (calls A-PRD-2's `POST /v1/schedules/preview` for the schedule editor's cron-validation + "next 5 fires" preview), `getDagLayout`, `putDagLayout` |
| Create | `api/src/kene_api/routers/dag_layouts.py` — GET/PUT for the layout sidecar |
| Create | `api/src/kene_api/models/dag_layout_models.py` — `DagLayoutDoc` Pydantic model |
| Create | `api/tests/integration/test_dag_layouts_router.py` |
| Modify | `frontend/src/pages/workflows/AutomationDetailsPage.test.tsx` (UI-PRD-03 shell test) — extend with DAG-canvas + side-panel assertions |
| Create | `frontend/src/components/automations/dag/DagDiagram.test.tsx` |
| Create | `frontend/src/components/workflows/ScheduleEditorModal.test.tsx` (shared — covers both Automation and Dashboard caller contexts) |
| Create | `frontend/src/components/workflows/ActivityDetailPanel.test.tsx` — covers `pinToDashboardSlot` absent (Automation path) and present (Dashboard path) |
| Create | `frontend/src/components/automations/OutputsTab.test.tsx` |

> **Out of scope (already shipped by UI-PRD-03):** the `/workflows/automations/:planId` route registration in `frontend/src/App.tsx`. Do not re-add the route.

### DAG diagram

- React Flow `<ReactFlow>` wrapper inside a fixed-height container
- Custom `TaskNode` renders: title, assignee badge, platform color stripe, status icon
- Edges are simple bezier; arrowhead at target
- Selection: click node/edge highlights; Delete key removes (with confirmation modal for nodes that have downstream dependents)
- Drag handle on node bottom-right → drag to another node's top to create a `depends_on` edge
- "Auto-layout" button runs dagre on current nodes/edges, animates positions
- Persistence: changes to nodes/edges → debounce 500ms → PUT to `/api/v1/plans/{account_id}/{plan_id}` (whole-plan replace; the tasks array is the source of truth)

### Serialization

`dagSerialize.ts`:
- `tasksToGraph(tasks: PlanTask[]): { nodes: DagNode[]; edges: DagEdge[] }` — nodes from tasks, edges from `depends_on`. Initial positions sourced from the layout sidecar (see below); fall back to dagre auto-layout if no sidecar doc exists.
- `graphToTasks(nodes, edges, originalTasks): PlanTask[]` — preserves all task fields except `depends_on`, which is derived from edges. Position coordinates do **not** flow back into `PlanTask` (positions live in the sidecar).

#### DAG layout sidecar

Node positions persist in a Firestore **sidecar doc**, not on `PlanTask` — this avoids touching A-PRD-01's contract and keeps layout-only edits (drag-to-reposition) cheap (one small write, no plan-level revalidation, no audit churn).

- **Path:** `accounts/{account_id}/dag_layouts/{plan_id}`
- **Shape:**
  ```ts
  type DagLayoutDoc = {
    plan_id: PlanId
    positions: Record<TaskId, { x: number; y: number }>
    updated_at: string  // ISO datetime
    version: number
  }
  ```
- **Endpoints owned by this PRD:**
  - `GET /api/v1/plans/{account_id}/{plan_id}/dag-layout` → returns the sidecar doc, or `404` if none exists (treated as "no saved positions" — caller falls back to dagre auto-layout).
  - `PUT /api/v1/plans/{account_id}/{plan_id}/dag-layout` → idempotent upsert of the full positions map; debounced 500ms by the frontend.
- **Lifecycle:** the sidecar lives under `accounts/{account_id}/`, so DM-PRD-05's `recursive_delete` covers cleanup on account deletion automatically. No extra hook needed. No audit entry — layout state is not user-meaningful enough to log.
- **No new composite index required** — the sidecar is read by `plan_id` (doc lookup, not query).
- **Size cap:** 100 tasks × ~64 bytes per entry ≈ 6.4 KB; well under Firestore's 1 MB doc limit.

Layout-only edits (drag a node) do **not** write the plan via PUT — they only write the sidecar. Edits that change `tasks` or `depends_on` (add task, connect edge, delete) still trigger the whole-plan PUT to `/api/v1/plans/{account_id}/{plan_id}`.

### Schedule editor modal

```
┌─ Schedule ────────────────────────┐
│  Tabs: [Daily] [Weekly] [Monthly] [Custom] │
│                                    │
│  (depends on tab — example: Weekly)│
│  Time: [09:00] AM/PM               │
│  Days: M T W T F S S (chips)       │
│  Timezone: [America/Los_Angeles ▾] │
│                                    │
│  Cron preview: "0 9 * * MON,WED,FRI"│
│  Next 5 fires:                     │
│    • Mon Apr 21 9:00 AM PT         │
│    • Wed Apr 23 9:00 AM PT         │
│    • Fri Apr 25 9:00 AM PT         │
│    ...                             │
│                                    │
│  [Cancel]  [Save]                  │
└────────────────────────────────────┘
```

- Daily / Weekly / Monthly each compose a cron string via `schedulePresetToCron`
- Custom tab: raw cron field with live validation via `POST /v1/schedules/preview` (A-PRD-2). The endpoint returns `{occurrences, truncated}` for a small window (e.g. next 30 days, `max_occurrences=5`); the editor uses `occurrences.length === 0` (combined with the 422 response on bad cron) to gate the Save button and renders the first 5 occurrences in the "Next 5 fires" preview.
- The frontend MUST NOT compute occurrences client-side (per A-PRD-2's contract — the preview endpoint is the single source of truth for occurrence expansion).
- Save → PATCH `/recurrence` (A-PRD-1)

### Outputs tab

- Visible only when selected task has `assignee_type === "agent"`
- Header: task title + "Outputs from recent runs"
- Filter chips: "All runs" / "Test runs only" / "Production only"
- List grouped by run, most recent first:
  ```
  ▼ Run #12 — Apr 16, 9:00 AM (Test) [success]
      • ad_copy.md (text/markdown, 3.2 KB) [Preview] [Download]
      • hero.png (image/png, 1.4 MB) [Preview] [Download]
  ▼ Run #11 — Apr 15, 9:00 AM [success]
      • ad_copy.md ...
  ```
- "Show older runs" pagination (last 20 by default)
- Preview behavior:
  - Text: open in modal with markdown rendering
  - Image: lightbox
  - Video (mp4): inline player (HTML5 `<video>`)
  - Other: download only
- Download: hits A-PRD-3's download endpoint, follows redirect to the signed URL

### Test Run controls

- Button: "Test Run" — disabled if a test run is already in flight
- On click: POST to A-PRD-4's test endpoint, optimistically render a "Test run started" banner with run_id
- Polling: every 2s, GET the run; update task statuses on the diagram (color/glow) until terminal
- Halt detection: when a `task_state.status === "Awaiting Approval"` and run is `is_test`, the corresponding diagram node pulses; clicking it opens the right panel with a prominent "Mark Complete" button
- Cancel button visible while run is non-terminal
- On terminal status: banner shows summary (e.g., "Test run complete — 5 tasks succeeded, 2 artifacts generated") + link to the Outputs tab

### `is_system` read-only mode

When the fetched automation has `is_system=true`, the page renders in read-only mode:

| Control | `is_system=false` | `is_system=true` |
|---|---|---|
| DAG diagram | Editable (drag nodes, add/delete tasks, connect edges) | **Read-only** — nodes visible and draggable for layout but no add/delete/connect. `<ReactFlow nodesDraggable={true} nodesConnectable={false} elementsSelectable={true} />`; Delete key disabled. |
| Auto-layout button | Enabled | Enabled (layout is non-destructive) |
| Schedule editor modal | "Edit schedule" opens modal | "View schedule" opens the modal read-only with Save button hidden |
| Test Run button | Visible | **Hidden** — system automations are triggered by their owning platform (e.g. the KG sweeper), not manually. |
| Run Now button (if present elsewhere on the page) | Visible | **Hidden** |
| Delete button | Visible | **Hidden** |
| Right-side `ActivityDetailPanel` — editable fields (title, description, assignee, etc.) | Editable | **Read-only** — fields render as text, not inputs |
| Right-side panel — status actions (**Mark Complete**, **Revision Requested**) | Visible on HITL tasks | **Visible** — this is the core interaction: reviewers approve or request revisions on halted runs (e.g. KG-PRD-04 proposals) without editing the template |
| Outputs tab | Visible | **Visible** — the primary purpose of the page for system automations is inspecting run artifacts |
| Run history (runs list, polling, banners) | Visible | **Visible** |

**Visual treatment:** a banner above the DAG reads "System automation — managed by KEN-E. You can review runs and approve halted tasks, but the template itself cannot be edited." Style it as informational (not an error). The DAG canvas gets a subtle read-only affordance (e.g. dashed border on nodes, no hover shadow).

**Implementation:** gate all write-control rendering on `!automation.is_system`. Gate HITL status actions on `assignee_type === "human"` only (no `is_system` check — they must work for system automations).

**Defense-in-depth:** the backend also rejects writes to `is_system=true` plans (PUT/PATCH/DELETE → 403) — see A-PRD-1 acceptance criteria. The frontend does not rely on the backend check alone, nor vice versa.

## 6. API contract

This PRD owns two new endpoints for the DAG layout sidecar (full spec in §5):

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/plans/{account_id}/{plan_id}/dag-layout` | Fetch saved DAG node positions (or 404 if none) |
| `PUT` | `/api/v1/plans/{account_id}/{plan_id}/dag-layout` | Idempotent upsert of the positions map (debounced 500ms by the frontend) |

Both endpoints reuse the existing `check_strategy_access`-equivalent dependency. Cross-account requests return `403`.

This PRD also consumes:
- `GET /api/v1/automations/{account_id}/{plan_id}` (A-PRD-1)
- `PUT /api/v1/plans/{account_id}/{plan_id}` (Calendar PRD-1) for whole-plan saves on diagram edits
- `PATCH /api/v1/automations/{account_id}/{plan_id}/recurrence` (A-PRD-1)
- `GET /api/v1/automations/{account_id}/{plan_id}/runs/{run_id}` (A-PRD-1) for polling test-run progress
- `POST /api/v1/automations/{account_id}/{plan_id}/runs/test` (A-PRD-4)
- `POST /api/v1/automations/{account_id}/{plan_id}/runs/{run_id}/cancel` (A-PRD-4)
- `POST /api/v1/schedules/preview` (A-PRD-2) — for cron validation + "next 5 fires" preview in the schedule editor modal
- `PATCH /api/v1/plans/{account_id}/{plan_id}/tasks/{task_id}` (Calendar PRD-1) for HITL Mark Complete
- `GET /api/v1/automations/{account_id}/{plan_id}/tasks/{task_id}/artifacts/recent` (A-PRD-3)
- `GET /api/v1/automations/{account_id}/{plan_id}/runs/{run_id}/artifacts/{artifact_id}/download` (A-PRD-3)

## 7. Acceptance criteria

1. Navigating to `/workflows/automations/{plan_id}` renders the page with the DAG diagram populated
2. Dragging a task node moves it; releasing persists position via `PUT /api/v1/plans/{account_id}/{plan_id}/dag-layout` (the sidecar — no full plan PUT for layout-only changes). On reload, `GET .../dag-layout` returns the saved positions; if 404, dagre auto-layout fills in defaults.
3. Dragging from a node's output handle to another node's input creates a `depends_on` edge; the change is persisted via PUT
4. Deleting a node prompts for confirmation if there are downstream dependents; on confirm, removes the task and its edges
5. Auto-layout button re-positions nodes via dagre and animates the change
6. Schedule editor modal: each preset tab generates the correct cron; "next 5 fires" preview matches expectations; Save → PATCH succeeds; recurrence summary on the page header updates
7. Test Run button triggers a test run; the diagram animates statuses as tasks complete (polling)
8. When a HITL task halts the test run, the diagram node pulses; clicking opens the right panel with a Mark Complete button; clicking it advances the run
9. Cancel button aborts the in-flight run
10. Outputs tab on an agent task shows artifacts grouped by run; download retrieves the file via signed URL; preview works for text / image / mp4
11. Outputs tab is hidden for human-assignee tasks
12. URL `/workflows/automations/{plan_id}?run={run_id}&task={task_id}` deep-links into the page with the right run polling and the right task panel open
13. `is_system=true` automations render with: read-only DAG (nodesConnectable=false, Delete key no-op), hidden Test Run / Run Now / Delete buttons, read-only right-panel fields, visible HITL Mark Complete / Revision Requested buttons on human tasks, visible Outputs tab, informational banner. Attempting any write action via backend requests returns 403.
14. All component tests pass; typecheck and format pass

## 8. Test plan

**Component tests:**
- `DagDiagram.test.tsx`: renders nodes/edges from a fixture; drag → updates layout; create-edge → updates `depends_on`; delete-node with downstream → confirmation modal
- `DagDiagram.test.tsx` (is_system): with `is_system=true`, nodesConnectable is false, Delete key does nothing, add-task right-click is suppressed
- `ScheduleEditorModal.test.tsx`: each preset tab → correct cron; custom tab validates input; save calls PATCH
- `ScheduleEditorModal.test.tsx` (is_system): Save button hidden, fields render read-only
- `OutputsTab.test.tsx`: renders artifacts grouped by run; filter chips work; preview opens correct modal type per mime
- `TestRunControls.test.tsx`: triggers run, polls, animates statuses; cancel aborts
- `TestRunControls.test.tsx` (is_system): Test Run button not rendered
- `AutomationDetailsPage.test.tsx`: full-page render; deep-link query params restore state
- `AutomationDetailsPage.test.tsx` (is_system): banner renders; HITL Mark Complete on human tasks still works

**Manual smoke (record steps for A-PRD-7):**
- Edit a DAG (add task, connect, delete, auto-layout) — verify all changes persist on reload
- Configure a schedule via each preset tab + custom — verify cron generated correctly
- Trigger a test run, halt at HITL, mark complete, verify completion + artifacts in Outputs tab
- Cancel a test run mid-flight

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| React Flow learning curve / bundle size | Bundle ~80KB gz — acceptable. Devs can ramp on it via the React Flow examples site. |
| Layout positions: extend PlanTask vs. sidecar doc | **Resolved — sidecar.** Sidecar at `accounts/{account_id}/dag_layouts/{plan_id}` (full spec in §5 "DAG layout sidecar"); no changes to A-PRD-01's `PlanTask` model. |
| Polling cost during long test runs | 2s poll for 5min = 150 requests. Acceptable for v1. Future: WebSocket / SSE push. |
| HITL halt UX visibility | Pulsing node + toast + sidebar notification — three signals so the user can't miss it. |
| Diagram with 100+ nodes | React Flow handles this fine; dagre layout may take 500ms for the first auto-layout. Show a spinner. |
| Cron validation: server vs. client | Resolved — server-side via A-PRD-2's `POST /v1/schedules/preview` (the canonical occurrence expander, per A-PRD-2's contract). `cronstrue` is used only for human-readable summaries (e.g. "Every Monday at 9:00 AM PT"), not for occurrence math. |
| Concurrent edits to the same automation by two users | Last-writer-wins via PUT optimistic concurrency. Surface a "modified by another user, refresh to see changes" toast on 409. |
| Outputs tab loading time when a task has many artifacts | Limit to 20 most recent runs by default; "Show older" expands. |

## 10. Reference

- Parent plan: [`../README.md`](../README.md) §5 (Phase 6)
- Foundation: [A-PRD-1](./A-PRD-01-data-model-and-api.md), [A-PRD-2](./A-PRD-02-recurring-scheduler.md), [A-PRD-3](./A-PRD-03-task-artifact-system.md), [A-PRD-4](./A-PRD-04-test-dry-run-mode.md)
- Shell: [UI-PRD-03](../../ui/projects/UI-PRD-03-workflows-shell.md) — `AutomationDetailsPage` shell + `/workflows/automations/:planId` route
- Forward-coordination: [DP-PRD-03](../../data-pipeline/projects/DP-PRD-03-task-system-integration.md) (third `assignee_type` value), [DP-PRD-04](../../data-pipeline/projects/DP-PRD-04-frontend-and-custom-jobs.md) (data-pipeline picker + custom-job authoring panel inside the shared DAG editor's side-panel)
- Pattern files: `frontend/src/components/ActivityDetailPanel.tsx` (Calendar PRD-3), `frontend/src/pages/CalendarPage.tsx`
- React Flow docs: https://reactflow.dev/
- Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) — Workflows / Automations / Configure
- CLAUDE.md rules in scope: C-5, C-6, C-8, G-2, G-3, T-2
