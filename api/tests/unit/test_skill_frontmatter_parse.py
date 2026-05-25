"""Unit tests for ``skill_validator.parse_frontmatter``.

Covers every branch of the frontmatter parser as specified in
SK-PRD-01 §8 (Unit tests — test_skill_frontmatter_parse.py).

PRD reference: docs/design/components/skills/projects/SK-PRD-01-skills-backend.md §8
"""

from __future__ import annotations

from src.kene_api.services.skill_validator import ParsedFrontmatter, parse_frontmatter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _md(frontmatter: str, body: str = "The body text.\n") -> bytes:
    """Build a minimal valid SKILL.md byte blob from raw frontmatter and body."""
    return f"---\n{frontmatter}---\n{body}".encode()


def _has_code(result: ParsedFrontmatter, code: str) -> bool:
    return any(i.code == code for i in result.issues)


def _issue_fields(result: ParsedFrontmatter) -> set[str]:
    return {i.field for i in result.issues}


# ---------------------------------------------------------------------------
# Happy-path round-trips
# ---------------------------------------------------------------------------


class TestParseFrontmatterHappyPath:
    """Valid agentskills.io-style SKILL.md files round-trip correctly."""

    def test_minimal_name_and_description(self) -> None:
        raw = _md("name: seo-checklist\ndescription: A concise SEO checklist.\n")
        result = parse_frontmatter(raw)

        assert result.frontmatter is not None
        assert result.frontmatter.name == "seo-checklist"
        assert result.frontmatter.description == "A concise SEO checklist."
        assert result.issues == []

    def test_with_license_and_compatibility(self) -> None:
        raw = _md(
            "name: my-skill\n"
            "description: Some description.\n"
            "license: Apache-2.0\n"
            "compatibility: KEN-E agents\n"
        )
        result = parse_frontmatter(raw)

        assert result.frontmatter is not None
        assert result.frontmatter.license == "Apache-2.0"
        assert result.frontmatter.compatibility == "KEN-E agents"
        assert result.issues == []

    def test_with_allowed_tools_alias(self) -> None:
        raw = _md(
            "name: my-skill\ndescription: desc\nallowed-tools: Read Write Bash(git:*)\n"
        )
        result = parse_frontmatter(raw)

        assert result.frontmatter is not None
        assert result.frontmatter.allowed_tools == "Read Write Bash(git:*)"
        assert result.issues == []

    def test_with_metadata_dict(self) -> None:
        raw = _md(
            "name: my-skill\n"
            "description: desc\n"
            "metadata:\n"
            "  author: alice\n"
            "  version: '1.0'\n"
        )
        result = parse_frontmatter(raw)

        assert result.frontmatter is not None
        assert result.frontmatter.metadata == {"author": "alice", "version": "1.0"}
        assert result.issues == []

    def test_body_bytes_returned_verbatim(self) -> None:
        body = "## Instructions\n\nDo the thing.\n\nWith trailing whitespace   \n"
        raw = _md("name: my-skill\ndescription: desc\n", body)
        result = parse_frontmatter(raw)

        assert result.frontmatter is not None
        assert result.body == body.encode("utf-8")

    def test_unknown_extra_fields_ignored(self) -> None:
        raw = _md("name: my-skill\ndescription: desc\nunknown-field: ignored\n")
        result = parse_frontmatter(raw)

        assert result.frontmatter is not None
        assert result.issues == []

    def test_all_optional_fields_omitted(self) -> None:
        raw = _md("name: my-skill\ndescription: Minimal.\n")
        result = parse_frontmatter(raw)

        assert result.frontmatter is not None
        assert result.frontmatter.license is None
        assert result.frontmatter.compatibility is None
        assert result.frontmatter.metadata is None
        assert result.frontmatter.allowed_tools is None


# ---------------------------------------------------------------------------
# Missing / malformed delimiter cases
# ---------------------------------------------------------------------------


class TestParseFrontmatterDelimiterErrors:
    """Delimiter-level errors yield the correct issue codes."""

    def test_no_frontmatter_body_only(self) -> None:
        raw = b"# Heading\n\nBody text here.\n"
        result = parse_frontmatter(raw)

        assert result.frontmatter is None
        assert _has_code(result, "frontmatter_missing")

    def test_frontmatter_unclosed(self) -> None:
        raw = b"---\nname: my-skill\ndescription: desc\n"
        result = parse_frontmatter(raw)

        assert result.frontmatter is None
        assert _has_code(result, "frontmatter_unclosed")

    def test_empty_frontmatter_block(self) -> None:
        raw = b"---\n---\nBody text.\n"
        result = parse_frontmatter(raw)

        assert result.frontmatter is None
        assert _has_code(result, "frontmatter_empty")

    def test_whitespace_only_frontmatter_block(self) -> None:
        raw = b"---\n   \n   \n---\nBody text.\n"
        result = parse_frontmatter(raw)

        assert result.frontmatter is None
        assert _has_code(result, "frontmatter_empty")


