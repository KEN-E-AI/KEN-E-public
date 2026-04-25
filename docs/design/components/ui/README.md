# UI (User Interface) — Product Requirements Document

> **Linear Team:** [KEN-E] UI
> **Last Updated:** 2026-04-20
> **Status:** Active

## 1. Overview

The UI component owns the end-user-facing surface of KEN-E — every page, layout, and global style in `frontend/` — and the in-progress migration of that surface to the "Soft Maximalism" design system authored in Figma ([KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism)). The migration replaces the current brand palette, typography, and layout primitives with a new token system (`theme.css` + `ThemeProvider`), ambient `BackgroundEffects`, two shell layouts (`LayoutC` for authenticated pages, `LayoutSettings` for settings), and a full redesign of every page in the application.

This component's work is organised as a **shell-first, pages-second** migration. UI-PRD-01 lands the design tokens and shared shell chrome (sidebar, top-nav, account switcher, notification bell, profile menu) — every subsequent project plugs into that shell. UI-PRD-02 through UI-PRD-07 each migrate one logical section of the application (auth + settings + chat, workflows, calendar, knowledge, extensions, performance). Sequencing matches the backend release plan so that each page's shell is ready before the backend component that owns its data wiring begins frontend work.

A developer reading only this section should understand: this component owns the global frontend shell, the `theme.css` token system, and the styling / shell for every top-level route. It **does not** own page-level data wiring for pages that already have a backend-owning PRD — those pages get their shell from UI projects and their data wiring from their home component (`agentic-harness`, `project-tasks`, `automations`, `knowledge-graph`, `skills`). The scope boundary is spelled out explicitly in §7 and restated at the top of every project PRD.

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Global shell (UI-PRD-01)                                                   │
│    ThemeProvider (light/dark)                                               │
│    BackgroundEffects (ambient)                                              │
│    LayoutC                    LayoutSettings                                │
│      ├── Sidebar                ├── Sidebar (compact)                       │
│      ├── TopNav                 └── Settings content area                   │
│      │     ├── AccountSwitcher                                              │
│      │     ├── NotificationBell                                             │
│      │     └── ProfileMenu                                                  │
│      └── Page content area                                                  │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼────────────────────────────┐
        │                           │                            │
        ▼                           ▼                            ▼
   UI-PRD-02                   UI-PRD-03                    UI-PRD-04
   Core Shell Pages            Workflows Shell              Calendar
   ├── /auth/*                 /workflows/                  /calendar
   ├── /settings/organization    ├── /agents                   ├── calendar view
   ├── /settings/account         ├── /automations              ├── list view
   ├── /settings/user            └── /skills                   └── detail panel
   └── /chat (= /)

        ▼                           ▼                            ▼
   UI-PRD-05                   UI-PRD-06                    UI-PRD-07
   Knowledge/Strategy          Extensions                   Performance
   /knowledge/*                /extensions/*                /performance

   Standalone (no shell) — between auth and the app
   ─────────────────────────────────────────────
   UI-PRD-08 · Organization Selection · /select-organization
```

### 2.1 Key Directories

| Path | Purpose |
|------|---------|
| `frontend/src/index.css` | Global token definitions — the Soft Maximalism palette, typography, radii, and dark-mode overrides land here (UI-PRD-01). |
| `frontend/src/App.css` | Kept minimal. Guard against reintroducing Vite-template styles that break the shell layout. |
| `frontend/tailwind.config.ts` | Tailwind theme extension — token wiring. Updated by UI-PRD-01. |
| `frontend/src/components/ui/` | shadcn/ui primitives (~50 components). UI-PRD-01 reviews and re-skins each primitive to match Figma; subsequent UI-PRDs consume them. |
| `frontend/src/components/layout/` | Shell layouts (`LayoutC`, `LayoutSettings`) and global chrome (`Sidebar`, `TopNav`, `AccountSwitcher`, `NotificationBell`, `ProfileMenu`, `SessionsSidebar`, `QuickStartGuide`). Created/expanded by UI-PRD-01. |
| `frontend/src/pages/` | Page components, one per route. Each UI-PRD creates or migrates a subset here. |
| `frontend/src/components/theme/` | `ThemeProvider`, `BackgroundEffects`, `ThemeToggle`. Created by UI-PRD-01. |
| `frontend/src/contexts/` | React contexts (Auth, Chat, Account). Consumed by pages; no new contexts owned by this component. |
| `frontend/src/App.tsx` | Routing configuration. Each UI-PRD adds or renames its routes here. |

### 2.2 Data Flow

The UI component consumes APIs; it does not own any. Data flow:

1. A user hits a route. React Router mounts the page.
2. The page reads `useAuth()` for the current user/organization/account and calls one or more backend APIs via the shared axios client (`frontend/src/lib/api.ts`, Firebase token injected).
3. Pages use TanStack Query for server state and React contexts for cross-component client state.
4. Data wiring (query hooks, service modules, branded-type transformers) for pages owned by another component lives in that component's PRD, not here.

### 2.3 API Contracts

The UI component does not own any API endpoints. It consumes:

| API | Owning component | Consumed by |
|-----|------------------|-------------|
| `/api/v1/auth/*`, Firebase Auth | Existing auth / firebase | UI-PRD-02 (auth pages) |
| `/api/v1/accounts/{account_id}/...` (settings, organization, user) | Existing settings | UI-PRD-02 |
| `/api/v1/chat` | `agentic-harness` | UI-PRD-02 (chat page) |
| `/api/v1/accounts/{account_id}/agent-configs/*` | `agentic-harness` (AH-PRD-02) | UI-PRD-03 (workflows shell; Agents tab data wiring is AH-PRD-02's) |
| `/api/v1/plans/*` | `project-tasks` (PR-PRD-01) | UI-PRD-04 (calendar; data wiring is PR-PRD-03's) |
| `/api/v1/accounts/{account_id}/automations/*` | `automations` (A-PRD-01) | UI-PRD-03 workflows shell (Automations tab data wiring is A-PRD-05/06's) |
| `/api/v1/accounts/{account_id}/skills/*` | `skills` (SK-PRD-01) | UI-PRD-03 workflows shell (Skills tab data wiring is SK-PRD-03's) |
| Knowledge-graph read APIs | `knowledge-graph` (KG-PRD-03) | UI-PRD-05 |

### 2.4 Key Abstractions

| Abstraction | Path | Purpose |
|-------------|------|---------|
| `ThemeProvider` | `frontend/src/components/theme/ThemeProvider.tsx` | Wraps the app, reads `localStorage`, exposes light/dark toggle via a hook. Created by UI-PRD-01. |
| `BackgroundEffects` | `frontend/src/components/theme/BackgroundEffects.tsx` | Ambient background ornamentation per Figma. Mounted once at app root. (UI-PRD-01) |
| `LayoutC` | `frontend/src/components/layout/LayoutC.tsx` | Authenticated-app layout — sidebar + top-nav + page content. Every authenticated page composes inside it. (UI-PRD-01) |
| `LayoutSettings` | `frontend/src/components/layout/LayoutSettings.tsx` | Settings-specific layout — narrower content area, secondary left nav for settings sub-sections. (UI-PRD-01) |
| `Sidebar` | `frontend/src/components/layout/Sidebar.tsx` | Primary left navigation. Surfaces routes from every UI-PRD; each project adds its nav entry here. |
| `AccountSwitcher` | `frontend/src/components/layout/AccountSwitcher.tsx` | Multi-tenant account/organization switcher. Reads from `useAuth()`. (UI-PRD-01) |
| `NotificationBell` | `frontend/src/components/layout/NotificationBell.tsx` | Top-nav notification center. Existing `NotificationSidebar` plugs in behind it. (UI-PRD-01) |
| `cn()` utility | `frontend/src/lib/utils.ts` | Existing `clsx` + `tailwind-merge` helper. Preserved; every new component uses it for className composition. |
| `useAuth()` | `frontend/src/contexts/AuthContext.tsx` | Existing — reads user / selectedOrganization / selectedAccount. All pages consume it. |

## 3. Component Dependencies

### 3.1 Depends On

| Component | Dependency | Reference |
|-----------|------------|-----------|
| Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) | Source of truth for every page design, token, and component spec. | File key `fhkgWZyTHdKtvDNRoQrcMT`. |
| Existing auth / Firebase | `useAuth()`, sign-in flow, token injection. UI-PRD-02 re-skins the auth pages but does not change auth logic. | `frontend/src/contexts/AuthContext.tsx`, `frontend/src/lib/api.ts` |
| shadcn/ui + Radix primitives | Underlying components in `frontend/src/components/ui/`. UI-PRD-01 re-skins them; later PRDs consume them. | `frontend/CLAUDE.md` §UI Component Library |

### 3.2 Depended On By

Every user-facing capability in KEN-E renders through this component's shell and styles. Specific downstream frontend work that relies on UI-PRD-01's shell being in place:

| Component | Dependency |
|-----------|------------|
| [Agentic Harness](../agentic-harness/README.md) | AH-PRD-02 ships `/workflows/agents` views — relies on UI-PRD-03's `WorkflowsLayout`. Scheduling AH-PRD-02 after UI-PRD-03 ensures it builds on the new design. |
| [Project Tasks](../project-tasks/README.md) | PR-PRD-03 ships the calendar page's data wiring — relies on UI-PRD-04's page shell. |
| [Automations](../automations/README.md) | A-PRD-05 (Automations list) and A-PRD-06 (Automation details) fill out the Automations tab inside UI-PRD-03's `WorkflowsLayout`. |
| [Knowledge Graph](../knowledge-graph/README.md) | KG-PRD-03's read tools back the redesigned Knowledge section owned by UI-PRD-05. |
| [Skills](../skills/README.md) | SK-PRD-03 (Skills authoring UI) lives inside UI-PRD-03's `WorkflowsLayout`; SK-PRD-04's agent-builder controls live inside `/workflows/agents`. |

## 4. Design System References

| Document | Sections | When to Read |
|----------|----------|--------------|
| Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) | Entire file | Before writing any UI code for this component. The Figma Make output provides reference React + Tailwind that should be adapted to this repo's conventions (see server instructions for `get_design_context`). |
| `frontend/CLAUDE.md` | CSS architecture, UI Component Library, Layout Troubleshooting | Before touching global styles or sidebar-aware layout padding. |
| Root `CLAUDE.md` | §2 While Coding, §3 Testing, §6 Tooling Gates | Branded types (C-5), `import type` (C-6), type-over-interface (C-8), test colocation (T-2), gates (G-2, G-3). |

## 5. Project Index

The migration is split across **8 project PRDs** under [`projects/`](./projects/). UI-PRD-01 is a hard prerequisite for UI-PRD-02…08. Beyond that, projects can run in parallel by separate dev teams once their owning backend release is close enough that a redesign won't rot before it ships.

### 5.1 Dependency graph

```
UI-PRD-01 (Design System Foundation + Shell)
    │
    ├──► UI-PRD-02 (Auth, Settings, Chat)         (Release 1)
    ├──► UI-PRD-03 (Workflows Shell + Tabs)       (Release 1 — precedes AH-PRD-02)
    ├──► UI-PRD-04 (Calendar)                     (Release 2 — precedes PR-PRD-03)
    ├──► UI-PRD-05 (Knowledge / Strategy)         (Release 3 — precedes KG-PRD-*)
    ├──► UI-PRD-06 (Extensions)                   (no backend PRD today — roadmap)
    ├──► UI-PRD-07 (Performance)                  (may be subsumed by PE-PRD-01…08)
    └──► UI-PRD-08 (Organization Selection)       (Release 1 — first screen post-auth)
```

### 5.2 Projects

| # | Project PRD | Owner team | Blocked by | Backend alignment | Est. |
|---|-------------|------------|------------|-------------------|------|
| 01 | [Design System Foundation + Shell](./projects/UI-PRD-01-design-system-foundation.md) | Frontend | — | — | ~8–10 days |
| 02 | [Core Shell Pages — Auth, Settings, Chat](./projects/UI-PRD-02-core-shell-pages.md) | Frontend | UI-PRD-01 | Release 1 | ~7–9 days |
| 03 | [Workflows Shell + Tabs](./projects/UI-PRD-03-workflows-shell.md) | Frontend | UI-PRD-01 | Release 1 (precedes AH-PRD-02) | ~4–5 days |
| 04 | [Calendar Page](./projects/UI-PRD-04-calendar-page.md) | Frontend | UI-PRD-01 | Release 2 (precedes PR-PRD-03) | ~4–5 days |
| 05 | [Knowledge / Strategy Section](./projects/UI-PRD-05-knowledge-section.md) | Frontend | UI-PRD-01 | Release 3 (precedes KG-PRD-*) | ~10–14 days |
| 06 | [Extensions Page](./projects/UI-PRD-06-extensions-page.md) | Frontend | UI-PRD-01 | Roadmap (no backend PRD yet) | ~4–6 days |
| 07 | [Performance Page](./projects/UI-PRD-07-performance-page.md) | Frontend | UI-PRD-01 | May be retired in favor of PE-PRD-01…08 | ~3–4 days |
| 08 | [Organization Selection Page](./projects/UI-PRD-08-organization-selection-page.md) | Frontend | UI-PRD-01 | Release 1 | ~3–4 days |

### 5.3 Cross-PRD coordination points

Two touchpoints need conscious coordination across components because a page's shell lives here and its data wiring lives elsewhere:

- **Workflows shell handoff (UI-PRD-03 ↔ AH-PRD-02, A-PRD-05/06, SK-PRD-03):** UI-PRD-03 ships `WorkflowsLayout` and three empty tab pages (`AgentsPage`, `AutomationsPage`, `SkillsPage`) that render skeletons or empty states. Data wiring is added later by each owning PRD. The layout's tab contract (tab registration, active-tab URL sync) must be stable before AH-PRD-02 starts; lock it in UI-PRD-03 code review.
- **Calendar page handoff (UI-PRD-04 ↔ PR-PRD-03):** UI-PRD-04 ships the `/calendar` route, `CalendarPage` shell with calendar + list views, `ActivityDetailPanel`, `ProjectEditDrawer` — all using mocked data. PR-PRD-03 replaces the mock with `/api/v1/plans/*` wiring and the `ProjectPlanContext`. Agree on the component prop signatures in UI-PRD-04 code review.

### 5.4 Recommended workflow

1. **Day 1:** Frontend kicks off UI-PRD-01. Every other UI-PRD is blocked on it.
2. **Day ~10 (UI-PRD-01 merged):** UI-PRD-02 and UI-PRD-03 start in parallel (two sub-teams). UI-PRD-03 must land before AH-PRD-02's frontend phase begins.
3. **Release 2 kickoff:** UI-PRD-04 begins ahead of PR-PRD-03.
4. **Release 3 kickoff:** UI-PRD-05 begins ahead of KG-PRD-01.
5. **Anytime after UI-PRD-01:** UI-PRD-06 and UI-PRD-07 slot in based on team capacity.

## 6. Global Document References

| Document | Relevant Sections | Why |
|----------|-------------------|-----|
| `frontend/CLAUDE.md` | Entire file | Frontend conventions, CSS architecture, layout padding math, shadcn primitives. |
| Root `CLAUDE.md` | §2 While Coding, §3 Testing, §6 Tooling Gates, §7 Git | Branded types, `import type`, test colocation, lint/typecheck/format gates, Conventional Commits. |
| `docs/design/DESIGN-REVIEW-LOG.md` | Latest entries | Track design-doc revisions that affect UI; add an entry when a UI-PRD lands a non-trivial design decision. |
| Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) | Entire file | Source of truth for every page, token, and component. |

## 7. Conventions and Constraints

### Scope boundary with backend-owned frontend work

Several pages have a backend-owning component that already reserves frontend scope (AH-PRD-02, PR-PRD-03, A-PRD-05/06, SK-PRD-03, KG-PRD-03). To avoid duplication:

- **UI projects own:** route registration, page shell, layout composition, styling, shared components (panels, drawers, modals that recur across pages), mocked data rendering, empty states, and component tests for the shell.
- **Backend-owning PRDs own:** typed API clients, React Query hooks, context/service modules, branded-type transformers, data-wired rendering, optimistic-update logic, integration tests against the API.
- **Handoff:** the UI-PRD ships the page with a typed `data` prop (or a mockable context). The backend-owning PRD replaces the mock with real wiring. Prop signatures are locked in the UI-PRD's code review.

Every project PRD restates this boundary at the top so a dev team reading only the PRD doesn't have to hunt for it.

### File structure

- Follow the existing structure (`frontend/src/pages/`, `frontend/src/components/`, `frontend/src/contexts/`). Do not restructure to `frontend/src/app/` as part of this migration — that is a separate decision tracked elsewhere.
- Page components live in `frontend/src/pages/`; subsections (e.g., Workflows tabs, Knowledge sub-pages) may nest under `frontend/src/pages/{section}/`.
- Section-specific components live in `frontend/src/components/{section}/`; truly shared chrome lives in `frontend/src/components/layout/`.

### Styling

- All color, typography, and spacing come from CSS variables defined in `frontend/src/index.css` and surfaced through Tailwind via `tailwind.config.ts`. Never hard-code a hex in a component.
- Use the `cn()` utility for every `className` composition. Prefer Tailwind utility classes over inline styles or component-level CSS files.
- Dark mode is a first-class concern: every new component must render correctly under both light and dark themes.

### TypeScript

- Branded types for every ID (CLAUDE.md C-5).
- `import type { … }` for type-only imports (C-6).
- `type` over `interface` unless interface merging is required (C-8).
- No new comments except critical caveats (C-7).

### Testing

- Colocated component tests in `*.test.tsx` (CLAUDE.md T-2).
- Each UI-PRD ships tests for new shell components; tests for data-wired behaviour live with the backend-owning PRD.
- No heavy mocking of the shell itself — tests exercise the composed page where possible.

### Gates

- `npm run build`, `npm run typecheck`, `npm run format.fix`, and `npm test` must pass before merge (G-2, G-3).

### Standard shape for a project PRD in [`projects/`](./projects/)

Every PRD follows the shared 10-section structure used across sibling components:

1. Context — problem this PRD solves
2. Scope — explicit in/out
3. Dependencies — other PRDs, files, services
4. Data contract — TypeScript types owned or consumed
5. Implementation outline — files to create / modify (table)
6. API contract — endpoints consumed (owned = N/A for this component)
7. Acceptance criteria — what "done" means
8. Test plan — component / visual / (optional) integration coverage
9. Risks & open questions
10. Reference — links back to sibling PRDs, upstream design docs, Figma

---

<!-- PRD MAINTENANCE NOTES

Updating this PRD:
- When a new UI project PRD is authored (e.g. UI-PRD-08): add it to §5.2 Projects and update §5.1 the dependency graph.
- When a project ships: update §5.2 status via PROJECT-PLANNER.md; update §2.1 Key Directories if new files land outside existing conventions.
- When the scope boundary with a backend PRD shifts: update §7 and the affected project PRD.
- When the Figma source changes significantly: note the change in DESIGN-REVIEW-LOG.md and update §4.

This PRD is read by the Dev Team agent during implementation planning. Keep it concise — every sentence should help a dev write better code or avoid mistakes.
-->
