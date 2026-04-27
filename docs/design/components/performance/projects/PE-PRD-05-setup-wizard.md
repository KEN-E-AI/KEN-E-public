# PE-PRD-05 — Setup Wizard

**Status:** Blocked — resumes once PE-PRD-01, PE-PRD-04, SE-PRD-01, SE-PRD-02 (with the new `/sar-e/{account_id}/config/backfill-plan` endpoint), and IN-PRD-03 ship
**Owner team:** Frontend (Performance) — with one backend line in SAR-E for the new `POST /sar-e/{account_id}/config/backfill-plan` endpoint (owned by SE-PRD-02)
**Blocked by:** PE-PRD-01 (`/performance/setup` route reservation, `WizardStep` branded type, `ForecastingEnabledGate`, feature flag `performance_setup_wizard`); PE-PRD-04 (`<FunnelStageMappingEditor />` reused as the Step 2 selection primitive); SE-PRD-01 (`POST /sar-e/{account_id}/config/setup` wizard-completion endpoint, `GET /sar-e/{account_id}/config/status` for polling); SE-PRD-02 (**new** `POST /sar-e/{account_id}/config/backfill-plan` endpoint — Data Pipeline history probe + equalized-depth computation); IN-PRD-03 (`/settings/integrations` — the link target when `connected_integrations` is empty)
**Blocks:** PE-PRD-08 (integration testing depends on a working end-to-end wizard flow)
**Estimated effort:** 3–4 days

---

## 1. Context

The Setup Wizard is the onboarding flow that turns an opted-out account into a fully configured SAR-E consumer. Pre-wizard, forecasting is disabled and only **Dashboards + Configuration** are visible on `/performance` (the four SAR-E-backed tabs are hidden by `ForecastingEnabledGate`); no analytical data renders for those four tabs. Post-wizard, SAR-E has four Effectiveness KPIs seeded, a funnel mapping persisted, a weekly ingestion automation scheduled, and up to 104 weeks of backfilled KPI history in motion — the user lands on Analysis with all six tabs visible.

Three facts shape this PRD:

1. **The wizard is a dedicated route, not a modal.** `/performance/setup` is its own React page with its own URL-addressable step state (`?step=welcome|define_kpis|backfill_depth|review`). This resolves implementation-plan §10 open question 5. The dedicated route is important because (a) Step 1 may redirect the user out to `/settings/integrations` and we need to resume cleanly on return, and (b) abandoning the wizard leaves a durable Firestore draft that any future visit to the Configuration tab's empty state links back to.
2. **Backfill depth is computed, not user-chosen.** The VAR model requires equal-length series across the four KPIs (implementation-plan §3 backfill-depth rationale). The wizard's Step 3 calls a new SAR-E endpoint — `POST /sar-e/{account_id}/config/backfill-plan` — that queries Data Pipeline for the available history of each selected KPI source and returns `backfill_weeks = min(104, min(weeks_available_across_all_four_kpis))`. No slider. The UI surfaces the computed cap and names the limiting KPI when one drives it.
3. **The wizard owns the `performance_wizard_draft` Firestore doc.** Step transitions persist the draft; closing the tab is fine; returning to `/performance` shows a "Resume setup" banner on Configuration (PE-PRD-04 renders the banner, but this PRD owns the draft schema + the API to read, write, and delete it). Abandonment is tracked via a Weave span capturing `{step, abandoned_at, elapsed_seconds}` for product tuning.

The wizard uses `<FunnelStageMappingEditor />` from PE-PRD-04 as its Step 2 selection primitive. No re-implementation of the 4-row editor — this PRD composes the existing component with `showSaveButton={false}` and `showHistory={false}`, passing `availableKpis` derived from `available_kpi_sources` (the Data Pipeline jobs from connected integrations).

## 2. Scope

### In scope
- **`/performance/setup` route** — dedicated React page (not a modal on Configuration)
- **Four-step flow** enforced by the `WizardStep` union from PE-PRD-01: `"welcome" | "define_kpis" | "backfill_depth" | "review"`, with URL state at `?step=<step>`
- **Step 1 — Welcome:** intro copy, "Continue" button; branches to `/settings/integrations` via deep link if `connected_integrations` is empty; on return, resumes from the saved draft
- **Step 2 — Define KPIs:** for each of the four Objectives, user picks one KPI source from `available_kpi_sources`, names it, captures `aggregation` + `unit` + `typical_direction` via a guided form. Uses `<FunnelStageMappingEditor />` as the selection primitive. Uniqueness validated.
- **Step 3 — Backfill Depth:** calls `POST /sar-e/{account_id}/config/backfill-plan` with the four KPI source IDs; SAR-E returns `backfill_weeks = min(104, min(weeks_available_across_all_four_kpis))`. The UI displays the plan; if the cap is driven by a specific KPI, names it. No slider. Warning when `backfill_weeks < 26`.
- **Step 4 — Review + Confirm:** summarizes mappings + backfill plan; submits `POST /sar-e/{account_id}/config/setup`; polls `/config/status` every 2s until `setup_wizard_completed=true`; redirects to `/performance/analysis`
- **Wizard-draft Firestore doc** at `accounts/{account_id}/performance_wizard_draft` — Shape B convention; this PRD owns the schema + read / write / delete semantics
- **Resume flow:** on `?resume=true`, page loads the draft and navigates to the step stored in `draft.current_step`
- **Abandonment telemetry** — Weave span `performance.setup_wizard` with `{step, abandoned_at, elapsed_seconds, outcome}` on blur / unload / completion
- **Frontend + backend** — one small backend line owned here: the three wizard-draft endpoints (`GET`, `PUT`, `DELETE`) under `/api/v1/performance/{account_id}/wizard-draft`. The `POST /sar-e/{account_id}/config/backfill-plan` endpoint is owned by SE-PRD-02 (upstream dependency).
- Unit tests per step + draft persistence; Playwright spec for welcome → integrations redirect → return → KPI selection → backfill → review → completion; Playwright spec for abandonment → resume

