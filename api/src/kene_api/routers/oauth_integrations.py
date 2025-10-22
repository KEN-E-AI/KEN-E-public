"""OAuth 2.0 integration endpoints for third-party services."""

import json
import logging
import os
import re
import secrets
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from ..auth import UserContext
from ..auth.user_context import get_current_user_context
from ..firestore import get_firestore_service
from ..metrics.oauth_metrics import (
    OAuthMetricsCollector,
    measure_oauth_flow,
    measure_encryption_operation,
    track_oauth_attempt,
    track_oauth_success,
    track_oauth_callback_error,
    track_token_refresh_success,
    track_token_refresh_failure,
    track_state_transition,
)
from ..models.integration_models import (
    IntegrationStatus,
    IntegrationStatusResponse,
    IntegrationType,
)
from ..models.oauth_models import (
    OAuthErrorCode,
    GoogleAnalyticsProperty,
    GoogleAnalyticsPropertiesResponse,
    UpdateSelectedPropertiesRequest,
)
from ..services.encryption_service import IntegrationCredentialsService
from ..services.oauth_state_service import OAuthStateService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/oauth", tags=["oauth"])

# Google OAuth 2.0 configuration
from ..utils.secrets import get_env_or_secret

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = get_env_or_secret("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"

# OAuth redirect URI - must be configured via environment variable
def get_google_redirect_uri() -> str:
    """Get the Google OAuth redirect URI from environment."""
    redirect_uri = os.getenv("GOOGLE_OAUTH_REDIRECT_URI")
    if not redirect_uri:
        raise ValueError(
            "GOOGLE_OAUTH_REDIRECT_URI environment variable is required"
        )
    return redirect_uri

# Google Analytics scopes
# We need both Data API and Admin API scopes
GA_SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",  # For Google Analytics Data API
    "https://www.googleapis.com/auth/analytics.edit",  # For Google Analytics Admin API (required for listing properties)
]

# Frontend URL configuration
def get_frontend_url() -> str:
    """Get the frontend URL from environment."""
    frontend_url = os.getenv("FRONTEND_URL")
    if not frontend_url:
        raise ValueError("FRONTEND_URL environment variable is required")
    return frontend_url.rstrip("/")  # Remove trailing slash if present


def generate_state_token() -> str:
    """Generate a secure random state token."""
    return secrets.token_urlsafe(32)


