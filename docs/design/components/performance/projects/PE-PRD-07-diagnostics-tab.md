# PE-PRD-07 — Diagnostics Tab

**Status:** Blocked — resumes once PE-PRD-01, SE-PRD-03, SE-PRD-04, SE-PRD-06, and DP-PRD-01 ship
**Owner team:** Frontend (Performance)
**Blocked by:** PE-PRD-01 (page shell, `ForecastingEnabledGate`, feature-flag wiring); SE-PRD-03 (VAR baseline + confidence bands + `confidence_level` + `training_weeks` + `model_version` + last-retrained-at timestamp); SE-PRD-04 (IRF coefficients produced per model version — enables convergence status + `retrain_needed` flag upstream); SE-PRD-06 (analytical query layer exposes health-snapshot reads); DP-PRD-01 (pipeline-runs foundation — the ingestion-status query for per-KPI coverage + latest-week-ingested + failed-job surfacing is built against `accounts/{account_id}/data_pipeline_runs/*`)
**Blocks:** PE-PRD-08 (integration testing)
**Estimated effort:** 2–3 days

---

## 1. Context

The Diagnostics tab is the fifth tab on the Performance page. It is the single place a user goes to answer two questions:

1. **"How trustworthy are the numbers I'm seeing on Analysis, Simulations, and Targets?"** — surfaced through SAR-E's model health: per-KPI baseline confidence bands, IRF convergence status, last-retrained-at timestamps, and a `retrain_needed` flag.
2. **"Is the upstream data flowing correctly?"** — surfaced through Data Pipeline ingestion status: latest-week-ingested per KPI, gap counts over the last 13 weeks, 53-week coverage percentages, and recently-failed jobs.

Both halves are **read-only in v1**. A "Retrain now" trigger and a "Retry failed job" action are valuable but distinct in risk profile (retrain reruns a multi-minute statsmodels fit; ingestion retry re-hits a rate-limited platform API) and are **deferred to a later PRD** so this one can ship quickly.

The tab is hidden from the Performance-page nav until the setup wizard completes (`ForecastingEnabledGate` from PE-PRD-01). Once forecasting is enabled, the tab fetches `/api/v1/performance/{account_id}/diagnostics` — a composite bundle that joins SAR-E's `Baseline` + `model_version` metadata with Data Pipeline's ingestion-run metadata. The backend composition lives in PE-PRD-01's bundle-endpoint scaffold; this PRD is frontend-only with tight upstream data-contract coordination.

Data in this tab changes slowly (weekly retrain cadence per SE-PRD-03; daily ingestion per DP-PRD-02). The tab polls `/diagnostics` every 60 seconds while visible — see §2 scope + §9 Open Question 1 for the rationale and fallback.

## 2. Scope

### In scope
- `DiagnosticsTab.tsx` page component mounted at `/performance/diagnostics`, rendered only when `performance_diagnostics_tab` flag is on AND `ForecastingEnabledGate` reports `forecasting_enabled=true`
- `useDiagnosticsTab` hook: React Query wrapper around `GET /api/v1/performance/{account_id}/diagnostics`; `refetchInterval: 60_000` while the tab is the active route (paused otherwise to avoid background polling)
- **Model-health section** consisting of:
  - `ConfidenceBandsChart` — per-KPI small-multiple: 12-week baseline line with an 80% prediction-interval shaded band (CI low / CI high from `ForecastPoint.ci_low` / `ci_high` per SE-PRD-03 §3.4). Reuses Dashboards' LineChart widget (DB-PRD-03) where its composed-axes support lands; otherwise a thin Recharts `AreaChart` wrapper purpose-built for this view (Open Question).
  - `IRFConvergenceBadge` per KPI — states `converged` / `not_converged` / `insufficient_data`, each with an explanatory tooltip (see §4.2 for copy)
  - `LastRetrainedAt` per KPI — humanized timestamp ("3 days ago") + raw ISO on hover; highlights red if older than 14 days
  - `RetrainNeededFlag` per KPI — boolean `retrain_needed=true` renders an amber badge with a one-line reason: `data_drift_detected` / `config_changed` / `manual_override`
