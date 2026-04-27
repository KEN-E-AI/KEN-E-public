# DP-PRD-02 — Google Analytics Connector

**Status:** Draft — ready to start once DP-PRD-01 + IN-PRD-02 ship
**Owner team:** Backend (Data Pipeline)
**Blocked by:** DP-PRD-01 (`DataPipelineService` + models + internal run endpoint); IN-PRD-02 (Google OAuth flow + `/api/v1/internal/integrations/credentials/{account_id}/{platform_id}` internal endpoint)
**Blocks:** DP-PRD-03 (task-system integration requires a real connector to prove the end-to-end path); SE-PRD-02 (SAR-E weekly KPI ingestion depends on the 4 daily jobs seeded here AND on `GoogleAnalyticsConnector.get_history_depth()` lighting up the internal `/history-depth` endpoint scoped in DP-PRD-01 §6.7)
**Estimated effort:** 4–5 days

---

## 1. Context

DP-PRD-01 ships the service scaffold and the `StubConnector`. This PRD delivers the **first real connector** — `GoogleAnalyticsConnector` — along with an 8-job starter catalog seeded into the global `data_pipeline_jobs/*` collection. Four of those jobs are SAR-E-specific (`ga.unbranded_search_daily`, `ga.branded_search_daily`, `ga.pdp_views_daily`, `ga.first_purchases_daily`) and unblock SE-PRD-02's weekly ingestion automation.

The connector uses the official `google-analytics-data` Python client (GA Data API v1). **It does not go through MCP** — the decision recorded at plan §6.3 is that the MCP path is the right shape for the reasoning-heavy Google Analytics Specialist (AH-PRD-03) but the wrong shape for deterministic extraction. Two independent failure modes, two independent upgrade paths, one platform.

Credentials are loaded exclusively through Integrations' internal endpoint (`GET /api/v1/internal/integrations/credentials/{account_id}/google`, OIDC-authed). The connector never reads Firestore token docs directly — that substrate belongs to IN-PRD-01 and IN-PRD-02.

This PRD also ships the first real rate-limit enforcement layer (per-account, per-connector), retry and error-handling policy (transient → retry with backoff; semantic 4xx → fail + notification + hold plan; auth 401/403 → Integrations re-auth flow), and the observability glue that fills in the `data_pipeline.run` Weave span with GA-specific attributes.

What this PRD is **not:** the task-system dispatch wiring (DP-PRD-03); the frontend (DP-PRD-04); additional connectors for Google Ads, Meta, Mailchimp (DP-PRD-05); BigQuery external-table materialization for GA jobs (deferred until DP-PRD-06 telemetry proves value).

## 2. Scope

### In scope

- `GoogleAnalyticsConnector` implementing `DataPipelineConnector`, wrapping the official `google-analytics-data` client
- Starter catalog — 8 `DataPipelineJob` docs seeded into the global `data_pipeline_jobs/*` collection via a new migration:
  - `ga.sessions_by_date`
  - `ga.transactions_by_date`
  - `ga.conversions_by_source_medium`
  - `ga.top_landing_pages`
  - `ga.unbranded_search_daily` — SAR-E; `inputs={target_date: date}` default yesterday UTC; output `[{date, value}]`; `default_cache_ttl_seconds=0`
  - `ga.branded_search_daily` — same shape
  - `ga.pdp_views_daily` — same shape
  - `ga.first_purchases_daily` — same shape
- Credential loading via the Integrations internal endpoint `GET /api/v1/internal/integrations/credentials/{account_id}/google` (OIDC-authed)
- Rate-limit enforcement per plan §3.3 GA starting points: **100/day · 20/hr · 5 concurrent** per account; breach returns `429` with `Retry-After`; 3 breaches in a 24-hour window fires an account-level notification via the existing `create_notification` API
- Retry + error-handling policy:
  - Transient (network error, platform 5xx, platform 429): exponential backoff, **3 attempts total** (base delay 2s, jitter ±25%)
  - Semantic 4xx (400, 404 property not found, invalid dimension, etc.): fail the run immediately; surface a notification with the sanitized API response; downstream dispatch (DP-PRD-03) holds the plan
  - Auth 401 / 403: invoke Integrations' mark-expired hook (`POST /api/v1/internal/integrations/connections/{id}/mark-expired` from IN-PRD-05) and fail the run with `error_message="integration_needs_reauth"`; downstream tasks halt until the user reconnects
