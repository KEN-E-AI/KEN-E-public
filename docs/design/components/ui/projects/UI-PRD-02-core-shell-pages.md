# UI-PRD-02 — Core Shell Pages: Auth & Settings

**Status:** Blocked on UI-PRD-01
**Owner team:** Frontend
**Blocked by:** UI-PRD-01
**Parallel with:** UI-PRD-03, UI-PRD-06, UI-PRD-08
**Estimated effort:** 5–7 days

---

## 1. Context

Authentication and settings are the "day one" non-conversational surfaces every user touches. Both already exist but use the old design system. This PRD redesigns them onto `LayoutSettings` + the new Soft Maximalism tokens, deletes the legacy admin-style `Home.tsx` hub, and registers `/` as a redirect to `/chat`.

**Scope boundary:** data wiring for authentication (Firebase Auth) and settings endpoints is preserved as-is — this PRD re-skins the existing logic. **The `/chat` page is owned end-to-end by the [Chat component](../../chat/README.md) (CH-PRD-02)** — this PRD does not create the chat route, page, sidebar, or any chat component; it only owns the `/` → `/chat` redirect coordination.

> **History:** UI-PRD-02 originally included `/chat` page creation. The Chat component was carved out as the 15th KEN-E component, and CH-PRD-02 absorbed the chat scope. See [chat README §3.1](../../chat/README.md#31-depends-on) and [chat implementation-plan §5.3](../../chat/implementation-plan.md).

## 2. Scope

### In scope
- Redesign `Authentication.tsx` (sign-in, sign-up, email verification, invitation acceptance flows) onto the new design
- **Auth route-gating change:** `Authentication.tsx` becomes a route-mounted page (no longer inline-rendered by `ProtectedRoute`). `ProtectedRoute` redirects unauthenticated users to `/sign-in` via `<Navigate to="/sign-in" replace />` instead of inline-rendering `<Authentication>`. Mirrors UI-PRD-08's pattern for `<OrganizationSelection>` and makes `/sign-in` (and `/sign-up`) the canonical entry points.
- Redesign `AccountSettings.tsx` (organization + account settings) onto `LayoutSettings`
- Redesign `UserSettings.tsx` onto `LayoutSettings`
- Redesign `AcceptInvitation.tsx` onto the auth layout
- Redesign `/create-organization` page (the destination of the "Create new organization" CTAs in `UI-PRD-08`'s `SelectOrganizationPage` and the zero-orgs auto-redirect). Standalone layout (same `BackgroundEffects` treatment as the auth pages, no `LayoutC`/`LayoutSettings` shell). Reuses the existing org-creation form logic; only re-skins.
- Delete the legacy `Home.tsx` and register `/` as `<Navigate to="/chat" replace />` (the destination is owned by CH-PRD-02 behind the `chat_v2_enabled` flag — see §11 Cleanup and the coordination note in this PRD's Reference section)
- Register `/settings` (no sub-route) as `<Navigate to="/settings/organization" replace />` so users typing the bare path land on a real page instead of hitting UI-PRD-01's `NotFoundPage`.
- **`LayoutSettings` sub-nav as a registry pattern.** The settings sub-nav reads its rows from a `SETTINGS_NAV_REGISTRY` exported from `frontend/src/components/layout/LayoutSettings.tsx`. UI-PRD-02 seeds the registry with **Organization → Account → User** in that order; downstream PRDs append their entries (IN-PRD-03 inserts **Integrations**, BL-PRD-04 inserts **Subscription**) without modifying `LayoutSettings` itself. Final v1 row order: Organization / Account / User / Integrations / Subscription.
- Route migration: preserve current backward-compat redirects in `App.tsx`
- Delete the dropped legacy routes + pages listed in §11 Cleanup
- Component tests for every migrated page

### Out of scope
- Changes to Firebase auth logic, email verification flow, or invitation backend
- Changes to settings API endpoints
- Changes to the create-organization form **logic** (data model, API calls, validation rules) — this PRD only re-skins the page
- **`/chat` page, `ChatInterface`, `ThinkingBlock`, `SessionsSidebar`** — owned by **CH-PRD-02** ([chat/projects/CH-PRD-02](../../chat/projects/CH-PRD-02-chat-page-shell-and-sidebar.md)). This PRD does not create any `frontend/src/components/chat/*` files.
- Organization Selection page — owned by **UI-PRD-08** (new `/select-organization` page)
- Integrations settings tab — owned by **IN-PRD-03** (plugs into `SETTINGS_NAV_REGISTRY`)
- Subscription settings tab — owned by **BL-PRD-04** (plugs into `SETTINGS_NAV_REGISTRY`)

### Pages dropped from the product (handled in §11 Cleanup, not redesigned)
- `Home.tsx` — replaced by a `/` → `/chat` redirect; the destination page is owned by CH-PRD-02
- `AdminSettings.tsx`, `AdminIndustryKeywords.tsx`, `AgentConfigManagement.tsx`, `ToolUsageDashboard.tsx` — admin surfaces removed from the product; no redesign
- `Settings.tsx` — old `/settings` hub page; superseded by `LayoutSettings` sub-nav

## 3. Dependencies

- **Canonical reference (`docs/figma-export/`):** the source of truth for every page redesigned by this PRD. Build to match the export exactly. **Do not deviate** — if a deviation seems necessary, raise it as an open question on the Linear issue and wait for explicit approval. Specific paths to read for this PRD:
  - Pages: `docs/figma-export/src/app/pages/` — `Authentication` (sign-in/sign-up/email-verification), `AcceptInvitation`, `AccountSettings`, `UserSettings`, `CreateOrganization` (match by file/route name)
  - Settings layout: `docs/figma-export/src/app/layouts/LayoutSettings*` and the sub-nav structure
  - Tokens & shared components: `docs/figma-export/src/styles/`, `src/app/components/`
  - Design rationale: `docs/figma-export/guidelines/Guidelines.md`, `guidelines/ken-e_design_guidelines.md`
- **UI-PRD-01:** shell tokens, `LayoutSettings`, `LayoutC`, re-skinned shadcn primitives
- **CH-PRD-02 (coordination):** owns the `/chat` route this PRD's `/` redirect points at. CH-PRD-02 must land before or in the same release window as UI-PRD-02 so the redirect resolves to a real page (behind `chat_v2_enabled`). If CH-PRD-02 hasn't shipped yet, the redirect can land first — `/chat` will render the `chat_v2_enabled=false` fallback (a "coming soon" placeholder per CH-PRD-02 §2.1).
- **UI-PRD-08 (coordination):** UI-PRD-08 lands the `<Navigate to="/select-organization">` gate in `ProtectedRoute`. UI-PRD-02 mirrors that pattern for `<Authentication>` (`<Navigate to="/sign-in">`). The two PRDs touch the same `ProtectedRoute.tsx` file; coordinate landing order at PR review.
- **IN-PRD-03, BL-PRD-04 (downstream):** both register entries in `SETTINGS_NAV_REGISTRY` (Integrations and Subscription respectively). UI-PRD-02 freezes the registry shape + helper at merge.
- **Existing files to study:**
  - `frontend/src/pages/Authentication.tsx`, `AcceptInvitation.tsx`, `AccountSettings.tsx`, `UserSettings.tsx`, `CreateOrganization.tsx` (or current path)
  - `frontend/src/contexts/AuthContext.tsx`
  - `frontend/src/components/auth/*`
  - `frontend/src/components/auth/ProtectedRoute.tsx` (for the gating change)
- **Figma nodes:** SignInPage, CreateAccountPage, EmailVerificationPage, InvitationAcceptancePage, OrganizationSettingsPage, AccountSettingsPage, UserSettingsPage

## 4. Data contract (TypeScript)

No new types. Consumed types already defined:
- `AuthContextValue` from `contexts/AuthContext.tsx`

Branded IDs reused from existing code.

## 5. Implementation outline

| Action | File |
|--------|------|
| Modify | `frontend/src/pages/Authentication.tsx` — redesign per Figma SignInPage/CreateAccountPage; route-mounted (no longer inline-rendered by `ProtectedRoute`) |
| Modify | `frontend/src/components/auth/ProtectedRoute.tsx` — replace inline `<Authentication>` render with `<Navigate to="/sign-in" replace />` when unauthenticated (matches UI-PRD-08's pattern) |
| Modify | `frontend/src/pages/AcceptInvitation.tsx` |
| Modify | `frontend/src/pages/AccountSettings.tsx` — recompose into `LayoutSettings` |
| Modify | `frontend/src/pages/UserSettings.tsx` |
| Modify | `frontend/src/pages/CreateOrganization.tsx` (or current path) — re-skin onto Soft Maximalism with the auth-page background treatment; logic preserved |
| Modify | `frontend/src/components/layout/LayoutSettings.tsx` — read rows from `SETTINGS_NAV_REGISTRY`; export the registry constant + a registration helper |
| Modify | `frontend/src/App.tsx` — wrap settings routes in `LayoutSettings`; register `/` as `<Navigate to="/chat" replace />`; register `/settings` as `<Navigate to="/settings/organization" replace />`; register `/sign-in` and `/sign-up` as the canonical auth routes; delete the import + route for the legacy `Home` page |
| Modify | `frontend/src/components/auth/*` — update email action handler and related sub-components for new design |
| Create | colocated `*.test.tsx` for every materially changed component |

### Auth page structure
Sign-in and sign-up share a centered card over `BackgroundEffects`. Password reset, email verification, and invitation acceptance reuse the same card shell. Error / success states use new `Alert` variants from UI-PRD-01.

### Auth route-gating change
The legacy pattern inline-renders `<Authentication onComplete={…}>` from inside `ProtectedRoute` when the user isn't signed in. This PRD switches to a route-based gate: `ProtectedRoute` redirects to `/sign-in` (`<Navigate to="/sign-in" replace />`); the auth pages are normal route components that call the existing auth handlers and then `navigate('/')` on success. Matches UI-PRD-08's `SelectOrganizationPage` gating pattern and makes `/sign-in` / `/sign-up` the canonical entry points instead of URLs that are only reachable by typing them. Backward-compat: `/login` and `/signup` redirect to `/sign-in` and `/sign-up` respectively.

### Settings sub-nav (registry pattern)

`LayoutSettings` exposes a `SETTINGS_NAV_REGISTRY: SettingsNavRow[]` constant + a `registerSettingsNavRow(row)` helper. Each row carries `{ id, label, path, order, isVisible? }`. UI-PRD-02 seeds three rows (Organization / Account / User). Downstream PRDs register their own:

- `IN-PRD-03` registers `{ id: 'integrations', label: 'Integrations', path: '/settings/integrations', order: 40 }`
- `BL-PRD-04` registers `{ id: 'subscription', label: 'Subscription', path: '/settings/subscription', order: 50 }`

`order` values leave gaps (10, 20, 30, 40, 50) for future insertions. `LayoutSettings` reads the registry once at module load and renders rows sorted by `order`. Final v1 row order: Organization (10) / Account (20) / User (30) / Integrations (40) / Subscription (50). Forms use `react-hook-form` + Zod (already in deps). File uploads (logo, avatar) reuse existing upload logic.

### Create Organization page
Re-skin the existing create-organization form onto the auth-page visual treatment (`BackgroundEffects` + centered card). Standalone (no `LayoutC` or `LayoutSettings`). Preserves: Firestore + organization API write logic, validation rules, redirect-on-success to `/select-organization` (or auto-pick the new org if it's the user's only one — existing behavior). Visual parity with `/sign-in`'s card shell.

### Root-route coordination with CH-PRD-02
- UI-PRD-02 registers `/` as `<Navigate to="/chat" replace />` and deletes `Home.tsx`.
- CH-PRD-02 registers the `/chat` route inside `LayoutC` (behind `chat_v2_enabled`).
- The two PRs must merge in either order, but the redirect destination is only useful once CH-PRD-02's route exists. Confirm landing order at PR review.
- The `chat_v2_enabled=false` fallback is owned by CH-PRD-02 — a 404 or "coming soon" placeholder per CH-PRD-02 §2.1.

## 6. API contract

This PRD consumes only existing endpoints — no new contracts.

## 7. Acceptance criteria

1. `/sign-in` and `/sign-up` render the new design; the existing auth flow (Firebase sign-in, sign-up, OTP verification, invitation token handling) works end-to-end. Hitting any protected route while unauthenticated lands the user on `/sign-in` via `ProtectedRoute`'s `<Navigate>` — not via inline render.
2. `/invite/:token` renders the new design and preserves the token-to-account flow.
3. `/settings/organization`, `/settings/account/:accountId`, `/settings/user` render inside `LayoutSettings` with the new left-nav design; forms save and load correctly.
4. `/settings` (no sub-route) renders `<Navigate to="/settings/organization" replace />`.
5. `/create-organization` renders the redesigned page with the auth-page visual treatment; the existing create-organization form logic is preserved (validation rules, API call, success redirect).
6. `/` renders `<Navigate to="/chat" replace />`; `Home.tsx` and its imports are removed; no live references remain.
7. Dark mode renders correctly on every page.
8. Backward-compat route redirects (`/login` → `/sign-in`, `/signup` → `/sign-up`, `/organization-settings`, `/account-settings`, `/user-settings`) still work. (`/organization-selection` is converted to a redirect by **UI-PRD-08**, not this PRD.)
9. `LayoutSettings` reads its sub-nav from `SETTINGS_NAV_REGISTRY`; visiting each registered route highlights the correct row. Adding / removing entries in the registry changes the sub-nav without modifying `LayoutSettings`.
10. **Responsive (per UI-PRD-01 breakpoints):** every page renders correctly at 375 / 768 / 1200 / 1440 / 1920 widths; `LayoutSettings` sub-nav collapses to a top tab strip on mobile.
11. **Canonical-reference parity.** Every page delivered by this PRD matches `docs/figma-export/src/app/pages/<corresponding-path>` in structure, variants, tokens, DOM landmarks, and a11y semantics. Any deviation is documented as an open question on the Linear issue *before* implementation and approved by the PRD owner; un-flagged deviations block the PR.
12. Component tests pass; `npm run typecheck`, `npm run format.fix`, `npm run build`, `npm test` pass.

## 8. Test plan

**Component tests:**
- `Authentication.test.tsx`: sign-in form renders; error alerts surface; OTP flow renders correctly (existing tests preserved and updated for new markup)
- `AcceptInvitation.test.tsx`: token handling preserved
- `AccountSettings.test.tsx` / `UserSettings.test.tsx`: existing tests updated for new layout
- `LayoutSettings.test.tsx`: registry-driven sub-nav renders the seeded rows in `order` order; appending a row via `registerSettingsNavRow` adds it without re-rendering existing rows
- `CreateOrganization.test.tsx`: form renders, validation rules preserved, success path navigates correctly
- `ProtectedRoute.test.tsx`: unauthenticated user is redirected to `/sign-in` (route-based gate), not inline-rendered with `<Authentication>`
- `App.test.tsx` (or routing test): visiting `/` redirects to `/chat`; visiting `/settings` redirects to `/settings/organization`

**Manual smoke:**
- End-to-end sign-in, sign-up, email verification, invitation acceptance (use an existing test account)
- Visit `/`; verify redirect to `/chat`
- Visit `/settings`; verify redirect to `/settings/organization`
- Visit any protected route while signed out; verify redirect to `/sign-in`
- Resize browser through 375 / 768 / 1200 widths on auth pages, settings pages, and `/create-organization`

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| Existing auth tests rely on DOM structure that changes | Update test selectors as part of this PRD; prefer role-based queries |
| `/` redirect lands before CH-PRD-02's destination is ready | Acceptable — CH-PRD-02's `chat_v2_enabled=false` fallback (coming-soon placeholder) handles the gap. Confirm at code review. |
| Settings form validation rules differ between old and new design | Preserve current Zod schemas; only change layout/styling |
| Lingering imports of `Home` from other tests / components | Grep `frontend/src` for `Home` and `pages/Home`; remove all references in the same PR |

### Open questions

- None remain. The Home/Chat handoff is resolved (UI-PRD-02 owns the redirect; CH-PRD-02 owns the destination).

## 10. Reference

- Parent component: [`../README.md`](../README.md)
- Sibling: [`UI-PRD-01-design-system-foundation.md`](./UI-PRD-01-design-system-foundation.md)
- **Sibling component (coordination):** [`../../chat/projects/CH-PRD-02-chat-page-shell-and-sidebar.md`](../../chat/projects/CH-PRD-02-chat-page-shell-and-sidebar.md) — owns the `/chat` destination this PRD's `/` redirect points at.
- Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) — SignInPage, CreateAccountPage, EmailVerificationPage, InvitationAcceptancePage, OrganizationSettingsPage, AccountSettingsPage, UserSettingsPage
- Existing files: `frontend/src/pages/Authentication.tsx`, `AccountSettings.tsx`, `UserSettings.tsx`, `AcceptInvitation.tsx`; `frontend/src/contexts/AuthContext.tsx`
- `frontend/CLAUDE.md` — Authentication State, CSS architecture
- CLAUDE.md rules in scope: C-5, C-6, C-8; T-2; G-2, G-3

## 11. Cleanup — legacy pages deleted by this PRD

The following files are removed as part of this PRD. Each is either absorbed by a new surface (the `LayoutSettings` sub-nav, or the Chat component for `Home`'s former `/` slot) or dropped from the product. Any lingering route references in `App.tsx`, sidebar nav, or tests must be removed in the same PR.

| File | Route(s) | Replaced by / reason |
|------|----------|----------------------|
| `frontend/src/pages/Home.tsx` | `/` | `/` is now `<Navigate to="/chat" replace />`. The `/chat` destination is owned by **CH-PRD-02** (Chat component). |
| `frontend/src/pages/Settings.tsx` | `/settings` | `/settings` becomes `<Navigate to="/settings/organization" replace />`; the `LayoutSettings` sub-nav supplies the hub UX. |
| `frontend/src/pages/AdminSettings.tsx` | `/settings/admin` | Dropped — per-account admin toggles removed from the product. (Note: a separate platform-level super-admin section in the `Sidebar` is reserved by **UI-PRD-01** for future admin tooling like FF-PRD-02's `/admin/feature-flags` — different scope.) |
| `frontend/src/pages/AdminIndustryKeywords.tsx` | `/settings/admin/industry-keywords` | Dropped |
| `frontend/src/pages/AgentConfigManagement.tsx` | `/settings/admin/agent-configs` | Dropped — admin surface removed; agent configuration will be authored via the Workflows > Agents UI (AH-PRD-02) |
| `frontend/src/pages/ToolUsageDashboard.tsx` | `/settings/admin/tool-usage` | Dropped |

`frontend/src/pages/OrganizationSelection.tsx` and its route are deleted by **UI-PRD-08**, not this PRD.

Post-cleanup checks:
- `grep -r "Home\|AdminSettings\|AdminIndustryKeywords\|AgentConfigManagement\|ToolUsageDashboard\|pages/Settings" frontend/src` returns only legitimate matches (e.g., `LayoutSettings` unrelated to the old `Settings.tsx` hub)
- `App.tsx` no longer imports or routes to any deleted page; `/` route is the redirect
- `Sidebar.tsx` has no nav entries pointing to deleted routes
- Associated `*.test.tsx` files for deleted pages are also deleted
