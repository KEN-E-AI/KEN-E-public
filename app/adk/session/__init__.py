"""Session management module for KEN-E.

This module provides:
- SessionRecoveryService: Recover sessions for returning users
"""

from .recovery import (
    RecoverableSession,
    SessionRecoveryResult,
    SessionRecoveryService,
    get_recovery_service,
    reset_recovery_service,
)

__all__ = [
    "RecoverableSession",
    "SessionRecoveryResult",
    "SessionRecoveryService",
    "get_recovery_service",
    "reset_recovery_service",
]
