# A-PRD-5 — Automations List Page

**Status:** Ready for development (after A-PRD-1 merges)
**Owner team:** Frontend
**Blocked by:** A-PRD-1
**Parallel with:** A-PRDs 2, 3, 6
**Estimated effort:** 2 days

---

## 1. Context

The Figma design includes a "Workflows" page with multiple tabs, one of which is "Automations". This PRD delivers that page: a filtered, paginated list of all automations for the current account, with row-level actions to configure, run-now, pause/resume, and delete.

The list may be large — accounts with mature automation programs could have hundreds. Filters and cursor-based pagination keep the UI responsive.

## 2. Scope

### In scope
- New `/workflows` route with tab container
- "Automations" tab containing the list
- Filter bar: goal (text search), campaign (multi-select), tags (multi-select), status (multi-select), created_by (multi-select), is_active (toggle)
- **Default query excludes `is_system=true` automations** (platform-owned templates — see §is_system handling)
- Cursor-based pagination ("Load more" button)
- Row actions: Configure → navigate to A-PRD-6, Run Now, Pause / Resume, Delete (with confirmation)
- URL state sync: filters and tab persist in query params
- Component tests with `*.test.tsx`

### Out of scope
- The Automation Details page (A-PRD-6)
- Other Workflows tabs (Projects, Templates, etc. — future PRDs)
- Bulk actions (multi-select rows + bulk pause / delete) — future
- Server-side text search beyond simple substring (no full-text index)
- A dedicated "System" tab or admin UI for browsing `is_system=true` automations (deferred; debug-only access via direct URL to A-PRD-6 is enough for v1)

## 3. Dependencies

- **A-PRD-1:** consumes `GET /api/v1/automations/{account_id}` + `PATCH .../recurrence` + `DELETE .../{plan_id}` (DELETE inherited from Calendar PRD-1)
- **A-PRD-2:** "Run Now" button calls `POST .../runs`
- **Calendar PRD-3:** reuses branded types (`PlanId`, `AccountId`), service-layer pattern, and `useAuth().selectedOrgAccount` context
- **Existing files to study:**
  - `frontend/src/pages/CalendarPage.tsx` (Calendar PRD-3) — list-view filtering pattern
  - `frontend/src/services/projectPlanService.ts` (Calendar PRD-3) — extend with automation methods
  - `frontend/src/components/Sidebar.tsx` — add "Workflows" nav entry

## 4. Data contract (TypeScript)

Reuses Calendar PRD-3 types; adds:

```ts
type RunStatus =
  | 'pending'
  | 'running'
  | 'halted_for_human'
  | 'complete'
  | 'failed'
  | 'cancelled'

type Automation = ProjectPlan & {
  save_as_automation: true
  recurrence_cron: string | null
  recurrence_timezone: string
  last_run_at: string | null         // ISO datetime
  last_run_id: RunId | null
  last_run_status: RunStatus | null  // enriched server-side
  next_run_at: string | null
}

type AutomationFilters = {
  goal?: string
  campaign?: string[]
  tags?: string[]
  status?: PlanStatus[]
  created_by?: UserId[]
  is_active?: boolean
}

type PaginatedResponse<T> = {
  items: T[]
  next_cursor: string | null
  total_count_estimate?: number
}
```

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `frontend/src/pages/WorkflowsPage.tsx` (tab container) |
| Create | `frontend/src/components/automations/AutomationsList.tsx` |
| Create | `frontend/src/components/automations/AutomationFilterBar.tsx` |
| Create | `frontend/src/components/automations/AutomationListRow.tsx` |
| Create | `frontend/src/components/automations/RecurrenceSummary.tsx` (renders cron → "Every Monday 9:00 AM PT") |
| Modify | `frontend/src/services/projectPlanService.ts` — add `listAutomations`, `runAutomationNow`, `toggleAutomationActive` |
| Modify | `frontend/src/types/projectPlan.ts` — add `Automation`, `AutomationFilters`, `RunStatus` |
| Modify | `frontend/src/App.tsx` — add `/workflows` route |
| Modify | `frontend/src/components/Sidebar.tsx` — add "Workflows" nav entry |
| Create | `frontend/src/contexts/AutomationListContext.tsx` (filter state + pagination state) |
| Create | `frontend/src/pages/WorkflowsPage.test.tsx` |
| Create | `frontend/src/components/automations/AutomationsList.test.tsx` |
| Create | `frontend/src/components/automations/AutomationFilterBar.test.tsx` |

### Page structure

```
WorkflowsPage
  ├─ Tabs: [Automations] [Projects (future)] [Templates (future)]
  └─ AutomationsList (active tab)
       ├─ AutomationFilterBar
       └─ table:
            AutomationListRow × N
              ├─ Title + RecurrenceSummary
              ├─ Last run (timestamp + status badge)
              ├─ Next run (timestamp)
              ├─ Status badge (Active / Paused)
              ├─ Created by
              └─ Actions menu: Configure / Run Now / Pause | Resume / Delete
       └─ "Load more" button (when next_cursor)
```

### Filter bar behavior

- All filters are multi-select except `goal` (substring) and `is_active` (toggle)
- Changing any filter resets pagination cursor (fetches first page)
- Filters serialize to URL query params, e.g., `/workflows?tab=automations&campaign=Spring,Summer&is_active=true`
- "Clear filters" button resets to no filters + first page

### Pagination

