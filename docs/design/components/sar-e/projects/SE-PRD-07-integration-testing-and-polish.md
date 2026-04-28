# SE-PRD-07 — Integration Testing & Polish

**Status:** Blocked — resumes once SE-PRDs 01–06 ship
**Owner team:** SAR-E component team (backend) + a testing liaison
**Blocked by:** SE-PRD-01 (config surface), SE-PRD-02 (ingestion + backfill-plan), SE-PRD-03 (VAR + baseline), SE-PRD-04 (IRF scenarios), SE-PRD-05 (target derivation specialist), SE-PRD-06 (analytical query layer)
**Blocks:** — (terminal project for the SAR-E component; gates the component's v1 release)
**Estimated effort:** 3 days

---

## 1. Context

SAR-E's six prior PRDs deliver the component in layers: config → ingestion → VAR → IRF → targets → analytics. Each ships with its own unit + integration coverage. This PRD validates the **composition**: an end-to-end flow from account creation through to the Analysis and Simulations tabs rendering real values, plus a set of cross-cutting audits — methodology-language compliance, load, and the future A/B framework for model swaps.

Five deliverables anchor the project:

1. **One end-to-end test that exercises the full lifecycle.** A single pytest run seeds a fresh account, mocks the Integrations + Data Pipeline boundaries, runs the wizard, waits for ingestion, triggers retrain, derives targets, saves them, and queries every analytical surface. The test asserts data presence, correctness, and cache coherence at every stage.
2. **A load test of the critical hot paths.** Scenarios endpoint (SE-PRD-04) and analytical queries (SE-PRD-06) are the two reader-heavy surfaces. Target p99s are documented in the respective PRDs; this project runs them as a CI-adjacent (nightly) Locust load test and gates the release at the stated thresholds.
3. **Methodology-language audit.** Walk every SAR-E response string — specialist output, error messages, frontend-bound payload fields — and assert zero occurrences of the banned causation phrases. This PRD contributes the grep-based CI gate that lands in `make lint`; SE-PRD-05 already enforces the runtime lint on specialist outputs.
4. **Model A/B harness.** A Firestore-backed config toggle lets ops route some percentage of `/targets/derive` calls to a challenger model (`gemini-2.0-flash` initially). Results are captured in Weave with a `challenger=true` tag so we can compare Gemini Pro vs. Flash accuracy + cost without touching code. This PRD ships the harness; actual experiment runs are ops decisions.
5. **Runbook additions to `api/CLAUDE.md`.** Operational knowledge — how to trigger an ad-hoc retrain, how to interpret `confidence_level="low"`, how to inspect the methodology audit trail, how to flip the A/B harness, how to roll back if a retrain corrupts baselines — lives in `api/CLAUDE.md` so on-call can find it without reading PRDs.

## 2. Scope

### In scope

- **End-to-end integration test suite** under `api/tests/integration/test_sar_e_full_lifecycle.py`:
  - One test per lifecycle milestone (pre-wizard / post-wizard / post-backfill / post-retrain / post-derive / post-save) runnable independently against a shared fixture, plus a single "golden-path" test that runs all milestones sequentially
  - Fixture `@pytest.fixture(scope="session") def sar_e_golden_account()` seeds an account, mocks Integrations, mocks Data Pipeline runs to produce deterministic daily Parquet artifacts covering 52 weeks
  - Mocks: Integrations `/connections` + `/credentials`; Data Pipeline `/jobs` + `/run` + `/history-depth`; Gemini Pro (responds from a recorded fixture under `tests/fixtures/gemini_pro_target_derivation/`)
  - Assertions at each milestone verify Firestore state + response shapes
- **Load test harness** `tests/load_test/sar_e_scenarios_locust.py` + `sar_e_analytics_locust.py`:
  - 100 concurrent users, 5-minute steady state
  - Scenarios: `POST /scenarios` with 20 overrides each; 90/10 read-write split (read = funnel snapshot + trendline)
  - Analytics: `GET /analytics/funnel`, `/trendline/Consideration`, `/cost-rollup?dimensions=channel,campaign`; 100/0 read-only
  - Output: a `locust_report.html` uploaded as a CI artifact on nightly runs
  - Gate: p99 ≤500ms on `/scenarios`, p95 <500ms on `/analytics/cost-rollup` (500-task account), p95 <100ms on `/analytics/funnel` + `/trendline/*` (warm cache)
- **Methodology audit CI gate** `api/tests/lint/test_methodology_language.py`:
  - Runs as part of `make lint`
  - Greps `api/src/kene_api/routers/sar_e_*.py`, `api/src/kene_api/services/sar_e_*.py`, `api/src/kene_api/models/sar_e_models.py`, `app/adk/agents/performance_forecasting/**`, and every string literal in them
  - Banned pattern: `\b(caused|because|due to|leads to|results in)\b` (case-insensitive)
  - False-positive allowlist in `tests/lint/methodology_allowlist.txt` for accidental matches (e.g., "duration" contains "due" — but `due\b` + word boundary catches that; allowlist handles the rest)
  - Asserts `grep` count == 0 across the scoped files
- **Model A/B harness**:
  - New Firestore doc `config/sar_e_model_ab` (admin-only, env-wide): `{enabled: bool, challenger_model: str, challenger_traffic_pct: int (0-100), started_at: datetime}`
  - `sar_e_target_derivation.py` reads the doc per-request; routes `challenger_traffic_pct`% of calls to the challenger model via a hash of `account_id + derivation_context_hash` (sticky — the same account+context pair always routes the same way, so an A/B user doesn't flip mid-session)
  - Both responses (champion + challenger when both fire) are stored in Weave with a `variant: "champion" | "challenger"` tag; only the champion's output is returned to the caller
  - Shadow mode: `mode="shadow"` (default) runs the challenger in the background without blocking the response; `mode="active"` returns the challenger's output to the caller for the routed traffic pct
  - Admin endpoint `PUT /api/v1/internal/admin/sar-e/model-ab` (OIDC + super-admin) to update the doc; `GET` returns current state
  - Opt-out: per-account `accounts/{account_id}/sar_e_config.ab_harness_opt_out: bool` (defined on `SarEConfig` in SE-PRD-01 §4.1, default `false`) skips the challenger entirely — used for SLA-sensitive accounts. This PRD reads the field; it does not declare it.
- **Runbook additions** (append to `api/CLAUDE.md`):
  - "SAR-E operations" section covering:
    - How to trigger an ad-hoc VAR retrain (`curl POST /internal/sar-e/retrain-var` + OIDC snippet)
    - How to read `confidence_level` values + what each signifies
    - How to inspect the methodology audit log (Weave filter query + Firestore audit doc path)
    - How to flip the A/B harness (admin endpoint call)
    - How to roll back a bad baseline (delete `baselines/*` + retrigger retrain; or restore from a prior retrain's IRF snapshot which is addressable by `model_version`)
    - How to handle a wizard-failed-mid-setup account (re-run wizard; `/config/setup`'s rollback is idempotent)
    - How to handle a "baseline computing" banner that's stuck (check `PlanRun` status in Automations UI; surface commands)
- **Cache-coherence regression tests** `api/tests/integration/test_sar_e_cache_coherence.py`:
  - Retrain → the trendline + funnel snapshot cache is invalidated
  - Mapping PUT → the mapping resolver cache + analytics cache are both invalidated
  - KPI PATCH → the analytics cache is invalidated
  - Target save → `useTargets`-bound endpoints return the new values on next call
- **Component README** `docs/design/components/sar-e/README.md` — first-pass draft (per CLAUDE.md convention, every component has a README once the component is shipped). Sections: architecture diagram, key abstractions, API contracts, component dependencies, PRD index, and a "verification report" appendix summarizing SE-PRD-07's test results.

### Out of scope (handled by other PRDs)

- Unit tests for individual services — owned by each PRD
- Frontend Playwright coverage of the Performance tabs — PE-PRD-08
- Ingestion retry logic — SE-PRD-02 handles its own retries; this PRD only tests the surface
- Eval harness for the specialist — SE-PRD-05 ships 20 golden cases; this PRD does not grow that list
- Production cost monitoring — ops concern, not a deliverable here
- `ChannelCoverage` threshold tuning — SE-PRD-06's responsibility; v1 hardcodes 0.6

## 3. Dependencies

- All six upstream SE-PRDs
- `tests/load_test/` conventions (Locust) already established (reference `tests/load_test/` per repo layout)
- `api/CLAUDE.md` is the canonical operational runbook
- Gemini Pro test fixture format (recorded responses from a curated 20-case eval set) — SE-PRD-05's responsibility; this PRD consumes them

## 4. Data contract

This PRD does not introduce new persistent data models. The one new Firestore doc is:

```python
class SarEModelABConfig(BaseModel):
    enabled: bool
    challenger_model: str                            # e.g., "gemini-2.0-flash"
    challenger_traffic_pct: int = Field(..., ge=0, le=100)
    mode: Literal["shadow", "active"]
    started_at: datetime
    updated_at: datetime
    updated_by: str                                  # super-admin user_id
```

Path: `config/sar_e_model_ab` (global, not per-account — consistent with other `config/*` singletons in the codebase).

## 5. Implementation outline

| Action | File |
|---|---|
| Create | `api/tests/integration/test_sar_e_full_lifecycle.py` |
| Create | `api/tests/fixtures/sar_e_golden_account.py` — session-scoped fixture |
| Create | `api/tests/fixtures/gemini_pro_target_derivation/` — recorded responses (20 cases) |
| Create | `api/tests/integration/test_sar_e_cache_coherence.py` |
| Create | `api/tests/lint/test_methodology_language.py` |
| Create | `api/tests/lint/methodology_allowlist.txt` |
| Modify | `Makefile` — extend `lint` target to include `pytest api/tests/lint/ -q` |
| Create | `tests/load_test/sar_e_scenarios_locust.py` |
| Create | `tests/load_test/sar_e_analytics_locust.py` |
| Create | `tests/load_test/sar_e_fixtures/seed_load_test_account.py` — seeds the perf-test fixture (one 500-task account) |
| Modify | `api/src/kene_api/services/sar_e_target_derivation.py` (SE-PRD-05) — read `config/sar_e_model_ab` + route challenger traffic |
| Create | `api/src/kene_api/routers/sar_e_admin.py` — `/internal/admin/sar-e/model-ab` endpoints |
| Modify | `api/src/kene_api/main.py` — mount `sar_e_admin.router` |
| Modify | `api/CLAUDE.md` — add "SAR-E operations" section |
| Create | `docs/design/components/sar-e/README.md` — component README (first draft) |

### 5.1 End-to-end test layout

```python
# api/tests/integration/test_sar_e_full_lifecycle.py

@pytest.fixture(scope="module")
async def golden_account(firestore_emulator, integrations_mock, data_pipeline_mock, gemini_pro_mock):
    account_id = await create_account(name="E2E Test Account")
    return account_id


async def test_lifecycle_01_pre_wizard(golden_account):
    resp = await client.get(f"/api/v1/sar-e/{golden_account}/config/status")
    assert resp.json()["enabled"] is False
    assert resp.json()["setup_wizard_completed"] is False
    assert resp.json()["connected_integrations"] == []


async def test_lifecycle_02_after_integration_connect(golden_account):
    # Mock one connection
    integrations_mock.add_connection(golden_account, platform_id="google_analytics")
    data_pipeline_mock.add_job(account_id=golden_account, job_id="ga.unbranded_search_daily", weeks_available=80)
    # ... 3 more jobs

    resp = await client.get(f"/api/v1/sar-e/{golden_account}/config/status")
    assert len(resp.json()["available_kpi_sources"]) == 4


async def test_lifecycle_03_wizard_completion(golden_account):
    # Call /config/backfill-plan then /config/setup
    bfp = await client.post(
        f"/api/v1/sar-e/{golden_account}/config/backfill-plan",
        json={"kpi_source_job_ids": ["ga.unbranded_search_daily", ..., ...]},
    )
    assert bfp.json()["backfill_weeks"] == 52  # from the mocked 80/52/... depths

    setup = await client.post(
        f"/api/v1/sar-e/{golden_account}/config/setup",
        json={"kpis": [...4 KPIs...], "funnel_mapping": {...}, "initial_backfill_weeks": 52},
    )
    assert setup.json()["enabled"] is True
    assert setup.json()["backfill_plan_run_id"] is not None


async def test_lifecycle_04_ingestion_and_retrain(golden_account):
    # Simulate 52 weeks of backfill runs completing
    await simulate_backfill_completion(golden_account)

    # Verify 52×4=208 KPIDataPoints written
    points = await collection_group_count("kpi_time_series", f"account_id={golden_account}")
    assert points == 208

    # Trigger retrain
    retrain = await client.post(
        "/api/v1/internal/sar-e/retrain-var",
        headers=oidc_headers("sar_e_retrain_agent"),
        json={"account_id": golden_account},
    )
    assert retrain.json()["outcome"] == "trained"
    assert retrain.json()["confidence_level"] == "high"

    # Verify 4 baselines + 1 IRF snapshot
    baselines = await subcoll_count(golden_account, "baselines")
    irf = await subcoll_count(golden_account, "irf_coefficients")
    assert baselines == 4
    assert irf == 1


async def test_lifecycle_05_target_derivation(golden_account):
    # Seed a calendar window with 2 promotions + 1 holiday
    await seed_calendar_activities(golden_account, count=3)

    resp = await client.post(
        f"/api/v1/sar-e/{golden_account}/targets/derive",
        json={"period_start": next_monday().isoformat(), "period_end": (next_monday() + timedelta(weeks=12, days=-1)).isoformat()},
    )
    body = resp.json()
    assert len(body["targets"]) == 48
    for target in body["targets"]:
        assert "caused" not in target["methodology_note"].lower()
        assert "because" not in target["reasoning"].lower()


async def test_lifecycle_06_save_as_targets(golden_account):
    # Simulate PE-PRD-03's save flow: POST each target
    derive = await client.post(f"/api/v1/sar-e/{golden_account}/targets/derive", json={...})
    for dt in derive.json()["targets"]:
        await client.post(f"/api/v1/sar-e/{golden_account}/targets", json={
            "kpi_id": dt["kpi_id"],
            "period": dt["period"],
            "value": dt["value"],
            ...
        })

    listing = await client.get(f"/api/v1/sar-e/{golden_account}/targets")
    assert len(listing.json()) == 48


async def test_lifecycle_07_analytical_queries(golden_account):
    funnel = await client.get(
        f"/api/v1/sar-e/{golden_account}/analytics/funnel"
        f"?start={last_monday().isoformat()}&end={last_sunday().isoformat()}&comparison=vs_target"
    )
    assert len(funnel.json()["stages"]) == 4
    for stage in funnel.json()["stages"]:
        assert stage["comparison_value"] is not None  # targets now exist

    trend = await client.get(f"/api/v1/sar-e/{golden_account}/analytics/trendline/Consideration?window_weeks=53")
    assert len(trend.json()["points"]) == 53

    cost = await client.get(
        f"/api/v1/sar-e/{golden_account}/analytics/cost-rollup"
        f"?start={last_monday().isoformat()}&end={next_sunday().isoformat()}&dimensions=channel,campaign"
    )
    assert cost.json()["grand_total"] >= 0


async def test_lifecycle_08_simulations_composite(golden_account):
    # Emulate the Performance API's /simulations/run composite (PE-PRD-03)
    scenarios_resp = await client.post(
        f"/api/v1/sar-e/{golden_account}/scenarios",
        json={"overrides": [
            {"kpi_id": "<consideration_kpi>", "week_start": next_monday().isoformat(), "value": 15000.0},
        ]},
    )
    assert len(scenarios_resp.json()["data_points"]) == 48
```

Each milestone has assertions; together they're the "happy path from zero to Analysis tab."

### 5.2 Methodology lint

```python
# api/tests/lint/test_methodology_language.py

import pathlib
import re

SCOPED_GLOBS = [
    "api/src/kene_api/routers/sar_e_*.py",
    "api/src/kene_api/services/sar_e_*.py",
    "api/src/kene_api/models/sar_e_models.py",
    "app/adk/agents/performance_forecasting/**/*.py",
]

BANNED = re.compile(r"\b(caused|because|due to|leads to|results in|causes|causing)\b", re.I)


def _read_allowlist() -> set[str]:
    path = pathlib.Path("api/tests/lint/methodology_allowlist.txt")
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text().splitlines() if line.strip() and not line.startswith("#")}


def test_no_causation_phrases_in_sar_e_code():
    allowlist = _read_allowlist()
    violations: list[tuple[str, int, str]] = []
    for glob in SCOPED_GLOBS:
        for file in pathlib.Path.cwd().glob(glob):
            for lineno, line in enumerate(file.read_text().splitlines(), start=1):
                if BANNED.search(line):
                    token = f"{file}:{lineno}:{line.strip()}"
                    if token in allowlist:
                        continue
                    violations.append((str(file), lineno, line.strip()))
    assert not violations, (
        f"Methodology drift detected — {len(violations)} banned phrases in SAR-E code:\n"
        + "\n".join(f"  {f}:{n}: {l}" for f, n, l in violations)
    )
```

Allowlist lives at `api/tests/lint/methodology_allowlist.txt`; each line is a `file:lineno:content` token documenting a permitted use (e.g., a comment like `# Runtime linter removes "because" from specialist output`).

### 5.3 A/B harness in the derivation service

```python
async def dispatch_to_specialist(request, account_id, context) -> DeriveResponse:
    ab_config = await load_ab_config()
    acct = await get_sar_e_config(account_id)
    use_challenger = (
        ab_config.enabled
        and not acct.ab_harness_opt_out
        and _route_to_challenger(account_id, context.derivation_context_hash, ab_config.challenger_traffic_pct)
    )

    if use_challenger and ab_config.mode == "active":
        return await _dispatch_with_model(request, account_id, context, model=ab_config.challenger_model, variant="challenger")

    champion_result = await _dispatch_with_model(request, account_id, context, model="gemini-2.0-pro", variant="champion")

    if use_challenger and ab_config.mode == "shadow":
        # fire-and-forget; log to Weave but don't block
        asyncio.create_task(_dispatch_with_model_shadow(request, account_id, context, ab_config.challenger_model))

    return champion_result


def _route_to_challenger(account_id: str, context_hash: str, pct: int) -> bool:
    bucket = int(hashlib.md5(f"{account_id}:{context_hash}".encode()).hexdigest(), 16) % 100
    return bucket < pct
```

Sticky bucketing by `(account_id, context_hash)` prevents a user from flipping mid-derive.

### 5.4 Admin endpoint

```python
# api/src/kene_api/routers/sar_e_admin.py

@router.put("/internal/admin/sar-e/model-ab")
async def update_ab_config(body: SarEModelABConfig, user=Depends(require_super_admin)) -> SarEModelABConfig:
    # The A/B config doc is global (`config/sar_e_model_ab`), but the audit registry only registers
    # `(parent_kind="account", audit_subcollection="sar_e_audit", ..., action="ab_config_update")`.
    # Until DM-PRD-07's registry grows a global-scope `sar_e_audit` descriptor, this PRD uses a
    # synthetic `parent_kind="account"` with `parent_id="__system__"` (matching the convention
    # other super-admin actions use) so the action stays inside the registered tuple set.
    await write_audit(
        parent_kind="account",
        parent_id="__system__",
        audit_subcollection="sar_e_audit",
        resource_type="sar_e_config",
        action="ab_config_update",                            # registered in DM-PRD-07's audit registry
        user_id=user.id,
        before_state=...,
        after_state=body.model_dump(),
    )
    await firestore_client.set(_ab_config_doc(), body.model_dump(mode="json"))
    return body


@router.get("/internal/admin/sar-e/model-ab")
async def get_ab_config(user=Depends(require_super_admin)) -> SarEModelABConfig:
    return await load_ab_config()
```

### 5.5 Load test setup

```python
# tests/load_test/sar_e_scenarios_locust.py

class ScenariosUser(HttpUser):
    wait_time = between(0.5, 2)

    @task(10)
    def funnel(self):
        self.client.get(f"/api/v1/sar-e/{ACCOUNT_ID}/analytics/funnel?...")

    @task(10)
    def trendline(self):
        self.client.get(f"/api/v1/sar-e/{ACCOUNT_ID}/analytics/trendline/Consideration?window_weeks=53")

    @task(1)
    def scenario(self):
        self.client.post(
            f"/api/v1/sar-e/{ACCOUNT_ID}/scenarios",
            json={"overrides": [
                {"kpi_id": KPI_ID_A, "week_start": "2026-05-04", "value": 15000.0},
                {"kpi_id": KPI_ID_B, "week_start": "2026-05-04", "value": 2000.0},
            ]},
        )
```

Shape: ramp 100 users over 60s, hold 5 min, ramp down 60s. Reports generated from Locust CLI.

### 5.6 Component README outline

```markdown
# SAR-E — Simulation and Recommendations Engine

## What SAR-E is
... (mirror implementation-plan §1)

## Architecture
[diagram: wizard → config → ingestion → VAR → IRF → targets → analytics]

## Key abstractions
- EffectivenessKPI / KPIDataPoint / FunnelStageMapping / Baseline / Target / ...

## API contracts
[pointer to each PRD §6 surface; summarized table]

## Component dependencies
- Data Pipeline (inputs)
- Automations (scheduling)
- Project Tasks (calendar reads)
- Performance (consumer)
- Agentic Harness (specialist runtime)

## PRD index
- [SE-PRD-01](./SE-PRD-01-configuration-foundation.md) — ...
- [SE-PRD-02](./SE-PRD-02-weekly-kpi-ingestion.md) — ...
...

## Verification report
[SE-PRD-07 test results — eval pass rate, load test p99, methodology audit count]
```

## 6. API contract (owned here)

| Method | Path | Purpose | Role |
|---|---|---|---|
| `GET` | `/api/v1/internal/admin/sar-e/model-ab` | Read A/B config | super-admin |
| `PUT` | `/api/v1/internal/admin/sar-e/model-ab` | Update A/B config | super-admin |

No user-facing endpoints.

## 7. Acceptance criteria

1. **End-to-end test passes.** `pytest api/tests/integration/test_sar_e_full_lifecycle.py -v` passes with all 8 milestones green in CI.
2. **Lifecycle test covers full path.** Each milestone asserts both Firestore state and API response shape. Skipping any milestone (via `@pytest.mark.skip` for debugging) still lets later milestones run independently (each has a self-contained setup).
3. **Load test gates.** Scheduled nightly load test reports:
   - `/scenarios` p99 ≤500ms at 100 concurrent users
   - `/analytics/cost-rollup` (500-task account) p95 <500ms
   - `/analytics/funnel` + `/trendline` (warm cache) p95 <100ms
   - Report uploaded as a CI artifact
4. **Methodology lint gate passes.** `make lint` runs `test_methodology_language.py`; the SAR-E code base has zero banned phrases in router / service / model / specialist files.
5. **Methodology lint catches regressions.** Inserting `"because"` into `api/src/kene_api/routers/sar_e_targets.py` causes `make lint` to fail with a specific file:lineno diagnostic.
6. **Allowlist works.** Adding a whitelisted file:lineno token to `methodology_allowlist.txt` suppresses that exact match without affecting others.
7. **A/B harness shadow mode.** Setting `enabled=true, mode=shadow, challenger_traffic_pct=50, challenger_model=gemini-2.0-flash` → 50% of eligible derivations trigger a background Flash call logged to Weave; caller always sees Pro output; caller latency is unaffected (measured: <50ms overhead under shadow).
8. **A/B harness active mode.** Same config but `mode=active` → 50% of callers receive Flash output; Weave tags `variant=challenger` for those calls.
9. **A/B harness stickiness.** Two sequential `/targets/derive` calls for the same `(account_id, derivation_context_hash)` route to the same variant in both shadow and active modes.
10. **A/B harness opt-out.** Account with `sar_e_config.ab_harness_opt_out=true` always sees champion (Pro) regardless of A/B config.
11. **A/B admin endpoint.** `PUT /internal/admin/sar-e/model-ab` requires super-admin; non-admin → 403; update writes an audit entry with `action="ab_config_update"` (DM-PRD-07's registered action) and `resource_type="sar_e_config"`.
12. **Cache-coherence tests.** All four scenarios in §5.x (retrain, mapping PUT, KPI PATCH, target save) pass — subsequent reads return fresh values without manual invalidation.
13. **Runbook in `api/CLAUDE.md`.** Section "SAR-E operations" exists with all 7 bullets from §2 in-scope; each bullet has a runnable command or clear procedure.
14. **Component README created.** `docs/design/components/sar-e/README.md` exists with all sections from §5.6; PRD index links to every shipped PRD; verification-report appendix references the load-test artifacts.
15. **Verification report.** The README's verification-report appendix names the eval pass rate (from `tests/evals/performance_forecasting/`, SE-PRD-05), the load-test p99 values, and the methodology-audit match count (zero). Template:
    ```
    ## Verification report (SE-PRD-07, YYYY-MM-DD)
    - Eval golden cases: N passing / M total (from SE-PRD-05)
    - Load test: /scenarios p99=XXXms, /cost-rollup p95=XXXms
    - Methodology audit: 0 banned phrases across N files scanned
    - End-to-end lifecycle: 8/8 milestones green
    ```
16. **Tooling gates.** `make lint`, `mypy`, `ruff`, `codespell`, pytest all pass.

## 8. Test plan

**End-to-end** (§5.1): 8 ordered milestone tests + one golden-path composite. All pass green.

**Load tests** (§5.5): run nightly via `.github/workflows/load-test.yml` (CI addition — CI task). Gates on the thresholds in AC #3. Regression threshold: p99 regression >25% from the prior week alerts via Slack (ops concern).

**Methodology audit** (§5.2): runs per-commit via `make lint`.

**A/B harness** (§5.3 + §5.4):
- Unit test on `_route_to_challenger` (deterministic bucketing)
- Integration test: seed `config/sar_e_model_ab` with various configs → run 100 mock derivations → assert the observed pct within ±5% of configured
- Integration test: shadow mode does not add response latency (mock Flash with a 500ms delay → caller response unaffected; background task completes async)
- Integration test: opt-out account never hits challenger
- Admin endpoint: non-admin → 403; super-admin → 200 + audit write

**Cache coherence** (§5.x covered by `test_sar_e_cache_coherence.py`):
- Retrain invalidates trendline cache (assert with a read-retrain-read sequence)
- Mapping PUT invalidates analytics cache
- KPI PATCH invalidates analytics cache
- Target save → next list call returns the new target

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| **E2E test is flaky on shared CI.** Firestore emulator + 52-week data seeding takes time; concurrent CI jobs may conflict. | Fixture is module-scoped, account_id prefixed with run-id; 60s timeout on Gemini mock calls; retries disabled on first failure to surface real issues. |
| **Load test hits real Firestore/Vertex budgets.** Nightly runs cost money. | Use a dedicated test project with budget cap alerts; scheduled off-hours; tear-down after. |
| **A/B harness increases Gemini spend.** Shadow mode doubles spend on routed traffic. | Default `challenger_traffic_pct=0`; require super-admin to turn on; ops budget review before each experiment. |
| **Methodology lint false positives.** Legitimate uses of banned phrases in comments (e.g., "this MUST not say 'caused'") get flagged. | Allowlist mechanism handles them. Adding to the allowlist requires a documented reason in a same-PR comment. |
| **A/B harness logic coupling.** The derivation service gains a branch per-request. | Minimal — single Firestore read cached in-process, one hash check, one possible background fire. Well-isolated in `dispatch_to_specialist`. |
| **Runbook drift.** Operations commands in `api/CLAUDE.md` go stale as the codebase evolves. | Runbook lists commands (not code paths) so renames don't invalidate them. Quarterly review in the SAR-E component's health check. |
| **E2E fixture maintenance.** Mocking Data Pipeline + Integrations is fragile; upstream shape changes require fixture updates. | Fixture uses the public Pydantic schemas from `DataPipelineJob` / `PlatformConnectionSummary` — if they change, `mypy` catches it. |
| **Locust fixture account pollution.** Nightly runs seed data; cleanup must be reliable or the account grows unbounded. | Teardown fixture runs `DELETE /accounts/{id}` at the end of every nightly; if cleanup fails, a weekly cron sweeps test accounts older than 7 days. |

### Open questions

1. **Should the load test gate PRs or only run nightly?** First-pass: nightly-only (PR CI already exercises unit + integration). Revisit if performance regressions slip through.
2. **Should the A/B harness track per-variant costs?** Weave captures token counts; ops can query. An explicit cost report is deferred unless the harness is used heavily.
3. **How long do we keep A/B shadow data?** First-pass: indefinite in Weave. If retention becomes a concern, Weave's built-in retention policies handle it.
4. **Component README maintenance.** Who owns keeping it current as future PRDs land? First-pass: the last PRD's owner updates the README index. Consider adding a PR checklist item (part of CLAUDE.md) if this slips.
5. **Verification report in the README — one-time or recurring?** First-pass: one-time at SE-PRD-07 completion. Future quarterly health checks could append entries.

## 10. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md) §6 SE-PRD-07
- Upstream: SE-PRDs 01–06
- Runbook target: [`api/CLAUDE.md`](../../../../../api/CLAUDE.md)
- Existing load-test conventions: `tests/load_test/`
- Weave span catalog: `docs/trace-structure-spec.md`
- CLAUDE.md rules in scope: PY-1, PY-2, PY-3, PY-5, PY-7; C-1, C-2, C-4; T-1, T-3, T-4, T-5, T-6, T-7, T-8; G-1