@router.get("/authorize/google-analytics")
@measure_oauth_flow("google_analytics")
async def authorize_google_analytics(
    account_id: str = Query(..., description="Account ID for the integration"),
    current_user: UserContext = Depends(get_current_user_context),
) -> dict[str, str]:
    """
    Initiate OAuth 2.0 flow for Google Analytics.
    Returns the authorization URL for the frontend to redirect to.
    """
    # Track OAuth attempt
    track_oauth_attempt("google_analytics")
    
    # Check permissions
    if not current_user.is_super_admin:
        account_permissions = current_user.account_permissions or {}
        account_perm = account_permissions.get(account_id)
        # account_perm is a string like "edit" or "view", not a dict
        if account_perm not in ["edit", "admin", "editor"]:
            track_oauth_callback_error("google_analytics", "permission_denied")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to manage this account's integrations",
            )

    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        track_oauth_callback_error("google_analytics", "config_missing")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth is not configured. Please set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET.",
        )

    try:
        redirect_uri = get_google_redirect_uri()
    except ValueError as e:
        track_oauth_callback_error("google_analytics", "redirect_uri_error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e

    # Generate state token and store it persistently
    state = generate_state_token()

    # Get OAuth state service
    firestore_service = get_firestore_service()
    db = firestore_service.get_client()
    oauth_state_service = OAuthStateService(db)

    # Log state transition
    logger.info(f"[OAUTH_STATE] Creating state token for user {current_user.user_id}, account {account_id}")
    track_state_transition("google_analytics", "none", "initiated")

    # Store state in database
    await oauth_state_service.create_state(
        state_token=state,
        user_id=current_user.user_id,
        account_id=account_id,
        integration_type="google_analytics",
        ttl_minutes=15,
    )
    
    logger.info(f"[OAUTH_STATE] State token created successfully: {state[:8]}...")

    # Build authorization URL
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
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
    # Use metrics collector for the entire callback flow
    async with OAuthMetricsCollector("google_analytics") as collector:
        try:
            frontend_url = get_frontend_url()
        except ValueError:
            collector.track_error("config_error")
            # Fallback to a generic error page if frontend URL is not configured
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="System configuration error: FRONTEND_URL not set",
            ) from None

        # Handle errors from Google using error codes
        if error:
            logger.error(f"[OAUTH_CALLBACK] OAuth error from Google: {error}")
            collector.track_error(f"google_{error}")
            track_state_transition("google_analytics", "initiated", "failed")
            # Map Google errors to our error codes
            error_code = OAuthErrorCode.AUTHORIZATION_DENIED if error == "access_denied" else OAuthErrorCode.UNKNOWN_ERROR
            return RedirectResponse(
                url=f"{frontend_url}/account-settings?oauth_error={error_code.value}"
            )

        if not code or not state:
            logger.warning("[OAUTH_CALLBACK] Missing code or state in callback")
            collector.track_error("missing_params")
            track_state_transition("google_analytics", "initiated", "invalid")
            return RedirectResponse(
                url=f"{frontend_url}/account-settings?oauth_error={OAuthErrorCode.STATE_INVALID.value}"
            )

        # Get OAuth state service
        firestore_service = get_firestore_service()
        db = firestore_service.get_client()
        oauth_state_service = OAuthStateService(db)

        # Verify state token from database
        oauth_state = await oauth_state_service.get_state(state)
        if not oauth_state:
            logger.warning(f"[OAUTH_CALLBACK] Invalid or expired state token: {state[:8]}...")
            collector.track_error("state_expired")
            track_state_transition("google_analytics", "initiated", "expired")
            return RedirectResponse(
                url=f"{frontend_url}/account-settings?oauth_error={OAuthErrorCode.STATE_EXPIRED.value}"
            )

        user_id = oauth_state.user_id
        account_id = oauth_state.account_id
        
        logger.info(f"[OAUTH_CALLBACK] Valid state token for user {user_id}, account {account_id}")
        track_state_transition("google_analytics", "initiated", "verified")

        try:
            redirect_uri = get_google_redirect_uri()

            # Exchange authorization code for tokens
            async with httpx.AsyncClient() as client:
                token_response = await client.post(
                    GOOGLE_TOKEN_URI,
                    data={
                        "client_id": GOOGLE_CLIENT_ID,
                        "client_secret": GOOGLE_CLIENT_SECRET,
                        "code": code,
                        "redirect_uri": redirect_uri,
                        "grant_type": "authorization_code",
                    },
                )

                if token_response.status_code != 200:
                    logger.error(f"[OAUTH_CALLBACK] Token exchange failed: {token_response.text}")
                    collector.track_error("token_exchange_failed")
                    track_state_transition("google_analytics", "verified", "failed")
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

            # Clean up state from database
            await oauth_state_service.delete_state(state)
            
            # Mark success
            logger.info(f"[OAUTH_CALLBACK] Successfully completed OAuth flow for account {account_id}")
            collector.track_success()
            track_oauth_success("google_analytics")
            track_state_transition("google_analytics", "verified", "completed")

            # Redirect to frontend with success - go to property selection
            # Use /settings/organization which is the actual route (not /account-settings which redirects)
            redirect_url = f"{frontend_url}/settings/organization?oauth_success=google_analytics&account={account_id}&select_properties=true"
            logger.info(f"[OAUTH_CALLBACK] Redirecting to frontend with property selection: {redirect_url}")
            return RedirectResponse(url=redirect_url)

        except ValueError as e:
            # Configuration errors
            logger.error(f"[OAUTH_CALLBACK] OAuth configuration error: {e}")
            collector.track_error("configuration_error")
            track_state_transition("google_analytics", "verified", "failed")
            return RedirectResponse(
                url=f"{frontend_url}/account-settings?oauth_error={OAuthErrorCode.CONFIGURATION_ERROR.value}"
            )
        except Exception as e:
            logger.error(f"[OAUTH_CALLBACK] OAuth callback error: {e}")
            collector.track_error("unknown_error")
            track_state_transition("google_analytics", "verified", "failed")
            # Use error code instead of raw error message
            return RedirectResponse(
                url=f"{frontend_url}/account-settings?oauth_error={OAuthErrorCode.TOKEN_EXCHANGE_FAILED.value}"
            )


