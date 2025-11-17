# Permission System Cleanup Recommendation

## Executive Summary

The current permission system has unnecessary complexity due to backward compatibility code for a migration that was never completed. This document provides a phased approach to simplify the codebase by removing legacy permission structures and consolidating to a single canonical format.

**Impact**: Reduces technical debt, improves maintainability, eliminates three-way fallback logic, and removes confusing variable naming.

**Timeline**: 3 phases over 2-3 weeks (can be adjusted based on priorities)

---

## Problem Statement

### Current Complexity

The permission system currently maintains **three different permission sources** with confusing fallback logic:

1. **`permissions.accounts`** (OLD structure - deprecated)
   - Only read for backward compatibility
   - No longer written to
   - Still created on new user initialization

2. **`permissions.account_permissions`** (NEW structure - canonical)
   - Actively written by all permission grant/revoke operations
   - Contains account-level permissions (view/edit)

3. **`accessible_accounts`** (Legacy list)
   - Fallback mechanism for view-only users
   - Unclear ownership and maintenance

### Code Locations Affected

#### 1. UserContext Model
**File**: `api/src/kene_api/auth/models.py`

```python
# Lines 13-19: Three permission fields
accessible_accounts: list[str]
permissions: dict[str, str]  # OLD - marked deprecated but still used
organization_permissions: dict[str, str]
account_permissions: dict[str, str] = field(default_factory=dict)  # NEW
```

**Three-way fallback logic** in `has_account_access()` method (lines 70-92):
```python
# Check 1: account_permissions (NEW)
if account_id not in self.account_permissions:
    # Check 2: permissions (OLD)
    if account_id in self.permissions:
        return True
    # Check 3: accessible_accounts (Legacy list)
    if account_id in self.accessible_accounts:
        if not required_roles or "view" in required_roles:
            return True
```

**Also affected**: `has_account_permission()` method (lines 132-136) has similar fallback.

#### 2. User Context Building
**File**: `api/src/kene_api/auth/user_context.py`

**Lines 224-252** - Confusing variable naming:
```python
permissions = user_data.get("permissions", {})
account_permissions = permissions.get("accounts", {})  # Gets OLD data!
organization_permissions = permissions.get("organizations", {})
account_level_permissions = permissions.get("account_permissions", {})  # Gets NEW data!

# ... later ...
return UserContext(
    permissions=account_permissions,  # OLD assigned to 'permissions'
    account_permissions=account_level_permissions,  # NEW assigned to 'account_permissions'
)
```

**Lines 176-190** - New user creation uses OLD structure:
```python
user_data = {
    "permissions": {
        "accounts": {},  # Creates OLD empty structure
        "organizations": {},
    },
}
```

#### 3. Dependencies (Optional User)
**File**: `api/src/kene_api/auth/dependencies.py`

**Lines 64-73** - Merging logic:
```python
old_accounts = permissions.get("accounts", {})
new_account_permissions = permissions.get("account_permissions", {})
# New structure takes precedence if account exists in both
user_context.account_permissions = {
    **old_accounts,
    **new_account_permissions,
}
```

#### 4. Permission Grants (NEW structure used)
**Files**: Multiple files write to NEW structure only:
- `api/src/kene_api/routers/accounts.py:1362`
- `api/src/kene_api/routers/firestore.py:2419, 2545, 3024`

Example:
```python
field_path=f"permissions.account_permissions.{account_id}"
```

### Critical Issues Identified

1. **Inconsistent Initialization**: New users created with OLD structure (`permissions.accounts: {}`), but permissions granted to NEW structure (`permissions.account_permissions`)

2. **Confusing Variable Names**:
   - `account_permissions` variable holds OLD data
   - `account_level_permissions` variable holds NEW data
   - This is backwards and confusing

3. **Multiple Code Paths**: Three fallback mechanisms increase debugging complexity and risk of inconsistent behavior

4. **No Migration Timeline**: Code comments say "deprecated" and "backward compatibility" but no concrete plan to remove

5. **Unused Field Creation**: Every new user gets an empty `permissions.accounts: {}` field that is never used

