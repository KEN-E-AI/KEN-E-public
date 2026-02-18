"""Tests for MCP server configuration module."""

from __future__ import annotations

import pytest
import yaml

from app.adk.mcp_config.config import (
    MCPConfigLoader,
    MCPServerConfig,
    SseConnectionConfig,
    StdioConnectionConfig,
    _resolve_env_pattern,
)


class TestStdioConnectionConfig:
    """Tests for StdioConnectionConfig."""

    def test_basic_config(self):
        """Test creating a basic stdio config."""
        config = StdioConnectionConfig(
            command="npx",
            args=["-y", "test-server"],
        )
        assert config.connection_type == "stdio"
        assert config.command == "npx"
        assert config.args == ["-y", "test-server"]
        assert config.env == {}

    def test_env_var_resolution(self, monkeypatch):
        """Test environment variable resolution in env dict."""
        monkeypatch.setenv("TEST_API_KEY", "secret123")
        monkeypatch.setenv("TEST_PROJECT", "my-project")

        config = StdioConnectionConfig(
            command="npx",
            args=["-y", "test-server"],
            env={
                "API_KEY": "${TEST_API_KEY}",
                "PROJECT": "${TEST_PROJECT}",
                "STATIC": "plain_value",
            },
        )

        assert config.env["API_KEY"] == "secret123"
        assert config.env["PROJECT"] == "my-project"
        assert config.env["STATIC"] == "plain_value"

    def test_missing_env_var_becomes_empty(self, monkeypatch):
        """Test that missing env vars become empty strings."""
        monkeypatch.delenv("NONEXISTENT_VAR", raising=False)

        config = StdioConnectionConfig(
            command="npx",
            env={"KEY": "${NONEXISTENT_VAR}"},
        )

        assert config.env["KEY"] == ""


class TestSseConnectionConfig:
    """Tests for SseConnectionConfig."""

    def test_basic_config(self):
        """Test creating a basic SSE config."""
        config = SseConnectionConfig(
            url="https://mcp.example.com/api",
        )
        assert config.connection_type == "sse"
        assert config.url == "https://mcp.example.com/api"
        assert config.timeout_seconds == 30
        assert config.headers == {}

    def test_url_resolution(self, monkeypatch):
        """Test URL with environment variable."""
        monkeypatch.setenv("MCP_HOST", "https://mcp.example.com")

        config = SseConnectionConfig(
            url="${MCP_HOST}/api",
        )

        assert config.url == "https://mcp.example.com/api"

    def test_header_resolution(self, monkeypatch):
        """Test header values with environment variables."""
        monkeypatch.setenv("API_TOKEN", "bearer_token_123")

        config = SseConnectionConfig(
            url="https://example.com",
            headers={
                "Authorization": "Bearer ${API_TOKEN}",
                "Content-Type": "application/json",
            },
        )

        assert config.headers["Authorization"] == "Bearer bearer_token_123"
        assert config.headers["Content-Type"] == "application/json"

    def test_timeout_validation(self):
        """Test timeout bounds validation."""
        # Valid timeout
        config = SseConnectionConfig(url="https://example.com", timeout_seconds=60)
        assert config.timeout_seconds == 60

        # Too low
        with pytest.raises(ValueError):
            SseConnectionConfig(url="https://example.com", timeout_seconds=1)

        # Too high
        with pytest.raises(ValueError):
            SseConnectionConfig(url="https://example.com", timeout_seconds=500)


class TestMCPServerConfig:
    """Tests for MCPServerConfig."""

    def test_stdio_server_config(self):
        """Test creating a server config with stdio connection."""
        config = MCPServerConfig(
            name="test_server",
            description="Test server",
            category="testing",
            connection=StdioConnectionConfig(
                command="npx",
                args=["-y", "test"],
            ),
        )

        assert config.name == "test_server"
        assert config.category == "testing"
        assert config.enabled is True
        assert config.tool_count == 0
        assert config.estimated_tokens == 1000

    def test_sse_server_config(self):
        """Test creating a server config with SSE connection."""
        config = MCPServerConfig(
            name="remote_server",
            description="Remote MCP server",
            category="analytics",
            tool_count=12,
            estimated_tokens=1800,
            keywords=["analytics", "data"],
            connection=SseConnectionConfig(url="https://mcp.example.com"),
        )

        assert config.name == "remote_server"
        assert config.tool_count == 12
        assert config.estimated_tokens == 1800
        assert config.keywords == ["analytics", "data"]

    def test_sse_empty_url_raises(self):
        """Test that SSE config without URL raises validation error."""
        with pytest.raises(ValueError, match="requires a non-empty URL"):
            MCPServerConfig(
                name="bad_server",
                description="Test",
                category="test",
                connection=SseConnectionConfig(url=""),
            )

    def test_disabled_server(self):
        """Test creating a disabled server config."""
        config = MCPServerConfig(
            name="disabled_server",
            description="Disabled server",
            category="test",
            enabled=False,
            connection=StdioConnectionConfig(command="test"),
        )

        assert config.enabled is False


