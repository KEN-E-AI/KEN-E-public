"""Tests for the GA MCP server health ping service."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from src.kene_api.services.mcp_health_service import check_ga_mcp_health

TEST_URL = "https://ga-mcp-server.example.com"


@pytest.mark.asyncio
class TestCheckGaMcpHealth:
    """Tests for check_ga_mcp_health."""

    async def test_returns_reachable_on_200(self) -> None:
        mock_response = httpx.Response(status_code=200)
        with patch("src.kene_api.services.mcp_health_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await check_ga_mcp_health(url=TEST_URL)

        assert result == {
            "reachable": True,
            "latency_ms": pytest.approx(result["latency_ms"]),
            "url": TEST_URL,
            "error": None,
        }
        assert isinstance(result["latency_ms"], float)

    async def test_returns_reachable_on_4xx(self) -> None:
        """4xx responses mean the server is reachable (just rejecting the request)."""
        mock_response = httpx.Response(status_code=404)
        with patch("src.kene_api.services.mcp_health_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await check_ga_mcp_health(url=TEST_URL)

        assert result["reachable"] is True
        assert result["error"] is None

    async def test_returns_unreachable_on_500(self) -> None:
        mock_response = httpx.Response(status_code=500)
        with patch("src.kene_api.services.mcp_health_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await check_ga_mcp_health(url=TEST_URL)

        assert result["reachable"] is False
        assert result["error"] == "HTTP 500"

    async def test_returns_unreachable_on_timeout(self) -> None:
        with patch("src.kene_api.services.mcp_health_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("timed out")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await check_ga_mcp_health(url=TEST_URL)

        assert result == {
            "reachable": False,
            "latency_ms": pytest.approx(result["latency_ms"]),
            "url": TEST_URL,
            "error": "Connection timed out",
        }

    async def test_returns_unreachable_on_connect_error(self) -> None:
        with patch("src.kene_api.services.mcp_health_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await check_ga_mcp_health(url=TEST_URL)

        assert result["reachable"] is False
        assert "Connection failed" in result["error"]
        assert result["latency_ms"] is None

    async def test_returns_error_when_url_not_configured(self) -> None:
        with patch.dict("os.environ", {}, clear=False):
            # Ensure GA_MCP_SERVER_URL is not set
            import os
            os.environ.pop("GA_MCP_SERVER_URL", None)

            result = await check_ga_mcp_health(url="")

        assert result == {
            "reachable": False,
            "latency_ms": None,
            "url": "",
            "error": "GA_MCP_SERVER_URL not configured",
        }

    async def test_falls_back_to_env_var(self) -> None:
        mock_response = httpx.Response(status_code=200)
        with (
            patch.dict("os.environ", {"GA_MCP_SERVER_URL": TEST_URL}),
            patch("src.kene_api.services.mcp_health_service.httpx.AsyncClient") as mock_cls,
        ):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await check_ga_mcp_health()

        assert result["reachable"] is True
        assert result["url"] == TEST_URL

    async def test_strips_trailing_slash_from_url(self) -> None:
        mock_response = httpx.Response(status_code=200)
        with patch("src.kene_api.services.mcp_health_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await check_ga_mcp_health(url=f"{TEST_URL}/")

        assert result["url"] == TEST_URL
