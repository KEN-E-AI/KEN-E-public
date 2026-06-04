"""AH-104 deploy spike — ephemeral Agent Engine creation harness.

Validates that the KEN-E agent tree (built via agent_factory.build_hierarchy())
can be packaged as an App + AdkApp and submitted to Vertex AI Agent Engine as a
brand-new ephemeral engine.

SAFETY INVARIANTS — read before touching this file:
  1. NEVER call agent_engines.update(). Always agent_engines.create().
  2. NEVER call _resolve_existing_engine_id() or update_secret_manager().
     This script has no knowledge of the canonical engine and must not acquire it.
  3. NEVER use the canonical engine ID (5957383247464759296). The spike creates
     its own ephemeral engine with a timestamped displayName and saves the
     resource name to .spike_engine_id for subsequent cleanup.
  4. Default behaviour: the engine is deleted immediately after creation
     (--keep skips that cleanup so downstream probes can exercise it).

Usage (from repo root):
    .venv-adk2/bin/python docs/spike-adk2/spike_deploy.py \\
        --project ken-e-dev --location us-central1 [--dry-run] [--keep]

Exit codes:
    0 — success (engine created, or dry-run completed)
    1 — build or deploy failure (see stderr)
    2 — infrastructure / credentials issue (ADC missing, permission denied, etc.)

ADK version required: 2.0.0 (in .venv-adk2/)
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# sys.path: repo root must be on path so app.adk.* and shared.* resolve.
# This script is run from the repo root but __file__ is inside docs/spike-adk2/,
# so we walk up two levels.
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent          # docs/spike-adk2/
_REPO_ROOT = _HERE.parent.parent                 # repo root (contains CLAUDE.md)
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger("spike_deploy")

# ---------------------------------------------------------------------------
# Harness constants (mirror _live_harness.py)
# ---------------------------------------------------------------------------
_SPIKE_ENGINE_ID_FILE: Path = _HERE / ".spike_engine_id"
"""Written after a successful create(); read by cleanup steps."""

_REQUIREMENTS_FILE: Path = _HERE / "spike_requirements.txt"
"""Passed to agent_engines.create() as the requirements file."""

_SPIKE_DISPLAY_NAME_PREFIX: str = "ken-e-chat-agent-spike-ah104"


# ---------------------------------------------------------------------------
# Exit-code helpers (consistent with probe convention)
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
    """Return 2 for infra/credential errors, 1 for genuine build/deploy failures."""
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


# ---------------------------------------------------------------------------
# Deploy-tree assembly
# ---------------------------------------------------------------------------

def _assemble_spike_tree(temp_path: Path) -> None:
    """Copy the app.adk deploy tree into *temp_path* for packaging.

    Mirrors app/adk/deploy_packaging.assemble_deploy_tree() but:
    - Uses spike_requirements.txt instead of app/adk/requirements.txt
    - Does not process .env files (spike does not need resolved secrets for
      the packaging step; ADK pickles the agent graph, not runtime config)
    - Does not require copy_env=True logic (no secret resolution in spike)
    """
    adk_root = _REPO_ROOT / "app" / "adk"

    # agents/ — Agent Engine entry point
    agents_src = adk_root / "agents"
    if not agents_src.exists():
        raise FileNotFoundError(
            f"agents/ not found at {agents_src}. "
            "Run from the repo root with the spike venv."
        )
    shutil.copytree(agents_src, temp_path / "agents")
    logger.info("Copied agents/")

    # requirements.txt — use spike_requirements.txt
    if not _REQUIREMENTS_FILE.exists():
        raise FileNotFoundError(
            f"spike_requirements.txt not found at {_REQUIREMENTS_FILE}. "
            "Create it before running the deploy spike."
        )
    shutil.copy2(_REQUIREMENTS_FILE, temp_path / "requirements.txt")
    logger.info("Copied spike_requirements.txt -> requirements.txt")

    # shared/
    shared_src = _REPO_ROOT / "shared"
    if shared_src.exists():
        shutil.copytree(shared_src, temp_path / "shared")
        logger.info("Copied shared/")
    else:
        logger.warning("shared/ not found — some agent helpers may fail at runtime")

    # app/adk sub-packages
    app_adk_dest = temp_path / "app" / "adk"
    app_adk_dest.mkdir(parents=True)
    (temp_path / "app" / "__init__.py").touch()
    (app_adk_dest / "__init__.py").touch()

    for subpkg in ("agents", "security", "tracking", "tools", "mcp_config"):
        src = adk_root / subpkg
        if src.exists():
            shutil.copytree(
                src,
                app_adk_dest / subpkg,
                ignore=shutil.ignore_patterns("tests", "__pycache__"),
            )
            logger.info("Copied app.adk.%s/", subpkg)
        else:
            logger.warning("app/adk/%s not found", subpkg)

    # app/utils
    app_utils_src = _REPO_ROOT / "app" / "utils"
    if app_utils_src.exists():
        shutil.copytree(
            app_utils_src,
            temp_path / "app" / "utils",
            ignore=shutil.ignore_patterns("tests", "__pycache__"),
        )
        logger.info("Copied app/utils/")
    else:
        logger.warning("app/utils/ not found")


# ---------------------------------------------------------------------------
# Engine cleanup helper
# ---------------------------------------------------------------------------

def _delete_spike_engine(resource_name: str) -> bool:
    """Delete the ephemeral spike engine via the Agent Engine API.

    Returns True on success (including 404 — already gone), False on failure.
    On failure, logs a warning; the caller decides whether to remove the ID file
    (it should NOT remove .spike_engine_id on failure so manual cleanup is possible).
    """
    try:
        from vertexai import agent_engines

        logger.info("Deleting spike engine %s ...", resource_name)
        engine = agent_engines.get(resource_name)
        engine.delete(force=True)
        logger.info("Spike engine deleted.")
        return True
    except Exception as exc:
        text = f"{type(exc).__name__}: {exc}".lower()
        if "not found" in text or "404" in text:
            logger.info("Spike engine %s already gone (404) — treating as success.", resource_name)
            return True
        logger.warning(
            "Could not delete spike engine %s: %s\n"
            "  Manual cleanup: .venv-adk2/bin/python docs/spike-adk2/cleanup_spike_engine.py",
            resource_name,
            exc,
        )
        return False


# ---------------------------------------------------------------------------
# Core deploy logic
# ---------------------------------------------------------------------------

def _build_adk_app(temp_path: Path) -> object:
    """Import build_hierarchy() from the temp tree and wrap in App + AdkApp.

    Returns the AdkApp instance ready for agent_engines.create().

    Raises:
        ImportError: if the temp-tree packaging is broken.
        Any exception raised by build_hierarchy() itself.
    """
    import importlib
    import importlib.util

    # Prepend the temp tree so its agents/ package shadows any installed one.
    if str(temp_path) not in sys.path:
        sys.path.insert(0, str(temp_path))

    # Force re-import in case a previous dry-run attempt left stale modules.
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("agents.") or mod_name == "agents":
            del sys.modules[mod_name]

    from google.adk.agents.context_cache_config import ContextCacheConfig
    from google.adk.apps.app import App, EventsCompactionConfig
    from google.adk.apps.llm_event_summarizer import LlmEventSummarizer
    from google.adk.models import Gemini
    from google.adk.plugins import ReflectAndRetryToolPlugin
    from vertexai import agent_engines as _ae

    from agents.agent_factory import build_hierarchy  # type: ignore[import]

    logger.info("Calling build_hierarchy() ...")
    ken_e_agent = build_hierarchy()
    logger.info("build_hierarchy() returned: %s", type(ken_e_agent).__name__)

    compaction_summarizer = LlmEventSummarizer(llm=Gemini(model="gemini-2.5-flash"))
    compaction_config = EventsCompactionConfig(
        summarizer=compaction_summarizer,
        compaction_interval=5,
        overlap_size=1,
        token_threshold=50000,
        event_retention_size=10,
    )

    adk_app = App(
        name="ken_e_chatbot",
        root_agent=ken_e_agent,
        plugins=[ReflectAndRetryToolPlugin(max_retries=2)],
        events_compaction_config=compaction_config,
        context_cache_config=ContextCacheConfig(
            min_tokens=2048,
            ttl_seconds=600,
            cache_intervals=5,
        ),
    )
    logger.info("App constructed: %s", adk_app)

    app = _ae.AdkApp(app=adk_app, enable_tracing=True)
    logger.info("AdkApp constructed: %s", type(app).__name__)

    return app


def main() -> int:
    """Entry point. Returns exit code (0=success, 1=failure, 2=infra error)."""

    parser = argparse.ArgumentParser(
        description="AH-104 spike: create an ephemeral KEN-E Agent Engine for testing."
    )
    parser.add_argument(
        "--project",
        default="ken-e-dev",
        help="GCP project ID (default: ken-e-dev)",
    )
    parser.add_argument(
        "--location",
        default="us-central1",
        help="Vertex AI location (default: us-central1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Build App + AdkApp but skip agent_engines.create(). "
            "Exits 0 if the graph compiles without error."
        ),
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help=(
            "Keep the ephemeral engine after creation (default: delete it). "
            "Use when downstream probes need to query the engine."
        ),
    )
    args = parser.parse_args()

    project: str = args.project
    location: str = args.location
    dry_run: bool = args.dry_run
    keep: bool = args.keep

    # ------------------------------------------------------------------
    # Vertex AI routing — must be set before any genai/vertexai import
    # ------------------------------------------------------------------
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
    os.environ["GOOGLE_CLOUD_PROJECT"] = project
    os.environ["GOOGLE_CLOUD_LOCATION"] = location

    logger.info("=" * 68)
    logger.info("AH-104 deploy spike")
    logger.info("  project  : %s", project)
    logger.info("  location : %s", location)
    logger.info("  dry-run  : %s", dry_run)
    logger.info("  keep     : %s", keep)
    logger.info("=" * 68)

    # ------------------------------------------------------------------
    # Assemble deploy tree in a temp directory
    # ------------------------------------------------------------------
    resource_name: str | None = None

    with tempfile.TemporaryDirectory(prefix="spike-ah104-") as tmp:
        temp_path = Path(tmp)
        logger.info("Staging deploy tree in %s", temp_path)

        try:
            _assemble_spike_tree(temp_path)
        except (FileNotFoundError, ImportError) as exc:
            logger.error("Deploy tree assembly failed: %s", exc)
            return 1

        # Add temp_path to sys.path now so build_hierarchy imports resolve.
        if str(temp_path) not in sys.path:
            sys.path.insert(0, str(temp_path))

        # ------------------------------------------------------------------
        # Build App + AdkApp
        # ------------------------------------------------------------------
        try:
            adk_app_instance = _build_adk_app(temp_path)
        except Exception as exc:
            logger.error("Failed to build App/AdkApp: %s", exc, exc_info=True)
            return _classify_exit(exc)

        # ------------------------------------------------------------------
        # Dry-run path: report and exit without creating the engine
        # ------------------------------------------------------------------
        if dry_run:
            req_path = temp_path / "requirements.txt"
            print("")
            print("DRY RUN: would create engine with requirements=", str(req_path))
            print(
                "  extra_packages=['agents', 'shared', 'app']"
            )
            print("  AdkApp:", type(adk_app_instance).__name__)
            print("")
            logger.info("DRY RUN complete — no engine created.")
            return 0

        # ------------------------------------------------------------------
        # Live path: initialise Vertex AI and create ephemeral engine
        # ------------------------------------------------------------------
        import vertexai

        staging_bucket = f"gs://{project}-adk-staging"
        try:
            vertexai.init(
                project=project,
                location=location,
                staging_bucket=staging_bucket,
            )
            logger.info("vertexai.init() done (staging bucket: %s)", staging_bucket)
        except Exception as exc:
            logger.error("vertexai.init() failed: %s", exc, exc_info=True)
            return _classify_exit(exc)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        display_name = f"{_SPIKE_DISPLAY_NAME_PREFIX}-{timestamp}"

        logger.info("Creating ephemeral engine: %s ...", display_name)

        # SAFETY: always agent_engines.create() — never update(), never touch
        # the canonical engine (5957383247464759296).
        from vertexai import agent_engines

        try:
            # Change into temp_path so relative paths in requirements.txt
            # resolve correctly during the staging upload.
            original_cwd = os.getcwd()
            os.chdir(temp_path)
            try:
                deployed_engine = agent_engines.create(
                    agent_engine=adk_app_instance,
                    requirements="requirements.txt",
                    display_name=display_name,
                    description=(
                        "AH-104 spike — ephemeral engine, safe to delete. "
                        "Created by docs/spike-adk2/spike_deploy.py."
                    ),
                    extra_packages=["agents", "shared", "app"],
                )
            finally:
                os.chdir(original_cwd)

            resource_name = deployed_engine.resource_name
        except Exception as exc:
            logger.error("agent_engines.create() failed: %s", exc, exc_info=True)
            return _classify_exit(exc)

        # ------------------------------------------------------------------
        # Persist resource name to .spike_engine_id
        # ------------------------------------------------------------------
        _SPIKE_ENGINE_ID_FILE.write_text(resource_name + "\n")
        logger.info("Wrote resource name to %s", _SPIKE_ENGINE_ID_FILE)

        print("")
        print("=" * 68)
        print("SPIKE ENGINE CREATED")
        print(f"  resource_name : {resource_name}")
        print(f"  display_name  : {display_name}")
        print(f"  id_file       : {_SPIKE_ENGINE_ID_FILE}")
        print("=" * 68)
        print("")

        # ------------------------------------------------------------------
        # Cleanup unless --keep was passed
        # ------------------------------------------------------------------
        if not keep:
            deleted_ok = _delete_spike_engine(resource_name)
            if deleted_ok:
                # Remove the id file only after confirmed deletion so stale IDs
                # don't confuse subsequent runs.
                try:
                    _SPIKE_ENGINE_ID_FILE.unlink(missing_ok=True)
                except OSError as exc:
                    logger.warning("Could not remove %s: %s", _SPIKE_ENGINE_ID_FILE, exc)
            else:
                # Deletion failed — keep .spike_engine_id so cleanup_spike_engine.py
                # can pick it up in a subsequent manual run.
                print(
                    f"\nWARNING: Engine deletion failed; {_SPIKE_ENGINE_ID_FILE} retained.\n"
                    "  Run: .venv-adk2/bin/python docs/spike-adk2/cleanup_spike_engine.py\n"
                    "  to delete the engine manually."
                )
                return 1
        else:
            logger.info(
                "--keep specified: engine preserved at %s", resource_name
            )
            logger.info(
                "Run 'vertexai.agent_engines.get(%r).delete(force=True)' "
                "or re-run without --keep to clean up.",
                resource_name,
            )

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
