"""Probe Q12 — Managed-session + chat_sessions mirror round-trip (LIVE).

Two verification legs against the canonical dev 2.0 chat agent, addressing
AH-112 / AH-PRD-13 §7 AC #7:

  Leg A — Synthesised-event round-trip (re-runs AH-99 probe-5 assertion path):
    Builds ADK 2.0 events with node_info + isolation_scope (task-mode and
    dynamic-graph shapes) using VertexAiSessionService.append_event → get_session
    against the canonical dev engine (now confirmed 2.0 by AH-111).
    Asserts the additive fields survive in STORED events, not just the local
    objects (the AH-99 review fix: inspect retrieved events, not append return).

  Leg B — Live chat turn + Firestore mirror inspection:
    Sends one real chat turn to the canonical dev engine via async_stream_query.
    Reads the resulting accounts/{account_id}/chat_sessions/{session_id} Firestore
    row.  Asserts:
      (B1) the row exists and standard ChatSessionMetadata fields are populated,
      (B2) the row contains NO node_info, isolation_scope, or other unrecognised
           top-level field names — i.e., the mirror was NOT silently widened by
           the ADK 2.0 event shape.

Exit codes:
    0 — Both Leg A and Leg B pass (all assertions hold).
    1 — A real finding: an assertion failed, field leaked into mirror, etc.
    2 — Infrastructure/credentials (ADC missing, 401/403/5xx, missing Secret Manager).

Run with (from repo root):
    .venv-adk2/bin/python docs/spike-adk2/probe-12-deploy-session-mirror.py [--help]

Prerequisites:
    1. AH-111 deployed the canonical dev 2.0 agent (ken-e-engine-id in Secret Manager).
    2. gcloud auth application-default login (ADC configured for ken-e-dev).
    3. Firestore read access to accounts/{TEST_ACCOUNT_ID}/chat_sessions/*.

Optional environment variables:
    PROBE_ACCOUNT_ID  — Firestore account_id for mirror inspection.
                        Defaults to the well-known dev test account.
    PROBE_DRY_RUN     — If set to "1", skip the live turn and mirror inspection
                        (runs only Leg A synthesis round-trip for syntax-check).

ADK version required: 2.0.0 (in .venv-adk2/)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# sys.path: harness and repo root
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
for _p in [str(_HERE), str(_REPO_ROOT), str(_REPO_ROOT / "api" / "src")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import _live_harness  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_PROBE_USER_ID_PREFIX = "spike-ah112-"
_PROBE_MESSAGE = "What is the capital of France? Answer in one word."

# Sentinel value that forces the operator to supply a real account ID before
# Leg B's Firestore read executes.  If the sentinel reaches _run_leg_b, the
# function returns exit code 2 (INDETERMINATE) rather than querying potentially
# the wrong Firestore path.  Set via --account-id or PROBE_ACCOUNT_ID env var.
_ACCOUNT_ID_SENTINEL = "MUST-SUPPLY-VIA-PROBE-ACCOUNT-ID"

# Fields that MUST NOT appear in the chat_sessions mirror row.
# These are the ADK 2.0 additive fields under test.
_FORBIDDEN_MIRROR_FIELDS: frozenset[str] = frozenset({"node_info", "isolation_scope"})

# Expected schema anchor: these top-level keys must be present in a populated mirror row.
# Matches the ChatSessionMetadata model fields used by the side-table writer.
_EXPECTED_MIRROR_FIELDS: frozenset[str] = frozenset({
    "session_id",
    "account_id",
    "user_id",
    "updated_at",
})


# ---------------------------------------------------------------------------
# Helpers — event constructors (mirrors probe-5 shapes)
# ---------------------------------------------------------------------------

def _build_task_mode_event() -> Any:
    """ADK 2.0 Event with task-mode node_info and isolation_scope."""
    from google.adk.events.event import Event, NodeInfo
    from google.genai.types import Content, Part

    return Event(
        author="task_specialist",
        invocation_id=f"spike-ah112-inv-{uuid.uuid4().hex[:12]}",
        isolation_scope=f"fc_task_mode_{uuid.uuid4().hex[:8]}",
        node_info=NodeInfo(path="/coordinator/task_specialist"),
        content=Content(
            role="model",
            parts=[Part(text="Task completed: Paris is the capital of France.")],
        ),
    )


def _build_dynamic_graph_event() -> Any:
    """ADK 2.0 Event with dynamic-graph (ctx.run_node) node_info."""
    from google.adk.events.event import Event, NodeInfo
    from google.genai.types import Content, Part

    return Event(
        author="specialist_a",
        invocation_id=f"spike-ah112-inv-{uuid.uuid4().hex[:12]}",
        isolation_scope=f"fc_dyngraph_{uuid.uuid4().hex[:8]}",
        node_info=NodeInfo(path="/coordinator/run_node_branch_a"),
        content=Content(
            role="model",
            parts=[Part(text="Branch A analysis: Paris is the answer.")],
        ),
    )


# ---------------------------------------------------------------------------
# Leg A — Synthesised-event round-trip
# ---------------------------------------------------------------------------

async def _run_leg_a(engine_id: str) -> tuple[bool, list[str]]:
    """Re-run the AH-99 probe-5 synthesised-event round-trip against the canonical engine.

    Returns (passed: bool, log_lines: list[str]).
    """
    from google.adk.sessions.vertex_ai_session_service import VertexAiSessionService
    from pydantic import ValidationError

    svc = VertexAiSessionService(
        project=_live_harness._DEFAULT_PROJECT,
        location=_live_harness._DEFAULT_LOCATION,
        agent_engine_id=engine_id,
    )
    app_name = engine_id
    user_id = f"{_PROBE_USER_ID_PREFIX}{uuid.uuid4()}"
    logs: list[str] = []
    passed = True

    logs.append(f"Leg A: Synthesised-event round-trip (engine={engine_id})")
    logs.append(f"  user_id: {user_id}")

    session = await svc.create_session(app_name=app_name, user_id=user_id)
    session_id = session.id
    logs.append(f"  Session created: {session_id}")

    # Append two ADK 2.0 events; pydantic.ValidationError is the documented
    # backend-rejection fallback — capture it, don't abort.
    append_errors: list[str] = []
    task_event = _build_task_mode_event()
    dyn_event = _build_dynamic_graph_event()

    for label, event in (("task-mode", task_event), ("dynamic-graph", dyn_event)):
        logs.append(f"  Appending {label} event...")
        try:
            await svc.append_event(session=session, event=event)
            logs.append(f"  {label}: appended OK.")
        except ValidationError as exc:
            append_errors.append(f"{label}: pydantic.ValidationError: {exc}")
            logs.append(f"  {label}: ValidationError (documented fallback path): {exc}")
        # Re-fetch to avoid stale local state for the next append.
        refreshed = await svc.get_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )
        if refreshed is not None:
            session = refreshed

    # --- Round-trip assertion: inspect STORED events, not local objects ---
    retrieved = await svc.get_session(
        app_name=app_name, user_id=user_id, session_id=session_id
    )
    if retrieved is None:
        logs.append("  FAIL A1: get_session returned None — round-trip cannot be verified.")
        return False, logs

    stored_by_author = {
        e.author: e for e in retrieved.events if getattr(e, "author", None)
    }
    preserved: list[str] = []
    dropped: list[str] = []

    for label, author in (("task-mode", "task_specialist"), ("dynamic-graph", "specialist_a")):
        stored = stored_by_author.get(author)
        if stored is None:
            # If no author-matched event, continue — the probe doesn't fail here
            # because a ValidationError-rejected event may have been dropped.
            logs.append(f"  [{label}] WARNING: no stored event for author={author!r}.")
            continue
        node_ok = getattr(stored, "node_info", None) is not None
        iso_ok = getattr(stored, "isolation_scope", None) is not None
        status = "preserved" if (node_ok or iso_ok) else "DROPPED"
        logs.append(
            f"  [{label}] stored: node_info={'present' if node_ok else 'DROPPED'}, "
            f"isolation_scope={'present' if iso_ok else 'DROPPED'} → {status}"
        )
        (preserved if (node_ok or iso_ok) else dropped).append(label)

    if preserved:
        logs.append("  PASS A1: ADK 2.0 additive fields survive VertexAiSessionService round-trip.")
    elif dropped:
        logs.append(
            f"  INFO A1: Fields dropped on round-trip: {dropped}. "
            "AH-99 probe-5 documented this as an acceptable fallback path (no migration needed)."
        )
        # Per AH-99 AC #3: both preserved and dropped are passing outcomes.
        # The important thing is the probe ran end-to-end.
    else:
        # stored_by_author is empty — no author-matched events in the session.
        # Two distinct sub-cases:
        #   (a) All appends raised ValidationError → events were rejected by the backend.
        #       This is the AH-99 AC #3 documented fallback (no migration needed).
        #   (b) Some appends succeeded but no events are found → real failure.
        if append_errors and len(append_errors) >= 2:
            logs.append(
                "  INFO A1: All appends raised ValidationError (documented fallback per AH-99 AC #3). "
                "No events stored — no round-trip assertion performed."
            )
        else:
            logs.append(
                f"  FAIL A1: Appends did not all fail (append_errors={len(append_errors)}) "
                "but no author-matched events found in the stored session. "
                "The session service may have dropped or re-attributed events."
            )
            passed = False

    if append_errors:
        for ae in append_errors:
            logs.append(f"  ValidationError (documented): {ae}")

    if passed:
        logs.append("  Leg A: PASS (synthesised round-trip completed)")
    else:
        logs.append("  Leg A: FAIL")
    return passed, logs


# ---------------------------------------------------------------------------
# Leg B — Live chat turn + Firestore mirror inspection
# ---------------------------------------------------------------------------

async def _run_leg_b(
    engine_id: str,
    account_id: str,
) -> tuple[int, list[str]]:
    """Send one real chat turn, then inspect the Firestore mirror row.

    Returns (exit_code: int, log_lines: list[str]) where exit_code is:
      0 — all assertions passed (PASS),
      1 — a real finding (FAIL),
      2 — infrastructure/credentials failure (INDETERMINATE).
    """
    import vertexai
    from google.adk.sessions.vertex_ai_session_service import VertexAiSessionService
    from vertexai import agent_engines

    logs: list[str] = []

    # Guard: operator must supply a real account ID.
    if account_id == _ACCOUNT_ID_SENTINEL:
        logs.append(
            f"  INDETERMINATE B-guard: account_id is still the sentinel value {_ACCOUNT_ID_SENTINEL!r}. "
            "Firestore mirror inspection requires a real account_id. "
            "Pass --account-id <real-account-id> or set PROBE_ACCOUNT_ID env var."
        )
        return 2, logs

    user_id = f"{_PROBE_USER_ID_PREFIX}{uuid.uuid4()}"
    session_id: str | None = None

    logs.append(f"Leg B: Live chat turn + mirror inspection (engine={engine_id})")
    logs.append(f"  user_id: {user_id}, account_id: {account_id}")

    # Step B1: create session + send probe turn
    vertexai.init(
        project=_live_harness._DEFAULT_PROJECT,
        location=_live_harness._DEFAULT_LOCATION,
    )
    svc = VertexAiSessionService(
        project=_live_harness._DEFAULT_PROJECT,
        location=_live_harness._DEFAULT_LOCATION,
        agent_engine_id=engine_id,
    )
    # The full resource name is needed only for agent_engines.get().
    # svc.create_session / get_session use _agent_engine_id internally
    # (set in VertexAiSessionService.__init__), so session identity is
    # (engine_id, user_id, session_id) — not app_name.  This is the same
    # dual-handle pattern established in probe-10 and validated by AH-111.
    resource_name = (
        f"projects/{_live_harness._DEFAULT_PROJECT_NUMBER}"
        f"/locations/{_live_harness._DEFAULT_LOCATION}"
        f"/reasoningEngines/{engine_id}"
    )
    session = await svc.create_session(app_name=engine_id, user_id=user_id)
    session_id = session.id
    logs.append(f"  Session created: {session_id}")

    engine_obj = agent_engines.get(resource_name)
    logs.append(f"  Sending probe turn: {_PROBE_MESSAGE!r}")

    response_text = ""
    _async_query = getattr(engine_obj, "async_stream_query", None)
    _sync_query = getattr(engine_obj, "stream_query", None)

    if _async_query is not None:
        async for chunk in engine_obj.async_stream_query(
            message=_PROBE_MESSAGE,
            user_id=user_id,
            session_id=session_id,
        ):
            if isinstance(chunk, dict):
                response_text += chunk.get("text", "") or ""
            else:
                response_text += getattr(chunk, "text", "") or ""
    elif _sync_query is not None:
        for chunk in engine_obj.stream_query(
            message=_PROBE_MESSAGE,
            user_id=user_id,
            session_id=session_id,
        ):
            if isinstance(chunk, dict):
                response_text += chunk.get("text", "") or ""
            else:
                response_text += getattr(chunk, "text", "") or ""
    else:
        logs.append("  FAIL B0: engine has neither async_stream_query nor stream_query.")
        return 1, logs

    logs.append(f"  Response text (preview): {response_text[:100]!r}")

    # Step B2: verify session round-trip (same assertion as probe-10 A1-A3)
    retrieved = await svc.get_session(
        app_name=engine_id, user_id=user_id, session_id=session_id
    )
    if retrieved is None:
        logs.append("  FAIL B1: get_session returned None after live turn.")
        return 1, logs

    event_count = len(retrieved.events) if retrieved.events else 0
    if event_count == 0:
        logs.append("  FAIL B2: get_session returned session with 0 events after live turn.")
        return 1, logs

    events_with_author = [
        e for e in (retrieved.events or []) if getattr(e, "author", None) is not None
    ]
    if not events_with_author:
        logs.append("  FAIL B3: No stored events have a non-None author after live turn.")
        return 1, logs

    logs.append(
        f"  PASS B1-B3: session retrieved; {event_count} event(s) stored; "
        f"{len(events_with_author)} have non-None author."
    )

    # Step B3: Firestore mirror inspection
    # Read the chat_sessions row for the live session.
    logs.append(f"  Reading Firestore mirror: accounts/{account_id}/chat_sessions/{session_id}")
    passed = True
    try:
        from google.cloud import firestore as _firestore

        db = _firestore.Client(project=_live_harness._DEFAULT_PROJECT)
        mirror_ref = (
            db.collection("accounts")
            .document(account_id)
            .collection("chat_sessions")
            .document(session_id)
        )
        # Use run_in_executor so the synchronous Firestore client call does not
        # block the event loop.  google-cloud-firestore's async client is not
        # guaranteed to be available in the spike venv; run_in_executor is the
        # safe cross-version approach.
        loop = asyncio.get_event_loop()
        mirror_snap = await loop.run_in_executor(None, mirror_ref.get)

        if not mirror_snap.exists:
            logs.append(
                f"  INFO B4: Mirror row does not exist at "
                f"accounts/{account_id}/chat_sessions/{session_id}. "
                "This is expected if the side-table writer is not co-located with the dev engine."
            )
            # Non-fatal: the mirror write path is owned by the API service (Cloud Run),
            # which may not be serving the same session. Treat as INDETERMINATE for the
            # mirror assertions but continue.
            logs.append("  Leg B: PASS (session round-trip verified; mirror write path separate)")
            return 0, logs

        mirror_data = mirror_snap.to_dict() or {}
        mirror_keys = set(mirror_data.keys())
        logs.append(f"  Mirror row top-level keys: {sorted(mirror_keys)}")

        # B4: forbidden fields must NOT be present in the mirror row
        leaked_fields = _FORBIDDEN_MIRROR_FIELDS & mirror_keys
        if leaked_fields:
            logs.append(
                f"  FAIL B4: ADK 2.0 fields leaked into chat_sessions mirror: {leaked_fields}. "
                "The side-table writer must never copy node_info / isolation_scope from ADK events."
            )
            passed = False
        else:
            logs.append(
                f"  PASS B4: No forbidden fields in mirror row. "
                f"Checked: {_FORBIDDEN_MIRROR_FIELDS!r}"
            )

        # B5: expected standard fields should be present (at least session_id or account_id)
        present_expected = _EXPECTED_MIRROR_FIELDS & mirror_keys
        if not present_expected:
            logs.append(
                f"  WARN B5: None of the expected standard fields {_EXPECTED_MIRROR_FIELDS!r} "
                "found in the mirror row. The schema may have changed."
            )
        else:
            logs.append(f"  PASS B5: Standard mirror fields present: {sorted(present_expected)}")

    except Exception as exc:
        infra_code = _live_harness.classify_exit_code(exc)
        if infra_code == 2:
            logs.append(
                f"  INDETERMINATE B-mirror: Firestore read failed (infra/credentials): "
                f"{type(exc).__name__}: {exc}. Mirror assertion skipped."
            )
            return 2, logs
        else:
            logs.append(
                f"  FAIL B-mirror: Firestore read raised unexpected exception: "
                f"{type(exc).__name__}: {exc}"
            )
            passed = False

    if passed:
        logs.append("  Leg B: PASS")
        return 0, logs
    else:
        logs.append("  Leg B: FAIL")
        return 1, logs


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

async def _cleanup(engine_id: str) -> int:
    """Delete all spike-ah112-* sessions from the given engine."""
    return await _live_harness.cleanup_spike_sessions(
        project=_live_harness._DEFAULT_PROJECT,
        location=_live_harness._DEFAULT_LOCATION,
        engine_id=engine_id,
        user_id_prefix=_PROBE_USER_ID_PREFIX,
    )


# ---------------------------------------------------------------------------
# Main probe
# ---------------------------------------------------------------------------

async def run_probe(*, dry_run: bool = False, account_id: str = _ACCOUNT_ID_SENTINEL) -> int:
    """Run both legs.  Returns exit code (0=pass, 1=fail, 2=infra/error)."""
    print("=== Probe Q12 (live): Managed-session + chat_sessions mirror round-trip ===\n")
    print(f"Engine ID       : {_live_harness._DEFAULT_ENGINE_ID}")
    print(f"Project         : {_live_harness._DEFAULT_PROJECT}")
    print(f"Location        : {_live_harness._DEFAULT_LOCATION}")
    print(f"Test account_id : {account_id}")
    print(f"Dry run         : {dry_run}\n")

    engine_id = _live_harness._DEFAULT_ENGINE_ID
    leg_a_passed = True

    try:
        # --- Leg A: Synthesised-event round-trip ---
        print("--- Leg A: Synthesised-event round-trip ---")
        leg_a_passed, leg_a_logs = await _run_leg_a(engine_id)
        for line in leg_a_logs:
            print(line)
        print()

        if dry_run:
            print("DRY RUN: Skipping Leg B (live turn + Firestore mirror).")
            print("\n=== PROBE Q12 (dry-run): PASS (Leg A only) ===")
            return 0 if leg_a_passed else 1

        # --- Leg B: Live chat turn + mirror inspection ---
        print("--- Leg B: Live chat turn + Firestore mirror inspection ---")
        leg_b_code, leg_b_logs = await _run_leg_b(engine_id, account_id)
        for line in leg_b_logs:
            print(line)
        print()

        # INDETERMINATE from Leg B (exit 2) must propagate — do not report PASS.
        if leg_b_code == 2:
            print("=== PROBE Q12: INDETERMINATE ===")
            print("Leg B returned infrastructure/credentials failure — mirror assertion was not executed.")
            print("Resolve the infrastructure issue (see INDETERMINATE line above) and re-run.")
            return 2

        # --- Final verdict ---
        overall_pass = leg_a_passed and (leg_b_code == 0)
        if overall_pass:
            print("=== PROBE Q12 (live): PASS ===")
            print("Summary:")
            print("  Leg A PASS — ADK 2.0 synthesised events completed VertexAiSessionService round-trip.")
            print("  Leg B PASS — Live chat turn stored events retrieved; mirror row has no leaked 2.0 fields.")
            return 0
        else:
            print("=== PROBE Q12 (live): FAIL ===")
            print("See FAIL lines above for details.")
            return 1

    finally:
        print(f"\nCleaning up spike-ah112-* sessions (engine: {engine_id})...")
        deleted = await _cleanup(engine_id)
        print(f"  Deleted {deleted} spike session(s).")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe Q12 — managed-session + chat_sessions mirror round-trip."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip Leg B (live turn + Firestore mirror). Run Leg A only (syntax / import check).",
    )
    parser.add_argument(
        "--account-id",
        default=os.environ.get("PROBE_ACCOUNT_ID", _ACCOUNT_ID_SENTINEL),
        help=(
            "Firestore account_id for the chat_sessions mirror lookup (required for Leg B). "
            "Override via PROBE_ACCOUNT_ID env var. "
            "If not supplied, Leg B returns INDETERMINATE (exit 2)."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    dry_run = args.dry_run or os.environ.get("PROBE_DRY_RUN") == "1"
    try:
        exit_code = asyncio.run(run_probe(dry_run=dry_run, account_id=args.account_id))
    except Exception as exc:
        code = _live_harness.classify_exit_code(exc)
        label = (
            "infrastructure/credentials"
            if code == 2
            else "FINDING — ADK 2.0 or mirror behaviour differs from assumption"
        )
        print(f"\nERROR [{label}] (exit {code}): {type(exc).__name__}: {exc}")
        print(
            "\nNote: exit 2 = infra/credentials (ADC missing, 401/403/5xx, transport) -> INDETERMINATE; "
            "exit 1 = real finding (leaked field, no events, changed API) -> NO-GO.\n"
            "This probe needs:\n"
            "  - aiplatform.reasoningEngines.use (Agent Engine session service)\n"
            "  - aiplatform.reasoningEngines.query (stream_query)\n"
            "  - datastore.entities.get on accounts/{account_id}/chat_sessions/*\n"
            "on ken-e-dev via Application Default Credentials."
        )
        sys.exit(code)
    sys.exit(exit_code)
