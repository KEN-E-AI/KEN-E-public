# IN-PRD-01 — Core Model + Encryption

**Status:** Not started
**Owner team:** Integrations component team (backend)
**Blocked by:** [DM-PRD-00](../../data-management/projects/DM-PRD-00-migration-foundation.md) (Shape B convention + migration framework), [DM-PRD-07](../../data-management/projects/DM-PRD-07-approval-workflow-and-audit.md) (`AuditEntry` schema + `write_audit` helper)
**Parallel with:** FF-PRD-01 (Feature Flags data model) — both are foundation-release backend projects with no cross-dependency
**Blocks:** IN-PRD-02, IN-PRD-04 (via IN-PRD-02), DP-PRD-01 (soft — can stub via `StubPlatform` and swap to IN-PRD-02 during DP-PRD-02)
**Estimated effort:** 4 days backend

---

## 1. Context

Integrations is KEN-E's third-party credential substrate. It owns the OAuth flow per platform, the encrypted token store, the refresh lifecycle, the per-account multi-user sharing semantics, and the revocation / re-auth flow. Every component that talks to a third-party platform — Data Pipeline connectors, Agent Factory tools, future Knowledge Graph ingestion — reads credentials through this component. See [`../implementation-plan.md`](../implementation-plan.md) for the full component design.

This project lays the foundation: the Pydantic shapes, the Firestore layout (Shape B), KMS-encrypted token storage, the OAuth state-token service (signed JWT), the audit writer, and a `StubPlatform` contract-test fake OAuth server. It ships no real platform integration — that's IN-PRD-02. The validation checkpoint here is that a stub OAuth flow completes end-to-end (initiate → callback with fake code → stored + KMS-encrypted → retrieve via internal endpoint → plaintext appears only in-memory).

Landing the substrate first, without any real platform, lets downstream projects (DP-PRD-01 Data Pipeline foundation, AH-PRD-02 Agent Factory) build against `StubPlatform` if they ship in parallel. Once IN-PRD-02 adds Google, they swap.

## 2. Scope

### In scope
- **Pydantic models** for `PlatformDefinition`, `PlatformConnection`, `EncryptedToken`, `ConnectionAuditEntry` (shapes in §4).
- **Firestore layout** — new collections `platform_definitions/*` (global Shape B carve-out) and subcollections under `accounts/{account_id}/` for connections, tokens, and audit. Terraform composite indexes where needed.
- **`PlatformDefinition` catalog seed migration** — empty catalog shipped; IN-PRD-02 adds `google`.
- **`KMSEncryptionService`** wrapping Cloud KMS with env-specific key (`projects/kene-{env}/locations/us/keyRings/integrations/cryptoKeys/token-encryption`). Encrypt/decrypt helpers tracking `kms_key_version` per ciphertext. Key-rotation re-wrap is deferred to IN-PRD-06's rotation playbook; service tracks the field but does not yet sweep.
- **`EncryptedToken` write/read helpers** — tokens live at `accounts/{account_id}/platform_connections/{connection_id}/tokens/{kind}` so a revoke is one recursive-delete and plaintext never appears at the connection-document level.
- **`ConnectionAuditEntry` + `write_audit` integration** — lifecycle events (`connected`, `refreshed`, `revoked`, `reauth_requested`, `used`, `error`) persisted under `accounts/{account_id}/integrations_audit/{audit_id}` via the DM-PRD-07 helper.
- **`StateTokenService`** — issues and verifies HMAC-signed JWT state tokens for OAuth CSRF defense. Signing key in Secret Manager (`sm://integrations-state-token-hmac-{env}`), 10-minute expiry, rotation runbook referenced in IN-PRD-06. JWT claims: `{user_id, account_id, platform_id, nonce, exp}`.
- **Internal credential-read endpoint** — `GET /api/v1/internal/integrations/credentials/{account_id}/{platform_id}` (OIDC-authed). Returns decrypted `{access_token, expires_at, external_account_id}`. Emits a `used` audit event. Pre-emptive refresh wiring is a stub here (no refresh yet — IN-PRD-02 fills it in); for the stub platform, the endpoint returns the stored stub token as-is.
- **`StubPlatform`** — deterministic in-memory fake OAuth server for contract tests. Runs as a FastAPI router under `/api/v1/_test/stub-platform/` behind a non-production flag. Issues predictable codes + tokens; lets IN-PRD-01's end-to-end test exercise initiate → callback → store → read without any external network dependency.
- **OAuth initiate + callback scaffolding** — `POST /api/v1/integrations/{account_id}/connections/{platform_id}/initiate` and `GET /api/v1/integrations/callback/{platform_id}` wired generically from `PlatformDefinition`, exercised end-to-end against `StubPlatform` only.
- **Weave spans** — `integrations.credential_read`, `integrations.store_token`, `integrations.stub_oauth_flow` with `{platform_id, account_id_hash, latency_ms}` (no token values ever on a span).
- **Feature flag** — `integrations_enabled` kill switch on all user-facing endpoints (internal credential-read endpoint is unconditional).

