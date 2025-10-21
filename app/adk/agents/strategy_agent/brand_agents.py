"""
Split agent architecture for brand guidelines.

Following ADK constraint workaround: Agents with output_schema cannot use tools.
- Researcher agent: Has tools (google_search), NO output_schema
- Formatter agent: NO tools, has output_schema with BrandGuidelines model

Configurations are now loaded from Firestore for easy iteration without redeployment.
"""

import google.adk as adk
from google.adk.tools import AgentTool
from google.genai.types import GenerateContentConfig

from .brand_models import BrandGuidelines
from .config_loader import create_agent_from_firestore_config


def create_brand_researcher(google_search_agent):
    """
    Create researcher agent that gathers brand guidelines information.

    This agent:
    - HAS tools (google_search)
    - NO output_schema
    - Returns unstructured research data
    - Configuration loaded from Firestore for easy iteration

    Args:
        google_search_agent: Google search tool agent

    Returns:
        ADK Agent for brand research
    """
    return create_agent_from_firestore_config(
        doc_id="brand_researcher",
        google_search_agent=google_search_agent,
    )


def create_brand_formatter():
    """
    Create formatter agent that structures research into BrandGuidelines schema.

    This agent:
    - NO tools
    - HAS output_schema (BrandGuidelines)
    - Converts unstructured research into structured JSON
    - Configuration loaded from Firestore for easy iteration

    Returns:
        ADK Agent for formatting brand guidelines
    """
    return create_agent_from_firestore_config(
        doc_id="brand_formatter",
        output_schema=BrandGuidelines,
    )
