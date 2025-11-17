"""Unit tests for cached user context service."""

from unittest import mock

import pytest

from src.kene_api.auth.cached_user_context import CachedUserContextService
from src.kene_api.auth.models import UserContext


class TestCachedUserContextService:
    """Test cached user context service functionality."""

    @pytest.fixture
    def user_context(self):
        """Create a test user context."""
        return UserContext(
            user_id="test-user-123",
            email="test@example.com",            permissions={"acc_1": "admin", "acc_2": "viewer"},
            organization_permissions={"org_1": "admin"},
        )

    @pytest.fixture
    def cached_service(self):
        """Create a cached user context service with mocked Redis."""
        with mock.patch(
            "src.kene_api.auth.cached_user_context.get_redis_service"
        ) as mock_get_redis:
            mock_redis = mock.Mock()
            mock_get_redis.return_value = mock_redis
            service = CachedUserContextService()
            service.redis = mock_redis
            return service

    def test_get_cache_key(self, cached_service):
        """Test cache key generation."""
        key = cached_service._get_cache_key("user123")
        assert key == "user_context:user123"

    def test_get_user_context_from_cache(self, cached_service, user_context):
        """Test getting user context from cache."""
        # Mock Redis available and returning cached data
        cached_service.redis.is_available.return_value = True
        cached_data = {
            "user_id": user_context.user_id,
            "email": user_context.email,
            "accessible_accounts": user_context.accessible_accounts,
            "permissions": user_context.permissions,
            "organization_permissions": user_context.organization_permissions,
        }
        cached_service.redis.get_json.return_value = cached_data

        result = cached_service.get_user_context("test-user-123")

        assert result is not None
        assert result.user_id == user_context.user_id
        assert result.email == user_context.email
        assert result.accessible_accounts == user_context.accessible_accounts
        assert result.permissions == user_context.permissions
        assert result.organization_permissions == user_context.organization_permissions

        cached_service.redis.get_json.assert_called_once_with(
            "user_context:test-user-123"
        )

    def test_get_user_context_redis_unavailable(self, cached_service):
        """Test getting user context when Redis is unavailable."""
        cached_service.redis.is_available.return_value = False

        result = cached_service.get_user_context("test-user-123")

        assert result is None
        cached_service.redis.get_json.assert_not_called()

    def test_get_user_context_cache_miss(self, cached_service):
        """Test getting user context with cache miss."""
        cached_service.redis.is_available.return_value = True
        cached_service.redis.get_json.return_value = None

        result = cached_service.get_user_context("test-user-123")

        assert result is None

    def test_get_user_context_deserialization_error(self, cached_service):
        """Test handling deserialization error."""
        cached_service.redis.is_available.return_value = True
        # Return incomplete data that will cause deserialization error
        cached_service.redis.get_json.return_value = {"invalid": "data"}

        result = cached_service.get_user_context("test-user-123")

        assert result is None

    def test_set_user_context_success(self, cached_service, user_context):
        """Test successfully caching user context."""
        cached_service.redis.is_available.return_value = True
        cached_service.redis.set_json.return_value = True

        result = cached_service.set_user_context(user_context)

        assert result is True

        expected_data = {
            "user_id": user_context.user_id,
            "email": user_context.email,
            "accessible_accounts": user_context.accessible_accounts,
            "permissions": user_context.permissions,
            "organization_permissions": user_context.organization_permissions,
            "account_permissions": user_context.account_permissions,
        }
        cached_service.redis.set_json.assert_called_once_with(
            "user_context:test-user-123",
            expected_data,
            300,  # USER_CONTEXT_CACHE_TTL
        )

    def test_set_user_context_redis_unavailable(self, cached_service, user_context):
        """Test caching when Redis is unavailable."""
        cached_service.redis.is_available.return_value = False

        result = cached_service.set_user_context(user_context)

        assert result is False
        cached_service.redis.set_json.assert_not_called()

    def test_invalidate_user_context_success(self, cached_service):
        """Test successfully invalidating cached user context."""
        cached_service.redis.is_available.return_value = True
        cached_service.redis.delete.return_value = True

        result = cached_service.invalidate_user_context("test-user-123")

        assert result is True
        cached_service.redis.delete.assert_called_once_with(
            "user_context:test-user-123"
        )

    def test_invalidate_user_context_redis_unavailable(self, cached_service):
        """Test invalidating when Redis is unavailable."""
        cached_service.redis.is_available.return_value = False

        result = cached_service.invalidate_user_context("test-user-123")

        assert result is False
        cached_service.redis.delete.assert_not_called()
