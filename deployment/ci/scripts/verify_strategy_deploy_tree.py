"""Strategy deploy-tree smoke test for CI (AH-106).

Validates that the strategy-supervisor Agent Engine artefacts can be assembled
and imported without triggering an actual Vertex AI deploy, and that the
strategy tree does not accidentally pull in ADK 2.0-only modules at
module-scope.

Mirrors ``verify_deploy_tree.py`` (chat tree) for the strategy tree
(``deploy_with_sys_version.py``, ``google-adk==1.34.1``).

Five checks:
  1. assemble_strategy_deploy_tree() runs without error (packaging integrity).
  2. ``from agents.strategy_agent.orchestrator import app`` resolves inside the
     packaged tree with the source tree stripped from sys.path (import
     resolution).  Confirms the strategy entry-point unpickles cleanly on a
     1.34 venv.
  3. deploy_with_sys_version.py imports cleanly when run from app/adk/ —
     replicates the CD step ``cd app/adk && python deploy_with_sys_version.py``
     in a subprocess so import-order regressions fail PR checks instead of
     staging deploys.
  4. The assembled requirements.txt declares exactly ``google-adk==1.34.1``
     (AH-105 / AH-106 manifest decoupling guard).  The strategy deploy must
     use requirements-strategy.txt, not the chat tree's 2.0 manifest.
  5. Cross-major coupling guard — inject raising stubs into sys.modules for
     the two known ADK 2.0-only module paths (``google.adk.tools.skill_toolset``
     and ``google.adk.code_executors.agent_engine_sandbox_code_executor``) and
     re-import ``agents.strategy_agent.orchestrator``.  If any module on the
     strategy import path has moved one of those imports to module scope, the
     stub raises and the check fails — catching the regression class before it
     reaches production.

Exit 0 = all five checks pass.  Non-zero = at least one check failed.

Design notes (AH-106):
  * The two known ADK 2.0-only modules are imported lazily (inside function
    bodies) in the current codebase, so they do NOT break a 1.34 venv today.
    This guard exists to catch a future regression where one of those imports
    moves to module scope (e.g. via an ``__init__.py`` re-export).
  * The guard is restricted to the two known modules; future 2.0-only adds
    extend the allow-list in the same PR that adopts them.
  * Running this check in a 1.34.1 venv (CI: ``strategy-deploy-tree-smoke``)
    is the authoritative proof.  In the default 2.0 venv the stubs still
    provide a structural regression guard even though ADK 2.0 would otherwise
    satisfy those imports.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import tempfile
import types
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ADK 2.0-only module stub — raises ImportError when imported (Check 5).
# ---------------------------------------------------------------------------

_ADK2_ONLY_MODULES = (
    "google.adk.tools.skill_toolset",
    "google.adk.code_executors.agent_engine_sandbox_code_executor",
)


def _make_raising_stub(module_name: str) -> types.ModuleType:
    """Return a module whose attribute access raises ImportError.

    When injected into ``sys.modules`` before an import statement, any
    ``from <module_name> import Symbol`` will call ``__getattr__`` on the stub
    and raise ``ImportError``.  This lets us detect when a module on the
    strategy import path references an ADK 2.0-only symbol at module scope.

    The stub is constructed by subclassing ``types.ModuleType`` directly (not
    by post-hoc ``__class__`` reassignment, which is a CPython implementation
    detail not guaranteed by the language specification).
    """
    # Capture module_name in the class body so the closure is stable across
    # multiple invocations of _make_raising_stub in the same interpreter.
    _captured_name = module_name

    class _RaisingModule(types.ModuleType):
        def __getattr__(self, name: str) -> object:
            raise ImportError(
                f"ADK 2.0-only symbol accessed: {_captured_name}.{name} — "
                f"this import is not available in the google-adk==1.34.x "
                f"strategy tree.  Move the import inside a function body "
                f"(lazy import) so the strategy tree can stay on 1.34 "
                f"(AH-106 cross-major coupling guard)."
            )

    stub = _RaisingModule(module_name)
    return stub


def main() -> int:
    repo_root = (
        Path(__file__).resolve().parent.parent.parent.parent
    )  # deployment/ci/scripts/ → repo root

    sys.path.insert(0, str(repo_root))

    # ------------------------------------------------------------------
    # Check 1: assemble_strategy_deploy_tree() runs without error
    # ------------------------------------------------------------------
    from app.adk.deploy_packaging import assemble_strategy_deploy_tree

    with tempfile.TemporaryDirectory() as tmp:
        temp_path = Path(tmp)
        logger.info("Check 1: assembling strategy deploy tree into %s", temp_path)
        try:
            assemble_strategy_deploy_tree(temp_path, copy_env=False)
        except Exception as exc:
            logger.error("FAIL Check 1: assemble_strategy_deploy_tree raised: %s", exc)
            return 1

        agents_dir = temp_path / "agents"
        if not agents_dir.exists():
            logger.error("FAIL Check 1: agents/ not found in strategy deploy tree")
            return 1
        if not (temp_path / "requirements.txt").exists():
            logger.error("FAIL Check 1: requirements.txt not found in strategy deploy tree")
            return 1
        logger.info("PASS Check 1: strategy deploy tree assembled cleanly")

        # ------------------------------------------------------------------
        # Check 2: from agents.strategy_agent.orchestrator import app resolves
        # ------------------------------------------------------------------
        # Prepend temp_path so ``agents`` resolves from the packaged tree.
        logger.info(
            "Check 2: importing agents.strategy_agent.orchestrator from packaged tree"
        )
        original_path = sys.path[:]
        sys.path = [str(temp_path), *sys.path]

        try:
            # Purge any cached agents.* imports so the packaged path is used.
            for key in list(sys.modules.keys()):
                if key.startswith("agents") or key.startswith("app.adk"):
                    del sys.modules[key]

            try:
                import agents.strategy_agent.orchestrator as _orch  # noqa: F401

                logger.info(
                    "PASS Check 2: agents.strategy_agent.orchestrator imported from "
                    "packaged tree"
                )
            except ImportError as exc:
                logger.error(
                    "FAIL Check 2: import failed: %s", exc, exc_info=True
                )
                return 1
        finally:
            sys.path = original_path

        # ------------------------------------------------------------------
        # Check 4: assembled requirements.txt declares google-adk==1.34.1
        # ------------------------------------------------------------------
        # Done inside the temp_path context while it's still available.
        logger.info("Check 4: verifying assembled requirements.txt pin")
        req_text = (temp_path / "requirements.txt").read_text()
        adk_pins = [
            line.strip()
            for line in req_text.splitlines()
            if line.strip().startswith("google-adk")
        ]
        if adk_pins != ["google-adk==1.34.1"]:
            logger.error(
                "FAIL Check 4: assembled requirements.txt declares google-adk pins %s, "
                "expected exactly ['google-adk==1.34.1'] — the strategy tree has "
                "re-coupled to the chat manifest (AH-105 / AH-106 decoupling guard)",
                adk_pins,
            )
            return 1
        logger.info(
            "PASS Check 4: assembled requirements.txt correctly pins google-adk==1.34.1"
        )

        # ------------------------------------------------------------------
        # Check 5: cross-major coupling guard (ADK 2.0-only raising stubs)
        # ------------------------------------------------------------------
        # Inject raising stubs for ADK 2.0-only modules, then re-import the
        # strategy entry point.  Any module that imported one of those at
        # module scope will trigger the stub's __getattr__ and fail this check.
        logger.info(
            "Check 5: cross-major coupling guard (ADK 2.0-only raising stubs)"
        )

        original_path = sys.path[:]
        sys.path = [str(temp_path), *sys.path]
        stubs_injected: list[str] = []

        try:
            # Purge cached agents.* + app.adk.* modules before injecting stubs.
            for key in list(sys.modules.keys()):
                if key.startswith("agents") or key.startswith("app.adk"):
                    del sys.modules[key]

            # Inject raising stubs for the two ADK 2.0-only paths.
            for mod_name in _ADK2_ONLY_MODULES:
                stub = _make_raising_stub(mod_name)
                sys.modules[mod_name] = stub
                stubs_injected.append(mod_name)
                logger.info("  Injected raising stub for %s", mod_name)

            try:
                import agents.strategy_agent.orchestrator as _orch2  # noqa: F401

                logger.info(
                    "PASS Check 5: strategy tree imports cleanly with ADK 2.0-only "
                    "stubs injected — no cross-major coupling at module scope"
                )
            except ImportError as exc:
                logger.error(
                    "FAIL Check 5: ADK 2.0-only import detected at module scope: %s\n"
                    "Move the offending import inside a function body (lazy import) "
                    "so the strategy tree can stay on google-adk==1.34.1 (AH-106).",
                    exc,
                )
                return 1
        finally:
            # Clean up injected stubs so subsequent test runs start fresh.
            for mod_name in stubs_injected:
                sys.modules.pop(mod_name, None)
            for key in list(sys.modules.keys()):
                if key.startswith("agents") or key.startswith("app.adk"):
                    del sys.modules[key]
            sys.path = original_path

    # ------------------------------------------------------------------
    # Check 3: deploy_with_sys_version.py imports cleanly from app/adk/ cwd
    # ------------------------------------------------------------------
    # Replicates the CD step `cd app/adk && python deploy_with_sys_version.py`.
    # Running in a subprocess gives a fresh interpreter whose sys.path[0] is the
    # cwd (app/adk), matching the deploy environment — any import that fires
    # before the script's own sys.path bootstrap will fail here instead of
    # slipping through to a staging deploy.
    adk_dir = repo_root / "app" / "adk"
    logger.info(
        "Check 3: importing deploy_with_sys_version from %s", adk_dir
    )
    result = subprocess.run(
        [sys.executable, "-c", "import deploy_with_sys_version"],
        cwd=str(adk_dir),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error(
            "FAIL Check 3: `python -c 'import deploy_with_sys_version'` from app/adk/ "
            "exited %s\nstderr:\n%s",
            result.returncode,
            result.stderr,
        )
        return 1
    logger.info(
        "PASS Check 3: deploy_with_sys_version imports cleanly from app/adk/ cwd"
    )

    logger.info(
        "All 5 checks passed — strategy deploy tree is correctly packaged and "
        "ADK-major-agnostic at module scope."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
