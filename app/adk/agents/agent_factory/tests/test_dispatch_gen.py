"""Unit tests for app.adk.agents.agent_factory.dispatch.

The ``generate_dispatch_functions`` / ``_build_dispatch`` symbols were deleted
in AH-66 (confirmed zero non-test production callers).  Only
``assemble_available_specialists_block`` remains; this file now covers that
public symbol exclusively.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.adk.agents.agent_factory.dispatch import (
    assemble_available_specialists_block,
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
        desc_part = bullet[len("- **long_spec**: "):]
        assert len(desc_part) <= 500

    def test_description_all_unsafe_chars_falls_back(self) -> None:
        unsafe = "\x00\x01\x02\x03"
        specialists = {"bad_spec": _make_specialist("bad_spec", unsafe)}
        result = assemble_available_specialists_block(specialists)

        assert "(no description provided)" in result
