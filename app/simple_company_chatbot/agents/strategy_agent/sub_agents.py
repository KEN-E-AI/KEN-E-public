"""
V3 Strategy Agent System - 5 Specialized Sequential Agents.
Each agent has its own strategist-reviewer-editor refinement loop.
"""

import logging
from typing import Dict, Any, Optional

from google.adk.agents import Agent, SequentialAgent, LoopAgent
from google.adk.tools import google_search, ToolContext, VertexAiSearchTool, AgentTool

# Use absolute imports for deployment, fall back to relative for local testing
try:
    from agents.strategy_agent.models import StrategyContext
    from agents.strategy_agent.utils import get_best_practices, get_reviewer_guidelines
    from agents.strategy_agent.context import context_manager
except ImportError:
    from .models import StrategyContext
    from .utils import get_best_practices, get_reviewer_guidelines
    from .context import context_manager

logger = logging.getLogger(__name__)

# Configuration - will be loaded from environment or Firestore
DATASTORE_ID = "projects/ken-e-dev/locations/us-central1/collections/default_collection/dataStores/strategy-docs-acc-test-account_1755429117747"


# ============================================================================
# Common Tools and Helper Functions
# ============================================================================

def exit_loop(tool_context: ToolContext, final_document: str = ""):
    """Call this function ONLY when the document is approved, signaling the loop should end."""
    print(f"  [Tool Call] exit_loop triggered by {tool_context.agent_name}")
    
    # Print the final strategy document before exiting
    print("\n" + "="*60)
    print("🎯 FINAL APPROVED STRATEGY DOCUMENT:")
    print("="*60)
    
    if final_document:
        print(final_document)
    else:
        print("⚠️ No final document provided to exit_loop function")
    
    print("="*60 + "\n")
    
    tool_context.actions.escalate = True
    return {"status": "Loop terminated successfully", "document_displayed": bool(final_document)}


def create_internal_search_agent() -> Agent:
    """Create the internal search agent that uses Vertex AI Search."""
    return Agent(
        name="internal_search_agent",
        model="gemini-2.0-flash",
        instruction="Answer questions using Vertex AI Search to find information from internal documents. Always cite sources when available.",
        description="Enterprise document search assistant with Vertex AI Search capabilities",
        tools=[VertexAiSearchTool(data_store_id=DATASTORE_ID)]
    )


def create_google_search_agent() -> Agent:
    """Create the Google search agent for external research."""
    return Agent(
        name="google_search_agent",
        model="gemini-2.0-flash",
        instruction="Answer questions using Google Search to find information on the Internet. Always cite sources when available.",
        description="Internet research assistant with Google Search capabilities",
        tools=[google_search]
    )


# ============================================================================
# 1. BUSINESS STRATEGY AGENT
# ============================================================================

def create_business_strategist(context: Optional[StrategyContext] = None) -> Agent:
    """Create the business strategy strategist agent."""
    internal_search = create_internal_search_agent()
    google_search_agent = create_google_search_agent()
    
    # Extract company details from context for template substitution
    company_name = context.company_name if context else "the company"
    industry = context.industry if context else "the industry"
    
    # Import the synchronous versions for use in agent context
    from .utils import get_best_practices_sync, extract_field_requirements_from_best_practices
    
    # Fetch best practices from Firestore
    best_practices = get_best_practices_sync("business_strategy")
    if not best_practices:
        logger.warning("Using default best practices for business_strategy")
        best_practices = "Create a comprehensive business strategy document with all required sections."
    
    # Dynamically extract output requirements from best practices
    output_requirements = extract_field_requirements_from_best_practices(best_practices)
    
    # Get instruction from Excel specification
    instruction = f"""
# ROLE & GOAL
You are a Strategic Business Expert creating a comprehensive business strategy document.

Your task is to create a comprehensive business strategy document that follows the BEST PRACTICES for the company specified in the NEW INFORMATION.
This document will serve as the foundation for downstream tactical marketing plans.
Use your tool 'google_search_agent' to review the website provided in the NEW INFORMATION, and search for relevant information about the business on the Internet.

# BEST PRACTICES
{best_practices}

Some queries you can use to learn about the business strategy include:
- '{company_name} industry'
- '{company_name} competitors in the industry: {industry}'
- '{company_name} mission vision values'
- '{company_name} financial performance revenue'
- '{company_name} market size trends'
- '{company_name} products services'
- '{company_name} customer segments'

{output_requirements}
"""
    
    return Agent(
        name="business_strategist",
        model="gemini-2.0-flash",
        tools=[AgentTool(agent=internal_search), AgentTool(agent=google_search_agent)],
        description="Strategic business expert that creates comprehensive business strategy documents",
        instruction=instruction,
        output_key="updated_strategy_doc"
    )


