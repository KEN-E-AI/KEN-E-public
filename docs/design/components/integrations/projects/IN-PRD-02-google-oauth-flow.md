# IN-PRD-02 — Google OAuth Flow

**Status:** Not started
**Owner team:** Integrations component team (backend)
**Blocked by:** [IN-PRD-01](./IN-PRD-01-core-model-encryption.md) (core model + encryption + generic OAuth scaffolding + StateTokenService)
**Parallel with:** None within Integrations — IN-PRD-03/04/05 all chain off this project
**Blocks:** [IN-PRD-03](./IN-PRD-03-connection-management-ui.md), [IN-PRD-04](./IN-PRD-04-meta-mailchimp-platforms.md), [DP-PRD-02](../../data-pipeline/projects/DP-PRD-02-google-analytics-connector.md), AH-PRD-03 header-provider refactor (absorbed by IN-PRD-06)
**Estimated effort:** 4 days backend

---

## 1. Context

IN-PRD-01 ships the OAuth substrate and exercises it against a stub platform. This project lights up the first real platform — Google — which covers both Google Analytics and Google Ads under a single OAuth app with incremental scopes per connection. Google is the load-bearing platform for Release 1: DP-PRD-02 (GA connector), AH-PRD-03 (GA specialist), and SE-PRD-02 (weekly KPI ingestion) all depend on it.

The project delivers the `google` platform definition, the per-env OAuth client credentials, the authorization + callback flow against real Google OAuth, refresh-token lifecycle (pre-emptive refresh within `refresh_lookahead_seconds`), an idle-connection cleanup cron (revoke connections inactive for 90 days), and integration tests against the Google OAuth sandbox. It also wires the post-callback health check — at connect time, a low-cost read against GA Admin API or Ads `customers.list` validates the granted scopes before the connection is declared successful.

After this project, a user can connect Google via UI, Data Pipeline GA jobs can read tokens, expiring tokens auto-refresh without user action, and revoke propagates in <30s.

## 2. Scope

### In scope
- **`google` `PlatformDefinition`** — authorization URL, token URL, revoke URL, scopes (GA + Ads starter set), `redirect_uri_template`, `supports_refresh=true`, `refresh_lookahead_seconds=300`, `health_check_endpoint` pointing at a low-cost GA Admin API read, `platform_version=1`.
- **Incremental scopes per connection** — single shared OAuth app; scopes requested at `initiate()` time vary per downstream consumer (GA connections request `analytics.readonly`, Ads connections request `adwords`). Granted scopes persisted on `PlatformConnection.scope`.
- **Per-env OAuth client credentials** — dev / staging / production apps registered with Google; client_id + client_secret stored in Secret Manager (`google-oauth-client-id-{env}`, `google-oauth-client-secret-{env}`). `PlatformDefinition` references them via `client_id_secret_ref` / `client_secret_secret_ref`.
- **Real-Google authorization + callback** — generalizes IN-PRD-01's generic `oauth.py` paths; adds Google-specific concerns: `access_type=offline` + `prompt=consent` to guarantee a refresh token on first grant, incremental-auth (`include_granted_scopes=true`).
- **Post-callback health check** — after token exchange, call `PlatformDefinition.health_check_endpoint` (GA Admin API `accountSummaries.list` with 1-result limit) using the new access token. Non-2xx → abort connect, surface a descriptive error to the UI (e.g., "GA4 read access not granted"), discard tokens, write an `error` audit entry.
- **Refresh lifecycle** — on credential read, if `expires_at` is within `refresh_lookahead_seconds`, refresh synchronously (~200ms). Firestore transaction on the connection doc prevents thundering-herd refreshes across concurrent callers. `last_refreshed_at` + `kms_key_version` updated on each refresh. Emits a `refreshed` audit entry.
- **Revoke** — `DELETE /connections/{connection_id}` calls Google's revoke endpoint (best-effort; tolerate 400 "already revoked"), recursive-deletes tokens, writes `revoked` audit entry.
- **Idle-connection cleanup** — sibling Cloud Scheduler cron (`integrations-idle-cleanup`) fires daily, finds connections with `last_used_at` older than 90 days, revokes them and emits a notification.
- **Pre-emptive refresh worker (optional)** — Cloud Scheduler cron every 5 minutes scans connections whose `expires_at` falls within the next 10 minutes and refreshes them proactively, so the first credential-read in a window doesn't pay the 200ms refresh cost. Capped at 100 connections per tick (headroom; fast-follow if load exceeds).
- **External account labeling** — after a successful connect, call GA Admin API (`accountSummaries.list`) to fetch account display names; store the first match as `PlatformConnection.external_account_label` (e.g., "GA4: ken-e.com") and `external_account_id`. If multiple GA accounts are accessible, pick the first alphabetically and log a debug note — multi-account selection UX is IN-PRD-03's concern.
- **Integration tests** — against Google OAuth *sandbox* where available (Google provides a sandbox for Ads; GA uses real OAuth with test accounts). Hermetic unit tests use `respx`/`httpx_mock` to stub Google's token + revoke endpoints.
- **Feature flag** — per-platform `integration_google_enabled` flag. When off, the platform doesn't appear in `/platforms` and `initiate()` on `google` 404s.

