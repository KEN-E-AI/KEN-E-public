# DM-PRD-05 — Deletion Sweep Rewrite (Account + User)

**Status:** Blocked
**Owner team:** Backend
**Blocked by:** DM-PRD-01, DM-PRD-02, DM-PRD-03, DM-PRD-04
**Parallel with:** —
**Blocks:** DM-PRD-06, DM-PRD-07
**Estimated effort:** 2–3 days

---

## 1. Context

KEN-E has two distinct delete-cascade gaps today:

**Account deletion.** The flow at `api/src/kene_api/routers/accounts.py:968-997` sweeps exactly **one** per-account collection (`strategy_docs_{account_id}`). Under Shape A this was explicit-by-design, but it meant every other per-account collection (`strategy_audit`, `agent_analytics`, `cost_aggregations`, `performance_profiles`, `strategy_processing_state`, plus the originally Shape B-like `monitoring_topics/{id}` and `alert_configurations/{id}`, plus the Shape D nested accounts-map inside `organizations/{org_id}`) was **orphaned** on account deletion. Latent GDPR issue.

**User deletion.** No `DELETE /api/v1/users/{user_id}` endpoint exists. The codebase has only per-org member-removal at `routers/firestore.py:2576` (which only edits the legacy `users.permissions.organizations.{org_id}` field — and after DM-PRD-07 lands, it operates on the new `organizations/{org_id}/members/{user_id}` subcollection but still doesn't delete the user record itself or sweep cross-account state). Three downstream PRDs already depend on a user-deletion sweep: CH-PRD-03 (cleans `users/{user_id}/chat_categories/*`), IN-PRD-05 (`on-user-removed` hook revoking integrations), and DM-PRD-07 (cleans cross-org/account `members/{user_id}` rows).

This project rewrites both. After DM-PRD-01–DM-PRD-04 migrate every per-account collection to `accounts/{account_id}/...`, **account deletion** becomes a single call:

```python
firestore.recursive_delete(db.collection("accounts").document(account_id))
```

**User deletion** becomes a coordinated sweep: collection-group cleanup of `members/{user_id}` rows across every org and account, IN-PRD-05's `on-user-removed` hook chained per affected account, deletion of user-scoped subcollections (`users/{user_id}/notification_status`, `users/{user_id}/preferences`, `users/{user_id}/chat_categories` — and any future user-scoped subcollection), then `recursive_delete(users/{user_id})` to reap the user doc itself.

This project ships both rewrites plus end-to-end tests that prove nothing is orphaned.

Can only start after **all four** data-migration projects (DM-PRD-01, DM-PRD-02, DM-PRD-03, DM-PRD-04) complete and verify — otherwise `recursive_delete` won't cover the un-migrated collections and the bug persists for a different shape.

## 2. Scope

### In scope

**Account deletion**
- Rewrite `api/src/kene_api/routers/accounts.py:968-997` to use `firestore.recursive_delete`
- Simplify `api/scripts/delete_intellipure_accounts.py` to match
- Keep existing GCS-prefix deletion via `storage_service.delete_account_documents` (unchanged)
- Keep existing Neo4j cascade deletion (unchanged)
- Add a new integration test `test_account_deletion_no_orphans.py` that seeds every migrated resource type and verifies nothing is orphaned after deletion

**User deletion (new)**
- Add `DELETE /api/v1/users/{user_id}` endpoint, super-admin-gated (`@ken-e.ai` only — full user-data purge is an internal/compliance action, not self-service)
- Add `delete_user_data(user_id)` orchestrator in `api/src/kene_api/services/user_deletion_service.py`:
  1. Collection-group query `members.where(user_id == user_id)` — for each match, delete the row and (if `parent_kind == "account"`) call IN-PRD-05's `on-user-removed(account_id, user_id)` hook synchronously
  2. Delete every user-scoped subcollection under `users/{user_id}` — explicitly enumerated: `notification_status`, `preferences`, `chat_categories`, plus a registered `USER_SUBCOLLECTIONS` list extended by future PRDs
  3. `firestore.recursive_delete(users/{user_id})` — reaps the user doc and any subcollections registered via `USER_SUBCOLLECTIONS`
  4. GCS prefix purge (no user-scoped GCS data exists today; the helper checks `gs://*/users/{user_id}/*` prefixes against an explicit allowlist and is a no-op until any future user-scoped GCS data is registered)
  5. Audit entry written to `organizations/{primary_org_id}/account_member_audit/` with `action=remove`, `actor_kind=super_admin` (best effort — if user has no org membership, audit is skipped)
- Add an integration test `test_user_deletion_no_orphans.py` that seeds members across 2 orgs × 3 accounts, plus 5 chat categories, plus 3 integration connections, plus notification preferences, runs `DELETE /api/v1/users/{user_id}`, and asserts every fixture is gone and IN-PRD-05's hook fired the right number of times

### Out of scope

- Any further data-model changes — DM-PRD-01–DM-PRD-04 own those
- Deletion retry / partial-failure semantics beyond what `recursive_delete` provides (the user-deletion orchestrator logs each step's outcome but does not roll back on partial failure — re-running is idempotent)
- GCS lifecycle rule changes
- Self-service user-deletion UI (super-admin-only API ships here; UI is a separate project)
- Firebase user-record deletion (Firebase Auth has its own deletion API; this PRD only purges KEN-E-side data — out-of-band Firebase deletion happens via the existing super-admin Firebase console flow)

## 3. Dependencies

- **DM-PRD-01:** `strategy_docs`, `strategy_audit`, `strategy_processing_state` live under `accounts/{id}/...`
- **DM-PRD-02:** `agent_analytics`, `cost_aggregations`, `performance_profiles` live under `accounts/{id}/...`
- **DM-PRD-03:** funnel/KPI config lives on `accounts/{id}` doc (or subcollection), not on `organizations/{org_id}`
- **DM-PRD-04:** `monitoring_topics` and `alert_configurations` live under `accounts/{id}/...`
- **IN-PRD-05** (consumer of the user-deletion orchestrator): provides the `on_user_removed(account_id, user_id)` hook this orchestrator calls per affected account. If IN-PRD-05 hasn't shipped when this PRD lands, the hook call is a no-op stub that becomes live when IN-PRD-05 merges.
- Existing files to study:
  - `api/src/kene_api/routers/accounts.py` (L900–L1070 — the delete-account endpoint)
  - `api/src/kene_api/services/storage_service.py:229-269` (`delete_account_documents`)
  - `api/scripts/delete_intellipure_accounts.py`
  - `api/src/kene_api/routers/firestore.py:2300–2620` (existing org-member endpoints — DM-PRD-07 retrofits these to write to the new subcollection paths; this PRD's user-deletion orchestrator removes the rows there too)
  - `api/src/kene_api/repositories/firestore_notification_repository.py:202-285` (paths for `users/{user_id}/notification_status` and `users/{user_id}/preferences`)

## 4. Target implementation

### 4.1 Account deletion

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
    cleanup_results["firestore_account_deleted"] = True
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

### 4.2 User deletion

```python
# api/src/kene_api/services/user_deletion_service.py

# Registry — extended by future PRDs that add user-scoped GCS prefixes / subcollections.
# Current entries are exhaustive as of DM-PRD-05 ship date.
USER_SUBCOLLECTIONS: list[str] = [
    "notification_status",   # firestore_notification_repository.py
    "preferences",           # firestore_notification_repository.py
    "chat_categories",       # CH-PRD-03
]

USER_GCS_PREFIXES: list[str] = []  # empty in v1; add via separate PR if any future user-scoped GCS data is introduced

async def delete_user_data(user_id: str, *, actor: AuthenticatedActor) -> UserDeletionResult:
    """Purge all KEN-E-side data for a user.

    Steps (each step is best-effort and logged; partial failure does not roll back):
      1. Resolve every (parent_kind, parent_id) where this user has a members row.
      2. For each (account_id, user_id), call IN-PRD-05's on_user_removed hook.
      3. Delete every members row across orgs + accounts (collection-group sweep).
      4. recursive_delete(users/{user_id}) — reaps user doc + every subcollection in USER_SUBCOLLECTIONS.
      5. GCS prefix purge for every prefix in USER_GCS_PREFIXES (no-op in v1).
      6. Audit entry (best effort — written to the user's primary org's account_member_audit).

    Idempotent: re-running on an already-purged user_id is a no-op (recursive_delete on
    a missing doc is a no-op; collection-group sweep returns zero matches).
    """
    result = UserDeletionResult(user_id=user_id)

    # 1. Discover affected scopes via collection-group queries
    org_member_rows = await collection_group("members") \
        .where("user_id", "==", user_id) \
        .where("parent_kind", "==", "organization") \
        .stream()
    account_member_rows = await collection_group("members") \
        .where("user_id", "==", user_id) \
        .where("parent_kind", "==", "account") \
        .stream()

    # 2. Fire IN-PRD-05's hook per affected account (synchronous; any failure logged + continues)
    for row in account_member_rows:
        account_id = row.parent.parent.id
        try:
            await on_user_removed(account_id=account_id, user_id=user_id)
            result.integrations_hook_fired += 1
        except Exception as e:
            logger.exception(f"on_user_removed failed for account_id={account_id}")
            result.errors.append(f"integrations_hook[{account_id}]: {e}")

    # 3. Delete all members rows
    for row in [*org_member_rows, *account_member_rows]:
        await row.reference.delete()
        result.member_rows_deleted += 1

    # 4. Reap user doc + registered subcollections
    user_ref = firestore_db.collection("users").document(user_id)
    await firestore_db.recursive_delete(user_ref)
    result.user_doc_deleted = True

    # 5. GCS purge (v1: no-op)
    for prefix in USER_GCS_PREFIXES:
        await storage_service.delete_user_prefix(prefix.format(user_id=user_id))
        result.gcs_prefixes_purged += 1

    # 6. Best-effort audit
    if org_member_rows:
        primary_org_id = org_member_rows[0].parent.parent.id
        try:
            await write_audit(
                parent_kind="organization",
                parent_id=primary_org_id,
                audit_subcollection="account_member_audit",
                resource_type="org_member",
                resource_id=user_id,
                action="remove",
                actor=actor,
                before_state={"user_id": user_id},
                after_state=None,
            )
        except Exception:
            logger.warning("Audit write failed during user deletion; not blocking")

    return result
```

### 4.3 New endpoint

```
DELETE /api/v1/users/{user_id}

Auth: super-admin only (Firebase claim email ends with "@ken-e.ai")
Returns 200 with UserDeletionResult body.
On any 4xx auth failure: 403 with {error: "super_admin_required"}.
```

This is intentionally a thin wrapper — all logic lives in `user_deletion_service`.

## 5. Implementation outline

| Action | File |
|---|---|
| Modify | `api/src/kene_api/routers/accounts.py` L968-997 — replace sweep with `recursive_delete` |
| Modify | `api/src/kene_api/routers/accounts.py` (the response building block around L1045-1058) — rename `firestore_collection_deleted` → `firestore_account_deleted`; update the response model in `api/src/kene_api/models/` |
| Modify | `api/scripts/delete_intellipure_accounts.py` L60-75 — mirror the same rewrite |
| Create | `api/src/kene_api/services/user_deletion_service.py` — `delete_user_data` orchestrator + `USER_SUBCOLLECTIONS` registry |
| Modify | `api/src/kene_api/routers/users.py` — add `DELETE /api/v1/users/{user_id}` super-admin-gated endpoint calling `delete_user_data` |
| Create | `api/src/kene_api/models/user_deletion.py` — `UserDeletionResult` Pydantic model |
| Create | `api/tests/integration/test_account_deletion_no_orphans.py` |
| Create | `api/tests/integration/test_user_deletion_no_orphans.py` |
| Update | `api/tests/test_cascade_delete.py` (if present) — update assertions for new cleanup_results keys | **Resolved 2026-05-15 (DM-51): no-op — the specific file `api/tests/test_cascade_delete.py` was never created.** Two related files exist but neither asserts on Firestore response fields: `api/scripts/test_cascade_delete.py` is a manual HTTP+Neo4j smoke-test script; `api/tests/unit/test_accounts_cascade_delete.py` tests Neo4j cascade logic only. Neither references `firestore_collection_deleted` or `deleted_docs_count`. Post-DM-47 contract (AC-1/AC-2) is covered by `api/tests/integration/test_agent_config_overlay.py::TestAccountDeletionSweep`. Comprehensive Shape-B no-orphan coverage ships under DM-50. |

## 6. Acceptance criteria

### Account deletion
1. `DELETE /api/v1/accounts/{id}` calls `firestore.recursive_delete(db.collection("accounts").document(id))` once; no per-collection enumeration remains in `routers/accounts.py`.
2. The response body's `firestore_collection_deleted` field is renamed to `firestore_account_deleted` and reflects success/failure of the recursive delete.
3. After `DELETE /api/v1/accounts/test_account`, **no Firestore documents** exist under any `accounts/test_account/…` path (verified via Firestore admin API in the integration test).
4. After the same `DELETE`, **no GCS objects** exist under `gs://kene-docs-{env}-{region}/accounts/test_account/*` (verified via `bucket.list_blobs(prefix=...)`).
5. Existing Neo4j cascade deletion still runs (unchanged behavior).
6. `api/scripts/delete_intellipure_accounts.py` runs against a seeded account and leaves no residue.
7. `cleanup_errors` in the response is empty for the happy path; populated with a clear message if `recursive_delete` raises.

### User deletion
8. `DELETE /api/v1/users/{user_id}` returns `403` for non-super-admin callers.
9. `DELETE /api/v1/users/{user_id}` for a seeded user with members rows in 2 orgs × 3 accounts:
   - All 5 `members/{user_id}` rows are gone (verified via collection-group query).
   - IN-PRD-05's `on_user_removed` hook fired exactly 3 times (once per affected account).
   - `users/{user_id}` doc is gone.
   - All entries in `users/{user_id}/notification_status`, `users/{user_id}/preferences`, `users/{user_id}/chat_categories` are gone.
   - Response body's `UserDeletionResult` has accurate counts.
10. Re-running `DELETE /api/v1/users/{user_id}` on an already-purged user is a no-op (200 with zero-count `UserDeletionResult`).
11. `USER_SUBCOLLECTIONS` registry is documented in `user_deletion_service.py` with one comment line per entry indicating the owning PRD; future PRDs that add user-scoped subcollections must update the registry (CI grep enforces this — see DM-PRD-06 §4.2).
12. `pytest api/tests/integration/test_account_deletion_no_orphans.py api/tests/integration/test_user_deletion_no_orphans.py` passes.
13. `pytest api/tests/` passes. `make lint` clean.

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
    - accounts/test_acc_deletion/members/u_alice, u_bob (DM-PRD-07)
    - accounts/test_acc_deletion/project_plan_audit/aud_1 (DM-PRD-07)
    - accounts/test_acc_deletion/integrations_audit/aud_1 (DM-PRD-07)
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

### New integration test (`api/tests/integration/test_user_deletion_no_orphans.py`)

```
setup:
  seed user "u_carol" with:
    - users/u_carol (doc)
    - users/u_carol/notification_status/n_1, n_2
    - users/u_carol/preferences/notifications
    - users/u_carol/chat_categories/cat_research, cat_outreach, cat_admin
    - organizations/org_acme/members/u_carol (role=member)
    - organizations/org_widgets/members/u_carol (role=admin)
    - accounts/acc_acme_a/members/u_carol (role=editor)
    - accounts/acc_acme_b/members/u_carol (role=viewer)
    - accounts/acc_widgets_main/members/u_carol (role=admin)
    - accounts/acc_acme_a/platform_connections/conn_ga (with tokens — IN-PRD-01)
    - accounts/acc_acme_b/platform_connections/conn_ga (with tokens)
    - accounts/acc_widgets_main/platform_connections/conn_ga (with tokens)
  mock IN-PRD-05's on_user_removed hook to count invocations.

act:
  DELETE /api/v1/users/u_carol  (as super_admin)

assert:
  - response.status == 200
  - response.body.member_rows_deleted == 5
  - response.body.integrations_hook_fired == 3
  - response.body.user_doc_deleted == true
  - on_user_removed mock called with each of (acc_acme_a, acc_acme_b, acc_widgets_main)
  - users/u_carol/* — no docs anywhere
  - organizations/org_acme/members/u_carol — gone
  - organizations/org_widgets/members/u_carol — gone
  - accounts/acc_acme_a/members/u_carol — gone (and so on)
  - audit entry exists at organizations/org_acme/account_member_audit/{audit_id} or organizations/org_widgets/account_member_audit/{audit_id}

  Re-run DELETE /api/v1/users/u_carol → response.body.member_rows_deleted == 0, no errors.
```

### Update existing tests
- `api/tests/test_cascade_delete.py` — response-body field rename (`firestore_collection_deleted` → `firestore_account_deleted`). **Resolved 2026-05-15 (DM-51): no-op — the specific file `api/tests/test_cascade_delete.py` was never created.** Two related files exist but neither asserts on Firestore response fields (`api/scripts/test_cascade_delete.py` is a manual HTTP+Neo4j smoke-test script; `api/tests/unit/test_accounts_cascade_delete.py` tests Neo4j cascade logic only). Post-DM-47 rename semantics are asserted in `api/tests/integration/test_agent_config_overlay.py::TestAccountDeletionSweep`. Comprehensive Shape-B no-orphan coverage ships under DM-50.

### Manual verification
- In dev, create a realistic account via the normal onboarding flow; run it through for a day so analytics / audit / etc. exist; then call `DELETE` and verify via Firestore console + GCS console that nothing is orphaned

## 8. Risks & open questions

| Risk | Mitigation |
|---|---|
| `recursive_delete` latency exceeds timeout for a very large account | If seed-account test shows > 30s, dispatch via `BackgroundTasks` and return 202 Accepted; track status in a short-lived Firestore doc. Add a follow-up PR if this becomes an issue in staging |
| User has thousands of `members` rows (large multi-tenant operator) | The collection-group sweep is paginated; no single-batch limit. Test with 100-row fixture; revisit if real-world has >1k. |
| A new collection is added after DM-PRD-05 ships but not placed under `accounts/{id}/` | DM-PRD-06 verification checklist (and ongoing code review) enforces the Shape B convention. Documented in `api/CLAUDE.md` (by DM-PRD-00) |
| A new user-scoped subcollection is added without registering in `USER_SUBCOLLECTIONS` | DM-PRD-06 §4.2 grep enforces presence in the registry; failing CI on any new `users/{user_id}/{name}/` subcollection write where `name` is not in the registry |
| IN-PRD-05's `on_user_removed` hook is slow (per-account → 3-platform connection revoke each) | Hook calls run sequentially today; switch to `asyncio.gather` if user has >5 affected accounts. Profile during integration test. |
| `recursive_delete` doesn't exist in the pinned SDK version | Verify at implementation start. If missing, fall back to a manual iterative delete via `list_documents()` recursively (still one helper, called once) |
| Pre-DM-PRD-05 behavior (sweep only strategy_docs) relied on for some ops reason | `routers/accounts.py:968-997` comments don't indicate any special semantics; historical behavior was incomplete by accident. Proceed with confidence; flag in PR description |

### Open questions

- **Q:** Should we expose a progress hook / logging for `recursive_delete`? → **Default: log-only.** Emit a "delete started" and "delete completed in Ns, M docs removed" log line. Revisit if operators need finer-grained progress.
- **Q:** Should user deletion be soft (tombstone) before hard? → **No.** Super-admin-gated already gates against accidental clicks; soft-delete adds complexity and an additional state to migrate later. If a user-recoverable "deactivate" is needed, that's a separate product feature.
- **Q:** Does Firebase user-record deletion happen here or out-of-band? → **Out-of-band.** This PRD only purges KEN-E-side data. Operators delete the Firebase user via the Firebase console after this endpoint succeeds.

## 9. Reference

- Parent plan: [`../multi-tenant-migration-plan.md`](../multi-tenant-migration-plan.md) §3.4 and §4 Phase 4
- Upstream projects: [DM-PRD-01](./DM-PRD-01-strategy-suite-migration.md), [DM-PRD-02](./DM-PRD-02-analytics-suite-migration.md), [DM-PRD-03](./DM-PRD-03-shape-d-split.md), [DM-PRD-04](./DM-PRD-04-shape-b-like-collapse.md)
- Downstream: [DM-PRD-06](./DM-PRD-06-verification-and-cutover.md), [DM-PRD-07](./DM-PRD-07-approval-workflow-and-audit.md)
- Consumers of the user-deletion sweep: [IN-PRD-05](../../integrations/projects/IN-PRD-05-reauth-lifecycle.md), [CH-PRD-03](../../chat/projects/CH-PRD-03-session-categories.md), [DM-PRD-07](./DM-PRD-07-approval-workflow-and-audit.md)
- Decision: [Review 15 in DESIGN-REVIEW-LOG](../../../DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1) — Multi-Tenant Data Model Shape
- Firestore SDK reference: [`recursive_delete`](https://cloud.google.com/python/docs/reference/firestore/latest/google.cloud.firestore_v1.client.Client#google_cloud_firestore_v1_client_Client_recursive_delete)
- CLAUDE.md rules in scope: PY-1, PY-2, PY-3, PY-7; D-1, D-5; T-1, T-3, T-4, T-5, T-6
