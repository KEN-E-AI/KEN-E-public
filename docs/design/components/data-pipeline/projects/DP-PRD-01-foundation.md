# DP-PRD-01 — Foundation

**Status:** Draft — ready to start once DM-PRD-00 ships
**Owner team:** Backend (Data Pipeline)
**Blocked by:** DM-PRD-00 (Migration Foundation — provisions the Shape B migration framework + composite-index registry every new collection in this PRD relies on)
**Blocks:** DP-PRD-02, DP-PRD-03
**Estimated effort:** 3–4 days

---

## 1. Context

The Data Pipeline is KEN-E's deterministic, non-agentic path to third-party platform APIs. It exists because agent-routed extraction — Root Agent → specialist → MCP tool call → code execution — is the right shape for *reasoning-heavy* requests ("what caused the drop?") but the wrong shape for *repeatable, well-defined* extractions ("pull transactions by date, daily, at 07:00 UTC"). For the second class, the Data Pipeline calls the platform API directly with a known recipe, produces a structured artifact, and hands off to downstream tasks.

This PRD delivers the foundation every other PRD in the component consumes: the Pydantic shapes (`DataPipelineJob`, `DataPipelineRun`, `PipelineJobSpec`, `PipelineOutput`, `DataPipelineConnector` protocol); the sibling Cloud Run service scaffold at `kene-data-pipeline-{env}`; the OIDC-authed internal execution endpoint `POST /api/v1/internal/data-pipeline/run`; the per-account cache-lookup logic keyed on `sha256(account_id || job_id || canonical_json(inputs) || job.version)`; the `DataPipelineRun` persistence layer (including `status=cached` audit rows); a `StubConnector` that lets downstream PRDs exercise the contract before any live connector exists; and the three new Firestore collections (`data_pipeline_jobs/*` global, `accounts/{account_id}/data_pipeline_jobs/*` per-account overlay, `accounts/{account_id}/data_pipeline_runs/*` execution history) provisioned through the DM-PRD-00 migration framework.

What this PRD is **not:** any live connector implementation (Google Analytics is DP-PRD-02; Meta, Google Ads, Mailchimp are DP-PRD-05); the `TaskOrchestrator` dispatch branch that routes a `PlanTask` to a pipeline run (DP-PRD-03); any frontend work (DP-PRD-04). The exit criterion is narrow — a `StubConnector` job executes end-to-end through the service, writes a `DataPipelineRun`, and returns a `PipelineOutput`.

## 2. Scope

### In scope

- `DataPipelineJob`, `DataPipelineRun`, `PipelineJobSpec`, `PipelineOutput`, `FieldSpec`, `BqTableRef` Pydantic models per plan §3.1, living in a new module under the sibling service
- `DataPipelineConnector` runtime `Protocol` with a single `async run(operation, inputs, credentials) -> PipelineOutput` method
- `StubConnector` — in-memory fake implementing the protocol; returns a deterministic `PipelineOutput` shaped by the inputs; used by contract tests and by DP-PRD-03 before DP-PRD-02 lands
- Sibling Cloud Run service `kene-data-pipeline-{env}` scaffold: Dockerfile, `uvicorn` entrypoint, health endpoint, OIDC auth dependency, Firestore + GCS client bootstrap, Weave tracing initialization
- `DataPipelineService` class: resolves `DataPipelineJob` from catalog (global → per-account overlay precedence), validates `inputs` against the job's `input_schema`, computes the cache key, dispatches to the connector, persists a `DataPipelineRun`
- `POST /api/v1/internal/data-pipeline/run` OIDC-authed endpoint (same pattern as PR-PRD-06 / A-PRD-02) callable by the orchestrator; 10-minute cap per run; fire-and-forget semantics with a PATCH back to the plan on completion
- Catalog read endpoints on the main API (colocated with the existing FastAPI app): `GET /api/v1/data-pipeline/jobs` (list global + per-account overlay, filter by `connector`), `GET /api/v1/data-pipeline/jobs/{job_id}` (fetch one)
- Catalog write endpoint `POST /api/v1/data-pipeline/jobs` — create a per-account custom job; validates against the `DataPipelineJob` schema + a JSON-Schema meta-validator on declared `input_schema` / `output_schema`; requires `editor` role or higher per DM-PRD-07
- Run read endpoints on the main API: `GET /api/v1/data-pipeline/{account_id}/runs` (list with filters: `plan_id`, `task_id`, `job_id`, `status`, `from`, `to`), `GET /api/v1/data-pipeline/{account_id}/runs/{run_id}` (detail + artifact link)
- Per-account cache lookup keyed on `sha256(account_id || job_id || canonical_json(inputs) || job.version)`; cache hits still write a `DataPipelineRun` with `status="cached"` for audit completeness
- Firestore collections: `data_pipeline_jobs/{job_id}` (global catalog — Shape B carve-out mirroring `agent_configs/*`), `accounts/{account_id}/data_pipeline_jobs/{job_id}` (per-account overlay), `accounts/{account_id}/data_pipeline_runs/{run_id}` (execution history). Migration authored against DM-PRD-00's framework; composite indexes registered per `(account_id, plan_id, started_at)` and `(account_id, job_id, started_at)`
- Weave span `data_pipeline.run` emission scaffold with `{connector, operation, input_hash, row_count, cache_hit, test_mode}` attributes (DP-PRD-02 fills in per-connector values; this PRD emits the span and verifies shape via `StubConnector`)
- Contract tests exercising the `StubConnector` path end-to-end against the internal endpoint
- `make lint` + `pytest` clean on every PR

