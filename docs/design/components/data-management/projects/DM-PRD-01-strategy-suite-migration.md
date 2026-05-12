# DM-PRD-01 — Strategy Suite Migration

**Status:** Blocked
**Owner team:** Backend / Strategy
**Blocked by:** DM-PRD-00
**Parallel with:** DM-PRD-02, DM-PRD-03, DM-PRD-04
**Blocks:** DM-PRD-05
**Estimated effort:** 3–4 days

---

## 1. Context

Migrate three Shape A collections in the strategy resource family to Shape B subcollections under `accounts/{account_id}/...`:

- `strategy_docs_{account_id}/{doc_type}` → `accounts/{account_id}/strategy_docs/{doc_type}` (bounded, ~11 doc types)
- `strategy_docs_{account_id}/{doc_type}/versions/{n}` → `accounts/{account_id}/strategy_docs/{doc_type}/versions/{n}` (unbounded)
- `strategy_audit_{account_id}/{audit_id}` → `accounts/{account_id}/strategy_audit/{audit_id}` (unbounded)
- `strategy_processing_state_{account_id}` → `accounts/{account_id}/strategy_processing_state/{state_id}` (bounded)

**Side-effect fix:** the silently-broken `collection_group("strategy_audit")` query at `api/src/kene_api/services/audit_service.py:189` starts working as soon as strategy_audit collections move — without editing the query. That query was written for Shape B but Shape A caused it to always return empty.

These three resources cluster together because `routers/strategy.py` and `services/audit_service.py` are tightly coupled, and they share the highest code surface area in the migration (routers, services, strategy agent internals, tasks, and ops scripts).

## 2. Scope

### In scope
- Register three entries in `api/scripts/_migrate_shape_b/resources.py` (from DM-PRD-00): `strategy_docs`, `strategy_audit`, `strategy_processing_state`
- Run migration in dev; verify counts; delete legacy collections
- Swap all read + write call sites to Shape B paths
- Update unit and integration tests
- Update `api/check_strategy_docs.py` debug script
- Update `api/scripts/delete_intellipure_accounts.py` path references (full sweep-rewrite stays in DM-PRD-05)
- Add a new integration test confirming `audit_service.get_user_activity(user_id)` now returns cross-account results

### Out of scope
- Account-deletion flow rewrite in `routers/accounts.py:968-997` — DM-PRD-05 owns this
- `strategy_doc_guides` (global; not account-scoped; unchanged)
- Analytics collections (`agent_analytics_*`, `cost_aggregations_*`, `performance_profiles_*`) — DM-PRD-02 owns these
- Shape D split (org doc nested accounts map) — DM-PRD-03 owns this
- Session-id naming like `session_id=f"strategy_{account_id}"` in `tasks/strategy_tasks.py:227` — these are identifiers, not collection paths; do not touch

## 3. Dependencies

- **DM-PRD-00:** `migrate_to_shape_b.py` merged; `strategy_audit` collection-group index deployed and `READY`
- **DM-69 (fast-follow):** Five COLLECTION-scoped composite indexes on `strategy_audit` required by `get_strategy_audit_log`, `get_recent_actions`, and `get_document_history` — shipped as a separate issue after wave-1. Operator must run `terraform apply` and confirm `READY` before these query paths are unblocked in dev.
- Existing files to study:
  - `api/src/kene_api/routers/strategy.py`
  - `api/src/kene_api/services/audit_service.py`
  - `api/src/kene_api/services/account_service.py`
  - `api/src/kene_api/services/graph_sync_service.py`
  - `api/src/kene_api/tasks/strategy_tasks.py`
  - `app/adk/agents/strategy_agent/firestore.py`
  - `api/check_strategy_docs.py`
  - `api/scripts/delete_intellipure_accounts.py`

## 4. Call-site inventory

Sourced from [`../multi-tenant-migration-plan.md`](../multi-tenant-migration-plan.md) §3.1 and §3.5. This is the authoritative list — update code at each site to Shape B paths.

