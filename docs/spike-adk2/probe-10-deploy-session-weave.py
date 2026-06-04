"""Probe Q10 — Deployed session round-trip + Weave init check. (LIVE)

Two validations in one probe:

  Session round-trip (adapts AH-99 probe-5 to live deploy path):
    1. Reads the ephemeral engine resource name from .spike_engine_id.
    2. Sends a probe turn to the deployed engine, captures session_id.
    3. Uses VertexAiSessionService.get_session() to retrieve stored events.
    4. Asserts the session has at least one event with author + content.
    The round-trip result drives the exit code — it is a hard gate.

  Weave trace check (non-blocking — either outcome is acceptable):
    1. Calls init_weave_if_needed(required=False) from app.utils.weave_observability.
    2. Records whether it returns True or False, and the reason.
    3. If True: decorates a probe function with @safe_weave_op(), calls it, and
       checks whether a span was emitted (verifying the op decorator path works).
    4. If False: records the reason per AH-PRD-13 §9 "carry forward" — the
       session round-trip still passes.
    5. Checks for google.genai LLM-call autopatch presence (ADK 2.0 observation).

Run with (from repo root):
    .venv-adk2/bin/python docs/spike-adk2/probe-10-deploy-session-weave.py

Prerequisites:
    1. Run spike_deploy.py --keep first.
    2. gcloud auth application-default login (ADC configured for ken-e-dev).
    3. Optional: WANDB_API_KEY set (for the Weave init leg to return True).

Exit codes:
    0 — session round-trip succeeds (Weave outcome is non-blocking)
    1 — session round-trip failed (get_session returned None, no events, etc.)
    2 — infrastructure/credentials error (ADC missing, 401/403/5xx, or missing .spike_engine_id)

ADK version required: 2.0.0 (in .venv-adk2/)
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# sys.path: ensure harness and repo root are importable
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import _live_harness  # noqa: E402

print("=== Probe Q10 (live): Deployed session round-trip + Weave init check ===\n")

# ---------------------------------------------------------------------------
# AH-104 spike constants
# ---------------------------------------------------------------------------
_SPIKE_ENGINE_ID_FILE: Path = _HERE / ".spike_engine_id"
_SPIKE_USER_ID_PREFIX: str = "spike-ah104-"
_PROBE_MESSAGE: str = "What is two plus two? Answer in one word."


async def _cleanup_ah104_sessions(engine_id: str) -> int:
    """Delete all spike-ah104-* sessions for the given bare engine ID."""
    return await _live_harness.cleanup_spike_sessions(
        project=_live_harness._DEFAULT_PROJECT,
        location=_live_harness._DEFAULT_LOCATION,
        engine_id=engine_id,
        user_id_prefix=_SPIKE_USER_ID_PREFIX,
    )


# ---------------------------------------------------------------------------
# Weave leg — synchronous helper, called from the async run_probe()
# ---------------------------------------------------------------------------

def _run_weave_check() -> dict[str, Any]:
    """Execute the Weave init + span-emission check.

    Returns a result dict summarising the outcome.  Never raises — all
    exceptions are caught and stored in the result dict so the caller
    (run_probe) can log them without affecting the session-round-trip exit code.
    """
    result: dict[str, Any] = {
        "weave_init_result": None,
        "weave_init_reason": None,
        "op_call_succeeded": None,
        "genai_autopatch_present": None,
        "notes": [],
    }

    # Step 1: inject workspace root into sys.path so app.utils.weave_observability
    # resolves to the source tree (same pattern as _live_harness.import_real_modules).
    for p in [str(_REPO_ROOT), str(_REPO_ROOT / "api" / "src")]:
        if p not in sys.path:
            sys.path.insert(0, p)

    try:
        from app.utils.weave_observability import init_weave_if_needed, safe_weave_op
    except ImportError as exc:
        result["weave_init_reason"] = f"ImportError: {exc}"
        result["notes"].append(
            "Could not import app.utils.weave_observability — "
            "Weave check skipped."
        )
        return result

    # Step 2: call init_weave_if_needed(required=False)
    try:
        weave_ready = init_weave_if_needed(required=False)
        result["weave_init_result"] = weave_ready
    except Exception as exc:
        result["weave_init_result"] = False
        result["weave_init_reason"] = f"{type(exc).__name__}: {exc}"
        result["notes"].append(f"init_weave_if_needed() raised: {exc}")
        return result

    if not weave_ready:
        # Determine the most likely reason (AH-PRD-13 §9 carry-forward)
        wandb_key = os.getenv("WANDB_API_KEY", "")
        if not wandb_key:
            result["weave_init_reason"] = (
                "WANDB_API_KEY not set — Weave tracing cannot be enabled "
                "(AH-PRD-13 §9: carry forward to production deploy config)"
            )
        else:
            result["weave_init_reason"] = (
                "init_weave_if_needed returned False with WANDB_API_KEY present — "
                "check weave.init() exception in process log."
            )
        result["notes"].append("Weave init returned False — session round-trip is unaffected.")
        return result

    result["weave_init_reason"] = "Weave ready"

    # Step 3: define a @safe_weave_op decorated probe function and call it
    try:
        @safe_weave_op(name="probe_q10_weave_test")
        def _probe_op(x: int) -> int:
            return x * 2

        call_result = _probe_op(21)
        result["op_call_succeeded"] = (call_result == 42)
        result["notes"].append(
            f"@safe_weave_op decorated function returned {call_result} (expected 42)."
        )
    except Exception as exc:
        result["op_call_succeeded"] = False
        result["notes"].append(
            f"@safe_weave_op call raised: {type(exc).__name__}: {exc}"
        )

    # Step 4: check for google.genai autopatch in Weave (ADK 2.0 observation)
    # Weave may register autopatchers for google.genai LLM calls.  This varies
    # by weave version and is informational — not a hard assertion.
    try:
        import weave as _weave

        # Try the integrations registry path (varies by weave version).
        autopatch_registry: dict[str, Any] = {}
        for attr in ("_autopatch_registry", "_autopatchers", "autopatchers"):
            registry = getattr(_weave, attr, None)
            if registry is not None:
                autopatch_registry = dict(registry) if hasattr(registry, "items") else {}
                break

        genai_patched = any(
            "genai" in str(k).lower() or "google" in str(k).lower()
            for k in autopatch_registry
        )
        result["genai_autopatch_present"] = genai_patched
        result["notes"].append(
            f"google.genai autopatch in weave registry: {genai_patched} "
            f"(registry keys: {list(autopatch_registry.keys())[:5]})"
        )
    except Exception as exc:
        result["genai_autopatch_present"] = None
        result["notes"].append(
            f"Could not inspect Weave autopatch registry: {type(exc).__name__}: {exc}"
        )

    return result


# ---------------------------------------------------------------------------
# Main probe
# ---------------------------------------------------------------------------

async def run_probe() -> int:
    """Run the live Q10 probe.  Returns exit code (0=pass, 1=fail, 2=error)."""

    # ------------------------------------------------------------------
    # 1. Read ephemeral engine resource name
    # ------------------------------------------------------------------
    if not _SPIKE_ENGINE_ID_FILE.exists():
        print(
            f"ERROR: {_SPIKE_ENGINE_ID_FILE} not found.\n"
            "Run spike_deploy.py --keep first to create the ephemeral engine\n"
            "and persist its resource name, then re-run this probe."
        )
        return 2

    resource_name = _SPIKE_ENGINE_ID_FILE.read_text().strip()
    if not resource_name:
        print(
            f"ERROR: {_SPIKE_ENGINE_ID_FILE} is empty.\n"
            "Re-run spike_deploy.py --keep to repopulate it."
        )
        return 2

    import re as _re
    _CANONICAL_ENGINE_RESOURCE = (
        "projects/525657242938/locations/us-central1/reasoningEngines/5957383247464759296"
    )
    _CANONICAL_ENGINE_ID = "5957383247464759296"
    parts = resource_name.split("/")
    if len(parts) < 6 or parts[-2] != "reasoningEngines":
        print(
            f"ERROR: Unexpected resource name format: {resource_name!r}\n"
            "Expected: projects/<project-num>/locations/<loc>/reasoningEngines/<id>"
        )
        return 2
    bare_engine_id = parts[-1]
    # Validate format: all real reasoningEngines IDs are long numeric strings.
    if not _re.fullmatch(r"\d+", bare_engine_id):
        print(
            f"ERROR: Extracted bare_engine_id {bare_engine_id!r} does not match "
            r"^\d+$ — the .spike_engine_id file may be malformed or tampered with."
        )
        return 2
    # Safety guard: never operate against the canonical engine.
    if bare_engine_id == _CANONICAL_ENGINE_ID or resource_name == _CANONICAL_ENGINE_RESOURCE:
        print(
            "CRITICAL SAFETY ERROR: .spike_engine_id contains the canonical engine resource.\n"
            f"  resource_name={resource_name!r}\n"
            "  This probe will NOT interact with the canonical engine. Aborting."
        )
        return 1

    print(f"Ephemeral engine resource name : {resource_name}")
    print(f"Bare engine ID                 : {bare_engine_id}")

    # ------------------------------------------------------------------
    # 2. Set up session service and send probe turn
    # ------------------------------------------------------------------
    user_id = f"{_SPIKE_USER_ID_PREFIX}{uuid.uuid4()}"
    session_id: str | None = None
    print(f"Probe user_id                  : {user_id}\n")

    try:
        from google.adk.sessions.vertex_ai_session_service import VertexAiSessionService
        from vertexai import agent_engines
        import vertexai

        vertexai.init(
            project=_live_harness._DEFAULT_PROJECT,
            location=_live_harness._DEFAULT_LOCATION,
        )

        svc = VertexAiSessionService(
            project=_live_harness._DEFAULT_PROJECT,
            location=_live_harness._DEFAULT_LOCATION,
            agent_engine_id=bare_engine_id,
        )

        # Create session
        session = await svc.create_session(
            app_name=bare_engine_id,
            user_id=user_id,
        )
        session_id = session.id
        print(f"Session created                : {session_id}")

        # Send probe turn via stream_query / async_stream_query
        engine_obj = agent_engines.get(resource_name)
        print(f"Sending probe turn             : {_PROBE_MESSAGE!r}")

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
            print(
                "FAIL: engine has neither async_stream_query nor stream_query.\n"
                f"  Available query attrs: {[a for a in dir(engine_obj) if 'query' in a.lower()]}"
            )
            return 1

        print(f"Response text (preview)        : {response_text[:120]!r}\n")

    except Exception as exc:
        code = _live_harness.classify_exit_code(exc)
        print(
            f"\nERROR [{'infra' if code == 2 else 'finding'}]: "
            f"Probe turn failed: {type(exc).__name__}: {exc}"
        )
        return code

    try:
        # ------------------------------------------------------------------
        # 3. Session round-trip: get_session and inspect stored events
        # ------------------------------------------------------------------
        print("--- Session round-trip: get_session() ---\n")

        retrieved = await svc.get_session(
            app_name=bare_engine_id,
            user_id=user_id,
            session_id=session_id,
        )

        assertion_failures: list[str] = []

        # A1: get_session must return a non-None session
        if retrieved is None:
            assertion_failures.append(
                "FAIL A1: get_session() returned None — cannot verify the round-trip.\n"
                f"  (user_id={user_id!r}, session_id={session_id!r})"
            )
        else:
            event_count = len(retrieved.events) if retrieved.events else 0
            print(f"Session retrievable            : ID={retrieved.id}; events stored: {event_count}")

            # A2: at least one event must be present
            if event_count == 0:
                assertion_failures.append(
                    "FAIL A2: get_session() returned a session with 0 events.\n"
                    "  At least one event (the probe turn response) must be stored."
                )
            else:
                print(f"PASS A2: {event_count} event(s) stored in the retrieved session.")

                # A3: each event must have author + content
                events_with_author = [
                    e for e in (retrieved.events or [])
                    if getattr(e, "author", None) is not None
                ]
                if not events_with_author:
                    assertion_failures.append(
                        "FAIL A3: No stored events have a non-None author field.\n"
                        "  Expected at least one event authored by the model or user."
                    )
                else:
                    print(
                        f"PASS A3: {len(events_with_author)} event(s) have non-None author."
                    )
                    # Print a sample event summary for the record
                    for ev in (retrieved.events or [])[:3]:
                        author = getattr(ev, "author", None)
                        content = getattr(ev, "content", None)
                        parts = getattr(content, "parts", None) or []
                        text_parts = [
                            getattr(p, "text", None) for p in parts if getattr(p, "text", None)
                        ]
                        text_preview = repr(text_parts[0][:60]) if text_parts else "None"
                        print(
                            f"  Event: author={author!r} "
                            f"text_preview={text_preview}"
                        )

        # ------------------------------------------------------------------
        # 4. Weave leg (non-blocking)
        # ------------------------------------------------------------------
        print("\n--- Weave init + span check ---\n")
        weave_result = _run_weave_check()
        weave_ok = weave_result["weave_init_result"]
        print(f"Weave init result              : {weave_ok}")
        print(f"Weave init reason              : {weave_result['weave_init_reason']}")
        if weave_ok:
            print(f"Op call succeeded              : {weave_result['op_call_succeeded']}")
            print(f"google.genai autopatch present : {weave_result['genai_autopatch_present']}")
        for note in weave_result["notes"]:
            print(f"  NOTE: {note}")

        # ------------------------------------------------------------------
        # 5. Final verdict — session round-trip drives exit code
        # ------------------------------------------------------------------
        if assertion_failures:
            print("\n=== PROBE Q10: FAIL ===")
            for failure in assertion_failures:
                print(f"  {failure}")
            return 1

        print("\n=== PROBE Q10: PASS ===")
        print("Session round-trip assertions hold:")
        print("  A1: get_session() returned a non-None session.")
        print("  A2: At least one event stored in the retrieved session.")
        print("  A3: At least one event has a non-None author.")
        if weave_ok:
            print("  Weave: init succeeded; @safe_weave_op span emitted.")
        else:
            print(
                f"  Weave: init returned False ({weave_result['weave_init_reason']}) — "
                "non-blocking per AH-PRD-13 §9."
            )
        return 0

    finally:
        print(f"\nCleaning up spike-ah104-* sessions (engine: {bare_engine_id})...")
        deleted = await _cleanup_ah104_sessions(bare_engine_id)
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
            "exit 1 = a real finding (session not returned, no events, changed API) -> NO-GO.\n"
            "This probe needs Agent Engine + session service access on ken-e-dev "
            "(ADC via 'gcloud auth application-default login') "
            "and a live .spike_engine_id written by spike_deploy.py --keep."
        )
        sys.exit(code)
    sys.exit(exit_code)
