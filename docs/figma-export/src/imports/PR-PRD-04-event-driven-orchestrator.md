# PRD-4 — Event-Driven Task Orchestrator

**Status:** Ready for development (after PRD-1 merges)
**Owner team:** Backend (separate from PRD-1 team)
**Blocked by:** PRD-1
**Parallel with:** PRDs 2, 3, 6
**Estimated effort:** 3–4 days

> **Note on scope:** This PRD covers **event-driven** orchestration only. Time-based triggering of tasks at `due_date + launch_time_utc` is owned by [PRD-6](./PR-PRD-06-time-based-scheduler.md) — when the scheduler fires a task, it hands off to the orchestrator defined here.

---

## 1. Context

Once a project plan is `active`, the system needs to advance it autonomously: when one task completes, downstream tasks whose dependencies are now satisfied must be unblocked and either dispatched (for agent tasks) or surfaced to a human (for human tasks). When a human requests a revision, the upstream agent task must be re-run with the feedback. None of this exists today.

This PRD builds the `TaskOrchestrator` service — the single point where task-status changes converge and downstream effects fan out.

## 2. Scope

### In scope
- `TaskOrchestrator` service with `on_task_status_change` (event-driven entry point)
- A separate hook `on_task_due` for PRD-6 to call when the scheduler fires a time-triggered task
- Dependency-resolution logic (Kahn-style: a task is unblocked when all `depends_on` are in a terminal "done" state)
- Agent task dispatch (reuse `AgentEngineClient` pattern from `chat.py`)
- Human task notification using the existing notification system + a new `"Task Ready"` category
- Revision loop (capped at 5 iterations)
- Failure handling (mark task failed, notify owner, allow independent branches to continue)
- Two new API endpoints: `/activate` and `/revision`
- Frontend snippet: notification icon/color + deep-link nav in `NotificationSidebar.tsx`
- Unit + integration tests with mocked agent dispatch

### Out of scope
- The scheduler itself (PRD-6)
- The CRUD endpoints (PRD-1)
- The planning agent (PRD-2)
- Calendar page / detail panel UI (PRD-3) — this PRD only touches `NotificationSidebar.tsx` for deep-link wiring

## 3. Dependencies

- **PRD-1:** uses `ProjectPlan` / `PlanTask` models; calls `PATCH` task endpoint
- **PRD-3:** coordinates on the small `NotificationSidebar.tsx` change (this PRD owns the enum + nav wiring; PRD-3 owns the calendar page that the deep link lands on)
- **PRD-6:** exposes `on_task_due(plan_id, task_id)` as the hand-off contract
- **Existing files to study:**
  - `api/src/kene_api/services/notification_service_v2.py` (`create_notification` API)
  - `api/src/kene_api/repositories/firestore_notification_repository.py`
  - `api/src/kene_api/models/kene_models.py` (`NotificationCategory` enum)
  - `api/src/kene_api/routers/chat.py` lines 258–378 (`AgentEngineClient`)
  - `frontend/src/components/notifications/NotificationSidebar.tsx`
  - `frontend/src/types/notification.types.ts` (icon/color maps)

## 4. Data contract

### Orchestrator API (Python)
```python
class TaskOrchestrator:
    async def on_task_status_change(
        self,
        account_id: str,
        plan_id: str,
        task_id: str,
        new_status: TaskStatus,
        completion_notes: str | None = None,
        revision_comment: str | None = None,
    ) -> OrchestratorResult: ...

    async def on_task_due(
        self,
        account_id: str,
        plan_id: str,
        task_id: str,
    ) -> OrchestratorResult: ...

    async def activate_plan(
        self,
        account_id: str,
        plan_id: str,
    ) -> OrchestratorResult: ...
```

`OrchestratorResult`:
```python
class OrchestratorResult(BaseModel):
    plan_id: str
    updated_task_id: str | None
    newly_unblocked_task_ids: list[str]
    dispatched_agent_task_ids: list[str]
    notified_human_task_ids: list[str]
    revision_iteration: int | None  # for revision loop tracking
```

### Notification payload (extends existing system)
- Add `"Task Ready"` to `NotificationCategory` enum
- `data` field shape:
  ```json
  {
    "plan_id": "...",
    "task_id": "...",
    "task_title": "...",
    "upstream_task_summary": "...",
    "action_required": "review_and_approve",
    "deep_link": "/calendar?project=...&task=..."
  }
  ```

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `api/src/kene_api/services/task_orchestrator.py` |
| Create | `api/src/kene_api/services/task_orchestrator_dispatch.py` (agent dispatch helper using `AgentEngineClient`) |
| Modify | `api/src/kene_api/routers/project_plans.py` (PRD-1) — add `/activate` and `/tasks/{task_id}/revision` endpoints that delegate to the orchestrator |
| Modify | `api/src/kene_api/models/kene_models.py` — add `"Task Ready"` to `NotificationCategory` enum |
| Modify | `app/adk/agents/project_planning_tools.py` (PRD-2) — wire `update_task_status` to also call orchestrator (so agent and API paths converge) |
| Modify | `frontend/src/types/notification.types.ts` — add icon + color for `"Task Ready"` |
| Modify | `frontend/src/components/notifications/NotificationSidebar.tsx` — when category is `"Task Ready"`, navigate to `data.deep_link` on click |
| Create | `api/tests/unit/test_task_orchestrator.py` |
| Create | `api/tests/integration/test_orchestrator_endpoints.py` |

