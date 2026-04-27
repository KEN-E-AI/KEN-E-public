# PE-PRD-08 — Integration Testing & Polish

**Status:** Blocked — resumes once PE-PRD-02, PE-PRD-03, PE-PRD-04, PE-PRD-05, PE-PRD-06, and PE-PRD-07 all ship
**Owner team:** QA + whichever Performance team finishes first
**Blocked by:** PE-PRD-02 (Analysis tab); PE-PRD-03 (Simulations tab); PE-PRD-04 (Configuration tab); PE-PRD-05 (Setup Wizard); PE-PRD-06 (Targets tab); PE-PRD-07 (Diagnostics tab)
**Blocks:** —
**Estimated effort:** 2–3 days

---

## 1. Context

The six prior Performance PRDs deliver the page shell, five rendering tabs, and the setup wizard. Each ships with its own colocated unit + integration tests. This PRD is the **end-to-end closing sprint**: cross-tab flows, wizard ↔ tab transitions, the terminology-rename audit, rendering-performance targets, accessibility, and contract tests against SAR-E's OpenAPI.

It also performs the final documentation pass — updating the Performance component README with shipped status and appending a verification report that captures observed performance numbers and the final state of open questions.

This PRD is the belt-and-suspenders check on the two invariants the Performance component has to satisfy:

1. **Pre-wizard users see only the Configuration tab.** Analysis / Simulations / Targets / Diagnostics must be hidden from the nav until SAR-E `/config/status` returns `enabled=true`.
2. **Goal → Target rename is complete.** Zero `useGoals` / `GoalsContext` / `setForecastAsGoals` / user-facing `Goals:` strings may remain in any Performance-page file.

Both are tested here via automation: grep audits + Playwright UI assertions.

## 2. Scope

### In scope

- **E2E Playwright suites** — the five scenarios listed in implementation-plan §6 PE-PRD-08 (each enumerated in §4.1 below)
- **Terminology-rename audit** — automated grep asserting zero `useGoals` / `GoalsContext` / `setForecastAsGoals` / user-facing `Goals:` strings in the Performance surface. Runs as a CI gate.
- **Rendering-performance targets**:
  - 53-week trendline (via Dashboards LineChart widget) + 4-stage drill-down rendered under 2s p95 (implementation-plan §11 success criterion)
  - Tab-switch latency (any → any) under 200ms p95 when data is cached
- **Contract tests** between every `/api/v1/performance/{account_id}/*` bundle endpoint and SAR-E's OpenAPI, enforced in CI (implementation-plan §5.1 requirement)
- **Accessibility audit** across all six tabs + the setup wizard (automated axe-core pass in Playwright + a manual keyboard-navigation pass)
- **Verification report** appended to `docs/design/components/performance/README.md` — see §4.6 for the template paragraph structure
- **PROJECT-PLANNER update** — flip all PE-PRD rows to `shipped` once this PRD's gates are green

### Out of scope

- **Load testing beyond the p95 targets.** Single-user-session scaling is not exercised here; SAR-E owns its own `/scenarios` load test in SE-PRD-07. A separate Performance perf PRD lands later if traffic demands it.
- **Security pen-testing beyond SAR-E's contract.** The Performance component itself is a read-only frontend over SAR-E; the ongoing security-review skill covers this during regular PR review.
- **Deeper model-correctness testing.** Validating the VAR baseline, IRF coefficients, and the `performance_forecasting` specialist's reasoning is SAR-E's responsibility (SE-PRD-07 §11 methodology-language audit + golden-path evals).
- **Cross-browser matrix testing.** Playwright runs against Chromium in CI; Safari / Firefox test runs are a separate infra concern.
- **Feature-flag rollback drill.** Handled by FF-PRD-04's flag-rollback PRD if needed.
- **Data contract extensions.** No new Pydantic models or TypeScript types are introduced by this PRD. It consumes PE-PRD-01 through PE-PRD-07's contracts as-is.

## 3. Dependencies

