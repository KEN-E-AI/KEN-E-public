# DP-PRD-07 — Data Pipeline Residency

**Status:** Ready to start
**Owner team:** [KEN-E] Data Pipeline
**Initiative:** Data Residency (US + EU)
**Blocked by:** DM-PRD-09 (Regional-Cell Foundation), DP-PRD-01 (Foundation)
**Blocks:** —
**Estimated effort:** 2–3 days (mostly *requirement-folding* into the in-flight DP set, not net-new code — see §1)

> **Program context.** This is one slice of the **Data Residency (US + EU)** program; it closes gap-register item **R-19**. The program is *not* a new component — each slice is a PRD homed in the component that owns the affected code, bound together by the [Data Residency (US + EU) Linear Initiative](https://linear.app/ken-e/initiative/data-residency-us-eu-e60f510ef09b) and the cross-component spec [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md). Read that doc's §1–§4 (esp. §2 locked decisions, §3.2 regional-cell table, §3.4 reference pattern), §5 (gap register — R-19), and §6.2 (phase 1) before this PRD. The **keystone is [`DM-PRD-09`](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md)** — this PRD **reuses its `Region` enum, `CELLS` config map, `resolve_account_region(account_id)`, and `get_firestore_for_account(account_id)` resolver** and does **not** redefine them.

---

## 1. Context

The Data Pipeline is KEN-E's deterministic, non-agentic path to third-party platform APIs ([`../README.md`](../README.md) §1): a sibling Cloud Run service `kene-data-pipeline-{env}` runs a connector against a platform recipe, writes the result as a `TaskArtifact`, persists a `DataPipelineRun`, and hands off to downstream tasks. SAR-E's daily KPI ingestion is the first production consumer.

The whole component is **pre-launch and PRD-only today** — there is no `services/data_pipeline/` tree, no `data_pipeline.py` routers, and no `deployment/terraform/data_pipeline*` files in the repo (verified 2026-05-29). The residency audit (R-19) flags this as a single high-severity gap whose fix site is [`DP-PRD-01-foundation.md:225`](./DP-PRD-01-foundation.md) — i.e. *the foundation has not been written yet*. Concretely the Data Pipeline is **not regionalized** along three axes:

1. **The sibling Cloud Run service** is scoped as a single `kene-data-pipeline-{env}` deploy ([`../README.md`](../README.md) §2.1; [DP-PRD-01 §5](./DP-PRD-01-foundation.md) `deployment/terraform/data_pipeline_service.tf`). The repo's Cloud Run region today defaults to `us-central1` (`deployment/terraform/variables.tf:33`), so a single service would process EU connector inputs/outputs in the US.
2. **Run records** live at `accounts/{account_id}/data_pipeline_runs/{run_id}` ([DP-PRD-01 §4.2, §5 Firestore layout](./DP-PRD-01-foundation.md)) — account-scoped Shape B, but with no region routing they land in the single global Firestore database flagged by **R-01**. The **global job catalog** `data_pipeline_jobs/{job_id}` is routing metadata, not regulated content.
3. **Extracted artifacts** are written through A-PRD-03's store to `gs://kene-task-artifacts-{env}/…` ([`../README.md`](../README.md) §2.2 step 5) — a single US bucket, the same class of leak as the chat-artifact bucket flagged by R-07.

**Key recommendation — fold, don't retrofit.** Because the component has not shipped, the cheapest and safest path is to **bake these residency requirements into the in-flight DP-PRD set (DP-PRD-01..04/06) before they ship**, rather than building US-only then retrofitting an EU cell. This PRD therefore documents the **residency requirement + acceptance criteria the DP set must meet**; the actual code lands inside those PRDs. The "effort" above is the requirement-folding + review-gate work, not a standalone implementation. See [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) §7 (the DR-PRD-08 row carries the note *"fold into DP-PRD before it ships"*) and §6.2 (R-19 is phase 1).

Per the locked decisions ([`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) §2): residency boundary is the account (D1); two regions at launch, US + EU (D2); each cell is a full stack including a regional Cloud Run service (D3); `data_region` is immutable after creation (D5), so a run's home cell never moves under it.

## 2. Scope

### In scope

- **Regional Cloud Run service per cell** — the sibling service deploys **once per region** (`kene-data-pipeline-{env}-us` in `us-central1`, `kene-data-pipeline-{env}-eu` in `europe-west1`), each in its region's GCP project per DM-PRD-09's project-per-region topology. The main-API `DataPipelineDispatcher` (DP-PRD-03) **resolves the target service URL by the account's region** via `resolve_account_region(account_id)` before it POSTs `/api/v1/internal/data-pipeline/run`.
- **Region-routed run records** — `DataPipelineRun` reads/writes go through DM-PRD-09's `get_firestore_for_account(account_id)` so `accounts/{account_id}/data_pipeline_runs/*` lands in the account's cell. Applies to the sibling service's run-persistence path (DP-PRD-01 `service.py`) **and** the main-API run-read endpoints (DP-PRD-01 `data_pipeline.py`) **and** the `/ingestion-status` aggregator (DP-PRD-01 §6.7).
- **Region-routed global catalog reads** — `data_pipeline_jobs/{job_id}` (global carve-out) + the per-account overlay `accounts/{account_id}/data_pipeline_jobs/*` resolve through the same convention: the **global** catalog is control-plane routing metadata (read via the control-plane client, acceptable per R-22), the **per-account overlay** is account-scoped and routes by `data_region`.
- **Regional extracted artifacts** — connector output is written to a **region-appropriate** artifact bucket. The Data Pipeline does not own the bucket (A-PRD-03 does), so this slice's requirement is: the artifact-store helper DP-PRD-03 calls MUST select the bucket by `data_region` (the GCS reference pattern, `storage_service.py:_get_bucket_config`). Coordinated with DR-PRD-05 (chat residency, R-07) which regionalizes the artifact buckets.
- **Region-correct credential + model paths (delegation, not implementation)** — connectors fetch credentials via Integrations' internal endpoint and never decrypt directly; KMS regionality is owned by DR-PRD-03 (IN-PRD-08). This PRD only requires that the per-region sibling service calls the **same-region** Integrations + downstream services (no cross-cell hop).
- **Folding the above into the DP set** — concretely amend DP-PRD-01 (Firestore + GCS client bootstrap, run persistence, `/ingestion-status` aggregator), DP-PRD-03 (dispatcher URL routing), and the Terraform tasks (DP-PRD-01 `data_pipeline_service.tf` → region × env iteration matching DM-PRD-09's module shape). Recorded here as acceptance criteria the DP set must satisfy (§7).

### Out of scope

- **Regionalizing any store the Data Pipeline does not own.** Firestore physical residency + the routing resolver (DM-PRD-09 / R-01); KMS + OAuth tokens (DR-PRD-03 / IN-PRD-08, R-05); model/Agent Engine reasoning (DR-PRD-01, R-03/R-04); the artifact *bucket definitions* themselves (DR-PRD-05, R-07); per-region BigQuery datasets for downstream SAR-E (DR-PRD-06 / SE, R-14). This slice **consumes** those; it does not build them.
- **Migrating existing pipeline data into the EU cell.** Green-field per open question Q7 ([`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) §8) — and moot here, since the component is pre-launch. Supervised region migration is DR-PRD-10.
- **Cross-cell admin / global run analytics fan-out** — DR-PRD-10 (R-21).
- **Connector implementations, the task-system dispatch branch, or the frontend** — those remain owned by DP-PRD-02/03/04/05; this PRD only adds the residency *constraint* each must honor.

## 3. Dependencies

- **DM-PRD-09 (Regional-Cell Foundation)** — hard prerequisite. Publishes `Region` / `CELLS` / `normalize_region` ([`DM-PRD-09 §4.1`](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md)), `resolve_account_region(account_id)` + `get_firestore_for_account(account_id)` ([`§4.4`](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md)), the project-per-region Terraform shape ([`§5`](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md)), and `data_region` immutability + enum validation. This PRD reuses all of them and reinvents none.
- **DP-PRD-01 (Foundation)** — the PRD whose service, run records, catalog collections, and `/ingestion-status` aggregator this slice regionalizes ([DP-PRD-01 §4.2, §5, §6.1, §6.7](./DP-PRD-01-foundation.md)). Because both are pre-launch, the cleanest sequencing is to **land DP-PRD-01 with the residency hooks already in** rather than as a follow-up PR.
- **DP-PRD-03 (Task-system integration)** — owns `DataPipelineDispatcher` ([`../README.md`](../README.md) §2.1), which gains the region-routed service-URL selection.
- **Integrations (IN-PRD-02)** — credential endpoint consumed per region; KMS regionality is DR-PRD-03 (IN-PRD-08, R-05).
- **Automations (A-PRD-03)** — owns the artifact store + bucket; the bucket regionalization itself is coordinated with DR-PRD-05 (R-07).
- **Reference pattern:** `api/src/kene_api/services/storage_service.py:31-72` (GCS `data_region` routing) — the canonical `get_<resource>(data_region)` shape DM-PRD-09 generalized and this PRD's Cloud Run + Firestore + GCS routing all mirror.
- **External / open:** EU Agent Engine GA (Q1) does **not** block this PRD (the Data Pipeline is non-agentic). The EU region choice (`europe-west1`, Q6) and project-per-region topology (Q3) are inherited from DM-PRD-09.

## 4. Data contract

No new persisted shapes. `DataPipelineJob`, `DataPipelineRun`, `PipelineJobSpec`, `PipelineOutput` are defined in [DP-PRD-01 §4](./DP-PRD-01-foundation.md) and are unchanged. This PRD adds **routing rules** over the existing shapes.

### 4.1 Residency routing table (per-store posture)

| Store / resource | DP-PRD-01 location | Residency posture | Routing key |
|---|---|---|---|
| Sibling Cloud Run service | `kene-data-pipeline-{env}` (single) | **per-region service** `…-{us,eu}` | `resolve_account_region(account_id)` → service URL |
| `data_pipeline_runs/{run_id}` | `accounts/{account_id}/data_pipeline_runs/*` (Shape B) | account-pinned regional Firestore | `get_firestore_for_account(account_id)` |
| Per-account job overlay | `accounts/{account_id}/data_pipeline_jobs/*` (Shape B) | account-pinned regional Firestore | `get_firestore_for_account(account_id)` |
| Global job catalog | `data_pipeline_jobs/{job_id}` (global carve-out) | control-plane routing metadata (R-22) | control-plane client (no regulated content) |
| Extracted artifacts | `gs://kene-task-artifacts-{env}/…` (A-PRD-03) | region-appropriate bucket | `data_region` → bucket (per `storage_service.py`) |

### 4.2 Cell invariant for runs

A `DataPipelineRun.account_id` resolves to exactly one region via `resolve_account_region`, and because `data_region` is immutable (DM-PRD-09 / D5), a run's home cell is fixed for its lifetime. The cache key `sha256(account_id || job_id || canonical_json(inputs) || job.version)` ([DP-PRD-01 §5](./DP-PRD-01-foundation.md)) already includes `account_id`, so cache lookups never cross cells — no extra cache-key change is needed; the cache simply lives in the account's regional Firestore.

## 5. Implementation outline

This is a **requirement-folding** PRD: each row names the DP-set file to amend and the residency change, rather than introducing a separate module. (All files below are *created* by the named DP PRD; this slice adds the residency behavior to that creation.)

| Action | File | Owning PRD | Residency change |
|---|---|---|---|
| Amend | `services/data_pipeline/src/kene_data_pipeline/main.py` | DP-PRD-01 | Bootstrap the Firestore + GCS clients via the region the service is deployed into; import `Region` / `CELLS` from the shared foundation rather than reading a bare project id |
| Amend | `services/data_pipeline/src/kene_data_pipeline/service.py` | DP-PRD-01 | Persist / read `DataPipelineRun` + overlay jobs via `get_firestore_for_account(account_id)`; global catalog via the control-plane client |
| Amend | `api/src/kene_api/routers/data_pipeline.py` | DP-PRD-01 | Run-read endpoints route Firestore by `resolve_account_region(account_id)` |
| Amend | `api/src/kene_api/services/data_pipeline_ingestion_aggregator.py` + `routers/internal/data_pipeline_ingestion_status.py` | DP-PRD-01 | `/ingestion-status` collection-group reads execute against the account's regional Firestore |
| Amend | `api/src/kene_api/services/data_pipeline_dispatcher.py` | DP-PRD-03 | Resolve the per-region sibling-service URL by `resolve_account_region(account_id)` before POSTing `/run` |
| Amend | `deployment/terraform/data_pipeline_service.tf` | DP-PRD-01 | Iterate the Cloud Run service over **regions × environments** (mirroring DM-PRD-09's module shape); one service per cell, each in its regional project with same-region IAM/SA |
| Coordinate | artifact-store bucket selection (A-PRD-03 helper) | DR-PRD-05 (R-07) | Connector output bucket selected by `data_region` per `storage_service.py:_get_bucket_config` |
| Create | `services/data_pipeline/tests/integration/test_residency_routing.py` | this PRD | Asserts an EU account's run lands in the EU Firestore + EU service URL; a US account in US (see §8) |

## 6. API contract

No new HTTP surface and **no change to any request/response shape** in [DP-PRD-01 §6](./DP-PRD-01-foundation.md) or [`../README.md`](../README.md) §2.3. The internal `POST /api/v1/internal/data-pipeline/run` contract is unchanged; what changes is the **base URL** the dispatcher selects (per-region service) and the **Firestore database** each handler binds (per-region client).

| Contract | Consumed by | Source of truth |
|---|---|---|
| Per-region sibling-service URL routing (`account_id → kene-data-pipeline-{env}-{us\|eu}`) | `DataPipelineDispatcher` (DP-PRD-03) | `data_pipeline_dispatcher.py` + `resolve_account_region` (DM-PRD-09) |
| Region-bound Firestore for run + overlay reads/writes | sibling `service.py`; main-API run/ingestion-status routers | `get_firestore_for_account` (DM-PRD-09) |
| Region-appropriate artifact bucket | connector output write path | `storage_service.py:_get_bucket_config` (reference) / DR-PRD-05 |

## 7. Acceptance criteria

These are the residency criteria the DP set must satisfy. They are phrased so DP-PRD-01/03/06 acceptance suites can absorb them directly.

1. **Single source of truth reused.** The sibling service and the main-API run paths import `Region`, `CELLS`, `resolve_account_region`, and `get_firestore_for_account` from DM-PRD-09's foundation module — no `firestore.Client(...)` / project-id literal is constructed for account-scoped reads/writes in any `data_pipeline` module (grep-gate, mirroring DM-PRD-09 AC-6).
2. **Per-region service deploy.** `deployment/terraform/data_pipeline_service.tf` applies cleanly producing `kene-data-pipeline-{env}-us` (in `us-central1`) and `kene-data-pipeline-{env}-eu` (in `europe-west1`), each in its regional GCP project; `gcloud run services list` shows both in dev (operator-verified, not gated in CI).
3. **Dispatcher routes by region.** `DataPipelineDispatcher`, given an EU account, POSTs `/api/v1/internal/data-pipeline/run` to the EU service URL; given a US account, to the US service URL (asserted with `resolve_account_region` stubbed per region).
4. **Run records land in-cell.** A run executed for an EU account writes `accounts/{account_id}/data_pipeline_runs/{run_id}` into the **EU** Firestore database and **never** the US database; symmetrically for US. Verified against two emulated regional Firestore targets.
5. **Catalog routing.** The per-account job overlay (`accounts/{account_id}/data_pipeline_jobs/*`) routes by region exactly like runs; the **global** `data_pipeline_jobs/*` catalog is read via the control-plane client only (no account-scoped read goes through it).
6. **Artifacts are region-resident.** Connector output for an EU account is written to the EU artifact bucket (the `europe-west1` bucket selected via `data_region`), not the US bucket — coordinated assertion with DR-PRD-05.
7. **Cache stays in-cell.** A cache hit for an EU account is served from the EU Firestore (the cache key already includes `account_id`); no cross-cell read occurs.
8. **`/ingestion-status` is in-cell.** The §6.7 aggregator's collection-group reads for an EU account execute against the EU Firestore and return the same `IngestionStatusResponse` shape as today.
9. **No cross-cell hop in execution.** The per-region sibling service calls the **same-region** Integrations credential endpoint and downstream services; an EU run makes no US-region network call carrying account content.
10. `make lint` passes; `pytest services/data_pipeline/tests/integration/test_residency_routing.py` passes; `lychee --config lychee.toml .` passes for this doc.

## 8. Test plan

### Unit / pure-logic

- **Service-URL resolver** — table-driven over `{US → us-service-url, EU → eu-service-url}`; unknown region rejected the same way `normalize_region` rejects it (reuse DM-PRD-09 behavior; no re-test of the resolver itself, only the URL map).

### Integration (`services/data_pipeline/tests/integration/test_residency_routing.py`, two emulated regional Firestore targets + stubbed `resolve_account_region`)

- EU account → run doc written to the EU emulator, absent from the US emulator (AC-4); US account → mirror (AC-4).
- EU account → dispatcher selects the EU service URL; US account → US URL (AC-3).
- Per-account overlay read for an EU account hits the EU Firestore; global catalog read goes through the control-plane client (AC-5).
- Cache-hit path for an EU account reads only the EU Firestore (AC-7).
- `/ingestion-status` for an EU account aggregates only EU runs and returns the unchanged response shape (AC-8).

### Coordinated (with DR-PRD-05)

- Connector output for an EU account is uploaded to the `europe-west1` artifact bucket (AC-6) — asserted where the artifact-store bucket selector lands.

### Operator-verified (not CI-gated)

- Terraform apply in dev shows both regional Cloud Run services (AC-2), matching DM-PRD-09 AC-7's operator-verified Firestore pattern.

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| Residency hooks bolted on **after** DP-PRD-01 ships US-only → an EU retrofit + data migration | **Fold the requirements into DP-PRD-01/03 before they ship** (this PRD's central recommendation). Component is pre-launch, so there is no data to migrate and no production service to recut. |
| A stray `firestore.Client(...)` / bare project id in a `data_pipeline` module silently pins runs to US | Centralize on `get_firestore_for_account`; grep-gate (AC-1), mirroring DM-PRD-09 AC-6. |
| Cross-cell hop: a US-deployed service serving an EU account (or vice-versa) | Dispatcher routes by `resolve_account_region` (AC-3); the service itself only ever talks to same-region peers (AC-9). |
| Artifact bucket ownership split across components (A-PRD-03 owns the bucket; this slice needs it regional) | Explicit coordination with DR-PRD-05 (R-07); AC-6 is a shared assertion, not a duplicated bucket definition. |
| SAR-E daily-ingestion automation spans regions if one org holds accounts in both cells | Inherits open question Q5 (org/region scope, [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) §8); resolution lives in DR-PRD-07 (PR-PRD-10, per-region schedulers). Does not block this slice. |

### Open questions (carry from program spec §8)

- **Q3 / Q6 — topology + EU region:** inherited from DM-PRD-09 (project-per-region, `europe-west1`). Decides the regional Cloud Run service's project + region. **Needed before the Terraform amend.**
- **Q5 — org/region scope:** if one org can hold accounts in both cells, SAR-E's daily-ingestion automation must dispatch per region (DR-PRD-07). Informs sequencing, not this PRD's contract.

## 10. Reference

- Program spec: [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) — §2 locked decisions (D1–D6), §3.2 regional-cell table, §3.4 reference pattern, §5 gap register (**R-19**), §6.2 (phase 1), §7 (DR-PRD-08 row — *"fold into DP-PRD before it ships"*).
- Keystone foundation: [`../../data-management/projects/DM-PRD-09-regional-cell-foundation.md`](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md) — `Region` / `CELLS` / `normalize_region` (§4.1), `resolve_account_region` + `get_firestore_for_account` (§4.4), project-per-region Terraform (§5). **Reused, not redefined.**
- Sibling foundation: [`./DP-PRD-01-foundation.md`](./DP-PRD-01-foundation.md) — sibling Cloud Run service + run records (§4.2, §5), `/ingestion-status` aggregator (§4.7, §6.7), internal run endpoint (§6.1). The gap register cites `DP-PRD-01-foundation.md:225` as R-19's fix site.
- Component README: [`../README.md`](../README.md) — §2 architecture (dispatcher, sibling service, artifact write), §2.3 API contracts.
- Reference implementation: `api/src/kene_api/services/storage_service.py:31-72` (GCS `data_region` routing — the canonical resolver shape).
- Current state confirming pre-launch: no `services/data_pipeline/` tree, no `api/src/kene_api/routers/data_pipeline.py`, no `deployment/terraform/data_pipeline*` (verified 2026-05-29); Cloud Run region default `deployment/terraform/variables.tf:33`.
- CLAUDE.md rules in scope: PY-1, PY-2, PY-5, PY-7; D-1, D-2, D-5; O-1, O-2; T-1, T-3, T-4.
