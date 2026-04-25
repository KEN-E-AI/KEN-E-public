# PE-PRD-03 — Simulations Tab

**Status:** Blocked — resumes once PE-PRD-01, SE-PRD-03, SE-PRD-04, and SE-PRD-05 ship
**Owner team:** Frontend (Performance)
**Blocked by:** PE-PRD-01 (`/performance` shell, `PerformanceDateRangeContext`, `ForecastingEnabledGate`, `useTargets` scaffolding, `WizardStep` / `FunnelObjective` / `EffectivenessKPIId` branded types); SE-PRD-03 (12-week VAR baseline via `GET /sar-e/{account_id}/forecasts/baseline`); SE-PRD-04 (IRF scenario propagation via `POST /sar-e/{account_id}/scenarios`); SE-PRD-05 (target derivation via `POST /sar-e/{account_id}/targets/derive`, target persistence via `POST /sar-e/{account_id}/targets` with supersede-on-edit)
**Blocks:** PE-PRD-08 (integration-testing suite consumes the finished Simulations tab)
**Estimated effort:** 4 days

---

## 1. Context

The Simulations tab is where users look forward. It answers three linked questions: (1) what does my current plan look like over the next 12 weeks, (2) what does SAR-E's baseline say the funnel will do, and (3) what per-KPI Target values should I commit to for the horizon? The tab renders three sub-tabs matching the Figma export — "Current Plan", "Simulated Results", "Recommendations" — a 12-week baseline-vs-target chart, a "Run Simulation" trigger, and a "Save Forecast as Targets" persistence action.

Three facts shape this PRD:

1. **Composite axes require a bespoke Recharts wrapper.** The 12-week baseline-vs-target visualization overlays a baseline line, a target line, and (post-run) a scenario line on a shared x-axis, with a secondary y-axis available for a divergent measure. Dashboards' LineChart widget (DB-PRD-03) handles single-axis trendlines; this tab owns its own `ComposedChart` wrapper. Reuse is not possible without a widget rewrite.
2. **Simulation is a single user gesture, not a 2-step workflow.** The user clicks "Run Simulation". Under the covers the Performance API (PE-PRD-01) calls SAR-E `/scenarios` (IRF) and `/targets/derive` (LLM specialist) in sequence and returns one `SimulationRunResult`. This PRD owns the composite endpoint `POST /api/v1/performance/{account_id}/simulations/run` that fans those out. Persisting Targets is a separate, explicit action — never automatic.
3. **"Target" replaces "Goal" everywhere on Performance — this PRD is the enforcement point.** The Figma export labels LLM-derived forecast values as "Goals" (`SimulationsSection.tsx` lines 1578 / 1600 / 1603; `setForecastAsGoals`; `useGoals`; `GoalsContext`). These are Target values, not freeform business goals. This PRD completes the rename across the Performance surface and adds an ESLint guard so the regression can't reappear. Post-merge, `grep -rn 'useGoals\|GoalsContext\|setForecastAsGoals\|Goals:' frontend/src/pages/Performance* frontend/src/components/performance` returns zero matches.

The tab is hidden from the Performance tab nav until the setup wizard (PE-PRD-05) completes — no pre-enablement empty state lives here. `ForecastingEnabledGate` from PE-PRD-01 handles visibility at the nav level.

## 2. Scope

