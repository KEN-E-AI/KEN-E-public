# DP-PRD-03 — Task-System Integration

**Status:** Draft — ready to start once DP-PRD-02, PR-PRD-04, A-PRD-03, and A-PRD-04 ship
**Owner team:** Backend (Data Pipeline + Project Tasks)
**Blocked by:** DP-PRD-02 (needs a real connector to run an end-to-end task); PR-PRD-04 (`TaskOrchestrator` surface — dispatch branch is added here); A-PRD-03 (`TaskArtifact` write path — pipeline output is persisted through it); A-PRD-04 (`is_test` flag on `TaskOrchestrator` — honored here per `DataPipelineJob.test_mode_policy`)
**Blocks:** DP-PRD-04 (frontend depends on a functional end-to-end pipeline task); DP-PRD-06 (integration testing closes over this surface); SE-PRD-02 (SAR-E weekly ingestion automation dispatches through this branch)
**Estimated effort:** 3–4 days

---

## 1. Context

DP-PRD-01 built the execution substrate. DP-PRD-02 shipped the first real connector. Neither wired the Data Pipeline into the `TaskOrchestrator` — today, nothing in the project-tasks runtime knows how to route a `PlanTask` through the Data Pipeline. A user cannot compose a plan whose first task pulls GA data and whose second task reasons over it; the two systems are still disjoint.

This PRD closes that gap. It extends `PlanTask.assignee_type` from `Literal["agent", "human"]` to `Literal["agent", "human", "data_pipeline"]` and introduces a sibling `pipeline_spec: PipelineJobSpec | None` field (PR-PRD-01 patch). It adds a `data_pipeline` branch to `TaskOrchestrator.on_task_due` and `on_task_status_change` (PR-PRD-04 patch) that HTTP-calls `POST /api/v1/internal/data-pipeline/run` fire-and-forget with a 10-minute cap. It writes the pipeline output as a `TaskArtifact` via A-PRD-03 so a downstream agent task sees it as upstream context (A-PRD-03's prompt-injection helper consumes the same artifact system). It disables the revision loop on pipeline tasks (deterministic output — nothing to revise). And it honors the `is_test` flag per job (A-PRD-04) using each job's `test_mode_policy` — `run_normally` (the default, used by every SAR-E daily job), `sandbox_endpoint` (future write-capable jobs opt in), or `fail_not_testable`.

The exit criterion is narrow: a one-shot plan with a pipeline task + a downstream agent task activates; the pipeline task runs; a `TaskArtifact` is written; the agent task sees it as upstream context.

What this PRD is **not:** any new connector (DP-PRD-02 owns GA; DP-PRD-05 owns Ads/Meta/Mailchimp); any frontend — the `ProjectEditDrawer` "Data Pipeline" assignee option, the `PipelineJobPicker`, the schema-driven input form, and the run viewer are DP-PRD-04's scope.

## 2. Scope

### In scope

- `PlanTask.assignee_type` extended from `Literal["agent", "human"]` to `Literal["agent", "human", "data_pipeline"]` (PR-PRD-01 patch); new `pipeline_spec: PipelineJobSpec | None` field on `PlanTask`
- Pydantic validator: when `assignee_type == "data_pipeline"`, `pipeline_spec` MUST be non-null AND `agent_id` / `assignee_email` MUST be null; inverse checks on the other branches
- DAG validator unchanged — `depends_on` wiring works the same for pipeline tasks as for agent tasks
- `DataPipelineDispatcher` service — thin HTTP client that bridges orchestrator → sibling Cloud Run service; handles OIDC auth, timeout enforcement (10-min cap matches DP-PRD-01), and the PATCH-back on completion
- `TaskOrchestrator.on_task_due` gains a `data_pipeline` branch: resolves the task's `pipeline_spec`, applies `{inputs.*}` substitution (reusing A-PRD-02's helper), dispatches via `DataPipelineDispatcher`, enters the `running` waiting state
- `TaskOrchestrator.on_task_status_change` — on `Complete` from the data-pipeline branch, unblocks downstream tasks the same way agent completion does; on `Failed`, marks the task failed, notifies the owner, halts dependent branches (same semantics as a failed agent task)
- Revision loop **disabled** for pipeline tasks: `POST /plans/.../tasks/{task_id}/revision` on a pipeline task returns `409 Conflict` with `{"reason": "pipeline_tasks_are_deterministic"}`
- `TaskArtifact` write path: `DataPipelineDispatcher` calls A-PRD-03's artifact-write helper after a successful run to persist the `PipelineOutput` under the task's `output_artifact_name` (from `PipelineJobSpec`); the artifact's `created_by_agent` is set to `"data_pipeline:{job_id}"`
- Downstream prompt injection: A-PRD-03's prompt-builder already lists upstream artifacts for agent tasks; this PRD verifies that pipeline-produced artifacts appear in that list with their signed URL and filename (no code change to A-PRD-03 required — the contract is satisfied by writing a conformant `TaskArtifact`)
- `is_test` honored per `DataPipelineJob.test_mode_policy` (from DP-PRD-01):
  - `run_normally` (default, all current jobs) — test runs execute the connector as usual and write a real `TaskArtifact`
  - `sandbox_endpoint` — future write-capable jobs route to a provider sandbox; out of band for v1 but the dispatch code honors the policy by setting a `use_sandbox=true` header on the internal run endpoint that `DataPipelineService` (DP-PRD-01) forwards to the connector
  - `fail_not_testable` — the orchestrator short-circuits the dispatch, marks the task `Skipped` with a human-readable reason, and continues the plan
