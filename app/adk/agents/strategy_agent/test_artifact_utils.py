"""
Unit tests for artifact_utils.py
Following T-1 through T-8: Comprehensive testing of extracted functions
"""

import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch
from google.genai.types import Part

from agents.strategy_agent.artifact_utils import (
    parse_gcs_url,
    determine_artifact_bucket,
    create_artifact_from_gcs,
    save_artifact_to_service,
    load_uploaded_documents_as_artifacts,
    UPLOADED_STRATEGY_PREFIX,
)


class TestParseGcsUrl:
    """Test the pure function parse_gcs_url"""

    def test_valid_gcs_url_with_path(self):
        bucket, path = parse_gcs_url("gs://my-bucket/path/to/file.pdf")
        assert bucket == "my-bucket"
        assert path == "path/to/file.pdf"

    def test_valid_gcs_url_root_file(self):
        bucket, path = parse_gcs_url("gs://my-bucket/file.pdf")
        assert bucket == "my-bucket"
        assert path == "file.pdf"

    def test_valid_gcs_url_no_file(self):
        bucket, path = parse_gcs_url("gs://my-bucket/")
        assert bucket == "my-bucket"
        assert path == ""

    def test_invalid_url_format(self):
        bucket, path = parse_gcs_url("https://not-gcs.com/file.pdf")
        assert bucket is None
        assert path is None

    def test_empty_url(self):
        bucket, path = parse_gcs_url("")
        assert bucket is None
        assert path is None

    def test_none_url(self):
        bucket, path = parse_gcs_url(None)
        assert bucket is None
        assert path is None


class TestDetermineArtifactBucket:
    """Test the pure function determine_artifact_bucket"""

    def test_extract_bucket_from_uploaded_docs(self):
        docs = ["gs://custom-bucket/file1.pdf", "gs://other-bucket/file2.pdf"]
        bucket = determine_artifact_bucket(docs)
        assert bucket == "custom-bucket"

    def test_fallback_to_environment_development(self):
        bucket = determine_artifact_bucket([], environment="development")
        assert bucket == "ken-e-development-files-us"

    def test_fallback_to_environment_staging(self):
        bucket = determine_artifact_bucket([], environment="staging")
        assert bucket == "ken-e-staging-files-us"

    def test_fallback_to_environment_production(self):
        bucket = determine_artifact_bucket([], environment="production")
        assert bucket == "ken-e-production-files-us"

    @patch.dict("os.environ", {"ENVIRONMENT": "staging"})
    def test_use_env_var_when_no_environment_provided(self):
        bucket = determine_artifact_bucket([])
        assert bucket == "ken-e-staging-files-us"

    def test_invalid_url_falls_back_to_default(self):
        docs = ["https://not-gcs.com/file.pdf"]
        bucket = determine_artifact_bucket(docs, environment="development")
        assert bucket == "ken-e-development-files-us"


class TestCreateArtifactFromGcs:
    """Test create_artifact_from_gcs with mocked GCS client"""

    def test_successful_download(self):
        # Mock storage client and blob
        mock_client = Mock()
        mock_bucket = Mock()
        mock_blob = Mock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.download_as_bytes.return_value = b"PDF content"
        mock_blob.content_type = "application/pdf"

        artifact, filename = create_artifact_from_gcs(
            mock_client, "test-bucket", "path/to/document.pdf"
        )

        assert artifact is not None
        assert filename == "document.pdf"
        mock_client.bucket.assert_called_once_with("test-bucket")
        mock_bucket.blob.assert_called_once_with("path/to/document.pdf")
        mock_blob.download_as_bytes.assert_called_once()

    def test_download_failure(self):
        # Mock storage client that raises exception
        mock_client = Mock()
        mock_client.bucket.side_effect = Exception("Network error")

        artifact, filename = create_artifact_from_gcs(
            mock_client, "test-bucket", "path/to/document.pdf"
        )

        assert artifact is None
        assert filename == "document.pdf"

    def test_empty_blob_path(self):
        mock_client = Mock()

        artifact, filename = create_artifact_from_gcs(mock_client, "test-bucket", "")

        assert filename == "unknown"