### Out of scope

- **`GoogleAnalyticsConnector` + the 8-job starter catalog.** Owned by DP-PRD-02.
- **Google Ads / Meta Ads / Mailchimp connectors.** Owned by DP-PRD-05.
- **`TaskOrchestrator.on_task_due` / `on_task_status_change` `data_pipeline` branch.** Owned by DP-PRD-03, which also extends `PlanTask.assignee_type`.
- **Frontend consumption — `ProjectEditDrawer` assignee selector, `PipelineJobPicker`, schema-driven input forms, run-viewer, custom-job authoring UI.** Owned by DP-PRD-04.
- **BigQuery external-table materialization.** The `bigquery_external_table` field is defined on `DataPipelineJob` here but not acted on until DP-PRD-02's per-job opt-in. The v1 model is the `None`-default case.
- **Credential loading from Integrations.** This PRD's `StubConnector` accepts a stubbed credentials dict; the real `/api/v1/internal/integrations/credentials/{account_id}/{platform_id}` call lands in DP-PRD-02.
- **Rate-limit enforcement.** v1 starting points are specified in plan §3.3 but enforcement is per-connector and ships with DP-PRD-02.

## 3. Dependencies

- **DM-PRD-00 (Migration Foundation):** hard prerequisite. Publishes the migration framework + composite-index registry this PRD uses to provision `data_pipeline_jobs/*`, `accounts/*/data_pipeline_jobs/*`, and `accounts/*/data_pipeline_runs/*`. Without it there is no standard path to add new collection-group queries.
- **DM-PRD-07 (Approval Workflow & Audit):** soft dependency. The `POST /api/v1/data-pipeline/jobs` endpoint calls `require_role("editor")` and writes audit entries through the `write_audit` helper published by DM-PRD-07. If DM-PRD-07 has not merged when this PRD starts, the endpoint can ship behind a feature flag with a stub role check; once DM-PRD-07 lands the gate is swapped in. The run write endpoints do not require this dependency.
- **Integrations (IN-PRD-02):** soft dependency for this PRD specifically — `StubConnector` bypasses Integrations. The credential-read internal endpoint at `GET /api/v1/internal/integrations/credentials/{account_id}/{platform_id}` is called from DP-PRD-02's `GoogleAnalyticsConnector`, not here. DP-PRD-01 leaves a `credentials: dict` parameter on the connector protocol that DP-PRD-02 fills in.
- **Project Tasks (PR-PRD-01):** soft dependency. `DataPipelineRun` carries `plan_id` and `task_id` so runs can be attributed to a task; the schema does not require PR-PRD-01 to ship first, but the full end-to-end hand-off requires DP-PRD-03 which depends on PR-PRD-04.
- **Automations (A-PRD-02, A-PRD-03):** soft dependency. `PipelineJobSpec.output_artifact_name` is the name under which a downstream `TaskArtifact` will be written in DP-PRD-03 via A-PRD-03's write path. This PRD exposes the field but does not call A-PRD-03.
- **Existing files to study:**
  - `api/src/kene_api/routers/strategy.py` — account-scoped CRUD pattern this PRD's catalog + runs routers mirror (versioning, soft-delete, access-control dependency)
  - `api/src/kene_api/routers/project_plans.py` (PR-PRD-01) — router registration + audit + `PATCH` semantics reference
  - `api/src/kene_api/models/strategy_models.py` — Pydantic + validator conventions for account-scoped models
  - `api/src/kene_api/routers/internal/scheduler.py` (when PR-PRD-06 ships) — OIDC-authed internal endpoint pattern, identical shape to the `/internal/data-pipeline/run` published here
  - `api/src/kene_api/services/firestore_service.py` — Firestore client + transaction helpers
  - `api/src/kene_api/main.py` — FastAPI app + router registration
  - `app/utils/gcs.py` — GCS helpers; `PipelineOutput` serialization will go through a sibling writer in DP-PRD-03 via A-PRD-03
  - `app/adk/tracking/` — Weave span helpers; `data_pipeline.run` span is emitted through the same pattern
  - `deployment/terraform/` — Cloud Run service provisioning module this PRD extends for `kene-data-pipeline-{env}`
  - [`../implementation-plan.md`](../implementation-plan.md) §3.1, §3.2, §3.3, §4 — canonical data model + API surface this PRD realizes
  - [`../../sar-e/implementation-plan.md`](../../sar-e/implementation-plan.md) §3.1–§3.2, §5.1 — SAR-E is the first production consumer via DP-PRD-02; this PRD's `DataPipelineJob.default_cache_ttl_seconds` is set to `0` on SAR-E's 4 daily jobs
  - [`../../integrations/implementation-plan.md`](../../integrations/implementation-plan.md) §3.1, §4 — `PlatformConnection` + `/api/v1/internal/integrations/credentials/{account_id}/{platform_id}` contract consumed by DP-PRD-02
  - [`../../project-tasks/README.md`](../../project-tasks/README.md) §2.3 — `ProjectPlan` / `PlanTask` API surface the run endpoint reports to

