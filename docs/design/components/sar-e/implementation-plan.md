# SAR-E (Simulation and Recommendations Engine) — Implementation Plan

**Status:** Draft — 2026-04-23 (revised for weekly-only aggregation, 12-week horizon, wizard-based enablement)
**Owner:** SAR-E component team (TBD)
**Proposed PRD prefix:** `SE-PRD-NN`

---

## 1. What SAR-E is

SAR-E is KEN-E's **analytical backend** for marketing measurement and forecasting. It owns:

- **Effectiveness KPI time series** — weekly values of business-configured metrics (e.g., `unbranded_search_clicks`, `pdp_views`, `first_purchases`). Ingested from Data Pipeline extracts and aggregated to weekly at storage time.
- **Funnel Stage Mapping** — the 4-row configuration binding each funnel Objective (`Problem Awareness | Brand Awareness | Consideration | Conversion`) to one Effectiveness KPI.
- **Statistical forecasting** — a Vector Auto-Regression (VAR) model trained per account on the 4 mapped KPIs at **weekly granularity**, producing **12-week** baseline forecasts. Scenario propagation via Impulse Response Functions (IRF).
- **LLM-driven Target derivation** — a new ADK specialist (`performance_forecasting`) compares the calendar of planned activities against the VAR baseline and historical periods to produce per-KPI Target values for the 12-week horizon.
- **Analytical queries** — funnel snapshot, 53-week trendlines, cost rollup by dimension × objective — composed from KPI time series + Project-Tasks calendar data.
- **Ancillary configuration** — Thresholds (anomaly bounds per KPI) and Channel Coverage (data-availability matrix). Exogenous events live as Calendar activities in project-tasks (category: `holiday` / `promotion` / `event`) and are read by SAR-E when needed — SAR-E does not own exogenous-event storage.

**SAR-E is opt-in per account.** At account creation the forecasting stack is disabled; it activates only after the user (a) connects at least one third-party integration (via Integrations) and (b) completes the Performance-page setup wizard that picks Effectiveness KPIs and maps them to funnel Objectives. Until that happens, the Performance Analysis and Simulations tabs show an empty-state / "set up forecasting" CTA.

Four facts shape the design:

1. **SAR-E is the computation home.** Performance renders SAR-E outputs; Data Pipeline feeds SAR-E inputs. SAR-E owns every statistical artifact — KPI series, baselines, targets, scenarios, thresholds, coverage, mapping history. A developer touching numbers touches this component.
2. **Weekly is the only internal granularity.** The VAR model, baseline forecasts, target derivation, and trendline queries all operate on weekly data. Daily data exists only as the raw extract from Data Pipeline jobs — it is aggregated to weekly at ingestion time and daily rows are not persisted in SAR-E. The 12-week forecast horizon is the v1 default; industries with longer customer lifecycles will be able to extend it in a future release.
3. **Reasoning belongs to an ADK specialist; math belongs to statsmodels.** VAR training + IRF propagation are closed-form numerical code (statsmodels + numpy) invoked synchronously at request time or on retrain. Target derivation is an ADK agent call (Gemini 2.0 Pro via Vertex AI) that reasons over the baseline + calendar + historical periods. Two independent subsystems; neither replaces the other.
4. **"Statistical association only" is a methodological invariant.** Every output phrases relationships as associations, never causation. Hard-coded in the specialist's system prompt, response schemas, and frontend copy contracts.

## 2. What exists today (before SAR-E)