### Core algorithm — `on_task_status_change`
```
1. Load plan from Firestore (PRD-1's repository).
2. Update the task's status (PRD-1's PATCH path or direct repo write).
3. Branch on new_status:
   - "Complete" or "Approved":
       a. For each task whose depends_on includes task_id:
            if all its deps are now in {"Complete", "Approved"}:
              if task.assignee_type == "agent":
                dispatch agent (background); record in dispatched_agent_task_ids
              else:
                create "Task Ready" notification with deep_link;
                record in notified_human_task_ids
   - "Revision Requested":
       a. Find the upstream agent task that produced this output (most recent
          in-chain agent task whose dependents include task_id).
       b. Bump revision_iteration; if > 5 → mark task as Failed and notify owner;
          else → set upstream task back to "Draft" with revision_comment,
          re-dispatch agent with the comment included in the prompt.
   - "Rejected":
       a. Mark all transitively-downstream tasks as Blocked.
       b. Notify project owner.
4. Persist plan; write audit entries.
5. Return OrchestratorResult.
```

### `on_task_due` (PRD-6 hand-off)
- Verify task `status == "Approved"` and `launched_at` is set (idempotency guard set by PRD-6 before calling)
- Dispatch via the same agent/notify path used for unblocked downstream tasks

### Agent dispatch helper
- Wraps `AgentEngineClient` from `chat.py`; constructs prompt containing task description, project goal, related task outputs, and `revision_comment` (if any)
- Runs as a FastAPI `BackgroundTasks` so the originating request returns immediately
- On agent completion, agent calls `update_task_status(status="Awaiting Approval" | "Complete")`, which routes back into the orchestrator → completes the loop

## 6. API contract

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/plans/{account_id}/{plan_id}/activate` | Set status to `active`; identify root tasks (no `depends_on`); dispatch agent roots, notify human roots |
| `POST` | `/api/v1/plans/{account_id}/{plan_id}/tasks/{task_id}/revision` | Body: `{revision_comment: str}`. Sets task to `Revision Requested` and triggers the revision branch of the orchestrator. |

Request/response bodies follow the strategy router conventions. Auth via the same access-control dependency as PRD-1.

## 7. Acceptance criteria

1. Activating a plan with two root agent tasks dispatches both immediately
2. Marking an agent task `Complete` whose dependent has all other deps satisfied triggers the dependent (agent dispatched OR notification created)
3. Marking a human task `Approved` similarly unblocks downstream
4. Marking a task `Revision Requested` resets the producing upstream task to `Draft` and re-dispatches with the comment included in the prompt
5. Revision iterations cap at 5; the 6th attempt marks the task `Failed` and notifies owner
6. Marking a task `Rejected` blocks all transitively-downstream tasks; tasks not on that branch continue independently
7. The notification appears in `NotificationSidebar` with the new "Task Ready" icon/color; clicking it routes to `/calendar?project=...&task=...` (verified manually with PRD-3 merged)
8. `update_task_status` (ADK tool) and the API PATCH path produce identical orchestrator behavior
9. Audit log captures every status change with actor (`agent:project_planning` or `user:{user_id}`), timestamp, and old/new status
10. All unit + integration tests pass

## 8. Test plan

**Unit tests** (`test_task_orchestrator.py`):
- Diamond dependency: A → (B, C) → D. Complete A → both B and C dispatched. Complete one of B/C → D not yet unblocked. Complete the other → D unblocked.
- Revision loop: simulate 3 iterations succeed; 6th iteration triggers `Failed`
- Reject: A → B → C; reject B → C is blocked, A unaffected
- Mixed agent/human: agent root completes → human dependent gets notification (not dispatch); human dependent approves → agent grandchild gets dispatch
- Idempotency: `on_task_due` called twice for the same task only dispatches once (guard via `launched_at` set by PRD-6)

**Integration tests** (`test_orchestrator_endpoints.py`):
- Full activate flow with a 3-task plan + mocked agent client
- Revision endpoint: POST → orchestrator side effects observable in Firestore
- Cross-account access denied
- `update_task_status` ADK tool path produces identical Firestore state as the PATCH path

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| Concurrent updates to the same plan (race) | Use Firestore transactions for status writes; orchestrator reads-then-writes within a transaction |
| Agent dispatch fails mid-plan | Mark task `Failed` (new status — coordinate with PRD-1 to add to enum); other branches continue; audit and notify |
| Determining the "producing upstream task" for revisions in fan-in topologies is ambiguous | Default heuristic: most recent agent task in the closure of `depends_on`. Document and revisit. Consider a `produced_by_task_id` link field in v2. |
| Notifications miss the user (polling-based system) | Existing limitation; future work: add Firestore real-time listeners for "Task Ready" |
| Prompt injection via `revision_comment` | Existing `adk_before_tool_callback` security hook applies; sanitize before injection |
| Coordinating the `NotificationSidebar.tsx` change with PRD-3 | Small surface area; PR can be reviewed by both teams. Add a clear comment in `notification.types.ts` referencing PRD-4. |

## 10. Reference

- Parent plan: [`../../../project-planning-implementation-plan.md`](../../../project-planning-implementation-plan.md) §Task Orchestration, §Implementation Phases (Phase 4)
- Pattern files: `api/src/kene_api/services/notification_service_v2.py`, `api/src/kene_api/routers/chat.py` (lines 258–378 for `AgentEngineClient`)
- CLAUDE.md rules in scope: PY-1, PY-2, PY-3, PY-7 (Python); D-1 (DB context managers); T-1, T-3, T-4, T-5, T-6 (testing); C-2, C-4 (naming/composition)
