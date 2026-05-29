# BL-PRD-07 — Telemetry & Analytics Residency

**Status:** Ready to start
**Owner team:** [KEN-E] Billing
**Initiative:** Data Residency (US + EU)
**Blocked by:** [DM-PRD-09](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md), [BL-PRD-02](./BL-PRD-02-token-meter-monthly-enforcement.md)
**Blocks:** —
**Estimated effort:** 3–4 days
**Cut-line:** Phase 1 (post-launch regional-cell hardening — design doc §6.2)

> **Program context.** This is the **DR-PRD-06** slice of the data-residency program — homed in Billing because it owns the usage-write path (`usage_records`, `tool_usage_events`). The program is *not* a new component: it is held together by the cross-component spec [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) and the **Data Residency (US + EU)** Linear Initiative. Read that doc's §1–§4 and §5 (gap register) before this PRD. This PRD closes **R-13** (telemetry/usage collections, owned here) and is the billing half of **R-14** (BigQuery — the per-region *dataset* work is owned by SAR-E and split to [`SE-PRD-08`](../../sar-e/projects/SE-PRD-08-sar-e-performance-residency.md); see §2 boundary).

---

## 1. Context

KEN-E pins each account to a residency region via the **immutable, enum-validated** `data_region` (US / EU) shipped by the keystone [`DM-PRD-09`](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md). That PRD ships the **Regional Cell routing convention** — `resolve_account_region(account_id) -> Region`, `get_firestore_for_account(account_id) -> firestore.Client`, the `Region` enum, and the `CELLS` config map (`../../data-management/README.md` §7.8). Firestore is the only store it wires through the resolver; every other store is a separate, dependent slice. **This PRD wires the billing/telemetry stores through that same resolver — it does not redefine any of it.**

Two telemetry stores in Billing's ownership are still **single-region or global**, so once the EU Firestore database is split out (`DM-PRD-09`), EU usage data is unreachable from the EU cell:

1. **`usage_records` (Shape C)** — `POST /usage/record` writes to a top-level `usage_records/{record_id}` collection on the **single global** Firestore client (`api/src/kene_api/routers/usage.py:23` `db = firestore.Client()`; write at `:258`; reads at `:129`, `:192`, `:300`). All EU usage rows physically land in the US database (**R-13**).
2. **`tool_usage_events` (Shape C)** — the ADK usage tracker batches tool-execution events into a top-level `tool_usage_events` collection on its own ADC-built global client (`app/adk/tracking/usage.py:135` `COLLECTION_NAME`; client at `:159-175`; flush at `:262`). Same leak, ADK side (**R-13**).

A distinct concern: **`usage_records` is a deliberate Shape-C carve-out** (`../../data-management/README.md` §7.1, §7.4 — "remain Shape C — do not migrate, do not touch") justified by org-level billing aggregation across accounts. Residency forces an exception to that carve-out: the rows must become **physically region-resident**. This PRD resolves the tension by keeping the carve-out *logically* (still a top-level, `account_id`-tagged collection, queried org-wide within a cell) while routing the collection's **physical Firestore client by region** — the same move `DM-PRD-09` makes for `accounts/*`. **No path-shape migration to Shape B is performed** (that would break the cross-account org aggregation the carve-out exists for); only the underlying client is regionalized. This is called out explicitly so the next reader of §7.1 understands why a residency PRD touches a "do not touch" collection. See §9-Q1.

A third store, **BigQuery, is single-region (US dataset)** (`api/src/kene_api/bigquery.py:42` `project_id` from `GOOGLE_CLOUD_PROJECT_ID`; client at `:59-62`; query at `:245-255`) — **R-14**. The cross-component boundary in §2 governs how much of R-14 lands here.

See [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) §2 (D1, D3), §3.2 (per-region row), §3.4 (reference pattern), §4 (BigQuery posture), §5 (R-13, R-14).

## 2. Scope

### In scope

