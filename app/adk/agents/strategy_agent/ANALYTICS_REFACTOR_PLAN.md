# Analytics System Refactoring Plan

## Overview
This plan addresses critical issues identified in the analytics system code review, prioritizing maintainability and testability improvements.

## Phase 1: High Priority Refactoring (Week 1)

### 1.1 Refactor execute_strategy_generation in orchestrator.py

**Objective**: Extract analytics setup and reporting into separate functions to reduce complexity.

**New Functions to Create**:

```python
def initialize_analytics_services(
    account_id: str, 
    project_id: Optional[str],
    enable_analytics: bool
) -> Tuple[Optional[AnalyticsService], Optional[PerformanceProfiler], 
           Optional[AlertManager], Optional[OptimizationAnalyzer]]:
    """Initialize all analytics services."""
    if not enable_analytics:
        return None, None, None, None
    # ... initialization logic
    return analytics_service, performance_profiler, alert_manager, optimization_analyzer

def report_execution_summary(
    analytics_service: Optional[AnalyticsService],
    performance_profiler: Optional[PerformanceProfiler],
    optimization_analyzer: Optional[OptimizationAnalyzer],
    main_operation: Optional[PerformanceMetrics]
) -> None:
    """Generate and log execution summary reports."""
    # ... reporting logic

def check_token_limits_before_execution(
    alert_manager: Optional[AlertManager],
    execution_input: str,
    performance_profiler: Optional[PerformanceProfiler],
    main_operation: Optional[PerformanceMetrics]
) -> Optional[str]:
    """Check token limits and circuit breaker. Returns error message if execution should abort."""
    # ... token checking logic
```

### 1.2 Break up analyze_usage_patterns in optimization_analyzer.py

**New Functions**:
- `analyze_agent_patterns()` - Agent-specific analysis
- `analyze_model_usage()` - Model usage statistics  
- `analyze_error_patterns()` - Error pattern analysis
- `analyze_peak_usage()` - Hourly usage analysis
- `analyze_context_utilization()` - Context utilization stats

### 1.3 Add Pydantic Models

**New File**: `analytics_models.py`

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict, Any, List, Optional

class ExecutionMetrics(BaseModel):
    execution_id: str
    agent_name: str
    account_id: str
    timestamp: datetime
    model: str
    prompt_tokens: int
    response_tokens: int
    total_tokens: int
    prompt_cost: float
    response_cost: float
    total_cost: float
    execution_time_seconds: float
    success: bool
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class DailyCostAggregation(BaseModel):
    date: str
    account_id: str
    total_cost: float
    total_tokens: int
    total_executions: int
    cost_by_agent: Dict[str, float]
    cost_by_model: Dict[str, float]
    tokens_by_model: Dict[str, int]

class PerformanceProfile(BaseModel):
    execution_id: str
    account_id: str
    timestamp: datetime
    agent_name: str
    operation: str
    duration_seconds: float
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_bottleneck: bool
    severity: str

class AlertData(BaseModel):
    alert_id: str
    account_id: str
    timestamp: str
    severity: str
    percentage: float
    current_tokens: int
    max_tokens: int
    message: str
    context: Optional[str] = None
    agent_name: Optional[str] = None
    circuit_breaker_open: bool = False
```

### 1.4 Fix Import Organization

Move all imports to top of files:
- `from datetime import timedelta` in performance_profiler.py and alert_manager.py
- `import requests` in alert_manager.py (with try/except for optional)

## Phase 2: Medium Priority (Week 2)

### 2.1 Simplify check_token_usage

Create helper functions:
- `should_trigger_alert()` - Threshold checking
- `is_in_cooldown()` - Cooldown checking  
- `create_and_send_alert()` - Alert handling

### 2.2 Document Email Stub

Add clear documentation that email is an extension point with example implementation.

### 2.3 Add Integration Tests

Create `test_analytics_integration.py` with:
- Full execution flow test
- Alert escalation test
- Cost aggregation test
- Optimization recommendation test

### 2.4 Document Thread Safety

Add warning to performance_profiler.py about thread-local storage limitations.

## Phase 3: Low Priority (Week 3)

### 3.1 Add Retry Logic

Create `@with_firestore_retry` decorator for critical operations.

### 3.2 Async Support Evaluation

Research and prototype async versions if needed.

## Implementation Order

1. Start with orchestrator.py refactoring (highest impact)
2. Add Pydantic models (improves type safety)
3. Break up optimization_analyzer.py
4. Fix imports
5. Continue with medium priority items

## Success Metrics

- Functions < 50 lines
- Cyclomatic complexity < 10
- Type hints coverage 100%
- Test coverage > 90%

## Files to Modify

1. `/app/adk/agents/strategy_agent/orchestrator.py`
2. `/app/adk/agents/strategy_agent/optimization_analyzer.py`
3. `/app/adk/agents/strategy_agent/analytics_service.py` (new models)
4. `/app/adk/agents/strategy_agent/analytics_models.py` (new file)
5. `/app/adk/agents/strategy_agent/alert_manager.py`
6. `/app/adk/agents/strategy_agent/performance_profiler.py`