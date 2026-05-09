# Performance — Implementation Plan

**Status:** Draft — 2026-04-23 (revised for SAR-E weekly model + setup wizard)
**Owner:** Performance component team (TBD)
**Proposed PRD prefix:** `PE-PRD-NN`

---

## 1. What Performance is

The Performance component is KEN-E's marketing-measurement dashboard — a six-tab page (`Analysis`, **`Dashboards`**, `Simulations`, `Targets`, `Diagnostics`, `Configuration`, in Figma order) that surfaces how the business is expanding its conversion funnel, the user's pinned-artifact Dashboards, what its calendar of activities is predicted to do over the next 12 weeks, the current KPI target values with actuals-to-date, and forecast-model health. Performance owns five of the six tabs (Analysis / Simulations / Targets / Diagnostics / Configuration) plus the page shell + tab routing; the **Dashboards** tab is owned by the [Dashboards component](../dashboards/README.md) (DB-PRD-02 list / DB-PRD-03 details). SAR-E provides the data for Analysis, Simulations, Targets, and Diagnostics.

Three facts shape the design:

1. **Performance is a frontend + thin orchestration layer.** All analytical computation (weekly baseline forecasts, scenario propagation, target derivation, KPI time series, cost aggregation by dimension) lives in SAR-E (`../sar-e/`). Performance renders; Performance does not model. The only backend surface owned here is composite read endpoints that bundle SAR-E + Project-Tasks data for a page load.
2. **Every Objective maps to exactly one Effectiveness KPI.** The four-stage funnel (`Problem Awareness | Brand Awareness | Consideration | Conversion`) is fixed; the metric measuring each stage's expansion is user-configured via the Funnel Stage Mapping tool. Mapping is owned by SAR-E (persisted, versioned); Performance renders the editor **and owns the initial setup wizard** that creates the mapping in the first place.
3. **"Target" replaces "Goal" everywhere on the Performance page.** In the Figma export, the Simulations tab labels LLM-derived forecast values as "Goals" (`SimulationsSection.tsx` lines 1578/1600/1603; `setForecastAsGoals`; `useGoals`; `GoalsContext`). These are Target values — per-KPI per-week — not freeform business goals. The rename is tracked here; Goals as a concept live in Knowledge Graph.

**Performance is opt-in (for the SAR-E-backed tabs).** SAR-E is disabled at account creation. Pre-wizard, only **Dashboards + Configuration** are visible in the nav; the four SAR-E-backed tabs (Analysis, Simulations, Targets, Diagnostics) are hidden by `ForecastingEnabledGate`. Configuration shows an empty-state CTA linking to the setup wizard; Dashboards renders DB-PRD-02's list (or its empty state) without gating. Pre-wizard, `/performance` redirects to `/performance/configuration`; post-wizard, it redirects to `/performance/analysis`. Once forecasting is enabled, all six tabs are visible — the four SAR-E-backed tabs render live data against SAR-E's weekly KPI series, 12-week baseline, and per-KPI targets.

## 2. What exists today (before Performance)

| Upstream | What it gives us |
|---|---|
| **SAR-E** (new, concurrent) | `/analytics/*`, `/forecasts/*`, `/scenarios`, `/targets/*`, `/config/*` APIs. Also `/config/status` + `/config/setup` + `/config/effectiveness-kpis` for the wizard. |
| **Integrations** (new, concurrent) | OAuth connections. Performance doesn't call Integrations directly, but the wizard displays connected-integration state via SAR-E's `/config/status` and links to `/settings/integrations` (IN-PRD-03) when none are connected. |
| **Project Tasks** (PR-PRD-07, PR-PRD-08) | `Campaign` + `CampaignObjective` enum; `PlanTask.cost / channel / platform / owner_email / campaign_id`; Calendar activities with `category in ["holiday", "promotion", "event"]` — read directly by the Analysis tab's External Factors panel. |
| **UI** (Soft Maximalism) | Design system, global shell, navigation. Performance registers a new top-level page at `/performance`. |
| **Feature Flags** | Per-tab gating + a dedicated wizard flag. |

