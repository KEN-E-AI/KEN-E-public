# UI Primitive Deviations

This file records known intentional deviations from the Figma export reference
(`docs/figma-export/src/app/components/ui/`). Each entry explains what differs,
why the decision was made, and what callers should be aware of.

Tracked since: UI-14

---

## Badge

**Deviation**: Element type. Figma export uses `<span>`; repo uses `<div>` via
`forwardRef<HTMLDivElement>`.

**Reason**: Preserves the existing API — 72+ callers hold `HTMLDivElement` refs
or rely on block-level containment. Changing the element would require a
coordinated migration across the codebase.

**Impact**: None in practice unless a caller inspects `element.tagName` directly
(e.g. `ref.current.tagName === 'SPAN'`). Display behaviour is identical because
both `<span>` and `<div>` are styled with `display: inline-flex`.

---

## Dialog & Sheet

**Deviation**: Implementation layer. The Figma export replaces Radix UI with a
custom context + portal implementation.

**Reason**: Figma Make runs in a sandboxed iframe environment that restricts
third-party focus management; the export therefore re-implements focus trapping
manually. In the production codebase there is no such constraint. The repo keeps
`@radix-ui/react-dialog` (Dialog and Sheet both use it), which provides a
battle-tested focus trap, scroll lock, and full ARIA semantics out of the box.
Only the Tailwind class tokens were updated from the export.

**Impact**: None for callers. The public component API (`DialogTrigger`,
`DialogContent`, `SheetTrigger`, `SheetContent`, etc.) is unchanged.

---

## Coral palette tokens

**Deviation**: The Figma design file references `--color-coral-100`,
`--color-coral-300`, `--color-coral-500`, and `--shadow-color-coral`. None of
these tokens exist in the repo's CSS custom properties after UI-12.

**Reason**: Coral was intentionally omitted from the UI-12 token set (design
decision). The tokens were mapped to the nearest semantic equivalents already
present in the system:

| Figma token | Repo mapping |
|---|---|
| `--color-coral-100` | `--color-error-bg` |
| `--color-coral-300` | `--color-violet-300` |
| `--color-coral-500` | `--color-violet-500` |
| `--shadow-color-coral` | `--shadow-color-violet` |

**Impact**: If coral is formally added to the design system in a future ticket,
these mappings should be revisited and updated. Callers must not introduce
`--color-coral-*` literals — use the mapped tokens above until coral ships.

---

## All components — forwardRef pattern

**Deviation**: Figma export uses plain function components throughout.

**Reason**: Figma Make's sandbox does not support `React.forwardRef` (the
generated output cannot pass refs through component boundaries). The production
repo uses `React.forwardRef` on every primitive, which is required for
form-library integration (React Hook Form's `register`), portal positioning
(Radix UI anchor refs), and composable UI patterns in the broader codebase.

**Impact**: None. The forwarded ref is additive — callers that do not use refs
are unaffected.

---

## CardTitle

**Deviation**: Heading level changed from `<h3>` (Figma export) to `<h4>`.

**Reason**: Cards appear inside page sections that typically use `<h3>` for
section headings. Rendering `<h3>` inside an `<h3>` context would create an
incorrect document outline. `<h4>` better reflects the typical nesting depth of
cards in the KEN-E page hierarchy.

**Impact**: Minor. Callers that relied on the heading level for CSS outline
styling (e.g. `h3 + .card-body` selectors) may need to update their selector.
Screen-reader users will encounter `<h4>` instead of `<h3>` in the landmark
hierarchy.
