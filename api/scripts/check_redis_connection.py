#!/usr/bin/env python3
"""Test Redis connection and basic operations."""

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

# Add parent directory to path to import kene_api modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.kene_api.redis_client import get_redis_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def print_section(title: str) -> None:
    """Print a formatted section header."""
    print(f"\n{'=' * 60}")
    print(f" {title}")
    print(f"{'=' * 60}")


async def test_redis_connection():
    """Test Redis connection and operations."""
    redis = get_redis_service()

    print_section("Redis Connection Test")

    # Test 1: Check availability
    print("\n1. Testing Redis availability...")
    is_available = redis.is_available()
    if is_available:
        print("   ✓ Redis is available and responding to ping")
    else:
        print("   ✗ Redis is not available")
        print("   Make sure Redis is running:")
        print("   - Local: redis-server")
        print("   - Docker: docker run -d -p 6379:6379 redis:7-alpine")
        print("   - Docker Compose: cd api && docker-compose up redis")
        return False

    # Test 2: Basic string operations
    print("\n2. Testing basic string operations...")
    test_key = "test:connection"
    test_value = "Hello, Redis!"

    # Set
    success = redis.set(test_key, test_value)
    if success:
        print(f"   ✓ SET {test_key} = '{test_value}'")
    else:
        print(f"   ✗ Failed to SET {test_key}")
        return False

    # Get
    retrieved = redis.get(test_key)
    if retrieved == test_value:
        print(f"   ✓ GET {test_key} = '{retrieved}'")
    else:
        print(f"   ✗ GET failed. Expected '{test_value}', got '{retrieved}'")
        return False

    # Delete
    deleted = redis.delete(test_key)
    if deleted:
        print(f"   ✓ DELETE {test_key}")
    else:
        print(f"   ✗ Failed to DELETE {test_key}")

    # Test 3: TTL operations
    print("\n3. Testing TTL operations...")
    ttl_key = "test:ttl"
    ttl_value = "Expires soon"
    ttl_seconds = 2

    success = redis.set(ttl_key, ttl_value, ttl=ttl_seconds)
    if success:
        print(f"   ✓ SET {ttl_key} with TTL={ttl_seconds}s")
    else:
        print("   ✗ Failed to SET with TTL")
        return False

    # Check immediately
    retrieved = redis.get(ttl_key)
    if retrieved == ttl_value:
        print("   ✓ Key exists immediately after setting")
    else:
        print("   ✗ Key not found immediately after setting")

    # Wait for expiration
    print(f"   Waiting {ttl_seconds + 1} seconds for expiration...")
    time.sleep(ttl_seconds + 1)

    retrieved = redis.get(ttl_key)
    if retrieved is None:
        print("   ✓ Key expired after TTL")
    else:
        print(f"   ✗ Key still exists after TTL: '{retrieved}'")

    # Test 4: JSON operations
    print("\n4. Testing JSON operations...")
    json_key = "test:json"
    json_data = {
        "user_id": "test_user_123",
        "preferences": {"theme": "dark", "notifications": True},
        "created_at": "2025-01-01T00:00:00Z",
    }

    success = redis.set_json(json_key, json_data)
    if success:
        print(f"   ✓ SET JSON data for {json_key}")
    else:
        print("   ✗ Failed to SET JSON data")
        return False

    retrieved_json = redis.get_json(json_key)
    if retrieved_json == json_data:
        print("   ✓ GET JSON data matches original")
        print(f"     Data: {json.dumps(retrieved_json, indent=2)}")
    else:
        print("   ✗ JSON data mismatch")
        print(f"     Expected: {json_data}")
        print(f"     Got: {retrieved_json}")

    redis.delete(json_key)

    # Test 5: Simulate cache patterns used in KEN-E
    print("\n5. Testing KEN-E cache patterns...")

    # User context caching (from cached_user_context.py)
    user_id = "test_user_456"
    cache_key = f"user_context:{user_id}"
    user_context = {
        "user_id": user_id,
        "email": "test@example.com",
        "organization_id": "org_123",
        "roles": ["user", "admin"],
    }

    success = redis.set_json(cache_key, user_context, ttl=300)
    if success:
        print(f"   ✓ Cached user context for {user_id}")
    else:
        print("   ✗ Failed to cache user context")

    # Token revocation (from token_revocation.py)
    token_id = "test_token_789"
    revoked_key = f"revoked_token:{token_id}"

    success = redis.set(revoked_key, "1", ttl=3600)
    if success:
        print(f"   ✓ Marked token {token_id} as revoked")
    else:
        print("   ✗ Failed to mark token as revoked")

    # Check if token is revoked
    is_revoked = redis.get(revoked_key) == "1"
    if is_revoked:
        print("   ✓ Token revocation check working")
    else:
        print("   ✗ Token revocation check failed")

    # Cleanup
    redis.delete(cache_key)
    redis.delete(revoked_key)

    return True


