"""Firestore implementation of notification repository."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from google.cloud import firestore
from google.cloud.firestore_v1.field_path import FieldPath

logger = logging.getLogger(__name__)

from ..models.kene_models import (
    Notification,
    NotificationCategory,
    NotificationChannel,
    NotificationStatus,
    UserNotificationPreferences,
)
from .notification_repository import NotificationRepository

logger = logging.getLogger(__name__)


class FirestoreNotificationRepository(NotificationRepository):
    """Firestore implementation of notification repository."""

    def __init__(self, db: firestore.Client):
        self.db = db

    async def create(self, notification: Notification) -> str:
        """Create a new notification in Firestore."""
        notification_data = notification.model_dump()
        self.db.collection("notifications").document(notification.id).set(notification_data)
        return notification.id

    async def get_by_id(self, notification_id: str) -> Notification | None:
        """Get a notification by ID from Firestore."""
        doc = self.db.collection("notifications").document(notification_id).get()
        
        if not doc.exists:
            return None
        
        data = doc.to_dict()
        return Notification(**data)

    def _create_batches(self, account_ids: list[str], batch_size: int = 10) -> list[list[str]]:
        """Split account IDs into batches of specified size."""
        return [account_ids[i:i + batch_size] for i in range(0, len(account_ids), batch_size)]
    
    async def _fetch_batch(
        self,
        batch_account_ids: list[str],
        include_archived: bool,
    ) -> list[Notification]:
        """Fetch notifications for a single batch of account IDs."""
        query = self.db.collection("notifications").where(
            "account_id", "in", batch_account_ids
        )
        
        if not include_archived:
            now = datetime.now().isoformat()
            query = query.where("archived_at", ">", now)
            # When filtering by archived_at, we need to order by archived_at first
            # to match the existing composite index
            query = query.order_by("archived_at", direction=firestore.Query.ASCENDING)
        
        # Try with ordering by created_at
        try:
            # Order by created_at descending
            # Note: This requires a composite index in Firestore
            ordered_query = query.order_by("created_at", direction=firestore.Query.DESCENDING)
            docs = ordered_query.stream()
        except Exception as e:
            # If there's an index issue, fall back to simpler query
            logger.warning(f"Firestore query failed (likely missing index): {e}")
            docs = query.stream()
        
        notifications = []
        for doc in docs:
            data = doc.to_dict()
            notifications.append(Notification(**data))
        
        return notifications
    
    async def _fetch_batches_parallel(
        self,
        batches: list[list[str]],
        include_archived: bool,
    ) -> list[Notification]:
        """Fetch multiple batches of notifications in parallel."""
        # Create tasks for parallel execution
        tasks = [
            self._fetch_batch(batch, include_archived)
            for batch in batches
        ]
        
        # Execute all batches in parallel
        batch_results = await asyncio.gather(*tasks)
        
        # Flatten the results
        all_notifications = []
        for batch_notifications in batch_results:
            all_notifications.extend(batch_notifications)
        
        return all_notifications
    
    def _sort_notifications(self, notifications: list[Notification]) -> list[Notification]:
        """Sort notifications by created_at in descending order."""
        return sorted(notifications, key=lambda n: n.created_at, reverse=True)
    
    def _apply_pagination(
        self,
        notifications: list[Notification],
        limit: int | None,
        offset: int,
    ) -> list[Notification]:
        """Apply pagination to a list of notifications."""
        if offset > 0:
            notifications = notifications[offset:]
        if limit:
            notifications = notifications[:limit]
        return notifications

    async def get_by_account(
        self,
        account_ids: list[str],
        include_archived: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Notification]:
        """Get notifications for specified accounts from Firestore.
        
        This method handles Firestore's limitation of 10 items in "IN" queries
        by batching the account IDs and fetching in parallel for better performance.
        """
        # Firestore doesn't allow empty arrays in "in" queries
        if not account_ids:
            return []
        
        # For small sets, use direct query with Firestore pagination
        if len(account_ids) <= 10 and limit and limit <= 100:
            # Single batch, can use Firestore's native pagination
            return await self._fetch_batch_with_pagination(
                account_ids, include_archived, limit, offset
            )
        
        # For larger sets, fetch all and paginate in memory
        batches = self._create_batches(account_ids)
        notifications = await self._fetch_batches_parallel(batches, include_archived)
        notifications = self._sort_notifications(notifications)
        return self._apply_pagination(notifications, limit, offset)
    
    async def _fetch_batch_with_pagination(
        self,
        account_ids: list[str],
        include_archived: bool,
        limit: int,
        offset: int,
    ) -> list[Notification]:
        """Fetch a single batch with Firestore-level pagination."""
        query = self.db.collection("notifications").where(
            "account_id", "in", account_ids
        )
        
        if not include_archived:
            now = datetime.now().isoformat()
            query = query.where("archived_at", ">", now)
            # When filtering by archived_at, we need to order by archived_at first
            # to match the existing composite index
            query = query.order_by("archived_at", direction=firestore.Query.ASCENDING)
        
        # Apply ordering by created_at
        query = query.order_by("created_at", direction=firestore.Query.DESCENDING)
        if offset > 0:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        
        try:
            docs = query.stream()
        except Exception as e:
            logger.warning(f"Firestore query with pagination failed: {e}")
            # Fallback to in-memory pagination
            notifications = await self._fetch_batch(account_ids, include_archived)
            notifications = self._sort_notifications(notifications)
            return self._apply_pagination(notifications, limit, offset)
        
        notifications = []
        for doc in docs:
            data = doc.to_dict()
            notifications.append(Notification(**data))
        
        return notifications

    async def get_user_statuses(
        self,
        user_id: str,
        notification_ids: list[str],
    ) -> dict[str, dict[str, Any]]:
        """Get user's statuses for specific notifications from Firestore."""
        status_collection = (
            self.db.collection("users")
            .document(user_id)
            .collection("notification_status")
        )
        
        statuses = {}
        
        # Firestore doesn't support WHERE IN with more than 10 values
        # So we need to batch the requests
        for i in range(0, len(notification_ids), 10):
            batch_ids = notification_ids[i:i + 10]
            
            docs = status_collection.where(
                FieldPath.document_id(), "in", batch_ids
            ).stream()
            
            for doc in docs:
                statuses[doc.id] = doc.to_dict()
        
        return statuses

    async def update_user_status(
        self,
        user_id: str,
        notification_id: str,
        status: NotificationStatus,
    ) -> None:
        """Update a user's notification status in Firestore."""
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
        
        if status == NotificationStatus.READ:
            update_data["read_at"] = datetime.now().isoformat()
        elif status == NotificationStatus.ARCHIVED:
            update_data["archived_at"] = datetime.now().isoformat()
        
        status_ref.update(update_data)

    async def get_user_preferences(self, user_id: str) -> UserNotificationPreferences | None:
        """Get user's notification preferences from Firestore."""
        pref_ref = (
            self.db.collection("users")
            .document(user_id)
            .collection("preferences")
            .document("notifications")
        )
        
        pref_doc = pref_ref.get()
        
        if not pref_doc.exists:
            return None
        
        pref_data = pref_doc.to_dict()
        return UserNotificationPreferences(
            categories=[NotificationCategory(cat) for cat in pref_data.get("categories", [])],
            channels=[NotificationChannel(ch) for ch in pref_data.get("channels", ["ui"])],
            updated_at=pref_data.get("updated_at", datetime.now().isoformat()),
        )

    async def set_user_preferences(
        self,
        user_id: str,
        preferences: UserNotificationPreferences,
    ) -> None:
        """Set user's notification preferences in Firestore."""
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

    async def count_unread(self, user_id: str, account_ids: list[str]) -> int:
        """Count unread notifications for a user in Firestore."""
        # Get active notifications for accessible accounts
        now = datetime.now().isoformat()
        
        # We need to count manually since Firestore doesn't support
        # counting with joins across collections
        notifications = await self.get_by_account(account_ids, include_archived=False)
        
        if not notifications:
            return 0
        
        # Get user statuses for these notifications
        notification_ids = [n.id for n in notifications]
        user_statuses = await self.get_user_statuses(user_id, notification_ids)
        
        # Count unread
        unread_count = 0
        for notification in notifications:
            status_data = user_statuses.get(notification.id, {"status": "unread"})
            if status_data.get("status") == NotificationStatus.UNREAD.value:
                unread_count += 1
        
        return unread_count

    async def get_users_by_account(self, account_id: str) -> list[tuple[str, dict[str, Any]]]:
        """Get all users with access to an account from Firestore."""
        users = []
        
        # Query all users
        users_stream = self.db.collection("users").stream()
        
        for user_doc in users_stream:
            user_data = user_doc.to_dict()
            user_id = user_doc.id
            
            # Check if user has access to this account
            permissions = user_data.get("permissions", {})
            account_permissions = permissions.get("accounts", {})
            
            if account_id in account_permissions:
                users.append((user_id, user_data))
        
        return users

    async def batch_create_user_statuses(
        self,
        statuses: list[dict[str, Any]],
    ) -> None:
        """Create multiple user notification statuses in batch in Firestore."""
        batch = self.db.batch()
        batch_count = 0
        
        for status in statuses:
            user_id = status["user_id"]
            notification_id = status["notification_id"]
            
            status_ref = (
                self.db.collection("users")
                .document(user_id)
                .collection("notification_status")
                .document(notification_id)
            )
            
            batch.set(status_ref, {
                "notification_id": notification_id,
                "status": status["status"],
                "updated_at": status["updated_at"],
            })
            
            batch_count += 1
            
            # Commit every 500 operations (Firestore limit)
            if batch_count >= 500:
                batch.commit()
                batch = self.db.batch()
                batch_count = 0
        
        # Commit remaining operations
        if batch_count > 0:
            batch.commit()

    async def archive_old_notifications(self, days: int = 30) -> int:
        """Archive notifications older than specified days in Firestore."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        archived_count = 0
        
        # Get all users
        users = self.db.collection("users").stream()
        
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
                    if notif_data.get("created_at", "") < cutoff:
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
                                "archived_at": datetime.now().isoformat(),
                                "updated_at": datetime.now().isoformat(),
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