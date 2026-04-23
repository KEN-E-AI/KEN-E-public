# Integrations — Implementation Plan

**Status:** Draft — 2026-04-23
**Owner:** Integrations component team (TBD)
**Proposed PRD prefix:** `IN-PRD-NN`

---

## 1. What Integrations is

The Integrations component is KEN-E's **third-party credential substrate**. It owns the OAuth flow per platform, the encrypted token store, the refresh lifecycle, the per-account multi-user sharing semantics, and the revocation / re-auth flow. Every component that talks to a third-party platform — Data Pipeline connectors, Agent Factory tools, future Knowledge Graph ingestion — reads credentials through this component.

Three facts shape the design:

1. **Connections are account-scoped, not user-scoped.** When a user authorizes "My Business's GA account", the resulting tokens belong to the KEN-E account. Every user with access to that account can invoke jobs that use them. This matches marketing-team workflows where one person sets up the integration and the whole team benefits.
2. **Tokens are KMS-encrypted at rest.** The encryption key lives in Google Cloud KMS; decrypted tokens exist only in-memory on the service that needs them. A stolen Firestore export does not yield usable credentials.
3. **Re-auth is first-class.** Tokens expire, scopes change, users revoke access. The component emits a standard "re-auth required" notification via the existing notification system; every consumer handles it the same way — hold the task, surface the notification, restore on reconnection.

## 2. What exists today (before Integrations)

This is a foundational component. The OAuth patterns have been sketched piecemeal across AH-PRD-02 (`_make_header_provider(auth_type)`) and AH-PRD-03 (`ga_credentials` lifecycle), but no single doc owns the full substrate. Integrations consolidates those patterns.

| Upstream | What it gives us |
|---|---|
| **DM-PRD-00** (Migration Foundation) | Shape B convention + migration framework for new `platform_definitions` / `accounts/*/platform_connections` collections. |
| **DM-PRD-07** (Approval & Audit) | `AuditEntry` schema + `write_audit` helper for lifecycle events. |
| **Notifications** (existing) | `create_notification` + `NotificationCategory`. Integrations adds `"Integration Needs Re-auth"`. |
| **GCP KMS + Secret Manager** | Env-specific encryption key + per-platform OAuth client secrets. |

## 3. Data-model

### 3.1 Pydantic shapes

```python
class PlatformDefinition(BaseModel):
    platform_id: str                       # "google_analytics" | "google_ads" | "meta_ads" | ...
    display_name: str                      # "Google Analytics"
    oauth_authorization_url: str
    oauth_token_url: str
    oauth_revoke_url: str | None
    scopes: list[str]
    redirect_uri_template: str             # "/integrations/callback/{platform_id}?env={env}"
    auth_type: Literal["oauth2_auth_code"]   # v1 only — service_account + api_key deferred
    client_id_secret_ref: str              # Secret Manager ref for OAuth client_id
    client_secret_secret_ref: str          # Secret Manager ref for OAuth client_secret
    supports_refresh: bool
    refresh_lookahead_seconds: int = 300   # pre-emptive refresh if token expires within this window
    health_check_endpoint: str | None      # optional URL pinged post-callback to validate tokens + scopes
    platform_version: int                  # bump when scopes / endpoints change

class PlatformConnection(BaseModel):
    connection_id: str                     # UUID
    account_id: str
    platform_id: str
    status: Literal["connected", "expired", "revoked", "error"]
    connected_by_user_id: str              # KEN-E user who initiated the flow
    connected_at: datetime
    last_refreshed_at: datetime | None
    last_used_at: datetime | None
    scope: list[str]                       # granted scopes (may be subset of requested)
    external_account_label: str | None     # "GA4 property: 123456789 (ken-e.com)"
    external_account_id: str | None        # platform-native ID for reference
    platform_version_at_connect: int
    error_message: str | None

class EncryptedToken(BaseModel):
    connection_id: str
    kind: Literal["access_token", "refresh_token", "id_token"]
    ciphertext: bytes                      # KMS-encrypted; decrypted only in-memory
    kms_key_version: str                   # for rotation tracking
    expires_at: datetime | None
    updated_at: datetime

class ConnectionAuditEntry(BaseModel):
    audit_id: str
    connection_id: str
    account_id: str
    actor_id: str                          # user ID or "system"
    event: Literal["connected", "refreshed", "revoked", "reauth_requested", "used", "error"]
    timestamp: datetime
    metadata: dict                         # platform-specific context
```

