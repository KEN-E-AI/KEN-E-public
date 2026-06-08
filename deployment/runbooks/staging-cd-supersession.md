# Staging CD Supersession Runbook

**Issue:** AH-156
**Last updated:** 2026-06-08
**Applies to:** `deployment/cd/staging.yaml` — the `cd-pipeline` Cloud Build trigger

---

## Overview

As of AH-156, the staging CD pipeline serializes concurrent deploys so that only the **tip commit** of `main` runs `agent_engines.update()` against the shared staging chat engine. Two steps at the head of every build enforce this:

1. **`supersede-redundant-builds`** — cancels strictly-older WORKING/QUEUED `cd-pipeline` builds at build start (best-effort, ordered by `createTime`). It compares each candidate's epoch `createTime` against this build's own, so a newer/tip build is never cancelled — only the tip ever supersedes others.
2. **`tip-commit-guard`** — writes `/workspace/proceed_with_deploy.flag = true|false`. Stale builds write `false`; their five gated deploy steps exit 0 immediately and log `[AH-156] tip-commit-guard: superseded — skipping <step>`.

This matches the "Option 1 + Option 2" approach in AH-156: best-effort cancellation for blast-radius reduction, plus an authoritative per-build flag as the safety net.

---

## Supersession contract

| Build | `proceed_with_deploy.flag` | Deploy steps | Result |
|---|---|---|---|
| Tip commit (latest push) | `true` | All five run normally | Staging fully updated |
| Stale commit (earlier push) | `false` | All five skip immediately | Build exits success, no side effects |

**Gated steps** (skip on `false`):
- `deploy-strategy-supervisor-staging` — `agent_engines.update()` for the strategy tree
- `deploy-ken-e-agent-staging` — `agent_engines.update()` for the chat tree
- `deploy-api-to-cloud-run` — Cloud Run API service
- `deploy-react-cloud-run` — Cloud Run frontend service
- `trigger-prod-deployment` — prod-trigger fan-out

**Ungated steps** (always run):
- Container image builds and pushes — content-addressed by `${COMMIT_SHA}`, no shared mutable target
- Load tests and p95 gate — exercise the deployed API, not this build's image
- GCS export

---

## Verifying supersession is working

After a burst of pushes to `main`, check Cloud Build history:

```bash
gcloud builds list \
  --project=ken-e-cicd \
  --filter="substitutions.TRIGGER_NAME='cd-pipeline'" \
  --limit=20 \
  --format="table(id,status,substitutions.COMMIT_SHA:label=COMMIT,createTime)"
```

Expected pattern after a burst:
- Tip commit build: `SUCCESS` with all deploy steps logging normal output
- Earlier builds: `SUCCESS` (or `CANCELLED`) with deploy steps logging `[AH-156] tip-commit-guard: superseded — skipping …`

In the tip commit build's `supersede-redundant-builds` step log, you should see:
```
[AH-156] Supersession complete: N cancelled, K kept, F failed.
```
where `cancelled` counts strictly-older racing builds that were superseded, `kept` counts builds with a newer-or-equal `createTime` that were intentionally **not** cancelled (so a stale build can never cancel the tip), and `failed` counts cancel calls that returned non-zero (usually a build that reached a terminal state between the list and the cancel).

---

## Overriding for a manual same-commit re-deploy

Use case: you want to re-deploy a specific commit to staging without pushing a new commit.

```bash
gcloud builds triggers run cd-pipeline \
  --project=ken-e-cicd \
  --region=us-central1 \
  --sha=<target-commit-sha>
```

The `supersede-redundant-builds` step still cancels any strictly-older racing builds (never a newer one); the `tip-commit-guard` step re-reads the tip of `origin/main` via `git ls-remote`. If `<target-commit-sha>` is currently the tip of `main`, the deploy proceeds normally. If it is not the tip (e.g., you are re-deploying an older commit for diagnostics), the tip-commit guard writes `false` and the deploy steps skip.

