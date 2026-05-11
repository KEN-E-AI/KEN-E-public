# DM-29 — Dev Migration Run Log: `alert_configurations`

**Issue:** DM-29  
**Date:** 2026-05-11  
**Operator:** Dev Team agent (data-management-dev-team)  
**Script:** `api/scripts/migrate_to_shape_b.py --resource=alert_configurations`  
**Project:** `ken-e-dev` (Firestore database: `(default)`)  
**Branch:** `feat/DM-29-alert-configurations-dev-migration`

---

## Summary

The Dev Team VM (`fun-e-agent-vm@fun-e-business.iam.gserviceaccount.com`) does not have
Firestore read/write permissions on the `ken-e-dev` project. The migration script cannot
connect to the target Firestore instance from this VM. This is the environmental constraint
identified in the implementation plan's risk table (Risk: "gcloud credentials in the Dev
Team VM are not configured for `ken-e-dev`").

**This run log documents:**

1. Everything verified from the VM before the Firestore access block.
2. The exact operator runbook to complete the migration from a machine with `ken-e-dev` access.
3. The results of the mocked unit test suite (proves code-path correctness).
4. The outcome the Test Team must verify once an operator runs the runbook.

---

## Task 1 — Pre-flight verification

**Timestamp:** 2026-05-11T07:41:00Z  
**`migrate_to_shape_b.py --list` output:**

```
2026-05-11 07:44:54,936 INFO project_id=ken-e-dev database_id=(default)
agent_analytics -> accounts/{account_id}/agent_analytics
alert_configurations -> accounts/{account_id}/alert_configurations
cost_aggregations -> accounts/{account_id}/cost_aggregations
monitoring_topics -> accounts/{account_id}/monitoring_topics
performance_profiles -> accounts/{account_id}/performance_profiles
strategy_audit -> accounts/{account_id}/strategy_audit
strategy_docs -> accounts/{account_id}/strategy_docs
strategy_processing_state -> accounts/{account_id}/strategy_processing_state
```

`alert_configurations` is registered (DM-22 confirmed). Registry entry:

```
MigrateConfig:
  old_prefix:                ''
  new_subcollection:         'alert_configurations'
  has_versions:              False
  source_is_single_collection: True
  destination_doc_id:        'default'
  is_field_migration:        False
```

**Migration semantics:**

- Source: `alert_configurations/{account_id}` — root-level collection; doc-id IS the `account_id`
- Destination: `accounts/{account_id}/alert_configurations/default`

**Firestore connectivity check:**

```
gcloud auth application-default print-access-token  → SUCCESS (VM has a valid token)
Firestore Client(project="ken-e-dev").collection("alert_configurations").stream()
  → google.api_core.exceptions.PermissionDenied: 403 Missing or insufficient permissions.
```

**Pre-flight verdict:** BLOCKED — credentials exist but the VM service account
(`fun-e-agent-vm@fun-e-business.iam.gserviceaccount.com`) is not granted Firestore
access on `ken-e-dev`. Tasks 2–6 cannot run from this VM.

---

## Tasks 2–6 — Migration runbook (to be executed by an operator with `ken-e-dev` access)

The operator must run the following sequence from a machine (or Cloud Shell) authenticated
with a principal that has `roles/datastore.user` on `ken-e-dev`. The script is already
deployed to the repo root; no additional code changes are needed.

```bash
# 0. Set environment
export GOOGLE_CLOUD_PROJECT_ID=ken-e-dev
export FIRESTORE_DATABASE_ID='(default)'

cd /path/to/KEN-E  # repo root

# 1. Sanity check — confirm registry shows alert_configurations
python api/scripts/migrate_to_shape_b.py --list
# Expected: "alert_configurations -> accounts/{account_id}/alert_configurations"

# 2. Task 2 — Dry-run (no writes)
python api/scripts/migrate_to_shape_b.py --resource=alert_configurations --dry-run
# Expected:
#   Resource: alert_configurations
#     Source collections found:   N       (N ≥ 0)
#     Source doc count:            N
#     Destination path:            accounts/{id}/alert_configurations
#     Destination doc count:       0
#     Status:                      DRY RUN
#
# If N == 0: root collection is already empty or was never populated.
# AC-2 is vacuously satisfied; skip Task 3 + 4 and proceed to Task 5.

# 3. Task 3 — Copy + verify (non-destructive; source untouched)
python api/scripts/migrate_to_shape_b.py --resource=alert_configurations
# Expected:
#   Resource: alert_configurations
#     Source collections found:   N
#     Source doc count:            N
#     Destination path:            accounts/{id}/alert_configurations
#     Destination doc count:       N
#     Status:                      VERIFIED
#     Next step:                   re-run with --confirm-delete
#
# If exit code is 1 (FAILED): inspect per-account mismatch lines in stderr.
# Do NOT proceed to Task 4 until exit code is 0 (VERIFIED).

# 4a. Spot-check (Firestore console or gcloud CLI)
#   For one sampled account_id from the dry-run output:
#   Confirm accounts/{account_id}/alert_configurations/default exists
#   and its payload matches the original alert_configurations/{account_id} doc.

# 4b. Task 4 — Confirm-delete legacy + assert root collection empty
python api/scripts/migrate_to_shape_b.py --resource=alert_configurations --confirm-delete --yes
# Expected: exit code 0; runner deletes all root-level alert_configurations/{account_id} docs.
#
# Known carve-out (PRD §8 Risks): nested alert_configurations/{account_id}/alerts/*
# subcollection docs (24 h alert history written by alert_manager.py:492-495) are NOT
# cascade-deleted by batch.delete(doc.reference). These remain as orphans under the
# now-empty parent ref. Record the count below; DM-PRD-05's recursive_delete will reap
# them when account deletion fires.
#
# Post-delete assertion:
gcloud firestore documents list \
  --collection="alert_configurations" \
  --project=ken-e-dev \
  --database='(default)' 2>&1
# Expected: empty or zero documents listed.

# 5. Task 5 — Live AlertManager.load() smoke check
#   Replace <ACCOUNT_ID> with any account that had an alert_configurations/{account_id} doc.
python - <<'PYEOF'
import os, json
os.environ["GOOGLE_CLOUD_PROJECT_ID"] = "ken-e-dev"
from app.adk.agents.strategy_agent.alert_manager import AlertManager

account_id = "<ACCOUNT_ID>"   # ← replace with a real account ID, e.g. "acc_abc123ef"
if account_id.startswith("<"):
    raise SystemExit("ERROR: replace <ACCOUNT_ID> with a real account ID before running")
mgr = AlertManager(account_id=account_id, project_id="ken-e-dev")
config = mgr.load()
print(f"AlertManager.load() returned: {json.dumps(config, indent=2, default=str)}")
assert config, "load() returned falsy — check Firestore path"
if config.get("account_id") is not None:
    assert config.get("account_id") == account_id, (
        f"account_id mismatch: expected {account_id!r}, got {config.get('account_id')!r}"
    )
print("SMOKE CHECK PASSED")
PYEOF
# Expected: non-empty dict; no exception; "SMOKE CHECK PASSED"

# 6. Task 6 — Idempotency re-run
python api/scripts/migrate_to_shape_b.py --resource=alert_configurations
# Expected after --confirm-delete:
#   Source collections found:   0   (nothing left to copy)
#   Source doc count:            0
#   Status:                      VERIFIED
#   (idempotent no-op)
```