- **PE-PRD-02, PE-PRD-03, PE-PRD-04, PE-PRD-05, PE-PRD-06, PE-PRD-07:** all merged before this PRD starts. Each of their acceptance criteria must be green in CI.
- **SE-PRD-07 (SAR-E Integration testing & polish):** publishes the golden-path SAR-E fixtures + the methodology-language audit. This PRD's E2E suites reuse SE-PRD-07's seeded account fixtures where possible (backfilled account, empty account, partially-ingested account) rather than re-seeding.
- **DP-PRD-06 (Data Pipeline testing & polish):** verifies the ingestion-status query is stable. PE-PRD-07's Diagnostics tab fixtures depend on it.
- **A-PRD-04 (Test / Dry-Run Mode), if shipped:** used by the Simulations E2E to produce deterministic simulation outputs without hitting Gemini 2.0 Pro on every CI run. If not yet shipped, this PRD adds a `seed_sar_e_fixture` helper that writes baseline + target docs directly to Firestore (see §4.5).
- **IN-PRD-03 (Connection-management UI):** the wizard-abandonment scenario navigates through `/settings/integrations`; that page must be navigable (even as a stub) for E2E to pass.
- **Feature Flags (FF-PRD-03):** all six `performance_*_tab` flags (including `performance_dashboards_tab`) + `performance_setup_wizard` are resolvable in the CI test environment.
- **Existing files to study:**
  - `frontend/e2e/` — existing Playwright setup + helpers
  - `api/tests/integration/` — contract-test patterns + OpenAPI schema validator
  - `deployment/ci/` — pipeline hooks for E2E + perf gates
  - `docs/design/components/dashboards/projects/DB-PRD-04-integration-testing-and-polish.md` — direct pattern template for this PRD
  - `docs/design/components/performance/README.md` — verification-report target file

## 4. Test plan

This PRD has no new data contract. All contract coverage is inherited from PE-PRD-01 through PE-PRD-07 and verified here against SAR-E's OpenAPI (§4.5) and Data Pipeline's ingestion-status query (§4.5).

### 4.1 End-to-end Playwright suites

**E2E-1 — New-account wizard flow (golden path)**

