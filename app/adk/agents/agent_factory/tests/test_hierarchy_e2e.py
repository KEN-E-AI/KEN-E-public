"""Integration tests for app.adk.agents.agent_factory.hierarchy.build_hierarchy().

Per AH-PRD-09 Phase 2, build_hierarchy() builds the root agent only.
Specialists are resolved per-turn by specialist_runtime; no N+1 Firestore
read occurs at deploy time.

Test classes:
  TC-1  TestRootOnlyBuild           — root is LlmAgent "ken_e" with single delegate tool
  TC-2  TestDelegateToSpecialistE2E — tool routes to specialist_runtime.run end-to-end
  TC-3  TestAccountOverlay          — account_id overlay is forwarded to _load_and_merge
  TC-4  TestRootInstructionContent  — instruction provider wiring
  TC-5  TestErrorHandling           — missing root config, bad account_id
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from google.adk.agents import LlmAgent
from google.adk.agents.llm_agent_config import LlmAgentConfig

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


# ---------------------------------------------------------------------------
# In-memory Firestore stand-in
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
# Canonical fixture documents
# ---------------------------------------------------------------------------

_ROOT_DOC = {
    "instruction": "You are KEN-E root.",
    "model": "gemini-2.0-flash",
    "description": "Root orchestration agent",
}

_E2E_DOCS: dict = {
    ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
    # Extra specialist configs present in Firestore — must NOT affect root.tools.
    ("agent_configs", "analytics_specialist"): {
        "instruction": "You are an analytics specialist.",
        "model": "gemini-2.0-flash",
        "description": "Handles Google Analytics queries",
        "mcp_servers": ["ga_mcp"],
    },
    ("agent_configs", "ads_specialist"): {
        "instruction": "You are an ads specialist.",
        "model": "gemini-2.0-flash",
        "description": "Handles Google Ads queries",
        "mcp_servers": ["ads_mcp"],
    },
}


def _run_build_hierarchy(docs: dict, account_id: str | None = None) -> LlmAgent:
    """Call build_hierarchy with standard callback patches."""
    import app.adk.agents.agent_factory.hierarchy as h

    with (
        _PATCH_BEFORE_AGENT,
        _PATCH_AFTER_AGENT,
        _PATCH_BEFORE_TOOL,
        _PATCH_AFTER_TOOL,
    ):
        return h.build_hierarchy(account_id=account_id, db=_FakeFirestoreDb(docs))


def _make_context(state: dict) -> MagicMock:
    ctx = MagicMock()
    ctx.state = state
    return ctx


@pytest.fixture(autouse=True)
def _patch_e2e_config_cache_loader():
    """Prevent agent.instruction(ctx) calls from hitting real Firestore."""
    from app.adk.agents.utils import config_cache

    config_cache.clear_config_cache()
    with patch.object(
        config_cache,
        "load_config_from_firestore",
        side_effect=lambda doc_id, project_id="ken-e-dev": (
            LlmAgentConfig(
                name=doc_id,
                model="gemini-2.0-flash",
                instruction=_ROOT_DOC["instruction"],
                description="",
                generate_content_config={"temperature": 0.3, "max_output_tokens": 2048},
            ),
            {"version": "test"},
            {},
        ),
    ):
        yield
    config_cache.clear_config_cache()


# ---------------------------------------------------------------------------
# TC-1: Root-only build
# ---------------------------------------------------------------------------


class TestRootOnlyBuild:
    """TC-1: build_hierarchy() returns an LlmAgent named 'ken_e' with no
    specialist-dispatch tool (AH-75 replaced delegate_to_specialist with
    ADK's native transfer_to_agent + dynamically-attached sub_agents),
    regardless of how many specialist configs exist in Firestore."""

    def test_root_is_llm_agent(self) -> None:
        root = _run_build_hierarchy(_E2E_DOCS)
        assert isinstance(root, LlmAgent)

    def test_root_name_is_ken_e(self) -> None:
        root = _run_build_hierarchy(_E2E_DOCS)
        assert root.name == "ken_e"

    def test_root_has_no_specialist_dispatch_tool(self) -> None:
        """AH-75: root carries no specialist-dispatch tool. Specialists are
        reached via transfer_to_agent + per-turn sub_agents attachment."""
        root = _run_build_hierarchy(_E2E_DOCS)
        assert root.tools == []

    def test_root_has_attach_specialists_before_agent_callback(self) -> None:
        """The runtime sub_agents-sync callback must be wired so per-turn
        attachment runs before the LLM is invoked."""
        from app.adk.agents.agent_factory.sub_agent_attacher import (
            attach_specialists_before_agent_callback,
        )
        root = _run_build_hierarchy(_E2E_DOCS)
        callbacks = root.before_agent_callback or []
        assert attach_specialists_before_agent_callback in callbacks

    def test_extra_specialist_configs_do_not_add_tools(self) -> None:
        """Specialist Firestore docs exist but must NOT add tools to the root."""
        root = _run_build_hierarchy(_E2E_DOCS)
        # _E2E_DOCS has 2 specialist configs + root — root still has 0 tools.
        assert root.tools == []

    def test_single_firestore_read_for_root_config(self) -> None:
        """build_hierarchy reads only the root config, not all specialist configs."""
        import app.adk.agents.agent_factory.hierarchy as h
        from app.adk.agents.agent_factory.config_loader import _load_and_merge

        load_calls: list[str] = []

        def _spy(db: Any, config_id: str, account_id: Any) -> Any:
            load_calls.append(config_id)
            return _load_and_merge(db, config_id, account_id)

        with (
            _PATCH_BEFORE_AGENT,
            _PATCH_AFTER_AGENT,
            _PATCH_BEFORE_TOOL,
            _PATCH_AFTER_TOOL,
            patch(
                "app.adk.agents.agent_factory.hierarchy._load_and_merge",
                side_effect=_spy,
            ),
        ):
            h.build_hierarchy(db=_FakeFirestoreDb(_E2E_DOCS))

        # Only the root config should be loaded.
        assert load_calls == ["ken_e_chatbot"]


# ---------------------------------------------------------------------------
# TC-2 was TestDelegateToSpecialistE2E in pre-AH-75 code — the function-tool
# dispatch path. AH-75 (Approach 1) replaced delegate_to_specialist with ADK's
# native transfer_to_agent + dynamically-attached sub_agents. The equivalent
# coverage now lives in:
#   * test_sub_agent_attacher.py — per-turn sub_agents sync mechanics
#   * test_specialist_runtime.py::TestSpecialistRuntimeReviewWrap — review-
#     pipeline opt-in via config.default_acceptance_criteria
#   * test_chat_billing_parity.py — transfer_to_agent end-to-end event
#     propagation under both Mode A and Mode B (no xfail after AH-75)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# TC-3: Account overlay
# ---------------------------------------------------------------------------


class TestAccountOverlay:
    """TC-3: account_id is forwarded to _load_and_merge; root config picks up
    account-specific overlays via the existing merge semantics."""

    def test_account_id_forwarded_to_load_and_merge(self) -> None:
        import app.adk.agents.agent_factory.hierarchy as h
        from app.adk.agents.agent_factory.config_loader import _load_and_merge

        captured_account_ids: list[str | None] = []

        def _spy(db: Any, config_id: str, account_id: Any) -> Any:
            captured_account_ids.append(account_id)
            return _load_and_merge(db, config_id, account_id)

        with (
            _PATCH_BEFORE_AGENT,
            _PATCH_AFTER_AGENT,
            _PATCH_BEFORE_TOOL,
            _PATCH_AFTER_TOOL,
            patch(
                "app.adk.agents.agent_factory.hierarchy._load_and_merge",
                side_effect=_spy,
            ),
        ):
            h.build_hierarchy(
                account_id="acc_test",
                db=_FakeFirestoreDb({("agent_configs", "ken_e_chatbot"): _ROOT_DOC}),
            )

        assert "acc_test" in captured_account_ids

    def test_none_account_id_forwarded_as_none(self) -> None:
        import app.adk.agents.agent_factory.hierarchy as h
        from app.adk.agents.agent_factory.config_loader import _load_and_merge

        captured_account_ids: list[str | None] = []

        def _spy(db: Any, config_id: str, account_id: Any) -> Any:
            captured_account_ids.append(account_id)
            return _load_and_merge(db, config_id, account_id)

        with (
            _PATCH_BEFORE_AGENT,
            _PATCH_AFTER_AGENT,
            _PATCH_BEFORE_TOOL,
            _PATCH_AFTER_TOOL,
            patch(
                "app.adk.agents.agent_factory.hierarchy._load_and_merge",
                side_effect=_spy,
            ),
        ):
            h.build_hierarchy(
                account_id=None,
                db=_FakeFirestoreDb({("agent_configs", "ken_e_chatbot"): _ROOT_DOC}),
            )

        assert None in captured_account_ids

    def test_account_overlay_root_still_has_no_dispatch_tool(self) -> None:
        """With account_id provided, root still has no specialist-dispatch tool
        (AH-75 — sub_agents are populated per-turn by the before_agent_callback)."""
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("accounts", "acc_xyz", "agent_configs", "ken_e_chatbot"): {
                "instruction": "CUSTOM root instruction for acc_xyz.",
                "model": "gemini-2.0-flash",
                "based_on_version": 1,
            },
        }
        root = _run_build_hierarchy(docs, account_id="acc_xyz")
        assert root.tools == []


# ---------------------------------------------------------------------------
# TC-4: Root instruction content
# ---------------------------------------------------------------------------


class TestRootInstructionContent:
    """TC-4: The root instruction provider is wired to compose cache-backed
    base instruction + available_specialists_provider per-turn."""

    def test_instruction_includes_base_root_instruction(self) -> None:
        canned_block = "## Available Specialists\n\n- None registered."

        with patch(
            "app.adk.agents.agent_factory.specialist_runtime.available_specialists_provider",
            return_value=canned_block,
        ):
            root = _run_build_hierarchy({("agent_configs", "ken_e_chatbot"): _ROOT_DOC})

        rendered = root.instruction(_make_context({}))
        assert "You are KEN-E root." in rendered

    def test_instruction_includes_available_specialists_block(self) -> None:
        canned_block = "## Available Specialists\n\n- **my_agent**: Does things."

        with patch(
            "app.adk.agents.agent_factory.specialist_runtime.available_specialists_provider",
            return_value=canned_block,
        ):
            root = _run_build_hierarchy({("agent_configs", "ken_e_chatbot"): _ROOT_DOC})

        rendered = root.instruction(_make_context({}))
        assert "## Available Specialists" in rendered
        assert "my_agent" in rendered

    def test_instruction_with_org_context_prepends_context_block(self) -> None:
        canned_block = "## Available Specialists\n\n- None registered."

        with patch(
            "app.adk.agents.agent_factory.specialist_runtime.available_specialists_provider",
            return_value=canned_block,
        ):
            root = _run_build_hierarchy({("agent_configs", "ken_e_chatbot"): _ROOT_DOC})

        rendered = root.instruction(
            _make_context({"organization_context": "Acme Corp marketing"})
        )
        assert "[ORGANIZATION CONTEXT]" in rendered
        assert "Acme Corp marketing" in rendered
        assert "You are KEN-E root." in rendered


# ---------------------------------------------------------------------------
# TC-5: Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """TC-5: Error paths in build_hierarchy."""

    def test_missing_root_config_raises_config_not_found(self) -> None:
        from app.adk.agents.agent_factory.config_loader import ConfigNotFoundError

        with pytest.raises(ConfigNotFoundError):
            _run_build_hierarchy({})

    def test_only_specialist_configs_no_root_raises_config_not_found(self) -> None:
        from app.adk.agents.agent_factory.config_loader import ConfigNotFoundError

        docs = {
            ("agent_configs", "analytics_specialist"): {
                "instruction": "You are analytics.",
                "model": "gemini-2.0-flash",
                "mcp_servers": [],
            }
        }
        with pytest.raises(ConfigNotFoundError):
            _run_build_hierarchy(docs)

    def test_invalid_account_id_raises_value_error(self) -> None:
        import app.adk.agents.agent_factory.hierarchy as h

        with pytest.raises(ValueError, match="is invalid"):
            h.build_hierarchy(
                account_id="../../etc/passwd",
                db=_FakeFirestoreDb({}),
            )

    def test_firestore_connection_failure_raises_firestore_connection_error(
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