### In scope
- `SimulationsTab` page at `/performance/simulations` with three sub-tabs (Current Plan / Simulated Results / Recommendations), sub-tab state preserved in URL query (`?view=current|simulated|recommendations`)
- **12-week baseline-vs-target `ComposedChart`** — Recharts wrapper (`BaselineVsTargetChart`) with a weekly x-axis, a primary y-axis for the mapped KPI value, a baseline line (from SAR-E), a target line (from saved Targets), and an overlayed scenario line (post-run); honors the Soft Maximalism color scale and a secondary y-axis toggle when two KPIs share the view
- Per-stage expansion panel: clicking a funnel Objective expands an accordion that reveals the LLM specialist's `reasoning` + `methodology_note` fields for that KPI, plus the per-week derivation context hash (for audit / re-run inspection)
- "Run Simulation" button that POSTs `/api/v1/performance/{account_id}/simulations/run` and surfaces loading / success / error / partial states; the button disables while a run is in flight
- "Save Forecast as Targets" action that POSTs each per-(KPI, week) target to `POST /sar-e/{account_id}/targets`; handles SAR-E's supersede-on-edit semantics by surfacing a single "this will replace N existing targets" confirmation before firing
- **Deep-link entry from PE-PRD-06 Targets tab:** query params `?replace_kpi={kpi_id}&replace_week={week_start_iso}` — on mount, the Simulations page scrolls the Save-Forecast-as-Targets panel into view, highlights the matching (KPI, week) row, and pre-selects that single target for replacement. Params are stripped from the URL after consumption so reload doesn't re-trigger the flow. Handshake contract mirrors PE-PRD-06 §6.3.
- `useSimulations` TanStack Query hook consuming `GET /api/v1/performance/{account_id}/simulations`; `useRunSimulation` + `useSaveTargets` mutation hooks
- **Terminology rename pass** — migrate every `Goal` / `useGoals` / `GoalsContext` / `setForecastAsGoals` reference across `frontend/src/pages/Performance*` + `frontend/src/components/performance/**` to `Target` equivalents, plus an ESLint `no-restricted-syntax` rule forbidding the banned identifiers inside the Performance surface
- Branded types: `SimulationRunId`, `TargetId`, `EffectivenessKPIId` (re-exported from PE-PRD-01)
- Unit tests per sub-tab + chart wrapper + rename audit; Playwright spec for run → save → Targets-tab reflection

### Out of scope
- Targets tab rendering (owned by PE-PRD-06)
- Custom scenario authoring UI (setting override values per KPI per week) — v1 runs scenarios against the current plan only; freeform scenario overrides deferred to a later PRD
- IRF visualization beyond the scenario-line overlay (e.g., sensitivity heatmaps) — deferred
- Multi-horizon selection (6 / 12 / 26 week options) — v1 is 12-week only, matching SAR-E's horizon
- Auto-re-derive on calendar change — SE-PRD-05 flags this as a future enhancement
- Partial / incremental saving of a subset of targets — "Save Forecast as Targets" is all-or-nothing in v1 (users edit via the Targets tab post-save)
- Exporting the simulation run to CSV / PDF

## 3. Dependencies

- **PE-PRD-01:** `/performance` page shell, `PerformanceDateRangeContext`, `ForecastingEnabledGate`, `useTargets` stub (to be replaced by the real mutation hooks here), `FunnelObjective` / `EffectivenessKPIId` / `WizardStep` branded types, feature flag `performance_simulations_tab` registration.
- **SE-PRD-03 (VAR + 12-week baseline):** `GET /sar-e/{account_id}/forecasts/baseline` — the source of the baseline line on the chart. Called via the Performance API's `/simulations` bundle; not called directly from the frontend.
- **SE-PRD-04 (Scenario propagation):** `POST /sar-e/{account_id}/scenarios` — the IRF-propagated scenario values. Called transitively through the Performance `/simulations/run` composite endpoint.
- **SE-PRD-05 (Target derivation + persistence):** `POST /sar-e/{account_id}/targets/derive` (LLM specialist producing per-(KPI, week) targets + reasoning); `POST /sar-e/{account_id}/targets` (persist with supersede-on-edit); `PATCH /sar-e/{account_id}/targets/{target_id}` (edit). The derive call happens inside the composite run endpoint; the persist call is direct from the frontend.
- **UI-PRD-01 (Soft Maximalism):** tokens, shadcn primitives, chart color scale. No new primitives introduced.
- **Feature Flags (FF-PRD-03):** `useFeatureFlag('performance_simulations_tab')` gates the tab. ESLint rule shipped under the same PR.
- **External libraries:** `recharts` (already in `frontend/package.json`). No new runtime libs. Note that Dashboards' LineChart widget (DB-PRD-03) is NOT reused here — composed axes exceed its contract.
- **Existing files to study:**
  - `frontend/src/pages/Performance/SimulationsTab.tsx` (current Figma stub, pre-rename) — reference UX, rebuild against the Soft Maximalism design system
  - `frontend/src/components/performance/SimulationsSection.tsx` (Figma stub) — source of the rename targets
  - `frontend/src/hooks/useGoals.ts` (to be renamed to `useTargets.ts`) — signature pattern to preserve during migration
  - `docs/figma-export/src/app/pages/performance/SimulationsSection.tsx` — reference UX for the three sub-tabs

