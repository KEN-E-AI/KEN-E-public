# DM-60 — Staging Migration Execute Run-Log

**Issue:** DM-60 — Execute staging migration with `--confirm-delete` and verify counts (covers AC-1, §4.3 step 3b)
**PRD:** DM-PRD-06 §4.3 — Staging Cutover, step 3 (phases A & B)
**Date:** __FILL_DATE__ (Phase A) · __FILL_DATE_B__ (Phase B)
**Branch:** docs/DM-60-staging-migration-execute
**Executed by:** Dev Team agent (data-management-dev-team) — template · PO (operator with staging IAM) — command execution

---

## Summary

| # | Item | Result | Notes |
|---|------|--------|-------|
| 1 | Phase A — `(default)` DB: copy + verify | __FILL_PHASE_A_DEFAULT_RESULT__ | See §Phase A — `(default)` |
| 2 | Phase A — `analytics` DB: copy + verify | __FILL_PHASE_A_ANALYTICS_RESULT__ | See §Phase A — `analytics` |
| 3 | Phase A halt-decision gate | __FILL_HALT_DECISION__ | All counts match DM-59 baseline? |
| 4 | Phase B — `(default)` DB: `--confirm-delete` | __FILL_PHASE_B_DEFAULT_RESULT__ | See §Phase B — `(default)` |
| 5 | Phase B — `analytics` DB: `--confirm-delete` | __FILL_PHASE_B_ANALYTICS_RESULT__ | See §Phase B — `analytics` |
| 6 | Per-resource timing captured | __FILL_TIMING_RESULT__ | See §Per-resource Timing |
| 7 | All ACs satisfied | __FILL_AC_RESULT__ | See §Acceptance Criteria |

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

Phase A runs the migration in copy-only mode: source collections are read and docs are written to the new `accounts/{account_id}/{resource}/...` subcollections. Source collections are **not** deleted. Both passes must exit 0 and all per-resource destination counts must match source counts before Phase B begins.

### Phase A — `(default)` database

**Command:**
```bash
GOOGLE_CLOUD_PROJECT_ID=ken-e-staging FIRESTORE_DATABASE_ID="(default)" \
  uv run python api/scripts/migrate_to_shape_b.py --all
```

**Executed at:** __FILL_PHASE_A_DEFAULT_TIMESTAMP__
**Exit code:** __FILL_PHASE_A_DEFAULT_EXIT__
**Elapsed (wall-clock):** __FILL_PHASE_A_DEFAULT_ELAPSED__

**Per-resource results:**

| Resource | Source colls | Source docs | Dest docs | Status | Elapsed (s) |
|----------|-------------|-------------|-----------|--------|-------------|
| agent_analytics | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| alert_configurations | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| cost_aggregations | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| monitoring_topics | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| performance_profiles | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| strategy_audit | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| strategy_docs | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| strategy_processing_state | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |

<details>
<summary>Full stdout (paste here)</summary>
<pre>
__FILL_PHASE_A_DEFAULT_STDOUT__
</pre>
</details>

<details>
<summary>Full stderr (paste here)</summary>
<pre>
__FILL_PHASE_A_DEFAULT_STDERR__
</pre>
</details>

---

### Phase A — `analytics` database

