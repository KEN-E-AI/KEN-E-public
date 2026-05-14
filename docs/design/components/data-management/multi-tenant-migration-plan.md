# Multi-Tenant Data Model — Migration Plan

**Decision:** [Review 15 in DESIGN-REVIEW-LOG](../../DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1) — Multi-Tenant Data Model Shape: Firestore Subcollections (Shape B) + GCS Prefix (G1)
**Research findings:** [`../../multi-tenant-data-model-research-findings.md`](../../multi-tenant-data-model-research-findings.md)
**Research brief:** [`../../multi-tenant-data-model-research-brief.md`](../../multi-tenant-data-model-research-brief.md)
**Created:** 2026-04-20
**Status:** Draft — ready for implementation kickoff

---

## 1. Objective

Realign all account-scoped Firestore data under the canonical Shape B pattern (`accounts/{account_id}/{resource}/…`), split the `organizations/{org_id}` nested-accounts map out to per-account docs, and keep GCS on the existing G1 pattern. Preserve Shape C only for `notifications` and `usage_records`.

KEN-E has no production users, so this is a single-cutover migration per environment. No dual-write, no backwards-compatibility phase, no downtime window tracking. Repeatability across dev → staging → prod matters because the migration will run in each environment.

## 2. Target state

### Firestore

```
accounts/{account_id}                                            # account doc (currently doesn't exist as a first-class doc
                                                                 # in most envs — some fields migrate here from organizations/{org_id})
accounts/{account_id}/strategy_docs/{doc_type}                   # from strategy_docs_{account_id}/
accounts/{account_id}/strategy_docs/{doc_type}/versions/{n}
accounts/{account_id}/strategy_audit/{audit_id}                  # from strategy_audit_{account_id}/
accounts/{account_id}/strategy_processing_state/{state_id}       # from strategy_processing_state_{account_id}/
accounts/{account_id}/agent_analytics/{metric_id}                # from agent_analytics_{account_id}/
accounts/{account_id}/cost_aggregations/{agg_id}                 # from cost_aggregations_{account_id}/
accounts/{account_id}/performance_profiles/{profile_id}          # from performance_profiles_{account_id}/ (aka performance_profiles_acc_{account_id})
accounts/{account_id}/monitoring_topics/{topic_id}               # from monitoring_topics/{account_id} (Shape B-like → Shape B)
accounts/{account_id}/alert_configurations/{config_id}           # from alert_configurations/{account_id}
# Planned resources (will land directly under Shape B, no Shape A stop):
accounts/{account_id}/skills/{skill_id}
accounts/{account_id}/skills/{skill_id}/versions/{n}
accounts/{account_id}/project_plans/{plan_id}
accounts/{account_id}/project_plans/{plan_id}/versions/{n}
accounts/{account_id}/project_plan_audit/{audit_id}
accounts/{account_id}/plan_runs/{run_id}
accounts/{account_id}/plan_runs/{run_id}/artifacts/{artifact_id}

# Shape C (unchanged)
notifications/{notification_id}
usage_records/{record_id}

# Unchanged (non-account-scoped)
organizations/{org_id}                                           # still the root doc for orgs,
                                                                 # but no longer contains nested account config
users/{user_id}                                                  # with subcollections (notification_status, preferences)
agent_configs/{config_id}
industry_keywords, industry-templates, subscription-plans,
strategy_doc_guides, security_audit_logs, revoked_tokens,
revoked_tokens_all, oauth_states, integration_credentials,
optimization_recommendations, health_check
```

### GCS

Unchanged. Continue the existing G1 pattern in `api/src/kene_api/services/storage_service.py`:
```
gs://kene-docs-{env}-{region}/accounts/{account_id}/{filename}
gs://kene-skills-{env}/accounts/{account_id}/{skill_name}/{version}/…     (planned)
gs://kene-task-artifacts-{env}/{account_id}/{plan_id}/{run_id}/{task_id}/…  (planned)
```

## 3. Scope

### 3.1 Collections that move (Shape A → Shape B)

