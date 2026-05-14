# DM-46 — Dev Migration Run Log: Shape D Split (`migrate_shape_d_split.py`)

**Issue:** DM-46 — Run dev data migration end-to-end + final pytest + make lint sweep (covers AC-7)
**Script:** `api/scripts/migrate_shape_d_split.py`
**Environment:** `ken-e-dev`
**Executor:** `fun-e-agent-vm@fun-e-business.iam.gserviceaccount.com`
**Date:** 2026-05-12
**PRD:** DM-PRD-03 Shape D Split — §5 Phase 4 + Phase 5, §6 AC-7

---

## Pre-flight checks (agent-verified, 2026-05-12)

### Residue scan (Shape D field tree)

```bash
rg -n "accounts\.\{account_id\}\.(funnels|account_settings)" api/ app/ \
  --glob '!**/docs/**' --glob '!**/*.md'
# Exit: 1 (no matches in source files)

rg -n 'accounts\.\{account_id\}\.' api/ app/ \
  --glob '!**/docs/**' --glob '!**/*.md' --glob '!**/tests/**'
# Exit: 1 (no matches in production source files)
```

**Result: zero hits** — all 15 `firestore.py` Shape D methods were refactored to Shape B paths by DM-41/DM-42. The one match found (`api/tests/unit/test_firestore_service_shape_d_paths.py:5`) is in a test comment (`# … Shape D paths … in place`) — expected, not source code.

### Dev inventory (organizations with accounts map)

```python
# Queried organizations collection in ken-e-dev:
# Total orgs:                1
# Orgs with accounts map:    0  (org_test_neo4j has no accounts map field)
# Total accounts in maps:    0
```

**Expected outcome:** zero source accounts to migrate. The single dev org (`org_test_neo4j`) was seeded without the nested `accounts` map. All migration steps below are expected to report zero accounts processed.

---

## Step 1: Write-pass dry-run

```bash
GOOGLE_CLOUD_PROJECT_ID=ken-e-dev python api/scripts/migrate_shape_d_split.py \
  --env=dev --dry-run
```

**Stderr (log lines):**
```
2026-05-12 10:01:21,319 INFO migrate_shape_d_split: env=dev project_id=ken-e-dev database_id=(default) dry_run=True confirm_delete_field=False
2026-05-12 10:01:21,319 INFO DRY RUN — no writes will be made
```

**Stdout (per-account records + JSON SUMMARY):**
```

=== JSON SUMMARY ===

{
  "total_orgs": 0,
  "total_accounts": 0,
  "copied": 0,
  "skipped": 0,
  "empty": 0,
  "errors": 0,
  "orgs_field_deleted": 0,
  "orgs_would_delete": 0,
  "orgs_already_clean": 0,
  "orgs_skipped_unmigrated": 0,
  "orgs_skipped_concurrent_write": 0
}
```

**Exit code:** 0  
**Errors:** 0  
**Notes:** As expected per pre-flight inventory. The runner found no orgs with a non-empty `accounts` map. `total_orgs=0` because the iterator skips orgs with empty or absent `accounts` maps (`_iter_org_accounts` debug-logs them and yields nothing).

---

## Step 2: Write-pass (actual)

**Gate check (Task 2 exit code 0 AND errors == 0):** ✓ PASSED — proceeding to write-pass.

```bash
GOOGLE_CLOUD_PROJECT_ID=ken-e-dev python api/scripts/migrate_shape_d_split.py \
  --env=dev
```

**Stderr:**
```
2026-05-12 10:01:25,124 INFO migrate_shape_d_split: env=dev project_id=ken-e-dev database_id=(default) dry_run=False confirm_delete_field=False
```

**Stdout:**
```

=== JSON SUMMARY ===

{
  "total_orgs": 0,
  "total_accounts": 0,
  "copied": 0,
  "skipped": 0,
  "empty": 0,
  "errors": 0,
  "orgs_field_deleted": 0,
  "orgs_would_delete": 0,
  "orgs_already_clean": 0,
  "orgs_skipped_unmigrated": 0,
  "orgs_skipped_concurrent_write": 0
}
```

**Exit code:** 0  
**Status:** VERIFIED — `errors == 0`, `copied + skipped + empty == total_accounts (0)`  
**Gate decision:** ✓ PROCEED to Wave 3 (spot-check + delete-field pass).

---

## Step 3: Sample-org spot-check (PRD §6.AC-5 evidence)

Queried the org `org_test_neo4j` in `ken-e-dev` post-write-pass:

```
org_id=org_test_neo4j
  has accounts map: False
  CLEAN: no accounts map in source
  fields: ['created_at', 'owner_uid', 'name', 'members']
```

- **`accounts` map present:** No (was never set on this org)
- **`accounts/{account_id}` docs with `organization_id`:** N/A — no accounts to migrate
- **`account_settings` + `funnels` fields populated:** N/A — no source payloads

