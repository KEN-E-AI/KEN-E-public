"""Pre-execution hooks for security verification.

This module provides hooks that integrate with ADK's callback system
to enforce security before tool execution.

Usage:
    from google.adk.agents import Agent
    from app.adk.security.hooks import adk_before_tool_callback

    agent = Agent(
        model='gemini-2.5-pro',
        name='ken_e',
        before_tool_callback=adk_before_tool_callback,
    )
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import weave

from app.adk.tracking.tool_trace_context import stash_trace_context
from app.utils.weave_observability import WEAVE_AVAILABLE, init_weave_if_needed
from shared.structured_logging import get_structured_logger, log_context

from .permissions import (
    CATEGORY_TO_PROVIDER,
    PermissionCheckResult,
    get_permission_service,
)

if TYPE_CHECKING:
    from google.adk.tools import BaseTool, ToolContext

logger = get_structured_logger(__name__)


def _ga_token_fingerprint(token: str | None) -> str:
    """Short, non-reversible fingerprint of a GA access token for log correlation.

    sha256[:8] — never logs the token itself. The API-side injection log
    (``api/src/kene_api/routers/chat.py``) computes this identically, so a
    single test-env turn confirms whether the token the API injected into
    session state is the one the engine actually sees here: matching
    fingerprints prove ``append_event`` propagation; a mismatch/``absent``
    means the engine read stale/absent credentials.
    """
    if not token:
        return "absent"
    return hashlib.sha256(token.encode()).hexdigest()[:8]


async def _refresh_ga_token_if_needed(tool_context: ToolContext) -> None:
    """Refresh GA access token if expired, using stored refresh_token.

    The refresh token stays in session state and never crosses HTTP.
    """
    state = _get_state_dict(tool_context)
    ga_creds = state.get("ga_credentials", {})
    if not ga_creds.get("refresh_token") or not ga_creds.get("expires_at"):
        return

    expires_at = ga_creds["expires_at"]
    if isinstance(expires_at, (int, float)):
        expires_at = datetime.fromtimestamp(expires_at, tz=timezone.utc)
    elif isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))

    # Refresh if token expires within 5 minutes
    if datetime.now(timezone.utc) < expires_at - timedelta(minutes=5):
        return

    try:
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": ga_creds["refresh_token"],
                    "client_id": ga_creds.get("client_id", ""),
                    "client_secret": ga_creds.get("client_secret", ""),
                },
            )
        if response.status_code == 200:
            token_data = response.json()
            ga_creds["access_token"] = token_data["access_token"]
            ga_creds["expires_at"] = (
                datetime.now(timezone.utc)
                + timedelta(seconds=token_data.get("expires_in", 3600))
            ).isoformat()
            if hasattr(tool_context, "state") and hasattr(
                tool_context.state, "__setitem__"
            ):
                tool_context.state["ga_credentials"] = ga_creds
            logger.info("GA access token refreshed successfully")
        else:
            logger.warning(
                f"GA token refresh failed with status {response.status_code}"
            )
    except Exception as e:
        logger.warning(f"GA token refresh error: {e}")


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
        category=tool_def.category,
    )

    if not result.allowed:
        # Diagnostic: a `no_token` denial means the resolved credential key was
        # absent from session state. Log which credential-bearing keys ARE present
        # (names + booleans only, never token values) so we can tell "token never
        # reached the session" apart from "wrong key / stale code".
        state_keys = (
            sorted(str(k) for k in state.keys() if not str(k).startswith("_"))
            if hasattr(state, "keys")
            else []
        )
        ga_creds = state.get("ga_credentials") or {}
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
                    "provider": provider,
                    "account_id": account_id,
                    "session_state_keys": state_keys,
                    "ga_credentials_present": bool(ga_creds),
                    "ga_access_token_present": bool(ga_creds.get("access_token")),
                    # Correlates with the API-side ensure_ga_credentials token_fp.
                    # Same fingerprint → the injected token reached the engine;
                    # mismatch/"absent" → stale or unpropagated session state.
                    "ga_access_token_fp": _ga_token_fingerprint(
                        ga_creds.get("access_token")
                    ),
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
    # Initialize Weave on first tool call (idempotent). On Agent Engine,
    # module-level init in ken_e_agent.py doesn't re-execute after
    # deserialization, so this callback is the earliest runtime hook.
    # The WEAVE_AVAILABLE guard avoids entering the lock + secret-lookup
    # path when the weave package isn't even installed.
    if WEAVE_AVAILABLE:
        init_weave_if_needed()

    if hasattr(tool_context, "state") and hasattr(tool_context.state, "__setitem__"):
        tool_context.state["_tool_start_time"] = time.monotonic()

        # Build trace context attributes for this tool span.
        # Entered here, exited in adk_after_tool_callback.
        # Per docs/trace-structure-spec.md §4.3, L3 tool spans must carry
        # tool_name and parent agent identity in addition to the context block.
        trace_attrs: dict[str, Any] = {
            "tool_name": tool.name,
            "context_agent_id": "ken_e_chatbot",
        }

        # context_agent_goal: the user's query that triggered this tool call
        user_content = tool_context.user_content
        if user_content and hasattr(user_content, "parts") and user_content.parts:
            goal_text = getattr(user_content.parts[0], "text", None)
            if goal_text:
                trace_attrs["context_agent_goal"] = goal_text[:500]

        # context_previous_tool_calls: list of tool names called before this one
        previous = tool_context.state.get("_previous_tool_calls", [])
        trace_attrs["context_previous_tool_calls"] = list(previous)

        # context_reasoning: LLM's reasoning text from after_model_callback
        reasoning = tool_context.state.get("_last_reasoning")
        if reasoning:
            trace_attrs["context_reasoning"] = reasoning
            tool_context.state["_last_reasoning"] = None  # Clear after read

        attrs_ctx = weave.attributes(trace_attrs)
        attrs_ctx.__enter__()
        # Hold the (generator-backed) context manager off session state and
        # exit it in adk_after_tool_callback. It must NOT live in ADK state:
        # AgentTool.run_async deep-copies parent state into agent-as-tool child
        # sessions, and a generator can't be pickled. See tool_trace_context.
        stash_trace_context(tool_context, attrs_ctx)

    await _refresh_ga_token_if_needed(tool_context)

    result = await before_tool_execution_hook(tool.name, tool_context)

    if result.allowed:
        return None

    if result.requires_reauth:
        if hasattr(tool_context, "state") and hasattr(
            tool_context.state, "__setitem__"
        ):
            tool_context.state["_requires_reauth"] = True
            tool_context.state["_reauth_service"] = "google-analytics"
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
            return state
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
        category=tool_def.category,
    )


# ---------------------------------------------------------------------------
# GA OAuth after-tool callback (AH-28)
# ---------------------------------------------------------------------------

# Indicator strings that signal a 401 / expired-token response from the GA MCP
# server.  Checked case-insensitively; update when the GA MCP server changes
# its error format.
#
# Strong indicators: specific OAuth error codes safe to match in the message-
# only path (no error flag required) because they are unlikely to appear in
# legitimate GA API data payloads.
_GA_401_STRONG_INDICATORS = (
    "token expired",
    "token has been revoked",
    "invalid_grant",
)
# Weak indicators: common HTTP / OAuth status words that could also appear in
# legitimate domain data (e.g. "401" in a GA property ID or report count,
# "unauthorized" in a domain-specific resource name).  Only matched when the
# response also carries an explicit error/isError/sentinel flag.
_GA_401_WEAK_INDICATORS = (
    "401",
    "unauthorized",
    "authentication_required",
)

_GA_REAUTH_MESSAGE = (
    "Your Google Analytics access has expired. "
    "Please reconnect Google Analytics to continue."
)
_GA_REAUTH_RESPONSE: dict[str, Any] = {
    "error": "authentication_required",
    "message": _GA_REAUTH_MESSAGE,
    "requires_reauth": True,
}


def _is_ga_401(tool_response: Any) -> bool:
    """Return True when *tool_response* indicates a GA OAuth 401.

    Detection is split into two indicator tiers:
    * ``_GA_401_STRONG_INDICATORS``: specific OAuth error codes matched in ALL
      paths, including the message-only dict path.
    * ``_GA_401_WEAK_INDICATORS``: generic HTTP/OAuth status words (``"401"``,
      ``"unauthorized"``) matched only when the response also carries an
      explicit ``error``/``isError``/``_error`` flag — these strings are common
      enough in legitimate GA data (e.g., ``"Processed 401 rows"``, a property
      ID containing ``"401"``) that matching them without an error flag would
      produce false-positive reauth prompts.

    Returns False on any unexpected type or when no indicator matches.
    """
    try:
        if isinstance(tool_response, dict):
            # ADK exception sentinel path — carries both strong and weak indicators.
            if "_error" in tool_response:
                err_val = str(tool_response["_error"]).lower()
                all_inds = _GA_401_STRONG_INDICATORS + _GA_401_WEAK_INDICATORS
                return any(ind in err_val for ind in all_inds)

            # Explicit error/isError flag — carry both tiers.
            if tool_response.get("error") or tool_response.get("isError"):
                msg = str(tool_response.get("message", "")).lower()
                err = str(tool_response.get("error", "")).lower()
                haystack = msg + " " + err
                all_inds = _GA_401_STRONG_INDICATORS + _GA_401_WEAK_INDICATORS
                return any(ind in haystack for ind in all_inds)

            # Message-only path (no error flag): only match strong indicators to
            # avoid false positives on GA numeric data or domain-specific terms.
            msg = str(tool_response.get("message", "")).lower()
            if msg:
                return any(ind in msg for ind in _GA_401_STRONG_INDICATORS)

        elif isinstance(tool_response, str):
            # Plain string: only match strong indicators for the same reason.
            lower = tool_response.lower()
            return any(ind in lower for ind in _GA_401_STRONG_INDICATORS)
    except Exception:
        pass
    return False


async def ga_oauth_after_tool_callback(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    tool_response: Any,
) -> dict[str, Any] | None:
    """ADK ``after_tool_callback`` that detects GA OAuth 401 errors.

    When a GA MCP tool returns a 401-shaped response (expired or revoked
    token), this callback:

    1. Sets ``tool_context.state["_requires_reauth"] = True`` and
       ``tool_context.state["_reauth_service"] = "google-analytics"`` so the
       chat router's reauth-polling path (``chat.py:2450-2466``) surfaces a
       re-auth prompt on the next turn.
    2. Returns a replacement dict with the canonical ``authentication_required``
       shape (same as ``adk_before_tool_callback`` on the pre-flight path) so
       the LLM context is consistent regardless of which detection layer
       caught the expiry.

    Returns ``None`` (passthrough) on:
    * Successful tool responses
    * Non-401 errors (e.g., ``permission_denied``)
    * Any exception inside the detection logic (degrades gracefully — the
      upstream MCP error reaches the LLM unchanged)

    The ``_requires_reauth`` / ``_reauth_service`` pair is idempotent: if the
    pre-flight ``adk_before_tool_callback`` already wrote the same keys, the
    second write is a no-op.

    Forward-compat: ``_make_header_provider`` is retrofitted by IN-PRD-06 to
    fetch credentials from the Integrations endpoint rather than session state.
    The ``_requires_reauth`` contract this callback writes stays valid because
    the chat router reads session state, not headers.
    """
    try:
        if not _is_ga_401(tool_response):
            return None

        if hasattr(tool_context, "state") and hasattr(
            tool_context.state, "__setitem__"
        ):
            tool_context.state["_requires_reauth"] = True
            tool_context.state["_reauth_service"] = "google-analytics"
            logger.info(
                "ga_oauth_reauth_detected",
                extra=log_context(
                    component="ga_oauth_callback",
                    action="reauth_detected",
                    extra={
                        "tool_name": getattr(tool, "name", "unknown"),
                        "reauth_service": "google-analytics",
                    },
                ),
            )

        return dict(_GA_REAUTH_RESPONSE)
    except Exception:
        logger.warning(
            "ga_oauth_after_tool_callback: detection logic raised unexpectedly; "
            "passing response through unchanged",
            exc_info=True,
        )
        return None
