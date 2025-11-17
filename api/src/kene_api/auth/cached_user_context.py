"""Cached user context for improved performance."""

import logging
from typing import Optional

from .models import UserContext

logger = logging.getLogger(__name__)

# Cache TTL in seconds (5 minutes)
USER_CONTEXT_CACHE_TTL = 300


class CachedUserContextService:
    """Service for caching user contexts."""

    def __init__(self):
        """Initialize the cached user context service."""
        self._redis = None  # Lazy initialization
    
    @property
    def redis(self):
        """Lazy-load Redis service to avoid initialization at module import."""
        if self._redis is None:
            from ..redis_client import get_redis_service
            self._redis = get_redis_service()
        return self._redis

    def _get_cache_key(self, user_id: str) -> str:
        """Generate cache key for user context."""
        return f"user_context:{user_id}"

    def get_user_context(self, user_id: str) -> Optional[UserContext]:
        """Get user context from cache."""
        if not self.redis.is_available():
            return None

        cache_key = self._get_cache_key(user_id)
        cached_data = self.redis.get_json(cache_key)

        if cached_data:
            try:
                # Check if cache has account_permissions field
                # If missing, invalidate cache to force fresh load from Firestore
                if "account_permissions" not in cached_data:
                    logger.warning(f"Cache for user {user_id} missing account_permissions field, invalidating cache")
                    self.invalidate_user_context(user_id)
                    return None

                return UserContext(
                    user_id=cached_data["user_id"],
                    email=cached_data["email"],
                    accessible_accounts=cached_data["accessible_accounts"],
                    permissions=cached_data["permissions"],
                    organization_permissions=cached_data["organization_permissions"],
                    account_permissions=cached_data.get("account_permissions", {}),
                )
            except Exception as e:
                logger.error(f"Failed to deserialize cached user context: {e}")
                return None

        return None

    def set_user_context(self, user_context: UserContext) -> bool:
        """Cache user context."""
        if not self.redis.is_available():
            return False

        cache_key = self._get_cache_key(user_context.user_id)

        # Convert to dictionary for caching
        context_data = {
            "user_id": user_context.user_id,
            "email": user_context.email,
            "accessible_accounts": user_context.accessible_accounts,
            "permissions": user_context.permissions,
            "organization_permissions": user_context.organization_permissions,
            "account_permissions": user_context.account_permissions,
        }

        return self.redis.set_json(cache_key, context_data, USER_CONTEXT_CACHE_TTL)

    def invalidate_user_context(self, user_id: str) -> bool:
        """Invalidate cached user context."""
        if not self.redis.is_available():
            return False

        cache_key = self._get_cache_key(user_id)
        return self.redis.delete(cache_key)


# Global cached user context service
cached_user_context_service = CachedUserContextService()


def get_cached_user_context_service() -> CachedUserContextService:
    """Get cached user context service instance."""
    return cached_user_context_service
