"""
Split agent architecture for business strategy.

Following ADK constraint workaround: Agents with output_schema cannot use tools.
- Researcher agent: Has tools (google_search), NO output_schema
- Formatter agent: NO tools, has output_schema with StructuredBusinessStrategy model
"""

import os
import json
from typing import Dict, Any
import google.adk as adk
from google.genai.types import GenerateContentConfig
from google.adk.tools import AgentTool
from .structured_models import StructuredBusinessStrategy


def create_business_researcher(google_search_agent):
    """
    Create researcher agent that gathers business strategy information.

    This agent:
    - HAS tools (google_search)
    - NO output_schema
    - Returns unstructured research data

    Args:
        google_search_agent: Google search tool agent

    Returns:
        ADK Agent for business research
    """
    return adk.Agent(
        name="business_researcher",
        description="Researches business strategy information",
        model="gemini-2.0-flash",
        tools=[AgentTool(agent=google_search_agent)],
        generate_content_config=GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=4000  # Limit to prevent rate limit issues
        ),
        instruction="""You are a business strategy researcher.

For the company mentioned by the user, research and provide a comprehensive report covering:

1. Company Overview - History, mission, vision, current status
2. Business Value Propositions - Core value the company delivers to customers overall
3. Products and Services - Product categories and specific products with their value propositions
4. SWOT Analysis - For each strength, identify opportunities it creates. For each weakness, identify risks it exposes.
5. Strategic Goals - Top strategic objectives the company should focus on

Use the google_search agent to find current information about the company.
Provide detailed, factual research findings.
Be specific and include examples of how strengths create opportunities and weaknesses create risks."""
    )


def create_business_formatter():
    """
    Create formatter agent that structures research into StructuredBusinessStrategy schema.

    This agent:
    - NO tools
    - HAS output_schema (StructuredBusinessStrategy)
    - Converts unstructured research into structured JSON

    Returns:
        ADK Agent for formatting business strategy
    """
    return adk.Agent(
        name="business_formatter",
        description="Formats business research into structured strategy",
        model="gemini-2.5-pro",  # Using 2.5 Pro for better schema handling
        tools=[],  # NO tools - required for output_schema
        generate_content_config=GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=4000,
            response_mime_type="application/json"
        ),
        output_schema=StructuredBusinessStrategy,
        instruction="""You are a business strategy formatter.

Take the research report provided by the user and format it into a structured business strategy.

For the structured output:

1. Extract 1-5 business-level value propositions that describe the overall company value
2. Extract 1-5 main product categories with 1-5 specific products each
3. For SWOT Analysis:
   - Identify 1-5 core strengths, and for EACH strength list 1-5 opportunities it creates
   - Identify 1-5 key weaknesses, and for EACH weakness list 1-5 risks it exposes
4. Identify 1-5 strategic goals

Create IDs using lowercase-hyphenated format (e.g., 'strength-brand-recognition').
Be specific and actionable in all descriptions.
Ensure all required fields are populated."""
    )


def format_with_openai(research_data: str) -> Dict[str, Any]:
    """
    Use OpenAI to format research data into structured strategy.
    OpenAI handles complex schemas better than Gemini.

    Args:
        research_data: Unstructured research text

    Returns:
        Dictionary matching StructuredBusinessStrategy schema
    """
    from openai import OpenAI as OpenAIClient

    client = OpenAIClient(api_key=os.getenv('OPENAI_API_KEY'))

    # Use the chat.completions.parse method (beta is needed for parse)
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",  # Use the specific model that supports structured outputs
        messages=[
            {"role": "system", "content": """You are a business strategy formatter.

Take the research report provided and format it into a structured business strategy.

For the structured output:
1. Extract 1-5 business-level value propositions that describe the overall company value
2. Extract 1-5 main product categories with 1-5 specific products each
3. For SWOT Analysis:
   - Identify 1-5 core strengths, and for EACH strength list 1-5 opportunities it creates
   - Identify 1-5 key weaknesses, and for EACH weakness list 1-5 risks it exposes
4. Identify 1-5 strategic goals

Create IDs using lowercase-hyphenated format (e.g., 'strength-brand-recognition').
Be specific and actionable in all descriptions.
Ensure all required fields are populated."""},
            {"role": "user", "content": f"Format this research into structured business strategy:\n\n{research_data}"}
        ],
        # Pass the Pydantic class directly - OpenAI will handle the conversion
        response_format=StructuredBusinessStrategy
    )

    # The parsed response is in the parsed attribute
    if completion.choices[0].message.parsed:
        # Convert to dict for compatibility with the rest of our code
        return completion.choices[0].message.parsed.model_dump()
    else:
        # Fallback to JSON content if parsing failed
        return json.loads(completion.choices[0].message.content)