**Notes:** Zero-source state confirmed. Per the Implementation Plan's Risk section: "Acceptable outcome — AC-7 only requires `pytest` + `make lint` to pass. The run-log will document the zero-source state explicitly (precedent: DM-18 ran against an empty inventory)." PRD §6.AC-5 (every migrated `accounts/{id}` doc has an `organization_id` back-reference) is vacuously satisfied — no accounts exist in the source `accounts` map.

---

## Step 4: Delete-field dry-run

```bash
GOOGLE_CLOUD_PROJECT_ID=ken-e-dev python api/scripts/migrate_shape_d_split.py \
  --env=dev --confirm-delete-field --dry-run
```

**Stderr:**
```
2026-05-12 10:01:36,258 INFO migrate_shape_d_split: env=dev project_id=ken-e-dev database_id=(default) dry_run=True confirm_delete_field=True
2026-05-12 10:01:36,259 INFO DRY RUN — no writes will be made
2026-05-12 10:01:36,817 INFO Running delete-field pass (--confirm-delete-field)
```

**Stdout:**
```
{"org_id":"org_test_neo4j","action":"already_clean","account_count_in_map":0,"missing_account_ids":[],"error":null}

=== JSON SUMMARY ===

{
  "total_orgs": 1,
  "total_accounts": 0,
  "copied": 0,
  "skipped": 0,
  "empty": 0,
  "errors": 0,
  "orgs_field_deleted": 0,
  "orgs_would_delete": 0,
  "orgs_already_clean": 1,
  "orgs_skipped_unmigrated": 0,
  "orgs_skipped_concurrent_write": 0
}
```

**Exit code:** 0  
**`orgs_skipped_unmigrated`:** 0  
**`orgs_skipped_concurrent_write`:** 0  
**Notes:** `org_test_neo4j` reports `already_clean` — the `accounts` field was never set. The delete-pass correctly identifies this as a no-op. The TOCTOU guard counter checks out: `orgs_skipped_unmigrated + orgs_skipped_concurrent_write == 0`.

> **Why `total_orgs=1` here vs. `total_orgs=0` in Steps 1–2:** The write-pass iterator (`_iter_org_accounts`) yields only orgs with a non-empty `accounts` map — since `org_test_neo4j` had no such map, it yielded nothing and `total_orgs=0`. The delete-pass iterator walks **all** org docs unconditionally to determine their clean/migrated state, so `total_orgs=1` reflects the single org in the `organizations` collection. Both behaviors are correct.

---

## Step 5: Delete-field pass (destructive cut-over)

**Gate check (Step 4 `orgs_skipped_unmigrated == 0` AND `orgs_skipped_concurrent_write == 0`):** ✓ PASSED.

```bash
GOOGLE_CLOUD_PROJECT_ID=ken-e-dev python api/scripts/migrate_shape_d_split.py \
  --env=dev --confirm-delete-field
```

**Stderr:**
```
2026-05-12 10:01:40,123 INFO migrate_shape_d_split: env=dev project_id=ken-e-dev database_id=(default) dry_run=False confirm_delete_field=True
2026-05-12 10:01:40,690 INFO Running delete-field pass (--confirm-delete-field)
```

**Stdout:**
```
{"org_id":"org_test_neo4j","action":"already_clean","account_count_in_map":0,"missing_account_ids":[],"error":null}

=== JSON SUMMARY ===

{
  "total_orgs": 1,
  "total_accounts": 0,
  "copied": 0,
  "skipped": 0,
  "empty": 0,
  "errors": 0,
  "orgs_field_deleted": 0,
  "orgs_would_delete": 0,
  "orgs_already_clean": 1,
  "orgs_skipped_unmigrated": 0,
  "orgs_skipped_concurrent_write": 0
}
```

**Exit code:** 0  
**`orgs_skipped_unmigrated + orgs_skipped_concurrent_write`:** 0 ✓ (closes PRD §6.AC-4)  
**Notes:** `org_test_neo4j` is `already_clean` — no `DELETE_FIELD` write issued, which is correct. The cut-over is a logical no-op: the `accounts` field was never populated in `ken-e-dev`.

---

## Step 6: Post-cut-over spot-check

Queried `organizations` collection post-cut-over:

```
org_id=org_test_neo4j
  has 'accounts' field: False
  CLEAN: no accounts field
  fields: ['name', 'owner_uid', 'created_at', 'members']
```

- **`organizations/{org_id}` docs have no `accounts.*` fields:** ✓ confirmed  
- **`accounts/{account_id}` docs preserved:** N/A — no source data  
- **Satisfies PRD §6.AC-4:** ✓ (no `accounts.*` field present on any org doc)

---

## Step 7: Idempotency re-run (closes PRD §6.AC-8)

```bash
GOOGLE_CLOUD_PROJECT_ID=ken-e-dev python api/scripts/migrate_shape_d_split.py \
  --env=dev --confirm-delete-field
```

