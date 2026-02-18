"""Pre-execution hooks for security verification.

This module provides hooks that integrate with ADK's callback system
to enforce security before tool execution.

Usage:
    from google.adk.agents import Agent
    from app.adk.security.hooks import adk_before_tool_callback

    agent = Agent(
        model='gemini-2.0-flash',
        name='ken_e',
        before_tool_callback=adk_before_tool_callback,
    )
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from shared.structured_logging import get_structured_logger, log_context

from .permissions import (
    CATEGORY_TO_PROVIDER,
    PermissionCheckResult,
    get_permission_service,
)

if TYPE_CHECKING:
    from google.adk.tools import BaseTool, ToolContext

logger = get_structured_logger(__name__)


async def before_tool_execution_hook(
    tool_name: str,
    tool_context: Any,
    **kwargs: Any,
) -> PermissionCheckResult:
    """Hook called before tool execution to verify permissions.

    This integrates with ADK's callback system to enforce security.
    The hook checks:
    1. Tool exists in registry
    2. User has required OAuth scopes
    3. Token is valid and not expired

    Args:
        tool_name: Name of the tool being executed
        tool_context: ADK ToolContext with session state
        **kwargs: Additional keyword arguments from ADK

    Returns:
        PermissionCheckResult indicating if execution should proceed

    Note:
        If result.allowed is False, the calling code should handle
        the denial appropriately (e.g., return error to user).
    """
    # Get tool definition from registry
    try:
        from app.adk.tools.registry import get_default_registry

        registry = get_default_registry()
        tool_def = registry.get_tool(tool_name)
    except Exception as e:
        logger.warning(f"Could not access tool registry: {e}")
        tool_def = None

    if tool_def is None:
        # Tool not in registry - allow (might be internal ADK tool)
        logger.debug(
            f"Tool '{tool_name}' not in registry, allowing execution",
            extra=log_context(
                component="security_hooks",
                action="registry_miss",
                tool_name=tool_name,
            ),
        )
        return PermissionCheckResult(allowed=True, reason="Tool not in registry")

    # Extract required scopes from tool definition
    required_scopes = [p.scope for p in tool_def.permissions]

    # Get user context from session state
    state = _get_state_dict(tool_context)
    user_id = state.get("user_id", "unknown")
    account_id = state.get("account_id", "unknown")

    # Determine OAuth provider from tool category
    provider = CATEGORY_TO_PROVIDER.get(tool_def.category, "unknown")

    # Get token info from state
    permission_service = get_permission_service()
    token_info = await permission_service.get_token_info_from_state(state, provider)

    # Verify permission
    result = await permission_service.verify_tool_permission(
        tool_name=tool_name,
        required_scopes=required_scopes,
        user_id=user_id,
        account_id=account_id,
        token_info=token_info,
    )

    if not result.allowed:
        logger.warning(
            f"Tool execution blocked: {result.reason}",
            extra=log_context(
                component="security_hooks",
                action="tool_blocked",
                tool_name=tool_name,
                extra={
                    "reason": result.reason,
                    "requires_reauth": result.requires_reauth,
                    "missing_scopes": result.missing_scopes,
                },
            ),
        )

    return result


async def adk_before_tool_callback(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
) -> dict[str, Any] | None:
    """ADK-compatible before_tool_callback adapter.

    Wraps the existing permission verification hook to match ADK's
    expected callback signature: (BaseTool, dict, ToolContext) -> Optional[dict].

    Returns None to allow execution, or a dict with error details to block.
    Also stores _tool_start_time in state for usage tracking duration.

    Args:
        tool: ADK BaseTool being executed
        args: Tool arguments
        tool_context: ADK ToolContext with session state

    Returns:
        None if allowed, dict with error info if blocked
    """
    if hasattr(tool_context, "state") and hasattr(tool_context.state, "__setitem__"):
        tool_context.state["_tool_start_time"] = time.monotonic()

    result = await before_tool_execution_hook(tool.name, tool_context)

    if result.allowed:
        return None

    if result.requires_reauth:
        return {
            "error": "authentication_required",
            "message": result.reason,
            "requires_reauth": True,
            "missing_scopes": result.missing_scopes or [],
        }

    return {"error": "permission_denied", "message": result.reason}


def _get_state_dict(tool_context: Any) -> dict[str, Any]:
    """Extract state dictionary from ADK ToolContext.

    Handles different possible ToolContext structures.

    Args:
        tool_context: ADK ToolContext object

    Returns:
        State dictionary (empty if not accessible)
    """
    if tool_context is None:
        return {}

    # ADK ToolContext has a state attribute
    if hasattr(tool_context, "state"):
        state = tool_context.state
        if isinstance(state, dict):
            return state
        # ADK state might be a State object with dict-like access
        if hasattr(state, "get"):
            return state  # type: ignore
        # Try to convert to dict
        if hasattr(state, "to_dict"):
            return state.to_dict()

    # Fallback: try to access as dict directly
    if isinstance(tool_context, dict):
        return tool_context

    return {}


async def verify_tool_for_user(
    tool_name: str,
    user_id: str,
    account_id: str,
    session_state: dict[str, Any],
) -> PermissionCheckResult:
    """Verify tool access for a user without ADK context.

    This is a standalone function for permission checking outside
    of the ADK callback flow.

    Args:
        tool_name: Name of the tool to verify
        user_id: User ID requesting access
        account_id: Account context
        session_state: Session state containing credentials

    Returns:
        PermissionCheckResult indicating if access is allowed
    """
    # Get tool definition
    try:
        from app.adk.tools.registry import get_default_registry

        registry = get_default_registry()
        tool_def = registry.get_tool(tool_name)
    except Exception:
        tool_def = None

    if tool_def is None:
        return PermissionCheckResult(allowed=True, reason="Tool not in registry")

    required_scopes = [p.scope for p in tool_def.permissions]
    provider = CATEGORY_TO_PROVIDER.get(tool_def.category, "unknown")

    permission_service = get_permission_service()
    token_info = await permission_service.get_token_info_from_state(
        session_state, provider
    )

    return await permission_service.verify_tool_permission(
        tool_name=tool_name,
        required_scopes=required_scopes,
        user_id=user_id,
        account_id=account_id,
        token_info=token_info,
    )
