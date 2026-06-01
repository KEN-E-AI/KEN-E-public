"""Tests for authentication endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from src.kene_api.main import app
from src.kene_api.rate_limiter import recaptcha_rate_limiter
from src.kene_api.recaptcha import RecaptchaVerificationResult

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_recaptcha_limiter():
    """Clear recaptcha rate-limiter state before/after each test.

    test_auth.py makes real requests to the recaptcha endpoint so the global
    recaptcha_rate_limiter accumulates in-memory state across tests.  Without
    this reset, test_verify_recaptcha_failure (the 2nd test in the file) gets
    429 because the fallback LocalRateLimiter is already at capacity from
    test_verify_recaptcha_success.  Matches the fixture pattern already used
    in test_auth_rate_limiting.py for the same reason.
    """
    recaptcha_rate_limiter.minute_requests.clear()
    recaptcha_rate_limiter.hour_requests.clear()
    yield
    recaptcha_rate_limiter.minute_requests.clear()
    recaptcha_rate_limiter.hour_requests.clear()


@pytest.mark.asyncio
async def test_verify_recaptcha_success():
    """Test successful reCAPTCHA verification endpoint."""
    mock_result = RecaptchaVerificationResult(
        success=True,
        challenge_ts="2024-01-01T00:00:00Z",
        hostname="example.com",
    )

    with patch(
        "src.kene_api.routers.auth.recaptcha_service.verify_token",
        new_callable=AsyncMock,
    ) as mock_verify:
        mock_verify.return_value = mock_result

        response = client.post(
            "/api/v1/auth/verify-recaptcha",
            json={"token": "valid_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "reCAPTCHA verification successful"
        assert data["error_codes"] is None


@pytest.mark.asyncio
async def test_verify_recaptcha_failure():
    """Test failed reCAPTCHA verification endpoint."""
    mock_result = RecaptchaVerificationResult(
        success=False,
        error_codes=["invalid-input-response"],
    )

    with patch(
        "src.kene_api.routers.auth.recaptcha_service.verify_token",
        new_callable=AsyncMock,
    ) as mock_verify:
        mock_verify.return_value = mock_result

        response = client.post(
            "/api/v1/auth/verify-recaptcha",
            json={"token": "invalid_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["message"] == "reCAPTCHA verification failed"
        assert data["error_codes"] == ["invalid-input-response"]


def test_get_recaptcha_site_key_success():
    """Test getting reCAPTCHA site key."""
    with patch("src.kene_api.routers.auth.settings") as mock_settings:
        mock_settings.RECAPTCHA_SITE_KEY = "test_site_key"

        response = client.get("/api/v1/auth/recaptcha-site-key")

        assert response.status_code == 200
        data = response.json()
        assert data["site_key"] == "test_site_key"


def test_get_recaptcha_site_key_not_configured():
    """Test getting reCAPTCHA site key when not configured."""
    with patch("src.kene_api.routers.auth.settings") as mock_settings:
        mock_settings.RECAPTCHA_SITE_KEY = ""

        response = client.get("/api/v1/auth/recaptcha-site-key")

        assert response.status_code == 500
        assert response.json()["detail"] == "reCAPTCHA site key not configured"


def test_verify_recaptcha_missing_token():
    """Test reCAPTCHA verification with missing token."""
    response = client.post(
        "/api/v1/auth/verify-recaptcha",
        json={},
    )

    assert response.status_code == 422  # Validation error
