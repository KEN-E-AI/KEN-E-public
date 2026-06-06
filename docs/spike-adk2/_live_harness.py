"""Live-run harness for the AH-99 Phase 0.5 spike.

Provides:
  - import_real_modules()   — load real extract_billable_tokens + SessionTurnAccumulator
  - make_runner()           — build an ADK 2.0 Runner backed by VertexAiSessionService
  - run_and_collect()       — drive one turn and return every Event
  - cleanup_spike_sessions()— enumerate + delete spike-ah99-* sessions from dev engine
  - MAX_TURNS_PER_PROBE     — budget ceiling per probe
  - assert_under_budget()   — fail-fast when callers exceed the call ceiling

ISOLATION GUARANTEE: This module only runs inside .venv-adk2/ (ADK 2.0.0).
Never import it from the main project uv env (ADK 1.34.1) — the Event shape
differs and would break extract_billable_tokens callers in the main codebase.

Credentials: Application Default Credentials (run `gcloud auth
application-default login` before executing any probe that makes live calls).
"""

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import os
import sys
import uuid
from typing import TYPE_CHECKING, Any, Callable

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_TURNS_PER_PROBE: int = 3
"""Hard ceiling on per-probe turns against the live Gemini model."""

_SPIKE_USER_ID_PREFIX: str = "spike-ah99-"
"""Every session this harness creates uses this prefix.  cleanup_spike_sessions()
filters on it so only spike sessions are deleted — never production sessions."""

# Dev Agent Engine config — sourced from app/adk/.env.development
_DEFAULT_PROJECT: str = "ken-e-dev"
_DEFAULT_PROJECT_NUMBER: str = "525657242938"
"""Numeric GCP project number for ken-e-dev.  Used to build full Vertex AI resource names
of the form projects/{number}/locations/{location}/reasoningEngines/{id}.
Source of truth: `gcloud projects describe ken-e-dev --format='value(projectNumber)'`."""
_DEFAULT_LOCATION: str = "us-central1"
_DEFAULT_ENGINE_ID: str = "5957383247464759296"
"""The reasoningEngines resource ID for the dev Agent Engine.
Full resource: projects/525657242938/locations/us-central1/reasoningEngines/5957383247464759296
The VertexAiSessionService constructor accepts the bare numeric ID."""

_DEFAULT_MODEL: str = "gemini-2.0-flash"
"""Cheapest Gemini Flash model.  Probes must not use Pro or experimental models.

NOTE (AH-99 live run, 2026-06-01): the pinned alias ``gemini-2.0-flash-001``
reproducibly 404s through ADK 2.0's env-based genai client (which does not pass
project/location explicitly), even though it resolves fine via a direct
``Client(vertexai=True, project=..., location=...)`` call.  The unversioned
``gemini-2.0-flash`` resolves correctly on ken-e-dev/us-central1."""

# ---------------------------------------------------------------------------
# Vertex AI routing for the model client
# ---------------------------------------------------------------------------
# ADK 2.0 builds its google.genai client from the environment, NOT from the
# VertexAiSessionService config.  Without these three vars the model layer
# falls back to the Gemini API (AI Studio) backend and raises "No API key was
# provided".  The whole spike targets ken-e-dev, so set them explicitly here
# (overriding any inherited shell value such as ken-e-production) so the probes
# are self-contained — no manual `export` needed, per README.
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
os.environ["GOOGLE_CLOUD_PROJECT"] = _DEFAULT_PROJECT
os.environ["GOOGLE_CLOUD_LOCATION"] = _DEFAULT_LOCATION

# ---------------------------------------------------------------------------
# Real-module import contract
# ---------------------------------------------------------------------------

# Resolved lazily by import_real_modules(); stored here for assertion re-checks.
_extract_billable_tokens: Callable[..., Any] | None = None
_SessionTurnAccumulator: type | None = None


