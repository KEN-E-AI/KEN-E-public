"""Probe Q4 — Dynamic-graph fan-out via ctx.run_node; usage_metadata in outer stream. (LIVE)

Tests the dynamic-graph path: an LlmAgent coordinator whose function tool
fans out to two task-mode specialists via ctx.run_node + asyncio.gather.

Run with (from repo root):
    .venv-adk2/bin/python docs/spike-adk2/probe-4-usage-metadata.py

Findings (AH-96 static duck-typing sim, upgraded to live by AH-99):
    Q4 (live): Both fan-out branches' inner events appear in the outer stream
    with non-null usage_metadata.  extract_billable_tokens + SessionTurnAccumulator
    count all inner tokens (billing accuracy improvement vs. ADK 1.x).

Prior static content:
    The AH-96 probe-4 verified extract_billable_tokens duck-typing against a
    mock ADK 2.0 event.  That finding is retained as a docstring note below.
    This rewrite adds the live assertion that confirms the same invariant on
    real Gemini Flash events flowing through the actual ADK 2.0 runtime.

Static finding (carried forward):
    - ADK 2.0 Event.usage_metadata is Optional[GenerateContentResponseUsageMetadata].
    - Two new optional fields in the 2026 genai SDK: tool_use_prompt_token_count,
      traffic_type — silently ignored by extract_billable_tokens via duck-typing.
    - New Event fields: node_info, output, isolation_scope — don't break accounting.

Exit codes:
    0 — both fan-out branches' inner events visible; accumulator > 0; parity holds
    1 — assertion failed (stdout shows which)
    2 — unexpected exception (infrastructure/credential issue)

ADK version required: 2.0.0 (in .venv-adk2/)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _live_harness

print("=== Probe Q4 (live): Dynamic-graph fan-out + usage_metadata ===\n")


def _make_fan_out_tool(
    specialist_a: Any,
    specialist_b: Any,
) -> Any:
    """Build a FunctionTool that fans out to two task-mode specialists via ctx.run_node."""
    from google.adk.tools import FunctionTool

    async def fan_out_analysis(question: str, tool_context: Any) -> str:
        """Dispatch the question to two specialist analysts and combine their answers.

        Args:
            question: The question to analyze from two perspectives.
            tool_context: ADK ToolContext — provides ctx.run_node.

        Returns:
            Combined analysis from both specialists.
        """
        # Fan out to both specialists concurrently — the dynamic-graph path
        result_a, result_b = await asyncio.gather(
            tool_context.run_node(
                specialist_a,
                question,
                override_isolation_scope=f"branch_a_{question[:10]}",
            ),
            tool_context.run_node(
                specialist_b,
                question,
                override_isolation_scope=f"branch_b_{question[:10]}",
            ),
        )
        return f"Specialist A: {result_a}\nSpecialist B: {result_b}"

    return FunctionTool(func=fan_out_analysis)


async def run_probe() -> int:
    """Run the live probe.  Returns exit code (0=pass, 1=fail, 2=error)."""

    extract_billable_tokens, SessionTurnAccumulator = _live_harness.import_real_modules()

    from google.adk.agents.llm_agent import LlmAgent

    # Two task-mode leaf specialists for the fan-out
    specialist_a = LlmAgent(
        name="specialist_a",
        model=_live_harness._DEFAULT_MODEL,
        mode="task",
        instruction="You are Analyst A. Answer the user's question in one sentence from an economic perspective.",
    )
    specialist_b = LlmAgent(
        name="specialist_b",
        model=_live_harness._DEFAULT_MODEL,
        mode="task",
        instruction="You are Analyst B. Answer the user's question in one sentence from a social perspective.",
    )

    fan_out_tool = _make_fan_out_tool(specialist_a, specialist_b)

    coordinator = LlmAgent(
        name="coordinator",
        model=_live_harness._DEFAULT_MODEL,
        mode="chat",
        instruction=(
            "You are a multi-perspective analyst. When given a question, "
            "use the fan_out_analysis tool to get two perspectives, then "
            "summarize both answers in 2-3 sentences."
        ),
        tools=[fan_out_tool],
    )

    runner, user_id = _live_harness.make_runner(coordinator)
    print(f"Session user_id: {user_id}")

    try:
        print("\nRunning one turn (fan-out to two specialists) against real Gemini Flash...")
        events = await _live_harness.run_and_collect(
            runner,
            "What is the impact of remote work adoption? Answer from two perspectives.",
            user_id=user_id,
        )

        print(f"Total events yielded: {len(events)}")

        # Feed all events into the real accumulator
        accumulator = SessionTurnAccumulator()
        for event in events:
            accumulator.add_event(event)
        accumulator_total = accumulator._input + accumulator._output + accumulator._reasoning

        # Sum via extract_billable_tokens
        per_event_total = 0
        inner_events_by_author: dict[str, list[dict[str, Any]]] = {}

        for event in events:
            counts = extract_billable_tokens(event)
            per_event_total += counts.total_billable

            author = getattr(event, "author", None)
            usage = getattr(event, "usage_metadata", None)
            if author not in (None, "user", "coordinator") and usage is not None:
                node_info = getattr(event, "node_info", None)
                entry = {
                    "author": author,
                    "isolation_scope": getattr(event, "isolation_scope", None),
                    "node_path": getattr(node_info, "path", None) if node_info else None,
                    "prompt_token_count": getattr(usage, "prompt_token_count", None),
                    "candidates_token_count": getattr(usage, "candidates_token_count", None),
                }
                if author not in inner_events_by_author:
                    inner_events_by_author[author] = []
                inner_events_by_author[author].append(entry)

        # Print diagnostics
        print("\nInner specialist events with usage_metadata (by author):")
        for author, evs in inner_events_by_author.items():
            print(f"  {author}: {len(evs)} event(s)")
            for ev in evs[:2]:  # limit to first 2 per author
                print(f"    {ev}")

        print(f"\nextract_billable_tokens sum: {per_event_total}")
        print(f"SessionTurnAccumulator total: {accumulator_total}")

        # Assertions
        assertion_failures: list[str] = []

        # A1: Both fan-out branches contributed events with usage_metadata
        branches_seen = set(inner_events_by_author.keys())
        if "specialist_a" not in branches_seen:
            assertion_failures.append(
                "FAIL A1a: No events with usage_metadata from specialist_a in outer stream. "
                "Branch A fan-out events not propagated."
            )
        if "specialist_b" not in branches_seen:
            assertion_failures.append(
                "FAIL A1b: No events with usage_metadata from specialist_b in outer stream. "
                "Branch B fan-out events not propagated."
            )

        if not assertion_failures:
            print(
                f"\nPASS A1: Both fan-out branches visible in outer stream "
                f"(branches seen: {branches_seen})."
            )
            # Print decisive evidence for AH-99 AC #2
            print("\n=== DECISIVE EVIDENCE: First inner event per branch with usage_metadata ===")
            for author, evs in inner_events_by_author.items():
                print(f"Branch '{author}' first event:")
                print(json.dumps(evs[0], indent=2))

        # A2: Accumulator counted tokens
        if accumulator_total == 0:
            assertion_failures.append(
                "FAIL A2: SessionTurnAccumulator total is 0 — inner tokens not counted."
            )
        else:
            print(f"\nPASS A2: SessionTurnAccumulator counted {accumulator_total} total tokens.")

        # A3: Parity invariant
        if per_event_total != accumulator_total:
            assertion_failures.append(
                f"FAIL A3: Parity violated — "
                f"extract_billable_tokens sum ({per_event_total}) != "
                f"accumulator total ({accumulator_total})."
            )
        else:
            print(
                f"PASS A3: Parity invariant holds — "
                f"sum ({per_event_total}) == accumulator ({accumulator_total})."
            )

        if assertion_failures:
            print("\n=== PROBE Q4 (live): FAIL ===")
            for failure in assertion_failures:
                print(f"  {failure}")
            return 1

        print("\n=== PROBE Q4 (live): PASS ===")
        print("Dynamic-graph fan-out path: both branches' inner events visible in outer stream.")
        print("AH-99 AC #2 (dynamic-graph path) confirmed on real Gemini Flash.")
        return 0

    finally:
        print(f"\nCleaning up spike sessions...")
        deleted = await _live_harness.cleanup_spike_sessions()
        print(f"  Deleted {deleted} spike session(s).")


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(run_probe())
    except Exception as exc:
        code = _live_harness.classify_exit_code(exc)
        label = (
            "infrastructure/credentials"
            if code == 2
            else "FINDING — ADK 2.0 differs from the spike assumption"
        )
        print(f"\nERROR [{label}] (exit {code}): {type(exc).__name__}: {exc}")
        print(
            "\nNote: exit 2 = infra/credentials (ADC, 401/403/429/5xx, transport) -> INDETERMINATE; "
            "exit 1 = a real finding (model 404, changed ADK API, validation error) -> NO-GO. "
            "This probe needs Gemini Flash + Agent Engine access on ken-e-dev "
            "(ADC via 'gcloud auth application-default login')."
        )
        sys.exit(code)
    sys.exit(exit_code)
