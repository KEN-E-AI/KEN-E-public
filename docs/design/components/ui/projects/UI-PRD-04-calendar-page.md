# UI-PRD-04 — Calendar Page

**Status:** Blocked on UI-PRD-01
**Owner team:** Frontend
**Blocked by:** UI-PRD-01
**Parallel with:** UI-PRD-05, UI-PRD-06, UI-PRD-07
**Estimated effort:** 4–5 days

---

## 1. Context

Release 2 introduces project planning. The primary UI is a calendar view at `/calendar` where users see tasks scheduled on their due date, drill into task details, and edit project metadata. This PRD builds the page shell against mocked data so `PR-PRD-03` can wire it to `/api/v1/plans/*` without also doing the design migration.

**Scope boundary:** this PRD owns the route, page shell (calendar + list views), detail panel, edit drawer, and mocked data rendering. `PR-PRD-03` owns `ProjectPlanContext`, `projectPlanService`, branded types, optimistic updates, and integration tests.

## 2. Scope

### In scope
- New `/calendar` route under `LayoutC`
- `CalendarPage` with calendar view (default) and list view (toggle)
- Filter bar: project, campaign, platform, status, assignee, tags
- `ActivityDetailPanel` right-slider for task details (read-only in this PRD; editable fields wired by PR-PRD-03)
- `ProjectEditDrawer` for project-level editing (read-only in this PRD; save wired by PR-PRD-03)
- Platform color palette per Figma (Paid Search / Social / Email / Display / Content color families)
- `MonthYearPicker` month navigation
- "Add" dropdown (Add Task / Add Project) — buttons are present; behavior is mocked
- Deep-link URL structure (`?project=` / `?task=`) — params are read; click handlers update params; data refresh is PR-PRD-03's
- Sidebar nav entry for Calendar
- Component tests for page shell and panels

### Out of scope
- All data wiring — owned by PR-PRD-03
- `ProjectPlanContext`, `projectPlanService`, branded types — owned by PR-PRD-03 (UI-PRD-04 uses a mock context)
- Status-transition logic — owned by PR-PRD-04
- Chat-link integration (`[View Plan](/calendar?project=...)` SPA rendering) — owned by PR-PRD-03

## 3. Dependencies

- **UI-PRD-01:** `LayoutC`, shadcn primitives (Dialog, Sheet, Popover, DropdownMenu, Tabs, Table, Badge, Select)
- **Downstream consumer:** [`PR-PRD-03`](../../project-tasks/projects/PR-PRD-03-calendar-page-frontend.md) — replaces the mock context with real wiring
- **Existing files to study:**
  - `frontend/src/components/ui/calendar.tsx` — shadcn date primitive (after UI-PRD-01 re-skin)
  - `frontend/src/components/notifications/NotificationSidebar.tsx` — slider pattern reference
- **Figma nodes:** CalendarPage, ActivityDetailPanel, GroupEditDrawer (→ rename to ProjectEditDrawer), MonthYearPicker

## 4. Data contract (TypeScript)

This PRD defines mock shapes matching the Figma data. PR-PRD-03 will replace these with branded types from `frontend/src/types/projectPlan.ts`.

```ts
// frontend/src/pages/calendar/mockData.ts  (DELETED when PR-PRD-03 lands)

export type MockTaskStatus =
  | "Draft" | "Awaiting Approval" | "Approved"
  | "Rejected" | "Revision Requested" | "Complete";

export type MockPlanTask = {
  task_id: string;
  title: string;
  status: MockTaskStatus;
  due_date: string | null;
  platform: string | null;
  assignee_name: string;
  // …remaining fields match Figma's calendarData.ts
};

export type MockProjectPlan = {
  plan_id: string;
  title: string;
  tasks: MockPlanTask[];
  // …
};
```

The component props for `CalendarPage`, `ActivityDetailPanel`, and `ProjectEditDrawer` accept a generic `data` prop plus callbacks. PR-PRD-03 swaps the mock for real data; prop signatures stay stable.

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `frontend/src/pages/CalendarPage.tsx` |
| Create | `frontend/src/pages/calendar/CalendarView.tsx` — monthly grid |
| Create | `frontend/src/pages/calendar/ListView.tsx` — sortable/filterable table |
| Create | `frontend/src/pages/calendar/FilterBar.tsx` |
| Create | `frontend/src/components/calendar/ActivityDetailPanel.tsx` |
| Create | `frontend/src/components/calendar/ProjectEditDrawer.tsx` |
| Create | `frontend/src/components/calendar/MonthYearPicker.tsx` (if not already in UI-PRD-01 shared components) |
| Create | `frontend/src/pages/calendar/mockData.ts` — DELETED by PR-PRD-03 |
| Create | `frontend/src/pages/calendar/platformColors.ts` — pure helper |
| Modify | `frontend/src/App.tsx` — add `/calendar` route |
| Modify | `frontend/src/components/layout/Sidebar.tsx` — add Calendar nav entry |
| Create | colocated `*.test.tsx` for each new component |

