# Integrations — Product Requirements Document

> **Linear Team:** [KEN-E] Integrations
> **Last Updated:** 2026-04-23
> **Status:** Draft — substrate designed, PRDs scoped, not yet implemented

## 1. Overview

The Integrations component is KEN-E's **third-party credential substrate**. It owns the OAuth flow per platform, the encrypted token store, the refresh lifecycle, the per-account multi-user sharing semantics, and the revocation / re-auth flow. Every component that talks to a third-party platform — Data Pipeline connectors, Agent Factory tools, future Knowledge Graph ingestion — reads credentials through this component. No other component decrypts tokens, speaks OAuth, or writes to `platform_connections/*`.

Three facts shape the design. **Connections are account-scoped, not user-scoped** — when a user authorizes "my business's GA account," the resulting tokens belong to the KEN-E account and every member can invoke jobs that use them, which matches how marketing teams actually work. **Tokens are KMS-encrypted at rest** with an env-specific Cloud KMS key that never leaves GCP, so a stolen Firestore export does not yield usable credentials. **Re-auth is first-class** — tokens expire, scopes change, users revoke at the platform; the component emits a single standard "Connection Needs Re-auth" notification and every consumer handles it the same way (hold the task, surface the notification, restore on reconnection).

A developer reading only this section should understand: this component owns the `platform_definitions/*` and `accounts/{account_id}/platform_connections/*` Firestore collections (plus the token subcollection + audit log), the `/api/v1/integrations/*` user-facing and `/api/v1/internal/integrations/*` service-to-service API surfaces, the `/settings/integrations` UI tab, and the KMS-encryption + JWT-state-token + re-auth-notification substrate that makes all of the above work. It ships across **7 project PRDs (IN-PRD-01 → IN-PRD-07)** and blocks the Data Pipeline platform connectors (DP-PRD-02 Google Analytics, DP-PRD-05 Meta / Mailchimp) as well as the Agent Factory's credential-loading retrofit (IN-PRD-06 absorbs the cleanup). IN-PRD-07 is an opt-in verification surface — on-demand "Test connection" from the Settings tab plus an MCP tool — that rides the substrate without gating anything downstream.

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  User connects a platform                                                   │
│    POST /api/v1/integrations/{account_id}/connections/{platform_id}/initiate│
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Integrations OAuth flow (generic; driven by PlatformDefinition)            │
│    ├── StateTokenService.issue() — HMAC-signed JWT (10-min exp, nonce)      │
│    ├── Build authorize URL from PlatformDefinition + scopes + state         │
│    └── Redirect user's browser to the platform's auth page                  │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  GET /api/v1/integrations/callback/{platform_id}?code=...&state=...         │
│    1. StateTokenService.verify(state) — sig + exp + nonce replay            │
│    2. Exchange code → tokens at PlatformDefinition.oauth_token_url          │
│    3. If PlatformDefinition.long_lived_exchange_url — second exchange       │
│    4. If PlatformDefinition.health_check_endpoint — validate scopes         │
│    5. KMSEncryptionService.encrypt(tokens) → EncryptedToken rows            │
│    6. Persist PlatformConnection + write_connection_audit(event=connected)  │
│    7. Redirect to /settings/integrations/{connection_id}                    │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
                       accounts/{account_id}/
                         platform_connections/{connection_id}
                           ├── (doc) status, scope, connected_by_user_id,
                           │         external_account_label, last_used_at
                           └── tokens/
                               ├── access_token  (EncryptedToken)
                               ├── refresh_token (EncryptedToken)
                               └── id_token      (EncryptedToken, optional)

                           Credential read (service-to-service)

┌─────────────────────────────────────────────────────────────────────────────┐
│  Consumer (Data Pipeline / Agent Factory / Knowledge Graph)                 │
│    GET /api/v1/internal/integrations/credentials/{account_id}/{platform_id} │
│    (OIDC-authed, service-account-scoped)                                    │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. Load PlatformConnection; if status != connected → 409 needs_reauth      │
│  2. If now + refresh_lookahead_seconds > expires_at:                        │
│       refresh_connection()  (Firestore-transaction lock, ~200ms)            │
│  3. KMSEncryptionService.decrypt(access_token) → plaintext in-memory only   │
│  4. write_connection_audit(event=used)  (debounced)                         │
│  5. Return { access_token, expires_at, external_account_id }                │
└─────────────────────────────────────────────────────────────────────────────┘

                                 Re-auth lifecycle