---

## Recommended Solution: Phased Migration Approach

### Canonical Structure (Target State)

```json
{
  "uid": "user_123",
  "email": "user@example.com",
  "permissions": {
    "organizations": {
      "org_123": "admin",
      "org_456": "view"
    },
    "account_permissions": {
      "acc_123": "edit",
      "acc_456": "view"
    }
  }
}
```

**Removed**:
- `permissions.accounts` (OLD structure)
- `accessible_accounts` field from UserContext

**Retained**:
- `permissions.organizations` (organization-level roles)
- `permissions.account_permissions` (account-level permissions)

---

## Phase 1: Data Migration (Week 1)

**Goal**: Migrate all existing Firestore user documents to use only the NEW structure.

### Tasks

#### 1.1 Create Migration Script

**Create**: `api/scripts/migrate_permissions.py`

```python
"""Migration script to consolidate permission structures.

Migrates from:
  permissions.accounts -> permissions.account_permissions

This script:
1. Reads all user documents
2. Merges permissions.accounts into permissions.account_permissions
3. Deletes permissions.accounts field
4. Logs migration results
"""

import asyncio
from google.cloud import firestore
from google.cloud.firestore_v1 import DELETE_FIELD

async def migrate_user_permissions():
    """Migrate all users from old to new permission structure."""
    db = firestore.Client()
    users_ref = db.collection("users")

    migrated_count = 0
    skipped_count = 0
    error_count = 0

    # Get all users
    users = users_ref.stream()

    for user_doc in users:
        user_id = user_doc.id
        user_data = user_doc.to_dict()

        permissions = user_data.get("permissions", {})
        old_accounts = permissions.get("accounts", {})
        new_account_permissions = permissions.get("account_permissions", {})

        # Skip if no migration needed
        if not old_accounts:
            skipped_count += 1
            continue

        try:
            # Merge: NEW structure takes precedence
            merged_permissions = {**old_accounts, **new_account_permissions}

            # Update Firestore
            users_ref.document(user_id).update({
                "permissions.account_permissions": merged_permissions,
                "permissions.accounts": DELETE_FIELD,
            })

            migrated_count += 1
            print(f"✓ Migrated user {user_id}: {len(old_accounts)} old + {len(new_account_permissions)} new = {len(merged_permissions)} total")

        except Exception as e:
            error_count += 1
            print(f"✗ Error migrating user {user_id}: {e}")

    print(f"\n=== Migration Complete ===")
    print(f"Migrated: {migrated_count}")
    print(f"Skipped: {skipped_count}")
    print(f"Errors: {error_count}")

if __name__ == "__main__":
    asyncio.run(migrate_user_permissions())
```

#### 1.2 Run Migration

**Execute in each environment** (development → staging → production):

```bash
# Development
GOOGLE_CLOUD_PROJECT_ID=ken-e-dev python api/scripts/migrate_permissions.py

# Staging
GOOGLE_CLOUD_PROJECT_ID=ken-e-staging python api/scripts/migrate_permissions.py

# Production (with backup first!)
GOOGLE_CLOUD_PROJECT_ID=ken-e-prod python api/scripts/migrate_permissions.py
```

#### 1.3 Verify Migration

Create verification script: `api/scripts/verify_migration.py`

```python
"""Verify that all users have been migrated."""

from google.cloud import firestore

def verify_migration():
    db = firestore.Client()
    users = db.collection("users").stream()

    users_with_old_structure = []

    for user_doc in users:
        user_data = user_doc.to_dict()
        permissions = user_data.get("permissions", {})

        if "accounts" in permissions:
            users_with_old_structure.append(user_doc.id)

    if users_with_old_structure:
        print(f"❌ Found {len(users_with_old_structure)} users with old structure:")
        for user_id in users_with_old_structure:
            print(f"   - {user_id}")
    else:
        print("✅ All users migrated successfully!")

if __name__ == "__main__":
    verify_migration()
```

