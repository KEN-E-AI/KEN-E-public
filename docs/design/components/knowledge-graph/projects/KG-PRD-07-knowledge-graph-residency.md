# KG-PRD-07 — Knowledge-Graph Residency

**Status:** Ready to start
**Owner team:** [KEN-E] Knowledge Graph
**Initiative:** Data Residency (US + EU)
**Blocked by:** DM-PRD-09 (regional-cell foundation), KG-PRD-01 (Neo4j migration runner)
**Blocks:** —
**Estimated effort:** 2–3 days

> **Program context.** This is the knowledge-graph slice of the data-residency program (logical `DR-PRD-04` in the program breakdown). The program is *not* a new component: each slice is a PRD homed in the component that owns the affected code, bound together by the **Data Residency (US + EU)** Linear Initiative and the cross-component spec [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md). Read that doc's §1–§4 (esp. §2 locked decisions, §3.4 reference pattern, §4 per-store posture — the Neo4j row) and §5 (gap register, R-06) before this PRD. This project closes **R-06** (a launch blocker, §6.1).

---

## 1. Context

KEN-E pins each account to a residency region via `data_region` (UI: "Data Storage Region"; values **US / EU**). The knowledge graph does **not** honor it: a **single global Neo4j Aura instance** backs every account, US and EU alike. The driver is built once from one set of credentials — `settings.neo4j_uri` / `settings.neo4j_username` / `settings.neo4j_password` (`api/src/kene_api/config.py:28-30`) at `api/src/kene_api/database.py:26-28` — and exposed as a single module-global singleton `neo4j_service = Neo4jService()` (`api/src/kene_api/database.py:309`) consumed everywhere via `get_neo4j_service()`. Every account-scoped read goes through that one connection regardless of region; e.g. the chat org-context load resolves the global service and queries it directly (`api/src/kene_api/routers/chat.py:138-141`):

```python
neo4j_service = await get_neo4j_service()
result = await neo4j_service.execute_query(ORG_CONTEXT_QUERY, {"account_id": account_id})
```

So **EU org / brand strategy data physically lives in the US DBMS** — the most concentrated body of regulated EU strategy content in the system after Firestore. This is **R-06**, a launch blocker.

**The fix (design doc §4 Neo4j row + §7 DR-PRD-04 row): a separate EU Neo4j *instance* — one DBMS per region — NOT a second named database inside the US instance.** Multiple named databases in one Aura instance share a single cloud region, so a `data_region`-named database in the US instance would still store EU data in the US — it does not satisfy residency. (Aura multi-DB is also tier-limited.) We therefore keep **exactly one database per regional instance** and resolve which *instance* (i.e. which `NEO4J_URI` + credentials) an account uses by its `data_region`, mirroring the foundation's `get_<resource>(account_id)` pattern.

This slice ships:

1. **A region registry of Neo4j cells** — a `Region → Neo4jCellConfig(uri, username, password, database)` map, built from per-region env, with US as the default cell.
2. **A `get_neo4j_for_account(account_id)` resolver** — reusing DM-PRD-09's `resolve_account_region(account_id)` and `Region` enum — returning the region-appropriate, per-region-cached `Neo4jService`.
3. **The DI / call-site refactor** so account-scoped Neo4j access is region-routed, while the existing global singleton is retained as the **US (default-cell)** service.
4. **The migration runner applied to both regional instances** so the EU DBMS comes up with the identical KG-PRD-01 schema (constraints, indexes, vector index, `:KGNode` backfill) before it ever serves an account.

**No existing data is migrated.** Per the program's open question Q7, the EU cell is **green-field** (new EU sign-ups only); a supervised region-migration tool is DR-PRD-10, out of scope here. The EU instance starts empty and the runner brings it to schema parity.

See [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) §2 (D1, D4 — wait, the relevant decisions are D1 account-as-boundary, D5 immutable region, D6 verify-before-open), §3.2 (cell table — Neo4j row), §3.4 (reference pattern), §4 (Neo4j posture). The keystone is [`../../data-management/projects/DM-PRD-09-regional-cell-foundation.md`](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md); the schema this slice must replicate to both instances is [`./KG-PRD-01-migrations-constraints-indexes.md`](./KG-PRD-01-migrations-constraints-indexes.md).

## 2. Scope

### In scope

