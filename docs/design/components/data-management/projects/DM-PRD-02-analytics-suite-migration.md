# DM-PRD-02 — Analytics Suite Migration

**Status:** Complete
**Owner team:** Agent Platform / Analytics
**Blocked by:** DM-PRD-00
**Parallel with:** DM-PRD-01, DM-PRD-03, DM-PRD-04
**Blocks:** DM-PRD-05
**Estimated effort:** 2–3 days

---

## 1. Context

Migrate three Shape A analytics collections (all living in `app/adk/agents/strategy_agent/`) to Shape B subcollections:

- `agent_analytics_{account_id}` → `accounts/{account_id}/agent_analytics/{metric_id}` (unbounded)
- `cost_aggregations_{account_id}` → `accounts/{account_id}/cost_aggregations/{agg_id}` (unbounded)
- `performance_profiles_{account_id}` → `accounts/{account_id}/performance_profiles/{profile_id}` (unbounded)

> **Resolved 2026-05-07 (DM-30 PO verification):** Earlier drafts of this PRD called out a "naming inconsistency" between `performance_profiles_{account_id}` and a `performance_profiles_acc_{account_id}` variant, citing `RUNTIME_WARNINGS_ERRORS.md:230`. PO verification found this claim unsupported: account_ids in the codebase are uniformly `acc_<uuid>` (per `api/src/kene_api/routers/accounts.py:72,87`), the only production write site is `f"performance_profiles_{self.account_id}"` (`performance_profiler.py:240,320`), and no double-prefix `performance_profiles_acc_acc_*` collections exist in dev/staging/prod. The runtime-warnings doc was filling a literal collection name into a `{account_id}` template — there is one source-collection naming pattern, not two. The default `removeprefix("performance_profiles_")` correctly returns `acc_<hex>` (the canonical account_id); no custom `account_id_extractor` is needed.

This project is independent of DM-PRD-01 — no shared files — so it can run fully in parallel.

## 2. Scope

### In scope
- Register three entries in `api/scripts/_migrate_shape_b/resources.py`: `agent_analytics`, `cost_aggregations`, `performance_profiles`
- Run migration in dev; verify counts; delete legacy collections
- Swap all read + write call sites to Shape B paths
- Update unit and integration tests
- Ensure `optimization_recommendations` (global collection, unrelated) is unchanged

### Out of scope
- `optimization_recommendations` — global, not account-scoped; unchanged
- Any changes to the analytics-ingestion pipeline (just path updates)
- Strategy collections (DM-PRD-01), Shape D (DM-PRD-03), Shape B-like (DM-PRD-04), deletion sweep (DM-PRD-05)

## 3. Dependencies

- **DM-PRD-00:** `migrate_to_shape_b.py` merged
- Existing files to study:
  - `app/adk/agents/strategy_agent/analytics_service.py`
  - `app/adk/agents/strategy_agent/async_analytics_queue.py`
  - `app/adk/agents/strategy_agent/optimization_analyzer.py`
  - `app/adk/agents/strategy_agent/performance_profiler.py`

## 4. Call-site inventory

From [`../multi-tenant-migration-plan.md`](../multi-tenant-migration-plan.md) §3.1 + §3.5:

| File | Lines | Change |
|---|---|---|
| `app/adk/agents/strategy_agent/analytics_service.py` | 143, 211, 239, 383 | `agent_analytics_{self.account_id}` → `accounts/{self.account_id}/agent_analytics` |
| `app/adk/agents/strategy_agent/analytics_service.py` | 281, 342 | `cost_aggregations_{self.account_id}` → `accounts/{self.account_id}/cost_aggregations` |
| `app/adk/agents/strategy_agent/async_analytics_queue.py` | 170 | `agent_analytics_{account_id}` path update |
| `app/adk/agents/strategy_agent/optimization_analyzer.py` | 200 | `agent_analytics_{self.account_id}` path update |
| `app/adk/agents/strategy_agent/performance_profiler.py` | 240, 320 | `performance_profiles_{self.account_id}` path update |
| `app/adk/agents/strategy_agent/RUNTIME_WARNINGS_ERRORS.md` | 230 | Doc update — replace the imprecise `performance_profiles_acc_{account_id}` template with the new Shape B path |

## 5. Implementation outline

### Phase 1 — Register resources

Add to `api/scripts/_migrate_shape_b/resources.py`:

```python
RESOURCES["agent_analytics"] = MigrateConfig(
    old_prefix="agent_analytics_",
    new_subcollection="agent_analytics",
    has_versions=False,
)
RESOURCES["cost_aggregations"] = MigrateConfig(
    old_prefix="cost_aggregations_",
    new_subcollection="cost_aggregations",
    has_versions=False,
)
RESOURCES["performance_profiles"] = MigrateConfig(
    old_prefix="performance_profiles_",
    new_subcollection="performance_profiles",
    has_versions=False,
)
```

### Phase 2 — Code migration

