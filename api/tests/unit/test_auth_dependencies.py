"""Unit tests for authentication dependencies."""

from unittest.mock import MagicMock, patch

import pytest
from src.kene_api.auth.dependencies import get_current_user_optional


@pytest.fixture
def mock_credentials():
    """Create mock HTTP Bearer credentials."""
    credentials = MagicMock()
    credentials.credentials = "mock_token_12345"
    return credentials


@pytest.fixture
def mock_firestore_service():
    """Create mock Firestore service."""
    service = MagicMock()
    return service


@pytest.fixture
def mock_firestore_client():
    """Create mock Firestore client with collection/document structure."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_user_doc():
    """Create mock user document."""
    doc = MagicMock()
    doc.exists = True
    return doc


class TestGetCurrentUserOptional:
    """Test get_current_user_optional function."""

    @pytest.mark.asyncio
    async def test_handles_only_new_permissions_structure(
        self,
        mock_credentials,
        mock_firestore_service,
        mock_firestore_client,
        mock_user_doc,
    ):
        """Test with only new permissions.account_permissions structure."""
        # Arrange
        user_data = {
            "permissions": {
                "account_permissions": {
                    "acc_new_1": "edit",
                    "acc_new_2": "view",
                },
            }
        }
        mock_user_doc.to_dict.return_value = user_data
        mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_user_doc
        mock_firestore_service.get_client.return_value = mock_firestore_client

        decoded_token = {
            "uid": "user_123",
            "email": "test@example.com",
        }

        with patch(
            "src.kene_api.auth.dependencies.verify_id_token", return_value=decoded_token
        ):
            # Act
            result = await get_current_user_optional(
                mock_credentials, mock_firestore_service
            )

            # Assert
            assert result is not None
            assert result.account_permissions["acc_new_1"] == "edit"
            assert result.account_permissions["acc_new_2"] == "view"

    @pytest.mark.asyncio
    async def test_handles_no_permissions(
        self,
        mock_credentials,
        mock_firestore_service,
        mock_firestore_client,
        mock_user_doc,
    ):
        """Test user with no permissions at all."""
        # Arrange
        user_data = {"permissions": {}}
        mock_user_doc.to_dict.return_value = user_data
        mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_user_doc
        mock_firestore_service.get_client.return_value = mock_firestore_client

        decoded_token = {
            "uid": "user_123",
            "email": "test@example.com",
        }

        with patch(
            "src.kene_api.auth.dependencies.verify_id_token", return_value=decoded_token
        ):
            # Act
            result = await get_current_user_optional(
                mock_credentials, mock_firestore_service
            )

            # Assert
            assert result is not None
            assert result.account_permissions == {}
            assert result.organization_permissions == {}

    @pytest.mark.asyncio
    async def test_returns_none_on_invalid_token(
        self, mock_credentials, mock_firestore_service
    ):
        """Test that None is returned when token verification fails."""
        # Arrange
        with patch(
            "src.kene_api.auth.dependencies.verify_id_token",
            side_effect=Exception("Invalid token"),
        ):
            # Act
            result = await get_current_user_optional(
                mock_credentials, mock_firestore_service
            )

            # Assert
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_credentials(self, mock_firestore_service):
        """Test that None is returned when no credentials provided."""
        # Act
        result = await get_current_user_optional(None, mock_firestore_service)

        # Assert
        assert result is None
