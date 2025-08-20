"""
Audit logging service for strategy document operations.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import uuid4

from fastapi import Request
from google.cloud import firestore

from ..auth.models import UserContext
from ..models.strategy_models import StrategyAuditEntry

logger = logging.getLogger(__name__)

# Initialize Firestore client
db = firestore.Client()


async def log_strategy_action(
    account_id: str,
    doc_type: str,
    action: str,
    user: UserContext,
    request: Request = None,
    doc_id: Optional[str] = None,
    version: Optional[int] = None,
    changes: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    fields_modified: Optional[List[str]] = None
) -> str:
    """
    Log a strategy document action to the audit trail.
    
    Args:
        account_id: Account ID for the document
        doc_type: Type of strategy document
        action: Action performed (created, updated, deleted, viewed, exported)
        user: User context with authentication info
        request: FastAPI request object for IP and user agent
        doc_id: Document ID if applicable
        version: Document version at time of action
        changes: Before/after changes for updates
        session_id: Chat session ID if from chatbot
        fields_modified: List of fields that were modified
        
    Returns:
        Audit entry ID
    """
    try:
        # Create audit entry
        audit_entry = StrategyAuditEntry(
            action=action,
            user_id=user.user_id,
            user_email=user.email,
            timestamp=datetime.utcnow(),
            doc_type=doc_type,
            doc_id=doc_id,
            version=version or 1,
            changes=changes,
            fields_modified=fields_modified,
            session_id=session_id,
            request_id=str(uuid4())
        )
        
        # Add request metadata if available
        if request:
            audit_entry.ip_address = request.client.host if request.client else None
            audit_entry.user_agent = request.headers.get("user-agent")
        
        # Save to Firestore in account-specific audit collection
        audit_id = f"{doc_type}_{datetime.utcnow().isoformat()}_{uuid4().hex[:8]}"
        audit_ref = db.document(f"strategy_audit_{account_id}/{audit_id}")
        audit_ref.set(audit_entry.dict())
        
        logger.info(
            f"Audit log created: {action} on {doc_type} by {user.email} "
            f"for account {account_id}"
        )
        
        return audit_id
        
    except Exception as e:
        logger.error(f"Failed to create audit log: {e}")
        # Don't fail the main operation if audit logging fails
        return ""


async def get_recent_actions(
    account_id: str,
    user_id: Optional[str] = None,
    doc_type: Optional[str] = None,
    limit: int = 10
) -> List[StrategyAuditEntry]:
    """
    Get recent strategy document actions.
    
    Args:
        account_id: Account ID to query
        user_id: Optional user ID filter
        doc_type: Optional document type filter
        limit: Maximum entries to return
        
    Returns:
        List of recent audit entries
    """
    try:
        # Build query on account-specific audit collection
        audit_ref = db.collection(f"strategy_audit_{account_id}")
        query = audit_ref.order_by("timestamp", direction=firestore.Query.DESCENDING)
        
        if user_id:
            query = query.where("user_id", "==", user_id)
        if doc_type:
            query = query.where("doc_type", "==", doc_type)
        
        query = query.limit(limit)
        
        # Execute query
        entries = []
        for doc in query.stream():
            entry_data = doc.to_dict()
            entries.append(StrategyAuditEntry(**entry_data))
        
        return entries
        
    except Exception as e:
        logger.error(f"Failed to retrieve audit entries: {e}")
        return []


async def get_document_history(
    account_id: str,
    doc_type: str,
    doc_id: str,
    limit: int = 50
) -> List[StrategyAuditEntry]:
    """
    Get complete history for a specific document.
    
    Args:
        account_id: Account ID
        doc_type: Document type
        doc_id: Document ID
        limit: Maximum entries to return
        
    Returns:
        List of audit entries for the document
    """
    try:
        # Query for specific document in account-specific audit collection
        audit_ref = db.collection(f"strategy_audit_{account_id}")
        query = audit_ref.where("doc_type", "==", doc_type)
        query = query.where("doc_id", "==", doc_id)
        query = query.order_by("timestamp", direction=firestore.Query.DESCENDING)
        query = query.limit(limit)
        
        # Execute query
        entries = []
        for doc in query.stream():
            entry_data = doc.to_dict()
            entries.append(StrategyAuditEntry(**entry_data))
        
        return entries
        
    except Exception as e:
        logger.error(f"Failed to retrieve document history: {e}")
        return []


async def get_user_activity(
    user_id: str,
    limit: int = 100
) -> List[StrategyAuditEntry]:
    """
    Get all strategy document activity for a specific user across all accounts.
    
    Args:
        user_id: User ID to query
        limit: Maximum entries to return
        
    Returns:
        List of audit entries for the user
    """
    try:
        # This requires a collection group query
        audit_ref = db.collection_group("strategy_audit")
        query = audit_ref.where("user_id", "==", user_id)
        query = query.order_by("timestamp", direction=firestore.Query.DESCENDING)
        query = query.limit(limit)
        
        # Execute query
        entries = []
        for doc in query.stream():
            entry_data = doc.to_dict()
            entries.append(StrategyAuditEntry(**entry_data))
        
        return entries
        
    except Exception as e:
        logger.error(f"Failed to retrieve user activity: {e}")
        return []


async def cleanup_old_audit_logs(
    account_id: str,
    days_to_keep: int = 90
) -> int:
    """
    Clean up old audit logs beyond retention period.
    
    Args:
        account_id: Account ID
        days_to_keep: Number of days to retain logs
        
    Returns:
        Number of entries deleted
    """
    try:
        # Calculate cutoff date
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        # Query for old entries in account-specific audit collection
        audit_ref = db.collection(f"strategy_audit_{account_id}")
        query = audit_ref.where("timestamp", "<", cutoff_date)
        
        # Delete in batches
        deleted_count = 0
        batch = db.batch()
        batch_size = 0
        
        for doc in query.stream():
            batch.delete(doc.reference)
            batch_size += 1
            deleted_count += 1
            
            # Commit batch at 500 operations
            if batch_size >= 500:
                batch.commit()
                batch = db.batch()
                batch_size = 0
        
        # Commit remaining
        if batch_size > 0:
            batch.commit()
        
        logger.info(f"Cleaned up {deleted_count} old audit entries for account {account_id}")
        return deleted_count
        
    except Exception as e:
        logger.error(f"Failed to cleanup audit logs: {e}")
        return 0


from datetime import timedelta  # Add this import at the top