### Out of scope
- **Account-creation-time wizard auto-launch** — user opts in via the Configuration CTA; no modal on first login (implementation-plan §8 non-goal)
- **Editing the wizard's outputs before submission via inline dialogs** — users confirm at Step 4 and edit post-completion via Configuration
- **The `POST /sar-e/{account_id}/config/backfill-plan` implementation** — SE-PRD-02 owns it. This PRD specifies the contract + consumes it.
- **KPI-authoring UI** separate from the wizard — the wizard is the onboarding path; ongoing KPI CRUD is deferred per PE-PRD-04 §2 out-of-scope
- **Multi-account bulk setup** — one account at a time
- **Skipping steps** — every step requires explicit confirmation (implementation-plan §8 non-goal: "Auto-advancing the wizard without user input")
- **Re-running the wizard after completion** — `setup_wizard_completed=true` is terminal; users edit via Configuration. Revisit if users need to reset.

## 3. Dependencies

- **PE-PRD-01:** `/performance/setup` route registration, `WizardStep` branded type, `ForecastingEnabledGate` (does NOT gate the wizard — the wizard is explicitly accessible pre-enablement), feature flag `performance_setup_wizard` registration.
- **PE-PRD-04:** `<FunnelStageMappingEditor />` reused as Step 2's selection primitive. Props contract defined in PE-PRD-04 §5.3; this PRD's Step 2 imports `FunnelStageMappingEditor` directly with `showSaveButton=false`, `showHistory=false`.
- **SE-PRD-01:** `POST /sar-e/{account_id}/config/setup` (wizard-completion endpoint; in one transaction seeds KPI registry, writes mapping, creates ingestion automation, triggers backfill); `GET /sar-e/{account_id}/config/status` (for completion polling); `GET /api/v1/performance/{account_id}/configuration` (reads `connected_integrations`, `available_kpi_sources`).
- **SE-PRD-02 (Weekly ingestion):** **new upstream endpoint** — `POST /sar-e/{account_id}/config/backfill-plan`. This PRD introduces the endpoint in the contract but SE-PRD-02 delivers the implementation. Contract specified in §6.2 below; also flagged in the Risks section.
- **IN-PRD-03 (Connection-management UI):** `/settings/integrations` — the redirect target when `connected_integrations` is empty. The wizard navigates to this route and relies on IN-PRD-03's connection-confirmation deep-link UX to return cleanly.
- **UI-PRD-01 (Soft Maximalism):** design tokens, shadcn primitives. No new primitives. Reuses Stepper pattern if available (confirm with design at kickoff — if no Stepper primitive exists, ship a local `<WizardStepper>` in `frontend/src/components/performance/wizard/`).
- **Feature Flags (FF-PRD-03):** `useFeatureFlag('performance_setup_wizard')`; when disabled, the route returns a 404-style "Not available" page and the Configuration CTA is hidden.
- **Weave tracing:** `performance.setup_wizard` span namespace.
- **Existing files to study:**
  - `docs/figma-export/src/app/pages/performance/PerformanceSetupWizard.tsx` — reference UX (if present); rebuild against Soft Maximalism
  - `frontend/src/components/performance/config/FunnelStageMappingEditor.tsx` (from PE-PRD-04) — reused component
  - `frontend/src/pages/Performance/ConfigurationTab.tsx` (from PE-PRD-04) — the entry point that launches this wizard
  - `api/src/kene_api/routers/performance.py` (from PE-PRD-01) — backend router extended with wizard-draft endpoints

## 4. Data contract

### 4.1 Wizard-draft schema (owned by this PRD)

Firestore path: `accounts/{account_id}/performance_wizard_draft` (Shape B; single document per account).