def create_business_reviewer() -> Agent:
    """Create the business strategy reviewer agent."""
    # Import the synchronous versions for use in agent context
    from .utils import (
        get_reviewer_guidelines_sync, 
        get_best_practices_sync,
        extract_validation_criteria_from_guidelines
    )
    
    # Fetch reviewer guidelines from Firestore
    reviewer_guidelines = get_reviewer_guidelines_sync("business_strategy")
    if not reviewer_guidelines:
        logger.warning("Using default reviewer guidelines for business_strategy")
        reviewer_guidelines = "Review the document for completeness, accuracy, and strategic alignment."
    
    # Fetch best practices to know what fields to validate
    best_practices = get_best_practices_sync("business_strategy")
    if not best_practices:
        logger.warning("Using default best practices for business_strategy validation")
        best_practices = "{}"
    
    # Dynamically extract validation criteria
    validation_process = extract_validation_criteria_from_guidelines(reviewer_guidelines, best_practices)
    
    return Agent(
        name="business_reviewer",
        model="gemini-2.0-flash",
        tools=[],
        description="Expert reviewer for business strategy documents",
        instruction=f"""
# ROLE & GOAL
You are an experienced Business Strategy Reviewer. Your goal is to review a business strategy document against provided guidelines.

# REVIEWER GUIDELINES
{reviewer_guidelines}

{validation_process}

# OUTPUT REQUIREMENTS
- IF any issues found: Provide specific, actionable feedback listing EXACTLY which fields are missing or incorrect
- ELSE: Respond exactly with: 'The document meets all criteria.'
""",
        output_key="criticism"
    )


def create_business_editor() -> Agent:
    """Create the business strategy editor agent."""
    internal_search = create_internal_search_agent()
    google_search_agent = create_google_search_agent()
    
    return Agent(
        name="business_editor",
        model="gemini-2.0-flash",
        tools=[AgentTool(agent=internal_search), AgentTool(agent=google_search_agent), exit_loop],
        description="Expert editor for business strategy documents",
        instruction="""
# ROLE & GOAL
You are a Senior Business Strategy Editor refining documents based on feedback.

# CRITICAL INSTRUCTION
Check the criticism first. If the criticism is EXACTLY "The document meets all criteria." (case-sensitive match), then immediately call exit_loop().

# INPUTS AVAILABLE
- criticism: The reviewer's feedback
- updated_strategy_doc: The current business strategy document (from strategist or previous editor iteration)

# PROCESS
1. Read the criticism carefully
2. If criticism == "The document meets all criteria.": Call exit_loop() with no parameters
3. If changes needed: Take the updated_strategy_doc and modify it based on the criticism

# OUTPUT REQUIREMENTS
- If calling exit_loop: Call the function exit_loop() and provide no text output
- If editing: Return ONLY the complete revised JSON document (the modified updated_strategy_doc)
""",
        output_key="updated_strategy_doc"
    )


def create_business_strategy_agent(context: Optional[StrategyContext] = None) -> SequentialAgent:
    """Create the complete business strategy agent with refinement loop."""
    strategist = create_business_strategist(context)
    reviewer = create_business_reviewer()
    editor = create_business_editor()
    
    refinement_loop = LoopAgent(
        name="business_refinement_loop",
        sub_agents=[reviewer, editor],
        description="Refines business strategy through review cycles",
        max_iterations=3
    )
    
    return SequentialAgent(
        name="business_strategy_agent",
        sub_agents=[strategist, refinement_loop],
        description="Creates comprehensive business strategy documents"
    )


# ============================================================================
# 2. COMPETITIVE STRATEGY AGENT
# ============================================================================

