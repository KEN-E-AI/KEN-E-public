# DM-PRD-05 — Account Deletion Sweep Rewrite

**Status:** Blocked
**Owner team:** Backend
**Blocked by:** DM-PRD-01, DM-PRD-02, DM-PRD-03, DM-PRD-04
**Parallel with:** —
**Blocks:** DM-PRD-06
**Estimated effort:** 1–2 days

---

## 1. Context

The account-deletion flow at `api/src/kene_api/routers/accounts.py:968-997` currently sweeps exactly **one** per-account collection (`strategy_docs_{account_id}`). Under Shape A this was explicit-by-design, but it meant every other per-account collection (`strategy_audit`, `agent_analytics`, `cost_aggregations`, `performance_profiles`, `strategy_processing_state`, plus the originally Shape B-like `monitoring_topics/{id}` and `alert_configurations/{id}`, plus the Shape D nested accounts-map inside `organizations/{org_id}`) was **orphaned** on account deletion. Latent GDPR issue.

After DM-PRD-01–DM-PRD-04 migrate all of those to `accounts/{account_id}/...`, deletion becomes a single call:

```python
firestore.recursive_delete(db.collection("accounts").document(account_id))
```

This project is that rewrite, plus an end-to-end test that proves nothing is orphaned.

Can only start after **all four** data-migration projects (DM-PRD-01, DM-PRD-02, DM-PRD-03, DM-PRD-04) complete and verify — otherwise `recursive_delete` won't cover the un-migrated collections and the bug persists for a different shape.

## 2. Scope

### In scope
- Rewrite `api/src/kene_api/routers/accounts.py:968-997` to use `firestore.recursive_delete`
- Simplify `api/scripts/delete_intellipure_accounts.py` to match
- Keep existing GCS-prefix deletion via `storage_service.delete_account_documents` (unchanged)
- Keep existing Neo4j cascade deletion (unchanged)
- Add a new integration test `test_account_deletion_no_orphans.py` that seeds every migrated resource type and verifies nothing is orphaned after deletion

### Out of scope
- Any further data-model changes — DM-PRD-01–DM-PRD-04 own those
- Deletion retry / partial-failure semantics beyond what `recursive_delete` provides
- GCS lifecycle rule changes

## 3. Dependencies

- **DM-PRD-01:** `strategy_docs`, `strategy_audit`, `strategy_processing_state` live under `accounts/{id}/...`
- **DM-PRD-02:** `agent_analytics`, `cost_aggregations`, `performance_profiles` live under `accounts/{id}/...`
- **DM-PRD-03:** funnel/KPI config lives on `accounts/{id}` doc (or subcollection), not on `organizations/{org_id}`
- **DM-PRD-04:** `monitoring_topics` and `alert_configurations` live under `accounts/{id}/...`
- Existing files to study:
  - `api/src/kene_api/routers/accounts.py` (L900–L1070 — the delete-account endpoint)
  - `api/src/kene_api/services/storage_service.py:229-269` (`delete_account_documents`)
  - `api/scripts/delete_intellipure_accounts.py`

## 4. Target implementation

Replace the current sweep at `routers/accounts.py:968-997`:

```python
# BEFORE (the current code — keep for diff reference)
collection_name = f"strategy_docs_{account_id}"
firestore_db = firestore.get_client()
collection_ref = firestore_db.collection(collection_name)
docs = collection_ref.list_documents()
deleted_docs_count = 0
for doc in docs:
    doc.delete()
    deleted_docs_count += 1
# ... per-collection book-keeping ...
```

With:

```python
# AFTER
try:
    firestore_db = firestore.get_client()
    account_doc_ref = firestore_db.collection("accounts").document(account_id)
    firestore_db.recursive_delete(account_doc_ref)
    cleanup_results["firestore_collection_deleted"] = True
    logger.info(f"Recursive-deleted accounts/{account_id} and all subcollections")
except Exception as e:
    logger.error(f"Failed to recursive-delete accounts/{account_id}: {e}")
    cleanup_results["cleanup_errors"].append(f"Firestore cleanup failed: {e}")
```

Rename `cleanup_results["firestore_collection_deleted"]` → `cleanup_results["firestore_account_deleted"]` for accuracy. Update the response model.

Notes:
- `recursive_delete()` is an official Firestore Python SDK method — verify signature against the installed `google-cloud-firestore` version at implementation start. Use the bulk-writer variant for throughput if available.
- GCS deletion still uses `storage_service.delete_account_documents(account_id, data_region)` — unchanged.
- Neo4j cascade delete — unchanged.

## 5. Implementation outline

| Action | File |
|---|---|
| Modify | `api/src/kene_api/routers/accounts.py` L968-997 — replace sweep with `recursive_delete` |
| Modify | `api/src/kene_api/routers/accounts.py` (the response building block around L1045-1058) — rename `firestore_collection_deleted` → `firestore_account_deleted`; update the response model in `api/src/kene_api/models/` |
| Modify | `api/scripts/delete_intellipure_accounts.py` L60-75 — mirror the same rewrite |
| Create | `api/tests/integration/test_account_deletion_no_orphans.py` |
| Update | `api/tests/test_cascade_delete.py` (if present) — update assertions for new cleanup_results keys |

## 6. Acceptance criteria

