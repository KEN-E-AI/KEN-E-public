# DM-PRD-00 — Migration Foundation

**Status:** Ready to start
**Owner team:** Platform / Infra
**Blocked by:** —
**Parallel with:** —
**Blocks:** DM-PRD-01, DM-PRD-02, DM-PRD-03, DM-PRD-04
**Estimated effort:** 2–3 days

---

## 1. Context

Foundation project for the multi-tenant data model migration. Produces the shared tooling and infrastructure that DM-PRD-01–DM-PRD-04 depend on:

1. A reusable, config-driven migration script (`migrate_to_shape_b.py`)
2. Firestore indexes for the new Shape B layout
3. Documentation updates so every future feature writes directly to Shape B

**No data is migrated in this project.** DM-PRD-01–DM-PRD-04 each register their resources with the script and run it to migrate their respective collections.

See [`../multi-tenant-migration-plan.md`](../multi-tenant-migration-plan.md) §4 Phase 0 and §5 for the plan excerpt that drives this PRD.

## 2. Scope

### In scope
- Create `api/scripts/migrate_to_shape_b.py` — config-driven copy/verify/delete CLI
- Create `api/scripts/_migrate_shape_b/` supporting module (MigrateConfig, verification helpers, RESOURCES registry)
- Create `api/scripts/seed_shape_b_fixtures.py` — seeds a realistic test account under Shape B for local dev
- Add new Firestore indexes to `deployment/firestore.indexes.json`
- Create/update `deployment/terraform/firestore_indexes.tf` Terraform wrapper
- Update `api/CLAUDE.md` and `app/CLAUDE.md` (if present) with a new "Shape B Multi-Tenant Data Model Convention" section
- Unit tests for the migration script (`api/tests/unit/test_migrate_to_shape_b.py`)
- Integration test against Firestore emulator (`api/tests/integration/test_migration_script_against_emulator.py`)

### Out of scope
- Data migration for any specific resource — owned by DM-PRD-01, DM-PRD-02, DM-PRD-03, DM-PRD-04
- Deletion of legacy Shape A indexes — owned by each downstream project as part of its confirm-delete step
- Account-deletion flow rewrite — owned by DM-PRD-05
- Any backwards-compatibility shim — no production users, not needed

## 3. Dependencies

- Firestore emulator for integration testing (already used elsewhere in the repo)
- Existing `deployment/firestore.indexes.json` (currently has `notifications` / `notification_status` indexes)
- Existing Terraform conventions in `deployment/terraform/`
- Existing seed-script conventions (e.g., `api/scripts/init_subscription_plans.py`)

## 4. Data contract

### Migration script CLI

```bash
# List configured resources
python api/scripts/migrate_to_shape_b.py --list

# Dry-run (prints plan, writes nothing)
python api/scripts/migrate_to_shape_b.py --resource=<name> --dry-run

# Copy + verify (non-destructive; source untouched)
python api/scripts/migrate_to_shape_b.py --resource=<name>

# Copy + verify + delete source collections
python api/scripts/migrate_to_shape_b.py --resource=<name> --confirm-delete

# Run all configured resources
python api/scripts/migrate_to_shape_b.py --all
```

Exit codes: `0` success, `1` verification failed, `2` usage error, `3` runtime error.

### Resource config schema

```python
# api/scripts/_migrate_shape_b/config.py
from dataclasses import dataclass
from collections.abc import Callable

@dataclass(frozen=True)
class MigrateConfig:
    old_prefix: str                                       # e.g., "strategy_docs_"
    new_subcollection: str                                # e.g., "strategy_docs"
    has_versions: bool = False                            # copies /versions/{n} subcollection too
    account_id_extractor: Callable[[str], str] | None = None
    # Default extractor strips `old_prefix` from collection name to get account_id.
    # Custom extractor needed for e.g. `performance_profiles_acc_{account_id}`.
```

The `RESOURCES` registry starts empty. DM-PRD-01–DM-PRD-04 populate it via pull requests.

```python
# api/scripts/_migrate_shape_b/resources.py
RESOURCES: dict[str, MigrateConfig] = {
    # Populated by DM-PRD-01–DM-PRD-04 — empty on DM-PRD-00 merge.
}
```

### Script output format

Per resource, the script prints:

```
Resource: strategy_docs
  Source collections found:   42
  Source doc count:            1,284
  Destination path:            accounts/{id}/strategy_docs
  Destination doc count:       1,284
  Status:                      VERIFIED
  Next step:                   re-run with --confirm-delete
```