- Notifications: on pipeline-task failure, emit an `"Integration Error"` notification with deep link to `/settings/integrations/{connection_id}` (reuses the category added in DP-PRD-02); on `integration_needs_reauth`, emit the `"Integration Needs Re-auth"` notification (from IN-PRD-05)
- Unit tests for the branch (mock `DataPipelineDispatcher`); integration tests with a `StubConnector`-backed job end-to-end
- `make lint` + `pytest` green

### Out of scope

- **Live connector behavior.** Tested via DP-PRD-02's GA connector; this PRD's assertion surface is the branch + artifact write, not the GA-specific path.
- **Frontend.** `ProjectEditDrawer`'s "Data Pipeline" assignee option, `PipelineJobPicker`, schema-driven input form, `ActivityDetailPanel` pipeline-run viewer — all DP-PRD-04.
- **Custom-job authoring UI.** DP-PRD-04.
- **Recurring automations containing pipeline tasks.** A-PRD-02's recurring scheduler already composes plans from templates; pipeline tasks ride that system unchanged because this PRD does not modify `PlanRun` at all. SE-PRD-02 exercises this path as part of its weekly ingestion automation.
- **Review-loop semantics.** Disabled per the resolved decision in the plan §10 ("Excluded from the review loop"); no behavior to design.
- **Cross-connector rate-limit coordination.** DP-PRD-02's per-connector limits apply; this PRD does not aggregate across connectors.

## 3. Dependencies

- **DP-PRD-02 (Google Analytics connector):** hard prerequisite. Needed so the end-to-end contract test pulls real GA data and writes a conformant `TaskArtifact`. Until DP-PRD-02 lands, the orchestrator would have only `StubConnector` to hit, which is fine for unit tests but not for the E2E acceptance criterion.
- **PR-PRD-04 (Event-Driven Orchestrator):** hard prerequisite. Publishes `TaskOrchestrator.on_task_due` and `on_task_status_change` — the two hooks extended here. The orchestrator already carries the `run_id` threading from A-PRD-02; this PRD adds the `data_pipeline` branch alongside the existing `agent` / `human` branches.
- **A-PRD-03 (Task Artifact System):** hard prerequisite. `TaskArtifact` + GCS bucket + signed-URL helper + prompt-builder integration. This PRD writes `TaskArtifact` docs but does not modify A-PRD-03's write path — it calls the helper as a consumer.
- **A-PRD-04 (Test / Dry-Run Mode):** hard prerequisite. Adds `is_test` threading to `TaskOrchestrator`. This PRD consumes that flag when resolving `test_mode_policy`.
- **PR-PRD-01 (Data Model & API):** hard prerequisite (already assumed by PR-PRD-04). This PRD patches `PlanTask` defined there — extension is additive (new optional field + new literal in the existing union).
- **IN-PRD-05 (Re-auth lifecycle):** soft dependency. The pipeline-task failure path cites the `"Integration Needs Re-auth"` notification category; if IN-PRD-05 has not merged, the orchestrator fires `"Integration Error"` and the reauth call is a no-op until IN-PRD-05 wires it up.
- **Existing files to study:**
  - `api/src/kene_api/services/task_orchestrator.py` (PR-PRD-04) — the dispatch switch where the `data_pipeline` branch is added
  - `api/src/kene_api/services/task_orchestrator_dispatch.py` (PR-PRD-04) — agent-dispatch helper; pipeline dispatch lives in a sibling file
  - `api/src/kene_api/services/automation_run_engine.py` (A-PRD-02) — `{inputs.*}` substitution helper reused here (or moved into a shared utility if not already)
  - `api/src/kene_api/services/artifact_service.py` (A-PRD-03) — `TaskArtifact` write path
  - `api/src/kene_api/models/project_plan_models.py` (PR-PRD-01) — `PlanTask` model to extend
  - `services/data_pipeline/src/kene_data_pipeline/models.py` (DP-PRD-01) — `PipelineJobSpec` to import
  - `api/src/kene_api/routers/project_plans.py` (PR-PRD-01) — `POST /tasks/{task_id}/revision` endpoint gets the 409 guard
  - `api/src/kene_api/services/notification_service_v2.py` — `create_notification` API
  - [`../implementation-plan.md`](../implementation-plan.md) §3.3 (execution model, test-mode policy), §6.1 (Project Tasks integration), §6.2 (Automations integration), §7 DP-PRD-03

