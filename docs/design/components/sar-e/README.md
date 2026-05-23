# SAR-E (Simulation and Recommendations Engine) — Product Requirements Document

> **Linear Team:** [KEN-E] SAR-E
> **Last Updated:** 2026-04-23
> **Status:** Draft — 7 PRDs authored; implementation not yet started

## 1. Overview

SAR-E is KEN-E's **analytical backend** for marketing measurement and forecasting. It owns weekly Effectiveness KPI time series, the 4-row Funnel Stage Mapping that binds each funnel Objective (`Problem Awareness | Brand Awareness | Consideration | Conversion`) to one KPI, statistical forecasting via a Vector Auto-Regression (VAR) model trained per account, LLM-driven per-KPI-per-week Target derivation, and the analytical query layer the Performance page renders. A developer touching numbers — baselines, targets, trendlines, cost rollups — touches this component.

SAR-E is **opt-in per account**. At account creation the forecasting stack is disabled; it activates only after the user (a) connects at least one third-party integration (via Integrations) and (b) completes the Performance-page setup wizard that picks Effectiveness KPIs and maps them to Objectives. Until then, every SAR-E analytical endpoint returns an empty-shape response and the Performance Analysis / Simulations / Targets / Diagnostics tabs are hidden from the nav by `ForecastingEnabledGate` (PE-PRD-01). The gate flips atomically on successful `/config/setup` completion.

Four facts shape the design: (1) SAR-E is the computation home — Performance renders SAR-E outputs, Data Pipeline feeds SAR-E inputs, SAR-E owns every statistical artifact (KPI series, baselines, targets, scenarios, thresholds, coverage, mapping history). (2) Weekly is the only internal granularity — the VAR model, baseline forecasts, Target derivation, and trendline queries all operate on weekly data; daily rows are produced by Data Pipeline, aggregated to weekly at ingestion time, and the daily source rows are not persisted in SAR-E. (3) Reasoning belongs to an ADK specialist; math belongs to statsmodels — VAR training and IRF propagation are closed-form numerical code invoked synchronously at request time or on retrain; Target derivation is a Gemini 2.0 Pro specialist call that reasons over baseline + calendar + historical periods. (4) "Statistical association only" is a methodological invariant — every output phrases relationships as associations, never causation. Hard-coded in the specialist's system prompt, response schemas, and a `make lint` CI gate (SE-PRD-07) that scans `sar_e_*` files for banned phrases (`caused`, `because`, `due to`, …).

A developer reading only this section should understand: this component owns the `accounts/{account_id}/sar_e_config`, `effectiveness_kpis`, `kpi_time_series`, `funnel_mapping` (+history), `thresholds`, `channel_coverage`, `baselines`, `irf_coefficients`, and `targets` Firestore surfaces; the `/api/v1/sar-e/*` API; the weekly `is_system=true` ingestion + retrain automation (composed by SE-PRD-02, chained with retrain by SE-PRD-03); the `performance_forecasting` ADK specialist; and the methodology-language invariant. It is the platform the Performance page (PE-PRD-01 through PE-PRD-08) renders.

## 2. Architecture

```
┌───────────────────────────┐   ┌───────────────────────────┐
│ Integrations (IN-PRD-*)   │   │ Data Pipeline (DP-PRD-*)  │
│ - OAuth + credentials     │   │ - GA daily extraction jobs│
│ - connections roster      │   │ - Parquet artifacts       │
└─────────────┬─────────────┘   └─────────────┬─────────────┘
              │                                │
              ▼                                ▼
     ┌────────────────────────────────────────────────┐
     │  Setup Wizard (PE-PRD-05) + Config Tab (PE-04) │
     │   ↓ POST /config/setup (atomic transaction)    │
     │  Config foundation (SE-PRD-01)                 │
     │   - SarEConfig (enabled, horizon, backfill)    │
     │   - EffectivenessKPI × 4 (per-account)         │
     │   - FunnelStageMapping + history               │
     │   - Thresholds, ChannelCoverage                │
     └──────────────────────┬─────────────────────────┘
                            │
                            ▼
     ┌────────────────────────────────────────────────┐
     │  Weekly ingestion automation (SE-PRD-02)       │
     │   is_system=true; cron 0 7 * * 1 UTC           │
     │   - N Data Pipeline extract tasks (per KPI)    │
     │   - sar_e_ingestion glue agent task            │
     │       → POST /internal/sar-e/ingest-kpi-series │
     │         aggregates 7 daily → 1 weekly per KPI  │
     │   - sar_e_retrain glue agent task (SE-PRD-03)  │
     │       → POST /internal/sar-e/retrain-var       │
     └──────────────────────┬─────────────────────────┘
                            │
                            ▼
     ┌────────────────────────────────────────────────┐
     │   accounts/{account_id}/                       │
     │     kpi_time_series/{kpi_id}__{week_start}     │
     │     baselines/{kpi_id}          (SE-PRD-03)    │
     │     irf_coefficients/{model_version}           │
     │                                 (SE-PRD-04)    │
     │     targets/{target_id}         (SE-PRD-05)    │
     └──────┬──────────────────┬──────────────┬───────┘
            │                  │              │
            ▼                  ▼              ▼
  ┌──────────────────┐  ┌───────────────┐  ┌──────────────────┐
  │ /scenarios       │  │ /targets      │  │ /analytics/*     │
  │ (SE-PRD-04)      │  │ /derive       │  │ (SE-PRD-06)      │
  │ IRF propagation  │  │ (SE-PRD-05)   │  │ funnel /         │
  │ 48-row response  │  │ performance_  │  │ trendline /      │
  │                  │  │ forecasting   │  │ cost-rollup /    │
  │                  │  │ specialist    │  │ related-metrics  │
  └────────┬─────────┘  └───────┬───────┘  └────────┬─────────┘
           │                    │                   │
           └────────────────────┼───────────────────┘
                                ▼
                   ┌──────────────────────────┐
                   │  Performance page        │
                   │  (PE-PRD-01..08)         │
                   │  Analysis / Simulations /│
                   │  Targets / Diagnostics / │
                   │  Configuration           │
                   └──────────────────────────┘
```

### 2.1 Key Directories

SAR-E is a backend-only component. Every surface lives in `api/` + `app/adk/`; there is no SAR-E-owned frontend code (the Performance component consumes SAR-E via HTTP).

