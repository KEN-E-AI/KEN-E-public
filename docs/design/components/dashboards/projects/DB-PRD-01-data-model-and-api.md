# DB-PRD-01 — Dashboard Data Model & API

**Status:** Blocked — resumes once PR-PRD-01, A-PRD-01, A-PRD-03, DM-PRD-05, and DM-PRD-07 ship
**Owner team:** Backend (foundation)
**Blocked by:** PR-PRD-01 (base `ProjectPlan` / `PlanTask` this PRD extends); A-PRD-01 (`ProjectPlan.type` enum); A-PRD-03 (artifact storage + signed-URL download path); DM-PRD-05 (deletion sweep covers the new subcollection behavior on `ProjectPlan`); DM-PRD-07 (`require_role` + `write_audit` helpers used by every mutating endpoint)
**Blocks:** DB-PRD-02, DB-PRD-03
**Estimated effort:** 2–3 days

---

## 1. Context

A Dashboard is a `ProjectPlan` with `type="dashboard"` that additionally carries a canvas layout — an ordered set of `DashboardPlacement` entries binding plan tasks to visual widgets. Running the dashboard invokes the standard Automations manual-trigger endpoint (`A-PRD-02`); the canvas refreshes by re-resolving each placement against the latest `PlanRun`'s artifacts.

This PRD delivers the **foundation** — the Pydantic schema extensions, the artifact resolver service, and the `/api/v1/dashboards/*` API surface that the frontend (DB-PRD-02, DB-PRD-03) consumes. No UI work. Every subsequent Dashboards PRD builds against the data contract published here.

It also lands one small update to A-PRD-01's list endpoint so dashboards are not shown as automations (and vice versa).

## 2. Scope

### In scope
- `DashboardPlacement` Pydantic model + `OutputFileType` enum + `OutputConfig` Pydantic model
- Extend `ProjectPlan` with `dashboard_placements: list[DashboardPlacement]` (capped at 100)
- Extend `PlanTask` with `output_config: OutputConfig | None`
- Model-level validators: placement references a real task in the plan; `type="dashboard"` plans reject invalid placements on create/update
- `DashboardArtifactResolver` service: given a plan + latest `PlanRun`, compute a `DashboardArtifact[]` with status (`fresh` / `disconnected` / `pending`), inlined payload for small artifacts (≤64 KB), or signed URL for large. Includes a `classify_artifact(mime_type, content_head)` helper that maps A-PRD-03's `TaskArtifact.mime_type` to the dashboards `OutputFileType` enum (since A-PRD-03 stores only `mime_type`)
- New `/api/v1/dashboards/*` router — list, get-enriched, create, duplicate, PUT placements, delete (soft)
- Duplicate endpoint: clones a dashboard into a new `ProjectPlan` with new `task_id`s, remapped `depends_on` edges and placement `task_id` references, preserved schedule with `is_active=false`, empty run history
- Update `A-PRD-01` list endpoint to filter `type="freeform"` by default on `/api/v1/automations/{account_id}`; accept explicit `?type=dashboard` or `?type=all` for debugging
- Unit tests for the resolver + validators; integration tests for every endpoint