### Out of scope
- Real platform OAuth (Google, Meta, Mailchimp) — IN-PRD-02 and IN-PRD-04.
- Refresh-token lifecycle logic — IN-PRD-02.
- Connection-management UI — IN-PRD-03.
- Re-auth notifications + user-removal hook — IN-PRD-05.
- KMS key-rotation sweeper job — IN-PRD-06 (field tracked here, worker not built).
- Inbound webhooks from platforms — separate future component.
- Non-OAuth auth types (service-account JSON, API keys) — deferred; `PlatformDefinition.auth_type` Literal is narrowed to `"oauth2_auth_code"` in v1.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[DM-PRD-00](../../data-management/projects/DM-PRD-00-migration-foundation.md)** | Shape B convention + `api/scripts/migrate_to_shape_b.py` CLI + `_migrate_shape_b/resources.py` registry. New subcollections under `accounts/{account_id}/` are created via this framework. | `../../data-management/README.md` §2.2 Data Flow |
| **[DM-PRD-07](../../data-management/projects/DM-PRD-07-approval-workflow-and-audit.md)** | `AuditEntry` schema + `write_audit(actor_id, event, ...)` helper. Integrations defines a subclass `ConnectionAuditEntry` with platform-specific metadata and uses the shared writer. | `../../data-management/README.md` audit section |
| Cloud KMS | Per-environment `token-encryption` key under the `integrations` key ring. Terraform adds the keys + IAM bindings to the API service account (encrypt + decrypt only; no key export). | `deployment/terraform/` |
| Secret Manager | Per-environment secret `integrations-state-token-hmac-{env}` holding the JWT signing key. Rotation cadence owned by the IN-PRD-06 runbook. | `deployment/terraform/` |
| Existing API auth | OIDC-authed internal endpoint pattern reused from Data Pipeline / Agent Engine callbacks. | `api/src/kene_api/auth/` |

## 4. Data contract

### Pydantic shapes

```python
class PlatformDefinition(BaseModel):
    platform_id: str                       # "google_analytics" | "google_ads" | "meta_ads" | ...
    display_name: str                      # "Google Analytics"
    oauth_authorization_url: str
    oauth_token_url: str
    oauth_revoke_url: str | None
    scopes: list[str]
    redirect_uri_template: str             # "/integrations/callback/{platform_id}?env={env}"
    auth_type: Literal["oauth2_auth_code"] # v1 only — service_account + api_key deferred
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
    actor_id: str                          # user ID or "system:<subtype>"
    event: Literal["connected", "refreshed", "revoked", "reauth_requested", "used", "error"]
    timestamp: datetime
    metadata: dict                         # platform-specific context (no token values)

class StateTokenClaims(BaseModel):
    user_id: str
    account_id: str
    platform_id: str
    nonce: str                             # 128-bit random, also stored so a used nonce can't replay
    exp: datetime                          # 10-min expiry
```

### Firestore layout (Shape B)

