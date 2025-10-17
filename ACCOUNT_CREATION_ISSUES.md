# Account Creation Issues

This document tracks issues identified with the account creation flow that need to be addressed.

---

## Issue 1: Initial Activities Not Created During Account Creation

### Problem Description

When a new account is created, Activity nodes are not being created in Neo4j, even though the `_create_initial_activities()` function exists and is designed to create them.

**Root Cause:** The call to `_create_initial_activities()` was **accidentally removed** during a refactoring that extracted account creation logic into a separate service.

### Investigation Details

#### Git History Analysis

1. **Original Implementation (commit `50918e4`):**
   - Commit: `feat(api): auto-create initial activities on account creation`
   - Date: Thu Jul 24 09:35:39 2025
   - The `_create_initial_activities()` function was added to [accounts.py](api/src/kene_api/routers/accounts.py)
   - It was properly called in the `create_account` endpoint:
     ```python
     # Create initial activities for the new account
     activities_created = await _create_initial_activities(db, firestore, account_id)
     if activities_created > 0:
         logger.info(
             f"Successfully created {activities_created} initial activities for account {account_id}"
         )
     ```

2. **Refactoring (commit `0c2580b`):**
   - Commit: `feat: implement real-time progress tracking for account creation`
   - Date: Sat Aug 30 22:13:14 2025
   - Created `account_service.py` with `create_account_internal()` function
   - Moved account creation logic from the router to the service
   - **The call to `_create_initial_activities()` was NOT migrated to the new service**
   - This was an oversight during the refactoring

#### Current State

