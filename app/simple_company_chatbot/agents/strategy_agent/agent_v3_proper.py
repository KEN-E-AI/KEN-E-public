#!/usr/bin/env python3
"""
V3 Strategy Agent - Proper ADK SequentialAgent that uses EXISTING sub-agents.
This simply chains the 5 ALREADY IMPLEMENTED strategy agents together.
"""

import logging
from google.adk.agents import SequentialAgent
from vertexai.preview import reasoning_engines

# Import the EXISTING, PROPERLY IMPLEMENTED sub-agents
# Use absolute imports that will work when deployed
try:
    # Try absolute imports for deployment
    from agents.strategy_agent.sub_agents import (
        create_business_strategy_agent,
        create_competitive_strategy_agent,
        create_customer_strategy_agent,
        create_marketing_strategy_agent,
        create_brand_guidelines_agent
    )
    from agents.strategy_agent.models import StrategyContext
except ImportError:
    # Fall back to relative imports for local testing
    from .sub_agents import (
        create_business_strategy_agent,
        create_competitive_strategy_agent,
        create_customer_strategy_agent,
        create_marketing_strategy_agent,
        create_brand_guidelines_agent
    )
    from .models import StrategyContext

logger = logging.getLogger(__name__)

# Initialize W&B/Weave observability if available
try:
    import weave
    weave.init(project_name="ken-e-strategy-agent")
    logger.info("W&B observability initialized in agent_v3_proper")
except Exception as e:
    logger.warning(f"W&B initialization skipped in agent_v3_proper: {e}")


def create_v3_strategy_sequential_agent(context: StrategyContext) -> SequentialAgent:
    """
    Create the V3 strategy agent by chaining the 5 EXISTING strategy agents.
    
    Each of these agents already:
    - Uses the correct instructions from the Excel/V3 docs
    - Gets best practices and reviewer guidelines from Firestore
    - Has LoopAgent for reviewer-editor refinement
    - Properly passes context between agents via get_previous_outputs()
    
    Args:
        context: StrategyContext with company information
        
    Returns:
        SequentialAgent that runs all 5 strategy agents in sequence
    """
    
    logger.info(f"Creating V3 Sequential Agent for {context.company_name}")
    
    # Create all 5 strategy agents using the EXISTING implementations
    # Each of these already has the proper instructions, Firestore lookups, and refinement loops
    business_agent = create_business_strategy_agent(context)
    competitive_agent = create_competitive_strategy_agent(context)
    customer_agent = create_customer_strategy_agent(context)
    marketing_agent = create_marketing_strategy_agent(context)
    brand_agent = create_brand_guidelines_agent(context)
    
    # Chain them together in a SequentialAgent
    # This is ALL we need - ADK will handle running them in sequence
    strategy_sequential_agent = SequentialAgent(
        name="v3_strategy_generator",
        sub_agents=[
            business_agent,
            competitive_agent,
            customer_agent,
            marketing_agent,
            brand_agent
        ],
        description="Generates all 5 strategy documents in sequence using existing properly-implemented agents"
    )
    
    logger.info(f"✅ V3 Sequential Agent created with 5 strategy agents for {context.company_name}")
    return strategy_sequential_agent


# For deployment, we need a way to create the agent without context
def create_v3_strategy_agent_for_deployment():
    """
    Create a wrapper agent for deployment that will create the sequential agent when invoked.
    This is needed because we can't pass context at deployment time.
    """
    from google.adk.agents import Agent
    
    def execute_strategy_generation(
        company_name: str,
        industry: str,
        websites: str,
        customer_regions: str,
        account_id: str,
        user_id: str,
        annual_ad_budget: float = 0.0
    ) -> str:
        """Execute the V3 strategy generation with the existing agents."""
        
        # Create context from inputs
        context = StrategyContext(
            account_id=account_id,
            user_id=user_id,
            company_name=company_name,
            websites=websites.split(',') if websites else [],
            industry=industry,
            customer_regions=customer_regions.split(',') if customer_regions else [],
            annual_ad_budget=annual_ad_budget
        )
        
        # Create the sequential agent with context
        sequential_agent = create_v3_strategy_sequential_agent(context)
        
        # The sequential agent will run all 5 agents automatically
        # Each agent already saves to Firestore internally
        
        return f"Strategy generation initiated for {company_name}. Running 5 sequential agents with refinement loops."
    
    # Create wrapper agent
    wrapper_agent = Agent(
        name="v3_strategy_wrapper",
        model="gemini-2.0-flash",
        instruction="""You coordinate V3 strategy document generation.
        
When asked to generate strategies, use the execute_strategy_generation tool.
The tool will create and run a SequentialAgent with 5 strategy agents.""",
        tools=[execute_strategy_generation]
    )
    
    return wrapper_agent


# Create the agent for deployment
try:
    strategy_agent = create_v3_strategy_agent_for_deployment()
    
    # Wrap with AdkApp for deployment
    app = reasoning_engines.AdkApp(
        agent=strategy_agent,
        enable_tracing=True
    )
    
    logger.info("✅ V3 Strategy Agent ready for deployment")
except Exception as e:
    logger.error(f"Failed to create V3 Strategy Agent: {e}")
    strategy_agent = None
    app = None


# Export for use
__all__ = ['strategy_agent', 'app', 'create_v3_strategy_sequential_agent']