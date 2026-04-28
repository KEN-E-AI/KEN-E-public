# PRD-3 — Calendar Page Frontend

**Status:** Ready for development (after PR-PRD-01 and PR-PRD-07 merge)
**Owner team:** Frontend
**Blocked by:** PR-PRD-01 (consumes API + types); PR-PRD-07 (consumes the multi-category `PlanTask` contract, the orphan-task endpoints, and the batch-create / group-edit endpoints that the Figma calendar page exercises)
**Parallel with:** PR-PRDs 2, 4, 6 (after deps met)
**Estimated effort:** 3–4 days

---

## 1. Context

Project plans need a visual interface where users can see all upcoming activities on a calendar, drill into individual ones, edit project-level metadata, and approve/reject/revise work. The Figma design ("KEN-E UI V2 — Soft Maximalism") provides the calendar page already; this PRD adapts it to the KEN-E React codebase and renames its domain ("Tactic" → Task, "Tactic Group" → Project).

The activity model the calendar renders is delivered by [PR-PRD-07](./PR-PRD-07-calendar-activities.md): every `PlanTask` carries a `category` (`task` / `promotion` / `holiday` / `event`), optional sparse fields (e.g., `promotion_type`, `holiday_type`, `discount_details`, `region`), task-level recurrence, an `unscheduled` flag, and `owner_email` distinct from `assignee_name`. Campaigns are first-class entities owned by [PR-PRD-08](./PR-PRD-08-campaign-management.md), referenced by `campaign_id`. PR-PRD-03 consumes both contracts; it does not extend either.

## 2. Scope

