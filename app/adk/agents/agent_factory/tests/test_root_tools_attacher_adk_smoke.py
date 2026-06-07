"""ADK behaviour spike: confirm mid-callback root.tools mutation is honoured on the
same turn in google-adk==1.27.5.

Spike result (Task 1 from AH-100):
    PASS — mutating ``agent.tools`` inside a ``before_agent_callback`` IS picked
    up on the same invocation turn.

    Evidence from ADK source (1.27.5):
    * ``base_agent.py:291`` — ``_handle_before_agent_callback`` fires *before*
      ``_run_async_impl``.
    * ``base_llm_flow.py:418-441`` — ``_process_agent_tools`` reads
      ``agent.tools`` directly at LLM-request build time (no early snapshot or
      per-invocation cache).
    * ``invocation_context.py:214`` — ``canonical_tools_cache`` is populated
      only inside ``_maybe_add_grounding_metadata`` (grounding metadata path),
      not before the LLM request is assembled.

    Therefore: ``root.tools = [new_list]`` inside a ``before_agent_callback``
    exposes the mutated list to ``_process_agent_tools`` on the same turn.
    The same reasoning that makes per-turn ``root.sub_agents`` mutation work
    (AH-75 / ``sub_agent_attacher.py``) applies equally to ``root.tools``.

    This module also contains a live runner test that confirms the behaviour
    against a real (mock-model) ADK Runner so the conclusion is observable
    rather than just reasoned.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from google.adk.agents import LlmAgent
from google.adk.tools.function_tool import FunctionTool

if TYPE_CHECKING:
    from google.adk.agents.callback_context import CallbackContext


# ---------------------------------------------------------------------------
# Minimal test tool — used as the "tools added by the callback" sentinel
# ---------------------------------------------------------------------------


def _search_web(query: str) -> str:  # pragma: no cover — never called by the mock model
    """Stub: returns a fake search result."""
    return f"result for: {query}"


_SEARCH_TOOL = FunctionTool(func=_search_web)


# ---------------------------------------------------------------------------
# Spike: static structural proof that the mutation path is sound
# ---------------------------------------------------------------------------


class TestADKToolsMutationStaticProof:
    """Structural verification without a live Runner.

    Confirms the three properties identified in the spike above hold for the
    installed google-adk version: (1) ``before_agent_callback`` fires before
    ``_run_async_impl``; (2) ``_process_agent_tools`` reads ``agent.tools``
    without a pre-invocation snapshot; (3) ``canonical_tools_cache`` is not
    set before the LLM request is assembled.
    """

    def test_before_agent_callback_fires_before_run_async_impl(self) -> None:
        """``base_agent.run_async`` calls ``_handle_before_agent_callback``
        before ``_run_async_impl`` — confirmed from the ADK source read order."""
        import inspect

        from google.adk.agents.base_agent import BaseAgent

        src = inspect.getsource(BaseAgent.run_async)
        before_idx = src.index("_handle_before_agent_callback")
        run_impl_idx = src.index("_run_async_impl")
        assert before_idx < run_impl_idx, (
            "Expected _handle_before_agent_callback to appear before "
            "_run_async_impl in BaseAgent.run_async"
        )

    def test_process_agent_tools_reads_from_agent_tools_directly(self) -> None:
        """``_process_agent_tools`` reads ``agent.tools`` without a snapshot."""
        import inspect

        from google.adk.flows.llm_flows import base_llm_flow

        src = inspect.getsource(base_llm_flow._process_agent_tools)
        # The function reads ``agent.tools`` at LLM-request build time.
        assert "agent.tools" in src, (
            "_process_agent_tools must read agent.tools; if it no longer does, "
            "the per-turn root-tool-mutation pattern requires re-validation."
        )
        # It must NOT cache the result before iterating.
        # (If a ``tools_snapshot = agent.tools`` line were added upstream of the
        # iteration, the per-turn mutation pattern would break.)
        assert "tools_snapshot" not in src, (
            "Unexpected 'tools_snapshot' in _process_agent_tools — check whether "
            "ADK now pre-snapshots tools before the callback fires."
        )

    def test_canonical_tools_cache_not_read_inside_process_agent_tools(self) -> None:
        """``_process_agent_tools`` does NOT read ``canonical_tools_cache`` — it
        reads ``agent.tools`` directly. This confirms the cache cannot bypass a
        mid-callback ``agent.tools`` mutation."""
        import inspect

        from google.adk.flows.llm_flows import base_llm_flow

        src = inspect.getsource(base_llm_flow._process_agent_tools)
        # The function must NOT reference the invocation-context cache.
        assert "canonical_tools_cache" not in src, (
            "_process_agent_tools must not read canonical_tools_cache; if it now "
            "does, a pre-callback snapshot would bypass the per-turn mutation."
        )


# ---------------------------------------------------------------------------
# Spike: live Runner confirmation that tools mutated in before_agent_callback
# are visible to the LLM on the same turn
# ---------------------------------------------------------------------------


class TestMutationHonouredOnSameTurn:
    """End-to-end confirmation against a mock-model Runner.

    AH-108 probe result (google-adk==2.0.0):
        Path 1 confirmed — ``_invocation_context.agent`` in ADK 2.0 IS the
        per-turn clone, so a ``before_agent_callback`` that mutates
        ``agent.tools`` via attribute reassignment IS visible to
        ``_process_agent_tools`` on the same invocation (the LLM request
        carries the tool declarations).  The tool mutation does NOT propagate
        back to the original agent object (the original's ``tools`` stays
        ``[]``), so the pre-existing xfail test below remains xfailing — the
        *original-agent* assertion is the wrong invariant for production.

        The production-relevant invariant — "the LLM sees the mutated tools
        mid-turn" — is captured by ``test_llm_sees_mutated_tools_on_same_turn``
        (Task 1 probe), which passes.  Tasks 3a/4a apply the two consistency
        cleanups: in-place slice assignment + populated-guard (so a fresh
        per-turn clone with ``tools=[]`` that hits the hash-fingerprint cache
        still gets its tools resolved).
    """

    def test_llm_sees_mutated_tools_on_same_turn(self) -> None:
        """AH-108 Task 1 probe: the mock LLM's llm_request.tools_dict contains
        the tool appended by the before_agent_callback — i.e. the LLM-observable
        production property holds on google-adk==2.0.0.

        This is the correct invariant for the AH-100 mechanism: what matters is
        that the LLM call site sees the mutated tool list on the same invocation,
        not whether the original agent's ``.tools`` attribute is updated after
        the turn (the clone-doesn't-propagate-back xfail below covers that).
        """
        received_tools: list[Any] = []

        def _adding_callback(*, callback_context: CallbackContext) -> None:  # type: ignore[misc]
            agent = callback_context._invocation_context.agent
            agent.tools = [_SEARCH_TOOL]
            return None

        agent = LlmAgent(
            name="spike_root",
            model="gemini-2.0-flash",
            instruction="You are a test agent.",
            tools=[],
            before_agent_callback=_adding_callback,
        )

        _run_one_turn_with_mock_model(agent, user_text="hello", received_tools=received_tools)

        # The LLM request must contain the tool declaration injected by the callback.
        assert len(received_tools) > 0, (
            "LLM did not receive any tool declarations — the before_agent_callback "
            "mutation was not visible to _process_agent_tools on this turn. "
            "This would mean Path 2 (re-resolving toolset fallback) is required."
        )
        assert "_search_web" in received_tools, (
            f"Expected '_search_web' in llm_request.tools_dict keys; got {received_tools!r}"
        )

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "ADK 2.0: Runner.build_node().clone() creates a per-turn clone whose "
            "tool mutations do not propagate back to the original agent object. "
            "The production-relevant invariant ('LLM sees the mutated tools mid-turn') "
            "is covered by test_llm_sees_mutated_tools_on_same_turn (which passes). "
            "This test's post-turn original-agent assertion is intentionally left "
            "as a permanent xfail to document the ADK 2.0 clone semantics."
        ),
    )
    def test_tools_mutated_in_before_callback_are_on_agent_after_turn(self) -> None:
        """Documents that tool mutations inside before_agent_callback do NOT
        persist on the original agent object under ADK 2.0 (clone semantics).

        The original agent's ``tools`` remains ``[]`` after the turn because the
        callback mutates the per-turn clone, which is discarded after the turn.
        This is expected behaviour on ADK 2.0 and does NOT indicate a production
        bug — see test_llm_sees_mutated_tools_on_same_turn for the production check.
        """
        received_tools: list[Any] = []

        def _adding_callback(*, callback_context: CallbackContext) -> None:  # type: ignore[misc]
            agent = callback_context._invocation_context.agent
            agent.tools = [_SEARCH_TOOL]
            return None

        agent = LlmAgent(
            name="spike_root",
            model="gemini-2.0-flash",
            instruction="You are a test agent.",
            tools=[],
            before_agent_callback=_adding_callback,
        )

        assert agent.tools == []
        _run_one_turn_with_mock_model(agent, user_text="hello", received_tools=received_tools)

        # This assertion FAILS on ADK 2.0 (xfail): the original agent's tools
        # are not updated because only the per-turn clone was mutated.
        assert len(agent.tools) == 1
        assert agent.tools[0] is _SEARCH_TOOL


def _run_one_turn_with_mock_model(
    agent: LlmAgent,
    user_text: str,
    received_tools: list[Any],
) -> None:
    """Drive a single turn through a minimal synchronous Runner wrapper.

    Uses the in-memory session service so no real infrastructure is needed.
    The mock model emits one plain-text response and records the tools list it
    would have received.  Fires ``before_agent_callback`` as a real turn would.
    """
    import asyncio

    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    async def _run() -> None:
        session_service = InMemorySessionService()
        session = await session_service.create_session(
            app_name="spike_test", user_id="u1"
        )

        # Minimal mock model: records tool declarations from llm_request and
        # returns a plain-text response so the flow completes.
        mock_model = MagicMock()
        mock_model.model = "gemini-2.0-flash"

        async def _generate(*args: Any, **kwargs: Any):  # type: ignore[misc]
            from google.adk.models import LlmResponse
            from google.genai import types

            llm_request = args[0] if args else kwargs.get("llm_request")
            if llm_request and hasattr(llm_request, "tools_dict"):
                received_tools.extend(llm_request.tools_dict.keys())

            resp = LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part(text="ok")],
                )
            )
            yield resp

        mock_model.generate_content_async = _generate

        with patch.object(type(agent), "canonical_model", new_callable=lambda: property(lambda self: mock_model)):
            runner = Runner(
                app_name="spike_test",
                agent=agent,
                session_service=session_service,
            )
            from google.genai import types as gtypes

            user_msg = gtypes.Content(
                role="user",
                parts=[gtypes.Part(text=user_text)],
            )
            async for _ in runner.run_async(
                user_id="u1",
                session_id=session.id,
                new_message=user_msg,
            ):
                pass

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# AH-117: production-path gate — the REAL before_agent_callback must expose the
# task-mode delegation tool to the LLM on the same turn.
#
# This is the honest, production-wiring counterpart to the construct-time billing
# gate (TestAgentGoogleSearchTaskModeParity). It drives a real Runner turn whose
# root carries the REAL ``attach_root_tools_before_agent_callback`` and asserts
# the LLM request carries the ``google_search`` task-delegation tool. Before the
# AH-117 fix the callback added the sub-agent to ``sub_agents`` but NOT the
# ``_TaskAgentTool`` to ``tools``, so the LLM never saw ``request_task_<name>``
# and the delegation (plus its billing) silently never fired.
# ---------------------------------------------------------------------------


class TestTaskModeDelegationToolReachesLLM:
    def test_real_callback_exposes_request_task_tool_to_llm(self) -> None:
        import importlib

        from app.adk.agents.agent_factory import root_tools_attacher as rta
        from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
        from app.adk.tools.registry.agent_tool_registry import (
            clear_agent_tool_registry,
            register_agent_subagent,
            task_mode_supported,
        )

        if not task_mode_supported():
            pytest.skip("task-mode sub-agents require ADK 2.0+")

        from app.adk.tools.agent_tools.google_search import (
            create_google_search_subagent,
        )

        clear_agent_tool_registry()
        register_agent_subagent("google_search", create_google_search_subagent)
        rta._reset_applied_hash_for_tests()

        cfg = MergedAgentConfig(
            instruction="Root.",
            model="gemini-2.0-flash",
            description="root",
            mcp_servers=[],
            tool_ids=["agent.google_search"],
        )

        received_tools: list[Any] = []
        try:
            agent = LlmAgent(
                name="ken_e",
                model="gemini-2.0-flash",
                instruction="You are a test root agent.",
                tools=[],
                before_agent_callback=rta.attach_root_tools_before_agent_callback,
            )
            with patch.object(rta, "get_cached_merged_config", return_value=cfg):
                _run_one_turn_with_mock_model(
                    agent, user_text="hello", received_tools=received_tools
                )
        finally:
            clear_agent_tool_registry()
            rta._reset_applied_hash_for_tests()
            # Restore production registrations for adjacent suites (process-global).
            import app.adk.tools.agent_tools.google_search as _gs
            import app.adk.tools.agent_tools.numerical_analyst as _na

            importlib.reload(_gs)
            importlib.reload(_na)

        assert "google_search" in received_tools, (
            "The real attach_root_tools_before_agent_callback must expose the "
            "google_search task-delegation tool to the LLM on the same turn; got "
            f"tools_dict keys={received_tools!r}. Without it the LLM cannot emit "
            "request_task_google_search and the search sub-agent's tokens go "
            "uncounted (AH-117)."
        )
