# DP-PRD-05 — Additional Connectors (Google Ads, Meta Ads, Mailchimp)

**Status:** Blocked — resumes once DP-PRD-02 ships (framework proven on Google Analytics) and IN-PRD-04 delivers Meta + Mailchimp OAuth
**Owner team:** Data Pipeline component team
**Blocked by:** DP-PRD-02 (connector framework proven end-to-end against a real GA4 property; `BaseConnector` abstract + rate-limit middleware + retry / auth-error contract established); IN-PRD-04 (Meta + Mailchimp OAuth flows and `PlatformConnection` entries — Google Ads reuses the same Google OAuth app as DP-PRD-02)
**Blocks:** —
**Estimated effort:** 2–3 days per connector × 3 connectors = ~7–9 days total

---

## 1. Context

DP-PRD-02 proves the connector framework against Google Analytics: a `DataPipelineConnector` Protocol, a `BaseConnector` helper that loads credentials via Integrations' internal endpoint, a per-account rate-limit middleware, a transient-error retry ladder (3 attempts, exponential backoff), and a seeded job catalog. Everything in DP-PRD-05 is a **second-and-third application** of that framework — no new architecture, no new data shapes, no new service endpoints.

Three facts shape this PRD:

1. **Three connectors, one shape.** `GoogleAdsConnector`, `MetaAdsConnector`, and `MailchimpConnector` each implement `DataPipelineConnector.run(operation, inputs, credentials) -> PipelineOutput` per plan §3.1. Each uses its platform's official Python SDK where one exists (Google Ads API Python client, Meta Business SDK, Mailchimp Marketing Python); where SDKs fall short on operations we care about, we fall back to direct HTTPS via `httpx` scoped to a single file per connector.
2. **Rate limits are configured per connector, not per job.** Plan §3.3 fixes the per-account budgets: Google Ads 50/day · 10/hr · 3 concurrent; Meta Ads 50/day · 10/hr · 3 concurrent; Mailchimp 20/day · 5/hr · 2 concurrent. DP-PRD-06 telemetry feeds tuning; this PRD wires the limits into the existing middleware and no more.
3. **Each connector ships with 3–5 seeded jobs.** The starter sets below are suggestions — teams may refine at build time — but the minimum bar is three runnable jobs per connector, each producing a deterministic Parquet artifact under a real account.

Credential loading extends DP-PRD-02's pattern with `auth_type` awareness. Integrations' `GET /api/v1/internal/integrations/credentials/{account_id}/{platform_id}` response carries an `auth_type` field (`oauth` / `api_key` / `basic`). Google Ads, Meta Ads, and (in most deployments) Mailchimp are `oauth`; a platform using an API key would get the `api_key` shape. Each connector reads the field in its constructor and configures its SDK appropriately.

**Explicit non-goal: HubSpot.** HubSpot is deferred until the HubSpot Specialist PRD lands. Not in scope here, not noted in dependencies, not tested. Revisit only after the specialist work begins.

## 2. Scope

### In scope

- **`GoogleAdsConnector`** — `app/data_pipeline/connectors/google_ads.py` — wraps the `google-ads` Python client. Reuses the same Google OAuth credential from IN-PRD-02 that DP-PRD-02 uses for GA; no new OAuth scopes are added beyond what IN-PRD-02 requested (confirm `https://www.googleapis.com/auth/adwords` is in the Google platform definition before kickoff).
- **`MetaAdsConnector`** — `app/data_pipeline/connectors/meta_ads.py` — wraps the `facebook_business` Python SDK. Reads credentials from Integrations' internal endpoint with `platform_id="meta_ads"` (IN-PRD-04).
- **`MailchimpConnector`** — `app/data_pipeline/connectors/mailchimp.py` — wraps the `mailchimp-marketing` Python SDK. Reads credentials from Integrations with `platform_id="mailchimp"` (IN-PRD-04). Respects Mailchimp's data-center prefix in the server URL (Integrations stores it as part of the connection's `external_account_id`).
- **Rate-limit budgets wired into the middleware** per plan §3.3:
  - `google_ads`: 50/day · 10/hr · 3 concurrent
  - `meta_ads`: 50/day · 10/hr · 3 concurrent
  - `mailchimp`: 20/day · 5/hr · 2 concurrent