- Output serialization:
  - **Parquet** (default) for tabular jobs — written to GCS via A-PRD-03's artifact-write helper (wired up in DP-PRD-03); in this PRD the connector only returns a `PipelineOutput`, and the Parquet write is exercised via a unit test of `DataPipelineService`'s serialization path
  - **JSON** fallback for non-tabular shapes (no GA jobs in the v1 starter catalog use JSON; the code path is verified against `StubConnector`-style inputs to keep regression-proof)
- Weave span `data_pipeline.run` populated with `{connector: "google_analytics", operation, input_hash, row_count, cache_hit, test_mode}` on every invocation; span records `error` status with sanitized message on failure
- **`GoogleAnalyticsConnector.get_history_depth(credentials)` implementation** — lights up the internal `/history-depth` endpoint scoped in DP-PRD-01 §6.7 for `connector="google_analytics"`. Returns `weeks_available: int` for the resolved GA4 property by reading the property's `dataRetention` configuration via `AnalyticsAdminServiceAsyncClient.get_data_retention_settings(name="properties/{id}/dataRetentionSettings")`. Maps the API enum to weeks: `MONTHS_2 → 9`, `MONTHS_14 → 60`, `MONTHS_26 → 113`, `MONTHS_38 → 165`, `MONTHS_50 → 217`, default `60` (the GA4 default) on unknown values. SAR-E's SE-PRD-02 backfill probe consumes this through the internal endpoint.
- Unit tests with a mocked GA client and a stub credentials service
- Integration tests against a real GA4 property + real OAuth tokens, gated behind `@pytest.mark.platform` (matches existing platform-sensitive test convention)

### Out of scope

- **`PlanTask.assignee_type="data_pipeline"` extension and orchestrator dispatch branch.** Owned by DP-PRD-03.
- **`TaskArtifact` write integration via A-PRD-03.** DP-PRD-02 returns `PipelineOutput` from the connector; the artifact-write hand-off is DP-PRD-03's scope.
- **Custom per-account GA jobs via the authoring UI.** Owned by DP-PRD-04. The 8 starter jobs here are `is_system=true` global catalog entries.
- **Google Ads, Meta, Mailchimp connectors.** Owned by DP-PRD-05.
- **BigQuery external-table provisioning.** The `bigquery_external_table` field is left `None` on all 8 seeded jobs in this PRD. The feature is a DP-PRD-06 polish item gated on telemetry demand.
- **Reasoning-path changes to the GA Specialist (AH-PRD-03).** Independent failure domain per plan §6.3.

## 3. Dependencies

- **DP-PRD-01 (Foundation):** hard prerequisite. Supplies `DataPipelineService`, the `DataPipelineConnector` protocol, the internal run endpoint, the `DataPipelineRun` persistence layer, the cache, and the Weave span scaffold. This PRD registers `GoogleAnalyticsConnector` with the service's connector registry.
- **IN-PRD-02 (Google OAuth):** hard prerequisite. Provides the Google `PlatformConnection` lifecycle and the internal credentials endpoint `GET /api/v1/internal/integrations/credentials/{account_id}/google` that this connector calls on every invocation. Without it, the connector has no tokens.
- **IN-PRD-05 (Re-auth lifecycle):** soft dependency. On 401/403 this connector calls `POST /api/v1/internal/integrations/connections/{id}/mark-expired`; if IN-PRD-05 has not merged when DP-PRD-02 ships, the mark-expired side effect can be stubbed as a log-only event and swapped in during IN-PRD-05 integration.
- **DM-PRD-00 (Migration Foundation):** soft dependency. The migration that seeds the 8 global catalog entries (`DM-2026-05-08-ga-starter-catalog.py`) runs on DM-PRD-00's framework. Reuses the framework published in DP-PRD-01's migration.
- **Notifications (existing):** the rate-limit-breach notification uses the existing `create_notification` API + the `NotificationCategory` enum. A new category `"Data Pipeline Rate Limit"` is added (coordinated; owner is this PRD).
- **SE-PRD-02 (Weekly KPI ingestion):** this PRD's 4 SAR-E-specific jobs unblock SE-PRD-02; the output shape (`[{date: YYYY-MM-DD, value: float}]`) is the stable schema SE-PRD-02 ingests.
- **Existing files to study:**
  - `api/src/kene_api/services/notification_service_v2.py` — `create_notification` + `NotificationCategory` (new category added here)
  - `api/src/kene_api/routers/oauth_integrations.py` — existing OAuth wiring to look at before IN-PRD-02 lands (for pattern, not for import)
  - `app/utils/gcs.py` — Parquet write helper (shared with DP-PRD-01)
  - `services/data_pipeline/src/kene_data_pipeline/service.py` (from DP-PRD-01) — `DataPipelineService` where the connector registry lives
  - `services/data_pipeline/src/kene_data_pipeline/connectors/stub.py` (from DP-PRD-01) — reference for the protocol implementation pattern
  - [`../implementation-plan.md`](../implementation-plan.md) §3.3 (execution model + rate limits + error handling + test-mode policy), §5 (SAR-E integration), §6.3 (AH-PRD-03 note — independent failure modes)
  - [`../../sar-e/implementation-plan.md`](../../sar-e/implementation-plan.md) §3.1, §5.1 — SAR-E's consumption contract for the 4 daily jobs
  - [`../../integrations/implementation-plan.md`](../../integrations/implementation-plan.md) §3.4, §4 — credential-read endpoint
  - Google Analytics Data API Python client reference: <https://googleapis.dev/python/analyticsdata/latest/index.html>