## 4. Data contract

### 4.1 `DataPipelineJob`

```python
class BqTableRef(BaseModel):
    project: str                           # GCP project id
    dataset: str
    table: str                             # versioned per plan §10 open Q — new version → new suffix

class FieldSpec(BaseModel):
    name: str
    type: Literal["string", "integer", "float", "boolean", "date", "datetime"]
    nullable: bool = False

class DataPipelineJob(BaseModel):
    job_id: str
    connector: Literal["google_analytics", "google_ads", "meta_ads", "mailchimp"]
    operation: str                         # e.g., "transactions_by_date"
    display_name: str
    description: str
    input_schema: dict                     # JSON Schema; validated by jsonschema.Draft202012Validator on write
    output_schema: dict                    # JSON Schema
    output_format: Literal["parquet", "json", "csv"] = "parquet"
    bigquery_external_table: BqTableRef | None = None
    default_cache_ttl_seconds: int | None = None
    test_mode_policy: Literal["run_normally", "sandbox_endpoint", "fail_not_testable"] = "run_normally"
    visible_in_frontend: bool = True
    version: int = 1
    created_at: datetime
    updated_at: datetime
    is_system: bool = False                # matches PR-PRD-01 `is_system` semantics
```

**Validators:**

- `job_id` matches `^[a-z0-9_]+\.[a-z0-9_]+$` (namespace.operation — e.g., `ga.transactions_by_date`)
- `input_schema` and `output_schema` are JSON-Schema-compatible (meta-validated on write via `jsonschema.validators.Draft202012Validator.check_schema`)
- `version >= 1` and monotonically increases on `PUT` (old versions are not retained in v1; cache invalidation is handled by the version bump being part of the cache key)

### 4.2 `DataPipelineRun`

```python
class DataPipelineRun(BaseModel):
    run_id: str                            # UUID
    account_id: str
    plan_id: str | None                    # nullable only for ad-hoc invocations; always set from orchestrator
    task_id: str | None                    # same
    job_id: str
    inputs: dict                           # validated against DataPipelineJob.input_schema
    input_hash: str                        # sha256 of (account_id || job_id || canonical_json(inputs) || job.version)
    output_artifact_id: str | None         # FK to the TaskArtifact written by A-PRD-03 in DP-PRD-03
    status: Literal["running", "succeeded", "failed", "cached"]
    cache_hit: bool
    is_test: bool = False                  # honored in DP-PRD-03 per DataPipelineJob.test_mode_policy
    started_at: datetime
    finished_at: datetime | None = None
    error_message: str | None = None
    tokens_charged: int = 0                # always 0; parity with agent runs
```

**Validators:**