| Old path | New path | Bounded? | Primary call sites |
|---|---|---|---|
| `strategy_docs_{account_id}/{doc_type}` | `accounts/{account_id}/strategy_docs/{doc_type}` | Bounded | `api/src/kene_api/routers/strategy.py` (L86, 149, 154, 219, 233, 336); `api/src/kene_api/services/account_service.py:378`; `api/src/kene_api/tasks/strategy_tasks.py:814`; `app/adk/agents/strategy_agent/firestore.py` (L280, 335, 363, 406, 467, 474); `app/adk/agents/strategy_agent/ARTIFACT_CONVENTIONS.md:34` |
| `strategy_docs_{account_id}/{doc_type}/versions/{n}` | `accounts/{account_id}/strategy_docs/{doc_type}/versions/{n}` | Unbounded | `routers/strategy.py:149, 233` |
| `strategy_audit_{account_id}/{audit_id}` | `accounts/{account_id}/strategy_audit/{audit_id}` | Unbounded | `services/audit_service.py:75, 111, 154, 189 (broken query), 226`; `routers/strategy.py:445` |
| `strategy_processing_state_{account_id}` | `accounts/{account_id}/strategy_processing_state/{state_id}` | Bounded | `app/adk/agents/strategy_agent/firestore.py:622, 642` |
| `agent_analytics_{account_id}` | `accounts/{account_id}/agent_analytics/{metric_id}` | Unbounded | `app/adk/agents/strategy_agent/analytics_service.py:143, 211, 239, 383`; `async_analytics_queue.py:170`; `optimization_analyzer.py:200` |
| `cost_aggregations_{account_id}` | `accounts/{account_id}/cost_aggregations/{agg_id}` | Unbounded | `analytics_service.py:281, 342` |
| `performance_profiles_{account_id}` (inconsistent `_acc_` variant) | `accounts/{account_id}/performance_profiles/{profile_id}` | Unbounded | `app/adk/agents/strategy_agent/performance_profiler.py:240, 320`; `RUNTIME_WARNINGS_ERRORS.md:230` |

### 3.2 Shape B-like → Shape B (optional; bundled for consistency)

| Old path | New path | Call sites |
|---|---|---|
| `monitoring_topics/{account_id}` (doc) | `accounts/{account_id}/monitoring_topics/{topic_id}` | `services/monitoring_sync_service.py`; `graph_sync_service.py:2298, 2314, 2883, 2901`; `routers/monitoring_topics.py` |
| `alert_configurations/{account_id}` (doc) | `accounts/{account_id}/alert_configurations/{config_id}` | `app/adk/agents/strategy_agent/alert_manager.py:147, 202, 486, 641` |

> **Note:** These two are already de-facto one-doc-per-account patterns. The migration is cosmetic but collapses the data-shape count in the codebase from 4 to 2 (Shape B + Shape C). Can be deferred if the migration scope pressure is high; both patterns are functionally equivalent.

### 3.3 Shape D split (organizations/{org_id} nested accounts-map → accounts/{account_id} docs)

The `organizations/{org_id}` doc currently holds nested `accounts.{account_id}.account_settings.overview_kpis.*` and `accounts.{account_id}.funnels.*` maps for every account in the org. This is the 1 MiB-ceiling sleeper risk at 10k+ accounts.

| Old path | New path | Call sites |
|---|---|---|
| `organizations/{org_id}` field `accounts.{account_id}.account_settings.overview_kpis.{kpi}` | `accounts/{account_id}` field `account_settings.overview_kpis.{kpi}` | `firestore.py:441, 491, 619, 671` |
| `organizations/{org_id}` field `accounts.{account_id}.funnels.organization.{step}` | `accounts/{account_id}` field `funnels.organization.{step}` (small) OR `accounts/{account_id}/funnels/organization/{step}` (subcollection if unbounded) | `firestore.py:746, 786, 895, 934, 991` |
| `organizations/{org_id}` field `accounts.{account_id}.funnels.big_bets.{big_bet}.{step}` | `accounts/{account_id}` field `funnels.big_bets.{big_bet}.{step}` OR `accounts/{account_id}/funnels/big_bets/{big_bet}/{step}` | `firestore.py:749, 1082, 1141, 1215` |
| `…/{step}.channels.{channel_name}` | Same nesting under the new parent (fields or subcollections depending on observed size) | `firestore.py:891, 893, 1078, 1080, 1135, 1137, 1211, 1213` |
| `…/{step}.channels.{channel_name}.tactics.{tactic_name}` | Same | `firestore.py:1407, 1409, 1467, 1469` |