## 4. Data contract

### 4.1 Connector implementation

```python
class GoogleAnalyticsConnector:
    """Implements DataPipelineConnector for GA4 Data API."""

    def __init__(
        self,
        client_factory: Callable[[dict], BetaAnalyticsDataAsyncClient],
        rate_limiter: RateLimiter,
        notification_client: NotificationService,
    ) -> None: ...

    async def run(
        self,
        operation: str,
        inputs: dict,
        credentials: dict,         # {access_token, expires_at, external_account_id}
    ) -> PipelineOutput: ...
```

**Dispatch table** — `operation` → internal method:

| `operation` | Method | GA4 API call | Output row shape |
|---|---|---|---|
| `sessions_by_date` | `_run_sessions_by_date` | `run_report` — dimensions `[date]`, metrics `[sessions]` | `{date, sessions}` |
| `transactions_by_date` | `_run_transactions_by_date` | `run_report` — dimensions `[date]`, metrics `[transactions, totalRevenue]` | `{date, transactions, total_revenue}` |
| `conversions_by_source_medium` | `_run_conversions_by_source_medium` | `run_report` — dimensions `[date, sessionSourceMedium]`, metrics `[conversions]` | `{date, source_medium, conversions}` |
| `top_landing_pages` | `_run_top_landing_pages` | `run_report` — dimensions `[landingPage]`, metrics `[sessions, conversions]`, ordered by sessions desc, limit from inputs | `{landing_page, sessions, conversions}` |
| `unbranded_search_daily` | `_run_unbranded_search_daily` | `run_report` — segment: non-branded organic; dimensions `[date]`, metrics `[sessions]` | `{date, value}` |
| `branded_search_daily` | same | segment: branded organic | `{date, value}` |
| `pdp_views_daily` | same | page path filter on product-detail pattern | `{date, value}` |
| `first_purchases_daily` | same | metric `firstTimePurchaserConversions` | `{date, value}` |

### 4.2 Starter catalog — job-level inputs

#### `ga.sessions_by_date` (and `ga.transactions_by_date`)

```python
input_schema = {
    "type": "object",
    "properties": {
        "start_date": {"type": "string", "format": "date"},
        "end_date": {"type": "string", "format": "date"},
        "property_id": {"type": "string"},   # GA4 property id; resolved from credentials.external_account_id if omitted
    },
    "required": ["start_date", "end_date"],
    "additionalProperties": False,
}
output_format = "parquet"
default_cache_ttl_seconds = 3600          # 1 hour — historical daily data is stable
test_mode_policy = "run_normally"
```

#### `ga.conversions_by_source_medium`

Same shape as `sessions_by_date` plus optional `limit: int = 100` on the source-medium dimension.

#### `ga.top_landing_pages`

Adds `limit: int = 50` (max 1000 per GA4 limit) and optional `page_path_prefix: string`.

#### SAR-E daily jobs — `ga.unbranded_search_daily`, `ga.branded_search_daily`, `ga.pdp_views_daily`, `ga.first_purchases_daily`

```python
input_schema = {
    "type": "object",
    "properties": {
        "target_date": {"type": "string", "format": "date"},    # default: yesterday UTC (computed client-side)
        "property_id": {"type": "string"},
    },
    "required": [],
    "additionalProperties": False,
}
output_format = "parquet"
default_cache_ttl_seconds = 0           # each daily pull is unique by date
test_mode_policy = "run_normally"       # SAR-E needs real values in test runs
```