def create_competitive_strategist(context: Optional[StrategyContext] = None) -> Agent:
    """Create the competitive strategy strategist agent."""
    internal_search = create_internal_search_agent()
    google_search_agent = create_google_search_agent()
    
    # Import the synchronous versions for use in agent context
    from .utils import get_best_practices_sync, extract_field_requirements_from_best_practices
    
    # Fetch best practices from Firestore
    best_practices = get_best_practices_sync("competitive_strategy")
    if not best_practices:
        logger.warning("Using default best practices for competitive_strategy")
        best_practices = "Create a comprehensive competitive strategy document with all required sections."
    
    # Dynamically extract output requirements from best practices
    output_requirements = extract_field_requirements_from_best_practices(best_practices)
    
    # Build instruction that will access state at runtime
    instruction = f"""
# ROLE & GOAL
You are a Competitive Strategy Expert creating a comprehensive competitive strategy document.

Your task is to create a comprehensive competitive strategy document that follows the BEST PRACTICES document for the company specified in the NEW INFORMATION provided.
This document will serve as the foundation for downstream tactical marketing plans.

# BEST PRACTICES
{best_practices}

# PREVIOUS STRATEGY OUTPUTS
You have access to the business strategy document from the previous agent.
The business strategy document (if available) will be in the state as 'updated_strategy_doc'.
Use ALL 6 fields from the business strategy to inform your competitive analysis:
- businessStrategySummary
- companyOverview  
- marketAndIndustryAnalysis
- productsAndServices
- marketingAndCustomerStrategy
- swotAnalysis

If a business strategy document is available in the state, incorporate its insights into your competitive analysis.

TOOLS: Use your tool 'google_search_agent' to conduct research on the business and its competitors using Google search.

{output_requirements}
"""
    
    return Agent(
        name="competitive_strategist",
        model="gemini-2.0-flash",
        tools=[AgentTool(agent=internal_search), AgentTool(agent=google_search_agent)],
        description="Competitive strategy expert that analyzes market competition",
        instruction=instruction,
        output_key="updated_strategy_doc"
    )


def create_competitive_reviewer() -> Agent:
    """Create the competitive strategy reviewer agent."""
    # Import the synchronous versions for use in agent context
    from .utils import (
        get_reviewer_guidelines_sync, 
        get_best_practices_sync,
        extract_validation_criteria_from_guidelines
    )
    
    # Fetch reviewer guidelines from Firestore
    reviewer_guidelines = get_reviewer_guidelines_sync("competitive_strategy")
    if not reviewer_guidelines:
        logger.warning("Using default reviewer guidelines for competitive_strategy")
        reviewer_guidelines = "Review the document for competitive analysis completeness."
    
    # Fetch best practices to know what fields to validate
    best_practices = get_best_practices_sync("competitive_strategy")
    if not best_practices:
        logger.warning("Using default best practices for competitive_strategy validation")
        best_practices = "{}"
    
    # Dynamically extract validation criteria
    validation_process = extract_validation_criteria_from_guidelines(reviewer_guidelines, best_practices)
    
    return Agent(
        name="competitive_reviewer",
        model="gemini-2.0-flash",
        tools=[],
        description="Expert reviewer for competitive strategy documents",
        instruction=f"""
# ROLE & GOAL
You are an experienced Competitive Strategy Reviewer.

# REVIEWER GUIDELINES
{reviewer_guidelines}

{validation_process}

# OUTPUT REQUIREMENTS
- IF any issues found: Provide specific feedback
- ELSE: Respond exactly with: 'The document meets all criteria.'
""",
        output_key="criticism"
    )


def create_competitive_editor() -> Agent:
    """Create the competitive strategy editor agent."""
    internal_search = create_internal_search_agent()
    google_search_agent = create_google_search_agent()
    
    return Agent(
        name="competitive_editor",
        model="gemini-2.0-flash",
        tools=[AgentTool(agent=internal_search), AgentTool(agent=google_search_agent), exit_loop],
        description="Expert editor for competitive strategy documents",
        instruction="""
# ROLE & GOAL
You are a Senior Competitive Strategy Editor.

# CRITICAL INSTRUCTION
If criticism is EXACTLY "The document meets all criteria." then immediately call exit_loop().

# INPUTS AVAILABLE
- criticism: The reviewer's feedback
- updated_strategy_doc: The current competitive strategy document

# OUTPUT REQUIREMENTS
- If calling exit_loop: Call the function exit_loop() and provide no text output
- If editing: Return ONLY the complete revised JSON document (the modified updated_strategy_doc)
""",
        output_key="updated_strategy_doc"
    )