@router.post("/refresh/{account_id}/google-analytics")
async def refresh_google_analytics_token(
    account_id: str,
    current_user: UserContext = Depends(get_current_user_context),
) -> dict[str, str]:
    """
    Refresh the access token for Google Analytics using the stored refresh token.
    """
    logger.info(f"[TOKEN_REFRESH] Starting token refresh for account {account_id}")
    
    # Check permissions
    if not current_user.is_super_admin:
        account_permissions = current_user.account_permissions or {}
        account_perm = account_permissions.get(account_id)
        # account_perm is a string like "edit" or "view", not a dict
        if account_perm not in ["edit", "admin", "editor"]:
            track_token_refresh_failure("google_analytics", "permission_denied")
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
            logger.warning(f"[TOKEN_REFRESH] No refresh token found for account {account_id}")
            track_token_refresh_failure("google_analytics", "no_refresh_token")
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
                logger.error(f"[TOKEN_REFRESH] Token refresh failed: {refresh_response.text}")
                track_token_refresh_failure("google_analytics", f"http_{refresh_response.status_code}")
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
        
        logger.info(f"[TOKEN_REFRESH] Successfully refreshed token for account {account_id}")
        track_token_refresh_success("google_analytics")

        return {"message": "Token refreshed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[TOKEN_REFRESH] Token refresh error: {e}")
        track_token_refresh_failure("google_analytics", "unknown_error")
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
        account_perm = account_permissions.get(account_id)
        # account_perm is a string like "edit" or "view", not a dict
        if account_perm not in ["edit", "admin", "editor"]:
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


