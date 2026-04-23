# SE-PRD-02 — Weekly KPI Time Series + Ingestion

**Status:** Blocked — resumes once SE-PRD-01, DP-PRD-01, and DP-PRD-02 ship
**Owner team:** SAR-E component team (backend)
**Blocked by:** SE-PRD-01 (`EffectivenessKPI`, `SarEConfig`, `/config/setup` transaction + automation seeder entry point); DP-PRD-01 (`DataPipelineJob`, `DataPipelineRun`, `PipelineOutput` contract); DP-PRD-02 (the four SAR-E-specific GA daily jobs — `ga.unbranded_search_daily`, `ga.branded_search_daily`, `ga.pdp_views_daily`, `ga.first_purchases_daily`); DP-PRD-03 (`TaskOrchestrator` `data_pipeline` branch — the ingestion automation's extraction tasks run through this)
**Blocks:** SE-PRD-03 (VAR training reads `KPIDataPoint`); SE-PRD-06 (trendline + cost-rollup queries read `KPIDataPoint`); PE-PRD-05 (setup wizard calls `POST /config/backfill-plan` — **new endpoint owned here**)
**Estimated effort:** 4 days

---

## 1. Context

SE-PRD-01 made SAR-E opt-in-able. This PRD makes it actually collect data. After the setup wizard flips `enabled=true`, the `is_system=true` weekly ingestion automation that SE-PRD-01 seeded (with a stub task graph) now needs a real task graph that (a) extracts the prior ISO week's daily values from Data Pipeline per mapped KPI, (b) aggregates the 7 daily rows to 1 weekly row using each KPI's configured `aggregation`, and (c) upserts the result into SAR-E's `kpi_time_series` subcollection. Plus a one-shot backfill plan that does the same thing for the last N ISO weeks.

Three facts shape this PRD:

1. **Weekly is the only persisted granularity in SAR-E.** Daily extracts are produced by Data Pipeline jobs as Parquet artifacts under `kene-task-artifacts-{env}/...`; SAR-E reads them, aggregates, writes one `KPIDataPoint` per `(kpi_id, week_start)`, and does not persist the daily rows. This is the invariant the VAR model (SE-PRD-03) and every analytical query (SE-PRD-06) rely on. Crossing it is a non-goal of v1 (implementation-plan §8).
2. **Partial weeks are tracked explicitly and excluded from VAR input.** The "current" ISO week (Monday → Sunday that is not yet complete at ingestion time) is written with `is_partial=true` so Analysis trendlines can display the in-progress value (with a visual marker) without corrupting training data. Each subsequent ingestion run re-processes partial weeks until they're complete; the `is_partial` flag flips to `false` atomically with the final-week write.
3. **The backfill-plan endpoint is a thin pre-submit probe.** PE-PRD-05 calls `POST /config/backfill-plan` from Step 3 of the wizard to get the computed `backfill_weeks = min(104, min(weeks_available_across_all_four_kpis))` so the UI can surface the cap and name the limiting KPI. The endpoint does not trigger any actual ingestion; the real backfill starts in `/config/setup`. This PRD owns both the probe endpoint and the backfill plan execution.

The ingestion automation's recurrence is `0 7 * * 1 UTC` (Mondays at 07:00 UTC) — seeded by SE-PRD-01 but with a stub task graph. This PRD replaces the stub with the real graph.

## 2. Scope

### In scope

- **`KPIDataPoint` Pydantic model** under `api/src/kene_api/models/sar_e_models.py` (alongside SE-PRD-01's models):
  - `{account_id, kpi_id, week_start, value, source_artifact_ids, ingested_at, is_partial}`
  - Firestore path: `accounts/{account_id}/kpi_time_series/{kpi_id}__{week_start_iso}` (compound id for easy upsert by `(kpi_id, week_start)`)
  - Composite index: `(kpi_id ASC, week_start ASC)` on the collection-group for SE-PRD-03 / SE-PRD-06 reads
- **`POST /api/v1/internal/sar-e/ingest-kpi-series`** (OIDC-authed; called by the weekly automation's final task and by the one-shot backfill plan):
  - Body: `{account_id, kpi_ids, target_week_start, source_artifacts: list[ArtifactRef]}`
  - Reads each listed Data Pipeline artifact (daily rows for the target week), groups by `kpi_id`, aggregates 7 daily rows → 1 weekly value per `EffectivenessKPI.aggregation`, upserts a `KPIDataPoint` per KPI per week
  - Upsert semantics on compound id = idempotency; running the endpoint twice with the same payload is a no-op
  - Partial-week handling: if the target week is the current ISO week (`today < week_end`), writes `is_partial=true`; if the target week is complete, writes `is_partial=false` and (if a partial row already existed) overwrites it atomically
  - Writes audit entry `sar_e.ingest` with `{account_id, kpi_ids, target_week, artifact_count, outcome}`
  - Returns `IngestResponse`: `{written: int, skipped: int, partial: int, data_points: list[KPIDataPointSummary]}`
- **`POST /api/v1/sar-e/{account_id}/config/backfill-plan`** — the pre-submit probe PE-PRD-05 calls from the wizard's Step 3:
  - Body: `{kpi_source_job_ids: list[str]}` (exactly 4)
  - For each `source_job_id`, query Data Pipeline's history-depth indicator (`GET /internal/data-pipeline/jobs/{job_id}/history-depth?account_id=…`) — returns `weeks_available` per job (how far back the connector can fetch)
  - Compute `backfill_weeks = min(104, min(weeks_available))`; if `backfill_weeks < 26`, include a warning flag plus the name of the limiting KPI source
  - Cache the per-source depth for 5 minutes (in-process LRU, `functools.lru_cache` with TTL wrapper) — the wizard iterates Step 3 under the user's gaze and repeated probes should be cheap
  - Response: `BackfillPlanResponse { backfill_weeks, limiting_source_job_id, limiting_source_display_name, per_source_depth: dict[str, int], below_recommended_minimum: bool }`
- **Extend `sar_e_automation_seeder` (from SE-PRD-01)** with:
  - `create_weekly_ingestion_automation(account_id, kpi_ids)` — replaces SE-PRD-01's stub. Composes a `ProjectPlan` with one Data Pipeline extraction task per KPI (via the DP-PRD-03 `TaskOrchestrator` `data_pipeline` branch) for the prior ISO week, plus a final `assignee_type=agent` task whose tool calls `POST /internal/sar-e/ingest-kpi-series` with the produced artifact refs. `is_system=true, recurrence=0 7 * * 1 UTC`.
  - `trigger_one_shot_backfill(account_id, kpi_ids, weeks)` — composes a one-shot (non-recurring) `ProjectPlan` executing the same extraction → aggregation DAG once per ISO week for the last `weeks` weeks. Runs as a background `PlanRun`; completes when all per-week ingestion tasks finish. Uses `is_system=true` so it doesn't pollute the Automations list.
- **Compound-id upsert helper** `api/src/kene_api/services/sar_e_ingestion_service.py`:
  - `write_weekly_data_point(account_id, kpi_id, week_start, value, source_artifact_ids, is_partial) -> KPIDataPoint`
  - Uses Firestore `set(..., merge=False)` on the compound doc id — idempotent by construction
- **Aggregation logic** in `sar_e_ingestion_service.aggregate_daily_to_weekly(kpi: EffectivenessKPI, daily_values: list[tuple[date, float, float | None]]) -> float`:
  - `sum` → `sum(v for _, v, _ in daily_values)`
  - `mean` → `mean(v for _, v, _ in daily_values)`
  - `weighted_mean` → `sum(v * w for _, v, w in daily_values) / sum(w for _, _, w in daily_values)` — weight is the third element; requires the Data Pipeline job to emit a paired weight column
- **Tests**:
  - Unit tests for aggregation (every `aggregation` value + edge cases: all-zero weights, null days, single-day weeks)
  - Unit tests for the upsert helper (idempotency, partial-week flip)
  - Integration test: seed a Data Pipeline fixture with 7 days of daily rows; call `/ingest-kpi-series`; assert 1 weekly row written with `is_partial=false`
  - Integration test: partial-week — seed 4 days, call with `target_week_start = current week`; assert `is_partial=true`; seed remaining 3 days + call again; assert `is_partial=false` and same compound id
  - Integration test: backfill-plan probe with 4 sources of varying depths (104 / 80 / 52 / 26 weeks) → returns `backfill_weeks=26, limiting_source_job_id=<the 26-week one>`
  - Integration test: backfill plan run on a test account seeded with 52 weeks of daily extracts → exactly 52 `KPIDataPoint` rows per KPI; none with `is_partial=true` unless the current week was partial at run time

### Out of scope (handled by other PRDs)

- The `EffectivenessKPI`, `SarEConfig`, `FunnelStageMapping` models + `/config/setup` transaction (SE-PRD-01)
- The four GA daily jobs (`ga.unbranded_search_daily` etc.) — DP-PRD-02 delivers them
- `DataPipelineJob.history-depth` internal endpoint — DP-PRD-01 / DP-PRD-02 own it; this PRD consumes it
- VAR training or any statistical computation (SE-PRD-03)
- Scenario propagation (SE-PRD-04)
- Target derivation (SE-PRD-05)
- Analytical read endpoints (SE-PRD-06)
- Channel Coverage matrix population — SE-PRD-06 or an admin tool owns the heuristic; this PRD only notes the integration point (§5.4)
- Daily-granularity overlays for anomaly investigation — a future enhancement flagged in implementation-plan §8

## 3. Dependencies

- **SE-PRD-01:** `sar_e_automation_seeder` module + `/config/setup` transaction entry point. This PRD extends the seeder's two function bodies from stubs to real implementations.
- **DP-PRD-01 (Foundation):** `DataPipelineJob`, `DataPipelineRun`, `PipelineOutput` contracts; `POST /internal/data-pipeline/run` executes a job; the artifact ref returned includes GCS URI + `output_schema` metadata.
- **DP-PRD-02 (Google Analytics connector):** the four SAR-E-specific GA daily jobs exist. Each job's output is a deterministic Parquet artifact with shape `[{date: YYYY-MM-DD, value: float, weight?: float}]`. History-depth indicator on the job tells SAR-E how far back the connector can fetch (derived from the underlying GA property's data retention — typically 14 months for GA4 unless extended).
- **DP-PRD-03 (Task-system integration):** `TaskOrchestrator.on_task_due` has a `data_pipeline` branch that routes `assignee_type="data_pipeline"` tasks to `DataPipelineDispatcher`, which calls `POST /internal/data-pipeline/run`, waits for the run, and writes the resulting artifact as an upstream context for downstream tasks. SAR-E's ingestion automation graph uses this exact path.
- **Automations (A-PRD-01, A-PRD-02, A-PRD-03, A-PRD-04):** `is_system=true` plan lifecycle, recurring scheduler, `PlanRun` orchestration, artifact system. SAR-E's ingestion plan is built on top.
- **SE-PRD-01 audit helper:** `write_audit(...)` is already wired from SE-PRD-01; this PRD adds one new audit action `sar_e.ingest`.
- **Existing files to study:**
  - `api/src/kene_api/services/sar_e_automation_seeder.py` — stubs to extend
  - `app/adk/tools/data_pipeline_tool.py` (DP-PRD-03) — how Data Pipeline artifacts are referenced in ADK tool payloads
  - `api/src/kene_api/routers/automations.py` — existing `PlanRun` creation path; the one-shot backfill uses the same API
  - `api/src/kene_api/services/orchestrator.py` — `TaskOrchestrator.on_task_due` dispatch

## 4. Data contract

### 4.1 `KPIDataPoint` model

```python
class KPIDataPoint(BaseModel):
    account_id: str
    kpi_id: str
    week_start: date                                         # Monday of the ISO week, UTC
    value: float
    source_artifact_ids: list[str]                           # Data Pipeline run ids whose outputs fed this row
    ingested_at: datetime
    is_partial: bool = False                                 # true iff week was incomplete at aggregation time

    @property
    def doc_id(self) -> str:
        return f"{self.kpi_id}__{self.week_start.isoformat()}"
```

### 4.2 `/internal/sar-e/ingest-kpi-series` request + response

```python
class ArtifactRef(BaseModel):
    run_id: str                                              # DataPipelineRun.id
    kpi_id: str                                              # which KPI this artifact feeds (a run maps to one KPI)
    gcs_uri: str


class IngestRequest(BaseModel):
    account_id: str
    kpi_ids: list[str]                                       # the KPIs being processed (used for audit + validation)
    target_week_start: date                                  # Monday of the ISO week being written
    source_artifacts: list[ArtifactRef]


class KPIDataPointSummary(BaseModel):
    kpi_id: str
    week_start: date
    value: float
    is_partial: bool


class IngestResponse(BaseModel):
    written: int
    skipped: int                                             # rows where the value was unchanged from a previous ingest
    partial: int                                             # subset of `written` that were is_partial=true
    data_points: list[KPIDataPointSummary]
```

### 4.3 `/config/backfill-plan` request + response

```python
class BackfillPlanRequest(BaseModel):
    kpi_source_job_ids: list[str] = Field(..., min_length=4, max_length=4)


class BackfillPlanResponse(BaseModel):
    backfill_weeks: int                                      # min(104, min(per_source_depth values))
    limiting_source_job_id: str                              # the source_job_id whose depth drove the cap (may be ""
                                                             # if all sources had ≥104 weeks, i.e., cap is the hard limit)
    limiting_source_display_name: str
    per_source_depth: dict[str, int]                         # source_job_id → weeks_available
    below_recommended_minimum: bool                          # backfill_weeks < 26
```

### 4.4 Firestore layout additions (Shape B)

| Path | Purpose |
|---|---|
| `accounts/{account_id}/kpi_time_series/{kpi_id}__{week_start_iso}` | `KPIDataPoint` entries |

Composite index additions (Terraform):

- `kpi_time_series` collection-group — `(kpi_id ASC, week_start ASC)` for SE-PRD-03 training queries + SE-PRD-06 trendline queries
- `kpi_time_series` collection-group — `(kpi_id ASC, is_partial ASC, week_start ASC)` for "exclude partial weeks from VAR training"

Register `kpi_time_series` in `_migrate_shape_b/resources.py`.

## 5. Implementation outline

| Action | File |
|---|---|
| Modify | `api/src/kene_api/models/sar_e_models.py` — add `KPIDataPoint`, `ArtifactRef`, `IngestRequest`, `IngestResponse`, `BackfillPlanRequest`, `BackfillPlanResponse` |
| Create | `api/src/kene_api/services/sar_e_ingestion_service.py` — `write_weekly_data_point`, `aggregate_daily_to_weekly`, `fetch_and_parse_artifact` (Parquet → list of daily rows) |
| Create | `api/src/kene_api/routers/sar_e_ingestion.py` — `/internal/sar-e/ingest-kpi-series` endpoint (OIDC dependency), `/config/backfill-plan` endpoint |
| Modify | `api/src/kene_api/services/sar_e_automation_seeder.py` — flesh out `create_weekly_ingestion_automation` + `trigger_one_shot_backfill` (replace SE-PRD-01's stubs) |
| Modify | `api/src/kene_api/main.py` — mount `sar_e_ingestion.router` (both routes live in one file — internal + wizard-facing) |
| Modify | `api/src/_migrate_shape_b/resources.py` — register `kpi_time_series` |
| Modify | `deployment/terraform/firestore-indexes.tf` — add the two composite indexes from §4.4 |
| Create | `api/tests/unit/test_sar_e_aggregation.py` — aggregation math (sum / mean / weighted_mean / edge cases) |
| Create | `api/tests/unit/test_sar_e_ingestion_service.py` — upsert idempotency, partial-week handling |
| Create | `api/tests/integration/test_sar_e_ingest_endpoint.py` — happy path + partial-week + idempotency |
| Create | `api/tests/integration/test_sar_e_backfill_plan.py` — history-depth probe contract |
| Create | `api/tests/integration/test_sar_e_weekly_automation.py` — creates an automation, simulates a Monday run, asserts 4 weekly rows written |
| Create | `api/tests/integration/test_sar_e_backfill_run.py` — one-shot backfill plan executes end-to-end against seeded DP fixtures; asserts N×4 rows written |

### 5.1 Weekly ingestion automation task graph

`create_weekly_ingestion_automation(account_id, kpi_ids)` composes:

```
Plan: "SAR-E Weekly KPI Ingestion"
  is_system: true
  recurrence: 0 7 * * 1 UTC
  tasks:
    extract_task[i]  for each kpi_id in kpi_ids:
      assignee_type: "data_pipeline"
      pipeline_spec:
        job_id: <EffectivenessKPI.source_job_id>
        inputs:
          date_start: {macros.previous_iso_week_start}
          date_end:   {macros.previous_iso_week_end}
        account_id: {account_id}
      due_date: {macros.run_date}

    ingest_task:
      assignee_type: "agent"
      agent_name: "sar_e_ingestion"      # ADK function-tool-only agent; stub below
      depends_on: [extract_task[0], ..., extract_task[N-1]]
      context:
        target_week_start: {macros.previous_iso_week_start}
        account_id:        {account_id}
        kpi_ids:           {kpi_ids}
```

The `sar_e_ingestion` agent is a single-tool ADK agent registered in `agent_configs/sar_e_ingestion` with one function tool that calls `POST /internal/sar-e/ingest-kpi-series` with the upstream task artifacts. No LLM reasoning — it's a deterministic glue agent. (Alternatively, the orchestrator could fire the internal endpoint directly without routing through an agent; the agent route preserves the Artifact-system + Weave-tracing + revision-loop contracts that DP-PRD-03 / A-PRD-03 already standardize on. Confirm with the Agentic Harness team at kickoff whether this agent can be elided in favor of a direct orchestrator call.)

The `{macros.previous_iso_week_start}` / `{macros.previous_iso_week_end}` substitution relies on A-PRD-02's `{inputs.*}` pattern extended with time macros; if A-PRD-02 ships without them, compute at plan-clone time in the seeder.

### 5.2 One-shot backfill plan

`trigger_one_shot_backfill(account_id, kpi_ids, weeks)` composes one Plan with `weeks` sequential weekly sub-sections — each sub-section is an `extract_task` per KPI + a shared `ingest_task`. The sub-sections run in parallel where possible (Data Pipeline is rate-limited per connector; each weekly extract is an independent API call).

```
Plan: "SAR-E Initial Backfill"
  is_system: true
  recurrence: null                              # one-shot
  tasks:
    for week w in [target_week - weeks, ..., target_week - 1]:
      extract_task[w][i] for each kpi_id in kpi_ids:
        ...same as weekly ingest...
      ingest_task[w]:
        assignee_type: "agent"
        agent_name: "sar_e_ingestion"
        depends_on: [extract_task[w][0], ..., extract_task[w][N-1]]
        context:
          target_week_start: {macros.week_w_start}
          ...
```

Back-pressure: Data Pipeline's per-connector rate limits cap the total run duration. The plan is expected to complete within minutes-to-hours depending on account size; users do not need to wait synchronously. PE-PRD-05 redirects to `/performance/analysis` on `setup_wizard_completed=true` and the Analysis tab surfaces a "backfill in progress" banner (PE-PRD-02 §5.X) until the final ingest-task completes.

### 5.3 Partial-week handling

Let `target_week_start = Monday of the ISO week being ingested`, `target_week_end = target_week_start + 6 days`, `today = UTC today`:

- If `today > target_week_end` → the week is complete. Aggregate all 7 daily rows, write `is_partial=false`.
- If `today <= target_week_end` → the week is in progress. Aggregate the daily rows available (usually 1–6 rows), write `is_partial=true`. SE-PRD-03's VAR trainer excludes these; SE-PRD-06's trendline includes them with a visual marker.
- On a subsequent ingest for the same `(kpi_id, week_start)` once the week is complete, `set(..., merge=False)` overwrites the partial row with the final `is_partial=false` row atomically.

Source-artifact provenance: `source_artifact_ids` is the list of `DataPipelineRun.id`s whose Parquet outputs were read. When the week is re-ingested (partial → complete), the list is replaced with the new superset — we do not retain a chain of prior artifacts, since the compound id already identifies the aggregation target uniquely.

### 5.4 Channel Coverage integration point

The ingestion service notes, per week, which channels produced non-zero rows. This is the raw signal `ChannelCoverage` population logic will consume. **This PRD does not populate `ChannelCoverage`** — it only emits a structured log entry (`sar_e.ingest.channel_signal`) with `{account_id, week_start, channels_with_data: list[str]}`. SE-PRD-06 (or a follow-up admin tool) decides how to roll those signals into the coverage matrix. The decision is flagged in implementation-plan §10 open questions ("Channel Coverage population: who writes?"). This PRD punts the roll-up to keep scope tight; it does guarantee the signal is emitted.

### 5.5 Backfill-plan endpoint caching

The wizard's Step 3 calls `/config/backfill-plan` when the user lands on the step. The user may back-nav to Step 2, swap a KPI, and return — triggering a second call. Data Pipeline's `/jobs/{id}/history-depth` is not free (may hit the connector's API to discover retention). A 5-minute in-process LRU cache on `(account_id, source_job_id)` is sufficient; no Redis.

```python
@ttl_lru_cache(ttl_seconds=300, maxsize=1024)
def _cached_history_depth(account_id: str, source_job_id: str) -> int:
    return data_pipeline_client.get_history_depth(account_id, source_job_id)
```

Implement `ttl_lru_cache` as a small wrapper in `api/src/kene_api/utils/caching.py`.

## 6. API contract (owned here)

| Method | Path | Purpose | Role |
|---|---|---|---|
| `POST` | `/api/v1/internal/sar-e/ingest-kpi-series` | Ingest a week's aggregated values. OIDC-authed (called by the `sar_e_ingestion` agent from within the automation); not reachable from the public API gateway. | internal |
| `POST` | `/api/v1/sar-e/{account_id}/config/backfill-plan` | Pre-submit probe for the wizard's Step 3 — computes `backfill_weeks`. Role: editor (wizard callers are editors; super-admins bypass). | editor |

## 7. Acceptance criteria

1. **Weekly automation exists post-setup.** After `POST /config/setup` completes (SE-PRD-01), querying the Automations API for `is_system=true` plans on the account returns exactly one "SAR-E Weekly KPI Ingestion" plan with `recurrence=0 7 * * 1 UTC` and a task graph containing N Data Pipeline extraction tasks (one per KPI) + 1 agent-ingest final task. The stub graph from SE-PRD-01 has been replaced by this PRD.
2. **Weekly ingestion writes 1 row per KPI per week.** Given a test fixture with 7 days of daily rows for a given `kpi_id` across 4 KPIs, firing the ingestion endpoint for the target week writes exactly 4 `KPIDataPoint` docs at `accounts/{id}/kpi_time_series/{kpi_id}__{week_start}`. Each row's `value` matches the KPI's `aggregation` applied to the 7 daily values.
3. **Idempotency.** Firing `/internal/sar-e/ingest-kpi-series` twice with identical payloads produces no change on the second call (`IngestResponse.written=0, skipped=4`) and leaves Firestore state byte-identical.
4. **Partial-week flag.** Firing for a target week where `today <= target_week_end`: `is_partial=true`; firing again after the week completes: row overwritten, `is_partial=false`, compound doc id unchanged, `source_artifact_ids` reflects the full-week artifacts.
5. **Aggregation variants.**
   - `sum`: 7 daily values `[1, 2, 3, 4, 5, 6, 7]` → weekly value `28`
   - `mean`: same input → `4.0`
   - `weighted_mean` with weights `[1, 1, 1, 1, 1, 1, 1]` → `4.0`; weights `[7, 1, 1, 1, 1, 1, 1]` + same values → `(1*7 + 2+3+4+5+6+7) / (7+1+1+1+1+1+1) = 34/13 ≈ 2.615`
   - `weighted_mean` with `sum(weights) == 0` → the endpoint returns a 422 with `kpi_id`-scoped error (no silent divide-by-zero)
6. **Null-day handling.** If a day is missing from the Data Pipeline artifact (connector reported no rows), the aggregation skips it (doesn't treat missing as zero); the written row's `source_artifact_ids` still lists the underlying runs. `is_partial=true` regardless of calendar completeness — "present but missing-day" is an incomplete week.
7. **`/config/backfill-plan` computes min.** Given 4 `source_job_id`s with `history-depth` of `104`, `80`, `52`, `26` weeks respectively, the endpoint returns `{backfill_weeks: 26, limiting_source_job_id: <26-week id>, limiting_source_display_name: <that job's display_name>, per_source_depth: {...}, below_recommended_minimum: false}`.
8. **`/config/backfill-plan` min-hit cap.** Given 4 sources with depths `200, 150, 120, 108`, the endpoint returns `backfill_weeks=104, limiting_source_job_id=""` (empty — the cap won, not a particular source).
9. **`/config/backfill-plan` warning on shallow history.** Given 4 sources where the min is `10`, returns `backfill_weeks=10, below_recommended_minimum=true` and a warning log line; does not fail.
10. **`/config/backfill-plan` caches within 5 minutes.** Calling the endpoint twice within 5 minutes with the same payload produces only one Data Pipeline `history-depth` call per source (asserted via mock call count).
11. **One-shot backfill plan creates N weeks.** After `/config/setup` kicks off the backfill with `initial_backfill_weeks=52`, the backfill `PlanRun` executes to completion and produces exactly `52 × len(kpi_ids)` `KPIDataPoint` rows.
12. **Backfill plan handles per-KPI depth differences.** When one KPI's source has 80 weeks of history and another has only 26, the backfill is scoped to `min(52, 26) = 26` weeks **per KPI** — the plan runs 26 weekly sub-sections, each producing rows for all 4 KPIs. (Expected behavior, because the wizard already clamped `initial_backfill_weeks` via `/config/backfill-plan` — this AC guards against regression if a future caller skips the probe.)
13. **OIDC gate.** `POST /internal/sar-e/ingest-kpi-series` without an OIDC token returns `401`; with a token minted for a different service principal than the agent's returns `403`.
14. **Audit trail.** Every ingest call writes `sar_e.ingest` audit entry with `{account_id, kpi_ids, target_week_start, written, skipped, partial}` (no PII; summary counts only).
15. **Channel-signal log emission.** Each ingest call emits a `sar_e.ingest.channel_signal` structured log line with `{account_id, week_start, channels_with_data}`. No Firestore write in this PRD — consumers roll it up separately.
16. **Shape B registration.** `kpi_time_series` appears in `_migrate_shape_b/resources.py`; the two composite indexes exist in `deployment/terraform/firestore-indexes.tf`.
17. **Account deletion.** Deleting an account removes all `kpi_time_series/*` rows (covered by the enumerated sweep extension from SE-PRD-01 or by DM-PRD-05's `recursive_delete`).
18. **Lint + tooling gates.** `make lint`, `mypy`, `ruff`, `codespell` clean.

## 8. Test plan

**Unit tests — aggregation** (`test_sar_e_aggregation.py`):
- All three aggregation types with fixed 7-day inputs
- `weighted_mean` with zero-sum weights → raises a typed error
- Null-day inputs (missing dates) → skipped in computation, `is_partial` is set by the caller
- Single-day "week" (backfill of a week with 1 day of data only) → `is_partial=true`, value is the single day's value

**Unit tests — ingestion service** (`test_sar_e_ingestion_service.py`):
- `write_weekly_data_point` with fresh id writes a new doc
- Same call twice: second is a no-op (idempotent)
- Partial → complete transition overwrites the row; compound doc id unchanged

**Integration tests — ingest endpoint** (`test_sar_e_ingest_endpoint.py`):
- Happy path: 4 KPIs × 7 daily rows → 4 `KPIDataPoint` rows written
- Idempotency: repeat the call, assert 0 writes on second call
- Partial-week: `target_week_start = current ISO week Monday`, artifacts cover 4 days → 1 row per KPI with `is_partial=true`
- Partial → complete: after first partial call, feed a second call with the same week now complete → row overwritten, `is_partial=false`
- OIDC: no token → 401; wrong audience → 403

**Integration tests — backfill-plan endpoint** (`test_sar_e_backfill_plan.py`):
- 4 sources with depths `104 / 80 / 52 / 26` → response as in AC #7
- 4 sources all `≥104` → `limiting_source_job_id=""`
- Below-recommended: min depth `10` → `below_recommended_minimum=true`
- Caching: mock Data Pipeline; call twice in 5 minutes → only one call per source
- Not enough sources supplied (3 instead of 4) → 422 validation error

**Integration tests — weekly automation** (`test_sar_e_weekly_automation.py`):
- Complete `/config/setup` → fetch the seeded `is_system=true` plan → assert task count + recurrence
- Simulate a Monday run: manually trigger the PlanRun for the prior week → assert 4 `KPIDataPoint` rows appear post-run

**Integration tests — backfill execution** (`test_sar_e_backfill_run.py`):
- Seed 52 weeks of daily DP fixtures for 4 KPIs → run backfill → assert 52 × 4 = 208 rows in `kpi_time_series`
- Per-KPI depth mismatch: 4 KPIs with per-source depths `52 / 52 / 52 / 26` → backfill runs 26 weeks → assert 26 × 4 = 104 rows
- Idempotency: re-run the same backfill plan → 0 new rows (all existing rows upserted-unchanged)

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| **DP artifact format variance.** Different connectors may emit different schemas; the ingestion service's Parquet parser has to tolerate schema drift. | DP-PRD-02 standardizes the `[{date, value, weight?}]` shape for all SAR-E-feeding jobs. If a non-SAR-E job is ever wired (unlikely), the validator at KPI-creation time (SE-PRD-01 §6.4) would have rejected it. Ingest asserts the shape on parse and 422s on drift. |
| **Partial-week race at Monday 00:00 UTC.** The weekly cron fires at Monday 07:00 UTC; if a user is in a west-of-UTC timezone, "last week" locally may not yet be complete. | We always treat ISO weeks in UTC (implementation plan §1 invariant). `week_end = week_start + 6 days` — the cron at Monday 07:00 UTC is 7 hours after week_end; safe. If a connector is still catching up at ingestion time, the written row is `is_partial=false` with the best available data; next week's ingestion does not revisit it. (Re-ingest of a stale week is an explicit admin action — out of scope for v1.) |
| **DP job retries stretch past the 07:00 window.** A slow GA extract could cause the ingest-task to fire before all extract-tasks complete. | The `TaskOrchestrator` waits on `depends_on`; the ingest-task doesn't fire until all extracts are done (DP-PRD-03 contract). If the chain exceeds 24h, the plan surfaces as overdue in the Automations UI (A-PRD-06). SAR-E does not paper over DP reliability issues. |
| **Backfill plan explodes task count.** 104 weeks × 4 KPIs = 416 extract tasks + 104 ingest tasks ≈ 520 total. | A-PRD-07's 1k-automation perf test covers similar scale. The plan is `is_system=true` so it doesn't pollute the user's Automations list. Each task is small; total runtime bounded by DP rate limits. |
| **`weighted_mean` without a weight column.** KPI created pre-SE-PRD-01-validator; or a DP job that drops the weight column post-creation. | SE-PRD-01's validator at KPI create/edit rejects the combination. Ingest-time assertion: `aggregation=="weighted_mean"` requires `weight` present in every daily row; otherwise 422. Existing KPIs grandfathered via a migration step (none at v1). |
| **Artifact fetch cost.** 4 GCS reads per week per account, run weekly — modest. One-shot backfill of 104 weeks × 4 KPIs = 416 GCS reads per account bootstrap — still modest at 10KB per Parquet artifact. | No concern. Artifacts are already on GCS with 30-day lifecycle (A-PRD-03); SAR-E reads them within that window. |
| **`sar_e_ingestion` glue agent adds complexity.** Could call the internal endpoint directly from the orchestrator. | Flagged in §5.1 as a kickoff decision. The agent route preserves Weave span structure + artifact-write semantics from A-PRD-03; direct call would require SAR-E to re-implement those contracts. Recommend keeping the agent. |
| **`backfill-plan` cache invalidation on disconnect.** If the user disconnects GA after the probe succeeds, the cached depth is stale. | 5-minute TTL caps exposure. The `/config/setup` call itself re-queries (the cache is in the probe path only); if the final depth differs, the backfill is scoped appropriately at plan time. Tolerable. |

### Open questions

1. **Should ingestion support delta-aware re-ingest (only fetch new days)?** v1: no — always re-fetches the full 7-day window. Bandwidth is modest. Revisit if connector rate limits become a bottleneck.
2. **Channel Coverage population owner.** Flagged in implementation-plan §10. This PRD emits the signal; SE-PRD-06 or an admin tool (future) rolls it into `ChannelCoverage`. Default first-pass: SE-PRD-06 writes a simple rule — `has_data=true iff any ingest for the week saw the channel non-zero at least once`.
3. **Should the glue agent be a real `LlmAgent` or a `FunctionTool`-only agent?** Likely function-tool-only (no LLM); confirm with the Agentic Harness team at kickoff.
4. **`macros.previous_iso_week_start` substitution.** Depends on A-PRD-02's input-substitution extension. If not available, SAR-E's seeder computes it at plan-clone time (the orchestrator already supports runtime-computed inputs — see A-PRD-02 §X).

## 10. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md) §6 SE-PRD-02
- Upstream: [SE-PRD-01](./SE-PRD-01-configuration-foundation.md), [DP-PRD-01](../../data-pipeline/projects/DP-PRD-01-foundation.md), [DP-PRD-02](../../data-pipeline/projects/DP-PRD-02-google-analytics-connector.md), [DP-PRD-03](../../data-pipeline/projects/DP-PRD-03-task-system-integration.md)
- Downstream: [SE-PRD-03](./SE-PRD-03-var-baseline.md), [SE-PRD-06](./SE-PRD-06-analytical-query-layer.md), [PE-PRD-05](../../performance/projects/PE-PRD-05-setup-wizard.md)
- Automations platform: [A-PRD-01](../../automations/projects/A-PRD-01-data-model-and-api-extensions.md), [A-PRD-02](../../automations/projects/A-PRD-02-recurring-scheduler-and-run-engine.md), [A-PRD-03](../../automations/projects/A-PRD-03-task-artifact-system.md)
- CLAUDE.md rules in scope: PY-1, PY-2, PY-3, PY-5, PY-7; C-1, C-2, C-4; D-1, D-2, D-5; T-1, T-3, T-4, T-5, T-6, T-7, T-8; G-1
