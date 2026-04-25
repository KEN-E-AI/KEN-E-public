# PRD-6 — Time-Based Task Scheduler

**Status:** Ready for development (after PR-PRD-01 and DM-PRD-00 merge)
**Owner team:** Backend / Infra
**Blocked by:** PR-PRD-01 (needs `launched_at` field in `PlanTask` schema); DM-PRD-00 (provides the `project_plans` collection-group composite index)
**Parallel with:** PRDs 2, 3, 4
**Estimated effort:** 2–3 days
**Origin:** Net-new — closes a gap identified during review of `project-planning-implementation-plan.md`

---

## 1. Context

The data model includes `launch_time_utc: str | None` on every task — a `HH:mm` UTC time meant to combine with `due_date` to form a precise trigger datetime (e.g., a Mailchimp blast at 13:00 UTC on 2026-04-20). The original implementation plan describes an event-driven orchestrator (PRD-4) but **does not include any mechanism to fire a task when its scheduled datetime arrives**.

Codebase exploration confirms KEN-E has **no scheduler infrastructure today**:

- No Cloud Scheduler / Cloud Tasks / EventArc resources in `deployment/terraform/`
- No APScheduler / Celery in Python deps
- `notification_service_v2.archive_old_notifications()` has a comment that it "should be called by a scheduled job," but no such job exists

This PRD builds the missing infrastructure: a Cloud Scheduler cron firing once a minute against an internal endpoint that scans for due tasks and hands each one off to the `TaskOrchestrator` (PRD-4) for dispatch.

## 2. Scope

### In scope
- Cloud Scheduler resource (Terraform) firing every 1 minute
- Internal endpoint `POST /api/v1/internal/scheduler/launch-due-tasks` (auth via OIDC service-account token from Cloud Scheduler)
- Query logic to find tasks where `due_date + launch_time_utc <= now(UTC)`, status `Approved`, `launched_at IS NULL`
- Idempotent firing via `launched_at` write (set before dispatch)
- Hand-off to `TaskOrchestrator.on_task_due(...)` (PRD-4 contract)
- Firestore composite index for the query
- Observability: structured logs + a "tasks fired per tick" metric
- Unit tests for query / idempotency; integration test with a fake clock

### Out of scope
- The orchestrator itself (PRD-4)
- Task status state machine / agent dispatch (PRD-4)
- The `launched_at` field definition (PRD-1 — coordinated)
- Scheduling beyond the per-task `launch_time_utc` model (e.g., recurring schedules — future work)

## 3. Dependencies

