"""Security tests: super-admin status requires a verified email.

Firebase email/password signup is enabled, so anyone can register an unused
``@ken-e.ai`` address and receive a valid ID token without ever controlling the
mailbox. These tests lock in two defences:

* ``UserContext.is_super_admin`` (and everything that branches on it) requires
  ``email_verified`` to be true.
* The auth flow applies rate limiting to every authenticated request — super
  admins are no longer exempt.
"""

from unittest import mock

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from src.kene_api.auth.cached_user_context import CachedUserContextService
from src.kene_api.auth.models import UserContext
from src.kene_api.auth.user_context import (
    _build_user_context_from_data,
    _get_user_context_with_limiter,
)


class TestBuildUserContextThreadsEmailVerified:
    """``_build_user_context_from_data`` must carry the token's verified flag."""

    def test_unverified_ken_e_email_is_not_super_admin(self):
        context = _build_user_context_from_data(
            "user123",
            "attacker@ken-e.ai",
            False,  # email_verified
            {"permissions": {"organizations": {}, "account_permissions": {}}},
        )

        assert context.email_verified is False
        assert context.is_super_admin is False

    def test_verified_ken_e_email_is_super_admin(self):
        context = _build_user_context_from_data(
            "user123",
            "staff@ken-e.ai",
            True,  # email_verified
            {"permissions": {"organizations": {}, "account_permissions": {}}},
        )

        assert context.email_verified is True
        assert context.is_super_admin is True


def _make_request() -> mock.Mock:
    request = mock.Mock()
    request.client = mock.Mock(host="127.0.0.1")
    request.headers = mock.Mock()
    request.headers.get = mock.Mock(return_value="TestAgent/1.0")
    request.url = "http://test.com/api/endpoint"
    return request


def _make_firestore_service(email: str) -> mock.Mock:
    user_doc = mock.Mock()
    user_doc.exists = True
    user_doc.to_dict.return_value = {
        "uid": "admin123",
        "email": email,
        "permissions": {"organizations": {}, "account_permissions": {}},
    }
    client = mock.Mock()
    client.collection.return_value.document.return_value.get.return_value = user_doc
    service = mock.Mock()
    service.get_client.return_value = client
    return service


@pytest.mark.asyncio
class TestSuperAdminIsRateLimited:
    """Super admins are no longer exempt from rate limiting."""

    async def test_rate_limiting_applied_for_ken_e_email(self):
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="valid-token"
        )
        firestore_service = _make_firestore_service("admin@ken-e.ai")

        with (
            mock.patch(
                "src.kene_api.auth.user_context._verify_and_decode_token"
            ) as mock_verify,
            mock.patch(
                "src.kene_api.auth.user_context._check_token_revocation"
            ) as mock_check,
            mock.patch(
                "src.kene_api.auth.user_context._apply_rate_limiting"
            ) as mock_rate_limit,
            mock.patch(
                "src.kene_api.auth.user_context.get_audit_logger"
            ) as mock_get_audit,
            mock.patch(
                "src.kene_api.auth.cached_user_context.get_cached_user_context_service"
            ) as mock_get_cached,
        ):
            mock_verify.return_value = (
                {"uid": "admin123", "email": "admin@ken-e.ai", "email_verified": True},
                "admin123",
                "admin@ken-e.ai",
            )
            mock_check.return_value = None
            mock_rate_limit.return_value = None
            mock_get_audit.return_value = mock.AsyncMock()

            cache_service = mock.Mock()
            cache_service.get_user_context.return_value = None
            cache_service.set_user_context.return_value = True
            mock_get_cached.return_value = cache_service

            result = await _get_user_context_with_limiter(
                _make_request(), credentials, firestore_service, None
            )

            # The bypass is gone: rate limiting runs for the super admin too.
            mock_rate_limit.assert_called_once()
            assert result.is_super_admin is True

    async def test_unverified_ken_e_token_yields_no_super_admin(self):
        """An unverified @ken-e.ai token authenticates but is not a super admin."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="valid-token"
        )
        firestore_service = _make_firestore_service("attacker@ken-e.ai")

        with (
            mock.patch(
                "src.kene_api.auth.user_context._verify_and_decode_token"
            ) as mock_verify,
            mock.patch(
                "src.kene_api.auth.user_context._check_token_revocation"
            ) as mock_check,
            mock.patch(
                "src.kene_api.auth.user_context._apply_rate_limiting"
            ) as mock_rate_limit,
            mock.patch(
                "src.kene_api.auth.user_context.get_audit_logger"
            ) as mock_get_audit,
            mock.patch(
                "src.kene_api.auth.cached_user_context.get_cached_user_context_service"
            ) as mock_get_cached,
        ):
            mock_verify.return_value = (
                {
                    "uid": "attacker123",
                    "email": "attacker@ken-e.ai",
                    "email_verified": False,
                },
                "attacker123",
                "attacker@ken-e.ai",
            )
            mock_check.return_value = None
            mock_rate_limit.return_value = None
            mock_get_audit.return_value = mock.AsyncMock()

            cache_service = mock.Mock()
            cache_service.get_user_context.return_value = None
            cache_service.set_user_context.return_value = True
            mock_get_cached.return_value = cache_service

            result = await _get_user_context_with_limiter(
                _make_request(), credentials, firestore_service, None
            )

            assert result.email_verified is False
            assert result.is_super_admin is False


class TestCachedContextPreservesEmailVerified:
    """The Redis cache must not silently drop the verified flag."""

    @pytest.fixture
    def cached_service(self):
        service = CachedUserContextService()
        service._redis = mock.Mock()
        return service

    def test_roundtrip_preserves_email_verified(self, cached_service):
        cached_service.redis.is_available.return_value = True
        captured = {}
        cached_service.redis.set_json.side_effect = (
            lambda key, data, ttl: captured.update(data) or True
        )

        cached_service.set_user_context(
            UserContext(
                user_id="staff1",
                email="staff@ken-e.ai",
                organization_permissions={},
                account_permissions={},
                email_verified=True,
            )
        )
        cached_service.redis.get_json.return_value = captured

        restored = cached_service.get_user_context("staff1")

        assert restored is not None
        assert restored.email_verified is True
        assert restored.is_super_admin is True

    def test_cache_entry_missing_email_verified_is_invalidated(self, cached_service):
        """A pre-deploy cache entry without email_verified must not be trusted."""
        cached_service.redis.is_available.return_value = True
        cached_service.redis.get_json.return_value = {
            "user_id": "staff1",
            "email": "staff@ken-e.ai",
            "organization_permissions": {},
            "account_permissions": {},
            # email_verified intentionally absent
        }

        result = cached_service.get_user_context("staff1")

        assert result is None
        cached_service.redis.delete.assert_called_once_with("user_context:staff1")