**Output row shape (stable contract for SE-PRD-02):** `[{date: "YYYY-MM-DD", value: float}]`. A 7-day pull returns 7 rows.

### 4.3 Rate-limit state (per-account, per-connector)

Tracked in Firestore at `accounts/{account_id}/data_pipeline_rate_limits/{connector}`:

```python
class RateLimitCounter(BaseModel):
    account_id: str
    connector: str                      # "google_analytics"
    day_window_start: datetime          # UTC midnight of the current day
    day_count: int
    hour_window_start: datetime
    hour_count: int
    concurrent: int                     # currently-in-flight runs
    breach_events_24h: list[datetime]   # for the 3-in-24h notification trigger
```

Enforcement rule (per plan §3.3 GA):

| Limit | Value | Check |
|---|---|---|
| `day_count` | 100 | `day_count < 100` |
| `hour_count` | 20 | `hour_count < 20` |
| `concurrent` | 5 | `concurrent < 5` |

Breach → `HTTP 429` from `DataPipelineService` before the connector is invoked; `Retry-After` header set to the minimum TTL of the violated window. Breach is recorded in `breach_events_24h`; third breach in 24h fires a `NotificationCategory."Data Pipeline Rate Limit"` notification with a deep link to `/settings/integrations/{connection_id}`.

### 4.4 Weave span enrichment

Every invocation emits `data_pipeline.run` with:

```python
{
    "connector": "google_analytics",
    "operation": "transactions_by_date",
    "input_hash": "<sha256>",
    "row_count": <int>,                 # 0 on cache hit + 0 on failure before response
    "cache_hit": <bool>,
    "test_mode": <bool>,
    # On failure:
    "error_class": "<transient|semantic|auth|timeout>",
    "error_message_sanitized": "<str, no PII>",
}
```

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `services/data_pipeline/src/kene_data_pipeline/connectors/google_analytics.py` — `GoogleAnalyticsConnector` + per-operation methods + `get_history_depth(credentials) -> int` calling the GA Admin API's `getDataRetentionSettings` and mapping the enum to weeks |
| Create | `services/data_pipeline/src/kene_data_pipeline/connectors/ga_credentials.py` — small wrapper that calls `GET /api/v1/internal/integrations/credentials/{account_id}/google` and refreshes on 401 |
| Create | `services/data_pipeline/src/kene_data_pipeline/rate_limit.py` — `RateLimiter` + Firestore-backed counters + `check_and_increment(account_id, connector)` |
| Create | `services/data_pipeline/src/kene_data_pipeline/retry.py` — `exponential_backoff` helper + `classify_error(exc) -> Literal["transient", "semantic", "auth", "timeout"]` |
| Modify | `services/data_pipeline/src/kene_data_pipeline/service.py` (DP-PRD-01) — register `GoogleAnalyticsConnector`; call `RateLimiter.check_and_increment` before connector dispatch; on `auth` errors call the Integrations mark-expired hook |
| Modify | `services/data_pipeline/pyproject.toml` — add `google-analytics-data`, `pyarrow`, `httpx` |
| Create | `deployment/migrations/DM-2026-05-08-ga-starter-catalog.py` — seeds the 8 global catalog entries into `data_pipeline_jobs/*` with `is_system=true` |
| Modify | `api/src/kene_api/models/kene_models.py` — add `"Data Pipeline Rate Limit"` to `NotificationCategory` |
| Create | `services/data_pipeline/tests/unit/test_google_analytics_connector.py` |
| Create | `services/data_pipeline/tests/unit/test_rate_limit.py` |
| Create | `services/data_pipeline/tests/unit/test_retry.py` |
| Create | `services/data_pipeline/tests/unit/test_ga_credentials.py` |
| Create | `services/data_pipeline/tests/integration/test_ga_connector_live.py` (marked `@pytest.mark.platform`) |
| Create | `services/data_pipeline/tests/integration/test_rate_limit_enforcement.py` |

### Credential-loading flow

```
DataPipelineService.run(...)
  ├─ resolve DataPipelineJob (job.connector="google_analytics")
  ├─ RateLimiter.check_and_increment(account_id, "google_analytics")
  │    ├─ breach → raise RateLimitExceeded → 429
  │    └─ ok    → proceed
  ├─ GaCredentialsClient.get_credentials(account_id)
  │    └─ GET /api/v1/internal/integrations/credentials/{account_id}/google  (OIDC)
  │         returns {access_token, expires_at, external_account_id}
  ├─ GoogleAnalyticsConnector.run(operation, inputs, credentials)
  │    ├─ retry 3× on transient errors (network, 5xx, 429 from Google)
  │    ├─ on 401/403 → mark-expired via IN-PRD-05 + raise AuthExpired → fail run
  │    └─ on 2xx → return PipelineOutput
  └─ Persist DataPipelineRun with status succeeded/failed
```