**Deliverables**:
- [ ] Migration script created and tested
- [ ] Migration run in development environment
- [ ] Migration verified in development
- [ ] Migration run in staging environment
- [ ] Migration verified in staging
- [ ] Migration run in production environment (with backup)
- [ ] Migration verified in production

---

## Phase 2: Code Cleanup (Week 2)

**Goal**: Remove all backward compatibility code and simplify permission checking logic.

### Tasks

#### 2.1 Update UserContext Model

**File**: `api/src/kene_api/auth/models.py`

**Changes**:
1. Remove `permissions` field (line 13-15)
2. Remove `accessible_accounts` field (line 12)
3. Simplify `has_account_access()` method (remove fallback logic)
4. Simplify `has_account_permission()` method (remove fallback logic)

**Before** (lines 13-19):
```python
accessible_accounts: list[str]
permissions: dict[str, str]  # account_id -> role (deprecated, for backward compatibility)
organization_permissions: dict[str, str]  # organization_id -> role
account_permissions: dict[str, str] = field(default_factory=dict)
```

**After**:
```python
organization_permissions: dict[str, str]  # organization_id -> role
account_permissions: dict[str, str] = field(default_factory=dict)  # account_id -> edit|view
```

**Before** (lines 70-92 in `has_account_access`):
```python
# Check explicit account permissions for view-role users
if account_id not in self.account_permissions:
    logger.debug(f"[has_account_access] Account {account_id} NOT in account_permissions")
    # Backward compatibility: check old permissions dict
    if account_id in self.permissions:
        logger.debug(f"[has_account_access] Account {account_id} found in old permissions")
        return True
    # Check if account is in accessible_accounts (fallback for view-only users)
    if account_id in self.accessible_accounts:
        logger.debug(f"[has_account_access] Account {account_id} found in accessible_accounts")
        if not required_roles or "view" in required_roles:
            return True
    logger.warning(f"[has_account_access] Account {account_id} not found in any permissions")
    return False
```

**After**:
```python
# Check explicit account permissions
if account_id not in self.account_permissions:
    logger.warning(f"[has_account_access] Account {account_id} not in account_permissions")
    return False
```

**Before** (lines 132-137 in `has_account_permission`):
```python
account_perm = self.account_permissions.get(account_id)
if not account_perm:
    # Backward compatibility: check old permissions dict
    if account_id in self.permissions:
        return True
    return False
```

**After**:
```python
account_perm = self.account_permissions.get(account_id)
if not account_perm:
    return False
```

#### 2.2 Update User Context Building

**File**: `api/src/kene_api/auth/user_context.py`

**Lines 224-252** - Fix confusing variable naming and remove OLD structure handling:

**Before**:
```python
permissions = user_data.get("permissions", {})
account_permissions = permissions.get("accounts", {})  # OLD
organization_permissions = permissions.get("organizations", {})
account_level_permissions = permissions.get("account_permissions", {})  # NEW

# Debug logging
logger.debug(f"[create_user_context] account_permissions (old 'accounts'): {account_permissions}")
logger.debug(f"[create_user_context] account_level_permissions (new 'account_permissions'): {account_level_permissions}")

all_accessible_accounts = set(account_permissions.keys())
all_accessible_accounts.update(account_level_permissions.keys())

return UserContext(
    user_id=user_id,
    email=email,
    accessible_accounts=list(all_accessible_accounts),
    permissions=account_permissions,
    organization_permissions=organization_permissions,
    account_permissions=account_level_permissions,
)
```

**After**:
```python
permissions = user_data.get("permissions", {})
organization_permissions = permissions.get("organizations", {})
account_permissions = permissions.get("account_permissions", {})

# Debug logging
logger.debug(f"[create_user_context] account_permissions: {account_permissions}")
logger.debug(f"[create_user_context] organization_permissions: {organization_permissions}")

return UserContext(
    user_id=user_id,
    email=email,
    organization_permissions=organization_permissions,
    account_permissions=account_permissions,
)
```

**Lines 176-190** - Fix new user creation to use NEW structure:

**Before**:
```python
user_data = {
    "uid": user_id,
    "email": email,
    "profile": {
        "email": email,
    },
    "permissions": {
        "accounts": {},
        "organizations": {},
    },
    "created_at": firestore.SERVER_TIMESTAMP,
}
```

**After**:
```python
user_data = {
    "uid": user_id,
    "email": email,
    "profile": {
        "email": email,
    },
    "permissions": {
        "organizations": {},
        "account_permissions": {},
    },
    "created_at": firestore.SERVER_TIMESTAMP,
}
```

#### 2.3 Update Dependencies

**File**: `api/src/kene_api/auth/dependencies.py`

**Lines 51-77** - Remove merging logic:

**Before**:
```python
user_context = UserContext(
    user_id=decoded_token["uid"],
    email=decoded_token.get("email", ""),
    accessible_accounts=[],
    permissions={},
    organization_permissions={},
)

if user_doc.exists:
    user_data = user_doc.to_dict()
    permissions = user_data.get("permissions", {})

    # Merge both old and new account permission structures
    old_accounts = permissions.get("accounts", {})
    new_account_permissions = permissions.get("account_permissions", {})
    user_context.account_permissions = {
        **old_accounts,
        **new_account_permissions,
    }

    user_context.organization_permissions = permissions.get("organizations", {})
```

**After**:
```python
user_context = UserContext(
    user_id=decoded_token["uid"],
    email=decoded_token.get("email", ""),
    organization_permissions={},
    account_permissions={},
)

if user_doc.exists:
    user_data = user_doc.to_dict()
    permissions = user_data.get("permissions", {})

    user_context.account_permissions = permissions.get("account_permissions", {})
    user_context.organization_permissions = permissions.get("organizations", {})
```

#### 2.4 Update Cached User Context

**File**: `api/src/kene_api/auth/cached_user_context.py`

Search for any references to `permissions` or `accessible_accounts` fields and update serialization/deserialization logic.

**Deliverables**:
- [ ] UserContext model simplified (remove 2 fields, simplify 2 methods)
- [ ] User context building simplified (fix variable naming, remove merging)
- [ ] Dependencies simplified (remove merging logic)
- [ ] Cached user context updated if needed
- [ ] All changes tested locally

---

## Phase 3: Testing & Validation (Week 2-3)

**Goal**: Ensure all functionality works correctly with simplified permission system.

### Tasks

#### 3.1 Update Unit Tests

**Files to check**:
- `api/tests/test_auth_models.py` - Update tests for UserContext
- Any tests that create UserContext objects with old fields

**Changes needed**:
```python
# Before
user_context = UserContext(
    user_id="test",
    email="test@example.com",
    accessible_accounts=["acc_123"],
    permissions={"acc_123": "edit"},  # OLD
    organization_permissions={},
    account_permissions={},
)

# After
user_context = UserContext(
    user_id="test",
    email="test@example.com",
    organization_permissions={},
    account_permissions={"acc_123": "edit"},  # Only this one
)
```

#### 3.2 Update Integration Tests

Search for integration tests that:
- Create mock user contexts
- Test permission checking logic
- Test account access flows

**Command to find tests**:
```bash
grep -r "accessible_accounts\|permissions.*accounts" api/tests/
```

#### 3.3 Manual Testing Checklist

Test in development environment:

- [ ] User login works
- [ ] Organization admin can access all accounts
- [ ] View-role user can access permitted accounts (view only)
- [ ] Edit-role user can access permitted accounts (edit)
- [ ] Super admin (@ken-e.ai) has access to all accounts
- [ ] Permission grant/revoke works correctly
- [ ] User cache invalidation works
- [ ] No errors in logs related to missing permissions

#### 3.4 Staging Validation

After code deployed to staging:

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Manual smoke tests pass
- [ ] No permission-related errors in logs
- [ ] Performance is same or better (fewer fallback checks)

**Deliverables**:
- [ ] All tests updated and passing
- [ ] Manual testing complete in development
- [ ] Staging validation complete
- [ ] Documentation updated (if any)

---

## Rollback Plan

If issues are discovered after Phase 2 deployment:

