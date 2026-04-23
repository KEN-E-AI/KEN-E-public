# SE-PRD-06 — Analytical Query Layer

**Status:** Blocked — resumes once SE-PRD-01, SE-PRD-02, SE-PRD-03, PR-PRD-07, and PR-PRD-08 ship
**Owner team:** SAR-E component team (backend)
**Blocked by:** SE-PRD-01 (`FunnelStageMapping` + `FunnelMappingHistory` drive objective→KPI resolution; `Threshold` values surface on the funnel snapshot; `ChannelCoverage` feeds the cost-rollup inclusion semantics); SE-PRD-02 (`KPIDataPoint` weekly rows are the reading surface for trendline + funnel snapshot); SE-PRD-03 (baselines are joined into the funnel snapshot's comparison column); PR-PRD-07 (`PlanTask.cost / channel / platform / owner_email / campaign_id`; Calendar category filter for the External Factors surface Performance consumes directly); PR-PRD-08 (`Campaign.objective` for the cost-rollup-by-objective dimension)
**Blocks:** SE-PRD-07 (E2E test exercises every endpoint here); PE-PRD-02 (Analysis tab renders every endpoint here); PE-PRD-07 (Diagnostics tab reads trendline with staleness annotations)
**Estimated effort:** 4 days

---

## 1. Context

SAR-E's analytical query layer is what the Analysis tab reads. It takes raw ingredients — weekly `KPIDataPoint` rows, `FunnelStageMapping` (resolved per-week via history), `Baseline` snapshots, `PlanTask` costs tagged with `campaign_id` + `channel` + `platform` + `owner_email`, and `Campaign.objective` — and composes four cached query endpoints: `/analytics/funnel`, `/analytics/trendline/{objective}`, `/analytics/cost-rollup`, `/analytics/related-metrics`.

Three facts shape the design:

1. **Funnel-mapping resolution is per-week.** Asking "what was Consideration in week 2026-W12?" requires reading the `FunnelStageMapping` version that was active during that week, then looking up the corresponding KPI id. `FunnelMappingHistory` (SE-PRD-01) is the source; this PRD's query helpers walk it. A mapping change between two edit points never corrupts the trendline — the pre-change weeks render via the pre-change KPI, the post-change weeks via the post-change KPI. The UI may draw a vertical marker at the transition (PE-PRD-02 §5 decides whether to); the data layer guarantees correctness.
2. **Under-covered channels appear in cost rollup; they do not appear in VAR training.** Implementation-plan §3.5 split semantics. The cost-rollup query reads `PlanTask.cost` grouped by `{channel | campaign | platform | owner} × objective` without consulting `ChannelCoverage`; users always see money spent. The training-path exclusion is SE-PRD-03's responsibility. This PRD's integration test locks the asymmetry with a single assertion pair.
3. **Caching is in-process + short-TTL.** 5 minutes for funnel snapshot + trendline; cost-rollup recomputed on demand (cost data mutates with every task edit). No Redis; TanStack Query on the frontend (PE-PRD-02) absorbs the remaining burst. Cost-rollup can get expensive on busy accounts (500 tasks × 4 dimensions × 12 weeks = 24k cells); the composite Firestore indexes on `(campaign_id, week)` and `(channel, week)` drive it down to <500ms p95.

Also in scope, though small: `ChannelCoverage` population — the roll-up from SE-PRD-02's `sar_e.ingest.channel_signal` log stream into the `ChannelCoverage` matrix. SE-PRD-02 emits the signal; this PRD writes a small per-ingest handler that updates the matrix (see §5.5). Handles implementation-plan §10 open question "Channel Coverage population — who writes?".

## 2. Scope

### In scope

- **Analytical query service** `api/src/kene_api/services/sar_e_analytics_service.py`:
  - `get_funnel_snapshot(account_id, period: DateRange, comparison: Literal["wow","yoy","vs_target"]) -> FunnelSnapshotResponse`
  - `get_trendline(account_id, objective: FunnelObjective, window_weeks: int = 53) -> TrendlineResponse`
  - `get_cost_rollup(account_id, period: DateRange, dimensions: list[CostDimension]) -> CostRollupResponse`
  - `get_related_metrics(account_id, period: DateRange, comparison: Literal["wow","yoy"]) -> RelatedMetricsResponse`
- **Historical mapping resolver** `api/src/kene_api/services/sar_e_mapping_resolver.py`:
  - `resolve_mapping_at_week(account_id, week_start) -> dict[FunnelObjective, str]` — walks `FunnelMappingHistory` to return the mapping active for that week; cached per-account+week via 5-min LRU
  - Bulk helper `resolve_mappings_for_range(account_id, period) -> dict[date, dict[FunnelObjective, str]]` — computes once per distinct version-boundary within the range
- **Analytical query endpoints**:
  - `GET /api/v1/sar-e/{account_id}/analytics/funnel?start=YYYY-MM-DD&end=YYYY-MM-DD&comparison=wow|yoy|vs_target` — 4-stage funnel snapshot with comparison column
  - `GET /api/v1/sar-e/{account_id}/analytics/trendline/{objective}?window_weeks=53` — weekly KPI trendline for a funnel stage, default 53 weeks, max 156
  - `GET /api/v1/sar-e/{account_id}/analytics/cost-rollup?start=&end=&dimensions=channel,campaign` — cost aggregated by `dimensions[]` × objective; dimensions ∈ `{channel, campaign, platform, owner}`; 1–4 dimensions per call
  - `GET /api/v1/sar-e/{account_id}/analytics/related-metrics?start=&end=&comparison=wow|yoy` — non-mapped KPI values + deltas for the period
- **Cache layer** `api/src/kene_api/utils/analytics_cache.py`:
  - In-process LRU with 5-min TTL, keyed by `(account_id, endpoint, serialized_params)`
  - Invalidated on: `FunnelStageMapping PUT` (SE-PRD-01); new `Baseline` writes (SE-PRD-03 retrain); `EffectivenessKPI` CRUD (SE-PRD-01). Invalidation wildcard: `(account_id, *)`.
  - Cache-Control response header: `max-age=300, private` for funnel + trendline; `max-age=0, must-revalidate` for cost-rollup and related-metrics
- **`ChannelCoverage` population handler** `api/src/kene_api/services/sar_e_channel_coverage_builder.py`:
  - Consumes `sar_e.ingest.channel_signal` structured logs (SE-PRD-02 §5.4) — v1: this is implemented as an explicit service-layer call from `sar_e_ingestion_service.write_weekly_data_point(...)` into `channel_coverage_builder.record_signal(...)` rather than a log-consumer pipeline (simpler, in-process)
  - Updates `accounts/{account_id}/channel_coverage.matrix` incrementally: for each `(channel, week_start)` pair seen with non-zero rows, upserts `{channel, week_start, has_data: True}`; matrix compacted to the last 52 weeks on each write
  - Flags a channel as "under-covered" when its per-week `has_data` rate over the last 26 weeks is below 60% (configurable via `SarEConfig.channel_coverage_threshold`, default 0.6). The "flag" here is informational — SE-PRD-03 reads the raw matrix and applies its own threshold; the `under_covered_channels` field on the coverage response is a convenience projection.
- **Tests**:
  - Unit: `resolve_mapping_at_week` with 3-version history
  - Unit: cost-rollup aggregation with mixed dimensions
  - Unit: `ChannelCoverage` roll-up (signal → matrix → under-covered projection)
  - Integration: funnel snapshot with `comparison=wow` and `vs_target`
  - Integration: trendline with 53 weeks returns 53 points (one per ISO week)
  - Integration: cost-rollup across 500 tasks → p95 <500ms
  - Integration: under-covered channel appears in cost-rollup (asymmetry test)
  - Integration: funnel-mapping change mid-window — trendline seamless; funnel snapshot uses the latest mapping for the current-period column and the historical mapping for the comparison column (or, for `vs_target`, against targets keyed on current mapping)
  - Cache invalidation: PUT funnel mapping → next funnel snapshot call re-queries

### Out of scope (handled by other PRDs)

- VAR / baseline computation (SE-PRD-03)
- Target derivation + CRUD (SE-PRD-05) — trendline's `vs_target` comparison reads targets but doesn't mutate them
- Performance API bundle endpoints (`/performance/{account_id}/analysis`) — PE-PRD-02 composes the SAR-E analytical reads into the Performance bundle
- UI rendering (PE-PRD-02)
- External Factors panel on the Analysis tab — PE-PRD-02 reads project-tasks Calendar directly; SAR-E does not proxy that read
- CLV calculations — descoped per implementation-plan §8 / PE-PRD-04 §2
- Daily-granularity overlays — future enhancement

## 3. Dependencies

- **SE-PRD-01:** `FunnelStageMapping`, `FunnelMappingHistory`, `Threshold`, `ChannelCoverage` models. This PRD adds the `get_current_mapping_version` helper to SE-PRD-01's service (or duplicates the read into `sar_e_mapping_resolver`) — confirm at kickoff.
- **SE-PRD-02:** `KPIDataPoint` reads; `sar_e.ingest.channel_signal` log integration point (§5.5 implements the consumer side).
- **SE-PRD-03:** `Baseline` reads for the funnel snapshot's `comparison=vs_baseline` column (if/when added — v1 supports `wow`, `yoy`, `vs_target` only; a baseline comparison is a future enhancement). For trendline, v1 returns only actual values; SE-PRD-03's baseline overlay is composed on the frontend.
- **SE-PRD-05:** Target reads for `comparison=vs_target` column on the funnel snapshot + trendline overlays.
- **PR-PRD-07:** `PlanTask.cost / channel / platform / owner_email / campaign_id`; Calendar `category` field is not consumed here (External Factors panel reads Calendar directly in PE-PRD-02).
- **PR-PRD-08:** `Campaign.campaign_id / objective` — the join table for cost-rollup-by-objective.
- **Existing files to study:**
  - `api/src/kene_api/routers/plans.py` — PlanTask listing + filter patterns
  - `api/src/kene_api/firestore.py` — collection-group query patterns

## 4. Data contract

### 4.1 Funnel snapshot

```python
class FunnelStageSnapshot(BaseModel):
    objective: FunnelObjective
    kpi_id: str                                              # resolved via history
    display_name: str                                        # EffectivenessKPI.display_name
    unit: Literal["count", "currency", "percent", "duration_seconds"]
    value: float                                             # sum or mean across the period per KPI.aggregation
    comparison_value: float | None                           # prior week / prior year / target, depending on mode
    comparison_delta_pct: float | None                       # (value - comparison_value) / comparison_value
    threshold_status: Literal["ok", "warn", "critical"] | None


class FunnelSnapshotResponse(BaseModel):
    account_id: str
    period: DateRange
    comparison_mode: Literal["wow", "yoy", "vs_target"]
    stages: list[FunnelStageSnapshot]                        # exactly 4
    generated_at: datetime
```

### 4.2 Trendline

```python
class TrendlinePoint(BaseModel):
    week_start: date
    value: float
    is_partial: bool                                         # carried through from KPIDataPoint


class TrendlineResponse(BaseModel):
    account_id: str
    objective: FunnelObjective
    kpi_ids: list[str]                                       # length 1 if mapping stable across window; 2+ if transitions
    transitions: list[dict]                                  # [{week_start, from_kpi_id, to_kpi_id}] — 0 entries if stable
    display_name: str                                        # the current-mapping KPI's display name
    unit: Literal["count", "currency", "percent", "duration_seconds"]
    window_weeks: int
    points: list[TrendlinePoint]                             # one per ISO week in the window
    generated_at: datetime
```

When the mapping changes mid-window, `points` still carries weekly values (each week uses the KPI valid at that week). `transitions` tells the UI where to draw a marker.

### 4.3 Cost rollup

```python
CostDimension = Literal["channel", "campaign", "platform", "owner"]


class CostRollupCell(BaseModel):
    dimension: CostDimension
    dimension_value: str                                     # e.g., "social_media", "campaign_id_abc", "meta_ads", "jane@example.com"
    dimension_display: str                                   # e.g., "Social Media", "Summer Promo", "Meta Ads", "Jane"
    objective: FunnelObjective
    week_start: date
    planned_cost: float
    task_count: int


class CostRollupResponse(BaseModel):
    account_id: str
    period: DateRange
    dimensions: list[CostDimension]
    cells: list[CostRollupCell]                              # `len(dimensions) × 4 objectives × N weeks × M distinct values`
    grand_total: float
    generated_at: datetime
```

The cell shape is a flat list for JSON friendliness; frontend pivots into 2D as needed.

### 4.4 Related metrics

```python
class RelatedMetricValue(BaseModel):
    kpi_id: str
    display_name: str
    unit: Literal["count", "currency", "percent", "duration_seconds"]
    value: float
    comparison_value: float | None
    comparison_delta_pct: float | None


class RelatedMetricsResponse(BaseModel):
    account_id: str
    period: DateRange
    comparison_mode: Literal["wow", "yoy"]
    metrics: list[RelatedMetricValue]                        # non-mapped active KPIs
    generated_at: datetime
```

"Related metrics" are every `EffectivenessKPI` with `is_active=true` that is NOT currently mapped to a funnel Objective. Useful for eyeballing signals not yet promoted into the core funnel.

## 5. Implementation outline

| Action | File |
|---|---|
| Create | `api/src/kene_api/services/sar_e_mapping_resolver.py` — historical mapping resolver |
| Create | `api/src/kene_api/services/sar_e_analytics_service.py` — all four queries |
| Create | `api/src/kene_api/services/sar_e_channel_coverage_builder.py` — signal → matrix roll-up |
| Modify | `api/src/kene_api/services/sar_e_ingestion_service.py` (SE-PRD-02) — call `channel_coverage_builder.record_signal(...)` after each week's writes |
| Create | `api/src/kene_api/utils/analytics_cache.py` — LRU + TTL + invalidation helpers |
| Create | `api/src/kene_api/routers/sar_e_analytics.py` — four GET endpoints |
| Modify | `api/src/kene_api/services/sar_e_config_service.py` (SE-PRD-01) — `bump_funnel_mapping` calls `analytics_cache.invalidate(account_id)`; same on KPI CRUD |
| Modify | `api/src/kene_api/services/sar_e_retrain_service.py` (SE-PRD-03) — calls `analytics_cache.invalidate(account_id)` after baseline persist |
| Modify | `api/src/kene_api/main.py` — mount `sar_e_analytics.router` |
| Modify | `deployment/terraform/firestore-indexes.tf` — composite indexes `(campaign_id ASC, week ASC)` and `(channel ASC, week ASC)` on `plans` collection-group |
| Create | `api/tests/unit/test_sar_e_mapping_resolver.py` |
| Create | `api/tests/unit/test_sar_e_analytics_service.py` |
| Create | `api/tests/unit/test_sar_e_channel_coverage_builder.py` |
| Create | `api/tests/integration/test_sar_e_analytics_endpoints.py` |
| Create | `api/tests/integration/test_sar_e_cost_rollup_with_uncovered_channels.py` |
| Create | `api/tests/perf/test_sar_e_cost_rollup_perf.py` |

### 5.1 Funnel snapshot

```python
async def get_funnel_snapshot(
    account_id: str,
    period: DateRange,
    comparison: Literal["wow", "yoy", "vs_target"],
) -> FunnelSnapshotResponse:
    # Resolve mapping at `period.end` (the "current" view)
    mapping = await resolve_mapping_at_week(account_id, period.end)
    if not mapping:
        return _empty_snapshot(account_id, period, comparison)

    stages = []
    for objective, kpi_id in mapping.items():
        kpi = await get_effectiveness_kpi(account_id, kpi_id)
        current_value = await _aggregate_kpi_over_period(account_id, kpi_id, period, kpi.aggregation)

        comparison_value = await _compute_comparison(
            account_id, kpi_id, kpi.aggregation, period, comparison
        )
        threshold_status = await _classify_against_thresholds(account_id, kpi_id, current_value)

        stages.append(FunnelStageSnapshot(
            objective=objective,
            kpi_id=kpi_id,
            display_name=kpi.display_name,
            unit=kpi.unit,
            value=current_value,
            comparison_value=comparison_value,
            comparison_delta_pct=_safe_pct_delta(current_value, comparison_value),
            threshold_status=threshold_status,
        ))

    return FunnelSnapshotResponse(
        account_id=account_id, period=period, comparison_mode=comparison,
        stages=stages, generated_at=datetime.utcnow(),
    )
```

`_compute_comparison` shifts the period by 7 days (wow) or 365 days (yoy; snapped to same-ISO-week alignment) or reads from `/targets` (vs_target — sums target values covering the period, keyed on the current-period mapping so "target" matches "what's being compared to"). For `vs_target`, if no target exists for a given objective/week, that stage's `comparison_value=null`.

### 5.2 Trendline

```python
async def get_trendline(
    account_id: str,
    objective: FunnelObjective,
    window_weeks: int = 53,
) -> TrendlineResponse:
    end_week = _last_complete_iso_week()
    start_week = end_week - timedelta(weeks=window_weeks - 1)

    # For each week in [start_week..end_week], resolve which KPI was mapped
    mappings_by_week = await resolve_mappings_for_range(
        account_id, DateRange(start=start_week, end=end_week)
    )
    kpi_ids_seen = set()
    transitions: list[dict] = []
    prior_kpi = None
    points: list[TrendlinePoint] = []

    for week in _iter_iso_weeks(start_week, end_week):
        per_week_mapping = mappings_by_week.get(week, {})
        kpi_id = per_week_mapping.get(objective)
        if kpi_id is None:
            # no mapping for this objective during this historical window — skip
            continue
        if prior_kpi is not None and prior_kpi != kpi_id:
            transitions.append({
                "week_start": week.isoformat(),
                "from_kpi_id": prior_kpi,
                "to_kpi_id": kpi_id,
            })
        prior_kpi = kpi_id
        kpi_ids_seen.add(kpi_id)

        point = await read_time_series_point(account_id, kpi_id, week)
        if point:
            points.append(TrendlinePoint(
                week_start=week, value=point.value, is_partial=point.is_partial,
            ))
        else:
            points.append(TrendlinePoint(week_start=week, value=0.0, is_partial=True))

    # Current display name + unit come from the last-week mapping
    current_kpi = await get_effectiveness_kpi(account_id, prior_kpi) if prior_kpi else None

    return TrendlineResponse(
        account_id=account_id, objective=objective,
        kpi_ids=sorted(kpi_ids_seen),
        transitions=transitions,
        display_name=current_kpi.display_name if current_kpi else "",
        unit=current_kpi.unit if current_kpi else "count",
        window_weeks=window_weeks,
        points=points,
        generated_at=datetime.utcnow(),
    )
```

53 weeks is the default (1 year + 1 week so week-over-week comparisons line up). Max 156 (3 years). Lower bound enforced: `window_weeks >= 4`.

### 5.3 Cost rollup

Reads every `PlanTask` in `accounts/{account_id}/plans/*/tasks/*` where:
- `due_date` falls within `period`
- `category` in `{"task"}` (exclude holidays / promotions / events — those are exogenous-event markers, not owned tasks; categories from PR-PRD-07)
- `assignee_type` in `{"human", "agent"}` — pipeline tasks have no cost

Group by `{dimension} × campaign.objective × week_start(due_date)` and sum `cost`. The `campaign_id → objective` mapping comes from `accounts/{account_id}/campaigns/{campaign_id}.objective` (PR-PRD-08). Tasks with no `campaign_id` fall back to one of PR-PRD-08's per-objective generic campaigns — resolving the objective via that fallback chain.

**Performance:** a collection-group query `plans.tasks` with filters `due_date >= start, due_date <= end` + an order-by `campaign_id` or `channel` (depending on requested dimensions) relies on the composite indexes in §4 / §5 file inventory. Expected query fanout: one query per dimension. With 4 dimensions, that's 4 Firestore queries, each streaming up to ~1000 tasks; the service then aggregates in Python. Measured on 500 tasks × 4 dimensions: p95 <500ms.

**Channel Coverage asymmetry:** no consultation of `ChannelCoverage`. Every task contributes, regardless of whether its `channel` is flagged under-covered. Integration test §7.AC-10 locks this.

### 5.4 Related metrics

Symmetric to `get_funnel_snapshot` but over non-mapped active KPIs. Cheap — same aggregation helper.

### 5.5 Channel Coverage builder

```python
class ChannelCoverageBuilder:
    def record_signal(
        self, account_id: str, week_start: date, channels_with_data: list[str]
    ) -> None:
        """Called by SE-PRD-02's ingestion service after each weekly write."""
        existing = get_channel_coverage(account_id)
        updated = _upsert_coverage_points(existing, week_start, channels_with_data)
        updated = _compact_to_last_n_weeks(updated, weeks=52)
        set_channel_coverage(account_id, updated)

    def compute_under_covered_channels(
        self, account_id: str, threshold: float = 0.6
    ) -> list[str]:
        coverage = get_channel_coverage(account_id)
        last_26 = _filter_weeks(coverage, weeks=26)
        channel_rates = _per_channel_has_data_rate(last_26)
        return [ch for ch, rate in channel_rates.items() if rate < threshold]
```

The builder writes on every ingestion call (cheap — one Firestore read + one Firestore write per weekly ingest per account). Admin-edit path via `PUT /config/channel-coverage` (SE-PRD-01) is manual override. Automatic writes respect manual overrides: if `has_data` was manually set to `true` for a channel/week, the builder does not overwrite it — instead it merges additively (always sets `true` when it sees data; leaves explicit manual values alone via a metadata flag `source: "auto" | "manual"` on each coverage point).

Extend `ChannelCoveragePoint` with an optional `source: Literal["auto", "manual"] = "auto"` field. Manual edits via `PUT /config/channel-coverage` (SE-PRD-01) set `source="manual"`; the builder only overwrites `source="auto"` rows.

## 6. API contract (owned here)

| Method | Path | Purpose | Role |
|---|---|---|---|
| `GET` | `/api/v1/sar-e/{account_id}/analytics/funnel?start&end&comparison` | Funnel snapshot | viewer |
| `GET` | `/api/v1/sar-e/{account_id}/analytics/trendline/{objective}?window_weeks` | 53-week trendline | viewer |
| `GET` | `/api/v1/sar-e/{account_id}/analytics/cost-rollup?start&end&dimensions` | Cost aggregated by dimensions × objective | viewer |
| `GET` | `/api/v1/sar-e/{account_id}/analytics/related-metrics?start&end&comparison` | Non-mapped KPI values + deltas | viewer |

All four gate on `SarEConfig.enabled=true`. If `enabled=false`, all four return `200 OK` with an empty-shape response (empty `stages`, `points`, `cells`, or `metrics` arrays); the UI renders the "set up forecasting" empty state (PE-PRD-01's `ForecastingEnabledGate` usually intercepts first, but the backend must still behave correctly if called directly).

## 7. Acceptance criteria

1. **Funnel snapshot — happy path.** Given an account with `enabled=true`, a current mapping of 4 KPIs, and 53 weeks of data, `GET /analytics/funnel?start=2026-04-06&end=2026-04-12&comparison=wow` returns 4 stages. Each stage has correct `kpi_id` (matching the mapping), `value` (matching the mapped KPI's aggregated weekly value), `comparison_value` (prior week's value), and `comparison_delta_pct` computed correctly.
2. **Funnel snapshot — `yoy`.** Same call with `comparison=yoy` returns each stage's `comparison_value` from 52 weeks prior (snapped to same ISO week).
3. **Funnel snapshot — `vs_target`.** With 4 targets persisted for the current period, `comparison=vs_target` returns each stage's `comparison_value` set to the target's `value` and `comparison_delta_pct` computed correctly. Stages without a target have `comparison_value=null`.
4. **Funnel snapshot — threshold.** A KPI's current value exceeds `critical_high` → `threshold_status="critical"`; between `warn_high` and `critical_high` → `"warn"`; within bounds → `"ok"`; no thresholds defined → `null`.
5. **Trendline — 53-week default.** `GET /analytics/trendline/Consideration?window_weeks=53` returns 53 points covering the last 53 complete ISO weeks (partial current week excluded from the window by design).
6. **Trendline — mapping transition.** Mid-window, the Consideration KPI is swapped. `kpi_ids` returns a length-2 list; `transitions` has a single entry with `from_kpi_id`, `to_kpi_id`, and the `week_start` of the switch; `points` carries the correct value per week (pre-transition reads the old KPI, post-transition reads the new one).
7. **Trendline — `is_partial` preserved.** A trendline ending at the current ISO week — if asked with `include_current_partial=true` (a query param added for PE-PRD-02's display) — includes the partial week's point with `is_partial=true`. (v1 default: excluded; flag gate this via query param for PE-PRD-02.)
8. **Cost-rollup — 1-dimension.** `?dimensions=channel` returns cells keyed by channel × objective × week; `grand_total` matches `sum(cells.planned_cost)`.
9. **Cost-rollup — multi-dimension.** `?dimensions=channel,campaign,platform,owner` returns cells across all 4 dimensions; task counts double-count across dimensions (expected — each dimension is an independent pivot; the grand total is computed against the unique-task planned-cost sum).
10. **Cost-rollup — under-covered channel included.** Given a channel flagged under-covered in `ChannelCoverage` and 10 tasks in that channel during the period, `/analytics/cost-rollup?dimensions=channel` returns cells for that channel with correct `planned_cost`. Paired assertion: the same scenario's VAR training excludes the channel from inputs (asserted via `Baseline.training_inputs.excluded_channels` from SE-PRD-03).
11. **Cost-rollup — performance.** 500 tasks × 4 dimensions × 12 weeks → p95 <500ms measured across 20 runs (fresh cache each run). Warmed-cache p95 <50ms.
12. **Related metrics — non-mapped only.** With 4 mapped KPIs + 2 non-mapped active KPIs, `/analytics/related-metrics?comparison=wow` returns 2 entries (the non-mapped KPIs); mapped KPIs are excluded.
13. **Enabled-gate — all four endpoints.** With `sar_e_config.enabled=false`, all four endpoints return 200 with empty arrays; no reads hit Firestore beyond the `SarEConfig` check.
14. **Cache behavior.** A funnel snapshot call warms the LRU; a second call within 5 minutes returns cached (mock Firestore call count = 0 on second call). A `PUT /config/funnel-mapping` invalidates the cache; the next funnel snapshot call re-queries.
15. **Cache invalidation on retrain.** A successful `/internal/sar-e/retrain-var` call invalidates the cache; the next trendline call reads fresh `KPIDataPoint` values (relevant when the retrain's ingest-task added new weekly rows).
16. **Channel Coverage population.** After 2 weekly ingestions — one with channels `[A, B]`, one with `[A]` only — `/config/channel-coverage` returns a matrix with `(A, W1, true, auto), (B, W1, true, auto), (A, W2, true, auto)`; `B` at W2 is absent (no signal).
17. **Channel Coverage — manual edit preserved.** Setting `(A, W3, false, manual)` via `PUT /config/channel-coverage`, then running an ingest that sees A with data → the manual entry is preserved; a new auto entry does not overwrite.
18. **Under-covered projection.** Channel `X` has `has_data=true` in 10 of the last 26 weeks (38% rate); `under_covered_channels` (projection on `/config/channel-coverage`) includes `X` when `threshold=0.6`. Not included when `threshold=0.3`.
19. **Funnel-mapping resolver correctness.** Given a history with versions `v1 (2026-01-01)`, `v2 (2026-02-15)`, `v3 (2026-03-20)`, querying `resolve_mapping_at_week(2026-02-20)` returns v2's mapping. Before v1 returns an empty mapping.
20. **Shape B + indexes.** Composite indexes for `(campaign_id, week)` + `(channel, week)` exist in `deployment/terraform/firestore-indexes.tf`.
21. **Tooling gates.** `make lint`, `mypy`, `ruff`, `codespell`, pytest pass.

## 8. Test plan

**Unit tests — mapping resolver** (`test_sar_e_mapping_resolver.py`):
- History of 3 versions; resolve returns the right version for any week
- Resolve before any version returns empty mapping
- Resolve for a week exactly at version-boundary uses the new version
- `resolve_mappings_for_range` with a mapping change in the middle returns a dict with distinct mappings for pre- and post-change weeks
- Cache hits on the second call within 5 minutes

**Unit tests — analytics service** (`test_sar_e_analytics_service.py`):
- Funnel snapshot aggregation: `sum` KPI over a 1-week period == the single weekly value; over a 4-week period == sum of 4 weekly values
- Funnel snapshot comparison: `wow` shifts 7 days; `yoy` shifts 364 days (7×52) to keep ISO-week alignment
- Threshold classification: all branches (`ok`, `warn`, `critical`, `null`)
- Trendline with a stable mapping returns a single-KPI `kpi_ids` list + empty `transitions`
- Trendline with a transition returns two KPIs + one transition entry
- Cost-rollup aggregation math
- Related-metrics excludes mapped KPIs

**Unit tests — channel coverage builder** (`test_sar_e_channel_coverage_builder.py`):
- `record_signal` with fresh account writes the first row
- Repeated signal for same (channel, week) is idempotent
- Compaction: after 53 weeks of signals, coverage matrix retains only the last 52 weeks
- Manual-override preservation: `source="manual"` rows are not overwritten
- `compute_under_covered_channels(threshold=0.6)` returns correct list

**Integration tests — endpoints** (`test_sar_e_analytics_endpoints.py`):
- All four endpoints happy path on a seeded account
- `enabled=false` → empty responses
- `window_weeks<4` → 422
- `window_weeks>156` → clamped to 156 (or 422 — confirm product preference at kickoff; first-pass: clamp silently)
- `dimensions` empty or unknown → 422

**Integration test — coverage asymmetry** (`test_sar_e_cost_rollup_with_uncovered_channels.py`):
- Seed an account with `ChannelCoverage` flagging "social_media" as under-covered
- Seed 10 `PlanTask`s with `channel="social_media"` during the period
- Assert `/analytics/cost-rollup?dimensions=channel` returns cells for "social_media" with correct totals
- Assert (in the same test) that the same account's latest `Baseline.training_inputs.excluded_channels` includes "social_media" — the cost rollup includes what VAR training excludes

**Perf test** (`test_sar_e_cost_rollup_perf.py`):
- Seed 500 `PlanTask`s across 4 dimensions × 4 campaigns × 12 weeks
- 20 iterations of `/analytics/cost-rollup?dimensions=channel,campaign,platform,owner` with cache disabled
- Assert p95 <500ms, p99 <1s
- 20 iterations with cache enabled: p95 <50ms

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| **Trendline query at 156 weeks × 4 KPIs could hit Firestore quota.** 156 × 4 = 624 doc reads per trendline × concurrent users. | Composite index on `(kpi_id ASC, week_start ASC)` + range queries pull all 156 rows in one shot per KPI (4 queries total). Easily within budget. Trendline caches at 5 min. |
| **Cost-rollup order-by + filter require matching composite indexes.** Missing indexes cause query failures at runtime. | `deployment/terraform/firestore-indexes.tf` PR in the same changeset; smoke test in CI that exercises each composite. |
| **Cache invalidation on PUT mapping is global-to-account.** If an admin PUTs a no-op mapping (identical to current), the cache is still flushed. | SE-PRD-01's `bump_funnel_mapping` already short-circuits to 304 on no-op — no invalidation fires in that case. |
| **Under-covered threshold is static at 0.6.** Some accounts with inherently spiky channels may be consistently flagged. | `SarEConfig.channel_coverage_threshold` (new field, add here or defer) lets admins override per account. First-pass: hardcode 0.6; add the override field in a follow-up if users need it. |
| **`ChannelCoverage` builder writes on every weekly ingest × every account.** 1000 accounts × 1 write/week = 52k writes/year — trivial. | No concern. Firestore pricing absorbs. |
| **Trendline "current partial week" display.** Including the partial week in the default window makes wow/yoy deltas asymmetric; excluding surprises users who just published data. | `window_weeks` defaults to the last 53 complete weeks; `?include_current_partial=true` opt-in. PE-PRD-02 decides how to render. |
| **Mapping resolver cache invalidation.** A mapping PUT changes the history; the resolver's cache entries for pre-change weeks remain valid, but post-change week entries become stale. | Invalidate resolver cache on every `PUT /config/funnel-mapping` — same hook as analytics-cache invalidation. |
| **`vs_target` comparison when targets exist for only some weeks.** Funnel snapshot over a 4-week period where targets cover 2 of the 4 weeks. | Aggregate `target_value` as `sum(target.value)` over weeks present; do not impute. If all weeks have targets, the comparison is clean; if partial, `comparison_value` is the partial sum and `comparison_delta_pct` is computed against that (documented). |
| **Related-metrics can surface unit-mismatched KPIs in one response.** (e.g., currency + percent together.) | The UI (PE-PRD-02) groups by unit; data layer returns flat list. Response already carries `unit` per metric; nothing to mitigate at the API. |

### Open questions

1. **Should `/analytics/funnel` support a multi-week period that spans a mapping change?** v1: treats the period as a whole and uses the latest mapping for the whole period. Alternative: split by mapping boundaries and return 4+ sub-periods. Splitting is complicated; v1 keeps it simple. Revisit if users report confusion.
2. **Should `CostRollup.cells` be pivoted on the server to `{dimension: {dimension_value: {objective: {week: cost}}}}`?** First-pass: flat list — simpler JSON, easier caching, frontend can pivot. Revisit if payload size becomes a concern.
3. **`ChannelCoverage` threshold configurability.** Add `SarEConfig.channel_coverage_threshold` here or defer to a follow-up? First-pass: defer. Hardcoded 0.6 until user feedback indicates otherwise.
4. **Related-metrics ordering.** Alphabetical by display_name? By `typical_direction`? v1: alphabetical. Product can override by passing `?order_by=`.
5. **Should trendline include upcoming baseline forecast points (baseline overlay)?** Currently the frontend composes the overlay from `/forecasts/baseline` + `/analytics/trendline/{objective}` separately. Alternative: trendline carries baseline points natively. Deferred — two endpoints keep concerns clean; frontend already does the compose.

## 10. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md) §6 SE-PRD-06
- Upstream: [SE-PRD-01](./SE-PRD-01-configuration-foundation.md), [SE-PRD-02](./SE-PRD-02-weekly-kpi-ingestion.md), [SE-PRD-03](./SE-PRD-03-var-baseline.md), [PR-PRD-07](../../project-tasks/projects/PR-PRD-07-calendar-activities.md), [PR-PRD-08](../../project-tasks/projects/PR-PRD-08-campaign-management.md)
- Related: [SE-PRD-05](./SE-PRD-05-target-derivation-specialist.md) — vs_target comparison reads targets
- Downstream: [SE-PRD-07](./SE-PRD-07-integration-testing-and-polish.md), [PE-PRD-02](../../performance/projects/PE-PRD-02-analysis-tab.md), [PE-PRD-07](../../performance/projects/PE-PRD-07-diagnostics-tab.md)
- CLAUDE.md rules in scope: PY-1, PY-2, PY-3, PY-5, PY-7; C-1, C-2, C-4; D-2, D-4, D-5; T-1, T-3, T-4, T-5, T-6, T-7, T-8; G-1
