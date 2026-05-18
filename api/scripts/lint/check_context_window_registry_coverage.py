"""CI lint: every model= kwarg in app/adk/agents/**/*.py must be in
MODEL_CONTEXT_WINDOW_REGISTRY (api/src/kene_api/chat/context_windows.py).

Usage (from repo root):
    uv run python api/scripts/lint/check_context_window_registry_coverage.py

The scan root defaults to app/adk/agents/; pass --agents-root <dir> to scan a
different tree (used by the unit test to scan a temp fixture dir rather than
mutating the real source tree).

Exits 0 when all deployed model literals are registered; exits 1 with a
human-readable list of violations otherwise.

Why AST-based (not regex):
  Regex would match model= in docstrings, comments, and raw strings, and
  would miss formatting variations. AST evaluates structure — only real
  keyword arguments of type str literal are collected.

What is excluded:
  - Files matching test_*.py, tests/ dirs, temp_eval* dirs, utils/test_*.py
  - Call nodes where the model= kwarg value is not an ast.Constant(str)
    (e.g. model=config.model, model=f"gpt-{v}" — dynamic values cannot be
    verified statically; they are a known limitation documented in the plan)
"""

import argparse
import ast
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — resolve repo root from this script's location
# ---------------------------------------------------------------------------

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]  # api/scripts/lint/ → repo root
AGENTS_ROOT = REPO_ROOT / "app" / "adk" / "agents"
API_SRC = REPO_ROOT / "api" / "src"

# ---------------------------------------------------------------------------
# Exclusion rules (path-prefix based)
# ---------------------------------------------------------------------------

EXCLUDED_PATH_PARTS = frozenset(
    {
        "tests",
        "temp_eval",
    }
)

EXCLUDED_FILENAME_PREFIXES = ("test_",)


def _is_excluded(path: Path) -> bool:
    """Return True if the path should be skipped by the lint."""
    for part in path.parts:
        if part in EXCLUDED_PATH_PARTS or part.startswith("temp_eval"):
            return True
    if path.name.startswith(EXCLUDED_FILENAME_PREFIXES):
        return True
    return False


# ---------------------------------------------------------------------------
# AST collection
# ---------------------------------------------------------------------------


def _collect_model_literals(path: Path) -> list[tuple[Path, int, str]]:
    """Return (file, lineno, model_id) for each model="..." kwarg in path."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return []

    results: list[tuple[Path, int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg != "model":
                continue
            # Only check string literal values — skip dynamic expressions
            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                results.append((path, kw.value.lineno, kw.value.value))
    return results


# ---------------------------------------------------------------------------
# Registry import
# ---------------------------------------------------------------------------


def _load_registry() -> set[str]:
    """Import MODEL_CONTEXT_WINDOW_REGISTRY and return its keys."""
    sys.path.insert(0, str(API_SRC))
    try:
        from kene_api.chat.context_windows import MODEL_CONTEXT_WINDOW_REGISTRY

        return set(MODEL_CONTEXT_WINDOW_REGISTRY.keys())
    finally:
        sys.path.pop(0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agents-root",
        type=Path,
        default=AGENTS_ROOT,
        help="Directory tree to scan for model= kwargs (default: app/adk/agents).",
    )
    args = parser.parse_args(argv)
    agents_root: Path = args.agents_root.resolve()

    if not agents_root.is_dir():
        print(
            f"ERROR: agents directory not found at {agents_root}. "
            "Run this script from the repo root.",
            file=sys.stderr,
        )
        return 1

    registry_keys = _load_registry()

    violations: list[tuple[Path, int, str]] = []
    files_scanned = 0

    for py_file in sorted(agents_root.rglob("*.py")):
        if _is_excluded(py_file):
            continue
        files_scanned += 1
        for file, lineno, model_id in _collect_model_literals(py_file):
            if model_id not in registry_keys:
                violations.append((file, lineno, model_id))

    if not violations:
        print(
            f"context-window registry coverage: OK "
            f"({files_scanned} files scanned, {len(registry_keys)} models registered)"
        )
        return 0

    print(
        f"FAIL: {len(violations)} unregistered model literal(s) detected:",
        file=sys.stderr,
    )
    for file, lineno, model_id in violations:
        try:
            rel: Path = file.relative_to(REPO_ROOT)
        except ValueError:
            # --agents-root pointed outside the repo (e.g. a temp fixture dir)
            rel = file
        print(f'  {rel}:{lineno}  model="{model_id}"', file=sys.stderr)
    print(
        "\nRemediation: add each model to MODEL_CONTEXT_WINDOW_REGISTRY in "
        "api/src/kene_api/chat/context_windows.py",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
