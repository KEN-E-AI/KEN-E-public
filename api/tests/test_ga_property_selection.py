"""
Tests for Google Analytics property selection functionality.
"""

import base64
import json
from unittest.mock import MagicMock, patch

import pytest
from src.kene_api.services.ga_credential_helper import GACredentialHelper


@pytest.fixture
def mock_firestore_db():
    """Mock Firestore database client."""
    return MagicMock()


@pytest.fixture
def ga_helper(mock_firestore_db):
    """Create a GACredentialHelper instance with mocked database."""
    return GACredentialHelper(mock_firestore_db)


@pytest.fixture
def sample_oauth_credentials():
    """Sample OAuth credentials with selected properties."""
    return {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "expires_at": 1234567890,
        "selected_property_ids": ["properties/123456", "properties/789012"],
        "selected_properties": [
            {"property_id": "properties/123456", "display_name": "Test Property 1"},
            {"property_id": "properties/789012", "display_name": "Test Property 2"},
        ],
    }


@pytest.fixture
def sample_single_property_credentials():
    """Sample OAuth credentials with a single selected property."""
    return {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "expires_at": 1234567890,
        "selected_property_ids": ["properties/123456"],
        "selected_properties": [
            {"property_id": "properties/123456", "display_name": "Single Property"}
        ],
    }


@pytest.fixture
def sample_no_property_credentials():
    """Sample OAuth credentials with no selected properties."""
    return {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "expires_at": 1234567890,
        "selected_property_ids": [],
        "selected_properties": [],
    }


class TestGACredentialHelper:
    """Test the GACredentialHelper class."""

    @pytest.mark.asyncio
    async def test_get_oauth_credentials_success(
        self, ga_helper, mock_firestore_db, sample_oauth_credentials
    ):
        """Test successful retrieval of OAuth credentials."""
        # Mock the encryption service
        with patch.object(
            ga_helper.creds_service,
            "get_credentials",
            return_value=sample_oauth_credentials,
        ):
            result = await ga_helper.get_oauth_credentials("test_account_id")

            assert result is not None
            assert result["access_token"] == "test_access_token"
            assert result["refresh_token"] == "test_refresh_token"
            assert len(result["selected_property_ids"]) == 2
            assert result["selected_property_ids"][0] == "properties/123456"

    @pytest.mark.asyncio
    async def test_get_oauth_credentials_not_found(self, ga_helper):
        """Test retrieval when no credentials are found."""
        with patch.object(
            ga_helper.creds_service, "get_credentials", return_value=None
        ):
            result = await ga_helper.get_oauth_credentials("test_account_id")
            assert result is None

    @pytest.mark.asyncio
    async def test_format_for_agent_with_properties(
        self, ga_helper, sample_oauth_credentials
    ):
        """Test formatting credentials for agent with selected properties."""
        formatted = ga_helper.format_for_agent(
            sample_oauth_credentials, "test_account_id"
        )

        # Decode the base64 result
        decoded = json.loads(base64.b64decode(formatted).decode())

        assert decoded["access_token"] == "test_access_token"
        assert decoded["refresh_token"] == "test_refresh_token"
        assert decoded["tenant_id"] == "test_account_id"
        assert len(decoded["selected_property_ids"]) == 2
        assert decoded["selected_property_ids"][0] == "properties/123456"
        assert len(decoded["selected_properties"]) == 2
        assert decoded["selected_properties"][0]["display_name"] == "Test Property 1"

    @pytest.mark.asyncio
    async def test_format_for_agent_single_property(
        self, ga_helper, sample_single_property_credentials
    ):
        """Test formatting credentials with a single selected property."""
        formatted = ga_helper.format_for_agent(
            sample_single_property_credentials, "test_account_id"
        )

        # Decode the base64 result
        decoded = json.loads(base64.b64decode(formatted).decode())

        assert len(decoded["selected_property_ids"]) == 1
        assert decoded["selected_property_ids"][0] == "properties/123456"
        assert decoded["selected_properties"][0]["display_name"] == "Single Property"

    @pytest.mark.asyncio
    async def test_format_for_agent_no_properties(
        self, ga_helper, sample_no_property_credentials
    ):
        """Test formatting credentials with no selected properties."""
        formatted = ga_helper.format_for_agent(
            sample_no_property_credentials, "test_account_id"
        )

        # Decode the base64 result
        decoded = json.loads(base64.b64decode(formatted).decode())

        assert decoded["selected_property_ids"] == []
        assert decoded["selected_properties"] == []

    @pytest.mark.asyncio
    async def test_get_and_format_credentials(
        self, ga_helper, sample_oauth_credentials
    ):
        """Test the complete get and format flow."""
        with patch.object(
            ga_helper, "get_oauth_credentials", return_value=sample_oauth_credentials
        ):
            with patch.object(
                ga_helper, "refresh_if_expired", return_value=sample_oauth_credentials
            ):
                result = await ga_helper.get_and_format_credentials("test_account_id")

                assert result is not None
                assert result["tenant_id"] == "test_account_id"
                assert "tenant_credentials" in result
                assert len(result["selected_property_ids"]) == 2
                assert len(result["selected_properties"]) == 2
