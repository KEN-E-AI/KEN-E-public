"""
Unit tests for the SK-PRD-02 skill-toolset wiring in build_agent().

Tests inject a fake ``kene_api.services.skill_loader`` module into
``sys.modules`` via ``monkeypatch`` so the tests run in the app-adk-tests CI
environment where ``kene_api`` is not installed.

The test helper ``_build_with_skills`` is intentionally separate from the
``_build`` helper in test_factory.py so that skill-loading behaviour is
exercised directly rather than bypassed.

SK-27 note: AC-2a calls for setting ``skill_load_total_failure=true`` on the
agent's ``skill.list`` Weave span.  In the all-skills-fail case no
``SkillToolset`` is attached and the ``list_skills`` tool will never fire, so
no ``skill.list`` span ever exists.  This issue satisfies the actionable part
of AC-2a by:
  1. Emitting a structured ERROR log ``skill_load_total_failure`` with
     ``account_id``, ``config_id``, and ``skill_ids`` (observable by ops).
  2. Recording ``skill_load_total_failure=True`` on the
     ``skill_metadata`` sidecar (``WeakKeyDictionary`` keyed by the
     ``LlmAgent``) so SK-27 can read the flag when it adds span instrumentation.
"""

from __future__ import annotations

import asyncio
import sys
import types
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.adk.agents.agent_factory.config_loader import MergedAgentConfig

# ---------------------------------------------------------------------------
# Sentinel callback objects (mirrors test_factory.py)
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
# Fake ADK Skill factory
# ---------------------------------------------------------------------------


def _make_adk_skill(name: str) -> Any:
    """Return a minimal ADK Skill with the given name."""
    from google.adk.skills import models

    return models.Skill(
        frontmatter=models.Frontmatter(name=name, description=f"Skill {name}"),
        instructions=f"# {name}\nDo things.",
    )


# ---------------------------------------------------------------------------
# Fake kene_api.services.skill_loader module factory
# ---------------------------------------------------------------------------


class _SkillNotFoundError(Exception):
    """Stand-in for kene_api.services.skill_loader.SkillNotFoundError."""


class _SkillCorruptError(Exception):
    """Stand-in for kene_api.services.skill_loader.SkillCorruptError."""


def _make_fake_loader_module(
    *,
    skills_by_id: dict[str, Any] | None = None,
    raise_for_ids: dict[str, type[Exception]] | None = None,
) -> types.ModuleType:
    """Create a fake ``kene_api.services.skill_loader`` module.

    Args:
        skills_by_id: Map of skill_id → ADK Skill to return on success.
        raise_for_ids: Map of skill_id → exception class to raise on load.
    """
    skills_by_id = skills_by_id or {}
    raise_for_ids = raise_for_ids or {}

    async def load_skill(account_id: str, skill_id: str, **kwargs: Any) -> Any:
        if skill_id in raise_for_ids:
            raise raise_for_ids[skill_id](
                f"Fake error loading {skill_id!r} for account {account_id!r}"
            )
        if skill_id in skills_by_id:
            return skills_by_id[skill_id]
        raise _SkillNotFoundError(
            f"Skill {skill_id!r} not found (account={account_id!r})"
        )

    mod = types.ModuleType("kene_api.services.skill_loader")
    mod.load_skill = load_skill  # type: ignore[attr-defined]
    mod.SkillNotFoundError = _SkillNotFoundError  # type: ignore[attr-defined]
    mod.SkillCorruptError = _SkillCorruptError  # type: ignore[attr-defined]
    return mod


# ---------------------------------------------------------------------------
# Build helper
# ---------------------------------------------------------------------------


def _build_with_skills(config: MergedAgentConfig, *, account_id: str, **kwargs: Any):
    """Call build_agent with real skill-loading wiring (callbacks patched)."""
    import app.adk.agents.agent_factory.builder as b

    with _PATCH_BEFORE_AGENT, _PATCH_AFTER_AGENT, _PATCH_BEFORE_TOOL, _PATCH_AFTER_TOOL:
        return b.build_agent(config, account_id=account_id, **kwargs)


def _make_config(**kwargs: Any) -> MergedAgentConfig:
    defaults = {"instruction": "You are a helpful agent.", "model": "gemini-2.0-flash"}
    return MergedAgentConfig(**{**defaults, **kwargs})


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestBoundary:
    """build_agent raises TypeError when account_id is omitted entirely."""

    def test_missing_account_id_raises_type_error(self) -> None:
        """Omitting the required account_id keyword-only arg raises TypeError."""
        import app.adk.agents.agent_factory.builder as b

        config = _make_config()
        with (
            _PATCH_BEFORE_AGENT,
            _PATCH_AFTER_AGENT,
            _PATCH_BEFORE_TOOL,
            _PATCH_AFTER_TOOL,
            pytest.raises(TypeError),
        ):
            b.build_agent(config, name="no_account")  # type: ignore[call-arg]


