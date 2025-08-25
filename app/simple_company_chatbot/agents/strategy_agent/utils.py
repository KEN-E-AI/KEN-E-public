"""
Utility functions for V3 Strategy Agent System.
Handles Firestore access for templates and document storage.
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from google.cloud import firestore
import os

logger = logging.getLogger(__name__)

# Auto-initialize Firestore client when module loads
# This ensures it works in Agent Engine context where initialize_firestore might not be called
try:
    # Get project ID from environment if available, otherwise let Firestore auto-detect
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
    db = firestore.Client(project=project_id)
    logger.info(f"Firestore client auto-initialized with project: {project_id}")
except Exception as e:
    logger.warning(f"Could not auto-initialize Firestore: {e}")
    db = None


def initialize_firestore(project_id: str):
    """Initialize Firestore client with the given project ID."""
    global db
    if not db:
        try:
            db = firestore.Client(project=project_id)
            logger.info(f"Firestore client initialized with project: {project_id}")
        except Exception as e:
            logger.error(f"Failed to initialize Firestore client with project {project_id}: {e}")
            raise


async def get_best_practices(doc_type: str) -> Optional[str]:
    """
    Retrieve best practices template from Firestore.
    
    Args:
        doc_type: Type of strategy document (e.g., 'business_strategy')
        
    Returns:
        Best practices JSON schema as string, or None if not found
    """
    if not db:
        logger.warning("No Firestore client available, using placeholder best practices")
        return json.dumps({
            "structure": f"Placeholder best practices for {doc_type}",
            "note": "Real template should be loaded from Firestore"
        })
    
    try:
        # Fetch from Firestore path specified in Excel
        doc_path = f"{doc_type}_best_practices"
        doc_ref = db.collection("strategy_doc_guides").document(doc_path)
        doc = doc_ref.get()
        
        if doc.exists:
            doc_data = doc.to_dict()
            # The entire document IS the best practices (fields are the sections)
            # Convert to a formatted string for the agent to use
            content = json.dumps(doc_data, indent=2)
            logger.info(f"Retrieved best practices for {doc_type} - {len(doc_data)} sections, {len(content)} chars")
            return content
        else:
            logger.warning(f"Best practices not found for {doc_type} at path: strategy_doc_guides/{doc_path}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to retrieve best practices for {doc_type}: {e}")
        return None


async def get_reviewer_guidelines(doc_type: str) -> Optional[str]:
    """
    Retrieve reviewer guidelines from Firestore.
    
    Args:
        doc_type: Type of strategy document (e.g., 'business_strategy')
        
    Returns:
        Reviewer guidelines as string, or None if not found
    """
    if not db:
        logger.warning("No Firestore client available, using placeholder reviewer guidelines")
        return f"Placeholder reviewer guidelines for {doc_type}. Real guidelines should be loaded from Firestore."
    
    try:
        # Fetch from Firestore path specified in Excel
        doc_path = f"{doc_type}_reviewer_guidelines"
        doc_ref = db.collection("strategy_doc_guides").document(doc_path)
        doc = doc_ref.get()
        
        if doc.exists:
            doc_data = doc.to_dict()
            # The entire document IS the reviewer guidelines (fields are the criteria)
            # Convert to a formatted string for the agent to use
            content = json.dumps(doc_data, indent=2)
            logger.info(f"Retrieved reviewer guidelines for {doc_type} - {len(doc_data)} criteria, {len(content)} chars")
            return content
        else:
            logger.warning(f"Reviewer guidelines not found for {doc_type} at path: strategy_doc_guides/{doc_path}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to retrieve reviewer guidelines for {doc_type}: {e}")
        return None


def get_best_practices_sync(doc_type: str) -> Optional[str]:
    """
    Synchronous version to retrieve best practices template from Firestore.
    
    Args:
        doc_type: Type of strategy document (e.g., 'business_strategy')
        
    Returns:
        Best practices JSON schema as string, or None if not found
    """
    global db
    
    if not db:
        logger.warning("No Firestore client available, using placeholder best practices")
        return json.dumps({
            "structure": f"Placeholder best practices for {doc_type}",
            "note": "Real template should be loaded from Firestore"
        })
    
    try:
        # Fetch from Firestore path specified in Excel
        doc_path = f"{doc_type}_best_practices"
        doc_ref = db.collection("strategy_doc_guides").document(doc_path)
        doc = doc_ref.get()
        
        if doc.exists:
            doc_data = doc.to_dict()
            # The entire document IS the best practices (fields are the sections)
            # Convert to a formatted string for the agent to use
            content = json.dumps(doc_data, indent=2)
            logger.info(f"Retrieved best practices for {doc_type} - {len(doc_data)} sections, {len(content)} chars")
            return content
        else:
            logger.warning(f"Best practices not found for {doc_type} at path: strategy_doc_guides/{doc_path}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to retrieve best practices for {doc_type}: {e}")
        return None


def get_reviewer_guidelines_sync(doc_type: str) -> Optional[str]:
    """
    Synchronous version to retrieve reviewer guidelines from Firestore.
    
    Args:
        doc_type: Type of strategy document (e.g., 'business_strategy')
        
    Returns:
        Reviewer guidelines as string, or None if not found
    """
    global db
    
    if not db:
        logger.warning("No Firestore client available, using placeholder reviewer guidelines")
        return f"Placeholder reviewer guidelines for {doc_type}. Real guidelines should be loaded from Firestore."
    
    try:
        # Fetch from Firestore path specified in Excel
        doc_path = f"{doc_type}_reviewer_guidelines"
        doc_ref = db.collection("strategy_doc_guides").document(doc_path)
        doc = doc_ref.get()
        
        if doc.exists:
            doc_data = doc.to_dict()
            # The entire document IS the reviewer guidelines (fields are the criteria)
            # Convert to a formatted string for the agent to use
            content = json.dumps(doc_data, indent=2)
            logger.info(f"Retrieved reviewer guidelines for {doc_type} - {len(doc_data)} criteria, {len(content)} chars")
            return content
        else:
            logger.warning(f"Reviewer guidelines not found for {doc_type} at path: strategy_doc_guides/{doc_path}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to retrieve reviewer guidelines for {doc_type}: {e}")
        return None


def save_strategy_document_sync(
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
    global db
    
    logger.info(f"[FIRESTORE_SAVE] Starting sync save for {doc_type} - account: {account_id}")
    logger.info(f"[FIRESTORE_SAVE] Current db client: {db}")
    
    # Try to initialize Firestore if not already done
    if not db:
        logger.info("[FIRESTORE_SAVE] DB client is None, attempting initialization...")
        try:
            # Try multiple approaches to initialize Firestore
            import os
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID") or os.getenv("GCP_PROJECT") or "ken-e-dev"
            logger.info(f"[FIRESTORE_SAVE] Attempting to create client with project: {project_id}")
            db = firestore.Client(project=project_id)
            logger.info(f"[FIRESTORE_SAVE] Successfully created client: {db}")
        except Exception as e1:
            logger.error(f"[FIRESTORE_SAVE] First attempt failed: {e1}")
            try:
                # Fallback to auto-detection
                logger.info("[FIRESTORE_SAVE] Trying auto-detection...")
                db = firestore.Client()
                logger.info(f"[FIRESTORE_SAVE] Auto-detection successful: {db}")
            except Exception as e2:
                logger.error(f"[FIRESTORE_SAVE] Auto-detection failed: {e2}")
                # Last resort - hardcode the project
                try:
                    logger.info("[FIRESTORE_SAVE] Last resort - hardcoded project...")
                    db = firestore.Client(project="ken-e-dev")
                    logger.info(f"[FIRESTORE_SAVE] Hardcoded project successful: {db}")
                except Exception as e3:
                    logger.error(f"[FIRESTORE_SAVE] All initialization attempts failed: {e3}")
                    return False
    
    if not db:
        logger.error("[FIRESTORE_SAVE] No Firestore client available after all attempts")
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
        
        doc_ref = db.collection(collection_name).document(doc_type)
        doc_ref.set(doc_data)
        
        logger.info(f"[FIRESTORE_SAVE] Successfully saved {doc_type} document for account {account_id}")
        return True
        
    except Exception as e:
        logger.error(f"[FIRESTORE_SAVE] Failed to save strategy document: {e}")
        import traceback
        logger.error(f"[FIRESTORE_SAVE] Traceback: {traceback.format_exc()}")
        return False


async def save_strategy_document(
    account_id: str,
    doc_type: str,
    content: Dict[str, Any],
    user_id: Optional[str] = None
) -> bool:
    """
    Save a strategy document to Firestore.
    
    Args:
        account_id: Account ID for document scoping
        doc_type: Type of strategy document
        content: Document content as dictionary
        user_id: Optional user ID for attribution
        
    Returns:
        Success status
    """
    global db
    
    logger.info(f"[FIRESTORE_SAVE] Starting save for {doc_type} - account: {account_id}")
    logger.info(f"[FIRESTORE_SAVE] Current db client: {db}")
    
    # Try to initialize Firestore if not already done
    if not db:
        logger.info("[FIRESTORE_SAVE] DB client is None, attempting initialization...")
        try:
            # Try multiple approaches to initialize Firestore
            import os
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID") or os.getenv("GCP_PROJECT") or "ken-e-dev"
            logger.info(f"[FIRESTORE_SAVE] Attempting to create client with project: {project_id}")
            db = firestore.Client(project=project_id)
            logger.info(f"[FIRESTORE_SAVE] Successfully created client: {db}")
        except Exception as e1:
            logger.error(f"[FIRESTORE_SAVE] First attempt failed: {e1}")
            try:
                # Fallback to auto-detection
                logger.info("[FIRESTORE_SAVE] Trying auto-detection...")
                db = firestore.Client()
                logger.info(f"[FIRESTORE_SAVE] Auto-detection successful: {db}")
            except Exception as e2:
                logger.error(f"[FIRESTORE_SAVE] Auto-detection failed: {e2}")
                # Last resort - hardcode the project
                try:
                    logger.info("[FIRESTORE_SAVE] Last resort - hardcoded project...")
                    db = firestore.Client(project="ken-e-dev")
                    logger.info(f"[FIRESTORE_SAVE] Hardcoded project successful: {db}")
                except Exception as e3:
                    logger.error(f"[FIRESTORE_SAVE] All initialization attempts failed: {e3}")
                    return False
    
    if not db:
        logger.error("[FIRESTORE_SAVE] No Firestore client available after all attempts")
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
        
        doc_ref = db.collection(collection_name).document(doc_type)
        doc_ref.set(doc_data)
        
        logger.info(f"[FIRESTORE_SAVE] Successfully saved {doc_type} document for account {account_id}")
        return True
        
    except Exception as e:
        logger.error(f"[FIRESTORE_SAVE] Failed to save strategy document: {e}")
        import traceback
        logger.error(f"[FIRESTORE_SAVE] Traceback: {traceback.format_exc()}")
        return False


async def get_strategy_document(
    account_id: str,
    doc_type: str
) -> Optional[Dict[str, Any]]:
    """
    Retrieve a strategy document from Firestore.
    
    Args:
        account_id: Account ID for document scoping
        doc_type: Type of strategy document
        
    Returns:
        Document content as dictionary, or None if not found
    """
    if not db:
        logger.warning("No Firestore client available, cannot retrieve document")
        return None
    
    try:
        # Fetch from account-specific collection
        collection_name = f"strategy_docs_{account_id}"
        doc_ref = db.collection(collection_name).document(doc_type)
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
    account_id: str,
    doc_type: str,
    content: Dict[str, Any],
    user_id: Optional[str] = None
) -> bool:
    """
    Update an existing strategy document in Firestore.
    
    Args:
        account_id: Account ID for document scoping
        doc_type: Type of strategy document
        content: Updated document content
        user_id: Optional user ID for attribution
        
    Returns:
        Success status
    """
    if not db:
        logger.warning("No Firestore client available, document not updated")
        return False
    
    try:
        # Get existing document to increment version
        collection_name = f"strategy_docs_{account_id}"
        doc_ref = db.collection(collection_name).document(doc_type)
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


def parse_json_response(response_text: str) -> Optional[Dict[str, Any]]:
    """
    Parse JSON from agent response text.
    Handles cases where agent might include non-JSON text.
    
    Args:
        response_text: Raw response from agent
        
    Returns:
        Parsed JSON as dictionary, or None if parsing fails
    """
    if not response_text:
        return None
    
    # Try direct JSON parsing first
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass
    
    # Try to find JSON in the text (agent might add explanations)
    # Look for JSON boundaries
    start_markers = ['{', '[']
    end_markers = ['}', ']']
    
    for start_marker in start_markers:
        if start_marker in response_text:
            start_idx = response_text.index(start_marker)
            
            # Find matching end marker
            for end_marker in end_markers:
                if end_marker in response_text:
                    # Try different end positions (might have multiple objects)
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
    The full descriptions are already in the BEST PRACTICES section above.
    
    Args:
        best_practices_json: JSON string of best practices document
        
    Returns:
        Formatted string for OUTPUT REQUIREMENTS section
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
        # Fallback to generic instruction
        return """# OUTPUT REQUIREMENTS
Your response must be ONLY a complete JSON document following the BEST PRACTICES structure above.
Include ALL fields defined in the BEST PRACTICES document.
DO NOT include any conversational text, only output the JSON document."""


def extract_validation_criteria_from_guidelines(guidelines_json: str, best_practices_json: str) -> str:
    """
    Extract validation criteria from reviewer guidelines and best practices.
    
    Args:
        guidelines_json: JSON string of reviewer guidelines
        best_practices_json: JSON string of best practices to get expected field count
        
    Returns:
        Formatted string for reviewer validation process
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
    
    Args:
        company_name: Company name
        websites: Company websites
        industry: Industry description
        customer_regions: Target regions
        annual_ad_budget: Optional ad budget
        supporting_documents: Optional supporting docs
        
    Returns:
        Formatted string for prompt
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