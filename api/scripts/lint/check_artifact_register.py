"""CI lint: every call to ``save_artifact`` via ``context``, ``tool_context``,
or ``artifact_service`` must come from the canonical wrapper or an allow-listed
file.

The wrapper (``api/src/kene_api/chat/artifacts.py``) is the only production
path that correctly writes both the GCS blob AND the Firestore metadata row.
A direct ``.save_artifact`` call from any non-allow-listed file silently
produces a GCS orphan that never surfaces in the Chat ArtifactsPanel.

The strategy-agent file (``app/adk/agents/strategy_agent/artifact_utils.py``)
is allow-listed rather than migrated. Four architectural mismatches prevent
the migration: no ToolContext at the setup-time callsite, a different ADK
``app_name``, no parent ``chat_sessions/{session_id}`` Firestore row (the
wrapper's atomic ``batch.update`` would raise NotFound and crash strategy
runs), and a different GCS namespace. Strategy artifacts are setup-time
inputs that pre-load context for the strategy workflow — they are not
user-visible chat outputs.

Usage (from repo root):
    uv run python api/scripts/lint/check_artifact_register.py

Pass ``--root <dir>`` to scan a different tree (used by integration tests
so fixtures are written under pytest's ``tmp_path`` rather than the real source
tree — no leftover-on-crash risk, safe under pytest-xdist).

Exits 0 when the tree is clean; exits 1 with file:line violations on stderr
otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — resolve repo root from this script's location
# ---------------------------------------------------------------------------

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]  # api/scripts/lint/ → repo root

# ---------------------------------------------------------------------------
# Allow-list: files that are permitted to call save_artifact directly.
# Match is suffix-based so it works whether --root is repo root or a temp dir.
# ---------------------------------------------------------------------------

ALLOWLIST: frozenset[str] = frozenset(
    {
        "api/src/kene_api/chat/artifacts.py",  # the wrapper itself
        "app/adk/agents/strategy_agent/artifact_utils.py",  # setup-time input loader; not a chat-session tool
    }
)

# ---------------------------------------------------------------------------
# Detection pattern
# ---------------------------------------------------------------------------

PATTERN: re.Pattern[str] = re.compile(
    r"\b(context|tool_context|artifact_service)\.save_artifact\b"
)

# ---------------------------------------------------------------------------
# Exclusion rules — mirrors check_context_window_registry_coverage.py
# ---------------------------------------------------------------------------

EXCLUDED_PATH_PARTS: frozenset[str] = frozenset(
    {"tests", ".venv", "node_modules", ".git"}
)
EXCLUDED_FILENAME_PREFIXES: tuple[str, ...] = ("test_",)


def _is_excluded(path: Path) -> bool:
    """Return True if the path should be skipped (test trees)."""
    for part in path.parts:
        if part in EXCLUDED_PATH_PARTS:
            return True
    if path.name.startswith(EXCLUDED_FILENAME_PREFIXES):
        return True
    return False


def _is_allowlisted(path: Path, root: Path) -> bool:
    """Return True if the path is in the explicit allow-list."""
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    return str(rel).replace("\\", "/") in ALLOWLIST


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Directory tree to scan (default: repo root).",
    )
    args = parser.parse_args(argv)
    root: Path = args.root.resolve()

    if not root.is_dir():
        print(
            f"ERROR: scan root not found at {root}. "
            "Run this script from the repo root or pass --root.",
            file=sys.stderr,
        )
        return 1

    violations: list[tuple[Path, int, str]] = []
    files_scanned = 0

    for py_file in sorted(root.rglob("*.py")):
        if _is_excluded(py_file):
            continue
        if _is_allowlisted(py_file, root):
            continue
        try:
            lines = py_file.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            print(
                f"WARNING: could not decode {py_file} as UTF-8; skipping.",
                file=sys.stderr,
            )
            continue
        files_scanned += 1
        for lineno, line in enumerate(lines, start=1):
            if PATTERN.search(line):
                violations.append((py_file, lineno, line.strip()))

    if not violations:
        print(f"artifact-register coverage: OK ({files_scanned} files scanned)")
        return 0

    print(
        f"FAIL: {len(violations)} raw save_artifact call(s) detected:",
        file=sys.stderr,
    )
    for file, lineno, stripped in violations:
        try:
            rel = file.relative_to(root)
        except ValueError:
            rel = file
        print(f"  {rel}:{lineno}  {stripped}", file=sys.stderr)
    print(
        "\nUse chat.artifacts.register_artifact() instead.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