class TestAC1SkillWiring:
    """AC-1: Two-skill config → LlmAgent contains exactly one SkillToolset."""

    def test_two_skills_produce_one_skill_toolset_in_tools(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from google.adk.tools.skill_toolset import SkillToolset

        skill_a = _make_adk_skill("skill-alpha")
        skill_b = _make_adk_skill("skill-beta")
        fake_loader = _make_fake_loader_module(
            skills_by_id={"id-a": skill_a, "id-b": skill_b}
        )
        monkeypatch.setitem(sys.modules, "kene_api.services.skill_loader", fake_loader)

        config = _make_config(skill_ids=["id-a", "id-b"])
        agent = _build_with_skills(config, name="two_skills", account_id="acc_x")

        toolsets = [t for t in agent.tools if isinstance(t, SkillToolset)]
        assert len(toolsets) == 1, "Expected exactly one SkillToolset"
        toolset = toolsets[0]
        assert set(toolset._skills.keys()) == {"skill-alpha", "skill-beta"}

    def test_loader_called_with_correct_account_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """load_skill is always called with the account_id from build_agent."""
        calls: list[tuple[str, str]] = []

        async def tracking_load_skill(
            account_id: str, skill_id: str, **kwargs: Any
        ) -> Any:
            calls.append((account_id, skill_id))
            return _make_adk_skill(f"skill-{skill_id}")

        mod = types.ModuleType("kene_api.services.skill_loader")
        mod.load_skill = tracking_load_skill  # type: ignore[attr-defined]
        mod.SkillNotFoundError = _SkillNotFoundError  # type: ignore[attr-defined]
        mod.SkillCorruptError = _SkillCorruptError  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "kene_api.services.skill_loader", mod)

        config = _make_config(skill_ids=["id-1", "id-2"])
        _build_with_skills(config, name="tracking", account_id="acc_tracker")

        assert calls == [("acc_tracker", "id-1"), ("acc_tracker", "id-2")]


