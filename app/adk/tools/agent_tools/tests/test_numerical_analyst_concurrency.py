"""Concurrency smoke test for the numerical analyst agent-as-a-tool (AH-149).

The `numerical_analyst` AgentTool is registered once at import time — one
object shared across all turns. Each concurrent turn drives it with a distinct
numeric input; this test verifies that N concurrent ``run_async`` calls on the
shared singleton produce distinct, input-matched results with no cross-talk.

The ``asyncio.Barrier`` is load-bearing: every concurrent call must reach it
before any is released, so ``max_in_flight == N`` can only be observed if all N
ran simultaneously. A serialized implementation would block at the barrier —
surfaced by the ``wait_for`` timeout.

Follows the pattern established by ``test_google_search_concurrency.py``.
"""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from google.adk.tools.agent_tool import AgentTool
from google.genai import types

import app.adk.tools.agent_tools.numerical_analyst as na_mod
from app.adk.tools.registry.agent_tool_registry import get_agent_tool

# ── fakes ────────────────────────────────────────────────────────────────


class _FakeState:
    def __init__(self) -> None:
        self._d: dict[str, Any] = {}

    def to_dict(self) -> dict[str, Any]:
        return dict(self._d)

    def update(self, other: dict[str, Any]) -> None:
        self._d.update(other)


def _make_tool_context(user_id: str) -> Any:
    """A stand-in ToolContext, distinct per call."""
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
    """Records peak number of simultaneously in-flight leaf runs."""

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
    """Build a Runner stand-in that overlaps and echoes each call's request."""

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
            # All concurrent calls must reach this barrier before any proceeds.
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


@pytest.fixture()
def numerical_analyst_tool() -> AgentTool:
    importlib.reload(na_mod)
    tool = get_agent_tool("numerical_analyst")
    assert isinstance(tool, AgentTool)
    return tool


@pytest.mark.asyncio
async def test_shared_singleton_runs_concurrent_calls_without_cross_talk(
    numerical_analyst_tool: AgentTool,
) -> None:
    """N concurrent calls on the shared singleton return distinct input-matched results."""
    n = 3
    tracker = _OverlapTracker(parties=n)
    created_runners: list[Any] = []
    fake_runner = _fake_runner_factory(tracker, created_runners)
    requests = [f"compute {i}" for i in range(n)]

    with patch("google.adk.runners.Runner", fake_runner):
        results = await asyncio.wait_for(
            asyncio.gather(
                *[
                    numerical_analyst_tool.run_async(
                        args={"request": req},
                        tool_context=_make_tool_context(user_id=f"u{i}"),
                    )
                    for i, req in enumerate(requests)
                ]
            ),
            timeout=10,
        )

    # All N calls were in-flight simultaneously — genuinely concurrent.
    assert tracker.max_in_flight == n
    # Each call returned its own input — no state bleed through the shared tool.
    assert sorted(results) == [f"echo:{req}" for req in requests]
    # One shared AgentTool fanned out into N isolated leaf runs.
    assert len(created_runners) == n
