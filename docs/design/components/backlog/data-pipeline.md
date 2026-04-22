# Data Pipeline — Component Implementation Plan

> **Status:** Backlog — not yet broken into project PRDs
> **Last Updated:** 2026-04-20
> **Proposed component prefix:** `DP-PRD-NN`
> **Proposed Linear team:** [TBD] Data Pipeline
> **Release bucket:** TBD (depends on upstream components — see §8)

## 1. Overview

The Data Pipeline component is KEN-E's **deterministic, non-agentic** path to third-party platform APIs (Google Analytics first, then Google Ads, Meta Ads, Mailchimp, etc.). It exists because the agent-routed path — Root Agent → dispatch → narrow specialist → MCP tool call → code execution — is the right shape for ambiguous, analytical, reasoning-heavy requests ("what changed in traffic last week?") but the wrong shape for repeatable, well-defined extractions ("pull transactions by date for the last 30 days every Monday at 07:00 UTC"). For the second class of work, the data pipeline calls the platform API directly with a known recipe, produces a structured artifact, and hands off to downstream tasks.

Concretely, a user composing a project in the Calendar view can assign a task to the **Data Pipeline** (a third `assignee_type` alongside `agent` and `human`). The task carries a `pipeline_job` reference (e.g., `ga.transactions_by_date`) plus its input parameters. When the `TaskOrchestrator` fires the task, it dispatches to the Data Pipeline service instead of Agent Engine. The service runs the named job via a platform connector, writes the result as a `TaskArtifact` to the GCS bucket owned by the Automations platform (A-PRD-03), and marks the task Complete. Downstream agent or human tasks read that artifact as upstream context. Because the same inputs always produce the same output, pipeline runs are cache-friendly, cheap, auditable, and free of LLM non-determinism.

A developer reading only this section should understand: this component adds a `data_pipeline` task executor that bypasses Agent Engine for deterministic API calls, reuses OAuth credentials already stored for the matching specialist agent, plugs into the existing `TaskOrchestrator` dispatch path, and emits outputs through the existing `TaskArtifact` contract. It does **not** replace the Google Analytics Specialist or any other agent — the two paths are complementary, not alternatives.

## 2. Why this component is needed

| Scenario | Agent path (today / AH-PRD-03) | Data pipeline path (proposed) |
|----------|-------------------------------|-------------------------------|
| "What caused the drop in conversions last week?" | ✅ GA Specialist reasons, calls multiple MCP tools, runs code execution, iterates with reviewer | ❌ Not a fit — requires reasoning |
| "Pull transactions broken down by date for the last 30 days" | ⚠️ Works, but each run costs LLM tokens, review-loop iterations, and may format differently | ✅ Deterministic — one API call, one CSV, cached |
| "Every Monday at 07:00 UTC, refresh the weekly KPI table" | ⚠️ 52 LLM-driven runs per year with variable output | ✅ One recipe, executed 52 times with byte-identical output for byte-identical inputs |
| "Fetch last month's Meta ad spend and pass it into the strategy agent as context" | ⚠️ Round-tripping through an agent to get structured data is wasteful | ✅ Pipeline produces the artifact; agent reads it as upstream context |

The core principle: **reasoning belongs in agents, extraction belongs in pipelines.** When a marketing team codifies a known data pull, promoting it from an agent task to a pipeline job saves tokens, saves latency, and makes the output deterministic enough to diff across runs.

## 3. Architecture

