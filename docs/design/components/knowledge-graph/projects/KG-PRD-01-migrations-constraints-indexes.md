# KG-PRD-01 — Neo4j Migrations, Constraints, Indexes, `:KGNode` Backfill

**Status:** Ready for development
**Owner team:** Backend / Infra
**Blocks:** KG-PRDs 2, 3, 4, 5
**Estimated effort:** 2 days

---

## 1. Context

Neo4j today has **no declared constraints, no custom indexes, and no vector index** despite the `embedding` property already being written on strategy nodes. Uniqueness is enforced only by Pydantic validation and a one-off cleanup script (`api/scripts/cleanup_neo4j_data.py`). The 28 existing node types each carry their own labels — there is no shared label that would let us create a single cross-type constraint, index, or vector index.

This PRD lays the foundations that every downstream KG PRD depends on:

1. A **lightweight migration runner** so Neo4j schema changes ship like code (numbered Cypher files, idempotent, applied on API startup, tracked via a `:Migration` ledger node).
2. An **initial migration** that creates uniqueness constraints, lookup indexes, and a 768-dimension cosine vector index.
3. A **backfill migration** that adds the shared `:KGNode` label to every existing strategy node and backfills `valid_from := created_time`.

Zero behavior change is expected at the read / write path; this is pure schema hardening.

## 2. Scope

### In scope
- `api/src/kene_api/db_migrations/` directory containing numbered `.cypher` migration files
- `api/scripts/apply_neo4j_migrations.py` — idempotent runner invoked from the FastAPI lifespan
- Migration 001: constraints + lookup indexes + vector index (all `IF NOT EXISTS`)
- Migration 002: backfill `:KGNode` label + `valid_from` onto every existing strategy node
- Ledger node (`:Migration {name, applied_at, hash}`) to skip already-applied migrations
- Startup hook in `api/src/kene_api/main.py` that runs the runner inside the lifespan, after `neo4j_service.connect()`
- Unit tests for the runner's file discovery, hash comparison, and skip logic
- Integration tests for each migration (apply to a fresh DB, assert constraints/indexes/labels present)

### Out of scope
- New node types (`Session`, `Observation`, `ResearchRun`) — KG-PRD-02 owns those
- Any changes to `GraphSyncService` methods — KG-PRD-02
- Tools that query the vector index — KG-PRD-03
- Changing how strategy agents write — KG-PRD-05

## 3. Dependencies

- **External:** Neo4j 5.13+ (vector index support), `neo4j` async driver (already installed)
- **Existing files to study:**
  - `api/src/kene_api/database.py` — `Neo4jService` (session management, retry logic)
  - `api/src/kene_api/main.py:73` — FastAPI lifespan where startup hooks live
  - `api/scripts/cleanup_neo4j_data.py` — existing ad-hoc data fix script; same style but we're going stricter
- **Verify ahead of kickoff:**
  - Neo4j server version running in all three environments (dev / staging / prod) supports vector indexes. If any env is < 5.13, upgrade ticket first.
  - `Account` and `Organization` node ID properties as they appear in the current DB (spot-check a handful). The exploration found `account_id` / `organization_id`; constraint names assume this.

## 4. Data contract

### Migration file format

Files live under `api/src/kene_api/db_migrations/` and follow `NNN_short_snake_case_name.cypher`. Each file is a sequence of Cypher statements separated by `;\n` (the runner splits on `;` at statement boundaries).

All statements MUST be idempotent — either `IF NOT EXISTS` on DDL or `MERGE` on DML. The runner has no transaction boundary; an interrupted migration leaves the DB in a partial state, and re-running must be safe.

### Ledger node

```cypher
(:Migration {name: "001_base_constraints", applied_at: datetime(), hash: "<sha256-of-file>"})
```

- `name` — the filename without extension
- `applied_at` — when the runner finished applying it
- `hash` — SHA-256 of the file contents at apply time, used to detect post-apply edits (which should never happen — migration files are immutable once merged)

The runner applies files in sorted filename order, skipping any whose `name` already exists in the ledger. A hash mismatch (file edited after apply) emits a hard error at startup — the fix is a new migration that undoes and redoes, not editing the old file.

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `api/src/kene_api/db_migrations/__init__.py` |
| Create | `api/src/kene_api/db_migrations/001_base_constraints.cypher` |
| Create | `api/src/kene_api/db_migrations/002_kgnode_backfill.cypher` |
| Create | `api/scripts/apply_neo4j_migrations.py` |
| Modify | `api/src/kene_api/main.py` — call runner in lifespan after `neo4j_service.connect()` |
| Create | `api/tests/unit/test_migration_runner.py` |
| Create | `api/tests/integration/test_migrations_applied.py` |

### Migration 001 — base constraints and indexes

