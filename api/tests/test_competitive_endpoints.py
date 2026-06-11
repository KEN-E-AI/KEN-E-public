"""Integration tests for competitive knowledge graph endpoints with monitoring sync."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.kene_api.auth.dependencies import get_current_user
from src.kene_api.auth.models import UserContext
from src.kene_api.firestore import get_firestore_service
from src.kene_api.main import app
from src.kene_api.services.graph_sync_service import get_graph_sync_service

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason="Requires Firebase/Firestore emulator — unblocked by DM-84",
)


class TestCompetitorEndpoints:
    """Test competitor CRUD with monitoring topics sync."""

    @pytest.fixture
    def mock_user(self):
        return UserContext(
            user_id="test_user",
            email="test@example.com",
            organization_permissions={"org_test": "admin"},
            account_permissions={"acc_test": "edit"},
        )

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def _override_auth(self, mock_user):
        app.dependency_overrides[get_current_user] = lambda: mock_user
        yield
        app.dependency_overrides.pop(get_current_user, None)

    @pytest.fixture(autouse=True)
    def _mock_org_resolver(self):
        # IN-2: the access gate resolves the account's owning org via Neo4j.
        # Patch it to org_test (mock_user is an org_test admin) so these
        # competitor endpoint tests don't need a live graph.
        with patch(
            "src.kene_api.auth.account_org.resolve_owning_organization_id",
            new=AsyncMock(return_value="org_test"),
        ):
            yield

    @pytest.fixture
    def mock_graph_service(self):
        service = AsyncMock()
        app.dependency_overrides[get_graph_sync_service] = lambda: service
        yield service
        app.dependency_overrides.pop(get_graph_sync_service, None)

    @pytest.fixture
    def mock_firestore(self):
        service = MagicMock()
        app.dependency_overrides[get_firestore_service] = lambda: service
        yield service
        app.dependency_overrides.pop(get_firestore_service, None)

    def test_create_competitor_with_keywords_syncs_to_monitoring(
        self, client, mock_graph_service, mock_firestore
    ):
        """Test creating competitor with keywords adds to monitoring topics."""
        mock_graph_service.create_competitor = AsyncMock(
            return_value={
                "node_id": "comp_123",
                "account_id": "acc_test",
                "display_name": "Acme Corp",
                "description": "A competitor",
                "references": [],
                "website": "https://acme.com",
                "created_time": "2025-01-19T00:00:00",
                "last_modified": "2025-01-19T00:00:00",
                "created_by": "test_user",
                "last_modified_by": "test_user",
            }
        )
        mock_firestore.get_document.return_value = {
            "account_id": "acc_test",
            "organization_id": "org_test",
            "industry_keywords": [],
            "company_keywords": [],
            "customer_keywords": [],
            "competitor_entries": [],
            "created_at": "2025-01-19T00:00:00",
            "updated_at": "2025-01-19T00:00:00",
        }

        response = client.post(
            "/api/v1/knowledge-graph/acc_test/competitors",
            json={
                "display_name": "Acme Corp",
                "description": "A competitor",
                "references": [],
                "website": "https://acme.com",
                "keywords": ["acme", "competitor"],
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        assert response.json()["display_name"] == "Acme Corp"
        assert mock_firestore.update_document.called

    def test_create_competitor_without_keywords_no_monitoring_sync(
        self, client, mock_graph_service, mock_firestore
    ):
        """Test creating competitor without keywords doesn't sync."""
        mock_graph_service.create_competitor = AsyncMock(
            return_value={
                "node_id": "comp_123",
                "account_id": "acc_test",
                "display_name": "Acme Corp",
                "description": "A competitor",
                "references": [],
                "website": None,
                "created_time": "2025-01-19T00:00:00",
                "last_modified": "2025-01-19T00:00:00",
                "created_by": "test_user",
                "last_modified_by": "test_user",
            }
        )

        response = client.post(
            "/api/v1/knowledge-graph/acc_test/competitors",
            json={
                "display_name": "Acme Corp",
                "description": "A competitor",
                "references": [],
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        assert not mock_firestore.get_document.called

    def test_create_competitor_firestore_failure_still_succeeds(
        self, client, mock_graph_service, mock_firestore
    ):
        """Test that Firestore failure doesn't fail competitor creation."""
        mock_graph_service.create_competitor = AsyncMock(
            return_value={
                "node_id": "comp_123",
                "account_id": "acc_test",
                "display_name": "Acme Corp",
                "description": "A competitor",
                "references": [],
                "website": "https://acme.com",
                "created_time": "2025-01-19T00:00:00",
                "last_modified": "2025-01-19T00:00:00",
                "created_by": "test_user",
                "last_modified_by": "test_user",
            }
        )
        mock_firestore.get_document.side_effect = Exception("Firestore timeout")

        response = client.post(
            "/api/v1/knowledge-graph/acc_test/competitors",
            json={
                "display_name": "Acme Corp",
                "description": "A competitor",
                "references": [],
                "website": "https://acme.com",
                "keywords": ["acme"],
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200

    def test_delete_competitor_removes_from_monitoring(
        self, client, mock_graph_service, mock_firestore
    ):
        """Test deleting competitor removes from monitoring topics."""
        competitor_dict = {
            "node_id": "comp_123",
            "account_id": "acc_test",
            "display_name": "Acme Corp",
            "description": "A competitor",
            "references": [],
            "created_time": "2025-01-19T00:00:00",
            "last_modified": "2025-01-19T00:00:00",
            "created_by": "test_user",
            "last_modified_by": "test_user",
        }
        mock_graph_service.get_node = AsyncMock(return_value=competitor_dict)
        mock_graph_service.delete_competitor = AsyncMock(
            return_value={"success": True, "deleted_count": 1}
        )
        mock_firestore.get_document.return_value = {
            "account_id": "acc_test",
            "organization_id": "org_test",
            "industry_keywords": [],
            "company_keywords": [],
            "customer_keywords": [],
            "competitor_entries": [
                {
                    "name": "Acme Corp",
                    "website": "https://acme.com",
                    "keywords": ["acme"],
                }
            ],
            "created_at": "2025-01-19T00:00:00",
            "updated_at": "2025-01-19T00:00:00",
        }

        response = client.delete(
            "/api/v1/knowledge-graph/acc_test/competitors/comp_123",
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        assert mock_firestore.update_document.called

    def test_create_competitor_invalid_keywords_fails_validation(self, client):
        """Test that invalid keywords fail validation."""
        response = client.post(
            "/api/v1/knowledge-graph/acc_test/competitors",
            json={
                "display_name": "Acme Corp",
                "description": "A competitor",
                "references": [],
                "keywords": ["x"] * 25,
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert any("keywords" in str(error).lower() for error in detail)

    def test_create_competitor_invalid_url_fails_validation(self, client):
        """Test that invalid website URL fails validation."""
        response = client.post(
            "/api/v1/knowledge-graph/acc_test/competitors",
            json={
                "display_name": "Acme Corp",
                "description": "A competitor",
                "references": [],
                "website": "not-a-valid-url",
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert any("website" in str(error).lower() for error in detail)

    def test_create_competitor_keyword_too_short_fails_validation(self, client):
        """Test that keywords shorter than 2 chars fail validation."""
        response = client.post(
            "/api/v1/knowledge-graph/acc_test/competitors",
            json={
                "display_name": "Acme Corp",
                "description": "A competitor",
                "references": [],
                "keywords": ["a"],
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 422

    def test_create_competitor_keyword_too_long_fails_validation(self, client):
        """Test that keywords longer than 50 chars fail validation."""
        response = client.post(
            "/api/v1/knowledge-graph/acc_test/competitors",
            json={
                "display_name": "Acme Corp",
                "description": "A competitor",
                "references": [],
                "keywords": ["a" * 51],
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 422
