# DM-PRD-08 — Production Cutover

**Status:** Backlog
**Owner team:** Platform / Infra (PO: Ken Williams; execution: Darshan Valia)
**Blocked by:** DM-PRD-06
**Parallel with:** —
**Blocks:** —
**Estimated effort:** 1 day (cutover window itself ~30–45 min wall-clock)

---

## 1. Context

Terminal cutover project. Promotes the Shape A→B migration from staging (DM-PRD-06) to production (`ken-e-production`). DM-PRD-06 was explicitly staging-scoped — its §Out of scope stated *"Production cutover — no production users exist, so there is nothing to cut over in prod until launch. This project's 'staging cutover' is the end-state until production is provisioned."* That assumption now needs revisiting: the same Shape A residue that motivated staging cleanup (DM-92) exists in prod today, and downstream Release 1 work (and any pre-launch dogfooding) benefits from prod being on Shape B before further feature work lands.

A 2026-05-25 read-only inventory of `ken-e-production / (default)` confirmed the production environment still has **no real customer accounts**: three demo-fixture organizations (`equity-trust`, `healthway`, `open-lines` — the same names as staging), seven sparse user docs, and `accounts/` empty (0 docs). The actual source-collection footprint to migrate is ~34 docs across `strategy_docs_acc_*` (4 collections), `alert_configurations`, `monitoring_topics`, and one literal `strategy_docs_<test_account_id>` placeholder collection. The same three orgs carry the dead `accounts`-list field residue surfaced by DM-92 in staging.

No new code is produced here. The work is **export, deploy, cut over, clean up residue, verify, document, and ship a rollback runbook**. Per [Review 15](../../../DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1), the migration remains a **single-cutover per environment** — no dual-write, no version shim, no downtime window — because there are still no real users. The destructive step (`--confirm-delete`) is gated by a halt-gate where the PO explicitly confirms Phase A counts before authorising deletion.

## 2. Scope

### In scope