1. `DELETE /api/v1/accounts/{id}` calls `firestore.recursive_delete(db.collection("accounts").document(id))` once; no per-collection enumeration remains in `routers/accounts.py`.
2. The response body's `firestore_collection_deleted` field is renamed to `firestore_account_deleted` and reflects success/failure of the recursive delete.
3. After `DELETE /api/v1/accounts/test_account`, **no Firestore documents** exist under any `accounts/test_account/…` path (verified via Firestore admin API in the integration test).
4. After the same `DELETE`, **no GCS objects** exist under `gs://kene-docs-{env}-{region}/accounts/test_account/*` (verified via `bucket.list_blobs(prefix=...)`).
5. Existing Neo4j cascade deletion still runs (unchanged behavior).
6. `api/scripts/delete_intellipure_accounts.py` runs against a seeded account and leaves no residue (integration-level test, optional manual verification).
7. `pytest api/tests/integration/test_account_deletion_no_orphans.py` passes.
8. `pytest api/tests/` passes. `make lint` clean.
9. `cleanup_errors` in the response is empty for the happy path; populated with a clear message if `recursive_delete` raises.

## 7. Test plan

### New integration test (`api/tests/integration/test_account_deletion_no_orphans.py`)

```
setup:
  seed account "test_acc_deletion" with:
    - accounts/test_acc_deletion (doc)
    - accounts/test_acc_deletion/strategy_docs/swot (+ versions/1, versions/2)
    - accounts/test_acc_deletion/strategy_audit/audit_1, audit_2
    - accounts/test_acc_deletion/strategy_processing_state/state_1
    - accounts/test_acc_deletion/agent_analytics/m_1, m_2, m_3
    - accounts/test_acc_deletion/cost_aggregations/agg_1
    - accounts/test_acc_deletion/performance_profiles/prof_1
    - accounts/test_acc_deletion/monitoring_topics/default
    - accounts/test_acc_deletion/alert_configurations/default
    - gs://.../accounts/test_acc_deletion/file1.pdf, file2.png

act:
  DELETE /api/v1/accounts/test_acc_deletion

assert:
  - response.status == 200
  - response.body.firestore_account_deleted == true
  - response.body.gcs_documents_deleted >= 1
  - response.body.cleanup_errors == []
  - for each subcollection path listed above: db.list_documents() returns empty
  - bucket.list_blobs(prefix="accounts/test_acc_deletion/") returns empty
  - Neo4j: no nodes with account_id="test_acc_deletion"
```

### Update existing tests
- `api/tests/test_cascade_delete.py` — response-body field rename (`firestore_collection_deleted` → `firestore_account_deleted`)

### Manual verification
- In dev, create a realistic account via the normal onboarding flow; run it through for a day so analytics / audit / etc. exist; then call `DELETE` and verify via Firestore console + GCS console that nothing is orphaned

## 8. Risks & open questions

| Risk | Mitigation |
|---|---|
| `recursive_delete` latency exceeds timeout for a very large account | If seed-account test shows > 30s, dispatch via `BackgroundTasks` and return 202 Accepted; track status in a short-lived Firestore doc. Add a follow-up PR if this becomes an issue in staging |
| A new collection is added after DM-PRD-05 ships but not placed under `accounts/{id}/` | DM-PRD-06 verification checklist (and ongoing code review) enforces the Shape B convention. Documented in `api/CLAUDE.md` (by DM-PRD-00) |
| Pre-DM-PRD-05 behavior (sweep only strategy_docs) relied on for some ops reason | `routers/accounts.py:968-997` comments don't indicate any special semantics; historical behavior was incomplete by accident. Proceed with confidence; flag in PR description |
| `recursive_delete` doesn't exist in the pinned SDK version | Verify at implementation start: `from google.cloud.firestore import Client; Client.recursive_delete`. If missing, fall back to a manual iterative delete via `list_documents()` recursively (still one helper, called once) |

### Open questions

- **Q:** Should we expose a progress hook / logging for `recursive_delete`? → **Default: log-only.** Emit a "delete started" and "delete completed in Ns, M docs removed" log line. Revisit if operators need finer-grained progress.

## 9. Reference

- Parent plan: [`../multi-tenant-migration-plan.md`](../multi-tenant-migration-plan.md) §3.4 and §4 Phase 4
- Upstream projects: [DM-PRD-01](./DM-PRD-01-strategy-suite-migration.md), [DM-PRD-02](./DM-PRD-02-analytics-suite-migration.md), [DM-PRD-03](./DM-PRD-03-shape-d-split.md), [DM-PRD-04](./DM-PRD-04-shape-b-like-collapse.md)
- Downstream: [DM-PRD-06](./DM-PRD-06-verification-and-cutover.md)
- Decision: [Review 15 in DESIGN-REVIEW-LOG](../../../DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1) — Multi-Tenant Data Model Shape
- Firestore SDK reference: [`recursive_delete`](https://cloud.google.com/python/docs/reference/firestore/latest/google.cloud.firestore_v1.client.Client#google_cloud_firestore_v1_client_Client_recursive_delete)
- CLAUDE.md rules in scope: PY-1, PY-2, PY-3, PY-7; D-1, D-5; T-1, T-3, T-4, T-5, T-6
