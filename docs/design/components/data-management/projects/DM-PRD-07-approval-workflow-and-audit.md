# DM-PRD-07 — Approval Workflow & Audit

**Status:** Blocked — resumes once PR-PRD-01 and DM-PRD-05 ship
**Owner team:** Backend / Platform
**Blocked by:** PR-PRD-01 (status enum + transition endpoints this PRD gates); DM-PRD-05 (ensures `recursive_delete` covers the audit subcollection)
**Blocks:** PR-PRD-07 (all approval-sensitive endpoints call this PRD's gate)
**Estimated effort:** 2–3 days

---

## 1. Context

The Figma-designed Calendar page models a six-state status lifecycle for activities (`Draft → Awaiting Approval → Approved → Complete`, with `Rejected` and `Revision Requested → Draft` branches). PR-PRD-01 publishes the enum and the transition endpoints but leaves three gaps:

1. **No role model.** Every authenticated user can make every transition. Product requires that `Approved` / `Rejected` transitions be restricted to an `approver` role (or higher), while `Draft ↔ Awaiting Approval` is available to any editor.
2. **No formal audit-log document shape.** PR-PRD-01 writes to `project_plan_audit/{audit_id}` but does not specify the document structure (who changed what, before/after snapshots, actor email, action type, IP/user-agent, correlation id). Downstream compliance and replay tooling need a stable contract.
3. **No retention policy.** The audit data must be retained long enough to satisfy compliance and long enough to support investigation of user-visible incidents, but Firestore storage grows unboundedly without a policy.

This PRD delivers the role model, the gate that enforces it on every status-changing endpoint, the formal audit-log schema, and the retention policy. It lives under Data Management because the document shape and retention are DM concerns (Shape B convention, cross-component); the transition gate is enforced by a shared dependency that any component can import.

## 2. Scope

### In scope
- `UserRole` enum (`viewer | editor | approver | admin`)
- Role storage on `accounts/{account_id}/members/{user_id}` (a new subcollection, or existing-if-present; verify at implementation start)
- FastAPI dependency `require_role(min_role: UserRole)` usable from any router
- Transition policy table: for each (from_state, to_state) pair, the minimum role required. Consumed by PR-PRD-01's `transition` endpoint and by PR-PRD-07's status-patch paths.
- Formal `AuditEntry` Pydantic model and document shape
- Audit-write helper `write_audit(...)` used by PR-PRD-01, PR-PRD-07 (and any future consumer; PR-PRD-08 retrofits its audit writes to call `write_audit` once this PRD ships, the same way PR-PRD-01 does)
- Retention: 2 years hot in Firestore under `accounts/{account_id}/project_plan_audit/`; nightly export to BigQuery for indefinite archive
- Cloud Scheduler job + internal endpoint that trims audit entries older than 2 years (after successful BigQuery export)
- Unit tests for the role gate and the audit helper; integration tests for transition denial + audit-write verification

### Out of scope
- Role assignment UI (admin page — separate frontend project)
- OIDC / SSO group-to-role mapping (handled elsewhere; this PRD only reads the persisted role)
- Audit of *read* operations (considered; deferred — only writes/transitions audited in v1)
- Custom per-customer retention overrides (2-year default fits current contracts; revisit)
- BigQuery schema evolution tooling (out of scope; one-shot schema)

## 3. Dependencies

- **PR-PRD-01:** owns the transition endpoint; calls `require_role(...)` and `write_audit(...)` from this PRD on every mutation.
- **PR-PRD-07 (Calendar Activities):** consumer — every activity status mutation (including batch-create and group-edit) routes through `require_role` and `write_audit`.
- **PR-PRD-08 (Campaign Management):** later consumer — does not block PR-PRD-08's initial ship. PR-PRD-08 lands its own raw audit writes (mirroring PR-PRD-01's interim approach) and retrofits them to call `write_audit` after this PRD ships. Once retrofitted, role gating is `editor`-minimum for create/patch; `admin`-minimum for delete of a non-generic campaign (generic deletions are already blocked in PR-PRD-08).
- **DM-PRD-00 (Migration Foundation):** adds the `project_plan_audit` collection-group composite index for the nightly BigQuery export scan (`at ASC`, cross-account).
- **DM-PRD-05 (Deletion Sweep Rewrite):** `project_plan_audit` is under `accounts/{account_id}/...` and is covered by `recursive_delete`. No special cleanup.
- **External:** BigQuery (destination for the audit archive). Re-use the existing GCP project and a new dataset `audit_archive_{env}`.
- **Existing files to study:** `api/src/kene_api/dependencies/auth.py` (or wherever `check_strategy_access` lives — see PR-PRD-01 §3), `api/src/kene_api/routers/project_plans.py` (existing audit-write sites).

