"""Unit tests for refactored user context authentication functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from src.kene_api.auth.audit_logger import SecurityEventType
from src.kene_api.auth.models import UserContext
from src.kene_api.auth.user_context import (
    _apply_rate_limiting,
    _build_user_context_from_data,
    _check_token_revocation,
    _get_or_create_user_document,
    _get_user_context_with_limiter,
    _verify_and_decode_token,
)


@pytest.fixture
def mock_request():
    """Create a mock FastAPI request."""
    request = MagicMock(spec=Request)
    request.client.host = "127.0.0.1"
    request.headers = {"User-Agent": "TestAgent/1.0"}
    request.url = "http://test.com/api/test"
    return request


@pytest.fixture
def mock_rate_limiter():
    """Create a mock rate limiter."""
    limiter = MagicMock()
    limiter.check_rate_limit = MagicMock()
    return limiter


@pytest.fixture
def mock_audit_logger():
    """Create a mock audit logger."""
    logger = AsyncMock()
    logger.log_rate_limit_exceeded = AsyncMock()
    logger.log_event = AsyncMock()
    logger.log_login_failure = AsyncMock()
    logger.log_login_success = AsyncMock()
    return logger


@pytest.fixture
def mock_credentials():
    """Create mock HTTP credentials."""
    creds = MagicMock(spec=HTTPAuthorizationCredentials)
    creds.credentials = "test-token-123"
    return creds


class TestApplyRateLimiting:
    """Test _apply_rate_limiting function."""

    @pytest.mark.asyncio
    async def test_rate_limiting_passes(
        self, mock_request, mock_rate_limiter, mock_audit_logger
    ):
        """Test rate limiting when under limit."""
        await _apply_rate_limiting(
            mock_request, mock_rate_limiter, mock_audit_logger, "127.0.0.1"
        )

        mock_rate_limiter.check_rate_limit.assert_called_once_with(mock_request)
        mock_audit_logger.log_rate_limit_exceeded.assert_not_called()

    @pytest.mark.asyncio
    async def test_rate_limiting_exceeded(
        self, mock_request, mock_rate_limiter, mock_audit_logger
    ):
        """Test rate limiting when limit exceeded."""
        exc = HTTPException(status_code=429, detail="Rate limit exceeded")
        mock_rate_limiter.check_rate_limit.side_effect = exc

        with pytest.raises(HTTPException) as exc_info:
            await _apply_rate_limiting(
                mock_request, mock_rate_limiter, mock_audit_logger, "127.0.0.1"
            )

        assert exc_info.value.status_code == 429
        mock_audit_logger.log_rate_limit_exceeded.assert_called_once_with(
            ip_address="127.0.0.1",
            endpoint="http://test.com/api/test",
        )


class TestVerifyAndDecodeToken:
    """Test _verify_and_decode_token function."""

    @pytest.mark.asyncio
    async def test_valid_token(
        self, mock_credentials, mock_audit_logger, mock_request, mock_rate_limiter
    ):
        """Test successful token verification."""
        with patch("src.kene_api.auth.user_context.verify_id_token") as mock_verify:
            mock_verify.return_value = {
                "uid": "user123",
                "email": "test@example.com",
                "iat": 1234567890,
            }

            decoded, user_id, email = await _verify_and_decode_token(
                mock_credentials,
                mock_audit_logger,
                "127.0.0.1",
                "TestAgent",
                mock_rate_limiter,
                mock_request,
            )

            assert user_id == "user123"
            assert email == "test@example.com"
            assert decoded["uid"] == "user123"
            mock_verify.assert_called_once_with("test-token-123")

    @pytest.mark.asyncio
    async def test_invalid_token(
        self, mock_credentials, mock_audit_logger, mock_request, mock_rate_limiter
    ):
        """Test failed token verification."""
        with patch("src.kene_api.auth.user_context.verify_id_token") as mock_verify:
            mock_verify.side_effect = Exception("Invalid token")

            with pytest.raises(HTTPException) as exc_info:
                await _verify_and_decode_token(
                    mock_credentials,
                    mock_audit_logger,
                    "127.0.0.1",
                    "TestAgent",
                    mock_rate_limiter,
                    mock_request,
                )

            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "Invalid authentication token"
            mock_audit_logger.log_event.assert_called_once()


class TestCheckTokenRevocation:
    """Test _check_token_revocation function."""

    @pytest.mark.asyncio
    async def test_token_not_revoked(self, mock_audit_logger):
        """Test when token is not revoked."""
        decoded_token = {"jti": "token123", "iat": 1234567890}

        with patch(
            "src.kene_api.auth.user_context.get_token_revocation_service"
        ) as mock_service:
            mock_revocation = AsyncMock()
            mock_revocation.is_token_revoked = AsyncMock(return_value=False)
            mock_service.return_value = mock_revocation

            # Should not raise
            await _check_token_revocation(
                decoded_token, "user123", mock_audit_logger, "127.0.0.1", "TestAgent"
            )

            mock_revocation.is_token_revoked.assert_called_once()
            mock_audit_logger.log_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_token_revoked(self, mock_audit_logger):
        """Test when token is revoked."""
        decoded_token = {"jti": "token123", "iat": 1234567890}

        with patch(
            "src.kene_api.auth.user_context.get_token_revocation_service"
        ) as mock_service:
            mock_revocation = AsyncMock()
            mock_revocation.is_token_revoked = AsyncMock(return_value=True)
            mock_service.return_value = mock_revocation

            with pytest.raises(HTTPException) as exc_info:
                await _check_token_revocation(
                    decoded_token,
                    "user123",
                    mock_audit_logger,
                    "127.0.0.1",
                    "TestAgent",
                )

            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "Token has been revoked"
            mock_audit_logger.log_event.assert_called_once()


class TestGetOrCreateUserDocument:
    """Test _get_or_create_user_document function."""

    @pytest.mark.asyncio
    async def test_existing_user(self, mock_audit_logger):
        """Test fetching existing user document."""
        mock_firestore = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "uid": "user123",
            "email": "test@example.com",
            "permissions": {"accounts": {}, "organizations": {}},
        }
        mock_firestore.collection().document().get.return_value = mock_doc

        result = await _get_or_create_user_document(
            mock_firestore,
            "user123",
            "test@example.com",
            mock_audit_logger,
            "127.0.0.1",
            "TestAgent",
        )

        assert result["uid"] == "user123"
        assert result["email"] == "test@example.com"
        mock_audit_logger.log_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_new_user(self, mock_audit_logger):
        """Test creating new user document."""
        mock_firestore = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_firestore.collection().document().get.return_value = mock_doc

        result = await _get_or_create_user_document(
            mock_firestore,
            "user123",
            "test@example.com",
            mock_audit_logger,
            "127.0.0.1",
            "TestAgent",
        )

        assert result["uid"] == "user123"
        assert result["email"] == "test@example.com"
        assert "permissions" in result
        mock_firestore.collection().document().set.assert_called_once()
        mock_audit_logger.log_event.assert_called_once_with(
            event_type=SecurityEventType.USER_CREATED,
            user_id="user123",
            email="test@example.com",
            ip_address="127.0.0.1",
            user_agent="TestAgent",
            severity="INFO",
        )


class TestBuildUserContextFromData:
    """Test _build_user_context_from_data function."""

    def test_build_context_with_permissions(self):
        """Test building user context with various permissions."""
        user_data = {
            "uid": "user123",
            "email": "test@example.com",
            "permissions": {
                "accounts": {"acc1": "admin", "acc2": "viewer"},
                "organizations": {"org1": "owner"},
                "account_permissions": {"acc3": "editor"},
            },
        }

        context = _build_user_context_from_data(
            "user123", "test@example.com", user_data
        )

        assert context.user_id == "user123"
        assert context.email == "test@example.com"
        assert set(context.accessible_accounts) == {"acc3"}
        assert context.account_permissions == {"acc3": "editor"}
        assert context.organization_permissions == {"org1": "owner"}

    def test_build_context_no_permissions(self):
        """Test building user context without permissions."""
        user_data = {"uid": "user123", "email": "test@example.com"}

        context = _build_user_context_from_data(
            "user123", "test@example.com", user_data
        )

        assert context.user_id == "user123"
        assert context.email == "test@example.com"
        assert context.accessible_accounts == []
        assert context.account_permissions == {}
        assert context.organization_permissions == {}


class TestGetUserContextWithLimiter:
    """Test the main _get_user_context_with_limiter function."""

    @pytest.mark.asyncio
    async def test_missing_credentials(self, mock_request):
        """Test handling missing credentials."""
        mock_firestore = MagicMock()

        with patch(
            "src.kene_api.auth.user_context.get_audit_logger"
        ) as mock_get_logger:
            mock_get_logger.return_value = AsyncMock()

            with pytest.raises(HTTPException) as exc_info:
                await _get_user_context_with_limiter(
                    mock_request, None, mock_firestore, None
                )

            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "Missing authentication credentials"

    @pytest.mark.asyncio
    async def test_cached_context_returned(self, mock_request, mock_credentials):
        """Test returning cached user context."""
        mock_firestore = MagicMock()
        cached_context = UserContext(
            user_id="user123",
            email="test@example.com",
            account_permissions={"acc1": "admin"},
            organization_permissions={},
        )

        with (
            patch("src.kene_api.auth.user_context.get_audit_logger") as mock_get_logger,
            patch(
                "src.kene_api.auth.user_context._verify_and_decode_token"
            ) as mock_verify,
            patch(
                "src.kene_api.auth.user_context._check_token_revocation"
            ) as mock_check,
            patch(
                "src.kene_api.auth.cached_user_context.get_cached_user_context_service"
            ) as mock_cache,
        ):
            mock_get_logger.return_value = AsyncMock()
            mock_verify.return_value = (
                {"uid": "user123"},
                "user123",
                "test@example.com",
            )
            mock_check.return_value = None

            cache_service = MagicMock()
            cache_service.get_user_context.return_value = cached_context
            mock_cache.return_value = cache_service

            result = await _get_user_context_with_limiter(
                mock_request, mock_credentials, mock_firestore, None
            )

            assert result == cached_context
            cache_service.get_user_context.assert_called_once_with("user123")

    @pytest.mark.asyncio
    async def test_super_admin_is_rate_limited(self, mock_request, mock_credentials):
        """Super admins are rate limited like everyone else (bypass removed)."""
        mock_firestore = MagicMock()
        mock_firestore.get_client().collection().document().get().exists = True
        mock_firestore.get_client().collection().document().get().to_dict.return_value = {
            "uid": "admin123",
            "email": "admin@ken-e.ai",
            "permissions": {},
        }

        with (
            patch("src.kene_api.auth.user_context.get_audit_logger") as mock_get_logger,
            patch(
                "src.kene_api.auth.user_context._verify_and_decode_token"
            ) as mock_verify,
            patch(
                "src.kene_api.auth.user_context._check_token_revocation"
            ) as mock_check,
            patch(
                "src.kene_api.auth.user_context._apply_rate_limiting"
            ) as mock_rate_limit,
            patch(
                "src.kene_api.auth.cached_user_context.get_cached_user_context_service"
            ) as mock_cache,
        ):
            mock_get_logger.return_value = AsyncMock()
            mock_verify.return_value = (
                {
                    "uid": "admin123",
                    "email": "admin@ken-e.ai",
                    "email_verified": True,
                },
                "admin123",
                "admin@ken-e.ai",
            )
            mock_check.return_value = None

            cache_service = MagicMock()
            cache_service.get_user_context.return_value = None
            cache_service.set_user_context = MagicMock()
            mock_cache.return_value = cache_service

            result = await _get_user_context_with_limiter(
                mock_request, mock_credentials, mock_firestore, None
            )

            assert result.user_id == "admin123"
            assert result.email == "admin@ken-e.ai"
            # Rate limiting now applies to super admins too.
            mock_rate_limit.assert_called_once()


class TestApiTestBypassToken:
    """Unit tests for the API_TEST_BYPASS_TOKEN bypass path in _get_user_context_with_limiter."""

    @pytest.fixture
    def mock_firestore_service(self):
        return MagicMock()

    @pytest.mark.asyncio
    async def test_exact_token_returns_non_member(
        self, mock_request, mock_firestore_service
    ):
        """Exact bearer match → non-member UserContext with empty account_permissions."""
        creds = MagicMock()
        creds.credentials = "test-bypass-secret"

        with patch("src.kene_api.auth.user_context.settings") as mock_settings:
            mock_settings.api_test_bypass_token = "test-bypass-secret"

            result = await _get_user_context_with_limiter(
                mock_request, creds, mock_firestore_service, None
            )

        assert result.user_id == "test-bypass-no-member"
        assert result.email == "no-member@test.internal"
        assert result.account_permissions == {}
        assert result.organization_permissions == {}
        assert result.roles == []

    @pytest.mark.asyncio
    async def test_prefixed_token_returns_member(
        self, mock_request, mock_firestore_service
    ):
        """Bearer == '{token}:{account_id}' → member UserContext for that account."""
        creds = MagicMock()
        creds.credentials = "test-bypass-secret:acc-xyz"

        with patch("src.kene_api.auth.user_context.settings") as mock_settings:
            mock_settings.api_test_bypass_token = "test-bypass-secret"

            result = await _get_user_context_with_limiter(
                mock_request, creds, mock_firestore_service, None
            )

        assert result.user_id == "test-bypass-acc-xyz"
        assert result.email == "member-acc-xyz@test.internal"
        assert result.account_permissions == {"acc-xyz": "edit"}
        assert result.organization_permissions == {}
        assert result.roles == []

    @pytest.mark.asyncio
    async def test_unrecognized_bearer_falls_through_to_firebase(
        self, mock_request, mock_credentials, mock_firestore_service
    ):
        """Unrecognized bearer value falls through to normal Firebase verification."""
        # mock_credentials has bearer "test-token-123" which does not match the
        # bypass token "test-bypass-secret", so the bypass path is not taken.
        with (
            patch("src.kene_api.auth.user_context.settings") as mock_settings,
            patch(
                "src.kene_api.auth.user_context._verify_and_decode_token",
                new_callable=AsyncMock,
            ) as mock_verify,
            patch(
                "src.kene_api.auth.user_context._apply_rate_limiting",
                new_callable=AsyncMock,
            ),
            patch(
                "src.kene_api.auth.user_context._check_token_revocation",
                new_callable=AsyncMock,
            ),
            patch(
                "src.kene_api.auth.cached_user_context.get_cached_user_context_service"
            ) as mock_cache_factory,
        ):
            mock_settings.api_test_bypass_token = "test-bypass-secret"
            mock_settings.load_test_bypass_uid = ""
            mock_verify.return_value = (
                {"uid": "real-uid", "email": "real@example.com"},
                "real-uid",
                "real@example.com",
            )
            cache_svc = MagicMock()
            cache_svc.get_user_context.return_value = None
            cache_svc.set_user_context = MagicMock()
            mock_cache_factory.return_value = cache_svc

            mock_firestore_db = MagicMock()
            mock_doc = MagicMock()
            mock_doc.exists = True
            mock_doc.to_dict.return_value = {
                "uid": "real-uid",
                "email": "real@example.com",
                "permissions": {"organizations": {}, "account_permissions": {}},
                "roles": [],
            }
            mock_firestore_db.collection.return_value.document.return_value.get.return_value = mock_doc
            mock_firestore_service.get_client.return_value = mock_firestore_db

            with patch("src.kene_api.auth.user_context.get_audit_logger") as mock_audit:
                mock_audit.return_value = AsyncMock()
                result = await _get_user_context_with_limiter(
                    mock_request, mock_credentials, mock_firestore_service, None
                )

        # Firebase verify_id_token was called — the bypass was not taken.
        mock_verify.assert_called_once()
        assert result.user_id == "real-uid"