### Out of scope (handled by other PRDs)
- Running a dashboard (use `A-PRD-02`'s manual trigger endpoint directly)
- Plan-editing endpoints (use `PR-PRD-01`'s `PUT /plans` + `PATCH .../tasks/{task_id}`)
- Schedule configuration (use `A-PRD-01`'s recurrence PATCH)
- Frontend (DB-PRD-02, DB-PRD-03)
- Real-time refresh during runs
- Extensions / dashboard templates

## 3. Dependencies

- **PR-PRD-01 (Data Model & API):** base `ProjectPlan` / `PlanTask`. This PRD extends both with new optional fields; existing user plans continue to validate unchanged.
- **A-PRD-01 (Automations Data Model):** publishes `ProjectPlan.type: Literal["freeform", "dashboard"]`. DB-PRD-01 uses `type="dashboard"` as the dashboards discriminator. Update to A-PRD-01 list endpoint is small (default filter only).
- **A-PRD-03 (Task Artifact System):** provides `TaskArtifact` docs at `accounts/{account_id}/plan_runs/{run_id}/artifacts/{artifact_id}` and a signed-URL download endpoint. The resolver reads artifact metadata from that subcollection and generates download URLs via the same `artifact_store.generate_signed_url(artifact_id, ttl_seconds=3600)` helper A-PRD-03 ships.
- **DM-PRD-05:** already covers `recursive_delete(accounts/{account_id})`. No new subcollection is introduced by this PRD (placements are embedded on the plan doc), so no additional delete work.
- **DM-PRD-07 (Approval Workflow & Audit):** `require_role` on every mutating endpoint; `write_audit` on every mutation. Role gates: `editor` for create / PUT placements / delete; `viewer` for GET.
- **External:** `croniter` / `zoneinfo` (only indirectly via A-PRD-02's preview endpoint, not consumed here)
- **Existing files to study:**
  - `api/src/kene_api/models/project_plan_models.py` (PR-PRD-01) — extend here
  - `api/src/kene_api/models/plan_run_models.py` (A-PRD-01) — read for PlanRun + TaskRunState shape
  - `api/src/kene_api/models/task_artifact_models.py` (A-PRD-03) — read for TaskArtifact shape
  - `api/src/kene_api/services/artifact_store.py` (A-PRD-03) — signed-URL helper
  - `api/src/kene_api/routers/project_plans.py` — pattern for the new router

## 4. Data contract

### 4.1 `OutputFileType` enum

```python
class OutputFileType(str, Enum):
    TEXT          = "text"
    VISUALIZATION = "visualization"   # Vega-Lite spec (JSON with $schema)
    CSV           = "csv"
    IMAGE         = "image"
    DOCUMENT      = "document"
    JSON          = "json"            # generic JSON, not necessarily a Vega spec
    HTML          = "html"
    VIDEO         = "video"
    AUDIO         = "audio"
    OTHER         = "other"
```

This mirrors the frontend inventory in `docs/figma-export/src/app/data/automationDetailsData.ts:121`. Add to the shared types module so any component (Automations, Dashboards) can reference it.

### 4.2 `OutputConfig` (on `PlanTask`)

```python
class OutputConfig(BaseModel):
    enabled: bool = False
    expected_file_types: list[OutputFileType] = Field(default_factory=list)

    @validator("expected_file_types")
    def dedupe(cls, v):
        return list(dict.fromkeys(v))           # preserve order, drop duplicates
```

### 4.3 `DashboardPlacement` (on `ProjectPlan`)

```python
class DashboardPlacement(BaseModel):
    placement_id: str                           # UUID; stable across edits
    task_id: str                                # references a PlanTask.task_id in this plan
    file_type: OutputFileType
    # Canvas layout — absolute pixel coordinates, 8-px grid snap enforced by the UI
    x: int = Field(ge=0, le=10_000)
    y: int = Field(ge=0, le=10_000)
    w: int = Field(ge=64, le=4_000)             # min 64 px wide, max 4000
    h: int = Field(ge=64, le=4_000)
    # Optional presentation overrides (applied at render time by the frontend)
    view_override: Literal["bar", "line", "area", "point", "arc", "table"] | None = None
    color: str | None = None                    # hex, validated at render time
    show_data_labels: bool | None = None
```

### 4.4 `ProjectPlan` — fields added

```python
class ProjectPlan(BaseModel):
    # ... existing fields (PR-PRD-01, PR-PRD-07, PR-PRD-08, A-PRD-01)
    dashboard_placements: list[DashboardPlacement] = Field(
        default_factory=list,
        max_items=100,
    )
```

### 4.5 `PlanTask` — fields added

```python
class PlanTask(BaseModel):
    # ... existing fields (PR-PRD-01, PR-PRD-07)
    output_config: OutputConfig | None = None
```

### 4.6 Model-level validators

Added to `ProjectPlan`'s root validator:

- **Placement tasks exist:** every `placement.task_id` must be in `{t.task_id for t in tasks}`; otherwise `422` with the offending placement id(s).
- **Placement type-locked:** if `type != "dashboard"` and `dashboard_placements` is non-empty, reject with `422`. Freeform and automation plans cannot carry placements.
- **Placement count cap:** enforced by `max_items=100` on the field.
- **No duplicate `(task_id, file_type)` pairs:** two placements may both point to the same task but MUST target different file types. Violation → `422`.

Disconnected-state rules (task exists but `output_config.enabled=false` or `file_type` not in `expected_file_types`) are **not** create-time errors — they surface as `status="disconnected"` from the resolver. This lets users save a dashboard whose tasks aren't yet fully configured.

### 4.7 `DashboardArtifact` — resolver output

```python
class DashboardArtifact(BaseModel):
    placement_id: str
    task_id: str
    file_type: OutputFileType
    status: Literal["fresh", "disconnected", "pending"]
    # Inline payload shape varies by file_type; None for large artifacts
    inline_payload: dict | None = None
    # Signed URL for large artifacts (fetched via A-PRD-03's store)
    download_url: str | None = None
    # When the referenced OutputFile was produced (None for disconnected/pending)
    updated_at: datetime | None = None
    # Opaque pointer to the underlying TaskArtifact doc for debugging
    artifact_id: str | None = None
```

**Status semantics — three values, not four.** This PRD intentionally does **not** define a `stale` status. Rationale: A-PRD-03's `TaskArtifact` lives at `accounts/{account_id}/plan_runs/{run_id}/artifacts/{artifact_id}` with no `produced_in_run_id` field — an artifact in `latest_run`'s subcollection is by definition produced in `latest_run`. Implementing a "stale" branch would require the resolver to walk back through every prior `PlanRun` to find the most recent matching artifact (an unbounded scan that conflicts with the §5 "1 run read + 1 artifacts list" cost target). The tradeoff: when a re-run fails to emit an expected artifact, the corresponding placement renders `pending` ("task hasn't produced this output yet") instead of "stale" with prior data. The user re-runs to refresh — same UX, simpler resolver, simpler test surface.

**Inline payload shapes:**

| `file_type` | `inline_payload` shape (when `status == "fresh"` and size ≤ 64 KB) |
|---|---|
| `text` | `{"content": str}` — raw text, markdown rendered client-side |
| `visualization` | `{"spec": dict}` — Vega-Lite spec (validated: has `$schema` starting with `https://vega.github.io/schema/vega-lite/`) |
| `csv` | **not inlined** — always served via `download_url`. Client parses and renders as a table. |
| `json` | `{"data": dict or list}` — if it's a Vega-Lite spec, re-classify to `visualization` at resolve time |
| `image`, `document`, `video`, `audio`, `html`, `other` | **not inlined** — always served via `download_url`; the file-fallback widget renders a download card |

### 4.8 Status resolution algorithm

For each placement `p` in `plan.dashboard_placements`:

1. Find `task` in `plan.tasks` where `task.task_id == p.task_id`.
   - If none: return `status="disconnected"`.
2. If `task.output_config is None` or `task.output_config.enabled is False` or `p.file_type not in task.output_config.expected_file_types`: return `status="disconnected"`.
3. Load `latest_run: PlanRun | None` = most recent `PlanRun` for this plan with `status in {"complete", "failed"}` (not in-flight). If none exists: return `status="pending"` with `updated_at=None`.
4. Walk `latest_run`'s `artifacts/` subcollection (single list operation, in-memory join) and look for the first `TaskArtifact` where `task_id == p.task_id` AND `classify_artifact(artifact.mime_type, artifact.content_head) == p.file_type` (see §4.9 for the classifier). If multiple match (the same task emitted two artifacts of the same `file_type` in one run), pick the one with the latest `created_at`.
   - **Found:** `status="fresh"`, populate `updated_at` from the artifact's `created_at`, populate `inline_payload` or `download_url` per §4.7's payload-shape table, populate `artifact_id`.
   - **Not found:** `status="pending"`, `updated_at=None`, `inline_payload=None`, `download_url=None`. (The latest run completed but didn't emit an artifact matching this `file_type` — the user can re-run to refresh.)

Note: this PRD does **not** scan back through prior `PlanRun`s to surface a "stale" prior artifact when the latest run fails to re-emit. See §4.7's "Status semantics — three values, not four" rationale.

### 4.9 Artifact classification (`mime_type` → `OutputFileType`)

A-PRD-03's `TaskArtifact` stores `mime_type: str` only — it does not carry the dashboards `OutputFileType` enum. The resolver bridges that gap with a pure mapping function owned by this PRD:

```python
def classify_artifact(
    mime_type: str,
    content_head: bytes | None = None,   # first ~256 bytes of the artifact, optional
) -> OutputFileType:
    """Map A-PRD-03 mime_type → dashboards OutputFileType.

    content_head, when supplied, lets the classifier distinguish Vega-Lite
    JSON (-> visualization) from generic JSON (-> json). Callers that don't
    pass content_head get the conservative classification (json).
    """
```

| Input mime_type | Returns |
|---|---|
| `text/plain`, `text/markdown`, `text/*` (any other `text/*` not listed below) | `text` |
| `text/csv`, `application/csv` | `csv` |
| `text/html` | `html` |
| `image/*` (`png`, `jpeg`, `gif`, `svg+xml`, `webp`, etc.) | `image` |
| `video/*` | `video` |
| `audio/*` | `audio` |
| `application/pdf`, `application/msword`, `application/vnd.openxmlformats-officedocument.*`, `application/vnd.ms-*` | `document` |
| `application/json` **with** `content_head` containing `https://vega.github.io/schema/vega-lite/` | `visualization` |
| `application/json` **without** content_head, or content_head lacks the Vega-Lite schema marker | `json` |
| anything else | `other` |

**Vega-Lite detection rule.** Match the regex `https://vega\.github\.io/schema/vega-lite/v\d+\.json` anywhere in the first 256 bytes of `content_head`. The bytes are decoded as UTF-8 with `errors="replace"` before scanning; non-text payloads cannot match. (The 256-byte window is a hint, not a hard cap — the field is conventionally near the top of a Vega-Lite spec; longer scans add cost without benefit.)

**Re-classification at resolve time.** If a placement's `file_type == "json"` but the artifact classifies as `visualization` (the agent attached a Vega-Lite spec via `attach_task_artifact` with mime_type `application/json` rather than calling `create_visualization`), the resolver returns `file_type="visualization"` on the `DashboardArtifact` and serves it as a Vega-Lite payload. Symmetric: a placement with `file_type="visualization"` whose artifact lacks the Vega-Lite schema marker returns `file_type="json"` and serves the raw JSON. (This makes mis-typed agent output recoverable rather than appearing as `pending`.)

The classifier is a pure function — no I/O, no Firestore reads. It lives at `api/src/kene_api/services/artifact_classifier.py` and is unit-tested independently of the resolver.

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `api/src/kene_api/models/output_types.py` — `OutputFileType` enum (shared across components) |
| Modify | `api/src/kene_api/models/project_plan_models.py` — add `DashboardPlacement`, `OutputConfig`, extend `ProjectPlan` and `PlanTask`, add root validators |
| Create | `api/src/kene_api/models/dashboard_models.py` — `DashboardArtifact`, `DashboardGetResponse` wrapper |
| Create | `api/src/kene_api/services/artifact_classifier.py` — pure `classify_artifact(mime_type, content_head=None) → OutputFileType` helper (§4.9). Consumed by the resolver. |
| Create | `api/src/kene_api/services/dashboard_artifact_resolver.py` — the resolver algorithm; consumes `artifact_classifier` |
| Create | `api/src/kene_api/routers/dashboards.py` — list / get / create / duplicate / put-placements / delete endpoints |
| Create | `api/src/kene_api/services/dashboard_duplicate_service.py` — deep-copy with task-id remap + depends_on + placement remap in one Firestore transaction |
| Modify | `api/src/kene_api/routers/automations.py` (A-PRD-01) — add default `type="freeform"` filter on the list endpoint |
| Modify | `api/src/kene_api/main.py` — register the dashboards router |
| Create | `api/tests/unit/test_artifact_classifier.py` — covers the mime → file_type mapping table + Vega-Lite detection |
| Create | `api/tests/unit/test_dashboard_placement_validators.py` |
| Create | `api/tests/unit/test_dashboard_artifact_resolver.py` |
| Create | `api/tests/integration/test_dashboards_router.py` |
| Create | `api/tests/unit/test_dashboard_duplicate_service.py` |
| Create | `api/tests/integration/test_automations_excludes_dashboards.py` |

### Firestore layout (no new subcollections)

```
accounts/{account_id}/project_plans/{plan_id}                     # PR-PRD-01 (extended)
  └── tasks[].output_config                                       # NEW (this PRD)
  └── dashboard_placements[]                                      # NEW (this PRD, when type="dashboard")
accounts/{account_id}/plan_runs/{run_id}                          # A-PRD-01 (read for resolver)
accounts/{account_id}/plan_runs/{run_id}/artifacts/{artifact_id}  # A-PRD-03 (read for resolver)
accounts/{account_id}/project_plan_audit/{audit_id}               # DM-PRD-07 (write mutations)
```

Placements are embedded on the plan doc rather than a subcollection because:
- The cap is 100 placements per dashboard; Firestore doc size limit (1 MB) is not a concern at this scale.
- The frontend reads the whole canvas layout atomically on GET.
- The canvas PUT replaces the entire array in one write.

### Composite indexes

No new indexes required. The list endpoint's `type="dashboard"` filter uses the `is_system / is_active / updated_at` collection-scope index A-PRD-01 already ships (the `type` field fits as an additional equality filter; see §5 implementation outline of A-PRD-01 index definitions — verify no new composite is needed). If profiling in staging shows a scan warning, add one: `type ASC, is_active ASC, updated_at DESC` under `accounts/*/project_plans`. Track as a follow-up, not a blocker.

### Resolver cost model (per `GET /dashboards/{plan_id}`)

The resolver's per-request cost is bounded and small:

- **1 plan-doc read** (the dashboard `ProjectPlan`)
- **1 plan_runs query** to find the latest terminal-state run (composite index already provided by A-PRD-01)
- **1 artifacts subcollection list** for that run (returns N artifacts where N is bounded by attach-rate × tasks; in practice ≤ a few dozen for a 100-placement dashboard)
- **In-memory join**: for each placement (≤100), scan the artifact list to find a match, running `classify_artifact` once per artifact. O(placements × artifacts) join, both factors bounded; well under the 500ms p95 target in DB-PRD-04 §4.5 P-1.

No per-placement Firestore round-trip. The resolver does **not** scan back through prior `PlanRun`s (the "stale" branch was intentionally cut — see §4.7's "three values, not four" rationale).

## 6. API contract

### 6.1 List dashboards

```
GET /api/v1/dashboards/{account_id}
    ?is_active=true        # default true; false returns soft-deleted
    &tags[]=X&tags[]=Y     # OR semantics (array_contains_any)
    &cursor=<opaque>
    &page_size=25          # max 100
```

Response: `PaginatedResponse<DashboardSummary>` where `DashboardSummary` is `{plan_id, title, description, tags, is_active, last_run_at, next_run_at, last_run.status, placement_count, updated_at}`. The summary does NOT include resolved artifacts — clients call GET-one for that.

Server filters `type="dashboard"` + `is_system=false` + account scope.

### 6.2 Get dashboard (with resolved artifacts)

```
GET /api/v1/dashboards/{account_id}/{plan_id}
```

Response:
```json
{
  "plan": ProjectPlan,              // full plan incl. tasks, placements, schedule, etc.
  "latest_run": PlanRun | null,     // most recent terminal-state run; null if never run
  "artifacts": DashboardArtifact[]  // one per placement, in placement order
}
```

Rules:
- 404 if plan doesn't exist, is soft-deleted, or `type != "dashboard"`.
- `artifacts.length == plan.dashboard_placements.length` always; status fields cover the gap cases.
- Signed URLs in `artifacts[*].download_url` expire 1 hour after response.

### 6.3 Create dashboard

```
POST /api/v1/dashboards/{account_id}
Body: {title: str, description?: str, tags?: list[str]}
```

Creates a `ProjectPlan` with:
- `type = "dashboard"`
- `title`, `description`, `tags` = from body
- `goal = ""` (empty; required by base model but meaningless for dashboards)
- `tasks = []`
- `dashboard_placements = []`
- `acceptance_criteria = []`
- `is_active = true`
- `status = "draft"`

Returns `201` with the full `ProjectPlan`. Caller follows up with `PR-PRD-01`'s `PUT /plans` to add tasks.

### 6.4 Replace canvas layout

```
PUT /api/v1/dashboards/{account_id}/{plan_id}/placements
Body: DashboardPlacement[]           // full array; last-write-wins
```

Atomically replaces `dashboard_placements` on the plan. Applies all `§4.6` validators. Returns `200` with the updated placements. Writes an audit entry with the diff summary (added / removed / moved placement ids).

### 6.5 Delete dashboard

```
DELETE /api/v1/dashboards/{account_id}/{plan_id}
```

Delegates to `PR-PRD-01`'s `DELETE /plans/{plan_id}` (soft-delete, `is_active=false`). Returns `200`. Writes audit entry.

### 6.6 Duplicate dashboard

```
POST /api/v1/dashboards/{account_id}/{plan_id}/duplicate
Body: {title?: string}                   // optional; defaults to "{source.title} (Copy)"
```

Creates a new `ProjectPlan` that is a deep copy of the source with the following rules:

**Copied:**
- `type = "dashboard"`
- `description`, `tags`, `acceptance_criteria` (with new `criterion_id`s)
- `schedule` / `recurrence_cron` / `recurrence_timezone`
- `campaign_id`, `extension_id`, `goal_id`
- `tasks` — deep-copied with **new `task_id`s**; each task's `depends_on` list is remapped via the `{old_id → new_id}` map
- `dashboard_placements` — deep-copied with **new `placement_id`s**; each placement's `task_id` is remapped via the same map

**Reset (not copied):**
- `plan_id` — new UUID
- `version = 1` — not a continuation of the source's version history
- `is_active = false` — a duplicate's schedule does not immediately start firing; the user must re-enable it
- `status = "draft"`
- `last_run_at = null`, `last_run_id = null`, `next_run_at = null`
- `launched_at` on every task reset to `null`
- `completion_notes` and `revision_comment` on every task reset to `null`
- Task statuses reset to `"Draft"` (the source's in-progress statuses don't carry forward)
- `is_system = false` — a duplicate is never a system template, even if the source was
- `created_at = now`, `created_by = caller_email`, `updated_at = now`

The operation is a single Firestore transaction: if any step fails, no partial dashboard is persisted. Returns `201` with the full new `ProjectPlan`. Writes one audit entry with `action="duplicate"` and `before_state=null`, `after_state=<new plan>`, `diff_summary=["duplicated from {source.plan_id}"]`.

Duplicating a `type="freeform"` plan through this endpoint returns `422` (the Dashboards API only duplicates dashboards — for non-dashboard plans, use a future Project Tasks duplicate endpoint).

### 6.7 Automations list update (A-PRD-01)

`GET /api/v1/automations/{account_id}` gains a new query parameter and default:

```
?type=freeform            # default; returns only freeform plans
?type=dashboard           # debugging only; not surfaced in the Automations UI
?type=all                 # debugging only
```

Existing `save_as_automation=true`, `is_system=false`, and `is_active` filters unchanged. The default change is backwards-compatible for the Automations UI (which only cares about freeform) and prevents dashboards from appearing as automations.

## 7. Acceptance criteria

1. Posting a `ProjectPlan` with `type="dashboard"`, 3 tasks, and 3 `dashboard_placements` referencing those tasks returns `201`; `GET /dashboards/{plan_id}` returns the same plan with `artifacts: DashboardArtifact[]` of length 3.
2. Posting a placement whose `task_id` is not in the plan's `tasks[]` returns `422` with a clear message naming the offending `placement_id`.
3. Posting a `ProjectPlan` with `type="freeform"` and non-empty `dashboard_placements` returns `422`.
4. Posting a plan with two placements having the same `(task_id, file_type)` pair returns `422`.
5. Posting a plan with 101 placements returns `422`.
6. `PUT /placements` with a valid full array replaces the layout; the response reflects the new array in order; an audit entry is written with `diff_summary` listing added / removed / moved ids.
7. `PUT /placements` with the same array it currently has (no-op) still succeeds (`200`) and writes an audit entry with empty `diff_summary`.
8. `GET /dashboards/{plan_id}` on a plan with no completed runs returns `latest_run=null` and `artifacts[*].status == "pending"`.
9. `GET /dashboards/{plan_id}` after the plan's latest run emitted every expected artifact returns `artifacts[*].status == "fresh"` with `updated_at` set to the latest run's completion timestamp.
10. `GET /dashboards/{plan_id}` after a task's `output_config.enabled` flips to `false` returns `artifacts[i].status == "disconnected"` for placements referencing that task.
11. `GET /dashboards/{plan_id}` after a re-run where one task didn't re-emit the placement's expected file type returns `artifacts[i].status == "pending"` for that placement, with `updated_at=null` and no `inline_payload` / `download_url`. (Resolver does not surface a prior run's artifact; the placement reflects the latest run's emission state.)
12. Inline payload threshold holds: a 60 KB text artifact is returned inline (`inline_payload.content`), a 65 KB text artifact is returned via `download_url` only.
13. Vega-Lite validation: a `visualization` artifact whose JSON lacks `$schema` matching `https://vega.github.io/schema/vega-lite/` is re-classified to `json` and served inline as `{"data": ...}` without a Vega render hint.
14. **Classifier round-trip:** a `mime_type='application/json'` artifact whose first 256 B contains `https://vega.github.io/schema/vega-lite/v6.json` resolves to `file_type='visualization'` on the `DashboardArtifact`; a `mime_type='application/json'` payload with no `$schema` resolves to `file_type='json'`. (Tests that the resolver can recover from agents calling `attach_task_artifact` with mime `application/json` rather than going through `create_visualization`.)
15. Cross-account access returns `403` on every endpoint.
16. `GET /api/v1/automations/{account_id}` (no `?type=`) excludes every plan with `type="dashboard"`; the same query with `?type=all` returns both.
17. All role gates fire: `viewer` → GET `200`, `POST`/`PUT`/`DELETE` `403`. `editor` → all `2xx`.
18. All endpoints write an `AuditEntry` with `resource_type="project_plan"`, `action ∈ {"create", "update", "delete"}` where appropriate. Placement edits use `action="update"` with `diff_summary` describing the placement changes.
19. `POST /duplicate` on a source dashboard creates a new `ProjectPlan` with new `plan_id`, new `task_id`s across all tasks, remapped `depends_on` edges that still point within the new plan, remapped placement `task_id` references, copied `dashboard_placements` with new `placement_id`s, and `is_active=false`. Source plan unchanged.
20. `POST /duplicate` with no body defaults `title` to `"{source.title} (Copy)"`; with body `{title: "Q2 Clone"}` uses the supplied title. Duplicates may share a title with the source (no uniqueness constraint on plan title).
21. `POST /duplicate` writes exactly one audit entry with `action="duplicate"`, `before_state=null`, `after_state=<new plan>`, `diff_summary=["duplicated from {source.plan_id}"]`. The source plan gets no audit entry (unchanged).
22. `POST /duplicate` on a `type="freeform"` plan returns `422` with a clear message; the endpoint only handles dashboards.
23. `POST /duplicate` transaction rollback: a simulated failure mid-copy leaves no partial plan in Firestore (source intact, no new doc).
24. `make lint` clean; all unit + integration tests pass.

## 8. Test plan

**Unit tests** (`test_dashboard_placement_validators.py`):
- Each validator fires with the expected error message on its violation
- Valid placements: 0, 1, 50, 100 placements accepted; 101 rejected
- `type="dashboard"` + empty placements accepted (dashboards created empty)
- `type="freeform"` + empty placements accepted (freeform plans unaffected)
- `type="freeform"` + 1 placement rejected with type-locked message

**Unit tests** (`test_artifact_classifier.py`):
- Each row of §4.9's mime-type table maps to the documented `OutputFileType`
- Vega-Lite detection: `{"$schema": "https://vega.github.io/schema/vega-lite/v6.json", ...}` (first 256 B) → `visualization`; `{"$schema": "https://vega.github.io/schema/vega/v6.json", ...}` (plain Vega) → `json`; JSON without any `$schema` → `json`
- `content_head=None` with `mime_type="application/json"` → conservative fallback `json` (no Vega detection without a content peek)
- Non-UTF-8 bytes in `content_head` decode with replacement and never throw
- `mime_type` casing variants (`Application/JSON`, `IMAGE/PNG`) normalize correctly

**Unit tests** (`test_dashboard_artifact_resolver.py`):
- All three status branches: `fresh`, `disconnected`, `pending`
- Inline threshold: 0 KB, 1 KB, 63 KB, 64 KB, 65 KB, 10 MB text / visualization
- `csv` always served via URL regardless of size
- `file_type="json"` placement + Vega-Lite `application/json` artifact → `DashboardArtifact.file_type="visualization"` (recovery from mis-typed agent output)
- `file_type="visualization"` placement + plain JSON artifact (no Vega-Lite `$schema`) → `DashboardArtifact.file_type="json"`
- Task deleted between dashboard save and resolver call → `disconnected`
- `output_config` flipped mid-life → `disconnected`
- Same `(task_id, file_type)` pair referenced by two placements (should have been rejected at save time; resolver treats defensively — both get the same `fresh`/`pending` resolution)
- Latest run completed but emitted no artifact for the placement's `(task_id, file_type)` → `pending`
- Same task emitted two artifacts with the same classified `file_type` in one run → resolver picks the one with the latest `created_at`

**Integration tests** (`test_dashboards_router.py`):
- Full lifecycle: create → add tasks (via PR-PRD-01 PUT) → add placements (PUT) → run (via A-PRD-02 manual trigger) → GET returns resolved artifacts
- Role gating: each of viewer / editor / approver / admin × each endpoint → expected status codes
- Cross-account `403`
- Empty dashboard GET (no placements, no runs) returns `artifacts=[]`, `latest_run=null`
- Delete then GET → `404`
- Duplicate: source with 5 tasks + 3 placements → POST /duplicate → response has 5 tasks with new task_ids, 3 placements with new placement_ids, all cross-references remapped, `is_active=false`, `status="draft"`. Source plan unchanged.
- Duplicate with title override: `{title: "Custom"}` → response.title == "Custom"
- Duplicate with no body: response.title == "{source.title} (Copy)"
- Duplicate a freeform plan → 422
- Duplicate cross-account → 403

**Unit tests** (`test_dashboard_duplicate_service.py`):
- `task_id` remap map is complete: every old task_id in source appears once in the map; no collisions in new_ids
- `depends_on` edges in the copied plan reference only new task_ids; no stale references to source's task_ids
- Placement `task_id`s in the copied plan reference only new task_ids
- Reset fields: `last_run_at`, `last_run_id`, `next_run_at`, `launched_at` (on every task), `completion_notes`, `revision_comment` all null; task statuses all `"Draft"`
- Transaction rollback: a mocked Firestore write failure on the final commit leaves no partial plan

**Integration tests** (`test_automations_excludes_dashboards.py`):
- Seed 3 plans: 1 freeform + save_as_automation=true, 1 dashboard + save_as_automation=true, 1 dashboard without save_as_automation
- `GET /automations` returns only the freeform plan
- `GET /automations?type=dashboard` returns both dashboards
- `GET /automations?type=all` returns all three
- `GET /dashboards` returns both dashboards, never the freeform

## 9. Risks & open questions

| Risk / question | Mitigation |
|---|---|
| Placement PUT with identical array every 500 ms during a drag | Frontend owns the debounce (DB-PRD-03); backend is idempotent either way. The audit-entry-per-write cost is accepted — empty `diff_summary` audits still record who-tried-to-edit-when. If audit volume becomes a problem, skip audit writes when `diff_summary == []`. |
| Signed URLs returned in a bulk GET expire in 1 h; user may open the dashboard and leave the tab open overnight | Frontend refetches the GET when a widget's signed URL 403s. Document in DB-PRD-03. |
| Placement `color` / `view_override` unsanitized | Color = hex-string regex validation at resolver time (not save time, to allow future CSS vars); `view_override` is an enum, already validated. |
| Breaking API change to A-PRD-01 list default | The default change (`type="freeform"`) is backwards-compatible for the Automations UI (which never wanted dashboards in the list). Flag in release notes; the A-PRD-05 frontend already assumes automation-type results. |
| Failed re-run leaves placements as `pending` instead of showing prior data ("no stale state" tradeoff — see §4.7) | Acceptable v1 tradeoff — the user re-runs to refresh. If user research surfaces the "wanted to see prior run while debugging" pattern, follow up with either (a) a `?include_prior=true` query param that walks back through runs, or (b) materialize a `latest_artifact_per_(task_id,file_type)` index at the plan level. Both options are additive; the v1 API leaves room. |

### Open questions

1. **Should `dashboard_placements` be versioned separately from the plan?** PR-PRD-01 versions the plan on `PUT /plans`. Canvas layout changes go through `PUT /placements`, which does NOT bump the plan's version. Rationale: placements are UI state, not execution state. Revisit if users request layout history.
2. **Are there access-control reasons a viewer shouldn't see `download_url`s?** The URLs expire in 1 h and require the viewer to already be account-scoped. Same exposure as A-PRD-03. Leave consistent.

### Resolved

- **Deleting a referenced task does not cascade to placements.** Confirmed 2026-04-22. A placement whose `task_id` no longer exists (or whose task has `output_config.enabled=false` or no longer declares the placement's `file_type`) is surfaced by the resolver with `status="disconnected"`. The user can re-point the placement to a different task or remove it. Rationale: no silent layout loss; consistent with how `pending` is handled (resolver reflects state, does not mutate it).
- **No `stale` status — three values, not four.** Confirmed 2026-04-27. Originally specified as `fresh / stale / disconnected / pending`, but A-PRD-03 doesn't carry a `produced_in_run_id` on `TaskArtifact` (the run subcollection path is the producer-of-record). Walking back through prior runs to surface a "stale" prior artifact would unbound the resolver's read cost and complicate the test surface. Cut to three values; users re-run to refresh when an expected artifact didn't materialize. See §4.7 for the full rationale.

## 10. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md)
- Foundation: [PR-PRD-01](../../project-tasks/projects/PR-PRD-01-data-model-and-api.md) §4 data contract
- Sibling: [A-PRD-01](../../automations/projects/A-PRD-01-data-model-and-api.md) — `ProjectPlan.type` enum owner
- Sibling: [A-PRD-03](../../automations/projects/A-PRD-03-task-artifact-system.md) — artifact store + signed-URL helper
- Role gate + audit: [DM-PRD-07](../../data-management/projects/DM-PRD-07-approval-workflow-and-audit.md)
- Frontend context: `docs/figma-export/src/app/data/mockData.ts` (`DashboardPlacement`, `OutputFileType`), `docs/figma-export/src/app/data/automationDetailsData.ts` (`OutputConfig`, `TaskRunOutput`), `docs/figma-export/src/app/components/DashboardCanvas.tsx` (canvas model + artifact-resolution hook)
- CLAUDE.md rules in scope: C-1, C-5; D-1, D-5; PY-1, PY-2, PY-7; T-1, T-3, T-4, T-7, T-8
