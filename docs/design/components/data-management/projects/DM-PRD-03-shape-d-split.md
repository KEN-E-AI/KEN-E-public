# DM-PRD-03 — Shape D Split (Organizations → Per-Account Docs)

**Status:** Blocked
**Owner team:** Backend / Data
**Blocked by:** DM-PRD-00
**Parallel with:** DM-PRD-01, DM-PRD-02, DM-PRD-04
**Blocks:** DM-PRD-05
**Estimated effort:** 3–4 days

---

## 1. Context

The `organizations/{org_id}` Firestore doc currently holds nested `accounts.{account_id}.account_settings.*` and `accounts.{account_id}.funnels.*` maps for **every account in the org**. This is the 1 MiB-per-document ceiling sleeper risk at the 10k-account scale target.

This project splits that nested structure out of the organization doc and into per-account docs at `accounts/{account_id}`. The funnel / KPI tree becomes a direct field (or a subcollection, depending on observed size) on the account doc — removing the multi-account-in-one-doc pattern entirely.

Unlike DM-PRD-01/DM-PRD-02, this is **not** a collection move. It's a field-path refactor inside the document model. The migration plan's [§3.3](../multi-tenant-migration-plan.md#33-shape-d-split-organizationsorg_id-nested-accounts-map--accountsaccount_id-docs) specifies the target paths.

## 2. Scope

### In scope
- **Phase 2.1 — Profile (non-destructive):** measure current `organizations/{org_id}` doc sizes and account-count distribution; pick implementation style for funnel tree
- **Phase 2.2 — Implement:** write migration helper that moves `accounts.{id}.account_settings.*` and `accounts.{id}.funnels.*` out of org docs into `accounts/{id}` docs
- Update `api/src/kene_api/firestore.py` — 15 methods at lines 441–1469 that read/write these nested field paths
- Update affected tests
- Verify: funnel/KPI dashboard, funnel step CRUD, KPI-setting APIs all continue to work
- Implement style decision:
  - If observed p99 funnel tree fits comfortably in ~500 KiB on the new account doc → keep as map field on `accounts/{id}`
  - Otherwise → store as a subcollection tree under `accounts/{id}/funnels/*`

### Out of scope
- Changes to Neo4j (funnel and KPI node representation is unaffected)
- Changes to the organization-level fields that are not account-scoped (e.g., `organizations/{org_id}.name`, `organizations/{org_id}.agency`) — those stay on the org doc
- Collections owned by DM-PRD-01/DM-PRD-02/DM-PRD-04
- Account-deletion flow (DM-PRD-05)

## 3. Dependencies

- **DM-PRD-00:** Shape B convention documented; migration script infrastructure in place (even if this project doesn't use the generic migrator — see §5)
- Existing files to study:
  - `api/src/kene_api/firestore.py` (especially `ORGANIZATIONS_COLLECTION` constant at L23, and methods at L441, 491, 544, 619, 671, 751, 786, 895, 934, 991, 1082, 1141, 1215, 1411, 1471)
  - `api/src/kene_api/routers/firestore.py` — consumers of the Shape D methods
  - `api/src/kene_api/routers/funnel_reports.py` (if present) — downstream consumer
  - Any Neo4j service that joins on the funnel config (read-only, shouldn't change, but verify)

## 4. Target data model

Pre-migration (status quo):
```
organizations/{org_id}
  ├─ (org-level fields: name, agency, created_at, …)
  └─ accounts: {
       "acc_abc": {
         "account_settings": {"overview_kpis": {"income_kpi": "m_123", ...}},
         "funnels": {
           "organization": {"1": {...step 1...}, "2": {...}, ...},
           "big_bets":     {"bet_1": {"1": {...}, "2": {...}}}
         }
       },
       "acc_def": { ... }
     }
```

Post-migration:
```
organizations/{org_id}
  └─ (org-level fields only; no nested accounts map)

accounts/{account_id}
  ├─ organization_id: "{org_id}"                      (back-reference)
  ├─ account_settings.overview_kpis.{kpi_name}        (direct map field)
  └─ funnels: { ... }                                 (direct map field — if p99 < 500 KiB)
  │
  OR (if funnel tree exceeds 500 KiB on p99):
  │
  └─ funnels/organization/{step_num}                  (subcollection)
     funnels/big_bets/{big_bet_name}/{step_num}
```

The implementation style for `funnels` is picked after Phase 2.1 profiling. Document the decision in a short callout in `firestore.py` and in the `../multi-tenant-migration-plan.md` §3.3 section (appended, not rewritten).

## 5. Implementation outline

### Phase 2.1 — Profile (day 1)

Run a read-only profiler script (`api/scripts/profile_org_doc_sizes.py` — create for this project):

```bash
python api/scripts/profile_org_doc_sizes.py --env=dev
# Output per org:
#   org_id, byte_size, account_count, max_account_byte_size, max_funnel_depth
# Summary:
#   p50, p95, p99 of total doc size
#   p99 of per-account byte footprint
#   count of orgs currently > 500 KiB, > 750 KiB
```

If p99 per-account byte footprint < 500 KiB → **Style A: map field on account doc** (simpler).
Else → **Style B: subcollection under `accounts/{id}/funnels/`** (safer at scale).

Record the decision in the PR description and in a short `## Funnel storage style decision` section added to `../multi-tenant-migration-plan.md` §3.3.

### Phase 2.2 — Migration helper (day 1–2)

Create `api/scripts/migrate_shape_d_split.py`. Unlike `migrate_to_shape_b.py`, this script is resource-specific (one-off migration, not reusable). For each org doc:

1. Read `accounts` map field.
2. For each `{account_id, nested_payload}` in the map:
   a. Ensure `accounts/{account_id}` doc exists; create with `organization_id` back-reference if missing.
   b. Merge `nested_payload.account_settings` and `nested_payload.funnels` into the account doc (Style A) OR write to `accounts/{account_id}/funnels/` subcollection (Style B).
3. After every account in the org is migrated and verified, remove the `accounts` field from the org doc via `firestore.DELETE_FIELD`.

Script supports `--dry-run`, `--confirm-delete-field` flags similar to the DM-PRD-00 script.

### Phase 3 — Code update (day 2–3)

Update all 15 Shape D methods in `api/src/kene_api/firestore.py` (lines listed in §3). Each method currently takes `(organization_id, account_id, ...)` and updates a field path like `accounts.{account_id}.funnels.…` on the org doc. After migration:

- Method signatures keep `account_id` but drop `organization_id` where possible (most methods don't actually need `organization_id` post-migration).
- Field path changes from `accounts.{account_id}.…` on `organizations/{org_id}` to a field path (or subcollection) on `accounts/{account_id}`.

Maintain backwards-compat-friendly signatures **only if required by callers**. Since there are no production users, signature changes are acceptable — verify with callers in `routers/firestore.py` and update them.

### Phase 4 — Data migration (day 3)

```bash
# Dev
python api/scripts/migrate_shape_d_split.py --env=dev --dry-run
python api/scripts/migrate_shape_d_split.py --env=dev

# Spot-check: verify a sample org no longer has nested accounts map
# Spot-check: verify accounts/{id} docs now have the funnel/KPI fields

python api/scripts/migrate_shape_d_split.py --env=dev --confirm-delete-field
```

### Phase 5 — Verification (day 4)

- KPI dashboard / funnel dashboard endpoints return the same data post-migration (before-after diff)
- Funnel step CRUD (create, update, delete) works
- `organizations/{org_id}` docs have no `accounts.*` fields after migration (verify via Firestore console)
- `accounts/{id}` docs have the new fields/subcollections populated

## 6. Acceptance criteria

1. `api/scripts/profile_org_doc_sizes.py` runs successfully against dev; output includes p50/p95/p99 byte sizes and the count of orgs exceeding size thresholds.
2. A storage-style decision (A: field, B: subcollection) is documented in the PR description and appended to `../multi-tenant-migration-plan.md` §3.3 with the measured numbers.
3. All 15 methods in `api/src/kene_api/firestore.py` at lines 441–1469 no longer reference `organizations/{org_id}.accounts.{account_id}.*` field paths. They read/write `accounts/{account_id}` docs (or subcollections, per the chosen style).
4. After running `migrate_shape_d_split.py --confirm-delete-field` in dev, `organizations/{org_id}` docs have no `accounts.*` field.
5. Every migrated `accounts/{account_id}` doc has an `organization_id` back-reference field.
6. KPI and funnel endpoints (`GET /api/v1/accounts/{id}/funnels/…`, `PATCH …/kpi`, etc.) return the same data before and after migration for a seeded account (capture before/after JSON and diff).
7. `pytest api/tests/` passes. `make lint` clean.
8. Migration script is idempotent: re-running `--confirm-delete-field` after a successful run is a no-op.

## 7. Test plan

### Unit tests (update existing)
- `api/tests/test_firestore.py` tests for KPI / funnel methods — update fixtures and assertions for new paths
- `api/tests/test_funnel_reports.py` — if present, update to new paths

### Integration tests
- Seed an organization with 2 accounts, each with a full funnel tree (organization steps + 2 big_bets × 3 steps × 2 channels × 2 tactics). Run migration. Assert:
  - `organizations/{org_id}` has no `accounts` field
  - Both `accounts/{id}` docs have correct funnel/KPI data
  - The API returns the same response as pre-migration

### Migration idempotency test
- Run migration twice; second run is a no-op (no errors, no duplicate writes)

## 8. Risks & open questions

| Risk | Mitigation |
|---|---|
| Hidden consumers of the old Shape D paths outside `firestore.py` | Grep `rg -n "accounts\.\{account_id\}\.(funnels|account_settings)" api/ app/`; address every hit |
| Style B (subcollection) performance regression on hot reads | Profile reads before/after; if > 20% latency delta on funnel dashboard, fall back to Style A |
| Field-delete on org docs loses data if aborted mid-run | Script writes account docs first, verifies count, then deletes field. Partial failure leaves data in BOTH places (old + new) — not data loss. Re-run resumes |
| Neo4j funnel-related queries break | Neo4j is read-only affected; funnel/KPI storage was always Firestore. Verify once, no code change expected |
| Org-level fields (non-account-scoped) accidentally migrated | Migration explicitly only touches `accounts.*` map field; unit test asserts other org fields untouched |

### Open questions

- **Q:** Should `organizations/{org_id}` be renamed to `accounts_organizations/{org_id}` for consistency? → **No.** The collection name `organizations` is clear and stable; only the nested structure was the problem. No rename.
- **Q:** Do we add a DB-level assertion that every account doc has an `organization_id`? → **Defer to a follow-up.** Add as a Firestore security-rule hint or a Pydantic model constraint in a separate PR; not blocking for this migration.

## 9. Reference

- Parent plan: [`../multi-tenant-migration-plan.md`](../multi-tenant-migration-plan.md) §3.3
- Upstream: [DM-PRD-00](./DM-PRD-00-migration-foundation.md)
- Downstream: [DM-PRD-05](./DM-PRD-05-deletion-sweep-rewrite.md)
- Notion decision: [Multi-Tenant Data Model Shape](https://www.notion.so/34830fd653028177bc0dc2a1637c7f60)
- Code: `api/src/kene_api/firestore.py` (the L441–L1469 block of methods)
- CLAUDE.md rules in scope: PY-1, PY-2, PY-5, PY-7; D-1, D-2, D-5; T-1, T-3, T-4, T-6
