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
        # AH-40: flat generation fields — exercised by TC-7.
        "temperature": 0.7,
        "max_output_tokens": 4096,
    },
    ("agent_configs", "ads_specialist"): {
        "instruction": "You are an ads specialist.",
        "model": "gemini-2.0-flash",
        "description": "Handles Google Ads queries",
        "mcp_servers": ["ads_mcp", "shared_viz_mcp"],
        "temperature": 0.2,
        "max_output_tokens": 2048,
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


# ---------------------------------------------------------------------------
# TC-7: AH-40 AC-4 — generation config flows from Firestore through
# build_hierarchy() into the constructed specialist LlmAgents at the
# hierarchy level (not just the lower-level build_agent factory tests).
# ---------------------------------------------------------------------------


class TestSpecialistGenerationConfigE2E:
    """TC-7 / AH-40 AC-4: build_hierarchy() applies the seeded ``temperature``
    and ``max_output_tokens`` to each specialist's SDK ``GenerateContentConfig``.

    The lower-level builder tests in ``test_factory.py`` cover the
    construction-boundary wiring. This test asserts the same property at
    the hierarchy level — i.e. against the docs as they would actually be
    read from Firestore — to close AC-4's literal "end-to-end build of
    ``agent_factory.build_hierarchy()`` against a fixture Firestore" gap.
    """

    def _capture_specialists(self, docs: dict) -> dict:
        """Run build_hierarchy and return a map from specialist name to its
        constructed LlmAgent."""
        import app.adk.agents.agent_factory.builder as b
        import app.adk.agents.agent_factory.hierarchy as h

        fake_db = _FakeFirestoreDb(docs)
        fake_registry = _FakeRegistry()
        captured: dict[str, object] = {}
        original_build_agent = b.build_agent

        def _capture(config, *, name: str, tools=None, **kwargs):
            agent = original_build_agent(config, name=name, tools=tools, **kwargs)
            captured[name] = agent
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
                side_effect=_capture,
            ),
        ):
            mock_build_toolset.side_effect = lambda sid, doc: MagicMock(
                name=f"toolset_{sid}"
            )
            mock_get_registry.return_value = fake_registry
            h.build_hierarchy(db=fake_db)

        return captured

    def test_analytics_specialist_generation_config_matches_doc(self) -> None:
        captured = self._capture_specialists(_E2E_DOCS)
        analytics = captured["analytics_specialist"]

        assert analytics.generate_content_config is not None
        assert analytics.generate_content_config.temperature == 0.7
        assert analytics.generate_content_config.max_output_tokens == 4096

    def test_ads_specialist_generation_config_matches_doc(self) -> None:
        captured = self._capture_specialists(_E2E_DOCS)
        ads = captured["ads_specialist"]

        assert ads.generate_content_config is not None
        assert ads.generate_content_config.temperature == 0.2
        assert ads.generate_content_config.max_output_tokens == 2048


# ---------------------------------------------------------------------------
# TC-AH41: Audit-field wiring — mcp_servers attaches the right toolset, the
# automatically_available filter excludes hidden defaults, and a regression
# contrast documents the pre-AH-41 bug where the GA agent had no MCP
# toolset because mcp_servers was not seeded.
# ---------------------------------------------------------------------------


# Realistic AH-41 fixture: ken_e_chatbot root + GA specialist (with MCP) +
# news specialist (no MCP, uses Vertex AI Search elsewhere). Matches the
# decision matrix exactly.
_AH41_DOCS: dict = {
    ("agent_configs", "ken_e_chatbot"): {
        "instruction": "You are KEN-E root.",
        "model": "gemini-2.5-pro",
        "description": "Root orchestration agent",
        "code_execution_enabled": False,
        "mcp_servers": [],
        "skill_ids": [],
        "sandbox_code_executor_enabled": False,
        "response_schema": None,
        "available_to_copy": False,
        "automatically_available": True,
        "visible_in_frontend": True,
    },
    ("agent_configs", "google_analytics_agent"): {
        "instruction": "You are a Google Analytics assistant.",
        "model": "gemini-2.5-pro",
        "description": "GA assistant",
        "code_execution_enabled": True,
        "mcp_servers": ["google_analytics_mcp"],
        "skill_ids": [],
        "sandbox_code_executor_enabled": False,
        "response_schema": None,
        "available_to_copy": True,
        "automatically_available": True,
        "visible_in_frontend": True,
    },
    ("agent_configs", "company_news_agent"): {
        "instruction": "You are a company news assistant.",
        "model": "gemini-2.5-pro",
        "description": "Company news",
        "code_execution_enabled": False,
        "mcp_servers": [],
        "skill_ids": [],
        "sandbox_code_executor_enabled": False,
        "response_schema": None,
        "available_to_copy": True,
        "automatically_available": True,
        "visible_in_frontend": True,
    },
    ("mcp_server_configs", "google_analytics_mcp"): {
        "enabled": True,
        "connection": {
            "connection_type": "sse",
            "url": "https://ga.mcp.example.com",
        },
        "auth_type": "ga_oauth",
    },
}