| File | Lines | Notes |
|---|---|---|
| `api/src/kene_api/routers/strategy.py` | 86, 149, 154, 219, 233, 336, 445 | `strategy_docs_{account_id}` → `accounts/{account_id}/strategy_docs`; ditto `strategy_audit` |
| `api/src/kene_api/services/audit_service.py` | 75, 111, 154, 226 | Path-only updates |
| `api/src/kene_api/services/audit_service.py` | 189 | **Do NOT edit the query.** The `collection_group("strategy_audit")` line stays as is — once data moves, the query starts working |
| `api/src/kene_api/services/account_service.py` | 378 | Path update |
| `api/src/kene_api/services/graph_sync_service.py` | 4102 | Path update |
| `api/src/kene_api/tasks/strategy_tasks.py` | 803 (docstring), 814 | Path update (docstring + code) |
| `api/src/kene_api/tasks/strategy_tasks.py` | 227 | Session-id prefix — **do NOT change.** Identifier, not a collection path |
| `app/adk/agents/strategy_agent/firestore.py` | 280, 335, 363, 406, 467, 474, 622, 641–642 | Path updates |
| `app/adk/agents/strategy_agent/ARTIFACT_CONVENTIONS.md` | 34 | Doc update — mention new path |
| `api/check_strategy_docs.py` | 15, 21 | Path update |
| `api/scripts/delete_intellipure_accounts.py` | 60–75 | Path update (full sweep-rewrite stays in DM-PRD-05) |

## 5. Implementation outline

### Phase 1 — Register resources (morning day 1)

Add to `api/scripts/_migrate_shape_b/resources.py`:

```python
RESOURCES["strategy_processing_state"] = MigrateConfig(
    old_prefix="strategy_processing_state_",
    new_subcollection="strategy_processing_state",
    has_versions=False,
)
RESOURCES["strategy_docs"] = MigrateConfig(
    old_prefix="strategy_docs_",
    new_subcollection="strategy_docs",
    has_versions=True,
)
RESOURCES["strategy_audit"] = MigrateConfig(
    old_prefix="strategy_audit_",
    new_subcollection="strategy_audit",
    has_versions=False,
)
```

### Phase 2 — Code migration (day 1–2)

Order by risk (lowest first):

1. **`strategy_processing_state`** — smallest, bounded, fewest call sites (2). Validates the pattern.
2. **`strategy_docs`** — biggest surface area (router, service, agent internals, versions subcollection).
3. **`strategy_audit`** — audit-query fix comes for free.

For each resource, in one branch:
1. Update all write call sites to new path.
2. Update all read call sites to new path.
3. Update unit-test fixtures.
4. Run `pytest api/tests/ app/adk/agents/strategy_agent/tests/` — all green.
5. Run `make lint` — clean.

### Phase 3 — Data migration (day 2–3)

Against the dev environment:

```bash
# Dry run first
python api/scripts/migrate_to_shape_b.py --resource=strategy_processing_state --dry-run

# Copy + verify
python api/scripts/migrate_to_shape_b.py --resource=strategy_processing_state

# Spot-check via Firestore console → console shows accounts/{id}/strategy_processing_state

# Delete legacy
python api/scripts/migrate_to_shape_b.py --resource=strategy_processing_state --confirm-delete

# Repeat for strategy_docs and strategy_audit
```

### Phase 4 — Verification (day 3–4)

- `pytest api/tests/` — all green
- `pytest api/tests/integration/test_strategy_audit_cross_account.py` — new test (see §7)
- Manual smoke in dev:
  - Create a strategy doc via API → lands in `accounts/{id}/strategy_docs/{doc_type}`
  - Edit the doc → creates `accounts/{id}/strategy_docs/{doc_type}/versions/2`
  - Audit entry appears in `accounts/{id}/strategy_audit/{audit_id}`
- `api/check_strategy_docs.py` works against a migrated account

## 6. Acceptance criteria

