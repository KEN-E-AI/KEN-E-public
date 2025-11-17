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
    async def test_merges_old_and_new_account_permissions(
        self,
        mock_credentials,
        mock_firestore_service,
        mock_firestore_client,
        mock_user_doc,
    ):
        """Test that both old and new permission structures are merged correctly."""
        # Arrange
        user_data = {
            "permissions": {
                "accounts": {
                    "acc_old_1": "admin",
                    "acc_old_2": "view",
                },
                "account_permissions": {
                    "acc_new_1": "edit",
                    "acc_new_2": "view",
                },
                "organizations": {
                    "org_123": "view",
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
            assert result.user_id == "user_123"
            assert result.email == "test@example.com"
            # Verify all 4 accounts are present
            assert len(result.account_permissions) == 4
            # Verify old accounts
            assert result.account_permissions["acc_old_1"] == "admin"
            assert result.account_permissions["acc_old_2"] == "view"
            # Verify new accounts
            assert result.account_permissions["acc_new_1"] == "edit"
            assert result.account_permissions["acc_new_2"] == "view"
            # Verify org permissions
            assert result.organization_permissions["org_123"] == "view"

    @pytest.mark.asyncio
    async def test_new_permissions_override_old_when_duplicate(
        self,
        mock_credentials,
        mock_firestore_service,
        mock_firestore_client,
        mock_user_doc,
    ):
        """Test that new account_permissions take precedence over old accounts when same account ID exists in both."""
        # Arrange
        user_data = {
            "permissions": {
                "accounts": {
                    "acc_duplicate": "view",  # Old: view
                    "acc_old_only": "admin",
                },
                "account_permissions": {
                    "acc_duplicate": "edit",  # New: edit (should win)
                    "acc_new_only": "view",
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
            # New permission should override old
            assert result.account_permissions["acc_duplicate"] == "edit"
            assert result.account_permissions["acc_old_only"] == "admin"
            assert result.account_permissions["acc_new_only"] == "view"

    @pytest.mark.asyncio
    async def test_handles_only_old_permissions_structure(
        self,
        mock_credentials,
        mock_firestore_service,
        mock_firestore_client,
        mock_user_doc,
    ):
        """Test backward compatibility with only old permissions.accounts structure."""
        # Arrange
        user_data = {
            "permissions": {
                "accounts": {
                    "acc_old_1": "admin",
                    "acc_old_2": "view",
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
            assert result.account_permissions["acc_old_1"] == "admin"
            assert result.account_permissions["acc_old_2"] == "view"

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
