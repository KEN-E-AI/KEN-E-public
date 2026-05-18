"""Unit tests for user context and authentication utilities."""

from unittest import mock

import pytest
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from src.kene_api.auth.models import UserContext
from src.kene_api.auth.user_context import (
    get_current_user_context,
    get_optional_user_context,
    require_account_access,
    require_organization_access,
)


class TestUserContext:
    """Test UserContext dataclass methods."""

    def test_has_account_access_without_roles(self):
        """Test account access check without specific roles."""
        user = UserContext(
            user_id="test-user",
            email="test@example.com",
            account_permissions={"acc_1": "admin", "acc_2": "viewer"},
            organization_permissions={},
        )

        # Should have access to accounts in permissions
        assert user.has_account_access("acc_1") is True
        assert user.has_account_access("acc_2") is True

        # Should not have access to other accounts
        assert user.has_account_access("acc_3") is False

    def test_has_account_access_with_roles(self):
        """Test account access check with specific role requirements."""
        user = UserContext(
            user_id="test-user",
            email="test@example.com",
            account_permissions={"acc_1": "admin", "acc_2": "viewer"},
            organization_permissions={},
        )

        # Should have access with correct role
        assert user.has_account_access("acc_1", ["admin"]) is True
        assert user.has_account_access("acc_2", ["viewer", "admin"]) is True

        # Should not have access with wrong role
        assert user.has_account_access("acc_1", ["viewer"]) is False
        assert user.has_account_access("acc_2", ["admin"]) is False

    def test_has_organization_access_without_roles(self):
        """Test organization access check without specific roles."""
        user = UserContext(
            user_id="test-user",
            email="test@example.com",
            account_permissions={},
            organization_permissions={"org_1": "admin", "org_2": "viewer"},
        )

        # Should have access to orgs in permissions
        assert user.has_organization_access("org_1") is True
        assert user.has_organization_access("org_2") is True

        # Should not have access to other orgs
        assert user.has_organization_access("org_3") is False

    def test_has_organization_access_with_roles(self):
        """Test organization access check with specific role requirements."""
        user = UserContext(
            user_id="test-user",
            email="test@example.com",
            account_permissions={},
            organization_permissions={"org_1": "admin", "org_2": "viewer"},
        )

        # Should have access with correct role
        assert user.has_organization_access("org_1", ["admin"]) is True
        assert user.has_organization_access("org_2", ["viewer", "admin"]) is True

        # Should not have access with wrong role
        assert user.has_organization_access("org_1", ["viewer"]) is False
        assert user.has_organization_access("org_2", ["admin"]) is False