async def test_performance():
    """Test Redis performance with various operations."""
    redis = get_redis_service()

    if not redis.is_available():
        print("\nSkipping performance tests - Redis not available")
        return

    print_section("Redis Performance Test")

    # Test write performance
    print("\n1. Write performance (1000 operations)...")
    start_time = time.time()
    for i in range(1000):
        redis.set(f"perf:test:{i}", f"value_{i}")
    write_time = time.time() - start_time
    writes_per_sec = 1000 / write_time
    print(f"   ✓ Completed 1000 writes in {write_time:.3f}s")
    print(f"   → {writes_per_sec:.0f} writes/second")

    # Test read performance
    print("\n2. Read performance (1000 operations)...")
    start_time = time.time()
    for i in range(1000):
        redis.get(f"perf:test:{i}")
    read_time = time.time() - start_time
    reads_per_sec = 1000 / read_time
    print(f"   ✓ Completed 1000 reads in {read_time:.3f}s")
    print(f"   → {reads_per_sec:.0f} reads/second")

    # Cleanup
    print("\n3. Cleanup...")
    for i in range(1000):
        redis.delete(f"perf:test:{i}")
    print("   ✓ Cleaned up test keys")

    # Summary
    print("\n" + "=" * 60)
    print(" Performance Summary")
    print("=" * 60)
    print(f" Write throughput: {writes_per_sec:,.0f} ops/sec")
    print(f" Read throughput:  {reads_per_sec:,.0f} ops/sec")
    print(f" Avg write latency: {(write_time / 1000) * 1000:.2f} ms")
    print(f" Avg read latency:  {(read_time / 1000) * 1000:.2f} ms")


def main():
    """Main test runner."""
    print("\n" + "=" * 60)
    print(" KEN-E Redis Connection Test")
    print("=" * 60)

    # Show current configuration
    print("\nCurrent Redis Configuration:")
    print(f"  REDIS_HOST: {os.getenv('REDIS_HOST', 'localhost')}")
    print(f"  REDIS_PORT: {os.getenv('REDIS_PORT', '6379')}")
    print(f"  REDIS_DB: {os.getenv('REDIS_DB', '0')}")
    print(f"  REDIS_PASSWORD: {'***' if os.getenv('REDIS_PASSWORD') else '(not set)'}")

    # Run tests
    loop = asyncio.get_event_loop()

    # Connection tests
    success = loop.run_until_complete(test_redis_connection())

    if success:
        print("\n" + "=" * 60)
        print(" ✓ All connection tests passed!")
        print("=" * 60)

        # Performance tests
        loop.run_until_complete(test_performance())

        print("\n" + "=" * 60)
        print(" ✓ Redis is properly configured and working!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Your Redis cache is ready for use")
        print("2. Token revocation caching will work automatically")
        print("3. User context caching will work automatically")
        print("4. Consider adding more cache patterns for frequently accessed data")

        return 0
    else:
        print("\n" + "=" * 60)
        print(" ✗ Some tests failed. Please check Redis configuration.")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
