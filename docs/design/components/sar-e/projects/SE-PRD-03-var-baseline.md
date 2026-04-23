# SE-PRD-03 — VAR Model + 12-Week Baseline Forecast

**Status:** Blocked — resumes once SE-PRD-02 ships
**Owner team:** SAR-E component team (backend / applied stats)
**Blocked by:** SE-PRD-02 (`KPIDataPoint` weekly rows are the VAR training input; `is_partial=true` rows must be excludable; the weekly ingestion automation is where we chain the retrain task)
**Blocks:** SE-PRD-04 (IRF reads persisted VAR coefficients); SE-PRD-05 (Target derivation specialist reads `Baseline` per KPI); SE-PRD-06 (analytical queries surface `confidence_level` + model-version metadata); PE-PRD-03 (Simulations chart); PE-PRD-07 (Diagnostics tab)
**Estimated effort:** 4 days

---

## 1. Context

SAR-E's forecasting core is a Vector Auto-Regression (VAR) model trained on the 4 Funnel-mapped Effectiveness KPIs at weekly granularity. Training is closed-form numerical code (statsmodels VAR) invoked asynchronously from the weekly ingestion automation; forecast reads always hit a persisted `Baseline` snapshot so the synchronous API path is cheap. This PRD delivers the training pipeline, the persistence layer, the forecast read endpoint, and the retrain automation wiring.

Four facts shape the design:

1. **VAR colocates with the API.** statsmodels VAR fits in-process; no separate model server. Retrain jobs run on the same uvicorn workers as the API (implementation-plan §10 resolved). The retrain endpoint is OIDC-authed and called from the weekly automation's final task; synchronous reads hit Firestore only. We never train on the forecast-read hot path.
2. **Under-covered channels are excluded at training-input time — not at read time.** `ChannelCoverage` is the single source of truth for which channels feed the VAR matrix (implementation-plan §3.5 split semantics). The VAR trainer consults the coverage matrix and drops any channel flagged below the threshold before fitting; cost-rollup queries (SE-PRD-06) include the same channels without change. A unit test locks this asymmetry.
3. **Confidence is a coarse label, not a number.** We surface `confidence_level: low | medium | high` (derived from `training_weeks`: `<26 → low`, `26–52 → medium`, `>52 → high`), plus 80% prediction intervals on the forecast points. We do not expose the fitted coefficients, log-likelihood, or AIC — they're captured in the persisted `Baseline` for debugging but not returned by the API. The Diagnostics tab (PE-PRD-07) may surface them later.
4. **`<26 weeks` is a hard guard.** Accounts with less than 26 weeks of complete history get a flat-baseline forecast with wide CI and `confidence_level="low"` (implementation-plan §9 risks). The training function returns this degenerate baseline instead of raising; the wizard setup flow can complete even on a brand-new GA account.

The retrain cadence is weekly. The ingestion automation's final task (SE-PRD-02) fires a retrain task in its `on_success` chain. Ad-hoc retrain is an admin action via `POST /internal/sar-e/retrain-var` directly; no user-facing "retrain now" button in v1.

## 2. Scope

### In scope

- **`Baseline` + `ForecastPoint` Pydantic models** under `api/src/kene_api/models/sar_e_models.py`:
  - `ForecastPoint { week_start, value, ci_low, ci_high }`
  - `Baseline { account_id, kpi_id, generated_at, model_version, horizon_weeks, horizon: list[ForecastPoint], confidence_level, training_weeks, training_inputs: VARTrainingInputsSnapshot }`
  - `VARTrainingInputsSnapshot { included_kpi_ids, excluded_channels, training_window_start, training_window_end, lag_order, fit_aic, fit_bic }` — informational; not part of the user-facing contract
- **`VAREstimator` class** in `api/src/kene_api/services/sar_e_var_estimator.py`:
  - Wraps `statsmodels.tsa.api.VAR`; log-transforms non-negative KPI series with `log1p`; exposes `fit(training_matrix) -> FittedVARModel`
  - Lag selection via AIC/BIC with a min-sample guard of **26 weeks** (implementation-plan §6 SE-PRD-03 deliverable) and a max-lag cap of 8 weeks (2 months of influence)
  - Returns a `FittedVARModel` wrapping statsmodels' `VARResults` plus the transformation metadata (so SE-PRD-04's IRF engine can invert log scale correctly)
  - Degenerate case (`training_weeks < 26`): returns a sentinel `FlatBaselineModel` whose `forecast()` emits the 12-week per-KPI mean of the last 4 complete weeks with CI = ±2σ of the training window (wide)
