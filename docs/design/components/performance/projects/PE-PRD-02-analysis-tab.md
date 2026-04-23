# PE-PRD-02 — Analysis Tab

**Status:** Draft — ready to start once PE-PRD-01, SE-PRD-06, SE-PRD-01, DB-PRD-03, and PR-PRD-07 ship
**Owner team:** Frontend (Performance)
**Blocked by:** PE-PRD-01 (page shell + `ForecastingEnabledGate` + `PerformanceDateRangeContext` + branded types); SE-PRD-06 (analytical query layer — `/analytics/funnel`, `/analytics/trendline/{objective}`, `/analytics/cost-rollup`, `/analytics/related-metrics`); SE-PRD-01 (`/config/status` gate); DB-PRD-03 (LineChart widget from Dashboards, reused for 53-week trendlines); PR-PRD-07 (Calendar read with `category in ["holiday", "promotion", "event"]` for External Factors panel)
**Blocks:** PE-PRD-08
**Estimated effort:** 4–5 days

---

## 1. Context

The Analysis tab is Performance's "What Happened" surface. It answers three questions at a glance:

1. **Where did the funnel expand?** A 4-stage funnel viz (Problem Awareness → Brand Awareness → Consideration → Conversion) showing each stage's Effectiveness-KPI value + delta vs. the selected comparison mode.
2. **How did each stage trend?** A 53-week weekly trendline per stage, rendered via the same `LineChart` widget Dashboards ships (DB-PRD-03), with a marker on the current in-progress (`is_partial=true`) week.
3. **Where did the money go?** Cost-rollup chips grouped by one dimension at a time (channel / campaign / platform / owner), plus a related-metrics grid and an External Factors panel that reads the project-tasks Calendar directly.

All analytical computation lives in SAR-E. This PRD is a frontend consumer of the `/performance/{account_id}/analysis` composite bundle (and, for External Factors, a direct read against `/plans/{account_id}?category=...`). The bundle short-circuits to an empty payload if SAR-E is disabled, but this tab is never rendered pre-wizard — `ForecastingEnabledGate` hides it from the nav. No per-tab empty-state-CTA surface is required.

The tab renders skeleton-first and fills in as bundle fields arrive. Comparison-mode changes trigger a re-fetch, not a re-layout. Cost-dimension switches trigger a re-fetch of the cost rollup alone (the bundle is re-parameterized via the `dimension` query arg). Related metrics are lazy-loaded on stage-expand — they are *not* in the initial bundle.

## 2. Scope

### In scope

- `AnalysisTab` component replacing PE-PRD-01's `<AnalysisTabPlaceholder />`
- Four-stage funnel visualization: CSS `clip-path` polygons, per-stage tile showing KPI name + current-period value + delta vs. comparison mode; click-to-expand a stage reveals the trendline + related metrics for that stage
- Comparison-mode toggle: three-way control (`wow` / `yoy` / `vs_target`); selection is a tab-local state (does not mutate `PerformanceDateRangeContext.comparisonMode` — see §9 open question 1)
- 53-week weekly trendline per funnel stage, rendered via DB-PRD-03's `LineChart` widget; bundle returns `weekly_points: TrendlinePoint[]` per stage; widget consumes directly
- `is_partial` marker: the most recent week's `TrendlinePoint` carries `is_partial=true` when ingestion is mid-week; widget renders a dashed line segment + tooltip callout
- "Insufficient history" badge: when `weekly_points.length < 53`, the trendline shrinks to available weeks and surfaces a badge ("12 / 53 weeks available. Baseline quality improves as history accumulates.")
- Cost-rollup chip rail: dimension picker (single-select: channel | campaign | platform | owner); switching triggers a scoped re-fetch of `/analysis?dimension=<one>`; chips show top-N (N=10 v1) rollup buckets with value + share-of-period-cost
- Related-metrics grid: lazy-loaded on stage expand via `GET /api/v1/sar-e/{account_id}/analytics/related-metrics?objective=<stage>`; shows non-mapped KPIs for the selected stage + period + comparison mode
- External Factors panel: reads project-tasks Calendar directly via `GET /api/v1/plans/{account_id}?category=holiday&category=promotion&category=event&from=<period.start>&to=<period.end>`; renders chronological list grouped by category. Does NOT go through SAR-E.
- Skeleton-first render states: funnel skeleton, trendline skeleton, cost-chip skeleton, External Factors skeleton — each replaced independently as its data arrives
- Loading / empty / error states:
  - Loading: skeletons as above
  - Empty (account backfilled but no tasks in period): funnel renders KPI values (possibly zero), cost chips render "No cost recorded in this period", External Factors renders "No holidays, promotions, or events scheduled"
  - Error: each section surfaces an inline retry affordance scoped to that section's fetch (a failed cost-rollup fetch does not fail the funnel render)