| Path | Purpose |
|------|---------|
| `api/src/kene_api/models/sar_e_models.py` | All Pydantic models: `SarEConfig`, `EffectivenessKPI`, `FunnelStageMapping`, `FunnelMappingHistoryEntry`, `Threshold`, `ChannelCoverage`, `KPIDataPoint`, `Baseline`, `ForecastPoint`, `IRFCoefficients`, `ScenarioOverride`/`ScenarioDataPoint`/`ScenarioResponse`, `Target`/`DerivedTarget`/`DerivedTargetsResponse`, analytical-query responses (SE-PRDs 01–06) |
| `api/src/kene_api/routers/sar_e_config.py` | `/config/status`, `/config/setup`, `/config/funnel-mapping` (+history), `/config/thresholds`, `/config/channel-coverage`, `/config/effectiveness-kpis` CRUD (SE-PRD-01) |
| `api/src/kene_api/routers/sar_e_ingestion.py` | `/internal/sar-e/ingest-kpi-series` + `/config/backfill-plan` (SE-PRD-02) |
| `api/src/kene_api/routers/sar_e_forecasts.py` | `/forecasts/baseline`, `/internal/sar-e/retrain-var`, `/scenarios` (SE-PRDs 03 + 04) |
| `api/src/kene_api/routers/sar_e_targets.py` | `/targets` CRUD + `/targets/derive` (SE-PRD-05) |
| `api/src/kene_api/routers/sar_e_analytics.py` | `/analytics/funnel`, `/trendline/{objective}`, `/cost-rollup`, `/related-metrics` (SE-PRD-06) |
| `api/src/kene_api/routers/sar_e_admin.py` | `/internal/admin/sar-e/model-ab` super-admin A/B harness (SE-PRD-07) |
| `api/src/kene_api/services/sar_e_config_service.py` | Wizard-completion transaction + config mutations with audit (SE-PRD-01) |
| `api/src/kene_api/services/sar_e_ingestion_service.py` | Weekly aggregation + compound-id upsert + partial-week handling (SE-PRD-02) |
| `api/src/kene_api/services/sar_e_automation_seeder.py` | Composes the weekly ingestion + retrain automation plan and the one-shot backfill plan (SE-PRDs 01 stub → 02 + 03 full) |
| `api/src/kene_api/services/sar_e_training_input.py` | Assembles `(weeks × 4)` training matrix from `kpi_time_series`; aligns weeks; excludes `is_partial=true` rows (SE-PRD-03) |
| `api/src/kene_api/services/sar_e_var_estimator.py` | `VAREstimator` wrapping statsmodels VAR + `FlatBaselineModel` fallback (SE-PRD-03) |
| `api/src/kene_api/services/sar_e_forecast_engine.py` | Produces 12-week `Baseline` horizons with 80% PI; log1p↔expm1 conversions (SE-PRD-03) |
| `api/src/kene_api/services/sar_e_retrain_service.py` | Retrain orchestrator — reads matrix → fits → persists baselines + IRF snapshot → Weave span (SE-PRDs 03 + 04) |
| `api/src/kene_api/services/sar_e_irf_engine.py` | MA representation + natural/log-scale scenario propagation (SE-PRD-04) |
| `api/src/kene_api/services/sar_e_scenario_service.py` | Loads baseline + IRF snapshot + validates overrides + propagates (SE-PRD-04) |
| `api/src/kene_api/services/sar_e_target_derivation.py` | Wraps the specialist dispatch + context-hash cache + methodology lint + retry loop (SE-PRD-05) |
| `api/src/kene_api/services/sar_e_target_service.py` | Targets CRUD with supersede-on-edit transaction (SE-PRD-05) |
| `api/src/kene_api/services/sar_e_historical_pulses.py` | 1.5σ-deviation detection against a 4-week trailing mean with calendar-category annotation (SE-PRD-05) |
| `api/src/kene_api/services/sar_e_analytics_service.py` | Funnel snapshot, trendline, cost-rollup, related-metrics composition (SE-PRD-06) |
| `api/src/kene_api/services/sar_e_mapping_resolver.py` | Per-week historical mapping resolution via `FunnelMappingHistory` (SE-PRD-06) |
| `api/src/kene_api/services/sar_e_channel_coverage_builder.py` | Per-ingest signal → matrix roll-up with manual-override preservation (SE-PRDs 02 signal + 06 consumer) |
| `api/src/kene_api/utils/analytics_cache.py` | In-process LRU with 5-min TTL + cross-endpoint invalidation helpers (SE-PRD-06) |
| `app/adk/agents/performance_forecasting/__init__.py` | Factory-built specialist (Gemini 2.0 Pro) registered at `agent_configs/performance_forecasting` (SE-PRD-05) |
| `app/adk/agents/performance_forecasting/system_prompt.py` | "Statistical association only" system prompt with banned-phrase rules |
| `app/adk/agents/performance_forecasting/tools.py` | `get_baseline`, `get_calendar_summary`, `get_historical_pulses`, advisory `save_targets` function tools |
| `api/tests/fixtures/gemini_pro_target_derivation/` | 20 recorded eval fixtures for specialist (SE-PRD-05) |
| `tests/evals/performance_forecasting/` | Golden-path eval cases for the specialist |
| `api/tests/lint/test_methodology_language.py` | `make lint` gate — zero banned causation phrases in `sar_e_*` files (SE-PRD-07) |
| `api/tests/lint/methodology_allowlist.txt` | Permitted matches with documented reasons (SE-PRD-07) |
| `tests/load_test/sar_e_scenarios_locust.py` + `sar_e_analytics_locust.py` | Nightly load test gating p99/p95 thresholds (SE-PRD-07) |
| `api/tests/integration/test_sar_e_full_lifecycle.py` | End-to-end 8-milestone lifecycle test (SE-PRD-07) |
| `deployment/terraform/firestore-indexes.tf` | SAR-E composite indexes: `kpi_time_series (kpi_id, week_start)` + partial filter, `funnel_mapping_history (version DESC)`, `plans (campaign_id, week)` + `(channel, week)`, `targets (kpi_id, period.start, is_active)` |

### 2.2 Data Flow