## 4. Data contract

### `UserRole`

```
class UserRole(str, Enum):
    VIEWER   = "viewer"
    EDITOR   = "editor"
    APPROVER = "approver"
    ADMIN    = "admin"
```

Ordering: `viewer < editor < approver < admin`. `require_role(UserRole.APPROVER)` accepts approvers and admins.

### `AccountMember` — role storage

```
accounts/{account_id}/members/{user_id}

user_id: str
email: str
role: UserRole
created_at: datetime
updated_at: datetime
```

If a `members` subcollection already exists (verify at implementation start), extend it with a `role` field. Otherwise, create it. The caller's role is resolved once per request and cached on the request scope.

### Transition policy table

| Transition | Minimum role |
|------------|--------------|
| `Draft → Awaiting Approval` | `editor` |
| `Awaiting Approval → Approved` | `approver` |
| `Awaiting Approval → Rejected` | `approver` |
| `Awaiting Approval → Revision Requested` | `approver` |
| `Revision Requested → Draft` | `editor` |
| `Approved → Complete` | `editor` |
| Any non-listed transition | denied (`409 Conflict`) |

The status enum itself and the permitted-transition graph are owned by PR-PRD-01; this PRD only adds the role overlay.

### `AuditEntry`

```
audit_id: str                              # ULID (time-sortable)
account_id: str
resource_type: Literal[
    "project_plan", "plan_task", "campaign",
    "orphan_task", "plan_run"
]
resource_id: str                           # plan_id, task_id, campaign_id, run_id
parent_resource_id: str | None             # e.g. plan_id for a plan_task action
action: Literal[
    "create", "update", "delete",
    "status_transition", "attach", "detach",
    "approve", "reject", "request_revision",
    "batch_create", "group_edit", "run_start", "run_complete",
]
actor_user_id: str
actor_email: str
actor_role: UserRole
before_state: dict | None                  # resource snapshot pre-action (None on create)
after_state: dict | None                   # resource snapshot post-action (None on delete)
diff_summary: list[str]                    # human-readable deltas, e.g. ["status: Draft → Approved"]
request_id: str                            # correlation id (propagated from request middleware)
user_agent: str | None
ip_address: str | None                     # truncated to /24 (IPv4) or /48 (IPv6) for PII minimization
at: datetime                               # server time (UTC)
```

Document path:

```
accounts/{account_id}/project_plan_audit/{audit_id}
```

### Retention policy

- **Hot (Firestore):** 2 years. Entries older than 2 years are deleted nightly by a Cloud Scheduler job after successful export to BigQuery.
- **Archive (BigQuery):** indefinite. Dataset `audit_archive_{env}`, table `audit_entries`, partitioned by `DATE(at)`, clustered on `account_id, resource_type`.
- **Export cadence:** nightly (daily at 03:00 UTC). Re-entrant: partitioned by `at` date so re-running for a given day is idempotent.
- **Trim cadence:** nightly, after the export. The trim job deletes entries with `at < now() - 730 days` *only if* the corresponding BigQuery partition is present (else skip and alert).

### Helper: `write_audit(...)`

```python
async def write_audit(
    *,
    account_id: str,
    resource_type: ResourceType,
    resource_id: str,
    action: Action,
    actor: AuthenticatedUser,
    before_state: dict | None,
    after_state: dict | None,
    parent_resource_id: str | None = None,
) -> None:
    """Compose AuditEntry, compute diff_summary, persist to Firestore.

    Non-blocking: called inside the same Firestore transaction as the mutation
    it records, so either both commit or both fail.
    """
```

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `api/src/kene_api/models/audit_models.py` — `AuditEntry`, `UserRole`, `ResourceType`, `Action` enums |
| Create | `api/src/kene_api/services/audit_service.py` — `write_audit`, `compute_diff_summary` |
| Create | `api/src/kene_api/dependencies/rbac.py` — `require_role(min_role)`, transition policy table, `assert_transition_allowed(from_state, to_state, actor_role)` |
| Modify | `api/src/kene_api/routers/project_plans.py` (PR-PRD-01) — apply `require_role` on mutating endpoints; replace ad-hoc audit writes with `write_audit` |
| Modify | `api/src/kene_api/routers/campaigns.py` (PR-PRD-08) — same |
| Modify | `api/src/kene_api/routers/orphan_tasks.py` (PR-PRD-07) — same |
| Create | `api/src/kene_api/routers/internal/audit_archive.py` — `POST /internal/audit/export-to-bq` and `POST /internal/audit/trim-expired` (OIDC, Cloud Scheduler) |
| Create | `api/src/kene_api/services/audit_archive_service.py` — BigQuery export + trim logic |
| Create | `deployment/terraform/cloud_scheduler_audit_archive.tf` |
| Create | `deployment/terraform/bigquery_audit_archive.tf` — dataset + table + partitioning config |
| Create | `api/tests/unit/test_rbac_role_gate.py` |
| Create | `api/tests/unit/test_audit_diff_summary.py` |
| Create | `api/tests/integration/test_transition_role_enforcement.py` |
| Create | `api/tests/integration/test_audit_write_on_all_mutations.py` |
| Create | `api/tests/integration/test_audit_archive_and_trim.py` |

