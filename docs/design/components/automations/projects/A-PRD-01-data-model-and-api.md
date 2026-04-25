# A-PRD-1 — Data Model & API Extensions

**Status:** Blocked — resumes once PR-PRD-01, DM-PRD-00, and DM-PRD-05 ship
**Owner team:** Backend (foundation)
**Blocked by:** PR-PRD-01 (base `ProjectPlan` / `PlanTask` this PRD extends); DM-PRD-00 (provides the `plan_runs` collection-scope composite indexes); DM-PRD-05 (ensures `recursive_delete` covers the new `plan_runs` + artifact subcollections — ship DM-PRD-05 first to avoid an orphaned-data interim)
**Blocks:** A-PRDs 2, 3, 4, 5, 6
**Estimated effort:** 2–3 days

---

## 1. Context

Automations are projects saved for repeated execution. This PRD extends the existing `ProjectPlan` model with the fields that mark a plan as an automation and store its recurrence config, and introduces a new `PlanRun` model that captures a single execution of an automation. It also adds the read endpoints the frontend list page (A-PRD-5) and details page (A-PRD-6) consume.

This is the **foundation** — all other Automations PRDs build against the contract published here.

> **Note on `is_system`:** the `is_system: bool` flag on `ProjectPlan` is defined in Calendar [PRD-1 §4](../../project-tasks/projects/PR-PRD-01-data-model-and-api.md#4-data-contract). This PRD's extensions (automation config fields, `PlanRun`, read endpoints) must consume and respect that flag; the field itself is not re-defined here.

## 2. Scope

### In scope
- Extend `ProjectPlan` with automation fields (`save_as_automation`, `recurrence_cron`, `recurrence_timezone`, `last_run_at`, `last_run_id`, `next_run_at`)
- New `PlanRun` and `TaskRunState` Pydantic models
- New Firestore subcollection `accounts/{account_id}/plan_runs` (Shape B layout)
- Composite indexes for filtered/paginated automation queries
- Cron + IANA timezone validators on the model
- Read endpoints for the list page (with filters + cursor pagination) and details page
- PATCH endpoint to update recurrence config
- Unit tests for validators and pagination helper; integration tests for endpoints

### Out of scope (handled by other PRDs)
- The scheduler tick that consumes `next_run_at` (A-PRD-2)
- The endpoint that creates a `PlanRun` from a template (A-PRDs 2 + 4)
- Artifact data model (A-PRD-3)
- Test-mode endpoint behavior (A-PRD-4)

## 3. Dependencies

- **PR-PRD-01 (Project Tasks — Data Model & API):** extends the existing `ProjectPlan` / `PlanTask` models; reuses `accounts/{account_id}/project_plans` subcollection.
- **DM-PRD-00 (Migration Foundation):** hard prerequisite. Provisions the two `plan_runs` collection-scope composite indexes (`template_plan_id ASC, started_at DESC` and `template_plan_id ASC, is_test ASC, started_at DESC`) in `deployment/firestore.indexes.json` and wraps them via `deployment/terraform/firestore_indexes.tf`. This PRD verifies the indexes are present and consumes them; it does not create or modify those index resources.
- **DM-PRD-05 (Deletion Sweep Rewrite):** hard prerequisite. DM-PRD-05 replaces the enumerated sweep in `routers/accounts.py:968-997` with `firestore.recursive_delete(accounts/{account_id})`, which automatically covers the new `plan_runs` subcollection and its nested `artifacts/` subcollection (A-PRD-3). Without it, `DELETE /accounts/{account_id}` would orphan plan-run and artifact metadata.
- **External:** `croniter` (cron parsing + next-fire computation), `zoneinfo` (stdlib timezone validation)
- **Existing files to study:**
  - `api/src/kene_api/models/project_plan_models.py` (PR-PRD-01)
  - `api/src/kene_api/routers/project_plans.py` (PR-PRD-01) — pattern to mirror
  - `api/src/kene_api/services/firestore_service.py` (pagination helper)

## 4. Data contract

### `ProjectPlan` — fields added

```
save_as_automation: bool = False
recurrence_cron: str | None = None          # 5-field cron, UTC interpretation if no tz
recurrence_timezone: str = "UTC"            # IANA name; controls cron interpretation
last_run_at: datetime | None = None
last_run_id: str | None = None
next_run_at: datetime | None = None         # set by A-PRD-2 scheduler after each fire

# Plan classification — added by this PRD to align with the Figma frontend's
# Projects / Dashboard split. Consumed by PR-PRD-07 (Calendar Activities) and
# by the Dashboard frontend.
type: Literal["freeform", "dashboard"] = "freeform"
                                            # freeform = user-defined DAG of tasks (default;
                                            # matches PR-PRD-01's implicit behavior).
                                            # dashboard = a dashboard-placement plan. No
                                            # runtime behavior change here; the Dashboard
                                            # frontend renders based on this discriminator.

# External linkage — added here because Automations care about both values
# (routing a run to a specific extension; scoring progress against a goal).
# Both are nullable and uninterpreted at this layer; consumers (extensions
# registry, goals service) resolve them at use-time.
extension_id: str | None = None             # FK to an entry in the extensions registry;
                                            # used by the orchestrator (A-PRD-2) when a run
                                            # should dispatch through a specific extension
goal_id: str | None = None                  # FK to a Goal document; used by reporting and
                                            # by the Dashboard frontend to group plans
```

### `PlanRun` — new model

```
run_id: str                                 # UUID
account_id: str
template_plan_id: str                       # FK to ProjectPlan
template_version: int                       # snapshot of template version at trigger time
triggered_by: Literal["scheduled", "manual", "test", "system"]
triggered_by_user_id: str | None            # for manual / test; null for scheduled / system
is_test: bool = False
inputs: dict | None = None                  # per-run context (e.g., session_id, source refs).
                                            # Substituted into agent prompts via {inputs.*}
                                            # template syntax. Owned by A-PRD-2.
status: RunStatus                           # pending | running | halted_for_human |
                                            # complete | failed | cancelled
task_states: list[TaskRunState]
started_at: datetime
completed_at: datetime | None = None
created_at: datetime
updated_at: datetime
version: int
```

### `triggered_by="system"` and `inputs`

`triggered_by="system"` is used by platform services (not user actions, not Cloud Scheduler's recurring tick) that need to kick off a run imperatively — e.g. the Knowledge Graph session-end sweeper (KG-PRD-04). `inputs` carries the context that run needs (session id, account id, transcript reference, etc.) and is surfaced to dispatched agents via prompt-template substitution. A-PRD-2 owns the substitution mechanism; this PRD only owns the field.

Shape of `inputs` is opaque at the data-model layer — a JSON object. Individual consuming PRDs (e.g. KG-PRD-04) document the keys they write and read. The scheduler tick (also A-PRD-2) leaves `inputs=null` for scheduled runs; the manual "Run now" endpoint passes through whatever the caller sends.

### `TaskRunState` — per-task execution snapshot

```
task_id: str                                # references template's PlanTask.task_id
status: TaskStatus                          # same enum as Calendar PRD-1
started_at: datetime | None
completed_at: datetime | None
assignee_dispatched: str | None             # agent name or user_id
revision_iteration: int = 0
completion_notes: str | None = None
revision_comment: str | None = None
```

### Validators

- `recurrence_cron`: parsed with `croniter.is_valid(cron_expr)`; reject if invalid. Must be a 5-field expression (no seconds, no year).
- `recurrence_timezone`: `zoneinfo.ZoneInfo(name)` must succeed.
- `save_as_automation == True` → `is_active` must be set (defaults are fine).
- `next_run_at` is read-only via the API (computed server-side by A-PRD-2).
- `type`: one of `"freeform"` or `"dashboard"`. Mutable (a plan can be re-classified by the UI).
- `extension_id` / `goal_id`: opaque strings. The model does not verify existence of the referenced entity; resolution is lazy at use-time (extensions registry, goals service).

### Pagination contract

All list endpoints accept:
- `page_size: int = 25` (max 100)
- `cursor: str | None` — opaque base64-encoded cursor of the last doc's sort key + id

Responses include:
```
{
  "items": [...],
  "next_cursor": "..." | null,
  "total_count_estimate": 1234   // optional, may be omitted if expensive
}
```

## 5. Implementation outline

| Action | File |
|--------|------|
| Modify | `api/src/kene_api/models/project_plan_models.py` — add fields + validators |
| Create | `api/src/kene_api/models/plan_run_models.py` — `PlanRun`, `TaskRunState`, `RunStatus` enum |
| Create | `api/src/kene_api/routers/automations.py` — list / get / runs-list / runs-get / patch-recurrence endpoints |
| Modify | `api/src/kene_api/main.py` — register router under `/api/v1/automations` |
| Create | `api/src/kene_api/services/automation_query.py` — filter + cursor pagination helper |
| Create | `deployment/terraform/firestore_indexes_automations.tf` — the **4 `project_plans` collection-scope** composite indexes for the list page filters (below). The two `plan_runs` collection-scope indexes ship from DM-PRD-00 — do **not** re-declare them here. |
| Verify | `deployment/firestore.indexes.json` already contains the two `plan_runs` collection-scope composite indexes (`template_plan_id ASC, started_at DESC` and `template_plan_id ASC, is_test ASC, started_at DESC`) shipped by DM-PRD-00. Coordinate with the DM-PRD-00 owner if a field needs to change. |
| Create | `api/tests/unit/test_automation_validators.py` |
| Create | `api/tests/unit/test_automation_pagination.py` |
| Create | `api/tests/integration/test_automations_router.py` |

### Firestore layout (delta from Calendar PRD-1)

> **Revised 2026-04-20** — Firestore paths follow the Shape B layout (`accounts/{account_id}/{resource}/...`). See [Multi-Tenant Data Model Shape Decision](https://www.notion.so/34830fd653028177bc0dc2a1637c7f60) for rationale.

```
accounts/{account_id}/project_plans/{plan_id}                        # template (extended)
accounts/{account_id}/plan_runs/{run_id}                             # NEW: per-execution doc
accounts/{account_id}/plan_runs/{run_id}/artifacts/{artifact_id}     # NEW: A-PRD-3 owns
accounts/{account_id}/project_plan_audit/{audit_id}                  # existing; new entry types
                                                                     #   for run lifecycle events
```

### Composite indexes

This PRD owns the **4 `project_plans` collection-scope indexes** for the list page filter combinations (declared in `firestore_indexes_automations.tf`). Indexes are scoped to the account's subcollection (`queryScope: COLLECTION`) for single-account reads:

```
collection: accounts/*/project_plans   (queryScope: COLLECTION)  — owned by this PRD
  fields: [save_as_automation ASC, is_system ASC, is_active ASC, updated_at DESC]
  fields: [save_as_automation ASC, is_system ASC, status ASC, updated_at DESC]
  fields: [save_as_automation ASC, is_system ASC, campaign ASC, updated_at DESC]
  fields: [save_as_automation ASC, is_system ASC, created_by ASC, updated_at DESC]
```

The **2 `plan_runs` collection-scope indexes** consumed by the runs-list endpoint ship from DM-PRD-00 — this PRD only verifies their presence:

```
collection: accounts/*/plan_runs   (queryScope: COLLECTION)  — owned by DM-PRD-00
  fields: [template_plan_id ASC, started_at DESC]
  fields: [template_plan_id ASC, is_test ASC, started_at DESC]
```

Cross-account reads (e.g., the scheduler's due-task query under PR-PRD-06) use collection-group indexes on `project_plans` — also owned by DM-PRD-00, not duplicated here.

Every automation list query includes `is_system` as a leading equality filter (default `false`), so the composite indexes above lead with `save_as_automation, is_system`. Tags filter uses `array_contains_any` (no composite index needed beyond the base filters).

## 6. API contract

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/automations/{account_id}` | List automations. Query params: `goal` (substring), `campaign[]`, `tags[]`, `status[]`, `created_by[]`, `is_active`, `is_system` (default `false`), `cursor`, `page_size` |
| `GET` | `/api/v1/automations/{account_id}/{plan_id}` | Fetch one automation enriched with `last_run_at`, `next_run_at`, `last_run.status` |
| `PATCH` | `/api/v1/automations/{account_id}/{plan_id}/recurrence` | Body: `{recurrence_cron, recurrence_timezone, is_active}` — updates schedule config. A-PRD-2 will re-compute `next_run_at` on the next tick. |
| `GET` | `/api/v1/automations/{account_id}/{plan_id}/runs` | List runs for an automation. Query params: `is_test`, `status[]`, `cursor`, `page_size` |
| `GET` | `/api/v1/automations/{account_id}/{plan_id}/runs/{run_id}` | Fetch one run with `task_states` |

Endpoints reuse the existing access-control dependency (`check_strategy_access`-equivalent). Cross-account requests return `403`.

## 7. Acceptance criteria

1. Setting `save_as_automation=true` on a `ProjectPlan` succeeds; `GET /api/v1/automations/{account_id}` returns it
2. Setting `recurrence_cron="0 9 * * MON"` and `recurrence_timezone="America/Los_Angeles"` is accepted; invalid cron or invalid timezone returns `422`
3. List endpoint with `campaign=["Spring"]&status=["active"]` returns only matching automations; pagination cursor walks the full result set without duplicates or skips
4. Patching `recurrence_cron` updates the field and clears `next_run_at` (so A-PRD-2's next tick will re-compute it)
5. A `PlanRun` doc can be created (manually for tests; A-PRD-2 owns the production path) and is returned by the runs-list endpoint
5a. The `inputs` field on `PlanRun` round-trips through create + fetch without coercion (stored as a nested map in Firestore, returned as a JSON object)
5b. The `triggered_by` enum accepts `"system"` as a valid value
5c. The list endpoint defaults `is_system=false` when the query param is absent; explicit `?is_system=true` returns only system templates (used only for debugging — not surfaced in the UI, see A-PRD-5)
5d. `PATCH /api/v1/automations/{account_id}/{plan_id}/recurrence` on a plan where `is_system=true` returns `403` (system templates have no user-editable schedule). The corresponding write-rejection rules for `PUT /api/v1/plans/{account_id}/{plan_id}`, `PATCH .../tasks/{task_id}`, and `DELETE /api/v1/plans/{account_id}/{plan_id}` are owned by Calendar PRD-1 since they live on its endpoints.
5e. `type` round-trips: `POST` with `type="dashboard"` persists and `GET` returns it. `type` unset on a create defaults to `"freeform"`. Invalid value → `422`.
5f. `extension_id` and `goal_id` round-trip as opaque strings: `POST` with values persists; `GET` returns them unchanged; `None` is accepted and returned.
6. Cross-account access returns `403` on every endpoint
7. The 4 `project_plans` collection-scope composite indexes owned by this PRD are present in `firestore_indexes_automations.tf`; the 2 `plan_runs` collection-scope indexes shipped by DM-PRD-00 are verified to exist in `deployment/firestore.indexes.json` before merging. The Firestore emulator runs all list / runs-list queries without scan-warning logs.
8. All unit and integration tests pass

## 8. Test plan

**Unit tests** (`test_automation_validators.py`):
- Valid 5-field crons: `"* * * * *"`, `"0 9 * * MON"`, `"*/15 * * * *"`, `"0 0 1 1 *"`
- Invalid: empty, 6-field, `"every monday"`, `"60 * * * *"`
- Valid timezones: `UTC`, `America/Los_Angeles`, `Europe/London`, `Asia/Tokyo`
- Invalid: empty, `"PST"` (abbrev), `"Mars/Olympus"`
- `save_as_automation=False` with `recurrence_cron` set → allowed (no schedule, no automation behavior)
- `triggered_by="system"` with `triggered_by_user_id=None` → allowed; with a user_id → allowed (caller's choice)
- `inputs={"session_id": "s_123", "account_id": "a_456"}` → round-trips; deeply nested maps round-trip; `inputs=None` round-trips
- `type`: accepts `"freeform"` / `"dashboard"`; rejects `"workflow"`, empty, or null on create (defaults to `"freeform"` if omitted in the request)
- `extension_id` / `goal_id`: accept any non-empty string or `None`; whitespace-only rejected

**Unit tests** (`test_automation_pagination.py`):
- Cursor encode/decode round-trip
- Empty result set → `next_cursor=null`
- Last page → `next_cursor=null`
- Page boundary: 26 items, page_size=25 → first page returns 25 + cursor; second page returns 1 + null

**Integration tests** (`test_automations_router.py`):
- Full list with no filters returns all automations for the account
- Filter combinations: each filter alone, two together, all together
- Cursor pagination across 100 automations matches a non-paginated control list
- PATCH recurrence: valid cron updates field; invalid → 422; cross-account → 403
- Runs list: empty (new automation) → empty; with 5 runs → 5 returned
- `is_test=true` filter on runs list returns only test runs

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| `croniter` semantics differ subtly from Cloud Scheduler's cron parser | Use `croniter` exclusively (not Cloud Scheduler's parser). Document the supported syntax in the model docstring. |
| Tag filter with multiple tags: AND vs OR semantics | Default to OR (`array_contains_any`); document. AND requires app-side filtering. |
| `total_count_estimate` may be expensive at scale | Optional in v1 — frontend can hide it; revisit if product wants it |
| `template_version` snapshot vs. live template | A-PRD-2 snapshots template_version at trigger time so a run reflects the recipe as it was when fired, not as edited later. Document the contract here so the run-engine PRD inherits it. |

## 10. Reference

- Parent plan: [`../README.md`](../README.md) §3 (Data model)
- Calendar foundation: [Calendar PRD-1](../../project-tasks/projects/PR-PRD-01-data-model-and-api.md)
- Pattern files: `api/src/kene_api/routers/project_plans.py`, `api/src/kene_api/services/firestore_service.py`
- CLAUDE.md rules in scope: D-1, D-2, D-5; PY-1, PY-2, PY-7; T-1, T-3, T-4, T-7, T-8
