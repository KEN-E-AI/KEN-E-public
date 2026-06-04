"""Tests for Weave agent-level span callbacks."""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from google.adk.agents.llm_agent_config import LlmAgentConfig

from app.adk.tracking.callbacks import (
    _get_chatbot_config_metadata,
    _weave_agent_span_stack,
    capture_last_model_output_after_model_callback,
    weave_after_agent_callback,
    weave_before_agent_callback,
)


def _stack_calls() -> list:
    """Return the calls currently on the per-agent span stack (bottom→top)."""
    return [call for (call, _attrs) in (_weave_agent_span_stack.get() or [])]

_INIT_WEAVE_PATH = "app.adk.tracking.callbacks.init_weave_if_needed"
_GET_CLIENT_PATH = "app.adk.tracking.callbacks._weave_get_client"
_CALL_CTX_PATH = "app.adk.tracking.callbacks._weave_call_context"
_CONFIG_META_PATH = "app.adk.tracking.callbacks._get_chatbot_config_metadata"


def _config_cache_module():
    """Resolve the same ``config_cache`` module ``_get_chatbot_config_metadata``
    imports from.

    The callback tries the Agent-Engine-flattened ``agents.utils.config_cache``
    first and falls back to ``app.adk.agents.utils.config_cache``. Under pytest
    the flattened path is importable, so patching the ``app.adk.…`` module
    object would miss the real ``get_cached_config``. Mirroring the import order
    here guarantees we patch the object the callback actually calls.
    """
    try:
        from agents.utils import config_cache
    except ImportError:
        from app.adk.agents.utils import config_cache
    return config_cache


_MOCK_CONFIG_METADATA = {
    "version": "v1.0.0",
    "experiment_id": "baseline",
    "variant_name": "baseline",
    "model": "gemini-2.5-pro",
}


def _make_invocation_ctx(
    instruction: str | None = None, agent_name: str = "ken_e"
) -> MagicMock:
    """Build a minimal _invocation_context mock with an optional agent."""
    ic = MagicMock()
    if instruction is not None:
        agent = MagicMock()
        agent.name = agent_name
        agent.canonical_instruction = AsyncMock(return_value=(instruction, False))
        ic.agent = agent
    else:
        ic.agent = None
    return ic


@dataclass
class MockCallbackContext:
    """Minimal stand-in for google.adk.agents.callback_context.CallbackContext."""

    agent_name: str = "ken_e"
    state: dict = field(default_factory=dict)
    _invocation_context: MagicMock | None = None


@pytest.fixture(autouse=True)
def _reset_span_stack():
    """Ensure the per-agent span stack is clean before and after each test."""
    _weave_agent_span_stack.set(None)
    yield
    _weave_agent_span_stack.set(None)


