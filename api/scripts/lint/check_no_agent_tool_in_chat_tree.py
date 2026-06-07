"""CI lint: no ``AgentTool(`` constructor call may exist anywhere in the
chat-tree 2.0 build (``app/adk/``), except inside ``strategy_agent/``.

Background (AH-PRD-15 §2):  GitHub ``google/adk-python#3984`` (OPEN) means
``AgentTool.run_async`` discards inner sub-agent events on ADK 2.0 — so
``gemini-2.5-flash`` tokens go uncounted and grounded-search steps vanish
from traces.  AH-114/115/116 migrated the chat-tree agent-as-tool surface to
task-mode (``LlmAgent(mode='task')``) / ``ctx.run_node``.  This guard locks in
that migration so no future change silently reintroduces an ``AgentTool``
constructor in the chat tree.

Scope boundary (AH-PRD-15 §2):
  ``app/adk/agents/strategy_agent/`` stays pinned to ADK 1.34.x and is retired
  via KG-PRD-05 — its ``AgentTool`` usage is correct on 1.34.1 and is
  explicitly excluded from this guard.

Limitation (known, acceptable): the regex matches the literal token
``AgentTool(``.  An aliased construction
(``from … import AgentTool as Alias; Alias(...)``) is not caught.
Bypassing the guard this way is a deliberate act; the guard exists to catch
unintentional regressions, not adversarial misuse (mirrors
``check_artifact_register.py``'s approach).

Usage (from repo root):
    uv run python api/scripts/lint/check_no_agent_tool_in_chat_tree.py

Pass ``--root <dir>`` to scan a different tree (used by integration tests so
fixtures are written under pytest's ``tmp_path`` rather than the real source
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
# Path setup — resolve app/adk/ root from this script's location
# ---------------------------------------------------------------------------

SCRIPT_PATH = Path(__file__).resolve()
# api/scripts/lint/ → api/ → repo root → app/adk/
DEFAULT_ROOT: Path = SCRIPT_PATH.parents[3] / "app" / "adk"

# ---------------------------------------------------------------------------
# Detection pattern — constructor calls only, not import / isinstance / docs
# ---------------------------------------------------------------------------

PATTERN: re.Pattern[str] = re.compile(r"\bAgentTool\s*\(")

# ---------------------------------------------------------------------------
# Exclusion rules
# ---------------------------------------------------------------------------

EXCLUDED_PATH_PARTS: frozenset[str] = frozenset(
    {
        "tests",
        ".venv",
        "node_modules",
        ".git",
        "__pycache__",
        "strategy_agent",  # stays on ADK 1.34.1; retired via KG-PRD-05
    }
)
EXCLUDED_FILENAME_PREFIXES: tuple[str, ...] = ("test_",)


def _is_excluded(path: Path) -> bool:
    """Return True if the path should be skipped."""
    for part in path.parts:
        if part in EXCLUDED_PATH_PARTS:
            return True
    if path.name.startswith(EXCLUDED_FILENAME_PREFIXES):
        return True
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="Directory tree to scan (default: app/adk/ relative to repo root).",
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
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            if PATTERN.search(line):
                violations.append((py_file, lineno, stripped))

    if not violations:
        print(f"no-AgentTool-in-chat-tree: OK ({files_scanned} files scanned)")
        return 0

    print(
        f"FAIL: {len(violations)} AgentTool( constructor(s) detected in chat tree:",
        file=sys.stderr,
    )
    for file, lineno, stripped in violations:
        try:
            rel = file.relative_to(root)
        except ValueError:
            rel = file
        print(f"  {rel}:{lineno}  {stripped}", file=sys.stderr)
    print(
        "\nUse the task-mode dispatch path (LlmAgent(mode='task')) — see AH-PRD-15 §2 and AH-114.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
