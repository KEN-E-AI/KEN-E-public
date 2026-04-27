# PE-PRD-04 — Configuration Tab

**Status:** Blocked — resumes once PE-PRD-01 and SE-PRD-01 ship
**Owner team:** Frontend (Performance)
**Blocked by:** PE-PRD-01 (`/performance` shell, `PerformanceDateRangeContext`, `ForecastingEnabledGate`, `FunnelObjective` / `EffectivenessKPIId` branded types, feature-flag wiring); SE-PRD-01 (`GET /sar-e/{account_id}/config/status`, `/config/funnel-mapping`, `/config/thresholds`, `/config/channel-coverage`, `/config/effectiveness-kpis` — every mutation target this tab writes to)
**Blocks:** PE-PRD-05 (Setup Wizard reuses the Funnel Stage Mapping editor component defined here); PE-PRD-08 (integration testing depends on the finished Configuration tab for the pre-wizard + post-wizard flows)
**Estimated effort:** 3 days

---

## 1. Context

The Configuration tab is the settings surface for SAR-E. Once forecasting is enabled, it holds three editors: Funnel Stage Mapping (the 4-row Objective → KPI binding that drives every analytical view), Thresholds (per-KPI anomaly bounds), and Channel Coverage (the data-availability matrix that tells SAR-E which channels to exclude from VAR training). Pre-wizard, the tab owns a very different job — it's the **only** visible Performance tab, rendering an empty-state CTA that launches the setup wizard and (when a draft exists) a "Resume setup" banner that rehydrates it.

Three facts shape this PRD:

1. **Configuration has two distinct modes — pre-wizard and post-wizard — driven entirely by `forecasting_enabled`.** Pre-wizard, the four SAR-E-backed tabs (Analysis / Simulations / Targets / Diagnostics) are hidden from the nav by `ForecastingEnabledGate` (PE-PRD-01); the user sees **Dashboards + Configuration**, and Configuration only shows the CTA. Post-wizard, all six tabs appear and Configuration renders the three editor panels. No middle state — the wizard-completion event from SE-PRD-01 flips the gate atomically.
2. **The Funnel Stage Mapping editor is reused by the wizard.** PE-PRD-05's Step 2 ("Define KPIs") presents the same 4-row Objective → KPI selection primitive with the same uniqueness validator. This PRD ships that primitive as a standalone `<FunnelStageMappingEditor />` component so the wizard can compose it without re-implementing validation logic.
3. **CLV editor is descoped; ExogenousEventsSection has moved to Calendar.** The Figma export shows both inside Configuration. Per the Performance implementation plan (§8 Non-goals), CLV does not ship in v1, and exogenous events live as Calendar activities with `category in ["holiday", "promotion", "event"]` (owned by project-tasks PR-PRD-03). This PRD **removes** both surfaces. Copy on the Analysis tab's External Factors panel links users to the Calendar for edits; no Configuration entry point is needed.

The tab does not call any Performance-owned bundle endpoints for mutations — saves go directly to SAR-E (`PUT /sar-e/{account_id}/config/*`). The only read is the Configuration bundle (`GET /api/v1/performance/{account_id}/configuration`), which SAR-E-proxies the editor state so the Configuration tab and the setup wizard share one endpoint.

## 2. Scope

### In scope
- `ConfigurationTab` page at `/performance/configuration` with two render modes keyed on `forecasting_enabled`
- **Pre-wizard mode:**
  - Empty-state CTA ("Set up forecasting to unlock performance insights") with a primary button that navigates to `/performance/setup` (PE-PRD-05)
  - "Resume setup" banner variant shown when `accounts/{account_id}/performance_wizard_draft` exists (Firestore read via the Configuration bundle)
  - Links to `/settings/integrations` when `connected_integrations` is empty, explaining that at least one integration must be connected first