def create_competitive_strategy_agent(context: Optional[StrategyContext] = None) -> SequentialAgent:
    """Create the complete competitive strategy agent with refinement loop."""
    strategist = create_competitive_strategist(context)
    reviewer = create_competitive_reviewer()
    editor = create_competitive_editor()
    
    refinement_loop = LoopAgent(
        name="competitive_refinement_loop",
        sub_agents=[reviewer, editor],
        description="Refines competitive strategy through review cycles",
        max_iterations=3
    )
    
    return SequentialAgent(
        name="competitive_strategy_agent",
        sub_agents=[strategist, refinement_loop],
        description="Creates comprehensive competitive strategy documents"
    )


# ============================================================================
# 3. CUSTOMER STRATEGY AGENT
# ============================================================================

def create_customer_strategist(context: Optional[StrategyContext] = None) -> Agent:
    """Create the customer strategy strategist agent."""
    internal_search = create_internal_search_agent()
    google_search_agent = create_google_search_agent()
    
    # Import the synchronous versions for use in agent context
    from .utils import get_best_practices_sync, extract_field_requirements_from_best_practices
    
    # Fetch best practices from Firestore
    best_practices = get_best_practices_sync("customer_strategy")
    if not best_practices:
        logger.warning("Using default best practices for customer_strategy")
        best_practices = "Create a comprehensive customer strategy document with detailed personas."
    
    # Dynamically extract output requirements from best practices
    output_requirements = extract_field_requirements_from_best_practices(best_practices)
    
    # Build instruction that will access state at runtime
    instruction = f"""
# ROLE & GOAL
You are a Customer Strategy Expert creating a comprehensive customer strategy document.

Your task is to create a comprehensive customer strategy document that follows the BEST PRACTICES document for the company specified in the NEW INFORMATION provided.

# BEST PRACTICES
{best_practices}
Think carefully about the ideal customer profiles, and create 3-5 ideal customer profiles that showcase the different pain points and buyer motivation for each persona.
Consider how customers within each persona might become aware of the company, the critical information that they are looking for when considering making a purchase, and how they might become loyal return customers in the future.

# PREVIOUS STRATEGY OUTPUTS
You have access to strategy documents from previous agents in the state.
The state may contain:
1. Business strategy document with these 6 fields:
   - businessStrategySummary
   - companyOverview
   - marketAndIndustryAnalysis
   - productsAndServices
   - marketingAndCustomerStrategy
   - swotAnalysis

2. Competitive strategy document with these 3 fields:
   - competitiveLandscape
   - competitiveStrategySummary
   - strategicRecommendations

Use insights from BOTH the business and competitive strategies to inform your customer personas and journey maps.

TOOLS: Use your tool 'google_search_agent' to conduct research on the business, its customers, and its competitors with Google search.

{output_requirements}
"""
    
    return Agent(
        name="customer_strategist",
        model="gemini-2.0-flash",
        tools=[AgentTool(agent=internal_search), AgentTool(agent=google_search_agent)],
        description="Customer strategy expert that creates detailed personas and journey maps",
        instruction=instruction,
        output_key="updated_strategy_doc"
    )


def create_customer_reviewer() -> Agent:
    """Create the customer strategy reviewer agent."""
    # Import the synchronous versions for use in agent context
    from .utils import (
        get_reviewer_guidelines_sync, 
        get_best_practices_sync,
        extract_validation_criteria_from_guidelines
    )
    
    # Fetch reviewer guidelines from Firestore
    reviewer_guidelines = get_reviewer_guidelines_sync("customer_strategy")
    if not reviewer_guidelines:
        logger.warning("Using default reviewer guidelines for customer_strategy")
        reviewer_guidelines = "Review the document for detailed personas and journey maps."
    
    # Fetch best practices to know what fields to validate
    best_practices = get_best_practices_sync("customer_strategy")
    if not best_practices:
        logger.warning("Using default best practices for customer_strategy validation")
        best_practices = "{}"
    
    # Dynamically extract validation criteria
    validation_process = extract_validation_criteria_from_guidelines(reviewer_guidelines, best_practices)
    
    return Agent(
        name="customer_reviewer",
        model="gemini-2.0-flash",
        tools=[],
        description="Expert reviewer for customer strategy documents",
        instruction=f"""
# ROLE & GOAL
You are an experienced Customer Strategy Reviewer.

# REVIEWER GUIDELINES
{reviewer_guidelines}

{validation_process}

# OUTPUT REQUIREMENTS
- IF any issues found: Provide specific feedback
- ELSE: Respond exactly with: 'The document meets all criteria.'
""",
        output_key="criticism"
    )


