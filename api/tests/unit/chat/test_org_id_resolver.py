"""Unit tests for _get_organization_id_for_account helper (CH-15)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


class TestGetOrganizationIdForAccount:
    @pytest.mark.asyncio
    async def test_returns_org_id_on_success(self) -> None:
        mock_service = AsyncMock()
        mock_service.execute_query = AsyncMock(
            return_value=[{"organization_id": "org_abc123"}]
        )
        with patch(
            "src.kene_api.routers.chat.get_neo4j_service",
            new=AsyncMock(return_value=mock_service),
        ):
            from src.kene_api.routers.chat import _get_organization_id_for_account

            result = await _get_organization_id_for_account("acc_test_001")

        assert result == "org_abc123"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_results(self) -> None:
        mock_service = AsyncMock()
        mock_service.execute_query = AsyncMock(return_value=[])
        with patch(
            "src.kene_api.routers.chat.get_neo4j_service",
            new=AsyncMock(return_value=mock_service),
        ):
            from src.kene_api.routers.chat import _get_organization_id_for_account

            result = await _get_organization_id_for_account("acc_orphan")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self) -> None:
        with patch(
            "src.kene_api.routers.chat.get_neo4j_service",
            new=AsyncMock(side_effect=RuntimeError("neo4j unavailable")),
        ):
            from src.kene_api.routers.chat import _get_organization_id_for_account

            result = await _get_organization_id_for_account("acc_broken")

        assert result is None
