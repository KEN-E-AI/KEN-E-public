# Performance — Product Requirements Document

> **Linear Team:** [TBD] Performance
> **Last Updated:** 2026-04-23
> **Status:** Draft — 8 PRDs authored; implementation not yet started

## 1. Overview

Performance is KEN-E's **marketing-measurement page** — a five-tab surface (`Analysis`, `Simulations`, `Targets`, `Diagnostics`, `Configuration`) at `/performance` that shows how the business is expanding its conversion funnel, what its 12-week forecast looks like, which per-KPI Targets are in effect, and how healthy the forecasting model + ingestion pipeline are. The component also owns the four-step **Setup Wizard** at `/performance/setup` that turns an opted-out account into a fully configured SAR-E consumer.

Performance is deliberately **a frontend + thin orchestration layer, not an analytical engine.** All statistical computation — weekly VAR baselines, IRF scenario propagation, LLM-driven Target derivation, KPI time-series aggregation, cost rollups by dimension — lives in [SAR-E](../sar-e/README.md). Performance renders. The only backend surface owned here is a set of five composite read endpoints (`/api/v1/performance/{account_id}/{analysis,simulations,targets,diagnostics,configuration}`) that bundle SAR-E + Project-Tasks data for a single page load, plus a `POST /simulations/run` orchestration endpoint that fans out to SAR-E `/scenarios` + `/targets/derive`, and the three wizard-draft CRUD endpoints that persist mid-flow state.

Performance is **opt-in per account.** SAR-E is disabled at account creation. Pre-wizard, only the Configuration tab is visible in the nav (the other four are hidden by `ForecastingEnabledGate`) and it renders an empty-state CTA pointing at the wizard; `/performance` redirects to `/performance/configuration`. Post-wizard, SAR-E's `/config/status` flips to `enabled=true`, all five tabs appear, and `/performance` redirects to `/performance/analysis`. A developer reading only this section should understand: this component owns the `/performance` page shell, the five tab UIs, the setup wizard, five composite BFF endpoints, a `performance_wizard_draft` Firestore doc, and the Figma-export-to-production terminology rename (`Goal` → `Target`). It does **not** own forecasting, target persistence, analytical queries, KPI ingestion, or the OAuth connection UI.

## 2. Architecture