| Upstream | What it gives us |
|---|---|
| **Agentic Harness (AH-PRD-02)** | `agent_factory.build_hierarchy()` + Firestore `agents/{agent_id}` config pattern. SAR-E's `performance_forecasting` specialist is a factory-assembled agent. |
| **Integrations** (IN-PRD-02+) | OAuth flows + credential substrate. SAR-E does not call external APIs directly — it consumes artifacts produced by Data Pipeline, which consumes Integrations. |
| **Project Tasks (PR-PRD-08)** | `Campaign` + `CampaignObjective` enum. SAR-E reads campaigns for cost rollups. |
| **Project Tasks (PR-PRD-07)** | `PlanTask.cost / channel / platform / owner_email / campaign_id`; calendar `category` including `"holiday"` / `"promotion"` / `"event"` — SAR-E reads these as exogenous-event context. |
| **Automations (A-PRD-01/02)** | Recurring `PlanRun` scheduler. SAR-E uses `is_system=true` recurring automations (created post-wizard, not at account creation) for weekly ingestion + retrain. |
| **Data Pipeline** (new, concurrent) | `google_analytics` connector + SAR-E-specific daily extraction jobs; Meta / Google Ads / Mailchimp connectors land as additional integrations come online. |
| **Data Management (DM-PRD-00, DM-PRD-07)** | Migration framework + audit shape for new collections. Role gate for mutations. |

## 3. Data-model

### 3.1 Effectiveness KPI registry

```python
class EffectivenessKPI(BaseModel):
    kpi_id: str                           # "unbranded_search_clicks"
    account_id: str                       # per-account only — no global catalog
    display_name: str                     # "Unbranded Search Clicks"
    source_job_id: str                    # FK to a DataPipelineJob; ingestion reads this job's artifacts
    unit: Literal["count", "currency", "percent", "duration_seconds"]
    typical_direction: Literal["up_is_good", "down_is_good", "neutral"]
    aggregation: Literal["sum", "mean", "weighted_mean"]   # how daily values roll up to weekly
    is_active: bool = True
    created_via: Literal["setup_wizard", "config_tab"]
    created_at: datetime
```

**No global/platform catalog.** Users create KPI definitions via the setup wizard (initial onboarding) or the Configuration tab (ongoing edits). A KPI can only be created when an underlying `DataPipelineJob` tied to a connected integration is available — the wizard enforces this.

### 3.2 KPI time series (weekly only)

```python
class KPIDataPoint(BaseModel):
    account_id: str
    kpi_id: str
    week_start: date                      # Monday of the ISO week, UTC
    value: float                          # aggregated per EffectivenessKPI.aggregation
    source_artifact_ids: list[str]        # Data Pipeline runs whose outputs rolled up into this week
    ingested_at: datetime
    is_partial: bool = False              # true if the week was incomplete at aggregation time
```

Stored at `accounts/{account_id}/kpi_time_series/{kpi_id}__{week_start_iso}`. Collection-group indexed by `(kpi_id, week_start)`. **No daily rows** — Data Pipeline's daily extracts are aggregated to weekly during the ingestion task and the source daily rows are not persisted in SAR-E. `is_partial` flags the current in-progress week, which is excluded from VAR training but included in trendline display (with a visual marker).

### 3.3 Funnel Stage Mapping

```python
class FunnelStageMapping(BaseModel):
    account_id: str
    mappings: dict[FunnelObjective, EffectivenessKPIId]  # exactly 4 entries
    version: int
    updated_at: datetime
    updated_by: str
```

Plus `FunnelMappingHistory` — `accounts/{account_id}/funnel_mapping_history/{version}` — so analytical queries resolve the mapping active for any historical week.

### 3.4 Baseline + Target

```python
class ForecastPoint(BaseModel):
    week_start: date
    value: float
    ci_low: float
    ci_high: float

class Baseline(BaseModel):
    account_id: str
    kpi_id: str
    generated_at: datetime
    model_version: str                    # "var-p4-lag2-2026-04-23"
    horizon_weeks: int = 12               # v1 default; per-account override planned for industry-specific lifecycles
    horizon: list[ForecastPoint]          # len == horizon_weeks
    confidence_level: Literal["low", "medium", "high"]   # from training sample size
    training_weeks: int                   # how much history the fit used

class Target(BaseModel):
    target_id: str
    account_id: str
    kpi_id: str
    period: DateRange                     # typically one ISO week within the 12-week horizon
    value: float
    baseline_value: float                 # captured at derivation time
    derived_by: Literal["specialist", "user_edit"]
    derivation_context_hash: str          # hash of calendar snapshot + baseline — idempotency key
    reasoning: str | None                 # specialist-provided justification
    created_at: datetime
    created_by: str
```

