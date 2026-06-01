# ADK 2.0 spike workspace

**Status:** AH-99 Phase 0.5 — ✅ GO-confirmed (all four live probes exit 0; see [`../spike-adk2-supervisor-orchestration-live.md`](../spike-adk2-supervisor-orchestration-live.md))

This directory contains isolated probes for the ADK 2.0 supervisor-orchestration
spike. The probes validate findings from AH-96 (static analysis, CONDITIONAL GO)
against a real Gemini Flash model and the dev Vertex AI Agent Engine.

**Isolation rule:** This workspace uses `google-adk==2.0.0`. The main KEN-E project
is pinned to `google-adk==1.34.1` in `app/adk/pyproject.toml`. **Never add ADK 2.0
to the project's `uv` env** — it changes the `Event` shape and would break
`extract_billable_tokens` callers across the codebase.

## Prerequisites

### 1. GCP authentication

```bash
gcloud auth application-default login
# Confirm project access
gcloud config set project ken-e-dev
```

The VM / CI service account needs these IAM permissions on `ken-e-dev`:
- `aiplatform.endpoints.predict` (Gemini Flash calls)
- `aiplatform.sessions.list`, `aiplatform.sessions.create`,
  `aiplatform.sessions.delete`, `aiplatform.sessions.appendEvent`,
  `aiplatform.sessions.get` (VertexAiSessionService round-trip)

### 2. Bootstrap the isolated venv

Run from the **repo root** (`KEN-E/`). **Python 3.10+ is required** — `google-adk==2.0.0`
does not support 3.9 (the macOS system `python3`). This run used python3.12:

```bash
python3.12 -m venv .venv-adk2          # or: uv venv --python 3.12 .venv-adk2
.venv-adk2/bin/pip install -r docs/spike-adk2/requirements.txt
# Confirm the pin took (requirements.txt pins google-adk[gcp]==2.0.0):
.venv-adk2/bin/python -c "from importlib.metadata import version; print('google-adk', version('google-adk'))"
```

The venv is at the repo root (not inside this directory) so it is gitignored by
the root `.gitignore`. It is never committed.

### 3. Verify harness imports

```bash
.venv-adk2/bin/python -c "
import sys
sys.path.insert(0, 'docs/spike-adk2')
import _live_harness
_live_harness.import_real_modules()
print('OK')
"
```

Expected output: `OK` (no assertion errors).

## Running individual probes

All probes are run from the **repo root** using the spike venv:

```bash
# Q1 — inner event propagation (task-mode path, live)
.venv-adk2/bin/python docs/spike-adk2/probe-1-inner-event-propagation.py

# Q4 — dynamic-graph fan-out (live)
.venv-adk2/bin/python docs/spike-adk2/probe-4-usage-metadata.py

# Q5 — VertexAiSessionService round-trip (live, hits dev Agent Engine)
.venv-adk2/bin/python docs/spike-adk2/probe-5-session-service-schema.py

# Q7 — LoopAgent review-loop end-to-end (live)
.venv-adk2/bin/python docs/spike-adk2/probe-7-loop-agent-task-mode.py

# Static probes (no live calls needed)
.venv-adk2/bin/python docs/spike-adk2/probe-2-task-mode-graph-restriction.py
.venv-adk2/bin/python docs/spike-adk2/probe-3-weave-contextvar.py
.venv-adk2/bin/python docs/spike-adk2/probe-6-agent-tool-bridge.py
```

Exit-code contract: **0** = assertions held; **1** = a real finding (model 404, changed
ADK API, validation error) → NO-GO; **2** = infrastructure/credentials (missing ADC,
401/403/429/5xx, transport) → INDETERMINATE. Classifier: `_live_harness.classify_exit_code`.

## Dev Agent Engine config

| Setting | Value |
|---|---|
| Project | `ken-e-dev` |
| Location | `us-central1` |
| Engine ID | `5957383247464759296` |
| Full resource | `projects/525657242938/locations/us-central1/reasoningEngines/5957383247464759296` |

These values come from `app/adk/.env.development`. The harness reads them as defaults
from `_live_harness._DEFAULT_*` constants, and on import sets `GOOGLE_GENAI_USE_VERTEXAI=TRUE`
+ `GOOGLE_CLOUD_PROJECT` + `GOOGLE_CLOUD_LOCATION` to the dev values so the model client routes
through Vertex — **no env var export needed**. (Without these, ADK falls back to the AI Studio
backend and raises `No API key was provided`.)

## Session cleanup

All spike sessions use the `spike-ah99-` user_id prefix. Probes call
`cleanup_spike_sessions()` in a `finally` block. To manually clean up any
leaked sessions:

```python
import asyncio
import sys
sys.path.insert(0, 'docs/spike-adk2')
import _live_harness
deleted = asyncio.run(_live_harness.cleanup_spike_sessions())
print(f"Deleted {deleted} spike sessions")
```

## Model spend guardrail

- Model: `gemini-2.0-flash` (cheapest Flash tier; the pinned `-001` alias 404s through ADK's env-based genai client)
- Per-probe ceiling: `MAX_TURNS_PER_PROBE = 3` (enforced by `assert_under_budget()`)
- Aggregate target across all probe runs: ≤ ~50 calls
- Note: the budget guard counts `run_and_collect` invocations (one per probe), not individual model calls — a coarse circuit-breaker, not a precise meter. The GO run spent ~12 Flash calls total.

## Findings documents

| Document | Contents |
|---|---|
| `docs/spike-adk2-supervisor-orchestration.md` | AH-96 static analysis (CONDITIONAL GO) |
| `docs/spike-adk2-supervisor-orchestration-live.md` | AH-99 live evidence + verdict |
