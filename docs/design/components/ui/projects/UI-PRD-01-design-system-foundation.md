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
- Create `LayoutC` (authenticated-app layout) and `LayoutSettings` (settings layout). `LayoutC` exposes a `bannerSlot` outlet above the page content area so downstream components (BL-PRD-04's `OrganizationStatusBanner`, future system-wide banners) can mount without modifying `LayoutC` itself.
- Create / migrate global chrome: `Sidebar`, `TopNav`, `AccountSwitcher`, `NotificationBell`, `ProfileMenu`. `Sidebar` reserves a super-admin-only nav section at the bottom (rendered when `useAuth().isSuperAdmin === true`) into which FF-PRD-02 (and future admin tools) plug their entries.
- Create top-level `<ErrorBoundary>` mounted in `frontend/src/App.tsx` with a fallback UI that uses Soft Maximalism tokens; reset-on-route-change behavior.
- Mount the toast provider (`<Toaster />` from sonner / shadcn) in `frontend/src/App.tsx` so downstream PRDs (UI-PRD-06, BL-PRD-04, etc.) can fire toasts without re-mounting the provider.
- Create `NotFoundPage` and register a catch-all `<Route path="*">` in `frontend/src/App.tsx`. The page renders inside `LayoutC` when the user is authenticated and standalone (no shell) when unauthenticated.
- Mount `ThemeProvider` + `BackgroundEffects` in `frontend/src/App.tsx`
- Land a preview/storybook page (or dev-only route) that renders one of every re-skinned primitive and the shell at different viewport widths for QA
- Component tests for every new shell component

### Out of scope
- Any page-level content (Auth, Chat, Workflows, Calendar, Knowledge, Extensions, Performance) — owned by UI-PRD-02 / UI-PRD-03 / UI-PRD-04 / UI-PRD-05 / UI-PRD-06 / UI-PRD-08 (UI-PRD-07 retired — see component README)
- A standalone `/notifications` full-list page — deferred to the future Notifications component (see [`docs/design/components/backlog/notifications.md`](../../backlog/notifications.md)). `NotificationBell` opens the existing `frontend/src/components/notifications/NotificationSidebar.tsx` until those PRDs ship.
- `SessionsSidebar` — owned by **CH-PRD-02** at `frontend/src/components/chat/SessionsSidebar.tsx` (Chat secondary sidebar; not part of the global shell).
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
| Create | `frontend/src/components/layout/LayoutC.tsx` (with `bannerSlot` outlet above page content) |
| Create | `frontend/src/components/layout/LayoutSettings.tsx` |
| Create | `frontend/src/components/layout/Sidebar.tsx` (includes super-admin-only section at bottom, gated on `useAuth().isSuperAdmin`) |
| Create | `frontend/src/components/layout/TopNav.tsx` |
| Create | `frontend/src/components/layout/AccountSwitcher.tsx` |
| Create | `frontend/src/components/layout/NotificationBell.tsx` |
| Create | `frontend/src/components/layout/ProfileMenu.tsx` |
| Create | `frontend/src/components/layout/AppErrorBoundary.tsx` — top-level error boundary with Soft Maximalism fallback UI; resets on `useLocation()` change |
| Create | `frontend/src/pages/NotFoundPage.tsx` — 404 page; renders inside `LayoutC` when authenticated, standalone when not |
| Modify | `frontend/src/App.tsx` — wrap `<BrowserRouter>` with `<ThemeProvider>` and `<AppErrorBoundary>`; mount `<BackgroundEffects>` and `<Toaster />`; register catch-all `<Route path="*" element={<NotFoundPage />} />` |
| Create | `frontend/src/pages/__dev__/DesignSystemPreview.tsx` (dev-only route, non-production) |
| Modify | `frontend/src/App.tsx` — register `/__dev__/design-system` route under `import.meta.env.DEV` |
| Create | colocated `*.test.tsx` for every new shell component (including `AppErrorBoundary.test.tsx` and `NotFoundPage.test.tsx`) |

### Sidebar and layout padding

Figma shows two sidebar states (collapsed / expanded). Preserve the padding math documented in `frontend/CLAUDE.md` §Layout Troubleshooting — `LayoutC` must calculate its content padding from the sidebar width so pages never overlap chrome. Encode widths as Tailwind utilities so dark-mode and responsive variants stay in sync.

### Responsive breakpoints

Three breakpoints are first-class for every shell component and downstream page UI-PRD:

| Breakpoint | Range | Sidebar | TopNav | LayoutSettings sub-nav |
|-----------|-------|---------|--------|------------------------|
| **Desktop** | ≥ 1200px | Persistent (collapsed or expanded per user pref) | Full (account switcher + bell + profile) | Persistent left rail |
| **Tablet** | 768px – 1199px | Collapsed by default; expand → drawer overlay | Full | Persistent left rail (narrowed) |
| **Mobile** | < 768px | Hidden; hamburger button in `TopNav` opens a full-height drawer | Compact (logo + bell + profile menu; account switcher inside drawer) | Sub-nav collapses to top tab strip above page content |

Encoded as Tailwind utilities (`md:` ≈ 768px, `xl:` redefined to 1200px in `tailwind.config.ts`). Every page-level UI-PRD inherits these breakpoints — no per-page breakpoint redeclaration. Visual QA passes at 375 / 768 / 1200 / 1440 / 1920 widths.

### Accessibility baseline

Every shell component and every downstream page UI-PRD inherits these guarantees:

- **WCAG AA contrast.** All text + interactive surfaces ≥ 4.5:1 (≥ 3:1 for ≥ 18pt). axe-core CI check on changed components in `frontend/src/components/ui/` and `frontend/src/components/layout/` blocks merge on contrast violations.
- **Keyboard navigation.** Every interactive element reachable via Tab; logical Tab order; Esc dismisses modals / drawers / popovers; Arrow keys navigate composite widgets (Tabs, Menu, Listbox).
- **Visible focus.** Every interactive element shows a visible focus ring under both light and dark themes (token: `--ring`). No `outline: none` without a token-driven replacement.
- **Semantic landmarks.** `LayoutC` and `LayoutSettings` render `<header>`, `<nav>`, `<main>`, `<aside>` landmarks; pages render `<h1>` exactly once.
- **Screen-reader labels.** Icon-only buttons (`Sidebar` collapse, `NotificationBell`, `ThemeToggle`) have `aria-label`; status dots have `role="status"` + accessible text.
- **Reduced motion.** `BackgroundEffects` and any new motion respects `prefers-reduced-motion` (already noted in §9 open question — defaulting yes).

These are baseline rules — page UI-PRDs may add additional axe checks but must not weaken these.

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
6. `LayoutC` renders `Sidebar` + `TopNav` (with `AccountSwitcher`, `NotificationBell`, `ProfileMenu`) + `bannerSlot` + page content; `LayoutSettings` renders the settings variant.
7. Sidebar padding math matches `frontend/CLAUDE.md` values at both collapsed and expanded states.
8. `/` renders through `LayoutC` (Home page wrapped), with no visible regression on existing content (content may look unstyled in places where downstream UI-PRDs have not yet migrated a page — that is acceptable).
9. Dark mode renders correctly across every shell component.
10. Dev-only `/__dev__/design-system` route renders one of every re-skinned primitive and the full shell at 375 / 768 / 1200 / 1440 / 1920 widths.
11. `<AppErrorBoundary>` catches an uncaught render error and renders a Soft Maximalism fallback; navigating to a different route resets the boundary.
12. `<Toaster />` is mounted once at the app root; firing a toast from any descendant renders correctly under both themes.
13. Hitting an unknown URL renders `NotFoundPage` (inside `LayoutC` when authenticated; standalone when not).
14. `Sidebar` shows the super-admin section only when `useAuth().isSuperAdmin === true`; the section is empty in this PRD (FF-PRD-02 plugs in its entry).
15. **Responsive breakpoints (§ Responsive breakpoints) verified at 375 / 768 / 1200 / 1440 / 1920** — Sidebar, TopNav, LayoutC, LayoutSettings, and the dev preview render correctly in mobile / tablet / desktop modes; mobile drawer opens from `TopNav`'s hamburger; LayoutSettings sub-nav collapses to a top tab strip on mobile.
16. **Accessibility baseline (§ Accessibility baseline) holds:** axe-core CI passes on every re-skinned primitive and shell component; every interactive element shows a visible focus ring under both themes; semantic landmarks present in `LayoutC` and `LayoutSettings`.

**Definition of Done (applies to every AC above):** `npm run typecheck`, `npm run format.fix`, `npm run build`, and `npm test` all pass; component tests for any new shell component are colocated and passing.

## 8. Test plan

**Component tests (colocated):**
- `ThemeProvider.test.tsx`: toggle flips `.dark` class on `<html>`; `localStorage` persists across remount
- `LayoutC.test.tsx`: renders Sidebar + TopNav + `bannerSlot` + children; sidebar collapse/expand fires correct classes; banner renders only when slot has content
- `LayoutSettings.test.tsx`: renders the narrow variant
- `Sidebar.test.tsx`: nav items render; active route highlights; collapse toggle works; super-admin section visible only when `isSuperAdmin === true`
- `AccountSwitcher.test.tsx`: reads from `useAuth()`; selecting an account calls the auth switch handler
- `NotificationBell.test.tsx`: badge renders count; click opens the existing notification sidebar
- `ProfileMenu.test.tsx`: renders user info; sign-out calls the auth handler
- `AppErrorBoundary.test.tsx`: catches a thrown error; renders fallback; resets on route change
- `NotFoundPage.test.tsx`: renders inside `LayoutC` when authenticated; renders standalone when not

**Visual QA (manual, via dev-only preview route):**
- One pass at light / dark / **375 / 768 / 1200 / 1440 / 1920**
- Screenshot diff against Figma for each re-skinned primitive
- Mobile (< 768px): hamburger opens `Sidebar` drawer; `TopNav` collapses to compact form; `LayoutSettings` sub-nav collapses to top tab strip
- Tablet (768–1199px): `Sidebar` collapsed by default; expand opens drawer overlay
- Desktop (≥ 1200px): full persistent shell

**Accessibility QA:**
- axe-core CI run against the dev preview route — zero violations on shell components and re-skinned primitives
- Manual keyboard-only walkthrough: Tab through `LayoutC` → `Sidebar` → `TopNav` → page content; Esc dismisses drawers / popovers

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
- **Q:** Mobile sidebar drawer — overlay or push-content? → **Default:** overlay (matches Figma; preserves desktop padding math).
- **Q:** `tailwind.config.ts` redefines `xl` to 1200px; does any existing page rely on the default 1280px? → Audit before merge; flag if any `xl:` Tailwind utility breaks.

## 10. Reference

- Parent component: [`../README.md`](../README.md)
- Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism)
- `frontend/CLAUDE.md` — CSS architecture, layout padding math, `cn()` utility, UI Component Library
- Root `CLAUDE.md` — §2 (C-5, C-6, C-7, C-8), §3 (T-2), §6 (G-2, G-3)
