"""Field-surface guard for LeasedSandboxExecutor (SK-42).

Construction-only tests previously passed even though
``LeasedSandboxExecutor.__init__`` skipped ``super().__init__()`` — the failure
surfaced only when ADK reads an inherited ``BaseCodeExecutor`` field per request
(``_code_execution.py:141-144``).  These tests instantiate the real executor and
assert every inherited Pydantic field is populated, so a future regression that
drops ``super().__init__()`` fails at unit-test time instead of at runtime.

``execute_code`` → ``pool.lease()`` proxying under the pool's real refcount is
covered by ``test_leased_executor_refcount_boundary`` in
``tests/integration/test_sandbox_pool_runtime_resolver.py``; this file covers
the field surface and the synchronous ADK call contract.
"""

from __future__ import annotations

import contextlib
import inspect
from typing import Any
from unittest.mock import MagicMock

from google.adk.code_executors import BaseCodeExecutor

from app.adk.agents.agent_factory.leased_sandbox_executor import LeasedSandboxExecutor
from app.adk.agents.agent_factory.sandbox_pool import SandboxPool


def _make_executor() -> LeasedSandboxExecutor:
    return LeasedSandboxExecutor(
        pool=MagicMock(spec=SandboxPool),
        account_id="acc_123",
        config_id="my_agent",
    )


def test_is_base_code_executor_instance() -> None:
    """The real executor is a BaseCodeExecutor (satisfies LlmAgent validation)."""
    assert isinstance(_make_executor(), BaseCodeExecutor)


def test_inherited_fields_populated() -> None:
    """super().__init__() must populate every inherited BaseCodeExecutor field.

    ADK reads these per request; an unset field raises AttributeError on the
    first turn (the SK-42 blocker this guard prevents from regressing).  Reading
    each field below is what would raise if the base initialiser were skipped.
    """
    e = _make_executor()
    assert (
        bool(e.code_block_delimiters),  # non-empty list of (start, end) pairs
        bool(e.execution_result_delimiters),  # populated (start, end) tuple
        e.optimize_data_file,
        e.stateful,
        e.error_retry_attempts,
    ) == (True, True, False, False, 2)


def test_wrapper_attrs_set() -> None:
    """Wrapper-specific attrs are set after the base initialiser runs."""
    pool = MagicMock(spec=SandboxPool)
    e = LeasedSandboxExecutor(pool=pool, account_id="acc_123", config_id="my_agent")
    assert (e._pool, e._account_id, e._config_id) == (pool, "acc_123", "my_agent")


def test_execute_code_is_not_a_coroutine_function() -> None:
    """execute_code must be a plain (sync) function per ADK's BaseCodeExecutor.

    ADK's ``_code_execution`` flow calls ``execute_code(...)`` un-awaited and
    reads ``.stdout`` off the return value, so an ``async def`` here hands ADK a
    coroutine and crashes on the first code turn (the PR #727 blocker).
    """
    assert not inspect.iscoroutinefunction(LeasedSandboxExecutor.execute_code)


def test_execute_code_proxies_inner_result_synchronously() -> None:
    """execute_code enters pool.lease() and returns the inner result directly.

    Uses a sync lease() context manager and a sync inner executor — mirroring
    the real (post-rework) pool surface — and asserts the wrapper returns the
    inner executor's result object unchanged (not a coroutine).
    """
    sentinel = object()
    inner = MagicMock()
    inner.execute_code.return_value = sentinel

    @contextlib.contextmanager
    def _fake_lease(*, account_id: str, config_id: str) -> Any:
        yield inner

    pool = MagicMock(spec=SandboxPool)
    pool.lease.side_effect = _fake_lease

    e = LeasedSandboxExecutor(pool=pool, account_id="acc_123", config_id="my_agent")
    ctx, code_input = MagicMock(), MagicMock()
    result = e.execute_code(ctx, code_input)

    assert result is sentinel
    pool.lease.assert_called_once_with(account_id="acc_123", config_id="my_agent")
    inner.execute_code.assert_called_once_with(ctx, code_input)