```
┌───────────────────────────────────────────────────────────────────────────┐
│  Calendar UI (PR-PRD-03) / Automations UI (A-PRD-05/06)                   │
│    Task editor — assignee_type dropdown: agent | human | data_pipeline    │
│    Pipeline spec editor — pick a job from the catalog + fill inputs       │
└─────────────────────────────┬─────────────────────────────────────────────┘
                              │ PATCH /plans/.../tasks/...
                              ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  TaskOrchestrator (PR-PRD-04)                                             │
│    on_task_status_change / on_task_due                                    │
│    if task.assignee_type == "data_pipeline":                              │
│        DataPipelineDispatcher.dispatch(task)                              │
│    elif task.assignee_type == "agent":                                    │
│        AgentEngineClient.invoke(...)      (existing)                      │
│    else:                                                                  │
│        NotificationService.notify_human(...)   (existing)                 │
└─────────────────────────────┬─────────────────────────────────────────────┘
                              │ dispatch
                              ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  Data Pipeline Service (new — Python, Cloud Run sibling to the API)       │
│    1. Resolve job_id → DataPipelineJob (global catalog + overlay)         │
│    2. Validate inputs against job schema                                  │
│    3. Look up cache by (account_id, job_id, input_hash)                   │
│    4. If miss: load OAuth creds → instantiate connector → run            │
│    5. Serialize output (CSV/JSON/Parquet) → write TaskArtifact (A-PRD-03) │
│    6. PATCH task status → Complete, attach artifact                      │
│    7. Emit Weave span: data_pipeline.run                                 │
└─────────────────────────────┬─────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  Connector layer (one per platform)                                       │
│    GoogleAnalyticsConnector  (uses ga_credentials + GA Data API)          │
│    GoogleAdsConnector        (uses google_ads_credentials + google-ads)   │
│    MetaAdsConnector          (uses meta_credentials + facebook-business)  │
│    MailchimpConnector        (uses mailchimp_credentials + mailchimp SDK) │
│    ... implements DataPipelineConnector protocol                          │
└───────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Key abstractions (proposed)

| Abstraction | Purpose |
|-------------|---------|
| `DataPipelineJob` (Pydantic) | Catalog entry describing a named recipe — connector, operation, input schema (JSON Schema), output schema, rate-limit hints, version. |
| `PipelineJobSpec` (embedded in `PlanTask`) | What a specific task instance runs — `job_id`, `inputs: dict`, `output_artifact_name`. Validated against the job's input schema at save time. |
| `DataPipelineRun` (Pydantic + Firestore) | Execution record — `run_id`, `account_id`, `plan_id`, `task_id`, `job_id`, `inputs`, `input_hash`, `output_artifact_id`, `status`, `started_at`, `finished_at`, `error`, `cache_hit: bool`. |
| `DataPipelineConnector` (Protocol) | Common interface: `async def run(operation: str, inputs: dict, credentials: dict) -> PipelineOutput`. Each platform implements one. |
| `DataPipelineDispatcher` | Single entry point from `TaskOrchestrator`. Resolves job → connector, manages cache, writes artifact, updates task. |
| `PipelineOutput` | Normalized shape — `{rows: list[dict], schema: list[FieldSpec], metadata: {row_count, query_params, source_api_version}}`. Serialized per artifact mime type. |

### 3.2 Data model additions

```python
# Extend PlanTask (PR-PRD-01):
class PlanTask(BaseModel):
    ...
    assignee_type: Literal["agent", "human", "data_pipeline"]  # ADDED value
    pipeline_spec: PipelineJobSpec | None = None               # populated iff data_pipeline

class PipelineJobSpec(BaseModel):
    job_id: str           # references data_pipeline_jobs/{job_id}
    inputs: dict          # validated against job's input_schema
    output_artifact_name: str

# New:
class DataPipelineJob(BaseModel):
    job_id: str
    connector: Literal["google_analytics", "google_ads", "meta_ads", "mailchimp", ...]
    operation: str                    # e.g. "transactions_by_date"
    display_name: str
    description: str
    input_schema: dict                # JSON Schema
    output_schema: dict               # JSON Schema (describes tabular output)
    default_cache_ttl_seconds: int | None
    visible_in_frontend: bool
    version: int

class DataPipelineRun(BaseModel):
    run_id: str
    account_id: str
    plan_id: str
    task_id: str
    job_id: str
    inputs: dict
    input_hash: str
    output_artifact_id: str | None
    status: Literal["running", "succeeded", "failed", "cached"]
    cache_hit: bool
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None
    tokens_charged: int               # always 0 for pipeline — kept for parity with agent runs
