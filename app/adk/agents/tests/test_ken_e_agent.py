"""Test KEN-E agent routing."""

from ..ken_e_agent import create_ken_e_agent


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


def test_ken_e_instructions_include_routing():
    """Test agent instructions include routing information."""
    agent = create_ken_e_agent()

    # Check for key instruction components
    assert "KEN-E" in agent.instruction
    assert "Company News" in agent.instruction
    assert "Google Analytics" in agent.instruction
    assert "search_company_news" in agent.instruction
    assert "query_google_analytics" in agent.instruction

    # Check that strategy documents note is included
    assert "Strategy documents are automatically generated" in agent.instruction
