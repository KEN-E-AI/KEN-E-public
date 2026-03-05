"""Tests for Weave agent-level span callbacks."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from app.adk.tracking.callbacks import (
    _current_agent_call,
    weave_after_agent_callback,
    weave_before_agent_callback,
)

_TRACE_AVAILABLE_PATH = "app.adk.tracking.callbacks._WEAVE_TRACE_AVAILABLE"
_INIT_WEAVE_PATH = "app.adk.tracking.callbacks.init_weave_if_needed"
_GET_CLIENT_PATH = "app.adk.tracking.callbacks._weave_get_client"
_CALL_CTX_PATH = "app.adk.tracking.callbacks._weave_call_context"


@dataclass
class MockCallbackContext:
    """Minimal stand-in for google.adk.agents.callback_context.CallbackContext."""

    agent_name: str = "ken_e"


@pytest.fixture(autouse=True)
def _reset_context_var():
    """Ensure the ContextVar is clean before and after each test."""
    _current_agent_call.set(None)
    yield
    _current_agent_call.set(None)


class TestWeaveBeforeAgentCallback:
    """Tests for weave_before_agent_callback."""

    def test_creates_call_and_sets_context_var(self):
        mock_call = MagicMock(id="call-123")
        mock_client = MagicMock()
        mock_client.create_call.return_value = mock_call

        with patch(_TRACE_AVAILABLE_PATH, True), patch(_INIT_WEAVE_PATH), patch(
            _GET_CLIENT_PATH, return_value=mock_client
        ):
            result = weave_before_agent_callback(
                callback_context=MockCallbackContext()
            )

        assert result is None
        mock_client.create_call.assert_called_once_with(
            op="ken_e_agent",
            inputs={"agent": "ken_e"},
            use_stack=True,
        )
        assert _current_agent_call.get(None) is mock_call

    def test_calls_init_weave_before_getting_client(self):
        call_order: list[str] = []

        def mock_init():
            call_order.append("init")

        def mock_get():
            call_order.append("get_client")
            return None

        with patch(_TRACE_AVAILABLE_PATH, True), patch(
            _INIT_WEAVE_PATH, side_effect=mock_init
        ), patch(_GET_CLIENT_PATH, side_effect=mock_get):
            weave_before_agent_callback(
                callback_context=MockCallbackContext()
            )

        assert call_order == ["init", "get_client"]

    def test_noop_when_client_is_none(self):
        with patch(_TRACE_AVAILABLE_PATH, True), patch(_INIT_WEAVE_PATH), patch(
            _GET_CLIENT_PATH, return_value=None
        ):
            result = weave_before_agent_callback(
                callback_context=MockCallbackContext()
            )

        assert result is None
        assert _current_agent_call.get(None) is None

    def test_noop_when_trace_unavailable(self):
        with patch(_TRACE_AVAILABLE_PATH, False):
            result = weave_before_agent_callback(
                callback_context=MockCallbackContext()
            )

        assert result is None
        assert _current_agent_call.get(None) is None

    def test_handles_create_call_exception(self):
        mock_client = MagicMock()
        mock_client.create_call.side_effect = RuntimeError("Weave down")

        with patch(_TRACE_AVAILABLE_PATH, True), patch(_INIT_WEAVE_PATH), patch(
            _GET_CLIENT_PATH, return_value=mock_client
        ):
            result = weave_before_agent_callback(
                callback_context=MockCallbackContext()
            )

        assert result is None
        assert _current_agent_call.get(None) is None


class TestWeaveAfterAgentCallback:
    """Tests for weave_after_agent_callback."""

    def test_finishes_call_and_pops_stack(self):
        mock_call = MagicMock(id="call-456")
        _current_agent_call.set(mock_call)

        mock_client = MagicMock()

        with patch(_TRACE_AVAILABLE_PATH, True), patch(
            _GET_CLIENT_PATH, return_value=mock_client
        ), patch(_CALL_CTX_PATH) as mock_ctx:
            result = weave_after_agent_callback(
                callback_context=MockCallbackContext()
            )

        assert result is None
        mock_client.finish_call.assert_called_once_with(
            mock_call, output={"status": "completed"}
        )
        mock_ctx.pop_call.assert_called_once_with("call-456")
        assert _current_agent_call.get(None) is None

    def test_noop_when_no_call_in_context_var(self):
        result = weave_after_agent_callback(
            callback_context=MockCallbackContext()
        )

        assert result is None
        assert _current_agent_call.get(None) is None

    def test_noop_when_trace_unavailable(self):
        mock_call = MagicMock(id="call-no-trace")
        _current_agent_call.set(mock_call)

        with patch(_TRACE_AVAILABLE_PATH, False):
            result = weave_after_agent_callback(
                callback_context=MockCallbackContext()
            )

        assert result is None

    def test_handles_finish_exception_and_still_cleans_up(self):
        mock_call = MagicMock(id="call-789")
        _current_agent_call.set(mock_call)

        mock_client = MagicMock()
        mock_client.finish_call.side_effect = RuntimeError("Weave error")

        with patch(_TRACE_AVAILABLE_PATH, True), patch(
            _GET_CLIENT_PATH, return_value=mock_client
        ), patch(_CALL_CTX_PATH) as mock_ctx:
            result = weave_after_agent_callback(
                callback_context=MockCallbackContext()
            )

        assert result is None
        mock_ctx.pop_call.assert_called_with("call-789")
        assert _current_agent_call.get(None) is None

    def test_handles_pop_call_exception_gracefully(self):
        mock_call = MagicMock(id="call-000")
        _current_agent_call.set(mock_call)

        mock_client = MagicMock()
        mock_client.finish_call.side_effect = RuntimeError("finish fail")

        with patch(_TRACE_AVAILABLE_PATH, True), patch(
            _GET_CLIENT_PATH, return_value=mock_client
        ), patch(_CALL_CTX_PATH) as mock_ctx:
            mock_ctx.pop_call.side_effect = RuntimeError("pop fail")
            result = weave_after_agent_callback(
                callback_context=MockCallbackContext()
            )

        assert result is None
        assert _current_agent_call.get(None) is None