- Author a rollback runbook at `deployment/runbooks/shape-b-migration-rollback.md` covering pre-cutover GCS export, Phase A non-destructive abort, halt-gate go/no-go, Phase B PITR / import recovery, code rollback via Cloud Run revision pin, and abort criteria.
- Schedule a prod maintenance window and deploy the merged DM-PRD-00–05 code to `ken-e-production`.
- Take a pre-cutover managed Firestore export to `gs://ken-e-production-backups/pre-shape-b-cutover-<YYYY-MM-DD>/` as the belt-and-suspenders backup.
- Run `migrate_to_shape_b.py --all --env=production --dry-run`, inspect output, then execute the real migration with `--confirm-delete` after the halt-gate go/no-go.
- Clean the dead `accounts` list field from the three prod org docs (`equity-trust`, `healthway`, `open-lines`) using DM-92's audit/cleanup script.
- Delete the orphan `strategy_docs_<test_account_id>` placeholder collection (a literal-string artifact that doesn't correspond to any real account).
- Run the Phase 6 verification checklist (mirroring DM-PRD-06 §4.1 + §4.2) against `ken-e-production`.
- Document a prod migration timing report.
- Add a new Review entry to `docs/design/DESIGN-REVIEW-LOG.md` (next available number) cross-linking to Review 15 and the DM-PRD-06 Review entry, and flip DM-PRD-08 status in both `docs/design/components/data-management/README.md` §5.1 and `docs/design/components/PROJECT-PLANNER.md`.

### Out of scope

- Any code changes (all owned by DM-PRD-00–DM-PRD-05).
- Re-running staging cutover work (closed by DM-PRD-06).
- DM-PRD-07 (Roles, Members, Audit Substrate) — separate workstream, not blocked by or blocking this project.
- Customer comms / status page — there are no customers.
- Performance load test or failover drill — production is empty; deferred to a future production-readiness project closer to launch.

## 3. Dependencies

- **DM-PRD-06:** staging cutover complete, Phase 6 verification passed, Review entry landed, README rollup applied. (As of 2026-05-25 these are all Done: DM-58 through DM-92.)
- DM-PRD-00–05 code already shipped to production via normal CD pipeline (or will be by issue #2's deploy step).
- Production GCP project `ken-e-production` with Firestore (`(default)` + `analytics` databases) provisioned.
- Production service account with appropriate IAM for running migration (Firestore read/write + delete), taking GCS exports (`roles/datastore.importExportAdmin`), and writing to `gs://ken-e-production-backups/`.
- DM-92's `cleanup_old_accounts_field` script (PR #641) merged and available on the deployed prod revision.

## 4. Verification & execution checklist

### 4.1 Pre-cutover prep (done before maintenance window opens)

- [ ] Rollback runbook authored at `deployment/runbooks/shape-b-migration-rollback.md` and reviewed by PO.
- [ ] DM-PRD-06 confirmed signed off (Review entry visible in `DESIGN-REVIEW-LOG.md`; README §5.1 shows DM-PRD-00–06 Complete).
- [ ] Read-only re-inventory of `ken-e-production / (default)` re-confirms three-org residue + ~34 source-collection docs (script preserved in the runbook).
- [ ] `gs://ken-e-production-backups/` bucket exists with `roles/storage.objectCreator` granted to the operator's account (or to a dedicated migration SA).

### 4.2 Cutover window

1. **Deploy.** Confirm the deployed revision on `kene-api-production` includes the merged DM-PRD-00–05 code (specifically: `migrate_to_shape_b.py`, the `_migrate_shape_b/` module, `cleanup_old_accounts_field.py`, and the Shape B routers).
2. **Pre-cutover GCS export** (belt-and-suspenders backup):
   ```bash
   gcloud firestore export gs://ken-e-production-backups/pre-shape-b-cutover-$(date +%Y-%m-%d)/ \
     --project=ken-e-production --database='(default)'
   ```
   Wait for the operation to complete. Record the operation ID in the run log.
3. **Dry-run.**
   ```bash
   python api/scripts/migrate_to_shape_b.py --all --env=production --dry-run
   ```
   Inspect per-resource counts; confirm against the pre-cutover inventory.
4. **Halt-gate (PO go/no-go).** Operator presents dry-run counts to PO. PO either authorises `--confirm-delete` or aborts (no destructive action taken; source data untouched).
5. **Phase A (copy + verify) + Phase B (delete).**
   ```bash
   python api/scripts/migrate_to_shape_b.py --all --env=production --confirm-delete
   ```
   Capture per-resource elapsed time during the run.
6. **Residue cleanup.**
   - Run `cleanup_old_accounts_field` against the three orgs `equity-trust`, `healthway`, `open-lines` (dry-run first, then real).
   - Delete the orphan `strategy_docs_<test_account_id>` placeholder collection.

### 4.3 Phase 6 verification against production

Mirrors DM-PRD-06 §4.1 + §4.2, pointed at `ken-e-production`:

- [ ] No top-level `strategy_docs_*`, `strategy_audit_*`, `strategy_processing_state_*`, `agent_analytics_*`, `cost_aggregations_*`, `performance_profiles_*`, `monitoring_topics/{account_id}`, or `alert_configurations/{account_id}` remain.
- [ ] `notifications` and `usage_records` collections still exist (Shape C carve-out — must NOT be migrated).
- [ ] `organizations/{org_id}` docs (all three) have no `accounts.*` fields.
- [ ] No `strategy_docs_<test_account_id>` placeholder collection remains.
- [ ] Index budget: `gcloud firestore indexes composite list --project=ken-e-production --database='(default)' | wc -l` returns < 50.
- [ ] Codebase residue scan (DM-PRD-06 §4.2 greps) re-run against current `main` returns zero hits in source files. (No expected delta since DM-PRD-06 already verified this; this is a regression check.)

### 4.4 Documentation updates

- Document the prod migration timing report — per-resource elapsed time and total wall-clock. Format mirrors DM-62's staging report; either inline in the new Review entry or as a sibling doc at `docs/design/components/data-management/runs/DM-PRD-08-prod-migration-execute.md`.
- Add a new Review entry to `docs/design/DESIGN-REVIEW-LOG.md` (next available number; expected ~Review 32 depending on intervening reviews) titled "Shape A→B Production Cutover Complete" and cross-linking to Review 15 (the original decision) and the DM-PRD-06 staging Review entry.
- Update `docs/design/components/data-management/README.md` §5.1 — mark DM-PRD-08 Status as "Complete."
- Update `docs/design/components/PROJECT-PLANNER.md` — flip DM-PRD-08 status to `shipped`.

## 5. Rollback plan

Detailed runbook lives at `deployment/runbooks/shape-b-migration-rollback.md` (authored as the first issue of this project). Summary:

| Layer | Mechanism | Time-to-restore |
|---|---|---|
| Pre-cutover safety net | GCS export to `gs://ken-e-production-backups/pre-shape-b-cutover-<date>/` (taken in §4.2 step 2) | ~10–15 min via `gcloud firestore import` |
| Phase A (copy + verify) | Non-destructive — source untouched. Abort = exit with no rollback needed. | Instant |
| Halt-gate | PO go/no-go before `--confirm-delete`. Irreversibility boundary. | Instant |
| Phase B (deletion of source) | Firestore PITR restore (~7 day window) or GCS import from pre-cutover export | 10–60 min |
| Code | Cloud Run revision pin (re-deploy prior revision); meaningful only with concurrent data restore — practical posture is fix-forward on Shape B | ~5 min |

**Abort criteria (any one triggers halt before `--confirm-delete`):**
- Phase A source/destination count mismatch on any resource
- DM-92 residue cleanup script errors on any of the three orgs
- Phase 6 verification fails any item against the post-Phase-A state

**Decision authority:** PO (Ken Williams) alone calls go/no-go on `--confirm-delete`.

## 6. Acceptance criteria

1. **Rollback runbook exists** at `deployment/runbooks/shape-b-migration-rollback.md` and is referenced from the cutover-window issue.
2. **Pre-cutover GCS export captured** at `gs://ken-e-production-backups/pre-shape-b-cutover-<YYYY-MM-DD>/` with the operation ID recorded; restore-from-export procedure is documented in the runbook.
3. **Deploy verified** — current `kene-api-production` revision includes the merged DM-PRD-00–05 code (`migrate_to_shape_b.py`, `_migrate_shape_b/`, `cleanup_old_accounts_field.py`, and the Shape B routers).
4. **Dry-run executed and inspected** — per-resource counts captured and reconciled against the pre-cutover inventory; halt-gate documented with PO go/no-go.
5. **Production migration executes successfully across all registered resources** — Phase A + Phase B both exit 0; per-resource counts match (source = destination), source collections deleted; post-cutover dry-run reports zero source remaining.
6. **Phase 6 verification checklist (§4.3) passes** against `ken-e-production` — every checkbox green.
7. **`accounts`-field residue cleaned** — the three org docs (`equity-trust`, `healthway`, `open-lines`) have no `accounts` field after cleanup; idempotency verified (second run reports zero changes).
8. **Orphan `strategy_docs_<test_account_id>` placeholder collection deleted** from `ken-e-production`.
9. **Prod migration timing report posted** — per-resource elapsed time + total wall-clock, in a reusable format (markdown table); either inlined in the Review entry (§AC-10) or as a sibling doc.
10. **DESIGN-REVIEW-LOG entry added + DM-PRD-08 status flipped to Complete** in both the data-management README §5.1 and PROJECT-PLANNER.md.

## 7. Test plan

All verification is covered by §4.3. There is no new test code in this project.

A "red-light" test: if any of §4.3's checks fail after the migration runs, **do not** flip status to Complete (AC-10). File a follow-up issue against the responsible team (likely DM-PRD-05 or DM-92) and leave DM-PRD-08 open until green.

## 8. Risks & open questions

| Risk | Mitigation |
|---|---|
| Pre-cutover state has drifted since the 2026-05-25 inventory (new collections, new orgs) | AC-1 re-runs the inventory at window-open; if delta detected, PO decides whether to expand scope or proceed |
| Phase A succeeds but Phase B (deletion) fails partway through | Each resource's deletion is independent and idempotent. Re-run `--confirm-delete` is safe. If unrecoverable, restore from pre-cutover GCS export |
| `accounts`-field cleanup script behaves differently in prod than staging (e.g., new field shape) | Dry-run mode runs first; PO reviews diff before applying |
| Orphan `strategy_docs_<test_account_id>` collection turns out to be referenced by code somewhere (unlikely — it's a literal-string artifact) | Codebase grep for the literal string `<test_account_id>` runs as part of §4.3; zero hits expected |
| Firestore PITR window (~7 days) expires before a data issue surfaces | The pre-cutover GCS export (AC-2) is the long-term backup; no time-bound on import-from-export |
| Operator runs `--confirm-delete` against staging by mistake while authenticated for prod | `--env=production` is the only path that touches prod; staging would use `--env=staging`. Halt-gate also requires PO confirmation between dry-run and real run |

### Open questions

- **Q:** Should the GCS export bucket apply Object Lifecycle Management to auto-delete the pre-cutover export after N days? → **Defer to the rollback runbook author.** A 90-day retention is reasonable; finalise in §AC-1.
- **Q:** Should we pre-create empty `accounts/` subcollection paths for the three orgs before migration, or let Phase A create them as a side-effect? → **Let Phase A create them.** Matches staging behavior; no precedent for pre-creating.

## 9. Reference

- Parent plan: [`../multi-tenant-migration-plan.md`](../multi-tenant-migration-plan.md) §4 Phase 6, §11
- Upstream: [DM-PRD-06](./DM-PRD-06-verification-and-cutover.md)
- Related: [DM-92](https://linear.app/ken-e/issue/DM-92/delete-dead-accounts-field-from-staging-org-docs-audit-prod-for-same) — staging `accounts`-residue cleanup; this PRD picks up the deferred prod-side audit
- Migration script: `api/scripts/migrate_to_shape_b.py` + `api/scripts/_migrate_shape_b/resources.py`
- Residue cleanup script: `api/scripts/cleanup_old_accounts_field.py`
- Decision: [Review 15 in DESIGN-REVIEW-LOG](../../../DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1) — Multi-Tenant Data Model Shape
- CLAUDE.md rules in scope: (none — no code; documentation, ops, and verification only)
