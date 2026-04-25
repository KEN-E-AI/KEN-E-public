# IN-PRD-07 — On-demand Connection Test

**Status:** Not started
**Owner team:** Integrations component team (backend + thin frontend + small agent-tool addition). **Co-owned surface:** the `frontend/src/components/chat/AuthStatusCard.tsx` extension is Chat-team code; Integrations ships the wiring change, Chat reviews it. Schedule the AuthStatusCard extension as a **follow-up PR** after the main Integrations PR (backend + Settings-tab button + MCP tool) lands, to keep each diff scoped and each reviewer's context tight.
**Blocked by:** [IN-PRD-02](./IN-PRD-02-google-oauth-flow.md) (`health_check_endpoint` + credential-read + refresh); [IN-PRD-03](./IN-PRD-03-connection-management-ui.md) (`ConnectionCard` host surface); [IN-PRD-05](./IN-PRD-05-reauth-lifecycle.md) (`mark-expired` helper for definitive 401s)
**Parallel with:** [IN-PRD-06](./IN-PRD-06-integration-testing-cleanup.md) — capstone work does not conflict; this PRD reads the same substrate IN-PRD-06 validates
**Unblocks (soft):** [CH-PRD-04](../../chat/projects/CH-PRD-04-session-status-view.md) — the Chat component's Authentication Status card ships read-only against IN-PRD-03's `/connections` data; this PRD's endpoint + `useTestConnectionMutation` hook + `last_tested_at` field turn on the per-row Check Status button + state-reactive CTAs. IN-PRD-07 absorbs the small frontend extension to `AuthStatusCard.tsx` (behind `integrations_connection_test_enabled`).
**Blocks:** — (terminal, opt-in verification surface)
**Estimated effort:** 1.5 days backend + 1 day frontend + 0.5 day MCP tool = 3 days

---

## 1. Context

The Settings → Integrations tab (IN-PRD-03) shows the stored `PlatformConnection.status` — a passive signal meaning "as of our last interaction, this looked fine." That signal is correct by construction but it lags reality: a user may have revoked access at Google minutes ago, a scope may have been silently narrowed, or the platform's backend may be returning 500s. None of these change `status` until a downstream consumer trips over them and calls `mark-expired`.

Users want active verification before initiating work that depends on a connection — especially writes. The concrete trigger for this PRD: a user wants to confirm Google Ads is actually authenticated before asking a KEN-E agent to modify campaigns via the Google Ads MCP. A failed mutating call halfway through an agent plan is costly; a 1-second preflight probe costs nothing.

The pieces needed already exist in the substrate. `PlatformDefinition.health_check_endpoint` is declared and used once at connect time (IN-PRD-02 §5.4). The credential-read path already handles transparent refresh. The `mark-expired` helper already handles definitive 401s. This PRD wires those together into a single user-facing endpoint, wraps it in a Settings-card button, and exposes it as an MCP tool so agents can optionally self-test before a mutating operation.

Scope is deliberately narrow: on-demand only (no background polling), single probe per platform (no per-capability matrix), 60-second server-side cache per connection (reusing the existing connection document as the cache store).

## 2. Scope

### In scope

