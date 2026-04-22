# UI-PRD-05 — Knowledge / Strategy Section

**Status:** Blocked on UI-PRD-01
**Owner team:** Frontend
**Blocked by:** UI-PRD-01
**Parallel with:** UI-PRD-04, UI-PRD-06, UI-PRD-07
**Estimated effort:** 10–14 days (largest UI-PRD — consider splitting if team capacity is constrained)

---

## 1. Context

The Knowledge section is KEN-E's surface for exploring everything it knows about an account's brand, products, customers, competitors, strategy, and marketing. Today it has seven sub-pages under `/knowledge/*` built on the old design system. The Figma redesign both re-skins existing pages and adds new ones (Journey, Marketing, Brand, KnowledgeGraph). Knowledge Graph (KG-PRD-*) lands its data wiring in Release 3; this PRD ships the shell so the backend work builds on the new design.

**Scope boundary:** this PRD owns routes, page shells, shared section components (content cards, section headers, charts, tables), and mocked data rendering. Data wiring for the redesigned pages is owned by `KG-PRD-03` (read tools) and the existing strategy-document endpoints (preserved as-is where no backend change is planned).

## 2. Scope

### In scope
- Redesign `Knowledge.tsx` (index / landing)
- Redesign existing pages: `KnowledgeAccount`, `KnowledgeBrand`, `KnowledgeCompetitors`, `KnowledgeCustomers`, `KnowledgeMetrics`, `KnowledgeStrategy`, `KnowledgeActivities`, `Products`, `Customers`, `Insights`
- Add new pages from Figma: `JourneyPage`, `MarketingPage`, `KnowledgeGraphPage`
- `LayoutC`-composed section with a left sub-nav for the Knowledge topics
- Shared section components: `SectionHeader`, `ContentCard`, `MetricTile`, `InsightList`, `EntityTable` (names may differ after reviewing Figma)
- Route migration in `App.tsx`; preserve backward-compat redirects where existing URLs are in use
- Sidebar nav entry for Knowledge (top-level) with sub-routes surfaced via the section's left nav
- Component tests for new page shells and shared section components

### Out of scope
- Data wiring to `KG-PRD-03` read tools (`load_context_section`, `load_document`, `search_kb`, `list_observations`) — that wiring is KG-PRD-03's
- Changes to Neo4j queries or any knowledge-graph backend
- Changes to existing strategy-document endpoints
- `AnalysisReport` page — defer to a follow-up unless design parity is trivial

## 3. Dependencies

- **UI-PRD-01:** `LayoutC`, shadcn primitives (Card, Table, Chart, Tabs, Accordion, Badge, Progress)
- **Downstream consumer:** [`KG-PRD-03`](../../knowledge-graph/projects/KG-PRD-03-orchestrator-read-tools.md) — ADK read tools back the redesigned pages' dynamic content
- **Existing files to study:**
  - `frontend/src/pages/Knowledge.tsx`, `Knowledge*.tsx`, `Customers.tsx`, `Products.tsx`, `Insights.tsx`
  - `frontend/src/components/knowledge-graph/*`, `frontend/src/components/knowledge-base/*`
- **Figma nodes:** StrategyIndex, AccountDetailsPage, BrandPage, CompetitorsPage, CustomersPage, InsightsPage, JourneyPage, MarketingPage, MetricsPage, ProductsPage, KnowledgeGraphPage

## 4. Data contract (TypeScript)

This PRD defines mock shapes for each page. Real wiring is owned by KG-PRD-03 and existing strategy endpoints; component props accept a generic `data` prop so the mock-to-real swap doesn't require rewriting components.

No new branded types beyond what already exists in `frontend/src/types/`.

## 5. Implementation outline

| Action | File |
|--------|------|
| Modify | `frontend/src/pages/Knowledge.tsx` — new index page |
| Modify | `frontend/src/pages/KnowledgeAccount.tsx`, `KnowledgeBrand.tsx`, `KnowledgeCompetitors.tsx`, `KnowledgeCustomers.tsx`, `KnowledgeMetrics.tsx`, `KnowledgeStrategy.tsx`, `KnowledgeActivities.tsx` |
| Modify | `frontend/src/pages/Products.tsx`, `Customers.tsx`, `Insights.tsx` |
| Create | `frontend/src/pages/knowledge/JourneyPage.tsx` |
| Create | `frontend/src/pages/knowledge/MarketingPage.tsx` |
| Create | `frontend/src/pages/knowledge/KnowledgeGraphPage.tsx` |
| Create | `frontend/src/pages/knowledge/KnowledgeLayout.tsx` — left sub-nav + content area (wraps `LayoutC`) |
| Create | `frontend/src/components/knowledge/SectionHeader.tsx` |
| Create | `frontend/src/components/knowledge/ContentCard.tsx` |
| Create | `frontend/src/components/knowledge/MetricTile.tsx` |
| Create | `frontend/src/components/knowledge/InsightList.tsx` |
| Create | `frontend/src/components/knowledge/EntityTable.tsx` |
| Modify | `frontend/src/App.tsx` — route registration for new pages; preserve existing redirects |
| Modify | `frontend/src/components/layout/Sidebar.tsx` — Knowledge entry |
| Create | colocated `*.test.tsx` for each new component |

