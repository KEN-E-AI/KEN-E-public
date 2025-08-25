"""
Context management for V3 Strategy Agent System.
Handles state persistence and context passing between agents.
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from google.cloud import firestore
import os

# Use absolute imports for deployment, fall back to relative for local testing
try:
    from agents.strategy_agent.models import StrategyContext
except ImportError:
    from .models import StrategyContext

logger = logging.getLogger(__name__)

# Auto-initialize Firestore client when module loads
# This ensures it works in Agent Engine context
try:
    # Get project ID from environment if available, otherwise let Firestore auto-detect
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
    db = firestore.Client(project=project_id)
    logger.info(f"Firestore client auto-initialized in context with project: {project_id}")
except Exception as e:
    logger.warning(f"Could not auto-initialize Firestore in context: {e}")
    db = None


def initialize_firestore(project_id: str):
    """Initialize Firestore client with the given project ID."""
    global db
    if not db:
        try:
            db = firestore.Client(project=project_id)
            logger.info(f"Firestore client initialized for context management with project: {project_id}")
        except Exception as e:
            logger.error(f"Failed to initialize Firestore client with project {project_id}: {e}")
            raise


class ContextManager:
    """Manages strategy context persistence and retrieval."""
    
    def __init__(self, firestore_client=None):
        """Initialize context manager with optional Firestore client."""
        self.db = firestore_client or db
        
    async def save_context(self, context: StrategyContext) -> bool:
        """
        Save strategy context to Firestore for persistence.
        
        Args:
            context: StrategyContext object to save
            
        Returns:
            Success status
        """
        # Try to initialize Firestore if not already done
        if not self.db:
            try:
                import os
                project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID") or os.getenv("GCP_PROJECT") or "ken-e-dev"
                self.db = firestore.Client(project=project_id)
            except:
                try:
                    self.db = firestore.Client()
                except:
                    try:
                        self.db = firestore.Client(project="ken-e-dev")
                    except:
                        return False
        
        if not self.db:
            return False
            
        try:
            # Convert context to dict
            context_data = context.dict()
            
            # Add metadata
            context_data["last_updated"] = datetime.utcnow()
            
            # Save to Firestore
            doc_ref = self.db.collection(f"strategy_processing_state_{context.account_id}").document("current_state")
            doc_ref.set(context_data)
            
            logger.info(f"Context saved for account {context.account_id} at stage {context.current_stage}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save context: {e}")
            return False
    
    async def load_context(self, account_id: str) -> Optional[StrategyContext]:
        """
        Load strategy context from Firestore.
        
        Args:
            account_id: Account ID to load context for
            
        Returns:
            StrategyContext if found, None otherwise
        """
        if not self.db:
            logger.warning("No Firestore client available, cannot load context")
            return None
            
        try:
            # Load from Firestore
            doc_ref = self.db.collection(f"strategy_processing_state_{account_id}").document("current_state")
            doc = doc_ref.get()
            
            if not doc.exists:
                logger.info(f"No existing context found for account {account_id}")
                return None
            
            # Convert to StrategyContext
            context_data = doc.to_dict()
            context = StrategyContext(**context_data)
            
            logger.info(f"Context loaded for account {account_id} at stage {context.current_stage}")
            return context
            
        except Exception as e:
            logger.error(f"Failed to load context: {e}")
            return None
    
    async def clear_context(self, account_id: str) -> bool:
        """
        Clear strategy context from Firestore (used after completion).
        
        Args:
            account_id: Account ID to clear context for
            
        Returns:
            Success status
        """
        if not self.db:
            logger.warning("No Firestore client available, context not cleared")
            return False
            
        try:
            # Delete the document
            doc_ref = self.db.collection(f"strategy_processing_state_{account_id}").document("current_state")
            doc_ref.delete()
            
            logger.info(f"Context cleared for account {account_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear context: {e}")
            return False
    
    def create_initial_context(
        self,
        account_id: str,
        company_name: str,
        websites: list,
        industry: str,
        customer_regions: list,
        annual_ad_budget: Optional[float] = None,
        supporting_documents: Optional[list] = None,
        user_id: Optional[str] = None
    ) -> StrategyContext:
        """
        Create initial context for strategy generation.
        
        Args:
            account_id: Account ID
            company_name: Company name to analyze
            websites: Company websites
            industry: Industry description
            customer_regions: Target regions
            annual_ad_budget: Optional ad budget
            supporting_documents: Optional supporting docs
            user_id: Optional user ID
            
        Returns:
            Initialized StrategyContext
        """
        return StrategyContext(
            account_id=account_id,
            user_id=user_id,
            company_name=company_name,
            websites=websites,
            industry=industry,
            customer_regions=customer_regions,
            annual_ad_budget=annual_ad_budget,
            supporting_documents=supporting_documents,
            started_at=datetime.utcnow()
        )
    
    def format_previous_outputs_for_prompt(self, outputs: Dict[str, Any]) -> str:
        """
        Format previous agent outputs for inclusion in prompt.
        
        Args:
            outputs: Dictionary of previous outputs
            
        Returns:
            Formatted string for prompt
        """
        if not outputs:
            return ""
        
        formatted = "You have been provided with the following information from previous strategy documents:\n"
        
        for key, value in outputs.items():
            if value is not None:
                # Convert complex structures to JSON strings
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, indent=2)
                formatted += f'  - {key}: "{value}"\n'
        
        return formatted
    
    async def update_account_status(self, account_id: str, status: str, stage: Optional[str] = None) -> bool:
        """
        Update account setup status in the main accounts collection.
        
        Args:
            account_id: Account ID
            status: Status to set (pending, processing, ready)
            stage: Optional current stage name
            
        Returns:
            Success status
        """
        if not self.db:
            logger.warning("No Firestore client available, status not updated")
            return False
            
        try:
            # Update account document
            doc_ref = self.db.collection("accounts").document(account_id)
            
            update_data = {
                "setup_status": status,
                "setup_updated_at": datetime.utcnow()
            }
            
            if stage:
                update_data["setup_stage"] = stage
            
            doc_ref.update(update_data)
            
            logger.info(f"Account {account_id} status updated to {status}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update account status: {e}")
            return False


# Global context manager instance
context_manager = ContextManager()