def _capture_specialists_with_docs(docs: dict) -> tuple[object, dict]:
    """Run build_hierarchy and capture each specialist LlmAgent by name."""
    import app.adk.agents.agent_factory.builder as b
    import app.adk.agents.agent_factory.hierarchy as h

    fake_db = _FakeFirestoreDb(docs)
    fake_registry = _FakeRegistry()
    captured: dict[str, object] = {}
    original_build_agent = b.build_agent

    def _capture(config, *, name: str, tools=None, **kwargs):
        agent = original_build_agent(config, name=name, tools=tools, **kwargs)
        if name != "ken_e":
            captured[name] = agent
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
            side_effect=_capture,
        ),
    ):
        mock_build_toolset.side_effect = lambda sid, doc: MagicMock(
            name=f"toolset_{sid}"
        )
        mock_get_registry.return_value = fake_registry
        root = h.build_hierarchy(db=fake_db)

    return root, captured


class TestAH41AuditFieldsWired:
    """AC-3 / AC-4: hierarchy build attaches the right tools and flags
    when the AH-41 matrix is seeded on every doc."""

    def test_ga_specialist_has_mcp_toolset_attached(self) -> None:
        _, specialists = _capture_specialists_with_docs(_AH41_DOCS)
        ga = specialists["google_analytics_agent"]
        assert len(ga.tools) == 1, (
            "AH-41 AC-4: the GA specialist's mcp_servers list must produce "
            "exactly one MCP toolset attached at runtime"
        )

    def test_news_specialist_has_empty_tools_list(self) -> None:
        _, specialists = _capture_specialists_with_docs(_AH41_DOCS)
        news = specialists["company_news_agent"]
        assert news.tools == []

    def test_ga_specialist_has_code_executor(self) -> None:
        _, specialists = _capture_specialists_with_docs(_AH41_DOCS)
        ga = specialists["google_analytics_agent"]
        assert ga.code_executor is not None

    def test_news_specialist_has_no_code_executor(self) -> None:
        _, specialists = _capture_specialists_with_docs(_AH41_DOCS)
        news = specialists["company_news_agent"]
        assert news.code_executor is None

    def test_root_has_dispatch_tools_for_both_specialists(self) -> None:
        root, _ = _capture_specialists_with_docs(_AH41_DOCS)
        tool_names = {getattr(t, "__name__", None) for t in root.tools}
        assert "dispatch_to_google_analytics_agent" in tool_names
        assert "dispatch_to_company_news_agent" in tool_names


class TestAH41AutomaticallyAvailableFilter:
    """AH-41: a default-status specialist with automatically_available=False
    is excluded from the hierarchy at Step 4½ of build_hierarchy."""

    def test_specialist_with_automatically_available_false_is_excluded(self) -> None:
        docs = {k: dict(v) for k, v in _AH41_DOCS.items()}
        docs[("agent_configs", "company_news_agent")]["automatically_available"] = False

        root, specialists = _capture_specialists_with_docs(docs)
        assert "company_news_agent" not in specialists
        tool_names = {getattr(t, "__name__", None) for t in root.tools}
        assert "dispatch_to_company_news_agent" not in tool_names
        # GA still present.
        assert "google_analytics_agent" in specialists