- **Credential-loader extension.** The shared credential-fetch helper inspects `auth_type` on the Integrations response and shapes the credentials dict appropriately per connector. For Google Ads + Meta Ads (both `oauth`), the shape mirrors DP-PRD-02. For any future `api_key` platforms, the field is `{"api_key": "..."}`; for `basic` the field is `{"username": "...", "password": "..."}`. All three connectors delivered here are `oauth`, but the helper is agnostic.
- **Seeded job catalog entries** — 3–5 jobs per connector, all flagged `visible_in_frontend=true` unless noted:

  | Connector | Suggested starter jobs |
  |---|---|
  | Google Ads | `gads.campaign_performance_daily`, `gads.keyword_performance`, `gads.ad_group_spend` |
  | Meta Ads | `meta.ad_performance_daily`, `meta.campaign_spend`, `meta.audience_insights` |
  | Mailchimp | `mailchimp.campaign_send_summary`, `mailchimp.subscriber_counts`, `mailchimp.open_click_rates` |

  Teams may add a 4th or 5th job per connector at build time if doing so doesn't slip the effort estimate; minimum bar is three per connector. Seeded via DM-PRD-00 migration on the global `data_pipeline_jobs/*` collection.

- **Unit tests per connector** (mocked SDK / stub credential service).
- **Integration tests per connector** against live platform APIs under `@pytest.mark.platform`, gated by env-var credentials (the same pattern DP-PRD-02 established). Each integration test runs each seeded job with canonical inputs and asserts a non-empty Parquet artifact + a deterministic schema.
- **Migration** adding the nine+ seeded jobs to `data_pipeline_jobs/*` with `version=1`.

### Out of scope

- **HubSpot connector.** Deferred until the HubSpot Specialist PRD lands. Not tracked here beyond this mention.
- **New `PlatformDefinition`s.** IN-PRD-04 owns the `meta` + `mailchimp` platform definitions and OAuth flows. This PRD consumes them.
- **Bumping rate-limit budgets past plan §3.3.** This PRD wires the numbers as specified; tuning happens in DP-PRD-06 based on live telemetry.
- **New service endpoints.** Plan §4 enumerates the full API surface; connectors are internal consumers of `POST /api/v1/internal/data-pipeline/run` — no routes added here.
- **Cross-platform joins inside one job.** Plan §9 non-goal — "Cross-platform joins inside one job." Assembly across connectors stays in downstream agent tasks.
- **Connector-specific frontend surfaces.** All frontend flows from DP-PRD-04 are connector-agnostic (the picker filters by `connector` metadata; the input form is schema-driven). No frontend changes here.
- **Custom retry policies per operation.** The DP-PRD-02 retry ladder applies uniformly: 3 attempts with exponential backoff on transient (5xx / 429 / network) errors; immediate fail on semantic 4xx; re-auth trigger on 401 / 403 per plan §3.3.
- **Real-time streaming extracts.** Plan §9 non-goal — batch only.

## 3. Dependencies

- **DP-PRD-02 (Google Analytics connector):** framework proven. `BaseConnector`, rate-limit middleware, retry ladder, credential-fetch helper, `PipelineOutput` shape, artifact-write pipeline, error-notification flow, `@pytest.mark.platform` integration-test harness all consumed as-is.
- **DP-PRD-01 (Foundation):** `DataPipelineConnector` Protocol, service endpoint, cache-lookup flow, `DataPipelineRun` persistence — all upstream.
- **IN-PRD-04 (Meta + Mailchimp platforms):** adds `meta_ads` and `mailchimp` entries to `platform_definitions/*` + wires their OAuth callbacks. This PRD's Meta + Mailchimp connectors cannot proceed before those connections are authable from the UI.
- **IN-PRD-02 (Google OAuth):** Google Ads connector reuses the same Google OAuth app DP-PRD-02 established. Incremental scope request (`adwords`) must be confirmed against the existing `google` `PlatformDefinition.scopes` list.
- **DM-PRD-00 (Migration foundation):** the seeded-catalog migration follows the standard Shape B pattern used by DP-PRD-02.
- **Existing files to study:**
  - `/Volumes/WorkDrive/Active Work/Github/KEN-E/docs/design/components/data-pipeline/implementation-plan.md` §3, §4 — shapes + endpoints
  - `/Volumes/WorkDrive/Active Work/Github/KEN-E/docs/design/components/data-pipeline/projects/DP-PRD-02-google-analytics-connector.md` — connector pattern template (the file this PRD extends)
  - `/Volumes/WorkDrive/Active Work/Github/KEN-E/docs/design/components/integrations/implementation-plan.md` §6 IN-PRD-04 — Meta + Mailchimp platform-definition contracts
  - `app/data_pipeline/connectors/google_analytics.py` (from DP-PRD-02) — the exemplar
  - `app/data_pipeline/connectors/base.py` (from DP-PRD-02) — the shared base class + rate-limit middleware

