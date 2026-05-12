# DM-29 — Dev Migration Run Log: `alert_configurations`

**Issue:** DM-29  
**Date:** 2026-05-12  
**Operator:** Dev Team agent (data-management-dev-team)  
**Script:** `api/scripts/migrate_to_shape_b.py --resource=alert_configurations`  
**Project:** `ken-e-dev` (Firestore database: `(default)`)  
**Branch:** `feat/DM-29-alert-configurations-dev-migration`

---

## Summary

Migration **executed successfully** on 2026-05-12. The `alert_configurations` Firestore
data has been moved from the root-level collection (`alert_configurations/{account_id}`)
to Shape B subcollections (`accounts/{account_id}/alert_configurations/default`).

**Counts:** 325 source docs migrated → 325 destination docs created and verified.

**Nested `alerts/` subcollection disposition:** 19 accounts had nested
`alert_configurations/{account_id}/alerts/` subcollections totalling 111 alert-history
docs. These are NOT in scope for DM-PRD-04 (not in the §4 call-site inventory —
`AlertManager` reads/writes `accounts/{id}/alert_configurations/default`, not `alerts/`).
They were **explicitly cleaned** via targeted `recursive_delete` per PRD §8 option (b)
immediately after `--confirm-delete`, rather than left as orphans that DM-PRD-05 would
not automatically reap (because DM-PRD-05's `recursive_delete(accounts/{account_id})`
targets the `accounts/` path, not the legacy `alert_configurations/` root collection).

**`AlertManager.load()` smoke check:** PASSED — live dev Firestore, returned payload
matching the pre-migration baseline.

---

## Task 1 — Pre-flight verification

**Timestamp:** 2026-05-12T07:54:36Z

**`migrate_to_shape_b.py --list` output:**

```
2026-05-12 07:54:51,907 INFO project_id=ken-e-dev database_id=(default)
agent_analytics -> accounts/{account_id}/agent_analytics
alert_configurations -> accounts/{account_id}/alert_configurations
cost_aggregations -> accounts/{account_id}/cost_aggregations
monitoring_topics -> accounts/{account_id}/monitoring_topics
performance_profiles -> accounts/{account_id}/performance_profiles
strategy_audit -> accounts/{account_id}/strategy_audit
strategy_docs -> accounts/{account_id}/strategy_docs
strategy_processing_state -> accounts/{account_id}/strategy_processing_state
```

Registry entry for `alert_configurations`:

```
MigrateConfig:
  old_prefix:                ''
  new_subcollection:         'alert_configurations'
  has_versions:              False
  source_is_single_collection: True
  destination_doc_id:        'default'
  is_field_migration:        False
```

**Pre-migration doc count:** 325 root-level `alert_configurations/{account_id}` docs.

**Baseline payload captured (spot-check account `acc_0130d61c010c4e10b9700a0508e82a2e`):**

```json
{
  "cooldown_minutes": 15,
  "thresholds": [
    {"percentage": 50, "severity": "info", "channels": ["logging"]},
    {"percentage": 75, "severity": "warning", "channels": ["logging", "firestore"]},
    {"percentage": 90, "severity": "error", "channels": ["logging", "firestore", "webhook"]},
    {"percentage": 95, "severity": "critical", "channels": ["logging", "firestore", "webhook", "email"]}
  ],
  "enabled": true,
  "notification_channels": {
    "webhook": {"enabled": false, "headers": {}, "url": null},
    "email": {"recipients": [], "enabled": false}
  },
  "circuit_breaker_enabled": true,
  "account_id": "acc_0130d61c010c4e10b9700a0508e82a2e",
  "circuit_breaker_threshold": 100
}
```

**Nested `alerts/` subcollection inventory (full scan):**
- 325 accounts scanned for `alert_configurations/{account_id}/alerts/` subcollections
- Found: **19 accounts** with nested `alerts/` subcollections, **111 total alert docs**
- See full account list in the "Nested `alerts/` subcollection disposition" section below

---

## Task 2 — Dry-run

**Timestamp:** 2026-05-12T07:54:53Z  
**Command:** `GOOGLE_CLOUD_PROJECT_ID=ken-e-dev python3 api/scripts/migrate_to_shape_b.py --resource=alert_configurations --dry-run`

**Output:**

```
2026-05-12 07:54:51,907 INFO project_id=ken-e-dev database_id=(default)
2026-05-12 07:54:53,252 INFO [alert_configurations] dry-run: walking single source collection: alert_configurations
Resource: alert_configurations
  Source collections found:   325
  Source doc count:            325
  Destination path:            accounts/{id}/alert_configurations
  Destination doc count:       0
  Status:                      DRY RUN
  Next step:                   re-run without --dry-run to copy
```

**Exit code:** 0

---

## Task 3 — Copy + verify

**Timestamp start:** 2026-05-12T07:55:09Z  
**Command:** `GOOGLE_CLOUD_PROJECT_ID=ken-e-dev python3 api/scripts/migrate_to_shape_b.py --resource=alert_configurations`

