# UI-PRD-07 — Performance Page

**Status:** Blocked on UI-PRD-01
**Owner team:** Frontend
**Blocked by:** UI-PRD-01
**Parallel with:** UI-PRD-02, UI-PRD-03, UI-PRD-04, UI-PRD-05, UI-PRD-06
**Estimated effort:** 3–4 days

---

## 1. Context

The existing Performance page (`frontend/src/pages/Performance.tsx`) displays marketing performance metrics and charts. Figma redesigns the page with new metric tiles, chart styling, and layout under `LayoutC`. No backend change is planned — the existing data loading and analytics endpoints are preserved. This PRD is placed last in the UI migration because it has no release dependency and can ship whenever team capacity allows.

**Scope boundary:** this PRD owns the page shell, metric tiles, chart styling, and layout. Data loading logic, analytics queries, and any GA/Ads integration calls are preserved as-is.

## 2. Scope

### In scope
- Redesign `Performance.tsx` onto `LayoutC`
- Metric tile row (KPIs) per Figma
- Chart styling updated to use Soft Maximalism tokens (via shadcn `chart.tsx` re-skin from UI-PRD-01)
- Filter bar (date range, account, channel — match Figma)
- Export / share actions preserved if present today
- Component tests for new sub-components

### Out of scope
- Changes to analytics data loading, APIs, or backend
- Changes to existing Recommendations, Campaigns, or Reports pages (separate surfaces)
- New metric definitions

## 3. Dependencies

- **UI-PRD-01:** `LayoutC`, shadcn `chart.tsx` re-skin, `Card`, `Badge`, `Select`
- **Existing files to study:**
  - `frontend/src/pages/Performance.tsx` — current implementation, data loading
  - `frontend/src/components/dashboard/*` — existing dashboard components
- **Figma nodes:** PerformancePage (+ any nested metric/chart components)

## 4. Data contract (TypeScript)

No new types. The existing performance data shapes are preserved — only the presentation layer changes.

## 5. Implementation outline

| Action | File |
|--------|------|
| Modify | `frontend/src/pages/Performance.tsx` — recompose page onto `LayoutC` with new Figma structure |
| Create | `frontend/src/components/performance/MetricTile.tsx` (if not shared with UI-PRD-05) |
| Create | `frontend/src/components/performance/PerformanceChart.tsx` — themed chart wrapper |
| Create | `frontend/src/components/performance/PerformanceFilterBar.tsx` |
| Modify | `frontend/src/components/layout/Sidebar.tsx` — preserve Performance entry; update icon if Figma changed it |
| Create | colocated `*.test.tsx` for each new component |

### Page structure

- **Filter bar (top):** date range, account, channel
- **Metric tile row:** 4–6 KPIs per Figma (values + deltas + sparklines)
- **Chart grid:** primary trend chart + supporting charts (per Figma)
- **Table (if present in Figma):** channel/campaign breakdown

### Chart theming

All charts consume the Soft Maximalism token palette via the shadcn `chart.tsx` primitive re-skinned in UI-PRD-01. No inline color values.

## 6. API contract

N/A — no new endpoints. Existing performance data loading is preserved.

## 7. Acceptance criteria

1. `/performance` renders the redesigned page inside `LayoutC`.
2. Metric tiles display current values + deltas + sparklines per Figma.
3. Filter bar updates chart data (existing logic preserved); selections persist in URL query params if the current implementation already does so.
4. Charts render using the new token palette; dark mode renders correctly.
5. No regression in data loading or analytics queries.
6. Component tests pass; `npm run typecheck`, `npm run format.fix`, `npm run build`, `npm test` pass.

## 8. Test plan

**Component tests:**
- `Performance.test.tsx`: updated from existing test; preserves data-loading coverage; updates selectors to new markup
- `MetricTile.test.tsx`: renders value / delta / sparkline; handles null values
- `PerformanceChart.test.tsx`: renders with token palette; respects dark-mode class
- `PerformanceFilterBar.test.tsx`: filter changes propagate

**Visual QA:**
- Screenshot diff against Figma at 1280 / 1440
- Dark mode pass

**Regression guard:**
- Existing data loading paths unchanged — verify network calls in DevTools match pre-redesign

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| Chart library color API conflicts with Soft Maximalism tokens | Encode palette via CSS variables consumed by the chart library's theme prop |
| Existing metric tile logic is spread across multiple components | Consolidate into a single `MetricTile` if the refactor is small; otherwise preserve current decomposition and re-skin in place |
| Date / account filter state lives in component state vs. URL | Preserve current behavior; refactor to URL state only if already consistent elsewhere |

### Open questions

- **Q:** Does Figma introduce any new KPI that requires backend change? → **Assumption:** no — scope is presentation-only. If a new KPI surfaces, defer to a follow-up PRD with backend ownership.

## 10. Reference

- Parent component: [`../README.md`](../README.md)
- Sibling: [`UI-PRD-01-design-system-foundation.md`](./UI-PRD-01-design-system-foundation.md)
- Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) — PerformancePage
- Existing files: `frontend/src/pages/Performance.tsx`, `frontend/src/components/dashboard/*`
- CLAUDE.md rules in scope: C-5, C-6, C-8; T-2; G-2, G-3