| Path | Purpose |
|---|---|
| `platform_definitions/{platform_id}` | Global catalog (Shape B carve-out for non-account-scoped configs) |
| `accounts/{account_id}/platform_connections/{connection_id}` | Per-account connection state |
| `accounts/{account_id}/platform_connections/{connection_id}/tokens/{kind}` | Encrypted token subcollection (`access_token`, `refresh_token`, `id_token`) |
| `accounts/{account_id}/integrations_audit/{audit_id}` | Lifecycle audit log |
| `integrations_state_nonces/{nonce}` | 15-minute TTL record of used JWT nonces (replay defense); TTL via Firestore TTL policy |

Tokens live in a subcollection under the connection so a revoke is a single `firestore.recursive_delete(...)` and plaintext ciphertext never appears at the connection-document level (defense in depth).

### KMS encryption scheme

- Env key: `projects/kene-{env}/locations/us/keyRings/integrations/cryptoKeys/token-encryption`.
- `EncryptedToken.ciphertext` is the KMS encryption of `json.dumps({access_token, refresh_token, ...})` scoped to a single connection.
- Decrypt happens in-memory on the caller service; no plaintext is written anywhere.
- `kms_key_version` is recorded per token so IN-PRD-06's rotation sweeper can re-wrap old tokens after a rotation event.

## 5. Implementation outline

### 5.1 File inventory

| Action | File |
|--------|------|
| Create | `api/src/kene_api/models/integrations.py` — all Pydantic shapes |
| Create | `api/src/kene_api/integrations/__init__.py` |
| Create | `api/src/kene_api/integrations/kms.py` — `KMSEncryptionService` |
| Create | `api/src/kene_api/integrations/tokens.py` — `EncryptedToken` read/write helpers |
| Create | `api/src/kene_api/integrations/audit.py` — `write_connection_audit` wrapper over DM-PRD-07's `write_audit` |
| Create | `api/src/kene_api/integrations/state_tokens.py` — `StateTokenService` (issue + verify JWT) |
| Create | `api/src/kene_api/integrations/oauth.py` — generic `initiate()` + `handle_callback()` driven by `PlatformDefinition` |
| Create | `api/src/kene_api/integrations/stub_platform.py` — `StubPlatform` in-memory fake |
| Create | `api/src/kene_api/routers/integrations.py` — initiate + callback + internal credential-read |
| Create | `api/src/kene_api/routers/_test_stub_platform.py` — non-prod only, behind `ENV != "production"` gate |
| Create | `api/scripts/migrate_integrations_foundation.py` — registers the new Shape B paths + seeds empty `platform_definitions` catalog |
| Modify | `deployment/terraform/` — KMS key ring + key + IAM bindings; Secret Manager secret for state-token HMAC |
| Modify | `deployment/terraform/firestore.tf` — composite index on `accounts/{account_id}/integrations_audit` (`event, timestamp DESC`), TTL policy on `integrations_state_nonces` |
| Modify | `api/src/kene_api/main.py` — register routers behind `integrations_enabled` flag |
| Create | `api/tests/unit/integrations/test_kms.py`, `test_tokens.py`, `test_state_tokens.py`, `test_audit.py`, `test_oauth.py` |
| Create | `api/tests/integration/integrations/test_stub_end_to_end.py` — full initiate → callback → store → read loop |

### 5.2 OAuth initiate + callback flow (generic)

```text
initiate(account_id, platform_id):
  1. Load PlatformDefinition from Firestore.
  2. Resolve client_id from Secret Manager.
  3. Issue JWT state token via StateTokenService (claims include user_id, account_id, platform_id, nonce, exp=+10min).
  4. Build authorization URL from PlatformDefinition + scopes + state.
  5. Return { authorization_url }.

callback(platform_id, code, state):
  1. Verify JWT signature + exp; extract claims.
  2. Check nonce against integrations_state_nonces; reject if present; insert with 15-min TTL.
  3. Resolve client_secret from Secret Manager.
  4. POST to PlatformDefinition.oauth_token_url with { code, client_id, client_secret, redirect_uri }.
  5. If PlatformDefinition.health_check_endpoint is set, call it with the new access_token (<1s timeout).
     On non-2xx, skip persistence, audit "error", return a descriptive 400.
  6. KMS-encrypt tokens; persist EncryptedToken rows; create PlatformConnection with status=connected.
  7. write_connection_audit(event="connected", actor_id=user_id, metadata={platform_version_at_connect, granted_scopes}).
  8. Redirect to /settings/integrations/{connection_id}.
```

