"""Weave span helper for SandboxPool emit sites.

Provides a single async context manager ``emit_sandbox_pool_span(name, attrs)``
that wraps ``client.create_call`` + ``client.finish_call`` and degrades to a
no-op when Weave is unavailable — matching the ``try/except`` discipline used
by ``weave_before_agent_callback`` in ``callbacks.py``.

Usage::

    async with emit_sandbox_pool_span("sandbox_pool.get", {
        "account_id": account_id,
        "config_id": config_id,
        "cache_hit": cache_hit,
        "pool_size_after": pool_size_after,
    }):
        pass  # span wraps the logical event; body is usually empty

The helper guarantees:
* The wrapped block always executes, regardless of Weave health.
* ``finish_call`` is always invoked after ``create_call`` succeeds, even if
  the wrapped block raises.
* Any Weave exception is caught, logged as a warning, and swallowed so the
  pool caller is never interrupted by an observability failure.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator, Callable
from typing import Any

from shared.structured_logging import get_structured_logger

logger = get_structured_logger(__name__)

# Lazy import guard — same discipline as sandbox_pool.py and mcp.py:372.
# This module must remain importable in test environments without a live Weave
# or ADK install.  The explicit Optional annotation ensures mypy does not
# narrow the type to non-None even when the import succeeds.
_weave_get_client: Callable[[], Any] | None = None
try:
    from weave.trace.api import get_client as _weave_get_client
except ImportError:  # pragma: no cover
    pass


@contextlib.asynccontextmanager
async def emit_sandbox_pool_span(
    name: str,
    attrs: dict[str, Any],
) -> AsyncGenerator[None, None]:
    """Async context manager that emits a named Weave span for a pool event.

    Creates the call before yielding and finishes it after the wrapped block
    completes (or raises).  Degrades to a silent no-op when Weave is
    unavailable or if the client raises during call creation.

    Args:
        name: Span operation name, e.g. ``"sandbox_pool.get"``.
        attrs: Attributes dict forwarded to ``client.create_call``.
    """
    call = None
    get_client = _weave_get_client
    try:
        if get_client is None:
            yield
            return
        client = get_client()
        if client is None:
            yield
            return
        call = client.create_call(
            op=name,
            inputs=attrs,
            attributes=attrs,
        )
    except Exception:
        logger.warning(
            "emit_sandbox_pool_span: failed to create Weave call",
            exc_info=True,
        )
        yield
        return

    try:
        yield
    finally:
        try:
            if get_client is not None and call is not None:
                finish_client = get_client()
                if finish_client is not None:
                    finish_client.finish_call(call, output=attrs)
        except Exception:
            logger.warning(
                "emit_sandbox_pool_span: failed to finish Weave call",
                exc_info=True,
            )