1. **Account creation (SE-PRD-01).** On `POST /api/v1/accounts/`, the post-create hook writes `accounts/{account_id}/sar_e_config` with `{enabled: false, setup_wizard_completed: false, forecast_horizon_weeks: 12, initial_backfill_weeks: 104}`, an empty `funnel_mapping` (version 0), and an empty `channel_coverage`. Every SAR-E endpoint that mutates or computes returns an empty-shape response until `enabled` flips.
2. **Setup wizard probe (SE-PRD-02).** The wizard's Step 3 posts to `/config/backfill-plan` with 4 `source_job_id`s; SAR-E queries Data Pipeline's `/jobs/{id}/history-depth` per source (5-min LRU), returns `backfill_weeks = min(104, min(per_source_depth))` + the limiting source. The UI uses this to display the cap.
3. **Wizard completion (SE-PRD-01).** `POST /config/setup` runs one Firestore transaction: seed 4 `EffectivenessKPI` docs, write `FunnelStageMapping` v1 + `FunnelMappingHistory/1`, flip `SarEConfig.enabled=true`. Outside the transaction: call `sar_e_automation_seeder.create_weekly_ingestion_automation(...)` to create the `is_system=true` recurring plan (cron `0 7 * * 1 UTC`), then `trigger_one_shot_backfill(...)` to start the initial backfill plan. On side-effect failure, the endpoint compensates by flipping `enabled=false` so the wizard can retry cleanly.
4. **Weekly ingestion (SE-PRD-02).** Every Monday at 07:00 UTC the Automations platform fires the plan. Per KPI, a Data Pipeline extract task pulls 7 daily rows for the prior ISO week; the `sar_e_ingestion` glue agent calls `POST /internal/sar-e/ingest-kpi-series` with the artifact refs; the service aggregates 7 daily → 1 weekly per `EffectivenessKPI.aggregation` (`sum` / `mean` / `weighted_mean`) and upserts `KPIDataPoint` at `accounts/{account_id}/kpi_time_series/{kpi_id}__{week_start}`. Partial weeks (current in-progress ISO week) are written with `is_partial=true` and overwritten atomically when the week completes.
5. **Channel signal roll-up (SE-PRDs 02 + 06).** Each ingest call invokes `channel_coverage_builder.record_signal(...)` with the per-channel non-zero list; the builder upserts `ChannelCoveragePoint` (`source="auto"`) without overwriting `source="manual"` entries. Admin edits via `PUT /config/channel-coverage` set `source="manual"`.
6. **Weekly retrain (SE-PRD-03).** After the ingest task, the plan's final `sar_e_retrain` glue agent calls `POST /internal/sar-e/retrain-var`. The service assembles the training matrix (aligned on `week_start`, `is_partial=false` only), runs statsmodels VAR on log1p-transformed series with AIC lag selection (min 26 weeks, max lag 8), falls back to `FlatBaselineModel` below the threshold (wide CI, `confidence_level="low"`), produces + persists 4 `Baseline` docs at `accounts/{account_id}/baselines/{kpi_id}`, and computes + persists an `IRFCoefficients` snapshot at `accounts/{account_id}/irf_coefficients/{model_version}` (retention: latest 4). A Weave `sar_e.var_retrain` span captures timing + confidence.
7. **Scenario read (SE-PRD-04).** `POST /scenarios` with 1–100 per-(kpi_id, week) overrides loads the current baseline bundle + the matching IRF snapshot (cache keyed by `model_version`), validates overrides (within the 12-week horizon, no duplicates, known KPIs), propagates in log space via `scenario_log = baseline_log + Σ (ma_rep[h - w_override] · delta_j)`, converts via `expm1`, clamps non-negatives, returns 48 `ScenarioDataPoint`s. Stateless — no persistence. p99 ≤500ms at 100 concurrent.
8. **Target derivation (SE-PRD-05).** `POST /targets/derive` dispatches the `performance_forecasting` specialist (Gemini 2.0 Pro) with a system prompt enforcing "statistical association only" language. The specialist calls `get_baseline`, `get_calendar_summary` (project-tasks Calendar including `holiday` / `promotion` / `event` categories), `get_historical_pulses` (1.5σ-deviation weeks with calendar overlap context), and emits a `DerivedTargetsResponse` of 48 targets (12 weeks × 4 KPIs) with per-target `reasoning` + `methodology_note`. Response-schema + banned-phrase runtime lint (retry up to 2×, 502 on 3rd failure with `fallback_available=true`). Idempotency cache on `sha256(baseline + calendar + pulses)` with 10-min TTL.
9. **Target persistence (SE-PRD-05).** Users save derived targets via `POST /targets` (one per `(kpi_id, period)`). Supersede-on-edit: a prior target for the same key is hard-deleted in the same transaction, replaced by the new target with a fresh `target_id`. No version history. `PATCH` delegates to supersede with `derived_by="user_edit"`. `DELETE` soft-deletes (`is_active=false`) for audit.
10. **Analytical reads (SE-PRD-06).** `/analytics/funnel` (4 stages × current KPI mapping × `wow`/`yoy`/`vs_target` comparison + threshold status), `/trendline/{objective}` (53-week default, per-week mapping resolution from `FunnelMappingHistory`, transitions surfaced), `/cost-rollup` (dimensions × objective from `PlanTask.cost` joined via `Campaign.objective` — **includes** under-covered channels), `/related-metrics` (non-mapped active KPIs). 5-min LRU cache invalidated on mapping PUT, KPI CRUD, and retrain.
11. **Diagnostics (PE-PRD-07).** Reads `Baseline.confidence_level` + `generated_at` per KPI; if `generated_at` is >8 days old, PE-PRD-07 surfaces a "retrain needed" flag (inspection only; does not re-trigger).

### 2.3 API Contracts

Owned endpoints (all under `/api/v1/sar-e/{account_id}/` unless noted):

| Endpoint | Method | Owner | Schema |
|----------|--------|-------|--------|
| `/config/status` | GET | SE-PRD-01 | `SarEConfigStatus` (joins Integrations + Data Pipeline catalog) |
| `/config/setup` | POST | SE-PRD-01 | `SetupRequest` → `SetupResponse`; atomic; admin-only |
| `/config/funnel-mapping` | GET / PUT | SE-PRD-01 | `FunnelStageMapping` |
| `/config/funnel-mapping/history` | GET | SE-PRD-01 | `list[FunnelMappingHistoryEntry]` most-recent-first |
| `/config/thresholds` | GET / PUT | SE-PRD-01 | `list[Threshold]` |
| `/config/channel-coverage` | GET / PUT | SE-PRD-01 / SE-PRD-06 builder | `ChannelCoverage` |
| `/config/effectiveness-kpis[/{kpi_id}]` | GET / POST / PATCH / DELETE | SE-PRD-01 | `EffectivenessKPI` |
| `/config/backfill-plan` | POST | SE-PRD-02 | `BackfillPlanRequest` → `BackfillPlanResponse` |
| `/forecasts/baseline` | GET | SE-PRD-03 | `BaselineBundle`; `Cache-Control: max-age=30` |
| `/scenarios` | POST | SE-PRD-04 | `ScenarioRequest` → `ScenarioResponse` (48 rows) |
| `/targets/derive` | POST | SE-PRD-05 | `DeriveRequest` → `DeriveResponse`; p95 ≤30s |
| `/targets[/{target_id}]` | GET / POST / PATCH / DELETE | SE-PRD-05 | `Target` with supersede-on-edit |
| `/analytics/funnel?start&end&comparison` | GET | SE-PRD-06 | `FunnelSnapshotResponse` |
| `/analytics/trendline/{objective}?window_weeks` | GET | SE-PRD-06 | `TrendlineResponse` (default 53 weeks, max 156) |
| `/analytics/cost-rollup?start&end&dimensions` | GET | SE-PRD-06 | `CostRollupResponse` — **includes** under-covered channels |
| `/analytics/related-metrics?start&end&comparison` | GET | SE-PRD-06 | `RelatedMetricsResponse` |
| `/internal/sar-e/ingest-kpi-series` | POST | SE-PRD-02 | OIDC; glue-agent-called |
| `/internal/sar-e/retrain-var` | POST | SE-PRD-03 | OIDC; glue-agent-called + ad-hoc admin |
| `/internal/admin/sar-e/model-ab` | GET / PUT | SE-PRD-07 | super-admin A/B harness config |

Schema source of truth: `api/src/kene_api/models/sar_e_models.py` (Pydantic). The TypeScript branded types consumed by PE-PRD-* live in `frontend/src/types/performance/*.ts` and mirror the Python shapes. `Campaign.objective` / `FunnelObjective` is a type-alias re-export from `PR-PRD-08.CampaignObjective` so the 4-value enum stays in lockstep.

Consumed endpoints:

| Endpoint | Owner | Purpose in SAR-E |
|----------|-------|------------------|
| `/api/v1/internal/integrations/{account_id}/connections` | Integrations (IN-PRD-*) | Join into `/config/status.connected_integrations` |
| `/api/v1/internal/data-pipeline/jobs?account_id=…` | Data Pipeline (DP-PRD-01) | KPI-source validator on `POST /config/effectiveness-kpis` |
| `/api/v1/internal/data-pipeline/jobs/{job_id}/history-depth?account_id=…` | DP-PRD-02 | `/config/backfill-plan` pre-submit probe |
| `/api/v1/internal/data-pipeline/run` (transitively, via `TaskOrchestrator`) | DP-PRD-03 | Weekly ingestion + backfill plan DAG fan-out |
| `/api/v1/plans/*` — `PlanTask` + `Campaign` reads | PR-PRD-07 + PR-PRD-08 | `get_calendar_summary` tool + `/analytics/cost-rollup` + historical-pulse calendar overlap |
| `/api/v1/automations/{account_id}/{plan_id}/runs` (manual-trigger) | A-PRD-02 | One-shot backfill plan kick-off in `/config/setup` |

### 2.4 Key Abstractions

| Abstraction | Path | Purpose |
|-------------|------|---------|
| `SarEConfig` | `api/src/kene_api/models/sar_e_models.py` | Single per-account doc at `accounts/{account_id}/sar_e_config`. `enabled` is the opt-in gate every SAR-E endpoint checks; wizard completion flips it atomically. |
| `EffectivenessKPI` + `FunnelStageMapping` | same | Per-account (no global catalog). Mapping references a KPI `kpi_id`; history resolved per-week at analytical-query time. |
| `KPIDataPoint` | same | One weekly row per KPI. Compound doc id `{kpi_id}__{week_start_iso}` enables idempotent upsert. `is_partial=true` marks the in-progress ISO week (excluded from VAR training, included in trendlines). |
| `Baseline` + `IRFCoefficients` | same | Persisted retrain output. `Baseline` holds 12 weekly `ForecastPoint`s per KPI + `confidence_level` + `training_inputs` snapshot; `IRFCoefficients` is the `(13, 4, 4)` MA-representation snapshot addressable by `model_version` (retention: latest 4). |
| `VAREstimator` / `FlatBaselineModel` / `ForecastEngine` | `api/src/kene_api/services/sar_e_{var_estimator,forecast_engine}.py` | statsmodels VAR on log1p-transformed series (AIC, min 26 weeks, max lag 8); `FlatBaselineModel` fallback for `<26 weeks` returns per-KPI last-4-weeks mean with `±2σ` CI. |
| `IRFEngine` | `api/src/kene_api/services/sar_e_irf_engine.py` | MA representation + natural↔log scenario propagation. Flat-baseline fallback emits identity MA (no cross-KPI propagation). Scenario superposition is a linear sum of per-override contributions; tested with 1e-9 tolerance. |
| `performance_forecasting` specialist | `app/adk/agents/performance_forecasting/` | Gemini 2.0 Pro; resolved per turn by `specialist_runtime.resolve_agent` (AH-PRD-09 Phase 2) from `agent_configs/performance_forecasting`; reached via `delegate_to_specialist("performance_forecasting", …)`. Tools `get_baseline` / `get_calendar_summary` / `get_historical_pulses` (advisory `save_targets`); strict `DerivedTargetsResponse` schema + banned-phrase runtime lint. |
| `Target` with supersede-on-edit | `api/src/kene_api/services/sar_e_target_service.py` | `POST /targets` / `PATCH /targets/{id}` with a conflicting `(kpi_id, period)` hard-deletes the prior row + writes a fresh one. Zero version history. Audit records the transition. |
| `sar_e_mapping_resolver` | `api/src/kene_api/services/sar_e_mapping_resolver.py` | Walks `FunnelMappingHistory` to answer "which KPI was Consideration during week X?" — keeps trendlines coherent across mapping edits. |
| `ChannelCoverage` split semantics | `sar_e_channel_coverage_builder.py` + `sar_e_training_input.py` + `sar_e_analytics_service.py` | Under-covered channels are **excluded** from VAR training input but **included** in cost rollup. Single source of truth (the matrix); two consumers enforce the asymmetry. Paired integration test in SE-PRD-06 locks it. |
| `derivation_context_hash` | `sar_e_target_derivation.py` | `sha256(baseline + calendar + pulses)` 10-min LRU key — dedupes repeat derivation calls so Gemini Pro isn't paid twice for identical context. |
| Methodology lint | `api/tests/lint/test_methodology_language.py` | `make lint` gate. Scans router / service / model / specialist files for banned phrases (`caused`, `because`, `due to`, …). Allowlist file handles documented exceptions. |

## 3. Component Dependencies