┌───────────────────┐  refresh fails  ┌─────────────────────────────────────┐
│ refresh_sweeper   ├────────────────►│ mark_expired(connection_id, reason) │
│ (5-min cron)      │                 │  1. Firestore txn: status=expired   │
└───────────────────┘                 │  2. 24h dedup window check          │
┌───────────────────┐ consumer 401    │  3. write_connection_audit          │
│ Any consumer      ├────────────────►│  4. create_notification             │
│ (401 on API call) │                 │        INTEGRATION_NEEDS_REAUTH     │
└───────────────────┘                 │        deep-link:                   │
┌───────────────────┐ user removed    │          /settings/integrations/{id}│
│ on_user_removed   ├────────────────►│ + user-removal: revoke + delete all │
│ (internal hook)   │                 │   connections authored by user      │
└───────────────────┘                 └─────────────────────────────────────┘
```

### 2.1 Key Directories

| Path | Purpose |
|------|---------|
| `api/src/kene_api/models/integrations.py` | `PlatformDefinition`, `PlatformConnection`, `EncryptedToken`, `ConnectionAuditEntry`, `StateTokenClaims`, `PlatformConnectionPublic`. Created by IN-PRD-01; extended by IN-PRD-04 (`long_lived_exchange_url`, `revoke_method`, `token_response_extra_fields`, `platform_metadata`) and IN-PRD-05 (`last_reauth_notification_sent_at`). |
| `api/src/kene_api/integrations/kms.py` | `KMSEncryptionService` — envelope around Cloud KMS encrypt/decrypt; tracks `kms_key_version` per ciphertext. (IN-PRD-01) |
| `api/src/kene_api/integrations/tokens.py` | `EncryptedToken` read/write helpers; writes under `accounts/{account_id}/platform_connections/{connection_id}/tokens/{kind}`. (IN-PRD-01) |
| `api/src/kene_api/integrations/state_tokens.py` | `StateTokenService` — HMAC-signed JWT issue/verify, 10-min expiry, one-time nonce enforcement. (IN-PRD-01) |
| `api/src/kene_api/integrations/oauth.py` | Generic OAuth initiate + callback driven by `PlatformDefinition`. No platform-specific branches. (IN-PRD-01; extended declaratively by IN-PRD-04) |
| `api/src/kene_api/integrations/refresh.py` | `refresh_connection()` helper — Firestore-transaction-guarded token refresh; honors `refresh_grant_type`. (IN-PRD-02; extended by IN-PRD-04 for `fb_exchange_token`) |
| `api/src/kene_api/integrations/reauth.py` | `mark_expired(...)` transactional helper + notification emission + 24h dedup. (IN-PRD-05) |
| `api/src/kene_api/integrations/user_removal.py` | `on_user_removed(account_id, user_id)` handler — revokes + deletes every connection authored by the removed user. (IN-PRD-05) |
| `api/src/kene_api/integrations/audit.py` | `write_connection_audit(...)` — thin wrapper over DM-PRD-07's `write_audit`. (IN-PRD-01) |
| `api/src/kene_api/integrations/stub_platform.py` | In-memory fake OAuth server for hermetic tests; non-production only. (IN-PRD-01; extended by IN-PRD-04 for Meta / Mailchimp variants) |
| `api/src/kene_api/integrations/platforms/google.py` | Google-specific scope assembly + health-check parsing + `accountSummaries.list` label fetch. Pure module, no branches in generic code. (IN-PRD-02) |
| `api/src/kene_api/integrations/workers/refresh_sweeper.py` | Cloud Scheduler handler — pre-emptive refresh (5-min cadence). (IN-PRD-02) |
| `api/src/kene_api/integrations/workers/idle_cleanup.py` | Daily cron — revokes connections inactive ≥90 days. (IN-PRD-02) |
| `api/src/kene_api/integrations/workers/stuck_expired_watchdog.py` | Daily cron — alerts on connections stuck `expired` >7 days. (IN-PRD-05) |
| `api/src/kene_api/integrations/workers/kms_rewrap_sweeper.py` | Post-rotation re-encrypt-under-new-version sweeper; disabled by default. (IN-PRD-06) |
| `api/src/kene_api/integrations/testing.py` | `test_connection(account_id, connection_id)` — orchestrator for the on-demand Test-connection endpoint. 60s cache on the connection doc. (IN-PRD-07) |
| `api/src/kene_api/models/integrations_test.py` | `ConnectionTestResult`, `ConnectionTestError`, `ProbeDetails`. (IN-PRD-07) |
| `app/adk/tools/integrations_test_tool.py` | MCP tool exposing `integrations.test_connection(platform_id)` for agent-side preflight. (IN-PRD-07) |
| `api/src/kene_api/routers/integrations.py` | User-facing + internal endpoints — initiate, callback, refresh, revoke, mark-expired, on-user-removed, credential-read. (IN-PRD-01; extended across IN-PRD-02 / IN-PRD-05) |
| `api/src/kene_api/routers/integrations_management.py` | Management reads — `/connections`, `/connections/{id}`, `/connections/{id}/downstream-impact`, `/audit`, `/platforms`. (IN-PRD-03) |
| `api/src/kene_api/routers/_test_stub_platform.py` | Stub-platform test harness; gated `ENV != "production"`. (IN-PRD-01) |
| `api/scripts/migrate_integrations_foundation.py` | Shape B migration — creates collections, seeds empty `platform_definitions`, configures indexes + TTL. (IN-PRD-01) |
| `api/scripts/seed_google_platform_definition.py` | Seeds `platform_definitions/google`. (IN-PRD-02) |
| `api/scripts/seed_meta_platform_definition.py`, `seed_mailchimp_platform_definition.py` | (IN-PRD-04) |
| `frontend/src/app/pages/settings/integrations/` | Settings → Integrations tab: `IntegrationsTab.tsx`, `ConnectionCard.tsx`, `ConnectFlow.tsx` (popup choreography), `DisconnectDialog.tsx`, `AuditLogDrawer.tsx`, `EmptyState.tsx`. (IN-PRD-03) + `ConnectionTestResultBadge.tsx` (IN-PRD-07) |
| `frontend/src/app/lib/api/integrations.ts` | Typed API client + React Query hooks with branded `ConnectionId` / `PlatformId`. (IN-PRD-03) |
| `docs/design/components/integrations/operations/` | Runbooks: `google-oauth-setup.md`, `meta-oauth-setup.md`, `mailchimp-oauth-setup.md`, `kms-key-rotation.md`, `integrations-watchdog.md`. |

### 2.2 Data Flow

1. **Connect (IN-PRD-01 substrate + IN-PRD-02 Google / IN-PRD-04 Meta + Mailchimp).** A user in the UI (IN-PRD-03) clicks Connect; the frontend POSTs to `initiate`, which builds a JWT state token and returns a platform authorization URL. The user completes OAuth in a popup; the platform redirects to our generic callback (`/api/v1/integrations/callback/{platform_id}`). The callback verifies the JWT (signature + exp + nonce not-previously-used), exchanges the code, optionally runs a long-lived-token exchange (Meta — declarative via `long_lived_exchange_url`), optionally runs a health check against a platform-configured endpoint (aborts on non-2xx), KMS-encrypts the tokens under the env key, and persists `PlatformConnection` + `EncryptedToken` rows. One `connected` audit entry is written.
2. **Read (every consumer).** Data Pipeline, Agent Factory (post-IN-PRD-06), and any future consumer calls `GET /api/v1/internal/integrations/credentials/{account_id}/{platform_id}` with an OIDC token. The endpoint loads the connection, returns 409 `needs_reauth` if the status is non-`connected`, pre-emptively refreshes if the token expires within `refresh_lookahead_seconds` (Firestore-transaction-guarded to prevent thundering-herd refreshes), decrypts the access token in-memory only, and returns `{access_token, expires_at, external_account_id}`. Emits a debounced `used` audit entry.
3. **Refresh (IN-PRD-02).** Two paths: (a) the `refresh_sweeper` cron runs every 5 min and pre-emptively refreshes connections expiring within 10 min; (b) synchronous refresh on the credential-read path for connections missed by the sweeper. Both converge on `refresh.refresh_connection(connection_id)`, which holds a Firestore transaction on the connection doc, calls the platform's token endpoint with the platform's `refresh_grant_type` (default `"refresh_token"`, Meta uses `"fb_exchange_token"`), re-KMS-encrypts, and emits a `refreshed` audit entry.
4. **Expire / re-auth (IN-PRD-05).** Three triggers enter `mark_expired(connection_id, reason)`: (i) refresh failure, (ii) a consumer posting `mark-expired` after catching a 401 on a platform call (handles cases where the platform revokes a token before its expiry), (iii) `on_user_removed` revoking connections authored by a removed user. `mark_expired` transitions `status` to `expired` in a Firestore transaction, checks the 24h dedup window, writes a `reauth_requested` audit entry, and emits a `NotificationCategory.INTEGRATION_NEEDS_REAUTH` notification deep-linking to `/settings/integrations/{connection_id}`.
5. **Revoke (IN-PRD-02).** `DELETE /connections/{connection_id}` (account-admin only) calls the platform's revoke endpoint with the method specified by `PlatformDefinition.revoke_method` (POST default; DELETE for Mailchimp), tolerates 400-already-revoked, and `firestore.recursive_delete`s the connection and its token subcollection. One `revoked` audit entry.
6. **User removal (IN-PRD-05).** When a user is removed from an account (via the existing member-removal flow), a post-commit call to `POST /api/v1/internal/integrations/on-user-removed` iterates every `PlatformConnection` where `connected_by_user_id == removed_user_id`, best-effort-revokes each, deletes them, writes `revoked` audit entries with `actor_id="system:user_removed"`, and emits one notification per revoked connection to remaining account admins.
7. **Rotation (IN-PRD-06).** KMS key rotation is driven from the runbook — rotate in Cloud KMS, enable the `kms_rewrap_sweeper` hourly cron, monitor `kms_key_version` distribution, disable old key version after 24h, destroy after 30d. The sweeper decrypts each `EncryptedToken` (KMS handles version resolution automatically), re-encrypts under the current version, persists with the new `kms_key_version`. Capped at 500 tokens/tick.

### 2.3 API Contracts

Owned endpoints:

| Endpoint | Method | Owner | Purpose |
|----------|--------|-------|---------|
| `/api/v1/integrations/{account_id}/connections/{platform_id}/initiate` | POST | IN-PRD-01 | Start OAuth; returns `{ authorization_url }`. Account member auth. |
| `/api/v1/integrations/callback/{platform_id}` | GET | IN-PRD-01 | OAuth callback; verifies state JWT, exchanges code, persists tokens, redirects to UI. |
| `/api/v1/integrations/{account_id}/connections/{connection_id}` | DELETE | IN-PRD-02 | Revoke + recursive-delete. **Account admin.** |
| `/api/v1/integrations/{account_id}/connections/{connection_id}/refresh` | POST | IN-PRD-02 | Force refresh. **Account admin** (rate-limited 1/min). |
| `/api/v1/integrations/{account_id}/connections/{connection_id}/test` | POST | IN-PRD-07 | On-demand live probe. Account member. Returns `ConnectionTestResult`. 60s cache on the connection doc; transient errors not cached. |
| `/api/v1/integrations/{account_id}/connections` | GET | IN-PRD-03 | Enriched connection cards — includes `connected_by_user: UserRef`. |
| `/api/v1/integrations/{account_id}/connections/{connection_id}` | GET | IN-PRD-03 | Full `PlatformConnectionPublic`. No tokens. |
| `/api/v1/integrations/{account_id}/connections/{connection_id}/downstream-impact` | GET | IN-PRD-03 | Up to 20 entities affected by a disconnect (for the confirmation dialog). |
| `/api/v1/integrations/{account_id}/audit` | GET | IN-PRD-03 | Paginated `ConnectionAuditEntry` log with filters. |
| `/api/v1/integrations/platforms` | GET | IN-PRD-03 | `PlatformDefinition` list filtered by per-platform feature flags; includes `connected: bool` per platform for the account. |
| `/api/v1/internal/integrations/credentials/{account_id}/{platform_id}` | GET | IN-PRD-01 (refresh by IN-PRD-02) | OIDC. Decrypted `{access_token, expires_at, external_account_id}`. Transparently refreshes. |
| `/api/v1/internal/integrations/connections/{connection_id}/mark-expired` | POST | IN-PRD-05 | OIDC. Called by consumers on 401. 24h-deduped notification. |
| `/api/v1/internal/integrations/on-user-removed` | POST | IN-PRD-05 | OIDC. Revoke + delete connections authored by the removed user. |
| `/api/v1/internal/integrations/refresh-sweeper` | POST | IN-PRD-02 | Cloud Scheduler. Pre-emptive refresh batch. |
| `/api/v1/internal/integrations/idle-cleanup` | POST | IN-PRD-02 | Cloud Scheduler. Daily 90-day-idle revocation. |
| `/api/v1/internal/integrations/stuck-expired-watchdog` | POST | IN-PRD-05 | Cloud Scheduler. Daily PagerDuty/Slack alert. |
| `/api/v1/internal/integrations/kms-rewrap-sweeper` | POST | IN-PRD-06 | Cloud Scheduler. Post-rotation re-encrypt batch; disabled by default. |
| `/api/v1/_test/stub-platform/{authorize,token,health}` | varies | IN-PRD-01 | Non-production stub OAuth server. `ENV=production` returns 404. |

Schema source of truth: `api/src/kene_api/models/integrations.py` (Pydantic), mirrored in `frontend/src/app/lib/api/integrations.ts` as branded `ConnectionId` / `PlatformId` / `UserRef`. URL paths use kebab-case (`platform-connections`); Firestore paths use snake_case (`platform_connections`).

### 2.4 Key Abstractions

| Abstraction | Path | Purpose |
|-------------|------|---------|
| `PlatformDefinition` | `api/src/kene_api/models/integrations.py` | Declarative spec of how to OAuth a platform — URLs, scopes, `auth_type="oauth2_auth_code"`, `refresh_grant_type`, `revoke_method`, `long_lived_exchange_url`, `token_response_extra_fields`, `health_check_endpoint`, `platform_version`. New platforms are a Firestore seed, not code. |
| `PlatformConnection` | Same | Per-account connection state — `status`, `connected_by_user_id`, `scope`, `external_account_label`, `platform_metadata` (e.g., `{"dc": "us14"}` for Mailchimp), `last_reauth_notification_sent_at`. |
| `EncryptedToken` | Same | KMS ciphertext for one `kind` (`access_token` / `refresh_token` / `id_token`) under the connection. `kms_key_version` tracked for rotation. |
| `KMSEncryptionService` | `api/src/kene_api/integrations/kms.py` | `encrypt(plaintext) → (ciphertext, kms_key_version)`, `decrypt(ciphertext) → plaintext`. KMS resolves version automatically on decrypt; we persist the version for the rotation sweeper. |
| `StateTokenService` | `api/src/kene_api/integrations/state_tokens.py` | HMAC-signed JWT issue/verify for OAuth CSRF defense. Claims: `{user_id, account_id, platform_id, nonce, exp}`. One-time nonce enforced via `integrations_state_nonces/{nonce}` with 15-min TTL. |
| `refresh_connection(connection_id)` | `api/src/kene_api/integrations/refresh.py` | Firestore-transaction-guarded refresh. Dispatches on `PlatformDefinition.refresh_grant_type`. Writes `refreshed` audit. Fails closed → calls `mark_expired`. |
| `mark_expired(connection_id, reason)` | `api/src/kene_api/integrations/reauth.py` | Atomic `status=expired` + 24h dedup + audit + notification. Idempotent on already-expired. Single source of truth for the `connected → expired` transition. |
| `on_user_removed(account_id, user_id)` | `api/src/kene_api/integrations/user_removal.py` | Revoke + delete every connection authored by `user_id`; notify remaining admins. |
| `write_connection_audit(...)` | `api/src/kene_api/integrations/audit.py` | Writes `ConnectionAuditEntry` via DM-PRD-07's `write_audit`. Lint rule blocks token values in `metadata`. |
| `StubPlatform` | `api/src/kene_api/integrations/stub_platform.py` | In-memory fake OAuth server. Configurable modes for plain OAuth, long-lived exchange (Meta), extra response fields (Mailchimp `dc`). Non-production only. |
| `test_connection(account_id, connection_id)` | `api/src/kene_api/integrations/testing.py` | On-demand verification orchestrator. Reads credentials via the existing internal path, calls `PlatformDefinition.health_check_endpoint` with a 1s timeout, classifies the response into `{ok, auth_failed, scope_missing, rate_limited, platform_5xx, timeout, network, needs_reauth, no_probe_configured}`, triggers `mark_expired` on definitive 401/403, persists result on the connection doc with a 60s cache window (transient errors not cached). (IN-PRD-07) |
| `ConnectionTestResult` | `api/src/kene_api/models/integrations_test.py` | Response type — `{ok, checked_at, latency_ms, probe, error?, cache_hit}`. (IN-PRD-07) |

## 3. Component Dependencies

### 3.1 Depends On

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[Data Management — DM-PRD-00 (Migration Foundation)](../data-management/projects/DM-PRD-00-migration-foundation.md)** | **Hard prerequisite for IN-PRD-01.** Shape B convention + `migrate_to_shape_b.py` + `_migrate_shape_b/resources.py` registry. Integrations lands its new subcollections (`accounts/{account_id}/platform_connections`, the token subcollection, `accounts/{account_id}/integrations_audit`) via this framework. | `../data-management/README.md` §2.2 |
| **[Data Management — DM-PRD-07 (Approval Workflow & Audit)](../data-management/projects/DM-PRD-07-approval-workflow-and-audit.md)** | **Hard prerequisite for IN-PRD-01.** `AuditEntry` schema + `write_audit(actor_id, event, ...)`. Integrations subclasses into `ConnectionAuditEntry`. | `../data-management/README.md` audit section |
| **[Feature Flags — FF-PRD-01 (Evaluation API + Backend SDK)](../feature-flags/projects/FF-PRD-01-data-model-evaluation-api.md)** | **Hard prerequisite.** `integrations_enabled`, `integrations_ui_enabled`, `integrations_reauth_lifecycle_enabled`, `integrations_connection_test_enabled`, and per-platform flags (`integration_google_enabled`, `integration_meta_enabled`, `integration_mailchimp_enabled`). | `../feature-flags/README.md` |
| **[UI — UI-PRD-01 (Design System Foundation + Shell)](../ui/projects/UI-PRD-01-design-system-foundation.md)** | **Hard prerequisite for IN-PRD-03.** `LayoutSettings` shell + re-skinned shadcn primitives (`Card`, `Badge`, `Sheet`, `Dialog`, `Button`). | `../ui/README.md` |
| GCP Cloud KMS | Per-environment `token-encryption` key under the `integrations` key ring. Service account has only `cryptoKeyEncrypterDecrypter` — no export, no destroy. Terraform `lifecycle { prevent_destroy = true }` on the key. | `deployment/terraform/` |
| GCP Secret Manager | Per-env OAuth client credentials (`google-oauth-client-{id,secret}-{env}`, Meta, Mailchimp) + `integrations-state-token-hmac-{env}` JWT signing key. | `deployment/terraform/` |
| GCP Cloud Scheduler | Four cron jobs: `integrations-google-refresh-sweeper` (5-min), `integrations-idle-cleanup` (daily), `integrations-stuck-expired-watchdog` (daily), `integrations-kms-rewrap-sweeper` (hourly, disabled by default). | `deployment/terraform/` |
| Existing notification system | `create_notification(account_id, category, payload, deep_link)` + the bell UI + email-digest routing. IN-PRD-05 adds `NotificationCategory.INTEGRATION_NEEDS_REAUTH`. | `api/src/kene_api/notifications/` |
| Existing account-member service | Member-removal flow adds a post-commit call to `POST /internal/integrations/on-user-removed`. | `api/src/kene_api/routers/accounts.py` (or `organizations.py`) |
| W&B Weave tracing | `integrations.credential_read`, `integrations.refresh`, `integrations.revoke`, `integrations.kms_rewrap`, `integrations.store_token`, `integrations.stub_oauth_flow` spans. No token values on spans (lint-enforced). | `app/adk/tracking/` |

### 3.2 Depended On By

| Component | Dependency |
|-----------|------------|
| **[Data Pipeline](../data-pipeline/README.md)** | DP-PRD-02 (Google Analytics connector) blocks on IN-PRD-02. DP-PRD-05 (Meta Ads + Mailchimp connectors) blocks on IN-PRD-04. Both read credentials exclusively via `GET /api/v1/internal/integrations/credentials/...` — no direct token access. DP-PRD-04 (custom-job authoring UI) uses the connection picker from IN-PRD-03. |
| **[Agentic Harness](../agentic-harness/README.md)** | AH-PRD-02 ships a transitional `_make_header_provider(auth_type)` that reads OAuth tokens from ADK session state. **IN-PRD-06 retrofits it** to call `GET /api/v1/internal/integrations/credentials/...` instead. The closure signature + `header_provider=` plumbing stay intact; only the credential source moves. After IN-PRD-06, `grep -rn '_make_header_provider\|ga_credentials\[' api/src/ app/` yields zero session-state hits. |
| **[Performance / Setup Wizard (PE-PRD-05)](../performance/projects/PE-PRD-05-setup-wizard.md)** | Wizard deep-links to `/settings/integrations` when a required platform isn't connected; reads `GET /platforms` to detect connection status. |
| **[Knowledge Graph](../knowledge-graph/README.md)** | Future platform ingestion (once KG pulls from GA / Ads / Meta directly) will read credentials via Integrations. Not yet active. |
| **[Automations](../automations/README.md)** | Downstream-impact lookup in IN-PRD-03's Disconnect dialog enumerates scheduled automations that reference affected platforms. Transitive only — Automations never reads tokens. |
| **[Chat (CH-PRD-04)](../chat/projects/CH-PRD-04-session-status-view.md)** | Session Status View's Authentication Status card (§5.6) renders account-level integration state — **hard dep on IN-PRD-03** for `GET /connections` + `useConnections(accountId)` hook; **soft dep on IN-PRD-07** for the per-row Check Status button + state-reactive CTAs (flag-gated on `integrations_connection_test_enabled`). Pure frontend composition — no new Chat-owned backend endpoint. Deep-links to `/settings/integrations/{connection_id}` for row-level management. |
| Engineering incident response | Any platform can be killed account-wide in ≤60s via the per-platform feature flag. Any individual connection can be force-revoked via the admin UI. Documented in `operations/` runbooks. |

## 4. Design System References

| Document | Sections | When to Read |
|----------|----------|--------------|
| Figma Make export — `settings-integrations` node | Connection-card variants (5 states), Disconnect dialog, Audit-log drawer, Empty state | When implementing IN-PRD-03. Card states map 1:1 to `PlatformConnection.status` values plus "not connected" and the `Error` + `Expired` variants show the `error_message`. |
| `frontend/CLAUDE.md` | CSS architecture, shadcn/ui component library, branded types (`ConnectionId`, `PlatformId`), TanStack Query patterns | Before adding any React component under `pages/settings/integrations/`. |
| UI-PRD-01's `LayoutSettings` + tab pattern | Existing Settings-page shell | The Integrations tab follows the same tab-entry pattern as Account Settings / User Settings / Organization Settings. Match it — don't invent a new layout. |

## 5. Project Index

The component's work is split across **7 project PRDs** under [`projects/`](./projects/). IN-PRD-01 is a strict prerequisite (the substrate); IN-PRD-02 is a strict prerequisite for the remaining five (first real platform). After IN-PRD-02 lands, IN-PRD-03 (UI), IN-PRD-04 (Meta + Mailchimp), and the first half of IN-PRD-05 (the `mark-expired` hook + user-removal handler) can run in parallel. IN-PRD-05's notification path needs IN-PRD-03's deep-link target. IN-PRD-06 is the capstone — E2E + legacy cleanup + KMS-rotation drill. IN-PRD-07 is an optional verification surface (on-demand Test-connection endpoint + Settings-card button + MCP tool) that can ship in parallel with IN-PRD-06 or as a fast-follow; it reads the substrate IN-PRD-02/03/05 deliver and gates nothing downstream.

### 5.1 Dependency graph

```
DM-PRD-00 (Migration Foundation)  ─┐
DM-PRD-07 (Audit schema)          ─┤
FF-PRD-01 (Feature Flags)         ─┤
                                    │
                                    ▼
                          ┌───────────────────┐
                          │   IN-PRD-01       │  Core model + encryption + JWT state + StubPlatform
                          └─────────┬─────────┘
                                    │
                                    ▼
                          ┌───────────────────┐
                          │   IN-PRD-02       │  Google OAuth + refresh + health check
                          └─┬───────┬──────┬──┘
                            │       │      │
                  UI-PRD-01 │       │      │
                     │      │       │      │
                     ▼      ▼       ▼      ▼
               ┌──────────┐ ┌─────────┐ ┌──────────┐   ┌──────────┐
               │IN-PRD-03 │ │IN-PRD-04│ │DP-PRD-02 │   │AH-PRD-03 │
               │ UI tab   │ │Meta/MC  │ │ GA conn. │   │(transit.)│
               └────┬─────┘ └────┬────┘ └──────────┘   └──────────┘
                    │            │                          ▲
                    ▼            ▼                          │ IN-PRD-06
              ┌──────────┐ ┌──────────┐                     │ retrofit
              │IN-PRD-05 │ │DP-PRD-05 │                     │
              │ Re-auth  │ └──────────┘                     │
              └────┬─────┘                                  │
                   │                                         │
                   ▼                                         │
              ┌──────────┐                                   │
              │IN-PRD-06 │ ──────────────────────────────────┘
              │ E2E +    │
              │ KMS rot. │
              │ + legacy │
              │ cleanup  │
              └──────────┘

          IN-PRD-03 + IN-PRD-05
                    │
                    ▼
              ┌──────────┐
              │IN-PRD-07 │   On-demand Test-connection
              │ Test     │   (endpoint + Settings button
              │ conn.    │    + MCP tool; parallel with 06)
              └──────────┘