- **PR-PRD-01:** must include `launched_at: datetime | None` on `PlanTask` from v1 (coordinated in PR-PRD-01's data contract)
- **PR-PRD-04:** exposes `TaskOrchestrator.on_task_due(account_id, plan_id, task_id) -> OrchestratorResult`
- **DM-PRD-00 (Migration Foundation):** provisions the `project_plans` collection-group composite index (`status ASC, launched_at ASC, due_date ASC`) in `deployment/firestore.indexes.json` and wraps it via `deployment/terraform/firestore_indexes.tf`. This PRD verifies the index is present and uses it; it does not create or modify the index resource itself.
- **External:** Cloud Scheduler (GCP)
- **Existing files to study:**
  - `deployment/terraform/` (see existing GCP resources for module conventions)
  - `api/src/kene_api/main.py` (router registration)
  - `api/src/kene_api/auth/` (find pattern for OIDC token validation, or build new)
  - `api/src/kene_api/tasks/strategy_tasks.py` (FastAPI `BackgroundTasks` reference)

## 4. Data contract

### Field added to `PlanTask` (in PRD-1's schema)
```
launched_at: datetime | None    # set by scheduler when task is fired; idempotency guard
```

### Internal endpoint request/response
Request body: empty (or `{"now": "2026-04-20T13:00:00Z"}` for testability — defaults to `datetime.now(UTC)` if omitted)

Response:
```json
{
  "checked_at": "2026-04-20T13:00:00Z",
  "tasks_fired": [
    {"plan_id": "p_123", "task_id": "t_456", "scheduled_for": "2026-04-20T13:00:00Z"}
  ],
  "task_count": 1
}
```

### Cloud Scheduler config
- Schedule: `* * * * *` (every minute)
- Target: HTTP POST to the internal endpoint
- Auth: OIDC token, audience set to the API service URL
- Retry: 3 attempts with exponential backoff
- Time zone: UTC

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `api/src/kene_api/services/task_scheduler.py` (query + idempotent fire logic) |
| Create | `api/src/kene_api/routers/internal/scheduler.py` (endpoint + OIDC auth dep) |
| Modify | `api/src/kene_api/main.py` — register internal router under `/api/v1/internal` |
| Modify | `api/src/kene_api/auth/` — add `verify_oidc_token` dependency if not present |
| Create | `deployment/terraform/cloud_scheduler.tf` — Cloud Scheduler job + service account + IAM binding |
| Verify | `deployment/firestore.indexes.json` already contains the `project_plans` collection-group composite index (`status ASC, launched_at ASC, due_date ASC`) shipped by DM-PRD-00. Do **not** re-declare the index here; coordinate with the DM-PRD-00 owner if a field needs to change. |
| Create | `api/tests/unit/test_task_scheduler.py` |
| Create | `api/tests/integration/test_scheduler_endpoint.py` |

### Core algorithm — `find_and_fire_due_tasks(now: datetime)`

> **Revised 2026-04-20** — The scheduler uses a collection-group query over `project_plans` under the Shape B layout (`accounts/*/project_plans`). See [Review 15 in DESIGN-REVIEW-LOG](../../../DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1) for rationale.

```
1. Query Firestore (collection group "project_plans"):
     where status == "Approved"
       and launched_at IS NULL
       and due_date <= now.date()
2. For each task in result:
     a. Compute trigger_dt = combine(due_date, launch_time_utc, UTC).
        If launch_time_utc is None → trigger_dt = midnight UTC of due_date.
     b. If trigger_dt > now → skip (still in future).
     c. Run a Firestore transaction:
          re-read the task; if launched_at is still None, set launched_at = now.
          (Returns the task only if the write succeeded — guarantees one fire.)
     d. If the transaction wrote: call orchestrator.on_task_due(...) as a
        BackgroundTask. If it didn't (someone else fired): skip.
3. Return summary of fired tasks.
```

### Idempotency
- Single source of truth: `launched_at` set inside a Firestore transaction is the lock
- Cloud Scheduler may retry; the transaction guarantees only one fire
- If the orchestrator hand-off fails, the task remains marked `launched_at` and `Failed` — explicit operator action required (intentional: avoid silent re-fire)

### Auth (OIDC)
Cloud Scheduler signs requests with a Google-issued OIDC token. The endpoint must:
- Extract `Authorization: Bearer <token>` header
- Verify signature, issuer, and audience (the API service URL)
- Verify the calling service account matches the dedicated scheduler SA (defined in Terraform)

## 6. API contract

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/v1/internal/scheduler/launch-due-tasks` | OIDC (Cloud Scheduler SA only) | Scan for due tasks, fire each via the orchestrator |

This endpoint MUST NOT be exposed to user authentication — it is internal-only.

## 7. Acceptance criteria

1. A task with `due_date=today`, `launch_time_utc="<one minute ago>"`, `status="Approved"` is fired on the next scheduler tick
2. A task in the future is not fired
3. A task with `status != "Approved"` is not fired (e.g., `Draft`, `Awaiting Approval`)
4. A task with `launched_at IS NOT NULL` is not fired again (idempotency)
5. Two concurrent invocations of the endpoint fire each task exactly once (transaction-protected)
6. Calling the endpoint without a valid OIDC token returns `401`
7. Calling with a token from any other service account returns `403`
8. Tasks with `launch_time_utc IS NULL` and `due_date=today` fire at midnight UTC of `due_date`
9. The composite index exists in Firestore (verified by the query running without scan-warning logs)
10. Logs and metrics show "tasks fired per tick" counts; an end-to-end manual test fires a real task within ~60s of its scheduled time

## 8. Test plan

**Unit tests** (`test_task_scheduler.py`):
- Future task not fired
- Past `Approved` task fired
- Past `Draft` task not fired
- Already-launched task not fired
- `launch_time_utc IS NULL` → fires at UTC midnight of `due_date`
- Time combine: `due_date=2026-04-20, launch_time_utc="13:00"` → `2026-04-20T13:00:00Z`
- Idempotency: simulating two concurrent calls with the transaction lock, only one wins
- Edge: `launch_time_utc="00:00"` and `launch_time_utc="23:59"` both work

**Integration tests** (`test_scheduler_endpoint.py`):
- Endpoint with a valid signed OIDC token → 200 + correct task list
- Endpoint with no token → 401
- Endpoint with wrong-audience token → 401
- Endpoint with token from non-scheduler SA → 403
- Endpoint with `now` override (test mode) lets us simulate firing a future task
- After endpoint call, `launched_at` is set on the task in Firestore and orchestrator was invoked once

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| Cloud Scheduler retries cause double-fire | Firestore transaction on `launched_at` is the canonical guard |
| Scheduler downtime causes missed fires | On recovery, the next tick picks up everything with `due_date + launch_time_utc <= now`. Acceptable: most marketing tasks tolerate minute-scale lag. |
| Long-running orchestrator hand-off blocks the endpoint | Dispatch via `BackgroundTasks` so the HTTP response returns immediately |
| Timezone confusion: what does `due_date=2026-04-20` mean if user is in PT? | Decision: `due_date` is a date in **UTC**. Frontend (PRD-3) displays in UTC for consistency. Document this clearly in PRD-1's model docstring. |
| Composite index not created → query falls back to scan | Index is provisioned by DM-PRD-00 (Migration Foundation). This PRD's acceptance criteria include verifying the index exists before merging; CI asserts presence. |
| What about recurring schedules (e.g., "every Tuesday")? | Out of scope. Could be added later as a `recurrence: RRULE | None` field. |

## 10. Reference

- Parent plan: [`../../../project-planning-implementation-plan.md`](../../../project-planning-implementation-plan.md) §Task Orchestration (note: this PRD covers the time-based gap not addressed in the parent plan)
- Cross-PRD coordination: [PRD-1 §Data contract](./PR-PRD-01-data-model-and-api.md#4-data-contract) (`launched_at` field), [PRD-4 §Data contract](./PR-PRD-04-event-driven-orchestrator.md#4-data-contract) (`on_task_due` signature)
- Pattern files: `deployment/terraform/`, `api/src/kene_api/main.py`, `api/src/kene_api/tasks/strategy_tasks.py`
- CLAUDE.md rules in scope: PY-1, PY-2, PY-3, PY-7 (Python); D-1, D-5 (DB); T-1, T-3, T-4, T-6 (testing)