## 4. Data contract

### 4.1 `PlanTask` extension (PR-PRD-01 patch)

```python
# api/src/kene_api/models/project_plan_models.py  (modified)

class PlanTask(BaseModel):
    # ... existing fields (task_id, title, description, depends_on, etc.)
    assignee_type: Literal["agent", "human", "data_pipeline"]   # extended
    assignee_name: str | None = None                            # legacy; still used for "agent" / "human"
    pipeline_spec: PipelineJobSpec | None = None                # NEW — required iff assignee_type=="data_pipeline"
    # ... existing status, depends_on, cost, due_date, launch_time_utc, launched_at, etc.
```

**Cross-field validator** (Pydantic `model_validator(mode="after")`):

```python
@model_validator(mode="after")
def _check_assignee_consistency(self) -> "PlanTask":
    if self.assignee_type == "data_pipeline":
        if self.pipeline_spec is None:
            raise ValueError("pipeline_spec required when assignee_type=='data_pipeline'")
        if self.assignee_name is not None:
            raise ValueError("assignee_name must be null for data_pipeline tasks")
    else:
        if self.pipeline_spec is not None:
            raise ValueError("pipeline_spec must be null for non-data_pipeline tasks")
    return self
```

The data-pipeline assignee is identified by `pipeline_spec.job_id` — **not** by `agent_id` or `assignee_email`. A pipeline task with an `assignee_name` set fails validation.

### 4.2 `PipelineJobSpec` (re-exported from DP-PRD-01)

```python
class PipelineJobSpec(BaseModel):
    job_id: str                      # FK to DataPipelineJob in global catalog or per-account overlay
    inputs: dict                     # validated at dispatch time
    output_artifact_name: str        # filename of the TaskArtifact written on success
```

Imported into `project_plan_models.py` from the shared module (or duplicated per DP-PRD-01's deploy-unit convention). `inputs` supports `{inputs.*}` substitution from the enclosing `PlanRun.inputs` in the same way agent prompts do (A-PRD-02 substitution helper).

### 4.3 `DataPipelineDispatcher` service (new)

```python
class DataPipelineDispatcher:
    """Bridges TaskOrchestrator -> sibling Cloud Run Data Pipeline service."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        service_url: str,                           # kene-data-pipeline-{env} base URL
        oidc_token_provider: Callable[[], Awaitable[str]],
        artifact_service: ArtifactService,          # A-PRD-03
        notification_service: NotificationService,
        orchestrator_ref: TaskOrchestrator,         # to report back on completion
    ) -> None: ...

    async def dispatch(
        self,
        account_id: str,
        plan_id: str,
        task_id: str,
        pipeline_spec: PipelineJobSpec,
        run_id: str | None,                         # PlanRun id when inside an automation
        is_test: bool,
    ) -> None: ...

    async def _on_pipeline_complete(
        self,
        account_id: str,
        plan_id: str,
        task_id: str,
        pipeline_run_id: str,
        output_artifact_name: str,
    ) -> None: ...
```

`dispatch` returns immediately (the run endpoint is fire-and-forget with its own 10-min cap). `_on_pipeline_complete` is invoked by the sibling service's PATCH-back on run completion; it:

1. Fetches the final `DataPipelineRun` record
2. On `succeeded` — reads the serialized `PipelineOutput` from GCS, writes a `TaskArtifact` via `artifact_service.create(...)` using `output_artifact_name` as `filename`, then calls `orchestrator.on_task_status_change(..., new_status="Complete")`
3. On `failed` — fires the right notification, then calls `orchestrator.on_task_status_change(..., new_status="Failed")`
4. On `cached` — same as `succeeded` but reuses the prior run's `output_artifact_id` (already linked by DP-PRD-01's cache-hit path)

### 4.4 Orchestrator branch extension (PR-PRD-04 patch)

