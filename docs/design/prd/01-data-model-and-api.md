# PRD-1 — Project Plan Data Model & API

**Status:** Ready for development
**Owner team:** Backend (foundation)
**Blocks:** PRDs 2, 3, 4, 6
**Estimated effort:** 2–3 days

---

## 1. Context

KEN-E needs the ability to persist structured project plans (tasks, dependencies, acceptance criteria, status, audit trail) outside the agent session so that they can be displayed in the frontend, modified by humans, and acted on by agents over time.

This PRD delivers the **foundation** — the Pydantic schema and the CRUD API. Every other PRD in this set (Planning Agent, Calendar Frontend, Orchestrator, Scheduler) consumes the data contract published here, so this work must ship first.

The architecture follows the existing Strategy Document pattern (`api/src/kene_api/routers/strategy.py`) — account-scoped Firestore collections, versioning, audit log, access-control dependency. No new infrastructure is required.

## 2. Scope

### In scope
- Pydantic models for `ProjectPlan`, `PlanTask`, `AcceptanceCriterion`, status enums, and request/response wrappers
- DAG validator (Kahn's algorithm) on the Pydantic model: cycle detection + missing-reference detection
- CRUD router with list / get / create / update / patch-task / soft-delete / audit-log endpoints
- Firestore collections, versioning, and audit trail mirroring the Strategy pattern
- Access control dependency (account-scoped, view/edit permissions)
- Unit tests for models + DAG validator; integration tests for endpoints

### Out of scope (handled by other PRDs)
- The `/activate` and `/revision` endpoints (PRD-4)
- The `/internal/scheduler/launch-due-tasks` endpoint (PRD-6)
- Any agent-side or frontend code

## 3. Dependencies

- **External:** Firestore, FastAPI (existing in repo)
- **Existing files to study:** `api/src/kene_api/routers/strategy.py`, `api/src/kene_api/models/strategy_models.py`, `api/src/kene_api/services/firestore_service.py`
- **Coordination:** Confirm with the PRD-6 team that the `launched_at: datetime | None` field is included in v1 of `PlanTask` so a schema migration is not needed mid-sprint.

## 4. Data contract

### `ProjectPlan`
```
plan_id: str (UUID)
account_id: str
title: str
goal: str
acceptance_criteria: list[AcceptanceCriterion]
tasks: list[PlanTask]
campaign: str | None
tags: list[str]
status: PlanStatus              # draft | active | completed | archived
created_by: str
created_at: datetime
updated_at: datetime
version: int
is_active: bool
is_system: bool = False         # system-created templates (seeded, not user-authored)
                                # hidden from the user-facing list page and read-only
                                # on the details page. Consumed by A-PRDs 5 + 6 and by
                                # the Knowledge Graph PRDs for the session-end workflow.
```

### `is_system` semantics

`is_system=True` marks a template as platform-owned (seeded via a migration script, not created by a user through the UI). It carries two product guarantees, enforced by downstream PRDs rather than this one:

- The automations list page (A-PRD-5) filters `is_system=true` out of the default query.
- The automation details page (A-PRD-6) renders read-only when `is_system=true` — no DAG edits, no Run Now, no Delete.

This PRD only owns the field itself. The enforcement lives in the consuming PRDs.

### `AcceptanceCriterion`
```
criterion_id: str
description: str
is_met: bool                    # default False
```

### `PlanTask`
```
task_id: str
title: str
description: str
assignee_type: Literal["agent", "human"]
assignee_name: str
status: TaskStatus              # Draft | Awaiting Approval | Approved | Rejected | Revision Requested | Complete
depends_on: list[str]           # task_ids — forms the DAG
cost: float | None
due_date: date | None
launch_time_utc: str | None     # "HH:mm" UTC
launched_at: datetime | None    # set by PRD-6 scheduler when task is fired (idempotency guard)
platform: str | None
tags: list[str]
estimated_effort: Literal["small", "medium", "large"] | None
completion_notes: str | None
revision_comment: str | None
```

### Validators (model-level)
- `launch_time_utc` matches `^([01]\d|2[0-3]):[0-5]\d$`
- `assignee_type == "agent"` → `assignee_name` must exist in `app.adk.agents.registry` (defer this check to a separate validator the agent team can wire in PRD-2; for PRD-1, only the regex/format checks)
- DAG validator on `tasks`:
  - Every `task_id` in any `depends_on` exists in `tasks`
  - No cycles (Kahn's topological sort)
  - Returns clear error message identifying offending task(s)

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `api/src/kene_api/models/project_plan_models.py` |
| Create | `api/src/kene_api/routers/project_plans.py` |
| Modify | `api/src/kene_api/main.py` — register the router |
| Create | `api/tests/unit/test_project_plan_models.py` |
| Create | `api/tests/unit/test_project_plan_dag_validator.py` |
| Create | `api/tests/integration/test_project_plans_router.py` |

### Firestore layout
```
project_plans_{account_id}/
  {plan_id}/                                 # current version
project_plans_{account_id}/{plan_id}/versions/{version_number}/   # archived snapshots
project_plan_audit_{account_id}/             # audit entries (who changed what, when)
```

## 6. API contract

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/plans/{account_id}` | List all plans for the account (filterable by status, campaign, tag) |
| `GET` | `/api/v1/plans/{account_id}/{plan_id}` | Fetch a specific plan |
| `POST` | `/api/v1/plans/{account_id}` | Create a new plan |
| `PUT` | `/api/v1/plans/{account_id}/{plan_id}` | Update a plan (creates new version, archives previous) |
| `PATCH` | `/api/v1/plans/{account_id}/{plan_id}/tasks/{task_id}` | Update a single task's mutable fields |
| `DELETE` | `/api/v1/plans/{account_id}/{plan_id}` | Soft-delete (`is_active = false`) |
| `GET` | `/api/v1/plans/{account_id}/{plan_id}/history` | Audit log entries for the plan |

Auth: standard `check_strategy_access`-equivalent dependency, scoped per account. Responses use the same `200 / 201 / 403 / 404 / 422` patterns as the strategy router.

## 7. Acceptance criteria

1. Posting a valid plan returns `201` with `plan_id` and persists to `project_plans_{account_id}`
2. Posting a plan with a dependency cycle returns `422` with an error message naming the offending task IDs
3. Posting a plan referencing a non-existent `depends_on` task ID returns `422`
4. PUT'ing an updated plan creates a new version snapshot in `versions/{n}` and bumps `version` on the live doc
5. PATCH'ing a single task only modifies that task and writes an audit entry
6. A user from another account receives `403` on any of the above
7. The `launched_at` field exists on the model (defaults to `None`) so PRD-6 can use it without schema changes
8. The `is_system` field exists on the model (defaults to `False`) so A-PRDs 5, 6 and the Knowledge Graph PRDs can rely on it without schema changes
8a. Write protection for system plans:
    - `POST /api/v1/plans/{account_id}` accepts `is_system=true` from authenticated callers (service-account or privileged tokens), but the field silently defaults to `false` for standard user-auth requests — users cannot create system templates from the UI.
    - `PUT /api/v1/plans/{account_id}/{plan_id}` on a plan where `is_system=true` returns `403` regardless of payload.
    - `PATCH /api/v1/plans/{account_id}/{plan_id}/tasks/{task_id}` on a task whose parent plan has `is_system=true` returns `403` **unless** the patch touches only status / completion_notes / revision_comment / revision_iteration fields. This carve-out lets HITL Mark Complete / Revision Requested work on system runs without allowing template edits.
    - `DELETE /api/v1/plans/{account_id}/{plan_id}` on a system plan returns `403`.
    - The status-only carve-out uses an explicit allowlist (not a denylist). Any unlisted field in the PATCH payload triggers the 403.
9. All endpoints have corresponding integration tests passing in `api/tests/`

## 8. Test plan

**Unit tests** (`test_project_plan_models.py`, `test_project_plan_dag_validator.py`):
- DAG validator: empty `depends_on` (root), valid linear chain, valid diamond, simple 2-cycle, self-reference cycle, deep cycle (5 hops), missing reference, single-task plan, large plan (~50 tasks)
- `launch_time_utc` regex: valid (`"00:00"`, `"13:00"`, `"23:59"`), invalid (`"24:00"`, `"1:0"`, `"13:60"`, `""`)
- Status transition rules (where enforced at the model level)

**Integration tests** (`test_project_plans_router.py`):
- Full CRUD lifecycle for one plan
- Versioning: PUT twice, GET history returns 2 entries
- Soft-delete: DELETE then GET returns `404`
- Access control: cross-account access returns `403`
- Audit log records `created_by`, `action`, `timestamp` for every mutation
- `is_system` write protection:
  - Seed a plan with `is_system=true`. PUT with any payload → `403`.
  - PATCH that task with `{"status": "Complete", "completion_notes": "ok"}` → `200` (carve-out honored).
  - PATCH that task with `{"title": "new"}` → `403` (outside allowlist).
  - PATCH with `{"status": "Complete", "title": "new"}` → `403` (mixed payload rejected whole).
  - DELETE the plan → `403`.
- `is_system` default on POST: user-auth request with `is_system=true` in the body → persisted as `false`; service-auth request → persisted as `true`.

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| `due_date` timezone interpretation (date-only vs. local vs. account TZ) is ambiguous when combined with `launch_time_utc` for PRD-6 | Decide upfront: `due_date` is a date in **UTC**, combined with `launch_time_utc` to form the UTC trigger datetime. Document this in the model docstring. |
| Schema drift between PRD-1 and PRD-6 if `launched_at` is forgotten | Include the field in v1 (already in the data contract above). Coordinate with PRD-6 team during PRD-1 review. |
| Pydantic serialization of `date` vs `datetime` | Use `date` for `due_date`, `datetime` for `launched_at` and timestamps. Match existing strategy model conventions. |

## 10. Reference

- Parent plan: [`../project-planning-implementation-plan.md`](../project-planning-implementation-plan.md) §Data Model, §API Endpoints, §Implementation Phases (Phase 1)
- Pattern to mirror: `api/src/kene_api/routers/strategy.py`, `api/src/kene_api/models/strategy_models.py`
- CLAUDE.md rules in scope: D-1, D-2, D-5 (database), PY-1, PY-2, PY-7 (Python), T-1, T-3, T-4, T-7, T-8 (testing)