### Error classification

```python
def classify_error(exc: Exception) -> Literal["transient", "semantic", "auth", "timeout"]:
    # google.api_core.exceptions.DeadlineExceeded / Aborted / Unavailable → transient
    # google.api_core.exceptions.ResourceExhausted (429 from Google) → transient (backoff applies)
    # google.api_core.exceptions.Unauthenticated (401) → auth
    # google.api_core.exceptions.PermissionDenied (403) → auth
    # google.api_core.exceptions.InvalidArgument (400) → semantic
    # google.api_core.exceptions.NotFound (404) → semantic
    # asyncio.TimeoutError → timeout
    # network errors (httpx/grpc) → transient
    # everything else → transient (fail-safe: let the backoff catch it)
```

**Retry schedule (transient errors):**

| Attempt | Delay (s) | Jitter |
|---|---|---|
| 1 | — | — |
| 2 | 2 | ±25% |
| 3 | 4 | ±25% |

Total max wait ≈ 8s before final failure. Well under the service's 10-minute cap (DP-PRD-01).

### Rate-limit enforcement algorithm

```python
async def check_and_increment(account_id: str, connector: str) -> None:
    async with firestore_transaction() as txn:
        doc = await txn.get(path_for(account_id, connector))
        now = utcnow()
        # Roll windows if we've crossed boundaries
        if doc.day_window_start < day_start(now):
            doc.day_window_start = day_start(now)
            doc.day_count = 0
        if doc.hour_window_start < hour_start(now):
            doc.hour_window_start = hour_start(now)
            doc.hour_count = 0
        # Enforce
        limits = LIMITS[connector]   # {day: 100, hour: 20, concurrent: 5}
        if doc.day_count >= limits["day"]:
            raise RateLimitExceeded(retry_after=seconds_until_next_day(now))
        if doc.hour_count >= limits["hour"]:
            raise RateLimitExceeded(retry_after=seconds_until_next_hour(now))
        if doc.concurrent >= limits["concurrent"]:
            raise RateLimitExceeded(retry_after=30)
        # Increment
        doc.day_count += 1
        doc.hour_count += 1
        doc.concurrent += 1
        await txn.set(path_for(account_id, connector), doc)

async def release_concurrency_slot(account_id: str, connector: str) -> None:
    async with firestore_transaction() as txn:
        doc = await txn.get(path_for(account_id, connector))
        doc.concurrent = max(0, doc.concurrent - 1)
        await txn.set(path_for(account_id, connector), doc)
```

Finalizer in `DataPipelineService` releases the concurrency slot in a `try/finally` around the connector call.

Breach tracking: on `RateLimitExceeded`, append `now` to `breach_events_24h`, pruning entries older than 24h. If the pruned list has `len >= 3`, emit the notification once per 24h window (suppress repeat notifications by checking `last_breach_notified_at`).

## 6. API contract

### 6.1 Internal (consumed)

**`GET /api/v1/internal/integrations/credentials/{account_id}/google`** (owned by IN-PRD-02)

Response:

```json
{
  "access_token": "ya29....",
  "expires_at": "2026-04-23T09:00:00Z",
  "external_account_id": "properties/123456789"
}
```

**`POST /api/v1/internal/integrations/connections/{connection_id}/mark-expired`** (owned by IN-PRD-05)

Called on a 401/403 from GA. Empty body; returns `204`.

### 6.2 External (no new endpoints)

This PRD ships no new user-facing API endpoints. The 8 starter jobs become available via `GET /api/v1/data-pipeline/jobs` (DP-PRD-01) after the seeding migration runs. Invocation happens through `POST /api/v1/internal/data-pipeline/run` (DP-PRD-01).

### 6.3 Error response shapes

Failures from the connector propagate to the internal run endpoint (DP-PRD-01) as `DataPipelineRun.status="failed"` with `error_message` set. The error-classification maps to user-visible surfaces as follows:

