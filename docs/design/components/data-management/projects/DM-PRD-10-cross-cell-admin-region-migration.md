# DM-PRD-10 — Cross-Cell Admin & Region Migration

**Status:** Ready to start
**Owner team:** [KEN-E] Data Management
**Initiative:** Data Residency (US + EU)
**Blocked by:** [DM-PRD-09](./DM-PRD-09-regional-cell-foundation.md) (regional-cell foundation — routing directory, `CELLS` registry, resolver, immutability guard)
**Parallel with:** —
**Blocks:** —
**Estimated effort:** 4–5 days

> **Program context.** This is a **Phase-2 / steady-state** slice of the data-residency program (cut-line in [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) §6.3). It is *not* a new component — it is homed in Data Management because it owns the global admin/analytics code and the `data_region` field. Read the program spec's §1–§4 (esp. §2 decision **D5** — "`data_region` is immutable after account creation; changing region is a Phase-2 supervised migration, not a field edit"), §5 (gap register, **R-21**), §6.3 (Phase 2), and §7 before this PRD. This project **closes R-21** and reuses, never redefines, every primitive from DM-PRD-09.

---

## 1. Context

DM-PRD-09 split the data plane into per-region cells: each account is pinned to a home region (`acc.data_region`, US/EU), resolved through the global `account_regions/{account_id}` directory and the `CELLS` registry, and served by a per-region Firestore client via `get_firestore_for_account(account_id)`. DM-PRD-09 also made `data_region` **immutable** at the field level — `PUT /accounts/{id}` returns `409` on any region change ([`./DM-PRD-09-regional-cell-foundation.md`](./DM-PRD-09-regional-cell-foundation.md) §4.3).