```python
# api/src/kene_api/services/task_orchestrator.py  (modified)

class TaskOrchestrator:
    # ... existing fields
    dispatcher: DataPipelineDispatcher     # NEW injected dependency

    async def on_task_due(
        self,
        account_id: str,
        plan_id: str,
        task_id: str,
        run_id: str | None = None,
        is_test: bool = False,
    ) -> OrchestratorResult:
        task = await self._load_task(account_id, plan_id, task_id)
        if task.assignee_type == "data_pipeline":
            spec = self._resolve_pipeline_spec(task, run=run_id)   # applies {inputs.*} substitution
            policy = await self._job_test_mode_policy(spec.job_id, account_id)
            if is_test and policy == "fail_not_testable":
                await self._mark_task(task, status="Skipped", reason="not_testable_in_test_mode")
                return self._result_after(task, dispatched=False)
            await self.dispatcher.dispatch(
                account_id=account_id,
                plan_id=plan_id,
                task_id=task_id,
                pipeline_spec=spec,
                run_id=run_id,
                is_test=is_test,
            )
            # PATCH-back from sibling service will call on_task_status_change
            return self._result_after(task, dispatched=True)
        elif task.assignee_type == "agent":
            # ... existing agent branch
        elif task.assignee_type == "human":
            # ... existing human branch
```

`on_task_status_change` requires no new branch — the dispatcher calls it with `new_status="Complete"` / `"Failed"` / `"Skipped"` using the existing paths.

### 4.5 Revision-endpoint 409 guard (PR-PRD-01 + PR-PRD-04 patch)

```python
# api/src/kene_api/routers/project_plans.py  (modified)

@router.post("/{account_id}/{plan_id}/tasks/{task_id}/revision")
async def request_revision(...):
    task = await load_task(...)
    if task.assignee_type == "data_pipeline":
        raise HTTPException(
            status_code=409,
            detail={"reason": "pipeline_tasks_are_deterministic"},
        )
    # ... existing revision flow
```

### 4.6 Notification payloads (reused)

Pipeline-task failure emits existing categories; no new category in this PRD.

| Error class (from DP-PRD-02) | Category | `data` field |
|---|---|---|
| `semantic` | `"Integration Error"` | `{plan_id, task_id, job_id, error_message_sanitized, deep_link: "/calendar?project={plan_id}&task={task_id}"}` |
| `auth` | `"Integration Needs Re-auth"` (IN-PRD-05) | `{plan_id, task_id, connection_id, deep_link: "/settings/integrations/{connection_id}"}` |
| `transient_after_retry` | `"Integration Error"` | same shape as semantic |
| `timeout` | `"Integration Error"` | same shape |

## 5. Implementation outline

| Action | File |
|--------|------|
| Modify | `api/src/kene_api/models/project_plan_models.py` — extend `PlanTask.assignee_type` literal; add `pipeline_spec`; add cross-field validator |
| Create | `api/src/kene_api/services/data_pipeline_dispatcher.py` — `DataPipelineDispatcher` (HTTP client to sibling service + artifact write + orchestrator callback) |
| Modify | `api/src/kene_api/services/task_orchestrator.py` (PR-PRD-04) — add `data_pipeline` branch to `on_task_due`; accept dispatcher via dependency injection |
| Modify | `api/src/kene_api/routers/project_plans.py` (PR-PRD-01) — `POST .../tasks/{task_id}/revision` returns `409` on data-pipeline tasks |
| Modify | `api/src/kene_api/main.py` — register `DataPipelineDispatcher` dependency; wire into the orchestrator singleton |
| Modify | `services/data_pipeline/src/kene_data_pipeline/routers/internal.py` (DP-PRD-01) — on run completion, PATCH back to the main API's callback endpoint (see below) |
| Create | `api/src/kene_api/routers/internal/data_pipeline_callback.py` — OIDC-authed `POST /api/v1/internal/data-pipeline/callback` endpoint the sibling service calls to report completion; dispatches to `DataPipelineDispatcher._on_pipeline_complete` |
| Modify | `api/src/kene_api/models/data_pipeline_models.py` (from DP-PRD-01 main-API mirror) — ensure `PipelineJobSpec` is importable from `project_plan_models.py` |
| Create | `api/tests/unit/test_plan_task_pipeline_validator.py` |
| Create | `api/tests/unit/test_data_pipeline_dispatcher.py` |
| Create | `api/tests/unit/test_task_orchestrator_pipeline_branch.py` |
| Create | `api/tests/integration/test_pipeline_task_e2e.py` |
| Create | `api/tests/integration/test_revision_on_pipeline_task.py` |

### Orchestrator → sibling service → callback flow

