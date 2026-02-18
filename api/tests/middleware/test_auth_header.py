"""Tests for OAuth header authentication middleware."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from src.kene_api.middleware.auth_header import (
    AuthHeaderMiddleware,
    OAuthCredentials,
)


class TestOAuthCredentials:
    """Tests for OAuthCredentials model."""

    def test_minimal_credentials(self):
        """Test creating credentials with only access_token."""
        creds = OAuthCredentials(access_token="token123")

        assert creds.access_token == "token123"
        assert creds.refresh_token is None
        assert creds.token_type == "Bearer"
        assert creds.provider == "unknown"
        assert creds.scopes == []

    def test_full_credentials(self):
        """Test creating credentials with all fields."""
        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        creds = OAuthCredentials(
            access_token="access",
            refresh_token="refresh",
            token_type="Bearer",
            expires_at=expires,
            scopes=["read", "write"],
            provider="google",
            client_id="client_123",
            client_secret="secret_456",
            token_uri="https://oauth2.googleapis.com/token",
        )

        assert creds.access_token == "access"
        assert creds.refresh_token == "refresh"
        assert creds.expires_at == expires
        assert creds.scopes == ["read", "write"]
        assert creds.provider == "google"


def _make_request(headers: dict[str, str] | None = None) -> MagicMock:
    """Create a mock request with proper headers dict."""
    request = MagicMock()
    request.headers = headers or {}
    request.json = AsyncMock(side_effect=Exception("No body"))
    return request


class TestAuthHeaderMiddleware:
    """Tests for AuthHeaderMiddleware."""

    @pytest.fixture
    def middleware(self):
        """Create a middleware instance for testing."""
        return AuthHeaderMiddleware()

    @pytest.mark.asyncio
    async def test_simple_bearer_token(self, middleware):
        """Test extraction of simple bearer token."""
        request = _make_request()
        auth = HTTPAuthorizationCredentials(scheme="Bearer", credentials="my_access_token")

        credentials, source = await middleware.extract_credentials(request, auth)

        assert credentials.access_token == "my_access_token"
        assert source == "header"
        assert credentials.refresh_token is None

    @pytest.mark.asyncio
    async def test_x_oauth_credentials_header(self, middleware):
        """Test extraction of full credentials via X-OAuth-Credentials header."""
        full_creds = {
            "access_token": "token123",
            "refresh_token": "refresh456",
            "provider": "google",
            "scopes": ["analytics.readonly"],
        }
        encoded = base64.b64encode(json.dumps(full_creds).encode()).decode()
        request = _make_request(headers={"X-OAuth-Credentials": encoded})

        credentials, source = await middleware.extract_credentials(request, None)

        assert credentials.access_token == "token123"
        assert credentials.refresh_token == "refresh456"
        assert credentials.provider == "google"
        assert credentials.scopes == ["analytics.readonly"]
        assert source == "header"

    @pytest.mark.asyncio
    async def test_x_oauth_credentials_with_expiry(self, middleware):
        """Test X-OAuth-Credentials with numeric timestamp expiry."""
        expires_timestamp = datetime.now(timezone.utc).timestamp() + 3600
        full_creds = {
            "access_token": "token",
            "expires_at": expires_timestamp,
        }
        encoded = base64.b64encode(json.dumps(full_creds).encode()).decode()
        request = _make_request(headers={"X-OAuth-Credentials": encoded})

        credentials, source = await middleware.extract_credentials(request, None)

        assert credentials.access_token == "token"
        assert credentials.expires_at is not None
        assert credentials.expires_at > datetime.now(timezone.utc)

    @pytest.mark.asyncio
    async def test_x_oauth_credentials_preferred_over_bearer(self, middleware):
        """Test that X-OAuth-Credentials takes priority over Authorization header."""
        full_creds = {"access_token": "oauth_creds_token"}
        encoded = base64.b64encode(json.dumps(full_creds).encode()).decode()
        request = _make_request(headers={"X-OAuth-Credentials": encoded})
        auth = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bearer_token")

        credentials, source = await middleware.extract_credentials(request, auth)

        assert credentials.access_token == "oauth_creds_token"

    @pytest.mark.asyncio
    async def test_legacy_body_credentials(self, middleware):
        """Test extraction of legacy body-based credentials."""
        request = MagicMock()
        request.headers = {}

        body_creds = {
            "access_token": "old_token",
            "refresh_token": "old_refresh",
            "provider": "google",
        }
        encoded = base64.b64encode(json.dumps(body_creds).encode()).decode()
        request.json = AsyncMock(return_value={"tenant_credentials": encoded})

        credentials, source = await middleware.extract_credentials(request, None)

        assert credentials.access_token == "old_token"
        assert credentials.refresh_token == "old_refresh"
        assert source == "body"

    @pytest.mark.asyncio
    async def test_no_credentials_raises_401(self, middleware):
        """Test that missing credentials raises 401."""
        request = MagicMock()
        request.headers = {}
        request.json = AsyncMock(return_value={})

        with pytest.raises(HTTPException) as exc_info:
            await middleware.extract_credentials(request, None)

        assert exc_info.value.status_code == 401
        assert "No authentication credentials" in exc_info.value.detail
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    @pytest.mark.asyncio
    async def test_header_preferred_over_body(self, middleware):
        """Test that header credentials are preferred over body."""
        request = MagicMock()
        request.headers = {}

        body_creds = {"access_token": "body_token"}
        encoded = base64.b64encode(json.dumps(body_creds).encode()).decode()
        request.json = AsyncMock(return_value={"tenant_credentials": encoded})

        auth = HTTPAuthorizationCredentials(scheme="Bearer", credentials="header_token")

        credentials, source = await middleware.extract_credentials(request, auth)

        assert credentials.access_token == "header_token"
        assert source == "header"

    @pytest.mark.asyncio
    async def test_invalid_body_credentials_raises_400(self, middleware):
        """Test that invalid body credentials raise 400."""
        request = MagicMock()
        request.headers = {}
        request.json = AsyncMock(
            return_value={"tenant_credentials": "not_valid_base64!!"}
        )

        with pytest.raises(HTTPException) as exc_info:
            await middleware.extract_credentials(request, None)

        assert exc_info.value.status_code == 400
        assert "Invalid credentials format" in exc_info.value.detail


class TestParseBearerToken:
    """Tests for _parse_bearer_token method."""

    @pytest.fixture
    def middleware(self):
        return AuthHeaderMiddleware()

    def test_simple_token(self, middleware):
        """Test parsing a simple access token."""
        creds = middleware._parse_bearer_token("simple_token")

        assert creds.access_token == "simple_token"
        assert creds.refresh_token is None

    def test_base64_treated_as_simple_token(self, middleware):
        """Bearer tokens are always treated as simple tokens (no base64 decoding)."""
        full_creds = {"access_token": "inner_token"}
        encoded = base64.b64encode(json.dumps(full_creds).encode()).decode()

        creds = middleware._parse_bearer_token(encoded)

        assert creds.access_token == encoded


class TestParseCredentialBundle:
    """Tests for _parse_credential_bundle method."""

    @pytest.fixture
    def middleware(self):
        return AuthHeaderMiddleware()

    def test_full_credential_bundle(self, middleware):
        """Test parsing base64-encoded full credentials."""
        full_creds = {
            "access_token": "access123",
            "refresh_token": "refresh456",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "client.apps.googleusercontent.com",
            "provider": "google",
        }
        encoded = base64.b64encode(json.dumps(full_creds).encode()).decode()

        creds = middleware._parse_credential_bundle(encoded)

        assert creds.access_token == "access123"
        assert creds.refresh_token == "refresh456"
        assert creds.token_uri == "https://oauth2.googleapis.com/token"
        assert creds.client_id == "client.apps.googleusercontent.com"

    def test_iso_format_expires_at(self, middleware):
        """Test parsing ISO format expires_at."""
        expires_iso = "2024-12-31T23:59:59Z"
        full_creds = {
            "access_token": "token",
            "expires_at": expires_iso,
        }
        encoded = base64.b64encode(json.dumps(full_creds).encode()).decode()

        creds = middleware._parse_credential_bundle(encoded)

        assert creds.expires_at is not None
        assert creds.expires_at.year == 2024
        assert creds.expires_at.month == 12
        assert creds.expires_at.day == 31

    def test_invalid_base64_raises_400(self, middleware):
        """Test that invalid base64 raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            middleware._parse_credential_bundle("not-valid-base64!!")

        assert exc_info.value.status_code == 400

    def test_invalid_json_raises_400(self, middleware):
        """Test that valid base64 but invalid JSON raises 400."""
        encoded = base64.b64encode(b"not json").decode()

        with pytest.raises(HTTPException) as exc_info:
            middleware._parse_credential_bundle(encoded)

        assert exc_info.value.status_code == 400


class TestParseBodyCredentials:
    """Tests for _parse_body_credentials method."""

    @pytest.fixture
    def middleware(self):
        return AuthHeaderMiddleware()

    def test_valid_body_credentials(self, middleware):
        """Test parsing valid body credentials."""
        body_creds = {
            "access_token": "access",
            "refresh_token": "refresh",
            "provider": "google",
        }
        encoded = base64.b64encode(json.dumps(body_creds).encode()).decode()

        creds = middleware._parse_body_credentials(encoded)

        assert creds.access_token == "access"
        assert creds.refresh_token == "refresh"
        assert creds.provider == "google"
        # Should default to Google token URI
        assert creds.token_uri == "https://oauth2.googleapis.com/token"

    def test_invalid_base64_raises(self, middleware):
        """Test that invalid base64 raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            middleware._parse_body_credentials("not-valid-base64!!")

        assert exc_info.value.status_code == 400

    def test_invalid_json_raises(self, middleware):
        """Test that valid base64 but invalid JSON raises."""
        encoded = base64.b64encode(b"not json").decode()

        with pytest.raises(HTTPException) as exc_info:
            middleware._parse_body_credentials(encoded)

        assert exc_info.value.status_code == 400