IN-PRD-01 exercises this against `StubPlatform` only; IN-PRD-02 wires the first real platform (Google).

### 5.3 `StubPlatform` contract

A non-production FastAPI router providing three endpoints that mimic OAuth behavior deterministically:

- `GET /api/v1/_test/stub-platform/authorize?client_id=...&redirect_uri=...&state=...&scope=...` — immediately 302s to `redirect_uri?code=stub_code_{nonce}&state={state}`.
- `POST /api/v1/_test/stub-platform/token` — accepts `code`; returns `{access_token: "stub_access_{nonce}", refresh_token: "stub_refresh_{nonce}", expires_in: 3600}`.
- `GET /api/v1/_test/stub-platform/health` — configurable response (default 200) so the health-check path can be exercised both ways in tests.

The `stub` `PlatformDefinition` is seeded into `platform_definitions/*` in the non-production environments only. The `_test_stub_platform.py` router is registered only when `ENV != "production"` to guarantee the fake isn't deployed to prod.

### 5.4 `KMSEncryptionService` contract

```python
class KMSEncryptionService:
    def __init__(self, key_name: str): ...
    def encrypt(self, plaintext: bytes) -> tuple[bytes, str]:
        """Returns (ciphertext, kms_key_version)."""
    def decrypt(self, ciphertext: bytes) -> bytes:
        """Uses key implied by the current key_name; KMS resolves the key version from ciphertext."""
```

Key facts:
- The encryption key never leaves GCP KMS.
- The KEN-E service account has only `cloudkms.cryptoKeyEncrypterDecrypter` on the key — no export, no destroy.
- Key version tracking is *advisory* — KMS handles actual decryption against any past version until it's disabled. We persist `kms_key_version` so IN-PRD-06's sweeper can target old-version tokens for re-wrapping.

## 6. API contract

### User-facing (OAuth lifecycle — generic)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/integrations/{account_id}/connections/{platform_id}/initiate` | Start OAuth; returns `{ authorization_url }`. Requires account access. |
| `GET` | `/api/v1/integrations/callback/{platform_id}` | OAuth callback; exchanges code for tokens, persists, redirects to UI. |

### Internal (service-to-service, OIDC)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/internal/integrations/credentials/{account_id}/{platform_id}` | Returns decrypted `{access_token, expires_at, external_account_id}`. Emits a `used` audit event. Refresh logic stubbed here (no-op for IN-PRD-01); IN-PRD-02 wires pre-emptive refresh. |

Both user-facing paths are gated by the `integrations_enabled` feature flag. The internal credential-read is not flag-gated (once a connection exists, downstream consumers must be able to read it regardless of user-facing UI state).

## 7. Acceptance criteria

1. **Pydantic shapes land** as specified in §4 under `api/src/kene_api/models/integrations.py`. `auth_type` Literal is narrowed to `"oauth2_auth_code"`.
2. **Firestore layout + migration** — `api/scripts/migrate_integrations_foundation.py` creates the required collections, seeds the empty `platform_definitions` catalog, configures the audit composite index, and sets the TTL policy on `integrations_state_nonces`.
3. **KMS wiring** — Terraform provisions per-env key ring + key + IAM bindings; `KMSEncryptionService.encrypt` produces ciphertext + `kms_key_version`; `decrypt` round-trips correctly. Unit test asserts plaintext never reaches Firestore fixture documents.
4. **State tokens are signed JWTs** — `StateTokenService.issue(...)` produces a JWT signed by the env HMAC key (pulled from Secret Manager). `verify(...)` enforces signature + exp and rejects used nonces (one-time use enforced via `integrations_state_nonces`).
5. **Audit integration** — `write_connection_audit(event, ...)` writes via the DM-PRD-07 `write_audit` helper; lifecycle events land under `accounts/{account_id}/integrations_audit/{audit_id}`. No token values appear in metadata.
6. **StubPlatform end-to-end test** — integration test exercises `initiate → authorize (stub 302) → callback → store → read` and asserts: (a) `PlatformConnection` row created with `status=connected`; (b) tokens stored KMS-encrypted in the subcollection; (c) internal credential-read returns decrypted `access_token`; (d) a `connected` and a `used` audit entry exist.
7. **Health check aborts on non-2xx** — test flips `StubPlatform`'s health endpoint to 403; callback aborts, no `PlatformConnection` written, one `error` audit entry exists.
8. **Nonce replay rejected** — test replays a valid callback URL twice; second call 400s with "state token already used."
9. **Expired JWT rejected** — test crafts a JWT with `exp` in the past; callback 400s.
10. **No plaintext at rest** — test inspects the raw Firestore fixture after a successful connect and asserts no field contains the stub access token or refresh token string.
11. **Feature flag gate** — when `integrations_enabled=false`, user-facing routes 404; internal credential-read still works.
12. **Weave spans emitted** — tracing test captures `integrations.store_token` + `integrations.credential_read` + `integrations.stub_oauth_flow` with expected attributes. No token fields on any span.
13. **Production stub-platform fence** — integration test sets `ENV=production`; `/api/v1/_test/stub-platform/*` returns 404.

