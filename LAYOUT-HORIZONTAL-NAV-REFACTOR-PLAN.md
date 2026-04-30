# Layout Refactor: Install figma-export Frontend

**Author:** Ken Williams (with Claude Opus 4.7 — drafted 2026-04-30, rev 2)
**Status:** Plan / not yet started
**Owner:** Ken Williams (manual execution — not assigned to autonomous agents)
**Related:** PR #302 (Wave 2 — UI-15 LayoutC + UI-16 LayoutSettings), Linear UI-PRD-01
**Canonical reference:** `docs/figma-export/src/app/layouts/LayoutC.tsx` and the components it imports

---

## 1. Why this work is needed

PR #302 ships `LayoutC` correctly per its Linear-issue acceptance criteria, but the resulting page does not match the canonical figma reference at `docs/figma-export/src/app/layouts/LayoutC.tsx`. The mismatch traces back to **Wave 1 specification drift**, not a Wave 2 implementation defect.

**What the figma-export shows at `/`:**
- Top header (desktop) containing: `Logo` → `AccountSwitcher` → vertical separator → **horizontal primary nav** (Chat, Performance, Calendar, Workflows, Knowledge, Extensions, Settings as violet pills) → `NotificationBell` + `ProfileMenu`. Rainbow-gradient bottom border.
- `Extensions` nav pill expands a hover panel listing active extensions, sourced from `useExtensions()` context.
- Mobile (`<768px`) compact top header (Logo + AccountSwitcher + Bell + Profile) plus a **bottom tab bar** with all 7 nav items as icon + tiny label.
- Main content area beside a `SessionsSidebar` (chat history, left rail).
- On non-home pages, a collapsible **Mini Chat Widget** docked at the bottom with a drag-resize handle and an embedded `<ChatInterface compact />`.
- Theme toggle lives **inside `ProfileMenu`** (not as a separate icon button) — `ProfileMenu.tsx:20` calls `useTheme()`.

**What we built across Wave 1 + Wave 2:**
- `Sidebar.tsx` (UI-17) — vertical left rail rendering the 7 primary-nav items as a column of icons + labels.
- `TopNav.tsx` (UI-18, with UI-15 ThemeToggle wiring) — slim top bar with `AccountSwitcher | spacer | NotificationBell + ThemeToggle + ProfileMenu`.
- `LayoutC.tsx` (UI-15) — composes `<Sidebar />` (left) + `<TopNav />` (top) + `<main>{children}</main>`.

Same nav items, **wrong axis**; ThemeToggle in the wrong place; no Mini Chat Widget; no SessionsSidebar; no Extensions hover; no mobile bottom tab bar.

**Root cause of the drift:**
- UI-17 Linear AC text said *"renders nav items per Figma"* without specifying axis or relationship to TopNav.
- UI-18 Linear AC text did not include the primary navigation items.
- The Wave 1 Dev Team planning agents either did not load `docs/figma-export/src/app/layouts/LayoutC.tsx` or read it but anchored on the issue titles instead of the figma's actual component composition.
- UI-15 (Wave 2) faithfully composed those two components; the inputs were the wrong shape.

This refactor is being executed **manually** because the same Linear-spec drift would likely re-produce a near-version of the same mistake if reissued to agents, and the figma-export reference is concrete enough to follow directly.

---

## 2. Goal

Make `localhost:8080/` visually and behaviorally match `docs/figma-export/src/app/layouts/LayoutC.tsx` at every breakpoint shown in the figma — desktop and mobile equally — without re-introducing legacy chrome (`HomeLayout`, `IconNavigation`, `ContextSidebar`, `GlobalHeader`).

After this work:
- `/` renders the figma desktop top bar (Logo + AccountSwitcher + horizontal nav + Bell + Profile, with rainbow bottom border).
- Theme toggle is reachable from inside `ProfileMenu` (not as a standalone TopNav button).
- The left side of `/` shows a stub `SessionsSidebar` ported from figma (CH-PRD-02 will later replace the stub with the real chat-session-history wiring).
- The Extensions nav pill renders the figma hover panel, backed by a stub `ExtensionsContext`.
- Non-home pages render the Mini Chat Widget at the bottom (collapsible, resizable), backed by a stub `<ChatInterface compact />` until CH-PRD-02 wires it.
- Mobile (`<768px`) renders the compact top header plus the figma bottom tab bar.
- The DOM still passes UI-15's negative regression assertion: no `IconNavigation`, `ContextSidebar`, or `GlobalHeader` root element present at `/`.
- UI-PRD-01 §7 ACs that the figma does not enforce (semantic landmarks `<header>`/`<main>`, `LAYOUT_BANNER_REGISTRY` / `bannerSlot`) remain in place for PRD compliance.

