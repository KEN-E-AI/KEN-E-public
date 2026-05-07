# DM-PRD-04 — Shape B-like Collapse

**Status:** Blocked
**Owner team:** Backend / Strategy
**Blocked by:** DM-PRD-00
**Parallel with:** DM-PRD-01, DM-PRD-02, DM-PRD-03
**Blocks:** DM-PRD-05
**Estimated effort:** 1–2 days

---

## 1. Context

Two collections in the codebase use a "Shape B-like" pattern — a global collection where each document's ID is an `account_id`:

- `monitoring_topics/{account_id}` (doc)
- `alert_configurations/{account_id}` (doc)

Functionally this is equivalent to a degenerate Shape B, but it's inconsistent with the canonical `accounts/{account_id}/{resource}/...` layout. This project collapses both into true Shape B subcollections:

- `monitoring_topics/{account_id}` → `accounts/{account_id}/monitoring_topics/{topic_id}`
- `alert_configurations/{account_id}` → `accounts/{account_id}/alert_configurations/{config_id}`

**This is the smallest and most cosmetic project in the set** — buys consistency across the codebase, not correctness. Included in v1 per the migration plan to avoid leaving a fourth data shape behind after DM-PRD-01–DM-PRD-03 complete.

## 2. Scope

### In scope
- Migrate `monitoring_topics/{account_id}` docs → `accounts/{account_id}/monitoring_topics/{topic_id}` subcollection
- Migrate `alert_configurations/{account_id}` docs → `accounts/{account_id}/alert_configurations/{config_id}` subcollection
- Update call sites in monitoring + alert-manager code
- Update tests

### Out of scope
- Any change to the monitoring or alerts feature behavior (purely a storage move)
- `MONITORING_TOPICS_COLLECTION` / similar constants at the module level — these may become per-account path helpers; module-level constants that still make sense (like `OAUTH_STATES_COLLECTION` for the unrelated global `oauth_states` collection) are untouched

## 3. Dependencies

- **DM-PRD-00:** `migrate_to_shape_b.py` merged
- Existing files to study:
  - `api/src/kene_api/services/monitoring_sync_service.py`
  - `api/src/kene_api/services/graph_sync_service.py` (monitoring_topics writes at L2298, 2314, 2883, 2901)
  - `api/src/kene_api/routers/monitoring_topics.py`
  - `app/adk/agents/strategy_agent/alert_manager.py`

## 4. Call-site inventory

Sourced from [`../multi-tenant-migration-plan.md`](../multi-tenant-migration-plan.md) §3.2 + §3.5:

### monitoring_topics
| File | Lines | Change |
|---|---|---|
| `api/src/kene_api/services/monitoring_sync_service.py` | L12 (`MONITORING_TOPICS_COLLECTION` constant), full file (reads/writes) | Collection constant replaced by path-builder function |
| `api/src/kene_api/services/graph_sync_service.py` | 2298, 2314, 2883, 2901 | `collection="monitoring_topics", document_id=account_id` → `collection path = accounts/{account_id}/monitoring_topics`, `document_id=topic_id` |
| `api/src/kene_api/routers/monitoring_topics.py` | L91–92 (module-level constants), plus all handler paths | Path update everywhere it references `monitoring_topics/{account_id}` |

### alert_configurations
| File | Lines | Change |
|---|---|---|
| `app/adk/agents/strategy_agent/alert_manager.py` | 145–148, 202, 486, 641 | `collection("alert_configurations").document(self.account_id)` → `collection(f"accounts/{self.account_id}/alert_configurations").document(config_id)` |

### Doc-ID migration note

Today, the doc at `monitoring_topics/{account_id}` holds a single record for the account. Under Shape B, we need to pick a doc ID inside `accounts/{account_id}/monitoring_topics/`. Simplest approach: use a stable ID like `"default"` or `"primary"`, or mint a UUID if the model expects many. Decide during implementation based on the existing data model — if there's always one monitoring-topics record per account, use a fixed ID `"default"`. Same for `alert_configurations`.

The migration script needs to write to `accounts/{id}/monitoring_topics/default` (not `accounts/{id}/monitoring_topics/{account_id}`) — update the MigrateConfig accordingly (see §5).

## 5. Implementation outline

### Phase 1 — Register resources (with custom destination doc-id)

Add to `api/scripts/_migrate_shape_b/resources.py`:

```python
# Both of these are "one doc per account" — rename the source-doc-id `{account_id}`
# to a stable `"default"` when moving to the subcollection.
RESOURCES["monitoring_topics"] = MigrateConfig(
    old_prefix="",                                  # whole collection, not a prefix
    new_subcollection="monitoring_topics",
    has_versions=False,
    source_is_single_collection=True,               # new flag — see below
    destination_doc_id="default",                   # new flag — see below
)
RESOURCES["alert_configurations"] = MigrateConfig(
    old_prefix="",
    new_subcollection="alert_configurations",
    has_versions=False,
    source_is_single_collection=True,
    destination_doc_id="default",
)
```

**DM-PRD-00 dependency:** the DM-PRD-00 script's `MigrateConfig` signature needs two additional fields — `source_is_single_collection: bool` and `destination_doc_id: str`. Coordinate with the DM-PRD-00 team to include these; if DM-PRD-00 has already merged, this project files a small follow-up PR to DM-PRD-00 before Phase 1 runs. Alternative: this project bypasses the generic script and writes a one-off migration (`api/scripts/migrate_monitoring_topics_and_alerts.py`). Recommend the generic-extension approach if the DM-PRD-00 PR is still in review; otherwise write the one-off.

### Phase 2 — Code migration

Per resource:

1. Update all read sites to `accounts/{account_id}/{resource}/default` (or iterate if the model supports multiple topics/configs per account).
2. Update all write sites similarly.
3. Update tests.
4. Run `pytest` green.

### Phase 3 — Data migration (dev)

```bash
python api/scripts/migrate_to_shape_b.py --resource=monitoring_topics --dry-run
python api/scripts/migrate_to_shape_b.py --resource=monitoring_topics
python api/scripts/migrate_to_shape_b.py --resource=monitoring_topics --confirm-delete

python api/scripts/migrate_to_shape_b.py --resource=alert_configurations
python api/scripts/migrate_to_shape_b.py --resource=alert_configurations --confirm-delete
```

### Phase 4 — Verification

- Monitoring endpoints (`GET /api/v1/accounts/{id}/monitoring_topics`) return same data post-migration
- Alert manager reads configs from the new path
- No `monitoring_topics/{some_account_id}` docs remain at the root level
- No `alert_configurations/{some_account_id}` docs remain at the root level

## 6. Acceptance criteria

1. All call sites in §4 reference `accounts/{account_id}/monitoring_topics/default` and `accounts/{account_id}/alert_configurations/default` (or the agreed-upon doc-ID pattern).
2. In dev Firestore, the root-level `monitoring_topics` and `alert_configurations` collections are empty (or deleted).
3. Monitoring endpoints return the same data as pre-migration for a seeded account (before-after diff).
4. Alert manager loads + saves alert configurations correctly (validated by a unit test that exercises `AlertManager(account_id=...).load()` and `.save()`).
5. `pytest api/tests/ app/adk/agents/strategy_agent/tests/` passes. `make lint` clean.
6. `MONITORING_TOPICS_COLLECTION = "monitoring_topics"` constants at `api/src/kene_api/services/monitoring_sync_service.py:12` and `api/src/kene_api/routers/monitoring_topics.py:91` either: (a) removed if no longer used, or (b) repurposed as the subcollection name (`"monitoring_topics"`) with a clear comment.

## 7. Test plan

### Unit tests (update existing)
- `api/tests/test_monitoring_topics*.py` — update fixtures
- `api/tests/unit/test_monitoring_topics_concepts.py` — update fixtures
- Alert manager tests — update fixtures for the new path

### Integration tests
- Seed an account with a `monitoring_topics` doc under the old pattern, run the migration script, confirm the new path has the data and the old collection is empty
- Same for `alert_configurations`

### Manual verification
- Hit the monitoring endpoint in dev and assert identical JSON before and after migration

## 8. Risks & open questions