def create_customer_editor() -> Agent:
    """Create the customer strategy editor agent."""
    internal_search = create_internal_search_agent()
    google_search_agent = create_google_search_agent()
    
    return Agent(
        name="customer_editor",
        model="gemini-2.0-flash",
        tools=[AgentTool(agent=internal_search), AgentTool(agent=google_search_agent), exit_loop],
        description="Expert editor for customer strategy documents",
        instruction="""
# ROLE & GOAL
You are a Senior Customer Strategy Editor.

# CRITICAL INSTRUCTION
If criticism is EXACTLY "The document meets all criteria." then immediately call exit_loop().

# INPUTS AVAILABLE
- criticism: The reviewer's feedback
- updated_strategy_doc: The current customer strategy document

# OUTPUT REQUIREMENTS
- If calling exit_loop: Call the function exit_loop() and provide no text output
- If editing: Return ONLY the complete revised JSON document (the modified updated_strategy_doc)
""",
        output_key="updated_strategy_doc"
    )


def create_customer_strategy_agent(context: Optional[StrategyContext] = None) -> SequentialAgent:
    """Create the complete customer strategy agent with refinement loop."""
    strategist = create_customer_strategist(context)
    reviewer = create_customer_reviewer()
    editor = create_customer_editor()
    
    refinement_loop = LoopAgent(
        name="customer_refinement_loop",
        sub_agents=[reviewer, editor],
        description="Refines customer strategy through review cycles",
        max_iterations=3
    )
    
    return SequentialAgent(
        name="customer_strategy_agent",
        sub_agents=[strategist, refinement_loop],
        description="Creates comprehensive customer strategy documents"
    )


# ============================================================================
# 4. MARKETING STRATEGY AGENT
# ============================================================================

def create_marketing_strategist(context: Optional[StrategyContext] = None) -> Agent:
    """Create the marketing strategy strategist agent."""
    internal_search = create_internal_search_agent()
    google_search_agent = create_google_search_agent()
    
    # Import the synchronous versions for use in agent context
    from .utils import get_best_practices_sync, extract_field_requirements_from_best_practices
    
    # Fetch best practices from Firestore
    best_practices = get_best_practices_sync("marketing_strategy")
    if not best_practices:
        logger.warning("Using default best practices for marketing_strategy")
        best_practices = "Create a comprehensive marketing strategy document with campaign plans."
    
    # Dynamically extract output requirements from best practices
    output_requirements = extract_field_requirements_from_best_practices(best_practices)
    
    # Build instruction that will access state at runtime
    instruction = f"""
# ROLE & GOAL
You are a Marketing Strategy Expert creating a comprehensive marketing strategy document.

Your task is to create a comprehensive marketing strategy document that follows the BEST PRACTICES document for the company specified in the NEW INFORMATION provided.

# BEST PRACTICES
{best_practices}

# PREVIOUS STRATEGY OUTPUTS
You have access to strategy documents from ALL previous agents in the state.
The state contains:

1. Business strategy document with these 6 fields:
   - businessStrategySummary
   - companyOverview
   - marketAndIndustryAnalysis
   - productsAndServices
   - marketingAndCustomerStrategy
   - swotAnalysis

2. Competitive strategy document with these 3 fields:
   - competitiveLandscape
   - competitiveStrategySummary
   - strategicRecommendations

3. Customer strategy document with these 3 fields:
   - customerProfiles
   - customerJourneyMaps
   - personaInsights

Use insights from ALL three previous strategies (business, competitive, and customer) to inform your marketing campaigns and channel strategies.

You must propose paid digital marketing campaigns for key channels such as Search, Youtube, Display and Gmail. 
For each campaign, describe the objective, audience, budget allocation, expected outcomes, expected CPM or CPC, and KPIs.

TOOLS: Use your tool 'google_search_agent' to conduct research on marketing best practices and channel strategies.

{output_requirements}
"""
    
    return Agent(
        name="marketing_strategist",
        model="gemini-2.0-flash",
        tools=[AgentTool(agent=internal_search), AgentTool(agent=google_search_agent)],
        description="Marketing strategy expert that creates comprehensive campaign plans",
        instruction=instruction,
        output_key="updated_strategy_doc"
    )


