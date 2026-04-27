# PE-PRD-01 — Page Shell, Routing & Shared State

**Status:** Draft — ready to start once UI-PRD-01 ships
**Owner team:** Frontend (Performance)
**Blocked by:** UI-PRD-01 (design tokens + shell layout the six tabs live in); FF-PRD-03 (the `useFeatureFlag` hook every tab mounts behind)
**Blocks:** PE-PRD-02, PE-PRD-03, PE-PRD-04, PE-PRD-05, PE-PRD-06, PE-PRD-07
**Estimated effort:** 1–2 days

---

## 1. Context

Performance is a new top-level page at `/performance` with **six tabs** in this order (per Figma): Analysis, **Dashboards**, Simulations, Targets, Diagnostics, Configuration. Every downstream PRD in the component (PE-PRD-02 through PE-PRD-07) ships a tab or wizard against the shell published here, and the **Dashboards** tab is owned and filled in by the Dashboards component (DB-PRD-02 list / DB-PRD-03 details). This PRD delivers that shell — nothing more — so the per-tab work can parallelize the moment its upstream data dependencies land.

Three shell responsibilities anchor this PRD:

1. **Opt-in enablement (SAR-E only).** SAR-E is disabled at account creation. Until the setup wizard completes, the four SAR-E-backed tabs (Analysis / Simulations / Targets / Diagnostics) are hidden from the nav entirely; **Dashboards** and **Configuration** remain visible regardless because Dashboards is independent of SAR-E (powered by Project Tasks + Automations, not by the analytical backend). Configuration renders a single empty-state CTA pointing at `/performance/setup` until the wizard completes; Dashboards renders the regular DB-PRD-02 list (or its empty state) without gating. Once SAR-E's `/config/status` flips to `enabled=true`, all six tabs appear and `/performance` defaults to Analysis. The gate that drives this behavior lives here, not in each tab.
2. **Shared page state.** Every data tab reads the same week-indexed period and comparison mode. Hoisting that into a `PerformanceDateRangeContext` at the shell — versus redeclaring it per tab — means a user's date selection survives tab switches and the per-tab query keys stay trivially composable.
3. **Terminology scaffolding.** The Figma export labels forecast-derived values as "Goals" in Simulations; the product decision is to rename that concept to "Targets" everywhere in this component (Goals remain a Knowledge-Graph concept). The `useTargets` hook scaffolding and the naming convention for every downstream hook / context / component ships here so PE-PRD-03 does not need to re-introduce the rename mid-build.

This PRD does no live data consumption. All TanStack Query wiring, bundle fetches, and chart rendering ships in the per-tab PRDs.

## 2. Scope

### In scope

