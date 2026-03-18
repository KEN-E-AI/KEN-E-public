# Subscription Plans Caching Guide

## Issue
When modifying the `subscription-plans` collection in Firestore, changes are not immediately visible in the development environment due to multiple layers of caching.

## Caching Layers

### 1. Backend API Cache (Python/FastAPI)
- **Location**: `api/src/kene_api/routers/subscription_plans.py`
- **Duration**: 5 minutes (300 seconds)
- **Type**: In-memory cache using Python globals

### 2. Frontend React Query Cache
- **Location**: `frontend/src/hooks/useSubscriptionPlans.ts`
- **Duration**: 5 minutes stale time, 10 minutes garbage collection
- **Type**: Client-side cache managed by TanStack Query

## Solutions

### Quick Fix (Immediate)
1. **Restart the API server** to clear backend cache:
   ```bash
   # Stop with Ctrl+C, then restart:
   cd api && uv run --active -- uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Hard refresh the browser** (Cmd+Shift+R on Mac) to clear React Query cache

### Automatic Solution (Implemented)
The codebase now includes development-specific cache bypasses:

1. **Backend**: Cache is disabled in development environment
   - Checks `ENVIRONMENT` env variable
   - If set to "development", caching is disabled

2. **Frontend**: Cache is disabled in development environment
   - Checks `VITE_ENVIRONMENT` env variable
   - If set to "development":
     - `staleTime` and `gcTime` are set to 0
     - `refetchOnWindowFocus` is enabled
     - Refresh button added to PlanSelectionModal

### Manual Cache Refresh
In the PlanSelectionModal, users can now click the refresh button (↻) to manually refetch subscription plans.

## Environment Variables
Ensure these are set in your development environment:

**Backend** (in `api/.env`):
```
ENVIRONMENT=development
```

**Frontend** (in `frontend/.env.development`):
```
VITE_ENVIRONMENT=development
```

## Testing Firestore Changes
1. Modify subscription plans in Firestore console
2. Either:
   - Click the refresh button in the modal
   - Switch browser tabs (triggers refetch in dev mode)
   - Reload the page
3. Changes should appear immediately

## Production Behavior
In production environments (staging/production), caching remains enabled for performance:
- Backend: 5-minute cache
- Frontend: 5-minute stale time
- This prevents excessive Firestore reads and improves performance