### Page structure

- **View toggle (top-right):** radio buttons — Calendar / List.
- **Filter bar:** multi-select dropdowns (Project / Campaign / Platform / Status / Assignee / Tags). Selections persist in URL query params.
- **Calendar view:** monthly grid with platform-colored task chips on each day. Clicking opens `ActivityDetailPanel`.
- **List view:** sortable columns (title, project, campaign, platform, status, assignee, due date, launch time, cost, tags).
- **Add dropdown (top-right):** "Add Task" / "Add Project" — opens the appropriate drawer (mocked).

### Platform color palette

Encode as a pure helper in `platformColors.ts`:

| Platform | Color family |
|----------|--------------|
| Paid Search (Google Ads) | Oranges |
| Social (Meta, Instagram, TikTok, LinkedIn) | Blues |
| Email (Mailchimp) | Greens |
| Display | Purples |
| Content | Teals |

Verify contrast via axe DevTools against the Soft Maximalism tokens.

## 6. API contract

N/A — this PRD consumes no APIs. `PR-PRD-03` wires `/api/v1/plans/*`.

## 7. Acceptance criteria

1. Sidebar has a Calendar entry; clicking it navigates to `/calendar`.
2. Calendar view renders the monthly grid with mocked tasks chipped on the correct days.
3. Toggle to list view renders the table; columns sort and filter correctly.
4. Filter selections persist in URL query params (round-trips across browser back / forward).
5. Clicking a task chip opens `ActivityDetailPanel` with `?task=…` in the URL; the panel displays mocked task fields.
6. Clicking "Edit Project" opens `ProjectEditDrawer` with mocked project fields.
7. Month navigation via `MonthYearPicker` updates the visible month.
8. Platform color palette matches Figma; axe DevTools reports no contrast violations at AA.
9. Dark mode renders correctly.
10. Component tests pass; `npm run typecheck`, `npm run format.fix`, `npm run build`, `npm test` pass.

## 8. Test plan

**Component tests:**
- `CalendarPage.test.tsx`: renders both view modes, toggles between them, filter bar updates URL params
- `CalendarView.test.tsx`: renders chips on correct dates; click opens panel
- `ListView.test.tsx`: column sort + multi-filter combinations
- `ActivityDetailPanel.test.tsx`: renders mocked fields; close button clears `?task=`
- `ProjectEditDrawer.test.tsx`: renders mocked project fields
- `platformColors.test.ts`: each known platform maps to the expected color family; unknowns fall back to a neutral family

**Manual smoke (recorded for PR-PRD-03 regression):**
- Open `/calendar`, switch view modes, apply filters, deep-link a task, open + close both drawers

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| Mock data structure drifts from PR-PRD-01's final Pydantic model | Use the current Figma `calendarData.ts` as the source; PR-PRD-03 is responsible for mapping server types to match these props |
| Calendar grid performance with dense task counts | Virtualize cells; collapse overflow with "+N more" badge |
| Prop signatures change between UI-PRD-04 and PR-PRD-03 | Freeze signatures in UI-PRD-04 code review; changes require follow-up PRD |
| Color contrast on chips against light + dark backgrounds | Test both modes; adjust token saturation if needed |

### Open questions

- **Q:** Should the calendar view honor user's TZ or UTC? → Per PR-PRD-03 recommendation: **UTC for consistency with `launch_time_utc`**; PR-PRD-03 can revisit.
- **Q:** Does the Add Task / Add Project dropdown create plans locally or call an API? → Out of scope — owned by PR-PRD-03 / PR-PRD-04.

## 10. Reference

- Parent component: [`../README.md`](../README.md)
- Sibling: [`UI-PRD-01-design-system-foundation.md`](./UI-PRD-01-design-system-foundation.md)
- Downstream consumer: [`PR-PRD-03`](../../project-tasks/projects/PR-PRD-03-calendar-page-frontend.md)
- Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) — CalendarPage, ActivityDetailPanel, GroupEditDrawer, MonthYearPicker
- CLAUDE.md rules in scope: C-5, C-6, C-8; T-2; G-2, G-3
