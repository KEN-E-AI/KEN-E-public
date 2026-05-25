# DM-92 — Org `accounts` Field Residue Audit Run Log

**Issue:** DM-92 — Delete dead `accounts` field from staging org docs + audit prod for same residue
**PRD:** DM-PRD-06 §4.1 check #8 ("`organizations/{org_id}` docs have no `accounts.*` fields") — follow-up from DM-61 Anomaly #2
**Script:** `api/scripts/audit_org_accounts_field.py`
**Related run-log:** [`DM-61-phase6-staging-verification-checklist.md`](./DM-61-phase6-staging-verification-checklist.md)

---

## Context

DM-61 Phase-6 staging verification (check #8, 2026-05-23) found that 3 staging org docs
(`equity-trust`, `healthway`, `open-lines`) carried a dead, pre-Shape-D `accounts` **list**
of denormalized account objects on the org doc.

Per Ken's 2026-05-23 decision (DM-61 comment 2026-05-23T16:53Z):
- The field is **legacy residue** — a list shape predating DM-PRD-03's Shape D map design.
- The app reads `accounts` from a Neo4j Cypher `collect(acc)` call
  (`routers/organizations.py:218/353`), never from this Firestore field.
- `migrate_shape_d_split.py` correctly skips it (it looks for a `dict`-typed `accounts` map,
  not a list).
- `ken-e-dev` org docs have no `accounts` field; the app is healthy without it.

Action: delete the field from staging (done in DM-61 close-out, 2026-05-25) and audit
`ken-e-production` for the same residue before the production cutover.

---

## Acceptance Criteria

- [ ] **AC-1** — Staging org docs `equity-trust` / `healthway` / `open-lines` have no `accounts`
  field; check #8 re-runs clean via the canonical script.
- [ ] **AC-2** — `ken-e-production` organizations collection audited for `accounts`-field residue;
  cleaned if found, or confirmed absent.

---

## Operator Commands

### Audit-only (read-only, any environment)

```bash
# Smoke-test against dev (expect PASS — dev was clean during DM-61)
GOOGLE_CLOUD_PROJECT_ID=ken-e-dev \
  python api/scripts/audit_org_accounts_field.py --env=dev

# Re-verify staging (expect PASS — remediation done 2026-05-25 in DM-61 close-out)
GOOGLE_CLOUD_PROJECT_ID=ken-e-staging \
  python api/scripts/audit_org_accounts_field.py --env=staging

# Audit production (before prod cutover)
GOOGLE_CLOUD_PROJECT_ID=ken-e-production \
  python api/scripts/audit_org_accounts_field.py --env=production
```

### Delete residue (only if audit finds offenders)

```bash
# Preview deletion (dry run)
GOOGLE_CLOUD_PROJECT_ID=ken-e-production \
  python api/scripts/audit_org_accounts_field.py --env=production --confirm-delete --dry-run

# Execute deletion
GOOGLE_CLOUD_PROJECT_ID=ken-e-production \
  python api/scripts/audit_org_accounts_field.py --env=production --confirm-delete

# Re-audit to confirm clean
GOOGLE_CLOUD_PROJECT_ID=ken-e-production \
  python api/scripts/audit_org_accounts_field.py --env=production
```

Exit codes: `0` = success/clean, `1` = offenders found or errors, `2` = usage error, `3` = runtime error.

---

## Staging Evidence

### Background — Initial Remediation (DM-61 Close-out, 2026-05-25)

The initial deletion of the dead `accounts` field was performed **inline** during the DM-61
close-out (2026-05-25T07:21Z) before `api/scripts/audit_org_accounts_field.py` existed.
The Firestore REST API was used directly:

| Org doc | Dead `accounts` field value | Deleted by |
|---------|----------------------------|-----------|
| `equity-trust` | `list[1]` — `["a000002"]` | `darshan@ken-e.ai`, 2026-05-25 |
| `healthway` | `list[2]` — `["a000001", "test-account-1"]` | `darshan@ken-e.ai`, 2026-05-25 |
| `open-lines` | `list[1]` — `["a000000"]` | `darshan@ken-e.ai`, 2026-05-25 |

DM-61 check #8 re-verified clean immediately after deletion:

```
# Re-run after remediation — PASS:
  staging organizations docs: 3
  docs with accounts field: NONE
```

### Post-Remediation Re-Verification (Wave 2 — operator-run)

> **TODO — to be filled by the operator when running Wave 2 against `ken-e-staging`.**
>
> IAM prerequisite: `roles/datastore.viewer` on `ken-e-staging` (same posture used in DM-61 Wave B).
>
> Command:
> ```bash
> GOOGLE_CLOUD_PROJECT_ID=ken-e-staging \
>   python api/scripts/audit_org_accounts_field.py --env=staging
> ```
>
> Paste the full stdout (JSON lines + JSON SUMMARY block + final PASS/FAIL line) here.
> Expected final line: `PASS: no org doc has an accounts field`

**Operator:** _(fill in)_
**Date:** _(fill in)_
**IAM account:** _(fill in)_

```
[PASTE SCRIPT OUTPUT HERE]
```

**AC-1 status:** _(PASS / FAIL)_

---

## Production Evidence

> **TODO — to be filled by the operator at prod-cutover preparation time.**
>
> This section is a runbook.  Wave 3 is **operator-gated** — the Dev Team VM does not hold
> `ken-e-production` IAM.  Execute before the production cutover begins.
>
> IAM prerequisite: `roles/datastore.viewer` on `ken-e-production` for the audit; additionally
> `roles/datastore.user` (or `roles/datastore.owner`) for the delete-pass if residue is found.

### Step 1 — Audit (read-only)

```bash
GOOGLE_CLOUD_PROJECT_ID=ken-e-production \
  python api/scripts/audit_org_accounts_field.py --env=production
```

Paste full output below. Two outcomes:

**Outcome A — Clean (expected):** final line is `PASS: no org doc has an accounts field`
→ AC-2 is satisfied; close DM-92; no Step 2 needed.

**Outcome B — Residue found:** the summary JSON shows `orgs_with_accounts_field > 0`
→ proceed to Step 2.

**Operator:** _(fill in)_
**Date:** _(fill in)_
**IAM account:** _(fill in)_

```
[PASTE SCRIPT OUTPUT HERE]
```

**Outcome:** _(A — clean / B — residue found; N offenders)_

---

### Step 2 — Delete residue (only if Step 1 found offenders)

> Skip this step if Step 1 returned `PASS`.

```bash
# Preview first
GOOGLE_CLOUD_PROJECT_ID=ken-e-production \
  python api/scripts/audit_org_accounts_field.py --env=production --confirm-delete --dry-run

# Execute
GOOGLE_CLOUD_PROJECT_ID=ken-e-production \
  python api/scripts/audit_org_accounts_field.py --env=production --confirm-delete
```

**Dry-run output:**

```
[PASTE DRY-RUN OUTPUT HERE]
```

**Delete-pass output:**

```
[PASTE DELETE-PASS OUTPUT HERE]
```

### Step 3 — Re-audit after deletion

```bash
GOOGLE_CLOUD_PROJECT_ID=ken-e-production \
  python api/scripts/audit_org_accounts_field.py --env=production
```

Expected: `PASS: no org doc has an accounts field`

```
[PASTE RE-AUDIT OUTPUT HERE]
```

**AC-2 status:** _(PASS / FAIL)_

---

## Acceptance Criteria Checklist

| AC | Criterion | Status |
|----|-----------|--------|
| AC-1 | Staging org docs confirmed clean via `audit_org_accounts_field.py --env=staging` | ⬜ Pending Wave 2 re-verification |
| AC-2 | `ken-e-production` organizations collection audited and confirmed clean (or cleaned) | ⬜ Pending Wave 3 (prod-cutover prep) |

---

## PO Sign-off Addendum

> To be completed by the PO / operator after Waves 2 and 3.

**Date of AC-1 sign-off:** _(fill in)_
**Date of AC-2 sign-off:** _(fill in)_
**Operator IAM account:** _(fill in)_

| AC | Sign-off | Notes |
|----|----------|-------|
| AC-1 — Staging confirmed clean | ⬜ | |
| AC-2 — Production confirmed clean / cleaned | ⬜ | |

> After both ACs are signed off, move DM-92 to Done.

---

_Produced by: data-management-dev-team | Workflow: step-2-implementing | Issue: DM-92_