### Idempotency contract
- Re-running with the same args is a no-op after a successful run (duplicate destination writes detected via doc-id check, logged and skipped).
- `--confirm-delete` only deletes source collections if verification passes in the current invocation.
- Partial failure mid-run → re-run resumes from where it left off (skip-already-migrated is the default).

## 5. Implementation outline

| Action | File |
|---|---|
| Create | `api/scripts/migrate_to_shape_b.py` — CLI entry point |
| Create | `api/scripts/_migrate_shape_b/__init__.py` |
| Create | `api/scripts/_migrate_shape_b/config.py` — `MigrateConfig` dataclass |
| Create | `api/scripts/_migrate_shape_b/resources.py` — empty `RESOURCES` dict |
| Create | `api/scripts/_migrate_shape_b/runner.py` — copy/verify/delete core |
| Create | `api/scripts/seed_shape_b_fixtures.py` |
| Modify | `deployment/firestore.indexes.json` — add 6 new index entries (see §5.1) |
| Create or modify | `deployment/terraform/firestore_indexes.tf` — Terraform wrapper that references the JSON file |
| Modify | `api/CLAUDE.md` — append "Shape B Multi-Tenant Data Model Convention" section |
| Modify | `app/CLAUDE.md` (if present) — same section |
| Create | `api/tests/unit/test_migrate_to_shape_b.py` |
| Create | `api/tests/integration/test_migration_script_against_emulator.py` |

### 5.1 New indexes

Append to `deployment/firestore.indexes.json` (full JSON shown in `../multi-tenant-migration-plan.md` §5.1; reproduced here for handoff convenience):

```jsonc
{
  "indexes": [
    // ... existing notifications / notification_status entries — do not touch ...

    // Strategy audit cross-account (fixes audit_service.py:189 once DM-PRD-01 migrates)
    {
      "collectionGroup": "strategy_audit",
      "queryScope": "COLLECTION_GROUP",
      "fields": [
        {"fieldPath": "user_id",   "order": "ASCENDING"},
        {"fieldPath": "timestamp", "order": "DESCENDING"}
      ]
    },

    // Scheduler / automations cross-account due-task scan (for PRD-6)
    {
      "collectionGroup": "project_plans",
      "queryScope": "COLLECTION_GROUP",
      "fields": [
        {"fieldPath": "status",      "order": "ASCENDING"},
        {"fieldPath": "launched_at", "order": "ASCENDING"},
        {"fieldPath": "due_date",    "order": "ASCENDING"}
      ]
    },

    // Skills list per account
    {
      "collectionGroup": "skills",
      "queryScope":      "COLLECTION",
      "fields": [
        {"fieldPath": "status",     "order": "ASCENDING"},
        {"fieldPath": "updated_at", "order": "DESCENDING"}
      ]
    },
    {
      "collectionGroup": "skills",
      "queryScope":      "COLLECTION",
      "fields": [
        {"fieldPath": "has_scripts", "order": "ASCENDING"},
        {"fieldPath": "updated_at",  "order": "DESCENDING"}
      ]
    },

    // Plan runs per automation
    {
      "collectionGroup": "plan_runs",
      "queryScope":      "COLLECTION",
      "fields": [
        {"fieldPath": "template_plan_id", "order": "ASCENDING"},
        {"fieldPath": "started_at",       "order": "DESCENDING"}
      ]
    },
    {
      "collectionGroup": "plan_runs",
      "queryScope":      "COLLECTION",
      "fields": [
        {"fieldPath": "template_plan_id", "order": "ASCENDING"},
        {"fieldPath": "is_test",          "order": "ASCENDING"},
        {"fieldPath": "started_at",       "order": "DESCENDING"}
      ]
    }
  ]
}
```

### 5.2 Shape B convention (to append to `api/CLAUDE.md`)

```markdown
## Shape B Multi-Tenant Data Model Convention

All account-scoped Firestore data lives under `accounts/{account_id}/{resource}/...`.

Examples:
- Skill: `accounts/acc_abc/skills/sk_123`
- Strategy doc version: `accounts/acc_abc/strategy_docs/swot/versions/3`
- Audit entry: `accounts/acc_abc/strategy_audit/audit_42`

Account-level deletion sweeps via `firestore.recursive_delete(db.collection("accounts").document(account_id))` — one call, all subcollections gone.

Exceptions (Shape C — global collection with `account_id` field):
- `notifications` — users query N accounts at once via `where("account_id","in",[batch])`
- `usage_records` — org-level billing aggregation

See [Review 15 in DESIGN-REVIEW-LOG](../../../DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1) for full rationale.
```