```python
# api/src/kene_api/models/performance_wizard_models.py

class PerformanceWizardDraft(BaseModel):
    account_id: str
    current_step: Literal["welcome", "define_kpis", "backfill_depth", "review"]

    # Step 2 state (nullable until Step 2 is touched)
    kpi_selections: list[WizardKPISelection] | None = None

    # Step 3 state (nullable until Step 3's backfill-plan call completes)
    backfill_plan: BackfillPlan | None = None

    # Metadata
    started_at: datetime
    updated_at: datetime
    started_by_user_id: str
    resumed_count: int = 0                              # incremented on each resume

class WizardKPISelection(BaseModel):
    objective: Literal["Problem Awareness", "Brand Awareness", "Consideration", "Conversion"]
    source_job_id: str                                  # from available_kpi_sources
    display_name: str                                   # user-edited
    unit: Literal["count", "currency", "percent", "duration_seconds"]
    typical_direction: Literal["up_is_good", "down_is_good", "neutral"]
    aggregation: Literal["sum", "mean", "weighted_mean"]

class BackfillPlan(BaseModel):
    backfill_weeks: int                                 # computed; ≤ 104
    weeks_available_per_kpi: dict[str, int]            # source_job_id → weeks
    limiting_source_job_id: str | None                  # set when the cap is driven by a specific KPI (< 104)
    computed_at: datetime
```

TypeScript mirror at `frontend/src/types/performance/wizard.ts`:

```typescript
import type { Brand } from '@/types/brand';

export type AccountId = Brand<string, 'AccountId'>;
export type SourceJobId = Brand<string, 'SourceJobId'>;

export type WizardStep = 'welcome' | 'define_kpis' | 'backfill_depth' | 'review';

export interface WizardKPISelection {
  objective: FunnelObjective;
  source_job_id: SourceJobId;
  display_name: string;
  unit: 'count' | 'currency' | 'percent' | 'duration_seconds';
  typical_direction: 'up_is_good' | 'down_is_good' | 'neutral';
  aggregation: 'sum' | 'mean' | 'weighted_mean';
}

export interface BackfillPlan {
  backfill_weeks: number;
  weeks_available_per_kpi: Record<SourceJobId, number>;
  limiting_source_job_id: SourceJobId | null;
  computed_at: string;
}

export interface PerformanceWizardDraft {
  account_id: AccountId;
  current_step: WizardStep;
  kpi_selections: WizardKPISelection[] | null;
  backfill_plan: BackfillPlan | null;
  started_at: string;
  updated_at: string;
  started_by_user_id: string;
  resumed_count: number;
}
```

Brand types per CLAUDE.md C-5; `import type` per C-6.

### 4.2 Backfill-plan request/response (contract for SE-PRD-02)

This PRD specifies the contract; SE-PRD-02 delivers the implementation. Called from Step 3.

```python
# Request body — POST /api/v1/sar-e/{account_id}/config/backfill-plan
class BackfillPlanRequest(BaseModel):
    kpi_source_job_ids: list[str]                       # exactly 4 source job IDs

# Response body
class BackfillPlanResponse(BaseModel):
    backfill_weeks: int                                 # min(104, min_weeks_available)
    weeks_available_per_kpi: dict[str, int]            # source_job_id → integer weeks
    limiting_source_job_id: str | None                  # None if all four sources have ≥104 weeks
    computed_at: datetime
```

Semantics:
- SAR-E queries Data Pipeline's history-depth indicator per `source_job_id`
- `backfill_weeks = min(104, min(weeks_available_per_kpi.values()))`
- `limiting_source_job_id` is set to the source that produced the minimum **only when that minimum is <104**; when all sources have ≥104 weeks, it's `None` (the 104-week cap applies and no single source is driving it)
- If multiple sources tie for the minimum, `limiting_source_job_id` is the lexicographically first source job id (deterministic for display)
- Errors: if any `kpi_source_job_ids` entry is not a valid Data Pipeline job for the account, return 422 with the offending id(s)

### 4.3 Setup-completion request (SE-PRD-01 existing contract — consumed here)

```python
# POST /api/v1/sar-e/{account_id}/config/setup
class SetupRequest(BaseModel):
    kpis: list[WizardKPISelection]                      # the 4 selections
    funnel_mapping: dict[FunnelObjective, str]          # Objective → source_job_id (SAR-E coins the kpi_id)
    initial_backfill_weeks: int                         # from the backfill plan
```

### 4.4 Wizard-draft endpoints (owned here)

```python
# GET  /api/v1/performance/{account_id}/wizard-draft  → PerformanceWizardDraft | 404
# PUT  /api/v1/performance/{account_id}/wizard-draft  → upsert full draft
# DELETE /api/v1/performance/{account_id}/wizard-draft → remove draft ("Start over")
```

