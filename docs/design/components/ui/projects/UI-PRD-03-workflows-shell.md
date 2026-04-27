# UI-PRD-03 — Workflows Shell + Tabs

**Status:** Blocked on UI-PRD-01
**Owner team:** Frontend
**Blocked by:** UI-PRD-01
**Parallel with:** UI-PRD-02, UI-PRD-04, UI-PRD-06
**Estimated effort:** 4–5 days

---

## 1. Context

Three Release-1-to-3 features — Agents (AH-PRD-02), Automations (A-PRD-05 / A-PRD-06), Skills (SK-PRD-03) — all live under a shared `/workflows` shell with tabbed navigation. Each of those backend-owning PRDs adds the data-wired tab content for its feature. This PRD lands the shell first so those PRDs build on the new design rather than re-skinning later. Without this, AH-PRD-02's Agents UI (Release 1) ships against the old style and we incur a re-skin.

**Scope boundary:** this PRD owns the `WorkflowsLayout` (tab container, active-tab URL sync), the three tab page shells (`AgentsPage`, `AutomationsPage`, `SkillsPage`) with skeleton or empty-state content, and the two detail-page shells (`AgentCreatePage`, `AutomationDetailsPage`) with mocked data. Data wiring is owned by AH-PRD-02, A-PRD-05/06, and SK-PRD-03 respectively.

## 2. Scope

### In scope
- New `/workflows` route group under `LayoutC`
- `WorkflowsLayout` — tab container (Agents / Automations / Skills) with URL-synced active tab
- `AgentsPage` shell at `/workflows/agents` — empty state + list skeleton
- `AutomationsPage` shell at `/workflows/automations` — empty state + list skeleton
- `SkillsPage` shell at `/workflows/skills` — empty state + list skeleton
- `AgentCreatePage` shell at `/workflows/agents/new` — form layout with mocked submit
- `AutomationDetailsPage` shell at `/workflows/automations/:planId` — header, tabs (Overview / Outputs), mocked data
- Sidebar nav entry pointing at `/workflows/agents` (default tab)
- Tab contract documented for downstream PRDs to consume
- Component tests for the shell, tab router, and empty states

### Out of scope
- Data wiring for the Agents tab — owned by AH-PRD-02
- Data wiring for the Automations tab and detail page — owned by A-PRD-05 / A-PRD-06
- Data wiring for the Skills tab — owned by SK-PRD-03
- Agent Builder controls (skills picker, sandbox toggle) — owned by SK-PRD-04
- React Flow DAG editor on the automation details page — owned by A-PRD-06

## 3. Dependencies

- **UI-PRD-01:** `LayoutC`, `Sidebar`, re-skinned shadcn primitives (Tabs, Card, Button, Input, Table)
- **Downstream consumers** (informational — they will consume the shell this PRD builds):
  - [`AH-PRD-02`](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) — Agents tab + AgentCreatePage data wiring
  - [`A-PRD-05`](../../automations/projects/A-PRD-05-automations-list-page.md) — Automations tab data wiring
  - [`A-PRD-06`](../../automations/projects/A-PRD-06-automation-details-page.md) — Automation details page data wiring
  - [`SK-PRD-03`](../../skills/projects/SK-PRD-03-authoring-ui.md) — Skills tab data wiring
- **Existing files to study:**
  - `frontend/src/App.tsx` — routing
  - `frontend/src/components/ui/tabs.tsx` (post-UI-PRD-01 re-skin)

## 4. Data contract (TypeScript)

```ts
// frontend/src/pages/workflows/WorkflowsLayout.tsx

export type WorkflowTab = "agents" | "automations" | "skills";

export type WorkflowsLayoutProps = {
  activeTab: WorkflowTab;
  children: React.ReactNode;
};
```

No server data contracts — tab pages receive mock data as props until their owning PRD ships.

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `frontend/src/pages/workflows/WorkflowsLayout.tsx` |
| Create | `frontend/src/pages/workflows/AgentsPage.tsx` — shell, empty state |
| Create | `frontend/src/pages/workflows/AutomationsPage.tsx` — shell, empty state |
| Create | `frontend/src/pages/workflows/SkillsPage.tsx` — shell, empty state |
| Create | `frontend/src/pages/workflows/AgentCreatePage.tsx` — form layout, mocked submit |
| Create | `frontend/src/pages/workflows/AutomationDetailsPage.tsx` — header + tabs, mocked data |
| Create | `frontend/src/pages/workflows/components/EmptyState.tsx` (shared across tabs if not already in UI-PRD-01) |
| Modify | `frontend/src/App.tsx` — add the five new routes under `LayoutC` |
| Modify | `frontend/src/components/layout/Sidebar.tsx` — add Workflows nav entry |
| Create | colocated `*.test.tsx` for `WorkflowsLayout`, each page shell, and the empty state |

