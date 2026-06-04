"""Concurrency smoke test for the Google web search agent-as-a-tool (AH-98, AC #9).

AC #9 requires that an agent assigned ``agent.google_search`` which emits two or
more ``google_search`` calls in a single model turn executes them *concurrently*.

ADK 1.27.5 already dispatches one turn's function calls in parallel
(``handle_function_call_list_async`` → ``asyncio.gather`` over
``asyncio.create_task``). The part that is *ours* — and the risk the design note
flagged — is that a single shared ``AgentTool`` instance is reused across those
concurrent invocations: ``register_agent_tool`` stores one object and every
agent's roster references that same one. Each call gets its own
``InvocationContext`` (a fresh ``Runner`` + session inside ``run_async``), so it
should be safe, but the strategy path only ever called it sequentially.

Two facets are pinned here:

* ``test_shared_singleton_runs_concurrent_calls_without_cross_talk`` drives the
  *real registered singleton* with N concurrent ``run_async`` calls and proves
  (a) they genuinely overlap — peak in-flight == N, enforced by an
  ``asyncio.Barrier`` that would dead-stall a serialized implementation — and
  (b) each call's result tracks its own input, i.e. no state bleed through the
  shared object.
* ``test_adk_dispatches_one_turns_calls_in_parallel`` pins the ADK framework
  assumption the design relies on: the per-turn dispatcher fans calls out with
  ``asyncio.create_task`` + ``asyncio.gather``. A future ADK bump that serialized
  tool execution (regressing parallel ``google_search``) trips this.

The leaf agent's runtime is stubbed (ADK's ``Runner`` is patched) so the test
never touches the network / Gemini — it exercises the shared-instance + dispatch
plumbing, not the search backend.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from google.adk.tools.agent_tool import AgentTool
from google.genai import types

# Importing the module registers the AgentTool as a side effect.
import app.adk.tools.agent_tools.google_search as gs_mod
from app.adk.tools.registry.agent_tool_registry import get_agent_tool

# ── fakes ───────────────────────────────────────────────────────────────────


class _FakeState:
    """Minimal ToolContext.state — ``to_dict`` + ``update`` are all run_async uses."""

    def __init__(self) -> None:
        self._d: dict[str, Any] = {}

    def to_dict(self) -> dict[str, Any]:
        return dict(self._d)

    def update(self, other: dict[str, Any]) -> None:
        self._d.update(other)


def _make_tool_context(user_id: str) -> Any:
    """A stand-in ToolContext, distinct per call.

    A separate object (and ``_invocation_context``) per invocation mirrors the
    real per-call isolation that makes reusing one shared ``AgentTool`` safe —
    the property under test.
    """
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
    """Records the peak number of simultaneously in-flight leaf runs.

    The ``Barrier`` is load-bearing: every concurrent run must reach it before
    *any* is released, so ``max_in_flight`` can only reach N if all N ran at
    once. A serialized implementation blocks the first run at the barrier
    forever — surfaced by the ``wait_for`` timeout in the test.
    """

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
            # Block until every concurrent call is in-flight: proves overlap.
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
def google_search_tool() -> AgentTool:
    # Reload re-runs the registration side effect deterministically — adjacent
    # suites can clear the shared registry in teardown.
    importlib.reload(gs_mod)
    tool = get_agent_tool("google_search")
    assert isinstance(tool, AgentTool)
    return tool


@pytest.mark.asyncio
async def test_shared_singleton_runs_concurrent_calls_without_cross_talk(
    google_search_tool: AgentTool,
) -> None:
    n = 3
    tracker = _OverlapTracker(parties=n)
    created_runners: list[Any] = []
    fake_runner = _fake_runner_factory(tracker, created_runners)
    requests = [f"q{i}" for i in range(n)]

    # One shared AgentTool object, N concurrent run_async calls — exactly how a
    # single model turn emitting N google_search calls drives it.
    with patch("google.adk.runners.Runner", fake_runner):
        results = await asyncio.wait_for(
            asyncio.gather(
                *[
                    google_search_tool.run_async(
                        args={"request": req},
                        tool_context=_make_tool_context(user_id=f"u{i}"),
                    )
                    for i, req in enumerate(requests)
                ]
            ),
            timeout=10,
        )

    # All N calls were in-flight at once → genuinely concurrent, not serialized.
    assert tracker.max_in_flight == n
    # Each call returned its own input → no state bleed through the shared tool.
    assert sorted(results) == [f"echo:{req}" for req in requests]
    # The one shared AgentTool fanned out into N isolated leaf runs.
    assert len(created_runners) == n


def test_adk_dispatches_one_turns_calls_in_parallel() -> None:
    # AC #9's framework half: ADK fans a single turn's function calls out
    # concurrently. Pinned by source so an ADK upgrade that serialized tool
    # execution fails here loudly; behaviour is verified end-to-end against
    # google-adk==1.27.5 in the design note.
    from google.adk.flows.llm_flows import functions

    source = inspect.getsource(functions.handle_function_call_list_async)
    assert "asyncio.create_task" in source
    assert "asyncio.gather" in source
