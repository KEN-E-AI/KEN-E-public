"""Integration tests for Firestore with Secret Manager authentication."""

import json
import os
import tempfile
from unittest.mock import Mock, patch

from google.auth import credentials
from src.kene_api.firestore import FirestoreService


class TestFirestoreSecretManagerIntegration:
    """Integration tests for Firestore service with Secret Manager authentication."""

    def setup_method(self):
        """Set up test fixtures."""
        self.firestore_service = FirestoreService()

        # Sample service account data for testing
        self.test_service_account_data = {
            "type": "service_account",
            "project_id": "test-project-123",
            "private_key_id": "test-key-id",
            "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC...\n-----END PRIVATE KEY-----\n",
            "client_email": "test-service@test-project-123.iam.gserviceaccount.com",
            "client_id": "123456789012345678901",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/test-service%40test-project-123.iam.gserviceaccount.com",
        }

    @patch(
        "src.kene_api.firestore.service_account.Credentials.from_service_account_info"
    )
    @patch("src.kene_api.firestore.firestore.Client")
    @patch("src.kene_api.firestore.get_env_or_secret")
    def test_initialize_with_secret_manager_service_account(
        self, mock_get_secret_json, mock_firestore_client, mock_from_info
    ):
        """Test Firestore initialization with service account from Secret Manager."""
        # Arrange
        # get_env_or_secret returns the raw JSON string; firestore.py parses it
        # with json.loads before calling from_service_account_info.
        mock_get_secret_json.return_value = json.dumps(self.test_service_account_data)
        mock_credentials = Mock(spec=credentials.Credentials)
        mock_from_info.return_value = mock_credentials
        mock_client_instance = Mock()
        mock_firestore_client.return_value = mock_client_instance

        secret_path = "projects/123/secrets/service-account-json/versions/latest"

        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLOUD_PROJECT_ID": "test-project-123",
                "FIRESTORE_DATABASE_ID": "(default)",
                "GOOGLE_APPLICATION_CREDENTIALS": secret_path,
                "USE_APPLICATION_DEFAULT_CREDENTIALS": "false",
            },
        ):
            # Act
            result = self.firestore_service.initialize()

            # Assert
            assert result is True
            assert self.firestore_service._initialized is True
            assert self.firestore_service._db is mock_client_instance

            mock_get_secret_json.assert_called_once_with(
                "GOOGLE_APPLICATION_CREDENTIALS"
            )
            mock_from_info.assert_called_once_with(self.test_service_account_data)
            mock_firestore_client.assert_called_once_with(
                project="test-project-123",
                database="(default)",
                credentials=mock_credentials,
            )

    @patch("src.kene_api.firestore.firestore.Client")
    @patch(
        "src.kene_api.firestore.service_account.Credentials.from_service_account_file"
    )
    def test_initialize_with_file_based_credentials(
        self, mock_from_file, mock_firestore_client
    ):
        """Test Firestore initialization with traditional file-based credentials."""
        # Arrange
        mock_credentials = Mock(spec=credentials.Credentials)
        mock_from_file.return_value = mock_credentials
        mock_client_instance = Mock()
        mock_firestore_client.return_value = mock_client_instance

        # Create a temporary service account file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(self.test_service_account_data, f)
            temp_file_path = f.name

        try:
            with patch.dict(
                os.environ,
                {
                    "GOOGLE_CLOUD_PROJECT_ID": "test-project-123",
                    "FIRESTORE_DATABASE_ID": "(default)",
                    "GOOGLE_APPLICATION_CREDENTIALS": temp_file_path,
                    "USE_APPLICATION_DEFAULT_CREDENTIALS": "false",
                },
            ):
                # Act
                result = self.firestore_service.initialize()

                # Assert
                assert result is True
                assert self.firestore_service._initialized is True
                assert self.firestore_service._db is mock_client_instance

                mock_from_file.assert_called_once_with(temp_file_path)
                mock_firestore_client.assert_called_once_with(
                    project="test-project-123",
                    database="(default)",
                    credentials=mock_credentials,
                )
        finally:
            os.unlink(temp_file_path)

    @patch("src.kene_api.firestore.default")
    @patch("src.kene_api.firestore.firestore.Client")
    def test_initialize_with_application_default_credentials(
        self, mock_firestore_client, mock_default
    ):
        """Test Firestore initialization with Application Default Credentials."""
        # Arrange
        mock_credentials = Mock(spec=credentials.Credentials)
        mock_default.return_value = (mock_credentials, "detected-project")
        mock_client_instance = Mock()
        mock_firestore_client.return_value = mock_client_instance

        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLOUD_PROJECT_ID": "test-project-123",
                "FIRESTORE_DATABASE_ID": "(default)",
                "USE_APPLICATION_DEFAULT_CREDENTIALS": "true",
            },
        ):
            # Act
            result = self.firestore_service.initialize()

            # Assert
            assert result is True
            assert self.firestore_service._initialized is True
            assert self.firestore_service._db is mock_client_instance

            mock_default.assert_called_once()
            mock_firestore_client.assert_called_once_with(
                project="test-project-123",
                database="(default)",
                credentials=mock_credentials,
            )

    @patch("src.kene_api.firestore.get_env_or_secret")
    def test_initialize_secret_manager_failure_with_fallback(
        self, mock_get_secret_json
    ):
        """Test Firestore initialization when Secret Manager fails but ADC works."""
        # Arrange
        mock_get_secret_json.side_effect = Exception("Secret Manager access denied")

        secret_path = "projects/123/secrets/service-account-json/versions/latest"

        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLOUD_PROJECT_ID": "test-project-123",
                "FIRESTORE_DATABASE_ID": "(default)",
                "GOOGLE_APPLICATION_CREDENTIALS": secret_path,
                "USE_APPLICATION_DEFAULT_CREDENTIALS": "false",
            },
        ):
            # Act
            result = self.firestore_service.initialize()

            # Assert
            assert result is False
            assert self.firestore_service._initialized is False

    @patch("src.kene_api.firestore.get_env_or_secret")
    def test_initialize_secret_manager_returns_none(self, mock_get_secret_json):
        """Test Firestore initialization when Secret Manager returns None."""
        # Arrange
        mock_get_secret_json.return_value = None

        secret_path = "projects/123/secrets/service-account-json/versions/latest"

        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLOUD_PROJECT_ID": "test-project-123",
                "FIRESTORE_DATABASE_ID": "(default)",
                "GOOGLE_APPLICATION_CREDENTIALS": secret_path,
                "USE_APPLICATION_DEFAULT_CREDENTIALS": "false",
            },
        ):
            # Act
            result = self.firestore_service.initialize()

            # Assert
            assert result is False
            assert self.firestore_service._initialized is False

    def test_initialize_missing_project_id(self):
        """Test Firestore initialization fails with missing project ID."""
        # Arrange
        with patch.dict(os.environ, {}, clear=True):
            # Act
            result = self.firestore_service.initialize()

            # Assert
            assert result is False
            assert self.firestore_service._initialized is False

    @patch(
        "src.kene_api.firestore.service_account.Credentials.from_service_account_info"
    )
    @patch("src.kene_api.firestore.firestore.Client")
    @patch("src.kene_api.firestore.get_env_or_secret")
    def test_health_check_with_secret_manager_auth(
        self, mock_get_secret_json, mock_firestore_client, mock_from_info
    ):
        """Test health check functionality with Secret Manager authentication."""
        # Arrange
        mock_get_secret_json.return_value = json.dumps(self.test_service_account_data)
        mock_credentials = Mock(spec=credentials.Credentials)
        mock_from_info.return_value = mock_credentials
        mock_client_instance = Mock()
        mock_collection = Mock()
        mock_client_instance.collection.return_value = mock_collection
        mock_collection.limit.return_value = mock_collection
        mock_collection.get.return_value = []  # Empty result for health check
        mock_firestore_client.return_value = mock_client_instance

        secret_path = "projects/123/secrets/service-account-json/versions/latest"

        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLOUD_PROJECT_ID": "test-project-123",
                "FIRESTORE_DATABASE_ID": "(default)",
                "GOOGLE_APPLICATION_CREDENTIALS": secret_path,
                "USE_APPLICATION_DEFAULT_CREDENTIALS": "false",
            },
        ):
            # Act
            health_result = self.firestore_service.health_check()

            # Assert
            assert health_result is True
            assert self.firestore_service._initialized is True

            # Verify health check query was made
            mock_client_instance.collection.assert_called_with("health_check")
            mock_collection.limit.assert_called_with(1)
            mock_collection.get.assert_called_once()

    @patch(
        "src.kene_api.firestore.service_account.Credentials.from_service_account_info"
    )
    @patch("src.kene_api.firestore.firestore.Client")
    @patch("src.kene_api.firestore.get_env_or_secret")
    def test_document_operations_with_secret_manager_auth(
        self, mock_get_secret_json, mock_firestore_client, mock_from_info
    ):
        """Test basic document operations with Secret Manager authentication."""
        # Arrange
        mock_get_secret_json.return_value = json.dumps(self.test_service_account_data)
        mock_credentials = Mock(spec=credentials.Credentials)
        mock_from_info.return_value = mock_credentials
        mock_client_instance = Mock()
        mock_collection = Mock()
        mock_doc_ref = Mock()
        mock_doc = Mock()

        mock_client_instance.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_doc_ref
        mock_doc_ref.get.return_value = mock_doc
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"test": "data"}

        mock_firestore_client.return_value = mock_client_instance

        secret_path = "projects/123/secrets/service-account-json/versions/latest"

        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLOUD_PROJECT_ID": "test-project-123",
                "FIRESTORE_DATABASE_ID": "(default)",
                "GOOGLE_APPLICATION_CREDENTIALS": secret_path,
                "USE_APPLICATION_DEFAULT_CREDENTIALS": "false",
            },
        ):
            # Initialize the service
            init_result = self.firestore_service.initialize()
            assert init_result is True

            # Act - Test document retrieval
            result = self.firestore_service.get_document("test_collection", "test_doc")

            # Assert
            assert result == {"test": "data"}
            mock_client_instance.collection.assert_called_with("test_collection")
            mock_collection.document.assert_called_with("test_doc")