**Targets are superseded on edit** — no version history retained. `POST /targets` or `PATCH /targets/{id}` with a conflicting `(kpi_id, period)` overwrites the prior value; the audit log records the transition; the prior target value is not preserved.

### 3.5 Thresholds + Channel Coverage

```python
class Threshold(BaseModel):
    kpi_id: str
    bound: Literal["warn_low", "warn_high", "critical_low", "critical_high"]
    value: float

class ChannelCoverage(BaseModel):
    account_id: str
    matrix: list[ChannelCoveragePoint]    # (channel, week_start, has_data) triples
    updated_at: datetime
```

**Thresholds are surfaced on the Performance page only — v1 does not emit notifications on threshold breach.** Future enhancement if product demand warrants.

**Channel Coverage has split semantics:** channels flagged as under-covered are **excluded from VAR training** (insufficient data to estimate coefficients reliably) but **included in cost rollup** (users still need to see money spent there, even when the signal-to-noise for forecasting is poor).

### 3.6 Scenario response

```python
class ScenarioOverride(BaseModel):
    kpi_id: str
    week_start: date
    value: float                          # user-supplied override in natural units

class ScenarioDataPoint(BaseModel):
    week_start: date
    kpi_id: str
    baseline: float
    scenario: float
    incremental: float

class ScenarioResponse(BaseModel):
    account_id: str
    overrides: list[ScenarioOverride]
    data_points: list[ScenarioDataPoint]  # 12 weeks × 4 KPIs == 48 rows
    computed_at: datetime
    model_version: str
```

### 3.7 Firestore layout (Shape B)

| Path | Purpose |
|---|---|
| `accounts/{account_id}/sar_e_config` (doc) | `{enabled, setup_wizard_completed, forecast_horizon_weeks, initial_backfill_weeks}` |
| `accounts/{account_id}/effectiveness_kpis/{kpi_id}` | Per-account KPI definitions (no global catalog) |
| `accounts/{account_id}/kpi_time_series/{compound_id}` | Weekly time-series points |
| `accounts/{account_id}/funnel_mapping` (doc) | Current mapping |
| `accounts/{account_id}/funnel_mapping_history/{version}` | Audit trail |
| `accounts/{account_id}/baselines/{kpi_id}` | Latest baseline per KPI |
| `accounts/{account_id}/targets/{target_id}` | Saved targets (superseded on edit) |
| `accounts/{account_id}/thresholds/{kpi_id}` | Per-KPI thresholds |
| `accounts/{account_id}/channel_coverage` (doc) | Matrix |

No global KPI catalog. No exogenous-events collection (read from project-tasks Calendar).

## 4. API surface

### Analytical reads

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/sar-e/{account_id}/analytics/funnel` | 4-stage funnel snapshot for a period + comparison. |
| `GET` | `/api/v1/sar-e/{account_id}/analytics/trendline/{objective}` | Weekly Effectiveness-KPI trendline for a funnel stage (default 53-week window). |
| `GET` | `/api/v1/sar-e/{account_id}/analytics/cost-rollup` | Cost aggregated by `dimensions[]` (channel / campaign / platform / owner) × objective. **Includes under-covered channels.** |
| `GET` | `/api/v1/sar-e/{account_id}/analytics/related-metrics` | Non-mapped KPI values + deltas for a period. |

### Forecasts + scenarios + targets

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/sar-e/{account_id}/forecasts/baseline` | VAR baseline across all mapped KPIs over the 12-week horizon. |
| `POST` | `/api/v1/sar-e/{account_id}/scenarios` | IRF-propagated scenario given a list of weekly overrides. |
| `POST` | `/api/v1/sar-e/{account_id}/targets/derive` | Specialist derivation. |
| `GET` | `/api/v1/sar-e/{account_id}/targets` | List saved targets. |
| `POST` | `/api/v1/sar-e/{account_id}/targets` | Persist (supersedes any prior target for the same `(kpi_id, period)`). |
| `PATCH` | `/api/v1/sar-e/{account_id}/targets/{target_id}` | Edit (same supersede semantics). |
| `DELETE` | `/api/v1/sar-e/{account_id}/targets/{target_id}` | Soft-delete. |

