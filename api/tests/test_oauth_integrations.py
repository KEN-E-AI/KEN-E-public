"""Fixed tests for OAuth 2.0 integration endpoints using dependency overrides."""

import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from src.kene_api.auth import UserContext
from src.kene_api.auth.user_context import get_current_user_context
from src.kene_api.firestore import get_firestore_service
from src.kene_api.main import app
from src.kene_api.models.integration_models import (
    IntegrationStatus,
)

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason="Requires Firebase/Firestore emulator — unblocked by DM-84",
)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_user_context():
    """Mock user context."""
    user = Mock()
    user.user_id = "test_user_id"
    user.email = "test@example.com"
    user.is_super_admin = True
    user.account_permissions = {"test_account_id": {"role": "admin"}}
    user.organization_permissions = {}
    user.accessible_accounts = ["test_account_id"]
    user.permissions = {}
    return user


@pytest.fixture
def mock_firestore_service():
    """Mock Firestore service."""
    mock_service = Mock()
    mock_client = Mock()
    mock_service.get_client.return_value = mock_client
    return mock_service


class TestOAuthAuthorization:
    """Test OAuth authorization endpoints."""

    def test_authorize_google_analytics_success(
        self, client, mock_user_context, mock_firestore_service
    ):
        """Test successful Google Analytics OAuth authorization initiation."""
        # Override dependencies
        app.dependency_overrides[get_current_user_context] = lambda: mock_user_context
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        try:
            with patch(
                "src.kene_api.routers.oauth_integrations.GOOGLE_CLIENT_ID",
                "test_client_id",
            ):
                with patch(
                    "src.kene_api.routers.oauth_integrations.GOOGLE_CLIENT_SECRET",
                    "test_secret",
                ):
                    with patch(
                        "src.kene_api.routers.oauth_integrations.get_google_redirect_uri",
                        return_value="http://localhost:8000/api/oauth/callback/google",
                    ):
                        with patch(
                            "src.kene_api.routers.oauth_integrations.OAuthStateService"
                        ) as MockOAuthStateService:
                            mock_oauth_service = Mock()
                            mock_oauth_service.create_state = AsyncMock()
                            MockOAuthStateService.return_value = mock_oauth_service

                            response = client.get(
                                "/api/oauth/authorize/google-analytics",
                                params={"account_id": "test_account_id"},
                            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "auth_url" in data
            assert "message" in data
            assert "test_client_id" in data["auth_url"]
        finally:
            app.dependency_overrides.clear()

    def test_authorize_google_analytics_no_credentials(
        self, client, mock_user_context, mock_firestore_service
    ):
        """Test Google Analytics OAuth when credentials are not configured."""
        app.dependency_overrides[get_current_user_context] = lambda: mock_user_context
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        try:
            with patch("src.kene_api.routers.oauth_integrations.GOOGLE_CLIENT_ID", ""):
                with patch(
                    "src.kene_api.routers.oauth_integrations.GOOGLE_CLIENT_SECRET", ""
                ):
                    response = client.get(
                        "/api/oauth/authorize/google-analytics",
                        params={"account_id": "test_account_id"},
                    )

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "not configured" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_authorize_google_analytics_permission_denied(
        self, client, mock_firestore_service
    ):
        """Test Google Analytics OAuth with insufficient permissions."""
        # A bare Mock() makes user.has_account_access(...) return a truthy
        # Mock, silently bypassing the permission check the test wants to
        # exercise. UserContext implements the method against real data.
        user = UserContext(
            user_id="test_user_id",
            email="test@example.com",
            organization_permissions={},
            account_permissions={"test_account_id": "viewer"},
        )

        app.dependency_overrides[get_current_user_context] = lambda: user
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        try:
            with patch(
                "src.kene_api.routers.oauth_integrations.GOOGLE_CLIENT_ID",
                "test_client_id",
            ):
                with patch(
                    "src.kene_api.routers.oauth_integrations.GOOGLE_CLIENT_SECRET",
                    "test_secret",
                ):
                    response = client.get(
                        "/api/oauth/authorize/google-analytics",
                        params={"account_id": "test_account_id"},
                    )

            assert response.status_code == status.HTTP_403_FORBIDDEN
            assert "permission" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()


class TestOAuthCallback:
    """Test OAuth callback handling."""

    def test_google_oauth_callback_success(self):
        """Test successful OAuth callback handling."""
        from datetime import timezone

        from src.kene_api.models.oauth_models import OAuthState

        # Create client with follow_redirects=False to prevent 404 from redirect
        client = TestClient(app, follow_redirects=False)

        # Mock OAuth state
        mock_oauth_state = OAuthState(
            state_token="test_state",
            user_id="test_user",
            account_id="test_account",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            integration_type="google_analytics",
        )

        try:
            # Mock the OAuth state service
            with patch(
                "src.kene_api.routers.oauth_integrations.OAuthStateService"
            ) as MockOAuthStateService:
                mock_oauth_service = Mock()
                mock_oauth_service.get_state = AsyncMock(return_value=mock_oauth_state)
                mock_oauth_service.delete_state = AsyncMock(return_value=True)
                MockOAuthStateService.return_value = mock_oauth_service

                with patch("httpx.AsyncClient") as MockAsyncClient:
                    # Mock the async client instance
                    mock_client = MockAsyncClient.return_value.__aenter__.return_value

                    # Mock token exchange response
                    mock_token_response = Mock()
                    mock_token_response.status_code = 200
                    mock_token_response.json.return_value = {
                        "access_token": "test_access_token",
                        "refresh_token": "test_refresh_token",
                        "expires_in": 3600,
                        "scope": "test_scope",
                    }
                    mock_client.post = AsyncMock(return_value=mock_token_response)

                    # Mock user info response
                    mock_user_response = Mock()
                    mock_user_response.status_code = 200
                    mock_user_response.json.return_value = {
                        "email": "test@example.com",
                        "id": "12345",
                    }
                    mock_client.get = AsyncMock(return_value=mock_user_response)

                    with patch(
                        "src.kene_api.routers.oauth_integrations.get_firestore_service"
                    ):
                        with patch(
                            "src.kene_api.routers.oauth_integrations.IntegrationCredentialsService"
                        ) as mock_service:
                            mock_service_instance = Mock()
                            mock_service_instance.store_credentials = AsyncMock()
                            mock_service.return_value = mock_service_instance

                            with patch(
                                "src.kene_api.routers.oauth_integrations.get_frontend_url",
                                return_value="http://frontend.example.com",
                            ):
                                with patch(
                                    "src.kene_api.routers.oauth_integrations.get_google_redirect_uri",
                                    return_value="http://localhost:8000/api/oauth/callback/google",
                                ):
                                    response = client.get(
                                        "/api/oauth/callback/google",
                                        params={
                                            "code": "test_auth_code",
                                            "state": "test_state",
                                        },
                                    )

            # Debug output
            if response.status_code != status.HTTP_307_TEMPORARY_REDIRECT:
                print(f"Response status: {response.status_code}")
                print(
                    f"Response body: {response.text if hasattr(response, 'text') else 'No body'}"
                )
                print(f"Response headers: {response.headers}")

            assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
            assert "oauth_success=google_analytics" in response.headers["location"]
        finally:
            pass  # No cleanup needed with mocked service

    def test_google_oauth_callback_preserves_refresh_token_on_reauth(self):
        """Test that re-authorization preserves the existing refresh token when Google omits it."""
        from datetime import timezone

        from src.kene_api.models.oauth_models import OAuthState

        client = TestClient(app, follow_redirects=False)

        mock_oauth_state = OAuthState(
            state_token="test_state",
            user_id="test_user",
            account_id="test_account",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            integration_type="google_analytics",
        )

        with patch(
            "src.kene_api.routers.oauth_integrations.OAuthStateService"
        ) as MockOAuthStateService:
            mock_oauth_service = Mock()
            mock_oauth_service.get_state = AsyncMock(return_value=mock_oauth_state)
            mock_oauth_service.delete_state = AsyncMock(return_value=True)
            MockOAuthStateService.return_value = mock_oauth_service

            with patch("httpx.AsyncClient") as MockAsyncClient:
                mock_client = MockAsyncClient.return_value.__aenter__.return_value

                # Google re-auth response: no refresh_token
                mock_token_response = Mock()
                mock_token_response.status_code = 200
                mock_token_response.json.return_value = {
                    "access_token": "new_access_token",
                    "expires_in": 3600,
                    "scope": "test_scope",
                }
                mock_client.post = AsyncMock(return_value=mock_token_response)

                mock_user_response = Mock()
                mock_user_response.status_code = 200
                mock_user_response.json.return_value = {
                    "email": "test@example.com",
                    "id": "12345",
                }
                mock_client.get = AsyncMock(return_value=mock_user_response)

                with patch(
                    "src.kene_api.routers.oauth_integrations.get_firestore_service"
                ):
                    with patch(
                        "src.kene_api.routers.oauth_integrations.IntegrationCredentialsService"
                    ) as mock_service:
                        mock_service_instance = Mock()
                        # Existing credentials with a valid refresh token
                        mock_service_instance.get_credentials = AsyncMock(
                            return_value={
                                "access_token": "old_access_token",
                                "refresh_token": "existing_refresh_token",
                            }
                        )
                        mock_service_instance.store_credentials = AsyncMock()
                        mock_service.return_value = mock_service_instance

                        with patch(
                            "src.kene_api.routers.oauth_integrations.get_frontend_url",
                            return_value="http://frontend.example.com",
                        ):
                            with patch(
                                "src.kene_api.routers.oauth_integrations.get_google_redirect_uri",
                                return_value="http://localhost:8000/api/oauth/callback/google",
                            ):
                                response = client.get(
                                    "/api/oauth/callback/google",
                                    params={
                                        "code": "test_auth_code",
                                        "state": "test_state",
                                    },
                                )

                        assert (
                            response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
                        )

                        # Verify stored credentials preserved the existing refresh token
                        stored_creds = mock_service_instance.store_credentials.call_args
                        assert (
                            stored_creds.kwargs["credentials"]["refresh_token"]
                            == "existing_refresh_token"
                        )
                        assert (
                            stored_creds.kwargs["credentials"]["access_token"]
                            == "new_access_token"
                        )

    def test_google_oauth_callback_invalid_state(self, client):
        """Test OAuth callback with invalid state token."""
        # Create client with follow_redirects=False to handle redirect response
        client = TestClient(app, follow_redirects=False)

        with patch(
            "src.kene_api.routers.oauth_integrations.OAuthStateService"
        ) as MockOAuthStateService:
            mock_oauth_service = Mock()
            mock_oauth_service.get_state = AsyncMock(return_value=None)
            MockOAuthStateService.return_value = mock_oauth_service

            with patch(
                "src.kene_api.routers.oauth_integrations.get_frontend_url",
                return_value="http://frontend.example.com",
            ):
                response = client.get(
                    "/api/oauth/callback/google",
                    params={
                        "code": "test_auth_code",
                        "state": "invalid_state",
                    },
                )

        assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
        assert "oauth_error=state_expired" in response.headers["location"]


class TestTokenRefresh:
    """Test token refresh functionality."""

    def test_refresh_google_analytics_token_success(
        self, client, mock_user_context, mock_firestore_service
    ):
        """Test successful token refresh."""
        app.dependency_overrides[get_current_user_context] = lambda: mock_user_context
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        try:
            with patch(
                "src.kene_api.routers.oauth_integrations.IntegrationCredentialsService"
            ) as mock_service:
                mock_service_instance = Mock()
                mock_service_instance.get_credentials = AsyncMock(
                    return_value={
                        "refresh_token": "test_refresh_token",
                        "access_token": "old_access_token",
                    }
                )
                mock_service_instance.update_credentials = AsyncMock()
                mock_service.return_value = mock_service_instance

                with patch("httpx.AsyncClient") as MockAsyncClient:
                    mock_client = MockAsyncClient.return_value.__aenter__.return_value

                    # Mock refresh response
                    mock_refresh_response = Mock()
                    mock_refresh_response.status_code = 200
                    mock_refresh_response.json.return_value = {
                        "access_token": "new_access_token",
                        "expires_in": 3600,
                    }
                    mock_client.post = AsyncMock(return_value=mock_refresh_response)

                    response = client.post(
                        "/api/oauth/refresh/test_account_id/google-analytics",
                    )

            assert response.status_code == status.HTTP_200_OK
            assert "refreshed successfully" in response.json()["message"].lower()
        finally:
            app.dependency_overrides.clear()


class TestDisconnect:
    """Test disconnection functionality."""

    def test_disconnect_google_analytics_success(
        self, client, mock_user_context, mock_firestore_service
    ):
        """Test successful Google Analytics disconnection."""
        app.dependency_overrides[get_current_user_context] = lambda: mock_user_context
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        try:
            with patch(
                "src.kene_api.routers.oauth_integrations.IntegrationCredentialsService"
            ) as mock_service:
                mock_service_instance = Mock()
                mock_service_instance.delete_credentials = AsyncMock()
                mock_service.return_value = mock_service_instance

                response = client.delete(
                    "/api/oauth/disconnect/test_account_id/google-analytics",
                )

            assert response.status_code == status.HTTP_200_OK
            assert "disconnected successfully" in response.json()["message"].lower()
        finally:
            app.dependency_overrides.clear()


class TestStatus:
    """Test status checking functionality."""

    def test_get_google_analytics_status_configured(
        self, client, mock_user_context, mock_firestore_service
    ):
        """Test checking status of configured Google Analytics integration."""
        app.dependency_overrides[get_current_user_context] = lambda: mock_user_context
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        try:
            with patch(
                "src.kene_api.routers.oauth_integrations.IntegrationCredentialsService"
            ) as mock_service:
                mock_service_instance = Mock()
                mock_service_instance.get_credentials = AsyncMock(
                    return_value={
                        "access_token": "test_token",
                        "expires_at": (datetime.now() + timedelta(hours=1)).timestamp(),
                        "user_email": "test@example.com",
                    }
                )
                mock_service.return_value = mock_service_instance

                response = client.get(
                    "/api/oauth/status/test_account_id/google-analytics",
                )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == IntegrationStatus.CONFIGURED.value
            assert data["user_email"] == "test@example.com"
        finally:
            app.dependency_overrides.clear()

    def test_get_google_analytics_status_not_configured(
        self, client, mock_user_context, mock_firestore_service
    ):
        """Test checking status of non-configured Google Analytics integration."""
        app.dependency_overrides[get_current_user_context] = lambda: mock_user_context
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        try:
            with patch(
                "src.kene_api.routers.oauth_integrations.IntegrationCredentialsService"
            ) as mock_service:
                mock_service_instance = Mock()
                mock_service_instance.get_credentials = AsyncMock(return_value=None)
                mock_service.return_value = mock_service_instance

                response = client.get(
                    "/api/oauth/status/test_account_id/google-analytics",
                )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == IntegrationStatus.NOT_CONFIGURED.value
        finally:
            app.dependency_overrides.clear()

    def test_get_google_analytics_status_configured_despite_expired_access_token(
        self, client, mock_user_context, mock_firestore_service
    ):
        """Test that expired access token with valid refresh token still shows CONFIGURED."""
        app.dependency_overrides[get_current_user_context] = lambda: mock_user_context
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        try:
            with patch(
                "src.kene_api.routers.oauth_integrations.IntegrationCredentialsService"
            ) as mock_service:
                mock_service_instance = Mock()
                mock_service_instance.get_credentials = AsyncMock(
                    return_value={
                        "access_token": "test_token",
                        "refresh_token": "valid_refresh_token",
                        "expires_at": (
                            datetime.now() - timedelta(hours=1)
                        ).timestamp(),  # Access token expired
                        "user_email": "test@example.com",
                    }
                )
                mock_service.return_value = mock_service_instance

                response = client.get(
                    "/api/oauth/status/test_account_id/google-analytics",
                )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == IntegrationStatus.CONFIGURED.value
            assert data["error_message"] is None
        finally:
            app.dependency_overrides.clear()

    def test_get_google_analytics_status_expired(
        self, client, mock_user_context, mock_firestore_service
    ):
        """Test checking status of expired Google Analytics integration when no refresh token."""
        app.dependency_overrides[get_current_user_context] = lambda: mock_user_context
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        try:
            with patch(
                "src.kene_api.routers.oauth_integrations.IntegrationCredentialsService"
            ) as mock_service:
                mock_service_instance = Mock()
                mock_service_instance.get_credentials = AsyncMock(
                    return_value={
                        "access_token": "test_token",
                        "expires_at": (
                            datetime.now() - timedelta(hours=1)
                        ).timestamp(),  # Expired
                        "user_email": "test@example.com",
                    }
                )
                mock_service.return_value = mock_service_instance

                response = client.get(
                    "/api/oauth/status/test_account_id/google-analytics",
                )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == IntegrationStatus.EXPIRED.value
            assert "expired" in data["error_message"].lower()
        finally:
            app.dependency_overrides.clear()
