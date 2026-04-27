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
- Redesign `AccountSettings.tsx` (organization + account settings) onto `LayoutSettings`
- Redesign `UserSettings.tsx` onto `LayoutSettings`
- Redesign `AcceptInvitation.tsx` onto the auth layout
- Delete the legacy `Home.tsx` and register `/` as `<Navigate to="/chat" replace />` (the destination is owned by CH-PRD-02 behind the `chat_v2_enabled` flag — see §11 Cleanup and the coordination note in this PRD's Reference section)
- Route migration: preserve current backward-compat redirects in `App.tsx`
- Delete the dropped legacy routes + pages listed in §11 Cleanup
- Component tests for every migrated page

### Out of scope
- Changes to Firebase auth logic, email verification flow, or invitation backend
- Changes to settings API endpoints
- **`/chat` page, `ChatInterface`, `ThinkingBlock`, `SessionsSidebar`** — owned by **CH-PRD-02** ([chat/projects/CH-PRD-02](../../chat/projects/CH-PRD-02-chat-page-shell-and-sidebar.md)). This PRD does not create any `frontend/src/components/chat/*` files.
- Organization Selection page — owned by **UI-PRD-08** (new `/select-organization` page)

### Pages dropped from the product (handled in §11 Cleanup, not redesigned)
- `Home.tsx` — replaced by a `/` → `/chat` redirect; the destination page is owned by CH-PRD-02
- `AdminSettings.tsx`, `AdminIndustryKeywords.tsx`, `AgentConfigManagement.tsx`, `ToolUsageDashboard.tsx` — admin surfaces removed from the product; no redesign
- `Settings.tsx` — old `/settings` hub page; superseded by `LayoutSettings` sub-nav

## 3. Dependencies

- **UI-PRD-01:** shell tokens, `LayoutSettings`, `LayoutC`, re-skinned shadcn primitives
- **CH-PRD-02 (coordination):** owns the `/chat` route this PRD's `/` redirect points at. CH-PRD-02 must land before or in the same release window as UI-PRD-02 so the redirect resolves to a real page (behind `chat_v2_enabled`). If CH-PRD-02 hasn't shipped yet, the redirect can land first — `/chat` will render the `chat_v2_enabled=false` fallback (a "coming soon" placeholder per CH-PRD-02 §2.1).
- **Existing files to study:**
  - `frontend/src/pages/Authentication.tsx`, `AcceptInvitation.tsx`, `AccountSettings.tsx`, `UserSettings.tsx`
  - `frontend/src/contexts/AuthContext.tsx`
  - `frontend/src/components/auth/*`
- **Figma nodes:** SignInPage, CreateAccountPage, EmailVerificationPage, InvitationAcceptancePage, OrganizationSettingsPage, AccountSettingsPage, UserSettingsPage

## 4. Data contract (TypeScript)

No new types. Consumed types already defined:
- `AuthContextValue` from `contexts/AuthContext.tsx`

Branded IDs reused from existing code.

## 5. Implementation outline

| Action | File |
|--------|------|
| Modify | `frontend/src/pages/Authentication.tsx` — redesign per Figma SignInPage/CreateAccountPage |
| Modify | `frontend/src/pages/AcceptInvitation.tsx` |
| Modify | `frontend/src/pages/AccountSettings.tsx` — recompose into `LayoutSettings` |
| Modify | `frontend/src/pages/UserSettings.tsx` |
| Modify | `frontend/src/App.tsx` — wrap settings routes in `LayoutSettings`; register `/` as `<Navigate to="/chat" replace />`; delete the import + route for the legacy `Home` page |
| Modify | `frontend/src/components/auth/*` — update email action handler and related sub-components for new design |
| Create | colocated `*.test.tsx` for every materially changed component |

### Auth page structure
Sign-in and sign-up share a centered card over `BackgroundEffects`. Password reset, email verification, and invitation acceptance reuse the same card shell. Error / success states use new `Alert` variants from UI-PRD-01.

### Settings page structure
`LayoutSettings` provides a secondary left nav with three rows: Organization, Account, User. Each row is a route. Forms use `react-hook-form` + Zod (already in deps). File uploads (logo, avatar) reuse existing upload logic.

### Root-route coordination with CH-PRD-02
- UI-PRD-02 registers `/` as `<Navigate to="/chat" replace />` and deletes `Home.tsx`.
- CH-PRD-02 registers the `/chat` route inside `LayoutC` (behind `chat_v2_enabled`).
- The two PRs must merge in either order, but the redirect destination is only useful once CH-PRD-02's route exists. Confirm landing order at PR review.
- The `chat_v2_enabled=false` fallback is owned by CH-PRD-02 — a 404 or "coming soon" placeholder per CH-PRD-02 §2.1.

## 6. API contract

This PRD consumes only existing endpoints — no new contracts.

## 7. Acceptance criteria

1. `/auth/signin` and `/auth/signup` render the new design; the existing auth flow (Firebase sign-in, sign-up, OTP verification, invitation token handling) works end-to-end.
2. `/invite/:token` renders the new design and preserves the token-to-account flow.
3. `/settings/organization`, `/settings/account/:accountId`, `/settings/user` render inside `LayoutSettings` with the new left-nav design; forms save and load correctly.
4. `/` renders `<Navigate to="/chat" replace />`; `Home.tsx` and its imports are removed; no live references remain.
5. Dark mode renders correctly on every page.
6. Backward-compat route redirects (`/login`, `/signup`, `/organization-settings`, `/account-settings`, `/user-settings`) still work.
7. Component tests pass; `npm run typecheck`, `npm run format.fix`, `npm run build`, `npm test` pass.

## 8. Test plan

**Component tests:**
- `Authentication.test.tsx`: sign-in form renders; error alerts surface; OTP flow renders correctly (existing tests preserved and updated for new markup)
- `AcceptInvitation.test.tsx`: token handling preserved
- `AccountSettings.test.tsx` / `UserSettings.test.tsx`: existing tests updated for new layout
- `App.test.tsx` (or routing test): visiting `/` redirects to `/chat`

**Manual smoke:**
- End-to-end sign-in, sign-up, email verification, invitation acceptance (use an existing test account)
- Visit `/`; verify redirect to `/chat`

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
| `frontend/src/pages/Settings.tsx` | `/settings` | `LayoutSettings` sub-nav — no hub page needed |
| `frontend/src/pages/AdminSettings.tsx` | `/settings/admin` | Dropped — admin surface removed from the product |
| `frontend/src/pages/AdminIndustryKeywords.tsx` | `/settings/admin/industry-keywords` | Dropped |
| `frontend/src/pages/AgentConfigManagement.tsx` | `/settings/admin/agent-configs` | Dropped — admin surface removed; agent configuration will be authored via the Workflows > Agents UI (AH-PRD-02) |
| `frontend/src/pages/ToolUsageDashboard.tsx` | `/settings/admin/tool-usage` | Dropped |

`frontend/src/pages/OrganizationSelection.tsx` and its route are deleted by **UI-PRD-08**, not this PRD.

Post-cleanup checks:
- `grep -r "Home\|AdminSettings\|AdminIndustryKeywords\|AgentConfigManagement\|ToolUsageDashboard\|pages/Settings" frontend/src` returns only legitimate matches (e.g., `LayoutSettings` unrelated to the old `Settings.tsx` hub)
- `App.tsx` no longer imports or routes to any deleted page; `/` route is the redirect
- `Sidebar.tsx` has no nav entries pointing to deleted routes
- Associated `*.test.tsx` files for deleted pages are also deleted