## 6. Acceptance criteria

1. `python api/scripts/migrate_to_shape_b.py --list` prints the (empty) RESOURCES registry and exits 0.
2. `python api/scripts/migrate_to_shape_b.py --resource=unknown` exits with code 2 and a clear "unknown resource" message.
3. Integration test seeds 3 dummy source collections (`example_acc_A`, `example_acc_B`, `example_acc_C`) in the emulator, registers a test-only `example` resource, runs `--resource=example`, and verifies: (a) data copied to `accounts/{A,B,C}/example/…`; (b) source collections untouched; (c) counts match; (d) exit 0.
4. Re-running the same invocation after success is a no-op (log: "already migrated").
5. `--resource=example --confirm-delete` deletes source collections only after verification passes; running `--confirm-delete` without a prior successful copy exits 1.
6. `--dry-run` writes nothing and prints the plan.
7. All 6 new indexes appear in `deployment/firestore.indexes.json` with correct `queryScope`.
8. After Terraform apply in dev, `gcloud firestore indexes composite list --project=ken-e-dev --database='(default)'` shows all 6 new indexes with state `READY` (operator-verified; not gated in CI).
9. `api/CLAUDE.md` has the new "Shape B Multi-Tenant Data Model Convention" section.
10. `make lint` passes. `pytest api/tests/unit/test_migrate_to_shape_b.py api/tests/integration/test_migration_script_against_emulator.py` passes.
11. `api/scripts/seed_shape_b_fixtures.py` seeds a realistic test account at `accounts/test_acc_fixture/...` with at least one doc under `strategy_docs`, `strategy_audit`, and `skills` subcollections. Used by DM-PRD-01–DM-PRD-04 and feature teams.

## 7. Test plan

### Unit tests (`api/tests/unit/test_migrate_to_shape_b.py`)

- `MigrateConfig` rejects empty `old_prefix`, empty `new_subcollection`
- Default `account_id_extractor` strips prefix: `strategy_docs_acc_abc` → `acc_abc`
- Custom extractor for `performance_profiles_acc_{id}` pattern: input `performance_profiles_acc_abc_xyz` → `acc_abc_xyz`
- Verification: counts match → VERIFIED; counts mismatch → FAILED with per-account diff
- CLI arg parsing: `--dry-run`, `--confirm-delete`, `--resource`, `--all`, `--list`
- Unknown resource → exit code 2
- `--confirm-delete` without prior verification → exit code 1

### Integration tests (`api/tests/integration/test_migration_script_against_emulator.py`)

- Seed 3 source collections + run copy + assert destination has same docs
- Re-run is a no-op (doc count unchanged; no error)
- `--confirm-delete` drops source collections (verify via `list_collections()`)
- `has_versions=True` copies `/versions/{n}` subcollection too (seed a doc with 2 versions; verify both land)
- Partial data (one source empty, another with docs) handled correctly

## 8. Risks & open questions

| Risk | Mitigation |
|---|---|
| Script writes to wrong project | Script logs `project_id` + `database_id` at startup; requires `GOOGLE_CLOUD_PROJECT_ID` env var; `--confirm-delete` prompts interactively unless `--yes` is passed |
| Firestore emulator diverges from prod for `list_documents()` on empty collections | Before running in staging, a human spot-checks the dev run with `gcloud firestore` CLI |
| Index builds block deploys | Index creation is async; Terraform apply returns immediately. Operators monitor `gcloud firestore indexes composite list` for READY before downstream projects start |
| Resources discovered later that we missed | The `RESOURCES` registry is open — DM-PRD-05 verification (account deletion) will surface any orphaned collections; those can be added as a follow-up |

### Open questions

- **Q:** Should the script support `--account-id=<id>` to migrate a single account? → **Default: no.** Per-resource is the unit of migration; per-account would complicate idempotency bookkeeping. Revisit if a migration goes wrong in staging and we need surgical recovery.

## 9. Reference

- Parent plan: [`../multi-tenant-migration-plan.md`](../multi-tenant-migration-plan.md) §4 Phase 0, §5, §6
- Decision: [Review 15 in DESIGN-REVIEW-LOG](../../../DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1) — Multi-Tenant Data Model Shape
- Existing index file: `deployment/firestore.indexes.json`
- Seed-script pattern: `api/scripts/init_subscription_plans.py`
- CLAUDE.md rules in scope: PY-1, PY-2, PY-5, PY-7; T-1, T-3, T-4, T-6
