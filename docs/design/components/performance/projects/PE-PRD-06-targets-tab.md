# PE-PRD-06 — Targets Tab

**Status:** Blocked — resumes once PE-PRD-01 and SE-PRD-05 ship
**Owner team:** Frontend (Performance)
**Blocked by:** PE-PRD-01 (page shell, `ForecastingEnabledGate`, branded types, `useTargets` scaffolding, feature-flag wiring); SE-PRD-05 (target persistence with supersede-on-edit + specialist-generated derivation reasoning available via `GET /sar-e/{account_id}/targets/{target_id}`)
**Blocks:** PE-PRD-08 (integration testing)
**Estimated effort:** 2 days

---

## 1. Context

The Targets tab is the fourth tab on the Performance page. It answers one question: "For each Effectiveness KPI × each week in the 12-week horizon, what Target is currently in effect, and how far along are we against it?"

Targets are the per-(KPI, week) numerical values the `performance_forecasting` ADK specialist produces when a user runs a simulation on the Simulations tab and clicks "Save Forecast as Targets" (PE-PRD-03). SAR-E persists them with **supersede-on-edit** semantics (SE-PRD-05 §3.4): there is only one active Target at any time for any given `(kpi_id, period)` pair, and the derivation reasoning (specialist `reasoning` + `methodology_note`) is retained on the saved record.

This tab renders that state. It does not produce Targets — all derivation happens upstream. It does, however, provide the fastest path back to a fresh derivation via a "Replace this target" shortcut that deep-links into the Simulations tab with the selected `(KPI, week)` pre-populated in the Save-Forecast-as-Targets flow.

The tab is hidden from the Performance-page nav until the setup wizard completes (`ForecastingEnabledGate` from PE-PRD-01). Once forecasting is enabled, the tab fetches `/api/v1/performance/{account_id}/targets` — a composite bundle that joins SAR-E's saved `Target` records with the latest actuals-to-date from the KPI time series. The backend composition lives in PE-PRD-01's bundle-endpoint scaffold; this PRD is frontend-only.

## 2. Scope

### In scope
- `TargetsTab.tsx` page component mounted at `/performance/targets`, rendered only when `performance_targets_tab` flag is on AND `ForecastingEnabledGate` reports `forecasting_enabled=true`
- `useTargetsTab` hook: React Query wrapper around `GET /api/v1/performance/{account_id}/targets`; keys on `(account_id, week_range_filter)`; 5-minute stale time
- `TargetsTable` component — per-KPI × per-week table of currently-active Targets with actuals-to-date progress columns; weekly rows sorted **descending** (current week at top)
- Week-range filter: default `current 12-week horizon` (current ISO week + next 11 weeks); selectable alternates documented in §6
- Per-row drill-down (inline expandable; modal is an Open Question) showing the specialist's derivation reasoning: `reasoning`, `methodology_note`, `baseline_value` at derivation time, and the `created_at` / `created_by` of the current saved Target
- "Replace this target" shortcut on each row — navigates to `/performance/simulations?replace_kpi={kpi_id}&replace_week={week_start_iso}`; the Simulations tab (PE-PRD-03) consumes those query params to pre-populate its Save-Forecast-as-Targets flow
- Empty-state within the tab when `forecasting_enabled=true` but `targets` is empty or null ("Save forecasts as Targets on the Simulations tab to populate this view", with a button linking to `/performance/simulations`)
- Loading / error states; skeleton-first render; `TargetsTable` shows a progressive fill as the bundle streams
- Branded frontend types for `TargetWithActuals`, `TargetId`, `WeekStartISO` as defined in §4
- Terminology invariant: no `Goal` / `useGoals` / `GoalsContext` / `setForecastAsGoals` strings anywhere in this tab (PE-PRD-08 audits)

