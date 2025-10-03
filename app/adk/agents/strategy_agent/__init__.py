"""
Strategy Agent System - Split agent architecture with Neo4j knowledge graph.

Architecture:
- Researcher agents: Have tools (google_search), NO output_schema
- Formatter agents: NO tools, have output_schema
- Neo4j: Knowledge graph storage with embeddings for semantic search
- Firestore: Backup document storage
"""

from .orchestrator import (
    strategy_agent,
    app,
    execute_strategy_generation,
    execute_strategy_generation_direct,
    extract_document_sections,
)

from .models import (
    StrategyContext,
    StrategyGenerationRequest,
    StrategyGenerationResponse,
)

from .agents import (
    create_google_search_agent,
)

# Import split agent modules
from . import business_agents
from . import competitive_agents
from . import marketing_agents
from . import brand_agents

# Import graph builders
from . import business_graph_builder
from . import competitive_graph_builder
from . import marketing_graph_builder
from . import brand_graph_builder

# Import Neo4j and embeddings
from . import neo4j_tools
from . import embeddings

__all__ = [
    # Main orchestrator
    "strategy_agent",
    "app",
    "execute_strategy_generation",
    "execute_strategy_generation_direct",
    "extract_document_sections",
    # Models
    "StrategyContext",
    "StrategyGenerationRequest",
    "StrategyGenerationResponse",
    # Shared components
    "create_google_search_agent",
    # Split agent modules
    "business_agents",
    "competitive_agents",
    "marketing_agents",
    "brand_agents",
    # Graph builders
    "business_graph_builder",
    "competitive_graph_builder",
    "marketing_graph_builder",
    "brand_graph_builder",
    # Infrastructure
    "neo4j_tools",
    "embeddings",
]
