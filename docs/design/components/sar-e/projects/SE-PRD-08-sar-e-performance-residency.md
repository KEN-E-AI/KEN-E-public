# SE-PRD-08 — SAR-E / Performance Residency-by-Design

**Status:** Ready to start
**Owner team:** [KEN-E] SAR-E (Performance attached for visibility)
**Initiative:** Data Residency (US + EU)
**Blocked by:** DM-PRD-09 (Regional-cell foundation), SE-PRD-01 (Configuration foundation)
**Blocks:** —
**Estimated effort:** 3–4 days

> **Program context.** This is a slice of the **Data Residency (US + EU)** program; it is **not** a new component. It is homed in SAR-E, with Performance attached because the same guard-rail covers the Performance BFF. Read [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) §1–§3 (target architecture), §5 (gap register — this PRD closes **R-20**), §6.3 (phase 2 cut-line) before this PRD. The **keystone is [`../../data-management/projects/DM-PRD-09-regional-cell-foundation.md`](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md)**; this PRD **reuses** its `Region` / `CELLS` registry and its `resolve_account_region(account_id)` / `get_firestore_for_account(account_id)` resolver — it does **not** redefine them.

---

## 1. Context

SAR-E and Performance are **still being built** — no `sar_e_*` service, router, model, or specialist file yet exists under `api/src/kene_api/` (verified 2026-05-29: the `api/src/kene_api/routers/sar_e_*.py`, `services/sar_e_*.py`, `models/sar_e_models.py`, and `app/adk/agents/performance_forecasting/` paths enumerated in [`../README.md`](../README.md) §2.1 are PRD-only). The only analytical code on disk is the unrelated, single-instance `BigQueryService` at `api/src/kene_api/bigquery.py:22-72` (holiday-calendar lookups) and the reference GCS pattern at `api/src/kene_api/services/storage_service.py:31-72`.

This is what makes **R-20** a phase-2 gap rather than a phase-1 blocker: there is no EU SAR-E content in the US cell to leak *today*, because there is no SAR-E content at all. But every account-scoped store SAR-E is specified to own — `accounts/{account_id}/sar_e_config`, `effectiveness_kpis`, `kpi_time_series`, `funnel_mapping` (+history), `thresholds`, `channel_coverage`, `baselines`, `irf_coefficients`, `targets` ([`../README.md`](../README.md) §7) — and the Performance `accounts/{account_id}/performance_wizard_draft` doc ([`../../performance/README.md`](../../performance/README.md) §7) will land as **single-region Firestore** if built against the pre-foundation `FirestoreService` / `get_firestore_client()` acquisition path, inheriting every leak DM-PRD-09 exists to close.

