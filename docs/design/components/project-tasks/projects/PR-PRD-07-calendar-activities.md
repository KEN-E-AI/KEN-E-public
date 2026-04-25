# PR-PRD-07 — Calendar Activities (Multi-Category Model)

**Status:** Blocked — resumes after PR-PRD-01, PR-PRD-08, and DM-PRD-07 ship
**Owner team:** Backend
**Blocked by:** PR-PRD-01 (base `ProjectPlan` / `PlanTask` this PRD extends); PR-PRD-08 (Campaign Management — activities reference `Campaign` via `campaign_id`); DM-PRD-07 (Approval Workflow & Audit — transition gating + audit schema this PRD consumes)
**Blocks:** PR-PRD-03 (Calendar page frontend — depends on this contract for the four activity categories, orphan-task endpoints, batch/group operations)
**Estimated effort:** 3–4 days

---

## 1. Context

The Figma-designed Calendar page models a `CalendarActivity` with four categories (`task`, `promotion`, `holiday`, `event`) unified in one collection. PR-PRD-01 delivers a single uniform `PlanTask` with a status lifecycle and DAG, but no notion of category, no sparse per-category fields (promotion discount, holiday type, region, etc.), no orphan-task lifecycle, and no batch / group operations.

This PRD extends `PlanTask` — rather than introducing a parallel `Activity` type — so the Calendar page, the Projects page, and the Automations runtime all read and write the same document shape. All extensions are optional-by-default; an `is_system=true` plan and an existing user plan continue to validate unchanged.

Orphan tasks (tasks with `plan_id = null` or `unscheduled = true`) are first-class: they appear in the Calendar's Unscheduled Tasks panel, are owner-scoped, and can be moved into an existing plan or into a newly-created plan atomically.

## 2. Scope

### In scope
- Extend `PlanTask` with: `category`, `channel`, `task_type`, `owner_email`, `unscheduled`, a task-level recurrence schedule, and category-specific sparse fields for promotion and holiday
- Category validators (promotion requires `promotion_type`; holiday requires `holiday_type`; `unscheduled=true` forbids `due_date`)
- Orphan-task lifecycle: list-for-user, attach-to-existing-plan, atomic create-plan-and-attach, detach-from-plan
- Batch activity creation endpoint (Batch Activity Wizard): multi-day with per-day overrides, transactional
- Group edit endpoint: patch N tasks in a single request
- Full filter enumeration on the list endpoint (status, category, owner, platform, channel, campaign_id, plan_id, date-range, tags, task_type, activity_type)
- `detach_from_plan` semantics (moving a task out of a plan produces an orphan task)
- Unit tests for validators and the category discriminator; integration tests for orphan lifecycle, batch create, and group edit

### Out of scope
- Campaign CRUD (PR-PRD-08)
- Approval-transition gating and audit log persistence (DM-PRD-07)
- Schedule-preview endpoint for expanding task-level recurrence in a window (A-PRD-2 update — adds `POST /v1/schedules/preview` used by the frontend Calendar grid)
- Automation / plan-level scheduling (A-PRD-1 / A-PRD-2 — plan-level `recurrence_cron` is unchanged)
- Frontend changes (tracked in PR-PRD-03)

## 3. Dependencies

- **PR-PRD-01 (Project Plan Data Model & API):** extends `PlanTask`, reuses the `accounts/{account_id}/project_plans` subcollection and versioning, reuses the DAG validator and audit pattern.
- **PR-PRD-08 (Campaign Management):** activities reference a `Campaign` via the existing `campaign_id` field (typed string now; becomes FK to the Campaign collection once PR-PRD-08 ships). The "generic fallback campaign per objective" is seeded by PR-PRD-08 at account creation and consumed here when a user submits an activity with no campaign selected.
- **DM-PRD-07 (Approval Workflow & Audit):** provides the role-based transition gate the create / patch / batch / group-edit endpoints call into. The audit-log document shape this PRD writes into `project_plan_audit/` is owned by DM-PRD-07; this PRD only supplies before/after snapshots.
- **A-PRD-2 update (Schedule Preview):** the frontend Calendar grid reads task-level recurrence through `POST /v1/schedules/preview`; this PRD ships only the storage of the schedule, not the occurrence-expansion endpoint.
- **DM-PRD-05 (Deletion Sweep Rewrite):** the new endpoints operate on subcollections already covered by `recursive_delete`; no new delete paths to audit.
- **Existing files to study:** `api/src/kene_api/models/project_plan_models.py`, `api/src/kene_api/routers/project_plans.py`, `api/src/kene_api/services/firestore_service.py`.