def create_marketing_reviewer() -> Agent:
    """Create the marketing strategy reviewer agent."""
    # Import the synchronous versions for use in agent context
    from .utils import (
        get_reviewer_guidelines_sync, 
        get_best_practices_sync,
        extract_validation_criteria_from_guidelines
    )
    
    # Fetch reviewer guidelines from Firestore
    reviewer_guidelines = get_reviewer_guidelines_sync("marketing_strategy")
    if not reviewer_guidelines:
        logger.warning("Using default reviewer guidelines for marketing_strategy")
        reviewer_guidelines = "Review the document for comprehensive campaign strategies."
    
    # Fetch best practices to know what fields to validate
    best_practices = get_best_practices_sync("marketing_strategy")
    if not best_practices:
        logger.warning("Using default best practices for marketing_strategy validation")
        best_practices = "{}"
    
    # Dynamically extract validation criteria
    validation_process = extract_validation_criteria_from_guidelines(reviewer_guidelines, best_practices)
    
    return Agent(
        name="marketing_reviewer",
        model="gemini-2.0-flash",
        tools=[],
        description="Expert reviewer for marketing strategy documents",
        instruction=f"""
# ROLE & GOAL
You are an experienced Marketing Strategy Reviewer.

# REVIEWER GUIDELINES
{reviewer_guidelines}

{validation_process}

# OUTPUT REQUIREMENTS
- IF any issues found: Provide specific feedback
- ELSE: Respond exactly with: 'The document meets all criteria.'
""",
        output_key="criticism"
    )


def create_marketing_editor() -> Agent:
    """Create the marketing strategy editor agent."""
    internal_search = create_internal_search_agent()
    google_search_agent = create_google_search_agent()
    
    return Agent(
        name="marketing_editor",
        model="gemini-2.0-flash",
        tools=[AgentTool(agent=internal_search), AgentTool(agent=google_search_agent), exit_loop],
        description="Expert editor for marketing strategy documents",
        instruction="""
# ROLE & GOAL
You are a Senior Marketing Strategy Editor.

# CRITICAL INSTRUCTION
If criticism is EXACTLY "The document meets all criteria." then immediately call exit_loop().

# INPUTS AVAILABLE
- criticism: The reviewer's feedback
- updated_strategy_doc: The current marketing strategy document

# OUTPUT REQUIREMENTS
- If calling exit_loop: Call the function exit_loop() and provide no text output
- If editing: Return ONLY the complete revised JSON document (the modified updated_strategy_doc)
""",
        output_key="updated_strategy_doc"
    )


def create_marketing_strategy_agent(context: Optional[StrategyContext] = None) -> SequentialAgent:
    """Create the complete marketing strategy agent with refinement loop."""
    strategist = create_marketing_strategist(context)
    reviewer = create_marketing_reviewer()
    editor = create_marketing_editor()
    
    refinement_loop = LoopAgent(
        name="marketing_refinement_loop",
        sub_agents=[reviewer, editor],
        description="Refines marketing strategy through review cycles",
        max_iterations=3
    )
    
    return SequentialAgent(
        name="marketing_strategy_agent",
        sub_agents=[strategist, refinement_loop],
        description="Creates comprehensive marketing strategy documents"
    )


# ============================================================================
# 5. BRAND GUIDELINES AGENT
# ============================================================================

def create_brand_strategist(context: Optional[StrategyContext] = None) -> Agent:
    """Create the brand guidelines strategist agent."""
    internal_search = create_internal_search_agent()
    google_search_agent = create_google_search_agent()
    
    # Import the synchronous versions for use in agent context
    from .utils import get_best_practices_sync, extract_field_requirements_from_best_practices
    
    # Fetch best practices from Firestore
    best_practices = get_best_practices_sync("brand_guidelines")
    if not best_practices:
        logger.warning("Using default best practices for brand_guidelines")
        best_practices = "Create comprehensive brand guidelines with visual and messaging frameworks."
    
    # Dynamically extract output requirements from best practices
    output_requirements = extract_field_requirements_from_best_practices(best_practices)
    
    # Build instruction that will access state at runtime
    instruction = f"""
# ROLE & GOAL
You are a Brand Strategy Expert creating comprehensive brand guidelines.

Your task is to create a comprehensive brand guidelines document that follows the BEST PRACTICES document for the company specified in the NEW INFORMATION provided.

# BEST PRACTICES
{best_practices}

# PREVIOUS STRATEGY OUTPUTS
You have access to strategy documents from ALL previous agents in the state.
The state contains:

1. Business strategy document with these 5 fields (excluding SWOT):
   - businessStrategySummary
   - companyOverview
   - marketAndIndustryAnalysis
   - productsAndServices
   - marketingAndCustomerStrategy

2. Competitive strategy document with these 2 fields (excluding competitiveLandscape):
   - competitiveStrategySummary
   - strategicRecommendations

3. Customer strategy document with these 3 fields:
   - customerProfiles
   - customerJourneyMaps
   - personaInsights

4. Marketing strategy document with these 3 fields:
   - channelStrategies
   - campaignPlans
   - messagingFramework

Use insights from ALL four previous strategies to inform your brand guidelines.

This document will serve as the foundation for all marketing communications and ensure brand consistency across all touchpoints.

TOOLS: Use your tool 'google_search_agent' to research the company's current brand presence and industry best practices.

{output_requirements}
"""
    
    return Agent(
        name="brand_strategist",
        model="gemini-2.0-flash",
        tools=[AgentTool(agent=internal_search), AgentTool(agent=google_search_agent)],
        description="Brand strategy expert that creates comprehensive brand guidelines",
        instruction=instruction,
        output_key="updated_strategy_doc"
    )