### Option 1: Rollback Code Only
1. Revert Phase 2 code changes
2. Data migration (Phase 1) remains - both structures will work

### Option 2: Full Rollback (if data migration caused issues)
1. Revert Phase 2 code changes
2. Run reverse migration script to restore `permissions.accounts`

**Reverse migration script**: `api/scripts/rollback_migration.py`

```python
"""Rollback migration by copying account_permissions back to accounts."""

def rollback_migration():
    db = firestore.Client()
    users = db.collection("users").stream()

    for user_doc in users:
        user_id = user_doc.id
        user_data = user_doc.to_dict()
        permissions = user_data.get("permissions", {})
        account_permissions = permissions.get("account_permissions", {})

        # Copy NEW back to OLD
        db.collection("users").document(user_id).update({
            "permissions.accounts": account_permissions
        })
```

---

## Success Metrics

### Quantitative
- **Code Complexity**: Reduce UserContext from 4 fields to 2 fields (50% reduction)
- **Fallback Paths**: Reduce from 3 permission checks to 1 (66% reduction)
- **Test Coverage**: Maintain or improve test coverage (target: >80%)
- **Performance**: No regression in auth check performance (target: <5ms p95)

### Qualitative
- Code is easier to understand (no confusing variable names)
- New developers can understand permission system quickly
- Debugging permission issues is straightforward (one source of truth)
- No technical debt comments about "deprecated" or "backward compatibility"

---

## Timeline Summary

| Phase | Duration | Key Milestone |
|-------|----------|---------------|
| Phase 1: Data Migration | Week 1 | All Firestore data uses NEW structure only |
| Phase 2: Code Cleanup | Week 2 | All backward compatibility code removed |
| Phase 3: Testing & Validation | Week 2-3 | All tests pass, staging validated |
| **Total** | **2-3 weeks** | **Production deployment with simplified permissions** |

---

## Additional Recommendations

### 1. Add Monitoring

After Phase 2 deployment, add monitoring for:
- Permission check failures (should be rare)
- Cache hit rate for user contexts
- Any errors related to missing permission fields

### 2. Update Documentation

Update any developer documentation that references:
- Permission system architecture
- How to grant/revoke permissions
- Permission hierarchy (super admin → org admin → account permissions)

### 3. Consider Future Enhancements

Once simplified, consider:
- Role-based access control (RBAC) with custom roles
- Permission inheritance (account → organization → global)
- Audit logging for permission changes
- Permission templates for common scenarios

---

## Files Modified Summary

### Phase 1 (Data Migration)
- **New**: `api/scripts/migrate_permissions.py`
- **New**: `api/scripts/verify_migration.py`
- **New**: `api/scripts/rollback_migration.py`

### Phase 2 (Code Cleanup)
- **Modified**: `api/src/kene_api/auth/models.py` (UserContext)
- **Modified**: `api/src/kene_api/auth/user_context.py` (_build_user_context_from_data, _get_or_create_user_document)
- **Modified**: `api/src/kene_api/auth/dependencies.py` (get_current_user_optional)
- **Modified**: `api/src/kene_api/auth/cached_user_context.py` (if serialization logic exists)

### Phase 3 (Testing)
- **Modified**: `api/tests/test_auth_models.py` (update UserContext tests)
- **Modified**: Various integration tests (grep search required)

---

## Questions for Implementation

1. **Backup Strategy**: Should we export Firestore backup before migration in production?
2. **Deployment Coordination**: Can we deploy Phase 2 code immediately after Phase 1 migration, or need separation?
3. **Communication**: Should we notify team before each phase deployment?
4. **Monitoring Window**: How long should we monitor after Phase 2 deployment before considering it successful?

---

## Conclusion

This phased migration approach balances safety with forward progress:
- **Phase 1** migrates data without code changes (safe, reversible)
- **Phase 2** removes complexity after data is clean (high impact)
- **Phase 3** ensures quality before production deployment

The end result is a significantly simpler, more maintainable permission system with a single source of truth and no confusing fallback logic.

**Recommendation: Proceed with Phase 1 in development environment first, validate thoroughly, then continue with remaining phases.**
