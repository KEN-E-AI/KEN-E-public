# UI-PRD-08 — Organization Selection Page

**Status:** Blocked on UI-PRD-01
**Owner team:** Frontend
**Blocked by:** UI-PRD-01
**Parallel with:** UI-PRD-02, UI-PRD-03, UI-PRD-06
**Estimated effort:** 3–4 days

---

## 1. Context

Today, a user who signs in and belongs to more than one organization (or has access to an agency → child-org → account tree, or is a super-admin) lands on `frontend/src/pages/OrganizationSelection.tsx` before the rest of the app becomes routable. That page is styled with the old brand palette and has no Figma-designed counterpart in the current Soft Maximalism export.

This PRD ships the redesigned `/select-organization` page — the first screen a user sees after authentication — rebuilt against the Soft Maximalism tokens, the `BackgroundEffects` treatment already used on the auth pages, and the new `Logo` / `Button` / `Card` primitives re-skinned by UI-PRD-01.

**Scope boundary:** all data-layer behaviour in the existing page is preserved verbatim — `AuthContext` bindings (`setSelectedOrgAccount`, `completeWorkspaceSelection`, `setCurrentOrganization`, `setOrgMetadata`, `setAccountMetadata`), the super-admin-fetches-all-orgs branch, agency → child-org → account drill-down, single-account auto-select + auto-navigate, and the "no orgs → redirect to `/create-organization`" fallback. This PRD re-skins the UI and re-homes the route.

## 2. Scope

