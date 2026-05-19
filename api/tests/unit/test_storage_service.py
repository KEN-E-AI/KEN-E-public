"""Unit tests for StorageService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.kene_api.services.storage_service import StorageService


class TestStorageService:
    """Test StorageService functionality."""

    @pytest.fixture
    def mock_storage_client(self):
        """Mock Google Cloud Storage client."""
        with patch(
            "src.kene_api.services.storage_service.storage.Client"
        ) as mock_client:
            yield mock_client

    @pytest.fixture
    def storage_service(self, mock_storage_client):
        """Create StorageService instance with mocked client."""
        with patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
            service = StorageService()
            return service

    @pytest.mark.asyncio
    async def test_ensure_account_folder_creates_placeholder(
        self, storage_service, mock_storage_client
    ):
        """Test that ensure_account_folder creates a placeholder file."""
        # Setup mocks
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.exists.return_value = False  # Placeholder doesn't exist yet
        mock_bucket.blob.return_value = mock_blob

        mock_storage_client.return_value.get_bucket.return_value = mock_bucket

        # Mock bucket existence
        storage_service.ensure_bucket_exists = AsyncMock(
            return_value=("test-bucket", "us-central1")
        )

        # Test
        result = await storage_service.ensure_account_folder("test-account", "US")

        # Assertions
        assert result is True
        mock_bucket.blob.assert_called_once_with("accounts/test-account/.placeholder")
        mock_blob.upload_from_string.assert_called_once()

        # Check that the uploaded content contains expected information
        uploaded_args = mock_blob.upload_from_string.call_args
        assert "test-account" in uploaded_args[0][0]
        assert "Created at:" in uploaded_args[0][0]

    @pytest.mark.asyncio
    async def test_ensure_account_folder_already_exists(
        self, storage_service, mock_storage_client
    ):
        """Test that ensure_account_folder doesn't recreate existing placeholder."""
        # Setup mocks
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True  # Placeholder already exists
        mock_bucket.blob.return_value = mock_blob

        mock_storage_client.return_value.get_bucket.return_value = mock_bucket

        # Mock bucket existence
        storage_service.ensure_bucket_exists = AsyncMock(
            return_value=("test-bucket", "us-central1")
        )

        # Test
        result = await storage_service.ensure_account_folder("test-account", "US")

        # Assertions
        assert result is True
        mock_bucket.blob.assert_called_once_with("accounts/test-account/.placeholder")
        mock_blob.upload_from_string.assert_not_called()  # Should not upload if already exists

    @pytest.mark.asyncio
    async def test_ensure_account_folder_handles_errors(
        self, storage_service, mock_storage_client
    ):
        """Test that ensure_account_folder handles errors gracefully."""
        # Setup mocks to raise an exception
        mock_storage_client.return_value.get_bucket.side_effect = Exception(
            "Storage error"
        )

        # Mock bucket existence
        storage_service.ensure_bucket_exists = AsyncMock(
            return_value=("test-bucket", "us-central1")
        )

        # Test
        result = await storage_service.ensure_account_folder("test-account", "US")

        # Should return False on error
        assert result is False

    @pytest.mark.asyncio
    async def test_ensure_account_folder_different_regions(
        self, storage_service, mock_storage_client
    ):
        """Test that ensure_account_folder works with different regions."""
        # Setup mocks
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.exists.return_value = False
        mock_bucket.blob.return_value = mock_blob

        mock_storage_client.return_value.get_bucket.return_value = mock_bucket

        # Mock bucket existence for EU region
        storage_service.ensure_bucket_exists = AsyncMock(
            return_value=("test-bucket-eu", "europe-west1")
        )

        # Test
        result = await storage_service.ensure_account_folder("test-account", "EU")

        # Assertions
        assert result is True
        storage_service.ensure_bucket_exists.assert_called_once_with("EU")
        mock_bucket.blob.assert_called_once_with("accounts/test-account/.placeholder")