- **`ForecastEngine` class** in `api/src/kene_api/services/sar_e_forecast_engine.py`:
  - Takes a `FittedVARModel`, produces 12 weekly `ForecastPoint`s per KPI at natural scale
  - Converts log-scale forecast intervals back to natural scale via `expm1`
  - CI at 80% confidence (`forecast_interval(alpha=0.20)`); `ci_low` clamped at 0 for non-negative KPIs
- **Training-input assembler** in `api/src/kene_api/services/sar_e_training_input.py`:
  - `assemble_training_matrix(account_id) -> TrainingMatrix` — reads `kpi_time_series` for the 4 mapped KPIs, filters `is_partial=false`, aligns on `week_start`, drops any week where one or more KPIs is missing, returns a `(weeks × 4)` numpy matrix plus the aligned `week_start` vector
  - Reads `ChannelCoverage` and — this is the key asymmetry — when a KPI is sourced from a job whose output breaks down by channel, drops rows for channels flagged under-covered **before** aggregation (§5.2). For KPIs not channel-decomposed (e.g., GA `sessions_total`), the full row is retained.
  - Confidence-level derivation: `len(training_matrix) < 26 → "low"`, `26 ≤ len < 52 → "medium"`, `≥ 52 → "high"`
- **`Baseline` persistence** at `accounts/{account_id}/baselines/{kpi_id}`:
  - Always overwritten (no version history — the most recent trained baseline is authoritative)
  - Composite index: none needed (single-doc reads per `kpi_id`)
  - Contains the full 12-week forecast + metadata
- **`/api/v1/sar-e/{account_id}/forecasts/baseline`** (GET) — returns all 4 KPIs' baselines as a dict `{kpi_id: Baseline}`. Always reads from persisted `Baseline` docs; never triggers training. If a KPI has no baseline yet (pre-first-retrain), the response omits that key (the Analysis + Simulations tabs render a "baseline computing" banner per PE-PRD-02/03).
- **`/api/v1/internal/sar-e/retrain-var`** (POST, OIDC-authed) — body `{account_id}`. Loads the training matrix, fits the VAR, produces + persists 4 `Baseline` docs, writes a Weave span `sar_e.var_retrain` with `{account_id_hash, training_weeks, lag_order, duration_ms, confidence_level}`. Returns `{kpi_ids: [...], training_weeks, lag_order, model_version, duration_ms}`.
- **Weekly retrain automation wiring** — extend SE-PRD-02's `sar_e_automation_seeder.create_weekly_ingestion_automation` so the plan's final task is a retrain-task (`assignee_type="agent"`, ADK glue agent calling `/internal/sar-e/retrain-var`) that depends on the ingest-task. Retrain runs after ingestion every Monday, same `is_system=true` plan.
- **Model-version tagging** — each `Baseline` carries `model_version: "var-p{lag}-{YYYY-MM-DD}"` (e.g., `"var-p2-2026-04-27"`). `Baseline.generated_at` is UTC.
- **Weave span `sar_e.var_retrain`** — wraps the entire retrain call. Captures `{account_id_hash, training_weeks, lag_order, aic, bic, confidence_level, duration_ms, outcome}`. No PII.
- **Tests**:
  - Unit: VAREstimator on synthetic data (known AR(1) process — trained model recovers the correct lag)
  - Unit: log-transform → `expm1` roundtrip exactness for `ForecastPoint` CI bounds
  - Unit: `<26 weeks` produces a flat baseline with wide CI, no exception
  - Unit: under-covered channel dropped from training matrix (construction); included in cost-rollup path (reference assertion only — cost-rollup is SE-PRD-06)
  - Integration: seed 104 weeks of `KPIDataPoint` rows for 4 KPIs; call `/internal/sar-e/retrain-var`; assert 4 `Baseline` docs written with 12 horizon points each; `confidence_level="high"`
  - Integration: partial-week row for current week is excluded (training matrix stops at last complete week)
  - Integration: weekly automation chain — ingest-task → retrain-task → 4 `Baseline` docs present at plan completion
  - Performance: retrain on 104 weeks × 4 KPIs completes under 10 minutes p95 on a standard uvicorn worker (acceptance criterion from implementation-plan §11)

### Out of scope (handled by other PRDs)