**Implementation decision for funnel/KPI tree:** profile a realistic account's current doc size during Phase 2. If p99 stays well under 500 KiB, keep the tree as a field on `accounts/{account_id}`. If it approaches 500 KiB, split `funnels` into a `funnels/` subcollection. Either way, the multi-account-in-one-doc pattern is removed.

### Funnel storage style decision

**Chosen style: Style A — map field on `accounts/{account_id}`** (the simpler option).

**Rubric applied:** `p99 per-account funnel-tree byte footprint < 500 KiB → Style A; otherwise Style B` (per DM-PRD-03 §5 Phase 2.1).

**Measured numbers from DM-35 dev run** (profiler script `api/scripts/profile_org_doc_sizes.py`, commit `474ccd19`, run against the dev Firestore project):

| Metric | Value |
|---|---|
| `total_orgs` | 1 (dev fixture org) |
| `total_accounts` | 0 |
| `total_size_p50` | trivially small (no funnel data) |
| `total_size_p95` | trivially small |
| `total_size_p99` | trivially small |
| `per_account_size_p50` | 0 |
| `per_account_size_p95` | 0 |
| `per_account_size_p99` | 0 |
| `orgs_over_500_kib` | 0 |
| `orgs_over_750_kib` | 0 |
| `accounts_over_500_kib` | 0 |
| `accounts_over_750_kib` | 0 |
| `byte_size_methodology` | `len(json.dumps(doc, default=str).encode("utf-8"))` (overestimates by ~10–20%) |

**Rationale:** The p99 per-account value (0 bytes) satisfies the `< 500 KiB` threshold vacuously — the dev environment has no populated Shape D account-funnel-trees. Style A is the PRD-stated simpler default and aligns with how the existing `firestore.py` methods at L441–L1469 already model the data (nested map paths on the org doc), minimising the DM-42 refactor surface.

**Thin-signal caveat:** the measurement is structurally thin (vacuously satisfied rather than positively confirmed). Style B remains reachable as a follow-up migration if post-launch production measurement reveals accounts approaching the 500 KiB band. The escalation path: re-run `profile_org_doc_sizes.py` against staging/prod; if any account's `per_account_size_p99 >= 400 KiB`, open a follow-up issue to evaluate Style B before the 1 MiB doc-ceiling risk materialises.

**Decision recorded in:** DM-38 resolution comment (cite for DM-41/DM-42 contracts) and `api/src/kene_api/firestore.py` comment block above `# KPI Operations`.

### 3.4 Code-only changes that fall out of the shape migration

- **`api/src/kene_api/routers/accounts.py:968-997` — account-deletion sweep:** replace the explicit `collection_name = f"strategy_docs_{account_id}"` block with a single `firestore.recursive_delete(db.collection("accounts").document(account_id))` call. Remove the enumerated list of per-account collections entirely.
- **`api/src/kene_api/services/audit_service.py:189` — `collection_group("strategy_audit")`:** this dead query becomes live once audit collections move to `accounts/*/strategy_audit/*`. Keep the query; add the missing collection-group index.
- **`api/scripts/delete_intellipure_accounts.py`:** replace the enumerated collection sweep (L60-75) with `recursive_delete`.
- **`api/check_strategy_docs.py:15`:** update the debug script to the new path.

### 3.5 Call-site inventory (by file, for code-review use)

```
api/
  check_strategy_docs.py                           # debug script — L15
  src/kene_api/firestore.py                        # Shape D field paths — L441-1469 (15 occurrences)
  src/kene_api/routers/
    accounts.py                                    # deletion sweep — L913, 968-997
    strategy.py                                    # Shape A — L86, 149, 154, 219, 233, 336, 445
  src/kene_api/services/
    account_service.py                             # collection_name — L378
    audit_service.py                               # Shape A + broken collection_group — L75, 111, 154, 189, 226
    graph_sync_service.py                          # rollup refs + monitoring_topics — L2298, 2314, 2883, 2901, 3750, 4102-4103, 4598
    monitoring_sync_service.py                     # monitoring_topics doc — full file
    graph_validation_service.py                    # SWOT node_id prefix — L201 (prefix only; no collection)
  src/kene_api/tasks/strategy_tasks.py             # session/collection refs — L227, 803, 814, 831
  scripts/
    delete_intellipure_accounts.py                 # Shape A sweep — L60-75
  tests/                                           # test fixtures match new paths
app/
  adk/agent_standalone_embedded.py                 # L305
  adk/agents/strategy_agent/
    artifact_utils.py                              # session app_name — L297
    business_graph_builder.py                      # node_id prefixes — multiple (prefix-only; no collection)
    competitive_graph_builder.py                   # node_id prefixes — multiple
    marketing_graph_builder.py                     # rollup node_ids — L840, 901
    firestore.py                                   # Shape A — L108, 145, 177, 209, 280-475, 621, 641-642
    analytics_service.py                           # Shape A — L143, 211, 239, 281, 342, 383
    async_analytics_queue.py                       # Shape A — L170
    optimization_analyzer.py                       # Shape A — L200
    performance_profiler.py                        # Shape A — L240, 320
    alert_manager.py                               # Shape B-like — L145-641 (optional)
    orchestrator.py                                # session ids — L1307, 1309, 1635 (session, not collection)
deployment/
  firestore.indexes.json                           # index updates — see §5
  terraform/                                       # add new *.tf for collection-group indexes
```

