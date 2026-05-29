# PR-PRD-10 — Cross-Account Sweep Regionalization

**Status:** Ready to start
**Owner team:** [KEN-E] Projects & Tasks
**Initiative:** Data Residency (US + EU)
**Blocked by:** DM-PRD-09 (regional-cell foundation — `Region`/`CELLS`/`resolve_account_region`/`get_firestore_for_account`); PR-PRD-06 (time-based scheduler); A-PRD-02 (recurring scheduler & run engine)
**Blocks:** —
**Estimated effort:** 3–4 days
**Cut-line:** Phase 1 (post-launch hardening — see [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) §6.2)

> **Program context.** Part of the **Data Residency (US + EU)** program; this slice (logical `DR-PRD-07`) closes **R-09**. It reuses — and does **not** redefine — the routing substrate from the keystone [`DM-PRD-09`](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md): the `Region` enum, the `CELLS` config map, `resolve_account_region(account_id)`, and `get_firestore_for_account(account_id)`. Read [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) §2 (decisions), §3.3 (request flow), §5 (R-09), §6.2 (Phase 1), §8 Q5 before this PRD.
>
> **Cross-component split.** The scheduler/run-engine sweeps (PR-PRD-06, A-PRD-02, KG-PRD-04) are **project-tasks** work and owned here. The deletion fan-out (DM-PRD-05) and audit/chat side-table sweeps live in **data-management / chat** code; this PRD specifies the shared fan-out helper and the contract those sweeps must adopt, with that secondary team attached to the Linear project for visibility.

---

## 1. Context

KEN-E's residency model (D1, [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) §2) pins each account's entire data plane to one regional cell (US or EU). DM-PRD-09 splits Firestore into one `(default)` database per regional GCP project and routes account-scoped access through `get_firestore_for_account(account_id)`.

That split silently breaks every **cross-account collection-group sweep** — queries that today run a single `collection_group(...)` against the one global Firestore client to scan *across all accounts at once*. Once the EU cell exists, such a query bound to the US client returns **only US matches**: deletion, scheduling, and audit sweeps would **skip the EU cell entirely** (**R-09**, §5). The defect is silent — no error, just missing rows — which makes it a compliance and correctness hazard.

The affected production sweeps, with verified sites:

| Sweep | Site | Today | After split |
|---|---|---|---|
| Chat side-table session lookup | `api/src/kene_api/chat/side_table.py:219-224` (`find_session_for_user`) | `self._db.collection_group("chat_sessions")` on an injected client | misses EU sessions |
| Strategy audit user-activity | `api/src/kene_api/services/audit_service.py:262` (`get_user_activity`); module-global `db = firestore.Client()` at `audit_service.py:20` | `db.collection_group("strategy_audit")` on a region-blind global singleton | misses EU audit entries |
| User-deletion member sweep (DM-PRD-05) | `api/src/kene_api/services/user_deletion_service.py:126` (`db.collection_group("members")`); DM-PRD-05 §implementation `collection_group("members")` ([`../../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md`](../../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md) lines 150,154) | one global query | leaves EU `members` rows + EU account data un-deleted (GDPR) |
| Time-based scheduler tick (PR-PRD-06) | `find_and_fire_due_tasks` `collection_group("project_plans")` ([`./PR-PRD-06-time-based-scheduler.md`](./PR-PRD-06-time-based-scheduler.md) §5) | one global query | never fires EU tasks |
| Recurring automation tick (A-PRD-02) | `find_and_fire_due_automations` `collection_group("project_plans_*")` ([`../../automations/projects/A-PRD-02-recurring-scheduler.md`](../../automations/projects/A-PRD-02-recurring-scheduler.md) §5) | one global query | never fires EU automations |
| Session-end idle sweeper (KG-PRD-04) | `POST /api/v1/internal/scheduler/process-idle-sessions` idle-session scan ([`../../knowledge-graph/projects/KG-PRD-04-session-end-automation.md`](../../knowledge-graph/projects/KG-PRD-04-session-end-automation.md) §sweeper) | one global query | never reviews EU sessions |

PR-PRD-06 and A-PRD-02 are not yet built; this PRD ships **alongside** them so their scheduler ticks are regional from day one, and retrofits the three sweeps that already exist (`side_table.py`, `audit_service.py`, `user_deletion_service.py`).