- Page size: 25 (server default)
- "Load more" appends to the existing list (preserves scroll)
- When `next_cursor === null`, hide the button
- Total count (if returned by server) shown as "Showing 25 of ~340"

### `is_system` handling

`is_system: bool` on `ProjectPlan` (Calendar PRD-1) marks a template as platform-owned rather than user-authored. Known use case: the session-end automation seeded by KG-PRD-04.

**Client-side rule:** the list query passed to `GET /api/v1/automations/{account_id}` always sends `is_system=false` by default. The server honors the filter.

**Why filter client-side** — users did not create these templates, should not configure or delete them, and would be confused by them appearing alongside their own work. There is no current product surface for browsing them; operators inspect them via direct URL to A-PRD-6, which renders read-only.

**Not in v1:**
- A "System" tab or toggle that reveals system automations. Debug access via direct URL is sufficient until a real need emerges.
- Any row-level indicator of system automations. Since they never appear in the list, no badge is needed.

**If a system automation ever leaks into the list** (regression): the row renders as normal but its action menu should suppress Configure, Run Now, Pause/Resume, and Delete — the details page will refuse to edit, so the UX degrades gracefully instead of throwing. Implement this as a defense-in-depth check; not a primary control.

### Row actions

- **Configure** — `<Link to={`/workflows/automations/${automation.plan_id}`}>` (A-PRD-6)
- **Run Now** — POST to A-PRD-2's manual-trigger endpoint; toast on success with deep link to the new run
- **Pause / Resume** — PATCH `/recurrence` with `is_active=false` / `true`; optimistic update with rollback on failure
- **Delete** — confirmation modal → DELETE → optimistic remove from list; rollback on failure

### Recurrence summary helper

Pure function: cron + timezone → human string.
- `"0 9 * * MON"` + `"America/Los_Angeles"` → `"Every Monday at 9:00 AM PT"`
- `"*/15 * * * *"` + `"UTC"` → `"Every 15 minutes"`
- `"0 0 1 * *"` + `"UTC"` → `"Monthly on the 1st at 12:00 AM UTC"`
- Use a small library (e.g., `cronstrue`) or hand-roll for the common patterns; fall back to raw cron + tz for exotic expressions.

## 6. API contract

This PRD only consumes — no new endpoints. Calls:
- `GET /api/v1/automations/{account_id}` — list (with filters + cursor)
- `POST /api/v1/automations/{account_id}/{plan_id}/runs` — manual trigger (A-PRD-2)
- `PATCH /api/v1/automations/{account_id}/{plan_id}/recurrence` — pause / resume
- `DELETE /api/v1/plans/{account_id}/{plan_id}` — soft delete (Calendar PRD-1)

## 7. Acceptance criteria

1. Navigating to `/workflows` renders the page with the Automations tab selected by default
2. The list loads automations for the current account; pagination "Load more" appends 25 at a time without duplicates
2a. The list excludes `is_system=true` automations even when none of the other filters are active (verified with a fixture that includes a seeded system template — it must not appear)
3. Applying any filter combination updates the list and the URL query params
4. Clicking "Configure" navigates to `/workflows/automations/{plan_id}` (A-PRD-6 route)
5. Clicking "Run Now" calls the manual-trigger endpoint and shows a success toast with a link to the new run
6. Pause toggles `is_active` to false; the row reflects the change immediately and persists on reload
7. Delete prompts for confirmation, then removes the row optimistically; on server error, the row is restored and a toast surfaces
8. URL deep links work: pasting `/workflows?tab=automations&is_active=false&campaign=Spring` loads the filtered view directly
9. Account switch (via header) clears state and reloads for the new account
10. All component tests pass; `npm run typecheck` and `npm run format.fix` pass

## 8. Test plan

**Component tests:**
- `WorkflowsPage.test.tsx`: renders tab container; default tab is Automations
- `AutomationsList.test.tsx`: renders rows from a mock service; "Load more" appends; empty state renders when no automations
- `AutomationFilterBar.test.tsx`: each filter type (text, multi-select, toggle) updates context + URL; clear-filters resets all
- `AutomationListRow.test.tsx`: each action calls the right service method; pause/resume optimistic update + rollback path
- `RecurrenceSummary.test.tsx`: known cron strings → expected human strings

**Manual smoke (record steps for A-PRD-7):**
- Open `/workflows`, apply 3 filters in combination, paste a deep link with filters, switch accounts, run-now an automation, pause an automation

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| Filter state lost on browser back-button | URL query params drive state; back-button restores naturally |
| Optimistic delete race with concurrent edit | On 4xx/409, restore the row + toast "automation was modified — refresh" |
| Cron-to-human translation gaps for exotic patterns | Fall back to "Custom schedule: `<cron>` (`<tz>`)"; full coverage not required |
| Tab routing convention conflicts with existing app router | Verify `/workflows?tab=automations` pattern; if app prefers nested routes (`/workflows/automations`), adjust before implementation |

## 10. Reference

- Parent plan: [`../README.md`](../README.md) §5 (Phase 5)
- Foundation: [A-PRD-1](./01-data-model-and-api.md)
- Pattern files: `frontend/src/pages/CalendarPage.tsx` (Calendar PRD-3), `frontend/src/services/projectPlanService.ts`
- Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) — Workflows page, Automations tab
- CLAUDE.md rules in scope: C-5 (branded types), C-6 (`import type`), C-8 (`type` over `interface`), G-2, G-3, T-2