```cypher
// Uniqueness
CREATE CONSTRAINT account_id_unique IF NOT EXISTS
  FOR (a:Account) REQUIRE a.account_id IS UNIQUE;

CREATE CONSTRAINT organization_id_unique IF NOT EXISTS
  FOR (o:Organization) REQUIRE o.organization_id IS UNIQUE;

CREATE CONSTRAINT kg_node_id_unique IF NOT EXISTS
  FOR (n:KGNode) REQUIRE n.node_id IS UNIQUE;

// Lookup indexes
CREATE INDEX kg_node_account_id IF NOT EXISTS
  FOR (n:KGNode) ON (n.account_id);

// Vector index (768-dim, cosine — matches text-embedding-004)
CREATE VECTOR INDEX kb_vector_index IF NOT EXISTS
  FOR (n:KGNode) ON (n.embedding)
  OPTIONS {indexConfig: {
    `vector.dimensions`: 768,
    `vector.similarity_function`: 'cosine'
  }};
```

Note: `kg_node_id_unique` only fires for nodes that actually carry the `:KGNode` label. Migration 002 adds the label to existing nodes; migration 001 creates the constraint before the label exists, which is valid — the constraint is a schema rule, not a retroactive check.

### Migration 002 — backfill `:KGNode` label and `valid_from`

28 strategy labels to reach. For each label, add `:KGNode` and stamp `valid_from := created_time` where null:

```cypher
// Business strategy
MATCH (n:ProductCategory) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);
MATCH (n:Product) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);
MATCH (n:ValueProposition) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);
MATCH (n:Strength) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);
MATCH (n:Weakness) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);
MATCH (n:Opportunity) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);
MATCH (n:Risk) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);
MATCH (n:Goal) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);
MATCH (n:SWOTAnalysis) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);

// Competitive strategy
MATCH (n:Competitor) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);
MATCH (n:CompetitorTactic) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);
MATCH (n:CompetitorStrength) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);
MATCH (n:CompetitorWeakness) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);
MATCH (n:SubstituteProduct) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);
MATCH (n:CompetitiveEnvironment) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);

// Marketing strategy
MATCH (n:CustomerProfile) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);
MATCH (n:ProblemAwarenessStrategy) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);
MATCH (n:BrandAwarenessStrategy) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);
MATCH (n:ConsiderationStrategy) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);
MATCH (n:ConversionStrategy) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);
MATCH (n:LoyaltyStrategy) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);

// Brand strategy
MATCH (n:BrandIdentity) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);
MATCH (n:BrandPersonality) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);
MATCH (n:VoiceAndTone) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);
MATCH (n:ColorPalette) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);
MATCH (n:Typography) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);
MATCH (n:ImageStyle) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);
MATCH (n:MissionAndValues) SET n:KGNode, n.valid_from = coalesce(n.valid_from, n.created_time);
```

Re-running this migration is a no-op: `SET n:KGNode` on an already-labeled node is idempotent; `coalesce` preserves any `valid_from` set by a later write.

### Runner — core shape

```python
# api/scripts/apply_neo4j_migrations.py
from pathlib import Path
import hashlib, logging
from api.src.kene_api.database import neo4j_service

MIGRATIONS_DIR = Path(__file__).parent.parent / "src" / "kene_api" / "db_migrations"

def _read_migration_files() -> list[tuple[str, str, str]]:
    """Return (name, content, hash) sorted by filename."""
    files = sorted(MIGRATIONS_DIR.glob("*.cypher"))
    return [
        (f.stem, f.read_text(), hashlib.sha256(f.read_bytes()).hexdigest())
        for f in files
    ]

async def _get_applied() -> dict[str, str]:
    """Return {name: hash} for already-applied migrations."""
    rows = await neo4j_service.execute_query(
        "MATCH (m:Migration) RETURN m.name AS name, m.hash AS hash",
        {},
    )
    return {r["name"]: r["hash"] for r in rows}

async def _apply(name: str, content: str, hash_: str) -> None:
    # Split on ";" at end of line (simple heuristic; migrations avoid ";" inside strings)
    statements = [s.strip() for s in content.split(";") if s.strip()]
    for stmt in statements:
        await neo4j_service.execute_write_operation(stmt, {})
    await neo4j_service.execute_write_operation(
        "MERGE (m:Migration {name: $name}) "
        "SET m.applied_at = datetime(), m.hash = $hash",
        {"name": name, "hash": hash_},
    )

async def apply_all_migrations() -> dict:
    applied = await _get_applied()
    summary = {"applied": [], "skipped": [], "hash_mismatches": []}
    for name, content, hash_ in _read_migration_files():
        if name in applied:
            if applied[name] != hash_:
                summary["hash_mismatches"].append(name)
                raise RuntimeError(
                    f"Migration {name} has been modified after apply. "
                    f"Create a new migration to correct; never edit applied ones."
                )
            summary["skipped"].append(name)
            continue
        logging.info(f"Applying Neo4j migration: {name}")
        await _apply(name, content, hash_)
        summary["applied"].append(name)
    return summary
```

### Lifespan hook

