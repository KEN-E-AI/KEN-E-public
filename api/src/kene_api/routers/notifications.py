"""Notifications router for managing notifications and user preferences."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import UserContext, get_current_user_context
from ..firestore import get_firestore_service
from ..models.kene_models import (
    CreateNotificationRequest,
    CreateNotificationResponse,
    NotificationWithStatus,
    SuccessResponse,
    UpdateNotificationStatusRequest,
    UserNotificationPreferences,
)
from ..services.notification_service import NotificationService

router = APIRouter(tags=["notifications"])
logger = logging.getLogger(__name__)


def get_notification_service(
    firestore_service = Depends(get_firestore_service),
) -> NotificationService:
    """Get notification service instance."""
    # Get the actual Firestore client from the service
    return NotificationService(firestore_service.get_client())




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
    
    **Note:** User must have appropriate permissions to create notifications for the specified account.
    """
    try:
        # Verify user has write access to the account
        if not user.has_account_access(request.account_id, required_roles=["owner", "admin", "editor"]):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions to create notifications for account {request.account_id}"
            )
        
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
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating notification: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating notification: {e!s}")


@router.get("/", response_model=list[NotificationWithStatus])
async def get_notifications(
    include_archived: bool = Query(False, description="Include archived notifications"),
    account_id: str | None = Query(None, description="Filter by specific account (optional)"),
    user: UserContext = Depends(get_current_user_context),
    service: NotificationService = Depends(get_notification_service),
) -> list[NotificationWithStatus]:
    """
    Get notifications for the current user across all accessible accounts.
    
    **Parameters:**
    - `include_archived` (optional): Whether to include archived notifications (default: false)
    - `account_id` (optional): Filter by specific account ID
    
    **Returns:**
    - List of notifications with user-specific status
    
    **Example:**
    ```
    GET /api/v1/notifications?include_archived=false
    GET /api/v1/notifications?account_id=acc_123
    ```
    
    **Note:** This endpoint returns notifications based on the requesting user's preferences.
    Each user may see different statuses for the same notification.
    """
    try:
        # Determine which accounts to fetch notifications for
        if account_id:
            # Verify user has access to the specified account
            if not user.has_account_access(account_id):
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied to account {account_id}"
                )
            account_ids = [account_id]
        else:
            # Get all accessible accounts
            account_ids = user.accessible_accounts
        
        notifications = await service.get_user_notifications(
            user_id=user.user_id,
            account_ids=account_ids,
            include_archived=include_archived,
        )
        
        return notifications
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching notifications: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching notifications: {e!s}")


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
        raise HTTPException(status_code=500, detail=f"Error updating notification status: {e!s}")


@router.get("/preferences", response_model=UserNotificationPreferences)
async def get_notification_preferences(
    user: UserContext = Depends(get_current_user_context),
    service: NotificationService = Depends(get_notification_service),
) -> UserNotificationPreferences:
    """
    Get user's notification preferences.
    
    **Returns:**
    - User's notification preferences including categories and channels
    
    **Example:**
    ```
    GET /api/v1/notifications/preferences
    ```
    """
    try:
        logger.info(f"Fetching notification preferences for user: {user.user_id}")
        preferences = await service.get_user_preferences(user.user_id)
        logger.info(f"Successfully fetched preferences: {preferences}")
        return preferences
        
    except Exception as e:
        logger.error(f"Error fetching notification preferences for user {user.user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching notification preferences: {e!s}")


@router.put("/preferences", response_model=SuccessResponse)
async def update_notification_preferences(
    preferences: UserNotificationPreferences,
    user: UserContext = Depends(get_current_user_context),
    service: NotificationService = Depends(get_notification_service),
) -> SuccessResponse:
    """
    Update user's notification preferences.
    
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
    try:
        await service.update_user_preferences(user.user_id, preferences)
        
        return SuccessResponse(
            success=True,
            message="Notification preferences updated successfully",
        )
        
    except Exception as e:
        logger.error(f"Error updating notification preferences: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating notification preferences: {e!s}")


@router.get("/unread-count", response_model=dict[str, int])
async def get_unread_count(
    account_id: str | None = Query(None, description="Filter by specific account (optional)"),
    user: UserContext = Depends(get_current_user_context),
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
    GET /api/v1/notifications/unread-count
    GET /api/v1/notifications/unread-count?account_id=acc_123
    ```
    """
    try:
        # Determine which accounts to count notifications for
        if account_id:
            # Verify user has access to the specified account
            if not user.has_account_access(account_id):
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied to account {account_id}"
                )
            account_ids = [account_id]
        else:
            # Get all accessible accounts
            account_ids = user.accessible_accounts
            
        unread_count = await service.get_unread_count(user.user_id, account_ids)
        
        return {"unread_count": unread_count}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching unread count: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching unread count: {e!s}")


@router.post("/archive-old", response_model=dict[str, Any])
async def archive_old_notifications(
    service: NotificationService = Depends(get_notification_service),
) -> dict[str, Any]:
    """
    Archive notifications older than 30 days.
    
    This endpoint should be called by a scheduled job.
    
    **Returns:**
    - Object with archived_count field
    
    **Example:**
    ```
    POST /api/v1/notifications/archive-old
    ```
    """
    try:
        archived_count = await service.archive_old_notifications()
        
        return {
            "success": True,
            "archived_count": archived_count,
            "message": f"Archived {archived_count} notifications",
        }
        
    except Exception as e:
        logger.error(f"Error archiving old notifications: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error archiving notifications: {e!s}")