```
User activates plan with pipeline task T1 + agent task T2 (T2 depends_on T1)
  │
  ▼
TaskOrchestrator.activate_plan
  └─ T1 ready: assignee_type="data_pipeline"
        on_task_due(T1, run_id=R, is_test=False)
          └─ dispatcher.dispatch(account, plan, T1, spec, run_id=R, is_test=False)
                └─ POST kene-data-pipeline-{env}/api/v1/internal/data-pipeline/run
                     body: {account_id, plan_id, task_id, job_id, inputs, is_test}
                     OIDC auth
              (returns 201 with run_id, fire-and-forget)
  │
  ...  DataPipelineService runs connector ...
  │
  ▼
Sibling service: run completes
  └─ POST kene-api-{env}/api/v1/internal/data-pipeline/callback
       body: {account_id, plan_id, task_id, run_id, status, output_gcs_uri}
       OIDC auth
       │
       ▼
  data_pipeline_callback router
    └─ dispatcher._on_pipeline_complete(...)
          ├─ read PipelineOutput from GCS
          ├─ artifact_service.create(TaskArtifact) using spec.output_artifact_name
          └─ orchestrator.on_task_status_change(T1, status="Complete")
                └─ T2 unblocked; dispatched as agent task
                      agent prompt includes T1's TaskArtifact (A-PRD-03 prompt-builder)
```

### `{inputs.*}` substitution

Reuses A-PRD-02's helper. When `PlanTask.pipeline_spec.inputs` contains `{"start_date": "{inputs.week_start}", "end_date": "{inputs.week_end}"}` and the enclosing `PlanRun.inputs == {"week_start": "2026-04-15", "week_end": "2026-04-21"}`, substitution resolves before dispatch so the sibling service receives `inputs == {"start_date": "2026-04-15", "end_date": "2026-04-21"}`.

Rules inherited from A-PRD-02:

- Two nesting levels max (`{inputs.user.id}` OK; `{inputs.a.b.c}` left literal)
- Missing keys → empty string + warning log
- Non-agent tasks normally don't participate in substitution; pipeline tasks participate because their inputs are structured analogous to agent prompts

### Callback endpoint spec

```
POST /api/v1/internal/data-pipeline/callback
Auth: OIDC (sibling service SA allowed)
Body:
{
  "account_id": "a_123",
  "plan_id": "p_456",
  "task_id": "t_789",
  "run_id": "r_abc",
  "pipeline_run_id": "dp_run_xyz",
  "status": "succeeded" | "failed" | "cached",
  "output_gcs_uri": "gs://kene-data-pipeline-artifacts-.../...",   // null on failure
  "error_class": "transient" | "semantic" | "auth" | "timeout" | null,
  "error_message_sanitized": "..." | null
}
Response: 204
```

### Test-mode policy resolution

```python
async def _job_test_mode_policy(job_id: str, account_id: str) -> str:
    job = await resolve_job(job_id, account_id)   # overlay > global
    return job.test_mode_policy                    # Literal["run_normally", "sandbox_endpoint", "fail_not_testable"]
```

| `is_test` | `test_mode_policy` | Behavior |
|---|---|---|
| `false` | any | Normal dispatch |
| `true` | `run_normally` | Normal dispatch, artifact written |
| `true` | `sandbox_endpoint` | Dispatch with `use_sandbox=true` forwarded to the connector (v1: DP-PRD-01 forwards the flag; no connector in v1 uses it) |
| `true` | `fail_not_testable` | Task set to `Skipped` with `completion_notes="not_testable_in_test_mode"`; downstream tasks continue per existing orphan-branch semantics |

## 6. API contract

### 6.1 Existing endpoints — modified behavior

**`POST /api/v1/plans/{account_id}` / `PUT /api/v1/plans/{account_id}/{plan_id}`** (from PR-PRD-01)