class TestWeaveBeforeAgentCallback:
    """Tests for weave_before_agent_callback (async)."""

    @pytest.mark.asyncio
    @patch(_CONFIG_META_PATH, return_value=_MOCK_CONFIG_METADATA)
    async def test_creates_call_and_pushes_frame(self, mock_cfg: MagicMock):
        mock_call = MagicMock(id="call-123")
        mock_client = MagicMock()
        mock_client.create_call.return_value = mock_call

        with patch(_INIT_WEAVE_PATH), patch(_GET_CLIENT_PATH, return_value=mock_client):
            result = await weave_before_agent_callback(
                callback_context=MockCallbackContext()
            )

        assert result is None
        # With no _invocation_context the agent name falls back to "ken_e" (the
        # root agent's ADK name) — the span op is now named after the agent, not
        # the legacy hardcoded "ken_e_agent".
        mock_client.create_call.assert_called_once_with(
            op="ken_e",
            inputs={"agent": "ken_e", "context_agent_goal": None},
            attributes=ANY,
            use_stack=True,
        )
        assert _stack_calls() == [mock_call]

    @pytest.mark.asyncio
    @patch(_CONFIG_META_PATH, return_value=_MOCK_CONFIG_METADATA)
    async def test_span_named_after_specialist_agent(self, mock_cfg: MagicMock):
        """The span op is the running agent's name (e.g. a specialist doc_id)."""
        mock_call = MagicMock(id="call-spec")
        mock_client = MagicMock()
        mock_client.create_call.return_value = mock_call

        ic = MagicMock()
        ic.agent = MagicMock()
        ic.agent.name = "google_analytics_specialist"
        # Skip the instruction branch cleanly (LoopAgent-like: no instruction).
        del ic.agent.canonical_instruction
        ctx = MockCallbackContext(_invocation_context=ic)

        with patch(_INIT_WEAVE_PATH), patch(_GET_CLIENT_PATH, return_value=mock_client):
            await weave_before_agent_callback(callback_context=ctx)

        kwargs = mock_client.create_call.call_args.kwargs
        assert kwargs["op"] == "google_analytics_specialist"
        assert kwargs["inputs"]["agent"] == "google_analytics_specialist"

    @pytest.mark.asyncio
    @patch(_CONFIG_META_PATH, return_value=_MOCK_CONFIG_METADATA)
    async def test_includes_instruction_in_inputs_when_available(
        self, mock_cfg: MagicMock
    ):
        """Instruction text from canonical_instruction must appear in create_call inputs."""
        mock_call = MagicMock(id="call-instr")
        mock_client = MagicMock()
        mock_client.create_call.return_value = mock_call

        instruction = "You are the KEN-E assistant."
        ctx = MockCallbackContext(
            _invocation_context=_make_invocation_ctx(instruction=instruction)
        )

        with patch(_INIT_WEAVE_PATH), patch(_GET_CLIENT_PATH, return_value=mock_client):
            result = await weave_before_agent_callback(callback_context=ctx)

        assert result is None
        call_kwargs = mock_client.create_call.call_args.kwargs
        assert call_kwargs["inputs"]["instruction"] == instruction

    @pytest.mark.asyncio
    @patch(_CONFIG_META_PATH, return_value=_MOCK_CONFIG_METADATA)
    async def test_omits_instruction_key_when_agent_not_available(
        self, mock_cfg: MagicMock
    ):
        """When _invocation_context.agent is None, 'instruction' key is absent."""
        mock_call = MagicMock(id="call-no-agent")
        mock_client = MagicMock()
        mock_client.create_call.return_value = mock_call

        ctx = MockCallbackContext(
            _invocation_context=_make_invocation_ctx(instruction=None)
        )

        with patch(_INIT_WEAVE_PATH), patch(_GET_CLIENT_PATH, return_value=mock_client):
            result = await weave_before_agent_callback(callback_context=ctx)

        assert result is None
        call_kwargs = mock_client.create_call.call_args.kwargs
        assert "instruction" not in call_kwargs["inputs"]

    @pytest.mark.asyncio
    async def test_calls_init_weave_before_getting_client(self):
        call_order: list[str] = []

        def mock_init():
            call_order.append("init")

        def mock_get():
            call_order.append("get_client")
            return None

        # client is None → early return before _build_chatbot_root_attrs;
        # no need to patch _get_chatbot_config_metadata here.
        with (
            patch(_INIT_WEAVE_PATH, side_effect=mock_init),
            patch(_GET_CLIENT_PATH, side_effect=mock_get),
        ):
            await weave_before_agent_callback(callback_context=MockCallbackContext())

        assert call_order == ["init", "get_client"]

    @pytest.mark.asyncio
    async def test_noop_when_client_is_none(self):
        # Returns None before reaching _build_chatbot_root_attrs → no patch needed.
        with patch(_INIT_WEAVE_PATH), patch(_GET_CLIENT_PATH, return_value=None):
            result = await weave_before_agent_callback(
                callback_context=MockCallbackContext()
            )

        assert result is None
        assert _stack_calls() == []

    @pytest.mark.asyncio
    @patch(_CONFIG_META_PATH, return_value=_MOCK_CONFIG_METADATA)
    async def test_handles_create_call_exception(self, mock_cfg: MagicMock):
        mock_client = MagicMock()
        mock_client.create_call.side_effect = RuntimeError("Weave down")

        with patch(_INIT_WEAVE_PATH), patch(_GET_CLIENT_PATH, return_value=mock_client):
            result = await weave_before_agent_callback(
                callback_context=MockCallbackContext()
            )

        assert result is None
        assert _stack_calls() == []

    @pytest.mark.asyncio
    @patch(_CONFIG_META_PATH, return_value=_MOCK_CONFIG_METADATA)
    async def test_instruction_resolution_exception_is_swallowed(
        self, mock_cfg: MagicMock
    ):
        """canonical_instruction raising must not break the span creation."""
        mock_call = MagicMock(id="call-exc")
        mock_client = MagicMock()
        mock_client.create_call.return_value = mock_call

        ic = MagicMock()
        ic.agent.canonical_instruction = AsyncMock(
            side_effect=RuntimeError("ADK internal error")
        )
        ctx = MockCallbackContext(_invocation_context=ic)

        with patch(_INIT_WEAVE_PATH), patch(_GET_CLIENT_PATH, return_value=mock_client):
            result = await weave_before_agent_callback(callback_context=ctx)

        assert result is None
        # Span still created; 'instruction' key absent from inputs.
        mock_client.create_call.assert_called_once()
        call_kwargs = mock_client.create_call.call_args.kwargs
        assert "instruction" not in call_kwargs["inputs"]


