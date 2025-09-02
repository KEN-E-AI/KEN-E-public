"""API endpoints for managing integration credentials."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud import firestore

from ..auth import UserContext
from ..auth.user_context import get_current_user_context
from ..firestore import get_firestore_service
from ..models.integration_models import (
    GoogleAnalyticsCredentials,
    IntegrationCredentialsRequest,
    IntegrationCredentialsUpdate,
    IntegrationStatus,
    IntegrationStatusResponse,
    IntegrationTestRequest,
    IntegrationTestResponse,
    IntegrationType,
)
from ..services.encryption_service import IntegrationCredentialsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


def check_account_permission(user_context: UserContext, account_id: str) -> bool:
    """Check if user has permission to manage account integrations."""
    # Super admins have access to all accounts
    if user_context.is_super_admin:
        return True

    # Check if user has edit permission for this account
    account_permissions = user_context.account_permissions or {}
    account_perm = account_permissions.get(account_id, {})
    return account_perm.get("role") in ["admin", "editor"]


async def test_google_analytics_connection(
    credentials: dict[str, Any]
) -> IntegrationTestResponse:
    """Test Google Analytics connection with provided credentials."""
    try:
        # Validate credentials structure
        ga_creds = GoogleAnalyticsCredentials(**credentials)

        # For now, we'll just validate the structure and format
        # In production, you would actually test the connection to GA
        # This could be done by:
        # 1. Using the google-analytics-data library
        # 2. Making a test API call to the GA MCP server
        # 3. Or using the service account to authenticate with GA API

        # Basic validation checks
        if not ga_creds.private_key.startswith("-----BEGIN"):
            raise ValueError("Invalid private key format")

        if "@" not in ga_creds.client_email:
            raise ValueError("Invalid service account email")

        # TODO: Implement actual GA API connection test
        # For now, we'll assume valid structure means valid credentials

        return IntegrationTestResponse(
            success=True,
            message="Credentials validated successfully. Connection test pending implementation.",
            details={
                "service_account": ga_creds.client_email,
                "project_id": ga_creds.project_id,
            },
        )

    except Exception as e:
        logger.error(f"Google Analytics connection test failed: {e}")
        return IntegrationTestResponse(
            success=False,
            message=f"Validation failed: {e!s}",
            details={"error": str(e)},
        )


@router.post("/{account_id}/google-analytics")
async def store_google_analytics_credentials(
    account_id: str,
    request: IntegrationCredentialsRequest,
    current_user: UserContext = Depends(get_current_user_context),
) -> dict[str, str]:
    """Store Google Analytics credentials for an account."""
    # Check permissions
    if not check_account_permission(current_user, account_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to manage this account's integrations",
        )

    if request.integration_type != IntegrationType.GOOGLE_ANALYTICS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint only handles Google Analytics credentials",
        )

    try:
        # Initialize services
        firestore_service = get_firestore_service()
        db = firestore_service.get_client()
        creds_service = IntegrationCredentialsService(db)

        # Store the credentials
        await creds_service.store_credentials(
            account_id=account_id,
            integration_type=request.integration_type.value,
            credentials=request.credentials,
            user_id=current_user.user_id,
        )

        return {"message": "Credentials stored successfully"}

    except Exception as e:
        logger.error(f"Failed to store credentials: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store credentials",
        ) from e


@router.get("/{account_id}/google-analytics/status")
async def get_google_analytics_status(
    account_id: str,
    current_user: UserContext = Depends(get_current_user_context),
) -> IntegrationStatusResponse:
    """Check if Google Analytics is configured for an account."""
    # Check permissions
    if not check_account_permission(current_user, account_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this account's integrations",
        )

    try:
        # Initialize services
        firestore_service = get_firestore_service()
        db = firestore_service.get_client()
        creds_service = IntegrationCredentialsService(db)

        # Check if credentials exist
        exists = await creds_service.check_credentials_exist(
            account_id=account_id,
            integration_type=IntegrationType.GOOGLE_ANALYTICS.value,
        )

        if exists:
            # Get the document to retrieve metadata
            doc_id = f"{account_id}_{IntegrationType.GOOGLE_ANALYTICS.value}"
            doc = db.collection("integration_credentials").document(doc_id).get()
            doc_data = doc.to_dict() if doc.exists else {}

            return IntegrationStatusResponse(
                integration_type=IntegrationType.GOOGLE_ANALYTICS,
                status=IntegrationStatus.CONFIGURED,
                configured_at=doc_data.get("created_at"),
                last_tested_at=doc_data.get("last_tested_at"),
            )
        else:
            return IntegrationStatusResponse(
                integration_type=IntegrationType.GOOGLE_ANALYTICS,
                status=IntegrationStatus.NOT_CONFIGURED,
            )

    except Exception as e:
        logger.error(f"Failed to check integration status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check integration status",
        ) from e


@router.post("/{account_id}/google-analytics/test")
async def test_google_analytics_integration(
    account_id: str,
    request: IntegrationTestRequest,
    current_user: UserContext = Depends(get_current_user_context),
) -> IntegrationTestResponse:
    """Test Google Analytics connection for an account."""
    # Check permissions
    if not check_account_permission(current_user, account_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to test this account's integrations",
        )

    if request.integration_type != IntegrationType.GOOGLE_ANALYTICS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint only handles Google Analytics",
        )

    try:
        credentials = request.credentials

        # If no credentials provided, use stored ones
        if not credentials:
            firestore_service = get_firestore_service()
            db = firestore_service.get_client()
            creds_service = IntegrationCredentialsService(db)
            credentials = await creds_service.get_credentials(
                account_id=account_id,
                integration_type=IntegrationType.GOOGLE_ANALYTICS.value,
            )

            if not credentials:
                return IntegrationTestResponse(
                    success=False,
                    message="No credentials found for this integration",
                )

        # Test the connection
        result = await test_google_analytics_connection(credentials)

        # Update last tested timestamp if using stored credentials
        if not request.credentials and result.success:
            doc_id = f"{account_id}_{IntegrationType.GOOGLE_ANALYTICS.value}"
            db.collection("integration_credentials").document(doc_id).update(
                {"last_tested_at": firestore.SERVER_TIMESTAMP}
            )

        return result

    except Exception as e:
        logger.error(f"Failed to test integration: {e}")
        return IntegrationTestResponse(
            success=False,
            message=f"Test failed: {e!s}",
        )


@router.put("/{account_id}/google-analytics")
async def update_google_analytics_credentials(
    account_id: str,
    request: IntegrationCredentialsUpdate,
    current_user: UserContext = Depends(get_current_user_context),
) -> dict[str, str]:
    """Update Google Analytics credentials for an account."""
    # Check permissions
    if not check_account_permission(current_user, account_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to manage this account's integrations",
        )

    try:
        # Initialize services
        firestore_service = get_firestore_service()
        db = firestore_service.get_client()
        creds_service = IntegrationCredentialsService(db)

        # Check if credentials exist
        exists = await creds_service.check_credentials_exist(
            account_id=account_id,
            integration_type=IntegrationType.GOOGLE_ANALYTICS.value,
        )

        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No existing credentials found to update",
            )

        # Update the credentials
        await creds_service.update_credentials(
            account_id=account_id,
            integration_type=IntegrationType.GOOGLE_ANALYTICS.value,
            credentials=request.credentials,
            user_id=current_user.user_id,
        )

        return {"message": "Credentials updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update credentials: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update credentials",
        ) from e


@router.delete("/{account_id}/google-analytics")
async def delete_google_analytics_credentials(
    account_id: str,
    current_user: UserContext = Depends(get_current_user_context),
) -> dict[str, str]:
    """Delete Google Analytics credentials for an account."""
    # Check permissions
    if not check_account_permission(current_user, account_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to manage this account's integrations",
        )

    try:
        # Initialize services
        firestore_service = get_firestore_service()
        db = firestore_service.get_client()
        creds_service = IntegrationCredentialsService(db)

        # Delete the credentials
        await creds_service.delete_credentials(
            account_id=account_id,
            integration_type=IntegrationType.GOOGLE_ANALYTICS.value,
        )

        return {"message": "Credentials deleted successfully"}

    except Exception as e:
        logger.error(f"Failed to delete credentials: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete credentials",
        ) from e
