# Shape A → B Migration Rollback Runbook

**Scope:** the `migrate_to_shape_b.py --all --confirm-delete` cutover against any environment (dev / staging / production). Specific values below assume `ken-e-production` because this runbook exists primarily for DM-PRD-08 (the prod cutover); substitute the matching project/database for other envs.

**Authoring context:** authored as part of DM-93 in the DM-PRD-08 series. Required to exist before the destructive `--confirm-delete` step (DM-97) opens its window. References [DM-PRD-08 §5 (Rollback plan)](../../docs/design/components/data-management/projects/DM-PRD-08-production-cutover.md#5-rollback-plan), [DM-PRD-08 §8 (Open questions)](../../docs/design/components/data-management/projects/DM-PRD-08-production-cutover.md#8-risks--open-questions), and the staging precedent at [`docs/design/components/data-management/projects/DM-PRD-06-verification-and-cutover.md` §4.3](../../docs/design/components/data-management/projects/DM-PRD-06-verification-and-cutover.md).

**Decision authority for `--confirm-delete`:** **Ken Williams (PO) alone.** No other engineer authorises the destructive step. If Ken is unavailable and the cutover window has opened, **abort**; do not improvise an alternative authoriser.

---

## 0. Quick reference — when to use which rollback layer

| Failure observed | Layer to invoke | Section |
|---|---|---|
| Phase A reported a count mismatch on any resource | Exit script + investigate; no rollback needed (source untouched) | §2 |
| PO declines at the halt-gate after dry-run review | Exit script; document ABORT decision | §3 |
| Phase B (`--confirm-delete`) partial failure mid-run | Re-run is idempotent (already-deleted resources are no-ops); if irrecoverable, escalate to §4 | §4 |
| Phase B succeeded but post-Phase-B verification fails | Restore via Firestore PITR (≤7 days) or GCS import | §4 |
| Wrong-environment migration (e.g. ran against prod with staging intent) | Same as Phase B recovery — restore from PITR or GCS export | §4 |
| Cloud Run revision serving Shape A code after Shape B data lands | Re-deploy Shape B-aware revision; **do NOT pin to a Shape A revision unless the data is also restored** | §5 |

---

## 1. Pre-cutover safety net — GCS export

A managed Firestore export to GCS is the long-term restore substrate. Taken in DM-95 (a hard pre-condition of DM-97 per its `blockedBy` edge).

### 1.1 IAM requirements (operator running the export)

- `roles/datastore.importExportAdmin` on the source project (`ken-e-production`)
- `roles/storage.objectCreator` on the destination bucket (`gs://ken-e-production-backups/`)
- Bucket must exist before the export is invoked (see §1.2 for bucket creation)

### 1.2 Destination bucket

**Path convention:** `gs://ken-e-production-backups/pre-shape-b-cutover-<YYYY-MM-DD>/` (one prefix per cutover attempt, dated to avoid clobbering prior exports).

**Bucket setup (one-time per env):**

```bash
# CORRECTED 2026-05-27 from DM-PRD-08 §4.2's `-l nam5` — that's a Firestore
# multi-region string and is rejected by GCS (`BadRequestException: 400 The
# specified location constraint is not valid`). Use `-l us` for the GCS
# equivalent multi-region (functionally identical geo-redundancy).
gsutil mb -p ken-e-production -l us gs://ken-e-production-backups/

# Apply 90-day Object Lifecycle Management (resolves DM-PRD-08 §8 open
# question — see §1.4 below).
cat > /tmp/lifecycle.json <<'EOF'
{"rule": [{"action": {"type": "Delete"}, "condition": {"age": 90}}]}
EOF
gsutil lifecycle set /tmp/lifecycle.json gs://ken-e-production-backups/
```

### 1.3 Export command

```bash
DATE=$(date +%Y-%m-%d)
gcloud firestore export gs://ken-e-production-backups/pre-shape-b-cutover-${DATE}/ \
  --project=ken-e-production --database='(default)'
```

**Notes:**

- Export the `(default)` database **only** (per DM-PRD-08 §4 AC-4: Shape A→B touches only `(default)`; the `analytics` database carries unrelated data).
- Capture the operation ID immediately into a shell variable to defend against losing it in scrollback:

  ```bash
  OP_ID=$(gcloud firestore operations list --project=ken-e-production \
    --filter="metadata.outputUriPrefix:pre-shape-b-cutover-${DATE}" \
    --format='value(name)' --limit=1)
  echo "Export op id: $OP_ID"
  ```

- Poll until done (typical: 5-10 min for ~34 docs; longer for prod-scale data):

  ```bash
  gcloud firestore operations describe "$OP_ID" --project=ken-e-production
  ```

  Look for `done: true` with no `error:` field. Record the operation ID, prefix path, and the resulting object count in the cutover run log.

### 1.4 Bucket lifecycle decision

**Resolved (DM-PRD-08 §8 open question):** 90-day Object Lifecycle Management delete. Rationale:

- Firestore PITR provides a ~7-day in-database rollback window automatically; the GCS export is the longer-tail substrate.
- 90 days covers the realistic "we missed something" window for a one-time migration of this scope (~34 docs in prod, no live customers). The cost of retaining is negligible against the cost of needing it.
- If a real production-data incident surfaces beyond 90 days, the migration itself can be re-run from current state — the GCS export's role is bounded to immediate-post-cutover incident response.
- **Alternative considered + rejected:** indefinite retention. Adds ongoing GCS billing for a backup that loses operational relevance once Phase 6 verification has held for >30 days.

### 1.5 Restore from this GCS export

```bash
# Restores into a DIFFERENT database (do NOT import directly over a live
# (default) — import into a sibling like (default)-restore-<date>, then
# Cloud Console-rename or copy collections back over once you've verified.)
DATE=2026-05-28  # the date of the actual export prefix (see the DM-PRD-08 run log)
gcloud firestore import gs://ken-e-production-backups/pre-shape-b-cutover-${DATE}/ \
  --project=ken-e-production --database="(default)-restore-${DATE}"
```

For a same-database import (which overwrites): see Google's [Firestore import-export docs](https://cloud.google.com/firestore/docs/manage-data/export-import) for the exact `--collection-ids` flag and existing-data-handling caveats. Typical recovery time: 10-60 min depending on volume.

---

## 2. Phase A (copy + verify) — non-destructive abort

Phase A is the copy-only pass. Source collections are read; documents are written to the new `accounts/{account_id}/{resource}/...` subcollections. **Source collections are never deleted in Phase A.**

### 2.1 What "Phase A failure" means

Phase A fails when `migrate_to_shape_b.py --all` (no `--confirm-delete`) returns a non-zero exit code OR a per-resource line shows `Source doc count != Destination doc count`. Either condition means the script will refuse to proceed to Phase B.

### 2.2 Recovery

**There is no rollback to perform.** The source is unchanged. The destination may have partial Shape-B writes (the script aborts on first verification failure), but those writes are inert until the application is told to read from them.

Steps:

1. Capture the failing stdout/stderr in full to the run log.
2. Investigate root cause (most common: a malformed source document, a network glitch causing partial writes, or a permissions gap).
3. If the failure was transient (e.g. network), re-run `--all` (no `--confirm-delete`). The destination is treated as authoritative for already-migrated docs; the script re-verifies counts and only logs `Copied 0` for already-present rows.
4. If the failure is persistent, file a follow-up issue against the responsible team (DM-PRD-05 owns the migration script). Do **NOT** proceed to Phase B until Phase A returns a clean exit 0 with all resources VERIFIED.

### 2.3 Cleaning up partial Phase A writes

In rare cases (e.g. you intend to retry Phase A from a clean slate after a script change), use `firestore.recursive_delete` on the partial `accounts/{account_id}/{resource}/...` subcollections. The source is untouched, so this is a write-only cleanup — no data loss risk to the source.

---

## 3. Halt-gate — PO go/no-go between Phase A and `--confirm-delete`

The halt-gate is the irreversibility boundary. Phase A has succeeded; the destination matches the source; Phase B will delete the source. The PO reviews the dry-run counts and authorises one of two paths.

### 3.1 What gets reviewed

The operator presents the post-Phase-A dry-run output:

```bash
GOOGLE_CLOUD_PROJECT_ID=ken-e-production FIRESTORE_DATABASE_ID='(default)' \
  uv run python scripts/migrate_to_shape_b.py --all --dry-run
```

The PO compares the per-resource Source doc count + Destination doc count against:
- The pre-cutover inventory recorded in DM-PRD-08 §1 (or the latest equivalent paragraph for re-runs)
- The expectation that source and destination match exactly for every resource
- The expectation that `notifications` and `usage_records` are NOT in the candidate list (Shape C carve-out; must not be migrated)

### 3.2 PROCEED — written-record template

The PROCEED decision is recorded in the cutover run log as a quoted block:

```
HALT-GATE DECISION: PROCEED
Decided by: Ken Williams (PO)
Decided at: <YYYY-MM-DDTHH:MM:SSZ>
Phase A counts reviewed:
  alert_configurations: source=N, dest=N
  monitoring_topics:    source=N, dest=N
  strategy_docs:        source=N, dest=N
  (... other resources, all source==dest ...)
Reconciliation: matches pre-cutover inventory (DM-PRD-08 §1).
Authorisation: proceed to --confirm-delete on (default) database.
```

This block is also pasted as a comment on the Linear issue covering the destructive step (DM-97) so the audit trail is durable in Linear, not just in the run-log file.

### 3.3 ABORT — written-record template

The ABORT decision short-circuits the cutover. No destructive command is run.

```
HALT-GATE DECISION: ABORT
Decided by: Ken Williams (PO)
Decided at: <YYYY-MM-DDTHH:MM:SSZ>
Reason: <one-line summary of why — count drift, unexpected resource, etc.>
Next step: <follow-up issue filed / re-run scheduled for ... / cutover cancelled>
```

The pre-cutover GCS export taken in DM-95 remains in place (the 90-day OLM applies regardless of whether the cutover proceeds). The destination Shape-B subcollections written during Phase A can be cleaned up via `firestore.recursive_delete` if the abort is permanent; otherwise they remain harmless until a future Phase A re-runs (which will treat them as already-present and re-verify counts).

---

## 4. Phase B (destructive) — recovery

Phase B is reached only when the halt-gate authorises PROCEED. The script deletes source collections in batched `batch.delete(doc.reference)` calls per resource. The destination Shape-B writes are untouched by this phase.

### 4.1 What "Phase B failure" means

Three failure modes:

- **Network/permission error mid-batch.** Script may exit non-zero with partial source deletion (some docs deleted, others remain).
- **Idempotent re-run misread.** Re-running `--confirm-delete` after a partial failure is **safe** — re-copy returns "Copied 0" (dest already present), re-verify confirms counts, then delete proceeds against whatever source remains. Misreading the re-run as "it deleted more docs this time" is a misinterpretation; it deleted the residual.
- **Post-cutover verification fail.** Phase B exited 0, but DM-101's Phase 6 checklist (§4.3) catches residual Shape A collections, missing `notifications`/`usage_records`, or stranded `accounts.*` fields on org docs.

### 4.2 Recovery via Firestore PITR (≤7-day window)

PITR is the fastest recovery — restores the entire database to a point in time.

```bash
# Choose a timestamp from BEFORE the destructive Phase B started. The DM-97
# run log captures the start timestamp; if PITR is needed, look there.
RESTORE_TIMESTAMP="2026-05-27T07:00:00Z"   # placeholder — use real value
gcloud firestore databases restore \
  --source-database=projects/ken-e-production/databases/'(default)' \
  --destination-database='(default)-restored' \
  --snapshot-time=${RESTORE_TIMESTAMP} \
  --project=ken-e-production
```

**Notes:**

- Restore goes into a NEW database (`(default)-restored`), never overwrites the live one. After restore, either point the application at the new database (via env var or Cloud Run revision update) OR copy collections back via a one-off script.
- The 7-day PITR window is automatic — no setup required.
- Recovery time: typically 10-30 min for prod-scale data.

### 4.3 Recovery via GCS import (>7-day window or PITR unavailable)

```bash
DATE=2026-05-28  # date of the actual pre-cutover export prefix (see the DM-PRD-08 run log)
gcloud firestore import gs://ken-e-production-backups/pre-shape-b-cutover-${DATE}/ \
  --project=ken-e-production --database='(default)-restored'
```

Same NEW-database pattern. Recovery time: 30-90 min depending on volume.

### 4.4 After restore — application reconciliation

Restoring Shape A data leaves a coherence problem: the deployed application code is Shape B-aware and will issue queries against `accounts/{account_id}/{resource}/...` paths that no longer exist post-restore. Two paths:

- **Fix-forward (recommended):** keep the Shape B data we WROTE (Phase A already populated the destination); the restore is a sanity-check substrate, not the live data. Investigate what Phase 6 verification failed, fix the residue, and proceed.
- **Code rollback (incoherent — only as a last resort):** see §5. A Shape A application + Shape B data = wrong queries. Don't pin to a Shape A revision unless the data is also restored to Shape A; that's a coordinated multi-step recovery.

---

## 5. Code rollback — Cloud Run revision pin

A code-only rollback (Cloud Run revision pin without data restore) is **incoherent** because the application reads from one shape and the data is in the other. Document this here so future operators don't try it as a quick fix.

If a coordinated code+data rollback is genuinely needed:

```bash
# 1. Find the prior (Shape A-compatible) revision
gcloud run revisions list --service=kene-api-production \
  --region=us-central1 --project=ken-e-production \
  --format='table(name,creationTimestamp,active)' --limit=10

# 2. Restore the Shape A data via §4.2 or §4.3 first
# (DO NOT skip this step.)

# 3. Pin traffic to the prior revision
PRIOR_REV=kene-api-production-XXXXX   # placeholder — use real value
gcloud run services update-traffic kene-api-production \
  --to-revisions=${PRIOR_REV}=100 \
  --region=us-central1 --project=ken-e-production
```

Recovery time for the code-pin step alone: ~5 min (the data restore in step 2 dominates the wall-clock).

---

## 6. Abort criteria (any single condition triggers halt)

The cutover halts (no Phase B run, or no DM-102 close-out) when any of these conditions surfaces:

1. **Phase A source/destination count mismatch on any resource.** Recovery: §2.2.
2. **`audit_org_accounts_field.py --confirm-delete --dry-run` reports any org with `action="error"`** — the Shape-D safety check fired, meaning the `accounts` field on an org doc is no longer the dead pre-Shape-D list residue (it might be live data shape D has migrated into). DM-98 halts; do not run the real cleanup. Investigate the affected org manually.
3. **DM-92-style residue cleanup script errors on any of the three orgs** (`equity-trust`, `healthway`, `open-lines`). Recovery: investigate the error per-org; if data is in an unexpected shape, halt and brief Ken before touching it.
4. **Phase 6 verification (DM-101 §4.3) fails any item against the post-Phase-A or post-cleanup state.** Recovery: file a follow-up issue against the team responsible for the failing check; do not flip DM-PRD-08 status to Complete (DM-102) until green.
5. **Operator authentication lapse mid-execution** (e.g. ADC expired). Recovery: re-authenticate (`gcloud auth application-default login`), re-verify prod IAM tests pass, resume from the last completed step (each Linear issue's closing comment is the canonical resume point).

---

## 7. Decision authority

**`--confirm-delete` is authorised by Ken Williams (PO) alone.** No other engineer — including the operator running the script, including DM-PRD-08 issue assignees — has authority to invoke Phase B without Ken's explicit go.

For DM-PRD-08 specifically, Ken delegated PO authority to Darshan Valia (operator) for the cutover via the 2026-05-27 message ("you can run this any time…"). This delegation is documented in the cutover run log and the Linear DM-PRD-08 project comment; it is project-specific and does NOT generalise to future cutovers without re-delegation.

The halt-gate decision (PROCEED / ABORT) is captured in the run log per §3.2 / §3.3 as a written record, regardless of whether the authoriser is Ken or a delegated PO-proxy.

---

## 8. Sign-off

| Field | Value |
|---|---|
| Authored by | Darshan Valia (operator) as part of DM-93 |
| Date authored | 2026-05-27 |
| Authoring PR | (filled in once the PR opens) |
| PO sign-off | (filled in by Ken or PO-proxy review) |
| First used by | DM-95 / DM-97 (DM-PRD-08 production cutover) |
| Owner team | data-management |
| Review cadence | After each successful production-migration use; mark stale if not used within 12 months and the underlying scripts have shipped >3 minor changes since |

---

**Related operational refs:**

- DM-60 staging run log (operational precedent): [`docs/design/components/data-management/runs/DM-60-staging-migration-execute.md`](../../docs/design/components/data-management/runs/DM-60-staging-migration-execute.md)
- DM-PRD-08 (this cutover's PRD): [`docs/design/components/data-management/projects/DM-PRD-08-production-cutover.md`](../../docs/design/components/data-management/projects/DM-PRD-08-production-cutover.md)
- DM-PRD-06 staging cutover PRD: [`docs/design/components/data-management/projects/DM-PRD-06-verification-and-cutover.md`](../../docs/design/components/data-management/projects/DM-PRD-06-verification-and-cutover.md)
- Migration script source: `api/scripts/migrate_to_shape_b.py` + `api/scripts/_migrate_shape_b/resources.py`
- Org-accounts-residue audit script: `api/scripts/audit_org_accounts_field.py` (DM-92 deliverable, used by DM-98)
