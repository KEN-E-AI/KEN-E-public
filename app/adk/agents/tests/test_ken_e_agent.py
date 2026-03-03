"""Test KEN-E agent routing and InstructionProvider."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from ..ken_e_agent import _BASE_INSTRUCTION, build_ken_e_instruction, create_ken_e_agent


def test_ken_e_has_correct_tools():
    """Test that KEN-E only has news and analytics tools."""
    agent = create_ken_e_agent()
    tool_names = [tool.__name__ for tool in agent.tools]

    assert "search_company_news" in tool_names
    assert "query_google_analytics" in tool_names
    assert "create_strategy" not in tool_names  # Should NOT have strategy tool
    assert len(tool_names) == 2  # Only two tools


def test_ken_e_agent_name():
    """Test agent has correct name."""
    agent = create_ken_e_agent()
    assert agent.name == "ken_e"


def test_ken_e_agent_model():
    """Test agent uses correct model."""
    agent = create_ken_e_agent()
    assert agent.model == "gemini-2.0-flash"


def test_ken_e_instruction_is_callable():
    """Test agent instruction is a callable (InstructionProvider pattern)."""
    agent = create_ken_e_agent()
    assert callable(agent.instruction)
    assert agent.instruction is build_ken_e_instruction


class TestBuildKenEInstruction:
    """Tests for the build_ken_e_instruction InstructionProvider callable."""

    def _make_context(self, state: dict) -> MagicMock:
        """Create a mock ReadonlyContext with given state."""
        ctx = MagicMock()
        ctx.state = state
        return ctx

    def test_returns_base_instruction_when_no_org_context(self):
        """Without org context in state, returns base instruction only."""
        ctx = self._make_context({})
        result = build_ken_e_instruction(ctx)
        assert result == _BASE_INSTRUCTION

    def test_returns_base_instruction_when_org_context_is_none(self):
        """With None org context in state, returns base instruction only."""
        ctx = self._make_context({"organization_context": None})
        result = build_ken_e_instruction(ctx)
        assert result == _BASE_INSTRUCTION

    def test_returns_base_instruction_when_org_context_is_empty(self):
        """With empty string org context in state, returns base instruction only."""
        ctx = self._make_context({"organization_context": ""})
        result = build_ken_e_instruction(ctx)
        assert result == _BASE_INSTRUCTION

    def test_prepends_org_context_when_present(self):
        """With org context in state, prepends it before base instruction."""
        org_context = "# Acme Corp\nIndustry: Tech\n**Tone:** Professional"
        ctx = self._make_context({"organization_context": org_context})
        result = build_ken_e_instruction(ctx)

        assert result.startswith("[ORGANIZATION CONTEXT]")
        assert org_context in result
        assert "[END CONTEXT]" in result
        assert _BASE_INSTRUCTION in result
        # Context comes before instruction
        assert result.index("[ORGANIZATION CONTEXT]") < result.index(_BASE_INSTRUCTION)

    def test_org_context_with_curly_braces_not_interpolated(self):
        """Org context containing curly braces is preserved literally."""
        org_context = "Revenue: {confidential} | Format: {custom}"
        ctx = self._make_context({"organization_context": org_context})
        result = build_ken_e_instruction(ctx)

        assert "{confidential}" in result
        assert "{custom}" in result

    def test_base_instruction_contains_routing_info(self):
        """Base instruction includes all key routing components."""
        assert "KEN-E" in _BASE_INSTRUCTION
        assert "Company News" in _BASE_INSTRUCTION
        assert "Google Analytics" in _BASE_INSTRUCTION
        assert "search_company_news" in _BASE_INSTRUCTION
        assert "query_google_analytics" in _BASE_INSTRUCTION
        assert "Strategy documents are automatically generated" in _BASE_INSTRUCTION

    def test_ignores_unrelated_state_keys(self):
        """Other state keys don't affect instruction generation."""
        ctx = self._make_context({
            "ga_credentials": {"access_token": "secret"},
            "account_id": "acc_123",
        })
        result = build_ken_e_instruction(ctx)
        assert result == _BASE_INSTRUCTION