### Page structure

All Knowledge pages compose inside `KnowledgeLayout`, which renders a left sub-nav listing the section's topics (Strategy, Account, Brand, Products, Customers, Competitors, Journey, Marketing, Metrics, Insights, Knowledge Graph) and a content area. The sub-nav's active entry syncs with the current route.

### Knowledge Graph page

Renders a graph visualization placeholder in this PRD. KG-PRD-03 may swap in a real graph component (d3 / cytoscape / sigma). Component prop signature should accept nodes + edges arrays so the swap is trivial.

### Splitting strategy (if team capacity is limited)

If this PRD is too large to ship in a single cycle, split into:
- **UI-PRD-05a:** shared layout + shared components + index page (4–5 days)
- **UI-PRD-05b:** existing-page redesigns (5–6 days)
- **UI-PRD-05c:** new pages (Journey, Marketing, KnowledgeGraph) (3–4 days)

Note the split in `PROJECT-PLANNER.md` if adopted.

## 6. API contract

N/A — this PRD consumes no new APIs. Existing strategy endpoints remain consumed by the migrated pages. KG-PRD-03 later adds read-tool backing for dynamic content.

## 7. Acceptance criteria

1. Sidebar has a Knowledge entry; clicking it navigates to `/knowledge` (index).
2. `KnowledgeLayout` renders a left sub-nav with every topic; clicking an entry navigates to the correct sub-route.
3. Every existing `/knowledge/*` route renders its redesigned page without regressing existing data display.
4. New routes `/knowledge/journey`, `/knowledge/marketing`, `/knowledge/graph` render their pages with mocked data.
5. Shared section components (`SectionHeader`, `ContentCard`, `MetricTile`, etc.) are used consistently across all pages.
6. Backward-compat redirects preserved (none removed in this PRD).
7. Dark mode renders correctly on every page.
8. Component tests pass; `npm run typecheck`, `npm run format.fix`, `npm run build`, `npm test` pass.

## 8. Test plan

**Component tests:**
- One `*.test.tsx` per page shell: renders with mocked data, sub-nav highlights correct entry
- `KnowledgeLayout.test.tsx`: left sub-nav, active-route highlighting, children render in content area
- Shared component tests: `SectionHeader`, `ContentCard`, `MetricTile`, `InsightList`, `EntityTable`

**Visual QA:**
- Screenshot diff each page against Figma at 1280 / 1440
- Dark mode pass on every page

**Regression guard:**
- Existing `Knowledge*.tsx` tests continue to pass after the redesign (update selectors as needed)

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| PRD is large; single dev can't finish in one release cycle | Split per §5 "Splitting strategy" |
| Existing pages' data-loading logic breaks under the redesign | Preserve logic as-is; only change presentation |
| Knowledge graph visualization is out of scope but page shell needs a placeholder that doesn't look broken | Use an illustrated empty state with "Graph coming soon" copy; swap via KG-PRD-03 |
| Mocked data drift for new pages | Use the Figma data as the source; flag to backend team what the read tools need to return |
| Sub-nav entries don't match final KG-PRD-03 content model | Prioritize Figma as the naming / grouping source; KG-PRD-03 can rename later if needed |

### Open questions

- **Q:** Should `/knowledge/insights` remain or merge into `/knowledge` (index)? → **Default:** keep separate — Figma lists both.
- **Q:** Does `AnalysisReport` get redesigned here or as a follow-up? → **Defer to follow-up** unless small enough to include mid-PRD.
- **Q:** Split or single PRD? → Team owner decides at kickoff based on capacity.

## 10. Reference

- Parent component: [`../README.md`](../README.md)
- Sibling: [`UI-PRD-01-design-system-foundation.md`](./UI-PRD-01-design-system-foundation.md)
- Downstream consumer: [`KG-PRD-03`](../../knowledge-graph/projects/KG-PRD-03-orchestrator-read-tools.md)
- Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) — StrategyIndex, AccountDetailsPage, BrandPage, CompetitorsPage, CustomersPage, InsightsPage, JourneyPage, MarketingPage, MetricsPage, ProductsPage, KnowledgeGraphPage
- CLAUDE.md rules in scope: C-5, C-6, C-8; T-2; G-2, G-3
