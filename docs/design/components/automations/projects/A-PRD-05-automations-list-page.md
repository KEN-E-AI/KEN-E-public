# A-PRD-5 — Automations List Page

**Status:** Ready for development (after A-PRD-1 merges)
**Owner team:** Frontend
**Blocked by:** A-PRD-1; UI-PRD-03 (provides the `WorkflowsLayout` tab container, the `/workflows/automations` route, the Sidebar nav entry, and the empty-state `AutomationsPage` shell that this PRD wires data into)
**Parallel with:** A-PRDs 2, 3, 6
**Estimated effort:** 2 days

---

## 1. Context

The Figma design includes a "Workflows" page with multiple tabs, one of which is "Automations". This PRD delivers that page: a filtered, paginated list of all automations for the current account, with row-level actions to configure, run-now, pause/resume, and delete.

The list may be large — accounts with mature automation programs could have hundreds. Filters and cursor-based pagination keep the UI responsive.

## 2. Scope

### In scope
- Wire data into the existing `AutomationsPage` shell at `/workflows/automations` shipped by UI-PRD-03 (replace its empty-state with the data-wired list). The `WorkflowsLayout` tab container, the `/workflows` route group, and the Sidebar nav entry are already in place — this PRD does not re-create them.
- Filter bar: goal (text search), campaign (multi-select), tags (multi-select), status (multi-select), created_by (multi-select), is_active (toggle)
- **Default query excludes `is_system=true` automations** (platform-owned templates — see §is_system handling)
- Cursor-based pagination ("Load more" button)
- Row actions: Configure → navigate to A-PRD-6, Run Now, Pause / Resume, Delete (with confirmation)
- URL state sync: filters persist in query params on `/workflows/automations`
- Component tests with `*.test.tsx`

### Out of scope
- The `WorkflowsLayout` tab container, the `/workflows/*` routes, the Sidebar nav entry, and the empty-state shells for sibling tabs (Agents / Skills) — owned by UI-PRD-03
- The Automation Details page (A-PRD-6)
- Other Workflows tabs' data wiring (Agents → AH-PRD-02; Skills → SK-PRD-03)
- Bulk actions (multi-select rows + bulk pause / delete) — future
- Server-side text search beyond simple substring (no full-text index)
- A dedicated "System" tab or admin UI for browsing `is_system=true` automations (deferred; debug-only access via direct URL to A-PRD-6 is enough for v1)

## 3. Dependencies

- **UI-PRD-03 (hard prerequisite):** ships `frontend/src/pages/workflows/WorkflowsLayout.tsx` (tab container with URL-synced active tab), `frontend/src/pages/workflows/AutomationsPage.tsx` (empty-state shell this PRD modifies), the `/workflows/automations` route under `LayoutC` in `frontend/src/App.tsx`, and the Sidebar "Workflows" nav entry. The tab contract is frozen at UI-PRD-03 merge.
- **A-PRD-1:** consumes `GET /api/v1/automations/{account_id}` + `PATCH .../recurrence` + `DELETE .../{plan_id}` (DELETE inherited from Calendar PRD-1)
- **A-PRD-2:** "Run Now" button calls `POST .../runs`
- **Calendar PRD-3:** reuses branded types (`PlanId`, `AccountId`), service-layer pattern, and `useAuth().selectedOrgAccount` context
- **Existing files to study:**
  - `frontend/src/pages/workflows/AutomationsPage.tsx` (UI-PRD-03) — empty-state shell this PRD replaces
  - `frontend/src/pages/workflows/WorkflowsLayout.tsx` (UI-PRD-03) — tab contract this PRD consumes (do **not** modify)
  - `frontend/src/pages/CalendarPage.tsx` (Calendar PRD-3) — list-view filtering pattern
  - `frontend/src/services/projectPlanService.ts` (Calendar PRD-3) — extend with automation methods

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
| Modify | `frontend/src/pages/workflows/AutomationsPage.tsx` (UI-PRD-03 shell) — replace empty state with `<AutomationsList />` |
| Create | `frontend/src/components/automations/AutomationsList.tsx` |
| Create | `frontend/src/components/automations/AutomationFilterBar.tsx` |
| Create | `frontend/src/components/automations/AutomationListRow.tsx` |
| Create | `frontend/src/components/automations/RecurrenceSummary.tsx` (renders cron → "Every Monday 9:00 AM PT") |
| Modify | `frontend/src/services/projectPlanService.ts` — add `listAutomations`, `runAutomationNow`, `toggleAutomationActive` |
| Modify | `frontend/src/types/projectPlan.ts` — add `Automation`, `AutomationFilters`, `RunStatus` |
| Create | `frontend/src/contexts/AutomationListContext.tsx` (filter state + pagination state) |
| Modify | `frontend/src/pages/workflows/AutomationsPage.test.tsx` (UI-PRD-03 shell test) — extend with data-wired assertions |
| Create | `frontend/src/components/automations/AutomationsList.test.tsx` |
| Create | `frontend/src/components/automations/AutomationFilterBar.test.tsx` |

