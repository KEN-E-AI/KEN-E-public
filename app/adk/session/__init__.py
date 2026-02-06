"""Session management module for KEN-E.

This module provides:
- SessionRecoveryService: Recover sessions for returning users
- SessionTimeoutManager: Manage session timeout and warnings
"""

from .recovery import (
    RecoverableSession,
    SessionRecoveryResult,
    SessionRecoveryService,
    get_recovery_service,
    reset_recovery_service,
)
from .timeout import (
    SessionTimeoutManager,
    TimeoutConfig,
    get_timeout_manager,
    reset_timeout_manager,
)

__all__ = [
    "RecoverableSession",
    "SessionRecoveryResult",
    "SessionRecoveryService",
    "SessionTimeoutManager",
    "TimeoutConfig",
    "get_recovery_service",
    "get_timeout_manager",
    "reset_recovery_service",
    "reset_timeout_manager",
]