- **Ingestion-health section** consisting of:
  - `PerKPIIngestionTable` — one row per mapped Effectiveness KPI showing: `kpi_display_name`, `latest_week_ingested` (ISO date), `gap_count_last_13_weeks`, `coverage_percent_last_53_weeks`, `last_successful_run_at`
  - `FailedJobsPanel` — surfaces jobs whose most recent `DataPipelineRun.status="failed"` is within the last 7 days; one card per failed-job context with `connector`, `operation`, `last_error_message`, `failed_at`, and a link to `/settings/integrations` when the error is auth-related
  - Visual rule: any KPI with `coverage_percent_last_53_weeks < 80` or `gap_count_last_13_weeks > 2` gets a warning chip
- Branded / shared frontend types per §4
- Loading / error / tab-level empty-state handling
- Feature-flag gating and `ForecastingEnabledGate` wrap
- Read-only — no mutation endpoints called; no "Retrain now" button, no "Retry job" button

### Out of scope (handled by other PRDs)
- **"Retrain now" trigger.** Deferred. Needs a separate PRD covering `POST /internal/sar-e/retrain-var` invocation with rate-limit + concurrency guards and a user-visible progress indicator. Not in v1.
- **"Retry failed job" trigger.** Deferred for the same reason — rate-limit coordination with Data Pipeline + possible OAuth re-auth flow.
- **Historical model-health timeline.** SAR-E snapshots only the latest `Baseline` per KPI (SE-PRD-03 §3.4); a retrospective CI-band replay is a future enhancement.
- **Per-KPI correlation matrix** (VAR coefficient display). Useful for power users but out of scope for the diagnostics-focused v1.
- **Alerting / notification rules based on diagnostics state.** Surface-only per SAR-E non-goal §8; notifications across the product are a future component.
- **Data Pipeline admin actions** (pause job, change schedule). Owned by DP-PRD-04 frontend.
- **The composite `/performance/{account_id}/diagnostics` bundle endpoint.** Owned by PE-PRD-01's backend scaffold; this PRD consumes it.

## 3. Dependencies

- **PE-PRD-01 (Page shell):** provides `/performance/diagnostics` route, `ForecastingEnabledGate`, `performance_diagnostics_tab` feature-flag wiring, `PerformanceDateRangeContext` (consumed read-only here — Diagnostics does not drive date-range changes), shared branded types.
- **SE-PRD-03 (VAR model + baseline forecast):** provides `Baseline.horizon[]` with `ForecastPoint.ci_low` / `ci_high` (used for confidence-band rendering), `Baseline.confidence_level`, `Baseline.training_weeks`, `Baseline.model_version`, `Baseline.generated_at` (surfaced as last-retrained-at), and the `Baseline.retrain_needed: bool` + `Baseline.retrain_reason: Literal["data_drift_detected", "config_changed", "manual_override"] | None` fields. SE-PRD-03 §4.1 + §5.8 ship the schema + the `flag_baselines_for_retrain(account_id, reason)` helper; SE-PRD-01's funnel-mapping save endpoint calls the helper with `reason="config_changed"`. v1 only fires `config_changed`; `data_drift_detected` and `manual_override` are reserved for future setters but the schema is forward-compatible — `RetrainNeededBadge` renders the reason copy verbatim from §4.2 regardless of which value fires.
- **SE-PRD-04 (Scenario propagation / IRF):** produces `irf_coefficients` snapshot tied to each model version. The IRF convergence status (`converged` / `not_converged` / `insufficient_data`) is a boolean-plus-reason signal derived at IRF compute time. Coordinate the exact field name at kickoff; this PRD assumes `irf_convergence: Literal["converged", "not_converged", "insufficient_data"]` on the per-KPI model-health record.
- **SE-PRD-06 (Analytical query layer):** provides the read endpoint that assembles the `ModelHealthSnapshot`. Composition: one `Baseline` doc per mapped KPI + the IRF convergence status from SE-PRD-04's snapshot.
- **DP-PRD-01 (Data Pipeline foundation):** owns `DataPipelineRun` + `accounts/{account_id}/data_pipeline_runs/*`. The per-source aggregation query lives at `GET /api/v1/internal/data-pipeline/{account_id}/ingestion-status?source_job_ids=...` (DP-PRD-01 §6.7) and returns `IngestionStatusEntry { source_job_id, latest_run_at, latest_run_status, latest_successful_run_at, consecutive_failures, latest_error_message }` per requested source. **DP-PRD-01 owns the run-side fields** (`latest_run_at`, `latest_run_status`, `latest_successful_run_at`, `consecutive_failures`, `latest_error_message`); **SE-PRD-06 owns the kpi-time-series-derived fields** (`latest_week_ingested`, `gap_count_last_13_weeks`, `coverage_percent_last_53_weeks`) — composed from `accounts/{account_id}/kpi_time_series` reads in the analytical query layer. PE-PRD-07's bundle composer joins both into `KPIIngestionStatus` (§4.3) keyed on `kpi_id ↔ source_job_id`.
- **UI component library:** Soft Maximalism table + badge + chart primitives. The confidence-band chart uses either Dashboards' LineChart widget (DB-PRD-03, preferred) or a purpose-built Recharts `ComposedChart` (fallback if composed-axes don't land in time — Open Question 3).
- **Feature Flags (FF-PRD-03):** `performance_diagnostics_tab` via `useFeatureFlag`.
- **Existing files to study:**
  - `frontend/src/pages/Performance/` — other tab implementations for layout + polling conventions
  - `api/src/kene_api/models/data_pipeline_models.py` (DP-PRD-01) — `DataPipelineRun` shape
  - `api/src/kene_api/models/sar_e_models.py` (SE-PRD-03) — `Baseline`, `ForecastPoint`
  - `frontend/src/components/dashboards/widgets/LineChart.tsx` (DB-PRD-03) — widget reuse candidate

