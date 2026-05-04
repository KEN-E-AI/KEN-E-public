# Accessibility Baseline

**Component:** UI  
**Standard:** WCAG 2.1 AA  
**Status:** Implemented (UI-22)

---

## Overview

This document describes the accessibility baseline for the KEN-E frontend — the CI gates that enforce it, the token-pair contrast commitments, and the documented exemptions.

---

## CI Gate

The `frontend-a11y-tests` step in `deployment/ci/pr_checks.yaml` runs on every PR. It executes the following test files via Vitest:

| File | What it covers |
|------|---------------|
| `src/test/axe.test.ts` | `runAxe` helper self-test (trivial DOM) |
| `src/test/wcag.test.ts` | WCAG 2.1 contrast math unit tests |
| `src/test/token-contrast.test.ts` | In-use token-pair WCAG AA verification |
| `src/test/focus-ring-audit.test.ts` | Static `outline-none` / focus-ring audit |
| `src/test/a11y-primitives.test.tsx` | axe sweeps — Button, Input, Alert, Badge, Card |
| `src/test/a11y-shell.test.tsx` | axe sweeps — ThemeToggle, AppErrorBoundary fallback, NotificationBell, SidebarRail |
| `src/test/keyboard-nav.test.tsx` | Keyboard Tab + Enter/Space activation smoke tests |
| `src/test/keyboard-dialog.test.tsx` | Esc dismisses Dialog, Sheet, Popover, DropdownMenu |
| `src/test/keyboard-menu.test.tsx` | Arrow key navigation — Tabs, DropdownMenu, Select |
| `src/test/reduced-motion.test.ts` | `prefers-reduced-motion` CSS rule smoke test |

### axe configuration

axe runs with `color-contrast` disabled in JSDOM. JSDOM has no layout engine — `getComputedStyle` returns empty values, so axe cannot reliably compute contrast ratios. Contrast is instead verified deterministically via token-pair math in `token-contrast.test.ts`. See `src/test/axe.ts` for the shared `runAxe` helper.

---

## WCAG AA Token-Pair Commitments

The following token pairs are verified in `token-contrast.test.ts`. All must meet WCAG 2.1 §1.4.3 AA.

### Normal text (≥ 4.5:1)

| Pair | Light ratio | Dark ratio |
|------|------------|------------|
| `text-primary` on `bg-primary` | ✅ | ✅ |
| `text-primary` on `bg-elevated` | ✅ | ✅ |
| `text-secondary` on `bg-primary` | ✅ | ✅ |
| `text-secondary` on `bg-secondary` | ✅ | ✅ |
| `text-primary` on `bg-secondary` | ✅ | ✅ |
| `success-text` on `success-bg` | ✅ | ✅ |
| `error-text` on `error-bg` | ✅ | ✅ |
| `warning-text` on `warning-bg` | ✅ | ✅ |
| `info-text` on `info-bg` | ✅ | ✅ |

### Large text (≥ 3:1) — bold ≥ 14pt or regular ≥ 18pt

| Pair | Light ratio | Dark ratio | Usage restriction |
|------|------------|------------|-------------------|
| `text-inverse` on `violet-500` | ~4.47:1 ✅ | ~6.0:1 ✅ | Active nav pills, badge labels only — always large/bold |

---

## Exemptions

### `border-strong` decorative separators

`--color-border-strong` (`#cbd5e1` light / `#475569` dark) is used as a visual separator between surface regions — not as text or an interactive component indicator. WCAG 1.4.11 (Non-text Contrast, 3:1) applies to UI components and graphical objects, not decorative borders. `border-strong` is intentionally excluded from the token-pair test list.

**If `border-strong` is ever used for input borders or focus indicators, re-audit immediately** — those uses would require 3:1 minimum and must be flagged for contrast hardening.

### `violet-500` on light `bg-primary` as normal body text

`--color-violet-500` (`#6366f1`) on `--color-bg-primary` (`#fafbfc`) = ~4.31:1, which does not meet AA for normal text (4.5:1). This pair is intentionally absent from the test. Its usage is limited to:

- Large interactive labels (nav pill text, badge labels — large text AA 3:1 ✅)
- Icon fills where non-text contrast (3:1) applies ✅

Using violet-500 for small body copy would be a WCAG violation.

### `text-inverse` on `violet-500` — large text only

Light mode: `#ffffff` on `#6366f1` = ~4.47:1. Passes large-text AA (3:1) but not normal-text AA (4.5:1). Usage is restricted to bold badge labels and active nav pill text (≥ 14pt bold). This constraint is enforced by design convention; no runtime enforcement is currently wired.

---

## Focus Ring Audit

`focus-ring-audit.test.ts` scans all `.tsx` files under `src/components/ui/`, `src/components/layout/`, and `src/components/theme/`. Any file containing `outline-none` must also have a recognized focus-visible companion in the ±3 surrounding lines.

### Recognized companions

| Pattern | Rationale |
|---------|-----------|
| `focus-visible:outline` | Standard Tailwind focus-visible ring |
| `focus-visible:ring` | Ring variant |
| `focus-visible:border` | Border-based focus (e.g. Input) |
| `focus-visible:shadow` | Shadow-based focus |
| `focus:bg-` | Radix menu items — background change on focus |
| `data-[state=` | Radix floating panels (HoverCard, Popover) — not Tab-focusable; `outline-none` suppresses default browser outline on the panel container |
| `[&_` | Tailwind arbitrary child selector — targets non-focusable child elements (e.g. `[&_.recharts-layer]:outline-none`) |
| `select-none` | `role="option"` listbox items in comboboxes — navigated by arrow keys, not Tab; `outline-none` is correct |

---

## `<aside>` Landmark

`LayoutC.tsx` wraps `SessionsSidebar` in:

```html
<aside aria-label="Chat sessions" class="hidden md:flex …">
```

This gives screen reader users a named complementary landmark for the session history panel, satisfying WCAG 2.4.1 (Bypass Blocks) and conforming to ARIA Landmarks best practices.

The landmark is verified in `LayoutC.test.tsx`:
```typescript
test("renders <aside aria-label='Chat sessions'> wrapping SessionsSidebar", () => {
  const aside = screen.getByRole("complementary", { name: /chat sessions/i });
  expect(within(aside).getByTestId("sessions-sidebar")).toBeInTheDocument();
});
```

---

## Reduced Motion

`src/index.css` contains:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

This universal rule suppresses all CSS transitions and animations when the user has opted into reduced motion (WCAG 2.3.3 Animation from Interactions). It is verified by `reduced-motion.test.ts`.

---

## Backlog

Open items (contrast hardening):

- Consider bumping `violet-500` to `violet-600` to achieve ≥ 4.5:1 on `bg-primary` for normal text uses.
- Audit input focus borders — if `border-strong` is ever used as a focus outline, it needs a color update.
- Extend axe sweep coverage to `src/components/chat/` and `src/pages/` as those components stabilize.
- Add exemptions for `text-tertiary` on `bg-primary` (~2.5:1, fails AA — decorative/disabled text only) and `accent-foreground` on `accent` (~3.94:1, fails AA — large-text interactive only).
