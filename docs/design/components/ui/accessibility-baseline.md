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
| `src/test/a11y-primitives.test.tsx` | axe sweeps — Button, Input, Alert, Badge, Card, Tabs |
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
| `violet-600` on `bg-primary` (body text) | ~6.04:1 ✅ | ~8.95:1 ✅ |
| `text-inverse` on `violet-600` (default Button) | ~6.28:1 ✅ | ~8.96:1 ✅ |
| `text-primary` on `teal-500` (TabsTrigger active, light) | ~5.74:1 ✅ | — |
| `text-inverse` on `teal-500` (TabsTrigger active, dark) | — | ~10.56:1 ✅ |

### Large text (≥ 3:1) — bold ≥ 14pt or regular ≥ 18pt

| Pair | Light ratio | Dark ratio | Usage restriction |
|------|------------|------------|-------------------|
| `text-inverse` on `violet-500` | ~4.47:1 ✅ | ~6.0:1 ✅ | Active nav pills, badge labels only — always large/bold. **Not for buttons** — use `violet-600` (normal text AA). |
| `accent-foreground` on `accent` | ~3.995:1 ✅ | ~3.330:1 ✅ | Large interactive labels only (≥ 14pt bold or ≥ 18pt regular) |

---

## Exemptions

### `border-strong` decorative separators

`--color-border-strong` (`#cbd5e1` light / `#475569` dark) is used as a visual separator between surface regions — not as text or an interactive component indicator. WCAG 1.4.11 (Non-text Contrast, 3:1) applies to UI components and graphical objects, not decorative borders. `border-strong` is intentionally excluded from the token-pair test list.

**If `border-strong` is ever used for input borders or focus indicators, re-audit immediately** — those uses would require 3:1 minimum and must be flagged for contrast hardening.

### `violet-500` on light `bg-primary` as normal body text

`--color-violet-500` (`#6366f1`) on `--color-bg-primary` (`#fafbfc`) = ~4.31:1, which does not meet AA for normal text (4.5:1). This pair is intentionally absent from the test. Its usage is limited to:

- Large interactive labels (nav pill text, badge labels — large text AA 3:1 ✅)
- Icon fills where non-text contrast (3:1) applies ✅

Using violet-500 for small body copy would be a WCAG violation. **Use `--color-violet-600` instead** — see usage rule below.

### Brand violet usage rule (UI-54)

When you need brand-tinted text, the choice depends on size:

| Context | Token | Light ratio | Dark ratio |
|---------|-------|-------------|------------|
| Body text (small, regular weight) — chips, paragraphs, captions | `--color-violet-600` (`#4f46e5` / `#a5b4fc`) | ~6.04:1 ✅ AA normal | ~8.95:1 ✅ AA normal |
| Large interactive labels (≥ 14pt bold or ≥ 18pt regular) — nav pills, badge labels | `--color-violet-500` (`#6366f1` / `#818cf8`) | ~4.31:1 ✅ AA large | ~6.0:1 ✅ AA normal |
| Button text (14px bold ≈ 10.5pt — normal text threshold applies) | `--color-violet-600` (`#4f46e5` / `#a5b4fc`) as bg; `text-inverse` as fg | ~6.28:1 ✅ AA normal | ~8.96:1 ✅ AA normal |
| Icons / focus rings / non-text UI | `--color-violet-500` | ✅ 3:1 non-text | ✅ |

The brand identity is preserved via `--color-violet-500` everywhere it visually meets AA at its intended use; for small body text the slightly darker `--color-violet-600` keeps the brand feel while clearing the 4.5:1 floor.

### `text-inverse` on `violet-500` — large text only

Light mode: `#ffffff` on `#6366f1` = ~4.47:1. Passes large-text AA (3:1) but not normal-text AA (4.5:1). Usage is restricted to bold badge labels and active nav pill text (≥ 14pt bold). This constraint is enforced by design convention; no runtime enforcement is currently wired.

**Default Button (`variant="default"`) uses `violet-600` since UI-39.** Button text is `--text-body-md` (14px bold ≈ 10.5pt), below the 14pt bold large-text threshold — normal-text AA (4.5:1) applies. `text-inverse` on `violet-600` = ~6.28:1 light / ~8.96:1 dark, both passing normal-text AA. See `token-contrast.test.ts` `textInverseVioletSixHundredPairs`.

### `accent-foreground` on `accent` — large interactive text only

`--accent-foreground` resolves to `--color-violet-500`; `--accent` resolves to `--color-violet-100` in light mode and `--color-violet-200` in dark mode.

| Mode | Foreground | Background | Ratio | AA verdict |
|------|------------|------------|-------|------------|
| Light | `#6366f1` (violet-500) | `#eef2ff` (violet-100) | ~3.995:1 | ✅ large text (3:1) |
| Dark | `#818cf8` (violet-500) | `#3730a3` (violet-200) | ~3.330:1 | ✅ large text (3:1) |

Both modes fail normal-text AA (4.5:1) but pass large-text AA (3:1). Usage is restricted to large interactive labels (≥ 14pt bold or ≥ 18pt regular). Using `accent-foreground` on `accent` for small body copy would be a WCAG violation. This pair is tested in `token-contrast.test.ts` (`accentFgPairs`, `kind: "large"`) — CI will fail if either mode drops below 3:1.

### `text-tertiary` on `bg-primary`

`--color-text-tertiary` is `#64748b` in **both** light and dark mode; `--color-bg-primary` is `#fafbfc` in light mode and `#0f172a` in dark mode.

> **Deviation from Figma export:** The Figma export specifies `#94A3B8` (slate-400) for light-mode `--color-text-tertiary`. That value produces ~2.47:1 on `#fafbfc`, which fails both WCAG AA thresholds. The implementation uses `#64748b` (slate-500) instead. This deviation was approved as a required WCAG compliance fix (same pattern as the TabsTrigger active-state deviation).

| Mode | Foreground | Background | Ratio | AA verdict |
|------|------------|------------|-------|------------|
| Light | `#64748b` | `#fafbfc` | ~4.57:1 | ✅ passes normal (4.5:1) |
| Dark | `#64748b` | `#0f172a` | ~3.751:1 | ❌ fails normal (4.5:1); ✅ large (3:1) |

Light mode now passes WCAG AA for normal text. Dark mode still fails normal-text AA — follow-on fix needed to raise dark `--color-text-tertiary` to a value that clears 4.5:1 on `#0f172a` (e.g. `#94a3b8` gives ~5.0:1 on the dark background). Dark mode usage remains **limited to secondary/decorative contexts** until the follow-on is applied.

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
