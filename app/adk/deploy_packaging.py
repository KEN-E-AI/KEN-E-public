"""Deploy-tree assembly helpers for KEN-E Agent Engine packaging.

Two helpers live here — one per deploy tree:

* ``assemble_deploy_tree()`` — chat tree (``deploy_ken_e.py``,
  ``google-adk[mcp]==2.0.0``).  Extracted in AH-23 so CI can exercise
  packaging without a real deploy.

* ``assemble_strategy_deploy_tree()`` — strategy-supervisor tree
  (``deploy_with_sys_version.py``, ``google-adk==1.34.1``).  Added in AH-106
  to make the strategy tree's packaging testable in CI independently of a
  live deploy, mirroring the pattern established for the chat tree.

Both trees share the same ``app/`` source packages (``agents``, ``security``,
``tracking``, ``tools``, ``mcp_config``, ``app/utils``).  The shared modules
are ADK-major-agnostic — audit summary below.  Only the ``requirements.txt``
payload differs: the chat tree ships ``requirements.txt`` (``==2.0.0``); the
strategy tree ships ``requirements-strategy.txt`` renamed to
``requirements.txt`` (``==1.34.1``).

Shared ``app.adk.*`` module audit (AH-106):
  agents     — agent_factory uses ``google.adk.tools.skill_toolset`` and
               ``google.adk.code_executors.agent_engine_sandbox_code_executor``
               but only via deferred (inside-function) imports, so neither
               fires at module-scope on a 1.34 venv.  Stable surface:
               ``LlmAgent``, ``LoopAgent``, ``Agent``, ``transfer_to_agent``.
  security   — ``google.adk.agents.Agent``, ``google.adk.tools.BaseTool /
               ToolContext`` — both stable across 1.34 and 2.0.
  tracking   — ``google.adk.agents.CallbackContext``, ``google.adk.tools.
               BaseTool / ToolContext``, ``google.adk.models.LlmResponse`` —
               all stable across 1.34 and 2.0.
  tools      — ``google.adk.tools.AgentTool``, ``google.adk.tools.
               FunctionTool``, ``google.adk.tools.google_search``,
               ``google.adk.agents.Agent``, ``google.adk.code_executors.
               BuiltInCodeExecutor`` — all stable across 1.34 and 2.0.
  mcp_config — no top-level ``google.adk`` imports; MCPServerManager is
               imported inside ``get_mcp_servers()`` and is guarded by a
               try/except for environments where MCP is unavailable.

CI consumers:
  ``deployment/ci/scripts/verify_deploy_tree.py``          — chat tree
  ``deployment/ci/scripts/verify_strategy_deploy_tree.py`` — strategy tree
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


def assemble_strategy_deploy_tree(temp_path: Path, *, copy_env: bool = True) -> None:
    """Copy all strategy-deploy artefacts into *temp_path*.

    Mirrors ``assemble_deploy_tree()`` for the strategy-supervisor tree
    (``deploy_with_sys_version.py``, ``google-adk==1.34.1``).  Extracts the
    inline ``shutil.copytree`` loop from ``deploy_with_sys_version.py:225-301``
    so the strategy tree's packaging can be exercised by CI without triggering
    an actual Agent Engine deploy.

    Key difference from ``assemble_deploy_tree()``:
    * The ``requirements.txt`` payload is sourced from
      ``app/adk/requirements-strategy.txt`` (``google-adk==1.34.1``), NOT
      from ``app/adk/requirements.txt`` (``google-adk[mcp]==2.0.0``).  Agent
      Engine requires a file named ``requirements.txt``; the rename is
      intentional.

    Note on ``.env`` handling: neither this helper nor ``assemble_deploy_tree``
    contains ``.env`` copy/resolution logic.  The ``copy_env`` parameter is
    accepted for API symmetry with ``assemble_deploy_tree`` and for future use,
    but callers are responsible for ``.env`` resolution via ``process_env_file``
    (in ``deploy_with_sys_version.py``) after calling this helper.  The CI
    smoke test passes ``copy_env=False`` as an explicit signal that credentials
    are not available; live deployments omit the flag (default ``True``) to
    indicate they *do* handle credentials — through the surrounding call site,
    not through this function.

    Args:
        temp_path: Destination directory (must already exist).
        copy_env: Reserved for future use.  Currently has no effect — ``.env``
            resolution is always the caller's responsibility.  Pass ``False``
            in credential-free CI contexts as a semantic signal.
    """
    adk_root = Path(__file__).parent  # app/adk/

    # ------------------------------------------------------------------ agents
    # The ``agents/`` top-level package is the strategy-supervisor entry point.
    # Resolved relative to this file (app/adk/) so the helper is CWD-agnostic
    # (unlike the inline copy in deploy_with_sys_version.py which used a bare
    # ``Path("agents")`` resolved against CWD).
    agents_src = adk_root / "agents"
    if agents_src.exists():
        shutil.copytree(agents_src, temp_path / "agents")
        logger.info("Copied agents directory")
    else:
        raise FileNotFoundError(
            f"agents/ directory not found at {agents_src}. "
            "Deploy tree cannot be assembled without the Agent Engine entry point."
        )

    # ----------------------------------------------------------- shared/
    # Contains the secrets utility and other shared code.
    shared_src = adk_root.parent.parent / "shared"
    if shared_src.exists():
        shutil.copytree(shared_src, temp_path / "shared")
        logger.info("Copied shared package")
    else:
        logger.warning("shared package not found")

    # ------------------------------------------------------- app/adk sub-packages
    # Copied so absolute imports like
    # ``from app.adk.tools.agent_tools.google_search import …`` resolve on
    # the Agent Engine backend.  The strategy agent re-exports
    # ``create_google_search_agent`` at package import; without these packages
    # it fails to unpickle with ``ModuleNotFoundError: No module named 'app.adk'``.
    #
    # Shared app.adk.* modules are ADK-major-agnostic (see module docstring).
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

    # ---------------------------------------------------------------- app/utils
    # Contains weave_observability and other utilities needed by the strategy agent.
    app_utils_src = adk_root.parent / "utils"  # app/utils/
    if app_utils_src.exists():
        shutil.copytree(
            app_utils_src,
            temp_path / "app" / "utils",
            ignore=shutil.ignore_patterns("tests", "__pycache__"),
        )
        logger.info("Copied app/utils package")
    else:
        logger.warning("app/utils not found")

    # --------------------------------------------------- requirements-strategy.txt
    # Agent Engine requires a file named ``requirements.txt`` in the deploy root.
    # The strategy tree is pinned to ``google-adk==1.34.1``; copying
    # requirements-strategy.txt under the expected name keeps it decoupled from
    # the chat tree's 2.0 manifest (AH-105 / AH-106).
    strategy_reqs = adk_root / "requirements-strategy.txt"
    if strategy_reqs.exists():
        shutil.copy2(strategy_reqs, temp_path / "requirements.txt")
        logger.info(
            "Copied requirements-strategy.txt → requirements.txt (google-adk==1.34.1)"
        )
    else:
        raise FileNotFoundError(
            f"requirements-strategy.txt not found at {strategy_reqs}. "
            "Strategy deploy tree cannot be assembled without its pinned manifest."
        )