## 4. Data contract

No new Pydantic shapes. No new frontend types. No new Firestore collections beyond the migrations below.

### 4.1 Seeded `DataPipelineJob` migrations

Each job is a `DataPipelineJob` document per plan §3.1 with `scope="global"` and `version=1`. Seeded via DM-PRD-00 migration on `data_pipeline_jobs/*`. Shape is identical for every connector; the distinguishing fields are `connector`, `operation`, `input_schema`, `output_schema`. Starter examples below — concrete JSON Schemas drafted at build time and reviewed with the connector lead.

**Google Ads — `gads.campaign_performance_daily`** — sketch:

```python
DataPipelineJob(
    job_id="gads.campaign_performance_daily",
    connector="google_ads",
    operation="campaign_performance_daily",
    display_name="Google Ads — Campaign performance (daily)",
    description="Per-campaign impressions, clicks, cost, conversions for a date range.",
    input_schema={
        "type": "object",
        "properties": {
            "customer_id": {"type": "string"},
            "start_date": {"type": "string", "format": "date"},
            "end_date": {"type": "string", "format": "date"},
        },
        "required": ["customer_id", "start_date", "end_date"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "date": {"type": "string", "format": "date"},
            "campaign_id": {"type": "string"},
            "campaign_name": {"type": "string"},
            "impressions": {"type": "integer"},
            "clicks": {"type": "integer"},
            "cost_micros": {"type": "integer"},
            "conversions": {"type": "number"},
        },
    },
    output_format="parquet",
    default_cache_ttl_seconds=3600,
    test_mode_policy="run_normally",
    visible_in_frontend=True,
    version=1,
)
```

The remaining seeded jobs per connector follow the same shape; concrete schemas live in each connector's migration file.

### 4.2 Rate-limit configuration

Rate-limit middleware (from DP-PRD-02) reads configuration from a single constant per connector. This PRD adds three entries:

```python
# app/data_pipeline/rate_limits.py (extended)
PER_CONNECTOR_LIMITS = {
    "google_analytics": RateLimitBudget(day=100, hour=20, concurrent=5),
    "google_ads":       RateLimitBudget(day=50, hour=10, concurrent=3),  # NEW
    "meta_ads":         RateLimitBudget(day=50, hour=10, concurrent=3),  # NEW
    "mailchimp":        RateLimitBudget(day=20, hour=5,  concurrent=2),  # NEW
}
```

Breach returns 429 with a `Retry-After` header computed from the tightest violated window. After 3 breaches in a 24-hour window the existing account-level notification from DP-PRD-02 fires.

### 4.3 Credential-fetch helper — `auth_type` awareness

DP-PRD-02 introduced a `load_credentials(account_id, platform_id) -> dict` helper. This PRD extends it to read the `auth_type` field returned by `GET /api/v1/internal/integrations/credentials/{account_id}/{platform_id}` and shape the output:

```python
# app/data_pipeline/credentials.py (extended)
async def load_credentials(account_id: str, platform_id: str) -> dict:
    resp = await integrations_client.get_credentials(account_id, platform_id)
    match resp.auth_type:
        case "oauth":
            return {
                "auth_type": "oauth",
                "access_token": resp.access_token,
                "expires_at": resp.expires_at,
                "external_account_id": resp.external_account_id,
            }
        case "api_key":
            return {"auth_type": "api_key", "api_key": resp.api_key}
        case "basic":
            return {"auth_type": "basic", "username": resp.username, "password": resp.password}
        case _:
            raise ValueError(f"Unsupported auth_type: {resp.auth_type!r}")
```

