"""
Split agent architecture for marketing and customer intelligence analysis.

Following ADK constraint workaround: Agents with output_schema cannot use tools.
- Researcher agent: Has tools (google_search), NO output_schema
- Formatter agent: NO tools, has output_schema with MarketingResearchReport model

Configurations are now loaded from Firestore for easy iteration without redeployment.
"""

import google.adk as adk
from google.adk.tools import AgentTool
from google.genai.types import GenerateContentConfig

from .config_loader import create_agent_from_firestore_config
from .marketing_models import MarketingResearchReport


def create_marketing_researcher(google_search_agent):
    """
    Create researcher agent that gathers marketing and customer intelligence.

    This agent:
    - HAS tools (google_search)
    - NO output_schema
    - Returns unstructured research data
    - Configuration loaded from Firestore for easy iteration

    Args:
        google_search_agent: Google search tool agent

    Returns:
        ADK Agent for marketing research
    """
    return create_agent_from_firestore_config(
        doc_id="marketing_researcher",
        google_search_agent=google_search_agent,
    )


def create_marketing_formatter():
    """
    Create formatter agent that structures research into MarketingResearchReport schema.

    This agent:
    - NO tools
    - HAS output_schema (MarketingResearchReport)
    - Converts unstructured research into structured JSON
    - Configuration loaded from Firestore for easy iteration

    Returns:
        ADK Agent for formatting marketing research
    """
    return create_agent_from_firestore_config(
        doc_id="marketing_formatter",
        output_schema=MarketingResearchReport,
    )
