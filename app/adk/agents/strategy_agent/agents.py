"""
Strategy agent implementations for KEN-E marketing analysis.
These agents create the 5 core strategy documents.
"""

import logging
import json
from typing import Optional, Dict, Any, List
from google.adk.agents import Agent, SequentialAgent, LoopAgent
from google.adk.tools import AgentTool, exit_loop, google_search
from google.genai import types

# Import models
from .models import StrategyContext

# Set up logging
logger = logging.getLogger(__name__)

# Import Firestore utilities
try:
    from .firestore import (
        get_best_practices_sync,
        get_reviewer_guidelines_sync,
        extract_field_requirements_from_best_practices,
        format_new_information
    )
    FIRESTORE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Firestore utilities not available: {e}")
    FIRESTORE_AVAILABLE = False
    # Define stubs
    def get_best_practices_sync(doc_type: str) -> Optional[str]:
        return None
    def get_reviewer_guidelines_sync(doc_type: str) -> Optional[str]:
        return None
    def extract_field_requirements_from_best_practices(best_practices: str) -> str:
        return ""
    def format_new_information(**kwargs) -> str:
        return json.dumps(kwargs)


# ============================================================================
# SHARED COMPONENTS
# ============================================================================

def create_google_search_agent() -> Agent:
    """Create the Google search sub-agent used by all strategy agents."""
    return Agent(
        name="google_search_agent",
        model="gemini-2.5-flash",
        tools=[google_search],
        description="Expert web researcher that searches Google for public information",
        instruction="Search for relevant public information about the topic. Focus on official sources and recent data.",
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192
        )
    )


# ============================================================================
# 1. BUSINESS STRATEGY AGENT
# ============================================================================

def create_business_strategist(context: Optional[StrategyContext] = None) -> Agent:
    """Create the business strategy strategist agent."""
    google_search_agent = create_google_search_agent()
    
    # Safely extract context information with proper None handling
    if context:
        company_name = context.company_name
        industry = context.industry
        new_information = format_new_information(
            company_name=context.company_name,
            websites=context.websites,
            industry=context.industry,
            customer_regions=context.customer_regions,
            annual_ad_budget=context.annual_ad_budget
        )
    else:
        company_name = "the company"
        industry = "the industry"
        new_information = "No context provided"
    
    # Import the synchronous versions for use in agent context
    from .firestore import get_best_practices_sync, extract_field_requirements_from_best_practices
    
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
You are a Strategic Marketing Expert. 
Your goal is to create a comprehensive business strategy document based on the provided information.

CRITICAL: You MUST output a complete JSON strategy document that follows the provided BEST PRACTICES schema exactly.

# TOOLS
- google_search_agent: Uses Google search to find relevant information on the Internet

# YOUR TASK
You will receive several inputs in your conversation:
- BEST PRACTICES: A JSON schema that defines the exact structure your output must follow
- NEW INFORMATION: Details about the company to research and analyze

# PERSONA
You are an expert business consultant, meticulous in your analysis and precise in your writing. 
You ensure all outputs are professional, robust, and strictly adhere to provided guidelines. 
You are a critical thinker who can synthesize disparate information into a coherent strategic plan.

# PROCESS
You must follow this logic precisely:
1. **Analyze All Inputs:** Begin by thoroughly reading and understanding the query and all provided documents (`BUSINESS INFORMATION`, and `BEST PRACTICES`).
   - Review the contents of the company websites `BUSINESS INFORMATION` section.

2. **Research Requirements:**
   - **MANDATORY**: Research each item defined in the BEST PRACTICES.
   - If you cannot find information needed for a section on the provided websites, try searching for it. Search for multiple queries related to each section you need to complete.
   - If you are unable to find information needed for a section on the provided website or through a search, insert the text: "requires further research"
   - **MANDATORY**: You MUST add references any time you insert information that was found through one of your search agents so that the source document can be reviewed later.
   - Think carefully and take your time to ensure the document is comprehensive and accurate
   - Use specific, targeted search queries like:
    - '{company_name} industry'
    - '{company_name} competitors in the industry: {industry}'
    - '{company_name} mission vision values'
    - '{company_name} financial performance revenue'
    - '{company_name} market size trends'
    - '{company_name} products services'
    - '{company_name} customer segments'

