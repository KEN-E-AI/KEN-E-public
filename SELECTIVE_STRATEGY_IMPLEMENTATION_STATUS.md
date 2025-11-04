# Selective Strategy Execution - Implementation Status

**Feature Branch**: `feature/selective-strategy-execution`
**Date**: 2025-11-04
**Status**: Backend Complete, Frontend Pending

---

## Overview

This feature allows admin users to select which strategy agents to run during account creation and regeneration, instead of always running all strategies sequentially. Regular users will only see the standard "run all strategies" option.

---

## ✅ COMPLETED - Backend Implementation

### 1. Constants and Configuration (`app/adk/agents/strategy_agent/constants.py`)
- ✅ Created `VALID_STRATEGY_TYPES` list
- ✅ Created `DEFAULT_PRODUCT_CATEGORIES` list (5 generic categories for marketing strategy when business strategy not run)

### 2. Orchestrator Updates (`app/adk/agents/strategy_agent/orchestrator.py`)
- ✅ Updated `execute_strategy_generation_direct()` signature to accept:
  - `enabled_strategies: Optional[List[str]]` - list of strategies to generate
  - `override_product_categories: Optional[List[str]]` - categories for marketing without business
- ✅ Added validation logic for `enabled_strategies` parameter
- ✅ Added strategy filtering in the main loop (skips disabled strategies)
- ✅ Implemented smart product category handling for marketing strategy:
  - Priority 1: Use `override_product_categories` if provided
  - Priority 2: Use categories from business strategy if available
  - Priority 3: Use `DEFAULT_PRODUCT_CATEGORIES` as fallback
- ✅ Updated `execute_strategy_generation()` wrapper to accept and pass through new parameters
- ✅ Updated agent instruction to parse new parameters from text messages

### 3. API Task Layer (`api/src/kene_api/tasks/strategy_tasks.py`)
- ✅ Updated `trigger_strategy_generation()` signature to accept new parameters
- ✅ Updated message construction to include `enabled_strategies` and `override_product_categories`
- ✅ Added logging for selective strategy execution

### 4. API Models (`api/src/kene_api/models/kene_models.py`)
- ✅ Added `enabled_strategies` field to `AccountRequest` model
- ✅ Added `override_product_categories` field to `AccountRequest` model

### 5. API Endpoints (`api/src/kene_api/routers/accounts.py`)
- ✅ Updated `create_account()` endpoint to accept:
  - `enabled_strategies: str | None` (JSON string of array)
  - `override_product_categories: str | None` (JSON string of array)
- ✅ Updated form parser call to include new parameters

### 6. Form Parsing (`api/src/kene_api/services/form_parsing_service.py`)
- ✅ Updated `parse_account_form_data()` to parse new JSON fields
- ✅ Added proper error handling for JSON parsing

### 7. Account Service (`api/src/kene_api/services/account_service.py`)
- ✅ Updated `background_tasks.add_task()` call to pass new parameters to `trigger_strategy_generation()`

---

## ⏳ PENDING - Frontend Implementation

### 8. Frontend Constants (NEW FILE: `frontend/src/constants/strategies.ts`)
```typescript
export const VALID_STRATEGY_TYPES = [
  'business_strategy',
  'competitive_strategy',
  'marketing_strategy',
  'brand_guidelines',
] as const;

export type StrategyType = typeof VALID_STRATEGY_TYPES[number];

export const STRATEGY_LABELS: Record<StrategyType, string> = {
  business_strategy: 'Business Strategy',
  competitive_strategy: 'Competitive Analysis',
  marketing_strategy: 'Marketing Strategy',
  brand_guidelines: 'Brand Guidelines',
};

export const DEFAULT_PRODUCT_CATEGORIES = [
  'Core Products & Services',
  'Premium Offerings',
  'Subscription Services',
  'Professional Solutions',
  'Digital Products',
];
```

### 9. Account Creation Form Updates
**File**: `frontend/src/components/accounts/CreateAccountForm.tsx` (or similar)

**Changes Needed**:
- Add "Strategy Selection" section (admin-only, visible based on `user.is_super_admin` or organization admin check)
- Add checkboxes for each strategy type (all checked by default)
- Add conditional "Product Categories" input that appears when:
  - Marketing Strategy is checked
  - Business Strategy is NOT checked
- Pre-populate product categories input with `DEFAULT_PRODUCT_CATEGORIES`
- Pass `enabled_strategies` and `override_product_categories` in form submission

### 10. Strategy Regeneration Page (NEW FILE)
**File**: `frontend/src/pages/admin/RegenerateStrategies.tsx`

**Features Needed**:
- Admin-only page (check permissions)
- Display current account info
- Strategy selection checkboxes (same as creation form)
- Product categories input (conditional)
- "Regenerate Selected Strategies" button
- Warning message: "This will overwrite existing strategy data"
- Call new API endpoint (see below)

### 11. New API Endpoint for Regeneration
**File**: `api/src/kene_api/routers/strategies.py` or `accounts.py`

**Endpoint**: `POST /api/accounts/{account_id}/strategies/regenerate`

