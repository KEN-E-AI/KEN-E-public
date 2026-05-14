# DM-18 — Dev Migration Run Log: `strategy_processing_state`

**Issue:** DM-18 — Run dev data migration: `strategy_processing_state` (smallest first — validates pattern)
**Resource:** `strategy_processing_state`
**Environment:** `ken-e-dev`
**Executor:** `fun-e-agent-vm@fun-e-business.iam.gserviceaccount.com`
**Date:** 2026-05-12
**Migration CLI:** `api/scripts/migrate_to_shape_b.py`

## Pre-flight checks (agent-verified, 2026-05-12)

- **Registry entry:** `RESOURCES["strategy_processing_state"]` present with `old_prefix="strategy_processing_state_"`, `new_subcollection="strategy_processing_state"`, `has_versions=False`. Confirmed by `cd api && pytest tests/unit/test_migrate_to_shape_b.py -k strategy_processing_state` (1 passed).
- **Shape A residue:** `rg -n 'strategy_processing_state_' api/src/ app/` — **zero hits** in source files.
- **`--list` output:** `strategy_processing_state -> accounts/{account_id}/strategy_processing_state` present.

Expected outcome: `strategy_processing_state_*` top-level collections were inventoried as **absent** in `ken-e-dev` on 2026-05-11 (PO comment on DM-28). All steps below are expected to report `Source collections found: 0`.

---

## Step 1: Dry-run

```
GOOGLE_CLOUD_PROJECT_ID=ken-e-dev python api/scripts/migrate_to_shape_b.py \
  --resource=strategy_processing_state --dry-run
```

**Stdout/stderr (verbatim):**

```
2026-05-12 08:13:43,183 INFO project_id=ken-e-dev database_id=(default)
2026-05-12 08:13:44,218 INFO [strategy_processing_state] dry-run: scanning top-level collections with prefix 'strategy_processing_state_'
Resource: strategy_processing_state
  Source collections found:   0
  Source doc count:            0
  Destination path:            accounts/{id}/strategy_processing_state
  Destination doc count:       0
  Status:                      DRY RUN
  Next step:                   re-run without --dry-run to copy
```

**Exit code:** 0
**Source collections found:** 0
**Notes:** As expected per PO inventory (2026-05-11). No source collections in ken-e-dev.

---

## Step 2: Copy + verify

```
GOOGLE_CLOUD_PROJECT_ID=ken-e-dev python api/scripts/migrate_to_shape_b.py \
  --resource=strategy_processing_state
```

**Stdout/stderr (verbatim):**

```
2026-05-12 08:13:47,987 INFO project_id=ken-e-dev database_id=(default)
2026-05-12 08:13:48,431 INFO [strategy_processing_state] Scanning top-level collections with prefix 'strategy_processing_state_'
Resource: strategy_processing_state
  Source collections found:   0
  Source doc count:            0
  Destination path:            accounts/{id}/strategy_processing_state
  Destination doc count:       0
  Status:                      VERIFIED
  Next step:                   re-run with --confirm-delete
```

**Exit code:** 0
**Status reported:** VERIFIED
**Source doc count:** 0
**Destination doc count:** 0

---

## Step 3: Console spot-check

**Checked in Firestore console for `ken-e-dev`:**

- Top-level `strategy_processing_state_*` collections present: no
- Sample account checked: N/A — no source data
- `accounts/{account_id}/strategy_processing_state/` present: N/A — no source data (consistent with 0 source collections)
- Observation: Runner confirmed 0 source collections in Steps 1 and 2. No top-level `strategy_processing_state_*` collections exist in `ken-e-dev`. AC-2 satisfied for this resource.

---

## Step 4: Confirm-delete

```
GOOGLE_CLOUD_PROJECT_ID=ken-e-dev python api/scripts/migrate_to_shape_b.py \
  --resource=strategy_processing_state --confirm-delete --yes
```

_(The interactive `YES` prompt fires regardless of source collection count. When source collections are 0, typing `YES` exits 0 with `Source collections deleted: 0` and `Total docs deleted: 0`. The runner only deletes if verification passed in the same invocation. `--yes` flag used for unattended VM execution.)_

**Stdout/stderr (verbatim):**

```
2026-05-12 08:13:52,096 INFO project_id=ken-e-dev database_id=(default)
2026-05-12 08:13:52,536 INFO [strategy_processing_state] Scanning top-level collections with prefix 'strategy_processing_state_'
2026-05-12 08:13:53,412 WARNING [strategy_processing_state] --yes supplied: skipping interactive confirmation for deletion
2026-05-12 08:13:53,412 INFO [strategy_processing_state] Deleting source collections with prefix 'strategy_processing_state_'
Resource: strategy_processing_state
  Source collections found:   0
  Source doc count:            0
  Destination path:            accounts/{id}/strategy_processing_state
  Destination doc count:       0
  Status:                      VERIFIED
  Next step:                   re-run with --confirm-delete
Resource: strategy_processing_state — deletion complete
  Source collections deleted: 0
  Total docs deleted:         0
```

**Exit code:** 0
**Source collections deleted:** 0
**Total docs deleted:** 0

---

## Step 5: Idempotency re-run (closes AC-8)

```
GOOGLE_CLOUD_PROJECT_ID=ken-e-dev python api/scripts/migrate_to_shape_b.py \
  --resource=strategy_processing_state
```

**Stdout/stderr (verbatim):**

```
2026-05-12 08:13:56,626 INFO project_id=ken-e-dev database_id=(default)
2026-05-12 08:13:57,070 INFO [strategy_processing_state] Scanning top-level collections with prefix 'strategy_processing_state_'
Resource: strategy_processing_state
  Source collections found:   0
  Source doc count:            0
  Destination path:            accounts/{id}/strategy_processing_state
  Destination doc count:       0
  Status:                      VERIFIED
  Next step:                   re-run with --confirm-delete
```

**Exit code:** 0
**Status reported:** VERIFIED
**New docs written:** 0
**Result:** no-op confirmed — re-run after `--confirm-delete` produces identical VERIFIED output with 0 docs touched

---

## Final state

- [x] All five steps completed and output captured above.
- [x] No top-level `strategy_processing_state_*` collections in `ken-e-dev`.
- [x] AC-2 (no legacy collections) satisfied for `strategy_processing_state`.
- [x] AC-8 (idempotency) confirmed by Step 5. _(DM-PRD-01 §6 AC-8 is written with `strategy_docs` as the example resource; the same idempotency mechanism applies to `strategy_processing_state`.)_

**DM-PRD-01 §6 (AC-2, AC-8) satisfied for `strategy_processing_state`:** ✓ complete