3. **Create New Document**
   - Synthesize your research findings into a complete, new strategy document that is well referenced with the URL's of the sources.
   - **MANDATORY**: You MUST add references any time you insert information that was found through one of your search agents so that the source document can be reviewed later.

4. **Final Review and Formatting:**
   - This is the most critical step. Before providing your response, validate your entire draft against the `BEST PRACTICES`.
   - Ensure every section, heading, and requirement from the guide is perfectly represented in your output document.

# OUTPUT REQUIREMENTS
- Your response must be ONLY the complete JSON strategy document
- Your final output MUST be the complete and final strategy document with ALL sections filled out based on your research.
- The structure, sections, and formatting of your response MUST EXACTLY MATCH the specifications in the `BEST PRACTICES`.
- For each top-level key in the final JSON, the value MUST be a single string. Synthesize the analysis of all required sub-topics for a given section into one cohesive narrative string. DO NOT use nested JSON objects.
- DO NOT include any conversational text, preambles, or explanations in your output. Your response should only be the document itself.
- DO NOT leave any placeholder text or "requires further research" statements.

=== BEGIN INPUT DATA ===

BEST PRACTICES DOCUMENT:
{best_practices}

BUSINESS INFORMATION:
{new_information}

=== END INPUT DATA ===

Based on the above inputs, create the complete Business Strategy document now.
"""
    
    return Agent(
        name="business_strategist",
        model="gemini-2.5-pro",
        tools=[AgentTool(agent=google_search_agent)],
        description="Strategic business expert that creates comprehensive business strategy documents",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=65535
        ),
        output_key="business_strategy_doc"
    )


def create_business_reviewer() -> Agent:
    """Create the business strategy reviewer agent."""
    from .firestore import get_reviewer_guidelines_sync
    
    guidelines = get_reviewer_guidelines_sync("business_strategy")
    if not guidelines:
        logger.warning("Using default review guidelines for business_strategy")
        guidelines = "Review the business strategy document for completeness and accuracy."
    
    instruction = f"""
You are a Senior Strategy Reviewer. Review the business strategy document and provide specific feedback.

# REVIEW GUIDELINES
{guidelines}

# YOUR TASK
1. Check if all required sections from BEST PRACTICES are present
2. Verify information accuracy and completeness
3. Identify any gaps or areas needing improvement
4. Provide specific, actionable feedback

# OUTPUT FORMAT
Provide your review as a structured list of:
- Missing sections (if any)
- Incomplete areas needing more detail
- Specific improvements needed
- Quality assessment (1-10 score)

Be constructive and specific in your feedback.
"""
    
    return Agent(
        name="business_reviewer",
        model="gemini-2.5-flash",
        description="Reviews business strategy documents for quality and completeness",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192
        ),
        output_key="review_feedback"
    )


def create_business_editor() -> Agent:
    """Create the business strategy editor agent."""
    google_search_agent = create_google_search_agent()
    
    instruction = """
You are a Strategy Document Editor. Based on the review feedback, improve the business strategy document.

# YOUR TASK
1. Address each point of feedback from the reviewer
2. Use google_search_agent to find missing information
3. Enhance sections that need more detail
4. Ensure the final document meets all requirements