All three connectors delivered here are `oauth`. The helper is written agnostic so future connectors can plug in without touching this code.

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `app/data_pipeline/connectors/google_ads.py` — `GoogleAdsConnector(BaseConnector)`; one `_op_*` method per seeded operation |
| Create | `app/data_pipeline/connectors/meta_ads.py` — `MetaAdsConnector(BaseConnector)` |
| Create | `app/data_pipeline/connectors/mailchimp.py` — `MailchimpConnector(BaseConnector)` |
| Modify | `app/data_pipeline/connectors/registry.py` — register the three new connectors against `DataPipelineConnector` Protocol |
| Modify | `app/data_pipeline/rate_limits.py` — add Google Ads + Meta Ads + Mailchimp budgets per §4.2 |
| Modify | `app/data_pipeline/credentials.py` — extend `load_credentials` to branch on `auth_type` per §4.3 |
| Create | `app/data_pipeline/migrations/seed_google_ads_jobs.py` — migration adding the 3 (or more) Google Ads seeded jobs to `data_pipeline_jobs/*` |
| Create | `app/data_pipeline/migrations/seed_meta_ads_jobs.py` — migration adding the 3 (or more) Meta Ads seeded jobs |
| Create | `app/data_pipeline/migrations/seed_mailchimp_jobs.py` — migration adding the 3 (or more) Mailchimp seeded jobs |
| Create | `api/tests/unit/test_google_ads_connector.py` — mocked SDK; one test per operation covering happy path + transient retry + auth error + rate-limit breach |
| Create | `api/tests/unit/test_meta_ads_connector.py` — same coverage pattern |
| Create | `api/tests/unit/test_mailchimp_connector.py` — same coverage pattern |
| Create | `api/tests/unit/test_credential_loader_auth_type.py` — covers the `auth_type` branch logic added in §4.3 |
| Create | `api/tests/integration/test_google_ads_connector_live.py` — `@pytest.mark.platform`; runs each Google Ads seeded job against a sandbox GA account |
| Create | `api/tests/integration/test_meta_ads_connector_live.py` — `@pytest.mark.platform` |
| Create | `api/tests/integration/test_mailchimp_connector_live.py` — `@pytest.mark.platform` |
| Create | `api/tests/integration/test_rate_limit_budgets.py` — per-connector budgets enforced; 429 with `Retry-After` on breach; 3-breach notification fires |

### 5.1 Google Ads connector

- SDK: `google-ads` (official). Constructor wires the SDK's `GoogleAdsClient` with the OAuth access token loaded from Integrations + a developer token stored in Secret Manager (`sm://google-ads-developer-token`).
- Operations: one `_op_campaign_performance_daily`, `_op_keyword_performance`, `_op_ad_group_spend` method each. Each issues a single GAQL query against the SDK's `GoogleAdsService.search_stream`, maps rows to the `output_schema` shape, returns a `PipelineOutput(rows=..., schema=..., metadata={row_count, query, source_api_version})`.
- Rate-limit: decorated with the shared middleware at `@rate_limited("google_ads")`.
- Retry: reuses the DP-PRD-02 retry ladder — transient `google.ads.googleads.errors.GoogleAdsException` with a `QuotaError` subcode retries up to 3×; auth errors trigger IN-PRD-05's re-auth flow.

### 5.2 Meta Ads connector

- SDK: `facebook_business`. Constructor calls `FacebookAdsApi.init(access_token=...)` with the OAuth access token loaded from Integrations.
- Operations: `_op_ad_performance_daily` (uses `AdAccount(...).get_insights(...)` with `time_range` + `breakdowns=['publisher_platform']`), `_op_campaign_spend` (`Campaign.get_insights(...)`), `_op_audience_insights` (`CustomAudience.get_insights(...)`).
- Rate-limit: `@rate_limited("meta_ads")`.
- Retry: Meta's transient errors surface as `FacebookRequestError` with `api_error_code` in `(1, 2, 4, 17, 341)` (their standard retry codes); the connector's `_should_retry` helper matches those codes; all others fail fast.

### 5.3 Mailchimp connector

- SDK: `mailchimp-marketing`. Constructor calls `client.set_config({"api_key": ..., "server": server_prefix})` where `server_prefix` comes from the connection's `external_account_id` (Mailchimp's data-center prefix). The OAuth access-token-for-API-key exchange pattern is owned by IN-PRD-04.
- Operations: `_op_campaign_send_summary` (`client.reports.get_campaign_report(campaign_id)`), `_op_subscriber_counts` (`client.lists.get_list_members_info`), `_op_open_click_rates` (`client.reports.get_email_activity_for_campaign`).
- Rate-limit: `@rate_limited("mailchimp")`. Mailchimp's published limit is 10 concurrent per API key; this PRD sets our per-account budget at 2 concurrent (plan §3.3) to leave headroom for human users of the same credential.
- Retry: Mailchimp returns 429 with a `Retry-After` header; the connector respects that header directly inside the retry ladder (overrides the default exponential-backoff delay).