Order: `cost_aggregations` (2 sites) → `agent_analytics` (4 sites) → `performance_profiles` (2 sites, plus the `RUNTIME_WARNINGS_ERRORS.md` doc update). Commit per resource. (The earlier "naming-inconsistency resolution" framing was retracted — see §1 Context — there is one source-collection pattern; the default `removeprefix` extractor is correct.)

### Phase 3 — Data migration (dev)

```bash
python api/scripts/migrate_to_shape_b.py --resource=cost_aggregations
python api/scripts/migrate_to_shape_b.py --resource=cost_aggregations --confirm-delete

python api/scripts/migrate_to_shape_b.py --resource=agent_analytics
python api/scripts/migrate_to_shape_b.py --resource=agent_analytics --confirm-delete

python api/scripts/migrate_to_shape_b.py --resource=performance_profiles --dry-run
python api/scripts/migrate_to_shape_b.py --resource=performance_profiles
python api/scripts/migrate_to_shape_b.py --resource=performance_profiles --confirm-delete
```

### Phase 4 — Verification

- Agents write metrics → data lands at `accounts/{id}/agent_analytics/*` (verify via Firestore console after an agent run)
- Cost aggregation run → data lands at `accounts/{id}/cost_aggregations/*`
- Performance profiler output → `accounts/{id}/performance_profiles/*`

## 6. Acceptance criteria

1. All call sites in §4 use `accounts/{account_id}/{agent_analytics,cost_aggregations,performance_profiles}/` paths. `rg -n "(agent_analytics|cost_aggregations|performance_profiles)_" app/` returns zero hits in source files (fixtures/tests excluded per repo convention).
2. In dev Firestore, no top-level collections matching `agent_analytics_*`, `cost_aggregations_*`, or `performance_profiles_*` exist.
3. A live agent run writes analytics metrics to `accounts/{id}/agent_analytics/{metric_id}` (verified via Firestore console).
4. Running `async_analytics_queue` flushes events to `accounts/{id}/agent_analytics/` with no lost events vs. pre-migration baseline.
5. `optimization_analyzer.py` reads analytics correctly and returns a non-empty recommendation set for a seeded account with ≥ 7 days of analytics.
6. `performance_profiler` writes land at `accounts/{id}/performance_profiles/`.
7. `RUNTIME_WARNINGS_ERRORS.md:230` reflects the new path.
8. `pytest app/adk/agents/strategy_agent/tests/` passes. `make lint` clean.

## 7. Test plan

### Unit tests (update existing)
- `app/adk/agents/strategy_agent/tests/test_analytics_service.py` (or equivalent) — fixture paths updated
- Performance profiler tests updated

### Integration tests
- Spin up analytics write → read → aggregate flow against emulator; confirm all writes hit new paths

### Manual verification (in dev)
- Kick off an agent run; watch Firestore console for new docs at `accounts/{id}/agent_analytics/`
- Run `optimization_analyzer` for a seeded account; confirm non-empty output

## 8. Risks & open questions

| Risk | Mitigation |
|---|---|
| `performance_profiles` source-collection naming | **Resolved 2026-05-07 (DM-30 PO verification):** there is exactly one source pattern, `performance_profiles_acc_<hex>`; the default `removeprefix("performance_profiles_")` correctly returns the canonical `acc_<hex>` account_id; no custom `account_id_extractor` is needed. (Earlier drafts proposed a `_performance_profiles_extractor` for a hypothetical second variant — that premise was unsupported.) See §1 Context. DM-34's emulator integration test pins the production `RESOURCES["performance_profiles"]` config as a regression guard. |
| Analytics write volume saturates migration script | These collections can be large per account. Script batches at 500 writes/sec. Plan for a longer-running migration on this resource; can split by account batch if needed (see open question) |
| Stale analytics cached in Redis (if any) | Check `api/src/kene_api/redis_client.py` for analytics cache keys; invalidate as part of cutover |

### Open questions

- **Q:** Can analytics volume exceed what the one-shot migration script handles comfortably? → **Profile during dry-run.** If any single account's analytics count exceeds ~100k docs, split migration by account batch (manual scripting, or a follow-up enhancement to `migrate_to_shape_b.py --account=<id>`). Report findings at Phase 3 start.

## 9. Reference

- Parent plan: [`../multi-tenant-migration-plan.md`](../multi-tenant-migration-plan.md) §3.1, §3.5
- Upstream: [DM-PRD-00](./DM-PRD-00-migration-foundation.md)
- Downstream: [DM-PRD-05](./DM-PRD-05-deletion-sweep-rewrite.md)
- Decision: [Review 15 in DESIGN-REVIEW-LOG](../../../DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1) — Multi-Tenant Data Model Shape
- `RUNTIME_WARNINGS_ERRORS.md` callout updated by DM-33: `app/adk/agents/strategy_agent/RUNTIME_WARNINGS_ERRORS.md` §7 (bottlenecks-query path moved to Shape B; the composite index is still pending DM-40)
- CLAUDE.md rules in scope: PY-1, PY-2, PY-7; T-1, T-3, T-4, T-6