## 4. Phases

Each phase is self-contained and independently testable. Phases 1–3 are Firestore; Phases 4–5 are docs + verification.

### Phase 0 — Preparation

1. Create `api/scripts/migrate_to_shape_b.py` — the migration script that runs in every environment. Idempotent. Reads old paths, writes new paths, verifies counts match, then deletes old paths only after explicit confirmation flag.
2. Create `api/scripts/seed_shape_b_fixtures.py` — seeds a small realistic account under Shape B for local dev. Used to replace any Shape A fixtures in tests that are deleted.
3. Add Terraform indexes for collection-group queries (see §5).
4. Update `api/CLAUDE.md` Architecture Patterns section to reference the Shape B convention.

### Phase 1 — Shape A collections → Shape B subcollections

Per-collection steps (repeat for each table row in §3.1):

1. Write the new Shape B write path in code (dual-write briefly during dev testing — not in prod; see §6).
2. Migrate existing data via `migrate_to_shape_b.py --resource=<resource>` which:
   - Lists all `{resource}_*` collections.
   - For each, creates `accounts/{account_id}/{resource}/` subcollection docs matching the source.
   - Verifies counts.
3. Swap reads to the new path.
4. Delete the old collections via `migrate_to_shape_b.py --resource=<resource> --confirm-delete`.
5. Update tests. Run `pytest api/tests/` green.

**Order within Phase 1 (by coupling):**
1. `strategy_processing_state` (standalone, bounded, cheapest to migrate first)
2. `strategy_docs` + `strategy_audit` (tight coupling with `routers/strategy.py` and `services/audit_service.py`)
3. `agent_analytics` + `cost_aggregations` + `performance_profiles` (app/adk/agents/strategy_agent/)

### Phase 2 — Shape D split from `organizations/{org_id}`

1. Profile current `organizations/{org_id}` doc sizes — any already approaching 500 KiB are priority.
2. Write migration helper `migrate_org_nested_to_account_docs()` that:
   - For each `organizations/{org_id}` doc, enumerates the `accounts.*` keys.
   - For each, reads the nested `account_settings` + `funnels` and writes to `accounts/{account_id}` doc fields (or subcollections if funnel tree > 500 KiB).
   - After successful write, removes the `accounts.{account_id}` field from the org doc (`firestore.DELETE_FIELD`).
3. Update `api/src/kene_api/firestore.py` (15 methods touching field paths at L441-1469) to read/write from `accounts/{account_id}` doc fields instead of `organizations/{org_id}.accounts.{account_id}`.
4. Run migration in dev. Verify every feature that touches funnels/KPIs still works (KPI dashboard, funnel config API, funnel step CRUD).

### Phase 3 — Shape B-like → Shape B (optional)

Only run if Phase 1+2 land cleanly and time permits. Not blocking for the decision-is-correct validation.

1. Migrate `monitoring_topics/{account_id}` doc → `accounts/{account_id}/monitoring_topics/{topic_id}` subcollection.
2. Migrate `alert_configurations/{account_id}` doc → `accounts/{account_id}/alert_configurations/{config_id}` subcollection.
3. Update call sites listed in §3.2.

### Phase 4 — Code cleanups (land with Phase 1)