### Configuration

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/sar-e/{account_id}/config/status` | `{enabled, setup_wizard_completed, connected_integrations, available_kpi_sources}`. Performance uses this to decide between empty-state CTA and live charts. |
| `POST` | `/api/v1/sar-e/{account_id}/config/setup` | **Wizard-completion endpoint.** Body: `{kpis[], funnel_mapping, initial_backfill_weeks}`. In one transaction: seeds KPI registry, writes funnel mapping, creates the weekly ingestion automation, kicks off the backfill plan. |
| `GET` / `PUT` | `/api/v1/sar-e/{account_id}/config/funnel-mapping` | Read / replace mapping (post-wizard edits). |
| `GET` | `/api/v1/sar-e/{account_id}/config/funnel-mapping/history` | Version history. |
| `GET` / `PUT` | `/api/v1/sar-e/{account_id}/config/thresholds` | Read / replace. |
| `GET` / `PUT` | `/api/v1/sar-e/{account_id}/config/channel-coverage` | Read / replace. |
| `GET` / `POST` / `PATCH` / `DELETE` | `/api/v1/sar-e/{account_id}/config/effectiveness-kpis[/{kpi_id}]` | CRUD outside the wizard (power users, post-setup additions). |

### Internal

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/internal/sar-e/ingest-kpi-series` | OIDC; called by the scheduled ingestion automation. Reads Data Pipeline artifacts for the past ISO week, aggregates to weekly per KPI (`sum` / `mean` / `weighted_mean` per `EffectivenessKPI.aggregation`), writes one `KPIDataPoint` per KPI per week with upsert semantics on `(kpi_id, week_start)`. |
| `POST` | `/api/v1/internal/sar-e/retrain-var` | OIDC; triggers VAR retrain. Scheduled weekly; admin-overridable for ad-hoc. |

## 5. Interaction with existing + concurrent components

### 5.1 Data Pipeline

SAR-E consumes Data Pipeline outputs. The integration is a single `is_system=true` recurring automation per account — **not seeded at account creation**. It is composed by the setup wizard after the user has (a) connected at least one third-party integration and (b) chosen KPIs + mapped them to objectives.

After wizard completion:

```
Plan: "SAR-E Weekly KPI Ingestion" (is_system=true, recurrence: 0 7 * * 1 UTC — Mondays at 07:00)
  ├─ task_1: ga.unbranded_search_daily   × 7 day-scoped invocations for the prior week
  ├─ task_2..N: one extraction chain per configured Effectiveness KPI
  └─ task_final: sar-e.ingest            (assignee_type=agent, depends_on=[all extractions])
              └─ tool calls POST /internal/sar-e/ingest-kpi-series
                 (aggregates 7 daily artifacts to 1 weekly row per KPI)
```

The exact task set depends on which integrations + KPIs the user selected — the wizard composes the plan dynamically. An initial backfill (default 104 weeks, configurable) runs as a one-shot `is_system` plan at wizard completion.

### 5.2 Agentic Harness

SAR-E ships one new specialist: `performance_forecasting`. Firestore config `agents/performance_forecasting`:

- **Model:** `gemini-2.0-pro`. A/B framework in SE-PRD-07 enables future optimization against Flash or successor models.
- **System prompt:** enforces "statistical association only" language; requires a `methodology_note` field in every response.
- **Tools:** `get_baseline(kpi_ids)`, `get_calendar_summary(start_week, end_week)` (includes `holiday` / `promotion` / `event` calendar entries as context), `get_historical_pulses(objective, lookback_weeks)`, `save_targets(targets)`.

