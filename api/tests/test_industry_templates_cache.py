"""Tests for industry templates cache behavior and concurrency."""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock

import pytest
from src.kene_api.routers.industry_templates import ThreadSafeTemplateCache


class TestThreadSafeTemplateCache:
    """Tests for ThreadSafeTemplateCache class."""

    def test_cache_basic_operations(self):
        """Test basic cache operations: get, set, invalidate."""
        cache = ThreadSafeTemplateCache(max_size=3, ttl_seconds=60)

        # Test set and get
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

        # Test get non-existent key
        assert cache.get("non_existent") is None

        # Test invalidate specific key
        cache.invalidate("key1")
        assert cache.get("key1") is None

        # Test invalidate all
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.invalidate()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_cache_ttl_expiration(self):
        """Test that cache entries expire after TTL."""
        cache = ThreadSafeTemplateCache(max_size=3, ttl_seconds=0.1)  # 100ms TTL

        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

        # Wait for expiration
        time.sleep(0.2)
        assert cache.get("key1") is None

    def test_cache_max_size_eviction(self):
        """Test that cache evicts oldest entries when max size is reached."""
        cache = ThreadSafeTemplateCache(max_size=3, ttl_seconds=60)

        # Fill cache to capacity
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # Add one more - should evict key1 (oldest)
        cache.set("key4", "value4")

        assert cache.get("key1") is None  # Evicted
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_cache_lru_behavior(self):
        """Test that cache implements LRU eviction properly."""
        cache = ThreadSafeTemplateCache(max_size=3, ttl_seconds=60)

        # Fill cache
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # Access key1 to make it recently used
        assert cache.get("key1") == "value1"

        # Add key4 - should evict key2 (least recently used)
        cache.set("key4", "value4")

        assert cache.get("key1") == "value1"  # Still there (recently used)
        assert cache.get("key2") is None  # Evicted (least recently used)
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_cache_invalidate_pattern(self):
        """Test pattern-based cache invalidation."""
        cache = ThreadSafeTemplateCache(max_size=10, ttl_seconds=60)

        # Set various keys
        cache.set("industry:retail", "retail_data")
        cache.set("industry:manufacturing", "manufacturing_data")
        cache.set("id:123", "id_data")
        cache.set("all_templates", "all_data")

        # Invalidate by pattern
        cache.invalidate_pattern("industry:")

        # Industry keys should be gone
        assert cache.get("industry:retail") is None
        assert cache.get("industry:manufacturing") is None

        # Other keys should remain
        assert cache.get("id:123") == "id_data"
        assert cache.get("all_templates") == "all_data"

    def test_cache_statistics(self):
        """Test cache statistics tracking."""
        cache = ThreadSafeTemplateCache(max_size=3, ttl_seconds=60)

        # Initial stats
        stats = cache.get_stats()
        assert stats["size"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0

        # Generate some hits and misses
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"  # Hit
        assert cache.get("key2") is None  # Miss
        assert cache.get("key1") == "value1"  # Hit

        stats = cache.get_stats()
        assert stats["size"] == 1
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_ratio"] == 2 / 3

    def test_cache_thread_safety_concurrent_writes(self):
        """Test that cache is thread-safe for concurrent writes."""
        cache = ThreadSafeTemplateCache(max_size=100, ttl_seconds=60)
        errors = []

        def write_to_cache(thread_id):
            try:
                for i in range(10):
                    cache.set(f"thread_{thread_id}_key_{i}", f"value_{i}")
                    time.sleep(0.001)  # Small delay to increase contention
            except Exception as e:
                errors.append(e)

        # Run multiple threads concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(write_to_cache, i) for i in range(10)]
            for future in as_completed(futures):
                future.result()

        # No errors should occur
        assert len(errors) == 0

        # All values should be present
        for thread_id in range(10):
            for i in range(10):
                key = f"thread_{thread_id}_key_{i}"
                assert cache.get(key) == f"value_{i}"

    def test_cache_thread_safety_concurrent_reads(self):
        """Test that cache is thread-safe for concurrent reads."""
        cache = ThreadSafeTemplateCache(max_size=100, ttl_seconds=60)

        # Populate cache
        for i in range(20):
            cache.set(f"key_{i}", f"value_{i}")

        results = []
        errors = []

        def read_from_cache(thread_id):
            try:
                thread_results = []
                for i in range(20):
                    value = cache.get(f"key_{i}")
                    thread_results.append(value)
                results.append(thread_results)
            except Exception as e:
                errors.append(e)

        # Run multiple threads concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(read_from_cache, i) for i in range(10)]
            for future in as_completed(futures):
                future.result()

        # No errors should occur
        assert len(errors) == 0

        # All threads should get the same values
        expected = [f"value_{i}" for i in range(20)]
        for thread_results in results:
            assert thread_results == expected

    def test_cache_thread_safety_mixed_operations(self):
        """Test thread safety with mixed read/write/invalidate operations."""
        cache = ThreadSafeTemplateCache(max_size=100, ttl_seconds=60)
        errors = []

        def mixed_operations(thread_id):
            try:
                for i in range(20):
                    operation = i % 4
                    if operation == 0:
                        # Write
                        cache.set(f"key_{thread_id}_{i}", f"value_{i}")
                    elif operation == 1:
                        # Read
                        cache.get(f"key_{thread_id}_{i - 1}")
                    elif operation == 2:
                        # Invalidate specific
                        cache.invalidate(f"key_{thread_id}_{i - 2}")
                    else:
                        # Pattern invalidate
                        cache.invalidate_pattern(f"key_{thread_id}_")
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        # Run multiple threads concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(mixed_operations, i) for i in range(10)]
            for future in as_completed(futures):
                future.result()

        # No errors should occur
        assert len(errors) == 0

    def test_cache_no_caching_when_max_size_zero(self):
        """Test that cache doesn't store anything when max_size is 0."""
        cache = ThreadSafeTemplateCache(max_size=0, ttl_seconds=60)

        cache.set("key1", "value1")
        assert cache.get("key1") is None

        stats = cache.get_stats()
        assert stats["size"] == 0
        assert stats["max_size"] == 0


class TestCacheIntegration:
    """Integration tests for cache with the API."""

    @pytest.mark.asyncio
    async def test_cache_integration_with_fetch_functions(self):
        """Test cache integration with fetch functions."""
        from src.kene_api.routers.industry_templates import (
            _fetch_all_templates,
            _template_cache,
        )

        # Clear cache
        _template_cache.invalidate()

        # Mock FirestoreService
        mock_firestore = Mock()
        mock_firestore.health_check.return_value = True
        mock_firestore.list_documents.return_value = [
            {
                "id": "test_id",
                "industry": "Test Industry",
                "name": "Test Template",
                "description": "Test",
                "definition": "Test definition",
                "is_active": True,
            }
        ]

        # First call should hit Firestore
        result1 = await _fetch_all_templates(mock_firestore)
        assert len(result1) == 1
        assert mock_firestore.list_documents.call_count == 1

        # Second call should use cache (if enabled)
        result2 = await _fetch_all_templates(mock_firestore)
        assert result1 == result2

        # Check if cache was used based on environment
        from src.kene_api.routers.industry_templates import IS_DEVELOPMENT

        if not IS_DEVELOPMENT:
            # In production, should still be 1 call (cached)
            assert mock_firestore.list_documents.call_count == 1
        else:
            # In development, cache is disabled so 2 calls
            assert mock_firestore.list_documents.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_update(self):
        """Test that cache is properly invalidated on template update."""
        from src.kene_api.routers.industry_templates import _template_cache

        # The module-level cache is configured for the current environment;
        # in development (the test default) caching is disabled (max_size=0,
        # ttl_seconds=0). Temporarily enable caching so this test exercises the
        # real invalidate() behavior on the actual module-level cache object.
        original_max_size = _template_cache._max_size
        original_ttl = _template_cache._ttl_seconds
        _template_cache._max_size = 128
        _template_cache._ttl_seconds = 3600
        try:
            _template_cache.invalidate()  # Start from a clean slate

            # Setup cache with test data
            _template_cache.set("all_templates", ["template1", "template2"])
            _template_cache.set("id:test_id", "template1")
            _template_cache.set("industry:Test Industry", "template1")

            # Verify cache has data
            assert _template_cache.get("all_templates") is not None
            assert _template_cache.get("id:test_id") is not None
            assert _template_cache.get("industry:Test Industry") is not None

            # Simulate update - should invalidate related entries
            _template_cache.invalidate("all_templates")
            _template_cache.invalidate("id:test_id")
            _template_cache.invalidate("industry:Test Industry")

            # Verify cache was cleared
            assert _template_cache.get("all_templates") is None
            assert _template_cache.get("id:test_id") is None
            assert _template_cache.get("industry:Test Industry") is None
        finally:
            _template_cache.invalidate()
            _template_cache._max_size = original_max_size
            _template_cache._ttl_seconds = original_ttl


class TestCacheParameterized:
    """Parameterized tests for cache behavior."""

    @pytest.mark.parametrize(
        "max_size,ttl_seconds,expected_caching",
        [
            (0, 60, False),  # No caching when max_size is 0
            (10, 0, False),  # No caching when TTL is 0
            (10, 60, True),  # Normal caching
        ],
    )
    def test_cache_configuration_scenarios(
        self, max_size, ttl_seconds, expected_caching
    ):
        """Test different cache configuration scenarios."""
        cache = ThreadSafeTemplateCache(max_size=max_size, ttl_seconds=ttl_seconds)

        cache.set("test_key", "test_value")

        if expected_caching:
            assert cache.get("test_key") == "test_value"
        else:
            assert cache.get("test_key") is None

    @pytest.mark.parametrize(
        "num_threads,num_operations",
        [
            (5, 10),
            (10, 20),
            (20, 50),
        ],
    )
    def test_cache_concurrent_stress(self, num_threads, num_operations):
        """Stress test cache with varying thread and operation counts."""
        cache = ThreadSafeTemplateCache(max_size=1000, ttl_seconds=60)
        errors = []

        def stress_test(thread_id):
            try:
                for i in range(num_operations):
                    key = f"t{thread_id}_k{i}"
                    value = f"v{i}"

                    # Random operations
                    op = i % 3
                    if op == 0:
                        cache.set(key, value)
                    elif op == 1:
                        cache.get(key)
                    else:
                        cache.invalidate(key)
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(stress_test, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors occurred: {errors}"

    @pytest.mark.parametrize(
        "pattern,keys_to_set,expected_removed",
        [
            (
                "industry:",
                ["industry:a", "industry:b", "id:1"],
                ["industry:a", "industry:b"],
            ),
            ("test", ["test1", "test2", "other"], ["test1", "test2"]),
            (
                "",
                ["key1", "key2", "key3"],
                ["key1", "key2", "key3"],
            ),  # Empty pattern matches all
        ],
    )
    def test_cache_pattern_invalidation_scenarios(
        self, pattern, keys_to_set, expected_removed
    ):
        """Test different pattern invalidation scenarios."""
        cache = ThreadSafeTemplateCache(max_size=100, ttl_seconds=60)

        # Set all keys
        for key in keys_to_set:
            cache.set(key, f"value_{key}")

        # Verify all keys exist
        for key in keys_to_set:
            assert cache.get(key) == f"value_{key}"

        # Invalidate by pattern
        cache.invalidate_pattern(pattern)

        # Check which keys were removed
        for key in keys_to_set:
            if key in expected_removed:
                assert cache.get(key) is None
            else:
                assert cache.get(key) == f"value_{key}"
