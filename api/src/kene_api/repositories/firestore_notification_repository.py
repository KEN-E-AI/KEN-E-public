"""Firestore implementation of notification repository."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from google.cloud import firestore
from google.cloud.firestore_v1.field_path import FieldPath

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
    """Firestore implementation of notification repository.

    All Firestore operations use asyncio.to_thread() to avoid blocking
    the asyncio event loop, since the synchronous Firestore client's
    .stream(), .get(), .set(), etc. make blocking network calls.
    """

    def __init__(self, db: firestore.Client):
        self.db = db

    async def create(self, notification: Notification) -> str:
        """Create a new notification in Firestore."""
        notification_data = notification.model_dump()

        def _write() -> None:
            self.db.collection("notifications").document(notification.id).set(
                notification_data
            )

        await asyncio.to_thread(_write)
        return notification.id

    async def get_by_id(self, notification_id: str) -> Notification | None:
        """Get a notification by ID from Firestore."""

        def _read() -> Any:
            return self.db.collection("notifications").document(notification_id).get()

        doc = await asyncio.to_thread(_read)

        if not doc.exists:
            return None

        data = doc.to_dict()
        return Notification(**data)

    def _create_batches(
        self, account_ids: list[str], batch_size: int = 10
    ) -> list[list[str]]:
        """Split account IDs into batches of specified size."""
        return [
            account_ids[i : i + batch_size]
            for i in range(0, len(account_ids), batch_size)
        ]

    async def _fetch_batch(
        self,
        batch_account_ids: list[str],
        include_archived: bool,
    ) -> list[Notification]:
        """Fetch notifications for a single batch of account IDs."""
        query = self.db.collection("notifications").where(
            filter=firestore.FieldFilter("account_id", "in", batch_account_ids)
        )

        if not include_archived:
            now = datetime.now().isoformat()
            query = query.where(filter=firestore.FieldFilter("archived_at", ">", now))
            query = query.order_by("archived_at", direction=firestore.Query.ASCENDING)

        def _run_query() -> list[dict[str, Any]]:
            try:
                ordered_query = query.order_by(
                    "created_at", direction=firestore.Query.DESCENDING
                )
                return [doc.to_dict() for doc in ordered_query.stream()]
            except Exception as e:
                logger.warning(f"Firestore query failed (likely missing index): {e}")
                return [doc.to_dict() for doc in query.stream()]

        docs_data = await asyncio.to_thread(_run_query)
        return [Notification(**data) for data in docs_data]

    async def _fetch_batches_parallel(
        self,
        batches: list[list[str]],
        include_archived: bool,
    ) -> list[Notification]:
        """Fetch multiple batches of notifications in parallel."""
        tasks = [self._fetch_batch(batch, include_archived) for batch in batches]
        batch_results = await asyncio.gather(*tasks)

        all_notifications = []
        for batch_notifications in batch_results:
            all_notifications.extend(batch_notifications)

        return all_notifications

    def _sort_notifications(
        self, notifications: list[Notification]
    ) -> list[Notification]:
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
        if not account_ids:
            return []

        if len(account_ids) <= 10 and limit and limit <= 100:
            return await self._fetch_batch_with_pagination(
                account_ids, include_archived, limit, offset
            )

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
            filter=firestore.FieldFilter("account_id", "in", account_ids)
        )

        if not include_archived:
            now = datetime.now().isoformat()
            query = query.where(filter=firestore.FieldFilter("archived_at", ">", now))
            query = query.order_by("archived_at", direction=firestore.Query.ASCENDING)

        query = query.order_by("created_at", direction=firestore.Query.DESCENDING)
        if offset > 0:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)

        def _run_query() -> list[dict[str, Any]]:
            return [doc.to_dict() for doc in query.stream()]

        try:
            docs_data = await asyncio.to_thread(_run_query)
        except Exception as e:
            logger.warning(f"Firestore query with pagination failed: {e}")
            notifications = await self._fetch_batch(account_ids, include_archived)
            notifications = self._sort_notifications(notifications)
            return self._apply_pagination(notifications, limit, offset)

        return [Notification(**data) for data in docs_data]

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

        def _fetch_all_statuses() -> dict[str, dict[str, Any]]:
            statuses: dict[str, dict[str, Any]] = {}
            for i in range(0, len(notification_ids), 10):
                batch_ids = notification_ids[i : i + 10]
                docs = status_collection.where(
                    filter=firestore.FieldFilter(
                        FieldPath.document_id(), "in", batch_ids
                    )
                ).stream()
                for doc in docs:
                    statuses[doc.id] = doc.to_dict()
            return statuses

        return await asyncio.to_thread(_fetch_all_statuses)

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

        update_data: dict[str, str] = {
            "status": status.value,
            "updated_at": datetime.now().isoformat(),
        }

        if status == NotificationStatus.READ:
            update_data["read_at"] = datetime.now().isoformat()
        elif status == NotificationStatus.ARCHIVED:
            update_data["archived_at"] = datetime.now().isoformat()

        await asyncio.to_thread(status_ref.update, update_data)

    async def get_user_preferences(
        self, user_id: str
    ) -> UserNotificationPreferences | None:
        """Get user's notification preferences from Firestore."""
        pref_ref = (
            self.db.collection("users")
            .document(user_id)
            .collection("preferences")
            .document("notifications")
        )

        pref_doc = await asyncio.to_thread(pref_ref.get)

        if not pref_doc.exists:
            return None

        pref_data = pref_doc.to_dict()
        return UserNotificationPreferences(
            categories=[
                NotificationCategory(cat) for cat in pref_data.get("categories", [])
            ],
            channels=[
                NotificationChannel(ch) for ch in pref_data.get("channels", ["ui"])
            ],
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

        await asyncio.to_thread(pref_ref.set, pref_data)

    async def count_unread(self, user_id: str, account_ids: list[str]) -> int:
        """Count unread notifications for a user in Firestore."""
        notifications = await self.get_by_account(account_ids, include_archived=False)

        if not notifications:
            return 0

        notification_ids = [n.id for n in notifications]
        user_statuses = await self.get_user_statuses(user_id, notification_ids)

        unread_count = 0
        for notification in notifications:
            status_data = user_statuses.get(notification.id, {"status": "unread"})
            if status_data.get("status") == NotificationStatus.UNREAD.value:
                unread_count += 1

        return unread_count

    async def get_users_by_account(
        self, account_id: str
    ) -> list[tuple[str, dict[str, Any]]]:
        """Get all users with access to an account from Firestore."""

        def _query_users() -> list[tuple[str, dict[str, Any]]]:
            users = []
            users_stream = self.db.collection("users").stream()
            for user_doc in users_stream:
                user_data = user_doc.to_dict()
                user_id = user_doc.id
                permissions = user_data.get("permissions", {})
                account_permissions = permissions.get("accounts", {})
                if account_id in account_permissions:
                    users.append((user_id, user_data))
            return users

        return await asyncio.to_thread(_query_users)

    async def batch_create_user_statuses(
        self,
        statuses: list[dict[str, Any]],
    ) -> None:
        """Create multiple user notification statuses in batch in Firestore."""

        def _batch_write() -> None:
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

                batch.set(
                    status_ref,
                    {
                        "notification_id": notification_id,
                        "status": status["status"],
                        "updated_at": status["updated_at"],
                    },
                )

                batch_count += 1

                if batch_count >= 500:
                    batch.commit()
                    batch = self.db.batch()
                    batch_count = 0

            if batch_count > 0:
                batch.commit()

        await asyncio.to_thread(_batch_write)

    async def archive_old_notifications(self, days: int = 30) -> int:
        """Archive notifications older than specified days in Firestore."""

        def _archive() -> int:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            archived_count = 0
            users = self.db.collection("users").stream()
            batch = self.db.batch()
            batch_count = 0

            for user_doc in users:
                user_id = user_doc.id
                status_query = (
                    self.db.collection("users")
                    .document(user_id)
                    .collection("notification_status")
                    .where(
                        filter=firestore.FieldFilter(
                            "status", "!=", NotificationStatus.ARCHIVED.value
                        )
                    )
                )
                status_docs = status_query.stream()

                for status_doc in status_docs:
                    status_data = status_doc.to_dict()
                    notification_id = status_data["notification_id"]

                    notif_doc = (
                        self.db.collection("notifications")
                        .document(notification_id)
                        .get()
                    )

                    if notif_doc.exists:
                        notif_data = notif_doc.to_dict()
                        if notif_data.get("created_at", "") < cutoff:
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

                            if batch_count >= 500:
                                batch.commit()
                                batch = self.db.batch()
                                batch_count = 0

            if batch_count > 0:
                batch.commit()

            logger.info(f"Auto-archived {archived_count} notifications")
            return archived_count

        return await asyncio.to_thread(_archive)
