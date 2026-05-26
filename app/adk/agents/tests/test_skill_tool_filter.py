"""Unit tests for app.adk.agents.skill_tool_filter.

All tests are pure — no ADK fixtures, no I/O, no GCP calls.
Fake tool objects are constructed with SimpleNamespace so they carry a
.name attribute matching the contract expected by restrict_tools_for_skill
and skill_allowed_tools_before_tool_callback.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.adk.agents.skill_tool_filter import (
    _tool_name_matches,
    parse_allowed_tools,
    restrict_tools_for_skill,
    skill_allowed_tools_before_tool_callback,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tool(name: str) -> SimpleNamespace:
    """Create a minimal fake tool with a .name attribute."""
    return SimpleNamespace(name=name)


def _make_context(state: dict[str, Any]) -> MagicMock:
    ctx = MagicMock()
    ctx.state = state
    return ctx


# ---------------------------------------------------------------------------
# parse_allowed_tools
# ---------------------------------------------------------------------------


class TestParseAllowedTools:
    def test_none_returns_none(self) -> None:
        assert parse_allowed_tools(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert parse_allowed_tools("") is None

    def test_whitespace_only_returns_none(self) -> None:
        assert parse_allowed_tools("   ") is None

    def test_single_token(self) -> None:
        result = parse_allowed_tools("Read")
        assert result == {"Read"}

    def test_multiple_tokens(self) -> None:
        result = parse_allowed_tools("Read Bash(git:*)")
        assert result == {"Read", "Bash(git:*)"}

    def test_extra_whitespace_is_tolerated(self) -> None:
        result = parse_allowed_tools("  Read   Bash(git:*)  ")
        assert result == {"Read", "Bash(git:*)"}

    def test_returns_set_not_list(self) -> None:
        result = parse_allowed_tools("Read Write")
        assert isinstance(result, set)

    def test_duplicate_tokens_deduplicated(self) -> None:
        result = parse_allowed_tools("Read Read")
        assert result == {"Read"}


# ---------------------------------------------------------------------------
# _tool_name_matches
# ---------------------------------------------------------------------------


class TestToolNameMatches:
    def test_exact_match_returns_true(self) -> None:
        assert _tool_name_matches("Read", "Read") is True

    def test_exact_no_match_returns_false(self) -> None:
        assert _tool_name_matches("Write", "Read") is False

    def test_suffix_glob_matches_prefix(self) -> None:
        assert _tool_name_matches("Bash(git:status)", "Bash(git:*)") is True

    def test_suffix_glob_does_not_match_other_prefix(self) -> None:
        assert _tool_name_matches("Bash(jq:keys)", "Bash(git:*)") is False

    def test_bare_star_matches_any_tool(self) -> None:
        assert _tool_name_matches("AnythingAtAll", "*") is True

    def test_glob_requires_full_prefix_before_star(self) -> None:
        assert _tool_name_matches("ReadExtra", "Read*") is True
        assert _tool_name_matches("OtherTool", "Read*") is False

    def test_exact_match_case_sensitive(self) -> None:
        assert _tool_name_matches("read", "Read") is False

    def test_glob_on_empty_suffix(self) -> None:
        # "Bash(*" means: tool name must start with "Bash("
        assert _tool_name_matches("Bash(git:status)", "Bash(*") is True
        assert _tool_name_matches("Write", "Bash(*") is False


# ---------------------------------------------------------------------------
# restrict_tools_for_skill
# ---------------------------------------------------------------------------


class TestRestrictToolsForSkill:
    def test_none_allowed_returns_all_tools_unchanged(self) -> None:
        tools = [_tool("Read"), _tool("Write"), _tool("Edit")]
        result = restrict_tools_for_skill(tools, None)
        assert result == tools

    def test_empty_set_returns_empty_list(self) -> None:
        tools = [_tool("Read"), _tool("Write")]
        result = restrict_tools_for_skill(tools, set())
        assert result == []

    def test_single_exact_match_returns_only_that_tool(self) -> None:
        read, write, edit = _tool("Read"), _tool("Write"), _tool("Edit")
        result = restrict_tools_for_skill([read, write, edit], {"Read"})
        assert result == [read]

    def test_multiple_exact_matches_preserved(self) -> None:
        read, write = _tool("Read"), _tool("Write")
        result = restrict_tools_for_skill([read, write], {"Read", "Write"})
        assert {r.name for r in result} == {"Read", "Write"}

    def test_restriction_cannot_grant_absent_tool(self) -> None:
        read = _tool("Read")
        result = restrict_tools_for_skill([read], {"NonExistent"})
        assert result == []

    def test_nonexistent_in_allowed_only_returns_empty(self) -> None:
        result = restrict_tools_for_skill([_tool("Read")], {"NonexistentTool"})
        assert result == []

    def test_glob_match_filters_correctly(self) -> None:
        bash_git = _tool("Bash(git:status)")
        bash_jq = _tool("Bash(jq:keys)")
        result = restrict_tools_for_skill([bash_git, bash_jq], {"Bash(git:*)"})
        assert result == [bash_git]

    def test_order_of_tools_is_preserved(self) -> None:
        t1, t2, t3 = _tool("A"), _tool("B"), _tool("C")
        result = restrict_tools_for_skill([t1, t2, t3], {"A", "C"})
        assert [r.name for r in result] == ["A", "C"]

    def test_empty_agent_tools_returns_empty_list(self) -> None:
        assert restrict_tools_for_skill([], {"Read"}) == []

    def test_empty_agent_tools_with_none_returns_empty_list(self) -> None:
        assert restrict_tools_for_skill([], None) == []


# ---------------------------------------------------------------------------
# skill_allowed_tools_before_tool_callback
# ---------------------------------------------------------------------------


class TestSkillAllowedToolsCallback:
    """Tests for the ADK-shaped async callback."""

    @pytest.mark.asyncio
    async def test_no_active_skill_returns_none(self) -> None:
        tool = _tool("Read")
        ctx = _make_context({})
        result = await skill_allowed_tools_before_tool_callback(tool, {}, ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_active_skill_id_none_returns_none(self) -> None:
        tool = _tool("Read")
        ctx = _make_context({"active_skill_id": None})
        result = await skill_allowed_tools_before_tool_callback(tool, {}, ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_active_skill_allowed_tool_returns_none(self) -> None:
        tool = _tool("Read")
        ctx = _make_context(
            {
                "active_skill_id": "sk_x",
                "skills_allowed_tools": {"sk_x": ["Read"]},
            }
        )
        result = await skill_allowed_tools_before_tool_callback(tool, {}, ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_active_skill_disallowed_tool_returns_error_dict(self) -> None:
        tool = _tool("Write")
        ctx = _make_context(
            {
                "active_skill_id": "sk_x",
                "skills_allowed_tools": {"sk_x": ["Read"]},
            }
        )
        result = await skill_allowed_tools_before_tool_callback(tool, {}, ctx)
        assert result is not None
        assert result["error"] == "tool_restricted_by_skill"
        assert result["tool_name"] == "Write"
        assert result["active_skill_id"] == "sk_x"

    @pytest.mark.asyncio
    async def test_allowed_tools_never_grants_absent_tool(self) -> None:
        """AC-7: restriction cannot add a tool not already on the agent."""
        tool = _tool("Read")
        ctx = _make_context(
            {
                "active_skill_id": "sk_x",
                "skills_allowed_tools": {"sk_x": ["NonexistentTool"]},
            }
        )
        result = await skill_allowed_tools_before_tool_callback(tool, {}, ctx)
        assert result is not None
        assert result["error"] == "tool_restricted_by_skill"

    @pytest.mark.asyncio
    async def test_missing_skills_allowed_tools_degrades_open(self, caplog) -> None:
        tool = _tool("Read")
        ctx = _make_context({"active_skill_id": "sk_x"})
        with caplog.at_level(
            logging.WARNING, logger="app.adk.agents.skill_tool_filter"
        ):
            result = await skill_allowed_tools_before_tool_callback(tool, {}, ctx)
        assert result is None
        assert any("degrading open" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_skill_id_missing_from_map_degrades_open(self) -> None:
        tool = _tool("Read")
        ctx = _make_context(
            {
                "active_skill_id": "sk_x",
                "skills_allowed_tools": {},  # no entry for sk_x
            }
        )
        # Missing entry in map → degrade open (None value = no frontmatter)
        # An empty dict means sk_x has no entry → we degrade open
        result = await skill_allowed_tools_before_tool_callback(tool, {}, ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_skill_none_value_means_no_restriction(self) -> None:
        """None value in the map means the skill has no allowed-tools frontmatter."""
        tool = _tool("Write")
        ctx = _make_context(
            {
                "active_skill_id": "sk_x",
                "skills_allowed_tools": {"sk_x": None},
            }
        )
        result = await skill_allowed_tools_before_tool_callback(tool, {}, ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_list_value_blocks_all_tools(self) -> None:
        """Explicit empty list = block everything."""
        tool = _tool("Read")
        ctx = _make_context(
            {
                "active_skill_id": "sk_x",
                "skills_allowed_tools": {"sk_x": []},
            }
        )
        result = await skill_allowed_tools_before_tool_callback(tool, {}, ctx)
        assert result is not None
        assert result["error"] == "tool_restricted_by_skill"

    @pytest.mark.asyncio
    async def test_no_state_attribute_degrades_open(self) -> None:
        """Callback must not crash if tool_context has no state."""
        tool = _tool("Read")
        ctx = object()  # no .state at all
        result = await skill_allowed_tools_before_tool_callback(tool, {}, ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_glob_pattern_in_allowed_tools_matches_correctly(self) -> None:
        bash_git = _tool("Bash(git:status)")
        ctx = _make_context(
            {
                "active_skill_id": "sk_x",
                "skills_allowed_tools": {"sk_x": ["Bash(git:*)"]},
            }
        )
        result = await skill_allowed_tools_before_tool_callback(bash_git, {}, ctx)
        assert result is None  # allowed

    @pytest.mark.asyncio
    async def test_glob_pattern_blocks_non_matching_tool(self) -> None:
        bash_jq = _tool("Bash(jq:keys)")
        ctx = _make_context(
            {
                "active_skill_id": "sk_x",
                "skills_allowed_tools": {"sk_x": ["Bash(git:*)"]},
            }
        )
        result = await skill_allowed_tools_before_tool_callback(bash_jq, {}, ctx)
        assert result is not None
        assert result["error"] == "tool_restricted_by_skill"
