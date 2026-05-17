"""Security tests: super-admin status derives only from an explicit role.

Super-admin is no longer inferred from an ``@ken-e.ai`` email. It is granted
explicitly by writing ``"super_admin"`` into the ``roles`` array on the user's
``users/{uid}`` Firestore doc, keyed on the immutable Firebase uid. These tests
lock in:

* ``UserContext.is_super_admin`` is true iff ``"super_admin"`` is in ``roles``.
* The auth flow threads ``roles`` from the user doc into the context.
* The Redis cache round-trips ``roles`` and invalidates pre-deploy entries.
* Rate limiting applies to every authenticated request — super admins included.
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


class TestIsSuperAdminDerivesFromRoles:
    """``is_super_admin`` reads the roles array and nothing else."""

    def test_super_admin_role_grants_status(self):
        context = UserContext(
            user_id="u1",
            email="staff@example.com",
            organization_permissions={},
            account_permissions={},
            roles=["super_admin"],
        )

        assert context.is_super_admin is True

    def test_empty_roles_is_not_super_admin(self):
        context = UserContext(
            user_id="u1",
            email="staff@example.com",
            organization_permissions={},
            account_permissions={},
        )

        assert context.is_super_admin is False

    def test_ken_e_email_without_role_is_not_super_admin(self):
        """An @ken-e.ai email no longer confers super-admin on its own."""
        context = UserContext(
            user_id="u1",
            email="staff@ken-e.ai",
            organization_permissions={},
            account_permissions={},
        )

        assert context.is_super_admin is False

    def test_other_roles_do_not_confer_super_admin(self):
        context = UserContext(
            user_id="u1",
            email="staff@example.com",
            organization_permissions={},
            account_permissions={},
            roles=["billing_admin", "viewer"],
        )

        assert context.is_super_admin is False

    def test_no_role_denies_privileged_methods(self):
        """Methods that branch on super-admin must deny a user with no role."""
        user = UserContext(
            user_id="u1",
            email="staff@ken-e.ai",
            organization_permissions={},
            account_permissions={},
        )

        assert user.has_account_permission("acc123", "org456", "edit") is False
        assert user.has_organization_permission("org123", "admin") is False
        assert user.get_effective_organization_role("any_org") is None
        assert user.get_effective_account_role("any_acc", "any_org") is None


class TestBuildUserContextThreadsRoles:
    """``_build_user_context_from_data`` must carry the doc's roles array."""

    def test_roles_threaded_from_user_data(self):
        context = _build_user_context_from_data(
            "user123",
            "staff@example.com",
            {
                "permissions": {"organizations": {}, "account_permissions": {}},
                "roles": ["super_admin"],
            },
        )

        assert context.roles == ["super_admin"]
        assert context.is_super_admin is True

    def test_missing_roles_defaults_to_empty(self):
        context = _build_user_context_from_data(
            "user123",
            "staff@example.com",
            {"permissions": {"organizations": {}, "account_permissions": {}}},
        )

        assert context.roles == []
        assert context.is_super_admin is False


def _make_request() -> mock.Mock:
    request = mock.Mock()
    request.client = mock.Mock(host="127.0.0.1")
    request.headers = mock.Mock()
    request.headers.get = mock.Mock(return_value="TestAgent/1.0")
    request.url = "http://test.com/api/endpoint"
    return request


def _make_firestore_service(email: str, roles: list[str] | None = None) -> mock.Mock:
    user_doc = mock.Mock()
    user_doc.exists = True
    user_doc.to_dict.return_value = {
        "uid": "admin123",
        "email": email,
        "permissions": {"organizations": {}, "account_permissions": {}},
        "roles": roles or [],
    }
    client = mock.Mock()
    client.collection.return_value.document.return_value.get.return_value = user_doc
    service = mock.Mock()
    service.get_client.return_value = client
    return service


@pytest.mark.asyncio
class TestSuperAdminIsRateLimited:
    """Super admins are not exempt from rate limiting."""

    async def test_rate_limiting_applied_for_super_admin(self):
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="valid-token"
        )
        firestore_service = _make_firestore_service(
            "admin@example.com", roles=["super_admin"]
        )

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
                {"uid": "admin123", "email": "admin@example.com"},
                "admin123",
                "admin@example.com",
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

    async def test_user_without_role_is_not_super_admin(self):
        """A normal user authenticates but is not a super admin."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="valid-token"
        )
        firestore_service = _make_firestore_service("user@example.com")

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
                {"uid": "user123", "email": "user@example.com"},
                "user123",
                "user@example.com",
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

            assert result.roles == []
            assert result.is_super_admin is False


class TestCachedContextPreservesRoles:
    """The Redis cache must round-trip roles, not silently drop them."""

    @pytest.fixture
    def cached_service(self):
        service = CachedUserContextService()
        service._redis = mock.Mock()
        return service

    def test_roundtrip_preserves_roles(self, cached_service):
        cached_service.redis.is_available.return_value = True
        captured = {}
        cached_service.redis.set_json.side_effect = (
            lambda key, data, ttl: captured.update(data) or True
        )

        cached_service.set_user_context(
            UserContext(
                user_id="staff1",
                email="staff@example.com",
                organization_permissions={},
                account_permissions={},
                roles=["super_admin"],
            )
        )
        cached_service.redis.get_json.return_value = captured

        restored = cached_service.get_user_context("staff1")

        assert restored is not None
        assert restored.roles == ["super_admin"]
        assert restored.is_super_admin is True

    def test_cache_entry_missing_roles_is_invalidated(self, cached_service):
        """A pre-deploy cache entry without roles must not be trusted."""
        cached_service.redis.is_available.return_value = True
        cached_service.redis.get_json.return_value = {
            "user_id": "staff1",
            "email": "staff@example.com",
            "organization_permissions": {},
            "account_permissions": {},
            # roles intentionally absent
        }

        result = cached_service.get_user_context("staff1")

        assert result is None
        cached_service.redis.delete.assert_called_once_with("user_context:staff1")
