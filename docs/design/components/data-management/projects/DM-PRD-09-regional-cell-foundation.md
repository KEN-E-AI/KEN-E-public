# DM-PRD-09 — Regional-Cell Foundation

**Status:** Ready to start
**Owner team:** [KEN-E] Data Management (Platform / Infra)
**Initiative:** Data Residency (US + EU)
**Blocked by:** DM-PRD-08 (production cutover — keeps the foundation off a still-migrating data plane)
**Parallel with:** —
**Blocks:** every per-component residency slice — DR-PRD-01 … DR-PRD-10 (see [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) §7)
**Estimated effort:** 4–5 days

> **Program context.** This is the **keystone** of the data-residency program. The program is *not* a new component: each subsequent slice is a PRD homed in the component that owns the affected code (`AH-PRD-NN`, `KG-PRD-NN`, `IN-PRD-NN`, …), bound together by the **Data Residency (US + EU)** Linear Initiative and the cross-component spec [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md). Read that doc's §1–§3 and §5 (gap register) before this PRD. This project closes **R-01, R-08, R-18, R-22** and ships the routing substrate every other slice reuses.

---

## 1. Context

KEN-E pins each account to a residency region via `data_region` (UI: "Data Storage Region"; values **US / EU**). Today exactly one data plane honors it — GCS business documents (`storage_service.py:_get_bucket_config`, US→`us-central1` / EU→`europe-west1`). Everything else is single-region (`us-central1`) or global: a **single global Firestore database** backs all US + EU accounts (`firestore.py:61-83`, `dependencies.py:20-37`), so EU regulated content physically lives in the US (**R-01**). Compounding this, `data_region` is **mutable after creation** with no guard (`accounts.py:832-834`) and **lacks enum validation** — unknown/absent values silently default to `"US"` at create time (`accounts.py:704`, `953`) (**R-08 / R-18**).

This PRD ships the **foundation** the rest of the program builds on:

1. **The regional-cell topology** — a second GCP project/region (EU) standing up an EU Firestore database (green-field), plus the Terraform shape to iterate regions × environments.
2. **The global routing directory + resolver** — an `account_id → home-region` lookup and a `get_<resource>(account_id)` DI pattern (the **Regional Cell routing convention**), modeled on `storage_service.py`. Firestore is the first store wired through it; downstream slices route Neo4j / KMS / model / Redis / BigQuery the same way.
3. **The cell invariant** — `data_region` becomes an immutable, enum-validated field, so an account cannot be silently moved between cells after its data has landed.

**No existing data is migrated.** Per open question Q7, the EU cell is green-field (new EU sign-ups only); a supervised region-migration tool is DR-PRD-10, explicitly out of scope here. **No store other than Firestore is regionalized here** — Neo4j (DR-PRD-04), KMS (DR-PRD-03), model/Agent Engine (DR-PRD-01), Redis/BigQuery (DR-PRD-05/06) are separate slices that consume this foundation's resolver.

See [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) §2 (locked decisions D1–D6), §3 (target architecture), §3.4 (reference pattern), §3.5 (model-endpoint strategy).

## 2. Scope

### In scope

