"""Tests for caching functionality."""

import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from src.kene_api.cache import (
    CacheService,
    InMemoryCache,
    all_industry_keywords_key,
    cache_result,
    industry_keywords_key,
    monitoring_topics_key,
)


class _FakeRedis:
    """Minimal in-process Redis stand-in implementing the subset of the
    Redis protocol that CacheService relies on (get/setex/delete).

    CacheService is built against a redis-py client interface, not the
    InMemoryCache interface, so a working unit test must supply something
    that speaks that protocol.
    """

    def __init__(self):
        self._store: dict[str, str] = {}

    def get(self, key: str):
        return self._store.get(key)

    def setex(self, key: str, ttl_seconds: int, value: str):
        self._store[key] = value
        return True

    def delete(self, *keys: str):
        deleted = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                deleted += 1
        return deleted


class TestInMemoryCache:
    """Test InMemoryCache implementation."""

    def test_set_and_get(self):
        cache = InMemoryCache()

        # Test basic set/get
        assert cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

        # Test complex data
        data = {"name": "test", "items": [1, 2, 3]}
        assert cache.set("key2", data)
        assert cache.get("key2") == data

    def test_expiration(self):
        cache = InMemoryCache()

        # Set with 1 second TTL
        assert cache.set("key1", "value1", ttl_seconds=1)
        assert cache.get("key1") == "value1"

        # Mock time to simulate expiration
        with patch("src.kene_api.cache.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime.utcnow() + timedelta(seconds=2)
            assert cache.get("key1") is None

    def test_delete(self):
        cache = InMemoryCache()

        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

        assert cache.delete("key1")
        assert cache.get("key1") is None

        # Delete non-existent key
        assert not cache.delete("nonexistent")

    def test_delete_pattern(self):
        cache = InMemoryCache()

        # Set multiple keys
        cache.set("prefix:key1", "value1")
        cache.set("prefix:key2", "value2")
        cache.set("other:key3", "value3")

        # Delete by pattern
        deleted = cache.delete_pattern("prefix:*")
        assert deleted == 2

        assert cache.get("prefix:key1") is None
        assert cache.get("prefix:key2") is None
        assert cache.get("other:key3") == "value3"


class TestCacheService:
    """Test CacheService with Redis mock."""

    def test_disabled_cache(self):
        """Test cache service when Redis is not available."""
        cache = CacheService(redis_client=None)

        assert not cache.enabled
        assert cache.get("key") is None
        assert not cache.set("key", "value")
        assert not cache.delete("key")
        assert cache.delete_pattern("pattern*") == 0

    def test_redis_operations(self):
        """Test cache service with mocked Redis."""
        mock_redis = Mock()
        cache = CacheService(redis_client=mock_redis)

        assert cache.enabled

        # Test get
        mock_redis.get.return_value = json.dumps("value1")
        assert cache.get("key1") == "value1"
        mock_redis.get.assert_called_with("key1")

        # Test set
        assert cache.set("key2", {"data": "value"}, ttl_seconds=300)
        mock_redis.setex.assert_called_with("key2", 300, '{"data": "value"}')

        # Test delete
        assert cache.delete("key3")
        mock_redis.delete.assert_called_with("key3")

    def test_redis_errors(self):
        """Test error handling in cache service."""
        from redis.exceptions import RedisError

        mock_redis = Mock()
        cache = CacheService(redis_client=mock_redis)

        # Test get error
        mock_redis.get.side_effect = RedisError("Connection failed")
        assert cache.get("key") is None

        # Test set error
        mock_redis.setex.side_effect = RedisError("Connection failed")
        assert not cache.set("key", "value")

        # Test delete error
        mock_redis.delete.side_effect = RedisError("Connection failed")
        assert not cache.delete("key")


class TestCacheKeys:
    """Test cache key generators."""

    def test_industry_keywords_key(self):
        assert industry_keywords_key("Technology") == "industry_keywords:technology"
        assert industry_keywords_key("Health Care") == "industry_keywords:health_care"
        assert (
            industry_keywords_key("Finance, Insurance")
            == "industry_keywords:finance_insurance"
        )

    def test_all_industry_keywords_key(self):
        assert all_industry_keywords_key() == "industry_keywords:all"

    def test_monitoring_topics_key(self):
        assert monitoring_topics_key("acc_123") == "monitoring_topics:acc_123"


class TestCacheDecorator:
    """Test cache_result decorator."""

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """Test decorator returns cached value on hit."""
        cache_service = CacheService(_FakeRedis())

        call_count = 0

        @cache_result(
            key_func=lambda x: f"test:{x}", ttl_seconds=60, cache_service=cache_service
        )
        async def test_func(x):
            nonlocal call_count
            call_count += 1
            return f"result_{x}"

        # First call - should execute function
        result1 = await test_func("abc")
        assert result1 == "result_abc"
        assert call_count == 1

        # Second call - should return cached value
        result2 = await test_func("abc")
        assert result2 == "result_abc"
        assert call_count == 1  # Function not called again

        # Different argument - should execute function
        result3 = await test_func("def")
        assert result3 == "result_def"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_cache_disabled(self):
        """Test decorator bypasses cache when disabled."""
        call_count = 0

        @cache_result(
            key_func=lambda x: f"test:{x}",
            cache_service=CacheService(None),  # Disabled cache
        )
        async def test_func(x):
            nonlocal call_count
            call_count += 1
            return f"result_{x}"

        # Both calls should execute function
        await test_func("abc")
        await test_func("abc")
        assert call_count == 2