| Class | `error_message` prefix | Notification category | User action |
|---|---|---|---|
| `transient` (after 3 retries) | `"transient_error_after_retry: "` | none in v1 | retry by re-activating the plan |
| `semantic` | `"semantic_error: "` | `"Integration Error"` | edit inputs or job |
| `auth` | `"integration_needs_reauth"` | `"Integration Needs Re-auth"` (from IN-PRD-05) | reconnect in `/settings/integrations` |
| `timeout` | `"timeout_10_min"` | none | retry |

`error_message` is sanitized through the existing FastAPI exception handlers before it reaches the run doc; it never contains tokens or raw GA responses.

### 6.4 Consumption rules

- The GA connector is invoked **only** through `DataPipelineService` — no direct callers. AH-PRD-03 continues to own the MCP-based reasoning path and does not route through this connector (plan §6.3).
- `credentials.external_account_id` is the GA4 property id. If the job's `inputs.property_id` is set, it takes precedence; otherwise the connector uses `external_account_id` from the credentials response.
- SAR-E's SE-PRD-02 invokes the 4 daily jobs one-at-a-time (per-day) via its weekly ingestion plan (plan §5). The per-hour rate limit of 20 comfortably accommodates 7 invocations × 4 jobs = 28 calls spaced over the ingestion window.

## 7. Acceptance criteria

1. `GoogleAnalyticsConnector` implements `DataPipelineConnector` — `isinstance(connector, DataPipelineConnector)` is `True` at runtime via the runtime-checkable `Protocol`.
2. The 8 starter jobs exist in `data_pipeline_jobs/*` after the seeding migration: `ga.sessions_by_date`, `ga.transactions_by_date`, `ga.conversions_by_source_medium`, `ga.top_landing_pages`, `ga.unbranded_search_daily`, `ga.branded_search_daily`, `ga.pdp_views_daily`, `ga.first_purchases_daily`. All carry `is_system=true`.
3. Each SAR-E-specific job (`ga.unbranded_search_daily`, `ga.branded_search_daily`, `ga.pdp_views_daily`, `ga.first_purchases_daily`) has `default_cache_ttl_seconds=0`, `test_mode_policy="run_normally"`, `input_schema` accepting optional `target_date` (default yesterday UTC, computed by `DataPipelineService` if omitted), and output rows of shape `[{date: "YYYY-MM-DD", value: float}]`.
4. A valid invocation of `ga.transactions_by_date` with date-range inputs returns a `PipelineOutput` whose rows match the expected columns `{date, transactions, total_revenue}` and whose `PipelineOutput.schema` declares matching `FieldSpec` entries.
5. A transient error (simulated via a GA client mock raising `google.api_core.exceptions.Unavailable` twice then succeeding) results in exactly 3 client calls and a successful run.
6. A permanent transient error (3 consecutive `Unavailable` responses) fails the run with `error_message="transient_error_after_retry: <sanitized>"`; the Weave span records `error_class="transient"`.
7. A `google.api_core.exceptions.Unauthenticated` (401) triggers exactly one call to `POST /api/v1/internal/integrations/connections/{connection_id}/mark-expired` and fails the run with `error_message="integration_needs_reauth"`; Weave span records `error_class="auth"`.
8. A `google.api_core.exceptions.InvalidArgument` (400) fails the run immediately (no retry) with `error_message` prefixed `"semantic_error: "`; a notification with category `"Integration Error"` is created for the account.
9. Rate-limit enforcement: the 21st GA invocation in a single hour for a single account returns `429` with a `Retry-After` header pointing at the next hour boundary. The 101st in a day returns `429` with `Retry-After` pointing at the next UTC midnight. The 6th concurrent invocation returns `429` with `Retry-After=30`. Cross-account isolation: account B hitting 21 within an hour is not affected by account A's counter.
10. Breach tracking: 3 rate-limit breaches in a 24-hour window for the same account fires exactly one `"Data Pipeline Rate Limit"` notification; subsequent breaches in the same 24-hour window do not duplicate it.
11. Credential loading: the connector's `run()` reads credentials exclusively via `GET /api/v1/internal/integrations/credentials/{account_id}/google`; it never reads `accounts/{account_id}/platform_connections/*` directly (verified via a grep-style unit test on the connector module's imports).
12. On 401 from GA, the retry logic does NOT re-attempt — auth errors are terminal; only the mark-expired hook fires. (Distinct from transient retry.)
13. Weave span `data_pipeline.run` on a `google_analytics` invocation carries exactly `{connector, operation, input_hash, row_count, cache_hit, test_mode}` on success; on failure it additionally carries `{error_class, error_message_sanitized}` with no token or raw-response leakage (asserted via substring absence of `access_token` in the span payload).
14. Parquet serialization: `DataPipelineService` writes the `PipelineOutput` rows as Parquet to GCS with a schema matching the declared `FieldSpec` list. A roundtrip test reads the Parquet file back and compares rows to the source `PipelineOutput`.
15. SAR-E contract test: invoking `ga.unbranded_search_daily` with `target_date="2026-04-22"` returns a `PipelineOutput` with exactly 1 row whose shape is `{"date": "2026-04-22", "value": <float>}`. (Uses mocked GA client in unit tests; live GA4 in the platform-marked integration test.)
16. **`GoogleAnalyticsConnector.get_history_depth(credentials)`** returns the right week count for each `dataRetentionSettings.eventDataRetention` enum: `MONTHS_2 → 9`, `MONTHS_14 → 60`, `MONTHS_26 → 113`, `MONTHS_38 → 165`, `MONTHS_50 → 217`. The internal endpoint `GET /api/v1/internal/data-pipeline/jobs/ga.sessions_by_date/history-depth?account_id=A` (DP-PRD-01 §6.7) returns `{"weeks_available": <int>}` matching the connector's value when called with valid credentials; returns `409` `{"reason": "needs_reauth", ...}` when the GA connection is in `expired` state.
17. `make lint` passes (**G-1**) and `pytest services/data_pipeline/tests/` passes green on CI with platform-marked tests skipped; running with `pytest -m platform` and live credentials passes against a seed GA4 property.