All three gated by `editor`-role minimum; audit entries written per DM-PRD-07. The Configuration tab's "Start over" affordance (PE-PRD-04) calls the DELETE.

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `frontend/src/pages/Performance/SetupWizardPage.tsx` — root page at `/performance/setup`; reads `?step=` + `?resume=` query params; orchestrates the four-step flow |
| Create | `frontend/src/components/performance/wizard/WizardStepper.tsx` — stepper indicator (if no UI primitive exists; confirm with design at kickoff) |
| Create | `frontend/src/components/performance/wizard/WelcomeStep.tsx` — Step 1 |
| Create | `frontend/src/components/performance/wizard/DefineKPIsStep.tsx` — Step 2; composes `<FunnelStageMappingEditor />` |
| Create | `frontend/src/components/performance/wizard/KPISelectionForm.tsx` — per-Objective form (display_name / unit / typical_direction / aggregation) used inside Step 2 |
| Create | `frontend/src/components/performance/wizard/BackfillDepthStep.tsx` — Step 3; renders the computed plan + limiting-KPI callout |
| Create | `frontend/src/components/performance/wizard/ReviewStep.tsx` — Step 4; summarizes + submits + polls |
| Create | `frontend/src/components/performance/wizard/WizardFooter.tsx` — shared navigation (Back / Continue / Submit) |
| Create | `frontend/src/hooks/useWizardDraft.ts` — TanStack Query hook for GET + PUT + DELETE against `/performance/{account_id}/wizard-draft` |
| Create | `frontend/src/hooks/useBackfillPlan.ts` — mutation hook for `POST /sar-e/{account_id}/config/backfill-plan` |
| Create | `frontend/src/hooks/useSetupSubmit.ts` — mutation hook for `POST /sar-e/{account_id}/config/setup` + polling `/config/status` |
| Create | `frontend/src/services/performanceWizardApi.ts` — axios wrappers (draft + backfill-plan + setup + status) |
| Create | `frontend/src/types/performance/wizard.ts` — branded types + `WizardStep` + `WizardKPISelection` + `BackfillPlan` + `PerformanceWizardDraft` |
| Create | `api/src/kene_api/models/performance_wizard_models.py` — Pydantic shapes (mirror of §4.1) |
| Create | `api/src/kene_api/routers/performance_wizard.py` — GET / PUT / DELETE wizard-draft endpoints; OIDC via existing account-scoping middleware |
| Modify | `api/src/kene_api/routers/performance.py` — register the wizard-draft router under `/api/v1/performance/{account_id}/wizard-draft` |
| Modify | `api/src/kene_api/main.py` — mount the router |
| Create | `frontend/src/pages/Performance/__tests__/SetupWizardPage.test.tsx` |
| Create | `frontend/src/components/performance/wizard/__tests__/WelcomeStep.test.tsx` |
| Create | `frontend/src/components/performance/wizard/__tests__/DefineKPIsStep.test.tsx` |
| Create | `frontend/src/components/performance/wizard/__tests__/BackfillDepthStep.test.tsx` |
| Create | `frontend/src/components/performance/wizard/__tests__/ReviewStep.test.tsx` |
| Create | `frontend/src/hooks/__tests__/useWizardDraft.test.ts` |
| Create | `frontend/src/hooks/__tests__/useBackfillPlan.test.ts` |
| Create | `frontend/src/hooks/__tests__/useSetupSubmit.test.ts` |
| Create | `api/tests/unit/test_performance_wizard_models.py` |
| Create | `api/tests/integration/test_performance_wizard_router.py` |
| Create | `frontend/e2e/performance-setup-wizard-happy-path.spec.ts` (Playwright) |
| Create | `frontend/e2e/performance-setup-wizard-abandon-resume.spec.ts` (Playwright) |

### 5.1 Step 1 — Welcome

Renders intro copy, bullet points explaining what forecasting does, and a single "Continue" button. On `mount`:

1. Read the Configuration bundle (`GET /api/v1/performance/{account_id}/configuration`) → extract `connected_integrations`.
2. If `connected_integrations.length === 0`: render a sub-CTA "Connect an integration first" that navigates to `/settings/integrations?return_to=/performance/setup`. Keep the draft in `welcome` state.
3. On return from `/settings/integrations` (detected via `document.referrer` or a `?return_to` echo), re-read the bundle and advance automatically if connections are now present — but still require the user to click "Continue" to move to Step 2 (no auto-advance per implementation-plan §8).

Draft transition: `{ current_step: 'welcome', kpi_selections: null, backfill_plan: null }` — written once on first arrival if no draft exists.

### 5.2 Step 2 — Define KPIs

1. Renders `<FunnelStageMappingEditor mapping={mappingFromDraft} availableKpis={availableKpisFromSources} onMappingChange={...} showSaveButton={false} showHistory={false} />` where:
   - `mappingFromDraft` is derived from `draft.kpi_selections` (maps Objective → `source_job_id`)
   - `availableKpisFromSources` is derived from `configurationBundle.available_kpi_sources`, each transformed into an `EffectivenessKPI`-shaped object using the source's `unit_suggestion` and a synthesized `display_name`
2. Below the editor, for each of the 4 selected source jobs, renders `<KPISelectionForm>` — inputs for display_name, unit, typical_direction, aggregation. Defaults: display_name = source's `display_name`, unit = source's `unit_suggestion`, typical_direction = `up_is_good`, aggregation = `sum`.
3. Validation: all four Objectives must have a selection; all four display_names must be non-empty and ≤100 chars.
4. On "Continue": PUT the draft with the updated `kpi_selections` array and `current_step = 'backfill_depth'`.

### 5.3 Step 3 — Backfill Depth