Invoked from `POST /targets/derive`. Response: `{targets[], reasoning, confidence, methodology_note}`.

### 5.3 Project Tasks

- Reads `Campaign` + `PlanTask` for cost rollup. No writes.
- **Exogenous events live as Calendar activities** with `category in ["holiday", "promotion", "event"]`. SAR-E reads them through existing `/plans/*` APIs via the specialist's `get_calendar_summary` tool. Performance's Analysis tab also reads them directly for the "External Factors" panel — SAR-E does not proxy this read.

### 5.4 Automations

- `is_system=true` recurring automations for weekly ingestion + weekly VAR retrain, composed by the setup wizard.
- Target derivation is user-triggered in v1 (from Performance Simulations); auto-re-derive on calendar change is a future enhancement.

### 5.5 Performance

Performance is SAR-E's primary consumer. The Configuration tab surfaces funnel mapping, thresholds, and channel coverage; the Analysis and Simulations tabs render SAR-E's analytical and forecast outputs. **The setup-wizard UI is owned by Performance** — will need a dedicated PRD covering the wizard flow added to the Performance implementation plan (see §10 open questions).

### 5.6 Knowledge Graph

Out of scope for v1. Future: Baseline + Target snapshots could become dated `Observation` nodes for cross-session recall.

## 6. Phasing

Seven PRDs.

### SE-PRD-01 — Configuration foundation + setup state

**Delivers:** `EffectivenessKPI`, `FunnelStageMapping`, `FunnelMappingHistory`, `Threshold`, `ChannelCoverage` Pydantic models; `sar_e_config` per-account doc with `{enabled, setup_wizard_completed, forecast_horizon_weeks, initial_backfill_weeks}`; account-creation hook sets `enabled=false` + empty mapping + default thresholds; `/config/status` read endpoint; `/config/setup` wizard-completion endpoint that in one transaction seeds KPIs + writes mapping + creates the ingestion automation + triggers backfill; `/config/funnel-mapping`, `/config/thresholds`, `/config/channel-coverage`, `/config/effectiveness-kpis` routers for post-setup edits; `FunnelStageMapping` uniqueness validator; audit via DM-PRD-07.

**Blocked by:** DM-PRD-00, DM-PRD-07, PR-PRD-08.

**Blocks:** SE-PRD-02, SE-PRD-03, SE-PRD-06.

**Effort:** 4 days.

### SE-PRD-02 — Weekly KPI time series + ingestion

**Delivers:** `KPIDataPoint` weekly model + Firestore layout; `POST /internal/sar-e/ingest-kpi-series` reading Data Pipeline artifacts for the past ISO week and aggregating per KPI (`sum` / `mean` / `weighted_mean` per `EffectivenessKPI.aggregation`); partial-week handling (`is_partial=true` for current in-progress week, excluded from VAR input); upsert semantics on `(kpi_id, week_start)` for idempotency; backfill-path helper for wizard-triggered initial load up to 104 weeks.

**Blocked by:** SE-PRD-01, DP-PRD-01, DP-PRD-02.

**Blocks:** SE-PRD-03, SE-PRD-06.

**Effort:** 4 days.

### SE-PRD-03 — VAR model + baseline forecast

**Delivers:** `VAREstimator` wrapping statsmodels VAR on log-transformed weekly series (lag selection via AIC/BIC with a min-sample guard of **26 weeks**); under-covered channels excluded from the training input matrix per `ChannelCoverage`; `ForecastEngine` producing **12-week** horizon with 80% prediction intervals; `Baseline` persistence per KPI; `GET /forecasts/baseline`; `POST /internal/sar-e/retrain-var` called by a weekly `is_system` automation (the same plan that does ingestion, with retrain as a final step); model-version tagging; Weave span `sar_e.var_retrain`; `confidence_level` derived from `training_weeks`.