### 5.4 Seeded-catalog migration

Per-connector migration file. Each one:

1. Reads the connector's starter job list from a Python dict inside the migration.
2. For each job, writes to `data_pipeline_jobs/{job_id}` with `scope="global"` + `version=1`.
3. Idempotent: if a job already exists with the same `job_id` + `version`, skip. If `job_id` exists at a lower version, the migration logs a warning and skips — version bumps go through a separate versioning migration (future DP-PRD-06 polish).

## 6. API contract

No new endpoints. All three connectors are invoked by `POST /api/v1/internal/data-pipeline/run` (owned by DP-PRD-01, plan §4).

Endpoints consumed:

| Method | Path | Purpose | Owner |
|---|---|---|---|
| `POST` | `/api/v1/internal/data-pipeline/run` | Orchestrator-to-service dispatch; routes to the connector via the registry | DP-PRD-01 |
| `GET` | `/api/v1/internal/integrations/credentials/{account_id}/{platform_id}` | OIDC; returns `{access_token, expires_at, external_account_id, auth_type}` | IN-PRD-02 / IN-PRD-04 |
| `POST` | `/api/v1/internal/integrations/connections/{connection_id}/mark-expired` | Called on 401 / 403 from the platform to trigger re-auth | IN-PRD-05 |

## 7. Acceptance criteria

1. `GoogleAdsConnector` implements the `DataPipelineConnector` Protocol; `registry.resolve("google_ads")` returns an instance.
2. `MetaAdsConnector` implements the `DataPipelineConnector` Protocol; `registry.resolve("meta_ads")` returns an instance.
3. `MailchimpConnector` implements the `DataPipelineConnector` Protocol; `registry.resolve("mailchimp")` returns an instance.
4. Seeded Google Ads jobs (minimum `gads.campaign_performance_daily`, `gads.keyword_performance`, `gads.ad_group_spend`) exist in `data_pipeline_jobs/*` with `scope="global"`, `version=1`, `visible_in_frontend=true`, and valid `input_schema` / `output_schema` documents.
5. Seeded Meta Ads jobs (minimum `meta.ad_performance_daily`, `meta.campaign_spend`, `meta.audience_insights`) exist with the same attributes.
6. Seeded Mailchimp jobs (minimum `mailchimp.campaign_send_summary`, `mailchimp.subscriber_counts`, `mailchimp.open_click_rates`) exist with the same attributes.
7. Each seeded job runs end-to-end via `POST /api/v1/internal/data-pipeline/run` against a live account (covered in integration tests gated by `@pytest.mark.platform`) and produces a Parquet artifact matching its declared `output_schema`.
8. Rate-limit middleware enforces 50/day · 10/hr · 3 concurrent for `google_ads`; identical for `meta_ads`; 20/day · 5/hr · 2 concurrent for `mailchimp`. Breaches return HTTP 429 with a `Retry-After` header from the tightest violated window.
9. Three consecutive rate-limit breaches within a 24-hour window fire the existing DP-PRD-02 account-level notification.
10. Transient-error retry: 5xx / platform-specific quota / network errors retry up to 3 times with exponential backoff; the 4th failure surfaces as a task failure + notification per plan §3.3.
11. Auth-error handling: platform 401 / 403 responses trigger `POST /internal/integrations/connections/{id}/mark-expired` and fail the task; downstream tasks halt until reconnection.
12. Credential loader: `load_credentials(account_id, platform_id)` returns the `oauth` shape for `google_ads` / `meta_ads` / `mailchimp` and raises a `ValueError` for an unsupported `auth_type`.
13. Cross-account isolation: a connector run for account A never reads account B's credentials; a run against account B's connection cannot use account A's rate-limit quota.
14. Observability: every run emits a `data_pipeline.run` Weave span with `{connector, operation, input_hash, row_count, cache_hit, test_mode}` (inherited from DP-PRD-02).
15. HubSpot is **not** present in the connector registry, the rate-limit config, or the seeded-jobs catalog. Explicit non-goal per plan §7 DP-PRD-05.
16. `make lint`, `pytest api/tests/data_pipeline/` (unit suite), and the `@pytest.mark.platform`-gated integration suite all green.
17. Migrations are idempotent: running `seed_{connector}_jobs.py` twice leaves the catalog in an identical state.
18. Unit tests: one happy-path + one transient-retry + one auth-error + one rate-limit test per operation per connector.