## 4. Data contract

### 4.1 Consumed from the Performance API (PE-PRD-01 shape)

```typescript
import type { Brand } from '@/types/brand';

export type SimulationRunId = Brand<string, 'SimulationRunId'>;
export type TargetId = Brand<string, 'TargetId'>;
export type EffectivenessKPIId = Brand<string, 'EffectivenessKPIId'>;
export type FunnelObjective =
  | 'Problem Awareness'
  | 'Brand Awareness'
  | 'Consideration'
  | 'Conversion';

export interface ForecastPoint {
  week_start: string;       // ISO date (Monday of the ISO week)
  value: number;
  ci_low: number;
  ci_high: number;
}

export interface SavedTarget {
  target_id: TargetId;
  kpi_id: EffectivenessKPIId;
  period_start: string;     // ISO date
  period_end: string;       // ISO date
  value: number;
  baseline_value: number;
  reasoning: string | null;
  derived_by: 'specialist' | 'user_edit';
  created_at: string;
}

export interface CalendarSummary {
  total_tasks: number;
  total_planned_cost: number;
  campaigns: Array<{ campaign_id: string; name: string; task_count: number }>;
  holidays: Array<{ week_start: string; name: string }>;
  promotions: Array<{ week_start: string; name: string }>;
}

// Bundle returned by GET /api/v1/performance/{account_id}/simulations
export interface SimulationsBundle {
  forecasting_enabled: boolean;
  baseline: Record<EffectivenessKPIId, ForecastPoint[]> | null;   // 12 weekly points per KPI
  calendar_summary: CalendarSummary | null;
  saved_targets: SavedTarget[] | null;
  horizon_weeks: number | null;
}
```

### 4.2 Composite run endpoint contract

```typescript
// POST /api/v1/performance/{account_id}/simulations/run (body empty in v1)
export interface SimulationRunResult {
  run_id: SimulationRunId;
  horizon_weeks: number;                              // 12 in v1
  baseline: Record<EffectivenessKPIId, ForecastPoint[]>;
  scenario: Record<EffectivenessKPIId, ForecastPoint[]>;
  incremental: Record<EffectivenessKPIId, ForecastPoint[]>;   // scenario - baseline
  derived_targets: DerivedTarget[];
  model_version: string;
  computed_at: string;                                // ISO datetime
}

export interface DerivedTarget {
  kpi_id: EffectivenessKPIId;
  objective: FunnelObjective;
  period_start: string;
  period_end: string;
  value: number;
  baseline_value: number;
  reasoning: string;
  methodology_note: string;                           // SAR-E enforces "statistical association only" language
  derivation_context_hash: string;
}
```

### 4.3 Client-side derived types

```typescript
export type SimulationsSubTab = 'current' | 'simulated' | 'recommendations';

export interface ChartDatum {
  week_start: string;
  baseline: number;
  target: number | null;       // null until saved or derived
  scenario: number | null;     // null before a run completes
  ci_low: number;
  ci_high: number;
}

export type RunStatus =
  | { kind: 'idle' }
  | { kind: 'running'; started_at: string }
  | { kind: 'complete'; result: SimulationRunResult }
  | { kind: 'failed'; message: string };
```

