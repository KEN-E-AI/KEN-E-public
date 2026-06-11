"""Tests for monitoring topics API endpoints with comprehensive error scenarios."""

import asyncio
import os
from unittest import mock
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from src.kene_api.auth.models import UserContext
from src.kene_api.auth.user_context import get_current_user_context
from src.kene_api.firestore import get_firestore_service
from src.kene_api.main import app

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason="Requires Firebase/Firestore emulator",
)


def _install_user_override(user: UserContext):
    app.dependency_overrides[get_current_user_context] = lambda: user


def _clear_user_override():
    app.dependency_overrides.pop(get_current_user_context, None)


class TestMonitoringTopicsEndpoints:
    """Test monitoring topics API endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def mock_user(self):
        user = UserContext(
            user_id="test_user",
            email="test@example.com",
            organization_permissions={"org_test": "admin"},
            account_permissions={"acc_test": "edit"},
        )
        _install_user_override(user)
        yield user
        _clear_user_override()

    @pytest.fixture
    def mock_user_no_access(self):
        user = UserContext(
            user_id="test_user_no_access",
            email="notest@example.com",
            organization_permissions={},
            account_permissions={},
        )
        _install_user_override(user)
        yield user
        _clear_user_override()

    @pytest.fixture
    def mock_user_view_only(self):
        user = UserContext(
            user_id="test_user_view",
            email="view@example.com",
            organization_permissions={"org_test": "view"},
            account_permissions={"acc_test": "view"},
        )
        _install_user_override(user)
        yield user
        _clear_user_override()

    @pytest.fixture
    def mock_super_admin(self):
        user = UserContext(
            user_id="admin_user",
            email="admin@ken-e.ai",
            organization_permissions={"org_test": "admin"},
            account_permissions={},
            roles=["super_admin"],
        )
        _install_user_override(user)
        yield user
        _clear_user_override()

    @pytest.fixture(autouse=True)
    def _mock_org_resolver(self):
        # IN-2: the access gate (require_account_access_for) resolves the
        # account's owning org via Neo4j. Patch it to org_test so these
        # endpoint tests don't need a live graph; mock_user is an org_test
        # admin so the permission check then passes.
        with mock.patch(
            "src.kene_api.auth.account_org.resolve_owning_organization_id",
            new=AsyncMock(return_value="org_test"),
        ):
            yield

    @pytest.fixture
    def mock_firestore(self):
        service = MagicMock()
        app.dependency_overrides[get_firestore_service] = lambda: service
        yield service
        app.dependency_overrides.pop(get_firestore_service, None)

    @pytest.fixture
    def mock_neo4j(self):
        # The router calls ``await get_neo4j_service()`` directly (not via
        # FastAPI Depends), so a dependency_override would not be reached —
        # patch the function reference at the import site.
        service = AsyncMock()
        with mock.patch(
            "src.kene_api.routers.monitoring_topics.get_neo4j_service",
            new=AsyncMock(return_value=service),
        ):
            yield service

    # ========================================================================
    # GET endpoint tests
    # ========================================================================

    def test_get_monitoring_topics_success(self, client, mock_user, mock_firestore):
        """Test successful retrieval of monitoring topics."""
        mock_firestore.get_document.return_value = {
            "account_id": "acc_test",
            "organization_id": "org_test",
            "industry_keywords": ["keyword1", "keyword2"],
            "company_keywords": ["company1"],
            "customer_keywords": [],
            "competitor_entries": [],
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
        }

        response = client.get(
            "/api/v1/monitoring-topics/acc_test",
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["account_id"] == "acc_test"

    def test_get_monitoring_topics_no_document_creates_new(
        self, client, mock_user, mock_firestore, mock_neo4j
    ):
        """Test that a new document is created when none exists."""
        from src.kene_api.models.monitoring_models import MonitoringTopics

        mock_firestore.get_document.return_value = None

        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.single.return_value = {
            "industry": "Manufacturing",
            "organization_id": "org_test",
        }
        mock_session.run.return_value = mock_result
        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_neo4j.get_session = MagicMock(return_value=session_cm)

        created_topics = MonitoringTopics(
            account_id="acc_test",
            organization_id="org_test",
            industry_keywords=["tools", "factory"],
            created_at="2025-01-01T00:00:00",
            updated_at="2025-01-01T00:00:00",
        )

        with mock.patch(
            "src.kene_api.routers.monitoring_topics.get_or_create_monitoring_topics",
            new=AsyncMock(return_value=created_topics),
        ):
            response = client.get(
                "/api/v1/monitoring-topics/acc_test",
                headers={"Authorization": "Bearer test_token"},
            )

        assert response.status_code == 200
        assert response.json()["data"]["account_id"] == "acc_test"

    def test_get_monitoring_topics_access_denied(self, client, mock_user_no_access):
        """Test access denied for user without permissions.

        IN-2: denial returns 404 'Account not found' (anti-enumeration), not 403.
        """
        response = client.get(
            "/api/v1/monitoring-topics/acc_test",
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_monitoring_topics_no_auth(self, client):
        """Test request without authentication."""
        response = client.get("/api/v1/monitoring-topics/acc_test")
        assert response.status_code == 401

    def test_get_monitoring_topics_account_not_in_neo4j(
        self, client, mock_user, mock_firestore, mock_neo4j
    ):
        """Test when account doesn't exist in Neo4j."""
        mock_firestore.get_document.return_value = None

        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.single.return_value = None
        mock_session.run.return_value = mock_result
        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_neo4j.get_session = MagicMock(return_value=session_cm)

        response = client.get(
            "/api/v1/monitoring-topics/acc_test",
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        assert response.json()["data"] is None

    def test_get_monitoring_topics_neo4j_connection_error(
        self, client, mock_user, mock_firestore, mock_neo4j
    ):
        """Test handling of Neo4j connection error."""
        mock_firestore.get_document.return_value = None
        mock_neo4j.get_session = MagicMock(
            side_effect=Exception("Neo4j connection failed")
        )

        response = client.get(
            "/api/v1/monitoring-topics/acc_test",
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 500
        assert "Neo4j connection failed" in response.json()["detail"]

    def test_get_monitoring_topics_firestore_error(
        self, client, mock_user, mock_firestore
    ):
        """Test handling of Firestore error."""
        mock_firestore.get_document.side_effect = Exception("Firestore quota exceeded")

        response = client.get(
            "/api/v1/monitoring-topics/acc_test",
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 500
        assert "Firestore quota exceeded" in response.json()["detail"]

    # ========================================================================
    # PUT company keywords tests
    # ========================================================================

    def test_update_company_keywords_success(self, client, mock_user, mock_firestore):
        """Test successful update of company keywords."""
        mock_firestore.get_document.return_value = {
            "account_id": "acc_test",
            "company_keywords": ["old_keyword"],
        }

        response = client.put(
            "/api/v1/monitoring-topics/acc_test/company",
            json={
                "account_id": "acc_test",
                "company_keywords": ["new_keyword1", "new_keyword2"],
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        assert response.json()["data"]["company_keywords"] == [
            "new_keyword1",
            "new_keyword2",
        ]

    def test_update_company_keywords_validation_error(self, client, mock_user):
        """Test validation error for mismatched account ID."""
        response = client.put(
            "/api/v1/monitoring-topics/acc_test/company",
            json={"account_id": "acc_different", "company_keywords": ["valid"]},
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 400
        assert "Account ID in path does not match" in response.json()["detail"]

    def test_update_company_keywords_view_only_access(
        self, client, mock_user_view_only
    ):
        """Test that view-only users cannot update keywords.

        IN-2: insufficient (view-only) access returns 404 'Account not found'
        (anti-enumeration), not 403.
        """
        response = client.put(
            "/api/v1/monitoring-topics/acc_test/company",
            json={"account_id": "acc_test", "company_keywords": ["keyword"]},
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_company_keywords_empty_list(
        self, client, mock_user, mock_firestore
    ):
        """Test updating with empty keyword list."""
        mock_firestore.get_document.return_value = {
            "account_id": "acc_test",
            "company_keywords": ["old_keyword"],
        }

        response = client.put(
            "/api/v1/monitoring-topics/acc_test/company",
            json={"account_id": "acc_test", "company_keywords": []},
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        assert response.json()["data"]["company_keywords"] == []

    def test_update_company_keywords_at_max(self, client, mock_user, mock_firestore):
        """Test updating with the maximum allowed keyword count (20 per KeywordValidators.MAX_COUNT)."""
        mock_firestore.get_document.return_value = {"account_id": "acc_test"}

        max_keyword_list = [f"keyword_{i}" for i in range(20)]

        response = client.put(
            "/api/v1/monitoring-topics/acc_test/company",
            json={
                "account_id": "acc_test",
                "company_keywords": max_keyword_list,
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        assert len(response.json()["data"]["company_keywords"]) == 20

    def test_update_company_keywords_over_max_rejected(self, client, mock_user):
        """Test that exceeding the max keyword count (20) is rejected at validation."""
        over_max = [f"keyword_{i}" for i in range(21)]

        response = client.put(
            "/api/v1/monitoring-topics/acc_test/company",
            json={"account_id": "acc_test", "company_keywords": over_max},
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 422

    # ========================================================================
    # POST competitor tests
    # ========================================================================

    def test_add_competitor_success(self, client, mock_user, mock_firestore):
        """Test successful addition of competitor."""
        mock_firestore.get_document.return_value = {
            "account_id": "acc_test",
            "competitor_entries": [],
        }

        response = client.post(
            "/api/v1/monitoring-topics/acc_test/competitors",
            json={
                "account_id": "acc_test",
                "competitor_entry": {
                    "name": "New Competitor",
                    "keywords": ["comp_keyword"],
                },
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        assert response.json()["data"]["competitor"]["name"] == "New Competitor"

    def test_add_competitor_appends_when_name_exists(
        self, client, mock_user, mock_firestore
    ):
        """POST /competitors appends entries unconditionally — no name-uniqueness check.

        Posting an entry whose name already appears in competitor_entries
        succeeds with 200. Tracked product follow-up: enforce node_id
        uniqueness on the POST.
        """
        mock_firestore.get_document.return_value = {
            "account_id": "acc_test",
            "competitor_entries": [
                {"name": "Existing Competitor", "keywords": ["keyword1"]}
            ],
        }

        response = client.post(
            "/api/v1/monitoring-topics/acc_test/competitors",
            json={
                "account_id": "acc_test",
                "competitor_entry": {
                    "name": "Existing Competitor",
                    "keywords": ["keyword2"],
                },
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200

    def test_add_competitor_with_website(self, client, mock_user, mock_firestore):
        """Test adding competitor with website."""
        mock_firestore.get_document.return_value = {
            "account_id": "acc_test",
            "competitor_entries": [],
        }

        response = client.post(
            "/api/v1/monitoring-topics/acc_test/competitors",
            json={
                "account_id": "acc_test",
                "competitor_entry": {
                    "name": "Competitor with Site",
                    "website": "https://competitor.com",
                    "keywords": ["comp"],
                },
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        competitor = response.json()["data"]["competitor"]
        assert competitor["name"] == "Competitor with Site"
        assert competitor["website"] == "https://competitor.com"

    # ========================================================================
    # DELETE competitor tests
    # ========================================================================

    def test_delete_competitor_success(self, client, mock_user, mock_firestore):
        """Test successful deletion of competitor by array index."""
        mock_firestore.get_document.return_value = {
            "account_id": "acc_test",
            "competitor_entries": [{"name": "To Delete", "keywords": ["keyword"]}],
        }

        response = client.delete(
            "/api/v1/monitoring-topics/acc_test/competitors/0",
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Competitor deleted successfully"

    def test_delete_competitor_index_out_of_range(
        self, client, mock_user, mock_firestore
    ):
        """Test deleting at an out-of-range index returns 404."""
        mock_firestore.get_document.return_value = {
            "account_id": "acc_test",
            "competitor_entries": [],
        }

        response = client.delete(
            "/api/v1/monitoring-topics/acc_test/competitors/99",
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 404
        assert "Competitor not found" in response.json()["detail"]

    # ========================================================================
    # Network timeout test
    # ========================================================================

    def test_network_timeout_handling(self, client, mock_user, mock_firestore):
        """Test handling of network timeout."""
        mock_firestore.get_document.side_effect = asyncio.TimeoutError(
            "Request timed out"
        )

        response = client.get(
            "/api/v1/monitoring-topics/acc_test",
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 500

    # ========================================================================
    # Industry keywords tests
    # ========================================================================

    def test_update_industry_keywords_super_admin(
        self, client, mock_super_admin, mock_firestore
    ):
        """Test that super admin can update industry keywords for a valid industry."""
        response = client.put(
            "/api/v1/monitoring-topics/industries/Manufacturing",
            json={
                "industry": "Manufacturing",
                "keywords": ["tools", "factory", "supply chain"],
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200

    def test_update_industry_keywords_regular_user_denied(self, client, mock_user):
        """Test that regular users cannot update industry keywords."""
        response = client.put(
            "/api/v1/monitoring-topics/industries/Manufacturing",
            json={"industry": "Manufacturing", "keywords": ["tools", "factory"]},
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 403
        assert "Only super admins" in response.json()["detail"]