class TestGetCurrentUserContext:
    """Test get_current_user_context function."""

    @pytest.mark.asyncio
    async def test_missing_credentials(self):
        """Test that missing credentials raise 401."""
        mock_request = mock.Mock(spec=Request)
        mock_request.headers = mock.Mock()
        mock_request.headers.get = mock.Mock(return_value=None)
        mock_request.client = mock.Mock(host="127.0.0.1")
        mock_firestore = mock.Mock()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_context(mock_request, None, mock_firestore)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Missing authentication credentials"

    @pytest.mark.asyncio
    async def test_invalid_token(self):
        """Test that invalid tokens raise 401."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="invalid-token"
        )
        mock_firestore = mock.Mock()
        mock_request = mock.Mock(spec=Request)
        mock_request.client.host = "127.0.0.1"
        mock_request.url = "http://test.com/api/test"
        mock_request.headers = {}

        with mock.patch(
            "src.kene_api.auth.user_context.verify_id_token",
            side_effect=Exception("Invalid token"),
        ):
            with mock.patch(
                "src.kene_api.auth.user_context.token_rate_limiter.check_rate_limit"
            ):
                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user_context(
                        mock_request, credentials, mock_firestore
                    )

                assert exc_info.value.status_code == 401
                assert exc_info.value.detail == "Invalid authentication token"

    @pytest.mark.asyncio
    async def test_valid_token_new_user(self):
        """Test that valid token for new user creates user document."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="valid-token"
        )
        decoded_token = {
            "uid": "new-user-id",
            "email": "newuser@example.com",
        }

        # Mock Firestore
        mock_firestore_client = mock.Mock()
        mock_collection = mock.Mock()
        mock_document = mock.Mock()
        mock_user_doc = mock.Mock()
        mock_user_doc.exists = False

        mock_firestore_client.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_document
        mock_document.get.return_value = mock_user_doc
        mock_document.set = mock.Mock()

        mock_firestore_service = mock.Mock()
        mock_firestore_service.get_client.return_value = mock_firestore_client

        mock_request = mock.Mock(spec=Request)
        mock_request.client = mock.Mock(host="127.0.0.1")
        mock_request.headers = mock.Mock()
        mock_request.headers.get = mock.Mock(return_value="TestAgent/1.0")
        mock_request.url = "http://test.com/api/test"

        mock_revocation_service = mock.AsyncMock()
        mock_revocation_service.is_token_revoked = mock.AsyncMock(return_value=False)

        with mock.patch(
            "src.kene_api.auth.user_context.verify_id_token", return_value=decoded_token
        ):
            with mock.patch(
                "src.kene_api.auth.user_context.token_rate_limiter.check_rate_limit"
            ):
                with mock.patch(
                    "src.kene_api.auth.user_context.get_token_revocation_service",
                    return_value=mock_revocation_service,
                ):
                    with mock.patch(
                        "src.kene_api.auth.cached_user_context.get_cached_user_context_service"
                    ) as mock_get_cached:
                        mock_cached_service = mock.Mock()
                        mock_cached_service.get_user_context.return_value = None
                        mock_cached_service.set_user_context.return_value = True
                        mock_get_cached.return_value = mock_cached_service

                        result = await get_current_user_context(
                            mock_request, credentials, mock_firestore_service
                        )

            # Verify user creation
            mock_document.set.assert_called_once()
            created_data = mock_document.set.call_args[0][0]
            assert created_data["uid"] == "new-user-id"
            assert created_data["email"] == "newuser@example.com"
            assert created_data["permissions"]["account_permissions"] == {}
            assert created_data["permissions"]["organizations"] == {}

            # Verify returned context
            assert result.user_id == "new-user-id"
            assert result.email == "newuser@example.com"
            assert result.accessible_accounts == []
            assert result.account_permissions == {}
            assert result.organization_permissions == {}

    @pytest.mark.asyncio
    async def test_super_admin_is_rate_limited(self):
        """Super admins are rate limited like everyone else (bypass removed)."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="valid-token"
        )
        decoded_token = {
            "uid": "super-admin-id",
            "email": "admin@ken-e.ai",  # Super admin email domain
            "email_verified": True,
            "iat": 1234567890,
        }

        # Mock Firestore
        mock_firestore_client = mock.Mock()
        mock_collection = mock.Mock()
        mock_document = mock.Mock()
        mock_user_doc = mock.Mock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {
            "uid": "super-admin-id",
            "email": "admin@ken-e.ai",
            "permissions": {
                "accounts": {},
                "organizations": {},
            },
            "roles": ["super_admin"],
        }

        mock_firestore_client.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_document
        mock_document.get.return_value = mock_user_doc

        mock_firestore_service = mock.Mock()
        mock_firestore_service.get_client.return_value = mock_firestore_client

        mock_request = mock.Mock(spec=Request)
        mock_request.client = mock.Mock(host="127.0.0.1")
        mock_request.headers = mock.Mock()
        mock_request.headers.get = mock.Mock(return_value="User-Agent")
        mock_request.url = "http://test.com/api/endpoint"

        with mock.patch(
            "src.kene_api.auth.user_context.verify_id_token", return_value=decoded_token
        ):
            # Mock rate limiter - should NOT be called for super admin
            with mock.patch(
                "src.kene_api.auth.user_context.token_rate_limiter.check_rate_limit"
            ) as mock_rate_limit:
                with mock.patch(
                    "src.kene_api.auth.cached_user_context.get_cached_user_context_service"
                ) as mock_get_cached:
                    with mock.patch(
                        "src.kene_api.auth.user_context.get_token_revocation_service"
                    ) as mock_get_revocation:
                        with mock.patch(
                            "src.kene_api.auth.user_context.get_audit_logger"
                        ) as mock_get_audit:
                            mock_cached_service = mock.Mock()
                            mock_cached_service.get_user_context.return_value = None
                            mock_cached_service.set_user_context.return_value = True
                            mock_get_cached.return_value = mock_cached_service

                            mock_revocation_service = mock.Mock()
                            mock_revocation_service.is_token_revoked = mock.AsyncMock(
                                return_value=False
                            )
                            mock_get_revocation.return_value = mock_revocation_service

                            mock_audit_logger = mock.Mock()
                            mock_audit_logger.log_event = mock.AsyncMock()
                            mock_audit_logger.log_login_success = mock.AsyncMock()
                            mock_get_audit.return_value = mock_audit_logger

                            result = await get_current_user_context(
                                mock_request, credentials, mock_firestore_service
                            )

                            # Rate limiting now applies to super admins too.
                            mock_rate_limit.assert_called()

                            # Verify returned context
                            assert result.user_id == "super-admin-id"
                            assert result.email == "admin@ken-e.ai"
                            assert result.is_super_admin is True

    @pytest.mark.asyncio
    async def test_regular_user_is_rate_limited(self):
        """Test that regular users are subject to rate limiting."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="valid-token"
        )
        decoded_token = {
            "uid": "regular-user-id",
            "email": "user@example.com",  # Not a super admin email
            "iat": 1234567890,
        }

        mock_firestore_service = mock.Mock()
        mock_request = mock.Mock(spec=Request)
        mock_request.client = mock.Mock(host="127.0.0.1")
        mock_request.headers = mock.Mock()
        mock_request.headers.get = mock.Mock(return_value="User-Agent")
        mock_request.url = "http://test.com/api/endpoint"

        with mock.patch(
            "src.kene_api.auth.user_context.verify_id_token", return_value=decoded_token
        ):
            # Mock rate limiter to raise exception
            with mock.patch(
                "src.kene_api.auth.user_context.token_rate_limiter.check_rate_limit"
            ) as mock_rate_limit:
                with mock.patch(
                    "src.kene_api.auth.user_context.get_audit_logger"
                ) as mock_get_audit:
                    mock_rate_limit.side_effect = HTTPException(
                        status_code=429, detail="Rate limit exceeded"
                    )
                    mock_audit_logger = mock.Mock()
                    mock_audit_logger.log_rate_limit_exceeded = mock.AsyncMock()
                    mock_get_audit.return_value = mock_audit_logger

                    with pytest.raises(HTTPException) as exc_info:
                        await get_current_user_context(
                            mock_request, credentials, mock_firestore_service
                        )

                    # Verify rate limiter was called for regular user
                    mock_rate_limit.assert_called_once_with(mock_request)

                    # Verify the exception is rate limit
                    assert exc_info.value.status_code == 429
                    assert "Rate limit exceeded" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_valid_token_existing_user(self):
        """Test that valid token for existing user returns user data."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="valid-token"
        )
        decoded_token = {
            "uid": "existing-user-id",
            "email": "user@example.com",
        }

        # Mock Firestore
        mock_firestore_client = mock.Mock()
        mock_collection = mock.Mock()
        mock_document = mock.Mock()
        mock_user_doc = mock.Mock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {
            "uid": "existing-user-id",
            "email": "user@example.com",
            "permissions": {
                "accounts": {"acc_1": "admin", "acc_2": "viewer"},
                "organizations": {"org_1": "admin"},
            },
        }

        mock_firestore_client.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_document
        mock_document.get.return_value = mock_user_doc

        mock_firestore_service = mock.Mock()
        mock_firestore_service.get_client.return_value = mock_firestore_client

        mock_request = mock.Mock(spec=Request)
        mock_request.client = mock.Mock(host="127.0.0.1")
        mock_request.headers = mock.Mock()
        mock_request.headers.get = mock.Mock(return_value="TestAgent/1.0")
        mock_request.url = "http://test.com/api/test"

        mock_revocation_service = mock.AsyncMock()
        mock_revocation_service.is_token_revoked = mock.AsyncMock(return_value=False)

        with mock.patch(
            "src.kene_api.auth.user_context.verify_id_token", return_value=decoded_token
        ):
            with mock.patch(
                "src.kene_api.auth.user_context.token_rate_limiter.check_rate_limit"
            ):
                with mock.patch(
                    "src.kene_api.auth.user_context.get_token_revocation_service",
                    return_value=mock_revocation_service,
                ):
                    with mock.patch(
                        "src.kene_api.auth.cached_user_context.get_cached_user_context_service"
                    ) as mock_get_cached:
                        mock_cached_service = mock.Mock()
                        mock_cached_service.get_user_context.return_value = None
                        mock_cached_service.set_user_context.return_value = True
                        mock_get_cached.return_value = mock_cached_service

                        result = await get_current_user_context(
                            mock_request, credentials, mock_firestore_service
                        )

            # Verify no user creation (existing user)
            mock_document.set.assert_not_called()

            # Verify returned context
            assert result.user_id == "existing-user-id"
            assert result.email == "user@example.com"
            assert result.accessible_accounts == []
            assert result.account_permissions == {}
            assert result.organization_permissions == {"org_1": "admin"}


class TestGetOptionalUserContext:
    """Test get_optional_user_context function."""

    @pytest.mark.asyncio
    async def test_no_credentials_returns_none(self):
        """Test that no credentials return None."""
        mock_request = mock.Mock(spec=Request)
        mock_firestore = mock.Mock()

        result = await get_optional_user_context(mock_request, None, mock_firestore)
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_credentials_returns_none(self):
        """Test that invalid credentials return None."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="invalid-token"
        )
        mock_firestore = mock.Mock()
        mock_request = mock.Mock(spec=Request)

        with mock.patch(
            "src.kene_api.auth.user_context.get_current_user_context",
            side_effect=HTTPException(status_code=401, detail="Invalid token"),
        ):
            result = await get_optional_user_context(
                mock_request, credentials, mock_firestore
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_valid_credentials_returns_context(self):
        """Test that valid credentials return user context."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="valid-token"
        )
        mock_firestore = mock.Mock()
        mock_request = mock.Mock(spec=Request)

        expected_context = UserContext(
            user_id="test-user",
            email="test@example.com",
            account_permissions={"acc_1": "admin"},
            organization_permissions={},
        )

        with mock.patch(
            "src.kene_api.auth.user_context.get_current_user_context",
            return_value=expected_context,
        ):
            result = await get_optional_user_context(
                mock_request, credentials, mock_firestore
            )
            assert result == expected_context


class TestRequireAccountAccess:
    """Test require_account_access function."""

    def test_require_account_access_granted(self):
        """Test that access is granted when user has permission."""
        user = UserContext(
            user_id="test-user",
            email="test@example.com",
            account_permissions={"acc_1": "admin"},
            organization_permissions={},
        )

        check_fn = require_account_access("acc_1")
        # Should not raise
        check_fn(user)

    def test_require_account_access_denied_no_access(self):
        """Test that access is denied when user lacks permission."""
        user = UserContext(
            user_id="test-user",
            email="test@example.com",
            account_permissions={"acc_1": "admin"},
            organization_permissions={},
        )

        check_fn = require_account_access("acc_2")
        with mock.patch("asyncio.create_task"):
            with pytest.raises(HTTPException) as exc_info:
                check_fn(user)

        assert exc_info.value.status_code == 403
        assert "Access denied to account acc_2" in exc_info.value.detail

    def test_require_account_access_with_roles(self):
        """Test that access requires specific roles when specified."""
        user = UserContext(
            user_id="test-user",
            email="test@example.com",
            account_permissions={"acc_1": "viewer"},
            organization_permissions={},
        )

        # Should succeed with correct role
        check_fn = require_account_access("acc_1", ["viewer", "admin"])
        with mock.patch("asyncio.create_task"):
            check_fn(user)

        # Should fail with wrong role
        check_fn = require_account_access("acc_1", ["admin"])
        with mock.patch("asyncio.create_task"):
            with pytest.raises(HTTPException) as exc_info:
                check_fn(user)

        assert exc_info.value.status_code == 403
        assert "with role in ['admin']" in exc_info.value.detail


class TestRequireOrganizationAccess:
    """Test require_organization_access function."""

    def test_require_organization_access_granted(self):
        """Test that access is granted when user has permission."""
        user = UserContext(
            user_id="test-user",
            email="test@example.com",
            account_permissions={},
            organization_permissions={"org_1": "admin"},
        )

        check_fn = require_organization_access("org_1")
        # Should not raise
        check_fn(user)

    def test_require_organization_access_denied(self):
        """Test that access is denied when user lacks permission."""
        user = UserContext(
            user_id="test-user",
            email="test@example.com",
            account_permissions={},
            organization_permissions={"org_1": "admin"},
        )

        check_fn = require_organization_access("org_2")
        with mock.patch("asyncio.create_task"):
            with pytest.raises(HTTPException) as exc_info:
                check_fn(user)

        assert exc_info.value.status_code == 403
        assert "Access denied to organization org_2" in exc_info.value.detail
