"""Deploy-tree assembly helper for KEN-E Agent Engine packaging.

Extracted from ``deploy_ken_e.py`` so the temp-tree construction can be
exercised by CI smoke tests without triggering an actual Agent Engine deploy.

The canonical consumer is ``deploy_ken_e.py``; the CI smoke script at
``deployment/ci/scripts/verify_deploy_tree.py`` is the test consumer.
"""

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def assemble_deploy_tree(temp_path: Path, *, copy_env: bool = True) -> None:
    """Copy all deploy-time artefacts into *temp_path*.

    Replicates the copy-tree logic that previously lived inline in
    ``deploy_ken_e.py:171-238``.  Behaviour is identical: the same source
    directories are discovered relative to this file's location so the helper
    works whether it is called from the repo root or from inside the temp dir.

    Args:
        temp_path: Destination directory (must already exist).
        copy_env: When *False*, the ``.env.*`` processing is skipped.  The CI
            smoke step passes ``copy_env=False`` because it has no credentials
            and only needs to validate import resolution, not runtime config.
    """
    # ------------------------------------------------------------------ agents
    # The ``agents/`` top-level package is the Agent Engine entry point.
    # Copied to ``temp_path/agents/`` so ``from agents.agent_factory import …``
    # resolves in the deployed environment.
    # Resolved relative to this file (app/adk/) so the function is CWD-agnostic.
    adk_root_early = Path(__file__).parent  # app/adk/
    agents_src = adk_root_early / "agents"
    if agents_src.exists():
        shutil.copytree(agents_src, temp_path / "agents")
        logger.info("Copied agents directory")
    else:
        raise FileNotFoundError(
            f"agents/ directory not found at {agents_src}. "
            "Deploy tree cannot be assembled without the Agent Engine entry point."
        )

    # -------------------------------------------------------- requirements.txt
    req_src = adk_root_early / "requirements.txt"  # app/adk/requirements.txt
    if req_src.exists():
        shutil.copy2(req_src, temp_path / "requirements.txt")
        logger.info("Copied requirements.txt")

    # --------------------------------------------------------------- shared/
    # Contains the secrets utility and other shared code.
    shared_src = Path(__file__).parent.parent.parent / "shared"
    if shared_src.exists():
        shutil.copytree(shared_src, temp_path / "shared")
        logger.info("Copied shared package")
    else:
        logger.warning("shared package not found")

    # --------------------------------------------------- app/adk sub-packages
    # Copied so that absolute imports of the form
    # ``from app.adk.agents.agent_factory.builder import …`` resolve at deploy
    # time.  Without this, ``build_hierarchy()`` raises
    # ``ModuleNotFoundError: No module named 'app.adk.agents'``.
    #
    # Sub-package list:
    #   agents     — factory, dispatch generator, root agent, specialists
    #   security   — auth hooks consumed by callbacks
    #   tracking   — Weave observability callbacks
    #   tools      — tool registry + function-tool definitions
    #   mcp_config — MCPServerManager YAML fallback path
    adk_root = adk_root_early  # already set above; alias kept for readability below
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
            logger.info(f"Copied app.adk.{subpkg} package")
        else:
            logger.warning(f"app/adk/{subpkg} not found")

    # --------------------------------------------------------------- app/utils
    # Contains weave_observability and other utilities needed by ken_e_agent.
    app_utils_src = adk_root.parent / "utils"  # app/utils/
    if app_utils_src.exists():
        shutil.copytree(
            app_utils_src,
            temp_path / "app" / "utils",
            ignore=shutil.ignore_patterns("tests", "__pycache__"),
        )
        logger.info("Copied app.utils package")
    else:
        logger.warning("app/utils not found")
