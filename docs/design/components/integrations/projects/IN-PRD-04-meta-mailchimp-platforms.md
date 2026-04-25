# IN-PRD-04 — Meta + Mailchimp Platforms

**Status:** Not started
**Owner team:** Integrations component team (backend)
**Blocked by:** [IN-PRD-02](./IN-PRD-02-google-oauth-flow.md) (generic OAuth flow + refresh + revoke paths proven on one real platform)
**Parallel with:** [IN-PRD-03](./IN-PRD-03-connection-management-ui.md) — the UI auto-picks up new platforms as their feature flags flip on
**Blocks:** [DP-PRD-05](../../data-pipeline/projects/DP-PRD-05-additional-connectors.md) (Meta Ads + Mailchimp connectors)
**Estimated effort:** 3 days backend

---

## 1. Context

IN-PRD-02 validated the substrate on Google. This project extends it to Meta and Mailchimp, which exercise the platform-generic design against platform-specific quirks:

- **Meta** issues short-lived access tokens that must be exchanged for a 60-day long-lived token via a separate endpoint immediately after the code exchange. Meta doesn't issue refresh tokens in the OAuth sense; we refresh by re-exchanging the long-lived token against the `/oauth/access_token?grant_type=fb_exchange_token` endpoint before expiry.
- **Mailchimp** returns a `dc` (data-center) prefix in the token response (e.g., `us14`) that must be stored and used as the API base URL for every subsequent call. This is neither a scope nor a refresh token — it's platform-native routing metadata.
- **Mailchimp** uses `account_type=user` / `account_type=account` variations and a non-standard revoke URL (actually a DELETE against `/3.0/ping/keys`, not a dedicated revoke endpoint).

The goal is to prove the substrate is **platform-generic**: we capture Meta's long-lived-exchange as a declarative field on `PlatformDefinition`, Mailchimp's `dc` prefix as a field on `PlatformConnection`, and revoke-URL shape variance in `PlatformDefinition` — no platform-specific code in the generic OAuth flow. If this project requires touching `oauth.py`, `refresh.py`, or similar generic files more than a small amount, the substrate design needs revisiting.

## 2. Scope

### In scope
- **`meta` `PlatformDefinition`** — authorization URL, token URL, revoke URL, scopes (`ads_read`, `ads_management`, `business_management`, `pages_read_engagement`), `redirect_uri_template`, `supports_refresh=true`, `health_check_endpoint` → `graph.facebook.com/v18.0/me`, `platform_version=1`, new field `long_lived_exchange_url` (optional, declarative — present only for Meta).
- **`mailchimp` `PlatformDefinition`** — authorization URL, token URL, revoke URL (`DELETE /3.0/ping/keys` variant handled via a `revoke_method` field defaulting to `"POST"`), scopes (`none` — Mailchimp scopes are implicit), `redirect_uri_template`, `supports_refresh=false` (Mailchimp issues long-lived tokens without refresh), `health_check_endpoint` → `/3.0/ping` (resolved per-connection using the `dc` prefix), `platform_version=1`.
- **`PlatformDefinition` schema extensions** — `long_lived_exchange_url: str | None`, `revoke_method: Literal["POST","DELETE","GET"] = "POST"`, `token_response_extra_fields: list[str] = []` (list of non-standard token-response fields to persist, e.g., `["dc"]` for Mailchimp).
- **`PlatformConnection` extensions** — `platform_metadata: dict = {}` stores `token_response_extra_fields` values. For Mailchimp, this holds `{"dc": "us14"}`; for Meta, empty.
- **Long-lived-token exchange (Meta)** — after the initial code→access_token exchange, if `PlatformDefinition.long_lived_exchange_url` is set, invoke it with the short-lived token and replace the stored `access_token` + `expires_at` with the long-lived response. Implemented generically in `oauth.py`; Meta is the only platform that sets this field in v1.
- **Refresh variants** — extend `refresh.py` to support Meta's `fb_exchange_token` grant (declarative via a `refresh_grant_type` field on `PlatformDefinition`, default `"refresh_token"`). Mailchimp connections skip refresh entirely (`supports_refresh=false`).
- **Health-check URL templating** — `health_check_endpoint` is rendered with `platform_metadata` (e.g., `https://{dc}.api.mailchimp.com/3.0/ping` for Mailchimp). Small templating helper; covered by tests.
- **Per-env OAuth credentials** — Meta App + Mailchimp App registered per env; client_id + client_secret in Secret Manager.
- **`StubPlatform` extensions** — add configurable "long-lived exchange" mode and "extra response fields" mode so the stub can replay Meta's and Mailchimp's quirks in hermetic tests. This is the real validation that the substrate is platform-generic: if the stub can do it declaratively, platform code in v1 is unnecessary.
- **Feature flags** — `integration_meta_enabled`, `integration_mailchimp_enabled`.

