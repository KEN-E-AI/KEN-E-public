# API Endpoint Migration Summary

## Changes Made

### 1. Moved Search Logic from Insights to Funnel Reports

**From:** `/api/v1/insights/search` (POST)
**To:** `/api/v1/funnel-reports/analysis` (POST)

### 2. Removed activity_id Parameter

The new analysis endpoint no longer requires the `activity_id` parameter that was present in the original search endpoint.

### 3. Cleaned Up Mock Endpoints

**Removed the following mock-only endpoints from funnel_reports:**
- `/api/v1/funnel-reports/workflow` (POST) - Mock workflow execution
- `/api/v1/funnel-reports/saved-queries` (GET/POST/DELETE) - Mock saved query management  
- `/api/v1/funnel-reports/saved-queries/{query_id}/run` (POST) - Mock query execution
- `/api/v1/funnel-reports/summary` (GET) - Mock summary data

These endpoints only returned hardcoded mock data and provided no real functionality.

### 4. New Request Model

**Added:** `AnalysisSearchRequest` model in `kene_models.py`
- Contains the same fields as `InsightSearchRequest` except `activity_id`
- Fields: `account_id`, `metric_id`, `evaluation_date_start`, `evaluation_date_end`, `comparison_date_start`, `comparison_date_end`, `direction`

### 5. Updated Function Call

The search logic now calls `search_main()` with `activity_id=None` instead of `request.activity_id`.

## Files Modified

1. **`src/kene_api/models/kene_models.py`**
   - Added `AnalysisSearchRequest` model

2. **`src/kene_api/routers/funnel_reports.py`**
   - Added new `/analysis` endpoint with search logic
   - Removed mock endpoints: `/workflow`, `/saved-queries`, `/summary`
   - Cleaned up unused imports and dependencies
   - Added imports for Neo4j service and search utility

3. **`src/kene_api/routers/insights.py`**
   - Removed `/search` endpoint
   - Removed unused imports (`InsightSearchRequest`, `InsightSearchResponse`, `search_main`)

4. **`tests/test_insights.py`**
   - Removed `test_search_insights` test method
   - Removed temporary migration verification test

5. **`tests/test_funnel_reports.py`** (New file)
   - Added comprehensive tests for the new analysis endpoint
   - Removed tests for mock endpoints that were deleted
   - Tests include: basic functionality, invalid date format handling, database unavailability
   - Uses proper mocking of `search_main` function and async Neo4j service
   - Verifies that `activity_id=None` is passed to the search function

## API Usage

### Old Usage (Deprecated)
```bash
POST /api/v1/insights/search
{
  "account_id": "test_account",
  "activity_id": "activity_001",  # This field is no longer needed
  "metric_id": "metric_001",
  "evaluation_date_start": "2024-01-01",
  "evaluation_date_end": "2024-01-31",
  "comparison_date_start": "2023-12-01",
  "comparison_date_end": "2023-12-31",
  "direction": "positive"
}
```

### New Usage
```bash
POST /api/v1/funnel-reports/analysis
{
  "account_id": "test_account",
  "metric_id": "metric_001",
  "evaluation_date_start": "2024-01-01",
  "evaluation_date_end": "2024-01-31",
  "comparison_date_start": "2023-12-01",
  "comparison_date_end": "2023-12-31",
  "direction": "positive"
}
```

## Response Format

The response format remains the same: `InsightSearchResponse` with `insights` array and `total` count.

## Testing

- All existing insights tests pass with proper functionality testing
- New funnel_reports tests pass with comprehensive coverage of analysis endpoint
- Analysis endpoint properly tested for functionality, error handling, and database connectivity
- Tests verify that `activity_id` parameter is correctly removed (passed as `None`)
- Migration verification tests removed as they are no longer needed