## 4. Data contract

### 4.1 Branded / shared types (frontend)

Add to `frontend/src/types/performance.ts`:

```ts
import type { Brand } from '@/types/brand';
import type { EffectivenessKPIId, WeekStartISO } from '@/types/performance';

export type ModelVersion = Brand<string, 'ModelVersion'>;   // e.g., "var-p4-lag2-2026-04-23"
export type DataPipelineJobId = Brand<string, 'DataPipelineJobId'>;
```

`EffectivenessKPIId` and `WeekStartISO` are defined by PE-PRD-01 + PE-PRD-06 respectively.

### 4.2 `ModelHealthSnapshot` (per-KPI model-health record)

```ts
export type IRFConvergence = 'converged' | 'not_converged' | 'insufficient_data';
export type RetrainReason = 'data_drift_detected' | 'config_changed' | 'manual_override' | null;
export type ConfidenceLevel = 'low' | 'medium' | 'high';   // mirrors SE-PRD-03 Baseline.confidence_level

export type PerKPIModelHealth = {
  kpi_id: EffectivenessKPIId;
  kpi_display_name: string;
  model_version: ModelVersion;
  last_retrained_at: string;              // ISO timestamp; Baseline.generated_at
  training_weeks: number;                 // Baseline.training_weeks
  confidence_level: ConfidenceLevel;
  baseline_forecast: Array<{
    week_start: WeekStartISO;
    value: number;
    ci_low: number;
    ci_high: number;
  }>;                                     // len == Baseline.horizon_weeks (12 in v1)
  irf_convergence: IRFConvergence;
  retrain_needed: boolean;
  retrain_reason: RetrainReason;          // non-null iff retrain_needed === true
};

export type ModelHealthSnapshot = {
  per_kpi: PerKPIModelHealth[];           // one entry per mapped Effectiveness KPI (4 in v1)
  snapshot_taken_at: string;              // ISO timestamp — when the bundle composer read the latest Baselines
};
```

IRF-convergence tooltip copy (referenced by `IRFConvergenceBadge`):
- **converged:** "The scenario-propagation coefficients stabilized within the 12-week horizon. Scenarios are considered reliable for this KPI."
- **not_converged:** "Scenario propagation did not stabilize within the 12-week horizon. Scenarios may be noisy for this KPI — retraining with more data may help."
- **insufficient_data:** "Not enough history to fit reliable scenario coefficients. The baseline is a flat projection; scenario results reflect that limitation."

