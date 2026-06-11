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
        """Test that None is returned when token verification raises ValueError."""
        # Arrange
        with patch(
            "src.kene_api.auth.dependencies.verify_id_token",
            side_effect=ValueError("Invalid token: id token has expired"),
        ):
            # Act
            result = await get_current_user_optional(
                mock_credentials, mock_firestore_service
            )

            # Assert
            assert result is None

    @pytest.mark.asyncio
    async def test_propagates_non_auth_errors(
        self, mock_credentials, mock_firestore_service, mock_firestore_client
    ):
        """Non-auth errors (e.g. Firestore outage) are NOT swallowed."""
        # Arrange: token verifies OK but Firestore client raises
        decoded_token = {"uid": "user_xyz", "email": "user@example.com"}
        mock_firestore_service.get_client.side_effect = RuntimeError("Firestore unavailable")

        with patch(
            "src.kene_api.auth.dependencies.verify_id_token",
            return_value=decoded_token,
        ):
            # Act + Assert: RuntimeError propagates instead of returning None
            with pytest.raises(RuntimeError, match="Firestore unavailable"):
                await get_current_user_optional(
                    mock_credentials, mock_firestore_service
                )

    @pytest.mark.asyncio
    async def test_returns_none_when_no_credentials(self, mock_firestore_service):
        """Test that None is returned when no credentials provided."""
        # Act
        result = await get_current_user_optional(None, mock_firestore_service)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_mixed_permission_structures_uses_new_structure(
        self,
        mock_credentials,
        mock_firestore_service,
        mock_firestore_client,
        mock_user_doc,
        caplog,
    ):
        """Verify users with both old and new structures use account_permissions (new) only.

        This tests the edge case during migration where a user might have both:
        - Old: permissions.accounts
        - New: permissions.account_permissions

        Expected behavior: Use new structure, ignore old, log warning.
        """
        # Arrange: User with BOTH old and new permission structures
        user_data = {
            "permissions": {
                "accounts": {
                    "old-account-1": "edit",
                    "old-account-2": "admin",
                },  # Old structure
                "account_permissions": {
                    "new-account-1": "view",
                    "new-account-2": "edit",
                },  # New structure
                "organizations": {"org_123": "view"},
            }
        }
        mock_user_doc.to_dict.return_value = user_data
        mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_user_doc
        mock_firestore_service.get_client.return_value = mock_firestore_client

        decoded_token = {
            "uid": "mixed_user_456",
            "email": "mixed@example.com",
        }

        with patch(
            "src.kene_api.auth.dependencies.verify_id_token", return_value=decoded_token
        ):
            # Act
            result = await get_current_user_optional(
                mock_credentials, mock_firestore_service
            )

            # Assert: Only NEW structure is used
            assert result is not None
            assert result.account_permissions == {
                "new-account-1": "view",
                "new-account-2": "edit",
            }

            # Assert: OLD structure is NOT used
            assert "old-account-1" not in result.account_permissions
            assert "old-account-2" not in result.account_permissions

            # Assert: Organization permissions loaded correctly
            assert result.organization_permissions == {"org_123": "view"}

            # Assert: Warning logged about old structure
            assert any(
                "deprecated 'permissions.accounts' field" in record.message
                for record in caplog.records
            ), "Should log warning about deprecated field"

    @pytest.mark.asyncio
    async def test_old_structure_only_gets_migrated_prompt(
        self,
        mock_credentials,
        mock_firestore_service,
        mock_firestore_client,
        mock_user_doc,
        caplog,
    ):
        """Verify users with ONLY old structure are detected and warned about.

        This catches cases where migration hasn't been run yet.
        """
        # Arrange: User with ONLY old structure (no account_permissions)
        user_data = {
            "permissions": {
                "accounts": {"legacy-account": "admin"},  # Old structure only
                "organizations": {},
            }
        }
        mock_user_doc.to_dict.return_value = user_data
        mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_user_doc
        mock_firestore_service.get_client.return_value = mock_firestore_client

        decoded_token = {
            "uid": "legacy_user_789",
            "email": "legacy@example.com",
        }

        with patch(
            "src.kene_api.auth.dependencies.verify_id_token", return_value=decoded_token
        ):
            # Act
            result = await get_current_user_optional(
                mock_credentials, mock_firestore_service
            )

            # Assert: User context created (doesn't crash)
            assert result is not None

            # Assert: Gets empty account_permissions (old structure ignored)
            assert result.account_permissions == {}

            # Assert: Error logged about missing migration
            assert any(
                "deprecated 'permissions.accounts' field" in record.message
                and "Migration script must be run" in record.message
                for record in caplog.records
            ), "Should log error prompting migration"
