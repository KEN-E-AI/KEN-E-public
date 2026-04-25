# DB-PRD-02 — Dashboards Tab & List Page

**Status:** Blocked — resumes once DB-PRD-01 ships
**Owner team:** Frontend
**Blocked by:** DB-PRD-01 (API contract this page consumes); UI-PRD-07 (Performance page shell — soft dep, see §3)
**Blocks:** DB-PRD-03 (shares the Performance tab shell)
**Estimated effort:** 2 days

---

## 1. Context

Dashboards is a new tab on the Performance page (`/performance?tab=dashboards`). This PRD delivers the **shell** for that tab and the **list page** users land on when they select it: a scrollable list of the account's dashboards with create / edit / run shortcuts, an empty state for first-time users, and a New Dashboard creation flow.

It does **not** deliver the dashboard details canvas (DB-PRD-03). Details page deep-links are routed but land on a stub that DB-PRD-03 fills in.

The Performance page itself is being redesigned under UI-PRD-07. This PRD coordinates with the UI-PRD-07 team on tab mechanics but ships independently: if UI-PRD-07 hasn't merged, the Dashboards tab lands as a sibling tab using the same Soft Maximalism tokens.

## 2. Scope

### In scope
- Add Dashboards tab to `PerformancePage` alongside Analysis / Simulations / Goals / Diagnostics / Config
- URL state: `/performance?tab=dashboards` selects it; deep-links from Sidebar / Notifications work
- Dashboards list view: per-row title, description, schedule summary, last-run timestamp, status badge (Active / Inactive), configure button, row-level menu (Run Now / Duplicate / Delete)
- Empty state: illustration + copy + "New Dashboard" CTA
- Create flow: modal with title (required, ≤200 chars), description (optional, ≤1000 chars), tags (multi-select typeahead from account-wide tag list). Submit → `POST /api/v1/dashboards/{account_id}` → redirect to `/performance/dashboards/{plan_id}`
- TanStack Query hooks with 30-second stale time for the list
- Service layer + branded types (`DashboardPlanId`, `AccountId`)
- Unit tests for the query hooks + the create-form validation; Playwright spec for the empty-state → create → redirect flow

### Out of scope (DB-PRD-03)
- The dashboard details page canvas, widgets, run controls
- Pin-to-dashboard affordance on task panels

### Out of scope (other PRDs / releases)
- Sharing / per-dashboard permissions
- Thumbnails / canvas previews on list rows (future enhancement)
- Filter / sort on the list (future; default order is `updated_at DESC`)
- Extensions (dashboard templates) — out of scope entirely for this release

## 3. Dependencies