**Request Body**:
```json
{
  "enabled_strategies": ["marketing_strategy", "brand_guidelines"],
  "override_product_categories": ["Core Products", "Premium Services"]
}
```

**Implementation**:
- Check user is admin (organization admin or super admin)
- Validate `enabled_strategies` list
- Call `trigger_strategy_generation()` with existing account data + new strategy selection
- Return success/error response

### 12. Routing Updates
**File**: `frontend/src/App.tsx` or routing configuration

**Changes Needed**:
- Add route: `/admin/accounts/:accountId/regenerate-strategies`
- Protect route with admin permission check
- Add navigation link in account detail pages (admin only)

---

## 🧪 PENDING - Testing

### 13. Backend Unit Tests
**File**: `app/adk/agents/strategy_agent/tests/test_orchestrator.py`

**Test Cases Needed**:
1. Test filtering logic skips disabled strategies
2. Test marketing strategy with override categories
3. Test marketing strategy with default categories
4. Test validation of invalid strategy types
5. Test that product category override is ignored if marketing not enabled

### 14. API Tests
**File**: `api/tests/test_strategy_tasks.py`

**Test Cases Needed**:
1. Test `trigger_strategy_generation()` with enabled_strategies parameter
2. Test `trigger_strategy_generation()` with override_product_categories parameter
3. Test account creation with strategy selection
4. Test regeneration endpoint (once created)

### 15. Frontend Tests
- Component tests for strategy selection UI
- Integration tests for form submission
- Permission tests for admin-only features

---

## 🔍 PENDING - Type Checking and Linting

### 16. Backend Type Checking
```bash
cd api && uv run mypy src/kene_api/
cd app && uv run mypy adk/agents/strategy_agent/
```

### 17. Backend Linting
```bash
cd api && uv run ruff check src/
cd app && uv run ruff format adk/agents/
```

### 18. Frontend Type Checking
```bash
cd frontend && npm run typecheck
```

### 19. Frontend Linting
```bash
cd frontend && npm run format.fix
```

---

## 📋 Summary of Changes

### Files Modified (8):
1. `app/adk/agents/strategy_agent/orchestrator.py` - Core filtering and override logic
2. `app/adk/agents/strategy_agent/constants.py` - NEW FILE - Constants
3. `api/src/kene_api/tasks/strategy_tasks.py` - Parameter passing
4. `api/src/kene_api/models/kene_models.py` - Model updates
5. `api/src/kene_api/routers/accounts.py` - Endpoint updates
6. `api/src/kene_api/services/form_parsing_service.py` - Form parsing
7. `api/src/kene_api/services/account_service.py` - Service layer updates

### Files To Create (3):
8. `frontend/src/constants/strategies.ts` - Frontend constants
9. `frontend/src/pages/admin/RegenerateStrategies.tsx` - Regeneration page
10. API endpoint for regeneration (location TBD)

### Files To Modify (2):
11. Account creation form component
12. Frontend routing configuration

---

## 🚀 Next Steps

1. **Run type checking and linting on backend** (Task 16-17)
2. **Create frontend constants file** (Task 8)
3. **Update account creation form** (Task 9)
4. **Create regeneration page** (Task 10)
5. **Create regeneration API endpoint** (Task 11)
6. **Update routing** (Task 12)
7. **Write tests** (Task 13-15)
8. **Frontend type checking and linting** (Task 18-19)
9. **Manual testing** - Test all scenarios end-to-end
10. **Create PR** - After all tests pass

---

## 🎯 Testing Scenarios

Once implementation is complete, test these scenarios:

1. **Scenario 1**: Create account with only Business Strategy
2. **Scenario 2**: Create account with only Marketing Strategy (with default categories)
3. **Scenario 3**: Create account with Marketing + Competitive (no Business)
4. **Scenario 4**: Create account with all strategies (default behavior)
5. **Scenario 5**: Regenerate single strategy for existing account
6. **Scenario 6**: Verify regular users don't see strategy selection options
7. **Scenario 7**: Verify admin users see strategy selection options

---

## 📚 Architecture Decisions

### Why Per-Request Parameters Instead of Persistent Config?
**Decision**: Strategy selection is passed as parameters per request, not stored in Account model

**Rationale**:
- More flexible for testing (admins can change selection each time)
- Simpler implementation (no DB schema changes)
- Matches user requirement for "ephemeral" selection

### Why Default Categories for Marketing Strategy?
**Decision**: Provide 5 generic but realistic default product categories

**Rationale**:
- Speeds up testing (no manual input required)
- Provides realistic starting point for evaluation
- User requirement: "default placeholder categories... not too vague"

### Why Overwrite Instead of Versioning?
**Decision**: Regenerating strategies overwrites existing Firestore/Neo4j data

**Rationale**:
- Simpler implementation
- Matches current system behavior
- User requirement: "overwrite existing strategy data"
- Can be enhanced to versioning in future if needed

---

**DELETE THIS FILE**: After PR is merged, delete this status file as it's a temporary implementation tracking document.
