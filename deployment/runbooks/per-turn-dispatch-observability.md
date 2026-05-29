# Per-Turn Dispatch Observability

## Purpose

This runbook covers how to monitor and debug the per-turn dispatch runtime introduced in AH-PRD-09: the specialist resolver (`specialist_runtime.py`), the MCP toolset pool (`mcp_pool.py`), and the TTL config cache (`config_cache.py`). Use it to diagnose cache performance regressions, MCP pool exhaustion, and dispatch errors before escalating to the emergency rollback procedure.

---

## Cloud Monitoring Dashboard

**URL pattern:** `https://console.cloud.google.com/monitoring/dashboards?project={env}` — look for "Per-Turn Dispatch — {env}" (e.g. "Per-Turn Dispatch — development").

The dashboard is provisioned by Terraform (`deployment/terraform/monitoring.tf`, resource `google_monitoring_dashboard.per_turn_dispatch`). If it is missing, run `terraform apply` in the relevant environment workspace.

### Metrics and what they mean

| Metric | Log message | Source module | What to look for |
|--------|-------------|---------------|-----------------|
| `agentic_harness/config_cache_hit_rate` | `config_cache_read` | `config_cache.py` | Rate < 70% → TTL too short or high cache churn from frequent admin edits |
| `agentic_harness/agent_cache_hit_rate` | `specialist_agent_resolved` | `specialist_runtime.py` | Rate < 80% → Firestore config changes triggering frequent specialist rebuilds |
| `agentic_harness/mcp_pool_cache_hit_rate` | `mcp_pool_checkout` | `mcp_pool.py` | Rate < 90% → MCP connections not being reused; check idle TTL configuration |
| `agentic_harness/mcp_pool_size` | `mcp_pool_checkout` | `mcp_pool.py` | Size growing unbounded → check that `aclose()` is invoked on eviction |
| `agentic_harness/dispatch_error_count` | ERROR logs in specialist_runtime | `specialist_runtime.py` | Any sustained non-zero rate → check MCP server health and OAuth credentials |

All five metrics are log-based metrics derived from structured Cloud Logging entries emitted by the runtime modules. The raw log entries are queryable in Cloud Logging under `resource.type="cloud_run_revision"`.

**Example Cloud Logging query for cache misses:**

```
resource.type="cloud_run_revision"
jsonPayload.message="config_cache_read"
jsonPayload.cache_hit=false
```

**Example Cloud Logging query for MCP pool checkouts:**

```
resource.type="cloud_run_revision"
jsonPayload.message="mcp_pool_checkout"
```

---

## W&B Weave Dashboards

Weave dashboards are configured in the W&B UI and are not stored in this repo. The W&B project is `ken-e/{env}`, team `ken-e-ai` (e.g. `ken-e/development`).

The following saved views should be created in the W&B UI under the project's Traces tab:

### 1. Review Loop Iteration Count

- **Weave operation:** `review_loop_iteration`
- **View type:** Histogram of the `iteration_count` attribute per trace
- **Typical range:** Mostly 1–2 iterations per turn. Sustained 3+ iterations indicates review acceptance criteria that are too strict or a specialist instruction mismatch.
- **Where to find it:** W&B project `ken-e/{env}` → Traces → filter `op_name = "review_loop_iteration"` → group by `attributes.iteration_count`.

### 2. Exit Loop vs Max Iterations

- **Weave operation:** `review_pipeline`
- **View type:** Stacked bar or ratio line chart on `exit_reason` attribute values
- **Typical ratio:** `approved` should dominate; `max_iterations` hits indicate the reviewer is rejecting work that meets user expectations.
- **Where to find it:** W&B project `ken-e/{env}` → Traces → filter `op_name = "review_pipeline"` → group by `attributes.exit_reason`.

### 3. `load_config_from_firestore` Span Count

- **Weave operation:** `load_config_from_firestore`
- **View type:** Count per minute line chart
- **Typical range:** On a warm cache, fewer than 1 span per turn (the config-cache hit path still emits a Weave span via the `@safe_weave_op` decorator, but no Firestore call is made). A sustained rate above 1/turn per active session means the TTL cache is not retaining entries.
- **Where to find it:** W&B project `ken-e/{env}` → Traces → filter `op_name = "load_config_from_firestore"` → plot count over time.

