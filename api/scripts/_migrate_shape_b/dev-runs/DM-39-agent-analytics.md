# DM-39 — `agent_analytics` Dev Migration Run Log

**Environment:** `ken-e-dev`
**Date:** 2026-05-12
**Operator:** Dev Team agent (VM)
**Issue:** [DM-39](https://linear.app/ken-e/issue/DM-39)
**PRD:** `docs/design/components/data-management/projects/DM-PRD-02-analytics-suite-migration.md`

## Context

Second data migration in DM-PRD-02 (`agent_analytics`). Highest-volume resource by design — every agent run writes metrics; `async_analytics_queue` flushes events in batches. Per PRD §8, the dry-run inspection step was used to profile per-account doc counts before committing to the copy phase.

Pre-conditions confirmed at execution time:
- DM-30: `agent_analytics` registry entry live at `api/scripts/_migrate_shape_b/resources.py`
- DM-32: `analytics_service.py`, `async_analytics_queue.py`, `optimization_analyzer.py` call sites updated to `accounts/{account_id}/agent_analytics`
- DM-37: `cost_aggregations` dev migration validated the three-mode runbook pattern

**Key operational finding — analytics named database:**

The `async_analytics_queue` writes to the `analytics` named Firestore database (`database="analytics"` — `async_analytics_queue.py:96`), not the `(default)` database. The `(default)` database had zero `agent_analytics_*` collections (same empty-dev baseline as DM-37). The actual data — 287 accounts, 2,144 docs — resided in the `analytics` named database.

The migration required setting `FIRESTORE_DATABASE_ID=analytics` on all CLI invocations targeting the real data. The `(default)` database runs were a structural no-op (confirmed by the dry-run before the `analytics`-targeted run).

## Migration Result

**Outcome: VERIFIED (287 source collections, 2,144 docs — all migrated)**

Two runs were performed:

1. **`(default)` database (pre-discovery):** Empty baseline — 0 `agent_analytics_*` collections found. All phases completed with `Source collections found: 0`, `Status: VERIFIED`, exit code 0. Consistent with `cost_aggregations` (DM-37) finding.

2. **`analytics` named database (post-discovery):** 287 `agent_analytics_*` collections found with 2,144 total docs. Max per-account doc count: 79 (well below the 100k flag threshold from PRD §8). All docs copied, verified (counts match), source collections deleted.

## Run Summary

### `(default)` database (structural no-op)

| Phase | Command | Source found | Status | Exit |
|---|---|---|---|---|
| Registry check | `--list` | — | `agent_analytics` confirmed | 0 |
| Dry-run | `--resource=agent_analytics --dry-run` | 0 collections, 0 docs | `DRY RUN` | 0 |
| Copy + verify | `--resource=agent_analytics` | 0 collections, 0 docs | `VERIFIED` | 0 |
| Confirm-delete | `--resource=agent_analytics --confirm-delete --yes` | 0 collections deleted | `VERIFIED` | 0 |
| Idempotency re-run | `--resource=agent_analytics` | 0 collections, 0 docs | `VERIFIED` | 0 |

### `analytics` named database (real data)

| Phase | Command | Source found | Dest count | Status | Exit | Wall time |
|---|---|---|---|---|---|---|
| Dry-run | `FIRESTORE_DATABASE_ID=analytics --resource=agent_analytics --dry-run` | 287 collections, 2,144 docs | 0 | `DRY RUN` | 0 | < 5 s |
| Copy + verify | `FIRESTORE_DATABASE_ID=analytics --resource=agent_analytics` | 287 collections, 2,144 docs | 2,144 | `VERIFIED` | 0 | ~61 s |
| Confirm-delete | `FIRESTORE_DATABASE_ID=analytics --resource=agent_analytics --confirm-delete --yes` | 287 deleted, 2,144 docs | 2,144 | `VERIFIED` | 0 | ~73 s |
| Idempotency re-run | `FIRESTORE_DATABASE_ID=analytics --resource=agent_analytics` | 0 collections, 0 docs | 0 | `VERIFIED` | 0 | < 5 s |
| Collection-group spot-check | `collection_group("agent_analytics")` | — | 2,144 docs at `accounts/*/agent_analytics/...` | CONFIRMED | — | — |

**Write throughput:** ~35 docs/sec during copy phase. Well within the 500 writes/sec batch budget. No throttling observed.

**Per-account doc-count summary (dry-run inspection):**
- Total collections: 287
- Total docs: 2,144
- Max per account: 79 (`agent_analytics_test_new_engine_123`)
- Average per account: 7.5
- Accounts > 100k docs: **0** — no halt needed (PRD §8 threshold check passed)

## Smoke Test (Task 6 — AC-4)

Exercised `AsyncAnalyticsQueue._flush_batch` against `ken-e-dev` (`analytics` database) with a 3-event synthetic batch using `account_id="dm39_smoke"`:

| Check | Expected | Actual | Status |
|---|---|---|---|
| Shape B docs at `accounts/dm39_smoke/agent_analytics/` | 3 | 3 | ✅ |
| Shape A docs at `agent_analytics_dm39_smoke` | 0 | 0 | ✅ |
| Cleanup: docs remaining after `recursive_delete`-equivalent | 0 | 0 | ✅ |

Events were queued via `AsyncAnalyticsQueue.track_event()` and flushed synchronously via `AsyncAnalyticsQueue.flush()` (with `enable_background_worker=False` for deterministic execution). All 3 docs landed at `accounts/dm39_smoke/agent_analytics/{auto_id}` with `event_type=smoke_test`. No write to any top-level `agent_analytics_*` path. Smoke fixtures cleaned up.

## Acceptance Criteria

| AC | Criterion | Status |
|---|---|---|
| AC-2 (agent_analytics portion) | No top-level `agent_analytics_*` collections remain in dev (`(default)` + `analytics` databases) | ✅ Confirmed — 0 in `(default)`; 0 in `analytics` post-cutover |
| AC-4 (agent_analytics portion) | `async_analytics_queue` flushes events to `accounts/{id}/agent_analytics/...` | ✅ Confirmed — 3 docs at Shape B path in smoke test |
| AC-8 | Migration script is idempotent | ✅ Re-run on both databases: VERIFIED, exit 0 |
| PRD §8 100k-threshold | No account exceeds 100k docs in dry-run | ✅ Max was 79 — no halt/flag required |

## Notes

- **Analytics named database discovery:** All production `agent_analytics` data lived in the `analytics` named Firestore database, not `(default)`. This is consistent with `async_analytics_queue.py:96` which always initialises with `database="analytics"`. The DM-37 `cost_aggregations` run targeted only `(default)` — `cost_aggregations` is written by `analytics_service.py` which uses the default database client, so that run was correct. Future data-migration runbooks for analytics-related resources should profile **both** databases at the pre-flight step.
- **No queue coordination needed:** As expected, the dev `async_analytics_queue` was idle during the migration. DM-32 having already migrated all write paths to Shape B means the source `agent_analytics_*` collections in the `analytics` database were fully pre-DM-32 residue and no new writes were racing the delete.
- **Live-agent end-to-end verification** (confirming a real specialist run writes analytics to Shape B and `optimization_analyzer.py` reads back correctly) is scoped to DM-43, not this issue.
- Full CLI stdout captured in the DM-39 Linear comment audit trail (2026-05-12).