**Blocked by:** SE-PRD-02.

**Blocks:** SE-PRD-04, SE-PRD-05, SE-PRD-06.

**Effort:** 4 days.

### SE-PRD-04 — Scenario propagation (IRF)

**Delivers:** `IRFEngine` computing MA representation up to the 12-week horizon; persisted `irf_coefficients` snapshot tied to each model version; `POST /scenarios` accepting weekly overrides and returning baseline / scenario / incremental per KPI per week; natural-scale ↔ log-scale conversion at the API boundary.

**Blocked by:** SE-PRD-03.

**Blocks:** SE-PRD-05, SE-PRD-06.

**Effort:** 3 days.

### SE-PRD-05 — Target derivation specialist

**Delivers:** `performance_forecasting` Firestore agent config (model=`gemini-2.0-pro`) + tool-function module `app/adk/agents/performance_forecasting_tools.py`; system prompt enforcing "statistical association only" language + required `methodology_note` field; `get_baseline`, `get_calendar_summary` (includes `holiday`/`promotion`/`event` calendar categories), `get_historical_pulses`, `save_targets` tools; `POST /targets/derive` dispatching via the factory; `/targets` CRUD with **supersede-on-edit** semantics. Strict JSON-schema response validation with 2× retry. Idempotency on `derivation_context_hash`.

**Blocked by:** SE-PRD-03, SE-PRD-04, AH-PRD-02.

**Blocks:** SE-PRD-06, SE-PRD-07.

**Effort:** 4 days.

### SE-PRD-06 — Analytical query layer

**Delivers:** `/analytics/funnel`, `/analytics/trendline/{objective}` (default 53-week weekly window), `/analytics/cost-rollup` (four dimensions — channel / campaign / platform / owner — **includes under-covered channels**), `/analytics/related-metrics`. Each composes KPI time series + Project-Tasks calendar reads + FunnelStageMapping (historical resolution per week). Cache: 5-min TTL on funnel + trendline; cost rollup recomputed on demand.

**Blocked by:** SE-PRD-01, SE-PRD-02, SE-PRD-03, PR-PRD-07, PR-PRD-08.

**Blocks:** SE-PRD-07.

**Effort:** 4 days.

### SE-PRD-07 — Integration testing & polish

**Delivers:** End-to-end test: seed account → user connects Google → user runs wizard on Performance → SAR-E seeds KPIs + ingestion automation + 52-week backfill → Data Pipeline GA jobs execute → weekly aggregation writes 52 rows per KPI → VAR retrains → baseline + trendline queries succeed → user derives Target → supersedes → Simulations `vs Target` comparison reads it. Load test: 100 parallel `/scenarios` calls under 500ms p99. Methodology-language audit (no `caused` / `because` / `due to` in response strings). Model A/B harness for future Gemini-Flash vs Gemini-Pro evaluation. Runbook additions to `api/CLAUDE.md`.

**Blocked by:** SE-PRDs 01–06.

**Effort:** 3 days.

## 7. Dependency graph

```
┌─────────────────────────┐    ┌────────────────────────┐    ┌───────────────────┐
│     DM-PRD-00/07        │    │      PR-PRD-08         │    │     AH-PRD-02     │
│  (migration + audit)    │    │  (Campaign + objective)│    │  (agent factory)  │
└────────────┬────────────┘    └───────────┬────────────┘    └─────────┬─────────┘
             │                              │                          │
             └──────────┬───────────────────┘                          │
                        ▼                                              │
              ┌───────────────────┐                                    │
              │     SE-PRD-01     │ Configuration foundation + setup   │
              └─────────┬─────────┘                                    │
                        │                                              │
                        ▼                                              │
              ┌───────────────────┐     ┌──────────────────────┐       │
              │     SE-PRD-02     │◄────│  DP-PRD-01 + DP-PRD-02│      │
              │  Weekly ingestion │     │  (foundation + GA)   │       │
              └─────────┬─────────┘     └──────────────────────┘       │
                        │                                              │
                        ▼                                              │
              ┌───────────────────┐                                    │
              │     SE-PRD-03     │ VAR + 12-week baseline             │
              └─────────┬─────────┘                                    │
                        │                                              │
                        ▼                                              │
              ┌───────────────────┐                                    │
              │     SE-PRD-04     │ IRF + scenarios                    │
              └─────────┬─────────┘                                    │
                        │                                              │
                        ▼                                              │
              ┌───────────────────┐◄───────────────────────────────────┘
              │     SE-PRD-05     │ Target derivation specialist
              └─────────┬─────────┘
                        │
                        ▼
              ┌───────────────────┐
              │     SE-PRD-06     │ Analytical query layer
              └─────────┬─────────┘
                        │
                        ▼
              ┌───────────────────┐
              │     SE-PRD-07     │ Integration testing
              └───────────────────┘
```