- **`usage_records` regional routing** — replace the module-global `db = firestore.Client()` (`usage.py:23`) with the `DM-PRD-09` resolver. The write path (`POST /usage/record`, `:258`) routes the record to `get_firestore_for_account(usage_record.account_id)` so the row physically lands in the writing account's home cell. The collection stays top-level + `account_id`-tagged (Shape-C preserved logically per §1); only the client is region-selected.
- **Region-scoped reads** — the three read endpoints (`get_user_costs` `:129`, `get_account_costs` `:192`, `get_overall_usage` `:300`) read from the region-appropriate client: account/user-scoped reads resolve the single account's region; the super-admin `get_overall_usage` cross-cell read fans out across **both** cells (`for region in Region: get_firestore_for_region(region)`) and merges. (Cross-cell admin *fan-out helper* generalization is DR-PRD-10 / `DM-PRD-10`; here we add the minimal per-cell loop this one super-admin endpoint needs, not a generic framework.)
- **`tool_usage_events` regional routing** — the ADK `UsageTracker` (`app/adk/tracking/usage.py`) becomes region-aware: events carry `account_id` (already passed to `track_execution`, `:181`), and `_flush_batch` (`:251-276`) groups the batch by resolved region and commits each group to that region's client. The aggregation read (`get_usage_aggregation`, consumed by `/usage/tool-usage` at `usage.py:438`) fans across cells the same way as `get_overall_usage`.
- **Reuse-only of the foundation** — `Region`, `CELLS`, `normalize_region`, `resolve_account_region`, `get_firestore_for_account` are imported from `shared/residency/` (DM-PRD-09). A thin `get_firestore_for_region(region: Region)` accessor (per-region cached, same one-client-per-region semantics) is added **only if** DM-PRD-09 did not already expose it for the fan-out case; otherwise reused. No new resolver, registry, or config map.
- **BigQuery client selection by region (billing-owned half of R-14)** — `bigquery.py` selects the regional dataset's GCP project/location via the `CELLS` map keyed by an account's `data_region`, instead of the ambient `GOOGLE_CLOUD_PROJECT_ID` (`:42`, `:59-62`). **The accessor + region routing live here; the per-region BigQuery *dataset provisioning, schema, and SAR-E analytical query layer* are SAR-E's and are split to `SE-PRD-08`** (see boundary below).
- **Reconciliation residency** — the BL-PRD-02 reconciliation script (`api/scripts/reconcile_billing_meter.py`) reads usage per cell and writes its per-cell discrepancy rows to the matching regional client (so EU reconciliation artifacts stay EU-resident).
- **Docs** — append a "Telemetry & analytics residency" note to the Billing README pointing at this PRD; record the Shape-C-exception decision in [`../../../DESIGN-REVIEW-LOG.md`](../../../DESIGN-REVIEW-LOG.md).

### Out of scope

- **BigQuery per-region dataset provisioning + schema + the SAR-E analytical query layer** — owned by SAR-E, split to [`SE-PRD-08`](../../sar-e/projects/SE-PRD-08-sar-e-performance-residency.md). **Boundary:** this PRD makes the BigQuery *client* region-routable (the accessor + `CELLS`-keyed project/location selection for billing callers); SE-PRD-08 stands up the EU dataset, its tables/indexes, and every SAR-E query that reads it. The billing accessor is a no-op for EU until SE-PRD-08's EU dataset exists.
- **Defining the routing resolver / `Region` enum / `CELLS` map / `data_region` immutability** — owned by `DM-PRD-09`; imported, never redefined.
- **The BL-PRD-02 meter counters** (`organizations/{org_id}/usage_windows/*`, `accounts/{account_id}/usage_daily/*`) — those are **org/account-scoped Shape-B** docs already routed through the account's Firestore client once `DM-PRD-09` lands; their regionalization is a straight consequence of BL-PRD-02 writing through `get_firestore_for_account`, not new work here. This PRD covers the **Shape-C** telemetry stores (`usage_records`, `tool_usage_events`) + the BigQuery client, which BL-PRD-02 does not touch.
- **Migrating existing US-resident usage rows into the EU cell** — green-field per design-doc Q7; no backfill (consistent with BL-PRD-02 "meter starts at zero").
- **Generic cross-cell admin fan-out framework** — DR-PRD-10 / `DM-PRD-10`.
- **Trace/log content-capture residency** — DR-PRD-02 / `AH-PRD-12` (R-02, R-12).

## 3. Dependencies