### Out of scope (handled by other PRDs)
- Creating or editing Targets in-tab. All mutation flows go through Simulations (PE-PRD-03) + SAR-E `/targets` (SE-PRD-05)
- The composite `/performance/{account_id}/targets` bundle endpoint itself — owned by PE-PRD-01's backend scaffold; this PRD consumes it
- Target derivation reasoning generation — owned by SE-PRD-05 specialist
- Actuals time-series ingestion — owned by Data Pipeline (DP-PRD-02) + SAR-E (SE-PRD-02)
- Historical Target timeline / version playback — SAR-E supersedes on edit and does not retain history; a retrospective view is deferred
- Bulk delete / archive — Targets are superseded via Simulations; soft-delete goes through `DELETE /sar-e/targets/{target_id}` (SE-PRD-05) and is not surfaced in this tab in v1
- Comparison-mode rendering (`vs_target`) on the Analysis tab — owned by PE-PRD-02

## 3. Dependencies

- **PE-PRD-01 (Page shell):** provides `/performance/targets` route registration, `PerformanceDateRangeContext`, `ForecastingEnabledGate`, `useTargets` hook wrapping SAR-E `/targets` (may be reused or lifted-and-shifted into `useTargetsTab`), `EffectivenessKPIId` branded type, `performance_targets_tab` feature-flag wiring.
- **SE-PRD-05 (Target derivation specialist):** provides `/sar-e/{account_id}/targets` GET (list), `/sar-e/{account_id}/targets/{target_id}` GET (single, includes `reasoning` + `methodology_note`), and the supersede-on-edit semantics that guarantee at most one active Target per `(kpi_id, period)`. The bundle endpoint (§5) wraps these reads and joins actuals.
- **SE-PRD-06 (Analytical query layer):** provides the weekly KPI time-series read used to compute `actual_value` and `is_partial_week` for the current (in-progress) week on each row.
- **PE-PRD-03 (Simulations tab):** consumes `replace_kpi` + `replace_week` query params when the "Replace this target" shortcut navigates in. The handshake contract is defined in §6.3 of this PRD and mirrored in PE-PRD-03's scope; confirm at kickoff if PE-PRD-03 has already shipped.
- **UI component library:** uses the Soft Maximalism table primitives and `MonthYearPicker` / `WeekRangePicker` (confirm which exists). Progress indicators follow the design-system `ProgressBar` + `DeltaBadge` conventions.
- **Feature Flags (FF-PRD-03):** `performance_targets_tab` must be resolvable via `useFeatureFlag`.
- **Existing files to study:**
  - `frontend/src/pages/Performance/` — other tab implementations (PE-PRD-02 / 03 / 04) for layout conventions
  - `frontend/src/hooks/useTargets.ts` — the thin wrapper scaffolded in PE-PRD-01
  - `frontend/src/types/performance.ts` — branded-type module from PE-PRD-01

## 4. Data contract

### 4.1 Branded types (frontend)

Add to `frontend/src/types/performance.ts`:

```ts
import type { Brand } from '@/types/brand';
import type { EffectivenessKPIId, FunnelObjective } from '@/types/performance';

export type TargetId = Brand<string, 'TargetId'>;
export type WeekStartISO = Brand<string, 'WeekStartISO'>;   // ISO date string, Monday UTC
```

`EffectivenessKPIId` and `FunnelObjective` are already defined by PE-PRD-01. `WeekStartISO` is new and shared with PE-PRD-02 / 03 / 07.

### 4.2 `TargetWithActuals` (response shape)

```ts
export type TargetWithActuals = {
  target_id: TargetId;
  kpi_id: EffectivenessKPIId;
  kpi_display_name: string;             // denormalized for table rendering without an extra lookup
  objective: FunnelObjective;           // resolved via funnel mapping at bundle-composition time
  week_start: WeekStartISO;
  target_value: number;
  actual_value: number | null;          // null if the week hasn't started or has no actuals yet
  actuals_delta_absolute: number | null; // actual - target (null when actual_value is null)
  actuals_delta_percent: number | null;  // (actual - target) / target * 100; null when actual_value or target is 0
  is_partial_week: boolean;             // true for the current in-progress ISO week
  baseline_value_at_derivation: number; // captured at derivation time per SE-PRD-05 §3.4
  derived_by: 'specialist' | 'user_edit';
  derivation_reasoning_snippet: string; // first ~200 chars of the specialist's `reasoning`; full text loaded on drill-down
  methodology_note: string;             // the "statistical association only" disclaimer from SE-PRD-05
  created_at: string;                   // ISO timestamp
  created_by: string;                   // email
};
```

