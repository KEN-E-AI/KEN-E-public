# DM-PRD-07 — Roles, Members, Audit Substrate

**Status:** Blocked — resumes once PR-PRD-01 and DM-PRD-05 ship
**Owner team:** Backend / Platform
**Blocked by:** PR-PRD-01 (status enum + transition endpoints this PRD gates); DM-PRD-05 (ensures `recursive_delete` covers the new audit + members subcollections, and the user-deletion sweep cleans `members` rows across orgs/accounts)
**Blocks:** PR-PRD-07 (all approval-sensitive endpoints call this PRD's gate); IN-PRD-01, BL-PRD-01, SE-PRD-01, DP-PRD-01 (consumers of the generalized audit substrate)
**Estimated effort:** 4–5 days

---

## 1. Context

The Figma-designed Calendar page models a six-state status lifecycle for activities (`Draft → Awaiting Approval → Approved → Complete`, with `Rejected` and `Revision Requested → Draft` branches). PR-PRD-01 publishes the enum and the transition endpoints but leaves four cross-cutting gaps that no other component owns:

1. **No formal role model.** Every authenticated user can make every transition. Product requires that `Approved` / `Rejected` transitions be restricted to an `approver` role (or higher), while `Draft ↔ Awaiting Approval` is available to any editor.
2. **No member storage.** Today, membership lives on `users/{user_id}.permissions.organizations.{org_id}` (`admin` / `view`) and `users/{user_id}.permissions.account_permissions.{account_id}`. Two distinct concerns (org-level relationship + per-account access) are conflated on the user doc — a Shape D-style nested-map pattern that doesn't scale and isn't the right home for a 4-value account-level role.
3. **No formal audit-log document shape, and no shared writer.** PR-PRD-01 writes to `project_plan_audit/{audit_id}` but does not specify the document structure (who changed what, before/after snapshots, actor email, action type, IP/user-agent, correlation id). Five other components (Integrations, Billing, SAR-E, Data Pipeline, Calendar Activities) need the same primitive but with different parent paths and different resource/action enums.
4. **No retention policy.** The audit data must be retained long enough to satisfy compliance and long enough to support investigation of user-visible incidents, but Firestore storage grows unboundedly without a policy.

This PRD delivers all four:

- A two-tier role model (`OrgRole` + `AccountRole`) with explicit overlay rules.
- Two new Shape B subcollections for member storage (one org-scoped, one account-scoped) plus a one-time hybrid migration off the user-doc field tree.
- A generalized `write_audit(...)` substrate with a per-component registry of allowed `(parent_kind, audit_subcollection, resource_type, action)` tuples — every mutating endpoint in KEN-E writes via this single helper.
- Two-year hot retention in Firestore + nightly export to a single combined BigQuery archive.

It lives under Data Management because all four concerns are platform-level conventions consumed by every component.

## 2. Scope

### In scope

**Role model**
- `OrgRole` enum (`admin | member`) and `AccountRole` enum (`viewer | editor | approver | admin`)
- Member storage at `organizations/{org_id}/members/{user_id}` (org-scoped) and `accounts/{account_id}/members/{user_id}` (account-scoped, explicit grants only)
- Bootstrap rules (§4.4): org creator becomes org `admin`; account creator typically inherits via overlay
- Overlay resolution helper `resolve_effective_account_role(user_id, account_id) -> AccountRole | None`
- FastAPI dependency `require_role(min_role, scope=Org|Account)` usable from any router
- Member CRUD endpoints (org-scope + account-scope) — see §6
- Transition policy table for the project-plan status lifecycle (consumed by PR-PRD-01 / PR-PRD-07)

**Member migration (one-time, `members_migration` resource on the DM-PRD-00 framework)**
- Migrate `users/{user_id}.permissions.organizations.{org_id}` (values `"admin"` / `"view"`) → `organizations/{org_id}/members/{user_id}` (`admin` / `member`); legacy field tree dropped
- Migrate `users/{user_id}.permissions.account_permissions.{account_id}` → `accounts/{account_id}/members/{user_id}` with role assignment per the mapping in §4.5; legacy field tree dropped
- Retrofit the existing `PUT/DELETE /api/v1/firestore/organizations/{organization_id}/members/{user_id}` endpoints (`routers/firestore.py:2442`, `:2576`) to write to the new subcollection paths

**Generalized audit substrate**
- Generalized `AuditEntry` Pydantic model (open `resource_type: str`, open `action: str`, configurable `parent_kind` + `parent_id` + `audit_subcollection`)
- Per-component registry — consumers register `(parent_kind, audit_subcollection, ResourceType: Literal[...], Action: Literal[...])` tuples; writes that don't match the registry are rejected
- `write_audit(...)` helper used by PR-PRD-01, PR-PRD-07, IN-PRD-01, IN-PRD-05, BL-PRD-01, BL-PRD-03, BL-PRD-05, SE-PRD-01/02/07, DP-PRD-01, and any future consumer
- Six audit subcollections registered in v1:
  - `accounts/{account_id}/project_plan_audit/{audit_id}` — PR-PRD-01 / PR-PRD-07 / PR-PRD-08
  - `accounts/{account_id}/integrations_audit/{audit_id}` — IN-PRD-01 / IN-PRD-05 / IN-PRD-07
  - `organizations/{org_id}/billing_audit/{audit_id}` — BL-PRD-01 / BL-PRD-03 / BL-PRD-05
  - `accounts/{account_id}/sar_e_audit/{audit_id}` — SE-PRD-01 / SE-PRD-02 / SE-PRD-07
  - `accounts/{account_id}/data_pipeline_audit/{audit_id}` — DP-PRD-01
  - `organizations/{org_id}/account_member_audit/{audit_id}` and `accounts/{account_id}/account_member_audit/{audit_id}` — this PRD (member-CRUD events)

**Retention + archive**
- 2 years hot in Firestore for every registered audit subcollection
- Nightly export to one combined BigQuery table `audit_archive_{env}.audit_entries` with `parent_kind` / `parent_id` / `audit_subcollection` columns, partitioned by `DATE(at)`, clustered on `parent_kind, resource_type`
- Cloud Scheduler trim job that deletes Firestore entries older than 2 years (only after the matching BQ partition is confirmed present and non-empty)

**Tests**
- Unit tests for the role gate, overlay resolver, audit registry, and diff helper
- Integration tests for transition denial, audit-write coverage, member-CRUD lifecycle, and archive + trim

### Out of scope

- Role-assignment admin UI (separate frontend project — bare API ships here)
- OIDC / SSO group-to-role mapping (handled elsewhere; this PRD only reads the persisted role)
- Audit of *read* operations (deferred — only writes/transitions audited in v1)
- Custom per-customer retention overrides (2-year default fits current contracts; revisit)
- BigQuery schema evolution tooling (one-shot schema)
- Cross-org member visibility / role inheritance across orgs (out of scope; one user × one org × N accounts)

## 3. Dependencies

- **PR-PRD-01:** owns the transition endpoint; calls `require_role(...)` and `write_audit(...)` from this PRD on every mutation.
- **PR-PRD-07 (Calendar Activities):** consumer — every activity status mutation (including batch-create and group-edit) routes through `require_role` and `write_audit`.
- **PR-PRD-08 (Campaign Management):** later consumer — does not block PR-PRD-08's initial ship. PR-PRD-08 lands its own raw audit writes (mirroring PR-PRD-01's interim approach) and retrofits them to call `write_audit` after this PRD ships.
- **DM-PRD-00 (Migration Foundation):** registers the `members_migration` resource and adds the collection-group composite indexes for `project_plan_audit` (`at ASC`), `members` (`role ASC`), and a generic `audit_at_idx` for the nightly BQ export scan across audit subcollections.
- **DM-PRD-05 (Deletion Sweep Rewrite):** ensures `recursive_delete(accounts/{account_id})` and `recursive_delete(organizations/{org_id})` cover all member + audit subcollections, and that the user-deletion sweep cleans cross-account/org `members/{user_id}` rows.
- **External:** BigQuery (destination for the audit archive). Reuse the existing GCP project and a new dataset `audit_archive_{env}`.
- **Existing files to study:** `api/src/kene_api/routers/firestore.py` (L2300-2620 — existing org-member endpoints; retrofit target), `api/src/kene_api/auth/cached_user_context.py` (cache invalidation pattern), `api/src/kene_api/services/account_service.py` (account-creation hook — bootstrap insertion point), `api/src/kene_api/auth/user_context.py` (where `permissions` is read today).