### 3.1 Depends On

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **Data Management — DM-PRD-00 (Migration Foundation)** | **Hard prerequisite for SE-PRD-01.** Establishes the Shape B convention + `_migrate_shape_b/resources.py` registry. Every SAR-E collection (`sar_e_config`, `effectiveness_kpis`, `kpi_time_series`, `funnel_mapping` (+history), `thresholds`, `channel_coverage`, `baselines`, `irf_coefficients`, `targets`) is registered there. | [`../data-management/projects/DM-PRD-00-migration-foundation.md`](../data-management/projects/DM-PRD-00-migration-foundation.md) |
| **Data Management — DM-PRD-07 (Roles, Members, Audit Substrate)** | **Hard prerequisite for SE-PRD-01.** `AccountRole` enum + `require_role(AccountRole.EDITOR \| AccountRole.ADMIN, scope="account")` dependencies + generalized `write_audit(parent_kind="account", parent_id=account_id, audit_subcollection="sar_e_audit", ...)` helper. Every SAR-E mutation (setup / mapping PUT / threshold PUT / KPI CRUD / target writes / A/B config updates) writes an audit entry. | [`../data-management/projects/DM-PRD-07-approval-workflow-and-audit.md`](../data-management/projects/DM-PRD-07-approval-workflow-and-audit.md) |
| **Project Tasks — PR-PRD-07 (Calendar Activities)** | **Hard prerequisite for SE-PRD-05 + SE-PRD-06.** `PlanTask.category` (`task` / `promotion` / `holiday` / `event`) + `cost` / `channel` / `platform` / `owner_email` / `campaign_id`. Specialist's `get_calendar_summary` tool + analytical cost-rollup + historical-pulse calendar overlap all depend on these fields. | [`../project-tasks/projects/PR-PRD-07-calendar-activities.md`](../project-tasks/projects/PR-PRD-07-calendar-activities.md) |
| **Project Tasks — PR-PRD-08 (Campaign Management)** | **Hard prerequisite for SE-PRD-01 + SE-PRD-06.** Exports the `CampaignObjective` enum (`FunnelObjective` is a type-alias re-export). Cost-rollup joins `PlanTask.campaign_id → Campaign.objective`. | [`../project-tasks/projects/PR-PRD-08-campaign-management.md`](../project-tasks/projects/PR-PRD-08-campaign-management.md) |
| **Data Pipeline — DP-PRD-01 (Foundation)** | **Hard prerequisite for SE-PRD-02.** `DataPipelineJob`, `DataPipelineRun`, `PipelineOutput` contracts; `/internal/data-pipeline/run`; job catalog read. | [`../data-pipeline/projects/DP-PRD-01-foundation.md`](../data-pipeline/projects/DP-PRD-01-foundation.md) |
| **Data Pipeline — DP-PRD-02 (GA Connector)** | **Hard prerequisite for SE-PRD-02.** Delivers the four SAR-E-specific GA daily jobs (`ga.unbranded_search_daily`, `ga.branded_search_daily`, `ga.pdp_views_daily`, `ga.first_purchases_daily`) with deterministic `[{date, value, weight?}]` Parquet output + a `/history-depth` indicator the backfill-plan probe consumes. | [`../data-pipeline/projects/DP-PRD-02-google-analytics-connector.md`](../data-pipeline/projects/DP-PRD-02-google-analytics-connector.md) |
| **Data Pipeline — DP-PRD-03 (Task-system Integration)** | **Hard prerequisite for SE-PRD-02.** `PlanTask.assignee_type="data_pipeline"` + `TaskOrchestrator.on_task_due` `data_pipeline` branch — SAR-E's weekly ingestion plan's extract tasks route through this path. | [`../data-pipeline/projects/DP-PRD-03-task-system-integration.md`](../data-pipeline/projects/DP-PRD-03-task-system-integration.md) |
| **Automations — A-PRD-01, A-PRD-02, A-PRD-03** | **Hard prerequisite for SE-PRDs 01 + 02 + 03.** `ProjectPlan` automation fields (`is_system=true`, `recurrence_cron`), `PlanRun` model, Cloud Scheduler recurring tick, manual-trigger endpoint for backfill kickoff, `TaskArtifact` + `attach_task_artifact` pattern (artifacts are the inter-task contract SAR-E's ingestion reads). | [`../automations/README.md`](../automations/README.md) §2 |
| **Agentic Harness — AH-PRD-02 (Agent Factory) + AH-PRD-09 Phase 2 (Per-Turn Dispatch)** | **Hard prerequisite for SE-PRD-05.** AH-PRD-02 publishes the `agent_configs/{config_id}` schema (including `response_schema`). AH-PRD-09 Phase 2 ships `specialist_runtime.resolve_config` + `resolve_agent` (per-turn construction) and `delegate_to_specialist` (the single root tool). `agent_configs/performance_forecasting` is resolved per turn; the SAR-E router reaches it via `delegate_to_specialist("performance_forecasting", …)` — no `dispatch_to_performance_forecasting()` is generated. Both code paths must honor `response_schema` — confirm at SE-PRD-05 kickoff if not already plumbed. | [`../agentic-harness/projects/AH-PRD-02-agent-factory.md`](../agentic-harness/projects/AH-PRD-02-agent-factory.md), [`../agentic-harness/projects/AH-PRD-09-per-turn-dispatch.md`](../agentic-harness/projects/AH-PRD-09-per-turn-dispatch.md) |
| **Integrations (IN-PRD-02+)** | Consumed (read-only) via `/internal/integrations/{account_id}/connections` for `/config/status` joins and the KPI source-job platform check. No OAuth coupling — Data Pipeline does the extraction. | [`../integrations/README.md`](../integrations/README.md) (if present) |
| Python deps: `statsmodels >= 0.14.0,<0.15.0` | SE-PRD-03. Pinned because `VAR.ma_rep` + `select_order` APIs shift across minor versions. | `api/pyproject.toml` |
| `@safe_weave_op` + Weave span helpers | `app/adk/tracking/` — used for `sar_e.var_retrain`, `sar_e.scenarios.compute`, `sar_e.target_derivation`. |
| Google Cloud Firestore — transactional writes | `api/src/kene_api/firestore.py`. Used for `/config/setup` atomicity, funnel-mapping version bumps, target supersede. |

### 3.2 Depended On By

| Component | Dependency |
|-----------|------------|
| **Performance (PE-PRDs 01–08)** | **Primary consumer.** Every Performance tab reads a SAR-E surface: Analysis (funnel + trendline + cost-rollup + related-metrics), Simulations (baseline + scenarios + derive + targets persist), Targets (list + single-target drill-down), Diagnostics (baseline confidence + IRF status + retrain-needed flag), Configuration (mapping + thresholds + channel-coverage CRUD + status + wizard trigger). The setup wizard (PE-PRD-05) calls `/config/backfill-plan` + `/config/setup` + polls `/config/status` for completion. |
| **Dashboards (DB-PRDs 01–04)** | Dashboards' LineChart widget (DB-PRD-03) is the renderer for Analysis's 53-week trendline per PE-PRD-02's wiring. The Simulations tab's composite chart is a separate Recharts wrapper owned by PE-PRD-03 (the widget contract doesn't support overlaid baseline / target / scenario axes). |
| **Knowledge Graph (future)** | Out of scope for v1; noted in implementation-plan §5.6. Baseline + Target snapshots could become dated `Observation` nodes for cross-session recall. |

## 4. Design System References

SAR-E is a backend component; it renders nothing. The Performance component (PE-PRDs 01–08) is the design-system consumer. Reference these only when authoring a SAR-E API surface that must align with a Performance visualization:

| Document | Sections | When to Read |
|----------|----------|--------------|
| [`../performance/README.md`](../performance/README.md) (if present; else `../performance/implementation-plan.md`) | Analysis tab + Simulations tab visualization contracts | When shipping a new analytical endpoint or changing the shape of an existing one — confirm the frontend's bundle / chart expectations still hold. |
| `docs/figma-export/src/app/pages/performance/` | Analysis / Simulations / Configuration / Targets / Diagnostics sections | Reference UX only — rebuild against Soft Maximalism; not a SAR-E deliverable. |

## 5. Project Index

The component's work is split across **7 independently shippable project PRDs** under [`projects/`](./projects/). The split follows a strict dependency chain: a config foundation unblocks ingestion; ingestion unblocks VAR; VAR unblocks IRF; VAR + IRF + factory unblock the specialist; everything unblocks the analytical query layer; and a closeout PRD validates composition. Each PRD publishes a contract up front so downstream teams can stub + test in parallel.

### 5.1 Dependency graph

```
┌─────────────────────────┐   ┌────────────────────────┐   ┌───────────────────┐   ┌───────────────────┐
│     DM-PRD-00/07        │   │      PR-PRD-08         │   │     AH-PRD-02     │   │  A-PRDs 01–04     │
│  (migration + audit)    │   │  (Campaign + objective)│   │  (agent factory)  │   │ (automations      │
│                         │   │                        │   │                   │   │  platform)        │
└────────────┬────────────┘   └───────────┬────────────┘   └─────────┬─────────┘   └─────────┬─────────┘
             │                             │                         │                       │
             └──────────┬──────────────────┘                         │                       │
                        ▼                                            │                       │
              ┌───────────────────┐◄────────────────────────────────────────────────────────┤
              │     SE-PRD-01     │  Configuration foundation        │                       │
              │                   │  (needs A-PRD-01: ProjectPlan +  │                       │
              │                   │   PlanRun model for stub seeder) │                       │
              └─────────┬─────────┘                                  │                       │
                        │                                            │                       │
                        ▼                                            │                       │
              ┌───────────────────┐    ┌──────────────────────┐      │                       │
              │     SE-PRD-02     │◄───│  DP-PRDs 01 + 02 + 03│      │ (sar_e_ingestion      │
              │  Weekly ingestion │    │                      │      │  glue agent;          │
              │                   │◄───────────────────────────────── │  is_system plan;     │
              │                   │◄────────────────────────────────────────────────────────┤
              └─────────┬─────────┘    └──────────────────────┘      │  artifact system;     │
                        │                                            │  test-mode honoring)  │
                        ▼                                            │                       │
              ┌───────────────────┐                                  │                       │
              │     SE-PRD-03     │  VAR + 12-week baseline          │ (sar_e_retrain glue   │
              │                   │◄───────────────────────────────── │  agent; weekly       │
              │                   │◄──────────────────────────────────────── (A-PRDs 01–02)  │
              └─────────┬─────────┘                                  │   recurring plan)     │
                        │                                            │                       │
                        ▼                                            │                       │
              ┌───────────────────┐                                  │                       │
              │     SE-PRD-04     │  IRF + scenarios                 │                       │
              └─────────┬─────────┘                                  │                       │
                        │                                            │                       │
                        ▼                                            │                       │
              ┌───────────────────┐◄─────────────────────────────────┘                       │
              │     SE-PRD-05     │  Target derivation specialist                            │
              │                   │  (needs AH-PRD-02 + response_schema field)               │
              └─────────┬─────────┘                                                          │
                        │                                                                    │
                        ▼                                                                    │
              ┌───────────────────┐                                                          │
              │     SE-PRD-06     │  Analytical query layer                                  │
              └─────────┬─────────┘    (consumes PR-PRD-07 + 08)                             │
                        │                                                                    │
                        ▼                                                                    │
              ┌───────────────────┐                                                          │
              │     SE-PRD-07     │  Integration testing + polish                            │
              └───────────────────┘                                                          │
```

### 5.2 Projects

| # | Project PRD | Owner team | Blocked by | Parallel with | Est. |
|---|-------------|------------|------------|---------------|------|
| 01 | [Configuration Foundation + Setup State](./projects/SE-PRD-01-configuration-foundation.md) | Backend (foundation) | DM-PRD-00, DM-PRD-07, PR-PRD-08, A-PRD-01 | — | 4 days |
| 02 | [Weekly KPI Ingestion + Backfill Plan](./projects/SE-PRD-02-weekly-kpi-ingestion.md) | Backend | SE-PRD-01, DP-PRDs 01 + 02 + 03, AH-PRD-02, A-PRDs 01–04 | — | 4 days |
| 03 | [VAR Model + 12-Week Baseline Forecast](./projects/SE-PRD-03-var-baseline.md) | Backend / applied stats | SE-PRD-02, AH-PRD-02, A-PRDs 01–02 | — | 4 days |
| 04 | [Scenario Propagation (IRF)](./projects/SE-PRD-04-irf-scenarios.md) | Backend / applied stats | SE-PRD-03 | 05 | 3 days |
| 05 | [Target Derivation Specialist](./projects/SE-PRD-05-target-derivation-specialist.md) | Backend + Agentic Harness liaison | SE-PRD-03, SE-PRD-04, AH-PRD-02 | 04 (partial) | 4 days |
| 06 | [Analytical Query Layer](./projects/SE-PRD-06-analytical-query-layer.md) | Backend | SE-PRDs 01 + 02 + 03, PR-PRDs 07 + 08 | 04, 05 | 4 days |
| 07 | [Integration Testing & Polish](./projects/SE-PRD-07-integration-testing-and-polish.md) | Backend + QA | SE-PRDs 01–06 | — | 3 days |

**Total effort:** ~26 engineer-days. The chain is mostly serial (01 → 02 → 03 → 04 → 05 → 06 → 07); only 04 + 05 + 06 have meaningful parallelism.

### 5.3 Recommended workflow

1. **Sprint 1 (foundation).** Backend ships SE-PRD-01. Other teams stub against the published Pydantic schemas.
2. **Sprint 2 (ingestion).** SE-PRD-02 lands once DP-PRDs 01 + 02 + 03 are merged. `POST /config/backfill-plan` + the real automation task graph turn on.
3. **Sprint 3 (VAR).** SE-PRD-03 lands. `/forecasts/baseline` serves reads; weekly retrain is chained into the existing ingestion automation.
4. **Sprint 4 (parallel build).** SE-PRD-04 (applied-stats engineer), SE-PRD-05 (specialist — pair backend + Agentic Harness), and SE-PRD-06 (analytical query layer — backend) can all start once SE-PRD-03 is in review; each consumes the baseline as a finalized contract. SE-PRD-04 blocks SE-PRD-05 only at the "specialist uses `/scenarios` as a tool" future-work boundary — v1 does not wire scenarios into the specialist, so they can be truly parallel.
5. **Sprint 5 (close-out).** SE-PRD-07 runs the 8-milestone E2E, load tests, methodology audit, A/B harness, and appends a verification report to this README.

### 5.4 Cross-PRD coordination points

- **Automation task-graph extension (SE-PRD-01 → SE-PRD-02 → SE-PRD-03).** SE-PRD-01 ships `sar_e_automation_seeder` with **stub** `create_weekly_ingestion_automation` + `trigger_one_shot_backfill` functions. SE-PRD-02 replaces the stubs with the real ingestion graph + backfill plan. SE-PRD-03 extends the ingestion plan's final task to include the `sar_e_retrain` glue agent. Each PRD owns its slice but they land additively — PR reviews should chain via stacked branches when possible.
- **Channel-coverage asymmetry (SE-PRD-03 ↔ SE-PRD-06).** The `ChannelCoverage` matrix is the single source of truth; VAR training excludes flagged channels (SE-PRD-03) and cost-rollup includes them (SE-PRD-06). The paired assertion — `Baseline.training_inputs.excluded_channels` supersets `under_covered_channels` AND `/analytics/cost-rollup` returns cells for those same channels — is an integration test in SE-PRD-06 (§7 AC-10). When either side changes, rerun the test.
- **Channel-exclusion at matrix level (v1 limitation).** Per SE-PRD-03 §5.2, under-covered channels are *traced* in `Baseline.training_inputs.excluded_channels` but not *enforced* at training-matrix level in v1. Because `KPIDataPoint` is channel-indifferent, exclusion would require extending SE-PRD-02's ingestion to emit per-channel rows. Documented as v1.1 follow-up; the training-inputs field is populated correctly from day one.
- **Specialist `response_schema` + factory plumbing (SE-PRD-05 ↔ AH-PRD-02).** Confirm at SE-PRD-05 kickoff that AH-PRD-02's factory supports `response_schema` declarations in `agent_configs/*` docs. If not, file an issue — AH-PRD-02 plumbs it through; this PRD does not ship a factory extension.
- **Supersede contract → PATCH stability (SE-PRD-05 ↔ PE-PRD-06).** `PATCH /targets/{target_id}` returns a new `target_id` (because supersede hard-deletes and writes fresh). PE-PRD-06's Targets-tab drill-down refetches by the new id. If the UI hits friction, revisit the in-place-update vs. supersede-with-new-id trade-off.
- **Performance wizard coordination (SE-PRDs 01 + 02 ↔ PE-PRD-05).** PE-PRD-05 specifies a new upstream endpoint `POST /config/backfill-plan` (owned by SE-PRD-02). The contract is written in the PE-PRD-05 body; SE-PRD-02 owns the implementation. File an upstream issue at PE-PRD-05 kickoff to confirm the ordering.
- **Performance API bundle endpoints (PE-PRD-01 ↔ SAR-E reads).** PE-PRD-01 publishes `/performance/{account_id}/analysis`, `/simulations`, `/targets`, `/diagnostics`, `/configuration` bundle endpoints that compose SAR-E reads into one request. SAR-E does not own those bundles; changes to SAR-E response shapes require a coordinated PR to the Performance bundle implementations.

## 6. Global Document References

| Document | Relevant Sections | Why |
|----------|-------------------|-----|
| [`./implementation-plan.md`](./implementation-plan.md) | Entire document; especially §3 (Data model), §5 (Interaction with existing components), §10 (Resolved decisions) | Authoritative source for v1 scope decisions (weekly-only granularity, 12-week horizon, opt-in via wizard, supersede-on-edit for targets, split channel-coverage semantics). |
| [`../performance/implementation-plan.md`](../performance/implementation-plan.md) | §2 (Scope), §5 (Interaction), §10 (Open questions) | Performance is the primary consumer; the wizard flow + Configuration / Simulations / Analysis tabs live there. |
| [`../data-management/README.md`](../data-management/README.md) | §2 (Architecture), §5.3 (composite-index registry) | Shape B path convention that all nine SAR-E Firestore collections follow; index registry the four SAR-E-specific composites live under. |
| [`../automations/README.md`](../automations/README.md) | §2 (Architecture), §7 (`is_system` semantics, `inputs`, `triggered_by`) | SAR-E's weekly ingestion + retrain rides as an `is_system=true` plan. Understanding the platform is prerequisite for SE-PRDs 02 + 03. |
| [`../agentic-harness/README.md`](../agentic-harness/README.md) | §2 (Architecture), §2.4 (Key Abstractions), §2.5 (routing) | Factory construction pattern for `performance_forecasting` (SE-PRD-05) and the `sar_e_ingestion` / `sar_e_retrain` glue agents (SE-PRDs 02 + 03). |
| `docs/KEN-E-System-Architecture.md` | §1.6 (Component Landscape), §4 (Tool taxonomy), §10 (Infrastructure) | Cross-component orientation + ADK tool conventions the specialist tools follow. |
| `docs/KEN-E-Self-Improving-Evaluation-Framework-Design.md` | MER-E scoring + feedback loops | Context for the methodology-note invariant — MER-E surfaces adherence as a scoring signal. Relevant when tuning the specialist's prompts. |
| `docs/trace-structure-spec.md` | Weave span catalog | Format for `sar_e.var_retrain`, `sar_e.scenarios.compute`, `sar_e.target_derivation`, `sar_e.ingest` spans. |
| [`../../DESIGN-REVIEW-LOG.md`](../../DESIGN-REVIEW-LOG.md) | 2026-04-23 entry (if added when SAR-E ships) | Revision history for cross-component SAR-E decisions (weekly-only, wizard-gated enablement, etc.). |
| statsmodels VAR docs: https://www.statsmodels.org/stable/vector_ar.html | `VAR.fit`, `VAR.select_order`, `VARResults.ma_rep`, `VARResults.forecast_interval` | Reference when implementing SE-PRDs 03 + 04. Not fetched at runtime. |

## 7. Conventions and Constraints

### Data model

- **Opt-in gate.** Every public SAR-E endpoint checks `SarEConfig.enabled=true` and returns an empty-shape response on `false`. Internal endpoints (`/internal/sar-e/*`) check the same — a scheduled retrain on a disabled account is a no-op that returns `outcome="skipped_disabled"` in ≤50ms.
- **Weekly-only granularity.** The VAR model, baselines, targets, IRF, and every analytical query operate on weekly data. Daily rows are never persisted in SAR-E; they exist only as Data Pipeline artifacts read transiently during ingestion.
- **12-week horizon.** Hardcoded in v1. `SarEConfig.forecast_horizon_weeks=12` is a forward-compat field; reading a non-12 value is a runtime assertion failure in the current code.
- **ISO week in UTC.** `week_start` is always the Monday of the ISO week in UTC. Timezone-aware downstream UX is PE-PRD-02's concern; SAR-E is UTC-only internally.
- **Partial-week semantics.** `KPIDataPoint.is_partial=true` marks the in-progress ISO week; the VAR trainer filters these out, trendlines include them with a visual marker. Overwritten atomically when the week completes (same compound doc id `{kpi_id}__{week_start_iso}`).
- **Funnel mapping has history; targets do not.** `FunnelMappingHistory` retains every version for per-week resolution during analytical queries. `Target` supersede-on-edit hard-deletes the prior row. The asymmetry is intentional — mapping changes alter interpretation of historical data; target changes do not.
- **No global KPI catalog.** Every `EffectivenessKPI` is per-account and tied to a specific `DataPipelineJob` via `source_job_id`. A KPI can only be created when an underlying job is available for a connected integration.

### Firestore layout (Shape B)

All paths are under `accounts/{account_id}/…`:

- `sar_e_config` — single doc per account (SE-PRD-01)
- `effectiveness_kpis/{kpi_id}` — per-account KPI definitions (SE-PRD-01)
- `funnel_mapping` — current mapping (SE-PRD-01)
- `funnel_mapping_history/{version}` — version audit trail (SE-PRD-01)
- `thresholds/{kpi_id}` — per-KPI bounds (SE-PRD-01)
- `channel_coverage` — matrix (SE-PRDs 01 + 02 + 06)
- `kpi_time_series/{kpi_id}__{week_start_iso}` — weekly time-series rows (SE-PRD-02)
- `baselines/{kpi_id}` — most recent baseline (SE-PRD-03)
- `irf_coefficients/{model_version}` — MA snapshot, latest-4 retention (SE-PRD-04)
- `targets/{target_id}` — active + soft-deleted targets (SE-PRD-05)

Plus one global config doc:

- `config/sar_e_model_ab` — A/B harness configuration (SE-PRD-07); super-admin-writable

All collections registered in `api/src/_migrate_shape_b/resources.py`. Covered by DM-PRD-05's `recursive_delete` on account deletion once it ships (interim: each PRD extends the enumerated sweep in `routers/accounts.py:968-997`).

### Composite indexes (Terraform)

Four SAR-E-specific composites in `deployment/terraform/firestore-indexes.tf`:

- `effectiveness_kpis`: `(is_active ASC, display_name ASC)` — Configuration tab dropdown
- `funnel_mapping_history`: `(version DESC)` — history drawer
- `kpi_time_series` (collection-group): `(kpi_id ASC, week_start ASC)` + `(kpi_id ASC, is_partial ASC, week_start ASC)` — VAR training + trendline queries
- `targets`: `(kpi_id ASC, period.start ASC, is_active ASC)` — Targets tab list

Plus two Project-Tasks composites SE-PRD-06 requires on `plans.tasks` collection-group: `(campaign_id ASC, week ASC)` and `(channel ASC, week ASC)`.

### API conventions

- All user-facing endpoints live under `/api/v1/sar-e/{account_id}/`. Internal endpoints (called by glue agents in the weekly automation) live under `/api/v1/internal/sar-e/`.
- Role gating (DM-PRD-07): reads require `viewer`; most mutations require `editor`; `/config/setup` requires `admin` (kicks off backfill with cost implications).
- Idempotency: `/internal/sar-e/ingest-kpi-series` is idempotent via compound doc id; `/targets/derive` is idempotent via `derivation_context_hash` + 10-min cache; `/config/funnel-mapping PUT` with a no-op diff returns `304 Not Modified`.
- OIDC on internal endpoints. `/ingest-kpi-series` + `/retrain-var` require service-principal tokens minted for the `sar_e_ingestion` / `sar_e_retrain` glue agents.
- Cache-Control: `/forecasts/baseline` returns `max-age=30`; `/analytics/funnel` + `/trendline` return `max-age=300`; cost-rollup + scenarios return `max-age=0, must-revalidate`.

### Statistical invariant — "association only"

- **Specialist prompt** (SE-PRD-05) forbids causation language; allowed phrasings: "associated with", "correlated with", "historically coincided with", "tends to co-occur with".
- **Response schema** requires a `methodology_note` field on every `DerivedTarget` + at the response level.
- **Runtime lint** on specialist output checks against a banned-phrase regex; 2-retry then fail-with-fallback.
- **CI lint gate** (SE-PRD-07) scans every `sar_e_*` router / service / model file for the banned phrases and fails `make lint` on a hit. Allowlist file handles documented exceptions.

### Specialist (SE-PRD-05)

- Model: `gemini-2.0-pro`, temperature `0.2`, `response_schema=DerivedTargetsResponse`, resolved per turn by `specialist_runtime.resolve_agent` (AH-PRD-09 Phase 2) from `agent_configs/performance_forecasting`; the SAR-E router reaches it via `delegate_to_specialist("performance_forecasting", …)`.
- Tools are local function tools (not MCP): `get_baseline`, `get_calendar_summary` (includes `holiday` / `promotion` / `event` calendar categories), `get_historical_pulses`, advisory `save_targets`.
- `derivation_context_hash = sha256(baseline + calendar + pulses)` is the idempotency key. 10-min in-process LRU.
- A/B harness (SE-PRD-07) routes a configurable % of requests to a challenger model (`gemini-2.0-flash` initially) via sticky bucketing on `(account_id, context_hash)`. Shadow mode logs to Weave without blocking; active mode returns challenger output to routed traffic. Per-account `ab_harness_opt_out` honored.

### VAR (SE-PRD-03)

- `VAREstimator` wraps statsmodels `VAR` on `log1p`-transformed weekly series. AIC lag selection. Min training: 26 weeks (below → `FlatBaselineModel`). Max lag: 8 weeks.
- `Baseline.confidence_level`: `<26 → "low"`, `26–52 → "medium"`, `>52 → "high"`.
- `Baseline.model_version = "var-p{lag}-{YYYY-MM-DD}"`. Flat: `"flat-{YYYY-MM-DD}"`.
- Ad-hoc retrain: `curl POST /internal/sar-e/retrain-var` with OIDC for `sar_e_retrain` agent. Weekly retrain is wired as the final task of the ingestion automation; ad-hoc is an operational action documented in `api/CLAUDE.md` (SE-PRD-07 runbook).

### IRF (SE-PRD-04)

- MA representation `(horizon+1, 4, 4)` computed once per retrain, persisted at `irf_coefficients/{model_version}` (latest 4 retained).
- Propagation: natural-scale overrides → log-space deltas → superposition via MA rep → `expm1` back to natural scale → non-negative clamp.
- Stateless `POST /scenarios`; no persistence. p99 ≤500ms @ 100 concurrent.

### Analytical queries (SE-PRD-06)

- **Historical mapping resolution.** `/analytics/trendline/{objective}` resolves the mapping per-week via `FunnelMappingHistory`; transitions surface in the response for UI marker rendering.
- **Channel-coverage split.** VAR training excludes flagged channels; cost rollup includes them. Single source of truth (the matrix); paired test locks the asymmetry.
- **Caching.** 5-min in-process LRU. Invalidated on mapping PUT, KPI CRUD, retrain, target save (when `comparison=vs_target`).
- **Default trendline window:** 53 weeks (one year + 1 week for wow/yoy alignment). Max 156.

### Testing

- Unit tests colocated in `test_*.py` files (CLAUDE.md T-1). Integration tests under `api/tests/integration/`.
- E2E lifecycle test (SE-PRD-07) runs 8 milestones from account creation through analytical queries; session-scoped fixture; mocks at the Integrations / Data Pipeline / Gemini boundaries.
- Nightly Locust load test (SE-PRD-07) gates: `/scenarios` p99 ≤500ms, `/analytics/cost-rollup` p95 <500ms (500-task account), `/analytics/funnel` + `/trendline` p95 <100ms warm.
- Specialist evals: 20 golden cases under `tests/evals/performance_forecasting/` (SE-PRD-05). Gemini-live tests are `@pytest.mark.gemini` and skipped in fast CI; run nightly.
- `make lint` runs the methodology-language gate (SE-PRD-07).

### Standard shape for a project PRD in [`projects/`](./projects/)

Each PRD follows the 10-section structure used across the KEN-E components:

1. Context — problem this PRD solves
2. Scope — explicit in/out
3. Dependencies — other PRDs, files, services
4. Data contract — Pydantic / TypeScript types owned or consumed
5. Implementation outline — files to create / modify (table)
6. API contract — endpoints (where applicable)
7. Acceptance criteria — what "done" means
8. Test plan — unit / integration / E2E coverage
9. Risks & open questions
10. Reference — links back to sibling PRDs, parent plans, external docs

---

<!-- PRD MAINTENANCE NOTES

Updating this PRD:
- When a new feature-parent is created in Linear: add it to §5 Project Index
- When a feature-parent is completed: update its status in §5
- When architecture changes (new models, new services, new endpoints): update §2
- When a new cross-component dependency is introduced: update §3
- When the methodology lint's banned-phrase list expands (SE-PRD-07): update §7 "Statistical invariant"
- SE-PRD-07 will append a "Status: shipped" section at the top of §5.3 with a verification-report link once the full set ships. The verification report names: eval pass rate (SE-PRD-05 golden cases), load-test p99/p95 values, methodology-audit match count (0), and E2E lifecycle outcome (8/8 green).

This PRD is read by the Dev Team agent during implementation planning (CLAUDE.md §Context Loading Sequence, Step 3). Keep it concise — every sentence should help a dev write better code or avoid mistakes.
-->
