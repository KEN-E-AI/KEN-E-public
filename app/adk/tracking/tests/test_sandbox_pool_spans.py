"""Unit tests for app.adk.tracking.sandbox_pool_spans.emit_sandbox_pool_span.

Coverage:
(a) No-op when Weave client is unavailable.
(b) create_call / finish_call invoked with correct op + attributes.
(c) Exception in the wrapped block does not prevent finish_call.
(d) Helper never raises even if Weave itself raises during create_call or
    finish_call.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

_GET_CLIENT_PATH = "app.adk.tracking.sandbox_pool_spans._weave_get_client"

_ATTRS = {
    "account_id": "acc_123",
    "config_id": "cfg_abc",
    "cache_hit": True,
    "pool_size_after": 3,
}


# ---------------------------------------------------------------------------
# (a) No-op when client is unavailable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_noop_when_client_none() -> None:
    """Helper silently yields and emits nothing when get_client() returns None."""
    with patch(_GET_CLIENT_PATH, return_value=None):
        executed = False
        from app.adk.tracking.sandbox_pool_spans import emit_sandbox_pool_span

        async with emit_sandbox_pool_span("sandbox_pool.get", _ATTRS):
            executed = True

    assert executed, "Wrapped block should still execute"


# ---------------------------------------------------------------------------
# (b) create_call / finish_call invoked with correct op + attributes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_creates_and_finishes_call() -> None:
    """When a Weave client is available, create_call and finish_call are each
    called exactly once with the expected arguments."""
    mock_call = MagicMock(id="span-1")
    mock_client = MagicMock()
    mock_client.create_call.return_value = mock_call

    with patch(_GET_CLIENT_PATH, return_value=mock_client):
        from app.adk.tracking.sandbox_pool_spans import emit_sandbox_pool_span

        async with emit_sandbox_pool_span("sandbox_pool.get", _ATTRS):
            pass

    mock_client.create_call.assert_called_once_with(
        op="sandbox_pool.get",
        inputs=_ATTRS,
        attributes=_ATTRS,
    )
    mock_client.finish_call.assert_called_once_with(mock_call, output=_ATTRS)


# ---------------------------------------------------------------------------
# (c) Exception in the wrapped block does not prevent finish_call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finish_call_called_even_on_exception() -> None:
    """finish_call is invoked in the finally block even when the wrapped body
    raises — the exception propagates to the caller."""
    mock_call = MagicMock(id="span-2")
    mock_client = MagicMock()
    mock_client.create_call.return_value = mock_call

    with patch(_GET_CLIENT_PATH, return_value=mock_client):
        from app.adk.tracking.sandbox_pool_spans import emit_sandbox_pool_span

        with pytest.raises(ValueError, match="boom"):
            async with emit_sandbox_pool_span("sandbox_pool.evict", _ATTRS):
                raise ValueError("boom")

    mock_client.finish_call.assert_called_once_with(mock_call, output=_ATTRS)


# ---------------------------------------------------------------------------
# (d) Helper never raises even if Weave raises during create_call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_noop_when_create_call_raises() -> None:
    """If create_call itself raises, the helper swallows the exception, the
    wrapped block still runs, and finish_call is NOT called (no call object)."""
    mock_client = MagicMock()
    mock_client.create_call.side_effect = RuntimeError("Weave is down")

    from app.adk.tracking.sandbox_pool_spans import emit_sandbox_pool_span

    executed = False
    with patch(_GET_CLIENT_PATH, return_value=mock_client):
        async with emit_sandbox_pool_span("sandbox_pool.get", _ATTRS):
            executed = True

    assert executed, "Wrapped block must run despite create_call failure"
    mock_client.finish_call.assert_not_called()


# ---------------------------------------------------------------------------
# (d-2) Helper never raises even if Weave raises during finish_call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_noop_when_finish_call_raises() -> None:
    """If finish_call raises, the helper swallows it and the caller does not
    see any exception."""
    mock_call = MagicMock(id="span-3")
    mock_client = MagicMock()
    mock_client.create_call.return_value = mock_call
    mock_client.finish_call.side_effect = RuntimeError("finish failed")

    from app.adk.tracking.sandbox_pool_spans import emit_sandbox_pool_span

    with patch(_GET_CLIENT_PATH, return_value=mock_client):
        # Must not raise
        async with emit_sandbox_pool_span("sandbox_pool.evict", _ATTRS):
            pass