## 4. Data contract

### 4.1 Role enums

```python
class OrgRole(str, Enum):
    ADMIN  = "admin"
    MEMBER = "member"

class AccountRole(str, Enum):
    VIEWER   = "viewer"
    EDITOR   = "editor"
    APPROVER = "approver"
    ADMIN    = "admin"
```

Ordering within each enum: `member < admin`, `viewer < editor < approver < admin`. `require_role(AccountRole.APPROVER)` accepts approvers and admins; `require_role(OrgRole.ADMIN)` accepts org admins only.

### 4.2 Member storage

```
organizations/{org_id}/members/{user_id}
    user_id: str
    email: str
    role: OrgRole                   # admin | member
    created_at: datetime
    updated_at: datetime
    invited_by: str | None          # user_id of inviting admin
    last_role_change_by: str | None # user_id who last set this role

accounts/{account_id}/members/{user_id}
    user_id: str
    email: str
    role: AccountRole               # viewer | editor | approver | admin
    created_at: datetime
    updated_at: datetime
    granted_by: str                 # user_id of granting admin
    last_role_change_by: str | None
```

Account-level member docs are **explicit grants only** — they exist when an admin assigns a non-default role to a user. Org-level docs always exist for every member of an org (so org membership is the source of truth for "is this user in this org at all").