## 8. Test plan

### Unit
- `KMSEncryptionService` encrypt/decrypt round-trip (mocked KMS client); `kms_key_version` persisted.
- `StateTokenService` issue/verify happy path; tampered signature rejected; expired exp rejected; missing claim rejected.
- `EncryptedToken` helpers write to the correct subcollection path with `kind` discriminator; read returns latest row.
- `write_connection_audit` delegates to DM-PRD-07's `write_audit` with correct shape; rejects entries containing `access_token`/`refresh_token` substrings in metadata (lint rule).
- `PlatformDefinition` Pydantic validation: unknown `auth_type` rejected.

### Integration
- StubPlatform full-loop test (AC #6).
- Health-check abort path (AC #7).
- Nonce replay (AC #8); expired JWT (AC #9).
- No-plaintext-at-rest inspection (AC #10).
- Feature-flag gating (AC #11).
- Production-fence on stub router (AC #13).

### Manual verification
- Dev-env: run `./api/scripts/setup_local_dev.sh`, hit the stub flow via `curl`, inspect Firestore console to confirm token subcollection exists under the connection and contains `ciphertext` + `kms_key_version` fields only.

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| KMS key accidentally deleted or disabled mid-migration | Terraform `lifecycle { prevent_destroy = true }` on the key; IAM bindings exclude `cryptoKeyVersions.destroy` for the service account. |
| JWT signing key leakage | Stored in Secret Manager with per-env ACL; rotation runbook in IN-PRD-06; rotation invalidates all in-flight `initiate` calls (acceptable — ≤10-min window). |
| StubPlatform leaks to production | `ENV != "production"` fence on the router; regression test asserts 404 in prod build. |
| Shape B migration ordering | IN-PRD-01's migration is additive (new collections only). Runs cleanly on any account already on Shape B (DM-PRD-00). |
| Nonce collection growth | Firestore TTL policy auto-deletes after 15 min; index only on the document id, so growth is bounded. |
| Downstream consumers written against stub drift when real platform lands | Contract is the internal credential-read response shape (`{access_token, expires_at, external_account_id}`), which is unchanged between stub and real. IN-PRD-02 extends it only via the `refresh` wiring (transparent to callers). |

### Open questions
- **Q:** Should the stub platform be disabled in *staging* as well, or only production? → Leave enabled in staging for E2E smoke tests; prod-only fence. Revisit if any staging security review objects.

## 10. Reference

- Component plan: [`../implementation-plan.md`](../implementation-plan.md)
- Upstream: [DM-PRD-00](../../data-management/projects/DM-PRD-00-migration-foundation.md), [DM-PRD-07](../../data-management/projects/DM-PRD-07-approval-workflow-and-audit.md)
- Downstream: [IN-PRD-02](./IN-PRD-02-google-oauth-flow.md), [DP-PRD-01](../../data-pipeline/projects/DP-PRD-01-foundation.md) (soft)
- CLAUDE.md rules in scope: PY-1, PY-2, PY-5, PY-7; D-1, D-2, D-5; C-2, C-4, C-5; T-1, T-3, T-4, T-5
