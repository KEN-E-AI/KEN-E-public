"""
Integration tests for document processing utilities.
Following existing test patterns from test_integration.py.
"""

import pytest
import io
import time
import sys
import concurrent.futures
from unittest.mock import Mock, patch, MagicMock
from google.cloud import storage

from app.adk.agents.strategy_agent.document_utils import (
    extract_text_from_pdf,
    _extract_text_from_pdf_impl,
    load_document_from_gcs,
    load_documents_from_gcs_urls,
    validate_document_size,
    create_document_loading_summary,
    create_error_context,
    DocumentSizeError,
    DocumentProcessingError,
    DocumentFormatError,
    MAX_DOCUMENT_SIZE,
    MAX_TOTAL_SIZE,
    MAX_TEXT_LENGTH,
)


class TestDocumentSizeLimits:
    """Test document size validation."""

    def test_validate_document_size_within_limit(self):
        """Test document within size limit passes."""
        content = b"x" * 1000  # 1KB
        validate_document_size(content, "test.pdf")  # Should not raise

    def test_validate_document_size_at_limit(self):
        """Test document exactly at size limit passes."""
        content = b"x" * MAX_DOCUMENT_SIZE  # Exactly at limit
        validate_document_size(content, "test.pdf")  # Should not raise

    def test_validate_document_size_exceeds_limit(self):
        """Test document exceeding size limit raises error."""
        content = b"x" * (MAX_DOCUMENT_SIZE + 1)
        with pytest.raises(DocumentSizeError) as exc_info:
            validate_document_size(content, "large.pdf")
        assert "exceeds size limit" in str(exc_info.value)
        assert "large.pdf" in str(exc_info.value)

    def test_validate_empty_document(self):
        """Test empty document passes validation."""
        content = b""
        validate_document_size(content, "empty.txt")  # Should not raise


