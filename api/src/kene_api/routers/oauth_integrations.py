"""OAuth 2.0 integration endpoints for third-party services."""

import logging
import os
import secrets
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from ..auth import UserContext
from ..auth.user_context import get_current_user_context
from ..firestore import get_firestore_service
from ..models.integration_models import (
    IntegrationStatus,
    IntegrationStatusResponse,
    IntegrationType,
)
from ..services.encryption_service import IntegrationCredentialsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/oauth", tags=["oauth"])

# Google OAuth 2.0 configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/api/oauth/callback/google"
)

# Google Analytics scopes
GA_SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/analytics.manage.users.readonly",
]

# Temporary state storage (in production, use Redis or database)
oauth_states: dict[str, dict[str, Any]] = {}


def generate_state_token() -> str:
    """Generate a secure random state token."""
    return secrets.token_urlsafe(32)


def verify_state_token(state: str) -> dict[str, Any] | None:
    """Verify and retrieve state data."""
    data = oauth_states.get(state)
    if data:
        # Check if state is not expired (15 minutes)
        if datetime.now() - data.get("created_at", datetime.now()) < timedelta(minutes=15):
            return data
    return None


@router.get("/authorize/google-analytics")
async def authorize_google_analytics(
    account_id: str = Query(..., description="Account ID for the integration"),
    current_user: UserContext = Depends(get_current_user_context),
) -> dict[str, str]:
    """
    Initiate OAuth 2.0 flow for Google Analytics.
    Returns the authorization URL for the frontend to redirect to.
    """
    # Check permissions
    if not current_user.is_super_admin:
        account_permissions = current_user.account_permissions or {}
        account_perm = account_permissions.get(account_id, {})
        if account_perm.get("role") not in ["admin", "editor"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to manage this account's integrations",
            )

    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth is not configured. Please set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET.",
        )

    # Generate state token and store it with user/account info
    state = generate_state_token()
    oauth_states[state] = {
        "user_id": current_user.user_id,
        "account_id": account_id,
        "created_at": datetime.now(),
    }

    # Build authorization URL
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(GA_SCOPES),
        "state": state,
        "access_type": "offline",  # Request refresh token
        "prompt": "consent",  # Force consent to ensure refresh token
    }

    auth_url = f"{GOOGLE_AUTH_URI}?{urlencode(params)}"

    return {
        "auth_url": auth_url,
        "message": "Redirect user to auth_url to complete authorization",
    }


@router.get("/callback/google")
async def google_oauth_callback(
    code: str = Query(None, description="Authorization code from Google"),
    state: str = Query(None, description="State token for verification"),
    error: str = Query(None, description="Error from Google if authorization failed"),
) -> RedirectResponse:
    """
    Handle OAuth 2.0 callback from Google.
    Exchange authorization code for access and refresh tokens.
    """
    # Handle errors from Google
    if error:
        logger.error(f"OAuth error from Google: {error}")
        # Redirect to frontend with error
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:8080")
        return RedirectResponse(
            url=f"{frontend_url}/account-settings?oauth_error={error}"
        )

    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code or state",
        )

    # Verify state token
    state_data = verify_state_token(state)
    if not state_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state token",
        )

    user_id = state_data["user_id"]
    account_id = state_data["account_id"]

    try:
        # Exchange authorization code for tokens
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URI,
                data={
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )

            if token_response.status_code != 200:
                logger.error(f"Token exchange failed: {token_response.text}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to exchange authorization code for tokens",
                )

            tokens = token_response.json()

            # Get user info to verify the connection
            user_info_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )

            user_info = user_info_response.json() if user_info_response.status_code == 200 else {}

        # Store tokens securely
        firestore_service = get_firestore_service()
        db = firestore_service.get_client()
        creds_service = IntegrationCredentialsService(db)

        # Prepare credentials data
        credentials_data = {
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "token_type": tokens.get("token_type", "Bearer"),
            "expires_at": datetime.now().timestamp() + tokens.get("expires_in", 3600),
            "scope": tokens.get("scope", ""),
            "user_email": user_info.get("email", ""),
            "user_id": user_info.get("id", ""),
        }

        await creds_service.store_credentials(
            account_id=account_id,
            integration_type="google_analytics",
            credentials=credentials_data,
            user_id=user_id,
        )

        # Clean up state
        del oauth_states[state]

        # Redirect to frontend with success
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:8080")
        return RedirectResponse(
            url=f"{frontend_url}/account-settings?oauth_success=google_analytics&account={account_id}"
        )

    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        # Redirect to frontend with error
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:8080")
        return RedirectResponse(
            url=f"{frontend_url}/account-settings?oauth_error=token_exchange_failed"
        )