## 4. Data contract

### `PlanTask` — fields added

```
category: Literal["task", "promotion", "holiday", "event"] = "task"
channel: str | None = None                 # "Paid Search", "Social", "Email", ...
task_type: str | None = None               # "Brand", "Demand Gen", ... (free-form typeahead)
owner_email: str | None = None             # human owner (distinct from assignee_name;
                                           # assignee_name holds agent/automation target)
unscheduled: bool = False                  # true → task has no due_date and is an orphan-panel
                                           # candidate until scheduled, assigned, or deleted

# Task-level recurrence (distinct from plan-level recurrence on ProjectPlan).
# When set + enabled, the Calendar grid shows virtual occurrences expanded in-view
# via POST /v1/schedules/preview. No materialized occurrence rows are persisted.
recurrence_cron: str | None = None         # 5-field cron; same parser/format as A-PRD-1
recurrence_timezone: str = "UTC"           # IANA name; same validator as A-PRD-1
recurrence_enabled: bool = False

# Promotion-specific (sparse — required only when category == "promotion")
product_service: str | None = None
promotion_type: Literal[
    "Discount", "Bundle", "Free Trial", "BOGO",
    "Flash Sale", "Seasonal", "Launch Offer"
] | None = None
discount_details: str | None = None
end_date: date | None = None               # promotion end date (distinct from due_date)
promo_url: str | None = None
region: str | None = None

# Holiday-specific (sparse — required only when category == "holiday")
holiday_type: Literal[
    "Public", "Religious", "Cultural", "Observance", "Company"
] | None = None
recurring: bool = False                    # "does this holiday repeat annually?" — boolean
                                           # flag only; no cron. Distinct from recurrence_cron.
```

Event category has no additional fields in v1 — it reuses the base `PlanTask` shape.

### `ProjectPlan` — fields added

```
type: Literal["freeform", "dashboard"] = "freeform"
                                           # freeform = user-defined DAG (default, matches
                                           # the current implicit behavior). dashboard = a
                                           # dashboard-placement plan (shape per frontend
                                           # Dashboard page; no runtime behavior change).
```

### Validators (model-level)

- `category == "promotion"` → `promotion_type` is not None
- `category == "holiday"` → `holiday_type` is not None
- `unscheduled == True` → `due_date is None` AND `launch_time_utc is None`
- `recurrence_enabled == True` → `recurrence_cron` is not None and `croniter.is_valid(recurrence_cron)`
- `recurrence_timezone` validated via `zoneinfo.ZoneInfo(name)` (reuse helper from A-PRD-1)
- Existing `launch_time_utc` regex and DAG validator unchanged

### Orphan-task semantics

An orphan task is any `PlanTask` stored at the top-level orphan subcollection (see §5 Firestore layout) — i.e. not a member of any plan's `tasks` list. Two operations exist:

- **Attach to existing plan.** Transactionally: remove from orphan subcollection; append to target plan's `tasks`; re-run the DAG validator on the target plan.
- **Attach to new plan.** Transactionally: create a new `ProjectPlan` from a minimal payload (title, optional goal); attach the task as above. Single transaction, single audit entry pair.
- **Detach from plan.** Transactionally: remove from plan's `tasks`; copy to orphan subcollection; prune any `depends_on` edges that referenced the detached task.

## 5. Implementation outline