# OUTPUT FORMAT
Provide the complete, updated business strategy document in JSON format.
All feedback points must be addressed.
"""
    
    return Agent(
        name="business_editor",
        model="gemini-2.5-flash",
        tools=[AgentTool(agent=google_search_agent), exit_loop],
        description="Edits and improves business strategy documents based on feedback",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=65535
        ),
        output_key="business_strategy_doc"
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
    google_search_agent = create_google_search_agent()
    
    # Safely extract context information with proper None handling
    if context:
        company_name = context.company_name
        industry = context.industry
        new_information = format_new_information(
            company_name=context.company_name,
            websites=context.websites,
            industry=context.industry,
            customer_regions=context.customer_regions,
            annual_ad_budget=context.annual_ad_budget
        )
    else:
        company_name = "the company"
        industry = "the industry"
        new_information = "No context provided"
    
    # Import the synchronous versions for use in agent context
    from .firestore import get_best_practices_sync, extract_field_requirements_from_best_practices
    
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

# TOOLS
- google_search_agent: Uses Google search to find relevant information on the Internet

# YOUR TASK
You will receive several inputs in your conversation:
- BEST PRACTICES: A JSON schema that defines the exact structure your output must follow
- NEW INFORMATION: Details about the company to research and analyze

# PROCESS
Follow this process:
1. Research {company_name} and its competitive landscape
2. Identify key competitors in {industry}
3. Analyze competitive positioning and strategies
4. Create comprehensive competitive analysis following BEST PRACTICES

Use specific search queries like:
- '{company_name} competitors'
- '{industry} market leaders'
- '{company_name} vs competitor comparison'
- '{industry} market share analysis'

# OUTPUT REQUIREMENTS
- Output ONLY the complete JSON strategy document
- Follow the BEST PRACTICES structure exactly
- Include all required sections with detailed analysis

=== BEGIN INPUT DATA ===

BEST PRACTICES DOCUMENT:
{best_practices}

OUTPUT REQUIREMENTS:
{output_requirements}

NEW INFORMATION:
{new_information}

=== END INPUT DATA ===

Create the complete Competitive Strategy document now.
"""
    
    return Agent(
        name="competitive_strategist",
        model="gemini-2.5-pro",
        tools=[AgentTool(agent=google_search_agent)],
        description="Competitive intelligence expert that creates detailed competitive analysis",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=65535
        ),
        output_key="competitive_strategy_doc"
    )


def create_competitive_reviewer() -> Agent:
    """Create the competitive strategy reviewer agent."""
    from .firestore import get_reviewer_guidelines_sync
    
    guidelines = get_reviewer_guidelines_sync("competitive_strategy")
    if not guidelines:
        logger.warning("Using default review guidelines for competitive_strategy")
        guidelines = "Review the competitive strategy document for completeness and accuracy."
    
    instruction = f"""
You are a Senior Competitive Intelligence Reviewer. Review the competitive strategy document.

# REVIEW GUIDELINES
{guidelines}

# YOUR TASK
1. Verify competitor identification is comprehensive
2. Check competitive analysis depth and accuracy
3. Assess strategic recommendations quality
4. Provide specific improvement feedback

# OUTPUT FORMAT
Provide structured feedback with:
- Missing competitors or analysis gaps
- Areas needing deeper analysis
- Strategic insights quality (1-10)
- Specific improvements needed
"""
    
    return Agent(
        name="competitive_reviewer",
        model="gemini-2.5-flash",
        description="Reviews competitive strategy documents",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192
        ),
        output_key="review_feedback"
    )