### 4.3 Effective-role resolution (overlay)

```python
def resolve_effective_account_role(user_id: str, account_id: str) -> AccountRole | None:
    """Compute the user's effective role on an account.

    Returns None if the user has no access to the account at all.
    """
    org_id = get_account_organization(account_id)            # cached
    org_member = get_org_member(org_id, user_id)             # cached
    if org_member is None:
        return None                                          # not in the org → no access

    # 1. Explicit per-account grant wins
    explicit = get_account_member(account_id, user_id)
    if explicit is not None:
        return explicit.role

    # 2. Overlay from org role
    if org_member.role == OrgRole.ADMIN:
        return AccountRole.ADMIN
    if org_member.role == OrgRole.MEMBER:
        return AccountRole.VIEWER

    return None  # unreachable (enum-exhaustive), but explicit
```

Cached per request scope (single Firestore read amortized across every dependency that resolves the role).

### 4.4 Bootstrap rules

| Trigger | Effect |
|---------|--------|
| User creates an organization | `organizations/{org_id}/members/{creator_user_id}` written with `role=admin`, `invited_by=null` |
| User creates an account inside an org | If creator is org `admin`, no account-level `members` doc is written (overlay handles it). If creator is org `member`, `accounts/{account_id}/members/{creator_user_id}` written with `role=admin` (rare edge case — typically blocked at the org level, but valid if product allows) |
| Admin invites a new user to an org | `organizations/{org_id}/members/{user_id}` written with `role=member` (default). Promotion to `admin` requires an explicit `PATCH`. |
| Admin grants an explicit account-level role to a user | `accounts/{account_id}/members/{user_id}` written with the granted role |
| User is removed from an org | DM-PRD-05 user-deletion sweep is the cleanest path. For "remove from this org but keep the user," delete the `organizations/{org_id}/members/{user_id}` doc + every `accounts/{account_id}/members/{user_id}` doc under accounts in that org (collection-group filter on `account_id IN org_accounts`). IN-PRD-05's `on-user-removed` hook fires per affected account. |

### 4.5 Hybrid migration mapping

Source (existing user-doc field tree):

```
users/{user_id}.permissions.organizations.{org_id} ∈ {"admin", "view"}
users/{user_id}.permissions.account_permissions.{account_id} = ...  # legacy shape — variable
```

Target (new subcollections):

```
organizations/{org_id}/members/{user_id}.role:
    "admin" → OrgRole.ADMIN
    "view"  → OrgRole.MEMBER

accounts/{account_id}/members/{user_id}.role:
    Per-account overrides preserved as explicit grants. The legacy values are
    coarse (often just "granted" booleans); the migration assigns AccountRole
    based on the parent org role:
      org "admin" + account_permissions present → AccountRole.ADMIN (explicit)
      org "view"  + account_permissions present → AccountRole.EDITOR (explicit, conservative default)
      org "view"  + no account_permissions      → no doc (overlay → VIEWER)
      org "admin" + no account_permissions      → no doc (overlay → ADMIN)
```

**Conservative-default rationale:** the legacy `account_permissions` map signals the user was deliberately given access; bumping them from the overlay's `viewer` to explicit `editor` preserves their working capability. If a customer needs `approver` for a specific user post-migration, an admin promotes them via the new API.

The migration is registered as the `members_migration` resource on DM-PRD-00's `migrate_to_shape_b.py` framework (uses a custom migration class — the resource `_is_field_migration: True` flag tells the runner to walk source field paths instead of source collections).

### 4.6 Transition policy table

| Transition | Minimum account role |
|------------|----------------------|
| `Draft → Awaiting Approval` | `editor` |
| `Awaiting Approval → Approved` | `approver` |
| `Awaiting Approval → Rejected` | `approver` |
| `Awaiting Approval → Revision Requested` | `approver` |
| `Revision Requested → Draft` | `editor` |
| `Approved → Complete` | `editor` |
| Any non-listed transition | denied (`409 Conflict`) |

The status enum and the permitted-transition graph are owned by PR-PRD-01; this PRD only adds the role overlay.

### 4.7 Generalized `AuditEntry`

```python
class AuditEntry(BaseModel):
    audit_id: str                              # ULID (time-sortable)
    parent_kind: Literal["account", "organization"]
    parent_id: str                             # account_id or org_id
    audit_subcollection: str                   # e.g. "project_plan_audit", "billing_audit"
    resource_type: str                         # registered per consumer; see registry
    resource_id: str                           # plan_id, connection_id, subscription_id, ...
    parent_resource_id: str | None             # e.g. plan_id for a plan_task action
    action: str                                # registered per consumer; see registry
    actor_user_id: str
    actor_email: str
    actor_role: OrgRole | AccountRole | None   # None for super-admin or system actors
    actor_kind: Literal["user", "system", "super_admin"]
    before_state: dict | None                  # resource snapshot pre-action (None on create)
    after_state: dict | None                   # resource snapshot post-action (None on delete)
    diff_summary: list[str]                    # human-readable deltas, e.g. ["status: Draft → Approved"]
    request_id: str                            # correlation id
    user_agent: str | None
    ip_address: str | None                     # truncated to /24 (IPv4) or /48 (IPv6)
    at: datetime                               # server time (UTC)
```