1. `api/src/kene_api/routers/accounts.py:968-997` — replace enumerated deletion with `firestore.recursive_delete(db.collection("accounts").document(account_id))`.
2. `api/src/kene_api/services/audit_service.py:189` — keep `collection_group("strategy_audit")`; add matching collection-group index. Write a test that confirms `get_user_activity(user_id)` now returns results.
3. `api/scripts/delete_intellipure_accounts.py` — collapse to `recursive_delete`.
4. `api/check_strategy_docs.py` — update to new path.

### Phase 5 — PRD + doc edits

Tracked separately (executed in the same session as this plan was written):

- `docs/design/components/skills/projects/SK-PRD-01-skills-backend.md` — ~15 path references
- `docs/design/components/skills/projects/SK-PRD-02-agent-integration.md`
- `docs/design/components/skills/projects/SK-PRD-04-agent-builder-controls.md`
- `docs/design/components/project-tasks/projects/PR-PRD-01-data-model-and-api.md`
- `docs/design/components/project-tasks/projects/PR-PRD-06-time-based-scheduler.md` (also remove the per-account-iteration fallback row in the Risks table)
- `docs/design/components/automations/projects/A-PRD-01-data-model-and-api.md`
- `docs/design/components/automations/projects/A-PRD-03-task-artifact-system.md`
- `docs/design/components/knowledge-graph/projects/KG-PRD-04-session-end-automation.md`
- `docs/design/DESIGN-REVIEW-LOG.md` — new review entry

### Phase 6 — Verification

Run after each environment cutover:

- [ ] `make lint` passes.
- [ ] `pytest api/tests/` passes.
- [ ] Account deletion e2e: create a test account, seed data across all migrated resources, delete via `DELETE /api/v1/accounts/{account_id}`, verify Firestore and GCS are empty for that account.
- [ ] Broken audit query fixed: `get_user_activity(user_id)` returns results in a seeded environment where multiple accounts have strategy_audit entries.
- [ ] Scheduler dry run (if PRD-6 has shipped): `collection_group("project_plans").where("due_datetime_utc", "<=", now)` returns expected results across all accounts.
- [ ] Index budget check: `gcloud firestore indexes composite list` totals under 50 (well below 200 cap).
- [ ] `organizations/{org_id}` docs have no `accounts.*` fields left after Phase 2.

## 5. Terraform / index changes

### 5.1 New collection-group indexes in `deployment/firestore.indexes.json`

```jsonc
{
  "indexes": [
    // --- existing notifications / notification_status entries ---
    // (keep as-is)

    // --- new: cross-account strategy audit (fixes audit_service.py:189) ---
    {
      "collectionGroup": "strategy_audit",
      "queryScope": "COLLECTION_GROUP",
      "fields": [
        {"fieldPath": "user_id", "order": "ASCENDING"},
        {"fieldPath": "timestamp", "order": "DESCENDING"}
      ]
    },

    // --- new: project_plans (serves scheduler tick for PRD-6) ---
    {
      "collectionGroup": "project_plans",
      "queryScope": "COLLECTION_GROUP",
      "fields": [
        {"fieldPath": "status", "order": "ASCENDING"},
        {"fieldPath": "launched_at", "order": "ASCENDING"},
        {"fieldPath": "due_date", "order": "ASCENDING"}
      ]
    },

    // --- new: skills listing per account (collection scope is fine; kept local) ---
    {
      "collectionGroup": "skills",
      "queryScope": "COLLECTION",
      "fields": [
        {"fieldPath": "status", "order": "ASCENDING"},
        {"fieldPath": "updated_at", "order": "DESCENDING"}
      ]
    },
    {
      "collectionGroup": "skills",
      "queryScope": "COLLECTION",
      "fields": [
        {"fieldPath": "has_scripts", "order": "ASCENDING"},
        {"fieldPath": "updated_at", "order": "DESCENDING"}
      ]
    },

    // --- new: plan_runs per automation (collection scope) ---
    {
      "collectionGroup": "plan_runs",
      "queryScope": "COLLECTION",
      "fields": [
        {"fieldPath": "template_plan_id", "order": "ASCENDING"},
        {"fieldPath": "started_at", "order": "DESCENDING"}
      ]
    },
    {
      "collectionGroup": "plan_runs",
      "queryScope": "COLLECTION",
      "fields": [
        {"fieldPath": "template_plan_id", "order": "ASCENDING"},
        {"fieldPath": "is_test", "order": "ASCENDING"},
        {"fieldPath": "started_at", "order": "DESCENDING"}
      ]
    }

    // --- deprecated (to delete post-migration): any per-collection index on
    //     strategy_docs_*, strategy_audit_*, project_plans_{account_id}, etc.
    //     Verify with gcloud firestore indexes composite list; drop any that match.
  ]
}
```

