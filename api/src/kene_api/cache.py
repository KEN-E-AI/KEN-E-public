"""Caching utilities for KEN-E API."""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

from redis import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class CacheService:
    """Service for caching data using Redis."""

    def __init__(self, redis_client: Optional[Redis] = None):
        """Initialize cache service.

        Args:
            redis_client: Optional Redis client. If not provided, caching is disabled.
        """
        self.redis = redis_client
        self._enabled = redis_client is not None

    @property
    def enabled(self) -> bool:
        """Check if caching is enabled."""
        return self._enabled

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found or cache disabled
        """
        if not self.enabled:
            return None

        try:
            value = self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except (RedisError, json.JSONDecodeError) as e:
            logger.error(f"Error getting cache key {key}: {str(e)}")
            return None

    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache (must be JSON serializable)
            ttl_seconds: Time to live in seconds (default 1 hour)

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            serialized = json.dumps(value)
            self.redis.setex(key, ttl_seconds, serialized)
            return True
        except (RedisError, json.JSONDecodeError, TypeError) as e:
            logger.error(f"Error setting cache key {key}: {str(e)}")
            return False

    def delete(self, key: str) -> bool:
        """Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            self.redis.delete(key)
            return True
        except RedisError as e:
            logger.error(f"Error deleting cache key {key}: {str(e)}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern.

        Args:
            pattern: Pattern to match (e.g., "industry_keywords:*")

        Returns:
            Number of keys deleted
        """
        if not self.enabled:
            return 0

        try:
            keys = list(self.redis.scan_iter(match=pattern))
            if keys:
                return self.redis.delete(*keys)
            return 0
        except RedisError as e:
            logger.error(f"Error deleting cache pattern {pattern}: {str(e)}")
            return 0
    
    def increment(self, key: str) -> bool:
        """Increment a counter in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            self.redis.incr(key)
            return True
        except RedisError as e:
            logger.error(f"Error incrementing cache key {key}: {str(e)}")
            return False
    
    def ttl(self, key: str) -> Optional[int]:
        """Get time-to-live for a key in seconds.
        
        Args:
            key: Cache key
            
        Returns:
            TTL in seconds, or None if key doesn't exist or error
        """
        if not self.enabled:
            return None
        
        try:
            ttl = self.redis.ttl(key)
            return ttl if ttl > 0 else None
        except RedisError as e:
            logger.error(f"Error getting TTL for cache key {key}: {str(e)}")
            return None


class InMemoryCache:
    """Simple in-memory cache for development/testing."""

    def __init__(self):
        self._cache: dict[str, tuple[Any, datetime]] = {}

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if key in self._cache:
            value, expiry = self._cache[key]
            if expiry > datetime.utcnow():
                return value
            else:
                del self._cache[key]
        return None

    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        """Set value in cache."""
        expiry = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        self._cache[key] = (value, expiry)
        return True

    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        import fnmatch

        keys_to_delete = [k for k in self._cache.keys() if fnmatch.fnmatch(k, pattern)]
        for key in keys_to_delete:
            del self._cache[key]
        return len(keys_to_delete)


# Cache key generators
def industry_keywords_key(industry: str) -> str:
    """Generate cache key for industry keywords."""
    normalized = industry.lower().replace(" ", "_").replace(",", "")
    return f"industry_keywords:{normalized}"


def all_industry_keywords_key() -> str:
    """Generate cache key for all industry keywords."""
    return "industry_keywords:all"


def monitoring_topics_key(account_id: str) -> str:
    """Generate cache key for monitoring topics."""
    return f"monitoring_topics:{account_id}"


# Cache decorators
def cache_result(
    key_func: Callable[..., str],
    ttl_seconds: int = 3600,
    cache_service: Optional[CacheService] = None,
):
    """Decorator to cache function results.

    Args:
        key_func: Function to generate cache key from arguments
        ttl_seconds: Time to live in seconds
        cache_service: Cache service instance (uses global if not provided)
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Get cache service
            cache = cache_service or getattr(func, "_cache_service", None)
            if not cache or not cache.enabled:
                return await func(*args, **kwargs)

            # Generate cache key
            cache_key = key_func(*args, **kwargs)

            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_value

            # Call function and cache result
            result = await func(*args, **kwargs)
            cache.set(cache_key, result, ttl_seconds)
            logger.debug(f"Cached result for key: {cache_key}")

            return result

        return wrapper

    return decorator