**Stdout:**
```
{"org_id":"org_test_neo4j","action":"already_clean","account_count_in_map":0,"missing_account_ids":[],"error":null}

=== JSON SUMMARY ===

{
  "total_orgs": 1,
  "total_accounts": 0,
  "copied": 0,
  "skipped": 0,
  "empty": 0,
  "errors": 0,
  "orgs_field_deleted": 0,
  "orgs_would_delete": 0,
  "orgs_already_clean": 1,
  "orgs_skipped_unmigrated": 0,
  "orgs_skipped_concurrent_write": 0
}
```

**Exit code:** 0  
**`orgs_already_clean`:** 1 (total orgs migrated) — idempotency confirmed  
**Writes issued:** 0  
**Result:** No-op confirmed — re-running reports `already_clean` with zero writes.

---

## Step 8: AC-7 tooling gate (`pytest api/tests/` + `make lint`)

### pytest

```bash
pytest api/tests/ --tb=no -q
# 217 failed, 1367 passed, 137 skipped, 214 warnings, 71 errors in 95.80s
# EXIT CODE: 1
```

**Same result on `main` (baseline, no DM-46 changes):**
```bash
# 217 failed, 1367 passed, 137 skipped, 214 warnings, 71 errors in 64.56s
# EXIT CODE: 1
```

**Assessment:** Failures are **pre-existing on `main`** — identical counts on both the `main` baseline and this feature branch. The DM-46 branch introduces zero new test failures (this branch adds only one markdown file). The failures span multiple test files:
- `test_account_permissions.py` (11 errors) — `UserContext` field removed by prior DM work
- `test_graph_sync_service.py` (33 unit failures) — pre-existing Neo4j mock issues
- `test_user_context*.py` (25 failures) — pre-existing auth model issues
- Other test files — pre-existing integration test failures requiring live services

**AC-7 verdict:** NOT MET in the strict sense (exit code 1). However, the failures are pre-existing on `main` and unrelated to DM-PRD-03 changes. Per the Implementation Plan: "If pytest fails, capture the failure, do NOT mark AC-7 met, post a comment naming the test + the suspected owner."

**Likely owners:**
- `test_account_permissions.py` — `UserContext.accessible_accounts` removal; suspected owner: DM-42 (firestore.py refactor) or a prior DM-PRD-03 issue
- `test_graph_sync_service.py` — monitoring topics Shape B path changes; suspected owner: DM-22/DM-25 (DM-PRD-04 Shape B-like collapse work)
- `test_user_context*.py` — auth model changes; suspected owner: unrelated upstream work

### make lint

```bash
make lint
# Would fix 2916 errors (229 additional fixes available with --unsafe-fixes).
# make: *** [Makefile:27: lint] Error 1
# EXIT CODE: 2 (make failure)
```

**Same result on `main`:**
```bash
# Would fix 2916 errors (229 additional fixes available with --unsafe-fixes).
# make: *** [Makefile:27: lint] Error 1
```

**Assessment:** Pre-existing ruff formatting violations on `main`. DM-46 introduces no new lint issues.

**AC-7 verdict (lint):** NOT MET. Pre-existing violations — same count on `main`.

**Escalation record:** Pre-existing failures posted as a comment on DM-46 (see Step 6 handoff comment — Linear issue `DM-46`). Suspected owners documented above. PO decision on DM-PRD-05 unblock is pending PO acknowledgment.

---

## Final state

| Step | Result | PRD AC |
|---|---|---|
| Pre-flight residue scan | Zero hits in source files | — |
| Write-pass dry-run | Exit 0, errors=0 | — |
| Write-pass (actual) | Exit 0, errors=0 | — |
| Sample-org spot-check | Clean (vacuous — no source data) | AC-5 ✓ (vacuous — no accounts map existed) |
| Delete-field dry-run | Exit 0, skipped_unmigrated=0 | — |
| Delete-field pass + post-cut-over spot-check | Exit 0, already_clean=1; no `accounts.*` on any org | AC-4 ✓ (vacuous — no accounts map existed) |
| Idempotency re-run | Exit 0, already_clean=1, 0 writes | AC-8 ✓ |
| KPI/funnel endpoint before/after diff | Not exercisable — no seeded account in `ken-e-dev` | AC-6 ✓ (vacuous — no source data; covered by DM-45) |
| `pytest api/tests/` | **Exit 1** — 217 pre-existing failures | AC-7 ✗ (pre-existing) |
| `make lint` | **Exit 2** — 2916 pre-existing violations | AC-7 ✗ (pre-existing) |

**Migration completed:** ✓ — All Shape D source data in `ken-e-dev` is in the target state. The single dev org (`org_test_neo4j`) never had the `accounts` nested map, so the migration is vacuously complete.

**AC-7 status:** Blocked by pre-existing `pytest` and `make lint` failures on `main`. The failures are identical before and after this branch — DM-46 introduced no regressions. Escalated to PO via DM-46 comment.

**DM-PRD-05 unblock status:** PENDING PO decision. AC-7 is NOT MET due to pre-existing failures unrelated to DM-PRD-03. Migration script exits 0 with no orphaned Shape D data in dev; failures belong to other issue owners. Awaiting PO acknowledgment on DM-46 before DM-PRD-05 starts.
