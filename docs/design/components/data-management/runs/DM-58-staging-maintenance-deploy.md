# DM-58 — Staging Maintenance Window and Deploy Log

**Issue:** DM-58 — Schedule staging maintenance window and deploy DM-PRD-00–DM-PRD-05 code (covers AC-1, §4.3 steps 1–2)
**PRD:** DM-PRD-06 §4.3 — Staging Cutover, steps 1–2
**Date:** 2026-05-19 (template) · 2026-05-23 (PO verification addendum)
**Branch:** docs/DM-58-staging-maintenance-deploy
**Executed by:** Dev Team agent (data-management-dev-team) — template · PO (operator with staging IAM) — verification

---

## PO Verification Addendum — 2026-05-23

The operator verification (AC-2, AC-3) was run by the PO against `ken-e-staging` on 2026-05-23T10:57Z, after the DM-PRD-06 IAM blocker was cleared (`roles/datastore.owner` granted to `ken-e-api@ken-e-staging` via terraform PR #612, merged to `main` as `ae7d3b99`). Evidence is pasted into the blocks below.

**All three technical ACs are satisfied:** code is deployed + healthy (AC-2), service-account IAM is in place (AC-3), and the deploy pin is amended to current `main` (AC-4).

**The maintenance window is deliberately NOT yet open.** AC-1 (the Slack #engineering announcement, which signals "cutover starting now") is held pending an explicit PO go-ahead to open the window. The migration sequence (DM-59 dry-run → DM-60 confirm-delete → DM-61 checklist) has **not** been started. This run-log records the readiness state; it is not the window-open marker.

---

## Summary

| # | Item | Result | Notes |
|---|------|--------|-------|
| 1 | Maintenance window scheduled | HELD | Plan recorded below; window NOT yet open — awaiting PO go-ahead |
| 2 | Announcement sent | HELD (AC-1) | Not sent — opening the window is a deliberate, separate PO action |
| 3 | Code deployed to staging | ✅ VERIFIED | Live ready revision `kene-api-staging-00336-qkg` (READY); staging CD current |
| 4 | `/health` endpoint OK | ✅ VERIFIED | `HTTP/2 200`, Firestore/Neo4j/Redis healthy — see evidence |
| 5 | No startup errors in Cloud Run logs | ✅ VERIFIED | No boot errors; only benign runtime cache-serialization warnings (annotated) |
| 6 | Service-account IAM verified | ✅ VERIFIED | `datastore.owner` + `storage.admin`/`objectAdmin`; indexes READY |
| 7 | Deploy commit hash recorded | ✅ AMENDED | Superseded `ef31ad3d` → current `main` HEAD `ae7d3b99` — see §Deploy Pin |

Pre-conditions (both passed per prior issues):
- DM-56 (Phase 6 dev-environment verification checklist) — Done ✓
- DM-57 (Codebase residue scan) — Done ✓

---

## Maintenance Window Plan

**Window status:** HELD — verified ready, NOT yet open (awaiting explicit PO go-ahead)
**Expected duration:** ≥ 30 minutes (covers DM-59 dry-run → DM-60 confirm-delete → DM-61 checklist)
**Scope of impact:** staging Firestore + GCS for `ken-e-staging`; staging API (`kene-api-staging`) may reject writes during migration steps DM-60 and DM-61
**Announcement channel:** Slack #engineering (Q2 PO answer: "No other teams — Slack #engineering broadcast is sufficient")
**Announcement sent by:** PO (template below) — **not yet sent**
**Announcement confirmed timestamp:** _(PO: record ISO 8601 UTC when the message is sent — this is the window-open moment)_

---

## Announcement Template

> **[Staging maintenance window open — Data Management Shape B cutover]**
>
> **Start time: [INSERT ISO 8601 UTC — e.g. 2026-05-23T14:00:00Z]**
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

**Original pin (2026-05-19) — SUPERSEDED:**

```
ef31ad3deb02795544cf3c3b1141831bee92e12c
Merge pull request #537 from KEN-E-AI/chore/ah-54-ci-colocated-agent-tests
```

This 05-19 pin is stale — `main` has advanced through the full DM/CH/FF merge stream since.

**Amended pin (2026-05-23, PO verification):**

```
ae7d3b9989335b5087f175525e8a8c539790b192
chore(terraform): grant ken-e-api datastore.owner (staging + prod) — DM-PRD-06 (#612)
```

Source: `git rev-parse origin/main` at 2026-05-23T10:57Z. Staging CD is current and tracking `main`: the live ready revision is `kene-api-staging-00336-qkg` (created 2026-05-23T10:56Z, READY), which deployed off this `main` stream.

> **Operator note (re-confirm at window-open):** Because the window is HELD, `main` may advance further before the cutover actually runs. The binding deploy pin is whatever `main` HEAD is deployed to `kene-api-staging` **at the moment AC-1's announcement is sent**. Re-run `git rev-parse origin/main` + the Cloud Run revision check below immediately before starting DM-59, and update this box if `ae7d3b99` is no longer HEAD.

**Trigger name:** `cd-pipeline`
**Staging YAML:** `deployment/cd/staging.yaml`
**Cloud Run service:** `kene-api-staging`
**Revision label format:** `kene-api-staging-<auto-suffix>` (Cloud Run auto-generates the suffix; `staging.yaml` does not pass `--revision-suffix`). The suffix does NOT embed the commit SHA — confirm via revision READY state + URL resolution, not the suffix.
**Staging API URL:** `https://kene-api-staging-391472102753.us-central1.run.app`

---

## Healthcheck Evidence

Verified by PO on 2026-05-23T10:57Z.

### 1 — Cloud Run revision check

```bash
gcloud run services describe kene-api-staging --region=us-central1 \
  --project=ken-e-staging \
  --format='value(status.latestReadyRevisionName,status.url)'
```

**Output (2026-05-23T10:57Z):**

```
kene-api-staging-00336-qkg	https://kene-api-staging-d3wm5f7uba-uc.a.run.app
```

Revision `00336-qkg` (created 2026-05-23T10:56Z) is READY and serving traffic. (The `d3wm5f7uba-uc` and `391472102753` URL forms both resolve to the same service.)

---

### 2 — `/health` endpoint

```bash
curl -isS https://kene-api-staging-391472102753.us-central1.run.app/health
```

**Output (2026-05-23T10:57Z):**

```
HTTP/2 200
content-type: application/json

{"status":"healthy","message":"API is running","services":{"neo4j":"healthy","firestore":"healthy","redis":"healthy","mcp":"unavailable"}}
```

`200`; Firestore + Neo4j + Redis all healthy. (`mcp: unavailable` is the expected steady-state for the API container — the MCP servers run in the agent runtime, not the API service; not a DM-58 concern.)

---

### 3 — Startup error scan (last 1 h)

```bash
gcloud logging read \
  'resource.type=cloud_run_revision AND resource.labels.service_name=kene-api-staging AND severity>=ERROR' \
  --project=ken-e-staging --limit=20 --freshness=1h \
  --format='value(timestamp,jsonPayload.message)'
```

**Output (2026-05-23T10:57Z):** no startup/boot errors. The only ERROR-severity entries are repeated runtime cache-write warnings:

```
2026-05-23T10:31:45Z  Failed to encode JSON for key user_context:<uid>: Object of type DatetimeWithNanoseconds is not JSON serializable
  … (repeated)
```

**Annotation — KNOWN-BENIGN, pre-existing:** these are runtime Redis user-context cache-serialization warnings (a `DatetimeWithNanoseconds` value isn't JSON-serialized before caching). They are **not** startup failures — the service boots cleanly and serves `200`. Unrelated to the DM-PRD-06 code or the migration. Flagged separately to the platform owner as a pre-existing app bug; does **not** block DM-58.

---

## IAM Verification

Verified by PO on 2026-05-23T10:57Z (PO holds staging IAM; the agent-VM carve-out note no longer applies).

### 1 — Firestore admin on the API SA (required for `recursive_delete` + migration writes)

```bash
gcloud projects get-iam-policy ken-e-staging \
  --flatten='bindings[].members' \
  --filter='bindings.members:serviceAccount:ken-e-api@ken-e-staging.iam.gserviceaccount.com' \
  --format='value(bindings.role)'
```

**Output (relevant roles):**

```
roles/datastore.owner
roles/datastore.user
roles/storage.admin
roles/storage.objectAdmin
roles/storage.objectViewer
roles/secretmanager.secretAccessor
… (aiplatform/firebase/logging/monitoring service roles omitted)
```

✅ `roles/datastore.owner` is present (codified via terraform PR #612) — `recursive_delete` at DM-60 will not hit PERMISSION_DENIED.

---

### 2 — GCS bucket access

> **Correction to the original command:** the templated bucket `gs://kene-docs-staging-us-central1` does not exist in `ken-e-staging`. The staging file/document buckets are `ken-e-staging-files-us` and `ken-e-staging-files-eu`. Bucket-level IAM is not set per-bucket — access is granted **project-wide**, which covers every bucket in the project.

```bash
gcloud projects get-iam-policy ken-e-staging \
  --flatten='bindings[].members' \
  --filter='bindings.members:serviceAccount:ken-e-api@ken-e-staging.iam.gserviceaccount.com' \
  --format='value(bindings.role)' | grep storage
```

**Output:**

```
roles/storage.admin
roles/storage.objectAdmin
roles/storage.objectViewer
```

✅ Project-level `roles/storage.admin` + `roles/storage.objectAdmin` grant the API SA full object access across all `ken-e-staging` buckets (incl. `ken-e-staging-files-us`/`-eu`).

---

### 3 — Firestore composite indexes are READY (DM-PRD-00 prerequisites)

```bash
gcloud firestore indexes composite list \
  --project=ken-e-staging \
  --database='(default)' \
  --format='value(name,state)' | grep -v READY
```

**Output:** empty (every composite index on `(default)` is in `READY` state).

✅ No index still building.

---

## Acceptance Criteria Checklist

| AC | Criterion | Status |
|----|-----------|--------|
| AC-1 | Staging maintenance window scheduled and announced to relevant teams | **HELD** — announcement intentionally not sent; awaiting explicit PO go-ahead to open the window |
| AC-2 | DM-PRD-00–DM-PRD-05 code deployed to staging; service is up and healthy | ✅ DONE — rev `00336-qkg` READY, `/health` 200, no boot errors |
| AC-3 | Service-account IAM verified for migration + deletion operations | ✅ DONE — `datastore.owner` + `storage.admin`/`objectAdmin`; indexes READY |
| AC-4 | Deploy commit hash recorded for DM-61 (issue #6) residue scan | ✅ DONE — amended to `ae7d3b99` (re-confirm at window-open) |

---

## Sign-off

This run-log captures the **readiness** state. Three of four ACs are satisfied. The remaining step is a deliberate PO decision, not a verification task:

1. **AC-1 (held):** PO opens the window by sending the Slack #engineering announcement and recording the timestamp. **This commits to the migration sequence** (DM-59 dry-run → DM-60 confirm-delete → DM-61 checklist) and is the gate for starting DM-59.
2. AC-2 ✅ — healthcheck evidence pasted above.
3. AC-3 ✅ — IAM evidence pasted above.
4. AC-4 ✅ — pin amended above.

Until the PO chooses to open the window, DM-58 stays in its current state and DM-59 does not begin.

---
_Produced by: data-management-dev-team (template) · PO verification 2026-05-23 | Workflow: step-2-implementing → po-operator-verification | Issue: DM-58_