@router.get("/google-analytics/properties/{account_id}")
async def get_google_analytics_properties(
    account_id: str,
    current_user: UserContext = Depends(get_current_user_context),
) -> GoogleAnalyticsPropertiesResponse:
    """
    Get list of Google Analytics properties accessible with the stored OAuth token.
    """
    # Check permissions
    if not current_user.is_super_admin:
        account_permissions = current_user.account_permissions or {}
        account_perm = account_permissions.get(account_id)
        # account_perm is a string like "edit" or "view", not a dict
        if account_perm not in ["edit", "view", "admin", "editor", "viewer"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this account's integrations",
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

        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Google Analytics is not connected for this account",
            )

        access_token = credentials.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No valid access token found. Please reconnect Google Analytics.",
            )

        # Check if token is expired and refresh if needed
        expires_at = credentials.get("expires_at", 0)
        if datetime.now().timestamp() > expires_at:
            # Try to refresh the token
            refresh_token = credentials.get("refresh_token")
            if not refresh_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Access token expired and no refresh token available. Please reconnect.",
                )

            # Refresh the token
            async with httpx.AsyncClient() as client:
                refresh_response = await client.post(
                    GOOGLE_TOKEN_URI,
                    data={
                        "client_id": GOOGLE_CLIENT_ID,
                        "client_secret": GOOGLE_CLIENT_SECRET,
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token",
                    },
                )

                if refresh_response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Failed to refresh access token. Please reconnect.",
                    )

                new_tokens = refresh_response.json()
                access_token = new_tokens.get("access_token")
                
                # Update stored credentials
                credentials["access_token"] = access_token
                credentials["expires_at"] = datetime.now().timestamp() + new_tokens.get("expires_in", 3600)
                
                await creds_service.update_credentials(
                    account_id=account_id,
                    integration_type="google_analytics",
                    credentials=credentials,
                    user_id=current_user.user_id,
                )

        # Check if credentials have stored GA account info from old integration
        stored_ga_account = credentials.get("ga_account", {})
        logger.info(f"[GA_PROPERTIES] Stored GA account info in credentials: {json.dumps(stored_ga_account, indent=2)}")
        
        # Call Google Analytics Admin API to list properties
        logger.info(f"[GA_PROPERTIES] Starting to fetch properties for account {account_id}")
        logger.info(f"[GA_PROPERTIES] Using access token: {access_token[:20]}..." if access_token else "No token")
        
        properties = []
        async with httpx.AsyncClient() as client:
            # First, get the list of accounts
            logger.info("[GA_PROPERTIES] Fetching GA accounts from Admin API v1alpha")
            accounts_response = await client.get(
                "https://analyticsadmin.googleapis.com/v1alpha/accounts",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"pageSize": 200},
            )

            logger.info(f"[GA_PROPERTIES] Accounts API response status: {accounts_response.status_code}")
            
            if accounts_response.status_code != 200:
                logger.error(f"[GA_PROPERTIES] Failed to fetch GA accounts: {accounts_response.text}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to fetch Google Analytics accounts",
                )

            accounts_data = accounts_response.json()
            logger.info(f"[GA_PROPERTIES] Raw accounts response: {json.dumps(accounts_data, indent=2)}")
            accounts = accounts_data.get("accounts", [])
            logger.info(f"[GA_PROPERTIES] Found {len(accounts)} GA accounts: {[acc.get('displayName', 'Unknown') for acc in accounts]}")
            
            # Log the structure of ALL accounts for debugging
            for idx, acc in enumerate(accounts):
                logger.info(f"[GA_PROPERTIES] Account {idx}: {json.dumps(acc, indent=2)}")

            # For each account, get its properties
            for account in accounts:
                # The account dict might have either 'name' (resource name) or 'account' (account ID)
                # Let's handle both cases
                account_name = account.get("name", "")  
                account_id = account.get("account", "")  # Sometimes the API returns just the ID
                account_display_name = account.get("displayName", "Unknown Account")
                
                # If we don't have account_name but have account_id, use that
                if not account_name and account_id:
                    account_name = account_id
                
                logger.info(f"[GA_PROPERTIES] Processing account: {account_display_name} (name={account_name}, id={account_id})")
                logger.info(f"[GA_PROPERTIES] Full account object: {json.dumps(account, indent=2)}")
                
                if not account_name:
                    logger.warning(f"[GA_PROPERTIES] Skipping account {account_display_name} - no name or ID field")
                    continue
                    
                # Ensure account_name has the proper format for the API
                # The API expects: /v1beta/accounts/{accountId}/properties
                if account_name.startswith("accounts/"):
                    # Already has the correct format
                    pass
                elif account_name.isdigit():
                    # Just the numeric ID, add the prefix
                    account_name = f"accounts/{account_name}"
                else:
                    # Unknown format, try to extract the ID
                    match = re.search(r'(\d+)', account_name)
                    if match:
                        account_name = f"accounts/{match.group(1)}"
                    else:
                        logger.error(f"[GA_PROPERTIES] Cannot parse account identifier: {account_name}")
                        continue
                
                # According to GA Admin API docs, we need to use the properties endpoint with a filter
                # The account_name should be in format "accounts/123456"
                properties_url = "https://analyticsadmin.googleapis.com/v1alpha/properties"
                
                # Ensure we have the proper account format for the filter
                if not account_name.startswith("accounts/"):
                    filter_account = f"accounts/{account_name}"
                else:
                    filter_account = account_name
                
                logger.info(f"[GA_PROPERTIES] Fetching from URL: {properties_url} with filter: parent:{filter_account}")
                
                properties_response = await client.get(
                    properties_url,
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={
                        "filter": f"parent:{filter_account}",
                        "pageSize": 200
                    },
                )

                logger.info(f"[GA_PROPERTIES] Properties API response status for {account_display_name}: {properties_response.status_code}")
                
                if properties_response.status_code != 200:
                    error_detail = properties_response.text
                    logger.error(f"[GA_PROPERTIES] Failed to fetch properties for {account_display_name}: {error_detail}")
                    logger.error(f"[GA_PROPERTIES] Request URL was: {properties_url}")
                    continue
                
                if properties_response.status_code == 200:
                    properties_data = properties_response.json()
                    account_properties = properties_data.get("properties", [])
                    logger.info(f"[GA_PROPERTIES] Found {len(account_properties)} properties in account {account_display_name}")
                    
                    for prop in account_properties:
                        property_info = GoogleAnalyticsProperty(
                            property_id=prop.get("name", ""),  # Format: properties/123456
                            display_name=prop.get("displayName", "Unknown Property"),
                            account_id=account_name,
                            account_display_name=account_display_name,
                            time_zone=prop.get("timeZone", ""),
                            industry_category=prop.get("industryCategory", ""),
                            create_time=prop.get("createTime", ""),
                        )
                        properties.append(property_info)
                        logger.info(f"[GA_PROPERTIES] Added property: {property_info.display_name} ({property_info.property_id})")
                else:
                    logger.warning(f"[GA_PROPERTIES] Failed to fetch properties for account {account_display_name}: {properties_response.text}")

        # Get currently selected properties if any
        selected_property_ids = credentials.get("selected_property_ids", [])
        
        logger.info(f"[GA_PROPERTIES] Total properties found: {len(properties)}")
        logger.info(f"[GA_PROPERTIES] Selected property IDs: {selected_property_ids}")

        return GoogleAnalyticsPropertiesResponse(
            properties=properties,
            selected_property_ids=selected_property_ids,
            total_count=len(properties),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch GA properties: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch Google Analytics properties",
        ) from e


