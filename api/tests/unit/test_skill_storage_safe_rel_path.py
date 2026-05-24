"""Unit tests for ``skill_storage.safe_rel_path``.

Exhaustively covers all rejection classes documented in SK-PRD-01 §7 AC-4
and SK-14's Implementation Plan Task 1 acceptance criteria.

One parametrized test class per rejection class; a separate class for valid
inputs to ensure we don't over-reject.
"""

from __future__ import annotations

import pytest
from src.kene_api.services.skill_storage import safe_rel_path


class TestSafeRelPathValid:
    """Paths that should pass and return the canonical form."""

    @pytest.mark.parametrize(
        "input_path, expected",
        [
            ("references/style.md", "references/style.md"),
            ("references/guide.txt", "references/guide.txt"),
            ("assets/logo.png", "assets/logo.png"),
            ("scripts/extract.py", "scripts/extract.py"),
            ("SKILL.md", "SKILL.md"),
            # Nested within a valid dir is fine.
            ("references/subdir/note.md", "references/subdir/note.md"),
            # A single dot in the middle normalises away.
            ("references/./style.md", "references/style.md"),
            # Mixed depth is still safe.
            ("assets/images/hero.jpg", "assets/images/hero.jpg"),
        ],
    )
    def test_returns_canonical_path(self, input_path: str, expected: str) -> None:
        assert safe_rel_path(input_path) == expected


class TestSafeRelPathEmptyString:
    """Empty string must be rejected."""

    def test_empty_string(self) -> None:
        assert safe_rel_path("") is None


class TestSafeRelPathNullByte:
    """Paths containing null bytes are rejected."""

    @pytest.mark.parametrize(
        "path",
        [
            "a\x00b",
            "\x00",
            "references/\x00style.md",
            "scripts/extract\x00.py",
        ],
    )
    def test_null_byte_rejected(self, path: str) -> None:
        assert safe_rel_path(path) is None


class TestSafeRelPathBackslash:
    """Backslashes indicate mixed separators and are rejected."""

    @pytest.mark.parametrize(
        "path",
        [
            "references\\style.md",
            "references\\..\\etc",
            "assets\\logo.png",
            "scripts\\extract.py",
        ],
    )
    def test_backslash_rejected(self, path: str) -> None:
        assert safe_rel_path(path) is None


class TestSafeRelPathUrlEncoded:
    """Any percent sign is rejected — covers URL-encoded dots and double-encoding."""

    @pytest.mark.parametrize(
        "path",
        [
            # Single-encoding
            "%2e%2e/etc/passwd",
            "%2E%2E/etc/passwd",
            "references/%2e%2e/secret",
            "%2e%2e%2fetc",
            "%2E%2E%2Fetc",
            "references/%2E%2E%2Fsecret",
            "a/%2e/b",
            # Double-encoding (%25 decodes to %, then %2e decodes to .)
            "%252e%252e/etc/passwd",
            "references/%252e%252e/secret",
            # Any bare percent sign
            "references/style%20guide.md",
            "assets/logo%2epng",
        ],
    )
    def test_percent_encoding_rejected(self, path: str) -> None:
        assert safe_rel_path(path) is None


class TestSafeRelPathAbsolutePath:
    """Absolute paths (leading /) are rejected."""

    @pytest.mark.parametrize(
        "path",
        [
            "/etc/passwd",
            "/abs/path",
            "/references/style.md",
        ],
    )
    def test_absolute_path_rejected(self, path: str) -> None:
        assert safe_rel_path(path) is None


class TestSafeRelPathTraversal:
    """Paths containing ``..`` after normpath are rejected."""

    @pytest.mark.parametrize(
        "path",
        [
            "../etc/passwd",
            "references/../../etc",
            "a/../../../b",
            "..",
            "../",
            "references/../../../secret",
        ],
    )
    def test_traversal_rejected(self, path: str) -> None:
        assert safe_rel_path(path) is None


class TestSafeRelPathMixedCases:
    """Edge cases that could combine multiple rejection triggers."""

    @pytest.mark.parametrize(
        "path",
        [
            # URL-encoded traversal with leading slash
            "/%2e%2e/etc",
            # Null + traversal
            "../\x00passwd",
            # Backslash traversal
            "..\\/etc",
        ],
    )
    def test_mixed_rejection(self, path: str) -> None:
        assert safe_rel_path(path) is None
