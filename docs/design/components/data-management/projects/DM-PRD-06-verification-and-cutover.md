# DM-PRD-06 — Verification & Staging Cutover

**Status:** Blocked
**Owner team:** Platform / Infra (with support from Backend)
**Blocked by:** DM-PRD-05
**Parallel with:** —
**Blocks:** —
**Estimated effort:** 1 day

---

## 1. Context

Terminal verification project. Runs the full §6 checklist from the migration plan in dev, then promotes the cutover to staging. Also performs a backward-sanity scan of the whole codebase to catch any Shape A / Shape D / Shape B-like references that slipped through DM-PRD-01–DM-PRD-05.

No new code is produced here. The work is **verify, document, and cut over**.

## 2. Scope

### In scope
- Run the Phase 6 verification checklist from the migration plan in dev (`../multi-tenant-migration-plan.md` §4 Phase 6)
- Run the whole-codebase scan for residual Shape A / D / B-like references
- Promote the cutover to staging: run `migrate_to_shape_b.py --all` in staging (with appropriate service-account credentials)
- Update `DESIGN-REVIEW-LOG.md` with a "migration complete" entry (Review 16 or the next available number) cross-linking to Review 15 (the original data-model decision)
- Update each completed PRD's Status to "Complete" in `README.md`

### Out of scope
- Any code changes (all owned by DM-PRD-00–DM-PRD-05)
- Production cutover — no production users exist, so there is nothing to cut over in prod until launch. This project's "staging cutover" is the end-state until production is provisioned.
- New feature work built on Shape B — those teams start in parallel per the README

## 3. Dependencies

- **DM-PRD-05:** deletion-sweep rewrite merged and passing tests
- DM-PRD-01, DM-PRD-02, DM-PRD-03, DM-PRD-04 all complete (transitively via DM-PRD-05)
- Staging environment exists with Firestore + GCS provisioned
- Staging service account with appropriate IAM for running migration + deletion

## 4. Verification checklist

### 4.1 Dev environment

- [ ] `make lint` passes
- [ ] `pytest api/tests/ app/adk/agents/strategy_agent/tests/` passes
- [ ] Account deletion end-to-end: seed an account with data in every migrated resource (see test from DM-PRD-05), `DELETE`, verify nothing orphaned in Firestore or GCS
- [ ] Broken cross-account audit query works: `get_user_activity(user_id)` returns results for a seeded user with audit entries across ≥ 2 accounts
- [ ] Scheduler dry-run (if PRD-6 has shipped): `collection_group("project_plans").where("due_datetime_utc", "<=", now)` query runs against seeded cross-account plans and returns expected results
- [ ] Index budget: `gcloud firestore indexes composite list --project=ken-e-dev --database='(default)' | wc -l` returns < 50 (well below the 200-per-project cap)
- [ ] `organizations/{org_id}` docs have no `accounts.*` fields
- [ ] No top-level `strategy_docs_*`, `strategy_audit_*`, `strategy_processing_state_*`, `agent_analytics_*`, `cost_aggregations_*`, `performance_profiles_*`, `performance_profiles_acc_*`, `monitoring_topics/{account_id}`, or `alert_configurations/{account_id}` remain
- [ ] `notifications` and `usage_records` collections still exist (Shape C carve-out — must NOT be migrated)

### 4.2 Codebase residue scan

Run the following and address any hits (expected: zero hits in source files; hits in `multi-tenant-migration-plan.md`, research docs, and this PRD set are fine because those are historical/documentation):

```bash
rg -n "strategy_docs_\{account_id\}|strategy_audit_\{account_id\}|strategy_processing_state_\{account_id\}" api/ app/ \
  --glob '!**/docs/**' --glob '!**/*.md'
rg -n "agent_analytics_\{account_id\}|cost_aggregations_\{account_id\}|performance_profiles_\{account_id\}" api/ app/ \
  --glob '!**/docs/**' --glob '!**/*.md'
rg -n "accounts\.\{account_id\}\." api/ app/ \
  --glob '!**/docs/**' --glob '!**/*.md'
rg -n 'collection\("monitoring_topics"\)|collection\("alert_configurations"\)' api/ app/ \
  --glob '!**/docs/**'
```

