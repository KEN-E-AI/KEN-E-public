# CLAUDE.md - API

This file provides guidance for working with the KEN-E API codebase. For general project guidelines and best practices, refer to the [root CLAUDE.md](../CLAUDE.md).

## Overview

FastAPI REST service backed by Neo4j (graph DB) and Firestore (document DB), deployed on Cloud Run. Integrates with Vertex AI Agent Engine for chat completions and Firebase Auth for identity.

## Project Structure

```
api/src/kene_api/
├── main.py              # FastAPI app, lifespan events, health probes
├── config.py            # Settings class, environment config
├── database.py          # Neo4j driver, session management, retry logic
├── dependencies.py      # FastAPI Depends() singletons
├── exceptions.py        # Domain exception hierarchy
├── firestore.py         # Firestore client with lazy init
├── auth/
│   ├── user_context.py  # Firebase token → UserContext flow
│   └── ...
├── middleware/
│   ├── request_id.py    # X-Request-Id propagation via contextvars
│   └── auth_header.py   # OAuth credential extraction
├── routers/             # API route handlers
├── services/            # Business logic (separated from HTTP)
├── repositories/        # Data access layer
├── models/              # Pydantic models for all entities
└── metrics/             # Prometheus metrics
```

## Common Commands

```bash
# Development server
cd api && uv run uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
cd api && pytest tests/

# Switch environment
cd api && ./scripts/set_environment.sh [development|staging|production]
```

## Architecture Patterns

### Neo4j Session Management

Always use the async context manager — never create sessions manually:

```python
async with self.get_session() as session:
    result = await session.execute_read(_execute_query)
```

Three query methods on `Neo4jService`:
- `execute_query()` — read queries (`session.execute_read`)
- `execute_write_query()` — writes with RETURN (`session.execute_write`)
- `execute_write_operation()` — mutations without RETURN (returns summary counters)

Write queries retry up to 3 times with exponential backoff for defunct connection errors. See `database.py`.

### Dependency Injection

Singletons use `@lru_cache(maxsize=1)` wrapped by a FastAPI `Depends()` function:

```python
@lru_cache(maxsize=1)
def get_firestore_client() -> firestore.Client:
    ...

def get_firestore() -> firestore.Client:
    return get_firestore_client()  # Used in Depends()
```

See `dependencies.py`.

### Secret Manager Resolution

Config values support the `sm://` prefix for GCP Secret Manager. When a setting starts with `sm://`, the `get_env_or_secret()` helper resolves it at startup. See `config.py` and `shared.secrets`.

### Auth Flow

Firebase token → Firestore permissions → `UserContext` model:

1. Rate limiting check (super_admin `@ken-e.ai` users bypass)
2. Firebase ID token verification
3. Token revocation check
4. Cache lookup (Redis), then Firestore fetch
5. Auto-create user document if missing
6. Audit logging for security events

Two FastAPI dependencies: `get_current_user_context()` (required) and `get_optional_user_context()` (optional). See `auth/user_context.py`.

### Authorization

**Account-scoped endpoints** — the only sanctioned gate is `require_account_access_for(user, account_id, level)` from `auth/account_org.py`. It resolves the account's owning org, calls `has_account_permission`, and raises `404` on denial (anti-enumeration). Super-admin short-circuits the resolver. Use `"view"` for reads and `"edit"` for writes.

`UserContext.has_account_access()` is **deprecated** (IN-2) — it contains an any-org-admin bypass that breaks multi-tenant isolation. Calling it raises `NotImplementedError`. A CI grep guard (`tests/test_no_has_account_access_usage.py`) enforces this in every PR.

**Knowledge-graph endpoints** — use `check_graph_access()` in `routers/knowledge_graph/crud_factory.py`, which delegates to `require_account_access_for`.

**Organization-scoped endpoints** — use `require_organization_access()` from `auth/dependencies.py`.

### Repository Pattern

Abstract base → concrete implementation → cached decorator. See `repositories/`.

### Service Layer

Pure business logic separated from HTTP concerns. Routers call services; services call repositories. See `services/`.

### Custom Exceptions

Domain-grouped exceptions with rich context:
- **Config/Service:** `SecretManagerError`, `EmailServiceInitializationError`
- **Graph/Knowledge:** `NodeCreationException`, `NodeNotFoundException`, `NodeHasDependenciesException`, `DuplicateNodeException`, `ValidationException`, `GraphSyncException`