---

## 3. Scope (everything below is in scope)

| # | Item | figma-export reference | Notes |
|---|------|------------------------|-------|
| 1 | Port `Logo` component (already done in commit `1828994`) | `src/app/components/Logo.tsx` | Use `<Logo variant="icon" size="sm" />` in TopNav and LayoutSettings |
| 2 | Rewrite `TopNav.tsx`: desktop header + mobile compact header | `src/app/layouts/LayoutC.tsx:80-178` | Includes Logo, AccountSwitcher, horizontal primary nav, Bell, Profile; rainbow bottom border at both breakpoints |
| 3 | Add `ExtensionsNavItem` (with hover panel) | `src/app/layouts/LayoutC.tsx:308+` | Hovered Extensions pill expands a panel listing active extensions |
| 4 | Stub `ExtensionsContext` + `ExtensionsProvider` | `src/app/contexts/ExtensionsContext.tsx` | Returns an empty list of active extensions until the Extensions component PRD ships; preserves the figma context shape so the hover panel renders |
| 5 | Rewrite `LayoutC.tsx` as the figma's outer layout | `src/app/layouts/LayoutC.tsx:80-306` | Wraps everything in `<ExtensionsProvider>`; renders the new top bars, Mini Chat Widget on non-home, mobile bottom nav |
| 6 | Add Mini Chat Widget to `LayoutC` | `src/app/layouts/LayoutC.tsx:201-266` | Collapsible bottom panel with drag-resize handle and embedded `<ChatInterface compact />`; only on non-home routes; desktop only (`hidden md:block`) |
| 7 | Stub `<ChatInterface compact />` | `src/app/components/ChatInterface.tsx` | Placeholder until CH-PRD-02 wires the real chat. Render a non-functional shell that visually matches the figma; mark with a TODO referencing CH-PRD-02 |
| 8 | Add mobile bottom tab bar | `src/app/layouts/LayoutC.tsx:268-303` | `grid grid-cols-7`, all 7 nav items as icon + tiny label, active state `text-[var(--color-violet-500)] scale-110`, top border `--gradient-rainbow` |
| 9 | Stub `SessionsSidebar` | `src/app/components/SessionsSidebar.tsx` (218 lines) | Port the visual shell from figma; mark internals (session selection, search, categories) as `TODO(CH-PRD-02)`. Mounts at the left of the main content area in `LayoutC` (`md:flex` only) |
| 10 | Move ThemeToggle into `ProfileMenu`'s dropdown | `src/app/components/ProfileMenu.tsx:20` (`useTheme` consumer) | Remove `<ThemeToggle />` from `TopNav` (Wave 2 wiring); the theme toggle UI ships inside the ProfileMenu dropdown via `useTheme().setTheme(...)`, matching figma |
| 11 | Render registered `SUPER_ADMIN_NAV` rows in `ProfileMenu`'s dropdown | n/a (figma silent — preserves UI-PRD-01 / FF-PRD-02 contract) | Section labeled "Admin" in the dropdown, gated on `useAuth().isSuperAdmin === true`; uses `useSyncExternalStore` against the existing registry |
| 12 | Delete `Sidebar.tsx` and its tests | n/a | Extract `SUPER_ADMIN_NAV`, `registerSuperAdminNavRow`, `resetSuperAdminNavForTesting`, `_navSubscribe`, `_getNavSnapshot` into `frontend/src/components/layout/super-admin-nav-registry.ts` first; consumers will be `ProfileMenu` (item 11) |
| 13 | Preserve PRD-required additions on top of figma | UI-PRD-01 §5, §7 AC-6, AC-16 | Keep `LAYOUT_BANNER_REGISTRY` / `registerLayoutBanner` / `<bannerSlot>` outlet in `LayoutC` between top nav and main content; keep `<header>` and `<main>` semantic-landmark wrappers (figma uses `<div>`s, but PRD requires landmarks for accessibility) |
| 14 | Update tests | n/a | TopNav, LayoutC, ProfileMenu, Home — see §5.10 for specifics |

---

## 4. Reference materials