The fix has two shapes, selected by the answer to **open Q5** (§9 — the lead question): if one organization can hold accounts in *both* cells, every sweep must **fan out per region**; if an org (and its scheduler/deletion domain) is region-pinned, the sweep can be **pinned to a single cell**. This PRD is written for the fan-out case (the safe default) and notes where the pinned case simplifies it.

## 2. Scope

### In scope

- **A shared region fan-out helper** — a small utility that, given a per-cell query builder, runs it against **every** `CELLS` entry's Firestore client and concatenates/merges the results. This is the single place that iterates the `CELLS` registry; every sweep calls it instead of `firestore.Client().collection_group(...)`.
- **Scheduler tick regionalization (PR-PRD-06)** — `find_and_fire_due_tasks` runs its `project_plans` collection-group query per cell; due tasks fire against the cell that owns them (the per-cell client is the one used for the idempotency transaction and the orchestrator hand-off).
- **Recurring automation tick regionalization (A-PRD-02)** — `find_and_fire_due_automations` runs its `project_plans` query per cell; the `PlanRun` create + `next_run_at` transaction execute on the owning cell's client.
- **Session-end idle sweeper regionalization (KG-PRD-04)** — the idle-session scan fans out per cell; each triggered `PlanRun` is created in its session's home cell.
- **Adoption contract for the data-management / chat sweeps** — `side_table.find_session_for_user`, `audit_service.get_user_activity`, and the DM-PRD-05 `members` deletion sweep switch from a region-blind client to the fan-out helper. (Implementation of the DM-PRD-05 sweep is owned by data-management; this PRD specifies the contract and provides the helper.)
- **`audit_service` global-client fix** — replace the module-level `db = firestore.Client()` (`audit_service.py:20`) so cross-account reads route through the helper; per-account writes (`log_strategy_action`, which already takes `account_id`) route through `get_firestore_for_account(account_id)`.
- **Convention note** — append a short "Cross-account sweeps fan out per region" subsection to the project-tasks README pointing at the helper, mirroring how DM-PRD-09 documents the routing convention.

### Out of scope

- **Defining `Region` / `CELLS` / `resolve_account_region` / `get_firestore_for_account`** — owned by DM-PRD-09; reused, never redefined.
- **Regionalizing any non-Firestore store** (Neo4j, KMS, model endpoint, Redis, BigQuery) — separate DR slices.
- **Single-account, account-scoped reads/writes** — those already take `account_id` and route via `get_firestore_for_account`; this PRD only touches **cross-account** collection-group sweeps.
- **The Cloud Scheduler / OIDC infrastructure** — owned by PR-PRD-06 (reused by A-PRD-02 and KG-PRD-04). This PRD does not add scheduler jobs; it changes the **query** inside the existing tick endpoints.
- **Supervised account region-migration + cross-cell global admin/analytics** — DM-PRD-10 (DR-PRD-10).
- **The R-10 Neo4j cross-account `account_id` hotfix** — standalone PR (design doc §6.4).

## 3. Dependencies

- **DM-PRD-09** complete — provides `Region`, `CELLS`, `resolve_account_region(account_id)`, `get_firestore_for_account(account_id)` in `shared/residency/`. **Hard prerequisite.**
- **PR-PRD-06** — the time-based scheduler tick whose `project_plans` query this PRD regionalizes. Ship together.
- **A-PRD-02** — the recurring automation tick (`project_plans` query + `PlanRun` create) this PRD regionalizes. Ship together.
- **KG-PRD-04** — the idle-session sweeper whose scan this PRD regionalizes (KG team coordinates).
- **DM-PRD-05** — the deletion sweep (`members` collection-group) that adopts the helper (data-management team owns the edit).
- Existing reference pattern: `api/src/kene_api/services/storage_service.py:31-72` (GCS `data_region` routing) — the per-store resolver shape DM-PRD-09 generalized and this PRD consumes.
- **Open:** Q5 (§9) — org/region scope. Drives whether the helper fans out (default) or pins. Should be answered at kickoff.

## 4. Data contract

This PRD adds **no new persisted fields and no new collections**. It changes *which Firestore database* a fixed set of queries run against. The only new artifact is an in-process helper contract.

### 4.1 Region fan-out helper (the single `CELLS`-iteration point)