# ---------------------------------------------------------------------------
# Tab-indentation detection
# ---------------------------------------------------------------------------


class TestParseFrontmatterCRLF:
    """CRLF line endings are handled correctly."""

    def test_crlf_frontmatter_parses_correctly(self) -> None:
        raw = b"---\r\nname: my-skill\r\ndescription: desc\r\n---\r\nBody.\r\n"
        result = parse_frontmatter(raw)

        assert result.frontmatter is not None
        assert result.frontmatter.name == "my-skill"
        assert result.issues == []

    def test_crlf_block_scalar_does_not_false_close(self) -> None:
        # A YAML block scalar that contains "---" must NOT be treated as a closer.
        raw = (
            b"---\r\n"
            b"name: my-skill\r\n"
            b"description: 'has --- inside'\r\n"
            b"---\r\n"
            b"Body.\r\n"
        )
        result = parse_frontmatter(raw)

        assert result.frontmatter is not None
        assert result.issues == []


class TestParseFrontmatterTabIndent:
    """Leading tabs in frontmatter are detected and reported."""

    def test_tab_indented_value_raises_issue(self) -> None:
        # A tab-indented continuation/mapping value — realistic copy-paste error.
        raw = b"---\nname: my-skill\n\tdescription: desc\n---\nBody.\n"
        result = parse_frontmatter(raw)

        assert result.frontmatter is None
        assert _has_code(result, "frontmatter_tab_indent")

    def test_tab_inside_quoted_string_is_fine(self) -> None:
        # A tab character *inside* a quoted YAML value (not leading indent).
        raw = "---\nname: my-skill\ndescription: 'value with\ttab inside'\n---\nBody.\n"
        result = parse_frontmatter(raw.encode("utf-8"))

        # Should succeed — the tab is inside a quoted string, not leading indent.
        assert result.frontmatter is not None
        assert result.issues == []


# ---------------------------------------------------------------------------
# YAML parse errors
# ---------------------------------------------------------------------------


class TestParseFrontmatterYamlErrors:
    """Malformed YAML emits frontmatter_yaml_invalid."""

    def test_malformed_yaml_unclosed_bracket(self) -> None:
        raw = b"---\nname: [unclosed\ndescription: desc\n---\nBody.\n"
        result = parse_frontmatter(raw)

        assert result.frontmatter is None
        assert _has_code(result, "frontmatter_yaml_invalid")

    def test_non_dict_yaml_list(self) -> None:
        raw = b"---\n- item1\n- item2\n---\nBody.\n"
        result = parse_frontmatter(raw)

        assert result.frontmatter is None
        assert _has_code(result, "frontmatter_yaml_invalid")

    def test_non_utf8_bytes(self) -> None:
        raw = b"---\nname: \xff\xfe\n---\nBody.\n"
        result = parse_frontmatter(raw)

        assert result.frontmatter is None
        assert len(result.issues) > 0

    def test_pure_non_utf8_blob(self) -> None:
        raw = bytes(range(128, 256))
        result = parse_frontmatter(raw)

        assert result.frontmatter is None
        assert _has_code(result, "frontmatter_yaml_invalid")


# ---------------------------------------------------------------------------
# Field-level Pydantic violation cases
# ---------------------------------------------------------------------------


class TestParseFrontmatterFieldViolations:
    """Pydantic validation errors surface as issues with field pointers."""

    def test_uppercase_name_emits_name_regex_code(self) -> None:
        raw = _md("name: PDF-Processing\ndescription: desc\n")
        result = parse_frontmatter(raw)

        assert result.frontmatter is None
        assert any(
            i.code == "name_regex" and "frontmatter.name" in i.field
            for i in result.issues
        )

    def test_description_too_long_emits_description_length_code(self) -> None:
        raw = _md(f"name: my-skill\ndescription: {'d' * 1025}\n")
        result = parse_frontmatter(raw)

        assert result.frontmatter is None
        assert any(
            i.code == "description_length" and "frontmatter.description" in i.field
            for i in result.issues
        )

    def test_missing_required_fields(self) -> None:
        # No name or description.
        raw = b"---\nlicense: MIT\n---\nBody.\n"
        result = parse_frontmatter(raw)

        assert result.frontmatter is None
        assert len(result.issues) > 0

    def test_never_raises_on_bad_input(self) -> None:
        # Regardless of input, parse_frontmatter must return — never raise.
        for raw in [
            b"",
            b"\x00",
            b"---\n",
            b"---\n---\n",
            b"---\ngarbage: [[\n---\n",
        ]:
            result = parse_frontmatter(raw)
            assert isinstance(result, ParsedFrontmatter)