Retrain-reason copy:
- **data_drift_detected:** "Recent ingested data has drifted significantly from the training distribution."
- **config_changed:** "Funnel mapping, KPI registry, or channel coverage changed since the last retrain."
- **manual_override:** "An administrator flagged this model for retrain."

### 4.3 `KPIIngestionStatus` (per-KPI ingestion record)

```ts
export type KPIIngestionStatus = {
  kpi_id: EffectivenessKPIId;
  kpi_display_name: string;
  source_job_id: DataPipelineJobId;                  // the EffectivenessKPI.source_job_id
  latest_week_ingested: WeekStartISO | null;         // null if no weekly rows yet
  gap_count_last_13_weeks: number;                   // count of weeks with no KPIDataPoint in the last 13 ISO weeks
  coverage_percent_last_53_weeks: number;            // 0-100; (53 - gap_count_53) / 53 * 100, rounded to 1 decimal
  last_successful_run_at: string | null;             // ISO timestamp of the most recent DataPipelineRun with status="succeeded" for this job
  consecutive_failures: number;                      // number of most-recent runs with status="failed" immediately before the latest succeeded run (0 if no recent failures)
};
```

### 4.4 `FailedJobSummary` (failed-jobs panel record)

```ts
export type FailedJobSummary = {
  source_job_id: DataPipelineJobId;
  connector: 'google_analytics' | 'google_ads' | 'meta_ads' | 'mailchimp';
  operation: string;                                 // e.g., "unbranded_search_daily"
  affected_kpi_ids: EffectivenessKPIId[];            // all KPIs that have this job as their source_job_id
  last_error_message: string;
  failed_at: string;                                 // ISO timestamp
  error_kind: 'auth' | 'rate_limit' | 'transient' | 'semantic';
};
```

`error_kind` is derived at bundle-composition time: `auth` if the last error message matched a 401/403 pattern, `rate_limit` for 429, `transient` for 5xx/network, `semantic` otherwise. Used by the UI to decide whether to show the "Check Integrations" link (only on `error_kind === 'auth'`).

### 4.5 `DiagnosticsBundle` (consumed from PE-PRD-01's backend)

Mirrors implementation-plan §3.2; re-declared here so the frontend type matches exactly:

```ts
export type DiagnosticsBundle = {
  forecasting_enabled: boolean;
  model_health: ModelHealthSnapshot | null;
  per_kpi_ingestion: KPIIngestionStatus[] | null;
  failed_jobs: FailedJobSummary[] | null;
  retrain_needed: boolean | null;                    // account-level rollup: any KPI.retrain_needed === true
};
```

The top-level `retrain_needed` is a convenience rollup; the per-KPI flag on `PerKPIModelHealth.retrain_needed` is the source of truth for in-tab rendering.

## 5. Implementation outline

