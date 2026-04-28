# DB-PRD-02 — Dashboards Tab & List Page

**Status:** Blocked — resumes once DB-PRD-01 and PE-PRD-01 ship
**Owner team:** Frontend
**Blocked by:** DB-PRD-01 (API contract this page consumes); PE-PRD-01 (Performance page shell — owns the Dashboards tab slot + route)
**Blocks:** DB-PRD-03 (shares the Performance tab shell)
**Estimated effort:** 2 days

---

## 1. Context

Dashboards is the **2nd tab** on the Performance page (between Analysis and Simulations) — full tab order per Figma: Analysis / **Dashboards** / Simulations / Targets / Diagnostics / Configuration. PE-PRD-01 reserves the tab slot, route (`/performance/dashboards`), placeholder component, and feature flag (`performance_dashboards_tab`); this PRD swaps the placeholder for a real list view. Dashboards is **not gated by SAR-E** — it remains visible regardless of `ForecastingEnabledGate` state, since dashboards are powered by Project Tasks + Automations rather than the analytical backend.

This PRD delivers the **shell** for that tab and the **list page** users land on when they select it: a scrollable list of the account's dashboards with create / edit / run shortcuts, an empty state for first-time users, and a New Dashboard creation flow.

It does **not** deliver the dashboard details canvas (DB-PRD-03). Details page deep-links are routed but land on a stub that DB-PRD-03 fills in.

## 2. Scope

### In scope
- Replace PE-PRD-01's `<DashboardsTabPlaceholder />` at `/performance/dashboards` with the real `DashboardsSection` (this PRD's deliverable). Tab order locked by PE-PRD-01: Analysis / **Dashboards** / Simulations / Targets / Diagnostics / Configuration.
- URL state: `/performance/dashboards` selects the tab; deep-links from Sidebar / Notifications work
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
- **PE-PRD-01 (Performance Page Shell):** owns the Performance tab container, the `/performance/dashboards` route, the `<DashboardsTabPlaceholder />` stub this PRD replaces, the `performance_dashboards_tab` feature flag, and the gating decision (Dashboards is **not** wrapped in `ForecastingEnabledGate`). PE-PRD-01 must be merged before this PRD starts.
- **UI-PRD-01 (Design System):** consumes tokens from `theme.css`, Tailwind config, and the redesigned shadcn primitives under `frontend/src/components/ui/`.
- **Notifications (A-PRD-02 producer):** "Dashboard ready" notifications come from A-PRD-02's `AUTOMATION_RUN_COMPLETE` notification, fired on every `PlanRun` terminal state for `plan.created_by` (skipped for `is_test=true` runs). For `plan.type=='dashboard'` the deep-link is `/performance/dashboards/{plan_id}?runId={run_id}` (for `type='freeform'`, A-PRD-02 routes to `/workflows/automations/{plan_id}?run={run_id}` — same producer, two consumers). No work in this PRD; verify the deep-link format renders the right run highlighted in DB-PRD-03 (`?runId={run_id}` is a query param read by the details page, not a route). PE-PRD-01 owns the `/performance/dashboards/{plan_id}` route registration.
- **Existing files to study:**
  - `frontend/src/pages/Performance/PerformancePage.tsx` (PE-PRD-01 target) — tab container to plug into
  - `frontend/src/pages/Performance/DashboardsTabPlaceholder.tsx` (PE-PRD-01) — the stub this PRD replaces
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
| Modify | `frontend/src/pages/Performance/PerformancePage.tsx` — replace PE-PRD-01's `<DashboardsTabPlaceholder />` mount with `<DashboardsSection />` at `/performance/dashboards` |
| Delete | `frontend/src/pages/Performance/DashboardsTabPlaceholder.tsx` — placeholder shipped by PE-PRD-01; this PRD removes it |
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

PE-PRD-01 owns the route shape (path-based, not query-string). This PRD consumes:

```
/performance                                   → gate-driven redirect (PE-PRD-01)
/performance/dashboards                        → Dashboards list (this PRD)
/performance/dashboards/{plan_id}              → Dashboard details (stub until DB-PRD-03)
/performance/dashboards/{plan_id}?runId={...}  → details with a specific run highlighted (DB-PRD-03)
```

Sidebar "Performance" link goes to `/performance` (PE-PRD-01's gate-driven default). No direct Sidebar entry for "Dashboards" in v1; users navigate Performance → Dashboards tab.

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
8. Row-menu "Duplicate" opens `DuplicateDashboardDialog` pre-filled with `"{source.title} (Copy)"`. Submitting POSTs to the duplicate endpoint; on 201, a toast shows with an "Open new dashboard" link; the list re-fetches and the new dashboard appears at the top.
9. Duplicate of a dashboard with an active schedule creates a new dashboard with `is_active=false` (schedule preserved but disabled). The new dashboard's row shows the schedule summary but a toned-down / paused visual state.
10. Deep-linking to `/performance/dashboards` selects the Dashboards tab on page load (URL → state sync).
11. Deep-linking to `/performance/dashboards/{plan_id}` renders the stub until DB-PRD-03 replaces it.
12. Viewer-role users see the list and rows but the "+ New Dashboard" CTA and row-menu destructive actions (Delete, Run Now) are disabled with tooltips.
13. Cross-account access returns `403` at the API layer; UI renders a toast and navigates to `/accounts`.
14. List is paginated: loading 30 dashboards shows the first page with `page_size=25` default; scrolling to bottom triggers the next-page fetch via `cursor`.
15. `npm run build` clean; `npm run typecheck` clean; `npm run format.fix` clean.
16. All unit tests pass; Playwright `dashboards-create-flow.spec.ts` passes.

## 8. Test plan

**Unit tests** (`DashboardsSection.test.tsx`):
- Renders list when API returns ≥1 dashboard
- Renders empty state when API returns zero
- Row-menu actions fire the correct axios calls
- Viewer role disables destructive actions
- Deep-link `/performance/dashboards` selects the tab on mount

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
| PE-PRD-01 hasn't merged when this PRD starts | Hard block — DB-PRD-02 cannot start until PE-PRD-01 is merged (it relies on PE-PRD-01's tab slot, route registration, and `<DashboardsTabPlaceholder />` to swap out). Sequencing is enforced via `blocked_by` in `PROJECT-PLANNER.md`. |
| Sidebar navigation convention for "Dashboards" not yet decided | v1 lives under Performance tab only. Revisit if product wants a top-level "Dashboards" sidebar entry. |
| Last-run status lags until the next 30-s list re-fetch | Acceptable for v1. Future enhancement: subscribe to run-status updates via SSE or push from the notification system. |
| Tags typeahead hits an endpoint that doesn't yet exist | Verify `/api/v1/accounts/{account_id}/tags` or equivalent at implementation start. If absent, degrade the field to a free-text comma-separated input (tags deduped server-side). |

### Open questions

- **Should "Run Now" be available on a dashboard with zero tasks?** Proposed: no — disable with a tooltip ("Add at least one task before running"). Confirm at implementation.

## 10. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md)
- Foundation: [DB-PRD-01](./DB-PRD-01-data-model-and-api.md)
- Sibling (shared tab container): [PE-PRD-01 Performance page shell](../../performance/projects/PE-PRD-01-page-shell-and-routing.md) — owns the Dashboards tab slot, route, placeholder, and feature flag. (UI-PRD-07 — the original presentation-only redesign — is **retired and subsumed by PE-PRD-01**.)
- Pattern to mirror: [A-PRD-05 Automations list](../../automations/projects/A-PRD-05-automations-list-page.md)
- Figma reference: `docs/figma-export/src/app/components/DashboardsSection.tsx` (UX only — rebuild in Soft Maximalism)
- Frontend conventions: `frontend/CLAUDE.md` (CSS architecture, component library, branded types)
- CLAUDE.md rules in scope: C-5, C-6, C-8; T-2, T-6, T-8; G-2, G-3
