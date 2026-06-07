"""Concurrency smoke test for the numerical analyst agent-as-a-tool (AH-149).

AH-114 (registry migration): the ``numerical_analyst`` catalogue entry now stores
a task-mode ``LlmAgent`` instead of an ``AgentTool``. The ``AgentTool.run_async``
concurrency contract tested here no longer applies — task-mode dispatch uses
ADK's ``request_task_<name>`` / ``complete_task`` / ``ctx.run_node`` fan-out.
The parallel-search re-validation (covering ``numerical_analyst`` on the specialist
path) is in scope for AH-119 (Re-validate AH-98 parallel-search AC #9 under
``ctx.run_node``), which will rewrite this test against the task-mode model.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest
from google.genai import types

# ── fakes ────────────────────────────────────────────────────────────────


class _FakeState:
    def __init__(self) -> None:
        self._d: dict[str, Any] = {}

    def to_dict(self) -> dict[str, Any]:
        return dict(self._d)

    def update(self, other: dict[str, Any]) -> None:
        self._d.update(other)


def _make_tool_context(user_id: str) -> Any:
    invocation_context = SimpleNamespace(
        app_name="test_app",
        user_id=user_id,
        credential_service=None,
        plugin_manager=SimpleNamespace(plugins=[]),
    )
    return SimpleNamespace(
        actions=SimpleNamespace(skip_summarization=False),
        state=_FakeState(),
        _invocation_context=invocation_context,
    )


class _OverlapTracker:
    def __init__(self, parties: int) -> None:
        self.barrier = asyncio.Barrier(parties)
        self.in_flight = 0
        self.max_in_flight = 0
        self._lock = asyncio.Lock()

    async def enter(self) -> None:
        async with self._lock:
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)

    async def leave(self) -> None:
        async with self._lock:
            self.in_flight -= 1


def _fake_runner_factory(tracker: _OverlapTracker, created: list[Any]) -> type:
    class _FakeRunner:
        def __init__(self, *, agent: Any, **_: Any) -> None:
            self.agent = agent
            self.session_service = SimpleNamespace(create_session=self._create_session)
            created.append(self)

        async def _create_session(
            self, *, app_name: str, user_id: str, state: dict[str, Any]
        ) -> SimpleNamespace:
            return SimpleNamespace(id="sess", user_id=user_id)

        async def run_async(
            self, *, user_id: str, session_id: str, new_message: Any
        ) -> AsyncIterator[SimpleNamespace]:
            request_text = new_message.parts[0].text
            await tracker.enter()
            await tracker.barrier.wait()
            try:
                yield SimpleNamespace(
                    actions=SimpleNamespace(state_delta=None),
                    grounding_metadata=None,
                    content=types.Content(
                        role="model",
                        parts=[types.Part(text=f"echo:{request_text}")],
                    ),
                )
            finally:
                await tracker.leave()

        async def close(self) -> None:
            pass

    return _FakeRunner


# ── tests ─────────────────────────────────────────────────────────────────


@pytest.mark.skip(
    reason=(
        "AH-114: registry stores task-mode LlmAgent instead of AgentTool. "
        "AgentTool.run_async concurrency is replaced by ctx.run_node fan-out "
        "in the task-mode model. AH-119 re-validates parallel-search AC #9 "
        "under the new ADK 2.0 concurrency model (ctx.run_node / asyncio.gather)."
    )
)
@pytest.mark.asyncio
async def test_shared_singleton_runs_concurrent_calls_without_cross_talk() -> None:
    """N concurrent calls on the shared singleton return distinct input-matched results."""
    # AH-119 rewrites this test to drive ctx.run_node fan-out concurrency.
    # The old AgentTool.run_async body is removed — LlmAgent has no run_async method.
    # See the helpers above (_OverlapTracker, _fake_runner_factory) which AH-119 may reuse.
    pytest.fail("AH-119: implement concurrent ctx.run_node fan-out test here")