Document path is computed from `parent_kind` + `parent_id` + `audit_subcollection`:
- `parent_kind="account"` → `accounts/{parent_id}/{audit_subcollection}/{audit_id}`
- `parent_kind="organization"` → `organizations/{parent_id}/{audit_subcollection}/{audit_id}`

### 4.8 Audit registry

Per-component registry lives at `api/src/kene_api/services/audit_registry.py`. Each entry pins the allowed `(parent_kind, audit_subcollection, resource_types, actions)` set. `write_audit(...)` rejects writes outside the registry with `AuditRegistryError`.

```python
@dataclass(frozen=True)
class AuditDescriptor:
    parent_kind: Literal["account", "organization"]
    audit_subcollection: str
    resource_types: frozenset[str]
    actions: frozenset[str]
    owning_component: str       # for grep / blame

REGISTRY: list[AuditDescriptor] = [
    AuditDescriptor(
        parent_kind="account",
        audit_subcollection="project_plan_audit",
        resource_types=frozenset({
            "project_plan", "plan_task", "campaign", "orphan_task", "plan_run",
        }),
        actions=frozenset({
            "create", "update", "delete",
            "status_transition", "attach", "detach",
            "approve", "reject", "request_revision",
            "batch_create", "group_edit", "run_start", "run_complete",
        }),
        owning_component="project-tasks",
    ),
    AuditDescriptor(
        parent_kind="account",
        audit_subcollection="integrations_audit",
        resource_types=frozenset({"platform_connection"}),
        actions=frozenset({
            "connected", "refreshed", "revoked",
            "reauth_requested", "used", "error", "tested",
        }),
        owning_component="integrations",
    ),
    AuditDescriptor(
        parent_kind="organization",
        audit_subcollection="billing_audit",
        resource_types=frozenset({
            "billing_profile", "subscription", "checkout_session",
            "invoice", "manual_override",
        }),
        actions=frozenset({
            "profile_created", "checkout_started", "subscription_created",
            "subscription_updated", "subscription_canceled",
            "invoice_paid", "invoice_failed",
            "manual_override_applied", "sales_handoff",
        }),
        owning_component="billing",
    ),
    AuditDescriptor(
        parent_kind="account",
        audit_subcollection="sar_e_audit",
        resource_types=frozenset({
            "sar_e_config", "effectiveness_kpi", "funnel_mapping",
            "thresholds", "channel_coverage", "target",
        }),
        actions=frozenset({
            "create", "update", "delete",
            "setup_completed", "ingest", "retrain",
            "ab_config_update", "target_derive", "target_save",
        }),
        owning_component="sar-e",
    ),
    AuditDescriptor(
        parent_kind="account",
        audit_subcollection="data_pipeline_audit",
        resource_types=frozenset({"data_pipeline_job", "data_pipeline_run"}),
        actions=frozenset({"create", "update", "delete", "run", "cached"}),
        owning_component="data-pipeline",
    ),
    AuditDescriptor(
        parent_kind="account",
        audit_subcollection="account_member_audit",
        resource_types=frozenset({"account_member"}),
        actions=frozenset({"grant", "update_role", "revoke"}),
        owning_component="data-management",
    ),
    AuditDescriptor(
        parent_kind="organization",
        audit_subcollection="account_member_audit",
        resource_types=frozenset({"org_member"}),
        actions=frozenset({"invite", "update_role", "remove"}),
        owning_component="data-management",
    ),
]
```

Adding a new audit consumer is a one-line append to the registry — no helper changes, no schema migration.

### 4.9 Retention policy

- **Hot (Firestore):** 2 years for every registered audit subcollection. Entries older than 2 years are deleted nightly by the trim job after successful export.
- **Archive (BigQuery):** indefinite. Dataset `audit_archive_{env}`, table `audit_entries`, partitioned by `DATE(at)`, clustered on `parent_kind, resource_type`.
- **Export cadence:** nightly (daily at 03:00 UTC). Re-entrant: partitioned by `at` date so re-running for a given day is idempotent (partition replace semantics).
- **Trim cadence:** nightly, after the export. The trim job deletes entries with `at < now() - 730 days` *only if* the corresponding BigQuery partition is present and non-empty (else skip and alert).

### 4.10 Helper signatures

