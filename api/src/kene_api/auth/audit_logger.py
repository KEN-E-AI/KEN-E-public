"""Audit logging for security events."""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any

from google.cloud import firestore

from ..firestore import get_firestore_service

logger = logging.getLogger(__name__)


class SecurityEventType(str, Enum):
    """Types of security events to audit."""

    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    TOKEN_VERIFICATION_FAILURE = "token_verification_failure"
    ACCESS_DENIED = "access_denied"
    PERMISSION_CHECK_FAILED = "permission_check_failed"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    USER_CREATED = "user_created"
    TOKEN_REVOKED = "token_revoked"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    SUPER_ADMIN_GRANTED = "super_admin_granted"
    SUPER_ADMIN_REVOKED = "super_admin_revoked"


class AuditLogger:
    """Service for logging security events."""

    def __init__(self):
        """Initialize the audit logger."""
        self.collection_name = "security_audit_logs"
        self._structured_logger = self._setup_structured_logging()

    def _setup_structured_logging(self) -> logging.Logger:
        """Set up structured logging for Google Cloud Logging."""
        audit_logger = logging.getLogger("security_audit")
        audit_logger.setLevel(logging.INFO)

        # Remove default handlers to avoid duplicate logs
        audit_logger.handlers = []

        # Add structured logging handler
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        audit_logger.addHandler(handler)

        return audit_logger

    async def log_event(
        self,
        event_type: SecurityEventType,
        user_id: str | None = None,
        email: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict[str, Any] | None = None,
        severity: str = "INFO",
    ) -> None:
        """Log a security event.

        Args:
            event_type: Type of security event
            user_id: User ID if available
            email: User email if available
            ip_address: Client IP address
            user_agent: Client user agent
            details: Additional event details
            severity: Log severity (INFO, WARNING, ERROR, CRITICAL)
        """
        event_data = {
            "event_type": event_type.value,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "email": email,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "details": details or {},
            "severity": severity,
        }

        # Log to structured logging for Cloud Logging
        self._structured_logger.log(
            getattr(logging, severity),
            json.dumps(
                {
                    "security_event": event_data,
                    "labels": {
                        "event_type": event_type.value,
                        "severity": severity,
                    },
                }
            ),
        )

        # Also store in Firestore for longer retention and queries
        try:
            firestore_service = get_firestore_service()
            db = firestore_service.get_client()

            # Add server timestamp
            event_data["server_timestamp"] = firestore.SERVER_TIMESTAMP

            # Store in Firestore
            await self._store_in_firestore(db, event_data)

        except Exception as e:
            logger.error(f"Failed to store audit log in Firestore: {e}")

    async def _store_in_firestore(self, db: firestore.Client, event_data: dict) -> None:
        """Store audit log in Firestore.

        Args:
            db: Firestore client
            event_data: Event data to store
        """
        # Create a document with auto-generated ID
        doc_ref = db.collection(self.collection_name).document()
        doc_ref.set(event_data)

    async def log_login_success(
        self,
        user_id: str,
        email: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Log successful login."""
        await self.log_event(
            event_type=SecurityEventType.LOGIN_SUCCESS,
            user_id=user_id,
            email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            severity="INFO",
        )

    async def log_login_failure(
        self,
        email: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        reason: str | None = None,
    ) -> None:
        """Log failed login attempt."""
        await self.log_event(
            event_type=SecurityEventType.LOGIN_FAILURE,
            email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"reason": reason},
            severity="WARNING",
        )

    async def log_access_denied(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        required_permission: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Log access denied event."""
        await self.log_event(
            event_type=SecurityEventType.ACCESS_DENIED,
            user_id=user_id,
            ip_address=ip_address,
            details={
                "resource_type": resource_type,
                "resource_id": resource_id,
                "required_permission": required_permission,
            },
            severity="WARNING",
        )

    async def log_rate_limit_exceeded(
        self,
        ip_address: str,
        endpoint: str | None = None,
        user_id: str | None = None,
    ) -> None:
        """Log rate limit exceeded event."""
        await self.log_event(
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
            user_id=user_id,
            ip_address=ip_address,
            details={"endpoint": endpoint},
            severity="WARNING",
        )

    async def log_token_revoked(
        self,
        user_id: str,
        token_id: str,
        reason: str | None = None,
        revoked_by: str | None = None,
    ) -> None:
        """Log token revocation event."""
        await self.log_event(
            event_type=SecurityEventType.TOKEN_REVOKED,
            user_id=user_id,
            details={
                "token_id": token_id,
                "reason": reason,
                "revoked_by": revoked_by,
            },
            severity="INFO",
        )


# Global audit logger instance
audit_logger = AuditLogger()


def get_audit_logger() -> AuditLogger:
    """Get audit logger instance."""
    return audit_logger
