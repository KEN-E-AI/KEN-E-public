# IN-PRD-03 — Connection-Management UI

**Status:** Not started
**Owner team:** Integrations component team (frontend + thin backend)
**Blocked by:** [IN-PRD-02](./IN-PRD-02-google-oauth-flow.md) (at least one real platform to connect); [UI-PRD-01](../../ui/projects/UI-PRD-01-design-system-foundation.md) (design system + LayoutSettings shell)
**Parallel with:** [IN-PRD-04](./IN-PRD-04-meta-mailchimp-platforms.md) — IN-PRD-04 adds platforms that automatically appear in this UI once their feature flags are on
**Blocks:** [IN-PRD-05](./IN-PRD-05-reauth-lifecycle.md) (re-auth flow lands on this page); [DP-PRD-04](../../data-pipeline/projects/DP-PRD-04-frontend-and-custom-jobs.md) (custom-job authoring uses the connection picker); [PE-PRD-05](../../performance/projects/PE-PRD-05-setup-wizard.md) (setup wizard links to this page for missing connections)
**Estimated effort:** 3 days frontend + 0.5 day backend management endpoints

---

## 1. Context

IN-PRD-02 lights up Google OAuth; users can connect via direct API calls, but there's no UI. This project delivers the Integrations tab of the Settings page — a single-stop console where users see every available platform, their connection status, who connected each one, when it was last used, and what scopes were granted. From here a user connects, disconnects, force-refreshes (admin), and views the lifecycle audit log.

The connection card shows the **display name of the user who connected the integration** (resolved from `PlatformConnection.connected_by_user_id`). This was an explicit product decision — marketing teams want visibility into who wired up each connection, even though the connection itself is account-scoped and shared across users. The audit log drawer covers deeper history.

The page also handles the re-auth deep-link target: when IN-PRD-05 emits a "Connection Needs Re-auth" notification, clicking it deep-links to `/settings/integrations/{connection_id}`, which scrolls to the relevant card with a prominent "Reconnect" CTA.

## 2. Scope

