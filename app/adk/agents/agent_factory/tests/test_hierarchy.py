"""Unit tests for app.adk.agents.agent_factory.hierarchy.build_hierarchy().

Covers the 8 AC-8 acceptance criteria dimensions defined in AH-17:

  AC-8a  Agent count from config
  AC-8b  MCP-server grouping
  AC-8c  code_execution flag
  AC-8d  Disabled-server exclusion
  AC-8e  auth_type validation
  AC-8f  Callback wiring
  AC-8g  Dispatch-function count
  AC-8h  Root-instruction Available Specialists content

No live GCP, ADK Agent Engine, or Weave calls are made — all heavyweight
dependencies are patched at the module boundary.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.adk.agents.agent_factory.config_loader import (
    ConfigNotFoundError,
    ConfigValidationError,
)
from app.adk.agents.agent_factory.mcp import MCPSchemaError

# ---------------------------------------------------------------------------
# Sentinel callback objects — injected at the builder module boundary
# (mirror the pattern from test_factory.py)
# ---------------------------------------------------------------------------

_WEAVE_BEFORE = MagicMock(name="weave_before_agent_callback")
_WEAVE_AFTER = MagicMock(name="weave_after_agent_callback")
_ADK_BEFORE_TOOL = MagicMock(name="adk_before_tool_callback")
_ADK_AFTER_TOOL = MagicMock(name="adk_after_tool_callback")

_PATCH_BEFORE_AGENT = patch(
    "app.adk.agents.agent_factory.builder.weave_before_agent_callback",
    _WEAVE_BEFORE,
)
_PATCH_AFTER_AGENT = patch(
    "app.adk.agents.agent_factory.builder.weave_after_agent_callback",
    _WEAVE_AFTER,
)
_PATCH_BEFORE_TOOL = patch(
    "app.adk.agents.agent_factory.builder.adk_before_tool_callback",
    _ADK_BEFORE_TOOL,
)
_PATCH_AFTER_TOOL = patch(
    "app.adk.agents.agent_factory.builder.adk_after_tool_callback",
    _ADK_AFTER_TOOL,
)

# Patch build_toolset_for_doc so no ADK MCP packages are exercised.
_PATCH_BUILD_TOOLSET = patch(
    "app.adk.agents.agent_factory.hierarchy.build_toolset_for_doc",
)

# Patch get_default_registry so roster.py uses a zero-tool fake registry
# (each unknown server falls back to logical count 1, well inside the cap).
_PATCH_GET_DEFAULT_REGISTRY = patch(
    "app.adk.tools.registry.tool_registry.get_default_registry",
)


# ---------------------------------------------------------------------------
# In-memory Firestore stand-in (mirrors test_factory.py for consistency)
# ---------------------------------------------------------------------------


class _FakeFirestoreDb:
    def __init__(self, docs: dict) -> None:
        self._docs = docs

    def collection(self, col: str) -> _FakeCollection:
        return _FakeCollection(self._docs, (col,))


class _FakeCollection:
    def __init__(self, docs: dict, path: tuple) -> None:
        self._docs = docs
        self._path = path

    def document(self, doc_id: str) -> _FakeDocument:
        return _FakeDocument(self._docs, (*self._path, doc_id))

    def list_documents(self) -> list:
        prefix = self._path
        return [
            _FakeDocRef(p)
            for p, _ in self._docs.items()
            if p[: len(prefix)] == prefix and len(p) == len(prefix) + 1
        ]


class _FakeDocument:
    def __init__(self, docs: dict, path: tuple) -> None:
        self._docs = docs
        self._path = path

    def get(self) -> _FakeSnapshot:
        return _FakeSnapshot(self._docs.get(self._path))

    def collection(self, col: str) -> _FakeCollection:
        return _FakeCollection(self._docs, (*self._path, col))


class _FakeDocRef:
    def __init__(self, path: tuple) -> None:
        self.id = path[-1]


class _FakeSnapshot:
    def __init__(self, data: dict | None) -> None:
        self._data = data
        self.exists = data is not None

    def to_dict(self) -> dict:
        return self._data or {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ROOT_DOC = {
    "instruction": "You are the KEN-E root assistant.",
    "model": "gemini-2.0-flash",
    "description": "Root orchestrator",
}

_SPECIALIST_A_DOC = {
    "instruction": "You are specialist A.",
    "model": "gemini-2.0-flash",
    "description": "Specialist A handles analytics.",
    "mcp_servers": [],
}

_SPECIALIST_B_DOC = {
    "instruction": "You are specialist B.",
    "model": "gemini-2.0-flash",
    "description": "Specialist B handles ads.",
    "mcp_servers": [],
}

_ENABLED_SERVER_DOC = {
    "enabled": True,
    "auth_type": "ga_oauth",
    "connection": {
        "connection_type": "sse",
        "url": "https://ga-mcp.example.com/sse",
    },
}

_DISABLED_SERVER_DOC = {
    "enabled": False,
    "auth_type": "ga_oauth",
    "connection": {
        "connection_type": "sse",
        "url": "https://disabled-mcp.example.com/sse",
    },
}


class _FakeRegistry:
    """Zero-tool registry — every unknown server falls back to count 1."""

    def list_tools(self) -> list:
        return []


def _build_hierarchy_with_patches(fake_db: _FakeFirestoreDb) -> object:
    """Call build_hierarchy with the standard set of patches applied."""
    import app.adk.agents.agent_factory.hierarchy as h

    fake_registry = _FakeRegistry()

    with (
        _PATCH_BEFORE_AGENT,
        _PATCH_AFTER_AGENT,
        _PATCH_BEFORE_TOOL,
        _PATCH_AFTER_TOOL,
        _PATCH_BUILD_TOOLSET as mock_build_toolset,
        _PATCH_GET_DEFAULT_REGISTRY as mock_get_registry,
    ):
        mock_build_toolset.return_value = MagicMock(name="mock_toolset")
        mock_get_registry.return_value = fake_registry
        return h.build_hierarchy(db=fake_db)


def _make_context(state: dict) -> MagicMock:
    ctx = MagicMock()
    ctx.state = state
    return ctx


# ---------------------------------------------------------------------------
# AC-8a: Agent count from config
# ---------------------------------------------------------------------------


class TestAgentCountFromConfig:
    def test_root_plus_two_specialists_produces_two_dispatch_tools(self) -> None:
        from google.adk.agents import LlmAgent

        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "specialist_a"): _SPECIALIST_A_DOC,
            ("agent_configs", "specialist_b"): _SPECIALIST_B_DOC,
        }
        fake_db = _FakeFirestoreDb(docs)
        root = _build_hierarchy_with_patches(fake_db)

        assert isinstance(root, LlmAgent)
        # Root's tools list should contain two dispatch callables.
        assert len(root.tools) == 2

    def test_dispatch_tool_names_match_specialist_config_ids(self) -> None:
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "specialist_a"): _SPECIALIST_A_DOC,
            ("agent_configs", "specialist_b"): _SPECIALIST_B_DOC,
        }
        fake_db = _FakeFirestoreDb(docs)
        root = _build_hierarchy_with_patches(fake_db)

        tool_names = {getattr(t, "__name__", None) for t in root.tools}
        assert "dispatch_to_specialist_a" in tool_names
        assert "dispatch_to_specialist_b" in tool_names

    def test_available_specialists_block_mentions_both_specialist_names(self) -> None:
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "specialist_a"): _SPECIALIST_A_DOC,
            ("agent_configs", "specialist_b"): _SPECIALIST_B_DOC,
        }
        fake_db = _FakeFirestoreDb(docs)
        root = _build_hierarchy_with_patches(fake_db)

        rendered = root.instruction(_make_context({}))
        assert "specialist_a" in rendered
        assert "specialist_b" in rendered

    def test_no_specialists_produces_zero_dispatch_tools(self) -> None:
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
        }
        fake_db = _FakeFirestoreDb(docs)
        root = _build_hierarchy_with_patches(fake_db)

        assert root.tools == []


# ---------------------------------------------------------------------------
# AC-8b: MCP-server grouping
# ---------------------------------------------------------------------------


class TestMcpServerGrouping:
    def test_each_specialist_with_shared_server_gets_its_own_toolset_instance(
        self,
    ) -> None:
        """Two specialists referencing the same server_id get distinct toolset objects."""
        spec_a_doc = {
            "instruction": "You are specialist A.",
            "model": "gemini-2.0-flash",
            "description": "Specialist A",
            "mcp_servers": ["shared_server"],
        }
        spec_b_doc = {
            "instruction": "You are specialist B.",
            "model": "gemini-2.0-flash",
            "description": "Specialist B",
            "mcp_servers": ["shared_server"],
        }
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "specialist_a"): spec_a_doc,
            ("agent_configs", "specialist_b"): spec_b_doc,
            ("mcp_server_configs", "shared_server"): _ENABLED_SERVER_DOC,
        }
        fake_db = _FakeFirestoreDb(docs)

        import app.adk.agents.agent_factory.hierarchy as h

        fake_registry = _FakeRegistry()
        built_toolsets: list[MagicMock] = []

        def _side_effect(server_id: str, doc: dict) -> MagicMock:
            ts = MagicMock(name=f"toolset_for_{server_id}")
            built_toolsets.append(ts)
            return ts

        with (
            _PATCH_BEFORE_AGENT,
            _PATCH_AFTER_AGENT,
            _PATCH_BEFORE_TOOL,
            _PATCH_AFTER_TOOL,
            _PATCH_BUILD_TOOLSET as mock_build_toolset,
            _PATCH_GET_DEFAULT_REGISTRY as mock_get_registry,
        ):
            mock_build_toolset.side_effect = _side_effect
            mock_get_registry.return_value = fake_registry
            h.build_hierarchy(db=fake_db)

        # build_toolset_for_doc should have been called once per specialist x server.
        assert mock_build_toolset.call_count == 2
        # The two toolset instances must be distinct objects.
        assert built_toolsets[0] is not built_toolsets[1]

    def test_specialist_with_no_mcp_servers_has_empty_tools(self) -> None:
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "specialist_a"): _SPECIALIST_A_DOC,  # mcp_servers: []
        }
        fake_db = _FakeFirestoreDb(docs)
        root = _build_hierarchy_with_patches(fake_db)

        # The root should have 1 dispatch tool (for specialist_a).
        assert len(root.tools) == 1


# ---------------------------------------------------------------------------
# AC-8c: code_execution flag
# ---------------------------------------------------------------------------


class TestCodeExecutionFlag:
    def test_specialist_with_code_execution_true_has_built_in_code_executor(
        self,
    ) -> None:
        from google.adk.code_executors import BuiltInCodeExecutor

        spec_with_code_exec = {
            "instruction": "You are a code specialist.",
            "model": "gemini-2.0-flash",
            "description": "Code executor specialist.",
            "code_execution_enabled": True,
            "mcp_servers": [],
        }
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "code_specialist"): spec_with_code_exec,
        }
        fake_db = _FakeFirestoreDb(docs)

        import app.adk.agents.agent_factory.hierarchy as h

        fake_registry = _FakeRegistry()
        built_specialists: dict[str, object] = {}

        original_build_agent = None

        def _capture_build_agent(config, *, name: str, tools=None, **kwargs):
            agent = original_build_agent(config, name=name, tools=tools, **kwargs)
            built_specialists[name] = agent
            return agent

        import app.adk.agents.agent_factory.builder as b

        original_build_agent = b.build_agent

        with (
            _PATCH_BEFORE_AGENT,
            _PATCH_AFTER_AGENT,
            _PATCH_BEFORE_TOOL,
            _PATCH_AFTER_TOOL,
            _PATCH_BUILD_TOOLSET as mock_build_toolset,
            _PATCH_GET_DEFAULT_REGISTRY as mock_get_registry,
            patch("app.adk.agents.agent_factory.hierarchy.build_agent", side_effect=_capture_build_agent),
        ):
            mock_build_toolset.return_value = MagicMock(name="mock_toolset")
            mock_get_registry.return_value = fake_registry
            h.build_hierarchy(db=fake_db)

        spec = built_specialists.get("code_specialist")
        assert spec is not None
        assert isinstance(spec.code_executor, BuiltInCodeExecutor)

    def test_specialist_with_code_execution_false_has_no_code_executor(self) -> None:
        spec_no_code_exec = {
            "instruction": "You are a standard specialist.",
            "model": "gemini-2.0-flash",
            "description": "Standard specialist.",
            "code_execution_enabled": False,
            "mcp_servers": [],
        }
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "std_specialist"): spec_no_code_exec,
        }
        fake_db = _FakeFirestoreDb(docs)

        import app.adk.agents.agent_factory.hierarchy as h

        fake_registry = _FakeRegistry()
        built_specialists: dict[str, object] = {}

        original_build_agent = None

        def _capture_build_agent(config, *, name: str, tools=None, **kwargs):
            agent = original_build_agent(config, name=name, tools=tools, **kwargs)
            built_specialists[name] = agent
            return agent

        import app.adk.agents.agent_factory.builder as b

        original_build_agent = b.build_agent

        with (
            _PATCH_BEFORE_AGENT,
            _PATCH_AFTER_AGENT,
            _PATCH_BEFORE_TOOL,
            _PATCH_AFTER_TOOL,
            _PATCH_BUILD_TOOLSET as mock_build_toolset,
            _PATCH_GET_DEFAULT_REGISTRY as mock_get_registry,
            patch("app.adk.agents.agent_factory.hierarchy.build_agent", side_effect=_capture_build_agent),
        ):
            mock_build_toolset.return_value = MagicMock(name="mock_toolset")
            mock_get_registry.return_value = fake_registry
            h.build_hierarchy(db=fake_db)

        spec = built_specialists.get("std_specialist")
        assert spec is not None
        assert spec.code_executor is None


# ---------------------------------------------------------------------------
# AC-8d: Disabled-server exclusion
# ---------------------------------------------------------------------------


class TestDisabledServerExclusion:
    def test_disabled_server_is_excluded_from_specialist_tools(self) -> None:
        spec_doc = {
            "instruction": "You are a mixed specialist.",
            "model": "gemini-2.0-flash",
            "description": "Has enabled and disabled servers.",
            "mcp_servers": ["enabled_server", "disabled_server"],
        }
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "mixed_specialist"): spec_doc,
            ("mcp_server_configs", "enabled_server"): _ENABLED_SERVER_DOC,
            ("mcp_server_configs", "disabled_server"): _DISABLED_SERVER_DOC,
        }
        fake_db = _FakeFirestoreDb(docs)

        import app.adk.agents.agent_factory.hierarchy as h

        fake_registry = _FakeRegistry()
        call_log: list[str] = []

        def _side_effect(server_id: str, doc: dict) -> MagicMock:
            call_log.append(server_id)
            return MagicMock(name=f"toolset_{server_id}")

        with (
            _PATCH_BEFORE_AGENT,
            _PATCH_AFTER_AGENT,
            _PATCH_BEFORE_TOOL,
            _PATCH_AFTER_TOOL,
            _PATCH_BUILD_TOOLSET as mock_build_toolset,
            _PATCH_GET_DEFAULT_REGISTRY as mock_get_registry,
        ):
            mock_build_toolset.side_effect = _side_effect
            mock_get_registry.return_value = fake_registry
            h.build_hierarchy(db=fake_db)

        # Only the enabled server should have had a toolset built for it.
        assert "enabled_server" in call_log
        assert "disabled_server" not in call_log

    def test_enabled_server_is_included_in_specialist_tools(self) -> None:
        spec_doc = {
            "instruction": "You are an analytics specialist.",
            "model": "gemini-2.0-flash",
            "description": "Analytics only.",
            "mcp_servers": ["enabled_server"],
        }
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "analytics_specialist"): spec_doc,
            ("mcp_server_configs", "enabled_server"): _ENABLED_SERVER_DOC,
        }
        fake_db = _FakeFirestoreDb(docs)

        import app.adk.agents.agent_factory.hierarchy as h

        fake_registry = _FakeRegistry()
        call_log: list[str] = []

        def _side_effect(server_id: str, doc: dict) -> MagicMock:
            call_log.append(server_id)
            return MagicMock(name=f"toolset_{server_id}")

        with (
            _PATCH_BEFORE_AGENT,
            _PATCH_AFTER_AGENT,
            _PATCH_BEFORE_TOOL,
            _PATCH_AFTER_TOOL,
            _PATCH_BUILD_TOOLSET as mock_build_toolset,
            _PATCH_GET_DEFAULT_REGISTRY as mock_get_registry,
        ):
            mock_build_toolset.side_effect = _side_effect
            mock_get_registry.return_value = fake_registry
            h.build_hierarchy(db=fake_db)

        assert "enabled_server" in call_log

    def test_missing_server_doc_is_skipped_without_raising(self) -> None:
        spec_doc = {
            "instruction": "You are a specialist.",
            "model": "gemini-2.0-flash",
            "description": "References a non-existent server.",
            "mcp_servers": ["ghost_server"],
        }
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "ghost_specialist"): spec_doc,
            # ghost_server is deliberately absent from mcp_server_configs
        }
        fake_db = _FakeFirestoreDb(docs)
        # Should not raise — missing server is logged as warning and skipped.
        root = _build_hierarchy_with_patches(fake_db)

        from google.adk.agents import LlmAgent

        assert isinstance(root, LlmAgent)


# ---------------------------------------------------------------------------
# AC-8e: auth_type validation
# ---------------------------------------------------------------------------


class TestAuthTypeValidation:
    def test_unknown_auth_type_raises_value_error(self) -> None:
        unknown_server_doc = {
            "enabled": True,
            "auth_type": "unknown_oauth",
            "connection": {
                "connection_type": "sse",
                "url": "https://unknown.example.com/sse",
            },
        }
        spec_doc = {
            "instruction": "You are a bad specialist.",
            "model": "gemini-2.0-flash",
            "description": "References a bad server.",
            "mcp_servers": ["bad_server"],
        }
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "bad_specialist"): spec_doc,
            ("mcp_server_configs", "bad_server"): unknown_server_doc,
        }
        fake_db = _FakeFirestoreDb(docs)

        import app.adk.agents.agent_factory.hierarchy as h

        fake_registry = _FakeRegistry()

        # Simulate build_toolset_for_doc raising ValueError for unknown auth_type.
        def _raise_for_unknown(server_id: str, doc: dict) -> object:
            if doc.get("auth_type") == "unknown_oauth":
                raise ValueError(
                    f"Unknown auth_type in MCP server config for {server_id}"
                )
            return MagicMock(name=f"toolset_{server_id}")

        with (
            _PATCH_BEFORE_AGENT,
            _PATCH_AFTER_AGENT,
            _PATCH_BEFORE_TOOL,
            _PATCH_AFTER_TOOL,
            _PATCH_BUILD_TOOLSET as mock_build_toolset,
            _PATCH_GET_DEFAULT_REGISTRY as mock_get_registry,
        ):
            mock_build_toolset.side_effect = _raise_for_unknown
            mock_get_registry.return_value = fake_registry

            with pytest.raises(ValueError):
                h.build_hierarchy(db=fake_db)

    def test_known_auth_type_does_not_raise(self) -> None:
        """Verifies the happy path — a known auth_type builds without error."""
        known_server_doc = {
            "enabled": True,
            "auth_type": "ga_oauth",
            "connection": {
                "connection_type": "sse",
                "url": "https://ga.example.com/sse",
            },
        }
        spec_doc = {
            "instruction": "You are a GA specialist.",
            "model": "gemini-2.0-flash",
            "description": "Handles GA analytics.",
            "mcp_servers": ["ga_server"],
        }
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "ga_specialist"): spec_doc,
            ("mcp_server_configs", "ga_server"): known_server_doc,
        }
        fake_db = _FakeFirestoreDb(docs)

        from google.adk.agents import LlmAgent

        root = _build_hierarchy_with_patches(fake_db)
        assert isinstance(root, LlmAgent)


# ---------------------------------------------------------------------------
# AC-8f: Callback wiring
# ---------------------------------------------------------------------------


class TestCallbackWiring:
    def test_root_agent_before_agent_callback_starts_with_weave_sentinel(
        self,
    ) -> None:
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "specialist_a"): _SPECIALIST_A_DOC,
        }
        fake_db = _FakeFirestoreDb(docs)
        root = _build_hierarchy_with_patches(fake_db)

        assert root.before_agent_callback[0] is _WEAVE_BEFORE

    def test_root_agent_after_agent_callback_starts_with_weave_sentinel(
        self,
    ) -> None:
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
        }
        fake_db = _FakeFirestoreDb(docs)
        root = _build_hierarchy_with_patches(fake_db)

        assert root.after_agent_callback[0] is _WEAVE_AFTER

    def test_root_agent_before_tool_callback_starts_with_adk_sentinel(
        self,
    ) -> None:
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
        }
        fake_db = _FakeFirestoreDb(docs)
        root = _build_hierarchy_with_patches(fake_db)

        assert root.before_tool_callback[0] is _ADK_BEFORE_TOOL

    def test_root_agent_after_tool_callback_starts_with_adk_sentinel(self) -> None:
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
        }
        fake_db = _FakeFirestoreDb(docs)
        root = _build_hierarchy_with_patches(fake_db)

        assert root.after_tool_callback[0] is _ADK_AFTER_TOOL

    def test_specialist_agents_have_standard_callbacks_wired(self) -> None:
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "specialist_a"): _SPECIALIST_A_DOC,
        }
        fake_db = _FakeFirestoreDb(docs)

        import app.adk.agents.agent_factory.hierarchy as h

        fake_registry = _FakeRegistry()
        built_agents: list[object] = []

        original_build_agent = None

        def _capture_build_agent(config, *, name: str, tools=None, **kwargs):
            agent = original_build_agent(config, name=name, tools=tools, **kwargs)
            built_agents.append(agent)
            return agent

        import app.adk.agents.agent_factory.builder as b

        original_build_agent = b.build_agent

        with (
            _PATCH_BEFORE_AGENT,
            _PATCH_AFTER_AGENT,
            _PATCH_BEFORE_TOOL,
            _PATCH_AFTER_TOOL,
            _PATCH_BUILD_TOOLSET as mock_build_toolset,
            _PATCH_GET_DEFAULT_REGISTRY as mock_get_registry,
            patch(
                "app.adk.agents.agent_factory.hierarchy.build_agent",
                side_effect=_capture_build_agent,
            ),
        ):
            mock_build_toolset.return_value = MagicMock(name="mock_toolset")
            mock_get_registry.return_value = fake_registry
            h.build_hierarchy(db=fake_db)

        # All agents (specialist + root) should have standard callbacks.
        assert len(built_agents) >= 2
        for agent in built_agents:
            assert agent.before_agent_callback[0] is _WEAVE_BEFORE
            assert agent.after_agent_callback[0] is _WEAVE_AFTER
            assert agent.before_tool_callback[0] is _ADK_BEFORE_TOOL
            assert agent.after_tool_callback[0] is _ADK_AFTER_TOOL


# ---------------------------------------------------------------------------
# AC-8g: Dispatch-function count
# ---------------------------------------------------------------------------


class TestDispatchFunctionCount:
    def test_dispatch_function_count_equals_specialist_count(self) -> None:
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "specialist_a"): _SPECIALIST_A_DOC,
            ("agent_configs", "specialist_b"): _SPECIALIST_B_DOC,
        }
        fake_db = _FakeFirestoreDb(docs)
        root = _build_hierarchy_with_patches(fake_db)

        assert len(root.tools) == 2

    def test_each_dispatch_function_has_correct_name_prefix(self) -> None:
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "specialist_a"): _SPECIALIST_A_DOC,
        }
        fake_db = _FakeFirestoreDb(docs)
        root = _build_hierarchy_with_patches(fake_db)

        tool_names = [getattr(t, "__name__", "") for t in root.tools]
        assert all(name.startswith("dispatch_to_") for name in tool_names)

    def test_dispatch_function_for_known_specialist_name(self) -> None:
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "analytics_agent"): {
                "instruction": "You handle analytics.",
                "model": "gemini-2.0-flash",
                "description": "Analytics specialist.",
                "mcp_servers": [],
            },
        }
        fake_db = _FakeFirestoreDb(docs)
        root = _build_hierarchy_with_patches(fake_db)

        tool_names = {getattr(t, "__name__", "") for t in root.tools}
        assert "dispatch_to_analytics_agent" in tool_names

    def test_no_specialists_produces_empty_dispatch_tools(self) -> None:
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
        }
        fake_db = _FakeFirestoreDb(docs)
        root = _build_hierarchy_with_patches(fake_db)

        assert root.tools == []


# ---------------------------------------------------------------------------
# AC-8h: Root-instruction Available Specialists content
# ---------------------------------------------------------------------------


class TestRootInstructionAvailableSpecialists:
    def test_rendered_root_instruction_contains_available_specialists_heading(
        self,
    ) -> None:
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "specialist_a"): _SPECIALIST_A_DOC,
        }
        fake_db = _FakeFirestoreDb(docs)
        root = _build_hierarchy_with_patches(fake_db)

        rendered = root.instruction(_make_context({}))
        assert "## Available Specialists" in rendered

    def test_rendered_root_instruction_contains_both_specialist_names(self) -> None:
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "specialist_a"): _SPECIALIST_A_DOC,
            ("agent_configs", "specialist_b"): _SPECIALIST_B_DOC,
        }
        fake_db = _FakeFirestoreDb(docs)
        root = _build_hierarchy_with_patches(fake_db)

        rendered = root.instruction(_make_context({}))
        assert "specialist_a" in rendered
        assert "specialist_b" in rendered

    def test_rendered_root_instruction_starts_with_root_config_instruction(
        self,
    ) -> None:
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "specialist_a"): _SPECIALIST_A_DOC,
        }
        fake_db = _FakeFirestoreDb(docs)
        root = _build_hierarchy_with_patches(fake_db)

        rendered = root.instruction(_make_context({}))
        assert rendered.startswith(_ROOT_DOC["instruction"])

    def test_rendered_root_instruction_with_no_specialists_still_has_heading(
        self,
    ) -> None:
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
        }
        fake_db = _FakeFirestoreDb(docs)
        root = _build_hierarchy_with_patches(fake_db)

        rendered = root.instruction(_make_context({}))
        assert "## Available Specialists" in rendered

    def test_root_agent_name_is_ken_e(self) -> None:
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
        }
        fake_db = _FakeFirestoreDb(docs)
        root = _build_hierarchy_with_patches(fake_db)

        assert root.name == "ken_e"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestErrorCases:
    def test_missing_root_config_raises_config_not_found_error(self) -> None:
        docs = {
            ("agent_configs", "specialist_a"): _SPECIALIST_A_DOC,
        }
        fake_db = _FakeFirestoreDb(docs)

        with pytest.raises(ConfigNotFoundError):
            _build_hierarchy_with_patches(fake_db)

    def test_empty_firestore_raises_config_not_found_error(self) -> None:
        fake_db = _FakeFirestoreDb({})

        with pytest.raises(ConfigNotFoundError):
            _build_hierarchy_with_patches(fake_db)

    def test_firestore_client_creation_failure_raises_firestore_connection_error(
        self,
    ) -> None:
        import app.adk.agents.agent_factory.hierarchy as h
        from app.adk.agents.agent_factory.config_loader import FirestoreConnectionError

        with (
            _PATCH_BEFORE_AGENT,
            _PATCH_AFTER_AGENT,
            _PATCH_BEFORE_TOOL,
            _PATCH_AFTER_TOOL,
            patch(
                "app.adk.agents.agent_factory.hierarchy._build_firestore_client",
                side_effect=RuntimeError("connection refused"),
            ),
        ):
            with pytest.raises(FirestoreConnectionError):
                h.build_hierarchy()

    def test_config_validation_error_is_skipped_not_fatal(self) -> None:
        """A specialist with an invalid Firestore document is skipped; root still builds."""
        import app.adk.agents.agent_factory.hierarchy as h
        from app.adk.agents.agent_factory.config_loader import MergedAgentConfig

        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "bad_specialist"): _SPECIALIST_A_DOC,
        }
        fake_db = _FakeFirestoreDb(docs)
        fake_registry = _FakeRegistry()

        root_config = MergedAgentConfig(**_ROOT_DOC)

        def _load_side_effect(db: object, config_id: str, account_id: object) -> MergedAgentConfig:
            if config_id == "bad_specialist":
                raise ConfigValidationError("bad doc")
            return root_config

        with (
            _PATCH_BEFORE_AGENT,
            _PATCH_AFTER_AGENT,
            _PATCH_BEFORE_TOOL,
            _PATCH_AFTER_TOOL,
            _PATCH_BUILD_TOOLSET as mock_build_toolset,
            _PATCH_GET_DEFAULT_REGISTRY as mock_get_registry,
            patch(
                "app.adk.agents.agent_factory.hierarchy._load_and_merge",
                side_effect=_load_side_effect,
            ),
        ):
            mock_build_toolset.return_value = MagicMock(name="mock_toolset")
            mock_get_registry.return_value = fake_registry
            root = h.build_hierarchy(db=fake_db)

        # bad_specialist was skipped; root was built with zero specialists.
        assert root.name == "ken_e"
        assert len(root.tools) == 0

    def test_mcp_schema_error_propagates_at_deploy_time(self) -> None:
        """MCPSchemaError from a malformed server doc fails the build (fail-fast)."""
        import app.adk.agents.agent_factory.hierarchy as h

        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "specialist_a"): {
                **_SPECIALIST_A_DOC,
                "mcp_servers": ["bad_server"],
            },
            ("mcp_server_configs", "bad_server"): {
                "enabled": True,
                "auth_type": "ga_oauth",
                # missing `connection` field → MCPSchemaError
            },
        }
        fake_db = _FakeFirestoreDb(docs)
        fake_registry = _FakeRegistry()

        with (
            _PATCH_BEFORE_AGENT,
            _PATCH_AFTER_AGENT,
            _PATCH_BEFORE_TOOL,
            _PATCH_AFTER_TOOL,
            patch(
                "app.adk.agents.agent_factory.hierarchy.build_toolset_for_doc",
                side_effect=MCPSchemaError("missing connection field"),
            ),
            _PATCH_GET_DEFAULT_REGISTRY as mock_get_registry,
        ):
            mock_get_registry.return_value = fake_registry
            with pytest.raises(MCPSchemaError):
                h.build_hierarchy(db=fake_db)

    def test_invalid_account_id_raises_value_error(self) -> None:
        """account_id containing path-separator characters raises ValueError."""
        import app.adk.agents.agent_factory.hierarchy as h

        with pytest.raises(ValueError, match="invalid characters"):
            h.build_hierarchy(account_id="../../admin", db=_FakeFirestoreDb({}))


# ---------------------------------------------------------------------------
# Private helper unit tests
# ---------------------------------------------------------------------------


class TestPrivateHelpers:
    def test_resolve_project_id_returns_argument_when_provided(self) -> None:
        from app.adk.agents.agent_factory.hierarchy import _resolve_project_id

        assert _resolve_project_id("my-project") == "my-project"

    def test_resolve_project_id_falls_back_to_env_var(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.adk.agents.agent_factory.hierarchy import _resolve_project_id

        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT_ID", "env-project")
        assert _resolve_project_id(None) == "env-project"

    def test_resolve_project_id_defaults_to_ken_e_dev(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.adk.agents.agent_factory.hierarchy import _resolve_project_id

        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT_ID", raising=False)
        assert _resolve_project_id(None) == "ken-e-dev"

    def test_list_config_ids_global_only_when_no_account(self) -> None:
        from app.adk.agents.agent_factory.hierarchy import _list_config_ids

        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "specialist_a"): _SPECIALIST_A_DOC,
        }
        fake_db = _FakeFirestoreDb(docs)
        ids = _list_config_ids(fake_db, account_id=None)

        assert ids == sorted(["ken_e_chatbot", "specialist_a"])

    def test_list_config_ids_merges_account_ids_when_account_provided(self) -> None:
        from app.adk.agents.agent_factory.hierarchy import _list_config_ids

        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "specialist_a"): _SPECIALIST_A_DOC,
            ("accounts", "acc_123", "agent_configs", "custom_specialist"): {
                "instruction": "Custom.",
                "model": "gemini-2.0-flash",
            },
        }
        fake_db = _FakeFirestoreDb(docs)
        ids = _list_config_ids(fake_db, account_id="acc_123")

        assert "ken_e_chatbot" in ids
        assert "specialist_a" in ids
        assert "custom_specialist" in ids
        assert ids == sorted(ids)  # must be sorted

    def test_list_config_ids_deduplicates_ids(self) -> None:
        from app.adk.agents.agent_factory.hierarchy import _list_config_ids

        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "specialist_a"): _SPECIALIST_A_DOC,
            # specialist_a also exists in account scope (overlay scenario)
            ("accounts", "acc_xyz", "agent_configs", "specialist_a"): {
                "instruction": "Override.",
                "model": "gemini-2.0-flash",
                "based_on_version": 1,
            },
        }
        fake_db = _FakeFirestoreDb(docs)
        ids = _list_config_ids(fake_db, account_id="acc_xyz")

        # specialist_a must appear exactly once even though it's in both collections.
        assert ids.count("specialist_a") == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