Brand types per CLAUDE.md C-5; `import type` for all type-only imports per C-6.

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `frontend/src/pages/Performance/SimulationsTab.tsx` — page shell with sub-tab router, gated by `ForecastingEnabledGate` |
| Create | `frontend/src/components/performance/simulations/CurrentPlanSubTab.tsx` — 12-week calendar summary from `calendar_summary` |
| Create | `frontend/src/components/performance/simulations/SimulatedResultsSubTab.tsx` — chart + per-stage expansion |
| Create | `frontend/src/components/performance/simulations/RecommendationsSubTab.tsx` — derived-targets list + save affordance |
| Create | `frontend/src/components/performance/simulations/BaselineVsTargetChart.tsx` — Recharts `ComposedChart` wrapper |
| Create | `frontend/src/components/performance/simulations/RunSimulationButton.tsx` — trigger + loading / error UI |
| Create | `frontend/src/components/performance/simulations/SaveAsTargetsDialog.tsx` — confirmation dialog handling the N-conflicts case |
| Create | `frontend/src/components/performance/simulations/StageReasoningAccordion.tsx` — per-Objective reasoning expansion |
| Create | `frontend/src/hooks/useSimulations.ts` — TanStack Query hook; 30-second stale time |
| Create | `frontend/src/hooks/useRunSimulation.ts` — mutation hook calling `POST /performance/.../simulations/run` |
| Create | `frontend/src/hooks/useSaveTargets.ts` — mutation hook iterating `POST /sar-e/{account_id}/targets`; rolls up N results; invalidates `useTargets` + `useSimulations` |
| Create | `frontend/src/services/performanceSimulationsApi.ts` — axios wrappers |
| Rename | `frontend/src/hooks/useGoals.ts` → `frontend/src/hooks/useTargets.ts` (callers updated in lockstep) |
| Rename | `frontend/src/contexts/GoalsContext.tsx` → `frontend/src/contexts/TargetsContext.tsx` |
| Rename | `setForecastAsGoals` → `setForecastAsTargets` (every occurrence) |
| Modify | `frontend/src/pages/Performance/*` + `frontend/src/components/performance/**` — rename audit pass; replace any remaining `Goals:` copy strings with `Targets:` |
| Create | `frontend/.eslintrc.cjs` overrides section or a dedicated `frontend/eslint-rules/no-performance-goals.js` — `no-restricted-syntax` forbidding `useGoals` / `GoalsContext` / `setForecastAsGoals` / `Goals:` inside `frontend/src/pages/Performance*` + `frontend/src/components/performance/**` |
| Create | `frontend/src/types/performance/simulations.ts` — branded types + `SimulationsSubTab` / `ChartDatum` / `RunStatus` |
| Create | `frontend/src/pages/Performance/__tests__/SimulationsTab.test.tsx` |
| Create | `frontend/src/components/performance/simulations/__tests__/BaselineVsTargetChart.test.tsx` |
| Create | `frontend/src/components/performance/simulations/__tests__/RunSimulationButton.test.tsx` |
| Create | `frontend/src/components/performance/simulations/__tests__/SaveAsTargetsDialog.test.tsx` |
| Create | `frontend/src/hooks/__tests__/useRunSimulation.test.ts` |
| Create | `frontend/src/hooks/__tests__/useSaveTargets.test.ts` |
| Create | `frontend/e2e/performance-simulations-run-save.spec.ts` (Playwright) |

### 5.1 Baseline-vs-target chart behavior

`BaselineVsTargetChart` renders a Recharts `ComposedChart` with:

- **X-axis:** ISO weeks (Monday labels, 12 ticks).
- **Primary Y-axis:** the selected KPI's natural units (from `EffectivenessKPI.unit`).
- **Baseline line:** solid; uses Soft Maximalism's primary chart color.
- **Baseline confidence band:** `Area` between `ci_low` and `ci_high`, rendered semi-transparent under the baseline line.
- **Target line:** dashed; uses the accent color. Only rendered when `saved_targets` or `derived_targets` has values for the weeks on the axis.
- **Scenario line:** dotted; only rendered when `runStatus.kind === 'complete'`.
- **Current-week marker:** vertical reference line on the Monday of the current ISO week.
- **Secondary y-axis:** hidden in v1 (single-KPI view); wired up as a future toggle.
- **Empty states:** when `baseline` is null (forecasting enabled but no baseline yet because backfill is still running), render a skeleton chart with a "Baseline computing — this may take a few minutes" banner; poll `/simulations` every 15s until `baseline !== null`.