class TestSaveArtifactToService:
    """Test save_artifact_to_service function"""

    def test_successful_save(self):
        mock_service = Mock()
        mock_artifact = Mock(spec=Part)

        # Create an async mock for save_artifact method
        async def mock_save_artifact(**kwargs):
            return 1

        mock_service.save_artifact = MagicMock(side_effect=mock_save_artifact)

        result = save_artifact_to_service(
            mock_service,
            mock_artifact,
            "test.pdf",
            "user_123",
            "session_456",
            app_name="test_app",
        )

        assert result is True
        # Verify save_artifact was called with correct params
        mock_service.save_artifact.assert_called_once()
        call_kwargs = mock_service.save_artifact.call_args[1]
        assert call_kwargs["app_name"] == "test_app"
        assert call_kwargs["user_id"] == "user_123"
        assert call_kwargs["session_id"] == "session_456"
        assert call_kwargs["filename"] == f"{UPLOADED_STRATEGY_PREFIX}test.pdf"
        assert call_kwargs["artifact"] == mock_artifact

    @patch("asyncio.run")
    def test_save_failure(self, mock_asyncio_run):
        mock_service = Mock()
        mock_artifact = Mock(spec=Part)

        # Mock the async save to raise an exception
        mock_asyncio_run.side_effect = Exception("Save failed")

        result = save_artifact_to_service(
            mock_service, mock_artifact, "test.pdf", "user_123", "session_456"
        )

        assert result is False


class TestLoadUploadedDocumentsAsArtifacts:
    """Test the main orchestration function"""

    @patch("asyncio.run")
    @patch("agents.strategy_agent.artifact_utils.GcsArtifactService")
    @patch("agents.strategy_agent.artifact_utils.storage.Client")
    def test_full_flow_with_documents(
        self, mock_storage_client_class, mock_artifact_service_class, mock_asyncio_run
    ):
        # Setup mocks
        mock_storage_client = Mock()
        mock_storage_client_class.return_value = mock_storage_client

        mock_artifact_service = Mock()
        mock_artifact_service_class.return_value = mock_artifact_service

        # Mock bucket and blob
        mock_bucket = Mock()
        mock_blob = Mock()
        mock_storage_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.download_as_bytes.return_value = b"Document content"
        mock_blob.content_type = "application/pdf"

        # Call function
        result = load_uploaded_documents_as_artifacts(
            uploaded_documents=["gs://test-bucket/doc1.pdf"],
            account_id="acc_123",
            session_user_id="user_456",
            session_id="session_789",
            project_id="test-project",
        )

        # Mock async save_artifact to return a version
        mock_asyncio_run.return_value = 1

        # Assertions
        assert result == mock_artifact_service
        # GcsArtifactService should be called with bucket_name only (no namespace)
        mock_artifact_service_class.assert_called_once_with(bucket_name="test-bucket")
        mock_storage_client_class.assert_called_once_with(project="test-project")

    @patch("agents.strategy_agent.artifact_utils.InMemoryArtifactService")
    def test_no_documents_returns_inmemory_service(self, mock_inmemory_service_class):
        mock_service = Mock()
        mock_inmemory_service_class.return_value = mock_service

        result = load_uploaded_documents_as_artifacts(
            uploaded_documents=[],
            account_id="acc_123",
            session_user_id="user_456",
            session_id="session_789",
        )

        assert result == mock_service
        mock_inmemory_service_class.assert_called_once()

    def test_with_injected_dependencies(self):
        # Test dependency injection for testability
        mock_storage = Mock()
        mock_artifact_service = Mock()

        result = load_uploaded_documents_as_artifacts(
            uploaded_documents=None,
            account_id="acc_123",
            session_user_id="user_456",
            session_id="session_789",
            storage_client=mock_storage,
            artifact_service=mock_artifact_service,
        )

        assert result == mock_artifact_service

    @patch("agents.strategy_agent.artifact_utils.GcsArtifactService")
    @patch("agents.strategy_agent.artifact_utils.InMemoryArtifactService")
    def test_fallback_on_gcs_setup_failure(self, mock_inmemory_class, mock_gcs_class):
        # Make GCS setup fail
        mock_gcs_class.side_effect = Exception("GCS setup failed")
        mock_inmemory = Mock()
        mock_inmemory_class.return_value = mock_inmemory

        result = load_uploaded_documents_as_artifacts(
            uploaded_documents=["gs://bucket/file.pdf"],
            account_id="acc_123",
            session_user_id="user_456",
            session_id="session_789",
        )

        assert result == mock_inmemory
        mock_inmemory_class.assert_called_once()