### In scope
- **Settings → Integrations tab** — new tab on the existing Settings page shell (from UI-PRD-01's `LayoutSettings`). Route: `/settings/integrations`, optional `/settings/integrations/:connection_id` for deep-linking.
- **Platform grid** — one card per platform definition where the platform's feature flag is on. Each card shows:
  - Platform logo + display name (from `PlatformDefinition`).
  - Connection status badge: `Connected` (green), `Expired` (amber), `Revoked` (grey), `Error` (red), `Not connected` (neutral).
  - When connected: the display name of the user who connected it (resolved by the management endpoint; see §5.3), `connected_at` / `last_used_at` timestamps, scope chips, `external_account_label` (e.g., "GA4: ken-e.com").
  - Primary action: **Connect** (not-connected), **Reconnect** (expired/revoked/error — account-admin only for reconnect of others' connections; any member for reconnect of their own), **Disconnect** (connected — account-admin only).
  - Overflow menu: **Force refresh** (account-admin only, admin-troubleshooting tool), **View audit log**.
- **Connect flow** — button calls `POST /initiate`, opens the returned `authorization_url` in a new window, listens for the callback redirect to our origin, and refreshes the card state on completion. Shows a spinner during the round-trip. On health-check failure from IN-PRD-02, surfaces the 400 error message inline.
- **Disconnect confirmation dialog** — lists downstream consumers that will break (see §5.4): "Disconnecting Google will pause these automations: [list]. Scheduled GA data-pipeline jobs will fail until someone reconnects." Explicit "I understand, disconnect" confirmation.
- **Audit-log drawer** — slide-out panel listing `ConnectionAuditEntry` rows filtered to the connection, most-recent first, with `event`, `actor_name` (resolved from `actor_id`), `timestamp`, and expandable `metadata`. Paginated at 50/page.
- **Deep-link behavior** — visiting `/settings/integrations/:connection_id` scrolls the matching card into view, highlights it with a pulse animation, and if the connection is in a non-connected state, auto-opens the Reconnect CTA.
- **Empty state** — before any integration is connected, show a centered card with short copy + link to the `/performance/setup` wizard (which IN-PRD-02 / PE-PRD-05 rely on).
- **Typed API client** — `frontend/src/app/lib/api/integrations.ts` with branded `ConnectionId`, `PlatformId`, typed query/mutation hooks.
- **Management endpoints** — thin backend additions exposing data the UI needs (see §6). The internal credential-read, initiate, callback, revoke, and force-refresh routes already exist from IN-PRD-01/02.
- **Authorization** — reuse existing role gates: any account member can connect a new platform or reconnect a connection they originally authored; account-admin required to disconnect, force-refresh, or reconnect a connection authored by someone else.
- **Feature flag** — `integrations_ui_enabled` flag masks the Integrations tab entirely (for dark-launch). Default on in dev/staging, on-with-allowlist in prod until IN-PRD-06 lands.

### Out of scope
- Re-auth notification emission — IN-PRD-05 (this project receives the deep-link; IN-PRD-05 fires the notification).
- User-removal handler — IN-PRD-05.
- Adding new platform types beyond those shipped by IN-PRD-02 / IN-PRD-04 — those projects seed `PlatformDefinition` docs and flip feature flags; this UI renders whatever is enabled.
- Multi-GA-property picker (when a user's Google account has access to many GA properties) — v1 picks the first; downstream tools let users pick per-query. Deferred.
- Per-scope editing after connect (expand/shrink scopes) — users must revoke + reconnect. Explicitly deferred per `implementation-plan.md` §8.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[IN-PRD-02](./IN-PRD-02-google-oauth-flow.md)** | Google platform end-to-end working. The UI can render the page with just IN-PRD-01's stub platform during development but is not useful without a real platform. | This component |
| **[UI-PRD-01](../../ui/projects/UI-PRD-01-design-system-foundation.md)** | Soft Maximalism tokens, `LayoutSettings` shell, shadcn primitives (`Card`, `Badge`, `Sheet`, `Dialog`, `Button`). | `../../ui/README.md` |
| Existing auth | `has_account_access` + admin-role check; current-user resolver for user-name display. | `api/src/kene_api/auth/` |
| User directory | A way to resolve `user_id → {display_name, email}` for multiple users efficiently — the Users API (batch lookup) or a join on account members. If a batch endpoint doesn't exist, add a minimal `POST /api/v1/users/lookup` (body: `{user_ids: []}`) as part of this project. | `api/src/kene_api/routers/users.py` |
| Feature Flags SDK | `useFeatureFlag("integrations_ui_enabled")` on the tab + per-platform flags from IN-PRD-02/04. | [FF-PRD-03](../../feature-flags/projects/FF-PRD-03-frontend-sdk-and-e2e.md) |
| Figma | Integrations tab design (connection card variants, audit drawer, empty state). Lives under `figma-make/exports/settings-integrations/`. | Figma Make file |

## 4. Data contract

No new Firestore shapes. This PRD reads existing `PlatformDefinition`, `PlatformConnection`, and `ConnectionAuditEntry` documents through new management endpoints.

Response shape for the list endpoint (§6):

```python
class ConnectionCardView(BaseModel):
    platform_id: str
    platform_display_name: str
    platform_logo_url: str | None
    connection: PlatformConnectionPublic | None  # None when not connected
    is_enabled: bool                              # per-platform feature flag state

class PlatformConnectionPublic(BaseModel):
    connection_id: str
    status: Literal["connected", "expired", "revoked", "error"]
    connected_by_user: UserRef                    # { user_id, display_name, email }
    connected_at: datetime
    last_used_at: datetime | None
    scope: list[str]
    external_account_label: str | None
    error_message: str | None                     # surfaced on 'error' / 'expired'
    # Tokens and connected_by_user_id-only (no UserRef) are NEVER included.
```

## 5. Implementation outline

### 5.1 File inventory

| Action | File |
|--------|------|
| Create | `frontend/src/app/pages/settings/integrations/IntegrationsTab.tsx` |
| Create | `frontend/src/app/pages/settings/integrations/ConnectionCard.tsx` |
| Create | `frontend/src/app/pages/settings/integrations/ConnectFlow.tsx` — popup-window choreography + post-message listener |
| Create | `frontend/src/app/pages/settings/integrations/DisconnectDialog.tsx` |
| Create | `frontend/src/app/pages/settings/integrations/AuditLogDrawer.tsx` |
| Create | `frontend/src/app/pages/settings/integrations/EmptyState.tsx` |
| Create | `frontend/src/app/pages/settings/integrations/ConnectionPicker.tsx` — reusable picker (filters `/connections` by `platform_id`, returns `connection_id`); consumed by **DP-PRD-04** custom-job authoring and **PE-PRD-05** setup wizard. |
| Modify | `frontend/src/app/pages/settings/SettingsLayout.tsx` — add Integrations tab entry |
| Create | `frontend/src/app/lib/api/integrations.ts` — typed API client + React Query hooks |
| Create | `api/src/kene_api/routers/integrations_management.py` — `GET /connections` (enriched view), `GET /connections/{id}`, `GET /audit`, `GET /platforms` |
| Modify | `api/src/kene_api/routers/integrations.py` — ensure `initiate` + `revoke` + `force-refresh` enforce admin where required |
| Modify-or-create | `api/src/kene_api/routers/users.py` — `POST /api/v1/users/lookup` batch endpoint if one doesn't already exist |
| Modify | `frontend/src/app/pages/settings/integrations/__tests__/` — component tests for card variants |
| Create | `api/tests/integration/integrations/test_management_endpoints.py` |
| Create | `frontend/src/app/pages/settings/integrations/__tests__/IntegrationsTab.spec.tsx` |

### 5.2 Connect flow choreography

Popup-based to avoid losing SPA state:

```text
onClickConnect(platform_id, return_to?):
  1. POST /initiate {return_to?} → { authorization_url }
  2. window.open(authorization_url, "integrations-oauth", popup-config)
  3. Listen on window 'message' channel for { type: "integrations:callback", outcome: "connected" | "error", connection_id?, error?, return_to? }
  4. Callback page (loaded inside the popup after Google redirects back) posts that message to window.opener and closes itself.
  5. Parent invalidates the TanStack Query cache for connections → card re-renders with new state.
  6. On outcome="connected" with a return_to value, parent navigates to return_to (e.g., /performance/setup); on outcome="error", surface the error message in an inline toast on the card and stay on /settings/integrations.
```

The callback page is the existing `GET /api/v1/integrations/callback/{platform_id}` route's redirect target — it renders a minimal HTML page that reads outcome + connection_id (+ return_to) from the redirect query string, posts to opener, and closes.

**`return_to` propagation through the OAuth round-trip.** `POST /initiate` accepts an optional `return_to: str` body field (must be a same-origin path; rejected if it includes a host or starts with `//`). The path is included in the JWT `state` claim by `StateTokenService.issue(...)` and read back on callback. The callback's HTML stub appends `?return_to=<path>` to its `postMessage` payload so the parent can navigate after card refresh. Default landing remains `/settings/integrations/{connection_id}` for the standalone Settings flow. Consumed by PE-PRD-05's wizard (`?return_to=/performance/setup`).

### 5.3 Connected-by-user resolution

The management `GET /connections` endpoint returns enriched `PlatformConnectionPublic` rows with `connected_by_user: UserRef`. Backend flow:

1. Load all `PlatformConnection` rows for the account.
2. Collect unique `connected_by_user_id` values.
3. Batch-fetch via users lookup (single read or single `in`-query against Firestore account members).
4. Resolve `UserRef = { user_id, display_name, email }`; fall back to `{ user_id, display_name: "Unknown user", email: null }` if the user is no longer an account member — though IN-PRD-05's user-removal handler revokes such connections, so this fallback should be rare in practice (it covers the race window between removal and sweep).

### 5.4 Downstream-impact summary for disconnect

When the Disconnect dialog opens, the UI calls a management endpoint `GET /connections/{id}/downstream-impact` returning a list of affected entities:

- `ProjectPlan`s / `PlanTask`s with `assignee_type="data_pipeline"` whose `pipeline_spec` references this platform.
- `agent_configs` whose wired MCP servers reference this platform (post-IN-PRD-06 cutover).
- Scheduled automations that include any of the above.

For v1, the list is best-effort: returns up to 20 entries with a tally ("… and N more"). If the lookup fails, the dialog falls back to a generic warning. This endpoint is scoped to this PRD; downstream components (project-tasks, agentic-harness) don't need to know it exists.

### 5.5 Audit-log drawer behavior

- Fetches via `GET /audit?connection_id=...` with cursor pagination (50 rows).
- Renders a compact timeline. Each row shows `event` (Connected / Refreshed / Revoked / Used / Error), relative timestamp, and an expandable JSON `metadata` snippet.
- Filters: event type (multi-select), date range (presets: 24h, 7d, 30d, 90d, custom).
- `Used` events are hidden by default (they dominate volume); a toggle enables them.

## 6. API contract

All routes require account access. Admin-only routes are explicitly marked.

### Management reads

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/integrations/{account_id}/connections` | Enriched list: one `ConnectionCardView` per platform where the platform flag is on. Resolves `connected_by_user_id` to `UserRef`. |
| `GET` | `/api/v1/integrations/{account_id}/connections/{connection_id}` | Full `PlatformConnectionPublic` (no tokens). |
| `GET` | `/api/v1/integrations/{account_id}/connections/{connection_id}/downstream-impact` | Up to 20 affected entities for the Disconnect dialog. |
| `GET` | `/api/v1/integrations/{account_id}/audit` | Paginated audit log (filters: `connection_id`, `event`, `from`, `to`, `cursor`, `include_used`). |
| `GET` | `/api/v1/integrations/platforms` | Available platform definitions filtered by per-platform feature flags; includes `connected: bool` per platform for the account. |

### Mutations (already existing, called by this UI)

| Method | Path | Auth |
|---|---|---|
| `POST` | `/api/v1/integrations/{account_id}/connections/{platform_id}/initiate` | Account member |
| `DELETE` | `/api/v1/integrations/{account_id}/connections/{connection_id}` | **Account admin** |
| `POST` | `/api/v1/integrations/{account_id}/connections/{connection_id}/refresh` | **Account admin** |

## 7. Acceptance criteria

1. **Tab rendered** — `/settings/integrations` appears on the Settings page when `integrations_ui_enabled=true`; hidden when off.
2. **Platform grid** — every platform whose per-platform flag is on renders a card. Disabled platforms are absent. Empty account (no connections, no enabled platforms) renders the empty-state component.
3. **Connection card states** — card renders correct copy for each of the five states (`Not connected`, `Connected`, `Expired`, `Revoked`, `Error`) with matching badge color and primary CTA.
4. **Connected-by user name visible** — when connected, the card shows the display name of the user who initiated the flow. Resolved from `connected_by_user_id → UserRef.display_name`. Fallback to "Unknown user" if the user is no longer a member.
5. **Connect flow** — clicking Connect opens a popup to Google, completes OAuth, closes the popup, and the card updates to Connected with all fields populated. Total round-trip <30s p95.
6. **Health-check failure surfaces** — with an intentionally under-scoped grant, the card shows a red `Error` state with the descriptive error from the backend, and no `PlatformConnection` row is written.
7. **Disconnect dialog lists impact** — opening Disconnect shows up to 20 downstream entities; confirmation triggers the revoke; card updates to `Not connected` and a toast confirms.
8. **Audit drawer** — View audit log opens a drawer listing entries filtered to the connection; filters + pagination work; `Used` events hidden by default.
9. **Deep-link behavior** — navigating to `/settings/integrations/:connection_id` scrolls to and highlights the matching card; if the connection is in a non-connected state, Reconnect is auto-focused.
10. **Authorization enforced** — non-admin member cannot Disconnect or Force refresh; UI hides those actions; backend 403s if called directly.
11. **Force refresh (admin)** — admin-only menu item calls `POST /connections/{id}/refresh`; toast reports new `expires_at`; card `last_refreshed_at` updates.
12. **Typed client + hooks** — `useConnections(accountId)`, `useConnection(accountId, connectionId)`, `useConnectMutation`, `useDisconnectMutation`, `useForceRefreshMutation`, `useAuditLog(...)` all typed; no `any` in the module.
13. **Batch user lookup efficient** — management `GET /connections` issues one user-lookup call regardless of connection count (verified by integration test assertion on request count).
14. **Accessibility** — cards are keyboard-navigable; status badges include `aria-label`s; audit drawer traps focus.

## 8. Test plan

### Unit (frontend, Vitest + Testing Library)
- `ConnectionCard` renders each of the five states with correct copy + CTA.
- `ConnectFlow` handles popup-blocked scenario (shows inline "Allow popups" guidance).
- `DisconnectDialog` blocks confirmation until the checkbox is checked; calls the downstream-impact endpoint on open.
- `AuditLogDrawer` filter toggles + pagination.

### Unit (backend, pytest)
- `/connections` endpoint batches user-lookup.
- `/connections/{id}/downstream-impact` returns <=20 entries; handles each consumer-type stub.
- Authorization enforced on `DELETE` / `force-refresh`.

### Integration
- Full UI flow against a dev-env account with StubPlatform (no real Google needed in CI): empty state → connect → card populated → force-refresh → disconnect → empty state.
- Deep-link behavior with a seeded expired connection.
- Concurrent-user test: user A connects; user B's `/connections` response shows the connection with A's display name.

### Manual verification
- Prod-gated prelaunch smoke test: connect a real Google account, confirm label + scopes, disconnect, confirm cleanup, check audit drawer.
- Accessibility pass: VoiceOver walks the page; keyboard-only nav completes a connect/disconnect cycle.

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| Popup-blocker breaks connect flow | Popup initiated inside the click handler (user-gesture-scoped); fallback inline guidance + retry if `window.open` returns null. |
| Stale `PlatformConnectionPublic` in the UI after a background refresh sweep | TanStack Query refetches on window-focus + every 60s while the tab is active. |
| "Unknown user" fallback creates confusion | IN-PRD-05 revokes connections whose `connected_by_user_id` was removed, so the fallback should be rare. Card tooltip explains: "The user who connected this integration is no longer a member of this account." |
| Downstream-impact lookup latency on large accounts | Cap at 20 results with tally; timeout at 3s; degrade to generic warning if the lookup fails. |
| Force refresh abused | Rate-limit per admin per connection (1/min) to prevent accidental hammering of Google's token endpoint. |

### Open questions
- **Q:** Should `Connected by <user>` include the user's avatar? → Yes if the UserRef includes one; otherwise initials. Non-blocking.
- **Q:** Show scope chips as human names (e.g., "Read GA data") or raw (`analytics.readonly`)? → Human names with raw on hover-tooltip. PlatformDefinition gets an optional `scope_display_names: dict[str, str]` field in IN-PRD-02's seed to support this; if missing, show raw.

## 10. Reference

- Component plan: [`../implementation-plan.md`](../implementation-plan.md)
- Upstream: [IN-PRD-02](./IN-PRD-02-google-oauth-flow.md), [UI-PRD-01](../../ui/projects/UI-PRD-01-design-system-foundation.md)
- Downstream: [IN-PRD-05](./IN-PRD-05-reauth-lifecycle.md), [DP-PRD-04](../../data-pipeline/projects/DP-PRD-04-frontend-and-custom-jobs.md), [PE-PRD-05](../../performance/projects/PE-PRD-05-setup-wizard.md)
- Design: Figma Make `settings-integrations` node
- CLAUDE.md rules in scope: C-5, C-6, C-8; T-2; G-2, G-3