Rules:
- `actuals_delta_percent` uses `target_value` as the denominator. If `target_value` is zero, both delta fields are null and the UI renders `—`.
- `is_partial_week=true` rows show a partial-week visual marker (matches `KPIDataPoint.is_partial` semantics from SE-PRD-02 §3.2).
- `derivation_reasoning_snippet` is a substring of the specialist's full `reasoning`. The drill-down fetches `GET /sar-e/targets/{target_id}` directly to render the complete text (avoids bloating the bundle).

### 4.3 `TargetsBundle` (consumed from PE-PRD-01's backend)

Mirrors implementation-plan §3.2. Re-declared here so the frontend type matches exactly:

```ts
export type TargetsBundle = {
  forecasting_enabled: boolean;
  targets: TargetWithActuals[] | null;   // null when forecasting_enabled is false
  last_updated: string | null;           // ISO timestamp of the latest-modified Target in the returned set
};
```

### 4.4 `TargetsTabFilters` (local component state)

```ts
export type TargetsTabFilters = {
  week_range:
    | { kind: 'current_horizon' }        // default — current week + next 11
    | { kind: 'trailing_4' }              // last 4 complete weeks
    | { kind: 'custom'; start: WeekStartISO; end: WeekStartISO };
  objective_filter: FunnelObjective | 'all';
};
```

Default: `{ week_range: { kind: 'current_horizon' }, objective_filter: 'all' }`.

## 5. Implementation outline

| Action | File |
|--------|------|
| Modify | `frontend/src/types/performance.ts` — add `TargetId`, `WeekStartISO`, `TargetWithActuals`, `TargetsBundle`, `TargetsTabFilters` |
| Create | `frontend/src/pages/Performance/TargetsTab.tsx` — page component; feature-flag gate; `ForecastingEnabledGate` wrap; tab-level empty state; filter bar; renders `TargetsTable` |
| Create | `frontend/src/hooks/useTargetsTab.ts` — React Query hook around `GET /api/v1/performance/{account_id}/targets`; query key `['performance-targets', accountId, filters.week_range]`; 5-min stale time; returns `{bundle, isLoading, isError, refetch}` |
| Modify | `api/src/kene_api/routers/performance.py` (scaffolded by PE-PRD-01) — add `GET /api/v1/performance/{account_id}/targets?week_range_start&week_range_end` endpoint; declares `require_role(AccountRole.VIEWER, scope="account")`; delegates composition to `PerformanceBundleComposer.compose_targets_bundle` |
| Modify | `api/src/kene_api/services/performance_bundle_composer.py` (scaffolded by PE-PRD-01) — add `async compose_targets_bundle(account_id, week_range_start, week_range_end)` method; reads SAR-E `/targets` filtered by week range, joins with current `FunnelStageMapping` + `EffectivenessKPI` records for display names, joins with SE-PRD-06 weekly KPI time-series for actuals-to-date per §6.1 |
| Modify | `api/src/kene_api/models/performance_models.py` (scaffolded by PE-PRD-01) — add `TargetsBundle`, `TargetWithActuals` Pydantic models per §4.2 + §4.3 |
| Create | `api/tests/integration/test_performance_targets_bundle.py` — bundle composition (4 KPIs × 12 weeks fixture); current-mapping resolution semantics per §9 OQ 5; partial-week marker preservation; `forecasting_enabled=false` short-circuit |
| Create | `frontend/src/components/performance/targets/TargetsTable.tsx` — the table primitive; columns: KPI / Week / Target / Actual / Delta / Progress / Actions; sorted descending by `week_start`; supports row-expansion |
| Create | `frontend/src/components/performance/targets/TargetRowDrillDown.tsx` — expanded-row content; loads `/sar-e/{account_id}/targets/{target_id}` on first expand; renders `reasoning`, `methodology_note`, `baseline_value_at_derivation`, `derived_by`, `created_at`, `created_by` |
| Create | `frontend/src/components/performance/targets/TargetActualsProgress.tsx` — progress indicator: bar + `DeltaBadge` + partial-week marker |
| Create | `frontend/src/components/performance/targets/TargetsFilterBar.tsx` — week-range selector + objective filter |
| Create | `frontend/src/components/performance/targets/ReplaceTargetAction.tsx` — small anchor/button that navigates to `/performance/simulations?replace_kpi={kpi_id}&replace_week={week_start}` |
| Create | `frontend/src/components/performance/targets/TargetsTabEmptyState.tsx` — "Save forecasts as Targets on the Simulations tab to populate this view" with CTA button |
| Create | `frontend/src/pages/Performance/TargetsTab.test.tsx` — colocated unit tests per T-2 |
| Create | `frontend/src/components/performance/targets/TargetsTable.test.tsx` — table rendering + sort + filter |
| Create | `frontend/src/components/performance/targets/TargetRowDrillDown.test.tsx` — lazy fetch + render |
| Create | `frontend/src/hooks/useTargetsTab.test.ts` — query-key + stale-time behavior |
| Verify | `frontend/src/pages/Performance/PerformancePage.tsx` (from PE-PRD-01) — confirm `TargetsTab` is registered when `performance_targets_tab` flag resolves true |