**Output:**

```
2026-05-12 07:55:09,946 INFO project_id=ken-e-dev database_id=(default)
2026-05-12 07:55:10,279 INFO [alert_configurations] Walking single source collection: alert_configurations
Resource: alert_configurations
  Source collections found:   325
  Source doc count:            325
  Destination path:            accounts/{id}/alert_configurations
  Destination doc count:       325
  Status:                      VERIFIED
  Next step:                   re-run with --confirm-delete
```

**Exit code:** 0

**Spot-check:** `accounts/acc_0130d61c010c4e10b9700a0508e82a2e/alert_configurations/default`
payload confirmed byte-equivalent to the Task 1 baseline JSON (same `circuit_breaker_threshold`,
`thresholds` array, `enabled`, `notification_channels`, `account_id`).

---

## Nested `alerts/` subcollection disposition

**Decision:** Explicit cleanup via targeted `recursive_delete` (PRD §8 option b).

**Rationale:**
- The nested `alert_configurations/{account_id}/alerts/` subcollections contain ≤24 h alert
  history written by `alert_manager.py:492-495`.
- These docs are **NOT** in the DM-PRD-04 §4 call-site inventory — `AlertManager` reads/writes
  `accounts/{id}/alert_configurations/default` only; it does not read `alerts/`.
- After `--confirm-delete` removes the parent docs, these subcollections would become orphaned
  at `alert_configurations/{account_id}/alerts/` — a legacy-root-collection location that
  DM-PRD-05's `recursive_delete(accounts/{account_id})` would NOT automatically reap
  (different path prefix).
- Leaving them as permanent dev-environment noise is unacceptable. Explicit cleanup is
  PRD §8 option (b) and leaves dev in a fully clean state.

**Accounts cleaned (19 total, 111 docs):**

| Account ID | Alert docs |
|---|---|
| acc_22fa05d223d7417aad5c625921349a26 | 4 |
| acc_237878648baf4760b10f7d1f67ea69df | 3 |
| acc_2c4092fbbeca45dd80a19bb3a6104151 | 4 |
| acc_31e60685df8e48eda36d477adb04183e | 20 |
| acc_5153f5f615564d75852abc1f7db71e24 | 4 |
| acc_5690646a47744bb689126d17ebc8107d | 3 |
| acc_5bad5c6ff92d41ae944b12fb09a716f7 | 5 |
| acc_738cd6fca8f040c1b5bca1b979dce793 | 6 |
| acc_a6dac30e64ea4a23970626867b0f1762 | 3 |
| acc_ad3d465334144dc796b6ad0186a93040 | 1 |
| acc_bf5d507ee4fc4ef99b5f21a767fedd26 | 3 |
| acc_c1097ae6de1847aba14d6c6f03ed2ce6 | 2 |
| acc_c36188bfb5504a94bf43a96e4d9fd886 | 4 |
| acc_ca85c0ce6b624c90ad7494f4c8d64f15 | 13 |
| acc_e0e6c476829843eeb9a2670337189bf6 | 3 |
| acc_e6a05499f9a54f4e8addc609c2f261f4 | 3 |
| acc_e7d378fd97724ba789c00f9cda4ff9a3 | 13 |
| acc_f5f6c7e53f8d45b3af9b45cb841e140e | 12 |
| acc_f7d92cc3ee8e4b119aca4e7c008bfb67 | 5 |

Cleanup method: `db.recursive_delete(db.collection("alert_configurations").document(account_id))`
executed for each account above, immediately after `--confirm-delete`.
Post-cleanup verification: 0 orphan `alerts/` docs remaining.

---

## Task 4 — Confirm-delete + post-delete assertion

**Timestamp:** 2026-05-12T07:56:28Z  
**Command:** `GOOGLE_CLOUD_PROJECT_ID=ken-e-dev python3 api/scripts/migrate_to_shape_b.py --resource=alert_configurations --confirm-delete --yes`

**Output:**

```
2026-05-12 07:56:28,245 INFO project_id=ken-e-dev database_id=(default)
2026-05-12 07:56:28,576 INFO [alert_configurations] Walking single source collection: alert_configurations
2026-05-12 07:56:46,757 WARNING [alert_configurations] --yes supplied: skipping interactive confirmation for deletion
2026-05-12 07:56:46,757 INFO [alert_configurations] Deleting source documents from single collection: alert_configurations
Resource: alert_configurations
  Source collections found:   325
  Source doc count:            325
  Destination path:            accounts/{id}/alert_configurations
  Destination doc count:       325
  Status:                      VERIFIED
  Next step:                   re-run with --confirm-delete
Resource: alert_configurations — deletion complete
  Source collections deleted: 325
  Total docs deleted:         325
```

**Exit code:** 0

**Post-delete assertion:** Root-level `alert_configurations` collection: **0 docs remaining**.