- Unit tests per section + hook; Playwright E2E for the period-change + comparison-mode + stage-expand + cost-dimension-switch flow

### Out of scope

- Funnel stage-mapping edits (lives in the Configuration tab — PE-PRD-04)
- Target CRUD (PE-PRD-06)
- Exogenous-event editing (Calendar page owns this — PR-PRD-07)
- Dashboards-style canvas placement / pinning — trendlines are tab-native, not canvas widgets
- Cross-stage drill-down or linked filters between sections (every section is independent within the tab)
- Combined-dimension cost rollups (explicit non-goal per implementation-plan §10 resolved question 3 — single dimension at a time)
- Monthly aggregation, daily drill-down, or custom time-aggregation (SAR-E is weekly-only)
- Automatic refresh during a run (static snapshot; refetch on period / comparison / dimension change only)

## 3. Dependencies

- **PE-PRD-01:** publishes `ForecastingEnabledGate`, `PerformanceDateRangeContext`, `FunnelObjective`, `EffectivenessKPIId`, `ComparisonMode`, `CostDimension` branded types, and the `performanceApi.ts` service-layer module this PRD extends.
- **SE-PRD-06 (Analytical query layer):** publishes `/analytics/funnel`, `/analytics/trendline/{objective}` (default 53-week window), `/analytics/cost-rollup` (single `dimension` query param per resolved question 3 in the implementation plan), `/analytics/related-metrics`. The Performance-side composite bundle at `/api/v1/performance/{account_id}/analysis` wraps these into a single page-load response.
- **SE-PRD-01:** `/config/status` — the gate above this tab reads it; this PRD assumes `enabled=true` and does not implement pre-wizard paths.
- **DB-PRD-03 (Dashboard Details & Canvas):** publishes the `LineChart` widget at `frontend/src/components/dashboards/widgets/VisualizationWidget.tsx` (with `view_override="line"`) or — more likely per the implementation plan — a dedicated line-chart renderer extracted during DB-PRD-03 for reuse. The contract assumed here: the widget accepts `{data: TrendlinePoint[], xKey, yKey, partialFlagKey, width, height}`. Confirm final export surface with Dashboards owner at PE-PRD-02 kickoff; if DB-PRD-03 ships a Vega-Lite-only renderer, this PRD wraps it with a small adapter (still no new runtime library).
- **PR-PRD-07 (Calendar Activities):** publishes `GET /api/v1/plans/{account_id}` with `category` filter accepting `holiday | promotion | event` (list filter per §5 of PR-PRD-07). External Factors reads directly — no SAR-E proxy.
- **Existing files to study:**
  - `frontend/src/pages/Performance/PerformancePage.tsx` (PE-PRD-01) — host component
  - `frontend/src/components/performance/ForecastingEnabledGate.tsx` (PE-PRD-01)
  - `frontend/src/contexts/PerformanceDateRangeContext.tsx` (PE-PRD-01)
  - `frontend/src/types/performance.ts` (PE-PRD-01) — branded types
  - `frontend/src/services/performanceApi.ts` (PE-PRD-01) — extend with `getAnalysisBundle`
  - `frontend/src/components/dashboards/widgets/VisualizationWidget.tsx` (DB-PRD-03) — reuse for trendline
  - `docs/figma-export/src/app/pages/performance/` — reference UX (note: AnalysisSection.tsx and FunnelSection.tsx are not present in the current export; rebuild from Figma designs at kickoff — see §9 Open question 2)