Related Terraform files:
- `deployment/terraform/firestore_indexes.tf` (new) — wraps the JSON file
- `deployment/terraform/firestore_indexes_skills.tf` (from SK-PRD-01) — align with new collection names
- `deployment/terraform/firestore_indexes_automations.tf` (from A-PRD-1) — align

### 5.2 GCS — no changes

The existing G1 layout in `storage_service.py` is unchanged. Bucket lifecycle policies (30-day trash for skills, 30-day lifecycle for task artifacts) remain bucket-level as planned.

### 5.3 IAM — no changes

Service-account roles already apply at the collection-group level. No IAM changes required.

## 6. Migration script design

### 6.1 Requirements

- **Idempotent** — re-running produces the same result; partial failures resume without duplication.
- **Reversible (pre-delete)** — Phase 1 step 2 creates the new data alongside the old. The old is deleted only after Phase 1 step 4 (`--confirm-delete` flag).
- **Verifiable** — after each `--resource=<r>` run, prints count mismatches and exits non-zero if any.
- **Environment-agnostic** — reads `GOOGLE_CLOUD_PROJECT_ID` / `FIRESTORE_DATABASE_ID` like the rest of the codebase.

### 6.2 Sketch (for `api/scripts/migrate_to_shape_b.py`)

```python
# Pseudocode — actual implementation lives in Phase 0
RESOURCES = {
    "strategy_docs": MigrateConfig(
        old_prefix="strategy_docs_",
        new_subcollection="strategy_docs",
        has_versions=True,
    ),
    "strategy_audit": MigrateConfig(
        old_prefix="strategy_audit_",
        new_subcollection="strategy_audit",
        has_versions=False,
    ),
    "strategy_processing_state": MigrateConfig(
        old_prefix="strategy_processing_state_",
        new_subcollection="strategy_processing_state",
        has_versions=False,
    ),
    "agent_analytics": MigrateConfig(
        old_prefix="agent_analytics_",
        new_subcollection="agent_analytics",
        has_versions=False,
    ),
    "cost_aggregations": MigrateConfig(
        old_prefix="cost_aggregations_",
        new_subcollection="cost_aggregations",
        has_versions=False,
    ),
    "performance_profiles": MigrateConfig(
        old_prefix="performance_profiles_",  # also handle _acc_ variant
        new_subcollection="performance_profiles",
        has_versions=False,
    ),
}


def migrate_resource(resource: str) -> MigrationReport:
    """Copy every {resource}_* collection to accounts/{account_id}/{resource}/*.

    Idempotent: if the destination doc exists with identical content, skip.
    Verification: return counts for old vs new. Caller decides whether to delete
    the source.
    """
    ...


def delete_old_collections(resource: str) -> int:
    """Delete every {resource}_* collection. Run only after migrate + verify succeeds."""
    ...
```

### 6.3 Environment-specific steps

| Environment | Approach |
|---|---|
| **Local** | Run migration script against Firestore emulator; regenerate fixtures via `seed_shape_b_fixtures.py`. No user data concern. |
| **Dev** | Run migration script; spot-check a few accounts via Firestore console; delete old collections. |
| **Staging** | Same as dev. Validate scheduler, session sweeper, and automation PRDs that consume the new paths. |
| **Prod** | **No current prod data.** When prod is provisioned, the code will already be on Shape B — no migration needed. The script exists for reproducibility if prod launches before all Phase 1 code lands and needs a one-time cutover. |

## 7. PRD impact (summary)

See Phase 5. The impact per PRD:

