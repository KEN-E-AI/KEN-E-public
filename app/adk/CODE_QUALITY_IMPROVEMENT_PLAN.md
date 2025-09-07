# Code Quality Improvement Plan for Agent Separation

## Analysis of Codebase Consistency

Based on analysis of the existing codebase:
- **Type hints**: Already used extensively (e.g., retry_utils.py, integration_models.py)
- **Pydantic models**: Standard pattern in API models directory
- **Retry logic**: Existing retry_utils.py can be reused
- **Async patterns**: Already present in async_analytics_queue.py
- **Testing patterns**: Pytest with fixtures and mocking

## Phase 1: Type Safety Improvements (High Priority)

### 1.1 Add Type Hints to dispatch_handlers.py
```python
from typing import Any, Dict, List, Optional
```
- Add return type `-> Dict[str, Any]` to all dispatch functions
- Add parameter types including `Optional[Dict[str, str]]` for tenant_context
- Follow existing pattern from retry_utils.py

### 1.2 Add Type Hints to supervisor_utils.py
- Add complete type hints following codebase patterns
- Use `Dict[str, Any]` for flexible dictionaries
- Import from typing module as per codebase standard

### 1.3 Add Type Hints to deployment scripts
- Type hint argparse functions: `-> argparse.ArgumentParser`
- Type hint deployment functions: `-> str` for engine IDs
- Follow patterns from existing scripts

## Phase 2: Data Validation with Pydantic (High Priority)

### 2.1 Create Pydantic Models
**Location**: `/app/adk/agents/models/strategy_models.py` (new directory following API pattern)

```python
from typing import List, Optional
from pydantic import BaseModel, Field

class StrategyParameters(BaseModel):
    """Parameters for strategy generation."""
    company_name: str = Field(..., description="Company name")
    industry: str = Field(..., description="Industry sector")
    websites: List[str] = Field(default_factory=list)
    customer_regions: List[str] = Field(default_factory=list)
    account_id: str = Field(..., description="Account identifier")
    user_id: str = Field(..., description="User identifier")
    annual_ad_budget: Optional[str] = None
    project_id: str = Field(..., description="GCP project ID")
    uploaded_documents: List[str] = Field(default_factory=list)
```

### 2.2 Refactor dispatch_to_strategy
- Replace string parsing with `StrategyParameters.parse_obj()`
- Use structured data validation
- Add proper ValidationError handling

## Phase 3: Fix Test Infrastructure (High Priority)

### 3.1 Fix Mock Patching
Current issue: Patching non-existent `vertexai` attribute
Solution: Patch at the correct import location
```python
@patch('google.cloud.aiplatform.reasoning_engines')  # Correct path
```

### 3.2 Add Fixtures
Following existing test patterns:
```python
@pytest.fixture
def mock_engine_ids():
    return {
        'ken_e': 'projects/123/locations/us/reasoningEngines/456',
        'strategy': 'projects/123/locations/us/reasoningEngines/789'
    }
```

## Phase 4: Reuse Existing Retry Logic (Medium Priority)

### 4.1 Import Existing retry_utils
Instead of creating new retry logic, reuse `/app/adk/agents/strategy_agent/retry_utils.py`:
```python
from agents.strategy_agent.retry_utils import retry_with_exponential_backoff
```

### 4.2 Apply to Agent Invocations
Wrap agent calls with existing retry decorator:
```python
@retry_with_exponential_backoff(max_attempts=3)
def invoke_agent_with_retry(agent, query):
    return invoke_agent_sync(agent, query)
```

## Phase 5: Async Operations (Low Priority - Defer)

**Decision**: Defer async conversion as it requires significant API changes
- Current implementation uses sync calls throughout
- Would require updating entire call chain
- Can be done in separate PR

## Phase 6: Testing Enhancements (Medium Priority)

### 6.1 Fix Existing Tests First
- Correct mock paths in test_agent_routing.py
- Ensure all tests pass before adding new ones

### 6.2 Add Integration Tests
Following existing test patterns in `/api/tests/integration/`:
```python
@pytest.mark.integration
async def test_ken_e_agent_connectivity():
    # Test actual agent is reachable
    pass
```

## Implementation Order

### Immediate (This PR):
1. **Add type hints** (Phase 1) - 30 minutes
2. **Create Pydantic models** (Phase 2.1) - 30 minutes
3. **Fix test mocking** (Phase 3.1) - 30 minutes
4. **Refactor dispatch_to_strategy** (Phase 2.2) - 45 minutes
5. **Apply existing retry logic** (Phase 4) - 30 minutes

### Future PR:
- Async conversion (Phase 5)
- Additional integration tests
- Performance optimizations

## Success Criteria
- [ ] All type hints added
- [ ] Pydantic models validate strategy parameters
- [ ] All tests pass (including fixed mocks)
- [ ] No string parsing in dispatch_to_strategy
- [ ] Retry logic applied to agent calls
- [ ] Type checking passes (mypy)
- [ ] Code formatted (ruff)

## Estimated Time: 2.5-3 hours

## Risk Mitigation
- Each change is isolated and testable
- Backward compatibility maintained
- Using existing patterns from codebase
- Reusing existing utilities where possible