### 5.2 Run simulation flow

1. User clicks `RunSimulationButton` on the "Simulated Results" sub-tab.
2. Hook fires `POST /api/v1/performance/{account_id}/simulations/run`. Button transitions to a running state with an elapsed-seconds counter.
3. Performance API composes: (a) read current baseline from SAR-E `/forecasts/baseline`; (b) read current calendar from project-tasks (for context); (c) call SAR-E `/scenarios` with the current plan state; (d) call SAR-E `/targets/derive`; (e) package into `SimulationRunResult`.
4. Frontend receives the result; the chart re-renders with scenario + derived-target overlays; the Recommendations sub-tab populates with derived targets + reasoning.
5. Run p95 target: under 30 seconds (inherits SAR-E's target-derivation p95). If exceeded, surface a timeout toast and allow retry.
6. Errors from the composite endpoint are categorized: `forecasting_disabled` (hard 409 — should never reach if gate works), `baseline_unavailable` (wait + retry banner), `specialist_failure` (retry once, then surface "LLM derivation failed — please try again"), `network` (standard retry).
7. Weave span `performance.simulations.run` captures `{account_id_hash, duration_ms, outcome, kpi_count, model_version}` (no PII).

### 5.3 Save-as-targets flow

1. User clicks "Save Forecast as Targets" on the Recommendations sub-tab.
2. Frontend computes the diff: for each `(kpi_id, period_start)` in `derived_targets`, check whether a `saved_targets` entry already exists for the same key.
3. If any conflicts exist, show `SaveAsTargetsDialog` with "This will replace N existing targets" and enumerate the affected weeks. Otherwise a lighter-weight "Save 48 targets" confirmation.
4. On confirm, iterate `POST /sar-e/{account_id}/targets` for each derived target. SAR-E supersedes on edit — no PATCH logic needed client-side. In v1 this is a serial loop to keep error handling simple; if partial failures occur, show a per-row result summary and leave the successful rows saved (no rollback).
5. Invalidate `useSimulations` and `useTargets` queries; the chart's target-line re-renders with persisted values.

### 5.4 Deep-link entry from the Targets tab (PE-PRD-06 handshake)

1. On mount, the Simulations page reads `useSearchParams()` for `replace_kpi` + `replace_week`.
2. If both are present and well-formed, `useSearchParams().delete(...)` strips them (via `router.replace`) so reload / back-navigation doesn't re-trigger the flow.
3. Scroll the Recommendations sub-tab's Save-Forecast-as-Targets panel into view (`scrollIntoView({ behavior: "smooth", block: "start" })`); activate that sub-tab if the user landed on a different one.
4. Highlight the row matching `(replace_kpi, replace_week)` in the derived-targets table (`aria-current="true"` + Soft Maximalism accent background).
5. If the Simulations bundle has no `derived_targets` for that `(kpi_id, week_start)` (e.g., the user hasn't run a simulation yet), surface a toast: "Run a simulation first to generate a replacement for this target" and auto-expand the "Run Simulation" CTA. The query params are still stripped.
6. If a simulation has already been run and the row exists, the user confirms the replace via the existing `SaveAsTargetsDialog` flow (§5.3) — the only behavioral difference is that the dialog's confirmation copy scopes to the single target ("This will replace 1 existing target for [KPI] in week-of [date]").

### 5.5 Rename enforcement

- Grep audit runs in CI as part of `npm run lint`: `grep -rn 'useGoals\|GoalsContext\|setForecastAsGoals\|Goals:' frontend/src/pages/Performance* frontend/src/components/performance` must return zero.
- ESLint `no-restricted-syntax` rule configured with four selectors matching `Identifier[name=/^useGoals$/]`, `Identifier[name=/^GoalsContext$/]`, `Identifier[name=/^setForecastAsGoals$/]`, and `Literal[value=/Goals:/]`, scoped to the Performance file globs. Violations emit a fixit message pointing at `useTargets` / `TargetsContext` / `setForecastAsTargets`.

## 6. API contract (consumed + owned)

| Method | Path | Purpose | Owner |
|---|---|---|---|
| `GET` | `/api/v1/performance/{account_id}/simulations?horizon_weeks=12` | Simulations tab bundle (baseline + calendar summary + saved targets) | PE-PRD-01 |
| `POST` | `/api/v1/performance/{account_id}/simulations/run` | **NEW — owned here.** Composite endpoint fanning out to SAR-E `/scenarios` + `/targets/derive`. Body empty in v1 (uses current plan as the scenario). Returns `SimulationRunResult`. p95 budget: 30s. | **This PRD** |
| `POST` | `/api/v1/sar-e/{account_id}/targets` | Persist a single target (supersede-on-edit). Called N times from the save-as-targets flow. | SE-PRD-05 |
| `PATCH` | `/api/v1/sar-e/{account_id}/targets/{target_id}` | Edit an existing target. Not used on initial save (supersede handles it); available for the Targets tab (PE-PRD-06). | SE-PRD-05 |
| `GET` | `/api/v1/sar-e/{account_id}/config/status` | Consumed transitively via the bundle's `forecasting_enabled` flag. | SE-PRD-01 |

The composite `/simulations/run` endpoint is new and owned by this PRD. Its implementation lives in `api/src/kene_api/routers/performance.py` and wraps existing SAR-E calls — it is not a SAR-E endpoint. The route contract, request validation, error taxonomy, and Weave span emission are all owned here.

## 7. Acceptance criteria

1. Navigating to `/performance/simulations` on an account with `forecasting_enabled=true` renders the Simulations tab with three sub-tabs defaulting to "Current Plan". URL updates to `?view=current`.
2. Switching sub-tabs updates the URL to `?view=simulated` / `?view=recommendations` and is deep-linkable.
3. On an account with `forecasting_enabled=false`, the Simulations tab is not present in the Performance nav (gated at the shell level by `ForecastingEnabledGate`); direct navigation to `/performance/simulations` redirects to `/performance/configuration`.
4. The "Simulated Results" sub-tab renders `BaselineVsTargetChart` with 12 weekly points drawn from the bundle's `baseline`; a dashed target line renders when `saved_targets` is non-empty.
5. Clicking "Run Simulation" POSTs `/performance/{account_id}/simulations/run`; the button transitions to a running state with an elapsed-seconds counter; on success the chart overlays a scenario line and the Recommendations sub-tab populates with derived targets + reasoning; on failure an inline error surfaces per §5.2's error taxonomy.
6. Run p95 target ≤30s (measured via Weave span `performance.simulations.run.duration_ms` in staging).
7. Clicking a funnel Objective in the per-stage expansion reveals an accordion showing `reasoning` + `methodology_note` + `derivation_context_hash` for that KPI's derived targets.
8. Clicking "Save Forecast as Targets" with zero pre-existing targets shows a "Save 48 targets" confirmation; on confirm, 48 `POST /sar-e/{account_id}/targets` calls fire; `useSimulations` + `useTargets` caches invalidate; the chart's target line reflects the saved values.
9. Clicking "Save Forecast as Targets" when some `(kpi_id, period)` pairs already have saved targets shows a "This will replace N existing targets" confirmation enumerating the affected weeks; on confirm, supersede-on-edit POSTs fire for all targets without client-side PATCH fallback.
10. Partial-failure save: if 3 of 48 POSTs return 5xx, the successful 45 targets persist; a toast enumerates the 3 failures and offers a retry affordance for just those.
11. Rename audit — `grep -rn 'useGoals\|GoalsContext\|setForecastAsGoals\|Goals:' frontend/src/pages/Performance* frontend/src/components/performance` returns zero matches. CI fails if violated.
12. ESLint rule fires on a synthetic reintroduction of `useGoals` / `GoalsContext` / `setForecastAsGoals` / `Goals:` within the Performance globs; passes on identical identifiers outside the Performance globs (e.g., Knowledge Graph's freeform Goals).
13. Deep-link entry from Targets tab: navigating to `/performance/simulations?replace_kpi=<id>&replace_week=<iso>` activates the Recommendations sub-tab, scrolls the Save-Forecast-as-Targets panel into view, highlights the matching row, and strips the query params from the URL. Clicking Save triggers a single-target replace confirmation; back-navigation to `/performance/targets` does not re-activate the flow.
14. Deep-link edge case: when no simulation has been run yet (empty `derived_targets`), the deep link still strips the params and shows the "Run a simulation first" toast with an auto-expanded Run CTA; the Run button is focused for keyboard users.
15. Feature-flag gating: toggling `performance_simulations_tab` off at runtime hides the tab from the nav within the flag's TTL; restoring it re-renders the tab without a full page reload.
16. Viewer-role users see the tab and the chart but `RunSimulationButton` + "Save Forecast as Targets" are disabled with tooltip copy ("Ask an editor to run simulations").
17. Cross-account navigation (`/performance/simulations` under a different `account_id` than the logged-in user has access to) redirects to `/accounts` with a toast.
18. All unit + Playwright tests pass; `npm run build`, `npm run typecheck`, `npm run format.fix`, and `npm run lint` all clean.

## 8. Test plan

**Unit tests — chart** (`BaselineVsTargetChart.test.tsx`):
- Renders 12 x-axis ticks when baseline has 12 points
- Confidence band `Area` uses the `ci_low` / `ci_high` values
- Target line hidden when no saved or derived targets; visible when present
- Scenario line only renders when `runStatus.kind === 'complete'`
- Current-week marker appears at the current ISO week
- Empty baseline → skeleton + "Baseline computing" banner

**Unit tests — run button** (`RunSimulationButton.test.tsx`):
- Click → mutation fires with empty body
- Running state shows elapsed-seconds counter
- Completion populates the Recommendations sub-tab
- Each of the four error categories renders the matching UI (tested with mocked responses)
- Button is disabled for viewer role

**Unit tests — save dialog** (`SaveAsTargetsDialog.test.tsx`):
- No conflicts → "Save 48 targets" copy
- 6 conflicts → "This will replace 6 existing targets" copy + enumerated weeks
- On confirm, 48 POST calls fire; 45 succeed + 3 fail → summary toast with retry affordance for the 3

**Unit tests — hooks:**
- `useSimulations`: 30-second stale time; polls every 15s when `baseline === null`; stops polling once baseline appears
- `useRunSimulation`: cache invalidation on success; error propagation with category metadata
- `useSaveTargets`: sequential POST loop; partial-failure accumulation; final invalidation of both `useSimulations` + `useTargets`

**Unit tests — rename audit** (`__tests__/rename-audit.test.ts`):
- CI-level shell test: runs the grep and asserts zero matches
- ESLint rule unit test: forbidden identifiers in-scope emit a violation; same identifiers out-of-scope do not

**Playwright** (`performance-simulations-run-save.spec.ts`):
- Seed an account with forecasting enabled, 52 weeks of history, 3 saved targets
- Navigate to `/performance/simulations` → verify baseline chart renders
- Click Run Simulation → wait for completion (mocked SAR-E responses) → verify scenario line appears + Recommendations populated
- Click Save Forecast as Targets → confirm the "replace 3" dialog → verify 48 POSTs fire → navigate to `/performance/targets` → verify the new values render
- Reopen `/performance/analysis` in `vs_target` mode → verify the trendline comparison reflects the new targets

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| Recharts `ComposedChart` performance with four overlaid series × 12 points | Trivial at this scale. Not a concern until horizon extends beyond 26 weeks. |
| SAR-E `/targets/derive` p95 exceeds 30s intermittently | Composite endpoint surfaces an explicit timeout + retry affordance; v1 accepts the occasional retry. Longer-term: background derivation + push notification on completion. |
| SAR-E `/scenarios` and `/targets/derive` return shapes drift from what this tab expects | All SAR-E contract calls are contract-tested against SAR-E's OpenAPI on CI in `api/tests/contract/test_sar_e_openapi.py`; a breaking change fails the build. |
| N-target save partial failure leaves the UI out of sync | Success + failure summaries are explicit; `useTargets` invalidation forces a re-read; no rollback logic needed because supersede is idempotent. |
| Rename pass misses a reference inside a dynamic string (e.g., i18n key) | ESLint's `Literal[value=/Goals:/]` selector catches copy strings; grep audit runs on CI. If an i18n layer lands later, extend the rule to cover resource files. |
| User triggers a second Run Simulation before the first completes | Button disabled until the mutation settles; second click is a no-op. In-flight cancellation deferred (unclear SAR-E cancellation semantics). |
| Figma's "Goals:" copy strings appear in screenshot assets checked into the repo | Scope excludes `docs/figma-export/**` from the rename + ESLint rule. The rule's glob is `frontend/src/pages/Performance*` + `frontend/src/components/performance/**` only. |
| ComposedChart secondary y-axis wiring unused in v1 but clutters the component | Ship the secondary axis behind an internal `enableSecondaryAxis` prop defaulting to `false`; expose when multi-KPI overlay lands. |

### Open questions

1. **Should the Recommendations sub-tab allow per-target edits before save?** v1 answer: no — the user either accepts the specialist's derivation wholesale or edits post-save via the Targets tab (PE-PRD-06). Confirm with product at kickoff; if yes, rescope.
2. **Does the scenario line show a confidence band or a single line?** v1 renders a single line for readability; the IRF-propagated scenario does have CIs from SE-PRD-04 but overlaying two bands is visually noisy. Revisit with design after first user-test pass.
3. **What happens if the user changes the calendar between opening the Simulations tab and clicking Run?** The composite endpoint reads the calendar fresh at run time, so the displayed pre-run "Current Plan" summary may be stale. Surface a small "Plan refreshed" banner when the run completes if `calendar_summary.total_tasks` has changed since page load. Confirm with design at kickoff.
4. **Does "Save Forecast as Targets" need an undo?** SAR-E does not retain target version history, so a true undo is impossible. A lighter affordance — "View previous baseline" — could approximate it. Deferred.

### Resolved

- **Target persistence strategy.** Resolved 2026-04-23: SAR-E supersedes on edit (no version history). The save flow uses repeated `POST /sar-e/{account_id}/targets` without client-side PATCH fallback. Confirmed by SE-PRD-05.
- **Reuse of Dashboards' LineChart widget.** Resolved 2026-04-23: not reused. Composed axes exceed the widget's contract; this tab owns its own Recharts wrapper.
- **Rename scope.** Resolved 2026-04-23: Performance surface only (`frontend/src/pages/Performance*` + `frontend/src/components/performance/**`). Knowledge Graph's freeform Goals are out of scope.

## 10. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md)
- Foundation: [PE-PRD-01 — page shell](./PE-PRD-01-page-shell-and-routing.md) (TBD path — align once PE-PRD-01 file is authored)
- Sibling tabs: [PE-PRD-02 Analysis](./PE-PRD-02-analysis-tab.md), [PE-PRD-06 Targets](./PE-PRD-06-targets-tab.md)
- Upstream: [SE-PRD-03 VAR + baseline](../../sar-e/projects/SE-PRD-03-var-baseline.md), [SE-PRD-04 IRF scenarios](../../sar-e/projects/SE-PRD-04-irf-scenarios.md), [SE-PRD-05 Target derivation specialist](../../sar-e/projects/SE-PRD-05-target-derivation-specialist.md)
- Dashboards LineChart widget (not reused, but referenced): [DB-PRD-03](../../dashboards/projects/DB-PRD-03-dashboard-details-and-canvas.md)
- Figma reference: `docs/figma-export/src/app/pages/performance/SimulationsSection.tsx`
- Design tokens: [UI-PRD-01](../../ui/projects/UI-PRD-01-design-system-foundation.md)
- CLAUDE.md rules in scope: C-1 (TDD), C-2 (domain vocabulary — "Target"), C-5 (branded IDs), C-6 (`import type`), C-7 (minimal comments), C-9 (no premature extraction); T-2 (colocated `*.test.tsx`), T-3 (API integration tests), T-5 (prefer integration tests over heavy mocking), T-6 (unit-test complex algorithms); G-2 (`npm run format.fix`), G-3 (`npm run typecheck`)