| Action | File |
|--------|------|
| Modify | `frontend/src/types/performance.ts` — add `ModelVersion`, `DataPipelineJobId`, `IRFConvergence`, `RetrainReason`, `ConfidenceLevel`, `PerKPIModelHealth`, `ModelHealthSnapshot`, `KPIIngestionStatus`, `FailedJobSummary`, `DiagnosticsBundle` |
| Create | `frontend/src/pages/Performance/DiagnosticsTab.tsx` — page component; feature-flag gate; `ForecastingEnabledGate` wrap; renders the two sections |
| Create | `frontend/src/hooks/useDiagnosticsTab.ts` — React Query hook around `GET /api/v1/performance/{account_id}/diagnostics`; `refetchInterval: 60_000` while tab is active; key `['performance-diagnostics', accountId]` |
| Modify | `api/src/kene_api/routers/performance.py` (scaffolded by PE-PRD-01) — add `GET /api/v1/performance/{account_id}/diagnostics` endpoint; declares `require_role(AccountRole.VIEWER, scope="account")`; delegates composition to `PerformanceBundleComposer.compose_diagnostics_bundle` |
| Modify | `api/src/kene_api/services/performance_bundle_composer.py` (scaffolded by PE-PRD-01) — add `async compose_diagnostics_bundle(account_id)` method per §6.1; fans out via `asyncio.gather` to (a) the 4 mapped `Baseline` docs + IRF-convergence snapshots from SAR-E, (b) DP-PRD-01's `GET /api/v1/internal/data-pipeline/{account_id}/ingestion-status?source_job_ids=...` for run-side fields, (c) SE-PRD-06's analytical query layer for `latest_week_ingested` / `gap_count_last_13_weeks` / `coverage_percent_last_53_weeks`, (d) `DataPipelineRun` 7-day failed-jobs query for `FailedJobSummary[]` |
| Modify | `api/src/kene_api/models/performance_models.py` (scaffolded by PE-PRD-01) — add `DiagnosticsBundle`, `ModelHealthSnapshot`, `PerKPIModelHealth`, `KPIIngestionStatus`, `FailedJobSummary` Pydantic models per §4 |
| Create | `api/tests/integration/test_performance_diagnostics_bundle.py` — bundle composition (4 KPIs fixture); `error_kind` derivation correctness (auth / rate_limit / transient / semantic); top-level `retrain_needed` rollup; `forecasting_enabled=false` short-circuit |
| Create | `frontend/src/components/performance/diagnostics/ModelHealthSection.tsx` — top-level section layout for the four per-KPI cards |
| Create | `frontend/src/components/performance/diagnostics/PerKPIModelHealthCard.tsx` — single-KPI card: title, confidence-band chart, IRF badge, last-retrained-at, retrain-needed badge |
| Create | `frontend/src/components/performance/diagnostics/ConfidenceBandsChart.tsx` — 12-week baseline line + 80% CI shaded band; reuses DB-PRD-03 LineChart or falls back to Recharts AreaChart per §9 Open Question 3 |
| Create | `frontend/src/components/performance/diagnostics/IRFConvergenceBadge.tsx` — pill with tooltip copy from §4.2 |
| Create | `frontend/src/components/performance/diagnostics/RetrainNeededBadge.tsx` — amber pill with reason copy from §4.2 |
| Create | `frontend/src/components/performance/diagnostics/LastRetrainedAt.tsx` — humanized timestamp + hover-reveal of ISO + stale-model red highlight (>14 days) |
| Create | `frontend/src/components/performance/diagnostics/IngestionHealthSection.tsx` — wraps the per-KPI table and the failed-jobs panel |
| Create | `frontend/src/components/performance/diagnostics/PerKPIIngestionTable.tsx` — row per mapped KPI with latest-week / gap-count / coverage / warning chips |
| Create | `frontend/src/components/performance/diagnostics/FailedJobsPanel.tsx` — cards for each FailedJobSummary; "Check Integrations" link only on `error_kind === 'auth'` |
| Create | `frontend/src/pages/Performance/DiagnosticsTab.test.tsx` — colocated per T-2 |
| Create | `frontend/src/components/performance/diagnostics/PerKPIModelHealthCard.test.tsx` |
| Create | `frontend/src/components/performance/diagnostics/ConfidenceBandsChart.test.tsx` |
| Create | `frontend/src/components/performance/diagnostics/PerKPIIngestionTable.test.tsx` |
| Create | `frontend/src/components/performance/diagnostics/FailedJobsPanel.test.tsx` |
| Create | `frontend/src/hooks/useDiagnosticsTab.test.ts` — polling-interval + `visibility` gating |
| Verify | `frontend/src/pages/Performance/PerformancePage.tsx` (from PE-PRD-01) — confirm `DiagnosticsTab` is registered when `performance_diagnostics_tab` resolves true |

## 6. API contract

### 6.1 `GET /api/v1/performance/{account_id}/diagnostics`

Owned by PE-PRD-01's bundle-endpoint scaffold. Composition logic documented here so PE-PRD-01's implementer has the full spec:

1. Read `/sar-e/{account_id}/config/status` — if `enabled=false`, return `{forecasting_enabled: false, model_health: null, per_kpi_ingestion: null, failed_jobs: null, retrain_needed: null}` immediately.
2. Read the current `FunnelStageMapping` to determine which 4 `EffectivenessKPI`s are mapped.
3. For each mapped KPI, read the latest `Baseline` doc (SE-PRD-03) — including the persisted `retrain_needed` + `retrain_reason` fields (§4.2) — and the matching IRF-convergence snapshot (SE-PRD-04). Assemble `PerKPIModelHealth`.
4. For each mapped KPI, derive `KPIIngestionStatus` by joining two upstream reads keyed on `kpi_id ↔ source_job_id`:
   - **Run-side fields** from DP-PRD-01's `GET /api/v1/internal/data-pipeline/{account_id}/ingestion-status?source_job_ids=<comma-sep>` — populates `last_successful_run_at`, `consecutive_failures`, plus the `latest_error_message` carried into the failed-jobs panel.
   - **Time-series-side fields** from SE-PRD-06's analytical query layer (read against `accounts/{account_id}/kpi_time_series`) — populates `latest_week_ingested`, `gap_count_last_13_weeks`, `coverage_percent_last_53_weeks`.
   - The bundle composer fires both reads in parallel via `asyncio.gather` and merges per-source. Either upstream returning a partial result (e.g., DP-PRD-01 reports a never-run source while SE-PRD-06 returns gap-count data, or vice versa) is acceptable — the bundle surfaces whichever fields are populated.
5. Derive `FailedJobSummary[]` from any `DataPipelineRun` docs with `status="failed"` and `finished_at >= now - 7 days`, grouped by `job_id`.
6. Set top-level `retrain_needed = any(model_health.per_kpi[i].retrain_needed)`.

Response: `DiagnosticsBundle` per §4.5.

Polling: the frontend calls this endpoint every 60 seconds while the tab is the active route. Backend-side caching: SE-PRD-06's 5-min TTL on the analytical query layer means most reads under a minute-cadence poll are cache hits; the ingestion-status query hits Firestore directly and is cheap (single aggregation per KPI).

### 6.2 No mutation endpoints

This tab is read-only. `POST /internal/sar-e/retrain-var` (SE-PRD-03) and DP-PRD job-retry endpoints exist but are not invoked from this tab in v1.

## 7. Acceptance criteria

1. With `performance_diagnostics_tab=false`, navigating to `/performance/diagnostics` renders a 404-style "Tab not available" screen; the Diagnostics tab does not appear in the Performance-page nav.
2. With `performance_diagnostics_tab=true` and `forecasting_enabled=false`, the tab is hidden from the nav; direct navigation redirects to `/performance/configuration`.
3. With `forecasting_enabled=true` and a seeded bundle, four `PerKPIModelHealthCard`s render (one per mapped KPI).
4. Each card renders the 12-week confidence-band chart with the baseline line and shaded CI area (visible differentiation between `ci_low` and `ci_high`).
5. Each card's `IRFConvergenceBadge` renders the correct state with the tooltip copy from §4.2.
6. Each card's `LastRetrainedAt` shows a humanized "N days ago" label; hovering reveals the raw ISO timestamp; values older than 14 days are rendered with the stale-model red highlight.
7. A card with `retrain_needed=true` renders `RetrainNeededBadge` with the reason copy matching the `retrain_reason` field.
8. The ingestion-health section renders a `PerKPIIngestionTable` with one row per mapped KPI; rows with `coverage_percent_last_53_weeks < 80` OR `gap_count_last_13_weeks > 2` show a warning chip.
9. The `FailedJobsPanel` renders a card for every `FailedJobSummary` in the bundle; cards with `error_kind === 'auth'` include a "Check Integrations" link pointing at `/settings/integrations`; other error kinds do NOT render that link.
10. If `failed_jobs` is empty, the panel shows "No failed jobs in the last 7 days" (not hidden — the absence is informative).
11. `useDiagnosticsTab` polls every 60 seconds only while the tab is the active route; switching away from Diagnostics to another Performance tab pauses the interval.
12. Initial render is skeleton-first; the bundle arrives and the skeleton morphs into the populated view; error state shows a retry button.
13. `npm run typecheck` passes; `npm run format.fix` passes; all colocated tests green.
14. `grep -rn 'Goal\|useGoals\|GoalsContext' frontend/src/pages/Performance/DiagnosticsTab.tsx frontend/src/components/performance/diagnostics/` returns zero matches.

## 8. Test plan

