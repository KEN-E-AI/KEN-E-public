"""
Firestore operations for V3 Strategy Agent System.
Consolidates all Firestore access into a single module with proper dependency injection.
"""

import json
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime
from google.cloud import firestore

logger = logging.getLogger(__name__)


class FirestoreClient:
    """Manages Firestore operations with proper dependency injection."""
    
    def __init__(self, project_id: Optional[str] = None, client: Optional[firestore.Client] = None):
        """
        Initialize with either a project ID or an existing client.
        
        Args:
            project_id: GCP project ID
            client: Existing Firestore client (for testing)
        """
        if client:
            self.db = client
        else:
            project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
            try:
                self.db = firestore.Client(project=project_id)
                logger.info(f"Firestore client initialized with project: {project_id}")
            except Exception as e:
                logger.warning(f"Could not initialize Firestore client: {e}")
                self.db = None
    
    def is_initialized(self) -> bool:
        """Check if the Firestore client is initialized."""
        return self.db is not None

    # ============================================================================
    # Template and Guidelines Operations
    # ============================================================================

    async def get_best_practices(self, doc_type: str) -> Optional[str]:
        """
        Retrieve best practices template from Firestore.
        
        Args:
            doc_type: Type of strategy document (e.g., 'business_strategy')
            
        Returns:
            Best practices JSON schema as string, or None if not found
        """
        if not self.db:
            logger.warning("No Firestore client available, using placeholder best practices")
            return json.dumps({
                "structure": f"Placeholder best practices for {doc_type}",
                "note": "Real template should be loaded from Firestore"
            })
        
        try:
            doc_path = f"{doc_type}_best_practices"
            doc_ref = self.db.collection("strategy_doc_guides").document(doc_path)
            doc = doc_ref.get()
            
            if doc.exists:
                doc_data = doc.to_dict()
                content = json.dumps(doc_data, indent=2)
                logger.info(f"Retrieved best practices for {doc_type} - {len(doc_data)} sections, {len(content)} chars")
                return content
            else:
                logger.warning(f"Best practices not found for {doc_type} at path: strategy_doc_guides/{doc_path}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to retrieve best practices for {doc_type}: {e}")
            return None

    def get_best_practices_sync(self, doc_type: str) -> Optional[str]:
        """
        Synchronous version to retrieve best practices template from Firestore.
        """
        if not self.db:
            logger.warning("No Firestore client available, using placeholder best practices")
            return json.dumps({
                "structure": f"Placeholder best practices for {doc_type}",
                "note": "Real template should be loaded from Firestore"
            })
        
        try:
            doc_path = f"{doc_type}_best_practices"
            doc_ref = self.db.collection("strategy_doc_guides").document(doc_path)
            doc = doc_ref.get()
            
            if doc.exists:
                doc_data = doc.to_dict()
                content = json.dumps(doc_data, indent=2)
                logger.info(f"Retrieved best practices for {doc_type} - {len(doc_data)} sections, {len(content)} chars")
                return content
            else:
                logger.warning(f"Best practices not found for {doc_type} at path: strategy_doc_guides/{doc_path}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to retrieve best practices for {doc_type}: {e}")
            return None

    async def get_reviewer_guidelines(self, doc_type: str) -> Optional[str]:
        """
        Retrieve reviewer guidelines from Firestore.
        """
        if not self.db:
            logger.warning("No Firestore client available, using placeholder reviewer guidelines")
            return f"Placeholder reviewer guidelines for {doc_type}. Real guidelines should be loaded from Firestore."
        
        try:
            doc_path = f"{doc_type}_reviewer_guidelines"
            doc_ref = self.db.collection("strategy_doc_guides").document(doc_path)
            doc = doc_ref.get()
            
            if doc.exists:
                doc_data = doc.to_dict()
                content = json.dumps(doc_data, indent=2)
                logger.info(f"Retrieved reviewer guidelines for {doc_type} - {len(doc_data)} criteria, {len(content)} chars")
                return content
            else:
                logger.warning(f"Reviewer guidelines not found for {doc_type} at path: strategy_doc_guides/{doc_path}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to retrieve reviewer guidelines for {doc_type}: {e}")
            return None

    def get_reviewer_guidelines_sync(self, doc_type: str) -> Optional[str]:
        """
        Synchronous version to retrieve reviewer guidelines from Firestore.
        """
        if not self.db:
            logger.warning("No Firestore client available, using placeholder reviewer guidelines")
            return f"Placeholder reviewer guidelines for {doc_type}. Real guidelines should be loaded from Firestore."
        
        try:
            doc_path = f"{doc_type}_reviewer_guidelines"
            doc_ref = self.db.collection("strategy_doc_guides").document(doc_path)
            doc = doc_ref.get()
            
            if doc.exists:
                doc_data = doc.to_dict()
                content = json.dumps(doc_data, indent=2)
                logger.info(f"Retrieved reviewer guidelines for {doc_type} - {len(doc_data)} criteria, {len(content)} chars")
                return content
            else:
                logger.warning(f"Reviewer guidelines not found for {doc_type} at path: strategy_doc_guides/{doc_path}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to retrieve reviewer guidelines for {doc_type}: {e}")
            return None

    # ============================================================================
    # Document Storage Operations
    # ============================================================================

    def save_strategy_document_sync(
        self,
        account_id: str,
        doc_type: str,
        content: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> bool:
        """
        Synchronous version to save a strategy document to Firestore.
        This is needed for use in Agent Engine context.
        
        Args:
            account_id: Account ID for document scoping
            doc_type: Type of strategy document
            content: Document content as dictionary
            user_id: Optional user ID for attribution
            
        Returns:
            Success status
        """
        logger.info(f"[FIRESTORE_SAVE] Starting sync save for {doc_type} - account: {account_id}")
        
        if not self.db:
            logger.error("[FIRESTORE_SAVE] No Firestore client available")
            return False
        
        try:
            # Log content size and structure
            logger.info(f"[FIRESTORE_SAVE] Content size: {len(str(content))} chars")
            logger.info(f"[FIRESTORE_SAVE] Content keys: {list(content.keys()) if isinstance(content, dict) else 'not a dict'}")
            
            # Prepare document data
            doc_data = {
                "content": content,
                "doc_type": doc_type,
                "account_id": account_id,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "created_by": user_id or "system",
                "version": 1
            }
            
            # Save to account-specific collection
            collection_name = f"strategy_docs_{account_id}"
            logger.info(f"[FIRESTORE_SAVE] Saving to collection: {collection_name}, document: {doc_type}")
            
            doc_ref = self.db.collection(collection_name).document(doc_type)
            doc_ref.set(doc_data)
            
            logger.info(f"[FIRESTORE_SAVE] Successfully saved {doc_type} document for account {account_id}")
            return True
            
        except Exception as e:
            logger.error(f"[FIRESTORE_SAVE] Failed to save strategy document: {e}")
            import traceback
            logger.error(f"[FIRESTORE_SAVE] Traceback: {traceback.format_exc()}")
            return False

    async def save_strategy_document(
        self,
        account_id: str,
        doc_type: str,
        content: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> bool:
        """
        Save a strategy document to Firestore.
        """
        logger.info(f"[FIRESTORE_SAVE] Starting save for {doc_type} - account: {account_id}")
        
        if not self.db:
            logger.error("[FIRESTORE_SAVE] No Firestore client available")
            return False
        
        try:
            # Prepare document data
            doc_data = {
                "content": content,
                "doc_type": doc_type,
                "account_id": account_id,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "created_by": user_id or "system",
                "version": 1
            }
            
            # Save to account-specific collection
            collection_name = f"strategy_docs_{account_id}"
            doc_ref = self.db.collection(collection_name).document(doc_type)
            doc_ref.set(doc_data)
            
            logger.info(f"[FIRESTORE_SAVE] Successfully saved {doc_type} document for account {account_id}")
            return True
            
        except Exception as e:
            logger.error(f"[FIRESTORE_SAVE] Failed to save strategy document: {e}")
            return False

    async def get_strategy_document(
        self,
        account_id: str,
        doc_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a strategy document from Firestore.
        """
        if not self.db:
            logger.warning("No Firestore client available, cannot retrieve document")
            return None
        
        try:
            collection_name = f"strategy_docs_{account_id}"
            doc_ref = self.db.collection(collection_name).document(doc_type)
            doc = doc_ref.get()
            
            if doc.exists:
                doc_data = doc.to_dict()
                content = doc_data.get("content", {})
                logger.info(f"Retrieved {doc_type} document for account {account_id}")
                return content
            else:
                logger.info(f"No existing {doc_type} document found for account {account_id}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to retrieve strategy document: {e}")
            return None

    async def update_strategy_document(
        self,
        account_id: str,
        doc_type: str,
        content: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> bool:
        """
        Update an existing strategy document in Firestore.
        """
        if not self.db:
            logger.warning("No Firestore client available, document not updated")
            return False
        
        try:
            collection_name = f"strategy_docs_{account_id}"
            doc_ref = self.db.collection(collection_name).document(doc_type)
            existing_doc = doc_ref.get()
            
            version = 1
            if existing_doc.exists:
                existing_data = existing_doc.to_dict()
                version = existing_data.get("version", 0) + 1
            
            # Update document
            doc_data = {
                "content": content,
                "doc_type": doc_type,
                "account_id": account_id,
                "updated_at": datetime.utcnow(),
                "updated_by": user_id or "system",
                "version": version
            }
            
            if not existing_doc.exists:
                doc_data["created_at"] = datetime.utcnow()
                doc_data["created_by"] = user_id or "system"
            
            doc_ref.set(doc_data, merge=True)
            
            logger.info(f"Updated {doc_type} document for account {account_id} to version {version}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update strategy document: {e}")
            return False


# ============================================================================
# Default Client Instance and Legacy Support Functions
# ============================================================================

# Create a default client instance for backward compatibility
_default_client: Optional[FirestoreClient] = None

def get_default_client() -> FirestoreClient:
    """Get or create the default Firestore client."""
    global _default_client
    if _default_client is None:
        _default_client = FirestoreClient()
    return _default_client

def initialize_firestore(project_id: str):
    """Initialize the default Firestore client with a specific project."""
    global _default_client
    _default_client = FirestoreClient(project_id=project_id)
    logger.info(f"Default Firestore client initialized with project: {project_id}")

# Legacy function wrappers for backward compatibility
def get_best_practices_sync(doc_type: str) -> Optional[str]:
    """Legacy wrapper for get_best_practices_sync."""
    return get_default_client().get_best_practices_sync(doc_type)

# Alias for backward compatibility - agents.py expects this name
get_best_practices = get_best_practices_sync

def get_reviewer_guidelines_sync(doc_type: str) -> Optional[str]:
    """Legacy wrapper for get_reviewer_guidelines_sync."""
    return get_default_client().get_reviewer_guidelines_sync(doc_type)

# Alias for backward compatibility - agents.py expects this name
get_reviewer_guidelines = get_reviewer_guidelines_sync

def save_strategy_document_sync(
    account_id: str,
    doc_type: str,
    content: Dict[str, Any],
    user_id: Optional[str] = None
) -> bool:
    """Legacy wrapper for save_strategy_document_sync."""
    return get_default_client().save_strategy_document_sync(account_id, doc_type, content, user_id)

async def save_strategy_document(
    account_id: str,
    doc_type: str,
    content: Dict[str, Any],
    user_id: Optional[str] = None
) -> bool:
    """Legacy wrapper for save_strategy_document."""
    return await get_default_client().save_strategy_document(account_id, doc_type, content, user_id)

async def get_strategy_document(
    account_id: str,
    doc_type: str
) -> Optional[Dict[str, Any]]:
    """Legacy wrapper for get_strategy_document."""
    return await get_default_client().get_strategy_document(account_id, doc_type)

async def update_strategy_document(
    account_id: str,
    doc_type: str,
    content: Dict[str, Any],
    user_id: Optional[str] = None
) -> bool:
    """Legacy wrapper for update_strategy_document."""
    return await get_default_client().update_strategy_document(account_id, doc_type, content, user_id)


# ============================================================================
# Context Management Operations
# ============================================================================

from .models import StrategyContext

class ContextManager:
    """Manages strategy context persistence and retrieval."""
    
    def __init__(self, firestore_client: Optional[FirestoreClient] = None):
        """Initialize context manager with optional Firestore client."""
        self.client = firestore_client or get_default_client()
        
    async def save_context(self, context: StrategyContext) -> bool:
        """
        Save strategy context to Firestore for persistence.
        """
        if not self.client.is_initialized():
            logger.warning("No Firestore client available, context not saved")
            return False
        
        try:
            context_data = context.model_dump()
            context_data["last_updated"] = datetime.utcnow()
            
            # Save to Firestore
            doc_ref = self.client.db.collection(f"strategy_processing_state_{context.account_id}").document("current_state")
            doc_ref.set(context_data)
            
            logger.info(f"Saved strategy context for account {context.account_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save strategy context: {e}")
            return False
    
    async def get_context(self, account_id: str) -> Optional[StrategyContext]:
        """
        Retrieve strategy context from Firestore.
        """
        if not self.client.is_initialized():
            logger.warning("No Firestore client available, cannot retrieve context")
            return None
        
        try:
            doc_ref = self.client.db.collection(f"strategy_processing_state_{account_id}").document("current_state")
            doc = doc_ref.get()
            
            if doc.exists:
                context_data = doc.to_dict()
                # Remove Firestore-specific fields
                context_data.pop("last_updated", None)
                
                # Reconstruct StrategyContext
                context = StrategyContext(**context_data)
                logger.info(f"Retrieved strategy context for account {account_id}")
                return context
            else:
                logger.info(f"No existing strategy context found for account {account_id}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to retrieve strategy context: {e}")
            return None


# Create a global context manager instance
context_manager = ContextManager()


# ============================================================================
# Utility Functions
# ============================================================================

def parse_json_response(response_text: str) -> Optional[Dict[str, Any]]:
    """
    Parse JSON from agent response text.
    Handles cases where agent might include non-JSON text.
    """
    if not response_text:
        return None
    
    # Try direct JSON parsing first
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass
    
    # Try to find JSON in the text
    start_markers = ['{', '[']
    end_markers = ['}', ']']
    
    for start_marker in start_markers:
        if start_marker in response_text:
            start_idx = response_text.index(start_marker)
            
            for end_marker in end_markers:
                if end_marker in response_text:
                    end_idx = response_text.rfind(end_marker)
                    
                    try:
                        json_str = response_text[start_idx:end_idx+1]
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        continue
    
    logger.warning("Could not parse JSON from agent response")
    return None


def extract_field_requirements_from_best_practices(best_practices_json: str) -> str:
    """
    Extract field names from best practices JSON to create OUTPUT REQUIREMENTS.
    """
    try:
        import json
        best_practices = json.loads(best_practices_json)
        
        requirements = []
        requirements.append("# OUTPUT REQUIREMENTS")
        requirements.append("Your response must be ONLY a complete JSON document with ALL these exact fields:")
        requirements.append("")
        
        # List all required field names
        for field_name in best_practices.keys():
            requirements.append(f"- {field_name}")
        
        requirements.append("")
        requirements.append("IMPORTANT: Each field MUST follow the EXACT description provided in the BEST PRACTICES section above.")
        requirements.append("The BEST PRACTICES section contains the complete requirements for what each field should contain.")
        requirements.append("DO NOT skip any fields. DO NOT add extra fields. Output ONLY the JSON document.")
        
        return "\n".join(requirements)
    except Exception as e:
        logger.error(f"Failed to extract field requirements: {e}")
        return """# OUTPUT REQUIREMENTS
Your response must be ONLY a complete JSON document following the BEST PRACTICES structure above.
Include ALL fields defined in the BEST PRACTICES document.
DO NOT include any conversational text, only output the JSON document."""


def extract_validation_criteria_from_guidelines(guidelines_json: str, best_practices_json: str) -> str:
    """
    Extract validation criteria from reviewer guidelines and best practices.
    """
    try:
        import json
        guidelines = json.loads(guidelines_json)
        best_practices = json.loads(best_practices_json)
        
        criteria = []
        criteria.append("# VALIDATION PROCESS")
        criteria.append(f"1. Check that ALL {len(best_practices)} required fields are present:")
        
        # List expected fields
        for field_name in best_practices.keys():
            criteria.append(f"   - {field_name}")
        
        criteria.append("")
        criteria.append("2. For EACH field, verify it matches the requirements in REVIEWER GUIDELINES above")
        criteria.append("3. Ensure all content is specific to the company, not generic")
        criteria.append("4. Verify all sections have substantial content (not placeholders)")
        criteria.append("")
        
        # Add specific guidelines if present
        if isinstance(guidelines, dict) and 'guidelines' in guidelines:
            criteria.append("# SPECIFIC REVIEW CRITERIA")
            criteria.append(guidelines['guidelines'])
        
        return "\n".join(criteria)
    except Exception as e:
        logger.error(f"Failed to extract validation criteria: {e}")
        return "Validate the document against the reviewer guidelines and best practices provided above."


def format_new_information(
    company_name: str,
    websites: list,
    industry: str,
    customer_regions: list,
    annual_ad_budget: Optional[float] = None,
    supporting_documents: Optional[list] = None
) -> str:
    """
    Format new information for agent prompt.
    """
    info = f"""Company to analyze: {company_name}
Company websites: {websites}
Industry: {industry}
Customer regions: {', '.join(customer_regions)}"""
    
    if annual_ad_budget:
        info += f"\nEstimated annual ad budget: ${annual_ad_budget:,.2f}"
    
    if supporting_documents:
        info += f"\nSupporting documents: {supporting_documents}"
    
    return info