- **Function location:** [api/src/kene_api/routers/accounts.py:347-428](api/src/kene_api/routers/accounts.py#L347-428)
- **Function status:** Defined but never called
- **Service location:** [api/src/kene_api/services/account_service.py:40-360](api/src/kene_api/services/account_service.py#L40-360)
- **Missing call:** No invocation of `_create_initial_activities()` in `create_account_internal()`

#### What the Function Does

The `_create_initial_activities()` function:
- Fetches activity templates from Firestore's `initial-activities` collection
- Creates Activity nodes in Neo4j with appropriate properties:
  - `activity_id`
  - `activity_name`
  - `activity_description`
  - `expected_impact`
  - `internal` (boolean)
  - `known_activity` (boolean)
- Creates `BELONGS_TO` relationships linking activities to the account
- Uses batch creation via `UNWIND` for efficiency
- Returns the count of activities created
- Has proper error handling (returns 0 on failure without failing account creation)

### Recommended Solution

**Restore the missing function call** by adding it to `create_account_internal()` after the account is created in Neo4j but before creating activity logs.

**Location:** [api/src/kene_api/services/account_service.py](api/src/kene_api/services/account_service.py) around line 253-268

**Implementation:**

Insert after line 252 (after account creation verification) and before line 256 (before "Create initial activity logs"):

```python
# Create initial activities from Firestore templates
try:
    from ..routers.accounts import _create_initial_activities

    activities_count = await _create_initial_activities(
        db=neo4j_service, firestore=firestore, account_id=account_id
    )
    logger.info(
        f"[ACCOUNT_CREATION] Created {activities_count} initial activities"
    )
except Exception as e:
    logger.error(f"[ACCOUNT_CREATION] Failed to create initial activities: {e}")
    # Don't fail account creation if initial activities fail
```

### Why This Order?

The activities should be created **before** activity logs because:
1. Activity logs have a `LOGGED` relationship pointing to Activity nodes
2. The `_create_initial_activity_logs()` function (line 431-539 in accounts.py) expects regional holiday activities to exist
3. Creating activities first ensures the relationship targets exist when logs are created

### Alternative: Better Architecture

Consider moving `_create_initial_activities()` from the router file to the service module for better code organization:
1. Move the function to `account_service.py` or a separate `activity_service.py`
2. This avoids importing from routers into services (which is generally an anti-pattern)
3. Keeps related business logic together

### Testing Checklist

After implementing the fix:
- [ ] Create a new test account via the API
- [ ] Verify Activity nodes appear in Neo4j with query:
  ```cypher
  MATCH (a:Activity)-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
  RETURN a
  ```
- [ ] Check that activities match the templates in the `initial-activities` Firestore collection
- [ ] Verify `BELONGS_TO` relationships are created correctly
- [ ] Confirm account creation still succeeds even if activity creation fails
- [ ] Test that activity logs can be created successfully after activities exist

### Related Files

- [api/src/kene_api/routers/accounts.py:347-428](api/src/kene_api/routers/accounts.py#L347-428) - Contains `_create_initial_activities()` function
- [api/src/kene_api/routers/accounts.py:431-539](api/src/kene_api/routers/accounts.py#L431-539) - Contains `_create_initial_activity_logs()` function (depends on activities existing)
- [api/src/kene_api/services/account_service.py:40-360](api/src/kene_api/services/account_service.py#L40-360) - Contains `create_account_internal()` function (needs the fix)
- [api/scripts/add_act_00_to_firestore.py](api/scripts/add_act_00_to_firestore.py) - Script to populate initial activities in Firestore

### Impact

**Severity:** High - Core functionality broken

**User Impact:**
- New accounts are created without initial activity templates
- Holiday activity logs cannot be created properly (missing activity targets)
- Users must manually create activities that should be automatic

**Data Impact:**
- Existing accounts created after commit `0c2580b` are missing initial activities
- May need a backfill script to add activities to affected accounts

---

## Issue 2: Python Version Constraint Not Documented

**Severity:** Medium

**Change:** `api/pyproject.toml`
```python
-requires-python = ">=3.12"
+requires-python = ">=3.12,<3.13"
```

**Problem:**
- Python 3.13 is explicitly blocked
- No documentation explaining why
- No timeline for when 3.13 support will be added

**Recommendation:**
- Add comment in `pyproject.toml` explaining constraint
- Document in `CLAUDE.md` if this is a long-term limitation
- Track 3.13 compatibility as a future task

---

## Issue 3: Circular Import Workaround in main.py

**Severity:** Low (but indicates design smell)

**Change:** `api/src/kene_api/main.py`
```python
from .routers import (
    accounts,
    activities,
    # ... many routers ...
)
# Separated import - why?
from .routers import (
    notifications_v2 as notifications,
)
```

**Problem:**
- Import separated from others suggests circular dependency
- Workaround rather than proper fix
- Makes code harder to understand

**Recommendation:**
- Investigate root cause of circular dependency
- Refactor to eliminate the cycle
- Document why separation is needed if unavoidable

---

## Issue 4: Secret Manager API Changes Without Migration Guide

**Severity:** Medium

**Changes:**
- Removed `secret_manager.py` with `get_env_var_or_secret()`
- Added `utils/secrets.py` with `get_env_or_secret()`
- Changed error handling behavior

**Example in `api/src/kene_api/email_service.py`:**
```python
# Old (allows graceful failure):
self.api_key = get_env_var_or_secret("SENDGRID_API_KEY", allow_failure=False)

# New (different error handling):
self.api_key = get_env_or_secret("SENDGRID_API_KEY")
```

**Concerns:**
- Error handling changed from explicit `allow_failure` parameter to implicit behavior
- No migration guide for updating existing code
- Need to verify all callsites have appropriate try/catch

**Recommendation:**
- Document breaking changes in PR description
- Add migration notes for Secret Manager API
- Verify all callsites handle errors correctly

---

## Issue 5: Test Coverage Gaps

**Severity:** High

**Removed tests:**
- `test_artifact_utils.py` (266 lines)
- `test_async_analytics_integration.py` (324 lines)
- `test_async_enabled.py` (148 lines)
- Various other test files

**Added tests:**
- `tests/neo4j/test_brand_neo4j.py` (352 lines)
- `tests/neo4j/test_business_neo4j.py` (547 lines)

**Concerns:**
- Net test coverage change unclear
- Old tests removed without clear replacement
- **No integration test for account creation flow** (would have caught Issue #1)
- Risk of additional undiscovered regressions

**Recommendation:**
- Add comprehensive integration test for account creation:
  ```python
  async def test_create_account_creates_initial_activities():
      # Create account
      account = await create_account(...)

      # Verify activities exist
      activities = await neo4j.execute_query(
          "MATCH (a:Activity)-[:BELONGS_TO]->(acc:Account {account_id: $id}) RETURN a",
          {"id": account.account_id}
      )
      assert len(activities) > 0
  ```
- Document why old tests were removed
- Run full test suite before merge

---

## Action Items for Developer

### Must Fix Before Merge (Blockers)

1. ❌ **Fix Issue #1: Add `_create_initial_activities()` call**
   - Location: `api/src/kene_api/services/account_service.py:253`
   - Implementation shown in Issue #1 above
   - Add integration test to prevent regression

2. ❌ **Comprehensive Testing**
   - Run full integration test suite
   - Manual QA of account creation end-to-end
   - Verify Neo4j graph structure is correct
   - Test email notifications

3. ❌ **Document Python 3.13 constraint**
   - Add comment in `pyproject.toml`
   - Explain reason and timeline for 3.13 support

### Should Fix (High Priority)

4. ⚠️ **Add integration test for account creation**
   - Test full flow including activities
   - Verify graph structure
   - Check error handling

5. ⚠️ **Document Secret Manager migration**
   - Breaking changes in API
   - Migration guide for existing code
   - Error handling differences

6. ⚠️ **Investigate circular import in main.py**
   - Document workaround reason
   - Or refactor to eliminate cycle

7. ⚠️ **Verify Neo4j indexes**
   - Ensure indexes exist for performance
   - Document index creation in deployment

---

