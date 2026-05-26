"""Tests for `[tool.codespell]` in pyproject.toml.

Regression-guards the skip pattern so an accidental edit can't re-introduce
the multi-thousand-file scan of vendored npm packages that DM-103 fixed.

Run with:
    uv run pytest tests/unit/test_codespell_config.py -v
"""

from pathlib import Path

import tomllib

REPO_ROOT = Path(__file__).parent.parent.parent
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"


def _load_codespell_config() -> dict:
    with PYPROJECT_PATH.open("rb") as f:
        return tomllib.load(f)["tool"]["codespell"]


def _skip_entries() -> list[str]:
    return [e.strip() for e in _load_codespell_config()["skip"].split(",")]


class TestSkipPattern:
    def test_node_modules_skipped(self) -> None:
        entries = _skip_entries()
        assert any("node_modules" in e for e in entries), (
            f"`**/node_modules` missing from codespell skip list: {entries}. "
            "Without it, codespell scans vendored npm packages and produces "
            "thousands of false-positive 'misspellings'."
        )

    def test_pyproject_self_skipped(self) -> None:
        """codespell scans pyproject.toml before applying the ignore list, so
        the ignore-words-list value itself would otherwise trip the check."""
        entries = _skip_entries()
        assert any("pyproject.toml" in e for e in entries), (
            f"pyproject.toml missing from skip list: {entries}"
        )

    def test_lockfiles_skipped(self) -> None:
        entries = _skip_entries()
        assert any("uv.lock" in e for e in entries)
        assert any("package-lock.json" in e for e in entries)


class TestIgnoreWords:
    def test_ignore_words_list_present(self) -> None:
        cfg = _load_codespell_config()
        assert "ignore-words-list" in cfg
        assert isinstance(cfg["ignore-words-list"], str)
        assert cfg["ignore-words-list"]