### 3.2 Firestore layout (Shape B)

| Path | Purpose |
|---|---|
| `platform_definitions/{platform_id}` | Global catalog (Shape B carve-out) |
| `accounts/{account_id}/platform_connections/{connection_id}` | Per-account connection state |
| `accounts/{account_id}/platform_connections/{connection_id}/tokens/{kind}` | Encrypted token subcollection (access / refresh / id) |
| `accounts/{account_id}/integrations_audit/{audit_id}` | Lifecycle audit log |

Tokens live in a subcollection under the connection so a revoke is a single recursive-delete and tokens never appear at the connection-document level (defense in depth).

### 3.3 KMS encryption scheme

- Per-environment encryption key in Cloud KMS: `projects/kene-{env}/locations/us/keyRings/integrations/cryptoKeys/token-encryption`.
- `EncryptedToken.ciphertext` is the KMS encryption of `json.dumps({access_token, refresh_token, ...})` scoped to the connection.
- Decrypt happens in-memory on the caller service; no plaintext is written anywhere.
- Key rotation is opaque to callers: Integrations tracks `kms_key_version` per token and re-encrypts on next refresh; a background job re-wraps old tokens after a rotation event.

### 3.4 Execution model

- **Deployment target:** colocated with the main API (FastAPI router). OAuth flows are lightweight HTTP; volume is low; colocation avoids cross-service latency for the hot path (credential reads from Data Pipeline / Agent Factory).
- **Credential-read endpoint:** `GET /api/v1/internal/integrations/credentials/{account_id}/{platform_id}` is OIDC-authed, called by Data Pipeline connectors and Agent Factory tools. Returns decrypted `{access_token, expires_at, external_account_id}`; emits a `used` audit event.
- **Refresh:** on credential read, if `expires_at` is within `refresh_lookahead_seconds`, refresh synchronously (adds ~200ms to the first read in a window); otherwise return cached.
- **Revoke:** `DELETE /connections/{connection_id}` calls the platform's revoke endpoint (best-effort) and recursive-deletes tokens immediately.
- **Post-callback health check:** after the token exchange succeeds, if `PlatformDefinition.health_check_endpoint` is set, Integrations issues one authenticated request to it (<1s timeout). A non-2xx response aborts the connect, surfaces a scope/permission error to the UI, and discards the just-exchanged tokens. Adds ~500ms–1s to the connect flow; catches wrong-scope issues before any downstream job hits a 401.
- **Concurrency on refresh:** use Firestore transactions on the connection doc to prevent thundering-herd refreshes when multiple services request credentials simultaneously.
- **Observability:** every credential read, refresh, and revoke emits a Weave span (`integrations.credential_read`, `integrations.refresh`, `integrations.revoke`) with `{platform_id, account_id_hash, cache_hit, latency_ms}`.

## 4. API surface

### User-facing (OAuth lifecycle)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/integrations/{account_id}/connections/{platform_id}/initiate` | Start OAuth; returns authorization URL + opaque `state` token. |
| `GET` | `/api/v1/integrations/callback/{platform_id}` | OAuth callback; exchanges code for tokens, persists, redirects to UI. |
| `POST` | `/api/v1/integrations/{account_id}/connections/{connection_id}/refresh` | Force a refresh (admin tool; normally automatic). |
| `DELETE` | `/api/v1/integrations/{account_id}/connections/{connection_id}` | Revoke + delete. Marks downstream consumers as "needs re-auth". |

### Management (UI reads)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/integrations/{account_id}/connections` | List for the account; returns status + label + last-used. |
| `GET` | `/api/v1/integrations/{account_id}/connections/{connection_id}` | Full details (no tokens returned). |
| `GET` | `/api/v1/integrations/platforms` | Available platform definitions + whether the account has an active connection. |
| `GET` | `/api/v1/integrations/{account_id}/audit` | Lifecycle audit log (filters: connection_id, event, date). |

### Internal (service-to-service)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/internal/integrations/credentials/{account_id}/{platform_id}` | OIDC; returns decrypted `{access_token, expires_at, external_account_id}`. Refreshes transparently if within the lookahead window. |

## 5. Interaction with existing + concurrent components