class TestMCPConfigLoader:
    """Tests for MCPConfigLoader."""

    def test_load_valid_config(self, tmp_path):
        """Test loading a valid YAML config."""
        config_content = {
            "servers": {
                "test_server": {
                    "description": "Test server",
                    "category": "testing",
                    "tool_count": 5,
                    "estimated_tokens": 500,
                    "keywords": ["test"],
                    "connection": {
                        "connection_type": "stdio",
                        "command": "npx",
                        "args": ["-y", "test"],
                    },
                    "enabled": True,
                }
            }
        }

        config_file = tmp_path / "mcp_servers.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        loader = MCPConfigLoader(config_path=config_file)
        configs = loader.load()

        assert "test_server" in configs
        assert configs["test_server"].name == "test_server"
        assert configs["test_server"].category == "testing"
        assert configs["test_server"].tool_count == 5

    def test_load_missing_file_returns_empty(self, tmp_path):
        """Test that missing config file returns empty dict."""
        loader = MCPConfigLoader(config_path=tmp_path / "nonexistent.yaml")
        configs = loader.load()

        assert configs == {}

    def test_get_enabled_servers(self, tmp_path):
        """Test filtering to only enabled servers."""
        config_content = {
            "servers": {
                "enabled_server": {
                    "description": "Enabled",
                    "category": "test",
                    "connection": {"connection_type": "stdio", "command": "test"},
                    "enabled": True,
                },
                "disabled_server": {
                    "description": "Disabled",
                    "category": "test",
                    "connection": {"connection_type": "stdio", "command": "test"},
                    "enabled": False,
                },
            }
        }

        config_file = tmp_path / "mcp_servers.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        loader = MCPConfigLoader(config_path=config_file)
        loader.load()

        enabled = loader.get_enabled_servers()

        assert len(enabled) == 1
        assert enabled[0].name == "enabled_server"

    def test_get_servers_by_category(self, tmp_path):
        """Test filtering servers by category."""
        config_content = {
            "servers": {
                "analytics_server": {
                    "description": "Analytics",
                    "category": "analytics",
                    "connection": {"connection_type": "stdio", "command": "test"},
                },
                "crm_server": {
                    "description": "CRM",
                    "category": "crm",
                    "connection": {"connection_type": "stdio", "command": "test"},
                },
            }
        }

        config_file = tmp_path / "mcp_servers.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        loader = MCPConfigLoader(config_path=config_file)
        loader.load()

        analytics = loader.get_servers_by_category("analytics")

        assert len(analytics) == 1
        assert analytics[0].name == "analytics_server"

    def test_invalid_config_is_skipped(self, tmp_path, caplog):
        """Test that invalid configs are skipped with error logging."""
        config_content = {
            "servers": {
                "valid_server": {
                    "description": "Valid",
                    "category": "test",
                    "connection": {"connection_type": "stdio", "command": "test"},
                },
                "invalid_server": {
                    # Missing required 'description' field
                    "category": "test",
                    "connection": {"connection_type": "stdio", "command": "test"},
                },
            }
        }

        config_file = tmp_path / "mcp_servers.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        loader = MCPConfigLoader(config_path=config_file)
        configs = loader.load()

        # Only valid server should be loaded
        assert "valid_server" in configs
        assert "invalid_server" not in configs


class TestResolveEnvPattern:
    """Tests for _resolve_env_pattern function."""

    def test_no_pattern(self):
        """Test string without patterns passes through."""
        assert _resolve_env_pattern("plain_string") == "plain_string"

    def test_single_pattern(self, monkeypatch):
        """Test resolving a single pattern."""
        monkeypatch.setenv("MY_VAR", "resolved_value")
        assert _resolve_env_pattern("${MY_VAR}") == "resolved_value"

    def test_multiple_patterns(self, monkeypatch):
        """Test resolving multiple patterns in one string."""
        monkeypatch.setenv("HOST", "example.com")
        monkeypatch.setenv("PORT", "8080")

        result = _resolve_env_pattern("https://${HOST}:${PORT}/api")
        assert result == "https://example.com:8080/api"

    def test_pattern_with_surrounding_text(self, monkeypatch):
        """Test pattern embedded in other text."""
        monkeypatch.setenv("TOKEN", "abc123")

        result = _resolve_env_pattern("Bearer ${TOKEN}")
        assert result == "Bearer abc123"

    def test_missing_var_becomes_empty(self, monkeypatch):
        """Test missing variable becomes empty string."""
        monkeypatch.delenv("MISSING_VAR", raising=False)

        result = _resolve_env_pattern("prefix_${MISSING_VAR}_suffix")
        assert result == "prefix__suffix"