- **DB-PRD-01:** publishes `GET /api/v1/dashboards/{account_id}` (list) and `POST /api/v1/dashboards/{account_id}` (create). Also provides `DashboardSummary` and `ProjectPlan` types mirrored client-side.
- **UI-PRD-07 (Performance page shell):** soft dependency. If merged, this PRD adds the Dashboards tab to the existing tab container. If not merged, this PRD ships a minimal tab container sized for 6 tabs using the Soft Maximalism tokens from UI-PRD-01. Coordinate with the UI-PRD-07 owner at planning time.
- **UI-PRD-01 (Design System):** consumes tokens from `theme.css`, Tailwind config, and the redesigned shadcn primitives under `frontend/src/components/ui/`.
- **Notifications (existing):** "Dashboard ready" notifications (from A-PRD-04's run-complete payload for `type="dashboard"` plans) deep-link to `/performance/dashboards/{plan_id}?runId={run_id}`. No change here; just verify the deep-link format is honored.
- **Existing files to study:**
  - `frontend/src/pages/PerformancePage.tsx` (UI-PRD-07 target) — tab container to extend
  - `frontend/src/pages/WorkflowsPage.tsx` (A-PRD-05) — sibling tab-and-list pattern to mirror
  - `frontend/src/pages/workflows/AutomationsList.tsx` (A-PRD-05) — list-row component to mirror
  - `docs/figma-export/src/app/components/DashboardsSection.tsx` — reference UX (but rebuilt in the Soft Maximalism design system, not literal)

## 4. Data contract (consumed, not owned)

TypeScript types mirrored from DB-PRD-01's Pydantic models:

```typescript
// frontend/src/types/dashboard.ts

export type DashboardPlanId = Brand<string, 'DashboardPlanId'>;

export interface DashboardSummary {
  plan_id: DashboardPlanId;
  title: string;
  description: string | null;
  tags: string[];
  is_active: boolean;
  last_run_at: string | null;          // ISO datetime
  next_run_at: string | null;          // from schedule
  last_run_status: 'pending' | 'running' | 'complete' | 'failed' | 'cancelled' | null;
  placement_count: number;
  updated_at: string;
}

export interface CreateDashboardRequest {
  title: string;
  description?: string;
  tags?: string[];
}
```

Brand types per CLAUDE.md C-5.

## 5. Implementation outline

| Action | File |
|--------|------|
| Modify | `frontend/src/pages/PerformancePage.tsx` — register `Dashboards` tab; route `?tab=dashboards` to the new section |
| Create | `frontend/src/pages/performance/DashboardsSection.tsx` — list + empty state |
| Create | `frontend/src/components/dashboards/DashboardListRow.tsx` — per-row card |
| Create | `frontend/src/components/dashboards/NewDashboardDialog.tsx` — create modal |
| Create | `frontend/src/components/dashboards/DuplicateDashboardDialog.tsx` — duplicate modal |
| Create | `frontend/src/types/dashboard.ts` — branded types |
| Create | `frontend/src/services/dashboardsApi.ts` — axios wrappers |
| Create | `frontend/src/hooks/useDashboards.ts` — TanStack Query hooks |
| Modify | `frontend/src/App.tsx` — add `/performance/dashboards/:planId` route (component stub for DB-PRD-03 to fill) |
| Create | `frontend/src/pages/performance/DashboardDetailsPageStub.tsx` — minimal stub shown until DB-PRD-03 replaces it |
| Create | `frontend/src/pages/performance/__tests__/DashboardsSection.test.tsx` |
| Create | `frontend/src/components/dashboards/__tests__/NewDashboardDialog.test.tsx` |
| Create | `frontend/e2e/dashboards-create-flow.spec.ts` (Playwright) |

### URL / routing contract

```
/performance                                   → default tab (analysis)
/performance?tab=dashboards                    → Dashboards list
/performance/dashboards/{plan_id}              → Dashboard details (stub until DB-PRD-03)
/performance/dashboards/{plan_id}?runId={...}  → details with a specific run highlighted (DB-PRD-03)
```

Sidebar "Performance" link goes to `/performance` (default). No direct Sidebar entry for "Dashboards" in v1; users navigate Performance → Dashboards tab.

### List-row UX

Per row, per the Figma reference (`docs/figma-export/src/app/components/DashboardsSection.tsx:76-128`):

```
┌──────────────────────────────────────────────────────────────────┐
│ [icon]  Title                                         [badge]    │
│         Description preview (1 line, truncated)                  │
│         [schedule summary]  ·  Last run: 2 hours ago             │
│                                            [Configure] [⋯ menu]  │
└──────────────────────────────────────────────────────────────────┘
```

- `[icon]`: `LayoutDashboard` in violet-500.
- `[badge]`: "Active" (violet) if `is_active`, "Inactive" (neutral) otherwise.
- Schedule summary: from `A-PRD-02`'s `describeSchedule()` logic — if the dashboard has a recurrence cron, show "Every Mon at 9:00 AM PT" etc. Else "Not scheduled."
- Last run timestamp: relative ("2 hours ago") with an `title` attribute containing the absolute ISO.
- Configure button: opens `/performance/dashboards/{plan_id}` (details page).
- `[⋯ menu]`: Run Now (calls A-PRD-02's manual trigger), Duplicate (opens the Duplicate dialog; see below), Delete (calls DB-PRD-01's DELETE).

### Empty state

Shown when `list.length === 0`:

```
[illustration]

No dashboards yet

Create a dashboard to schedule automated reports and visualize the
artifacts produced by your agents.

[+ New Dashboard]
```

CTA button opens the NewDashboardDialog.

### Create flow

Modal with:
- Title (required, ≤200 chars, trimmed, duplicate-name warning within account)
- Description (optional, ≤1000 chars, textarea)
- Tags (optional, typeahead from `GET /api/v1/accounts/{account_id}/tags` — existing endpoint)
- Cancel / Create buttons

On Create:
1. `POST /api/v1/dashboards/{account_id}` with the body.
2. On 201, navigate to `/performance/dashboards/{plan_id}`.
3. On 422 (duplicate title within account), surface the error inline on the Title field.
4. On 403, surface a toast ("You do not have permission to create dashboards in this account.").

### Duplicate flow

Selecting "Duplicate" from a row's `[⋯ menu]` opens `DuplicateDashboardDialog`:

- Title (pre-filled with `"{source.title} (Copy)"`, editable, required, ≤200 chars)
- Read-only preview line: "This will copy the canvas, tasks, and schedule. The duplicate's schedule will be off until you re-enable it."
- Cancel / Duplicate buttons

On Duplicate:
1. `POST /api/v1/dashboards/{account_id}/{plan_id}/duplicate` with `{title: <user input>}`.
2. On 201, invalidate the list query (new dashboard appears at the top once re-fetched) and show a toast: "Dashboard duplicated — [Open new dashboard]" with a link to the new plan's details page.
3. On 403, surface a toast ("You do not have permission to duplicate this dashboard.").
4. On 422 (`type="freeform"` target), impossible from the list row since we only list dashboards — but handle defensively with a generic error toast.

## 6. API contract (consumed)

| Method | Path | Purpose | Owner |
|--------|------|---------|-------|
| `GET` | `/api/v1/dashboards/{account_id}` | List. Query params: `is_active`, `tags[]`, `cursor`, `page_size`. | DB-PRD-01 |
| `POST` | `/api/v1/dashboards/{account_id}` | Create. | DB-PRD-01 |
| `POST` | `/api/v1/dashboards/{account_id}/{plan_id}/duplicate` | Duplicate (row-menu action). Body `{title?}`. | DB-PRD-01 |
| `DELETE` | `/api/v1/dashboards/{account_id}/{plan_id}` | Soft-delete. | DB-PRD-01 |
| `POST` | `/api/v1/automations/{account_id}/{plan_id}/runs` | Run Now (row-menu action). `triggered_by="manual"`. | A-PRD-02 |

Cache policy (TanStack Query):
- `useDashboardsList(account_id)` — 30 s stale time, re-fetch on window focus
- Invalidates on create / duplicate / delete / Run Now (new `last_run_status` expected shortly)

## 7. Acceptance criteria

1. Selecting the Dashboards tab on `/performance` loads `DashboardsSection` and issues `GET /api/v1/dashboards/{account_id}`.
2. On an account with zero dashboards, the empty state renders with the "+ New Dashboard" CTA. Clicking the CTA opens `NewDashboardDialog`.
3. Submitting the create dialog with valid input POSTs, navigates to `/performance/dashboards/{plan_id}`, and the new dashboard appears on the list when the user returns (invalidated query re-fetches).
4. Submitting with duplicate title within the account surfaces the 422 message inline on the Title field without dismissing the dialog.
5. Each list row renders title, schedule summary, last-run relative time, status badge, and a Configure button linking to the details URL.
6. Row-menu "Run Now" POSTs to the A-PRD-02 trigger endpoint; the row's `last_run_status` updates to "running" on the next re-fetch.
7. Row-menu "Delete" shows a confirmation (Cancel / Delete), then DELETEs on confirm; the row disappears from the list after invalidation.
7a. Row-menu "Duplicate" opens `DuplicateDashboardDialog` pre-filled with `"{source.title} (Copy)"`. Submitting POSTs to the duplicate endpoint; on 201, a toast shows with an "Open new dashboard" link; the list re-fetches and the new dashboard appears at the top.
7b. Duplicate of a dashboard with an active schedule creates a new dashboard with `is_active=false` (schedule preserved but disabled). The new dashboard's row shows the schedule summary but a toned-down / paused visual state.
8. Deep-linking to `/performance?tab=dashboards` selects the Dashboards tab on page load (URL → state sync).
9. Deep-linking to `/performance/dashboards/{plan_id}` renders the stub until DB-PRD-03 replaces it.
10. Viewer-role users see the list and rows but the "+ New Dashboard" CTA and row-menu destructive actions (Delete, Run Now) are disabled with tooltips.
11. Cross-account access returns `403` at the API layer; UI renders a toast and navigates to `/accounts`.
12. List is paginated: loading 30 dashboards shows the first page with `page_size=25` default; scrolling to bottom triggers the next-page fetch via `cursor`.
13. `npm run build` clean; `npm run typecheck` clean; `npm run format.fix` clean.
14. All unit tests pass; Playwright `dashboards-create-flow.spec.ts` passes.

## 8. Test plan

**Unit tests** (`DashboardsSection.test.tsx`):
- Renders list when API returns ≥1 dashboard
- Renders empty state when API returns zero
- Row-menu actions fire the correct axios calls
- Viewer role disables destructive actions
- Deep-link `?tab=dashboards` selects the tab on mount

**Unit tests** (`NewDashboardDialog.test.tsx`):
- Required-field validation on title (empty, whitespace-only, >200 chars)
- Description length cap enforced
- 422 from API surfaces inline
- 403 shows toast, does not dismiss dialog
- Success path navigates to the details URL

**Playwright** (`dashboards-create-flow.spec.ts`):
- Empty-state → open dialog → fill title → submit → land on details URL → return to list → row visible
- Run Now from the row menu → status badge updates to "running"
- Duplicate from the row menu → modal opens pre-filled → submit with edited title → toast shows → list re-fetches → duplicate appears at top with `is_active=false`
- Delete → confirm → row gone

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| UI-PRD-07 hasn't merged when this PRD starts | Ship a minimal tab container using the Soft Maximalism tokens from UI-PRD-01. Replace with UI-PRD-07's tab container in a follow-up PR once UI-PRD-07 lands. No user-visible regression. |
| Sidebar navigation convention for "Dashboards" not yet decided | v1 lives under Performance tab only. Revisit if product wants a top-level "Dashboards" sidebar entry. |
| Last-run status lags until the next 30-s list re-fetch | Acceptable for v1. Future enhancement: subscribe to run-status updates via SSE or push from the notification system. |
| Tags typeahead hits an endpoint that doesn't yet exist | Verify `/api/v1/accounts/{account_id}/tags` or equivalent at implementation start. If absent, degrade the field to a free-text comma-separated input (tags deduped server-side). |

### Open questions

- **Should "Run Now" be available on a dashboard with zero tasks?** Proposed: no — disable with a tooltip ("Add at least one task before running"). Confirm at implementation.

## 10. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md)
- Foundation: [DB-PRD-01](./DB-PRD-01-data-model-and-api.md)
- Sibling (shared tab container): [UI-PRD-07 Performance page](../../ui/projects/UI-PRD-07-performance-page.md) *(if exists; otherwise this PRD adds the tab container ad-hoc per §3)*
- Pattern to mirror: [A-PRD-05 Automations list](../../automations/projects/A-PRD-05-automations-list-page.md)
- Figma reference: `docs/figma-export/src/app/components/DashboardsSection.tsx` (UX only — rebuild in Soft Maximalism)
- Frontend conventions: `frontend/CLAUDE.md` (CSS architecture, component library, branded types)
- CLAUDE.md rules in scope: C-5, C-6, C-8; T-2, T-6, T-8; G-2, G-3
