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
| DM-PRD-00's `MigrateConfig` doesn't support "whole collection → subcollection with fixed doc-id" | Extend DM-PRD-00 (preferred) or write one-off script (fallback). Decide at Phase 1 kickoff |
| `MonitoringTopics` Pydantic model has a `doc_id` field tied to the old account-id-as-doc-id pattern | Check the model — if it embeds the account_id in the doc-id assumption, update to use a separate `topic_id` or `"default"` value. Document the decision in a short PR comment |
| Ops scripts that iterate `monitoring_topics` at the root level break | `rg -n 'collection\("monitoring_topics"\)' api/ app/ scripts/` — address every hit |

### Open questions

- **Q:** Should the migration preserve the original `account_id` as `topic_id` (so the destination is `accounts/{id}/monitoring_topics/{id}`)? → **Default: no, use `"default"`.** A fixed doc-id is cleaner given it's always one-doc-per-account today. If the model evolves to support multiple topics per account, new records mint UUIDs; the legacy migrated doc stays at `"default"`.
- **Q:** Does `alert_configurations` have the same "one doc per account" invariant? → **Likely yes** based on `alert_manager.py:202` (`.document(self.account_id).set(...)`). Confirm at implementation start by reading the class.

## 9. Reference

- Parent plan: [`../multi-tenant-migration-plan.md`](../multi-tenant-migration-plan.md) §3.2, §3.5
- Upstream: [DM-PRD-00](./DM-PRD-00-migration-foundation.md)
- Downstream: [DM-PRD-05](./DM-PRD-05-deletion-sweep-rewrite.md)
- Notion decision: [Multi-Tenant Data Model Shape](https://www.notion.so/34830fd653028177bc0dc2a1637c7f60)
- CLAUDE.md rules in scope: PY-1, PY-2, PY-7; T-1, T-3, T-4