| PRD | Change type |
|---|---|
| `docs/design/components/skills/projects/SK-PRD-01-skills-backend.md` | 15 path references; account-deletion section simplifies; index section switches to collection-group where relevant |
| `docs/design/components/skills/projects/SK-PRD-02-agent-integration.md` | 2 path references |
| `docs/design/components/skills/projects/SK-PRD-04-agent-builder-controls.md` | 5 path references |
| `docs/design/components/project-tasks/projects/PR-PRD-01-data-model-and-api.md` (Plans) | Firestore layout block + AC #1 |
| `docs/design/components/project-tasks/projects/PR-PRD-06-time-based-scheduler.md` | Collection-group index name; remove the per-account-iteration fallback row in §9 |
| `docs/design/components/automations/projects/A-PRD-01-data-model-and-api.md` | Firestore layout block + index section |
| `docs/design/components/automations/projects/A-PRD-03-task-artifact-system.md` | Artifact path reference |
| `docs/design/components/knowledge-graph/projects/KG-PRD-04-session-end-automation.md` | No structural path changes (uses Automations API), but add a Review-15 callout for reader context |

Each edited PRD gets a short inline callout at the top of its Firestore-layout section:
```
> **Revised 2026-04-20** — Firestore paths updated to Shape B (accounts/{account_id}/{resource}/...). See [Review 15 in DESIGN-REVIEW-LOG](../../DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1) — Multi-Tenant Data Model Shape for rationale.
```

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| `recursive_delete` latency at large account size | Phase 6 verification benchmarks a realistic account; if deletion > 10s, shard into BackgroundTasks. |
| Collection-group indexes build slowly in dev | Acceptable; indexes build in minutes for empty collections. Run `gcloud firestore indexes composite create` early in Phase 0 so they're ready by Phase 1 code landing. |
| Shape D split hits unexpected field-path issues | Phase 2 step 1 profiles first; if the funnel tree is larger than expected, subcollection split is the fallback. |
| Broken `collection_group("strategy_audit")` query triggers unexpected load once live | The query already has `WHERE user_id ==` + `ORDER BY timestamp DESC LIMIT 100`. With the new index, it's bounded and indexed. Log query duration after cutover. |
| Ops scripts that enumerate account-scoped collections break | `api/scripts/delete_intellipure_accounts.py` and `api/check_strategy_docs.py` are explicitly in §3.4; any other ad-hoc scripts are ephemeral and safe to break. |
| Partial migration leaves orphaned Shape A collections | Phase 1 step 4 (`--confirm-delete`) only runs after Phase 1 step 2 verification passes; if it fails mid-run, the script is idempotent and can be re-run to complete. |

## 9. Out of scope

- **Neo4j schema** — account isolation via node properties is unchanged.
- **Users / subcollections** — `users/{user_id}/notification_status`, `users/{user_id}/preferences` stay as is (user-scoped Shape B, not affected).
- **Shape C collections** — `notifications` and `usage_records` remain Shape C per the decision's carve-out.
- **Security rules** — enforcement stays in Python (`has_account_access` + `is_super_admin`). No Firestore rules work.
- **Moving research docs** — `docs/design/multi-tenant-data-model-research-{brief,findings}.md` stay in `docs/design/` (next to other architecture research). Only the migration plan lives in `docs/design/components/data-management/`.

## 10. Follow-ups after migration

These are independent of the migration but become easier once Shape B is in place:

- **Billing aggregation gap** (`DESIGN-REVIEW-LOG.md` §214): `usage_records` lacks `organization_id` / `session_id`. With Shape C retained, the fix is a schema addition + a composite index. Separate PR.
- **Session-age cleanup:** `strategy_processing_state` has no TTL today. Under the new pattern, a Firestore TTL policy on `accounts/*/strategy_processing_state` is a one-line Terraform add.
- **Per-account quota enforcement** (skills, plan_runs): once Shape B is in, `countFromServer` on `accounts/{account_id}/{resource}` gives exact counts for quota checks.

## 11. Execution checklist

- [x] Decision recorded in [Review 15 of DESIGN-REVIEW-LOG](../../DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1)
- [x] Migration plan drafted (this doc)
- [x] PRD edits landed (Phase 5 — see DESIGN-REVIEW-LOG for date)
- [ ] Migration script written (`api/scripts/migrate_to_shape_b.py`)
- [ ] Terraform index file updated (`deployment/firestore.indexes.json` and `.tf` wrapper)
- [ ] Phase 1 executed in dev
- [ ] Phase 2 executed in dev
- [ ] Phase 4 code cleanups landed
- [ ] Phase 6 verification passed in dev
- [ ] Staging cutover
- [ ] Phase 3 (optional — Shape B-like → Shape B)
