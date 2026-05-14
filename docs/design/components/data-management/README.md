# Data Management — Product Requirements Document

> **Linear Team:** [KEN-E] Data Management
> **Last Updated:** 2026-04-20
> **Status:** Active

## 1. Overview

The Data Management component owns the multi-tenant data model for KEN-E. It defines how account-scoped data is laid out in Firestore and Cloud Storage (GCS) so every downstream component — Strategy, Analytics, Skills, Project Tasks, Automations, Knowledge Graph — writes to a single, consistent, safely-isolated shape. This component owns no public API and no UI; it is a platform-level concern whose outputs are *conventions, migration scripts, and Firestore/GCS indexes* consumed by every other component.

Its immediate scope is the **Shape B migration plus the platform substrate that rides on it**: realigning every account-scoped Firestore collection under `accounts/{account_id}/{resource}/…`, splitting the legacy `organizations/{org_id}` nested accounts-map out to per-account docs, keeping GCS on the existing G1 prefix pattern, then layering a unified roles-and-audit substrate on top. Eight project PRDs (DM-PRD-00 through DM-PRD-07) break the work into parallelizable units — DM-PRD-00 is the blocking foundation; DM-PRD-01 through DM-PRD-04 then run in parallel across up to four dev teams; DM-PRD-05 rewrites the deletion sweep (account + user) once all four land; DM-PRD-06 does the staging cutover; DM-PRD-07 (after PR-PRD-01 lands) ships the two-tier role model, members storage, member-CRUD API, hybrid migration off the legacy `users.permissions.*` field tree, and the generalized audit substrate that every mutating endpoint in KEN-E writes through. Once this migration completes, the data-shape surface area across the codebase drops from four distinct patterns (Shape A/B/C/D) down to two (Shape B + Shape C) — giving every downstream component a single, unambiguous path contract to rely on.

KEN-E has no production users today, so this is a **single-cutover migration per environment** — no dual-write, no backwards-compatibility phase, no downtime window tracking. Repeatability across dev → staging → prod matters because the same migration script runs in each environment. The authoritative decision that drives this work is [Review 15 in DESIGN-REVIEW-LOG](../../DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1) — Multi-Tenant Data Model Shape (Firestore Subcollections + GCS Prefix G1); the step-by-step plan lives in [`./multi-tenant-migration-plan.md`](./multi-tenant-migration-plan.md).

## 2. Architecture

### 2.1 Key Directories

| Path | Purpose |
|------|---------|
| `api/scripts/migrate_to_shape_b.py` | Idempotent, verifiable, environment-agnostic migration CLI. Built by DM-PRD-00; resources registered by DM-PRD-01–DM-PRD-04. |
| `api/scripts/_migrate_shape_b/resources.py` | `MigrateConfig` registry — one entry per migrated resource. Authored in DM-PRD-00; extended by DM-PRD-01–DM-PRD-04. |
| `api/scripts/seed_shape_b_fixtures.py` | Seeds a realistic Shape B account for local dev; replaces any Shape A fixtures in tests. |
| `deployment/firestore.indexes.json` | Composite + collection-group indexes. |
| `deployment/terraform/firestore_indexes.tf` | Terraform wrapper for the indexes JSON. |
| `api/src/kene_api/firestore.py` | Field-path refactor target for the Shape D split (DM-PRD-03). |
| `api/src/kene_api/routers/accounts.py` (L968-997) | Account-deletion sweep — collapses to `firestore.recursive_delete(...)` in DM-PRD-05. |
| `api/src/kene_api/services/audit_service.py` (L189) | Broken `collection_group("strategy_audit")` query — goes live once DM-PRD-01 ships the new path + index. |
| `api/src/kene_api/services/storage_service.py` | GCS path helpers — G1 pattern retained, no changes required by this component. |

### 2.2 Data Flow

**Firestore target state** (what every downstream component reads/writes after migration):

