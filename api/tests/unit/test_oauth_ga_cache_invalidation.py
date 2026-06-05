"""Unit tests for GA credential cache invalidation on OAuth mutations.

The chat path caches ``ga_credentials`` (TTL up to GA_CREDENTIALS_TTL_SECONDS).
Connecting, disconnecting, or changing selected properties must drop that cache
so the next chat turn reloads fresh credentials instead of serving a stale token.
"""

from unittest.mock import MagicMock, patch

from src.kene_api.cache import ga_credentials_key
from src.kene_api.routers.oauth_integrations import _invalidate_ga_credentials_cache

ACCOUNT_ID = "acc_cache_invalidation_test"


def test_invalidate_deletes_cache_key_when_redis_available():
    mock_redis = MagicMock()
    mock_redis.is_available.return_value = True

    with patch(
        "src.kene_api.routers.oauth_integrations.get_redis_service",
        return_value=mock_redis,
    ):
        _invalidate_ga_credentials_cache(ACCOUNT_ID)

    mock_redis.delete.assert_called_once_with(ga_credentials_key(ACCOUNT_ID))


def test_invalidate_is_noop_when_redis_unavailable():
    mock_redis = MagicMock()
    mock_redis.is_available.return_value = False

    with patch(
        "src.kene_api.routers.oauth_integrations.get_redis_service",
        return_value=mock_redis,
    ):
        _invalidate_ga_credentials_cache(ACCOUNT_ID)

    mock_redis.delete.assert_not_called()


def test_invalidate_swallows_redis_errors():
    mock_redis = MagicMock()
    mock_redis.is_available.side_effect = RuntimeError("redis down")

    with patch(
        "src.kene_api.routers.oauth_integrations.get_redis_service",
        return_value=mock_redis,
    ):
        # Must not raise — invalidation is best-effort.
        _invalidate_ga_credentials_cache(ACCOUNT_ID)
