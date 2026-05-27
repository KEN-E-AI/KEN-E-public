"""Unit tests for Redis client."""

import json
from datetime import datetime, timezone
from unittest import mock

import pytest
from src.kene_api.redis_client import (
    RedisService,
    _key_prefix,
    redis_set_json_failures_total,
)


class TestRedisService:
    """Test Redis service functionality."""

    @pytest.fixture
    def redis_service(self):
        """Create a Redis service instance for testing."""
        service = RedisService()
        service._initialized = False
        return service

    def test_initialize_with_successful_connection(self, redis_service):
        """Test successful Redis initialization."""
        with mock.patch("redis.Redis") as mock_redis:
            # Mock successful ping
            mock_client = mock.Mock()
            mock_client.ping.return_value = True
            mock_redis.return_value = mock_client

            redis_service.initialize()

            assert redis_service._initialized is True
            assert redis_service.client is not None
            mock_client.ping.assert_called_once()

    def test_initialize_with_connection_failure(self, redis_service):
        """Test Redis initialization with connection failure."""
        with mock.patch("redis.Redis") as mock_redis:
            # Mock failed ping
            mock_client = mock.Mock()
            mock_client.ping.side_effect = Exception("Connection refused")
            mock_redis.return_value = mock_client

            redis_service.initialize()

            assert redis_service._initialized is True
            assert redis_service.client is None

    def test_is_available_with_working_connection(self, redis_service):
        """Test is_available with working Redis connection."""
        mock_client = mock.Mock()
        mock_client.ping.return_value = True
        redis_service.client = mock_client

        assert redis_service.is_available() is True
        mock_client.ping.assert_called_once()

    def test_is_available_with_no_client(self, redis_service):
        """Test is_available when client is None."""
        redis_service.client = None
        assert redis_service.is_available() is False

    def test_is_available_with_failed_ping(self, redis_service):
        """Test is_available when ping fails."""
        mock_client = mock.Mock()
        mock_client.ping.side_effect = Exception("Connection lost")
        redis_service.client = mock_client

        assert redis_service.is_available() is False

    def test_get_with_existing_key(self, redis_service):
        """Test getting an existing key from Redis."""
        mock_client = mock.Mock()
        mock_client.get.return_value = "test_value"
        redis_service.client = mock_client

        result = redis_service.get("test_key")

        assert result == "test_value"
        mock_client.get.assert_called_once_with("test_key")

    def test_get_with_no_client(self, redis_service):
        """Test get when client is None."""
        redis_service.client = None
        assert redis_service.get("test_key") is None

    def test_set_with_ttl(self, redis_service):
        """Test setting a value with TTL."""
        mock_client = mock.Mock()
        mock_client.setex.return_value = True
        redis_service.client = mock_client

        result = redis_service.set("test_key", "test_value", ttl=300)

        assert result is True
        mock_client.setex.assert_called_once_with("test_key", 300, "test_value")

    def test_set_without_ttl(self, redis_service):
        """Test setting a value without TTL."""
        mock_client = mock.Mock()
        mock_client.set.return_value = True
        redis_service.client = mock_client

        result = redis_service.set("test_key", "test_value")

        assert result is True
        mock_client.set.assert_called_once_with("test_key", "test_value")

    def test_delete_existing_key(self, redis_service):
        """Test deleting an existing key."""
        mock_client = mock.Mock()
        mock_client.delete.return_value = 1
        redis_service.client = mock_client

        result = redis_service.delete("test_key")

        assert result is True
        mock_client.delete.assert_called_once_with("test_key")

    def test_get_json_with_valid_json(self, redis_service):
        """Test getting JSON data."""
        mock_client = mock.Mock()
        test_data = {"key": "value", "number": 42}
        mock_client.get.return_value = json.dumps(test_data)
        redis_service.client = mock_client

        result = redis_service.get_json("test_key")

        assert result == test_data
        mock_client.get.assert_called_once_with("test_key")

    def test_get_json_with_invalid_json(self, redis_service):
        """Test getting invalid JSON data."""
        mock_client = mock.Mock()
        mock_client.get.return_value = "invalid json"
        redis_service.client = mock_client

        result = redis_service.get_json("test_key")

        assert result is None

    def test_set_json_with_valid_data(self, redis_service):
        """Test setting JSON data."""
        mock_client = mock.Mock()
        mock_client.setex.return_value = True
        redis_service.client = mock_client

        test_data = {"key": "value", "number": 42}
        result = redis_service.set_json("test_key", test_data, ttl=300)

        assert result is True
        expected_json = json.dumps(test_data)
        mock_client.setex.assert_called_once_with("test_key", 300, expected_json)

    def test_set_json_with_unserializable_value_returns_false_and_increments_counter(
        self, redis_service
    ):
        """Regression: a non-JSON-serializable value (e.g. a Firestore Timestamp
        smuggled into account_permissions) must not raise — it must log,
        increment redis_set_json_failures_total, and return False.

        This was the load-test bug: the seed wrote a nested
        {role, granted_at: datetime} dict into account_permissions; every
        cache write failed silently and every authed request fell through
        to Firestore, blowing the chat-sidebar p90 gate.
        """
        mock_client = mock.Mock()
        redis_service.client = mock_client

        unserializable = {"granted_at": datetime.now(timezone.utc)}
        labels = redis_set_json_failures_total.labels(
            key_prefix="user_context", reason="encode"
        )
        before = labels._value.get()

        result = redis_service.set_json("user_context:abc123", unserializable)

        assert result is False
        mock_client.setex.assert_not_called()
        mock_client.set.assert_not_called()
        assert labels._value.get() == before + 1


class TestKeyPrefix:
    """Tests for the cache-key prefix label helper."""

    def test_colon_delimited_key_returns_prefix(self):
        assert _key_prefix("user_context:abc123") == "user_context"

    def test_empty_prefix_with_leading_colon(self):
        assert _key_prefix(":bare") == ""

    def test_key_without_colon_falls_back_to_unknown(self):
        assert _key_prefix("rawkey") == "unknown"