### Diff summary examples

```
before={"status": "Draft", "name": "X"}
after ={"status": "Approved", "name": "X"}
diff_summary = ["status: Draft → Approved"]

before={"tags": ["a", "b"]}
after ={"tags": ["a", "b", "c"]}
diff_summary = ["tags: added c"]

before=None, after={"name": "New plan"}
diff_summary = ["created"]
```

Keep diffs shallow (top-level fields only; deeply-nested diffs are out of scope in v1). Consumers that need structural diffs can compute from `before_state` / `after_state`.

### BigQuery export

```
# nightly export SQL (conceptual)
EXPORT DATA OPTIONS(
  uri='gs://kene-audit-export-{env}/{date}/*.json.gz',
  format='NEWLINE_DELIMITED_JSON',
  compression='GZIP'
) AS
SELECT *
FROM `kene-{env}.audit_staging.audit_entries_{date}`

# then load into partitioned table
LOAD DATA INTO `kene-{env}.audit_archive.audit_entries`
  PARTITION BY DATE(at)
  CLUSTER BY account_id, resource_type
FROM 'gs://kene-audit-export-{env}/{date}/*.json.gz'
  FORMAT='NEWLINE_DELIMITED_JSON'
```

The exporter walks the `project_plan_audit` collection-group with the composite index (owned by DM-PRD-00) ordered by `at`, filtering `at >= yesterday_00:00 AND at < today_00:00`.

### Trim job safety

Before a trim runs, the exporter must have confirmed the BigQuery partition for the target date exists and is non-empty. If missing, the trim step logs a warning and skips — never deletes without confirmed archive.

## 6. API contract

### Consumed (dependency — no new user endpoint)

- `require_role(UserRole.APPROVER)` as a FastAPI dependency on the approval-sensitive endpoints owned by PR-PRD-01 / PR-PRD-07 / PR-PRD-08.
- `assert_transition_allowed(from, to, actor_role)` called by PR-PRD-01's transition endpoint before writing.
- `write_audit(...)` called from every mutating endpoint listed in §5.

### Internal (OIDC, Cloud Scheduler)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/internal/audit/export-to-bq` | Export the prior day's audit entries to BigQuery. Body: `{date: "2026-04-20"}` (optional — defaults to yesterday UTC). |
| `POST` | `/api/v1/internal/audit/trim-expired` | Delete Firestore audit entries older than 2 years, conditional on archived partition presence. |

Both endpoints are OIDC-protected using the same SA pattern as A-PRD-2 / PR-PRD-06.

## 7. Acceptance criteria

1. A user with `role=editor` patching `status` from `Awaiting Approval → Approved` receives `403`. Same action by an `approver` succeeds.
2. A `viewer` user receives `403` on any create / patch / delete endpoint on plans, activities, orphan tasks, or campaigns.
3. An `admin` user receives `200/201` on every mutating endpoint (role ordering honored).
4. A non-listed transition (e.g. `Draft → Approved`) is rejected with `409`, regardless of actor role.
5. Every mutating endpoint writes exactly one audit entry (one per affected resource for batch/group operations).
6. The audit entry contains: `actor_email`, `actor_role`, `action`, `before_state`, `after_state`, `diff_summary`, `request_id`, truncated `ip_address`, `at`. Inspecting one via Firestore matches the `AuditEntry` schema.
7. `diff_summary` on a status transition reads `"status: <from> → <to>"`. On a tag add/remove, reads `"tags: added X"` or `"tags: removed X"`.
8. Cross-account audit access: a request from account A cannot read audit entries from account B (enforced by the collection path + account-scoped dependency).
9. The nightly BigQuery export runs, producing a partition in `audit_archive.audit_entries` keyed on `DATE(at)`. Re-running for the same date is idempotent (no duplicates — partition replace semantics).
10. The trim job deletes Firestore entries with `at < now - 730 days`, and only if the matching BigQuery partition is present. If the partition is missing, the job logs and skips.
11. Terraform provisions: the Cloud Scheduler job (daily 03:00 UTC), the BigQuery dataset/table, and IAM bindings (audit-service SA has `roles/bigquery.dataEditor` on the dataset only).
12. All unit and integration tests pass; `make lint` clean.

