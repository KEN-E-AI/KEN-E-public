"""Unit tests for the account → organization resolver."""

import logging
from unittest.mock import AsyncMock, patch

import pytest

_RESOLVER = "src.kene_api.auth.account_org"


class TestResolveOwningOrganizationId:
    """Tests for resolve_owning_organization_id."""

    @pytest.mark.asyncio
    async def test_happy_path_returns_org_id(self):
        """Returns the organization_id when a :BELONGS_TO edge exists."""
        from src.kene_api.auth.account_org import resolve_owning_organization_id

        mock_result = [{"organization_id": "org_abc"}]
        with patch(
            f"{_RESOLVER}.neo4j_service.execute_query",
            AsyncMock(return_value=mock_result),
        ):
            result = await resolve_owning_organization_id("acc_123")

        assert result == "org_abc"

    @pytest.mark.asyncio
    async def test_no_match_returns_none(self):
        """Returns None when the account has no owning organization."""
        from src.kene_api.auth.account_org import resolve_owning_organization_id

        with patch(
            f"{_RESOLVER}.neo4j_service.execute_query",
            AsyncMock(return_value=[]),
        ):
            result = await resolve_owning_organization_id("acc_unknown")

        assert result is None

    @pytest.mark.asyncio
    async def test_neo4j_exception_returns_none_and_logs_warning(self, caplog):
        """Returns None and logs a WARNING when Neo4j raises."""
        from src.kene_api.auth.account_org import resolve_owning_organization_id

        with patch(
            f"{_RESOLVER}.neo4j_service.execute_query",
            AsyncMock(side_effect=RuntimeError("connection refused")),
        ):
            with caplog.at_level(logging.WARNING, logger="src.kene_api.auth.account_org"):
                result = await resolve_owning_organization_id("acc_123")

        assert result is None
        assert any(
            "resolve_owning_organization_id" in rec.message for rec in caplog.records
        )