### Out of scope
- Connection-management UI changes — IN-PRD-03 auto-renders new platforms from `PlatformDefinition`.
- Data Pipeline connectors for Meta / Mailchimp — DP-PRD-05.
- HubSpot — deferred until the HubSpot Specialist PRD lands (same reasoning as DP-PRD-05).
- Webhooks from Meta / Mailchimp — future `integrations-inbound` component.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[IN-PRD-02](./IN-PRD-02-google-oauth-flow.md)** | Generic `oauth.py` + `refresh.py` paths with Google validating the patterns. This project extends them declaratively. | This component |
| Meta Developer app | Meta Business app registered per env; App ID + App Secret + per-env OAuth redirect URIs. One-time manual setup runbook: `operations/meta-oauth-setup.md`. | Operations runbook |
| Mailchimp OAuth app | Mailchimp app registered per env. Runbook: `operations/mailchimp-oauth-setup.md`. | Operations runbook |
| Secret Manager | `meta-oauth-client-{id,secret}-{env}`, `mailchimp-oauth-client-{id,secret}-{env}`. | `deployment/terraform/` |
| Feature Flags | `integration_meta_enabled`, `integration_mailchimp_enabled`. | [FF-PRD-01](../../feature-flags/projects/FF-PRD-01-data-model-evaluation-api.md) |

## 4. Data contract

### `PlatformDefinition` extensions

```python
# Added in this project:
long_lived_exchange_url: str | None = None     # called after code exchange; replaces access_token
refresh_grant_type: str = "refresh_token"      # e.g., "fb_exchange_token" for Meta
revoke_method: Literal["POST", "DELETE", "GET"] = "POST"
token_response_extra_fields: list[str] = []    # fields from token response to persist on PlatformConnection.platform_metadata
```

### `PlatformConnection` extensions

```python
platform_metadata: dict = {}                   # platform-native routing fields (e.g., {"dc": "us14"})
```

### Seeded documents

- `platform_definitions/meta` (`platform_version=1`) — `long_lived_exchange_url` set, `refresh_grant_type="fb_exchange_token"`, `token_response_extra_fields=[]`.
- `platform_definitions/mailchimp` (`platform_version=1`) — `supports_refresh=false`, `revoke_method="DELETE"`, `token_response_extra_fields=["dc"]`, `health_check_endpoint="https://{dc}.api.mailchimp.com/3.0/ping"`.

## 5. Implementation outline

### 5.1 File inventory

| Action | File |
|--------|------|
| Modify | `api/src/kene_api/models/integrations.py` — new fields on `PlatformDefinition` and `PlatformConnection` |
| Modify | `api/src/kene_api/integrations/oauth.py` — long-lived-token exchange step; persist `token_response_extra_fields` into `platform_metadata`; render `health_check_endpoint` with metadata; honor `revoke_method` |
| Modify | `api/src/kene_api/integrations/refresh.py` — honor `refresh_grant_type`; `supports_refresh=false` short-circuits |
| Create | `api/scripts/seed_meta_platform_definition.py` |
| Create | `api/scripts/seed_mailchimp_platform_definition.py` |
| Modify | `api/src/kene_api/integrations/stub_platform.py` — new modes: `long_lived_exchange`, `extra_response_fields` |
| Modify | `deployment/terraform/` — four new Secret Manager secrets + bindings |
| Create | `docs/design/components/integrations/operations/meta-oauth-setup.md` |
| Create | `docs/design/components/integrations/operations/mailchimp-oauth-setup.md` |
| Create | `api/tests/unit/integrations/test_long_lived_exchange.py` |
| Create | `api/tests/unit/integrations/test_platform_metadata.py` |
| Create | `api/tests/unit/integrations/test_revoke_methods.py` |
| Create | `api/tests/integration/integrations/test_stub_platform_meta_variant.py` — proves substrate is platform-generic against StubPlatform |
| Create | `api/tests/integration/integrations/test_stub_platform_mailchimp_variant.py` |