```python
async def write_audit(
    *,
    parent_kind: Literal["account", "organization"],
    parent_id: str,
    audit_subcollection: str,
    resource_type: str,
    resource_id: str,
    action: str,
    actor: AuthenticatedActor,
    before_state: dict | None,
    after_state: dict | None,
    parent_resource_id: str | None = None,
) -> None:
    """Compose AuditEntry, validate against the registry, persist to Firestore.

    Raises AuditRegistryError if (parent_kind, audit_subcollection, resource_type, action)
    is not in REGISTRY. Non-blocking on the audited mutation: called inside the same
    Firestore transaction so either both commit or both fail.
    """

def require_role(
    min_role: OrgRole | AccountRole,
    *,
    scope: Literal["org", "account"],
):
    """FastAPI dependency that enforces role ≥ min_role at the given scope.

    For scope='account', resolves via `resolve_effective_account_role`.
    For scope='org', reads `organizations/{org_id}/members/{user_id}.role`.
    Returns 403 with structured body on rejection.
    """

def assert_transition_allowed(
    from_state: PlanStatus,
    to_state: PlanStatus,
    actor_role: AccountRole,
) -> None:
    """Raise HTTPException(409) if the transition is not in the policy table.
    Raise HTTPException(403) if actor_role is below the required minimum."""
```

`AuthenticatedActor` is a dataclass that wraps either a `UserContext` (real user), a system actor (Cloud Scheduler / internal cron), or a super-admin actor. The audit writer fills `actor_kind` accordingly.

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `api/src/kene_api/models/role_models.py` — `OrgRole`, `AccountRole`, `OrgMember`, `AccountMember`, ordering helpers |
| Create | `api/src/kene_api/models/audit_models.py` — `AuditEntry`, `AuditDescriptor`, `AuditRegistryError` |
| Create | `api/src/kene_api/services/audit_registry.py` — `REGISTRY` list (§4.8) |
| Create | `api/src/kene_api/services/audit_service.py` (extend existing) — `write_audit`, `compute_diff_summary`, registry validation |
| Create | `api/src/kene_api/services/member_service.py` — `get_org_member`, `get_account_member`, `resolve_effective_account_role`, `grant_account_role`, `update_account_role`, `revoke_account_role`, `invite_org_member`, `update_org_role`, `remove_org_member`; with request-scope cache |
| Create | `api/src/kene_api/dependencies/rbac.py` — `require_role(min_role, scope)`, `assert_transition_allowed`, transition policy table |
| Create | `api/src/kene_api/routers/members.py` — member CRUD endpoints (§6) |
| Modify | `api/src/kene_api/routers/firestore.py` (L2300–L2620) — retrofit existing `PUT/DELETE /organizations/{organization_id}/members/{user_id}` to write to the new subcollection paths via `member_service`; legacy field updates removed |
| Modify | `api/src/kene_api/services/account_creation_service.py` — bootstrap hook: insert `accounts/{account_id}/members/{creator_user_id}` only for the org-member creator edge case (§4.4); otherwise rely on overlay |
| Modify | `api/src/kene_api/services/account_service.py` (or wherever org-creation lives) — bootstrap hook: insert `organizations/{org_id}/members/{creator_user_id}` with `role=admin` |
| Modify | `api/src/kene_api/auth/user_context.py` — read role from new subcollections, not from `users.permissions.*` |
| Modify | `api/src/kene_api/routers/project_plans.py` (PR-PRD-01) — apply `require_role(scope="account")` on mutating endpoints; replace ad-hoc audit writes with `write_audit` |
| Modify | `api/src/kene_api/routers/campaigns.py` (PR-PRD-08) — same |
| Modify | `api/src/kene_api/routers/orphan_tasks.py` (PR-PRD-07) — same |
| Create | `api/scripts/_migrate_shape_b/members_migration.py` — one-shot migration of `users.permissions.organizations.*` and `users.permissions.account_permissions.*` into the new subcollections (registered as the `members_migration` resource on the DM-PRD-00 framework) |
| Create | `api/src/kene_api/routers/internal/audit_archive.py` — `POST /internal/audit/export-to-bq` and `POST /internal/audit/trim-expired` (OIDC, Cloud Scheduler) |
| Create | `api/src/kene_api/services/audit_archive_service.py` — BigQuery export + trim logic walking every registered audit subcollection |
| Create | `deployment/terraform/cloud_scheduler_audit_archive.tf` |
| Create | `deployment/terraform/bigquery_audit_archive.tf` — dataset + table + partitioning config |
| Create | `api/tests/unit/test_rbac_role_gate.py` |
| Create | `api/tests/unit/test_account_role_overlay.py` |
| Create | `api/tests/unit/test_audit_registry.py` |
| Create | `api/tests/unit/test_audit_diff_summary.py` |
| Create | `api/tests/integration/test_transition_role_enforcement.py` |
| Create | `api/tests/integration/test_audit_write_on_all_mutations.py` |
| Create | `api/tests/integration/test_member_crud_lifecycle.py` |
| Create | `api/tests/integration/test_members_migration.py` |
| Create | `api/tests/integration/test_audit_archive_and_trim.py` |

