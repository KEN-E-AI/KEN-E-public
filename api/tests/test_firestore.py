"""Tests for the Firestore router."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from src.kene_api.firestore import get_firestore_service
from src.kene_api.main import app


@pytest.fixture
def mock_firestore_service():
    """Mock Firestore service for testing."""
    mock_service = MagicMock()
    mock_service.health_check.return_value = True
    mock_service.create_document.return_value = "test_doc_id"
    mock_service.get_document.return_value = {"test_field": "test_value"}
    mock_service.update_document.return_value = True
    mock_service.array_union_document.return_value = True
    mock_service.replace_array_element.return_value = True
    mock_service.delete_document.return_value = True
    # Add subcollection method mocks
    mock_service.create_subcollection_document.return_value = "test_subdoc_id"
    mock_service.get_subcollection_document.return_value = {"test_field": "test_value"}
    mock_service.update_subcollection_document.return_value = True
    mock_service.delete_subcollection_document.return_value = True
    mock_service.array_union_subcollection_document.return_value = True
    mock_service.replace_array_element_subcollection.return_value = True
    mock_service.list_documents.return_value = [{"id": "doc1", "data": "value1"}]
    mock_service.query_documents.return_value = [{"id": "doc2", "data": "value2"}]
    mock_service.get_kpi_setting.return_value = "metric123"
    mock_service.update_kpi_setting.return_value = True
    mock_service.get_all_kpi_settings.return_value = {
        "income_kpi": "metric123",
        "marketing_cost_kpi": "metric456",
        "net_income_kpi": "metric789",
    }
    # Add channel method mocks
    mock_service.create_channel.return_value = {
        "channel_name": "test",
        "effectiveness_kpi": "metric123",
    }
    mock_service.get_channel.return_value = {"effectiveness_kpi": "metric123"}
    mock_service.list_channels.return_value = []
    mock_service.update_channel.return_value = {"effectiveness_kpi": "metric123"}
    mock_service.delete_channel.return_value = True
    # Add tactic method mocks
    mock_service.create_tactic.return_value = {
        "tactic_name": "test",
        "effectiveness_kpi": "metric123",
    }
    mock_service.get_tactic.return_value = {"effectiveness_kpi": "metric123"}
    mock_service.list_tactics.return_value = []
    mock_service.update_tactic.return_value = {"effectiveness_kpi": "metric123"}
    mock_service.delete_tactic.return_value = True
    # Add nested field set method mocks
    mock_service.set_nested_field.return_value = True
    mock_service.set_nested_field_subcollection.return_value = True
    return mock_service


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


@pytest.fixture
def mock_super_admin_context():
    """Mock super-admin user context for tests that need to bypass scope checks."""
    user = MagicMock()
    user.user_id = "test_user"
    user.email = "test@ken-e.ai"
    user.is_super_admin = True
    return user


@pytest.fixture
def mock_regular_user_context():
    """Mock regular user context (not super-admin)."""
    user = MagicMock()
    user.user_id = "test_user_uid"
    user.email = "user@example.com"
    user.is_super_admin = False
    return user


class TestFirestoreRouter:
    """Test suite for Firestore router."""

    @pytest.fixture(autouse=True)
    def setup_auth(self, mock_super_admin_context):
        """Provide super-admin auth override for all tests in this class."""
        from src.kene_api.auth.dependencies import get_current_user as gcu
        app.dependency_overrides[gcu] = lambda: mock_super_admin_context
        yield
        app.dependency_overrides.pop(gcu, None)

    def test_create_document_success(self, client, mock_firestore_service):
        """Test creating a document successfully."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        create_request = {
            "account_id": "test_account",
            "collection": "test_collection",
            "document_id": "test_doc",
            "data": {"field1": "value1", "field2": "value2"},
        }

        response = client.post("/api/v1/firestore/documents", json=create_request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["document_id"] == "test_doc_id"
        assert data["data"] == create_request["data"]

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.create_document.assert_called_once_with(
            collection="test_collection",
            document_id="test_doc",
            data={"field1": "value1", "field2": "value2"},
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_create_document_firestore_unavailable(
        self, client, mock_firestore_service
    ):
        """Test creating a document when Firestore is unavailable."""
        mock_firestore_service.health_check.return_value = False
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        create_request = {
            "account_id": "test_account",
            "collection": "test_collection",
            "data": {"field1": "value1"},
        }

        response = client.post("/api/v1/firestore/documents", json=create_request)

        assert response.status_code == 503
        assert "Firestore service unavailable" in response.json()["detail"]

        # Clean up
        app.dependency_overrides.clear()

    def test_get_document_success(self, client, mock_firestore_service):
        """Test getting a document successfully."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.get(
            "/api/v1/firestore/documents/test_collection/test_doc",
            params={"account_id": "test_account"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["document_id"] == "test_doc"
        assert data["data"] == {"test_field": "test_value"}

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.get_document.assert_called_once_with(
            collection="test_collection", document_id="test_doc"
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_get_document_not_found(self, client, mock_firestore_service):
        """Test getting a document that doesn't exist."""
        mock_firestore_service.get_document.return_value = None
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.get(
            "/api/v1/firestore/documents/test_collection/nonexistent_doc",
            params={"account_id": "test_account"},
        )

        assert response.status_code == 404
        assert "Document not found" in response.json()["detail"]

        # Clean up
        app.dependency_overrides.clear()

    def test_update_document_success(self, client, mock_firestore_service):
        """Test updating a document successfully."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_data = {"field1": "updated_value", "field2": "new_value"}

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "updated successfully" in data["message"]

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.update_document.assert_called_once_with(
            collection="test_collection", document_id="test_doc", data=update_data
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_update_document_not_found(self, client, mock_firestore_service):
        """Test updating a document that doesn't exist."""
        mock_firestore_service.update_document.return_value = False
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_data = {"field1": "updated_value"}

        response = client.put(
            "/api/v1/firestore/documents/test_collection/nonexistent_doc",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 404
        assert "Document not found" in response.json()["detail"]

        # Clean up
        app.dependency_overrides.clear()

    def test_array_union_document_success(self, client, mock_firestore_service):
        """Test arrayUnion operation successfully."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_data = {
            "update": {
                "operator": "arrayUnion",
                "field": "accounts",
                "value": {"account_id": "new_account", "name": "New Account"},
            }
        }

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Array union operation on field 'accounts'" in data["message"]

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.array_union_document.assert_called_once_with(
            collection="test_collection",
            document_id="test_doc",
            field="accounts",
            value={"account_id": "new_account", "name": "New Account"},
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_array_union_missing_field(self, client, mock_firestore_service):
        """Test arrayUnion operation with missing field parameter."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_data = {
            "update": {"operator": "arrayUnion", "value": {"account_id": "new_account"}}
        }

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 400
        assert (
            "arrayUnion operation requires 'field' and 'value' parameters"
            in response.json()["detail"]
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_array_union_missing_value(self, client, mock_firestore_service):
        """Test arrayUnion operation with missing value parameter."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_data = {"update": {"operator": "arrayUnion", "field": "accounts"}}

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 400
        assert (
            "arrayUnion operation requires 'field' and 'value' parameters"
            in response.json()["detail"]
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_replace_one_document_success(self, client, mock_firestore_service):
        """Test replaceOne operation successfully."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_data = {
            "update": {
                "operator": "replaceOne",
                "field": "accounts",
                "matchField": "account_id",
                "matchValue": "acc_001",
                "value": {
                    "account_id": "acc_001",
                    "name": "Updated Account",
                    "status": "premium",
                },
            }
        }

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert (
            "Replace operation on field 'accounts' where account_id=acc_001"
            in data["message"]
        )

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.replace_array_element.assert_called_once_with(
            collection="test_collection",
            document_id="test_doc",
            field="accounts",
            match_field="account_id",
            match_value="acc_001",
            new_value={
                "account_id": "acc_001",
                "name": "Updated Account",
                "status": "premium",
            },
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_replace_one_missing_parameters(self, client, mock_firestore_service):
        """Test replaceOne operation with missing parameters."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_data = {
            "update": {
                "operator": "replaceOne",
                "field": "accounts",
                "matchField": "account_id",
                # Missing matchValue and value
            }
        }

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 400
        assert (
            "replaceOne operation requires 'field', 'matchField', 'matchValue', and 'value' parameters"
            in response.json()["detail"]
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_replace_one_not_found(self, client, mock_firestore_service):
        """Test replaceOne operation when target element is not found."""
        mock_firestore_service.replace_array_element.return_value = False
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_data = {
            "update": {
                "operator": "replaceOne",
                "field": "accounts",
                "matchField": "account_id",
                "matchValue": "nonexistent_id",
                "value": {"account_id": "nonexistent_id", "name": "Updated Account"},
            }
        }

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 404
        assert "Document not found or operation failed" in response.json()["detail"]

        # Clean up
        app.dependency_overrides.clear()

    def test_invalid_update_operator(self, client, mock_firestore_service):
        """Test update operation with invalid operator."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_data = {
            "update": {
                "operator": "invalidOperator",
                "field": "accounts",
                "value": {"test": "value"},
            }
        }

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 400
        assert (
            "Unsupported update operator: invalidOperator" in response.json()["detail"]
        )
        assert (
            "Supported operators: arrayUnion, replaceOne, set"
            in response.json()["detail"]
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_array_union_firestore_unavailable(self, client, mock_firestore_service):
        """Test arrayUnion operation when Firestore is unavailable."""
        mock_firestore_service.health_check.return_value = False
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_data = {
            "update": {
                "operator": "arrayUnion",
                "field": "accounts",
                "value": {"account_id": "new_account"},
            }
        }

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 503
        assert "Firestore service unavailable" in response.json()["detail"]

        # Clean up
        app.dependency_overrides.clear()

    def test_array_union_operation_failed(self, client, mock_firestore_service):
        """Test arrayUnion operation when the operation fails."""
        mock_firestore_service.array_union_document.return_value = False
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_data = {
            "update": {
                "operator": "arrayUnion",
                "field": "accounts",
                "value": {"account_id": "new_account"},
            }
        }

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 404
        assert "Document not found or operation failed" in response.json()["detail"]

        # Clean up
        app.dependency_overrides.clear()

    def test_delete_document_success(self, client, mock_firestore_service):
        """Test deleting a document successfully."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.delete(
            "/api/v1/firestore/documents/test_collection/test_doc",
            params={"account_id": "test_account"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "deleted successfully" in data["message"]

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.delete_document.assert_called_once_with(
            collection="test_collection", document_id="test_doc"
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_create_subcollection_document_success(
        self, client, mock_firestore_service
    ):
        """Test creating a subcollection document successfully."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        create_data = {"field1": "value1", "field2": "value2"}

        response = client.post(
            "/api/v1/firestore/documents/test_collection/test_doc/notifications",
            json=create_data,
            params={
                "subdocument_id": "email_notifications",
                "account_id": "test_account",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["document_id"] == "test_subdoc_id"
        assert data["data"] == create_data

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.create_subcollection_document.assert_called_once_with(
            collection="test_collection",
            document_id="test_doc",
            subcollection="notifications",
            subdocument_id="email_notifications",
            data=create_data,
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_get_subcollection_document_success(self, client, mock_firestore_service):
        """Test getting a subcollection document successfully."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.get(
            "/api/v1/firestore/documents/test_collection/test_doc/notifications/email_notifications"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["document_id"] == "email_notifications"
        assert data["data"] == {"test_field": "test_value"}

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.get_subcollection_document.assert_called_once_with(
            collection="test_collection",
            document_id="test_doc",
            subcollection="notifications",
            subdocument_id="email_notifications",
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_get_subcollection_document_not_found(self, client, mock_firestore_service):
        """Test getting a subcollection document that doesn't exist."""
        mock_firestore_service.get_subcollection_document.return_value = None
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.get(
            "/api/v1/firestore/documents/test_collection/test_doc/notifications/nonexistent"
        )

        assert response.status_code == 404
        assert "Document not found" in response.json()["detail"]

        # Clean up
        app.dependency_overrides.clear()

    def test_update_subcollection_document_success(
        self, client, mock_firestore_service
    ):
        """Test updating a subcollection document successfully."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_data = {"enabled": True, "frequency": "daily"}

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc/notifications/email_notifications",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert (
            "Subcollection document email_notifications updated successfully"
            in data["message"]
        )

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.update_subcollection_document.assert_called_once_with(
            collection="test_collection",
            document_id="test_doc",
            subcollection="notifications",
            subdocument_id="email_notifications",
            data=update_data,
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_update_subcollection_document_array_union(
        self, client, mock_firestore_service
    ):
        """Test updating a subcollection document with arrayUnion operation."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_data = {
            "update": {
                "operator": "arrayUnion",
                "field": "subscriptions",
                "value": {"type": "newsletter", "status": "active"},
            }
        }

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc/notifications/email_notifications",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Array union operation on field 'subscriptions'" in data["message"]

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.array_union_subcollection_document.assert_called_once_with(
            collection="test_collection",
            document_id="test_doc",
            subcollection="notifications",
            subdocument_id="email_notifications",
            field="subscriptions",
            value={"type": "newsletter", "status": "active"},
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_update_subcollection_document_replace_one(
        self, client, mock_firestore_service
    ):
        """Test updating a subcollection document with replaceOne operation."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_data = {
            "update": {
                "operator": "replaceOne",
                "field": "subscriptions",
                "matchField": "type",
                "matchValue": "newsletter",
                "value": {
                    "type": "newsletter",
                    "status": "inactive",
                    "updated": "2025-07-02",
                },
            }
        }

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc/notifications/email_notifications",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert (
            "Replace operation on field 'subscriptions' where type=newsletter"
            in data["message"]
        )

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.replace_array_element_subcollection.assert_called_once_with(
            collection="test_collection",
            document_id="test_doc",
            subcollection="notifications",
            subdocument_id="email_notifications",
            field="subscriptions",
            match_field="type",
            match_value="newsletter",
            new_value={
                "type": "newsletter",
                "status": "inactive",
                "updated": "2025-07-02",
            },
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_delete_subcollection_document_success(
        self, client, mock_firestore_service
    ):
        """Test deleting a subcollection document successfully."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.delete(
            "/api/v1/firestore/documents/test_collection/test_doc/notifications/email_notifications",
            params={"account_id": "test_account"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert (
            "Subcollection document email_notifications deleted successfully"
            in data["message"]
        )

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.delete_subcollection_document.assert_called_once_with(
            collection="test_collection",
            document_id="test_doc",
            subcollection="notifications",
            subdocument_id="email_notifications",
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_query_documents_success(self, client, mock_firestore_service):
        """Test querying documents successfully."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        query_request = {
            "account_id": "test_account",
            "collection": "test_collection",
            "field": "status",
            "operator": "==",
            "value": "active",
            "limit": 10,
        }

        response = client.post("/api/v1/firestore/documents/query", json=query_request)

        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert data["total"] == 1
        assert data["documents"] == [{"id": "doc2", "data": "value2"}]

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.query_documents.assert_called_once_with(
            collection="test_collection",
            field="status",
            operator="==",
            value="active",
            limit=10,
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_list_collection_documents_success(self, client, mock_firestore_service):
        """Test listing all documents in a collection successfully."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.get(
            "/api/v1/firestore/collections/test_collection/documents",
            params={"account_id": "test_account", "limit": 5},
        )

        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert data["total"] == 1
        assert data["documents"] == [{"id": "doc1", "data": "value1"}]

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.list_documents.assert_called_once_with(
            collection="test_collection", limit=5
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_firestore_health_check_success(self, client, mock_firestore_service):
        """Test Firestore health check when service is healthy."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.get("/api/v1/firestore/health")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "healthy" in data["message"]

        mock_firestore_service.health_check.assert_called_once()

        # Clean up
        app.dependency_overrides.clear()

    def test_firestore_health_check_unhealthy(self, client, mock_firestore_service):
        """Test Firestore health check when service is unhealthy."""
        mock_firestore_service.health_check.return_value = False
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.get("/api/v1/firestore/health")

        assert response.status_code == 503
        assert "Firestore service unavailable" in response.json()["detail"]

        # Clean up
        app.dependency_overrides.clear()

    def test_get_kpi_setting_success(self, client, mock_firestore_service):
        """Test getting a KPI setting successfully."""
        mock_firestore_service.get_kpi_setting.return_value = "metric123"
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.get(
            "/api/v1/firestore/kpi-settings/account123/income_kpi"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["account_id"] == "account123"
        assert data["kpi_name"] == "income_kpi"
        assert data["metric_id"] == "metric123"

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.get_kpi_setting.assert_called_once_with(
            account_id="account123", kpi_name="income_kpi"
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_get_kpi_setting_not_found(self, client, mock_firestore_service):
        """Test getting a KPI setting that doesn't exist."""
        mock_firestore_service.get_kpi_setting.return_value = None
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.get(
            "/api/v1/firestore/kpi-settings/account123/income_kpi"
        )

        assert response.status_code == 404
        assert "KPI setting not found" in response.json()["detail"]

        # Clean up
        app.dependency_overrides.clear()

    def test_get_kpi_setting_invalid_kpi_name(self, client, mock_firestore_service):
        """Test getting a KPI setting with invalid KPI name."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.get(
            "/api/v1/firestore/kpi-settings/account123/invalid_kpi"
        )

        assert response.status_code == 400
        assert "Invalid kpi_name" in response.json()["detail"]

        # Clean up
        app.dependency_overrides.clear()

    def test_update_kpi_setting_success(self, client, mock_firestore_service):
        """Test updating a KPI setting successfully."""
        mock_firestore_service.update_kpi_setting.return_value = True
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_request = {
            "account_id": "account123",
            "kpi_name": "marketing_cost_kpi",
            "metric_id": "metric456",
        }

        response = client.put("/api/v1/firestore/kpi-settings", json=update_request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "KPI setting updated" in data["message"]

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.update_kpi_setting.assert_called_once_with(
            account_id="account123",
            kpi_name="marketing_cost_kpi",
            metric_id="metric456",
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_update_kpi_setting_invalid_kpi_name(self, client, mock_firestore_service):
        """Test updating a KPI setting with invalid KPI name."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_request = {
            "account_id": "account123",
            "kpi_name": "invalid_kpi",
            "metric_id": "metric456",
        }

        response = client.put("/api/v1/firestore/kpi-settings", json=update_request)

        assert response.status_code == 400
        assert "Invalid kpi_name" in response.json()["detail"]

        # Clean up
        app.dependency_overrides.clear()

    def test_update_kpi_setting_failure(self, client, mock_firestore_service):
        """Test updating a KPI setting when update fails."""
        mock_firestore_service.update_kpi_setting.return_value = False
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_request = {
            "account_id": "account123",
            "kpi_name": "net_income_kpi",
            "metric_id": "metric789",
        }

        response = client.put("/api/v1/firestore/kpi-settings", json=update_request)

        assert response.status_code == 500
        assert "Failed to update KPI setting" in response.json()["detail"]

        # Clean up
        app.dependency_overrides.clear()

    def test_get_all_kpi_settings_success(self, client, mock_firestore_service):
        """Test getting all KPI settings successfully."""
        mock_kpi_settings = {
            "income_kpi": "metric123",
            "marketing_cost_kpi": "metric456",
            "net_income_kpi": "metric789",
        }
        mock_firestore_service.get_all_kpi_settings.return_value = mock_kpi_settings
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.get("/api/v1/firestore/kpi-settings/account123")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["account_id"] == "account123"
        assert data["kpi_settings"] == mock_kpi_settings

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.get_all_kpi_settings.assert_called_once_with(
            account_id="account123"
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_get_all_kpi_settings_empty(self, client, mock_firestore_service):
        """Test getting all KPI settings when none exist."""
        mock_firestore_service.get_all_kpi_settings.return_value = None
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.get("/api/v1/firestore/kpi-settings/account123")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["account_id"] == "account123"
        assert data["kpi_settings"] == {}

        # Clean up
        app.dependency_overrides.clear()

    def test_create_funnel_step_success(self, client, mock_firestore_service):
        """Test creating a funnel step successfully."""
        mock_firestore_service.create_funnel_step.return_value = True
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        funnel_step_request = {
            "account_id": "account123",
            "funnel_type": "organization",
            "funnel_step_num": 1,
            "funnel_step_name": "awareness",
            "effectiveness_kpi": "metric123",
            "efficiency_kpi": "metric456",
            "objective": "Increase brand awareness",
        }

        response = client.post(
            "/api/v1/firestore/funnel-steps", json=funnel_step_request
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "created successfully" in data["message"]

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.create_funnel_step.assert_called_once_with(
            account_id="account123",
            funnel_type="organization",
            big_bet_name=None,
            funnel_step_num=1,
            funnel_step_data={
                "funnel_step_name": "awareness",
                "effectiveness_kpi": "metric123",
                "efficiency_kpi": "metric456",
                "objective": "Increase brand awareness",
            },
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_create_funnel_step_big_bet_success(self, client, mock_firestore_service):
        """Test creating a big bet funnel step successfully."""
        mock_firestore_service.create_funnel_step.return_value = True
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        funnel_step_request = {
            "account_id": "account123",
            "funnel_type": "big_bet",
            "big_bet_name": "new_product_launch",
            "funnel_step_num": 1,
            "funnel_step_name": "consideration",
            "effectiveness_kpi": "metric789",
            "efficiency_kpi": "metric101",
            "objective": "Drive product consideration",
        }

        response = client.post(
            "/api/v1/firestore/funnel-steps", json=funnel_step_request
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Clean up
        app.dependency_overrides.clear()

    def test_create_funnel_step_invalid_funnel_type(
        self, client, mock_firestore_service
    ):
        """Test creating a funnel step with invalid funnel type."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        funnel_step_request = {
            "account_id": "account123",
            "funnel_type": "invalid_type",
            "funnel_step_num": 1,
            "funnel_step_name": "awareness",
            "effectiveness_kpi": "metric123",
            "efficiency_kpi": "metric456",
            "objective": "Test objective",
        }

        response = client.post(
            "/api/v1/firestore/funnel-steps", json=funnel_step_request
        )

        assert response.status_code == 400
        assert "Invalid funnel_type" in response.json()["detail"]

        # Clean up
        app.dependency_overrides.clear()

    def test_create_funnel_step_big_bet_missing_name(
        self, client, mock_firestore_service
    ):
        """Test creating a big bet funnel step without big_bet_name."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        funnel_step_request = {
            "account_id": "account123",
            "funnel_type": "big_bet",
            "funnel_step_num": 1,
            "funnel_step_name": "awareness",
            "effectiveness_kpi": "metric123",
            "efficiency_kpi": "metric456",
            "objective": "Test objective",
        }

        response = client.post(
            "/api/v1/firestore/funnel-steps", json=funnel_step_request
        )

        assert response.status_code == 400
        assert "big_bet_name is required" in response.json()["detail"]

        # Clean up
        app.dependency_overrides.clear()

    def test_list_funnel_steps_success(self, client, mock_firestore_service):
        """Test listing funnel steps successfully."""
        mock_funnel_steps = [
            {
                "funnel_step_num": 1,
                "funnel_step_name": "awareness",
                "effectiveness_kpi": "metric123",
                "efficiency_kpi": "metric456",
                "objective": "Increase awareness",
            },
            {
                "funnel_step_num": 2,
                "funnel_step_name": "consideration",
                "effectiveness_kpi": "metric789",
                "efficiency_kpi": "metric101",
                "objective": "Drive consideration",
            },
        ]
        mock_firestore_service.list_funnel_steps.return_value = mock_funnel_steps
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.get(
            "/api/v1/firestore/funnel-steps/account123/organization"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["account_id"] == "account123"
        assert data["funnel_type"] == "organization"
        assert data["total"] == 2
        assert len(data["funnel_steps"]) == 2

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.list_funnel_steps.assert_called_once_with(
            account_id="account123",
            funnel_type="organization",
            big_bet_name=None,
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_get_funnel_step_success(self, client, mock_firestore_service):
        """Test getting a specific funnel step successfully."""
        mock_funnel_step = {
            "funnel_step_name": "conversion",
            "effectiveness_kpi": "metric999",
            "efficiency_kpi": "metric888",
            "objective": "Drive conversions",
        }
        mock_firestore_service.get_funnel_step.return_value = mock_funnel_step
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.get(
            "/api/v1/firestore/funnel-steps/account123/organization/3"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["account_id"] == "account123"
        assert data["funnel_type"] == "organization"
        assert data["funnel_step_num"] == 3
        assert data["funnel_step_data"] == mock_funnel_step

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.get_funnel_step.assert_called_once_with(
            account_id="account123",
            funnel_type="organization",
            big_bet_name=None,
            funnel_step_num=3,
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_get_funnel_step_not_found(self, client, mock_firestore_service):
        """Test getting a funnel step that doesn't exist."""
        mock_firestore_service.get_funnel_step.return_value = None
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.get(
            "/api/v1/firestore/funnel-steps/account123/organization/999"
        )

        assert response.status_code == 404
        assert "Funnel step not found" in response.json()["detail"]

        # Clean up
        app.dependency_overrides.clear()

    def test_update_funnel_step_success(self, client, mock_firestore_service):
        """Test updating a funnel step successfully."""
        mock_firestore_service.update_funnel_step.return_value = True
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        funnel_step_request = {
            "account_id": "account123",
            "funnel_type": "organization",
            "funnel_step_num": 2,
            "funnel_step_name": "loyalty",
            "effectiveness_kpi": "metric111",
            "efficiency_kpi": "metric222",
            "objective": "Build customer loyalty",
        }

        response = client.put(
            "/api/v1/firestore/funnel-steps/account123/organization/2",
            json=funnel_step_request,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "updated successfully" in data["message"]

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.update_funnel_step.assert_called_once_with(
            account_id="account123",
            funnel_type="organization",
            big_bet_name=None,
            funnel_step_num=2,
            funnel_step_data={
                "funnel_step_name": "loyalty",
                "effectiveness_kpi": "metric111",
                "efficiency_kpi": "metric222",
                "objective": "Build customer loyalty",
            },
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_delete_funnel_step_success(self, client, mock_firestore_service):
        """Test deleting a funnel step successfully."""
        mock_firestore_service.delete_funnel_step.return_value = True
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.delete(
            "/api/v1/firestore/funnel-steps/account123/organization/2"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "deleted successfully" in data["message"]

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.delete_funnel_step.assert_called_once_with(
            account_id="account123",
            funnel_type="organization",
            big_bet_name=None,
            funnel_step_num=2,
        )

        # Clean up
        app.dependency_overrides.clear()


class TestChannelEndpoints:
    """Test suite for channel endpoints."""

    def test_create_channel_success(self, client, mock_firestore_service):
        """Test creating a channel successfully."""
        mock_channel_data = {
            "channel_name": "email",
            "effectiveness_kpi": "metric123",
            "efficiency_kpi": "metric456",
            "supporting_metrics": ["metric789", "metric101"],
        }
        mock_firestore_service.create_channel.return_value = mock_channel_data
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        create_request = {
            "channel_name": "email",
            "effectiveness_kpi": "metric123",
            "efficiency_kpi": "metric456",
            "supporting_metrics": ["metric789", "metric101"],
        }

        response = client.post(
            "/api/v1/firestore/channels?account_id=account123&funnel_type=organization&funnel_step_num=1",
            json=create_request,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["account_id"] == "account123"
        assert data["funnel_type"] == "organization"
        assert data["funnel_step_num"] == 1
        assert data["channel_name"] == "email"
        assert data["channel_data"] == mock_channel_data

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.create_channel.assert_called_once_with(
            account_id="account123",
            funnel_type="organization",
            big_bet_name=None,
            funnel_step_num=1,
            channel_name="email",
            channel_data=create_request,
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_create_channel_already_exists(self, client, mock_firestore_service):
        """Test creating a channel that already exists."""
        mock_firestore_service.create_channel.return_value = None
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        create_request = {
            "channel_name": "email",
            "effectiveness_kpi": "metric123",
            "efficiency_kpi": "metric456",
            "supporting_metrics": ["metric789"],
        }

        response = client.post(
            "/api/v1/firestore/channels?account_id=account123&funnel_type=organization&funnel_step_num=1",
            json=create_request,
        )

        assert response.status_code == 400
        assert "Channel already exists" in response.json()["detail"]

        # Clean up
        app.dependency_overrides.clear()

    def test_get_channel_success(self, client, mock_firestore_service):
        """Test getting a channel successfully."""
        mock_channel_data = {
            "effectiveness_kpi": "metric123",
            "efficiency_kpi": "metric456",
            "supporting_metrics": ["metric789", "metric101"],
        }
        mock_firestore_service.get_channel.return_value = mock_channel_data
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.get(
            "/api/v1/firestore/channels/email?account_id=account123&funnel_type=organization&funnel_step_num=1"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["account_id"] == "account123"
        assert data["funnel_type"] == "organization"
        assert data["funnel_step_num"] == 1
        assert data["channel_name"] == "email"
        assert data["channel_data"] == mock_channel_data

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.get_channel.assert_called_once_with(
            account_id="account123",
            funnel_type="organization",
            big_bet_name=None,
            funnel_step_num=1,
            channel_name="email",
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_get_channel_not_found(self, client, mock_firestore_service):
        """Test getting a channel that doesn't exist."""
        mock_firestore_service.get_channel.return_value = None
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.get(
            "/api/v1/firestore/channels/nonexistent?account_id=account123&funnel_type=organization&funnel_step_num=1"
        )

        assert response.status_code == 404
        assert "Channel not found" in response.json()["detail"]

        # Clean up
        app.dependency_overrides.clear()

    def test_list_channels_success(self, client, mock_firestore_service):
        """Test listing channels successfully."""
        mock_channels = [
            {
                "channel_name": "email",
                "effectiveness_kpi": "metric123",
                "efficiency_kpi": "metric456",
                "supporting_metrics": ["metric789"],
            },
            {
                "channel_name": "social",
                "effectiveness_kpi": "metric234",
                "efficiency_kpi": "metric567",
                "supporting_metrics": ["metric890"],
            },
        ]
        mock_firestore_service.list_channels.return_value = mock_channels
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.get(
            "/api/v1/firestore/channels?account_id=account123&funnel_type=organization&funnel_step_num=1"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["channels"]) == 2

        # Clean up
        app.dependency_overrides.clear()

    def test_update_channel_success(self, client, mock_firestore_service):
        """Test updating a channel successfully."""
        mock_updated_data = {
            "effectiveness_kpi": "metric999",
            "efficiency_kpi": "metric456",
            "supporting_metrics": ["metric789", "metric101"],
        }
        mock_firestore_service.update_channel.return_value = mock_updated_data
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_request = {"effectiveness_kpi": "metric999"}

        response = client.put(
            "/api/v1/firestore/channels/email?account_id=account123&funnel_type=organization&funnel_step_num=1",
            json=update_request,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["account_id"] == "account123"
        assert data["funnel_type"] == "organization"
        assert data["funnel_step_num"] == 1
        assert data["channel_name"] == "email"
        assert data["channel_data"] == mock_updated_data

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.update_channel.assert_called_once_with(
            account_id="account123",
            funnel_type="organization",
            big_bet_name=None,
            funnel_step_num=1,
            channel_name="email",
            channel_data=update_request,
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_update_channel_not_found(self, client, mock_firestore_service):
        """Test updating a channel that doesn't exist."""
        mock_firestore_service.update_channel.return_value = None
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_request = {"effectiveness_kpi": "metric999"}

        response = client.put(
            "/api/v1/firestore/channels/nonexistent?account_id=account123&funnel_type=organization&funnel_step_num=1",
            json=update_request,
        )

        assert response.status_code == 404
        assert "Channel not found" in response.json()["detail"]

        # Clean up
        app.dependency_overrides.clear()

    def test_delete_channel_success(self, client, mock_firestore_service):
        """Test deleting a channel successfully."""
        mock_firestore_service.delete_channel.return_value = True
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.delete(
            "/api/v1/firestore/channels/email?account_id=account123&funnel_type=organization&funnel_step_num=1"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "deleted successfully" in data["message"]

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.delete_channel.assert_called_once_with(
            account_id="account123",
            funnel_type="organization",
            big_bet_name=None,
            funnel_step_num=1,
            channel_name="email",
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_delete_channel_not_found(self, client, mock_firestore_service):
        """Test deleting a channel that doesn't exist."""
        mock_firestore_service.delete_channel.return_value = False
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.delete(
            "/api/v1/firestore/channels/nonexistent?account_id=account123&funnel_type=organization&funnel_step_num=1"
        )

        assert response.status_code == 404
        assert "Channel not found" in response.json()["detail"]

        # Clean up
        app.dependency_overrides.clear()

    def test_channel_big_bet_funnel(self, client, mock_firestore_service):
        """Test channel operations with big bet funnel."""
        mock_channel_data = {
            "channel_name": "email",
            "effectiveness_kpi": "metric123",
            "efficiency_kpi": "metric456",
            "supporting_metrics": ["metric789"],
        }
        mock_firestore_service.create_channel.return_value = mock_channel_data
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        create_request = {
            "channel_name": "email",
            "effectiveness_kpi": "metric123",
            "efficiency_kpi": "metric456",
            "supporting_metrics": ["metric789"],
        }

        response = client.post(
            "/api/v1/firestore/channels?account_id=account123&funnel_type=big_bet&funnel_step_num=1&big_bet_name=expansion",
            json=create_request,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["funnel_type"] == "big_bet"
        assert data["big_bet_name"] == "expansion"

        mock_firestore_service.create_channel.assert_called_once_with(
            account_id="account123",
            funnel_type="big_bet",
            big_bet_name="expansion",
            funnel_step_num=1,
            channel_name="email",
            channel_data=create_request,
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_channel_invalid_funnel_type(self, client, mock_firestore_service):
        """Test channel operations with invalid funnel type."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        create_request = {
            "channel_name": "email",
            "effectiveness_kpi": "metric123",
            "efficiency_kpi": "metric456",
            "supporting_metrics": ["metric789"],
        }

        response = client.post(
            "/api/v1/firestore/channels?account_id=account123&funnel_type=invalid&funnel_step_num=1",
            json=create_request,
        )

        assert response.status_code == 400
        assert "Invalid funnel_type" in response.json()["detail"]

        # Clean up
        app.dependency_overrides.clear()

    def test_channel_missing_big_bet_name(self, client, mock_firestore_service):
        """Test channel operations missing big bet name when required."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        create_request = {
            "channel_name": "email",
            "effectiveness_kpi": "metric123",
            "efficiency_kpi": "metric456",
            "supporting_metrics": ["metric789"],
        }

        response = client.post(
            "/api/v1/firestore/channels?account_id=account123&funnel_type=big_bet&funnel_step_num=1",
            json=create_request,
        )

        assert response.status_code == 400
        assert "big_bet_name is required" in response.json()["detail"]

        # Clean up
        app.dependency_overrides.clear()


class TestTacticEndpoints:
    """Test suite for tactic endpoints."""

    @pytest.fixture(autouse=True)
    def setup_auth(self, mock_super_admin_context):
        """Provide super-admin auth override for all tests in this class."""
        from src.kene_api.auth.dependencies import get_current_user as gcu
        app.dependency_overrides[gcu] = lambda: mock_super_admin_context
        yield
        app.dependency_overrides.pop(gcu, None)

    def test_create_tactic_success(self, client, mock_firestore_service):
        """Test creating a tactic successfully."""
        mock_created_data = {
            "tactic_name": "email_campaign",
            "effectiveness_kpi": "metric123",
            "efficiency_kpi": "metric456",
            "supporting_metrics": ["metric789"],
        }
        mock_firestore_service.create_tactic.return_value = mock_created_data
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        create_request = {
            "tactic_name": "email_campaign",
            "effectiveness_kpi": "metric123",
            "efficiency_kpi": "metric456",
            "supporting_metrics": ["metric789"],
        }

        response = client.post(
            "/api/v1/firestore/tactics?account_id=account123&funnel_type=organization&funnel_step_num=1&channel_name=email",
            json=create_request,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["account_id"] == "account123"
        assert data["funnel_type"] == "organization"
        assert data["funnel_step_num"] == 1
        assert data["channel_name"] == "email"
        assert data["tactic_name"] == "email_campaign"
        assert data["tactic_data"] == mock_created_data

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.create_tactic.assert_called_once_with(
            account_id="account123",
            funnel_type="organization",
            big_bet_name=None,
            funnel_step_num=1,
            channel_name="email",
            tactic_name="email_campaign",
            tactic_data=create_request,
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_create_tactic_already_exists(self, client, mock_firestore_service):
        """Test creating a tactic that already exists."""
        mock_firestore_service.create_tactic.return_value = None
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        create_request = {
            "tactic_name": "existing_tactic",
            "effectiveness_kpi": "metric123",
            "efficiency_kpi": "metric456",
            "supporting_metrics": ["metric789"],
        }

        response = client.post(
            "/api/v1/firestore/tactics?account_id=account123&funnel_type=organization&funnel_step_num=1&channel_name=email",
            json=create_request,
        )

        assert response.status_code == 400
        data = response.json()
        assert "already exists" in data["detail"]

        # Clean up
        app.dependency_overrides.clear()

    def test_get_tactic_success(self, client, mock_firestore_service):
        """Test getting a tactic successfully."""
        mock_tactic_data = {
            "effectiveness_kpi": "metric123",
            "efficiency_kpi": "metric456",
            "supporting_metrics": ["metric789"],
        }
        mock_firestore_service.get_tactic.return_value = mock_tactic_data
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.get(
            "/api/v1/firestore/tactics/email_campaign?account_id=account123&funnel_type=organization&funnel_step_num=1&channel_name=email"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["tactic_name"] == "email_campaign"
        assert data["tactic_data"] == mock_tactic_data

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.get_tactic.assert_called_once_with(
            account_id="account123",
            funnel_type="organization",
            big_bet_name=None,
            funnel_step_num=1,
            channel_name="email",
            tactic_name="email_campaign",
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_get_tactic_not_found(self, client, mock_firestore_service):
        """Test getting a tactic that doesn't exist."""
        mock_firestore_service.get_tactic.return_value = None
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.get(
            "/api/v1/firestore/tactics/nonexistent?account_id=account123&funnel_type=organization&funnel_step_num=1&channel_name=email"
        )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Tactic not found"

        # Clean up
        app.dependency_overrides.clear()

    def test_list_tactics_success(self, client, mock_firestore_service):
        """Test listing tactics successfully."""
        mock_tactics = [
            {
                "tactic_name": "email_campaign",
                "effectiveness_kpi": "metric123",
                "efficiency_kpi": "metric456",
                "supporting_metrics": ["metric789"],
            },
            {
                "tactic_name": "social_media",
                "effectiveness_kpi": "metric234",
                "efficiency_kpi": "metric567",
                "supporting_metrics": ["metric890"],
            },
        ]
        mock_firestore_service.list_tactics.return_value = mock_tactics
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.get(
            "/api/v1/firestore/tactics?account_id=account123&funnel_type=organization&funnel_step_num=1&channel_name=email"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tactics"] == mock_tactics
        assert data["total"] == 2

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.list_tactics.assert_called_once_with(
            account_id="account123",
            funnel_type="organization",
            big_bet_name=None,
            funnel_step_num=1,
            channel_name="email",
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_update_tactic_success(self, client, mock_firestore_service):
        """Test updating a tactic successfully."""
        mock_updated_data = {
            "effectiveness_kpi": "metric999",
            "efficiency_kpi": "metric456",
            "supporting_metrics": ["metric789", "metric101"],
        }
        mock_firestore_service.update_tactic.return_value = mock_updated_data
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_request = {"effectiveness_kpi": "metric999"}

        response = client.put(
            "/api/v1/firestore/tactics/email_campaign?account_id=account123&funnel_type=organization&funnel_step_num=1&channel_name=email",
            json=update_request,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["tactic_name"] == "email_campaign"
        assert data["tactic_data"] == mock_updated_data

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.update_tactic.assert_called_once_with(
            account_id="account123",
            funnel_type="organization",
            big_bet_name=None,
            funnel_step_num=1,
            channel_name="email",
            tactic_name="email_campaign",
            tactic_data=update_request,
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_update_tactic_not_found(self, client, mock_firestore_service):
        """Test updating a tactic that doesn't exist."""
        mock_firestore_service.update_tactic.return_value = None
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_request = {"effectiveness_kpi": "metric999"}

        response = client.put(
            "/api/v1/firestore/tactics/nonexistent?account_id=account123&funnel_type=organization&funnel_step_num=1&channel_name=email",
            json=update_request,
        )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Tactic not found"

        # Clean up
        app.dependency_overrides.clear()

    def test_delete_tactic_success(self, client, mock_firestore_service):
        """Test deleting a tactic successfully."""
        mock_firestore_service.delete_tactic.return_value = True
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.delete(
            "/api/v1/firestore/tactics/email_campaign?account_id=account123&funnel_type=organization&funnel_step_num=1&channel_name=email"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "deleted successfully" in data["message"]

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.delete_tactic.assert_called_once_with(
            account_id="account123",
            funnel_type="organization",
            big_bet_name=None,
            funnel_step_num=1,
            channel_name="email",
            tactic_name="email_campaign",
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_delete_tactic_not_found(self, client, mock_firestore_service):
        """Test deleting a tactic that doesn't exist."""
        mock_firestore_service.delete_tactic.return_value = False
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.delete(
            "/api/v1/firestore/tactics/nonexistent?account_id=account123&funnel_type=organization&funnel_step_num=1&channel_name=email"
        )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Tactic not found"

        # Clean up
        app.dependency_overrides.clear()

    def test_tactic_big_bet_funnel(self, client, mock_firestore_service):
        """Test tactic operations with big bet funnel."""
        mock_tactic_data = {
            "effectiveness_kpi": "metric123",
            "efficiency_kpi": "metric456",
            "supporting_metrics": ["metric789"],
        }
        mock_firestore_service.get_tactic.return_value = mock_tactic_data
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.get(
            "/api/v1/firestore/tactics/test_tactic?account_id=account123&funnel_type=big_bet&funnel_step_num=1&channel_name=email&big_bet_name=new_product"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["funnel_type"] == "big_bet"
        assert data["big_bet_name"] == "new_product"

        mock_firestore_service.get_tactic.assert_called_once_with(
            account_id="account123",
            funnel_type="big_bet",
            big_bet_name="new_product",
            funnel_step_num=1,
            channel_name="email",
            tactic_name="test_tactic",
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_tactic_invalid_funnel_type(self, client, mock_firestore_service):
        """Test tactic operations with invalid funnel type."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.get(
            "/api/v1/firestore/tactics/test_tactic?account_id=account123&funnel_type=invalid&funnel_step_num=1&channel_name=email"
        )

        assert response.status_code == 400
        data = response.json()
        assert "Invalid funnel_type" in data["detail"]

        # Clean up
        app.dependency_overrides.clear()

    def test_tactic_missing_big_bet_name(self, client, mock_firestore_service):
        """Test tactic operations missing big bet name when required."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        response = client.get(
            "/api/v1/firestore/tactics/test_tactic?account_id=account123&funnel_type=big_bet&funnel_step_num=1&channel_name=email"
        )

        assert response.status_code == 400
        data = response.json()
        assert "big_bet_name is required" in data["detail"]

        # Clean up
        app.dependency_overrides.clear()

    def test_set_nested_field_success(self, client, mock_firestore_service):
        """Test set operation for nested field successfully."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_data = {
            "update": {
                "operator": "set",
                "field": "permissions.accounts.newAccountId",
                "value": "admin",
            }
        }

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert (
            "Document test_doc updated successfully - Set nested field operation on 'permissions.accounts.newAccountId'"
            in data["message"]
        )

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.set_nested_field.assert_called_once_with(
            collection="test_collection",
            document_id="test_doc",
            field_path="permissions.accounts.newAccountId",
            value="admin",
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_set_nested_field_complex_value(self, client, mock_firestore_service):
        """Test set operation with complex nested object value."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        complex_value = {
            "role": "admin",
            "permissions": ["read", "write"],
            "created_at": "2025-01-01T00:00:00Z",
        }

        update_data = {
            "update": {
                "operator": "set",
                "field": "user_data.profile.settings",
                "value": complex_value,
            }
        }

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert (
            "Document test_doc updated successfully - Set nested field operation on 'user_data.profile.settings'"
            in data["message"]
        )

        mock_firestore_service.set_nested_field.assert_called_once_with(
            collection="test_collection",
            document_id="test_doc",
            field_path="user_data.profile.settings",
            value=complex_value,
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_set_missing_field(self, client, mock_firestore_service):
        """Test set operation with missing field parameter."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_data = {"update": {"operator": "set", "value": "admin"}}

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 400
        assert (
            "set operation requires 'field' and 'value' parameters"
            in response.json()["detail"]
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_set_missing_value(self, client, mock_firestore_service):
        """Test set operation with missing value parameter."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_data = {
            "update": {"operator": "set", "field": "permissions.accounts.newAccountId"}
        }

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 400
        assert (
            "set operation requires 'field' and 'value' parameters"
            in response.json()["detail"]
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_set_empty_field_path(self, client, mock_firestore_service):
        """Test set operation with empty field path."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_data = {"update": {"operator": "set", "field": "", "value": "admin"}}

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 400
        assert (
            "set operation requires 'field' and 'value' parameters"
            in response.json()["detail"]
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_set_none_value_allowed(self, client, mock_firestore_service):
        """Test set operation with None value (should be allowed)."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_data = {
            "update": {
                "operator": "set",
                "field": "permissions.accounts.removedAccountId",
                "value": None,
            }
        }

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert (
            "Document test_doc updated successfully - Set nested field operation on 'permissions.accounts.removedAccountId'"
            in data["message"]
        )

        mock_firestore_service.set_nested_field.assert_called_once_with(
            collection="test_collection",
            document_id="test_doc",
            field_path="permissions.accounts.removedAccountId",
            value=None,
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_set_firestore_unavailable(self, client, mock_firestore_service):
        """Test set operation when Firestore is unavailable."""
        mock_firestore_service.health_check.return_value = False
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_data = {
            "update": {
                "operator": "set",
                "field": "permissions.accounts.newAccountId",
                "value": "admin",
            }
        }

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 503
        assert "Firestore service unavailable" in response.json()["detail"]

        # Clean up
        app.dependency_overrides.clear()

    def test_set_operation_failed(self, client, mock_firestore_service):
        """Test set operation when the operation fails."""
        mock_firestore_service.set_nested_field.return_value = False
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_data = {
            "update": {
                "operator": "set",
                "field": "permissions.accounts.newAccountId",
                "value": "admin",
            }
        }

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 404
        assert "Document not found or operation failed" in response.json()["detail"]

        # Clean up
        app.dependency_overrides.clear()

    def test_invalid_update_operator_includes_set(self, client, mock_firestore_service):
        """Test that error message includes 'set' in supported operators."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_data = {
            "update": {
                "operator": "invalidOperator",
                "field": "accounts",
                "value": {"test": "value"},
            }
        }

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 400
        assert (
            "Unsupported update operator: invalidOperator" in response.json()["detail"]
        )
        assert (
            "Supported operators: arrayUnion, replaceOne, set"
            in response.json()["detail"]
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_update_subcollection_document_set_nested_field(
        self, client, mock_firestore_service
    ):
        """Test set operation on subcollection document for nested field."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_data = {
            "update": {
                "operator": "set",
                "field": "config.notification_settings.email_enabled",
                "value": True,
            }
        }

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc/notifications/email_notifications",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert (
            "Subcollection document email_notifications updated successfully - Set nested field operation on 'config.notification_settings.email_enabled'"
            in data["message"]
        )

        mock_firestore_service.health_check.assert_called_once()
        mock_firestore_service.set_nested_field_subcollection.assert_called_once_with(
            collection="test_collection",
            document_id="test_doc",
            subcollection="notifications",
            subdocument_id="email_notifications",
            field_path="config.notification_settings.email_enabled",
            value=True,
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_update_subcollection_document_set_complex_object(
        self, client, mock_firestore_service
    ):
        """Test set operation on subcollection document with complex object."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        complex_config = {
            "frequency": "daily",
            "templates": ["welcome", "reminder"],
            "settings": {"html_enabled": True, "tracking_enabled": False},
        }

        update_data = {
            "update": {
                "operator": "set",
                "field": "notification_config.email",
                "value": complex_config,
            }
        }

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc/notifications/email_notifications",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert (
            "Subcollection document email_notifications updated successfully - Set nested field operation on 'notification_config.email'"
            in data["message"]
        )

        mock_firestore_service.set_nested_field_subcollection.assert_called_once_with(
            collection="test_collection",
            document_id="test_doc",
            subcollection="notifications",
            subdocument_id="email_notifications",
            field_path="notification_config.email",
            value=complex_config,
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_update_subcollection_document_set_missing_field(
        self, client, mock_firestore_service
    ):
        """Test set operation on subcollection document with missing field parameter."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_data = {"update": {"operator": "set", "value": True}}

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc/notifications/email_notifications",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 400
        assert (
            "set operation requires 'field' and 'value' parameters"
            in response.json()["detail"]
        )

        # Clean up
        app.dependency_overrides.clear()

    def test_update_subcollection_document_set_operation_failed(
        self, client, mock_firestore_service
    ):
        """Test set operation on subcollection document when operation fails."""
        mock_firestore_service.set_nested_field_subcollection.return_value = False
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        update_data = {
            "update": {
                "operator": "set",
                "field": "config.notification_settings.email_enabled",
                "value": True,
            }
        }

        response = client.put(
            "/api/v1/firestore/documents/test_collection/test_doc/notifications/email_notifications",
            json=update_data,
            params={"account_id": "test_account"},
        )

        assert response.status_code == 404
        assert "Document not found or operation failed" in response.json()["detail"]

        # Clean up
        app.dependency_overrides.clear()


class TestFirestoreEndpointAuth:
    """Auth/authz matrix for the 10 generic Firestore handlers.

    Each test covers one (endpoint, scenario) pair. The full matrix is:
      endpoints: create / get / update / delete / query / list  (6 top-level)
                 + create / get / update / delete subcollection  (4 subcollection)
      scenarios: 401-no-auth, 403-wrong-user, 403-non-users-collection,
                 200-self-user-doc, 200-super-admin
    """

    # ── helpers ──────────────────────────────────────────────────────────────

    @pytest.fixture(autouse=True)
    def setup_firestore(self, mock_firestore_service):
        """Override Firestore service for all tests in this class."""
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service
        yield
        app.dependency_overrides.pop(get_firestore_service, None)

    @pytest.fixture
    def raw_client(self):
        """TestClient with NO auth override — simulates unauthenticated requests."""
        return TestClient(app)

    @pytest.fixture
    def regular_user(self, mock_regular_user_context):
        """TestClient whose get_current_user returns a regular (non-super-admin) user."""
        from src.kene_api.auth.dependencies import get_current_user as gcu
        app.dependency_overrides[gcu] = lambda: mock_regular_user_context
        yield TestClient(app)
        app.dependency_overrides.pop(gcu, None)

    @pytest.fixture
    def super_admin_user(self, mock_super_admin_context):
        """TestClient whose get_current_user returns a super-admin user."""
        from src.kene_api.auth.dependencies import get_current_user as gcu
        app.dependency_overrides[gcu] = lambda: mock_super_admin_context
        yield TestClient(app)
        app.dependency_overrides.pop(gcu, None)

    # ── 401 — no auth ────────────────────────────────────────────────────────

    @pytest.mark.parametrize("method,path,kwargs", [
        ("post",   "/api/v1/firestore/documents",
         {"json": {"account_id": "uid1", "collection": "users", "document_id": "uid1", "data": {}}}),
        ("get",    "/api/v1/firestore/documents/users/uid1", {}),
        ("put",    "/api/v1/firestore/documents/users/uid1",
         {"json": {"field": "x"}, "params": {"account_id": "uid1"}}),
        ("delete", "/api/v1/firestore/documents/users/uid1",
         {"params": {"account_id": "uid1"}}),
        ("post",   "/api/v1/firestore/documents/query",
         {"json": {"account_id": "uid1", "collection": "users/uid1/prefs"}}),
        ("get",    "/api/v1/firestore/collections/users/documents",
         {"params": {"account_id": "uid1"}}),
    ])
    def test_401_no_auth(self, raw_client, method, path, kwargs):
        """All six handlers return 401 when no Authorization header is sent."""
        response = getattr(raw_client, method)(path, **kwargs)
        assert response.status_code == 401

    # ── 403 — authenticated but wrong user ───────────────────────────────────

    def test_403_create_wrong_user_doc(self, regular_user):
        """create_document: 403 when trying to create a different user's doc."""
        response = regular_user.post(
            "/api/v1/firestore/documents",
            json={"account_id": "ANOTHER_UID", "collection": "users", "document_id": "ANOTHER_UID", "data": {}},
        )
        assert response.status_code == 403

    def test_403_get_wrong_user_doc(self, regular_user):
        """get_document: 403 when fetching a different user's doc."""
        response = regular_user.get("/api/v1/firestore/documents/users/ANOTHER_UID")
        assert response.status_code == 403

    def test_403_update_wrong_user_doc(self, regular_user):
        """update_document: 403 when updating a different user's doc."""
        response = regular_user.put(
            "/api/v1/firestore/documents/users/ANOTHER_UID",
            json={"name": "hack"},
            params={"account_id": "ANOTHER_UID"},
        )
        assert response.status_code == 403

    def test_403_delete_wrong_user_doc(self, regular_user):
        """delete_document: 403 when deleting a different user's doc."""
        response = regular_user.delete(
            "/api/v1/firestore/documents/users/ANOTHER_UID",
            params={"account_id": "ANOTHER_UID"},
        )
        assert response.status_code == 403

    # ── 403 — non-users collection ───────────────────────────────────────────

    @pytest.mark.parametrize("collection", ["accounts", "organizations", "agent_configs", "arbitrary"])
    def test_403_non_users_collection_create(self, regular_user, collection):
        """create_document: 403 for any non-users collection."""
        response = regular_user.post(
            "/api/v1/firestore/documents",
            json={"account_id": "test_account", "collection": collection, "document_id": "test_doc_uid", "data": {}},
        )
        assert response.status_code == 403

    @pytest.mark.parametrize("collection", ["accounts", "organizations", "agent_configs"])
    def test_403_non_users_collection_get(self, regular_user, collection):
        """get_document: 403 for non-users collections."""
        response = regular_user.get(f"/api/v1/firestore/documents/{collection}/some_doc")
        assert response.status_code == 403

    @pytest.mark.parametrize("collection", ["accounts", "organizations"])
    def test_403_non_users_collection_update(self, regular_user, collection):
        """update_document: 403 for non-users collections."""
        response = regular_user.put(
            f"/api/v1/firestore/documents/{collection}/some_doc",
            json={"field": "value"},
            params={"account_id": "some_id"},
        )
        assert response.status_code == 403

    @pytest.mark.parametrize("collection", ["accounts", "organizations"])
    def test_403_non_users_collection_delete(self, regular_user, collection):
        """delete_document: 403 for non-users collections."""
        response = regular_user.delete(
            f"/api/v1/firestore/documents/{collection}/some_doc",
            params={"account_id": "some_id"},
        )
        assert response.status_code == 403

    @pytest.mark.parametrize("collection", ["accounts", "users"])
    def test_403_non_self_collection_query(self, regular_user, collection):
        """query_documents: 403 when collection is not caller's own subcollection."""
        response = regular_user.post(
            "/api/v1/firestore/documents/query",
            json={"account_id": "test_account", "collection": collection},
        )
        assert response.status_code == 403

    def test_403_list_collection_non_super_admin(self, regular_user):
        """list_collection_documents: 403 for non-super-admin (any collection)."""
        response = regular_user.get(
            "/api/v1/firestore/collections/users/documents",
            params={"account_id": "test_user_uid"},
        )
        assert response.status_code == 403

    # ── 200 — self-user-doc scoped calls ─────────────────────────────────────

    def test_200_create_own_user_doc(self, regular_user, mock_regular_user_context):
        """create_document: 200 when creating the caller's own user doc."""
        own_uid = mock_regular_user_context.user_id
        response = regular_user.post(
            "/api/v1/firestore/documents",
            json={"account_id": own_uid, "collection": "users", "document_id": own_uid, "data": {"name": "Alice"}},
        )
        assert response.status_code == 200

    def test_200_get_own_user_doc(self, regular_user, mock_regular_user_context):
        """get_document: 200 when fetching the caller's own user doc."""
        own_uid = mock_regular_user_context.user_id
        response = regular_user.get(f"/api/v1/firestore/documents/users/{own_uid}")
        assert response.status_code == 200

    def test_200_update_own_user_doc(self, regular_user, mock_regular_user_context):
        """update_document: 200 when updating the caller's own user doc."""
        own_uid = mock_regular_user_context.user_id
        response = regular_user.put(
            f"/api/v1/firestore/documents/users/{own_uid}",
            json={"name": "Alice"},
            params={"account_id": own_uid},
        )
        assert response.status_code == 200

    def test_403_delete_own_user_doc_blocked(self, regular_user, mock_regular_user_context):
        """delete_document: 403 even for own user doc — deletion is blocked entirely on users/ collection.

        Account deletion must go through the dedicated account-deletion API to preserve audit trails.
        """
        own_uid = mock_regular_user_context.user_id
        response = regular_user.delete(
            f"/api/v1/firestore/documents/users/{own_uid}",
            params={"account_id": own_uid},
        )
        assert response.status_code == 403

    def test_200_query_own_subcollection(self, regular_user, mock_regular_user_context):
        """query_documents: 200 when querying the caller's own user subcollection."""
        own_uid = mock_regular_user_context.user_id
        response = regular_user.post(
            "/api/v1/firestore/documents/query",
            json={"account_id": own_uid, "collection": f"users/{own_uid}/notifications"},
        )
        assert response.status_code == 200

    # ── 200 — super-admin bypasses scope checks ───────────────────────────────

    @pytest.mark.parametrize("collection", ["accounts", "organizations", "agent_configs", "users"])
    def test_200_super_admin_can_access_any_collection_create(self, super_admin_user, collection):
        """create_document: super-admin bypasses all scope checks."""
        response = super_admin_user.post(
            "/api/v1/firestore/documents",
            json={"account_id": "any_account", "collection": collection, "document_id": "any_doc", "data": {}},
        )
        assert response.status_code == 200

    def test_200_super_admin_list_collection(self, super_admin_user):
        """list_collection_documents: super-admin can enumerate any collection."""
        response = super_admin_user.get(
            "/api/v1/firestore/collections/users/documents",
            params={"account_id": "ignored"},
        )
        assert response.status_code == 200

    @pytest.mark.parametrize("method,path,kwargs", [
        ("get",  "/api/v1/firestore/documents/accounts/some_doc", {}),
        ("put",  "/api/v1/firestore/documents/accounts/some_doc",
         {"json": {"field": "v"}, "params": {"account_id": "ignored"}}),
        ("delete", "/api/v1/firestore/documents/accounts/some_doc",
         {"params": {"account_id": "ignored"}}),
        ("post", "/api/v1/firestore/documents/query",
         {"json": {"account_id": "ignored", "collection": "accounts"}}),
    ])
    def test_200_super_admin_get_update_delete_query(
        self, super_admin_user, method, path, kwargs
    ):
        """super-admin bypasses scope checks on get/update/delete/query handlers."""
        response = getattr(super_admin_user, method)(path, **kwargs)
        assert response.status_code == 200

    def test_403_super_admin_delete_users_doc_blocked(self, super_admin_user):
        """delete_document: even a super-admin cannot delete a users/ doc here.

        The users/ deletion block is unconditional — account deletion must go
        through the dedicated account-deletion API.
        """
        response = super_admin_user.delete(
            "/api/v1/firestore/documents/users/any_uid",
            params={"account_id": "ignored"},
        )
        assert response.status_code == 403

    # ── subcollection handlers — 401 / 403 / 200 ─────────────────────────────

    @pytest.mark.parametrize("method,path,kwargs", [
        ("post",   "/api/v1/firestore/documents/users/uid1/notifications",
         {"json": {"f": "x"}, "params": {"account_id": "uid1"}}),
        ("get",    "/api/v1/firestore/documents/users/uid1/notifications/sub1", {}),
        ("put",    "/api/v1/firestore/documents/users/uid1/notifications/sub1",
         {"json": {"f": "x"}, "params": {"account_id": "uid1"}}),
        ("delete", "/api/v1/firestore/documents/users/uid1/notifications/sub1",
         {"params": {"account_id": "uid1"}}),
    ])
    def test_401_no_auth_subcollection(self, raw_client, method, path, kwargs):
        """All four subcollection handlers return 401 when unauthenticated."""
        response = getattr(raw_client, method)(path, **kwargs)
        assert response.status_code == 401

    @pytest.mark.parametrize("method,path,kwargs", [
        ("post",   "/api/v1/firestore/documents/users/ANOTHER_UID/notifications",
         {"json": {"f": "x"}, "params": {"account_id": "ANOTHER_UID"}}),
        ("get",    "/api/v1/firestore/documents/users/ANOTHER_UID/notifications/sub1", {}),
        ("put",    "/api/v1/firestore/documents/users/ANOTHER_UID/notifications/sub1",
         {"json": {"f": "x"}, "params": {"account_id": "ANOTHER_UID"}}),
        ("delete", "/api/v1/firestore/documents/users/ANOTHER_UID/notifications/sub1",
         {"params": {"account_id": "ANOTHER_UID"}}),
    ])
    def test_403_subcollection_wrong_user(self, regular_user, method, path, kwargs):
        """All four subcollection handlers 403 when the parent doc is another user's."""
        response = getattr(regular_user, method)(path, **kwargs)
        assert response.status_code == 403

    @pytest.mark.parametrize("method,path,kwargs", [
        ("post",   "/api/v1/firestore/documents/accounts/acc1/members",
         {"json": {"f": "x"}, "params": {"account_id": "acc1"}}),
        ("get",    "/api/v1/firestore/documents/accounts/acc1/members/sub1", {}),
        ("put",    "/api/v1/firestore/documents/accounts/acc1/members/sub1",
         {"json": {"f": "x"}, "params": {"account_id": "acc1"}}),
        ("delete", "/api/v1/firestore/documents/accounts/acc1/members/sub1",
         {"params": {"account_id": "acc1"}}),
    ])
    def test_403_subcollection_non_users_parent(self, regular_user, method, path, kwargs):
        """All four subcollection handlers 403 when the parent collection is not users/."""
        response = getattr(regular_user, method)(path, **kwargs)
        assert response.status_code == 403

    @pytest.mark.parametrize("method,suffix,kwargs", [
        ("post",   "",      {"json": {"f": "x"}}),
        ("get",    "/sub1", {}),
        ("put",    "/sub1", {"json": {"f": "x"}}),
        ("delete", "/sub1", {}),
    ])
    def test_200_subcollection_self_scope(
        self, regular_user, mock_regular_user_context, method, suffix, kwargs
    ):
        """All four subcollection handlers 200 when scoped to the caller's own user doc."""
        own_uid = mock_regular_user_context.user_id
        path = f"/api/v1/firestore/documents/users/{own_uid}/notifications{suffix}"
        response = getattr(regular_user, method)(
            path, params={"account_id": own_uid}, **kwargs
        )
        assert response.status_code == 200

    # ── DM-81 regression: _reject_protected_user_field_write still fires ─────

    def test_403_protected_field_write_still_blocked_after_auth(self, regular_user, mock_regular_user_context):
        """_reject_protected_user_field_write still rejects roles/permissions writes post-auth."""
        own_uid = mock_regular_user_context.user_id
        response = regular_user.post(
            "/api/v1/firestore/documents",
            json={
                "account_id": own_uid,
                "collection": "users",
                "document_id": own_uid,
                "data": {"roles": ["super_admin"]},
            },
        )
        assert response.status_code == 403
        assert "roles" in response.json()["detail"]
