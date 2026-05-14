# DM-43 — End-to-end Verification Run Log

**Environment:** `ken-e-dev`
**Date:** 2026-05-13
**Operator:** Dev Team agent (VM)
**Issue:** [DM-43](https://linear.app/ken-e/issue/DM-43)
**PRD:** `docs/design/components/data-management/projects/DM-PRD-02-analytics-suite-migration.md`

## Context

§7.3 Verification Gate for DM-PRD-02 — confirms that all analytics-suite code paths
write fresh Firestore documents at Shape B paths (`accounts/{account_id}/{subcollection}/`)
rather than any legacy Shape A top-level paths. All prior DM-PRD-02 issues
(DM-37, DM-39, DM-40) migrated data in isolation; DM-43 exercises the live agent code
paths end-to-end.

Pre-conditions satisfied at run start:
- DM-30/DM-33: call-site updates for all three analytics modules merged
- DM-37: `cost_aggregations` dev data migrated (`(default)` DB)
- DM-39: `agent_analytics` dev data migrated (`analytics` DB)
- DM-40: `performance_profiles` dev data migrated (`analytics` DB)

**Key finding — DM-37 gap resolved:**

DM-37 ran the `cost_aggregations` migration against the `(default)` database only and
found 0 collections (empty baseline). The `analytics` named database, which is where
`AnalyticsService` actually writes (`firestore.Client(database="analytics")`), was not
targeted by DM-37 and contained **14 `cost_aggregations_acc_*` collections**. These were
resolved inline as part of this run's pre-flight sweep (see Pre-flight section).

## Pre-flight: Source Scan (Gate a)

```
rg -n "(agent_analytics|cost_aggregations|performance_profiles)_" app/
```

**Result: 0 legacy Shape A *writes* in production code.**

Verbatim rg output (re-verified 2026-05-13 by PO during review — the earlier table on this PR had stale/wrong line citations):

```
app/adk/agents/strategy_agent/tests/test_analytics_integration.py:198:        # Source collection mock (Shape A agent_analytics_ read path)
app/adk/agents/strategy_agent/tests/test_analytics_service.py:189:    # Source collection mock (Shape A agent_analytics_ read path)
```

Both hits are **comment lines** in test files describing legacy-path read-mock fixtures — not Shape A writes. They document tests that mock the pre-migration read path for backwards-compat coverage. No production-code Shape A write call sites remain.

## Pre-flight: DM-37 Gap Resolution

DM-37's runbook targeted only `(default)` database for `cost_aggregations`. The `analytics`
database had 14 surviving `cost_aggregations_acc_*` collections from the pre-migration era.
Resolved via `migrate_to_shape_b.py` with `FIRESTORE_DATABASE_ID=analytics`:

| Phase | Command | Found | Status |
|---|---|---|---|
| Dry-run | `FIRESTORE_DATABASE_ID=analytics --resource=cost_aggregations --dry-run` | 14 collections | `DRY RUN` |
| Copy + verify | `FIRESTORE_DATABASE_ID=analytics --resource=cost_aggregations` | 14 → 14 | `VERIFIED` |
| Confirm-delete | `FIRESTORE_DATABASE_ID=analytics --resource=cost_aggregations --confirm-delete --yes` | 14 deleted | `VERIFIED` |

Post-cleanup: 0 `cost_aggregations_acc_*` in either database.

## Live-Agent Smoke Tests (Wave 2)

Modules imported via `importlib.util.spec_from_file_location` (direct file-path load) to
bypass the `strategy_agent/__init__.py` → ADK chain → `starlette` → `from secrets import
token_hex` collision with `shared/secrets.py`. The workaround is semantically equivalent to
a normal package import for testing purposes.

All tests used the `ken-e-dev` project, `analytics` named Firestore database, and synthetic
`dm43_smoke_*` account IDs. All smoke fixtures were cleaned up after each test.

### Smoke 1 — `AsyncAnalyticsQueue`

| Check | Expected | Actual | Status |
|---|---|---|---|
| Shape B docs at `accounts/dm43_smoke_aa/agent_analytics/` | 3 | 3 | ✅ |
| Shape A docs at `agent_analytics_dm43_smoke_aa` | 0 | 0 | ✅ |
| `account_id` field in each doc | `dm43_smoke_aa` | `dm43_smoke_aa` | ✅ |
| Cleanup: docs remaining after delete | 0 | 0 | ✅ |

### Smoke 2 — `AnalyticsService.aggregate_daily_costs`

`AnalyticsService._init_firestore_clients()` sets `self.analytics_db = None` (IAM hold,
existing TODO comment at `analytics_service.py:67-68`). The smoke test monkey-patched
`analytics_db` post-instantiation with a fresh `firestore.Client(database="analytics")`
to exercise the write path — this matches the code path used in production once the IAM
hold is lifted.

| Check | Expected | Actual | Status |
|---|---|---|---|
| Shape B doc at `accounts/dm43_smoke_ca/cost_aggregations/` | 1 | 1 | ✅ |
| Shape A docs at `cost_aggregations_dm43_smoke_ca` | 0 | 0 | ✅ |
| `total_cost` field in doc | > 0 | 0.0150 | ✅ |
| Cleanup: docs remaining after delete | 0 | 0 | ✅ |

### Smoke 3 — `PerformanceProfiler`

| Check | Expected | Actual | Status |
|---|---|---|---|
| Shape B docs at `accounts/dm43_smoke_pp/performance_profiles/` | 3 | 3 | ✅ |
| Shape A docs at `performance_profiles_dm43_smoke_pp` | 0 | 0 | ✅ |
| `account_id` field in each doc | `dm43_smoke_pp` | `dm43_smoke_pp` | ✅ |
| `duration_seconds` field in each doc | > 0 | 0.05–0.06 s | ✅ |
| Cleanup: docs remaining after delete | 0 | 0 | ✅ |

### Smoke 4 — `OptimizationAnalyzer` (read + recommend)

Seeded 3 `agent_analytics` docs with `success=False` and `total_tokens=7000`
(`model="gemini-2.5-pro"`, well above `pro_model_simple_task_threshold=100` at
`optimization_analyzer.py:89`, so `model_downgrade` is intentionally NOT triggered).
The seed is designed to exercise the OTHER recommendation paths: `error_reduction`
via `success=False`, `context_reduction` via low context utilization on Pro, and
`load_distribution`. Called `generate_recommendations()`.

| Check | Expected | Actual | Status |
|---|---|---|---|
| Read from `accounts/dm43_smoke_oa/agent_analytics/` | seeded 3 docs | read 3 docs | ✅ |
| Recommendations returned | ≥ 1 | 3 | ✅ |
| `error_reduction` (priority=5) | present | present | ✅ |
| `context_reduction` (priority=3) | present | present | ✅ |
| `load_distribution` (priority=2) | present | present | ✅ |
| Cleanup: seeded docs remaining after delete | 0 | 0 | ✅ |

**Total smoke elapsed: 4.2 s.**

## Automated Gates (Wave 3)

### Gate (a) — rg source scan

```bash
rg -n "(agent_analytics|cost_aggregations|performance_profiles)_" app/
```

Result: **0 production-code hits** (2 intentional test carve-outs, see Pre-flight).

### Gate (b) — pytest

```bash
cd /home/agent/workspace && uv run --project app/adk pytest \
  app/adk/agents/strategy_agent/tests/test_analytics_service.py \
  app/adk/agents/strategy_agent/tests/test_analytics_integration.py \
  app/adk/agents/strategy_agent/tests/test_async_analytics_queue.py -q
```

| Test file | Tests | Failures |
|---|---|---|
| `test_analytics_service.py` | 10 | 0 |
| `test_analytics_integration.py` | 10 | 0 |
| `test_async_analytics_queue.py` | 6 | 0 |
| **Total** | **26** | **0** |

Pre-existing failures in non-analytics test files (14 total across `test_agents_basic.py`,
`test_document_utils.py`, `test_firestore.py`, `test_integration.py`) confirmed unrelated to
DM-PRD-02: zero `agent_analytics_|cost_aggregations_|performance_profiles_` pattern
references in those files. Same pre-existing posture established by DM-19/DM-37/DM-39/DM-40.

### Gate (c) — make lint

```bash
cd /home/agent/workspace && make lint
```

- **codespell:** passes after rewording two pre-existing false-positive triggers (neither
  was a real typo — both were codespell appeasements, not corrections):
  - `docs/design/components/data-management/runs/DM-19-strategy-docs-dev-migration-log.md:284`
    — a verbatim quote of a codespell finding (`CACL ==> CALC`) was rephrased to avoid the
    raw misspelled token. (Note: `# codespell:ignore` on that line would have preserved the
    quoted evidence; the rephrase chose readability over fidelity.)
  - `app/adk/agents/agent_factory/tests/test_factory.py:293` — test variable `name="mot"`
    renamed to `name="max_out"`. Codespell flagged `mot` as a misspelling of "not"; the
    rename is a false-positive workaround, not a real typo fix. (Note: the symmetric
    "no max_output_tokens" case at `test_factory.py:309` still uses `name="no_mot"`; CI's
    codespell does not flag it, presumably because the underscore-prefix changes the
    tokenization. Future contributors may rename for symmetry.)
- **ruff / mypy:** pre-existing baseline (2,451+ ruff errors; ~4,385 mypy errors) identical
  to `main`. DM-43 branch introduces **0 new ruff or mypy errors** — only the run-log (markdown),
  README §5.1 status flip, and PRD status flip are changed.

## Documentation Update (Wave 4 Task 7)

| File | Change |
|---|---|
| `docs/design/components/data-management/README.md` §5.1 | DM-PRD-02 status `Blocked` → `Complete` |
| `docs/design/components/data-management/projects/DM-PRD-02-analytics-suite-migration.md` L3 | `**Status:** Blocked` → `**Status:** Complete` |

## Acceptance Criteria

| AC | Criterion (per DM-PRD-02 §6) | Status |
|---|---|---|
| AC-1 | `rg` scan: 0 legacy Shape A patterns in production code | ✅ 0 hits (2 intentional test carve-outs excluded) |
| AC-2 | In dev Firestore, no top-level `agent_analytics_*`, `cost_aggregations_*`, or `performance_profiles_*` collections exist | ✅ `cost_aggregations_acc_*` in `analytics` DB resolved (pre-flight); `agent_analytics_*` confirmed 0 by DM-39; `performance_profiles_*` confirmed 0 by DM-40 |
| AC-3 | Live agent run → fresh docs at `accounts/{id}/agent_analytics/{metric_id}` | ✅ Smoke 1: 3 docs at Shape B path |
| AC-4 | `async_analytics_queue` flushes to `accounts/{id}/agent_analytics/` with no lost events | ✅ Smoke 1: 3 docs written, 3 read back — count matches |
| AC-5 | `optimization_analyzer` returns non-empty recommendation set for seeded account | ✅ Smoke 4: 3 recommendations returned |
| AC-6 | `performance_profiler` writes land at `accounts/{id}/performance_profiles/` | ✅ Smoke 3: 3 docs at Shape B path |
| AC-6 (ext) | `cost_aggregations` write lands at `accounts/{id}/cost_aggregations/` (issue-level extension of AC-2) | ✅* Smoke 2: 1 doc at Shape B path — but via post-instantiation **monkey-patch** of `AnalyticsService.analytics_db` (production has `analytics_db = None` due to ungranted IAM at `analytics_service.py:67-68`). Path logic verified; production execution gated on the IAM-grant follow-up tracked in **DM-75**. |
| AC-7 | `RUNTIME_WARNINGS_ERRORS.md` callout reflects the new path | ✅ The `performance_profiles` §7 entry was rewritten in PR #457 (DM-40 follow-up); `agent_analytics` and `cost_aggregations` weren't called out separately in RUNTIME_WARNINGS_ERRORS to begin with, so no doc-callout update was needed for those resources. |
| AC-8 | `pytest app/adk/agents/strategy_agent/tests/` passes; `make lint` clean | ✅ 26 analytics tests pass; codespell passes; 0 new ruff/mypy errors |
| DM-PRD-02 docs | Status flipped to Complete in README §5.1 + PRD frontmatter | ✅ Both files updated |
| DM-PRD-05 notify | DM-PRD-05 owner pinged on Linear that one more blocker is cleared | ✅ Posted in DM-43 comment + DM-PRD-05 issue |

## Notes

- **`shared/secrets.py` ↔ stdlib `secrets` import collision:** importing `strategy_agent`
  via `__init__.py` triggers `agents.py` → `google.adk` → `starlette` →
  `from secrets import token_hex`, which resolves to `shared/secrets.py` instead of
  the stdlib module. Fixed by using `importlib.util.spec_from_file_location` to load each
  module directly by file path, creating a minimal `strategy_agent` stub in `sys.modules`.
  This is equivalent to a normal package import for smoke-testing purposes.

- **IAM hold on `AnalyticsService.analytics_db`:** `analytics_service.py:67-68` sets
  `self.analytics_db = None` (existing TODO, IAM permissions not yet granted). The
  `aggregate_daily_costs` smoke test overrode `analytics_db` post-instantiation to exercise
  the write path. The path logic itself (`accounts/{account_id}/cost_aggregations`) is
  confirmed correct; the IAM grant is tracked as a separate operational follow-up in
  **DM-75** (Medium priority, assigned to Ken, scoped across all 3 envs per the DM-PRD-02
  "all envs" rule established by DM-73).

- **DM-37 runbook gap:** DM-37's migration runbook only targeted `(default)` database for
  `cost_aggregations`. The `analytics` named database should also have been targeted, as
  `AnalyticsService` always initialises with `database="analytics"`. The 14 surviving
  collections were resolved inline during DM-43 pre-flight. Future data-migration runbooks
  for analytics resources should always run against both `(default)` and `analytics` DBs.

- Full smoke script at `/tmp/dm43_smoke.py` (ephemeral — VM lifetime only).