This PRD is therefore a **residency-by-design guard-rail**, not a retrofit. It does not change any analytical behaviour, response shape, or statistical method. It bakes one rule into SE-PRD-01/02/05/06 and PE-PRD-01 before they ship: **every account-scoped SAR-E / Performance Firestore handle, the analytical query layer, and the Performance BFF acquire their datastore through the DM-PRD-09 resolver, keyed on `data_region`.** Because each regional cell runs its own Agent Engine ([`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) §3.5), the `performance_forecasting` specialist (Gemini 2.0 Pro, SE-PRD-05) is region-resident *by virtue of the cell it runs in* — this PRD adds no per-account model routing, only the requirement that the specialist's Firestore tool reads (`get_baseline`, `get_historical_pulses`) go through the same resolver.

This PRD also **absorbs** the per-region BigQuery **dataset** work that the program split out of `BL-PRD-07` (logical `DR-PRD-06`). Per [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) §7, `DR-PRD-06` keeps the `usage_records` / `tool_usage_events` Shape-B conversion in billing (`BL-PRD-07`) but explicitly hands "BigQuery work split to a future SE-PRD" to SAR-E — this is that SE-PRD. See §2 and the linkage note in §10.

## 2. Scope

### In scope

- **Foundation-resolver mandate (the guard-rail).** Every account-scoped SAR-E Firestore acquisition — in `routers/sar_e_*.py`, `services/sar_e_*.py`, and the `performance_forecasting` specialist's Firestore-backed tools — and the Performance BFF (`routers/performance.py`, `services/performance_bundle_composer.py`, `performance_simulation_orchestrator.py`) **must** obtain its client via `get_firestore_for_account(account_id)` from `shared/residency/routing.py` (DM-PRD-09). No `FirestoreService()` constructed for account data, no `firestore.Client()`, no `get_firestore_client()` (control-plane only) on an account path.
- **Analytical query layer routing (SE-PRD-06).** `sar_e_analytics_service` collection-group reads (`kpi_time_series`, `plans.tasks` cost-rollup joins, `funnel_mapping_history`) run against the **account's regional Firestore**, never a global sweep. The in-process `analytics_cache` LRU ([`../README.md`](../README.md) §2.1) is keyed by `(account_id, …)` — already region-disjoint since accounts never cross cells (D5) — and this PRD records that invariant so no future cache key conflates regions.
- **Performance BFF routing (PE-PRD-01).** The five composite read endpoints + `/simulations/run` orchestrator + `wizard-draft` CRUD resolve the account region once at the BFF boundary and thread the resolved Firestore client through `asyncio.gather` fan-out — one resolution per request, reused across SAR-E reads (mirrors the "resolved once per request and pinned" rule, [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) §3.1).
- **Per-region BigQuery datasets (absorbed from `DR-PRD-06`).** A `get_bigquery_for_account(account_id)` resolver layered on the DM-PRD-09 `CELLS` registry, returning a per-region-cached `bigquery.Client` pinned to the account's regional dataset/location (US dataset / `us-central1`; EU dataset / `europe-west1`), replicating the `storage_service` map shape. Any SAR-E analytical path that reads/writes BigQuery routes through it. (Note: SAR-E's primary stores are Firestore; this resolver exists so the split-out BigQuery dataset work has a home and the same guard-rail covers it.)
- **CI grep guard.** A `make lint` check (modelled on SE-PRD-07's methodology-language gate, [`../README.md`](../README.md) §2.1 `api/tests/lint/`) that **fails** when a `sar_e_*` or `performance*` source file constructs a single-region datastore directly — `FirestoreService(`, `firestore.Client(`, `bigquery.Client(`, or `get_firestore_client(` — outside the allowlisted control-plane reader. An allowlist file (`api/tests/lint/residency_allowlist.txt`) handles documented exceptions with reasons.
- **Doc annotations.** A short "Residency" note appended to the `### Conventions and Constraints` section of [`../README.md`](../README.md) and to [`../../performance/README.md`](../../performance/README.md) stating the resolver mandate, so a dev implementing SE-PRD-01/02/05/06 or PE-PRD-01 reads it during Step 3 of the Context Loading Sequence.

### Out of scope

- **Defining the resolver, `Region`/`CELLS`, the routing directory, `data_region` immutability/enum validation.** Owned by DM-PRD-09; reused, never redefined.
- **EU cell standup (GCP project, EU Firestore database, EU BigQuery dataset, Terraform region×env iteration).** Firestore cell is DM-PRD-09; the EU **BigQuery dataset resource** itself is provisioned by the same Terraform region-iteration shape DM-PRD-09 establishes — this PRD consumes the dataset registry, it does not author the infra module.
- **Model-inference / Agent-Engine residency.** The specialist's reasoning location is pinned by the cell's Agent Engine (`DR-PRD-01` → `AH-PRD-11`); this PRD only routes the specialist's **Firestore tool reads**.
- **`usage_records` / `tool_usage_events` Shape-B conversion.** Stays in billing (`BL-PRD-07`, logical `DR-PRD-06`); only the BigQuery dataset routing is absorbed here.
- **Any change to analytical behaviour** — VAR, IRF, target derivation, cost-rollup math, caching TTLs, response schemas, the "association only" invariant. Residency-only.
- **Cross-cell admin / global analytics fan-out and region migration.** `DR-PRD-10` (`DM-PRD-10`).

## 3. Dependencies

- **DM-PRD-09 (Regional-cell foundation)** — **hard prerequisite.** Supplies `Region` / `CellConfig` / `CELLS` / `normalize_region` (`shared/residency/regions.py`) and `resolve_account_region(account_id)` / `get_firestore_for_account(account_id)` (`shared/residency/routing.py`), the per-region client cache, the global routing directory, and `data_region` immutability + enum validation. This PRD is a thin consumer; if DM-PRD-09's resolver signature changes, this PRD follows it.
- **SE-PRD-01 (Configuration foundation)** — **hard prerequisite.** First SAR-E PRD to construct a Firestore handle (the `POST /config/setup` transaction, `sar_e_config_service`). The guard-rail must be in place before SE-PRD-01's Firestore acquisition is written, so SE-PRD-01 is built region-routed from line one rather than refactored. The remaining SAR-E/Performance PRDs (SE-PRD-02/03/04/05/06, PE-PRD-01) inherit the rule via the CI guard.
- Reference pattern: `api/src/kene_api/services/storage_service.py:31-72` (GCS `data_region` → `(bucket, location)` map) — the shape `get_bigquery_for_account` replicates.
- Existing BigQuery service to be region-wrapped/replaced on account paths: `api/src/kene_api/bigquery.py:22-72` (today a single global `bigquery.Client(project=…)`, no region routing).
- Existing methodology-lint gate as the structural template for the new grep guard: [`../README.md`](../README.md) §2.1 (`api/tests/lint/test_methodology_language.py` + `methodology_allowlist.txt`).
- **External / open:** confirm whether SAR-E v1 actually writes to BigQuery at all, or only Firestore (Q1 below). The resolver ships regardless so the absorbed `DR-PRD-06` split has a home, but its wiring footprint depends on the answer.

## 4. Data contract

This PRD introduces **no new persisted schema** — every SAR-E / Performance Firestore surface keeps the Shape B layout and Pydantic models defined by SE-PRD-01/02/05/06 + PE-PRD-01. It adds one internal resolver contract and reuses two from DM-PRD-09.

### 4.1 Reused from DM-PRD-09 (do not redefine)

```python
# shared/residency/regions.py  (DM-PRD-09)
class Region(StrEnum): US = "US"; EU = "EU"
CELLS: dict[Region, CellConfig]            # region → (gcp_project_id, firestore_database_id, location, …)

# shared/residency/routing.py   (DM-PRD-09)
def resolve_account_region(account_id: str) -> Region: ...
def get_firestore_for_account(account_id: str) -> firestore.Client: ...
```

### 4.2 New in this PRD (absorbed BigQuery split)

```python
# shared/residency/routing.py  (additive — same module, DM-PRD-09 pattern)
def get_bigquery_for_account(account_id: str) -> bigquery.Client:
    """Return the regional BigQuery client for the account's home cell.
    Resolves Region via resolve_account_region(); selects dataset + location
    from the DM-PRD-09 CELLS registry (extended with a bigquery_dataset_id /
    location field). Per-region cached (one client per Region, not per account),
    mirroring get_firestore_for_account and storage_service._get_bucket_config."""
```

- **No regulated content in any routing artifact** — region resolution uses the global directory's `account_id → region` mapping only (R-22).
- **Cache-key invariant (recorded, not new code):** SAR-E's `analytics_cache` LRU keys already begin with `account_id`; since an account is immutably pinned to one cell (D5), region never needs to enter the cache key. This PRD documents that as a constraint so a future contributor cannot introduce a region-blind global cache key.

## 5. Implementation outline

| Action | File | Notes |
|---|---|---|
| Add | `shared/residency/routing.py` | `get_bigquery_for_account(account_id)` (§4.2); extend the DM-PRD-09 per-region client cache. **Coordinate with DM-PRD-09** — same module. |
| Constrain | `api/src/kene_api/routers/sar_e_*.py`, `api/src/kene_api/services/sar_e_*.py` (SE-PRD-01/02/05/06) | Every account-scoped Firestore handle via `get_firestore_for_account(account_id)`; BigQuery (if any) via `get_bigquery_for_account(account_id)`. No direct client construction. *(Files created by SE-PRD-01..06 — this PRD sets the rule they are built to.)* |
| Constrain | `app/adk/agents/performance_forecasting/tools.py` (SE-PRD-05) | `get_baseline` / `get_historical_pulses` Firestore reads via the resolver. |
| Constrain | `api/src/kene_api/routers/performance.py`, `services/performance_bundle_composer.py`, `services/performance_simulation_orchestrator.py` (PE-PRD-01/03) | Resolve account region once at the BFF boundary; thread the resolved client through the fan-out. |
| Create | `api/tests/lint/test_residency_datastore_routing.py` | `make lint` grep guard: fail on `FirestoreService(` / `firestore.Client(` / `bigquery.Client(` / `get_firestore_client(` in `sar_e_*` / `performance*` source, outside the allowlist. |
| Create | `api/tests/lint/residency_allowlist.txt` | Documented exceptions (e.g. a deliberate control-plane read), each with a reason. |
| Create | `api/tests/unit/test_sar_e_residency_routing.py` | Resolver-usage unit tests (AC-1, AC-2, AC-5). |
| Modify | [`../README.md`](../README.md) | Append a "Residency (Regional Cell routing)" note to §7 Conventions and Constraints. |
| Modify | [`../../performance/README.md`](../../performance/README.md) | Append the same residency note to §7 Conventions and Constraints (BFF + wizard-draft route via the resolver). |

## 6. API contract

**No new public HTTP surface.** Every SAR-E `/api/v1/sar-e/{account_id}/*` and Performance `/api/v1/performance/{account_id}/*` endpoint keeps the contract defined in SE-PRD-01..06 / PE-PRD-01 ([`../README.md`](../README.md) §2.3, [`../../performance/README.md`](../../performance/README.md) §2.3). This PRD changes only **which physical datastore those endpoints hit**: the account's regional cell, resolved from `data_region`.

| Internal contract | Consumed by | Source of truth |
|---|---|---|
| `get_firestore_for_account(account_id)` (reused) | Every account-scoped SAR-E + Performance Firestore read/write | `shared/residency/routing.py` (DM-PRD-09) |
| `get_bigquery_for_account(account_id)` (new, §4.2) | Any SAR-E analytical BigQuery read/write | `shared/residency/routing.py` |
| CI grep guard: no direct single-region client in `sar_e_*` / `performance*` | `make lint` (review gate) | `api/tests/lint/test_residency_datastore_routing.py` |

## 7. Acceptance criteria

1. **No direct Firestore on an account path.** Every account-scoped Firestore acquisition in `sar_e_*` / `performance*` source resolves through `get_firestore_for_account(account_id)`; a static scan finds zero `FirestoreService(` / `firestore.Client(` constructions and zero `get_firestore_client(` calls on an account path in those files.
2. **CI grep guard fails on a direct single-region client.** Adding a bare `firestore.Client()` (or `FirestoreService()` / `bigquery.Client()`) to a `sar_e_*` or `performance*` file fails `make lint` via `test_residency_datastore_routing.py`; removing it (or routing through the resolver) makes `make lint` pass. The allowlist file suppresses only documented, reasoned exceptions.
3. **EU SAR-E account hits the EU cell.** With a mocked DM-PRD-09 resolver, a SAR-E read for an `EU` account returns a client pointed at the EU project / `europe-west1`; the same read for a `US` account hits the US project / `us-central1`. Two reads for the same region reuse the **same** cached client (one per region, not per account).
4. **BigQuery resolver routes by region.** `get_bigquery_for_account(account_id)` returns an EU-dataset/`europe-west1` client for an EU account and a US-dataset/`us-central1` client for a US account, per-region cached, matching `storage_service._get_bucket_config`'s shape (AC mirrors DM-PRD-09 AC-4).
5. **BFF resolves region once per request.** A Performance bundle request resolves the account region exactly once at the BFF boundary and reuses the resolved client across the `asyncio.gather` SAR-E fan-out (asserted by call-count on a mocked resolver) — no per-section re-resolution.
6. **Specialist tool reads are region-routed.** The `performance_forecasting` specialist's `get_baseline` / `get_historical_pulses` Firestore reads go through `get_firestore_for_account(account_id)` (unit-asserted on the tool boundary).
7. **No behaviour change.** SE-PRD-01..06 + PE-PRD-01 acceptance tests pass unchanged — response shapes, VAR/IRF/target outputs, cost-rollup, caching TTLs, and the "association only" lint are unaffected.
8. **Docs.** [`../README.md`](../README.md) §7 and [`../../performance/README.md`](../../performance/README.md) §7 each carry the residency note naming the `get_<resource>(account_id)` mandate and pointing at DM-PRD-09.
9. `make lint` passes (including the new guard + the existing methodology gate). `lychee --config lychee.toml .` passes for the touched docs.

## 8. Test plan

### Unit (`test_sar_e_residency_routing.py`)

- `get_bigquery_for_account` returns the right `CellConfig`-derived dataset/location per region and caches one client per region (mock `bigquery.Client`; constructor called once per region across repeated calls) (AC-4).
- A representative SAR-E service method (stubbed against SE-PRD-01's `sar_e_config_service`) acquires its Firestore handle via `get_firestore_for_account` with the request's `account_id` — assert the resolver is called and no direct constructor is touched (AC-1, AC-3).
- The Performance BFF composer resolves region once and passes the single client into the fan-out (mock resolver, assert call count = 1) (AC-5).
- Specialist tool boundary: `get_baseline` / `get_historical_pulses` route through the resolver (AC-6).

### Lint guard (`test_residency_datastore_routing.py`)

- Table-driven over the banned-construction patterns: a fixture file containing a bare `firestore.Client()` in a `sar_e_*` path → guard fails; the same content routed through `get_firestore_for_account` → guard passes; an allowlisted line → guard passes (AC-2).
- Confirms the guard scans the full `sar_e_*` + `performance*` source set and respects `residency_allowlist.txt`.

### Integration (Firestore emulator + mocked DM-PRD-09 resolver)

- An `EU` account's SAR-E read lands in the EU-configured emulator target and a `US` account's in the US target; no read crosses cells (AC-3). Reuses DM-PRD-09's emulator harness — this PRD does not stand up its own.

### Regression

- The existing SE-PRD-01..06 + PE-PRD-01 unit/integration suites run unchanged and green (AC-7).

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| SAR-E/Performance PRDs (01..06, PE-01) are authored/implemented **before** this guard lands, shipping single-region acquisition that must be retrofitted — exactly the leak R-20 warns of. | This PRD is `blocked_by` SE-PRD-01 specifically so the guard exists at SE-PRD-01 implementation time; the CI grep guard then fails any later straggler in SE-PRD-02..06 / PE-PRD-01 at PR time. Sequence: land the guard + resolver wiring as SE-PRD-01's first commit. |
| A contributor constructs `firestore.Client()` directly to "just read one doc," bypassing the resolver and silently staying US-only. | The `make lint` grep guard (AC-2) blocks it in CI; the allowlist forces a documented, reviewed reason for any exception. Mirrors the methodology-language gate that already polices `sar_e_*`. |
| DM-PRD-09 resolver signature shifts after this PRD is drafted. | This PRD is a pure consumer; treat DM-PRD-09's `routing.py` as the contract and follow it. `get_bigquery_for_account` is added to the *same* module to avoid a parallel cache. |
| Region-blind in-process analytics cache key conflates cells. | Recorded invariant (§4.2): account is immutably single-cell (D5), keys begin with `account_id`. Unit test asserts no global/region-less cache key is introduced. |

### Open questions

- **Q1 — Does SAR-E v1 read/write BigQuery at all,** or are all nine SAR-E stores Firestore-only (the README §7 layout is entirely Firestore)? If Firestore-only, `get_bigquery_for_account` still ships (it is the home for the absorbed `DR-PRD-06` BigQuery-dataset split) but has no SAR-E caller yet; confirm at kickoff so the wiring footprint is right.
- **Q2 — `CELLS` BigQuery field shape.** Confirm with DM-PRD-09 whether the per-region BigQuery dataset id + location lives on `CellConfig` (preferred — one registry) or a sibling map. Decides the `get_bigquery_for_account` lookup.
- **Q3 — Specialist Firestore-tool execution context.** Confirm the `performance_forecasting` tools execute in the API process (where the resolver is importable) vs. the Agent Engine runtime; if the latter, the `account_id` must be threaded into the tool call so the resolver can run cell-side.
- **Q4 — `BL-PRD-07` coordination.** `BL-PRD-07` (logical `DR-PRD-06`) owns `usage_records` / `tool_usage_events` Shape-B conversion and is authored separately; confirm at kickoff that the BigQuery dataset split is *only* here and not double-owned.

## 10. Reference

- Program spec: [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) — §1–§3 (target architecture, reference pattern §3.4, model strategy §3.5), §5 (gap register, **R-20** row + **R-22** control-plane confirmation), §6.3 (phase 2 cut-line), §7 (PRD breakdown — `DR-PRD-09` → this PRD; `DR-PRD-06` → `BL-PRD-07` "+ sar-e" with the BigQuery split handed here).
- Keystone reused (not redefined): [`../../data-management/projects/DM-PRD-09-regional-cell-foundation.md`](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md) — `Region` / `CELLS`, `resolve_account_region`, `get_firestore_for_account`, the per-region client cache, `data_region` immutability + enum.
- Reference implementation: `api/src/kene_api/services/storage_service.py:31-72` (GCS `data_region` routing — the shape `get_bigquery_for_account` replicates). Existing un-routed analytical client: `api/src/kene_api/bigquery.py:22-72`.
- Guard-railed siblings (built region-routed from line one): [`./SE-PRD-01-configuration-foundation.md`](./SE-PRD-01-configuration-foundation.md), [`./SE-PRD-02-weekly-kpi-ingestion.md`](./SE-PRD-02-weekly-kpi-ingestion.md), [`./SE-PRD-05-target-derivation-specialist.md`](./SE-PRD-05-target-derivation-specialist.md), [`./SE-PRD-06-analytical-query-layer.md`](./SE-PRD-06-analytical-query-layer.md); Performance shell/BFF: [`../../performance/projects/PE-PRD-01-page-shell-and-routing.md`](../../performance/projects/PE-PRD-01-page-shell-and-routing.md).
- Billing sibling (absorbed-split linkage): `BL-PRD-07` — Telemetry & Analytics Residency (logical `DR-PRD-06`), homed in [`../../billing/README.md`](../../billing/README.md); keeps `usage_records` / `tool_usage_events` Shape-B conversion, hands the BigQuery-dataset routing to this PRD. *(The `BL-PRD-07` document is not yet authored; referenced by allocated ID per the program spec §7.)*
- Component context: [`../README.md`](../README.md) (SAR-E stores §7, lint-gate template §2.1), [`../../performance/README.md`](../../performance/README.md) (BFF + wizard-draft §2, §7).
- CLAUDE.md rules in scope: PY-1, PY-5, PY-7; D-1, D-5; O-1; T-1, T-4, T-6; G-1, G-4.
