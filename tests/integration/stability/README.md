# Sprint 6 Local Test Harness

Local validation surface for the four Sprint 6 stability stories
(1.1.1-3, 1.14.5, 1.1.2-3, 1.1.5-4). The harness is **not** a CI target —
it's the toolkit a developer drives by hand to satisfy ACs 6.10–6.24.

See `docs/sprint6-phase2-plan.md` for the broader Phase 2 plan.

## Layout

```
tests/integration/stability/
├── query_corpus.py              # 28 prompts spanning 5 categories
├── memory_profiler.py           # psutil RSS sampler context manager
├── redis_ttl_fixture.py         # TTLController + pytest fixture
├── stream_reconnect_fixture.py  # APIServerSubprocess + streaming_chat_with_kill
├── weave_trace_capture.py       # In-memory weave span capture + compliance replay
├── diverse_invocation_runner.py # Async chat-completion runner + JSON report + CLI
├── runs/                        # Gitignored — JSON reports land here
└── tests/                       # Self-tests (19 tests, all pass green w/ Redis up)
```

## Prerequisites

- Python 3.12 via `uv` (the `api` venv).
- **Redis** on `localhost:6379` for the Redis fixture self-tests:
  `docker run -d --name kene-redis -p 6379:6379 redis:7-alpine`
- For Story 5 reconnect runs against the real API:
  - Application Default Credentials with Vertex AI + Firestore access.
  - A super-admin Firebase ID token (via the frontend or a custom mint).

## Running the self-tests

```bash
cd api
uv run pytest ../tests/integration/stability/tests/ -v
```

All 19 tests should pass green. Two of them require local Redis — they
fail fast with a clear error if Redis is unreachable, which is what you
want.

## Story → module mapping

| Story | ACs | Modules used |
|---|---|---|
| 1.1.1-3 (ADK stability) | 6.10–6.13 | `diverse_invocation_runner` + `memory_profiler` |
| 1.14.5 (OTEL stability) | 6.14–6.17 | `diverse_invocation_runner` + `memory_profiler` + `weave_trace_capture` |
| 1.1.2-3 (trace compliance) | 6.18–6.20 | `diverse_invocation_runner` + `weave_trace_capture` |
| 1.1.5-4 (session stability) | 6.21–6.24 | `memory_profiler` + `redis_ttl_fixture` + `stream_reconnect_fixture` |

## Driving a run by hand

```bash
# 1. Start the API locally (port 8000).
cd api && uv run uvicorn src.kene_api.main:app --port 8000

# 2. Mint a super-admin token (frontend devtools is the easiest path).
export HARNESS_AUTH_TOKEN="ey..."
export HARNESS_API_BASE_URL="http://localhost:8000"

# 3. Run a 50-query sweep into the harness's runs/ directory.
cd /path/to/repo
uv run --directory api python -m tests.integration.stability.diverse_invocation_runner \
    --queries 50 \
    --output tests/integration/stability/runs/run_$(date +%s).json
```

The runner writes a `RunReport` JSON with per-query latency, errors,
session ids, token counts, and aggregate p50/p95.

## Notes & known gaps

- **Live stream-reconnect smoke is not in the self-test suite.** The
  fixture's mechanics are unit-tested against a stub FastAPI app. AC-6.22
  is exercised when Story 5 drives the fixture against the dev API.
- **Weave capture works without `weave.init()`.** The patch is on the
  call-context module, so any weave-decorated function flowing through
  `client.create_call(...)` is captured. If wandb is configured, the
  spans also reach the dashboard as usual.
- **Per-call agent type is best-effort.** The runner reads
  `metadata.agent_type` / `metadata.actual_agent_type` /
  `metadata.dispatched_agent` from the response. If none are present,
  `actual_agent_type` is `None` — the validation stories should
  reconcile via Weave traces instead of trusting this field.