def create_brand_reviewer() -> Agent:
    """Create the brand guidelines reviewer agent."""
    # Import the synchronous versions for use in agent context
    from .utils import (
        get_reviewer_guidelines_sync, 
        get_best_practices_sync,
        extract_validation_criteria_from_guidelines
    )
    
    # Fetch reviewer guidelines from Firestore
    reviewer_guidelines = get_reviewer_guidelines_sync("brand_guidelines")
    if not reviewer_guidelines:
        logger.warning("Using default reviewer guidelines for brand_guidelines")
        reviewer_guidelines = "Review the document for comprehensive brand elements."
    
    # Fetch best practices to know what fields to validate
    best_practices = get_best_practices_sync("brand_guidelines")
    if not best_practices:
        logger.warning("Using default best practices for brand_guidelines validation")
        best_practices = "{}"
    
    # Dynamically extract validation criteria
    validation_process = extract_validation_criteria_from_guidelines(reviewer_guidelines, best_practices)
    
    return Agent(
        name="brand_reviewer",
        model="gemini-2.0-flash",
        tools=[],
        description="Expert reviewer for brand guidelines documents",
        instruction=f"""
# ROLE & GOAL
You are an experienced Brand Guidelines Reviewer.

# REVIEWER GUIDELINES
{reviewer_guidelines}

{validation_process}

# OUTPUT REQUIREMENTS
- IF any issues found: Provide specific feedback
- ELSE: Respond exactly with: 'The document meets all criteria.'
""",
        output_key="criticism"
    )


def create_brand_editor() -> Agent:
    """Create the brand guidelines editor agent."""
    internal_search = create_internal_search_agent()
    google_search_agent = create_google_search_agent()
    
    return Agent(
        name="brand_editor",
        model="gemini-2.0-flash",
        tools=[AgentTool(agent=internal_search), AgentTool(agent=google_search_agent), exit_loop],
        description="Expert editor for brand guidelines documents",
        instruction="""
# ROLE & GOAL
You are a Senior Brand Guidelines Editor.

# CRITICAL INSTRUCTION
If criticism is EXACTLY "The document meets all criteria." then immediately call exit_loop().

# INPUTS AVAILABLE
- criticism: The reviewer's feedback
- updated_strategy_doc: The current brand guidelines document

# OUTPUT REQUIREMENTS
- If calling exit_loop: Call the function exit_loop() and provide no text output
- If editing: Return ONLY the complete revised JSON document (the modified updated_strategy_doc)
""",
        output_key="updated_strategy_doc"
    )


def create_brand_guidelines_agent(context: Optional[StrategyContext] = None) -> SequentialAgent:
    """Create the complete brand guidelines agent with refinement loop."""
    strategist = create_brand_strategist(context)
    reviewer = create_brand_reviewer()
    editor = create_brand_editor()
    
    refinement_loop = LoopAgent(
        name="brand_refinement_loop",
        sub_agents=[reviewer, editor],
        description="Refines brand guidelines through review cycles",
        max_iterations=3
    )
    
    return SequentialAgent(
        name="brand_guidelines_agent",
        sub_agents=[strategist, refinement_loop],
        description="Creates comprehensive brand guidelines documents"
    )