1. On entry, fire `POST /sar-e/{account_id}/config/backfill-plan` with the four `source_job_id`s from the draft.
2. Render a loading skeleton while the call is in flight (p95 target: 3s — SAR-E queries Data Pipeline history-depth indicators).
3. On response:
   - Primary line: "We will backfill **{backfill_weeks} weeks** of historical data across all four KPIs."
   - If `limiting_source_job_id !== null`: secondary line naming the KPI — "{KPI display_name} has only {weeks_available_per_kpi[limiting_source_job_id]} weeks of data available; all four KPIs will be backfilled to the same depth to keep the series aligned."
   - If `backfill_weeks < 26`: warning banner — "Forecasts will start at low confidence until ~6 months of history accumulates."
4. No slider. The user cannot change the number. Copy emphasizes that VAR requires equal-length series.
5. PUT the draft with `backfill_plan` and `current_step = 'review'` on "Continue".
6. On API error (e.g., Data Pipeline history-depth probe fails), show an inline retry affordance; do not advance the draft.

### 5.4 Step 4 — Review + Confirm

1. Summary panel:
   - Funnel Mapping table (4 rows, read-only)
   - Backfill plan summary (weeks + limiting KPI if applicable)
   - Connected integrations chips
2. Submit button fires `POST /sar-e/{account_id}/config/setup` with:
   ```json
   {
     "kpis": [...draft.kpi_selections],
     "funnel_mapping": { "Problem Awareness": "source_job_id_1", ... },
     "initial_backfill_weeks": draft.backfill_plan.backfill_weeks
   }
   ```
