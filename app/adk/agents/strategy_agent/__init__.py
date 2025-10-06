"""
Strategy Agent System - Split agent architecture with Neo4j knowledge graph.

Architecture:
- Researcher agents: Have tools (google_search), NO output_schema
- Formatter agents: NO tools, have output_schema
- Neo4j: Knowledge graph storage with embeddings for semantic search
- Firestore: Backup document storage
"""

# Import models (safe, no circular deps)
from .models import (
    StrategyContext,
    StrategyGenerationRequest,
    StrategyGenerationResponse,
)

# Import shared components (safe)
from .agents import (
    create_google_search_agent,
)

# NOTE: orchestrator imports removed to avoid circular dependency
# Import orchestrator functions directly from orchestrator module when needed:
# from agents.strategy_agent.orchestrator import execute_strategy_generation_direct, app

__all__ = [
    # Models
    "StrategyContext",
    "StrategyGenerationRequest",
    "StrategyGenerationResponse",
    # Shared components
    "create_google_search_agent",
]
