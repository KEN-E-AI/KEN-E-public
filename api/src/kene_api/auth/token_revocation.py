"""Token revocation mechanism for Firebase Auth tokens."""

import logging
from datetime import datetime, timedelta

from google.cloud import firestore

from ..firestore import get_firestore_service
from .audit_logger import SecurityEventType, get_audit_logger

logger = logging.getLogger(__name__)


class TokenRevocationService:
    """Service for managing revoked tokens."""

    def __init__(self):
        """Initialize the token revocation service."""
        self.collection_name = "revoked_tokens"
        self._redis = (
            None  # Lazy initialization to avoid Redis connection at import time
        )
        # Cache revoked tokens for 1 hour
        self.cache_ttl = 3600

    @property
    def redis(self):
        """Lazy-load Redis service to avoid initialization at module import."""
        if self._redis is None:
            from ..redis_client import get_redis_service

            self._redis = get_redis_service()
        return self._redis

    async def revoke_token(
        self,
        token_id: str,
        user_id: str,
        reason: str | None = None,
        revoked_by: str | None = None,
        expires_at: datetime | None = None,
    ) -> None:
        """Revoke a token.

        Args:
            token_id: The JWT ID (jti) of the token to revoke
            user_id: The user ID associated with the token
            reason: Optional reason for revocation
            revoked_by: Optional ID of user who revoked the token
            expires_at: When the token expires (for cleanup)
        """
        if not token_id:
            raise ValueError(
                "token_id is required to revoke an individual token; "
                "use revoke_all_user_tokens for blanket revocation."
            )

        firestore_service = get_firestore_service()
        db = firestore_service.get_client()

        # Create revocation record
        revocation_data = {
            "token_id": token_id,
            "user_id": user_id,
            "reason": reason,
            "revoked_by": revoked_by,
            "revoked_at": firestore.SERVER_TIMESTAMP,
            "expires_at": expires_at or datetime.utcnow() + timedelta(days=30),
        }

        # Store in Firestore
        db.collection(self.collection_name).document(token_id).set(revocation_data)

        # Cache in Redis for fast lookup
        if self.redis.is_available():
            cache_key = f"revoked_token:{token_id}"
            self.redis.set(cache_key, "1", ttl=self.cache_ttl)

        # Log the revocation
        audit_logger = get_audit_logger()
        await audit_logger.log_token_revoked(
            user_id=user_id,
            token_id=token_id,
            reason=reason,
            revoked_by=revoked_by,
        )

        logger.info(f"Token {token_id} revoked for user {user_id}")

    async def revoke_all_user_tokens(
        self,
        user_id: str,
        reason: str | None = None,
        revoked_by: str | None = None,
    ) -> None:
        """Revoke all tokens for a user.

        Args:
            user_id: The user whose tokens to revoke
            reason: Optional reason for revocation
            revoked_by: Optional ID of user who revoked the tokens
        """
        firestore_service = get_firestore_service()
        db = firestore_service.get_client()

        # Create a special record that indicates all tokens before this time are revoked
        revocation_data = {
            "user_id": user_id,
            "revoke_all_before": firestore.SERVER_TIMESTAMP,
            "reason": reason,
            "revoked_by": revoked_by,
            "created_at": firestore.SERVER_TIMESTAMP,
        }

        # Store with user_id as document ID for easy lookup
        db.collection(f"{self.collection_name}_all").document(user_id).set(
            revocation_data
        )

        # Cache in Redis
        if self.redis.is_available():
            cache_key = f"revoked_all_tokens:{user_id}"
            # Store the timestamp when all tokens were revoked
            self.redis.set(cache_key, datetime.utcnow().isoformat(), ttl=self.cache_ttl)

        # Log the bulk revocation
        audit_logger = get_audit_logger()
        await audit_logger.log_event(
            event_type=SecurityEventType.TOKEN_REVOKED,
            user_id=user_id,
            details={
                "action": "revoke_all_tokens",
                "reason": reason,
                "revoked_by": revoked_by,
            },
            severity="WARNING",
        )

        logger.info(f"All tokens revoked for user {user_id}")

    async def is_token_revoked(
        self, token_id: str, user_id: str, issued_at: float | None = None
    ) -> bool:
        """Check if a token is revoked.

        Args:
            token_id: The JWT ID (jti) to check
            user_id: The user ID associated with the token
            issued_at: When the token was issued (Unix timestamp)

        Returns:
            True if the token is revoked, False otherwise
        """
        # An empty token_id means the decoded JWT had no jti and no sub+iat
        # fallback — there is no individual revocation record keyed on "", and
        # Firestore rejects the empty document path. Skip the per-token lookup
        # and fall through to the user-wide revoke_all check, which keys only
        # on user_id + issued_at.
        has_token_id = bool(token_id)

        # Check Redis first — revoke_token() and revoke_all_user_tokens()
        # write to both Redis AND Firestore, so Redis is authoritative
        # when available. Firestore is only needed as fallback when Redis
        # is down.
        if self.redis.is_available():
            if has_token_id:
                cache_key = f"revoked_token:{token_id}"
                if self.redis.get(cache_key):
                    return True

            all_tokens_key = f"revoked_all_tokens:{user_id}"
            revoke_all_timestamp = self.redis.get(all_tokens_key)
            if revoke_all_timestamp and issued_at:
                revoke_time = datetime.fromisoformat(revoke_all_timestamp).timestamp()
                if issued_at < revoke_time:
                    return True

            # Redis is available and has no revocation record — token is valid
            return False

        # Fall back to Firestore only when Redis is unavailable
        firestore_service = get_firestore_service()
        db = firestore_service.get_client()

        if has_token_id:
            token_doc = db.collection(self.collection_name).document(token_id).get()
            if token_doc.exists:
                return True

        if issued_at:
            all_tokens_doc = (
                db.collection(f"{self.collection_name}_all").document(user_id).get()
            )
            if all_tokens_doc.exists:
                data = all_tokens_doc.to_dict()
                revoke_all_before = data.get("revoke_all_before")
                if revoke_all_before and isinstance(revoke_all_before, datetime):
                    if issued_at < revoke_all_before.timestamp():
                        return True

        return False

    async def cleanup_expired_revocations(self) -> int:
        """Clean up expired token revocations.

        Returns:
            Number of records cleaned up
        """
        firestore_service = get_firestore_service()
        db = firestore_service.get_client()

        # Query for expired revocations
        now = datetime.utcnow()
        expired_docs = (
            db.collection(self.collection_name).where("expires_at", "<", now).stream()
        )

        count = 0
        batch = db.batch()

        for doc in expired_docs:
            batch.delete(doc.reference)
            count += 1

            # Commit every 100 deletions
            if count % 100 == 0:
                batch.commit()
                batch = db.batch()

        # Commit remaining deletions
        if count % 100 != 0:
            batch.commit()

        logger.info(f"Cleaned up {count} expired token revocations")
        return count


# Global token revocation service
token_revocation_service = TokenRevocationService()


def get_token_revocation_service() -> TokenRevocationService:
    """Get token revocation service instance."""
    return token_revocation_service