**To force-deploy a non-tip commit** (e.g., emergency rollback to a known-good SHA):
1. Cherry-pick or revert to that commit and push to `main` — the resulting tip commit will then deploy normally through the CD pipeline.
2. Alternatively, deploy directly via `gcloud` bypassing the pipeline entirely:
   ```bash
   # Example: re-deploy the chat agent directly
   cd app/adk && uv run python deploy_ken_e.py --env staging
   ```
   This bypasses the supersession logic and deploys immediately.

---

## Cancellation is ordering-safe (only strictly-older builds are cancelled)

`supersede-redundant-builds` cancels a candidate **only** when its epoch `createTime` is strictly earlier than this build's own (resolved from the same `gcloud builds list` output, since this build is `WORKING` while the step runs). A stale build therefore can never cancel a newer/tip build — closing the race where an older build, reaching its cancel step first, would have cancelled the still-queued tip build and then skipped its own deploy, leaving staging silently un-deployed. If this build cannot resolve its own `createTime` from the list, it cancels nobody and relies entirely on the `tip-commit-guard` (fail-safe).

Builds with an identical `createTime` (same second) are mutually kept and fall through to the guard — the benign residual race documented below.

---

## Residual race: two builds both pass the tip-commit guard

**Scenario:** two builds for the same commit SHA start within a few seconds of each other (e.g., a manual re-trigger before the first build completes its `tip-commit-guard` step). Both read `origin/main`'s tip, both see themselves as the tip, both write `true`, and both run `agent_engines.update()`.

**How to recognize it:** Cloud Build console shows two `deploy-ken-e-agent-staging` SUCCESS entries in close succession for the same `COMMIT_SHA`. Secret Manager `ken-e-engine-id` shows two versions stamped within seconds of each other pointing to the same engine.

**Impact:** functionally harmless (the second update is a no-op since the artifact is identical), but reintroduces the concurrent-LRO window that this fix targets. If you observe elevated code-13 failures *after* AH-156 merges and correlated with same-SHA double-triggers, the mitigation is a per-engine GCS atomic-create lock around `agent_engines.update()` — see **Escalation** below.

---

## The AH-154 precedent

[AH-154](https://linear.app/ken-e/issue/AH-154/200-stale-pending-prod-builds-deploy-to-prod-trigger-fires-per-main) solved the same swarm problem on the **prod** side by converting the `deploy-to-prod-pipeline` trigger to manual-invocation-only. Staging cannot follow that path (staging *is* push-to-main CD), so AH-156 implements supersession-in-yaml instead. `deployment/scripts/cancel_stale_pending_prod_builds.sh` is the precedent for the `gcloud builds list/cancel` shell pattern reused inside this build.

---

## Escalation: when to add a deploy mutex (Option 3)

If, after AH-156 merges, you still observe transient `500 INTERNAL` (gRPC code 13) failures on `deploy-ken-e-agent-staging` correlating with two near-simultaneous tip-commit-guard passes (the residual-race scenario above), file a follow-up issue to implement a per-engine GCS atomic-create lock in `app/adk/deploy_ken_e.py`:

```
Signal: Cloud Logging filter
  resource.type="build"
  textPayload=~"INTERNAL"
  labels."build.googelapis.com/trigger_id"="eb5667d6"
  + two WORKING builds overlap in time for the same trigger
```

The mutex would wrap `agent_engines.update()` in both `deploy_ken_e.py` and `deploy_with_sys_version.py` with a GCS `objects.insert` (If-None-Match: *) atomic create, releasing via object delete. Python unit tests with a mocked GCS client are appropriate at that stage.

**Do not add the mutex without confirming the residual-race signal first.** The coupling cost (new shared GCS state, error handling in the deploy path) is only justified if Option 1 + Option 2 prove insufficient.

---

## Related files

- [`deployment/cd/staging.yaml`](../cd/staging.yaml) — the pipeline this runbook documents
- [`deployment/scripts/cancel_stale_pending_prod_builds.sh`](../scripts/cancel_stale_pending_prod_builds.sh) — AH-154 precedent for the cancel pattern
- [AH-154](https://linear.app/ken-e/issue/AH-154) — prod-side swarm fix (manual trigger)
- [AH-156](https://linear.app/ken-e/issue/AH-156) — this fix