- **Region registry** — a single canonical `Region` enum (`US`, `EU`) + a `data_region → (gcp_project_id, firestore_database_id, location)` config map, mirroring `storage_service.py`'s bucket-config map. One source of truth, imported everywhere.
- **Global routing directory** — a control-plane Firestore collection `account_regions/{account_id} → {region, updated_at}`, written at account creation, resolved once per request at the auth/account-selection boundary and pinned for the rest of the request.
- **Region resolver** — `resolve_account_region(account_id) -> Region` (directory fast-path, Neo4j fallback + backfill on miss) and `get_firestore_for_account(account_id) -> firestore.Client` returning the region-appropriate, per-region-cached client. This is the canonical **`get_<resource>(account_id)` pattern** the convention names.
- **Firestore DI refactor** — replace the two region-blind acquisition points (`dependencies.py::get_firestore_client` and `firestore.py::FirestoreService`) so account-scoped access is region-routed; the existing global singleton is retained **only** as the control-plane client used to read the routing directory (`dependencies.py:36-37`, acceptable per R-22).
- **`data_region` immutability** — `PUT /api/v1/accounts/{account_id}` rejects any request that changes `data_region` from its stored value (`accounts.py:832-834`); the frontend dropdown is disabled post-creation (`AccountSettingsTabs.tsx:442-461`).
- **`data_region` enum validation** — create + update validate `data_region ∈ {US, EU}` and reject unknown values with `422` instead of silently defaulting to `"US"` (`accounts.py:704`, `545-752`). Absent-on-create still defaults to `US` (documented default), but a *present* invalid value is rejected.
- **EU regional cell (Firestore only)** — Terraform for the EU GCP project + EU `(default)` Firestore database (`eur3`) + the EU composite/collection-group indexes (the same set as the US cell). Green-field; no data copy.
- **Convention docs** — fill the `[PLANNED]` placeholder at [`../README.md`](../README.md) §7.8 with the canonical Regional Cell routing convention, and append a "Regional Cell Routing Convention" section to `api/CLAUDE.md` next to the Shape B section.

### Out of scope

- **Regionalizing any store other than Firestore** — Neo4j (DR-PRD-04), KMS/tokens (DR-PRD-03), model/Agent Engine reasoning (DR-PRD-01), observability (DR-PRD-02), Redis/idempotency/artifacts (DR-PRD-05), usage/BigQuery (DR-PRD-06).
- **Migrating existing data into the EU cell** — green-field per Q7; supervised region migration is DR-PRD-10.
- **Cross-cell admin / global analytics fan-out** — DR-PRD-10.
- **Gating EU sign-ups behind a feature flag** — the launch gating rule (§6.1 of the design doc) is a Feature-Flags concern, wired when the cell is verified end-to-end.
- **The R-10 Neo4j cross-account `account_id` hotfix** — ships as a standalone PR ahead of the program (design doc §6.4).

## 3. Dependencies

- **DM-PRD-08** complete — the Shape B production cutover is done, so the foundation refactors a settled Firestore data plane, not a migrating one.
- Existing reference pattern: `api/src/kene_api/services/storage_service.py:31-72` (GCS `data_region` routing) — the shape this PRD generalizes.
- Existing Firestore index set: `deployment/firestore.indexes.json` + `deployment/terraform/firestore_indexes.tf` (DM-PRD-00) — replicated to the EU database.
- Existing per-env Terraform module shape (`deployment/terraform/`, `locals.tf::deploy_project_ids`) — extended to iterate regions × environments.
- **External / open:** confirm the EU GCP project naming + `eur3` location with infra (Q3, Q6). EU Agent Engine GA (Q1) does **not** block this PRD — it blocks DR-PRD-01.

## 4. Data contract

### 4.1 Region registry (single source of truth)

```python
# shared/residency/regions.py
from enum import StrEnum
from dataclasses import dataclass

class Region(StrEnum):
    US = "US"
    EU = "EU"

@dataclass(frozen=True)
class CellConfig:
    region: Region
    gcp_project_id: str          # e.g. "ken-e-us-{env}" / "ken-e-eu-{env}"
    firestore_database_id: str   # "(default)" per regional project
    location: str                # "us-central1" / "europe-west1"

# Built from env per deployment; US is the default cell.
CELLS: dict[Region, CellConfig] = { ... }

DEFAULT_REGION = Region.US

def normalize_region(value: str | None) -> Region:
    """Map UI strings ('United States'/'Europe'/'US'/'EU', case-insensitive)
    to a Region. Raises ValueError on an unknown non-empty value."""
```

### 4.2 Global routing directory

```
# Control-plane Firestore (global project), NOT account-scoped data — routing metadata only (R-22)
account_regions/{account_id}
  region:      "US" | "EU"      # mirror of the authoritative acc.data_region (Neo4j)
  updated_at:  <server timestamp>
```

- **Authoritative source** of an account's region remains `acc.data_region` on the Neo4j Account node. The directory is a read-optimized projection written at account creation; immutability (§4.3) guarantees the two never diverge.
- Holds **no regulated content** — `account_id` + region only.

### 4.3 `data_region` field rules