class TestPDFExtraction:
    """Test PDF text extraction."""

    @pytest.fixture
    def sample_pdf_bytes(self):
        """Create a minimal valid PDF for testing."""
        # This is a simplified mock - in real tests we'd use a proper PDF
        return b"%PDF-1.4\n...mock pdf content..."

    def test_extract_text_from_valid_pdf(self, sample_pdf_bytes):
        """Test extracting text from valid PDF."""
        mock_pypdf2 = Mock()
        with patch.dict("sys.modules", {"PyPDF2": mock_pypdf2}):
            mock_reader = Mock()
            mock_page = Mock()
            mock_page.extract_text.return_value = "Test PDF Content\nPage 1"
            mock_reader.pages = [mock_page]
            mock_pypdf2.PdfReader.return_value = mock_reader

            result = extract_text_from_pdf(sample_pdf_bytes, "test.pdf")
            assert "Test PDF Content" in result
            assert "Page 1" in result

    def test_extract_text_from_multipage_pdf(self, sample_pdf_bytes):
        """Test extracting text from multi-page PDF."""
        mock_pypdf2 = Mock()
        with patch.dict("sys.modules", {"PyPDF2": mock_pypdf2}):
            mock_reader = Mock()
            mock_pages = []
            for i in range(5):
                mock_page = Mock()
                mock_page.extract_text.return_value = f"Page {i + 1} content"
                mock_pages.append(mock_page)
            mock_reader.pages = mock_pages
            mock_pypdf2.PdfReader.return_value = mock_reader

            result = extract_text_from_pdf(sample_pdf_bytes, "multipage.pdf")
            for i in range(5):
                assert f"Page {i + 1} content" in result

    def test_extract_text_truncates_long_content(self, sample_pdf_bytes):
        """Test that very long PDF content is truncated."""
        mock_pypdf2 = Mock()
        with patch.dict("sys.modules", {"PyPDF2": mock_pypdf2}):
            mock_reader = Mock()
            mock_page = Mock()
            # Create content longer than MAX_TEXT_LENGTH
            long_content = "x" * (MAX_TEXT_LENGTH + 1000)
            mock_page.extract_text.return_value = long_content
            mock_reader.pages = [mock_page]
            mock_pypdf2.PdfReader.return_value = mock_reader

            result = extract_text_from_pdf(sample_pdf_bytes, "long.pdf")
            assert len(result) <= MAX_TEXT_LENGTH + 20  # Allow for [TRUNCATED] marker
            assert "[TRUNCATED]" in result

    def test_extract_text_from_corrupt_pdf(self):
        """Test handling of corrupt PDF."""
        corrupt_pdf = b"Not a real PDF"
        mock_pypdf2 = Mock()
        with patch.dict("sys.modules", {"PyPDF2": mock_pypdf2}):
            mock_pypdf2.PdfReader.side_effect = Exception("Invalid PDF")

            with pytest.raises(DocumentProcessingError) as exc_info:
                extract_text_from_pdf(corrupt_pdf, "corrupt.pdf")
            assert "Failed to extract text" in str(exc_info.value)

    def test_extract_text_without_pypdf2(self, sample_pdf_bytes):
        """Test handling when PyPDF2 is not available."""
        with patch.dict("sys.modules", {"PyPDF2": None}):
            with pytest.raises(DocumentProcessingError) as exc_info:
                extract_text_from_pdf(sample_pdf_bytes, "test.pdf")
            assert "PyPDF2 not available" in str(exc_info.value)

    def test_extract_text_with_custom_timeout(self, sample_pdf_bytes):
        """Test PDF extraction with custom timeout parameter."""
        mock_pypdf2 = Mock()
        with patch.dict("sys.modules", {"PyPDF2": mock_pypdf2}):
            mock_reader = Mock()
            mock_page = Mock()
            mock_page.extract_text.return_value = "Quick extraction"
            mock_reader.pages = [mock_page]
            mock_pypdf2.PdfReader.return_value = mock_reader

            # Test with custom timeout
            result = extract_text_from_pdf(sample_pdf_bytes, "test.pdf", timeout=5.0)
            assert "Quick extraction" in result

    def test_extract_text_timeout_error(self, sample_pdf_bytes):
        """Test that PDF extraction raises timeout error when taking too long."""

        def slow_extraction(pdf_bytes, filename):
            time.sleep(2)  # Simulate slow extraction
            return "This should timeout"

        with patch(
            "app.adk.agents.strategy_agent.document_utils._extract_text_from_pdf_impl",
            side_effect=slow_extraction,
        ):
            with pytest.raises(DocumentProcessingError) as exc_info:
                # Use very short timeout to trigger timeout error
                extract_text_from_pdf(sample_pdf_bytes, "slow.pdf", timeout=0.1)
            assert "timed out after 0.1s" in str(exc_info.value)
            assert "slow.pdf" in str(exc_info.value)

    def test_extract_text_handles_executor_errors(self, sample_pdf_bytes):
        """Test that executor errors are properly handled."""
        with patch("concurrent.futures.ThreadPoolExecutor") as mock_executor_class:
            mock_executor = Mock()
            mock_future = Mock()
            mock_future.result.side_effect = RuntimeError("Executor failed")
            mock_executor.submit.return_value = mock_future
            mock_executor_class.return_value.__enter__.return_value = mock_executor

            with pytest.raises(DocumentProcessingError) as exc_info:
                extract_text_from_pdf(sample_pdf_bytes, "test.pdf")
            assert "Failed to extract text" in str(exc_info.value)


