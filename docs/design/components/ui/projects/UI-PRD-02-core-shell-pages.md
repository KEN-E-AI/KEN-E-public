# UI-PRD-02 — Core Shell Pages: Auth, Settings, Chat

**Status:** Blocked on UI-PRD-01
**Owner team:** Frontend
**Blocked by:** UI-PRD-01
**Parallel with:** UI-PRD-03, UI-PRD-06, UI-PRD-07
**Estimated effort:** 7–9 days

---

## 1. Context

The authentication, settings, and chat pages are the "day one" surfaces every user touches. Authentication and settings already exist but use the old design system; Chat is new (today KEN-E has a `ChatContext` and ad-hoc chat components, but no dedicated `/chat` page). This PRD redesigns the existing pages onto `LayoutSettings` + the new Soft Maximalism tokens and builds the `/chat` page per Figma.

**Scope boundary:** data wiring for authentication (Firebase Auth) and settings endpoints is preserved as-is — this PRD re-skins the existing logic. Chat page consumes the existing `/api/v1/chat` endpoint via the existing `ChatContext`; no new data layer.

## 2. Scope

### In scope
- Redesign `Authentication.tsx` (sign-in, sign-up, email verification, invitation acceptance flows) onto the new design
- Redesign `AccountSettings.tsx` (organization + account settings) onto `LayoutSettings`
- Redesign `UserSettings.tsx` onto `LayoutSettings`
- Redesign `AcceptInvitation.tsx` onto the auth layout
- New `/chat` route and `ChatPage` with full conversational UI (`ChatInterface`, `ThinkingBlock`, `SessionsSidebar`)
- Wire `SessionsSidebar` to the existing `ChatContext` session list
- Route migration: preserve current backward-compat redirects in `App.tsx`
- Component tests for every migrated page and the new chat components

### Out of scope
- Changes to Firebase auth logic, email verification flow, or invitation backend
- Changes to settings API endpoints
- Changes to the chat endpoint or agent behavior — UI-only
- AdminSettings / AdminIndustryKeywords / AgentConfigManagement / ToolUsageDashboard — admin-only pages deferred to a follow-up
- Organization Selection page — deferred (not in the current Figma set)

## 3. Dependencies

- **UI-PRD-01:** shell tokens, `LayoutSettings`, `LayoutC`, re-skinned shadcn primitives
- **Existing files to study:**
  - `frontend/src/pages/Authentication.tsx`, `AcceptInvitation.tsx`, `AccountSettings.tsx`, `UserSettings.tsx`
  - `frontend/src/contexts/AuthContext.tsx`, `ChatContext.tsx`
  - `frontend/src/components/auth/*`
  - Existing chat components (search for `Chat` under `frontend/src/components/`)
- **Figma nodes:** SignInPage, CreateAccountPage, EmailVerificationPage, InvitationAcceptancePage, OrganizationSettingsPage, AccountSettingsPage, UserSettingsPage, ChatPage

## 4. Data contract (TypeScript)

No new types. Consumed types already defined:
- `AuthContextValue` from `contexts/AuthContext.tsx`
- `ChatContextValue` from `contexts/ChatContext.tsx`

Branded IDs reused from existing code.

## 5. Implementation outline

| Action | File |
|--------|------|
| Modify | `frontend/src/pages/Authentication.tsx` — redesign per Figma SignInPage/CreateAccountPage |
| Modify | `frontend/src/pages/AcceptInvitation.tsx` |
| Modify | `frontend/src/pages/AccountSettings.tsx` — recompose into `LayoutSettings` |
| Modify | `frontend/src/pages/UserSettings.tsx` |
| Create | `frontend/src/pages/ChatPage.tsx` |
| Create | `frontend/src/components/chat/ChatInterface.tsx` |
| Create | `frontend/src/components/chat/ThinkingBlock.tsx` |
| Create | `frontend/src/components/chat/MessageList.tsx` |
| Create | `frontend/src/components/chat/MessageComposer.tsx` |
| Create | `frontend/src/components/chat/IntegrationIcon.tsx` |
| Modify | `frontend/src/components/layout/SessionsSidebar.tsx` — wire to `ChatContext` session list |
| Modify | `frontend/src/App.tsx` — add `/chat` route wrapped in `LayoutC`; wrap settings routes in `LayoutSettings` |
| Modify | `frontend/src/components/auth/*` — update email action handler and related sub-components for new design |
| Create | colocated `*.test.tsx` for every new or materially changed component |