---

## Task 5 — Mocked unit test (code-path correctness — VM-executable)

The DM-25 mocked round-trip test (`test_alert_manager.py::test_load_save_round_trip`)
was run from this VM to confirm the Shape B path is correctly implemented:

```
app/adk/agents/strategy_agent/tests/test_alert_manager.py::test_load_save_round_trip PASSED
```

**Full test suite result:**

```
20 passed in 2.10s
```

All 20 `test_alert_manager.py` tests pass, including:

- `test_alert_manager_initialization` — `AlertManager.__init__` calls `collection("accounts/{account_id}/alert_configurations")`
- `test_load_save_round_trip` — `save()`/`load()` round-trip verifies Shape B path end-to-end (mocked)
- `test_alert_manager_rejects_invalid_account_id[*]` — 5 parameterized cases

The `test_load_save_round_trip` test asserts:

```python
assert any(
    "accounts/test_acct_xyz/alert_configurations" in c for c in collection_calls
), ...
```

confirming `collection()` is called with the correct Shape B path on both `save()` and `load()`.

Additionally, the migration script unit tests (`test_migrate_to_shape_b.py`) all pass:

```
79 passed in 2.72s
```

Including the `alert_configurations` registry assertions:

- `TestShapeBLikeResourcesRegistry::test_alert_configurations_registered` PASSED
- `TestShapeBLikeResourcesRegistry::test_alert_configurations_source_is_single_collection` PASSED
- `TestShapeBLikeResourcesRegistry::test_alert_configurations_destination_doc_id` PASSED
- `TestShapeBLikeResourcesRegistry::test_alert_configurations_has_no_versions` PASSED
- `TestShapeBLikeResourcesRegistry::test_alert_configurations_full_config` PASSED

---

## Known carve-out: `alert_configurations/{account_id}/alerts/*` orphans

Per DM-PRD-04 §8 Risks, the runner's `--confirm-delete` step uses `batch.delete(doc.reference)`
which does **not** cascade-delete Firestore subcollections. Any docs at
`alert_configurations/{account_id}/alerts/` (≤24 h alert history, per `alert_manager.py:492-495`)
survive as orphans under the now-empty parent ref.

These are acceptable per PRD §8 ("alert history is at most 24 h old by design"). DM-PRD-05's
eventual `recursive_delete(accounts/{account_id})` will reap them when account deletion fires.

**Operator action:** record the orphan count here once Task 4 runs:

```
Orphan alerts/ docs: ___  (fill in after --confirm-delete)
```

---

## AC verification status

| AC | Description | Status |
|----|-------------|--------|
| AC-1 | Root-level `alert_configurations` collection empty/deleted in dev | PENDING OPERATOR RUN |
| AC-2 | `accounts/{id}/alert_configurations/default` populated for every pre-migration account | PENDING OPERATOR RUN |
| AC-3 | `AlertManager(account_id=…).load()` succeeds against migrated data | Code-path verified (mocked). Live check pending operator run. |
| AC-4 | Re-running `--resource=alert_configurations` is a no-op | PENDING OPERATOR RUN |
| DM-25 mocked test | Mocked round-trip (`test_load_save_round_trip`) passes | VERIFIED (20/20 tests pass) |

---

## Environment

- **VM:** `fun-e-agent-vm@fun-e-business.iam.gserviceaccount.com` (GCE, cloud-platform scope)
- **Target Firestore project:** `ken-e-dev`
- **Firestore access from VM:** DENIED (403 PERMISSION_DENIED)
- **Alternative needed:** Cloud Shell or a machine with `roles/datastore.user` on `ken-e-dev`
- **Emulator availability:** Firestore emulator requires Java (not available on VM)
- **Docker:** not available on VM
