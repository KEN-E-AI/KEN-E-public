"""AH-104 spike cleanup — delete the ephemeral spike engine and its sessions.

Reads the ephemeral engine resource name from docs/spike-adk2/.spike_engine_id,
deletes it (force=True), verifies the canonical engine is still present, cleans
up all spike-ah104-* sessions, and removes the .spike_engine_id file.

SAFETY INVARIANTS:
  1. NEVER touches the canonical engine (5957383247464759296).
     The script verifies the canonical engine is still alive after deletion
     so any accidental collision is caught immediately.
  2. Idempotent: safe to run even if the spike engine was already deleted.
     A 404 / "not found" response is treated as success.
  3. Does NOT call agent_engines.update() or anything that could mutate
     the canonical engine.

Usage (from repo root):
    .venv-adk2/bin/python docs/spike-adk2/cleanup_spike_engine.py

Exit codes:
    0 — cleanup complete (engine deleted or already gone; canonical engine confirmed alive)
    1 — unexpected error (engine deletion failed for a non-404 reason)
    2 — infrastructure/credentials error (ADC missing, 401/403/5xx)
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# sys.path: repo root and harness directory must be importable
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent          # docs/spike-adk2/
_REPO_ROOT = _HERE.parent.parent                 # repo root (contains CLAUDE.md)

if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# Vertex AI routing — set before any vertexai / genai import
# ---------------------------------------------------------------------------
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
os.environ["GOOGLE_CLOUD_PROJECT"] = "ken-e-dev"
os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger("cleanup_spike_engine")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_SPIKE_ENGINE_ID_FILE: Path = _HERE / ".spike_engine_id"

_CANONICAL_ENGINE_RESOURCE: str = (
    "projects/525657242938/locations/us-central1/reasoningEngines/5957383247464759296"
)
_SPIKE_USER_ID_PREFIX: str = "spike-ah104-"

_DEFAULT_PROJECT: str = "ken-e-dev"
_DEFAULT_LOCATION: str = "us-central1"
_DEFAULT_ENGINE_ID: str = "5957383247464759296"  # canonical engine bare ID


# ---------------------------------------------------------------------------
# Exit-code helper (consistent with probe convention in _live_harness.py)
# ---------------------------------------------------------------------------

_INFRA_ERROR_MARKERS = (
    "defaultcredentialserror",
    "could not automatically determine credentials",
    "permission denied",
    "permissiondenied",
    "does not have",        # GCS: "does not have storage.buckets.get access"
    "access denied",
    "forbidden",            # google.api_core.exceptions.Forbidden type name
    "unauthenticated",
    "reauthentication",
    "service unavailable",
    "deadline exceeded",
    "connection",
    "403",
    "401",
    "429",
    "500",
    "502",
    "503",
    "504",
)


def _classify_exit(exc: BaseException) -> int:
    """Return 2 for infra/credentials errors, 1 for genuine failures."""
    # Check multiple HTTP status code attributes — attribute name varies by SDK version
    # and whether the error came from HTTP vs gRPC transport.
    for attr in ("code", "status_code", "http_status"):
        code_val = getattr(exc, attr, None)
        if isinstance(code_val, int) and code_val in (401, 403, 429, 500, 502, 503, 504):
            return 2
    text = f"{type(exc).__name__}: {exc}".lower()
    if any(marker in text for marker in _INFRA_ERROR_MARKERS):
        return 2
    return 1


def _is_not_found(exc: BaseException) -> bool:
    """Return True if the exception represents a 404 / resource-not-found."""
    code = getattr(exc, "code", None)
    if code == 404:
        return True
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(phrase in text for phrase in ("not found", "404", "does not exist"))


# ---------------------------------------------------------------------------
# Spike session cleanup (async — wraps _live_harness.cleanup_spike_sessions)
# ---------------------------------------------------------------------------

async def _cleanup_sessions(spike_bare_id: str) -> int:
    """Delete all spike-ah104-* sessions from the spike engine (before deletion).

    Sessions created by probes 8 and 10 live on the spike engine, not on the
    canonical engine.  The engine deletion (step 3) with force=True may cascade-
    delete them automatically, but running this step first provides belt-and-
    suspenders assurance that no sessions linger if the cascade does not fire.

    Args:
        spike_bare_id: Bare reasoningEngines numeric ID of the spike engine
                       (extracted from the resource name by the caller).
    """
    import _live_harness

    return await _live_harness.cleanup_spike_sessions(
        project=_DEFAULT_PROJECT,
        location=_DEFAULT_LOCATION,
        engine_id=spike_bare_id,
        user_id_prefix=_SPIKE_USER_ID_PREFIX,
    )


# ---------------------------------------------------------------------------
# Main cleanup logic
# ---------------------------------------------------------------------------

def main() -> int:
    """Entry point.  Returns exit code (0=success, 1=failure, 2=infra error)."""

    print("=" * 68)
    print("AH-104 spike cleanup")
    print(f"  spike engine ID file  : {_SPIKE_ENGINE_ID_FILE}")
    print(f"  canonical engine      : {_CANONICAL_ENGINE_RESOURCE}")
    print(f"  session prefix        : {_SPIKE_USER_ID_PREFIX}")
    print("=" * 68)
    print()

    # ------------------------------------------------------------------
    # Step 1: Read the spike engine resource name
    # ------------------------------------------------------------------
    if not _SPIKE_ENGINE_ID_FILE.exists():
        print(
            f"INFO: {_SPIKE_ENGINE_ID_FILE} not found — "
            "no spike engine to clean up (already deleted or never created).\n"
            "Proceeding to session cleanup and canonical engine verification."
        )
        spike_resource_name: str | None = None
    else:
        spike_resource_name = _SPIKE_ENGINE_ID_FILE.read_text().strip() or None
        if not spike_resource_name:
            print(
                f"INFO: {_SPIKE_ENGINE_ID_FILE} is empty — "
                "no spike engine resource name to delete."
            )
            spike_resource_name = None
        else:
            print(f"Spike engine resource name : {spike_resource_name}")

    # ------------------------------------------------------------------
    # Step 2: Initialise Vertex AI SDK
    # ------------------------------------------------------------------
    try:
        import vertexai
        from vertexai import agent_engines

        vertexai.init(
            project=_DEFAULT_PROJECT,
            location=_DEFAULT_LOCATION,
        )
        logger.info("vertexai.init() done.")
    except Exception as exc:
        code = _classify_exit(exc)
        logger.error(
            "vertexai.init() failed: %s: %s", type(exc).__name__, exc
        )
        return code

    # ------------------------------------------------------------------
    # Step 3: Delete the spike engine (idempotent)
    # ------------------------------------------------------------------
    if spike_resource_name is not None:
        # Pre-deletion safety guard: abort if the resource name to be deleted
        # is the canonical engine.  This must never happen, but an explicit
        # check here makes the invariant enforcement proactive rather than
        # reactive (the post-deletion check in step 4 fires too late).
        if spike_resource_name == _CANONICAL_ENGINE_RESOURCE:
            print(
                "CRITICAL SAFETY ERROR: spike_resource_name matches the canonical "
                "engine resource name.\n"
                f"  spike_resource_name : {spike_resource_name!r}\n"
                f"  canonical           : {_CANONICAL_ENGINE_RESOURCE!r}\n"
                "  This must never happen — aborting without deleting anything.\n"
                "  Investigate how .spike_engine_id was written with the canonical ID."
            )
            return 1

        # Extract bare engine ID (last path segment) for session cleanup.
        spike_parts = spike_resource_name.split("/")
        if len(spike_parts) < 2 or spike_parts[-2] != "reasoningEngines":
            print(
                f"ERROR: spike_resource_name does not look like a reasoningEngines path: "
                f"{spike_resource_name!r}\n"
                "  Cannot extract bare engine ID — aborting."
            )
            return 1
        spike_bare_id = spike_parts[-1]
        # Validate it's numeric (all real reasoningEngines IDs are long integers)
        import re as _re
        if not _re.fullmatch(r"\d+", spike_bare_id):
            print(
                f"ERROR: extracted bare engine ID {spike_bare_id!r} does not match "
                r"^\d+$ — the resource name may be malformed.\n"
                f"  Full resource: {spike_resource_name!r}\n  Aborting."
            )
            return 1
        # Extra guard: the spike engine must not have the canonical engine's ID.
        if spike_bare_id == _DEFAULT_ENGINE_ID:
            print(
                "CRITICAL SAFETY ERROR: spike_bare_id matches the canonical engine ID "
                f"({_DEFAULT_ENGINE_ID!r}).\n"
                "  Aborting to protect the canonical engine."
            )
            return 1

        # Session cleanup (belt-and-suspenders: run before engine deletion so
        # sessions are explicitly removed even if the force=True cascade doesn't fire).
        print(f"\nCleaning up {_SPIKE_USER_ID_PREFIX}* sessions on spike engine {spike_bare_id} ...")
        try:
            deleted = asyncio.run(_cleanup_sessions(spike_bare_id))
            print(f"  Deleted {deleted} spike session(s) before engine deletion.")
        except Exception as exc:
            logger.warning(
                "Pre-deletion session cleanup failed (non-fatal, continuing): %s: %s",
                type(exc).__name__, exc,
            )
            print(
                f"  WARNING: Pre-deletion session cleanup failed: {type(exc).__name__}: {exc}\n"
                "  Continuing with engine deletion — force=True should cascade-delete sessions."
            )

        print(f"\nDeleting spike engine: {spike_resource_name} ...")
        try:
            spike_engine = agent_engines.get(spike_resource_name)
            spike_engine.delete(force=True)
            print("  Spike engine deleted successfully.")
            logger.info("Spike engine deleted: %s", spike_resource_name)
        except Exception as exc:
            if _is_not_found(exc):
                print(
                    f"  INFO: Spike engine already gone (404/not-found): {exc}\n"
                    "  Treating as success (idempotent)."
                )
            else:
                code = _classify_exit(exc)
                logger.error(
                    "Failed to delete spike engine %s: %s: %s",
                    spike_resource_name,
                    type(exc).__name__,
                    exc,
                )
                print(
                    f"\nERROR: Could not delete spike engine {spike_resource_name!r}.\n"
                    f"  {type(exc).__name__}: {exc}\n"
                    "  Manual cleanup may be needed."
                )
                return code
    else:
        print("\nSkipping engine deletion (no resource name available).")

    # ------------------------------------------------------------------
    # Step 4: Verify the canonical engine is still alive
    # ------------------------------------------------------------------
    print(f"\nVerifying canonical engine is still alive: {_CANONICAL_ENGINE_RESOURCE} ...")
    try:
        canonical_engine = agent_engines.get(_CANONICAL_ENGINE_RESOURCE)
        canonical_display_name = getattr(canonical_engine, "display_name", None) or ""
        canonical_rn = getattr(canonical_engine, "resource_name", None) or _CANONICAL_ENGINE_RESOURCE
        print(f"  Canonical engine alive: resource_name={canonical_rn!r}")
        print(f"  Canonical engine displayName: {canonical_display_name!r}")
        # Safety check: resource name must NOT be the spike engine
        if spike_resource_name and canonical_rn == spike_resource_name:
            print(
                "ERROR: canonical engine resource_name matches the spike engine resource_name!\n"
                "  This must never happen — the two engines must be distinct.\n"
                f"  canonical_rn={canonical_rn!r}, spike={spike_resource_name!r}"
            )
            return 1
        print("  PASS: Canonical engine confirmed alive and distinct from spike engine.")
    except Exception as exc:
        if _is_not_found(exc):
            # The canonical engine being "not found" is a severe error — it means
            # something went wrong and the production engine may be gone.
            print(
                f"\nCRITICAL ERROR: Canonical engine {_CANONICAL_ENGINE_RESOURCE!r} "
                f"returned 404/not-found: {exc}\n"
                "  Investigate immediately — this must not happen."
            )
            return 1
        code = _classify_exit(exc)
        print(
            f"\nERROR: Could not verify canonical engine: {type(exc).__name__}: {exc}"
        )
        return code

    # ------------------------------------------------------------------
    # Step 5: Remove .spike_engine_id file
    # ------------------------------------------------------------------
    # (Session cleanup was already run before engine deletion in step 3.
    # The engine's force=True deletion provides belt-and-suspenders for any
    # remaining sessions.)
    if _SPIKE_ENGINE_ID_FILE.exists():
        try:
            _SPIKE_ENGINE_ID_FILE.unlink()
            print(f"\nRemoved {_SPIKE_ENGINE_ID_FILE}")
        except OSError as exc:
            logger.warning("Could not remove %s: %s", _SPIKE_ENGINE_ID_FILE, exc)
            print(
                f"  WARNING: Could not remove {_SPIKE_ENGINE_ID_FILE}: {exc}\n"
                "  Remove it manually to avoid stale ID on next run."
            )
    else:
        print(f"\nINFO: {_SPIKE_ENGINE_ID_FILE} already absent — nothing to remove.")

    # ------------------------------------------------------------------
    # Done
    # ------------------------------------------------------------------
    id_file_status = "removed" if not _SPIKE_ENGINE_ID_FILE.exists() else "still present (check warnings)"
    print()
    print("=" * 68)
    print("AH-104 SPIKE CLEANUP COMPLETE")
    print(f"  Spike engine  : {'deleted' if spike_resource_name else 'not present'}")
    print(f"  Canonical eng : alive ({_CANONICAL_ENGINE_RESOURCE})")
    print(f"  ID file       : {id_file_status}")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)
    except Exception as exc:
        code = _classify_exit(exc)
        label = "infrastructure/credentials" if code == 2 else "unexpected error"
        logger.error(
            "Unhandled exception [%s] (exit %d): %s: %s",
            label,
            code,
            type(exc).__name__,
            exc,
        )
        print(
            f"\nERROR [{label}] (exit {code}): {type(exc).__name__}: {exc}\n"
            "Note: exit 2 = infra/credentials (ADC, permission denied, 5xx); "
            "exit 1 = unexpected failure."
        )
        sys.exit(code)
