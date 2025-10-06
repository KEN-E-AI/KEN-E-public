"""
Split agent architecture for competitive analysis.

Following ADK constraint workaround: Agents with output_schema cannot use tools.
- Researcher agent: Has tools (google_search), NO output_schema
- Formatter agent: NO tools, has output_schema with CompetitiveAnalysis model
"""

import google.adk as adk
from google.genai.types import GenerateContentConfig
from google.adk.tools import AgentTool
from .competitive_models import CompetitiveAnalysis


def create_competitive_researcher(google_search_agent):
    """
    Create researcher agent that gathers competitive intelligence.

    This agent:
    - HAS tools (google_search)
    - NO output_schema
    - Returns unstructured research data

    Args:
        google_search_agent: Google search tool agent

    Returns:
        ADK Agent for competitive research
    """
    return adk.Agent(
        name="competitive_researcher",
        description="Researches competitors and competitive environment",
        model="gemini-2.0-flash",
        tools=[AgentTool(agent=google_search_agent)],
        # NO output_schema - this allows tool usage
        generate_content_config=GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=2500  # Limit to prevent rate limit issues
        ),
        instruction="""You are a competitive intelligence researcher. Your role is to:

1. Identify and research the top competitors for the given company
2. Analyze the competitive environment and strategy
3. Gather detailed information about each competitor:
   - Company background, size, revenue, pricing strategy
   - Distribution channels and brand positioning
   - Their core value propositions (why customers choose them)
   - Marketing tactics they use (social media campaigns, events, ads, content marketing, etc.)
   - Key products/services that compete with the company's offerings
   - Competitor STRENGTHS: For each strength, identify the RISKS it creates for our company
   - Competitor WEAKNESSES: For each weakness, identify the OPPORTUNITIES it creates for our company
   - For substitute products: The key value proposition of each product

4. Use web search extensively to find accurate, current information
5. Return comprehensive research findings as unstructured text

Focus on actionable competitive intelligence that helps understand:
- Who are the direct competitors?
- What are their value propositions and how do they market?
- What products compete with our offerings?
- What strengths do they have (and what risks do those create for us)?
- What weaknesses can we exploit (and what opportunities do those create)?

Provide detailed findings with specific examples and data where possible."""
    )


def create_competitive_formatter():
    """
    Create formatter agent that structures research into CompetitiveAnalysis schema.

    This agent:
    - NO tools
    - HAS output_schema (CompetitiveAnalysis)
    - Converts unstructured research into structured JSON

    Returns:
        ADK Agent for formatting competitive analysis
    """
    return adk.Agent(
        name="competitive_formatter",
        description="Formats competitive research into structured analysis",
        model="gemini-2.5-pro",  # Using 2.5 Pro for better schema handling
        tools=[],  # NO tools - required for output_schema
        generate_content_config=GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=8000,
            response_mime_type="application/json"
        ),
        output_schema=CompetitiveAnalysis,  # Enforces JSON structure
        instruction="""You are a competitive analysis formatter. Your role is to:

1. Take unstructured competitive intelligence research
2. Extract and organize it into a structured CompetitiveAnalysis format
3. Ensure all required fields are populated with high-quality information

Guidelines:
- Identify 1-10 top competitors based on the research
- For each competitor, extract:
  * Name and comprehensive description (history, size, revenue, pricing, distribution, positioning)
  * 1-5 core value propositions explaining why customers choose them
  * 1-5 marketing tactics they use (social media, events, ads, etc.)
  * 1-5 substitute products with detailed descriptions
  * For each substitute product: ONE key value proposition
  * 1-10 key strengths with names, descriptions, AND 1-5 risks each strength creates for your company
  * 1-10 weaknesses with names, descriptions, AND 1-5 opportunities each weakness creates for your company

- Write clear, concise names (e.g., "Brand Recognition", "Market Leader")
- Provide detailed descriptions with specific examples
- Focus on actionable competitive intelligence
- Ensure the competitive_environment_description explains the strategy
  used to identify competitors (geography, size, brand awareness, etc.)

Output valid JSON matching the CompetitiveAnalysis schema EXACTLY.
Ensure all required fields are populated."""
    )