| File | Use as |
|------|--------|
| `docs/figma-export/src/app/layouts/LayoutC.tsx` | Canonical layout source — copy structure verbatim |
| `docs/figma-export/src/app/components/Logo.tsx` | Already ported in commit `1828994` |
| `docs/figma-export/src/app/components/AccountSwitcher.tsx` | Compare against `frontend/src/components/layout/AccountSwitcher.tsx`; align if behavior differs |
| `docs/figma-export/src/app/components/NotificationBell.tsx` | Same |
| `docs/figma-export/src/app/components/ProfileMenu.tsx` | Adopt the figma version's `useTheme()` integration; merge in our existing auth-handler wiring + add the SUPER_ADMIN_NAV section (item 11) |
| `docs/figma-export/src/app/components/ThemeToggle.tsx` | Source of the toggle UI now embedded inside ProfileMenu |
| `docs/figma-export/src/app/components/SessionsSidebar.tsx` | Port for the stub; visuals only |
| `docs/figma-export/src/app/components/ChatInterface.tsx` | Port for the stub; visuals only |
| `docs/figma-export/src/app/contexts/ExtensionsContext.tsx` | Source of the stub provider/consumer signatures |
| `frontend/src/index.css` | Verify Soft Maximalism tokens used by the figma exist: `--gradient-rainbow`, `--color-violet-500`, `--color-violet-100`, `--color-text-inverse`, `--color-text-tertiary`, `--color-bg-secondary`, `--color-accent`, `--color-border-default`, `--shadow-color-violet`, `--shadow-color-blue`, `--radius-pill`, `--radius-md`, `--ease-bounce`, `--ease-default`, `--duration-fast`, `--duration-default`, `--text-body-sm`, `--text-body-md`, `--font-display`, `--color-blue-500` |
| `docs/design/components/ui/projects/UI-PRD-01-design-system-foundation.md` | §7 ACs that survive the refactor: AC-3 (theme persistence), AC-6 (LayoutC composes shell + bannerSlot), AC-8 (`/` renders through LayoutC), AC-9 (dark mode across shell), AC-16 (semantic landmarks + axe-core baseline) |

---

## 5. File-by-file changes

### 5.1 `frontend/src/components/branding/Logo.tsx` — already done

Created in commit `1828994`. Verify it's used by `LayoutSettings.tsx` and the new `TopNav.tsx`.

### 5.2 `frontend/src/components/layout/super-admin-nav-registry.ts` (new)

Extract the registry-related exports from the existing `Sidebar.tsx`:

```ts
// Move these from Sidebar.tsx without semantic changes:
//   - type SuperAdminNavRow
//   - SUPER_ADMIN_NAV (mutable internal + readonly export)
//   - _navSubscribe, _getNavSnapshot
//   - registerSuperAdminNavRow
//   - resetSuperAdminNavForTesting
```

Keep the path-validation regex, the duplicate-id guard, the `useSyncExternalStore`-friendly `_navSubscribe` / `_getNavSnapshot` machinery, and the existing tests verbatim.

### 5.3 `frontend/src/contexts/ExtensionsContext.tsx` (new — stub)

Port the figma-export's `ExtensionsContext` shape. Return an empty `getActiveExtensionDefinitions()` until a real Extensions component lands. Mark the file with a top-line `// TODO: stub for Extensions PRD; replace with real implementation when Extensions component ships.`

### 5.4 `frontend/src/components/chat/SessionsSidebar.tsx` (new — stub)

Port `docs/figma-export/src/app/components/SessionsSidebar.tsx` visuals (the 218 lines). Wire the props (`sessions`, `onSessionSelect`, `onNewSession`) to no-op handlers and an empty session list — the visual shell is the goal; CH-PRD-02 will replace internals. Mark with `// TODO(CH-PRD-02): replace stub with real chat-session-history integration.`

This file lives in `components/chat/` (not `components/layout/`) because UI-PRD-01 §2 explicitly assigns SessionsSidebar to the Chat component. The stub sits in the Chat namespace from day one so CH-PRD-02 simply replaces internals without moving the file.

### 5.5 `frontend/src/components/chat/ChatInterface.tsx` (new — stub)

Port the figma-export `ChatInterface` (compact mode). Render a non-functional shell that visually matches; intercept any handlers as no-ops. Mark with `// TODO(CH-PRD-02): replace stub with real chat session integration.`

Lives in `components/chat/` for the same reason as item 5.4.

### 5.6 `frontend/src/components/layout/TopNav.tsx` — full rewrite

Transcribe the desktop header (figma `LayoutC.tsx:80-150`) and mobile compact header (figma `LayoutC.tsx:152-177`). The component renders **both** breakpoints' headers internally, hidden via Tailwind `hidden md:block` / `md:hidden` classes — the consumer (LayoutC) just renders `<TopNav />` once.