- Accepts `assignee_type="data_pipeline"` in `tasks[*]`. Requires `pipeline_spec` set; `assignee_name` must be null.
- Rejects with `422` if `pipeline_spec.job_id` does not resolve to any job in the global catalog or account overlay (reuses DP-PRD-01's resolver).
- Rejects with `422` if `pipeline_spec.inputs` fails the referenced `DataPipelineJob.input_schema` check at save time — except where `inputs` contains `{inputs.*}` templates (these bypass schema validation at save, re-validated at dispatch with substituted values).

**`POST /api/v1/plans/{account_id}/{plan_id}/tasks/{task_id}/revision`** (from PR-PRD-04)

- On a task where `assignee_type == "data_pipeline"`: returns `409 Conflict` with body `{"reason": "pipeline_tasks_are_deterministic"}`.

**`POST /api/v1/plans/{account_id}/{plan_id}/activate`** (from PR-PRD-04)

- Unchanged caller contract. Internally, root tasks with `assignee_type == "data_pipeline"` dispatch through `DataPipelineDispatcher` instead of `AgentEngineClient`.

### 6.2 New endpoint

**`POST /api/v1/internal/data-pipeline/callback`**

Owned by this PRD. OIDC-authed (sibling service SA). Invoked when a `DataPipelineRun` terminates (succeeded, failed, cached). Returns `204`.

**Error codes:**

| Code | Condition |
|---|---|
| `401` | Missing / invalid OIDC token |
| `403` | Caller SA is not `kene-data-pipeline-{env}` |
| `404` | Referenced `(account_id, plan_id, task_id)` does not exist — logged; no retry expected |
| `422` | `status` not in allowed set; `output_gcs_uri` set when `status="failed"` |
| `500` | Orchestrator callback raised; sibling service should retry per its own policy |

### 6.3 Consumption rules

- The callback endpoint is **strictly internal** — no user auth path. The sibling service at `kene-data-pipeline-{env}` is the only authorized caller.
- On a `succeeded` callback, the dispatcher reads the `PipelineOutput` from GCS once. If the GCS read fails, the dispatcher records the callback as `failed` with `error_message="artifact_read_failed"` and re-dispatches notification rather than crashing.
- Idempotency: a duplicate callback for the same `pipeline_run_id` is a no-op — the `TaskArtifact` write is guarded by `artifact_service.create(...)` returning the existing artifact when the content-hash matches, and `on_task_status_change` is idempotent per PR-PRD-04's acceptance criterion 9.

## 7. Acceptance criteria

1. A `PlanTask` with `assignee_type="data_pipeline"` and a valid `pipeline_spec` (job_id, inputs, output_artifact_name) passes Pydantic validation.
2. A `PlanTask` with `assignee_type="data_pipeline"` and `pipeline_spec=None` raises `ValueError` at model construction; error message identifies the missing field.
3. A `PlanTask` with `assignee_type="data_pipeline"` AND `assignee_name="some-agent"` set raises `ValueError` at model construction; error message flags the incompatible fields.
4. A `PlanTask` with `assignee_type="agent"` AND `pipeline_spec` set raises `ValueError`.
5. `POST /api/v1/plans/{account_id}` with a task whose `pipeline_spec.job_id` does not resolve returns `422` naming the offending `job_id`.
6. Activating a plan with a root `data_pipeline` task causes `DataPipelineDispatcher.dispatch` to be called exactly once with the resolved `PipelineJobSpec`, `is_test=False`, and the current `run_id` (if the plan is part of a `PlanRun`).
7. On a successful pipeline run, the callback endpoint writes a `TaskArtifact` with `filename == pipeline_spec.output_artifact_name` and `created_by_agent == f"data_pipeline:{pipeline_spec.job_id}"`; the downstream agent task's dispatch prompt lists that artifact in its upstream-artifact section (A-PRD-03 contract — verified by observing the prompt in the test).
8. On a `failed` callback with `error_class="semantic"`, the task moves to `Failed`, a notification of category `"Integration Error"` is created, and transitively-downstream tasks are blocked (existing PR-PRD-04 semantics).
9. On a `failed` callback with `error_class="auth"`, the task moves to `Failed` and a notification of category `"Integration Needs Re-auth"` is created (if IN-PRD-05 has merged; otherwise `"Integration Error"` is used and a TODO log is emitted).
10. `POST /api/v1/plans/{account_id}/{plan_id}/tasks/{task_id}/revision` on a data-pipeline task returns `409` with body `{"reason": "pipeline_tasks_are_deterministic"}`; a revision request on an adjacent agent task within the same plan is unaffected.
11. `is_test=True` on a task whose job has `test_mode_policy="run_normally"` dispatches normally and writes a real `TaskArtifact` (honors plan §3.3 "pipeline tasks run normally under `is_test=true`"). Verified with all SAR-E daily jobs.
12. `is_test=True` on a task whose job has `test_mode_policy="fail_not_testable"` sets the task to `Skipped` (no dispatch, no artifact) and allows downstream tasks to proceed per orphan-branch semantics; the sibling service is not invoked.
13. `is_test=True` on a task whose job has `test_mode_policy="sandbox_endpoint"` dispatches with `use_sandbox=true` forwarded to the internal run endpoint; the internal endpoint receives the flag (verified via a mock of the sibling service).
14. End-to-end contract test: activate a one-shot plan with a `StubConnector`-backed pipeline task T1 + an agent task T2 with `depends_on=[T1]`; T1 runs, `TaskArtifact` is written, T2 is dispatched and its prompt contains the T1 artifact's signed URL.
15. Cross-account isolation: account A activating a plan with a pipeline task does not cause any `DataPipelineRun` writes under account B (Firestore assertion).
16. Weave span: the `data_pipeline.run` span emitted by the sibling service (DP-PRD-02) carries the right `test_mode` value (`true` when the task was dispatched with `is_test=true`; `false` otherwise) — asserted end-to-end by the integration test.
17. `make lint` passes (**G-1**) and `pytest api/tests/ services/data_pipeline/tests/` passes green on CI.

## 8. Test plan

**Unit tests** (`api/tests/unit/`):

- `test_plan_task_pipeline_validator.py`
  - Happy path: `assignee_type="data_pipeline"` + valid `pipeline_spec` → valid
  - `assignee_type="data_pipeline"` + `pipeline_spec=None` → `ValidationError`
  - `assignee_type="data_pipeline"` + `pipeline_spec` valid + `assignee_name="x"` → `ValidationError`
  - `assignee_type="agent"` + `pipeline_spec` set → `ValidationError`
  - `assignee_type="human"` + `pipeline_spec` set → `ValidationError`
  - Existing agent / human branches continue to work unchanged
  - DAG validator unchanged: a pipeline task in `depends_on` chains works like agent/human

- `test_data_pipeline_dispatcher.py`
  - `dispatch` posts the right JSON body to the sibling service URL; OIDC token attached
  - Sibling-service 2xx → dispatcher returns (fire-and-forget)
  - Sibling-service 5xx on first call → surfaces the error (callback flow never runs); orchestrator marks task `Failed` with `transient_after_retry` message
  - `_on_pipeline_complete` on `succeeded`: reads GCS, writes `TaskArtifact` with correct `filename` + `created_by_agent`, calls `on_task_status_change(..., "Complete")`
  - `_on_pipeline_complete` on `failed` with `error_class="auth"`: creates `"Integration Needs Re-auth"` notification, calls `on_task_status_change(..., "Failed")`
  - `_on_pipeline_complete` on `cached`: reuses prior artifact id; no new GCS read; calls `on_task_status_change(..., "Complete")`
  - Duplicate callback for the same `pipeline_run_id` → idempotent no-op

- `test_task_orchestrator_pipeline_branch.py`
  - `on_task_due` on a data-pipeline task calls `dispatcher.dispatch` once with the substituted spec
  - `{inputs.*}` substitution: `pipeline_spec.inputs={"start_date": "{inputs.week_start}"}` + `PlanRun.inputs={"week_start": "2026-04-15"}` → dispatched inputs `{"start_date": "2026-04-15"}`
  - `is_test=True` + `test_mode_policy="run_normally"` → dispatch proceeds with `is_test=true` flag set
  - `is_test=True` + `test_mode_policy="fail_not_testable"` → task set to `Skipped`, `dispatcher.dispatch` NOT called
  - `is_test=True` + `test_mode_policy="sandbox_endpoint"` → dispatch proceeds with `use_sandbox=true`

**Integration tests** (`api/tests/integration/`):

- `test_pipeline_task_e2e.py`
  - Seed global catalog with a `StubConnector`-backed job `stub.echo`. Create a plan with T1 (`assignee_type="data_pipeline"`, `job_id="stub.echo"`, `output_artifact_name="stub_output.parquet"`) and T2 (`assignee_type="agent"`, `depends_on=[T1]`). Activate the plan. Assert:
    - T1 transitions `Draft → Running → Complete` within 5s
    - `TaskArtifact` exists at `accounts/{account_id}/plan_runs/{run_id}/artifacts/<id>` with the expected `filename` and `created_by_agent`
    - T2 is dispatched; its mock agent prompt contains the T1 artifact's signed URL
  - Same scenario with an artificially-slow `StubConnector` (sleep 2s) → behavior identical
  - Cross-account isolation: account A's activation writes no runs under account B
  - Weave span shape asserted end-to-end

- `test_revision_on_pipeline_task.py`
  - `POST /tasks/{task_id}/revision` on a pipeline task returns `409` with body `{"reason": "pipeline_tasks_are_deterministic"}`
  - Same endpoint on a sibling agent task within the same plan returns `200` (existing behavior preserved)

**E2E** (deferred to DP-PRD-06): full trace through DP-PRD-02's GA connector — pipeline task pulls real GA data, artifact is written, downstream analysis agent reads it.

## 9. Risks & open questions

### Resolved decisions

| Decision | Resolution |
|---|---|
| Data-pipeline assignee field | **`pipeline_spec: PipelineJobSpec`** — not `agent_id`, not `assignee_email`. Plan §3.1. |
| Revision loop for pipeline tasks | **Disabled** — pipelines are deterministic; revision is meaningless. `409` on the revision endpoint. Plan §10 resolved decisions. |
| Test-mode behavior | **`run_normally` by default** per `DataPipelineJob.test_mode_policy`. Side-effect suppression happens at side-effecting tasks, not extraction tasks. Plan §3.3 + §6.2. |
| Artifact write path | **Via A-PRD-03's `artifact_service.create()`** — no new GCS bucket, no new lifecycle rules. Pipeline-written artifacts are indistinguishable from agent-written artifacts downstream. |
| Orchestrator → sibling service transport | **HTTP + OIDC, fire-and-forget with 10-min cap.** Matches PR-PRD-06 / A-PRD-02 pattern. Plan §3.3. |
| Callback-endpoint ownership | **Main API** — sibling service PATCHes back here. Keeps Firestore writes on the main API path for consistency with existing observability + audit. |
| Cross-field validation on `PlanTask` | **Pydantic `model_validator(mode="after")`** rejects inconsistent combinations at model construction time (before any request body hits Firestore). |
| `{inputs.*}` substitution in pipeline inputs | **Yes** — reuses A-PRD-02's helper; applied at dispatch time, not at plan-save time (so save-time schema validation tolerates template markers). Plan §6.2. |
| Failure notifications | **Existing `"Integration Error"` + `"Integration Needs Re-auth"` categories** — no new notification categories in this PRD; `"Data Pipeline Rate Limit"` from DP-PRD-02 handles the rate-limit case. |

### Remaining open questions

| Question | Disposition |
|---|---|
| When a plan is saved with `{inputs.*}` markers in `pipeline_spec.inputs`, how strict is save-time schema validation? | First pass: validate the **structural** schema (keys match `input_schema.required`) and defer value-type validation to dispatch time after substitution. CONFIRM during implementation review — if users hit confusing runtime failures we tighten save-time checks by type-matching the template marker shape. |
| Should a pipeline task carry its own `revision_comment` field even if the endpoint is gated? | No — revision is disabled; the field stays off the pipeline branch. If a future PRD introduces agent-driven recovery (`../backlog/pipeline-error-recovery-specialist.md`), it adds its own field. |
| Ordering guarantee when the orchestrator dispatches a pipeline task and its `on_task_due` and the sibling-service callback race | The dispatch is fire-and-forget; the callback is idempotent per acceptance criterion and can arrive before `dispatch` returns. Firestore transactions on the task doc guard state transitions — same invariant as PR-PRD-04's agent path. **TODO** verify during DP-PRD-03 code review. |
| Should `is_system=true` plans be the only ones allowed to contain pipeline tasks in v1? | No — per plan §6.1 and per the SAR-E design, user-authored plans CAN contain pipeline tasks from v1. The `is_system` write-protection rules from PR-PRD-01 §8a continue to apply to the plans themselves. |
| Cleanup of `TaskArtifact` when a plan is soft-deleted mid-run | A-PRD-03's 30-day lifecycle handles it. No change required here. |

## 10. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md) §3.1 (Pydantic shapes), §3.3 (execution model + test mode), §6.1 (Project Tasks integration), §6.2 (Automations integration), §7 DP-PRD-03
- Upstream: [DP-PRD-01 — Foundation](./DP-PRD-01-foundation.md)
- Upstream: [DP-PRD-02 — Google Analytics connector](./DP-PRD-02-google-analytics-connector.md)
- Upstream: [PR-PRD-01 — Data Model & API](../../project-tasks/projects/PR-PRD-01-data-model-and-api.md) — `PlanTask` model extended here
- Upstream: [PR-PRD-04 — Event-Driven Orchestrator](../../project-tasks/projects/PR-PRD-04-event-driven-orchestrator.md) — `TaskOrchestrator` hooks extended here
- Upstream: [A-PRD-03 — Task Artifact System](../../automations/projects/03-task-artifact-system.md) — `TaskArtifact` write path
- Upstream: [A-PRD-04 — Test / Dry-Run Mode](../../automations/projects/04-test-dry-run-mode.md) — `is_test` threading
- Upstream (soft): [IN-PRD-05 — Re-auth lifecycle](../../integrations/implementation-plan.md) — `"Integration Needs Re-auth"` notification path
- Sibling (downstream): [DP-PRD-04 — Frontend + custom-job authoring](./DP-PRD-04-frontend-and-authoring.md)
- Sibling (downstream): [DP-PRD-06 — Integration testing & polish](./DP-PRD-06-integration-testing.md)
- Cross-component: [`../../sar-e/implementation-plan.md`](../../sar-e/implementation-plan.md) SE-PRD-02 — first scheduled consumer of this dispatch branch
- Pattern files: `api/src/kene_api/services/task_orchestrator.py`, `api/src/kene_api/services/automation_run_engine.py` (`{inputs.*}` substitution), `api/src/kene_api/services/artifact_service.py`
- CLAUDE.md rules in scope: **BP-1**, **BP-2** (complex-work approach draft — orchestrator extension); **C-2** (domain vocabulary — `pipeline_spec`, `dispatcher`, `test_mode_policy`), **C-4** (small composable `_on_pipeline_complete`), **C-5** / **C-6** (frontend branded types are out of scope here); **PY-1**, **PY-2**, **PY-3**, **PY-5**, **PY-7**; **D-1** (Firestore transaction on status writes); **T-1**, **T-3**, **T-4** (unit vs. integration separation), **T-5**, **T-6**; **G-1** (`make lint` gate); **O-1**, **O-2** (shared `PipelineJobSpec` imported, not redefined)
