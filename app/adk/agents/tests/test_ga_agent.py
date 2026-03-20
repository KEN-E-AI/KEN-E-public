"""Tests for Google Analytics agent Firestore config loading."""

import importlib
from unittest.mock import patch

from google.adk.agents.llm_agent_config import LlmAgentConfig

# Import the module directly (bypass __init__.py's __getattr__ which returns the agent instance)
ga_module = importlib.import_module("app.adk.agents.google_analytics_agent_v4")

GA_AGENT_INSTRUCTION = ga_module.GA_AGENT_INSTRUCTION
create_google_analytics_agent = ga_module.create_google_analytics_agent


@patch.object(ga_module, "load_config_from_firestore")
def test_ga_agent_firestore_config_applied(mock_load):
    """Firestore config fields are applied to the GA Agent."""
    mock_config = LlmAgentConfig(
        name="google_analytics_agent",
        model="gemini-2.5-pro",
        instruction="Custom GA instruction",
        description="Custom GA description",
        generate_content_config={"temperature": 0.5, "max_output_tokens": 8192},
    )
    mock_load.return_value = (mock_config, {"version": "v2.0"})

    agent = create_google_analytics_agent()

    assert agent.name == "google_analytics_agent_v4"
    assert agent.model == "gemini-2.5-pro"
    assert agent.instruction == "Custom GA instruction"
    assert agent.description == "Custom GA description"
    assert agent.generate_content_config is not None


@patch.object(ga_module, "load_config_from_firestore")
def test_ga_agent_fallback_on_failure(mock_load):
    """GA agent uses hardcoded defaults when Firestore loading fails."""
    mock_load.side_effect = Exception("Firestore unavailable")

    agent = create_google_analytics_agent()

    assert agent.name == "google_analytics_agent_v4"
    assert agent.model == "gemini-2.0-flash"
    assert agent.instruction == GA_AGENT_INSTRUCTION
    assert agent.description == ""


@patch.object(ga_module, "load_config_from_firestore")
def test_ga_agent_uses_fallback_instruction_when_config_instruction_empty(mock_load):
    """When Firestore config has empty instruction, falls back to hardcoded."""
    mock_config = LlmAgentConfig(
        name="google_analytics_agent",
        model="gemini-2.5-flash",
        instruction="",
    )
    mock_load.return_value = (mock_config, {"version": "v1.0"})

    agent = create_google_analytics_agent()

    assert agent.instruction == GA_AGENT_INSTRUCTION
