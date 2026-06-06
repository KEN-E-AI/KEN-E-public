"""Tests for app.adk.tracking.skill_spans (SK-PRD-02 §4 / SK-27 / SK-38)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import app.adk.tracking.skill_spans as skill_spans
from app.adk.tracking.skill_spans import (
    _skill_ctx_registry,
    assert_skill_tool_names_match,
    skill_spans_after_tool_callback,
    skill_spans_before_agent_callback,
    skill_spans_before_tool_callback,
)

_GET_CLIENT_PATH = "app.adk.tracking.skill_spans._weave_get_client"
_CALL_CTX_PATH = "app.adk.tracking.skill_spans._weave_call_context"


# ---------------------------------------------------------------------------
# Minimal fakes
# ---------------------------------------------------------------------------


class _SimpleState(dict):
    """dict subclass so hasattr(state, 'get') and state['x'] = v both work."""


@dataclass
class _FakeIC:
    """Minimal invocation_context with an agent attribute."""

    agent: Any = None


@dataclass
class _FakeCallbackContext:
    state: Any = field(default_factory=_SimpleState)
    _invocation_context: Any = field(default_factory=_FakeIC)


@dataclass
class _FakeToolContext:
    state: Any = field(default_factory=_SimpleState)
    _invocation_context: Any = field(default_factory=_FakeIC)
    function_call_id: str | None = "default-call-id"


@dataclass
class _FakeTool:
    name: str


def _make_agent_with_meta(**meta_kwargs: Any) -> Any:
    """Return a mock LlmAgent whose sidecar has the given metadata."""
    agent = MagicMock()
    # Patch get_skill_build_metadata to return meta_kwargs for this agent.
    return agent, meta_kwargs


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_skill_ctx():
    _skill_ctx_registry.set(None)
    yield
    _skill_ctx_registry.set(None)


# ---------------------------------------------------------------------------
# skill_spans_before_agent_callback
# ---------------------------------------------------------------------------


class TestBeforeAgentCallback:
    """Tests for skill_spans_before_agent_callback."""

    def _make_ctx(self, meta: dict | None = None, account_id: str = "acc_1"):
        agent = MagicMock()
        ic = _FakeIC(agent=agent)
        state = _SimpleState({"account_id": account_id})
        ctx = _FakeCallbackContext(state=state, _invocation_context=ic)
        return ctx, agent, meta or {}

    def test_seeds_skills_allowed_tools_in_state(self):
        skill_name_index = {
            "my-skill": {
                "skill_id": "sk_1",
                "version": 0,
                "allowed_tools": "Read Write",
            }
        }
        ctx, _agent, _ = self._make_ctx()
        with patch(
            "app.adk.agents.agent_factory.skill_metadata.get_skill_build_metadata",
            return_value={"skill_name_index": skill_name_index},
        ):
            result = skill_spans_before_agent_callback(ctx)

        assert result is None
        skills_map = ctx.state.get("skills_allowed_tools")
        assert skills_map is not None
        assert "sk_1" in skills_map
        assert skills_map["sk_1"] == {"Read", "Write"}

    def test_seeds_none_when_skill_has_no_allowed_tools(self):
        skill_name_index = {
            "my-skill": {
                "skill_id": "sk_2",
                "version": 0,
                "allowed_tools": None,
            }
        }
        ctx, _, _ = self._make_ctx()
        with patch(
            "app.adk.agents.agent_factory.skill_metadata.get_skill_build_metadata",
            return_value={"skill_name_index": skill_name_index},
        ):
            skill_spans_before_agent_callback(ctx)

        assert ctx.state["skills_allowed_tools"]["sk_2"] is None

    def test_clears_active_skill_id_at_turn_start(self):
        ctx, _, _ = self._make_ctx()
        ctx.state["active_skill_id"] = "stale_id"
        with patch(
            "app.adk.agents.agent_factory.skill_metadata.get_skill_build_metadata",
            return_value={},
        ):
            skill_spans_before_agent_callback(ctx)

        assert ctx.state["active_skill_id"] is None

    def test_emits_total_failure_span_when_flagged(self):
        ctx, _, _ = self._make_ctx()
        mock_call = MagicMock(id="fail-call-1")
        mock_client = MagicMock()
        mock_client.create_call.return_value = mock_call

        with (
            patch(
                "app.adk.agents.agent_factory.skill_metadata.get_skill_build_metadata",
                return_value={"skill_load_total_failure": True},
            ),
            patch(_GET_CLIENT_PATH, return_value=mock_client),
            patch(_CALL_CTX_PATH) as mock_ctx,
        ):
            skill_spans_before_agent_callback(ctx)

        attrs = mock_client.create_call.call_args.kwargs["attributes"]
        assert attrs["account_id"] == "acc_1"
        assert attrs["skill_count"] == 0
        assert attrs["skill_ids"] == []
        assert attrs["skill_owner_type"] == "account"
        assert attrs.get("skill_load_total_failure") is True
        mock_client.finish_call.assert_called_once_with(
            mock_call, output={"status": "degraded"}
        )
        mock_ctx.pop_call.assert_called_once_with("fail-call-1")

    def test_noop_when_no_agent_in_invocation_context(self):
        state = _SimpleState()
        ctx = _FakeCallbackContext(state=state, _invocation_context=None)
        # Should not raise
        result = skill_spans_before_agent_callback(ctx)
        assert result is None

    def test_degrades_open_on_exception(self):
        ctx, _, _ = self._make_ctx()
        with patch(
            "app.adk.agents.agent_factory.skill_metadata.get_skill_build_metadata",
            side_effect=RuntimeError("boom"),
        ):
            result = skill_spans_before_agent_callback(ctx)

        assert result is None

    def test_emits_timeout_span_when_skill_load_timeout_flagged(self):
        ctx, _, _ = self._make_ctx()
        mock_call = MagicMock(id="timeout-call-1")
        mock_client = MagicMock()
        mock_client.create_call.return_value = mock_call

        with (
            patch(
                "app.adk.agents.agent_factory.skill_metadata.get_skill_build_metadata",
                return_value={"skill_load_timeout": True},
            ),
            patch(_GET_CLIENT_PATH, return_value=mock_client),
            patch(_CALL_CTX_PATH),
        ):
            skill_spans_before_agent_callback(ctx)

        attrs = mock_client.create_call.call_args.kwargs["attributes"]
        assert attrs.get("skill_load_timeout") is True
        assert attrs["skill_count"] == 0
        assert attrs["skill_owner_type"] == "account"
        mock_client.finish_call.assert_called_once_with(
            mock_call, output={"status": "degraded"}
        )

    def test_failure_span_emitted_only_once_across_turns(self):
        """_skill_failure_span_emitted guard prevents re-emission on turn 2+."""
        ctx, _, _ = self._make_ctx()
        mock_client = MagicMock()
        mock_client.create_call.return_value = MagicMock(id="once-call-1")

        meta_patch = patch(
            "app.adk.agents.agent_factory.skill_metadata.get_skill_build_metadata",
            return_value={"skill_load_total_failure": True},
        )
        client_patch = patch(_GET_CLIENT_PATH, return_value=mock_client)
        call_ctx_patch = patch(_CALL_CTX_PATH)

        with meta_patch, client_patch, call_ctx_patch:
            skill_spans_before_agent_callback(ctx)  # turn 1 — should emit
            skill_spans_before_agent_callback(ctx)  # turn 2 — should NOT re-emit

        assert mock_client.create_call.call_count == 1


# ---------------------------------------------------------------------------
# skill_spans_before_tool_callback
# ---------------------------------------------------------------------------


class TestBeforeToolCallback:
    """Tests for skill_spans_before_tool_callback."""

    def _make_tool_ctx(self, account_id: str = "acc_t"):
        agent = MagicMock()
        ic = _FakeIC(agent=agent)
        state = _SimpleState({"account_id": account_id})
        return _FakeToolContext(state=state, _invocation_context=ic), agent

    @pytest.mark.asyncio
    async def test_noop_for_non_skill_tool(self):
        ctx, _ = self._make_tool_ctx()
        mock_client = MagicMock()
        with patch(_GET_CLIENT_PATH, return_value=mock_client):
            result = await skill_spans_before_tool_callback(
                tool=_FakeTool("search_web"),
                args={},
                tool_context=ctx,
            )
        assert result is None
        mock_client.create_call.assert_not_called()
        assert not (_skill_ctx_registry.get() or {})

    @pytest.mark.asyncio
    async def test_opens_list_skills_span(self):
        ctx, _ = self._make_tool_ctx()
        mock_call = MagicMock(id="list-call-1")
        mock_client = MagicMock()
        mock_client.create_call.return_value = mock_call
        skill_name_index = {
            "skill-a": {"skill_id": "sk_a", "version": 1, "allowed_tools": None},
            "skill-b": {"skill_id": "sk_b", "version": 1, "allowed_tools": None},
        }
        with (
            patch(
                "app.adk.agents.agent_factory.skill_metadata.get_skill_build_metadata",
                return_value={"skill_name_index": skill_name_index},
            ),
            patch(_GET_CLIENT_PATH, return_value=mock_client),
        ):
            result = await skill_spans_before_tool_callback(
                tool=_FakeTool("list_skills"),
                args={},
                tool_context=ctx,
            )

        assert result is None
        create_kwargs = mock_client.create_call.call_args
        assert create_kwargs.kwargs["op"] == "skill.list"
        assert create_kwargs.kwargs["attributes"]["account_id"] == "acc_t"
        assert create_kwargs.kwargs["attributes"]["skill_count"] == 2
        assert set(create_kwargs.kwargs["attributes"]["skill_ids"]) == {"sk_a", "sk_b"}
        assert create_kwargs.kwargs["attributes"]["skill_owner_type"] == "account"
        registry = _skill_ctx_registry.get()
        saved = registry.get(ctx.function_call_id)
        assert saved is not None
        assert saved["call"] is mock_call

    @pytest.mark.asyncio
    async def test_opens_load_skill_span_with_resolved_skill_id(self):
        ctx, _ = self._make_tool_ctx()
        mock_call = MagicMock(id="load-call-1")
        mock_client = MagicMock()
        mock_client.create_call.return_value = mock_call
        skill_name_index = {
            "seo-checklist": {
                "skill_id": "sk_seo",
                "version": 2,
                "allowed_tools": "Read",
            }
        }
        with (
            patch(
                "app.adk.agents.agent_factory.skill_metadata.get_skill_build_metadata",
                return_value={"skill_name_index": skill_name_index},
            ),
            patch(_GET_CLIENT_PATH, return_value=mock_client),
        ):
            result = await skill_spans_before_tool_callback(
                tool=_FakeTool("load_skill"),
                args={"name": "seo-checklist"},
                tool_context=ctx,
            )

        assert result is None
        attrs = mock_client.create_call.call_args.kwargs["attributes"]
        assert attrs["skill_id"] == "sk_seo"
        assert attrs["skill_name"] == "seo-checklist"
        assert attrs["skill_version"] == 2
        assert attrs["skill_owner_type"] == "account"
        registry = _skill_ctx_registry.get()
        saved = registry.get(ctx.function_call_id)
        assert saved is not None
        assert saved["skill_id"] == "sk_seo"

    @pytest.mark.asyncio
    async def test_opens_load_skill_resource_span(self):
        ctx, _ = self._make_tool_ctx()
        mock_call = MagicMock(id="res-call-1")
        mock_client = MagicMock()
        mock_client.create_call.return_value = mock_call
        skill_name_index = {
            "my-skill": {"skill_id": "sk_r", "version": 0, "allowed_tools": None}
        }
        with (
            patch(
                "app.adk.agents.agent_factory.skill_metadata.get_skill_build_metadata",
                return_value={"skill_name_index": skill_name_index},
            ),
            patch(_GET_CLIENT_PATH, return_value=mock_client),
        ):
            result = await skill_spans_before_tool_callback(
                tool=_FakeTool("load_skill_resource"),
                args={"skill_name": "my-skill", "path": "data/template.md"},
                tool_context=ctx,
            )

        assert result is None
        assert mock_client.create_call.call_args.kwargs["op"] == "skill.load_resource"
        attrs = mock_client.create_call.call_args.kwargs["attributes"]
        assert attrs["skill_id"] == "sk_r"
        assert attrs["rel_path"] == "data/template.md"
        assert attrs["skill_owner_type"] == "account"

    @pytest.mark.asyncio
    async def test_noop_when_client_is_none(self):
        ctx, _ = self._make_tool_ctx()
        with (
            patch(
                "app.adk.agents.agent_factory.skill_metadata.get_skill_build_metadata",
                return_value={},
            ),
            patch(_GET_CLIENT_PATH, return_value=None),
        ):
            result = await skill_spans_before_tool_callback(
                tool=_FakeTool("list_skills"),
                args={},
                tool_context=ctx,
            )
        assert result is None
        assert not (_skill_ctx_registry.get() or {})

    @pytest.mark.asyncio
    async def test_degrades_open_on_exception(self):
        ctx, _ = self._make_tool_ctx()
        with patch(
            "app.adk.agents.agent_factory.skill_metadata.get_skill_build_metadata",
            side_effect=RuntimeError("sidecar broken"),
        ):
            result = await skill_spans_before_tool_callback(
                tool=_FakeTool("load_skill"),
                args={"name": "boom"},
                tool_context=ctx,
            )
        assert result is None


# ---------------------------------------------------------------------------
# skill_spans_after_tool_callback
# ---------------------------------------------------------------------------


class TestAfterToolCallback:
    """Tests for skill_spans_after_tool_callback."""

    def _make_tool_ctx(self, account_id: str = "acc_a"):
        state = _SimpleState({"account_id": account_id})
        return _FakeToolContext(state=state)

    @pytest.mark.asyncio
    async def test_noop_for_non_skill_tool(self):
        ctx = self._make_tool_ctx()
        mock_client = MagicMock()
        with patch(_GET_CLIENT_PATH, return_value=mock_client):
            result = await skill_spans_after_tool_callback(
                tool=_FakeTool("search_web"),
                args={},
                tool_context=ctx,
                tool_response={},
            )
        assert result is None
        mock_client.finish_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_noop_when_no_in_flight_call(self):
        ctx = self._make_tool_ctx()
        # Registry is empty (autouse fixture cleared it) — no in-flight call.
        mock_client = MagicMock()
        with patch(_GET_CLIENT_PATH, return_value=mock_client):
            result = await skill_spans_after_tool_callback(
                tool=_FakeTool("list_skills"),
                args={},
                tool_context=ctx,
                tool_response={},
            )
        assert result is None
        mock_client.finish_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_finishes_list_skills_span(self):
        ctx = self._make_tool_ctx()
        mock_call = MagicMock(id="list-finish-1")
        _skill_ctx_registry.set(
            {ctx.function_call_id: {"call": mock_call, "skill_id": None}}
        )

        mock_client = MagicMock()
        with (
            patch(_GET_CLIENT_PATH, return_value=mock_client),
            patch(_CALL_CTX_PATH) as mock_ctx,
        ):
            result = await skill_spans_after_tool_callback(
                tool=_FakeTool("list_skills"),
                args={},
                tool_context=ctx,
                tool_response={"skills": []},
            )

        assert result is None
        mock_client.finish_call.assert_called_once()
        mock_ctx.pop_call.assert_called_once_with("list-finish-1")
        assert not (_skill_ctx_registry.get() or {})

    @pytest.mark.asyncio
    async def test_load_skill_sets_active_skill_id_on_success(self):
        ctx = self._make_tool_ctx()
        mock_call = MagicMock(id="load-finish-1")
        _skill_ctx_registry.set(
            {ctx.function_call_id: {"call": mock_call, "skill_id": "sk_loaded"}}
        )

        mock_client = MagicMock()
        instructions = "# My Skill\nDo stuff."
        with (
            patch(_GET_CLIENT_PATH, return_value=mock_client),
            patch(_CALL_CTX_PATH),
        ):
            await skill_spans_after_tool_callback(
                tool=_FakeTool("load_skill"),
                args={"name": "my-skill"},
                tool_context=ctx,
                tool_response={"instructions": instructions},
            )

        assert ctx.state["active_skill_id"] == "sk_loaded"
        finish_output = mock_client.finish_call.call_args.kwargs["output"]
        assert finish_output["instruction_bytes"] == len(instructions.encode("utf-8"))

    @pytest.mark.asyncio
    async def test_load_skill_does_not_set_active_skill_id_on_error(self):
        ctx = self._make_tool_ctx()
        mock_call = MagicMock(id="load-err-1")
        _skill_ctx_registry.set(
            {ctx.function_call_id: {"call": mock_call, "skill_id": "sk_should_not_set"}}
        )

        mock_client = MagicMock()
        with (
            patch(_GET_CLIENT_PATH, return_value=mock_client),
            patch(_CALL_CTX_PATH),
        ):
            await skill_spans_after_tool_callback(
                tool=_FakeTool("load_skill"),
                args={"name": "bad-skill"},
                tool_context=ctx,
                tool_response={"error": "skill_not_found", "message": "Not found"},
            )

        assert ctx.state.get("active_skill_id") is None

    @pytest.mark.asyncio
    async def test_load_skill_resource_records_resource_bytes(self):
        ctx = self._make_tool_ctx()
        mock_call = MagicMock(id="res-finish-1")
        _skill_ctx_registry.set(
            {ctx.function_call_id: {"call": mock_call, "skill_id": "sk_res"}}
        )

        mock_client = MagicMock()
        content = "# Template\nThis is the resource content."
        with (
            patch(_GET_CLIENT_PATH, return_value=mock_client),
            patch(_CALL_CTX_PATH),
        ):
            await skill_spans_after_tool_callback(
                tool=_FakeTool("load_skill_resource"),
                args={"skill_name": "my-skill", "path": "template.md"},
                tool_context=ctx,
                tool_response={"content": content},
            )

        finish_output = mock_client.finish_call.call_args.kwargs["output"]
        assert finish_output["resource_bytes"] == len(content.encode("utf-8"))

    @pytest.mark.asyncio
    async def test_clears_registry_entry_on_exception(self):
        ctx = self._make_tool_ctx()
        mock_call = MagicMock(id="ex-call-1")
        _skill_ctx_registry.set(
            {ctx.function_call_id: {"call": mock_call, "skill_id": "sk_x"}}
        )

        mock_client = MagicMock()
        mock_client.finish_call.side_effect = RuntimeError("weave down")
        with (
            patch(_GET_CLIENT_PATH, return_value=mock_client),
            patch(_CALL_CTX_PATH),
        ):
            result = await skill_spans_after_tool_callback(
                tool=_FakeTool("load_skill"),
                args={"name": "some-skill"},
                tool_context=ctx,
                tool_response={"instructions": "hi"},
            )

        assert result is None
        assert not (_skill_ctx_registry.get() or {})


# ---------------------------------------------------------------------------
# assert_skill_tool_names_match
# ---------------------------------------------------------------------------


class TestAssertSkillToolNamesMatch:
    """Tests for assert_skill_tool_names_match (SK-40).

    assert_skill_tool_names_match is async (uses ``await toolset.get_tools()``
    per ADK 2.0 API).  Each test drives it via ``asyncio.run()``.
    The check is a subset: all three expected names must be present.  Allowlisted
    extras (``run_skill_script``) pass silently; an unknown extra tool logs a
    WARNING (but does not raise) so it surfaces rather than slipping through
    untraced.
    """

    @pytest.fixture(autouse=True)
    def _reset_verified_flag(self):
        """Reset the module-level verified flag before and after each test."""
        skill_spans._skill_tool_names_verified = False
        yield
        skill_spans._skill_tool_names_verified = False

    def _make_toolset(self, *names: str) -> Any:
        """Return a fake toolset with an async ``get_tools()`` method."""
        tool_list = [_FakeTool(n) for n in names]

        class _FakeToolset:
            async def get_tools(self, _ctx: Any = None) -> list:
                return tool_list

        return _FakeToolset()

    @pytest.mark.asyncio
    async def test_happy_path_no_raise_and_flag_set(self):
        """Exact match of the three expected names → no raise; flag flips True."""
        ts = self._make_toolset("list_skills", "load_skill", "load_skill_resource")
        await assert_skill_tool_names_match(ts)
        assert skill_spans._skill_tool_names_verified is True

    @pytest.mark.asyncio
    async def test_allowlisted_extra_tool_tolerated_without_warning(self, caplog: Any):
        """ADK 2.0's run_skill_script is allowlisted → no raise and no WARNING."""
        ts = self._make_toolset(
            "list_skills", "load_skill", "load_skill_resource", "run_skill_script"
        )
        with caplog.at_level(logging.WARNING, logger="app.adk.tracking.skill_spans"):
            await assert_skill_tool_names_match(ts)
        assert skill_spans._skill_tool_names_verified is True
        assert [r for r in caplog.records if r.levelno == logging.WARNING] == []

    @pytest.mark.asyncio
    async def test_unknown_extra_tool_warns_but_does_not_raise(self, caplog: Any):
        """An un-allowlisted extra tool → no raise, flag set, exactly one WARNING."""
        ts = self._make_toolset(
            "list_skills", "load_skill", "load_skill_resource", "mystery_tool"
        )
        with caplog.at_level(logging.WARNING, logger="app.adk.tracking.skill_spans"):
            await assert_skill_tool_names_match(ts)
        assert skill_spans._skill_tool_names_verified is True
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert "skill_toolset_unexpected_tools" in warnings[0].getMessage()

    @pytest.mark.asyncio
    async def test_cached_after_first_success(self):
        """Second call with a broken toolset is skipped when flag is already True."""
        ts = self._make_toolset("list_skills", "load_skill", "load_skill_resource")
        await assert_skill_tool_names_match(ts)
        assert skill_spans._skill_tool_names_verified is True

        # Construct a toolset whose get_tools() raises — if the flag is not
        # short-circuiting, this would either log an error or raise RuntimeError.
        class _BrokenToolset:
            async def get_tools(self, _ctx: Any = None) -> list:
                raise AttributeError("get_tools unavailable")

        await assert_skill_tool_names_match(_BrokenToolset())  # must not raise
        assert skill_spans._skill_tool_names_verified is True

    @pytest.mark.asyncio
    async def test_rename_detected_raises_runtime_error(self):
        """A renamed tool (list_skills → skills_list) must raise RuntimeError."""
        ts = self._make_toolset("skills_list", "load_skill", "load_skill_resource")
        with pytest.raises(RuntimeError) as exc_info:
            await assert_skill_tool_names_match(ts)
        msg = exc_info.value.args[0]
        assert "list_skills" in msg

    @pytest.mark.asyncio
    async def test_missing_tool_raises_runtime_error(self):
        """Toolset missing one tool → raises RuntimeError naming the absent tool."""
        ts = self._make_toolset("list_skills", "load_skill")
        with pytest.raises(RuntimeError) as exc_info:
            await assert_skill_tool_names_match(ts)
        assert "load_skill_resource" in exc_info.value.args[0]

    @pytest.mark.asyncio
    async def test_introspection_failure_logs_error_and_does_not_raise(
        self, caplog: Any
    ):
        """get_tools() raises → ERROR log; no raise; flag stays False."""

        class _BadToolset:
            async def get_tools(self, _ctx: Any = None) -> list:
                raise AttributeError("no tools here")

        with caplog.at_level(logging.ERROR, logger="app.adk.tracking.skill_spans"):
            await assert_skill_tool_names_match(_BadToolset())

        assert skill_spans._skill_tool_names_verified is False
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) == 1
        # Use getMessage() for compatibility with both stdlib and structlog adapters.
        assert "skill_tool_names_check_failed" in error_records[0].getMessage()

    @pytest.mark.asyncio
    async def test_introspection_failure_retries_on_next_call(self):
        """Flag stays False after an introspection failure → next build retries."""

        class _BadToolset:
            async def get_tools(self, _ctx: Any = None) -> list:
                raise AttributeError("still broken")

        await assert_skill_tool_names_match(_BadToolset())
        assert skill_spans._skill_tool_names_verified is False

        # Now supply a correct toolset — it should pass normally.
        good_ts = self._make_toolset("list_skills", "load_skill", "load_skill_resource")
        await assert_skill_tool_names_match(good_ts)
        assert skill_spans._skill_tool_names_verified is True


