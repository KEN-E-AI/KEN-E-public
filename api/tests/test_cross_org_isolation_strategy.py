"""Cross-org isolation tests for routers/strategy.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from src.kene_api.auth import UserContext

_RESOLVER = "src.kene_api.auth.account_org.resolve_owning_organization_id"
_NEO4J = "src.kene_api.auth.account_org.neo4j_service.execute_query"


@pytest.fixture
def super_admin():
    return UserContext(
        user_id="sa1", email="sa@ken-e.ai",
        organization_permissions={}, account_permissions={}, roles=["super_admin"],
    )


@pytest.fixture
def org_a_admin():
    return UserContext(
        user_id="oa1", email="admin@org-a.com",
        organization_permissions={"org_A": "admin"}, account_permissions={},
    )


class TestStrategyCrossOrgIsolation:
    """check_strategy_access must deny org-A admin on org-B accounts."""

    @pytest.mark.asyncio
    async def test_view_cross_org_denied(self, org_a_admin):
        from src.kene_api.routers.strategy import check_strategy_access

        with patch(_RESOLVER, AsyncMock(return_value="org_B")):
            with pytest.raises(HTTPException) as exc:
                await check_strategy_access("acc_org_b", org_a_admin, "view")
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_edit_cross_org_denied(self, org_a_admin):
        from src.kene_api.routers.strategy import check_strategy_access

        with patch(_RESOLVER, AsyncMock(return_value="org_B")):
            with pytest.raises(HTTPException) as exc:
                await check_strategy_access("acc_org_b", org_a_admin, "edit")
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_super_admin_always_allowed(self, super_admin):
        from src.kene_api.routers.strategy import check_strategy_access

        with patch(_RESOLVER, AsyncMock(side_effect=AssertionError("must not be called"))):
            result = await check_strategy_access("any_acc", super_admin, "edit")
        assert result is super_admin

    @pytest.mark.asyncio
    async def test_own_org_account_allowed(self, org_a_admin):
        from src.kene_api.routers.strategy import check_strategy_access

        with patch(_RESOLVER, AsyncMock(return_value="org_A")):
            result = await check_strategy_access("acc_org_a", org_a_admin, "view")
        assert result is org_a_admin


class TestStrategyResolverCallCount:
    """Each strategy handler resolves the owning org at most once per request."""

    @pytest.fixture(autouse=True)
    def clear_org_cache(self):
        from src.kene_api.auth.account_org import _clear_cache
        _clear_cache()
        yield
        _clear_cache()

    @pytest.mark.asyncio
    async def test_list_documents_resolves_org_once(self, org_a_admin):
        """list_strategy_documents resolves owning org at most once."""
        from src.kene_api.routers.strategy import list_strategy_documents

        mock_neo4j = AsyncMock(return_value=[{"organization_id": "org_A"}])
        with patch(_NEO4J, mock_neo4j):
            with patch("src.kene_api.routers.strategy.db") as mock_db:
                mock_db.collection.return_value.where.return_value.where.return_value.stream.return_value = []
                with patch("src.kene_api.routers.strategy.log_strategy_action", AsyncMock()):
                    await list_strategy_documents(
                        account_id="acc_a",
                        doc_type=None,
                        is_active=True,
                        request=None,
                        user=org_a_admin,
                    )

        assert mock_neo4j.call_count == 1, (
            f"Expected 1 Neo4j call, got {mock_neo4j.call_count}"
        )

    @pytest.mark.asyncio
    async def test_get_document_resolves_org_once(self, org_a_admin):
        """get_strategy_document resolves owning org at most once."""
        from src.kene_api.routers.strategy import get_strategy_document

        mock_neo4j = AsyncMock(return_value=[{"organization_id": "org_A"}])

        # Firestore .get() is a synchronous call — use MagicMock.
        doc_mock = MagicMock()
        doc_mock.exists = True
        doc_mock.id = "strategy_doc_1"
        doc_mock.to_dict.return_value = {
            "doc_type": "business_strategy",
            "content": {},
            "version": 1,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
            "created_by": "user_1",
            "updated_by": "user_1",
            "account_id": "acc_a",
            "is_active": True,
        }

        with patch(_NEO4J, mock_neo4j):
            with patch("src.kene_api.routers.strategy.db") as mock_db:
                mock_db.document.return_value.get.return_value = doc_mock
                with patch("src.kene_api.routers.strategy.log_strategy_action", AsyncMock()):
                    await get_strategy_document(
                        account_id="acc_a",
                        doc_type="business_strategy",
                        version=None,
                        request=None,
                        user=org_a_admin,
                    )

        assert mock_neo4j.call_count == 1, (
            f"Expected 1 Neo4j call, got {mock_neo4j.call_count}"
        )

    @pytest.mark.asyncio
    async def test_create_document_resolves_org_once(self, org_a_admin):
        """create_or_update_strategy_document resolves owning org at most once."""
        from src.kene_api.models.strategy_models import StrategyDocumentRequest
        from src.kene_api.routers.strategy import create_or_update_strategy_document

        mock_neo4j = AsyncMock(return_value=[{"organization_id": "org_A"}])

        # Firestore .get() is a synchronous call — use MagicMock.
        existing_doc_mock = MagicMock()
        existing_doc_mock.exists = False

        doc_ref_mock = MagicMock()
        doc_ref_mock.get.return_value = existing_doc_mock
        doc_ref_mock.set.return_value = None
        doc_ref_mock.id = "business_strategy"

        document_request = StrategyDocumentRequest(
            doc_type="business_strategy",
            content={"executive_summary": "test"},
            title="Test Strategy",
        )

        with patch(_NEO4J, mock_neo4j):
            with patch("src.kene_api.routers.strategy.db") as mock_db:
                mock_db.document.return_value = doc_ref_mock
                with patch("src.kene_api.routers.strategy.log_strategy_action", AsyncMock()):
                    await create_or_update_strategy_document(
                        account_id="acc_a",
                        doc_type="business_strategy",
                        document_request=document_request,
                        request=None,
                        user=org_a_admin,
                    )

        assert mock_neo4j.call_count == 1, (
            f"Expected 1 Neo4j call, got {mock_neo4j.call_count}"
        )