def create_competitive_editor() -> Agent:
    """Create the competitive strategy editor agent."""
    google_search_agent = create_google_search_agent()
    
    instruction = """
You are a Competitive Strategy Editor. Improve the document based on review feedback.

# YOUR TASK
1. Address all reviewer feedback points
2. Research missing competitor information
3. Deepen analysis where needed
4. Enhance strategic recommendations

# OUTPUT FORMAT
Provide the complete, updated competitive strategy document in JSON format.
"""
    
    return Agent(
        name="competitive_editor",
        model="gemini-2.5-flash",
        tools=[AgentTool(agent=google_search_agent), exit_loop],
        description="Edits competitive strategy documents",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=65535
        ),
        output_key="competitive_strategy_doc"
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
    google_search_agent = create_google_search_agent()
    
    # Safely extract context information with proper None handling
    if context:
        company_name = context.company_name
        industry = context.industry
        new_information = format_new_information(
            company_name=context.company_name,
            websites=context.websites,
            industry=context.industry,
            customer_regions=context.customer_regions,
            annual_ad_budget=context.annual_ad_budget
        )
    else:
        company_name = "the company"
        industry = "the industry"
        new_information = "No context provided"
    
    # Import the synchronous versions for use in agent context
    from .firestore import get_best_practices_sync, extract_field_requirements_from_best_practices
    
    # Fetch best practices from Firestore
    best_practices = get_best_practices_sync("customer_strategy")
    if not best_practices:
        logger.warning("Using default best practices for customer_strategy")
        best_practices = "Create a comprehensive customer strategy document with all required sections."
    
    # Dynamically extract output requirements from best practices
    output_requirements = extract_field_requirements_from_best_practices(best_practices)
    
    instruction = f"""
# ROLE & GOAL
You are a Customer Insights Expert creating a comprehensive customer strategy document.

# TOOLS
- google_search_agent: Research customer demographics, behaviors, and preferences

# YOUR TASK
Create a customer strategy document following BEST PRACTICES for {company_name} in {industry}.

# PROCESS
1. Research target customer segments
2. Analyze customer needs and pain points
3. Map customer journey and touchpoints
4. Develop customer engagement strategies

Use search queries like:
- '{company_name} target customers'
- '{industry} customer demographics'
- '{company_name} customer reviews feedback'
- '{industry} buyer behavior trends'

# OUTPUT REQUIREMENTS
- Output ONLY the complete JSON strategy document
- Follow BEST PRACTICES structure exactly
- Include detailed customer insights

=== BEGIN INPUT DATA ===

BEST PRACTICES DOCUMENT:
{best_practices}

OUTPUT REQUIREMENTS:
{output_requirements}

NEW INFORMATION:
{new_information}

=== END INPUT DATA ===

Create the complete Customer Strategy document now.
"""
    
    return Agent(
        name="customer_strategist",
        model="gemini-2.5-pro",
        tools=[AgentTool(agent=google_search_agent)],
        description="Customer insights expert that creates detailed customer strategy documents",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=65535
        ),
        output_key="customer_strategy_doc"
    )


def create_customer_reviewer() -> Agent:
    """Create the customer strategy reviewer agent."""
    from .firestore import get_reviewer_guidelines_sync
    
    guidelines = get_reviewer_guidelines_sync("customer_strategy")
    if not guidelines:
        logger.warning("Using default review guidelines for customer_strategy")
        guidelines = "Review the customer strategy document for completeness and accuracy."
    
    instruction = f"""
You are a Senior Customer Experience Reviewer. Review the customer strategy document.

# REVIEW GUIDELINES
{guidelines}

# YOUR TASK
1. Verify customer segmentation completeness
2. Check persona development quality
3. Assess journey mapping accuracy
4. Review engagement strategy effectiveness

# OUTPUT FORMAT
Provide structured feedback with:
- Missing customer insights
- Persona development gaps
- Journey mapping improvements
- Quality score (1-10)
"""
    
    return Agent(
        name="customer_reviewer",
        model="gemini-2.5-flash",
        description="Reviews customer strategy documents",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192
        ),
        output_key="review_feedback"
    )


