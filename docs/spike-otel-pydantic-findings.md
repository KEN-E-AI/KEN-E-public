# Spike 1.14.1: OTEL Pydantic Bug in ADK >=1.23.0

**Status**: RESOLVED — Tracing re-enabled with workaround (2026-03-06)
**ADK Version installed**: 1.26.0
**Date**: 2026-02-24 (updated 2026-03-06)

## Summary

The Pydantic serialization bug in OTEL instrumentation for Google GenAI has been investigated. The bug occurs when `opentelemetry-instrumentation-google-genai` calls `BaseModel.model_dump()` on Pydantic **classes** instead of instances, causing `TypeError`. A workaround exists via environment variable.

## Background

- Our `pyproject.toml` requires `google-adk>=1.23.0`
- ADK 1.24.0 added extra OTEL span attributes via `opentelemetry-instrumentation-google-genai`
- The Pydantic bug was in the OTEL instrumentation package calling `BaseModel.model_dump()` on class objects (not instances) when recording `output_schema` as a span attribute
- Currently installed version is 1.14.1 — which predates the 1.24.0 OTEL changes

## Key Findings

### 1. Current State

Our `deploy_ken_e.py` creates `AdkApp` with `enable_tracing=False` (line 290), which means OTEL tracing is disabled for the deployed agent. The bug is not triggered in our current deployment.

### 2. Bug Trigger Condition

The bug triggers when:
1. `OTEL_SDK_DISABLED=false` (OTEL enabled)
2. An agent uses `output_schema` (a Pydantic model class) for structured output
3. The OTEL instrumentation tries to serialize the schema as a span attribute
4. It calls `model_dump()` on the **class** instead of an instance → `TypeError`

Our **strategy agents** use `output_schema` (e.g., `StructuredBusinessStrategy`, `CompetitiveAnalysis`) and would be affected. The chatbot agent does NOT use `output_schema`.

### 3. Workaround

```bash
# Disable only the google-genai OTEL instrumentation while keeping OTEL enabled
OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=google-genai
OTEL_SDK_DISABLED=false
```

This allows general OTEL tracing to work while disabling the problematic Google GenAI instrumentation package.

### 4. ADK Version Status

| Version | Relevant Changes |
|---------|-----------------|
| 1.14.1 | Currently installed — no OTEL changes |
| 1.23.0 | Our minimum requirement |
| 1.24.0 | Added extra OTEL span attributes (introduces bug) |
| 1.25.0 | Added `/health` and `/version` endpoints |
| 1.25.1 | Latest (Feb 18, 2026) — bug status unclear |

### 5. Testing Requirements

Before enabling OTEL in production:
1. Upgrade to ADK 1.25.1
2. Test with `OTEL_SDK_DISABLED=false` and a strategy agent that uses `output_schema`
3. If bug persists, apply the workaround: `OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=google-genai`
4. Test both strategy agents (which use `output_schema`) and chatbot agent (which doesn't)

## Recommendation for Sprint 5

### 1.14.2: OTEL Re-enablement Plan

1. Upgrade ADK to 1.25.1
2. Set `enable_tracing=True` in `deploy_ken_e.py` (configurable via env var)
3. Apply workaround `OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=google-genai` if needed
4. Test in dev environment before staging/production

### 1.14.3: OTEL + Weave Coexistence

- Weave has its own tracing (via `@weave.op()`) which is independent of OTEL
- OTEL spans can complement Weave traces for infrastructure-level visibility
- No conflict between the two systems — they operate at different levels

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Bug persists in 1.25.1 | Low | Workaround available via env var |
| OTEL overhead in production | Low | Can disable per-service |
| OTEL + Weave interference | None | Independent systems |
| Strategy agent output_schema breakage | Med | Test before enabling OTEL |

## Resolution (2026-03-06)

Tracing has been re-enabled across all environments:

1. `deploy_ken_e.py` now sets `enable_tracing=True` and applies the workaround via
   `os.environ.setdefault("OTEL_PYTHON_DISABLED_INSTRUMENTATIONS", "google-genai")`
   before creating `AdkApp`.
2. `.env.development`, `.env.staging`, `.env.production` all set:
   - `OTEL_SDK_DISABLED=false`
   - `OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=google-genai`
3. GCP Agent Engine dashboards (Tools, Traces, Models, Usage) now auto-populate.
4. A direct GA MCP server health ping was added at `api/src/kene_api/services/mcp_health_service.py`
   for proactive detection of MCP server outages.

## Existing Code References

- `app/adk/deploy_ken_e.py:299` — `enable_tracing=True` (re-enabled)
- `app/adk/agents/strategy_agent/orchestrator.py` — uses `output_schema` for formatters
- `app/adk/agents/ken_e_agent.py` — does NOT use `output_schema`
