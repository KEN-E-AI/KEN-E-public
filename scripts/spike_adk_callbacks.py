"""ADK 1.27.5 callback spike — confirm signatures and nested-firing semantics.

Empirically answers three questions for CH-PRD-01 (session metadata substrate):

  a. What are the exact before_agent_callback / after_agent_callback signatures?
  b. Does ADK fire these callbacks on nested sub-agents, or only on the agent
     they are registered on?
  c. Is `callback_context._invocation_context.agent.parent_agent is None` the
     canonical way to detect a root invocation?

Runs without GCP credentials or an LLM — uses BaseAgent subclasses whose
_run_async_impl yields a single no-op event, plus InMemorySessionService.

Usage:
    cd /home/agent/workspace/app/adk
    uv run python ../../scripts/spike_adk_callbacks.py
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable
from typing import TYPE_CHECKING

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.events.event import Event
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

if TYPE_CHECKING:
    from google.adk.agents.callback_context import CallbackContext

# ---------------------------------------------------------------------------
# Observation log — records every callback firing in order.
# ---------------------------------------------------------------------------

firing_log: list[dict[str, object]] = []


def _make_callback(label: str) -> Callable[[CallbackContext], types.Content | None]:
    """Return a before/after agent callback that logs its firing details."""

    def callback(callback_context: CallbackContext) -> types.Content | None:
        inv_ctx = getattr(callback_context, "_invocation_context", None)

        agent_name = "?"
        parent_agent = "?"
        invocation_id = "?"

        if inv_ctx is not None:
            agent = getattr(inv_ctx, "agent", None)
            if agent is not None:
                agent_name = agent.name
                raw_parent = getattr(agent, "parent_agent", "ATTR_MISSING")
                # Confirm parent_agent attribute exists and what it contains
                if raw_parent == "ATTR_MISSING":
                    parent_agent = "ATTR_MISSING"
                elif raw_parent is None:
                    parent_agent = None
                else:
                    parent_agent = getattr(raw_parent, "name", repr(raw_parent))
            invocation_id = getattr(inv_ctx, "invocation_id", "?")

        entry = {
            "label": label,
            "agent_name": agent_name,
            "parent_agent": parent_agent,
            "invocation_id": invocation_id,
        }
        firing_log.append(entry)
        print(
            f"  CALLBACK FIRED: label={label!r:25s} "
            f"agent={agent_name!r:12s} "
            f"parent_agent={str(parent_agent)!r:12s} "
            f"invocation_id={str(invocation_id)[:16]!r}"
        )
        return None  # do not intercept the agent run

    return callback


# ---------------------------------------------------------------------------
# Minimal no-op BaseAgent subclasses (no LLM required).
# ---------------------------------------------------------------------------


class SpikeAgent(BaseAgent):
    """A no-op agent that yields a single empty event and exits."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        # Yield one minimal event so the runner sees activity.
        yield Event(author=self.name, content=None)


# ---------------------------------------------------------------------------
# Experiment 1: Callbacks registered on root only.
#
# Expected: only root's before/after fire. Nested agent (via SequentialAgent
# sub_agents) fires its own callbacks only if IT has callbacks registered.
# ---------------------------------------------------------------------------


async def experiment_1_root_only_registration() -> None:
    """Register callbacks on root only; observe that nested agent does NOT fire them."""
    print("\n=== Experiment 1: callbacks on root only ===")
    firing_log.clear()

    nested = SpikeAgent(name="nested", description="nested agent")
    root = SequentialAgent(
        name="root",
        description="root sequential agent",
        sub_agents=[nested],
        before_agent_callback=_make_callback("root.before"),
        after_agent_callback=_make_callback("root.after"),
    )

    session_svc = InMemorySessionService()
    runner = Runner(
        app_name="spike_test",
        agent=root,
        session_service=session_svc,
    )

    session = await session_svc.create_session(
        app_name="spike_test", user_id="spike_user"
    )
    async for _ in runner.run_async(
        user_id="spike_user",
        session_id=session.id,
        new_message=types.Content(parts=[types.Part(text="hello")]),
    ):
        pass

    print(f"\n  Firing order: {[e['label'] for e in firing_log]}")
    assert firing_log[0]["label"] == "root.before", "root.before must fire first"
    assert firing_log[-1]["label"] == "root.after", "root.after must fire last"
    assert not any(e["label"].startswith("nested") for e in firing_log), (
        "No nested callbacks registered → none should fire"
    )
    print("  ✓ Only root.before / root.after fired (nested had no callbacks).")