See `exceptions.py`.

### Graceful Degradation

Non-critical services (Redis, Weave, MCP) log errors but don't block startup. Critical services (Neo4j, Firestore) report unhealthy but also don't crash. The lifespan handler wraps each component in try/except. See `main.py`.

### Request ID Middleware

`X-Request-Id` propagation via `contextvars`. Every request gets a unique ID available anywhere via `get_request_id()`. See `middleware/request_id.py`.

## Feature Flags

See [`../docs/design/components/feature-flags/README.md`](../docs/design/components/feature-flags/README.md) for the full component design, targeting model, and architecture.

### Helper usage

```python
from kene_api.services.feature_flag_service import is_feature_enabled

# In a router or service — the helper swallows service errors and returns `default`
# so a flag-system outage never takes down the caller.
if await is_feature_enabled("automations_beta", ctx):
    # new code path
else:
    # existing code path
```

### Chat-component flags

Three flags registered by `api/scripts/seed_chat_feature_flags.py` (run once per environment):

| Flag key | Default | Gates |
|---|---|---|
| `chat_v2_enabled` | `True` (GA) | Master kill switch — `POST /api/v1/internal/chat/side-table/update` returns 404 when off; `GET /api/v1/chat/conversations` returns the `ListChatSessionsResponse` (PRD §4.1 shape) when on, or falls back to the legacy `ConversationListResponse` shape when off. |
| `chat_status_detail_enabled` | `True` (GA) | Session status view endpoint + toggle button (depends on `chat_v2_enabled`). |
| `chat_categories_enabled` | `True` (GA) | Category CRUD, sidebar filter, assign dropdown (depends on `chat_v2_enabled`). |

The flag gate is fail-closed: a Firestore outage on the flag read returns `default=False`, so the internal endpoint returns 404 rather than letting an unverified write through.

### Kill-switch SLO

A super-admin flipping `is_active=false` on a flag propagates to every Cloud Run instance within ≤60 s (per-instance TTL; no Redis or Firestore listener in Release 1). Use this runbook to disable a misbehaving feature in production without a deploy.

```
To kill a feature in production:

1. Open /admin/feature-flags as a super-admin.
2. Find the flag; flip is_active → off.
3. Confirm the toast ("Kill switch applied. Fully effective within 60 s").
4. Monitor error rates / user reports. Full propagation across all Cloud Run
   instances takes ≤60 s (cache TTL).
```

> **Important:** If the flag was promoted to GA (`default_enabled` is `true`), also set `default_enabled → false` after step 2 — otherwise `is_active=false` falls back to `default_enabled=true` and the feature remains on for all users.

