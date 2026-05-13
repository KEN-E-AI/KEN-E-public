# DM-40 — `performance_profiles` Dev Migration Run Log

**Environment:** `ken-e-dev`
**Date:** 2026-05-13
**Operator:** Dev Team agent (VM)
**Issue:** [DM-40](https://linear.app/ken-e/issue/DM-40)
**PRD:** `docs/design/components/data-management/projects/DM-PRD-02-analytics-suite-migration.md`

## Context

Third and final data migration in DM-PRD-02 (`performance_profiles`). Records per-operation latency and bottleneck data emitted by `app/adk/agents/strategy_agent/performance_profiler.py` (`_store_metrics`). With this migration, no top-level `performance_profiles_acc_*` collections remain in the dev Firestore project — completing the data-migration half of DM-PRD-02 and unblocking DM-43 (end-to-end live-agent verification) and DM-PRD-05.

Pre-conditions confirmed at execution time:
- DM-30: `performance_profiles` registry entry live at `api/scripts/_migrate_shape_b/resources.py` (line 41-45, `old_prefix="performance_profiles_"`, no custom extractor)
- DM-33: `performance_profiler.py` call sites updated to `accounts/{account_id}/performance_profiles` (L240-242)
- DM-34: emulator integration test pins default-extractor behavior as regression guard
- DM-39: `agent_analytics` dev migration validated the `analytics` named database discovery approach

**Key finding confirmed from DM-39 — analytics named database:**

`PerformanceProfiler._init_firestore_client` initialises with `firestore.Client(project=self.project_id, database="analytics")` (`performance_profiler.py:139-141`). The `(default)` database had zero `performance_profiles_*` collections (consistent with DM-37/DM-39 empty-dev baseline). The actual data — 313 accounts, 1,652 docs — resided in the `analytics` named database. Per-account doc counts ranged from 1 to 54 (max: `performance_profiles_test_new_engine_123` with 54 docs), well below the PRD §8 100k-doc threshold.

**PRD §1 correction confirmed:** the `performance_profiles_acc_<hex>` source-collection pattern is confirmed as the single naming variant. The default `removeprefix("performance_profiles_")` extractor correctly returns the canonical `acc_<hex>` account_id. No custom `account_id_extractor` was needed (DM-30 PO verification, 2026-05-07).

## Migration Result

**Outcome: VERIFIED (313 source collections, 1,652 docs — all migrated and deleted)**

Two runs were performed per DM-39 precedent:

1. **`(default)` database:** Empty baseline — 0 `performance_profiles_*` collections found. All phases completed with `Source collections found: 0`, `Status: VERIFIED`, exit code 0. Consistent with DM-37 / DM-39 findings.

2. **`analytics` named database:** 313 `performance_profiles_acc_*` (and test-account) collections found with 1,652 total docs. Max per-account doc count: 54 (synthetic test account — well below the 100k flag threshold from PRD §8). All docs copied, verified (counts match), source collections deleted.

## Run Summary

### `(default)` database (structural no-op)

| Phase | Command | Source found | Status | Exit |
|---|---|---|---|---|
| Registry check | `--list` | — | `performance_profiles` confirmed | 0 |
| Dry-run | `--resource=performance_profiles --dry-run` | 0 collections, 0 docs | `DRY RUN` | 0 |
| Copy + verify | `--resource=performance_profiles` | 0 collections, 0 docs | `VERIFIED` | 0 |
| Confirm-delete | `--resource=performance_profiles --confirm-delete --yes` | 0 collections deleted | `VERIFIED` | 0 |
| Idempotency re-run | `--resource=performance_profiles` | 0 collections, 0 docs | `VERIFIED` | 0 |

### `analytics` named database (real data)

| Phase | Command | Source found | Dest count | Status | Exit | Wall time |
|---|---|---|---|---|---|---|
| Dry-run | `FIRESTORE_DATABASE_ID=analytics --resource=performance_profiles --dry-run` | 313 collections, 1,652 docs | 0 | `DRY RUN` | 0 | < 5 s |
| Copy + verify | `FIRESTORE_DATABASE_ID=analytics --resource=performance_profiles` | 313 collections, 1,652 docs | 1,652 | `VERIFIED` | 0 | ~45 s |
| Confirm-delete | `FIRESTORE_DATABASE_ID=analytics --resource=performance_profiles --confirm-delete --yes` | 313 deleted, 1,652 docs | 1,652 | `VERIFIED` | 0 | ~60 s |
| Idempotency re-run | `FIRESTORE_DATABASE_ID=analytics --resource=performance_profiles` | 0 collections, 0 docs | 0 | `VERIFIED` | 0 | < 5 s |

**Write throughput:** ~35 docs/sec during copy phase (1,652 docs / 45 s). Well within Firestore's WriteBatch limit of 500 operations per commit. No throttling observed.

**Per-account doc-count summary (dry-run inspection):**
- Total collections: 313
- Total docs: 1,652
- Max per account: 54 (`performance_profiles_test_new_engine_123` — synthetic test account)
- Average per account: 5.3
- Accounts > 100k docs: **0** — no halt needed (PRD §8 threshold check passed)

## Smoke Test (Task 7 — AC-6)

Exercised `PerformanceProfiler.start_operation()` + `end_operation()` (which calls `_store_metrics` when `duration` is set by `metrics.complete()`) against `ken-e-dev` (`analytics` database) with 3 synthetic operation cycles using `account_id="dm40_smoke"`:

| Check | Expected | Actual | Status |
|---|---|---|---|
| Shape B docs at `accounts/dm40_smoke/performance_profiles/` | 3 | 3 | ✅ |
| Shape A docs at `performance_profiles_dm40_smoke` | 0 | 0 | ✅ |
| Shape A docs at `performance_profiles_acc_dm40_smoke` | 0 | 0 | ✅ |
| `account_id` field in each doc | `dm40_smoke` | `dm40_smoke` | ✅ |
| `agent_name` field in each doc | `smoke_agent` | `smoke_agent` | ✅ |
| `duration_seconds` field in each doc | > 0 | 0.0502–0.0503 s | ✅ |
| Cleanup: docs remaining after delete | 0 | 0 | ✅ |

All 3 docs landed at `accounts/dm40_smoke/performance_profiles/{auto_id}` in the `analytics` database. No write to any top-level `performance_profiles_*` path. Smoke fixture cleaned up via collection delete + parent-doc delete.

## Acceptance Criteria

| AC | Criterion | Status |
|---|---|---|
| AC-2 (`performance_profiles` portion) | No top-level `performance_profiles_acc_*` collections remain in dev (`(default)` + `analytics` databases) | ✅ Confirmed — 0 in `(default)`; 0 in `analytics` post-cutover |
| AC-2 spot-check | `accounts/*/performance_profiles/...` contains 1,652 docs matching dry-run counts | ✅ Confirmed — verify phase reported 1,652 destination docs, matching 1,652 source docs |
| AC-6 (`performance_profiler` writes) | `performance_profiler` writes land at `accounts/{id}/performance_profiles/` in `analytics` database | ✅ Confirmed — 3 docs at Shape B path in smoke test, 0 at any legacy path |
| AC-8 | Migration script is idempotent | ✅ Re-run on both databases post-cutover: `VERIFIED`, exit 0 |
| PRD §8 threshold | No account exceeds 100k docs in dry-run; if exceeded, flag for DM-PRD-00 follow-up | ✅ Max was 54 — no halt/flag required |

## Notes

- **Analytics named database confirmed:** All `performance_profiles` data lived in the `analytics` named Firestore database, consistent with `performance_profiler.py:139-141` which always initialises with `database="analytics"`. The `(default)` database was empty for this resource across all phases.
- **Single naming pattern confirmed (PRD §1 correction):** All 313 source collections followed the `performance_profiles_acc_<hex>` pattern (plus ~9 synthetic test accounts using `performance_profiles_test_*` prefixes). The default `removeprefix("performance_profiles_")` extractor correctly extracted account_ids for all cases. No custom extractor was needed.
- **Max per-account count (54):** Observed on the synthetic `test_new_engine_123` test account — a long-running ADK test fixture that accumulated profiling data. Well within the PRD §8 100k threshold.
- **Smoke test import path:** The `performance_profiler` module was imported via `sys.path` manipulation (`app/adk/agents` as root) rather than via `adk.agents.strategy_agent` package init, which triggers ADK dependency chain and fails in the VM environment due to the `shared/secrets.py` ↔ stdlib `secrets` name collision. The direct-package import approach resolves relative imports correctly and is equivalent for smoke-testing purposes.
- **Collection-group query not available on `analytics` DB:** The pre-flight collision check and post-test read-back were performed via direct collection-path reads (`accounts/dm40_smoke/performance_profiles`) rather than `collection_group()` queries, because the `analytics` database does not have a collection-group index on `performance_profiles.account_id`. This is expected — the `performance_profiles` collection-group indexes in `deployment/firestore.indexes.json` target the `(default)` database only; the `analytics` database is an analytics-only write target.
- **Live-agent end-to-end verification** (confirming a real specialist run writes analytics to Shape B and `get_bottlenecks`/`optimization_analyzer` reads back correctly) is scoped to DM-43, not this issue.
- Full CLI stdout captured in the DM-40 Linear comment audit trail (2026-05-13).
