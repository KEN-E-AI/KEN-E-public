# KG-PRD-05 — Research-on-Creation Refactor (Strategy Agents → GraphSyncService + `ResearchRun`)

**Status:** Ready for development (after KG-PRDs 1 + 2 merge)
**Owner team:** Agent / ML
**Blocked by:** KG-PRD-01, KG-PRD-02
**Parallel with:** KG-PRD-03, KG-PRD-04
**Estimated effort:** 3–4 days

> **ADK 2.0 note (Review 45).** This PRD modifies the `strategy_agent` subsystem, which **stays pinned to ADK 1.34.x** and is **not** migrated to ADK 2.0 (the chat tree migrates; the strategy tree does not — see [AH-PRD-13](../../agentic-harness/projects/AH-PRD-13-adk2-foundation.md) §5.2). Keep the in-process `GraphSyncService` import ADK-major-agnostic. This refactor changes the strategy agents' graph-write path; it does **not** remove the agents (full removal is a later release).

---

## 1. Context

When a new account is created, the strategy agent orchestrator at `app/adk/agents/strategy_agent/orchestrator.py:780` runs four builders (business / competitive / marketing / brand) that together produce ~100 nodes across the 28 strategy node types. Two problems with the current wiring:

1. **Bypasses `GraphSyncService`.** Each builder writes directly via `neo4j_tools.Neo4jOperations` — raw Cypher, no Firestore dual-write, no validation, no audit stamping. The API's CRUD endpoints (which *do* use `GraphSyncService`) have diverged from the research path, which will get worse as KG-PRD-02 adds provenance stamping.
2. **Reruns produce duplicates.** `MERGE` is keyed on freshly generated `node_id`s (UUID-based), so a retry always creates duplicates. There is no way to re-run research on an existing account without manual cleanup.