| Dependency | What this PRD consumes | Reference |
|---|---|---|
| **[DM-PRD-09](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md)** (keystone) | `Region`, `CELLS`, `normalize_region`, `resolve_account_region(account_id)`, `get_firestore_for_account(account_id)`; the per-region client cache; `data_region` immutability + enum guarantee. | `shared/residency/regions.py`, `routing.py` |
| **[BL-PRD-02](./BL-PRD-02-token-meter-monthly-enforcement.md)** | The usage-write path this PRD regionalizes; `api/scripts/reconcile_billing_meter.py` (its per-cell read/write); the meter's org/account-scoped counters (rule out of scope, §2). | This component |
| Reference pattern | `api/src/kene_api/services/storage_service.py:31-72` — the `data_region → (resource, location)` map shape that DM-PRD-09 generalized and this PRD consumes. | — |
| **[SE-PRD-08](../../sar-e/projects/SE-PRD-08-sar-e-performance-residency.md)** (downstream sibling) | Provides the EU BigQuery dataset this PRD's regional client points at; until it lands, the EU branch of the BigQuery accessor has no dataset to read. Cross-references this PRD for the client-routing half. | `../../sar-e/projects/SE-PRD-08-sar-e-performance-residency.md` |
| Existing telemetry sites | `usage.py:23,129,192,258,300,438`; `app/adk/tracking/usage.py:135,159-175,181,251-276`; `bigquery.py:42,59-62,245-255`. | — |

## 4. Data contract

**No new collection, no path-shape change, no Pydantic-shape change.** The contract is "same documents, region-resident client."

### 4.1 `usage_records` (Shape-C carve-out — physical-region exception)

```
# Top-level, account_id-tagged — UNCHANGED logical shape (Shape C preserved)
usage_records/{record_id}
  account_id, user_id, timestamp, agent, model,
  prompt_tokens, response_tokens, total_tokens, ... total_cost
```

- **What changes:** the Firestore **client** the collection is read/written through is selected by `resolve_account_region(account_id)` instead of the global `firestore.Client()`. An EU account's rows live in the EU `(default)` database; US in US.
- **What does not change:** the collection name, document shape, the `account_id` field, or the within-cell org aggregation. The Shape-C carve-out (`../../data-management/README.md` §7.1) stands logically; this is a residency-driven physical-region exception, recorded in §9-Q1 and the design-review log.

### 4.2 `tool_usage_events` (Shape-C carve-out)

```
tool_usage_events/{event_id}
  account_id, user_id, tool_name, status, duration_ms,
  organization_id?, input_tokens?, output_tokens?, ...
```

- Each `UsageEvent` already carries `account_id` (`track_execution`, `app/adk/tracking/usage.py:181`); `_flush_batch` partitions the batch by `resolve_account_region(account_id)` and commits one Firestore batch per region.

### 4.3 BigQuery dataset selection

| Region | GCP project / location | Source |
|---|---|---|
| US | `CELLS[Region.US].gcp_project_id` / `.location` (`us-central1`) | `DM-PRD-09` `CELLS` map |
| EU | `CELLS[Region.EU].gcp_project_id` / `.location` (`europe-west1`) | `DM-PRD-09` `CELLS` map — **dataset provisioned by SE-PRD-08** |

The accessor returns a `bigquery.Client(project=CELLS[region].gcp_project_id, ...)`; the dataset/table names are SAR-E's contract (SE-PRD-08).

## 5. Implementation outline

| Action | File |
|---|---|
| Modify | `api/src/kene_api/routers/usage.py` — delete module-global `db` (`:23`); route `record_usage` write (`:258`) via `get_firestore_for_account(usage_record.account_id)`; route account/user reads (`:129`, `:192`) per-account; make `get_overall_usage` (`:300`) fan out across `Region` and merge |
| Modify | `app/adk/tracking/usage.py` — make `_flush_batch` (`:251-276`) group `self._batch` by `resolve_account_region(event.account_id)` and commit one batch per regional client; `get_usage_aggregation` reads fan out across cells |
| Modify | `api/src/kene_api/bigquery.py` — add `client_for_region(region: Region)` selecting project/location from `CELLS` (`:42`, `:59-62`); callers pass the account's region |
| Add (if absent in DM-PRD-09) | `shared/residency/routing.py` — `get_firestore_for_region(region: Region)` per-region-cached accessor for the cross-cell fan-out reads (reuse the DM-PRD-09 cache; do not add a second cache) |
| Modify | `api/scripts/reconcile_billing_meter.py` (BL-PRD-02) — read/write per cell; EU discrepancy rows to the EU client |
| Modify | [`../README.md`](../README.md) — "Telemetry & analytics residency" note linking this PRD |
| Modify | [`../../../DESIGN-REVIEW-LOG.md`](../../../DESIGN-REVIEW-LOG.md) — record the Shape-C physical-region exception |
| Create | `api/tests/unit/test_usage_residency_routing.py` |
| Create | `app/tests/.../test_tool_usage_residency.py` (colocated per ADK test layout) |
| Create | `api/tests/integration/test_usage_records_region_routing.py` |

