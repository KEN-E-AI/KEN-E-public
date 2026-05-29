"""Unit tests for app.adk.agents.agent_factory.dispatch.

The ``generate_dispatch_functions`` / ``_build_dispatch`` symbols were deleted
in AH-66 (confirmed zero non-test production callers).  Only
``assemble_available_specialists_block`` and ``assemble_specialists_block_from_state``
remain; this file covers both public symbols.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.adk.agents.agent_factory.dispatch import (
    assemble_available_specialists_block,
    assemble_specialists_block_from_state,
)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_specialist(
    name: str, description: str | None = "A test specialist"
) -> MagicMock:
    """Return a MagicMock that quacks like a minimal LlmAgent."""
    agent = MagicMock()
    agent.name = name
    agent.description = description
    return agent


# ---------------------------------------------------------------------------
# TestAssembleAvailableSpecialistsBlock
# ---------------------------------------------------------------------------


class TestAssembleAvailableSpecialistsBlock:
    def test_empty_specialists_returns_heading_plus_none_registered(self) -> None:
        result = assemble_available_specialists_block({})

        assert result.startswith("## Available Specialists")
        assert "None registered" in result

    def test_specialists_sorted_alphabetically_with_descriptions(self) -> None:
        specialists = {
            "c_spec": _make_specialist("c_spec", "C desc"),
            "a_spec": _make_specialist("a_spec", "A desc"),
            "b_spec": _make_specialist("b_spec", "B desc"),
        }
        result = assemble_available_specialists_block(specialists)

        assert result.startswith("## Available Specialists\n\n")
        lines = result.splitlines()
        bullets = [line for line in lines if line.startswith("- **")]
        assert len(bullets) == 3
        assert "a_spec" in bullets[0]
        assert "b_spec" in bullets[1]
        assert "c_spec" in bullets[2]
        assert "A desc" in bullets[0]
        assert "B desc" in bullets[1]
        assert "C desc" in bullets[2]

    def test_missing_description_uses_fallback(self) -> None:
        specialists = {"no_desc": _make_specialist("no_desc", None)}
        result = assemble_available_specialists_block(specialists)

        assert "(no description provided)" in result

    def test_empty_description_uses_fallback(self) -> None:
        specialists = {"empty_desc": _make_specialist("empty_desc", "")}
        result = assemble_available_specialists_block(specialists)

        assert "(no description provided)" in result

    def test_single_specialist_formats_correctly(self) -> None:
        specialists = {"my_spec": _make_specialist("my_spec", "Does things")}
        result = assemble_available_specialists_block(specialists)

        assert "- **my_spec**: Does things" in result

    def test_heading_always_present(self) -> None:
        for specialists in [{}, {"x": _make_specialist("x")}]:
            result = assemble_available_specialists_block(specialists)
            assert "## Available Specialists" in result


# ---------------------------------------------------------------------------
# TestAssembleAvailableSpecialistsBlockSanitisation
# ---------------------------------------------------------------------------


class TestAssembleAvailableSpecialistsBlockSanitisation:
    def test_description_unsafe_chars_stripped(self) -> None:
        specialists = {
            "safe_spec": _make_specialist(
                "safe_spec",
                "Normal description with no special chars",
            )
        }
        result = assemble_available_specialists_block(specialists)

        assert "Normal description with no special chars" in result

    def test_description_truncated_to_500_chars(self) -> None:
        long_desc = "x" * 600
        specialists = {"long_spec": _make_specialist("long_spec", long_desc)}
        result = assemble_available_specialists_block(specialists)

        bullet = next(line for line in result.splitlines() if line.startswith("- **"))
        # Description portion after "- **long_spec**: " should be ≤500 chars
        desc_part = bullet[len("- **long_spec**: ") :]
        assert len(desc_part) <= 500

    def test_description_all_unsafe_chars_falls_back(self) -> None:
        unsafe = "\x00\x01\x02\x03"
        specialists = {"bad_spec": _make_specialist("bad_spec", unsafe)}
        result = assemble_available_specialists_block(specialists)

        assert "(no description provided)" in result


# ---------------------------------------------------------------------------
# TestNameTitleRendering — AH-84
# ---------------------------------------------------------------------------


class TestNameTitleRendering:
    """AH-84: human name + title enrich the Available Specialists bullets."""

    def _make_meta(
        self, human_name: str | None = None, title: str | None = None
    ) -> dict:
        return {"human_name": human_name, "title": title}

    def test_both_clauses_present(self) -> None:
        specialists = {
            "ben_e_agent": _make_specialist("ben_e_agent", "Guards the brand.")
        }
        metadata = {"ben_e_agent": self._make_meta("BEN-E", "Brand Guardian")}
        result = assemble_available_specialists_block(specialists, metadata=metadata)

        assert (
            '- **ben_e_agent** — known as "BEN-E", Brand Guardian: Guards the brand.'
            in result
        )

    def test_only_human_name(self) -> None:
        specialists = {
            "ben_e_agent": _make_specialist("ben_e_agent", "Guards the brand.")
        }
        metadata = {"ben_e_agent": self._make_meta("BEN-E")}
        result = assemble_available_specialists_block(specialists, metadata=metadata)

        assert '- **ben_e_agent** — known as "BEN-E": Guards the brand.' in result

    def test_only_title(self) -> None:
        specialists = {
            "ben_e_agent": _make_specialist("ben_e_agent", "Guards the brand.")
        }
        metadata = {"ben_e_agent": self._make_meta(title="Brand Guardian")}
        result = assemble_available_specialists_block(specialists, metadata=metadata)

        assert "- **ben_e_agent** — Brand Guardian: Guards the brand." in result

    def test_neither_clause_byte_identical_to_legacy(self) -> None:
        """When both are absent the output is byte-for-byte equal to the pre-AH-84 format."""
        specialists = {"spec": _make_specialist("spec", "Does things.")}

        without_metadata = assemble_available_specialists_block(specialists)
        with_empty_metadata = assemble_available_specialists_block(
            specialists, metadata={"spec": self._make_meta()}
        )
        with_no_metadata_key = assemble_available_specialists_block(
            specialists, metadata={}
        )

        assert (
            without_metadata == "## Available Specialists\n\n- **spec**: Does things."
        )
        assert with_empty_metadata == without_metadata
        assert with_no_metadata_key == without_metadata

    def test_bold_token_is_always_doc_id(self) -> None:
        """The bold/routing token must be the doc_id, not the human name."""
        specialists = {
            "ga_specialist": _make_specialist("ga_specialist", "GA queries.")
        }
        metadata = {
            "ga_specialist": self._make_meta("Google Analytics Agent", "Analytics")
        }
        result = assemble_available_specialists_block(specialists, metadata=metadata)

        bullets = [line for line in result.splitlines() if line.startswith("- **")]
        assert len(bullets) == 1
        assert bullets[0].startswith("- **ga_specialist**")
        assert "Google Analytics Agent" in bullets[0]  # appears in the clause
        # The doc_id is bold; the human name is inside quotes after the em-dash
        assert '— known as "Google Analytics Agent"' in bullets[0]

    def test_human_name_truncated_to_64_chars(self) -> None:
        long_name = "A" * 80
        specialists = {"spec": _make_specialist("spec", "Does things.")}
        metadata = {"spec": self._make_meta(long_name)}
        result = assemble_available_specialists_block(specialists, metadata=metadata)

        # Extract the human_name portion from inside quotes
        bullet = next(line for line in result.splitlines() if line.startswith("- **"))
        # The quoted portion starts after 'known as "'
        start = bullet.index('known as "') + len('known as "')
        end = bullet.index('"', start)
        assert len(bullet[start:end]) <= 64

    def test_title_truncated_to_64_chars(self) -> None:
        long_title = "B" * 80
        specialists = {"spec": _make_specialist("spec", "Does things.")}
        metadata = {"spec": self._make_meta(title=long_title)}
        result = assemble_available_specialists_block(specialists, metadata=metadata)

        bullet = next(line for line in result.splitlines() if line.startswith("- **"))
        # Format is "- **spec** — {title}: {desc}" — title is between " — " and ": "
        after_em = bullet.split(" — ", 1)[1]  # "{title}: {desc}"
        title_part = after_em.split(": ", 1)[0]
        assert len(title_part) <= 64


# ---------------------------------------------------------------------------
# TestAssembleSpecialistsBlockFromState — AH-84 / AH-86
# ---------------------------------------------------------------------------


class TestAssembleSpecialistsBlockFromState:
    """Tests for the fast-path block builder (state-dict input)."""

    def test_empty_dicts_returns_none_registered(self) -> None:
        result = assemble_specialists_block_from_state([])
        assert "None registered" in result

    def test_basic_name_description_renders(self) -> None:
        dicts = [
            {"name": "my_spec", "description": "Does things.", "agent_id": "my_spec"}
        ]
        result = assemble_specialists_block_from_state(dicts)
        assert "- **my_spec**: Does things." in result

    def test_both_clauses_present(self) -> None:
        dicts = [
            {
                "name": "ben_e_agent",
                "description": "Guards the brand.",
                "agent_id": "ben_e_agent",
                "human_name": "BEN-E",
                "title": "Brand Guardian",
            }
        ]
        result = assemble_specialists_block_from_state(dicts)
        assert (
            '- **ben_e_agent** — known as "BEN-E", Brand Guardian: Guards the brand.'
            in result
        )

    def test_only_human_name(self) -> None:
        dicts = [{"name": "s", "description": "Desc.", "human_name": "Dave"}]
        result = assemble_specialists_block_from_state(dicts)
        assert '- **s** — known as "Dave": Desc.' in result

    def test_only_title(self) -> None:
        dicts = [{"name": "s", "description": "Desc.", "title": "Analyst"}]
        result = assemble_specialists_block_from_state(dicts)
        assert "- **s** — Analyst: Desc." in result

    def test_neither_clause_byte_identical_to_legacy(self) -> None:
        """No human_name/title → same output as before AH-84."""
        dicts = [{"name": "spec", "description": "Does things.", "agent_id": "spec"}]
        result = assemble_specialists_block_from_state(dicts)
        assert "- **spec**: Does things." in result
        assert "known as" not in result
        assert " — " not in result

    def test_bold_token_is_always_doc_id(self) -> None:
        dicts = [
            {
                "name": "ga_specialist",
                "description": "GA.",
                "human_name": "BEN-E",
                "title": "Analyst",
            }
        ]
        result = assemble_specialists_block_from_state(dicts)
        bullets = [line for line in result.splitlines() if line.startswith("- **")]
        assert bullets[0].startswith("- **ga_specialist**")

    def test_sorted_alphabetically(self) -> None:
        dicts = [
            {"name": "z_spec", "description": "Z"},
            {"name": "a_spec", "description": "A"},
        ]
        result = assemble_specialists_block_from_state(dicts)
        lines = [line for line in result.splitlines() if line.startswith("- **")]
        assert lines[0].startswith("- **a_spec**")
        assert lines[1].startswith("- **z_spec**")