class TestFirestoreErrorHandling:
    """Test error handling scenarios for Firestore with Secret Manager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.firestore_service = FirestoreService()

    def test_invalid_json_credentials_format(self):
        """Test handling of invalid JSON credentials format."""
        # Arrange
        secret_path = "projects/123/secrets/service-account-json/versions/latest"

        with (
            patch.dict(
                os.environ,
                {
                    "GOOGLE_CLOUD_PROJECT_ID": "test-project-123",
                    "GOOGLE_APPLICATION_CREDENTIALS": secret_path,
                    "USE_APPLICATION_DEFAULT_CREDENTIALS": "false",
                },
            ),
            patch(
                "src.kene_api.firestore.get_env_or_secret"
            ) as mock_get_secret,
        ):
            # get_env_or_secret returns a raw string; a malformed value
            # makes firestore.py raise on json.loads.
            mock_get_secret.return_value = "{not-valid-json"

            # Act
            result = self.firestore_service.initialize()

            # Assert
            assert result is False

    def test_raw_json_string_in_env_var(self):
        """Test handling of raw JSON string in environment variable."""
        # Arrange - Raw JSON in env var (should trigger error)
        raw_json = '{"type": "service_account", "project_id": "test"}'

        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLOUD_PROJECT_ID": "test-project-123",
                "GOOGLE_APPLICATION_CREDENTIALS": raw_json,
                "USE_APPLICATION_DEFAULT_CREDENTIALS": "false",
            },
        ):
            # Act
            result = self.firestore_service.initialize()

            # Assert
            assert result is False

    @patch(
        "src.kene_api.firestore.service_account.Credentials.from_service_account_info"
    )
    @patch("src.kene_api.firestore.firestore.Client")
    @patch("src.kene_api.firestore.get_env_or_secret")
    def test_firestore_client_initialization_failure(
        self, mock_get_secret_json, mock_firestore_client, mock_from_info
    ):
        """Test handling of Firestore client initialization failure."""
        # Arrange
        mock_get_secret_json.return_value = json.dumps(
            {
                "type": "service_account",
                "project_id": "test-project-123",
                "private_key": "test-key",
            }
        )
        mock_from_info.return_value = Mock(spec=credentials.Credentials)
        mock_firestore_client.side_effect = Exception("Firestore initialization failed")

        secret_path = "projects/123/secrets/service-account-json/versions/latest"

        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLOUD_PROJECT_ID": "test-project-123",
                "GOOGLE_APPLICATION_CREDENTIALS": secret_path,
                "USE_APPLICATION_DEFAULT_CREDENTIALS": "false",
            },
        ):
            # Act
            result = self.firestore_service.initialize()

            # Assert
            assert result is False
            assert self.firestore_service._initialized is False