def create_customer_editor() -> Agent:
    """Create the customer strategy editor agent."""
    google_search_agent = create_google_search_agent()
    
    instruction = """
You are a Customer Strategy Editor. Improve the document based on review feedback.

# YOUR TASK
1. Address all feedback points
2. Research missing customer insights
3. Enhance personas and journey maps
4. Strengthen engagement strategies

# OUTPUT FORMAT
Provide the complete, updated customer strategy document in JSON format.
"""
    
    return Agent(
        name="customer_editor",
        model="gemini-2.5-flash",
        tools=[AgentTool(agent=google_search_agent), exit_loop],
        description="Edits customer strategy documents",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=65535
        ),
        output_key="customer_strategy_doc"
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
    google_search_agent = create_google_search_agent()
    
    # Safely extract context information with proper None handling
    if context:
        company_name = context.company_name
        industry = context.industry
        new_information = format_new_information(
            company_name=context.company_name,
            websites=context.websites,
            industry=context.industry,
            customer_regions=context.customer_regions,
            annual_ad_budget=context.annual_ad_budget
        )
    else:
        company_name = "the company"
        industry = "the industry"
        new_information = "No context provided"
    
    # Import the synchronous versions for use in agent context
    from .firestore import get_best_practices_sync, extract_field_requirements_from_best_practices
    
    # Fetch best practices from Firestore
    best_practices = get_best_practices_sync("marketing_strategy")
    if not best_practices:
        logger.warning("Using default best practices for marketing_strategy")
        best_practices = "Create a comprehensive marketing strategy document with all required sections."
    
    # Dynamically extract output requirements from best practices
    output_requirements = extract_field_requirements_from_best_practices(best_practices)
    
    instruction = f"""
# ROLE & GOAL
You are a Marketing Strategy Expert creating a comprehensive marketing strategy document.

# TOOLS
- google_search_agent: Research marketing trends, channels, and best practices

# YOUR TASK
Create a marketing strategy document following BEST PRACTICES for {company_name} in {industry}.

# PROCESS
1. Define marketing objectives and KPIs
2. Develop positioning and messaging
3. Plan marketing mix and channels
4. Create campaign and content strategies

Use search queries like:
- '{industry} marketing trends 2024'
- '{company_name} marketing campaigns'
- '{industry} marketing channels effectiveness'
- 'digital marketing best practices {industry}'

# OUTPUT REQUIREMENTS
- Output ONLY the complete JSON strategy document
- Follow BEST PRACTICES structure exactly
- Include actionable marketing plans

=== BEGIN INPUT DATA ===

BEST PRACTICES DOCUMENT:
{best_practices}

OUTPUT REQUIREMENTS:
{output_requirements}

NEW INFORMATION:
{new_information}

=== END INPUT DATA ===

Create the complete Marketing Strategy document now.
"""
    
    return Agent(
        name="marketing_strategist",
        model="gemini-2.5-pro",
        tools=[AgentTool(agent=google_search_agent)],
        description="Marketing strategy expert that creates comprehensive marketing plans",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=65535
        ),
        output_key="marketing_strategy_doc"
    )


def create_marketing_reviewer() -> Agent:
    """Create the marketing strategy reviewer agent."""
    from .firestore import get_reviewer_guidelines_sync
    
    guidelines = get_reviewer_guidelines_sync("marketing_strategy")
    if not guidelines:
        logger.warning("Using default review guidelines for marketing_strategy")
        guidelines = "Review the marketing strategy document for completeness and accuracy."
    
    instruction = f"""
You are a Senior Marketing Reviewer. Review the marketing strategy document.

# REVIEW GUIDELINES
{guidelines}

# YOUR TASK
1. Verify marketing objectives clarity
2. Check channel strategy effectiveness
3. Assess campaign planning quality
4. Review budget allocation logic

# OUTPUT FORMAT
Provide structured feedback with:
- Missing marketing elements
- Channel strategy gaps
- Campaign planning improvements
- Quality score (1-10)
"""
    
    return Agent(
        name="marketing_reviewer",
        model="gemini-2.5-flash",
        description="Reviews marketing strategy documents",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192
        ),
        output_key="review_feedback"
    )