```python
# shared/residency/sweeps.py  (new; lives next to DM-PRD-09's residency module)
from typing import Callable, TypeVar
from google.cloud import firestore
from .regions import CELLS, Region          # DM-PRD-09 — imported, not redefined
from .routing import get_firestore_for_region  # thin wrapper over DM-PRD-09's per-region client cache

T = TypeVar("T")

def fan_out_collection_group(
    build_query: Callable[[firestore.Client], firestore.Query],
) -> list[tuple[Region, firestore.DocumentSnapshot]]:
    """Run `build_query` against every regional cell's Firestore client and
    return (region, doc) pairs across all cells. The ONLY place that iterates
    the CELLS registry for a sweep. Per-cell client comes from DM-PRD-09's
    per-region cache (one client per Region, not per account)."""
    results: list[tuple[Region, firestore.DocumentSnapshot]] = []
    for region in CELLS:
        client = get_firestore_for_region(region)
        for doc in build_query(client).stream():
            results.append((region, doc))
    return results
```

- **`get_firestore_for_region(region)`** is a thin sibling to DM-PRD-09's `get_firestore_for_account(account_id)` — both return the same per-region-cached client; the account variant resolves the region first, this one takes it directly. If DM-PRD-09 has not exposed it, add it to `routing.py` as a one-liner (coordinate with the DM-PRD-09 owner). **Do not** construct `firestore.Client()` here.
- For a **mutating** sweep (scheduler fire, automation `PlanRun` create, deletion), the caller carries the `region` from the returned pair so the follow-up transaction/write targets the **same** cell's client — never the global one.
- **Pinned-org variant (if Q5 = region-pinned):** the helper still exists, but scheduler/deletion callers that operate within one org resolve that org's region once (`resolve_account_region(account_id)`) and run a single-cell query — `fan_out_collection_group` is reserved for genuinely user-global sweeps (e.g. `audit_service.get_user_activity`, `side_table.find_session_for_user`, DM-PRD-05 user deletion) that span a user's accounts across cells.

### 4.2 Result-ordering caveat