### 5.1 Diff summary examples

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

### 5.2 BigQuery export

The exporter walks each registered audit subcollection via collection-group queries (one collection-group index per `audit_subcollection` value, pre-built by DM-PRD-00). Rows are unioned and written to the combined `audit_archive_{env}.audit_entries` table.

```
# nightly export (conceptual)
for descriptor in REGISTRY:
    rows = collection_group(descriptor.audit_subcollection) \
              .where("at", ">=", yesterday_00_00_utc) \
              .where("at", "<",  today_00_00_utc) \
              .stream()
    yield from rows  # already include parent_kind / parent_id / audit_subcollection

LOAD DATA INTO `kene-{env}.audit_archive.audit_entries`
  PARTITION BY DATE(at)
  CLUSTER BY parent_kind, resource_type
FROM 'gs://kene-audit-export-{env}/{date}/*.json.gz'
  FORMAT='NEWLINE_DELIMITED_JSON'
```

### 5.3 Trim job safety

Before a trim runs, the exporter must have confirmed the BigQuery partition for the target date exists and is non-empty (per registered subcollection if you want strict-per-subcollection — v1 uses combined-table presence as the gate). If missing, the trim step logs a warning and skips — never deletes without confirmed archive.

## 6. API contract

### 6.1 Member CRUD (new — owned by this PRD)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/organizations/{org_id}/members` | List org members. Returns `[OrgMember]`. Caller must be at least `member` of the org. |
| `POST` | `/api/v1/organizations/{org_id}/members` | Invite a user to the org (body: `{email, role}`). Caller must be org `admin`. Default `role=member`. |
| `PATCH` | `/api/v1/organizations/{org_id}/members/{user_id}` | Update org role (body: `{role}`). Caller must be org `admin`. |
| `DELETE` | `/api/v1/organizations/{org_id}/members/{user_id}` | Remove from org. Caller must be org `admin`. Triggers IN-PRD-05's `on-user-removed` hook for every affected account in the org. Cascades: deletes every `accounts/{account_id}/members/{user_id}` doc under accounts in this org. |
| `GET` | `/api/v1/accounts/{account_id}/members` | List account members. Returns `{explicit: [AccountMember], overlay: [{user_id, email, effective_role, source: "org_admin"\|"org_member"}]}`. Caller must have any role on the account. |
| `POST` | `/api/v1/accounts/{account_id}/members` | Grant explicit account-level role (body: `{user_id, role}`). Caller must be account `admin`. |
| `PATCH` | `/api/v1/accounts/{account_id}/members/{user_id}` | Update explicit role (body: `{role}`). Caller must be account `admin`. |
| `DELETE` | `/api/v1/accounts/{account_id}/members/{user_id}` | Revoke explicit grant (user reverts to overlay). Caller must be account `admin`. |

The pre-existing handlers in `routers/firestore.py:2442/2576` are retrofitted to write to the new paths and continue to work for callers using the old prefix; tests confirm both surfaces stay in sync until the legacy paths are deprecated (separate cleanup PR).

### 6.2 Consumed (dependency — no new user endpoint for audit)

- `require_role(...)` as a FastAPI dependency on every mutating endpoint owned by PR-PRD-01 / PR-PRD-07 / PR-PRD-08, IN-PRD-01 / IN-PRD-05, BL-PRD-01 / BL-PRD-03 / BL-PRD-05, SE-PRD-01 / SE-PRD-02 / SE-PRD-07, DP-PRD-01.
- `assert_transition_allowed(from, to, actor_role)` called by PR-PRD-01's transition endpoint before writing.
- `write_audit(...)` called from every mutating endpoint listed in the registry.

### 6.3 Internal (OIDC, Cloud Scheduler)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/internal/audit/export-to-bq` | Export the prior day's audit entries (across all registered subcollections) to BigQuery. Body: `{date: "2026-04-20"}` (optional — defaults to yesterday UTC). |
| `POST` | `/api/v1/internal/audit/trim-expired` | Delete Firestore audit entries older than 2 years across all registered subcollections, conditional on archived partition presence. |

Both endpoints are OIDC-protected using the same SA pattern as A-PRD-2 / PR-PRD-06.

## 7. Acceptance criteria