**Straggler guard.** As with `DM-PRD-09` (its §9 risk), a stray `firestore.Client()` in the usage path silently stays US-only. The module-global `db` at `usage.py:23` is exactly that pattern — its removal is the core of this PRD. Add a grep-based review-checklist item for direct `firestore.Client()` / `bigquery.Client(` construction in the billing/usage paths.

## 6. API contract

No new public HTTP surface; existing endpoints keep their shapes and become region-correct.

| Contract | Behavior change | Source of truth |
|---|---|---|
| `POST /api/v1/usage/record` | Row persists to the **account's home-cell** Firestore, not the global client. Same request/response. | `api/src/kene_api/routers/usage.py` |
| `GET /api/v1/usage/user/{user_id}/costs`, `GET /api/v1/usage/account/{account_id}/costs` | Read from the resolved account's regional client. Same response. | `usage.py` |
| `GET /api/v1/usage/summary`, super-admin `get_overall_usage`, `GET /api/v1/usage/tool-usage` | Cross-cell: fan out across `Region`, merge, then aggregate. Super-admin only (unchanged auth). | `usage.py`, `app/adk/tracking/usage.py` |
| `client_for_region(region)` (BigQuery) | Internal accessor consumed by billing callers + SE-PRD-08. | `api/src/kene_api/bigquery.py` |

## 7. Acceptance criteria

1. `POST /usage/record` for an EU account writes the `usage_records/{id}` document to the **EU** Firestore client and **not** the US client (integration test asserts the doc exists in the EU emulator/project and is absent from US); a US account writes to US.
2. `get_account_costs` / `get_user_costs` for an EU account read from the EU client; the returned `summary` reflects only that account's region-resident rows.
3. `get_overall_usage` (super-admin) returns the **union** of US + EU usage rows — a test seeding one US and one EU `usage_records` row gets both in the aggregate and the per-account breakdown.
4. The module-global `db = firestore.Client()` is removed from `usage.py`; no account-scoped `usage_records` access constructs a client directly (grep-gate + unit assertion on call sites).
5. `UsageTracker._flush_batch` with a mixed-region batch (one US, one EU event) commits the US event to the US client and the EU event to the EU client (unit test with mocked per-region clients asserts each `batch.commit()` target).
6. `get_usage_aggregation` / `GET /usage/tool-usage` aggregates `tool_usage_events` across both cells.
7. `bigquery.client_for_region(Region.EU)` builds a client targeting `CELLS[Region.EU].gcp_project_id` / location; `Region.US` targets the US project. No call reads the ambient `GOOGLE_CLOUD_PROJECT_ID` for account-scoped analytics.
8. The reconciliation script writes EU discrepancy rows to the EU client and US to US (per-cell isolation verified).
9. No path-shape migration: `usage_records` and `tool_usage_events` remain top-level, `account_id`-tagged collections (Shape-C logical shape unchanged); the residency exception is recorded in `DESIGN-REVIEW-LOG.md`.
10. `make lint` passes. `pytest api/tests/unit/test_usage_residency_routing.py api/tests/integration/test_usage_records_region_routing.py` and the ADK `test_tool_usage_residency.py` pass.
11. `lychee --config lychee.toml .` passes for the touched docs.

## 8. Test plan

### Unit
- **Region selection** (`test_usage_residency_routing.py`): `record_usage` resolves the write client from `resolve_account_region(account_id)`; mocked resolver returning US vs EU yields the correct client (AC-1). Assert the global `db` is gone and call sites route through the resolver (AC-4).
- **Batch partition** (`test_tool_usage_residency.py`): `_flush_batch` over a mixed-region batch routes each event to the right per-region client; an all-US batch makes exactly one commit on the US client (AC-5).
- **BigQuery accessor**: `client_for_region` per region selects the right project/location from `CELLS` (mock `bigquery.Client`); no ambient-env fallback for account-scoped reads (AC-7).
- **Fan-out merge**: a pure merge helper over `{US: rows, EU: rows}` produces the correct union + per-account totals (AC-3, AC-6).