Fan-out concatenates per-cell results, so a global `order_by(...).limit(N)` is **not** preserved across cells. Sweeps that depend on global ordering (e.g. `audit_service.get_user_activity`'s `order_by("timestamp" DESC).limit(limit)`) must re-sort and re-limit the merged result in Python after fan-out. Sweeps that are exhaustive (deletion, scheduler "all due") are order-independent and need no re-sort.

## 5. Implementation outline

| Action | File | Owner |
|---|---|---|
| Create | `shared/residency/sweeps.py` — `fan_out_collection_group`; (add `get_firestore_for_region` to `routing.py` if absent) | project-tasks |
| Modify | `api/src/kene_api/services/task_scheduler.py` (PR-PRD-06) — `find_and_fire_due_tasks` fans out the `project_plans` query; fire transaction + orchestrator hand-off use the owning cell's client | project-tasks |
| Modify | `api/src/kene_api/services/automation_run_engine.py` (A-PRD-02) — `find_and_fire_due_automations` fans out; `PlanRun` create + `next_run_at` transaction on the owning cell | project-tasks |
| Modify | `api/src/kene_api/routers/internal/session_sweeper.py` (KG-PRD-04) — idle-session scan fans out; per-session `PlanRun` created in its home cell | KG (coordinated) |
| Modify | `api/src/kene_api/chat/side_table.py:219-224` — `find_session_for_user` uses the fan-out helper instead of `self._db.collection_group(...)`; merge to first non-tombstoned match | chat (coordinated) |
| Modify | `api/src/kene_api/services/audit_service.py` — remove module-global `db` (line 20) as the cross-account path; `get_user_activity` (line 262) fans out + re-sorts/re-limits in Python; per-account helpers route via `get_firestore_for_account(account_id)` | data-management (coordinated) |
| Modify | `api/src/kene_api/services/user_deletion_service.py:126` — `members` collection-group sweep fans out across cells; per-account deletes target the owning cell (DM-PRD-05) | data-management |
| Modify | [`../README.md`](../README.md) — add "Cross-account sweeps fan out per region" note pointing at `residency/sweeps.py` | project-tasks |
| Create | `api/tests/unit/test_residency_sweeps.py` | project-tasks |
| Create | `api/tests/integration/test_scheduler_fanout.py` | project-tasks |

### Core change — pattern applied to every sweep

```
BEFORE:  for doc in db.collection_group("X").where(...).stream(): handle(doc)

AFTER:   for region, doc in fan_out_collection_group(
             lambda c: c.collection_group("X").where(...)
         ):
             handle(doc, region)   # mutations re-use get_firestore_for_region(region)
```

For mutating ticks, the idempotency transaction (PR-PRD-06 §5 `launched_at`; A-PRD-02 §5 `next_run_at`) runs on `get_firestore_for_region(region)` — preserving the single-fire guarantee **within** each cell.

## 6. API contract

No new public HTTP surface and no changed request/response shapes. The internal scheduler endpoints (`POST /api/v1/internal/scheduler/launch-due-tasks`, `.../launch-due-automations`, `.../process-idle-sessions`) keep their PR-PRD-06 / A-PRD-02 / KG-PRD-04 contracts; their response `tasks_fired` / `automations_fired` / `sessions_triggered` arrays now include matches from **all** cells.

| Contract | Consumed by | Source of truth |
|---|---|---|
| `fan_out_collection_group(build_query)` — runs a collection-group query against every `CELLS` cell, returns `(region, doc)` pairs | every cross-account sweep (scheduler, automations, session-end, audit, chat lookup, deletion) | `shared/residency/sweeps.py` |
| Scheduler / automation / sweeper ticks return matches across all cells | Cloud Scheduler (unchanged trigger) | the three internal endpoints |

## 7. Acceptance criteria

1. `fan_out_collection_group` invokes `build_query` exactly once per `CELLS` entry, each time with that cell's Firestore client, and returns `(region, doc)` pairs from every cell (asserted with a two-cell `CELLS` fixture).
2. `fan_out_collection_group` constructs **no** `firestore.Client()` of its own — it obtains clients only from the DM-PRD-09 per-region cache (`get_firestore_for_region`), verified by a unit guard + a grep-gate in review.
3. The time-based scheduler tick fires a due task that lives in the **EU** cell as well as one in the US cell; each task's `launched_at` idempotency transaction runs on its own cell's client (no cross-cell write).
4. The recurring automation tick creates a `PlanRun` for an EU-cell automation, and the `next_run_at` transaction + `PlanRun` doc land in the **EU** cell, not the US cell.
5. The session-end idle sweeper triggers a `PlanRun` for an idle session in the EU cell.
6. `side_table.find_session_for_user` returns a session that lives in the EU cell when the request carries only `(user_id, session_id)`; tombstoned rows are still excluded.
7. `audit_service.get_user_activity` returns entries from **both** cells, merged, re-sorted by `timestamp` DESC, and re-limited to `limit` (global ordering preserved across cells per §4.2).
8. The DM-PRD-05 user-deletion sweep deletes `members` rows and account-scoped data in **both** cells for a user whose accounts span US and EU (no EU residue).
9. A two-cell sweep where one cell returns zero matches still succeeds and returns the other cell's matches (empty cell is a no-op, not an error).
10. `make lint` passes. `pytest api/tests/unit/test_residency_sweeps.py api/tests/integration/test_scheduler_fanout.py` passes.
11. `lychee --config lychee.toml .` passes for the touched docs.

## 8. Test plan

### Unit (`test_residency_sweeps.py`)

- `fan_out_collection_group` over a mocked two-entry `CELLS` calls the builder once per cell with the right client and concatenates results (AC-1).
- No-client-construction guard: patch `firestore.Client` to raise; the helper still works using injected per-region clients (AC-2).
- Empty-cell merge: one cell returns `[]`, the other returns rows → merged list is the non-empty cell's rows (AC-9).
- Re-sort/re-limit helper for `get_user_activity`: merged unsorted rows from two cells → sorted DESC, truncated to `limit` (AC-7).

### Integration (`test_scheduler_fanout.py`, Firestore emulator — one namespace per simulated cell, mocked orchestrator)

- Seed one due `Approved` task in each cell → tick fires **both**; each `launched_at` is set in its own cell (AC-3).
- Seed one due automation in the EU cell → `PlanRun` + updated `next_run_at` exist in the EU namespace only (AC-4).
- Idempotency under fan-out: two concurrent ticks fire each cross-cell task exactly once (per-cell transaction still holds).
- `find_session_for_user` for an EU-cell session returns it; a tombstoned EU row returns `None` (AC-6).
- User-deletion sweep across a US+EU user removes `members` + account data in both cells; a follow-up fan-out query returns zero rows (AC-8).

> Per CLAUDE.md T-4, the pure fan-out/merge logic is unit-tested; the DB-touching sweep behavior is integration-tested against the emulator.

## 9. Risks & open questions

### Lead open question

- **Q5 (gating — design doc §8): can ONE organization hold accounts in BOTH cells?** This answer drives the entire PRD. **If yes** → every cross-account sweep must fan out per region (the default this PRD assumes), because a single org's scheduler/deletion/audit domain straddles cells. **If an org is region-pinned** → org-scoped sweeps (scheduler tick per org, org deletion) simplify to a single `resolve_account_region`-selected cell, and only genuinely user-global sweeps (user deletion, cross-account audit, session lookup) need the full fan-out. **The helper is written so either answer is a one-line caller change** (fan-out vs. pinned single-cell), but the answer must be confirmed at kickoff so callers pick the right mode. Until answered, default to fan-out (safe: never skips a cell).

### Risks

| Risk | Mitigation |
|---|---|
| A stray cross-account `collection_group(...)` on a region-blind client is missed and silently skips EU | Centralize on `fan_out_collection_group`; AC-2 unit guard + a `grep`-based review item for `collection_group(` outside `residency/sweeps.py`. A straggler audit is the Phase-1 closeout check, mirroring DM-PRD-09's straggler risk. |
| Fan-out breaks a global `order_by().limit()` (returns wrong "top N" across cells) | §4.2: order-dependent sweeps re-sort + re-limit in Python after merge (AC-7). Exhaustive sweeps are order-independent. |
| Fan-out N× latency / cost as more cells are added | Two cells at launch; queries are indexed (same composite indexes per cell, DM-PRD-09). If cell count grows, parallelize the per-cell queries — out of scope now. |
| A mutating sweep fires/writes against the wrong cell's client | The `(region, doc)` pair carries the owning region; the follow-up transaction uses `get_firestore_for_region(region)`. AC-3/AC-4 assert per-cell writes. |
| `audit_service` module-global `db` (line 20) reused elsewhere as a region-blind client | This PRD removes it as the **cross-account** path; per-account callers route via `get_firestore_for_account(account_id)`. Grep all `audit_service.db` references during the edit. |
| Ownership confusion across components | §1 split table + the per-file owner column in §5; DM-PRD-05 / KG-PRD-04 / chat edits are coordinated with their teams (attached to the Linear project). |

## 10. Reference

- Program spec: [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) — §2 (decisions D1), §3.3 (request flow), §5 (R-09), §6.2 (Phase 1), §8 Q5, §7 (DR-PRD-07 row).
- Keystone foundation (reuse, do not redefine): [`../../data-management/projects/DM-PRD-09-regional-cell-foundation.md`](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md) — `Region`, `CELLS`, `resolve_account_region`, `get_firestore_for_account`.
- Sibling sweeps regionalized: [`./PR-PRD-06-time-based-scheduler.md`](./PR-PRD-06-time-based-scheduler.md) (§5 `find_and_fire_due_tasks`), [`../../automations/projects/A-PRD-02-recurring-scheduler.md`](../../automations/projects/A-PRD-02-recurring-scheduler.md) (§5 `find_and_fire_due_automations`), [`../../knowledge-graph/projects/KG-PRD-04-session-end-automation.md`](../../knowledge-graph/projects/KG-PRD-04-session-end-automation.md) (idle sweeper), [`../../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md`](../../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md) (`members` sweep).
- Reference implementation: `api/src/kene_api/services/storage_service.py:31-72` (GCS `data_region` routing — the per-store resolver shape).
- Verified sweep sites: `api/src/kene_api/chat/side_table.py:219-224`, `api/src/kene_api/services/audit_service.py:20,262`, `api/src/kene_api/services/user_deletion_service.py:126`.
- CLAUDE.md rules in scope: PY-1, PY-3, PY-7; D-1, D-3, D-5; T-1, T-3, T-4, T-6.
