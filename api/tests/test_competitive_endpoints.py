"""Integration tests for competitive knowledge graph endpoints with monitoring sync."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from src.kene_api.auth.models import UserContext
from src.kene_api.main import app


class TestCompetitorEndpoints:
    """Test competitor CRUD with monitoring topics sync."""

    @pytest.fixture
    def mock_user(self):
        """Create mock user with edit access."""
        return UserContext(
            user_id="test_user",
            email="test@example.com",
            accessible_accounts=["acc_test"],
            permissions={},
            organization_permissions={"org_test": "admin"},
            account_permissions={"acc_test": "edit"},
        )

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_create_competitor_with_keywords_syncs_to_monitoring(
        self, client, mock_user
    ):
        """Test creating competitor with keywords adds to monitoring topics."""
        with patch(
            "src.kene_api.routers.knowledge_graph.competitive.get_current_user",
            return_value=mock_user,
        ):
            with patch(
                "src.kene_api.routers.knowledge_graph.competitive.get_graph_sync_service"
            ) as mock_graph:
                with patch(
                    "src.kene_api.routers.knowledge_graph.competitive.get_firestore_service"
                ) as mock_firestore:
                    # Mock graph service methods
                    mock_service = AsyncMock()
                    mock_service.create_competitor = AsyncMock(
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
                    mock_graph.return_value = mock_service

                    # Mock Firestore document
                    mock_firestore.return_value.get_document.return_value = {
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
                    data = response.json()
                    assert data["display_name"] == "Acme Corp"

                    # Verify Firestore was updated
                    assert mock_firestore.return_value.update_document.called

    def test_create_competitor_without_keywords_no_monitoring_sync(
        self, client, mock_user
    ):
        """Test creating competitor without keywords doesn't sync."""
        with patch(
            "src.kene_api.routers.knowledge_graph.competitive.get_current_user",
            return_value=mock_user,
        ):
            with patch(
                "src.kene_api.routers.knowledge_graph.competitive.get_graph_sync_service"
            ) as mock_graph:
                with patch(
                    "src.kene_api.routers.knowledge_graph.competitive.get_firestore_service"
                ) as mock_firestore:
                    # Mock graph service
                    mock_service = AsyncMock()
                    mock_service.create_competitor = AsyncMock(
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
                    mock_graph.return_value = mock_service

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

                    # Verify Firestore was NOT called
                    assert not mock_firestore.return_value.get_document.called

    def test_create_competitor_firestore_failure_still_succeeds(
        self, client, mock_user
    ):
        """Test that Firestore failure doesn't fail competitor creation."""
        with patch(
            "src.kene_api.routers.knowledge_graph.competitive.get_current_user",
            return_value=mock_user,
        ):
            with patch(
                "src.kene_api.routers.knowledge_graph.competitive.get_graph_sync_service"
            ) as mock_graph:
                with patch(
                    "src.kene_api.routers.knowledge_graph.competitive.get_firestore_service"
                ) as mock_firestore:
                    # Mock Neo4j success
                    mock_service = AsyncMock()
                    mock_service.create_competitor = AsyncMock(
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
                    mock_graph.return_value = mock_service

                    # Mock Firestore failure
                    mock_firestore.return_value.get_document.side_effect = Exception(
                        "Firestore timeout"
                    )

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

                    # Should still succeed
                    assert response.status_code == 200

    def test_delete_competitor_removes_from_monitoring(self, client, mock_user):
        """Test deleting competitor removes from monitoring topics."""
        with patch(
            "src.kene_api.routers.knowledge_graph.competitive.get_current_user",
            return_value=mock_user,
        ):
            with patch(
                "src.kene_api.routers.knowledge_graph.competitive.get_graph_sync_service"
            ) as mock_graph:
                with patch(
                    "src.kene_api.routers.knowledge_graph.competitive.get_firestore_service"
                ) as mock_firestore:
                    # Mock graph service
                    mock_service = AsyncMock()
                    mock_service.get_competitor = AsyncMock(
                        return_value={
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
                    )
                    mock_service.delete_competitor = AsyncMock(
                        return_value={"success": True, "deleted_count": 1}
                    )
                    mock_graph.return_value = mock_service

                    # Mock Firestore document
                    mock_firestore.return_value.get_document.return_value = {
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

                    # Verify Firestore was updated to remove competitor
                    assert mock_firestore.return_value.update_document.called

    def test_create_competitor_invalid_keywords_fails_validation(
        self, client, mock_user
    ):
        """Test that invalid keywords fail validation."""
        with patch(
            "src.kene_api.routers.knowledge_graph.competitive.get_current_user",
            return_value=mock_user,
        ):
            response = client.post(
                "/api/v1/knowledge-graph/acc_test/competitors",
                json={
                    "display_name": "Acme Corp",
                    "description": "A competitor",
                    "references": [],
                    "keywords": ["x"] * 25,  # Too many keywords
                },
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 422
            detail = response.json()["detail"]
            assert any("keywords" in str(error).lower() for error in detail)

    def test_create_competitor_invalid_url_fails_validation(self, client, mock_user):
        """Test that invalid website URL fails validation."""
        with patch(
            "src.kene_api.routers.knowledge_graph.competitive.get_current_user",
            return_value=mock_user,
        ):
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

    def test_create_competitor_keyword_too_short_fails_validation(
        self, client, mock_user
    ):
        """Test that keywords shorter than 2 chars fail validation."""
        with patch(
            "src.kene_api.routers.knowledge_graph.competitive.get_current_user",
            return_value=mock_user,
        ):
            response = client.post(
                "/api/v1/knowledge-graph/acc_test/competitors",
                json={
                    "display_name": "Acme Corp",
                    "description": "A competitor",
                    "references": [],
                    "keywords": ["a"],  # Too short
                },
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 422

    def test_create_competitor_keyword_too_long_fails_validation(
        self, client, mock_user
    ):
        """Test that keywords longer than 50 chars fail validation."""
        with patch(
            "src.kene_api.routers.knowledge_graph.competitive.get_current_user",
            return_value=mock_user,
        ):
            response = client.post(
                "/api/v1/knowledge-graph/acc_test/competitors",
                json={
                    "display_name": "Acme Corp",
                    "description": "A competitor",
                    "references": [],
                    "keywords": ["a" * 51],  # Too long
                },
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 422