class TestAH41RegressionContrastGaMissingMcpServers:
    """Regression-contrast documenting the pre-AH-41 bug.

    Before AH-41 the GA agent doc had no ``mcp_servers`` field, so it
    landed on the schema default of ``[]`` and ``hierarchy.py:247``
    iterated zero items — no MCP toolset attached at runtime.

    This test verifies that an empty ``mcp_servers`` list reproduces the
    pre-fix state: the specialist is built but has zero tools. AH-41
    fixes this by seeding ``mcp_servers=["google_analytics_mcp"]``
    explicitly on the GA doc.
    """

    def test_ga_specialist_with_empty_mcp_servers_has_no_tools(self) -> None:
        docs = {k: dict(v) for k, v in _AH41_DOCS.items()}
        # Reproduce the pre-AH-41 state: mcp_servers absent → defaults to [].
        docs[("agent_configs", "google_analytics_agent")]["mcp_servers"] = []

        _, specialists = _capture_specialists_with_docs(docs)
        ga = specialists["google_analytics_agent"]
        assert ga.tools == [], (
            "Pre-AH-41 regression case: with mcp_servers=[] the GA "
            "specialist gets zero toolsets — this is the bug the audit fixes"
        )


class TestAhPrd06ToolIdsThreading:
    """AH-PRD-06 (review item #3): when an agent_config carries ``tool_ids``,
    ``build_hierarchy`` must thread the per-server allowlist into
    ``build_toolset_for_doc`` via the ``allowed_tool_names`` kwarg — not
    mutate ``toolset.tool_filter`` after the fact. Also: servers with no
    listed tools should be skipped entirely.
    """

    def _docs_with_tool_ids(self, tool_ids: list[str]) -> dict:
        # Clone the base _E2E_DOCS and stamp tool_ids onto analytics_specialist.
        docs = {k: dict(v) for k, v in _E2E_DOCS.items()}
        docs[("agent_configs", "analytics_specialist")]["tool_ids"] = tool_ids
        return docs

    def _run_capturing_build_toolset(self, docs: dict) -> list[tuple]:
        """Return the list of ``(args, kwargs)`` ``build_toolset_for_doc`` was called with."""
        import app.adk.agents.agent_factory.hierarchy as h

        fake_db = _FakeFirestoreDb(docs)
        fake_registry = _FakeRegistry()
        calls: list[tuple] = []

        def _side_effect(*args, **kwargs):
            calls.append((args, kwargs))
            sid = args[0]
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

        return calls

    def test_tool_ids_set_passes_allowed_tool_names_at_construction(self) -> None:
        """Verifies the kwarg threading: when tool_ids names a tool on ga_mcp,
        build_toolset_for_doc receives allowed_tool_names=["list_ga_accounts"]
        for that server. Confirms the kwarg is live, not dead code."""
        docs = self._docs_with_tool_ids(["ga_mcp.list_ga_accounts"])
        calls = self._run_capturing_build_toolset(docs)

        ga_calls = [
            (args, kwargs) for args, kwargs in calls if args[0] == "ga_mcp"
        ]
        # analytics_specialist references ga_mcp; ads_specialist does not.
        # analytics has tool_ids set → the call carries the kwarg.
        analytics_ga_calls = [
            kwargs for _, kwargs in ga_calls if "allowed_tool_names" in kwargs
        ]
        assert len(analytics_ga_calls) == 1
        assert analytics_ga_calls[0]["allowed_tool_names"] == ["list_ga_accounts"]

    def test_tool_ids_none_omits_kwarg(self) -> None:
        """Legacy path: when tool_ids is absent, build_toolset_for_doc is
        called without the allowed_tool_names kwarg, preserving the original
        two-arg signature."""
        # _E2E_DOCS has no tool_ids on any spec.
        calls = self._run_capturing_build_toolset(_E2E_DOCS)
        # Every call should be (args=(sid, doc), kwargs={}).
        assert all(kwargs == {} for _, kwargs in calls)

    def test_tool_ids_skips_servers_with_no_match(self) -> None:
        """A server referenced by mcp_servers but not represented in tool_ids
        is dropped before the toolset is constructed (no wasted McpToolset
        instantiation)."""
        # analytics_specialist references ga_mcp + shared_viz_mcp; tool_ids
        # only names a ga_mcp tool, so shared_viz_mcp should be skipped on
        # this specialist (it will still appear on ads_specialist which has
        # no tool_ids restriction).
        docs = self._docs_with_tool_ids(["ga_mcp.list_ga_accounts"])
        calls = self._run_capturing_build_toolset(docs)

        # shared_viz_mcp should only be built once (for ads_specialist),
        # not twice (it would have been built for analytics in the legacy
        # path).
        shared_calls = [c for c in calls if c[0][0] == "shared_viz_mcp"]
        assert len(shared_calls) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