## 8. Non-goals

- **Replacing BigQuery, Fivetran, or any warehouse.** SAR-E stores only the weekly time series the VAR model requires.
- **User-authored forecasting models.** Users configure KPI → Objective mapping. Custom models are a Skills concern.
- **Sub-weekly granularity.** Daily / hourly is not supported in v1. Daily-granularity overlays for anomaly investigation are a future enhancement.
- **Monthly aggregation.** Explicitly removed — weekly only internally.
- **Real-time streaming updates.** Weekly ingestion + weekly retrain + on-demand target derivation.
- **Owning data extraction.** Delegated to Data Pipeline.
- **Owning exogenous events.** Events live as Calendar activities in project-tasks; SAR-E reads them transiently for target-derivation context and for Performance "External Factors" display (Performance reads directly).
- **Causal inference claims.** All outputs are associations.
- **Multi-year deep historical analysis.** 53-week trendline read window; 12-week forecast window.
- **Account-creation-time forecasting setup.** Forecasting stack is opt-in via the setup wizard after at least one integration is connected.
- **Notifications on threshold breach.** Surface on Performance only in v1.

## 9. Risks

| Risk | Mitigation |
|---|---|
| Accounts with <26 weeks of history can't train a reliable VAR | Hard guard: if `training_weeks < 26`, return `confidence_level="low"` + a flat-baseline forecast with wide CI. The setup wizard warns that meaningful forecasts require ~6 months of history; backfill fetches up to 104 weeks where available. |
| User connects a brand-new integration (e.g., GA account <6 months old) | Backfill fetches whatever is available; baseline endpoint returns low-confidence forecasts until sufficient history accumulates. UI surfaces a "building history" banner. |
| Weekly aggregation masks intra-week anomalies | Accepted — v1 scope. Future daily-drill-down PRD for anomaly investigation. |
| LLM Target derivation returns inconsistent structure | Strict JSON-schema response validation; retry up to 2×; on failure fall back to baseline-as-target with a surfaced warning. |
| Cost rollup slow at 1000s of tasks/account | Firestore collection-group queries + composite indexes on `(campaign_id, week)` / `(channel, week)`; 5-min response cache. |
| KPI time-series storage growth | 4 KPIs × 52 weeks × N years per account — trivial volume. Safe to scale. |
| "Statistical association" language leaks to "caused" | System prompt + response-shape `methodology_note` + SE-PRD-07 audit gate. |
| Funnel-mapping change during a period skews trendlines | `FunnelMappingHistory` is resolved per-week on read. |
| VAR retrain (~minutes) on request path | Retrain runs async via the weekly `is_system` automation; baseline reads always hit the persisted snapshot. |
| Under-covered channel exclusion as two-places-of-truth bug | `ChannelCoverage` is the single source; VAR training consults it, cost rollup ignores it. Unit tests in SE-PRD-03 + integration tests in SE-PRD-06 assert the split. |
| Setup wizard abandonment mid-flow | Wizard state persisted per step; user can resume. Account shows a "Set up forecasting" banner until completion or dismissal. |
| Gemini Pro cost at scale | `derivation_context_hash` dedupes repeat invocations. SE-PRD-07's A/B framework enables Flash evaluation if cost becomes prohibitive. |
| Partial-week edge cases (week-boundary ingestion race) | `is_partial=true` flag on the current week; ingestion re-processes partial weeks until complete. |

