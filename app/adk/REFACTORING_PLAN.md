# Function Complexity Refactoring Plan

## Overview
This document outlines the strategy to refactor complex functions in the strategy agent system to improve maintainability, testability, and readability.

## Identified Complex Functions

### 1. `execute_strategy_generation()` in orchestrator.py
**Current Issues:**
- Doing too much: initialization, execution, event processing, saving
- Difficult to test individual components
- High cyclomatic complexity

**Proposed Refactoring:**
```python
# Break into smaller, focused functions:
def create_runner(agent: SequentialAgent, session_service: SessionService) -> Runner:
    """Create and configure the Runner instance."""
    pass

def process_events(events: List[Event]) -> Dict[str, Any]:
    """Process events and extract documents."""
    pass

def save_documents_to_firestore(
    documents: Dict[str, Any],
    account_id: str,
    firestore_client: FirestoreClient
) -> Dict[str, bool]:
    """Save documents to Firestore and return success status."""
    pass

def execute_strategy_generation(...):
    """Orchestrate the strategy generation process."""
    # Now just coordinates the smaller functions
    runner = create_runner(agent, session_service)
    events = runner.run(...)
    documents = process_events(events)
    save_status = save_documents_to_firestore(documents, account_id, client)
    return format_result(documents, save_status)
```

### 2. Agent Creation Functions in agents.py
**Current Issues:**
- Repeated pattern with slight variations
- Long instruction strings embedded in functions
- Firestore dependency handling duplicated

**Proposed Refactoring:**
```python
class AgentFactory:
    """Factory for creating strategy agents with consistent patterns."""
    
    def __init__(self, firestore_provider: Optional[FirestoreProvider] = None):
        self.firestore_provider = firestore_provider or DefaultFirestoreProvider()
    
    def create_strategist(
        self,
        name: str,
        doc_type: str,
        context: Optional[StrategyContext],
        instruction_template: str,
        prior_docs: List[str] = None
    ) -> Agent:
        """Generic strategist creation with dependency injection."""
        pass

# Usage:
factory = AgentFactory(firestore_provider=MockFirestoreProvider())
business_agent = factory.create_strategist(
    name="business_strategist",
    doc_type="business_strategy",
    context=context,
    instruction_template=BUSINESS_INSTRUCTION_TEMPLATE
)
```

### 3. Instruction String Management
**Current Issues:**
- Long instruction strings inline in functions
- Difficult to maintain and test
- Repeated patterns across agents

**Proposed Refactoring:**
```python
# Move to separate module: instructions.py
class InstructionBuilder:
    """Build agent instructions from templates and context."""
    
    BASE_TEMPLATE = """
    # ROLE & GOAL
    {role_description}
    
    # TOOLS
    {tools_description}
    
    # YOUR TASK
    {task_description}
    
    # PROCESS
    {process_steps}
    
    # OUTPUT REQUIREMENTS
    {output_requirements}
    """
    
    def build(
        self,
        role: str,
        tools: List[str],
        task: str,
        process: List[str],
        requirements: str,
        context: Optional[StrategyContext] = None
    ) -> str:
        """Build instruction from components."""
        pass
```

## Implementation Priority

### Phase 1: Extract Instructions (Quick Win)
1. Create `instructions.py` module
2. Move all instruction strings to templates
3. Create InstructionBuilder class
4. Update agent creation functions to use builder

### Phase 2: Refactor Orchestrator
1. Split `execute_strategy_generation()` into smaller functions
2. Create helper functions for event processing
3. Separate concerns: execution, processing, persistence

### Phase 3: Implement Factory Pattern
1. Create AgentFactory class
2. Implement dependency injection for Firestore
3. Consolidate repeated patterns
4. Update all agent creation to use factory

## Benefits

### Immediate Benefits:
- ✅ Easier to test individual components
- ✅ Clearer separation of concerns
- ✅ Reduced code duplication
- ✅ Better error isolation

### Long-term Benefits:
- ✅ Easier to add new agent types
- ✅ Simpler to modify instruction templates
- ✅ Better maintainability
- ✅ Improved debugging capabilities

## Testing Strategy

### Unit Tests:
- Test each refactored function independently
- Mock external dependencies
- Test edge cases and error conditions

### Integration Tests:
- Test component interactions
- Verify data flow between functions
- Test with real and mock Firestore

### Regression Tests:
- Ensure refactored code produces same results
- Compare output before and after refactoring
- Verify no functionality is lost

## Risk Mitigation

### Risks:
1. Breaking existing functionality
2. Introducing new bugs
3. Performance degradation

### Mitigation:
1. Comprehensive test coverage before refactoring
2. Incremental refactoring with testing at each step
3. Performance benchmarking before and after
4. Keep original code until refactoring is proven

## Success Metrics

### Code Quality:
- Cyclomatic complexity < 10 per function
- Function length < 50 lines
- Test coverage > 80%

### Maintainability:
- Clear single responsibility per function
- Minimal code duplication
- Easy to understand and modify

### Performance:
- No degradation in execution time
- Memory usage remains stable
- Firestore calls optimized