- **Post-wizard mode:**
  - **Funnel Stage Mapping editor** — 4-row table. Each row: Objective label (fixed) → KPI dropdown populated from `available_kpis` (SAR-E's currently-defined Effectiveness KPIs). Uniqueness validator (no two Objectives mapped to the same KPI). Save / dirty-state / History drawer (reads `GET /sar-e/{account_id}/config/funnel-mapping/history`). Saves via `PUT /sar-e/{account_id}/config/funnel-mapping`.
  - **Thresholds editor** — per-KPI bounds (warn_low, warn_high, critical_low, critical_high). Number inputs with unit labels drawn from `EffectivenessKPI.unit`. Saves via `PUT /sar-e/{account_id}/config/thresholds`.
  - **Channel Coverage editor** — matrix view: rows = channels, columns = weeks (default 26-week window with ability to scroll), cells = `has_data` checkboxes. Saves via `PUT /sar-e/{account_id}/config/channel-coverage`.
  - Each section is an independent subcomponent with its own save + dirty + error states (implementation-plan §9 risk: "Configuration tab grows over time")
- **Standalone `<FunnelStageMappingEditor />` component** exported from `frontend/src/components/performance/config/FunnelStageMappingEditor.tsx`; PE-PRD-05's wizard imports it directly
- TanStack Query hooks: `useConfiguration` (page load), `useFunnelMappingMutation`, `useThresholdsMutation`, `useChannelCoverageMutation`
- Unit tests per editor; Playwright spec for pre-wizard → wizard launch → post-wizard flow + funnel-mapping save round-trip

### Out of scope
- **CLV editor** — descoped per product decision; no component, no copy, no API call
- **ExogenousEventsSection** — moved to Calendar (PR-PRD-03 owns editing; this PRD removes the Figma surface entirely)
- **KPI CRUD** outside the wizard (adding / removing KPIs post-setup) — SE-PRD-01 exposes `POST /config/effectiveness-kpis` and the wizard consumes it; a power-user "Add KPI" affordance is deferred to a future PRD
- **Funnel Mapping migration UX** — when the mapping changes, SAR-E invalidates analytical caches (per the implementation plan's risk table); a "your trendlines may shift" pre-save warning is in scope, but backfilling historical views against the new mapping is not
- **Wizard implementation** — owned by PE-PRD-05; this PRD only exposes the CTA + resume banner
- **Per-threshold notification emission** — SAR-E v1 does not emit notifications on threshold breach (SE-PRD implementation plan §10 resolved); the editor only persists values
- **Bulk threshold editing** (copy from one KPI to another) — v1 edits are per-KPI

## 3. Dependencies

- **PE-PRD-01:** page shell + `PerformanceDateRangeContext` + `ForecastingEnabledGate` + branded types + feature flag `performance_configuration_tab`. Configuration is the only tab visible pre-wizard, driven by gate logic shipped in PE-PRD-01.
- **SE-PRD-01 (Configuration foundation + setup state):** every mutation endpoint this tab writes to — `PUT /config/funnel-mapping`, `PUT /config/thresholds`, `PUT /config/channel-coverage` — plus the bundle read `GET /config/status` (used transitively). Also the version-history read `GET /config/funnel-mapping/history` for the History drawer.
- **UI-PRD-01 (Soft Maximalism):** design tokens, shadcn primitives (`<Table>`, `<Select>`, `<Input>`, `<Checkbox>`, `<Sheet>` for history drawer). No new primitives.
- **Feature Flags (FF-PRD-03):** `useFeatureFlag('performance_configuration_tab')` gates the tab. Each editor sits behind an inner flag (`performance_config_funnel_mapping`, `performance_config_thresholds`, `performance_config_channel_coverage`) per the implementation plan's "ship Funnel Mapping first" staging.
- **Integrations (IN-PRD-03):** pre-wizard, the CTA area links to `/settings/integrations` when `connected_integrations` is empty. The Configuration tab does not call Integrations directly — SAR-E's `/config/status` returns the connection summary.
- **Project Tasks (PR-PRD-03):** Calendar page owns exogenous-event editing. Configuration does not link to it from a dedicated button in v1; users find Calendar via the main nav. If UX testing shows poor discovery, revisit.
- **Existing files to study:**
  - `docs/figma-export/src/app/components/performance/ConfigurationSection.tsx` — reference UX, rebuild against Soft Maximalism
  - `docs/figma-export/src/app/components/performance/FunnelMappingEditor.tsx` — reference mapping table
  - `frontend/src/pages/Performance/*` (pre-rename state) — existing Figma stubs to replace
  - `frontend/src/components/performance/**` — tree this PRD's new components join

## 4. Data contract

### 4.1 Consumed from the Performance API (PE-PRD-01 shape)

```typescript
import type { Brand } from '@/types/brand';

export type EffectivenessKPIId = Brand<string, 'EffectivenessKPIId'>;
export type FunnelObjective =
  | 'Problem Awareness'
  | 'Brand Awareness'
  | 'Consideration'
  | 'Conversion';

export interface EffectivenessKPI {
  kpi_id: EffectivenessKPIId;
  display_name: string;
  unit: 'count' | 'currency' | 'percent' | 'duration_seconds';
  typical_direction: 'up_is_good' | 'down_is_good' | 'neutral';
  aggregation: 'sum' | 'mean' | 'weighted_mean';
  is_active: boolean;
}

export interface FunnelStageMapping {
  mappings: Record<FunnelObjective, EffectivenessKPIId>;    // exactly 4 entries
  version: number;
  updated_at: string;      // ISO datetime
  updated_by: string;
}

export interface FunnelMappingHistoryEntry {
  version: number;
  mappings: Record<FunnelObjective, EffectivenessKPIId>;
  updated_at: string;
  updated_by: string;
  diff_summary: string;    // e.g., "Consideration: kpi_abc → kpi_def"
}

export interface Threshold {
  kpi_id: EffectivenessKPIId;
  warn_low: number | null;
  warn_high: number | null;
  critical_low: number | null;
  critical_high: number | null;
}

export interface ChannelCoveragePoint {
  channel: string;
  week_start: string;      // ISO date
  has_data: boolean;
}

export interface ChannelCoverageMatrix {
  matrix: ChannelCoveragePoint[];
  updated_at: string;
}

export interface PlatformConnectionSummary {
  platform_id: string;
  connection_id: string;
  status: 'connected' | 'expired' | 'revoked' | 'error';
  external_account_label: string | null;
}

// Bundle returned by GET /api/v1/performance/{account_id}/configuration
export interface ConfigurationBundle {
  forecasting_enabled: boolean;
  setup_wizard_completed: boolean;
  funnel_mapping: FunnelStageMapping | null;
  thresholds: Threshold[] | null;
  channel_coverage: ChannelCoverageMatrix | null;
  available_kpis: EffectivenessKPI[] | null;

  // Always populated (drives both Configuration and the wizard)
  available_kpi_sources: AvailableKPISource[];
  connected_integrations: PlatformConnectionSummary[];

  // Pre-wizard: null when no draft; populated when draft exists
  wizard_draft: PerformanceWizardDraftSummary | null;
}

export interface PerformanceWizardDraftSummary {
  current_step: 'welcome' | 'define_kpis' | 'backfill_depth' | 'review';
  updated_at: string;
}

export interface AvailableKPISource {
  source_job_id: string;
  display_name: string;
  platform_id: string;
  unit_suggestion: 'count' | 'currency' | 'percent' | 'duration_seconds';
}
```

The `wizard_draft` field is populated if a draft Firestore doc exists at `accounts/{account_id}/performance_wizard_draft` (ownership: PE-PRD-05). Configuration consumes it to render the resume banner; the actual draft schema belongs to PE-PRD-05.

### 4.2 Client-side derived types

```typescript
export type ConfigurationMode = 'pre_wizard' | 'post_wizard';

export interface FunnelMappingFormState {
  mappings: Record<FunnelObjective, EffectivenessKPIId | null>;
  dirty: boolean;
  errors: Partial<Record<FunnelObjective, string>>;   // per-row error (e.g., duplicate)
}

export type EditorSaveStatus =
  | { kind: 'idle' }
  | { kind: 'saving' }
  | { kind: 'saved'; at: string }
  | { kind: 'error'; message: string };
```

Brand types per CLAUDE.md C-5.

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `frontend/src/pages/Performance/ConfigurationTab.tsx` — page shell, mode switch (pre-wizard / post-wizard) |
| Create | `frontend/src/components/performance/config/PreWizardEmptyState.tsx` — CTA + integration-check + resume banner |
| Create | `frontend/src/components/performance/config/FunnelStageMappingEditor.tsx` — **exported for wizard reuse (PE-PRD-05)** |
| Create | `frontend/src/components/performance/config/FunnelMappingHistoryDrawer.tsx` — `<Sheet>` reading mapping history |
| Create | `frontend/src/components/performance/config/ThresholdsEditor.tsx` — per-KPI bounds table |
| Create | `frontend/src/components/performance/config/ChannelCoverageEditor.tsx` — matrix view with week scroll |
| Create | `frontend/src/components/performance/config/ResumeSetupBanner.tsx` — variant shown when `wizard_draft !== null` |
| Create | `frontend/src/hooks/useConfiguration.ts` — TanStack Query hook; 60-second stale time |
| Create | `frontend/src/hooks/useFunnelMappingMutation.ts` |
| Create | `frontend/src/hooks/useThresholdsMutation.ts` |
| Create | `frontend/src/hooks/useChannelCoverageMutation.ts` |
| Create | `frontend/src/hooks/useFunnelMappingHistory.ts` |
| Create | `frontend/src/services/performanceConfigApi.ts` — axios wrappers for the `PUT /sar-e/config/*` endpoints + history read |
| Create | `frontend/src/types/performance/configuration.ts` — branded types + form state + `ConfigurationMode` |
| Create | `frontend/src/pages/Performance/__tests__/ConfigurationTab.test.tsx` |
| Create | `frontend/src/components/performance/config/__tests__/FunnelStageMappingEditor.test.tsx` |
| Create | `frontend/src/components/performance/config/__tests__/ThresholdsEditor.test.tsx` |
| Create | `frontend/src/components/performance/config/__tests__/ChannelCoverageEditor.test.tsx` |
| Create | `frontend/src/components/performance/config/__tests__/PreWizardEmptyState.test.tsx` |
| Create | `frontend/src/hooks/__tests__/useFunnelMappingMutation.test.ts` |
| Create | `frontend/e2e/performance-config-pre-and-post-wizard.spec.ts` (Playwright) |

### 5.1 Pre-wizard mode

Rendered when `configuration.forecasting_enabled === false`.

**Default state (no connected integrations, no draft):**
- Headline + subhead explaining what forecasting does
- Outlined card listing the four stages of setup (connect → define KPIs → backfill → review)
- Primary CTA: "Connect an integration" → navigates to `/settings/integrations` (IN-PRD-03)
- Secondary helper copy: "You'll need at least one integration connected to start."

**Default state (connected integrations, no draft):**
- Same headline / subhead
- Primary CTA: "Set up forecasting" → navigates to `/performance/setup` (PE-PRD-05)
- Secondary text: enumerate connected integrations as chips (`external_account_label` from each `PlatformConnectionSummary`)

**Resume state (`wizard_draft !== null`):**
- `<ResumeSetupBanner>` at the top — yellow accent color
- Copy: "You started setup on [date]. Want to pick up where you left off?"
- Primary CTA: "Resume setup" → navigates to `/performance/setup?resume=true` (PE-PRD-05 handles the query flag)
- Secondary action: "Start over" — calls `DELETE /sar-e/{account_id}/config/wizard-draft` (PE-PRD-05 owns this endpoint; Configuration just invokes it and refetches the bundle)

No force-route on resume per implementation-plan §10 resolved decision 6.

### 5.2 Post-wizard mode

Rendered when `configuration.forecasting_enabled === true`.

Three sections stacked vertically, each an independent subcomponent with its own save / dirty / error states:

1. `<FunnelStageMappingEditor mapping={...} availableKpis={...} onSave={...} showHistory />` — 4-row table with `<Select>` per row. Uniqueness validator runs on change (per-row error surfaces inline). Save button disabled until `dirty && errors is empty`. "History" button opens `<FunnelMappingHistoryDrawer>`. Pre-save warning: "Changing the mapping will refresh Analysis charts and invalidate cached views."
2. `<ThresholdsEditor thresholds={...} availableKpis={...} onSave={...} />` — one row per KPI with four number inputs (warn_low, warn_high, critical_low, critical_high). Validation: critical_low ≤ warn_low ≤ warn_high ≤ critical_high (allowing nulls to break the chain). Save button per-row or a single "Save all changes" at the bottom.
3. `<ChannelCoverageEditor matrix={...} onSave={...} />` — rows = channels (from the matrix), columns = weeks (default 26 most recent), checkboxes = `has_data`. Horizontal scroll for earlier weeks. "Select all" / "Clear all" per row. Save persists the entire matrix (SAR-E replaces atomically).

### 5.3 `<FunnelStageMappingEditor />` reuse contract (for PE-PRD-05)

```typescript
export interface FunnelStageMappingEditorProps {
  mapping: Record<FunnelObjective, EffectivenessKPIId | null>;
  availableKpis: EffectivenessKPI[];
  onMappingChange: (mapping: Record<FunnelObjective, EffectivenessKPIId | null>) => void;
  onSave?: () => Promise<void>;           // omitted in wizard; save handled by parent
  showHistory?: boolean;                  // false in wizard
  showSaveButton?: boolean;               // false in wizard (Next handles persistence)
  validateOnChange?: boolean;             // true always
  dirty?: boolean;
  errors?: Partial<Record<FunnelObjective, string>>;
}
```

The component is a controlled editor — parent owns the form state. In the Configuration tab, the parent is `ConfigurationTab` which owns `useFunnelMappingMutation`. In the wizard (PE-PRD-05), the parent is the wizard's Step 2 which owns draft-save logic. Both callers pass the same `availableKpis` from the Configuration bundle.

Uniqueness validation is the component's responsibility: on mapping change, compute `Object.values(mapping).filter(Boolean)` → reject if length !== new Set(...).size; set the duplicate row's `errors[objective]` to "This KPI is already mapped to [Other Objective]."

### 5.4 Editor mutation patterns

All three editor mutations share a pattern:

1. Optimistic update to TanStack Query cache on dispatch
2. `PUT /sar-e/{account_id}/config/...` with the full new value (SAR-E replaces atomically; no PATCH semantics)
3. On success: invalidate `/performance/{account_id}/configuration`; transition editor state to `{ kind: 'saved', at: now }`; toast
4. On failure: rollback optimistic update; transition to `{ kind: 'error', message }`; toast with retry affordance; log Weave span `performance.config.save_error`

The funnel-mapping save additionally invalidates `/performance/{account_id}/analysis` and `/performance/{account_id}/simulations` so trendlines + chart overlays re-render against the new mapping (implementation-plan §9 risk: "Stale Funnel Mapping skews every chart").

### 5.5 Feature-flag staging

Each editor is gated by an inner flag per the implementation plan. Default rollout:

- `performance_config_funnel_mapping`: true (ships first)
- `performance_config_thresholds`: false → true (ships after Funnel Mapping proves stable)
- `performance_config_channel_coverage`: false → true (ships last)

When an inner flag is false, the corresponding section renders a "Coming soon" card.

## 6. API contract (consumed)

| Method | Path | Purpose | Owner |
|---|---|---|---|
| `GET` | `/api/v1/performance/{account_id}/configuration` | Bundle for page load (both modes) | PE-PRD-01 |
| `PUT` | `/api/v1/sar-e/{account_id}/config/funnel-mapping` | Replace Funnel Mapping | SE-PRD-01 |
| `GET` | `/api/v1/sar-e/{account_id}/config/funnel-mapping/history` | Version history for the History drawer | SE-PRD-01 |
| `PUT` | `/api/v1/sar-e/{account_id}/config/thresholds` | Replace thresholds | SE-PRD-01 |
| `PUT` | `/api/v1/sar-e/{account_id}/config/channel-coverage` | Replace channel coverage matrix | SE-PRD-01 |
| `DELETE` | `/api/v1/sar-e/{account_id}/config/wizard-draft` | "Start over" from the Resume banner | PE-PRD-05 |

No endpoints owned by this PRD. Configuration is a pure-frontend project consuming SE-PRD-01's config surface and PE-PRD-01's bundle.

## 7. Acceptance criteria

1. On an account with `forecasting_enabled=false` and no connected integrations, the Configuration tab renders with an "Connect an integration" CTA linking to `/settings/integrations`. The other four Performance tabs are hidden from the nav.
2. On an account with `forecasting_enabled=false`, `connected_integrations` non-empty, and no wizard draft, the Configuration tab renders a "Set up forecasting" CTA linking to `/performance/setup`. Connected-integration chips enumerate `external_account_label`s.
3. On an account with `forecasting_enabled=false` and a wizard draft present, the Configuration tab renders the `<ResumeSetupBanner>` at the top with a "Resume setup" CTA that navigates to `/performance/setup?resume=true`, plus a "Start over" action that calls `DELETE /sar-e/{account_id}/config/wizard-draft` and refetches the bundle.
4. On an account with `forecasting_enabled=true`, the Configuration tab renders three editor sections (Funnel Stage Mapping, Thresholds, Channel Coverage). No CLV editor. No Exogenous Events section.
5. Funnel Stage Mapping editor renders 4 rows with KPI dropdowns; selecting a KPI already used by another Objective surfaces an inline error on the duplicate row and disables Save.
6. Saving a valid Funnel Mapping fires `PUT /sar-e/{account_id}/config/funnel-mapping` with the full mapping; on success the `useConfiguration`, `useAnalysis`, and `useSimulations` caches invalidate; a toast appears.
7. Funnel Mapping History drawer opens on click; renders rows from `GET /sar-e/{account_id}/config/funnel-mapping/history` with `diff_summary` per row.
8. Pre-save warning appears on the Funnel Mapping editor when the mapping is dirty: "Changing the mapping will refresh Analysis charts and invalidate cached views."
9. Thresholds editor enforces the inequality `critical_low ≤ warn_low ≤ warn_high ≤ critical_high` (nulls permitted); save fires `PUT /sar-e/{account_id}/config/thresholds`.
10. Channel Coverage editor renders rows × 26-week columns with `has_data` checkboxes; horizontal scroll reveals earlier weeks; save fires `PUT /sar-e/{account_id}/config/channel-coverage` with the complete matrix.
11. Optimistic-update rollback: a 5xx response from any editor save rolls back the visible state to its pre-save values and shows an error toast with a retry affordance.
12. Viewer-role users can see all three editors but all inputs are disabled with tooltips ("Ask an editor to change settings").
13. Feature-flag gating: with `performance_config_thresholds=false`, the Thresholds section renders a "Coming soon" card instead of the editor; Funnel Mapping and Channel Coverage continue to render normally.
14. The exported `<FunnelStageMappingEditor />` component accepts the props described in §5.3 and is importable from `frontend/src/components/performance/config/FunnelStageMappingEditor.tsx` — verified by a compile-time import in PE-PRD-05's Step 2 test.
15. Cross-account navigation redirects to `/accounts` with a toast.
16. Unit + Playwright tests pass; `npm run build`, `npm run typecheck`, `npm run format.fix`, `npm run lint` all clean.

## 8. Test plan

**Unit tests — page shell** (`ConfigurationTab.test.tsx`):
- Renders pre-wizard empty state when `forecasting_enabled=false`, no integrations, no draft
- Renders pre-wizard "Set up forecasting" CTA when integrations connected, no draft
- Renders `<ResumeSetupBanner>` when draft exists
- Renders three editor sections when `forecasting_enabled=true`
- Hides CLV and ExogenousEvents sections unconditionally (snapshot asserts absence of matching test-ids)

**Unit tests — Funnel Mapping editor** (`FunnelStageMappingEditor.test.tsx`):
- Controlled behavior: passing a `mapping` prop drives the select values; `onMappingChange` fires on select change
- Uniqueness validator: selecting a KPI already used elsewhere surfaces the expected error string; Save disabled while errors exist
- Uniqueness validator: swapping two Objectives' KPIs in one gesture clears both errors
- Wizard mode (`showSaveButton=false`, `showHistory=false`): editor renders without the Save button or History affordance
- Historic version rendering: passing `mapping` where a KPI id no longer exists in `availableKpis` shows "Unknown KPI (id)" + a warning

**Unit tests — Thresholds editor** (`ThresholdsEditor.test.tsx`):
- Inequality validator with all combinations of nulls
- Per-row save: only the dirty row's values are sent in the PUT payload (reconstructed from the full array)
- Unit labels match `EffectivenessKPI.unit` (currency → `$`, percent → `%`, etc.)

**Unit tests — Channel Coverage editor** (`ChannelCoverageEditor.test.tsx`):
- Renders N channel rows × 26 week columns by default
- Horizontal scroll reveals earlier weeks; "Select all" / "Clear all" per row works
- Save sends the full matrix; partial edits still send the complete array (SAR-E replaces atomically)

**Unit tests — pre-wizard empty state** (`PreWizardEmptyState.test.tsx`):
- No integrations: "Connect an integration" CTA + `/settings/integrations` link
- Integrations connected, no draft: "Set up forecasting" CTA + `/performance/setup` link
- Draft exists: `<ResumeSetupBanner>` rendered with correct copy

**Unit tests — hooks:**
- `useConfiguration`: 60-second stale time; returns bundle shape
- `useFunnelMappingMutation`: optimistic update; rollback on 5xx; cache invalidation cascade (configuration + analysis + simulations)
- `useThresholdsMutation` / `useChannelCoverageMutation`: optimistic update; rollback on 5xx

**Playwright** (`performance-config-pre-and-post-wizard.spec.ts`):
- Seed a new account with no integrations → navigate to `/performance` → auto-routes to `/performance/configuration` → "Connect an integration" CTA visible, other tabs hidden
- Seed an account with a wizard draft → verify `<ResumeSetupBanner>` renders → click "Resume setup" → verify URL is `/performance/setup?resume=true`
- Seed an account post-wizard → verify three editor sections render → edit Funnel Mapping → save → verify `PUT /config/funnel-mapping` fires with the full mapping → reload → verify persistence → verify `/performance/analysis` reflects the new mapping

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| Funnel Mapping save invalidates analytical caches; user perceives Analysis / Simulations as "broken" for a moment | Pre-save warning surfaces the intent; a small "Refreshing charts" spinner appears on Analysis / Simulations for <2s post-save. Covered by Playwright. |
| Feature-flag staging leaves users seeing "Coming soon" cards | Product-approved copy; shipping all three editors behind a single flag is an option if staging isn't wanted. Deferred to product review at kickoff. |
| `<FunnelStageMappingEditor />` reuse in the wizard introduces a props-shape drift | Contract is a typed React interface; TypeScript catches drift at compile time. PE-PRD-05's Step 2 tests import and render the component. |
| Channel Coverage editor matrix grows unwieldy for accounts with 10+ channels × 104 weeks | Default window is 26 weeks; scroll reveals earlier weeks. Row pagination deferred; revisit if usage data shows large matrices. |
| Viewer-role fallback on editor inputs — silent disablement confuses users | Tooltip on every disabled input + a banner at the top of the tab ("Read-only mode — ask an editor to change settings"). Covered by accessibility audit in PE-PRD-08. |
| All SAR-E contract calls are contract-tested against SAR-E's OpenAPI on CI | `api/tests/contract/test_sar_e_openapi.py` asserts every endpoint this tab calls matches the published schema; drift fails the build. |
| Resume banner's "Start over" action is destructive | Confirmation dialog before the DELETE fires; copy: "You'll lose the KPI selections and backfill choices from your draft." |
| Thresholds UI shows four per-KPI bounds × many KPIs → visually noisy | Collapse rows by default (show `display_name` + current bounds inline); expand on click. Confirmed with design at kickoff. |

### Open questions

1. **Should the pre-wizard Configuration tab show what the post-wizard tab will look like (ghosted editor previews)?** Could help set expectations. Cons: complicates the empty state, may mislead users who expect immediate configurability. Recommend no for v1; revisit if onboarding completion rates drop.
2. **Does editing the Funnel Mapping require an approval gate per DM-PRD-07?** SAR-E's audit applies, but the implementation plan doesn't require a separate approval workflow for config edits. Confirm with DM team at kickoff — if yes, the save button becomes "Request change" and the UX shifts.
3. **Does "Start over" from the Resume banner also revoke SAR-E's partial state?** If the wizard already triggered a backfill before the user abandoned, we may have KPI rows in SAR-E. SE-PRD-01's `DELETE /config/wizard-draft` semantics need clarification — does it cascade to kpi seeding? Confirm with SAR-E team at kickoff.
4. **Where does a user go to add a new KPI post-wizard?** v1 answer: nowhere — no Configuration surface. Power users can call the SAR-E API directly. Revisit after first release feedback.

### Resolved

- **CLV editor descoped.** Resolved 2026-04-23 per implementation-plan §8.
- **ExogenousEventsSection moved to Calendar.** Resolved 2026-04-23 per implementation-plan §8; no Configuration link in v1.
- **`<FunnelStageMappingEditor />` exported as a standalone, reusable component.** Resolved 2026-04-23 — PE-PRD-05 imports it directly; the wizard does not re-implement the primitive.

## 10. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md)
- Foundation: [PE-PRD-01 — page shell](./PE-PRD-01-page-shell-and-routing.md) (TBD path — align once PE-PRD-01 file is authored)
- Sibling: [PE-PRD-05 Setup Wizard](./PE-PRD-05-setup-wizard.md) (reuses `<FunnelStageMappingEditor />`)
- Upstream: [SE-PRD-01 Configuration foundation + setup state](../../sar-e/projects/SE-PRD-01-configuration-foundation.md)
- Related: [IN-PRD-03 Connection-management UI](../../integrations/projects/IN-PRD-03-connection-management-ui.md) (CTA link target)
- Related: [PR-PRD-03 Calendar](../../project-tasks/projects/PR-PRD-03-calendar-page-frontend.md) (new home for ExogenousEvents editing)
- Figma reference: `docs/figma-export/src/app/components/performance/ConfigurationSection.tsx`
- Design tokens: [UI-PRD-01](../../ui/projects/UI-PRD-01-design-system-foundation.md)
- CLAUDE.md rules in scope: C-1 (TDD), C-2 (domain vocabulary — Objective / Effectiveness KPI / Threshold), C-5 (branded IDs), C-6 (`import type`), C-8 (`type` default, `interface` for merging/readability), C-9 (no premature extraction except for the reused `<FunnelStageMappingEditor />`); T-2 (colocated `*.test.tsx`), T-3 (API integration tests), T-5 (prefer integration tests over heavy mocking), T-8 (assert the full structure); G-2 (`npm run format.fix`), G-3 (`npm run typecheck`)
