"""
Split agent architecture for competitive analysis.

Following ADK constraint workaround: Agents with output_schema cannot use tools.
- Researcher agent: Has tools (google_search), NO output_schema
- Formatter agent: NO tools, has output_schema with CompetitiveAnalysis model

Configurations are now loaded from Firestore for easy iteration without redeployment.
"""


from .competitive_models import CompetitiveAnalysis
from .config_loader import create_agent_from_firestore_config


def create_competitive_researcher(google_search_agent):
    """
    Create researcher agent that gathers competitive intelligence.

    This agent:
    - HAS tools (google_search)
    - NO output_schema
    - Returns unstructured research data
    - Configuration loaded from Firestore for easy iteration

    Args:
        google_search_agent: Google search tool agent

    Returns:
        ADK Agent for competitive research
    """
    return create_agent_from_firestore_config(
        doc_id="competitive_researcher",
        google_search_agent=google_search_agent,
    )


def create_competitive_formatter():
    """
    Create formatter agent that structures research into CompetitiveAnalysis schema.

    This agent:
    - NO tools
    - HAS output_schema (CompetitiveAnalysis)
    - Converts unstructured research into structured JSON
    - Configuration loaded from Firestore for easy iteration

    Returns:
        ADK Agent for formatting competitive analysis
    """
    return create_agent_from_firestore_config(
        doc_id="competitive_formatter",
        output_schema=CompetitiveAnalysis,
    )
