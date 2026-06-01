"""Probe Q5 — VertexAiSessionService live round-trip for ADK 2.0 event fields. (LIVE)

Creates a real dev session, appends ADK 2.0 events with node_info + isolation_scope,
then get_session / list_events and asserts the new fields survive the round-trip
(or documents the exact pydantic.ValidationError fallback path if they don't).

Run with (from repo root):
    .venv-adk2/bin/python docs/spike-adk2/probe-5-session-service-schema.py

Two terminal states — both exit 0:
    "raw_event roundtrip OK"    — Vertex AI backend accepted node_info + isolation_scope
                                   in the raw_event field and returned them via get_session.
    "raw_event fallback triggered" — The service's pydantic.ValidationError fallback fired;
                                   the probe documents which fields were dropped and at
                                   which API path.  This is the migration doc path per AH-99 AC #3.

Exits non-zero only on an unexpected exception class (not pydantic.ValidationError,
not 403/404 API errors that are part of the normal assertion surface).

Sessions created by this probe are deleted at teardown regardless of outcome.

AH-99 AC #3: probe exits 0 in EITHER terminal state (raw_event accepted OR fallback documented),
but exits non-zero if any unexpected error class surfaces.

ADK version required: 2.0.0 (in .venv-adk2/)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _live_harness

print("=== Probe Q5 (live): VertexAiSessionService schema round-trip ===\n")


def _build_task_mode_event() -> Any:
    """Construct an ADK 2.0 Event with task-mode node_info and isolation_scope.

    NodeInfo is at google.adk.events.event.NodeInfo (not in workflow._node_info).
    isolation_scope is a direct field on Event, not inside NodeInfo.
    """
    from google.adk.events.event import Event, NodeInfo
    from google.genai.types import Content, Part

    node_info = NodeInfo(
        path="/coordinator/task_specialist",
    )
    event = Event(
        author="task_specialist",
        invocation_id=f"spike-ah99-inv-{uuid.uuid4().hex[:12]}",
        isolation_scope=f"fc_task_mode_{uuid.uuid4().hex[:8]}",
        node_info=node_info,
        content=Content(
            role="model",
            parts=[Part(text="Task completed: The capital of France is Paris.")],
        ),
    )
    return event


def _build_dynamic_graph_event() -> Any:
    """Construct an ADK 2.0 Event with dynamic-graph (ctx.run_node) node_info."""
    from google.adk.events.event import Event, NodeInfo
    from google.genai.types import Content, Part

    node_info = NodeInfo(
        path="/coordinator/run_node_branch_a",
    )
    event = Event(
        author="specialist_a",
        invocation_id=f"spike-ah99-inv-{uuid.uuid4().hex[:12]}",
        isolation_scope=f"fc_dyngraph_{uuid.uuid4().hex[:8]}",
        node_info=node_info,
        content=Content(
            role="model",
            parts=[Part(text="Branch A analysis: Remote work boosts productivity.")],
        ),
    )
    return event


async def run_probe() -> int:
    """Run the live Q5 probe.  Returns exit code (0=pass, 1=fail, 2=error)."""
    from google.adk.sessions.vertex_ai_session_service import VertexAiSessionService
    from pydantic import ValidationError

    svc = VertexAiSessionService(
        project=_live_harness._DEFAULT_PROJECT,
        location=_live_harness._DEFAULT_LOCATION,
        agent_engine_id=_live_harness._DEFAULT_ENGINE_ID,
    )
    app_name = _live_harness._DEFAULT_ENGINE_ID
    user_id = f"{_live_harness._SPIKE_USER_ID_PREFIX}{uuid.uuid4()}"
    session_id: str | None = None

    print(f"Creating dev session (user_id: {user_id})...")

    try:
        # Create session
        session = await svc.create_session(
            app_name=app_name,
            user_id=user_id,
        )
        session_id = session.id
        print(f"  Session created: {session_id}")

        # Build two ADK 2.0 events with new fields
        task_mode_event = _build_task_mode_event()
        dynamic_graph_event = _build_dynamic_graph_event()

        # Append both events. A pydantic.ValidationError here is itself the
        # documented fallback path (the backend rejects the new fields), not a
        # crash — capture it and keep going.
        append_errors: list[str] = []

        print("\nAppending task-mode event (node_info + isolation_scope)...")
        try:
            await svc.append_event(session=session, event=task_mode_event)
            print("  appended task-mode event.")
        except ValidationError as exc:
            append_errors.append(f"task-mode: pydantic.ValidationError: {exc}")
            print(f"  pydantic.ValidationError on task-mode append_event: {exc}")

        # Re-fetch a clean session copy from the backend before the next append
        # (append_event mutates the local session in place).
        refreshed = await svc.get_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        ) or session

        print("\nAppending dynamic-graph event (node_info + isolation_scope)...")
        try:
            await svc.append_event(session=refreshed, event=dynamic_graph_event)
            print("  appended dynamic-graph event.")
        except ValidationError as exc:
            append_errors.append(f"dynamic-graph: pydantic.ValidationError: {exc}")
            print(f"  pydantic.ValidationError on dynamic-graph append_event: {exc}")

        # --- The REAL round-trip: re-fetch from the backend and inspect the
        # STORED (serialized -> persisted -> reconstructed) events, NOT the local
        # event objects we just built. The old probe inspected append_event()'s
        # return value (the same local object), which trivially still carried the
        # fields and could never detect a backend that drops them (AH-99 review). ---
        print("\nVerifying round-trip via get_session (inspecting STORED events)...")
        retrieved = await svc.get_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )
        if retrieved is None:
            print("  ERROR: get_session returned None — cannot verify the round-trip.")
            return 1
        print(
            f"  Session retrievable: ID={retrieved.id}; events stored: "
            f"{len(retrieved.events)}"
        )

        # Match the two appended events back by their (distinct) authors.
        stored_by_author = {
            e.author: e for e in retrieved.events if getattr(e, "author", None)
        }
        preserved: list[str] = []
        dropped: list[str] = []
        for label, author in (
            ("task-mode", "task_specialist"),
            ("dynamic-graph", "specialist_a"),
        ):
            stored = stored_by_author.get(author)
            if stored is None:
                print(f"  WARNING: no stored event found for author={author!r} ({label}).")
                dropped.append(f"{label}:event-missing")
                continue
            node_ok = getattr(stored, "node_info", None) is not None
            iso_ok = getattr(stored, "isolation_scope", None) is not None
            print(
                f"  [{label}] stored author={author}: "
                f"node_info={'present' if node_ok else 'DROPPED'}, "
                f"isolation_scope={'present' if iso_ok else 'DROPPED'}"
            )
            (preserved if (node_ok or iso_ok) else dropped).append(
                label if (node_ok or iso_ok) else f"{label}:node_info+isolation_scope"
            )

        print("\n--- Q5 Terminal State ---")
        if preserved and not dropped:
            print("raw_event roundtrip OK — the dev Agent Engine backend round-tripped ADK 2.0 "
                  "node_info / isolation_scope on the STORED events (verified via get_session).")
            print("AH-99 AC #3: NO migration needed for new event fields.")
        elif preserved:
            print(f"raw_event PARTIAL — preserved: {preserved}; dropped: {dropped}")
            print("AH-99 AC #3: Migration documented — some new fields do NOT survive the "
                  "Agent Engine round-trip. Chat team must not assume they persist.")
        else:
            print(f"raw_event fallback — dropped on round-trip: {dropped}")
            print("AH-99 AC #3: Migration documented — node_info / isolation_scope are stripped "
                  "before storage. Chat team must not assume they survive a round-trip.")

        if append_errors:
            print("\nValidationError(s) during append (documented fallback path):")
            for e in append_errors:
                print(f"  {e}")

        print("\n=== PROBE Q5 (live): PASS ===")
        print("(Both terminal states — fields preserved OR fallback documented — are passing "
              "outcomes; the verdict is now based on STORED events, not the local objects.)")
        return 0

    finally:
        print(f"\nCleaning up spike sessions (prefix: {_live_harness._SPIKE_USER_ID_PREFIX})...")
        deleted = await _live_harness.cleanup_spike_sessions()
        print(f"  Deleted {deleted} spike session(s).")
        # Final verification: confirm no spike sessions remain
        list_response = await svc.list_sessions(app_name=app_name)
        remaining = [
            s for s in list_response.sessions
            if s.user_id.startswith(_live_harness._SPIKE_USER_ID_PREFIX)
        ]
        print(f"  Spike sessions remaining after cleanup: {len(remaining)} (expected 0)")


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
            "exit 1 = a real finding (changed ADK API, validation error) -> NO-GO. "
            "This probe needs aiplatform.sessions.* on ken-e-dev (ADC configured)."
        )
        sys.exit(code)
    sys.exit(exit_code)