def create_marketing_editor() -> Agent:
    """Create the marketing strategy editor agent."""
    google_search_agent = create_google_search_agent()
    
    instruction = """
You are a Marketing Strategy Editor. Improve the document based on review feedback.

# YOUR TASK
1. Address all feedback points
2. Research marketing best practices
3. Enhance channel and campaign strategies
4. Optimize budget recommendations

# OUTPUT FORMAT
Provide the complete, updated marketing strategy document in JSON format.
"""
    
    return Agent(
        name="marketing_editor",
        model="gemini-2.5-flash",
        tools=[AgentTool(agent=google_search_agent), exit_loop],
        description="Edits marketing strategy documents",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=65535
        ),
        output_key="marketing_strategy_doc"
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
    google_search_agent = create_google_search_agent()
    
    # Safely extract context information with proper None handling
    if context:
        company_name = context.company_name
        industry = context.industry
        new_information = format_new_information(
            company_name=context.company_name,
            websites=context.websites,
            industry=context.industry,
            customer_regions=context.customer_regions,
            annual_ad_budget=context.annual_ad_budget
        )
    else:
        company_name = "the company"
        industry = "the industry"
        new_information = "No context provided"
    
    # Import the synchronous versions for use in agent context
    from .firestore import get_best_practices_sync, extract_field_requirements_from_best_practices
    
    # Fetch best practices from Firestore
    best_practices = get_best_practices_sync("brand_guidelines")
    if not best_practices:
        logger.warning("Using default best practices for brand_guidelines")
        best_practices = "Create comprehensive brand guidelines with all required sections."
    
    # Dynamically extract output requirements from best practices
    output_requirements = extract_field_requirements_from_best_practices(best_practices)
    
    instruction = f"""
# ROLE & GOAL
You are a Brand Strategy Expert creating comprehensive brand guidelines.

# TOOLS
- google_search_agent: Research brand positioning and industry standards

# YOUR TASK
Create brand guidelines following BEST PRACTICES for {company_name} in {industry}.

# PROCESS
1. Define brand mission, vision, and values
2. Develop brand personality and voice
3. Create messaging framework
4. Establish brand standards and guidelines

Use search queries like:
- '{company_name} brand identity'
- '{industry} branding best practices'
- '{company_name} mission vision values'
- 'brand voice examples {industry}'

# OUTPUT REQUIREMENTS
- Output ONLY the complete JSON guidelines document
- Follow BEST PRACTICES structure exactly
- Include comprehensive brand standards

=== BEGIN INPUT DATA ===

BEST PRACTICES DOCUMENT:
{best_practices}

OUTPUT REQUIREMENTS:
{output_requirements}

NEW INFORMATION:
{new_information}

=== END INPUT DATA ===

Create the complete Brand Guidelines document now.
"""
    
    return Agent(
        name="brand_strategist",
        model="gemini-2.5-pro",
        tools=[AgentTool(agent=google_search_agent)],
        description="Brand strategy expert that creates comprehensive brand guidelines",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=65535
        ),
        output_key="brand_guidelines_doc"
    )


def create_brand_reviewer() -> Agent:
    """Create the brand guidelines reviewer agent."""
    from .firestore import get_reviewer_guidelines_sync
    
    guidelines = get_reviewer_guidelines_sync("brand_guidelines")
    if not guidelines:
        logger.warning("Using default review guidelines for brand_guidelines")
        guidelines = "Review the brand guidelines for completeness and consistency."
    
    instruction = f"""
You are a Senior Brand Reviewer. Review the brand guidelines document.

# REVIEW GUIDELINES
{guidelines}

# YOUR TASK
1. Verify brand identity completeness
2. Check voice and tone consistency
3. Assess visual guidelines quality
4. Review usage standards clarity

# OUTPUT FORMAT
Provide structured feedback with:
- Missing brand elements
- Consistency issues
- Guidelines clarity improvements
- Quality score (1-10)
"""
    
    return Agent(
        name="brand_reviewer",
        model="gemini-2.5-flash",
        description="Reviews brand guidelines documents",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192
        ),
        output_key="review_feedback"
    )


def create_brand_editor() -> Agent:
    """Create the brand guidelines editor agent."""
    google_search_agent = create_google_search_agent()
    
    instruction = """
You are a Brand Guidelines Editor. Improve the document based on review feedback.

# YOUR TASK
1. Address all feedback points
2. Research brand best practices
3. Enhance brand standards clarity
4. Ensure comprehensive coverage

# OUTPUT FORMAT
Provide the complete, updated brand guidelines document in JSON format.
"""
    
    return Agent(
        name="brand_editor",
        model="gemini-2.5-flash",
        tools=[AgentTool(agent=google_search_agent), exit_loop],
        description="Edits brand guidelines documents",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=65535
        ),
        output_key="brand_guidelines_doc"
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