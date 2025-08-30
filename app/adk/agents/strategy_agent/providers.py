"""
Dependency injection providers for strategy agents.
This module provides interfaces and implementations for external dependencies,
making the code more testable and maintainable.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import json

logger = logging.getLogger(__name__)


# ============================================================================
# ABSTRACT INTERFACES
# ============================================================================

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
        document: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> bool:
        """Save a strategy document."""
        pass


class ObservabilityProvider(ABC):
    """Abstract interface for observability (W&B)."""
    
    @abstractmethod
    def init(self, project_name: str) -> bool:
        """Initialize observability."""
        pass
    
    @abstractmethod
    def log_event(self, event_name: str, data: Dict[str, Any]) -> None:
        """Log an event."""
        pass


# ============================================================================
# PRODUCTION IMPLEMENTATIONS
# ============================================================================

class FirestoreProviderImpl(FirestoreProvider):
    """Production Firestore implementation."""
    
    def __init__(self, project_id: Optional[str] = None):
        """Initialize with optional project ID."""
        try:
            from .firestore import (
                FirestoreClient,
                get_best_practices_sync,
                get_reviewer_guidelines_sync,
                save_strategy_document_sync
            )
            self.client = FirestoreClient(project_id=project_id)
            self._get_best_practices_sync = get_best_practices_sync
            self._get_reviewer_guidelines_sync = get_reviewer_guidelines_sync
            self._save_strategy_document_sync = save_strategy_document_sync
            self.available = True
        except ImportError as e:
            logger.warning(f"Firestore not available: {e}")
            self.client = None
            self.available = False
    
    def get_best_practices(self, doc_type: str) -> Optional[str]:
        """Get best practices from Firestore."""
        if not self.available:
            return None
        try:
            return self._get_best_practices_sync(doc_type)
        except Exception as e:
            logger.error(f"Error getting best practices: {e}")
            return None
    
    def get_reviewer_guidelines(self, doc_type: str) -> Optional[str]:
        """Get reviewer guidelines from Firestore."""
        if not self.available:
            return None
        try:
            return self._get_reviewer_guidelines_sync(doc_type)
        except Exception as e:
            logger.error(f"Error getting reviewer guidelines: {e}")
            return None
    
    def save_document(
        self,
        account_id: str,
        doc_type: str,
        document: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> bool:
        """Save document to Firestore."""
        if not self.available:
            return False
        try:
            return self._save_strategy_document_sync(
                account_id=account_id,
                doc_type=doc_type,
                document=document,
                user_id=user_id or "default_user",
                firestore_client=self.client
            )
        except Exception as e:
            logger.error(f"Error saving document: {e}")
            return False


class WandBProvider(ObservabilityProvider):
    """Weights & Biases observability implementation."""
    
    def __init__(self):
        """Initialize W&B provider."""
        self.initialized = False
    
    def init(self, project_name: str) -> bool:
        """Initialize W&B."""
        try:
            import weave
            weave.init(project_name=project_name)
            self.initialized = True
            logger.info("W&B observability initialized")
            return True
        except Exception as e:
            logger.warning(f"W&B initialization failed: {e}")
            return False
    
    def log_event(self, event_name: str, data: Dict[str, Any]) -> None:
        """Log event to W&B."""
        if not self.initialized:
            return
        try:
            # In real implementation, would log to W&B
            logger.debug(f"W&B event: {event_name} - {data}")
        except Exception as e:
            logger.warning(f"Failed to log to W&B: {e}")


# ============================================================================
# MOCK IMPLEMENTATIONS FOR TESTING
# ============================================================================

class MockFirestoreProvider(FirestoreProvider):
    """Mock Firestore for testing."""
    
    def __init__(self):
        """Initialize mock with default data."""
        self.best_practices = {
            "business_strategy": json.dumps({
                "sections": ["overview", "market_analysis", "swot", "recommendations"],
                "required_fields": ["businessStrategySummary", "companyOverview"]
            }),
            "competitive_strategy": json.dumps({
                "sections": ["competition", "positioning", "differentiation"],
                "required_fields": ["competitiveAnalysis", "marketPosition"]
            }),
            "customer_strategy": json.dumps({
                "sections": ["personas", "journey", "insights"],
                "required_fields": ["customerPersonas", "customerJourney"]
            }),
            "marketing_strategy": json.dumps({
                "sections": ["campaigns", "channels", "metrics"],
                "required_fields": ["marketingCampaigns", "channelStrategy"]
            }),
            "brand_guidelines": json.dumps({
                "sections": ["identity", "voice", "visual"],
                "required_fields": ["brandIdentity", "brandVoice"]
            })
        }
        
        self.reviewer_guidelines = {
            "business_strategy": "Review for completeness and accuracy in business analysis",
            "competitive_strategy": "Ensure competitive analysis is thorough",
            "customer_strategy": "Verify customer insights are data-driven",
            "marketing_strategy": "Check marketing strategies are actionable",
            "brand_guidelines": "Ensure brand guidelines are consistent"
        }
        
        self.saved_documents = []
    
    def get_best_practices(self, doc_type: str) -> Optional[str]:
        """Get mock best practices."""
        return self.best_practices.get(doc_type)
    
    def get_reviewer_guidelines(self, doc_type: str) -> Optional[str]:
        """Get mock reviewer guidelines."""
        return self.reviewer_guidelines.get(doc_type)
    
    def save_document(
        self,
        account_id: str,
        doc_type: str,
        document: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> bool:
        """Save document to mock storage."""
        self.saved_documents.append({
            "account_id": account_id,
            "doc_type": doc_type,
            "document": document,
            "user_id": user_id or "default_user"
        })
        return True


class MockObservabilityProvider(ObservabilityProvider):
    """Mock observability for testing."""
    
    def __init__(self):
        """Initialize mock."""
        self.initialized = False
        self.events = []
    
    def init(self, project_name: str) -> bool:
        """Initialize mock observability."""
        self.initialized = True
        logger.info(f"Mock observability initialized for {project_name}")
        return True
    
    def log_event(self, event_name: str, data: Dict[str, Any]) -> None:
        """Log event to mock storage."""
        self.events.append({
            "event_name": event_name,
            "data": data
        })


# ============================================================================
# DEPENDENCY CONTAINER
# ============================================================================

class DependencyContainer:
    """Container for managing dependencies."""
    
    def __init__(
        self,
        firestore_provider: Optional[FirestoreProvider] = None,
        observability_provider: Optional[ObservabilityProvider] = None
    ):
        """
        Initialize container with providers.
        
        Args:
            firestore_provider: Firestore provider instance
            observability_provider: Observability provider instance
        """
        # Use provided or create defaults
        self.firestore = firestore_provider or FirestoreProviderImpl()
        self.observability = observability_provider or WandBProvider()
    
    @classmethod
    def create_for_testing(cls) -> 'DependencyContainer':
        """
        Create container with mock dependencies for testing.
        
        Returns:
            DependencyContainer with mock providers
        """
        return cls(
            firestore_provider=MockFirestoreProvider(),
            observability_provider=MockObservabilityProvider()
        )
    
    @classmethod
    def create_for_production(cls, project_id: Optional[str] = None) -> 'DependencyContainer':
        """
        Create container with production dependencies.
        
        Args:
            project_id: GCP project ID for Firestore
            
        Returns:
            DependencyContainer with production providers
        """
        return cls(
            firestore_provider=FirestoreProviderImpl(project_id),
            observability_provider=WandBProvider()
        )
    
    @classmethod
    def create_for_local_dev(cls) -> 'DependencyContainer':
        """
        Create container for local development.
        Uses real Firestore but mock observability.
        
        Returns:
            DependencyContainer for local development
        """
        return cls(
            firestore_provider=FirestoreProviderImpl(),
            observability_provider=MockObservabilityProvider()
        )


# ============================================================================
# AGENT BUILDER WITH DEPENDENCY INJECTION
# ============================================================================

class StrategyAgentBuilder:
    """Builder for strategy agents with dependency injection."""
    
    def __init__(self, container: DependencyContainer):
        """
        Initialize builder with dependency container.
        
        Args:
            container: DependencyContainer with providers
        """
        self.container = container
    
    def get_best_practices_with_fallback(self, doc_type: str) -> str:
        """
        Get best practices with fallback to defaults.
        
        Args:
            doc_type: Type of document
            
        Returns:
            Best practices string
        """
        best_practices = self.container.firestore.get_best_practices(doc_type)
        
        if not best_practices:
            # Fallback to default
            logger.warning(f"Using default best practices for {doc_type}")
            best_practices = json.dumps({
                "sections": ["overview", "analysis", "recommendations"],
                "default": True
            })
        
        return best_practices
    
    def get_reviewer_guidelines_with_fallback(self, doc_type: str) -> str:
        """
        Get reviewer guidelines with fallback to defaults.
        
        Args:
            doc_type: Type of document
            
        Returns:
            Reviewer guidelines string
        """
        guidelines = self.container.firestore.get_reviewer_guidelines(doc_type)
        
        if not guidelines:
            # Fallback to default
            logger.warning(f"Using default reviewer guidelines for {doc_type}")
            guidelines = f"Review the {doc_type.replace('_', ' ')} for completeness and accuracy."
        
        return guidelines