Expected outcome: all resources report 0 source collections and 0 source docs (confirmed empty by DM-59 dry-run — Ken's manual cleanup). Every resource exits `VERIFIED` as a structural no-op.

**Command:**
```bash
GOOGLE_CLOUD_PROJECT_ID=ken-e-staging FIRESTORE_DATABASE_ID="analytics" \
  uv run python api/scripts/migrate_to_shape_b.py --all
```

**Executed at:** __FILL_PHASE_A_ANALYTICS_TIMESTAMP__
**Exit code:** __FILL_PHASE_A_ANALYTICS_EXIT__
**Elapsed (wall-clock):** __FILL_PHASE_A_ANALYTICS_ELAPSED__

**Per-resource results:**

| Resource | Source colls | Source docs | Dest docs | Status | Elapsed (s) |
|----------|-------------|-------------|-----------|--------|-------------|
| agent_analytics | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| alert_configurations | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| cost_aggregations | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| monitoring_topics | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| performance_profiles | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| strategy_audit | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| strategy_docs | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| strategy_processing_state | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |

<details>
<summary>Full stdout (paste here)</summary>
<pre>
__FILL_PHASE_A_ANALYTICS_STDOUT__
</pre>
</details>

<details>
<summary>Full stderr (paste here)</summary>
<pre>
__FILL_PHASE_A_ANALYTICS_STDERR__
</pre>
</details>

---

## Phase A Halt-Decision Gate

**⚠️ DO NOT run Phase B until all items below are checked.**

| Check | Expected | Actual | Pass? |
|-------|----------|--------|-------|
| `(default)` DB: all per-resource destination counts == source counts | Yes | __FILL__ | __FILL__ |
| `(default)` DB: exit code = 0 | 0 | __FILL_PHASE_A_DEFAULT_EXIT__ | __FILL__ |
| `analytics` DB: all per-resource source counts = 0 | Yes | __FILL__ | __FILL__ |
| `analytics` DB: exit code = 0 | 0 | __FILL_PHASE_A_ANALYTICS_EXIT__ | __FILL__ |
| `(default)` source counts within ±2 docs of DM-59 baseline (allowing for app writes during window) | Yes | __FILL__ | __FILL__ |

**Gate decision:** __FILL_GATE_DECISION__ (PROCEED to Phase B / HALT — see below)

> **If any check fails:** halt Phase B. Do NOT run `--confirm-delete`. File a follow-up issue against the responsible team (DM-PRD-01–DM-PRD-04 owners) per AC-5 ("Any verification failure halts the run and is filed against the responsible team"). Tag DM-60 with `escalation` label and @mention PO. Document the failure here and leave this file with its remaining `__FILL_*__` placeholders as evidence.

---

## Phase B — Source-Collection Deletion (`--confirm-delete`)

Phase B runs only after the halt-decision gate above is marked PROCEED. Each invocation copies (idempotent with Phase A), then deletes source collections (gated on `--confirm-delete --yes`). `--yes` skips the interactive prompt and is safe to use because the verification gate inside `cmd_all` still runs before any deletion proceeds (L184–L186 of `migrate_to_shape_b.py` — deletion is only reached after `migrate_resource` returns `EXIT_SUCCESS`).

### Phase B — `(default)` database

**Command:**
```bash
GOOGLE_CLOUD_PROJECT_ID=ken-e-staging FIRESTORE_DATABASE_ID="(default)" \
  uv run python api/scripts/migrate_to_shape_b.py --all --confirm-delete --yes
```

**Executed at:** __FILL_PHASE_B_DEFAULT_TIMESTAMP__
**Exit code:** __FILL_PHASE_B_DEFAULT_EXIT__
**Elapsed (wall-clock):** __FILL_PHASE_B_DEFAULT_ELAPSED__

**Per-resource deletion results:**

| Resource | Source colls deleted | Docs deleted | Malformed sources | Status | Elapsed (s) |
|----------|---------------------|-------------|-------------------|--------|-------------|
| agent_analytics | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| alert_configurations | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| cost_aggregations | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| monitoring_topics | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| performance_profiles | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| strategy_audit | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| strategy_docs | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| strategy_processing_state | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |

**Post-deletion residue check:**

```bash
# Should return empty for all migrated collection names
gcloud firestore collections list \
  --project=ken-e-staging \
  --database="(default)" \
  2>/dev/null | grep -E '^(alert_configurations|monitoring_topics|strategy_docs|strategy_audit|strategy_processing_state|agent_analytics|cost_aggregations|performance_profiles)$'
```

**Residue check output:** __FILL_RESIDUE_CHECK_DEFAULT__ _(empty = pass)_

<details>
<summary>Full stdout (paste here)</summary>
<pre>
__FILL_PHASE_B_DEFAULT_STDOUT__
</pre>
</details>

<details>
<summary>Full stderr (paste here)</summary>
<pre>
__FILL_PHASE_B_DEFAULT_STDERR__
</pre>
</details>

---

### Phase B — `analytics` database

Expected outcome: 0 deletions across every resource (empty-baseline — same as Phase A analytics pass). Structural no-op.

**Command:**
```bash
GOOGLE_CLOUD_PROJECT_ID=ken-e-staging FIRESTORE_DATABASE_ID="analytics" \
  uv run python api/scripts/migrate_to_shape_b.py --all --confirm-delete --yes
```

**Executed at:** __FILL_PHASE_B_ANALYTICS_TIMESTAMP__
**Exit code:** __FILL_PHASE_B_ANALYTICS_EXIT__
**Elapsed (wall-clock):** __FILL_PHASE_B_ANALYTICS_ELAPSED__

**Per-resource deletion results:**

| Resource | Source colls deleted | Docs deleted | Malformed sources | Status | Elapsed (s) |
|----------|---------------------|-------------|-------------------|--------|-------------|
| agent_analytics | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| alert_configurations | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| cost_aggregations | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| monitoring_topics | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| performance_profiles | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| strategy_audit | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| strategy_docs | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| strategy_processing_state | __FILL__ | __FILL__ | __FILL__ | __FILL__ | __FILL__ |

<details>
<summary>Full stdout (paste here)</summary>
<pre>
__FILL_PHASE_B_ANALYTICS_STDOUT__
</pre>
</details>

<details>
<summary>Full stderr (paste here)</summary>
<pre>
__FILL_PHASE_B_ANALYTICS_STDERR__
</pre>
</details>

---

## Per-resource Timing

Aggregated from Phase A and Phase B results above. Feeds DM-62 timing report directly.

| Resource | Phase | DB | Source docs | Elapsed (s) | Effective writes/sec | Within 500/sec ceiling? |
|----------|-------|----|-------------|-------------|----------------------|------------------------|
| agent_analytics | A (copy) | (default) | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| agent_analytics | A (copy) | analytics | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| agent_analytics | B (delete) | (default) | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| agent_analytics | B (delete) | analytics | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| alert_configurations | A (copy) | (default) | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| alert_configurations | A (copy) | analytics | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| alert_configurations | B (delete) | (default) | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| alert_configurations | B (delete) | analytics | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| cost_aggregations | A (copy) | (default) | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| cost_aggregations | A (copy) | analytics | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| cost_aggregations | B (delete) | (default) | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| cost_aggregations | B (delete) | analytics | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| monitoring_topics | A (copy) | (default) | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| monitoring_topics | A (copy) | analytics | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| monitoring_topics | B (delete) | (default) | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| monitoring_topics | B (delete) | analytics | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| performance_profiles | A (copy) | (default) | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| performance_profiles | A (copy) | analytics | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| performance_profiles | B (delete) | (default) | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| performance_profiles | B (delete) | analytics | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| strategy_audit | A (copy) | (default) | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| strategy_audit | A (copy) | analytics | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| strategy_audit | B (delete) | (default) | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| strategy_audit | B (delete) | analytics | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| strategy_docs | A (copy) | (default) | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| strategy_docs | A (copy) | analytics | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| strategy_docs | B (delete) | (default) | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| strategy_docs | B (delete) | analytics | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| strategy_processing_state | A (copy) | (default) | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| strategy_processing_state | A (copy) | analytics | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| strategy_processing_state | B (delete) | (default) | __FILL__ | __FILL__ | __FILL__ | __FILL__ |
| strategy_processing_state | B (delete) | analytics | __FILL__ | __FILL__ | __FILL__ | __FILL__ |

> **Note for DM-62:** for zero-doc resources, `Elapsed` and `Effective writes/sec` are both 0. For resources where source docs > 0, `Effective writes/sec` = `Source docs / Elapsed`. If any resource exceeded 10 s elapsed with > 0 source docs, annotate as a "watch this in prod" note in DM-62.

---

## Acceptance Criteria

| AC | Criterion | Status | Evidence |
|----|-----------|--------|---------|
| AC-1 | Staging migration executes successfully across all registered resources | __FILL__ | Phase A + Phase B exit codes above |
| AC-2 | Phase A: source / destination per-resource counts match | __FILL__ | §Phase A tables + halt-decision gate |
| AC-3 | Phase B: source collections deleted; new Shape B paths populated | __FILL__ | §Phase B tables + residue check |
| AC-4 | Per-resource elapsed time captured for issue DM-62's report | __FILL__ | §Per-resource Timing table |
| AC-5 | Any verification failure halts the run and is filed against the responsible team | __FILL__ | Halt-decision gate (no halt = pass; halt = follow-up filed) |

---

## Sign-off

| Field | Value |
|-------|-------|
| Date — Phase A | __FILL_DATE__ |
| Date — Phase B | __FILL_DATE_B__ |
| Operator — command execution | __FILL_OPERATOR__ (PO / staging IAM) |
| Agent — template + run-log ingestion | data-management-dev-team |
| Pre-condition: DM-58 (deploy) | Done ✅ — rev `ae7d3b99` (re-confirmed at window-open) |
| Pre-condition: DM-59 (dry-run) | Done ✅ — baseline counts in §Pre-conditions above |
| Ghost-subcollection note | Acknowledged — harmless; DM-PRD-05 `recursive_delete` reconciles |
| Downstream issues unblocked by this run | DM-61 (Phase 6 staging checklist), DM-62 (timing report), DM-63 (Review 16), DM-65 (README status flip) |

---
_Produced by: data-management-dev-team (template) | Workflow: step-2-implementing | Issue: DM-60_