| Operation | Rule |
|---|---|
| Create (`POST /accounts`) | Absent → defaults to `US` (documented). Present → must `normalize_region()` to `US`/`EU`, else `422`. On success, write `acc.data_region` **and** `account_regions/{account_id}`. |
| Update (`PUT /accounts/{id}`) | `data_region` equal to stored value → no-op. `data_region` **different** from stored value → `409 Conflict` ("data_region is immutable; region migration is a supervised operation"). Unknown value → `422`. |

### 4.4 Resolver contract

```python
# shared/residency/routing.py
def resolve_account_region(account_id: str) -> Region:
    """Directory fast-path; on miss, read acc.data_region from Neo4j and backfill
    the directory. Result is request-scoped cacheable."""

def get_firestore_for_account(account_id: str) -> firestore.Client:
    """Return the regional Firestore client for the account's home cell.
    Per-region cached (one client per Region, not per account)."""
```

### 4.5 Resolver extension API (the contract every downstream slice reuses)

This foundation ships **Firestore** routing; every other residency slice (DR-PRD-01…10) regionalizes a *different* store by adding **one resolver of the same shape** — never a second region registry. Four things are fixed here so the slices compose instead of diverging (this is why each dependent PRD is `blocked_by` DM-PRD-09):

**(a) Module home — `shared/residency/`, importable by both `api/` and `app/`.** The registry and resolvers live under the top-level `shared/` package (alongside `shared.secrets`, `shared.token_accounting`), **not** `api/src/kene_api/`. Agent-plane slices (AH-PRD-11/12) run in the `app/` ADK deployable and must import the same `Region` / `CELLS` / `resolve_account_region` without coupling the agent runtime to the API package.

**(b) The `get_<resource>_for_account` shape.** Each slice appends one function to `shared/residency/routing.py` that resolves `account_id → Region` (via `resolve_account_region`) and returns the region-appropriate, per-region-cached client/handle for its store:

```python
# shared/residency/routing.py — one function per slice, all the same shape
def get_firestore_for_account(account_id: str) -> firestore.Client: ...    # DM-PRD-09 (this PRD)
def get_neo4j_for_account(account_id: str) -> Driver:            ...        # KG-PRD-07  (DR-PRD-04)
def get_kms_keyring_for_account(account_id: str) -> str:         ...        # IN-PRD-08  (DR-PRD-03)
def get_bigquery_for_account(account_id: str) -> bigquery.Client: ...       # BL-PRD-07 / SE-PRD-08
def get_redis_for_account(account_id: str) -> Redis:            ...         # CH-PRD-07  (DR-PRD-05)
def get_agent_cell_for_account(account_id: str) -> CellConfig:  ...         # AH-PRD-11  (DR-PRD-01)
```

**(c) A by-region accessor for cross-account fan-out.** Sweeps that iterate *every* cell (deletion / scheduler / audit — DR-PRD-07 / PR-PRD-10) need a client by region, not by account. The foundation ships:

```python
def get_cell_for_region(region: Region) -> CellConfig: ...               # registry lookup
def get_firestore_for_region(region: Region) -> firestore.Client: ...    # per-region cached client
# downstream fan-out helpers iterate CELLS.values() and run one query per cell
```

**(d) `CellConfig` is the single extensible registry row.** This PRD ships its Firestore/location fields; each downstream slice **appends its store's coordinates to the same `CellConfig`** rather than introducing a parallel registry — e.g. `neo4j_uri` (KG-PRD-07), `kms_keyring` (IN-PRD-08), `bigquery_dataset` (BL/SE), `redis_uri` (CH-PRD-07), `agent_engine_id` + `vertex_ai_location` (AH-PRD-11). New fields are optional with a US-cell default so adding one never breaks an unrelated cell. The foundation owns the file; slices contribute fields by PR — the same open-registry pattern as `MigrateConfig` in DM-PRD-00.

## 5. Implementation outline