- IRF propagation + scenario math (SE-PRD-04)
- Target derivation (SE-PRD-05)
- Funnel trendline / cost-rollup / funnel-snapshot queries that consume the baseline (SE-PRD-06)
- Performance UI rendering of baselines (PE-PRD-02 / PE-PRD-03 / PE-PRD-07)
- VARX — adding exogenous-event regressors to the VAR. Explicitly deferred to v2 (implementation-plan §10 resolved).
- Causal inference — every output phrases relationships as associations (MER-E / methodology-note enforcement lands in SE-PRD-05's specialist).
- Multi-horizon configurability — 12 weeks is the only v1 horizon. `forecast_horizon_weeks` is stored on `SarEConfig` (SE-PRD-01) as forward-compat; reading a non-12 value is a runtime assertion failure in this PRD (intentional — tightening the scope until industries with longer cycles land).

## 3. Dependencies

- **SE-PRD-02:** `KPIDataPoint` model at `accounts/{account_id}/kpi_time_series/{kpi_id}__{week}`; `is_partial` filter; weekly ingestion automation's final task is extended here. Also the `sar_e_ingestion` glue agent pattern (§5.1 of SE-PRD-02) — we add a sibling `sar_e_retrain` glue agent.
- **SE-PRD-01:** `FunnelStageMapping` (gives the 4 KPI ids to train), `ChannelCoverage` (drives channel exclusion), `SarEConfig` (gate check: if `enabled=false`, retrain is a no-op that logs + returns early).
- **Agentic Harness (AH-PRD-02):** agent factory reads `agent_configs/sar_e_retrain` (single-tool glue agent calling `POST /internal/sar-e/retrain-var`). Unlike SE-PRD-05's `performance_forecasting` specialist, this is a `FunctionTool`-only agent — no LLM reasoning. The factory has to tolerate that; confirm at kickoff that AH-PRD-02's factory can construct an agent with zero LLM fields (`model=None`? or `model="gemini-2.0-flash"` with a no-op instruction?). First-pass approach: use `gemini-2.0-flash` with an instruction of `"Call the sar_e_retrain tool. Return its JSON output verbatim."` — cheap and simple.
- **Automations (A-PRD-01, A-PRD-02):** retrain task integrates into the weekly `is_system=true` plan. Uses `TaskOrchestrator.on_task_due` / `on_task_status_change`.
- **Python deps:** `statsmodels >= 0.14.0`, `numpy >= 1.26`, `pandas >= 2.0`. All already in `api/pyproject.toml` or adjacent; if `statsmodels` is not present, add it here.
- **Existing files to study:**
  - `api/src/kene_api/services/sar_e_ingestion_service.py` (SE-PRD-02) — Firestore service-layer pattern
  - `app/adk/tracking/` — `@safe_weave_op` + span helpers

## 4. Data contract

### 4.1 Forecast + baseline models

```python
class ForecastPoint(BaseModel):
    week_start: date
    value: float
    ci_low: float
    ci_high: float


class VARTrainingInputsSnapshot(BaseModel):
    included_kpi_ids: list[str]
    excluded_channels: list[str]
    training_window_start: date
    training_window_end: date
    lag_order: int
    fit_aic: float | None
    fit_bic: float | None


class Baseline(BaseModel):
    account_id: str
    kpi_id: str
    generated_at: datetime
    model_version: str                                       # "var-p{lag}-{YYYY-MM-DD}"
    horizon_weeks: int                                       # always 12 in v1
    horizon: list[ForecastPoint]                             # len == 12
    confidence_level: Literal["low", "medium", "high"]
    training_weeks: int                                      # rows available after alignment + partial filter
    training_inputs: VARTrainingInputsSnapshot
```

### 4.2 Retrain endpoint

```python
class RetrainRequest(BaseModel):
    account_id: str


class RetrainResponse(BaseModel):
    kpi_ids: list[str]
    training_weeks: int
    lag_order: int
    model_version: str
    confidence_level: Literal["low", "medium", "high"]
    duration_ms: int
    outcome: Literal["trained", "flat_baseline", "skipped_disabled", "skipped_no_mapping"]
```

### 4.3 Forecast-baseline endpoint

```python
class BaselineBundle(BaseModel):
    baselines: dict[str, Baseline]                           # keyed by kpi_id
    horizon_weeks: int
    generated_at: datetime                                   # min of the four Baseline.generated_at (they should all match within seconds)
```

Empty-map response when no baselines exist yet — the Analysis / Simulations tabs render a "baseline computing" banner.

### 4.4 Firestore layout (Shape B)

| Path | Shape | Purpose |
|---|---|---|
| `accounts/{account_id}/baselines/{kpi_id}` | subcollection | `Baseline` — one doc per mapped KPI; overwritten on each retrain |

Register `baselines` in `_migrate_shape_b/resources.py`. No composite indexes needed (doc-id lookup).

## 5. Implementation outline

| Action | File |
|---|---|
| Modify | `api/src/kene_api/models/sar_e_models.py` — add `ForecastPoint`, `Baseline`, `VARTrainingInputsSnapshot`, retrain request/response models |
| Create | `api/src/kene_api/services/sar_e_training_input.py` — `assemble_training_matrix(account_id) -> TrainingMatrix` |
| Create | `api/src/kene_api/services/sar_e_var_estimator.py` — `VAREstimator.fit`, `FittedVARModel`, `FlatBaselineModel` |
| Create | `api/src/kene_api/services/sar_e_forecast_engine.py` — `produce_baselines(fitted_model, training_inputs) -> list[Baseline]` |
| Create | `api/src/kene_api/services/sar_e_retrain_service.py` — orchestrates assemble → fit → produce → persist; adds Weave span |
| Create | `api/src/kene_api/routers/sar_e_forecasts.py` — `/forecasts/baseline` (GET) + `/internal/sar-e/retrain-var` (POST) |
| Modify | `api/src/kene_api/services/sar_e_automation_seeder.py` — extend `create_weekly_ingestion_automation` to include the retrain-task after the ingest-task |
| Modify | `api/src/kene_api/main.py` — mount `sar_e_forecasts.router` |
| Modify | `api/src/_migrate_shape_b/resources.py` — register `baselines` |
| Create | `agent_configs/sar_e_retrain` Firestore seed doc — single-tool glue agent |
| Modify | `api/pyproject.toml` — add `statsmodels>=0.14.0` if not already present |
| Create | `api/tests/unit/test_sar_e_var_estimator.py` |
| Create | `api/tests/unit/test_sar_e_forecast_engine.py` |
| Create | `api/tests/unit/test_sar_e_training_input.py` |
| Create | `api/tests/integration/test_sar_e_retrain_endpoint.py` |
| Create | `api/tests/integration/test_sar_e_forecasts_baseline_endpoint.py` |
| Create | `api/tests/integration/test_sar_e_weekly_automation_retrain.py` |
| Create | `api/tests/perf/test_sar_e_retrain_perf.py` — asserts ≤10min p95 on 104×4 synthetic fixture |

### 5.1 Training matrix assembly

```python
def assemble_training_matrix(account_id: str) -> TrainingMatrix:
    config = get_sar_e_config(account_id)
    if not config.enabled:
        return TrainingMatrix.empty(reason="disabled")

    mapping = get_funnel_mapping(account_id)
    if mapping.version == 0:
        return TrainingMatrix.empty(reason="no_mapping")

    kpi_ids = list(mapping.mappings.values())
    coverage = get_channel_coverage(account_id)
    excluded_channels = _channels_below_threshold(coverage)

    # Read all KPI time series in parallel
    series_by_kpi: dict[str, list[KPIDataPoint]] = await asyncio.gather(
        *[read_time_series(account_id, kid, is_partial=False) for kid in kpi_ids]
    )

    # For channel-decomposed KPIs, drop under-covered channels BEFORE aggregation
    # (channel breakdown lives in the DP artifact, not in the KPIDataPoint —
    # so this is informational in v1; the actual exclusion happens at artifact
    # parse time in SE-PRD-02. See §5.2 for the contract.)

    # Align on week_start — retain only weeks where all 4 KPIs have a value
    aligned = _align_on_week_start(series_by_kpi)

    return TrainingMatrix(
        matrix=np.array(aligned.values),                      # (weeks, 4)
        week_starts=aligned.week_starts,
        kpi_ids=kpi_ids,
        excluded_channels=excluded_channels,
        training_weeks=len(aligned.values),
    )
```

Alignment drops weeks where any KPI is missing (typical cause: different connectors starting to feed data at different times during backfill).

### 5.2 Channel-exclusion contract

The implementation-plan §3.5 "split semantics" require that under-covered channels are excluded from VAR training but included in cost rollup. This PRD establishes the contract:

- **Training path.** `ChannelCoverage` is read during training-matrix assembly. The excluded channels are recorded in `TrainingMatrix.excluded_channels` and carried through to `Baseline.training_inputs.excluded_channels` for traceability. The actual channel-level exclusion must happen during artifact ingestion (SE-PRD-02) — but SE-PRD-02 wrote channel-indifferent `KPIDataPoint` rows. To make the exclusion real, one of two approaches:
  - **v1 (shipped here):** Document the limitation. If a KPI is channel-decomposed, the user is expected to exclude the channel via `ChannelCoverage` **before** training is valuable (i.e., accept that the first retrain on a brand-new account is channel-blind, then edit `ChannelCoverage`, then the next weekly retrain is clean). Acceptable because `ChannelCoverage` is typically populated after the first backfill completes.
  - **v1.1 (follow-up):** Extend SE-PRD-02's ingestion service to emit per-(kpi_id, week, channel) rows alongside the aggregated weekly row, then have the training-matrix assembler re-aggregate post-exclusion. Scoped separately.
- **Cost-rollup path.** SE-PRD-06's cost rollup ignores `ChannelCoverage.excluded_channels` — cost is always included regardless. Asserted by integration test in SE-PRD-06.

Unit test here asserts `Baseline.training_inputs.excluded_channels` is a superset of the coverage-flagged channels. A placeholder assertion (since the exclusion itself isn't wired at training-matrix level until the v1.1 follow-up) — but the contract field exists from day one.

### 5.3 VAR fit

```python
class VAREstimator:
    MIN_TRAINING_WEEKS = 26
    MAX_LAG = 8

    def fit(self, matrix: TrainingMatrix) -> FittedVARModel | FlatBaselineModel:
        if matrix.training_weeks < self.MIN_TRAINING_WEEKS:
            return FlatBaselineModel(
                matrix=matrix,
                reason=f"training_weeks={matrix.training_weeks} < {self.MIN_TRAINING_WEEKS}",
            )

        log_matrix = np.log1p(matrix.matrix)                  # log1p handles zeros gracefully
        model = VAR(log_matrix)
        lag_order = min(self.MAX_LAG, model.select_order(maxlags=self.MAX_LAG).aic)
        lag_order = max(1, lag_order)                         # guard against degenerate select
        results = model.fit(lag_order)

        return FittedVARModel(
            statsmodels_results=results,
            lag_order=lag_order,
            training_matrix=matrix,
            transform="log1p",
        )
```

Notes:
- `log1p` is used (rather than raw `log`) to handle zero-valued weeks (e.g., a KPI reporting 0 conversions). `expm1` inverts it in the forecast engine.
- AIC is the default selection metric (AIC tends to prefer slightly higher lag orders than BIC; for 4-dim VAR on weekly data AIC is a standard choice).
- `MAX_LAG=8` caps the influence window at 2 months — longer lags in weekly VAR overfit on moderate-history accounts.

### 5.4 Forecast production

```python
def produce_baselines(
    fitted: FittedVARModel | FlatBaselineModel,
    now: datetime,
) -> list[Baseline]:
    if isinstance(fitted, FlatBaselineModel):
        return [_flat_baseline_for_kpi(fitted, kpi_id, now) for kpi_id in fitted.kpi_ids]

    horizon_log, ci_low_log, ci_high_log = fitted.statsmodels_results.forecast_interval(
        y=fitted.last_observations(),
        steps=12,
        alpha=0.20,
    )
    # Invert log1p: natural = expm1(log_forecast)
    horizon = np.expm1(horizon_log)
    ci_low = np.expm1(ci_low_log).clip(min=0.0)              # non-negative KPIs
    ci_high = np.expm1(ci_high_log)

    model_version = f"var-p{fitted.lag_order}-{now.date().isoformat()}"
    confidence = _confidence_from_weeks(fitted.training_matrix.training_weeks)

    baselines = []
    for kpi_idx, kpi_id in enumerate(fitted.training_matrix.kpi_ids):
        horizon_points = [
            ForecastPoint(
                week_start=_future_week(now, step),
                value=float(horizon[step, kpi_idx]),
                ci_low=float(ci_low[step, kpi_idx]),
                ci_high=float(ci_high[step, kpi_idx]),
            )
            for step in range(12)
        ]
        baselines.append(Baseline(
            account_id=fitted.training_matrix.account_id,
            kpi_id=kpi_id,
            generated_at=now,
            model_version=model_version,
            horizon_weeks=12,
            horizon=horizon_points,
            confidence_level=confidence,
            training_weeks=fitted.training_matrix.training_weeks,
            training_inputs=VARTrainingInputsSnapshot(...),
        ))
    return baselines
```

### 5.5 Retrain orchestration + persistence

```python
@safe_weave_op(name="sar_e.var_retrain")
async def retrain(account_id: str) -> RetrainResponse:
    start = time.monotonic()
    config = await get_sar_e_config(account_id)
    if not config.enabled:
        return RetrainResponse(outcome="skipped_disabled", ...)

    matrix = await assemble_training_matrix(account_id)
    if matrix.training_weeks == 0:
        return RetrainResponse(outcome="skipped_no_mapping", ...)

    fitted = VAREstimator().fit(matrix)
    now = datetime.utcnow()
    baselines = produce_baselines(fitted, now)

    async with firestore_client.batch() as batch:
        for baseline in baselines:
            batch.set(_baseline_doc(account_id, baseline.kpi_id), baseline.model_dump(mode="json"))

    duration_ms = int((time.monotonic() - start) * 1000)
    return RetrainResponse(
        kpi_ids=matrix.kpi_ids,
        training_weeks=matrix.training_weeks,
        lag_order=fitted.lag_order if isinstance(fitted, FittedVARModel) else 0,
        model_version=baselines[0].model_version,
        confidence_level=baselines[0].confidence_level,
        duration_ms=duration_ms,
        outcome="trained" if isinstance(fitted, FittedVARModel) else "flat_baseline",
    )
```

Weave span captures `{account_id_hash, training_weeks, lag_order, fit_aic, fit_bic, confidence_level, duration_ms, outcome}`.

### 5.6 Weekly automation chain

Extend SE-PRD-02's `create_weekly_ingestion_automation` to append:

```
retrain_task:
  assignee_type: "agent"
  agent_name: "sar_e_retrain"
  depends_on: [ingest_task]
  context:
    account_id: {account_id}
```

The `sar_e_retrain` glue agent has one function tool that calls `POST /internal/sar-e/retrain-var` with `{account_id}`. On failure (VAR fit exception, Firestore write error), the task is marked failed and the Automations UI surfaces it; SAR-E's baselines are unchanged. Next Monday's run tries again.

### 5.7 Ad-hoc retrain path

Admin-triggered retrain (e.g., after a mapping change that invalidates cached baselines) calls `POST /internal/sar-e/retrain-var` directly — same endpoint, OIDC-authed, same body. No user-facing UI in v1; invoked via `curl`/the runbook in SE-PRD-07.

## 6. API contract (owned here)

| Method | Path | Purpose | Role |
|---|---|---|---|
| `GET` | `/api/v1/sar-e/{account_id}/forecasts/baseline` | Read `BaselineBundle` (all 4 KPIs) | viewer |
| `POST` | `/api/v1/internal/sar-e/retrain-var` | Fit + persist baselines. OIDC-authed; called by the weekly automation + ad-hoc admin runs. | internal |

`GET /forecasts/baseline` is idempotent and cache-friendly: response `Cache-Control: max-age=30, public` (30-second TTL — aligned with the frontend's bundle cache; see PE-PRD-03's `useSimulations` 30s stale time). When a retrain completes, the Performance API emits a `sar-e.baseline_updated` event (in-process pub/sub or a Firestore doc write that the frontend polls via ETag — SE-PRD-06 decides); this PRD just ensures the new `Baseline` is written atomically and the `Cache-Control` is short.

## 7. Acceptance criteria

1. **Fresh account, zero history.** `/internal/sar-e/retrain-var` on a newly-set-up account with 0 weeks of data returns `{outcome: "flat_baseline", confidence_level: "low", training_weeks: 0}` without raising; 4 `Baseline` docs are written with `horizon[i].value = 0` for all i (no data → zero-forecast by convention) and wide CI.
2. **Partial history (<26 weeks).** On an account with 10 weeks of complete history, retrain returns `outcome: "flat_baseline", training_weeks: 10`; each baseline's horizon is the per-KPI mean of the 4 most-recent complete weeks; `confidence_level="low"`; CI is `mean ± 2σ`.
3. **Full history (≥52 weeks).** On 104 weeks × 4 KPIs of synthetic data (known stationary process), retrain returns `outcome: "trained", confidence_level: "high"`; `horizon` has 12 points per KPI; forecast values are within ±10% of the known true mean (sanity check, not a stats test); `lag_order` in `[1, 8]`.
4. **Lag recovery on known AR(1).** Fit on a synthetic AR(1) process (lag 1) with 100 weeks of data; assert `lag_order == 1` via AIC.
5. **Log-scale roundtrip correctness.** Fit on a series of integer counts in `[0, 10000]`; assert that re-applying `log1p` to `ForecastPoint.value` and running `forecast_interval` produces a result that, when `expm1`-inverted, matches the original `ForecastPoint.value` to 1e-9.
6. **Partial-week rows excluded.** A KPI time series with 53 rows (52 complete + 1 `is_partial=true`) produces a training matrix of exactly 52 rows; the partial row does not influence the fit.
7. **Under-covered-channel traceability.** `ChannelCoverage` flags channel `X` below threshold; retrain produces baselines where each `Baseline.training_inputs.excluded_channels` contains `X`. (The actual exclusion at matrix level is a v1.1 follow-up; the traceability field exists and is populated from day one.)
8. **`GET /forecasts/baseline` happy path.** On an account with 4 baselines, returns `BaselineBundle` with 4 entries; each with 12 `ForecastPoint`s; response cache-control `max-age=30`.
9. **`GET /forecasts/baseline` pre-first-retrain.** On a freshly-set-up account whose backfill is still running, the endpoint returns `{baselines: {}, horizon_weeks: 12, generated_at: null}` with HTTP 200 (not 404). Analysis + Simulations tabs render a "baseline computing" banner on this shape.
10. **OIDC gate on retrain.** `POST /internal/sar-e/retrain-var` without an OIDC token returns 401; with a mis-audience token returns 403.
11. **Enabled-gate on retrain.** On an account with `sar_e_config.enabled=false`, retrain returns `{outcome: "skipped_disabled"}` in under 50ms; no baselines are written.
12. **No-mapping gate.** On an enabled account with `FunnelStageMapping.version=0`, retrain returns `{outcome: "skipped_no_mapping"}`; no baselines are written.
13. **Weekly automation chains ingest → retrain.** After extending `create_weekly_ingestion_automation`, the seeded plan has `retrain_task` depending on `ingest_task`; simulating a Monday run executes both; 4 `Baseline` docs are written at plan completion.
14. **Model version tagging.** `Baseline.model_version` matches `^var-p[0-9]+-[0-9]{4}-[0-9]{2}-[0-9]{2}$`; for flat-baseline fallback, matches `^flat-[0-9]{4}-[0-9]{2}-[0-9]{2}$`.
15. **Weave span.** `sar_e.var_retrain` appears in Weave with attributes `{account_id_hash, training_weeks, lag_order, confidence_level, duration_ms, outcome}`. No PII; `account_id` is hashed.
16. **Perf target.** Retraining on 104 weeks × 4 KPIs completes in ≤10 min p95 on a standard uvicorn worker (single process, no GPU). Measured via `test_sar_e_retrain_perf.py` with a sample size of 20 runs.
17. **Baseline overwrites are atomic.** Two concurrent retrain calls for the same account produce a consistent final state — the last-to-commit wins; no interleaved half-written baselines.
18. **Account deletion.** Deleting an account removes all `baselines/*` rows (covered by the account-deletion sweep extension or DM-PRD-05 `recursive_delete`).
19. **Shape B registration + index.** `baselines` appears in `_migrate_shape_b/resources.py`.
20. **Tooling gates.** `make lint`, `mypy`, `ruff`, `codespell`, and the `pytest` suite all pass.

## 8. Test plan

**Unit tests — VAREstimator** (`test_sar_e_var_estimator.py`):
- Fit on synthetic AR(1) process with 100 weeks → recovers lag 1; coefficient within ±10% of true
- Fit on synthetic VAR(2) process with 100 weeks → recovers lag 2
- Fit on 10 weeks of data → returns `FlatBaselineModel` without raising
- Fit on 30 weeks of data → returns `FittedVARModel` (threshold: exactly 26 weeks is accepted)
- Max-lag cap: fit on 200 weeks of a process with true lag 15 → returns lag ≤ 8
- log1p / expm1 roundtrip exactness

**Unit tests — ForecastEngine** (`test_sar_e_forecast_engine.py`):
- `produce_baselines(FittedVARModel, now)` returns 4 baselines (one per KPI) each with 12 `ForecastPoint`s
- CI bounds: `ci_low <= value <= ci_high` for every point
- Non-negative clamp: `ci_low >= 0` for all points
- Flat baseline: horizon values equal the last-4-weeks mean; CI = mean ± 2σ
- Model-version string format

**Unit tests — Training input** (`test_sar_e_training_input.py`):
- 4 KPIs × 100 weeks each with staggered start dates → aligned matrix has the min overlap
- 4 KPIs × 53 weeks where 1 week is `is_partial=true` → matrix has 52 rows
- Disabled account → `training_weeks=0`, `reason="disabled"`
- No mapping → `training_weeks=0`, `reason="no_mapping"`
- `excluded_channels` populated from `ChannelCoverage` flags

**Integration tests — retrain endpoint** (`test_sar_e_retrain_endpoint.py`):
- Happy path on 104 weeks × 4 KPIs → 4 baselines written with `confidence_level="high"`
- `<26 weeks` → flat baselines written with `confidence_level="low"`
- Disabled account → `outcome="skipped_disabled"`; no writes
- Concurrent retrains (two simultaneous calls) → final state consistent
- OIDC auth: wrong audience → 403

**Integration tests — forecasts endpoint** (`test_sar_e_forecasts_baseline_endpoint.py`):
- 4 baselines exist → returns all 4
- 0 baselines → returns `{baselines: {}, ...}` with 200
- Cache-Control header present
- Stale baseline (`generated_at` > 8 days ago) still returns; staleness is a frontend concern

**Integration tests — weekly automation** (`test_sar_e_weekly_automation_retrain.py`):
- Run `create_weekly_ingestion_automation` → inspect the plan → assert `retrain_task` depends on `ingest_task`
- Simulate a Monday trigger → both tasks execute in order → 4 `Baseline` docs present at plan completion

**Perf test** (`test_sar_e_retrain_perf.py`):
- Seed 104 weeks × 4 KPIs of synthetic data
- Run retrain 20 times
- Assert p95 duration ≤10 min and mean ≤5 min

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| **statsmodels VAR convergence failure on pathological data.** Highly collinear KPIs or near-constant series can fail to converge. | `VAREstimator.fit` catches `ValueError` / `np.linalg.LinAlgError` from statsmodels and falls back to the flat-baseline model. Logs the failure via a Weave attribute so Diagnostics can surface it. |
| **Log-scale bias.** `expm1(E[log(x)]) ≠ E[x]` — the median-unbiased forecast underestimates the mean for skewed series. | Accepted for v1. The 80% prediction interval captures most of the asymmetry. Revisit if users report systematic underforecasting. |
| **Retrain duration on large accounts.** 2 years × 4 KPIs × 1 lag = trivial. But an account that eventually pushes horizon to 26 weeks + adds KPIs could slow retrain. | The weekly retrain runs async in the automation; no user-visible impact. Perf test caps v1 at 10min p95. A circuit breaker in the glue agent skips retrain if the previous run took >20 min. |
| **VAR lag selection instability week-over-week.** AIC may pick lag 2 one week and lag 3 the next as new data arrives. | Users see only the forecast values, not the lag; stability of lag across retrains is not a user-visible contract. `model_version` string captures the chosen lag for debugging. |
| **Under-covered-channel exclusion at matrix level deferred.** The v1 ship drops the channel only if the KPI was channel-decomposed at ingestion time — which SE-PRD-02 doesn't do. First weekly retrain on a fresh account is channel-blind. | Documented in §5.2. `Baseline.training_inputs.excluded_channels` is populated from `ChannelCoverage` regardless, so the field is available for surfacing in Diagnostics (PE-PRD-07). v1.1 follow-up extends SE-PRD-02 to emit per-channel rows. |
| **Concurrent retrain calls.** Two admins trigger ad-hoc retrain simultaneously. | Firestore batch writes are atomic per-doc; the last-to-commit wins per KPI. No corruption; acceptable. |
| **statsmodels upgrade breaks API.** `VAR.select_order` API has changed across versions. | Pin `statsmodels>=0.14.0,<0.15.0` initially; test upgrades in CI with `pytest api/tests/unit/test_sar_e_var_estimator.py` gating. |
| **glue-agent overhead.** Routing retrain through an LLM-backed ADK agent adds ~1-2s of Gemini latency + cost per weekly run. | Use `gemini-2.0-flash` with a short instruction; cost is ~$0.001/call; latency is dwarfed by retrain itself. If the agent is elided in favor of direct orchestrator → retrain-endpoint call, the `sar_e.var_retrain` Weave span still anchors observability. |
| **`Baseline.horizon` drift vs. actuals.** If users see baseline forecasts diverge badly from actuals, they lose trust. | Diagnostics tab (PE-PRD-07) surfaces `confidence_level` + "retrain-needed" flag (e.g., if last retrain >14 days ago or actuals drift >3σ). Out of scope here beyond emitting `generated_at` + `training_weeks`. |

### Open questions

1. **Should we expose AIC/BIC in the API?** v1: no — internal only, captured in `training_inputs`. Revisit if Diagnostics wants to surface "model quality" beyond `confidence_level`.
2. **What happens if the mapping changes mid-week (before the Monday retrain fires)?** v1: the Monday retrain reads the then-current mapping. Analytical queries (SE-PRD-06) resolve historical mappings per-week, so the trendline remains coherent even across a mapping switch. No forced retrain on mapping change in v1.
3. **Should we expose `/forecasts/baseline?kpi_id=X` for single-KPI reads?** v1: no — always returns all 4 (small payload; simpler contract).
4. **Should the flat baseline CI be `±2σ` or the wider `±3σ`?** v1: `±2σ` (80% interval roughly aligns with the VAR's 80% PI). Revisit if users report "low confidence" forecasts look too narrow.

## 10. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md) §6 SE-PRD-03
- Upstream: [SE-PRD-01](./SE-PRD-01-configuration-foundation.md), [SE-PRD-02](./SE-PRD-02-weekly-kpi-ingestion.md)
- Downstream: [SE-PRD-04](./SE-PRD-04-irf-scenarios.md), [SE-PRD-05](./SE-PRD-05-target-derivation-specialist.md), [SE-PRD-06](./SE-PRD-06-analytical-query-layer.md), [PE-PRD-03](../../performance/projects/PE-PRD-03-simulations-tab.md), [PE-PRD-07](../../performance/projects/PE-PRD-07-diagnostics-tab.md)
- Agent factory: [AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) — the `sar_e_retrain` glue agent is factory-assembled
- Automations: [A-PRD-01](../../automations/projects/A-PRD-01-data-model-and-api-extensions.md), [A-PRD-02](../../automations/projects/A-PRD-02-recurring-scheduler-and-run-engine.md)
- statsmodels VAR: https://www.statsmodels.org/stable/vector_ar.html (reference, not used at runtime for fetches)
- CLAUDE.md rules in scope: PY-1, PY-2, PY-3, PY-5, PY-7; C-1, C-2, C-4; D-2, D-5; T-1, T-3, T-4, T-5, T-6, T-7, T-8; G-1
