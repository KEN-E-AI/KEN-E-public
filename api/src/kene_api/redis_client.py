"""Redis client configuration and utilities."""

import json
import logging
import os
from typing import Any

import redis
from redis.exceptions import ConnectionError, TimeoutError

logger = logging.getLogger(__name__)


# A serialize failure means the JSON cache write silently fell back to "no
# cache" for every subsequent request keyed on the same prefix — a soft outage
# that previously went unnoticed for weeks (load-test seed wrote a Firestore
# Timestamp into account_permissions, killing the user_context cache for the
# load-test user and pushing chat-sidebar p90 over the 15 s CD gate).  Alert
# on rate(redis_set_json_failures_total{reason="encode"}) > 0 sustained.
#
# prometheus_client is an api/ dependency, not a repo-root one: the
# stability-harness redis_ttl_fixture imports this module from the repo-root
# uv environment where prometheus_client is not installed.  Fall back to a
# no-op counter in that case so the module still imports cleanly — the
# counter is alerting scaffolding, not load-bearing logic.
try:
    from prometheus_client import REGISTRY, Counter

    try:
        redis_set_json_failures_total: Any = Counter(
            "redis_set_json_failures_total",
            "Redis set_json failures by cache key prefix and failure reason",
            ["key_prefix", "reason"],
        )
    except ValueError:
        redis_set_json_failures_total = REGISTRY._names_to_collectors[
            "redis_set_json_failures_total"
        ]
except ImportError:

    class _NoOpCounter:
        """Stand-in when prometheus_client is unavailable (root harness)."""

        def labels(self, **_kwargs: Any) -> "_NoOpCounter":
            return self

        def inc(self, _amount: float = 1) -> None:
            return None

    redis_set_json_failures_total = _NoOpCounter()


def _key_prefix(key: str) -> str:
    """Return the `prefix` of a colon-delimited cache key for metric labeling.

    Bounds Prometheus label cardinality — user_context:<uid> collapses to
    "user_context".  Keys without a colon are labeled "unknown".
    """
    head, sep, _ = key.partition(":")
    return head if sep else "unknown"


class RedisService:
    """Redis service for caching."""

    def __init__(self):
        """Initialize Redis connection."""
        self.client: redis.Redis | None = None
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
                logger.warning(
                    f"Failed to connect to Redis: {e}. Caching will be disabled."
                )
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

    def get(self, key: str) -> str | None:
        """Get value from cache."""
        if not self.client:
            return None

        try:
            return self.client.get(key)
        except Exception as e:
            logger.error(f"Redis get error for key {key}: {e}")
            return None

    def set(self, key: str, value: str, ttl: int | None = None) -> bool:
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

    def get_json(self, key: str) -> Any | None:
        """Get JSON value from cache."""
        value = self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON for key {key}")
        return None

    def set_json(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set JSON value in cache."""
        try:
            json_value = json.dumps(value)
            return self.set(key, json_value, ttl)
        except (TypeError, ValueError) as e:
            # json.dumps raises TypeError on non-serializable values and
            # ValueError on circular references.  The stdlib `json` module
            # does NOT export a `JSONEncodeError` symbol (only
            # `JSONDecodeError`), so the previous tuple raised AttributeError
            # instead of catching the failure — turning a soft cache miss
            # into an unhandled exception in every caller.
            redis_set_json_failures_total.labels(
                key_prefix=_key_prefix(key), reason="encode"
            ).inc()
            logger.error(f"Failed to encode JSON for key {key}: {e}")
            return False


# Global Redis service instance
redis_service = RedisService()


def get_redis_service() -> RedisService:
    """Get Redis service instance."""
    if not redis_service._initialized:
        redis_service.initialize()
    return redis_service