```
accounts/{account_id}                                            # account root doc; some fields migrate here
                                                                 # from organizations/{org_id} in DM-PRD-03
accounts/{account_id}/strategy_docs/{doc_type}                   # was strategy_docs_{account_id}/
accounts/{account_id}/strategy_docs/{doc_type}/versions/{n}
accounts/{account_id}/strategy_audit/{audit_id}                  # was strategy_audit_{account_id}/
accounts/{account_id}/strategy_processing_state/{state_id}       # was strategy_processing_state_{account_id}/
accounts/{account_id}/agent_analytics/{metric_id}                # was agent_analytics_{account_id}/
accounts/{account_id}/cost_aggregations/{agg_id}                 # was cost_aggregations_{account_id}/
accounts/{account_id}/performance_profiles/{profile_id}          # was performance_profiles_{account_id}/
accounts/{account_id}/monitoring_topics/{topic_id}               # was monitoring_topics/{account_id} (Shape B-like → Shape B)
accounts/{account_id}/alert_configurations/{config_id}           # was alert_configurations/{account_id}

# Planned resources — land directly under Shape B (no Shape A intermediate stop):
accounts/{account_id}/skills/{skill_id}                          # Skills component
accounts/{account_id}/skills/{skill_id}/versions/{n}
accounts/{account_id}/project_plans/{plan_id}                    # Project Tasks component
accounts/{account_id}/project_plans/{plan_id}/versions/{n}
accounts/{account_id}/project_plan_audit/{audit_id}              # shape owned by DM-PRD-07
accounts/{account_id}/orphan_tasks/{task_id}                     # PR-PRD-07 — standalone tasks
accounts/{account_id}/campaigns/{campaign_id}                    # PR-PRD-08 — first-class Campaigns
accounts/{account_id}/members/{user_id}                          # DM-PRD-07 — explicit account-level role grants only
accounts/{account_id}/integrations_audit/{audit_id}              # DM-PRD-07 — Integrations audit subcollection
accounts/{account_id}/sar_e_audit/{audit_id}                     # DM-PRD-07 — SAR-E audit subcollection
accounts/{account_id}/data_pipeline_audit/{audit_id}             # DM-PRD-07 — Data Pipeline audit subcollection
accounts/{account_id}/account_member_audit/{audit_id}            # DM-PRD-07 — account-level member-CRUD audit
accounts/{account_id}/plan_runs/{run_id}                         # Automations component
accounts/{account_id}/plan_runs/{run_id}/artifacts/{artifact_id}

# Shape C retained (per decision carve-out)
notifications/{notification_id}
usage_records/{record_id}

# Org-scoped subcollections (DM-PRD-07)
organizations/{org_id}/members/{user_id}                         # DM-PRD-07 — every org member has a row
organizations/{org_id}/billing_audit/{audit_id}                  # DM-PRD-07 — Billing audit subcollection
organizations/{org_id}/account_member_audit/{audit_id}           # DM-PRD-07 — org-level member-CRUD audit

# User-scoped subcollections (existing — Shape B-compatible, not affected by the Shape A→B migration)
users/{user_id}                                                  # root user doc
users/{user_id}/notification_status/{notification_id}            # firestore_notification_repository.py
users/{user_id}/preferences/notifications                        # firestore_notification_repository.py — single doc
users/{user_id}/chat_categories/{category_id}                    # CH-PRD-03

# Non-account-scoped (unchanged)
organizations/{org_id}                                           # root org doc; no longer holds nested accounts map after DM-PRD-03
agent_configs/{config_id}
industry_keywords, industry-templates, subscription-plans,
strategy_doc_guides, security_audit_logs, revoked_tokens,
revoked_tokens_all, oauth_states, integration_credentials,
optimization_recommendations, health_check
```

After DM-PRD-07 ships, `users/{user_id}.permissions.organizations.*` and `users/{user_id}.permissions.account_permissions.*` field trees are migrated into the new `members` subcollections (org-scoped + account-scoped) and removed from the user doc.

**GCS target state** (unchanged from G1):

```
gs://kene-docs-{env}-{region}/accounts/{account_id}/{filename}
gs://kene-skills-{env}/accounts/{account_id}/{skill_name}/{version}/…         (planned — SK-PRD-01)
gs://kene-task-artifacts-{env}/{account_id}/{plan_id}/{run_id}/{task_id}/…    (planned — A-PRD-3)
```

**Cross-account queries** (scheduler sweeps, audit queries, automation list aggregation) use **collection-group queries** over the relevant subcollection (`project_plans`, `plan_runs`, `strategy_audit`) plus a collection-group index. Per-account iteration is never used in production code paths.

### 2.3 API Contracts

This component publishes no public HTTP API. Its contracts are structural and consumed by every other component:

| Contract | Consumed by | Source of truth |
|----------|-------------|-----------------|
| Shape B path convention: `accounts/{account_id}/{resource}/…` | Every router/service that writes account-scoped data | Prose convention documented here + in `api/CLAUDE.md`; enforced by code review and by the `MigrateConfig` registry |
| Collection-group indexes (`strategy_audit`, `project_plans`, `plan_runs`, `project_plan_audit`) | Audit queries (`audit_service.py`), Scheduler (`/api/v1/internal/scheduler/launch-due-tasks`), Automations list view, Audit archive exporter (DM-PRD-07) | `deployment/firestore.indexes.json` |
| Migration CLI: `python api/scripts/migrate_to_shape_b.py --resource=<r> [--dry-run \| --confirm-delete]` | All environments (dev / staging / prod) for a single-cutover migration | `api/scripts/_migrate_shape_b/` |
| `recursive_delete(accounts/{account_id})` semantic | Account-deletion endpoint, ops scripts (`delete_intellipure_accounts.py`) | `api/src/kene_api/routers/accounts.py` (DM-PRD-05) |
| `delete_user_data(user_id)` orchestrator + `DELETE /api/v1/users/{user_id}` (super-admin) | Full user-data purge: cross-org/account `members` cleanup + IN-PRD-05 `on_user_removed` hook chain + user-scoped subcollections + user doc | `api/src/kene_api/services/user_deletion_service.py` (DM-PRD-05) |
| `OrgRole` + `AccountRole` enums + `require_role(min_role, scope=Org\|Account)` FastAPI dependency + `resolve_effective_account_role(...)` overlay helper | Every mutating endpoint across Project Tasks / Automations / Calendar Activities / Campaigns / Integrations / Billing / SAR-E / Data Pipeline | `api/src/kene_api/dependencies/rbac.py`, `api/src/kene_api/services/member_service.py` (DM-PRD-07) |
| Member-CRUD API (`/api/v1/organizations/{org_id}/members[/{user_id}]`, `/api/v1/accounts/{account_id}/members[/{user_id}]`) | Frontend admin UI (separate project), super-admin tooling, IN-PRD-05 user-removal hook | `api/src/kene_api/routers/members.py` (DM-PRD-07) |
| Generalized `AuditEntry` document shape + `write_audit(parent_kind, parent_id, audit_subcollection, resource_type, action, ...)` helper + per-component registry | Every mutating endpoint that needs an audit trail — registry currently lists 6 audit subcollections (project_plan / integrations / billing / sar_e / data_pipeline / account_member, scoped per `parent_kind`) | `api/src/kene_api/services/audit_service.py`, `audit_registry.py` (DM-PRD-07) |
| BigQuery audit archive: combined `audit_archive_{env}.audit_entries` (partitioned by `DATE(at)`, clustered on `parent_kind, resource_type`; columns include `parent_kind`, `parent_id`, `audit_subcollection`) | Compliance / investigation queries across every registered audit subcollection; 2-year hot in Firestore → indefinite in BQ | `deployment/terraform/bigquery_audit_archive.tf` (DM-PRD-07) |

### 2.4 Key Abstractions

| Abstraction | Path | Purpose |
|-------------|------|---------|
| `MigrateConfig` | `api/scripts/_migrate_shape_b/resources.py` | Per-resource migration spec (old prefix, new subcollection, has_versions, source_is_single_collection, destination_doc_id, is_field_migration). DM-PRD-01–DM-PRD-04 each append one entry; DM-PRD-07 appends the `members_migration` field-migration entry. |
| `migrate_resource(resource)` | `api/scripts/_migrate_shape_b/core.py` | Idempotent copy from `{resource}_{account_id}/…` → `accounts/{account_id}/{resource}/…` with count verification. |
| `delete_old_collections(resource)` | Same | Deletes source collections only after verification succeeds (gated on `--confirm-delete`). |
| `firestore.recursive_delete(doc_ref)` | `api/src/kene_api/routers/accounts.py` (DM-PRD-05) | Replaces the enumerated collection sweep in account deletion. |
| `collection_group("strategy_audit")` query | `api/src/kene_api/services/audit_service.py` (L189) | Cross-account audit query — live once DM-PRD-01 ships the new path + collection-group index. |

## 3. Component Dependencies

### 3.1 Depends On