```

### 3.3 Firestore layout (Shape B convention)

| Path | Scope | Notes |
|------|-------|-------|
| `data_pipeline_jobs/{job_id}` | Global (Shape B carve-out) | Ships with platform; mirrors the `agent_configs/*` global pattern |
| `accounts/{account_id}/data_pipeline_jobs/{job_id}` | Per-account overlay + custom jobs | Same shallow-merge pattern as `agent_configs` overlays (AH-PRD-02) |
| `accounts/{account_id}/data_pipeline_runs/{run_id}` | Per-account | Execution history for audit, debugging, cache lookup |

### 3.4 Credential reuse

No new OAuth flow. The data pipeline reuses the same credential keys that the corresponding specialist agent uses — the connectors read from Firestore (or the same session-state layer, depending on execution context):

| Connector | Credential source | Established by |
|-----------|-------------------|----------------|
| `GoogleAnalyticsConnector` | `ga_credentials` | Existing (AH-PRD-03) |
| `GoogleAdsConnector` | `google_ads_credentials` | Future GA-Ads specialist |
| `MetaAdsConnector` | `meta_credentials` | Future Meta specialist |
| `MailchimpConnector` | `mailchimp_credentials` | Future Mailchimp specialist |

Note: pipeline runs are dispatched from the API tier (not from an ADK session), so credentials are loaded directly from the encrypted Firestore store rather than from `tool_context.state`. The same decrypt-on-load pattern used by the agent factory's `_make_header_provider(auth_type)` (AH-PRD-02) is reused.

### 3.5 Execution model

- **Deployment target:** sibling Cloud Run service (`kene-data-pipeline-{env}`), not embedded in the API. Rationale: isolate long-running extracts from request-path latency budgets; independent scaling.
- **Invocation:** `TaskOrchestrator` makes an HTTP call to the service's internal endpoint `POST /internal/data-pipeline/run` with the task reference. OIDC service-account auth mirrors the pattern in `PR-PRD-06` / `A-PRD-02`.
- **Concurrency:** runs are fire-and-forget from the orchestrator's perspective; the service PATCHes back to the plan when done. A single run is capped at (proposed) 10 minutes; longer extracts require chunking at the job-definition level.
- **Observability:** every run emits a `data_pipeline.run` Weave span with `{connector, operation, input_hash, row_count, cache_hit}` attributes, sibling to agent dispatch spans.

### 3.6 Caching & idempotency

- Cache key: `sha256(account_id || job_id || canonical_json(inputs) || job.version)`.
- On cache hit, the run record is still written (`status=cached`, `cache_hit=true`, pointing at the prior artifact) so audit history stays complete.
- TTL comes from `DataPipelineJob.default_cache_ttl_seconds` (can be overridden per-spec). Jobs that return "today's" data set TTL=0; reporting jobs over fixed windows set TTL=∞.

## 4. Integration with Project Tasks & Automations

The data pipeline is additive to the existing task/automation stack — it does not require changes to the `ProjectPlan` schema beyond the `PlanTask` extensions in §3.2.

### 4.1 Project Tasks (PR-PRDs)

- **PR-PRD-01 (Data Model & API):** extended with `assignee_type="data_pipeline"` and the `pipeline_spec` field. DAG validator unchanged — pipeline tasks are just another node.
- **PR-PRD-03 (Calendar Page Frontend):** the `ProjectEditDrawer` gains a "Data Pipeline" option in the assignee selector; when chosen, a job-picker + schema-driven input form replaces the human/agent assignee fields.
- **PR-PRD-04 (Event-Driven Orchestrator):** `TaskOrchestrator` gains a branch: `data_pipeline` tasks dispatch to `DataPipelineDispatcher`. Revision loop is not applicable to pipeline tasks (deterministic output — nothing to revise). On failure, the existing failure-handling path applies.

### 4.2 Automations (A-PRDs)

- **A-PRD-02 (Recurring Scheduler & Run Engine):** unchanged. Recurring automations spawn `PlanRun`s that contain pipeline tasks; each task is cloned from the template along with its `pipeline_spec`. The `{inputs.*}` substitution layer from A-PRD-02 can be applied to `pipeline_spec.inputs` the same way it applies to agent prompts.
- **A-PRD-03 (Task Artifact System):** pipeline output is a `TaskArtifact` — same bucket, same lifecycle, same metadata model. The pipeline writes directly; no `attach_task_artifact` ADK tool is needed because the service is not an agent.
- **A-PRD-04 (Test / Dry-Run Mode):** `is_test=true` pipeline runs either (a) hit a sandbox endpoint where the platform exposes one, or (b) short-circuit with a recorded fixture from a prior successful run of the same job/input. Per-job policy documented on `DataPipelineJob`.
- **A-PRD-06 (Automation Details Page):** the Outputs tab renders pipeline artifacts the same way it renders agent-produced ones.

### 4.3 Agentic Harness (AH-PRDs)

- **AH-PRD-03 (Google Analytics Specialist):** no changes; the specialist continues to own the reasoning path. The first data-pipeline connector targets the same API (GA Data API) but via the official Python client, not the MCP server — giving the two paths independent failure modes.
- **Future specialists (AH-PRD-05+):** a new specialist and a new connector for the same platform can ship in either order. The connector does not depend on the specialist.

### 4.4 Knowledge Graph (KG-PRDs) — future

Pipeline artifacts are natural inputs for `Observation` ingestion (KG-PRD-02) — a future PRD can add a one-step automation that turns a recurring pipeline pull into dated observations. Out of scope for the initial data-pipeline delivery; noted here because it informs the artifact schema decisions.

## 5. Connector roadmap

The first release ships one connector (Google Analytics) proving the pattern end-to-end. Additional connectors land as user demand warrants; each is ~1 PRD of work because the framework is already in place.

| Connector | Phase | Rationale |
|-----------|-------|-----------|
| `GoogleAnalyticsConnector` | Phase 2 (first connector) | GA is already the first specialist (AH-PRD-03); credential pattern is proven; highest near-term user value. |
| `GoogleAdsConnector` | Phase 5 (connector expansion) | Aligns with the planned Google Ads Specialist in the R5 narrow-specialist roadmap. |
| `MetaAdsConnector` | Phase 5 | Same rationale. |
| `MailchimpConnector` | Phase 5 | Same rationale. |
| `HubSpotConnector` | Deferred | HubSpot specialist isn't yet assigned — revisit when it lands. |

Each connector ships with a small starter library of jobs (3–5 per platform) chosen for common deterministic needs — date-range extracts, spend breakdowns, audience sizes. Users compose additional jobs over time; whether user-authored jobs are admin-only or self-service is an open question (§9).

## 6. Non-goals

- **Replacing the Google Analytics Specialist** — the specialist handles ambiguous questions, data shaping, and reasoning. The pipeline handles deterministic extraction. Both exist.
- **A general-purpose ETL platform** — this is not a substitute for BigQuery, Fivetran, or Airbyte. Scope is "repeatable API calls inside a project task," not "populate a warehouse."
- **User-authored Python for jobs** — jobs are declarative (connector + operation + input schema). Users do not write code. Custom code lives in Skills (Feature 2.6) when that component's sandbox is mature enough.
- **Cross-platform joins inside a single job** — a pipeline job hits one connector. Multi-platform assembly is the job of a downstream agent task that reads multiple upstream pipeline artifacts.
- **Real-time streaming** — all pipeline runs are batch, invoked on demand or on schedule.

## 7. Proposed project decomposition

Six candidate projects (`DP-PRD-01` … `DP-PRD-06`). The exact splits may shift when detailed PRDs are written; this is the first-pass shape used for estimation.

### Phase 1 — Foundation (`DP-PRD-01`)
- Pydantic models — `DataPipelineJob`, `DataPipelineRun`, `PipelineJobSpec`.
- `DataPipelineConnector` protocol + `PipelineOutput` normalized shape.
- `DataPipelineService` scaffold + internal `/run` endpoint (OIDC-authed).
- Cache lookup/write in Firestore + run-record persistence.
- `StubConnector` for contract validation in tests — returns deterministic fixtures.
- Firestore collections + migration entry for `data_pipeline_jobs` and `accounts/*/data_pipeline_runs`.
- **Exit criteria:** `DP-PRD-01` can execute a stub job end-to-end, write a `DataPipelineRun`, and return a `PipelineOutput`.

### Phase 2 — Google Analytics connector (`DP-PRD-02`)
- `GoogleAnalyticsConnector` implementing the protocol via the GA Data API v1 Python client.
- Starter job catalog seeded into `data_pipeline_jobs`:
  - `ga.sessions_by_date`
  - `ga.transactions_by_date`
  - `ga.conversions_by_source_medium`
  - `ga.top_landing_pages`
- Credential loading pattern shared with AH-PRD-02's `_make_header_provider("ga_oauth")`.
- Per-connector rate-limit + retry handling.
- Unit tests (mock GA client) + integration tests (live API, marked `@pytest.mark.platform`).
- **Exit criteria:** each seeded GA job runs end-to-end against a real GA4 property and produces a deterministic artifact.

### Phase 3 — Task system integration (`DP-PRD-03`)
- `PlanTask.assignee_type` extended to `"agent" | "human" | "data_pipeline"`; `pipeline_spec` field added (PR-PRD-01 patch).
- `TaskOrchestrator.on_task_due` / `on_task_status_change` gain a `data_pipeline` branch dispatching to `DataPipelineDispatcher` (PR-PRD-04 patch).
- `DataPipelineDispatcher` bridging the orchestrator to `DataPipelineService`; writes resulting `TaskArtifact` through the A-PRD-03 pipeline.
- Revision-loop path explicitly disabled for pipeline tasks.
- `is_test` branch (A-PRD-04) — sandbox / replay policy per job.
- **Exit criteria:** a project with one pipeline task can be activated; the task runs, an artifact is written, a downstream agent task sees it as upstream context.

### Phase 4 — Frontend (`DP-PRD-04`)
- `ProjectEditDrawer` assignee dropdown adds "Data Pipeline".
- `PipelineJobPicker` — browses the global + account-overlay job catalog, filterable by connector.
- Schema-driven input form (JSON Schema → form) with inline validation.
- Pipeline run viewer embedded in `ActivityDetailPanel` (status, inputs, artifact preview, cache indicator).
- Read-only pipeline catalog admin page at `/workflows/data-pipelines` (global list; per-account overlays deferred unless needed).
- **Exit criteria:** a user can compose, activate, and review a pipeline task end-to-end from the UI without API calls.

### Phase 5 — Additional connectors (`DP-PRD-05`)
- `GoogleAdsConnector`, `MetaAdsConnector`, `MailchimpConnector` (one connector per PRD is acceptable if estimation shows this is too wide).
- Seed job catalog per connector.
- Credential-loader extension for each new `auth_type`.
- **Exit criteria:** users of the R5 narrow-specialist cohort can run deterministic extracts for every platform the specialists cover.

### Phase 6 — Integration testing & polish (`DP-PRD-06`)
- End-to-end test: pipeline task → artifact → downstream agent task reads artifact → review loop passes.
- Recurring automation smoke test: pipeline task inside a scheduled `PlanRun` with `{inputs.*}` substitution.
- Cost / rate-limit load test — concurrent runs per account + per connector.
- Observability dashboard — pipeline-run volume, cache-hit rate, failure rate per connector.
- Documentation sweep: `api/CLAUDE.md` runbook for connector failures, re-auth prompts, `frontend/CLAUDE.md` pipeline-task UI notes.
- **Exit criteria:** verification report appended to the component README; ready to mark the component GA.

### Candidate dependency graph

```
DP-PRD-01 (Foundation) ──┬──► DP-PRD-02 (GA Connector) ──┐
                         │                               │
                         └──► DP-PRD-03 (Task System)    ├──► DP-PRD-06 (Integration & Polish)
                                      │                  │
                                      ▼                  │
                              DP-PRD-04 (Frontend) ──────┤
                                                         │
                         DP-PRD-05 (Additional Connectors) ◄─ (can start after DP-PRD-02 proves the pattern)