# ---------------------------------------------------------------------------
# SK-38 regression tests — concurrent dispatch + fallback path
# ---------------------------------------------------------------------------


class TestConcurrentDispatchAndFallback:
    """Regression tests added by SK-38.

    Verify that the per-call-ID registry correctly isolates interleaved
    before_tool / after_tool pairs within the same asyncio task, and that the
    fallback path fires (with a WARNING) when function_call_id is None.

    Note: the interleaved test runs sequentially within a single asyncio task.
    True cross-task concurrency is already isolated by ContextVar's per-task
    copy semantics; the bug scenario is intra-task interleaving (before_A →
    before_B → after_A → after_B), which the registry correctly handles.
    """

    def _make_tool_ctx_with_id(
        self, call_id: str | None, account_id: str = "acc_c"
    ) -> _FakeToolContext:
        state = _SimpleState({"account_id": account_id})
        ic = _FakeIC(agent=MagicMock())
        return _FakeToolContext(
            state=state, _invocation_context=ic, function_call_id=call_id
        )

    @pytest.mark.asyncio
    async def test_interleaved_before_after_pairs_no_cross_contamination(self):
        """Two interleaved load_skill invocations each close the correct span.

        Simulates the scenario where ADK calls before_tool for tool A and B
        sequentially (before either after_tool fires) within the SAME async
        task context — the latent bug the old single-slot ContextVar had.

        Ordering: before_A → before_B → after_A → after_B

        With the old single-slot approach, before_B would overwrite before_A's
        entry and after_A would close call_B instead of call_A.  The registry
        keyed by function_call_id eliminates this hazard.
        """
        call_a = MagicMock(id="interleaved-a")
        call_b = MagicMock(id="interleaved-b")

        # Both calls share a single mock client to keep the patch simple; we
        # distinguish which call was closed by the positional argument passed
        # to finish_call.
        mock_client = MagicMock()
        mock_client.create_call.side_effect = [call_a, call_b]

        ctx_a = self._make_tool_ctx_with_id("fn-call-id-A")
        ctx_b = self._make_tool_ctx_with_id("fn-call-id-B")

        skill_name_index = {
            "skill-a": {"skill_id": "sk_a", "version": 1, "allowed_tools": None},
            "skill-b": {"skill_id": "sk_b", "version": 2, "allowed_tools": None},
        }

        meta_patch = patch(
            "app.adk.agents.agent_factory.skill_metadata.get_skill_build_metadata",
            return_value={"skill_name_index": skill_name_index},
        )
        client_patch = patch(_GET_CLIENT_PATH, return_value=mock_client)
        call_ctx_patch = patch(_CALL_CTX_PATH)

        with meta_patch, client_patch, call_ctx_patch:
            # Phase 1: before_tool for A, then for B — no after_tool yet.
            await skill_spans_before_tool_callback(
                tool=_FakeTool("load_skill"),
                args={"name": "skill-a"},
                tool_context=ctx_a,
            )
            await skill_spans_before_tool_callback(
                tool=_FakeTool("load_skill"),
                args={"name": "skill-b"},
                tool_context=ctx_b,
            )

            # Both entries must be in the registry now.
            registry = _skill_ctx_registry.get()
            assert registry["fn-call-id-A"]["call"] is call_a
            assert registry["fn-call-id-B"]["call"] is call_b

            # Phase 2: after_tool for A first, then B.
            await skill_spans_after_tool_callback(
                tool=_FakeTool("load_skill"),
                args={"name": "skill-a"},
                tool_context=ctx_a,
                tool_response={"instructions": "instructions for A"},
            )
            # Only A's entry should have been popped.
            assert "fn-call-id-A" not in _skill_ctx_registry.get()
            assert "fn-call-id-B" in _skill_ctx_registry.get()

            await skill_spans_after_tool_callback(
                tool=_FakeTool("load_skill"),
                args={"name": "skill-b"},
                tool_context=ctx_b,
                tool_response={"instructions": "instructions for B"},
            )

        # finish_call was called twice; first call closed call_a, second closed call_b.
        assert mock_client.finish_call.call_count == 2
        first_closed = mock_client.finish_call.call_args_list[0].args[0]
        second_closed = mock_client.finish_call.call_args_list[1].args[0]
        assert first_closed is call_a
        assert second_closed is call_b

        # Registry is fully drained.
        assert not (_skill_ctx_registry.get() or {})

        # active_skill_id for each context was set to its own skill.
        assert ctx_a.state.get("active_skill_id") == "sk_a"
        assert ctx_b.state.get("active_skill_id") == "sk_b"

    @pytest.mark.asyncio
    async def test_fallback_to_single_slot_when_function_call_id_is_none(self, caplog):
        """When function_call_id is None, falls back to _single_slot key with a WARNING.

        Both before_tool and after_tool emit the WARNING.  The single-slot
        fallback replicates old behaviour and remains correct as long as
        dispatch is serialised (the expected case on ADK 1.27.5).
        """
        ctx = self._make_tool_ctx_with_id(call_id=None)
        mock_call = MagicMock(id="fallback-call-1")
        mock_client = MagicMock()
        mock_client.create_call.return_value = mock_call

        skill_name_index = {
            "my-skill": {"skill_id": "sk_fallback", "version": 1, "allowed_tools": None}
        }

        with caplog.at_level(logging.WARNING, logger="app.adk.tracking.skill_spans"):
            with (
                patch(
                    "app.adk.agents.agent_factory.skill_metadata.get_skill_build_metadata",
                    return_value={"skill_name_index": skill_name_index},
                ),
                patch(_GET_CLIENT_PATH, return_value=mock_client),
                patch(_CALL_CTX_PATH),
            ):
                await skill_spans_before_tool_callback(
                    tool=_FakeTool("load_skill"),
                    args={"name": "my-skill"},
                    tool_context=ctx,
                )

                # The entry is stored under the sentinel key after before_tool.
                registry = _skill_ctx_registry.get()
                assert "_single_slot" in registry
                assert registry["_single_slot"]["call"] is mock_call

                await skill_spans_after_tool_callback(
                    tool=_FakeTool("load_skill"),
                    args={"name": "my-skill"},
                    tool_context=ctx,
                    tool_response={"instructions": "fallback instructions"},
                )

        # Both before_tool and after_tool must have emitted the WARNING.
        warning_messages = [
            record.message
            for record in caplog.records
            if record.levelname == "WARNING"
            and "function_call_id is None" in record.message
        ]
        assert len(warning_messages) == 2

        mock_client.finish_call.assert_called_once()
        assert not (_skill_ctx_registry.get() or {})