## 4. Data contract

### 4.1 Composite bundle (consumed)

```typescript
// frontend/src/types/performance.ts — additions
export interface TrendlinePoint {
  week_start: string;      // ISO date (YYYY-MM-DD), Monday of the ISO week
  value: number;
  ci_low: number | null;   // confidence interval low (baseline forecasts only; null for historicals)
  ci_high: number | null;
  is_partial: boolean;     // true for the current in-progress week
}

export interface FunnelStageSnapshot {
  objective: FunnelObjective;
  kpi_id: EffectivenessKPIId;
  kpi_display_name: string;
  current_value: number;
  comparison_value: number | null;    // null if comparison not computable (e.g., yoy on <53 weeks of history)
  comparison_mode: ComparisonMode;    // echoes the request param
  delta_absolute: number | null;
  delta_pct: number | null;
  unit: 'count' | 'currency' | 'percent' | 'duration_seconds';
}

export interface FunnelSnapshot {
  period: DateRange;
  stages: FunnelStageSnapshot[];      // exactly 4 entries, ordered by FunnelObjective
}

export interface TrendlineSeries {
  objective: FunnelObjective;
  kpi_id: EffectivenessKPIId;
  weekly_points: TrendlinePoint[];    // up to 53 points; fewer if history is insufficient
  window_start: string;               // ISO date of earliest point
  window_end: string;                 // ISO date of latest point
}

export interface CostRollupBucket {
  dimension_value: string;            // e.g., "google-ads" for channel, "Spring Sale" for campaign
  total_cost: number;
  share_of_period: number;            // 0..1
  objective: FunnelObjective | null;  // null when a task's attribution is ambiguous
}

export interface CostRollup {
  dimension: CostDimension;           // echoes the request param
  buckets: CostRollupBucket[];        // top N, sorted by total_cost DESC
  other_total: number;                // rollup of buckets beyond top N
}

export interface ExogenousEventProjection {
  activity_id: string;
  category: 'holiday' | 'promotion' | 'event';
  title: string;
  start: string;                      // ISO date
  end: string | null;                 // ISO date; null for single-day
  // Category-specific details read directly from PR-PRD-07's PlanTask shape
  promotion_type?: string;
  holiday_type?: string;
  region?: string | null;
}

export interface RelatedMetric {
  kpi_id: EffectivenessKPIId;
  kpi_display_name: string;
  current_value: number;
  comparison_value: number | null;
  delta_pct: number | null;
  unit: 'count' | 'currency' | 'percent' | 'duration_seconds';
}

// Bundle response shape (mirrors implementation-plan §3.2)
export interface AnalysisBundle {
  forecasting_enabled: boolean;
  funnel: FunnelSnapshot | null;
  trendlines: Record<FunnelObjective, TrendlineSeries> | null;
  cost_rollups: CostRollup | null;                        // single dimension at a time
  external_factors: ExogenousEventProjection[] | null;
  related_metrics: RelatedMetric[] | null;                // empty array in initial bundle; populated on stage-expand
  period: DateRange;
  comparison: DateRange;
}
```