### In scope
- New `/calendar` route and sidebar nav entry
- `CalendarPage` with calendar view (default) and list view (toggle); per-category color/icon rendering for the four activity categories
- Sparse-field rendering in calendar cells + list rows (promotion discount badge, holiday tag, recurrence indicator)
- Unscheduled Tasks panel (orphan-task list, per `accounts/{account_id}/orphan_tasks/*`) with attach-to-existing-plan and attach-to-new-plan dialogs
- `ActivityDetailPanel` right-slider for task details (read + edit), including category-specific sparse-field editors
- `ProjectEditDrawer` for project-level editing (replaces Figma `GroupEditDrawer`)
- Batch Activity Wizard (multi-day create with per-day overrides) wiring `POST .../tasks/batch`
- Group Edit drawer wiring `PATCH .../tasks:group-edit`
- Inline campaign-create from the activity drawer (consumes PR-PRD-08's `POST /campaigns`)
- React context + service + branded types for project plan state
- Filters: project, campaign, platform, channel, status, assignee, owner, category, task_type, date range, tags
- Deep-link support: `/calendar?project={plan_id}&task={task_id}` opens the page with the right plan focused and the activity panel open
- Chat integration: render `[View Plan](/calendar?project={plan_id})` markdown links from agent responses
- Component tests with `*.test.tsx`

### Out of scope
- Status-transition business logic on the backend (PRD-4 owns that — frontend just calls the PATCH endpoint)
- Role gating on transitions (DM-PRD-07 — frontend reflects 403s as toasts but does not enforce)
- Notification deep-link wiring in `NotificationSidebar.tsx` (owned by PRD-4 since the notification category itself is added there)
- Anything that creates plans server-side (PRDs 1 + 2)
- Schedule-occurrence expansion endpoint (`POST /v1/schedules/preview`) — owned by [A-PRD-2](../../automations/projects/A-PRD-02-recurring-scheduler.md); this PRD consumes it to render task-level recurrence on the calendar grid

## 3. Dependencies

- **PR-PRD-01:** consumes `/api/v1/plans/*` endpoints and the base `ProjectPlan` / `PlanTask` shapes (incl. `Failed` / `Blocked` `TaskStatus` values)
- **PR-PRD-07 (hard prerequisite):** consumes the multi-category `PlanTask` extensions (`category`, `channel`, `task_type`, `owner_email`, `unscheduled`, task-level recurrence, sparse promotion/holiday fields), the `/api/v1/orphan-tasks/*` endpoints (list / attach-to-plan / attach-to-new-plan / detach), the `/api/v1/plans/.../tasks/batch` and `:group-edit` endpoints, and the extended list-endpoint filter set
- **PR-PRD-08:** consumes `/api/v1/campaigns/*` for the campaign picker + inline-create flow; persists `campaign_id` on activities
- **A-PRD-02 (consumed):** `POST /v1/schedules/preview` for expanding task-level recurrence in the calendar grid
- **Figma design:** [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism)
- **Existing files to study:**
  - `frontend/src/pages/Insights.tsx` (page → axios → branded type pattern)
  - `frontend/src/pages/Home.tsx` + `frontend/src/contexts/ChatContext.tsx` (context provider pattern)
  - `frontend/src/components/notifications/NotificationSidebar.tsx` (slider pattern)
  - `frontend/src/lib/api.ts` (axios client with Firebase token injection)
  - `frontend/src/App.tsx` (routing)
  - `docs/figma-export/src/app/data/calendarData.ts` (`CalendarActivity`, category enums, sparse field shapes)
  - `docs/figma-export/src/app/data/standaloneTasks.ts` (orphan-task pattern)
  - `docs/figma-export/src/app/pages/CalendarPage.tsx` (batch wizard, group edit, Unscheduled panel, Move-to-Project dialog)

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
  | 'Failed'
  | 'Blocked'

type ActivityCategory = 'task' | 'promotion' | 'holiday' | 'event'

type Platform =
  | 'Google Ads' | 'Meta Ads' | 'TikTok' | 'LinkedIn'
  | 'Mailchimp' | 'Instagram' | 'YouTube' | 'Display' | string

type PromotionType =
  | 'Discount' | 'Bundle' | 'Free Trial' | 'BOGO'
  | 'Flash Sale' | 'Seasonal' | 'Launch Offer'

type HolidayType = 'Public' | 'Religious' | 'Cultural' | 'Observance' | 'Company'

type PlanTask = {
  task_id: TaskId
  title: string
  description: string
  assignee_type: 'agent' | 'human' | 'data_pipeline'   // data_pipeline added by DP-PRD-03
  assignee_name: string
  owner_email: string | null                            // PR-PRD-07
  status: TaskStatus
  depends_on: TaskId[]
  cost: number | null
  due_date: string | null         // ISO date
  launch_time_utc: string | null  // "HH:mm"
  launched_at: string | null      // ISO datetime
  unscheduled: boolean             // PR-PRD-07
  category: ActivityCategory       // PR-PRD-07
  channel: string | null           // PR-PRD-07
  task_type: string | null         // PR-PRD-07 (free-form typeahead)
  platform: Platform | null
  tags: string[]
  estimated_effort: 'small' | 'medium' | 'large' | null
  completion_notes: string | null
  revision_comment: string | null

  // Task-level recurrence (PR-PRD-07)
  recurrence_cron: string | null
  recurrence_timezone: string      // IANA, default "UTC"
  recurrence_enabled: boolean

  // Promotion-specific (PR-PRD-07; required iff category == "promotion")
  product_service: string | null
  promotion_type: PromotionType | null
  discount_details: string | null
  end_date: string | null          // ISO date
  promo_url: string | null
  region: string | null

  // Holiday-specific (PR-PRD-07; required iff category == "holiday")
  holiday_type: HolidayType | null
  recurring: boolean               // annual repetition flag (NOT a cron)
}

type ProjectPlan = {
  plan_id: PlanId
  account_id: AccountId
  type: 'freeform' | 'dashboard'    // owned by A-PRD-01; default "freeform"
  title: string
  goal: string
  acceptance_criteria: AcceptanceCriterion[]
  tasks: PlanTask[]
  campaign_id: string | null        // PR-PRD-08 (renamed from `campaign`)
  tags: string[]
  status: 'draft' | 'active' | 'completed' | 'archived'
  is_system: boolean                // PR-PRD-01
  // ...timestamps, version
}
```

Use `import type { … }` for all type-only imports per C-6.

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `frontend/src/pages/CalendarPage.tsx` |
| Create | `frontend/src/components/calendar/ActivityDetailPanel.tsx` |
| Create | `frontend/src/components/calendar/ProjectEditDrawer.tsx` |
| Create | `frontend/src/components/calendar/UnscheduledTasksPanel.tsx` (orphan-task list) |
| Create | `frontend/src/components/calendar/MoveToPlanDialog.tsx` (attach orphan to existing or new plan) |
| Create | `frontend/src/components/calendar/BatchActivityWizard.tsx` (multi-day create with per-day overrides) |
| Create | `frontend/src/components/calendar/GroupEditDrawer.tsx` (apply one patch to N selected activities) |
| Create | `frontend/src/components/calendar/CategoryBadge.tsx` + `PromotionFields.tsx` + `HolidayFields.tsx` (sparse-field renderers/editors) |
| Create | `frontend/src/components/calendar/CampaignPicker.tsx` (with inline-create dialog) |
| Create | `frontend/src/contexts/ProjectPlanContext.tsx` (also exposes orphan-task and campaign state) |
| Create | `frontend/src/services/projectPlanService.ts` |
| Create | `frontend/src/services/orphanTaskService.ts` |
| Create | `frontend/src/services/campaignService.ts` |
| Create | `frontend/src/types/projectPlan.ts` (incl. category + sparse-field types) |
| Modify | `frontend/src/App.tsx` — add `/calendar` route |
| Modify | `frontend/src/components/Sidebar.tsx` (or equivalent) — add calendar nav entry |
| Create | `frontend/src/pages/CalendarPage.test.tsx` |
| Create | `frontend/src/components/calendar/ActivityDetailPanel.test.tsx` |
| Create | `frontend/src/components/calendar/ProjectEditDrawer.test.tsx` |
| Create | `frontend/src/components/calendar/UnscheduledTasksPanel.test.tsx` |
| Create | `frontend/src/components/calendar/BatchActivityWizard.test.tsx` |
| Create | `frontend/src/components/calendar/GroupEditDrawer.test.tsx` |

### Page structure

**Calendar view (default):**
- Monthly grid; activities placed on `due_date` cells
- Cell content: title, **category badge** (task / promotion / holiday / event), platform badge (color-coded — see palette below), status badge, assignee badge, recurrence-indicator dot when `recurrence_enabled`
- Recurring activities are virtually expanded in-view via `POST /v1/schedules/preview` (A-PRD-2); no occurrence rows persisted
- `MonthYearPicker` for navigation (reuse existing component)
- Click a cell → opens `ActivityDetailPanel` with `?task=...` query param

**List view:**
- Sortable/filterable table — columns: title, category, project, campaign, platform, channel, status, assignee, owner, due date, launch time, cost, tags
- Toggle (radio buttons) at top-right with calendar view

**Unscheduled Tasks panel (orphan tasks):**
- Side panel listing the caller's orphan tasks (defaults to `owner_email = current user`); paginated
- Per-row "Move to plan" action → `MoveToPlanDialog` (attach to existing OR create new plan + attach atomically)
- "Detach from plan" action on the activity detail panel for plan-membership tasks → orphan subcollection

**Filter bar:**
- Multi-select dropdowns: project, campaign, platform, channel, status, assignee, owner, **category**, **task_type**, tags
- Date-range filter (`from` / `to`) on `due_date`

**Add button (top-right):**
- Dropdown: "Add Activity" (single) | "Batch Activities" (multi-day wizard) | "Add Project" — opens the appropriate drawer / wizard

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
Editable fields: title, category, status (dropdown of valid transitions), assignee, owner, platform, channel, task_type, cost, due date, launch time, recurrence (toggle + cron + tz), unscheduled toggle, campaign (with inline-create), tags. Sparse-field editors mounted conditionally:
- `category="promotion"` → `product_service`, `promotion_type`, `discount_details`, `end_date`, `promo_url`, `region`
- `category="holiday"` → `holiday_type`, `recurring` (annual)
- `category="event"` → no extra fields
- `category="task"` → no extra fields

Read-only: dependencies (with status indicators), revision comment (when status is "Revision Requested"), completion notes, created/updated metadata.

### Project edit drawer (`ProjectEditDrawer`)
Project-level fields: title, goal, acceptance criteria, campaign (`campaign_id`), project-level tags, bulk activity property editing (apply shared changes across selected activities; consumes `PATCH .../tasks:group-edit`).

### Group edit drawer (`GroupEditDrawer`)
Standalone drawer reachable from list-view multi-select. Body is a thin wrapper around `PATCH .../tasks:group-edit` — applies one patch to N selected activities in a single transaction; one audit entry per task. Validates the patch against the same model rules as a single PATCH.

### Batch Activity Wizard (`BatchActivityWizard`)
Multi-step dialog for the multi-day creation flow:
1. **Shared fields** — category, channel, owner, campaign, platform, tags, recurrence (optional)
2. **Per-day overrides** — per-row date + per-row override fields
3. **Review** — summary table with "Create N activities"
Calls `POST .../tasks/batch` with `{shared_fields, tasks: [...]}`. On success, all-or-nothing (one transaction); on validation failure, surface field-level errors against the offending row.

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
- `GET /api/v1/plans/{account_id}` — list (with the full filter set published by PR-PRD-07)
- `GET /api/v1/plans/{account_id}/{plan_id}` — fetch
- `PATCH /api/v1/plans/{account_id}/{plan_id}/tasks/{task_id}` — single-activity update
- `PUT /api/v1/plans/{account_id}/{plan_id}` — project update
- `POST /api/v1/plans/{account_id}/{plan_id}/tasks/batch` — batch-create (PR-PRD-07)
- `PATCH /api/v1/plans/{account_id}/{plan_id}/tasks:group-edit` — group edit (PR-PRD-07)
- `POST /api/v1/plans/{account_id}/{plan_id}/tasks/{task_id}/detach` — detach to orphans (PR-PRD-07)
- `GET /api/v1/orphan-tasks/{account_id}` — orphan list (PR-PRD-07)
- `POST /api/v1/orphan-tasks/{account_id}` — create orphan (PR-PRD-07)
- `PATCH/DELETE /api/v1/orphan-tasks/{account_id}/{task_id}` — update / soft-delete orphan (PR-PRD-07)
- `POST /api/v1/orphan-tasks/{account_id}/{task_id}/attach-to-plan` — attach to existing plan (PR-PRD-07)
- `POST /api/v1/orphan-tasks/{account_id}/{task_id}/attach-to-new-plan` — atomic create-plan-and-attach (PR-PRD-07)
- `GET /api/v1/campaigns/{account_id}` — campaign picker (PR-PRD-08)
- `POST /api/v1/campaigns/{account_id}` — inline campaign create (PR-PRD-08)
- `POST /v1/schedules/preview` — task-level recurrence expansion in the calendar grid (A-PRD-2)

(`/activate` and `/revision` are PR-PRD-04; called from this UI but defined there.)

## 7. Acceptance criteria

1. Navigating to `/calendar` renders the calendar view with all activities for the current account; per-category badge and color renders correctly for `task`, `promotion`, `holiday`, `event`
2. Toggling to list view shows the activity table; columns are sortable and filterable; the `category` column renders alongside title
3. Filter selections (incl. `category[]`, `task_type[]`, `channel[]`, `from`, `to`) persist in URL query params (so deep links work)
4. Clicking an activity cell opens the detail panel and updates the URL (`?task=...`); category-specific sparse-field editors render only for the matching category
5. Editing a field calls `PATCH` and updates state optimistically; rollback on failure
6. Status dropdown only shows valid next transitions (Draft → Awaiting Approval → Approved → Complete; with Rejected and Revision Requested branches; `Failed` and `Blocked` rendered read-only by the orchestrator)
7. The `ProjectEditDrawer` opens via "Edit Project" or the Add Project button
8. Account switch (via header) clears state and reloads plans for the new account
9. A chat message containing `[View Plan](/calendar?project=p_123)` produces an in-app SPA link, not a full-page reload
10. **Unscheduled Tasks panel** lists the caller's orphan tasks; "Move to plan" opens the dialog; choosing an existing plan calls `attach-to-plan` and the activity moves into the calendar; choosing "Create new plan" creates the plan + attaches the task atomically
11. **Batch wizard** with 7 day-rows + a shared-fields stub creates 7 activities in one transaction; on validation failure no rows persist
12. **Group edit** drawer applies one patch to N selected activities; one audit entry per activity
13. **Inline campaign create** from the activity drawer creates the campaign via `POST /api/v1/campaigns` and the new id round-trips into `campaign_id`; existing campaigns reachable via the picker
14. Recurring activities (`recurrence_enabled=true`) render virtual occurrences in the calendar grid using `POST /v1/schedules/preview`; no duplicate persisted rows
15. **Detach** action on a plan-membership activity moves it to the orphan list and prunes any sibling `depends_on` references
16. All component tests pass; `npm run typecheck` and `npm run format.fix` pass

## 8. Test plan

**Component tests:**
- `CalendarPage.test.tsx`: renders both view modes, toggles between them, applies filters (incl. `category[]`, `task_type[]`, `channel[]`, date range), opens detail panel on cell click, reflects URL state, renders virtual recurrence occurrences from a stubbed `/schedules/preview` response
- `ActivityDetailPanel.test.tsx`: renders activity fields per category (sparse-field editors only show for matching category), calls PATCH on edit, status dropdown shows valid transitions only, shows revision comment when status is "Revision Requested"
- `ProjectEditDrawer.test.tsx`: renders project fields, calls PUT on save, bulk-edit applies to selected activities
- `UnscheduledTasksPanel.test.tsx`: lists orphan tasks, default `owner_email` filter is current user, "Move to plan" → existing-plan path calls `attach-to-plan`, new-plan path calls `attach-to-new-plan`
- `BatchActivityWizard.test.tsx`: shared-fields + 7 day rows → one batch POST; validation error on row 4 surfaces a row-level message and does not persist any rows
- `GroupEditDrawer.test.tsx`: 3 selected ids + `{owner_email}` patch → one `:group-edit` POST; rejects with `422` on unknown id without partial application
- `CampaignPicker.test.tsx`: existing-campaign select round-trips `campaign_id`; "Create new" path calls `POST /campaigns` then sets the resulting id
- `ProjectPlanContext.test.tsx`: reloads on account switch, clears selected activity on plan deselect

**Manual smoke (record steps for PRD-5):**
- Open `/calendar`, switch view modes, apply filters (category + date range), deep-link a specific activity, edit a promotion (sparse fields render), batch-create 5 activities, group-edit 3 of them, attach an orphan to a new plan, detach a task back to orphans, account switch

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| Calendar grid performance with hundreds of tasks per month | Virtualize cells; collapse overflow with "+N more" badge |
| Optimistic updates conflict with server validation | Roll back local state on `4xx` and surface a toast |
| Color palette accessibility (contrast) | Use the existing design-system tokens; verify with axe DevTools |
| Date timezone handling — frontend displays in account TZ but `due_date` is UTC date | Pick a stance (display as UTC vs. account-local) and document. Recommendation: display dates in UTC for consistency with `launch_time_utc`. |
| Markdown link `<Link>` override not applied | If renderer doesn't support overrides, fall back to a custom click handler that intercepts internal hrefs |

## 10. Reference

- Parent plan: [`../../../project-planning-implementation-plan.md`](../../../project-planning-implementation-plan.md) §Frontend: Calendar Page, §Implementation Phases (Phase 3)
- Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism); key components to adapt: `CalendarPage.tsx`, `ActivityDetailPanel.tsx`, `GroupEditDrawer.tsx` (→ `ProjectEditDrawer`), `calendarData.ts`, `ActivitiesContext.tsx`
- Pattern files: `frontend/src/pages/Insights.tsx`, `frontend/src/pages/Home.tsx`, `frontend/src/contexts/ChatContext.tsx`
- CLAUDE.md rules in scope: C-5 (branded types), C-6 (`import type`), C-8 (`type` over `interface`), G-2, G-3 (frontend gates), T-2 (tests)
