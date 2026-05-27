"""LeasedSandboxExecutor — thin wrapper that proxies execute_code through
SandboxPool.lease() so every code-execution call acquires / releases a
refcount-tracked lease.

SK-42: This wrapper is the production call site for the new lease API.
``_build_code_executor_async`` returns a ``LeasedSandboxExecutor`` instead of
a bare pooled executor.  ADK's ``LlmAgent`` stores it in ``code_executor`` and
calls ``await code_executor.execute_code(...)`` on each tool invocation.
Every such call enters ``async with self._pool.lease(...)``, ensuring:

  * ``_clear_tmp`` fires only on the 0 → 1 refcount transition (no in-flight
    concurrent ``execute_code`` is running when the clear executes).
  * Concurrent callers sharing the same pool entry share the executor without
    triggering a conflicting clear.

The wrapper inherits from ``BaseCodeExecutor`` (ADK's abstract base), which
satisfies Pydantic's ``LlmAgent.code_executor`` field validation — the test
comment at ``test_sandbox_pool_runtime_resolver.py:30`` confirms that any
``BaseCodeExecutor`` subclass passes validation (a plain ``MagicMock`` does
not).  Only ``execute_code`` is implemented; the pool's underlying
``AgentEngineSandboxCodeExecutor`` handles the real execution.

When ADK is unavailable (CI / test environments), the class falls back to
``object`` as its base so the module remains importable.  Tests that need
Pydantic-compatible instances substitute ``BuiltInCodeExecutor()`` instead of
instantiating this class directly — matching the pattern in
``test_sandbox_pool_runtime_resolver.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.adk.agents.agent_factory.sandbox_pool import SandboxPool

# Lazy BaseCodeExecutor import — same discipline as sandbox_pool._construct and
# mcp.py:372 so this module remains importable without a live ADK install.
try:
    from google.adk.code_executors import BaseCodeExecutor as _BaseCodeExecutor

    _BASE: type = _BaseCodeExecutor
except ImportError:  # pragma: no cover — only in test environments
    _BASE = object


class LeasedSandboxExecutor(_BASE):  # type: ignore[misc]
    """Code executor proxy that routes every execute_code call through
    ``SandboxPool.lease()`` (SK-42 CLOBBER fix).

    Usage::

        executor = LeasedSandboxExecutor(
            pool=pool,
            account_id="acc_123",
            config_id="my_agent",
        )
        # LlmAgent stores executor in code_executor field.
        # ADK calls: await executor.execute_code(invocation_context, input_data)
    """

    def __init__(
        self,
        pool: SandboxPool,
        account_id: str,
        config_id: str,
    ) -> None:
        # Do NOT call super().__init__() — BaseCodeExecutor may require
        # abstract-method registration that we satisfy via execute_code below,
        # and BuiltInCodeExecutor's no-arg pattern shows parent __init__ is
        # trivially optional in practice.
        self._pool = pool
        self._account_id = account_id
        self._config_id = config_id

    async def execute_code(
        self,
        invocation_context: Any,
        code_execution_input: Any,
    ) -> Any:
        """Proxy execute_code through a pool lease (SK-42 CLOBBER fix).

        Acquires a lease before delegating to the underlying pooled executor,
        ensuring ``_clear_tmp`` never runs while this call is in-flight on
        the shared Vertex container.
        """
        async with self._pool.lease(
            account_id=self._account_id, config_id=self._config_id
        ) as inner:
            return await inner.execute_code(invocation_context, code_execution_input)