Two steady-state needs survive that split and are the gap **R-21** ([`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) §5):

1. **Global admin + analytics ops still assume one database.** They were written against a single `FirestoreService` client and break (silently return *only US results*) once an EU cell exists:
   - **Super-admin management** — `admin.py::_query_super_admin_docs` runs `list_documents("users", roles array_contains super_admin)` against one client (`admin.py:59-66`); `list_super_admins` / `grant_super_admin` / `revoke_super_admin` all read/write through `get_firestore_service` (`admin.py:112-214`). An EU-resident super-admin's `users/{uid}` doc is invisible, and the last-admin guard (`admin.py:194`) miscounts across cells.
   - **Monitoring-topics fan-out** — `update_accounts_with_industry` sweeps `db.collection_group("monitoring_topics")` on one client (`monitoring_topics.py:179-221`), and `get_all_industry_keywords` reads the global `industry_keywords` collection (`monitoring_topics.py:1212-1294`); both miss EU once split.
   - (Same class as the Phase-1 deletion/scheduler/audit sweeps in **R-09**, e.g. `audit_service.py:258-262` — but those are owned by DR-PRD-07; **R-21 is the *admin / analytics* fan-out**, distinct from R-09's lifecycle sweeps.)

2. **No supervised path to change an account's region.** D5 deliberately blocks the field edit, which means there is currently **no** sanctioned way to move an account that signed up in the wrong cell, or to relocate an account after a sovereignty re-classification. The deliberate cross-cell move — copy the account's entire Shape B subtree from the source cell to the destination cell, flip the routing directory + `acc.data_region`, then reap the source — is exactly what the immutability guard exists to prevent from happening *accidentally*. This PRD builds the **verified, audited tool** that does it on purpose.

This PRD ships **(A)** a per-region fan-out helper that iterates the `CELLS` registry so global admin/analytics ops query every cell, and **(B)** a supervised, dry-run-first region-migration tool. Residency-only; no functional change to what admin ops *do*, only *where they look*.

## 2. Scope

### In scope

- **Cell fan-out helper** — `for_each_cell(fn)` / `fan_out_query(fn)` in `residency/routing.py` that iterates `CELLS` (DM-PRD-09 §4.1), invokes `fn(cell_config, client)` against each region's Firestore client, and merges results. One helper, reused by every global admin/analytics caller — the cross-cell analogue of `get_firestore_for_account` for ops that span *all* cells rather than resolve *one* account.
- **Admin op regionalization** — `_query_super_admin_docs` fans out across cells and dedupes; `grant_super_admin` / `revoke_super_admin` write to the cell that holds the target user's doc (resolved by region); the last-admin guard counts the **union** across cells (`admin.py:59-214`).
- **Monitoring-topics fan-out** — `update_accounts_with_industry` runs its collection-group sweep per cell (`monitoring_topics.py:179-221`); `get_all_industry_keywords` merges `industry_keywords` across cells (`monitoring_topics.py:1212`). `industry_keywords` write-on-update fans out so every cell stays in sync.
- **Region-migration tool** — a super-admin-gated, supervised operation `migrate_account_region(account_id, target_region)` that executes the pipeline in §5.2: **dry-run → snapshot → copy across cells → verify → flip routing directory + `acc.data_region` → reap source → audit.** Implemented as a CLI/script first (`scripts/migrate_account_region.py`), invokable by a single internal endpoint guarded by `require_super_admin`.
- **Migration ledger** — a `region_migrations/{migration_id}` record in the **control-plane** Firestore (routing metadata only, R-22) tracking each migration's state machine, byte/doc counts, and verification result, for audit and resumability.
- **Immutability-guard escape hatch** — the migration tool is the **only** writer permitted to change `acc.data_region` and `account_regions/{id}`; it does so via an internal path that the `PUT /accounts/{id}` `409` guard (DM-PRD-09 §4.3) does not gate. The guard stays in place for all client traffic.

### Out of scope

- **Redefining any DM-PRD-09 primitive** — `Region` / `CELLS` / `CellConfig` / `normalize_region` / `resolve_account_region` / `get_firestore_for_account` / the directory schema / the field-level immutability guard are **consumed as-is** ([`./DM-PRD-09-regional-cell-foundation.md`](./DM-PRD-09-regional-cell-foundation.md) §4, §6).
- **Phase-1 lifecycle sweeps (R-09)** — deletion fan-out, session-end loop, scheduler, and `strategy_audit` sweeps are **DR-PRD-07** (`project-tasks → PR-PRD-10`). R-21 is admin + analytics only.
- **Regionalizing non-Firestore stores during migration** — Neo4j (DR-PRD-04), KMS/tokens (DR-PRD-03), Agent-Engine sessions (DR-PRD-01), Redis/artifacts (DR-PRD-05), BigQuery (DR-PRD-06) own their own per-store move semantics. This tool moves the **Firestore Shape B subtree + the Neo4j `acc.data_region` flip + the routing-directory flip**; it *invokes* each regionalized store's own copy/reap once that store's slice has shipped, and **fails fast** on any store not yet regionalized (a migration cannot be run until every store the account uses is cell-aware). See §9.
- **A self-service UI for migration** — supervised super-admin/CLI operation only; no customer-facing region-change control (D5).
- **Cross-region *replication* / multi-cell accounts** — an account lives in exactly one cell before and after; this is a move, not a fork.

## 3. Dependencies

- **DM-PRD-09 complete** — supplies `residency/regions.py` (`Region`, `CELLS`, `CellConfig`, `normalize_region`) and `residency/routing.py` (`resolve_account_region`, `get_firestore_for_account`, the control-plane directory client, per-region client cache). This PRD adds `for_each_cell` to the same module and the migration tool alongside it.
- **The Shape B convention** ([`../README.md`](../README.md) §7.1) — account data is `accounts/{account_id}/...`, so a full account subtree is a single recursive copy/delete root (`db.collection("accounts").document(account_id)`). The migration copy/reap relies on this single-root property.
- Reference pattern: `api/src/kene_api/services/storage_service.py:31-72` (the `data_region → (resource, location)` map DM-PRD-09 generalized into `CELLS`).
- Affected call sites (real): `api/src/kene_api/routers/admin.py:59-214`, `api/src/kene_api/routers/monitoring_topics.py:179-221` and `:1212-1294`.
- **External / open:** whether each downstream store's region-migration hook exists yet gates *which accounts can be migrated* (§9, Q-A). EU cell must be verified end-to-end (program §6.1) before any production migration runs.

## 4. Data contract

### 4.1 Cell fan-out (no new schema — iterates the DM-PRD-09 registry)

```python
# shared/residency/routing.py  (added alongside DM-PRD-09's resolver)
def for_each_cell(fn: Callable[[CellConfig, firestore.Client], list[T]]) -> list[T]:
    """Invoke fn against every cell in CELLS and concatenate results.
    Callers dedupe/merge as their semantics require (e.g. super-admin union)."""
```

### 4.2 Migration ledger (control-plane Firestore — routing metadata only, R-22)

```
region_migrations/{migration_id}
  account_id:        str
  source_region:     "US" | "EU"        # = resolve_account_region(account_id) at start
  target_region:     "US" | "EU"
  state:             "dry_run" | "snapshotting" | "copying" | "verifying"
                     | "cutover" | "reaping" | "completed" | "failed" | "rolled_back"
  doc_count_source:  int                # observed at snapshot
  doc_count_copied:  int                # observed after copy
  verification:      "pending" | "match" | "mismatch"
  started_by:        str                # super-admin uid
  started_at:        <server timestamp>
  updated_at:        <server timestamp>
  error:             str | null
```

- Holds **no regulated content** — counts, states, ids only. Lives in the global control-plane DB, not in either cell.
- `migration_id` = `mig_{account_id}_{utc_compact}`; one in-flight migration per account is enforced (reject if an open ledger row exists).

### 4.3 Migration invariants

| Phase | Invariant |
|---|---|
| Before cutover | `account_regions/{id}` and `acc.data_region` still point at **source**; all live traffic stays in the source cell. The copy is a shadow write to the destination cell — no reads route there yet. |
| Cutover (atomic-as-possible) | Flip `account_regions/{id}.region` **then** `acc.data_region` (Neo4j) to **target**. Between the two writes the directory is authoritative for routing (DM-PRD-09 §4.2), so flip the directory first. |
| After cutover, before reap | Source subtree still exists (rollback safety net); reads now route to target. |
| Reap | Source `accounts/{id}` subtree recursively deleted **only after** verification = `match` and cutover confirmed. |

## 5. Implementation outline

### 5.1 Cell fan-out for global admin/analytics

| Action | File |
|---|---|
| Add | `residency/routing.py` — `for_each_cell(fn)` iterating `CELLS` |
| Modify | `routers/admin.py` — `_query_super_admin_docs` fans out + dedupes by `uid` (`:59-66`); grant/revoke resolve the target's cell and write there (`:124-214`); last-admin guard counts the union (`:194`) |
| Modify | `routers/monitoring_topics.py` — `update_accounts_with_industry` sweeps per cell (`:179-221`); `get_all_industry_keywords` merges + write fans out (`:1212-1294`) |

### 5.2 Region-migration pipeline

| Step | Action | Detail |
|---|---|---|
| 1. Dry-run | Enumerate source subtree | Count docs/subcollections under `accounts/{id}` in the source cell; report what *would* move; write ledger `state=dry_run`. No writes. Default mode — a real move requires an explicit `--execute` flag. |
| 2. Snapshot | Freeze a consistent read set | Record source doc count; (optional) set an account-level `migration_in_progress` flag to fence writes during the window. |
| 3. Copy | Stream source → target cell | Recursively copy `accounts/{id}/**` from `get_firestore_for_account`-style source client to the **target** cell's client, preserving paths (Shape B single-root). Invoke each already-regionalized store's own copy hook for its data; **fail fast** if a store the account uses has no hook yet (§2 out-of-scope, §9). |
| 4. Verify | Prove parity | Re-count target subtree; compare to snapshot; spot-check key docs. `verification=match` required to proceed; `mismatch` → `state=failed`, no cutover, source untouched. |
| 5. Cutover | Flip routing | Write `account_regions/{id}.region=target` (directory first), then `acc.data_region=target` (Neo4j) via the **internal** writer that bypasses the `PUT /accounts/{id}` 409 guard. Invalidate any cached region resolution. |
| 6. Reap | Delete source | `firestore.recursive_delete(source.collection("accounts").document(account_id))` (Shape B sweep, [`../README.md`](../README.md) §7.1) only after cutover confirmed. |
| 7. Audit | Record outcome | Ledger `state=completed`; emit a `SecurityEventType` audit event (reuse `admin.py::_audit_role_change` pattern, `admin.py:93-109`) attributing the move to the super-admin with source/target/counts. |

| Action | File |
|---|---|
| Create | `api/scripts/migrate_account_region.py` — CLI implementing steps 1–7; `--execute` required for a real move (dry-run default) |
| Create | `residency/migration.py` — `migrate_account_region(account_id, target_region, *, dry_run)`, ledger state machine, the internal `data_region` writer |
| Modify | `routers/admin.py` (or a new `routers/residency_admin.py`) — one `require_super_admin`-gated endpoint that triggers/queries a migration |
| Create | `api/tests/unit/test_residency_fan_out.py`, `api/tests/unit/test_region_migration.py` |
| Create | `api/tests/integration/test_region_migration.py` (Firestore emulator, two simulated cells) |
| Modify | [`../README.md`](../README.md) §7.8 — append the cross-cell fan-out + supervised-migration note (the field-level guard's deliberate escape hatch) |

## 6. API contract

| Contract | Consumed by | Source of truth |
|---|---|---|
| `for_each_cell(fn)` cross-cell query helper | every global admin/analytics op that must span cells | `shared/residency/routing.py` |
| `GET /api/v1/admin/super-admins` returns the **union** across cells; grant/revoke target the holder's cell | Admin UI, bootstrap | `api/src/kene_api/routers/admin.py` |
| `POST /api/v1/admin/region-migrations` (super-admin) — start a dry-run or `execute` move; `GET .../{migration_id}` — ledger status | Super-admin tooling / CLI | `api/src/kene_api/routers/admin.py` |
| `migrate_account_region(account_id, target_region, *, dry_run)` + `region_migrations/{id}` ledger | the migration CLI/endpoint | `shared/residency/migration.py` |
| `acc.data_region` change is permitted **only** through the migration writer; `PUT /accounts/{id}` still `409`s on a region change | account-update callers (blocked); migration tool (allowed) | DM-PRD-09 §4.3 + this PRD's internal writer |

## 7. Acceptance criteria

1. `for_each_cell(fn)` invokes `fn` once per entry in `CELLS` and concatenates results; with a single-cell `CELLS` it behaves identically to today (one call), so US-only deployments are unaffected.
2. `GET /api/v1/admin/super-admins` returns a super-admin whose `users/{uid}` doc lives in the **EU** cell as well as US ones, deduped by `uid`; the last-admin guard refuses to revoke when the cross-cell union is `<= 1` even if the local cell would show `> 1`.
3. `grant_super_admin` / `revoke_super_admin` for an EU-resident user writes to the **EU** cell's `users/{uid}` doc, not the US client.
4. `get_all_industry_keywords` merges `industry_keywords` from every cell; `update_accounts_with_industry` runs its `monitoring_topics` collection-group sweep once per cell.
5. `migrate_account_region(..., dry_run=True)` writes a `region_migrations/{id}` ledger with `state="dry_run"` and source doc counts, and makes **no** write to either cell's account subtree, the directory, or `acc.data_region`.
6. A full execute migration of an EU→US account: target cell holds the complete `accounts/{id}` subtree; `account_regions/{id}.region` and `acc.data_region` both read `US`; `resolve_account_region(id)` returns `US`; the source subtree is deleted; the ledger reads `completed` with `verification="match"` and an audit event was emitted.
7. A verification mismatch (target count != snapshot) leaves the ledger `failed`, **does not** flip the directory or `acc.data_region`, and **does not** reap the source — the account remains fully live in its source cell.
8. The migration writer is the **only** code path that changes `acc.data_region`; `PUT /api/v1/accounts/{id}` changing `data_region` still returns `409` (DM-PRD-09 guard intact — regression-asserted here).
9. Attempting to migrate an account whose data lives in a store with no region-migration hook yet (e.g. Neo4j pre-DR-PRD-04) fails fast in dry-run with a clear "store not cell-aware" error and writes nothing.
10. `make lint` passes; `pytest api/tests/unit/test_residency_fan_out.py api/tests/unit/test_region_migration.py api/tests/integration/test_region_migration.py` passes.
11. `lychee --config lychee.toml .` passes for the touched docs.

## 8. Test plan

### Unit (`test_residency_fan_out.py`, `test_region_migration.py`)

- `for_each_cell` with a 2-entry `CELLS` calls `fn` twice and concatenates; with a 1-entry `CELLS` calls once (AC-1).
- Super-admin union dedupes a uid present in both cells; last-admin guard counts the union (AC-2) — mock two cell clients.
- Migration state machine: dry-run writes ledger + no data writes (AC-5); mismatch path stops at `failed` with no cutover/reap (AC-7); fail-fast on a non-cell-aware store (AC-9). Mock the cell clients and the verify step.

### Integration (`test_region_migration.py`, Firestore emulator + two simulated cells + mocked Neo4j)

- Seed an account subtree in the "EU" emulator DB; run an execute migration to "US"; assert target parity, directory + `acc.data_region` = US, source reaped, ledger `completed` (AC-6).
- Inject a copy gap so verify mismatches; assert source untouched, no cutover (AC-7).
- Assert `PUT /accounts/{id}` region change still `409`s while the migration writer succeeds (AC-8).
- `grant_super_admin` for an EU user writes to the EU emulator DB (AC-3).

(Per CLAUDE.md T-4, pure fan-out/state-machine logic is unit-tested; DB-touching copy/verify/reap is integration-tested on the emulator.)

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| **Partial cross-store migration** — Firestore moves but Neo4j/KMS/Redis/BigQuery for that account don't, splitting the account across cells (the exact failure D5 names). | Fail-fast preflight (AC-9): a migration aborts in dry-run unless **every** store the account uses exposes a region-migration hook. Until DR-PRD-01…06 land their hooks, the tool can move only Firestore-only accounts. The ledger + verify gate make every move resumable/abortable. |
| **Cutover window write loss** — a write lands in the source cell after snapshot but before reap. | Optional `migration_in_progress` write fence during the window (§5.2 step 2); short window; reap only after verify. A self-service product flow is out of scope, so migrations are operator-scheduled into low-traffic windows. |
| **Directory ↔ Neo4j divergence during cutover** (two writes, not one transaction). | Flip the **directory first** (it is the routing authority per DM-PRD-09 §4.2), then `acc.data_region`; on failure between them, the ledger drives a deterministic re-flip or rollback. |
| **Fan-out cost / latency grows with cell count** | Two cells at launch; `for_each_cell` is the only fan-out primitive so a future cap/parallelism change is one place. Admin/analytics ops are low-QPS. |
| **Accidental reap** | Reap is gated on `verification="match"` **and** confirmed cutover; dry-run is the default and `--execute` is required for any write. |

### Open questions

- **Q-A — store-hook readiness:** which downstream stores expose a region-migration hook, and in what order? Determines which accounts are migratable at any point. Tracked against DR-PRD-01…06; this tool degrades gracefully (Firestore-only until then).
- **Q5 (carry from program §8) — org/region scope:** if one organization may hold accounts in both cells, the super-admin union and any org-level admin op must always fan out; if orgs are region-pinned, some ops can resolve to one cell. Informs whether `for_each_cell` or `get_firestore_for_account` is the right primitive per call site.
- **Whether the migration endpoint is needed at launch** or the CLI suffices for Phase 2 — endpoint is thin (`require_super_admin` wrapper); ship CLI first, endpoint if ops needs remote trigger.

## 10. Reference

- Program spec: [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) — §2 decision **D5** (region change = supervised migration, not a field edit), §5 **R-21**, §6.3 (Phase 2), §7 (PRD breakdown, DR-PRD-10 → DM-PRD-10 row).
- Keystone foundation (consumed, not redefined): [`./DM-PRD-09-regional-cell-foundation.md`](./DM-PRD-09-regional-cell-foundation.md) — §4.1 `CELLS`/`Region`, §4.2 routing directory, §4.3 `data_region` immutability guard, §4.4 `resolve_account_region` / `get_firestore_for_account`.
- Convention home: [`../README.md`](../README.md) §7.8 (Regional Cell routing convention); §7.1 Shape B path convention (single-root account subtree for copy/reap).
- Affected code (real `path:line`): `api/src/kene_api/routers/admin.py:59-214`, `api/src/kene_api/routers/monitoring_topics.py:179-221` and `:1212-1294`; audit pattern `admin.py:93-109`; reference pattern `api/src/kene_api/services/storage_service.py:31-72`.
- CLAUDE.md rules in scope: PY-1, PY-2, PY-5, PY-7; D-1, D-3, D-5; T-1, T-3, T-4, T-6.
