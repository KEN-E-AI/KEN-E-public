"""
Split agent architecture for business strategy.

Following ADK constraint workaround: Agents with output_schema cannot use tools.
- Researcher agent: Has tools (google_search), NO output_schema
- Formatter agent: NO tools, has output_schema with StructuredBusinessStrategy model

Configurations are now loaded from Firestore for easy iteration without redeployment.
"""

import json
import os
from typing import Any

from .config_loader import create_agent_from_firestore_config
from .structured_models import StructuredBusinessStrategy


def create_business_researcher(google_search_agent):
    """
    Create researcher agent that gathers business strategy information.

    This agent:
    - HAS tools (google_search)
    - NO output_schema
    - Returns unstructured research data
    - Configuration loaded from Firestore for easy iteration

    Args:
        google_search_agent: Google search tool agent

    Returns:
        ADK Agent for business research
    """
    return create_agent_from_firestore_config(
        doc_id="business_researcher",
        google_search_agent=google_search_agent,
    )


def create_business_formatter():
    """
    Create formatter agent that structures research into StructuredBusinessStrategy schema.

    This agent:
    - NO tools
    - HAS output_schema (StructuredBusinessStrategy)
    - Converts unstructured research into structured JSON
    - Configuration loaded from Firestore for easy iteration

    Returns:
        ADK Agent for formatting business strategy
    """
    return create_agent_from_firestore_config(
        doc_id="business_formatter",
        output_schema=StructuredBusinessStrategy,
    )


def format_with_openai(research_data: str) -> dict[str, Any]:
    """
    Use OpenAI to format research data into structured strategy.
    OpenAI handles complex schemas better than Gemini.

    Args:
        research_data: Unstructured research text

    Returns:
        Dictionary matching StructuredBusinessStrategy schema
    """
    from openai import OpenAI as OpenAIClient

    client = OpenAIClient(api_key=os.getenv("OPENAI_API_KEY"))

    # Use the chat.completions.parse method (beta is needed for parse)
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",  # Use the specific model that supports structured outputs
        messages=[
            {
                "role": "system",
                "content": """You are a business strategy formatter.

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
Ensure all required fields are populated.

CRITICAL: ONLY use information explicitly stated in the research provided. If specific details (like revenue figures, market metrics, or technical specifications) are not provided in the research, use placeholder values like "Not specified in research" or mark fields as unavailable. DO NOT invent, infer, or hallucinate data points, metrics, or technical specifications. When information is incomplete, explicitly indicate what is missing rather than filling in plausible-sounding but fabricated details.""",
            },
            {
                "role": "user",
                "content": f"Format this research into structured business strategy:\n\n{research_data}",
            },
        ],
        # Pass the Pydantic class directly - OpenAI will handle the conversion
        response_format=StructuredBusinessStrategy,
    )

    # The parsed response is in the parsed attribute
    if completion.choices[0].message.parsed:
        # Convert to dict for compatibility with the rest of our code
        return completion.choices[0].message.parsed.model_dump()
    else:
        # Fallback to JSON content if parsing failed
        return json.loads(completion.choices[0].message.content)