# ---------------------------------------------------------------------------
# Experiment 2: Callbacks on BOTH root and nested.
#
# Expected: root.before → nested.before → nested.after → root.after
# This mirrors AH-PRD-02's pattern of registering callbacks on every agent.
# ---------------------------------------------------------------------------


async def experiment_2_callbacks_on_every_agent() -> None:
    """Register callbacks on every agent; observe firing order and parent_agent values."""
    print("\n=== Experiment 2: callbacks on every agent (AH-PRD-02 pattern) ===")
    firing_log.clear()

    nested = SpikeAgent(
        name="nested",
        description="nested agent",
        before_agent_callback=_make_callback("nested.before"),
        after_agent_callback=_make_callback("nested.after"),
    )
    root = SequentialAgent(
        name="root",
        description="root sequential agent",
        sub_agents=[nested],
        before_agent_callback=_make_callback("root.before"),
        after_agent_callback=_make_callback("root.after"),
    )

    session_svc = InMemorySessionService()
    runner = Runner(
        app_name="spike_test2",
        agent=root,
        session_service=session_svc,
    )

    session = await session_svc.create_session(
        app_name="spike_test2", user_id="spike_user2"
    )
    async for _ in runner.run_async(
        user_id="spike_user2",
        session_id=session.id,
        new_message=types.Content(parts=[types.Part(text="hello")]),
    ):
        pass

    labels = [e["label"] for e in firing_log]
    print(f"\n  Firing order: {labels}")
    assert labels == [
        "root.before",
        "nested.before",
        "nested.after",
        "root.after",
    ], f"Unexpected firing order: {labels}"

    # Confirm parent_agent values
    root_before = next(e for e in firing_log if e["label"] == "root.before")
    nested_before = next(e for e in firing_log if e["label"] == "nested.before")

    assert root_before["parent_agent"] is None, (
        f"root.parent_agent should be None, got {root_before['parent_agent']!r}"
    )
    assert nested_before["parent_agent"] == "root", (
        f"nested.parent_agent should be 'root', got {nested_before['parent_agent']!r}"
    )

    print(
        "  ✓ Firing order correct: root.before → nested.before → nested.after → root.after"
    )
    print(f"  ✓ root.parent_agent = {root_before['parent_agent']!r} (None ↔ is root)")
    print(
        f"  ✓ nested.parent_agent = {nested_before['parent_agent']!r} (non-None ↔ is nested)"
    )


# ---------------------------------------------------------------------------
# Experiment 3: Root-only guard correctness.
#
# Simulate Chat's pattern: Chat registers on every agent (via AH-PRD-02),
# but the callback itself filters to root-only using the parent_agent check.
# Verify the guard prevents nested firings from being processed.
# ---------------------------------------------------------------------------


async def experiment_3_root_guard() -> None:
    """Chat's root-only guard: skip callback body when parent_agent is not None."""
    print("\n=== Experiment 3: root-only guard via parent_agent check ===")
    root_guard_log: list[str] = []

    def chat_before_callback(
        callback_context: CallbackContext,
    ) -> types.Content | None:
        inv_ctx = getattr(callback_context, "_invocation_context", None)
        agent = getattr(inv_ctx, "agent", None) if inv_ctx else None
        parent_agent = getattr(agent, "parent_agent", None) if agent else None

        # Root-only guard: skip nested invocations.
        if parent_agent is not None:
            return None  # defensive no-op

        agent_name = getattr(agent, "name", "?")
        root_guard_log.append(f"processed:{agent_name}")
        return None

    nested = SpikeAgent(
        name="nested2",
        description="nested agent for guard test",
        before_agent_callback=chat_before_callback,
    )
    root = SequentialAgent(
        name="root2",
        description="root sequential agent for guard test",
        sub_agents=[nested],
        before_agent_callback=chat_before_callback,
    )

    session_svc = InMemorySessionService()
    runner = Runner(
        app_name="spike_test3",
        agent=root,
        session_service=session_svc,
    )

    session = await session_svc.create_session(
        app_name="spike_test3", user_id="spike_user3"
    )
    async for _ in runner.run_async(
        user_id="spike_user3",
        session_id=session.id,
        new_message=types.Content(parts=[types.Part(text="hello")]),
    ):
        pass

    print(f"  root_guard_log (only root-level executions): {root_guard_log}")
    assert root_guard_log == ["processed:root2"], (
        f"Guard should allow only root; got {root_guard_log}"
    )
    print(
        "  ✓ Root-only guard works: nested.before callback skipped; root.before callback ran."
    )


