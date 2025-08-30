# Dependency Injection Architecture Design

## Problem Statement
Current implementation has tight coupling to external services (Firestore, Agent Engine, W&B), making the code difficult to test and maintain.

## Proposed Solution
Implement dependency injection pattern to decouple business logic from external dependencies.

## Architecture Design

### 1. Provider Interfaces

```python
# providers/interfaces.py
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class FirestoreProvider(ABC):
    """Abstract interface for Firestore operations."""
    
    @abstractmethod
    def get_best_practices(self, doc_type: str) -> Optional[str]:
        """Get best practices for a document type."""
        pass
    
    @abstractmethod
    def get_reviewer_guidelines(self, doc_type: str) -> Optional[str]:
        """Get reviewer guidelines for a document type."""
        pass
    
    @abstractmethod
    def save_document(
        self,
        account_id: str,
        doc_type: str,
        document: Dict[str, Any]
    ) -> bool:
        """Save a strategy document."""
        pass

class ObservabilityProvider(ABC):
    """Abstract interface for observability (W&B)."""
    
    @abstractmethod
    def init(self, project_name: str) -> None:
        """Initialize observability."""
        pass
    
    @abstractmethod
    def log_event(self, event_name: str, data: Dict[str, Any]) -> None:
        """Log an event."""
        pass

class AgentEngineProvider(ABC):
    """Abstract interface for Agent Engine operations."""
    
    @abstractmethod
    def create_runner(self, agent: Any, config: Dict[str, Any]) -> Any:
        """Create a runner for agent execution."""
        pass
```

### 2. Concrete Implementations

```python
# providers/firestore_impl.py
class FirestoreProviderImpl(FirestoreProvider):
    """Production Firestore implementation."""
    
    def __init__(self, project_id: Optional[str] = None):
        self.client = FirestoreClient(project_id=project_id)
    
    def get_best_practices(self, doc_type: str) -> Optional[str]:
        return get_best_practices_sync(doc_type)
    
    def get_reviewer_guidelines(self, doc_type: str) -> Optional[str]:
        return get_reviewer_guidelines_sync(doc_type)
    
    def save_document(
        self,
        account_id: str,
        doc_type: str,
        document: Dict[str, Any]
    ) -> bool:
        return save_strategy_document_sync(
            account_id=account_id,
            doc_type=doc_type,
            document=document,
            firestore_client=self.client
        )

# providers/mock_impl.py
class MockFirestoreProvider(FirestoreProvider):
    """Mock Firestore for testing."""
    
    def __init__(self):
        self.best_practices = {
            "business_strategy": '{"sections": ["overview", "analysis"]}',
            "competitive_strategy": '{"sections": ["competition", "positioning"]}'
        }
        self.saved_documents = []
    
    def get_best_practices(self, doc_type: str) -> Optional[str]:
        return self.best_practices.get(doc_type)
    
    def save_document(
        self,
        account_id: str,
        doc_type: str,
        document: Dict[str, Any]
    ) -> bool:
        self.saved_documents.append({
            "account_id": account_id,
            "doc_type": doc_type,
            "document": document
        })
        return True
```

### 3. Dependency Injection Container

```python
# providers/container.py
from typing import Optional

class DependencyContainer:
    """Container for managing dependencies."""
    
    def __init__(
        self,
        firestore_provider: Optional[FirestoreProvider] = None,
        observability_provider: Optional[ObservabilityProvider] = None,
        agent_engine_provider: Optional[AgentEngineProvider] = None
    ):
        # Use provided or create defaults
        self.firestore = firestore_provider or FirestoreProviderImpl()
        self.observability = observability_provider or WandBProvider()
        self.agent_engine = agent_engine_provider or AgentEngineProviderImpl()
    
    @classmethod
    def create_for_testing(cls) -> 'DependencyContainer':
        """Create container with mock dependencies for testing."""
        return cls(
            firestore_provider=MockFirestoreProvider(),
            observability_provider=MockObservabilityProvider(),
            agent_engine_provider=MockAgentEngineProvider()
        )
    
    @classmethod
    def create_for_production(cls, project_id: str) -> 'DependencyContainer':
        """Create container with production dependencies."""
        return cls(
            firestore_provider=FirestoreProviderImpl(project_id),
            observability_provider=WandBProvider(),
            agent_engine_provider=AgentEngineProviderImpl()
        )
```

### 4. Updated Agent Creation with DI

```python
# agents.py (refactored)
class StrategyAgentBuilder:
    """Builder for strategy agents with dependency injection."""
    
    def __init__(self, container: DependencyContainer):
        self.container = container
    
    def create_business_strategist(
        self,
        context: Optional[StrategyContext] = None
    ) -> Agent:
        """Create business strategist with injected dependencies."""
        # Get best practices from injected provider
        best_practices = self.container.firestore.get_best_practices("business_strategy")
        
        if not best_practices:
            best_practices = self._get_default_best_practices("business_strategy")
        
        instruction = self._build_instruction(
            agent_type="business_strategy",
            best_practices=best_practices,
            context=context
        )
        
        return Agent(
            name="business_strategist",
            model="gemini-2.5-pro",
            instruction=instruction,
            # ... other config
        )
    
    def _build_instruction(
        self,
        agent_type: str,
        best_practices: str,
        context: Optional[StrategyContext]
    ) -> str:
        """Build instruction with injected data."""
        # Instruction building logic here
        pass
```