| Component | Dependency | Reference |
|-----------|------------|-----------|
| GCP Firestore | Collection-group query support; `firestore.recursive_delete` via the Firestore admin SDK; composite + collection-group index builds. | `deployment/firestore.indexes.json`, `deployment/terraform/firestore_indexes.tf` |
| Existing strategy-document pattern | The Shape B layout models itself on `routers/strategy.py`'s versioning + audit pattern, which is the only end-to-end Shape-B-compatible subsystem today. | `api/src/kene_api/routers/strategy.py` |

### 3.2 Depended On By

| Component | Dependency |
|-----------|------------|
| [Project Tasks](../project-tasks/README.md) | Writes to `accounts/{account_id}/project_plans/…`. PR-PRD-01 (data model & API) and PR-PRD-06 (scheduler collection-group query) depend on the Shape B convention and the `project_plans` collection-group index. PR-PRD-07 (Calendar Activities) adds `accounts/{account_id}/orphan_tasks/…`. PR-PRD-08 (Campaign Management) adds `accounts/{account_id}/campaigns/…`. Both consume DM-PRD-07's `require_role` gate and `write_audit` helper (with `audit_subcollection="project_plan_audit"`). |
| [Skills](../skills/README.md) | Writes to `accounts/{account_id}/skills/…`. SK-PRD-01 depends on the Shape B convention and the `skills` collection-scope indexes. |
| [Automations](../automations/README.md) | Writes to `accounts/{account_id}/plan_runs/…`. A-PRD-01 (data model) and A-PRD-02 (recurring scheduler) depend on the Shape B convention and the `plan_runs` indexes (collection-scope) and `project_plans` (`save_as_automation, is_active, next_run_at`) collection-group index. |
| [Integrations](../integrations/README.md) | Writes encrypted tokens to `accounts/{account_id}/platform_connections/{connection_id}/tokens/*` and audit entries to `accounts/{account_id}/integrations_audit/*` via DM-PRD-07's `write_audit` (registered subcollection). IN-PRD-05 calls into DM-PRD-05's `delete_user_data` orchestrator via the `on_user_removed` hook. |
| [Billing](../billing/README.md) | Writes to `organizations/{org_id}/billing_audit/*` via DM-PRD-07's `write_audit` (the only org-scoped audit consumer in v1). Uses `require_role(OrgRole.ADMIN, scope="org")` on every state-changing endpoint. |
| [SAR-E](../sar-e/README.md) | Every account-scoped SAR-E collection (`sar_e_config`, `effectiveness_kpis`, `funnel_mapping`, `thresholds`, `channel_coverage`, `targets`, `kpi_time_series`, `baselines`, `irf_coefficients`) lives under `accounts/{account_id}/...`. Audits go to `accounts/{account_id}/sar_e_audit/*`. |
| [Data Pipeline](../data-pipeline/README.md) | Account-scoped `data_pipeline_jobs` overlay catalog + `data_pipeline_runs` under `accounts/{account_id}/...`. Audits go to `accounts/{account_id}/data_pipeline_audit/*`. |
| [Chat](../chat/README.md) | Side-table at `accounts/{account_id}/chat_sessions/*` + nested `artifacts/*`. Per-user categories at `users/{user_id}/chat_categories/*` (third user-scoped subcollection after `notification_status` and `preferences`). DM-PRD-05 user-deletion sweep cleans the user-scoped collection. |
| [Knowledge Graph](../knowledge-graph/README.md) | KG-PRD-04 (session-end automation) fires through an `is_system=true` project plan — consumes Shape B transitively via Project Tasks and Automations. |
| Strategy / Analytics / Monitoring / Alerts (existing subsystems) | Every account-scoped read/write in `strategy_agent/`, `monitoring_sync_service.py`, and `alert_manager.py` migrates to Shape B in DM-PRD-01, DM-PRD-02, and DM-PRD-04. |

## 4. Design System References

**N/A** — this is a backend-only, platform-level component. No UI surfaces.

## 5. Project Index

The component's work is split across **8 project PRDs** under [`projects/`](./projects/). Every PRD is self-contained — a team can pick one up and ship it without reading the others. The blocking relationships below determine how many teams can work in parallel at each phase. DM-PRD-07 was added alongside the Figma-frontend backend alignment: role-based access control and a formal audit-log schema are cross-cutting concerns that belong with Data Management rather than with any single consumer component.

### 5.1 Projects

