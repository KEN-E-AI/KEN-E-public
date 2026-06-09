"""Deploy-tree smoke test for CI (AH-23).

Validates that the Agent Engine deployment artefacts can be assembled and
imported without triggering an actual Vertex AI deploy.  Catches the class
of regression that shipped in PR #382: a ModuleNotFoundError that only
manifested at Agent Engine runtime because CI never exercised the packaged
import path.

Six checks:
  1. assemble_deploy_tree() runs without error (packaging integrity).
  2. from agents.agent_factory import build_hierarchy resolves inside the
     temp tree with the source tree stripped from sys.path (import resolution).
  3. Every dispatch function produced by build_hierarchy() survives a
     cloudpickle round-trip and typing.get_type_hints() + FunctionTool
     ._get_declaration() succeed on the restored object (AH-17 regression
     guard: `from __future__ import annotations` + cloudpickle breaks ADK
     FunctionTool declaration generation).
  4. deploy_ken_e.py imports cleanly when run from app/adk/ — replicates the
     CD step's `cd app/adk && python deploy_ken_e.py` invocation in a
     subprocess so import-order regressions (e.g. an `app.adk.*` import that
     fires before the script's `sys.path.insert` for repo root) fail PR
     checks instead of staging deploys.
  5. The chat and strategy deploy manifests stay decoupled on their pinned
     ADK majors (chat → google-adk[mcp]==2.0.0, strategy →
     google-adk==1.34.1) and the strategy deploy still consumes
     requirements-strategy.txt (AH-105 / AH-106 decoupling guard).
  6. The chat manifest's google-cloud-aiplatform pin matches the version
     app/adk/uv.lock resolves AND carries no [adk] extra (AH-121 guard). Two traps,
     both surfaced as opaque 400s from the staging deploy:
       - Pin skew: deploy_ken_e cloudpickles the agent with the LOCKED aiplatform's
         AdkApp wrapper (vertexai.agent_engines.templates.adk); an unpinned/skewed
         manifest installs a newer aiplatform in the container where that module has
         moved → the engine fails to unpickle at boot → "400 ...failed to be updated".
       - [adk] extra: aiplatform's [adk] extra depends on google-adk<2.0.0, which
         conflicts with the chat tree's google-adk[mcp]==2.0.0 → the backend container
         build fails with pip ResolutionImpossible → "400 Build failed". The manifest
         must use [agent_engines] only (matching pyproject.toml).
     This static check would have caught the staging-deploy outage that went red
     across multiple main commits.

Exit 0 = all six checks pass.  Non-zero = at least one check failed.
"""

# This script IS safe to use `from __future__ import annotations` — it is never
# cloudpickled.  The dispatch.py prohibition (checked by TestDispatchCloudpickleRoundTrip)
# applies only to modules whose closures are serialized into the Agent Engine artifact.
from __future__ import annotations

import inspect
import logging
import subprocess
import sys
import tempfile
import typing
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Minimal Firestore stand-in — no live GCP credentials required
# ---------------------------------------------------------------------------


class _FakeFirestoreDb:
    def __init__(self, docs: dict) -> None:
        self._docs = docs

    def collection(self, col: str) -> _FakeCollection:
        return _FakeCollection(self._docs, (col,))


class _FakeCollection:
    def __init__(self, docs: dict, path: tuple) -> None:
        self._docs = docs
        self._path = path

    def document(self, doc_id: str) -> _FakeDocument:
        return _FakeDocument(self._docs, (*self._path, doc_id))

    def list_documents(self) -> list:
        prefix = self._path
        return [
            _FakeDocRef(p)
            for p, _ in self._docs.items()
            if p[: len(prefix)] == prefix and len(p) == len(prefix) + 1
        ]


class _FakeDocument:
    def __init__(self, docs: dict, path: tuple) -> None:
        self._docs = docs
        self._path = path

    def get(self) -> _FakeSnapshot:
        return _FakeSnapshot(self._docs.get(self._path))

    def collection(self, col: str) -> _FakeCollection:
        return _FakeCollection(self._docs, (*self._path, col))