| Action | File |
|---|---|
| Create | `shared/residency/__init__.py` |
| Create | `shared/residency/regions.py` — `Region` enum, `CellConfig`, `CELLS`, `normalize_region`, `DEFAULT_REGION` |
| Create | `shared/residency/routing.py` — `resolve_account_region`, `get_firestore_for_account`, `get_cell_for_region` / `get_firestore_for_region` (by-region fan-out accessors, §4.5c), control-plane directory read/write, per-region client cache |
| Modify | `api/src/kene_api/dependencies.py` — keep `get_firestore_client()` as the **control-plane** client (directory only); add `get_firestore_for_account` DI; document the split |
| Modify | `api/src/kene_api/firestore.py` — make `FirestoreService` region-aware (accept a resolved `CellConfig` / `account_id`); preserve lazy-init + ADC behavior |
| Modify | `api/src/kene_api/routers/accounts.py` — enum-validate `data_region` on create (`~704`); immutability guard on update (`832-834`); write `account_regions/{id}` on create |
| Modify | `frontend/.../AccountSettingsTabs.tsx` (`442-461`) — disable the Data Storage Region dropdown post-creation; tooltip "Region is fixed after creation" |
| Modify | `deployment/terraform/` — region × env iteration; EU GCP project + EU `(default)` Firestore (`eur3`) + EU index set; `locals.tf` region registry |
| Modify | [`../README.md`](../README.md) §7.8 — replace the `[PLANNED]` placeholder with the canonical convention |
| Modify | `api/CLAUDE.md` — append "Regional Cell Routing Convention" section |
| Create | `api/tests/unit/test_residency_regions.py`, `api/tests/unit/test_residency_routing.py` |
| Create | `api/tests/integration/test_account_region_immutability.py` |

## 6. API contract

This component publishes no new public HTTP surface; it constrains an existing endpoint and adds an internal DI contract.

| Contract | Consumed by | Source of truth |
|---|---|---|
| `PUT /api/v1/accounts/{account_id}` rejects a `data_region` change (`409`); rejects unknown values (`422`) | Account Settings UI, any account-update caller | `api/src/kene_api/routers/accounts.py` |
| `POST /api/v1/accounts` enum-validates `data_region` (`422` on invalid); writes the routing-directory entry | Account-creation flow | `api/src/kene_api/routers/accounts.py` |
| `Region` enum + `CELLS` config map + `normalize_region()` | Every component that regionalizes a store (DR-PRD-01…10) | `shared/residency/regions.py` |
| `resolve_account_region(account_id)` + `get_firestore_for_account(account_id)` (the `get_<resource>(account_id)` pattern) | Every account-scoped Firestore read/write; the template every other store's resolver copies | `shared/residency/routing.py` |
| **Resolver extension API** (§4.5) — the `get_<resource>_for_account` shape, `get_cell_for_region` / `get_firestore_for_region` (fan-out), and the extensible `CellConfig` registry | Every downstream residency slice (DR-PRD-01…10) — each appends one resolver + its `CellConfig` fields | `shared/residency/routing.py`, `shared/residency/regions.py` |

## 7. Acceptance criteria

1. `normalize_region` maps `"United States"`, `"US"`, `"us"` → `Region.US`; `"Europe"`, `"EU"`, `"eu"` → `Region.EU`; raises `ValueError` on `"APAC"` / any unknown non-empty value; `None`/`""` → handled by the caller's default rule.
2. `POST /api/v1/accounts` with `data_region="APAC"` returns `422`; with no `data_region` creates an account with `data_region="US"`; with `data_region="EU"` writes `acc.data_region="EU"` **and** `account_regions/{id}.region="EU"`.
3. `PUT /api/v1/accounts/{id}` changing `data_region` from the stored value returns `409` and does not mutate `acc.data_region`; sending the **same** value is a `200` no-op on that field.
4. `get_firestore_for_account(account_id)` returns a client pointed at the EU project/`europe-west1` for an EU account and the US project/`us-central1` for a US account; calling it twice for the same region returns the **same** cached client (one client per region, not per account).
5. `resolve_account_region` returns the directory value on a hit; on a directory miss it reads `acc.data_region` from Neo4j, returns it, and backfills `account_regions/{id}`.
6. The control-plane `get_firestore_client()` is used **only** to read `account_regions/*`; no account-scoped collection (`accounts/*`, `users/*`, …) is read through it (enforced by a unit test asserting call sites + a grep gate in review).
7. EU Terraform applies cleanly in dev: `gcloud firestore databases list --project=<eu-dev-project>` shows a `(default)` database in `eur3`, and `gcloud firestore indexes composite list` shows the full index set `READY` (operator-verified; not gated in CI).
8. The frontend Data Storage Region dropdown is disabled for an existing account and enabled only on the create form.
9. [`../README.md`](../README.md) §7.8 no longer says `[PLANNED]` and documents the `get_<resource>(account_id)` pattern; `api/CLAUDE.md` has the "Regional Cell Routing Convention" section.
10. `make lint` passes. `pytest api/tests/unit/test_residency_regions.py api/tests/unit/test_residency_routing.py api/tests/integration/test_account_region_immutability.py` passes.
11. `lychee --config lychee.toml .` passes for the touched docs.