class TestGCSDocumentLoading:
    """Test loading documents from GCS."""

    @pytest.fixture
    def mock_storage_client(self):
        """Create mock GCS storage client."""
        mock_client = Mock(spec=storage.Client)
        mock_bucket = Mock()
        mock_blob = Mock()

        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        return mock_client, mock_bucket, mock_blob

    def test_load_text_document_from_gcs(self, mock_storage_client):
        """Test loading a text document from GCS."""
        mock_client, mock_bucket, mock_blob = mock_storage_client

        # Setup mock
        mock_blob.size = 1000
        mock_blob.download_as_bytes.return_value = b"Test document content"

        filename, content = load_document_from_gcs(
            "gs://test-bucket/path/to/test.txt", mock_client
        )

        assert filename == "test.txt"
        assert content == "Test document content"
        mock_blob.reload.assert_called_once()

    def test_load_markdown_document_from_gcs(self, mock_storage_client):
        """Test loading a markdown document from GCS."""
        mock_client, mock_bucket, mock_blob = mock_storage_client

        # Setup mock
        mock_blob.size = 500
        mock_blob.download_as_bytes.return_value = b"# Markdown Title\n\nContent here"

        filename, content = load_document_from_gcs(
            "gs://test-bucket/readme.md", mock_client
        )

        assert filename == "readme.md"
        assert "# Markdown Title" in content
        assert "Content here" in content

    def test_load_pdf_document_from_gcs(self, mock_storage_client):
        """Test loading a PDF document from GCS."""
        mock_client, mock_bucket, mock_blob = mock_storage_client

        # Setup mock
        mock_blob.size = 5000
        mock_blob.download_as_bytes.return_value = b"%PDF-1.4..."

        with patch(
            "app.adk.agents.strategy_agent.document_utils.extract_text_from_pdf"
        ) as mock_extract:
            mock_extract.return_value = "Extracted PDF content"

            filename, content = load_document_from_gcs(
                "gs://test-bucket/document.pdf", mock_client
            )

            assert filename == "document.pdf"
            assert content == "Extracted PDF content"
            mock_extract.assert_called_once()

    def test_load_unsupported_format_from_gcs(self, mock_storage_client):
        """Test loading an unsupported document format."""
        mock_client, mock_bucket, mock_blob = mock_storage_client

        # Setup mock
        mock_blob.size = 1000
        mock_blob.download_as_bytes.return_value = b"Binary content"

        filename, content = load_document_from_gcs(
            "gs://test-bucket/image.jpg", mock_client
        )

        assert filename == "image.jpg"
        assert "[Unsupported format: image.jpg" in content

    def test_load_oversized_document_from_gcs(self, mock_storage_client):
        """Test handling of oversized document."""
        mock_client, mock_bucket, mock_blob = mock_storage_client

        # Setup mock with large size
        mock_blob.size = MAX_DOCUMENT_SIZE + 1

        with pytest.raises(DocumentSizeError) as exc_info:
            load_document_from_gcs("gs://test-bucket/large.pdf", mock_client)
        assert "too large" in str(exc_info.value)

    def test_load_document_not_found(self, mock_storage_client):
        """Test handling of document not found error."""
        mock_client, mock_bucket, mock_blob = mock_storage_client

        # Simulate NotFound exception
        not_found_error = Exception("Not found")
        not_found_error.__class__.__name__ = "NotFound"
        mock_blob.reload.side_effect = not_found_error

        with pytest.raises(DocumentProcessingError) as exc_info:
            load_document_from_gcs("gs://test-bucket/missing.txt", mock_client)
        assert "not found" in str(exc_info.value)

    def test_load_document_access_denied(self, mock_storage_client):
        """Test handling of access denied error."""
        mock_client, mock_bucket, mock_blob = mock_storage_client

        # Simulate Forbidden exception
        forbidden_error = Exception("Forbidden")
        forbidden_error.__class__.__name__ = "Forbidden"
        mock_blob.reload.side_effect = forbidden_error

        with pytest.raises(DocumentProcessingError) as exc_info:
            load_document_from_gcs("gs://test-bucket/forbidden.txt", mock_client)
        assert "Access denied" in str(exc_info.value)

    def test_invalid_gcs_url(self):
        """Test handling of invalid GCS URL."""
        mock_client = Mock()

        with pytest.raises(ValueError) as exc_info:
            load_document_from_gcs("not-a-gcs-url", mock_client)
        assert "Invalid GCS URL" in str(exc_info.value)