def import_real_modules() -> tuple[Callable[..., Any], type]:
    """Import the real shared.token_accounting and chat.accumulator modules.

    Uses sys.path injection so the source files in the workspace are loaded
    directly — not copies, not re-implementations.  Two assertions confirm
    the files come from the correct repo workspace paths:
      - extract_billable_tokens must live at shared/token_accounting.py
      - SessionTurnAccumulator must live at api/src/kene_api/chat/accumulator.py

    Returns:
        Tuple of (extract_billable_tokens, SessionTurnAccumulator).

    Raises:
        AssertionError: if either import resolves to a file outside the repo
                        workspace (e.g. a stale .venv-adk2 copy was installed).
        ImportError: if the workspace root cannot be determined.
    """
    global _extract_billable_tokens, _SessionTurnAccumulator

    workspace_root = _find_workspace_root()

    # Inject workspace root and api/src so imports resolve to real source files.
    for path in [workspace_root, os.path.join(workspace_root, "api", "src")]:
        if path not in sys.path:
            sys.path.insert(0, path)

    from shared.token_accounting import (  # type: ignore[import]
        extract_billable_tokens,
    )
    from kene_api.chat.accumulator import (  # type: ignore[import]
        SessionTurnAccumulator,
    )

    # Assertion: must come from the actual workspace source tree.
    etb_path = inspect.getsourcefile(extract_billable_tokens)
    sta_path = inspect.getsourcefile(SessionTurnAccumulator)

    assert etb_path is not None, "extract_billable_tokens has no source file"
    assert "shared/token_accounting.py" in etb_path, (
        f"extract_billable_tokens loaded from unexpected path: {etb_path!r}\n"
        "Expected path containing 'shared/token_accounting.py'."
    )
    assert sta_path is not None, "SessionTurnAccumulator has no source file"
    assert "kene_api/chat/accumulator.py" in sta_path, (
        f"SessionTurnAccumulator loaded from unexpected path: {sta_path!r}\n"
        "Expected path containing 'kene_api/chat/accumulator.py'."
    )

    _extract_billable_tokens = extract_billable_tokens
    _SessionTurnAccumulator = SessionTurnAccumulator
    return extract_billable_tokens, SessionTurnAccumulator


# ---------------------------------------------------------------------------
# Runner factory
# ---------------------------------------------------------------------------


def make_runner(
    coordinator: Any,
    *,
    project: str = _DEFAULT_PROJECT,
    location: str = _DEFAULT_LOCATION,
    engine_id: str = _DEFAULT_ENGINE_ID,
    user_id_prefix: str = _SPIKE_USER_ID_PREFIX,
) -> tuple[Any, str]:
    """Build an ADK 2.0 Runner backed by VertexAiSessionService.

    Creates a fresh session under a unique `spike-ah99-<uuid4>` user_id.
    Each probe must call cleanup_spike_sessions() in a finally block.

    Args:
        coordinator: The root LlmAgent to run.
        project:     GCP project ID.
        location:    Vertex AI region.
        engine_id:   Bare reasoningEngines resource ID (numeric string).
        user_id_prefix: Prefix for the ephemeral user_id.

    Returns:
        Tuple of (Runner, user_id) — pass user_id to cleanup_spike_sessions().
    """
    from google.adk.runners import Runner
    from google.adk.sessions.vertex_ai_session_service import VertexAiSessionService

    user_id = f"{user_id_prefix}{uuid.uuid4()}"
    session_service = VertexAiSessionService(
        project=project,
        location=location,
        agent_engine_id=engine_id,
    )
    # Runner.app_name must start with a letter (App name validation in ADK 2.0).
    # The VertexAiSessionService uses its own _agent_engine_id (set in __init__)
    # and ignores the Runner's app_name when resolving the reasoning engine, so
    # the two names are independent.
    runner_app_name = "spike-ah99-probe"
    runner = Runner(
        agent=coordinator,
        session_service=session_service,
        auto_create_session=True,
        app_name=runner_app_name,
    )
    # Store the engine_id on the runner so run_and_collect can pass it to
    # session_service.create_session (which VertexAiSessionService resolves
    # internally via _get_reasoning_engine_id — any string works since
    # _agent_engine_id is already set in the constructor).
    runner._spike_engine_id = engine_id  # type: ignore[attr-defined]
    return runner, user_id


async def run_and_collect(
    runner: Any,
    prompt: str,
    *,
    user_id: str,
) -> list[Any]:
    """Drive one turn through Runner.run_async and collect all yielded Events.

    Pre-creates a session via the session service, then drives one turn via
    Runner.run_async.  Returns every Event yielded (inner + outer).

    Args:
        runner:  A Runner created by make_runner().
        prompt:  The user message for this turn.
        user_id: The unique user_id from make_runner().

    Returns:
        List of every Event yielded by the runner (inner + outer).
    """
    from google.genai.types import Content, Part

    assert_under_budget()

    new_message = Content(role="user", parts=[Part(text=prompt)])

    # Pre-create the session via the session service.
    # VertexAiSessionService.create_session uses _agent_engine_id internally
    # when resolving the reasoning engine, so app_name here is just passed
    # through to the stored Session.app_name — any string is fine.
    session_service = runner.session_service  # type: ignore[attr-defined]
    app_name = runner.app_name  # type: ignore[attr-defined]
    session = await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
    )

    events: list[Any] = []
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=new_message,
    ):
        events.append(event)

    return events


