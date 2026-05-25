# DM-62 — Staging Migration Timing Report

**Issue:** DM-62 — Document staging migration timing report (covers AC-5, §4.3 step 5)
**PRD:** DM-PRD-06 §4.3 step 5 (staging run timing) · §5 AC-5 · §7 Risks row 2
**Date of migration run:** 2026-05-23
**Date of report:** 2026-05-23
**Branch:** docs/DM-62-staging-migration-timing-report
**Source data:** DM-60 run-log (PR #615) — operator-filled timing; executed by `darshan@ken-e.ai`

---

## 1. Summary

The Shape A → B staging migration (`ken-e-staging`, Firestore `(default)` and `analytics` databases) ran on 2026-05-23 in four invocations — Phase A (copy + verify) × 2 DBs, then Phase B (confirm-delete) × 2 DBs. A total of **27 source documents** were migrated across 3 resources (`alert_configurations` 14, `monitoring_topics` 3, `strategy_docs` 10) in the `(default)` database. The `analytics` database was a structural no-op (0 source documents in all 8 resources). Both databases completed Phase A and Phase B with exit code 0.

Effective throughput was **0.29–0.38 docs/sec** across all non-zero resources — orders of magnitude below the 500 writes/sec batch ceiling specified in PRD §7 Risks. Latency was dominated by laptop→`nam5` Firestore round-trip (~serial RPCs per document), not the batch rate limiter. See §6 for production-scale implications.

---

## 2. Source Data

| Reference | Location | Notes |
|-----------|----------|-------|
| DM-60 run-log (Phase A + B results, timing table) | [PR #615](https://github.com/KEN-E-AI/KEN-E/pull/615) · `docs/design/components/data-management/runs/DM-60-staging-migration-execute.md` (branch `docs/DM-60-staging-migration-execute`) | Operator-filled timing data in §Per-resource Timing and §Phase A/B results |
| DM-59 dry-run baseline counts | DM-59 Linear issue (Done) | Source-collection counts verified before Phase A |
| DM-60 Linear comment (2026-05-23T12:24:25Z) | DM-60 issue thread | Aggregate confirmation: `(default)` 27 docs (14+3+10); `analytics` 0 |

---

## 3. Methodology

### 3.1 Per-resource elapsed time

The `migrate_to_shape_b.py` script (invoked via `--all`) does not emit an explicit per-resource elapsed-time line. The logger format at `api/scripts/migrate_to_shape_b.py:53` is:

```python
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
```

`%(asctime)s` defaults to `YYYY-MM-DD HH:MM:SS,mmm` (millisecond resolution). Per-resource granularity is reconstructed from the timestamp-prefixed `INFO [resource_name] Scanning …` log lines that bracket each resource's work in the `--all` invocation's stdout. The DM-60 run-log §Per-resource Timing section derives elapsed times from these boundaries, and the per-invocation wall-clock totals (from `Executed at` + `Elapsed (wall-clock)` in §Phase A and §Phase B) serve as a cross-check.

**Precision floor:** for resources with 0 source documents, the script scans for source collections and immediately finds none — elapsed time is dominated by a single Firestore list RPC (~1–4 s at `nam5` latency). These are reported as `< 1 s (scan only)` where a precise per-resource delta was not captured, and `n/a (0 docs)` for the writes/sec column.

**What would invalidate this methodology:** if the script is extended to emit an explicit `Elapsed: Xs` per-resource line, switch to consuming that directly. The per-resource elapsed values in the DM-60 run-log are marked `~` (approximate) because they are derived from interleaved log-line timestamps rather than a stop-watch.

### 3.2 Effective writes/sec

```
Effective writes/sec = Source docs ÷ Elapsed (s)
```

- **Phase A (copy):** 1 Firestore write per source document (destination doc creation).
- **Phase B (delete):** 1 Firestore batch-delete per source document (source collection deletion via `batch.delete(doc.reference)`).

No write fan-out: `strategy_docs` has `has_versions=True` but the staging run had 0 version subcollections; the count is confirmed 1:1.

**0-doc rows:** effective writes/sec = `n/a (0 docs)`. Division by zero is avoided; the ceiling check defaults to `Yes` (the ceiling was not approached).

### 3.3 "Within 500/sec ceiling?" column

PRD §7 Risks row 2 sets a 500 writes/sec batch ceiling per collection. A row is `Yes` if:
- Source docs = 0, OR
- Effective writes/sec < 500

A row is `No (rate=X.X)` only if effective writes/sec ≥ 500. No row in this run came close to the ceiling.

---

## 4. Per-resource Timing Table

**Columns:** Resource | Phase | DB | Source docs | Elapsed (s) | Effective writes/sec | Within 500/sec ceiling?

Rows are ordered by Resource (alphabetical), then Phase (A before B), then DB (`(default)` before `analytics`). 0-doc rows are included for completeness and grep-ability.

> **Note:** All timings are approximate (`~`), derived from log-timestamp deltas in DM-60's run-log. The `analytics` DB Phase A total wall-clock was ~30 s across all 8 resources (structural no-op); Phase B analytics was ~0 s (immediate no-op exit). Per-resource scan time for 0-doc resources is not individually distinguishable at 1-second log resolution.

| Resource | Phase | DB | Source docs | Elapsed (s) | Effective writes/sec | Within 500/sec ceiling? |
|----------|-------|----|-------------|-------------|---------------------|------------------------|
| agent_analytics | A (copy) | (default) | 0 | ~1 | n/a (0 docs) | Yes |
| agent_analytics | A (copy) | analytics | 0 | ~1 | n/a (0 docs) | Yes |
| agent_analytics | B (delete) | (default) | 0 | ~1 | n/a (0 docs) | Yes |
| agent_analytics | B (delete) | analytics | 0 | ~0 | n/a (0 docs) | Yes |
| alert_configurations | A (copy) | (default) | 14 | ~40 | ~0.35 | Yes |
| alert_configurations | A (copy) | analytics | 0 | ~1 | n/a (0 docs) | Yes |
| alert_configurations | B (delete) | (default) | 14 | ~37 | ~0.38 | Yes |
| alert_configurations | B (delete) | analytics | 0 | ~0 | n/a (0 docs) | Yes |
| cost_aggregations | A (copy) | (default) | 0 | ~1 | n/a (0 docs) | Yes |
| cost_aggregations | A (copy) | analytics | 0 | ~1 | n/a (0 docs) | Yes |
| cost_aggregations | B (delete) | (default) | 0 | ~1 | n/a (0 docs) | Yes |
| cost_aggregations | B (delete) | analytics | 0 | ~0 | n/a (0 docs) | Yes |
| monitoring_topics | A (copy) | (default) | 3 | ~10 | ~0.30 | Yes |
| monitoring_topics | A (copy) | analytics | 0 | ~1 | n/a (0 docs) | Yes |
| monitoring_topics | B (delete) | (default) | 3 | ~10 | ~0.30 | Yes |
| monitoring_topics | B (delete) | analytics | 0 | ~0 | n/a (0 docs) | Yes |
| performance_profiles | A (copy) | (default) | 0 | ~2 | n/a (0 docs) | Yes |
| performance_profiles | A (copy) | analytics | 0 | ~1 | n/a (0 docs) | Yes |
| performance_profiles | B (delete) | (default) | 0 | ~1 | n/a (0 docs) | Yes |
| performance_profiles | B (delete) | analytics | 0 | ~0 | n/a (0 docs) | Yes |
| strategy_audit | A (copy) | (default) | 0 | ~1 | n/a (0 docs) | Yes |
| strategy_audit | A (copy) | analytics | 0 | ~1 | n/a (0 docs) | Yes |
| strategy_audit | B (delete) | (default) | 0 | ~1 | n/a (0 docs) | Yes |
| strategy_audit | B (delete) | analytics | 0 | ~0 | n/a (0 docs) | Yes |
| strategy_docs | A (copy) | (default) | 10 | ~34 | ~0.29 | Yes |
| strategy_docs | A (copy) | analytics | 0 | ~1 | n/a (0 docs) | Yes |
| strategy_docs | B (delete) | (default) | 10 | ~33 | ~0.30 | Yes |
| strategy_docs | B (delete) | analytics | 0 | ~0 | n/a (0 docs) | Yes |
| strategy_processing_state | A (copy) | (default) | 0 | ~1 | n/a (0 docs) | Yes |
| strategy_processing_state | A (copy) | analytics | 0 | ~1 | n/a (0 docs) | Yes |
| strategy_processing_state | B (delete) | (default) | 0 | ~1 | n/a (0 docs) | Yes |
| strategy_processing_state | B (delete) | analytics | 0 | ~0 | n/a (0 docs) | Yes |

**All 32 rows: within 500/sec ceiling ✅**

---

## 5. Aggregate Summary

### 5.1 Per-invocation wall-clock

| Invocation | DB | Docs affected | Wall-clock elapsed |
|------------|-----|---------------|-------------------|
| Phase A — copy + verify | (default) | 27 copied | ~1 m 38 s (~98 s) |
| Phase A — copy + verify | analytics | 0 | ~30 s (scan only) |
| Phase B — confirm-delete | (default) | 27 deleted | ~1 m 34 s (~94 s) |
| Phase B — confirm-delete | analytics | 0 | ~0 s (immediate no-op) |
| **Total** | — | **27 migrated + 27 deleted** | **~3 m 42 s (~222 s)** |

### 5.2 Materially-measured resources only (non-zero source docs)

| Resource | Phase | DB | Source docs | Elapsed (s) | Effective writes/sec |
|----------|-------|----|-------------|-------------|---------------------|
| alert_configurations | A (copy) | (default) | 14 | ~40 | ~0.35 |
| alert_configurations | B (delete) | (default) | 14 | ~37 | ~0.38 |
| monitoring_topics | A (copy) | (default) | 3 | ~10 | ~0.30 |
| monitoring_topics | B (delete) | (default) | 3 | ~10 | ~0.30 |
| strategy_docs | A (copy) | (default) | 10 | ~34 | ~0.29 |
| strategy_docs | B (delete) | (default) | 10 | ~33 | ~0.30 |

**Peak observed rate:** ~0.38 docs/sec (`alert_configurations` Phase B), equivalent to **~1,316× below the 500 writes/sec PRD ceiling** (500 ÷ 0.38 ≈ 1,316).

**Throughput driver:** latency was dominated by laptop→`nam5` round-trip serial RPCs, not the 500 writes/sec batch rate limiter. The migration script processes documents sequentially (one Firestore read + one write RPC per doc); no batching was triggered at staging volume.

---

## 6. Implications for Production

The staging run's 27 source documents completed in under 4 minutes total. **At staging volume, the 500 writes/sec ceiling was irrelevant** — the per-document round-trip latency (~2–3 s) was the binding constraint, not the rate limiter.

**Scaling projection for production:** if the production database has on the order of 1 000–100 000 documents per active account (plausible for `strategy_docs` and `alert_configurations` at full utilization), the migration script's sequential-RPC pattern will scale roughly linearly with document count at a similar per-doc latency. At 1 000 docs, a single resource pass could take ~1–3 hours; at 100 000 docs, 100–300 hours — which would require either:

1. **Batched parallel processing** (extend `migrate_to_shape_b.py` to process multiple accounts concurrently, up to the 500 writes/sec ceiling per collection), or
2. **Overnight scheduling** per PRD §7 Risks row 2 ("budget time; run overnight if needed"), or
3. **Account-by-account segmentation** using a future `--account=<id>` flag (noted as a potential enhancement in DM-PRD-00 §8 Open Questions).

**Recommended ops trigger for the production cutover:** monitor per-resource effective writes/sec during the production dry-run. If any resource approaches **400 docs/sec** (80% of the 500/sec ceiling), switch from sequential to batched mode before running `--confirm-delete`. At staging volume (0.29–0.38 docs/sec), there was no need to apply this watch — it is a production-cutover concern only.

The `analytics` database will remain a structural no-op for production as well (analytics data already lives under Shape B paths from the DM-02 migration).

---

## 7. Cross-references

| Reference | Location | Relationship |
|-----------|----------|-------------|
| DM-PRD-06 §4.3 step 5 | [`./DM-PRD-06-verification-and-cutover.md`](../projects/DM-PRD-06-verification-and-cutover.md) | Primary PRD requirement: "Document staging run timing (how long each resource took; helps future ops)" |
| DM-PRD-06 §5 AC-5 | Same file | "Staging migration timing report is posted (a short comment in the DESIGN-REVIEW-LOG entry, or a separate doc linked from it)" — this file satisfies AC-5 via the "separate doc" path |
| DM-PRD-06 §7 Risks row 2 | Same file | "Staging migration runs slower than dev (more data) … timing scales with data volume" — §6 above addresses this |
| DM-60 run-log | `docs/design/components/data-management/runs/DM-60-staging-migration-execute.md` (branch `docs/DM-60-staging-migration-execute`, PR #615 — not yet merged to `main`) | Source of per-resource timing data consumed by this report |
| DM-63 (DESIGN-REVIEW-LOG "migration complete" entry) | DM-63 Linear issue | Consumer of this report — cross-link this file per PRD §5 AC-5. **Note:** DM-PRD-06 §4.4 refers to this as "Review 16" but Review 16 already exists in `DESIGN-REVIEW-LOG.md` (Feature Flags component, 2026-04-20). The next available number at time of writing is **Review 33**. DM-63 should use that number. |
| DESIGN-REVIEW-LOG Review 15 | [`../../../DESIGN-REVIEW-LOG.md`](../../../DESIGN-REVIEW-LOG.md) | Original data-model decision that this migration implements |

---

## 8. Sign-off

| Field | Value |
|-------|-------|
| Migration date | 2026-05-23 |
| Operator (command execution) | `darshan@ken-e.ai` (PO; ADC `roles/editor` on `ken-e-staging`) |
| Report author | data-management-dev-team (Dev Team agent) |
| Source data verified | DM-60 run-log §Per-resource Timing + §Phase A/B results |
| AC-5 satisfied | ✅ — timing report exists, format reusable for future ops, path available for DM-63 cross-link |
| Downstream consumer | DM-63 (DESIGN-REVIEW-LOG "migration complete" entry, Review 33) — cross-link at: `docs/design/components/data-management/runs/DM-62-staging-migration-timing-report.md` |

---
_Produced by: data-management-dev-team | Workflow: step-2-implementing | Issue: DM-62 | 2026-05-23_