### 5.1 Agentic Harness

AH-PRD-02's `_make_header_provider(auth_type)` is superseded by a call to `GET /internal/integrations/credentials/...`. The agent-factory config field `auth_type` becomes a `platform_id` reference; the factory injects a thin credential-fetcher into each ADK tool's `tool_context`. AH-PRD-02 + AH-PRD-03 get a follow-up patch in IN-PRD-06 to remove the old pattern.

### 5.2 Data Pipeline

Connectors load credentials via Integrations, not from a custom decrypt layer. DP-PRD-02 blocks on IN-PRD-02 (Google OAuth). DP-PRD-05 (Meta + Mailchimp) blocks on IN-PRD-04.

### 5.3 Notifications

New category: `"Integration Needs Re-auth"`. Routed by Integrations on refresh failure + 401 detection from downstream consumers. Notification deep-links to `/settings/integrations/{connection_id}`.

### 5.4 Feature Flags

Per-platform flags (`integration_google_enabled`, `integration_meta_enabled`, etc.) let us dark-launch new platforms without shipping a new KEN-E release.

### 5.5 Account / user lifecycle

When a user is removed from an account, every `PlatformConnection` they authored (`connected_by_user_id == removed_user_id`) is revoked and deleted. The account-management flow calls `POST /internal/integrations/on-user-removed {account_id, user_id}`; Integrations iterates the account's connections, best-effort-revokes each at the platform, recursive-deletes tokens, writes an audit entry (`actor_id = "system:user_removed"`, `event = "revoked"`), and emits a notification to remaining account admins naming each revoked connection so they can reconnect under a different user. Downstream tasks using those connections fail fast with the standard re-auth path.

## 6. Phasing

Six PRDs. Proposed prefix: `IN-PRD-NN`.

### IN-PRD-01 — Core model + encryption

**Delivers:** All Pydantic shapes; Firestore layout + migration; `PlatformDefinition` catalog doc + seed migration; `KMSEncryptionService` wrapping Cloud KMS (env-keyed); `EncryptedToken` write/read helpers; `ConnectionAuditEntry` + `write_audit` integration with DM-PRD-07; `StateTokenService` issuing and verifying HMAC-signed JWT state tokens (10-min expiry, signing key in Secret Manager, per-env rotation runbook); `StubPlatform` for contract tests (deterministic in-memory fake OAuth server).

**Exit criteria:** a stub OAuth flow completes end-to-end (initiate → callback with fake code → stored + KMS-encrypted → retrieve via internal endpoint → plaintext appears only in-memory).

**Blocked by:** DM-PRD-00, DM-PRD-07.

**Blocks:** IN-PRD-02, DP-PRD-01 (soft — DP-PRD-01 can stub via `StubPlatform` and swap to IN-PRD-02 during DP-PRD-02).

**Effort:** 4 days.

### IN-PRD-02 — Google OAuth flow

**Delivers:** `google` platform definition (shared OAuth app for GA + Google Ads — incremental scopes per connection) including `health_check_endpoint` pointing at a low-cost GA/Ads read that validates scope; client_id / secret wired to Secret Manager per env; authorization + callback endpoints against real Google OAuth; post-callback health check that aborts the connect on non-2xx; refresh-token lifecycle (pre-emptive refresh within `refresh_lookahead_seconds`); idle-token cleanup cron (revoke connections inactive for 90 days); integration tests against Google OAuth sandbox.

**Exit criteria:** a user connects Google via UI → post-callback health check passes → Data Pipeline GA jobs can read tokens → expiring tokens auto-refresh without user action → revoke propagates in <30s. An intentionally under-scoped OAuth grant is rejected at connect time by the health check (not at first job run).

**Blocked by:** IN-PRD-01.

**Blocks:** IN-PRD-03, DP-PRD-02, AH-PRD-03 refactor.

**Effort:** 4 days.

### IN-PRD-03 — Connection-management UI

**Delivers:** Integrations tab on the Settings page (`/settings/integrations`) listing platforms; per-platform connection card showing the **display name of the user who connected it** (resolved from `connected_by_user_id`), status badge, last-used timestamp, and scope chips; "Connect" button invoking the initiate flow; "Disconnect" button with confirmation (warns about downstream job impact); re-auth flow from notification deep-link; admin "force refresh" control; per-connection audit-log drawer.