1. A user with account role `editor` patching `status` from `Awaiting Approval → Approved` receives `403`. Same action by an `approver` succeeds.
2. A user with no org membership receives `403` on any account-scoped endpoint.
3. An org `member` (no explicit account grant) receives `200` on `GET` endpoints for any account in the org (overlay → `viewer`) and `403` on `PATCH/POST/DELETE` endpoints.
4. An org `admin` receives `200/201/204` on every mutating account endpoint without a per-account `members` doc existing (overlay → `admin`).
5. A non-listed transition (e.g., `Draft → Approved`) is rejected with `409`, regardless of actor role.
6. Every mutating endpoint listed in the audit registry writes exactly one audit entry via `write_audit(...)` (one per affected resource for batch/group operations).
7. `write_audit(...)` rejects writes that don't match the registry (`AuditRegistryError` → `500` with structured cause; smoke test in CI).
8. The audit entry contains: `actor_email`, `actor_role`, `actor_kind`, `action`, `before_state`, `after_state`, `diff_summary`, `request_id`, truncated `ip_address`, `at`, `parent_kind`, `parent_id`, `audit_subcollection`. Inspecting one via Firestore matches the `AuditEntry` schema.
9. `diff_summary` on a status transition reads `"status: <from> → <to>"`. On a tag add/remove, reads `"tags: added X"` or `"tags: removed X"`.
10. Cross-account audit access: a request from account A cannot read audit entries from account B (enforced by the collection path + account-scoped dependency).
11. Cross-org billing-audit access: a request scoped to org X cannot read billing-audit entries from org Y.
12. Member-CRUD endpoints succeed/fail per the role-gate rules in §6.1 (16 cases tested — admin-can / admin-can / member-can / nobody-can across the 4 mutating endpoints, plus 4 read paths for overlay vs explicit).
13. `members_migration` resource on the DM-PRD-00 framework migrates a seeded fixture of 5 users × 3 orgs × 7 accounts with mixed `permissions` shapes, producing the §4.5 expected output. Re-running is a no-op.
14. After the migration, the legacy `users.permissions.organizations.*` and `users.permissions.account_permissions.*` field trees are absent from every user doc (verified by integration test querying every user).
15. The nightly BigQuery export runs across **all six** registered audit subcollections, producing a partition in `audit_archive.audit_entries` keyed on `DATE(at)`. Re-running for the same date is idempotent (partition replace semantics).
16. The trim job deletes Firestore entries with `at < now - 730 days` across all registered subcollections, and only if the matching BigQuery partition is present. If the partition is missing, the job logs and skips.
17. Terraform provisions: the Cloud Scheduler job (daily 03:00 UTC), the BigQuery dataset/table, and IAM bindings (audit-service SA has `roles/bigquery.dataEditor` on the dataset only).
18. Bootstrap hook: creating an org via the existing creation flow writes one `organizations/{org_id}/members/{creator_user_id}` doc with `role=admin`. Creating an account by an org admin writes zero account-level `members` docs (overlay handles it).
19. All unit and integration tests pass; `make lint` clean.

## 8. Test plan

**Unit tests** (`test_rbac_role_gate.py`):
- Each role × each transition → matches the policy table
- `require_role(APPROVER, scope="account")` accepts `approver` and `admin`; rejects `editor` and `viewer`
- `require_role(ADMIN, scope="org")` accepts org `admin`; rejects org `member`
- Unknown role on member doc → treated as `viewer` (least privilege)

**Unit tests** (`test_account_role_overlay.py`):
- Org admin + no explicit doc → `AccountRole.ADMIN`
- Org admin + explicit doc with `editor` → explicit wins → `AccountRole.EDITOR`
- Org member + no explicit doc → `AccountRole.VIEWER`
- Org member + explicit doc with `approver` → explicit wins → `AccountRole.APPROVER`
- Non-org user + any account → `None`
- Cache hits: second call within request scope is a no-Firestore-read

**Unit tests** (`test_audit_registry.py`):
- Every entry in §4.8 is registered
- Adding a non-registered `(parent_kind, audit_subcollection, resource_type, action)` raises `AuditRegistryError`
- Two consumers writing to the same `audit_subcollection` with disjoint `resource_types` is allowed (e.g., `account_member_audit` for org-scope and account-scope)

**Unit tests** (`test_audit_diff_summary.py`):
- Status change → `"status: X → Y"`
- Tag add / remove → correct phrasing
- Multiple changes in one mutation → one line per changed field
- No-op update (before == after) → `diff_summary == []`, entry still written (for provenance)
- `before=None` (create) → `["created"]`; `after=None` (delete) → `["deleted"]`

**Integration tests** (`test_transition_role_enforcement.py`):
- Seed a plan + members with each role
- For each (role, transition) pair in the policy table → call the transition endpoint and assert status code

**Integration tests** (`test_audit_write_on_all_mutations.py`):
- For each mutating endpoint in PR-PRD-01, PR-PRD-07, PR-PRD-08, IN-PRD-01, BL-PRD-01, SE-PRD-01, DP-PRD-01: call it; assert one audit entry present in the right subcollection with the expected fields
- Batch create (PR-PRD-07): 5 tasks created → 5 audit entries
- Group edit (PR-PRD-07): 3 tasks patched → 3 audit entries
- Cross-component smoke: a single test seeds one mutation per registered consumer and asserts each lands in its declared subcollection