class _FakeDocRef:
    def __init__(self, path: tuple) -> None:
        self.id = path[-1]


class _FakeSnapshot:
    def __init__(self, data: dict | None) -> None:
        self._data = data
        self.exists = data is not None

    def to_dict(self) -> dict:
        return self._data or {}


# Minimal docs: 1 root config + 1 specialist (no MCP servers — avoids auth).
_FAKE_DOCS: dict = {
    ("agent_configs", "ken_e_chatbot"): {
        "instruction": "You are KEN-E root.",
        "model": "gemini-2.0-flash",
        "description": "Root orchestration agent",
    },
    ("agent_configs", "sample_specialist"): {
        "instruction": "You are a sample specialist.",
        "model": "gemini-2.0-flash",
        "description": "Sample specialist for smoke testing",
    },
}


def _locked_aiplatform_version(uv_lock_path: Path) -> str | None:
    """Return the google-cloud-aiplatform version resolved in a uv.lock, or None.

    Scans for the ``[[package]]`` block whose ``name = "google-cloud-aiplatform"``
    and returns its ``version``. The inline-table requires entries
    (``{ name = "google-cloud-aiplatform", extra = [...] }``) are not standalone
    ``name = ...`` lines, so they are correctly ignored.
    """
    in_block = False
    for line in uv_lock_path.read_text().splitlines():
        stripped = line.strip()
        if stripped == "[[package]]":
            in_block = False
        elif stripped == 'name = "google-cloud-aiplatform"':
            in_block = True
        elif in_block and stripped.startswith("version = "):
            return stripped.split('"')[1]
    return None


def _pinned_aiplatform_version(requirements_path: Path) -> str | None:
    """Return the ``==``-pinned google-cloud-aiplatform version, or None.

    Returns None when the entry is absent or not pinned with ``==`` — the AH-121
    failure mode, where an unpinned entry lets the container resolve a newer
    aiplatform than the one the agent was cloudpickled with. Optional extras such
    as ``[adk,agent_engines]`` are stripped before matching the base name.
    """
    for line in requirements_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name = stripped.split("==")[0].split("[")[0].strip()
        if name == "google-cloud-aiplatform":
            _, sep, version = stripped.partition("==")
            return version.strip() if sep else None
    return None


def _aiplatform_extras(requirements_path: Path) -> set[str] | None:
    """Return the extras declared on the google-cloud-aiplatform requirement, or None.

    e.g. ``google-cloud-aiplatform[agent_engines]==1.154.0`` -> ``{"agent_engines"}``.
    Returns None when the entry is absent. The chat tree must NOT carry the ``adk``
    extra: aiplatform's ``[adk]`` extra depends on ``google-adk<2.0.0``, which conflicts
    with the chat tree's ``google-adk[mcp]==2.0.0`` (AH-121 backend-build
    ResolutionImpossible). pyproject.toml uses ``[agent-engines]`` only; the manifest
    must match.
    """
    for line in requirements_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        base = stripped.split("==")[0].strip()
        if base.split("[")[0].strip() == "google-cloud-aiplatform":
            if "[" in base and "]" in base:
                inner = base[base.index("[") + 1 : base.index("]")]
                return {e.strip() for e in inner.split(",") if e.strip()}
            return set()
    return None