Inside the desktop block:
- `Logo variant="icon" size="sm"` left-most.
- `AccountSwitcher` next.
- Vertical separator (`h-8 w-px bg-[var(--color-border-default)] mx-5 shrink-0`).
- `<nav aria-label="Primary navigation" className="flex items-center gap-1 lg:gap-2 flex-1">` with the 7 `NAVIGATION` items rendered as `PrimaryNavItem`. The Extensions item renders `ExtensionsNavItem` from item 5.7.
- Right cluster: `NotificationBell` + `ProfileMenu`. **No standalone `<ThemeToggle />`** — that lives inside ProfileMenu now (item 5.9).

Pill styling per figma `LayoutC.tsx:117-125`:
- Active: `bg-[var(--color-violet-500)] text-[var(--color-text-inverse)] shadow-[var(--shadow-color-violet)]`
- Default: `text-[var(--color-text-tertiary)]`
- Hover: `hover:bg-[var(--color-accent)] hover:text-[var(--color-violet-500)] hover:-translate-y-0.5`
- Pill shape: `rounded-[var(--radius-pill)]`
- Transition: inline `style={{ transitionTimingFunction: 'var(--ease-bounce)', transitionDuration: 'var(--duration-fast)' }}`
- Icon-only at `md` viewport: hide label `<span className="hidden lg:inline">` and show via `Tooltip` from `@/components/ui/tooltip`.

The `NAVIGATION` array — copy verbatim from figma `LayoutC.tsx:25-33`:
```ts
const NAVIGATION = [
  { name: "Chat",        href: "/",                  icon: MessageSquare },
  { name: "Performance", href: "/performance",       icon: TrendingUp },
  { name: "Calendar",    href: "/calendar",          icon: Calendar },
  { name: "Workflows",   href: "/workflows",         icon: Network },
  { name: "Knowledge",   href: "/strategy",          icon: BookOpen },
  { name: "Extensions",  href: "/extensions",        icon: Puzzle },
  { name: "Settings",    href: "/settings/account",  icon: Settings },
] as const;
```

Mobile compact header: `Logo` + `AccountSwitcher compact` (left, min-width); `NotificationBell` + `ProfileMenu` (right). Rainbow border at 3px (figma uses 3px on mobile, 4px on desktop).

### 5.7 `frontend/src/components/layout/ExtensionsNavItem.tsx` (new — extracted from figma `LayoutC.tsx:308+`)

Port the figma's `ExtensionsNavItem`: a `Link` styled like `PrimaryNavItem` plus a hover panel (open after `onMouseEnter`, close after a 150 ms delay on `onMouseLeave`). Panel content lists `getActiveExtensionDefinitions()` from `useExtensions()` (the stub from item 5.3 returns `[]`, so the panel renders empty until the Extensions PRD wires it).

### 5.8 `frontend/src/components/layout/LayoutC.tsx` — rewrite

Wrap everything in `<ExtensionsProvider>` (figma `LayoutC.tsx:36-41` pattern). Inner component does:

```tsx
<div className="flex flex-col h-screen bg-[var(--color-bg-primary)]">
  <header className="shrink-0">  {/* PRD AC-16: semantic landmark; figma uses <div> */}
    <TopNav />
  </header>

  {/* PRD-required bannerSlot — figma does not have this; UI-PRD-01 AC-6 requires it */}
  {visibleBanners.length > 0 && (
    <div role="region" aria-label="System banners" className="shrink-0">
      {visibleBanners.map(...)}
    </div>
  )}

  <div className="flex-1 overflow-hidden flex">
    <SessionsSidebar /* stub from item 5.4 */ />
    <main className="flex-1 min-h-0 overflow-hidden flex flex-col bg-[var(--color-bg-secondary)]">
      <div className={cn(isFullWidth ? "" : "max-w-screen-2xl", "w-full flex-1 min-h-0 flex flex-col bg-[var(--color-bg-primary)]")}>
        {children}
      </div>
    </main>
  </div>

  {/* Mini Chat Widget — non-home pages, desktop only */}
  {!isHome && (
    <Collapsible open={miniChatOpen} onOpenChange={setMiniChatOpen} className="hidden md:block">
      {/* per figma LayoutC.tsx:201-266 — header tile + collapsible content with resize-drag */}
    </Collapsible>
  )}

  {/* Mobile bottom tab bar — per figma LayoutC.tsx:268-303 */}
  <nav aria-label="Primary navigation (mobile)" className="bg-[var(--color-bg-primary)] md:hidden relative" /* + rainbow top border */>
    <div className="grid grid-cols-7 h-16">
      {/* 7 NAVIGATION items as icon + tiny label, active state text-violet-500 + scale-110 */}
    </div>
  </nav>
</div>
```