1. All code call sites in §4 reference `accounts/{account_id}/strategy_{docs,audit,processing_state}/...` paths. `rg -n "strategy_(docs|audit|processing_state)_" api/ app/` returns zero hits in source files (fixtures and migration resources list are allowed; CI grep excludes those paths).
2. In the dev Firestore project, no top-level collections matching `strategy_docs_*`, `strategy_audit_*`, or `strategy_processing_state_*` exist after Phase 3 completes.
3. `audit_service.get_user_activity(user_id)` returns non-empty results for a seeded user with audit entries spread across ≥ 2 accounts (new integration test — see §7).
4. `POST /api/v1/accounts/{id}/strategy/...` writes land at `accounts/{id}/strategy_docs/{doc_type}` and create a matching audit entry at `accounts/{id}/strategy_audit/{audit_id}`.
5. Editing a strategy doc creates `accounts/{id}/strategy_docs/{doc_type}/versions/{n+1}`.
6. `api/check_strategy_docs.py` prints strategy doc contents for a migrated account without error.
7. `pytest api/tests/ app/adk/agents/strategy_agent/tests/` passes. `make lint` clean.
8. Migration script is idempotent: re-running `--resource=strategy_docs` is a no-op.

## 7. Test plan

### Unit tests (update existing)
- `api/tests/test_firestore.py` — fixture paths updated
- `api/tests/unit/test_strategy_*.py` — fixture paths updated
- `app/adk/agents/strategy_agent/tests/test_firestore.py` — fixture paths updated

### Integration tests (update existing + 1 new)
- `api/tests/integration/test_strategy_*.py` — full CRUD round-trip at new paths
- **New:** `api/tests/integration/test_strategy_audit_cross_account.py`:
  - Seed 2 accounts, each with 3 audit entries for the same `user_id`
  - Call `audit_service.get_user_activity(user_id, limit=100)`
  - Assert: 6 results, sorted by `timestamp DESC`
  - Confirms the `collection_group("strategy_audit")` query at `audit_service.py:189` works under Shape B

### Manual verification (in dev)
- Create → edit → audit → verify via Firestore console that docs appear at new paths
- Soft-delete an account and confirm (pre-DM-PRD-05) that `accounts/{id}/strategy_docs/*` is still there — DM-PRD-05 owns the sweep

## 8. Risks & open questions

| Risk | Mitigation |
|---|---|
| Missing a call site → stale Shape A writes after migration | CI grep blocks merge on any unexpected `strategy_(docs|audit|processing_state)_` usage in source; §4 table is the authoritative list |
| `collection_group("strategy_audit")` index not READY before migration | DM-PRD-00 deploys the index; before Phase 3, team runs `gcloud firestore indexes composite list` and confirms `READY` |
| `versions/{n}` subcollection not copied by the script | `MigrateConfig.has_versions=True` on `strategy_docs`; DM-PRD-00 integration test already exercises this path — verify it's covered before running the real migration |
| Write throughput on `strategy_audit` migration saturates the 500 writes/sec per-collection limit | Migration script batches at 500/sec; acceptable for a one-time migration. Log timing. |
| Tests depend on the old collection names via string constants | Search for `"strategy_docs_"` (with trailing underscore) in tests; update |

### Open questions

- **Q:** Do Neo4j embeddings need re-indexing after migration? → **No.** Embeddings live on Neo4j nodes, not in these Firestore collections. Unaffected.

## 9. Reference

- Parent plan: [`../multi-tenant-migration-plan.md`](../multi-tenant-migration-plan.md) §3.1, §3.4, §3.5
- Upstream: [DM-PRD-00](./DM-PRD-00-migration-foundation.md)
- Downstream: [DM-PRD-05](./DM-PRD-05-deletion-sweep-rewrite.md)
- Decision: [Review 15 in DESIGN-REVIEW-LOG](../../../DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1) — Multi-Tenant Data Model Shape
- CLAUDE.md rules in scope: PY-1, PY-2, PY-7; T-1, T-3, T-4, T-6, T-8
