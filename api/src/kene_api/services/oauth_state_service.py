"""OAuth state storage service using Firestore."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from google.cloud import firestore

from ..models.oauth_models import OAuthState

logger = logging.getLogger(__name__)

OAUTH_STATES_COLLECTION = "oauth_states"


class OAuthStateService:
    """Service for managing OAuth state tokens in Firestore."""

    def __init__(self, db: firestore.Client):
        """Initialize the OAuth state service.

        Args:
            db: Firestore client instance
        """
        self.db = db
        self.collection = self.db.collection(OAUTH_STATES_COLLECTION)

    async def create_state(
        self,
        state_token: str,
        user_id: str,
        account_id: str,
        integration_type: str,
        ttl_minutes: int = 15,
        metadata: dict[str, Any] | None = None,
    ) -> OAuthState:
        """Create and store a new OAuth state.

        Args:
            state_token: Unique state token
            user_id: User ID initiating the flow
            account_id: Account ID for the integration
            integration_type: Type of integration (e.g., 'google_analytics')
            ttl_minutes: Time to live in minutes (default: 15)
            metadata: Additional metadata

        Returns:
            Created OAuthState instance
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=ttl_minutes)

        oauth_state = OAuthState(
            state_token=state_token,
            user_id=user_id,
            account_id=account_id,
            created_at=now,
            expires_at=expires_at,
            integration_type=integration_type,
            metadata=metadata or {},
        )

        # Store in Firestore (run sync operation in thread pool)
        doc_ref = self.collection.document(state_token)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, doc_ref.set, oauth_state.model_dump(mode="json")
        )

        logger.info(f"Created OAuth state for user {user_id}, account {account_id}")

        return oauth_state

    async def get_state(self, state_token: str) -> OAuthState | None:
        """Retrieve and validate an OAuth state.

        Args:
            state_token: The state token to retrieve

        Returns:
            OAuthState if valid and not expired, None otherwise
        """
        try:
            doc_ref = self.collection.document(state_token)
            # Run sync operation in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            doc = await loop.run_in_executor(None, doc_ref.get)

            if not doc.exists:
                logger.warning(f"State token not found: {state_token}")
                return None

            data = doc.to_dict()
            if not data:
                return None

            # Convert timestamps if needed
            if isinstance(data.get("created_at"), firestore.SERVER_TIMESTAMP.__class__):
                data["created_at"] = datetime.now(timezone.utc)
            if isinstance(data.get("expires_at"), firestore.SERVER_TIMESTAMP.__class__):
                data["expires_at"] = datetime.now(timezone.utc)

            oauth_state = OAuthState(**data)

            # Check if expired
            if datetime.now(timezone.utc) > oauth_state.expires_at:
                logger.warning(f"State token expired: {state_token}")
                # Clean up expired state
                await self.delete_state(state_token)
                return None

            return oauth_state

        except Exception as e:
            logger.error(f"Error retrieving OAuth state: {e}")
            return None

    async def delete_state(self, state_token: str) -> bool:
        """Delete an OAuth state.

        Args:
            state_token: The state token to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            doc_ref = self.collection.document(state_token)
            # Run sync operation in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, doc_ref.delete)
            logger.info(f"Deleted OAuth state: {state_token}")
            return True
        except Exception as e:
            logger.error(f"Error deleting OAuth state: {e}")
            return False

    async def cleanup_expired_states(self) -> int:
        """Clean up expired OAuth states.

        Returns:
            Number of states deleted
        """
        try:
            now = datetime.now(timezone.utc)
            # Query for expired states
            expired_query = self.collection.where("expires_at", "<", now)

            # Run sync operations in thread pool
            loop = asyncio.get_event_loop()
            expired_docs = await loop.run_in_executor(
                None, list, expired_query.stream()
            )

            count = 0
            batch = self.db.batch()
            batch_size = 0

            for doc in expired_docs:
                batch.delete(doc.reference)
                batch_size += 1
                count += 1

                # Commit in batches of 500 (Firestore limit)
                if batch_size >= 500:
                    await loop.run_in_executor(None, batch.commit)
                    batch = self.db.batch()
                    batch_size = 0

            # Commit remaining
            if batch_size > 0:
                await loop.run_in_executor(None, batch.commit)

            if count > 0:
                logger.info(f"Cleaned up {count} expired OAuth states")

            return count

        except Exception as e:
            logger.error(f"Error cleaning up expired states: {e}")
            return 0