class TestWeaveAfterAgentCallback:
    """Tests for weave_after_agent_callback (pops THIS agent's frame off the
    per-agent span stack)."""

    def test_finishes_call_with_status_only_when_no_last_output(self):
        mock_call = MagicMock(id="call-456")
        _weave_agent_span_stack.set([(mock_call, None)])

        mock_client = MagicMock()
        ctx = MockCallbackContext()  # no temp:_last_model_output in state

        with (
            patch(_GET_CLIENT_PATH, return_value=mock_client),
            patch(_CALL_CTX_PATH) as mock_ctx,
        ):
            result = weave_after_agent_callback(callback_context=ctx)

        assert result is None
        mock_client.finish_call.assert_called_once_with(
            mock_call, output={"status": "completed"}
        )
        mock_ctx.pop_call.assert_called_once_with("call-456")
        assert _stack_calls() == []

    def test_finishes_call_with_text_when_last_output_set(self):
        mock_call = MagicMock(id="call-text")
        _weave_agent_span_stack.set([(mock_call, None)])

        mock_client = MagicMock()
        ctx = MockCallbackContext(
            state={"temp:_last_model_output": "Here is the answer."}
        )

        with (
            patch(_GET_CLIENT_PATH, return_value=mock_client),
            patch(_CALL_CTX_PATH) as mock_ctx,
        ):
            result = weave_after_agent_callback(callback_context=ctx)

        assert result is None
        mock_client.finish_call.assert_called_once_with(
            mock_call, output={"status": "completed", "text": "Here is the answer."}
        )
        mock_ctx.pop_call.assert_called_once_with("call-text")

    def test_exits_attrs_ctx_for_the_popped_frame(self):
        """The weave.attributes() CM opened in before is closed in after."""
        mock_call = MagicMock(id="call-attrs")
        attrs_ctx = MagicMock()
        _weave_agent_span_stack.set([(mock_call, attrs_ctx)])

        with (
            patch(_GET_CLIENT_PATH, return_value=MagicMock()),
            patch(_CALL_CTX_PATH),
        ):
            weave_after_agent_callback(callback_context=MockCallbackContext())

        attrs_ctx.__exit__.assert_called_once_with(None, None, None)
        assert _stack_calls() == []

    def test_noop_when_stack_empty(self):
        result = weave_after_agent_callback(callback_context=MockCallbackContext())

        assert result is None
        assert _stack_calls() == []

    @pytest.mark.asyncio
    async def test_nested_agents_finish_their_own_spans_lifo(self):
        """Root → specialist nesting: each after finishes its OWN span (LIFO),
        so the root span is NOT orphaned when a sub-agent runs in between.

        This is the regression guard for the single-ContextVar bug where a
        nested sub-agent clobbered the parent's reference and the root span was
        never finished. Runs as one async test so the before (awaited) and after
        (sync) callbacks all share a single contextvars context — using
        asyncio.run per call would mutate a copied context that never propagates
        back.
        """
        root_call = MagicMock(id="root")
        spec_call = MagicMock(id="spec")
        mock_client = MagicMock()
        mock_client.create_call.side_effect = [root_call, spec_call]

        with (
            patch(_INIT_WEAVE_PATH),
            patch(_GET_CLIENT_PATH, return_value=mock_client),
            patch(_CONFIG_META_PATH, return_value=_MOCK_CONFIG_METADATA),
            patch(_CALL_CTX_PATH) as mock_ctx,
        ):
            await weave_before_agent_callback(callback_context=MockCallbackContext())
            await weave_before_agent_callback(callback_context=MockCallbackContext())
            assert [c.id for c in _stack_calls()] == ["root", "spec"]

            weave_after_agent_callback(callback_context=MockCallbackContext())
            assert [c.id for c in _stack_calls()] == ["root"]

            weave_after_agent_callback(callback_context=MockCallbackContext())
            assert _stack_calls() == []

        finished = [c.args[0].id for c in mock_client.finish_call.call_args_list]
        assert finished == ["spec", "root"], (
            "Both spans must finish in LIFO order — the root must not be orphaned"
        )
        popped = [c.args[0] for c in mock_ctx.pop_call.call_args_list]
        assert popped == ["spec", "root"]

    def test_handles_finish_exception_and_still_cleans_up(self):
        mock_call = MagicMock(id="call-789")
        _weave_agent_span_stack.set([(mock_call, None)])

        mock_client = MagicMock()
        mock_client.finish_call.side_effect = RuntimeError("Weave error")

        with (
            patch(_GET_CLIENT_PATH, return_value=mock_client),
            patch(_CALL_CTX_PATH) as mock_ctx,
        ):
            result = weave_after_agent_callback(callback_context=MockCallbackContext())

        assert result is None
        mock_ctx.pop_call.assert_called_with("call-789")
        assert _stack_calls() == []

    def test_handles_pop_call_exception_gracefully(self):
        mock_call = MagicMock(id="call-000")
        _weave_agent_span_stack.set([(mock_call, None)])

        mock_client = MagicMock()
        mock_client.finish_call.side_effect = RuntimeError("finish fail")

        with (
            patch(_GET_CLIENT_PATH, return_value=mock_client),
            patch(_CALL_CTX_PATH) as mock_ctx,
        ):
            mock_ctx.pop_call.side_effect = RuntimeError("pop fail")
            result = weave_after_agent_callback(callback_context=MockCallbackContext())

        assert result is None
        assert _stack_calls() == []