Each grep should return **zero** hits after DM-PRD-01–DM-PRD-05 complete. Any hit is a leftover that must be filed against the responsible team.

### 4.3 Staging cutover

1. Coordinate a short maintenance window (no prod users, so no user impact — but reserve the window for staging-environment-integration purposes).
2. Deploy the merged code from DM-PRD-00–DM-PRD-05 to staging.
3. Run migration:
   ```bash
   python api/scripts/migrate_to_shape_b.py --all --env=staging --dry-run
   # inspect output
   python api/scripts/migrate_to_shape_b.py --all --env=staging
   # verify counts per resource
   python api/scripts/migrate_to_shape_b.py --all --env=staging --confirm-delete
   ```
4. Run the full Phase 6 verification checklist against staging (all items in §4.1 and §4.2).
5. Document staging run timing (how long each resource took; helps future ops).

### 4.4 Documentation updates

- Add **Review 16** entry to `docs/design/DESIGN-REVIEW-LOG.md`:
  - Scope: migration complete; all code on Shape B; staging cut over
  - Cross-link to [Review 15 in DESIGN-REVIEW-LOG](../../../DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1) — Multi-Tenant Data Model Shape
  - Link to the execution checklist in `../multi-tenant-migration-plan.md` §11 (all items checked)
- Update `docs/design/components/data-management/README.md` §Project Index — mark DM-PRD-00–DM-PRD-06 Status as "Complete"
- Update `docs/design/components/data-management/multi-tenant-migration-plan.md` §11 checklist — check the remaining boxes

## 5. Acceptance criteria

1. Every item in §4.1, §4.2, §4.3, §4.4 is checked off.
2. A new DESIGN-REVIEW-LOG entry exists documenting migration completion.
3. The migration plan §11 "Execution checklist" has all its checkboxes filled.
4. All PRDs DM-PRD-00–DM-PRD-06 in this project set have Status updated to "Complete" in the README.
5. Staging migration timing report is posted (a short comment in the DESIGN-REVIEW-LOG entry, or a separate doc linked from it).

## 6. Test plan

All verification is covered by §4. There is no new test code in this project.

A "red-light" test: if any of §4.1's checks fail, **do not proceed to §4.3**. File a follow-up against the responsible team (DM-PRD-01/DM-PRD-02/DM-PRD-03/DM-PRD-04/DM-PRD-05) and block this project until it's green.

## 7. Risks & open questions

| Risk | Mitigation |
|---|---|
| Residue scan finds hits after DM-PRD-01–DM-PRD-05 report "complete" | Catch via this project rather than in production. File issues with the owning teams; fix before proceeding to staging |
| Staging migration runs slower than dev (more data) | Migration script batches at 500 writes/sec per collection; timing scales with data volume. Budget time; run overnight if needed |
| Staging has data seeded in a way dev doesn't | Run `migrate_to_shape_b.py --list-source-collections` (new diagnostic subcommand — optional follow-up for DM-PRD-00) to compare; otherwise rely on the residue scan post-migration |
| `notifications` or `usage_records` accidentally migrated | The script's RESOURCES registry only includes what DM-PRD-01–DM-PRD-04 added. These two collections are not registered. Verify once via `--list` before running `--all` |

### Open questions

- **Q:** Should we add a production-readiness gate to DM-PRD-06 (full load test, failover drill)? → **Defer.** Production readiness is a separate workstream; this project gates on staging functional correctness. The migration itself is low-risk in prod because there are no users.

## 8. Reference

- Parent plan: [`../multi-tenant-migration-plan.md`](../multi-tenant-migration-plan.md) §4 Phase 6, §11
- Upstream: [DM-PRD-05](./DM-PRD-05-deletion-sweep-rewrite.md)
- Decision: [Review 15 in DESIGN-REVIEW-LOG](../../../DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1) — Multi-Tenant Data Model Shape
- CLAUDE.md rules in scope: (none — no code; documentation and verification only)