## 8. Test plan

### Unit (`test_residency_regions.py`, `test_residency_routing.py`)

- `normalize_region` table-driven over the alias set + unknown-value rejection (AC-1).
- `CELLS` has an entry for every `Region` member; `DEFAULT_REGION is Region.US`.
- `get_firestore_for_account` returns the right `CellConfig` per region and caches one client per region (mock `firestore.Client`; assert constructor called once per region across repeated calls) (AC-4).
- `resolve_account_region`: directory hit → no Neo4j call; directory miss → Neo4j read + directory backfill write (AC-5).
- Control-plane-isolation guard: assert `get_firestore_client()` is referenced only by the directory reader (AC-6).

### Integration (`test_account_region_immutability.py`, Firestore emulator + mocked Neo4j)

- Create with `data_region="EU"` → `acc.data_region` and `account_regions/{id}` both `"EU"` (AC-2).
- Create with `data_region="APAC"` → `422`, nothing written (AC-2).
- Update changing region → `409`, stored value unchanged (AC-3).
- Update with identical region → `200`, no-op (AC-3).

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| Stray `firestore.Client()` / `FirestoreService` instantiations bypass the resolver and silently stay US-only | Centralize on the two DI paths; add a `grep`-based review checklist item for direct client construction; AC-6 unit guard. Per-collection straggler audit tracked as a Phase-1 follow-up, not a launch blocker. |
| Directory ↔ Neo4j divergence | Immutability guard (§4.3) means region is write-once; the only writer is account creation. Resolver backfills on miss. DR-PRD-10 owns the supervised re-write. |
| EU index set drifts from US | Both cells render from the same `firestore.indexes.json`; Terraform applies it to each regional database. |
| Per-region client caching leaks across credentials | One client per `Region` keyed off `CellConfig`; ADC resolves per-project — verified in dev before staging. |

### Open questions (carry from design doc §8)

- **Q3 — topology:** confirm one GCP project per region (recommended) vs. one project with regional resources. Decides `CellConfig.gcp_project_id` shape. **Needed before Terraform.**
- **Q6 — EU region:** confirm `europe-west1` / `eur3` for all EU stores, or a specific member-state region for sovereignty.
- **Q7 — existing data:** confirmed green-field (new EU sign-ups only); no pre-launch EU data in the US cell to migrate. Re-confirm at kickoff.
- **Q5 — org/region scope:** can one organization hold accounts in both cells? Affects whether cross-account sweeps (DR-PRD-07) must fan out per region. Does not block this PRD but informs the directory key design.

## 10. Reference

- Program spec: [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) — §2 decisions, §3.1 control plane, §3.4 reference pattern, §3.5 model endpoints, §5 gap register (R-01/R-08/R-18/R-22), §7 PRD breakdown.
- Reference implementation: `api/src/kene_api/services/storage_service.py:31-72` (GCS `data_region` routing).
- Refactor targets: `api/src/kene_api/dependencies.py:20-56`, `api/src/kene_api/firestore.py:49-95`, `api/src/kene_api/routers/accounts.py:556`, `704`, `832-834`.
- Convention home: [`../README.md`](../README.md) §7.8; Shape B sibling convention: §7.1.
- CLAUDE.md rules in scope: PY-1, PY-2, PY-5, PY-7; D-2, D-5; T-1, T-3, T-4, T-6.