@router.post("/google-analytics/properties/{account_id}")
async def update_selected_properties(
    account_id: str,
    request: UpdateSelectedPropertiesRequest,
    current_user: UserContext = Depends(get_current_user_context),
) -> dict[str, Any]:
    """
    Update the selected Google Analytics properties for an account.
    """
    # Check permissions - only admin or editor can update
    if not current_user.is_super_admin:
        account_permissions = current_user.account_permissions or {}
        account_perm = account_permissions.get(account_id)
        # account_perm is a string like "edit" or "view", not a dict
        if account_perm not in ["edit", "admin", "editor"]:
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

        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Google Analytics is not connected for this account",
            )

        # Update credentials with selected properties
        credentials["selected_property_ids"] = request.property_ids
        credentials["selected_properties"] = [prop.dict() for prop in request.properties]

        await creds_service.update_credentials(
            account_id=account_id,
            integration_type="google_analytics",
            credentials=credentials,
            user_id=current_user.user_id,
        )

        logger.info(
            f"Updated selected GA properties for account {account_id}: {request.property_ids}"
        )

        return {
            "message": "Selected properties updated successfully",
            "selected_count": len(request.property_ids),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update selected properties: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update selected properties",
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
            
            # Get selected properties count
            selected_properties = credentials.get("selected_properties", [])
            property_count = len(selected_properties) if selected_properties else 0

            return IntegrationStatusResponse(
                integration_type=IntegrationType.GOOGLE_ANALYTICS,
                status=IntegrationStatus.EXPIRED if is_expired else IntegrationStatus.CONFIGURED,
                configured_at=None,  # You could store this in the credentials
                error_message="Access token expired. Please refresh." if is_expired else None,
                user_email=credentials.get("user_email"),
                property_count=property_count,
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