@router.post("/refresh/{account_id}/google-analytics")
async def refresh_google_analytics_token(
    account_id: str,
    current_user: UserContext = Depends(get_current_user_context),
) -> dict[str, str]:
    """
    Refresh the access token for Google Analytics using the stored refresh token.
    """
    # Check permissions
    if not current_user.is_super_admin:
        account_permissions = current_user.account_permissions or {}
        account_perm = account_permissions.get(account_id, {})
        if account_perm.get("role") not in ["admin", "editor"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to manage this account's integrations",
            )

    try:
        # Get stored credentials
        firestore_service = get_firestore_service()
        db = firestore_service.get_client()
        creds_service = IntegrationCredentialsService(db)

        credentials = await creds_service.get_credentials(
            account_id=account_id,
            integration_type="google_analytics",
        )

        if not credentials or not credentials.get("refresh_token"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No refresh token found. User needs to reauthorize.",
            )

        # Refresh the token
        async with httpx.AsyncClient() as client:
            refresh_response = await client.post(
                GOOGLE_TOKEN_URI,
                data={
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "refresh_token": credentials["refresh_token"],
                    "grant_type": "refresh_token",
                },
            )

            if refresh_response.status_code != 200:
                logger.error(f"Token refresh failed: {refresh_response.text}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to refresh access token",
                )

            new_tokens = refresh_response.json()

        # Update stored credentials with new access token
        credentials["access_token"] = new_tokens.get("access_token")
        credentials["expires_at"] = datetime.now().timestamp() + new_tokens.get("expires_in", 3600)

        await creds_service.update_credentials(
            account_id=account_id,
            integration_type="google_analytics",
            credentials=credentials,
            user_id=current_user.user_id,
        )

        return {"message": "Token refreshed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh token",
        ) from e


@router.delete("/disconnect/{account_id}/google-analytics")
async def disconnect_google_analytics(
    account_id: str,
    current_user: UserContext = Depends(get_current_user_context),
) -> dict[str, str]:
    """
    Disconnect Google Analytics by removing stored tokens.
    """
    # Check permissions
    if not current_user.is_super_admin:
        account_permissions = current_user.account_permissions or {}
        account_perm = account_permissions.get(account_id, {})
        if account_perm.get("role") not in ["admin", "editor"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to manage this account's integrations",
            )

    try:
        # Remove stored credentials
        firestore_service = get_firestore_service()
        db = firestore_service.get_client()
        creds_service = IntegrationCredentialsService(db)

        await creds_service.delete_credentials(
            account_id=account_id,
            integration_type="google_analytics",
        )

        return {"message": "Google Analytics disconnected successfully"}

    except Exception as e:
        logger.error(f"Failed to disconnect Google Analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disconnect Google Analytics",
        ) from e


@router.get("/status/{account_id}/google-analytics")
async def get_google_analytics_status(
    account_id: str,
    current_user: UserContext = Depends(get_current_user_context),
) -> IntegrationStatusResponse:
    """
    Check the status of Google Analytics integration.
    """
    try:
        firestore_service = get_firestore_service()
        db = firestore_service.get_client()
        creds_service = IntegrationCredentialsService(db)

        credentials = await creds_service.get_credentials(
            account_id=account_id,
            integration_type="google_analytics",
        )

        if credentials:
            # Check if token is expired
            expires_at = credentials.get("expires_at", 0)
            is_expired = datetime.now().timestamp() > expires_at

            return IntegrationStatusResponse(
                integration_type=IntegrationType.GOOGLE_ANALYTICS,
                status=IntegrationStatus.EXPIRED if is_expired else IntegrationStatus.CONFIGURED,
                configured_at=None,  # You could store this in the credentials
                error_message="Access token expired. Please refresh." if is_expired else None,
                user_email=credentials.get("user_email"),
            )
        else:
            return IntegrationStatusResponse(
                integration_type=IntegrationType.GOOGLE_ANALYTICS,
                status=IntegrationStatus.NOT_CONFIGURED,
            )

    except Exception as e:
        logger.error(f"Failed to check GA status: {e}")
        return IntegrationStatusResponse(
            integration_type=IntegrationType.GOOGLE_ANALYTICS,
            status=IntegrationStatus.ERROR,
            error_message=str(e),
        )