> **Out of scope (already shipped by UI-PRD-03):** `frontend/src/pages/workflows/WorkflowsLayout.tsx`, the `/workflows/*` route registrations in `frontend/src/App.tsx`, and the "Workflows" entry in `frontend/src/components/layout/Sidebar.tsx`. Do not re-create or modify these files.

### Page structure

UI-PRD-03 owns the outer shell (`WorkflowsLayout` with three tabs: Agents / Automations / Skills). This PRD replaces `AutomationsPage`'s empty state with the data-wired list:

```
WorkflowsLayout                                  ← UI-PRD-03 (do not modify)
  ├─ Tabs: [Agents] [Automations] [Skills]      ← UI-PRD-03
  └─ AutomationsPage (active tab)               ← this PRD modifies
       └─ AutomationsList                       ← this PRD creates
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
- Filters serialize to URL query params on the path-based route, e.g., `/workflows/automations?campaign=Spring,Summer&is_active=true` (the active tab is determined by the path, not a query param — per UI-PRD-03's tab contract)
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

1. Navigating to `/workflows/automations` renders the data-wired Automations list inside UI-PRD-03's `AutomationsPage` shell (the empty state is replaced when at least one automation exists for the account; otherwise the existing empty-state copy from UI-PRD-03 still renders)
2. The list loads automations for the current account; pagination "Load more" appends 25 at a time without duplicates
2a. The list excludes `is_system=true` automations even when none of the other filters are active (verified with a fixture that includes a seeded system template — it must not appear)
3. Applying any filter combination updates the list and the URL query params on `/workflows/automations`
4. Clicking "Configure" navigates to `/workflows/automations/{plan_id}` (A-PRD-6 route — the `AutomationDetailsPage` shell shipped by UI-PRD-03)
5. Clicking "Run Now" calls the manual-trigger endpoint and shows a success toast with a link to the new run
6. Pause toggles `is_active` to false; the row reflects the change immediately and persists on reload
7. Delete prompts for confirmation, then removes the row optimistically; on server error, the row is restored and a toast surfaces
8. URL deep links work: pasting `/workflows/automations?is_active=false&campaign=Spring` loads the filtered view directly
9. Account switch (via header) clears state and reloads for the new account
10. The `WorkflowsLayout` tab container (UI-PRD-03) renders unchanged — Agents / Automations / Skills tabs remain visible and functional; Automations tab no longer renders the empty state when data is present
11. All component tests pass; `npm run typecheck` and `npm run format.fix` pass

## 8. Test plan

**Component tests:**
- `AutomationsPage.test.tsx` (extends UI-PRD-03's existing test): renders the data-wired list when automations are present; falls back to UI-PRD-03's empty state when none exist; does **not** assert on the `WorkflowsLayout` tab container behavior (covered by UI-PRD-03)
- `AutomationsList.test.tsx`: renders rows from a mock service; "Load more" appends; empty state renders when no automations
- `AutomationFilterBar.test.tsx`: each filter type (text, multi-select, toggle) updates context + URL; clear-filters resets all
- `AutomationListRow.test.tsx`: each action calls the right service method; pause/resume optimistic update + rollback path
- `RecurrenceSummary.test.tsx`: known cron strings → expected human strings

**Manual smoke (record steps for A-PRD-7):**
- Open `/workflows/automations`, apply 3 filters in combination, paste a deep link with filters, switch accounts, run-now an automation, pause an automation

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| Filter state lost on browser back-button | URL query params drive state; back-button restores naturally |
| Optimistic delete race with concurrent edit | On 4xx/409, restore the row + toast "automation was modified — refresh" |
| Cron-to-human translation gaps for exotic patterns | Fall back to "Custom schedule: `<cron>` (`<tz>`)"; full coverage not required |
| Tab routing convention | Locked in by UI-PRD-03 — path-based routing (`/workflows/automations`), not query-param tabs. This PRD consumes that contract; do not change. |

## 10. Reference

- Parent plan: [`../README.md`](../README.md) §5 (Phase 5)
- Foundation: [A-PRD-1](./A-PRD-01-data-model-and-api.md)
- Shell: [UI-PRD-03](../../ui/projects/UI-PRD-03-workflows-shell.md) — `WorkflowsLayout` + `AutomationsPage` shell + `/workflows/automations` route
- Pattern files: `frontend/src/pages/CalendarPage.tsx` (Calendar PRD-3), `frontend/src/services/projectPlanService.ts`
- Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) — Workflows page, Automations tab
- CLAUDE.md rules in scope: C-5 (branded types), C-6 (`import type`), C-8 (`type` over `interface`), G-2, G-3, T-2