## 8. Test plan

**Unit tests** (`test_rbac_role_gate.py`):
- Each role × each transition → matches the policy table
- `require_role(APPROVER)` accepts `approver` and `admin`; rejects `editor` and `viewer`
- Unknown role on member doc → treated as `viewer` (least privilege)

**Unit tests** (`test_audit_diff_summary.py`):
- Status change → `"status: X → Y"`
- Tag add / remove → correct phrasing
- Multiple changes in one mutation → one line per changed field
- No-op update (before == after) → `diff_summary == []`, entry still written (for provenance)
- `before=None` (create) → `["created"]`; `after=None` (delete) → `["deleted"]`

**Integration tests** (`test_transition_role_enforcement.py`):
- Seed a plan + members with each role
- For each (role, transition) pair in the policy table → call the transition endpoint and assert status code
- Rejected transitions do not write audit entries for the attempted change (they may write an "access_denied" entry; out of scope for v1 — confirm with PM before adding)

**Integration tests** (`test_audit_write_on_all_mutations.py`):
- For each mutating endpoint in PR-PRD-01, PR-PRD-07, PR-PRD-08: call it; assert one audit entry present with the expected fields
- Batch create (PR-PRD-07): 5 tasks created → 5 audit entries
- Group edit (PR-PRD-07): 3 tasks patched → 3 audit entries

**Integration tests** (`test_audit_archive_and_trim.py`):
- Seed 10 audit entries dated 3 years ago
- Run export → partition in BigQuery contains 10 rows
- Run trim → the 10 entries are deleted from Firestore
- Repeat trim without re-export (simulate missing partition for a different date) → skip + warning, entries untouched
- Idempotency: re-run export for the same date → no duplicate rows in the partition

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| Role lookups on every request add latency | Cache the member doc per request scope; cache hit is free after the first access-control dependency resolves. |
| Audit writes inflate write QPS | Audit write is in the same transaction as the mutation it records — one logical write, at most one round-trip. Firestore handles this volume at current scale. |
| Denying rejected transitions vs. rejected audits — should we audit *attempts*? | Out of scope for v1. Revisit if security team requests. |
| `ip_address` truncation and PII | Truncated to /24 (IPv4) or /48 (IPv6) at write time; BigQuery archive inherits the truncated form. |
| BigQuery dataset provisioning drift | Terraform owns the schema; CI runs `terraform plan` on PRs touching the dataset module. |
| A new consumer forgets to call `write_audit` | Code review checklist addition (lint rule if feasible). Not enforceable at compile time; documented in the component README. |
| Role ordering wrong (e.g., approver > admin by accident) | Unit test pins the ordering explicitly. |
| Archived partition present but corrupt | Manual incident response. Trim job's "partition present and non-empty" check is the first defense. |

### Open questions

- **Q:** Should `viewer` be the default for a new account member, or should new members require explicit role assignment by an admin? → **Proposed default: `viewer`.** An admin promotes explicitly.
- **Q:** Should we audit role-change events themselves? → **Yes**, using the same `AuditEntry` schema with `resource_type="account_member"`, `action="update"`. Added to the transition policy: only `admin` can change roles.
- **Q:** Retention override for customers with shorter compliance windows? → Deferred. Today: single 2-year policy for all accounts.

## 10. Reference

- Foundation: [PR-PRD-01](../../project-tasks/projects/PR-PRD-01-data-model-and-api.md) §4 (`TaskStatus`, transition endpoint), §6 (audit endpoint)
- Consumers: [PR-PRD-07](../../project-tasks/projects/PR-PRD-07-calendar-activities.md) §6, [PR-PRD-08](../../project-tasks/projects/PR-PRD-08-campaign-management.md) §6
- Shape B conventions: [DM-PRD-00](./DM-PRD-00-migration-foundation.md)
- Deletion cascade: [DM-PRD-05](./DM-PRD-05-deletion-sweep-rewrite.md)
- Pattern: `api/src/kene_api/routers/strategy.py` (existing audit writes)
- CLAUDE.md rules in scope: C-1, C-5; D-1, D-5; PY-1, PY-2, PY-7; T-1, T-3, T-4, T-5, T-7, T-8
