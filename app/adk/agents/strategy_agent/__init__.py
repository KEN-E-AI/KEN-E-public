"""
Strategy Agent System - Simplified architecture for generating strategy documents.
"""

from .orchestrator import (
    strategy_agent,
    app,
    create_strategy_sequential_agent,
    execute_strategy_generation
)

from .models import (
    StrategyContext,
    StrategyGenerationRequest,
    StrategyGenerationResponse
)

from .agents import (
    create_business_strategy_agent,
    create_competitive_strategy_agent,
    create_customer_strategy_agent,
    create_marketing_strategy_agent,
    create_brand_guidelines_agent
)

__all__ = [
    # Main orchestrator
    'strategy_agent',
    'app',
    'create_strategy_sequential_agent',
    'execute_strategy_generation',
    
    # Models
    'StrategyContext',
    'StrategyGenerationRequest',
    'StrategyGenerationResponse',
    
    # Individual agents
    'create_business_strategy_agent',
    'create_competitive_strategy_agent',
    'create_customer_strategy_agent',
    'create_marketing_strategy_agent',
    'create_brand_guidelines_agent'
]