## 10. Resolved decisions + remaining open questions

### Resolved

| Decision | Resolution |
|---|---|
| VAR deployment target | **Colocated with the API** uvicorn process. Retrain runs async; synchronous forecast reads from persisted baseline. |
| KPI catalog seeding | **No global catalog.** KPIs are defined per-account via the setup wizard after the user connects at least one integration. Forecasting stack is disabled until wizard completes. |
| Forecast horizon + granularity | **12 weeks, weekly.** v1 default; future industry-specific configurability via `sar_e_config.forecast_horizon_weeks`. No monthly. |
| Retrain cadence | **Weekly** — matches weekly aggregation. |
| Exogenous events ownership | **Project-tasks Calendar** (`category in ["holiday", "promotion", "event"]`). SAR-E reads transiently via `get_calendar_summary` tool and Performance reads directly for the External Factors panel. |
| Threshold behavior | **Surface only on Performance** in v1. No notifications. |
| Channel Coverage semantics | **Split.** Exclude under-covered channels from VAR training; include them in cost rollup. |
| Target version history | **Superseded on edit.** No version history retained. |
| VARX with exogenous events | **v2.** v1 is plain VAR on 4 mapped KPIs. |
| Specialist model | **Gemini 2.0 Pro** initially. Optimize later via SE-PRD-07's A/B framework. |

### Remaining open

| Question | Disposition |
|---|---|
| Wizard UX home on Performance | Initial-setup modal on the Configuration tab, or a dedicated `/performance/setup` route? Owned by the Performance component — needs a dedicated PRD added to the Performance plan. |
| Partial-week display in Simulations | Simulations operates over future weeks (all complete projections); partial-week concerns apply to Analysis trendline only. Confirm no cross-cutting issue during SE-PRD-02. |
| KPI-author-time source-job validation | When a user adds a KPI via the Configuration tab post-wizard, how do we validate the chosen `source_job_id` is appropriate for that KPI's `aggregation` / `unit`? First-pass: UI-only guardrails + backend schema check on `DataPipelineJob.output_schema`. |
| Channel Coverage population | Who writes `ChannelCoverage` — the ingestion path (based on row counts per channel per week)? An admin tool? Both? Decide during SE-PRD-02/06. |

## 11. Success criteria

- Account bootstrap leaves forecasting disabled; `GET /config/status` returns `{enabled: false, setup_wizard_completed: false}`.
- A user who connects Google Analytics, runs the setup wizard, picks 4 KPIs + maps them to objectives, and completes the wizard has: an active `is_system` weekly ingestion automation, up to 104 weeks of backfilled weekly KPI data, a baseline forecast per mapped KPI (low-confidence if `<26 weeks`), and a live Performance Analysis tab.
- `POST /targets/derive` on a seeded account with 20+ calendar activities returns per-KPI targets + reasoning in under 30s p95.
- `GET /analytics/funnel` + `/trendline/{objective}` + `/cost-rollup` together render in <500ms p95 for an account with 2 years of weekly data + 500 calendar tasks.
- `grep -rn 'caused\|because\|due to' api/src/kene_api/routers/sar_e*.py` yields zero matches in response strings.
- Under-covered channel is verifiably excluded from VAR training input (unit test) and included in cost-rollup output (integration test).
- The `performance_forecasting` specialist passes 20 golden-path eval cases in `tests/evals/performance_forecasting/`.
- Weekly retrain completes within 10 minutes p95 for an account with 104 weeks of data.
- Target supersede semantics verified: `POST /targets` with an existing `(kpi_id, period)` replaces the prior target and leaves exactly one row.
