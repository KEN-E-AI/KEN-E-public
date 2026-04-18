# PRD-3 — Calendar Page Frontend

**Status:** Ready for development (after PRD-1 merges)
**Owner team:** Frontend
**Blocked by:** PRD-1 (consumes API + types)
**Parallel with:** PRDs 2, 4, 6
**Estimated effort:** 3–4 days

---

## 1. Context

Project plans need a visual interface where users can see all upcoming tasks on a calendar, drill into individual tasks, edit project-level metadata, and approve/reject/revise task work. The Figma design ("KEN-E UI V2 — Soft Maximalism") provides the calendar page already; this PRD adapts it to the KEN-E React codebase and renames its domain ("Tactic" → Task, "Tactic Group" → Project).

## 2. Scope

### In scope
- New `/calendar` route and sidebar nav entry
- `CalendarPage` with calendar view (default) and list view (toggle)
- `ActivityDetailPanel` right-slider for task details (read + edit)
- `ProjectEditDrawer` for project-level editing (replaces Figma `GroupEditDrawer`)
- React context + service + branded types for project plan state
- Filters: project, campaign, platform, status, assignee, tags
- Deep-link support: `/calendar?project={plan_id}&task={task_id}` opens the page with the right plan focused and the task panel open
- Chat integration: render `[View Plan](/calendar?project={plan_id})` markdown links from agent responses
- Component tests with `*.test.tsx`

### Out of scope
- Status-transition business logic on the backend (PRD-4 owns that — frontend just calls the PATCH endpoint)
- Notification deep-link wiring in `NotificationSidebar.tsx` (owned by PRD-4 since the notification category itself is added there)
- Anything that creates plans server-side (PRDs 1 + 2)

## 3. Dependencies

- **PRD-1:** consumes `/api/v1/plans/*` endpoints and the `ProjectPlan` / `PlanTask` shapes
- **Figma design:** [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism)
- **Existing files to study:**
  - `frontend/src/pages/Insights.tsx` (page → axios → branded type pattern)
  - `frontend/src/pages/Home.tsx` + `frontend/src/contexts/ChatContext.tsx` (context provider pattern)
  - `frontend/src/components/notifications/NotificationSidebar.tsx` (slider pattern)
  - `frontend/src/lib/api.ts` (axios client with Firebase token injection)
  - `frontend/src/App.tsx` (routing)

## 4. Data contract (TypeScript)

Branded types per CLAUDE.md C-5:

```ts
type PlanId = Brand<string, 'PlanId'>
type TaskId = Brand<string, 'TaskId'>
type AccountId = Brand<string, 'AccountId'>

type TaskStatus =
  | 'Draft'
  | 'Awaiting Approval'
  | 'Approved'
  | 'Rejected'
  | 'Revision Requested'
  | 'Complete'

type Platform =
  | 'Google Ads' | 'Meta Ads' | 'TikTok' | 'LinkedIn'
  | 'Mailchimp' | 'Instagram' | 'YouTube' | 'Display' | string

type PlanTask = {
  task_id: TaskId
  title: string
  description: string
  assignee_type: 'agent' | 'human'
  assignee_name: string
  status: TaskStatus
  depends_on: TaskId[]
  cost: number | null
  due_date: string | null         // ISO date
  launch_time_utc: string | null  // "HH:mm"
  launched_at: string | null      // ISO datetime
  platform: Platform | null
  tags: string[]
  estimated_effort: 'small' | 'medium' | 'large' | null
  completion_notes: string | null
  revision_comment: string | null
}

type ProjectPlan = {
  plan_id: PlanId
  account_id: AccountId
  title: string
  goal: string
  acceptance_criteria: AcceptanceCriterion[]
  tasks: PlanTask[]
  campaign: string | null
  tags: string[]
  status: 'draft' | 'active' | 'completed' | 'archived'
  // ...timestamps, version
}
```

Use `import type { … }` for all type-only imports per C-6.

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `frontend/src/pages/CalendarPage.tsx` |
| Create | `frontend/src/components/ActivityDetailPanel.tsx` |
| Create | `frontend/src/components/ProjectEditDrawer.tsx` |
| Create | `frontend/src/contexts/ProjectPlanContext.tsx` |
| Create | `frontend/src/services/projectPlanService.ts` |
| Create | `frontend/src/types/projectPlan.ts` |
| Modify | `frontend/src/App.tsx` — add `/calendar` route |
| Modify | `frontend/src/components/Sidebar.tsx` (or equivalent) — add calendar nav entry |
| Create | `frontend/src/pages/CalendarPage.test.tsx` |
| Create | `frontend/src/components/ActivityDetailPanel.test.tsx` |
| Create | `frontend/src/components/ProjectEditDrawer.test.tsx` |

### Page structure

**Calendar view (default):**
- Monthly grid; tasks placed on `due_date` cells
- Cell content: task title, platform badge (color-coded — see palette below), status badge, assignee badge
- `MonthYearPicker` for navigation (reuse existing component)
- Click a cell → opens `ActivityDetailPanel` with `?task=...` query param

**List view:**
- Sortable/filterable table — columns: title, project, campaign, platform, status, assignee, due date, launch time, cost, tags
- Toggle (radio buttons) at top-right with calendar view

**Filter bar:**
- Multi-select dropdowns: project, campaign, platform, status, assignee, tags

