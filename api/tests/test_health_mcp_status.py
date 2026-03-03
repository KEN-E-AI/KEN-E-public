"""Unit tests for /health endpoint MCP status section (Story 1.3.5)."""

from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from src.kene_api.main import app


def _make_mcp_status(
    loaded_count: int = 2,
    servers: list[dict] | None = None,
) -> dict:
    if servers is None:
        servers = [
            {"name": "news", "health_status": "healthy"},
            {"name": "analytics", "health_status": "healthy"},
        ]
    return {"loaded_count": loaded_count, "servers": servers}


@pytest.mark.asyncio
class TestHealthMcpStatus:
    """Verify the /health endpoint includes MCP status."""

    async def test_health_includes_mcp_key(self) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/health")
        data = response.json()
        assert "mcp" in data["services"]

    async def test_mcp_shows_loaded_servers_when_manager_available(self) -> None:
        mock_mgr = MagicMock()
        mock_mgr.get_status.return_value = _make_mcp_status()

        with patch("app.adk.mcp_config.get_mcp_manager", return_value=mock_mgr):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/health")

        data = response.json()
        mcp = data["services"]["mcp"]
        assert mcp["loaded_servers"] == 2
        assert len(mcp["servers"]) == 2
        assert mcp["servers"][0]["name"] == "news"
        assert mcp["servers"][0]["health"] == "healthy"

    async def test_mcp_shows_unavailable_when_manager_raises(self) -> None:
        with patch(
            "app.adk.mcp_config.get_mcp_manager",
            side_effect=Exception("not initialized"),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/health")

        data = response.json()
        assert data["services"]["mcp"] == "unavailable"
