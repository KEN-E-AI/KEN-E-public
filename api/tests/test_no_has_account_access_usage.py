"""CI guard: ensure has_account_access() is never called from production code.

This test fails if any file outside auth/models.py (the deprecated stub itself)
and known test files calls has_account_access(). It is the machine-enforced
equivalent of the code-review rule added in IN-2.

Allowed locations:
  - api/src/kene_api/auth/models.py           (the deprecated stub)
  - api/src/kene_api/auth/account_org.py      (docstring reference only)
  - api/src/kene_api/routers/oauth_integrations.py  (pending IN-1 merge; removed post-merge)
  - api/tests/test_auth_models.py             (tests for the deprecated stub)
  - api/tests/test_no_has_account_access_usage.py   (this file)
  - api/tests/test_oauth_permissions.py       (unit tests for UserContext permission logic)
  - api/tests/unit/test_user_context.py       (tests the deprecated-stub raises)
"""

from pathlib import Path

# Files that are explicitly allowed to contain the pattern.
# Use full path suffixes to avoid false-positives (e.g. a future routers/auth/models.py).
ALLOWED_SUFFIXES = frozenset(
    [
        "api/src/kene_api/auth/models.py",
        "api/src/kene_api/auth/account_org.py",
        "api/tests/test_auth_models.py",
        "api/tests/test_no_has_account_access_usage.py",
        "api/tests/test_oauth_permissions.py",
        "api/tests/unit/test_user_context.py",
    ]
)

REPO_ROOT = Path(__file__).parents[2]  # api/tests -> api -> repo root

_PATTERN = "has_account_access("
_SCAN_DIRS = ("api/src", "api/tests")


def _scan_hits(root: Path) -> list[str]:
    """Return ``path:lineno:line`` for every ``has_account_access(`` outside the allowlist.

    Pure-Python file walk (no ``git`` dependency) so the guard runs in any CI
    container — the ``api-unit-tests`` image has no ``git`` binary, which made
    the previous ``git grep`` implementation raise ``FileNotFoundError``.
    """
    hits: list[str] = []
    for rel_dir in _SCAN_DIRS:
        base = root / rel_dir
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            norm_path = path.as_posix()
            if any(norm_path.endswith(suffix) for suffix in ALLOWED_SUFFIXES):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if _PATTERN in line:
                    rel = path.relative_to(root).as_posix()
                    hits.append(f"{rel}:{lineno}:{line.strip()}")
    return hits


def test_no_has_account_access_in_production_code() -> None:
    """Fail if has_account_access() appears in any non-allowed file."""
    hits = _scan_hits(REPO_ROOT)
    assert not hits, (
        "has_account_access() found in non-allowed files (IN-2: use require_account_access_for instead):\n"
        + "\n".join(f"  {h}" for h in hits)
    )


def test_guard_rejects_planted_regression(tmp_path: Path) -> None:
    """End-to-end self-test: ``_scan_hits`` flags a planted call and ignores allowed files.

    Builds a throwaway repo tree under ``tmp_path`` with the pattern in both a
    non-allowlisted router and an allowlisted file, then runs the real
    ``_scan_hits`` against it — proving the scanner catches regressions while
    honouring the allowlist (IN-2 acceptance criterion d).
    """
    planted = tmp_path / "api/src/kene_api/routers/new_router.py"
    planted.parent.mkdir(parents=True, exist_ok=True)
    planted.write_text("if not user.has_account_access(account_id):\n    raise\n")

    allowed = tmp_path / "api/src/kene_api/auth/models.py"
    allowed.parent.mkdir(parents=True, exist_ok=True)
    allowed.write_text("def has_account_access(self):\n    raise NotImplementedError\n")

    hits = _scan_hits(tmp_path)

    assert any("routers/new_router.py" in h for h in hits), (
        f"Guard failed to detect planted regression; hits={hits!r}"
    )
    assert not any("auth/models.py" in h for h in hits), (
        f"Guard must not flag allowlisted files; hits={hits!r}"
    )
