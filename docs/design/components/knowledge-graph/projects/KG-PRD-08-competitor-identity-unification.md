# KG-PRD-08 — Competitor Identity Unification (Monitoring Entries → Graph `node_id`)

**Status:** Draft — pending review
**Owner team:** [KEN-E] Knowledge Graph
**Blocked by:** KG-PRD-01, KG-PRD-02
**Parallel with:** KG-PRD-05 (coordinate on `GraphSyncService`)
**Estimated effort:** 4–6 days
**Origin:** DM-91 wave-7 (PR #807) deferred product follow-up; tracked on KG-1.

> **Decision (2026-06-03): Option 2 — graph-canonical (hybrid).** The Neo4j `:Competitor` node is the single source of truth for competitor *identity*. Firestore monitoring `competitor_entries` are keyed by the graph node's `node_id` and produced via `MonitoringSyncService`; the monitoring entry still owns its *watch-config* (`keywords`, `website`). This is a hybrid — the graph owns identity + uniqueness, monitoring owns watch-config keyed by `node_id` — not a pure read-only mirror. The previously-proposed `409`-on-duplicate guard becomes unnecessary: uniqueness is structural at the graph node.

---

## 1. Context

Competitor data lives in two stores: the Neo4j `:Competitor` node (created via the graph CRUD endpoint, `routers/knowledge_graph/competitive.py:53`) and the Firestore monitoring document's `competitor_entries[]` array (under `accounts/{account_id}/monitoring_topics/default`). Today that array is written by **three paths that disagree on identity**:

| Write path | Sets `node_id`? | Dedup rule |
|---|---|---|
| `monitoring_topics.add_competitor` — `POST /monitoring-topics/{account_id}/competitors` (`monitoring_topics.py:748-750`) | Yes, if the request body includes it | **none** — appends unconditionally |
| `MonitoringSyncService.sync_competitor_to_monitoring` (`services/monitoring_sync_service.py:73-84`) | **No — drops it entirely** | dedupes on `name` (`:80-83`) |
| `monitoring_topics.update_competitor` — `PUT .../{competitor_index}` (`monitoring_topics.py:831`) | — | edits `keywords` in place, addressed by array index |

The consequence: a competitor created through the graph endpoint syncs **down** as a name-only entry with no `node_id` (`monitoring_sync_service.py:73-77`), while one added through the direct endpoint may carry a `node_id`, and neither sees the other's duplicates. Downstream consumers then dedupe inconsistently. This surfaced as the wave-7 documenting test `test_add_competitor_appends_when_name_exists` (`api/tests/test_monitoring_topics_endpoints.py:364`), which deliberately pins the broken append behavior with a "tracked product follow-up" note.

KG-PRD-01 + KG-PRD-02 establish `node_id` as the canonical identity for every `:KGNode` (including `:Competitor`) and retain the graph CRUD endpoint as the standard write path. This PRD completes that picture for the *monitoring projection*: it makes the graph the only place a competitor is born, fixes the sync to carry and key on `node_id`, migrates legacy name-only entries, and rewires callers. `keywords` remains monitoring-owned and independently editable (auto-filled at sync, `monitoring_sync_service.py:71`), which is why the end state is a hybrid rather than a mirror.

## 2. Scope

### In scope
- **Sync becomes node_id-keyed.** Extend `MonitoringSyncService.sync_competitor_to_monitoring` to accept and persist the competitor's `node_id`, dedupe on it, and stop producing name-only entries. Update the graph endpoint caller (`competitive.py:77`) to pass `created_competitor.node_id` (it already has it).
- **Graph becomes the sole create path.** Deprecate the direct-append `monitoring_topics.add_competitor` (`:694`). During transition it delegates to the graph create path (creating the `:Competitor` node + letting the sync project it) rather than appending; a later release removes the route. (Transition vs. hard-remove — see §9 open question.)
- **Migration.** Backfill `node_id` onto legacy name-only `competitor_entries` by matching `name` to the account's graph `:Competitor.display_name`. Idempotent, Shape-B compliant, reuses the KG-PRD-01 migration-runner pattern where applicable.
- **Rewire callers.** Repoint the frontend monitoring "add competitor" flow from `monitoringTopicsService.ts:35` (endpoint B) to `competitorService.create` (`services/competitorService.ts:67`, endpoint A). Audit + rewire any automation/agent caller of B.
- **Tests.** Replace `test_add_competitor_appends_when_name_exists` with a test asserting the new behavior; add sync-node_id-keying + migration coverage; keep the `api-unit-tests` gate green.

### Out of scope
- The graph competitor CRUD endpoint's external contract (`competitive.py`) — unchanged except for the internal node_id-to-sync wiring. This PRD routes everything *toward* it.
- Keyword-editing semantics on monitoring entries — `keywords` stays monitoring-owned; `update_competitor` keyword editing remains (though its array-index addressing is flagged in §9).
- The other competitive node types (`CompetitorTactic` / `Strength` / `Weakness` / `SubstituteProduct`).
- Final hard removal of the deprecated `CompetitorEntry.name` field — kept read-only for back-compat until the migration is verified in all environments; full removal is a follow-up.

## 3. Dependencies

- **KG-PRD-01** — `:KGNode` label + `kg_node_id_unique` constraint; without the node_id uniqueness constraint, "graph owns uniqueness" has no enforcement floor.
- **KG-PRD-02** — provenance spine + `GraphSyncService.create_node`; the graph create path this PRD funnels everything through.
- **Data Management** — the legacy-entry migration follows the Shape-B convention; DM-PRD-05's `recursive_delete` already covers `accounts/{account_id}/monitoring_topics` on account deletion, so no per-collection sweep edits are needed.
- **KG-PRD-05** — also touches `GraphSyncService`; coordinate landing order so the sync changes here don't conflict with the research-path refactor.
- **Files to study/modify:**
  - `api/src/kene_api/services/monitoring_sync_service.py` — the sync; primary change surface.
  - `api/src/kene_api/routers/knowledge_graph/competitive.py:52-86` — graph create; pass node_id into sync.
  - `api/src/kene_api/routers/monitoring_topics.py:694-770` — direct create (deprecate); `:773-855` update; `:857-905` delete (both addressed by array index).
  - `api/src/kene_api/models/monitoring_models.py:77-110` — `CompetitorEntry` (node_id authoritative; name deprecated).
  - `frontend/src/services/monitoringTopicsService.ts:35`, `frontend/src/services/competitorService.ts:67`, `frontend/src/queries/competitors.ts`.

## 4. Data contract

`CompetitorEntry` (`monitoring_models.py:77`) — no shape change, semantics tightened:
- `node_id: str` — becomes the authoritative key; effectively required for all entries post-migration (model stays `str | None` until the `name` field is removed in the follow-up).
- `name: str | None` — DEPRECATED; read-only back-compat only; no longer written by any path.
- `keywords`, `website` — unchanged; monitoring-owned watch-config.

`MonitoringSyncService.sync_competitor_to_monitoring` signature gains `competitor_node_id: str` and keys add/remove/dedup on it instead of `competitor_name`.

## 5. Implementation outline

| Action | File |
|---|---|
| Modify | `services/monitoring_sync_service.py` — add `competitor_node_id`; persist it on the `CompetitorEntry`; dedupe add (`:80-83`) and filter remove (`:104-108`) on `node_id`; stop minting name-only entries |
| Modify | `routers/knowledge_graph/competitive.py:77` — pass `created_competitor.node_id` into the sync (and on the delete-path sync, `:265`) |
| Modify | `routers/monitoring_topics.py:694` — `add_competitor` delegates to the graph create path instead of appending; mark route deprecated |
| Create | migration script — backfill `node_id` on legacy `competitor_entries` by `name → :Competitor.display_name`; idempotent; orphan handling per §9 |
| Modify | `frontend/src/services/monitoringTopicsService.ts` / `competitorService.ts` / `queries/competitors.ts` — monitoring add-flow uses the graph create path; surface duplicate/exists cleanly; remove any silent first-match `find()` |
| Modify | `api/tests/test_monitoring_topics_endpoints.py:364` — replace the documenting test with one asserting the unified behavior |
| Create | unit + integration tests for sync node_id-keying and the migration |

## 6. API contract

- `POST /api/v1/monitoring-topics/{account_id}/competitors` (endpoint B) — **deprecated.** During transition, internally creates the `:Competitor` graph node and returns the synced result (no longer a raw append); removed in a later release. (Hard-remove alternative in §9.)
- Graph competitor CRUD (`competitive.py`) — externally unchanged; internally now threads `node_id` into the monitoring sync.
- No new endpoints.

## 7. Acceptance criteria

1. **Verification gate resolved + recorded** — confirmed that the monitoring UI's add-competitor flow does not require monitoring-only competitors that never enter the graph. (If it does, scope falls back to Option 1 — see §9.)
2. Competitor identity is graph-canonical: no code path creates a monitoring entry without a corresponding `:Competitor.node_id`. No orphan entries possible.
3. `MonitoringSyncService` keys add/remove/dedup on `node_id`, not `name`; re-syncing the same competitor is a no-op and produces no duplicates and no name-only entries.
4. All pre-existing legacy name-only `competitor_entries` carry a `node_id` after migration; the migration is idempotent and Shape-B compliant.
5. The direct-append create path is deprecated/redirected; the frontend monitoring add-flow and any automation caller go through the graph create path.
6. Frontend no longer relies on silent first-match `find()`; an attempt to add an existing competitor surfaces a clear, deterministic result.
7. `test_add_competitor_appends_when_name_exists` is replaced with a test asserting the unified behavior; the `api-unit-tests` CI gate stays green.

## 8. Test plan

- **Unit** — `MonitoringSyncService` add/remove/dedup on `node_id` (incl. the "same node_id, different name" and "same name, different node_id" cases that the old name-keying got wrong); `CompetitorEntry` post-migration shape.
- **Integration** — create a competitor via the graph endpoint → it appears exactly once in `competitor_entries` **with** a `node_id`; re-create / re-sync is a no-op; delete removes it; the deprecated direct route routes through the graph and does not double-write.
- **Migration** — seed an account with legacy name-only entries (and a deliberate orphan) → run the migration → all matchable entries carry `node_id`, orphans handled per the §9 decision, second run is a no-op.
- **Frontend** — add-competitor happy path via the graph service; duplicate-add surfaces the expected state; no reliance on first-match `find()`.

## 9. Risks & open questions

- **[Gate] Graph-less competitors.** Does any product flow legitimately need a monitoring competitor that is *not* a strategic graph node? If yes, the hybrid boundary must absorb it (e.g. allow a lightweight graph node to be auto-created) or we fall back to Option 1. **Resolve before building** (AC #1).
- **Deprecation path for endpoint B.** Transition (delegate to graph create, remove later) vs. hard-remove now. Transition is lower-risk for any caller we miss; recommend transition + a follow-up removal issue.
- **Migration orphans.** Legacy entries whose `name` matches no graph `:Competitor` — auto-create the graph node from the entry, drop the entry, or flag for manual review? Recommend: attempt match by normalized name; on miss, create the graph node from the entry's data (preserving watch-config) so nothing is silently lost.
- **Index-addressed update/delete.** `update_competitor` / `delete_competitor` address entries by **array index** (`monitoring_topics.py:818,887`), which is fragile once ordering can change. Migrating these to `node_id` addressing is adjacent and worth folding in or filing as a fast-follow.
- **Coordination with KG-PRD-05.** Both edit near `GraphSyncService`; sequence to avoid conflicting merges.

## 10. Reference

- Sibling PRDs: [KG-PRD-01](./KG-PRD-01-migrations-constraints-indexes.md), [KG-PRD-02](./KG-PRD-02-provenance-spine.md), [KG-PRD-05](./KG-PRD-05-research-on-creation-refactor.md); component [README](../README.md).
- Data Management: [DM-PRD-00](../../data-management/projects/DM-PRD-00-migration-foundation.md), [DM-PRD-05](../../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md).
- Code: `monitoring_sync_service.py:71,73-84` · `competitive.py:52-86` · `monitoring_topics.py:694-905` · `monitoring_models.py:77-110` · `test_monitoring_topics_endpoints.py:364`.
- Origin: DM-91 wave-7 / PR #807 (DM-91 is Done — do not reopen); tracking issue KG-1.

<!-- Proposed Linear issue breakdown (for the project; not part of the PRD spec):
  1. Verification gate + deprecation-approach spike — resolve AC#1 + §9 endpoint-B decision; record both.
  2. Sync node_id-keying — MonitoringSyncService carries/persists/dedupes on node_id; wire competitive.py:77,265; unit tests.
  3. Legacy-entry migration — backfill node_id by name→display_name; orphan handling; idempotent; tests.
  4. Deprecate/redirect direct create path — add_competitor delegates to graph create; replace documenting test.
  5. Frontend rewire — monitoring add-flow → competitorService.create; duplicate handling; remove silent find().
  6. Integration tests + cleanup — E2E no-orphan/no-duplicate proof; optional index→node_id addressing fast-follow.
  ~6 issues — at the small end of the 8-12 guideline (validate-project-completeness will warn); deliberately scoped tight.
-->
