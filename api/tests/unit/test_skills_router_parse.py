"""Unit tests for ``routers.skills._parse_and_validate_bundle`` 422 rendering.

Verifies that validation failures surface as HTTP 422 with field-pointer
``detail`` lists matching the ``ValidationIssue`` shape from skill_validator.

PRD reference:
  docs/design/components/skills/projects/SK-PRD-01-skills-backend.md §8 Unit tests
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from src.kene_api.routers.skills import _parse_and_validate_bundle

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_SKILL_MD = b"""---
name: test-skill
description: A test skill for unit testing.
---

This is the body of the test skill.
"""


class _FakeUploadFile:
    """Minimal UploadFile substitute for sync/async testing."""

    def __init__(self, filename: str, content: bytes) -> None:
        self.filename = filename
        self._content = content

    async def read(self) -> bytes:
        return self._content


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestParseAndValidateBundle:
    @pytest.mark.asyncio
    async def test_valid_bundle_returns_report_and_bytes(self) -> None:
        skill_md = _FakeUploadFile("SKILL.md", _VALID_SKILL_MD)
        report, skill_md_bytes, files_data = await _parse_and_validate_bundle(
            skill_md, [], outer_name="test-skill"
        )
        assert report.valid is True
        assert skill_md_bytes == _VALID_SKILL_MD
        assert files_data == []

    @pytest.mark.asyncio
    async def test_missing_frontmatter_raises_422(self) -> None:
        bad_md = b"No frontmatter here."
        skill_md = _FakeUploadFile("SKILL.md", bad_md)
        with pytest.raises(HTTPException) as exc_info:
            await _parse_and_validate_bundle(skill_md, [], outer_name="test-skill")
        exc = exc_info.value
        assert exc.status_code == 422
        assert isinstance(exc.detail, list)
        fields = {item["field"] for item in exc.detail}
        assert "skill_md" in fields

    @pytest.mark.asyncio
    async def test_name_mismatch_raises_422_with_name_field(self) -> None:
        skill_md = _FakeUploadFile("SKILL.md", _VALID_SKILL_MD)
        with pytest.raises(HTTPException) as exc_info:
            await _parse_and_validate_bundle(skill_md, [], outer_name="different-name")
        exc = exc_info.value
        assert exc.status_code == 422
        fields = {item["field"] for item in exc.detail}
        assert "name" in fields
        codes = {item["code"] for item in exc.detail}
        assert "name_mismatch" in codes

    @pytest.mark.asyncio
    async def test_oversized_skill_md_raises_422(self) -> None:
        # 5001 bytes of header + body
        large_content = b"---\nname: x\ndescription: y\n---\n" + b"x" * 5000
        skill_md = _FakeUploadFile("SKILL.md", large_content)
        with pytest.raises(HTTPException) as exc_info:
            await _parse_and_validate_bundle(skill_md, [], outer_name="x")
        exc = exc_info.value
        assert exc.status_code == 422
        fields = {item["field"] for item in exc.detail}
        assert "skill_md" in fields

    @pytest.mark.asyncio
    async def test_invalid_name_raises_422_with_field_pointer(self) -> None:
        bad_md = b"---\nname: UPPERCASE\ndescription: A valid description.\n---\n"
        skill_md = _FakeUploadFile("SKILL.md", bad_md)
        with pytest.raises(HTTPException) as exc_info:
            await _parse_and_validate_bundle(skill_md, [], outer_name="UPPERCASE")
        exc = exc_info.value
        assert exc.status_code == 422
        # At least one issue should reference the name field.
        fields = {item["field"] for item in exc.detail}
        assert any("name" in f or "frontmatter" in f for f in fields)

    @pytest.mark.asyncio
    async def test_each_upload_file_read_exactly_once(self) -> None:
        """UploadFile.read() called once per file — no double-read."""
        read_count = 0

        class _CountingUploadFile:
            filename = "references/style.md"

            async def read(self) -> bytes:
                nonlocal read_count
                read_count += 1
                return b"content"

        skill_md = _FakeUploadFile("SKILL.md", _VALID_SKILL_MD)
        ref_file = _CountingUploadFile()
        await _parse_and_validate_bundle(skill_md, [ref_file], outer_name="test-skill")
        assert read_count == 1

    @pytest.mark.asyncio
    async def test_valid_bundle_with_reference_file(self) -> None:
        skill_md = _FakeUploadFile("SKILL.md", _VALID_SKILL_MD)
        ref = _FakeUploadFile(
            "references/guide.md", b"# Guide\nSome reference content."
        )
        report, _, files_data = await _parse_and_validate_bundle(
            skill_md, [ref], outer_name="test-skill"
        )
        assert report.valid is True
        assert len(files_data) == 1
        assert files_data[0][0] == "references/guide.md"

    @pytest.mark.asyncio
    async def test_scripts_file_sets_has_scripts(self) -> None:
        skill_md = _FakeUploadFile("SKILL.md", _VALID_SKILL_MD)
        script = _FakeUploadFile("scripts/run.py", b"print('hello')")
        report, _, _ = await _parse_and_validate_bundle(
            skill_md, [script], outer_name="test-skill"
        )
        assert report.valid is True
        assert report.has_scripts is True

    @pytest.mark.asyncio
    async def test_all_issues_present_in_422_detail(self) -> None:
        """Multiple validation failures all appear in detail, not just the first one."""
        # Too many reference files (21) to trigger that error + large SKILL.md.
        big_md = b"---\nname: ok-skill\ndescription: ok\n---\n" + b"x" * 4900
        skill_md = _FakeUploadFile("SKILL.md", big_md)
        # 21 reference files → too_many_reference_files
        refs = [_FakeUploadFile(f"references/file{i}.md", b"x") for i in range(21)]
        with pytest.raises(HTTPException) as exc_info:
            await _parse_and_validate_bundle(skill_md, refs, outer_name="ok-skill")
        exc = exc_info.value
        assert exc.status_code == 422
        codes = [item["code"] for item in exc.detail]
        assert "too_many_reference_files" in codes