| Action | File |
|--------|------|
| Modify | `api/src/kene_api/models/project_plan_models.py` — add fields, category discriminator, sparse-field validators, `type` enum on `ProjectPlan` |
| Modify | `api/src/kene_api/routers/project_plans.py` — extend list-endpoint filters; add batch-create and group-edit endpoints |
| Create | `api/src/kene_api/routers/orphan_tasks.py` — list / attach-to-plan / attach-to-new-plan / detach endpoints |
| Create | `api/src/kene_api/services/orphan_task_service.py` — transaction-level primitives |
| Modify | `api/src/kene_api/main.py` — register orphan-tasks router |
| Create | `api/tests/unit/test_plan_task_category_validators.py` |
| Create | `api/tests/unit/test_orphan_task_service.py` |
| Create | `api/tests/integration/test_orphan_tasks_router.py` |
| Create | `api/tests/integration/test_activities_batch_and_group_edit.py` |
| Modify | `deployment/terraform/firestore_indexes_project_tasks.tf` — add composite indexes for the new filters (see below) |

### Firestore layout (delta from PR-PRD-01)

```
accounts/{account_id}/project_plans/{plan_id}                         # PR-PRD-01 (extended)
accounts/{account_id}/project_plans/{plan_id}/versions/{n}            # PR-PRD-01
accounts/{account_id}/project_plan_audit/{audit_id}                   # PR-PRD-01 + DM-PRD-07

# NEW — orphan tasks: tasks not attached to any plan.
accounts/{account_id}/orphan_tasks/{task_id}                          # NEW
```

Rationale: orphan tasks are queried as their own collection ("list mine, newest first, optionally filtered"); nesting them under a phantom plan would force every query to traverse plan membership. A separate subcollection is simpler and mirrors how `plan_runs` relates to `project_plans`.

### Composite indexes (orphan_tasks)

```
collection: accounts/*/orphan_tasks   (queryScope: COLLECTION)
  fields: [owner_email ASC, updated_at DESC]
  fields: [owner_email ASC, category ASC, updated_at DESC]
  fields: [unscheduled ASC, owner_email ASC, updated_at DESC]
```

### Composite indexes (project_plans — added filters)

The PR-PRD-01 list endpoint already filters by `status`, `campaign`, `tag`. This PRD adds filters that the Calendar list/grid views require:

```
collection: accounts/*/project_plans   (queryScope: COLLECTION)
  # For tasks-within-a-plan slices driven by the Calendar filter bar, the query
  # is executed client-side on the `tasks` array within a plan doc (Firestore
  # array-of-maps is not index-able by subfield at scale). No new composite
  # index; the work is in the application-layer filter loop.
```

If profiling in staging shows the app-layer filter loop too slow for accounts with >200 plans, follow up by flattening `tasks` into a subcollection (`project_plans/{plan_id}/tasks/{task_id}`) — that's a larger migration owned by DM, out of scope here.

## 6. API contract

### Activities (within a plan)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/plans/{account_id}` | List plans (PR-PRD-01). **Extended filter set:** `status[]`, `category[]`, `owner_email[]`, `platform[]`, `channel[]`, `campaign_id[]`, `plan_id[]`, `task_type[]`, `tags[]`, `from` (ISO date), `to` (ISO date), `is_active`, `cursor`, `page_size` |
| `POST` | `/api/v1/plans/{account_id}/{plan_id}/tasks/batch` | Batch-create tasks in one transaction. Body: `{tasks: PlanTaskCreate[], shared_fields?: Partial<PlanTask>}` where each entry in `tasks` is merged over `shared_fields` — enabling the Wizard's multi-day + per-day override flow |
| `PATCH` | `/api/v1/plans/{account_id}/{plan_id}/tasks:group-edit` | Group-edit. Body: `{task_ids: string[], patch: Partial<PlanTask>}` — applies the same patch to every listed task in one transaction, writing one audit entry per task |

