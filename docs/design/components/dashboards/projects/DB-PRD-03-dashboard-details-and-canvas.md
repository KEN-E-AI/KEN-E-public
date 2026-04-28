# DB-PRD-03 — Dashboard Details & Canvas

**Status:** Blocked — resumes once DB-PRD-01, DB-PRD-02, and A-PRD-06 ship
**Owner team:** Frontend
**Blocked by:** DB-PRD-01 (API contract and resolved-artifact shape); DB-PRD-02 (Performance tab + navigation + stub route); A-PRD-06 (publishes three shared components consumed verbatim by this PRD: `frontend/src/components/dag/TaskGraph.tsx` + `TaskNode.tsx` + `dagLayout.ts`, `frontend/src/components/workflows/ActivityDetailPanel.tsx` with the additive `pinToDashboardSlot?: ReactNode` prop, and `frontend/src/components/workflows/ScheduleEditorModal.tsx`)
**Blocks:** DB-PRD-04
**Estimated effort:** 4–5 days

---

## 1. Context

The Dashboard Details page is where a user authors tasks, places widgets on a canvas, runs the plan, and sees the resolved artifacts. This PRD delivers that page end-to-end: the page shell, the split layout (task graph + canvas + task panel), the free-form drag-and-resize canvas, the four widget renderers, the Pin-to-Dashboard affordance on the task panel, the Run button and run-status polling, and the canvas-save debounce.

It **reuses three shared components** that A-PRD-06 ships:
- `frontend/src/components/dag/TaskGraph.tsx` (+ `TaskNode.tsx` + `dagLayout.ts`) — the DAG editor; consumed verbatim, driven by props (`tasks`, `edges`, `readOnly`, `onTaskAdd`, etc.).
- `frontend/src/components/workflows/ActivityDetailPanel.tsx` — the right-side task-edit panel, originally from Calendar PRD-3 and relocated to `components/workflows/` by A-PRD-06. This PRD passes the additive `pinToDashboardSlot?: ReactNode` prop with `<PinToDashboardPicker />` to render the Pin-to-Dashboard affordance; the panel collapses the slot region when the prop is absent (Automations / Calendar callers).
- `frontend/src/components/workflows/ScheduleEditorModal.tsx` — the schedule modal; consumed verbatim with the same prop contract A-PRD-06 publishes.

**No DAG re-implementation, no panel fork, no schedule-modal fork.** This PRD owns only `<PinToDashboardPicker />` (the slot value) and the canvas + widgets.

When the user clicks "+ Add Task" in the shared `TaskGraph` and selects `assignee_type="data_pipeline"`, the side-panel surfaces DP-PRD-04's pipeline-job picker + custom-job authoring — same flow as on the Automation Details page (A-PRD-06).

## 2. Scope