### 5.2 Generic `oauth.py` changes

The only changes to the generic flow:

```text
handle_callback (Meta variant):
  ... existing code exchange ...
  if PlatformDefinition.long_lived_exchange_url:
    access_token, expires_in = exchange_for_long_lived(
      PlatformDefinition.long_lived_exchange_url,
      client_id, client_secret,
      short_lived_access_token,
    )
  for field in PlatformDefinition.token_response_extra_fields:
    if field in token_response:
      platform_metadata[field] = token_response[field]
  ... existing persistence ...

resolve_health_check_url(PlatformDefinition, PlatformConnection):
  return PlatformDefinition.health_check_endpoint.format(**PlatformConnection.platform_metadata)

revoke_connection:
  method = PlatformDefinition.revoke_method
  httpx.request(method, revoke_url, params={"token": refresh_token_or_access_token})
```

All three changes are *declarative* — driven by `PlatformDefinition` fields, not `if platform_id == "meta"` branches.

### 5.3 Proof the substrate is platform-generic

The integration tests `test_stub_platform_meta_variant.py` and `test_stub_platform_mailchimp_variant.py` instantiate StubPlatform in each platform's mode, seed a stub `PlatformDefinition` matching Meta or Mailchimp behavior, and run the end-to-end flow. If either test requires importing Meta-specific or Mailchimp-specific helpers, the substrate has leaked platform knowledge and needs refactoring.

### 5.4 Mailchimp `dc` flow

```text
callback:
  1. Standard code exchange → { access_token, dc: "us14" }.
  2. token_response_extra_fields=["dc"] → platform_metadata["dc"] = "us14".
  3. Persist PlatformConnection with platform_metadata.
  4. Health check: resolve_health_check_url("https://{dc}.api.mailchimp.com/3.0/ping", {"dc": "us14"}) → GET it.
  5. On 2xx, proceed.
```

Downstream Mailchimp connectors (DP-PRD-05) read `platform_metadata["dc"]` alongside the access_token to build their API base URL.

### 5.5 Meta long-lived exchange

```text
callback:
  1. Standard code exchange → short-lived { access_token, expires_in=3600 }.
  2. long_lived_exchange_url is set → GET it with grant_type=fb_exchange_token + short-lived token.
  3. Response: { access_token: <60-day>, expires_in: 5184000 } → replace stored access_token + expires_at.
  4. Refresh flow (refresh.py) uses the same exchange endpoint + grant_type from PlatformDefinition.refresh_grant_type.
```

## 6. API contract

No new endpoints. This PRD extends the existing endpoints' behavior via `PlatformDefinition` fields. Management endpoints (IN-PRD-03) receive new platforms automatically.

## 7. Acceptance criteria