```python
# api/src/kene_api/main.py — inside lifespan, after neo4j_service.connect()
from api.scripts.apply_neo4j_migrations import apply_all_migrations

try:
    summary = await apply_all_migrations()
    logging.info(f"Neo4j migrations: {summary}")
except RuntimeError as e:
    logging.error(f"Neo4j migration failure: {e}")
    raise  # fail fast on startup — do not serve requests against an unknown schema
```

## 6. API contract

No new endpoints. This PRD is pure infrastructure.

## 7. Acceptance criteria

1. On a fresh Neo4j database, starting the API applies migrations 001 and 002 exactly once and records two `:Migration` nodes.
2. On a second startup, the runner reports both migrations as skipped and applies nothing.
3. `SHOW CONSTRAINTS` on the live DB returns at least: `account_id_unique`, `organization_id_unique`, `kg_node_id_unique`.
4. `SHOW INDEXES` returns at least: `kg_node_account_id`, `kb_vector_index` with `vector.dimensions=768` and `vector.similarity_function='cosine'`.
5. After migration 002, every node that carries any of the 28 strategy labels also carries `:KGNode`, and every such node has a non-null `valid_from`.
6. Attempting to create a second `Account` node with the same `account_id` fails with a constraint violation.
7. Attempting to create a second `KGNode` with an existing `node_id` fails with a constraint violation.
8. If a migration file is edited after it has been applied (hash mismatch), the next startup raises a clear error and refuses to serve requests.
9. `make test` passes without modification to existing tests — no regressions in the CRUD suite or strategy agent suite.
10. The `Neo4jService.execute_query` path still completes in < 100ms for a simple account fetch (no noticeable startup-time regression after migration apply).

## 8. Test plan

**Unit tests** (`test_migration_runner.py`):
- File discovery sorts by filename correctly (`010_foo.cypher` comes after `002_bar.cypher`)
- Hash computation is deterministic across runs
- `_apply` splits multi-statement files into individual statements and calls the driver per statement
- Hash mismatch raises `RuntimeError`
- With a mock ledger containing `001_base_constraints`, only `002_kgnode_backfill` is applied on the second run

**Integration tests** (`test_migrations_applied.py`) — run against the Neo4j test instance:
- Fresh DB → call `apply_all_migrations()` → `SHOW CONSTRAINTS` and `SHOW INDEXES` both include the expected names
- Seed 10 strategy nodes of varied labels without `:KGNode`; apply migration 002; verify all 10 now carry `:KGNode` and have `valid_from` set
- Idempotency: apply all migrations twice in a row; the second run reports skipped-only
- Hash tampering: after apply, modify file on disk, re-run → raises

**Regression:**
- Full existing CRUD suite (`api/tests/integration/test_knowledge_graph_endpoints.py`, etc.) passes without changes

## 9. Risks & open questions

| Risk / question | Mitigation |
|---|---|
| Migration 002 runs against a large DB and blocks startup for minutes | The 28 `MATCH ... SET` statements are fast (indexed label lookup + small per-node update). For pre-production data volumes (<10k nodes/account) this completes in seconds. Measure on staging first. If it ever becomes a concern, split into a background job and gate the label-check CRUD behavior on a feature flag. |
| Neo4j version < 5.13 in some env (no vector index) | Verify versions before kickoff; upgrade ticket first. Vector index is not optional — KG-PRD-03 depends on it. |
| Ledger `:Migration` node accidentally deleted | Next startup re-applies all migrations. Because every statement is idempotent (`IF NOT EXISTS`, `MERGE`), re-apply is safe — just wasteful. Low concern. |
| Runner swallows partial-apply failures | If statement N fails, statements 1..N-1 are committed (no transaction boundary) but the ledger row is not written, so the next run re-attempts. Individual statements are already idempotent, so re-run lands correctly. Document this; do not introduce a transaction unless measurement shows a real failure mode. |
| Strategy node label drift — a 29th label added to the schema before migration 002 merges | Any new label added to `NODE_TYPE_REGISTRY` between plan approval and PRD-1 merging must be added to migration 002. Cross-check the registry just before merging. |
| `coalesce(n.valid_from, n.created_time)` on a node whose `created_time` is also null | `coalesce` returns null, which is fine for v1 — subsequent writes will stamp it. Audit reveals only a handful of such nodes; they predate the audit-field rollout. Acceptable. |

## 10. Reference

- Parent plan: [`the-purpose-of-neo4j-clever-frost.md`](../../../../../Users/kenwilliams/.claude/plans/the-purpose-of-neo4j-clever-frost.md) §Phase 1 (this user's local plan; not committed)
- Existing files: `api/src/kene_api/database.py`, `api/src/kene_api/main.py`, `api/scripts/cleanup_neo4j_data.py`
- Neo4j docs: [Vector indexes](https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/), [Constraints](https://neo4j.com/docs/cypher-manual/current/constraints/)
- CLAUDE.md rules in scope: D-1, D-4, D-5; PY-1, PY-7; T-1, T-3, T-4