class TestCaptureLastModelOutputCallback:
    """Tests for capture_last_model_output_after_model_callback."""

    @staticmethod
    def _make_part(
        text: str | None = None, thought: bool = False, function_call: object = None
    ):
        part = MagicMock()
        part.text = text
        part.thought = thought
        part.function_call = function_call
        return part

    @staticmethod
    def _make_response(parts):
        resp = MagicMock()
        resp.content = MagicMock()
        resp.content.parts = parts
        return resp

    @pytest.mark.asyncio
    async def test_stores_plain_text_in_state(self):
        ctx = MockCallbackContext()
        parts = [self._make_part(text="Hello, world!")]
        resp = self._make_response(parts)

        result = await capture_last_model_output_after_model_callback(ctx, resp)

        assert result is None
        assert ctx.state["temp:_last_model_output"] == "Hello, world!"

    @pytest.mark.asyncio
    async def test_uses_invocation_scoped_temp_key(self):
        """The output text must be stored under a ``temp:``-prefixed key so ADK
        clears it between invocations. Persisting it under a plain key would let
        a turn that ends on a function_call surface the previous turn's text and
        would write the answer into the session document on every turn."""
        ctx = MockCallbackContext()
        resp = self._make_response([self._make_part(text="Answer.")])

        await capture_last_model_output_after_model_callback(ctx, resp)

        assert ctx.state["temp:_last_model_output"] == "Answer."
        assert "_last_model_output" not in ctx.state

    @pytest.mark.asyncio
    async def test_joins_multiple_text_parts(self):
        ctx = MockCallbackContext()
        parts = [self._make_part(text="Line 1"), self._make_part(text="Line 2")]
        resp = self._make_response(parts)

        await capture_last_model_output_after_model_callback(ctx, resp)

        assert ctx.state["temp:_last_model_output"] == "Line 1\nLine 2"

    @pytest.mark.asyncio
    async def test_skips_thought_parts(self):
        ctx = MockCallbackContext()
        parts = [
            self._make_part(text="<reasoning>", thought=True),
            self._make_part(text="User-visible answer."),
        ]
        resp = self._make_response(parts)

        await capture_last_model_output_after_model_callback(ctx, resp)

        assert ctx.state["temp:_last_model_output"] == "User-visible answer."

    @pytest.mark.asyncio
    async def test_skips_function_call_parts(self):
        ctx = MockCallbackContext()
        fc = MagicMock(name="some_tool")
        parts = [
            self._make_part(text="calling tool", function_call=fc),
            self._make_part(text="Final answer."),
        ]
        resp = self._make_response(parts)

        await capture_last_model_output_after_model_callback(ctx, resp)

        assert ctx.state["temp:_last_model_output"] == "Final answer."

    @pytest.mark.asyncio
    async def test_noop_on_empty_response(self):
        ctx = MockCallbackContext()
        resp = MagicMock()
        resp.content = None

        result = await capture_last_model_output_after_model_callback(ctx, resp)

        assert result is None
        assert "temp:_last_model_output" not in ctx.state

    @pytest.mark.asyncio
    async def test_noop_when_all_parts_are_thought_or_function_call(self):
        ctx = MockCallbackContext()
        parts = [
            self._make_part(text="<thought>", thought=True),
            self._make_part(text="tool", function_call=MagicMock()),
        ]
        resp = self._make_response(parts)

        await capture_last_model_output_after_model_callback(ctx, resp)

        assert "temp:_last_model_output" not in ctx.state