**See also:** [`../docs/design/components/feature-flags/README.md`](../docs/design/components/feature-flags/README.md) — full component design; [§7.4 Caching and propagation](../docs/design/components/feature-flags/README.md#74-caching-and-propagation) — canonical ≤60 s end-to-end SLO.

The ≤60 s propagation is two-layered: backend Cloud Run instances re-read Firestore after the 60 s in-process LRU TTL expires; frontend clients revalidate via TanStack Query (`staleTime=60_000`) on the next `selectedAccount.accountId` change or explicit refetch.

## Rate Limiting

The API uses a layered rate-limiting architecture across eight named limiter instances. The physical implementation lives in `api/src/kene_api/rate_limiter.py` and `api/src/kene_api/auth/rate_limiting.py`; it is owned by the Agentic Harness component because every chat turn traverses this gate before reaching the root agent.

### Limiter instances

| Name | Limits | Key strategy | `fallback_cap_divisor` | `fail_open` | `emit_remaining_on_success` |
|---|---|---|---|---|---|
| `auth` | 10/min, 50/hr | IP (pre-auth) | 10 (÷10 on Redis outage) | False | False |
| `bad_token` | 10/min, 50/hr | IP (pre-auth) | 10 | False | False |
| `password_reset` | 3/min, 10/hr | IP (pre-auth) | 10 | False | False |
| `recaptcha` | 5/min, 20/hr | IP (pre-auth) | 10 | False | False |
| `early_release` | 5/min, 20/hr | IP (pre-auth) | 10 | False | False |
| `signup_policy` | 20/min, 100/hr | IP (pre-auth) | 10 | False | False |
| `token` | `KENE_TOKEN_RATE_LIMIT_PER_MINUTE`/min (default 60), `KENE_TOKEN_RATE_LIMIT_PER_HOUR`/hr (default 1000) | Authenticated UID (sha256[:16] hash) | 1 | True | True |
| `progress` | 120/min, 2000/hr | Authenticated UID | 1 | True | True |

**Security-critical limiters** (`auth`, `bad_token`, `password_reset`, `recaptcha`, `early_release`, `signup_policy`): `fallback_cap_divisor=10` means a Redis outage divides effective limits by 10 per process instance, preventing a Redis failure from silently disabling brute-force protection. `emit_remaining_on_success=False` prevents leaking bucket headroom to unauthenticated callers. (`signup_policy` guards the read-only signup-policy GET with generous caps but keeps the same fail-closed, IP-keyed posture.)

**Throughput limiters** (`token`, `progress`): `fail_open=True` means a Redis error or open circuit breaker allows the request through — a Redis outage must not cascade to a service outage. `emit_remaining_on_success=True` so clients can use the `X-RateLimit-Remaining` header for backoff.

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `KENE_TOKEN_RATE_LIMIT_PER_MINUTE` | `60` | Per-minute limit for the `token` limiter |
| `KENE_TOKEN_RATE_LIMIT_PER_HOUR` | `1000` | Per-hour limit for the `token` limiter |
| `KENE_RATE_LIMIT_BACKEND` | `redis` | `redis` (production) or `memory` (development/test). When `memory`, `build_rate_limiter` returns a `LocalRateLimiter` directly with no Redis dependency. |
| `KENE_RATE_LIMIT_REDIS_PREFIX` | `kene:ratelimit` | Prefix for all Redis ZSET keys. Change only if multiple services share a Redis instance. |
| `KENE_RATE_LIMIT_TRUSTED_HOPS` | `1` | Number of trailing X-Forwarded-For entries controlled by trusted proxies. On Cloud Run without a Global Load Balancer, `1` is correct (Cloud Run's own internal proxy is the only trusted hop). **If a GLB is ever placed in front of Cloud Run, bump this to `2`** — otherwise attackers can spoof the client IP by prepending entries to the XFF chain. The `_validated_ip_key` function emits a WARNING with `action="xff_short_chain"` when the chain is shorter than expected, which surfaces ingress-config drift. |

### Trusted-hops model and XFF parsing

`_validated_ip_key(request)` reads `KENE_RATE_LIMIT_TRUSTED_HOPS` (default 1) and returns `X-Forwarded-For[-trusted_hops]`. If the chain is shorter than `trusted_hops`, it returns the sentinel key `"ip:_no_xff_chain_"` and emits a structured WARNING log (fields: `expected_hops`, `actual_hops`, `path`, `xff_header`). The sentinel bucket is capped at 5/min across all sentinel hits via a separate Redis ZSET — preventing an attacker from weaponising the sentinel bucket as a DoS lever.

On Cloud Run, `request.client.host` is the load-balancer IP, not the client IP. The rate limiter deliberately does NOT fall back to `request.client.host` — using it would make IP-keyed rate limits trivially bypassable by rotating through many IPs.

**GLB runbook:** If a GCP Global Load Balancer is ever added in front of Cloud Run, set `KENE_RATE_LIMIT_TRUSTED_HOPS=2` in the Cloud Run service environment variables. The GLB appends the real client IP to the XFF chain as a second trusted hop; without this adjustment, all requests would land in the sentinel bucket.

### Response headers

`RedisRateLimiter` emits the following headers on every response:

| Header | 429 response | 200 response |
|---|---|---|
| `X-RateLimit-Limit` | Always | Always |
| `X-RateLimit-Remaining` | Always (value: 0) | Only if `emit_remaining_on_success=True` |
| `X-RateLimit-Reset` | Always (Unix timestamp) | Always |
| `Retry-After` | Always (seconds until window expires) | Never |

`LocalRateLimiter` emits only `Retry-After` on 429 responses (no per-window counters available in the in-memory backend).

### `rate_limit_backend_override` feature flag (rollback path)

The `rate_limit_backend_override` feature flag in Firestore switches all `SwitchableRateLimiter` instances to use their in-process `LocalRateLimiter` fallback on the next request, without a redeploy.

```
To roll back from Redis to in-memory rate limiting:

1. Open /admin/feature-flags as a super-admin.
2. Find rate_limit_backend_override; flip is_active → on.
3. Confirm the toast. Fully effective within ≤60 s (per-instance TTL).
4. Monitor: SwitchableRateLimiter logs "SwitchableRateLimiter: Redis
   unavailable..." with ERROR severity when the flag is active.
5. To restore Redis path: flip is_active → off.
```

Every write to this flag emits a `FEATURE_FLAG_CHANGED` audit event with `severity="CRITICAL"` (via `emit_audit_if_critical` in `feature_flags/security_critical.py`) and increments the `ratelimit_backend_override_flips_total` Prometheus counter. A Cloud Monitoring alert fires on any flip — see `deployment/terraform/monitoring.tf`.

### Circuit breaker

`SwitchableRateLimiter` wraps a `_CircuitBreaker` (K=10 consecutive Redis errors → 60 s cooldown → half-open probe). The `ratelimit_circuit_breaker_state` Prometheus gauge tracks state per limiter: 0=closed, 1=open, 2=half_open. All state transitions also appear in structured logs (`action="circuit_breaker_opened"`) and in the `ratelimit_redis_errors_total` counter.

## Email Service Setup (Local Development)

The API uses SendGrid for sending invitation emails. To enable this locally:

### Automatic Setup (Recommended)
```bash
./api/scripts/setup_local_dev.sh
```

### Manual Setup

1. **Authenticate with Google Cloud:**
   ```bash
   gcloud auth application-default login
   ```

2. **Set your GCP project:**
   ```bash
   export GOOGLE_CLOUD_PROJECT=ken-e-dev
   # Or add to api/.env: GOOGLE_CLOUD_PROJECT=ken-e-dev
   ```

3. **Verify Secret Manager access:**
   ```bash
   gcloud secrets versions access latest --secret="sendgrid-api-key" --project=ken-e-dev
   ```

4. **Test the setup:**
   ```bash
   python api/scripts/diagnose_email_service.py
   ```

   You should see: `Email service appears to be configured correctly`

### Alternative: Direct API Key (Without GCP Auth)

If you prefer not to use Secret Manager locally:

1. Get the SendGrid API key from Secret Manager or create a dev key at https://app.sendgrid.com/settings/api_keys
2. Add to `api/.env`:
   ```bash
   SENDGRID_API_KEY=SG.your-actual-key-here  # NOT sm://
   ```
3. Restart the API server

### Troubleshooting

- **"SendGrid API key not found"**: Run `./api/scripts/setup_local_dev.sh` or set `GOOGLE_CLOUD_PROJECT`
- **"Failed to fetch secret"**: Check that you're authenticated with `gcloud auth application-default login`
- **"Permission denied"**: Ensure you have the `roles/secretmanager.secretAccessor` role

## Vertex AI Agent Engine API Endpoints

### POST `/api/v1/chat/completions`
**Request:**
```json
{
  "messages": [{"role": "user", "content": "Hello", "timestamp": "2025-01-31T12:00:00Z"}],
  "stream": false,
  "session_id": "optional-session-id"
}
```

**Response:**
```json
{
  "role": "assistant",
  "content": "Response text",
  "session_id": "chat_1234567890_abc123def"
}
```

### GET `/api/v1/chat/health`
Check Agent Engine connectivity and status.

## Testing

- **Framework:** pytest with pytest-asyncio for async tests
- **Fixtures:** Session-scoped autouse fixtures in `conftest.py` for Firebase mocking, Prometheus cleanup, and environment patches
- **Key fixture:** `mock_firebase_auth()` — patches `verify_id_token`, Firestore service, and environment variables
- **Structure:** Unit tests colocated with source or in `tests/unit/`, integration tests in `tests/integration/`
- **Pattern:** Use `@pytest.fixture` with appropriate scope; prefer integration tests over heavy mocking

## Shape B Multi-Tenant Data Model Convention

All account-scoped Firestore data lives under `accounts/{account_id}/{resource}/...`.

Examples:
- Skill: `accounts/acc_abc/skills/sk_123`
- Strategy doc version: `accounts/acc_abc/strategy_docs/swot/versions/3`
- Audit entry: `accounts/acc_abc/strategy_audit/audit_42`

Account-level deletion sweeps via `firestore.recursive_delete(db.collection("accounts").document(account_id))` — one call, all subcollections gone.

Exceptions (Shape C — global collection with `account_id` field):
- `notifications` — users query N accounts at once via `where("account_id","in",[batch])`
- `usage_records` — org-level billing aggregation

See [Review 15 in DESIGN-REVIEW-LOG](../docs/design/DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1) for full rationale.
