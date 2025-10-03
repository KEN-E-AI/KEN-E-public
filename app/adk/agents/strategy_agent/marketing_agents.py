"""
Split agent architecture for marketing and customer intelligence analysis.

Following ADK constraint workaround: Agents with output_schema cannot use tools.
- Researcher agent: Has tools (google_search), NO output_schema
- Formatter agent: NO tools, has output_schema with MarketingResearchReport model
"""

import google.adk as adk
from google.genai.types import GenerateContentConfig
from google.adk.tools import AgentTool
from .marketing_models import MarketingResearchReport


def create_marketing_researcher(google_search_agent):
    """
    Create researcher agent that gathers marketing and customer intelligence.

    This agent:
    - HAS tools (google_search)
    - NO output_schema
    - Returns unstructured research data

    Args:
        google_search_agent: Google search tool agent

    Returns:
        ADK Agent for marketing research
    """
    return adk.Agent(
        name="marketing_researcher",
        description="Researches customer profiles and marketing strategies",
        model="gemini-2.0-flash",
        tools=[AgentTool(agent=google_search_agent)],
        # NO output_schema - this allows tool usage
        generate_content_config=GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=4000  # Limit to prevent rate limit issues
        ),
        instruction="""You are a marketing intelligence researcher. Your role is to:

1. Research ideal customer profiles for each product category
2. For each customer profile, analyze:
   - Customer persona: Background, pain points, needs, motivations, communication preferences
   - Problem Awareness: How to make them aware of the problem the product solves
   - Brand Awareness: How to make them aware of the company and its products
   - Consideration: How they evaluate products and what influences their decision
   - Conversion: Critical factors that lead them to purchase
   - Loyalty: What makes them advocates and repeat customers

3. Use web search extensively to find:
   - Market research on customer segments
   - Consumer behavior patterns
   - Marketing channel effectiveness
   - Customer journey insights
   - Competitive positioning

4. For EACH product category, identify 2-5 distinct ideal customer profiles
5. Provide comprehensive, detailed research findings

Focus on actionable marketing intelligence that helps understand:
- Who are our ideal customers?
- What problems do they face?
- How do they discover and evaluate solutions?
- What motivates them to buy and stay loyal?

Provide detailed findings with specific examples and data where possible."""
    )


def create_marketing_formatter():
    """
    Create formatter agent that structures research into MarketingResearchReport schema.

    This agent:
    - NO tools
    - HAS output_schema (MarketingResearchReport)
    - Converts unstructured research into structured JSON

    Returns:
        ADK Agent for formatting marketing research
    """
    return adk.Agent(
        name="marketing_formatter",
        description="Formats marketing research into structured analysis",
        model="gemini-2.5-pro",  # Using 2.5 Pro for better schema handling
        tools=[],  # NO tools - required for output_schema
        generate_content_config=GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=8000,
            response_mime_type="application/json"
        ),
        output_schema=MarketingResearchReport,  # Enforces JSON structure
        instruction="""You are a marketing research formatter. Your role is to:

1. Take unstructured marketing intelligence research
2. Extract and organize it into a structured MarketingResearchReport format
3. Ensure all required fields are populated with high-quality information

Guidelines:
- Identify all product categories mentioned in the research
- For each product category, extract 2-5 distinct ideal customer profiles
- For each customer profile, create:
  * A narrative describing the persona (name, background, pain points, needs, motivations, channels)
  * Problem awareness strategy (max 4000 chars) - how to make them aware of the problem
  * Brand awareness strategy (max 4000 chars) - how to introduce the brand
  * Consideration strategy (max 4000 chars) - how they evaluate options
  * Conversion strategy (max 4000 chars) - critical factors for purchase decision
  * Loyalty strategy (max 4000 chars) - how to foster retention and advocacy

- Write detailed, actionable strategies with specific channels and touchpoints
- Include concrete examples and tactics
- Focus on practical, implementable marketing approaches
- Ensure each strategy is comprehensive (close to max length when appropriate)

Output valid JSON matching the MarketingResearchReport schema EXACTLY.
Ensure all required fields are populated with rich, detailed content."""
    )
