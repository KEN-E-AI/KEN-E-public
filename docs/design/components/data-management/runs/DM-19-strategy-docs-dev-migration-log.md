# DM-19 — Dev Migration Run Log: `strategy_docs` (with `versions/{n}` subcollection)

**Issue:** DM-19 — Run dev data migration: `strategy_docs` (with `versions/{n}` subcollection)
**Resource:** `strategy_docs`
**Environment:** `ken-e-dev` (`(default)` Firestore database)
**Executor:** Darshan Valia (PO, local mac) with a transient `dm19-local-migration@ken-e-dev.iam.gserviceaccount.com` service-account key — deleted after the run
**Date:** 2026-05-13
**Migration CLI:** `api/scripts/migrate_to_shape_b.py`
**Outcome:** **COMPLETED.** 105 source collections / 387 docs migrated, verified, deleted; idempotency re-run is a no-op; AC-6 smoke clean. 0 `strategy_docs_*` collections remain in `ken-e-dev`.

---

## Context

This issue had a first attempt on 2026-05-12 that **aborted at Step 1** — the dev-team agent's dry-run crashed on a top-level Firestore collection literally named `strategy_docs_` (the resource prefix with no account suffix). The runner's `_extract_account_id` returned `""` for that name and the runner then built the malformed Firestore path `accounts//strategy_docs`, which the SDK rejects with `InvalidArgument`. The abort discovered two blockers: (1) the runner bug, (2) a non-empty dev baseline contradicting the initial "0 source collections" assumption (106 source collections present — 1 orphan + 102 real-account + 3 test-account).

Both blockers were resolved before this re-run:

1. **Runner bug fixed in PR #455** (merged to `main` at `999a51c` on 2026-05-13). The runner now skips any source collection whose extracted `account_id` fails `_is_valid_account_id` (rejects empty / `/`-bearing / `.` / `..`), records the skip on a new `malformed_sources: list[str]` field on `CopyResult` / `VerifyResult` / `DeleteResult`, and surfaces the list in the operator-facing summary blocks ("Malformed source collections (skipped|left in place): N — <names>") plus an "Operator action: remove manually" line so AC-2 can't silently fail.
2. **PO direction captured on the DM-19 Linear thread** (4 decisions): (a) runner fix via local PR (done — #455); (b) migrate the 102 real `acc_<hex32>` accounts; (c) migrate the 3 test-account collections as-is (they have valid non-empty IDs after prefix-strip; future cleanup belongs to DM-PRD-05); (d) pre-delete the empty-suffix orphan via a one-time `recursive_delete` before the migration runs (because the runner correctly *skips* malformed sources but does not *remove* them, so AC-2 — "no top-level `strategy_docs_*` collections remain" — requires the operator to handle the orphan separately).

---

## Pre-flight checks (PO-verified, 2026-05-13)

### (a) Registry entry

`RESOURCES["strategy_docs"]` confirmed at `api/scripts/_migrate_shape_b/resources.py:19-23`: `old_prefix="strategy_docs_"`, `new_subcollection="strategy_docs"`, `has_versions=True`. ✓

### (b) Unit tests on the runner

```
cd api && uv run pytest tests/unit/test_migrate_to_shape_b.py -q
86 passed in 1.91s
```

Includes the 7-test `TestMalformedSourceCollection` class added in #455. ✓

### (c) Shape A residue grep (source-tree)

```
rg -n 'strategy_docs_\{|f"strategy_docs_|f'"'"'strategy_docs_' api/src/ app/
```

Returns exactly 3 hits, all in `routers/accounts.py` (the legacy deletion-sweep carve-out owned by DM-PRD-05; PRD §4 explicitly excludes these). ✓

### (d) Multi-database inventory

`ken-e-dev` has three Firestore databases: `(default)`, `eval-feedback`, `analytics`. Inventory for `strategy_*` data across all three (lesson from DM-39's `analytics` named-DB discovery):

| DB | `strategy_*` collections | Notes |
|---|---|---|
| `(default)` | 112 | 105 in-scope (102 real + 3 test) + 1 orphan + 6 unrelated globals (see §Out-of-scope below) |
| `eval-feedback` | 0 | clean |
| `analytics` | 0 | clean |

Confirms `strategy_docs_*` data lives only in `(default)`. The `strategy_audit_*` and `strategy_processing_state_*` prefixes — DM-20 and DM-18 respectively — are also absent across all three DBs, so DM-20 will be a structural no-op when it runs. ✓

---

## Step 0 — Orphan cleanup (manual, pre-migration)

### Pre-delete audit snapshot

Saved a full JSON snapshot of the orphan `strategy_docs_` collection to `/tmp/dm19-artifacts/orphan-snapshot.json` (30,734 bytes, not committed) before the destructive call. Summary of what was in there:

| Doc ID | `account_id` | `doc_type` | `version` | `created_by` | Created/Updated | Content keys |
|---|---|---|---|---|---|---|
| `business_strategy` | `''` (empty) | `business_strategy` | 1 | `system` | 2025-09-04 10:37:57 UTC | 8 keys: `externalEnvironmentAnalysisPESTEL`, `marketAndIndustryAnalysis`, `productsAndServices`, `marketingAndCustomerStrategy`, `companyOverview`, `swotAnalysis`, `businessStrategySummary`, `strategicRecommendationsAndFutureOutlook` |
| `competitive_strategy` | `''` (empty) | `competitive_strategy` | 1 | `system` | 2025-09-04 10:41:03 UTC | 5 keys: `detailedCompetitorProfiles`, `portersFiveForces`, `competitiveStrategySummary`, `competitiveLandscape`, `strategicRecommendations` |

Both docs carry `account_id=''` in their data — confirming they cannot be salvaged to a real account. They are 8-month-old artifacts of a write path that formatted `f"strategy_docs_{empty_account_id}"` with an empty string.

### Delete

```python
from google.cloud import firestore
c = firestore.Client(project="ken-e-dev", database="(default)")
c.recursive_delete(c.collection("strategy_docs_"))
```

**Result:** `Before delete: 2 docs in 'strategy_docs_' / After delete: 0 docs in 'strategy_docs_'`. Orphan collection cleared. 105 in-scope `strategy_docs_*` collections remain.

---

## Step 1 — Dry-run

```
GOOGLE_CLOUD_PROJECT_ID=ken-e-dev uv run python api/scripts/migrate_to_shape_b.py \
  --resource=strategy_docs --dry-run
```

```
Resource: strategy_docs
  Source collections found:   105
  Source doc count:            387
  Destination path:            accounts/{id}/strategy_docs
  Destination doc count:       0
  Status:                      DRY RUN
  Next step:                   re-run without --dry-run to copy
```

Exit code: 0. No "Malformed source collections" line — confirms the orphan delete worked and no other malformed sources are hiding. ✓

---

## Step 2 — Copy + verify

```
GOOGLE_CLOUD_PROJECT_ID=ken-e-dev uv run python api/scripts/migrate_to_shape_b.py \
  --resource=strategy_docs
```

Wall time: ~8 minutes (105 collections × ~5–14s/collection — laptop-to-`nam5` RTT, ~2 serial RPCs per source doc for idempotency check + `versions/` subcollection probe).

Per-collection log lines (verbose, abbreviated):
```
[strategy_docs] Copied 2 docs from strategy_docs_acc_01314f… → accounts/acc_01314f…/strategy_docs
[strategy_docs] Copied 5 docs from strategy_docs_acc_02362f… → accounts/acc_02362f…/strategy_docs
…
[strategy_docs] Copied 2 docs from strategy_docs_test_account_123 → accounts/test_account_123/strategy_docs
[strategy_docs] Copied 5 docs from strategy_docs_test_api_123 → accounts/test_api_123/strategy_docs
[strategy_docs] Copied 5 docs from strategy_docs_test_final_123 → accounts/test_final_123/strategy_docs
```

Summary:
```
Resource: strategy_docs
  Source collections found:   105
  Source doc count:            387
  Destination path:            accounts/{id}/strategy_docs
  Destination doc count:       387
  Status:                      VERIFIED
  Next step:                   re-run with --confirm-delete
```

Exit code: 0. **387/387 docs copied + verified.** No malformed-source line. ✓

---

## Step 3 — Spot-check (collection-group + sample accounts)

VM/local doesn't have Cloud Console UI; substitution via collection-group query matches the DM-37/DM-39 precedent.

```python
from google.cloud import firestore
c = firestore.Client(project="ken-e-dev", database="(default)")
# Total docs across all destinations
print(sum(1 for _ in c.collection_group("strategy_docs").stream()))
# → 387  (matches Step 2 source-doc count exactly)

# Sample one real account
list(c.collection("accounts").document("acc_01314f6855664ac3b249b0ce08990595").collection("strategy_docs").stream())
# → 2 docs: _placeholder, marketing_strategy

# Sample one test account
list(c.collection("accounts").document("test_api_123").collection("strategy_docs").stream())
# → 5 docs: brand_guidelines, business_strategy, competitive_strategy, customer_strategy, marketing_strategy
```

Spot-check passes. ✓

**Ghost-doc destinations note:** None of the 102 real or 3 test source-account IDs have a matching `accounts/{id}` root doc in `(default)` (the `accounts` root has only 1 doc total). The destinations are therefore "ghost-doc" subcollections — subcollection docs under non-existent parent docs. This is a normal Firestore pattern (collection-group queries find them; `db.collection("accounts").stream()` does not). PRD §2.2 implies root docs come from DM-PRD-03's Shape D split, which already ran as a no-op against the empty `org_test_neo4j` org. Not a blocker.

---

## Step 4 — Confirm-delete

```
GOOGLE_CLOUD_PROJECT_ID=ken-e-dev uv run python api/scripts/migrate_to_shape_b.py \
  --resource=strategy_docs --confirm-delete --yes
```

Wall time: ~13 minutes (in-invocation re-verify pass for all 105 collections, then bulk delete pass).

In-invocation re-verify completes with `Status: VERIFIED, 387/387`, then deletion proceeds:

```
[strategy_docs] Deleted 2 docs from strategy_docs_acc_01314f6855664ac3b249b0ce08990595
[strategy_docs] Deleted 5 docs from strategy_docs_acc_02362f2f4560478a93f37c0093e5cf65
…
[strategy_docs] Deleted 2 docs from strategy_docs_test_account_123
[strategy_docs] Deleted 5 docs from strategy_docs_test_api_123
[strategy_docs] Deleted 5 docs from strategy_docs_test_final_123
Resource: strategy_docs — deletion complete
  Source collections deleted: 105
  Total docs deleted:         387
```

Exit code: 0. No "Malformed source collections (left in place)" line. ✓

**Independent post-delete verification:**

```python
src = [col.id for col in c.collections() if col.id.startswith("strategy_docs_")]
# → []

cg_count = sum(1 for _ in c.collection_group("strategy_docs").stream())
# → 387
```

**0 source collections remain. 387 docs intact at destination. AC-2 satisfied.** ✓

---

## Step 5 — Idempotency re-run (AC-8)

```
GOOGLE_CLOUD_PROJECT_ID=ken-e-dev uv run python api/scripts/migrate_to_shape_b.py \
  --resource=strategy_docs
```

```
Resource: strategy_docs
  Source collections found:   0
  Source doc count:            0
  Destination path:            accounts/{id}/strategy_docs
  Destination doc count:       0
  Status:                      VERIFIED
  Next step:                   re-run with --confirm-delete
```

Exit code: 0. No copies, no writes, no deletes — true no-op. **AC-8 satisfied.** ✓

> The `Destination doc count: 0` here is a runner quirk: post-delete, the runner has no source `account_ids` to enumerate, so it counts zero matching destinations. The collection-group query in Step 3 / Step 4 independently confirms all 387 destination docs are intact.

---

## Step 6 — AC-6 smoke: `check_strategy_docs.py`

PRD §6 AC-6: *"`api/check_strategy_docs.py` prints strategy doc contents for a migrated account without error."*

Two invocations captured — the script as-is (hardcoded `acc_dc291ae14bb74219b7882c1b13c2161d` is not one of the 102 migrated accounts in dev, same as DM-18 precedent) and a one-off with a real migrated account_id for a stronger demonstration:

### AC-6.a — script as-is

```
cd api && uv run python check_strategy_docs.py
```

```
Checking Firestore collection: accounts/acc_dc291ae14bb74219b7882c1b13c2161d/strategy_docs
==================================================
==================================================
❌ No documents found yet - strategy generation may still be in progress
```

Exit code 0. No Python traceback. Script targets the Shape B path correctly (`accounts/{account_id}/strategy_docs`, updated by DM-17 — verified at `api/check_strategy_docs.py:14`). Matches the DM-18 precedent reading of AC-6 ("runs cleanly without error"). ✓

### AC-6.b — same logic with a real migrated account

```python
account_id = "acc_01314f6855664ac3b249b0ce08990595"   # one of the 102 migrated real accounts
db.collection(f"accounts/{account_id}/strategy_docs").stream()
```

```
Checking Firestore collection: accounts/acc_01314f6855664ac3b249b0ce08990595/strategy_docs
==================================================
==================================================
✓ _placeholder  doc_type=(no doc_type)  version=(no version)  created_at=2025-11-04T13:52:03.727218  content=<empty/other>
✓ marketing_strategy  doc_type=marketing_strategy  version=1  created_at=2025-11-04 13:54:53.854745+00:00  content=<dict, 2 keys>

Exit code: 0  (2 docs)
```

Stronger demonstration: 2 docs at the Shape B path, including a real `marketing_strategy` doc with `doc_type`, `version`, and a populated content dict — proves the migrated data is reachable through the same query pattern the script uses. ✓

---

## Step 7 — AC-7: pytest + lint

PRD §6 AC-7 / README §7.3: *"`pytest api/tests/ app/adk/agents/strategy_agent/tests/` passes. `make lint` clean."*

Baseline state on `main` (the same `999a51c` this branch is rebased onto) — measured to demonstrate that DM-19 introduces **zero new failures**:

| Tool | Result on `main` | Result on this branch | Delta from DM-19 |
|---|---|---|---|
| `pytest api/tests/` | 220 failed, 1,394 passed, 137 skipped, 71 errors (108s) | identical (this branch has no code changes; only the run-log markdown) | **0 regressions** |
| `ruff check .` (entire repo) | 2,451 errors | identical | **0 regressions** |
| `mypy .` (entire repo) | 4,385 errors / 426 files | identical | **0 regressions** |
| `make lint` (`codespell`) | fails on `node_modules` typos (`CACL ==> CALC`) | identical | **0 regressions** |

**AC-7 verdict:** the literal text of AC-7 is **not met** because of the pre-existing org-debt baseline on `main` — but DM-19 (and the runner-fix PR #455 that preceded it) introduces zero new failures. Same posture established by DM-37 / DM-39 / DM-46. The migration-specific test file passes 86/86: `cd api && uv run pytest tests/unit/test_migrate_to_shape_b.py -q` → exits 0.

---

## Step 8 — Operator-deferred recipes (AC-4 / AC-5)

The DM-19 issue body explicitly labels AC-4 / AC-5 as **manual smoke tests** because they require a live API server hitting `ken-e-dev` Firestore plus Firebase auth tokens — not in this run's scope. Same operator-deferred framing as DM-18 TC-4. Recipes for a future operator:

### AC-4 — `POST /api/v1/accounts/{id}/strategy/...` lands at Shape B + creates audit row

```
TOKEN=$(firebase auth-print-token darshan@ken-e.ai)
ACCOUNT_ID=acc_01314f6855664ac3b249b0ce08990595
curl -sS -X POST "https://api.ken-e-dev.example.com/api/v1/accounts/$ACCOUNT_ID/strategy/business_strategy" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"content": {"businessStrategySummary": "smoke-test"}}'
```

Expected: `accounts/$ACCOUNT_ID/strategy_docs/business_strategy` exists with the new content + `accounts/$ACCOUNT_ID/strategy_audit/{audit_id}` row created.

### AC-5 — Editing a strategy doc creates `versions/{n+1}`

```
curl -sS -X PUT "https://api.ken-e-dev.example.com/api/v1/accounts/$ACCOUNT_ID/strategy/business_strategy" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"content": {"businessStrategySummary": "smoke-test edited"}}'
```

Expected: `accounts/$ACCOUNT_ID/strategy_docs/business_strategy/versions/2` exists with the new content; `version` field bumped on the parent doc.

These can be folded into a future live-agent-end-to-end issue (analogous to DM-43 for analytics) when a PO has both API and Firebase auth handy.

---

## Out-of-scope collections observed (untouched by this migration)

The pre-flight inventory of `(default)` surfaced **6 global, non-account-scoped collections** that start with `strategy_*` but do **NOT** match the runner's `strategy_docs_` prefix and are therefore skipped at the `col_name.startswith(config.old_prefix)` filter:

| Collection | Doc count (not inspected) | DM-PRD-01 disposition |
|---|---|---|
| `strategy_doc_guides` | — | Explicitly listed in README §2.2 under "Non-account-scoped (unchanged)" — DM-PRD-01 §2 Out-of-scope. |
| `strategy_documents_brand_guidelines` | — | Not in any DM PRD; appears to be legacy global content. Same shape (single global collection, no `_acc_` per-account split). |
| `strategy_documents_business_strategy` | — | Same. |
| `strategy_documents_competitive_analysis` | — | Same. |
| `strategy_documents_marketing_strategy` | — | Same. |
| `strategy_sessions` | — | Not in any DM PRD; appears to be session-tracking global data. |

None are touched by this migration. If any need migration in the future, they would be picked up by a separate DM PRD with its own prefix registration.

---

## Final state — AC table

| AC | Source | Status |
|---|---|---|
| **PRD §6 AC-1** — call sites grep clean | `routers/accounts.py:913,968,970` are the documented DM-PRD-05 carve-out | ✅ verified in pre-flight (c) |
| **PRD §6 AC-2 / DM-19 AC #1** — no top-level `strategy_docs_*` in dev | Step 4 + independent verification | ✅ 0 collections remain |
| **PRD §6 AC-2 spot-check / DM-19 AC #2** — per-account doc counts match dry-run | Step 3 collection-group query (387 = 387) + per-account samples | ✅ |
| **PRD §6 AC-4** — `POST /strategy/...` lands at Shape B + audit | Operator-deferred recipe (Step 8) | ⏸ deferred — same as DM-18 |
| **PRD §6 AC-5** — edit creates `versions/{n+1}` | Operator-deferred recipe (Step 8) | ⏸ deferred — same as DM-18 |
| **PRD §6 AC-6** — `check_strategy_docs.py` runs cleanly | Step 6 (a) as-is + (b) with real migrated account | ✅ both pass exit 0 |
| **PRD §6 AC-7** — `pytest` + `make lint` | Step 7 baseline measurement | ⚠️ not met by literal AC text — pre-existing org-debt baseline identical on `main`; DM-19 introduces 0 regressions |
| **PRD §6 AC-8** — Migration script is idempotent | Step 5 idempotency re-run | ✅ 0 source / 0 writes / exit 0 |
| **README §7.3 verification gate** — dry-run → confirm-delete → pytest → make lint | Steps 1 / 4 / 7 | ✅ procedurally complete |

DM-PRD-05 dependency: this run satisfies the `strategy_docs` slice of "all data-migration projects complete the verification gate" (README §7.3 line 262).

---

## Audit trail

- Runner-bug fix: PR #455 (`fix(data-management): guard runner against malformed source collections (DM-PRD-00)`) — merged to `main` at `999a51c` on 2026-05-13.
- Linear DM-19 PO comment (2026-05-13) capturing the 4 PO decisions before the re-run.
- Original abort run-log: replaced by this document; the abort discovery is preserved in the DM-19 Linear comment thread + summarized in the §Context section above.
- Service-account key `dm19-local-migration@ken-e-dev.iam.gserviceaccount.com` (key id `f4f4c7b0db58f2edf1ed536322592e03a02c2256`) was created for this run only and is deleted after the PR lands.
- Orphan-snapshot JSON at `/tmp/dm19-artifacts/orphan-snapshot.json` is NOT committed (contains full content of two ~15KB strategy docs); summarized in §Step 0 above.
