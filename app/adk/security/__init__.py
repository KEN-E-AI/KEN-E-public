"""Security module for KEN-E tool execution.

This module provides:
- PermissionService: OAuth token verification before tool execution
- Permission verification hooks for ADK callback integration
"""

from .permissions import (
    PermissionCheckResult,
    PermissionService,
    TokenInfo,
    get_permission_service,
)

__all__ = [
    "PermissionCheckResult",
    "PermissionService",
    "TokenInfo",
    "get_permission_service",
]