```

### 5.2 Projects

| # | Project PRD | Owner team | Blocked by | Parallel with | Est. |
|---|-------------|------------|------------|---------------|------|
| 01 | [Core Model + Encryption](./projects/IN-PRD-01-core-model-encryption.md) | Integrations / Backend | DM-PRD-00, DM-PRD-07, FF-PRD-01 | — | 4 days |
| 02 | [Google OAuth Flow](./projects/IN-PRD-02-google-oauth-flow.md) | Integrations / Backend | IN-PRD-01 | — | 4 days |
| 03 | [Connection-Management UI](./projects/IN-PRD-03-connection-management-ui.md) | Integrations / Frontend + thin backend | IN-PRD-02, UI-PRD-01 | IN-PRD-04 | 3.5 days |
| 04 | [Meta + Mailchimp Platforms](./projects/IN-PRD-04-meta-mailchimp-platforms.md) | Integrations / Backend | IN-PRD-02 | IN-PRD-03 | 3 days |
| 05 | [Re-auth Lifecycle](./projects/IN-PRD-05-reauth-lifecycle.md) | Integrations / Backend + thin frontend | IN-PRD-02, IN-PRD-03 | IN-PRD-04 | 2 days |
| 06 | [Integration Testing + Legacy Cleanup](./projects/IN-PRD-06-integration-testing-cleanup.md) | Integrations / Backend (cross-component sweep) | IN-PRD-01..05 | — | 2 days |
| 07 | [On-demand Connection Test](./projects/IN-PRD-07-on-demand-connection-test.md) | Integrations / Backend + thin frontend + small agent-tool addition | IN-PRD-02, IN-PRD-03, IN-PRD-05 | IN-PRD-06 | 3 days |

### 5.3 Cross-PRD coordination points

Three touchpoints need conscious coordination:

- **Substrate genericity (IN-PRD-01 ↔ IN-PRD-04).** The integration tests in IN-PRD-04 (`test_stub_platform_meta_variant.py`, `test_stub_platform_mailchimp_variant.py`) are the acceptance test for whether IN-PRD-01's substrate design is truly platform-generic. If IN-PRD-04 ends up modifying `oauth.py` or `refresh.py` with `platform_id == "..."` branches, the design needs a revisit before Meta ships. The AC-level guard is `grep -rn 'platform_id == "meta"\|platform_id == "mailchimp"' api/src/kene_api/integrations/oauth.py api/src/kene_api/integrations/refresh.py` yielding zero hits.
- **Consumer protocol (IN-PRD-02 ↔ Data Pipeline / Agent Factory).** The four-step consumer protocol (`credential-read → use token → 401 → mark-expired`) is documented in §7.3 below. Downstream components follow it; Integrations doesn't chase consumers. Any deviation (e.g., a consumer deciding to cache tokens itself) is a protocol violation and should fail a code review.
- **Legacy cutover (IN-PRD-02 ↔ IN-PRD-06 ↔ AH-PRD-02).** AH-PRD-02 ships `_make_header_provider(auth_type)` reading session-state credential keys. IN-PRD-02 drops `# TODO(IN-PRD-06)` markers at each call site but does not modify the closure. IN-PRD-06 flips the body — the closure signature, `header_provider=` plumbing, and specialists remain untouched. The AC-level guards are the grep checks in IN-PRD-06 §7 #6.