### Out of scope
- Connection-management UI — IN-PRD-03.
- Meta + Mailchimp — IN-PRD-04.
- Re-auth notifications + user-removal hook — IN-PRD-05.
- Legacy cleanup (removing AH-PRD-02's `_make_header_provider` session-state reads) — IN-PRD-06.
- Multi-account connection picker (one KEN-E account connects to multiple GA properties) — not a goal for v1; user picks property inside each downstream tool.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[IN-PRD-01](./IN-PRD-01-core-model-encryption.md)** | All shapes, KMS, state tokens, generic initiate/callback, internal credential-read, audit writer. This project extends the generic paths with refresh logic and seeds the Google `PlatformDefinition`. | This component |
| Google Cloud project — OAuth client | Per-env OAuth 2.0 Client IDs registered in the Google Cloud Console with the correct redirect URIs for each env. Owner: platform admin. | `deployment/terraform/` does not manage these (not Terraform-able); one-time manual setup documented in an operations runbook shipped with this project. |
| Secret Manager | `google-oauth-client-id-{env}`, `google-oauth-client-secret-{env}` secrets. Terraform adds IAM bindings; values populated manually after OAuth client registration. | `deployment/terraform/` |
| Cloud Scheduler | Two jobs — `integrations-google-refresh-sweeper` (every 5 min) and `integrations-idle-cleanup` (daily). | `deployment/terraform/` |
| Existing Feature Flags | `integration_google_enabled` flag. Evaluated in the initiate/list paths. | [FF-PRD-01](../../feature-flags/projects/FF-PRD-01-data-model-evaluation-api-backend-sdk.md) |

## 4. Data contract

No schema changes beyond IN-PRD-01. This project adds:

- A seeded `platform_definitions/google` document (`platform_version=1`).
- `connected_by_user_id`, `scope`, `external_account_label`, `external_account_id` populated on real Google connections.
- `last_refreshed_at` updated on each refresh cycle.

## 5. Implementation outline

### 5.1 File inventory

| Action | File |
|--------|------|
| Create | `api/src/kene_api/integrations/platforms/google.py` — Google-specific concerns (scope set, health check, account-label fetch) |
| Modify | `api/src/kene_api/integrations/oauth.py` — add `access_type=offline` + `prompt=consent` query params when `PlatformDefinition.supports_refresh=true`; thread refresh logic into the credential-read path |
| Create | `api/src/kene_api/integrations/refresh.py` — `refresh_connection(connection_id)` helper with Firestore-transaction lock, token exchange, re-encrypt, audit |
| Modify | `api/src/kene_api/routers/integrations.py` — wire pre-emptive refresh inside the internal credential-read endpoint; add `DELETE` (revoke) endpoint; add `POST /connections/{id}/refresh` admin-force-refresh endpoint |
| Create | `api/src/kene_api/integrations/workers/refresh_sweeper.py` — Cloud Scheduler handler; scans connections with upcoming expiries |
| Create | `api/src/kene_api/integrations/workers/idle_cleanup.py` — Cloud Scheduler handler; revokes connections inactive 90 days |
| Create | `api/scripts/seed_google_platform_definition.py` — inserts the `platform_definitions/google` document |
| Modify | `deployment/terraform/` — Secret Manager secrets + IAM + two Cloud Scheduler jobs |
| Create | `docs/design/components/integrations/operations/google-oauth-setup.md` — runbook for registering the Google Cloud OAuth client per env |
| Create | `api/tests/unit/integrations/test_refresh.py` |
| Create | `api/tests/unit/integrations/test_google_platform.py` |
| Create | `api/tests/integration/integrations/test_google_oauth_flow.py` — real Google OAuth (dev-env credentials + a test Google account) |
| Create | `api/tests/integration/integrations/test_google_refresh_and_revoke.py` |

### 5.2 Refresh flow

```text
refresh_connection(connection_id):
  1. Firestore transaction on accounts/{account_id}/platform_connections/{connection_id}:
     a. If another refresh is in flight (in-flight marker set within last 5s), wait-and-retry.
     b. Set in-flight marker.
  2. Decrypt the current refresh_token.
  3. POST to Google token endpoint with grant_type=refresh_token.
  4. KMS-encrypt the new access_token (Google rotates refresh_token only on explicit revocation-and-reconnect; preserve the existing refresh_token unless the response contains a new one).
  5. Persist updated EncryptedToken rows; update last_refreshed_at; clear in-flight marker.
  6. write_connection_audit(event="refreshed", actor_id="system:refresh").
  7. On failure: status=expired, error_message set, emit reauth_requested audit entry (IN-PRD-05 consumes this to send the notification).
```

### 5.3 Credential-read with refresh

```text
GET /internal/integrations/credentials/{account_id}/{platform_id}:
  1. Load PlatformConnection; 404 if none.
  2. If status != connected: 409 with "needs_reauth".
  3. Load access_token EncryptedToken.
  4. If now + refresh_lookahead_seconds > expires_at:
     refresh_connection(connection_id)  # synchronous; ~200ms
  5. Decrypt and return { access_token, expires_at, external_account_id }.
  6. write_connection_audit(event="used", actor_id=caller_service_id) — debounced to once per minute per (connection_id, caller) to avoid audit-log bloat.
```

### 5.4 Health check (post-callback)

After the token exchange in `handle_callback`, before persisting the `PlatformConnection`:

```text
if PlatformDefinition.health_check_endpoint:
  1. httpx.get(health_check_endpoint, headers={"Authorization": f"Bearer {access_token}"}, timeout=1.0).
  2. On non-2xx or timeout: discard tokens, write_connection_audit(event="error", metadata={reason, status}), return 400 to the UI with a parsed error message.
  3. On 2xx: proceed with persistence and account-label fetch.
```

Google's chosen endpoint: `https://analyticsadmin.googleapis.com/v1beta/accountSummaries?pageSize=1`. Cheap, proves `analytics.readonly` is granted, and returns account metadata we use in step 5.5.

### 5.5 External account labeling

On a successful GA connect, fetch `accountSummaries.list`. Take the first result's `displayName` (e.g., "ken-e.com") and `account` resource name; store as `external_account_label` and `external_account_id`. If the call 403s post-health-check (edge case — token valid for health check but not for full list), log a debug note and leave both fields `null` — the UI shows a fallback label.

### 5.6 Revoke

```text
DELETE /api/v1/integrations/{account_id}/connections/{connection_id}:
  1. Authorization: account-admin.
  2. Load PlatformConnection; load refresh_token.
  3. POST to PlatformDefinition.oauth_revoke_url?token={refresh_token}. Tolerate 400.
  4. firestore.recursive_delete(accounts/{account_id}/platform_connections/{connection_id}).
  5. write_connection_audit(event="revoked", actor_id=caller_user_id).
  6. Publish a RevocationEvent to the internal notification bus so downstream consumers clear cached credentials (IN-PRD-05 consumes this).
```

## 6. API contract

Extends the IN-PRD-01 surface:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/integrations/{account_id}/connections/{connection_id}/refresh` | Force a refresh (admin tool; normally automatic). Returns new `expires_at`. |
| `DELETE` | `/api/v1/integrations/{account_id}/connections/{connection_id}` | Revoke + recursive-delete. |
| `GET` | `/api/v1/integrations/platforms` | List platform definitions filtered by `integration_<platform>_enabled` flags; includes `connected: bool` per platform for the account. |

Internal refresh-sweeper + idle-cleanup endpoints (OIDC, invoked by Cloud Scheduler):

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/internal/integrations/refresh-sweeper` | Refresh connections expiring within 10 min (batched). |
| `POST` | `/api/v1/internal/integrations/idle-cleanup` | Revoke connections inactive for 90+ days. |

## 7. Acceptance criteria

1. **Google platform seeded** — `platform_definitions/google` document lands via the seed script with correct authorization URL, token URL, revoke URL, scopes, `supports_refresh=true`, and `health_check_endpoint` set.
2. **Per-env OAuth credentials wired** — dev / staging / prod client_id + client_secret in Secret Manager; initiate flow resolves them per env.
3. **User connects Google via API** — `POST /initiate` on `google` returns a Google authorization URL including `access_type=offline` and `prompt=consent`. Callback exchanges the code and persists KMS-encrypted tokens under the account.
4. **Post-callback health check runs** — with a validly scoped grant, the flow completes; with an under-scoped grant (e.g., user deselects `analytics.readonly`), the callback 400s with "GA4 read access not granted" and no `PlatformConnection` row is written.
5. **External account label populated** — after a successful connect against a test GA account, `external_account_label` matches the GA property display name and `external_account_id` is set.
6. **Credential-read auto-refreshes** — integration test forces a token to within the refresh lookahead; credential-read returns a refreshed `access_token` with updated `expires_at`; `last_refreshed_at` updated; `refreshed` audit entry present.
7. **Thundering-herd safe** — simulated 20 concurrent credential-reads against the same near-expiry token produce exactly one refresh (Firestore-transaction-guarded), not 20.
8. **Revoke end-to-end** — revoke endpoint calls Google revoke, deletes tokens, writes `revoked` audit, and propagates revocation in <30s. Subsequent credential-read returns 409 `needs_reauth`.
9. **Pre-emptive refresh sweeper** — Cloud Scheduler handler processes a batch without errors; connections expiring within 10 min are refreshed; skips connections with `status != connected`.
10. **Idle-cleanup cron** — connections with `last_used_at` > 90 days ago are revoked; notification stubbed here (real routing in IN-PRD-05).
11. **Feature flag gate** — with `integration_google_enabled=false`, the `google` platform is absent from `/platforms` and `POST /initiate` on `google` returns 404.
12. **No plaintext at rest** — post-connect inspection confirms no Google access/refresh token string in any Firestore doc.
13. **Legacy cleanup marker** — `_make_header_provider` in AH-PRD-02's code remains functional; this PRD does not remove it (IN-PRD-06 does) but adds a `# TODO(IN-PRD-06)` marker at the call site to simplify the cutover.

## 8. Test plan

### Unit
- `refresh.py` — happy path, Google token-endpoint error, Firestore-transaction conflict-retry, expired refresh_token → `status=expired`.
- `google.py` — scope assembly per connection-type input, health-check response parsing, account-label extraction from `accountSummaries.list` response fixtures.
- Credential-read — with `now + lookahead < expires_at` returns cached; with `now + lookahead > expires_at` invokes refresh; with `status != connected` returns 409.

### Integration (hermetic)
- Full initiate → callback with `httpx_mock`-stubbed Google endpoints for token + health-check + account-summaries.
- Concurrent credential-reads (AC #7) using `asyncio.gather` and a single near-expiry token.
- Revoke flow with Google revoke endpoint mocked.

### Integration (real Google)
- One `@pytest.mark.external` test that runs against a real dev-env OAuth app and a dedicated test Google account. Gated by `RUN_EXTERNAL_INTEGRATION_TESTS=1`; excluded from the default CI run to keep it hermetic, but runnable on demand and in the IN-PRD-06 E2E suite.

### Manual verification
- End-to-end dev-env run: connect Google via `curl`-driven initiate + browser-driven authorize + curl-driven callback → confirm Firestore state → force-refresh via admin endpoint → revoke → confirm tokens gone.

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| Google returns no refresh_token on re-grant (user already granted once; `prompt=consent` omitted) | `prompt=consent` is always sent; test asserts `refresh_token` present in token response. |
| Refresh-token rotation (rare but possible) | Refresh handler writes any new `refresh_token` from the response; test stubs both rotation and no-rotation paths. |
| Rate limits on Google's token endpoint | Pre-emptive refresh batch capped at 100/tick + 5-min cadence ≈ 1200/hour upper bound; Google's published limit is substantially higher. Sweeper metric + alert if we ever hit a 429. |
| OAuth consent-screen verification | Prod OAuth app needs Google's verification for sensitive/restricted scopes. Scopes in scope here are sensitive (`analytics.readonly`, `adwords`) — verification runbook is part of `google-oauth-setup.md`. Block prod launch until verified. |
| User revokes at Google (outside KEN-E) | Next credential-read 401s; consumer calls `mark-expired` (IN-PRD-05); connection transitions to `expired`; re-auth notification fires. |
| External test account credentials leak in CI logs | External test gated off by default + uses a secrets-less OAuth flow variant; real tokens never land in logs (Weave + pytest log scrubbers). |

### Open questions
- **Q:** Should GA and Google Ads be separate platforms (`google_analytics`, `google_ads`) or a single `google` platform with incremental scopes? → Single `google` platform in v1 (one OAuth app, scopes per connection). Revisit if product wants per-surface disconnect ("disconnect Ads but keep GA").
- **Q:** Pre-emptive refresh sweeper cadence? 5 min is a guess. → Measure in staging: set to 5 min, instrument `refresh_required_on_read` counter, adjust if more than 5% of reads still trigger a sync refresh.

## 10. Reference

- Component plan: [`../implementation-plan.md`](../implementation-plan.md)
- Upstream: [IN-PRD-01](./IN-PRD-01-core-model-encryption.md)
- Downstream: [IN-PRD-03](./IN-PRD-03-connection-management-ui.md), [IN-PRD-04](./IN-PRD-04-meta-mailchimp-platforms.md), [DP-PRD-02](../../data-pipeline/projects/DP-PRD-02-google-analytics-connector.md), [AH-PRD-03](../../agentic-harness/projects/AH-PRD-03-google-analytics-specialist.md) (via IN-PRD-06 retrofit)
- Google OAuth docs: referenced per-env in `operations/google-oauth-setup.md`
- CLAUDE.md rules in scope: PY-1, PY-2, PY-5, PY-7; D-1, D-5; C-2, C-4, C-5; T-1, T-3, T-4, T-5
