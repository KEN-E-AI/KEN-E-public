"""Tests for reCAPTCHA service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from src.kene_api.recaptcha import RecaptchaService, RecaptchaVerificationResult


@pytest.fixture
def recaptcha_service():
    """Create a reCAPTCHA service instance for testing."""
    with patch("src.kene_api.recaptcha.settings") as mock_settings:
        mock_settings.RECAPTCHA_SECRET_KEY = "test_secret_key"
        service = RecaptchaService()
        return service


@pytest.mark.asyncio
async def test_verify_token_success(recaptcha_service):
    """Test successful reCAPTCHA verification."""
    mock_response = {
        "success": True,
        "challenge_ts": "2024-01-01T00:00:00Z",
        "hostname": "example.com",
    }

    with patch("httpx.AsyncClient") as mock_client:
        # Create a mock instance that will be returned by the context manager
        mock_instance = MagicMock()
        mock_client.return_value.__aenter__.return_value = mock_instance
        
        # Create a mock response
        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()
        
        # Configure the post method to return our mock response
        mock_instance.post = AsyncMock(return_value=mock_response_obj)

        result = await recaptcha_service.verify_token("valid_token", "127.0.0.1")

        assert result.success is True
        assert result.challenge_ts == "2024-01-01T00:00:00Z"
        assert result.hostname == "example.com"
        assert result.error_codes is None

        # Verify the API was called correctly
        mock_instance.post.assert_called_once_with(
            "https://www.google.com/recaptcha/api/siteverify",
            data={
                "secret": "test_secret_key",
                "response": "valid_token",
                "remoteip": "127.0.0.1"
            }
        )


@pytest.mark.asyncio
async def test_verify_token_failure(recaptcha_service):
    """Test failed reCAPTCHA verification."""
    mock_response = {
        "success": False,
        "error-codes": ["invalid-input-response"],
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value.__aenter__.return_value = mock_instance
        
        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()
        
        mock_instance.post = AsyncMock(return_value=mock_response_obj)

        result = await recaptcha_service.verify_token("invalid_token")

        assert result.success is False
        assert result.error_codes == ["invalid-input-response"]


@pytest.mark.asyncio
async def test_verify_token_no_secret_key():
    """Test verification when secret key is not configured."""
    with patch("src.kene_api.recaptcha.settings") as mock_settings:
        mock_settings.RECAPTCHA_SECRET_KEY = ""
        service = RecaptchaService()

        result = await service.verify_token("any_token")

        assert result.success is False
        assert result.error_codes == ["missing-secret-key"]


@pytest.mark.asyncio
async def test_verify_token_empty_token(recaptcha_service):
    """Test verification with empty token."""
    result = await recaptcha_service.verify_token("")

    assert result.success is False
    assert result.error_codes == ["missing-input-response"]


@pytest.mark.asyncio
async def test_verify_token_timeout(recaptcha_service):
    """Test verification timeout handling."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value.__aenter__.return_value = mock_instance
        
        # Configure post to raise TimeoutException
        mock_instance.post = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))

        result = await recaptcha_service.verify_token("token")

        assert result.success is False
        assert result.error_codes == ["timeout-error"]


@pytest.mark.asyncio
async def test_verify_token_http_error(recaptcha_service):
    """Test HTTP error handling."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value.__aenter__.return_value = mock_instance
        
        # Configure post to raise HTTPError
        mock_instance.post = AsyncMock(side_effect=httpx.HTTPError("HTTP Error"))

        result = await recaptcha_service.verify_token("token")

        assert result.success is False
        assert result.error_codes == ["http-error"]


@pytest.mark.asyncio
async def test_verify_token_unexpected_error(recaptcha_service):
    """Test unexpected error handling."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value.__aenter__.return_value = mock_instance
        
        # Configure post to raise generic Exception
        mock_instance.post = AsyncMock(side_effect=Exception("Unexpected error"))

        result = await recaptcha_service.verify_token("token")

        assert result.success is False
        assert result.error_codes == ["internal-error"]