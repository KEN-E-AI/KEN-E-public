"""Tests for app.adk.tracking.skill_spans (SK-PRD-02 §4 / SK-27)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.adk.tracking.skill_spans import (
    _current_skill_ctx,
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
    _current_skill_ctx.set(None)
    yield
    _current_skill_ctx.set(None)


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
            "app.adk.tracking.skill_spans.get_skill_build_metadata",
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
            "app.adk.tracking.skill_spans.get_skill_build_metadata",
            return_value={"skill_name_index": skill_name_index},
        ):
            skill_spans_before_agent_callback(ctx)

        assert ctx.state["skills_allowed_tools"]["sk_2"] is None

    def test_clears_active_skill_id_at_turn_start(self):
        ctx, _, _ = self._make_ctx()
        ctx.state["active_skill_id"] = "stale_id"
        with patch(
            "app.adk.tracking.skill_spans.get_skill_build_metadata",
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
                "app.adk.tracking.skill_spans.get_skill_build_metadata",
                return_value={"skill_load_total_failure": True},
            ),
            patch(_GET_CLIENT_PATH, return_value=mock_client),
            patch(_CALL_CTX_PATH) as mock_ctx,
        ):
            skill_spans_before_agent_callback(ctx)

        mock_client.create_call.assert_called_once_with(
            op="skill.list",
            inputs={},
            attributes={
                "account_id": "acc_1",
                "skill_count": 0,
                "skill_ids": [],
                "skill_load_total_failure": True,
            },
            use_stack=True,
        )
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
            "app.adk.tracking.skill_spans.get_skill_build_metadata",
            side_effect=RuntimeError("boom"),
        ):
            result = skill_spans_before_agent_callback(ctx)

        assert result is None


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
        assert _current_skill_ctx.get(None) is None

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
                "app.adk.tracking.skill_spans.get_skill_build_metadata",
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
        saved = _current_skill_ctx.get(None)
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
                "app.adk.tracking.skill_spans.get_skill_build_metadata",
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
        saved = _current_skill_ctx.get(None)
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
                "app.adk.tracking.skill_spans.get_skill_build_metadata",
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
        attrs = mock_client.create_call.call_args.kwargs["attributes"]
        assert attrs["op"] if False else attrs["skill_id"] == "sk_r"
        assert attrs["rel_path"] == "data/template.md"

    @pytest.mark.asyncio
    async def test_noop_when_client_is_none(self):
        ctx, _ = self._make_tool_ctx()
        with (
            patch(
                "app.adk.tracking.skill_spans.get_skill_build_metadata",
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
        assert _current_skill_ctx.get(None) is None

    @pytest.mark.asyncio
    async def test_degrades_open_on_exception(self):
        ctx, _ = self._make_tool_ctx()
        with patch(
            "app.adk.tracking.skill_spans.get_skill_build_metadata",
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
        _current_skill_ctx.set(None)
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
        _current_skill_ctx.set({"call": mock_call, "skill_id": None})

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
        assert _current_skill_ctx.get(None) is None

    @pytest.mark.asyncio
    async def test_load_skill_sets_active_skill_id_on_success(self):
        ctx = self._make_tool_ctx()
        mock_call = MagicMock(id="load-finish-1")
        _current_skill_ctx.set({"call": mock_call, "skill_id": "sk_loaded"})

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
        _current_skill_ctx.set({"call": mock_call, "skill_id": "sk_should_not_set"})

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
        _current_skill_ctx.set({"call": mock_call, "skill_id": "sk_res"})

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
    async def test_clears_context_var_on_exception(self):
        ctx = self._make_tool_ctx()
        mock_call = MagicMock(id="ex-call-1")
        _current_skill_ctx.set({"call": mock_call, "skill_id": "sk_x"})

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
        assert _current_skill_ctx.get(None) is None
