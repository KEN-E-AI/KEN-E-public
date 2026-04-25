"""
Audit logging service for strategy document operations and config changes.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import Request
from google.cloud import firestore

from ..auth.models import UserContext
from ..models.agent_config_models import ConfigAuditEntry
from ..models.strategy_models import StrategyAuditEntry

logger = logging.getLogger(__name__)

# Initialize Firestore client
db = firestore.Client()

# Map from ConfigAuditEntry.doc_type to its parent Firestore collection.
# Keep in sync with the collection names used by the admin routers in
# routers/agent_configs.py (agent_configs) and routers/mcp_server_configs.py
# (mcp_server_configs).
_CONFIG_COLLECTION_BY_DOC_TYPE: dict[str, str] = {
    "agent_config": "agent_configs",
    "mcp_server_config": "mcp_server_configs",
}


async def log_config_action(
    db: firestore.Client,
    doc_type: Literal["agent_config", "mcp_server_config"],
    doc_id: str,
    action: str,
    user: UserContext,
    *,
    version_after: str,
    version_before: str | None = None,
    fields_changed: list[str] | None = None,
    changes: dict[str, dict[str, Any]] | None = None,
) -> str:
    """Write a ConfigAuditEntry to the per-config history subcollection.

    Path: ``{collection}/{doc_id}/history/{iso_ts}_{uuid8}``. Audit failures
    are logged but do not propagate — the caller's main operation must not
    break if the audit write fails.

    See Sprint 6 Decision C for rationale.

    Returns:
        The audit document ID on success, or an empty string on failure.
    """
    collection = _CONFIG_COLLECTION_BY_DOC_TYPE.get(doc_type)
    if collection is None:
        raise ValueError(
            f"Unknown doc_type {doc_type!r}. "
            f"Supported: {sorted(_CONFIG_COLLECTION_BY_DOC_TYPE)}."
        )

    from ..middleware.request_id import get_request_id

    raw_request_id = get_request_id()
    request_id = raw_request_id if raw_request_id else None

    now = datetime.now(timezone.utc).isoformat()
    audit_id = f"{now}_{uuid4().hex[:8]}"

    entry = ConfigAuditEntry(
        action=action,
        doc_type=doc_type,
        doc_id=doc_id,
        user_id=user.user_id,
        user_email=user.email,
        timestamp=now,
        request_id=request_id,
        version_before=version_before,
        version_after=version_after,
        fields_changed=list(fields_changed or []),
        changes=dict(changes or {}),
    )

    try:
        db.collection(collection).document(doc_id).collection("history").document(
            audit_id
        ).set(entry.model_dump())
        logger.info(
            f"Config audit log created: {action} on {doc_type}/{doc_id} "
            f"by {user.email} (audit_id={audit_id})"
        )
        return audit_id
    except Exception as e:
        logger.error(f"Failed to write config audit entry: {e}")
        return ""


async def log_strategy_action(
    account_id: str,
    doc_type: str,
    action: str,
    user: UserContext,
    request: Request = None,
    doc_id: str | None = None,
    version: int | None = None,
    changes: dict[str, Any] | None = None,
    session_id: str | None = None,
    fields_modified: list[str] | None = None,
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
            request_id=str(uuid4()),
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
    user_id: str | None = None,
    doc_type: str | None = None,
    limit: int = 10,
) -> list[StrategyAuditEntry]:
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
    account_id: str, doc_type: str, doc_id: str, limit: int = 50
) -> list[StrategyAuditEntry]:
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


async def get_user_activity(user_id: str, limit: int = 100) -> list[StrategyAuditEntry]:
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


async def cleanup_old_audit_logs(account_id: str, days_to_keep: int = 90) -> int:
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

        logger.info(
            f"Cleaned up {deleted_count} old audit entries for account {account_id}"
        )
        return deleted_count

    except Exception as e:
        logger.error(f"Failed to cleanup audit logs: {e}")
        return 0