### Orphan tasks (no plan membership)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/orphan-tasks/{account_id}` | List orphan tasks for the account. Query params: `owner_email[]` (defaults to caller's email), `category[]`, `cursor`, `page_size` |
| `POST` | `/api/v1/orphan-tasks/{account_id}` | Create an orphan task. Body: full `PlanTaskCreate` shape (category etc.); if `unscheduled=true`, `due_date` MUST be absent |
| `PATCH` | `/api/v1/orphan-tasks/{account_id}/{task_id}` | Update orphan task (audit-logged) |
| `DELETE` | `/api/v1/orphan-tasks/{account_id}/{task_id}` | Soft-delete orphan task |
| `POST` | `/api/v1/orphan-tasks/{account_id}/{task_id}/attach-to-plan` | Body: `{plan_id: string}`. Moves the task into the target plan. Transaction. |
| `POST` | `/api/v1/orphan-tasks/{account_id}/{task_id}/attach-to-new-plan` | Body: `{plan: ProjectPlanCreate}`. Creates plan + attaches task in one transaction. Returns `{plan_id, task_id}` |
| `POST` | `/api/v1/plans/{account_id}/{plan_id}/tasks/{task_id}/detach` | Removes the task from its plan, placing it in `orphan_tasks`, pruning any `depends_on` references to it |

All endpoints use the existing account-scoped access-control dependency. Approval-sensitive transitions (e.g. patching `status` into `Approved`) defer to DM-PRD-07's role gate — this PRD calls the gate but does not own its implementation.

## 7. Acceptance criteria

1. Posting a `PlanTask` with `category="promotion"` and no `promotion_type` returns `422` with a message naming the missing required field. Same for `category="holiday"` without `holiday_type`.
2. Posting a task with `unscheduled=true` and any of `due_date`, `launch_time_utc` set returns `422`.
3. Posting a task with `recurrence_enabled=true` and no `recurrence_cron` returns `422`. An invalid cron string returns `422`.
4. `GET /api/v1/plans/{account_id}?category=promotion&from=2026-05-01&to=2026-05-31` returns only promotion-category tasks with `due_date` in range.
5. `POST /tasks/batch` with 7 task payloads and `shared_fields={campaign_id: "cc-6"}` creates 7 tasks, each carrying `campaign_id="cc-6"`, in one Firestore transaction. Writing one audit entry per task is acceptable.
6. `PATCH /tasks:group-edit` with `{task_ids: [t1, t2, t3], patch: {owner_email: "a@b.com"}}` sets `owner_email` on all three in one transaction.
7. `POST /api/v1/orphan-tasks/{account_id}` creates an orphan task at `accounts/{account_id}/orphan_tasks/{task_id}`. `GET` with default filters returns it. The task is not visible in any plan's `tasks` array.
8. `POST /orphan-tasks/{id}/attach-to-plan` moves the task from `orphan_tasks` into the target plan's `tasks`; subsequent `GET /orphan-tasks/{account_id}` does not include it; `GET /plans/{account_id}/{plan_id}` does. Source and target updates are in one transaction.
9. `POST /orphan-tasks/{id}/attach-to-new-plan` creates a new plan with the supplied title and attaches the task — a single transaction, no orphaned plan if the task step fails. Returns both IDs.
10. `POST /plans/{account_id}/{plan_id}/tasks/{task_id}/detach` removes the task and prunes any `depends_on` references to the detached task from siblings. The DAG validator runs after the prune.
11. `type="dashboard"` is accepted on a plan create and round-trips; no runtime behavior changes.
12. All new endpoints return `403` for cross-account requests.
13. All composite indexes for `orphan_tasks` exist in `firestore_indexes_project_tasks.tf`; emulator runs the new queries without scan warnings.
14. All unit and integration tests pass; `make lint` clean.

## 8. Test plan

**Unit tests** (`test_plan_task_category_validators.py`):
- Each category with complete required fields → accepted
- Each category missing its discriminant field → `422` with a clear message
- `unscheduled=true` combinations (with/without `due_date`, with/without `launch_time_utc`)
- `recurrence_enabled=true` combinations (with/without `recurrence_cron`, invalid cron, invalid tz)
- `type` enum on `ProjectPlan`: `freeform`, `dashboard`, rejected value