This PRD unifies the write path: every builder calls `GraphSyncService.create_node` (in-process import, per the parent plan's user decision). Each research pass creates a `ResearchRun` node (KG-PRD-02) and threads its `run_id` through the builders so every produced node carries `source_research_run_id` and a `:ESTABLISHED_BY` edge. Idempotency switches to `MERGE` keyed on `(account_id, run_id, natural_key)`, letting reruns no-op instead of duplicating.

## 2. Scope

### In scope
- Create a `ResearchRun` at the start of `execute_strategy_generation_direct()`; close it at the end with `status="complete"` or `"failed"`.
- Refactor each of the four builders to call `GraphSyncService.create_node` (via in-process import) instead of raw Cypher.
- Thread `research_run_id` from the orchestrator into each builder so every created node is stamped + edged.
- `MERGE` idempotency key change: `(account_id, run_id, natural_key)` where natural_key is derived per node type (e.g. Competitor → normalized competitor_name; Product → normalized product_name within a ProductCategory). Same-run re-dispatch = no-op.
- Handle embedding generation: keep batched post-write, do not block the API response.
- Update existing unit / integration tests to cover the new write path.
- Do NOT touch the Researcher / Formatter split or the google_search tool — those are the agent-side logic, unaffected by the storage refactor.

### Out of scope
- Changing which node types the research produces.
- Adding new node types.
- Re-running research automatically on existing accounts (reruns require an explicit trigger; out of scope for v1).
- Changing the MARK_AS_PLANNED semantics around selective strategies or product category overrides — keep behavior identical.
- Firestore collection schema changes beyond what `GraphSyncService` already produces.

## 3. Dependencies

- **KG-PRD-01:** `:KGNode` label and `kg_node_id_unique` constraint. Without these, the per-node uniqueness check on create has to rely on per-label constraints (which don't exist).
- **KG-PRD-02:** `ResearchRun` node type, `create_research_run` / `close_research_run`, `:ESTABLISHED_BY` edge handling in `create_node`, `source_research_run_id` property.
- **External:** none new.
- **Existing files to study and refactor:**
  - `app/adk/agents/strategy_agent/orchestrator.py:780+` — main entry `execute_strategy_generation_direct`
  - `app/adk/agents/strategy_agent/business_graph_builder.py`
  - `app/adk/agents/strategy_agent/competitive_graph_builder.py`
  - `app/adk/agents/strategy_agent/marketing_graph_builder.py`
  - `app/adk/agents/strategy_agent/brand_graph_builder.py`
  - `app/adk/agents/strategy_agent/neo4j_tools.py` — `Neo4jOperations.execute_write_transaction` is what the builders currently call; target for deprecation
  - `api/src/kene_api/services/graph_sync_service.py` — the target service; primarily `create_node`
  - `api/src/kene_api/tasks/strategy_tasks.py` — the background task that invokes the orchestrator
- **Coordination:**
  - `GraphSyncService` lives in `api/`; strategy agents live in `app/`. In-process import crosses the module boundary. Per the parent plan's user decision, accept the coupling (monorepo, both deploy together). Update `app/__init__.py` / `api/__init__.py` Python path configuration if needed.

## 4. Data contract

No new data types. Confirms the following fields on every node produced by research:

- `source_research_run_id` (property): the run_id of the `ResearchRun` that produced it
- `:ESTABLISHED_BY` edge: `(n:KGNode)-[:ESTABLISHED_BY]->(r:ResearchRun)`
- `last_updated_by_agent`: `"researcher"`
- `valid_from`: set to the research run's `started_at`

The `ResearchRun` node itself (from KG-PRD-02):

```python
ResearchRun(
    run_id="<uuid>",
    account_id="acc_abc",
    started_at=datetime(...),
    ended_at=datetime(...),
    status="complete",
    agents=["business", "competitive", "marketing", "brand"],
)
```

### Idempotency key

`MERGE` on each created node uses a composite key: `(account_id, source_research_run_id, natural_key)` where `natural_key` is a deterministic, type-specific string:

| Node type | `natural_key` |
|---|---|
| ProductCategory | normalize(product_name) |
| Product | normalize(product_name) + "@" + parent ProductCategory's natural_key |
| ValueProposition | normalize(display_name) + "@" + parent node's natural_key |
| Competitor | normalize(competitor_name) |
| CompetitorTactic | normalize(tactic_name) + "@" + parent Competitor's natural_key |
| SubstituteProduct | normalize(product_name) + "@" + parent Competitor's natural_key |
| CustomerProfile | normalize(display_name) |
| {Phase}AwarenessStrategy / ConsiderationStrategy / etc. | parent ProductCategory's natural_key |
| BrandIdentity | (singleton per account — natural_key = "BrandIdentity") |
| BrandPersonality / VoiceAndTone / ColorPalette / Typography / ImageStyle / MissionAndValues | normalize(display_name) |
| SWOTAnalysis / CompetitiveEnvironment | (singleton — natural_key = label) |
| Strength / Weakness / Opportunity / Risk / Goal | normalize(display_name) |

`normalize(s)` = lowercase, trim, collapse whitespace, strip punctuation. Same-run re-dispatch of the same research content lands on the same `natural_key` and MERGE becomes a no-op.

Implementation: `GraphSyncService.create_node` gains an optional `idempotency_key: tuple[str, str, str] | None` parameter; when provided, it MERGEs on that tuple rather than generating a fresh `node_id`.

## 5. Implementation outline

| Action | File |
|---|---|
| Modify | `app/adk/agents/strategy_agent/orchestrator.py` — create / close `ResearchRun`, thread `run_id` through builders |
| Modify | `app/adk/agents/strategy_agent/business_graph_builder.py` — replace `neo4j_tools` calls with `GraphSyncService.create_node` |
| Modify | `app/adk/agents/strategy_agent/competitive_graph_builder.py` — same |
| Modify | `app/adk/agents/strategy_agent/marketing_graph_builder.py` — same |
| Modify | `app/adk/agents/strategy_agent/brand_graph_builder.py` — same |
| Modify | `api/src/kene_api/services/graph_sync_service.py` — `create_node(..., idempotency_key=None, research_run_id=None)` |
| Modify | `app/adk/agents/strategy_agent/neo4j_tools.py` — keep `Neo4jOperations` but mark deprecated in favor of `GraphSyncService`; continue to host embedding helpers |
| Modify | existing strategy-agent tests to match the new write path (mock `GraphSyncService`, not Neo4j directly) |
| Create | `app/adk/agents/strategy_agent/tests/test_research_run_lifecycle.py` |
| Create | `app/adk/agents/strategy_agent/tests/test_idempotency_keys.py` |
| Create | `tests/integration/test_research_to_neo4j_sync.py` — account creation → Neo4j + Firestore + ResearchRun all aligned |

### Orchestrator changes

```python
# app/adk/agents/strategy_agent/orchestrator.py

async def execute_strategy_generation_direct(..., account_id: str, user_id: str, ...) -> dict:
    # NEW: create the run up front
    run = await graph_sync_service.create_research_run(
        account_id=account_id,
        agents=["business", "competitive", "marketing", "brand"],
    )
    run_id = run.run_id

    try:
        # Phase 1: business (extracts product categories first)
        business_result = await business_builder.build(..., research_run_id=run_id)

        # Phase 2: the other three in parallel
        results = await asyncio.gather(
            competitive_builder.build(..., research_run_id=run_id),
            marketing_builder.build(..., research_run_id=run_id),
            brand_builder.build(..., research_run_id=run_id),
        )

        await graph_sync_service.close_research_run(run_id=run_id, status="complete")
        return {...}

    except Exception:
        await graph_sync_service.close_research_run(run_id=run_id, status="failed")
        raise
```

### Builder change (pattern — same for all four)

Before:
```python
# business_graph_builder.py (current)
await neo4j_ops.execute_write_transaction([
    Query(
        cypher="""
            MERGE (cat:ProductCategory:Strategy {node_id: $node_id})
            SET cat.product_name = $name, ...
            MERGE (cat)-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
        """,
        params={"node_id": f"productcat_{account_id}_{uuid.uuid4().hex[:8]}",
                "name": category["name"], ...},
    ),
    ...
])
```

After:
```python
# business_graph_builder.py (new)
await graph_sync_service.create_node(
    account_id=account_id,
    node_type="ProductCategory",
    fields={
        "product_name": category["name"],
        "description": category["description"],
        ...
    },
    idempotency_key=(account_id, research_run_id, normalize(category["name"])),
    research_run_id=research_run_id,
    last_updated_by_agent="researcher",
    created_by=f"agent:researcher:{research_run_id}",
)
```

`create_node` handles: node_id generation (if not idempotency-matched), label application (`:ProductCategory:KGNode`), audit stamping, provenance stamping, `:ESTABLISHED_BY` edge to the ResearchRun, Firestore sync, rollback on failure. Builders become simple data-to-field translators.

### `create_node` extension

```python
# api/src/kene_api/services/graph_sync_service.py

async def create_node(
    self,
    account_id: str,
    node_type: str,
    fields: dict,
    idempotency_key: tuple[str, str, str] | None = None,
    session_id: str | None = None,
    research_run_id: str | None = None,
    last_updated_by_agent: Literal["researcher", "session_end_agent", "user"] = "user",
    created_by: str = "system",
) -> KGNodeBase:
    # 1. Validate node_type is registered.
    # 2. If idempotency_key is present, MERGE by that key; node_id comes from the existing node if matched,
    #    or is freshly generated if creating.
    # 3. Run the existing create_node path: Cypher, Firestore sync with rollback, embedding queue.
    # 4. Add `source_research_run_id` / `source_session_id` / `last_updated_by_agent` / `valid_from` properties.
    # 5. If research_run_id: MERGE (:KGNode {node_id})-[:ESTABLISHED_BY]->(:ResearchRun {run_id}).
    # 6. If session_id: MERGE (:KGNode {node_id})-[:OBSERVED_IN]->(:Session {session_id}).
```

The idempotency MERGE takes the form:
```cypher
MERGE (n:ProductCategory:KGNode {
  account_id: $account_id,
  source_research_run_id: $run_id,
  _natural_key: $natural_key          // underscore-prefixed to indicate derived
})
ON CREATE SET
  n.node_id = $new_node_id,
  n.product_name = $product_name,
  ...,
  n.valid_from = datetime(),
  n.created_time = datetime(),
  n.last_updated_by_agent = 'researcher'
ON MATCH SET
  n.last_modified = datetime()
RETURN n
```

A re-dispatched builder with the same `research_run_id` + `natural_key` lands on `ON MATCH` and does no harm.

### `neo4j_tools.py` disposition

Keep the file — it hosts embedding helpers (`EmbeddingGenerator` configuration, vector index checks) that remain useful. Remove or mark `@deprecated` the write functions (`execute_write_transaction`, `merge_account`, `create_strategy_node`, `update_strategy_node`). Builders stop importing them. The read helpers (if any) can stay until a future cleanup.

### Embedding generation

Stays async / batched post-write. The existing pattern in `app/adk/agents/strategy_agent/embeddings.py` — `get_nodes_needing_embeddings()` + batch generation — is invoked by `strategy_tasks.py` after the orchestrator returns. The refactor does not touch this step.

## 6. API contract

No new endpoints. The existing account-creation endpoint at `api/src/kene_api/routers/accounts.py:542-749` continues to trigger strategy generation in the background, unchanged externally.

## 7. Acceptance criteria

1. Creating a new account via the existing POST endpoint triggers `execute_strategy_generation_direct`, which first creates a `ResearchRun` and then runs the four builders. After completion, the `ResearchRun.status="complete"` and the `ended_at` is populated.
2. Every node produced by the research run has: `source_research_run_id == run.run_id`, `last_updated_by_agent == "researcher"`, `valid_from` set, and one `:ESTABLISHED_BY` edge to the ResearchRun.
3. `GraphSyncService.create_node` is the only write path used by the four builders — grep for `execute_write_transaction` or raw `MERGE` Cypher in `app/adk/agents/strategy_agent/*graph_builder.py` returns zero hits.
4. Firestore is kept in sync: every node that appears in Neo4j also appears in its corresponding `accounts/{account_id}/strategy_docs` subcollection (Shape B layout per the [Review 15 in DESIGN-REVIEW-LOG](../../../DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1)). Count match within ±0 after a full research run.
5. Re-running research for the same account with the same `research_run_id` (simulate via direct call, bypassing the account endpoint) is a no-op — no duplicate nodes created. Verified by snapshot + second call + count check.
6. Re-running research for the same account with a *different* `research_run_id` creates a new ResearchRun and a second set of nodes (distinct `source_research_run_id`). The old nodes remain untouched. This behavior is expected for v1 — deduplication across runs is a future concern.
7. If any builder raises mid-run, `close_research_run` sets `status="failed"` and the partial nodes that were created remain in the graph (they carry the failed run's id for later cleanup). The existing account-creation error path runs unchanged.
8. All existing strategy-agent tests pass or are updated to the new write path. No regression in node counts or Firestore doc counts.
9. Embedding generation still runs post-write in the background and produces 768-dim vectors for the new nodes within the usual window (< 5 minutes for a typical account).
10. `make lint` clean; `make test` passes.

## 8. Test plan

**Unit tests:**

- `test_research_run_lifecycle.py`:
  - Orchestrator creates a ResearchRun → four builders run (mocked) → closes with `status="complete"`.
  - Builder raises → orchestrator closes with `status="failed"`.
- `test_idempotency_keys.py`:
  - `normalize()` is deterministic: same input → same output; whitespace / casing / punctuation normalized.
  - Each node type's natural_key builder produces the expected key for fixture data.
  - `create_node` with `idempotency_key=(A, R, K)` twice in a row → one Cypher MERGE with two executions; the second is a no-op (ON MATCH).
- `test_builder_create_node_calls.py` (per builder):
  - Given a fixture research output, assert `create_node` is called with the expected `node_type`, `fields`, `idempotency_key`, `research_run_id`.
  - Relationships between produced nodes (e.g. Product → ProductCategory) are created via the existing relationship-creation path (either via `create_node`'s relationship-stamping or a follow-up `add_relationship` call — whichever the current pattern is).

**Integration tests:**

- `test_research_to_neo4j_sync.py`:
  - Create an account → wait for strategy generation to complete.
  - Assert: ResearchRun node exists with `status="complete"`, ~expected count of nodes per type, every node has `:ESTABLISHED_BY` → ResearchRun, Firestore counts match Neo4j counts.
- `test_research_rerun_idempotency.py`:
  - Trigger the orchestrator directly (bypass account endpoint) with the same `research_run_id` twice. Assert the second run produces zero new nodes.
- `test_research_failure_path.py`:
  - Inject a failure mid-run (e.g. patch one builder to raise). Assert `ResearchRun.status="failed"`, partial nodes remain (with the failed run's id), and no orphan Firestore docs.

**Regression:**

- Existing `app/adk/agents/strategy_agent/tests/neo4j/` suite passes without substantive logic changes.
- `test_knowledge_graph_endpoints.py` (API CRUD) passes without changes — CRUD and research now share the same write path.

## 9. Risks & open questions

| Risk / question | Mitigation |
|---|---|
| In-process import of `GraphSyncService` from `app/` to `api/` | Per parent plan decision — accept. Monorepo, both deploy together. If Python path / packaging surprises, fix by installing `api` as an editable dependency of `app` in `pyproject.toml`. |
| `create_node` latency with idempotency MERGE higher than raw bulk writes | Measure. If regression > 2x, batch the writes per builder (e.g. `create_nodes_bulk(account_id, node_type, fields_list, idempotency_keys)`) with a single Cypher UNWIND. Added complexity — only do if needed. |
| Firestore sync adds meaningful latency to research completion | It already is part of the CRUD write path — accepted cost. If needed, the background-task nature of strategy generation means end-user doesn't see the added time. |
| Partial failures leave orphan nodes with a failed ResearchRun id | Acceptable for v1 — cleanup is trivial (`MATCH (n:KGNode)-[:ESTABLISHED_BY]->(r:ResearchRun {status: 'failed'}) DETACH DELETE n, r`) and can be wrapped in a later cleanup script. Do not try to transactionally roll back research across agents — too many moving parts. |
| `natural_key` normalization differs subtly from a future session-end agent's normalization | Centralize `normalize()` in a shared utility (`app/adk/agents/utils/text_normalization.py`) used by both research and session-end. |
| Existing embedding pipeline references node properties in ways that change | Embeddings read `description` + `display_name` (or equivalents) for each node. The refactor preserves these properties. Verify on a dry run. |
| A builder currently creates a relationship across nodes via a single transaction | `create_node` creates nodes individually; relationships between research-produced nodes become separate calls (either via a new `add_relationship` method or via `create_node`'s existing relationship-stamping parameter — check the current `graph_sync_service` API). Audit each builder for relationship-creation patterns and migrate. |
| Changing `MERGE` keys from UUID to natural_key breaks existing accounts | Old research runs used UUID-based node_ids; new research runs use `(account_id, run_id, natural_key)` as the idempotency key. These are different uniqueness scopes — old nodes are never touched by new research. No data migration needed. |

## 10. Reference

- KG-PRD-01 (shared label, constraints); KG-PRD-02 (ResearchRun + provenance methods).
- Existing files being refactored: `app/adk/agents/strategy_agent/orchestrator.py`, `*_graph_builder.py` × 4, `neo4j_tools.py`.
- Existing service being extended: `api/src/kene_api/services/graph_sync_service.py`.
- CLAUDE.md rules in scope: C-2, C-4, C-9; PY-1, PY-2, PY-3, PY-7; T-1, T-3, T-5, T-8.