| Risk | Mitigation |
|---|---|
| DM-PRD-00's `MigrateConfig` doesn't support "whole collection → subcollection with fixed doc-id" | Resolved at DM-PRD-00 merge: `MigrateConfig` already ships `source_is_single_collection: bool` and `destination_doc_id: str | None` fields (`api/scripts/_migrate_shape_b/config.py:51-52`). No follow-up PR needed. |
| `MonitoringTopics` Pydantic model has a `doc_id` field tied to the old account-id-as-doc-id pattern | **Resolved 2026-05-06 (DM-21):** `MonitoringTopics` (`monitoring_models.py:146`) carries `account_id` as a **payload field** only; it has no `topic_id`, `id`, or `doc_id` field. The one-doc-per-account invariant lives entirely in the storage layer (`monitoring_sync_service.py:50,87,112`; `graph_sync_service.py:2298,2314,2883,2901`; `routers/monitoring_topics.py` ~30 sites). No model edit required. |
| Ops scripts that iterate `monitoring_topics` at the root level break | `rg -n 'collection\("monitoring_topics"\)' api/ app/ scripts/` — address every hit |
| Nested `alert_configurations/{account_id}/alerts/*` subcollection is not covered by the DM-PRD-00 runner's `has_versions=True` branch | `alert_manager.py:486-488` writes individual alert events to `alert_configurations/{account_id}/alerts/` (auto-ID); `alert_manager.py:641` reads with a 24 h `cutoff_time` filter. The `has_versions=True` flag hardcodes `"versions"` as the nested name and would not migrate `alerts`. Additionally, `batch.delete(doc.reference)` in the `--confirm-delete` step does **not** cascade-delete Firestore subcollections — the source `alerts/` data at `alert_configurations/{account_id}/alerts/*` becomes an orphan. DM-22 must decide: (a) extend `MigrateConfig` with a generic `nested_subcollection: str \| None` field that also `recursive_delete`s the nested source, (b) add an explicit `recursive_delete(alert_configurations/{account_id})` call in `--confirm-delete` to clean up the orphan (acceptable because alert history is at most 24 h old by design), or (c) document the orphan as a known data remnant for a post-migration ops sweep. DM-25 must update write/read paths to `accounts/{account_id}/alert_configurations/default/alerts/*`. |
| `AlertManager` reads/writes Firestore directly via a raw client, bypassing API HTTP auth | `alert_manager.py:146-150` (read) and `:202` (write) use `self.db.collection("alert_configurations").document(self.account_id)` with no `has_account_access` check — isolation relies entirely on the `account_id` string passed to `AlertManager.__init__`. DM-25 must update these paths to the Shape B layout **atomically** with the migration cutover to avoid a split-brain window where the API serves migrated paths while the ADK agent still writes to the legacy root collection. |
| `update_accounts_with_industry` derives write target from the document payload field, not the Firestore doc ID | The fan-out calls `firestore.update_document(document_id=doc["account_id"], ...)` — a corrupt or mismatched `account_id` payload field redirects the write to a different tenant's document. DM-23/DM-25 must update this fan-out to the new Shape B path and derive the account scope from the Firestore document path, not the payload field. |

### Open questions

- **Q:** Should the migration preserve the original `account_id` as `topic_id` (so the destination is `accounts/{id}/monitoring_topics/{id}`)? → **Default: no, use `"default"`.** A fixed doc-id is cleaner given it's always one-doc-per-account today. If the model evolves to support multiple topics per account, new records mint UUIDs; the legacy migrated doc stays at `"default"`.

  **Resolved 2026-05-06 (DM-21):** Audit confirms the canonical doc-id is `"default"` for both resources. The one-doc-per-account invariant is storage-layer-only: `MonitoringTopics` (`monitoring_models.py:146`) carries `account_id` as a payload field with no `topic_id` or `doc_id` field, so no Pydantic model edit is required. All monitored call sites (30+ in `routers/monitoring_topics.py`, `monitoring_sync_service.py:50,87,112`, `graph_sync_service.py:2298,2314,2883,2901`) use `document_id=account_id` directly on the storage layer; none asserts `doc.id == account_id` in test logic.

- **Q:** Does `alert_configurations` have the same "one doc per account" invariant? → **Likely yes** based on `alert_manager.py:202` (`.document(self.account_id).set(...)`). Confirm at implementation start by reading the class.

  **Resolved 2026-05-06 (DM-21):** Confirmed. `alert_manager.py:202` calls `.document(self.account_id).set(config)` (write); `alert_manager.py:146-150` calls `.document(self.account_id).get()` (read). The payload is a `Dict[str, Any]` (no Pydantic model) where `account_id` is a content field (`_get_default_config()` at L173 — `"account_id": self.account_id`), so the doc-id is fully decoupled from content. Migration to `accounts/{account_id}/alert_configurations/default` requires no model change. **Caveat:** `alert_manager.py:486` writes individual alert events to a nested `alerts/` subcollection (`alert_configurations/{account_id}/alerts/`) and `alert_manager.py:641` reads from it; this nested subcollection is not covered by the standard `MigrateConfig` runner — see new Risk row above.

## 9. Reference

- Parent plan: [`../multi-tenant-migration-plan.md`](../multi-tenant-migration-plan.md) §3.2, §3.5
- Upstream: [DM-PRD-00](./DM-PRD-00-migration-foundation.md)
- Downstream: [DM-PRD-05](./DM-PRD-05-deletion-sweep-rewrite.md)
- Decision: [Review 15 in DESIGN-REVIEW-LOG](../../../DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1) — Multi-Tenant Data Model Shape
- CLAUDE.md rules in scope: PY-1, PY-2, PY-7; T-1, T-3, T-4