def main() -> int:
    repo_root = (
        Path(__file__).resolve().parent.parent.parent.parent
    )  # deployment/ci/scripts/ → repo root

    # ------------------------------------------------------------------
    # Check 1: assemble_deploy_tree() runs without error
    # ------------------------------------------------------------------
    sys.path.insert(0, str(repo_root))
    from app.adk.deploy_packaging import assemble_deploy_tree

    with tempfile.TemporaryDirectory() as tmp:
        temp_path = Path(tmp)
        logger.info("Check 1: assembling deploy tree into %s", temp_path)
        assemble_deploy_tree(temp_path, copy_env=False)

        agents_dir = temp_path / "agents"
        if not agents_dir.exists():
            logger.error("FAIL Check 1: agents/ not found in deploy tree")
            return 1
        logger.info("PASS Check 1: agents/ present in deploy tree")

        # ------------------------------------------------------------------
        # Check 2: from agents.agent_factory import build_hierarchy resolves
        # ------------------------------------------------------------------
        # Prepend temp_path so ``agents`` resolves from the packaged tree.
        # There is no top-level ``agents/`` in the source tree, so the
        # packaged copy is the only candidate — no stripping of the venv
        # or other sys.path entries is necessary.
        logger.info("Check 2: importing build_hierarchy from packaged tree")

        original_path = sys.path[:]
        sys.path = [str(temp_path), *sys.path]

        try:
            # Purge any cached agents.* imports so the new path entry is used.
            for key in list(sys.modules.keys()):
                if key.startswith("agents"):
                    del sys.modules[key]

            try:
                from agents.agent_factory import build_hierarchy

                logger.info("PASS Check 2: build_hierarchy imported from packaged tree")
            except ImportError as exc:
                logger.error("FAIL Check 2: import failed: %s", exc)
                return 1

            # ------------------------------------------------------------------
            # Check 3: cloudpickle round-trip on dispatch functions
            # ------------------------------------------------------------------
            logger.info("Check 3: build_hierarchy + cloudpickle round-trip")

            from unittest.mock import MagicMock, patch

            fake_db = _FakeFirestoreDb(_FAKE_DOCS)

            _mock_weave_before = MagicMock()
            _mock_weave_after = MagicMock()
            _mock_before_tool = MagicMock()
            _mock_after_tool = MagicMock()
            _mock_registry = MagicMock()
            _mock_registry.list_tools.return_value = []

            try:
                with (
                    patch(
                        "app.adk.agents.agent_factory.builder.weave_before_agent_callback",
                        _mock_weave_before,
                    ),
                    patch(
                        "app.adk.agents.agent_factory.builder.weave_after_agent_callback",
                        _mock_weave_after,
                    ),
                    patch(
                        "app.adk.agents.agent_factory.builder.adk_before_tool_callback",
                        _mock_before_tool,
                    ),
                    patch(
                        "app.adk.agents.agent_factory.builder.adk_after_tool_callback",
                        _mock_after_tool,
                    ),
                    patch(
                        "app.adk.tools.registry.tool_registry.get_default_registry",
                        return_value=_mock_registry,
                    ),
                ):
                    root_agent = build_hierarchy(db=fake_db)
            except Exception as exc:
                logger.error(
                    "FAIL Check 3: build_hierarchy raised: %s", exc, exc_info=True
                )
                return 1

            import cloudpickle
            from google.adk.tools.function_tool import FunctionTool

            for tool in root_agent.tools:
                # Agent-delegation tools (AgentTool / _TaskAgentTool — e.g. the
                # AH-161 request_task dispatch shims seeded onto the deploy-time
                # root for each global ken_e_sub_agent specialist) are NOT
                # FunctionTools: they have no `.func`, and the get_type_hints /
                # FunctionTool-declaration validation below is function-tool
                # specific (it guards against cloudpickle silently dropping a
                # *function's* parameter schema). Validate only that they survive
                # a cloudpickle round-trip — the deploy invariant — and skip the
                # function-schema checks that don't apply to them.
                if not isinstance(tool, FunctionTool):
                    try:
                        cloudpickle.loads(cloudpickle.dumps(tool))
                        logger.info(
                            "  PASS cloudpickle round-trip (non-function tool): %s",
                            getattr(tool, "name", type(tool).__name__),
                        )
                    except Exception as exc:
                        logger.error(
                            "FAIL Check 3 (non-function tool) for %s: %s",
                            getattr(tool, "name", tool),
                            exc,
                            exc_info=True,
                        )
                        return 1
                    continue

                fn = getattr(tool, "func", tool) if hasattr(tool, "func") else tool
                try:
                    blob = cloudpickle.dumps(fn)
                    restored = cloudpickle.loads(blob)
                    hints = typing.get_type_hints(restored)
                    assert hints, f"get_type_hints returned empty dict for {fn}"
                    ft = FunctionTool(restored)
                    decl = ft._get_declaration()
                    assert decl is not None, (
                        f"_get_declaration() returned None for {fn}"
                    )
                    # ADK 2.0 emits the parameter schema in one of two fields:
                    # the legacy `parameters` (genai Schema), or, when a signature
                    # triggers the JSON_SCHEMA_FOR_FUNC_DECL path (e.g. a
                    # `list[dict[str, Any]]` arg), `parameters_json_schema` — in
                    # which case `parameters` is legitimately None. Accept either.
                    has_params = (
                        decl.parameters is not None
                        or getattr(decl, "parameters_json_schema", None) is not None
                    )
                    # A tool whose only arguments are ADK-injected (tool_context /
                    # input_stream) legitimately produces a declaration with no
                    # parameters — Gemini supports zero-argument function calls. Use
                    # ADK's own `_ignore_params` to find the LLM-facing arguments;
                    # only an *empty* declaration for a tool that DOES declare such
                    # arguments signals a cloudpickle round-trip that silently lost
                    # the schema (the real regression this check guards).
                    ignored = set(getattr(ft, "_ignore_params", ()))
                    declarable = [
                        name
                        for name in inspect.signature(restored).parameters
                        if name not in ignored
                    ]
                    if declarable:
                        assert has_params, (
                            f"declaration has neither parameters nor "
                            f"parameters_json_schema for {fn} "
                            f"(declarable params: {declarable})"
                        )
                    logger.info(
                        "  PASS cloudpickle round-trip: %s", getattr(fn, "__name__", fn)
                    )
                except Exception as exc:
                    logger.error("FAIL Check 3 for %s: %s", fn, exc, exc_info=True)
                    return 1

            logger.info(
                "PASS Check 3: all dispatch functions survive cloudpickle round-trip"
            )
        finally:
            sys.path = original_path

    # ------------------------------------------------------------------
    # Check 4: deploy_ken_e.py imports cleanly from app/adk/ cwd
    # ------------------------------------------------------------------
    # Replicates the CD step `cd app/adk && python deploy_ken_e.py`. Running
    # in a subprocess gives a fresh interpreter whose sys.path[0] is the cwd
    # (app/adk), matching the deploy environment — so any `from app.adk.*`
    # import that runs before the script's own sys.path bootstrap will fail
    # here instead of slipping through to a staging deploy.
    adk_dir = repo_root / "app" / "adk"
    logger.info("Check 4: importing deploy_ken_e from %s", adk_dir)
    result = subprocess.run(
        [sys.executable, "-c", "import deploy_ken_e"],
        cwd=str(adk_dir),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error(
            "FAIL Check 4: `python -c 'import deploy_ken_e'` from app/adk/ "
            "exited %s\nstderr:\n%s",
            result.returncode,
            result.stderr,
        )
        return 1
    logger.info("PASS Check 4: deploy_ken_e imports cleanly from app/adk/ cwd")

    # ------------------------------------------------------------------
    # Check 5: chat/strategy deploy manifests stay decoupled on their pins
    # ------------------------------------------------------------------
    # The two deploy trees share app/ source but deploy on different ADK majors:
    # the chat tree (app/adk/requirements.txt) on google-adk[mcp]==2.0.0, the
    # strategy tree (app/adk/requirements-strategy.txt) on google-adk==1.34.1.
    # This static pin check catches accidental re-coupling — e.g. dropping the
    # [mcp] extra the GA specialist needs, or re-pointing the strategy deploy at
    # the 2.0 manifest (AH-105 / AH-106).
    adk_root = repo_root / "app" / "adk"
    manifest_expectations = {
        adk_root / "requirements.txt": "google-adk[mcp]==2.0.0",
        adk_root / "requirements-strategy.txt": "google-adk==1.34.1",
    }
    for manifest_path, expected_pin in manifest_expectations.items():
        pins = [
            line.strip()
            for line in manifest_path.read_text().splitlines()
            if line.strip().startswith("google-adk")
        ]
        if pins != [expected_pin]:
            logger.error(
                "FAIL Check 5: %s declares google-adk pins %s, expected exactly ['%s']",
                manifest_path.name,
                pins,
                expected_pin,
            )
            return 1
    # The strategy deploy script must consume the strategy manifest, not the chat one.
    strategy_deploy_src = (adk_root / "deploy_with_sys_version.py").read_text()
    if "requirements-strategy.txt" not in strategy_deploy_src:
        logger.error(
            "FAIL Check 5: deploy_with_sys_version.py no longer references "
            "requirements-strategy.txt — the strategy tree may have re-coupled to "
            "the chat manifest (google-adk 2.0)."
        )
        return 1
    logger.info(
        "PASS Check 5: chat manifest pinned to google-adk[mcp]==2.0.0, "
        "strategy manifest pinned to google-adk==1.34.1"
    )

    # ------------------------------------------------------------------
    # Check 6: chat manifest aiplatform pin matches uv.lock (AH-121 guard)
    # ------------------------------------------------------------------
    # deploy_ken_e cloudpickles the agent with the aiplatform that uv.lock
    # resolves; the container installs from requirements.txt. If the manifest
    # pin is absent/unpinned/skewed, the container can resolve a newer aiplatform
    # where vertexai.agent_engines.templates.adk has moved, so the engine fails to
    # unpickle at boot → opaque "400 ...failed to be updated". Keep them identical.
    uv_lock = adk_root / "uv.lock"
    requirements_txt = adk_root / "requirements.txt"
    locked = _locked_aiplatform_version(uv_lock)
    pinned = _pinned_aiplatform_version(requirements_txt)
    if locked is None:
        logger.error(
            "FAIL Check 6: could not find a google-cloud-aiplatform package in %s",
            uv_lock,
        )
        return 1
    if pinned is None:
        logger.error(
            "FAIL Check 6: %s does not pin google-cloud-aiplatform with '=='. "
            "Unpinned → the container can install a newer aiplatform than the "
            "cloudpickle SDK (the AH-121 staging-deploy outage). Pin it to ==%s "
            "to match uv.lock.",
            requirements_txt.name,
            locked,
        )
        return 1
    if pinned != locked:
        logger.error(
            "FAIL Check 6: aiplatform pin skew — %s pins ==%s but uv.lock resolves "
            "%s. They MUST match (cloudpickle/unpickle version skew → opaque "
            "'400 ...failed to be updated' at engine boot).",
            requirements_txt.name,
            pinned,
            locked,
        )
        return 1
    extras = _aiplatform_extras(requirements_txt) or set()
    if "adk" in extras:
        logger.error(
            "FAIL Check 6: %s declares the google-cloud-aiplatform [adk] extra. That "
            "extra depends on google-adk<2.0.0 and conflicts with the chat tree's "
            "google-adk[mcp]==2.0.0 → the backend container build fails with pip "
            "ResolutionImpossible (AH-121 '400 Build failed'). Use [agent_engines] only "
            "(match pyproject.toml); google-adk is pinned directly and the templates.adk "
            "module ships in the wheel regardless of extras.",
            requirements_txt.name,
        )
        return 1
    logger.info(
        "PASS Check 6: google-cloud-aiplatform pinned to ==%s (extras=%s), matching uv.lock",
        pinned,
        sorted(extras) or "none",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
