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

Use `check_graph_access()` pattern with super_admin bypass. See `routers/knowledge_graph/crud_factory.py`. Account/org access checking via `require_account_access()` and `require_organization_access()`.

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

### Kill-switch SLO

A super-admin flipping `is_active=false` on a flag propagates to every Cloud Run instance within ≤60 s (per-instance TTL; no Redis or Firestore listener in Release 1).

### Incident response

To kill a misbehaving feature in production, open `/admin/feature-flags` as a super-admin and toggle `is_active` off. If `default_enabled` is `true` (the flag was promoted for GA), also set `default_enabled` to `false` — otherwise `is_active=false` returns `default_enabled` and the feature remains on. Each Cloud Run instance propagates the change within ≤60 s of the last write.

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