```
┌──────────────────────────┐   ┌──────────────────────────┐   ┌──────────────────────────┐
│   Integrations (IN-*)    │   │   Project Tasks (PR-*)   │   │   Dashboards (DB-*)      │
│   - /settings/integr.    │   │   - Calendar activities  │   │   - LineChart widget     │
│     (wizard deep-link)   │   │   - Campaign roster      │   │     (53-week trendline)  │
└───────────┬──────────────┘   └───────────┬──────────────┘   └───────────┬──────────────┘
            │                              │                              │
            │                              │                              │
            ▼                              ▼                              ▼
     ┌────────────────────────────────────────────────────────────────────────┐
     │   Performance Page (PE-PRD-01)                                         │
     │   /performance/{analysis,simulations,targets,diagnostics,              │
     │                 configuration,setup}                                   │
     │   PerformanceDateRangeContext · ForecastingEnabledGate · useTargets    │
     └──────────────────┬──────────────────────────────────────┬──────────────┘
                        │                                      │
                        ▼                                      ▼
           ┌──────────────────────────┐         ┌──────────────────────────────┐
           │  Performance BFF         │         │   Setup Wizard (PE-PRD-05)   │
           │  routers/performance.py  │         │   /performance/setup         │
           │                          │         │   4 steps · wizard-draft     │
           │  /analysis               │         │                              │
           │  /simulations            │         │   GET/PUT/DELETE             │
           │  /targets                │         │   /performance/.../           │
           │  /diagnostics            │         │     wizard-draft             │
           │  /configuration          │         └──────────────┬───────────────┘
           │  /simulations/run        │                        │
           └──────────────┬───────────┘                        │
                          │                                    │
                          │ composes                           │ calls
                          ▼                                    ▼
     ┌─────────────────────────────────────────────────────────────────────────┐
     │   SAR-E (SE-PRD-*)  —  /sar-e/{account_id}/...                          │
     │   /config/status     /config/setup         /config/funnel-mapping       │
     │   /config/thresholds /config/channel-cov.  /config/effectiveness-kpis   │
     │   /config/backfill-plan                                                 │
     │   /forecasts/baseline /scenarios           /targets  /targets/derive    │
     │   /analytics/funnel  /analytics/trendline  /analytics/cost-rollup       │
     │   /analytics/related-metrics                                            │
     └─────────────────────────────────────────────────────────────────────────┘
                          │
                          │ (parallel reads during bundle composition)
                          ▼
     ┌─────────────────────────────────────────────────────────────────────────┐
     │   Project Tasks  —  /plans/{account_id}?category=holiday|promotion|event│
     │   Data Pipeline  —  ingestion-status query (Diagnostics tab)            │
     └─────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Key Directories

Performance is primarily a frontend component; the backend is a thin BFF layer. Paths below are the authoritative home for each file type.

| Path | Purpose |
|------|---------|
| `frontend/src/pages/Performance/PerformancePage.tsx` | Page shell, five-tab router, default-route redirect logic. PE-PRD-01. |
| `frontend/src/pages/Performance/{Analysis,Simulations,Targets,Diagnostics,Configuration}Tab.tsx` | One file per tab; each replaces a PE-PRD-01 placeholder. PE-PRDs 02 / 03 / 06 / 07 / 04. |
| `frontend/src/pages/Performance/SetupWizard/` | Setup wizard route tree (`/performance/setup` + four step components). PE-PRD-05. |
| `frontend/src/components/performance/ForecastingEnabledGate.tsx` | Reads SAR-E `/config/status`; hides Analysis / Simulations / Targets / Diagnostics pre-wizard. PE-PRD-01. |
| `frontend/src/components/performance/ConfigurationEmptyState.tsx` | Pre-wizard CTA + "Resume setup" banner variant. PE-PRD-01 + PE-PRD-04. |
| `frontend/src/components/performance/FunnelVisualization.tsx` | 4-stage CSS clip-path funnel. PE-PRD-02. |
| `frontend/src/components/performance/AnalysisTrendline.tsx` | Adapter around Dashboards' LineChart widget (DB-PRD-03) for 53-week trendlines. PE-PRD-02. |
| `frontend/src/components/performance/CostRollupChipRail.tsx` | Single-dimension cost chips (channel \| campaign \| platform \| owner). PE-PRD-02. |
| `frontend/src/components/performance/ExternalFactorsPanel.tsx` | Reads project-tasks Calendar directly (not via SAR-E). PE-PRD-02. |
| `frontend/src/components/performance/BaselineVsTargetChart.tsx` | Recharts `ComposedChart` wrapper — composed axes the Dashboards widget doesn't cover. PE-PRD-03. |
| `frontend/src/components/performance/config/FunnelStageMappingEditor.tsx` | 4-row Objective → KPI editor. Reused by the setup wizard's Step 2. PE-PRD-04 (+ consumed by PE-PRD-05). |
| `frontend/src/components/performance/wizard/` | Wizard-only primitives (`WizardStepper`, per-step forms, draft-resume banner). PE-PRD-05. |
| `frontend/src/contexts/PerformanceDateRangeContext.tsx` | Week-indexed `period` + `comparisonMode`; persisted to `sessionStorage` per-account. PE-PRD-01. |
| `frontend/src/hooks/useTargets.ts` | Typed wrapper around SAR-E `/targets`; scaffolded in PE-PRD-01, wired live by PE-PRD-06. |
| `frontend/src/hooks/useAnalysisBundle.ts` / `useSimulations.ts` / `useTargetsTab.ts` / `useDiagnosticsTab.ts` / `useConfiguration.ts` | One TanStack Query hook per bundle endpoint. PE-PRDs 02 / 03 / 06 / 07 / 04. |
| `frontend/src/hooks/useExternalFactors.ts` | Direct Calendar read (bypasses SAR-E). PE-PRD-02. |
| `frontend/src/services/performanceApi.ts` | Axios client boundary for every bundle call + the run endpoint + wizard-draft CRUD. PE-PRD-01 + extensions in each tab PRD. |
| `frontend/src/types/performance.ts` | Branded types: `FunnelObjective`, `EffectivenessKPIId`, `ComparisonMode`, `CostDimension`, `WizardStep`, `TargetId`, `WeekStartISO`, `SimulationRunId`, `ModelVersion`. PE-PRD-01 + additive extensions. |
| `frontend/src/lib/featureFlags/registry.ts` | Six flag keys registered here: `performance_{analysis,simulations,targets,diagnostics,configuration}_tab` + `performance_setup_wizard`. PE-PRD-01. |
| `api/src/kene_api/routers/performance.py` | Five bundle endpoints + `/simulations/run` + three wizard-draft CRUD endpoints. PE-PRD-01 (scaffold) + extensions per tab PRD. |
| `api/src/kene_api/services/performance_bundle_composer.py` | Parallel-fanout service that assembles each bundle from SAR-E + Project-Tasks reads. PE-PRD-01 (stub) + extensions per tab PRD. |
| `api/src/kene_api/services/performance_simulation_orchestrator.py` | Sequences SAR-E `/scenarios` → `/targets/derive` behind `POST /performance/.../simulations/run`. PE-PRD-03. |
| `api/src/kene_api/models/performance_models.py` | `AnalysisBundle` / `SimulationsBundle` / `TargetsBundle` / `DiagnosticsBundle` / `ConfigurationBundle` / `SimulationRunResult` Pydantic composites. Tab-specific PRDs each extend. |
| `api/src/kene_api/models/performance_wizard_models.py` | `PerformanceWizardDraft` + `WizardKPISelection` + `BackfillPlan`. PE-PRD-05. |
| `frontend/e2e/performance-*.spec.ts` | Playwright specs: `performance-shell.spec.ts` (PE-PRD-01), plus one per tab + wizard + integration suite in PE-PRD-08. |
| `frontend/.eslintrc.*` | `no-restricted-syntax` rule forbidding `useGoals` / `GoalsContext` / `setForecastAsGoals` inside `pages/Performance*` + `components/performance/**`. PE-PRD-03. |

Legacy `frontend/src/pages/Performance.tsx` is **deleted** by PE-PRD-01; the Figma-export stubs under `docs/figma-export/src/app/pages/performance/` are reference-only (rebuild against Soft Maximalism; not imported).

### 2.2 Data Flow

1. **New account landing.** On `GET /performance`, the shell reads SAR-E `/config/status` via `ForecastingEnabledGate`. When `enabled=false`, the gate hides the four non-Configuration tabs from the nav and `/performance` redirects to `/performance/configuration`, which renders an empty-state CTA pointing at `/performance/setup`.
2. **Setup wizard (PE-PRD-05).** The wizard opens at `/performance/setup` with URL-backed step state (`?step=welcome|define_kpis|backfill_depth|review`). Step 1 routes to `/settings/integrations` if `connected_integrations` is empty and resumes from the `performance_wizard_draft` Firestore doc on return. Step 2 picks four KPIs from `available_kpi_sources` and maps each to a funnel Objective (reuses `<FunnelStageMappingEditor />` from PE-PRD-04). Step 3 calls `POST /sar-e/{account_id}/config/backfill-plan` and displays the computed equalized backfill depth (`min(104, min(per-source history))`). Step 4 submits `POST /sar-e/{account_id}/config/setup`, polls `/config/status` until `setup_wizard_completed=true`, and redirects to `/performance/analysis`.
3. **Enabled landing.** Once SAR-E is enabled, `/performance` redirects to `/performance/analysis`. `PerformanceDateRangeContext` initializes `period` to the current ISO week (Monday → Sunday UTC) and `comparisonMode` to `'wow'`, restoring from `sessionStorage` (key `perf.dateRange.{accountId}`) when present.
4. **Analysis tab (PE-PRD-02).** `useAnalysisBundle` fetches `GET /api/v1/performance/{account_id}/analysis?period=<>&comparison_mode=<>&dimension=<>`. The BFF fans out to SAR-E `/analytics/funnel`, `/analytics/trendline/*`, `/analytics/cost-rollup`, plus a direct Project-Tasks `/plans/?category=holiday|promotion|event` read for the External Factors panel. Related metrics lazy-load per stage on expand. The funnel renders 4 CSS clip-path polygons; trendlines render via Dashboards' LineChart widget (DB-PRD-03); the `is_partial=true` current week renders as a dashed segment.
5. **Simulations tab (PE-PRD-03).** `useSimulations` fetches the 12-week baseline + saved targets + calendar summary. "Run Simulation" POSTs `/api/v1/performance/{account_id}/simulations/run`; the BFF calls SAR-E `/scenarios` (IRF propagation) then `/targets/derive` (LLM specialist) and returns a `SimulationRunResult` with baseline + proposed targets + per-stage specialist reasoning. "Save Forecast as Targets" fires one `POST /sar-e/{account_id}/targets` per (KPI, week); SAR-E's supersede-on-edit semantics replace any conflicting prior target atomically.
6. **Targets tab (PE-PRD-06).** `useTargetsTab` fetches `GET /api/v1/performance/{account_id}/targets`, which joins SAR-E `/targets` list reads with the latest actuals-to-date from the KPI time series. Per-row drill-down fetches `GET /sar-e/{account_id}/targets/{target_id}` for the specialist's `reasoning` + `methodology_note`. The "Replace this target" shortcut deep-links to `/performance/simulations?replace_kpi={kpi_id}&replace_week={week_start_iso}` — PE-PRD-03 consumes those params, scrolls the Save-Forecast-as-Targets panel into view, and pre-selects the matching row.
7. **Diagnostics tab (PE-PRD-07).** `useDiagnosticsTab` fetches `GET /api/v1/performance/{account_id}/diagnostics` every 60s while visible; the BFF joins SAR-E model-health (baseline CI bands, IRF convergence, last-retrained-at, retrain-needed flag) with a Data Pipeline ingestion-status query (latest-week-ingested, gap counts, 53-week coverage, failed jobs). Read-only in v1.
8. **Configuration tab (PE-PRD-04).** Post-wizard, `useConfiguration` fetches the Configuration bundle and renders three editor panels (Funnel Stage Mapping, Thresholds, Channel Coverage). Saves fire **directly** to SAR-E (`PUT /sar-e/{account_id}/config/*`); the Configuration bundle is read-only. A mapping-save invalidates the Analysis / Simulations / Diagnostics bundle caches via `queryClient.invalidateQueries(['performance', ...])`.
9. **Wizard abandonment + resume.** Step transitions `PUT /api/v1/performance/{account_id}/wizard-draft`. Closing the tab leaves the draft; on return to `/performance`, the shell lands on Configuration and `ConfigurationEmptyState` renders the "Resume setup" banner variant when the draft exists. A Weave span `performance.setup_wizard` captures `{step, abandoned_at, elapsed_seconds, outcome}`.

### 2.3 API Contracts

**Owned endpoints** (all under `/api/v1/performance/{account_id}/`):

| Endpoint | Method | Owner PRD | Schema |
|----------|--------|-----------|--------|
| `/analysis?period&comparison_mode&dimension` | GET | PE-PRD-01 scaffold → PE-PRD-02 | `AnalysisBundle` — funnel + trendlines + cost rollup + external factors (optionally) + related metrics + period / comparison |
| `/simulations?horizon_weeks` | GET | PE-PRD-01 → PE-PRD-03 | `SimulationsBundle` — baseline + calendar summary + saved targets + horizon |
| `/simulations/run` | POST | PE-PRD-03 | `SimulationRunResult` — orchestrates SAR-E `/scenarios` + `/targets/derive` |
| `/targets` | GET | PE-PRD-01 → PE-PRD-06 | `TargetsBundle` — per (KPI, week) active Target joined with actuals-to-date |
| `/diagnostics` | GET | PE-PRD-01 → PE-PRD-07 | `DiagnosticsBundle` — SAR-E model health + Data Pipeline ingestion status + retrain-needed |
| `/configuration` | GET | PE-PRD-01 → PE-PRD-04 | `ConfigurationBundle` — mapping / thresholds / channel coverage / available KPIs + wizard prerequisites (`available_kpi_sources`, `connected_integrations`) |
| `/wizard-draft` | GET / PUT / DELETE | PE-PRD-05 | `PerformanceWizardDraft` — mid-flow state persistence |

Every bundle includes `forecasting_enabled: bool` at the top level so the frontend can short-circuit to the gated state without a second request. When `enabled=false`, every downstream field is `null`.

**Consumed endpoints** (not owned — do not duplicate):

| Endpoint | Owner | Purpose in Performance |
|----------|-------|------------------------|
| `GET /api/v1/sar-e/{account_id}/config/status` | SE-PRD-01 | `ForecastingEnabledGate` gate; also consumed by the bundle composer and wizard polling. Cache key `['sar-e', 'config-status', accountId]` (60s stale time). |
| `POST /api/v1/sar-e/{account_id}/config/setup` | SE-PRD-01 | Wizard Step 4 completion (called directly, not via BFF). |
| `POST /api/v1/sar-e/{account_id}/config/backfill-plan` | SE-PRD-02 | Wizard Step 3 backfill-depth probe. |
| `PUT /api/v1/sar-e/{account_id}/config/{funnel-mapping,thresholds,channel-coverage}` | SE-PRD-01 | Configuration tab editor saves (direct, not via BFF). |
| `POST /api/v1/sar-e/{account_id}/config/effectiveness-kpis` | SE-PRD-01 | Wizard Step 2 KPI creation. |
| `GET /api/v1/sar-e/{account_id}/forecasts/baseline` | SE-PRD-03 | Composed into `SimulationsBundle`. |
| `POST /api/v1/sar-e/{account_id}/scenarios` | SE-PRD-04 | Called by `POST /simulations/run` orchestrator. |
| `POST /api/v1/sar-e/{account_id}/targets/derive` | SE-PRD-05 | Called by `POST /simulations/run` orchestrator. |
| `POST/PATCH/DELETE /api/v1/sar-e/{account_id}/targets[/{target_id}]` | SE-PRD-05 | "Save Forecast as Targets" + Targets-tab drill-down / supersede. |
| `GET /api/v1/sar-e/{account_id}/analytics/{funnel,trendline,cost-rollup,related-metrics}` | SE-PRD-06 | Composed into `AnalysisBundle`; related-metrics also called lazily on stage expand. |
| `GET /api/v1/plans/{account_id}?category=holiday&category=promotion&category=event&from&to` | PR-PRD-07 | External Factors panel — **direct read, not via SAR-E**. |
| Data Pipeline ingestion-status query (path TBD at DP-PRD-01 kickoff) | DP-PRD-01 | Composed into `DiagnosticsBundle`. |

Schema source of truth: `api/src/kene_api/models/performance_models.py` + `performance_wizard_models.py` (Pydantic). TypeScript branded types + interface mirrors live in `frontend/src/types/performance.ts` and are additive per tab PRD.

### 2.4 Key Abstractions

| Abstraction | Path | Purpose |
|-------------|------|---------|
| `ForecastingEnabledGate` | `frontend/src/components/performance/ForecastingEnabledGate.tsx` | Reads SAR-E `/config/status` once per page mount (60s stale time); when `enabled=false`, hides Analysis / Simulations / Targets / Diagnostics from the tab nav and renders `ConfigurationEmptyState` under Configuration only. The single enablement surface for the component — per-tab empty-states are intentionally absent. |
| `PerformanceDateRangeContext` | `frontend/src/contexts/PerformanceDateRangeContext.tsx` | Shared week-indexed `period` + `comparisonMode` state across tabs. Always ISO-week-aligned (Monday UTC start). Persisted to `sessionStorage` keyed by `accountId`. Never aggregates weekly → monthly client-side. |
| `useTargets` | `frontend/src/hooks/useTargets.ts` | Typed wrapper around SAR-E `/targets`. Scaffolded in PE-PRD-01 as a no-op module boundary; PE-PRD-06 wires the live TanStack Query implementation. Downstream consumers (PE-PRD-02 `vs_target`, PE-PRD-03 Save-as-Targets) import from this path from day one. |
| Bundle composer | `api/src/kene_api/services/performance_bundle_composer.py` | Parallel-fanout service that assembles each bundle from SAR-E + Project-Tasks reads with `asyncio.gather`. Handles section-scoped errors (one failed SAR-E read returns a null section; other sections render). Short-circuits to all-nulls when `forecasting_enabled=false`. |
| Simulation orchestrator | `api/src/kene_api/services/performance_simulation_orchestrator.py` | Sequences SAR-E `/scenarios` (IRF) → `/targets/derive` (specialist) behind `POST /performance/.../simulations/run`. Returns a single `SimulationRunResult` so the frontend sees one user gesture. |
| `PerformanceWizardDraft` | `api/src/kene_api/models/performance_wizard_models.py` + `accounts/{account_id}/performance_wizard_draft` | Single-doc Firestore state for mid-wizard resume. Shape B convention. Owned by PE-PRD-05; read by PE-PRD-04 to render the "Resume setup" banner. |
| `AnalysisTrendline` adapter | `frontend/src/components/performance/AnalysisTrendline.tsx` | Shapes SAR-E's `TrendlineSeries` into the DB-PRD-03 LineChart widget's props. If the widget doesn't expose a dashed-segment prop, the adapter splits the series (complete weeks + partial tail as two adjacent series) to preserve the `is_partial` visual. |
| `BaselineVsTargetChart` | `frontend/src/components/performance/BaselineVsTargetChart.tsx` | Simulations-tab-owned Recharts `ComposedChart` wrapper — overlays baseline + target + scenario lines on a shared weekly x-axis with an optional secondary y-axis. The Dashboards LineChart widget doesn't cover composed axes; reuse is not possible here. |
| `FunnelStageMappingEditor` | `frontend/src/components/performance/config/FunnelStageMappingEditor.tsx` | The 4-row Objective → KPI selection primitive. Owned by PE-PRD-04; the setup wizard (PE-PRD-05) imports it with `showSaveButton={false}` + `showHistory={false}` as the Step 2 selection primitive. |
| `ConfigurationEmptyState` | `frontend/src/components/performance/ConfigurationEmptyState.tsx` | Pre-wizard CTA card; renders a "Resume setup" banner variant when `performance_wizard_draft` exists. Gated on the `performance_setup_wizard` flag — when off, label flips to "Setup unavailable" and the click target is inert (kill-switch path). |

## 3. Component Dependencies

### 3.1 Depends On

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[SAR-E](../sar-e/README.md)** | **Primary consumer relationship.** Every analytical view reads SAR-E. Every wizard step writes to SAR-E config. SE-PRD-01 (`/config/*` CRUD + setup + status), SE-PRD-02 (`/config/backfill-plan` for wizard Step 3), SE-PRD-03 (`/forecasts/baseline`), SE-PRD-04 (`/scenarios`), SE-PRD-05 (`/targets` + `/targets/derive`), SE-PRD-06 (`/analytics/*`). Contract-test each bundle endpoint against SAR-E's OpenAPI in CI (PE-PRD-08). | [`../sar-e/README.md`](../sar-e/README.md), [`../sar-e/implementation-plan.md`](../sar-e/implementation-plan.md) |
| **[Project Tasks](../project-tasks/README.md)** | PR-PRD-07 (Calendar Activities) — the Analysis tab's **External Factors panel reads `/plans/{account_id}?category=holiday&category=promotion&category=event` directly**, not via SAR-E. The category-discriminated `PlanTask` fields (`promotion_type`, `holiday_type`, `region`) are mapped client-side. PR-PRD-08 (Campaigns) supplies `Campaign.objective` for SAR-E's cost-rollup joins (indirect). Exogenous-event **editing** lives on the Calendar page — Performance removes the Figma Configuration tab's ExogenousEventsSection entirely. | [`../project-tasks/projects/PR-PRD-07-calendar-activities.md`](../project-tasks/projects/PR-PRD-07-calendar-activities.md) |
| **[Dashboards](../dashboards/README.md)** | DB-PRD-03 ships the LineChart widget used by the Analysis tab's 53-week trendlines. Ordering: Dashboards ships first. The Simulations tab's composed-axes chart does **not** use the Dashboards widget (composed axes exceed its contract) — PE-PRD-03 owns its own Recharts wrapper. | [`../dashboards/README.md`](../dashboards/README.md), [`../dashboards/projects/DB-PRD-03-dashboard-details-and-canvas.md`](../dashboards/projects/DB-PRD-03-dashboard-details-and-canvas.md) |
| **[Data Pipeline](../data-pipeline/README.md)** | DP-PRD-01 — the Diagnostics tab reads per-KPI ingestion freshness / gap counts / 53-week coverage / failed jobs via a new ingestion-status query built against `accounts/{account_id}/data_pipeline_runs/*`. PE-PRD-07's bundle composer consumes this read. | [`../data-pipeline/projects/DP-PRD-01-foundation.md`](../data-pipeline/projects/DP-PRD-01-foundation.md) |
| **[UI](../ui/README.md)** | UI-PRD-01 (Design System Foundation) supplies Soft Maximalism tokens, shadcn primitives, the global shell and sidebar slot. Performance registers as a new top-level nav entry. UI-PRD-07 (Performance Page redesign) is a **soft** dependency — this component's page shell **replaces** the legacy `Performance.tsx` entirely; UI-PRD-07's metric tiles + chart wrappers target legacy marketing data and are not consumed by the SAR-E-backed Performance page. | [`../ui/README.md`](../ui/README.md), [`../ui/projects/UI-PRD-01-design-system-foundation.md`](../ui/projects/UI-PRD-01-design-system-foundation.md), [`../ui/projects/UI-PRD-07-performance-page.md`](../ui/projects/UI-PRD-07-performance-page.md) |
| **[Feature Flags](../feature-flags/README.md)** | FF-PRD-03 publishes `FeatureFlagsProvider` + `useFeatureFlag(key)`. Six flag keys registered by PE-PRD-01: `performance_{analysis,simulations,targets,diagnostics,configuration}_tab` + `performance_setup_wizard`. Each tab is visibility-gated by its flag AND the enablement gate; the wizard flag is an independent kill-switch path. | [`../feature-flags/README.md`](../feature-flags/README.md), [`../feature-flags/projects/FF-PRD-03-frontend-sdk-and-e2e.md`](../feature-flags/projects/FF-PRD-03-frontend-sdk-and-e2e.md) |
| **[Integrations](../integrations/README.md)** | IN-PRD-03 (Connection Management UI) — the wizard's Step 1 deep-links to `/settings/integrations` when `connected_integrations` is empty and relies on IN-PRD-03's connection-confirmation UX to return cleanly. Performance does not call Integrations' APIs directly; connection summaries flow through SAR-E `/config/status`. | [`../integrations/projects/IN-PRD-03-connection-management-ui.md`](../integrations/projects/IN-PRD-03-connection-management-ui.md) |
| **[Data Management](../data-management/README.md)** | Shape B convention for the `accounts/{account_id}/performance_wizard_draft` doc. DM-PRD-00 migration-foundation registry picks up the new collection. DM-PRD-05 `recursive_delete` covers it on account deletion. DM-PRD-07 `require_role` + `write_audit` apply to wizard-draft mutations. | [`../data-management/README.md`](../data-management/README.md) §7 |
| External libraries | `recharts` (Simulations composed chart), `react-vega` (transitively via Dashboards widget). No new runtime libs introduced by Performance beyond what UI + Dashboards already ship. | `frontend/package.json` |

### 3.2 Depended On By

Performance sits at the top of the component graph — it is a rendering surface, not a platform. No other component depends on Performance's APIs in the current design.

| Component | Dependency |
|-----------|------------|
| Knowledge Graph (future) | Not yet wired. Performance's `performance_forecasting` specialist outputs (via SAR-E) may eventually surface in KG `Observation` nodes for cross-session recall. |
| Extensions (future) | Hypothetical — a `PerformanceOptimizerExtension` (referenced in UI-PRD-06) might deep-link into Performance. No code contract today. |

## 4. Design System References

| Document | Sections | When to Read |
|----------|----------|--------------|
| Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) | Performance page (all five tabs + wizard) | Starting any PE-PRD that ships a UI. Rebuild components against Soft Maximalism tokens — do not literally copy the Figma export. |
| `docs/figma-export/src/app/pages/performance/` | `SimulationsSection.tsx`, `ConfigurationSection.tsx`, `FunnelMappingEditor.tsx` | Reference UX only. **AnalysisSection.tsx and FunnelSection.tsx are not present** in the current export — rebuild from Figma designs at PE-PRD-02 kickoff. `SimulationsSection.tsx` is the **source of the Goal → Target rename targets** (lines 1578 / 1600 / 1603; `setForecastAsGoals`; `useGoals`; `GoalsContext`). |
| `docs/figma-export/src/app/pages/performance/PerformanceSetupWizard.tsx` (if present) | Entire file | Reference UX for PE-PRD-05. If absent, author fresh against Figma designs + the Stepper primitive (confirm availability at kickoff). |
| `frontend/CLAUDE.md` | CSS architecture, component library, branded-types convention | Before adding any new visual component. |
| `frontend/src/pages/workflows/AutomationDetailsPage.tsx` (A-PRD-06) | Task-graph + task-panel integration pattern | Reference when building the Simulations tab's per-stage expansion panel (similar accordion + reasoning-display pattern). |
| [`../agentic-harness/data-visualization.md`](../agentic-harness/data-visualization.md) | Vega-Lite artifact format, `create_visualization()` tool | Only relevant if extending the Dashboards LineChart widget the Analysis tab consumes — not a direct Performance deliverable. |

## 5. Project Index

The component's work is split across **8 independently shippable project PRDs** under [`projects/`](./projects/). PE-PRD-01 is the shell foundation; five tab PRDs (02 / 03 / 04 / 06 / 07) and the setup wizard (05) run largely in parallel once their upstream SAR-E + Dashboards + Data-Pipeline dependencies land; PE-PRD-08 closes out with end-to-end coverage and a verification report.

### 5.1 Dependency graph

```
Upstream components:
┌──────────────────────────────────────────────────────────────────┐
│  SE-PRDs 01 / 02 / 03 / 04 / 05 / 06  (SAR-E — every tab reads)  │
│  DB-PRD-03                            (LineChart widget)         │
│  DP-PRD-01                            (ingestion-status query)   │
│  PR-PRD-07                            (Calendar read)            │
│  IN-PRD-03                            (wizard deep-link target)  │
│  UI-PRD-01 + FF-PRD-03                (shell + flags)            │
└───────────────────────────────┬──────────────────────────────────┘
                                ▼
                   ┌──────────────────────────┐
                   │   PE-PRD-01              │
                   │   Page shell + routing   │
                   │   + shared state         │
                   └──┬────┬──────┬────┬────┬─┘
                      │    │      │    │    │
           ┌──────────┘    │      │    │    └──────────┐
           │               │      │    │               │
           ▼               ▼      ▼    ▼               ▼
   ┌──────────────┐  ┌─────────┐ ┌────────┐ ┌─────────┐ ┌──────────┐
   │  PE-PRD-02   │  │PE-PRD-03│ │PE-PRD-4│ │PE-PRD-06│ │PE-PRD-07 │
   │  Analysis    │  │Simulat. │ │Config  │ │Targets  │ │Diagnost. │
   └──────┬───────┘  └────┬────┘ └───┬────┘ └────┬────┘ └────┬─────┘
          │               │          │           │           │
          │               │          ▼           │           │
          │               │     ┌──────────┐     │           │
          │               │     │PE-PRD-05 │     │           │
          │               │     │Setup     │     │           │
          │               │     │Wizard    │     │           │
          │               │     └─────┬────┘     │           │
          │               │           │          │           │
          └───────────────┴───────────┴──────────┴───────────┘
                                      │
                                      ▼
                           ┌──────────────────────┐
                           │      PE-PRD-08       │
                           │  Integration testing │
                           │      & polish        │
                           └──────────────────────┘
```

### 5.2 Projects

| # | Project PRD | Owner team | Blocked by | Parallel with | Est. |
|---|-------------|------------|------------|---------------|------|
| 01 | [Page Shell, Routing & Shared State](./projects/PE-PRD-01-page-shell-and-routing.md) | Frontend (foundation) | UI-PRD-01, FF-PRD-03 | — | 1–2 days |
| 02 | [Analysis Tab](./projects/PE-PRD-02-analysis-tab.md) | Frontend | PE-PRD-01, SE-PRD-01, SE-PRD-06, DB-PRD-03, PR-PRD-07 | 03, 04, 05, 06, 07 | 4–5 days |
| 03 | [Simulations Tab](./projects/PE-PRD-03-simulations-tab.md) | Frontend | PE-PRD-01, SE-PRD-03, SE-PRD-04, SE-PRD-05 | 02, 04, 05, 06, 07 | 4 days |
| 04 | [Configuration Tab](./projects/PE-PRD-04-configuration-tab.md) | Frontend | PE-PRD-01, SE-PRD-01 | 02, 03, 06, 07 | 3 days |
| 05 | [Setup Wizard](./projects/PE-PRD-05-setup-wizard.md) | Frontend (+ one SAR-E backend line for `/config/backfill-plan`) | PE-PRD-01, PE-PRD-04, SE-PRD-01, SE-PRD-02, IN-PRD-03 | 02, 03, 06, 07 | 3–4 days |
| 06 | [Targets Tab](./projects/PE-PRD-06-targets-tab.md) | Frontend | PE-PRD-01, SE-PRD-05 | 02, 03, 04, 05, 07 | 2 days |
| 07 | [Diagnostics Tab](./projects/PE-PRD-07-diagnostics-tab.md) | Frontend | PE-PRD-01, SE-PRD-03, SE-PRD-04, SE-PRD-06, DP-PRD-01 | 02, 03, 04, 05, 06 | 2–3 days |
| 08 | [Integration Testing & Polish](./projects/PE-PRD-08-integration-testing.md) | QA + whichever team finishes first | PE-PRDs 02 / 03 / 04 / 05 / 06 / 07 | — | 2–3 days |

**Total effort:** ~22–27 engineer-days. After PE-PRD-01 lands, the five tabs + wizard are maximally parallel; the critical path runs PE-PRD-01 → (PE-PRD-03 or PE-PRD-05) → PE-PRD-08.

### 5.3 Recommended workflow

1. **Sprint 1 (foundation).** PE-PRD-01 lands. Five tab placeholders, routing, context, gate, feature flags, scaffolded `useTargets` all go live. No data flows yet.
2. **Sprint 2 (parallel build, first wave).** PE-PRD-04 (Configuration) and PE-PRD-02 (Analysis) land in parallel — Configuration provides `<FunnelStageMappingEditor />` that PE-PRD-05 reuses, Analysis uses the Dashboards LineChart widget (DB-PRD-03 must be shipped by now).
3. **Sprint 3 (parallel build, second wave).** PE-PRD-03 (Simulations — Goal → Target rename + ESLint guard), PE-PRD-05 (Setup Wizard — composes the editor from PE-PRD-04), PE-PRD-06 (Targets), PE-PRD-07 (Diagnostics) all land in parallel.
4. **Sprint 4 (close-out).** PE-PRD-08 runs the five E2E Playwright suites, the terminology-rename audit, the rendering-perf gates, the a11y audit, the SAR-E contract tests, and appends a verification report to this README.

### 5.4 Cross-PRD coordination points

- **`<FunnelStageMappingEditor />` reuse (PE-PRD-04 ↔ PE-PRD-05).** PE-PRD-04 ships the editor as a standalone component with a `showSaveButton` + `showHistory` prop contract. PE-PRD-05's Step 2 imports it directly with both off. If PE-PRD-05 starts before PE-PRD-04 lands, coordinate a stub component on a shared branch.
- **Targets tab ↔ Simulations tab deep-link handshake (PE-PRD-06 ↔ PE-PRD-03).** PE-PRD-06's "Replace this target" shortcut navigates to `/performance/simulations?replace_kpi={kpi_id}&replace_week={week_start_iso}`. PE-PRD-03 consumes those params on mount, scrolls the Save-Forecast-as-Targets panel into view, highlights the matching row, and strips the query params from the URL. Contract mirrored in both PRDs' §6.
- **`POST /sar-e/{account_id}/config/backfill-plan` (PE-PRD-05 ↔ SE-PRD-02).** This endpoint is **new** — introduced by PE-PRD-05's wizard Step 3 and delivered by SE-PRD-02. Contract specified in PE-PRD-05 §6; file an upstream issue at PE-PRD-05 kickoff to confirm SE-PRD-02 ordering.
- **Mapping-save cache invalidation (PE-PRD-04 ↔ PE-PRDs 02 / 03 / 07).** A funnel-mapping PUT must invalidate the Analysis / Simulations / Diagnostics TanStack Query caches (every trendline + baseline references the mapping). PE-PRD-01 registers the query keys; PE-PRD-04 wires `queryClient.invalidateQueries(['performance', ...])` after save.
- **Goal → Target rename (PE-PRD-03).** This is a one-time enforcement pass across the Performance surface. PE-PRD-03 renames every `useGoals` / `GoalsContext` / `setForecastAsGoals` / user-facing `Goals:` reference and adds the ESLint `no-restricted-syntax` guard. PE-PRD-08's grep audit is the final CI gate; it must return zero matches in `frontend/src/pages/Performance* frontend/src/components/performance`.
- **Dashboards LineChart widget contract (PE-PRD-02 ↔ DB-PRD-03).** If DB-PRD-03's exported widget doesn't expose a `partialKey` / dashed-segment prop, PE-PRD-02's `AnalysisTrendline` adapter splits the series into complete-weeks + partial-tail as two adjacent series. Either path renders identically. Confirm the widget's final prop surface at PE-PRD-02 kickoff.

## 6. Global Document References

| Document | Relevant Sections | Why |
|----------|-------------------|-----|
| [`./implementation-plan.md`](./implementation-plan.md) | Entire document; especially §2 (what exists), §3 (data model), §5 (component interaction), §6 (phasing), §10 (resolved decisions) | Authoritative source for v1 scope decisions: weekly-only granularity, opt-in via setup wizard, `Target` rename, single-dimension cost rollup, 53-week default trendline window, wizard UX home at dedicated route, supersede-on-edit semantics. |
| [`../sar-e/README.md`](../sar-e/README.md) | §2 (Architecture), §7 (Conventions) | Every Performance tab reads SAR-E. Understanding the opt-in gate, weekly-only granularity, `FunnelMappingHistory`, supersede-on-edit for targets, and the "statistical association only" invariant is prerequisite for every PE-PRD. |
| [`../dashboards/README.md`](../dashboards/README.md) | §2.4 (Key abstractions — widget renderers), §5 (Project Index — DB-PRD-03) | The LineChart widget the Analysis tab consumes ships from DB-PRD-03. Read before starting PE-PRD-02. |
| [`../project-tasks/README.md`](../project-tasks/README.md) | §2 (Architecture, especially `PlanTask.category`), §7 (Calendar activity conventions) | The Analysis tab's External Factors panel reads `PlanTask` directly with `category in ["holiday", "promotion", "event"]`. The cost-rollup by campaign dimension joins via `PlanTask.campaign_id → Campaign.objective`. |
| [`../feature-flags/README.md`](../feature-flags/README.md) | §2 (Architecture — provider + `useFeatureFlag`), §7 (Conventions — flag registration) | Every tab + the wizard sits behind a flag. Required reading before PE-PRD-01. |
| [`../ui/README.md`](../ui/README.md) | §2 (Design tokens, shell integration) | Every Performance UI file consumes Soft Maximalism tokens. Confirm at PE-PRD-05 kickoff whether a Stepper primitive exists for the wizard. |
| [`../data-pipeline/README.md`](../data-pipeline/README.md) | Foundation project (DP-PRD-01) + ingestion-status query | Only relevant for PE-PRD-07 (Diagnostics tab). |
| [`../data-management/README.md`](../data-management/README.md) | §7 (Shape B convention, audit, deletion sweep) | The `performance_wizard_draft` doc follows Shape B. DM-PRD-00 registry, DM-PRD-05 deletion sweep, DM-PRD-07 audit all apply. |
| `docs/KEN-E-System-Architecture.md` | §1.6 (Component Landscape) | Cross-component orientation. Read at the start of a story to confirm which component(s) the work touches. |
| [`../../DESIGN-REVIEW-LOG.md`](../../DESIGN-REVIEW-LOG.md) | Most recent Performance entry (if present) | History of Performance-specific design decisions (e.g., wizard UX home, cost-rollup dimension scope). |

## 7. Conventions and Constraints

### Scope and ownership

- **Performance renders; Performance does not model.** Every statistical computation lives in SAR-E. The only backend code in this component is (a) the five bundle-composer endpoints + `/simulations/run` orchestrator + wizard-draft CRUD, (b) the `PerformanceWizardDraft` Firestore doc. Do not add statistical code, ML models, or analytical aggregations here.
- **Single enablement gate, no per-tab empty states.** `ForecastingEnabledGate` is the only gate. Pre-wizard, Analysis / Simulations / Targets / Diagnostics are **hidden from the nav**; they do not render per-tab CTAs or empty-state cards. The Configuration tab is the sole pre-wizard surface.
- **Wizard UX home is a dedicated route, not a modal.** `/performance/setup` is its own React page. This lets Step 1 redirect cleanly to `/settings/integrations` and return, and lets abandoned drafts persist without coupling to the Configuration tab's render tree.

### Shared state

- **Week-indexed dates only.** `period` is always an ISO-week-aligned `DateRange` (Monday UTC → Sunday UTC). Multi-week ranges end on the Sunday of the final week. The frontend never aggregates weekly values to monthly client-side — monthly views are SAR-E's concern if they ever ship.
- **`PerformanceDateRangeContext` is account-scoped.** The `sessionStorage` key is `perf.dateRange.{accountId}`; switching accounts produces a fresh default (current ISO week + `wow` comparison).
- **`comparisonMode` is tab-local.** Each tab stores its own comparison choice. Simulations compares baseline ↔ target; Targets compares actuals ↔ target; Analysis is the only tab with a `wow / yoy / vs_target` selector. Do not promote it to the shared context without a cross-tab story.

### Bundles and caching

- **Each tab has exactly one page-load bundle.** Related metrics and External Factors are lazy-loaded exceptions (Analysis tab). Do not fan out one tab into N parallel fetches from the frontend — the BFF fan-out is the single round trip.
- **`forecasting_enabled: false` short-circuits to all-nulls.** Every bundle response carries the flag at the top level so the frontend can render the gated state without a second request. The BFF must return this shape in ≤100ms (no SAR-E reads on the disabled path).
- **Stale times.** Bundles: 5 minutes (matches SAR-E's `/analytics/*` cache). External Factors: 1 minute (Calendar edits should surface promptly). Config-status: 60 seconds (matches FF-PRD-03 reference-data convention). Diagnostics: 60-second `refetchInterval` while the tab is the active route; paused otherwise.
- **Cache invalidation.** A Configuration tab mapping / thresholds / channel-coverage save fires `queryClient.invalidateQueries(['performance', ...])` so Analysis / Simulations / Diagnostics refetch with the new config. Wizard completion invalidates `['sar-e', 'config-status', accountId]`.

### Terminology invariant — "Target" not "Goal"

- The Figma export labels LLM-derived forecast values as "Goals". These are **Target** values — per-KPI per-week numerical forecasts. Freeform business Goals are a Knowledge-Graph concept, not a Performance concept.
- **Zero tolerance:** `useGoals`, `GoalsContext`, `setForecastAsGoals`, and user-facing `Goals:` strings must not appear anywhere in `frontend/src/pages/Performance*` or `frontend/src/components/performance/**`.
- Enforced by (a) ESLint `no-restricted-syntax` rule shipped in PE-PRD-03, (b) PE-PRD-08's CI grep audit.

### API conventions

- **Bundle endpoints are reads only.** Every mutation goes directly to the owning component: SAR-E config PUTs, `/targets` POST/PATCH/DELETE, `/config/setup` POST. The BFF is a read-side aggregator, not a write proxy.
- **`POST /performance/{account_id}/simulations/run` is the one orchestration endpoint.** It composes SAR-E `/scenarios` + `/targets/derive` into one user gesture. Do not split simulation into a two-step client-side flow.
- **Role gating via DM-PRD-07.** Every BFF endpoint declares `require_role(UserRole.VIEWER)` on reads and `require_role(UserRole.EDITOR)` on wizard-draft mutations. Writes proxied to SAR-E inherit SAR-E's role matrix.
- **Contract tests in CI (PE-PRD-08).** Every `/api/v1/performance/*` bundle endpoint's response shape is validated against SAR-E's OpenAPI + Project-Tasks' schema. Schema drift fails the build.

### Firestore

- **One new collection.** `accounts/{account_id}/performance_wizard_draft` — single doc per account, Shape B. Owned by PE-PRD-05. Registered in `api/src/_migrate_shape_b/resources.py` and covered by DM-PRD-05's deletion sweep.
- **No Performance-specific composite indexes.** Every query is a single-collection scan by account. Composite indexes live in SAR-E, Project-Tasks, and Data-Pipeline.

### Frontend

- **Branded types** (`EffectivenessKPIId`, `TargetId`, `WeekStartISO`, `SimulationRunId`, `ModelVersion`) per CLAUDE.md C-5. Never use bare `string` for these IDs.
- **URL structure:**
  - `/performance` — auto-redirects to `/performance/configuration` pre-wizard, `/performance/analysis` post-wizard
  - `/performance/{analysis,simulations,targets,diagnostics,configuration}`
  - `/performance/setup?step={welcome,define_kpis,backfill_depth,review}` — URL-backed wizard step
  - `/performance/simulations?replace_kpi={}&replace_week={}` — Targets-tab deep-link handshake (consumed once + stripped)
- **Skeleton-first rendering.** Every tab renders section-scoped skeletons while bundles load; a slow section does not block other sections. Section-scoped errors surface inline retry affordances — never a full-page white screen.
- **No client-side resolvers.** The frontend never maps `(kpi_id, week) → value` itself; the BFF + SAR-E resolve everything server-side. This keeps `FunnelMappingHistory` the single source of truth.

### Figma export caveat

- `docs/figma-export/src/app/pages/performance/AnalysisSection.tsx` and `FunnelSection.tsx` are **not present** in the current export. PE-PRD-02 rebuilds them from Figma designs at kickoff.
- `docs/figma-export/src/app/pages/performance/SimulationsSection.tsx` **is** present and is the source of the Goal → Target rename targets. Do not import from this path in production code — rebuild against Soft Maximalism.
- `docs/figma-export/src/app/pages/performance/PerformanceSetupWizard.tsx` may or may not be present; confirm at PE-PRD-05 kickoff.

### Testing

- **Unit tests colocated** in `__tests__/*.test.tsx` next to each component / hook (CLAUDE.md T-2).
- **Playwright specs per-tab** under `frontend/e2e/performance-*.spec.ts`. PE-PRD-08 runs the cross-tab suites: new-account wizard flow, Save-as-Targets round-trip, Configuration-edit cache propagation, Diagnostics render on a backfilled account, wizard abandonment + resume.
- **Performance gates in CI (PE-PRD-08):** 53-week trendline + 4-stage drill-down under 2s p95; tab-switch latency under 200ms p95 when cached.
- **Contract tests (PE-PRD-08):** every bundle endpoint against SAR-E's OpenAPI in CI.
- **Accessibility audit (PE-PRD-08):** automated axe-core pass across all five tabs + wizard; manual keyboard-navigation pass.

### Standard shape for a project PRD in [`projects/`](./projects/)

Each PRD follows the 10-section structure used across the KEN-E components:

1. Context — problem this PRD solves
2. Scope — explicit in / out
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
- When architecture changes (new files, new abstractions, new bundle fields, new consumed endpoints): update §2
- When a new cross-component dependency is introduced: update §3
- When a new Figma spec becomes available (especially AnalysisSection.tsx / FunnelSection.tsx): update §4 and flag it in the implementation plan's risk table
- When the Goal → Target audit finds a new regression surface (new file path where the banned identifiers slipped in): extend the ESLint rule in PE-PRD-03 and the grep audit in PE-PRD-08
- PE-PRD-08 will append a "Shipped on YYYY-MM-DD — Verification Report" section below once the full component ships. The report names: terminology-audit match count (0), rendering-perf p95 (53-week trendline + 4-stage drill-down under 2s), tab-switch p95 (<200ms cached), a11y violations found + resolved, SAR-E contract-test pass rate, and the five E2E suite outcomes.

This PRD is read by the Dev Team agent during implementation planning (CLAUDE.md §Context Loading Sequence, Step 3). Keep it concise — every sentence should help a dev write better code or avoid mistakes.
-->