# ---------------------------------------------------------------------------
# Experiment 4: Confirm callback_context attributes exposed publicly.
# ---------------------------------------------------------------------------


async def experiment_4_callback_context_attrs() -> None:
    """Confirm what attributes are accessible on CallbackContext."""
    print("\n=== Experiment 4: CallbackContext attribute inventory ===")
    observed_attrs: dict[str, object] = {}

    def inspect_callback(
        callback_context: CallbackContext,
    ) -> types.Content | None:
        # Public ReadonlyContext properties
        observed_attrs["agent_name"] = callback_context.agent_name
        observed_attrs["invocation_id"] = callback_context.invocation_id
        observed_attrs["has_state"] = hasattr(callback_context, "state")

        # Private _invocation_context access (matches existing weave pattern)
        inv_ctx = getattr(callback_context, "_invocation_context", None)
        observed_attrs["has_invocation_context"] = inv_ctx is not None
        if inv_ctx is not None:
            agent = getattr(inv_ctx, "agent", None)
            observed_attrs["inv_ctx.agent.name"] = getattr(agent, "name", None)
            observed_attrs["inv_ctx.agent.parent_agent"] = getattr(
                agent, "parent_agent", "ATTR_MISSING"
            )

        return None

    simple_agent = SpikeAgent(
        name="simple",
        description="simple agent",
        before_agent_callback=inspect_callback,
    )

    session_svc = InMemorySessionService()
    runner = Runner(
        app_name="spike_test4",
        agent=simple_agent,
        session_service=session_svc,
    )
    session = await session_svc.create_session(
        app_name="spike_test4", user_id="spike_user4"
    )
    async for _ in runner.run_async(
        user_id="spike_user4",
        session_id=session.id,
        new_message=types.Content(parts=[types.Part(text="hello")]),
    ):
        pass

    for k, v in observed_attrs.items():
        print(f"  {k}: {v!r}")

    assert observed_attrs.get("agent_name") == "simple"
    assert observed_attrs.get("has_invocation_context") is True
    assert observed_attrs.get("inv_ctx.agent.name") == "simple"
    assert observed_attrs.get("inv_ctx.agent.parent_agent") is None
    assert "inv_ctx.agent.parent_agent" in observed_attrs, (
        "parent_agent attribute must exist on BaseAgent"
    )
    print(
        "  ✓ CallbackContext provides .agent_name (public) and ._invocation_context.agent.parent_agent (private)"
    )


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


async def main() -> None:
    print("=== ADK 1.27.5 Callback Spike ===")
    print("Verifying before_agent_callback / after_agent_callback semantics.\n")

    await experiment_1_root_only_registration()
    await experiment_2_callbacks_on_every_agent()
    await experiment_3_root_guard()
    await experiment_4_callback_context_attrs()

    print("\n=== All experiments passed ===")
    print()
    print("SUMMARY (for docs/spike-adk-chat-callbacks.md):")
    print("  1. Callbacks are per-agent: a callback registered on agent A fires only")
    print("     when A itself runs (not when A's sub-agents run).")
    print("  2. When callbacks ARE registered on every agent (AH-PRD-02 pattern),")
    print(
        "     firing order is: root.before → nested.before → nested.after → root.after"
    )
    print(
        "  3. Root detection: callback_context._invocation_context.agent.parent_agent is None"
    )
    print("     → True for root, False (non-None BaseAgent) for nested agents.")
    print("  4. The attribute name is `parent_agent` (NOT `parent`).")
    print("     PRD §5.2 must be amended: agent.parent → agent.parent_agent")
    print("  5. callback_context.agent_name is a public shortcut (read-only); the full")
    print("     parent-detection path requires the private _invocation_context field.")


if __name__ == "__main__":
    asyncio.run(main())