### 5. Updated Orchestrator with DI

```python
# orchestrator.py (refactored)
class StrategyOrchestrator:
    """Orchestrator with dependency injection."""
    
    def __init__(self, container: DependencyContainer):
        self.container = container
        self.agent_builder = StrategyAgentBuilder(container)
    
    def execute_strategy_generation(
        self,
        company_name: str,
        industry: str,
        websites: str,
        customer_regions: str,
        annual_ad_budget: Optional[float] = None,
        account_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> str:
        """Execute strategy generation with injected dependencies."""
        try:
            # Initialize observability
            self.container.observability.init("ken-e-strategy-agent")
            
            # Create context
            context = self._create_context(
                company_name=company_name,
                industry=industry,
                websites=websites,
                customer_regions=customer_regions,
                annual_ad_budget=annual_ad_budget,
                account_id=account_id,
                tenant_id=tenant_id
            )
            
            # Create agents using builder
            agents = self._create_all_agents(context)
            
            # Execute with agent engine provider
            runner = self.container.agent_engine.create_runner(
                agent=SequentialAgent(sub_agents=agents),
                config={"app_name": "strategy-generator"}
            )
            
            events = runner.run(...)
            
            # Process and save documents
            documents = self._process_events(events)
            self._save_documents(documents, account_id)
            
            return self._format_success_message(documents)
            
        except Exception as e:
            self.container.observability.log_event("error", {"error": str(e)})
            return f"Failed: {e}"
```

## Usage Examples

### Production Usage
```python
# In production deployment
container = DependencyContainer.create_for_production(
    project_id="ken-e-prod"
)
orchestrator = StrategyOrchestrator(container)
result = orchestrator.execute_strategy_generation(...)
```

### Testing Usage
```python
# In tests
def test_strategy_generation():
    # Create test container with mocks
    container = DependencyContainer.create_for_testing()
    
    # Access mock to set expectations
    mock_firestore = container.firestore
    mock_firestore.best_practices["business_strategy"] = "test practices"
    
    # Run orchestrator with mocks
    orchestrator = StrategyOrchestrator(container)
    result = orchestrator.execute_strategy_generation(...)
    
    # Verify mock interactions
    assert len(mock_firestore.saved_documents) == 5
```

### Local Development
```python
# For local development with partial mocks
container = DependencyContainer(
    firestore_provider=FirestoreProviderImpl(),  # Real Firestore
    observability_provider=MockObservabilityProvider(),  # Mock W&B
    agent_engine_provider=MockAgentEngineProvider()  # Mock Agent Engine
)
```

## Benefits

### Testability
- ✅ Easy to mock external dependencies
- ✅ Unit tests don't require real services
- ✅ Can test error scenarios easily

### Flexibility
- ✅ Easy to swap implementations
- ✅ Can use different providers for different environments
- ✅ Supports gradual migration

### Maintainability
- ✅ Clear separation of concerns
- ✅ Dependencies are explicit
- ✅ Easy to add new providers

### Debugging
- ✅ Can inject logging providers
- ✅ Easy to trace dependency usage
- ✅ Can inject debug implementations

## Migration Strategy

### Phase 1: Create Interfaces
1. Define provider interfaces
2. Create mock implementations
3. Write tests using mocks

### Phase 2: Wrap Existing Code
1. Create concrete implementations wrapping existing code
2. No changes to existing functionality
3. Gradual introduction of DI

### Phase 3: Refactor Components
1. Update agent creation to use DI
2. Update orchestrator to use DI
3. Update tests to use DI

### Phase 4: Optimize
1. Remove old code paths
2. Optimize provider implementations
3. Add caching where appropriate

## Testing Strategy

### Unit Tests
```python
def test_agent_creation_with_mock_firestore():
    container = DependencyContainer.create_for_testing()
    builder = StrategyAgentBuilder(container)
    
    agent = builder.create_business_strategist(context)
    
    assert agent.name == "business_strategist"
    assert container.firestore.get_best_practices.called
```

### Integration Tests
```python
def test_end_to_end_with_real_firestore():
    container = DependencyContainer(
        firestore_provider=FirestoreProviderImpl(project_id="test-project"),
        observability_provider=MockObservabilityProvider(),
        agent_engine_provider=MockAgentEngineProvider()
    )
    
    orchestrator = StrategyOrchestrator(container)
    result = orchestrator.execute_strategy_generation(...)
    
    assert "Successfully generated" in result
```

## Conclusion

This dependency injection architecture provides:
1. **Better testability** through easy mocking
2. **Cleaner code** with explicit dependencies
3. **Flexibility** to swap implementations
4. **Maintainability** through separation of concerns

The migration can be done incrementally without breaking existing functionality.