- `PerformancePage` at `/performance` with **six** child routes (in this tab order): `/performance/analysis`, `/performance/dashboards`, `/performance/simulations`, `/performance/targets`, `/performance/diagnostics`, `/performance/configuration`
- Dedicated `/performance/setup` route placeholder (full wizard ships in PE-PRD-05; this PRD mounts a route target so `/performance/setup` resolves instead of hitting UI-PRD-01's `NotFoundPage` during parallel development)
- `ForecastingEnabledGate` React component: reads SAR-E `/config/status` once per page mount; when `enabled=false`, hides **Analysis / Simulations / Targets / Diagnostics** from the tab nav and renders only **Dashboards + Configuration**. Configuration renders an empty-state CTA ("Set up forecasting") that navigates to `/performance/setup`; Dashboards renders DB-PRD-02's list (or its own empty state) regardless of SAR-E state. When `enabled=true`, renders all six tabs.
- Default-route logic on `/performance`: redirect to `/performance/configuration` when `enabled=false`; redirect to `/performance/analysis` when `enabled=true`
- `PerformanceDateRangeContext` provider — week-indexed `period: DateRange` plus `comparisonMode: ComparisonMode` — mounted inside the SAR-E-gated tabs only (Analysis / Simulations / Targets / Diagnostics). Not mounted above Dashboards or Configuration — pre-wizard there is no range to carry, and Dashboards uses its own filtering surfaces (DB-PRD-02 / DB-PRD-03)
- Five branded types in `frontend/src/types/performance.ts`: `FunnelObjective`, `EffectivenessKPIId`, `ComparisonMode`, `CostDimension`, `WizardStep`
- `useTargets` hook scaffolding in `frontend/src/hooks/useTargets.ts` — a typed wrapper around SAR-E `/targets` that exposes `{targets, isLoading, error, refetch}`. The hook defines the query key and response types; the first PRD to actually fetch is PE-PRD-03. This PRD registers the hook + types + a stub service call so downstream PRDs import from a stable module boundary on day one
- Feature-flag wiring for **seven** flags via FF-PRD-03's `useFeatureFlag` hook: `performance_analysis_tab`, `performance_dashboards_tab`, `performance_simulations_tab`, `performance_targets_tab`, `performance_diagnostics_tab`, `performance_configuration_tab`, `performance_setup_wizard`. Flags are registered in the feature-flags registry (`frontend/src/lib/featureFlags/registry.ts`) so the batch evaluation picks them up at provider mount; each tab is conditionally rendered based on its flag's resolved `enabled` state
- Placeholder components for each of the six tab routes so the nav works end-to-end immediately; each placeholder renders a single "Coming soon" card naming the PRD that replaces it. These stubs get swapped out by PE-PRDs 02 / 03 / 04 / 06 / 07 (Analysis / Simulations / Configuration / Targets / Diagnostics) and DB-PRD-02 (Dashboards)
- Unit tests for the gate, the date-range context, the default-route redirect, and the feature-flag-driven tab hiding

### Out of scope (handled by other PRDs)

- Any live data fetching against SAR-E bundle endpoints (PE-PRD-02, 03, 04, 06, 07)
- The setup wizard UI + its multi-step flow + persistent draft state (PE-PRD-05)
- The Funnel Stage Mapping editor, Thresholds editor, Channel Coverage editor (PE-PRD-04)
- The four-stage funnel viz, 53-week trendline, cost rollups, External Factors panel (PE-PRD-02)
- The 12-week baseline-vs-target chart, Run Simulation trigger, Save Forecast as Targets action (PE-PRD-03)
- Targets table with actuals-to-date + derivation drill-down (PE-PRD-06)
- Model-health + ingestion-status panels (PE-PRD-07)
- Terminology-rename grep-audit across Figma-derived code — runs as an acceptance gate in PE-PRD-08 after the Simulations tab ships

## 3. Dependencies

- **UI-PRD-01 (Design System Foundation):** supplies the shell layout, tab primitives, and Soft Maximalism tokens every placeholder + gate + CTA uses. The Performance page registers as a new top-level nav entry against the shell's sidebar slot.
- **FF-PRD-03 (Feature Flags Frontend SDK):** publishes `FeatureFlagsProvider` + `useFeatureFlag(key)`. Both are already mounted in `App.tsx` above `AuthContext`; this PRD registers seven new flag keys in `frontend/src/lib/featureFlags/registry.ts` so they're in the batch evaluation on provider mount.
- **DB-PRD-02 (Dashboards Tab & List):** owns and fills in the **Dashboards** tab content (`DashboardsSection`). PE-PRD-01 reserves the tab slot + route; DB-PRD-02 mounts its list view inside that slot. The legacy `frontend/src/pages/Performance.tsx` is deleted by this PRD entirely; UI-PRD-07 (the original presentation-only redesign) is **retired and subsumed by PE-PRD-01** (see component README §1.4 and `docs/design/DESIGN-REVIEW-LOG.md`) — no coordination remains.
- **SE-PRD-01 (SAR-E Configuration foundation):** publishes `GET /api/v1/sar-e/{account_id}/config/status`. `ForecastingEnabledGate` reads this endpoint. No write coupling here — status is read-only from Performance's perspective.
- **Existing files to study:**
  - `frontend/src/App.tsx` — shell-level routing + `FeatureFlagsProvider` mount
  - `frontend/src/pages/Performance.tsx` — legacy page to replace
  - `frontend/src/contexts/AuthContext.tsx` — context pattern (provider + hook + type exports) this PRD's `PerformanceDateRangeContext` mirrors
  - `frontend/src/hooks/useSettingsNavigation.ts` — hook pattern for URL-backed state
  - `frontend/src/lib/featureFlags/registry.ts` — flag-key registration point
  - `frontend/src/contexts/FeatureFlagsContext.tsx` — `useFeatureFlag` hook entry point
  - `frontend/src/components/layout/Sidebar.tsx` — top-level nav registration

## 4. Data contract

### 4.1 Branded types

```typescript
// frontend/src/types/performance.ts
import type { Brand } from '@/types/brand';

export type FunnelObjective =
  | 'Problem Awareness'
  | 'Brand Awareness'
  | 'Consideration'
  | 'Conversion';

export type EffectivenessKPIId = Brand<string, 'EffectivenessKPIId'>;

export type ComparisonMode = 'wow' | 'yoy' | 'vs_target';

export type CostDimension = 'channel' | 'campaign' | 'platform' | 'owner';

export type WizardStep = 'welcome' | 'define_kpis' | 'backfill_depth' | 'review';

// Week-indexed period used across every tab. The `start` field is always a
// Monday (ISO week start) in account-local timezone; `end` is the Sunday of
// the same ISO week. Multi-week ranges end on the Sunday of the final week.
export interface DateRange {
  start: string; // ISO date (YYYY-MM-DD)
  end: string;   // ISO date (YYYY-MM-DD)
}
```

Brand type utility lives at `frontend/src/types/brand.ts` per existing convention (see `dashboard.ts`'s `DashboardPlanId` for the same pattern).

### 4.2 Shared state shape

```typescript
// frontend/src/contexts/PerformanceDateRangeContext.tsx
export interface PerformanceDateRangeValue {
  period: DateRange;
  comparisonMode: ComparisonMode;
  setPeriod: (next: DateRange) => void;
  setComparisonMode: (next: ComparisonMode) => void;
}
```

Default `period` is the current ISO week (Monday → Sunday in account-local timezone, computed at provider mount). Default `comparisonMode` is `'wow'`. Both are persisted to `sessionStorage` under `perf.dateRange` and `perf.comparisonMode` so tab switches preserve state within a session.

### 4.3 `useTargets` hook contract

```typescript
// frontend/src/hooks/useTargets.ts
export interface TargetWithActuals {
  target_id: string;
  kpi_id: EffectivenessKPIId;
  period: DateRange;
  value: number;
  baseline_value: number;
  reasoning: string | null;
  // Actuals-to-date — populated by PE-PRD-06's bundle; null in this PRD's
  // scaffolding until the backend endpoint returns it.
  actual_to_date: number | null;
}

export interface UseTargetsResult {
  targets: TargetWithActuals[];
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useTargets(accountId: string): UseTargetsResult;
```

In this PRD the hook is registered but returns `{targets: [], isLoading: false, error: null, refetch: () => {}}` — a no-op. The point is to publish the module boundary; PE-PRD-06 implements the live TanStack Query call against SAR-E `/targets`. Downstream PRDs (PE-PRD-02 `vs_target` comparison, PE-PRD-03 Save-as-Targets) import from this path from day one.

### 4.4 `ForecastingEnabledGate` contract

```typescript
// frontend/src/components/performance/ForecastingEnabledGate.tsx
export interface ForecastingEnabledGateProps {
  accountId: string;
  children: ReactNode;  // rendered when enabled=true
}

// Internally reads SAR-E /config/status once per mount via TanStack Query
// (queryKey: ['sar-e', 'config-status', accountId], staleTime: 60_000).
// While loading: renders a skeleton of the tab nav.
// When enabled=false: renders <ConfigurationEmptyState /> (no children).
// When enabled=true: renders <PerformanceDateRangeProvider>{children}</...>.
```

The gate exposes no imperative API. Downstream consumers that need the current status (e.g., PE-PRD-04's Configuration tab rendering the "Resume setup" banner variant) call the same TanStack Query key directly via `useQuery` — cache is shared.

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `frontend/src/types/performance.ts` — branded types per §4.1 |
| Create | `frontend/src/contexts/PerformanceDateRangeContext.tsx` — provider + `usePerformanceDateRange` hook |
| Create | `frontend/src/components/performance/ForecastingEnabledGate.tsx` — enablement wrapper |
| Create | `frontend/src/components/performance/ConfigurationEmptyState.tsx` — CTA card rendered pre-wizard |
| Create | `frontend/src/pages/Performance/PerformancePage.tsx` — page shell; registers tab router |
| Create | `frontend/src/pages/Performance/AnalysisTabPlaceholder.tsx` — "Coming soon" stub replaced by PE-PRD-02 |
| Create | `frontend/src/pages/Performance/DashboardsTabPlaceholder.tsx` — stub replaced by DB-PRD-02 |
| Create | `frontend/src/pages/Performance/SimulationsTabPlaceholder.tsx` — stub replaced by PE-PRD-03 |
| Create | `frontend/src/pages/Performance/TargetsTabPlaceholder.tsx` — stub replaced by PE-PRD-06 |
| Create | `frontend/src/pages/Performance/DiagnosticsTabPlaceholder.tsx` — stub replaced by PE-PRD-07 |
| Create | `frontend/src/pages/Performance/ConfigurationTabPlaceholder.tsx` — stub replaced by PE-PRD-04 |
| Create | `frontend/src/pages/Performance/SetupRoutePlaceholder.tsx` — stub replaced by PE-PRD-05 |
| Create | `frontend/src/hooks/useTargets.ts` — hook scaffolding per §4.3 |
| Create | `frontend/src/services/performanceApi.ts` — axios client boundary used by every tab's bundle call (initial surface: `getConfigStatus(accountId)`; bundle fetchers added per tab PRD) |
| Modify | `frontend/src/App.tsx` — replace legacy `Performance.tsx` route with `PerformancePage`; register nested routes for `analysis`, `dashboards`, `simulations`, `targets`, `diagnostics`, `configuration`, `setup`; register `/performance` index redirect driven by gate |
| Modify | `frontend/src/lib/featureFlags/registry.ts` — add seven flag keys: `performance_analysis_tab`, `performance_dashboards_tab`, `performance_simulations_tab`, `performance_targets_tab`, `performance_diagnostics_tab`, `performance_configuration_tab`, `performance_setup_wizard` |
| Modify | `frontend/src/components/layout/Sidebar.tsx` — retain Performance nav entry; no icon change |
| Delete | `frontend/src/pages/Performance.tsx` — legacy page; replaced by `pages/Performance/PerformancePage.tsx`. Any callers (imports, route references) migrate to the new entrypoint |
| Create | `frontend/src/pages/Performance/__tests__/PerformancePage.test.tsx` |
| Create | `frontend/src/components/performance/__tests__/ForecastingEnabledGate.test.tsx` |
| Create | `frontend/src/contexts/__tests__/PerformanceDateRangeContext.test.tsx` |
| Create | `frontend/src/hooks/__tests__/useTargets.test.ts` |
| Create | `frontend/e2e/performance-shell.spec.ts` — end-to-end shell test (gated-nav + default redirect) |

### Routing diagram

```
App.tsx
 └─ /performance                               → <PerformancePage />
     ├─ (index)                                → <Navigate /> driven by gate:
     │                                            enabled=false → /performance/configuration
     │                                            enabled=true  → /performance/analysis
     ├─ /performance/analysis                  → <ForecastingEnabledGate>
     │                                            └─ <AnalysisTabPlaceholder />
     ├─ /performance/dashboards                → <DashboardsTabPlaceholder />
     │                                            (not wrapped in gate — Dashboards is independent of SAR-E;
     │                                             DB-PRD-02 replaces this stub with its list view)
     ├─ /performance/simulations               → <ForecastingEnabledGate>
     │                                            └─ <SimulationsTabPlaceholder />
     ├─ /performance/targets                   → <ForecastingEnabledGate>
     │                                            └─ <TargetsTabPlaceholder />
     ├─ /performance/diagnostics               → <ForecastingEnabledGate>
     │                                            └─ <DiagnosticsTabPlaceholder />
     ├─ /performance/configuration             → <ConfigurationTabPlaceholder />
     │                                            (not wrapped in gate — pre-wizard CTA, post-wizard PE-PRD-04 panels)
     └─ /performance/setup                     → <SetupRoutePlaceholder />
                                                  (replaced by PE-PRD-05)
```

Configuration and Dashboards routes are intentionally *not* wrapped in `ForecastingEnabledGate`. Configuration is the pre-wizard landing (and post-wizard editor home for PE-PRD-04); Dashboards is independent of SAR-E entirely (powered by Project Tasks + Automations). The gate's sole job is to hide the four SAR-E-backed tabs (Analysis / Simulations / Targets / Diagnostics) from the nav until the wizard completes.

### Feature-flag behavior

Each tab's visibility in the nav is the AND of (a) `ForecastingEnabledGate` state and (b) its corresponding flag. The flag wrapping is cheap — each flag defaults to `enabled=true` in the registry with a targeting rule (FF-PRD-02) flipping it off to dark-launch a tab. The flag is evaluated at provider mount; subsequent tab switches do not re-evaluate. If a user's flag flips mid-session, the change takes effect on next page load per FF-PRD-03's 60-second stale time.

The `performance_setup_wizard` flag gates the `/performance/setup` route and the CTA's click target in `ConfigurationEmptyState`. When disabled, the CTA label changes to "Setup unavailable" and the link is inert — this is the kill-switch path for PE-PRD-05 rollout.

## 6. API contract

### 6.1 Consumed: `GET /api/v1/sar-e/{account_id}/config/status` (SE-PRD-01)

```
GET /api/v1/sar-e/{account_id}/config/status
```

Response (subset consumed here — full shape is SE-PRD-01's contract):

```typescript
interface SarEConfigStatus {
  enabled: boolean;
  setup_wizard_completed: boolean;
  // Additional fields (connected_integrations, available_kpi_sources, etc.)
  // are consumed by PE-PRD-05's wizard, not here.
}
```

Consumption rules:
- `ForecastingEnabledGate` reads `enabled` only. `setup_wizard_completed` is read by PE-PRD-04 / PE-PRD-05 via the same TanStack Query key — cache is shared across tabs.
- Query key: `['sar-e', 'config-status', accountId]`.
- Stale time: 60 seconds (matches FF-PRD-03's convention for reference-data reads).
- Refetch triggers: window focus (default), tab switch back to Performance (explicit `refetch()` at page mount), explicit `invalidateQueries` after wizard completion (called by PE-PRD-05).
- Error handling: on 5xx / network error, the gate renders the "Coming soon" variant with a retry button rather than defaulting to enabled-false (fail-closed-for-nav, fail-open-for-troubleshooting).

### 6.2 Not owned here

This PRD does not ship any performance-bundle endpoints. Each tab's bundle fetcher lands in its own PRD:
- `/performance/{account_id}/analysis` — PE-PRD-02
- `/performance/{account_id}/simulations` — PE-PRD-03
- `/performance/{account_id}/targets` — PE-PRD-06
- `/performance/{account_id}/diagnostics` — PE-PRD-07
- `/performance/{account_id}/configuration` — PE-PRD-04

The `performanceApi.ts` service-layer boundary is created here with only `getConfigStatus(accountId)`; the bundle fetchers are additive additions per tab PRD.

## 7. Acceptance criteria

1. Navigating to `/performance` on a new account (SAR-E `enabled=false`) redirects to `/performance/configuration`; the tab nav shows **Dashboards + Configuration** only; Analysis / Simulations / Targets / Diagnostics are absent.
2. Navigating to `/performance` on an enabled account (`enabled=true`) redirects to `/performance/analysis`; the tab nav shows all six tabs in order Analysis / Dashboards / Simulations / Targets / Diagnostics / Configuration.
3. Navigating directly to `/performance/analysis` on a disabled account (`enabled=false`) redirects to `/performance/configuration` (no "flash" of the placeholder).
4. Navigating directly to `/performance/dashboards` on a disabled account renders `<DashboardsTabPlaceholder />` (no redirect — Dashboards is not gated by SAR-E).
5. Navigating directly to `/performance/setup` resolves to `<SetupRoutePlaceholder />` and does not redirect — the wizard route is independently reachable regardless of `enabled` state, so PE-PRD-05 can mount its flow.
6. The `ConfigurationEmptyState` CTA renders on `/performance/configuration` when `enabled=false`; clicking it navigates to `/performance/setup`.
7. Each of the six placeholder routes renders a card identifying the PRD that replaces it (e.g., "Analysis — PE-PRD-02", "Dashboards — DB-PRD-02"). These are strictly dev-scaffolding and live in test fixtures only; production builds ship the real components once each PRD merges.
8. `PerformanceDateRangeContext` defaults to the current ISO week and `'wow'` comparison mode on first render.
9. Changing the period via `setPeriod` on one tab and switching to another tab preserves the new period (persisted to `sessionStorage`).
10. Reloading the page within the same session restores the last-set period + comparison mode from `sessionStorage`.
11. Opening a new incognito session (no `sessionStorage`) falls back to the current-week + `'wow'` defaults.
12. Disabling `performance_analysis_tab` via feature-flag override (`?ff.performance_analysis_tab=off`) hides the Analysis tab from the nav on enabled accounts; the other five tabs remain visible.
13. Disabling `performance_dashboards_tab` hides the Dashboards tab on both enabled and disabled accounts; nav reflows correctly.
14. Disabling `performance_setup_wizard` via the same mechanism disables the CTA on `ConfigurationEmptyState` — the button label changes and the click target is inert.
15. `useTargets(accountId)` returns `{targets: [], isLoading: false, error: null, refetch: expect.any(Function)}` in this PRD. Invoking `refetch()` is a no-op (does not throw).
16. `FunnelObjective`, `EffectivenessKPIId`, `ComparisonMode`, `CostDimension`, `WizardStep` are exported from `frontend/src/types/performance.ts` and importable by at least one consumer in this PRD's tests.
17. `npm run build`, `npm run typecheck`, `npm run format.fix` all clean.
18. `performance-shell.spec.ts` Playwright test passes: (a) new account → lands on Configuration, only Dashboards + Configuration tabs visible; (b) enabled account → lands on Analysis, all six tabs visible in the documented order.

## 8. Test plan

**Unit tests** (`ForecastingEnabledGate.test.tsx`):
- `enabled=false` renders `<ConfigurationEmptyState />` and does not render `children`
- `enabled=true` renders `children` wrapped in `<PerformanceDateRangeProvider>`
- Loading state renders a skeleton (no flash of either variant)
- Network error renders a retry button and does not silently default to `enabled=true`
- Mock `useQuery` for `['sar-e', 'config-status', accountId]`; assert the query key and `staleTime: 60_000`

**Unit tests** (`PerformanceDateRangeContext.test.tsx`):
- Default `period` is the current ISO week (Monday → Sunday); assert via a fake-timer wrapping `new Date()`
- Default `comparisonMode` is `'wow'`
- `setPeriod` and `setComparisonMode` update context value in one render
- `sessionStorage` round-trip: set period, remount provider → restored
- Empty `sessionStorage` → defaults restored
- Malformed `sessionStorage.perf.dateRange` → defaults restored without throwing

**Unit tests** (`PerformancePage.test.tsx`):
- `/performance` with `enabled=false` → redirect to `/performance/configuration`
- `/performance` with `enabled=true` → redirect to `/performance/analysis`
- `/performance/analysis` with `enabled=false` → redirect to `/performance/configuration`
- `/performance/dashboards` with `enabled=false` → renders `<DashboardsTabPlaceholder />` (no redirect)
- `/performance/setup` renders `<SetupRoutePlaceholder />` regardless of `enabled`
- All six tab placeholders render their PRD labels
- Feature-flag override: `performance_analysis_tab=off` hides Analysis tab from nav on enabled account
- Feature-flag override: `performance_dashboards_tab=off` hides Dashboards tab in both states

**Unit tests** (`useTargets.test.ts`):
- Returns the documented default shape
- `refetch()` is callable and does not throw
- Import path resolves from `@/hooks/useTargets`

**Playwright integration** (`performance-shell.spec.ts`):
- Login as a user with a fresh account (`enabled=false` seeded) → visit `/performance` → assert URL is `/performance/configuration` → assert two tabs visible (`Dashboards`, `Configuration`)
- Login as a user with a backfilled account (`enabled=true` seeded) → visit `/performance` → assert URL is `/performance/analysis` → assert six tabs visible in order Analysis / Dashboards / Simulations / Targets / Diagnostics / Configuration
- Click Configuration tab's CTA → assert URL is `/performance/setup`
- Direct-navigate to `/performance/diagnostics` on a fresh account → assert redirect to `/performance/configuration`

## 9. Risks & open questions

| Risk / question | Mitigation |
|---|---|
| Gate check adds 1 RTT to every Performance page load | `staleTime: 60_000` + cache-shared across tabs. After first load the second tab mount reads from cache. |
| Redirect-during-render flicker on `/performance/analysis` when gate is still loading | The gate renders a skeleton of the tab nav (not a full tab view) while loading. The redirect fires only after status resolves. Acceptable trade: 1 paint of a skeleton vs. 1 paint of the wrong content. |
| Feature-flag provider not ready on first render | `FeatureFlagsProvider` is mounted above `AuthContext` per FF-PRD-03; by the time Performance renders, flags are resolved. If batch eval is still pending, each `useFeatureFlag` call returns `{isLoading: true}` and the tab is hidden from the nav (default-deny while loading). |
| Legacy `Performance.tsx` still referenced after delete | The `App.tsx` modification is atomic — route is redirected and import is removed in the same diff. Grep audit in the test plan confirms zero stale references. |
| `useTargets` scaffolding encourages premature caller coupling | The hook's live shape is specified in §4.3; downstream PRDs (PE-PRD-02 `vs_target`, PE-PRD-03 Save-as-Targets, PE-PRD-06 Targets tab) import from the stable module boundary from day one. No mock / stub swap is required when the live implementation lands. |
| `PerformanceDateRangeContext` in `sessionStorage` leaks across accounts | The provider key is account-scoped (`perf.dateRange.${accountId}`); switching accounts produces a fresh default. Assertion in test plan. |

Cross-references to implementation-plan risks that apply to this phase: none directly — the plan's risks (funnel-mapping churn, 53-week trendline perf, wizard abandonment, Goal→Target leakage) are all downstream of the shell and land in PE-PRDs 02 / 03 / 05 / 08.

### Open questions

1. **Should the `/performance` index route inspect the URL's prior search params?** If a user deep-links to `/performance?tab=simulations`, the current plan ignores the query string and redirects by `enabled`. Decision deferred to PE-PRD-02 kickoff; likely a no-op (our routing uses path segments, not query state).
2. **Should the gate's network-error state surface a specific retry message?** First pass: generic "Couldn't load Performance; retry." Revisit after PE-PRD-08's accessibility audit.

## 10. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md) §6 PE-PRD-01
- Sibling (downstream): [PE-PRD-02](./PE-PRD-02-analysis-tab.md) — first consumer of this shell
- Sibling (downstream): PE-PRD-03, PE-PRD-04, PE-PRD-05, PE-PRD-06, PE-PRD-07 — all mount against the shell published here
- Upstream: [UI-PRD-01](../../ui/projects/UI-PRD-01-design-system-foundation.md) — design tokens + shell layout
- Upstream: [FF-PRD-03](../../feature-flags/projects/FF-PRD-03-frontend-sdk-and-e2e.md) — `useFeatureFlag` hook + registry pattern
- Upstream: [SE-PRD-01](../../sar-e/implementation-plan.md) §6 — `/config/status` endpoint owner
- Figma reference: `docs/figma-export/src/app/pages/performance/` (note: AnalysisSection.tsx and FunnelSection.tsx are not present in the current export — rebuild from Figma designs at PE-PRD-02 kickoff)
- CLAUDE.md rules in scope: BP-1; C-1, C-3, C-5, C-6, C-8; T-2, T-5, T-8; G-2, G-3
