# Breaking Changes for PR #198

## ⚠️ API Breaking Changes

### 1. CustomerProfile Model - Field Rename

**Change:** `narrative` field renamed to `description`

**Impact:** API consumers must update request/response handling for customer profile endpoints

**Migration:**
```python
# Before
customer_profile = {
    "display_name": "Marketing Mary",
    "narrative": "Marketing Mary is a 35-year-old...",
    "references": []
}

# After
customer_profile = {
    "display_name": "Marketing Mary",
    "description": "Marketing Mary is a 35-year-old...",
    "references": []
}
```

**Affected Endpoints:**
- `POST /api/v1/knowledge-graph/{account_id}/customer-profiles`
- `PUT /api/v1/knowledge-graph/{account_id}/customer-profiles/{node_id}`
- `GET /api/v1/knowledge-graph/{account_id}/customer-profiles/{node_id}`

---

### 2. CustomerProfileListResponse - Field Rename

**Change:** `profiles` field renamed to `customer_profiles`

**Impact:** Frontend must update response parsing when fetching customer profile lists

**Migration:**
```typescript
// Before
const profiles = response.data.profiles;

// After
const profiles = response.data.customer_profiles;
```

**Affected Endpoints:**
- `GET /api/v1/knowledge-graph/{account_id}/customer-profiles`

---

### 3. MonitoringTopics Model - New Field

**Change:** Added `customer_profile_entries: list[CustomerProfileEntry]`

**Impact:** Backward compatible - defaults to empty list if not provided

**Migration:** No action required for existing code

---

### 4. CompetitorEntry & CustomerProfileEntry - Enhanced Validation

**Change:** Added model validator to ensure either `node_id` or `name` is provided

**Impact:** API will now reject requests that don't include at least one identifier

**Migration:**
```python
# Before (this will now fail)
competitor_entry = {
    "keywords": ["keyword1"]
}

# After (must include node_id or name)
competitor_entry = {
    "node_id": "comp_123",
    "keywords": ["keyword1"]
}
```

---

## Database Schema Changes

### Neo4j Schema

**CustomerProfile nodes:**
- Property `narrative` should be migrated to `description`
- Existing nodes with `narrative` property will need data migration

**Migration Script:** (to be run if needed)
```cypher
MATCH (cp:CustomerProfile)
WHERE cp.narrative IS NOT NULL AND cp.description IS NULL
SET cp.description = cp.narrative
REMOVE cp.narrative
```

---

## Frontend Changes

### Response Model Updates

The frontend has been updated to handle the new field names:
- `customerProfiles.ts` query hooks updated to use `customer_profiles` field
- `CustomerProfilesManagement.tsx` component updated to use `description` field
- Type definitions updated in `customerProfileService.ts`

---

## Backward Compatibility Notes

1. **CustomerProfileResponse** provides defaults for new fields:
   - `description: str = ""` (empty string if missing)
   - `references: list[str] = []` (empty list if missing)

2. **Legacy Support:**
   - `CompetitorEntry` and `CustomerProfileEntry` still accept `name` field for backward compatibility
   - Marked as `DEPRECATED` in field descriptions
   - Will be removed in future release

3. **MonitoringTopics:**
   - New `customer_profile_entries` field defaults to empty list
   - Existing documents without this field will continue to work

---

## Testing

All breaking changes have been tested:
- ✅ Unit tests for model validation
- ✅ Integration tests for new endpoints
- ✅ Frontend tests for layout calculations
- ✅ Type checking passes

---

## Rollback Plan

If issues arise:
1. Revert field renames in models (`description` → `narrative`, `customer_profiles` → `profiles`)
2. Remove model validators on `CompetitorEntry` and `CustomerProfileEntry`
3. Revert frontend changes to use old field names
4. Run database migration to restore `narrative` property if needed

---

## Questions?

Contact the development team or refer to:
- API Documentation: `/docs` endpoint
- Frontend Types: `frontend/src/services/customerProfileService.ts`
- Backend Models: `api/src/kene_api/models/graph_models.py`