## 8. Test plan

**Unit tests** (`services/data_pipeline/tests/unit/`):

- `test_google_analytics_connector.py`
  - Per-operation dispatch table coverage: each of the 8 operations invokes its mapped method; unknown operation raises `NotImplementedError`
  - Output row shape conformance for each operation (rows match the declared `output_schema`)
  - SAR-E daily jobs: mock returns 1 row → `PipelineOutput.rows == [{"date": "...", "value": ...}]`
  - `property_id` resolution: `inputs.property_id` wins over `credentials.external_account_id`; when both absent, validator fails at schema stage
  - Mock GA client raises `Unavailable` → 3 attempts → success on the 3rd; raises always → 3 attempts → fail
  - `Unauthenticated` → no retry, mark-expired called once, `AuthExpired` raised
  - `InvalidArgument` → no retry, `SemanticError` raised with sanitized message
  - `get_history_depth`: each `dataRetentionSettings.eventDataRetention` enum maps to the documented week count; an unknown enum returns the default `60`; `Unauthenticated` from the Admin API surfaces as `AuthExpired` (same handling as `run`).
- `test_rate_limit.py`
  - First invocation populates counters
  - 20th hour invocation succeeds, 21st raises `RateLimitExceeded` with `retry_after == seconds_until_next_hour`
  - 100th day invocation succeeds, 101st raises `RateLimitExceeded` with `retry_after == seconds_until_next_day`
  - 5 concurrent slots: the 5th acquires, the 6th raises
  - Cross-account: account A's counter increment does not affect account B
  - Breach tracking: 3 breaches in 24h → notification emitted exactly once; 4th breach in same window → no additional notification
  - Window rollover: at UTC midnight, `day_count` resets; at the top of the hour, `hour_count` resets
- `test_retry.py`
  - `classify_error` maps each Google API exception class to the right bucket
  - `exponential_backoff` emits delays `[2, 4]` with ±25% jitter
- `test_ga_credentials.py`
  - Credential-fetch wraps the OIDC call; returns `{access_token, expires_at, external_account_id}`
  - On 401 from the credentials endpoint: raises `CredentialsUnavailable` (upstream service behavior)

**Integration tests** (`services/data_pipeline/tests/integration/`):

- `test_rate_limit_enforcement.py` — drive `DataPipelineService` with a `StubConnector` counting ~25 times; assert the 21st returns `429`
- `test_ga_connector_live.py` (marked `@pytest.mark.platform`, live GA4 property + OAuth-obtained token)
  - `ga.sessions_by_date` for last-7-days → row count == 7 (or less if property has gaps)
  - `ga.transactions_by_date` returns non-empty rows with correct dtypes
  - `ga.unbranded_search_daily` with `target_date` yesterday returns exactly 1 row
  - Parquet roundtrip via `DataPipelineService` serialization path — read back equals source
  - `get_history_depth` against the live property returns a positive integer matching the property's configured retention (default GA4 setup yields `60`).