Where:
- `isHome = location.pathname === "/"`
- `isFullWidth = location.pathname.startsWith("/strategy") || location.pathname.startsWith("/workflows/automations") || location.pathname.startsWith("/performance/dashboards/")` (verbatim from figma `LayoutC.tsx:72`)
- `miniChatOpen` / `miniChatHeight` / resize handlers — verbatim from figma `LayoutC.tsx:48-70`
- `LAYOUT_BANNER_REGISTRY` / `useSyncExternalStore` plumbing — preserved from current implementation

The `<header>` wrapper around TopNav and the `<main>` wrapper around content are the **only** PRD-driven additions on top of the figma. The PRD AC-16 requires semantic landmarks; the figma uses `<div>`s; we keep the figma's child structure but wrap with the semantic elements as outermost ancestors. This is the explicit PRD-vs-figma decision documented in the original ask.

There are now **two** `<nav>` elements with `aria-label="Primary navigation"` (desktop in TopNav, mobile in LayoutC). Differentiate with `aria-label="Primary navigation (mobile)"` on the bottom tab bar so screen-reader users can tell them apart, and only one is visible at a given breakpoint.

### 5.9 `frontend/src/components/layout/ProfileMenu.tsx` — extend

Adopt the figma version's `useTheme` integration. Inside the dropdown menu, add (in this order):

1. The existing user-info / sign-out content (preserve).
2. A Theme section: a `DropdownMenuItem` (or a small toggle group) that calls `useTheme().setTheme(...)`. Visually match figma `ProfileMenu.tsx`.
3. A Super Admin section, conditionally rendered when `useAuth().isSuperAdmin === true`. Subscribes to the registry from item 5.2 via `useSyncExternalStore(_navSubscribe, _getNavSnapshot, _getNavSnapshot)`. Renders each `SUPER_ADMIN_NAV` row sorted by `order`, filtered by `isVisible !== false`. Each row is a `DropdownMenuItem` with `<Link to={row.path}>`.

The figma ProfileMenu does not include a super-admin section; that section is the only deviation, justified by the UI-PRD-01 / FF-PRD-02 contract (the user explicitly chose to keep `SUPER_ADMIN_NAV`).

### 5.10 Tests

- **`TopNav.test.tsx`** — replace existing assertions with:
  - Desktop header renders `<nav aria-label="Primary navigation">` containing 7 links matching `NAVIGATION` (verify each `href`).
  - Active route's `PrimaryNavItem` has the violet-pill class set; inactive has tertiary-text class set.
  - The Extensions slot renders `ExtensionsNavItem` (smoke test — hover panel covered separately).
  - Rainbow border present (assert via `style.borderImage`).
  - `<ThemeToggle />` is **not** rendered in TopNav.
  - At mobile viewport: only the compact header renders; horizontal nav hidden.
- **`LayoutC.test.tsx`** — replace `<Sidebar>` assertions with:
  - Renders `<header>` (semantic landmark) wrapping TopNav.
  - Renders `<main>` (semantic landmark) wrapping children.
  - Renders `SessionsSidebar` stub at desktop (`hidden md:flex` block).
  - Renders Mini Chat Widget on non-home routes only (use a memory router with `/performance` to assert presence; with `/` to assert absence).
  - Renders mobile bottom-tab `<nav aria-label="Primary navigation (mobile)">` containing 7 items.
  - `LAYOUT_BANNER_REGISTRY` outlet renders only when populated.
  - `useExtensions()` is wrapped by `ExtensionsProvider` (no React context error thrown at render).
- **`ProfileMenu.test.tsx`** — add cases:
  - Toggling theme item updates `<html>` class set (`.dark` ⇄ no class).
  - When `isSuperAdmin === false`, no Admin section renders.
  - When `isSuperAdmin === true` AND a row is registered, the row appears with the correct path; `isVisible: false` rows are filtered.
