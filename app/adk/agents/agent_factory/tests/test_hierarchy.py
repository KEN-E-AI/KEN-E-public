"""Unit tests for app.adk.agents.agent_factory.hierarchy.build_hierarchy().

Per AH-PRD-09 Phase 2, build_hierarchy() now builds the root agent only.
Specialists are resolved per-turn by specialist_runtime; no N+1 Firestore
read occurs at deploy time.

Covered AC dimensions:
  - Root agent construction: name, single tool, callbacks, config_doc_id
  - instruction_suffix_provider wiring (available_specialists_provider)
  - Error cases: missing root config, Firestore failure, invalid account_id
  - Cache-backed instruction hot-reload
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from google.adk.agents import LlmAgent
from google.adk.agents.llm_agent_config import LlmAgentConfig

from app.adk.agents.agent_factory.config_loader import ConfigNotFoundError

# ---------------------------------------------------------------------------
# Sentinel callback objects
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
# Test fixtures
# ---------------------------------------------------------------------------

_ROOT_DOC = {
    "instruction": "You are the KEN-E root assistant.",
    "model": "gemini-2.0-flash",
    "description": "Root orchestrator",
}


def _build_hierarchy_with_patches(fake_db: _FakeFirestoreDb) -> LlmAgent:
    """Call build_hierarchy with standard callback patches applied."""
    import app.adk.agents.agent_factory.hierarchy as h

    with (
        _PATCH_BEFORE_AGENT,
        _PATCH_AFTER_AGENT,
        _PATCH_BEFORE_TOOL,
        _PATCH_AFTER_TOOL,
    ):
        return h.build_hierarchy(db=fake_db)


def _make_context(state: dict) -> MagicMock:
    ctx = MagicMock()
    ctx.state = state
    return ctx


def _fake_cache_loader(
    doc_id: str, project_id: str = "ken-e-dev"
) -> tuple[Any, dict, dict]:
    """Minimal in-memory loader so agent.instruction(ctx) never hits Firestore."""
    cfg = LlmAgentConfig(
        name=doc_id,
        model="gemini-2.0-flash",
        instruction=_ROOT_DOC["instruction"],
        description="",
        generate_content_config={"temperature": 0.3, "max_output_tokens": 2048},
    )
    return cfg, {"version": "test"}, {}


@pytest.fixture(autouse=True)
def _patch_config_cache_loader():
    """Patch load_config_from_firestore for every test so instruction(ctx) never
    hits real Firestore."""
    from app.adk.agents.utils import config_cache

    config_cache.clear_config_cache()
    with patch.object(
        config_cache, "load_config_from_firestore", side_effect=_fake_cache_loader
    ):
        yield
    config_cache.clear_config_cache()


# ---------------------------------------------------------------------------
# TestRootAgentConstruction
# ---------------------------------------------------------------------------


class TestRootAgentConstruction:
    def test_root_agent_name_is_ken_e(self) -> None:
        docs = {("agent_configs", "ken_e_chatbot"): _ROOT_DOC}
        root = _build_hierarchy_with_patches(_FakeFirestoreDb(docs))

        assert root.name == "ken_e"

    def test_root_agent_is_llm_agent(self) -> None:
        docs = {("agent_configs", "ken_e_chatbot"): _ROOT_DOC}
        root = _build_hierarchy_with_patches(_FakeFirestoreDb(docs))

        assert isinstance(root, LlmAgent)

    def test_root_agent_has_exactly_one_tool(self) -> None:
        """Per AH-PRD-09 Phase 2, root carries only delegate_to_specialist."""
        docs = {("agent_configs", "ken_e_chatbot"): _ROOT_DOC}
        root = _build_hierarchy_with_patches(_FakeFirestoreDb(docs))

        assert len(root.tools) == 1

    def test_root_agent_tool_is_delegate_to_specialist(self) -> None:
        """The single root tool must be delegate_to_specialist by name."""
        docs = {("agent_configs", "ken_e_chatbot"): _ROOT_DOC}
        root = _build_hierarchy_with_patches(_FakeFirestoreDb(docs))

        tool_name = getattr(root.tools[0], "__name__", None)
        assert tool_name == "delegate_to_specialist"

    def test_root_agent_tool_count_unchanged_with_extra_configs(self) -> None:
        """Extra specialist configs in Firestore must not add tools to the root
        — specialists are resolved per-turn, not at deploy time."""
        extra_spec = {
            "instruction": "You are specialist A.",
            "model": "gemini-2.0-flash",
            "description": "Specialist A",
            "mcp_servers": [],
        }
        docs = {
            ("agent_configs", "ken_e_chatbot"): _ROOT_DOC,
            ("agent_configs", "specialist_a"): extra_spec,
            ("agent_configs", "specialist_b"): extra_spec,
        }
        root = _build_hierarchy_with_patches(_FakeFirestoreDb(docs))

        # Still only 1 tool regardless of how many specialist configs exist.
        assert len(root.tools) == 1

    def test_root_agent_instruction_suffix_provider_wired(self) -> None:
        """build_hierarchy must pass instruction_suffix_provider=available_specialists_provider
        to build_agent, NOT a static instruction_suffix string."""
        import app.adk.agents.agent_factory.builder as b
        import app.adk.agents.agent_factory.hierarchy as h
        from app.adk.agents.agent_factory.specialist_runtime import (
            available_specialists_provider,
        )

        docs = {("agent_configs", "ken_e_chatbot"): _ROOT_DOC}
        fake_db = _FakeFirestoreDb(docs)
        captured: dict[str, Any] = {}
        original_build_agent = b.build_agent

        def _spy(config, *, name: str, tools=None, **kwargs):
            captured["instruction_suffix_provider"] = kwargs.get(
                "instruction_suffix_provider"
            )
            captured["instruction_suffix"] = kwargs.get("instruction_suffix", "")
            return original_build_agent(config, name=name, tools=tools, **kwargs)

        with (
            _PATCH_BEFORE_AGENT,
            _PATCH_AFTER_AGENT,
            _PATCH_BEFORE_TOOL,
            _PATCH_AFTER_TOOL,
            patch(
                "app.adk.agents.agent_factory.hierarchy.build_agent",
                side_effect=_spy,
            ),
        ):
            h.build_hierarchy(db=fake_db)

        assert captured["instruction_suffix_provider"] is available_specialists_provider
        assert not captured["instruction_suffix"]


# ---------------------------------------------------------------------------
# TestCallbackWiring
# ---------------------------------------------------------------------------


class TestCallbackWiring:
    def test_root_agent_before_agent_callback_starts_with_weave_sentinel(
        self,
    ) -> None:
        docs = {("agent_configs", "ken_e_chatbot"): _ROOT_DOC}
        root = _build_hierarchy_with_patches(_FakeFirestoreDb(docs))

        assert root.before_agent_callback[0] is _WEAVE_BEFORE

    def test_root_agent_after_agent_callback_starts_with_weave_sentinel(
        self,
    ) -> None:
        docs = {("agent_configs", "ken_e_chatbot"): _ROOT_DOC}
        root = _build_hierarchy_with_patches(_FakeFirestoreDb(docs))

        assert root.after_agent_callback[0] is _WEAVE_AFTER

    def test_root_agent_before_tool_callback_starts_with_adk_sentinel(
        self,
    ) -> None:
        docs = {("agent_configs", "ken_e_chatbot"): _ROOT_DOC}
        root = _build_hierarchy_with_patches(_FakeFirestoreDb(docs))

        assert root.before_tool_callback[0] is _ADK_BEFORE_TOOL

    def test_root_agent_after_tool_callback_starts_with_adk_sentinel(self) -> None:
        docs = {("agent_configs", "ken_e_chatbot"): _ROOT_DOC}
        root = _build_hierarchy_with_patches(_FakeFirestoreDb(docs))

        assert root.after_tool_callback[0] is _ADK_AFTER_TOOL


# ---------------------------------------------------------------------------
# TestErrorCases
# ---------------------------------------------------------------------------


class TestErrorCases:
    def test_missing_root_config_raises_config_not_found_error(self) -> None:
        # Firestore has no ken_e_chatbot doc.
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

    @pytest.mark.parametrize(
        "bad_id",
        [
            "../../admin",
            "acc/with/slash",
            "..",
            "",
            "a" * 129,
        ],
    )
    def test_invalid_account_id_raises_value_error(self, bad_id: str) -> None:
        import app.adk.agents.agent_factory.hierarchy as h

        with pytest.raises(ValueError, match="is invalid"):
            h.build_hierarchy(account_id=bad_id, db=_FakeFirestoreDb({}))

    def test_none_account_id_skips_validation(self) -> None:
        import app.adk.agents.agent_factory.hierarchy as h

        try:
            h.build_hierarchy(account_id=None, db=_FakeFirestoreDb({}))
        except ValueError as exc:
            pytest.fail(f"Unexpected ValueError with account_id=None: {exc}")
        except Exception:
            pass

    def test_valid_account_id_accepted(self) -> None:
        import app.adk.agents.agent_factory.hierarchy as h

        try:
            h.build_hierarchy(account_id="acc_abcdef0123", db=_FakeFirestoreDb({}))
        except ValueError as exc:
            pytest.fail(f"Unexpected ValueError for valid account_id: {exc}")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# TestCacheBackedInstruction
# ---------------------------------------------------------------------------


def _make_llm_config_mock(instruction: str) -> MagicMock:
    cfg = MagicMock()
    cfg.instruction = instruction
    return cfg


class TestCacheBackedInstruction:
    def test_root_agent_instruction_reads_from_config_cache_per_call(self) -> None:
        from app.adk.agents.utils import config_cache

        docs = {("agent_configs", "ken_e_chatbot"): _ROOT_DOC}
        fake_db = _FakeFirestoreDb(docs)

        _canned_suffix = "## Available Specialists\n\n- None registered."

        with (
            patch.object(
                config_cache,
                "load_config_from_firestore",
                return_value=(
                    _make_llm_config_mock("v1 instruction"),
                    {"version": "v1"},
                    {},
                ),
            ),
            patch(
                "app.adk.agents.agent_factory.specialist_runtime.available_specialists_provider",
                return_value=_canned_suffix,
            ),
        ):
            config_cache.clear_config_cache()
            root_agent = _build_hierarchy_with_patches(fake_db)
            ctx = _make_context({})
            result = root_agent.instruction(ctx)

        assert "v1 instruction" in result

    def test_root_agent_live_reload_after_cache_clear(self) -> None:
        from app.adk.agents.utils import config_cache

        docs = {("agent_configs", "ken_e_chatbot"): _ROOT_DOC}
        fake_db = _FakeFirestoreDb(docs)

        _canned_suffix = "## Available Specialists\n\n- None registered."

        with (
            patch.object(config_cache, "load_config_from_firestore") as mock_load,
            patch(
                "app.adk.agents.agent_factory.specialist_runtime.available_specialists_provider",
                return_value=_canned_suffix,
            ),
        ):
            mock_load.return_value = (
                _make_llm_config_mock("v1 instruction"),
                {"version": "v1"},
                {},
            )
            config_cache.clear_config_cache()
            root_agent = _build_hierarchy_with_patches(fake_db)
            ctx = _make_context({})
            assert "v1 instruction" in root_agent.instruction(ctx)

            config_cache.clear_config_cache()
            mock_load.return_value = (
                _make_llm_config_mock("v2 updated instruction"),
                {"version": "v2"},
                {},
            )
            result = root_agent.instruction(ctx)

        assert "v2 updated instruction" in result
        assert "v1 instruction" not in result

    def test_root_agent_config_doc_id_is_root_config_id(self) -> None:
        """build_hierarchy must pass config_doc_id=ROOT_CONFIG_ID to build_agent."""
        import app.adk.agents.agent_factory.builder as b
        import app.adk.agents.agent_factory.hierarchy as h

        docs = {("agent_configs", "ken_e_chatbot"): _ROOT_DOC}
        fake_db = _FakeFirestoreDb(docs)
        captured: dict[str, Any] = {}
        original_build_agent = b.build_agent

        def _spy(config, *, name: str, tools=None, **kwargs):
            captured["config_doc_id"] = kwargs.get("config_doc_id")
            return original_build_agent(config, name=name, tools=tools, **kwargs)

        with (
            _PATCH_BEFORE_AGENT,
            _PATCH_AFTER_AGENT,
            _PATCH_BEFORE_TOOL,
            _PATCH_AFTER_TOOL,
            patch(
                "app.adk.agents.agent_factory.hierarchy.build_agent",
                side_effect=_spy,
            ),
        ):
            h.build_hierarchy(db=fake_db)

        from app.adk.agents.agent_factory.hierarchy import ROOT_CONFIG_ID

        assert captured["config_doc_id"] == ROOT_CONFIG_ID

    def test_get_cached_config_called_on_each_instruction_invocation(self) -> None:
        from app.adk.agents.utils import config_cache

        docs = {("agent_configs", "ken_e_chatbot"): _ROOT_DOC}
        fake_db = _FakeFirestoreDb(docs)

        _canned_suffix = "## Available Specialists\n\n- None registered."

        with (
            patch.object(
                config_cache,
                "load_config_from_firestore",
                return_value=(_make_llm_config_mock("base"), {}, {}),
            ) as mock_load,
            patch(
                "app.adk.agents.agent_factory.specialist_runtime.available_specialists_provider",
                return_value=_canned_suffix,
            ),
        ):
            config_cache.clear_config_cache()
            root_agent = _build_hierarchy_with_patches(fake_db)
            ctx = _make_context({})

            root_agent.instruction(ctx)
            assert mock_load.call_count == 1

            config_cache.clear_config_cache()
            root_agent.instruction(ctx)
            assert mock_load.call_count == 2


# ---------------------------------------------------------------------------
# TestPrivateHelpers
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


# ---------------------------------------------------------------------------
# TestWeaveDecoratorOnConfigCache — unchanged from AH-58
# ---------------------------------------------------------------------------


class TestWeaveDecoratorOnConfigCache:
    def test_get_cached_config_decorated_with_correct_span_name(self) -> None:
        import importlib

        import app.adk.agents.utils.config_cache as cc_module

        captured_names: list[str | None] = []

        def _recording_safe_weave_op(name: str | None = None):
            captured_names.append(name)

            def _identity(fn):
                return fn

            return _identity

        with patch(
            "app.utils.weave_observability.safe_weave_op",
            new=_recording_safe_weave_op,
        ):
            importlib.reload(cc_module)

        try:
            assert "load_config_from_firestore" in captured_names, (
                f"safe_weave_op was not called with name='load_config_from_firestore'; "
                f"captured names: {captured_names}"
            )
        finally:
            importlib.reload(cc_module)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
