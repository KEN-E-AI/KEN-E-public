"""CI lint: ``AgentTool(`` constructor calls are forbidden in the chat-tree 2.0
build (``app/adk/``), EXCEPT inside ``strategy_agent/`` and the two sanctioned
*isolation* leaves (see the allow-list below).

Background (AH-PRD-15 §2 + the AH-121 re-plan):  GitHub ``google/adk-python#3984``
(OPEN) means ``AgentTool.run_async`` discards inner sub-agent events on ADK 2.0 —
so the leaf's ``gemini-2.5-flash`` tokens go uncounted.  AH-114/115/116 tried to
migrate the chat-tree agent-as-tool surface to task-mode (``LlmAgent(mode='task')``)
to fix that, and this guard originally locked task-mode in.

**AH-121 re-plan:** task-mode is *unworkable* for the two real agent-tools.
``google_search`` (built-in grounding) and ``numerical_analyst`` (built-in code
execution) wrap a built-in tool that Gemini forbids alongside ANY function
declaration; every sub-agent mode injects one (``mode='task'`` → ``FinishTaskTool``;
``mode='chat'`` → ``transfer_to_agent``) → ``400 ... all search tools``.  The ONLY
mechanism that isolates such a leaf is an ``AgentTool`` (own sub-runner, no injected
sibling tool).  Those two constructions are therefore *required*, and the #3984
billing drop they incur is recovered by the ``capture_agent_tool_usage``
after_model_callback on each leaf (``app/adk/agents/agent_tool_billing.py``).

The guard still forbids every OTHER ``AgentTool(`` in the chat tree, so a future
change cannot silently reintroduce an unbilled inner-Runner path.

Scope boundary (AH-PRD-15 §2):
  ``app/adk/agents/strategy_agent/`` stays pinned to ADK 1.34.x and is retired
  via KG-PRD-05 — its ``AgentTool`` usage is correct on 1.34.1 and is
  explicitly excluded from this guard.

Isolation allow-list (AH-PRD-15 §7.7):
  ``tools/agent_tools/google_search.py`` and ``tools/agent_tools/numerical_analyst.py``
  may construct an ``AgentTool`` ONLY on a line that carries (or is immediately
  preceded by) the ``isolation-required`` marker comment.  An allow-listed file
  without the marker is still a violation — the marker forces each sanctioned
  construction to be a deliberate, documented act.  The companion test
  ``test_no_agent_tool_lint_rule.py`` also asserts those leaves carry the billing
  callback, so an AgentTool can never be reintroduced without its billing.

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

# ---------------------------------------------------------------------------
# Isolation allow-list (AH-PRD-15 §7.7 re-plan)
# ---------------------------------------------------------------------------
# These files MAY construct an AgentTool — but only on a line carrying (or
# immediately preceded by) the ``isolation-required`` marker. Paths are POSIX,
# relative to the scan root (``app/adk/``), so the integration test can recreate
# them under a temp root.
ISOLATION_ALLOWLIST: frozenset[str] = frozenset(
    {
        "tools/agent_tools/google_search.py",
        "tools/agent_tools/numerical_analyst.py",
    }
)
ISOLATION_MARKER: str = "isolation-required"
# How many preceding non-blank lines may carry the marker for a comment-above style.
_MARKER_LOOKBACK = 2


def _is_excluded(path: Path) -> bool:
    """Return True if the path should be skipped."""
    for part in path.parts:
        if part in EXCLUDED_PATH_PARTS:
            return True
    if path.name.startswith(EXCLUDED_FILENAME_PREFIXES):
        return True
    return False


def _is_sanctioned_isolation(rel_posix: str, lines: list[str], idx: int) -> bool:
    """Return True if the ``AgentTool(`` at ``lines[idx]`` is a sanctioned isolation.

    Requires BOTH: the file is on :data:`ISOLATION_ALLOWLIST`, AND the construction
    line itself or one of the ``_MARKER_LOOKBACK`` preceding non-blank lines carries
    the :data:`ISOLATION_MARKER`. An allow-listed file without the marker is still a
    violation.
    """
    if rel_posix not in ISOLATION_ALLOWLIST:
        return False
    if ISOLATION_MARKER in lines[idx]:
        return True
    seen = 0
    for j in range(idx - 1, -1, -1):
        prev = lines[j].strip()
        if not prev:
            continue
        if ISOLATION_MARKER in lines[j]:
            return True
        seen += 1
        if seen >= _MARKER_LOOKBACK:
            break
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
        try:
            rel_posix = py_file.relative_to(root).as_posix()
        except ValueError:
            rel_posix = py_file.as_posix()
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            if PATTERN.search(line):
                if _is_sanctioned_isolation(rel_posix, lines, idx):
                    continue
                violations.append((py_file, idx + 1, stripped))

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
        "\nAgentTool is forbidden in the chat tree except for the two sanctioned "
        "isolation leaves (google_search, numerical_analyst), which need it to isolate "
        "a built-in tool and must carry the 'isolation-required' marker + the "
        "capture_agent_tool_usage billing callback. For anything else, attach the "
        "sub-agent via transfer_to_agent (specialists) — see AH-PRD-15 §7.7 and the "
        "AH-121 re-plan.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
