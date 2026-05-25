"""Unit tests for artifact_id determinism (CH-44).

SHA-256 fixture values computed from: sha256(f"{session_id}|{filename}|{version}").hexdigest()[:32]
"""

from __future__ import annotations

import hashlib

import pytest
from src.kene_api.chat.artifacts import _artifact_id

# Pre-computed fixtures: (session_id, filename, version) → expected_id
_FIXTURES = [
    # sha256("sess_abc|report.pdf|0")[:32]
    ("sess_abc", "report.pdf", 0, "6bf5222872d33d2c01459bd90ca22a7d"),
    # sha256("s1|out.txt|2")[:32]
    ("s1", "out.txt", 2, "2057f0f040cb0463eeca082c33d283cc"),
    # sha256("|f|0")[:32]
    ("", "f", 0, "615f178b5d2f4156b57633f9af3b755b"),
]


class TestArtifactIdDeterminism:
    @pytest.mark.parametrize("session_id,filename,version,expected", _FIXTURES)
    def test_known_fixture(
        self, session_id: str, filename: str, version: int, expected: str
    ) -> None:
        assert _artifact_id(session_id, filename, version) == expected

    def test_length_is_32(self) -> None:
        art_id = _artifact_id("any_session", "any_file.pdf", 0)
        assert len(art_id) == 32

    def test_is_lowercase_hex(self) -> None:
        art_id = _artifact_id("s", "f", 0)
        assert art_id == art_id.lower()
        assert all(c in "0123456789abcdef" for c in art_id)

    def test_version_changes_id(self) -> None:
        id_v0 = _artifact_id("sess", "file.pdf", 0)
        id_v1 = _artifact_id("sess", "file.pdf", 1)
        assert id_v0 != id_v1

    def test_filename_changes_id(self) -> None:
        id_a = _artifact_id("sess", "a.pdf", 0)
        id_b = _artifact_id("sess", "b.pdf", 0)
        assert id_a != id_b

    def test_session_changes_id(self) -> None:
        id_a = _artifact_id("sess_a", "file.pdf", 0)
        id_b = _artifact_id("sess_b", "file.pdf", 0)
        assert id_a != id_b

    def test_consistent_with_hashlib(self) -> None:
        """Cross-check: _artifact_id matches direct hashlib computation."""
        session_id, filename, version = "my_session", "output.csv", 3
        key = f"{session_id}|{filename}|{version}"
        expected = hashlib.sha256(key.encode()).hexdigest()[:32]
        assert _artifact_id(session_id, filename, version) == expected