### In scope
- `DashboardDetailsPage` at `/performance/dashboards/{plan_id}` (replaces the DB-PRD-02 stub)
- Split layout: DAG on top, canvas on bottom, right-side task panel — with a resizable vertical divider (drag to reassign top/bottom split ratio)
- Header: back link, title (editable inline), status badges, schedule summary, Run button, Schedule modal entry, More menu (Delete, future Duplicate)
- Free-form canvas: absolute-positioned placements, drag-to-move, corner-handle resize, 8-px grid snap, collision OK (overlapping widgets allowed per Figma)
- **Install runtime deps** — `react-vega@^8`, `vega-lite@^6`, `vega@^6`. Production frontend currently ships `recharts` only; these are net-new packages. (AH-PRD-04's data-visualization spec calls them out as "renderer not yet on `main`"; this PRD is the first consumer to land them.)
- Four widget renderers:
  - **TextWidget** — markdown rendered via `react-markdown` + `rehype-raw`
  - **VisualizationWidget** — Vega-Lite spec via `react-vega`, honors `view_override` (bar / line / area / point / arc / table) by overriding `mark.type` at render time, honors `color` and `show_data_labels`
  - **TableWidget** — CSV fetched via `download_url`, parsed via `papaparse` client-side, rendered via the existing `DataTable` component
  - **FileWidget** — fallback for `image` / `document` / `video` / `audio` / `html` / `other`; shows filename + size + download button (signed URL)
- **`LineChart` adapter widget** at `frontend/src/components/dashboards/widgets/LineChart.tsx` — thin wrapper around `VisualizationWidget` with a fixed Vega-Lite line-chart spec. Prop contract (locked, consumed by PE-PRD-02 trendlines): `{data: TrendlinePoint[], xKey: string, yKey: string, partialFlagKey?: string, width: number, height: number}`. When `partialFlagKey` is provided, rows where `row[partialFlagKey] === true` render with a dashed segment (the "current in-progress week" affordance for PE-PRD-02). Does not consume `DashboardArtifact` directly — the adapter is a pure data-in / chart-out renderer reusable outside the canvas. Has its own export so PE-PRD-02 can import without dragging in canvas dependencies.
- Status indicator per widget: `fresh` (no badge), `disconnected` (unlink icon + tooltip), `pending` (spinner + "Task hasn't produced this output yet"). (No `stale` status — see DB-PRD-01 §4.7 rationale.)
- Pin-to-Dashboard picker rendered as the `pinToDashboardSlot` slot value in A-PRD-06's shared `ActivityDetailPanel` — opens a dropdown of the selected task's `output_config.expected_file_types`; clicking one adds a placement at an empty canvas location. The picker component itself (`<PinToDashboardPicker />`) is owned by this PRD; the slot mechanism is owned by A-PRD-06.
- Run button: POSTs to `A-PRD-02`'s manual trigger; polls `GET /dashboards/{plan_id}` every 2 s until `latest_run.status` is terminal; disables during in-flight
- Canvas PUT: debounced 500 ms after last drag / resize event; flushes on `pointerup` and `beforeunload`
- Unit tests per widget renderer; Playwright E2E for the drag / run / refresh flow

### Out of scope
- Real-time artifact streaming during a run (widgets stay on prior-run data until the run completes)
- Drill-down interactions between widgets
- Canvas undo/redo
- Widget-level configuration UI beyond `view_override` / `color` / `show_data_labels` already in the placement model
- Extensions (pre-built dashboard templates)

## 3. Dependencies

- **DB-PRD-01:** `GET /api/v1/dashboards/{account_id}/{plan_id}` (enriched response), `PUT /placements`, `DELETE`. Payload resolution rules (inline vs. signed URL) are owned there.
- **DB-PRD-02:** already registered the route and published the stub; this PRD replaces the stub component.
- **PR-PRD-01:** `PUT /api/v1/plans/{account_id}/{plan_id}` (for plan-title edits) and `PATCH .../tasks/{task_id}` (for task edits). Used by the task panel.
- **A-PRD-01:** `PATCH /api/v1/automations/{account_id}/{plan_id}/recurrence` (for schedule edits via the shared `ScheduleEditorModal`).
- **A-PRD-02:** `POST /api/v1/automations/{account_id}/{plan_id}/runs` (manual trigger). Same endpoint the Automations page uses.
- **A-PRD-06 (Automation Details page):** supplies three shared components:
  - **`frontend/src/components/dag/TaskGraph.tsx`** (+ `TaskNode.tsx` + `dagLayout.ts`) — DAG editor. Consumed verbatim, no fork.
  - **`frontend/src/components/workflows/ActivityDetailPanel.tsx`** — task-edit panel with the additive `pinToDashboardSlot?: ReactNode` prop that A-PRD-06 publishes for this PRD. This PRD passes `<PinToDashboardPicker />` as the slot value; A-PRD-06's own caller passes nothing and the slot region collapses.
  - **`frontend/src/components/workflows/ScheduleEditorModal.tsx`** — schedule editor modal. Consumed verbatim with the same prop contract A-PRD-06 ships.
  Coordination is one-way (A-PRD-06 publishes, this PRD consumes). All three components are at `frontend/src/components/{dag,workflows}/` to make their shared status visible at the file-tree level.
- **UI-PRD-01:** design tokens, shadcn primitives.
- **External:** `react-markdown`, `rehype-raw`, `papaparse`, `dagre` (via A-PRD-06's graph) — already present. **`react-vega@^8`, `vega-lite@^6`, `vega@^6`** are **new runtime deps** installed by this PRD (production frontend currently ships `recharts` only; AH-PRD-04 documents the renderer is not yet on `main`).
- **Existing files to study:**
  - `docs/figma-export/src/app/pages/performance/DashboardDetailsPage.tsx` — reference UX (rebuild in Soft Maximalism, not literal copy)
  - `docs/figma-export/src/app/components/DashboardCanvas.tsx` — reference canvas mechanics
  - `docs/figma-export/src/app/components/dashboard/ArtifactRenderer.tsx` — reference widget renderers
  - `frontend/src/pages/workflows/AutomationDetailsPage.tsx` (A-PRD-06 target) — pattern for the task-graph + task-panel integration

## 4. Data contract (consumed + client-side derived)

### Consumed from DB-PRD-01

```typescript
export interface DashboardGetResponse {
  plan: ProjectPlan;                     // full plan with tasks + dashboard_placements + schedule
  latest_run: PlanRun | null;
  artifacts: DashboardArtifact[];
}

export interface DashboardArtifact {
  placement_id: string;
  task_id: string;
  file_type: OutputFileType;
  status: 'fresh' | 'disconnected' | 'pending';     // three values, not four — see DB-PRD-01 §4.7
  inline_payload: Record<string, unknown> | null;   // shape depends on file_type
  download_url: string | null;                      // 1-hour signed URL for large artifacts
  updated_at: string | null;
  artifact_id: string | null;
}
```

### Client-side derived types

```typescript
// Per-placement render state, combining placement layout + resolved artifact
export interface CanvasTile {
  placement: DashboardPlacement;
  artifact: DashboardArtifact;
}

export type DragMode = 'idle' | 'moving' | 'resizing';

export interface DragState {
  mode: DragMode;
  placement_id: string | null;
  origin_x: number;
  origin_y: number;
  pointer_start: { x: number; y: number };
}
```

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `frontend/src/pages/performance/DashboardDetailsPage.tsx` — replaces the stub |
| Create | `frontend/src/components/dashboards/DashboardCanvas.tsx` — positioning, drag, resize, grid-snap |
| Create | `frontend/src/components/dashboards/CanvasTile.tsx` — wrapper around each widget with status badge + remove button |
| Create | `frontend/src/components/dashboards/widgets/TextWidget.tsx` |
| Create | `frontend/src/components/dashboards/widgets/VisualizationWidget.tsx` |
| Create | `frontend/src/components/dashboards/widgets/TableWidget.tsx` |
| Create | `frontend/src/components/dashboards/widgets/FileWidget.tsx` |
| Create | `frontend/src/components/dashboards/PinToDashboardPicker.tsx` — task-panel action |
| Consume (no edits) | `frontend/src/components/workflows/ActivityDetailPanel.tsx` (A-PRD-06) — pass `pinToDashboardSlot={<PinToDashboardPicker task={selectedTask} />}` from this page. A-PRD-06 owns the prop and the slot rendering location; this PRD only supplies the slot value. |
| Install | `react-vega@^8`, `vega-lite@^6`, `vega@^6` via `package.json` (new runtime deps; lockfile updated in the same PR) |
| Create | `frontend/src/components/dashboards/widgets/LineChart.tsx` — adapter for PE-PRD-02 (prop contract `{data, xKey, yKey, partialFlagKey?, width, height}`) |
| Create | `frontend/src/components/dashboards/widgets/__tests__/LineChart.test.tsx` |
| Create | `frontend/src/hooks/useDashboardDetails.ts` — TanStack Query (10-second stale while fresh; 2-second poll while a run is in-flight) |
| Create | `frontend/src/hooks/useDebouncedPlacementsPut.ts` — 500 ms debounce + beforeunload flush |
| Create | `frontend/src/services/dashboardsApi.ts` — extend with `getDashboardDetails`, `putPlacements`, `deleteDashboard` |
| Create | `frontend/src/components/dashboards/__tests__/DashboardCanvas.test.tsx` |
| Create | `frontend/src/components/dashboards/__tests__/widgets/*.test.tsx` (one per widget) |
| Create | `frontend/e2e/dashboards-pin-run-refresh.spec.ts` |

### Canvas mechanics

**Grid snap.** All placement coordinates are multiples of 8 pixels. Drag and resize round to the nearest 8 at `pointermove` time; persisted values are the rounded ones.

**Drag model.** A single shared `DragState` hook in `DashboardCanvas` handles both move and resize. `pointerdown` on the tile body → `mode="moving"`. `pointerdown` on the corner handle → `mode="resizing"`. `pointermove` updates the active placement's `x/y` or `w/h` in local state. `pointerup` flushes the change to the debounced PUT.

**Empty-canvas placeholder.** When `plan.dashboard_placements.length === 0`, the canvas shows an illustration + "Pin task outputs from the graph above to build your dashboard" + an arrow pointing up to the DAG view.

**Adding a placement.** Triggered from `PinToDashboardPicker`:
1. User clicks a task node in the shared `TaskGraph` → the shared `ActivityDetailPanel` (A-PRD-06) opens for that task.
2. Because this page passes `pinToDashboardSlot={<PinToDashboardPicker task={selectedTask} />}` to `ActivityDetailPanel`, the panel renders the picker in its slot region. (The Automation Details page does not pass the prop, so the slot region collapses there.)
3. If the task has `output_config.enabled=true`, `PinToDashboardPicker` shows a button that opens a dropdown of `task.output_config.expected_file_types`; the user clicks one.
4. Client generates a new `placement_id` (UUID), chooses an empty canvas location (see below), appends to local placements, and triggers the debounced PUT.

**Empty-location heuristic.** Iterate an 8-px grid scanning left-to-right, top-to-bottom, looking for a `320 × 240` rectangle with no overlap against existing placements. If the canvas is full, append at the bottom (increasing canvas height as needed).

**Removing a placement.** Each `CanvasTile` has an `X` button (editor role+); click → confirmation toast → local splice → debounced PUT.

### Widget renderers

All widgets receive:
```typescript
interface WidgetProps {
  artifact: DashboardArtifact;
  placement: DashboardPlacement;      // for view_override, color, show_data_labels
  width: number;                      // from placement.w
  height: number;                     // from placement.h
}
```

**TextWidget.** Renders `artifact.inline_payload.content` as Markdown via `react-markdown` + `rehype-raw`. Scrolls internally if content overflows.

**VisualizationWidget.** Takes `artifact.inline_payload.spec` (inlined) or fetches from `download_url` (rare — specs are small). Applies `placement.view_override` by cloning the spec and overriding `mark.type`. Applies `placement.color` as `config.range.category[0]` if set. Applies `placement.show_data_labels` by toggling `mark.text` layers. Renders via `<VegaLite spec={modifiedSpec} width={...} height={...} actions={false} theme={currentTheme} />`.

**TableWidget.** Fetches `artifact.download_url`, parses via `papaparse`. First-row-as-header default. Renders via the existing `DataTable` component with virtualization (for CSVs with >1000 rows). Shows parse errors inline.

**FileWidget.** Renders a card with filename, MIME type, size (if available), and a "Download" button linking to `download_url`. For `file_type="image"`, additionally renders the image inline via `<img src={download_url}>`.

### Status indicator overlay

Each `CanvasTile` shows a small status badge in the top-right corner based on `artifact.status`:

| Status | Badge |
|---|---|
| `fresh` | (none) |
| `disconnected` | Broken-link icon; tooltip: "This task no longer produces [file_type]. Edit the task or remove this widget." |
| `pending` | Spinner; tooltip: "Task hasn't produced [file_type] yet. Run the dashboard to generate it." |

The badge is `editor`-clickable to remove the widget when `status="disconnected"`. (No `stale` row — see DB-PRD-01 §4.7 rationale; placements where the latest run failed to re-emit render as `pending` and the user re-runs to refresh.)

### Run button + polling

- Disabled when no `latest_run` is terminal-state AND a run is in-flight
- On click: POST to `A-PRD-02`'s manual trigger endpoint; optimistically show "running" status on all pending widgets
- Poll `GET /dashboards/{plan_id}` every 2 s until `latest_run.status ∈ {"complete", "failed", "cancelled"}`
- On terminal state: stop polling, final GET fetches fresh artifacts, widgets re-render

### Title edit

Plan title is editable inline in the header. Click-to-edit → blur or Enter submits → `PUT /api/v1/plans/{account_id}/{plan_id}` (PR-PRD-01). Optimistic local update; rollback on 4xx.

## 6. API contract (consumed)

| Method | Path | Purpose | Owner |
|---|---|---|---|
| `GET` | `/api/v1/dashboards/{account_id}/{plan_id}` | Page load + poll | DB-PRD-01 |
| `PUT` | `/api/v1/dashboards/{account_id}/{plan_id}/placements` | Canvas save | DB-PRD-01 |
| `DELETE` | `/api/v1/dashboards/{account_id}/{plan_id}` | Delete action | DB-PRD-01 |
| `PUT` | `/api/v1/plans/{account_id}/{plan_id}` | Title edit | PR-PRD-01 |
| `PATCH` | `/api/v1/plans/{account_id}/{plan_id}/tasks/{task_id}` | Task edits | PR-PRD-01 |
| `POST` | `/api/v1/automations/{account_id}/{plan_id}/runs` | Run Now | A-PRD-02 |
| `PATCH` | `/api/v1/automations/{account_id}/{plan_id}/recurrence` | Schedule edit | A-PRD-01 |

## 7. Acceptance criteria

1. Navigating to `/performance/dashboards/{plan_id}` loads the page and issues a single `GET /dashboards/{plan_id}`. Split layout renders with task graph on top, canvas below, no task-panel sidebar until a task is clicked.
2. Clicking a task node produces the shared `ActivityDetailPanel` on the right with the Pin-to-Dashboard picker rendered in the `pinToDashboardSlot` region (because this page passes the slot value). The Automation Details page (A-PRD-06) does not pass the prop, so its slot region collapses — no regression for the Automations consumer.
3. Clicking "Pin to dashboard" → picker shows the task's `expected_file_types` → selecting one adds a new `CanvasTile` at the next empty grid location with the appropriate widget renderer.
4. Dragging a tile updates `x/y` locally in real time; on `pointerup`, a debounced `PUT /placements` fires within 500 ms with the full placements array.
5. Resizing a tile from its corner handle updates `w/h` live; snapped to 8 px; persisted on `pointerup`.
6. Two drags within 500 ms coalesce into a single PUT carrying the final state.
7. Closing the tab while a PUT is debounced flushes the pending PUT via `beforeunload`.
8. The Run button POSTs a manual trigger, the button transitions to "Running (00:12)" with an elapsed counter, polling starts at 2 s intervals.
9. On run completion, the final GET arrives and every widget with a new artifact transitions from `pending` to `fresh` (no badge).
10. A text artifact ≤64 KB renders inline via `TextWidget` (no network fetch beyond the initial GET).
11. A Vega-Lite visualization renders via `react-vega`; `view_override="line"` on a bar-chart spec causes the rendered chart to be a line chart.
12. A CSV artifact loads via `download_url`, parses, renders as a sortable / paginated `DataTable`.
13. A task's `output_config.enabled` flipped to `false` causes placements referencing it to render the `disconnected` badge; clicking "Remove" on the tile removes the placement and fires a PUT.
14. A 65 KB text artifact is served via `download_url` (not inline); `TextWidget` fetches the URL before rendering.
15. Viewer-role users see the canvas but cannot add/move/resize/remove tiles, cannot edit the title, and the Run / Delete buttons are disabled with tooltips.
16. Cross-account navigation returns the page to `/accounts` with a toast.
17. Placement limit: attempting to add a 101st placement shows a toast ("Dashboards support up to 100 widgets; remove an existing widget to add a new one.").
18. **`LineChart` adapter:** importing `<LineChart data={…} xKey="week" yKey="value" partialFlagKey="is_partial" width={600} height={240} />` from `frontend/src/components/dashboards/widgets/LineChart.tsx` renders a Vega-Lite line chart. When a row has `is_partial === true`, the segment leading to that row renders dashed; remaining rows render solid. The component is importable standalone (no canvas dependencies pulled in) so PE-PRD-02 can mount it inside its trendline adapter.
19. `npm run build` / `npm run typecheck` / `npm run format.fix` clean — including the three new runtime deps (`react-vega`, `vega-lite`, `vega`) resolving without peer-dep warnings.
20. Playwright `dashboards-pin-run-refresh.spec.ts` passes.

## 8. Test plan

**Unit tests — widgets** (`widgets/*.test.tsx`):
- `TextWidget`: renders markdown; honors width/height; handles empty content
- `VisualizationWidget`: renders a Vega-Lite bar chart; `view_override="line"` rewrites `mark.type`; `color` override applied; missing spec renders an error state
- `LineChart` adapter: passes data through to a fixed Vega-Lite line spec; `partialFlagKey` produces dashed segments; missing `partialFlagKey` produces all-solid; standalone import does not require `<DashboardCanvas>` context
- `TableWidget`: parses a 100-row CSV from `download_url`; handles 10k-row CSV (virtualized); surfaces parse errors
- `FileWidget`: renders download card with filename + size; for `file_type="image"`, renders `<img>` inline

**Unit tests — canvas** (`DashboardCanvas.test.tsx`):
- Drag: pointerdown → move → up updates `x/y` with 8-px snap
- Resize: pointerdown on corner → move → up updates `w/h` with 8-px snap and minimums enforced
- Remove: click X → splice local state → PUT fires
- Empty-canvas placeholder shown when 0 placements
- Empty-location heuristic: 3 existing placements → new placement lands in the first free grid cell

**Unit tests — hooks:**
- `useDebouncedPlacementsPut`: three calls within 500 ms → one PUT; the PUT carries the last-seen array
- `useDashboardDetails`: when `latest_run.status === "running"`, polling interval is 2 s; when terminal, polling stops

**Playwright** (`dashboards-pin-run-refresh.spec.ts`):
- Log in → create dashboard → add a task with `output_config.enabled=true`, `expected_file_types=["text"]` → pin "text" output to dashboard → Run Now → wait for completion → verify `TextWidget` renders content from the run's artifact
- Re-run → verify `updated_at` on the widget ticks forward
- Flip `output_config.enabled=false` via task edit → refresh → widget shows `disconnected` badge

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| Vega renderer memory footprint with 50+ charts on one canvas | Virtualize off-screen tiles (IntersectionObserver — render chart only when visible). Noted as a DB-PRD-04 perf test. |
| CSV too large to render as a table (>100 MB) | Fail gracefully in `TableWidget` with a "File too large to preview; [Download]" message. The `download_url` still works. |
| Signed URL expires while the tab is open | On 403 from `download_url`, re-fetch the GET (which regenerates URLs). If the widget is mid-render, show a transient "Refreshing..." state. |
| Drag performance with 100 tiles | Use CSS transforms for the dragged tile (not layout writes); only commit x/y on `pointerup`. Measured in DB-PRD-04. |
| User drags a tile off-screen (negative x) | Clamp to `x >= 0`, `y >= 0` at move time. |
| Pin-to-Dashboard picker on a task with `expected_file_types=[]` | Show "Configure task outputs first" with a link to the task-edit form. |
| A-PRD-06's `pinToDashboardSlot` prop on `ActivityDetailPanel` | Additive — the prop defaults to `undefined`, which collapses the slot region. No breaking change to A-PRD-06 / Calendar PRD-3 callers. |
| Dashboard with in-flight run opened in a second tab | Each tab polls independently; benign redundancy. Acceptable for v1. |

### Open questions

- **Tile aspect-ratio constraints?** Figma shows free aspect ratios. Enforce `w/h` minimums (64×64) and maximums (4000×4000) per DB-PRD-01 §4.3. No aspect lock.
- **Does clicking a widget focus the corresponding task in the DAG above?** Nice-to-have. Include if time; else defer. Low-risk addition.

### Resolved

- **Dashboards have one Run button — no separate Test Run.** Confirmed 2026-04-22. A-PRD-04's `is_test` mode is an Automations affordance for validating recipes before enabling recurring firing. Dashboards produce real artifacts on every run (that's the point), so the distinction doesn't apply. If a user needs `is_test` semantics for a dashboard-typed plan, they can hit `/api/v1/automations/{account_id}/{plan_id}/runs/test` directly — no UI surface for it.

## 10. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md)
- Foundation: [DB-PRD-01](./DB-PRD-01-data-model-and-api.md)
- Shell: [DB-PRD-02](./DB-PRD-02-dashboards-tab-and-list.md)
- Shared components: [A-PRD-06 Automation Details](../../automations/projects/A-PRD-06-automation-details-page.md)
- Figma reference: `docs/figma-export/src/app/pages/performance/DashboardDetailsPage.tsx`, `docs/figma-export/src/app/components/DashboardCanvas.tsx`, `docs/figma-export/src/app/components/dashboard/ArtifactRenderer.tsx`
- Design tokens: [UI-PRD-01](../../ui/projects/UI-PRD-01-design-system-foundation.md)
- CLAUDE.md rules in scope: C-1, C-5, C-6, C-8; T-2, T-6, T-8; G-2, G-3
