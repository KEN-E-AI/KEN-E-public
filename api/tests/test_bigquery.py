"""Tests for BigQuery service."""

import os
from unittest.mock import MagicMock, Mock, patch

import pytest
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

from src.kene_api.bigquery import BigQueryService, get_bigquery_service


class TestBigQueryService:
    """Test cases for BigQueryService."""

    def test_init(self):
        """Test BigQueryService initialization."""
        service = BigQueryService()
        assert service._client is None
        assert service._initialized is False

    def test_initialize_with_adc(self):
        """Test initialization with Application Default Credentials."""
        service = BigQueryService()

        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLOUD_PROJECT_ID": "test-project",
                "USE_APPLICATION_DEFAULT_CREDENTIALS": "true",
            },
        ):
            with patch("src.kene_api.bigquery.default") as mock_default:
                mock_credentials = Mock()
                mock_default.return_value = (mock_credentials, "test-project")

                with patch("src.kene_api.bigquery.bigquery.Client") as mock_client:
                    result = service.initialize()

                    assert result is True
                    assert service._initialized is True
                    mock_client.assert_called_once_with(
                        project="test-project", credentials=mock_credentials
                    )

    def test_initialize_with_service_account_file(self):
        """Test initialization with service account file."""
        service = BigQueryService()

        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLOUD_PROJECT_ID": "test-project",
                "USE_APPLICATION_DEFAULT_CREDENTIALS": "false",
                "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/creds.json",
            },
        ):
            with patch("os.path.isfile", return_value=True):
                with patch(
                    "src.kene_api.bigquery.service_account.Credentials.from_service_account_file"
                ) as mock_creds:
                    mock_credentials = Mock()
                    mock_creds.return_value = mock_credentials

                    with patch("src.kene_api.bigquery.bigquery.Client") as mock_client:
                        result = service.initialize()

                        assert result is True
                        assert service._initialized is True
                        mock_client.assert_called_once_with(
                            project="test-project", credentials=mock_credentials
                        )

    def test_initialize_missing_project_id(self):
        """Test initialization fails when project ID is missing."""
        service = BigQueryService()

        with patch.dict(os.environ, {}, clear=True):
            result = service.initialize()
            assert result is False
            assert service._initialized is False

    def test_health_check_success(self):
        """Test successful health check."""
        service = BigQueryService()
        service._initialized = True

        mock_client = Mock()
        mock_query_job = Mock()
        mock_query_job.result.return_value = [{"result": 1}]
        mock_client.query.return_value = mock_query_job
        service._client = mock_client

        result = service.health_check()
        assert result is True
        mock_client.query.assert_called_once_with("SELECT 1")

    def test_health_check_not_initialized(self):
        """Test health check when service is not initialized."""
        service = BigQueryService()

        with patch.object(service, "initialize", return_value=False):
            result = service.health_check()
            assert result is False

    def test_query_success(self):
        """Test successful query execution."""
        service = BigQueryService()
        service._initialized = True

        mock_client = Mock()
        mock_query_job = Mock()
        mock_row1 = {"id": 1, "name": "test1"}
        mock_row2 = {"id": 2, "name": "test2"}
        mock_query_job.result.return_value = [mock_row1, mock_row2]
        mock_client.query.return_value = mock_query_job
        service._client = mock_client

        results = service.query("SELECT * FROM test_table")

        assert len(results) == 2
        assert results[0] == mock_row1
        assert results[1] == mock_row2
        mock_client.query.assert_called_once()

    def test_query_not_initialized(self):
        """Test query fails when service is not initialized."""
        service = BigQueryService()

        with pytest.raises(RuntimeError, match="BigQuery not initialized"):
            service.query("SELECT * FROM test_table")

    def test_query_holiday_activities_success(self):
        """Test successful holiday activities query."""
        service = BigQueryService()
        service._initialized = True

        mock_client = Mock()
        mock_query_job = Mock()
        mock_results = [
            {
                "description": "New Year",
                "start_date": "2024-01-01",
                "end_date": "2024-01-01",
            },
            {
                "description": "Christmas",
                "start_date": "2024-12-25",
                "end_date": "2024-12-26",
            },
        ]
        mock_query_job.result.return_value = mock_results
        mock_client.query.return_value = mock_query_job
        service._client = mock_client

        results = service.query_holiday_activities("test-project", ["AU", "CA"])

        assert len(results) == 2
        assert results[0]["description"] == "New Year"
        assert results[1]["description"] == "Christmas"

        # Check the query was formatted correctly
        called_query = mock_client.query.call_args[0][0]
        assert "test-project.shared_activities.holiday-import" in called_query
        assert "WHERE region IN ('AU', 'CA')" in called_query

    def test_query_holiday_activities_empty_regions(self):
        """Test holiday activities query with empty regions list."""
        service = BigQueryService()
        service._initialized = True

        results = service.query_holiday_activities("test-project", [])
        assert results == []

    def test_query_holiday_activities_table_not_found(self):
        """Test holiday activities query when table doesn't exist."""
        service = BigQueryService()
        service._initialized = True

        with patch.object(service, "query", side_effect=NotFound("Table not found")):
            results = service.query_holiday_activities("test-project", ["AU"])
            assert results == []

    def test_get_bigquery_service(self):
        """Test getting the global BigQuery service instance."""
        with patch("src.kene_api.bigquery._bigquery_service", None):
            with patch.object(BigQueryService, "initialize", return_value=True):
                service1 = get_bigquery_service()
                service2 = get_bigquery_service()

                assert service1 is service2  # Should return the same instance
                assert isinstance(service1, BigQueryService)
