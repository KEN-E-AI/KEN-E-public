#!/usr/bin/env python3
"""Verify that every users/{user_id}/<subcollection>/ write in source code is
registered in USER_SUBCOLLECTIONS from user_deletion_service.py.

Usage (run from repo root):
    python api/scripts/check_user_subcollections_registry.py [--include-tests]

Exit codes:
    0  All observed subcollection names are in USER_SUBCOLLECTIONS.
    1  One or more writes-not-in-registry found (names + file:line printed).
    2  Usage error.

The check is intentionally one-directional: registry entries that have no
observed write (e.g. future PRDs that registered ahead of ship) are *not*
flagged.  Only writes absent from the registry indicate a real deletion gap.

Spec: docs/design/components/data-management/projects/
         DM-PRD-05-deletion-sweep-rewrite.md §6 AC-11
      docs/design/components/data-management/projects/
         DM-PRD-06-verification-and-cutover.md §4.2
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Repo-root detection and import-path setup
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent  # …/api/scripts/ -> …/api/ -> repo root
_API_SRC = _REPO_ROOT / "api" / "src"

sys.path.insert(0, str(_API_SRC))

try:
    from kene_api.services.user_deletion_service import USER_SUBCOLLECTIONS
except ImportError as exc:
    print(
        f"ERROR: cannot import USER_SUBCOLLECTIONS from "
        f"kene_api.services.user_deletion_service.\n"
        f"Run this script from the repository root:\n"
        f"  python api/scripts/check_user_subcollections_registry.py\n"
        f"Import error: {exc}",
        file=sys.stderr,
    )
    sys.exit(2)

# ---------------------------------------------------------------------------
# Source directories to scan
# ---------------------------------------------------------------------------

_SCAN_DIRS = [
    _REPO_ROOT / "api" / "src" / "kene_api",
    _REPO_ROOT / "app",
]

# ---------------------------------------------------------------------------
# Regex patterns for user-subcollection writes
#
# Pattern A: chained Firestore SDK call (may span multiple lines)
#   .collection("users").document(<anything>).collection("<name>")
#   The outer .collection("users") can be preceded by any expression.
#   We need the subcollection name that follows the second .collection(…).
#
# Pattern B: f-string path
#   f"users/{<var>}/<name>" or f'users/{<var>}/<name>'
# ---------------------------------------------------------------------------

# Pattern A captures the subcollection name from the chained API call.
# The three parts of the chain are separated by whitespace only (spaces/newlines
# for vertical formatting) — NOT arbitrary code.  This prevents the greedy
# matcher from crossing statement boundaries, which would produce false
# positives like `.collection("users").document(uid).get()` ... <many lines> ...
# `.collection("security")` appearing as a hit.
_PATTERN_A = re.compile(
    r'\.collection\(\s*["\']users["\']\s*\)'  # .collection("users")
    r"\s*"  # whitespace/newlines only
    r"\.document\([^)]+\)"  # .document(...)
    r"\s*"  # whitespace/newlines only
    r'\.collection\(\s*["\']([^"\']+)["\']\s*\)',  # .collection("<name>")  ← capture
    re.MULTILINE,
)

# Pattern B: f"users/{var}/subcollection_name"
_PATTERN_B = re.compile(
    r"""f["']users/\{[^}]+\}/([A-Za-z_][A-Za-z0-9_-]*)["']""",
    re.MULTILINE,
)


def _is_test_file(path: Path) -> bool:
    """Return True if any component of *path* looks like a test directory/file."""
    for part in path.parts:
        if part in ("tests", "testing") or part.startswith("test_"):
            return True
    return False


def _scan_file(path: Path) -> list[tuple[str, int]]:
    """Return list of (subcollection_name, line_number) from *path*."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    hits: list[tuple[str, int]] = []

    # We scan the whole file content for Pattern A (which can span lines).
    # For each match, compute the approximate line number from match.start().
    for match in _PATTERN_A.finditer(source):
        name = match.group(1)
        line_no = source.count("\n", 0, match.start()) + 1
        hits.append((name, line_no))

    for match in _PATTERN_B.finditer(source):
        name = match.group(1)
        line_no = source.count("\n", 0, match.start()) + 1
        hits.append((name, line_no))

    return hits


def run(include_tests: bool = False) -> int:
    """Scan source files; return exit code (0 = clean, 1 = mismatch)."""
    registry: set[str] = set(USER_SUBCOLLECTIONS)

    # observed: name → list of "file:line" strings for error reporting
    observed: dict[str, list[str]] = {}

    for base_dir in _SCAN_DIRS:
        if not base_dir.exists():
            continue
        for py_file in base_dir.rglob("*.py"):
            if not include_tests and _is_test_file(py_file):
                continue
            for name, lineno in _scan_file(py_file):
                rel = str(py_file.relative_to(_REPO_ROOT))
                observed.setdefault(name, []).append(f"{rel}:{lineno}")

    # Report observed set for human spot-check
    if observed:
        print("Observed user/{user_id}/<subcollection> writes in source:")
        for name in sorted(observed):
            marker = "  OK " if name in registry else "  !! "
            print(f"{marker} {name!r}")
            for loc in observed[name]:
                print(f"       {loc}")
    else:
        print("No user/{user_id}/<subcollection> writes detected in source.")

    # Writes present in source but absent from registry → deletion gap
    unregistered = {n: locs for n, locs in observed.items() if n not in registry}

    if unregistered:
        print(
            "\nERROR: The following subcollection writes are NOT in USER_SUBCOLLECTIONS "
            "and will be ORPHANED on user deletion:",
            file=sys.stderr,
        )
        for name, locs in sorted(unregistered.items()):
            print(f"  {name!r}", file=sys.stderr)
            for loc in locs:
                print(f"    {loc}", file=sys.stderr)
        print(
            "\nFix: add each name above to USER_SUBCOLLECTIONS in "
            "api/src/kene_api/services/user_deletion_service.py",
            file=sys.stderr,
        )
        return 1

    print(
        f"\nPASS: all {len(observed)} observed subcollection name(s) are registered "
        f"in USER_SUBCOLLECTIONS ({len(registry)} entries total)."
    )
    return 0


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="check_user_subcollections_registry",
        description=(
            "Verify every users/{user_id}/<subcollection> write in source is "
            "registered in USER_SUBCOLLECTIONS (user_deletion_service.py). "
            "Exits 0 on success, 1 on mismatch, 2 on usage error."
        ),
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        default=False,
        help=(
            "Also scan test files (default: excluded). "
            "Test fixtures may intentionally reference subcollections that "
            "don't yet have production write sites."
        ),
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    sys.exit(run(include_tests=args.include_tests))
