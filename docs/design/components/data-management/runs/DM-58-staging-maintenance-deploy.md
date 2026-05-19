# DM-58 — Staging Maintenance Window and Deploy Log

**Issue:** DM-58 — Schedule staging maintenance window and deploy DM-PRD-00–DM-PRD-05 code (covers AC-1, §4.3 steps 1–2)
**PRD:** DM-PRD-06 §4.3 — Staging Cutover, steps 1–2
**Date:** 2026-05-19
**Branch:** docs/DM-58-staging-maintenance-deploy
**Executed by:** Dev Team agent (data-management-dev-team)

---

## Summary

| # | Item | Result | Notes |
|---|------|--------|-------|
| 1 | Maintenance window scheduled | OPEN | Opened at-will per PO (Q1 answer); recorded below |
| 2 | Announcement sent | PENDING | PO to confirm #engineering Slack message was sent (see template below) |
| 3 | Code deployed to staging | PENDING — operator | Standard CD trigger fires on main; operator confirms revision is live |
| 4 | `/health` endpoint OK | PENDING — operator | Paste output below |
| 5 | No startup errors in Cloud Run logs | PENDING — operator | Paste output below |
| 6 | Service-account IAM verified | PENDING — operator | Paste output below |
| 7 | Deploy commit hash recorded | RECORDED | `ef31ad3deb02795544cf3c3b1141831bee92e12c` — see §Deploy Pin |

Pre-conditions (both passed per prior issues):
- DM-56 (Phase 6 dev-environment verification checklist) — Done ✓
- DM-57 (Codebase residue scan) — Done ✓

---

## Maintenance Window Plan

**Window status:** OPEN  
**Opened:** 2026-05-19 (at-will per PO Q1 response — agent opens window when work begins)  
**Expected duration:** ≥ 30 minutes (covers DM-59 dry-run → DM-60 confirm-delete → DM-61 checklist)  
**Scope of impact:** staging Firestore + GCS for `ken-e-staging`; staging API (`kene-api-staging`) may reject writes during migration steps DM-60 and DM-61  
**Announcement channel:** Slack #engineering (Q2 PO answer: "No other teams — Slack #engineering broadcast is sufficient")  
**Announcement sent by:** PO (see template below)  
**Announcement confirmed timestamp:** _(PO: record ISO 8601 UTC when message was sent)_

---

## Announcement Template

