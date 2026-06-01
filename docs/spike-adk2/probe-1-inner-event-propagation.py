"""Probe Q1 — Do inner task-mode sub-agent events reach the outer Runner stream? (LIVE)

Tests the task-mode path: LlmAgent(mode='chat') coordinator + LlmAgent(mode='task')
specialist, driven against real Gemini Flash.

Run with (from repo root):
    .venv-adk2/bin/python docs/spike-adk2/probe-1-inner-event-propagation.py

Findings (AH-96 static, upgraded to live by AH-99):
    Q1 (DECISIVE — LIVE PATH): Inner sub-agent events authored by the task specialist
    carry non-null usage_metadata and are visible to the outer Runner.run_async
    consumer.  extract_billable_tokens and SessionTurnAccumulator count them.

Exit codes:
    0 — all three live invariants hold (inner event with usage_metadata present;
        accumulator total > 0; accumulator total == sum of extract_billable_tokens)
    1 — at least one invariant failed (stdout shows which)
    2 — unexpected exception (infrastructure/credential issue)

ADK version required: 2.0.0 (in .venv-adk2/)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

# Resolve harness from same directory as this file
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _live_harness

print("=== Probe Q1 (live): Inner event propagation — task-mode path ===\n")


def _summarise_event(event: Any) -> dict[str, Any]:
    """Return a compact dict summary of an ADK 2.0 Event for diagnostic output."""
    usage = getattr(event, "usage_metadata", None)
    node_info = getattr(event, "node_info", None)
    return {
        "author": getattr(event, "author", None),
        "isolation_scope": getattr(event, "isolation_scope", None),
        "node_path": getattr(node_info, "path", None) if node_info else None,
        "has_usage_metadata": usage is not None,
        "prompt_token_count": getattr(usage, "prompt_token_count", None) if usage else None,
        "candidates_token_count": getattr(usage, "candidates_token_count", None) if usage else None,
        "turn_complete": getattr(event, "turn_complete", None),
    }


async def run_probe() -> int:
    """Run the live probe.  Returns exit code (0=pass, 1=fail, 2=error)."""

    extract_billable_tokens, SessionTurnAccumulator = _live_harness.import_real_modules()

    # --- Build the topology (Q1 task-mode path) ---
    from google.adk.agents.llm_agent import LlmAgent

    task_specialist = LlmAgent(
        name="task_specialist",
        model=_live_harness._DEFAULT_MODEL,
        mode="task",
        instruction=(
            "You are a concise analyst. Answer the user's question in exactly one "
            "sentence. Be factual and brief."
        ),
    )
    coordinator = LlmAgent(
        name="coordinator",
        model=_live_harness._DEFAULT_MODEL,
        mode="chat",
        instruction=(
            "You are a routing coordinator. For any question, delegate to "
            "task_specialist to answer it. Return the specialist's answer "
            "verbatim."
        ),
        sub_agents=[task_specialist],
    )

    runner, user_id = _live_harness.make_runner(coordinator)
    print(f"Session user_id: {user_id}")

    try:
        print("\nRunning one turn against real Gemini Flash...")
        events = await _live_harness.run_and_collect(
            runner,
            "What is the capital of France? Answer in one sentence.",
            user_id=user_id,
        )

        print(f"Total events yielded: {len(events)}")

        # --- Feed all events into the real accumulator ---
        accumulator = SessionTurnAccumulator()
        for event in events:
            accumulator.add_event(event)

        accumulator_total = accumulator._input + accumulator._output + accumulator._reasoning

        # --- Feed all events into extract_billable_tokens and sum ---
        per_event_total = 0
        inner_events_with_usage: list[dict[str, Any]] = []

        for event in events:
            counts = extract_billable_tokens(event)
            per_event_total += counts.total_billable
            author = getattr(event, "author", None)
            usage = getattr(event, "usage_metadata", None)
            if author not in (None, "user", "coordinator") and usage is not None:
                # This is an inner sub-agent event with usage_metadata
                node_info = getattr(event, "node_info", None)
                inner_events_with_usage.append({
                    "author": author,
                    "prompt_token_count": getattr(usage, "prompt_token_count", None),
                    "candidates_token_count": getattr(usage, "candidates_token_count", None),
                    "isolation_scope": getattr(event, "isolation_scope", None),
                    "node_path": getattr(node_info, "path", None) if node_info else None,
                })

        # --- Print diagnostics ---
        print("\nEvent summary (all events):")
        for event in events:
            print(f"  {_summarise_event(event)}")

        print(f"\nextract_billable_tokens sum across all events: {per_event_total}")
        print(f"SessionTurnAccumulator total (input+output+reasoning): {accumulator_total}")
        print(f"\nInner task-specialist events with usage_metadata: {len(inner_events_with_usage)}")
        for ev in inner_events_with_usage:
            print(f"  {ev}")

        # --- Assertions ---
        assertion_failures: list[str] = []

        # Assertion 1: at least one inner specialist event has non-null usage_metadata
        if len(inner_events_with_usage) == 0:
            assertion_failures.append(
                "FAIL A1: No inner sub-agent (task_specialist) events with non-null "
                "usage_metadata found in the outer stream. "
                "Inner event propagation is NOT working on this ADK build."
            )
        else:
            specialist_usage = inner_events_with_usage[0]
            if not specialist_usage.get("prompt_token_count"):
                assertion_failures.append(
                    f"FAIL A1b: Inner event found but prompt_token_count is None/0: "
                    f"{specialist_usage}"
                )
            else:
                print(
                    f"\nPASS A1: Inner task_specialist event has "
                    f"prompt_token_count={specialist_usage['prompt_token_count']} "
                    f"— inner events reach the outer stream with usage_metadata."
                )
                # Print the raw event JSON as irrefutable evidence (AH-99 AC #2)
                print("\n=== DECISIVE EVIDENCE: First inner specialist event with usage_metadata ===")
                print(json.dumps(specialist_usage, indent=2))

        # Assertion 2: accumulator counted tokens
        if accumulator_total == 0:
            assertion_failures.append(
                "FAIL A2: SessionTurnAccumulator total is 0 — the real accumulator "
                "did not count any tokens from the event stream."
            )
        else:
            print(f"\nPASS A2: SessionTurnAccumulator counted {accumulator_total} total tokens.")

        # Assertion 3: parity invariant — extract_billable_tokens sum == accumulator total
        if per_event_total != accumulator_total:
            assertion_failures.append(
                f"FAIL A3: Parity invariant violated — "
                f"extract_billable_tokens sum ({per_event_total}) != "
                f"accumulator total ({accumulator_total}). "
                "The two token-accounting paths disagree."
            )
        else:
            print(
                f"PASS A3: Parity invariant holds — "
                f"extract_billable_tokens sum ({per_event_total}) == "
                f"accumulator total ({accumulator_total})."
            )

        if assertion_failures:
            print("\n=== PROBE Q1 (live): FAIL ===")
            for failure in assertion_failures:
                print(f"  {failure}")
            return 1

        print("\n=== PROBE Q1 (live): PASS ===")
        print("All three live invariants hold on ADK 2.0 task-mode path:")
        print("  A1: Inner task_specialist events carry non-null usage_metadata in outer stream.")
        print("  A2: SessionTurnAccumulator counted the inner tokens.")
        print("  A3: Parity invariant: extract_billable_tokens sum == accumulator total.")
        return 0

    finally:
        print(f"\nCleaning up spike sessions (user_id prefix: {_live_harness._SPIKE_USER_ID_PREFIX})...")
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