**Exit criteria:** a user views, connects, and disconnects integrations from the UI without API calls; re-auth flow is fully self-serve.

**Blocked by:** IN-PRD-02.

**Blocks:** IN-PRD-05, DP-PRD-04 (custom-job authoring needs the connection picker).

**Effort:** 3 days.

### IN-PRD-04 — Meta + Mailchimp platforms

**Delivers:** `meta` + `mailchimp` platform definitions + OAuth flows. Platform-specific quirks captured in `PlatformDefinition` metadata (not connector code): Meta's long-lived token exchange, Mailchimp's server-prefix-in-token-response handling, revoke-URL variants. Updates to `StubPlatform` tests proving the substrate is platform-generic.

**Exit criteria:** Meta + Mailchimp connections supported end-to-end; downstream DP-PRD-05 connectors pass integration tests.

**Blocked by:** IN-PRD-02.

**Blocks:** DP-PRD-05.

**Effort:** 3 days.

### IN-PRD-05 — Re-auth lifecycle

**Delivers:** re-auth detection hook (`POST /internal/integrations/connections/{id}/mark-expired` callable by any consumer on a 401); notification emission via the existing system; re-auth notification UI wired to `/settings/integrations/{id}`; background job refreshing connections pre-emptively; alerting on stuck "expired" connections (>7 days); deep-link template for consumer notifications; **user-removal handler** (`POST /internal/integrations/on-user-removed`) that revokes + deletes every connection authored by a removed user and notifies remaining admins of each revoked connection.

**Exit criteria:** on an expired token, a user receives exactly one re-auth notification; clicking it routes to the connection-management page; reconnection restores service for all downstream consumers. Removing a user who authored one or more connections revokes them within 30s, emits one notification per revoked connection to remaining admins, and the connection no longer appears in `/settings/integrations`.

**Blocked by:** IN-PRD-02, IN-PRD-03.

**Blocks:** IN-PRD-06.

**Effort:** 2 days.

### IN-PRD-06 — Integration testing + legacy cleanup

**Delivers:** E2E suite — new account → connect Google → DP GA job runs → tokens auto-refresh → user revokes → downstream task fails with re-auth notification → user reconnects → task retries + succeeds. KMS key-rotation playbook + live rotation test. Legacy `_make_header_provider` removed from AH-PRD-02 + AH-PRD-03 code paths; documentation sweep for component READMEs referencing Integrations as the credentials source.

**Exit criteria:** verification report appended; `grep -rn '_make_header_provider' api/src/` yields zero matches; KMS rotation runbook validated.

**Blocked by:** IN-PRDs 01–05.

**Blocks:** —

**Effort:** 2 days.

## 7. Dependency graph

```
┌───────────────────┐       ┌───────────────────┐
│    DM-PRD-00      │       │    DM-PRD-07      │
│   (migration)     │       │  (audit schema)   │
└─────────┬─────────┘       └─────────┬─────────┘
          │                           │
          └─────────────┬─────────────┘
                        ▼
              ┌───────────────────┐
              │     IN-PRD-01     │  Core model + encryption
              └─────────┬─────────┘
                        │
                        ▼
              ┌───────────────────┐
              │     IN-PRD-02     │  Google OAuth
              └─┬───────┬──────┬──┘
                │       │      │
        ┌───────┘       │      └──────┐
        ▼               ▼             ▼
  ┌──────────┐   ┌──────────┐   ┌──────────┐
  │IN-PRD-03 │   │IN-PRD-04 │   │DP-PRD-02 │  (consumer: Data Pipeline GA)
  │ Conn UI  │   │ Meta/MC  │   └──────────┘
  └────┬─────┘   └─────┬────┘
       │               │
       ▼               ▼
┌──────────┐     ┌──────────┐
│IN-PRD-05 │     │DP-PRD-05 │  (consumer: Data Pipeline Meta/MC)
│ Re-auth  │     └──────────┘
└────┬─────┘
     │
     ▼
┌──────────┐
│IN-PRD-06 │  Integration testing + legacy cleanup
└──────────┘
```

## 8. Non-goals

