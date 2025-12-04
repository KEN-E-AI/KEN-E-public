"""Integration tests for customer profile monitoring keywords."""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from src.kene_api.auth.models import UserContext
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
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_add_customer_profile_keywords_success(self, client, mock_user):
        """Test adding customer profile keywords."""
        with patch(
            "src.kene_api.routers.monitoring_topics.get_current_user_context",
            return_value=mock_user,
        ):
            with patch(
                "src.kene_api.routers.monitoring_topics.get_firestore_service"
            ) as mock_firestore:
                # Mock existing document
                mock_firestore.return_value.get_document.return_value = {
                    "account_id": "acc_test",
                    "customer_profile_entries": [],
                }

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
                    data["message"]
                    == "Customer profile keywords added successfully"
                )
                assert data["data"]["customer_profile"]["node_id"] == "prof_123"

                # Verify Firestore was updated
                mock_firestore.return_value.update_document.assert_called_once()

    def test_add_customer_profile_keywords_no_access(self, client):
        """Test adding customer profile keywords without access fails."""
        mock_user_no_access = UserContext(
            user_id="test_user_no_access",
            email="notest@example.com",
            organization_permissions={},
            account_permissions={},
        )

        with patch(
            "src.kene_api.routers.monitoring_topics.get_current_user_context",
            return_value=mock_user_no_access,
        ):
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

    def test_update_customer_profile_keywords_success(self, client, mock_user):
        """Test updating customer profile keywords."""
        with patch(
            "src.kene_api.routers.monitoring_topics.get_current_user_context",
            return_value=mock_user,
        ):
            with patch(
                "src.kene_api.routers.monitoring_topics.get_firestore_service"
            ) as mock_firestore:
                # Mock existing document with one entry
                mock_firestore.return_value.get_document.return_value = {
                    "account_id": "acc_test",
                    "customer_profile_entries": [
                        {"node_id": "prof_123", "keywords": ["old_keyword"]}
                    ],
                }

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
                    data["message"]
                    == "Customer profile keywords updated successfully"
                )
                assert "new_keyword1" in data["data"]["customer_profile"]["keywords"]

    def test_update_customer_profile_keywords_invalid_index(
        self, client, mock_user
    ):
        """Test updating customer profile with invalid index fails."""
        with patch(
            "src.kene_api.routers.monitoring_topics.get_current_user_context",
            return_value=mock_user,
        ):
            with patch(
                "src.kene_api.routers.monitoring_topics.get_firestore_service"
            ) as mock_firestore:
                # Mock existing document with one entry
                mock_firestore.return_value.get_document.return_value = {
                    "account_id": "acc_test",
                    "customer_profile_entries": [
                        {"node_id": "prof_123", "keywords": ["keyword1"]}
                    ],
                }

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

    def test_delete_customer_profile_keywords_success(self, client, mock_user):
        """Test deleting customer profile keywords."""
        with patch(
            "src.kene_api.routers.monitoring_topics.get_current_user_context",
            return_value=mock_user,
        ):
            with patch(
                "src.kene_api.routers.monitoring_topics.get_firestore_service"
            ) as mock_firestore:
                # Mock existing document
                mock_firestore.return_value.get_document.return_value = {
                    "account_id": "acc_test",
                    "customer_profile_entries": [
                        {"node_id": "prof_123", "keywords": ["keyword1"]}
                    ],
                }

                response = client.delete(
                    "/api/v1/monitoring-topics/acc_test/customer-profiles/0",
                    headers={"Authorization": "Bearer test_token"},
                )

                assert response.status_code == 200
                data = response.json()
                assert (
                    data["message"]
                    == "Customer profile keywords deleted successfully"
                )
                assert data["data"]["deleted_customer_profile"]["node_id"] == "prof_123"

    def test_delete_customer_profile_keywords_invalid_index(
        self, client, mock_user
    ):
        """Test deleting customer profile with invalid index fails."""
        with patch(
            "src.kene_api.routers.monitoring_topics.get_current_user_context",
            return_value=mock_user,
        ):
            with patch(
                "src.kene_api.routers.monitoring_topics.get_firestore_service"
            ) as mock_firestore:
                # Mock existing document
                mock_firestore.return_value.get_document.return_value = {
                    "account_id": "acc_test",
                    "customer_profile_entries": [],
                }

                response = client.delete(
                    "/api/v1/monitoring-topics/acc_test/customer-profiles/0",
                    headers={"Authorization": "Bearer test_token"},
                )

                assert response.status_code == 404
