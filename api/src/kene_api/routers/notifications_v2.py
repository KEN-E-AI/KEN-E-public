"""Improved notifications router with proper authentication and authorization."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import UserContext
from ..auth.user_context import get_current_user_context
from ..database import get_neo4j_service
from ..firestore import get_firestore_service
from ..models.kene_models import (
    CreateNotificationRequest,
    CreateNotificationResponse,
    NotificationWithStatus,
    SuccessResponse,
    UpdateNotificationStatusRequest,
    UserNotificationPreferences,
)
from ..repositories import CachedNotificationRepository, FirestoreNotificationRepository
from ..services.notification_service_v2 import NotificationService

router = APIRouter(tags=["notifications"])
logger = logging.getLogger(__name__)


def get_notification_service(
    firestore_service=Depends(get_firestore_service),
) -> NotificationService:
    """Get notification service instance with caching."""
    # Get the actual Firestore client from the service
    firestore_db = firestore_service.get_client()
    # Create base repository
    base_repository = FirestoreNotificationRepository(firestore_db)

    # Wrap with caching layer
    cached_repository = CachedNotificationRepository(base_repository, cache_ttl=300)

    return NotificationService(cached_repository)


@router.post("/", response_model=CreateNotificationResponse)
async def create_notification(
    request: CreateNotificationRequest,
    user: UserContext = Depends(get_current_user_context),
    service: NotificationService = Depends(get_notification_service),
) -> CreateNotificationResponse:
    """
    Create a new notification for an account.

    **Request Body:**
    - `account_id` (required): The unique identifier for the account
    - `category` (required): Notification category (see enum for valid values)
    - `description` (required): Short description of the notification
    - `data` (optional): JSON object with additional data

    **Authorization:**
    - User must have access to the specified account

    **Returns:**
    - Success response with the created notification ID

    **Example:**
    ```json
    POST /api/v1/notifications
    {
        "account_id": "acc_123",
        "category": "KPI Performance",
        "description": "Revenue increased by 15% this quarter",
        "data": {
            "metric": "revenue",
            "change": 0.15,
            "period": "Q1 2024"
        }
    }
    ```
    """
    # Verify user has access to the account
    if not user.has_account_access(request.account_id):
        raise HTTPException(
            status_code=403,
            detail=f"Access denied to account {request.account_id}",
        )

    try:
        notification_id = await service.create_notification(
            account_id=request.account_id,
            category=request.category,
            description=request.description,
            data=request.data,
        )

        return CreateNotificationResponse(
            success=True,
            message="Notification created successfully",
            notification_id=notification_id,
        )

    except Exception as e:
        logger.error(f"Error creating notification: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create notification")


@router.get("/", response_model=list[NotificationWithStatus])
async def get_notifications(
    user: UserContext = Depends(get_current_user_context),
    account_id: str | None = Query(None, description="Filter by specific account ID"),
    include_archived: bool = Query(False, description="Include archived notifications"),
    limit: int = Query(
        50, ge=1, le=100, description="Maximum number of notifications to return"
    ),
    offset: int = Query(0, ge=0, description="Number of notifications to skip"),
    service: NotificationService = Depends(get_notification_service),
    db=Depends(get_neo4j_service),
) -> list[NotificationWithStatus]:
    """
    Get notifications for the current user.

    **Parameters:**
    - `account_id` (optional): Filter by specific account ID
    - `include_archived` (optional): Whether to include archived notifications (default: false)
    - `limit` (optional): Maximum number of notifications (1-100, default: 50)
    - `offset` (optional): Number of notifications to skip (default: 0)

    **Returns:**
    - List of notifications with user-specific status

    **Example:**
    ```
    GET /api/v1/notifications?account_id=acc_123&limit=20&offset=0
    ```
    """
    # Determine which accounts to query
    if account_id:
        # Verify user has access to the specified account
        if not user.has_account_access(account_id):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied to account {account_id}",
            )
        account_ids = [account_id]
    else:
        # Get all accessible accounts
        account_ids = user.accessible_accounts

        # For super admins and org admins, accessible_accounts might be empty since they have implicit access
        # We need to fetch all accounts they can access
        if not account_ids:
            if user.is_super_admin:
                # Super admins can see all accounts
                logger.info(
                    f"User {user.user_id} is super admin, fetching all accounts"
                )
                query = "MATCH (acc:Account) RETURN acc.account_id as account_id"
                result = await db.execute_query(query, {})
                account_ids = [record["account_id"] for record in result]

            elif any(
                role == "admin" for role in user.organization_permissions.values()
            ):
                # Org admins can see all accounts in their organizations
                admin_orgs = [
                    org_id
                    for org_id, role in user.organization_permissions.items()
                    if role == "admin"
                ]
                if admin_orgs:
                    logger.info(
                        f"User {user.user_id} is org admin, fetching organization accounts"
                    )
                    query = """
                    MATCH (org:Organization)<-[:BELONGS_TO]-(acc:Account)
                    WHERE org.organization_id IN $org_ids
                    RETURN DISTINCT acc.account_id as account_id
                    """
                    result = await db.execute_query(query, {"org_ids": admin_orgs})
                    account_ids = [record["account_id"] for record in result]

    if not account_ids:
        return []

    try:
        notifications = await service.get_user_notifications(
            user_id=user.user_id,
            account_ids=account_ids,
            include_archived=include_archived,
            limit=limit,
            offset=offset,
        )

        return notifications

    except Exception as e:
        logger.error(f"Error fetching notifications: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch notifications")


@router.put("/{notification_id}/status", response_model=SuccessResponse)
async def update_notification_status(
    notification_id: str,
    request: UpdateNotificationStatusRequest,
    user: UserContext = Depends(get_current_user_context),
    service: NotificationService = Depends(get_notification_service),
) -> SuccessResponse:
    """
    Update notification status for the current user.

    **Parameters:**
    - `notification_id` (path): The notification ID

    **Request Body:**
    - `status` (required): New status (excluded, unread, read, archived)

    **Returns:**
    - Success response

    **Example:**
    ```json
    PUT /api/v1/notifications/notif_acc_123_1234567890_456/status
    {
        "status": "read"
    }
    ```
    """
    try:
        # Note: We don't verify account access here because a user should be able to
        # update the status of any notification they can see, even if they lose
        # access to the account later

        await service.update_user_notification_status(
            user_id=user.user_id,
            notification_id=notification_id,
            status=request.status,
        )

        return SuccessResponse(
            success=True,
            message=f"Notification status updated to {request.status.value}",
        )

    except Exception as e:
        logger.error(f"Error updating notification status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error updating notification status: {e!s}"
        )


@router.get("/preferences", response_model=UserNotificationPreferences)
async def get_notification_preferences(
    user: UserContext = Depends(get_current_user_context),
    service: NotificationService = Depends(get_notification_service),
) -> UserNotificationPreferences:
    """
    Get current user's notification preferences.

    **Returns:**
    - User's notification preferences including categories and channels

    **Example:**
    ```
    GET /api/v1/notifications/preferences
    ```
    """
    try:
        preferences = await service.get_user_preferences(user.user_id)
        return preferences

    except Exception as e:
        logger.error(f"Error fetching notification preferences: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error fetching notification preferences: {e!s}"
        )


@router.put("/preferences", response_model=SuccessResponse)
async def update_notification_preferences(
    preferences: UserNotificationPreferences,
    user: UserContext = Depends(get_current_user_context),
    service: NotificationService = Depends(get_notification_service),
) -> SuccessResponse:
    """
    Update current user's notification preferences.

    **Request Body:**
    - `categories` (required): List of selected notification categories
    - `channels` (required): List of selected channels (ui, slack, email)

    **Returns:**
    - Success response

    **Example:**
    ```json
    PUT /api/v1/notifications/preferences
    {
        "categories": ["KPI Performance", "Data Quality Alert", "New Features"],
        "channels": ["ui", "email"]
    }
    ```
    """
    # Validate at least one channel is selected
    if not preferences.channels:
        raise HTTPException(
            status_code=400,
            detail="At least one notification channel must be selected",
        )

    try:
        await service.update_user_preferences(user.user_id, preferences)

        return SuccessResponse(
            success=True,
            message="Notification preferences updated successfully",
        )

    except Exception as e:
        logger.error(f"Error updating notification preferences: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error updating notification preferences: {e!s}"
        )


@router.get("/unread-count", response_model=dict[str, int])
async def get_unread_count(
    user: UserContext = Depends(get_current_user_context),
    account_id: str | None = Query(None, description="Filter by specific account ID"),
    service: NotificationService = Depends(get_notification_service),
) -> dict[str, int]:
    """
    Get count of unread notifications for the current user.

    **Parameters:**
    - `account_id` (optional): Filter by specific account ID

    **Returns:**
    - Object with unread_count field

    **Example:**
    ```
    GET /api/v1/notifications/unread-count?account_id=acc_123
    ```
    """
    # Determine which accounts to query
    if account_id:
        # Verify user has access to the specified account
        if not user.has_account_access(account_id):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied to account {account_id}",
            )
        account_ids = [account_id]
    else:
        # Get all accessible accounts
        account_ids = user.accessible_accounts

    if not account_ids:
        return {"unread_count": 0}

    try:
        unread_count = await service.get_unread_count(user.user_id, account_ids)

        return {"unread_count": unread_count}

    except Exception as e:
        logger.error(f"Error fetching unread count: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error fetching unread count: {e!s}"
        )


@router.post("/archive-old", response_model=dict[str, Any])
async def archive_old_notifications(
    user: UserContext = Depends(get_current_user_context),
    service: NotificationService = Depends(get_notification_service),
) -> dict[str, Any]:
    """
    Archive notifications older than 30 days.

    This endpoint should be called by a scheduled job or admin users.

    **Authorization:**
    - User must have admin role in at least one organization

    **Returns:**
    - Object with archived_count field

    **Example:**
    ```
    POST /api/v1/notifications/archive-old
    ```
    """
    # Verify user has admin access in at least one organization
    admin_orgs = [
        org_id
        for org_id, role in user.organization_permissions.items()
        if role in ["admin", "owner"]
    ]

    if not admin_orgs:
        raise HTTPException(
            status_code=403,
            detail="Admin access required to archive notifications",
        )

    try:
        archived_count = await service.archive_old_notifications()

        return {
            "success": True,
            "archived_count": archived_count,
            "message": f"Archived {archived_count} notifications",
        }

    except Exception as e:
        logger.error(f"Error archiving old notifications: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error archiving notifications: {e!s}"
        )