- **`POST /api/v1/integrations/{account_id}/connections/{connection_id}/test`** — user-facing endpoint, account-member auth. Returns a `ConnectionTestResult`.
- **60-second cache on the connection doc.** Successive calls within 60s return the cached result with `cache_hit=true`. Transient errors are **not** cached (user can retry immediately during a platform outage); successes and definitive errors are.
- **Probe execution.** Reuse `PlatformDefinition.health_check_endpoint` as-is. One probe per platform. 1-second timeout. No per-capability variants in v1.
- **Result classification.** 2xx → `ok=true`. 401/403 → `auth_failed` (`is_scope_issue=true` when the platform's response body signals an insufficient-scope error via a platform-specific parser). 429/5xx/timeout/network → transient variants. 409 from credential-read → short-circuit to `needs_reauth` with no platform call.
- **Definitive-401 side effect.** On a 401/403 that is not a transient pattern, call the existing `mark-expired` helper (IN-PRD-05) so the connection transitions to `expired` and the re-auth notification fires. Idempotent — `mark-expired` already handles already-expired.
- **UI: `Test connection` button on `ConnectionCard`.** Visible for every card state (including Not connected — short-circuits to a helpful hint). Spinner during the 1s probe. Result surfaces inline as a small badge with latency and a tooltip showing `checked_at`. On `needs_reauth` or definitive `auth_failed`, the Reconnect CTA auto-focuses.
- **MCP tool: `integrations.test_connection(platform_id)`.** Thin wrapper over the endpoint. Context-aware — resolves the caller's active `account_id` from ADK session context. Returns the `ConnectionTestResult` as JSON. Enables agent-side preflight before a mutating tool.
- **CH-PRD-04 Auth Status card extension (frontend).** Extend the already-shipped `frontend/src/components/chat/AuthStatusCard.tsx` (from CH-PRD-04 §5.6) with the per-row "Check Status" button and state-reactive CTAs that react to `ConnectionTestResult`. Gated by the same `integrations_connection_test_enabled` flag used by the Settings → Integrations button. No change to CH-PRD-04's component API; this is a behind-flag body swap. Small (~0.25 day, included in the 1 day frontend total).
- **New audit event: `"tested"`.** Written once per cache miss (so the audit log reflects actual platform traffic, not cache hits). Metadata: `{ok, error_code?, latency_ms}`. No plaintext token values.
- **Feature flag: `integrations_connection_test_enabled`.** Default on in dev/staging, on-with-allowlist in prod until IN-PRD-06 lands and the component-level kill switches flip on globally. When off: endpoint 404s, Test button hidden, MCP tool unregistered.

### Out of scope

- Background polling / continuous health monitoring. On-demand only per product decision.
- Per-capability probes (e.g., separate "Ads write" vs. "GA read" tests). Tracked as a v2 follow-up; single default probe per platform in v1.
- Chat pre-flight banner auto-testing every platform referenced in a prompt. Fast-follow candidate; not this PRD.
- Automatic pre-flight inside every agent tool call. Agents opt in by calling the MCP tool explicitly; the tool is not bolted into the root-agent planner.
- Cross-connection aggregated "System status" dashboard. The Settings tab grid is sufficient.
- Rate-limit middleware beyond the 60s cache. The cache is the rate limit — bounded-cost by construction.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[IN-PRD-02](./IN-PRD-02-google-oauth-flow.md)** | `PlatformDefinition.health_check_endpoint`, credential-read path with auto-refresh, the extracted `_run_health_check(platform_def, access_token)` helper (implied by IN-PRD-02 §5.4; this PRD makes it a reusable module-level function if IN-PRD-02 left it inline). | This component |
| **[IN-PRD-03](./IN-PRD-03-connection-management-ui.md)** | `ConnectionCard` component, `frontend/src/app/lib/api/integrations.ts` typed client, branded `ConnectionId` / `PlatformId` types, TanStack Query patterns. | This component |
| **[IN-PRD-05](./IN-PRD-05-reauth-lifecycle.md)** | `mark_expired(connection_id, reason)` transactional helper. | This component |
| **[Feature Flags — FF-PRD-01](../../feature-flags/projects/FF-PRD-01-data-model-evaluation-api.md)** | `integrations_connection_test_enabled` evaluation. | `../../feature-flags/README.md` |
| **[Agentic Harness — MCP substrate](../../agentic-harness/mcp-architecture.md)** | Tool registration path for `integrations.test_connection`; ADK session-context account resolution. | `../../agentic-harness/README.md` |
| W&B Weave tracing | New span `integrations.test_connection` with attributes `{platform_id, ok, cache_hit, latency_ms, error_code?}`. No token values. | `app/adk/tracking/` |

## 4. Data contract

### 4.1 New Pydantic types — `api/src/kene_api/models/integrations_test.py`

```python
class ProbeDetails(BaseModel):
    endpoint_label: str            # human-safe, e.g. "GA Admin: accountSummaries"; never the raw URL with query params
    method: Literal["GET", "POST"]
    status_code: int | None        # None on network error / timeout

class ConnectionTestError(BaseModel):
    code: Literal[
        "auth_failed",         # 401 definitive
        "scope_missing",       # 401/403 with platform-signaled scope error
        "rate_limited",        # 429
        "platform_5xx",        # 5xx
        "probe_misconfigured", # 4xx other than 401/403/429 (400/404/405/…); probe URL or method mismatch against the platform's current API surface — ops-alerting, not user-actionable
        "timeout",             # request exceeded probe timeout
        "network",             # DNS / connection / TLS failure
        "needs_reauth",        # connection not in 'connected' state; short-circuit
        "no_probe_configured"  # platform_definition.health_check_endpoint is None
    ]
    message: str             # human-readable, safe for UI display
    is_scope_issue: bool     # only true for scope_missing
    is_transient: bool       # true for rate_limited, platform_5xx, probe_misconfigured, timeout, network

class ConnectionTestResult(BaseModel):
    connection_id: str
    platform_id: str
    ok: bool
    checked_at: datetime
    latency_ms: int          # 0 when cache_hit=true and was_transient_error=true (edge case; see §5.2)
    probe: ProbeDetails | None   # None when ok=false and code in {"needs_reauth", "no_probe_configured"}
    error: ConnectionTestError | None
    cache_hit: bool
```

### 4.2 Extension to `PlatformConnection` — `api/src/kene_api/models/integrations.py`

Two new optional fields on the existing doc. No migration required — existing connections simply have them unset.

```python
last_test_result: ConnectionTestResult | None = None
last_tested_at: datetime | None = None   # only set when the result is eligible for cache (see §5.2)
```

### 4.3 Audit-event literal extension

`ConnectionAuditEntry.event` gains `"tested"`. Full literal after this PRD:

```python
event: Literal[
    "connected", "refreshed", "revoked",
    "reauth_requested",
    "used", "error", "tested",
]
```

## 5. Implementation outline

### 5.1 File inventory

| Action | File |
|--------|------|
| Create | `api/src/kene_api/integrations/testing.py` — `test_connection(account_id, connection_id)` orchestrator |
| Create | `api/src/kene_api/models/integrations_test.py` — `ConnectionTestResult`, `ConnectionTestError`, `ProbeDetails` |
| Modify | `api/src/kene_api/models/integrations.py` — add `last_test_result`, `last_tested_at` to `PlatformConnection`; extend `ConnectionAuditEntry.event` literal with `"tested"` |
| Modify | `api/src/kene_api/routers/integrations.py` — add `POST /connections/{id}/test` endpoint + feature-flag gate |
| Modify | `api/src/kene_api/integrations/oauth.py` — ensure `_run_health_check(platform_def, access_token, timeout_seconds)` is a reusable module-level function (extract from IN-PRD-02's inline implementation if needed) |
| Modify | `api/src/kene_api/integrations/platforms/google.py` — add `parse_scope_error(response_body: bytes) -> bool` helper used to set `is_scope_issue` |
| Create | `app/adk/tools/integrations_test_tool.py` — ADK tool exposing `integrations.test_connection(platform_id)` |
| Modify | `app/adk/mcp_config/` — register the new tool (follow the pattern in `agentic-harness/mcp-architecture.md`) |
| Modify | `frontend/src/app/lib/api/integrations.ts` — `useTestConnectionMutation` hook + `ConnectionTestResult` / `ConnectionTestError` types (mirrored from the Pydantic source of truth) |
| Modify | `frontend/src/app/pages/settings/integrations/ConnectionCard.tsx` — Test button + result surface |
| Create | `frontend/src/app/pages/settings/integrations/ConnectionTestResultBadge.tsx` — renders `{ok, transient, definitive, needs_reauth, cached, checking}` variants |
| Modify | `frontend/src/lib/chatApi.ts` (from CH-PRD-04) — replace the stub `useTestConnectionMutation` hook with a re-export from the real `frontend/src/app/lib/api/integrations.ts` (one-line swap). This is the seam the CH-PRD-04 graceful-degradation branch left in place. |
| Modify | `frontend/src/components/chat/AuthStatusCard.tsx` (from CH-PRD-04) — wire Check Status button to `useTestConnectionMutation` (now the real hook); implement state-reactive CTA behavior per the four-state table in CH-PRD-04 §5.6 (Authenticated / Needs re-auth / Transient / Not connected). Behind `integrations_connection_test_enabled`. |
| Create | `api/tests/unit/integrations/test_testing.py` |
| Create | `api/tests/unit/integrations/test_scope_error_parser.py` |
| Create | `api/tests/integration/integrations/test_connection_test_endpoint.py` |
| Create | `frontend/src/app/pages/settings/integrations/__tests__/ConnectionCard.test-connection.spec.tsx` |
| Create | `frontend/src/app/pages/settings/integrations/__tests__/ConnectionTestResultBadge.spec.tsx` |

### 5.2 `test_connection` flow

```text
test_connection(account_id, connection_id):
  1. Load PlatformConnection; 404 if none.
  2. Load PlatformDefinition for connection.platform_id.
  3. If platform_definition.health_check_endpoint is None:
       return ConnectionTestResult(ok=False,
         error=ConnectionTestError(code="no_probe_configured", ...),
         probe=None, cache_hit=False).
       (No persist; no audit.)
  4. Cache check. If conn.last_tested_at is not None
     AND (now - conn.last_tested_at) < 60s
     AND conn.updated_at <= conn.last_tested_at:      # cache is stale if the connection doc has been
                                                       # touched since the last test — reconnect, refresh,
                                                       # status transition, or any other field write
       return conn.last_test_result with cache_hit=True.
     (If conn.updated_at > conn.last_tested_at, skip the cache and re-probe.
      Covers the tab-A/tab-B reconnect race: user sees stale 'needs_reauth'
      in tab A for 60s after reconnecting in tab B — the check prevents it.)
  5. If conn.status != "connected":
       result = ConnectionTestResult(ok=False,
         error=ConnectionTestError(code="needs_reauth", is_transient=False, ...),
         probe=None, latency_ms=0, cache_hit=False).
       Persist last_test_result=result, last_tested_at=now (cacheable — definitive).
       write_connection_audit(event="tested", metadata={ok: False, error_code: "needs_reauth"}).
       return result.
  6. Read credentials via the existing internal path
     (auto-refreshes if within refresh_lookahead_seconds).
     - If credential-read returns 409 needs_reauth:
         result = ConnectionTestResult(ok=False,
           error=ConnectionTestError(code="needs_reauth", ...),
           cache_hit=False, latency_ms=0, probe=None).
         Persist + audit as in step 5. Return.
  7. Probe:
       t0 = now()
       try:
         resp = httpx.request(
           method=platform_definition.health_check_method or "GET",
           url=platform_definition.health_check_endpoint,  # template-expanded from platform_metadata
           headers={"Authorization": f"Bearer {access_token}"},
           timeout=1.0,
         )
         latency_ms = (now() - t0).milliseconds
       except httpx.TimeoutException:
         → classify timeout
       except httpx.NetworkError:
         → classify network
  8. Classify:
       2xx                              → ok=True
       401 or 403:
         scope_issue = platforms/<platform>.parse_scope_error(resp.content)
         code        = "scope_missing" if scope_issue else "auth_failed"
         is_transient = False
         side-effect: call mark_expired(connection_id, reason=code)
       429                              → code="rate_limited",        is_transient=True
       5xx                              → code="platform_5xx",        is_transient=True
       other 4xx (400/404/405/…)        → code="probe_misconfigured", is_transient=True
                                          # we cannot distinguish "our probe URL or method is wrong"
                                          # from "the platform changed its endpoint" — either way, do NOT
                                          # mark_expired (the connection itself is probably fine). Emit a
                                          # Weave/ops alert so we notice probe drift early.
       timeout                          → code="timeout",             is_transient=True
       network                          → code="network",             is_transient=True
  9. Build ConnectionTestResult.
 10. Persist — diagnostic fields only; **do NOT bump conn.updated_at**:
       conn.last_test_result = result
       conn.last_tested_at   = (now if ok or not is_transient else None)
     — transient errors are stored for UI display but do NOT extend the cache window,
     so the user can retry immediately. Successes and definitive errors are cached 60s.
     — `updated_at` is reserved for meaningful state changes (status transitions,
       scope grants, token refreshes, reconnects). Bumping it here would invalidate
       the cache on the first click (because step 4's check would always fire), so
       the write uses a targeted Firestore field update that omits `updated_at`.
       The callback (reconnect) and refresh paths continue to bump `updated_at`
       as they always have — the step-4 cache-invalidation check reads that.
 11. write_connection_audit(event="tested",
         metadata={ok, error_code?, latency_ms, cache_hit: False}).
 12. Return result.
```

Two subtleties worth calling out:

- **`last_tested_at` is the cache key**, not `last_test_result.checked_at`. A transient result has `checked_at` set (for UI display — "we tried 3s ago") but `last_tested_at` is None, so the next call goes live.
- **`mark_expired` is called before the return.** Transition is synchronous; the caller sees `ok=false, code=auth_failed` and the connection is already in `expired` by the time the notification fires. The UI refetch will show the `Expired` badge on the next render.

### 5.3 UI behavior

Button states on `ConnectionCard`:

| Card status | Test-button behavior |
|-------------|----------------------|
| `Not connected` | Test button hidden (nothing to test; Connect is the CTA). |
| `Connected` | Test button visible next to Force refresh. Any account member can click. |
| `Expired` / `Revoked` / `Error` | Test button visible; clicking short-circuits to `needs_reauth` result (no platform call) and auto-focuses Reconnect. |

Result surface after click (inline on the card, replacing or extending the status badge area for 10s, then auto-collapsing to a subtle "Verified 10s ago" tooltip on the main status badge):

| Result | Visual |
|--------|--------|
| `ok=true`, fresh | Green check, "Authenticated · 234ms" |
| `ok=true`, cache_hit | Green check, "Authenticated · cached (verified 12s ago)" |
| `is_transient=true` | Amber warning, "Platform temporarily unavailable — try again" + active retry button (bypasses cache naturally since transient results aren't cached) |
| `auth_failed` / `scope_missing` | Red X, "Authentication failed — [Reconnect]" + auto-focus the Reconnect CTA |
| `needs_reauth` | Red X, "Needs re-auth — [Reconnect]" + auto-focus |
| `no_probe_configured` | Grey info, "No live test available for this platform" (shouldn't happen for Google / Meta / Mailchimp; defensive copy for future platforms) |

### 5.4 MCP tool

- Path: `app/adk/tools/integrations_test_tool.py`.
- Tool name: `integrations.test_connection`.
- Signature: `test_connection(platform_id: str) -> dict` — returns the `ConnectionTestResult` as a JSON-serializable dict.
- Account resolution: pulls the active account from ADK session context (follow the pattern used by existing internal-credential tools once IN-PRD-06 lands; until then, match whatever pattern AH-PRD-02's `_make_header_provider` uses).
- Agent usage pattern (recommended, not enforced):
  ```
  result = integrations.test_connection("google")
  if not result["ok"]:
      # Surface the error to the user with a deep link
      return needs_reauth_response(result)
  # Proceed with the mutating Ads call
  ...
  ```
- Weave span: `integrations.test_connection` with `{platform_id, ok, cache_hit, latency_ms, error_code?}`.

## 6. API contract

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/integrations/{account_id}/connections/{connection_id}/test` | Account member | Run (or fetch cached) live probe. Returns `ConnectionTestResult`. |

Request body: empty (GET-semantics-on-POST chosen for parity with the existing POST-for-mutations pattern in `routers/integrations.py`; no idempotency headers needed — cache handles idempotency).

Response codes:

| Status | Body | When |
|--------|------|------|
| `200` | `ConnectionTestResult` | Always, whether `ok` is true or false. A probe running but returning an auth error is still a successful endpoint call. |
| `404` | `{detail: "connection not found"}` | Unknown `connection_id` for `account_id`. |
| `404` | `{detail: "feature disabled"}` | `integrations_connection_test_enabled` is off. |
| `403` | standard | Caller lacks account access. |

## 7. Acceptance criteria

1. **Endpoint exists and feature-flag-gated.** With `integrations_connection_test_enabled=true`, the endpoint accepts POSTs and returns `ConnectionTestResult`. With the flag off, it 404s and the UI Test button is hidden.
2. **Happy path.** Against a `connected` Google connection with valid scopes, the endpoint calls `health_check_endpoint` once, returns `ok=true` with `latency_ms > 0` and `cache_hit=false`, persists `last_test_result` + `last_tested_at` on the connection doc, and writes a `tested` audit entry.
3. **60s cache.** Two calls within 60s of a successful first call — first has `cache_hit=false`, second has `cache_hit=true` with identical `checked_at`. Integration test asserts the platform HTTP mock was called exactly once.
4. **Transient errors are not cached.** After a `platform_5xx` response, a subsequent call within 60s runs the probe live (asserted via a second platform HTTP call in the mock). `last_test_result` still reflects the transient error for UI display.
5. **Needs-reauth short-circuit.** Connection in `status=expired` → the endpoint returns `ok=false, error.code=needs_reauth` **without** calling the platform (integration test asserts mock was not called).
6. **Definitive 401 triggers mark-expired.** Platform returns 401 → response has `ok=false, error.code=auth_failed`, `mark_expired` was called exactly once, connection transitions to `expired`, and a re-auth notification is emitted through the IN-PRD-05 flow (assertion: one `reauth_requested` audit + one `INTEGRATION_NEEDS_REAUTH` notification).
7. **Scope-missing heuristic.** Platform returns 403 with a body signaling insufficient scope (test fixture modeled on Google's response shape) → `error.code=scope_missing` and `error.is_scope_issue=true`; still triggers `mark_expired`.
8. **Transient classifications stay `connected`.** 429, 5xx, **4xx-other-than-{401,403,429}** (classified `probe_misconfigured`), timeout, network — none of them invoke `mark_expired`; connection stays `status=connected`.
8a. **Probe-misconfigured emits an ops alert.** A 4xx-other response (e.g., a platform changed its endpoint from the value seeded in `PlatformDefinition.health_check_endpoint`) produces `error.code="probe_misconfigured"`, does NOT call `mark_expired`, and emits a Weave span / Slack alert so engineering can update the platform definition.
9. **No probe configured.** For a hypothetical platform definition with `health_check_endpoint=None`, endpoint returns `ok=false, error.code=no_probe_configured` with `probe=None`. No audit entry written in this branch (distinguishes "can't test" from "tested and failed").
10. **UI Test button visible on non-`Not connected` cards.** Clicking triggers the spinner → result surface (green / amber / red per §5.3) → auto-focus Reconnect on definitive failures.
11. **UI cache indicator.** Two clicks within 60s: second click shows "cached (verified N seconds ago)" with no network activity visible in the browser dev tools (asserted in Vitest + Testing Library via request mock counting).
12. **MCP tool.** Registered in `app/adk/tools/`; an ADK test-harness agent successfully calls `integrations.test_connection("google")` against a StubPlatform-backed connection and branches on the `ok` field.
13. **Audit log.** Each cache miss writes one `tested` audit entry with `metadata.ok` and (on failure) `metadata.error_code`. Cache hits do not write audit entries.
14. **No plaintext leakage.** Lint rule already enforced for `write_connection_audit` metadata is extended to reject `access_token` / `refresh_token` keys in `ConnectionTestResult.probe`. Weave spans and API responses pass the existing "no token strings" grep check.
15. **Latency budget.** p95 endpoint latency under 1.3 seconds end-to-end on cache miss against the real Google probe (1s timeout + overhead). Cache hits return in under 50ms.
16. **Typed frontend client.** `useTestConnectionMutation`, `ConnectionTestResult`, `ConnectionTestError` all typed; no `any` in `integrations.ts`; branded `ConnectionId` / `PlatformId` preserved.
17. **CH-PRD-04 Auth Status card interactive upgrade** *(conditional on CH-PRD-04 having shipped at IN-PRD-07 verification time)*. If CH-PRD-04 has shipped: with `integrations_connection_test_enabled=true`, `AuthStatusCard` renders the per-row Check Status button, clicking it fires `useTestConnectionMutation`, and row state transitions match CH-PRD-04 §5.6's four-state table (Authenticated / Needs re-auth / Transient / Not connected) — verified by `frontend/src/components/chat/__tests__/AuthStatusCard.spec.tsx`; with the flag off, the button is absent and the card remains read-only. If CH-PRD-04 has **not** yet shipped: this AC is deferred and verified as part of the follow-up PR that lands the AuthStatusCard extension after CH-PRD-04 merges.

## 8. Test plan

### Unit (backend, pytest)
- `test_testing.py` — one test per classification branch (happy, 401 auth_failed, 403 scope_missing, 429 rate_limited, 5xx, **400/404/405 probe_misconfigured** (each asserted non-transition of `status`), timeout, network, 409 needs_reauth short-circuit, non-connected short-circuit, no_probe_configured).
- `test_testing.py` — cache invalidation on reconnect: seed `conn.last_tested_at = T`, `conn.last_test_result = needs_reauth`, then update `conn.updated_at = T + 30s` (simulating a reconnect); call `test_connection` → assert the cache is bypassed and the probe runs (mock request count = 1, not cache-hit).
- `test_testing.py` — cache hit returns stored result without invoking credential-read or the probe.
- `test_testing.py` — transient result does not populate `last_tested_at`; successive call re-probes.
- `test_testing.py` — definitive-401 path calls `mark_expired` exactly once (assert via mock).
- `test_scope_error_parser.py` — Google scope-error fixture returns True; generic 403 body returns False; malformed body returns False (no raise).
- Audit — `tested` event written on cache miss, not on cache hit.

### Integration (hermetic, backend)
- Full endpoint flow against `StubPlatform` in each probe-response mode.
- Concurrent-call test: 10 parallel `POST /test` calls on the same connection; assert the platform mock was called at most once (first-writer-wins on the cache; others either see cache or also probe — both acceptable, but exactly-one is strongly preferred and achievable via a short Firestore-transaction window around the probe. If the simpler implementation lets up to N go through, accept and document — same reasoning as the refresh thundering-herd discussion in IN-PRD-02 §7).
- Rate-limit-style abuse test: 100 sequential calls within 60s → exactly 1 probe call, 99 cache hits, no errors.
- Feature-flag-off test: endpoint returns 404.

### Integration (real Google, gated)
- `@pytest.mark.external` test: connect a dev-env Google account → POST `/test` → assert `ok=true`. Manually revoke at Google (via Google's account-settings page outside the test; documented as a manual prerequisite for running this specific assertion) → POST `/test` → assert `ok=false, error.code in {auth_failed, needs_reauth}`. Gated by `RUN_EXTERNAL_INTEGRATION_TESTS=1`; runs in the IN-PRD-06 E2E suite.

### Unit (frontend, Vitest + Testing Library)
- `ConnectionTestResultBadge` renders each of the six variants (ok / ok-cached / transient / definitive / needs-reauth / no-probe) with correct copy, icon, and CTA presence.
- `useTestConnectionMutation` sets `isPending` during flight; surfaces both happy and error responses; no unhandled rejections.
- `ConnectionCard` test-button behavior: hidden on `Not connected`; clicking on `Connected` calls the mutation; definitive-failure auto-focuses Reconnect.

### Integration (frontend)
- TanStack Query cache invalidation: after a `needs_reauth` result, the connections list query refetches and the card re-renders with `Expired` status.

### MCP / ADK
- ADK test-harness agent invokes `integrations.test_connection("google")` against a StubPlatform-backed connection; asserts tool-call tracing is present; asserts the agent branches correctly on `result.ok`.

### Manual verification (prelaunch smoke)
- Connect real Google in dev → click Test → expect green check with latency.
- Disconnect at Google → click Test → expect red + Reconnect focus; verify the notification bell shows the re-auth notification.
- Temporarily block egress to `analyticsadmin.googleapis.com` at runtime (via a local proxy) → click Test → expect amber transient; verify connection stays `Connected` and no notification fires.

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| False-positive transient classification (platform returns 401 during a real multi-minute outage) | Accepted. The authoritative "connection is dead" detector is the consumer-protocol 401 path from IN-PRD-README §7.3. This endpoint is a user-facing verification surface; worst case a user clicks Test, sees transient, clicks again after the cache window, and sees the persistent 401 — at which point `mark_expired` fires normally. |
| Platform changes its response-body format for scope errors, breaking the heuristic | `is_scope_issue` degrades to `false` and the user sees generic `auth_failed` copy — still actionable (Reconnect). Scope-error fixture tests serve as the canary when updating client libraries. |
| Agents over-invoke the MCP tool in a loop | 60s cache + absence of explicit rate limits is fine because the cache hard-bounds cost per connection to one probe per minute regardless of call volume. Documented in the tool's docstring. |
| `no_probe_configured` platforms in the wild degrade the UX | Google, Meta, and Mailchimp all have `health_check_endpoint` set by IN-PRD-02 / IN-PRD-04. Adding a platform without one is a design-review signal; the `no_probe_configured` branch is defensive, not an expected path. |
| Concurrent Test + Force-Refresh races | Both operations touch the connection doc but different fields. Firestore last-writer-wins is acceptable here (Test persists `last_test_result` / `last_tested_at`; Force refresh persists `last_refreshed_at`). No correctness impact. |
| Single-probe design misses scope drift (Ads revoked but GA still granted) | Accepted per the user decision to ship a single probe per platform in v1. Per-capability probes tracked as v2 follow-up; the existing `scope_missing` heuristic partially covers this when the probe itself is gated on the relevant scope. |

### Open questions

- **Q:** Should the Test button be visible on `Not connected` cards to offer a "there's nothing to test yet" affordance? → **No.** Too noisy; Connect is the only sensible CTA in that state. Revisit if user research surfaces confusion.
- **Q:** Surface the last-verified timestamp as a subtle tooltip on the status badge of every card, even without clicking Test? → **Deferred.** Adds visual density; the cached-result behavior when Test is clicked already exposes this. Non-blocking fast-follow if users request it.
- **Q:** Expose probe `latency_ms` as a Weave metric for platform-SLO tracking? → **Yes.** Already in §5.4's span attributes; dashboards outside this PRD's scope.
- **Q:** Should the MCP tool accept an optional `force_refresh_cache=true` flag so agents can bypass the 60s cache when they genuinely need a fresh read? → **No in v1.** Agents never need to bypass a 60-second-old cache for preflight purposes; if the last result was `ok=true` 30s ago, that's good enough to proceed. Revisit only if a concrete agent failure mode shows up.

## 10. Reference

- Component plan: [`../implementation-plan.md`](../implementation-plan.md)
- Component README: [`../README.md`](../README.md) — §2.3 API Contracts (this PRD appends a row), §7.8 Feature-flag structure (this PRD adds `integrations_connection_test_enabled`)
- Upstream: [IN-PRD-02](./IN-PRD-02-google-oauth-flow.md), [IN-PRD-03](./IN-PRD-03-connection-management-ui.md), [IN-PRD-05](./IN-PRD-05-reauth-lifecycle.md)
- Peer: [IN-PRD-06](./IN-PRD-06-integration-testing-cleanup.md) — this PRD can ship during or after IN-PRD-06 without conflict
- Downstream consumer: [CH-PRD-04](../../chat/projects/CH-PRD-04-session-status-view.md) §5.6 Authentication Status card — ships read-only against IN-PRD-03's data; this PRD enables the Check Status button behind `integrations_connection_test_enabled`
- MCP guide: [`../../agentic-harness/mcp-architecture.md`](../../agentic-harness/mcp-architecture.md)
- CLAUDE.md rules in scope: PY-1, PY-2, PY-5, PY-7; C-2, C-4, C-5, C-6, C-8; T-1, T-3, T-4, T-5, T-6; G-1, G-2, G-3
