"""Unit tests for KEN-E InstructionProvider (build_ken_e_instruction).

Tests that org context from session state is correctly injected into
the agent's system prompt, and that the callable degrades gracefully
when no context is available.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Mock neo4j before any agent imports
neo4j_mock = MagicMock()
neo4j_mock.exceptions = MagicMock()
neo4j_mock.exceptions.ServiceUnavailable = Exception
neo4j_mock.exceptions.SessionExpired = Exception
sys.modules.setdefault("neo4j", neo4j_mock)
sys.modules.setdefault("neo4j.exceptions", neo4j_mock.exceptions)

# Add app directory to path
app_dir = Path(__file__).parents[3] / "app"
sys.path.insert(0, str(app_dir))

from adk.agents.ken_e_agent import (  # noqa: E402
    _BASE_INSTRUCTION,
    build_ken_e_instruction,
)


def _make_context(state: dict) -> MagicMock:
    """Create a mock ReadonlyContext with given state."""
    ctx = MagicMock()
    ctx.state = state
    return ctx


class TestBuildKenEInstruction:
    """Tests for build_ken_e_instruction InstructionProvider callable."""

    def test_returns_base_instruction_when_no_org_context(self):
        """Without org context in state, returns base instruction only."""
        ctx = _make_context({})
        assert build_ken_e_instruction(ctx) == _BASE_INSTRUCTION

    def test_returns_base_instruction_when_org_context_is_none(self):
        """With None org context, returns base instruction only."""
        ctx = _make_context({"organization_context": None})
        assert build_ken_e_instruction(ctx) == _BASE_INSTRUCTION

    def test_returns_base_instruction_when_org_context_is_empty(self):
        """With empty string, returns base instruction only."""
        ctx = _make_context({"organization_context": ""})
        assert build_ken_e_instruction(ctx) == _BASE_INSTRUCTION

    def test_prepends_org_context_when_present(self):
        """With org context, prepends it with delimiters before base instruction."""
        org_context = "# Acme Corp\nIndustry: Tech\n**Tone:** Professional"
        ctx = _make_context({"organization_context": org_context})
        result = build_ken_e_instruction(ctx)

        expected = f"[ORGANIZATION CONTEXT]\n{org_context}\n[END CONTEXT]\n\n{_BASE_INSTRUCTION}"
        assert result == expected

    def test_org_context_with_curly_braces_preserved(self):
        """Curly braces in org context are NOT interpolated (InstructionProvider bypasses templates)."""
        org_context = "Revenue: {confidential} | Format: {custom}"
        ctx = _make_context({"organization_context": org_context})
        result = build_ken_e_instruction(ctx)

        assert "{confidential}" in result
        assert "{custom}" in result

    def test_unrelated_state_keys_ignored(self):
        """Other state keys don't affect instruction generation."""
        ctx = _make_context(
            {
                "ga_credentials": {"access_token": "secret"},
                "account_id": "acc_123",
            }
        )
        assert build_ken_e_instruction(ctx) == _BASE_INSTRUCTION

    def test_context_appears_before_instruction(self):
        """Organization context block precedes the base instruction."""
        ctx = _make_context({"organization_context": "test context"})
        result = build_ken_e_instruction(ctx)

        context_end = result.index("[END CONTEXT]")
        instruction_start = result.index("You are KEN-E")
        assert context_end < instruction_start


class TestBaseInstruction:
    """Tests for the _BASE_INSTRUCTION constant."""

    def test_contains_routing_info(self):
        """Base instruction includes all key routing components."""
        assert "KEN-E" in _BASE_INSTRUCTION
        assert "search_company_news" in _BASE_INSTRUCTION
        assert "query_google_analytics" in _BASE_INSTRUCTION

    def test_contains_capability_sections(self):
        """Base instruction describes both capabilities."""
        assert "Company News" in _BASE_INSTRUCTION
        assert "Google Analytics" in _BASE_INSTRUCTION

    def test_contains_strategy_note(self):
        """Base instruction includes strategy document explanation."""
        assert "Strategy documents are automatically generated" in _BASE_INSTRUCTION

    def test_no_hardcoded_org_context_reference(self):
        """Base instruction doesn't say 'every message includes' context."""
        assert "Every message includes [ORGANIZATION CONTEXT]" not in _BASE_INSTRUCTION