- **End-user authentication.** That's Firebase Auth, not Integrations. This component is for third-party *platform* credentials.
- **Non-OAuth credential types.** v1 supports only OAuth 2.0 auth-code grant. Google service-account JSON uploads (useful in some enterprise Google Ads setups) and user-supplied API keys (copy-paste) are both deferred — most platforms we care about use OAuth, and starting single-mode keeps the substrate simple.
- **Webhook receivers from platforms.** Inbound webhooks (a platform pushing to KEN-E) are a separate concern; likely a future `integrations-inbound` component or folded into Data Pipeline.
- **Developer-portal OAuth for KEN-E's own public API.** When KEN-E exposes its own OAuth-able API, that's a different component (API Gateway / developer-portal).
- **Cross-account connection sharing.** An agency managing multiple accounts connects once per account. Shared connections across accounts deferred.
- **Scope editing after connect.** Users revoke + reconnect to change scopes; no in-place scope expansion in v1.

## 9. Risks

| Risk | Mitigation |
|---|---|
| KMS key rotation breaks existing tokens | `kms_key_version` tracked per token; background re-wrap job; rotation runbook tested in IN-PRD-06. |
| Multi-account sharing of one OAuth app → scope creep risk | Scopes requested per connection (incremental), not app-wide; granted scopes stored on connection so consumers can check before using. |
| Redirect URI management across envs | Templated in `PlatformDefinition`; env interpolated at initiate time; each env's OAuth app has its own approved list. |
| Token refresh race under concurrent reads | Firestore transaction on the connection doc; lock duration capped at 5s; callers retry. |
| Revocation race: user revokes while a long-running job has cached credentials | Accept. Callers that start a run cache credentials for the run's duration; the next run will fail + re-auth. |
| Platform changes its OAuth URL / scopes | `platform_version` on `PlatformDefinition`; bump invalidates existing connections (forces reconnect); migration script seeds new version. |
| Stolen Firestore export yields ciphertexts an attacker can brute-force | KMS key never leaves GCP; compromise requires KMS access, not just Firestore access. |
| Consumer service leaks plaintext token to logs | Code-review gate: no token value ever enters a structured log field; Weave spans only carry `platform_id` + hashes. Enforced by a lint rule. |

## 10. Open questions

1. ~~**Service-account JSON uploads.**~~ **Resolved (2026-04-23):** defer in v1. Only OAuth 2.0 auth-code grant is supported; `auth_type` Literal narrowed. See §8.
2. ~~**Per-user vs. per-account connection UX.**~~ **Resolved (2026-04-23):** the display name of the user who connected the integration must be shown on the connection card in the Integrations tab of Settings. Reflected in IN-PRD-03.
3. ~~**Removed-user cleanup.**~~ **Resolved (2026-04-23):** when a user is removed from an account, revoke + delete every connection they authored (do not keep the connection under a detached `connected_by_user_id`). Handled by the `on-user-removed` hook in IN-PRD-05; cross-component wiring in §5.5.
4. ~~**OAuth state-token storage.**~~ **Resolved (2026-04-23):** signed JWT. On initiate, Integrations issues a JWT encoding `{user_id, account_id, platform_id, nonce, exp}` (10-min expiry) signed with an internal HMAC key from Secret Manager; the JWT *is* the `state` parameter. On callback, verify signature + exp and extract claims. No Firestore round-trips; audit lives on `ConnectionAuditEntry` from the callback onward. Implementation detail for IN-PRD-01.
5. ~~**Connection testing at connect time.**~~ **Resolved (2026-04-23):** yes, add a platform-configurable `health_check_endpoint` on `PlatformDefinition`; invoked post-callback, a failure aborts the connect. Reflected in §3.1, §3.4, and IN-PRD-02 exit criteria.

## 11. Success criteria

- OAuth flow (initiate → callback → validated connection) completes in <30s p95.
- Tokens refresh automatically 5 min before expiry — no user-visible task stalls due to refresh.
- Revocation propagates to Data Pipeline + Agent Factory in <30s.
- `gcloud firestore export` of a connected account yields no plaintext tokens (KMS-encrypted at rest verified by inspection).
- `grep -rn '_make_header_provider\|ga_credentials\[' api/src/` yields zero matches after IN-PRD-06.
- Re-auth notification → reconnection → downstream task recovery in <5 minutes user-time (clicking the notification, completing OAuth, seeing the task retry).
- KMS key rotation completes with zero token-read failures during the rotation window (validated via IN-PRD-06 live-rotation test).