**E2E** — deferred to DP-PRD-03 once the orchestrator dispatch branch is wired (end-to-end GA job runs through a real `PlanTask`, writes a `TaskArtifact`, downstream agent task reads it).

## 9. Risks & open questions

### Resolved decisions

| Decision | Resolution |
|---|---|
| GA Data API access path | **Official `google-analytics-data` Python client, not MCP.** Separate failure domains from AH-PRD-03's reasoning path. Plan §6.3. |
| Credential loading | **Exclusively via Integrations internal endpoint.** No direct Firestore token reads. Plan §3.3. |
| Rate-limit starting points | **100/day · 20/hr · 5 concurrent per account.** Plan §3.3. DP-PRD-06 telemetry tunes if needed. |
| Breach notification threshold | **3 breaches in 24 hours.** One notification per 24h window, suppressed on repeats. Plan §3.3. |
| Retry policy | **3 attempts, exponential backoff (2s, 4s, jitter ±25%).** Matches plan §3.3 "3 attempts." |
| Auth-error handling | **Mark-expired via Integrations + fail run.** Downstream tasks halt until reconnect. Plan §3.3. |
| Test-mode behavior | **`run_normally` for all 8 starter jobs.** Pipeline tasks produce real data so downstream test runs can validate. Plan §3.3, plan §10 resolved decisions. |
| SAR-E output shape | **`[{date, value}]` with `default_cache_ttl_seconds=0`.** Plan §5, plan §10 resolved decisions. |
| Artifact format for all 8 jobs | **Parquet.** All 8 are tabular. |

### Remaining open questions

| Question | Disposition |
|---|---|
| Segment definitions for `unbranded_search_daily` / `branded_search_daily` | First pass: "branded organic" = source=google AND query contains the account's brand terms (pulled from Knowledge Graph or account profile at job-authoring time). **TODO**: confirm the exact segment definition with SAR-E team during DP-PRD-02 review. Mocked in unit tests; production definition finalized before the seeding migration runs. |
| `pdp_views_daily` page-path pattern | Currently assumes accounts have a canonical product-detail URL structure (e.g., `/products/*`). **CONFIRM** during DP-PRD-02 — if per-account, the pattern becomes an optional input field (`page_path_prefix`) defaulting to the account's configured value. |
| BigQuery external-table provisioning for GA jobs | Deferred. The `bigquery_external_table` field stays `None` for all 8 starter jobs. Plan §10 open question flags DP-PRD-06 as the review point. |
| Incremental vs. full-refresh for high-cardinality dimensions (`top_landing_pages`) | v1 pulls the full list. If token cost or storage becomes an issue, a future PRD introduces an `incremental_since` input. Not blocking. |
| Rate-limit tuning per-operation | v1 enforces a single limit per connector. `top_landing_pages` is heavier than `sessions_by_date`; if operation-level tuning is needed, add to DP-PRD-06. |

## 10. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md) §3.3 (execution model, rate limits, error handling), §5 (SAR-E integration), §6.3 (independent failure modes from AH-PRD-03), §7 DP-PRD-02
- Upstream: [DP-PRD-01 — Foundation](./DP-PRD-01-foundation.md)
- Upstream: [`../../integrations/implementation-plan.md`](../../integrations/implementation-plan.md) §3.4, §4 — credential-read internal endpoint
- Upstream (soft): [`../../integrations/implementation-plan.md`](../../integrations/implementation-plan.md) IN-PRD-05 — re-auth lifecycle
- Sibling (downstream): [DP-PRD-03 — Task-system integration](./DP-PRD-03-task-system-integration.md)
- Sibling (downstream): [`../../sar-e/implementation-plan.md`](../../sar-e/implementation-plan.md) SE-PRD-02 — weekly KPI ingestion consumer
- Cross-component (independent failure domain): [`../../agentic-harness/README.md`](../../agentic-harness/README.md) AH-PRD-03 (Google Analytics Specialist)
- GA4 Data API Python client: <https://googleapis.dev/python/analyticsdata/latest/index.html>
- CLAUDE.md rules in scope: **BP-1** (clarify before coding); **C-2** (domain vocabulary), **C-4** (small composable connector methods), **C-7** (no needless comments); **PY-1**, **PY-2**, **PY-3**, **PY-6**, **PY-7**; **D-1**, **D-5**; **T-1**, **T-3**, **T-4**, **T-5**, **T-6**, **T-8** (platform-marked integration tests + unit-test separation); **G-1** (`make lint` gate)
