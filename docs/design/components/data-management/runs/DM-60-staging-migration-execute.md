# DM-60 — Staging Migration Execute Run-Log

**Issue:** DM-60 — Execute staging migration with `--confirm-delete` and verify counts (covers AC-1, §4.3 step 3b)
**PRD:** DM-PRD-06 §4.3 — Staging Cutover, step 3 (phases A & B)
**Date:** 2026-05-23 (Phase A) · 2026-05-23 (Phase B)
**Branch:** docs/DM-60-staging-migration-execute
**Executed by:** Dev Team agent (data-management-dev-team) — template · PO (`darshan@ken-e.ai`, ADC `roles/editor` on `ken-e-staging`) — command execution

> **Scope: `ken-e-staging` ONLY.** Production was not touched. DM-PRD-06 is the staging cutover; a production cutover is a separate future effort. Prod still holds its legacy Shape A.
>
> **Command note:** `migrate_to_shape_b.py` has **no `--env` flag** (the issue's documented command is stale) — it reads `GOOGLE_CLOUD_PROJECT_ID` and operates on one Firestore DB per invocation, so each phase is run twice (`FIRESTORE_DATABASE_ID="(default)"` and `="analytics"`). Times below are local (IST, UTC+5:30).

---

## Summary

| # | Item | Result | Notes |
|---|------|--------|-------|
| 1 | Phase A — `(default)` DB: copy + verify | ✅ VERIFIED (exit 0) | alert_configurations 14→14, monitoring_topics 3→3, strategy_docs 10→10; rest no-op |
| 2 | Phase A — `analytics` DB: copy + verify | ✅ VERIFIED (exit 0) | all resources 0 source — structural no-op (Ken's manual cleanup) |
| 3 | Phase A halt-decision gate | ✅ PROCEED | all dest==source, both exits 0, counts == DM-59 baseline |
| 4 | Phase B — `(default)` DB: `--confirm-delete` | ✅ 27 docs deleted (exit 0) | alert_configurations 14, monitoring_topics 3, strategy_docs 10 |
| 5 | Phase B — `analytics` DB: `--confirm-delete` | ✅ 0 deleted (exit 0) | structural no-op |
| 6 | Per-resource timing captured | ✅ | See §Per-resource Timing (wall-clock derived from log timestamps) |
| 7 | All ACs satisfied | ✅ | See §Acceptance Criteria |

---

## Pre-conditions

Both required upstream issues are Done before Phase A:

| Issue | Title | Status |
|-------|-------|--------|
| DM-58 | Schedule staging maintenance window and deploy DM-PRD-00–DM-PRD-05 code | Done ✅ |
| DM-59 | Run staging migration `--dry-run` and inspect output | Done ✅ |

**DM-59 baseline counts** (source counts observed during dry-run — the contract for Phase A verification):

| Resource | `(default)` DB — source colls | `(default)` DB — source docs | `analytics` DB — source colls | `analytics` DB — source docs |
|----------|-------------------------------|------------------------------|-------------------------------|------------------------------|
| alert_configurations | 14 | 14 | 0 | 0 |
| monitoring_topics | 3 | 3 | 0 | 0 |
| strategy_docs | 3 | 10 | 0 | 0 |
| agent_analytics | 0 | 0 | 0 | 0 |
| cost_aggregations | 0 | 0 | 0 | 0 |
| performance_profiles | 0 | 0 | 0 | 0 |
| strategy_audit | 0 | 0 | 0 | 0 |
| strategy_processing_state | 0 | 0 | 0 | 0 |

**Ghost-subcollection note (from Ken's DM-59 resolution, 2026-05-23T12:00:27Z):** some source collections in `(default)` (`alert_configurations`, `monitoring_topics`, `strategy_docs`) may belong to old test accounts that Ken manually deleted last week. Migrating them creates ghost Shape-B subcollections under non-existent account docs — this is a known-harmless Firestore pattern (same as DM-19 dev run). DM-PRD-05's `recursive_delete(accounts/{account_id})` sweep reconciles when the account docs are purged. Not a halt condition.

---

## Phase A — Copy + Verify

Phase A runs the migration in copy-only mode: source collections are read and docs are written to the new `accounts/{account_id}/{resource}/...` subcollections. Source collections are **not** deleted. Both passes exited 0 and all per-resource destination counts matched source counts before Phase B began.

### Phase A — `(default)` database

**Command:**
```bash
GOOGLE_CLOUD_PROJECT_ID=ken-e-staging FIRESTORE_DATABASE_ID="(default)" \
  uv run python scripts/migrate_to_shape_b.py --all
```

**Executed at:** 2026-05-23 ~17:34:23 (local)
**Exit code:** 0 (all resources VERIFIED)
**Elapsed (wall-clock):** ~1m38s

**Per-resource results:**

| Resource | Source colls | Source docs | Dest docs | Status | Elapsed (s) |
|----------|-------------|-------------|-----------|--------|-------------|
| agent_analytics | 0 | 0 | 0 | VERIFIED | ~1 |
| alert_configurations | 14 | 14 | 14 | VERIFIED | ~40 |
| cost_aggregations | 0 | 0 | 0 | VERIFIED | ~1 |
| monitoring_topics | 3 | 3 | 3 | VERIFIED | ~10 |
| performance_profiles | 0 | 0 | 0 | VERIFIED | ~2 |
| strategy_audit | 0 | 0 | 0 | VERIFIED | ~1 |
| strategy_docs | 3 | 10 | 10 | VERIFIED | ~34 |
| strategy_processing_state | 0 | 0 | 0 | VERIFIED | ~1 |

<details>
<summary>stdout (per-resource summary blocks)</summary>
<pre>
Resource: alert_configurations
  Source collections found:   14
  Source doc count:            14
  Destination doc count:       14
  Status:                      VERIFIED
Resource: monitoring_topics
  Source collections found:   3
  Source doc count:            3
  Destination doc count:       3
  Status:                      VERIFIED
Resource: strategy_docs
  Source collections found:   3   (acc <test> 1, acc_0c894e… 5, acc_53036cba… 4)
  Source doc count:            10
  Destination doc count:       10
  Status:                      VERIFIED
(agent_analytics, cost_aggregations, performance_profiles, strategy_audit,
 strategy_processing_state: 0 source / 0 dest / VERIFIED)
</pre>
</details>

### Phase A — `analytics` database

**Command:**
```bash
GOOGLE_CLOUD_PROJECT_ID=ken-e-staging FIRESTORE_DATABASE_ID="analytics" \
  uv run python scripts/migrate_to_shape_b.py --all
```

**Executed at:** 2026-05-23 ~17:36 (local)
**Exit code:** 0
**Elapsed (wall-clock):** ~0.5m

**Per-resource results:** all 8 resources `0 source / 0 dest / VERIFIED` — structural no-op. The pre-existing Shape B data in `analytics` (2 accounts with `performance_profiles`/`agent_analytics` subcollections) was never read, written, or deleted (the script only derives destinations from source collections, of which there were none).

---

## Phase A Halt-Decision Gate

| Check | Expected | Actual | Pass? |
|-------|----------|--------|-------|
| `(default)` DB: all per-resource destination counts == source counts | Yes | Yes (14=14, 3=3, 10=10) | ✅ |
| `(default)` DB: exit code = 0 | 0 | 0 | ✅ |
| `analytics` DB: all per-resource source counts = 0 | Yes | Yes | ✅ |
| `analytics` DB: exit code = 0 | 0 | 0 | ✅ |
| `(default)` source counts within ±2 docs of DM-59 baseline | Yes | Exact match (14/3/10) | ✅ |

**Gate decision:** ✅ PROCEED to Phase B.

---

## Phase B — Source-Collection Deletion (`--confirm-delete`)

Phase B copies (idempotent with Phase A — re-copy logged "Copied 0" since dest already present), re-verifies, then deletes source collections. Deletion is reached only after `migrate_resource` returns `EXIT_SUCCESS` (the in-`cmd_all` verify gate). Delete mechanism = batched `batch.delete(doc.reference)` (not `recursive_delete`); only the Shape A source is removed — the Shape B destination is untouched.

### Phase B — `(default)` database

**Command:**
```bash
GOOGLE_CLOUD_PROJECT_ID=ken-e-staging FIRESTORE_DATABASE_ID="(default)" \
  uv run python scripts/migrate_to_shape_b.py --all --confirm-delete --yes
```

**Executed at:** 2026-05-23 ~17:50:05 (local)
**Exit code:** 0
**Elapsed (wall-clock):** ~1m34s

**Per-resource deletion results:**

| Resource | Source colls deleted | Docs deleted | Malformed sources | Status | Elapsed (s) |
|----------|---------------------|-------------|-------------------|--------|-------------|
| agent_analytics | 0 | 0 | 0 | VERIFIED→no-op | ~1 |
| alert_configurations | 14 | 14 | 0 | VERIFIED→deleted | ~37 |
| cost_aggregations | 0 | 0 | 0 | VERIFIED→no-op | ~1 |
| monitoring_topics | 3 | 3 | 0 | VERIFIED→deleted | ~10 |
| performance_profiles | 0 | 0 | 0 | VERIFIED→no-op | ~1 |
| strategy_audit | 0 | 0 | 0 | VERIFIED→no-op | ~1 |
| strategy_docs | 3 | 10 | 0 | VERIFIED→deleted | ~33 |
| strategy_processing_state | 0 | 0 | 0 | VERIFIED→no-op | ~1 |

(`Source colls deleted` reflects the script's metric: account-docs for single-collection resources, actual collections for prefix-based `strategy_docs`. **Total docs deleted: 27.** No malformed sources.)

**Post-deletion residue check** — re-ran `--all --dry-run` against `(default)`:

```
all 8 resources → Source collections found: 0
```

**Residue check output:** empty (0 source collections for every resource) → ✅ pass.

### Phase B — `analytics` database

**Command:**
```bash
GOOGLE_CLOUD_PROJECT_ID=ken-e-staging FIRESTORE_DATABASE_ID="analytics" \
  uv run python scripts/migrate_to_shape_b.py --all --confirm-delete --yes
```

**Executed at:** 2026-05-23 ~17:51 (local)
**Exit code:** 0
**Result:** 0 deletions across every resource — structural no-op. Existing Shape B data untouched.

---

## Per-resource Timing

Wall-clock per-resource elapsed, derived from interleaved log timestamps (the script does not emit a per-resource timer). Resources not listed were 0-doc structural no-ops in both phases / both DBs (~1–2 s scan each, 0 writes). Timings are dominated by laptop→`nam5` round-trip latency (~serial RPCs/doc), **not** the script's 500 writes/sec batch ceiling — effective throughput is well under it. Feeds DM-62.

| Resource | Phase | DB | Docs | Elapsed (s) | Effective docs/sec | Within 500/sec ceiling? |
|----------|-------|----|------|-------------|--------------------|------------------------|
| alert_configurations | A (copy) | (default) | 14 | ~40 | ~0.35 | Yes |
| alert_configurations | B (delete) | (default) | 14 | ~37 | ~0.38 | Yes |
| monitoring_topics | A (copy) | (default) | 3 | ~10 | ~0.30 | Yes |
| monitoring_topics | B (delete) | (default) | 3 | ~10 | ~0.30 | Yes |
| strategy_docs | A (copy) | (default) | 10 | ~34 | ~0.29 | Yes |
| strategy_docs | B (delete) | (default) | 10 | ~33 | ~0.30 | Yes |
| _all other resource × phase × DB combos_ | — | — | 0 | ~0 | n/a | Yes |

> **DM-62 note:** throughput is RTT-bound, not batch-rate-bound — a prod run with substantially more data per account would scale roughly linearly with doc count at this per-doc latency. None exceeded the 10 s/collection range seen in the DM-19 dev run.

---

## Acceptance Criteria

| AC | Criterion | Status | Evidence |
|----|-----------|--------|---------|
| AC-1 | Staging migration executes successfully across all registered resources | ✅ | Phase A + Phase B both exit 0 |
| AC-2 | Phase A: source / destination per-resource counts match | ✅ | 14=14, 3=3, 10=10; halt-gate PROCEED |
| AC-3 | Phase B: source collections deleted; new Shape B paths populated | ✅ | 27 docs deleted; post-cutover dry-run 0 source; dest verified before delete |
| AC-4 | Per-resource elapsed time captured for DM-62's report | ✅ | §Per-resource Timing |
| AC-5 | Any verification failure halts the run and is filed against the responsible team | ✅ (vacuous) | No verification failure occurred; halt-gate passed |

---

## Sign-off

| Field | Value |
|-------|-------|
| Date — Phase A | 2026-05-23 |
| Date — Phase B | 2026-05-23 |
| Operator — command execution | `darshan@ken-e.ai` (PO; ADC `roles/editor` on `ken-e-staging`) |
| Agent — template | data-management-dev-team |
| Pre-condition: DM-58 (deploy) | Done ✅ — rev `ae7d3b99` / `kene-api-staging-00336-qkg` (re-confirmed at window-open) |
| Pre-condition: DM-59 (dry-run) | Done ✅ — baseline counts in §Pre-conditions above |
| Ghost-subcollection note | Acknowledged — harmless; DM-PRD-05 `recursive_delete` reconciles |
| Downstream issues unblocked by this run | DM-61 (Phase 6 staging checklist), DM-62 (timing report), DM-63 (Review 16), DM-65 (README status flip) |

---
_Produced by: data-management-dev-team (template) · PO execution + run-log fill 2026-05-23 | Issue: DM-60_
