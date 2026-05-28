"""OAuth header authentication middleware for MCP server integration.

This middleware enables migration from custom GAMCPClient (body-based credentials)
to ADK's standard McpToolset (header-based credentials).

Supports:
1. Standard Bearer token: Authorization: Bearer {access_token}
2. X-OAuth-Credentials header: Base64-encoded full credential bundle
3. Legacy body-based auth (deprecated, with warning)

This follows OAuth2/HTTP authentication standards and enables ADK MCPToolset integration.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from shared.structured_logging import get_structured_logger, log_context

if TYPE_CHECKING:
    pass

logger = get_structured_logger(__name__)

# Security scheme for OpenAPI docs
bearer_scheme = HTTPBearer(auto_error=False)


class OAuthCredentials(BaseModel):
    """Validated OAuth credentials extracted from header or body.

    This model represents the credentials needed for OAuth-protected
    MCP server access. It can be populated from either:
    - A simple Bearer token (access_token only)
    - A base64-encoded JSON blob via X-OAuth-Credentials header
    - Legacy body-based tenant_credentials (deprecated)
    """

    access_token: str = Field(..., description="OAuth access token")
    refresh_token: str | None = Field(None, description="OAuth refresh token")
    token_type: str = Field("Bearer", description="Token type")
    expires_at: datetime | None = Field(None, description="Token expiration time")
    scopes: list[str] = Field(default_factory=list, description="Granted scopes")
    provider: str = Field(
        "unknown", description="OAuth provider (e.g., google, hubspot)"
    )
    client_id: str | None = Field(None, description="OAuth client ID")
    client_secret: str | None = Field(None, description="OAuth client secret")
    token_uri: str | None = Field(None, description="Token refresh URI")


class AuthHeaderMiddleware:
    """Middleware to extract OAuth credentials from request.

    Supports:
    1. X-OAuth-Credentials header: Base64-encoded full credential bundle
    2. Standard Bearer token: Authorization: Bearer {access_token}
    3. Legacy body-based auth (with deprecation warning)

    This enables migration from custom GAMCPClient to ADK McpToolset.

    Usage:
        middleware = get_auth_middleware()
        credentials, source = await middleware.extract_credentials(request, auth)
    """

    # Enable deprecation warnings for body-based auth
    DEPRECATE_BODY_AUTH = True

    async def extract_credentials(
        self,
        request: Request,
        authorization: HTTPAuthorizationCredentials | None = None,
    ) -> tuple[OAuthCredentials, str]:
        """Extract OAuth credentials from request.

        Priority:
        1. X-OAuth-Credentials header (full credential bundle)
        2. Authorization header (simple token)
        3. Request body tenant_credentials (legacy, deprecated)

        Args:
            request: FastAPI request object
            authorization: Extracted Authorization header credentials

        Returns:
            Tuple of (credentials, source) where source is "header" or "body"

        Raises:
            HTTPException: If no valid credentials found (401)
        """
        # 1. Check X-OAuth-Credentials header (full credential bundle)
        oauth_creds_header = request.headers.get("X-OAuth-Credentials")
        if oauth_creds_header:
            logger.debug(
                "Extracting credentials from X-OAuth-Credentials header",
                extra=log_context(
                    component="auth_middleware", action="extract_oauth_header"
                ),
            )
            return self._parse_credential_bundle(oauth_creds_header), "header"

        # 2. Authorization header (simple token)
        if authorization and authorization.credentials:
            logger.debug(
                "Extracting credentials from Authorization header",
                extra=log_context(component="auth_middleware", action="extract_header"),
            )
            return self._parse_bearer_token(authorization.credentials), "header"

        # 3. Fall back to body-based auth (legacy)
        try:
            body = await request.json()
            if "tenant_credentials" in body:
                if self.DEPRECATE_BODY_AUTH:
                    logger.warning(
                        "Body-based authentication is deprecated. "
                        "Please migrate to Authorization: Bearer header.",
                        extra=log_context(
                            component="auth_middleware",
                            action="deprecation_warning",
                            extra={"source": "body"},
                        ),
                    )
                return self._parse_body_credentials(body["tenant_credentials"]), "body"
        except HTTPException:
            # Re-raise HTTP exceptions (e.g., 400 for invalid credentials)
            raise
        except Exception:
            # Body parsing failed or no tenant_credentials
            pass

        # No credentials found
        raise HTTPException(
            status_code=401,
            detail="No authentication credentials provided. "
            "Use Authorization: Bearer {token} header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    def _parse_bearer_token(self, token: str) -> OAuthCredentials:
        """Parse a simple bearer token into credentials.

        Args:
            token: Bearer token string

        Returns:
            Parsed OAuth credentials with access_token only
        """
        return OAuthCredentials(access_token=token)

    def _parse_credential_bundle(self, encoded: str) -> OAuthCredentials:
        """Parse a base64-encoded credential bundle from X-OAuth-Credentials header.

        Args:
            encoded: Base64-encoded JSON string with full OAuth credentials

        Returns:
            Parsed OAuth credentials

        Raises:
            HTTPException: If credential format is invalid
        """
        try:
            padded = encoded + "=" * (4 - len(encoded) % 4)
            decoded = base64.b64decode(padded).decode()
            creds_dict = json.loads(decoded)

            expires_at = None
            if creds_dict.get("expires_at"):
                if isinstance(creds_dict["expires_at"], (int, float)):
                    expires_at = datetime.fromtimestamp(
                        creds_dict["expires_at"], tz=timezone.utc
                    )
                elif isinstance(creds_dict["expires_at"], str):
                    expires_at = datetime.fromisoformat(
                        creds_dict["expires_at"].replace("Z", "+00:00")
                    )

            return OAuthCredentials(
                access_token=creds_dict.get("access_token", ""),
                refresh_token=creds_dict.get("refresh_token"),
                token_type=creds_dict.get("token_type", "Bearer"),
                expires_at=expires_at,
                scopes=creds_dict.get("scopes", []),
                provider=creds_dict.get("provider", "unknown"),
                client_id=creds_dict.get("client_id"),
                client_secret=creds_dict.get("client_secret"),
                token_uri=creds_dict.get("token_uri"),
            )
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail="Invalid credential bundle format",
            ) from e

    def _parse_body_credentials(self, encoded_creds: str) -> OAuthCredentials:
        """Parse legacy body-based credentials (tenant_credentials).

        This is the format used by the custom GAMCPClient.

        Args:
            encoded_creds: Base64-encoded JSON with OAuth tokens

        Returns:
            Parsed OAuth credentials

        Raises:
            HTTPException: If credentials format is invalid
        """
        try:
            decoded = base64.b64decode(encoded_creds).decode()
            creds_dict = json.loads(decoded)

            # Parse expires_at if present
            expires_at = None
            if creds_dict.get("expires_at"):
                if isinstance(creds_dict["expires_at"], (int, float)):
                    expires_at = datetime.fromtimestamp(
                        creds_dict["expires_at"], tz=timezone.utc
                    )
                elif isinstance(creds_dict["expires_at"], str):
                    expires_at = datetime.fromisoformat(
                        creds_dict["expires_at"].replace("Z", "+00:00")
                    )

            return OAuthCredentials(
                access_token=creds_dict.get("access_token", ""),
                refresh_token=creds_dict.get("refresh_token"),
                token_type=creds_dict.get("token_type", "Bearer"),
                expires_at=expires_at,
                scopes=creds_dict.get("scopes", []),
                provider=creds_dict.get("provider", "google"),
                client_id=creds_dict.get("client_id"),
                client_secret=creds_dict.get("client_secret"),
                token_uri=creds_dict.get(
                    "token_uri", "https://oauth2.googleapis.com/token"
                ),
            )
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail="Invalid credentials format",
            ) from e


# Singleton middleware instance
_auth_middleware: AuthHeaderMiddleware | None = None


def get_auth_middleware() -> AuthHeaderMiddleware:
    """Get the singleton auth middleware instance.

    Returns:
        Shared AuthHeaderMiddleware instance
    """
    global _auth_middleware
    if _auth_middleware is None:
        _auth_middleware = AuthHeaderMiddleware()
    return _auth_middleware


async def get_oauth_credentials(
    request: Request,
    authorization: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> OAuthCredentials:
    """FastAPI dependency to extract OAuth credentials from request.

    This can be used as a dependency in route handlers to require
    OAuth credentials for MCP tool execution.

    Usage:
        @router.post("/tools/call")
        async def call_tool(
            credentials: OAuthCredentials = Depends(get_oauth_credentials),
        ):
            # Use credentials to call MCP server
            ...

    Args:
        request: FastAPI request object (injected)
        authorization: Authorization header (injected via HTTPBearer)

    Returns:
        Validated OAuth credentials

    Raises:
        HTTPException: 401 if no valid credentials found
    """
    middleware = get_auth_middleware()
    credentials, source = await middleware.extract_credentials(request, authorization)

    # Store auth source in request state for audit logging
    request.state.auth_source = source

    return credentials