---

## Common Debugging Recipes

### Cache hit rate < 70%

1. Verify `GOOGLE_CLOUD_PROJECT_ID` is set correctly on the Cloud Run service — a misconfigured project ID causes every lookup to reach a different Firestore project, guaranteeing a miss.
2. Confirm the config cache TTL is 60 s (the `ttl_seconds` default in `get_cached_config` and `get_cached_merged_config`).
3. Check whether an admin or automated process is updating config docs at high frequency — each write invalidates the cache on the next TTL expiry, forcing a Firestore round-trip.

```bash
# Count config_cache_read misses in the last 30 minutes
gcloud logging read \
  'resource.type="cloud_run_revision" AND jsonPayload.message="config_cache_read" AND jsonPayload.cache_hit=false' \
  --project={env-project-id} \
  --freshness=30m \
  --format="value(timestamp)" | wc -l
```

### MCP pool size growing unbounded

1. Confirm `aclose()` is invoked on every eviction path in `mcp_pool.py` (LRU eviction, TTL sweep, and manual evict). Search for `mcp_pool_aclose_failed` or `mcp_pool_lru_aclose_failed` in logs — these indicate `aclose()` is raising but pool integrity is preserved.
2. Check the `KENE_MCP_POOL_MAX_SIZE` environment variable if it has been overridden from the default of 128 entries.
3. Verify the background sweep is armed — `start()` is called from `attach_specialists_before_agent_callback`. A process that never handles a turn will not run the sweep.
4. Look for `mcp_pool_sweep_error` in Cloud Logging — this indicates the sweep loop crashed and is not evicting idle entries.

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND jsonPayload.message="mcp_pool_sweep_error"' \
  --project={env-project-id} \
  --freshness=1h
```

### High dispatch error count

1. Check MCP server Cloud Run health:
   ```bash
   gcloud run services describe kene-ga-mcp-{env} --region us-central1 --project {env-project-id}
   ```
2. Check OAuth credentials in Firestore — look for expired tokens in `accounts/{account_id}/integrations` documents.
3. Look for `mcp_pool_checkout_timeout` entries — a sustained rate indicates the MCP server is slow to accept new SSE connections. Check the server's instance count and CPU utilization.
4. Look for `Failed to build toolset` or `Unexpected error checking out MCP toolset` — these are the two error patterns counted by `dispatch_error_count`. The full stack trace appears in the same log entry.

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND severity="ERROR" AND jsonPayload.message=~"Failed to build toolset|Unexpected error checking out MCP toolset|mcp_pool_checkout_timeout"' \
  --project={env-project-id} \
  --freshness=1h
```

### Specialists not appearing in Available Specialists block

1. Check the `list_account_agent_configs_cached` TTL (60 s) — if the specialist config was just added to Firestore, wait for the next TTL window.
2. Verify the agent config document has `visible_in_frontend: true` set in Firestore (`agent_configs/{doc_id}`).
3. Search Cloud Logging for `[AVAILABLE-SPECIALISTS]` warning entries — these indicate the specialist resolution failed and the agent was excluded from the block:
   ```bash
   gcloud logging read \
     'resource.type="cloud_run_revision" AND jsonPayload.message=~"AVAILABLE-SPECIALISTS"' \
     --project={env-project-id} \
     --freshness=30m
   ```
4. If the warning shows `No account_id in session state`, verify the API is setting `account_id` in the ADK session state before the first turn.

---

## Cross-references

- Emergency rollback: [`per-turn-dispatch-emergency-rollback.md`](per-turn-dispatch-emergency-rollback.md)
- Architecture and failure modes: [`docs/design/components/agentic-harness/projects/AH-PRD-09-per-turn-dispatch.md`](../../docs/design/components/agentic-harness/projects/AH-PRD-09-per-turn-dispatch.md) §9.1 Risks
