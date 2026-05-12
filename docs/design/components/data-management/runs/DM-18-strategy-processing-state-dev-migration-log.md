# DM-18 — Dev Migration Run Log: `strategy_processing_state`

**Issue:** DM-18 — Run dev data migration: `strategy_processing_state` (smallest first — validates pattern)
**Resource:** `strategy_processing_state`
**Environment:** `ken-e-dev`
**Executor:** _paste executor identity (email or service account) here_
**Date:** _paste execution date (YYYY-MM-DD) here_
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

**Stdout/stderr (paste verbatim):**

```
_paste output here_
```

**Exit code:** _0 / non-zero_
**Source collections found:** _count_
**Notes:** _any unexpected output_

---

## Step 2: Copy + verify

```
GOOGLE_CLOUD_PROJECT_ID=ken-e-dev python api/scripts/migrate_to_shape_b.py \
  --resource=strategy_processing_state
```

**Stdout/stderr (paste verbatim):**

```
_paste output here_
```

**Exit code:** _0 / non-zero_
**Status reported:** _VERIFIED / FAILED_
**Source doc count:** _count_
**Destination doc count:** _count_

---

## Step 3: Console spot-check

**Checked in Firestore console for `ken-e-dev`:**

- Top-level `strategy_processing_state_*` collections present: _yes / no_
- Sample account checked: _redacted-account-id (or "N/A — no source data")_ ⚠️ **Redact real account IDs before committing; use a placeholder or log evidence in the Linear issue instead.**
- `accounts/{account_id}/strategy_processing_state/` present: _yes / no (or "N/A")_
- Observation: _paste notes here_

---

## Step 4: Confirm-delete

```
GOOGLE_CLOUD_PROJECT_ID=ken-e-dev python api/scripts/migrate_to_shape_b.py \
  --resource=strategy_processing_state --confirm-delete
```

_(The interactive `YES` prompt fires regardless of source collection count. When source collections are 0, typing `YES` exits 0 with `Source collections deleted: 0` and `Total docs deleted: 0`. The runner only deletes if verification passed in the same invocation.)_

**Stdout/stderr (paste verbatim):**

```
_paste output here_
```

**Exit code:** _0 / non-zero_
**Source collections deleted:** _count_
**Total docs deleted:** _count_

---

## Step 5: Idempotency re-run (closes AC-8)

```
GOOGLE_CLOUD_PROJECT_ID=ken-e-dev python api/scripts/migrate_to_shape_b.py \
  --resource=strategy_processing_state
```

**Stdout/stderr (paste verbatim):**

```
_paste output here_
```

**Exit code:** _0 / non-zero_
**Status reported:** _VERIFIED_
**New docs written:** _expected 0_
**Result:** _no-op confirmed / unexpected output_

---

## Final state

- [ ] All five steps completed and output captured above.
- [ ] No top-level `strategy_processing_state_*` collections in `ken-e-dev`.
- [ ] AC-2 (no legacy collections) satisfied for `strategy_processing_state`.
- [ ] AC-8 (idempotency) confirmed by Step 5. _(DM-PRD-01 §6 AC-8 is written with `strategy_docs` as the example resource; the same idempotency mechanism applies to `strategy_processing_state`.)_

**DM-PRD-01 §6 (AC-2, AC-8) satisfied for `strategy_processing_state`:** complete once all boxes above are checked.