class TestAC2MissingSkillTolerance:
    """AC-2: One failed skill → build succeeds with remaining skills loaded."""

    def test_one_of_two_skills_fails_build_succeeds(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        from google.adk.tools.skill_toolset import SkillToolset

        skill_a = _make_adk_skill("skill-surviving")
        fake_loader = _make_fake_loader_module(
            skills_by_id={"id-good": skill_a},
            raise_for_ids={"id-bad": _SkillNotFoundError},
        )
        monkeypatch.setitem(sys.modules, "kene_api.services.skill_loader", fake_loader)

        config = _make_config(skill_ids=["id-good", "id-bad"])

        with caplog.at_level(logging.WARNING):
            agent = _build_with_skills(config, name="partial", account_id="acc_y")

        # Build succeeded
        assert agent is not None

        # Only the surviving skill is in the toolset
        toolsets = [t for t in agent.tools if isinstance(t, SkillToolset)]
        assert len(toolsets) == 1
        assert set(toolsets[0]._skills.keys()) == {"skill-surviving"}

        # A WARNING log was emitted for the failed skill
        skipped_records = [
            r
            for r in caplog.records
            if r.levelname == "WARNING" and "skill_load_skipped" in r.getMessage()
        ]
        assert len(skipped_records) == 1
        # Extra fields are stored as record attributes, not in getMessage()
        assert getattr(skipped_records[0], "skill_id", None) == "id-bad"

    def test_skill_corrupt_error_is_also_tolerated(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        from google.adk.tools.skill_toolset import SkillToolset

        skill_ok = _make_adk_skill("skill-ok")
        fake_loader = _make_fake_loader_module(
            skills_by_id={"id-ok": skill_ok},
            raise_for_ids={"id-corrupt": _SkillCorruptError},
        )
        monkeypatch.setitem(sys.modules, "kene_api.services.skill_loader", fake_loader)

        config = _make_config(skill_ids=["id-ok", "id-corrupt"])

        with caplog.at_level(logging.WARNING):
            agent = _build_with_skills(config, name="corrupt_test", account_id="acc_c")

        toolsets = [t for t in agent.tools if isinstance(t, SkillToolset)]
        assert len(toolsets) == 1
        assert "skill-ok" in toolsets[0]._skills


class TestAC2aAllSkillsFail:
    """AC-2a: All skills fail → no SkillToolset, ERROR log, failure marker set."""

    def test_all_skills_fail_build_still_succeeds(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        from google.adk.tools.skill_toolset import SkillToolset

        fake_loader = _make_fake_loader_module(
            raise_for_ids={
                "id-a": _SkillNotFoundError,
                "id-b": _SkillNotFoundError,
            }
        )
        monkeypatch.setitem(sys.modules, "kene_api.services.skill_loader", fake_loader)

        config = _make_config(skill_ids=["id-a", "id-b"])

        with caplog.at_level(logging.ERROR):
            agent = _build_with_skills(config, name="all_fail", account_id="acc_fail")

        # Build did NOT raise
        assert agent is not None

        # No SkillToolset attached
        toolsets = [t for t in agent.tools if isinstance(t, SkillToolset)]
        assert toolsets == [], "No SkillToolset should be attached on total failure"

        # Exactly one ERROR-level total-failure log
        error_records = [
            r
            for r in caplog.records
            if r.levelname == "ERROR" and "skill_load_total_failure" in r.getMessage()
        ]
        assert len(error_records) == 1
        # Extra fields are stored as record attributes, not in getMessage()
        rec = error_records[0]
        assert getattr(rec, "account_id", None) == "acc_fail"
        assert set(getattr(rec, "skill_ids", [])) == {"id-a", "id-b"}

    def test_failure_marker_set_on_agent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_loader = _make_fake_loader_module(
            raise_for_ids={"id-only": _SkillNotFoundError}
        )
        monkeypatch.setitem(sys.modules, "kene_api.services.skill_loader", fake_loader)

        config = _make_config(skill_ids=["id-only"])
        agent = _build_with_skills(config, name="marker", account_id="acc_m")

        from app.adk.agents.agent_factory.skill_metadata import (
            get_skill_build_metadata,
        )

        assert get_skill_build_metadata(agent).get("skill_load_total_failure") is True

    def test_no_failure_marker_when_skills_load_ok(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_loader = _make_fake_loader_module(
            skills_by_id={"id-ok": _make_adk_skill("skill-ok")}
        )
        monkeypatch.setitem(sys.modules, "kene_api.services.skill_loader", fake_loader)

        config = _make_config(skill_ids=["id-ok"])
        agent = _build_with_skills(config, name="no_marker", account_id="acc_nm")

        from app.adk.agents.agent_factory.skill_metadata import (
            get_skill_build_metadata,
        )

        assert not get_skill_build_metadata(agent).get("skill_load_total_failure")

    def test_error_log_includes_account_config_and_skill_ids(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        fake_loader = _make_fake_loader_module(
            raise_for_ids={"sk-1": _SkillNotFoundError, "sk-2": _SkillCorruptError}
        )
        monkeypatch.setitem(sys.modules, "kene_api.services.skill_loader", fake_loader)

        config = _make_config(skill_ids=["sk-1", "sk-2"])

        with caplog.at_level(logging.ERROR):
            _build_with_skills(
                config,
                name="log_check",
                account_id="acc_log_check",
                config_doc_id="cfg_doc_123",
            )

        error_records = [
            r
            for r in caplog.records
            if r.levelname == "ERROR" and "skill_load_total_failure" in r.getMessage()
        ]
        assert error_records, "Expected at least one ERROR log"
        # Extra fields are stored as record attributes, not in getMessage()
        rec = error_records[0]
        assert getattr(rec, "account_id", None) == "acc_log_check"
        assert getattr(rec, "config_id", None) == "cfg_doc_123"


class TestAC3EmptySkillList:
    """AC-3: skill_ids=[] → no SkillToolset, tools list unchanged."""

    def test_empty_skill_ids_no_skill_toolset(self) -> None:
        from google.adk.tools.skill_toolset import SkillToolset

        config = _make_config(skill_ids=[])
        # No fake loader needed — the helper should return early before importing
        # kene_api when skill_ids is empty.
        with (
            _PATCH_BEFORE_AGENT,
            _PATCH_AFTER_AGENT,
            _PATCH_BEFORE_TOOL,
            _PATCH_AFTER_TOOL,
        ):
            import app.adk.agents.agent_factory.builder as b

            agent = b.build_agent(config, name="no_skills", account_id="acc_empty")

        toolsets = [t for t in agent.tools if isinstance(t, SkillToolset)]
        assert toolsets == []

    def test_empty_skill_ids_no_failure_marker(self) -> None:
        config = _make_config(skill_ids=[])
        with (
            _PATCH_BEFORE_AGENT,
            _PATCH_AFTER_AGENT,
            _PATCH_BEFORE_TOOL,
            _PATCH_AFTER_TOOL,
        ):
            import app.adk.agents.agent_factory.builder as b

            agent = b.build_agent(config, name="no_skills_marker", account_id="acc_nm2")

        from app.adk.agents.agent_factory.skill_metadata import (
            get_skill_build_metadata,
        )

        assert get_skill_build_metadata(agent) == {}

    def test_empty_skill_ids_does_not_import_kene_api(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When skill_ids=[], the loader is never imported even if kene_api is absent."""
        # Remove any existing kene_api stub so that an import attempt would fail
        for key in list(sys.modules.keys()):
            if key.startswith("kene_api"):
                monkeypatch.delitem(sys.modules, key, raising=False)

        config = _make_config(skill_ids=[])
        with (
            _PATCH_BEFORE_AGENT,
            _PATCH_AFTER_AGENT,
            _PATCH_BEFORE_TOOL,
            _PATCH_AFTER_TOOL,
        ):
            import app.adk.agents.agent_factory.builder as b

            # Should succeed without kene_api installed
            agent = b.build_agent(config, name="no_import", account_id="acc_ni")

        assert agent is not None


class TestAccountIdNone:
    """When account_id=None and skill_ids is non-empty, skills are skipped (not a failure)."""

    def test_none_account_id_skips_skills_gracefully(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        from google.adk.tools.skill_toolset import SkillToolset

        # Provide a loader that would succeed if called — but it shouldn't be.
        fake_loader = _make_fake_loader_module(
            skills_by_id={"id-x": _make_adk_skill("skill-x")}
        )
        monkeypatch.setitem(sys.modules, "kene_api.services.skill_loader", fake_loader)

        config = _make_config(skill_ids=["id-x"])

        with caplog.at_level(logging.WARNING):
            agent = _build_with_skills(config, name="none_account", account_id=None)

        # No SkillToolset — skills are skipped when account_id is None
        toolsets = [t for t in agent.tools if isinstance(t, SkillToolset)]
        assert toolsets == []

        # Not treated as total failure — sidecar carries no failure marker
        from app.adk.agents.agent_factory.skill_metadata import (
            get_skill_build_metadata,
        )

        assert not get_skill_build_metadata(agent).get("skill_load_total_failure")

        # A WARNING (not ERROR) should have been emitted
        warn_records = [
            r
            for r in caplog.records
            if r.levelname == "WARNING"
            and "skill_toolset_skipped_no_account" in r.getMessage()
        ]
        assert len(warn_records) == 1


class TestDuplicateSkillNameDegrades:
    """When SkillToolset construction raises ValueError (duplicate names), treat as total failure."""

    def test_duplicate_skill_names_degrade_to_total_failure(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        from google.adk.tools.skill_toolset import SkillToolset

        # Both skill IDs resolve to skills with the SAME name — causes ValueError.
        skill_dup = _make_adk_skill("same-name")
        fake_loader = _make_fake_loader_module(
            skills_by_id={"id-1": skill_dup, "id-2": skill_dup}
        )
        monkeypatch.setitem(sys.modules, "kene_api.services.skill_loader", fake_loader)

        config = _make_config(skill_ids=["id-1", "id-2"])

        with caplog.at_level(logging.ERROR):
            agent = _build_with_skills(config, name="dup", account_id="acc_dup")

        # No SkillToolset — ValueError degrades to total failure
        toolsets = [t for t in agent.tools if isinstance(t, SkillToolset)]
        assert toolsets == []

        # Total failure marker set on sidecar
        from app.adk.agents.agent_factory.skill_metadata import (
            get_skill_build_metadata,
        )

        assert get_skill_build_metadata(agent).get("skill_load_total_failure") is True

        # ERROR log emitted
        error_msgs = [
            r.getMessage()
            for r in caplog.records
            if r.levelname == "ERROR" and "skill_load_total_failure" in r.getMessage()
        ]
        assert error_msgs


class TestSandboxWiring:
    """AC-4, AC-5: SandboxPool delegation and independence matrix for sandbox x skills."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_mock_pool(self) -> Any:
        """Return a MagicMock(spec=SandboxPool) whose get_or_create returns a BuiltInCodeExecutor.

        ``LlmAgent.code_executor`` is a Pydantic field typed as ``BaseCodeExecutor``, so
        the sentinel must be a real subclass instance — a plain ``object()`` fails validation.
        We use ``BuiltInCodeExecutor`` as the stand-in since it is a no-arg BaseCodeExecutor
        subclass already in the test environment.
        """
        from unittest.mock import AsyncMock, MagicMock

        from google.adk.code_executors import BuiltInCodeExecutor

        from app.adk.agents.agent_factory.sandbox_pool import SandboxPool

        pool = MagicMock(spec=SandboxPool)
        sentinel = BuiltInCodeExecutor()
        pool.get_or_create = AsyncMock(return_value=sentinel)
        pool._sentinel = sentinel
        return pool

    def _build(
        self,
        config: MergedAgentConfig,
        *,
        account_id: str | None,
        sandbox_pool: Any,
        monkeypatch: pytest.MonkeyPatch | None = None,
    ) -> Any:
        import app.adk.agents.agent_factory.builder as b

        kw: dict[str, Any] = {"account_id": account_id, "sandbox_pool": sandbox_pool}

        with _PATCH_BEFORE_AGENT, _PATCH_AFTER_AGENT, _PATCH_BEFORE_TOOL, _PATCH_AFTER_TOOL:
            return b.build_agent(config, name="test_agent", **kw)

    # ------------------------------------------------------------------
    # AC-4 — sandbox wiring
    # ------------------------------------------------------------------

    def test_sandbox_true_pool_called_once_with_correct_key(self) -> None:
        """sandbox=True → pool.get_or_create called with (account_id, name)."""
        pool = self._make_mock_pool()
        config = _make_config(sandbox_code_executor_enabled=True)

        agent = self._build(config, account_id="acc_test", sandbox_pool=pool)

        pool.get_or_create.assert_called_once_with(account_id="acc_test", config_id="test_agent")
        assert agent.code_executor is pool._sentinel

    def test_sandbox_false_pool_not_called(self) -> None:
        """sandbox=False → pool.get_or_create NOT called; code_executor is None."""
        pool = self._make_mock_pool()
        config = _make_config(sandbox_code_executor_enabled=False, code_execution_enabled=False)

        agent = self._build(config, account_id="acc_test", sandbox_pool=pool)

        pool.get_or_create.assert_not_called()
        assert agent.code_executor is None

    def test_sandbox_true_code_execution_true_sandbox_wins(self) -> None:
        """sandbox=True + code_execution_enabled=True → sandbox takes precedence."""
        pool = self._make_mock_pool()
        config = _make_config(
            sandbox_code_executor_enabled=True,
            code_execution_enabled=True,
        )

        agent = self._build(config, account_id="acc_both", sandbox_pool=pool)

        pool.get_or_create.assert_called_once()
        assert agent.code_executor is pool._sentinel

    @pytest.mark.parametrize("code_execution_enabled", [False, True])
    def test_sandbox_true_account_id_none_returns_none_no_fallback(
        self, code_execution_enabled: bool, caplog: pytest.LogCaptureFixture
    ) -> None:
        """sandbox=True + account_id=None → None regardless of code_execution_enabled.

        When sandbox_code_executor_enabled=True and account_id is None, the function
        MUST return None rather than falling through to BuiltInCodeExecutor.  Sandbox
        is a hard requirement: if it cannot be keyed, the agent has no code executor
        that turn.  Mirrors test_sandbox_build_timeout_returns_none_no_fallback.
        """
        import logging

        pool = self._make_mock_pool()
        config = _make_config(
            sandbox_code_executor_enabled=True,
            code_execution_enabled=code_execution_enabled,
        )

        with caplog.at_level(logging.WARNING):
            agent = self._build(config, account_id=None, sandbox_pool=pool)

        pool.get_or_create.assert_not_called()
        assert agent.code_executor is None

        warn_records = [
            r for r in caplog.records
            if r.levelname == "WARNING" and "sandbox_skipped_no_account" in r.getMessage()
        ]
        assert len(warn_records) == 1

    def test_sandbox_true_inside_running_loop(self) -> None:
        """sandbox=True works when build_agent is called inside a running event loop."""
        pool = self._make_mock_pool()
        config = _make_config(sandbox_code_executor_enabled=True)

        async def _run() -> Any:
            return self._build(config, account_id="acc_loop", sandbox_pool=pool)

        agent = asyncio.run(_run())

        pool.get_or_create.assert_called_once_with(account_id="acc_loop", config_id="test_agent")
        assert agent.code_executor is pool._sentinel

    # ------------------------------------------------------------------
    # AC-5 — 4-combination independence matrix (skills x sandbox)
    # ------------------------------------------------------------------

    def test_independence_skills_empty_sandbox_false(self) -> None:
        """Combination (skills=∅, sandbox=False): no SkillToolset, no sandbox executor."""
        from google.adk.tools.skill_toolset import SkillToolset

        pool = self._make_mock_pool()
        config = _make_config(skill_ids=[], sandbox_code_executor_enabled=False)

        with _PATCH_BEFORE_AGENT, _PATCH_AFTER_AGENT, _PATCH_BEFORE_TOOL, _PATCH_AFTER_TOOL:
            import app.adk.agents.agent_factory.builder as b
            agent = b.build_agent(config, name="combo_ff", account_id="acc_ff", sandbox_pool=pool)

        pool.get_or_create.assert_not_called()
        assert agent.code_executor is None
        toolsets = [t for t in agent.tools if isinstance(t, SkillToolset)]
        assert toolsets == []

    def test_independence_skills_empty_sandbox_true(self) -> None:
        """Combination (skills=∅, sandbox=True): no SkillToolset, but sandbox executor attached."""
        from google.adk.tools.skill_toolset import SkillToolset

        pool = self._make_mock_pool()
        config = _make_config(skill_ids=[], sandbox_code_executor_enabled=True)

        with _PATCH_BEFORE_AGENT, _PATCH_AFTER_AGENT, _PATCH_BEFORE_TOOL, _PATCH_AFTER_TOOL:
            import app.adk.agents.agent_factory.builder as b
            agent = b.build_agent(config, name="combo_ft", account_id="acc_ft", sandbox_pool=pool)

        pool.get_or_create.assert_called_once()
        assert agent.code_executor is pool._sentinel
        toolsets = [t for t in agent.tools if isinstance(t, SkillToolset)]
        assert toolsets == []

    def test_independence_skills_nonempty_sandbox_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Combination (skills=[id-a], sandbox=False): SkillToolset attached, no sandbox executor."""
        from google.adk.tools.skill_toolset import SkillToolset

        skill_a = _make_adk_skill("skill-combo-tf")
        fake_loader = _make_fake_loader_module(skills_by_id={"id-a": skill_a})
        monkeypatch.setitem(sys.modules, "kene_api.services.skill_loader", fake_loader)

        pool = self._make_mock_pool()
        config = _make_config(skill_ids=["id-a"], sandbox_code_executor_enabled=False)

        agent = _build_with_skills(config, name="combo_tf", account_id="acc_tf", sandbox_pool=pool)

        pool.get_or_create.assert_not_called()
        assert agent.code_executor is None
        toolsets = [t for t in agent.tools if isinstance(t, SkillToolset)]
        assert len(toolsets) == 1

    def test_independence_skills_nonempty_sandbox_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Combination (skills=[id-a], sandbox=True): both SkillToolset and sandbox executor attached."""
        from google.adk.tools.skill_toolset import SkillToolset

        skill_a = _make_adk_skill("skill-combo-tt")
        fake_loader = _make_fake_loader_module(skills_by_id={"id-a": skill_a})
        monkeypatch.setitem(sys.modules, "kene_api.services.skill_loader", fake_loader)

        pool = self._make_mock_pool()
        config = _make_config(skill_ids=["id-a"], sandbox_code_executor_enabled=True)

        agent = _build_with_skills(config, name="combo_tt", account_id="acc_tt", sandbox_pool=pool)

        pool.get_or_create.assert_called_once()
        assert agent.code_executor is pool._sentinel
        toolsets = [t for t in agent.tools if isinstance(t, SkillToolset)]
        assert len(toolsets) == 1

    # ------------------------------------------------------------------
    # AC-4 — timeout enforcement
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("code_execution_enabled", [False, True])
    def test_sandbox_build_timeout_returns_none_no_fallback(
        self,
        code_execution_enabled: bool,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Timeout returns None regardless of code_execution_enabled — no silent downgrade.

        When sandbox_code_executor_enabled=True and the pool's get_or_create exceeds
        the timeout, the function MUST return None rather than falling through to
        BuiltInCodeExecutor.  Sandbox is a hard requirement: if it cannot be built,
        the agent has no code executor that turn.  See DESIGN-REVIEW-LOG Review 36.
        """
        import logging

        import app.adk.agents.agent_factory.builder as b

        async def _slow_get_or_create(*, account_id: str, config_id: str) -> Any:
            await asyncio.sleep(5.0)  # well beyond the 0.05 s patched timeout
            return None

        pool = self._make_mock_pool()
        pool.get_or_create = _slow_get_or_create  # type: ignore[assignment]
        monkeypatch.setattr(b, "_SANDBOX_BUILD_TIMEOUT_SECONDS", 0.05)

        config = _make_config(
            sandbox_code_executor_enabled=True,
            code_execution_enabled=code_execution_enabled,
        )

        with caplog.at_level(logging.ERROR):
            agent = self._build(config, account_id="acc_to", sandbox_pool=pool)

        # Sandbox timeout must NOT fall through to BuiltInCodeExecutor, even
        # when code_execution_enabled=True — isolation guarantee is fail-closed.
        assert agent.code_executor is None

        timeout_records = [
            r for r in caplog.records
            if r.levelname == "ERROR" and "sandbox_build_timeout" in r.getMessage()
        ]
        assert len(timeout_records) == 1
        rec = timeout_records[0]
        assert getattr(rec, "account_id", None) == "acc_to"
        assert getattr(rec, "config_id", None) == "test_agent"
        assert getattr(rec, "timeout_s", None) == 0.05


class TestAsyncBridge:
    """build_agent must work when called from inside a running event loop.

    The original PR-#687 implementation degraded silently to ``None`` and
    logged ``skill_toolset_skipped_event_loop_conflict``.  The fix routes the
    async loader through a worker thread so callers in async contexts (future
    AH-PRD-09 per-turn rebuild, FastAPI handlers, async tests) still get
    skills loaded.
    """

    def test_build_agent_inside_running_loop_loads_skills(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from google.adk.tools.skill_toolset import SkillToolset

        skill = _make_adk_skill("skill-async")
        fake_loader = _make_fake_loader_module(skills_by_id={"id-a": skill})
        monkeypatch.setitem(sys.modules, "kene_api.services.skill_loader", fake_loader)

        config = _make_config(skill_ids=["id-a"])

        async def _run() -> Any:
            return _build_with_skills(config, name="in_loop", account_id="acc_loop")

        agent = asyncio.run(_run())

        toolsets = [t for t in agent.tools if isinstance(t, SkillToolset)]
        assert len(toolsets) == 1
        assert "skill-async" in toolsets[0]._skills

    def test_build_agent_inside_running_loop_no_event_loop_conflict_log(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The retired 'skill_toolset_skipped_event_loop_conflict' key must no longer fire."""
        import logging

        skill = _make_adk_skill("skill-async-ok")
        fake_loader = _make_fake_loader_module(skills_by_id={"id-a": skill})
        monkeypatch.setitem(sys.modules, "kene_api.services.skill_loader", fake_loader)

        config = _make_config(skill_ids=["id-a"])

        async def _run() -> Any:
            return _build_with_skills(config, name="in_loop2", account_id="acc_loop2")

        with caplog.at_level(logging.ERROR):
            asyncio.run(_run())

        conflict_records = [
            r
            for r in caplog.records
            if "skill_toolset_skipped_event_loop_conflict" in r.getMessage()
        ]
        assert conflict_records == [], (
            "Retired log key should not fire; bridge should route via worker thread"
        )

    def test_skill_toolset_load_timeout_logs_and_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Timeout in the worker-thread path logs an ERROR and yields no SkillToolset."""
        import logging

        from google.adk.tools.skill_toolset import SkillToolset

        import app.adk.agents.agent_factory.builder as b

        async def _slow_async(
            account_id: str, skill_ids: list[str], *, config_id: str | None
        ) -> Any:
            await asyncio.sleep(5.0)
            return None

        monkeypatch.setattr(b, "_build_skill_toolset_async", _slow_async)
        monkeypatch.setattr(b, "_SKILL_LOAD_TIMEOUT_SECONDS", 0.05)

        config = _make_config(skill_ids=["id-slow"])

        async def _run() -> Any:
            return _build_with_skills(config, name="timeout", account_id="acc_to")

        with caplog.at_level(logging.ERROR):
            agent = asyncio.run(_run())

        toolsets = [t for t in agent.tools if isinstance(t, SkillToolset)]
        assert toolsets == []

        timeout_records = [
            r for r in caplog.records if "skill_toolset_load_timeout" in r.getMessage()
        ]
        assert len(timeout_records) == 1
        rec = timeout_records[0]
        assert getattr(rec, "account_id", None) == "acc_to"
        assert getattr(rec, "timeout_s", None) == 0.05

        # Sidecar surfaces the timeout to SK-27 so ops can distinguish "infra
        # slow" from skill_load_total_failure (which has different remediation).
        from app.adk.agents.agent_factory.skill_metadata import (
            get_skill_build_metadata,
        )

        metadata = get_skill_build_metadata(agent)
        assert metadata.get("skill_load_timeout") is True
        # Timeout is NOT a total failure — those two markers are exclusive.
        assert "skill_load_total_failure" not in metadata


class TestSkillNameIndex:
    """SK-27: skill_name_index sidecar records skill metadata for span callbacks."""

    def _make_skill_with_tools(self, name: str, allowed_tools: str | None = None) -> Any:
        from google.adk.skills import models

        return models.Skill(
            frontmatter=models.Frontmatter(
                name=name,
                description=f"Skill {name}",
                allowed_tools=allowed_tools,
            ),
            instructions=f"# {name}\nDo things.",
        )

    def test_skill_name_index_recorded_for_two_skills(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        skill_a = _make_adk_skill("alpha")
        skill_b = _make_adk_skill("beta")
        fake_loader = _make_fake_loader_module(
            skills_by_id={"id-alpha": skill_a, "id-beta": skill_b}
        )
        monkeypatch.setitem(sys.modules, "kene_api.services.skill_loader", fake_loader)

        config = _make_config(skill_ids=["id-alpha", "id-beta"])
        agent = _build_with_skills(config, name="index_two", account_id="acc_idx")

        from app.adk.agents.agent_factory.skill_metadata import get_skill_build_metadata

        meta = get_skill_build_metadata(agent)
        idx = meta.get("skill_name_index", {})

        assert set(idx.keys()) == {"alpha", "beta"}
        assert idx["alpha"]["skill_id"] == "id-alpha"
        assert idx["beta"]["skill_id"] == "id-beta"

    def test_skill_name_index_contains_required_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        skill = _make_adk_skill("my-skill")
        fake_loader = _make_fake_loader_module(skills_by_id={"id-ms": skill})
        monkeypatch.setitem(sys.modules, "kene_api.services.skill_loader", fake_loader)

        config = _make_config(skill_ids=["id-ms"])
        agent = _build_with_skills(config, name="index_fields", account_id="acc_f")

        from app.adk.agents.agent_factory.skill_metadata import get_skill_build_metadata

        meta = get_skill_build_metadata(agent)
        entry = meta["skill_name_index"]["my-skill"]

        assert entry["skill_id"] == "id-ms"
        assert "version" in entry
        assert "allowed_tools" in entry

    def test_skill_name_index_propagates_allowed_tools(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        skill = self._make_skill_with_tools("restricted", allowed_tools="Read Write")
        fake_loader = _make_fake_loader_module(skills_by_id={"id-r": skill})
        monkeypatch.setitem(sys.modules, "kene_api.services.skill_loader", fake_loader)

        config = _make_config(skill_ids=["id-r"])
        agent = _build_with_skills(config, name="index_at", account_id="acc_at")

        from app.adk.agents.agent_factory.skill_metadata import get_skill_build_metadata

        meta = get_skill_build_metadata(agent)
        entry = meta["skill_name_index"]["restricted"]
        assert entry["allowed_tools"] == "Read Write"

    def test_skill_name_index_excludes_failed_skills(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        skill_ok = _make_adk_skill("ok-skill")
        fake_loader = _make_fake_loader_module(
            skills_by_id={"id-ok": skill_ok},
            raise_for_ids={"id-bad": _SkillNotFoundError},
        )
        monkeypatch.setitem(sys.modules, "kene_api.services.skill_loader", fake_loader)

        config = _make_config(skill_ids=["id-ok", "id-bad"])
        agent = _build_with_skills(config, name="index_partial", account_id="acc_p")

        from app.adk.agents.agent_factory.skill_metadata import get_skill_build_metadata

        meta = get_skill_build_metadata(agent)
        idx = meta.get("skill_name_index", {})

        assert "ok-skill" in idx
        # No entry for the failed skill id
        for entry in idx.values():
            assert entry["skill_id"] != "id-bad"

    def test_skill_name_index_empty_when_all_skills_fail(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_loader = _make_fake_loader_module(
            raise_for_ids={"id-x": _SkillNotFoundError}
        )
        monkeypatch.setitem(sys.modules, "kene_api.services.skill_loader", fake_loader)

        config = _make_config(skill_ids=["id-x"])
        agent = _build_with_skills(config, name="index_total_fail", account_id="acc_tf")

        from app.adk.agents.agent_factory.skill_metadata import get_skill_build_metadata

        meta = get_skill_build_metadata(agent)
        # skill_name_index absent or empty on total failure
        assert not meta.get("skill_name_index")

    def test_skill_name_index_not_recorded_for_empty_skill_ids(self) -> None:
        config = _make_config(skill_ids=[])
        with _PATCH_BEFORE_AGENT, _PATCH_AFTER_AGENT, _PATCH_BEFORE_TOOL, _PATCH_AFTER_TOOL:
            import app.adk.agents.agent_factory.builder as b

            agent = b.build_agent(config, name="index_empty", account_id="acc_ei")

        from app.adk.agents.agent_factory.skill_metadata import get_skill_build_metadata

        assert "skill_name_index" not in get_skill_build_metadata(agent)
