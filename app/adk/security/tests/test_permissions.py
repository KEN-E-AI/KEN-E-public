"""Tests for permission verification service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.adk.security.permissions import (
    PermissionCheckResult,
    PermissionService,
    TokenInfo,
    get_permission_service,
    get_provider_for_category,
)


class TestTokenInfo:
    """Tests for TokenInfo dataclass."""

    def test_minimal_token_info(self):
        """Test creating minimal token info."""
        token = TokenInfo(access_token="abc123")

        assert token.access_token == "abc123"
        assert token.refresh_token is None
        assert token.expires_at is None
        assert token.scopes == []
        assert token.provider == "unknown"

    def test_full_token_info(self):
        """Test creating full token info."""
        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        token = TokenInfo(
            access_token="access",
            refresh_token="refresh",
            expires_at=expires,
            scopes=["scope1", "scope2"],
            provider="google",
        )

        assert token.access_token == "access"
        assert token.refresh_token == "refresh"
        assert token.expires_at == expires
        assert token.scopes == ["scope1", "scope2"]
        assert token.provider == "google"


class TestPermissionCheckResult:
    """Tests for PermissionCheckResult dataclass."""

    def test_allowed_result(self):
        """Test creating an allowed result."""
        result = PermissionCheckResult(allowed=True, reason="All checks passed")

        assert result.allowed is True
        assert result.requires_reauth is False
        assert result.missing_scopes is None

    def test_denied_result_with_missing_scopes(self):
        """Test creating a denied result with missing scopes."""
        result = PermissionCheckResult(
            allowed=False,
            reason="Missing scopes",
            requires_reauth=True,
            missing_scopes=["scope1", "scope2"],
        )

        assert result.allowed is False
        assert result.requires_reauth is True
        assert result.missing_scopes == ["scope1", "scope2"]


class TestPermissionService:
    """Tests for PermissionService."""

    @pytest.fixture
    def service(self):
        """Create a permission service for testing."""
        return PermissionService()

    @pytest.mark.asyncio
    async def test_no_scopes_required_allows(self, service):
        """Test that tools with no required scopes are allowed."""
        result = await service.verify_tool_permission(
            tool_name="public_tool",
            required_scopes=[],
            user_id="user1",
            account_id="acct1",
            token_info=None,
        )

        assert result.allowed is True
        assert result.reason == "No permissions required"

    @pytest.mark.asyncio
    async def test_no_token_denies(self, service):
        """Test that missing token denies access."""
        result = await service.verify_tool_permission(
            tool_name="private_tool",
            required_scopes=["read"],
            user_id="user1",
            account_id="acct1",
            token_info=None,
        )

        assert result.allowed is False
        assert result.requires_reauth is True
        assert result.missing_scopes == ["read"]
        assert "No authentication token" in result.reason

    @pytest.mark.asyncio
    async def test_expired_token_denies(self, service):
        """Test that expired token denies access."""
        # Token expired 1 hour ago
        expired_token = TokenInfo(
            access_token="expired",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            scopes=["read"],
        )

        result = await service.verify_tool_permission(
            tool_name="tool",
            required_scopes=["read"],
            user_id="user1",
            account_id="acct1",
            token_info=expired_token,
        )

        assert result.allowed is False
        assert result.requires_reauth is True
        assert "expired" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_expiring_soon_denies(self, service):
        """Test that token expiring within buffer (5 min) denies."""
        # Token expires in 2 minutes (within 5 minute buffer)
        expiring_token = TokenInfo(
            access_token="expiring",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=2),
            scopes=["read"],
        )

        result = await service.verify_tool_permission(
            tool_name="tool",
            required_scopes=["read"],
            user_id="user1",
            account_id="acct1",
            token_info=expiring_token,
        )

        assert result.allowed is False
        assert result.requires_reauth is True

    @pytest.mark.asyncio
    async def test_valid_token_with_all_scopes_allows(self, service):
        """Test that valid token with all scopes allows access."""
        valid_token = TokenInfo(
            access_token="valid",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scopes=["read", "write", "extra"],
        )

        result = await service.verify_tool_permission(
            tool_name="tool",
            required_scopes=["read", "write"],
            user_id="user1",
            account_id="acct1",
            token_info=valid_token,
        )

        assert result.allowed is True
        assert result.reason == "All permissions verified"

    @pytest.mark.asyncio
    async def test_missing_scopes_denies(self, service):
        """Test that missing scopes denies access."""
        token = TokenInfo(
            access_token="partial",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scopes=["read"],  # Missing "write"
        )

        result = await service.verify_tool_permission(
            tool_name="tool",
            required_scopes=["read", "write"],
            user_id="user1",
            account_id="acct1",
            token_info=token,
        )

        assert result.allowed is False
        assert result.requires_reauth is True
        assert "write" in result.missing_scopes

    @pytest.mark.asyncio
    async def test_token_without_expiry_is_valid(self, service):
        """Test that token without expiry (if scopes match) is allowed."""
        token = TokenInfo(
            access_token="no_expiry",
            expires_at=None,  # No expiry set
            scopes=["read"],
        )

        result = await service.verify_tool_permission(
            tool_name="tool",
            required_scopes=["read"],
            user_id="user1",
            account_id="acct1",
            token_info=token,
        )

        assert result.allowed is True


class TestGetTokenInfoFromState:
    """Tests for extracting token info from session state."""

    @pytest.fixture
    def service(self):
        return PermissionService()

    @pytest.mark.asyncio
    async def test_extract_google_credentials(self, service):
        """Test extracting Google credentials from state."""
        state = {
            "google_credentials": {
                "access_token": "google_token",
                "refresh_token": "google_refresh",
                "scopes": ["analytics.readonly"],
                "expires_at": (
                    datetime.now(timezone.utc) + timedelta(hours=1)
                ).isoformat(),
            }
        }

        token = await service.get_token_info_from_state(state, "google")

        assert token is not None
        assert token.access_token == "google_token"
        assert token.refresh_token == "google_refresh"
        assert token.scopes == ["analytics.readonly"]
        assert token.expires_at is not None

    @pytest.mark.asyncio
    async def test_missing_credentials_returns_none(self, service):
        """Test that missing credentials returns None."""
        state = {"other_data": "value"}

        token = await service.get_token_info_from_state(state, "google")

        assert token is None

    @pytest.mark.asyncio
    async def test_numeric_expiry_timestamp(self, service):
        """Test handling numeric expiry timestamp."""
        future_ts = (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
        state = {
            "hubspot_credentials": {
                "access_token": "hubspot_token",
                "expires_at": future_ts,
            }
        }

        token = await service.get_token_info_from_state(state, "hubspot")

        assert token is not None
        assert token.expires_at is not None
        # Should be in the future
        assert token.expires_at > datetime.now(timezone.utc)


class TestCategoryToProvider:
    """Tests for category to provider mapping."""

    def test_analytics_maps_to_google(self):
        """Test analytics category maps to google."""
        assert get_provider_for_category("analytics") == "google"

    def test_crm_maps_to_hubspot(self):
        """Test CRM category maps to hubspot."""
        assert get_provider_for_category("crm") == "hubspot"

    def test_social_maps_to_meta(self):
        """Test social category maps to meta."""
        assert get_provider_for_category("social") == "meta"

    def test_unknown_category_returns_unknown(self):
        """Test unknown category returns 'unknown'."""
        assert get_provider_for_category("nonexistent") == "unknown"


class TestSingleton:
    """Tests for singleton behavior."""

    def test_get_permission_service_returns_same_instance(self):
        """Test that get_permission_service returns same instance."""
        service1 = get_permission_service()
        service2 = get_permission_service()

        assert service1 is service2