### Auth page structure
Sign-in and sign-up share a centered card over `BackgroundEffects`. Password reset, email verification, and invitation acceptance reuse the same card shell. Error / success states use new `Alert` variants from UI-PRD-01.

### Settings page structure
`LayoutSettings` provides a secondary left nav with three rows: Organization, Account, User. Each row is a route. Forms use `react-hook-form` + Zod (already in deps). File uploads (logo, avatar) reuse existing upload logic.

### Chat page structure
- `SessionsSidebar` (left): list of past sessions, "New chat" button at top. Reads from `ChatContext`.
- `ChatInterface` (center): message list (infinite scroll up), `ThinkingBlock` for agent reasoning steps, composer at the bottom.
- `IntegrationIcon` inline to indicate which MCP integration a message used.
- Markdown rendering preserved from existing chat (react-markdown with `<Link>` override for in-app nav).

## 6. API contract

This PRD consumes only existing endpoints — no new contracts.

## 7. Acceptance criteria

1. `/auth/signin` and `/auth/signup` render the new design; the existing auth flow (Firebase sign-in, sign-up, OTP verification, invitation token handling) works end-to-end.
2. `/invite/:token` renders the new design and preserves the token-to-account flow.
3. `/settings/organization`, `/settings/account/:accountId`, `/settings/user` render inside `LayoutSettings` with the new left-nav design; forms save and load correctly.
4. `/chat` route exists, is protected, wraps in `LayoutC`, and renders the three-column chat layout.
5. Submitting a message in the composer streams through the existing chat endpoint and renders the response with `ThinkingBlock` for agent reasoning steps.
6. Session switch via `SessionsSidebar` loads the selected session's messages.
7. Dark mode renders correctly on every page.
8. Backward-compat route redirects (`/login`, `/signup`, `/organization-settings`, `/account-settings`, `/user-settings`) still work.
9. Component tests pass; `npm run typecheck`, `npm run format.fix`, `npm run build`, `npm test` pass.

## 8. Test plan

**Component tests:**
- `Authentication.test.tsx`: sign-in form renders; error alerts surface; OTP flow renders correctly (existing tests preserved and updated for new markup)
- `AcceptInvitation.test.tsx`: token handling preserved
- `AccountSettings.test.tsx` / `UserSettings.test.tsx`: existing tests updated for new layout
- `ChatPage.test.tsx`: renders three columns; new-chat button creates a session; message composer submits
- `ChatInterface.test.tsx`: message list scroll behavior, `ThinkingBlock` collapses/expands
- `SessionsSidebar.test.tsx`: renders sessions from context; clicking switches active session

**Manual smoke:**
- End-to-end sign-in, sign-up, email verification, invitation acceptance (use an existing test account)
- Create a chat session, send a message, switch sessions, refresh the page

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| Existing auth tests rely on DOM structure that changes | Update test selectors as part of this PRD; prefer role-based queries |
| Chat page conflicts with existing chat UI used on Home | Migrate existing chat usage to new components inline with this PRD, or leave Home's chat widget untouched (acceptable — Home is not in this PRD's scope) |
| `ThinkingBlock` rendering depends on agent event structure not yet finalized by AH-PRD-02 | Render best-effort from existing event schema; leave an extension point for new event types |
| Settings form validation rules differ between old and new design | Preserve current Zod schemas; only change layout/styling |

### Open questions

- **Q:** Does Home (`/`) remain as a landing page or get replaced by Chat? → **Assumption:** Home remains unchanged in this PRD; a follow-up can decide redirect behavior.
- **Q:** Does the chat page support artifact rendering (Vega-Lite viz)? → **Defer** to a future PRD tied to the data-visualization design doc.

## 10. Reference

- Parent component: [`../README.md`](../README.md)
- Sibling: [`UI-PRD-01-design-system-foundation.md`](./UI-PRD-01-design-system-foundation.md)
- Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) — SignInPage, CreateAccountPage, EmailVerificationPage, InvitationAcceptancePage, OrganizationSettingsPage, AccountSettingsPage, UserSettingsPage, ChatPage
- Existing files: `frontend/src/pages/Authentication.tsx`, `AccountSettings.tsx`, `UserSettings.tsx`, `AcceptInvitation.tsx`; `frontend/src/contexts/AuthContext.tsx`, `ChatContext.tsx`
- `frontend/CLAUDE.md` — Authentication State, CSS architecture
- CLAUDE.md rules in scope: C-5, C-6, C-8; T-2; G-2, G-3