**Orphan cleanup result:** 19 accounts × targeted `recursive_delete` → 111 alert docs
removed. 0 orphan `alerts/` docs remaining after cleanup.

---

## Task 5 — Live `AlertManager.load()` smoke check

**Timestamp:** 2026-05-12T07:57:20Z  
**Account tested:** `acc_0130d61c010c4e10b9700a0508e82a2e` (same account as Task 1 baseline)

**Invocation:**

```python
import json, os
os.environ["GOOGLE_CLOUD_PROJECT_ID"] = "ken-e-dev"
from app.adk.agents.strategy_agent.alert_manager import AlertManager
account_id = "acc_0130d61c010c4e10b9700a0508e82a2e"
mgr = AlertManager(account_id=account_id, project_id="ken-e-dev")
config = mgr.load()
print(f"AlertManager.load() returned: {json.dumps(config, indent=2, default=str)}")
assert config
assert config.get("account_id") == account_id
print("SMOKE CHECK PASSED")
```

**Output:**

```json
{
  "circuit_breaker_enabled": true,
  "notification_channels": {
    "webhook": {"enabled": false, "headers": {}, "url": null},
    "email": {"enabled": false, "recipients": []}
  },
  "enabled": true,
  "circuit_breaker_threshold": 100,
  "cooldown_minutes": 15,
  "thresholds": [
    {"severity": "info", "percentage": 50, "channels": ["logging"]},
    {"severity": "warning", "percentage": 75, "channels": ["logging", "firestore"]},
    {"severity": "error", "percentage": 90, "channels": ["logging", "firestore", "webhook"]},
    {"severity": "critical", "percentage": 95, "channels": ["logging", "firestore", "webhook", "email"]}
  ],
  "account_id": "acc_0130d61c010c4e10b9700a0508e82a2e"
}
SMOKE CHECK PASSED
```

**Exit code:** 0  
**Parity vs. Task 1 baseline:** All fields match (`circuit_breaker_threshold`, `thresholds` array, `enabled`, `account_id`, `cooldown_minutes`, `notification_channels`).

---

## Task 6 — Idempotency re-run

**Timestamp:** 2026-05-12T07:57:35Z  
**Command:** `GOOGLE_CLOUD_PROJECT_ID=ken-e-dev python3 api/scripts/migrate_to_shape_b.py --resource=alert_configurations`

**Output:**

```
2026-05-12 07:57:35,352 INFO project_id=ken-e-dev database_id=(default)
2026-05-12 07:57:35,678 INFO [alert_configurations] Walking single source collection: alert_configurations
Resource: alert_configurations
  Source collections found:   0
  Source doc count:            0
  Destination path:            accounts/{id}/alert_configurations
  Destination doc count:       0
  Status:                      VERIFIED
  Next step:                   re-run with --confirm-delete
```

**Exit code:** 0 — idempotent no-op (source already empty, nothing to copy).

---

## Task 7 — Mocked unit tests (code-path correctness)

All tests pass (run on branch, DM-25 mocked round-trip included):

```
20 passed in 2.10s  [test_alert_manager.py]
79 passed in 2.72s  [test_migrate_to_shape_b.py]
```

Including `alert_configurations` registry assertions:

- `TestShapeBLikeResourcesRegistry::test_alert_configurations_registered` PASSED
- `TestShapeBLikeResourcesRegistry::test_alert_configurations_source_is_single_collection` PASSED
- `TestShapeBLikeResourcesRegistry::test_alert_configurations_destination_doc_id` PASSED
- `TestShapeBLikeResourcesRegistry::test_alert_configurations_has_no_versions` PASSED
- `TestShapeBLikeResourcesRegistry::test_alert_configurations_full_config` PASSED

---

## AC verification status

| AC | Description | Status |
|----|-------------|--------|
| AC-1 | Root-level `alert_configurations` collection empty/deleted in dev | VERIFIED — 0 docs remaining |
| AC-2 | `accounts/{id}/alert_configurations/default` populated for all pre-migration accounts | VERIFIED — 325/325 docs migrated |
| AC-3 | `AlertManager(account_id=…).load()` succeeds against migrated data | VERIFIED — SMOKE CHECK PASSED, payload matches baseline |
| AC-4 | Re-running `--resource=alert_configurations` is a no-op | VERIFIED — idempotency re-run: Source collections found: 0 |
| DM-25 mocked test | Mocked round-trip (`test_load_save_round_trip`) passes | VERIFIED — 20/20 tests pass |

---

## Environment

- **VM:** `fun-e-agent-vm@fun-e-business.iam.gserviceaccount.com` (GCE, cloud-platform scope)
- **Target Firestore project:** `ken-e-dev`
- **Firestore access from VM:** GRANTED (`roles/datastore.user` — confirmed 2026-05-12)
- **Migration timing:** dry-run ~1s; copy+verify ~36s for 325 docs; confirm-delete ~18s
