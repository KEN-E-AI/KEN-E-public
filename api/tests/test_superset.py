"""Tests for Superset client integration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import requests

from src.kene_api.superset import SupersetClient, SupersetClientError


@pytest.fixture
def mock_session():
    """Mock requests session."""
    session = MagicMock()
    session.post = MagicMock()
    session.get = MagicMock()
    session.put = MagicMock()
    session.delete = MagicMock()
    session.headers = {}
    return session


@pytest.fixture
def superset_client(mock_session):
    """SupersetClient instance with mocked session."""
    client = SupersetClient()
    client.session = mock_session
    client.base_url = "http://test-superset.com"
    client.username = "test_user"
    client.password = "test_pass"
    return client


class TestSupersetClient:
    """Test class for SupersetClient."""

    @pytest.mark.asyncio
    async def test_authenticate_success(self, superset_client, mock_session):
        """Test successful authentication."""
        # Mock successful authentication response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "test_token"}
        mock_response.raise_for_status = MagicMock()
        mock_session.post.return_value = mock_response

        await superset_client.authenticate()

        assert superset_client.access_token == "test_token"
        assert "Authorization" in superset_client.session.headers
        assert superset_client.session.headers["Authorization"] == "Bearer test_token"

    @pytest.mark.asyncio
    async def test_authenticate_failure(self, superset_client, mock_session):
        """Test authentication failure."""
        # Mock failed authentication
        mock_session.post.side_effect = requests.RequestException("Auth failed")

        with pytest.raises(SupersetClientError):
            await superset_client.authenticate()

    @pytest.mark.asyncio
    async def test_get_dataset_success(self, superset_client, mock_session):
        """Test successful dataset retrieval."""
        superset_client.access_token = "test_token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": {"id": 1, "name": "test_dataset"}}
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        result = await superset_client.get_dataset(1)

        assert result == {"id": 1, "name": "test_dataset"}
        mock_session.get.assert_called_once_with(
            "http://test-superset.com/api/v1/dataset/1", timeout=30
        )

    @pytest.mark.asyncio
    async def test_get_dataset_not_found(self, superset_client, mock_session):
        """Test dataset not found."""
        superset_client.access_token = "test_token"

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_session.get.return_value = mock_response

        result = await superset_client.get_dataset(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_create_metric_success(self, superset_client, mock_session):
        """Test successful metric creation."""
        superset_client.access_token = "test_token"

        # Mock get_dataset call
        dataset_response = MagicMock()
        dataset_response.status_code = 200
        dataset_response.json.return_value = {
            "result": {"id": 1, "name": "test_dataset"}
        }
        dataset_response.raise_for_status = MagicMock()

        # Mock create_metric call
        metric_response = MagicMock()
        metric_response.status_code = 201
        metric_response.json.return_value = {
            "result": {"id": 123, "metric_name": "test_metric"}
        }
        metric_response.raise_for_status = MagicMock()

        mock_session.get.return_value = dataset_response
        mock_session.post.return_value = metric_response

        metric_data = {
            "metric_name": "test_metric",
            "verbose_name": "Test Metric",
            "expression": "COUNT(*)",
            "description": "Test metric description",
        }

        result = await superset_client.create_metric(1, metric_data)

        assert result == {"id": 123, "metric_name": "test_metric"}
        mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_metric_dataset_not_found(self, superset_client, mock_session):
        """Test metric creation when dataset doesn't exist."""
        superset_client.access_token = "test_token"

        # Mock dataset not found
        dataset_response = MagicMock()
        dataset_response.status_code = 404
        mock_session.get.return_value = dataset_response

        metric_data = {"metric_name": "test_metric", "expression": "COUNT(*)"}

        with pytest.raises(SupersetClientError, match="Dataset 999 not found"):
            await superset_client.create_metric(999, metric_data)

    @pytest.mark.asyncio
    async def test_update_metric_success(self, superset_client, mock_session):
        """Test successful metric update."""
        superset_client.access_token = "test_token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {"id": 123, "metric_name": "updated_metric"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_session.put.return_value = mock_response

        metric_data = {
            "metric_name": "updated_metric",
            "description": "Updated description",
        }

        result = await superset_client.update_metric(1, 123, metric_data)

        assert result == {"id": 123, "metric_name": "updated_metric"}
        mock_session.put.assert_called_once_with(
            "http://test-superset.com/api/v1/dataset/1/metric/123",
            json=metric_data,
            timeout=30,
        )

    @pytest.mark.asyncio
    async def test_delete_metric_success(self, superset_client, mock_session):
        """Test successful metric deletion."""
        superset_client.access_token = "test_token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_session.delete.return_value = mock_response

        result = await superset_client.delete_metric(1, 123)

        assert result is True
        mock_session.delete.assert_called_once_with(
            "http://test-superset.com/api/v1/dataset/1/metric/123", timeout=30
        )

    @pytest.mark.asyncio
    async def test_delete_metric_not_found(self, superset_client, mock_session):
        """Test metric deletion when metric doesn't exist."""
        superset_client.access_token = "test_token"

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_session.delete.return_value = mock_response

        result = await superset_client.delete_metric(1, 999)

        assert result is True  # Should return True even if not found

    @pytest.mark.asyncio
    async def test_delete_metric_failure(self, superset_client, mock_session):
        """Test metric deletion failure."""
        superset_client.access_token = "test_token"

        mock_session.delete.side_effect = requests.RequestException("Delete failed")

        result = await superset_client.delete_metric(1, 123)

        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_success(self, superset_client, mock_session):
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.get.return_value = mock_response

        result = await superset_client.health_check()

        assert result is True
        mock_session.get.assert_called_once_with(
            "http://test-superset.com/health", timeout=10
        )

    @pytest.mark.asyncio
    async def test_health_check_failure(self, superset_client, mock_session):
        """Test health check failure."""
        mock_session.get.side_effect = requests.RequestException("Connection failed")

        result = await superset_client.health_check()

        assert result is False
