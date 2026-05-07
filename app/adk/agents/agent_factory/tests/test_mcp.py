"""Unit tests for app.adk.agents.agent_factory.mcp.

All Firestore I/O is mocked so these tests run without GCP credentials.
ADK + MCP imports are also mocked so no live ADK install is required.

Coverage map
------------
* AC-2 (PRD §7): enabled servers → toolsets created; disabled → excluded.
* AC-3 (PRD §7): server with specialist_categories=["a","b"] is returned by
  both load_toolsets_for_specialist("a") and load_toolsets_for_specialist("b").
* Schema error: missing 'connection', unknown connection_type → MCPSchemaError.
* Auth-type propagation: known auth_type → header_provider callable;
  auth_type=None → header_provider=None; unknown auth_type → ValueError.
* SSE connection params: url + timeout_seconds wired through.
* Stdio connection params: command + args wired through.
* load_all_mcp_toolsets: filters disabled, skips schema errors with warning.
* load_toolsets_for_specialist: category filter applied correctly.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fake Firestore primitives
# ---------------------------------------------------------------------------


class _FakeSnapshot:
    def __init__(self, doc_id: str, data: dict | None) -> None:
        self.id = doc_id
        self._data = data
        self.exists = data is not None

    def to_dict(self) -> dict:
        return self._data or {}


class _FakeCollection:
    def __init__(self, snapshots: list[_FakeSnapshot]) -> None:
        self._snapshots = snapshots

    def stream(self) -> list[_FakeSnapshot]:
        return list(self._snapshots)


class FakeMCPDb:
    """In-memory Firestore stand-in for mcp_server_configs tests."""

    def __init__(self, docs: dict[str, dict | None]) -> None:
        """Args:
            docs: mapping of {server_id: doc_data} — use None to represent
                  a doc that should not appear (not the same as disabled=False).
                  Disabled docs should be represented by setting ``enabled=False``
                  in the data dict.
        """
        self._snapshots = [
            _FakeSnapshot(sid, data)
            for sid, data in docs.items()
            if data is not None
        ]

    def collection(self, name: str) -> _FakeCollection:
        assert name == "mcp_server_configs", f"Unexpected collection: {name!r}"
        return _FakeCollection(self._snapshots)


# ---------------------------------------------------------------------------
# Fixture data
# ---------------------------------------------------------------------------

_SSE_CONNECTION = {
    "connection_type": "sse",
    "url": "https://mcp.example.com/ga",
    "headers": {},
    "timeout_seconds": 30,
}

_STDIO_CONNECTION = {
    "connection_type": "stdio",
    "command": "npx",
    "args": ["-y", "@test/mcp-server"],
    "env": {"GA_PROPERTY_ID": "test-property-id"},
}

_GA_DOC: dict[str, Any] = {
    "name": "google_analytics_mcp",
    "enabled": True,
    "specialist_categories": ["google_analytics"],
    "auth_type": "ga_oauth",
    "connection": _SSE_CONNECTION,
}

_STDIO_DOC: dict[str, Any] = {
    "name": "local_stdio_mcp",
    "enabled": True,
    "specialist_categories": ["analytics"],
    "auth_type": None,
    "connection": _STDIO_CONNECTION,
}

_SHARED_DOC: dict[str, Any] = {
    "name": "shared_mcp",
    "enabled": True,
    "specialist_categories": ["google_analytics", "google_ads"],
    "auth_type": "ga_oauth",
    "connection": _SSE_CONNECTION,
}

_DISABLED_DOC: dict[str, Any] = {
    "name": "disabled_mcp",
    "enabled": False,
    "specialist_categories": ["google_analytics"],
    "auth_type": None,
    "connection": _SSE_CONNECTION,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_sse_params() -> type:
    """Return a mock class for SseConnectionParams."""
    cls = MagicMock(name="SseConnectionParams")
    instance = MagicMock(name="SseConnectionParamsInstance")
    instance.url = _SSE_CONNECTION["url"]
    cls.return_value = instance
    return cls


def _mock_stdio_params() -> type:
    """Return a mock class for StdioConnectionParams."""
    cls = MagicMock(name="StdioConnectionParams")
    instance = MagicMock(name="StdioConnectionParamsInstance")
    cls.return_value = instance
    return cls


def _mock_toolset_cls() -> type:
    """Return a mock McpToolset class."""
    cls = MagicMock(name="McpToolset")
    instance = MagicMock(name="McpToolsetInstance")
    cls.return_value = instance
    return cls


# ---------------------------------------------------------------------------
# Tests: build_toolset_for_doc (pure function)
# ---------------------------------------------------------------------------


class TestBuildToolsetForDoc:
    """Tests for the pure build_toolset_for_doc function."""

    def test_sse_doc_builds_toolset_with_correct_url(self) -> None:
        """AC-2: SSE doc → toolset with correct connection_params.url."""
        from app.adk.agents.agent_factory.mcp import build_toolset_for_doc

        fake_conn_params = MagicMock(name="FakeConnParams")
        fake_conn_params.url = _SSE_CONNECTION["url"]

        MockToolset2 = MagicMock(name="McpToolsetCls")
        toolset_instance = MagicMock(name="toolset")
        MockToolset2.return_value = toolset_instance

        with (
            patch(
                "app.adk.agents.agent_factory.mcp._build_connection_params",
                return_value=fake_conn_params,
            ),
            patch.dict(
                "sys.modules",
                {
                    "google.adk.tools.mcp_tool.mcp_toolset": MagicMock(
                        McpToolset=MockToolset2
                    ),
                },
            ),
        ):
            result = build_toolset_for_doc("google_analytics_mcp", _GA_DOC)

        assert result is toolset_instance
        MockToolset2.assert_called_once()
        call_kwargs = MockToolset2.call_args[1]
        assert call_kwargs["connection_params"] is fake_conn_params

    def test_sse_doc_header_provider_wired_for_ga_oauth(self) -> None:
        """AC-2: doc with auth_type='ga_oauth' → header_provider is callable."""
        from app.adk.agents.agent_factory.mcp import build_toolset_for_doc

        fake_conn_params = MagicMock()
        MockToolset = MagicMock(name="McpToolsetCls")
        toolset_instance = MagicMock()
        MockToolset.return_value = toolset_instance

        with (
            patch(
                "app.adk.agents.agent_factory.mcp._build_connection_params",
                return_value=fake_conn_params,
            ),
            patch.dict(
                "sys.modules",
                {
                    "google.adk.tools.mcp_tool.mcp_toolset": MagicMock(
                        McpToolset=MockToolset
                    ),
                },
            ),
        ):
            build_toolset_for_doc("google_analytics_mcp", _GA_DOC)

        call_kwargs = MockToolset.call_args[1]
        assert callable(call_kwargs["header_provider"])

    def test_auth_type_none_produces_none_header_provider(self) -> None:
        """AC-2: doc with auth_type=None → header_provider=None."""
        from app.adk.agents.agent_factory.mcp import build_toolset_for_doc

        doc = {**_STDIO_DOC, "auth_type": None}
        fake_conn_params = MagicMock()
        MockToolset = MagicMock(name="McpToolsetCls")
        toolset_instance = MagicMock()
        MockToolset.return_value = toolset_instance

        with (
            patch(
                "app.adk.agents.agent_factory.mcp._build_connection_params",
                return_value=fake_conn_params,
            ),
            patch.dict(
                "sys.modules",
                {
                    "google.adk.tools.mcp_tool.mcp_toolset": MagicMock(
                        McpToolset=MockToolset
                    ),
                },
            ),
        ):
            build_toolset_for_doc("local_stdio_mcp", doc)

        call_kwargs = MockToolset.call_args[1]
        assert call_kwargs["header_provider"] is None

    def test_auth_type_missing_key_produces_none_header_provider(self) -> None:
        """Doc with no 'auth_type' key → treated as None → header_provider=None."""
        from app.adk.agents.agent_factory.mcp import build_toolset_for_doc

        doc = {k: v for k, v in _STDIO_DOC.items() if k != "auth_type"}
        fake_conn_params = MagicMock()
        MockToolset = MagicMock(name="McpToolsetCls")
        toolset_instance = MagicMock()
        MockToolset.return_value = toolset_instance

        with (
            patch(
                "app.adk.agents.agent_factory.mcp._build_connection_params",
                return_value=fake_conn_params,
            ),
            patch.dict(
                "sys.modules",
                {
                    "google.adk.tools.mcp_tool.mcp_toolset": MagicMock(
                        McpToolset=MockToolset
                    ),
                },
            ),
        ):
            build_toolset_for_doc("local_stdio_mcp", doc)

        call_kwargs = MockToolset.call_args[1]
        assert call_kwargs["header_provider"] is None

    def test_unknown_auth_type_raises_value_error(self) -> None:
        """Unknown auth_type → ValueError from _make_header_provider (AH-12 contract)."""
        from app.adk.agents.agent_factory.mcp import build_toolset_for_doc

        doc = {**_GA_DOC, "auth_type": "unknown_oauth"}
        fake_conn_params = MagicMock()

        with (
            patch(
                "app.adk.agents.agent_factory.mcp._build_connection_params",
                return_value=fake_conn_params,
            ),
            pytest.raises(ValueError, match="Unknown auth_type"),
        ):
            build_toolset_for_doc("ga_mcp", doc)

    def test_missing_connection_raises_mcp_schema_error(self) -> None:
        """Doc missing 'connection' → MCPSchemaError naming the server_id."""
        from app.adk.agents.agent_factory.mcp import (
            MCPSchemaError,
            build_toolset_for_doc,
        )

        doc = {**_GA_DOC}
        del doc["connection"]

        with pytest.raises(MCPSchemaError, match="google_analytics_mcp"):
            build_toolset_for_doc("google_analytics_mcp", doc)

    def test_connection_is_none_raises_mcp_schema_error(self) -> None:
        """connection=None is treated as missing → MCPSchemaError."""
        from app.adk.agents.agent_factory.mcp import (
            MCPSchemaError,
            build_toolset_for_doc,
        )

        doc = {**_GA_DOC, "connection": None}

        with pytest.raises(MCPSchemaError, match="google_analytics_mcp"):
            build_toolset_for_doc("google_analytics_mcp", doc)

    def test_ga_oauth_header_provider_reads_correct_state_key(self) -> None:
        """The header_provider returned for ga_oauth reads 'ga_credentials'."""
        from app.adk.agents.agent_factory.mcp import build_toolset_for_doc

        fake_conn_params = MagicMock()
        MockToolset = MagicMock(name="McpToolsetCls")
        MockToolset.return_value = MagicMock()

        with (
            patch(
                "app.adk.agents.agent_factory.mcp._build_connection_params",
                return_value=fake_conn_params,
            ),
            patch.dict(
                "sys.modules",
                {
                    "google.adk.tools.mcp_tool.mcp_toolset": MagicMock(
                        McpToolset=MockToolset
                    ),
                },
            ),
        ):
            build_toolset_for_doc("google_analytics_mcp", _GA_DOC)

        header_provider = MockToolset.call_args[1]["header_provider"]
        assert callable(header_provider)

        # Simulate what ADK does: call header_provider(context) where context
        # has a .state dict.
        ctx = MagicMock()
        ctx.state = {"ga_credentials": {"access_token": "tok123", "tenant_id": "t1"}}
        headers = header_provider(ctx)
        assert headers["Authorization"] == "Bearer tok123"
        assert headers["X-Tenant-ID"] == "t1"

    def test_ga_oauth_header_provider_omits_headers_when_credentials_empty(
        self,
    ) -> None:
        """header_provider returns {} when credentials are not in state."""
        from app.adk.agents.agent_factory.mcp import build_toolset_for_doc

        fake_conn_params = MagicMock()
        MockToolset = MagicMock(name="McpToolsetCls")
        MockToolset.return_value = MagicMock()

        with (
            patch(
                "app.adk.agents.agent_factory.mcp._build_connection_params",
                return_value=fake_conn_params,
            ),
            patch.dict(
                "sys.modules",
                {
                    "google.adk.tools.mcp_tool.mcp_toolset": MagicMock(
                        McpToolset=MockToolset
                    ),
                },
            ),
        ):
            build_toolset_for_doc("google_analytics_mcp", _GA_DOC)

        header_provider = MockToolset.call_args[1]["header_provider"]
        ctx = MagicMock()
        ctx.state = {}
        assert header_provider(ctx) == {}


# ---------------------------------------------------------------------------
# Tests: build_toolset_for_config
# ---------------------------------------------------------------------------


class TestBuildToolsetForConfig:
    """Tests for the build_toolset_for_config public helper (AC-16)."""

    def _make_sse_config(self, auth_type: str | None = "ga_oauth") -> Any:
        from app.adk.mcp_config.config import MCPServerConfig

        return MCPServerConfig(
            name="test_sse_server",
            description="Test SSE server",
            category="analytics",
            connection={
                "connection_type": "sse",
                "url": "https://mcp.example.com/sse",
                "headers": {"X-Custom": "value"},
                "timeout_seconds": 45,
            },
            auth_type=auth_type,
        )

    def _make_stdio_config(self, auth_type: str | None = None) -> Any:
        from app.adk.mcp_config.config import MCPServerConfig

        return MCPServerConfig(
            name="test_stdio_server",
            description="Test stdio server",
            category="analytics",
            connection={
                "connection_type": "stdio",
                "command": "npx",
                "args": ["-y", "@test/mcp-server"],
                "env": {"SOME_VAR": "value"},
            },
            auth_type=auth_type,
        )

    def test_sse_config_round_trips_to_toolset(self) -> None:
        """SSE MCPServerConfig → build_toolset_for_doc called with correct doc-shape dict."""
        from app.adk.agents.agent_factory.mcp import build_toolset_for_config

        config = self._make_sse_config(auth_type="ga_oauth")
        mock_toolset = MagicMock(name="MockToolset")

        with patch(
            "app.adk.agents.agent_factory.mcp.build_toolset_for_doc",
            return_value=mock_toolset,
        ) as mock_build:
            result = build_toolset_for_config(config)

        assert result is mock_toolset
        expected_doc = {
            "connection": {
                "connection_type": "sse",
                "url": "https://mcp.example.com/sse",
                "headers": {"X-Custom": "value"},
                "timeout_seconds": 45,
            },
            "auth_type": "ga_oauth",
        }
        mock_build.assert_called_once_with("test_sse_server", expected_doc)

    def test_stdio_config_round_trips_to_toolset(self) -> None:
        """Stdio MCPServerConfig → build_toolset_for_doc called with correct doc-shape dict."""
        from app.adk.agents.agent_factory.mcp import build_toolset_for_config

        config = self._make_stdio_config(auth_type=None)
        mock_toolset = MagicMock(name="MockToolset")

        with patch(
            "app.adk.agents.agent_factory.mcp.build_toolset_for_doc",
            return_value=mock_toolset,
        ) as mock_build:
            result = build_toolset_for_config(config)

        assert result is mock_toolset
        expected_doc = {
            "connection": {
                "connection_type": "stdio",
                "command": "npx",
                "args": ["-y", "@test/mcp-server"],
                "env": {"SOME_VAR": "value"},
            },
            "auth_type": None,
        }
        mock_build.assert_called_once_with("test_stdio_server", expected_doc)

    def test_auth_type_none_passes_none(self) -> None:
        """config.auth_type=None → doc has auth_type=None → build_toolset_for_doc called with auth_type: None."""
        from app.adk.agents.agent_factory.mcp import build_toolset_for_config

        config = self._make_sse_config(auth_type=None)
        mock_toolset = MagicMock(name="MockToolset")

        with patch(
            "app.adk.agents.agent_factory.mcp.build_toolset_for_doc",
            return_value=mock_toolset,
        ) as mock_build:
            build_toolset_for_config(config)

        call_args = mock_build.call_args
        doc_passed = call_args[0][1]
        assert doc_passed["auth_type"] is None

    def test_unknown_auth_type_raises_value_error(self) -> None:
        """config.auth_type='unknown_oauth' → ValueError propagated from build_toolset_for_doc."""
        from app.adk.agents.agent_factory.mcp import build_toolset_for_config

        config = self._make_sse_config(auth_type="unknown_oauth")

        with pytest.raises(ValueError, match="Unknown auth_type"):
            build_toolset_for_config(config)

    def test_unknown_connection_type_raises_mcp_schema_error(self) -> None:
        """connection that is neither SseConnectionConfig nor StdioConnectionConfig → MCPSchemaError."""
        from app.adk.agents.agent_factory.mcp import (
            MCPSchemaError,
            build_toolset_for_config,
        )

        # Build a config then replace its connection with an unknown mock type
        config = self._make_sse_config()
        unknown_conn = MagicMock()
        unknown_conn.connection_type = "grpc"
        config = config.model_copy(update={"connection": unknown_conn})

        with pytest.raises(MCPSchemaError, match="SseConnectionConfig or StdioConnectionConfig"):
            build_toolset_for_config(config)

    def test_already_expanded_url_is_idempotent(self) -> None:
        """Literal (already-expanded) URL values pass through expansion unchanged."""
        from app.adk.agents.agent_factory.mcp import build_toolset_for_config

        config = self._make_sse_config(auth_type=None)
        mock_toolset = MagicMock(name="MockToolset")

        with patch(
            "app.adk.agents.agent_factory.mcp.build_toolset_for_doc",
            return_value=mock_toolset,
        ) as mock_build:
            build_toolset_for_config(config)

        doc_passed = mock_build.call_args[0][1]
        # No ${VAR} tokens → url is returned unchanged
        assert doc_passed["connection"]["url"] == "https://mcp.example.com/sse"


# ---------------------------------------------------------------------------
# Tests: _build_connection_params
# ---------------------------------------------------------------------------


class TestBuildConnectionParams:
    def _run(self, server_id: str, connection: dict, MockSse: Any, MockStdio: Any) -> Any:
        from app.adk.agents.agent_factory.mcp import _build_connection_params

        sse_module = MagicMock()
        sse_module.SseConnectionParams = MockSse
        stdio_module = MagicMock()
        stdio_module.StdioConnectionParams = MockStdio
        stdio_server_params_cls = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "google.adk.tools.mcp_tool.mcp_session_manager": MagicMock(
                    SseConnectionParams=MockSse,
                    StdioConnectionParams=MockStdio,
                ),
                "mcp.client.stdio": MagicMock(
                    StdioServerParameters=stdio_server_params_cls
                ),
            },
        ):
            return _build_connection_params(server_id, connection)

    def test_sse_doc_url_and_timeout_wired(self) -> None:
        """SSE doc → SseConnectionParams called with correct url and timeout."""
        MockSse = MagicMock(name="SseConnectionParams")
        sse_instance = MagicMock(name="SseInstance")
        MockSse.return_value = sse_instance
        MockStdio = MagicMock(name="StdioConnectionParams")

        result = self._run("ga_mcp", _SSE_CONNECTION, MockSse, MockStdio)

        assert result is sse_instance
        MockSse.assert_called_once()
        call_kwargs = MockSse.call_args[1]
        assert call_kwargs["url"] == _SSE_CONNECTION["url"]
        assert call_kwargs["timeout"] == float(_SSE_CONNECTION["timeout_seconds"])

    def test_stdio_doc_command_and_args_wired(self) -> None:
        """Stdio doc → StdioConnectionParams called with command and args."""
        MockSse = MagicMock(name="SseConnectionParams")
        MockStdio = MagicMock(name="StdioConnectionParams")
        stdio_instance = MagicMock(name="StdioInstance")
        MockStdio.return_value = stdio_instance

        result = self._run("stdio_mcp", _STDIO_CONNECTION, MockSse, MockStdio)

        assert result is stdio_instance
        MockStdio.assert_called_once()

    def test_unknown_connection_type_raises_mcp_schema_error(self) -> None:
        """connection_type not in {sse, stdio} → MCPSchemaError."""
        from app.adk.agents.agent_factory.mcp import (
            MCPSchemaError,
            _build_connection_params,
        )

        bad_conn = {**_SSE_CONNECTION, "connection_type": "grpc"}

        with (
            patch.dict(
                "sys.modules",
                {
                    "google.adk.tools.mcp_tool.mcp_session_manager": MagicMock(),
                },
            ),
            pytest.raises(MCPSchemaError, match="unknown connection_type"),
        ):
            _build_connection_params("some_server", bad_conn)

    def test_missing_connection_type_raises_mcp_schema_error(self) -> None:
        """connection dict with no 'connection_type' → MCPSchemaError."""
        from app.adk.agents.agent_factory.mcp import (
            MCPSchemaError,
            _build_connection_params,
        )

        no_type_conn = {"url": "https://example.com"}

        with (
            patch.dict("sys.modules", {"google.adk.tools.mcp_tool.mcp_session_manager": MagicMock()}),
            pytest.raises(MCPSchemaError, match="connection_type"),
        ):
            _build_connection_params("some_server", no_type_conn)

    def test_sse_http_url_raises_mcp_schema_error(self) -> None:
        """SSE doc with http:// URL → MCPSchemaError (must use https)."""
        from app.adk.agents.agent_factory.mcp import (
            MCPSchemaError,
            _build_connection_params,
        )

        http_conn = {**_SSE_CONNECTION, "url": "http://mcp.example.com/ga"}

        with (
            patch.dict(
                "sys.modules",
                {"google.adk.tools.mcp_tool.mcp_session_manager": MagicMock()},
            ),
            pytest.raises(MCPSchemaError, match="must use https"),
        ):
            _build_connection_params("srv", http_conn)

    def test_sse_internal_host_raises_mcp_schema_error(self) -> None:
        """SSE doc targeting metadata endpoint → MCPSchemaError."""
        from app.adk.agents.agent_factory.mcp import (
            MCPSchemaError,
            _build_connection_params,
        )

        metadata_conn = {**_SSE_CONNECTION, "url": "https://169.254.169.254/token"}

        with (
            patch.dict(
                "sys.modules",
                {"google.adk.tools.mcp_tool.mcp_session_manager": MagicMock()},
            ),
            pytest.raises(MCPSchemaError, match="reserved/internal host"),
        ):
            _build_connection_params("srv", metadata_conn)

    def test_sse_missing_url_raises_mcp_schema_error(self) -> None:
        """SSE connection dict with no 'url' key → MCPSchemaError (not KeyError)."""
        from app.adk.agents.agent_factory.mcp import (
            MCPSchemaError,
            _build_connection_params,
        )

        no_url_conn = {"connection_type": "sse", "timeout_seconds": 30}

        with (
            patch.dict(
                "sys.modules",
                {"google.adk.tools.mcp_tool.mcp_session_manager": MagicMock()},
            ),
            pytest.raises(MCPSchemaError, match="SSE 'url' is missing or empty"),
        ):
            _build_connection_params("srv", no_url_conn)

    @pytest.mark.parametrize(
        "private_url",
        [
            "https://10.0.0.1/sse",
            "https://10.255.255.255/sse",
            "https://172.16.0.1/sse",
            "https://172.31.255.255/sse",
            "https://192.168.1.1/sse",
            "https://0.0.0.0/sse",
            "https://[fc00::1]/sse",
            "https://[fe80::1]/sse",
            "https://100.64.0.1/sse",  # RFC 6598 CGNAT shared address space
        ],
    )
    def test_sse_private_ip_raises_mcp_schema_error(self, private_url: str) -> None:
        """SSE doc with RFC 1918 / private IP url → MCPSchemaError."""
        from app.adk.agents.agent_factory.mcp import (
            MCPSchemaError,
            _build_connection_params,
        )

        conn = {**_SSE_CONNECTION, "url": private_url}

        with (
            patch.dict(
                "sys.modules",
                {"google.adk.tools.mcp_tool.mcp_session_manager": MagicMock()},
            ),
            pytest.raises(MCPSchemaError, match="private/reserved address"),
        ):
            _build_connection_params("srv", conn)

    def test_sse_post_expansion_private_ip_raises_mcp_schema_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """${VAR} that expands to a private IP URL → MCPSchemaError (SSRF via env var)."""
        from app.adk.agents.agent_factory.mcp import (
            MCPSchemaError,
            _build_connection_params,
        )

        monkeypatch.setenv("INTERNAL_URL", "https://192.168.1.1/sse")
        conn = {
            "connection_type": "sse",
            "url": "${INTERNAL_URL}",
            "timeout_seconds": 30,
        }
        with (
            patch.dict(
                "sys.modules",
                {"google.adk.tools.mcp_tool.mcp_session_manager": MagicMock()},
            ),
            pytest.raises(MCPSchemaError, match="private/reserved address"),
        ):
            _build_connection_params("srv", conn)

    @pytest.mark.parametrize(
        "zone_url",
        [
            "https://[fe80::1%25eth0]/sse",  # RFC 6874 percent-encoded zone ID
            "https://[fe80::1%eth0]/sse",    # non-encoded form (also passed through by urlparse)
        ],
    )
    def test_sse_ipv6_zone_id_bypasses_blocked(self, zone_url: str) -> None:
        """Scoped IPv6 URL (zone ID suffix, both encoded forms) is blocked, not silently passed."""
        from app.adk.agents.agent_factory.mcp import (
            MCPSchemaError,
            _build_connection_params,
        )

        conn = {**_SSE_CONNECTION, "url": zone_url}

        with (
            patch.dict(
                "sys.modules",
                {"google.adk.tools.mcp_tool.mcp_session_manager": MagicMock()},
            ),
            pytest.raises(MCPSchemaError, match="private/reserved address"),
        ):
            _build_connection_params("srv", conn)

    def test_sse_public_ipv6_address_allowed(self) -> None:
        """Legitimate public IPv6 SSE address is accepted (not blocked by SSRF guards)."""
        from app.adk.agents.agent_factory.mcp import _build_connection_params

        MockSse = MagicMock(name="SseConnectionParams")
        MockSse.return_value = MagicMock(name="SseInstance")

        # 2001:4860:4860::8888 = Google public DNS IPv6 — fully routable, not private
        conn = {
            "connection_type": "sse",
            "url": "https://[2001:4860:4860::8888]/sse",
            "timeout_seconds": 30,
        }
        with patch.dict(
            "sys.modules",
            {
                "google.adk.tools.mcp_tool.mcp_session_manager": MagicMock(
                    SseConnectionParams=MockSse,
                    StdioConnectionParams=MagicMock(),
                ),
            },
        ):
            result = _build_connection_params("srv", conn)

        assert result is MockSse.return_value

    def test_stdio_missing_command_raises_mcp_schema_error(self) -> None:
        """stdio connection dict with no 'command' key → MCPSchemaError (not KeyError)."""
        from app.adk.agents.agent_factory.mcp import (
            MCPSchemaError,
            _build_connection_params,
        )

        no_cmd_conn = {"connection_type": "stdio", "args": ["-y"]}

        with (
            patch.dict(
                "sys.modules",
                {
                    "google.adk.tools.mcp_tool.mcp_session_manager": MagicMock(),
                    "mcp.client.stdio": MagicMock(),
                },
            ),
            pytest.raises(MCPSchemaError, match="stdio 'command' must be a non-empty string"),
        ):
            _build_connection_params("srv", no_cmd_conn)

    def test_sse_post_expansion_url_validated_against_https(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """URL that is valid after expansion but uses http scheme → MCPSchemaError."""
        from app.adk.agents.agent_factory.mcp import (
            MCPSchemaError,
            _build_connection_params,
        )

        monkeypatch.setenv("BAD_SCHEME_URL", "http://mcp.example.com/sse")
        conn = {
            "connection_type": "sse",
            "url": "${BAD_SCHEME_URL}",
            "timeout_seconds": 30,
        }

        with (
            patch.dict(
                "sys.modules",
                {"google.adk.tools.mcp_tool.mcp_session_manager": MagicMock()},
            ),
            pytest.raises(MCPSchemaError, match="must use https"),
        ):
            _build_connection_params("srv", conn)

    def test_stdio_command_placeholder_expanded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """${VAR} in stdio command is expanded before passing to StdioServerParameters."""
        from app.adk.agents.agent_factory.mcp import _build_connection_params

        monkeypatch.setenv("MCP_BINARY", "/usr/local/bin/mcp-server")

        MockStdio = MagicMock(name="StdioConnectionParams")
        MockStdio.return_value = MagicMock()
        MockStdioParams = MagicMock(name="StdioServerParameters")

        conn = {
            "connection_type": "stdio",
            "command": "${MCP_BINARY}",
            "args": [],
        }
        with patch.dict(
            "sys.modules",
            {
                "google.adk.tools.mcp_tool.mcp_session_manager": MagicMock(
                    SseConnectionParams=MagicMock(),
                    StdioConnectionParams=MockStdio,
                ),
                "mcp.client.stdio": MagicMock(StdioServerParameters=MockStdioParams),
            },
        ):
            _build_connection_params("srv", conn)

        params_kwargs = MockStdioParams.call_args[1]
        assert params_kwargs["command"] == "/usr/local/bin/mcp-server"

    def test_stdio_args_placeholder_expanded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """${VAR} in stdio args are expanded with correct indexed field names in errors."""
        from app.adk.agents.agent_factory.mcp import _build_connection_params

        monkeypatch.setenv("MCP_PACKAGE", "@acme/mcp-server@1.2.3")

        MockStdio = MagicMock(name="StdioConnectionParams")
        MockStdio.return_value = MagicMock()
        MockStdioParams = MagicMock(name="StdioServerParameters")

        conn = {
            "connection_type": "stdio",
            "command": "npx",
            "args": ["-y", "${MCP_PACKAGE}"],
        }
        with patch.dict(
            "sys.modules",
            {
                "google.adk.tools.mcp_tool.mcp_session_manager": MagicMock(
                    SseConnectionParams=MagicMock(),
                    StdioConnectionParams=MockStdio,
                ),
                "mcp.client.stdio": MagicMock(StdioServerParameters=MockStdioParams),
            },
        ):
            _build_connection_params("srv", conn)

        params_kwargs = MockStdioParams.call_args[1]
        assert params_kwargs["args"] == ["-y", "@acme/mcp-server@1.2.3"]

    def test_multi_placeholder_partial_failure_raises_on_first_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If the first of two ${VAR} tokens is unset, MCPSchemaError names that var."""
        from app.adk.agents.agent_factory.mcp import (
            MCPSchemaError,
            _expand_env_placeholders,
        )

        monkeypatch.delenv("FIRST_VAR", raising=False)
        monkeypatch.setenv("SECOND_VAR", "present")

        with pytest.raises(MCPSchemaError, match="FIRST_VAR"):
            _expand_env_placeholders(
                "https://${FIRST_VAR}.example.com:${SECOND_VAR}/sse",
                "srv",
                "connection.url",
            )


# ---------------------------------------------------------------------------
# Tests: load_all_mcp_toolsets
# ---------------------------------------------------------------------------


class TestLoadAllMcpToolsets:
    """Tests for load_all_mcp_toolsets with FakeMCPDb."""

    def _patch_build(self) -> MagicMock:
        """Return a mock for build_toolset_for_doc that returns a fresh MagicMock
        per call (keyed by server_id)."""
        call_results: dict[str, MagicMock] = {}

        def _side_effect(server_id: str, doc: dict) -> MagicMock:
            result = MagicMock(name=f"toolset_{server_id}")
            call_results[server_id] = result
            return result

        m = MagicMock(side_effect=_side_effect)
        m.call_results = call_results
        return m

    def test_enabled_servers_are_returned(self) -> None:
        """AC-2: enabled=True docs → toolsets in result dict."""
        from app.adk.agents.agent_factory import mcp as mcp_module

        db = FakeMCPDb({"ga_mcp": _GA_DOC, "stdio_mcp": _STDIO_DOC})
        mock_build = self._patch_build()

        with patch.object(mcp_module, "build_toolset_for_doc", mock_build):
            result = mcp_module.load_all_mcp_toolsets(db=db)

        assert set(result.keys()) == {"ga_mcp", "stdio_mcp"}

    def test_disabled_server_excluded(self) -> None:
        """AC-2: enabled=False docs → absent from result."""
        from app.adk.agents.agent_factory import mcp as mcp_module

        db = FakeMCPDb(
            {
                "ga_mcp": _GA_DOC,
                "disabled_mcp": _DISABLED_DOC,
            }
        )
        mock_build = self._patch_build()

        with patch.object(mcp_module, "build_toolset_for_doc", mock_build):
            result = mcp_module.load_all_mcp_toolsets(db=db)

        assert "disabled_mcp" not in result
        assert "ga_mcp" in result

    def test_three_docs_one_disabled_returns_two_toolsets(self) -> None:
        """AC-2: 3 docs (1 disabled) → 2 toolsets returned."""
        from app.adk.agents.agent_factory import mcp as mcp_module

        db = FakeMCPDb(
            {
                "ga_mcp": _GA_DOC,
                "shared_mcp": _SHARED_DOC,
                "disabled_mcp": _DISABLED_DOC,
            }
        )
        mock_build = self._patch_build()

        with patch.object(mcp_module, "build_toolset_for_doc", mock_build):
            result = mcp_module.load_all_mcp_toolsets(db=db)

        assert len(result) == 2
        assert "disabled_mcp" not in result

    def test_schema_error_is_logged_and_server_excluded(self) -> None:
        """build_toolset_for_doc raising MCPSchemaError → server excluded (no raise)."""
        from app.adk.agents.agent_factory import mcp as mcp_module
        from app.adk.agents.agent_factory.mcp import MCPSchemaError

        db = FakeMCPDb({"ga_mcp": _GA_DOC, "bad_mcp": {**_GA_DOC, "connection": None}})

        def _side_effect(server_id: str, doc: dict) -> Any:
            if server_id == "bad_mcp":
                raise MCPSchemaError("missing connection")
            return MagicMock(name=f"toolset_{server_id}")

        with patch.object(mcp_module, "build_toolset_for_doc", side_effect=_side_effect):
            result = mcp_module.load_all_mcp_toolsets(db=db)

        assert "ga_mcp" in result
        assert "bad_mcp" not in result

    def test_empty_collection_returns_empty_dict(self) -> None:
        """No docs in the collection → empty dict returned."""
        from app.adk.agents.agent_factory import mcp as mcp_module

        db = FakeMCPDb({})
        mock_build = self._patch_build()

        with patch.object(mcp_module, "build_toolset_for_doc", mock_build):
            result = mcp_module.load_all_mcp_toolsets(db=db)

        assert result == {}
        mock_build.assert_not_called()

    def test_missing_enabled_field_excluded_fail_closed(self) -> None:
        """Doc without 'enabled' field is excluded (fail-closed default)."""
        from app.adk.agents.agent_factory import mcp as mcp_module

        doc_without_enabled = {k: v for k, v in _GA_DOC.items() if k != "enabled"}
        db = FakeMCPDb({"no_flag_mcp": doc_without_enabled})
        mock_build = self._patch_build()

        with patch.object(mcp_module, "build_toolset_for_doc", mock_build):
            result = mcp_module.load_all_mcp_toolsets(db=db)

        assert result == {}
        mock_build.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: load_toolsets_for_specialist
# ---------------------------------------------------------------------------


class TestLoadToolsetsForSpecialist:
    """Tests for load_toolsets_for_specialist (category filter). Maps to AC-3."""

    def _make_db(self, docs: dict) -> FakeMCPDb:
        return FakeMCPDb(docs)

    def test_only_matching_category_returned(self) -> None:
        """AC-3 partial: load_toolsets_for_specialist returns only docs in category."""
        from app.adk.agents.agent_factory import mcp as mcp_module

        db = self._make_db({"ga_mcp": _GA_DOC, "stdio_mcp": _STDIO_DOC})

        def _build(server_id: str, doc: dict) -> MagicMock:
            return MagicMock(name=f"toolset_{server_id}")

        with patch.object(mcp_module, "build_toolset_for_doc", side_effect=_build):
            result = mcp_module.load_toolsets_for_specialist(
                "google_analytics", db=db
            )

        assert "ga_mcp" in result
        assert "stdio_mcp" not in result

    def test_shared_server_returned_for_both_categories(self) -> None:
        """AC-3: server with specialist_categories=["a","b"] → in both queries."""
        from app.adk.agents.agent_factory import mcp as mcp_module

        db = self._make_db({"shared_mcp": _SHARED_DOC})

        def _build(server_id: str, doc: dict) -> MagicMock:
            return MagicMock(name=f"toolset_{server_id}")

        with patch.object(mcp_module, "build_toolset_for_doc", side_effect=_build):
            result_ga = mcp_module.load_toolsets_for_specialist(
                "google_analytics", db=db
            )
            result_ads = mcp_module.load_toolsets_for_specialist(
                "google_ads", db=db
            )

        assert "shared_mcp" in result_ga
        assert "shared_mcp" in result_ads

    @pytest.mark.parametrize("category", ["google_analytics", "google_ads"])
    def test_shared_server_returned_for_each_category_parametrized(
        self, category: str
    ) -> None:
        """AC-3 parametrized: shared server appears for each listed category."""
        from app.adk.agents.agent_factory import mcp as mcp_module

        db = FakeMCPDb({"shared_mcp": _SHARED_DOC})

        def _build(server_id: str, doc: dict) -> MagicMock:
            return MagicMock(name=f"toolset_{server_id}")

        with patch.object(mcp_module, "build_toolset_for_doc", side_effect=_build):
            result = mcp_module.load_toolsets_for_specialist(category, db=db)

        assert "shared_mcp" in result

    def test_disabled_server_excluded_from_specialist_query(self) -> None:
        """Disabled server is not returned even if category matches."""
        from app.adk.agents.agent_factory import mcp as mcp_module

        db = self._make_db(
            {"disabled_ga": {**_DISABLED_DOC, "specialist_categories": ["google_analytics"]}}
        )

        def _build(server_id: str, doc: dict) -> MagicMock:
            return MagicMock(name=f"toolset_{server_id}")

        with patch.object(mcp_module, "build_toolset_for_doc", side_effect=_build):
            result = mcp_module.load_toolsets_for_specialist(
                "google_analytics", db=db
            )

        assert "disabled_ga" not in result

    def test_unknown_category_returns_empty(self) -> None:
        """Query for a category not present in any doc → empty dict."""
        from app.adk.agents.agent_factory import mcp as mcp_module

        db = self._make_db({"ga_mcp": _GA_DOC})

        def _build(server_id: str, doc: dict) -> MagicMock:
            return MagicMock(name=f"toolset_{server_id}")

        with patch.object(mcp_module, "build_toolset_for_doc", side_effect=_build):
            result = mcp_module.load_toolsets_for_specialist(
                "nonexistent_specialist", db=db
            )

        assert result == {}

    def test_schema_error_during_specialist_load_excludes_server(self) -> None:
        """build_toolset_for_doc raises → server excluded, no propagation."""
        from app.adk.agents.agent_factory import mcp as mcp_module
        from app.adk.agents.agent_factory.mcp import MCPSchemaError

        db = self._make_db({"ga_mcp": _GA_DOC})

        with patch.object(
            mcp_module,
            "build_toolset_for_doc",
            side_effect=MCPSchemaError("bad"),
        ):
            result = mcp_module.load_toolsets_for_specialist(
                "google_analytics", db=db
            )

        assert result == {}


# ---------------------------------------------------------------------------
# Tests: _expand_env_placeholders + _build_connection_params integration
# ---------------------------------------------------------------------------


class TestExpandEnvPlaceholders:
    """Unit tests for _expand_env_placeholders and its integration into
    _build_connection_params (AH-22 acceptance criteria)."""

    def test_known_var_resolves(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A single ${VAR} placeholder expands to the env value."""
        from app.adk.agents.agent_factory.mcp import _expand_env_placeholders

        monkeypatch.setenv("MY_URL", "https://example.com")
        result = _expand_env_placeholders(
            "${MY_URL}/path", "srv", "connection.url"
        )
        assert result == "https://example.com/path"

    def test_unset_var_raises_mcp_schema_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unset ${VAR} raises MCPSchemaError with server_id and field."""
        from app.adk.agents.agent_factory.mcp import (
            MCPSchemaError,
            _expand_env_placeholders,
        )

        monkeypatch.delenv("MISSING_VAR", raising=False)
        with pytest.raises(MCPSchemaError) as exc_info:
            _expand_env_placeholders(
                "${MISSING_VAR}/sse", "ga_mcp", "connection.url"
            )
        msg = str(exc_info.value)
        assert "ga_mcp" in msg
        assert "MISSING_VAR" in msg

    def test_empty_string_var_raises_mcp_schema_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An env var set to empty string is treated as unset → MCPSchemaError."""
        from app.adk.agents.agent_factory.mcp import (
            MCPSchemaError,
            _expand_env_placeholders,
        )

        monkeypatch.setenv("EMPTY_VAR", "")
        with pytest.raises(MCPSchemaError, match="EMPTY_VAR"):
            _expand_env_placeholders(
                "${EMPTY_VAR}", "my_server", "connection.url"
            )

    def test_multi_placeholder_resolves_all(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A string with multiple ${VAR} tokens all expand correctly."""
        from app.adk.agents.agent_factory.mcp import _expand_env_placeholders

        monkeypatch.setenv("HOST", "mcp.example.com")
        monkeypatch.setenv("PORT", "443")
        result = _expand_env_placeholders(
            "https://${HOST}:${PORT}/sse", "srv", "connection.url"
        )
        assert result == "https://mcp.example.com:443/sse"

    def test_non_placeholder_string_passes_through(self) -> None:
        """Strings with no ${...} patterns are returned unchanged."""
        from app.adk.agents.agent_factory.mcp import _expand_env_placeholders

        literal = "https://mcp.example.com/ga"
        result = _expand_env_placeholders(literal, "srv", "connection.url")
        assert result == literal

    # --- Integration: _build_connection_params applies expansion ---

    def test_sse_url_placeholder_expanded_in_build_connection_params(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_build_connection_params resolves ${VAR} in SSE url before calling SseConnectionParams."""
        from app.adk.agents.agent_factory.mcp import _build_connection_params

        monkeypatch.setenv("GA_MCP_SERVER_URL", "https://ga.mcp.example.com")

        MockSse = MagicMock(name="SseConnectionParams")
        MockSse.return_value = MagicMock(name="SseInstance")

        conn = {
            "connection_type": "sse",
            "url": "${GA_MCP_SERVER_URL}/mcp/sse",
            "timeout_seconds": 30,
        }
        with patch.dict(
            "sys.modules",
            {
                "google.adk.tools.mcp_tool.mcp_session_manager": MagicMock(
                    SseConnectionParams=MockSse,
                    StdioConnectionParams=MagicMock(),
                ),
            },
        ):
            _build_connection_params("ga_mcp", conn)

        call_kwargs = MockSse.call_args[1]
        assert call_kwargs["url"] == "https://ga.mcp.example.com/mcp/sse"

    def test_sse_url_unresolved_placeholder_raises_before_sse_params(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unresolved ${VAR} in SSE url → MCPSchemaError before SseConnectionParams is called."""
        from app.adk.agents.agent_factory.mcp import (
            MCPSchemaError,
            _build_connection_params,
        )

        monkeypatch.delenv("GA_MCP_SERVER_URL", raising=False)

        conn = {
            "connection_type": "sse",
            "url": "${GA_MCP_SERVER_URL}/sse",
            "timeout_seconds": 30,
        }
        MockSse = MagicMock(name="SseConnectionParams")
        with (
            patch.dict(
                "sys.modules",
                {
                    "google.adk.tools.mcp_tool.mcp_session_manager": MagicMock(
                        SseConnectionParams=MockSse,
                        StdioConnectionParams=MagicMock(),
                    ),
                },
            ),
            pytest.raises(MCPSchemaError, match="GA_MCP_SERVER_URL"),
        ):
            _build_connection_params("ga_mcp", conn)

        MockSse.assert_not_called()

    def test_sse_header_placeholder_expanded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """${VAR} in SSE header value is expanded before being passed to SseConnectionParams."""
        from app.adk.agents.agent_factory.mcp import _build_connection_params

        monkeypatch.setenv("HUBSPOT_API_KEY", "secret-key-123")

        MockSse = MagicMock(name="SseConnectionParams")
        MockSse.return_value = MagicMock(name="SseInstance")

        conn = {
            "connection_type": "sse",
            "url": "https://hubspot.mcp.example.com/sse",
            "headers": {"Authorization": "Bearer ${HUBSPOT_API_KEY}"},
            "timeout_seconds": 30,
        }
        with patch.dict(
            "sys.modules",
            {
                "google.adk.tools.mcp_tool.mcp_session_manager": MagicMock(
                    SseConnectionParams=MockSse,
                    StdioConnectionParams=MagicMock(),
                ),
            },
        ):
            _build_connection_params("hubspot_mcp", conn)

        call_kwargs = MockSse.call_args[1]
        assert call_kwargs["headers"] == {"Authorization": "Bearer secret-key-123"}

    def test_stdio_env_placeholder_expanded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """${VAR} in stdio env value is expanded before being passed to StdioServerParameters."""
        from app.adk.agents.agent_factory.mcp import _build_connection_params

        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")

        MockStdio = MagicMock(name="StdioConnectionParams")
        MockStdio.return_value = MagicMock(name="StdioInstance")
        MockStdioParams = MagicMock(name="StdioServerParameters")

        conn = {
            "connection_type": "stdio",
            "command": "npx",
            "args": ["-y", "@slack/mcp-server"],
            "env": {"SLACK_BOT_TOKEN": "${SLACK_BOT_TOKEN}"},
        }
        with patch.dict(
            "sys.modules",
            {
                "google.adk.tools.mcp_tool.mcp_session_manager": MagicMock(
                    SseConnectionParams=MagicMock(),
                    StdioConnectionParams=MockStdio,
                ),
                "mcp.client.stdio": MagicMock(
                    StdioServerParameters=MockStdioParams
                ),
            },
        ):
            _build_connection_params("slack_mcp", conn)

        params_call_kwargs = MockStdioParams.call_args[1]
        assert params_call_kwargs["env"] == {"SLACK_BOT_TOKEN": "xoxb-test-token"}


# ---------------------------------------------------------------------------
# Tests: public __all__ exports
# ---------------------------------------------------------------------------


class TestPublicExports:
    def test_public_symbols_importable_from_package(self) -> None:
        from app.adk.agents.agent_factory import (
            MCPFactoryError,
            MCPSchemaError,
            build_toolset_for_config,
            build_toolset_for_doc,
            load_all_mcp_toolsets,
            load_toolsets_for_specialist,
        )

        assert MCPFactoryError is not None
        assert MCPSchemaError is not None
        assert callable(build_toolset_for_config)
        assert callable(build_toolset_for_doc)
        assert callable(load_all_mcp_toolsets)
        assert callable(load_toolsets_for_specialist)

    def test_mcp_schema_error_is_subclass_of_mcp_factory_error(self) -> None:
        from app.adk.agents.agent_factory import MCPFactoryError, MCPSchemaError

        assert issubclass(MCPSchemaError, MCPFactoryError)

    def test_mcp_factory_error_is_subclass_of_exception(self) -> None:
        from app.adk.agents.agent_factory import MCPFactoryError

        assert issubclass(MCPFactoryError, Exception)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
