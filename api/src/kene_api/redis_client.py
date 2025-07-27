"""Redis client configuration and utilities."""

import json
import logging
import os
from typing import Any, Optional

import redis
from redis.exceptions import ConnectionError, TimeoutError

logger = logging.getLogger(__name__)


class RedisService:
    """Redis service for caching."""
    
    def __init__(self):
        """Initialize Redis connection."""
        self.client: Optional[redis.Redis] = None
        self._initialized = False
        
    def initialize(self) -> None:
        """Initialize Redis connection with retry logic."""
        if self._initialized:
            return
            
        try:
            # Get Redis configuration from environment
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            redis_password = os.getenv("REDIS_PASSWORD")
            redis_db = int(os.getenv("REDIS_DB", "0"))
            
            # Create Redis client
            self.client = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password,
                db=redis_db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_error=[ConnectionError, TimeoutError],
                health_check_interval=30,
            )
            
            # Test connection
            self.client.ping()
            self._initialized = True
            logger.info(f"Redis connected successfully to {redis_host}:{redis_port}")
            
        except Exception as e:
            if os.getenv("SUPPRESS_REDIS_WARNING", "").lower() != "true":
                logger.warning(f"Failed to connect to Redis: {e}. Caching will be disabled.")
            self.client = None
            self._initialized = True  # Mark as initialized even if failed
    
    def is_available(self) -> bool:
        """Check if Redis is available."""
        if not self.client:
            return False
            
        try:
            self.client.ping()
            return True
        except Exception:
            return False
    
    def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        if not self.client:
            return None
            
        try:
            return self.client.get(key)
        except Exception as e:
            logger.error(f"Redis get error for key {key}: {e}")
            return None
    
    def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL."""
        if not self.client:
            return False
            
        try:
            if ttl:
                return bool(self.client.setex(key, ttl, value))
            else:
                return bool(self.client.set(key, value))
        except Exception as e:
            logger.error(f"Redis set error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.client:
            return False
            
        try:
            return bool(self.client.delete(key))
        except Exception as e:
            logger.error(f"Redis delete error for key {key}: {e}")
            return False
    
    def get_json(self, key: str) -> Optional[Any]:
        """Get JSON value from cache."""
        value = self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON for key {key}")
        return None
    
    def set_json(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set JSON value in cache."""
        try:
            json_value = json.dumps(value)
            return self.set(key, json_value, ttl)
        except (TypeError, json.JSONEncodeError) as e:
            logger.error(f"Failed to encode JSON for key {key}: {e}")
            return False


# Global Redis service instance
redis_service = RedisService()


def get_redis_service() -> RedisService:
    """Get Redis service instance."""
    if not redis_service._initialized:
        redis_service.initialize()
    return redis_service