### Tab contract (for downstream PRDs)

`WorkflowsLayout` exposes two contracts that AH-PRD-02, A-PRD-05/06, and SK-PRD-03 consume:

1. **URL-synced active tab:** visiting `/workflows/agents|automations|skills` sets `activeTab`. Tab clicks navigate rather than mutate local state.
2. **Tab slot:** children render in the content area. Each tab page is responsible for its own sub-layout (search bar, list, actions).

The contract is frozen at UI-PRD-03 merge. Downstream PRDs must not modify `WorkflowsLayout`; if a new tab is needed, add it here and version the contract.

### Empty-state copy (per Figma)

- Agents: "Assemble specialist agents tailored to your workflow." + primary CTA "Create an agent"
- Automations: "Schedule recurring work. Let KEN-E take it from here." + primary CTA "Create an automation"
- Skills: "Package your team's playbooks as reusable skills." + primary CTA "Create a skill"

## 6. API contract

N/A — this PRD consumes no APIs. Downstream PRDs wire their own endpoints.

## 7. Acceptance criteria

1. Sidebar has a Workflows entry; clicking it navigates to `/workflows/agents`.
2. `WorkflowsLayout` renders three tabs; clicking a tab updates the URL to `/workflows/{tab}`; deep-linking to `/workflows/skills` activates the Skills tab.
3. Each tab's empty-state copy and CTA match Figma.
4. `AgentCreatePage` renders the form layout with all input fields visible and disabled; "Submit" shows a mock success toast.
5. `AutomationDetailsPage` renders the header with title, status badge, and two sub-tabs (Overview / Outputs); Overview shows a mocked DAG placeholder; Outputs shows an empty-state.
6. All routes are wrapped in `LayoutC` with correct sidebar padding.
7. Dark mode renders correctly on every page.
8. Component tests pass; `npm run typecheck`, `npm run format.fix`, `npm run build`, `npm test` pass.

## 8. Test plan

**Component tests:**
- `WorkflowsLayout.test.tsx`: renders three tabs; active tab reflects URL; tab click navigates (assert `useNavigate` called)
- `AgentsPage.test.tsx` / `AutomationsPage.test.tsx` / `SkillsPage.test.tsx`: empty state renders with correct copy + CTA
- `AgentCreatePage.test.tsx`: all form fields render; mock submit fires
- `AutomationDetailsPage.test.tsx`: header renders with status badge; sub-tabs switch

**Manual smoke:**
- Navigate through tabs via sidebar, tab buttons, and direct URL; verify browser back / forward preserves state

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| Tab contract change needed mid-downstream-PRD | Freeze contract at merge; any change requires a follow-up PRD referenced by all consumers |
| AgentCreatePage form fields diverge from AH-PRD-02's final data model | Use Figma as the field list; AH-PRD-02 adjusts binding, not layout |
| Skeleton vs. mocked-data choice for list pages | Prefer empty states over fake rows — avoids misleading screenshots in downstream PRDs |
| Sidebar nav entry label | Match Figma exactly; flag to design if ambiguous |

### Open questions

- **Q:** Should the Workflows tab order match Figma exactly or prioritize feature readiness? → **Default:** match Figma (Agents → Automations → Skills). Re-order is cheap later.
- **Q:** Do AgentCreatePage / AutomationDetailsPage need URL query params now or later? → **Defer** to their owning PRDs (AH-PRD-02, A-PRD-06).

## 10. Reference

- Parent component: [`../README.md`](../README.md)
- Sibling: [`UI-PRD-01-design-system-foundation.md`](./UI-PRD-01-design-system-foundation.md)
- Downstream consumers: [`AH-PRD-02`](../../agentic-harness/projects/AH-PRD-02-agent-factory.md), [`A-PRD-05`](../../automations/projects/A-PRD-05-automations-list-page.md), [`A-PRD-06`](../../automations/projects/A-PRD-06-automation-details-page.md), [`SK-PRD-03`](../../skills/projects/SK-PRD-03-authoring-ui.md)
- Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) — AgentsPage, AutomationsPage, SkillsPage, AgentCreatePage, AutomationDetailsPage
- CLAUDE.md rules in scope: C-5, C-6, C-8; T-2; G-2, G-3