> **[Staging maintenance window open — Data Management Shape B cutover]**
>
> **Start time: [INSERT ISO 8601 UTC — e.g. 2026-05-19T14:00:00Z]**
>
> The DM-PRD-06 staging cutover is starting now. `ken-e-staging` Firestore + GCS may be briefly inconsistent during the migration sequence (~30–60 min).
>
> **Impact:** Staging API writes to any account-scoped Firestore collection may fail or land in unexpected paths during the migration window. No production impact.
>
> **Teams affected:** Anyone using `ken-e-staging` for integration or testing.
>
> **ETA:** Window closes when DM-61 (Phase 6 staging checklist) posts complete results. Will post follow-up in this thread.
>
> _(PO: fill in start time before sending; post to #engineering)_

---

## Deploy Pin

The CD trigger (`google_cloudbuild_trigger.cd_pipeline` in `deployment/terraform/build_triggers.tf`, trigger name `cd-pipeline`) fires on every push to `main`, running `deployment/cd/staging.yaml`. The last `main` merge at window-open is the SUT for the staging migration.

**Commit hash at window-open:**

```
ef31ad3deb02795544cf3c3b1141831bee92e12c
Merge pull request #537 from KEN-E-AI/chore/ah-54-ci-colocated-agent-tests
```

Source: `git rev-parse HEAD` on `main` at 2026-05-19.

**Trigger name:** `cd-pipeline`  
**Staging YAML:** `deployment/cd/staging.yaml`  
**Cloud Run service:** `kene-api-staging`  
**Expected revision label format:** `kene-api-staging-<auto-suffix>` (Cloud Run auto-generates the revision suffix; `staging.yaml` does not pass `--revision-suffix`). Confirm the revision is READY and the URL resolves correctly — do not expect the suffix to embed the commit SHA.  
**Staging API URL:** `https://kene-api-staging-391472102753.us-central1.run.app`

> **Operator note:** Confirm the deployed Cloud Run revision name embeds `ef31ad3d` before starting DM-59. If `main` advanced after this commit, the revision will carry a different hash — record that hash in the amendment box below.

**Amendment (if main advanced before deploy):**  
_(Operator: if a newer commit deployed, record here: `git rev-parse HEAD` output + commit subject)_  
_(Corrected commit: ______)_

---

## Healthcheck Evidence

Commands listed for operator execution. Paste output below each command block.

### 1 — Cloud Run revision check

```bash
gcloud run services describe kene-api-staging --region=us-central1 \
  --project=ken-e-staging \
  --format='value(status.latestReadyRevisionName,status.url)'
```

**Expected:** `kene-api-staging-<commit-sha>` and `https://kene-api-staging-391472102753.us-central1.run.app`

_(operator: paste output here)_

---

### 2 — `/health` endpoint

```bash
curl -isS https://kene-api-staging-391472102753.us-central1.run.app/health
```

**Expected:** First line `HTTP/2 200` followed by JSON body (e.g., `{"status": "ok"}`). `-i` includes the response headers so the status code is visible.

_(operator: paste output here)_

---

### 3 — Startup error scan (last 1 h)

```bash
gcloud logging read \
  'resource.type=cloud_run_revision AND resource.labels.service_name=kene-api-staging AND severity>=ERROR' \
  --project=ken-e-staging --limit=20 --freshness=1h \
  --format='value(timestamp,jsonPayload.message)'
```

**Expected:** empty output (no errors in the last hour)

_(operator: paste output here — annotate any known-benign errors inline)_

---

## IAM Verification

Commands listed for operator execution. Paste output below each command block.

> **Note:** The agent VM does not have `gcloud` impersonation on `ken-e-staging` (intentional per DM-PRD-00 §7.4 dev-IAM carve-out). An operator with staging IAM must run these and paste the output before DM-59 starts.

### 1 — Firestore admin on the API SA (required for `recursive_delete` + migration writes)

```bash
gcloud projects get-iam-policy ken-e-staging \
  --flatten='bindings[].members' \
  --filter='bindings.members:serviceAccount:ken-e-api@ken-e-staging.iam.gserviceaccount.com' \
  --format='value(bindings.role)'
```

**Expected:** `roles/datastore.owner` (required for `recursive_delete` in the `--confirm-delete` migration step — `roles/datastore.user` is insufficient and will cause PERMISSION_DENIED at DM-60)

_(operator: paste output here)_

---

### 2 — GCS bucket access for `kene-docs-staging-*`

```bash
gsutil iam get gs://kene-docs-staging-us-central1 2>&1 \
  | grep -E 'ken-e-api@ken-e-staging|storage\.object(Admin|Creator)'
```

**Expected:** at least one matching line showing `serviceAccount:ken-e-api@ken-e-staging.iam.gserviceaccount.com` with `roles/storage.objectAdmin` or `roles/storage.objectCreator`

_(operator: paste output here)_

---

### 3 — Firestore composite indexes are READY (DM-PRD-00 prerequisites)

```bash
gcloud firestore indexes composite list \
  --project=ken-e-staging \
  --database='(default)' \
  --format='value(name,state)' | grep -v READY
```

**Expected:** empty output (every index in READY state — non-empty output flags an index still building)

_(operator: paste output here)_

---

## Acceptance Criteria Checklist

| AC | Criterion | Status |
|----|-----------|--------|
| AC-1 | Staging maintenance window scheduled and announced to relevant teams | PENDING — PO confirms Slack #engineering message sent |
| AC-2 | DM-PRD-00–DM-PRD-05 code deployed to staging; service is up and healthy | PENDING — operator pastes healthcheck evidence above |
| AC-3 | Service-account IAM verified for migration + deletion operations | PENDING — operator pastes IAM evidence above |
| AC-4 | Deploy commit hash recorded for DM-61 (issue #6) residue scan | DONE — `ef31ad3deb02795544cf3c3b1141831bee92e12c` |

---

## Sign-off

This run-log is complete when:
1. The PO confirms the Slack #engineering announcement was sent (AC-1).
2. An operator pastes Healthcheck Evidence output (AC-2).
3. An operator pastes IAM Verification output (AC-3).
4. AC-4 is already recorded above.

After all four are filled in, the issue moves to Testing Complete and DM-59 (`migrate_to_shape_b.py --all --env=staging --dry-run`) may begin.

---
_Produced by: data-management-dev-team | Workflow: step-2-implementing | Issue: DM-58 | Date: 2026-05-19_
