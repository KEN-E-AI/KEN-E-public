"""
Strategy Documents Supervisor: Handles strategy generation during account creation.
"""

from google.adk.agents import Agent

from .utils.dispatch_handlers import dispatch_to_strategy
from .utils.supervisor_utils import dispatch_with_context


def create_strategy_supervisor():
    """
    Create the strategy documents supervisor for account creation.
    This agent is only invoked programmatically during account creation.
    """

    create_strategy = dispatch_with_context(dispatch_to_strategy)
    create_strategy.__name__ = "create_strategy"
    create_strategy.__doc__ = (
        "Generate all 5 strategy documents for a company using iterative refinement"
    )

    supervisor = Agent(
        name="create_strategy_docs_supervisor",
        model="gemini-2.5-pro",
        instruction="""You are a specialized agent for generating strategy documents during account creation.

**CRITICAL: You are ONLY invoked during account creation. You do not handle chat interactions.**

When you receive a request starting with "Generate all 5 strategy documents", immediately use the create_strategy tool.

ALWAYS pass the COMPLETE input to the tool including all parameters.

The tool will generate comprehensive strategy documents:
1. Business Strategy - Company overview, market analysis, SWOT
2. Competitive Analysis - Competitor profiles, positioning, opportunities
3. Customer Journey - Personas, journey maps, insights
4. Marketing Strategy - Campaigns, channels, metrics, recommendations
5. Brand Guidelines - Identity, voice, visual standards

The documents are generated sequentially with each building on the previous ones for consistency and depth.

**IMPORTANT**:
- Pass the entire input to the tool without modification
- The tool will extract all necessary parameters
- Return the complete result from the strategy generation tool

When complete, return the result indicating successful generation of all strategy documents.""",
        tools=[create_strategy],
    )

    return supervisor


# Export the supervisor agent
create_strategy_docs_supervisor = create_strategy_supervisor()