**Unit tests** (`useDiagnosticsTab.test.ts`):
- Hook returns `isLoading: true` on first render.
- Hook fires the correct URL.
- Hook's `refetchInterval` fires a second request after 60 seconds (fake-timers).
- Hook pauses polling when the tab is not visible (mock `useMatch('/performance/diagnostics')` → false).
- Hook short-circuits to a static empty response when `forecasting_enabled=false`.

**Unit tests** (`ConfidenceBandsChart.test.tsx`):
- Renders 12 data points when `baseline_forecast.length === 12`.
- Renders the CI band (asserts on `ci_low` / `ci_high` path elements present).
- Renders the "insufficient history" badge when `training_weeks < 26` (hoisted from the card for chart-local display — confirm at kickoff).
- Degrades to "No baseline available" placeholder when `baseline_forecast.length === 0`.

**Unit tests** (`PerKPIModelHealthCard.test.tsx`):
- Full-happy-path render with fixtures for each of the three IRF states.
- `retrain_needed=true` → badge visible with matching reason.
- `retrain_needed=false` → badge not rendered.
- `last_retrained_at` more than 14 days ago → stale-model red class applied.

**Unit tests** (`PerKPIIngestionTable.test.tsx`):
- Empty `per_kpi_ingestion` → "No ingestion data yet" message.
- Four-row input → four rows rendered sorted alphabetically by `kpi_display_name`.
- Warning chip visibility matches §7 criterion 8 (four fixture cases: coverage under / over 80, gap count under / over 2).
- `latest_week_ingested=null` → column renders "Never" not a date.

**Unit tests** (`FailedJobsPanel.test.tsx`):
- Zero failed jobs → informative empty-state.
- `error_kind='auth'` → "Check Integrations" link present with correct `href`.
- `error_kind='rate_limit' | 'transient' | 'semantic'` → link NOT present.
- Multiple failed jobs render in `failed_at` descending order.

**Unit tests** (`DiagnosticsTab.test.tsx`):
- Feature flag off → not-available screen.
- `forecasting_enabled=false` → redirect (mock `useNavigate`).
- Full bundle → both sections render.

**Integration-style (MSW + React Testing Library)**:
- Happy path: seeded bundle → tab renders → poll at 60s triggers a second fetch → DOM does not visibly flicker (React Query keeps previous data while revalidating).

**Lint guard:** ESLint rule (installed in PE-PRD-03) fires on any `Goal*` identifier in this tab's files.

## 9. Risks & open questions

| Risk / question | Mitigation |
|---|---|
| 60s polling = 1440 extra reqs/account/day | Backend caching in SE-PRD-06 (5-min TTL) keeps this cheap; the ingestion-status query is a Firestore aggregation with a composite index per DP-PRD-01. If ops flags it during DP-PRD-06, loosen interval to 300s or move to manual-refresh (see Open Question 1). |
| Confidence-band chart depends on DB-PRD-03's composed-axes support | DB-PRD-03 doesn't explicitly call out composed-axes. If its LineChart widget doesn't support a CI band out-of-box at build time, fall back to a purpose-built Recharts `AreaChart` inside `ConfidenceBandsChart` (an additional internal component only — does NOT become a Dashboards widget). Confirm at kickoff. |
| `retrain_needed` + reason field may not yet exist on SE-PRD-03's `Baseline` model | **Resolved 2026-04-27.** SE-PRD-03 §4.1 now persists `retrain_needed: bool` + `retrain_reason: Literal["data_drift_detected", "config_changed", "manual_override"] \| None` on every `Baseline` doc. SE-PRD-03 §5.8 ships the `flag_baselines_for_retrain` helper; SE-PRD-01's funnel-mapping save endpoint (§6.2) calls it with `reason="config_changed"`. v1 only fires `config_changed`; the other two reasons are forward-compatible reserved values. |
| IRF convergence field name not yet fixed in SE-PRD-04 | This PRD assumes `irf_convergence` literal on the model-health record. Coordinate at kickoff. |
| Users see diagnostics state but can't act on it | v1 trade-off. Explicit "Retrain now" + "Retry job" actions are deferred to their own PRD so this one ships quickly. Surface a subtle "These actions are coming soon" footnote if needed. |
| Stale timestamps when user returns after a long absence | React Query `refetchOnWindowFocus` = true (default) catches this; additional 60s interval smooths steady-state. |
| No historical model-health timeline | SAR-E snapshots the latest `Baseline` only. A per-version replay would need a `baseline_history` subcollection which SE-PRD-03 explicitly does not retain. Revisit if product value is proven. |