1. **Meta platform seeded** — `platform_definitions/meta` document lands with `long_lived_exchange_url`, `refresh_grant_type="fb_exchange_token"`, `supports_refresh=true`, correct scopes + health-check URL.
2. **Mailchimp platform seeded** — `platform_definitions/mailchimp` document lands with `supports_refresh=false`, `revoke_method="DELETE"`, `token_response_extra_fields=["dc"]`, `health_check_endpoint` template using `{dc}`.
3. **Meta end-to-end (hermetic)** — StubPlatform in Meta mode returns a short-lived token; callback performs the long-lived exchange; stored `access_token` matches the long-lived value; `expires_at` reflects the long-lived expiry.
4. **Mailchimp end-to-end (hermetic)** — StubPlatform in Mailchimp mode returns `{access_token, dc}`; stored `platform_metadata.dc` equals the stub value; resolved health-check URL includes the `dc` prefix; health check fires against that URL.
5. **Meta refresh (hermetic)** — refresh flow invokes the `fb_exchange_token` grant; stored `access_token` + `expires_at` updated; `last_refreshed_at` updated.
6. **Mailchimp skips refresh** — refresh sweeper on Mailchimp connections is a no-op; credential-read returns the stored token even when `expires_at` is null (Mailchimp long-lived tokens don't expire in the usual sense).
7. **Revoke honors method** — Meta revoke uses POST; Mailchimp revoke uses DELETE; both land on the correct endpoint with the correct token param.
8. **Feature flags** — `integration_meta_enabled=false` hides Meta from `/platforms` and 404s `initiate`; same for Mailchimp.
9. **No platform-specific branches in generic code** — `grep -rn 'platform_id == "meta"\|platform_id == "mailchimp"' api/src/kene_api/integrations/oauth.py api/src/kene_api/integrations/refresh.py` yields zero matches. Platform-specific behavior is declarative via `PlatformDefinition` fields.
10. **Management endpoints render new platforms** — `GET /platforms` includes Meta and Mailchimp when their flags are on; the Settings Integrations tab (IN-PRD-03) renders cards for both without code changes.
11. **Health-check URL templating** — unit test covers `{dc}` substitution + missing-key graceful failure (falls back to un-templated URL + debug-log).
12. **Platform-version tracking** — existing Meta/Mailchimp connections carry `platform_version_at_connect=1`; a future bump (scope change) is additive and forces reconnect on next use.

## 8. Test plan

### Unit
- `PlatformDefinition` validation: new fields accepted; `revoke_method` Literal enforced.
- `oauth.py` long-lived-exchange branch: called when URL set, skipped when null.
- `oauth.py` `token_response_extra_fields`: captures listed fields, ignores unlisted.
- `oauth.py` health-check URL templating with missing + present metadata keys.
- `refresh.py` variant grant types: `refresh_token` vs `fb_exchange_token` payload shape.
- `refresh.py` `supports_refresh=false` short-circuit.
- Revoke method dispatch: POST / DELETE / GET variants.

### Integration (hermetic, StubPlatform)
- Meta mode end-to-end (AC #3, #5).
- Mailchimp mode end-to-end (AC #4, #6).
- Revoke-method variants (AC #7).
- Management endpoint new-platform visibility (AC #10).

### Integration (real platforms, gated)
- `@pytest.mark.external` Meta flow against a dev-env Meta Business app + test page. Gated behind `RUN_EXTERNAL_INTEGRATION_TESTS=1`.
- `@pytest.mark.external` Mailchimp flow against a dev-env Mailchimp app + test account.

### Manual verification
- Connect Meta via IN-PRD-03 UI on dev-env; confirm card shows correct scopes + `last_used_at` updates.
- Same for Mailchimp; additionally confirm `platform_metadata.dc` surfaces in the audit drawer's metadata field.

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| Meta verification required for `ads_read`/`ads_management` (sensitive scopes) | Same runbook pattern as Google. Dev/staging use a test Meta app (unverified, works on test users); prod requires verification. Block prod launch on verification. |
| Mailchimp changes its data-center prefix semantics | `platform_metadata` is a free-form dict, so additional fields ride along without schema changes. If Mailchimp deprecates `dc`, bump `platform_version`. |
| Meta long-lived token edge case: token refresh fails after ~60 days silently | Refresh sweeper attempts 7 days before expiry; on failure → `status=expired` → notification (IN-PRD-05). |
| Substrate leakage during implementation | AC #9's grep check + the StubPlatform-based integration tests. If a developer introduces a `platform_id == "meta"` branch, CI fails. |
| Mailchimp audience/user ambiguity on connection label | Connection-label fetch: call `/3.0/` root; use `account_name` field. Fallback to "Mailchimp account" if missing. |

### Open questions
- **Q:** Store the `dc` prefix as a separate first-class field on `PlatformConnection` instead of inside `platform_metadata`? → No. `platform_metadata` is the generic escape hatch; first-class only if many platforms need it.
- **Q:** Does Meta's long-lived exchange always return a refresh token? → No — it returns another access token with a new expiry; we re-exchange the long-lived token at refresh time. Tested explicitly.

## 10. Reference

- Component plan: [`../implementation-plan.md`](../implementation-plan.md)
- Upstream: [IN-PRD-02](./IN-PRD-02-google-oauth-flow.md)
- Downstream: [DP-PRD-05](../../data-pipeline/projects/DP-PRD-05-additional-connectors.md)
- Operations runbooks (shipped with this PRD): `operations/meta-oauth-setup.md`, `operations/mailchimp-oauth-setup.md`
- CLAUDE.md rules in scope: PY-1, PY-2, PY-7; D-2, D-5; C-2, C-4; T-1, T-3, T-4, T-5