### Integration (Firestore emulator, two named databases standing in for the two cells; mocked Neo4j region source)
- EU `POST /usage/record` lands in the EU DB and is absent from US (AC-1); symmetric US case.
- `get_account_costs` for EU reads only EU rows (AC-2).
- `get_overall_usage` returns the US+EU union (AC-3).
- Reconciliation per-cell write isolation (AC-8).

### Manual verification (dev, operator-run; not gated in CI)
- Create an EU dev account; run a chat that records usage; confirm in the Firestore console the `usage_records` row is in the EU dev database, not US.
- Confirm `client_for_region(Region.EU)` is a no-op-safe (errors cleanly) until SE-PRD-08's EU dataset exists.

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| **Shape-C carve-out tension** — touching a "do not migrate, do not touch" collection (`../../data-management/README.md` §7.1) | We do **not** migrate the path shape; we only swap the physical client. Logical Shape-C (top-level, `account_id`-tagged, within-cell org aggregation) is preserved. Recorded as an explicit physical-region exception in `DESIGN-REVIEW-LOG.md` (AC-9). |
| Stray `firestore.Client()` / `bigquery.Client(` bypasses the resolver and silently stays US-only | The module-global `db` is the canonical instance and its removal is core scope; grep-gate review item (§5); AC-4 unit guard. |
| Cross-cell fan-out reads double per-cell latency / cost on super-admin endpoints | Fan-out is confined to the two super-admin/aggregation endpoints; per-account endpoints resolve a single cell. Generic fan-out framework deferred to DR-PRD-10. |
| ADK tracker resolving region per event adds Neo4j/directory reads on the hot flush path | `resolve_account_region` is directory-fast-path + request-scoped cacheable (DM-PRD-09 §4.4); batch is already async/periodic (`FLUSH_INTERVAL_SECONDS=30`), so resolution amortizes. Cache region per `account_id` within a flush. |
| EU BigQuery accessor points at a dataset SE-PRD-08 hasn't created yet | Accessor is inert/no-op for EU until SE-PRD-08 lands; this PRD ships the routing, SE-PRD-08 ships the dataset. Sequencing tracked in the Initiative. |

### Open questions
- **Q1 (decision needed):** ratify the **Shape-C physical-region exception** for `usage_records` / `tool_usage_events` — keep logical Shape C, regionalize the physical client. **Proposal:** yes (the carve-out's reason, cross-account org aggregation, is preserved *within* a cell; cross-cell aggregation is the super-admin fan-out). Record in `DESIGN-REVIEW-LOG.md`.
- **Q2:** does `get_firestore_for_region(region)` already exist from DM-PRD-09's fan-out needs, or is this PRD the first cross-cell reader? Confirm at kickoff to avoid a duplicate cache. (Carries design-doc Q5: org/region scope — if an org can hold accounts in both cells, the super-admin org rollups *must* fan out; this PRD already assumes they can.)
- **Q3:** exact `usage_records` doc-id scheme under two cells — current `{user_id}_{timestamp}_{rand}` (`usage.py:257`) is already collision-safe per cell; confirm no global-uniqueness assumption elsewhere depends on a single namespace.

## 10. Reference

- Program spec: [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) — §2 (D1, D3), §3.2 (per-region row), §3.4 (reference pattern), §4 (BigQuery posture), §5 (R-13, R-14), §7 (DR-PRD-06 row, multi-component homing).
- Keystone foundation: [`DM-PRD-09`](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md) — `Region` / `CELLS` / `resolve_account_region` / `get_firestore_for_account` (reused, not redefined).
- Sibling billing PRD: [`BL-PRD-02`](./BL-PRD-02-token-meter-monthly-enforcement.md) — owns the usage-write path + reconciliation script regionalized here.
- SAR-E sibling (BigQuery dataset half of R-14): [`SE-PRD-08`](../../sar-e/projects/SE-PRD-08-sar-e-performance-residency.md).
- Shape-C carve-out: [`../../data-management/README.md`](../../data-management/README.md) §7.1, §7.4; Regional Cell convention: §7.8.
- Reference implementation: `api/src/kene_api/services/storage_service.py:31-72`.
- Refactor targets: `api/src/kene_api/routers/usage.py:23,129,192,258,300,438`; `app/adk/tracking/usage.py:135,159-175,251-276`; `api/src/kene_api/bigquery.py:42,59-62,245-255`.
- CLAUDE.md rules in scope: PY-1, PY-2, PY-5, PY-7; D-2, D-3, D-5; T-1, T-3, T-4.
