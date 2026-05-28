# Emergency Rollback — Per-Turn Dispatch

## When to use this runbook

The per-turn dispatch path (`specialist_runtime` + `attach_specialists_before_agent_callback`) is the **unconditional** production path as of AH-PRD-09 Phase 2 (AH-60, merged R1). There is no feature flag — the path cannot be toggled off at runtime. If the runtime resolver breaks at the code level (specialists fail to resolve, root agent errors on every turn), the remediation is a Cloud Run revision rollback.

## Emergency rollback procedure

### Step 1 — Roll back to the previous Cloud Run revision

```bash
# List recent revisions to find the last-known-good one
gcloud run revisions list --service kene-api-{env} --region {region} --limit 5

# Roll 100% of traffic to the previous revision
gcloud run services update-traffic kene-api-{env} \
  --region {region} \
  --to-revisions=<previous-revision-name>=100
```

Replace `{env}` with `development`, `staging`, or `production`, and `{region}` with the deployed region (typically `us-central1`).

**Propagation time:** ~30 s. No Firestore changes are involved; the revision rollback is immediate at the Cloud Run layer.

### Step 2 — Verify

Check that the root agent accepts chat turns and dispatches to specialists correctly in the rolled-back revision. A successful `POST /api/v1/accounts/{account_id}/chat` with a non-error response is sufficient.

### Step 3 — Alert and triage

1. Page oncall if not already paged.
2. File an incident linking this runbook and the error that triggered the rollback.
3. Check `docs/design/components/agentic-harness/projects/AH-PRD-09-per-turn-dispatch.md` §9.1 Risks for the relevant failure mode and its documented mitigation.

## Why there is no flag-based rollback

The per-turn dispatch feature flag (`agentic_harness_per_turn_dispatch`) was dropped in AH-66 (2026-05-28). KEN-E had no production users at rollout time and no legacy deploy-time factory path to fall back to — a flag would have guarded a path that did not exist. Revision rollback is both simpler and faster than a flag flip would have been.

For runtime-resolver troubleshooting before resorting to a revision rollback (e.g. stale config cache, MCP pool exhaustion), see §9 of [`AH-PRD-09-per-turn-dispatch.md`](../../docs/design/components/agentic-harness/projects/AH-PRD-09-per-turn-dispatch.md).
