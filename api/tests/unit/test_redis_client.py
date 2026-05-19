"""Unit tests for Redis client."""

import json
from unittest import mock

import pytest
from src.kene_api.redis_client import RedisService


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