```

## 8. Dependencies on other components

### Hard prerequisites (must ship before the data-pipeline component begins)

| Component | What's needed | Reference |
|-----------|---------------|-----------|
| **DM-PRD-00 (Migration Foundation)** | Shape B convention + migration framework for new `data_pipeline_jobs` / `accounts/*/data_pipeline_runs` collections. | `../data-management/projects/DM-PRD-00-migration-foundation.md` |
| **PR-PRD-01 (Data Model & API)** | `PlanTask` exists; data-pipeline adds the `data_pipeline` assignee variant and `pipeline_spec` field. | `../project-tasks/projects/PR-PRD-01-data-model-and-api.md` |
| **PR-PRD-04 (Event-Driven Orchestrator)** | `TaskOrchestrator` dispatch extension point. Pipeline dispatch lives alongside agent / human branches. | `../project-tasks/projects/PR-PRD-04-event-driven-orchestrator.md` |
| **A-PRD-03 (Task Artifact System)** | GCS bucket + `TaskArtifact` model; pipeline outputs are artifacts. | `../automations/projects/` (post-split) |

### Soft prerequisites (strongly recommended)

| Component | Why it helps | Reference |
|-----------|--------------|-----------|
| **AH-PRD-02 (Agent Factory)** | `_make_header_provider(auth_type)` is the credential-loading template the pipeline reuses. Ordering the factory first means both paths converge on one credential pattern. | `../agentic-harness/projects/AH-PRD-02-agent-factory.md` |
| **AH-PRD-03 (Google Analytics Specialist)** | Same GA OAuth token set, same session-state credential shape. Shipping GA specialist first means `ga_credentials` lifecycle is already proven. | `../agentic-harness/projects/AH-PRD-03-google-analytics-specialist.md` |
| **A-PRD-02 (Recurring Scheduler)** | Not required for v1 (pipeline tasks can live inside one-shot projects), but unlocks the highest-value use case — recurring deterministic pulls. Shipping it before DP-PRD-04 lets the Frontend surface recurrence in the same interaction. | `../automations/projects/` |

### Downstream consumers

- **Automations** — recurring data pulls become the first-class pipeline use case.
- **Knowledge Graph (future)** — pipeline artifacts → dated `Observation`s (not in scope here).
- **Future specialists (AH-PRD-05+)** — can reference pipeline jobs in their instructions as "when the user asks for X, suggest the `foo.bar` pipeline task instead of running it yourself."

## 9. Open questions (resolve before DP-PRD-01)

1. **Deployment target:** Cloud Run sibling service, or Cloud Run Job fired per run? Sibling service gives lower start latency and shared connection pooling; Jobs scale-to-zero more naturally. First-pass recommendation: sibling service; revisit if cold-start or idle-cost becomes a pain point.
2. **User-authored jobs:** are custom jobs (per-account Firestore overlays writing to `accounts/{account_id}/data_pipeline_jobs/{job_id}`) part of v1, or admin-only until a later UI PRD? Leaning admin-only for v1 to keep schema validation simple.
3. **Artifact format defaults:** CSV vs Parquet vs JSON per job. Start with JSON rows + optional CSV export at read time; revisit if big pulls show memory pressure.
4. **Cache granularity:** per-account cache (current proposal) or global cache where the same job + inputs hits the same artifact regardless of requesting account? Global is cheaper but leaks timing signals; per-account is safer. Start per-account.
5. **Re-auth signaling:** how does a pipeline run report "the account's GA token expired"? Proposal: write a notification via the existing notification system (same `_requires_reauth` signal the specialist uses) so the user experience stays consistent across both paths.
6. **Rate-limit budgets:** should the pipeline enforce per-account daily / hourly caps on calls to each platform? Not strictly necessary for deterministic extracts, but protective against runaway recurring automations.
7. **Revision semantics:** confirm in PR-PRD-04 that pipeline tasks are excluded from the 5-iteration revision loop — there is nothing an LLM can rewrite about a deterministic pull.
8. **Sandbox policy for A-PRD-04 dry-run mode:** which jobs support true sandbox endpoints, which replay fixtures, and which must be skipped? Per-job policy attribute, default to "skip".

## 10. Reference

- [`../project-tasks/README.md`](../project-tasks/README.md) — `PlanTask`, `TaskOrchestrator`, activation flow
- [`../project-tasks/projects/PR-PRD-04-event-driven-orchestrator.md`](../project-tasks/projects/PR-PRD-04-event-driven-orchestrator.md) — dispatch integration point
- [`../automations/README.md`](../automations/README.md) — `PlanRun`, recurring scheduler, `TaskArtifact`
- [`../agentic-harness/README.md`](../agentic-harness/README.md) — specialist pattern, credential header providers, narrow-per-platform roadmap
- [`../agentic-harness/projects/AH-PRD-03-google-analytics-specialist.md`](../agentic-harness/projects/AH-PRD-03-google-analytics-specialist.md) — GA OAuth + session-state credential pattern this component reuses
- [`../agentic-harness/mcp-architecture.md`](../agentic-harness/mcp-architecture.md) — platform integration decisions; the data pipeline is the **non-MCP** sibling path to the same platforms
- [`../data-management/README.md`](../data-management/README.md) — Shape B convention for new subcollections
- [`../PROJECT-PLANNER.md`](../PROJECT-PLANNER.md) — add `DP-PRD-NN` rows here when PRDs are authored

---

<!-- BACKLOG NOTES

This is a backlog document — not yet an active component. When work begins:
1. Create `docs/design/components/data-pipeline/README.md` (based on `README-TEMPLATE.md`) and port §1–4 of this doc into it.
2. Author `DP-PRD-NN` files under `docs/design/components/data-pipeline/projects/` using the 10-section project-PRD shape established by sibling components.
3. Add each new PRD row to `PROJECT-PLANNER.md` with `blocked_by` populated.
4. Delete or archive this backlog doc once the component folder is bootstrapped — it is a planning artifact, not an enduring design doc.

Open questions in §9 must all be resolved (at least tentatively) before `DP-PRD-01` drafting begins; unresolved questions become risks in the PRD §9.
-->
