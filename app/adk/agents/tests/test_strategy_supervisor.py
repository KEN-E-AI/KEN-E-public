"""Test strategy supervisor agent."""

from ..create_strategy_docs_supervisor import create_strategy_supervisor


def test_strategy_supervisor_has_only_strategy_tool():
    """Test that strategy supervisor only has strategy tool."""
    agent = create_strategy_supervisor()
    tool_names = [tool.__name__ for tool in agent.tools]

    assert "create_strategy" in tool_names
    assert len(tool_names) == 1  # Only one tool
    assert "search_company_news" not in tool_names  # Should NOT have news tool
    assert "query_google_analytics" not in tool_names  # Should NOT have analytics tool


def test_strategy_supervisor_name():
    """Test agent has correct name."""
    agent = create_strategy_supervisor()
    assert agent.name == "create_strategy_docs_supervisor"


def test_strategy_supervisor_model():
    """Test agent uses correct model."""
    agent = create_strategy_supervisor()
    assert agent.model == "gemini-2.0-flash"


def test_strategy_supervisor_instructions():
    """Test agent instructions are specific to strategy generation."""
    agent = create_strategy_supervisor()

    # Check for key instruction components
    assert "strategy documents during account creation" in agent.instruction
    assert "Generate all 5 strategy documents" in agent.instruction
    assert "create_strategy tool" in agent.instruction

    # Check that all 5 document types are mentioned
    assert "Business Strategy" in agent.instruction
    assert "Competitive Analysis" in agent.instruction
    assert "Customer Journey" in agent.instruction
    assert "Marketing Strategy" in agent.instruction
    assert "Brand Guidelines" in agent.instruction

    # Check that it's clear this is NOT for chat
    assert "ONLY invoked during account creation" in agent.instruction
    assert "do not handle chat interactions" in agent.instruction
