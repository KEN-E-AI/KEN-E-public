"""Probe Q8 — Send one probe turn to the deployed ephemeral spike engine. (LIVE)

Reads the ephemeral engine resource name written by spike_deploy.py --keep,
sends one probe turn via the Agent Engine stream_query / async_stream_query
path, asserts a non-empty text response, and records the engine displayName.

Run with (from repo root):
    .venv-adk2/bin/python docs/spike-adk2/probe-8-deploy-probe-turn.py

Prerequisites:
    1. Run spike_deploy.py --keep first to create the ephemeral engine and
       write its resource name to docs/spike-adk2/.spike_engine_id.
    2. gcloud auth application-default login (ADC configured for ken-e-dev).

Findings (AH-104 Wave 2):
    Q8: Validates that the deployed AdkApp responds to a stream_query call,
    confirming the engine packaging + ADK 2.0 App wrapper are functional.
    The displayName is asserted to carry the spike prefix so the probe can
    confirm it hit the ephemeral engine (not the canonical one).

Exit codes:
    0 — non-empty text response received; displayName verified
    1 — assertion failed (empty response, wrong engine, missing fields)
    2 — infrastructure/credentials error (ADC, 401/403/429/5xx, missing .spike_engine_id)

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

print("=== Probe Q8 (live): Deploy probe turn — ephemeral spike engine ===\n")

# ---------------------------------------------------------------------------
# AH-104 spike constants
# ---------------------------------------------------------------------------
_SPIKE_ENGINE_ID_FILE: Path = _HERE / ".spike_engine_id"
_SPIKE_USER_ID_PREFIX: str = "spike-ah104-"
_PROBE_MESSAGE: str = "Say hello and tell me your name."
_DISPLAY_NAME_PREFIX: str = "ken-e-chat-agent-spike-ah104"


def _summarise_event(event: Any) -> dict[str, Any]:
    """Return a compact dict summary of an ADK 2.0 Event for diagnostic output."""
    usage = getattr(event, "usage_metadata", None)
    content = getattr(event, "content", None)
    parts = getattr(content, "parts", None) or []
    text_parts = [
        getattr(p, "text", None) for p in parts if getattr(p, "text", None)
    ]
    return {
        "author": getattr(event, "author", None),
        "turn_complete": getattr(event, "turn_complete", None),
        "has_usage_metadata": usage is not None,
        "text_preview": (text_parts[0][:80] if text_parts else None),
    }


async def _cleanup_ah104_sessions(engine_id: str) -> int:
    """Delete all spike-ah104-* sessions for the given engine resource ID.

    The engine_id here is the BARE numeric ID extracted from the resource name,
    matching the pattern used by VertexAiSessionService(agent_engine_id=...).
    """
    return await _live_harness.cleanup_spike_sessions(
        project=_live_harness._DEFAULT_PROJECT,
        location=_live_harness._DEFAULT_LOCATION,
        engine_id=engine_id,
        user_id_prefix=_SPIKE_USER_ID_PREFIX,
    )


async def run_probe() -> int:
    """Run the live Q8 probe.  Returns exit code (0=pass, 1=fail, 2=error)."""

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

    # Extract the bare numeric engine ID from the resource name for session service.
    # Resource format: projects/<num>/locations/<loc>/reasoningEngines/<id>
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
            "  This probe will NOT query the canonical engine. Aborting."
        )
        return 1

    print(f"Ephemeral engine resource name : {resource_name}")
    print(f"Bare engine ID                 : {bare_engine_id}")

    # ------------------------------------------------------------------
    # 2. Retrieve the engine object and record its displayName
    # ------------------------------------------------------------------
    try:
        import vertexai
        from vertexai import agent_engines

        vertexai.init(
            project=_live_harness._DEFAULT_PROJECT,
            location=_live_harness._DEFAULT_LOCATION,
        )
        engine_obj = agent_engines.get(resource_name)
        display_name: str = getattr(engine_obj, "display_name", "") or ""
        print(f"Engine displayName             : {display_name!r}")
    except Exception as exc:
        code = _live_harness.classify_exit_code(exc)
        print(
            f"\nERROR [{'infra' if code == 2 else 'finding'}]: "
            f"Failed to retrieve engine: {type(exc).__name__}: {exc}"
        )
        return code

    # ------------------------------------------------------------------
    # 3. Build session service and generate a unique user/session ID
    # ------------------------------------------------------------------
    user_id = f"{_SPIKE_USER_ID_PREFIX}{uuid.uuid4()}"
    print(f"Probe user_id                  : {user_id}")

    try:
        from google.adk.sessions.vertex_ai_session_service import VertexAiSessionService

        svc = VertexAiSessionService(
            project=_live_harness._DEFAULT_PROJECT,
            location=_live_harness._DEFAULT_LOCATION,
            agent_engine_id=bare_engine_id,
        )
        session = await svc.create_session(
            app_name=bare_engine_id,
            user_id=user_id,
        )
        session_id = session.id
        print(f"Session created                : {session_id}")
    except Exception as exc:
        code = _live_harness.classify_exit_code(exc)
        print(
            f"\nERROR [{'infra' if code == 2 else 'finding'}]: "
            f"Session creation failed: {type(exc).__name__}: {exc}"
        )
        return code

    try:
        # ------------------------------------------------------------------
        # 4. Send the probe turn via stream_query / async_stream_query
        #    The AdkApp deployed to Agent Engine exposes both.  Prefer the
        #    async variant; fall back to the sync stream_query if unavailable.
        # ------------------------------------------------------------------
        print(f"\nSending probe turn: {_PROBE_MESSAGE!r}")
        response_text: str = ""
        raw_response_chunks: list[Any] = []

        # Try async_stream_query first (preferred — non-blocking on I/O-heavy turns).
        _async_query = getattr(engine_obj, "async_stream_query", None)
        _sync_query = getattr(engine_obj, "stream_query", None)

        if _async_query is not None:
            print("  Using: engine.async_stream_query()")
            async for chunk in engine_obj.async_stream_query(
                message=_PROBE_MESSAGE,
                user_id=user_id,
                session_id=session_id,
            ):
                raw_response_chunks.append(chunk)
                # Each chunk may be a dict or an object with a 'text' attribute.
                if isinstance(chunk, dict):
                    response_text += chunk.get("text", "") or ""
                else:
                    response_text += getattr(chunk, "text", "") or ""
        elif _sync_query is not None:
            print("  Using: engine.stream_query() (async_stream_query not available)")
            for chunk in engine_obj.stream_query(
                message=_PROBE_MESSAGE,
                user_id=user_id,
                session_id=session_id,
            ):
                raw_response_chunks.append(chunk)
                if isinstance(chunk, dict):
                    response_text += chunk.get("text", "") or ""
                else:
                    response_text += getattr(chunk, "text", "") or ""
        else:
            print(
                "FAIL: engine object has neither async_stream_query nor stream_query.\n"
                f"  Available attrs: {[a for a in dir(engine_obj) if 'query' in a.lower()]}"
            )
            return 1

        print(f"\nTotal response chunks received : {len(raw_response_chunks)}")
        print(f"Assembled response text        : {response_text[:200]!r}")

        # ------------------------------------------------------------------
        # 5. Assertions
        # ------------------------------------------------------------------
        assertion_failures: list[str] = []

        # A1: Non-empty response text
        if not response_text.strip():
            assertion_failures.append(
                "FAIL A1: Response text is empty. "
                "The deployed engine returned no text content for the probe turn."
            )
        else:
            print(
                f"\nPASS A1: Non-empty response received "
                f"({len(response_text)} chars)."
            )

        # A2: displayName carries the spike prefix (confirms we hit the ephemeral engine)
        if not display_name.startswith(_DISPLAY_NAME_PREFIX):
            assertion_failures.append(
                f"FAIL A2: displayName {display_name!r} does not start with "
                f"{_DISPLAY_NAME_PREFIX!r}. Did we hit the wrong engine?"
            )
        else:
            print(f"PASS A2: displayName prefix confirmed: {display_name!r}")

        # A3: At least one chunk was received
        if not raw_response_chunks:
            assertion_failures.append(
                "FAIL A3: No chunks received from stream_query. "
                "The engine stream returned zero items."
            )
        else:
            print(f"PASS A3: {len(raw_response_chunks)} chunk(s) received from stream.")

        if assertion_failures:
            print("\n=== PROBE Q8: FAIL ===")
            for failure in assertion_failures:
                print(f"  {failure}")
            return 1

        print("\n=== PROBE Q8: PASS ===")
        print("All assertions hold:")
        print("  A1: Non-empty response text from the deployed ephemeral engine.")
        print("  A2: Engine displayName confirms the correct ephemeral spike engine.")
        print("  A3: Stream returned at least one response chunk.")
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
            "exit 1 = a real finding (empty response, wrong engine, changed ADK API) -> NO-GO.\n"
            "This probe needs Agent Engine access on ken-e-dev "
            "(ADC via 'gcloud auth application-default login') "
            "and a live .spike_engine_id written by spike_deploy.py --keep."
        )
        sys.exit(code)
    sys.exit(exit_code)
