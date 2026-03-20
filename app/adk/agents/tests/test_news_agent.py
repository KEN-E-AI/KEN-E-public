"""Tests for Company News agent Firestore config loading."""

import os

# Set required env vars before importing the news agent module
# (module-level code in agent.py checks these at import time)
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project")
os.environ.setdefault("VERTEX_AI_NEWS_DATASTORE_ID", "test-datastore")

from unittest.mock import patch

from google.adk.agents.llm_agent_config import LlmAgentConfig

from ..company_news_chatbot.agent import (
    NEWS_AGENT_INSTRUCTION,
    create_main_agent,
)


@patch("app.adk.agents.company_news_chatbot.agent.VertexAiSearchTool")
@patch("app.adk.agents.strategy_agent.config_loader.load_config_from_firestore")
def test_news_agent_firestore_config_applied(mock_load, mock_search_tool):
    """Firestore config fields are applied to the News Agent."""
    mock_config = LlmAgentConfig(
        name="company_news_agent",
        model="gemini-2.5-pro",
        instruction="Custom news instruction",
        description="Custom news description",
        generate_content_config={"temperature": 0.5, "max_output_tokens": 8192},
    )
    mock_load.return_value = (mock_config, {"version": "v2.0"})

    agent = create_main_agent()

    assert agent.name == "company_news_chatbot"
    assert agent.model == "gemini-2.5-pro"
    assert agent.instruction == "Custom news instruction"
    assert agent.description == "Custom news description"
    assert agent.generate_content_config is not None


@patch("app.adk.agents.company_news_chatbot.agent.VertexAiSearchTool")
@patch("app.adk.agents.strategy_agent.config_loader.load_config_from_firestore")
def test_news_agent_fallback_on_failure(mock_load, mock_search_tool):
    """News agent uses hardcoded defaults when Firestore loading fails."""
    mock_load.side_effect = Exception("Firestore unavailable")

    agent = create_main_agent()

    assert agent.name == "company_news_chatbot"
    assert agent.model == "gemini-2.0-flash"
    assert agent.instruction == NEWS_AGENT_INSTRUCTION
    assert agent.description == ""


@patch("app.adk.agents.company_news_chatbot.agent.VertexAiSearchTool")
@patch("app.adk.agents.strategy_agent.config_loader.load_config_from_firestore")
def test_news_agent_uses_fallback_instruction_when_config_instruction_empty(
    mock_load, mock_search_tool
):
    """When Firestore config has empty instruction, falls back to hardcoded."""
    mock_config = LlmAgentConfig(
        name="company_news_agent",
        model="gemini-2.5-flash",
        instruction="",
    )
    mock_load.return_value = (mock_config, {"version": "v1.0"})

    agent = create_main_agent()

    assert agent.instruction == NEWS_AGENT_INSTRUCTION
