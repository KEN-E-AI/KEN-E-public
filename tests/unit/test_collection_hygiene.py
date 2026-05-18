"""Guard against test_*.py-named scripts re-entering directories DM-89 cleaned.

pytest collects ``test_*.py`` / ``*_test.py`` by default. Diagnostic scripts
that carry that name but aren't tests get imported during collection; several
call ``sys.exit()`` at import, which raises ``SystemExit`` and aborts the run
with an ``INTERNALERROR``. DM-89 renamed those scripts (``test_*`` ->
``check_*``); this test fails if any reappear in a directory already cleaned.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Directories DM-89 has cleared of test-named non-test scripts. As later
# phases land, append their directories here so a regression fails CI.
_CLEANED_DIRS = ["api/scripts"]


@pytest.mark.parametrize("rel_dir", _CLEANED_DIRS)
def test_no_test_named_scripts_in_cleaned_dir(rel_dir: str) -> None:
    """No ``test_*.py`` / ``*_test.py`` file sits directly in a cleaned dir.

    Scoped to the directory itself, not its ``tests/`` subtree — genuine
    pytest suites under ``<dir>/tests/`` are intentionally unaffected.
    """
    target = _REPO_ROOT / rel_dir
    offenders = sorted(
        path.name
        for path in target.iterdir()
        if path.is_file()
        and path.suffix == ".py"
        and (path.name.startswith("test_") or path.name.endswith("_test.py"))
    )
    assert offenders == [], (
        f"{rel_dir}/ contains test-named non-test scripts: {offenders}. "
        "Rename them (e.g. check_*.py) — pytest collects test_*.py by default "
        "and import-time side effects abort collection. See DM-89."
    )