### 5.4 Recommended workflow

1. **Sprint 1:** IN-PRD-01 lands (4 days, backend). No downstream work possible yet — gate.
2. **Sprint 2:** IN-PRD-02 lands (4 days, backend). DP-PRD-02 can start in parallel against the Integrations internal credential-read (with IN-PRD-02's stub fallback).
3. **Sprint 3:** IN-PRD-03 (frontend team) and IN-PRD-04 (backend team) run in parallel. IN-PRD-05's backend half (`mark-expired`, `on-user-removed`, stuck-expired watchdog) can start once IN-PRD-02 is done; the notification-UI half waits for IN-PRD-03's deep-link page.
4. **Sprint 4:** IN-PRD-06 capstone — E2E suite, KMS rotation drill in dev, AH-PRD-02 retrofit, docs sweep. Finalize feature-flag defaults. Verification report appended to this README.
5. **Sprint 4 or fast-follow:** IN-PRD-07 on-demand Test-connection — endpoint + Settings button + MCP tool. Can run in parallel with IN-PRD-06 (no substrate conflicts) or slip a sprint if IN-PRD-06 absorbs the team.

## 6. Global Document References

| Document | Relevant Sections | Why |
|----------|-------------------|-----|
| Root `CLAUDE.md` | §2 While Coding, §3 Testing, §4 Database, §6 Tooling Gates | Branded types (C-5), Pydantic (PY-2), context managers for DB + KMS (PY-5, D-1), test conventions (T-1..T-8), lint gates (G-1..G-3). |
| `api/CLAUDE.md` | Firestore access patterns, Secret Manager integration, OIDC for internal endpoints | Before building the KMS service, the state-token service, or any internal endpoint. |
| `frontend/CLAUDE.md` | CSS architecture, shadcn/ui, branded types, TanStack Query | Before building any component under `pages/settings/integrations/`. |
| [`../../DESIGN-REVIEW-LOG.md`](../../DESIGN-REVIEW-LOG.md) | Entry dated the IN-PRD-06 completion | Rationale for the substrate-plus-declarative-platforms design, and the AH-PRD-02 retrofit. (To be authored during IN-PRD-06.) |
| [`./implementation-plan.md`](./implementation-plan.md) | Entire document | Full component design narrative + open-questions resolution log. Reference while reviewing a project PRD if a decision feels implicit — the rationale is probably here. |
| `docs/KEN-E-System-Architecture.md` | §1.6 Component Landscape — Integrations row | Cross-component orientation. Updated to drop any `[PLANNED]` tags during IN-PRD-06. |

## 7. Conventions and Constraints

### 7.1 Token handling

- **Plaintext lives in memory only.** `KMSEncryptionService.decrypt(...)` returns plaintext that never gets written to Firestore, logs, Weave spans, or HTTP response bodies other than the OIDC-scoped `credentials` endpoint response. Enforced by a lint rule on `write_connection_audit` metadata and by code review on router responses.
- **KMS key never leaves GCP.** The service account has only `cloudkms.cryptoKeyEncrypterDecrypter`. No `cryptoKeyVersions.destroy` binding. No key export, ever.
- **`kms_key_version` is advisory on decrypt** (KMS auto-resolves the version from ciphertext metadata), but persisted so the rewrap sweeper can target old-version tokens.
- **Tokens live in a subcollection under the connection** (`tokens/{kind}`) so revocation is a single `firestore.recursive_delete(...)` and plaintext / ciphertext never appears at the connection-document level.

### 7.2 OAuth state tokens

- **Signed JWT, stateless.** `StateTokenService.issue(user_id, account_id, platform_id)` returns a JWT signed with the env HMAC key. `verify(jwt)` enforces signature + `exp` + one-time nonce usage.
- **10-minute expiry.** OAuth flows that take longer than 10 min between initiate and callback are rejected. Acceptable for real users; abandoned flows simply expire.
- **One-time nonces.** `integrations_state_nonces/{nonce}` is written on callback with a 15-min Firestore TTL. Replayed callbacks 400. No cleanup job — TTL handles it.
- **HMAC key rotation** is a runbook step under `operations/` (not yet authored; added in IN-PRD-06). Rotation invalidates in-flight flows only; no persisted-data migration needed.

### 7.3 Consumer protocol for credential reads

Any component that needs a platform token follows this exact pattern — no exceptions.

1. `GET /api/v1/internal/integrations/credentials/{account_id}/{platform_id}` with the service's OIDC token.
2. Use the returned `access_token` against the platform. **Do not cache it across tasks** — re-read at the start of each unit of work so refresh events propagate.
3. On platform 401 (or equivalent): `POST /api/v1/internal/integrations/connections/{connection_id}/mark-expired` with `{account_id, reason}`.
4. Fail the current task / run with `needs_reauth` status. The existing task revision loop handles retry once the connection is back.

Tokens never flow through ADK session state, Firestore outside `platform_connections/*`, Weave span attributes, or HTTP response bodies to non-OIDC callers. If a component *feels like* it should cache, the caller has the scope wrong — revisit per-task boundaries instead.

### 7.4 Platform definitions

- **New platforms are a Firestore seed, not code.** `PlatformDefinition` is declarative. The only platform-specific Python in the codebase is (a) the `google.py` module for account-label fetching and scope assembly (consumed once, during connect), and (b) helpers in the stub platform. If adding a platform requires touching `oauth.py` or `refresh.py`, the substrate design needs extending — see §5.3's grep guard.
- **`auth_type` is `Literal["oauth2_auth_code"]` in v1.** Service-account JSON + API-key + other auth modes are explicitly deferred per [`implementation-plan.md`](./implementation-plan.md) §10 Q1.
- **`platform_version` bumps invalidate existing connections.** Bump it on any change to scopes or endpoints; a migration step seeds the new version and forces affected users to reconnect on next use. `PlatformConnection.platform_version_at_connect` records the version in effect at connect time.
- **Incremental scopes per connection.** A single shared OAuth app (e.g., one `google` platform for GA + Ads) requests different scopes per initiate call based on the downstream consumer's needs. Granted scopes are persisted on `PlatformConnection.scope` so consumers can check before using.

### 7.5 Connection ownership + lifecycle

- **Connections are account-scoped, not user-scoped.** Every account member can invoke jobs that use them; only account admins can disconnect or force-refresh.
- **`connected_by_user_id` is informational** — shown in the UI so teams know who wired things up — not an access-control field.
- **When a user is removed from an account, every connection they authored is revoked + deleted.** No orphaned connections; no "detached" connections with an unknown owner. Handled by `on_user_removed(account_id, user_id)` (IN-PRD-05). Remaining admins are notified and expected to reconnect under a different user.
- **Scope editing is revoke-and-reconnect.** There is no in-place scope expansion. Users who need additional scopes disconnect and reconnect. v2 may add in-place; v1 does not.

### 7.6 Re-auth notifications

- **One notification category:** `NotificationCategory.INTEGRATION_NEEDS_REAUTH`. Every trigger (refresh failure, consumer 401, user removal) routes through it.
- **24-hour per-connection dedup.** `PlatformConnection.last_reauth_notification_sent_at` caps emission to once per connection per 24h. Consumers that retry on a dead connection don't storm users.
- **Deep-link template:** `/settings/integrations/{connection_id}` (for expirations) or `/settings/integrations` (for user-removal revocations, where the connection is deleted). IN-PRD-03 handles the pulse-animation + auto-focus Reconnect on deep-link load.
- **Stuck-expired watchdog alerts internally.** Connections stuck in `status=expired` for >7 days emit a single batched PagerDuty / Slack alert once per day. Not user-facing.

### 7.7 Firestore layout (Shape B + Shape C)

- `platform_definitions/{platform_id}` — Shape C carve-out (global, not account-scoped). Matches the `feature_flags` pattern.
- `accounts/{account_id}/platform_connections/{connection_id}` — Shape B subcollection.
- `accounts/{account_id}/platform_connections/{connection_id}/tokens/{kind}` — Shape B nested subcollection; token documents contain only `ciphertext + kms_key_version + expires_at + updated_at` fields.
- `accounts/{account_id}/integrations_audit/{audit_id}` — Shape B. Composite index: `(event ASC, timestamp DESC)`.
- `integrations_state_nonces/{nonce}` — Shape C with 15-min TTL policy. Replay defense only.

### 7.8 Feature-flag structure

- **Component-level kill switches:** `integrations_enabled` (user-facing endpoints; internal credential-read is unconditional), `integrations_ui_enabled` (Settings tab), `integrations_reauth_lifecycle_enabled` (notification emission — status transitions still happen regardless), `integrations_connection_test_enabled` (IN-PRD-07's on-demand Test-connection endpoint + Settings button + MCP tool; when off: endpoint 404s, button hidden, tool unregistered).
- **Per-platform kill switches:** `integration_google_enabled`, `integration_meta_enabled`, `integration_mailchimp_enabled`. Platform disappears from `/platforms` + `initiate` 404s when off. Internal credential-read still works for existing connections (so already-running consumer tasks can finish; disconnect the platform to really kill it).
- **IN-PRD-06 flips component-level flags on in prod by default.** Per-platform flags remain as the ongoing kill switches.

### 7.9 Standard shape for a project PRD in [`projects/`](./projects/)

Every PRD follows the shared 10-section structure used across sibling components:

1. Context — problem this PRD solves
2. Scope — explicit in/out
3. Dependencies — other PRDs, files, services
4. Data contract — Pydantic / TypeScript types owned or consumed
5. Implementation outline — files to create / modify (table)
6. API contract — endpoints (where applicable)
7. Acceptance criteria — what "done" means
8. Test plan — unit / integration / E2E coverage
9. Risks & open questions
10. Reference — links back to sibling PRDs, upstream design docs

---

<!-- PRD MAINTENANCE NOTES

Updating this PRD:
- When a new platform seed lands (Google Ads split from `google`, HubSpot, TikTok, etc.): no doc change needed unless the substrate contract changed. Update §7.4 only if the `PlatformDefinition` schema grew.
- When IN-PRD-06 completes: remove any [PLANNED] tags, update Status to "Active," append a Verification section (E2E results + rotation drill + grep-check output) at the end of §7, and cross-link from DESIGN-REVIEW-LOG.
- When a new consumer component starts using Integrations (e.g., Knowledge Graph ingestion): add a row under §3.2 Depended On By, and verify they follow the §7.3 consumer protocol in their PRD.
- When architecture changes (new worker, new endpoint, new storage path): update §2.
- When a new runbook is authored in operations/: link it from §2.1.

This PRD is read by the Dev Team agent during implementation planning (CLAUDE.md §Context Loading Sequence, Step 1). Keep it concise — every sentence should help a dev write better code or avoid mistakes.
-->
