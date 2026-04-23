# SE-PRD-04 — Scenario Propagation (IRF)

**Status:** Blocked — resumes once SE-PRD-03 ships
**Owner team:** SAR-E component team (backend / applied stats)
**Blocked by:** SE-PRD-03 (`FittedVARModel` produces the MA representation IRF integrates; `Baseline` persistence pattern is reused here for `irf_coefficients` snapshots)
**Blocks:** SE-PRD-05 (Target derivation specialist reads `Baseline` + calls `/scenarios` to evaluate user plans); PE-PRD-03 (Simulations tab's "Run Simulation" button posts to `/scenarios` transitively via the Performance `/simulations/run` composite endpoint)
**Estimated effort:** 3 days

---

## 1. Context

SE-PRD-03 made SAR-E forecast. This PRD makes it answer "what if?". The Simulations tab's user story is: "I plan to change my planned activities — show me how the funnel KPIs would likely respond over the next 12 weeks." The math is Impulse Response Functions (IRF) propagated off the trained VAR. Given a list of per-(kpi_id, week) override values, compute the resulting trajectory at every week of the horizon, with baseline / scenario / incremental values per KPI per week.

Three facts shape the design:

1. **IRF coefficients are derived, persisted, and never regenerated on request.** The MA representation (`VAR.ma_rep(maxn=12)`) is computed once per retrain and snapshotted to `accounts/{account_id}/irf_coefficients/{model_version}`. `POST /scenarios` reads the snapshot tied to the current `Baseline.model_version`; no retrain or matrix inversion on the hot path. p99 latency target ≤500ms at 100 concurrent requests.
2. **Overrides and responses are expressed in natural units. The propagation itself runs in log scale.** A user planning to spend $50k more on unbranded search clicks wants to express that in raw dollars; the API validates, converts `log1p(value) - log1p(baseline)` internally, propagates, and emits natural-scale results via `expm1`. The log scale matches the training transform from SE-PRD-03 (§5.3). Without this symmetry the propagation is numerically wrong.
3. **Scenarios compose; they do not persist.** Every call to `POST /scenarios` is stateless — it returns the computed trajectory and writes nothing. SE-PRD-05's Target derivation specialist invokes `/scenarios` multiple times during reasoning; each call is independent. This is intentional; persistence would require snapshot lifecycle management that the product doesn't yet need.

The IRF math: given a VAR(p) fit on 4 KPIs, the MA(∞) representation gives the impulse response — how a unit shock to KPI j at week 0 propagates to KPI i at week h. Linearity of VARs means a set of overrides at various weeks composes by superposition: trajectory = baseline + sum over (kpi_j, week_k) of override_delta_jk * IRF_matrix[h - k, i, j] for h ≥ k. We clamp at natural-scale zero for non-negative KPIs.

## 2. Scope

### In scope

- **`ScenarioOverride` + `ScenarioDataPoint` + `ScenarioResponse` Pydantic models** in `api/src/kene_api/models/sar_e_models.py`:
  - `ScenarioOverride { kpi_id, week_start, value }` — user-supplied override in natural units; value is the target for that week (the delta is computed server-side as `log1p(value) - log1p(baseline[kpi_id][week_start].value)`)
  - `ScenarioDataPoint { week_start, kpi_id, baseline, scenario, incremental }` — 48 entries (12 weeks × 4 KPIs)
  - `ScenarioResponse { account_id, overrides, data_points, computed_at, model_version }`
- **`IRFEngine` class** in `api/src/kene_api/services/sar_e_irf_engine.py`:
  - `compute_ma_representation(fitted: FittedVARModel, horizon: int = 12) -> np.ndarray` with shape `(horizon+1, K, K)` where K=4 KPIs
  - `propagate(overrides: list[ScenarioOverride], baseline_matrix: np.ndarray, ma_rep: np.ndarray, kpi_index: dict[str, int]) -> np.ndarray` returning the natural-scale scenario matrix `(horizon, K)`
  - Flat-baseline fallback: if the fitted model is `FlatBaselineModel`, `compute_ma_representation` returns an identity-impulse response (only the direct-shock week carries the override; no cross-KPI propagation). Scenarios still compute but incremental ≡ 0 for all off-override cells.
- **`irf_coefficients` snapshot persistence** at `accounts/{account_id}/irf_coefficients/{model_version}`:
  - `IRFCoefficients { account_id, model_version, horizon_weeks, kpi_order: list[str], ma_rep: list[list[list[float]]], generated_at }`
  - `kpi_order` locks the matrix axis positions so `ma_rep[h][i][j]` is always "response of KPI kpi_order[i] at week h to a unit log-shock of KPI kpi_order[j] at week 0"
  - One doc per retrain; prior snapshots retained (addressable by `model_version`) so in-flight `/scenarios` calls with a stale `model_version` continue to work. Retention: keep latest 4 (roughly one month of weekly retrains).
- **Extend `sar_e_retrain_service` (SE-PRD-03)** — after persisting `Baseline` docs, also compute + persist the IRF snapshot. Runs inside the same retrain span; adds one `irf_coefficients` write per retrain.
- **`/api/v1/sar-e/{account_id}/scenarios`** (POST):
  - Body: `{overrides: list[ScenarioOverride]}` — 1 to 48 overrides, each referencing an existing mapped KPI + a week within the 12-week horizon starting from next ISO week
  - Reads the current `Baseline` bundle + the matching `irf_coefficients` snapshot (by `Baseline.model_version`)
  - Validates: `kpi_id` in the current mapping; `week_start` within `[next_monday, next_monday + 12 weeks)`; `value >= 0` (non-negative KPIs); no duplicate `(kpi_id, week_start)`; total payload size ≤100 rows
  - Propagates; returns 48 data points (one per `(kpi_id, week)` in the 12-week grid) with `baseline`, `scenario`, and `incremental = scenario - baseline` fields
  - p99 ≤500ms at 100 concurrent requests
- **Natural↔log conversion at the API boundary** — covered in §5.3 below
- **Weave span `sar_e.scenarios.compute`** — attributes `{account_id_hash, override_count, model_version, duration_ms}`. No PII; no raw override values (override count only).
- **Tests**:
  - Unit: IRF engine on synthetic VAR(1) data with known closed-form IRF → propagation recovers the true trajectory to 1e-9
  - Unit: superposition — compute scenarios A and B separately, then A+B together; assert `incremental(A+B) == incremental(A) + incremental(B)` to 1e-9
  - Unit: flat-baseline fallback — IRF is identity; overrides only change their own `(kpi_id, week_start)` cell's scenario value; all other cells have `incremental == 0`
  - Unit: log↔natural roundtrip — overrides expressed in natural units, delta computed correctly in log space, re-expressed in natural units with `expm1`
  - Integration: seed a retrained account; `POST /scenarios` with 5 overrides; assert 48 `ScenarioDataPoint`s returned; assert `baseline` values match the persisted `Baseline.horizon` values exactly
  - Integration: 100 concurrent `/scenarios` calls → p99 ≤500ms
  - Integration: payload-size guard (101 overrides → 413 Payload Too Large)
  - Integration: stale-`model_version` handling (override references a KPI valid at baseline-generate time but dropped from mapping after) — returns 409 Conflict with a refetch hint

### Out of scope (handled by other PRDs)

- VAR training itself (SE-PRD-03)
- Target derivation — the specialist calls `/scenarios` as one of its tools (SE-PRD-05)
- Persistence of scenario results — stateless
- User-authored freeform scenarios (e.g., "halve my budget across all channels") — v1 accepts per-KPI-per-week value overrides only; budget-driven scenarios are a Skills concern (implementation-plan §8 Non-goals)
- IRF-based variance decomposition / Granger causality reports — deferred; the "statistical association only" invariant (SE-PRD-05) discourages them anyway
- Multi-step historical scenarios ("what if last quarter had been different?") — forecast-only in v1

## 3. Dependencies

- **SE-PRD-03:** `FittedVARModel`, `FlatBaselineModel`, `Baseline`, retrain service. This PRD extends the retrain path with one additional step (IRF snapshot write) and adds a new read endpoint.
- **statsmodels `VAR.ma_rep(maxn)`:** returns the moving-average representation as a `(maxn+1, K, K)` array. Verified API for `statsmodels >= 0.14.0`; pinned by SE-PRD-03.
- **numpy:** matrix operations for `propagate`.
- **Automations / Agentic Harness:** none directly — the IRF snapshot is written by the retrain service extension; no new task graphs.
- **Existing files to study:**
  - `api/src/kene_api/services/sar_e_retrain_service.py` (SE-PRD-03) — extension point
  - `api/src/kene_api/services/sar_e_forecast_engine.py` (SE-PRD-03) — reused log↔natural conversion helpers

## 4. Data contract

### 4.1 Scenario models

```python
class ScenarioOverride(BaseModel):
    kpi_id: str
    week_start: date                                         # Monday of an ISO week in the 12-week horizon
    value: float = Field(..., ge=0)                          # natural units; v1 assumes non-negative KPIs


class ScenarioDataPoint(BaseModel):
    week_start: date
    kpi_id: str
    baseline: float
    scenario: float
    incremental: float                                       # scenario - baseline


class ScenarioRequest(BaseModel):
    overrides: list[ScenarioOverride] = Field(..., min_length=1, max_length=100)

    @model_validator(mode="after")
    def no_duplicate_override_keys(self) -> "ScenarioRequest":
        seen = set()
        for override in self.overrides:
            key = (override.kpi_id, override.week_start)
            if key in seen:
                raise ValueError(f"duplicate override for {key}")
            seen.add(key)
        return self


class ScenarioResponse(BaseModel):
    account_id: str
    overrides: list[ScenarioOverride]                        # echoed back for caller traceability
    data_points: list[ScenarioDataPoint]                     # 48 entries = 12 weeks × 4 KPIs
    computed_at: datetime
    model_version: str                                       # matches the Baseline used
```

### 4.2 IRF snapshot model

```python
class IRFCoefficients(BaseModel):
    account_id: str
    model_version: str
    horizon_weeks: int                                       # always 12 in v1
    kpi_order: list[str]                                     # axis-ordered KPI ids
    ma_rep: list[list[list[float]]]                          # shape (horizon+1, K, K)
    generated_at: datetime
```

The `ma_rep[h][i][j]` is the response of KPI `kpi_order[i]` at week `h` to a unit log-shock of KPI `kpi_order[j]` at week 0. `h=0` is contemporaneous (the identity matrix for orthogonalized IRF; for non-orthogonalized we return the `A^0 = I` contemporaneous case).

### 4.3 Firestore layout additions

| Path | Shape | Purpose |
|---|---|---|
| `accounts/{account_id}/irf_coefficients/{model_version}` | subcollection | `IRFCoefficients` — keyed by model_version for addressability across retrains |

Register `irf_coefficients` in `_migrate_shape_b/resources.py`. No composite indexes (doc-id lookup).

Retention: the retrain service (extended here) keeps the latest 4 snapshots and deletes older ones on each retrain write. 4 × (roughly one per week) ≈ 1 month of history, enough to let any in-flight `/scenarios` call with a stale `model_version` finish cleanly.

## 5. Implementation outline

| Action | File |
|---|---|
| Modify | `api/src/kene_api/models/sar_e_models.py` — add scenario + IRF models |
| Create | `api/src/kene_api/services/sar_e_irf_engine.py` — `compute_ma_representation`, `propagate` |
| Modify | `api/src/kene_api/services/sar_e_retrain_service.py` — after baselines persist, compute + persist `IRFCoefficients` + trim to latest 4 |
| Create | `api/src/kene_api/services/sar_e_scenario_service.py` — load baseline + IRF + propagate |
| Modify | `api/src/kene_api/routers/sar_e_forecasts.py` — add `POST /scenarios` endpoint |
| Modify | `api/src/_migrate_shape_b/resources.py` — register `irf_coefficients` |
| Create | `api/tests/unit/test_sar_e_irf_engine.py` |
| Create | `api/tests/unit/test_sar_e_scenario_service.py` |
| Create | `api/tests/integration/test_sar_e_scenarios_endpoint.py` |
| Create | `api/tests/perf/test_sar_e_scenarios_load.py` — 100 concurrent → p99 ≤500ms |

### 5.1 MA representation

```python
def compute_ma_representation(
    fitted: FittedVARModel | FlatBaselineModel,
    horizon: int = 12,
) -> np.ndarray:
    if isinstance(fitted, FlatBaselineModel):
        K = len(fitted.kpi_ids)
        ma = np.zeros((horizon + 1, K, K))
        ma[0] = np.eye(K)                                    # identity at h=0
        return ma

    ma = fitted.statsmodels_results.ma_rep(maxn=horizon)
    assert ma.shape == (horizon + 1, 4, 4), f"unexpected MA shape {ma.shape}"
    return ma
```

### 5.2 Propagation

```python
def propagate(
    overrides: list[ScenarioOverride],
    baseline: dict[str, list[ForecastPoint]],                # kpi_id -> 12 ForecastPoints
    ma_rep: np.ndarray,                                      # (horizon+1, K, K)
    kpi_order: list[str],
) -> list[ScenarioDataPoint]:
    K = len(kpi_order)
    horizon = ma_rep.shape[0] - 1
    idx = {kpi_id: i for i, kpi_id in enumerate(kpi_order)}
    week_index = {bp.week_start: w for w, bp in enumerate(baseline[kpi_order[0]])}

    # Baseline matrix in log space: shape (horizon, K)
    baseline_log = np.zeros((horizon, K))
    for i, kpi_id in enumerate(kpi_order):
        for w, point in enumerate(baseline[kpi_id]):
            baseline_log[w, i] = np.log1p(point.value)

    # Compute per-override log-space delta and accumulate into scenario_log
    scenario_log = baseline_log.copy()
    for override in overrides:
        j = idx[override.kpi_id]
        w_override = week_index[override.week_start]
        delta_j = np.log1p(override.value) - baseline_log[w_override, j]
        # Propagate to all weeks h >= w_override for all KPIs i
        for h in range(w_override, horizon):
            for i in range(K):
                scenario_log[h, i] += ma_rep[h - w_override, i, j] * delta_j

    scenario_natural = np.expm1(scenario_log).clip(min=0.0)
    baseline_natural = np.expm1(baseline_log).clip(min=0.0)  # round-trip safety

    data_points: list[ScenarioDataPoint] = []
    for w in range(horizon):
        week_start = baseline[kpi_order[0]][w].week_start
        for i, kpi_id in enumerate(kpi_order):
            data_points.append(ScenarioDataPoint(
                week_start=week_start,
                kpi_id=kpi_id,
                baseline=float(baseline_natural[w, i]),
                scenario=float(scenario_natural[w, i]),
                incremental=float(scenario_natural[w, i] - baseline_natural[w, i]),
            ))
    return data_points
```

Performance note: the double loop `for h / for i` over 12×4 per override, with ≤100 overrides, is ≤4800 FLOPs — trivial. The expensive parts are the Firestore reads (baseline + IRF snapshot); each is a single doc read per KPI / per model_version, so 5 reads total. Cache the `IRFCoefficients` + the `Baseline` bundle per account in a 30-second in-process LRU to absorb burst traffic.

### 5.3 Natural↔log boundary

- **Input:** `ScenarioOverride.value` is always natural units (dollars, counts, ...). The service converts via `log1p` at the start of propagation.
- **Baseline values** already exist in natural units on `Baseline.horizon[].value`; convert to log space in-service, propagate, convert back.
- **Output:** `ScenarioDataPoint.baseline / scenario / incremental` are all natural units. `incremental` is the natural-scale difference, not `expm1(log_scenario - log_baseline)`. (The log-scale delta is a different quantity; returning it would violate the contract and would mislead the UI chart.)

### 5.4 Retrain-service extension

After SE-PRD-03's retrain persists 4 `Baseline` docs:

```python
ma_rep = irf_engine.compute_ma_representation(fitted, horizon=12)
irf_doc = IRFCoefficients(
    account_id=account_id,
    model_version=baselines[0].model_version,
    horizon_weeks=12,
    kpi_order=matrix.kpi_ids,
    ma_rep=ma_rep.tolist(),
    generated_at=now,
)
await firestore_client.set(_irf_doc(account_id, irf_doc.model_version), irf_doc.model_dump(mode="json"))
await _trim_irf_snapshots(account_id, keep=4)
```

Snapshot retention runs every retrain. Trim is a single collection-group query + ordered delete — cheap.

### 5.5 Scenario endpoint request flow

```python
@router.post("/{account_id}/scenarios", response_model=ScenarioResponse)
async def compute_scenario(account_id: str, request: ScenarioRequest, ...) -> ScenarioResponse:
    # 1. Load baselines (cached, 30s TTL)
    baseline_bundle = await get_baseline_bundle(account_id)
    if not baseline_bundle.baselines:
        raise HTTPException(409, "no baseline available yet; wait for backfill + retrain to complete")

    # 2. Validate overrides against current mapping + horizon
    _validate_overrides(request.overrides, baseline_bundle)

    # 3. Load IRF snapshot matching the baseline's model_version
    model_version = next(iter(baseline_bundle.baselines.values())).model_version
    irf = await get_irf_coefficients(account_id, model_version)
    if irf is None:
        raise HTTPException(409, "IRF snapshot missing for current model_version; retrigger retrain")

    # 4. Propagate
    data_points = irf_engine.propagate(
        overrides=request.overrides,
        baseline={k: b.horizon for k, b in baseline_bundle.baselines.items()},
        ma_rep=np.array(irf.ma_rep),
        kpi_order=irf.kpi_order,
    )

    return ScenarioResponse(
        account_id=account_id,
        overrides=request.overrides,
        data_points=data_points,
        computed_at=datetime.utcnow(),
        model_version=model_version,
    )
```

Weave span wraps the whole function: `sar_e.scenarios.compute` with `{account_id_hash, override_count, model_version, duration_ms}`.

## 6. API contract (owned here)

| Method | Path | Purpose | Role |
|---|---|---|---|
| `POST` | `/api/v1/sar-e/{account_id}/scenarios` | IRF-propagated scenario given overrides | viewer (reading hypothetical trajectories doesn't mutate state) |

Single endpoint. The retrain extension has no new endpoint — it's an internal side effect of `/internal/sar-e/retrain-var` (SE-PRD-03).

Notes:
- Consumed by **PE-PRD-03** transitively via the Performance API's `/simulations/run` composite endpoint.
- Consumed by **SE-PRD-05**'s Target derivation specialist's `evaluate_scenario` tool.

## 7. Acceptance criteria

1. **Retrain persists IRF snapshot.** After `/internal/sar-e/retrain-var` completes on a trained account, `accounts/{account_id}/irf_coefficients/{model_version}` exists with `horizon_weeks=12`, a `kpi_order` of length 4 matching the mapping, and an `ma_rep` of shape (13, 4, 4).
2. **Flat-baseline IRF is identity.** Retrain on a `<26 weeks` account produces an `ma_rep` whose `h=0` slice is the identity matrix and whose `h≥1` slices are zeros.
3. **Snapshot retention.** After 5 retrains on the same account, exactly 4 `irf_coefficients` docs exist (oldest trimmed).
4. **Happy-path scenario.** On a trained account with a current baseline, `POST /scenarios` with a single override `{kpi_id: X, week_start: W, value: V}` returns 48 `ScenarioDataPoint`s; the `(X, W)` row's `scenario` equals `V` to 1e-6; other weeks' responses for KPI X match `baseline[X][h].value * exp(ma_rep[h-w_W, idx(X), idx(X)] * (log1p(V) - log1p(baseline[X][W].value)))` within numerical tolerance.
5. **Superposition.** Running `scenarios(A)` + `scenarios(B)` separately and taking the sum of incrementals produces the same `data_points[i].incremental` values (to 1e-9) as `scenarios(A ∪ B)`. This validates the IRF-as-linear-combination assumption.
6. **Natural↔log roundtrip.** With no overrides supplied (`overrides=[]`), the endpoint would be rejected by the validator (`min_length=1`). With an override where `value == baseline[kpi_id][week_start].value`, the returned `incremental` is `0.0` within 1e-9 for every data point; the `scenario` column equals the `baseline` column exactly.
7. **Validator — unknown KPI.** Override referencing a `kpi_id` not in the current mapping → 422 with field-scoped error. Also rejected if the KPI was mapped at `Baseline.generated_at` but unmapped afterwards — same 422.
8. **Validator — out-of-horizon week.** Override with `week_start` earlier than `next_monday` or `>= next_monday + 12*7 days` → 422.
9. **Validator — duplicate override.** Two overrides with the same `(kpi_id, week_start)` → 422.
10. **Validator — payload size.** >100 overrides → 413 Payload Too Large.
11. **Stale `model_version`.** If the account's `Baseline` and `IRFCoefficients` disagree on `model_version` (e.g., retrain wrote baselines but failed to write IRF), the endpoint returns 409 Conflict with a hint "retrigger retrain".
12. **No-baseline case.** An account pre-first-retrain (empty `baselines/` subcollection) → 409 with a hint "no baseline available yet; wait for backfill + retrain to complete".
13. **Non-negative clamp.** If the propagation would yield a negative scenario value for a non-negative KPI, `scenario` is clamped at 0 and `incremental` reflects the clamp.
14. **Perf target.** 100 concurrent `/scenarios` calls with 20 overrides each return p99 ≤500ms on a single uvicorn worker (no cold cache — warm pool).
15. **Cached reads.** Repeated `/scenarios` calls for the same account within 30 seconds hit the in-process baseline + IRF cache (asserted via mock Firestore call count: 5 reads on the first call, 0 on subsequent calls within TTL).
16. **Weave span.** `sar_e.scenarios.compute` appears with `{account_id_hash, override_count, model_version, duration_ms}`. No raw override values in attributes.
17. **Account deletion.** Deleting an account removes all `irf_coefficients/*` rows.
18. **Shape B registration.** `irf_coefficients` appears in `_migrate_shape_b/resources.py`.
19. **Tooling gates.** `make lint`, `mypy`, `ruff`, `codespell`, pytest all pass.

## 8. Test plan

**Unit tests — IRF engine** (`test_sar_e_irf_engine.py`):
- `compute_ma_representation` on a known AR(1) VAR: MA rep matches closed-form `A^h` for h=0..12
- `compute_ma_representation` on `FlatBaselineModel`: identity at h=0, zeros elsewhere
- `propagate` with single override: scenario matrix matches hand-computed trajectory to 1e-9
- `propagate` with multiple overrides at different weeks: superposition verified against separate-then-sum
- `propagate` with override at week 11 (last horizon week): only week 11 affected (h_override=11 → only h=11 propagation window remains)
- `propagate` with override equal to baseline: incremental ≡ 0, scenario ≡ baseline
- Natural↔log roundtrip: for a baseline value 100, override value 150, the log-space delta is `log1p(150) - log1p(100)`; applied to identity IRF, scenario equals 150 exactly
- Non-negative clamp: negative IRF coefficient + large negative override → scenario clamped at 0

**Unit tests — scenario service** (`test_sar_e_scenario_service.py`):
- Service composes loaders correctly; returns correct `data_points` count (48)
- `model_version` echoed from baseline
- Cache: two sequential calls → 5 Firestore reads then 0

**Integration tests — endpoint** (`test_sar_e_scenarios_endpoint.py`):
- Happy path on a trained account with 5 overrides
- 422 cases: unknown KPI, out-of-horizon week, duplicate override, 0 overrides, 101 overrides (413)
- 409 cases: no baseline, model_version mismatch
- Stale mapping (KPI mapped at baseline-generation, unmapped after) → 422
- Flat-baseline account: scenario responds but incrementals are 0 except for the override cells

**Perf test** (`test_sar_e_scenarios_load.py`):
- 100 concurrent clients, 20 overrides each, 60s duration
- Measure p50 / p95 / p99; assert p99 ≤500ms
- Memory: verify no leak across 10k requests (RSS deltas bounded)

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| **MA representation growth at high lag.** A VAR(8) has an 8-step recursion unfolding into a much longer MA tail; `ma_rep(maxn=12)` is trivial but unbounded maxn could blow up memory. | Hard cap `horizon=12` in v1. Future extension to 26-week horizon extends this to `maxn=26`, still trivial at 4-dim. |
| **Log-scale amplification.** A user enters an override `value=100000` against a baseline of `1`; `log1p(100000) - log1p(1) ≈ 11.5` — a huge shock that propagates large values. | Accepted — the math is correct. The UI should render the chart with a warning if any cell's `scenario / baseline` ratio exceeds 10; that's a PE-PRD-03 concern. |
| **Orthogonalized vs. non-orthogonalized IRF.** statsmodels' `ma_rep` is the non-orthogonalized form. Ordering of KPIs doesn't matter for non-orthogonalized, which is what we want here. | Explicitly document this choice. `kpi_order` on the snapshot is purely for axis positioning, not economic ordering. |
| **Scenario superposition fails if users override the same week twice (at different values) across sequential calls.** Each `/scenarios` call is independent; the result of the second call does not build on the first. | Consistent with the stateless contract. UI (PE-PRD-03) presents the "Run Simulation" as a single fire-and-forget action; no sequencing. |
| **Stale model_version between retrains.** Retrain in flight; a `/scenarios` call reads the old baseline + old IRF; mid-call, retrain commits a new baseline but not yet a new IRF. | Retention of 4 IRF snapshots + keyed read by `model_version` resolves this — the scenario call always reads the IRF matching its baseline. If retrain's IRF write fails entirely, the 409 branch handles it. |
| **Perf under cold cache.** First `/scenarios` call after a Firestore-cache eviction reads 5 docs (4 baselines + 1 IRF). Each read is ~20-50ms → 100-250ms overhead. | Cached within 30s (burst-friendly). For sustained load, Firestore's client-side cache + connection pooling amortize. 500ms p99 is tested under warm pool; spec for cold-cache is "under 1s p99" — documented but not enforced.
| **Baseline mutation during a scenario call.** A retrain completes mid-request and writes a new `Baseline` with different `model_version`. | The request reads baseline once at entry; IRF is read via that same `model_version`. No mid-call re-read; the response is coherent with its declared `model_version`. |
| **Clamp hides information.** When a non-negative KPI scenario clamps at 0, the `incremental` mismatches what the raw math says. | Acceptable — the UI renders `scenario` and `incremental` naturally; users understand "we can't go below zero". Document in the API reference. Revisit if users ever request negative-capable KPIs.

### Open questions

1. **Should we expose an "explain this number" endpoint that returns the per-(override, week) contribution to a scenario cell?** Out of scope for v1; flagged for SE-PRD-05's specialist to surface via natural-language reasoning instead.
2. **Do we need a `/scenarios/batch` endpoint for the specialist to test many overrides in one call?** v1: no — the specialist calls `/scenarios` up to 5 times per derivation; each call is ≤500ms; total fits in the 30s p95 budget for `/targets/derive` (SE-PRD-05). Revisit if the specialist's call count balloons.
3. **Should the response include per-(override, cell) contributions?** Would grow the payload 5×–10×. v1: no; the IRF matrix itself is enough for an explainability surface (not exposed in v1).
4. **When the VAR has 1 lag and user overrides week 11, only week 11 can be affected. Is this surprising?** UI needs to communicate that overrides in the last horizon week have minimal downstream effect. That's a PE-PRD-03 concern; the math here is correct.

## 10. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md) §6 SE-PRD-04
- Upstream: [SE-PRD-03](./SE-PRD-03-var-baseline.md)
- Downstream: [SE-PRD-05](./SE-PRD-05-target-derivation-specialist.md), [PE-PRD-03](../../performance/projects/PE-PRD-03-simulations-tab.md)
- statsmodels VAR `ma_rep`: https://www.statsmodels.org/stable/generated/statsmodels.tsa.vector_ar.var_model.VARResults.ma_rep.html (reference only; not fetched at runtime)
- CLAUDE.md rules in scope: PY-1, PY-2, PY-3, PY-5, PY-7; C-1, C-2, C-4; D-2, D-5; T-1, T-3, T-5, T-6, T-8; G-1