**Add button (top-right):**
- Dropdown: "Add Task" | "Add Project" — opens the appropriate drawer

### Platform color palette (from Figma)
| Platform | Color family |
|----------|--------------|
| Paid Search (Google Ads) | Oranges |
| Social (Meta, Instagram, TikTok, LinkedIn) | Blues |
| Email (Mailchimp) | Greens |
| Display | Purples |
| Content | Teals |

Map raw platform strings → color family in a pure helper to keep the component simple.

### Right-slider detail panel (`ActivityDetailPanel`)
Editable fields: title, status (dropdown of valid transitions), assignee, platform, cost, due date, launch time, tags. Read-only: dependencies (with status indicators), revision comment (when status is "Revision Requested"), completion notes, created/updated metadata.

### Project edit drawer (`ProjectEditDrawer`)
Project-level fields: title, goal, acceptance criteria, campaign, project-level tags, bulk task property editing (apply shared changes across selected tasks).

### Context (`ProjectPlanContext`)
Mirrors Figma `ActivitiesContext`:
- `plans`, `selectedPlanId`, `selectedTaskId`, filters
- `loadPlans(accountId)`, `selectPlan(planId)`, `selectTask(taskId)`, `updateTask(planId, taskId, patch)`
- Listens to `selectedOrgAccount` from `useAuth()` and reloads on account switch

### Service (`projectPlanService.ts`)
Thin axios wrapper around `/api/v1/plans/*` (PRD-1). Returns branded types (transformers in `lib/`).

### Chat link integration
The existing chat message renderer already supports markdown. When the planning agent (PRD-2) returns a message containing `[View Plan](/calendar?project=...)`, the renderer must convert it to a React Router `Link` (not an `<a href>`) so navigation stays SPA. If the renderer already handles internal markdown links, no change is needed; if not, add a `react-markdown` link override.

## 6. API contract

This PRD only consumes — no new endpoints. Calls:
- `GET /api/v1/plans/{account_id}` — list
- `GET /api/v1/plans/{account_id}/{plan_id}` — fetch
- `PATCH /api/v1/plans/{account_id}/{plan_id}/tasks/{task_id}` — task update
- `PUT /api/v1/plans/{account_id}/{plan_id}` — project update

(`/activate` and `/revision` are PRD-4; called from this UI but defined there.)

## 7. Acceptance criteria

1. Navigating to `/calendar` renders the calendar view with all plans for the current account
2. Toggling to list view shows the task table; columns are sortable and filterable
3. Filter selections persist in URL query params (so deep links work)
4. Clicking a task cell opens the detail panel and updates the URL (`?task=...`)
5. Editing a task field calls `PATCH` and updates state optimistically; rollback on failure
6. Status dropdown only shows valid next transitions (Draft → Awaiting Approval → Approved → Complete; with Rejected and Revision Requested branches)
7. The `ProjectEditDrawer` opens via "Edit Project" or the Add Project button
8. Account switch (via header) clears state and reloads plans for the new account
9. A chat message containing `[View Plan](/calendar?project=p_123)` produces an in-app SPA link, not a full-page reload
10. All component tests pass; `npm run typecheck` and `npm run format.fix` pass

## 8. Test plan

**Component tests:**
- `CalendarPage.test.tsx`: renders both view modes, toggles between them, applies filters, opens detail panel on cell click, reflects URL state
- `ActivityDetailPanel.test.tsx`: renders task fields, calls PATCH on edit, status dropdown shows valid transitions only, shows revision comment when status is "Revision Requested"
- `ProjectEditDrawer.test.tsx`: renders project fields, calls PUT on save, bulk-edit applies to selected tasks
- `ProjectPlanContext.test.tsx`: reloads on account switch, clears selected task on plan deselect

**Manual smoke (record steps for PRD-5):**
- Open `/calendar`, switch view modes, apply filters, deep-link a specific task, edit a task, edit a project, account switch

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| Calendar grid performance with hundreds of tasks per month | Virtualize cells; collapse overflow with "+N more" badge |
| Optimistic updates conflict with server validation | Roll back local state on `4xx` and surface a toast |
| Color palette accessibility (contrast) | Use the existing design-system tokens; verify with axe DevTools |
| Date timezone handling — frontend displays in account TZ but `due_date` is UTC date | Pick a stance (display as UTC vs. account-local) and document. Recommendation: display dates in UTC for consistency with `launch_time_utc`. |
| Markdown link `<Link>` override not applied | If renderer doesn't support overrides, fall back to a custom click handler that intercepts internal hrefs |

## 10. Reference

- Parent plan: [`../project-planning-implementation-plan.md`](../project-planning-implementation-plan.md) §Frontend: Calendar Page, §Implementation Phases (Phase 3)
- Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism); key components to adapt: `CalendarPage.tsx`, `ActivityDetailPanel.tsx`, `GroupEditDrawer.tsx` (→ `ProjectEditDrawer`), `calendarData.ts`, `ActivitiesContext.tsx`
- Pattern files: `frontend/src/pages/Insights.tsx`, `frontend/src/pages/Home.tsx`, `frontend/src/contexts/ChatContext.tsx`
- CLAUDE.md rules in scope: C-5 (branded types), C-6 (`import type`), C-8 (`type` over `interface`), G-2, G-3 (frontend gates), T-2 (tests)
