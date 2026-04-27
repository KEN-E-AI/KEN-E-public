# UI-PRD-01 — Design System Foundation + Shell

**Status:** Ready for development
**Owner team:** Frontend
**Blocked by:** — (component-entry project)
**Parallel with:** — (every other UI-PRD is blocked on this one)
**Estimated effort:** 8–10 days

---

## 1. Context

The Figma design ([KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism)) introduces a new token system (`theme.css` + `ThemeProvider`), ambient `BackgroundEffects`, two shell layouts (`LayoutC` for authenticated pages, `LayoutSettings` for settings), and a redesigned shared chrome (sidebar, top-nav, account switcher, notification bell, profile menu). Every subsequent UI project plugs into this foundation. Landing it first unblocks UI-PRD-02 through UI-PRD-06 and UI-PRD-08 (UI-PRD-07 is retired — see component README) and ensures sibling-component frontend work (CH-PRD-02, PE-PRD-01, AH-PRD-02, PR-PRD-03, A-PRD-05/06, SK-PRD-03, KG-PRD-*) builds against the new design, not the old one.

**Scope boundary:** this PRD owns the tokens, shell layouts, and global chrome. Page-level content is owned by later UI-PRDs.

## 2. Scope

### In scope
- Migrate Soft Maximalism tokens into `frontend/src/index.css` (colors, typography, spacing, radii, shadows, motion) with light + dark variants
- Extend `frontend/tailwind.config.ts` to surface every new token as a utility class
- Create `ThemeProvider` with `useTheme()` hook, `localStorage` persistence, and a `ThemeToggle` component
- Create `BackgroundEffects` component; mount once at app root
- Re-skin the ~50 shadcn primitives in `frontend/src/components/ui/` to match Figma (Button, Card, Input, Dialog, Sheet, Tabs, etc.) — variant-by-variant audit
- Create `LayoutC` (authenticated-app layout) and `LayoutSettings` (settings layout)
- Create / migrate global chrome: `Sidebar`, `TopNav`, `AccountSwitcher`, `NotificationBell`, `ProfileMenu`, `SessionsSidebar`, `QuickStartGuide`
- Mount `ThemeProvider` + `BackgroundEffects` in `frontend/src/App.tsx`
- Land a preview/storybook page (or dev-only route) that renders one of every re-skinned primitive and the shell at different viewport widths for QA
- Component tests for every new shell component

### Out of scope
- Any page-level content (Auth, Chat, Workflows, Calendar, Knowledge, Extensions, Performance) — owned by UI-PRD-02…07
- Restructuring `frontend/src/` to a `frontend/src/app/` nested layout
- Storybook framework setup (a dev-only route is sufficient)

## 3. Dependencies

- **Figma file key:** `fhkgWZyTHdKtvDNRoQrcMT` — pull each shell component with `get_design_context` by nodeId
- **Existing files to study:**
  - `frontend/src/index.css` — current token system to replace
  - `frontend/src/components/ui/*` — current shadcn primitives to re-skin
  - `frontend/src/components/layout/` — existing layout components (if any) to migrate
  - `frontend/src/App.tsx` — where `ThemeProvider` and `BackgroundEffects` mount
  - `frontend/CLAUDE.md` §Styling System, §Layout Troubleshooting — conventions and sidebar padding math
- **External:** no new npm packages expected; confirm `tailwind-merge`, `clsx`, `class-variance-authority` already in deps

## 4. Data contract (TypeScript)

No server data consumed. Client-side types:

```ts
// frontend/src/components/theme/ThemeProvider.tsx

export type ThemeMode = "light" | "dark";

export type ThemeContextValue = {
  mode: ThemeMode;
  setMode: (mode: ThemeMode) => void;
  toggle: () => void;
};
```

Branded ID types are N/A for this project (no domain entities).

## 5. Implementation outline

| Action | File |
|--------|------|
| Modify | `frontend/src/index.css` — replace brand palette with Soft Maximalism tokens; keep `@layer base` directives |
| Modify | `frontend/tailwind.config.ts` — extend theme with new tokens |
| Create | `frontend/src/components/theme/ThemeProvider.tsx` |
| Create | `frontend/src/components/theme/BackgroundEffects.tsx` |
| Create | `frontend/src/components/theme/ThemeToggle.tsx` |
| Modify | every file in `frontend/src/components/ui/` — re-skin variants to match Figma; preserve APIs |
| Create | `frontend/src/components/layout/LayoutC.tsx` |
| Create | `frontend/src/components/layout/LayoutSettings.tsx` |
| Create | `frontend/src/components/layout/Sidebar.tsx` |
| Create | `frontend/src/components/layout/TopNav.tsx` |
| Create | `frontend/src/components/layout/AccountSwitcher.tsx` |
| Create | `frontend/src/components/layout/NotificationBell.tsx` |
| Create | `frontend/src/components/layout/ProfileMenu.tsx` |
| Create | `frontend/src/components/layout/SessionsSidebar.tsx` |
| Create | `frontend/src/components/layout/QuickStartGuide.tsx` |
| Modify | `frontend/src/App.tsx` — wrap `<BrowserRouter>` with `<ThemeProvider>` + mount `<BackgroundEffects>` |
| Create | `frontend/src/pages/__dev__/DesignSystemPreview.tsx` (dev-only route, non-production) |
| Modify | `frontend/src/App.tsx` — register `/__dev__/design-system` route under `import.meta.env.DEV` |
| Create | colocated `*.test.tsx` for every new shell component |