### Open questions

1. **Polling cadence: 60s real-time-ish vs fully manual refresh?** Diagnostics data updates at weekly cadence (retrain) + daily cadence (ingestion), so minute-level polling is overkill for freshness. Counter: it keeps the tab feeling alive and surfaces failed-job incidents faster. Default: ship 60s polling with the scope note that it can be converted to manual refresh if ops flags it. **Confirm at kickoff.** If the team prefers manual refresh, replace `refetchInterval: 60_000` with a "Refresh" button + last-fetched timestamp.
2. **~~Is `retrain_needed` already emitted by SAR-E, or is this PRD assuming a field that needs to be added?~~** **Resolved 2026-04-27.** SE-PRD-03 §4.1 + §5.8 now ships the field + setter helper; SE-PRD-01 §6.2 wires the funnel-mapping save call site. PE-PRD-07's bundle composer reads `Baseline.retrain_needed` + `Baseline.retrain_reason` directly. v1 only fires `config_changed`; `data_drift_detected` and `manual_override` are reserved values for future PRDs.
3. **DB-PRD-03's LineChart vs purpose-built Recharts AreaChart for the CI band.** Prefer reuse. Fallback is a thin Recharts wrapper limited to this tab — do NOT promote it to a shared Dashboards widget.
4. **Stale-model threshold (default: 14 days).** Based on a weekly retrain cadence + one-retrain-missed grace. Revisit if the retrain automation runs biweekly or monthly in some accounts.
5. **Failed-job window (default: 7 days).** Longer windows surface too much noise from transient platform outages; shorter windows hide ongoing auth failures. 7 is the compromise. Tune with DP-PRD-06 telemetry.
6. **Should `PerKPIModelHealthCard` show `confidence_level` (low/medium/high) alongside `training_weeks`?** Likely yes — it's the primary user-facing confidence indicator from SE-PRD-03. Add if kickoff design confirms.

## 10. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md) §3.2 `DiagnosticsBundle`, §4 API surface, §6 PE-PRD-07
- Upstream: [SE-PRD-03 VAR model + baseline forecast](../../sar-e/implementation-plan.md#se-prd-03--var-model--baseline-forecast) `Baseline`, `ForecastPoint`, confidence bands, `training_weeks`
- Upstream: [SE-PRD-04 Scenario propagation (IRF)](../../sar-e/implementation-plan.md#se-prd-04--scenario-propagation-irf) IRF convergence signal
- Upstream: [SE-PRD-06 Analytical query layer](../../sar-e/implementation-plan.md#se-prd-06--analytical-query-layer) composite-read layer + caching
- Upstream: [DP-PRD-01 Foundation](../../data-pipeline/implementation-plan.md#dp-prd-01--foundation) `DataPipelineRun` + ingestion-status query
- Sibling: [PE-PRD-01 Page shell](./PE-PRD-01-page-shell-and-routing.md) `ForecastingEnabledGate`, feature-flag wiring
- Sibling: [DB-PRD-03 Dashboard details & canvas](../../dashboards/projects/DB-PRD-03-dashboard-details-and-canvas.md) LineChart widget candidate for confidence-band reuse
- Style reference: [DB-PRD-01 Dashboard Data Model & API](../../dashboards/projects/DB-PRD-01-data-model-and-api.md)
- Feature Flags: [FF-PRD-03 `useFeatureFlag` hook](../../feature-flags/projects/FF-PRD-03-frontend-sdk-and-e2e.md)
- CLAUDE.md rules in scope: C-1 (TDD), C-4 (composable functions), C-5 (branded IDs), C-6 (`import type`), C-8 (prefer `type`); T-2 (colocated frontend tests), T-4 (separate pure vs DB), T-5 (prefer integration over heavy mocking), T-8 (structural assertions); G-2 (`npm run format.fix`), G-3 (`npm run typecheck`); O-2 (shared frontend/API types)
