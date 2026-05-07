"""Integration tests for app.adk.agents.agent_factory.hierarchy.build_hierarchy().

Exercises the full build_hierarchy() pipeline against an in-memory
_FakeFirestoreDb (no live GCP). Seeds 1 root config, 2 specialist configs,
and 3 MCP server configs including one shared between both specialists.

Test classes:
  TC-1  TestRootStructure             — root is an LlmAgent named "ken_e" with 2 dispatchers
  TC-2  TestSpecialistToolAssignments — each specialist gets its own correct toolsets
  TC-3  TestSharedServerDistinctInstances — shared server yields distinct toolset objects
  TC-4  TestRootInstructionContent    — rendered instruction contains expected strings
  TC-5  TestOverlayVariant            — account overlay overrides specialist instruction
  TC-6  TestStructuralEquivalenceSmoke — 2 specialists → 2 dispatch tools on root
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Sentinel callback objects — same pattern as test_hierarchy.py
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

_PATCH_BUILD_TOOLSET = patch(
    "app.adk.agents.agent_factory.hierarchy.build_toolset_for_doc",
)

_PATCH_GET_DEFAULT_REGISTRY = patch(
    "app.adk.tools.registry.tool_registry.get_default_registry",
)


# ---------------------------------------------------------------------------
# In-memory Firestore stand-in (copied from test_hierarchy.py)
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
# Canonical fake DB documents for the e2e fixture
# ---------------------------------------------------------------------------

_E2E_DOCS: dict = {
    ("agent_configs", "ken_e_chatbot"): {
        "instruction": "You are KEN-E root.",
        "model": "gemini-2.0-flash",
        "description": "Root orchestration agent",
    },
    ("agent_configs", "analytics_specialist"): {
        "instruction": "You are an analytics specialist.",
        "model": "gemini-2.0-flash",
        "description": "Handles Google Analytics queries",
        "mcp_servers": ["ga_mcp", "shared_viz_mcp"],
    },
    ("agent_configs", "ads_specialist"): {
        "instruction": "You are an ads specialist.",
        "model": "gemini-2.0-flash",
        "description": "Handles Google Ads queries",
        "mcp_servers": ["ads_mcp", "shared_viz_mcp"],
    },
    ("mcp_server_configs", "ga_mcp"): {
        "enabled": True,
        "connection": {"connection_type": "sse", "url": "https://ga.mcp.example.com"},
        "auth_type": "ga_oauth",
    },
    ("mcp_server_configs", "ads_mcp"): {
        "enabled": True,
        "connection": {"connection_type": "sse", "url": "https://ads.mcp.example.com"},
        "auth_type": "google_ads_oauth",
    },
    ("mcp_server_configs", "shared_viz_mcp"): {
        "enabled": True,
        "connection": {"connection_type": "sse", "url": "https://viz.mcp.example.com"},
        # no auth_type — shared server with no header_provider
    },
}


class _FakeRegistry:
    """Zero-tool registry — every unknown server falls back to count 1."""

    def list_tools(self) -> list:
        return []


def _run_build_hierarchy(docs: dict, account_id: str | None = None) -> object:
    """Call build_hierarchy with the standard set of patches applied.

    Uses side_effect=lambda sid, doc: MagicMock(name=f"toolset_{sid}") so each
    call produces a distinct MagicMock instance (critical for TC-3).
    """
    import app.adk.agents.agent_factory.hierarchy as h

    fake_db = _FakeFirestoreDb(docs)
    fake_registry = _FakeRegistry()

    with (
        _PATCH_BEFORE_AGENT,
        _PATCH_AFTER_AGENT,
        _PATCH_BEFORE_TOOL,
        _PATCH_AFTER_TOOL,
        _PATCH_BUILD_TOOLSET as mock_build_toolset,
        _PATCH_GET_DEFAULT_REGISTRY as mock_get_registry,
    ):
        mock_build_toolset.side_effect = lambda sid, doc: MagicMock(
            name=f"toolset_{sid}"
        )
        mock_get_registry.return_value = fake_registry
        return h.build_hierarchy(account_id=account_id, db=fake_db)


def _make_context(state: dict) -> MagicMock:
    ctx = MagicMock()
    ctx.state = state
    return ctx


# ---------------------------------------------------------------------------
# TC-1: Root structure
# ---------------------------------------------------------------------------


class TestRootStructure:
    """TC-1: build_hierarchy() returns an LlmAgent named 'ken_e' with 2 dispatch tools."""

    def test_root_is_llm_agent(self) -> None:
        from google.adk.agents import LlmAgent

        root = _run_build_hierarchy(_E2E_DOCS)
        assert isinstance(root, LlmAgent)

    def test_root_name_is_ken_e(self) -> None:
        root = _run_build_hierarchy(_E2E_DOCS)
        assert root.name == "ken_e"

    def test_root_tools_has_exactly_two_items(self) -> None:
        root = _run_build_hierarchy(_E2E_DOCS)
        assert len(root.tools) == 2

    def test_dispatch_function_names_match_specialist_ids(self) -> None:
        root = _run_build_hierarchy(_E2E_DOCS)
        tool_names = {getattr(t, "__name__", None) for t in root.tools}
        assert "dispatch_to_analytics_specialist" in tool_names
        assert "dispatch_to_ads_specialist" in tool_names


# ---------------------------------------------------------------------------
# TC-2: Specialist tool assignments
# ---------------------------------------------------------------------------


class TestSpecialistToolAssignments:
    """TC-2: Each specialist is built with the correct number of toolsets."""

    def test_analytics_specialist_built_with_two_toolsets(self) -> None:
        import app.adk.agents.agent_factory.hierarchy as h

        fake_db = _FakeFirestoreDb(_E2E_DOCS)
        fake_registry = _FakeRegistry()

        # Capture the tools= argument passed to build_agent for each specialist.
        specialist_tools: dict[str, list] = {}
        import app.adk.agents.agent_factory.builder as b

        original_build_agent = b.build_agent

        def _capture_build_agent(config, *, name: str, tools=None, **kwargs):
            agent = original_build_agent(config, name=name, tools=tools, **kwargs)
            if name != "ken_e":
                specialist_tools[name] = list(tools or [])
            return agent

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
            mock_build_toolset.side_effect = lambda sid, doc: MagicMock(
                name=f"toolset_{sid}"
            )
            mock_get_registry.return_value = fake_registry
            h.build_hierarchy(db=fake_db)

        assert "analytics_specialist" in specialist_tools
        assert len(specialist_tools["analytics_specialist"]) == 2

    def test_ads_specialist_built_with_two_toolsets(self) -> None:
        import app.adk.agents.agent_factory.hierarchy as h

        fake_db = _FakeFirestoreDb(_E2E_DOCS)
        fake_registry = _FakeRegistry()

        specialist_tools: dict[str, list] = {}
        import app.adk.agents.agent_factory.builder as b

        original_build_agent = b.build_agent

        def _capture_build_agent(config, *, name: str, tools=None, **kwargs):
            agent = original_build_agent(config, name=name, tools=tools, **kwargs)
            if name != "ken_e":
                specialist_tools[name] = list(tools or [])
            return agent

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
            mock_build_toolset.side_effect = lambda sid, doc: MagicMock(
                name=f"toolset_{sid}"
            )
            mock_get_registry.return_value = fake_registry
            h.build_hierarchy(db=fake_db)

        assert "ads_specialist" in specialist_tools
        assert len(specialist_tools["ads_specialist"]) == 2

    def test_build_toolset_called_once_per_specialist_per_server(self) -> None:
        """build_toolset_for_doc is called exactly 4 times (2 servers x 2 specialists)."""
        import app.adk.agents.agent_factory.hierarchy as h

        fake_db = _FakeFirestoreDb(_E2E_DOCS)
        fake_registry = _FakeRegistry()

        with (
            _PATCH_BEFORE_AGENT,
            _PATCH_AFTER_AGENT,
            _PATCH_BEFORE_TOOL,
            _PATCH_AFTER_TOOL,
            _PATCH_BUILD_TOOLSET as mock_build_toolset,
            _PATCH_GET_DEFAULT_REGISTRY as mock_get_registry,
        ):
            mock_build_toolset.side_effect = lambda sid, doc: MagicMock(
                name=f"toolset_{sid}"
            )
            mock_get_registry.return_value = fake_registry
            h.build_hierarchy(db=fake_db)

        # analytics_specialist: ga_mcp + shared_viz_mcp → 2 calls
        # ads_specialist:       ads_mcp + shared_viz_mcp → 2 calls
        # total = 4
        assert mock_build_toolset.call_count == 4

    def test_ga_mcp_toolset_assigned_only_to_analytics_specialist(self) -> None:
        """ga_mcp toolset goes to analytics_specialist, not ads_specialist."""
        import app.adk.agents.agent_factory.hierarchy as h

        fake_db = _FakeFirestoreDb(_E2E_DOCS)
        fake_registry = _FakeRegistry()

        # We infer specialist context from call ordering:
        # analytics_specialist is built before ads_specialist (alphabetical order).

        build_toolset_calls: list[str] = []

        def _side_effect(sid: str, doc: dict) -> MagicMock:
            build_toolset_calls.append(sid)
            return MagicMock(name=f"toolset_{sid}")

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

        # Sorted alphabetically: analytics_specialist before ads_specialist.
        # analytics_specialist's servers are declared as ["ga_mcp", "shared_viz_mcp"].
        # ads_specialist's servers are declared as ["ads_mcp", "shared_viz_mcp"].
        # Actual order depends on iteration over mcp_servers list in each config.
        assert "ga_mcp" in build_toolset_calls
        assert "ads_mcp" in build_toolset_calls
        assert "shared_viz_mcp" in build_toolset_calls
        # ga_mcp should appear exactly once (only analytics_specialist references it)
        assert build_toolset_calls.count("ga_mcp") == 1
        # ads_mcp should appear exactly once (only ads_specialist references it)
        assert build_toolset_calls.count("ads_mcp") == 1
        # shared_viz_mcp appears twice (one per specialist)
        assert build_toolset_calls.count("shared_viz_mcp") == 2


# ---------------------------------------------------------------------------
# TC-3: Shared server produces distinct toolset instances
# ---------------------------------------------------------------------------


class TestSharedServerDistinctInstances:
    """TC-3: The two shared_viz_mcp toolsets are distinct Python objects."""

    def test_shared_viz_mcp_toolsets_are_not_same_object(self) -> None:
        import app.adk.agents.agent_factory.hierarchy as h

        fake_db = _FakeFirestoreDb(_E2E_DOCS)
        fake_registry = _FakeRegistry()

        viz_toolsets: list[MagicMock] = []

        def _side_effect(sid: str, doc: dict) -> MagicMock:
            ts = MagicMock(name=f"toolset_{sid}")
            if sid == "shared_viz_mcp":
                viz_toolsets.append(ts)
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

        assert len(viz_toolsets) == 2, (
            "shared_viz_mcp toolset should be built exactly twice (once per specialist)"
        )
        assert viz_toolsets[0] is not viz_toolsets[1], (
            "Each specialist must receive its own independent shared_viz_mcp toolset instance"
        )

    def test_each_specialist_toolset_is_independent_mock(self) -> None:
        """All four toolset instances produced are distinct objects."""
        import app.adk.agents.agent_factory.hierarchy as h

        fake_db = _FakeFirestoreDb(_E2E_DOCS)
        fake_registry = _FakeRegistry()

        all_toolsets: list[MagicMock] = []

        def _side_effect(sid: str, doc: dict) -> MagicMock:
            ts = MagicMock(name=f"toolset_{sid}")
            all_toolsets.append(ts)
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

        assert len(all_toolsets) == 4
        # All four objects must be distinct — no aliasing across specialists.
        ids = [id(ts) for ts in all_toolsets]
        assert len(set(ids)) == 4, "All four toolset instances must be distinct objects"


# ---------------------------------------------------------------------------
# TC-4: Root instruction contains Available Specialists
# ---------------------------------------------------------------------------


class TestRootInstructionContent:
    """TC-4: Rendered root instruction has required structural content."""

    def test_rendered_instruction_contains_available_specialists_heading(self) -> None:
        root = _run_build_hierarchy(_E2E_DOCS)
        rendered = root.instruction(_make_context({}))
        assert "## Available Specialists" in rendered

    def test_rendered_instruction_contains_analytics_specialist(self) -> None:
        root = _run_build_hierarchy(_E2E_DOCS)
        rendered = root.instruction(_make_context({}))
        assert "analytics_specialist" in rendered

    def test_rendered_instruction_contains_ads_specialist(self) -> None:
        root = _run_build_hierarchy(_E2E_DOCS)
        rendered = root.instruction(_make_context({}))
        assert "ads_specialist" in rendered

    def test_rendered_instruction_starts_with_base_instruction(self) -> None:
        root = _run_build_hierarchy(_E2E_DOCS)
        rendered = root.instruction(_make_context({}))
        # When state is empty (no organization_context), the instruction provider
        # returns the raw combined_instruction without the org context wrapper.
        assert rendered.startswith("You are KEN-E root.")

    def test_rendered_instruction_with_org_context_state(self) -> None:
        """When state contains organization_context, the provider prepends it."""
        root = _run_build_hierarchy(_E2E_DOCS)
        rendered = root.instruction(_make_context({"organization_context": "OrgXYZ"}))
        assert "[ORGANIZATION CONTEXT]" in rendered
        assert "OrgXYZ" in rendered
        assert "You are KEN-E root." in rendered


# ---------------------------------------------------------------------------
# TC-5: Overlay variant
# ---------------------------------------------------------------------------


class TestOverlayVariant:
    """TC-5: account_id overlay overrides the analytics_specialist instruction."""

    def test_account_overlay_instruction_is_used(self) -> None:
        import app.adk.agents.agent_factory.hierarchy as h

        docs_with_overlay = dict(_E2E_DOCS)
        docs_with_overlay[
            ("accounts", "acc_xyz", "agent_configs", "analytics_specialist")
        ] = {
            "instruction": "You are CUSTOM analytics.",
            "model": "gemini-2.0-flash",
        }

        fake_db = _FakeFirestoreDb(docs_with_overlay)
        fake_registry = _FakeRegistry()

        specialist_instructions: dict[str, str] = {}
        import app.adk.agents.agent_factory.builder as b

        original_build_agent = b.build_agent

        def _capture_build_agent(config, *, name: str, tools=None, **kwargs):
            agent = original_build_agent(config, name=name, tools=tools, **kwargs)
            if name != "ken_e":
                # Render the instruction with empty state to inspect the base text.
                ctx = MagicMock()
                ctx.state = {}
                specialist_instructions[name] = agent.instruction(ctx)
            return agent

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
            mock_build_toolset.side_effect = lambda sid, doc: MagicMock(
                name=f"toolset_{sid}"
            )
            mock_get_registry.return_value = fake_registry
            h.build_hierarchy(account_id="acc_xyz", db=fake_db)

        assert "analytics_specialist" in specialist_instructions
        assert "You are CUSTOM analytics." in specialist_instructions["analytics_specialist"]

    def test_account_overlay_does_not_affect_ads_specialist(self) -> None:
        """The ads_specialist keeps its original instruction when only analytics is overridden."""
        import app.adk.agents.agent_factory.hierarchy as h

        docs_with_overlay = dict(_E2E_DOCS)
        docs_with_overlay[
            ("accounts", "acc_xyz", "agent_configs", "analytics_specialist")
        ] = {
            "instruction": "You are CUSTOM analytics.",
            "model": "gemini-2.0-flash",
        }

        fake_db = _FakeFirestoreDb(docs_with_overlay)
        fake_registry = _FakeRegistry()

        specialist_instructions: dict[str, str] = {}
        import app.adk.agents.agent_factory.builder as b

        original_build_agent = b.build_agent

        def _capture_build_agent(config, *, name: str, tools=None, **kwargs):
            agent = original_build_agent(config, name=name, tools=tools, **kwargs)
            if name != "ken_e":
                ctx = MagicMock()
                ctx.state = {}
                specialist_instructions[name] = agent.instruction(ctx)
            return agent

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
            mock_build_toolset.side_effect = lambda sid, doc: MagicMock(
                name=f"toolset_{sid}"
            )
            mock_get_registry.return_value = fake_registry
            h.build_hierarchy(account_id="acc_xyz", db=fake_db)

        assert "ads_specialist" in specialist_instructions
        assert "You are an ads specialist." in specialist_instructions["ads_specialist"]

    def test_overlay_root_still_has_two_dispatch_tools(self) -> None:
        """With account overlay, root still has 2 dispatch tools."""
        docs_with_overlay = dict(_E2E_DOCS)
        docs_with_overlay[
            ("accounts", "acc_xyz", "agent_configs", "analytics_specialist")
        ] = {
            "instruction": "You are CUSTOM analytics.",
            "model": "gemini-2.0-flash",
        }

        root = _run_build_hierarchy(docs_with_overlay, account_id="acc_xyz")
        assert len(root.tools) == 2


# ---------------------------------------------------------------------------
# TC-6: Structural-equivalence smoke test (legacy 2-specialist path)
# ---------------------------------------------------------------------------


class TestStructuralEquivalenceSmoke:
    """TC-6: Exactly 2 specialists → exactly 2 dispatch tools on root (legacy equivalence)."""

    def test_two_specialists_produce_two_dispatch_tools(self) -> None:
        """Mirrors the legacy hardcoded path that had search_company_news + query_google_analytics."""
        docs = {
            ("agent_configs", "ken_e_chatbot"): {
                "instruction": "You are the KEN-E root assistant.",
                "model": "gemini-2.0-flash",
                "description": "Root orchestrator",
            },
            ("agent_configs", "search_company_news"): {
                "instruction": "You search company news.",
                "model": "gemini-2.0-flash",
                "description": "Company news specialist.",
                "mcp_servers": [],
            },
            ("agent_configs", "query_google_analytics"): {
                "instruction": "You query Google Analytics.",
                "model": "gemini-2.0-flash",
                "description": "Google Analytics specialist.",
                "mcp_servers": [],
            },
        }
        root = _run_build_hierarchy(docs)

        assert len(root.tools) == 2

    def test_dispatch_tool_names_for_legacy_specialists(self) -> None:
        docs = {
            ("agent_configs", "ken_e_chatbot"): {
                "instruction": "You are the KEN-E root assistant.",
                "model": "gemini-2.0-flash",
                "description": "Root orchestrator",
            },
            ("agent_configs", "search_company_news"): {
                "instruction": "You search company news.",
                "model": "gemini-2.0-flash",
                "description": "Company news specialist.",
                "mcp_servers": [],
            },
            ("agent_configs", "query_google_analytics"): {
                "instruction": "You query Google Analytics.",
                "model": "gemini-2.0-flash",
                "description": "Google Analytics specialist.",
                "mcp_servers": [],
            },
        }
        root = _run_build_hierarchy(docs)

        tool_names = {getattr(t, "__name__", None) for t in root.tools}
        assert "dispatch_to_search_company_news" in tool_names
        assert "dispatch_to_query_google_analytics" in tool_names

    def test_root_is_structurally_equivalent_llm_agent(self) -> None:
        """Root is an LlmAgent named 'ken_e' — same structural identity as legacy path."""
        from google.adk.agents import LlmAgent

        docs = {
            ("agent_configs", "ken_e_chatbot"): {
                "instruction": "You are the KEN-E root assistant.",
                "model": "gemini-2.0-flash",
                "description": "Root orchestrator",
            },
            ("agent_configs", "search_company_news"): {
                "instruction": "You search company news.",
                "model": "gemini-2.0-flash",
                "description": "Company news specialist.",
                "mcp_servers": [],
            },
            ("agent_configs", "query_google_analytics"): {
                "instruction": "You query Google Analytics.",
                "model": "gemini-2.0-flash",
                "description": "Google Analytics specialist.",
                "mcp_servers": [],
            },
        }
        root = _run_build_hierarchy(docs)

        assert isinstance(root, LlmAgent)
        assert root.name == "ken_e"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
