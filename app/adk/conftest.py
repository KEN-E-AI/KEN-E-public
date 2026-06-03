"""Shared fixtures for app/adk tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clear_pending_trace_contexts():
    """Reset the off-state weave trace-context stash between tests.

    `adk_before_tool_callback` stashes a live weave.attributes() context manager
    in a module-global dict keyed by id(tool_context). If a test strands an entry
    (enters the before-hook without a paired after-callback), CPython id() reuse
    lets a later test pop that stale CM and exit it in the wrong asyncio context,
    raising weave's cross-context ValueError. Clearing per test makes that
    impossible regardless of test ordering.
    """
    yield
    from app.adk.tracking.tool_trace_context import clear_trace_contexts

    clear_trace_contexts()