## 8. Test plan

**Unit tests — connectors (mocked SDK + stub credential service):**
- `test_google_ads_connector.py` — one test per `_op_*` covering: happy path → asserts row count, schema shape, artifact-ready output; transient retry → 2 failures then a success, asserts 3 total SDK calls; auth error → 401 surfaces as an expected exception type; rate-limit passthrough → platform 429 respected via `Retry-After`.
- `test_meta_ads_connector.py` — same coverage pattern, tailored to `FacebookRequestError` codes.
- `test_mailchimp_connector.py` — same coverage pattern, tailored to Mailchimp's server-prefix handling + 429 `Retry-After`.

**Unit tests — credential loader:**
- `test_credential_loader_auth_type.py` — covers each `auth_type` branch: `oauth` shape, `api_key` shape, `basic` shape, and an unsupported value raising `ValueError`.

**Unit tests — rate-limit middleware:**
- `test_rate_limit_budgets.py` (extends DP-PRD-02's suite) — asserts the three new budgets are loaded correctly; breach returns 429 with the right `Retry-After`; 3-breach notification fires; breaches on one connector don't decrement another's window.

**Integration tests (`@pytest.mark.platform`):**
- `test_google_ads_connector_live.py` — runs each seeded job against a sandbox Google Ads account; asserts non-empty artifact + schema match. Gated on `GOOGLE_ADS_TEST_ACCOUNT_ID` + dev-token env-vars.
- `test_meta_ads_connector_live.py` — runs each seeded job against a sandbox Meta ad account. Gated on `META_ADS_TEST_ACCOUNT_ID` env-var.
- `test_mailchimp_connector_live.py` — runs each seeded job against a sandbox Mailchimp list. Gated on `MAILCHIMP_TEST_LIST_ID` env-var.
- Each live test, when run: (a) asserts rate-limit middleware permits the call; (b) asserts the resulting `DataPipelineRun` has `status="succeeded"`; (c) asserts the artifact is loadable as Parquet and matches the declared `output_schema`.

**Migration tests:**
- `test_seed_google_ads_jobs_migration.py` — asserts the migration writes the expected set of jobs; running twice is a no-op; seeded jobs pass a JSON-Schema meta-validation pass.
- `test_seed_meta_ads_jobs_migration.py` — same pattern.
- `test_seed_mailchimp_jobs_migration.py` — same pattern.

## 9. Risks & open questions

### Resolved decisions

| Decision | Resolution |
|---|---|
| HubSpot scope | Deferred. Not part of this PRD. Revisit alongside the HubSpot Specialist PRD. |
| SDK choice per connector | Official Python SDK where available; direct `httpx` fallback in single-file scope if an SDK gap blocks a seeded job. |
| Rate-limit budgets | Plan §3.3 numbers wired as-is. Tuning deferred to DP-PRD-06 telemetry. |
| Credential loader `auth_type` branching | Extended in a single helper (`load_credentials`) for all future connectors. All three delivered here are `oauth`. |
| Starter job counts | Minimum 3 per connector, max 5 per connector at team discretion. |
| Mailchimp server-prefix handling | Sourced from the `PlatformConnection.external_account_id` set during OAuth (IN-PRD-04 owns the source field). |
| Retry policy | Reuse DP-PRD-02 retry ladder uniformly; platform-specific error-code mapping lives inside each connector's `_should_retry`. |

### Remaining open questions

| Question | Disposition |
|---|---|
| Google Ads developer-token storage path | `sm://google-ads-developer-token` per env. Confirm against `api/src/kene_api/services/secrets.py` conventions at kickoff. |
| Mailchimp OAuth vs. API-key nuance | Most Mailchimp users in the wild use OAuth; some legacy-setup enterprise users use API keys. IN-PRD-04 owns the OAuth flow; API-key mode deferred until a customer asks. Confirm at kickoff. |
| Meta long-lived token refresh inside the pipeline | IN-PRD-04 owns the short → long-lived token exchange. The connector treats all access tokens as opaque. Double-check at kickoff that long-lived tokens are what Integrations returns on `GET /api/v1/internal/integrations/credentials/.../meta_ads`. |
| BigQuery external-table generation per seeded job | Plan §3 allows an optional `bigquery_external_table` on each job. V1 seeded jobs leave this `null`; a later polish PRD can opt high-volume jobs in once we see SAR-E-style consumption patterns. |
| `test_mode_policy` per job | All seeded jobs ship with `run_normally`. A future write-capable job (e.g., `gads.create_campaign` — not in v1) would opt into `sandbox_endpoint`. |
| Concurrent-test flakiness on shared sandbox accounts | Integration tests run serialized by default; `@pytest.mark.platform` scheduling is single-slot to avoid stepping on each other's rate-limit budgets. If this slows CI significantly, revisit. |
| Starter job refinement at build time | Teams may trim or add at build time provided the minimum-3 bar is preserved. If a connector only ships two runnable jobs, escalate before merge. |

## 10. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md) §7 DP-PRD-05
- Upstream: [DP-PRD-01 Foundation](./DP-PRD-01-foundation.md), [DP-PRD-02 Google Analytics connector](./DP-PRD-02-google-analytics-connector.md) — framework template
- Upstream: [IN-PRD-02 Google OAuth](../../integrations/projects/IN-PRD-02-google-oauth.md), [IN-PRD-04 Meta + Mailchimp platforms](../../integrations/projects/IN-PRD-04-meta-mailchimp-platforms.md)
- Sibling: [DP-PRD-03 Task-system integration](./DP-PRD-03-task-system-integration.md) — dispatcher branch + artifact write
- Sibling: [DP-PRD-06 Integration testing + polish](./DP-PRD-06-integration-testing.md) — rate-limit ceiling tests + connector-level perf data
- Related (deferred): HubSpot Specialist PRD — HubSpot connector follows that work
- Code files expected to be touched:
  - `app/data_pipeline/connectors/google_ads.py`
  - `app/data_pipeline/connectors/meta_ads.py`
  - `app/data_pipeline/connectors/mailchimp.py`
  - `app/data_pipeline/connectors/registry.py`
  - `app/data_pipeline/rate_limits.py`
  - `app/data_pipeline/credentials.py`
  - `app/data_pipeline/migrations/seed_google_ads_jobs.py`
  - `app/data_pipeline/migrations/seed_meta_ads_jobs.py`
  - `app/data_pipeline/migrations/seed_mailchimp_jobs.py`
  - `api/tests/unit/test_google_ads_connector.py`
  - `api/tests/unit/test_meta_ads_connector.py`
  - `api/tests/unit/test_mailchimp_connector.py`
  - `api/tests/unit/test_credential_loader_auth_type.py`
  - `api/tests/integration/test_google_ads_connector_live.py`
  - `api/tests/integration/test_meta_ads_connector_live.py`
  - `api/tests/integration/test_mailchimp_connector_live.py`
  - `api/tests/integration/test_rate_limit_budgets.py`
- CLAUDE.md rules in scope: C-1 (TDD), C-2 (domain vocabulary — `DataPipelineConnector`, `PipelineOutput`, seeded-job `job_id` slugs), C-3 (no classes when small functions suffice — each connector is one class because the SDK object is mutable and constructor-wired), C-4 (simple composable functions inside each connector); PY-1 (type hints), PY-2 (Pydantic), PY-3 (async I/O — connectors are async), PY-5 (context managers for SDK clients), PY-7 (no bare except — every `except` clauses the specific error type); D-1 (Firestore session management), D-2 (Pydantic models for entities — `DataPipelineJob`, `DataPipelineRun`, `PipelineOutput` inherited), D-5 (no hardcoded credentials — all via Secret Manager + Integrations); T-1 (colocated pytest), T-3 (API integration tests), T-4 (pure-logic unit vs platform-live integration split), T-5 (prefer integration over heavy mocking — the `@pytest.mark.platform` suite is the authoritative coverage), T-6 (unit-test retry ladders + rate-limit state machines), T-7 (pytest fixtures); G-1 (`make lint`); GH-1 (Conventional Commits).
