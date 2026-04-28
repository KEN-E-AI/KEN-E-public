# PRD-1 — Project Plan Data Model & API

**Status:** Blocked — resumes once DM-PRD-05 ships
**Owner team:** Backend (foundation)
**Blocked by:** DM-PRD-05 (Deletion Sweep Rewrite — ensures `recursive_delete` covers the new `project_plans` / `project_plan_audit` subcollections; ship DM-PRD-05 first to avoid an orphaned-data interim)
**Blocks:** PRDs 2, 3, 4, 6, 7 (PR-PRD-07 Calendar Activities extends this model), 8 (PR-PRD-08 Campaign Management renames the `campaign` field), 9 (DM-PRD-07 Approval Workflow & Audit layers over the transition endpoints)
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
- **DM-PRD-05 (Deletion Sweep Rewrite):** hard prerequisite. DM-PRD-05 replaces the enumerated sweep in `routers/accounts.py:968-997` with `firestore.recursive_delete(accounts/{account_id})`, which automatically covers the new `project_plans` and `project_plan_audit` subcollections introduced here. Without it, a `DELETE /accounts/{account_id}` would orphan project data.
- **Existing files to study:** `api/src/kene_api/routers/strategy.py`, `api/src/kene_api/models/strategy_models.py`, `api/src/kene_api/services/firestore_service.py`
- **Coordination:** Confirm with the PR-PRD-06 team that the `launched_at: datetime | None` field is included in v1 of `PlanTask` so a schema migration is not needed mid-sprint.

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
status: TaskStatus              # Draft | Awaiting Approval | Approved | Rejected | Revision Requested | Complete | Failed | Blocked
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

### `TaskStatus` semantics

`Failed` and `Blocked` are terminal lifecycle states that the orchestrator (PRD-4) writes — but the enum is owned by this PRD so the model and validators ship in v1 without a follow-up migration:

- **`Failed`** — written by the orchestrator when (a) the revision loop exceeds 5 iterations or (b) an agent / data-pipeline dispatch fails non-recoverably. Independent branches of the DAG continue running.
- **`Blocked`** — written by the orchestrator on every transitively-downstream task when an upstream task is `Rejected` or `Failed`. Reactivation requires a plan edit (changing `depends_on` or rejecting status); there is no direct `Blocked → Draft` transition exposed via the API.

The detailed transition rules and the side effects (notifications, downstream blocking, audit) live in [PR-PRD-04](./PR-PRD-04-event-driven-orchestrator.md). PR-PRD-01 ships only the enum values + the model field; PR-PRD-04 enforces the transition policy.

### Forward-coordination — `assignee_type` extension

[DP-PRD-03](../../data-pipeline/projects/DP-PRD-03-task-system-integration.md) extends `PlanTask.assignee_type` from `Literal["agent", "human"]` to `Literal["agent", "human", "data_pipeline"]` and adds a sibling `pipeline_spec: PipelineJobSpec | None` field. PR-PRD-01 ships the two-value union; DP-PRD-03 lands the third value as an additive patch (no migration needed because `pipeline_spec` defaults to `None` and existing rows already have `assignee_type ∈ {"agent", "human"}`).

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

> **Revised 2026-04-20** — Firestore paths follow the Shape B layout (`accounts/{account_id}/{resource}/...`). See [Review 15 in DESIGN-REVIEW-LOG](../../../DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1) for rationale.

```
accounts/{account_id}/project_plans/{plan_id}                                  # current version
accounts/{account_id}/project_plans/{plan_id}/versions/{version_number}        # archived snapshots
accounts/{account_id}/project_plan_audit/{audit_id}                            # audit entries (who changed what, when)
```