- `status` transitions allowed: `running → succeeded | failed`; `cached` is a terminal write on cache hit (no prior `running` state)
- `cache_hit=True` ↔ `status="cached"`
- `finished_at` must be >= `started_at` when set

### 4.3 `PipelineJobSpec`

```python
class PipelineJobSpec(BaseModel):
    job_id: str                            # FK to a DataPipelineJob in the global catalog or the per-account overlay
    inputs: dict                           # validated against that job's input_schema at dispatch time
    output_artifact_name: str              # the TaskArtifact filename written by DP-PRD-03
```

Consumed by `PlanTask.pipeline_spec` (DP-PRD-03). `output_artifact_name` is mandatory so downstream tasks can reference the upstream artifact by name in A-PRD-03's prompt injection.

### 4.4 `PipelineOutput`

```python
class PipelineOutput(BaseModel):
    rows: list[dict]
    schema: list[FieldSpec]
    metadata: dict                         # {row_count, query_params, source_api_version, ...}
```

Returned by every connector. Serialization to Parquet / JSON / CSV + write to GCS happens in `DataPipelineService` per the job's `output_format`; the connector itself is format-agnostic.

### 4.5 `DataPipelineConnector` protocol

```python
class DataPipelineConnector(Protocol):
    async def run(
        self,
        operation: str,
        inputs: dict,
        credentials: dict,
    ) -> PipelineOutput: ...
```

**Implementation rules:**

- `credentials` is a structural contract — a dict with keys `{access_token, expires_at, external_account_id}` as returned by `GET /api/v1/internal/integrations/credentials/{account_id}/{platform_id}` in DP-PRD-02. `StubConnector` accepts any dict.
- Connectors MUST NOT write to Firestore or GCS — `DataPipelineService` owns persistence
- Connectors MUST be stateless: one instance can be reused across accounts and operations

### 4.6 `StubConnector`

Lives in `services/data_pipeline/connectors/stub.py`. Returns a deterministic `PipelineOutput` whose `rows` are a function of `inputs` (e.g., `[{"key": k, "value": v} for k, v in sorted(inputs.items())]`). Used by:

- Contract tests in this PRD
- DP-PRD-03 integration tests that exercise the orchestrator dispatch branch before DP-PRD-02 ships

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `services/data_pipeline/src/kene_data_pipeline/__init__.py` |
| Create | `services/data_pipeline/src/kene_data_pipeline/main.py` — FastAPI app + internal router registration + OIDC auth + Weave init |
| Create | `services/data_pipeline/src/kene_data_pipeline/models.py` — `DataPipelineJob`, `DataPipelineRun`, `PipelineJobSpec`, `PipelineOutput`, `FieldSpec`, `BqTableRef`, `DataPipelineConnector` protocol |
| Create | `services/data_pipeline/src/kene_data_pipeline/service.py` — `DataPipelineService` (resolve job, validate inputs, cache lookup, dispatch to connector, persist run) |
| Create | `services/data_pipeline/src/kene_data_pipeline/cache.py` — `compute_input_hash(account_id, job_id, inputs, version) -> str`; cache-key canonicalization via `json.dumps(..., sort_keys=True, separators=(",", ":"))` |
| Create | `services/data_pipeline/src/kene_data_pipeline/connectors/__init__.py` |
| Create | `services/data_pipeline/src/kene_data_pipeline/connectors/stub.py` — `StubConnector` |
| Create | `services/data_pipeline/src/kene_data_pipeline/routers/internal.py` — `POST /api/v1/internal/data-pipeline/run` |
| Create | `services/data_pipeline/Dockerfile` — Cloud Run-compatible container |
| Create | `services/data_pipeline/pyproject.toml` — Python deps (`fastapi`, `uvicorn`, `google-cloud-firestore`, `google-cloud-storage`, `pyarrow`, `jsonschema`, `weave`) |
| Create | `api/src/kene_api/routers/data_pipeline.py` — catalog + runs read endpoints (main API; reads the sibling service's Firestore directly) |
| Modify | `api/src/kene_api/main.py` — register `data_pipeline` router |
| Create | `api/src/kene_api/models/data_pipeline_models.py` — Pydantic mirrors for the main API router (import from shared module or duplicate per existing convention; duplicate is fine if the sibling service is a separate deploy unit) |
| Create | `deployment/terraform/data_pipeline_service.tf` — Cloud Run service `kene-data-pipeline-{env}` + IAM + secrets |
| Create | `deployment/terraform/data_pipeline_firestore.tf` — composite-index registry entries |
| Create | `deployment/migrations/DM-2026-05-01-data-pipeline-collections.py` — migration authored against DM-PRD-00's framework; provisions empty `data_pipeline_jobs` root collection + indexes |
| Create | `services/data_pipeline/tests/unit/test_models.py` |
| Create | `services/data_pipeline/tests/unit/test_cache.py` |
| Create | `services/data_pipeline/tests/unit/test_service.py` |
| Create | `services/data_pipeline/tests/unit/test_stub_connector.py` |
| Create | `services/data_pipeline/tests/integration/test_internal_run_endpoint.py` |
| Create | `api/tests/integration/test_data_pipeline_catalog_router.py` |
| Create | `api/tests/integration/test_data_pipeline_runs_router.py` |

### Firestore layout

```
data_pipeline_jobs/{job_id}                                   # global catalog — Shape B carve-out
accounts/{account_id}/data_pipeline_jobs/{job_id}             # per-account overlay + custom jobs
accounts/{account_id}/data_pipeline_runs/{run_id}             # execution history
```

Catalog resolution rule: when `DataPipelineService` loads a job, per-account overlay takes precedence over the global entry for the same `job_id`. If the per-account doc is missing, fall back to the global doc. The frontend (DP-PRD-04) shows both with a "Custom" badge on overlays.

### Composite indexes

| Collection | Fields | Used by |
|---|---|---|
| `accounts/{account_id}/data_pipeline_runs` (collection-group) | `account_id ASC, plan_id ASC, started_at DESC` | `GET /runs?plan_id=...` |
| `accounts/{account_id}/data_pipeline_runs` (collection-group) | `account_id ASC, job_id ASC, started_at DESC` | `GET /runs?job_id=...` |
| `accounts/{account_id}/data_pipeline_runs` (collection-group) | `account_id ASC, status ASC, started_at DESC` | `GET /runs?status=...` |
| `accounts/{account_id}/data_pipeline_jobs` (collection-group) | `account_id ASC, connector ASC` | `GET /jobs?connector=...` |

### Cache key canonicalization

```python
def compute_input_hash(account_id: str, job_id: str, inputs: dict, version: int) -> str:
    canonical = json.dumps(
        {"account_id": account_id, "job_id": job_id, "inputs": inputs, "version": version},
        sort_keys=True,
        separators=(",", ":"),
        default=str,                       # for date/datetime inputs — ISO 8601
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

Per-account caching is enforced by the `account_id` inclusion. A cache hit writes a `DataPipelineRun` with `status="cached"`, `cache_hit=True`, and `output_artifact_id` copied from the prior successful run for the same hash.

## 6. API contract

### 6.1 `POST /api/v1/internal/data-pipeline/run` (sibling Cloud Run service)

**Auth:** OIDC. Caller SA is the same one PR-PRD-06's scheduler uses; the orchestrator identity invokes via service-to-service auth.

**Request:**

```json
{
  "account_id": "a_123",
  "plan_id": "p_456",
  "task_id": "t_789",
  "job_id": "ga.transactions_by_date",
  "inputs": {"start_date": "2026-04-01", "end_date": "2026-04-07"},
  "is_test": false
}
```

**Response:**

```json
{
  "run_id": "r_abc",
  "status": "running",
  "cache_hit": false,
  "started_at": "2026-04-23T07:00:00Z"
}
```

The endpoint returns immediately after persisting the `running` (or `cached`) run record; the actual connector execution happens in a `BackgroundTasks` and PATCHes the run to `succeeded` / `failed` on completion. 10-minute cap enforced via an `asyncio.wait_for` around the connector call; breach fails the run with `error_message="timeout_10_min"`.

**Error codes:**

| Code | Condition |
|---|---|
| `401` | Missing / invalid OIDC token |
| `403` | Caller SA not in the allowed service-to-service list |
| `404` | `job_id` not in the global catalog and not in the per-account overlay |
| `422` | `inputs` fails `DataPipelineJob.input_schema` validation; body names the offending keys |
| `429` | Per-connector rate-limit breach (shell shape exposed here; enforcement arrives in DP-PRD-02) — response body `{"retry_after_seconds": 60}` |
| `500` | Connector raised an unhandled exception; body sanitized via existing FastAPI exception handlers |

### 6.2 `GET /api/v1/data-pipeline/jobs` (main API)

**Auth:** account-scoped user auth (same pattern as `/plans/*`).

**Query params:** `connector` (optional), `include_overlay` (bool, default `true`), `account_id` (required when `include_overlay=true`).

**Response:**

```json
{
  "jobs": [
    {
      "job_id": "ga.transactions_by_date",
      "connector": "google_analytics",
      "operation": "transactions_by_date",
      "display_name": "Transactions by Date",
      "description": "...",
      "input_schema": {...},
      "output_schema": {...},
      "source": "global"
    },
    {
      "job_id": "acme.custom_mailchimp",
      "connector": "mailchimp",
      "source": "account_overlay",
      "...": "..."
    }
  ]
}
```

### 6.3 `GET /api/v1/data-pipeline/jobs/{job_id}`

Returns the overlay doc if present for the caller's account, else the global doc, else `404`. Response shape mirrors a single `DataPipelineJob`.

### 6.4 `POST /api/v1/data-pipeline/jobs`

**Auth:** user auth + `require_role("editor")` from DM-PRD-07.

**Body:** a `DataPipelineJob` payload. Validated against the Pydantic schema + JSON-Schema meta-validation on the declared `input_schema` / `output_schema`.

**Response:** `201` with the persisted doc + `Location` header pointing at `/jobs/{job_id}`.

**Error codes:** `403` role check fails; `409` `job_id` already exists in the account overlay; `422` schema validation fails (body names the offending field path).

### 6.5 `GET /api/v1/data-pipeline/{account_id}/runs`

**Query params:** `plan_id`, `task_id`, `job_id`, `status`, `from` (ISO datetime), `to` (ISO datetime), `cursor`, `page_size` (default 50, max 200).

**Response:** `{"runs": [DataPipelineRun, ...], "next_cursor": "..."}`.

### 6.6 `GET /api/v1/data-pipeline/{account_id}/runs/{run_id}`

Response: a single `DataPipelineRun` plus a signed URL for the output artifact (via A-PRD-03's signing helper when `output_artifact_id` is set; URL expiry 1 hour).

**Error codes:** `404` run not found or cross-account access.

### 6.7 Consumption rules

- The internal endpoint is the single entry point for run execution. The main API's run read endpoints are strictly read-only.
- Callers of `POST /api/v1/internal/data-pipeline/run` MUST set both `plan_id` and `task_id` when the caller is the orchestrator; ad-hoc calls (reserved for internal debugging) may leave them `null` but the run record stays queryable by `job_id`.
- The catalog endpoints are safe to call frequently — frontend (DP-PRD-04) will fetch the catalog on `ProjectEditDrawer` mount. No rate limit beyond the existing per-IP limit on `/api/v1/*`.

## 7. Acceptance criteria

1. `DataPipelineJob`, `DataPipelineRun`, `PipelineJobSpec`, `PipelineOutput`, `FieldSpec`, `BqTableRef`, and `DataPipelineConnector` are importable from `kene_data_pipeline.models` and pass a `mypy --strict` check under the service's `pyproject.toml`.
2. `StubConnector.run(operation="echo", inputs={"a": 1}, credentials={})` returns a `PipelineOutput` whose `rows == [{"key": "a", "value": 1}]`.
3. `POST /api/v1/internal/data-pipeline/run` with a valid OIDC token, an existing `StubConnector`-backed job, and well-formed inputs returns `201` with a `run_id`; a `DataPipelineRun` doc exists at `accounts/{account_id}/data_pipeline_runs/{run_id}` with `status="running"` on first read, transitioning to `succeeded` after the background task completes.
4. A second invocation with identical `(account_id, job_id, inputs, version)` returns `201` with `cache_hit=true`, `status="cached"`, and `output_artifact_id` copied from the first run; no connector call is made on the second invocation.
5. Invocation without a valid OIDC token returns `401`.
6. Invocation from a non-allowlisted service account returns `403`.
7. Invocation with `job_id` not present in the catalog returns `404`.
8. Invocation with inputs violating the job's `input_schema` returns `422` with a body naming the offending JSON-Pointer path (e.g., `"/start_date"`).
9. The 10-minute cap is enforced: a connector whose `run()` sleeps 11 minutes causes the endpoint to mark the run `failed` with `error_message="timeout_10_min"`.
10. `GET /api/v1/data-pipeline/jobs` returns the union of global catalog entries and the account overlay, with overlay entries carrying `source="account_overlay"`; filtering by `connector=google_analytics` restricts the response accordingly.
11. `POST /api/v1/data-pipeline/jobs` requires `editor` role (per DM-PRD-07); a viewer-role caller receives `403`; a missing `input_schema` or malformed JSON Schema receives `422` with the JSON-Pointer path of the failure.
12. `GET /api/v1/data-pipeline/{account_id}/runs?plan_id=...` returns only runs for that account + plan; cross-account access (user from account A requesting account B's runs) returns `403`.
13. `GET /api/v1/data-pipeline/{account_id}/runs/{run_id}` includes a 1-hour-TTL signed URL in the response when `output_artifact_id` is set; when unset, the field is `null`.
14. Every run (hit or miss) emits a `data_pipeline.run` Weave span with attributes `{connector, operation, input_hash, row_count, cache_hit, test_mode}`; span shape verified by a contract test asserting exact key set.
15. The migration `DM-2026-05-01-data-pipeline-collections.py` runs cleanly under DM-PRD-00's framework; composite indexes listed in §5 exist after migration in the local emulator and in the Terraform-managed indexes file.
16. `make lint` passes (**G-1**: ruff + mypy + codespell) and `pytest services/data_pipeline/tests/ api/tests/integration/test_data_pipeline_*.py` passes green on CI.

## 8. Test plan

**Unit tests** (`services/data_pipeline/tests/unit/`):

- `test_models.py` — `DataPipelineJob` validators: `job_id` regex matches / rejects; `input_schema` meta-validation fails for non-JSON-Schema dicts; `version` rejects `0`. `DataPipelineRun` status transitions: `running → succeeded` allowed, `succeeded → running` rejected; `cache_hit=True` without `status="cached"` rejected. `PipelineOutput` roundtrips through `.model_dump() / .model_validate()` preserving row order.
- `test_cache.py` — `compute_input_hash` stability: same inputs in different key orders yield identical hash; adding / removing a key changes the hash; date and datetime inputs are canonicalized as ISO 8601 strings; account-scoping — same `(job_id, inputs, version)` with different `account_id` yields distinct hashes.
- `test_service.py` — job resolution: overlay precedence over global; overlay missing → global returned; both missing → `404`. Input validation: schema failure produces a `ValidationError` naming the offending path. Cache hit path: second call returns the prior `output_artifact_id` without invoking the connector (mock asserts call count = 0).
- `test_stub_connector.py` — deterministic output given inputs; accepts arbitrary `credentials`; returns a `PipelineOutput` whose `schema` matches the row shape.

**Integration tests** (`services/data_pipeline/tests/integration/`):

- `test_internal_run_endpoint.py` — valid OIDC + valid job + valid inputs → `201`, run doc written, background task transitions status. Invalid OIDC → `401`. Non-allowlisted SA → `403`. Unknown `job_id` → `404`. Schema failure → `422` with JSON Pointer. 10-minute cap enforced via a connector that sleeps (test uses `asyncio.wait_for` with a reduced cap for speed). Cache hit path: two identical invocations produce two run docs (one `succeeded`, one `cached`) with the same `output_artifact_id`. Weave span shape assertion (`{connector, operation, input_hash, row_count, cache_hit, test_mode}`).

**Integration tests** (`api/tests/integration/`):

- `test_data_pipeline_catalog_router.py` — `GET /jobs` returns union; filter by `connector` works; `GET /jobs/{job_id}` resolves overlay > global; unknown `job_id` → `404`. `POST /jobs` with editor role → `201`; viewer role → `403`; malformed `input_schema` → `422` with JSON Pointer; duplicate `job_id` → `409`.
- `test_data_pipeline_runs_router.py` — `GET /runs` filter matrix (`plan_id`, `task_id`, `job_id`, `status`, `from`, `to`) returns the right subset. Cross-account access → `403`. `GET /runs/{run_id}` returns a signed URL when the run has `output_artifact_id`; omits it otherwise.

**E2E / contract tests** (`services/data_pipeline/tests/integration/test_stub_e2e.py`):

- Seed a global `DataPipelineJob` backed by `StubConnector`. Invoke the internal endpoint with valid inputs. Assert: (a) run transitions `running → succeeded` within 2s, (b) `PipelineOutput.rows` matches the stub's deterministic shape, (c) Weave span was emitted with the documented key set, (d) a second identical invocation is served from cache with `status="cached"` and no connector invocation.

## 9. Risks & open questions

### Resolved decisions

| Decision | Resolution |
|---|---|
| Deployment target | **Sibling Cloud Run service** — `kene-data-pipeline-{env}` — lower start latency than a container-per-invocation model, shared connection pooling, isolated from main-API request-path latency budgets. Matches plan §3.3. |
| Cache granularity | **Per-account.** The `account_id` is in the cache key. Global caching would leak timing signals across tenants. |
| Artifact format default | **Parquet** with per-job override (`output_format="json"` for non-tabular). Validated at `DataPipelineJob` creation time. |
| Cache-miss audit | **Cache hits write a `DataPipelineRun` with `status="cached"`.** Without this, audit completeness breaks — a support engineer can't tell which user triggered a cached read. |
| Custom-job authoring in v1 | **Yes** — per-account overlay collection + `POST /jobs` endpoint land in this PRD; the authoring UI ships in DP-PRD-04. Schema validation via JSON-Schema meta-validator on write. |
| Role gate on `POST /jobs` | **`editor`** per DM-PRD-07. Viewer role is read-only across the catalog. |
| Rate-limit enforcement location | **Per-connector in DP-PRD-02+.** The `429` error shape is documented here for contract consistency but this PRD's `StubConnector` never trips it. |
| `is_system` convention | **Inherited from PR-PRD-01** — seeded global catalog jobs carry `is_system=true`; cannot be edited via the per-account overlay path. |

### Remaining open questions

| Question | Disposition |
|---|---|
| Where do the shared Pydantic models live — inside the sibling service, inside the main API, or in a shared package? | First pass: duplicate in both trees, since the sibling service is a separate deploy unit with its own Docker image. A shared package (`kene-common`) is a follow-up if duplication proves a maintenance burden. Document in the DP-PRD-06 retrospective. |
| Soft-delete vs. hard-delete on account-overlay jobs | First pass: **soft-delete** via `is_active=false` field on the overlay doc, mirroring `ProjectPlan`. Hard-delete is an admin tool only. CONFIRM during DP-PRD-04 authoring-UI design. |
| Should the internal run endpoint support `dry_run=true` (validate inputs + compute cache key, no execute)? | Out of scope for this PRD. DP-PRD-04's custom-job preview will call the real endpoint against the `StubConnector` in staging. Revisit if product demand shows up. |
| BigQuery external-table lifecycle | Field defined here, activation in DP-PRD-02 for tabular jobs that opt in. Plan §10 open question: when Parquet schema evolves across job versions, new version → new external table name (version-suffixed). TODO: confirm naming convention during DP-PRD-02 kickoff. |

## 10. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md) §3 (Data-model), §4 (API surface), §7 DP-PRD-01
- Upstream: [DM-PRD-00 — Migration Foundation](../../data-management/projects/DM-PRD-00-migration-foundation.md)
- Upstream (soft): [DM-PRD-07 — Approval Workflow & Audit](../../data-management/projects/DM-PRD-07-approval-workflow-and-audit.md) — `require_role` + `write_audit`
- Sibling (downstream): [DP-PRD-02 — Google Analytics connector](./DP-PRD-02-google-analytics-connector.md)
- Sibling (downstream): [DP-PRD-03 — Task-system integration](./DP-PRD-03-task-system-integration.md)
- Cross-component: [`../../sar-e/implementation-plan.md`](../../sar-e/implementation-plan.md) §5.1 — SAR-E as the first production consumer
- Cross-component: [`../../integrations/implementation-plan.md`](../../integrations/implementation-plan.md) §4 — `/api/v1/internal/integrations/credentials/{account_id}/{platform_id}` contract
- Cross-component: [`../../project-tasks/README.md`](../../project-tasks/README.md) §2.3 — `ProjectPlan` / `PlanTask` API
- Pattern files: `api/src/kene_api/routers/strategy.py`, `api/src/kene_api/routers/project_plans.py`, `api/src/kene_api/services/firestore_service.py`, `app/utils/gcs.py`, `app/adk/tracking/`
- CLAUDE.md rules in scope: **BP-1** (clarify before coding); **C-2** (domain vocabulary — `connector`, `operation`, `job`, `run`), **C-4** (small composable functions in `service.py` + `cache.py`); **PY-1**, **PY-2**, **PY-3**, **PY-5**, **PY-7** (Python conventions); **D-1**, **D-2**, **D-5** (database); **T-1**, **T-3**, **T-4**, **T-5**, **T-8** (testing); **G-1** (`make lint` gate); **O-1**, **O-2** (code organization — sibling service under `services/data_pipeline/`, shared types mirrored)