1. Log in to a freshly-seeded account (no integrations connected, forecasting disabled; SAR-E `/config/status` returns `{enabled: false, setup_wizard_completed: false, connected_integrations: []}`).
2. Navigate to `/performance`. Assert the URL auto-resolves to `/performance/configuration` (PE-PRD-01's default-route logic).
3. Assert that **Dashboards + Configuration tabs are visible in the tab nav**; Analysis / Simulations / Targets / Diagnostics buttons are absent from the rendered DOM.
4. Assert the Configuration tab body renders the empty-state CTA ("Set up forecasting"); click it.
5. Wizard opens at `/performance/setup`, step 1 (Welcome). Because `connected_integrations` is empty, the Welcome step routes to `/settings/integrations`.
6. Complete the Google OAuth flow via the Integrations test harness (mock OAuth server — standard IN-PRD-02 fixture).
7. On return to `/performance/setup`, wizard resumes at step 2 (Define KPIs). Pick one KPI per Objective (4 total) from `available_kpi_sources`; name each; set `aggregation` + `unit` + `typical_direction`.
8. Advance to step 3 (Backfill Depth). Wizard calls `POST /sar-e/{account_id}/config/backfill-plan`; test harness returns `{backfill_weeks: 52}` for this fixture. Assert the calculated backfill is displayed.
9. Advance to step 4 (Review + Confirm). Click "Start backfill"; wizard submits `POST /sar-e/{account_id}/config/setup`.
10. Wizard polls `/sar-e/{account_id}/config/status`; test harness flips `enabled=true` + `setup_wizard_completed=true` within the polling window.
11. Wizard redirects to `/performance/analysis`.
12. Assert **all six tabs are now visible** in the nav (Analysis / Dashboards / Simulations / Targets / Diagnostics / Configuration).
13. Assert the Analysis tab renders: 4-stage funnel, 53-week trendlines (via Dashboards LineChart widget), cost-rollup chips, related-metrics grid, External Factors panel. Data may be low-confidence; the "insufficient history" badge is acceptable for this fixture.

**E2E-2 — Save-as-Targets round-trip**

Fixture: existing account with forecasting enabled, 104 weeks of backfilled KPI data, no saved Targets yet.

1. Navigate to `/performance/simulations`.
2. Click "Run Simulation" with default (empty) overrides.
3. Wait for the 12-week baseline-vs-target `ComposedChart` to render.
4. Click "Save Forecast as Targets". Confirm in the dialog that this persists all 12 weeks × 4 KPIs = 48 Targets.
5. Navigate to `/performance/targets`.
6. Assert the Targets table renders 48 rows (the newly-saved set), sorted descending by `week_start`.
7. Navigate to `/performance/analysis`; switch the comparison-mode toggle to `vs_target`.
8. Assert the trendline and metric-delta layer render with `vs_target` comparison populated (i.e., the 12-week forward window shows Target overlays).

**E2E-3 — Configuration mapping edit (post-wizard)**

Fixture: existing account with completed wizard + populated data.

1. Navigate to `/performance/configuration`.
2. In the Funnel Stage Mapping editor, swap the KPI bound to the "Brand Awareness" Objective for a different available KPI.
3. Click Save. Assert the save succeeds (PUT `/sar-e/config/funnel-mapping` returns 200).
4. Navigate to `/performance/analysis`.
5. Assert the "Brand Awareness" stage of the funnel now renders against the new KPI (the trendline data source has switched). Use the trendline's visible data-source label + a spot-check on a known-value week.

**E2E-4 — Diagnostics tab on a backfilled account**

Fixture: existing account with completed wizard, 104 weeks of data, latest VAR retrain completed, one GA job that failed 2 days ago with an auth error.

1. Navigate to `/performance/diagnostics`.
2. Assert the Model-health section renders four `PerKPIModelHealthCard`s.
3. For each card: assert the 12-week confidence-band chart is visible with the CI area rendered; assert `IRFConvergenceBadge` shows `converged`; assert `LastRetrainedAt` shows a recent timestamp.
4. Assert the `PerKPIIngestionTable` renders four rows; assert one row (the KPI whose source job failed) shows a warning chip due to the gap count or consecutive-failure signal.
5. Assert the `FailedJobsPanel` renders one card; the card's `error_kind === 'auth'` and includes a "Check Integrations" link pointing at `/settings/integrations`.

**E2E-5 — Wizard abandonment + resume**

Fixture: fresh account; wizard not started.

1. Navigate to `/performance/configuration`; click the "Set up forecasting" CTA.
2. Proceed through Welcome + Define KPIs (pick 4 KPIs).
3. Advance to step 3 (Backfill Depth). Close the browser tab without clicking Continue.
4. (Simulates time passing: open a new tab — same user, same session.)
5. Navigate to `/performance`. Assert the URL auto-resolves to `/performance/configuration` (still pre-wizard since `setup_wizard_completed=false`).
6. Assert a **"Resume setup"** banner renders on the Configuration empty-state (not a forced redirect to `/performance/setup` — per Open Question 6 in implementation-plan §10).
7. Click "Resume setup".
8. Assert the wizard opens at **step 3** with the previously-selected 4 KPIs still populated in step 2's summary (draft loaded from `accounts/{account_id}/performance_wizard_draft`).

### 4.2 Terminology-rename audit

Implemented as a standalone CI job + a test in `api/tests/integration/test_performance_terminology_rename.py` (Python-launched grep is the most portable form):

```bash
# The audit must return zero matches.
grep -rn --include='*.ts' --include='*.tsx' \
  -E 'useGoals\b|GoalsContext\b|setForecastAsGoals\b|\bGoals:' \
  frontend/src/pages/Performance \
  frontend/src/components/performance \
  frontend/src/hooks
```

Runs as a CI gate — a single match fails the build. The ESLint rule from PE-PRD-03 is the first line of defense; this audit is the second. The `Goals:` pattern specifically catches user-visible string literals; `useGoals` / `GoalsContext` / `setForecastAsGoals` catch identifier regressions.

### 4.3 Rendering-performance targets

**P-1 — Analysis tab initial render (53-week trendline + funnel + cost rollup)**
- Fixture: account with 104 weeks of backfilled KPI data, 50 calendar tasks in the 12-week horizon.
- Measure: navigation to `/performance/analysis` → all required components rendered (funnel + 4 trendlines + cost rollup chips + related metrics grid + External Factors panel).
- Target: **p95 < 2000ms** per implementation-plan §11.
- Runs 50 iterations in a Playwright perf spec with `performance.measure` markers. Fails CI if p95 > 2000ms.

**P-2 — Funnel-stage drill-down**
- From a loaded Analysis tab, click one of the four funnel stages.
- Measure: click → expanded detail (single-KPI 53-week trendline + cost chips) fully rendered.
- Target: **p95 < 500ms** (sub-target under the 2s gate above).
- Runs 50 iterations.

**P-3 — Tab-switch latency**
- From `/performance/analysis`, navigate to each other tab and back.
- Measure: route transition → tab body first-paint.
- Target: **p95 < 200ms** when data is in React Query cache (all previous bundles are fresh).
- Runs 100 iterations across the full tab cycle.

### 4.4 Accessibility audit

- Every tab (`/performance/analysis`, `/performance/simulations`, `/performance/targets`, `/performance/diagnostics`, `/performance/configuration`) + the wizard route (`/performance/setup`) is loaded in a Playwright test and passed through `axe-core` via `@axe-core/playwright`. Zero violations at `serious` or `critical` severity is the bar.
- **Manual keyboard-navigation pass:** one engineer runs a scripted keyboard-only walkthrough of each tab + the full wizard flow (tab forward, arrow keys in the table, enter / escape to expand/collapse drill-downs, esc to cancel modals). Findings logged in the verification report (§4.6).
- **Focus-order sanity check:** the wizard's step-by-step focus order matches reading order; the Configuration tab's Funnel Mapping editor focus order goes top-down through the four rows.

### 4.5 Contract tests against upstream OpenAPIs

For each bundle endpoint, generate a Pydantic model from the response shape and assert it matches what SAR-E / Data Pipeline publish in their OpenAPI spec. Runs in `api/tests/integration/test_performance_contract.py` on every PR touching `api/src/kene_api/routers/performance*.py` or `api/src/kene_api/services/performance*.py`.

Covered endpoints:

| Performance endpoint | Upstream fields consumed | Upstream source |
|---|---|---|
| `GET /performance/{account_id}/analysis` | `FunnelSnapshot`, `TrendlineSeries`, `CostRollup`, `RelatedMetric` | SAR-E `/analytics/*` |
| `GET /performance/{account_id}/simulations` | `ForecastPoint`, `CalendarSummary`, `Target` | SAR-E `/forecasts/baseline` + project-tasks Calendar |
| `GET /performance/{account_id}/targets` | `Target`, `KPIDataPoint` | SAR-E `/targets` + `/analytics/trendline` |
| `GET /performance/{account_id}/diagnostics` | `Baseline`, `DataPipelineRun`, `irf_convergence` | SAR-E `/forecasts/baseline` + DP-PRD-01 runs query |
| `GET /performance/{account_id}/configuration` | `FunnelStageMapping`, `Threshold`, `ChannelCoverage`, `EffectivenessKPI`, `AvailableKPISource` | SAR-E `/config/*` |

Any drift between what Performance's bundle composer expects and what SAR-E (or Data Pipeline) publishes fails the contract test. This protects against the "SAR-E contract changes mid-build" risk from implementation-plan §9.

Fixture strategy: if SE-PRD-07's test-harness fixtures are available, reuse them (seeded accounts at three states: empty, partially-ingested, fully-backfilled). If not yet available, this PRD ships a `seed_sar_e_fixture.py` helper that writes `Baseline` + `Target` + `KPIDataPoint` docs directly to the emulator, bypassing the VAR fit for CI speed.

### 4.6 Verification report (README append)

On completion, append a new section to `docs/design/components/performance/README.md`:

```markdown
## Verification Report (Shipped YYYY-MM-DD)

The Performance component shipped on YYYY-MM-DD. This section records the observed state at ship time.

**E2E coverage:** All five Playwright suites (`performance-wizard-flow`, `performance-save-as-targets`, `performance-configuration-edit`, `performance-diagnostics`, `performance-wizard-abandonment`) green in CI.

**Performance targets (50-100 iterations each):**
- Analysis tab initial render (P-1): p95 = XXXms (target < 2000ms)
- Funnel drill-down (P-2): p95 = XXXms (target < 500ms)
- Tab-switch latency (P-3): p95 = XXXms (target < 200ms)

**Terminology-rename audit:** Zero matches across `frontend/src/pages/Performance`, `frontend/src/components/performance`, `frontend/src/hooks`.

**Accessibility:** Zero `serious` or `critical` axe-core violations. Keyboard-navigation pass completed by <engineer name> on YYYY-MM-DD; findings: <list or "none">.

**Contract tests:** All five bundle endpoints pass against SAR-E's OpenAPI and Data Pipeline's ingestion-status query.

**Open questions at ship time:** <paste from implementation-plan §10 open questions with resolution notes>
```

### 4.7 Observability spot-checks

- Every mutating write (wizard `POST /sar-e/config/setup`, funnel-mapping PUT, Save-as-Targets POST) emits an `AuditEntry` per DM-PRD-07.
- The wizard emits the `performance.setup_wizard` Weave span with `{step, abandoned_at, elapsed_seconds}` per implementation-plan §6 PE-PRD-05 — verify span presence after E2E-5 runs.
- `useDiagnosticsTab`'s 60s polling generates the expected number of `GET /performance/{account_id}/diagnostics` spans in a 5-minute window.

## 5. Implementation outline

| Action | File |
|---|---|
| Create | `frontend/e2e/performance-wizard-flow.spec.ts` — E2E-1 |
| Create | `frontend/e2e/performance-save-as-targets.spec.ts` — E2E-2 |
| Create | `frontend/e2e/performance-configuration-edit.spec.ts` — E2E-3 |
| Create | `frontend/e2e/performance-diagnostics.spec.ts` — E2E-4 |
| Create | `frontend/e2e/performance-wizard-abandonment.spec.ts` — E2E-5 |
| Create | `frontend/e2e/performance-perf.spec.ts` — P-1 / P-2 / P-3 via `performance.measure` markers |
| Create | `frontend/e2e/performance-accessibility.spec.ts` — axe-core pass across all 5 tabs + wizard |
| Create | `api/tests/integration/test_performance_terminology_rename.py` — §4.2 grep audit |
| Create | `api/tests/integration/test_performance_contract.py` — §4.5 contract tests |
| Create (if needed) | `api/tests/fixtures/seed_sar_e_fixture.py` — helper if SE-PRD-07 fixtures not yet available |
| Modify | `docs/design/components/performance/README.md` — append §4.6 verification report + "Shipped YYYY-MM-DD" banner at top |
| Modify | `docs/design/components/PROJECT-PLANNER.md` — flip all PE-PRD rows to `shipped` |
| Verify | `deployment/ci/` — pipeline includes the new E2E + contract specs on PR and nightly |

## 6. Acceptance criteria

1. All five Playwright E2E specs (`performance-wizard-flow`, `performance-save-as-targets`, `performance-configuration-edit`, `performance-diagnostics`, `performance-wizard-abandonment`) pass in CI.
2. `performance-perf.spec.ts` passes at the p95 thresholds in §4.3 (P-1 < 2000ms, P-2 < 500ms, P-3 < 200ms).
3. `performance-accessibility.spec.ts` reports zero `serious` or `critical` axe-core violations across all six tabs + the wizard.
4. `test_performance_terminology_rename.py` returns zero matches for `useGoals` / `GoalsContext` / `setForecastAsGoals` / `Goals:` across the Performance surface.
5. `test_performance_contract.py` passes for all five bundle endpoints against SAR-E's OpenAPI + Data Pipeline's ingestion-status query.
6. Wizard E2E-5 specifically verifies: (a) the "Resume setup" banner appears on the Configuration tab and (b) the wizard reopens at step 3 with prior selections intact — this is the key resumability guarantee.
7. Manual keyboard-navigation pass completed and findings recorded in the verification report.
8. `docs/design/components/performance/README.md` gains a "Shipped YYYY-MM-DD" banner + a Verification Report section per §4.6 template.
9. `PROJECT-PLANNER.md` PE-PRD rows flipped to `shipped` with today's date.
10. Observability spot-checks (§4.7) pass: audit entries on every mutation, wizard Weave span emitted on abandonment + completion, diagnostics polling spans match the expected cadence.
11. `make lint` clean; `pytest api/tests/` all green; `npm run typecheck` clean; Playwright CI green.

## 7. Risks & open questions

| Risk | Mitigation |
|---|---|
| SE-PRD-07 fixtures not yet at CI parity | If SE-PRD-07's deterministic SAR-E fixtures have not shipped by the time this PRD lands, add `seed_sar_e_fixture.py` to write `Baseline`, `Target`, `KPIDataPoint`, and `DataPipelineRun` docs directly to the Firestore emulator. Document in each test file's header. |
| Mock OAuth for E2E-1 step 6 | Reuse IN-PRD-02's mock OAuth harness. If absent, this PRD adds a `MockGoogleOAuthServer` fixture on top of `pytest-httpserver`. |
| E2E flakiness on Chromium in CI runners | Use Playwright's `expect.toBeVisible({ timeout: 10_000 })` retries rather than explicit `waitForTimeout`. Run the perf suite with 50-100 iterations and use p95 rather than max. |
| `performance.measure` timing noise on shared CI runners | Budget a 10% tolerance bumper for the first 60 days post-ship; tighten after the first month's nightly telemetry. |
| Contract test churn as SAR-E tunes its OpenAPI mid-build | Contract tests run against SAR-E's **published** OpenAPI (committed to `api/openapi/sar-e.yaml` or similar). Regenerate on every upstream update; the test's job is to catch drift, not to freeze SAR-E's iteration. |
| Goal → Target rename leaks into files the grep doesn't cover | The grep scopes to `frontend/src/pages/Performance`, `frontend/src/components/performance`, `frontend/src/hooks`. If the refactor touched `frontend/src/contexts/` or another directory, widen the grep. Confirm at kickoff. |
| Verification report becomes stale | The report captures ship-time state only. For ongoing health, rely on the nightly CI telemetry + Weave spans. |
| Accessibility keyboard pass subjective | Script the walkthrough in a checklist (same checklist each time) and keep prior-round findings in the verification report; comparability over time matters more than absolute coverage in one pass. |

### Open questions

1. **Perf suite cadence — every PR or nightly?** Recommendation: nightly + on PRs that touch `frontend/src/pages/Performance/**` or `frontend/src/components/performance/**` or `api/src/kene_api/routers/performance*.py`. Confirm with the infra team.
2. **Should PE-PRD-08 own the composed-axes decision from PE-PRD-07's §9 Open Question 3?** No — that decision is made at PE-PRD-07 kickoff. PE-PRD-08 only validates whatever PE-PRD-07 shipped.
3. **Does the manual keyboard pass gate shipping or log findings for follow-up?** Recommendation: gate shipping on zero axe-core `critical` violations; manual-pass findings go into the verification report as a backlog list unless they rise to the level of blocking a keyboard-only user. Confirm at kickoff.
4. **Wizard draft TTL.** Implementation-plan §6 PE-PRD-05 doesn't specify how long `accounts/{account_id}/performance_wizard_draft` persists. E2E-5 assumes "at least one session later." If PE-PRD-05 enforces a short TTL (e.g., 24 hours), E2E-5's "next day" scenario should be validated with a clock-injection helper rather than literal day-passage.

## 8. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md) §6 PE-PRD-08, §11 Success criteria
- Siblings: [PE-PRD-01](./PE-PRD-01-page-shell-and-routing.md), [PE-PRD-02](./PE-PRD-02-analysis-tab.md), [PE-PRD-03](./PE-PRD-03-simulations-tab.md), [PE-PRD-04](./PE-PRD-04-configuration-tab.md), [PE-PRD-05](./PE-PRD-05-setup-wizard.md), [PE-PRD-06](./PE-PRD-06-targets-tab.md), [PE-PRD-07](./PE-PRD-07-diagnostics-tab.md)
- Pattern template: [DB-PRD-04 Dashboards Integration Testing & Polish](../../dashboards/projects/DB-PRD-04-integration-testing-and-polish.md)
- Upstream: [SE-PRD-07 SAR-E Integration testing & polish](../../sar-e/implementation-plan.md#se-prd-07--integration-testing--polish) fixtures + methodology-language audit
- Upstream: [DP-PRD-06 Data Pipeline Integration testing & polish](../../data-pipeline/implementation-plan.md#dp-prd-06--integration-testing--polish) ingestion-status query validation
- Role policy: [DM-PRD-07 §4 transition policy table](../../data-management/projects/DM-PRD-07-approval-workflow-and-audit.md#4-data-contract)
- Feature Flags: [FF-PRD-03 `useFeatureFlag` hook](../../feature-flags/projects/FF-PRD-03-frontend-sdk-and-e2e.md)
- CLAUDE.md rules in scope: T-2 (colocated frontend tests), T-3 (integration tests for API changes), T-4 (separate pure vs DB), T-5 (prefer integration over heavy mocking), T-6 (unit-test complex algorithms), T-8 (structural assertions); G-1 (`make lint`), G-2 (`npm run format.fix`), G-3 (`npm run typecheck`); GH-1 (Conventional Commits)