### Sidebar and layout padding

Figma shows two sidebar states (collapsed / expanded). Preserve the padding math documented in `frontend/CLAUDE.md` §Layout Troubleshooting — `LayoutC` must calculate its content padding from the sidebar width so pages never overlap chrome. Encode widths as Tailwind utilities so dark-mode and responsive variants stay in sync.

### Re-skin approach for `components/ui/`

- Pass 1: update token references (e.g., `bg-primary` → new primary). No API changes. `typecheck` must still pass.
- Pass 2: update variant recipes (`class-variance-authority` configs) to match Figma's size / state matrix.
- Pass 3: visual diff against Figma via the dev-only preview route.

### `AccountSwitcher`, `NotificationBell`, `ProfileMenu`

All three read from `useAuth()` and existing context providers. They render the new shell chrome but do not change auth, notification, or profile logic.

## 6. API contract

N/A — this project consumes no APIs.

## 7. Acceptance criteria

1. `frontend/src/index.css` defines the full Soft Maximalism token set for both `:root` (light) and `.dark` scopes.
2. `tailwind.config.ts` surfaces every new token; no component references a raw hex or rem value.
3. `<ThemeProvider>` wraps the app at root; `useTheme()` returns the current mode and a toggle; preference persists to `localStorage`.
4. `<BackgroundEffects>` renders once under the provider with no interaction side effects.
5. Every file in `frontend/src/components/ui/` has been visually reconciled with Figma; variants match the size/state matrix in the design.
6. `LayoutC` renders `Sidebar` + `TopNav` (with `AccountSwitcher`, `NotificationBell`, `ProfileMenu`) + page content; `LayoutSettings` renders the settings variant.
7. Sidebar padding math matches `frontend/CLAUDE.md` values at both collapsed and expanded states.
8. `/` renders through `LayoutC` (Home page wrapped), with no visible regression on existing content (content may look unstyled in places where downstream UI-PRDs have not yet migrated a page — that is acceptable).
9. Dark mode renders correctly across every shell component.
10. Dev-only `/__dev__/design-system` route renders one of every re-skinned primitive and the full shell at 1280 / 1440 / 1920 widths.

**Definition of Done (applies to every AC above):** `npm run typecheck`, `npm run format.fix`, `npm run build`, and `npm test` all pass; component tests for any new shell component are colocated and passing.

## 8. Test plan

**Component tests (colocated):**
- `ThemeProvider.test.tsx`: toggle flips `.dark` class on `<html>`; `localStorage` persists across remount
- `LayoutC.test.tsx`: renders Sidebar + TopNav + children; sidebar collapse/expand fires correct classes
- `LayoutSettings.test.tsx`: renders the narrow variant
- `Sidebar.test.tsx`: nav items render; active route highlights; collapse toggle works
- `AccountSwitcher.test.tsx`: reads from `useAuth()`; selecting an account calls the auth switch handler
- `NotificationBell.test.tsx`: badge renders count; click opens the existing notification sidebar
- `ProfileMenu.test.tsx`: renders user info; sign-out calls the auth handler

**Visual QA (manual, via dev-only preview route):**
- One pass at light / dark / 1280 / 1440 / 1920
- Screenshot diff against Figma for each re-skinned primitive

**Regression guard:**
- Every existing page must still render without console errors after `App.tsx` wraps everything in `<LayoutC>` (or `<LayoutSettings>` for settings routes). If a page breaks, document it — that page's redesign is owned by a later UI-PRD and can ship unstyled in the interim.

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| Re-skinning every shadcn primitive is a large surface area that can drag on | Scope the variant matrix up front; do Pass 1 (tokens only) before Pass 2 (variants); don't block on 100% visual parity for primitives rarely used |
| Sidebar padding math breaks existing pages whose content is width-constrained | Audit existing pages for `max-w-*` / `mx-auto` patterns that fight the new layout; flag per-page issues for the owning UI-PRD |
| Figma tokens don't map 1:1 to Tailwind utilities | Add a `semantic/` scale (e.g., `bg-surface`, `bg-elevated`) alongside the shadcn-style named tokens when Tailwind defaults don't fit |
| Dark-mode colour parity is under-specified in Figma | Default to a programmatic dark-mode derivation (invert L in oklch); flag misses for a follow-up |
| `App.css` reintroducing Vite template globals | Keep `App.css` empty or minimal per `frontend/CLAUDE.md` §CSS File Structure |

### Open questions

- **Q:** Does the Figma design include a storybook-ready component list, or do we cherry-pick from the Make output? → **Assumption:** cherry-pick via `get_design_context`; the dev-only preview route is our equivalent of a storybook.
- **Q:** Should `BackgroundEffects` be performance-gated (e.g., `prefers-reduced-motion`)? → **Default:** yes, respect the media query and fall back to a static gradient.

## 10. Reference

- Parent component: [`../README.md`](../README.md)
- Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism)
- `frontend/CLAUDE.md` — CSS architecture, layout padding math, `cn()` utility, UI Component Library
- Root `CLAUDE.md` — §2 (C-5, C-6, C-7, C-8), §3 (T-2), §6 (G-2, G-3)
