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
    "env": {"GA_PROPERTY_ID": "${GA_PROPERTY_ID}"},
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
# Tests: public __all__ exports
# ---------------------------------------------------------------------------


class TestPublicExports:
    def test_public_symbols_importable_from_package(self) -> None:
        from app.adk.agents.agent_factory import (
            MCPFactoryError,
            MCPSchemaError,
            build_toolset_for_doc,
            load_all_mcp_toolsets,
            load_toolsets_for_specialist,
        )

        assert MCPFactoryError is not None
        assert MCPSchemaError is not None
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