What's **missing** and needed for Performance:

- The `/performance` page shell with tab routing (six tabs — Analysis / Dashboards / Simulations / Targets / Diagnostics / Configuration). PE-PRD-01 reserves the Dashboards tab slot + placeholder; DB-PRD-02 fills it in.
- `PerformanceDateRangeContext` — shared week-indexed period + comparison-mode state across tabs.
- `ForecastingEnabledGate` that renders the Configuration empty-state CTA and hides Analysis / Simulations / Targets / Diagnostics from the tab nav until SAR-E `/config/status` flips to `enabled=true`.
- Analysis tab UI: funnel viz (CSS clip-path polygons per Figma), 53-week weekly trendline drill-down (reuses Dashboards' LineChart widget, DB-PRD-03), cost-rollup chips by one dimension at a time, related-metrics grid, External Factors panel (reads project-tasks).
- Simulations tab UI: 12-week baseline-vs-target line chart (Recharts `ComposedChart`), "Run Simulation" flow, "Save Forecast as Targets" action.
- Targets tab UI: per-KPI × per-week currently-active Target table with actuals-to-date, drill-down to derivation reasoning, shortcut back to Simulations for supersede-on-edit.
- Diagnostics tab UI: SAR-E model health (baseline-confidence intervals, IRF convergence, last-retrained-at, retrain-needed signals); per-KPI ingestion freshness / gap counts sourced from Data Pipeline.
- Configuration tab UI: Funnel Stage Mapping editor, Thresholds editor, Channel Coverage editor. CLV descoped; ExogenousEventsSection moved to Calendar.
- **Setup wizard UI** — multi-step guided flow at `/performance/setup`, invoked from the Configuration tab's empty-state CTA.
- Figma-to-production terminology rename: every `Goal` / `useGoals` / `GoalsContext` / `setForecastAsGoals` → `Target` / `useTargets` / `TargetsContext` / `setForecastAsTargets`.

## 3. Data-model extensions

Performance owns very little new backend state. The Pydantic / TypeScript shapes it introduces are page-state and composite-response types.

### 3.1 Frontend branded types

```ts
type FunnelObjective = "Problem Awareness" | "Brand Awareness" | "Consideration" | "Conversion";
type EffectivenessKPIId = Brand<string, "EffectivenessKPIId">;
type ComparisonMode = "wow" | "yoy" | "vs_target";
type CostDimension = "channel" | "campaign" | "platform" | "owner";
type WizardStep = "welcome" | "define_kpis" | "backfill_depth" | "review";
```

All comparison modes operate on weekly points directly — the frontend never aggregates weekly values to monthly. `ComparisonMode="wow"` compares each week to the prior week. `ComparisonMode="yoy"` compares each week to the same ISO week 53 weeks prior (aligned to the trendline's 53-week default window). `ComparisonMode="vs_target"` compares per-week actuals to the currently-active Target for each (KPI, week) pair; because SAR-E supersedes on edit (no target history), the comparison always reflects the latest saved value, even for weeks whose Target was updated mid-period.

### 3.2 Composite response shapes

Each tab has a single page-load endpoint that composes SAR-E + Project-Tasks data to minimize round-trips. Every bundle includes a top-level `forecasting_enabled` flag so the frontend can short-circuit to empty-state without a second request:

```python
# GET /api/v1/performance/{account_id}/analysis
class AnalysisBundle(BaseModel):
    forecasting_enabled: bool
    funnel: FunnelSnapshot | None                                # None if not enabled
    trendlines: dict[FunnelObjective, TrendlineSeries] | None    # weekly points over 53 weeks
    cost_rollups: list[CostRollup] | None                        # grouped by dimensions[] × objective
    external_factors: list[ExogenousEventProjection] | None      # from project-tasks Calendar
    related_metrics: list[RelatedMetric] | None
    period: DateRange
    comparison: DateRange
```

```python
# GET /api/v1/performance/{account_id}/simulations
class SimulationsBundle(BaseModel):
    forecasting_enabled: bool
    baseline: dict[EffectivenessKPIId, list[ForecastPoint]] | None   # 12 weekly points per KPI
    calendar_summary: CalendarSummary | None                         # 12-week planned activities rolled up
    saved_targets: list[Target] | None
    horizon_weeks: int | None                                        # 12 in v1
```

```python
# GET /api/v1/performance/{account_id}/targets
class TargetsBundle(BaseModel):
    forecasting_enabled: bool
    targets: list[TargetWithActuals] | None   # currently-active Target per (KPI, week) + actuals-to-date
    last_updated: datetime | None
```

```python
# GET /api/v1/performance/{account_id}/diagnostics
class DiagnosticsBundle(BaseModel):
    forecasting_enabled: bool
    model_health: ModelHealthSnapshot | None           # baseline confidence bands, IRF convergence, last-retrained-at
    per_kpi_ingestion: list[KPIIngestionStatus] | None # freshness, gap counts, latest week per KPI
    retrain_needed: bool | None
```

```python
# GET /api/v1/performance/{account_id}/configuration
class ConfigurationBundle(BaseModel):
    forecasting_enabled: bool
    setup_wizard_completed: bool
    funnel_mapping: FunnelStageMapping | None
    thresholds: list[Threshold] | None
    channel_coverage: ChannelCoverageMatrix | None
    available_kpis: list[EffectivenessKPI] | None
    # Wizard prerequisites — always populated so the wizard can render regardless of enablement
    available_kpi_sources: list[AvailableKPISource]             # Data Pipeline jobs from connected integrations
    connected_integrations: list[PlatformConnectionSummary]
```

The Configuration bundle always populates `available_kpi_sources` + `connected_integrations` so the wizard can render against it; the other fields go null until forecasting is enabled.

## 4. API surface

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/performance/{account_id}/analysis` | Bundle for Analysis tab. Query: `period` (week-indexed), `comparison_mode` (`wow` \| `yoy` \| `vs_target`), `dimension` (one of `channel` \| `campaign` \| `platform` \| `owner`). When SAR-E's `forecasting_enabled=false`, returns `{forecasting_enabled: false}` + nulls. |
| `GET` | `/api/v1/performance/{account_id}/simulations` | Bundle for Simulations tab. Query: `horizon_weeks` (default 12). |
| `GET` | `/api/v1/performance/{account_id}/targets` | Bundle for Targets tab. Returns currently-active Targets per (KPI, week) + actuals-to-date + derivation metadata. |
| `GET` | `/api/v1/performance/{account_id}/diagnostics` | Bundle for Diagnostics tab. Returns SAR-E model health + per-KPI ingestion status. |
| `GET` | `/api/v1/performance/{account_id}/configuration` | Bundle for Configuration tab + Setup Wizard. Always populated enough to drive either UI. |
| `POST` | `/api/v1/performance/{account_id}/simulations/run` | Triggers a simulation: calls SAR-E `/scenarios` + `/targets/derive` with current calendar state. Returns `SimulationRunResult` with baseline, computed targets, per-stage incremental, specialist reasoning. |

**Not owned here** (use SAR-E directly):

- Wizard completion: `POST /sar-e/config/setup` called directly by PE-PRD-05.
- Config mutations: `PUT /sar-e/config/funnel-mapping`, `PUT /sar-e/config/thresholds`, `PUT /sar-e/config/channel-coverage`.
- Target persistence: `POST /sar-e/targets`, `PATCH /sar-e/targets/{target_id}` (supersede semantics).
- Per-KPI CRUD outside wizard: `POST /sar-e/config/effectiveness-kpis`.

Rationale unchanged: bundles are a page-load optimization; settings writes and targeted reads go straight to the owner.

## 5. Interaction with existing components

### 5.1 SAR-E

Performance is SAR-E's primary consumer. Two interaction surfaces beyond pure rendering:

- **Enablement gate.** Every bundle endpoint checks SAR-E `/config/status` and short-circuits to an empty-state payload when `enabled=false`. The frontend's `ForecastingEnabledGate` wrapper renders the CTA variant.
- **Setup wizard I/O.** PE-PRD-05 drives `POST /sar-e/config/setup`, reads `/config/status` during polling, and consumes `available_kpi_sources` from the configuration bundle.

Contract-test each bundle against SAR-E's OpenAPI on CI.

### 5.2 Project Tasks

- Reads `Campaign` + calendar activities for cost-rollup by campaign dimension.
- **External Factors panel on the Analysis tab reads Calendar activities directly** via `GET /plans/{account_id}` with `category in ["holiday", "promotion", "event"]`. SAR-E does not proxy this read.
- Exogenous-event **editing** lives on the Calendar page (PR-PRD-03 extension owned by project-tasks). This component **removes** the Figma Configuration tab's ExogenousEventsSection entirely.

### 5.3 Integrations

Performance doesn't call Integrations directly. The setup wizard (PE-PRD-05) displays connected-integration state via SAR-E's `/config/status` and, if the user has no connections, its first step routes them to `/settings/integrations` (owned by Integrations / IN-PRD-03). On return, the wizard resumes from persisted draft state.

### 5.4 UI (Soft Maximalism)

New page at `/performance`. Reuses the existing `MonthYearPicker`, tab + button primitives. Funnel visualization uses CSS `clip-path` per Figma; 53-week trendlines use Dashboards' LineChart widget (DB-PRD-03); the Simulations 12-week baseline-vs-target chart uses Recharts `ComposedChart` (Dashboards widget not yet applicable to composed axes). Wizard reuses the Stepper pattern if available (confirm with design at PE-PRD-05 kickoff).

### 5.5 Feature Flags

Per-tab flags (`performance_analysis_tab`, `performance_simulations_tab`, `performance_targets_tab`, `performance_diagnostics_tab`, `performance_configuration_tab`) plus a dedicated `performance_setup_wizard` flag so the onboarding flow can dark-launch independently of the tabs.

### 5.6 Dashboards

Dashboards ships before Performance. PE-PRD-02 reuses Dashboards' line-chart widget (DB-PRD-03) for the 53-week trendline rather than owning a separate Recharts wrapper. Upstream dependency in the phasing graph.

## 6. Phasing

Eight PRDs. Tab rendering is split across PE-PRD-02 / 03 / 04 / 06 / 07; the wizard is PE-PRD-05; integration testing is PE-PRD-08.

### PE-PRD-01 — Page shell, routing, shared state

**Delivers:** `/performance` page registered in the global shell with six tabs (Analysis, **Dashboards**, Simulations, Targets, Diagnostics, Configuration, in Figma order); reserves the Dashboards tab slot + `<DashboardsTabPlaceholder />` for DB-PRD-02 to swap in; `PerformanceDateRangeContext` provider (week-indexed period + comparison-mode, mounted only inside the SAR-E-gated tabs); `ForecastingEnabledGate` that renders the Configuration empty-state CTA and hides **only** the four SAR-E-backed tabs (Analysis / Simulations / Targets / Diagnostics) from the tab nav until SAR-E `/config/status` flips to `enabled=true` — Dashboards + Configuration always visible; default-route logic (`/performance` → `/performance/configuration` pre-wizard, → `/performance/analysis` post-wizard); dedicated `/performance/setup` route reserved for the wizard; `FunnelObjective` / `EffectivenessKPIId` / `ComparisonMode` / `CostDimension` / `WizardStep` branded types in `frontend/src/types/performance.ts`; terminology-rename scaffolding (`useTargets` hook wrapping SAR-E `/targets`); feature-flag wiring for all six tab flags + wizard flag. No live data yet.

**Blocked by:** UI shell availability (global nav accepts a new top-level tab).

**Blocks:** PE-PRD-02, PE-PRD-03, PE-PRD-04, PE-PRD-05, PE-PRD-06, PE-PRD-07.

**Effort:** 1–2 days.

### PE-PRD-02 — Analysis tab

**Delivers:** "What Happened" section — 4-stage funnel (CSS clip-path polygons, stage-click to expand); **53-week weekly trendline per stage** rendered via Dashboards' LineChart widget (DB-PRD-03), with a visual marker on the current `is_partial` in-progress week; comparison-mode toggle (`wow` / `yoy` / `vs_target`) applied at the trendline and metric-delta layer; cost-rollup chips by **one** of channel / campaign / platform / owner at a time (single-dimension v1 per product decision; no combined-dimension roll-ups); related-metrics grid; External Factors panel (reads project-tasks Calendar directly — not via SAR-E). Consumes `/performance/analysis` bundle. Tab is hidden in the nav pre-wizard; no pre-enablement empty state is required. When the account has fewer than 53 weeks of history, the trendline shrinks to the available weeks and surfaces an "insufficient history" badge. Skeleton-first render with streamed fills. Loading / empty / error states.

**Blocked by:** PE-PRD-01, SE-PRD-06 (analytical query layer), SE-PRD-01 (config + status), DB-PRD-03 (LineChart widget), PR-PRD-07 (Calendar read for External Factors).

**Blocks:** PE-PRD-08.

**Effort:** 4–5 days.

### PE-PRD-03 — Simulations tab

**Delivers:** Three sub-tabs matching Figma ("Current Plan", "Simulated Results", "Recommendations"); **12-week baseline-vs-target `ComposedChart`**; "Run Simulation" trigger calling `POST /performance/simulations/run`; "Save Forecast as Targets" action persisting via SAR-E `/targets` with supersede-on-edit semantics; per-stage expansion showing LLM reasoning from the forecasting specialist. **Terminology rename** Goal → Target across all components / hooks / context / persistence calls in the Performance surface; ESLint rule added to prevent regression. Tab is hidden in the nav pre-wizard; no pre-enablement empty state is required.

**Blocked by:** PE-PRD-01, SE-PRD-03 (baseline), SE-PRD-04 (scenario), SE-PRD-05 (target derivation).

**Blocks:** PE-PRD-08.

**Effort:** 4 days.

### PE-PRD-04 — Configuration tab

**Delivers:** Funnel Stage Mapping editor (4-row table; each stage → dropdown of available KPIs; uniqueness validator; save / dirty / history affordances); Thresholds editor (per-KPI bounds); Channel Coverage editor (matrix view). Save calls go directly to SAR-E config endpoints. Does not include CLV (descoped) or ExogenousEventsSection (moved to Calendar). Pre-wizard: this is the only tab visible in the nav, rendering an empty-state CTA ("Set up forecasting") that launches the wizard (and a "Resume setup" banner variant when `performance_wizard_draft` exists). Post-wizard: editor panels replace the CTA.

**Blocked by:** PE-PRD-01, SE-PRD-01 (configuration data models + APIs).

**Blocks:** PE-PRD-05 (shares the Funnel Mapping editor component), PE-PRD-08.

**Effort:** 3 days.

### PE-PRD-05 — Setup Wizard (NEW)

**Delivers:** Dedicated-route multi-step guided flow at `/performance/setup`, launched from the Configuration tab's empty-state CTA when `forecasting_enabled=false`. Steps:

1. **Welcome** — explains what the forecasting stack does; branches to `/settings/integrations` if `connected_integrations` is empty, then resumes on return.
2. **Define KPIs** — for each of the four Objectives (Problem Awareness / Brand Awareness / Consideration / Conversion), the user picks one KPI from `available_kpi_sources` (Data Pipeline jobs across the user's connected integrations), names it, and captures its `aggregation` + `unit` + `typical_direction` via a guided form. Reuses the Funnel Stage Mapping editor component from PE-PRD-04 as the selection primitive. Uniqueness validated (one KPI source cannot be mapped to two Objectives). This step merges what was previously "Choose KPIs" + "Map to Objectives" — the mapping is authored at the same moment the KPIs are defined.
3. **Backfill Depth** — calls `POST /sar-e/config/backfill-plan` with the four selected KPI source IDs; SAR-E queries Data Pipeline to determine each source's available history and returns `backfill_weeks = min(104, min(weeks_available_across_all_four_kpis))`. The wizard displays: "We will backfill N weeks of historical data across all four KPIs." If one KPI source drives the cap, it's called out explicitly ("[KPI X] has only N weeks of data available; all four KPIs will be backfilled to the same depth to keep the series aligned."). No slider — backfill depth is computed, not user-chosen, since the VAR model requires equal-length series across the four KPIs. Warning surfaces when `backfill_weeks < 26` ("forecasts will start at low confidence until ~6 months of history accumulates"). User clicks "Continue" to proceed.
4. **Review + Confirm** — summarizes the four KPI-to-Objective mappings and the computed backfill plan; submits `POST /sar-e/config/setup` with `backfill_weeks` in the payload; shows a progress panel polling `/config/status` until `setup_wizard_completed=true`, then redirects to the Analysis tab (now with all six tabs visible).

Persistent wizard-draft state (`accounts/{account_id}/performance_wizard_draft` — owned by this PRD, Shape B convention) so users can resume mid-flow; a "Resume setup" banner variant of the Configuration empty-state appears on return (no force-route per Open Question 6). Abandonment tracked via Weave span `performance.setup_wizard` with `{step, abandoned_at, elapsed_seconds}`.

**New upstream endpoint:** `POST /sar-e/config/backfill-plan` is introduced by this PRD and must be delivered in SE-PRD-02 (weekly ingestion).

**Blocked by:** PE-PRD-01, PE-PRD-04 (Funnel Mapping editor component reuse), SE-PRD-01 (setup endpoint), SE-PRD-02 (backfill-plan endpoint + Data Pipeline history query), IN-PRD-03 (connection-management link target).

**Blocks:** PE-PRD-08.

**Effort:** 3–4 days.

### PE-PRD-06 — Targets tab (NEW)

**Delivers:** Per-KPI × per-week table of currently-active Targets with actuals-to-date progress indicators; drill-down to per-Target derivation reasoning (from SAR-E `/targets/{target_id}`); "Replace this target" shortcut that opens the Simulations "Save Forecast as Targets" flow with the selected (KPI, week) pre-populated. Consumes `/performance/targets` bundle. Tab is hidden in the nav pre-wizard.

**Blocked by:** PE-PRD-01, SE-PRD-05 (target persistence + derivation).

**Blocks:** PE-PRD-08.

**Effort:** 2 days.

### PE-PRD-07 — Diagnostics tab (NEW)

**Delivers:** Model-health dashboard — current baseline-forecast confidence bands (per KPI), IRF convergence status, last-retrained-at, retrain-needed signals (from SAR-E); per-KPI data coverage + gap counts + latest-week-ingested (from Data Pipeline ingestion-status query). Read-only; "Retrain now" trigger deferred to a later PRD. Consumes `/performance/diagnostics` bundle. Tab is hidden in the nav pre-wizard.

**Blocked by:** PE-PRD-01, SE-PRD-03 (baseline + health), SE-PRD-04 (IRF), SE-PRD-06 (analytical query layer), DP-PRD-01 (ingestion-status query).

**Blocks:** PE-PRD-08.

**Effort:** 2–3 days.

### PE-PRD-08 — Integration testing & polish

**Delivers:** E2E Playwright suite:

- New account → lands on `/performance` (auto-routed to `/performance/configuration`) → sees Dashboards + Configuration tabs (the four SAR-E-backed tabs are hidden) with Configuration's empty-state CTA → clicks wizard → connects Google (via Integrations) → completes wizard → forecasting enables → all six tabs appear → redirect to Analysis → 53-week trendlines (low-confidence baseline) + cost rollups render.
- Existing account → Simulations tab → Run Simulation → 12-week baseline+target renders → Save as Targets → Targets tab shows the new values → re-open Analysis in `vs_target` mode → comparison populated.
- Configuration tab (post-wizard) → edit funnel mapping → save → re-open Analysis → charts reflect new mapping.
- Diagnostics tab → confidence bands + coverage + retrain flag render for a backfilled account.
- Wizard abandonment: start → close at step 3 (Backfill Depth) → return to `/performance` → lands on Configuration → "Resume setup" banner renders → wizard opens at step 3 with prior selections intact.

Plus: terminology-rename audit (grep for `useGoals` / `GoalsContext` / `setForecastAsGoals` / `Goals:` in `frontend/src/pages/Performance*` + `frontend/src/components/performance/**`); rendering perf test (53-week trendline via Dashboards widget + 4-stage drill-down under 2s p95); accessibility audit; verification report appended to the component README.

**Blocked by:** PE-PRD-02, PE-PRD-03, PE-PRD-04, PE-PRD-05, PE-PRD-06, PE-PRD-07.

**Blocks:** —

**Effort:** 2–3 days.

## 7. Dependency graph

```
    ┌────────────────────────────────────────────────────────┐
    │  Upstream dependencies                                 │
    │    SE-PRDs 01/02/03/04/05/06  (SAR-E — ../sar-e/)      │
    │    IN-PRD-03                  (conn-mgmt UI)           │
    │    DB-PRD-03                  (Dashboards LineChart)   │
    │    DP-PRD-01                  (ingestion-status query) │
    │    PR-PRD-07                  (Calendar read)          │
    └───────────────────────────┬────────────────────────────┘
                                │
                                ▼
              ┌─────────────────────────────────────┐
              │        PE-PRD-01 (page shell)       │
              └──┬────────┬─────────┬───────┬──────┬┘
                 │        │         │       │      │
                 ▼        ▼         ▼       ▼      ▼
          ┌─────────┐┌────────┐┌──────┐┌──────┐┌──────┐
          │PE-PRD-02││PE-PRD-03│PE-04 ││PE-06 ││PE-07 │
          │Analysis ││Simulat. ││Config││Target.││Diag. │
          └────┬────┘└───┬─────┘└──┬───┘└──┬───┘└──┬───┘
               │         │         │      │       │
               │         │         ▼      │       │
               │         │    ┌────────┐  │       │
               │         │    │PE-PRD-5│  │       │
               │         │    │ Wizard │  │       │
               │         │    └───┬────┘  │       │
               │         │        │       │       │
               └─────────┴────────┴───────┴───────┘
                                 │
                                 ▼
                      ┌──────────────────────┐
                      │      PE-PRD-08       │
                      │ Integration testing  │
                      └──────────────────────┘
```

## 8. Non-goals

- **Owning the VAR model, IRF, or LLM target-derivation.** All three live in SAR-E.
- **Owning KPI time-series ingestion.** Delegated to Data Pipeline → SAR-E.
- **CLV editor.** Descoped per product decision; Figma section removed.
- **ExogenousEventsSection on Configuration.** Moved to Calendar (project-tasks PR-PRD-03 extension). Performance's Analysis tab only reads the resulting list.
- **Custom forecasting widgets.** Users build a Dashboard (`../dashboards/`) and pin analytical tasks for custom views.
- **Cross-tab drill-down / linked filters.** Tabs are independent; only `PerformanceDateRangeContext` is shared.
- **Freeform business Goals.** Goals live in Knowledge Graph; Performance uses "Target" exclusively.
- **Real-time streaming updates.** Bundles are request/response; the page refreshes on tab switch or date-range change.
- **Auto-advancing the wizard without user input.** Every step requires explicit confirmation; abandoned drafts persist but do not auto-submit.

## 9. Risks

| Risk | Mitigation |
|---|---|
| Figma export uses "Goal" in many places where it means Target. Incomplete rename leaks ambiguity. | PE-PRD-08 grep audit as an explicit gate. ESLint rule disallowing `useGoals` / `GoalsContext` / `setForecastAsGoals` in `frontend/src/pages/Performance*` + `frontend/src/components/performance/**`. |
| SAR-E contract changes mid-build | Composite-endpoint field mappings are trivial. Contract-test each bundle endpoint against SAR-E's OpenAPI on CI. |
| 53-week trendline slow on accounts with many metrics | `/performance/analysis` bundle returns only the mapped Effectiveness KPI per stage (4 series). Related metrics are separate lazy loads on demand. |
| Stale Funnel Mapping skews every chart | Mapping edits invalidate React Query caches for `/analytics/*`. Configuration tab History drawer surfaces last-modified + diff. |
| Configuration tab grows over time | Each section is an independent subcomponent with its own save / dirty state. Ship Funnel Mapping first, Thresholds + Channel Coverage after, each behind their own feature flag. |
| **Wizard abandoned mid-flow** | Wizard-draft state persisted to Firestore; "Resume setup" banner on next Performance visit. Weave span captures abandonment step for product tuning. |
| **Wizard shown to a user with no integrations connected** | First step routes to `/settings/integrations`; on return, wizard resumes from draft. |
| Multiple pre-wizard tabs would create empty-state proliferation | Only the Configuration tab is visible pre-wizard (showing the setup CTA); Analysis / Simulations / Targets / Diagnostics are hidden from the nav by `ForecastingEnabledGate`. Single wrapper, single CTA, no per-tab empty-state surfaces. |
| Simulations "Save as Targets" conflicts with prior saved Targets | SAR-E supersedes on edit; UI surfaces a "this will replace the existing target for week N" confirmation before POSTing. |

## 10. Open questions

All previously-open questions resolved during the 2026-04-23 review:

1. **Widget primitives shared with Dashboards.** Resolved: Dashboards ships first; PE-PRD-02 reuses Dashboards' LineChart widget (DB-PRD-03).
2. **History display on accounts with <53 weeks of data.** Resolved: trendline shrinks to the available weeks and shows an "insufficient history" badge.
3. **Cost-rollup dimension interaction.** Resolved: single dimension at a time (channel OR campaign OR platform OR owner); no combined dimensions in v1.
4. **"vs Target" comparison-mode semantics.** Resolved: comparison pins to the currently-active Target per (KPI, week). Because SAR-E supersedes on edit (no target history), there's only one value at any time — the comparison always reflects the latest saved value, even for weeks whose Target was updated mid-period.
5. **Wizard UX home.** Resolved: dedicated route at `/performance/setup` (not a modal on Configuration).
6. **Wizard resume UX.** Resolved: banner only on the Configuration empty-state; no force-route on return.

## 11. Success criteria

- A new account lands on `/performance` (auto-routed to `/performance/configuration`) and sees only the Configuration tab (with empty-state CTA) in the tab nav until the wizard completes; Analysis, Simulations, Targets, and Diagnostics are hidden.
- A user who connects Google and runs the wizard sees all five Performance tabs rendering live data within 30s of submit (wizard → SAR-E setup → initial backfill begins → status flips to enabled → tabs appear → redirect to Analysis → initial render).
- Wizard Backfill-Depth step: queries the four selected KPI sources, computes an equalized backfill depth (capped at 104 weeks), and surfaces the limiting source when the cap is driven by data availability.
- Analysis tab: select a week + `yoy` comparison → 4-stage funnel renders within 2s p95; clicking a funnel stage shows a 53-week trendline (via Dashboards LineChart widget) + single-dimension cost-rollup chips, with a dimension picker to switch between channel / campaign / platform / owner.
- Simulations tab: "Run Simulation" produces a 12-week baseline + target overlay within 10s p95; "Save Forecast as Targets" persists via SAR-E's supersede-on-edit semantics; re-opening Analysis shows the new targets in `vs_target` mode.
- Targets tab: per-(KPI, week) currently-active Target values render with actuals-to-date progress.
- Diagnostics tab: confidence bands, IRF convergence, per-KPI ingestion freshness, and retrain-needed flag all render for a backfilled account.
- Configuration tab: editing funnel mapping + saving + re-opening Analysis renders charts using the new mapping.
- `grep -rn 'useGoals\|GoalsContext\|setForecastAsGoals' frontend/src/pages/Performance* frontend/src/components/performance` returns zero matches.
- Wizard abandonment + resume test passes: user starts wizard → closes tab at step 3 (Backfill Depth) → returns next day → lands on Configuration → "Resume setup" banner renders → wizard opens at step 3 with prior selections intact.
