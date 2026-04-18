# A-PRD-4 — Test / Dry-Run Mode

**Status:** Ready for development (after A-PRDs 1 + 3 merge)
**Owner team:** Backend
**Blocked by:** A-PRD-1, A-PRD-3
**Parallel with:** A-PRDs 5, 6
**Estimated effort:** 2 days

---

## 1. Context

Before turning an automation loose on a recurring schedule, the user wants to verify it produces acceptable outputs. The "Test Run" button on the Automation Details page (A-PRD-6) triggers a one-off run with `is_test=true`. The run executes against real agents with real artifact persistence, so the user can inspect outputs in the Outputs tab.

When a test run hits a human-in-the-loop (HITL) task, the orchestrator **halts** at that task — sets it to `Awaiting Approval`, sends a notification, and waits for the user to manually mark it `Complete`. Once the user does so, the orchestrator continues to dispatch downstream tasks. This lets the user step through the entire automation, validating each agent output along the way.

## 2. Scope

### In scope
- New endpoint `POST /api/v1/automations/{account_id}/{plan_id}/runs/test`
- Orchestrator extension: when running with `is_test=true`, halt on HITL tasks instead of dispatching notifications-and-continuing
- New endpoint `POST /api/v1/automations/{account_id}/{plan_id}/runs/{run_id}/cancel` for aborting in-flight test runs
- Manual completion path for HITL tasks during test runs (reuses Calendar PRD-1's PATCH task endpoint, routed through the orchestrator)
- Notification payload includes a `is_test=true` flag so the frontend can label it
- Unit + integration tests including the halt/resume cycle

### Out of scope
- The `PlanRun` data model (A-PRD-1)
- Artifact persistence (A-PRD-3) — test runs save artifacts via that system unchanged
- Frontend UX for triggering tests, displaying halts, and the manual-complete UI (A-PRD-6)

## 3. Dependencies

- **A-PRD-1:** `PlanRun.is_test`, run status enum (`halted_for_human`)
- **A-PRD-3:** test runs save artifacts via the artifact system; the Outputs tab depends on this working
- **Calendar PRD-4:** `TaskOrchestrator.activate_plan` + `on_task_status_change` — extended here to support test-mode halt semantics
- **Calendar PRD-1:** PATCH task endpoint — must route status changes through the orchestrator (already does, per Calendar PRD-4)

### Coordination — orchestrator extension

This PRD adds an `is_test` boolean to the orchestrator's run-context. Threading:

- `activate_plan(account_id, plan_id, run_id, is_test=False)` — A-PRD-2 already added `run_id`; this PRD adds `is_test`
- `on_task_status_change` reads `is_test` from the loaded `PlanRun` (no signature change needed)
- The HITL halt logic lives in the "task is unblocked" branch: if `task.assignee_type == "human"` AND `run.is_test == True`, set status to `Awaiting Approval` + notify, but do **not** advance further until the human completes the task

## 4. Data contract

### Test-run trigger endpoint

`POST /api/v1/automations/{account_id}/{plan_id}/runs/test`

Request body (all fields optional):
```json
{
  "inputs": {
    "session_id": "s_abc",
    "some_other_context": "..."
  }
}
```

The `inputs` object, if provided, is stored on the new `PlanRun` and substituted into agent prompts per [A-PRD-2 §Inputs template substitution](./02-recurring-scheduler.md#inputs-template-substitution). This is how a user validates an automation that expects per-run context (e.g. the KG session-end automation, [KG-PRD-4](../../knowledge-graph/04-session-end-automation.md)) — they pass sample context in the test request and observe the agents dispatch against it.

This subsumes the previously-deferred `override_inputs` idea — one `inputs` field covers scheduled, manual, `system`, and `test` runs.

Response: the new `PlanRun` doc with `is_test=true`, `triggered_by="test"`, `triggered_by_user_id={user}`, `inputs=<as-provided-or-null>`.

### Cancel endpoint

`POST /api/v1/automations/{account_id}/{plan_id}/runs/{run_id}/cancel`

Sets run status to `cancelled`, marks all not-yet-complete `task_states` as `Cancelled`, aborts pending background dispatches via a cancellation token (or best-effort if dispatch is already in flight).

### Notification payload (extends Calendar PRD-4's `Task Ready`)

```json
{
  "plan_id": "...",
  "task_id": "...",
  "run_id": "...",
  "is_test": true,
  "task_title": "Review generated ad copy",
  "deep_link": "/workflows/automations/{plan_id}?run={run_id}&task={task_id}"
}
```

The frontend renders a "Test Run" badge when `is_test=true`.

## 5. Implementation outline

| Action | File |
|--------|------|
| Modify | `api/src/kene_api/routers/automations.py` (A-PRD-1) — add test-trigger + cancel endpoints |
| Modify | `api/src/kene_api/services/task_orchestrator.py` (Calendar PRD-4) — add `is_test` halt branch |
| Modify | `api/src/kene_api/services/automation_run_engine.py` (A-PRD-2) — `create_run(is_test=True, triggered_by="test")` helper |
| Modify | `api/src/kene_api/services/notification_service_v2.py` — include `is_test` in notification data payload |
| Create | `api/tests/unit/test_orchestrator_test_mode.py` |
| Create | `api/tests/integration/test_test_run_endpoints.py` |

### Halt behavior — full algorithm

```
on_task_status_change(run, task, new_status):
  ...
  if new_status in ("Complete", "Approved"):
    for downstream_task in find_unblocked_downstream(run, task):
      if downstream_task.assignee_type == "human":
        # Same path for normal AND test runs:
        # set status to "Awaiting Approval", create notification.
        # Difference: test-run notifications carry is_test=true so the
        # frontend can label them.
        set_status(downstream_task, "Awaiting Approval")
        notify("Task Ready", deep_link=..., is_test=run.is_test)
      else:  # agent
        if run.is_test:
          # Same: dispatch the agent. Test mode does not change agent dispatch.
          dispatch_agent(downstream_task, run)
        else:
          dispatch_agent(downstream_task, run)
```

**Key observation:** the halt at HITL tasks isn't a *new* code path — it's the same path the production-mode orchestrator uses for HITL gates (Calendar PRD-4 already halts at HITL tasks until a human approves). The `is_test` flag only affects:

1. The `is_test` field on the notification payload (so the UI can badge it)
2. The cancel-availability (test runs can be cancelled mid-flight; production runs follow Calendar PRD-4's semantics)
3. The `run.is_test` flag tagged on every `PlanRun` so artifact queries can filter

This means **A-PRD-4 is mostly orchestrator plumbing + two endpoints + a notification field**. The "halt at HITL" behavior comes for free from Calendar PRD-4.

### Cancel implementation

```
cancel_run(run_id):
  with transaction:
    run = repo.get(run_id)
    if run.status in ("complete", "failed", "cancelled"):
      return run  # already terminal
    run.status = "cancelled"
    for state in run.task_states:
      if state.status not in ("Complete", "Approved", "Failed"):
        state.status = "Cancelled"
    repo.save(run)
  # Background dispatches may still complete; their status writes are no-ops
  # because the run is terminal (orchestrator checks run.status before writes)
  return run
```

The orchestrator's status-write path checks `run.status` before applying any write; if the run is `cancelled`, the write is dropped and an audit entry is logged.

## 6. API contract

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/automations/{account_id}/{plan_id}/runs/test` | Trigger a test run; returns the `PlanRun` doc |
| `POST` | `/api/v1/automations/{account_id}/{plan_id}/runs/{run_id}/cancel` | Abort an in-flight run |

Both endpoints reuse the access-control dependency from A-PRD-1.

## 7. Acceptance criteria

1. POSTing to `/runs/test` creates a `PlanRun` with `is_test=true`, `triggered_by="test"`, status `pending`, and dispatches via the orchestrator
1a. POSTing to `/runs/test` with `{"inputs": {...}}` persists the inputs on the `PlanRun` and substitutes them into dispatched agent prompts per A-PRD-2's substitution rules
2. The first agent task in the DAG is dispatched (artifact saved per A-PRD-3)
3. When the run reaches a HITL task, the task's status is set to `Awaiting Approval` and a notification is created with `is_test=true` in the payload
4. No downstream tasks dispatch until the user PATCHes the HITL task to `Complete`
5. After the user completes the HITL task, the orchestrator dispatches the next-unblocked tasks
6. POSTing to `/cancel` while a run is in flight sets `run.status="cancelled"` and aborts pending dispatches; in-flight agent calls may complete but their status writes are dropped
7. A test run's artifacts are saved (per A-PRD-3) and visible when querying `/artifacts/recent?is_test=true`
8. Cross-account access on either endpoint returns 403
9. Two concurrent test runs of the same automation execute independently (separate `PlanRun` docs, separate task_states)
10. Notification payload's `is_test` flag is consumed by the frontend (smoke test with A-PRD-6)

## 8. Test plan

**Unit tests** (`test_orchestrator_test_mode.py`):
- `is_test=true` + HITL downstream task → status set to `Awaiting Approval`, notification with `is_test=true`, no downstream dispatch
- After user marks HITL `Complete` → next downstream tasks dispatch
- `is_test=true` + agent downstream task → dispatch happens normally (no change vs production)
- Cancel mid-run: status → cancelled; subsequent status writes dropped; audit entry logged
- Cancel of an already-terminal run: no-op (returns existing state, no error)

**Integration tests** (`test_test_run_endpoints.py`):
- POST /runs/test → 201 + PlanRun in Firestore + at least one BackgroundTask scheduled
- Full halt cycle with mocked agent: dispatch agent task → save artifact → orchestrator advances to HITL → halt → user PATCH → continue → run completes
- Cancel endpoint: 200 + run status changes to `cancelled`
- Cross-account: 403 on both endpoints
- Cancel an already-cancelled run: 200 (idempotent), state unchanged

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| User abandons a test run mid-way (no cancel, no completion) | Run sits in `halted_for_human` indefinitely. Acceptable for v1; UI surfaces "halted runs" so the user can clean up. Future: auto-expire halted test runs after 7 days. |
| In-flight agent dispatches after cancel can't be killed | Document: cancel is best-effort. The orchestrator drops their status writes, but the agent call itself completes (and may incur cost). Acceptable. |
| Test mode confusion: user thinks test won't side-effect the world but agent calls real APIs (sends real emails, etc.) | Document prominently: test mode = real agents, real outputs, real side effects. The "test" framing is about validating outputs, not about safety. If a true sandbox is needed later, that's a future PRD. |
| `is_test` notifications mixed with production notifications in the sidebar | Frontend filter: hide test notifications by default; user toggle to show. (Coordinate with A-PRD-6.) |
| HITL task during test gets approved by a *different* user than the test trigger | Allowed. Audit log captures actor. |

## 10. Reference

- Parent plan: [`../automations-implementation-plan.md`](../automations-implementation-plan.md) §2 (Test mode flow)
- Foundation: [A-PRD-1](./01-data-model-and-api.md), [A-PRD-3](./03-task-artifact-system.md)
- Orchestrator extension: [Calendar PRD-4](../../prd/04-event-driven-orchestrator.md)
- CLAUDE.md rules in scope: PY-1, PY-2, PY-7; T-1, T-3, T-5