class TestMultipleDocumentLoading:
    """Test loading multiple documents with cumulative limits."""

    def test_load_multiple_documents_success(self):
        """Test successfully loading multiple documents."""
        urls = ["gs://bucket/doc1.txt", "gs://bucket/doc2.txt", "gs://bucket/doc3.pdf"]

        with patch(
            "app.adk.agents.strategy_agent.document_utils.storage.Client"
        ) as mock_storage:
            with patch(
                "app.adk.agents.strategy_agent.document_utils.load_document_from_gcs"
            ) as mock_load:
                mock_load.side_effect = [
                    ("doc1.txt", "Content of doc1"),
                    ("doc2.txt", "Content of doc2"),
                    ("doc3.pdf", "PDF content extracted"),
                ]

                result = load_documents_from_gcs_urls(urls, "test-project")

                assert len(result) == 3
                assert "input_strategy_doc1.txt" in result
                assert "input_strategy_doc2.txt" in result
                assert "input_strategy_doc3.pdf" in result
                assert result["input_strategy_doc1.txt"] == "Content of doc1"

    def test_load_multiple_documents_with_size_limit(self):
        """Test loading multiple documents respects cumulative size limit."""
        urls = ["gs://bucket/doc1.txt", "gs://bucket/doc2.txt", "gs://bucket/doc3.txt"]

        with patch("app.adk.agents.strategy_agent.document_utils.storage.Client"):
            with patch(
                "app.adk.agents.strategy_agent.document_utils.load_document_from_gcs"
            ) as mock_load:
                # Create large content that will exceed cumulative limit
                large_content = "x" * (MAX_TOTAL_SIZE // 2 + 1000)

                mock_load.side_effect = [
                    ("doc1.txt", large_content),
                    ("doc2.txt", large_content),  # This would exceed total
                    ("doc3.txt", "small content"),
                ]

                result = load_documents_from_gcs_urls(urls, "test-project")

                # Should only load first document and skip second due to size
                assert len(result) == 1
                assert "input_strategy_doc1.txt" in result
                assert "input_strategy_doc2.txt" not in result

    def test_continue_on_single_document_failure(self):
        """Test that processing continues when one document fails."""
        urls = ["gs://bucket/good1.txt", "gs://bucket/bad.pdf", "gs://bucket/good2.txt"]

        with patch("app.adk.agents.strategy_agent.document_utils.storage.Client"):
            with patch(
                "app.adk.agents.strategy_agent.document_utils.load_document_from_gcs"
            ) as mock_load:

                def side_effect(url, client):
                    if "bad.pdf" in url:
                        raise DocumentProcessingError("Corrupt PDF")
                    elif "good1.txt" in url:
                        return ("good1.txt", "Content 1")
                    else:
                        return ("good2.txt", "Content 2")

                mock_load.side_effect = side_effect

                result = load_documents_from_gcs_urls(urls, "test-project")

                # Should load 2 out of 3 documents
                assert len(result) == 2
                assert "input_strategy_good1.txt" in result
                assert "input_strategy_good2.txt" in result

    def test_all_documents_fail(self):
        """Test handling when all documents fail to load."""
        urls = ["gs://bucket/bad1.pdf", "gs://bucket/bad2.pdf"]

        with patch("app.adk.agents.strategy_agent.document_utils.storage.Client"):
            with patch(
                "app.adk.agents.strategy_agent.document_utils.load_document_from_gcs"
            ) as mock_load:
                mock_load.side_effect = DocumentProcessingError("Failed")

                result = load_documents_from_gcs_urls(urls, "test-project")

                assert len(result) == 0

    def test_empty_url_list(self):
        """Test handling of empty URL list."""
        result = load_documents_from_gcs_urls([], "test-project")
        assert result == {}


class TestDocumentLoadingSummary:
    """Test document loading summary generation."""

    def test_summary_all_loaded(self):
        """Test summary when all documents are loaded."""
        loaded_docs = {
            "input_strategy_doc1.txt": "content1",
            "input_strategy_doc2.pdf": "content2",
        }
        requested_urls = ["gs://bucket/doc1.txt", "gs://bucket/doc2.pdf"]

        summary = create_document_loading_summary(loaded_docs, requested_urls)
        assert "Successfully loaded all 2 document(s)" in summary

    def test_summary_partial_loaded(self):
        """Test summary when some documents are loaded."""
        loaded_docs = {"input_strategy_doc1.txt": "content1"}
        requested_urls = [
            "gs://bucket/doc1.txt",
            "gs://bucket/doc2.pdf",
            "gs://bucket/doc3.txt",
        ]

        summary = create_document_loading_summary(loaded_docs, requested_urls)
        assert "Loaded 1 of 3 document(s)" in summary
        assert "Some documents could not be processed" in summary

    def test_summary_none_loaded(self):
        """Test summary when no documents are loaded."""
        loaded_docs = {}
        requested_urls = ["gs://bucket/doc1.txt", "gs://bucket/doc2.pdf"]

        summary = create_document_loading_summary(loaded_docs, requested_urls)
        assert "Unable to load any of the 2 requested document(s)" in summary
        assert "Proceeding with web research only" in summary

    def test_summary_no_requests(self):
        """Test summary when no documents were requested."""
        loaded_docs = {}
        requested_urls = []

        summary = create_document_loading_summary(loaded_docs, requested_urls)
        assert summary == ""


class TestErrorContext:
    """Test error context creation."""

    def test_create_error_context(self):
        """Test creating error context for logging."""
        error = ValueError("Test error message")
        context = create_error_context(error, "test_operation")

        assert context["error_type"] == "ValueError"
        assert context["error_message"] == "Test error message"
        assert context["operation"] == "test_operation"
        assert "timestamp" in context
