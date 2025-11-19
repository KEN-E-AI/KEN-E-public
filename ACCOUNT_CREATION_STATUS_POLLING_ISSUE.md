# Account Creation Status Polling Issue

## Problem Description

When loading the Account Settings page (Organization Settings), the account creation status endpoint is being called multiple times in rapid succession for the same account. This suggests the `AccountsManagement` component is re-rendering excessively, causing the `useAccountCreationProgress` hook to restart its polling cycle multiple times.

## Observed Behavior

### API Logs (Example)
```
[axios] Request starting: GET /api/v1/accounts/acc_a5490036b0fa4f39a4ec9cf18e3ab3e7/creation-status
[axios] Timeout setting: 0ms (undefined minutes)
[axios] Request time: 2025-11-19T15:45:06.600Z
[axios] Response received: GET /api/v1/accounts/acc_a5490036b0fa4f39a4ec9cf18e3ab3e7/creation-status
[axios] Duration: 544ms (0.5s)
```

This pattern repeats 5-6 times on a single page load, with each request taking 500-700ms.

### Timeline
All requests happen within a few seconds of page load:
- 15:45:06.600Z - Request 1 (544ms)
- 15:45:10.650Z - Request 2 (490ms)
- 15:45:40.654Z - Request 3 (634ms)
- 15:46:10.652Z - Request 4 (634ms)
- 15:47:10.657Z - Request 5 (710ms)

## Technical Context

### Hook Implementation
The `useAccountCreationProgress` hook ([frontend/src/hooks/useAccountCreationProgress.ts](frontend/src/hooks/useAccountCreationProgress.ts)) is designed to:
- Poll `/api/v1/accounts/{accountId}/creation-status` every 30 seconds
- Stop polling when status is "completed" or "failed"
- Use a cleanup function to clear the interval on unmount

### Usage Location
The hook is called once in `AccountsManagement.tsx`:
```typescript
const accountCreationProgress = useAccountCreationProgress(creatingAccountId);
```

### Expected Behavior
- Hook should run once when component mounts
- Poll every 30 seconds until creation completes
- Clean up interval on component unmount

### Actual Behavior
- Multiple rapid calls on initial page load (not 30 seconds apart)
- Suggests the component is mounting/unmounting or re-rendering multiple times
- Each render creates a new polling interval

## Potential Root Causes

1. **Component Re-rendering**: The `AccountsManagement` component may be re-rendering due to:
   - State changes in parent components
   - Context updates (AuthContext, ChatContext)
   - Dependencies in useEffect hooks
   - React Query cache updates

2. **Multiple Component Instances**: The component might be rendered multiple times in the component tree

3. **Dependency Array Issues**: useEffect hooks with incorrect dependencies causing re-runs

4. **State Updates During Render**: State updates causing cascading re-renders

## Investigation Steps

To diagnose this issue:

1. **Add render counting** to `AccountsManagement.tsx`:
   ```typescript
   const renderCount = useRef(0);
   useEffect(() => {
     renderCount.current++;
     console.log(`AccountsManagement render #${renderCount.current}`);
   });
   ```

2. **Check React DevTools Profiler** to see what's causing re-renders

3. **Review dependencies** in all useEffect hooks in `AccountsManagement.tsx`

4. **Check if component is duplicated** in the component tree

5. **Review context updates** that might trigger re-renders

## Related Files

- [frontend/src/hooks/useAccountCreationProgress.ts](frontend/src/hooks/useAccountCreationProgress.ts) - Polling hook
- [frontend/src/pages/components/AccountsManagement.tsx](frontend/src/pages/components/AccountsManagement.tsx) - Component using the hook
- [frontend/src/contexts/AuthContext.tsx](frontend/src/contexts/AuthContext.tsx) - May be triggering updates
- [api/src/kene_api/routers/accounts.py:L96-L155](api/src/kene_api/routers/accounts.py) - Backend endpoint being called

## Impact

- **Performance**: Unnecessary API calls waste resources and slow down page loads
- **User Experience**: Increased latency when loading settings page
- **Server Load**: Multiple redundant database queries
- **Costs**: Increased Cloud Run invocations and database operations

## Proposed Solutions

1. **Add memoization** to prevent unnecessary re-renders in `AccountsManagement`
2. **Use React.memo** for child components
3. **Review and fix useEffect dependencies** to prevent cascading updates
4. **Add polling state management** to prevent multiple concurrent polling sessions
5. **Implement request deduplication** at the API client level

## Notes

- This issue is separate from the permissions migration and organization selector dropdown fix
- The polling functionality works correctly (30-second intervals), but something is causing the component to remount frequently
- Need to identify what's triggering the re-renders to implement the correct fix
