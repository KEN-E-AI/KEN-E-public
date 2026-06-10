# ADK 2.0 Mixed-Turn Function-Call Drop — Spike & Upstream Issue Draft

**Status:** Complete — upstream issue body ready for PO submission  
**ADK version under test:** 2.0.0  
**KEN-E issue:** [AH-164](https://linear.app/ken-e/issue/AH-164)  
**Date:** 2026-06-10  
**Related PR:** [#973](https://github.com/KEN-E-AI/KEN-E/pull/973) (mitigation — `repair_orphaned_function_calls_before_model`)  
**Upstream tracker:** [`docs/adk-upstream-tracker.md`](./adk-upstream-tracker.md)

---

## Overview

When an `LlmAgent(mode='chat')` coordinator emits a model turn containing **both** a regular
function call (e.g., `set_todo_list`) and one or more task-delegation function calls (to
`LlmAgent(mode='task')` sub-agents), ADK 2.0's chat-mode wrapper breaks out of the agent's
event generator after handling the task FCs, silently discarding the pending
function-response event for the regular tool.

The session then holds a model turn with N function calls but only N−1 (or fewer) function
responses. Every subsequent request that replays that history hits Gemini's strict
FC/FR-count check and fails:

```
400 INVALID_ARGUMENT: Please ensure that the number of function response parts
is equal to the number of function call parts
```

The session is permanently poisoned from that point on.

This was latent on `gemini-2.5-pro`, which rarely emits regular and task FCs in the same
parallel turn. `gemini-3.1-pro-preview` does so routinely and ignores the per-tool "do NOT
call this tool in parallel with any other tools" declaration hint that
`_TaskAgentTool._get_declaration` injects.

The mitigation shipped in PR #973
(`repair_orphaned_function_calls_before_model` root `before_model_callback`) makes
affected sessions survivable by padding synthetic "interrupted" responses before each
outgoing request. The callback is intentionally kept permanently — see
[`docs/adk-upstream-tracker.md`](./adk-upstream-tracker.md) and
`app/adk/agents/agent_factory/content_repair.py` for rationale.

---

## Bug Location

**File:** `google/adk/workflow/_llm_agent_wrapper.py`  
**Lines:** 379–388 (ADK 2.0.0)

```python
# Step 2: run parent.run_async; on every fresh task FC, dispatch
# and re-enter parent.run_async with the FR in session.
while True:
    had_task_fc = False
    transferred = False
    run_method = agent.run_live(ic) if is_live else agent.run_async(ic)
    async with aclosing(run_method) as run_iter:
        async for event in run_iter:
            yield event
            task_fcs = _extract_task_delegation_fcs(event, tools_dict)
            for fc in task_fcs:
                output = await _dispatch_task_fc(agent, fc, ctx)
                yield _synthesize_task_fr_event(fc, output)
            if task_fcs:
                had_task_fc = True
                break  # ← closes run_iter; any unread events are dropped
```

The `break` at line 388 closes the `aclosing()` context, discarding all unread events from
`run_iter`. When the model turn includes a regular FC alongside the task FCs, the
framework's `functions.py` flow has queued a function-response event for the regular tool
(because `_defers_response` is `False` for regular tools), but the wrapper never reads it.

**Interplay with `_defers_response` (`flows/llm_flows/functions.py:579-587`):**

```python
if (
    tool.is_long_running or tool._defers_response
) and not function_response:
    # Tool defers its FR by design — skip auto-FR build.
    return None
```

`_TaskAgentTool._defers_response = True` (set in `agent_tool.py:389`), so the task-dispatch
tools return `None` here and the wrapper handles their FRs externally via
`_synthesize_task_fr_event`. The regular tool (`set_todo_list`) is NOT deferred
(`_defers_response = False`), so its FR event IS built and queued in the generator — but
the `break` ensures it is never read.

---

## Event Sequence: Expected vs. Actual

For a model turn with `set_todo_list` + two task-dispatch FCs (`ga_specialist`,
`meta_specialist`):

**Expected (correct behaviour):**

```
1.  model_event          {parts: [FC:set_todo_list, FC:ga_specialist, FC:meta_specialist]}
2.  user_event           {parts: [FR:set_todo_list]}        ← regular tool answered
3.  user_event           {parts: [FR:ga_specialist]}        ← task FC synthesised
4.  user_event           {parts: [FR:meta_specialist]}      ← task FC synthesised
5.  model_event          {"Synthesising results…"}
```

**Actual (ADK 2.0.0):**

```
1.  model_event          {parts: [FC:set_todo_list, FC:ga_specialist, FC:meta_specialist]}
                              ↑ all three FCs persisted to session
2.  <run_iter closed>    FR:set_todo_list is in the generator's pending output but discarded
3.  user_event           {parts: [FR:ga_specialist]}        ← task FC synthesised by wrapper
4.  user_event           {parts: [FR:meta_specialist]}      ← task FC synthesised by wrapper
5.  <next turn>          400 INVALID_ARGUMENT — 3 FCs, 2 FRs in history
```

`set_todo_list` never executes. Its ledger write is silently skipped. The model is told
the call was "interrupted" (via the PR #973 repair callback) and may retry.

---

## Minimal Repro Program

Runs against `google-adk==2.0.0`. Uses a hand-authored model response so the bug is
deterministic regardless of model behaviour.

```python
"""
Minimal repro: ADK 2.0.0 mixed-turn function-call drop.

Demonstrates that a regular FunctionTool's function-response event is silently
dropped when the model emits both a regular FC and a task-delegation FC in the
same turn.

Run (after copying this code block to a file):
    cd app/adk && uv run python /path/to/repro_mixed_turn.py

Expected: prints "FAIL: set_todo_list FR absent from session events (bug confirmed)"
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.models.registry import LLMRegistry
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.tools.function_tool import FunctionTool
from google.genai import types

# ──────────────────────────────────────────────────────────────────────────────
# Stub LLMs
# ──────────────────────────────────────────────────────────────────────────────

_REGULAR_TOOL_NAME = "set_todo_list"
_TASK_AGENT_NAME = "ga_specialist"

# The model ID registered below — the coordinator's stub emits ONE turn with
# both FCs, then a follow-up text turn.
_COORDINATOR_MODEL_ID = "stub-coordinator-mixed-turn"

_CALL_COUNT: list[int] = [0]


class _CoordinatorStubLlm(BaseLlm):
    """Emits a hand-authored model response with a regular FC + task-dispatch FC."""

    @classmethod
    def supported_models(cls) -> list[str]:
        return [_COORDINATOR_MODEL_ID]

    async def generate_content_async(
        self,
        llm_request: LlmRequest,
        stream: bool = False,
    ) -> AsyncIterator[LlmResponse]:
        _CALL_COUNT[0] += 1
        if _CALL_COUNT[0] == 1:
            # First turn: emit both a regular FC and a task-dispatch FC.
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            function_call=types.FunctionCall(
                                name=_REGULAR_TOOL_NAME,
                                args={"items": ["write upstream bug report"]},
                                id="fc-todo-001",
                            )
                        ),
                        types.Part(
                            function_call=types.FunctionCall(
                                name=_TASK_AGENT_NAME,
                                args={"request": "analyse GA traffic"},
                                id="fc-ga-001",
                            )
                        ),
                    ],
                ),
            )
        else:
            # Subsequent turn after the FRs land: emit a final text response.
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part(text="Done. Todo written and GA analysed.")],
                ),
                turn_complete=True,
            )


# The task-mode sub-agent's stub LLM just emits a text completion immediately.
_TASK_MODEL_ID = "stub-task-specialist"


class _TaskStubLlm(BaseLlm):
    @classmethod
    def supported_models(cls) -> list[str]:
        return [_TASK_MODEL_ID]

    async def generate_content_async(
        self,
        llm_request: LlmRequest,
        stream: bool = False,
    ) -> AsyncIterator[LlmResponse]:
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text="GA analysis complete.")],
            ),
            turn_complete=True,
        )


LLMRegistry.register(_CoordinatorStubLlm)
LLMRegistry.register(_TaskStubLlm)

# ──────────────────────────────────────────────────────────────────────────────
# Agent setup
# ──────────────────────────────────────────────────────────────────────────────


def set_todo_list(items: list[str]) -> dict[str, Any]:
    """Regular function tool — writes the todo list to session state."""
    return {"status": "ok", "items_written": items}


def _build_agents() -> LlmAgent:
    task_specialist = LlmAgent(
        name=_TASK_AGENT_NAME,
        mode="task",
        model=_TASK_MODEL_ID,
        instruction="You are a GA analyst.",
    )
    coordinator = LlmAgent(
        name="coordinator",
        mode="chat",
        model=_COORDINATOR_MODEL_ID,
        instruction=(
            "You coordinate tasks. Use set_todo_list to record work, "
            "then dispatch to ga_specialist."
        ),
        tools=[FunctionTool(set_todo_list)],
        sub_agents=[task_specialist],
    )
    return coordinator


# ──────────────────────────────────────────────────────────────────────────────
# Main: drive the runner and inspect session events
# ──────────────────────────────────────────────────────────────────────────────


async def _run_repro() -> None:
    svc = InMemorySessionService()
    session = await svc.create_session(app_name="repro", user_id="tester")
    runner = Runner(agent=_build_agents(), app_name="repro", session_service=svc)

    async for _ in runner.run_async(
        user_id=session.user_id,
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text="Write my todo list and analyse GA traffic.")],
        ),
    ):
        pass

    final = await svc.get_session(
        app_name="repro", user_id=session.user_id, session_id=session.id
    )
    events = final.events if final else []

    # Check: is there a function-response event for set_todo_list?
    todo_fr_found = any(
        any(
            p.function_response is not None and p.function_response.name == _REGULAR_TOOL_NAME
            for p in (e.content.parts if e.content else [])
        )
        for e in events
    )

    print("\n── Event dump ──")
    for i, e in enumerate(events):
        role = getattr(e.content, "role", "?") if e.content else "?"
        parts_summary = []
        for p in (e.content.parts if e.content else []):
            if p.function_call:
                parts_summary.append(f"FC:{p.function_call.name}")
            elif p.function_response:
                parts_summary.append(f"FR:{p.function_response.name}")
            elif p.text:
                parts_summary.append(f"text:{p.text[:40]!r}")
        print(f"  [{i}] role={role}  parts={parts_summary}")

    print()
    if not todo_fr_found:
        print(
            "FAIL: set_todo_list FR absent from session events (bug confirmed).\n"
            "The regular tool's function-response was dropped by _llm_agent_wrapper.py:388.\n"
            "FC count in history for the mixed turn: 2; FR count: 1 → 400 on next request."
        )
    else:
        print(
            "PASS: set_todo_list FR present in session events.\n"
            "If this is ADK 2.0.0 the bug may have been patched upstream — re-check."
        )


if __name__ == "__main__":
    asyncio.run(_run_repro())
```

---

## Related-but-Distinct Issue: #3984

[google/adk-python#3984](https://github.com/google/adk-python/issues/3984) documents that
`AgentTool.run_async` spins up a private inner `Runner` and discards all inner events
(including `usage_metadata`) from the outer stream. That is a separate, older issue with
the pre-2.0 `AgentTool` dispatch path. The mixed-turn FC drop described here is a bug in
the **2.0 task-mode wrapper** (`_llm_agent_wrapper.py`) — a different code path, a
different symptom (dropped FR event vs. dropped inner-stream events), and a different
failure class (session poisoning vs. billing gap).

---

## Upstream Issue Draft

The section below contains the exact body to paste into
`https://github.com/google/adk-python/issues/new` once the PO is ready to file.

---

---
> **Paste everything from the title line below into `https://github.com/google/adk-python/issues/new`.**
---

**Title:** `chat-mode wrapper (_llm_agent_wrapper.py) silently drops regular-tool FR when model emits regular FC + task FC in same turn → session poisoning`

---

**Environment**

- Python 3.13
- `google-adk==2.0.0`
- Affected models: `gemini-3.1-pro-preview` (routinely); `gemini-2.5-pro` (rarely)

**Bug description**

When an `LlmAgent(mode='chat')` coordinator emits a model turn containing **both** a
regular function call (non-task tool, e.g. a state-write tool) and one or more
task-delegation function calls (to `LlmAgent(mode='task')` sub-agents), the wrapper in
`_llm_agent_wrapper.py` breaks out of the event generator after handling the task FCs.
The pending function-response event for the regular tool is discarded (never yielded to
the session).

Two effects:

1. **The regular tool never executes.** Its side-effect is silently lost; the model is
   told the call was "interrupted" on the next turn.
2. **Session poisoning.** The session now holds a model turn with N function calls and
   fewer than N function responses. Every subsequent request that replays this history is
   rejected by Gemini:
   `400 INVALID_ARGUMENT: Please ensure that the number of function response parts is equal to the number of function call parts`
   The session cannot recover without external repair.

**Reproduction**

A self-contained Python repro is available at
`docs/spike-adk-mixed-turn-fc-drop.md` in the KEN-E repository (not public). The key
structure:

```python
# Coordinator stub LLM emits this hand-authored model response on the first turn:
types.Content(
    role="model",
    parts=[
        types.Part(function_call=types.FunctionCall(
            name="set_todo_list", args={"items": [...]}, id="fc-todo-001"
        )),
        types.Part(function_call=types.FunctionCall(
            name="ga_specialist", args={...}, id="fc-ga-001"   # task FC
        )),
    ],
)

# After Runner.run_async completes, session.events contains:
#   [model]  FC:set_todo_list  FC:ga_specialist   ← both FCs persisted
#   [user]   FR:ga_specialist                     ← task FR synthesised by wrapper
#   [model]  text:"Done."
#
# FR:set_todo_list is ABSENT.  Next turn → 400.
```

The repro uses a hand-authored model response to prove the bug is in the wrapper, not in
any particular model's parallel-calling behaviour.

**Root cause**

`google/adk/workflow/_llm_agent_wrapper.py`, lines 379–388:

```python
async with aclosing(run_method) as run_iter:
    async for event in run_iter:
        yield event
        task_fcs = _extract_task_delegation_fcs(event, tools_dict)
        for fc in task_fcs:
            output = await _dispatch_task_fc(agent, fc, ctx)
            yield _synthesize_task_fr_event(fc, output)
        if task_fcs:
            had_task_fc = True
            break  # ← closes run_iter; pending FR events are discarded
```

The `break` closes the `aclosing()` context. The regular tool's FR event is produced by
`flows/llm_flows/functions.py` (because `_defers_response` is `False` for regular tools)
and is sitting in the generator's pending output, but the wrapper never reads it.

`_TaskAgentTool._defers_response = True` (`agent_tool.py:389`) so task FCs correctly skip
the auto-FR build in `functions.py:580`. The problem is that the `break` discards
unprocessed events for any _non_-deferred tools in the same turn.

**Expected behaviour**

All regular-tool FRs from a mixed-model-turn should be yielded before breaking out of
`run_iter`. One fix sketch: before the `break`, drain remaining events from `run_iter`
until a model event is reached (non-model events after a mixed turn are the FRs for
non-deferred tools in that same turn).

**Observed behaviour**

The FR for the regular tool is dropped. The session holds an unbalanced FC/FR history that
Gemini permanently rejects.

**Related**

- [#3984](https://github.com/google/adk-python/issues/3984) — `AgentTool.run_async`
  discards inner-stream events (distinct issue: different code path, symptom is billing/
  token gaps rather than session poisoning).
- Declaration hint `_TaskAgentTool._get_declaration` appends "Do NOT call this tool in
  parallel with any other tools." `gemini-3.1-pro-preview` routinely ignores this hint,
  making the bug systematic on that model. The fix should be in the wrapper, not in
  model-instruction workarounds.