### In scope
- New route `/select-organization` registered in `frontend/src/App.tsx` — protected (requires Firebase auth), standalone (no `LayoutC` / `LayoutSettings` wrapper, same pattern as `/auth/signin`)
- New page component `frontend/src/pages/SelectOrganizationPage.tsx` implementing the Soft Maximalism design
- Two-column card layout: **Organizations** (left) → **Accounts** (right) with agency → child-org → account drill-down inside the right card when the selected org is an agency
- Client-side search/filter `<Input>` above the organization list (case-insensitive substring match on `organization_name`) — visible whenever the list contains more than 5 orgs; always visible for super-admins
- Gating change: `frontend/src/components/auth/ProtectedRoute.tsx` — switch from the current inline-mount pattern (renders `<OrganizationSelection>` when `!hasSelectedWorkspace`) to a route-based gate (`<Navigate to="/select-organization" replace />` when `!hasSelectedWorkspace`). This matches the auth-page precedent (`<Authentication>` will similarly become `<Navigate to="/sign-in">` under UI-PRD-02) and makes `/select-organization` the single canonical entry point instead of a URL that's only reachable by typing it.
- `BackgroundEffects` + violet/blue/teal blob gradient treatment consistent with the auth pages
- Super-admin branch preserved (fetches every organization instead of only the user's permissioned ones)
- Single-account auto-select + auto-navigate behaviour preserved
- "Create new organization" secondary CTA → `navigate('/create-organization')`
- "Create new account" secondary CTA → `navigate('/settings/organization?openCreateAccount=true')` (same handshake as today)
- "Organization settings" icon button on each org card → `navigate('/settings/organization')` (same handshake as today)
- Continue button disabled until a valid (org, account) pair (and child-org, if agency) is selected; on click, calls the existing `resolveOrganizationAndAccount` + `formatWorkspaceMetadata` + `completeWorkspaceSelection` path and then `navigate('/')` (which now renders `ChatPage`)
- Loading state and "error loading organization" badge preserved
- Dark-mode support via `ThemeProvider`
- Component tests

### Out of scope
- Changes to `AuthContext`, the `users/{uid}.permissions` Firestore read, or the batch `getOrganizationsBatch` API client
- Changes to the "create organization" form itself (owned by UI-PRD-02's `AccountSettings` redesign; this PRD only links to it)
- Changes to the invitation-acceptance flow (UI-PRD-02 owns `/accept-invitation`)
- Any backend / API change

## 3. Dependencies

- **UI-PRD-01:** `BackgroundEffects`, `ThemeProvider`, re-skinned `Card`/`Button`/`Badge`/`Input`/`Select`/`Dialog`, Soft Maximalism tokens in `index.css`
- **Existing files to preserve verbatim:**
  - `frontend/src/contexts/AuthContext.tsx` — all hooks + setters consumed by this page
  - `frontend/src/data/organizationApi.ts` — `getOrganizations`, `getOrganizationsBatch`, `getChildOrganizations`
  - `frontend/src/hooks/useChildOrganizations.ts`, `frontend/src/hooks/useAvailableAccounts.ts`
  - `frontend/src/lib/organizationUtils.ts` — `resolveOrganizationAndAccount`, `formatWorkspaceMetadata`, `getTargetOrganizationId`, `validateAccountCreationRequirements`
  - `frontend/src/constants/organizationSelection.ts`
- **Figma:** no existing export — this PRD is the first to author the design. Design decisions below; update once Figma adds a matching node.

## 4. Data contract (TypeScript)

No new types. Types consumed (all existing):
- `OrganizationId`, `AccountId` (branded) from `frontend/src/lib/branded-types.ts`
- `AuthContextValue` from `contexts/AuthContext.tsx`
- `Organization`, `Account`, `ChildOrganization` shapes from `data/organizationApi.ts`

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `frontend/src/pages/SelectOrganizationPage.tsx` — redesigned page, logic ported verbatim from current `OrganizationSelection.tsx` |
| Modify | `frontend/src/App.tsx` — register `/select-organization` as a protected standalone route; replace the legacy `/organization-selection` route with `<Navigate to="/select-organization" replace />` for backward compat |
| Modify | `frontend/src/components/auth/ProtectedRoute.tsx` — replace the current inline `<OrganizationSelection onComplete={…} />` render (lines 38–47) with `<Navigate to="/select-organization" replace />` when `!hasSelectedWorkspace`. The page itself is responsible for calling `completeWorkspaceSelection()` and then `navigate('/')` on a valid selection — `ProtectedRoute` no longer passes an `onComplete` callback. Zero-orgs branch stays inside `SelectOrganizationPage` (it redirects to `/create-organization` on mount when appropriate). |
| Delete | `frontend/src/pages/OrganizationSelection.tsx` (after `/select-organization` is live and tested) |
| Delete | Associated legacy test file(s) under `frontend/src/pages/OrganizationSelection*.test.tsx` if present |
| Create | `frontend/src/pages/SelectOrganizationPage.test.tsx` — colocated component tests |

### Page structure

Standalone page (no shell). Composition:

```
<BackgroundEffects />
<div center-vertical center-horizontal>
  <header> Logo + "Choose a workspace" + subtitle </header>
  <rainbow-accent-bar />
  <main two-col-grid>
    <Card title="Organizations">
      list of orgs (click to select; settings-icon button on hover)
      "+ Create new organization"
    </Card>
    <Card title="Accounts">
      if agency selected → nested child-org list → then account list
      else → flat account list
      "+ Create new account"
      empty state if no org selected
    </Card>
  </main>
  <Button primary "Continue →" disabled={!complete} />
  <footer> "Need help? Contact Support" </footer>
</div>
```

### Visual treatment (match the auth pages for continuity)
- Same violet → blue → teal gradient background with animated blobs
- Same `BackgroundEffects` + grain overlay
- Rainbow accent bar (4-color gradient) below the header, mirroring `SignInPage`
- Logo floats with `animate-logo-float`
- Cards use `bg-card` / `border-[var(--color-border-default)]` / `rounded-[var(--radius-lg)]` / `shadow-lg`
- Selection state uses `border-[var(--color-violet-500)]` + subtle violet tint
- Check-mark icon on selected row
- Continue button: primary coral `#F97066` with hover lift, matching the sign-in page's primary button

### Behavioural preservation checklist
- [ ] Super-admin: `isSuperAdmin` → fetch `getOrganizations()` all, permission = `"admin"`
- [ ] Non-super-admin: fetch `users/{uid}.permissions.organizations`
- [ ] If `Object.keys(orgsFromFirestore).length === 0 && !isSuperAdmin` → `navigate('/create-organization')`
- [ ] Batch-fetch org metadata via `getOrganizationsBatch(orgIds, true)`; skip deleted orgs with warning
- [ ] Agency org selected → `fetchChildOrganizations(orgId)`, then require child-org selection before accounts list
- [ ] If exactly one total account across all orgs → auto-select + `completeWorkspaceSelection()` + `navigate('/')` after 500ms
- [ ] Continue button: debounced (~500ms loading spinner) then `setSelectedOrgAccount` + `setCurrentOrganization` + `completeWorkspaceSelection()` + `navigate('/')`
- [ ] Organization gear icon → `setSelectedOrgAccount` with first account + `completeWorkspaceSelection()` + `navigate('/settings/organization')`
- [ ] "+ Create new account" → `setCurrentOrganization` + `completeWorkspaceSelection()` + `navigate('/settings/organization?openCreateAccount=true')`
- [ ] Error state: orgs with `metadata.error === true` render an `Error Loading` destructive badge but remain selectable (matches today)

## 6. API contract

No new endpoints. Consumes existing endpoints via `frontend/src/data/organizationApi.ts`:
- `GET /api/v1/firestore/documents/users/{uid}` (via axios, preserved)
- `GET /api/v1/organizations` (super-admin branch)
- `POST /api/v1/organizations/batch` (batch metadata fetch)
- `GET /api/v1/organizations/{orgId}/children` (agency drill-down)

## 7. Acceptance criteria

1. A signed-in user with ≥ 2 organizations, or an agency org, or super-admin status, lands on `/select-organization` after sign-in. Users with no selected workspace hitting any protected route are redirected to `/select-organization` by `ProtectedRoute` (route-based gate), not the legacy inline mount.
2. The legacy path `/organization-selection` renders `<Navigate to="/select-organization" replace />` so existing bookmarks / deep-links resolve to the new page. (Client-side redirect; no HTTP 301 involved — this is an SPA.)
3. Design matches Soft Maximalism: same background, logo, rainbow accent, card styling, and primary button treatment as `/sign-in`.
4. Selecting an org + account + clicking Continue calls the existing workspace-selection path and lands on `/` (ChatPage).
5. Super-admin branch: all organizations in the system are listed.
6. Agency branch: selecting an agency org reveals its child-org list; selecting a child reveals its accounts.
7. Single-account auto-select still works: user with exactly one account is auto-routed to `/` without clicking Continue.
8. Zero-orgs case: user with no org permissions (and not super-admin) is redirected to `/create-organization`.
9. Dark mode renders correctly.
10. Legacy file `frontend/src/pages/OrganizationSelection.tsx` is deleted; `App.tsx` no longer references it.
11. `npm run typecheck`, `npm run format.fix`, `npm run build`, `npm test` pass.

## 8. Test plan

**Component tests (`SelectOrganizationPage.test.tsx`):**
- Renders a list of organizations from `useAuth()` + `useOrgMetadata`
- Clicking an org populates the Accounts card
- Clicking an agency org reveals child-orgs; selecting a child then shows that child's accounts
- Super-admin user: mock `isSuperAdmin=true` → all orgs rendered with `"admin"` permission
- Zero orgs, non-super-admin → `navigate('/create-organization')` called
- Exactly one account total → auto-select + `navigate('/')` called after the delay
- Continue button disabled until (org, account) [and child-org if agency] are selected
- Gear icon click routes to `/settings/organization` with correct context populated
- "+ Create account" click routes to `/settings/organization?openCreateAccount=true`

**Manual smoke:**
- End-to-end sign-in → land on `/select-organization` for a multi-org test user
- Switch themes mid-selection
- Resize browser (1280 / 1440 / mobile)
- Verify deep-link `/organization-selection` still routes to the new page

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| `ProtectedRoute` redirect logic may already direct to `/organization-selection` from multiple call sites | Grep `frontend/src` for `organization-selection` before merge; update every reference in the same PR |
| Single-account auto-select races with the Continue button (double-fire) | Preserve current ref-guard pattern (`lastRefreshTime`, `isFetchingRef`); unit-test the race |
| Figma has no exported node for this page yet | Draft the visual treatment in this PRD, ship it, then back-fill Figma from the implementation — noted in DESIGN-REVIEW-LOG |
| Super-admin branch may surface hundreds of orgs | Add client-side search-by-name input above the org list if the list exceeds ~20; otherwise virtualise with the existing `react-window` if already in deps |

### Open questions

- **Q:** Should we add a "Recently used" section at the top of the org list? → **Defer** — not in scope for the migration; open a follow-up issue.
- **Q:** Should the search filter support fuzzy / typo-tolerant matching in addition to substring? → **Defer** — substring-only in v1; revisit if super-admins report it's painful.

## 10. Reference

- Parent component: [`../README.md`](../README.md)
- Siblings: [`UI-PRD-01-design-system-foundation.md`](./UI-PRD-01-design-system-foundation.md), [`UI-PRD-02-core-shell-pages.md`](./UI-PRD-02-core-shell-pages.md)
- Existing files: `frontend/src/pages/OrganizationSelection.tsx`, `frontend/src/contexts/AuthContext.tsx`, `frontend/src/data/organizationApi.ts`, `frontend/src/hooks/useChildOrganizations.ts`, `frontend/src/hooks/useAvailableAccounts.ts`, `frontend/src/lib/organizationUtils.ts`, `frontend/src/constants/organizationSelection.ts`
- Figma: node TBD — design spec lives in §5 of this PRD until Figma catches up
- `frontend/CLAUDE.md` — Authentication State, Layout Troubleshooting
- CLAUDE.md rules in scope: C-5, C-6, C-8; T-2; G-2, G-3