## 6. API contract

### 6.1 `GET /api/v1/performance/{account_id}/targets`

Owned by PE-PRD-01's bundle-endpoint scaffold; composition logic may land in PE-PRD-06 if PE-PRD-01 defers it (confirm at kickoff). Query parameters:

```
?week_range_start={iso_date}   # optional; default = current ISO week Monday UTC
&week_range_end={iso_date}     # optional; default = week_range_start + 11 weeks
```

Response: `TargetsBundle` per §4.3. When `forecasting_enabled=false`, returns `{forecasting_enabled: false, targets: null, last_updated: null}` and the frontend renders `ForecastingEnabledGate`'s configuration CTA instead of the tab body.

Composition logic (documented here so PE-PRD-01's implementer has the full spec):
1. Read `/sar-e/{account_id}/targets` filtered by `period.week_start >= week_range_start AND period.week_start <= week_range_end`.
2. For each returned `Target`, look up the active `FunnelStageMapping` to resolve `objective` and the `EffectivenessKPI` record to resolve `kpi_display_name`.
3. For each `(kpi_id, week_start)` pair, read the weekly `KPIDataPoint` via SE-PRD-06's analytical query layer to resolve `actual_value` + `is_partial_week`. If no data point exists (future week), set `actual_value=null`.
4. Return the joined list sorted descending by `week_start`.

### 6.2 `GET /api/v1/sar-e/{account_id}/targets/{target_id}` (drill-down)

Used directly by `TargetRowDrillDown` to fetch the full `reasoning` text. Returns the complete `Target` Pydantic model from SE-PRD-05 §3.4 including `reasoning`, `methodology_note`, `baseline_value`, `derivation_context_hash`, and audit fields.

### 6.3 Replace-target handshake with Simulations (PE-PRD-03)

When the user clicks "Replace this target" on a row:

```
Navigate to: /performance/simulations?replace_kpi={kpi_id}&replace_week={week_start_iso}
```

PE-PRD-03's Simulations tab must:
1. Read the two query params on mount.
2. If both are present, pre-scroll to the Save-Forecast-as-Targets flow with that `(kpi_id, week)` pre-selected.
3. Clear the query params from the URL after consuming them (replace-state; no history entry).

This is a one-way deep link; no callback. The contract is recorded in this PRD and must be mirrored in PE-PRD-03's scope before both ship.

## 7. Acceptance criteria

1. With `performance_targets_tab=false`, navigating to `/performance/targets` renders a 404-style "Tab not available" screen; the Targets tab does not appear in the Performance-page tab nav.
2. With `performance_targets_tab=true` and `forecasting_enabled=false`, the Targets tab is hidden from the nav (enforced by `ForecastingEnabledGate`); direct navigation to `/performance/targets` redirects to `/performance/configuration`.
3. With `performance_targets_tab=true`, `forecasting_enabled=true`, and `targets=[]`, the tab renders `TargetsTabEmptyState` with the CTA linking to `/performance/simulations`.
4. With a populated `targets` array (say 4 KPIs × 12 weeks = 48 rows), the `TargetsTable` renders all rows sorted descending by `week_start` with the current week at the top; partial-week rows show the partial-week marker.
5. The `actuals_delta_percent` column is formatted as `+12.3%` / `-4.7%` / `—` (for null); positive deltas use the design-system "positive" color, negative use "caution", zero is neutral.
6. Clicking a row expands it inline and fires `GET /sar-e/{account_id}/targets/{target_id}` once; subsequent collapses/expands of the same row do not re-fetch.
7. The drill-down renders `reasoning` in full, `methodology_note` verbatim (the "statistical association only" disclaimer), and the metadata block (`derived_by`, `baseline_value_at_derivation`, `created_at`, `created_by`).
8. Clicking "Replace this target" on a row navigates to `/performance/simulations?replace_kpi={kpi_id}&replace_week={week_start}`; the URL is visible in the address bar; PE-PRD-03's handshake (§6.3) consumes the params.
9. Changing the week-range filter to `trailing_4` re-fetches the bundle with the new window; React Query key includes the filter so the cache does not serve stale data.
10. Changing the objective filter is purely client-side (no re-fetch); rows hide/show based on `objective === filter` or `filter === 'all'`.
11. `last_updated` from the bundle is surfaced as a "Targets last updated at ..." label at the tab header.
12. Loading state renders a skeleton table with the right column count; error state renders a retry button that calls `refetch`.
13. `grep -rn 'Goal\|useGoals\|GoalsContext\|setForecastAsGoals' frontend/src/pages/Performance/TargetsTab.tsx frontend/src/components/performance/targets/ frontend/src/hooks/useTargetsTab.ts` returns zero matches.
14. `npm run typecheck` passes; `npm run format.fix` passes; all colocated tests green.

## 8. Test plan

**Unit tests** (`useTargetsTab.test.ts`):
- Hook returns `{isLoading: true}` on first render.
- Hook fires the correct URL when `week_range = current_horizon` (verifies `week_range_start` / `week_range_end` query params).
- Hook fires a new request when `week_range` changes.
- Hook does NOT fire when `forecasting_enabled=false` (short-circuits to a static response).
- Stale time = 5 min honored.

**Unit tests** (`TargetsTable.test.tsx`):
- Empty array renders empty-state (separate from tab-level empty-state — this is "filter produced zero rows").
- 48-row input renders 48 `<tr>`s sorted descending by `week_start` (test with mixed KPIs).
- Partial-week marker shows on the row whose `is_partial_week=true`.
- `actuals_delta_percent` formatting matches §7 criterion 5 (three fixture cases: positive, negative, zero / null).
- Row-click expands inline; only one row expanded at a time (confirm at kickoff if stacking multiple expansions is desired).

**Unit tests** (`TargetRowDrillDown.test.tsx`):
- On first mount, fires `GET /sar-e/{account_id}/targets/{target_id}`; on subsequent mounts of the same target_id within the component tree's lifetime, does NOT re-fetch (React Query cache).
- Renders `methodology_note` verbatim.
- Renders `reasoning` full-text (verifies it's NOT just the snippet).
- Error state: fetch failure shows retry button.

**Unit tests** (`TargetsTab.test.tsx`):
- Feature flag off → not-available screen.
- `forecasting_enabled=false` → redirect (mock `useNavigate`).
- `forecasting_enabled=true` + empty targets → `TargetsTabEmptyState`.
- "Replace this target" click → verifies correct navigation URL with both query params.
- Objective filter change → correctly filters rendered rows without a new network request.

**Integration-style (MSW + React Testing Library)**:
- Full happy path: mount the tab with a seeded bundle response → expand a row → verify single-target fetch fires → click "Replace this target" → verify navigation URL.

**Lint guard:** ESLint rule (installed in PE-PRD-03 per implementation-plan §9) fires on any `Goal*` usage in this tab's files.

## 9. Risks & open questions

| Risk / question | Mitigation |
|---|---|
| `TargetsBundle` composition latency on accounts with dense calendars | SAR-E list `/targets` is already filtered by week range; the actuals join is 4 KPIs × 12 weeks = 48 single-doc reads via SE-PRD-06's cache. Bundle p95 target: <300 ms. Escalate if profiling shows otherwise. |
| Inline drill-down vs modal | Inline reads better for comparison across rows (quick expand + collapse); modal is easier to read long reasoning. Ship inline in v1; add a "Expand to modal" affordance if product feedback asks. Open Question. |
| SAR-E `GET /sar-e/targets/{target_id}` round-trip on every expand | 5-min React Query cache + per-target key; subsequent expansions of the same row are cache hits. |
| Partial-week delta meaningful? | For `is_partial_week=true`, the denominator (full-week Target) is larger than the cumulative actual, so `actuals_delta_percent` will usually read as a large negative. Surface `(in-progress)` adjacent to the percentage so users don't misread it as a miss. |
| Week-range filter grows complex over time | v1 ships three presets (current_horizon, trailing_4, custom). Add more only on demand. |
| Terminology regression | PE-PRD-03 lands the ESLint rule disallowing `Goal*` identifiers; PE-PRD-08's grep audit is the belt-and-suspenders check. |

### Open questions

1. **Drill-down: inline expand vs modal?** Default: inline expand per §2 scope. Confirm at kickoff; switching to modal is a 1-day revision.
2. **Multi-row expand?** Ship single-row-expanded-at-a-time in v1 (prevents excessive fetches + preserves table compactness); revisit if users want side-by-side reasoning comparison.
3. **Export-to-CSV of the current view?** Out of scope for v1; users can pin a Dashboard to persist the state. Confirm at kickoff.
4. **Does the bundle include soft-deleted Targets?** No — SAR-E's list endpoint filters `is_active=true` by default; the Targets tab never shows soft-deleted rows.
5. **What happens if the active `FunnelStageMapping` changes mid-horizon?** The bundle composer uses the *latest* mapping to resolve `objective` for every row, not the historical mapping. Rationale: Targets tab is forward-looking; retroactive re-keying would mislead. Confirm with SE-PRD-06 owner.

## 10. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md) §3.2 `TargetsBundle`, §4 API surface, §6 PE-PRD-06
- Upstream: [SE-PRD-05 Target derivation specialist](../../sar-e/implementation-plan.md#se-prd-05--target-derivation-specialist) §3.4 target persistence + supersede-on-edit
- Upstream: [SE-PRD-06 Analytical query layer](../../sar-e/implementation-plan.md#se-prd-06--analytical-query-layer) weekly KPI time-series reads
- Sibling: [PE-PRD-01 Page shell](./PE-PRD-01-page-shell-and-routing.md) `ForecastingEnabledGate`, branded types, feature-flag wiring
- Sibling: [PE-PRD-03 Simulations tab](./PE-PRD-03-simulations-tab.md) Save-Forecast-as-Targets flow + replace-target handshake
- Style reference: [DB-PRD-01 Dashboard Data Model & API](../../dashboards/projects/DB-PRD-01-data-model-and-api.md)
- Feature Flags: [FF-PRD-03 `useFeatureFlag` hook](../../feature-flags/projects/FF-PRD-03-frontend-sdk-and-e2e.md)
- CLAUDE.md rules in scope: C-1 (TDD), C-5 (branded IDs), C-6 (`import type`), C-7 (minimal comments), C-8 (prefer `type`); T-2 (colocated frontend tests), T-4 (separate pure vs DB), T-8 (structural assertions); G-2 (`npm run format.fix`), G-3 (`npm run typecheck`); O-2 (shared types between frontend and API)
