# Testing Guide: AsyncAnalyticsQueue with Existing Agents

## Overview
This guide explains how to test the AsyncAnalyticsQueue implementation with your existing strategy agents to verify performance improvements and ensure compatibility.

## Testing Approaches

### 1. Unit Testing - Isolated Queue Testing
Run the standalone test script to verify queue functionality:

```bash
cd app/adk/agents/strategy_agent
python test_async_analytics_integration.py
```

This tests:
- Queue overflow handling
- Batch processing efficiency
- Graceful shutdown with pending events
- Performance comparison (sync vs async)

### 2. Integration Testing - With Real Agents

#### Option A: Modify Orchestrator (Non-invasive)
Update `orchestrator.py` temporarily to use async analytics:

```python
# In orchestrator.py, modify the analytics initialization:
def execute_strategy_generation(context, ...):
    # Original (comment out):
    # analytics_service = AnalyticsService(context.account_id)
    
    # Test with async (add):
    from async_analytics_queue import AsyncAnalyticsAdapter
    analytics_service = AsyncAnalyticsAdapter(context.account_id)
    
    # Rest of the code remains the same
```

#### Option B: Environment Variable Toggle
Add a feature flag to switch between sync/async:

```python
# In orchestrator.py
import os
from analytics_service import AnalyticsService
from async_analytics_queue import AsyncAnalyticsAdapter

def get_analytics_service(account_id: str):
    """Get analytics service based on environment config."""
    if os.getenv("USE_ASYNC_ANALYTICS", "false").lower() == "true":
        logger.info("Using ASYNC analytics")
        return AsyncAnalyticsAdapter(account_id)
    else:
        logger.info("Using SYNC analytics")
        return AnalyticsService(account_id)

# Then in execute_strategy_generation:
analytics_service = get_analytics_service(context.account_id)
```

Test with:
```bash
# Test with async
export USE_ASYNC_ANALYTICS=true
python deploy_supervisor.py

# Test with sync (default)
export USE_ASYNC_ANALYTICS=false
python deploy_supervisor.py
```

### 3. Load Testing - Performance Validation

Create a load test script:

```python
# load_test_analytics.py
import concurrent.futures
import time
from async_analytics_queue import AsyncAnalyticsAdapter
from analytics_service import AnalyticsService

def simulate_agent_load(analytics_service, agent_id: int):
    """Simulate a single agent execution."""
    for i in range(10):
        analytics_service.track_agent_execution(
            agent_name=f"agent_{agent_id}",
            prompt_tokens=1000,
            response_tokens=2000,
            model="gemini-2.5-flash",
            execution_time=1.0,
            success=True
        )
    return f"Agent {agent_id} completed"

def load_test(service_type="async", num_agents=20):
    """Run load test with multiple concurrent agents."""
    if service_type == "async":
        analytics = AsyncAnalyticsAdapter("load_test")
    else:
        analytics = AnalyticsService("load_test")
    
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(simulate_agent_load, analytics, i)
            for i in range(num_agents)
        ]
        results = [f.result() for f in futures]
    
    elapsed = time.time() - start_time
    
    if service_type == "async":
        analytics.shutdown()
    
    return elapsed

# Run comparison
async_time = load_test("async", 20)
sync_time = load_test("sync", 20)
print(f"Async: {async_time:.2f}s, Sync: {sync_time:.2f}s")
print(f"Improvement: {((sync_time - async_time) / sync_time * 100):.1f}%")
```

### 4. Production-Safe Testing

#### A. Canary Deployment
Test with a single account first:

```python
# In orchestrator.py
ASYNC_ANALYTICS_ACCOUNTS = ["test_account_123", "canary_account_456"]

def get_analytics_service(account_id: str):
    if account_id in ASYNC_ANALYTICS_ACCOUNTS:
        logger.info(f"Using ASYNC analytics for account {account_id}")
        return AsyncAnalyticsAdapter(account_id)
    return AnalyticsService(account_id)
```

#### B. Shadow Mode Testing
Run both analytics in parallel to compare:

```python
class ShadowAnalytics:
    """Run both sync and async analytics for comparison."""
    
    def __init__(self, account_id: str):
        self.sync = AnalyticsService(account_id)
        self.async_queue = AsyncAnalyticsAdapter(account_id)
    
    def track_agent_execution(self, **kwargs):
        # Track in both systems
        sync_result = self.sync.track_agent_execution(**kwargs)
        async_result = self.async_queue.track_agent_execution(**kwargs)
        
        # Log any discrepancies
        if sync_result['total_tokens'] != async_result['total_tokens']:
            logger.warning("Token count mismatch between sync and async")
        
        return sync_result  # Return sync result for compatibility
```

### 5. Monitoring & Validation

#### Key Metrics to Monitor

```python
# Add monitoring endpoint or logs
def monitor_async_queue(analytics_adapter):
    """Monitor async queue health."""
    status = analytics_adapter.queue.get_queue_status()
    
    # Log key metrics
    logger.info(f"Queue utilization: {status['utilization_percent']:.1f}%")
    logger.info(f"Events queued: {status['metrics']['events_queued']}")
    logger.info(f"Events processed: {status['metrics']['events_processed']}")
    logger.info(f"Failed events: {status['failed_events_count']}")
    
    # Alert if queue is backing up
    if status['utilization_percent'] > 80:
        logger.warning("Analytics queue high utilization!")
    
    return status
```

#### Validation Checklist

- [ ] **Performance**: Async is faster for agent execution
- [ ] **Data Integrity**: All events are eventually written to Firestore
- [ ] **Error Handling**: Failed events are logged and tracked
- [ ] **Memory Usage**: Queue doesn't cause memory issues
- [ ] **Shutdown**: Graceful shutdown flushes pending events
- [ ] **Circuit Breaker**: Still functions with async analytics
- [ ] **Cost Tracking**: Costs are accurately calculated

### 6. Rollback Plan

If issues arise, immediate rollback:

```python
# Quick rollback in orchestrator.py
def get_analytics_service(account_id: str):
    # return AsyncAnalyticsAdapter(account_id)  # Comment out
    return AnalyticsService(account_id)  # Revert to sync
```

## Expected Results

### Performance Improvements
- **Latency**: ~50-100ms → ~1ms per analytics call
- **Throughput**: 10-50x improvement with batching
- **Agent Speed**: 10-30% faster overall execution

### Resource Usage
- **Memory**: +~10MB for queue buffer
- **CPU**: Minimal increase (one background thread)
- **Network**: Reduced Firestore API calls by 10-100x

## Troubleshooting

### Queue Full Errors
```python
# Increase queue size
analytics = AsyncAnalyticsAdapter(
    account_id=account_id,
    queue_size=50000  # Increase from default 10000
)
```

### Events Not Appearing in Firestore
```python
# Force flush for debugging
analytics.queue.flush(timeout=10.0)
```

### Memory Issues
```python
# Reduce batch size and queue size
analytics = AsyncAnalyticsAdapter(
    account_id=account_id,
    queue_size=1000,
    batch_size=20
)
```

## Migration Timeline

1. **Week 1**: Test in development environment
2. **Week 2**: Deploy to staging with monitoring
3. **Week 3**: Canary deployment (5% of accounts)
4. **Week 4**: Gradual rollout (25%, 50%, 100%)

## Conclusion

The AsyncAnalyticsQueue provides significant performance improvements while maintaining compatibility with existing code. Follow this testing guide to safely validate and deploy the async analytics system.