async def cleanup_spike_sessions(
    *,
    project: str = _DEFAULT_PROJECT,
    location: str = _DEFAULT_LOCATION,
    engine_id: str = _DEFAULT_ENGINE_ID,
    user_id_prefix: str = _SPIKE_USER_ID_PREFIX,
) -> int:
    """Enumerate and delete all sessions with the spike user_id prefix.

    Safe to call multiple times (idempotent).  Returns the count of sessions
    deleted in this invocation (0 if none were found).

    The filter is performed client-side from the list_sessions response so
    the implementation is robust even if Vertex AI doesn't support prefix
    filtering in the API query.

    Args:
        project:       GCP project ID.
        location:      Vertex AI region.
        engine_id:     Bare reasoningEngines resource ID.
        user_id_prefix: Prefix to match — only sessions whose user_id starts
                        with this prefix are deleted.

    Returns:
        Number of sessions deleted.
    """
    from google.adk.sessions.vertex_ai_session_service import VertexAiSessionService

    svc = VertexAiSessionService(
        project=project,
        location=location,
        agent_engine_id=engine_id,
    )

    # list_sessions supports a user_id filter; but since the prefix varies per
    # probe run we list all and filter client-side.
    try:
        list_response = await svc.list_sessions(app_name=engine_id)
    except Exception as exc:
        print(f"  NOTE: list_sessions unavailable — {exc}")
        print(
            "  Returning 0: spike session count is unknown — "
            "manual verification recommended if probes ran with live credentials."
        )
        return 0
    spike_sessions = [
        s for s in list_response.sessions
        if s.user_id.startswith(user_id_prefix)
    ]

    deleted = 0
    for session in spike_sessions:
        try:
            await svc.delete_session(
                app_name=engine_id,
                user_id=session.user_id,
                session_id=session.id,
            )
            deleted += 1
        except Exception as exc:
            # Log but do not re-raise — idempotency guarantee means a failed
            # delete on one session should not abort the rest.
            print(f"  WARNING: failed to delete session {session.id}: {exc}")

    return deleted


# ---------------------------------------------------------------------------
# Budget enforcement
# ---------------------------------------------------------------------------

_turn_count: int = 0


def assert_under_budget(extra: int = 1) -> None:
    """Raise AssertionError if adding `extra` turns would exceed MAX_TURNS_PER_PROBE.

    Call once before each live model invocation.

    Args:
        extra: Number of turns about to be consumed (default 1).
    """
    global _turn_count
    _turn_count += extra
    assert _turn_count <= MAX_TURNS_PER_PROBE, (
        f"Budget exceeded: {_turn_count} turns consumed, ceiling is {MAX_TURNS_PER_PROBE}. "
        "The spike guardrail (≤50 aggregate calls, ≤3 per probe) has been reached."
    )


def reset_turn_count() -> None:
    """Reset the per-process turn counter.  Call between probes in test suites."""
    global _turn_count
    _turn_count = 0


# ---------------------------------------------------------------------------
# Exit-code classification
# ---------------------------------------------------------------------------

# HTTP status codes that mean "infrastructure / credentials", not "ADK 2.0
# behaved differently than the spike assumed".
_INFRA_STATUS_CODES = (401, 403, 429, 500, 502, 503, 504)
_INFRA_ERROR_MARKERS = (
    "defaultcredentialserror",
    "could not automatically determine credentials",
    "permission denied",
    "permissiondenied",
    "unauthenticated",
    "reauthentication",
    "503",
    "service unavailable",
    "deadline exceeded",
    "connection",
)


def classify_exit_code(exc: BaseException) -> int:
    """Map an uncaught probe exception to exit code 2 (infra) or 1 (finding).

    Exit 2 — infrastructure/credentials: missing ADC, 401/403/429/5xx, transport
        errors.  These are NOT findings about ADK 2.0 and route to INDETERMINATE.
    Exit 1 — a real finding: 404 model-not-found, TypeError/AttributeError from a
        changed ADK API, pydantic.ValidationError on a new field, etc.  These ARE
        findings and route to NO-GO.

    This is the fix for the AH-99 review nit: a bare ``except Exception -> exit 2``
    silently buckets genuine NO-GO signals (e.g. a renamed ``run_node``) as
    INDETERMINATE.  Inspect status codes and a marker substring set instead.
    """
    code = getattr(exc, "code", None)
    if isinstance(code, int) and code in _INFRA_STATUS_CODES:
        return 2
    text = f"{type(exc).__name__}: {exc}".lower()
    if any(marker in text for marker in _INFRA_ERROR_MARKERS):
        return 2
    return 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_workspace_root() -> str:
    """Return the absolute path to the KEN-E repository workspace root.

    Walks up from this file's location until it finds CLAUDE.md, which marks
    the repo root.  Raises RuntimeError if not found within 10 levels.
    """
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        if os.path.exists(os.path.join(current, "CLAUDE.md")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    raise RuntimeError(
        "Could not locate repository root (CLAUDE.md not found). "
        "Run probes from inside the KEN-E workspace."
    )
