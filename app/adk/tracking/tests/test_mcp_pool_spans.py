"""Unit tests for app.adk.tracking.mcp_pool_spans.

Mirrors test coverage and structure of test_sandbox_pool_spans.py.
No live Weave install required — the Weave client is stubbed via
``unittest.mock``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.adk.tracking.mcp_pool_spans import emit_mcp_pool_span

# ---------------------------------------------------------------------------
# Test 1 — module imports without Weave installed
# ---------------------------------------------------------------------------


def test_module_imports() -> None:
    """Importing the module and the helper succeed without a live Weave install."""
    import app.adk.tracking.mcp_pool_spans as mod

    assert callable(mod.emit_mcp_pool_span)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GET_CLIENT_PATH = "app.adk.tracking.mcp_pool_spans._weave_get_client"
_CALL_CTX_PATH = "app.adk.tracking.mcp_pool_spans._weave_call_context"


def _make_fake_client(call_id: str = "call-1") -> MagicMock:
    """Return a mock Weave client whose create_call / finish_call are tracked."""
    client = MagicMock(name="WeaveClient")
    call = MagicMock(name="WeaveCall")
    call.id = call_id
    client.create_call.return_value = call
    return client


# ---------------------------------------------------------------------------
# Test 2 — no-op when _weave_get_client is None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_noop_when_get_client_none() -> None:
    """When _weave_get_client is None (Weave not installed), the body executes
    and no Weave calls are made."""
    executed = []

    with patch(_GET_CLIENT_PATH, None):
        async with emit_mcp_pool_span("mcp_pool.get", {"key": "v"}):
            executed.append(True)

    assert executed == [True]


# ---------------------------------------------------------------------------
# Test 3 — no-op when client() returns None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_noop_when_client_returns_none() -> None:
    """When get_client() returns None, the body executes without Weave calls."""
    executed = []
    fake_get_client = MagicMock(return_value=None)

    with patch(_GET_CLIENT_PATH, fake_get_client):
        async with emit_mcp_pool_span("mcp_pool.evict", {"reason": "lru"}):
            executed.append(True)

    assert executed == [True]
    fake_get_client.assert_called_once()


# ---------------------------------------------------------------------------
# Test 4 — create_call and finish_call invoked on normal path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_and_finish_call_on_normal_path() -> None:
    """create_call is called before yield; finish_call is called after."""
    client = _make_fake_client()
    fake_call_ctx = MagicMock()

    with patch(_GET_CLIENT_PATH, lambda: client), patch(_CALL_CTX_PATH, fake_call_ctx):
        async with emit_mcp_pool_span("mcp_pool.get", {"cache_hit": False}):
            pass

    client.create_call.assert_called_once()
    client.finish_call.assert_called_once()


# ---------------------------------------------------------------------------
# Test 5 — finish_call is called even when body raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finish_call_on_body_raise() -> None:
    """finish_call is invoked in the finally block even if the wrapped body raises."""
    client = _make_fake_client()
    fake_call_ctx = MagicMock()

    with pytest.raises(ValueError, match="boom"):
        with (
            patch(_GET_CLIENT_PATH, lambda: client),
            patch(_CALL_CTX_PATH, fake_call_ctx),
        ):
            async with emit_mcp_pool_span("mcp_pool.evict", {"reason": "ttl"}):
                raise ValueError("boom")

    client.finish_call.assert_called_once()


# ---------------------------------------------------------------------------
# Test 6 — create_call raising is swallowed; body still executes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_call_raise_swallowed() -> None:
    """If create_call raises, the exception is swallowed and the body still runs."""
    client = _make_fake_client()
    client.create_call.side_effect = RuntimeError("weave unavailable")
    executed = []

    with patch(_GET_CLIENT_PATH, lambda: client):
        async with emit_mcp_pool_span("mcp_pool.get", {}):
            executed.append(True)

    assert executed == [True]
    client.finish_call.assert_not_called()


# ---------------------------------------------------------------------------
# Test 7 — finish_call raising is swallowed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finish_call_raise_swallowed() -> None:
    """If finish_call raises, the exception is swallowed and does not propagate."""
    client = _make_fake_client()
    client.finish_call.side_effect = RuntimeError("finish failed")
    fake_call_ctx = MagicMock()

    with patch(_GET_CLIENT_PATH, lambda: client), patch(_CALL_CTX_PATH, fake_call_ctx):
        async with emit_mcp_pool_span("mcp_pool.get", {"pool_size_after": 3}):
            pass  # must not raise


# ---------------------------------------------------------------------------
# Test 8 — attrs forwarded to create_call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_attrs_forwarded_to_create_call() -> None:
    """The attrs dict is passed as both inputs= and attributes= to create_call."""
    client = _make_fake_client()
    fake_call_ctx = MagicMock()
    attrs = {"kind": "cloud_run", "cache_hit": True, "pool_size_after": 5}

    with patch(_GET_CLIENT_PATH, lambda: client), patch(_CALL_CTX_PATH, fake_call_ctx):
        async with emit_mcp_pool_span("mcp_pool.get", attrs):
            pass

    call_kwargs = client.create_call.call_args[1]
    assert call_kwargs["inputs"] == attrs
    assert call_kwargs["attributes"] == attrs


# ---------------------------------------------------------------------------
# Test 9 — pop_call invoked on clean exit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pop_call_invoked_on_clean_exit() -> None:
    """_weave_call_context.pop_call is called with call.id after normal exit."""
    client = _make_fake_client(call_id="span-abc")
    fake_call_ctx = MagicMock()

    with patch(_GET_CLIENT_PATH, lambda: client), patch(_CALL_CTX_PATH, fake_call_ctx):
        async with emit_mcp_pool_span("mcp_pool.evict", {"reason": "manual"}):
            pass

    fake_call_ctx.pop_call.assert_called_once_with("span-abc")


# ---------------------------------------------------------------------------
# Test 10 — span name is forwarded as op= to create_call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_span_name_forwarded_as_op() -> None:
    """The ``name`` argument is forwarded as ``op=`` to create_call."""
    client = _make_fake_client()
    fake_call_ctx = MagicMock()

    for span_name in ("mcp_pool.get", "mcp_pool.evict"):
        client.create_call.reset_mock()
        with (
            patch(_GET_CLIENT_PATH, lambda: client),
            patch(_CALL_CTX_PATH, fake_call_ctx),
        ):
            async with emit_mcp_pool_span(span_name, {}):  # type: ignore[arg-type]
                pass

        call_kwargs = client.create_call.call_args[1]
        assert call_kwargs["op"] == span_name
