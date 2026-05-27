"""Deploy-tree smoke test for CI (AH-23).

Validates that the Agent Engine deployment artefacts can be assembled and
imported without triggering an actual Vertex AI deploy.  Catches the class
of regression that shipped in PR #382: a ModuleNotFoundError that only
manifested at Agent Engine runtime because CI never exercised the packaged
import path.

Four checks:
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

Exit 0 = all four checks pass.  Non-zero = at least one check failed.
"""

# This script IS safe to use `from __future__ import annotations` — it is never
# cloudpickled.  The dispatch.py prohibition (checked by TestDispatchCloudpickleRoundTrip)
# applies only to modules whose closures are serialized into the Agent Engine artifact.
from __future__ import annotations

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
                    assert decl.parameters is not None, (
                        f"declaration.parameters is None for {fn}"
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
