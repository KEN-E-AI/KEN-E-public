"""Tests for industry keywords API endpoints."""

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.kene_api.auth.models import UserContext
from src.kene_api.auth.user_context import get_current_user_context
from src.kene_api.firestore import get_firestore_service
from src.kene_api.main import app

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason="Requires Firebase/Firestore emulator — unblocked by DM-84",
)


class TestIndustryKeywordsEndpoints:
    """Test industry keywords API endpoints."""

    @pytest.fixture
    def mock_super_admin(self):
        """Create a mock super admin user context."""
        return UserContext(
            user_id="super_admin",
            email="admin@ken-e.ai",
            organization_permissions={},
            account_permissions={},
            roles=["super_admin"],
        )

    @pytest.fixture
    def mock_regular_user(self):
        """Create a mock regular user context."""
        return UserContext(
            user_id="regular_user",
            email="user@example.com",
            organization_permissions={"org_test": "admin"},
            account_permissions={"acc_test": "edit"},
        )

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def _isolate_overrides(self):
        """Snapshot and restore ``app.dependency_overrides`` around each test.

        FastAPI captures ``Depends()`` callables at route-registration time, so
        the auth/Firestore dependencies must be replaced via
        ``app.dependency_overrides`` rather than ``unittest.mock.patch``. The
        snapshot keeps overrides from leaking into adjacent test files.
        """
        saved = dict(app.dependency_overrides)
        yield
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)

    @staticmethod
    def _authenticate(user: UserContext) -> None:
        """Register a dependency override that authenticates as ``user``."""
        app.dependency_overrides[get_current_user_context] = lambda: user

    @staticmethod
    def _use_firestore(firestore: MagicMock) -> None:
        """Register a dependency override for the Firestore service."""
        app.dependency_overrides[get_firestore_service] = lambda: firestore

    @pytest.fixture
    def sample_industry_keywords(self):
        """Sample industry keywords data."""
        return [
            {
                "industry": "Finance and Insurance",
                "keywords": ["finance", "banking", "insurance", "investment"],
                "updated_by": "super_admin",
                "updated_at": "2025-01-01T00:00:00",
            },
            {
                "industry": "Technology",
                "keywords": ["tech", "software", "hardware", "AI"],
                "updated_by": "super_admin",
                "updated_at": "2025-01-01T00:00:00",
            },
        ]

    # GET endpoint tests
    def test_get_all_industry_keywords_success(
        self, client, mock_super_admin, sample_industry_keywords
    ):
        """Test successful retrieval of all industry keywords by super admin."""
        self._authenticate(mock_super_admin)
        mock_firestore = MagicMock()
        mock_firestore.list_documents.return_value = sample_industry_keywords
        self._use_firestore(mock_firestore)

        with patch(
            "src.kene_api.routers.industry_keywords._cache_service.get",
            return_value=None,
        ):
            with patch("src.kene_api.routers.industry_keywords._cache_service.set"):
                response = client.get(
                    "/api/v1/industry-keywords/",
                    headers={"Authorization": "Bearer test_token"},
                )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["industry"] == "Finance and Insurance"
        assert data[1]["industry"] == "Technology"

    def test_get_all_industry_keywords_cached(
        self, client, mock_super_admin, sample_industry_keywords
    ):
        """Test retrieval of industry keywords from cache."""
        self._authenticate(mock_super_admin)
        self._use_firestore(MagicMock())

        with patch(
            "src.kene_api.routers.industry_keywords._cache_service.get",
            return_value=sample_industry_keywords,
        ):
            response = client.get(
                "/api/v1/industry-keywords/",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_all_industry_keywords_forbidden_regular_user(
        self, client, mock_regular_user
    ):
        """Test that regular users cannot access industry keywords."""
        self._authenticate(mock_regular_user)
        self._use_firestore(MagicMock())

        response = client.get(
            "/api/v1/industry-keywords/",
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 403
        assert (
            "Only super admins can manage industry keywords"
            in response.json()["detail"]
        )

    # PUT endpoint tests
    def test_update_industry_keywords_success(self, client, mock_super_admin):
        """Test successful update of industry keywords by super admin."""
        self._authenticate(mock_super_admin)
        mock_firestore = MagicMock()
        mock_firestore.create_document.return_value = True
        self._use_firestore(mock_firestore)

        with patch("src.kene_api.routers.industry_keywords._cache_service.delete"):
            response = client.put(
                "/api/v1/industry-keywords/Finance%20and%20Insurance",
                json=["finance", "banking", "fintech", "investment", "trading"],
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Industry keywords updated for Finance and Insurance"
        assert data["data"]["keywords"] == [
            "finance",
            "banking",
            "fintech",
            "investment",
            "trading",
        ]

        # Verify Firestore call
        mock_firestore.create_document.assert_called_once()
        call_args = mock_firestore.create_document.call_args
        assert call_args.kwargs["collection"] == "industry_keywords"
        assert call_args.kwargs["document_id"] == "finance_and_insurance"
        assert call_args.kwargs["data"]["keywords"] == [
            "finance",
            "banking",
            "fintech",
            "investment",
            "trading",
        ]

    def test_update_industry_keywords_invalid_industry(self, client, mock_super_admin):
        """Test update with invalid industry name."""
        self._authenticate(mock_super_admin)
        self._use_firestore(MagicMock())

        response = client.put(
            "/api/v1/industry-keywords/Invalid%20Industry",
            json=["keyword1", "keyword2"],
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 400
        assert "Invalid industry: Invalid Industry" in response.json()["detail"]

    def test_update_industry_keywords_forbidden_regular_user(
        self, client, mock_regular_user
    ):
        """Test that regular users cannot update industry keywords."""
        self._authenticate(mock_regular_user)
        self._use_firestore(MagicMock())

        response = client.put(
            "/api/v1/industry-keywords/Finance%20and%20Insurance",
            json=["finance", "banking"],
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 403
        assert (
            "Only super admins can manage industry keywords"
            in response.json()["detail"]
        )

    # DELETE endpoint tests
    def test_delete_industry_keywords_success(self, client, mock_super_admin):
        """Test successful deletion of industry keywords by super admin."""
        self._authenticate(mock_super_admin)
        mock_firestore = MagicMock()
        mock_firestore.get_document.return_value = {
            "industry": "Finance and Insurance",
            "keywords": ["finance", "banking"],
            "updated_by": "super_admin",
            "updated_at": "2025-01-01T00:00:00",
        }
        mock_firestore.delete_document.return_value = True
        self._use_firestore(mock_firestore)

        with patch("src.kene_api.routers.industry_keywords._cache_service.delete"):
            response = client.delete(
                "/api/v1/industry-keywords/Finance%20and%20Insurance",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Industry keywords deleted for Finance and Insurance"
        assert data["data"]["industry"] == "Finance and Insurance"

        # Verify Firestore calls
        mock_firestore.get_document.assert_called_once_with(
            collection="industry_keywords",
            document_id="finance_and_insurance",
        )
        mock_firestore.delete_document.assert_called_once_with(
            collection="industry_keywords",
            document_id="finance_and_insurance",
        )

    def test_delete_industry_keywords_not_found(self, client, mock_super_admin):
        """Test deletion when industry keywords don't exist."""
        self._authenticate(mock_super_admin)
        mock_firestore = MagicMock()
        mock_firestore.get_document.return_value = None
        self._use_firestore(mock_firestore)

        response = client.delete(
            "/api/v1/industry-keywords/Finance%20and%20Insurance",
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 404
        assert (
            "No keywords found for industry: Finance and Insurance"
            in response.json()["detail"]
        )

    def test_delete_industry_keywords_invalid_industry(self, client, mock_super_admin):
        """Test deletion with invalid industry name."""
        self._authenticate(mock_super_admin)
        self._use_firestore(MagicMock())

        response = client.delete(
            "/api/v1/industry-keywords/Invalid%20Industry",
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 400
        assert "Invalid industry: Invalid Industry" in response.json()["detail"]

    def test_delete_industry_keywords_forbidden_regular_user(
        self, client, mock_regular_user
    ):
        """Test that regular users cannot delete industry keywords."""
        self._authenticate(mock_regular_user)
        self._use_firestore(MagicMock())

        response = client.delete(
            "/api/v1/industry-keywords/Finance%20and%20Insurance",
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 403
        assert (
            "Only super admins can manage industry keywords"
            in response.json()["detail"]
        )

    # Error handling tests
    def test_get_all_industry_keywords_firestore_error(self, client, mock_super_admin):
        """Test handling of Firestore errors during retrieval."""
        self._authenticate(mock_super_admin)
        mock_firestore = MagicMock()
        mock_firestore.list_documents.side_effect = Exception("Firestore error")
        self._use_firestore(mock_firestore)

        with patch(
            "src.kene_api.routers.industry_keywords._cache_service.get",
            return_value=None,
        ):
            response = client.get(
                "/api/v1/industry-keywords/",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == 500
        assert "Failed to retrieve industry keywords" in response.json()["detail"]

    def test_update_industry_keywords_firestore_error(self, client, mock_super_admin):
        """Test handling of Firestore errors during update."""
        self._authenticate(mock_super_admin)
        mock_firestore = MagicMock()
        mock_firestore.create_document.side_effect = Exception("Firestore error")
        self._use_firestore(mock_firestore)

        response = client.put(
            "/api/v1/industry-keywords/Finance%20and%20Insurance",
            json=["finance", "banking"],
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 500
        assert "Failed to update industry keywords" in response.json()["detail"]
