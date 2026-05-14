# DM-75 — IAM Grant: `roles/datastore.user` for Agent Engine SA

**Environment:** `ken-e-dev` / `ken-e-staging` / `ken-e-production`
**Date:** 2026-05-14
**Operator:** Dev Team agent (VM) — IAM apply steps are operator-run (Ken / Darshan)
**Issue:** [DM-75](https://linear.app/ken-e/issue/DM-75)
**PRD:** `docs/design/components/data-management/projects/DM-PRD-02-analytics-suite-migration.md`

## Context

`AnalyticsService._init_firestore_clients()` at `analytics_service.py:60-68` had a
long-standing TODO that set `self.analytics_db = None` because the Agent Engine SA
lacked `roles/datastore.user` on the `analytics` named Firestore database.

This run-log documents the two-stage close-out:

1. **Terraform PR (Dev Team, this PR):** append `roles/datastore.user` to the
   `agentengine_sa_roles` variable default so `terraform apply` grants the role
   to `service-{PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com`
   in each of `ken-e-dev`, `ken-e-staging`, and `ken-e-production`.
2. **Code revert (Dev Team, this PR):** lift the TODO block; restore
   `self.analytics_db = firestore.Client(project=self.project_id, database="analytics")`.

IAM application (Steps 3 and operator-verify below) is a Ken / Darshan action.

Precedent: DM-73 (`performance_profiles` bottleneck index, multi-env terraform apply)
and DM-72 (`strategy_audit` index, dev-only apply).

---

## Pre-flight IAM Audit (Task 1)

**To be performed by Ken / Darshan before merging the terraform change.**

Run against each env and paste output back as a comment on DM-75:

```bash
for project in ken-e-dev ken-e-staging ken-e-production; do
  PN=$(gcloud projects describe "$project" --format='value(projectNumber)')
  SA="service-${PN}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
  echo "=== $project / $SA ==="
  gcloud projects get-iam-policy "$project" \
    --flatten='bindings[].members[]' \
    --filter="bindings.members:serviceAccount:${SA} AND bindings.role:roles/datastore.user" \
    --format='value(bindings.role)'
done
```

Expected output (pre-grant):

| Env | SA | `roles/datastore.user` |
|---|---|---|
| ken-e-dev | `service-{PN}@gcp-sa-aiplatform-re.iam.gserviceaccount.com` | PRESENT or ABSENT |
| ken-e-staging | `service-{PN}@gcp-sa-aiplatform-re.iam.gserviceaccount.com` | ABSENT |
| ken-e-production | `service-{PN}@gcp-sa-aiplatform-re.iam.gserviceaccount.com` | ABSENT |

Note: DM-43 Smoke 1 (`AsyncAnalyticsQueue`) successfully wrote 3 docs to the `analytics` DB
in `ken-e-dev` without this grant, which suggests dev may already have the role. Pre-flight
confirms. Either way the terraform change is worth landing — it declares the role under
terraform management so future drift is auto-corrected.

---

## Terraform Plan Guidance (Task 2)

After this PR merges into `deployment/terraform/variables.tf`, the operator runs:

```bash
cd deployment/terraform
terraform init
terraform plan -var-file=vars/env.tfvars -out=dm75-iam.tfplan
```

**Expected plan output:**

- For each env in the Task 1 ABSENT set: one `+ google_project_iam_member` for
  `roles/datastore.user` on the Agent Engine SA. N additions total (N = 1–3 depending
  on how many envs were ABSENT in pre-flight).
- Zero changes to the other 5 `agentengine_sa_roles` entries.
- Zero changes to any other terraform resource.

**STOP if the plan shows any `- delete` on an existing IAM binding** — that would indicate
unexpected drift on one of the other roles. Paste the plan output as a comment on DM-75
before applying.

---

## Terraform Apply (Task 3 — Operator)

```bash
cd deployment/terraform
terraform apply dm75-iam.tfplan
```

Post-apply verification (re-run the pre-flight command above; all 3 envs should now show
`roles/datastore.user` PRESENT):

| Env | Post-apply `roles/datastore.user` | Status |
|---|---|---|
| ken-e-dev | _paste output_ | ☐ |
| ken-e-staging | _paste output_ | ☐ |
| ken-e-production | _paste output_ | ☐ |

---

## Code Revert (Task 4 — Dev Team, this PR)

`analytics_service.py:_init_firestore_clients` changes:

| Before | After |
|---|---|
| `self.analytics_db = None` (unconditional, with TODO block) | `self.analytics_db = firestore.Client(project=self.project_id, database="analytics")` (restored in try-block) |
| Log: "analytics temporarily disabled" | Log: standard (no qualifier) |

The except-block fallback `self.analytics_db = None` at the original L77-81 is retained —
transient init failures still degrade gracefully.

`test_analytics_integration.py:233` comment reworded from "IAM guard" to "hermetic CI"
rationale (test logic unchanged; mock injection is still correct).

---

## Automated Gates (Post-Code-Revert)

```bash
cd /home/agent/workspace
uv run --project app/adk pytest \
  app/adk/agents/strategy_agent/tests/test_analytics_service.py \
  app/adk/agents/strategy_agent/tests/test_analytics_integration.py \
  app/adk/agents/strategy_agent/tests/test_async_analytics_queue.py -q
make lint
```

| Gate | Expected | Actual | Status |
|---|---|---|---|
| pytest analytics suite (26 tests) | 0 failures | _TBD_ | ☐ |
| `make lint` (0 new errors vs. main) | clean | _TBD_ | ☐ |

_(To be filled in after CI run; see PR automated test results section.)_

---

## Live Dev Smoke (Task 6 — after IAM grant lands in ken-e-dev)

**To be performed by Ken / Darshan after Task 3 is confirmed in dev.**

Reuses the DM-43 Smoke 2 pattern but **without the monkey-patch**:

```python
# /tmp/dm75_smoke.py  (mirrors /tmp/dm43_smoke.py structure)
import sys, importlib.util

# Load analytics_service directly to bypass the shared/secrets import collision
spec = importlib.util.spec_from_file_location(
    "analytics_service",
    "/home/agent/workspace/app/adk/agents/strategy_agent/analytics_service.py"
)
mod = importlib.util.module_from_spec(spec)

# Minimal stubs to satisfy imports
sys.modules.setdefault("shared", type(sys)("shared"))
sys.modules.setdefault("shared.account_id_utils", type(sys)("shared.account_id_utils"))
sys.modules["shared.account_id_utils"].validate_account_id = lambda x: x

# Load retry_utils stub
spec_r = importlib.util.spec_from_file_location(
    "retry_utils",
    "/home/agent/workspace/app/adk/agents/strategy_agent/retry_utils.py"
)

spec.loader.exec_module(mod)
AnalyticsService = mod.AnalyticsService

SMOKE_ACCOUNT = "dm75_smoke_ca"
PROJECT = "ken-e-dev"

svc = AnalyticsService(account_id=SMOKE_ACCOUNT, project_id=PROJECT)
# No monkey-patch — analytics_db must be live now
assert svc.analytics_db is not None, "FAIL: analytics_db is still None after IAM grant"

result = svc.aggregate_daily_costs()
print(f"aggregate_daily_costs result: {result}")

# Verify Shape B write
from google.cloud import firestore
db = firestore.Client(project=PROJECT, database="analytics")
coll = db.collection("accounts").document(SMOKE_ACCOUNT).collection("cost_aggregations")
docs = list(coll.stream())
print(f"Docs at accounts/{SMOKE_ACCOUNT}/cost_aggregations: {len(docs)}")
assert len(docs) >= 1, "FAIL: no cost_aggregations docs written"
print(f"total_cost: {docs[0].to_dict().get('total_cost', 0)}")

# Cleanup
for d in docs:
    d.reference.delete()
print("Cleanup done.")
```

Expected smoke output:

| Check | Expected | Actual | Status |
|---|---|---|---|
| `analytics_db` not None (no monkey-patch) | True | _paste_ | ☐ |
| Shape B doc at `accounts/dm75_smoke_ca/cost_aggregations/` | 1 | _paste_ | ☐ |
| `total_cost` field in doc | ≥ 0 | _paste_ | ☐ |
| Shape A docs at `cost_aggregations_dm75_smoke_ca` | 0 | _paste_ | ☐ |
| Cleanup: docs remaining after delete | 0 | _paste_ | ☐ |

Paste script output as part of the AC-4 audit-trail comment on DM-75.

---

## Acceptance Criteria Summary

| AC | Criterion | Status |
|---|---|---|
| AC-1 | Agent Engine SA has `roles/datastore.user` on all 3 envs | ☐ (operator) |
| AC-2 | TODO block removed; `self.analytics_db = firestore.Client(...)` restored; PR links DM-75 | ✅ (this PR) |
| AC-3 | Live dev smoke: `cost_aggregations` doc at Shape B path without monkey-patch | ☐ (operator, after AC-1) |
| AC-4 | Audit-trail comment on DM-75 with IAM bindings + smoke output | ☐ (operator, after AC-3) |
