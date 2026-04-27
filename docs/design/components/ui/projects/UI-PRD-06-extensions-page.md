# UI-PRD-06 — Extensions Page

**Status:** Blocked on UI-PRD-01; **roadmap-only backend** (no backend PRD authored yet)
**Owner team:** Frontend
**Blocked by:** UI-PRD-01
**Parallel with:** UI-PRD-02, UI-PRD-03, UI-PRD-04, UI-PRD-05
**Estimated effort:** 4–6 days

---

## 1. Context

The Figma design introduces an Extensions concept — a marketplace-style gallery of first-party installable tools (Dashboard Creator, Performance Optimizer) that can be activated per account. There is **no corresponding backend PRD** in `PROJECT-PLANNER.md` at the time of writing; the user has confirmed Extensions is an active roadmap item, so this PRD ships the UI shell now. Each extension's activation and execution semantics are stubbed and will be wired when the backend roadmap for Extensions lands.

**Scope boundary:** this PRD owns the marketplace shell, the individual extension landing pages, and the per-extension activation UI as UI-only (mocked). A future backend PRD will own the activation API, entitlement model, and extension runtime.

## 2. Scope

### In scope
- New `/extensions` route under `LayoutC`
- `ExtensionsIndex` — marketplace gallery with extension cards (icon, name, short description, primary CTA)
- `/extensions/dashboard-creator` — `DashboardCreatorExtension` shell
- `/extensions/performance-optimizer` — `PerformanceOptimizerExtension` shell
- Shared `ExtensionCard` and `ExtensionLanding` components
- "Activate" button per extension (mocked; shows a toast)
- Sidebar nav entry for Extensions
- Component tests for shell and cards

### Out of scope
- Any backend — no activation API, no entitlement model, no execution runtime
- Third-party extension support (first-party only for v1)
- Extension marketplace search / filters
- Per-account extension billing UI

## 3. Dependencies

- **UI-PRD-01:** `LayoutC`, shadcn primitives (Card, Button, Dialog)
- **Future backend (not yet scoped):** a component PRD for Extensions runtime and activation API. Flag to product/engineering leadership at UI-PRD-06 kickoff to confirm the backend track.
- **Figma nodes:** ExtensionsIndex, DashboardCreatorExtension, PerformanceOptimizerExtension

## 4. Data contract (TypeScript)

```ts
// frontend/src/pages/extensions/extensionCatalog.ts

export type ExtensionId = "dashboard-creator" | "performance-optimizer";

export type ExtensionDefinition = {
  id: ExtensionId;
  name: string;
  shortDescription: string;
  longDescription: string;
  icon: string;         // lucide icon name or asset path
  status: "available" | "coming-soon";
};
```

The catalog is static in v1 — a hard-coded array in `extensionCatalog.ts`. When the backend lands, it replaces the array with an API fetch.

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `frontend/src/pages/extensions/ExtensionsIndex.tsx` |
| Create | `frontend/src/pages/extensions/DashboardCreatorExtension.tsx` |
| Create | `frontend/src/pages/extensions/PerformanceOptimizerExtension.tsx` |
| Create | `frontend/src/components/extensions/ExtensionCard.tsx` |
| Create | `frontend/src/components/extensions/ExtensionLanding.tsx` — shared landing-page shell with hero / feature list / activate CTA |
| Create | `frontend/src/pages/extensions/extensionCatalog.ts` — static catalog |
| Modify | `frontend/src/App.tsx` — register the three new routes |
| Modify | `frontend/src/components/layout/Sidebar.tsx` — Extensions entry |
| Create | colocated `*.test.tsx` for each new component |

### Page structure

- **ExtensionsIndex:** gallery grid of `ExtensionCard`s (one per catalog entry). Click navigates to the extension's landing page.
- **ExtensionLanding** (shared): hero with icon + name + short description; feature list; "Activate" button (mocked); footer with "coming-soon" badge when `status === "coming-soon"`.
- **DashboardCreatorExtension** / **PerformanceOptimizerExtension:** each composes `ExtensionLanding` with its own content.

### Activation (mocked)

Clicking "Activate" shows a toast: "Activation coming soon — check back when the Extensions backend lands." The button is disabled for `coming-soon` extensions.

## 6. API contract

N/A. Future Extensions backend PRD will own activation endpoints.

## 7. Acceptance criteria

1. Sidebar has an Extensions entry; clicking it navigates to `/extensions`.
2. `/extensions` renders the gallery with cards for Dashboard Creator and Performance Optimizer.
3. Clicking a card navigates to its landing page; back navigation returns to the index.
4. Each landing page renders hero + feature list + Activate button; clicking Activate shows the mocked toast.
5. `coming-soon` extensions render a disabled Activate button and a "Coming soon" badge.
6. Dark mode renders correctly.
7. Component tests pass; `npm run typecheck`, `npm run format.fix`, `npm run build`, `npm test` pass.

## 8. Test plan

**Component tests:**
- `ExtensionsIndex.test.tsx`: renders one card per catalog entry; click navigates
- `ExtensionCard.test.tsx`: renders name + icon; `coming-soon` variant renders badge
- `ExtensionLanding.test.tsx`: renders hero + feature list; Activate toast fires
- `DashboardCreatorExtension.test.tsx` / `PerformanceOptimizerExtension.test.tsx`: render expected content

**Manual smoke:**
- Navigate gallery → landing → back; verify toast on Activate

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| Backend PRD never materializes; this page ships as permanent "Coming soon" | Flag at kickoff; if backend is >2 releases out, consider shipping Extensions behind a feature flag until activation exists |
| Extension catalog outgrows two entries and hard-coded static array becomes unwieldy | When the catalog exceeds ~5 entries, extract to a JSON file; at that point the backend should own it |
| Per-extension UX diverges significantly from the shared `ExtensionLanding` pattern | Keep `ExtensionLanding` as the default; override on a per-extension basis only when the design requires |

### Open questions

- **Q:** Is Extensions an account-level or organization-level concept? → **Defer** to the future backend PRD.
- **Q:** Should UI-PRD-06 ship behind a feature flag? → **Recommendation:** yes, gate on `VITE_EXTENSIONS_ENABLED=true` so the nav entry can hide until backend is ready. Confirm with product at kickoff.

## 10. Reference

- Parent component: [`../README.md`](../README.md)
- Sibling: [`UI-PRD-01-design-system-foundation.md`](./UI-PRD-01-design-system-foundation.md)
- Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) — ExtensionsIndex, DashboardCreatorExtension, PerformanceOptimizerExtension
- CLAUDE.md rules in scope: C-5, C-6, C-8; T-2; G-2, G-3