- **`Home.test.tsx`** — keep the negative assertion regression guard ("no `IconNavigation`, `ContextSidebar`, or `GlobalHeader` root element present in the rendered DOM at `/`"); replace any made-up selectors with checks against the components' exported root display names or actual className signatures.
- **Delete `Sidebar.test.tsx`** after migrating its registry-contract test cases into a new `super-admin-nav-registry.test.ts` (covers dedup, order sort, visibility filter, path-regex rejection, store subscription/notify semantics).
- **`Logo.test.tsx`** (new — small) — render under each `size` prop, assert the `size-N` class is applied; render with `variant="icon"` vs `variant="full"` and assert the wordmark `<h2>KEN-E</h2>` is conditionally absent / present.
- **`SessionsSidebar.test.tsx`** (new — stub) — smoke render the stub with empty props; verify it does not throw.
- **`ChatInterface.test.tsx`** (new — stub) — smoke render compact mode; verify it does not throw.
- **`ExtensionsNavItem.test.tsx`** (new) — render with a stub provider returning two extensions; verify hover opens the panel; mouse-leave with the 150 ms timer closes it.

---

## 6. Acceptance criteria

1. Visiting `http://localhost:8080/` (desktop ≥ 768px) renders the figma top bar exactly: `Logo` (left), `AccountSwitcher`, vertical separator, `<nav aria-label="Primary navigation">` containing 7 violet-pill items (Chat / Performance / Calendar / Workflows / Knowledge / Extensions / Settings), `NotificationBell`, `ProfileMenu`. 4 px rainbow-gradient bottom border.
2. Active route's nav pill has violet background, inverse text, violet shadow.
3. The `Extensions` pill, when hovered, opens a panel listing the active extensions provided by `useExtensions()`. With the stub provider, the panel renders with the figma's empty/zero state.
4. The left side of `/` renders the stubbed `SessionsSidebar` component (visible at `md:flex+`). The component file lives at `frontend/src/components/chat/SessionsSidebar.tsx` so CH-PRD-02 replaces the file in place.
5. Navigating to a non-home route (e.g., `/performance`) renders the Mini Chat Widget docked at the bottom (desktop only). The widget is collapsible; expanded, it shows the figma's drag-resize handle and the stubbed `<ChatInterface compact />`.
6. On mobile (`<768px`), `/` renders: compact top header (Logo + AccountSwitcher + NotificationBell + ProfileMenu, 3 px rainbow bottom border) AND a bottom tab bar (`grid grid-cols-7`, all 7 nav items as icon + tiny label, active state `text-[var(--color-violet-500)] scale-110`, top border `--gradient-rainbow`). The Mini Chat Widget is hidden on mobile.
7. ThemeToggle UI lives **inside** `ProfileMenu`'s dropdown. Clicking it flips `<html>` between `.dark` and no-class state; reload preserves the choice; `<ThemeToggle />` is not rendered anywhere else.
8. `SUPER_ADMIN_NAV` registered rows render in `ProfileMenu`'s dropdown under an "Admin" sub-section. Section is gated on `useAuth().isSuperAdmin === true`. With zero rows, no section renders.
9. `LAYOUT_BANNER_REGISTRY` and `registerLayoutBanner` continue to work; banners render between the header and the main content area as before.
10. Negative regression assertion at `/`: no `IconNavigation`, `ContextSidebar`, or `GlobalHeader` root element present in the rendered DOM. (Test asserts via the components' actual className signatures or a `data-testid` hook added during this refactor — not invented selectors.)
11. Semantic-landmark assertion at `/`: `<header>` wraps TopNav; `<main>` wraps page content; both `<nav aria-label="Primary navigation">` (desktop, inside `<header>`) and `<nav aria-label="Primary navigation (mobile)">` (mobile, outside `<header>`) are present in the DOM (only one visible at a given breakpoint).
12. `LayoutSettings.tsx` uses `<Logo variant="icon" size="sm" />` (already in commit `1828994`).
13. `npm run typecheck`, `npm run format.fix`, `npm run build`, `npm test` all pass.
14. axe-core scan of `/` reports zero new violations under both light and dark themes (excluding pre-existing violations in not-yet-migrated descendants such as `HomeChatArea` — tracked as **CH-6**).

---

## 7. Risks & considerations

| Risk | Mitigation |
|------|------------|
| Deleting `Sidebar.tsx` breaks any consumer that imports it | `grep -rn "from.*['\"]@/components/layout/Sidebar['\"]" frontend/src/` before deletion. Migrate any non-test, non-self imports to the new `super-admin-nav-registry.ts` location first. |
| The stub `SessionsSidebar` and `ChatInterface` may visibly diverge from figma when CH-PRD-02 replaces internals | The stubs port figma's visual shell verbatim; CH-PRD-02 replaces internals only. File paths chosen so the replacement is in-place. |
| The stub `ExtensionsContext` has no real extensions, so the hover panel is always empty | Acceptable; figma's hover panel handles the empty case. The Extensions component PRD will populate `getActiveExtensionDefinitions()` later. |
| Tooltip behavior in headless Chromium (Radix sticky-content quirk noted in UI-17 test results) | Reuse the per-icon-isolated test pattern from `Sidebar.test.tsx` when writing `TopNav.test.tsx`. |
| Horizontal nav at narrower viewports (768-1024px) may overflow if labels are visible | Use `hidden lg:inline` on the label `<span>` to render icon-only at md/lg, restore label at xl+ — exactly the figma pattern (`LayoutC.tsx:128`). |
| The figma uses `bg-background`; our codebase uses `bg-[var(--color-bg-primary)]` for the same intent | Keep our token-explicit form; the figma's `bg-background` is just a Tailwind v4 convention that maps to the same CSS variable. Verify by inspecting `frontend/tailwind.config.ts`'s `theme.extend.colors.background` mapping. |
| Two `<nav aria-label="Primary navigation">` elements (desktop in TopNav, mobile in LayoutC) would cause an axe-core duplicate-landmark violation | Use distinct labels: `"Primary navigation"` (desktop) and `"Primary navigation (mobile)"` (mobile bottom tab bar). |
| Tests for `Sidebar` are extensive (22 cases) and most verify registry semantics, not rendering | Port them to `super-admin-nav-registry.test.ts` with no semantic changes. |
| Tailwind 3.4 vs figma-export's Tailwind 4 differ on dynamic spacing | Verified `tailwind.config.ts` already extends `spacing` with `15` and `18` — the only non-default sizes used by the ported `Logo`. If new figma classes hit other non-default scales, add them to the same `extend.spacing` block. |
| Mini Chat Widget's drag-resize uses `Pointer*` events and `setPointerCapture` | Port the figma's handlers verbatim (`LayoutC.tsx:52-70`); no abstraction layer needed. |

---

## 8. Suggested execution order

1. **Branch from `main`** after PR #302 merges. Suggested name: `feat/figma-layoutc-install`.
2. Extract `super-admin-nav-registry.ts` from `Sidebar.tsx`. Migrate the existing tests verbatim. Run `npm test` to confirm parity.
3. Add stub `frontend/src/contexts/ExtensionsContext.tsx`. No consumers yet; this is a leaf-first add.
4. Add stub `frontend/src/components/chat/SessionsSidebar.tsx` and `frontend/src/components/chat/ChatInterface.tsx`. No consumers yet.
5. Add `frontend/src/components/layout/ExtensionsNavItem.tsx` (consumes `useExtensions()`).
6. Rewrite `TopNav.tsx`. Add tests. Visual-verify against the figma desktop header and mobile compact header.
7. Extend `ProfileMenu.tsx` (add ThemeToggle slot via `useTheme()`; add SUPER_ADMIN_NAV section). Add tests.
8. Rewrite `LayoutC.tsx`: wrap in `<ExtensionsProvider>`; embed TopNav + bannerSlot + SessionsSidebar + main + Mini Chat Widget + mobile bottom tab bar. Update tests.
9. Delete `Sidebar.tsx` and `Sidebar.test.tsx`. Confirm no broken imports.
10. Run the full verification gate: `npm run typecheck`, `npm run format.fix`, `npm run build`, `npm test`, axe-core, manual visual diff against figma-export at port 5173.
11. Open a PR with side-by-side screenshots of `localhost:8080/` (this branch) vs `localhost:5173/` (figma-export) under both themes.

---

## 9. Minimum viable verification

Before opening a PR, confirm these in DevTools at `localhost:8080/` on desktop:

```js
// Desktop primary nav (inside <header>, inside TopNav):
const desktopNav = document.querySelector('header [aria-label="Primary navigation"]');
desktopNav !== null;
desktopNav.querySelectorAll('a').length === 7;

// No standalone ThemeToggle in TopNav:
document.querySelector('header [aria-label="Toggle theme"]') === null;

// SessionsSidebar stub mounted (look for a stable test hook added during port):
document.querySelector('[data-testid="sessions-sidebar"]') !== null;

// LAYOUT_BANNER_REGISTRY outlet conditionally renders:
document.querySelector('[role="region"][aria-label="System banners"]');
// (null when no banners registered, populated otherwise)

// Rainbow gradient border on TopNav desktop wrapper:
const topNavDesktop = document.querySelector('header > div'); // or whatever the wrapper is
getComputedStyle(topNavDesktop).borderImage; // includes "var(--gradient-rainbow)" or its computed gradient

// Legacy chrome NOT present at /:
document.querySelector('nav.icon-navigation, [data-component="icon-navigation"]') === null;
```

At a non-home route (e.g., `/performance`) on desktop:
```js
// Mini Chat Widget visible:
document.querySelector('[data-testid="mini-chat-widget"]') !== null;
```

At mobile (set viewport to 375 × 812):
```js
// Mobile compact header:
document.querySelector('[data-testid="topnav-mobile"]') !== null;

// Mobile bottom tab bar:
const mobileNav = document.querySelector('[aria-label="Primary navigation (mobile)"]');
mobileNav !== null;
mobileNav.querySelectorAll('a').length === 7;

// Mini Chat Widget hidden on mobile:
document.querySelector('[data-testid="mini-chat-widget"]')?.offsetParent === null;
```

Toggle theme via `ProfileMenu`:
```js
// Open ProfileMenu, click theme toggle item:
document.documentElement.classList.contains('dark'); // flips
```

If every check passes, the refactor is functionally complete; the remaining work is visual-polish-pass against the figma reference.

---

## 10. Deferred follow-ups

Items intentionally left out of this refactor's scope. Each needs a separate PR.

### 10.1 Restore `npm test` to a meaningful baseline (Node 25 / jsdom env breakage)

**Status:** workaround in place; real fix deferred.
**Search marker for the follow-up:** `TODO(test-env-node25)` — present in `frontend/src/test/setup.ts` next to the stub, and referenced from this plan.

**Problem (observed 2026-04-30 on Node 25.8.2 / macOS 25.4.0).** A baseline `npm test` at the branch tip reports **58 failing test files / 281 failing tests / 1 unhandled error**, none of which are assertion-level. The dominant categories:

- `localStorage.clear is not a function` in every test that does `localStorage.clear()` in `beforeEach` (e.g. `Sidebar.test.tsx` — 22/22 failing for this reason alone, identical before and after the registry extraction). Preceded by the Node warning `Warning: --localstorage-file was provided without a valid path`. Node 25 ships a built-in partial `localStorage` whose surface differs from jsdom's, and it is leaking into the jsdom environment.
- `target.hasPointerCapture is not a function` on Radix UI `Select` / `Collapsible` interactions — jsdom does not implement Pointer Capture.

These failures predate the layout refactor; they are surfaced here only because Phase 1 step 1 needed to "run `npm test` scoped to those files to confirm parity" and could not, since the old `Sidebar.test.tsx` baseline was already red.

**Workaround applied in this PR.** A `localStorage` stub in `frontend/src/test/setup.ts`, branded against `Storage.prototype` so it satisfies `instanceof Storage`. Reduces the suite from 281 → 252 failing tests. It is **not** a fix and does not address the Pointer Capture failures. Marked with the `TODO(test-env-node25)` comment for grep-ability.

**Known limitation of the stub (2 tests in `Sidebar.test.tsx`).** Two storage-event tests in `Sidebar.test.tsx` (`syncs collapsed state from another tab via storage event`, `ignores storage events for unrelated keys`) construct `new StorageEvent("storage", { storageArea: localStorage, ... })`. jsdom's `StorageEvent` constructor uses an **internal-slot** brand check (private symbols), not just `instanceof Storage` — so even a prototype-branded stub is rejected with `Failed to construct 'StorageEvent': parameter 2 has member 'storageArea' that is not of type 'Storage'`. Patching this would require constructing a real jsdom `Storage` instance from inside jsdom internals, which is brittle. These 2 cases are confined to `Sidebar.test.tsx`; Phase 2.4 deletes that file, so the failures self-resolve when the layout refactor lands. Until then they are **expected ambient failures** in this branch only — do not treat them as regressions.

**Action in the follow-up PR.**
1. Choose one fix path:
   - **(A) Pin Node to 22 LTS** via `frontend/.nvmrc` and `engines.node` in `frontend/package.json`. Narrowest fix — matches Vite/Vitest's currently tested matrix and stops Node 25 from injecting its built-in `localStorage`.
   - **(B) Stay on Node 25**, upgrade jsdom (and/or vitest) to a version that wins the global-storage race against Node 25, AND add Pointer Capture polyfills (e.g. via `@testing-library/user-event` + a small jsdom patch). More work; lets the team stay on the current Node.
2. Remove the `localStorage` stub from `setup.ts`.
3. Confirm `npm test` at HEAD is green (or at least: the 281 pre-existing env failures are gone; only assertion-level failures remain — those are separate work).
4. While here, fix or document the Radix Pointer Capture failures so the suite is meaningfully green, not just no-longer-erroring on `localStorage`.

**Verifier.** Run `npm test` at HEAD before and after the follow-up; diff failure counts.
