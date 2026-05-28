"""Field-surface guard for LeasedSandboxExecutor (SK-42).

Construction-only tests previously passed even though
``LeasedSandboxExecutor.__init__`` skipped ``super().__init__()`` — the failure
surfaced only when ADK reads an inherited ``BaseCodeExecutor`` field per request
(``_code_execution.py:141-144``).  These tests instantiate the real executor and
assert every inherited Pydantic field is populated, so a future regression that
drops ``super().__init__()`` fails at unit-test time instead of at runtime.

``execute_code`` → ``pool.lease()`` proxying is covered by
``test_leased_executor_refcount_boundary`` in
``tests/integration/test_sandbox_pool_runtime_resolver.py``; this file's sole
purpose is the field surface.
"""

from __future__ import annotations

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