**Integration tests** (`test_member_crud_lifecycle.py`):
- Org admin invites user → org-member doc exists, audit entry in `organizations/{org_id}/account_member_audit`
- Org admin promotes user to admin → `update_role` audit entry
- Org admin grants account-level approver to a non-org-admin user → `accounts/{account_id}/members/{user_id}` doc + audit entry in `accounts/{account_id}/account_member_audit`
- Account admin revokes explicit grant → user reverts to org-overlay role
- Org admin removes user from org → user's org-member doc + every account-level explicit doc in this org deleted, IN-PRD-05 hook fires

**Integration tests** (`test_members_migration.py`):
- Seed 5 users × 3 orgs × 7 accounts with mixed legacy `permissions` shapes
- Run migration
- Assert §4.5 mapping holds for every produced doc
- Assert `users.permissions.organizations` and `users.permissions.account_permissions` field trees are deleted
- Re-run is a no-op

**Integration tests** (`test_audit_archive_and_trim.py`):
- Seed 10 audit entries dated 3 years ago across all 6 registered subcollections
- Run export → partition in BigQuery contains 60 rows
- Run trim → the 60 entries are deleted from Firestore
- Repeat trim without re-export (simulate missing partition for a different date) → skip + warning, entries untouched
- Idempotency: re-run export for the same date → no duplicate rows in the partition

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| Role lookups on every request add latency | Cache the org-member + account-member docs per request scope; cache hit is free after the first access-control dependency resolves. |
| Audit writes inflate write QPS | Audit write is in the same transaction as the mutation it records — one logical write, at most one round-trip. Firestore handles this volume at current scale. |
| Denying rejected transitions vs. rejected audits — should we audit *attempts*? | Out of scope for v1. Revisit if security team requests. |
| `ip_address` truncation and PII | Truncated to /24 (IPv4) or /48 (IPv6) at write time; BigQuery archive inherits the truncated form. |
| BigQuery dataset provisioning drift | Terraform owns the schema; CI runs `terraform plan` on PRs touching the dataset module. |
| A new consumer forgets to register in §4.8 | `write_audit` raises `AuditRegistryError` at runtime; CI smoke test asserts every mutating router writes via `write_audit`. |
| Role ordering wrong | Unit test pins the ordering explicitly. |
| Archived partition present but corrupt | Manual incident response. Trim job's "partition present and non-empty" check is the first defense. |
| Migration touches every user doc — risk of partial failure | DM-PRD-00 idempotency contract applies. The runner skips users whose `permissions` field is already absent (resume-friendly). Pre-flight integration test on a snapshot fixture. |
| Legacy `users.permissions` field still read by some downstream code path | Pre-migration grep audit (Phase 0); failing CI grep on `users\.permissions\.` post-migration. |

### Open questions

- **Q:** Should `member` be the default for a new org member, or should new members require explicit role assignment by an admin? → **Default: `member`.** An admin promotes explicitly.
- **Q:** Should we audit role-change events themselves? → **Yes**, registered as `account_member_audit` for both org-scope and account-scope (§4.8). Only `admin` can trigger them.
- **Q:** Retention override for customers with shorter compliance windows? → Deferred. Today: single 2-year policy for all accounts.
- **Q:** Should `super_admin` (`@ken-e.ai`) bypass the role gate or pass through it as `admin`? → **Bypass.** `super_admin` actors set `actor_kind="super_admin"` on audit entries; `actor_role=null`.

## 10. Reference

- Foundation: [PR-PRD-01](../../project-tasks/projects/PR-PRD-01-data-model-and-api.md) §4 (`TaskStatus`, transition endpoint), §6 (audit endpoint)
- Consumers: [PR-PRD-07](../../project-tasks/projects/PR-PRD-07-calendar-activities.md) §6, [PR-PRD-08](../../project-tasks/projects/PR-PRD-08-campaign-management.md) §6, [IN-PRD-01](../../integrations/projects/IN-PRD-01-core-model-encryption.md), [IN-PRD-05](../../integrations/projects/IN-PRD-05-reauth-lifecycle.md), [BL-PRD-01](../../billing/projects/BL-PRD-01-core-model-stripe-foundation.md), [BL-PRD-05](../../billing/projects/BL-PRD-05-failure-modes-permissions.md), [SE-PRD-01](../../sar-e/projects/SE-PRD-01-configuration-foundation.md), [DP-PRD-01](../../data-pipeline/projects/DP-PRD-01-foundation.md)
- Shape B conventions: [DM-PRD-00](./DM-PRD-00-migration-foundation.md)
- Deletion cascade: [DM-PRD-05](./DM-PRD-05-deletion-sweep-rewrite.md)
- Pattern: `api/src/kene_api/routers/strategy.py` (existing audit writes), `api/src/kene_api/routers/firestore.py` (existing org-member endpoints)
- CLAUDE.md rules in scope: C-1, C-5; D-1, D-5; PY-1, PY-2, PY-7; T-1, T-3, T-4, T-5, T-7, T-8
