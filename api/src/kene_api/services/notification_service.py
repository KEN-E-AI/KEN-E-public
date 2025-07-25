"""Notification service for managing notifications and user preferences."""

import logging
import random
from datetime import datetime, timedelta
from typing import Any

from google.cloud import firestore

from ..models.kene_models import (
    NotificationCategory,
    NotificationChannel,
    NotificationStatus,
    NotificationWithStatus,
    UserNotificationPreferences,
)

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing notifications and user preferences."""

    def __init__(self, firestore_db: firestore.Client):
        """Initialize the notification service.
        
        Args:
            firestore_db: Firestore client instance
        """
        self.db = firestore_db

    async def create_notification(
        self,
        account_id: str,
        category: NotificationCategory,
        description: str,
        data: dict[str, Any] | None = None,
    ) -> str:
        """Create a new notification for an account.
        
        Args:
            account_id: The account ID this notification belongs to
            category: The notification category
            description: Short description of the notification
            data: Optional JSON data
            
        Returns:
            The created notification ID
        """
        # Generate unique notification ID
        timestamp_ms = int(datetime.now().timestamp() * 1000)
        random_num = random.randint(0, 1000)
        notification_id = f"notif_{account_id}_{timestamp_ms}_{random_num}"
        
        # Calculate auto-archive timestamp (30 days from now)
        archived_at = (datetime.now() + timedelta(days=30)).isoformat()
        
        # Create notification document
        notification_data = {
            "id": notification_id,
            "account_id": account_id,
            "category": category.value,
            "description": description,
            "data": data or {},
            "created_at": datetime.now().isoformat(),
            "archived_at": archived_at,
        }
        
        # Store in Firestore
        self.db.collection("notifications").document(notification_id).set(notification_data)
        
        # Initialize status for all users with access to this account
        await self._initialize_user_statuses(account_id, notification_id, category)
        
        logger.info(f"Created notification {notification_id} for account {account_id}")
        return notification_id

    async def _initialize_user_statuses(
        self,
        account_id: str,
        notification_id: str,
        category: NotificationCategory,
    ) -> None:
        """Initialize notification status for all users with access to the account.
        
        Args:
            account_id: The account ID
            notification_id: The notification ID
            category: The notification category
        """
        # Get all users with access to this account
        users_ref = self.db.collection("users")
        users = users_ref.stream()
        
        batch = self.db.batch()
        batch_count = 0
        
        for user_doc in users:
            user_data = user_doc.to_dict()
            user_id = user_doc.id
            
            # Check if user has access to this account
            permissions = user_data.get("permissions", {})
            account_permissions = permissions.get("accounts", {})
            
            if account_id in account_permissions:
                # Check user's notification preferences
                user_prefs = await self.get_user_preferences(user_id)
                
                # Determine initial status based on preferences
                if category in user_prefs.categories:
                    status = NotificationStatus.UNREAD
                else:
                    status = NotificationStatus.EXCLUDED
                
                # Create status document
                status_ref = (
                    self.db.collection("users")
                    .document(user_id)
                    .collection("notification_status")
                    .document(notification_id)
                )
                
                status_data = {
                    "notification_id": notification_id,
                    "status": status.value,
                    "updated_at": datetime.now().isoformat(),
                }
                
                batch.set(status_ref, status_data)
                batch_count += 1
                
                # Commit batch every 500 operations (Firestore limit)
                if batch_count >= 500:
                    batch.commit()
                    batch = self.db.batch()
                    batch_count = 0
        
        # Commit any remaining operations
        if batch_count > 0:
            batch.commit()

    async def get_user_notifications(
        self,
        user_id: str,
        account_ids: list[str],
        include_archived: bool = False,
    ) -> list[NotificationWithStatus]:
        """Get notifications for a user across their accessible accounts.
        
        Args:
            user_id: The user ID
            account_ids: List of account IDs the user has access to
            include_archived: Whether to include archived notifications
            
        Returns:
            List of notifications with user-specific status
        """
        notifications = []
        
        # Query notifications for all accessible accounts
        notif_query = self.db.collection("notifications").where(
            "account_id", "in", account_ids
        )
        
        # Filter out auto-archived if requested
        if not include_archived:
            now = datetime.now().isoformat()
            notif_query = notif_query.where("archived_at", ">", now)
        
        notif_docs = notif_query.stream()
        
        # Get user's notification statuses
        status_collection = (
            self.db.collection("users")
            .document(user_id)
            .collection("notification_status")
        )
        
        for notif_doc in notif_docs:
            notif_data = notif_doc.to_dict()
            notification_id = notif_data["id"]
            
            # Get user-specific status
            status_doc = status_collection.document(notification_id).get()
            
            if status_doc.exists:
                status_data = status_doc.to_dict()
                
                # Skip if user archived it (unless include_archived is True)
                if not include_archived and status_data.get("status") == NotificationStatus.ARCHIVED.value:
                    continue
                
                # Create NotificationWithStatus
                notification = NotificationWithStatus(
                    id=notif_data["id"],
                    account_id=notif_data["account_id"],
                    category=NotificationCategory(notif_data["category"]),
                    description=notif_data["description"],
                    data=notif_data.get("data"),
                    created_at=notif_data["created_at"],
                    archived_at=notif_data.get("archived_at"),
                    status=NotificationStatus(status_data["status"]),
                    read_at=status_data.get("read_at"),
                    user_archived_at=status_data.get("archived_at"),
                )
                
                notifications.append(notification)
        
        # Sort by created_at descending (newest first)
        notifications.sort(key=lambda x: x.created_at, reverse=True)
        
        return notifications

    async def update_user_notification_status(
        self,
        user_id: str,
        notification_id: str,
        status: NotificationStatus,
    ) -> None:
        """Update notification status for a specific user.
        
        Args:
            user_id: The user ID
            notification_id: The notification ID
            status: The new status
        """
        status_ref = (
            self.db.collection("users")
            .document(user_id)
            .collection("notification_status")
            .document(notification_id)
        )
        
        update_data = {
            "status": status.value,
            "updated_at": datetime.now().isoformat(),
        }
        
        # Add timestamps for specific status changes
        if status == NotificationStatus.READ:
            update_data["read_at"] = datetime.now().isoformat()
        elif status == NotificationStatus.ARCHIVED:
            update_data["archived_at"] = datetime.now().isoformat()
        
        status_ref.update(update_data)
        
        logger.info(f"Updated notification {notification_id} status to {status.value} for user {user_id}")

    async def get_user_preferences(self, user_id: str) -> UserNotificationPreferences:
        """Get user's notification preferences.
        
        Args:
            user_id: The user ID
            
        Returns:
            User's notification preferences
        """
        pref_ref = (
            self.db.collection("users")
            .document(user_id)
            .collection("preferences")
            .document("notifications")
        )
        
        pref_doc = pref_ref.get()
        
        if pref_doc.exists:
            pref_data = pref_doc.to_dict()
            return UserNotificationPreferences(
                categories=[NotificationCategory(cat) for cat in pref_data.get("categories", [])],
                channels=[NotificationChannel(ch) for ch in pref_data.get("channels", ["ui"])],
                updated_at=pref_data.get("updated_at", datetime.now().isoformat()),
            )
        else:
            # Return default preferences if not set
            default_prefs = UserNotificationPreferences(
                categories=list(NotificationCategory),  # All categories enabled by default
                channels=[NotificationChannel.UI],  # UI only by default
                updated_at=datetime.now().isoformat(),
            )
            
            # Save default preferences
            await self.update_user_preferences(user_id, default_prefs)
            
            return default_prefs

    async def update_user_preferences(
        self,
        user_id: str,
        preferences: UserNotificationPreferences,
    ) -> None:
        """Update user's notification preferences.
        
        Args:
            user_id: The user ID
            preferences: The new preferences
        """
        pref_ref = (
            self.db.collection("users")
            .document(user_id)
            .collection("preferences")
            .document("notifications")
        )
        
        pref_data = {
            "categories": [cat.value for cat in preferences.categories],
            "channels": [ch.value for ch in preferences.channels],
            "updated_at": datetime.now().isoformat(),
        }
        
        pref_ref.set(pref_data)
        
        logger.info(f"Updated notification preferences for user {user_id}")

    async def get_unread_count(self, user_id: str, account_ids: list[str]) -> int:
        """Get count of unread notifications for a user.
        
        Args:
            user_id: The user ID
            account_ids: List of account IDs the user has access to
            
        Returns:
            Count of unread notifications
        """
        # Get active notifications for accessible accounts
        now = datetime.now().isoformat()
        notif_query = (
            self.db.collection("notifications")
            .where("account_id", "in", account_ids)
            .where("archived_at", ">", now)
        )
        
        notif_docs = notif_query.stream()
        
        # Count unread notifications
        unread_count = 0
        status_collection = (
            self.db.collection("users")
            .document(user_id)
            .collection("notification_status")
        )
        
        for notif_doc in notif_docs:
            notification_id = notif_doc.to_dict()["id"]
            status_doc = status_collection.document(notification_id).get()
            
            if status_doc.exists:
                status_data = status_doc.to_dict()
                if status_data.get("status") == NotificationStatus.UNREAD.value:
                    unread_count += 1
        
        return unread_count

    async def archive_old_notifications(self) -> int:
        """Archive notifications older than 30 days.
        
        This method should be called by a scheduled job.
        
        Returns:
            Number of notifications archived
        """
        now = datetime.now().isoformat()
        
        # Query all users
        users = self.db.collection("users").stream()
        
        archived_count = 0
        batch = self.db.batch()
        batch_count = 0
        
        for user_doc in users:
            user_id = user_doc.id
            
            # Query notification statuses that should be auto-archived
            status_query = (
                self.db.collection("users")
                .document(user_id)
                .collection("notification_status")
                .where("status", "!=", NotificationStatus.ARCHIVED.value)
            )
            
            status_docs = status_query.stream()
            
            for status_doc in status_docs:
                status_data = status_doc.to_dict()
                notification_id = status_data["notification_id"]
                
                # Check if notification should be archived
                notif_doc = self.db.collection("notifications").document(notification_id).get()
                
                if notif_doc.exists:
                    notif_data = notif_doc.to_dict()
                    if notif_data.get("archived_at", "") <= now:
                        # Archive this notification
                        status_ref = (
                            self.db.collection("users")
                            .document(user_id)
                            .collection("notification_status")
                            .document(notification_id)
                        )
                        
                        batch.update(
                            status_ref,
                            {
                                "status": NotificationStatus.ARCHIVED.value,
                                "archived_at": now,
                                "updated_at": now,
                            },
                        )
                        
                        archived_count += 1
                        batch_count += 1
                        
                        # Commit batch every 500 operations
                        if batch_count >= 500:
                            batch.commit()
                            batch = self.db.batch()
                            batch_count = 0
        
        # Commit any remaining operations
        if batch_count > 0:
            batch.commit()
        
        logger.info(f"Auto-archived {archived_count} notifications")
        return archived_count