| ID | Title | Status | Effort | Blocked by | Blocks |
|---|---|---|---|---|---|
| [DM-PRD-00](./projects/DM-PRD-00-migration-foundation.md) | Migration Foundation | Ready to start | 2–3 d | — | DM-PRD-01, DM-PRD-02, DM-PRD-03, DM-PRD-04 |
| [DM-PRD-01](./projects/DM-PRD-01-strategy-suite-migration.md) | Strategy Suite Migration | Blocked | 3–4 d | DM-PRD-00 | DM-PRD-05 |
| [DM-PRD-02](./projects/DM-PRD-02-analytics-suite-migration.md) | Analytics Suite Migration | Complete | 2–3 d | DM-PRD-00 | DM-PRD-05 |
| [DM-PRD-03](./projects/DM-PRD-03-shape-d-split.md) | Shape D Split | Blocked | 3–4 d | DM-PRD-00 | DM-PRD-05 |
| [DM-PRD-04](./projects/DM-PRD-04-shape-b-like-collapse.md) | Shape B-like Collapse | Blocked | 1–2 d | DM-PRD-00 | DM-PRD-05 |
| [DM-PRD-05](./projects/DM-PRD-05-deletion-sweep-rewrite.md) | Deletion Sweep Rewrite (Account + User) | Blocked | 2–3 d | DM-PRD-01, DM-PRD-02, DM-PRD-03, DM-PRD-04 | DM-PRD-06, DM-PRD-07 |
| [DM-PRD-06](./projects/DM-PRD-06-verification-and-cutover.md) | Verification & Staging Cutover | Blocked | 1 d | DM-PRD-05 | — |
| [DM-PRD-07](./projects/DM-PRD-07-approval-workflow-and-audit.md) | Roles, Members, Audit Substrate | Blocked | 4–5 d | PR-PRD-01, DM-PRD-05 | PR-PRD-07 |

### 5.2 Dependency graph

```
                              ┌──────────────┐
                              │  DM-PRD-00   │  Foundation
                              │ (tools + idx)│
                              └──────┬───────┘
             ┌────────────────┬──────┴──────┬───────────────┐
             ▼                ▼             ▼               ▼
     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
     │  DM-PRD-01   │ │  DM-PRD-02   │ │  DM-PRD-03   │ │  DM-PRD-04   │
     │   Strategy   │ │  Analytics   │ │   Shape D    │ │  Shape B-~   │
     └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
            │                │                │                │
            └────────────────┴────────┬───────┴────────────────┘
                                      ▼
                              ┌──────────────┐
                              │  DM-PRD-05   │  Deletion sweep rewrite
                              └──────┬───────┘
                                     ▼
                              ┌──────────────┐
                              │  DM-PRD-06   │  Staging cutover
                              └──────────────┘
```

DM-PRD-01 through DM-PRD-04 are fully parallelizable after DM-PRD-00 ships. DM-PRD-07 runs in parallel with DM-PRD-06 once its prerequisites (PR-PRD-01 + DM-PRD-05) are in — they touch disjoint code paths.

**Critical path:** DM-PRD-00 → longest of (DM-PRD-01, DM-PRD-02, DM-PRD-03, DM-PRD-04) → DM-PRD-05 → DM-PRD-06 ≈ **8–11 working days** with 3–4 teams active during the middle phase. DM-PRD-07 adds 4–5 days but can overlap DM-PRD-06, so it does not extend the critical path.

### 5.3 Recommended workflow

1. **Sprint 1:** One team ships DM-PRD-00 (migration CLI + shared indexes + convention documented in `api/CLAUDE.md`). Other teams review the `MigrateConfig` schema and stub their resources.
2. **Sprint 2:** DM-PRD-01, DM-PRD-02, DM-PRD-03, DM-PRD-04 run in parallel across up to four teams. Each runs the verification gate (§7.3) independently.
3. **Sprint 3:** DM-PRD-05 consumes the verified state of DM-PRD-01–DM-PRD-04 and rewrites the deletion sweep. DM-PRD-06 closes out with the staging cutover and the final DESIGN-REVIEW-LOG entry. DM-PRD-07 runs in parallel with DM-PRD-06 once PR-PRD-01 has merged (the role-gate / audit-log helpers it publishes are what unblock PR-PRD-07 and PR-PRD-08 in the Project Tasks component).

### 5.4 Parallel feature work (not part of this project set)

Skills, Project Tasks, Automations, and Knowledge Graph feature PRDs already live under:

- [`../skills/projects/`](../skills/projects/) (SK-PRD-00 through SK-PRD-04)
- [`../project-tasks/projects/`](../project-tasks/projects/) (PR-PRD-01 through PR-PRD-08)
- [`../automations/projects/`](../automations/projects/) (01 through 07)
- [`../knowledge-graph/projects/`](../knowledge-graph/projects/) (KG-PRD-01 through KG-PRD-05)

Those teams can start implementation **as soon as DM-PRD-00 ships** (indexes in place, convention documented) — they write directly to Shape B paths and have no dependency on DM-PRD-01–DM-PRD-05. They may choose to wait for DM-PRD-05 if they want a clean end-to-end account-deletion contract, but it's not strictly required.

### 5.5 How to use these PRDs

1. Team picks up a project whose `Blocked by` column is empty (or whose blockers are complete).
2. Read the PRD top to bottom. Every PRD is self-contained — you do not need to read `./multi-tenant-migration-plan.md` unless a §Reference line in the PRD points to a specific section of it.
3. Follow the Implementation outline. Acceptance criteria define "done."
4. When complete, update this README's [§5.1 Projects](#51-projects) status column and notify any team blocked on you.

## 6. Global Document References

| Document | Relevant Sections | Why |
|----------|-------------------|-----|
| [`./multi-tenant-migration-plan.md`](./multi-tenant-migration-plan.md) | §3 Scope tables, §4 Phases, §5 Terraform / indexes JSON, §6 Migration script design, §8–§11 Risks / Out of scope / Follow-ups / Execution checklist | Detailed per-resource migration table and call-site inventory. Every DM-PRD's §Reference line cites one or more sections. Read on demand from a PRD, not up-front. |
| [`../../multi-tenant-data-model-research-findings.md`](../../multi-tenant-data-model-research-findings.md) | Q1 Inventory, Q2 Cross-account query list, Final recommendation | Research output that drove the Shape B + G1 decision. Read only if re-evaluating the decision; not needed for implementation. |
| [`../../multi-tenant-data-model-research-brief.md`](../../multi-tenant-data-model-research-brief.md) | Entire file | Historical — framed the decision research. Read only for background. |
| [`../../DESIGN-REVIEW-LOG.md`](../../DESIGN-REVIEW-LOG.md) | 2026-04-20 entry (Review 15 — Multi-Tenant Shape B) | Change log; records the PRD updates that realigned Skills / Plans / Automations / KG-04 to Shape B. |
| [`../../DESIGN-REVIEW-LOG.md`](../../DESIGN-REVIEW-LOG.md) | Review 15 (Multi-Tenant Data Model Shape) | Rationale, alternatives considered, decision criteria. (Historical Notion record retained as archive: [Multi-Tenant Data Model Shape](https://www.notion.so/34830fd653028177bc0dc2a1637c7f60).) |

## 7. Conventions and Constraints

### 7.1 Shape B path convention (enforced across all components)

- **Target layout:** `accounts/{account_id}/{resource}/…`
- **Shape C carve-out:** `notifications` and `usage_records` remain Shape C — do not migrate, do not touch.
- **Account-isolation enforcement** stays in Python (`has_account_access` + `is_super_admin`), never in Firestore security rules.
- **No production users** — single-cutover migration per environment; no dual-write, no backwards-compatibility shim, no feature flags.
- **Cross-account queries** use collection-group queries plus a matching collection-group index. Per-account iteration is never used in production code paths.
- **Migration script (DM-PRD-00):** every data-migrating project (DM-PRD-01–DM-PRD-04) registers its resources in `api/scripts/_migrate_shape_b/resources.py` and invokes the shared CLI. No hand-rolled migration scripts.

### 7.2 GCS (G1) retained

GCS paths are unchanged. Continue `gs://kene-{bucket}-{env}/accounts/{account_id}/…` in `api/src/kene_api/services/storage_service.py`. New GCS prefixes for Skills (SK-PRD-01) and Task Artifacts (A-PRD-03) land directly on this pattern.

### 7.3 Verification gate between projects

Before marking DM-PRD-01 / DM-PRD-02 / DM-PRD-03 / DM-PRD-04 complete, the team owning that project must run (in dev):

```bash
python api/scripts/migrate_to_shape_b.py --resource=<their_resource> --dry-run
# … verify counts match …
python api/scripts/migrate_to_shape_b.py --resource=<their_resource> --confirm-delete
# … confirm source collections are gone …
pytest api/tests/
make lint
```

DM-PRD-05 cannot start until **all** data-migration projects (DM-PRD-01 + DM-PRD-02 + DM-PRD-03 + DM-PRD-04) complete the verification gate. DM-PRD-06 cannot start until DM-PRD-05 completes.

### 7.4 Out of scope

- **Neo4j schema** — account isolation via node properties is unchanged.
- **Existing user-scoped subcollections** — `users/{user_id}/notification_status` and `users/{user_id}/preferences` (verified in `firestore_notification_repository.py`) stay as-is structurally; DM-PRD-05's user-deletion sweep registers them in `USER_SUBCOLLECTIONS` so they're purged on user delete. CH-PRD-03's `users/{user_id}/chat_categories` is the third user-scoped subcollection and joins the same registry.
- **Shape C collections** — `notifications` and `usage_records` remain Shape C per the decision carve-out.
- **Firestore security rules** — enforcement stays in Python; no rules work.
- **Research docs** — `docs/design/multi-tenant-data-model-research-{brief,findings}.md` stay in `docs/design/` next to other architecture research. Only the migration plan lives inside this component.
- **Role-assignment admin UI** — DM-PRD-07 ships the bare member-CRUD API. The frontend admin page is a separate UI project (not blocked by this component).
- **Firebase user record deletion** — DM-PRD-05's user-deletion sweep purges KEN-E-side data. The Firebase Auth user record is deleted out-of-band by an operator after the API call completes.
- **Dev environment IAM (intentional out-of-band)** — `deployment/terraform/locals.tf::deploy_project_ids` only enumerates `prod` and `staging`. Dev (`ken-e-dev`) is treated as a sandbox: IAM grants on the dev Agent Engine SA (including `roles/datastore.user` for `analytics_db` access) are added by engineers as needed and are not reconciled by terraform. Dev still gets terraform-managed Firestore indexes via the separate `firestore_index_project_ids` variable — indexes are required for query correctness, IAM is not. If dev is ever promoted to a production-like environment, adding it to `deploy_project_ids` is a scoped project (it pulls in CICD SA roles, Vertex SA roles, log sinks, and monitoring for dev), not a one-line cleanup.

### 7.5 Downstream PRD alignment

All downstream PRDs (Skills / Project Tasks / Automations / Knowledge Graph KG-04) were realigned to Shape B on 2026-04-20 — path references, Firestore layout callouts, index sections, and account-deletion sections. See [DESIGN-REVIEW-LOG §Review 15](../../DESIGN-REVIEW-LOG.md) for the full list of edits. New PRDs in those components must start on Shape B directly; no Shape A intermediate step is permitted.

### 7.6 `is_system` system-plan convention

`is_system=True` on a `ProjectPlan` marks it as a **platform-owned template** — seeded by a migration script or a system service, not user-authored. The flag is *defined* in Project Tasks [PR-PRD-01 §4](../project-tasks/projects/PR-PRD-01-data-model-and-api.md#4-data-contract); its *enforcement* is cross-cutting, which is why the canonical table lives here rather than inside any one consumer component.

| Consumer | Enforcement |
|---|---|
| Project Tasks PR-PRD-01 (`/api/v1/plans/*`) | Write protection on the base endpoints. User-auth `POST` with `is_system=true` silently defaults the field to `false`; `PUT` on a system plan → `403`; `DELETE` on a system plan → `403`; `PATCH .../tasks/{task_id}` → `403` unless the payload touches only an explicit status-only allowlist (`status`, `completion_notes`, `revision_comment`, `revision_iteration`) — the HITL carve-out that lets reviewers act on system-run tasks without editing the template. |
| Automations A-PRD-01 (`/api/v1/automations/*`) | `PATCH .../recurrence` on a system plan → `403`. System templates have no user-editable schedule. |
| Automations A-PRD-05 (Automations list page) | Default list query filters `is_system=true` out. An explicit `?is_system=true` is accepted for debugging but is not surfaced in the UI. Frontend also defaults the filter client-side (defense in depth). |
| Automations A-PRD-06 (Automation Details page) | Read-only when `is_system=true` — no DAG edits, no Run Now / Test Run, no Delete. HITL Mark Complete / Revision Requested **still work** on human tasks within system runs — that's the primary interaction for KG-PRD-04 reviewer approval. |
| Knowledge Graph KG-PRD-04 | Seeds the `kg-session-end-review` plan with `is_system=true` at account creation; system-triggered `PlanRun`s route through the Automations runtime. |

**Template vs. run distinction:** these rules govern the **template** (`ProjectPlan`). The **`PlanRun`** produced by a system template is a normal run document — reviewers interact with the run (Mark Complete, Request Revision on its human tasks) without being blocked by the template's read-only status.

When a new consumer PRD touches `is_system`, update this table rather than duplicating the rule inside that component's README.

### 7.7 Cross-account query pattern

Every production cross-account read — scheduler sweeps, audit aggregation, automation list collation, member lookup — uses a **collection-group query** over the relevant subcollection, combined with a matching collection-group composite index. **Per-account iteration is never used in production code paths.** Single-account list endpoints use collection-scope indexes instead.

| Index | Scope | Owner | Consumer |
|---|---|---|---|
| `strategy_audit` composite | collection-group | DM-PRD-00, wired in DM-PRD-01 | `audit_service.collection_group("strategy_audit")` |
| `project_plans` (`status ASC, launched_at ASC, due_date ASC`) | collection-group | DM-PRD-00 | PR-PRD-06 time-based scheduler (`/launch-due-tasks`) |
| `project_plans` (`save_as_automation ASC, is_active ASC, next_run_at ASC`) | collection-group | DM-PRD-00 | A-PRD-02 recurring scheduler (`/launch-due-automations`) |
| `project_plans` (list-page filter indexes, 4×) | collection-scope | A-PRD-01 | Automations list page (`/api/v1/automations/{account_id}`) |
| `plan_runs` (2×) | collection-scope | DM-PRD-00 | Automations runs list |
| `project_plan_audit` (`at ASC`) | collection-group | DM-PRD-00 (wired in DM-PRD-07) | Nightly BigQuery export (DM-PRD-07) |
| `members` (`user_id ASC, parent_kind ASC`) | collection-group | DM-PRD-00 (wired in DM-PRD-07 + DM-PRD-05) | DM-PRD-05 user-deletion sweep + DM-PRD-07 effective-role resolution |
| `integrations_audit`, `billing_audit`, `sar_e_audit`, `data_pipeline_audit`, `account_member_audit` (each `at ASC`) | collection-group | DM-PRD-07 | Nightly BigQuery export (one query per registered audit subcollection) |
| `orphan_tasks` (3× composite) | collection-scope | PR-PRD-07 | Unscheduled Tasks panel |
| `campaigns` (`is_active ASC, objective ASC, updated_at DESC`) | collection-scope | PR-PRD-08 | Campaign picker in the activity form |

When a new query crosses account boundaries, add a collection-group index here rather than iterating accounts in the application layer. When a consumer needs a single-account list filter, add the index to the owning component's Terraform file and register it in this table. When a new audit subcollection is registered with the audit substrate (DM-PRD-07 §4.8), add its collection-group `at` index here too.

---

<!-- PRD MAINTENANCE NOTES

Updating this PRD:
- When a project status changes: update §5.1 Projects table.
- When a new resource is added to the migration: append it to §2.2 Data Flow and register it in `api/scripts/_migrate_shape_b/resources.py`.
- When a new collection-group index is added: update §2.3 API Contracts and `deployment/firestore.indexes.json`.
- When the migration completes: flip §1 Overview status and check all boxes in `./multi-tenant-migration-plan.md` §11.
- When a downstream component adds a new Shape B resource: update §3.2 Depended On By.
- When the data-model decision is revised: add a new Review entry to `docs/design/DESIGN-REVIEW-LOG.md` and link it in §6 Global Document References.

Relationship to `./multi-tenant-migration-plan.md`:
- The migration plan holds the detailed per-resource call-site tables, Terraform index JSON, migration script design sketch, and execution checklist — content too granular for this README.
- Individual DM-PRDs reference specific sections of the plan by number (e.g., "§3.3 Shape D split"). Keep that numbering stable; do not renumber the plan.
- This README is the component-level entry point for a new dev team; the plan is read section-by-section when a PRD's §Reference line points to it.

This PRD is read by the Dev Team agent during implementation planning (CLAUDE.md §Context Loading Sequence, Step 1). Keep it concise — every sentence should help the agent write better code or avoid mistakes.

-->