3. On 200, begin polling `GET /sar-e/{account_id}/config/status` every 2s.
4. Render a progress panel with: "Seeding KPIs", "Scheduling ingestion", "Starting backfill" — updated based on status transitions. (SAR-E's `/config/status` returns `setup_wizard_completed` as a boolean; this PRD does not introduce intermediate progress states — the progress phrasing is UI-side copy while the backend completes its transaction.)
5. On `setup_wizard_completed=true`: DELETE the draft; invalidate the Configuration bundle; redirect to `/performance/analysis` with a one-time toast "Forecasting enabled. Welcome to Performance."
6. On submit failure: surface the error; leave the draft at `current_step='review'` so the user can retry.

### 5.5 Draft persistence cadence

- **On step entry:** PUT the draft with the new `current_step`
- **On significant input:** debounced PUT (500ms) for Step 2 edits; immediate PUT on Step 3 backfill-plan completion
- **On page unload:** flush pending PUT via `beforeunload`
- **On completion:** DELETE
- **`resumed_count`:** incremented on every page load where `?resume=true` is present or the draft's `current_step !== 'welcome'` when navigating in

### 5.6 Resume flow

1. User clicks "Resume setup" on Configuration's `<ResumeSetupBanner>` → navigates to `/performance/setup?resume=true`
2. Page loads the draft; navigates to `?step=<draft.current_step>` if not already there
3. Each step reads its state from the draft (Step 2 reads `kpi_selections`, Step 3 reads `backfill_plan`)
4. If `draft.current_step === 'backfill_depth'` but `draft.backfill_plan === null`, re-fire the backfill-plan call (defensive — a draft that stored Step 2 but failed to persist Step 3's response)

### 5.7 Telemetry

Weave span `performance.setup_wizard` captures:
- `account_id_hash`
- `step` — step at the time of span emission
- `outcome` — `'completed' | 'abandoned' | 'error'`
- `elapsed_seconds` — from `draft.started_at` to span emission
- `resumed_count`
- `abandoned_at` — populated only when `outcome='abandoned'`, set on `beforeunload` or tab blur

The span is written:
- On every step transition (for step-timing analysis)
- On `beforeunload` with `outcome='abandoned'` when `current_step !== 'review'` (best-effort via `navigator.sendBeacon`)
- On completion with `outcome='completed'`
- On submit error with `outcome='error'`

No PII in the span payload.

## 6. API contract (owned + consumed)

### 6.1 Owned by this PRD

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/performance/{account_id}/wizard-draft` | Returns the draft or 404. Role: editor minimum. |
| `PUT` | `/api/v1/performance/{account_id}/wizard-draft` | Upsert. Body: `PerformanceWizardDraft` (minus `started_at` if create / minus `updated_at` always — server sets). |
| `DELETE` | `/api/v1/performance/{account_id}/wizard-draft` | Removes the draft. Used on completion + from Configuration's "Start over". |

### 6.2 New upstream endpoint specified here, implemented by SE-PRD-02

| Method | Path | Purpose | Owner |
|---|---|---|---|
| `POST` | `/api/v1/sar-e/{account_id}/config/backfill-plan` | **NEW in SE-PRD-02.** Body: `{kpi_source_job_ids: string[]}` (exactly 4). Response: `BackfillPlanResponse` (§4.2). SAR-E queries Data Pipeline history-depth indicators per source; returns the equalized depth. | SE-PRD-02 |

This endpoint does not exist in the current SAR-E implementation plan. This PRD's Dependencies and Risks sections call out that SE-PRD-02 must deliver it before PE-PRD-05 can ship. Contract specified in §4.2 above; SE-PRD-02 owns the implementation.

### 6.3 Consumed (already owned by SAR-E)

| Method | Path | Purpose | Owner |
|---|---|---|---|
| `GET` | `/api/v1/performance/{account_id}/configuration` | Reads `connected_integrations` + `available_kpi_sources` | PE-PRD-01 |
| `GET` | `/api/v1/sar-e/{account_id}/config/status` | Polling target during Step 4 | SE-PRD-01 |
| `POST` | `/api/v1/sar-e/{account_id}/config/setup` | Step 4 submit — in one transaction seeds KPIs + writes mapping + creates ingestion automation + triggers backfill | SE-PRD-01 |

## 7. Acceptance criteria

1. Navigating to `/performance/setup` on an account with `forecasting_enabled=false` and no draft creates a draft at `accounts/{account_id}/performance_wizard_draft` with `current_step='welcome'`, `started_at=now`, `started_by_user_id=current_user`, and renders Step 1.
2. Step 1 "Continue" button is disabled when `connected_integrations.length === 0`; a sub-CTA "Connect an integration first" navigates to `/settings/integrations?return_to=/performance/setup`. On return, the button enables.
3. Step 2 composes `<FunnelStageMappingEditor />` with `showSaveButton=false` and `showHistory=false`. Selecting a source job for an Objective that's already used by another Objective surfaces an inline error (from the editor's own uniqueness validator).
4. Step 2 renders four `<KPISelectionForm>` instances (one per Objective) with defaults seeded from the selected source's `unit_suggestion`. Edits persist to the draft on blur with a 500ms debounce.
5. Step 2 "Continue" button is disabled until all four Objectives have a valid selection (non-empty display_name ≤100 chars, all four required form fields set).
6. Step 3 fires `POST /sar-e/{account_id}/config/backfill-plan` with the four source_job_ids from the draft; on success the panel renders the `backfill_weeks` value.
7. Step 3 names the limiting KPI when `limiting_source_job_id !== null`: copy includes "{KPI display_name} has only {N} weeks of data available…" verbatim. When all four sources have ≥104 weeks, no limiting-KPI callout renders.
8. Step 3 shows a warning banner when `backfill_weeks < 26`: "Forecasts will start at low confidence until ~6 months of history accumulates." No slider renders.
9. Step 3 on API error (e.g., 5xx from the backfill-plan endpoint) shows an inline retry affordance; the draft is not advanced.
10. Step 4 summary panel renders the four KPI mappings + the backfill plan + connected-integration chips, all read-only.
11. Step 4 submit fires `POST /sar-e/{account_id}/config/setup` with the correct payload shape (§5.4); on 200 begins polling `/config/status` every 2s.
12. Step 4 on `setup_wizard_completed=true`: DELETEs the draft; invalidates the Configuration bundle; redirects to `/performance/analysis` with a success toast.
13. Abandonment: closing the tab at Step 3 persists the draft with `current_step='backfill_depth'` and `backfill_plan` populated. Navigating to `/performance` next session lands on Configuration (PE-PRD-04's `<ResumeSetupBanner>` renders). Clicking "Resume setup" navigates to `/performance/setup?resume=true`, which opens Step 3 with the prior `backfill_plan` intact.
14. Weave span `performance.setup_wizard` fires on every step transition with `{step, elapsed_seconds, resumed_count}`; on `beforeunload` at non-terminal steps with `outcome='abandoned'`; on completion with `outcome='completed'`.
15. Backend endpoints: `GET /performance/{account_id}/wizard-draft` returns 404 for missing drafts + 200 with the draft otherwise; `PUT` upserts; `DELETE` removes and returns 204. All three require editor role minimum; viewer role gets 403.
16. Cross-account access (a user hitting `/performance/setup` for an account they don't belong to) returns 403 and redirects to `/accounts`.
17. Feature-flag gating: with `performance_setup_wizard=false`, `/performance/setup` renders a "Setup is currently unavailable" page and the Configuration tab's CTA is hidden.
18. `resumed_count` increments by 1 on each navigation to `/performance/setup?resume=true` or on load when the draft's `current_step !== 'welcome'`.
19. Start-over flow: Configuration's "Start over" action on the resume banner DELETEs the draft; on next `/performance/setup` visit, a fresh draft is created at `welcome`.
20. All SAR-E contract calls (backfill-plan, setup, status) are contract-tested against SAR-E's OpenAPI on CI via `api/tests/contract/test_sar_e_openapi.py`; drift fails the build.
21. `make lint`, `npm run build`, `npm run typecheck`, `npm run format.fix`, `npm run lint` all clean; unit + Playwright suites pass.

## 8. Test plan

**Unit tests — page** (`SetupWizardPage.test.tsx`):
- Routes to `?step=welcome` on first load with no draft
- Hydrates from draft on `?resume=true`
- `beforeunload` handler fires `navigator.sendBeacon` with the abandonment span
- Feature-flag off → renders "Setup is currently unavailable"
- Cross-account redirect

**Unit tests — Step 1** (`WelcomeStep.test.tsx`):
- Continue disabled when `connected_integrations` is empty
- "Connect an integration" CTA has correct `return_to` param
- Continue enabled after integrations detected on return

**Unit tests — Step 2** (`DefineKPIsStep.test.tsx`):
- Renders `<FunnelStageMappingEditor />` with correct props (`showSaveButton=false`, `showHistory=false`)
- Four `<KPISelectionForm>` instances render once four selections exist
- Continue disabled until every Objective has a selection + every form is valid
- Edits persist to draft with 500ms debounce (tested with fake timers)
- Uniqueness validation inherited from the editor (tested separately in PE-PRD-04)

**Unit tests — Step 3** (`BackfillDepthStep.test.tsx`):
- On entry, fires `POST /sar-e/{account_id}/config/backfill-plan` with the 4 source_job_ids from the draft
- Limiting-KPI callout renders when `limiting_source_job_id !== null`; not rendered otherwise
- `<26 weeks` warning banner renders at 25 weeks, not at 26 weeks (boundary)
- Retry affordance on API error; draft not advanced
- No slider in the DOM

**Unit tests — Step 4** (`ReviewStep.test.tsx`):
- Submit payload shape matches SE-PRD-01's `POST /config/setup` contract
- On 200, begins polling `/config/status`; polling stops on `setup_wizard_completed=true`
- On terminal state, DELETEs the draft and redirects to `/performance/analysis`
- On submit error, shows inline error; does not DELETE the draft

**Unit tests — hooks:**
- `useWizardDraft`: GET returns `PerformanceWizardDraft | null`; PUT upserts with optimistic update; DELETE invalidates cache
- `useBackfillPlan`: mutation fires correct body; response typed correctly; errors categorized
- `useSetupSubmit`: submit → polling → completion transitions; timeout at 60s with retry affordance

**Unit tests — backend** (`test_performance_wizard_models.py`):
- `PerformanceWizardDraft` validates all fields
- `WizardKPISelection` rejects invalid `unit` / `typical_direction` / `aggregation`
- `BackfillPlan.backfill_weeks` must be ≥0 and ≤104

**Integration tests — backend** (`test_performance_wizard_router.py`):
- GET on missing draft → 404
- PUT creates then updates; `updated_at` advances
- DELETE removes; subsequent GET → 404
- Role gating: viewer → 403 on all three; editor → 2xx
- Cross-account → 403

**Playwright — happy path** (`performance-setup-wizard-happy-path.spec.ts`):
- Seed an account with 1 connected integration and 4 available KPI sources (each with 52 weeks of history)
- Navigate to `/performance/configuration` → click "Set up forecasting"
- Step 1: click Continue
- Step 2: select 4 KPIs via the `<FunnelStageMappingEditor />`, fill 4 `<KPISelectionForm>`s, click Continue
- Step 3: verify the panel shows "52 weeks" (limiting KPI named if applicable) → click Continue
- Step 4: verify summary → click Submit → wait for polling to complete
- Verify redirect to `/performance/analysis`, verify all 5 tabs visible, verify `forecasting_enabled=true` via `/config/status`
- Verify draft doc deleted

**Playwright — abandon + resume** (`performance-setup-wizard-abandon-resume.spec.ts`):
- Seed an account with 1 connected integration and 4 available KPI sources
- Navigate to `/performance/setup` → complete Step 1 → complete Step 2 → arrive at Step 3 → close tab
- Return next session → navigate to `/performance` → auto-routes to `/performance/configuration` → verify `<ResumeSetupBanner>` renders
- Click "Resume setup" → verify URL is `/performance/setup?resume=true` → verify Step 3 renders with the prior `backfill_plan`
- Verify `resumed_count` incremented to 1 in the draft

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| **New upstream endpoint** `POST /sar-e/{account_id}/config/backfill-plan` does not yet exist in the SAR-E implementation plan | Specified in §4.2 + §6.2 of this PRD; called out in the header's "Blocked by" line. SE-PRD-02 must add this endpoint to its deliverables before PE-PRD-05 can ship. File an upstream issue in the SAR-E backlog at kickoff. |
| Data Pipeline history-depth probe is slow on accounts with many KPI sources | The probe only runs against the 4 selected source_job_ids. SE-PRD-02 should cache depth per source for ~5 minutes to avoid repeated queries during draft iteration. Specify in the SE-PRD-02 handoff. |
| User abandons mid-wizard on a mobile device where `beforeunload` is unreliable | Accept — the draft is still persisted at each step transition (PUT). Abandonment telemetry is best-effort; loss of an abandonment span for a single session is not a correctness issue. |
| Step 2 display_name collisions across Objectives (user names two KPIs "Clicks") | Not blocked by the wizard — SAR-E's `EffectivenessKPI` is uniquely identified by `kpi_id`, not `display_name`. Inline warning if two Objectives share a display_name, but allow. |
| Step 3 copy "all four KPIs will be backfilled to the same depth" confuses users who don't understand VAR | User-tested at kickoff. If copy doesn't land, switch to a progressive-disclosure explanation with a tooltip. |
| Setup transaction at Step 4 fails partway (KPIs seeded but backfill didn't kick off) | SE-PRD-01's `/config/setup` is specified as a single transaction. If SE-PRD-01 doesn't deliver atomicity, fall back to client-side orchestration + compensating DELETEs. Confirm with SAR-E team at kickoff. |
| All SAR-E contract calls (backfill-plan, setup, status) drift from spec mid-build | Contract-tested against SAR-E's OpenAPI on CI (`api/tests/contract/test_sar_e_openapi.py`); failures block merge. |
| `<FunnelStageMappingEditor />` props contract from PE-PRD-04 changes before this PRD ships | TypeScript catches drift at compile time; PE-PRD-04's acceptance criteria include a compile-time import test from PE-PRD-05's Step 2. |
| Draft doc bloats with repeated edits + `resumed_count` growth | Shape B + single doc per account; max size cap is 1 MB (Firestore). Realistic draft size is <5 KB even after many edits. Not a concern. |
| User starts a wizard, completes it, later revokes their integrations | Out of scope for this PRD. SAR-E's `/config/status` will eventually reflect broken ingestion; Performance's gate logic handles the display. Revisit in a later "re-onboarding" PRD. |
| Polling `/config/status` at 2s for a long-running setup transaction | SE-PRD-01's setup transaction p95 target is <5s (KPI seeding + automation creation; backfill runs async after completion). 2s polling is fine. If target slips, extend to 5s after 30s elapsed. |

### Open questions

1. **Should the wizard enforce a minimum `connected_integrations.length`** before allowing Step 1 → Step 2 transition, or is "at least one" sufficient? v1 answer: at least one. Confirm with product at kickoff — if multi-integration is the normal onboarding pattern, we may want to require more.
2. **Does Step 2 need a "preview" of what each KPI source looks like** (sample values, time range)? Nice-to-have. Deferred to post-v1 iteration unless user testing surfaces confusion.
3. **What happens when a user reopens the wizard after `setup_wizard_completed=true`?** v1 answer: `/performance/setup` redirects to `/performance/analysis` if already complete. Revisit if product wants a "reconfigure" flow; for now, users edit via Configuration.
4. **Should abandonment trigger a one-time email after 24h?** Retention tactic. Defer to a lifecycle-marketing discussion; out of scope for this PRD.
5. **`<WizardStepper>` primitive reuse** — does the design system have a Stepper component? Confirm with design at kickoff; if not, ship a local one in `frontend/src/components/performance/wizard/`.

### Resolved

- **Wizard UX home.** Resolved 2026-04-23: dedicated route at `/performance/setup` (not a modal on Configuration). Per implementation-plan §10 open question 5.
- **Wizard resume UX.** Resolved 2026-04-23: banner only on the Configuration empty-state; no force-route on return. Per implementation-plan §10 open question 6.
- **Backfill depth UX.** Resolved 2026-04-23: computed (no slider); limiting KPI named when the cap is driven by data availability. VAR requires equal-length series.
- **Wizard-draft ownership.** Resolved 2026-04-23: this PRD owns the schema + endpoints; PE-PRD-04 consumes via the `<ResumeSetupBanner>`.

## 10. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md)
- Foundation: [PE-PRD-01 — page shell](./PE-PRD-01-page-shell-and-routing.md) (TBD path — align once PE-PRD-01 file is authored)
- Sibling: [PE-PRD-04 Configuration tab](./PE-PRD-04-configuration-tab.md) (exports `<FunnelStageMappingEditor />` consumed by Step 2; hosts the resume banner)
- Upstream: [SE-PRD-01 Configuration foundation + setup state](../../sar-e/projects/SE-PRD-01-configuration-foundation.md), [SE-PRD-02 Weekly ingestion](../../sar-e/projects/SE-PRD-02-weekly-kpi-ingestion.md) — **must add the `POST /sar-e/{account_id}/config/backfill-plan` endpoint specified in §4.2 + §6.2**
- Related: [IN-PRD-03 Connection-management UI](../../integrations/projects/IN-PRD-03-connection-management-ui.md) (`/settings/integrations` — the redirect target in Step 1)
- Design tokens: [UI-PRD-01](../../ui/projects/UI-PRD-01-design-system-foundation.md)
- Figma reference: `docs/figma-export/src/app/pages/performance/PerformanceSetupWizard.tsx` (rebuild against Soft Maximalism)
- CLAUDE.md rules in scope: C-1 (TDD), C-2 (domain vocabulary — Objective / Effectiveness KPI / backfill / draft), C-5 (branded IDs — `AccountId`, `SourceJobId`), C-6 (`import type`), C-8 (`type` default), C-9 (no premature extraction; `<FunnelStageMappingEditor />` reuse is justified by PE-PRD-04 + PE-PRD-05 co-use); PY-1 (type hints), PY-2 (Pydantic), PY-5 (context managers), PY-7 (no bare except); D-1 (Firestore session management), D-2 (Pydantic models for entities), D-5 (no hardcoded credentials); T-1 (colocated pytest), T-2 (colocated `*.test.tsx`), T-3 (API integration tests), T-4 (pure-logic vs DB-touching split), T-6 (unit-test complex algorithms), T-7 (pytest fixtures); G-1 (`make lint`), G-2 (`npm run format.fix`), G-3 (`npm run typecheck`)