**TBD — confirm with SAR-E team at PE-PRD-02 kickoff:**
- Exact field names on `TrendlinePoint` (`is_partial` / `partial` / `incomplete_week` — SAR-E's `KPIDataPoint` uses `is_partial` per SE-PRD-02, so this PRD assumes the same key flows through to the bundle)
- Whether `comparison_value` fields may be negative (for delta-capable metrics) or strictly non-negative (count KPIs). Display logic handles both safely.
- Whether `external_factors` is truly populated by the bundle or the Performance API expects the frontend to fetch it directly (the implementation plan says "reads project-tasks Calendar directly"; this PRD ships the direct path). If the composite bundle duplicates the read, the direct fetch is harmless extra redundancy but is removed in PE-PRD-08 polish.

### 4.2 Widget-consumption types

The trendline per stage is rendered by DB-PRD-03's line-chart widget. The adapter in this PRD shapes `TrendlineSeries` into the widget's props:

```typescript
// frontend/src/components/performance/AnalysisTrendline.tsx
interface AnalysisTrendlineProps {
  series: TrendlineSeries;
  comparisonSeries?: TrendlineSeries;  // for wow / yoy / vs_target overlay
  unit: FunnelStageSnapshot['unit'];
  height: number;                      // from layout; typically 240
}

// Internally:
//   data        = series.weekly_points
//   xKey        = 'week_start'
//   yKey        = 'value'
//   partialKey  = 'is_partial'   // widget renders dashed segment for the last point if true
//   overlayData = comparisonSeries?.weekly_points
```

If DB-PRD-03's final exported widget does not expose `partialKey`, this PRD splits the series into two adjacent series (complete weeks + tail partial week as a separate series with dashed `view_override`). Either path produces the same visual.

### 4.3 External Factors query

```typescript
// frontend/src/services/performanceApi.ts — additions
export async function getExternalFactors(
  accountId: string,
  period: DateRange,
): Promise<ExogenousEventProjection[]> {
  // Direct call to project-tasks — not routed through SAR-E
  const params = new URLSearchParams();
  (['holiday', 'promotion', 'event'] as const).forEach(c => params.append('category', c));
  params.set('from', period.start);
  params.set('to', period.end);
  const { data } = await axios.get(`/api/v1/plans/${accountId}?${params.toString()}`);
  // Transform PlanTask shape to ExogenousEventProjection
  return data.items.map(mapPlanTaskToExogenousEvent);
}
```

The `mapPlanTaskToExogenousEvent` helper reads PR-PRD-07's `PlanTask` category-discriminated fields (`promotion_type`, `holiday_type`, `region`) and projects into the display shape.

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `frontend/src/pages/Performance/AnalysisTab.tsx` — tab container; replaces PE-PRD-01's placeholder |
| Create | `frontend/src/components/performance/FunnelVisualization.tsx` — 4-stage clip-path polygons + stage tiles |
| Create | `frontend/src/components/performance/FunnelStageTile.tsx` — single stage's KPI value + delta + expand toggle |
| Create | `frontend/src/components/performance/ComparisonModeToggle.tsx` — wow / yoy / vs_target three-way control |
| Create | `frontend/src/components/performance/AnalysisTrendline.tsx` — adapter around DB-PRD-03's LineChart widget |
| Create | `frontend/src/components/performance/InsufficientHistoryBadge.tsx` — `<53 weeks` indicator |
| Create | `frontend/src/components/performance/CostRollupChipRail.tsx` — dimension picker + chip row |
| Create | `frontend/src/components/performance/RelatedMetricsGrid.tsx` — lazy-loaded per stage |
| Create | `frontend/src/components/performance/ExternalFactorsPanel.tsx` — reads PR-PRD-07 directly |
| Create | `frontend/src/hooks/useAnalysisBundle.ts` — TanStack Query hook; key `['performance', 'analysis', accountId, period, comparisonMode, dimension]` |
| Create | `frontend/src/hooks/useRelatedMetrics.ts` — lazy hook; enabled only when a stage is expanded |
| Create | `frontend/src/hooks/useExternalFactors.ts` — direct Calendar-read hook |
| Modify | `frontend/src/services/performanceApi.ts` — add `getAnalysisBundle(accountId, {period, comparisonMode, dimension})`, `getRelatedMetrics(accountId, objective, period, comparisonMode)`, `getExternalFactors(accountId, period)` |
| Modify | `frontend/src/pages/Performance/PerformancePage.tsx` (PE-PRD-01) — swap `<AnalysisTabPlaceholder />` for `<AnalysisTab />` |
| Delete | `frontend/src/pages/Performance/AnalysisTabPlaceholder.tsx` (PE-PRD-01 scaffolding) |
| Create | `frontend/src/components/performance/__tests__/FunnelVisualization.test.tsx` |
| Create | `frontend/src/components/performance/__tests__/FunnelStageTile.test.tsx` |
| Create | `frontend/src/components/performance/__tests__/AnalysisTrendline.test.tsx` |
| Create | `frontend/src/components/performance/__tests__/CostRollupChipRail.test.tsx` |
| Create | `frontend/src/components/performance/__tests__/ExternalFactorsPanel.test.tsx` |
| Create | `frontend/src/components/performance/__tests__/InsufficientHistoryBadge.test.tsx` |
| Create | `frontend/src/hooks/__tests__/useAnalysisBundle.test.ts` |
| Create | `frontend/src/pages/Performance/__tests__/AnalysisTab.test.tsx` |
| Create | `frontend/e2e/performance-analysis.spec.ts` — period / comparison / stage-expand / cost-dimension-switch |

### Render flow

```
<AnalysisTab />
  ├─ <ComparisonModeToggle />                          (tab-local state)
  ├─ useAnalysisBundle(accountId, period, comparisonMode, dimension='channel')
  │
  ├─ {isLoading} <AnalysisSkeleton />
  ├─ {error}     <AnalysisErrorRetry scope="bundle" />
  └─ {data} →
       ├─ <FunnelVisualization stages={data.funnel.stages} />
       │     ├─ <FunnelStageTile ... /> × 4
       │     └─ on expand(stage) →
       │         ├─ <AnalysisTrendline series={data.trendlines[stage]} />
       │         │     └─ <InsufficientHistoryBadge />  (if weekly_points.length < 53)
       │         └─ <RelatedMetricsGrid /> (lazy via useRelatedMetrics)
       │
       ├─ <CostRollupChipRail rollup={data.cost_rollups} onDimensionChange={…} />
       │
       └─ <ExternalFactorsPanel /> (direct fetch via useExternalFactors)
```

### Fetch-scope model

| Trigger | Refetches |
|---|---|
| Tab mount | bundle + external factors (parallel) |
| Period change (via `PerformanceDateRangeContext`) | bundle + external factors |
| Comparison-mode change (tab-local) | bundle only |
| Dimension change (tab-local) | bundle only — server re-computes cost rollup for new dimension |
| Stage expand (first time) | related metrics (scoped to stage + period + comparison) |
| Stage expand (re-expand after comparison change) | related metrics (cache miss on new comparison key) |
| Stage collapse | none — related-metrics cache preserved for this stage |

Bundle query key: `['performance', 'analysis', accountId, period, comparisonMode, dimension]`. Related-metrics key: `['performance', 'related-metrics', accountId, objective, period, comparisonMode]`. External-factors key: `['performance', 'external-factors', accountId, period]`.

Stale time: 5 minutes for bundle + related metrics (matches SE-PRD-06 server-side cache); 1 minute for external factors (edits on Calendar should surface promptly).

### Rendering invariants

- **`is_partial` marker.** The most recent `TrendlinePoint` with `is_partial=true` renders as a dashed segment; tooltip says "Week in progress — value will update as ingestion completes."
- **`vs_target` mode without saved targets.** If `comparison_value` is `null` across all stages (no targets saved for this period), the toggle surfaces a one-line inline message ("No targets saved for this period. [Open Simulations to create them]") — the link navigates to `/performance/simulations` but does not pre-fill. No error is shown; the funnel still renders current values.
- **`yoy` on <53 weeks of history.** `comparison_value` is `null` per the SAR-E contract; the delta indicator renders `—` and the tile tooltip explains "Year-over-year requires 53 weeks of history."
- **Cost rollup with zero buckets.** Chip rail shows "No cost recorded in this period" with a muted style. Dimension picker remains interactive.
- **External Factors with zero entries.** Panel shows "No holidays, promotions, or events scheduled in this period" + a link to `/calendar`.

## 6. API contract

### 6.1 Bundle endpoint (owned by Performance BFF, consumed here)

```
GET /api/v1/performance/{account_id}/analysis
    ?period=<start>,<end>          # ISO week-aligned
    &comparison_mode=<mode>        # wow | yoy | vs_target
    &dimension=<cost_dimension>    # channel | campaign | platform | owner
```

Response: `AnalysisBundle` per §4.1.

Rules:
- `period.start` must be a Monday (ISO week start); `period.end` must be the Sunday of a complete or current ISO week. 422 on malformed period.
- `comparison_mode=yoy` requires ≥53 weeks of history on at least one KPI to produce a non-null `comparison_value`; fewer weeks returns the funnel with `comparison_value=null` per stage and a top-level hint field (TBD with SAR-E — `hint` field shape not spec'd; likely `{"code": "insufficient_history", "details": {"weeks_available": N}}`).
- `dimension` is single-valued per implementation-plan resolved question 3. Multi-dimension not accepted; request returns 422.
- `forecasting_enabled=false` short-circuits to `{forecasting_enabled: false, ...all nulls}` per implementation-plan §3.2. Frontend should not reach this endpoint when the gate renders Configuration-only, but the guard is defensive.
- Bundle errors per section: if `trendlines` fails to compute for one stage, that stage's key is absent from the `trendlines` map but other stages render. Frontend surfaces section-scoped error badges.

### 6.2 Related-metrics endpoint (SE-PRD-06 direct)

```
GET /api/v1/sar-e/{account_id}/analytics/related-metrics
    ?objective=<FunnelObjective>
    &period=<start>,<end>
    &comparison_mode=<mode>
```

Response: `{ related_metrics: RelatedMetric[] }`.

Called lazily on stage expand. Not part of the initial bundle (per implementation-plan §6 PE-PRD-02 scope).

### 6.3 External Factors endpoint (PR-PRD-07 direct)

```
GET /api/v1/plans/{account_id}
    ?category=holiday&category=promotion&category=event
    &from=<period.start>
    &to=<period.end>
```

Response: `{ items: PlanTask[], cursor: ... }` per PR-PRD-07 §5 list endpoint contract.

Mapped client-side to `ExogenousEventProjection[]` via `mapPlanTaskToExogenousEvent`.

## 7. Acceptance criteria

1. `/performance/analysis` on an enabled account renders four funnel-stage tiles in the order Problem Awareness → Brand Awareness → Consideration → Conversion; each tile shows the mapped KPI's display name, current value, and delta vs. the selected comparison mode.
2. Changing the comparison mode from `wow` to `yoy` re-fetches the bundle and updates each tile's delta; the trendline overlay series updates if a stage is expanded.
3. Changing the comparison mode to `vs_target` on an account with no saved targets for the period renders `—` in every delta; a "No targets saved for this period" inline message appears with a link to Simulations.
4. Clicking a funnel stage expands it: the 53-week trendline renders via DB-PRD-03's line-chart widget; related metrics lazy-load on first expand.
5. A stage with fewer than 53 weeks of history renders the available weeks + an `<InsufficientHistoryBadge />` reading "N / 53 weeks available. Baseline quality improves as history accumulates."
6. The most recent week's data point renders with a dashed segment and the tooltip "Week in progress — value will update as ingestion completes" when `is_partial=true`.
7. The cost-rollup chip rail defaults to `dimension='channel'`; switching to `campaign` triggers a scoped re-fetch and updates the chips without re-rendering the funnel.
8. Cost rollup with zero buckets renders "No cost recorded in this period"; the dimension picker remains interactive.
9. The External Factors panel calls `GET /api/v1/plans/{account_id}?category=holiday&category=promotion&category=event&from=...&to=...` directly (not through SAR-E) and renders returned items grouped by category, chronologically ordered within each group.
10. External Factors with zero entries renders "No holidays, promotions, or events scheduled in this period" + a link to `/calendar`.
11. Skeleton-first render: on tab mount, each section shows its own skeleton independently; a slow funnel fetch does not delay the cost-rollup section from rendering.
12. Section-scoped error: a failed cost-rollup fetch renders a retry affordance within the chip rail without tearing down the funnel or trendlines.
13. Period change via `PerformanceDateRangeContext` re-fetches both the bundle and External Factors; tab-local state (expanded stage, current dimension, current comparison mode) is preserved.
14. Leaving the tab and returning within 5 minutes serves the cached bundle (no refetch); after 5 minutes the bundle is refetched on tab focus.
15. Deep-link with query state is not required — comparison mode and dimension are tab-local (not URL-backed) per PE-PRD-01's scope.
16. `npm run build`, `npm run typecheck`, `npm run format.fix` all clean.
17. `performance-analysis.spec.ts` Playwright test passes: backfilled account → funnel renders → expand Consideration → trendline appears → switch `dimension` to `campaign` → chips change → switch `comparisonMode` to `yoy` → deltas update.

## 8. Test plan

**Unit tests** (`FunnelVisualization.test.tsx`):
- Four stages render in prescribed order regardless of bundle-field order
- Stage tile shows KPI display name + current value + delta (wow / yoy / vs_target)
- Delta styling (up-is-good KPIs: green for positive, red for negative; neutral KPIs: monochrome)
- `comparison_value === null` renders `—` in the delta slot and omits the up/down arrow
- Click on a stage toggles its expanded state

**Unit tests** (`FunnelStageTile.test.tsx`):
- Renders display name, unit-formatted value (currency, count, percent, duration), delta badge
- Absent `comparison_value` renders fallback `—`
- Tooltip on `—` delta in `yoy` mode reads "Year-over-year requires 53 weeks of history"
- Tooltip on `—` delta in `vs_target` mode reads "No target saved for this week"

**Unit tests** (`AnalysisTrendline.test.tsx`):
- Renders via the DB-PRD-03 line-chart widget (mock the widget; assert prop shape)
- Transforms `TrendlineSeries.weekly_points` into the widget's `{data, xKey, yKey}` shape
- `is_partial=true` on the last point produces a dashed segment (either via widget prop or split-series fallback)
- Comparison series renders as an overlay when provided
- Empty `weekly_points` renders "No data available for this period" placeholder

**Unit tests** (`InsufficientHistoryBadge.test.tsx`):
- Renders "N / 53 weeks available" with correct N
- Hidden when `weeks_available >= 53`

**Unit tests** (`CostRollupChipRail.test.tsx`):
- Dimension picker defaults to `channel`; emits `onDimensionChange('campaign')` on selection
- Renders top-N chips sorted by `total_cost DESC`; `other_total > 0` renders an "Other" chip
- Zero buckets renders the empty-state message
- Dimension button group is a single-select (not multi) — switching dimensions always calls back with one value

**Unit tests** (`ExternalFactorsPanel.test.tsx`):
- Calls `useExternalFactors(accountId, period)` with correct args
- Groups items by category: Holidays, Promotions, Events (fixed order)
- Sorts within group by `start` ASC
- Zero items renders empty-state with link to `/calendar`
- Mocks `getExternalFactors` to return a fixture spanning all three categories; assert DOM grouping

**Unit tests** (`useAnalysisBundle.test.ts`):
- Query key includes `accountId`, `period.start`, `period.end`, `comparisonMode`, `dimension`
- Two calls with identical args deduplicate to one network call
- Changing `dimension` with other args constant re-fetches
- 5-minute stale time
- Surfaces `forecasting_enabled=false` payload without treating it as error

**Unit tests** (`AnalysisTab.test.tsx`):
- Renders skeletons on initial mount
- Bundle success + external-factors success → all sections render in final state
- Bundle success + external-factors failure → other sections render; External Factors surfaces retry
- Bundle failure → section-scoped error banners; no white-screen
- Comparison-mode toggle updates UI state and triggers exactly one bundle refetch

**Playwright integration** (`performance-analysis.spec.ts`):
- Login as user with a backfilled account (≥53 weeks of history seeded) → navigate to `/performance/analysis` → funnel renders four stages
- Click Consideration → trendline appears within 2s (per implementation-plan §11 success criterion)
- Switch comparison mode to `yoy` → deltas re-render; trendline overlay appears
- Switch cost dimension from `channel` to `campaign` → chip rail updates; funnel unchanged
- Scroll to External Factors → at least one holiday / promotion / event fixture renders
- Change period via `PerformanceDateRangeContext` control → bundle refetches; External Factors refetches
- Log in as user with a 20-week-old account (<53 weeks) → trendline shows 20 points + "20 / 53 weeks available" badge

## 9. Risks & open questions

| Risk / question | Mitigation |
|---|---|
| DB-PRD-03's exported line-chart widget does not expose a `partialKey` / dashed-segment prop | Fallback: split the series into two adjacent series (complete weeks + 1-point partial tail rendered with `view_override="line"` + dashed styling via Vega `mark.strokeDash`). Confirmed at kickoff with Dashboards owner. |
| AnalysisSection / FunnelSection Figma files not present in current figma-export | Rebuild from Figma designs at kickoff; implementation plan §9 Risk row 1 confirms this is expected. The clip-path math for the 4-stage funnel is a straightforward polygon formula; no reference code needed. |
| 53-week trendline slow on accounts with many metrics | Per implementation-plan §9 row 3: bundle returns only the mapped Effectiveness KPI per stage (4 series). Related metrics are separate lazy fetches. |
| Stale Funnel Mapping skews trendlines mid-view | Per implementation-plan §9 row 4: Configuration tab mapping edits invalidate `['performance', 'analysis', ...]` cache keys via `queryClient.invalidateQueries`. This PRD registers the query keys; PE-PRD-04 wires the invalidation. |
| External Factors direct fetch hits a different auth scope than SAR-E | PR-PRD-07's `GET /plans` endpoint is account-scoped same as SAR-E; both use the existing auth middleware. Validated in integration test. |
| `vs_target` mode without saved targets shows confusing zeros | Resolved: `comparison_value=null` renders `—` (not 0); inline message directs users to Simulations. |
| Bundle field-name mismatches (TBD in §4.1) | TBD rows in §4.1 are explicit; PE-PRD-02 kickoff resolves against SAR-E's shipped OpenAPI spec. Adapter layer in `performanceApi.ts` absorbs any field-name drift. |
| Playwright test for `<53 weeks` fixture requires seeded history | Test uses SAR-E's test fixtures (`tests/fixtures/sar-e/20-week-account.json` — TBD with SAR-E owner); if fixtures aren't ready, the test is marked `test.skip` with a TODO and PE-PRD-08 picks it up. |
| Combined-dimension cost rollup creeps back into scope | Explicit non-goal per §2 and implementation-plan resolved question 3. Code review gate in PE-PRD-08. |

Cross-references to implementation-plan risks that apply to this phase: Risks 3 (53-week trendline perf), 4 (stale funnel mapping), 7 (pre-wizard tab proliferation — resolved by gate; this PRD confirms the gate behavior).

### Open questions

1. **Should comparison mode be promoted to `PerformanceDateRangeContext`?** Current PRD keeps it tab-local because Simulations and Targets have different "comparison" semantics (Simulations compares baseline to target; Targets compares actuals to target). If a cross-tab story emerges where Analysis's `wow` / `yoy` should follow the user into Simulations, promote the mode to the shared context. Decide at PE-PRD-03 kickoff.
2. **Rebuild Figma AnalysisSection.tsx from scratch or use a cached export?** The file is referenced in the implementation plan but absent from `docs/figma-export/src/`. Confirm with design owner at PE-PRD-02 kickoff whether a newer export is coming or the component is to be authored fresh.
3. **Should the dimension picker persist to `sessionStorage`?** Current PRD: tab-local state, resets on tab switch. PE-PRD-08 UX audit revisits.
4. **Does the bundle response include a `hint` field for insufficient-history signals?** TBD with SAR-E per §4.1; current UI gracefully handles `null` comparison values regardless.

## 10. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md) §6 PE-PRD-02
- Sibling (upstream): [PE-PRD-01](./PE-PRD-01-page-shell-and-routing.md) — page shell + branded types + context
- Upstream: [SE-PRD-06](../../sar-e/implementation-plan.md) §6 — analytical query layer
- Upstream: [SE-PRD-01](../../sar-e/implementation-plan.md) §6 — `/config/status` gate
- Upstream: [DB-PRD-03](../../dashboards/projects/DB-PRD-03-dashboard-details-and-canvas.md) — line-chart widget reused here
- Upstream: [PR-PRD-07](../../project-tasks/projects/PR-PRD-07-calendar-activities.md) — Calendar list endpoint for External Factors
- Figma reference: `docs/figma-export/src/app/pages/performance/` (AnalysisSection.tsx + FunnelSection.tsx absent — rebuild at kickoff)
- CLAUDE.md rules in scope: C-1, C-3, C-5, C-6, C-8, C-9; T-2, T-4, T-5, T-6, T-8; G-2, G-3