class TestGetChatbotConfigMetadata:
    """Projection from ``get_cached_config`` to the six span-attribute keys.

    These exercise the production projection directly (no mock on
    ``_get_chatbot_config_metadata`` itself) — the rest of the suite mocks
    that seam to stay hermetic, so the mapping is otherwise untested.
    """

    @staticmethod
    def _make_config(
        model: str = "gemini-2.5-pro",
        temperature: float | None = 0.3,
        max_output_tokens: int | None = 2048,
    ) -> LlmAgentConfig:
        gcc: dict[str, object] = {}
        if temperature is not None:
            gcc["temperature"] = temperature
        if max_output_tokens is not None:
            gcc["max_output_tokens"] = max_output_tokens
        return LlmAgentConfig(
            name="ken_e_chatbot",
            model=model,
            instruction="sys",
            description="desc",
            generate_content_config=gcc or None,
        )

    def test_projects_all_six_keys(self):
        config = self._make_config()
        metadata = {
            "version": "v2.1.0",
            "experiment_id": "exp-42",
            "variant_name": "treatment",
        }
        with patch.object(
            _config_cache_module(),
            "get_cached_config",
            return_value=(config, metadata, {}),
        ):
            result = _get_chatbot_config_metadata()

        assert result == {
            "version": "v2.1.0",
            "experiment_id": "exp-42",
            "variant_name": "treatment",
            "model": "gemini-2.5-pro",
            "temperature": 0.3,
            "max_output_tokens": 2048,
        }

    def test_defaults_when_metadata_keys_missing(self):
        config = self._make_config(temperature=None, max_output_tokens=None)
        with patch.object(
            _config_cache_module(),
            "get_cached_config",
            return_value=(config, {}, {}),
        ):
            result = _get_chatbot_config_metadata()

        assert result == {
            "version": None,
            "experiment_id": "baseline",
            "variant_name": "baseline",
            "model": "gemini-2.5-pro",
            "temperature": None,
            "max_output_tokens": None,
        }

    def test_returns_empty_dict_when_get_cached_config_raises(self):
        with patch.object(
            _config_cache_module(),
            "get_cached_config",
            side_effect=RuntimeError("firestore down"),
        ):
            result = _get_chatbot_config_metadata()

        assert result == {}