**Unit tests** (`test_orphan_task_service.py`):
- `attach_to_plan`: orphan doc removed, plan doc updated with appended task, DAG re-validated
- `attach_to_new_plan`: new plan created, task attached, if the task-attach step raises the transaction rolls back and no orphaned plan remains
- `detach`: task copied to orphan subcollection, plan's `tasks` list shortened, `depends_on` references pruned from siblings
- Concurrency: two simultaneous `attach_to_plan` calls for the same task → one succeeds, one returns `409`

**Integration tests** (`test_orphan_tasks_router.py`):
- Full lifecycle: create → list → attach-to-plan → absent from list → detach → present in list → delete → absent
- Cross-account access returns `403` on every endpoint
- `attach-to-new-plan` returns `{plan_id, task_id}`; the plan is retrievable via PR-PRD-01's `GET /plans/{account_id}/{plan_id}`
- Default `owner_email` filter is the caller's email; explicit `owner_email` filter returns the specified user's orphans

**Integration tests** (`test_activities_batch_and_group_edit.py`):
- Batch create: 5 tasks → all 5 present, shared field applied, individual overrides preserved
- Batch create with one invalid entry → entire batch rolls back; none persisted
- Group edit: 3 task IDs → 3 tasks patched; one audit entry per task
- Group edit with one unknown task ID → `422`, no partial application

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| Task-level recurrence and plan-level recurrence could be confused | Distinct field names (`recurrence_cron` lives on both but the Pydantic models are separate) and docstring callouts. Frontend clearly models them as different settings (Repeat toggle on task vs. Save-as-Automation on plan). |
| App-layer filter over `tasks` array could be slow for accounts with many plans | Measured in staging; if p95 list latency exceeds 250ms, flatten `tasks` into a subcollection (tracked as a follow-up migration, not in this PRD) |
| `orphan_tasks` and plan `tasks` drift out of sync if attach/detach transactions fail mid-write | Single Firestore transaction for both operations is the canonical guard. Integration test covers the rollback case. |
| Category-specific sparse fields bloat the doc | Promotion/holiday fields are optional and rare relative to `task`. Firestore handles sparse fields without penalty. |
| `PlanTask.assignee_name` vs. `owner_email` overlap | Documented: `assignee_name` is the agent or automation target (who *executes*); `owner_email` is the human responsible (who *approves / owns the outcome*). Both can coexist on a single task. |
| Batch create — transactional size limits (Firestore: 500 ops/txn) | Cap batch size at 100 entries; return `413` if exceeded. Document. |
| Generic fallback campaign resolution when `campaign_id is None` | Owned by PR-PRD-08. This PRD stores whatever the client sends; resolution happens at campaign read time. |

## 10. Reference

- Foundation: [PR-PRD-01](./PR-PRD-01-data-model-and-api.md) §4 data contract, §6 API contract
- Campaigns: [PR-PRD-08](./PR-PRD-08-campaign-management.md)
- Approval + audit: [DM-PRD-07](../../data-management/projects/DM-PRD-07-approval-workflow-and-audit.md)
- Schedule preview: [A-PRD-2](../../automations/projects/A-PRD-02-recurring-scheduler.md) §6 (updated to add the preview and upcoming endpoints)
- Frontend context: `docs/figma-export/src/app/data/calendarData.ts` (`CalendarActivity`, category enums, sparse field shapes), `docs/figma-export/src/app/data/standaloneTasks.ts` (orphan-task pattern), `docs/figma-export/src/app/pages/CalendarPage.tsx` (batch wizard, group edit, Unscheduled panel, Move-to-Project dialog)
- CLAUDE.md rules in scope: C-1, C-5; D-1, D-2, D-5; PY-1, PY-2, PY-7; T-1, T-3, T-4, T-7, T-8
