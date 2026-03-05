"""Test KEN-E agent routing and InstructionProvider."""

import importlib
from unittest.mock import MagicMock, patch

from google.adk.agents.llm_agent_config import LlmAgentConfig

# Import the module directly (bypass __init__.py's __getattr__ which returns the agent instance)
ken_e_module = importlib.import_module("app.adk.agents.ken_e_agent")

_BASE_INSTRUCTION = ken_e_module._BASE_INSTRUCTION
build_ken_e_instruction = ken_e_module.build_ken_e_instruction
_make_instruction_provider = ken_e_module._make_instruction_provider
create_ken_e_agent = ken_e_module.create_ken_e_agent


def test_ken_e_has_correct_tools():
    """Test that KEN-E only has news and analytics tools."""
    agent = create_ken_e_agent()
    tool_names = [tool.__name__ for tool in agent.tools]

    assert "search_company_news" in tool_names
    assert "query_google_analytics" in tool_names
    assert "create_strategy" not in tool_names  # Should NOT have strategy tool
    assert len(tool_names) == 2  # Only two tools


def test_ken_e_agent_name():
    """Test agent has correct name regardless of config."""
    agent = create_ken_e_agent()
    assert agent.name == "ken_e"


def test_ken_e_instruction_is_callable():
    """Test agent instruction is a callable (InstructionProvider pattern)."""
    agent = create_ken_e_agent()
    assert callable(agent.instruction)


@patch.object(ken_e_module, "load_config_from_firestore")
def test_firestore_config_applied(mock_load):
    """Firestore config fields are applied to the Agent."""
    mock_config = LlmAgentConfig(
        name="ken_e_chatbot",
        model="gemini-2.5-pro",
        instruction="Custom instruction from Firestore",
        description="Custom description",
        generate_content_config={"temperature": 0.3, "max_output_tokens": 2048},
    )
    mock_load.return_value = (mock_config, {"version": "v2.0"})

    agent = create_ken_e_agent()

    assert agent.model == "gemini-2.5-pro"
    assert agent.description == "Custom description"
    assert agent.generate_content_config is not None
    # Instruction should be a callable that uses the Firestore instruction
    assert callable(agent.instruction)
    ctx = MagicMock()
    ctx.state = {}
    result = agent.instruction(ctx)
    assert result == "Custom instruction from Firestore"


@patch.object(ken_e_module, "load_config_from_firestore")
def test_firestore_fallback_on_failure(mock_load):
    """Agent uses hardcoded defaults when Firestore loading fails."""
    mock_load.side_effect = Exception("Firestore unavailable")

    agent = create_ken_e_agent()

    assert agent.model == "gemini-2.0-flash"
    assert agent.description == ""
    # Instruction should still be callable and use _BASE_INSTRUCTION
    assert callable(agent.instruction)
    ctx = MagicMock()
    ctx.state = {}
    result = agent.instruction(ctx)
    assert result == _BASE_INSTRUCTION


@patch.object(ken_e_module, "load_config_from_firestore")
def test_instruction_provider_uses_firestore_instruction(mock_load):
    """The closure-based instruction provider uses the loaded Firestore instruction, not _BASE_INSTRUCTION."""
    custom_instruction = "You are a custom KEN-E agent."
    mock_config = LlmAgentConfig(
        name="ken_e_chatbot",
        model="gemini-2.0-flash",
        instruction=custom_instruction,
    )
    mock_load.return_value = (mock_config, {"version": "v1.1"})

    agent = create_ken_e_agent()

    # Without org context — should return custom instruction
    ctx = MagicMock()
    ctx.state = {}
    assert agent.instruction(ctx) == custom_instruction

    # With org context — should prepend org context before custom instruction
    ctx.state = {"organization_context": "Acme Corp"}
    result = agent.instruction(ctx)
    assert "Acme Corp" in result
    assert custom_instruction in result
    assert _BASE_INSTRUCTION not in result


@patch.object(ken_e_module, "load_config_from_firestore")
def test_agent_name_stays_ken_e(mock_load):
    """Agent name must be 'ken_e' regardless of Firestore config."""
    mock_config = LlmAgentConfig(
        name="some_other_name",
        model="gemini-2.5-flash",
        instruction="Some instruction",
    )
    mock_load.return_value = (mock_config, {"version": "v1.0"})

    agent = create_ken_e_agent()
    assert agent.name == "ken_e"


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


class TestMakeInstructionProvider:
    """Tests for the _make_instruction_provider closure factory."""

    def _make_context(self, state: dict) -> MagicMock:
        ctx = MagicMock()
        ctx.state = state
        return ctx

    def test_returns_base_instruction_without_org_context(self):
        provider = _make_instruction_provider("Custom base")
        ctx = self._make_context({})
        assert provider(ctx) == "Custom base"

    def test_prepends_org_context(self):
        provider = _make_instruction_provider("Custom base")
        ctx = self._make_context({"organization_context": "Org info"})
        result = provider(ctx)
        assert "Org info" in result
        assert "Custom base" in result
        assert result.index("[ORGANIZATION CONTEXT]") < result.index("Custom base")

    def test_different_base_instructions_produce_different_providers(self):
        provider_a = _make_instruction_provider("Instruction A")
        provider_b = _make_instruction_provider("Instruction B")
        ctx = self._make_context({})
        assert provider_a(ctx) == "Instruction A"
        assert provider_b(ctx) == "Instruction B"
