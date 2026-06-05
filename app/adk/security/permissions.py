"""Permission verification service for tool execution.

This module provides OAuth token verification before tool execution,
ensuring users have the required scopes for each tool they attempt to use.

Features:
- OAuth token verification
- Scope checking against tool requirements
- Token expiry validation with buffer time
- Audit logging for security compliance
- Re-authorization flow support

Design Reference: Story 1.2.3 - Permission Verification
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from shared.structured_logging import get_structured_logger, log_context

logger = get_structured_logger(__name__)

# Dedicated audit logger for security events
_audit_logger = get_structured_logger("permission_audit")

# OAuth credentials are written to ADK session state under integration-specific
# keys by the MCP header-provider layer (see
# ``agent_factory.header_provider.CREDENTIAL_KEYS``). The permission service keys
# by OAuth *provider*, so it needs the same mapping. Google Analytics — the only
# live Google integration — stores its token under ``ga_credentials``, NOT
# ``google_credentials`` (which is never written anywhere). Reading the wrong key
# made every GA tool call fail the pre-flight check with ``no_token``.
#
# NOTE: ``analytics`` and ``ads`` both map to provider ``"google"`` in
# CATEGORY_TO_PROVIDER. When Google Ads ships (its own ``google_ads_credentials``
# key) this lookup must become category-aware rather than provider-keyed.
_PROVIDER_CREDENTIAL_KEY: dict[str, str] = {
    "google": "ga_credentials",
}


@dataclass
class PermissionCheckResult:
    """Result of a permission check.

    Attributes:
        allowed: Whether the action is permitted
        reason: Human-readable explanation
        requires_reauth: Whether user needs to re-authenticate
        missing_scopes: Scopes the user doesn't have but needs
    """

    allowed: bool
    reason: str
    requires_reauth: bool = False
    missing_scopes: list[str] | None = None


@dataclass
class TokenInfo:
    """OAuth token information for permission verification.

    Attributes:
        access_token: The OAuth access token
        refresh_token: Optional refresh token for token renewal
        expires_at: Token expiration time (None if unknown)
        scopes: List of granted OAuth scopes
        provider: OAuth provider name (e.g., "google", "hubspot")
    """

    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    scopes: list[str] = field(default_factory=list)
    provider: str = "unknown"


class PermissionService:
    """Verifies user permissions before tool execution.

    Integrates with Sprint 2's permission mapping and adds:
    - OAuth token verification
    - Token expiry checking with 5-minute buffer
    - Audit logging for compliance
    - Re-authorization flow support

    Usage:
        service = get_permission_service()
        result = await service.verify_tool_permission(
            tool_name="get_ga4_report",
            required_scopes=["analytics.readonly"],
            user_id="user123",
            account_id="acct456",
            token_info=token_info,
        )
        if not result.allowed:
            # Handle permission denied
            if result.requires_reauth:
                # Redirect to OAuth flow

    Audit Logging:
        All permission checks are logged to the 'permission_audit' logger
        with structured fields for compliance and debugging.
    """

    # Token expiry buffer - require reauth 5 minutes before actual expiry
    EXPIRY_BUFFER = timedelta(minutes=5)

    async def verify_tool_permission(
        self,
        tool_name: str,
        required_scopes: list[str],
        user_id: str,
        account_id: str,
        token_info: TokenInfo | None,
        organization_id: str | None = None,
        category: str | None = None,
    ) -> PermissionCheckResult:
        """Verify user has permission to execute a tool.

        Performs the following checks:
        1. If no scopes required, allow (public tools)
        2. If no token provided, deny with reauth flag
        3. If token expired (or expiring within buffer), deny with reauth
        4. If missing required scopes, deny with list of missing scopes

        Args:
            tool_name: Name of the tool being executed
            required_scopes: Scopes required by the tool
            user_id: User attempting to execute
            account_id: Account context for the operation
            token_info: OAuth token info, if available
            organization_id: Optional organization context
            category: Tool category (e.g. "analytics"). When the category is one
                whose tokens carry no abstract scopes (``_SCOPELESS_CATEGORIES``),
                a token with an empty scope set is trusted; otherwise scopes are
                enforced strictly.

        Returns:
            PermissionCheckResult indicating if execution is allowed
        """
        # Log the permission check initiation
        _audit_logger.info(
            "Permission check initiated",
            extra=log_context(
                component="permission_service",
                action="check_start",
                tool_name=tool_name,
                extra={
                    "user_id": user_id,
                    "account_id": account_id,
                    "required_scopes": required_scopes,
                    "organization_id": organization_id,
                },
            ),
        )

        # If no scopes required, allow
        if not required_scopes:
            self._log_result(
                tool_name,
                user_id,
                account_id,
                allowed=True,
                reason="no_scopes_required",
            )
            return PermissionCheckResult(allowed=True, reason="No permissions required")

        # If no token provided, deny
        if token_info is None:
            missing = required_scopes
            self._log_result(
                tool_name,
                user_id,
                account_id,
                allowed=False,
                reason="no_token",
                missing_scopes=missing,
            )
            return PermissionCheckResult(
                allowed=False,
                reason="No authentication token found",
                requires_reauth=True,
                missing_scopes=missing,
            )

        # Check token expiry
        if token_info.expires_at is not None:
            now = datetime.now(timezone.utc)
            # Handle naive datetimes by assuming UTC
            expires_at = token_info.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if now + self.EXPIRY_BUFFER > expires_at:
                self._log_result(
                    tool_name,
                    user_id,
                    account_id,
                    allowed=False,
                    reason="token_expired",
                )
                return PermissionCheckResult(
                    allowed=False,
                    reason="Authentication token has expired",
                    requires_reauth=True,
                )

        # Check scopes. For scopeless categories (e.g. Google Analytics) the
        # OAuth token carries no abstract-scope list — the tool's "analytics:read"
        # capability label is not an OAuth scope, and real scope enforcement
        # happens at the provider's API. There, an empty scope set means "scopes
        # unknown — trust the downstream API", NOT "missing every scope", so a
        # present, non-expired token is allowed. Every other category enforces
        # strictly: an empty scope set is treated as missing all required scopes.
        user_scopes = set(token_info.scopes)
        scope_enforcement_relaxed = category in _SCOPELESS_CATEGORIES
        if user_scopes or not scope_enforcement_relaxed:
            required_set = set(required_scopes)
            missing = list(required_set - user_scopes)

            if missing:
                self._log_result(
                    tool_name,
                    user_id,
                    account_id,
                    allowed=False,
                    reason="missing_scopes",
                    missing_scopes=missing,
                )
                return PermissionCheckResult(
                    allowed=False,
                    reason=f"Missing required scopes: {', '.join(missing)}",
                    requires_reauth=True,
                    missing_scopes=missing,
                )

        # All checks passed
        self._log_result(
            tool_name, user_id, account_id, allowed=True, reason="all_checks_passed"
        )
        return PermissionCheckResult(allowed=True, reason="All permissions verified")

    def _log_result(
        self,
        tool_name: str,
        user_id: str,
        account_id: str,
        allowed: bool,
        reason: str,
        missing_scopes: list[str] | None = None,
    ) -> None:
        """Log the permission check result for audit trail.

        Args:
            tool_name: Tool that was checked
            user_id: User who requested access
            account_id: Account context
            allowed: Whether permission was granted
            reason: Reason for the decision
            missing_scopes: List of scopes user was missing
        """
        log_level = "info" if allowed else "warning"
        getattr(_audit_logger, log_level)(
            f"Permission {'granted' if allowed else 'denied'}: {reason}",
            extra=log_context(
                component="permission_service",
                action="check_result",
                tool_name=tool_name,
                success=allowed,
                extra={
                    "user_id": user_id,
                    "account_id": account_id,
                    "allowed": allowed,
                    "reason": reason,
                    "missing_scopes": missing_scopes,
                },
            ),
        )

    async def get_token_info_from_state(
        self,
        state: dict[str, Any],
        provider: str,
    ) -> TokenInfo | None:
        """Extract token info from session state.

        This integrates with ADK's state management to retrieve
        stored OAuth credentials.

        Args:
            state: Session state dictionary
            provider: OAuth provider name (e.g., "google", "hubspot")

        Returns:
            TokenInfo if credentials found, None otherwise
        """
        try:
            # Resolve the session-state key the credentials are actually written
            # under (see _PROVIDER_CREDENTIAL_KEY). Falls back to the historical
            # "{provider}_credentials" convention for providers without an override.
            credentials_key = _PROVIDER_CREDENTIAL_KEY.get(
                provider, f"{provider}_credentials"
            )
            credentials = state.get(credentials_key)
            if credentials is None:
                return None

            # Parse expires_at if present
            expires_at = None
            if credentials.get("expires_at"):
                if isinstance(credentials["expires_at"], datetime):
                    expires_at = credentials["expires_at"]
                elif isinstance(credentials["expires_at"], (int, float)):
                    expires_at = datetime.fromtimestamp(
                        credentials["expires_at"], tz=timezone.utc
                    )
                elif isinstance(credentials["expires_at"], str):
                    expires_at = datetime.fromisoformat(
                        credentials["expires_at"].replace("Z", "+00:00")
                    )

            return TokenInfo(
                access_token=credentials.get("access_token", ""),
                refresh_token=credentials.get("refresh_token"),
                expires_at=expires_at,
                scopes=credentials.get("scopes", []),
                provider=provider,
            )
        except Exception as e:
            logger.error(f"Failed to extract token info: {e}")
            return None


# Provider mapping from tool categories
CATEGORY_TO_PROVIDER: dict[str, str] = {
    "analytics": "google",
    "ads": "google",
    "search": "google",
    "crm": "hubspot",
    "social": "meta",
    "advertising": "meta",
}

# Categories whose OAuth tokens do NOT enumerate abstract scopes. The tool's
# "<x>:read" label is a capability marker, not a real OAuth scope, and the
# provider's API performs the actual scope enforcement. For these categories an
# empty scope set means "scopes unknown — trust the downstream API"; for every
# other category an empty scope set is enforced strictly (treated as missing all
# required scopes). Keep this analytics-only until a relaxed integration ships.
_SCOPELESS_CATEGORIES: frozenset[str] = frozenset({"analytics"})


def get_provider_for_category(category: str) -> str:
    """Get OAuth provider for a tool category.

    Args:
        category: Tool category (e.g., "analytics", "crm")

    Returns:
        Provider name (e.g., "google", "hubspot")
    """
    return CATEGORY_TO_PROVIDER.get(category, "unknown")


# Singleton instance
_permission_service: PermissionService | None = None


def get_permission_service() -> PermissionService:
    """Get the singleton permission service.

    Returns:
        Shared PermissionService instance
    """
    global _permission_service
    if _permission_service is None:
        _permission_service = PermissionService()
    return _permission_service
