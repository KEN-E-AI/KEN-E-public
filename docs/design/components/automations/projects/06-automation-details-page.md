# A-PRD-6 — Automation Details Page

**Status:** Ready for development (after A-PRD-1 merges; soft dependencies on A-PRDs 3 + 4)
**Owner team:** Frontend
**Blocked by:** A-PRD-1
**Soft-dependent on:** A-PRD-3 (Outputs tab), A-PRD-4 (Test Run button)
**Parallel with:** A-PRDs 2, 3, 5
**Estimated effort:** 4–5 days

---

## 1. Context

When a user clicks "Configure" on an automation row in A-PRD-5, they land on the Automation Details page. This page is the user's primary control surface for an automation: visualize the dependency graph as a diagram, edit tasks and edges, configure the recurrence schedule, trigger and inspect test runs, and review past artifact outputs per task.

This PRD is the largest frontend piece in the Automations set — five capabilities composed into one page.

## 2. Scope

### In scope
- New route `/workflows/automations/{plan_id}`
- DAG diagram using **React Flow** (xyflow): draggable task nodes, draggable edges for dependencies, custom node component matching the design system
- Inline DAG editing: add task (right-click canvas), connect tasks (drag handle to handle), delete (selection + Delete key), auto-layout (dagre) button
- Right-side `ActivityDetailPanel` (reused from Calendar PRD-3) extended with a new **"Outputs"** tab that lists artifacts from past runs of the selected task
- Schedule editor modal: Daily / Weekly / Monthly preset picker + Custom (cron) tab + timezone picker + "next 5 fires" preview
- "Test Run" button + in-page progress display: tasks animate as they complete; halted HITL tasks pulse with "Action required"; user can mark complete from the right panel
- Cancel-test-run button while a run is in flight
- **Read-only mode when `is_system=true`** — used for platform-owned templates (e.g. KG-PRD-04's session-end automation). See §is_system read-only mode.
- **HITL Mark Complete / Revision Requested affordances** that work on system-owned runs too — this is how users review and approve session-end proposals without being able to edit the underlying template.
- Component tests

### Out of scope
- Backend test-run engine (A-PRD-4)
- Backend artifact storage (A-PRD-3)
- The list page (A-PRD-5)
- Real-time collaboration (multiple users editing the diagram simultaneously) — future
- Undo/redo for diagram edits — future

## 3. Dependencies

- **A-PRD-1:** API for fetching the automation, listing runs, patching tasks
- **A-PRD-3:** API for listing artifacts per task; without A-PRD-3, the Outputs tab shows an empty state
- **A-PRD-4:** Test-run endpoint + cancel endpoint; without A-PRD-4, the Test Run button is hidden
- **Calendar PRD-3:** reuses `ActivityDetailPanel` (must be extensible — confirm with the owning team)
- **External libraries:**
  - `@xyflow/react` (React Flow) — DAG diagram
  - `dagre` — auto-layout
  - `cronstrue` — cron → human-readable in the schedule preview (can also import from A-PRD-5)
- **Existing files to study:**
  - `frontend/src/components/ActivityDetailPanel.tsx` (Calendar PRD-3)
  - `frontend/src/services/projectPlanService.ts` (Calendar PRD-3)

### Coordination — extending `ActivityDetailPanel`

The right-panel detail component owns the tab strip. This PRD adds a new tab key (`"outputs"`) that appears when:
1. The selected task has `assignee_type === "agent"`, AND
2. The current page is the Automation Details page (not the calendar)

Pass an `availableTabs` prop or use a slot pattern. Coordinate with the Calendar PRD-3 owners.

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
| Create | `frontend/src/pages/AutomationDetailsPage.tsx` |
| Create | `frontend/src/components/automations/dag/DagDiagram.tsx` (React Flow wrapper) |
| Create | `frontend/src/components/automations/dag/TaskNode.tsx` (custom node) |
| Create | `frontend/src/components/automations/dag/dagLayout.ts` (dagre auto-layout helper) |
| Create | `frontend/src/components/automations/dag/dagSerialize.ts` (`PlanTask[]` ↔ `{nodes, edges}`) |
| Create | `frontend/src/components/automations/ScheduleEditorModal.tsx` |
| Create | `frontend/src/components/automations/schedulePresetToCron.ts` |
| Modify | `frontend/src/components/ActivityDetailPanel.tsx` (Calendar PRD-3) — add `availableTabs` + Outputs tab content slot |
| Create | `frontend/src/components/automations/OutputsTab.tsx` |
| Create | `frontend/src/components/automations/TestRunControls.tsx` (button + progress + cancel) |
| Modify | `frontend/src/services/projectPlanService.ts` — add `getAutomation`, `getRun`, `listRuns`, `triggerTestRun`, `cancelRun`, `listTaskArtifactsRecent` |
| Modify | `frontend/src/App.tsx` — add `/workflows/automations/:planId` route |
| Create | `frontend/src/pages/AutomationDetailsPage.test.tsx` |
| Create | `frontend/src/components/automations/dag/DagDiagram.test.tsx` |
| Create | `frontend/src/components/automations/ScheduleEditorModal.test.tsx` |
| Create | `frontend/src/components/automations/OutputsTab.test.tsx` |

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
- `tasksToGraph(tasks: PlanTask[]): { nodes: DagNode[]; edges: DagEdge[] }` — nodes from tasks, edges from `depends_on`. Initial positions via dagre auto-layout if no saved positions exist.
- `graphToTasks(nodes, edges, originalTasks): PlanTask[]` — preserves all task fields except `depends_on`, which is derived from edges
- Node positions are persisted server-side via `PlanTask.layout_x`, `PlanTask.layout_y` — **coordinate with A-PRD-1 to add these fields** (or store positions in a sidecar `dag_layout_{plan_id}` doc to avoid touching A-PRD-1's contract; recommend the sidecar approach to keep PRD-1 stable)

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
- Custom tab: raw cron field with live validation (calls a new endpoint `POST /api/v1/automations/_validate_cron` that returns `{is_valid, next_fires: [datetime, ...]}` — small addition to consider for A-PRD-1 or live in this PRD's frontend by importing `cronstrue` + a local cron iterator)
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

This PRD consumes:
- `GET /api/v1/automations/{account_id}/{plan_id}` (A-PRD-1)
- `PUT /api/v1/plans/{account_id}/{plan_id}` (Calendar PRD-1) for whole-plan saves on diagram edits
- `PATCH /api/v1/automations/{account_id}/{plan_id}/recurrence` (A-PRD-1)
- `GET /api/v1/automations/{account_id}/{plan_id}/runs/{run_id}` (A-PRD-1) for polling test-run progress
- `POST /api/v1/automations/{account_id}/{plan_id}/runs/test` (A-PRD-4)
- `POST /api/v1/automations/{account_id}/{plan_id}/runs/{run_id}/cancel` (A-PRD-4)
- `PATCH /api/v1/plans/{account_id}/{plan_id}/tasks/{task_id}` (Calendar PRD-1) for HITL Mark Complete
- `GET /api/v1/automations/{account_id}/{plan_id}/tasks/{task_id}/artifacts/recent` (A-PRD-3)
- `GET /api/v1/automations/{account_id}/{plan_id}/runs/{run_id}/artifacts/{artifact_id}/download` (A-PRD-3)

## 7. Acceptance criteria

1. Navigating to `/workflows/automations/{plan_id}` renders the page with the DAG diagram populated
2. Dragging a task node moves it; releasing persists position via the layout sidecar (no full plan PUT for layout-only changes)
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
| Layout positions: extend PlanTask vs. sidecar doc | **Recommendation: sidecar.** Avoids modifying A-PRD-1's contract; keeps layout concerns on the frontend's side. New collection: `dag_layouts_{account_id}/{plan_id}` with `{task_id: {x, y}}` map. Backend: trivial CRUD. Confirm before implementation. |
| Polling cost during long test runs | 2s poll for 5min = 150 requests. Acceptable for v1. Future: WebSocket / SSE push. |
| HITL halt UX visibility | Pulsing node + toast + sidebar notification — three signals so the user can't miss it. |
| Diagram with 100+ nodes | React Flow handles this fine; dagre layout may take 500ms for the first auto-layout. Show a spinner. |
| Cron validation: server vs. client | Pick one — recommendation: client-side via `cronstrue` + a minimal cron iterator for "next 5 fires" preview, server validates on PATCH. |
| Concurrent edits to the same automation by two users | Last-writer-wins via PUT optimistic concurrency. Surface a "modified by another user, refresh to see changes" toast on 409. |
| Outputs tab loading time when a task has many artifacts | Limit to 20 most recent runs by default; "Show older" expands. |

## 10. Reference

- Parent plan: [`../README.md`](../README.md) §5 (Phase 6)
- Foundation: [A-PRD-1](./01-data-model-and-api.md), [A-PRD-3](./03-task-artifact-system.md), [A-PRD-4](./04-test-dry-run-mode.md)
- Pattern files: `frontend/src/components/ActivityDetailPanel.tsx` (Calendar PRD-3), `frontend/src/pages/CalendarPage.tsx`
- React Flow docs: https://reactflow.dev/
- Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) — Workflows / Automations / Configure
- CLAUDE.md rules in scope: C-5, C-6, C-8, G-2, G-3, T-2
