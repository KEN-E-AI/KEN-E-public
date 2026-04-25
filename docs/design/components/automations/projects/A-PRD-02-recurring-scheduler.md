# A-PRD-2 — Recurring Scheduler & Run Engine

**Status:** Ready for development (after A-PRD-1, PR-PRD-04, and PR-PRD-06 merge)
**Owner team:** Backend / Infra
**Blocked by:** A-PRD-1; PR-PRD-04 (`TaskOrchestrator` — extended here with an optional `run_id` parameter); PR-PRD-06 (Cloud Scheduler Terraform + SA — reused for the sibling `launch-due-automations` job)
**Parallel with:** A-PRDs 3, 5, 6
**Estimated effort:** 3 days

---

## 1. Context

A-PRD-1 publishes the `recurrence_cron` field on `ProjectPlan` and the `PlanRun` model, but nothing actually fires automations on schedule. This PRD builds that engine: a once-per-minute Cloud Scheduler tick that finds automations whose `next_run_at <= now`, clones the template into a new `PlanRun`, and hands the run to the `TaskOrchestrator` (Calendar PRD-4) for execution.

It also delivers the manual-trigger endpoint that a user invokes from the Automation Details page ("Run now") — same engine, different `triggered_by`.

This PRD reuses the Cloud Scheduler infrastructure delivered by [Calendar PRD-6](../../project-tasks/projects/PR-PRD-06-time-based-scheduler.md) but adds a sibling endpoint, since per-task firing and per-automation firing have different queries and different downstream paths.

## 2. Scope

### In scope
- `AutomationRunEngine` service: clones a template into a `PlanRun`, computes next fire time, dispatches via the orchestrator
- New internal endpoint `POST /api/v1/internal/scheduler/launch-due-automations` (OIDC, called by Cloud Scheduler)
- New manual-trigger endpoint `POST /api/v1/automations/{account_id}/{plan_id}/runs` (user-auth) accepting `triggered_by` ∈ {`"manual"`, `"system"`} and an optional `inputs: dict`
- **New public preview endpoint `POST /api/v1/schedules/preview`** (user-auth) — given a schedule config and a date window, returns the occurrence dates. Used by the Calendar grid to expand task-level recurrence in the visible window and by the Activity-form UI to show a human-readable preview of a schedule the user is editing.
- **New public upcoming-runs endpoint `GET /api/v1/automations/{account_id}/schedules/upcoming`** (user-auth) — given a date window, lists automations whose scheduled occurrences fall in the window along with the occurrence dates. Used by the Calendar's "Projects in view" panel.
- Cloud Scheduler resource (Terraform) — same SA as Calendar PRD-6, sibling job
- Extension to `TaskOrchestrator.activate_plan` and `on_task_status_change`: optional `run_id` parameter; when present, status reads/writes target the `PlanRun` doc instead of the template
- **Inputs template substitution in the orchestrator's prompt builder**: when a run carries `inputs`, agent-task prompts get `{inputs.key}` placeholders replaced at dispatch time (owned here; consumed by KG-PRD-04 and any other system-triggered automation)
- `croniter`-based next-fire computation with explicit IANA timezone
- Backfill policy: only fire ONCE for "now" after server downtime (no missed-run replay)
- Idempotency: single Firestore transaction guards "compute next_run_at + create PlanRun" so a Cloud Scheduler retry never double-fires
- Unit + integration tests with a fake clock

### Out of scope
- The artifact system (A-PRD-3)
- Test-mode endpoint behavior (A-PRD-4) — though both PRDs touch the same orchestrator extension; coordinate
- The Frontend trigger UX (A-PRD-6)

## 3. Dependencies

- **A-PRD-1:** `ProjectPlan.recurrence_cron`, `next_run_at`, `PlanRun` model
- **Calendar PRD-4:** `TaskOrchestrator.activate_plan` — this PRD extends its signature with optional `run_id`
- **Calendar PRD-6:** Cloud Scheduler infrastructure + OIDC auth dependency — reuse
- **External:** `croniter`, `zoneinfo`, Cloud Scheduler (GCP)

### Coordination — orchestrator signature change

This PRD adds an optional `run_id` parameter to `TaskOrchestrator.activate_plan(account_id, plan_id, run_id=None)` and `on_task_status_change(...)`. Behavior:

- `run_id is None` → legacy behavior; status reads/writes go to the template `ProjectPlan.tasks[*]`
- `run_id is not None` → status reads/writes go to `PlanRun.task_states[*]`; the template is read-only

The Calendar PRD-4 owners must review this change. It is additive (no breaking change for existing callers).

## 4. Data contract

### Internal scheduler endpoint

`POST /api/v1/internal/scheduler/launch-due-automations`

Request body (optional `now` for testability):
```json
{"now": "2026-04-20T13:00:00Z"}
```

Response:
```json
{
  "checked_at": "2026-04-20T13:00:00Z",
  "automations_fired": [
    {
      "plan_id": "p_123",
      "run_id": "r_456",
      "scheduled_for": "2026-04-20T13:00:00Z",
      "next_run_at": "2026-04-21T13:00:00Z"
    }
  ],
  "automation_count": 1
}
```

### Manual trigger endpoint

`POST /api/v1/automations/{account_id}/{plan_id}/runs`

Request body:
```json
{
  "triggered_by": "manual",     // or "system" for platform-initiated runs
  "inputs": {                    // optional; arbitrary JSON object
    "session_id": "s_abc",
    "account_id": "a_123"
  }
}
```

Rules:
- `triggered_by="manual"` — the endpoint records `triggered_by_user_id` from the auth context.
- `triggered_by="system"` — used by platform services (e.g. KG-PRD-04's idle-session sweeper) that kick off runs imperatively. The endpoint MAY allow `triggered_by_user_id=null` in this case; callers running under a service account identity pass that through.
- `inputs` is opaque to this PRD — stored verbatim on the `PlanRun` and surfaced to dispatched agents via template substitution (see below). Size cap: 100 KB serialized (reject with 413 if exceeded; document in the OpenAPI spec).

Response: the new `PlanRun` doc.

### Cloud Scheduler config

Sibling job to the Calendar PRD-6 scheduler:
- Schedule: `* * * * *` (every minute)
- Target: `POST /api/v1/internal/scheduler/launch-due-automations`
- Auth: OIDC (same SA as Calendar PRD-6)
- Retry: 3 attempts, exponential backoff
- Time zone: UTC

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `api/src/kene_api/services/automation_run_engine.py` (clone-template + compute-next-fire) |
| Create | `api/src/kene_api/services/schedule_preview_service.py` (pure helper: cron + tz + window → occurrence list; shared by the preview endpoint and the upcoming-runs endpoint) |
| Create | `api/src/kene_api/routers/internal/automation_scheduler.py` (internal endpoint) |
| Create | `api/src/kene_api/routers/schedules.py` (public `preview` and `upcoming` endpoints) |
| Modify | `api/src/kene_api/routers/automations.py` (A-PRD-1) — add manual-trigger endpoint |
| Modify | `api/src/kene_api/main.py` — register `schedules` router |
| Modify | `api/src/kene_api/services/task_orchestrator.py` (Calendar PRD-4) — add `run_id` param threading |
| Modify | `api/src/kene_api/main.py` — register internal router |
| Create | `deployment/terraform/cloud_scheduler_automations.tf` |
| Create | `api/tests/unit/test_automation_run_engine.py` |
| Create | `api/tests/unit/test_cron_next_fire.py` |
| Create | `api/tests/unit/test_schedule_preview_service.py` |
| Create | `api/tests/integration/test_automation_scheduler_endpoint.py` |
| Create | `api/tests/integration/test_schedules_preview_and_upcoming.py` |

### Core algorithm — `find_and_fire_due_automations(now: datetime)`

```
1. Query Firestore (collection group "project_plans_*"):
     where save_as_automation == True
       and is_active == True
       and next_run_at <= now
       (and recurrence_cron != null)
2. For each automation:
     a. Run a Firestore transaction:
          re-read template; if next_run_at still <= now:
            - compute new_next = croniter(cron, base=now, timezone=tz).get_next(datetime)
            - update template: next_run_at=new_next, last_run_at=now
            - create PlanRun doc (deep-clone tasks → task_states with status="Draft",
              triggered_by="scheduled", template_version snapshotted)
            - return run_id
          else: return None (someone else fired)
     b. If run_id returned: dispatch via BackgroundTask:
          await orchestrator.activate_plan(account_id, plan_id, run_id=run_id)
3. Return summary.
```

### Cron next-fire computation

```python
from croniter import croniter
from zoneinfo import ZoneInfo

def compute_next_fire(cron_expr: str, tz_name: str, base: datetime) -> datetime:
    tz = ZoneInfo(tz_name)
    base_local = base.astimezone(tz)
    iter_ = croniter(cron_expr, base_local)
    next_local = iter_.get_next(datetime)
    return next_local.astimezone(timezone.utc)
```

DST behavior: `croniter` correctly handles DST transitions when the base datetime is timezone-aware. The integration test covers the spring-forward / fall-back boundaries.

### Backfill policy (no replay)

If `next_run_at` is hours in the past (server downtime), the algorithm above fires **once** for "now" and computes the next fire from "now" — it does not replay missed slots. This is documented in the model docstring on `recurrence_cron` and called out in the Acceptance section.

### Idempotency guarantees

- Cloud Scheduler may retry the endpoint within a tick; the Firestore transaction on `next_run_at` is the canonical guard
- Each run gets a fresh `run_id` (UUID); two concurrent endpoint invocations never share a run
- The orchestrator hand-off is a `BackgroundTask`; the HTTP response is returned before dispatch begins

### When manual trigger overlaps with a scheduled fire

If a user clicks "Run now" while another run of the same automation is in flight, both runs proceed independently — separate `PlanRun` docs, separate `task_states`, separate artifact buckets. The orchestrator never reads from the template during a run, so no interference.

### Inputs template substitution

When the orchestrator dispatches an agent task, it composes a prompt from `PlanTask.description` + the current run's `inputs`. Substitution uses `{inputs.key}` placeholders:

```
PlanTask.description = "Read the transcript for {inputs.session_id} and emit a SessionReview."
run.inputs           = {"session_id": "s_abc"}
→ prompt             = "Read the transcript for s_abc and emit a SessionReview."
```

Rules:
- Only `{inputs.<simple_key>}` and `{inputs.<key>.<nested_key>}` (two levels max) are substituted. Deeper paths are left literal.
- Keys missing from `inputs` resolve to empty string and emit a warning log — the prompt renders but the orchestrator flags the gap.
- Substitution is applied once, before dispatch; agents never see the raw `{inputs.*}` markers. Non-agent tasks (human-assigned) do not participate in substitution.
- Other `{…}` template variables are reserved for future use (e.g. `{upstream_artifacts}`, `{revision_feedback}`) — substitution engine must tolerate unrecognized markers by leaving them intact for downstream handling.

Implementation lives in `AutomationRunEngine._build_agent_prompt(task, run)` (or the equivalent function inside `TaskOrchestrator` — owner's choice). Keep it small and pure so it's unit-testable without the orchestrator harness.

## 6. API contract

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/v1/internal/scheduler/launch-due-automations` | OIDC (Cloud Scheduler SA) | Scheduled tick |
| `POST` | `/api/v1/automations/{account_id}/{plan_id}/runs` | User auth | Manual "Run now" |
| `POST` | `/api/v1/schedules/preview` | User auth | Expand a schedule config into occurrence dates for a window |
| `GET` | `/api/v1/automations/{account_id}/schedules/upcoming` | User auth | List automations with occurrences in a window (Calendar "Projects in view" panel) |

The internal endpoint MUST NOT be exposed to user authentication. The manual-trigger and preview/upcoming endpoints use the same access-control dependency as A-PRD-1.

### `POST /api/v1/schedules/preview`

Request:
```json
{
  "recurrence_cron": "0 9 * * MON",
  "recurrence_timezone": "America/Los_Angeles",
  "window_start": "2026-05-01T00:00:00Z",
  "window_end":   "2026-05-31T23:59:59Z",
  "max_occurrences": 64
}
```

Response:
```json
{
  "occurrences": [
    "2026-05-04T16:00:00Z",
    "2026-05-11T16:00:00Z",
    "2026-05-18T16:00:00Z",
    "2026-05-25T16:00:00Z"
  ],
  "truncated": false
}
```

Rules:
- `window_end - window_start` must be ≤ 90 days; otherwise `422`.
- `max_occurrences` is optional (default 64, hard cap 128). Exceeding the cap produces `truncated=true` with the first N occurrences returned.
- Invalid cron or timezone → `422` with the same messages used by the model validators.
- The endpoint is pure (no Firestore reads or writes) — safe to call frequently from the UI.
- This endpoint is the single source of truth for occurrence expansion. The frontend MUST NOT compute occurrences client-side (the legacy `computeNextRun` in the Figma export is deprecated; the preview endpoint replaces it).

### `GET /api/v1/automations/{account_id}/schedules/upcoming`

Query params:
- `from: ISO datetime` (required, UTC)
- `to: ISO datetime` (required, UTC; must be ≤ from + 90 days)
- `is_test: bool` — default false; when true, includes test runs in the consideration set (this endpoint still only previews, no runs are fired)

Response:
```json
{
  "window": {"from": "...", "to": "..."},
  "items": [
    {
      "plan_id": "p_123",
      "title": "Weekly competitive landscape sweep",
      "recurrence_cron": "0 9 * * MON",
      "recurrence_timezone": "America/Los_Angeles",
      "occurrences": ["2026-05-04T16:00:00Z", "2026-05-11T16:00:00Z"],
      "occurrence_count": 2
    }
  ]
}
```

Rules:
- Filters to automations with `save_as_automation=true`, `is_active=true`, and `is_system=false` (per A-PRD-1's default filter policy — system plans are hidden from the user-facing Calendar panel).
- Per-plan occurrence computation uses the same helper as `/schedules/preview`.
- Total result size capped at 200 plans × 64 occurrences; if exceeded, `truncated=true` is returned and the client is expected to narrow the window.
- Read-only; no side effects.

## 7. Acceptance criteria

1. An automation with `recurrence_cron="* * * * *"` and `next_run_at=now-30s` is fired on the next scheduler tick; a new `PlanRun` doc exists; `next_run_at` is updated to ~now+1min
2. A future automation (`next_run_at=now+1h`) is not fired
3. An inactive automation (`is_active=false`) is not fired
4. An automation without `recurrence_cron` is not fired by the scheduler tick (but can still be fired manually)
5. Two concurrent ticks fire the same automation **exactly once** (transaction-protected)
6. Manual trigger creates a `PlanRun` with `triggered_by="manual"`, `triggered_by_user_id` set, and dispatches via the orchestrator
6a. Manual trigger with `triggered_by="system"` is accepted (service-account or platform caller) and creates a `PlanRun` whose `triggered_by_user_id` may be null
6b. Manual trigger with `inputs={"k": "v"}` stores the object on the `PlanRun` and substitutes `{inputs.k}` placeholders in dispatched agent prompts before invocation
6c. An agent task with `description` containing `{inputs.missing_key}` and a run whose `inputs` omits that key dispatches with an empty string substituted and emits a warning log
7. The orchestrator running on the new `PlanRun` updates `task_states[*]` (not the template) on every status change
8. After a 1-hour downtime simulation, the next tick fires each due automation exactly once (no backfill replay)
9. DST transition test: a `recurrence_cron="30 2 * * *"` automation in `America/Los_Angeles` does not fire twice on fall-back day and does not skip on spring-forward day (croniter behavior)
10. Cloud Scheduler config exists in Terraform; the OIDC auth path returns 401 / 403 for invalid tokens
11. `POST /api/v1/schedules/preview` with `recurrence_cron="0 9 * * MON"` and a 4-week window returns 4 occurrence timestamps in UTC, matching the cron + timezone interpretation
12. `POST /api/v1/schedules/preview` with an invalid cron returns `422`; with `window_end - window_start > 90 days` returns `422`; with more occurrences than `max_occurrences` returns `truncated=true` plus the first N
13. `GET /api/v1/automations/{account_id}/schedules/upcoming?from=...&to=...` returns only automations with `save_as_automation=true`, `is_active=true`, `is_system=false`; each item includes its occurrence list for the window; cross-account → `403`
14. The preview and upcoming endpoints are pure reads — calling them repeatedly produces identical results and writes nothing to Firestore

## 8. Test plan

**Unit tests** (`test_cron_next_fire.py`):
- `"0 9 * * MON"` in `America/Los_Angeles`, base = a Sunday → returns next Monday 9am LA
- DST spring-forward: `"30 2 * * *"` on the day clocks jump 2→3am
- DST fall-back: `"30 1 * * *"` on the day 1:30am occurs twice
- Leap day: `"0 0 29 2 *"` — next fire from 2026 is 2028
- `"*/15 * * * *"` from 14:07 → 14:15
- Invalid cron raises

**Unit tests** (`test_automation_run_engine.py`):
- Clone template into PlanRun: tasks deep-copied into task_states with status="Draft"
- `template_version` snapshotted into PlanRun
- Idempotency: two concurrent invocations with mocked transaction → only one PlanRun created
- `next_run_at` is updated atomically with PlanRun creation
- Backfill: `next_run_at = now - 1hr`, after fire `next_run_at = next-cron-from-now` (not `next-cron-from-prior-fire`)
- Inputs substitution: `"hello {inputs.name}"` + `inputs={"name": "world"}` → `"hello world"`
- Inputs substitution: two-level nesting `{inputs.user.id}` resolves; three-level `{inputs.a.b.c}` left literal
- Inputs substitution: missing key → empty string + warning; unrecognized marker `{upstream_artifacts}` left intact
- Inputs substitution runs only for agent-assigned tasks (no-op for human tasks)
- Manual trigger accepts `triggered_by="system"` with `inputs` payload; `inputs` is persisted on the PlanRun doc

**Integration tests** (`test_automation_scheduler_endpoint.py`):
- Endpoint with valid OIDC + 1 due automation → 200, 1 fired, PlanRun in Firestore
- Endpoint with no token → 401
- Endpoint with token from non-scheduler SA → 403
- Endpoint with `now` override fires a future automation
- After fire, orchestrator was invoked exactly once with the new run_id (mock orchestrator, assert call count)
- Manual trigger endpoint: returns 201 + new PlanRun; cross-account → 403

**Unit tests** (`test_schedule_preview_service.py`):
- 5-field cron + tz + window → correct UTC occurrence list
- Window of exactly 90 days at the boundary → accepted; 91 days → rejected
- `max_occurrences=5` against a cron with 10 matches in the window → 5 occurrences, `truncated=true`
- Invalid cron / invalid tz → raises validation error consumed by the router to produce `422`

**Integration tests** (`test_schedules_preview_and_upcoming.py`):
- `POST /schedules/preview`: weekly Monday cron, 4-week window → 4 occurrences; edge cron on DST boundary → correct UTC values
- Preview with bad cron / bad tz / too-long window → `422`
- `GET /schedules/upcoming`: seed 3 automations (two user, one system), only the two user-owned with `is_active=true` appear in the response; occurrences are present per item
- Cross-account `GET /schedules/upcoming` → `403`
- Truncation: seed 300 automations with matching schedules → response `truncated=true` with `items.length <= 200`

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| Two scheduler jobs (A-PRD-2 and Calendar PRD-6) firing the same minute | They query disjoint sets — Calendar fires individual tasks where `launched_at IS NULL`; this fires automations where `next_run_at <= now`. No collision possible. |
| Long-running orchestrator hand-off blocks the scheduler endpoint | Dispatch via `BackgroundTasks`; HTTP returns < 500ms |
| Composite index for the query is missing → scan | Index part of the Terraform PR; CI verifies presence |
| Edge: an automation's `recurrence_cron` is changed mid-run | The in-flight run uses the snapshotted `template_version`. The new cron applies to the next tick onward. Document. |
| Manual trigger endpoint abused (DoS the orchestrator) | Existing rate limits on user endpoints apply; add a per-account "max in-flight runs" if abuse seen |
| `croniter` library dependency risk | Pin version; small dep; well-maintained. Alternative: write a small wrapper if eval shows correctness issues. |
| Inputs substitution accidentally interpolates secrets from agent context | Substitution only reads from `run.inputs` (caller-provided), never from env vars or session state. Document. |
| `triggered_by="system"` used from an unauthenticated caller | The manual-trigger endpoint still requires auth. Service accounts authenticate with service-account tokens; no anonymous path exists. |

## 10. Reference

- Parent plan: [`../README.md`](../README.md) §2 (Architectural overview)
- Foundation: [A-PRD-1](./A-PRD-01-data-model-and-api.md)
- Reused infra: [Calendar PRD-6](../../project-tasks/projects/PR-PRD-06-time-based-scheduler.md), [Calendar PRD-4](../../project-tasks/projects/PR-PRD-04-event-driven-orchestrator.md)
- Pattern files: `api/src/kene_api/routers/internal/scheduler.py` (Calendar PRD-6)
- CLAUDE.md rules in scope: PY-1, PY-2, PY-3, PY-7; D-1, D-5; T-1, T-3, T-4, T-6
