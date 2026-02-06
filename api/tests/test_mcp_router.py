"""Tests for MCP router endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.kene_api.auth.dependencies import get_current_user
from src.kene_api.main import app


@pytest.fixture
def mock_user_context():
    """Create a mock authenticated user context."""
    user = MagicMock()
    user.user_id = "test_user"
    user.email = "test@example.com"
    user.is_super_admin = True
    user.has_account_access = MagicMock(return_value=True)
    return user


@pytest.fixture
def test_client(mock_user_context):
    """Create a test client with auth dependency overridden."""
    app.dependency_overrides[get_current_user] = lambda: mock_user_context
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def mock_mcp_manager():
    """Create a mock MCP manager."""
    manager = MagicMock()
    manager.get_status.return_value = {
        "loaded_count": 2,
        "max_servers": 10,
        "total_tokens": 1500,
        "max_tokens": 15000,
        "servers": [
            {
                "name": "test_server_1",
                "tool_count": 5,
                "tokens": 800,
                "loaded_at": "2026-02-06T10:00:00",
                "last_used": "2026-02-06T10:30:00",
                "health_status": "healthy",
            },
            {
                "name": "test_server_2",
                "tool_count": 3,
                "tokens": 700,
                "loaded_at": "2026-02-06T09:00:00",
                "last_used": "2026-02-06T09:30:00",
                "health_status": "degraded",
            },
        ],
    }
    manager.is_loaded.return_value = True
    manager.load_server = AsyncMock()
    manager.unload_server = AsyncMock()
    return manager


@pytest.fixture
def mock_config_loader():
    """Create a mock config loader."""
    loader = MagicMock()

    config1 = MagicMock()
    config1.description = "Test Server 1"
    config1.category = "testing"
    config1.tool_count = 5
    config1.estimated_tokens = 800
    config1.enabled = True
    config1.connection.connection_type = "stdio"

    config2 = MagicMock()
    config2.description = "Test Server 2"
    config2.category = "testing"
    config2.tool_count = 3
    config2.estimated_tokens = 700
    config2.enabled = False
    config2.connection.connection_type = "sse"

    loader._configs = {
        "test_server_1": config1,
        "test_server_2": config2,
    }
    return loader


@pytest.fixture
def mock_usage_tracker():
    """Create a mock usage tracker."""
    tracker = MagicMock()
    tracker.get_pending_count.return_value = 5
    tracker.get_stored_count.return_value = 100
    tracker._use_firestore = False
    tracker.flush = AsyncMock()

    # Mock aggregation result
    agg = MagicMock()
    agg.period_start = datetime(2026, 2, 1, tzinfo=timezone.utc)
    agg.period_end = datetime(2026, 2, 6, tzinfo=timezone.utc)
    agg.total_calls = 50
    agg.success_count = 45
    agg.failure_count = 5
    agg.success_rate = 0.9
    agg.avg_duration_ms = 150.0
    agg.total_tokens = 1000
    agg.by_tool = {"analytics": 30, "crm": 20}
    agg.by_user = {"user1": 25, "user2": 25}
    agg.by_status = {"success": 45, "failure": 5}
    tracker.get_usage_aggregation = AsyncMock(return_value=agg)

    return tracker


@pytest.fixture
def mock_timeout_manager():
    """Create a mock timeout manager."""
    manager = MagicMock()
    manager.config.warning_minutes = 25
    manager.config.timeout_minutes = 30
    manager.config.check_interval_seconds = 60
    manager._activity = {"user1:session1": datetime.now(timezone.utc)}
    manager._warned = set()
    return manager


@pytest.fixture
def mock_recovery_service():
    """Create a mock recovery service."""
    service = MagicMock()
    service.RECOVERY_WINDOW_DAYS = 7
    service.list_recoverable_sessions = AsyncMock(return_value=[])
    return service


class TestMCPStatusEndpoints:
    """Tests for MCP status endpoints."""

    def test_get_mcp_status(
        self,
        test_client,
        mock_mcp_manager,
    ):
        """Test GET /api/v1/mcp/status returns server status."""
        with patch(
            "src.kene_api.routers.mcp._get_mcp_manager",
            return_value=mock_mcp_manager,
        ):
            response = test_client.get("/api/v1/mcp/status")

        assert response.status_code == 200
        data = response.json()
        assert data["loaded_count"] == 2
        assert data["max_servers"] == 10
        assert data["total_tokens"] == 1500
        assert len(data["servers"]) == 2

    def test_get_mcp_health(
        self,
        test_client,
        mock_mcp_manager,
    ):
        """Test GET /api/v1/mcp/health returns health status."""
        with patch(
            "src.kene_api.routers.mcp._get_mcp_manager",
            return_value=mock_mcp_manager,
        ):
            response = test_client.get("/api/v1/mcp/health")

        assert response.status_code == 200
        data = response.json()
        assert data["overall_status"] == "degraded"  # One server is degraded
        assert data["healthy_count"] == 1
        assert data["degraded_count"] == 1
        assert data["unhealthy_count"] == 0

    def test_get_mcp_config(
        self,
        test_client,
        mock_config_loader,
    ):
        """Test GET /api/v1/mcp/config returns configuration."""
        with patch(
            "src.kene_api.routers.mcp._get_mcp_config_loader",
            return_value=mock_config_loader,
        ):
            response = test_client.get("/api/v1/mcp/config")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["enabled_count"] == 1
        assert len(data["servers"]) == 2


class TestMCPLoadEndpoints:
    """Tests for MCP load/unload endpoints."""

    def test_load_server_success(
        self,
        test_client,
        mock_mcp_manager,
    ):
        """Test POST /api/v1/mcp/load successfully loads server."""
        mock_mcp_manager.load_server.return_value = [
            {"name": "tool1"},
            {"name": "tool2"},
            {"name": "tool3"},
        ]

        with patch(
            "src.kene_api.routers.mcp._get_mcp_manager",
            return_value=mock_mcp_manager,
        ):
            response = test_client.post(
                "/api/v1/mcp/load",
                json={"server_name": "test_server"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "loaded"
        assert data["server_name"] == "test_server"
        assert data["tool_count"] == 3

    def test_load_server_not_found(
        self,
        test_client,
        mock_mcp_manager,
    ):
        """Test POST /api/v1/mcp/load returns 404 for unknown server."""
        mock_mcp_manager.load_server.side_effect = ValueError("Unknown server")

        with patch(
            "src.kene_api.routers.mcp._get_mcp_manager",
            return_value=mock_mcp_manager,
        ):
            response = test_client.post(
                "/api/v1/mcp/load",
                json={"server_name": "nonexistent"},
            )

        assert response.status_code == 404

    def test_unload_server_success(
        self,
        test_client,
        mock_mcp_manager,
    ):
        """Test POST /api/v1/mcp/unload/{name} successfully unloads."""
        with patch(
            "src.kene_api.routers.mcp._get_mcp_manager",
            return_value=mock_mcp_manager,
        ):
            response = test_client.post("/api/v1/mcp/unload/test_server")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unloaded"

    def test_unload_server_not_loaded(
        self,
        test_client,
        mock_mcp_manager,
    ):
        """Test POST /api/v1/mcp/unload/{name} returns 404 if not loaded."""
        mock_mcp_manager.is_loaded.return_value = False

        with patch(
            "src.kene_api.routers.mcp._get_mcp_manager",
            return_value=mock_mcp_manager,
        ):
            response = test_client.post("/api/v1/mcp/unload/not_loaded")

        assert response.status_code == 404


class TestToolUsageEndpoints:
    """Tests for tool usage tracking endpoints."""

    def test_get_tool_usage(
        self,
        test_client,
        mock_usage_tracker,
    ):
        """Test GET /api/v1/mcp/tools/usage returns usage stats."""
        with patch(
            "src.kene_api.routers.mcp._get_usage_tracker",
            return_value=mock_usage_tracker,
        ):
            response = test_client.get(
                "/api/v1/mcp/tools/usage",
                params={"account_id": "test_account", "days": 7},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total_calls"] == 50
        assert data["success_rate"] == 0.9
        assert data["by_tool"]["analytics"] == 30

    def test_get_tool_usage_pending(
        self,
        test_client,
        mock_usage_tracker,
    ):
        """Test GET /api/v1/mcp/tools/usage/pending returns pending info."""
        with patch(
            "src.kene_api.routers.mcp._get_usage_tracker",
            return_value=mock_usage_tracker,
        ):
            response = test_client.get("/api/v1/mcp/tools/usage/pending")

        assert response.status_code == 200
        data = response.json()
        assert data["pending_count"] == 5
        assert data["stored_count"] == 100
        assert data["using_firestore"] is False

    def test_flush_tool_usage(
        self,
        test_client,
        mock_usage_tracker,
    ):
        """Test POST /api/v1/mcp/tools/usage/flush flushes events."""
        mock_usage_tracker.get_pending_count.side_effect = [5, 0]  # Before and after

        with patch(
            "src.kene_api.routers.mcp._get_usage_tracker",
            return_value=mock_usage_tracker,
        ):
            response = test_client.post("/api/v1/mcp/tools/usage/flush")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "flushed"
        assert data["events_flushed"] == 5


class TestSessionStatusEndpoints:
    """Tests for session status endpoints."""

    def test_get_session_status(
        self,
        test_client,
        mock_timeout_manager,
        mock_recovery_service,
    ):
        """Test GET /api/v1/mcp/sessions/status returns session status."""
        with patch(
            "src.kene_api.routers.mcp._get_timeout_manager",
            return_value=mock_timeout_manager,
        ), patch(
            "src.kene_api.routers.mcp._get_recovery_service",
            return_value=mock_recovery_service,
        ):
            response = test_client.get("/api/v1/mcp/sessions/status")

        assert response.status_code == 200
        data = response.json()
        assert data["timeout_config"]["warning_minutes"] == 25
        assert data["timeout_config"]["timeout_minutes"] == 30
        assert data["recovery_window_days"] == 7


class TestAdminDashboard:
    """Tests for admin dashboard endpoint."""

    def test_get_admin_dashboard(
        self,
        test_client,
        mock_mcp_manager,
        mock_usage_tracker,
    ):
        """Test GET /api/v1/mcp/admin/dashboard returns complete status."""
        with patch(
            "src.kene_api.routers.mcp._get_mcp_manager",
            return_value=mock_mcp_manager,
        ), patch(
            "src.kene_api.routers.mcp._get_usage_tracker",
            return_value=mock_usage_tracker,
        ):
            response = test_client.get("/api/v1/mcp/admin/dashboard")

        assert response.status_code == 200
        data = response.json()
        assert "mcp_servers" in data
        assert "mcp_health" in data
        assert "tool_usage_pending" in data
        assert "session_status" in data
        assert "features_enabled" in data
        assert data["features_enabled"]["mcp_lazy_loading"] is True