## 6. API contract

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/plans/{account_id}` | List plans. **Supported filters:** `status[]`, `category[]` (task/promotion/holiday/event — added by PR-PRD-07), `owner_email[]`, `platform[]`, `channel[]`, `campaign_id[]`, `plan_id[]`, `task_type[]`, `tags[]`, `from` (ISO date), `to` (ISO date), `is_active`, `cursor`, `page_size`. The category / owner / platform / channel / task_type / date-range filters are introduced by PR-PRD-07 and apply over the embedded `tasks` array; v1 ships the public contract for them, with PR-PRD-07 adding the server-side filter loop. |
| `GET` | `/api/v1/plans/{account_id}/{plan_id}` | Fetch a specific plan |
| `GET` | `/api/v1/plans/{account_id}/{plan_id}/execution-order` | Topologically-sorted waves for DAG execution. Response: `{waves: [[task_id, ...], [task_id, ...], ...]}` where each inner array is a set of tasks safe to execute in parallel. Computed from `tasks[*].depends_on` via the same DAG logic used by the validator. Consumers: `TaskOrchestrator` (PR-PRD-04), Calendar UI (for read-only visualization). |
| `POST` | `/api/v1/plans/{account_id}` | Create a new plan |
| `PUT` | `/api/v1/plans/{account_id}/{plan_id}` | Update a plan (creates new version, archives previous) |
| `PATCH` | `/api/v1/plans/{account_id}/{plan_id}/tasks/{task_id}` | Update a single task's mutable fields |
| `DELETE` | `/api/v1/plans/{account_id}/{plan_id}` | Soft-delete (`is_active = false`) |
| `GET` | `/api/v1/plans/{account_id}/{plan_id}/history` | Audit log entries for the plan. Returns `AuditEntry` documents owned by [DM-PRD-07](../../data-management/projects/DM-PRD-07-approval-workflow-and-audit.md) — shape, retention, and write helper live there. |

Auth: standard `check_strategy_access`-equivalent dependency, scoped per account. Role enforcement on status-changing transitions is delegated to `require_role(AccountRole.EDITOR | AccountRole.APPROVER, scope="account")` + `assert_transition_allowed(...)` from [DM-PRD-07](../../data-management/projects/DM-PRD-07-approval-workflow-and-audit.md); this PRD ships the raw transition endpoints and calls the gate. Audit writes route through `write_audit(parent_kind="account", parent_id=account_id, audit_subcollection="project_plan_audit", resource_type=<one of "project_plan"|"plan_task">, action=<registered project-tasks action>, ...)` (registered in DM-PRD-07's audit registry §4.8). Responses use the same `200 / 201 / 403 / 404 / 409 / 422` patterns as the strategy router (with `409` reserved for disallowed transitions).

## 7. Acceptance criteria

1. Posting a valid plan returns `201` with `plan_id` and persists to `accounts/{account_id}/project_plans`
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
10. `GET /api/v1/plans/{account_id}/{plan_id}/execution-order` returns waves whose union equals `{t.task_id for t in plan.tasks}` (no task missed), and no task in wave N depends on any task in wave M > N. Runs in O(V+E) over the plan's DAG.

## 8. Test plan

**Unit tests** (`test_project_plan_models.py`, `test_project_plan_dag_validator.py`):
- DAG validator: empty `depends_on` (root), valid linear chain, valid diamond, simple 2-cycle, self-reference cycle, deep cycle (5 hops), missing reference, single-task plan, large plan (~50 tasks)
- `launch_time_utc` regex: valid (`"00:00"`, `"13:00"`, `"23:59"`), invalid (`"24:00"`, `"1:0"`, `"13:60"`, `""`)
- Status transition rules (where enforced at the model level)
- `TaskStatus` enum accepts all eight values (`Draft`, `Awaiting Approval`, `Approved`, `Rejected`, `Revision Requested`, `Complete`, `Failed`, `Blocked`); a ninth value rejected at parse time

**Integration tests** (`test_project_plans_router.py`):
- Full CRUD lifecycle for one plan
- Versioning: PUT twice, GET history returns 2 entries
- Soft-delete: DELETE then GET returns `404`
- Access control: cross-account access returns `403`
- Audit log records `actor_email`, `action`, `at` for every mutation (schema per DM-PRD-07)
- `GET .../execution-order` on a linear chain (A → B → C) returns `[[A], [B], [C]]`; on a diamond (A → B, A → C, B → D, C → D) returns `[[A], [B, C], [D]]`; on a plan with parallel roots returns the roots in wave 0
- `GET .../execution-order` on an empty plan returns `{waves: []}`
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

- Parent plan: [`../../../project-planning-implementation-plan.md`](../../../project-planning-implementation-plan.md) §Data Model, §API Endpoints, §Implementation Phases (Phase 1)
- Pattern to mirror: `api/src/kene_api/routers/strategy.py`, `api/src/kene_api/models/strategy_models.py`
- CLAUDE.md rules in scope: D-1, D-2, D-5 (database), PY-1, PY-2, PY-7 (Python), T-1, T-3, T-4, T-7, T-8 (testing)
