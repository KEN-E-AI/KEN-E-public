# Sprint 6 Phase 2 — Implementation Plan

> **Transient document.** Delete on Sprint 6 closeout.

This plan picks up after PR #240 merged Feature 1.1.4 to main. It covers the remaining 5 Sprint 6 stories (1 new harness infra + 4 stability validations) and the closeout. Designed so a fresh session can resume any single piece without re-discovering context.

## Overview

| # | Story | Pts | Notion | Status | Effort | Order |
|---|---|---|---|---|---|---|
| 1 | 1.1.x — Sprint 6 local test harness | 8 | [story](https://www.notion.so/34f30fd653028133badcc84c941827df) | In progress | ~9 hr | First (blocks 4) |
| 2 | 1.1.1-3 — ADK production stability | 5 | [story](https://www.notion.so/34230fd6530281978757cb5c8935f46e) | Backlog | ~4 hr | After harness |
| 3 | 1.14.5 — OTEL production stability | 5 | [story](https://www.notion.so/34230fd6530281e8bbd5c2a158284eca) | Backlog | ~5 hr | After harness; **probe outcome unknown** |
| 4 | 1.1.2-3 — Trace compliance | 5 | [story](https://www.notion.so/34230fd6530281d1af1ae3ca904e4ac5) | Backlog | ~5 hr | After harness |
| 5 | 1.1.5-4 — Session stability | 5 | [story](https://www.notion.so/34230fd653028179bff5dfbc7a594a12) | Backlog | ~5 hr (2 hr wall-clock) | After harness |
| 6 | Sprint 6 closeout | — | [Sprint 6](https://www.notion.so/34230fd65302819684eef7045d2abf23) | — | ~1 hr | Last |

**Persistent decision log:** [Session — Sprint 6 Phase 2](https://www.notion.so/34f30fd65302810cac44f7f7e39e55bd) (Notion). Per-story decisions go as comments on each story page when the story closes.

## Phase 0 decisions (locked at start of Phase 2)

1. **Filed harness as a 9th Sprint 6 story** rather than bundling under 1.1.1-3. AC-6.28 will read "all 9 stories meet ACs." The 4 stability stories were updated to set `Blocked By = harness story`.
2. **Validation stories run LOCAL.** Story titles say "production validation" but Sprint 6 ACs 6.10–6.24 use `locally`. The harness IS the validation surface.
3. **OTEL probe is a known unknown.** Story 1.14.5 starts with the diagnostic; either outcome ships (re-enable workaround OR delete it). Finding goes in the closeout writeup, not as a blocker.
4. **Linear is post-Sprint-7.** Sprint 6 stays Notion-tracked.
5. **No /start-session, /run-tests, /end-session.** Those skills are gone. Manual Notion updates substitute. Persistent log = Session Log entry above + per-story comments.
6. **Branch strategy:** one branch per story (`feature/1.1.x-sprint6-harness`, `feature/1.1.1-3-adk-stability`, etc.), each landing as its own PR off `main`. Don't stack — the harness merges first, then validation stories pull in main.

## Story 1 — Harness build (9 hr)

Branch: `feature/1.1.x-sprint6-harness` off `main`.

Directory: `tests/integration/stability/`. Tests: `tests/integration/stability/tests/`.

### Module 1 — `query_corpus.py` (~30 min)

Pure data; no runtime deps.

- Define `QueryCategory` enum: `ONBOARDING`, `STRATEGY`, `ANALYTICS`, `ERROR_SCENARIO`, `EDGE_CASE_ROUTING`.
- Define `QueryCase` dataclass: `query: str`, `category: QueryCategory`, `expected_agent_type: str` (one of `orchestrator | chatbot | strategy_supervisor | strategy_sub_agent | specialist`), `notes: str = ""`.
- Module-level `QUERIES: list[QueryCase]` with **≥25 entries**, ≥5 per category. Source from realistic prompts that exercise the routing surface (use `app/adk/agents/registry.py` agent IDs as routing targets).
- Helper `queries_by_category(cat) -> list[QueryCase]`.
- Test: ≥25 total, ≥5 per category, all `expected_agent_type` values are in the registry's known set.

### Module 2 — `memory_profiler.py` (~45 min)

`psutil`-based RSS sampler. Check `pyproject.toml` for `psutil`; add if missing.

- `class MemoryProfile`: `baseline_rss: int`, `samples: list[tuple[float, int]]` (monotonic_ts, rss_bytes), `final_rss: int`, `delta_pct: float`, `peak_rss: int`.
- `class MemoryProfiler` context manager:
  - `__init__(sample_interval_s=5.0, target_pid=None)` — defaults to current process; can profile a child by PID.
  - `__enter__`: capture baseline, start daemon sampler thread.
  - `__exit__`: capture final, stop sampler, compute delta_pct + peak.
  - `result() -> MemoryProfile` after exit.
- Test: spawn allocation loop, assert non-zero samples, delta_pct >= 0 and < 100.

### Module 3 — `redis_ttl_fixture.py` (~1 hr)

Pytest fixture for deterministic TTL "expiry" without wall-clock waits.

- **Approach (record in module docstring):** don't fake Redis. Provide a `TTLController` fixture that connects to dev Redis via `api.src.kene_api.redis_client.get_redis_service()` and exposes `delete_key(key)`, `expire_now(key)`, `flush_pattern(pattern)`. Tests simulate expiry via explicit deletion.
- **Justification:** the actual behavior under test is the fallback path when a key is absent. That code path is identical whether absence is from TTL expiry or explicit delete. Faking the entire Redis client requires mocking `setex`/`get` throughout the API — high cost, low realism gain.
- Test: seed a key, `expire_now`, assert `redis_client.get` returns None, assert API fallback to Firestore activates.

### Module 4 — `stream_reconnect_fixture.py` (~2 hr)

Pytest fixture that spawns API in subprocess, kills mid-stream, verifies session preservation.

- `class APIServerSubprocess`: wraps `subprocess.Popen` running `uvicorn src.kene_api.main:app --port <ephemeral>`. Cleanup on teardown.
- Fixture `streaming_chat_with_kill(scope="function")`:
  1. Bind to ephemeral port via `socket.bind(("", 0))`.
  2. Wait for `Application startup complete` in stderr (timeout 30s).
  3. Open `httpx.AsyncClient` with super-admin Bearer token (env var or test fixture).
  4. POST `/api/v1/chat/completions` with `stream=True`, capture `session_id` from first chunk.
  5. After N chunks, send `SIGTERM` to subprocess.
  6. Wait for exit, restart on the same port.
  7. Issue follow-up POST with the captured `session_id`.
  8. Verify session preserved via response metadata or by querying `VertexAiSessionService` directly.
- Mark `@pytest.mark.integration` (slow, requires real ADC).
- Test: smoke against dev API session.

### Module 5 — `weave_trace_capture.py` (~2 hr) — trickiest

Capture `@weave.op()` span metadata in-memory without writing to `trace.wandb.ai`.

- **Approach (decision recorded in module docstring):** monkey-patch `weave.trace.context.call_context` (or equivalent — verify exact import path against pinned weave) at fixture entry to write captured span data to a thread-local list.
- **Why this approach:** weave is pinned narrowly (≥0.51.0,<0.51.57) so monkey-patching is safe for Sprint 6. Alternative (intercepting HTTP exporter) is deeper and adds serialization complexity to data extraction.
- `class TraceCapture` context manager:
  - `__enter__`: patch Weave entry points; clear capture list.
  - `__exit__`: unpatch; flush.
  - `traces: list[dict]` property — captured spans as flat dicts compatible with `validate_trace_compliance(trace_metadata=...)`.
- Each captured trace must contain (match field set in `app/adk/tracking/tests/fixtures/*.json`):
  `agent_id`, `agent_version`, `account_id`, `session_id`, `user_id`, `experiment_id`, `variant_name`, `model_used`, `temperature`, `max_output_tokens`, `environment`, `rollout_percentage`.
- Helper: `replay_through_compliance(captures: list[dict]) -> list[TraceComplianceResult]` runs each capture through `validate_trace_compliance`.
- Test: invoke a `@weave.op()`-decorated function inside `TraceCapture()`, assert ≥1 trace captured, assert each passes `validate_trace_compliance` (or fails for documented reasons).

### Module 6 — `diverse_invocation_runner.py` (~1.5 hr)

Run N queries through the chat endpoint, capture metrics, write JSON report.

- `class InvocationResult`: `query`, `category`, `expected_agent_type`, `actual_agent_type | None`, `duration_s`, `error | None`, `tokens_in | None`, `tokens_out | None`, `session_id | None`.
- `class RunReport`: `started_at`, `finished_at`, `total_runs`, `error_count`, `error_rate`, `latency_p50_s`, `latency_p95_s`, `results`.
- `async def run_corpus(queries, api_url, auth_token, output_path=None) -> RunReport`:
  - For each query: POST `/api/v1/chat/completions` non-streaming, capture status/response/duration.
  - Tokens: from response body (verify shape via `api/src/kene_api/routers/chat.py`).
  - `actual_agent_type`: best-effort tag from response metadata or dispatch tool fired.
  - On error: record `error` string, continue.
- CLI: `python -m tests.integration.stability.diverse_invocation_runner --queries 50 --output run_<ts>.json`.
- Test: against `httpx_mock`-stubbed API, run 5 queries, assert report has 5 results, p50/p95 computed, JSON file written.

### `README.md`

Document end-to-end usage:

- Prerequisites (ADC, env vars, optional API server for runner tests).
- How each validation story uses the harness:
  - 1.1.1-3 → `runner` + `memory_profiler`
  - 1.14.5 → `runner` + `memory_profiler` + `weave_trace_capture`
  - 1.1.2-3 → `runner` + `weave_trace_capture`
  - 1.1.5-4 → `memory_profiler` + `redis_ttl_fixture` + `stream_reconnect_fixture`
- Run harness self-tests: `cd api && uv run pytest ../tests/integration/stability/tests/`.
- `runs/` directory is gitignored (add to `.gitignore`).

### Tests

`tests/integration/stability/tests/`:
- `test_query_corpus.py` — 4 tests
- `test_memory_profiler.py` — 3 tests
- `test_redis_ttl_fixture.py` — 2 tests (skip if Redis unavailable)
- `test_stream_reconnect_fixture.py` — 1 smoke (`@pytest.mark.integration`)
- `test_weave_trace_capture.py` — 3 tests
- `test_diverse_invocation_runner.py` — 3 tests (with `httpx_mock`)

### Closeout for Story 1

- All 7 ACs verified by tests.
- Lint + format clean (`ruff check`, `ruff format`).
- Notion comment on harness story: actual hours, deviations from plan, gaps for follow-ups.
- Status → Done.
- Push branch + open PR (title: `feat: Sprint 6 local test harness (Story 1.1.x)`).
- Don't proceed to Story 2 until harness PR is merged.

## Story 2 — 1.1.1-3 ADK Stability (4 hr)

Branch: `feature/1.1.1-3-adk-stability` off `main` (after harness merges).

Sprint 6 ACs 6.10–6.13. AC-6.10 (≥50 invocations zero failures), 6.11 (config change → tools refresh on next call), 6.12 (callbacks zero errors), 6.13 (10+ org_context merges including missing/empty/large).

Implementation:
1. New script `tests/integration/stability/runs/run_adk_stability.py` (or just a pytest test) that:
   - Imports harness modules.
   - Runs `diverse_invocation_runner.run_corpus(QUERIES, ...)` against a local API.
   - Asserts `error_count == 0` for ADK-construction failures.
   - For 6.11: makes a config change via `/api/v1/agent-configs/ken_e_chatbot` PUT (or directly via Firestore SDK), waits cache TTL (60s) or clears cache, runs another invocation, asserts new instruction is in effect.
   - For 6.12: hooks the callback bus and counts errors during the run.
   - For 6.13: builds 10 org_context payloads (missing, empty, "small", >10KB, malformed JSON, duplicate keys, etc.) and runs each through the chat endpoint.
2. Output: `run_adk_stability_<ts>.json` plus a summary log.
3. If any assertion fails, file follow-ups (max 2 fix-iterations cap).

Closeout: Notion story → Done with results summary; Session Log update; PR.

## Story 3 — 1.14.5 OTEL Stability (5 hr)

Branch: `feature/1.14.5-otel-stability` off `main`.

Sprint 6 ACs 6.14–6.17.

**Step 1 — Probe closure (the wildcard):**
- Set `OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=` (empty) in `app/adk/.env.development`.
- Re-deploy or run the strategy-agent suite locally that uses `output_schema`.
- If `model_dump()` Pydantic crash fires: re-enable the workaround in all .env files, update `docs/spike-otel-pydantic-findings.md` with "still present on ADK ≥1.27.4," document the persisting bug.
- If clean: delete the workaround from `.env.development` / `.env.staging` / `.env.production` / `app/adk/deploy_ken_e.py:313`, update spike doc to mark it resolved.

**Step 2 — Memory delta:**
- Use harness `memory_profiler` to wrap two paired runs of `diverse_invocation_runner` against same query set: one with `OTEL_SDK_DISABLED=true`, one with OTEL on.
- Assert `delta_pct < 10`.

**Step 3 — GenAI span coverage:**
- Use harness `weave_trace_capture` during a 50+ invocation run.
- Assert 100% of invocations produce GenAI spans containing `model`, `tokens_in`/`tokens_out`, `temperature`.

**Step 4 — Non-GenAI OTEL:**
- With workaround active (or default), run 20+ invocations and assert HTTP spans, DB calls, request tracing all produce correct spans (use `weave_trace_capture` + manual Weave UI spot-check).

Closeout: Notion comment on probe outcome, results summary, Session Log update, PR.

## Story 4 — 1.1.2-3 Trace Compliance (5 hr)

Branch: `feature/1.1.2-3-trace-compliance` off `main`.

Sprint 6 ACs 6.18–6.20.

Implementation:
1. Run `diverse_invocation_runner` (≥20 queries from `QUERIES`) wrapped in `weave_trace_capture`.
2. Feed captured traces to `validate_trace_compliance()`.
3. Assert 100% pass rate. If failures:
   - Triage by span level (Root, L1, L2, L3) and agent type.
   - Fix metadata gaps. Up to 2 fix-iterations.
   - If still failing after 2 iterations, file gaps as follow-up tickets and proceed to closeout.
4. Spot-check ≥10 traces in Weave UI for the AC-6.20 manual check.

Closeout: Results summary (pass rate, fixes applied, follow-ups filed), Session Log, PR.

## Story 5 — 1.1.5-4 Session Stability (5 hr; wall-clock 2 hr+)

Branch: `feature/1.1.5-4-session-stability` off `main`.

Sprint 6 ACs 6.21–6.24.

**Test 1 — 2hr sustained session:**
- Use harness `memory_profiler` to wrap a 2-hour run of `diverse_invocation_runner` with sleep-between-runs sized to interact every 5 min (~24 runs).
- Assert `delta_pct < 10`.
- This is wall-clock 2hr — start it early and let it run while doing other stories' coding.

**Test 2 — Stream reconnect:**
- Use harness `stream_reconnect_fixture`.
- Assert state preserved.

**Test 3 — Redis TTL cycle:**
- Use harness `redis_ttl_fixture` to expire `org_context` keys.
- Assert next request reloads from Neo4j/Firestore with no stale data.

**Test 4 — Long-session state integrity:**
- Run 20+ interactions in a single session including ≥1 cache-expiry cycle and ≥1 reconnect.
- Assert all state keys (`organization_context`, `ga_credentials`, `_last_reasoning`, `_previous_tool_calls`) remain intact.

Closeout: Results summary, Session Log, PR.

## Story 6 — Closeout (1 hr)

1. Verify all 9 Sprint 6 stories Done in Notion.
2. Add Review 21 to `docs/design/DESIGN-REVIEW-LOG.md` summarizing Phase 2 (4 validation runs + harness, OTEL probe outcome, any follow-ups).
3. Update Sprint 6 page status: Planning → Done.
4. Add Sprint 6 retro notes to the Sprint page (3 things that went well, 3 things to improve).
5. File any follow-up tickets surfaced during validation as new Notion stories under their proper features.
6. Update Session Log status → Completed with final outcome summary.
7. Delete `docs/sprint6-phase2-plan.md` (this file).

## Risks + open questions for next session

1. **Weave introspection** — harness Module 5 depends on monkey-patching weave internals. If pinned weave version changed during the gap, the patch may need adjustment. Verify against `pyproject.toml` weave constraint before starting.
2. **OTEL probe outcome** — could go either way. Budget 2hr extra in Story 3 if bug persists and we need to update docs + re-enable carefully.
3. **2hr wall-clock floor** in Story 5 — start it as a background task while doing Stories 2/3/4 coding. Or split this story across two sessions.
4. **Harness tests run hermetic** — but stream_reconnect_fixture needs a real API + ADC. Tests for that are marked `@pytest.mark.integration` and skipped in CI.
5. **httpx_mock dependency** — for Module 6 tests. If not in `pyproject.toml`, add it as a dev dep.

## Calibration anchor

Feature 1.1.4 estimate was ~20–22 hr; actual ~17–22 hr effective + 1 unplanned surprise (secret-leak). Phase 2 budget: ~30 hr planned, expect 33–38 hr with 1–2 surprises.
