"""Integration tests for customer profile monitoring keywords."""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from src.kene_api.auth.models import UserContext
from src.kene_api.auth.user_context import get_current_user_context
from src.kene_api.firestore import get_firestore_service
from src.kene_api.main import app


class TestCustomerProfileMonitoring:
    """Test customer profile monitoring keywords CRUD."""

    @pytest.fixture
    def mock_user(self):
        """Create mock user with edit access."""
        return UserContext(
            user_id="test_user",
            email="test@example.com",
            organization_permissions={"org_test": "admin"},
            account_permissions={"acc_test": "edit"},
        )

    @pytest.fixture
    def mock_user_no_access(self):
        """Create mock user without access."""
        return UserContext(
            user_id="test_user_no_access",
            email="notest@example.com",
            organization_permissions={},
            account_permissions={},
        )

    @pytest.fixture
    def mock_firestore_service(self):
        """Create mock Firestore service."""
        mock_service = MagicMock()
        mock_service.get_document.return_value = None
        mock_service.update_document.return_value = None
        return mock_service

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_add_customer_profile_keywords_success(
        self, client, mock_user, mock_firestore_service
    ):
        """Test adding customer profile keywords."""
        # Mock existing document
        mock_firestore_service.get_document.return_value = {
            "account_id": "acc_test",
            "customer_profile_entries": [],
        }

        # Override dependencies
        app.dependency_overrides[get_current_user_context] = lambda: mock_user
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        try:
            response = client.post(
                "/api/v1/monitoring-topics/acc_test/customer-profiles",
                json={
                    "account_id": "acc_test",
                    "customer_profile_entry": {
                        "node_id": "prof_123",
                        "keywords": ["keyword1", "keyword2"],
                    },
                },
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 200
            data = response.json()
            assert (
                data["message"] == "Customer profile keywords added successfully"
            )
            assert data["data"]["customer_profile"]["node_id"] == "prof_123"

            # Verify Firestore was updated
            mock_firestore_service.update_document.assert_called_once()
        finally:
            # Clean up overrides
            app.dependency_overrides.clear()

    def test_add_customer_profile_keywords_no_access(
        self, client, mock_user_no_access, mock_firestore_service
    ):
        """Test adding customer profile keywords without access fails."""
        # Override dependencies
        app.dependency_overrides[get_current_user_context] = lambda: mock_user_no_access
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        try:
            response = client.post(
                "/api/v1/monitoring-topics/acc_test/customer-profiles",
                json={
                    "account_id": "acc_test",
                    "customer_profile_entry": {
                        "node_id": "prof_123",
                        "keywords": ["keyword1"],
                    },
                },
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 403
        finally:
            app.dependency_overrides.clear()

    def test_update_customer_profile_keywords_success(
        self, client, mock_user, mock_firestore_service
    ):
        """Test updating customer profile keywords."""
        # Mock existing document with one entry
        mock_firestore_service.get_document.return_value = {
            "account_id": "acc_test",
            "customer_profile_entries": [
                {"node_id": "prof_123", "keywords": ["old_keyword"]}
            ],
        }

        # Override dependencies
        app.dependency_overrides[get_current_user_context] = lambda: mock_user
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        try:
            response = client.put(
                "/api/v1/monitoring-topics/acc_test/customer-profiles/0",
                json={
                    "account_id": "acc_test",
                    "customer_profile_index": 0,
                    "node_id": "prof_123",
                    "keywords": ["new_keyword1", "new_keyword2"],
                },
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 200
            data = response.json()
            assert (
                data["message"] == "Customer profile keywords updated successfully"
            )
            assert "new_keyword1" in data["data"]["customer_profile"]["keywords"]
        finally:
            app.dependency_overrides.clear()

    def test_update_customer_profile_keywords_invalid_index(
        self, client, mock_user, mock_firestore_service
    ):
        """Test updating customer profile with invalid index fails."""
        # Mock existing document with one entry
        mock_firestore_service.get_document.return_value = {
            "account_id": "acc_test",
            "customer_profile_entries": [
                {"node_id": "prof_123", "keywords": ["keyword1"]}
            ],
        }

        # Override dependencies
        app.dependency_overrides[get_current_user_context] = lambda: mock_user
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        try:
            response = client.put(
                "/api/v1/monitoring-topics/acc_test/customer-profiles/99",
                json={
                    "account_id": "acc_test",
                    "customer_profile_index": 99,
                    "keywords": ["new_keyword"],
                },
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_delete_customer_profile_keywords_success(
        self, client, mock_user, mock_firestore_service
    ):
        """Test deleting customer profile keywords."""
        # Mock existing document
        mock_firestore_service.get_document.return_value = {
            "account_id": "acc_test",
            "customer_profile_entries": [
                {"node_id": "prof_123", "keywords": ["keyword1"]}
            ],
        }

        # Override dependencies
        app.dependency_overrides[get_current_user_context] = lambda: mock_user
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        try:
            response = client.delete(
                "/api/v1/monitoring-topics/acc_test/customer-profiles/0",
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 200
            data = response.json()
            assert (
                data["message"] == "Customer profile keywords deleted successfully"
            )
            assert data["data"]["deleted_customer_profile"]["node_id"] == "prof_123"
        finally:
            app.dependency_overrides.clear()

    def test_delete_customer_profile_keywords_invalid_index(
        self, client, mock_user, mock_firestore_service
    ):
        """Test deleting customer profile with invalid index fails."""
        # Mock existing document
        mock_firestore_service.get_document.return_value = {
            "account_id": "acc_test",
            "customer_profile_entries": [],
        }

        # Override dependencies
        app.dependency_overrides[get_current_user_context] = lambda: mock_user
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

        try:
            response = client.delete(
                "/api/v1/monitoring-topics/acc_test/customer-profiles/0",
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()