- **Neo4j cell registry** — a `Region → Neo4jCellConfig` map (`uri`, `username`, `password`, `database`), built from per-region env vars (`NEO4J_URI_US` / `NEO4J_URI_EU`, etc.), with `DEFAULT_REGION` (US) as the fallback cell. One source of truth, imported wherever a Neo4j connection is acquired. Mirrors `storage_service.py:_get_bucket_config` (`api/src/kene_api/services/storage_service.py:31-72`).
- **`get_neo4j_for_account(account_id) -> Neo4jService` resolver** — reuses DM-PRD-09's `resolve_account_region(account_id)` (directory fast-path) and `Region` enum; returns the region's `Neo4jService`, **per-region cached** (one connected driver per `Region`, not per account). This is the KG instantiation of the **`get_<resource>(account_id)` pattern**. It does **not** redefine the region registry or the routing directory — those are owned by DM-PRD-09.
- **`Neo4jService` made cell-aware** — accept a resolved `Neo4jCellConfig` (or build the driver from it) instead of reading `settings.neo4j_uri` directly at `database.py:26-28`; preserve lazy connect, retry, session-management, and health-check behavior unchanged. Each regional service keeps **one** `database=` (its cell's single DB).
- **Call-site refactor** — replace region-blind `get_neo4j_service()` acquisitions on account-scoped paths (e.g. chat org-context `chat.py:138`) with `get_neo4j_for_account(account_id)`. The global singleton is retained as the **US / default-cell service** for genuinely region-agnostic paths (startup, migrations, control-plane).
- **Migration runner applied to both regional instances** — extend KG-PRD-01's `apply_all_migrations()` so the FastAPI lifespan applies the migration set to **every** configured regional `Neo4jService` (US and EU), each tracking its own `:Migration` ledger in its own DBMS. Startup fails fast if any configured instance cannot be brought to schema parity.
- **Terraform / config wiring** — per-region `NEO4J_URI_*` / credential env (and Secret Manager refs) for the EU instance, threaded into the per-env deploy. Provisioning the EU instance itself is an infra task gated on the Q4 decision (Aura-EU vs self-host on EU GKE).
- **Docs** — note the KG instantiation of the Regional Cell routing convention in [`../README.md`](../README.md) (point at DM-PRD-09 §7.8 as the canonical convention; do not re-document it).

### Out of scope

- **The DM-PRD-09 foundation itself** — the `Region` enum, `CELLS` registry, `account_regions/{account_id}` routing directory, `resolve_account_region(account_id)`, and `data_region` immutability/enum validation are owned by DM-PRD-09 and **reused, not redefined** here.
- **The R-10 Neo4j cross-account `account_id` authorization hotfix** — the 7 cascade Cypher queries that match on `node_id` alone (`graph_sync_service.py:791,806,942,968` and the `delete_*` / `update_*` family) are a **live, exploitable-today** authorization leak independent of regions. They ship as a **standalone hotfix PR ahead of the residency program** (design doc §6.4), **not** in this slice. R-10 and R-06 are separate gaps; do not bundle them.
- **Migrating existing data into the EU instance** — green-field per Q7; supervised region migration is DR-PRD-10.
- **Any store other than Neo4j** — Firestore (DM-PRD-09), KMS/tokens (IN-PRD-08), model/Agent Engine (AH-PRD-11), observability (AH-PRD-12), Redis/artifacts (CH-PRD-07), BigQuery (BL-PRD-07 / SE-PRD).
- **Cross-cell admin / global KG analytics fan-out** — DR-PRD-10.
- **Gating EU sign-ups behind a feature flag** — the launch gating rule (design doc §6.1) is a Feature-Flags concern, wired when the EU cell is verified end-to-end.

## 3. Dependencies

- **DM-PRD-09 complete** — provides the `Region` enum, `CELLS` registry, the `account_regions/{account_id}` routing directory, and `resolve_account_region(account_id)`. `get_neo4j_for_account` is a thin consumer of these. **Hard blocker.**
- **KG-PRD-01 complete** — provides the migration runner (`api/scripts/apply_neo4j_migrations.py`, `apply_all_migrations()`), the migration set (001 constraints/indexes/vector index, 002 `:KGNode` backfill), and the `:Migration` ledger. This slice generalizes the runner from one instance to N regional instances. **Hard blocker.**
- Existing reference pattern: `api/src/kene_api/services/storage_service.py:31-72` (GCS `data_region` routing) — the shape this PRD replicates for Neo4j.
- Refactor targets: `api/src/kene_api/database.py:26-28` (driver build), `:76` (`session(database=...)`), `:309` (global singleton); `api/src/kene_api/config.py:28-31` (Neo4j settings); `api/src/kene_api/routers/chat.py:138-141` (representative account-scoped call site).
- **External / open:** the EU Neo4j instance must exist before the EU cell serves traffic — **Q4** (Aura-EU under our plan vs. self-host on EU GKE), to be decided **week 1**. Until then, `get_neo4j_for_account` for an EU account has no target; EU sign-ups stay gated (design doc §6.1).

## 4. Data contract

### 4.1 Neo4j cell registry (single source of truth for KG connections)

```python
# shared/residency/neo4j_cells.py
from dataclasses import dataclass
from shared.residency.regions import Region, DEFAULT_REGION  # owned by DM-PRD-09

@dataclass(frozen=True)
class Neo4jCellConfig:
    region: Region
    uri: str          # NEO4J_URI_US / NEO4J_URI_EU — a distinct DBMS per region
    username: str
    password: str
    database: str     # exactly ONE database per regional instance (default: "neo4j")

# Built from per-region env; US is the default cell.
NEO4J_CELLS: dict[Region, Neo4jCellConfig] = { ... }
```

- **Invariant:** each `Region` maps to a **distinct DBMS** (`uri`), each with **one** `database`. There is never more than one named database per regional instance — multi-DB-in-one-instance does not satisfy residency (§1).
- The map is built from env (`NEO4J_URI_US`, `NEO4J_USERNAME_US`, `NEO4J_PASSWORD_US`, and the `_EU` equivalents, with the bare `NEO4J_URI`/etc. accepted as the US alias for back-compat). Credentials resolve via the existing `sm://` Secret Manager path (`config.py`).
- Authoritative region for an account remains `acc.data_region` on the Neo4j Account node, projected into the DM-PRD-09 routing directory; this slice **reads** the resolved region, it does not own the mapping.

### 4.2 Resolver contract

```python
# shared/residency/routing.py  (extends DM-PRD-09's routing module)
def get_neo4j_for_account(account_id: str) -> Neo4jService:
    """Resolve the account's home region via resolve_account_region(account_id),
    then return the regional Neo4jService for that cell. Per-region cached
    (one connected driver per Region, not per account). Mirrors
    get_firestore_for_account(account_id)."""
```

| Operation | Rule |
|---|---|
| Resolve | `region = resolve_account_region(account_id)` (DM-PRD-09 directory fast-path; Neo4j fallback + backfill on miss). |
| Connect | Return the cached `Neo4jService` for `NEO4J_CELLS[region]`; lazily connect on first use (preserves `database.py` lazy-init). |
| Default | An account whose region is unresolvable resolves to `DEFAULT_REGION` (US) — never silently to "no DB". |

### 4.3 Migration ledger per instance

KG-PRD-01's `:Migration {name, applied_at, hash}` ledger node is **per DBMS**. The EU instance maintains its own ledger; applying the same migration set to both instances records two independent ledgers that must converge to the same set of `name`s. No cross-instance ledger sharing.

## 5. Implementation outline

| Action | File |
|---|---|
| Create | `shared/residency/neo4j_cells.py` — `Neo4jCellConfig`, `NEO4J_CELLS` (built from per-region env), validation that each region maps to a distinct `uri` with one `database` |
| Modify | `shared/residency/routing.py` (DM-PRD-09's module) — add `get_neo4j_for_account(account_id)`; per-region `Neo4jService` cache |
| Modify | `api/src/kene_api/database.py` — `Neo4jService.__init__`/`connect` accept a `Neo4jCellConfig` (driver built from cell config, not `settings.neo4j_uri` at `:26-28`); `get_session` uses the cell's `database` (generalize `:76`); keep the `:309` global singleton as the US/default-cell instance |
| Modify | `api/src/kene_api/config.py` — add per-region `NEO4J_URI_US/EU`, `NEO4J_USERNAME_*`, `NEO4J_PASSWORD_*` (`:28-31`), keeping bare vars as the US alias |
| Modify | `api/src/kene_api/routers/chat.py` (`:138`) and other account-scoped Neo4j call sites — use `get_neo4j_for_account(account_id)` instead of the region-blind `get_neo4j_service()` |
| Modify | `api/scripts/apply_neo4j_migrations.py` + the `main.py` lifespan hook — iterate `apply_all_migrations()` over **every** configured regional `Neo4jService`; fail fast if any cannot reach schema parity |
| Modify | `deployment/terraform/` + env config — per-region `NEO4J_URI_*` / credential wiring (Secret Manager refs) for the EU instance |
| Modify | [`../README.md`](../README.md) — note the KG instantiation of the Regional Cell routing convention, pointing at DM-PRD-09 §7.8 as canonical |
| Create | `api/tests/unit/test_residency_neo4j_cells.py`, `api/tests/unit/test_get_neo4j_for_account.py` |
| Create | `api/tests/integration/test_neo4j_region_routing.py` |

## 6. API contract

This slice publishes no new public HTTP surface; it adds an internal DI contract and constrains how Neo4j connections are acquired.

| Contract | Consumed by | Source of truth |
|---|---|---|
| `get_neo4j_for_account(account_id) -> Neo4jService` (the `get_<resource>(account_id)` pattern for Neo4j) | Every account-scoped Neo4j read/write (chat org-context, KG read tools, graph sync) | `shared/residency/routing.py` |
| `Neo4jCellConfig` + `NEO4J_CELLS` (one distinct DBMS per region, one DB each) | KG connection acquisition; any future regional KG consumer | `shared/residency/neo4j_cells.py` |
| Migration runner applies the KG-PRD-01 set to **all** configured regional instances at startup | FastAPI lifespan | `api/scripts/apply_neo4j_migrations.py` |
| `Region` enum, `resolve_account_region(account_id)`, routing directory | (reused, not defined here) | DM-PRD-09 `shared/residency/` |

## 7. Acceptance criteria

1. `NEO4J_CELLS` has an entry for every `Region` member; each entry's `uri` is **distinct** (a separate DBMS), and each entry has exactly **one** `database` — a unit test asserts no two regions share a `uri` and rejects any config that maps a region to a named-database-on-a-shared-instance shape.
2. `get_neo4j_for_account(account_id)` returns a `Neo4jService` whose driver points at the EU instance for an EU account and the US instance for a US account, resolving the region via DM-PRD-09's `resolve_account_region` (mocked).
3. Calling `get_neo4j_for_account` twice for two accounts in the **same** region returns the **same** cached `Neo4jService` (one connected driver per region, not per account).
4. The account-scoped chat org-context path (`chat.py:138`) acquires its Neo4j connection through `get_neo4j_for_account(account_id)`, not the bare global singleton — verified by a unit test asserting the call site.
5. On startup, `apply_all_migrations()` runs against **every** configured regional instance; on a fresh EU instance it applies the full KG-PRD-01 set (001 + 002) and records a `:Migration` ledger in the EU DBMS independently of the US ledger.
6. Startup fails fast (raises in the lifespan) if any configured regional instance is unreachable or cannot be brought to schema parity — the API does not serve account-scoped requests against an unmigrated instance.
7. An EU account's org-context query reads from the EU instance and returns **no** rows that exist only in the US instance (cell isolation), verified against two separate test DBMSs (or two databases standing in for two instances) seeded disjointly.
8. The retained global singleton (`database.py:309`) resolves to the US / default cell and is used only on region-agnostic paths (startup, migrations); no account-scoped call site reads it directly after the refactor (grep-gate in review + AC-4 unit guard).
9. `R-10 is not touched by this PR` — the cascade Cypher `account_id` binding is confirmed to ship as a separate hotfix; this PR's diff contains no change to `graph_sync_service.py` cascade `WHERE` clauses.
10. `make lint` passes. `pytest api/tests/unit/test_residency_neo4j_cells.py api/tests/unit/test_get_neo4j_for_account.py api/tests/integration/test_neo4j_region_routing.py` passes.
11. `lychee --config lychee.toml .` passes for the touched docs.

## 8. Test plan

### Unit (`test_residency_neo4j_cells.py`, `test_get_neo4j_for_account.py`)

- `NEO4J_CELLS` has an entry per `Region`; all `uri`s distinct; one `database` each; config that collapses two regions onto one `uri` raises (AC-1).
- `get_neo4j_for_account` returns the right cell's `Neo4jService` per region, resolving via a mocked `resolve_account_region` (AC-2).
- Per-region caching: two same-region accounts → identical `Neo4jService` object; constructor/connect invoked once per region across repeated calls (mock the driver) (AC-3).
- Call-site guard: assert the chat org-context path references `get_neo4j_for_account`, and that no account-scoped path references the bare global singleton (AC-4, AC-8).
- Default-region fallback: an unresolvable region resolves to `DEFAULT_REGION` (US), never to a missing target (AC-2/§4.2).

### Integration (`test_neo4j_region_routing.py`, two Neo4j test targets / two databases standing in for two instances)

- Fresh EU target → lifespan migration run applies 001 + 002 and writes an EU `:Migration` ledger independent of the US ledger (AC-5).
- Unreachable configured instance → startup raises; account-scoped requests are not served (AC-6).
- Seed US-only org-context data; an EU account's org-context query returns no US-only rows (cell isolation, AC-7).

### Regression

- KG-PRD-01's `test_migrations_applied.py` and the existing KG CRUD suite pass unchanged against the (default) US instance — single-region deployments where only US is configured behave exactly as before.

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| Stray `Neo4jService()` / `get_neo4j_service()` construction on an account-scoped path bypasses the resolver and silently stays US-only | Centralize on `get_neo4j_for_account`; AC-4/AC-8 unit guards + a grep review checklist for direct singleton use. Per-call-site straggler audit tracked as a Phase-1 follow-up, not a launch blocker. |
| EU instance missing at launch (Q4 unresolved) | Provisioning is gated on the Q4 decision (week 1). Until the EU instance exists and is migration-verified, EU sign-ups stay gated (design doc §6.1, D6) — under-promise beats a residency violation. |
| Migration set drifts between US and EU instances | Both instances render from the **same** KG-PRD-01 migration files; the runner iterates all configured instances each startup; AC-5 asserts ledger parity. |
| Per-region driver caching leaks a connection/credential across cells | One `Neo4jService` per `Region` keyed off `Neo4jCellConfig`; distinct credentials per cell; verified in dev before staging (mirrors DM-PRD-09's per-region client caching risk). |
| Confusing R-06 with R-10 and bundling the auth hotfix here | Out-of-scope §2 states R-10 ships as a standalone hotfix ahead of the program (design doc §6.4); AC-9 asserts this PR's diff does not touch the cascade `WHERE` clauses. |

### Open questions

- **Q4 — Neo4j EU host:** Aura-EU under our current plan, or self-host on EU GKE? **Decide week 1** (design doc §8 Q4). Determines `Neo4jCellConfig.uri` shape, credential management, and the infra provisioning ticket. Does not block writing this PRD's code (the resolver is host-agnostic) but **does** block standing up the EU cell.
- **Q6 — EU region:** confirm `europe-west1` (the existing GCS pattern) for the EU Neo4j instance, or a specific member-state region for sovereignty (carry from design doc §8).
- **Q7 — existing data:** confirmed green-field (new EU sign-ups only); no pre-launch EU strategy data in the US instance to migrate. Re-confirm at kickoff; if false, escalate to DR-PRD-10.
- **Q5 — org/region scope:** can one organization hold accounts in both cells? If yes, any cross-account KG sweep (session-end learning loop, KG-PRD-04) must fan out per region (DR-PRD-07). Does not block this slice but informs downstream KG work.

## 10. Reference

- Program spec: [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) — §2 (D1, D5, D6), §3.2 (cell table, Neo4j row), §3.4 (reference pattern), §4 (Neo4j posture), §5 (R-06; R-10 separate), §6.1 (launch blockers), §6.4 (R-10 hotfix), §7 (DR-PRD-04 row), §8 (Q4–Q7).
- Foundation (reused, not redefined): [`../../data-management/projects/DM-PRD-09-regional-cell-foundation.md`](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md) — `Region`/`CELLS` registry, routing directory, `resolve_account_region(account_id)`, `get_<resource>(account_id)` pattern.
- Sibling KG foundation: [`./KG-PRD-01-migrations-constraints-indexes.md`](./KG-PRD-01-migrations-constraints-indexes.md) — migration runner + schema set applied to both regional instances.
- Reference implementation: `api/src/kene_api/services/storage_service.py:31-72` (GCS `data_region` routing).
- Refactor targets: `api/src/kene_api/database.py:26-28`, `:76`, `:309`; `api/src/kene_api/config.py:28-31`; `api/src/kene_api/routers/chat.py:138-141`.
- CLAUDE.md rules in scope: PY-1, PY-2, PY-5, PY-7; D-1, D-5; T-1, T-3, T-4.
